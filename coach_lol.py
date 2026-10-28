"""
Quíron — coach de voz para League of Legends
=======================================================

Lê a Live Client Data API OFICIAL da Riot (https://127.0.0.1:2999), que o
próprio cliente do LoL disponibiliza no seu PC durante a partida, e dá
lembretes por voz.

Avisos durante a partida ligados. Para ficar só no "antes e depois" (build
no início, silêncio na partida, resumo no fim), use somente_antes_e_depois
no CONFIG.

Regra de ouro deste projeto: ele só usa informação que você JÁ consegue ver
na tela (seu ouro, seus itens, tempo de jogo, placar do Tab). Não lê memória,
não mostra inimigo fora da visão, não cronometra feitiços/ult inimigos e não
cronometra renascimento de objetivos.

Uso:
    python -m pip install requests pyttsx3 vosk sounddevice
    python coach_lol.py                 # com voz e comandos pelo microfone
    python coach_lol.py --sem-voz       # só texto no terminal
    python coach_lol.py --sem-microfone # sem comandos de voz

Comandos de voz: "coach itens", "coach silêncio", "coach volta", "coach anota".

Também faz: ajuda na seleção de campeões (seu histórico por função e notas
sobre o time inimigo), aviso de ouro para o próximo item, CS/min baixo, e,
no fim, resumo falado com aviso de sequência de derrotas e de madrugada.
Para ver a evolução: python relatorio_lol.py

Deixe rodando antes de entrar na fila. Ele espera a partida começar sozinho.
Ao fim de cada partida, salva um resumo em ./partidas/ para revisarmos juntos.
"""

import argparse
import json
import os
import queue
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

import requests
import urllib3

import builds_genericas
import plano
from cliente_lol import FRAGMENTOS, ClienteLoL

# Pasta dos dados (partidas, caches, configuração, modelo de voz). No .exe é a
# pasta do executável; rodando o .py, é a pasta do script.
def _pasta_dados() -> Path:
    """Instalado (.exe): %APPDATA%\\Quiron. Rodando o .py: a pasta do script."""
    if getattr(sys, "frozen", False):
        pasta = Path(os.environ.get("APPDATA", str(Path.home()))) / "Quiron"
        pasta.mkdir(parents=True, exist_ok=True)
        return pasta
    return Path(__file__).parent


BASE = _pasta_dados()

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ---------------------------------------------------------------------------
# CONFIGURAÇÃO — ajuste à vontade
# ---------------------------------------------------------------------------
CONFIG = {
    # MODO "ANTES E DEPOIS" (padrão): fica só no que a Riot cita como aprovado.
    #   - No início: build e ajustes para a composição inimiga (informação
    #     estática da tela de carregamento).
    #   - Durante a partida: NÃO fala nem mostra avisos. Só registra dados
    #     para o resumo (e responde aos seus comandos de voz).
    #   - No fim: resumo falado e salvo em ./partidas/.
    # Mude para False para reativar os avisos durante a partida (zona cinzenta
    # das regras da Riot; use por sua conta).
    "somente_antes_e_depois": False,
    "voz_ligada": True,

    # App (janela): bandeja e inicialização
    "minimizar_para_bandeja": True,
    "iniciar_coach_ao_abrir": False,
    "iniciar_com_windows": False,
    "verificar_atualizacoes": True,
    "builds_automaticas": True,

    "intervalo_leitura_s": 2.0,

    # Ouro acumulado (vivo) que dispara sugestão de voltar à base
    "ouro_para_recall": 1300,
    "intervalo_aviso_ouro_s": 60,

    # Participação em abates (KP): avisa se ficar abaixo disso após X minutos
    "kp_minimo": 0.50,
    "kp_checar_apos_min": 10,
    "intervalo_aviso_kp_s": 240,

    # Sentinela de controle: lembra se você estiver sem uma no inventário
    "lembrar_sentinela_controle": True,
    "intervalo_aviso_sentinela_s": 180,

    # Lembretes por tempo de jogo (minuto -> frase). Confira os tempos do
    # patch atual e edite aqui; são só lembretes de relógio, como olhar o
    # cronômetro do jogo.
    "lembretes_tempo": {
        "4:30": "Primeiro dragão nasce em breve.",
        "13:30": "As placas das torres caem aos 14 minutos.",
        "19:30": "Vinte minutos de jogo.",
    },

    # Frase quando você chega no nível 6, 11 e 16
    "avisar_niveis_ult": True,

    # Analisa a composição inimiga no início e fala os ajustes de build
    "analisar_composicao": True,

    # Avisa quando o caçador inimigo (quem tem Smite) aparece no histórico de
    # abates/objetivos — a mesma informação do canto da tela.
    "avisar_cacador_inimigo": True,
    "intervalo_aviso_cacador_s": 15,

    # Recompensa ("Neutralizado"): estimativa por sequência de abates e por
    # valor dos itens (ambos visíveis no histórico e no Tab).
    "avisar_recompensa": True,
    "sequencia_recompensa": 3,          # abates seguidos sem morrer
    "vantagem_itens_recompensa": 2000,  # ouro em itens acima da média da partida
    "intervalo_aviso_recompensa_s": 90,

    # Ouro para o próximo item da build (o seu ouro e a sua loja)
    "avisar_proximo_item": True,
    "ouro_perto_do_item": 250,

    # CS por minuto abaixo do mínimo da função (suporte não tem aviso)
    "avisar_cs_baixo": True,
    "cs_minimo": {"JUNGLE": 5.5, "TOP": 6.5, "MIDDLE": 6.5, "BOTTOM": 7.0},
    "cs_checar_apos_min": 8,
    "intervalo_aviso_cs_s": 240,

    # Depois da partida: aviso de sequência de derrotas e de jogo de madrugada
    "avisar_sequencia_derrotas": 2,
    "madrugada_entre": (1, 6),   # horas (início, fim)

    # Ajuda na seleção de campeões (API local do cliente do LoL)
    "ajuda_selecao": True,
    "aceitar_fila": True,
    "importar_runas": True,
    "importar_itens": True,
    "importar_feiticos": False,
    "sugerir_escolha": True,     # na sua vez no draft: melhor campeão do seu pool
    "analise_draft": True,       # no fim do draft: pontos positivos e negativos

    # Início da partida: plano de jogo e, se você for o caçador, a rota inicial
    "plano_pre_partida": True,
    "rota_selva": True,

    # Diferença de ouro em itens entre os times (avisa ao mudar de faixa)
    "avisar_diferenca_ouro": True,
    "faixa_diferenca_ouro": 2000,

    # Chat com IA (API do Claude). A chave fica no Gerenciador de Credenciais.
    "modelo_ia": "claude-sonnet-5-5",
    "plano_por_ia": False,       # plano pré-partida também pela IA (custa centavos)
    # Perfil do jogador (preenchido no primeiro uso do app)
    "perfil": {},
    "chave_api_reserva": "",
    "pasta_lol": r"C:\Riot Games\League of Legends",

    # Comandos de voz (reconhecimento offline com Vosk). Diga "coach" + comando:
    #   "coach itens"    -> repete a build e os ajustes contra o time inimigo
    #   "coach silêncio" -> para de falar por alguns minutos
    #   "coach volta"    -> volta a falar
    #   "coach anota"    -> marca o momento para revisar no resumo da partida
    "comandos_de_voz": True,
    "microfone": "",                  # vazio = padrão do Windows
    "microfone_so_na_partida": True,  # fecha o microfone fora da partida
    "minutos_silencio": 3,
}

CONFIG_ARQ = BASE / "config_coach.json"


def migrar_dados_antigos() -> int:
    """Copia partidas e configuração das versões antigas para a pasta atual.

    Origens: %APPDATA%\\CoachLoL (versão "Coach LoL"), a pasta Downloads e a
    pasta do executável. Só copia o que ainda não existe; nada é apagado.
    """
    import shutil
    appdata = Path(os.environ.get("APPDATA", str(Path.home())))
    origens = [appdata / "CoachLoL", Path.home() / "Downloads", Path(sys.executable).parent]
    copiados = 0
    for origem in origens:
        if not origem.is_dir() or origem.resolve() == BASE.resolve():
            continue
        antigas = origem / "partidas"
        if antigas.is_dir():
            (BASE / "partidas").mkdir(exist_ok=True)
            for arq in antigas.glob("*.json"):
                destino = BASE / "partidas" / arq.name
                if not destino.exists():
                    shutil.copy2(arq, destino)
                    copiados += 1
        for nome in ("config_coach.json", "builds_usuario.json"):
            if (origem / nome).exists() and not (BASE / nome).exists():
                shutil.copy2(origem / nome, BASE / nome)
        if (origem / "modelo_voz").is_dir() and not (BASE / "modelo_voz").exists():
            shutil.copytree(origem / "modelo_voz", BASE / "modelo_voz")
    return copiados


def carregar_config():
    """Aplica em CONFIG o que foi salvo pelo app (config_coach.json)."""
    try:
        salvo = json.loads(CONFIG_ARQ.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    for k, v in salvo.items():
        if k in CONFIG:
            CONFIG[k] = tuple(v) if isinstance(CONFIG[k], tuple) else v


def salvar_config(mudancas: dict):
    try:
        salvo = json.loads(CONFIG_ARQ.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        salvo = {}
    salvo.update(mudancas)
    CONFIG.update(mudancas)
    CONFIG_ARQ.write_text(json.dumps(salvo, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Builds: arquivos e atualização
# ---------------------------------------------------------------------------
REPO_GITHUB = "tonetasa/coach-lol"
URL_BUILDS_REMOTAS = f"https://raw.githubusercontent.com/{REPO_GITHUB}/main/builds.json"
ARQ_BUILDS_REMOTAS = BASE / "builds_baixadas.json"
ARQ_BUILDS_USUARIO = BASE / "builds_usuario.json"


def _ler_json(arq: Path) -> dict:
    try:
        return json.loads(arq.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _build_valida(b) -> bool:
    return (isinstance(b, dict) and isinstance(b.get("itens"), list)
            and all(isinstance(i, str) for i in b["itens"])
            and b.get("ajustes", "mago") in TIPOS_AJUSTE)


def _versao_patch(p: str) -> tuple:
    try:
        return tuple(int(x) for x in str(p).split("."))
    except ValueError:
        return (0,)


def carregar_builds():
    """Monta BUILDS: padrão <- baixadas (se patch >= padrão) <- suas edições."""
    base = {k: dict(v) for k, v in BUILDS_PADRAO.items()}
    info = {"patch": PATCH_PADRAO, "fonte": "padrão"}
    remoto = _ler_json(ARQ_BUILDS_REMOTAS)
    if (isinstance(remoto.get("campeoes"), dict)
            and _versao_patch(remoto.get("patch")) >= _versao_patch(PATCH_PADRAO)):
        for cid, b in remoto["campeoes"].items():
            if _build_valida(b):
                base[cid] = b
        info = {"patch": remoto.get("patch"), "fonte": "GitHub",
                "atualizado": remoto.get("atualizado")}
    usuario = _ler_json(ARQ_BUILDS_USUARIO)
    for cid, b in usuario.items():
        if _build_valida(b):
            base[cid] = dict(b, personalizado=True)
    BUILDS.clear()
    for cid, b in base.items():
        BUILDS[cid] = dict(b, ajustes=TIPOS_AJUSTE[b.get("ajustes", "mago")],
                           tipo_ajuste=b.get("ajustes", "mago"))
    INFO_BUILDS.clear()
    INFO_BUILDS.update(info)


def baixar_builds() -> str | None:
    """Baixa builds.json do GitHub. Retorna o patch se mudou, senão None."""
    r = requests.get(URL_BUILDS_REMOTAS, timeout=8)
    r.raise_for_status()
    dados = r.json()
    if not isinstance(dados.get("campeoes"), dict):
        raise ValueError("builds.json sem a chave 'campeoes'")
    antigo = _ler_json(ARQ_BUILDS_REMOTAS)
    ARQ_BUILDS_REMOTAS.write_text(json.dumps(dados, ensure_ascii=False, indent=2),
                                  encoding="utf-8")
    carregar_builds()
    mudou = antigo.get("patch") != dados.get("patch") or antigo.get("campeoes") != dados["campeoes"]
    return dados.get("patch") if mudou else None


def salvar_build_usuario(cid: str, build: dict):
    dados = _ler_json(ARQ_BUILDS_USUARIO)
    atual = BUILDS.get(cid, {})
    dados[cid] = {k: build[k] for k in ("funcao", "runas", "itens", "ajustes", "pagina",
                                        "feiticos") if k in build}
    for k in ("pagina", "feiticos"):  # mantém a página de runas e feitiços que já existiam
        if k not in dados[cid] and k in atual:
            dados[cid][k] = atual[k]
    ARQ_BUILDS_USUARIO.write_text(json.dumps(dados, ensure_ascii=False, indent=2),
                                  encoding="utf-8")
    carregar_builds()


def restaurar_build(cid: str):
    dados = _ler_json(ARQ_BUILDS_USUARIO)
    dados.pop(cid, None)
    ARQ_BUILDS_USUARIO.write_text(json.dumps(dados, ensure_ascii=False, indent=2),
                                  encoding="utf-8")
    carregar_builds()


def exportar_builds_padrao() -> dict:
    """Formato do builds.json publicado no GitHub."""
    return {"patch": PATCH_PADRAO, "atualizado": datetime.now().date().isoformat(),
            "campeoes": BUILDS_PADRAO}


URL_MODELO_VOZ = "https://alphacephei.com/vosk/models/vosk-model-small-pt-0.3.zip"
PASTA_MODELO_VOZ = BASE / "modelo_voz"
FRASES_COMANDO = {
    "coach itens": "build", "coach repete os itens": "build",
    "coach silêncio": "silencio", "coach cala a boca": "silencio",
    "coach volta": "volta", "coach pode falar": "volta",
    "coach anota": "anota", "coach marca": "anota",
}

POSICOES = {"TOP": "no topo", "MIDDLE": "no meio", "BOTTOM": "no bot",
            "UTILITY": "no bot", "JUNGLE": "na selva"}

# ---------------------------------------------------------------------------
# BUILDS — patch 26.21 (atualize junto com o documento "Builds LoL")
# Chave = id do campeão no Data Dragon (ex.: "MonkeyKing" para Wukong).
# Itens em inglês, como no Data Dragon; o coach fala o nome em português.
# "itens" = ordem principal, usada no aviso de ouro para o próximo item.
# ---------------------------------------------------------------------------
# Ajustes por composição: (descrição, [itens opcionais])
AJUSTES_MAGO = {
    "ap": ("muito dano mágico", ["Banshee's Veil"]),
    "ad": ("muito dano físico", ["Zhonya's Hourglass"]),
    "cura": ("muita cura", ["Oblivion Orb", "Morellonomicon"]),
    "tanques": ("dois ou mais tanques", ["Void Staff", "Liandry's Torment"]),
    "cc": ("muito controle de grupo", ["Mercury's Treads"]),
    "assassinos": ("assassino", ["Zhonya's Hourglass"]),
}
AJUSTES_ENCANTADOR = {
    "ap": ("muito dano mágico", ["Mikael's Blessing"]),
    "ad": ("muito dano físico", ["Locket of the Iron Solari"]),
    "cura": ("muita cura", ["Oblivion Orb"]),
    "tanques": ("dois ou mais tanques", ["Shurelya's Battlesong"]),
    "cc": ("muito controle de grupo", ["Mikael's Blessing"]),
    "assassinos": ("assassino", ["Redemption", "Locket of the Iron Solari"]),
}

def pagina(primaria, runas, secundaria, runas2, fragmentos):
    """Página de runas com nomes em inglês (Data Dragon) e fragmentos por apelido."""
    return {"primaria": primaria, "runas": runas, "secundaria": secundaria,
            "runas2": runas2, "fragmentos": fragmentos}


BUILDS_PADRAO = {
    "Fiddlesticks": {"pagina": pagina("Domination", ["Electrocute", "Cheap Shot", "Grisly Mementos", "Ultimate Hunter"], "Sorcery", ["Axiom Arcanist", "Transcendence"], ["adaptativo", "adaptativo", "vida_escalavel"]),
        "feiticos": ["Flash", "Smite"], "funcao": "JUNGLE", "runas": "Eletrocutar",
                     "itens": ["Malignance", "Sorcerer's Shoes", "Liandry's Torment",
                               "Zhonya's Hourglass"],
                     "ajustes": "mago"},
    "Karma": {"pagina": pagina("Sorcery", ["Summon Aery", "Manaflow Band", "Transcendence", "Gathering Storm"], "Resolve", ["Font of Life", "Revitalize"], ["aceleracao", "adaptativo", "vida"]),
        "feiticos": ["Flash", "Heal"], "funcao": "UTILITY", "runas": "Aery",
              "itens": ["Ionian Boots of Lucidity", "Echoes of Helia", "Moonstone Renewer",
                        "Redemption"],
              "ajustes": "encantador"},
    "Lulu": {"pagina": pagina("Sorcery", ["Summon Aery", "Manaflow Band", "Transcendence", "Scorch"], "Resolve", ["Bone Plating", "Revitalize"], ["aceleracao", "adaptativo", "vida_escalavel"]),
        "feiticos": ["Flash", "Heal"], "funcao": "UTILITY", "runas": "Aery",
             "itens": ["Ardent Censer", "Ionian Boots of Lucidity", "Mikael's Blessing",
                       "Moonstone Renewer"],
             "ajustes": "encantador"},
    "Seraphine": {"pagina": pagina("Sorcery", ["Summon Aery", "Manaflow Band", "Transcendence", "Gathering Storm"], "Resolve", ["Font of Life", "Revitalize"], ["aceleracao", "adaptativo", "vida"]),
        "feiticos": ["Flash", "Heal"], "funcao": "UTILITY", "runas": "Aery",
                  "itens": ["Echoes of Helia", "Ionian Boots of Lucidity", "Diadem of Songs",
                            "Moonstone Renewer"],
                  "ajustes": "encantador"},
    "Morgana": {"pagina": pagina("Sorcery", ["Arcane Comet", "Manaflow Band", "Transcendence", "Scorch"], "Domination", ["Cheap Shot", "Ultimate Hunter"], ["adaptativo", "adaptativo", "vida_escalavel"]),
        "feiticos": ["Flash", "Ignite"], "funcao": "UTILITY", "runas": "Cometa Arcano",
                "itens": ["Blackfire Torch", "Ionian Boots of Lucidity", "Zhonya's Hourglass",
                          "Rylai's Crystal Scepter"],
                "ajustes": "mago"},
    "Milio": {"pagina": pagina("Sorcery", ["Summon Aery", "Manaflow Band", "Transcendence", "Scorch"], "Resolve", ["Bone Plating", "Revitalize"], ["aceleracao", "adaptativo", "vida_escalavel"]),
        "feiticos": ["Flash", "Heal"], "funcao": "UTILITY", "runas": "Aery",
              "itens": ["Echoes of Helia", "Ionian Boots of Lucidity", "Moonstone Renewer",
                        "Ardent Censer"],
              "ajustes": "encantador"},
}
PATCH_PADRAO = "26.21"
TIPOS_AJUSTE = {"mago": AJUSTES_MAGO, "encantador": AJUSTES_ENCANTADOR,
                "fisico": builds_genericas.AJUSTES_FISICO,
                "tanque": builds_genericas.AJUSTES_TANQUE}

# Builds em uso: padrão  <-  baixadas do GitHub  <-  editadas por você no app.
# (preenchido por carregar_builds(); "ajustes" já vem como dicionário)
BUILDS: dict = {}
INFO_BUILDS = {"patch": PATCH_PADRAO, "fonte": "padrão"}

# O perfil (Riot ID, elo, funções e pool) vem da tela de primeiro uso do app e
# fica em CONFIG["perfil"]. Histórico de temporada já conhecido de alguém pode
# servir de ponto de partida (somado às partidas que o Quíron registra).
HISTORICO_SEMENTE = {
    "yabbadabbadoo#420": {  # op.gg, 27/10/2026
        "Fiddlesticks": (70, 65), "Karma": (18, 8), "Lulu": (10, 5),
        "Seraphine": (7, 8), "Morgana": (6, 6),
    },
}
# Perfil da versão antiga (antes do primeiro uso existir): preenche o assistente
PERFIL_ANTIGO = {
    "riot_id": "YabbaDabbaDoo#420", "servidor": "BR", "elo": "Esmeralda IV",
    "funcoes": ["JUNGLE", "UTILITY"],
    "pool": {"JUNGLE": ["Fiddlesticks"],
             "UTILITY": ["Karma", "Lulu", "Seraphine", "Morgana", "Milio"]},
}
FUNCOES = ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"]


def perfil() -> dict:
    p = CONFIG.get("perfil") or {}
    return {"riot_id": p.get("riot_id", ""), "servidor": p.get("servidor", "BR"),
            "elo": p.get("elo", ""), "funcoes": list(p.get("funcoes", [])),
            "pool": {f: list(c) for f, c in (p.get("pool") or {}).items()}}


def pool_da_funcao(funcao: str) -> list[str]:
    return perfil()["pool"].get(funcao, [])


def todos_do_pool() -> list[str]:
    vistos = []
    for f in FUNCOES:
        for c in pool_da_funcao(f):
            if c not in vistos:
                vistos.append(c)
    return vistos


def texto_perfil() -> str:
    p = perfil()
    if not p["funcoes"]:
        return "perfil não configurado"
    nomes = {"TOP": "topo", "JUNGLE": "caçador", "MIDDLE": "meio", "BOTTOM": "atirador",
             "UTILITY": "suporte"}
    partes = [f"{nomes[f]} ({', '.join(p['pool'].get(f, [])) or 'sem pool'})"
              for f in p["funcoes"]]
    return (f"{p['elo'] or 'elo não informado'} no servidor {p['servidor']}"
            f"{' (' + p['riot_id'] + ')' if p['riot_id'] else ''}; joga de " + "; ".join(partes))


def obter_build(cid: str, campeoes: dict, funcao: str | None = None) -> dict | None:
    """Build pesquisada (builds.json ou sua edição) ou, se não houver, a genérica."""
    if cid in BUILDS:
        return BUILDS[cid]
    if cid not in campeoes:
        return None
    if not funcao:
        funcao = next((f for f in FUNCOES if cid in pool_da_funcao(f)), None)
    b = builds_genericas.build_generica(cid, campeoes[cid], funcao)
    return dict(b, ajustes=TIPOS_AJUSTE[b["ajustes"]], tipo_ajuste=b["ajustes"])
# Suportes de engajamento (gancho/atordoamento) e campeões que mergulham
ENGAJE = {"Leona", "Nautilus", "Thresh", "Blitzcrank", "Pyke", "Rell", "Alistar",
          "Rakan", "Maokai", "Braum", "Poppy"}
MERGULHO = {"Zed", "Talon", "Khazix", "Rengar", "Evelynn", "Akali", "Katarina",
            "Qiyana", "Diana", "Vi", "Camille", "Irelia", "Fizz", "Kayn", "Nocturne",
            "LeeSin", "Hecarim", "Kassadin", "Naafiri", "Briar", "Yone", "Yasuo"}

# Campeões com cura forte (ids do Data Dragon)
CURA_FORTE = {
    "Soraka", "Aatrox", "Vladimir", "DrMundo", "Warwick", "Sylas", "Yuumi",
    "Sona", "Nami", "Briar", "Fiddlesticks", "Swain", "Illaoi", "Olaf",
    "Volibear", "Kayn", "Nasus", "Trundle", "Senna", "Milio", "Renata",
    "Seraphine", "Zac", "Maokai", "Gwen", "Darius", "Samira",
}
# Campeões com muito controle de grupo (além dos marcados como Tank)
MUITO_CC = {
    "Leona", "Nautilus", "Morgana", "Lissandra", "Thresh", "Rell", "Ashe",
    "Amumu", "Sejuani", "Maokai", "Zac", "Alistar", "Blitzcrank", "Pyke",
    "Rakan", "Lux", "Neeko", "Annie", "Vi", "Skarner", "Poppy", "Taric",
    "Braum", "Malphite", "Ornn", "Zyra", "Twisted Fate", "Veigar",
    "Jarvan IV", "JarvanIV", "Cassiopeia", "Bard", "Rammus", "Nunu",
}

API = "https://127.0.0.1:2999/liveclientdata/allgamedata"
DDRAGON = "https://ddragon.leagueoflegends.com"
PASTA_PARTIDAS = BASE / "partidas"
CACHE_CAMPEOES = BASE / "campeoes_cache.json"
ID_SENTINELA_CONTROLE = 2055


# ---------------------------------------------------------------------------
# Voz
# ---------------------------------------------------------------------------
class Voz:
    """Fala em uma thread separada para não travar a leitura do jogo."""

    def __init__(self, ativa: bool):
        self.mudo_ate = 0.0   # time.time() até quando fica em silêncio
        self.bloqueado = False  # modo "antes e depois": sem avisos durante a partida
        self.fila: "queue.Queue[str]" = queue.Queue()
        self._thread: threading.Thread | None = None
        self.ativa = False
        self.ligar(ativa)

    def ligar(self, ativa: bool):
        """Liga ou desliga a fala (o motor de voz é criado uma vez só)."""
        self.ativa = ativa
        if ativa and self._thread is None:
            self._thread = threading.Thread(target=self._loop, daemon=True)
            self._thread.start()

    def _loop(self):
        import pyttsx3
        motor = pyttsx3.init()
        for v in motor.getProperty("voices"):
            nome = (v.name + " " + v.id).lower()
            if "portug" in nome or "brazil" in nome or "pt-br" in nome or "maria" in nome:
                motor.setProperty("voice", v.id)
                break
        motor.setProperty("rate", 185)
        while True:
            frase = self.fila.get()
            motor.say(frase)
            motor.runAndWait()

    def falar(self, frase: str, tempo_jogo: float | None = None, forcar: bool = False):
        if self.bloqueado and not forcar:
            return  # nem fala nem mostra: nada de informação durante a partida
        prefixo = f"[{fmt_tempo(tempo_jogo)}] " if tempo_jogo is not None else ""
        mudo = time.time() < self.mudo_ate and not forcar
        print(prefixo + ("(mudo) " if mudo else "") + frase, flush=True)
        if self.ativa and not mudo:
            self.fila.put(frase)


# ---------------------------------------------------------------------------
# Comandos de voz (offline, Vosk)
# ---------------------------------------------------------------------------
def listar_microfones() -> list[str]:
    """Nomes dos dispositivos de entrada de áudio (para escolher nas Configurações)."""
    try:
        import sounddevice as sd
        nomes = []
        for d in sd.query_devices():
            if d.get("max_input_channels", 0) > 0 and d["name"] not in nomes:
                nomes.append(d["name"])
        return nomes
    except Exception:  # noqa: BLE001
        return []


class OuvidoComandos:
    """Escuta o microfone e coloca comandos reconhecidos numa fila.

    Usa um vocabulário fechado (só as frases de FRASES_COMANDO), o que deixa
    o reconhecimento rápido e evita disparar com conversa normal.
    """

    def __init__(self):
        self.fila: "queue.Queue[str]" = queue.Queue()
        self.ativo = False
        self.escutar = threading.Event()
        try:
            import sounddevice  # noqa: F401
            import vosk  # noqa: F401
        except ImportError:
            print("(Comandos de voz desligados: rode  python -m pip install vosk sounddevice)")
            return
        if not self._garantir_modelo():
            return
        self.ativo = True
        threading.Thread(target=self._loop, daemon=True).start()

    def _garantir_modelo(self) -> bool:
        if PASTA_MODELO_VOZ.exists() and any(PASTA_MODELO_VOZ.iterdir()):
            return True
        import io
        import urllib.request
        import zipfile
        print("Baixando modelo de voz em português (~30 MB, só na primeira vez)...")
        try:
            with urllib.request.urlopen(URL_MODELO_VOZ, timeout=120) as r:
                dados = r.read()
            with zipfile.ZipFile(io.BytesIO(dados)) as z:
                z.extractall(PASTA_MODELO_VOZ)
            return True
        except Exception as e:  # noqa: BLE001
            print(f"(Não consegui baixar o modelo de voz: {e}. Comandos de voz desligados.)")
            return False

    # O microfone só fica aberto enquanto `escutar` estiver ligado (durante a
    # partida, por padrão). Microfone aberto faz fones Bluetooth trocarem para o
    # modo "telefone" e o Windows abaixar outros sons, piorando música e jogo.
    def ligar_microfone(self, ligar: bool):
        if ligar:
            self.escutar.set()
        else:
            self.escutar.clear()

    def _loop(self):
        import sounddevice as sd
        import vosk
        vosk.SetLogLevel(-1)
        pasta = next(p for p in PASTA_MODELO_VOZ.iterdir() if p.is_dir())
        modelo = vosk.Model(str(pasta))
        gramatica = json.dumps(list(FRASES_COMANDO) + ["[unk]"], ensure_ascii=False)
        audio: "queue.Queue[bytes]" = queue.Queue()

        def callback(indata, frames, tempo, status):
            audio.put(bytes(indata))

        while True:
            self.escutar.wait()
            rec = vosk.KaldiRecognizer(modelo, 16000, gramatica)
            dispositivo = CONFIG.get("microfone") or None
            try:
                with sd.RawInputStream(samplerate=16000, blocksize=8000, dtype="int16",
                                       channels=1, callback=callback, device=dispositivo):
                    print('Microfone ligado. Diga "coach itens", "coach silêncio", '
                          '"coach volta" ou "coach anota".')
                    while self.escutar.is_set():
                        try:
                            bloco = audio.get(timeout=0.5)
                        except queue.Empty:
                            continue
                        if rec.AcceptWaveform(bloco):
                            texto = json.loads(rec.Result()).get("text", "").strip()
                            if texto in FRASES_COMANDO:
                                self.fila.put(FRASES_COMANDO[texto])
                print("Microfone desligado.")
            except Exception as e:  # noqa: BLE001
                print(f"(Erro no microfone: {e}. Comandos de voz desligados.)")
                self.escutar.clear()
                self.ativo = False
                return
            while not audio.empty():
                audio.get_nowait()

    def pegar(self) -> list[str]:
        cmds = []
        while not self.fila.empty():
            cmds.append(self.fila.get())
        return cmds


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------
def fmt_tempo(seg: float | None) -> str:
    if seg is None:
        return "--:--"
    return f"{int(seg // 60):02d}:{int(seg % 60):02d}"


def parse_mmss(txt: str) -> int:
    m, s = txt.split(":")
    return int(m) * 60 + int(s)


def ler_jogo(sessao: requests.Session) -> dict | None:
    try:
        r = sessao.get(API, timeout=1.5, verify=False)
        if r.status_code == 200:
            return r.json()
    except (requests.RequestException, ValueError):
        pass
    return None


VERSAO_CACHE = 3  # aumente quando o formato do cache mudar


def _versao_ddragon() -> str:
    return requests.get(f"{DDRAGON}/api/versions.json", timeout=5).json()[0]


def _com_cache(arquivo: Path, construir) -> dict:
    """Baixa dados do Data Dragon uma vez por patch e guarda em cache local."""
    try:
        versao = _versao_ddragon()
        if arquivo.exists():
            cache = json.loads(arquivo.read_text(encoding="utf-8"))
            if cache.get("versao") == versao and cache.get("formato") == VERSAO_CACHE:
                return cache["dados"]
        dados = construir(versao)
        arquivo.write_text(json.dumps({"versao": versao, "formato": VERSAO_CACHE,
                                       "dados": dados}, ensure_ascii=False), encoding="utf-8")
        return dados
    except (requests.RequestException, ValueError, KeyError, IndexError):
        if arquivo.exists():
            cache = json.loads(arquivo.read_text(encoding="utf-8"))
            if cache.get("formato") == VERSAO_CACHE:
                return cache["dados"]
        return {}


def carregar_campeoes() -> dict:
    """Dados públicos dos campeões (Data Dragon oficial da Riot), com cache local.

    Retorna {id: {"name", "key", "tags", "info"}}. Sem internet nem cache: {}.
    """
    def construir(versao):
        dados = requests.get(
            f"{DDRAGON}/cdn/{versao}/data/pt_BR/champion.json", timeout=15).json()["data"]
        return {k: {"name": v["name"], "key": int(v["key"]), "tags": v["tags"],
                    "info": v["info"]} for k, v in dados.items()}
    return _com_cache(CACHE_CAMPEOES, construir)


CACHE_ITENS = BASE / "itens_cache.json"


def carregar_itens() -> dict:
    """{id(str): {"nome": pt-BR, "en": inglês, "preco": total, "de": [componentes]}}."""
    def construir(versao):
        base = f"{DDRAGON}/cdn/{versao}/data"
        pt = requests.get(f"{base}/pt_BR/item.json", timeout=15).json()["data"]
        en = requests.get(f"{base}/en_US/item.json", timeout=15).json()["data"]
        return {k: {"nome": v["name"], "en": en.get(k, {}).get("name", v["name"]),
                    "preco": v["gold"]["total"], "de": v.get("from", []),
                    # aparece na lista do editor de builds (itens da loja de Summoner's Rift)
                    "loja": bool(v["gold"].get("purchasable") and v.get("maps", {}).get("11")
                                 and len(k) <= 4 and v["gold"]["total"] >= 700)}
                for k, v in pt.items()}
    return _com_cache(CACHE_ITENS, construir)


CACHE_RUNAS = BASE / "runas_cache.json"
FEITICOS = {"Flash": 4, "Smite": 11, "Heal": 7, "Ignite": 14, "Exhaust": 3,
            "Barrier": 21, "Teleport": 12, "Cleanse": 1, "Ghost": 6}


def carregar_runas() -> dict:
    """{"arvores": {inglês: id}, "runas": {inglês: id}, "pt": {id: português}}."""
    def construir(versao):
        base = f"{DDRAGON}/cdn/{versao}/data"
        en = requests.get(f"{base}/en_US/runesReforged.json", timeout=15).json()
        pt = requests.get(f"{base}/pt_BR/runesReforged.json", timeout=15).json()
        dados = {"arvores": {}, "runas": {}, "pt": {}}
        for arvore in en:
            dados["arvores"][arvore["name"]] = arvore["id"]
            for slot in arvore["slots"]:
                for r in slot["runes"]:
                    dados["runas"][r["name"]] = r["id"]
        for arvore in pt:
            dados["pt"][str(arvore["id"])] = arvore["name"]
            for slot in arvore["slots"]:
                for r in slot["runes"]:
                    dados["pt"][str(r["id"])] = r["name"]
        return dados
    return _com_cache(CACHE_RUNAS, construir)


def ids_da_pagina(pagina: dict, runas: dict) -> tuple[int, int, list[int]] | None:
    """Converte a página (nomes em inglês) para os ids que o cliente usa."""
    try:
        prim = runas["arvores"][pagina["primaria"]]
        sec = runas["arvores"][pagina["secundaria"]]
        perks = [runas["runas"][n] for n in pagina["runas"] + pagina["runas2"]]
        perks += [FRAGMENTOS[f] for f in pagina["fragmentos"]]
    except (KeyError, TypeError):
        return None
    return (prim, sec, perks) if len(perks) == 9 else None


class Itens:
    """Consulta de itens: nome em português, preço e quanto falta para comprar."""

    def __init__(self, dados: dict):
        self.dados = dados
        self.por_nome: dict[str, str] = {}
        # prefere o id "normal" (4 dígitos) quando o mesmo nome existe em outros modos
        for k in sorted(dados, key=lambda k: (len(k), k)):
            self.por_nome.setdefault(dados[k]["en"], k)

    def __bool__(self):
        return bool(self.dados)

    def id(self, nome_en: str) -> str | None:
        return self.por_nome.get(nome_en)

    def nomes_loja(self) -> list[str]:
        """Nomes em português dos itens da loja, em ordem alfabética."""
        return sorted({d["nome"] for d in self.dados.values() if d.get("loja")})

    def en_de_pt(self, nome_pt: str) -> str:
        """Nome em inglês (usado nas builds) a partir do nome em português."""
        for k in sorted(self.dados, key=lambda k: (len(k), k)):
            if self.dados[k]["nome"] == nome_pt:
                return self.dados[k]["en"]
        return nome_pt

    def nome_pt(self, nome_en: str) -> str:
        i = self.id(nome_en)
        return self.dados[i]["nome"] if i else nome_en

    def preco(self, item_id) -> int:
        return self.dados.get(str(item_id), {}).get("preco", 0)

    def custo_restante(self, item_id: str, inventario: list) -> int:
        """Preço do item menos o valor dos componentes que você já tem."""
        estoque = [str(i) for i in inventario]

        def valor_possuido(iid: str) -> int:
            total = 0
            for comp in self.dados.get(iid, {}).get("de", []):
                if comp in estoque:
                    estoque.remove(comp)
                    total += self.preco(comp)
                else:
                    total += valor_possuido(comp)
            return total

        return max(self.preco(item_id) - valor_possuido(item_id), 0)


def id_campeao(jogador: dict, campeoes: dict) -> str:
    """Converte o jogador da API ao vivo no id do Data Dragon (ex.: Wukong -> MonkeyKing)."""
    raw = jogador.get("rawChampionName", "")
    if "displayname_" in raw:
        cid = raw.split("displayname_")[-1]
        if cid in campeoes or not campeoes:
            return cid
    nome = jogador.get("championName", "")
    for cid, c in campeoes.items():
        if c["name"] == nome:
            return cid
    return nome.replace(" ", "").replace("'", "").replace(".", "")


def analisar_inimigos(ids: list[str], campeoes: dict) -> list[str]:
    """Retorna as chaves de ajuste que se aplicam ('ap', 'ad', 'cura', ...)."""
    if not campeoes:
        return []
    ap = ad = tanques = assassinos = cc = 0
    cura = False
    for cid in ids:
        c = campeoes.get(cid)
        if not c:
            continue
        tags, info = c["tags"], c["info"]
        if tags[0] != "Support" or info["magic"] >= 8 or info["attack"] >= 8:
            if info["magic"] > info["attack"]:
                ap += 1
            else:
                ad += 1
        if "Tank" in tags:
            tanques += 1
            cc += 1
        elif cid in MUITO_CC or c["name"] in MUITO_CC:
            cc += 1
        if tags[0] == "Assassin":
            assassinos += 1
        if cid in CURA_FORTE:
            cura = True
    ajustes = []
    if ap >= 3:
        ajustes.append("ap")
    if ad >= 3:
        ajustes.append("ad")
    if cura:
        ajustes.append("cura")
    if tanques >= 2:
        ajustes.append("tanques")
    if cc >= 3:
        ajustes.append("cc")
    if assassinos >= 1:
        ajustes.append("assassinos")
    return ajustes


def nomes_possiveis(jogador: dict) -> set[str]:
    """Os eventos usam às vezes o nome curto, às vezes o Riot ID completo."""
    nomes = set()
    for chave in ("riotId", "summonerName", "riotIdGameName"):
        valor = jogador.get(chave)
        if valor:
            nomes.add(valor)
            nomes.add(valor.split("#")[0])
    return nomes


def ler_partidas() -> list[dict]:
    """Todos os resumos salvos em ./partidas/, do mais antigo para o mais novo."""
    partidas = []
    for arq in sorted(PASTA_PARTIDAS.glob("*.json")):
        try:
            partidas.append(json.loads(arq.read_text(encoding="utf-8")))
        except (ValueError, OSError):
            pass
    partidas.sort(key=lambda r: r.get("data", ""))
    return partidas


def avisos_de_sessao(agora: datetime | None = None) -> list[str]:
    """Fatos sobre a sua sessão: sequência de derrotas e jogo de madrugada."""
    agora = agora or datetime.now()
    avisos = []
    hoje = [r for r in ler_partidas()
            if (agora - datetime.fromisoformat(r["data"])).total_seconds() < 12 * 3600]
    derrotas = 0
    for r in reversed(hoje):
        if r.get("resultado") == "derrota":
            derrotas += 1
        else:
            break
    if derrotas >= CONFIG["avisar_sequencia_derrotas"]:
        avisos.append(f"São {derrotas} derrotas seguidas nesta sessão. "
                      "Talvez seja uma boa hora para uma pausa.")
    ini, fim = CONFIG["madrugada_entre"]
    if ini <= agora.hour < fim:
        madrugada = [r for r in ler_partidas() if r.get("resultado")
                     and ini <= datetime.fromisoformat(r["data"]).hour < fim]
        if len(madrugada) >= 5:
            v = sum(r["resultado"] == "vitória" for r in madrugada)
            avisos.append(f"Já passou da {ini} da manhã. De madrugada você venceu "
                          f"{v} de {len(madrugada)} partidas.")
        else:
            avisos.append(f"Já passou da {ini} da manhã. No seu histórico, "
                          "as partidas de madrugada rendem menos.")
    return avisos


# ---------------------------------------------------------------------------
# Coach
# ---------------------------------------------------------------------------
class Coach:
    def __init__(self, voz: Voz, campeoes: dict | None = None, itens: "Itens | None" = None):
        self.voz = voz
        self.campeoes = campeoes or {}
        self.itens = itens or Itens({})
        self.reset()

    def reset(self):
        self.voz.bloqueado = False
        self.em_partida = False
        self.eu = None            # dados do meu campeão em allPlayers
        self.meu_time = None
        self.meus_nomes: set[str] = set()
        self.eventos_vistos = 0
        self.ultimo_aviso: dict[str, float] = {}
        self.lembretes_feitos: set[str] = set()
        self.nivel_anterior = 0
        self.mortes: list[dict] = []
        self.historico_kp: list[tuple[float, float]] = []
        self.ultimo_jogo: dict | None = None
        self.dica_build: str | None = None   # repetida no primeiro aviso de ouro
        self.dica_build_repetida = False
        self.cacadores_inimigos: dict[str, dict] = {}  # nome -> jogador
        self.anotacoes: list[str] = []                 # tempos marcados com "coach anota"
        self.texto_build: str | None = None            # build + ajustes, para "coach build"
        self.sequencias: dict[str, int] = {}           # campeão -> abates seguidos
        self.ja_avisou_recompensa: set[str] = set()    # campeões já avisados (zera ao morrer)
        self.build: dict | None = None                 # build do meu campeão
        self.avisos_item: set[str] = set()             # "perto_<id>" / "pronto_<id>" já falados
        self.resultado: str | None = None              # "Win" / "Lose" (evento GameEnd)
        self.diferenca_ouro = 0                        # meu time - inimigo (itens)
        self.faixa_ouro = 0
        self.plano_texto: list[str] = []

    # -- helpers -----------------------------------------------------------
    def pode_avisar(self, chave: str, intervalo: float, agora: float) -> bool:
        if agora - self.ultimo_aviso.get(chave, -1e9) >= intervalo:
            self.ultimo_aviso[chave] = agora
            return True
        return False

    def identificar_jogador(self, jogo: dict):
        ativo = jogo.get("activePlayer", {})
        nomes_ativo = nomes_possiveis(ativo)
        for p in jogo.get("allPlayers", []):
            if nomes_possiveis(p) & nomes_ativo:
                self.eu = p
                self.meu_time = p.get("team")
                self.meus_nomes = nomes_possiveis(p) | nomes_ativo
                return

    # -- início ------------------------------------------------------------
    def inicio_partida(self, jogo: dict):
        self.em_partida = True
        self.identificar_jogador(jogo)
        if not self.eu:
            self.voz.falar("Partida detectada, mas não identifiquei seu campeão.")
            return
        aliados = [p["championName"] for p in jogo["allPlayers"] if p.get("team") == self.meu_time]
        inimigos = [p["championName"] for p in jogo["allPlayers"] if p.get("team") != self.meu_time]
        print("\n=== Partida iniciada ===")
        print("Seu time :", ", ".join(aliados))
        print("Inimigos :", ", ".join(inimigos))
        self.voz.falar(f"Partida começando. Você está de {self.eu['championName']}. Boa sorte.")
        self.identificar_cacadores(jogo)
        if CONFIG["analisar_composicao"]:
            self.falar_build(jogo)
        self.falar_plano(jogo)
        if CONFIG["somente_antes_e_depois"]:
            self.voz.bloqueado = True
            print("(Modo antes e depois: sem avisos durante a partida. "
                  "Resumo no final.)")

    def identificar_cacadores(self, jogo: dict):
        """Caçador inimigo = quem tem Smite (visível no placar/Tab)."""
        for p in jogo.get("allPlayers", []):
            if p.get("team") == self.meu_time:
                continue
            feiticos = p.get("summonerSpells", {})
            for f in feiticos.values():
                raw = (f.get("rawDisplayName", "") + " " + f.get("displayName", "")).lower()
                if "smite" in raw or "golpear" in raw:
                    for nome in nomes_possiveis(p):
                        self.cacadores_inimigos[nome] = p
                    print(f"Caçador inimigo: {p['championName']}")
                    break

    def jogador_por_nome(self, nome: str) -> dict | None:
        for p in (self.ultimo_jogo or {}).get("allPlayers", []):
            if nome in nomes_possiveis(p):
                return p
        return None

    def checar_cacador(self, ev: dict, t: float):
        if not CONFIG["avisar_cacador_inimigo"] or not self.cacadores_inimigos:
            return
        # ignora eventos antigos (ex.: script aberto no meio da partida)
        if t - ev.get("EventTime", t) > 10:
            return
        envolvidos = [ev.get("KillerName", "")] + list(ev.get("Assisters", []))
        cacador = next((self.cacadores_inimigos[n] for n in envolvidos
                        if n in self.cacadores_inimigos), None)
        if not cacador:
            return
        nome_ev = ev.get("EventName")
        campeao = cacador["championName"]
        if nome_ev == "ChampionKill":
            vitima = self.jogador_por_nome(ev.get("VictimName", ""))
            if vitima is None:
                return
            lugar = POSICOES.get(vitima.get("position", ""), "")
            frase = f"{campeao}, caçador inimigo, apareceu {lugar} no abate de {vitima['championName']}."
        elif nome_ev == "DragonKill":
            frase = f"{campeao}, caçador inimigo, está no dragão. Lado de baixo do mapa."
        elif nome_ev in ("HeraldKill", "HordeKill", "BaronKill"):
            frase = f"{campeao}, caçador inimigo, está no lado de cima do mapa."
        elif nome_ev == "TurretKilled":
            frase = f"{campeao}, caçador inimigo, ajudou a derrubar uma torre."
        else:
            return
        if self.pode_avisar("cacador", CONFIG["intervalo_aviso_cacador_s"], t):
            self.voz.falar(" ".join(frase.split()), t)

    # -- recompensa / "Neutralizado" ---------------------------------------
    def atualizar_sequencias(self, ev: dict):
        if ev.get("EventName") != "ChampionKill":
            return
        matador = self.jogador_por_nome(ev.get("KillerName", ""))
        vitima = self.jogador_por_nome(ev.get("VictimName", ""))
        if vitima:
            campeao = vitima["championName"]
            if campeao in self.ja_avisou_recompensa and vitima.get("team") != self.meu_time:
                self.voz.falar(f"Neutralizado! {campeao} perdeu a recompensa.")
            self.sequencias[campeao] = 0
            self.ja_avisou_recompensa.discard(campeao)
        if matador:
            c = matador["championName"]
            self.sequencias[c] = self.sequencias.get(c, 0) + 1

    def valor_itens(self, jogador: dict) -> int:
        return sum(self.itens.preco(i.get("itemID")) * max(i.get("count", 1), 1)
                   for i in jogador.get("items", []))

    def checar_recompensa(self, jogo: dict, t: float):
        if not CONFIG["avisar_recompensa"]:
            return
        jogadores = jogo.get("allPlayers", [])
        media = (sum(self.valor_itens(p) for p in jogadores) / len(jogadores)
                 if self.itens and jogadores else 0)
        for p in jogadores:
            campeao = p["championName"]
            if campeao in self.ja_avisou_recompensa:
                continue
            seq = self.sequencias.get(campeao, 0)
            vantagem = self.valor_itens(p) - media if media else 0
            motivo = None
            if seq >= CONFIG["sequencia_recompensa"]:
                motivo = f"está com {seq} abates seguidos"
            elif vantagem >= CONFIG["vantagem_itens_recompensa"]:
                motivo = f"tem uns {round(vantagem, -2):.0f} de ouro em itens acima da média"
            if not motivo:
                continue
            if not self.pode_avisar(f"recompensa_{campeao}",
                                    CONFIG["intervalo_aviso_recompensa_s"], t):
                continue
            self.ja_avisou_recompensa.add(campeao)
            if p is self.eu or nomes_possiveis(p) & self.meus_nomes:
                self.voz.falar(f"Você {motivo}. Provavelmente está valendo recompensa.", t)
            elif p.get("team") != self.meu_time:
                self.voz.falar(f"{campeao} {motivo}. Provavelmente está valendo recompensa.", t)

    def texto_ajuste(self, chave: str, build: dict) -> str | None:
        if chave not in build["ajustes"]:
            return None
        desc, itens = build["ajustes"][chave]
        nomes = [self.itens.nome_pt(i) for i in itens]
        if not nomes:
            return f"Time inimigo com {desc}."
        rotulo = "Opção" if len(nomes) == 1 else "Opções"
        return f"Time inimigo com {desc}. {rotulo}: {' e '.join(nomes)}."

    def falar_build(self, jogo: dict):
        meu_id = id_campeao(self.eu, self.campeoes)
        build = obter_build(meu_id, self.campeoes, self.eu.get("position") or None)
        if not build:
            print(f"(Sem build cadastrada para {meu_id}. Adicione na aba Builds do app.)")
            return
        self.build = build
        lista = ", ".join(self.itens.nome_pt(i) for i in build["itens"])
        rotulo = "Build genérica" if build.get("generica") else "Build"
        self.voz.falar(f"{rotulo}: {lista}.")
        ids_inimigos = [id_campeao(p, self.campeoes) for p in jogo["allPlayers"]
                        if p.get("team") != self.meu_time]
        ajustes = [txt for k in analisar_inimigos(ids_inimigos, self.campeoes)
                   if (txt := self.texto_ajuste(k, build))]
        if not self.campeoes:
            print("(Sem dados de campeões: análise da composição inimiga desativada.)")
        for frase in ajustes:
            self.voz.falar(frase)
        if ajustes:
            self.dica_build = " ".join(ajustes)
        self.texto_build = " ".join([f"{rotulo}: {lista}."] + ajustes)

    # -- plano de jogo e rota da selva ---------------------------------------
    def falar_plano(self, jogo: dict):
        nomes = lambda cid: self.campeoes.get(cid, {}).get("name", cid)  # noqa: E731
        frases = []
        if CONFIG["plano_pre_partida"]:
            frases = plano.montar_plano(jogo, self.eu, self.meu_time, self.campeoes,
                                        id_campeao, ENGAJE, MUITO_CC, MERGULHO, nomes)
        sou_cacador = (self.eu.get("position") == "JUNGLE"
                       or (self.build or {}).get("funcao") == "JUNGLE"
                       or any("smite" in (f.get("rawDisplayName", "") + f.get("displayName", ""))
                              .lower() or "golpear" in f.get("displayName", "").lower()
                              for f in self.eu.get("summonerSpells", {}).values()))
        if CONFIG["rota_selva"] and sou_cacador:
            frases.append(plano.rota_selva(jogo, self.meu_time, self.campeoes, id_campeao,
                                           ENGAJE, MUITO_CC, nomes))
        self.plano_texto = frases
        for f in frases:
            self.voz.falar(f)
        if CONFIG["plano_por_ia"]:
            threading.Thread(target=self._plano_ia, args=(jogo,), daemon=True).start()

    def _plano_ia(self, jogo: dict):
        import ia_chat  # importado aqui para evitar import circular
        chave = ia_chat.obter_chave()
        if not chave:
            return
        resumo = {"meu_time": [(p["championName"], p.get("position")) for p in jogo["allPlayers"]
                               if p.get("team") == self.meu_time],
                  "inimigos": [(p["championName"], p.get("position")) for p in jogo["allPlayers"]
                               if p.get("team") != self.meu_time],
                  "eu": (self.eu["championName"], self.eu.get("position"))}
        try:
            texto = ia_chat.plano_por_ia(resumo, chave, CONFIG["modelo_ia"])
            if texto:
                self.plano_texto.append(texto)
                self.voz.falar("Plano da IA: " + texto, forcar=True)
        except Exception as e:  # noqa: BLE001
            print(f"(Plano da IA indisponível: {e})")

    # -- diferença de ouro entre os times ----------------------------------
    def checar_diferenca_ouro(self, jogo: dict, t: float):
        if not self.itens:
            return
        meu = sum(self.valor_itens(p) for p in jogo["allPlayers"] if p.get("team") == self.meu_time)
        deles = sum(self.valor_itens(p) for p in jogo["allPlayers"] if p.get("team") != self.meu_time)
        self.diferenca_ouro = meu - deles
        if not CONFIG["avisar_diferenca_ouro"] or t < 5 * 60:
            return
        passo = CONFIG["faixa_diferenca_ouro"]
        faixa = int(self.diferenca_ouro / passo)  # trunca em direção ao zero
        if faixa != self.faixa_ouro and self.pode_avisar("ouro_times", 120, t):
            self.faixa_ouro = faixa
            valor = abs(round(self.diferenca_ouro, -2))
            if faixa == 0:
                self.voz.falar("Ouro em itens equilibrado entre os times.", t)
            else:
                lado = "à frente" if faixa > 0 else "atrás"
                self.voz.falar(f"Seu time está cerca de {valor:.0f} de ouro {lado} em itens.", t)

    # -- ouro para o próximo item ------------------------------------------
    def checar_proximo_item(self, ativo: dict, t: float):
        if not CONFIG["avisar_proximo_item"] or not self.build or not self.itens:
            return
        if self.eu.get("isDead"):
            return
        inventario = [i.get("itemID") for i in self.eu.get("items", [])]
        possuidos = {str(i) for i in inventario}
        proximo = None
        for nome in self.build["itens"]:
            iid = self.itens.id(nome)
            if iid and iid not in possuidos:
                proximo = (nome, iid)
                break
        if not proximo:
            return
        nome, iid = proximo
        falta = self.itens.custo_restante(iid, inventario) - ativo.get("currentGold", 0)
        nome_pt = self.itens.nome_pt(nome)
        if falta <= 0 and f"pronto_{iid}" not in self.avisos_item:
            self.avisos_item.add(f"pronto_{iid}")
            self.avisos_item.add(f"perto_{iid}")
            self.voz.falar(f"Ouro suficiente para {nome_pt}.", t)
            if self.dica_build and not self.dica_build_repetida:
                self.dica_build_repetida = True
                self.voz.falar("Sobre os itens: " + self.dica_build, t)
        elif 0 < falta <= CONFIG["ouro_perto_do_item"] and f"perto_{iid}" not in self.avisos_item:
            self.avisos_item.add(f"perto_{iid}")
            self.voz.falar(f"Faltam {int(round(falta, -1))} de ouro para {nome_pt}.", t)

    # -- CS por minuto -----------------------------------------------------
    def checar_cs(self, t: float):
        if not CONFIG["avisar_cs_baixo"] or not self.build:
            return
        funcao = self.build.get("funcao")
        minimo = CONFIG["cs_minimo"].get(funcao)
        if not minimo or t < CONFIG["cs_checar_apos_min"] * 60:
            return
        cs_min = self.eu["scores"].get("creepScore", 0) / (t / 60)
        if cs_min < minimo and self.pode_avisar("cs", CONFIG["intervalo_aviso_cs_s"], t):
            self.voz.falar(f"Seu CS por minuto está em {cs_min:.1f}.".replace(".", ",", 1), t)

    # -- comandos de voz ---------------------------------------------------
    def executar_comando(self, cmd: str):
        t = (self.ultimo_jogo or {}).get("gameData", {}).get("gameTime")
        if cmd == "build":
            self.voz.falar(self.texto_build or "Não tenho build cadastrada para esse campeão.",
                           t, forcar=True)
        elif cmd == "silencio":
            minutos = CONFIG["minutos_silencio"]
            self.voz.falar(f"Ok, silêncio por {minutos} minutos.", t, forcar=True)
            self.voz.mudo_ate = time.time() + minutos * 60
        elif cmd == "volta":
            self.voz.mudo_ate = 0
            self.voz.falar("Voltei.", t)
        elif cmd == "anota":
            if not self.em_partida or t is None:
                return
            self.anotacoes.append(fmt_tempo(t))
            self.voz.falar("Anotado.", t, forcar=True)

    # -- loop principal ----------------------------------------------------
    def processar(self, jogo: dict):
        if not self.em_partida:
            self.inicio_partida(jogo)

        self.ultimo_jogo = jogo
        t = jogo.get("gameData", {}).get("gameTime", 0.0)
        ativo = jogo.get("activePlayer", {})

        # atualiza meu registro em allPlayers
        for p in jogo.get("allPlayers", []):
            if nomes_possiveis(p) & self.meus_nomes:
                self.eu = p
        if not self.eu:
            return

        self.checar_eventos(jogo, t)
        self.checar_ouro(ativo, t)
        self.checar_kp(jogo, t)
        self.checar_sentinela(t)
        self.checar_lembretes_tempo(t)
        self.checar_nivel(ativo, t)
        self.checar_recompensa(jogo, t)
        self.checar_proximo_item(ativo, t)
        self.checar_diferenca_ouro(jogo, t)
        self.checar_cs(t)

    def checar_eventos(self, jogo: dict, t: float):
        eventos = jogo.get("events", {}).get("Events", [])
        novos = eventos[self.eventos_vistos:]
        self.eventos_vistos = len(eventos)
        for ev in novos:
            self.checar_cacador(ev, t)
            self.atualizar_sequencias(ev)
            nome = ev.get("EventName")
            if nome == "ChampionKill" and ev.get("VictimName") in self.meus_nomes:
                tempo = ev.get("EventTime", t)
                self.mortes.append({"tempo": fmt_tempo(tempo), "matador": ev.get("KillerName")})
                if tempo < 14 * 60:
                    self.voz.falar(
                        "Morte antes dos 14 minutos. Ficou anotada no resumo.", t)
                else:
                    self.voz.falar("Você morreu.", t)
            elif nome == "GameEnd":
                self.voz.bloqueado = False
                self.resultado = ev.get("Result")

    def checar_ouro(self, ativo: dict, t: float):
        ouro = ativo.get("currentGold", 0)
        # com build cadastrada, o aviso de "próximo item" substitui este
        if self.build and CONFIG["avisar_proximo_item"] and self.itens:
            return
        if (ouro >= CONFIG["ouro_para_recall"] and not self.eu.get("isDead")
                and self.pode_avisar("ouro", CONFIG["intervalo_aviso_ouro_s"], t)):
            self.voz.falar(f"Você tem {int(ouro)} de ouro.", t)
            if self.dica_build and not self.dica_build_repetida:
                self.dica_build_repetida = True
                self.voz.falar("Sobre os itens: " + self.dica_build, t)

    def checar_kp(self, jogo: dict, t: float):
        if t < CONFIG["kp_checar_apos_min"] * 60:
            return
        abates_time = sum(p["scores"]["kills"] for p in jogo["allPlayers"]
                          if p.get("team") == self.meu_time)
        if abates_time < 3:
            return
        s = self.eu["scores"]
        kp = (s["kills"] + s["assists"]) / abates_time
        self.historico_kp.append((t, kp))
        if kp < CONFIG["kp_minimo"] and self.pode_avisar("kp", CONFIG["intervalo_aviso_kp_s"], t):
            self.voz.falar(
                f"Sua participação em abates está em {round(kp * 100)} por cento.", t)

    def checar_sentinela(self, t: float):
        if not CONFIG["lembrar_sentinela_controle"] or t < 3 * 60:
            return
        tem = any(i.get("itemID") == ID_SENTINELA_CONTROLE for i in self.eu.get("items", []))
        if not tem and self.pode_avisar("sentinela", CONFIG["intervalo_aviso_sentinela_s"], t):
            self.voz.falar("Você está sem sentinela de controle.", t)

    def checar_lembretes_tempo(self, t: float):
        for mmss, frase in CONFIG["lembretes_tempo"].items():
            alvo = parse_mmss(mmss)
            if mmss not in self.lembretes_feitos and alvo <= t < alvo + 10:
                self.lembretes_feitos.add(mmss)
                self.voz.falar(frase, t)

    def checar_nivel(self, ativo: dict, t: float):
        nivel = ativo.get("level", 0)
        if CONFIG["avisar_niveis_ult"] and nivel != self.nivel_anterior:
            if nivel == 6:
                self.voz.falar("Nível 6. Ultimate disponível.", t)
            elif nivel in (11, 16):
                self.voz.falar(f"Nível {nivel}. Ultimate mais forte.", t)
        self.nivel_anterior = nivel

    # -- fim ---------------------------------------------------------------
    def fim_partida(self):
        if not self.em_partida or not self.ultimo_jogo or not self.eu:
            self.reset()
            return
        jogo = self.ultimo_jogo
        s = self.eu["scores"]
        dur = jogo.get("gameData", {}).get("gameTime", 0)
        resumo = {
            "data": datetime.now().isoformat(timespec="seconds"),
            "resultado": {"Win": "vitória", "Lose": "derrota"}.get(self.resultado or ""),
            "campeao": self.eu.get("championName"),
            "campeao_id": id_campeao(self.eu, self.campeoes),
            "posicao": self.eu.get("position"),
            "duracao": fmt_tempo(dur),
            "kda": f'{s["kills"]}/{s["deaths"]}/{s["assists"]}',
            "cs": s.get("creepScore"),
            "cs_por_min": round(s.get("creepScore", 0) / max(dur / 60, 1), 1),
            "placar_visao": round(s.get("wardScore", 0), 1),
            "kp_final": (round((s["kills"] + s["assists"]) / tot, 2)
                         if (tot := sum(p["scores"]["kills"] for p in jogo["allPlayers"]
                                        if p.get("team") == self.meu_time)) else None),
            "mortes": self.mortes,
            "mortes_antes_14": sum(1 for m in self.mortes if parse_mmss(m["tempo"]) < 14 * 60),
            "momentos_anotados": self.anotacoes,
            "aliados": [p["championName"] for p in jogo["allPlayers"] if p.get("team") == self.meu_time],
            "inimigos": [p["championName"] for p in jogo["allPlayers"] if p.get("team") != self.meu_time],
        }
        PASTA_PARTIDAS.mkdir(exist_ok=True)
        arq = PASTA_PARTIDAS / f"{datetime.now():%Y%m%d_%H%M%S}_{resumo['campeao']}.json"
        arq.write_text(json.dumps(resumo, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n=== Partida encerrada. Resumo salvo em {arq} ===")
        self.falar_resumo(resumo, jogo)
        self.reset()

    def falar_resumo(self, resumo: dict, jogo: dict):
        """Resumo pós-partida: só as suas próprias estatísticas."""
        self.voz.bloqueado = False
        abates_time = sum(p["scores"]["kills"] for p in jogo["allPlayers"]
                          if p.get("team") == self.meu_time)
        s = self.eu["scores"]
        kp = min(100, round((s["kills"] + s["assists"]) / abates_time * 100)) if abates_time else None
        partes = [f"Resumo da partida de {resumo['campeao']}. KDA {resumo['kda'].replace('/', ', ')}."]
        if kp is not None:
            partes.append(f"Participação em abates: {kp} por cento.")
        partes.append(f"{resumo['mortes_antes_14']} mortes antes dos 14 minutos.")
        partes.append(f"Placar de visão {resumo['placar_visao']:.0f}.")
        if resumo["momentos_anotados"]:
            partes.append("Momentos anotados: " + ", ".join(resumo["momentos_anotados"]) + ".")
        partes += avisos_de_sessao()
        for frase in partes:
            self.voz.falar(frase)
        print()


# ---------------------------------------------------------------------------
# Seleção de campeões (API local do cliente — LCU)
# ---------------------------------------------------------------------------
NOMES_FUNCAO = {"UTILITY": "suporte", "JUNGLE": "caçador", "TOP": "topo",
                "MIDDLE": "meio", "BOTTOM": "atirador"}


def estatisticas_pool() -> dict[str, tuple[int, int]]:
    """Vitórias e derrotas por campeão do pool: histórico inicial + partidas registradas."""
    semente = HISTORICO_SEMENTE.get(perfil()["riot_id"].strip().lower(), {})
    stats = {c: list(semente.get(c, (0, 0))) for c in todos_do_pool()}
    for c, vd in semente.items():
        stats.setdefault(c, list(vd))
    for r in ler_partidas():
        c = r.get("campeao_id") or r.get("campeao")
        if r.get("resultado"):
            stats.setdefault(c, [0, 0])
            stats[c][0 if r["resultado"] == "vitória" else 1] += 1
    return {c: (v, d) for c, (v, d) in stats.items()}


class SelecaoCampeoes:
    """Lê a seleção de campeões: destaca o seu pool e importa runas e itens.

    Usa a API local do cliente (a mesma do lobby). A Riot diz que essa API não
    tem suporte oficial para apps de terceiros: funciona, mas pode mudar.
    """

    def __init__(self, voz: Voz, campeoes: dict, cliente: ClienteLoL | None = None,
                 itens: "Itens | None" = None, runas: dict | None = None):
        self.voz = voz
        self.por_chave = {c["key"]: cid for cid, c in campeoes.items() if "key" in c}
        self.nomes = {cid: c["name"] for cid, c in campeoes.items()}
        self.campeoes = campeoes
        self.cliente = cliente or ClienteLoL(CONFIG["pasta_lol"])
        self.itens = itens or Itens({})
        self.runas = runas or {}
        self.reset()

    def reset(self):
        self.ativa = False
        self.inimigos_vistos: set[str] = set()
        self.notas_faladas: set[str] = set()
        self.importado: str | None = None
        self.vez_anunciada = None        # id da ação de escolha já comentada
        self.draft_analisado = False
        self.analise: dict | None = None  # última análise (para o app mostrar)

    def ler(self) -> dict | None:
        self.cliente.pasta = Path(CONFIG["pasta_lol"])
        return self.cliente.get("/lol-champ-select/v1/session")

    # -- importação -----------------------------------------------------------
    def importar(self, cid: str, eu: dict):
        funcao = (eu.get("assignedPosition") or "").upper() or None
        build = obter_build(cid, self.campeoes, funcao)
        nome = self.nomes.get(cid, cid)
        if not build:
            print(f"(Sem build cadastrada para {nome}: nada importado.)")
            return
        feitos = []
        if CONFIG["importar_runas"] and build.get("pagina") and self.runas:
            ids = ids_da_pagina(build["pagina"], self.runas)
            if ids:
                res = self.cliente.importar_runas(*ids, nome=f"Quíron - {nome}")
                if res.startswith("ok"):
                    feitos.append("runas")
                else:
                    print(f"(Runas não importadas: {res}. Apague uma página no cliente.)")
        if CONFIG["importar_itens"] and self.itens:
            principal = [i for i in (self.itens.id(n) for n in build["itens"]) if i]
            extras = []
            for _, nomes in build["ajustes"].values():
                for n in nomes:
                    iid = self.itens.id(n)
                    if iid and iid not in principal and iid not in extras:
                        extras.append(iid)
            chave = self.campeoes.get(cid, {}).get("key")
            if chave and self.cliente.importar_itens(
                    chave, nome, [("Build principal (Quíron)", principal),
                                  ("Opções contra o time inimigo", extras),
                                  ("Visão", ["2055"])]):
                feitos.append("itens")
        if CONFIG["importar_feiticos"] and build.get("feiticos"):
            if self.trocar_feiticos(build["feiticos"], eu):
                feitos.append("feitiços")
        if feitos:
            self.voz.falar(f"{', '.join(feitos).capitalize()} de {nome} importados.")

    def trocar_feiticos(self, nomes: list[str], eu: dict) -> bool:
        ids = [FEITICOS[n] for n in nomes if n in FEITICOS][:2]
        if len(ids) != 2:
            return False
        # mantém o Flash na tecla em que você já costuma usar
        if 4 in ids and eu.get("spell2Id") == 4:
            ids = [i for i in ids if i != 4] + [4]
        elif 4 in ids:
            ids = [4] + [i for i in ids if i != 4]
        r = self.cliente.pedir("PATCH", "/lol-champ-select/v1/session/my-selection",
                               json={"spell1Id": ids[0], "spell2Id": ids[1]})
        return r is not None and r.status_code in (200, 204)

    def processar(self, sessao: dict | None):
        if not sessao:
            if self.ativa:
                self.reset()
            return
        eu = next((p for p in sessao.get("myTeam", [])
                   if p.get("cellId") == sessao.get("localPlayerCellId")), None)
        if not eu:
            return
        funcao = (eu.get("assignedPosition") or "").upper()
        if not self.ativa:
            self.ativa = True
            if CONFIG["ajuda_selecao"]:
                self.falar_pool(funcao)
        meu = self.por_chave.get(eu.get("championId"))
        if meu and meu != self.importado:
            self.importado = meu
            self.importar(meu, eu)
        inimigos = {self.por_chave.get(p.get("championId"))
                    for p in sessao.get("theirTeam", []) if p.get("championId")}
        inimigos.discard(None)
        if inimigos - self.inimigos_vistos:
            self.inimigos_vistos |= inimigos
            if CONFIG["ajuda_selecao"]:
                self.falar_notas(funcao)
        self.checar_vez(sessao, eu, funcao)
        self.checar_fim_do_draft(sessao, eu)

    # -- draft ----------------------------------------------------------------
    def _times(self, sessao: dict, eu: dict) -> tuple[list[str], list[str]]:
        aliados = [self.por_chave.get(p.get("championId")) for p in sessao.get("myTeam", [])
                   if p.get("championId") and p is not eu]
        inimigos = [self.por_chave.get(p.get("championId"))
                    for p in sessao.get("theirTeam", []) if p.get("championId")]
        return [c for c in aliados if c], [c for c in inimigos if c]

    def checar_vez(self, sessao: dict, eu: dict, funcao: str):
        if not CONFIG["sugerir_escolha"]:
            return
        local = sessao.get("localPlayerCellId")
        acoes = [a for grupo in sessao.get("actions", []) for a in grupo]
        minha = next((a for a in acoes if a.get("actorCellId") == local and a.get("type") == "pick"
                      and a.get("isInProgress") and not a.get("completed")), None)
        if not minha or minha.get("id") == self.vez_anunciada:
            return
        self.vez_anunciada = minha.get("id")
        pool = pool_da_funcao(funcao)
        if not pool:
            return
        aliados, inimigos = self._times(sessao, eu)
        banidos = {self.por_chave.get(a.get("championId")) for a in acoes
                   if a.get("type") == "ban" and a.get("completed")}
        nomes = lambda c: self.nomes.get(c, c)  # noqa: E731
        ranking = plano.sugerir_escolha(pool, aliados, inimigos, banidos, estatisticas_pool(),
                                        self.campeoes, ENGAJE, MUITO_CC, MERGULHO, nomes)
        if not ranking:
            self.voz.falar("Sua vez de escolher. Nenhum campeão do seu pool está disponível.")
            return
        melhor, _, motivos = ranking[0]
        frase = f"Sua vez de escolher. Melhor opção: {nomes(melhor)}"
        frase += (": " + "; ".join(motivos[:2]) + ".") if motivos else "."
        if len(ranking) > 1:
            frase += f" Alternativa: {nomes(ranking[1][0])}."
        self.voz.falar(frase)

    def checar_fim_do_draft(self, sessao: dict, eu: dict):
        if not CONFIG["analise_draft"] or self.draft_analisado:
            return
        fase = (sessao.get("timer") or {}).get("phase")
        if fase != "FINALIZATION":
            return
        self.draft_analisado = True
        aliados, inimigos = self._times(sessao, eu)
        meu = self.por_chave.get(eu.get("championId"))
        if meu:
            aliados.append(meu)
        if len(aliados) < 3 or len(inimigos) < 3:
            return
        nomes = lambda c: self.nomes.get(c, c)  # noqa: E731
        bons, ruins = plano.analisar_draft(aliados, inimigos, self.campeoes, ENGAJE, MUITO_CC,
                                           MERGULHO, nomes)
        self.analise = {"positivos": bons, "negativos": ruins}
        self.voz.falar("Draft fechado. Pontos positivos: " + " ".join(bons[:2]))
        self.voz.falar("Pontos de atenção: " + " ".join(ruins[:2]))
        for extra in bons[2:] + ruins[2:]:
            print("  • " + extra)

    def falar_pool(self, funcao: str):
        pool = pool_da_funcao(funcao)
        if not pool:
            self.voz.falar("Seleção de campeões.")
            return
        stats = estatisticas_pool()
        linhas = []
        for c in sorted(pool, key=lambda c: -self._taxa(stats.get(c, (0, 0)))):
            v, d = stats.get(c, (0, 0))
            if v + d >= 5:
                linhas.append(f"{self.nomes.get(c, c)} {round(100 * v / (v + d))} por cento "
                              f"em {v + d} partidas")
        frase = f"Seleção de campeões, você está de {NOMES_FUNCAO.get(funcao, funcao)}."
        if linhas:
            frase += " Seu histórico: " + "; ".join(linhas[:3]) + "."
        self.voz.falar(frase)

    @staticmethod
    def _taxa(vd: tuple[int, int]) -> float:
        v, d = vd
        return (v + 1) / (v + d + 2)  # suaviza amostras pequenas

    def falar_notas(self, funcao: str):
        pool = pool_da_funcao(funcao)
        notas = []
        engaje = sorted(self.inimigos_vistos & ENGAJE)
        resposta = [c for c in ("Morgana", "Milio") if c in pool]
        if engaje and resposta and "engaje" not in self.notas_faladas:
            self.notas_faladas.add("engaje")
            nomes = " e ".join(self.nomes.get(c, c) for c in engaje)
            notas.append(f"Inimigo com engajamento: {nomes}. No seu pool, "
                         f"{' e '.join(resposta)} anulam controle de grupo.")
        mergulho = sorted(self.inimigos_vistos & MERGULHO)
        if len(mergulho) >= 2 and "Lulu" in pool and "mergulho" not in self.notas_faladas:
            self.notas_faladas.add("mergulho")
            nomes = " e ".join(self.nomes.get(c, c) for c in mergulho)
            notas.append(f"Inimigos que mergulham: {nomes}. No seu pool, "
                         "Lulu é a que mais protege o carry.")
        cura = sorted(c for c in self.inimigos_vistos if c in CURA_FORTE)
        if cura and "cura" not in self.notas_faladas:
            self.notas_faladas.add("cura")
            nomes = " e ".join(self.nomes.get(c, c) for c in cura)
            notas.append(f"Inimigo com muita cura: {nomes}.")
        for n in notas:
            self.voz.falar(n)


# ---------------------------------------------------------------------------
def rodar(parar: threading.Event | None = None, voz: "Voz | None" = None,
          ouvido: "OuvidoComandos | None" = None, estado=None):
    """Loop principal. `parar` encerra o loop; `estado(texto)` recebe o status."""
    parar = parar or threading.Event()
    estado = estado or (lambda texto: None)
    voz = voz or Voz(ativa=True)
    estado("Carregando dados dos campeões...")
    print("Carregando dados dos campeões...")
    if not BUILDS:
        carregar_builds()
    campeoes = carregar_campeoes()
    itens = Itens(carregar_itens())
    coach = Coach(voz, campeoes, itens)
    cliente = ClienteLoL(CONFIG["pasta_lol"])
    selecao = (SelecaoCampeoes(voz, campeoes, cliente, itens, carregar_runas())
               if campeoes else None)
    sessao = requests.Session()
    print("Quíron rodando. Aguardando partida...")
    estado("Aguardando partida")

    falhas = 0
    proxima_leitura = 0.0
    ultimo_estado = ""
    while not parar.is_set():
        # microfone aberto só quando faz sentido (ver OuvidoComandos)
        if ouvido and ouvido.ativo:
            quer = CONFIG["comandos_de_voz"] and (coach.em_partida
                                                  or not CONFIG["microfone_so_na_partida"])
            if quer != ouvido.escutar.is_set():
                ouvido.ligar_microfone(quer)
        # comandos de voz respondem rápido (a cada 0,2 s)
        if ouvido and ouvido.ativo and CONFIG["comandos_de_voz"]:
            for cmd in ouvido.pegar():
                coach.executar_comando(cmd)

        if time.time() >= proxima_leitura:
            proxima_leitura = time.time() + CONFIG["intervalo_leitura_s"]
            jogo = ler_jogo(sessao)
            if jogo and jogo.get("allPlayers"):
                falhas = 0
                coach.processar(jogo)
                novo = (f"Em partida: {coach.eu['championName']}" if coach.eu
                        else "Em partida")
                if coach.itens and abs(coach.diferenca_ouro) >= 100:
                    d = coach.diferenca_ouro
                    novo += f" · ouro {'+' if d > 0 else '−'}{abs(d) / 1000:.1f} mil".replace(".", ",")
            else:
                falhas += 1
                novo = "Aguardando partida"
                # ~10 s sem resposta depois de uma partida = partida acabou
                if coach.em_partida and falhas >= 5:
                    coach.fim_partida()
                    print("Aguardando próxima partida...")
                elif coach.em_partida:
                    novo = ultimo_estado
                # fora da partida: aceita a fila e acompanha a seleção de campeões
                if CONFIG["aceitar_fila"] and not coach.em_partida:
                    cliente.pasta = Path(CONFIG["pasta_lol"])
                    if cliente.aceitar_fila():
                        print("Partida encontrada: aceita automaticamente.")
                        novo = "Partida aceita"
                usa_cliente = any(CONFIG[k] for k in (
                    "ajuda_selecao", "importar_runas", "importar_itens", "importar_feiticos",
                    "sugerir_escolha", "analise_draft"))
                if selecao and usa_cliente and not coach.em_partida:
                    selecao.processar(selecao.ler())
                    if selecao.ativa:
                        novo = "Seleção de campeões"
            if novo != ultimo_estado:
                ultimo_estado = novo
                estado(novo)
        time.sleep(0.2)
    if coach.em_partida:
        coach.fim_partida()
    if ouvido:
        ouvido.ligar_microfone(False)
    estado("Parado")


def main():
    ap = argparse.ArgumentParser(description="Quíron: coach por voz (API oficial local)")
    ap.add_argument("--sem-voz", action="store_true", help="só mostra os avisos no terminal")
    ap.add_argument("--sem-microfone", action="store_true", help="desliga os comandos de voz")
    args = ap.parse_args()
    carregar_config()
    voz = Voz(ativa=not args.sem_voz and CONFIG["voz_ligada"])
    ouvido = (OuvidoComandos() if CONFIG["comandos_de_voz"] and not args.sem_microfone
              else None)
    print("(Ctrl+C para sair)")
    rodar(voz=voz, ouvido=ouvido)


carregar_builds()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nAté a próxima!")

