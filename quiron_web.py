"""
Quíron — interface nova (HTML dentro de uma janela do Windows, via pywebview)
=============================================================================

A janela mostra as páginas da pasta ui/ (HTML, CSS e JavaScript). Este módulo
é a ponte: a classe Api tem tudo o que a tela pode pedir (estado do coach,
configurações, perfil, builds, relatório, voz, atualização) e a função
`evento()` empurra novidades do Python para a tela (avisos, estado, etc.).

O coach em si (coach_lol.py) não muda. Se a janela nova não abrir (por
exemplo, sem o WebView2 no Windows), o app abre na interface clássica.
"""

import json
import os
import queue
import sys
import threading
import webbrowser
from datetime import datetime
from pathlib import Path

import atualizacao
import coach_lol as coach
import funcoes_comuns
import registro
import relatorio_lol as relatorio
from versao import AVISO, VERSAO

PASTA_RECURSOS = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
PASTA_UI = PASTA_RECURSOS / "ui"
URL_BUILDS = "https://claude.ai/artifact/DNv4gfXzbRkregwhFNtQ4N"
NOME_REGISTRO = "Quiron"
NOME_REGISTRO_ANTIGO = "CoachLoL"

NOMES_FUNCAO = {"TOP": "Topo", "JUNGLE": "Caçador", "MIDDLE": "Meio", "BOTTOM": "Atirador",
                "UTILITY": "Suporte"}
TIPOS_AJUSTE = {"mago": "Mago / dano mágico", "encantador": "Encantador / proteção",
                "fisico": "Dano físico", "tanque": "Tanque"}
FEITICOS_PT = {"Flash": "Flash", "Smite": "Golpear", "Heal": "Curar", "Ignite": "Incendiar",
               "Exhaust": "Exaustão", "Barrier": "Barreira", "Teleport": "Teleporte",
               "Cleanse": "Purificar", "Ghost": "Fantasma"}
FEITICOS_ARQ = {"Flash": "SummonerFlash", "Smite": "SummonerSmite", "Heal": "SummonerHeal",
                "Ignite": "SummonerDot", "Exhaust": "SummonerExhaust",
                "Barrier": "SummonerBarrier", "Teleport": "SummonerTeleport",
                "Cleanse": "SummonerBoost", "Ghost": "SummonerHaste"}

# Interruptores simples (chave na CONFIG, título, descrição, invertido?)
INTERRUPTORES = {
    "cliente": [
        ("aceitar_fila", "Aceitar a fila sozinho", "Aceita a partida assim que ela é encontrada.", False),
        ("ajuda_selecao", "Ajuda na seleção de campeões", "Seu histórico na função e notas sobre os inimigos.", False),
        ("sugerir_escolha", "Sugerir escolha no draft", "Na sua vez: o campeão do seu pool que mais combina.", False),
        ("analise_draft", "Análise do draft no fim", "Pontos positivos e de atenção do seu time.", False),
        ("importar_runas", "Importar runas", "Cria a página “Quíron” do campeão escolhido.", False),
        ("importar_itens", "Importar itens", "Cria o conjunto de itens “Quíron” da loja.", False),
        ("importar_feiticos", "Importar feitiços", "Usa os feitiços da build (Flash na tecla de sempre).", False),
    ],
    "inicio": [
        ("analisar_composicao", "Build e ajustes no início", "Fala a build e as opções contra o time inimigo.", False),
        ("plano_pre_partida", "Plano pré-partida", "Fase forte, iniciação, ameaças e sua rota.", False),
        ("rota_selva", "Rota inicial da selva", "Quando você for o caçador: por onde começar e terminar.", False),
    ],
    "partida": [
        ("somente_antes_e_depois", "Avisos durante a partida", "Desligado: só build no início e resumo no fim.", True),
        ("avisar_objetivos", "Objetivos neutros nascendo", "Dragão, vastilarvas, arauto e barão, 1 minuto antes.", False),
        ("avisar_cacador_inimigo", "Caçador inimigo", "Quando ele aparece em abates e objetivos.", False),
        ("avisar_proximo_item", "Ouro para o próximo item", "Quanto falta para o próximo item da build.", False),
        ("avisar_diferenca_ouro", "Diferença de ouro dos times", "Pelos itens no placar, quando muda de faixa.", False),
        ("avisar_recompensa", "Recompensa", "Quem provavelmente está valendo ouro extra.", False),
        ("avisar_cs_baixo", "CS por minuto baixo", "Fora do suporte, quando ficar abaixo do mínimo.", False),
        ("modo_menos", "Modo “menos”", "Só os avisos importantes (igual a dizer “menos”).", False),
    ],
    "aplicativo": [
        ("iniciar_com_windows", "Iniciar com o Windows", "Abre minimizado na bandeja e já liga o coach.", False),
        ("minimizar_para_bandeja", "Minimizar para a bandeja ao fechar", "O X esconde a janela; para sair, use o ícone perto do relógio.", False),
        ("iniciar_coach_ao_abrir", "Ligar o coach ao abrir", "", False),
        ("verificar_atualizacoes", "Avisar versão nova", "Consulta o GitHub ao abrir o app.", False),
        ("builds_automaticas", "Baixar builds atualizadas", "Busca as builds do patch novo. Suas edições são mantidas.", False),
    ],
}

# Dicas para o ponto mais fraco da teia (uma por dia, alternando)
DICAS = {
    "farm": ["Entre uma luta e outra, volte para a rota ou para os campos: cada onda vale cerca de 120 de ouro.",
             "Nos primeiros 10 minutos, tente não perder nenhum último golpe da onda de canhão.",
             "Antes de ir para um objetivo, limpe a onda que está chegando na sua rota."],
    "visao": ["Compre uma sentinela de controle a cada volta à base: ela custa pouco e salva vidas.",
              "Antes de dragão e barão, coloque visão 1 minuto antes de ele nascer.",
              "Troque o amuleto pela lente quando o seu time estiver na frente: tirar a visão inimiga também conta."],
    "lutas": ["Quando um objetivo estiver para nascer, esteja perto dele 30 segundos antes.",
              "Se o seu time luta e você está longe, prefira pegar placas ou campos do outro lado.",
              "Olhe o minimapa a cada onda: muitas lutas começam com um aliado pedindo ajuda."],
    "abates": ["Antes de entrar numa luta, confira se o inimigo está sem o feitiço de fuga principal.",
               "Jogue para o seu ponto forte: se o seu campeão escala, evite lutas arriscadas cedo.",
               "Depois de um abate, use a vantagem: torre, dragão ou visão, não só voltar para a rota."],
    "sobrevivencia": ["Sem visão do caçador inimigo, jogue como se ele estivesse perto de você.",
                      "Morrer antes dos 14 minutos dá ouro de placa e de abate: segure a rota em vez de arriscar.",
                      "Volte para a base com o ouro do próximo item, não com a vida baixa no meio da rota."],
}
EIXOS = [("farm", "Farm"), ("visao", "Visão"), ("lutas", "Lutas"), ("abates", "Abates"),
         ("sobrevivencia", "Sobrevivência")]


# ---------------------------------------------------------------------------
# Utilidades do Windows
# ---------------------------------------------------------------------------
def comando_inicializacao() -> str:
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}" --minimizado'
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    return f'"{pythonw}" "{Path(__file__).with_name("coach_app.py").resolve()}" --minimizado'


def iniciar_com_windows(ligar: bool) -> bool:
    if sys.platform != "win32":
        return False
    import winreg
    chave = r"Software\Microsoft\Windows\CurrentVersion\Run"
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, chave, 0, winreg.KEY_SET_VALUE) as k:
        if ligar:
            winreg.SetValueEx(k, NOME_REGISTRO, 0, winreg.REG_SZ, comando_inicializacao())
        else:
            try:
                winreg.DeleteValue(k, NOME_REGISTRO)
            except FileNotFoundError:
                pass
        try:
            winreg.DeleteValue(k, NOME_REGISTRO_ANTIGO)
        except FileNotFoundError:
            pass
    return True


def _dec(v: float) -> str:
    return f"{v:.1f}".replace(".", ",")


def abrir_arquivo(caminho: Path):
    if sys.platform == "win32":
        os.startfile(caminho)  # noqa: S606
    else:
        webbrowser.open(Path(caminho).as_uri())


class SaidaParaTela:
    """Substitui o print: manda o texto para a tela (e para o log)."""

    def __init__(self, api: "Api"):
        self.api = api

    def write(self, texto):
        if texto and texto.strip():
            registro.log.info(texto.strip())
            self.api.escrever(texto.rstrip("\n"))

    def flush(self):
        pass


# ---------------------------------------------------------------------------
# A ponte
# ---------------------------------------------------------------------------
class Api:
    """Tudo o que o JavaScript pode chamar (window.pywebview.api.<método>).

    Métodos que começam com "_" não ficam visíveis para a página. O pywebview
    chama cada método numa thread própria, então esperar rede aqui não trava
    a janela.
    """

    def __init__(self):
        self._janela = None
        self._eventos: "queue.Queue[dict]" = queue.Queue()   # usados no modo de teste
        self._pronto = False
        self._pendentes: list[dict] = []
        self._historico: list[str] = []
        self._trava = threading.Lock()
        self._parar = threading.Event()
        self._thread: threading.Thread | None = None
        self._voz: coach.Voz | None = None
        self._voz_teste: coach.Voz | None = None
        self._ouvido = None
        self._bandeja = None
        self._estado = "Parado"
        self._itens = coach.Itens({})
        self._campeoes: dict = {}
        self._runas: dict = {}
        self._info_atualizacao: dict | None = None
        self._ao_sair = None

        self._migrados = coach.migrar_dados_antigos() if getattr(sys, "frozen", False) else 0
        registro.configurar(coach.BASE, VERSAO)
        ja_usava = coach.CONFIG_ARQ.exists()
        coach.carregar_config()
        if not coach.CONFIG.get("chave_ia_apagada"):
            threading.Thread(target=coach.apagar_chave_ia_antiga, daemon=True).start()
            coach.salvar_config({"chave_ia_apagada": True})
        self._precisa_perfil = not coach.perfil()["funcoes"]
        self._perfil_sugerido = coach.PERFIL_ANTIGO if (self._precisa_perfil and ja_usava) else None
        coach.carregar_builds()

    # ---- infraestrutura ---------------------------------------------------
    def _ligar_janela(self, janela):
        self._janela = janela

    def _pagina_pronta(self):
        with self._trava:
            self._pronto = True
            pendentes, self._pendentes = self._pendentes, []
        for ev in pendentes:
            self._enviar(ev)

    def _enviar(self, ev: dict):
        self._eventos.put(ev)
        if self._janela is not None:
            try:
                self._janela.evaluate_js(
                    f"window.quiron && window.quiron.evento({json.dumps(ev, ensure_ascii=False)})")
            except Exception:  # noqa: BLE001 (janela fechando)
                pass

    def evento(self, tipo: str, dados=None):
        ev = {"tipo": tipo, "dados": dados}
        with self._trava:
            if not self._pronto and self._janela is not None:
                self._pendentes.append(ev)
                return
        self._enviar(ev)

    def escrever(self, texto: str):
        linha = texto
        with self._trava:
            self._historico.append(linha)
            self._historico = self._historico[-400:]
        self.evento("log", linha)

    def proximos_eventos(self, espera: float = 20.0) -> list[dict]:
        """Só para o modo de teste (navegador comum): espera eventos novos."""
        try:
            evs = [self._eventos.get(timeout=espera)]
        except queue.Empty:
            return []
        while not self._eventos.empty():
            evs.append(self._eventos.get_nowait())
        return evs

    # ---- carga inicial ------------------------------------------------------
    def inicial(self) -> dict:
        """Tudo o que a tela precisa para desenhar a primeira vez."""
        self._pagina_pronta()
        return {
            "versao": VERSAO, "aviso": AVISO, "base": str(coach.BASE),
            "ddragon": coach.versao_dados(), "estado": self._estado,
            "rodando": self._rodando(), "log": list(self._historico),
            "config": self.config(), "perfil": self.perfil(),
            "precisa_perfil": self._precisa_perfil and bool(self._campeoes),
            "atualizacao": self._info_atualizacao, "migrados": self._migrados,
            "dados_prontos": bool(self._campeoes),
        }

    def _carregar_dados(self):
        self._itens = coach.Itens(coach.carregar_itens())
        self._campeoes = coach.carregar_campeoes()
        self._runas = coach.carregar_runas()
        self.evento("dados_prontos", {"ddragon": coach.versao_dados(),
                                      "precisa_perfil": self._precisa_perfil and bool(self._campeoes)})

    def _verificacoes(self):
        if coach.CONFIG["builds_automaticas"]:
            self._baixar_builds(manual=False)
        if coach.CONFIG["verificar_atualizacoes"]:
            self._checar_versao(manual=False)

    # ---- configurações -------------------------------------------------------
    def config(self) -> dict:
        c = coach.CONFIG
        grupos = {}
        for grupo, lista in INTERRUPTORES.items():
            grupos[grupo] = [{"chave": k, "titulo": t, "desc": d,
                              "valor": (not c.get(k)) if inv else bool(c.get(k))}
                             for k, t, d, inv in lista]
        return {
            "grupos": grupos,
            "voz_ligada": c["voz_ligada"], "comandos_de_voz": c["comandos_de_voz"],
            "microfone_so_na_partida": c["microfone_so_na_partida"],
            "microfone": c.get("microfone", ""), "voz_windows": c.get("voz_windows", ""),
            "velocidade_voz": c.get("velocidade_voz", 185), "volume_voz": c.get("volume_voz", 100),
            "palavra_chamada": c.get("palavra_chamada", "Quíron"),
            "pasta_lol": c.get("pasta_lol", ""),
            "exemplos_chamada": coach.exemplos_chamada(),
        }

    def definir(self, chave: str, valor):
        """Muda uma configuração. Interruptores invertidos chegam já como na tela."""
        invertidos = {k for lista in INTERRUPTORES.values() for k, _, _, inv in lista if inv}
        if chave in invertidos:
            valor = not valor
        if chave == "iniciar_com_windows":
            ok = iniciar_com_windows(bool(valor))
            if valor and not ok:
                self.escrever("“Iniciar com o Windows” só funciona no Windows.")
            valor = bool(valor) and ok
        coach.salvar_config({chave: valor})
        if chave == "voz_ligada" and self._voz:
            self._voz.ligar(bool(valor))
        return self.config()

    def vozes(self) -> list[dict]:
        return [{"nome": "Automática (português)", "id": ""}] + [
            {"nome": n, "id": i} for n, i in coach.listar_vozes()]

    def microfones(self) -> list[str]:
        return coach.listar_microfones()

    def testar_voz(self):
        frase = (f"Olá! Eu sou o Quíron. Diga {coach.CONFIG.get('palavra_chamada', 'Quíron')} "
                 "itens para ouvir a build.")
        voz = self._voz
        if voz is None or not voz.ativa:
            if self._voz_teste is None:
                self._voz_teste = coach.Voz(ativa=True)
            voz = self._voz_teste
        voz.fila.put(frase)

    def chamada_validar(self, nome: str) -> dict:
        nome = (nome or "").strip()
        if not coach.vocabulario():
            return {"estado": "sem_modelo", "pode_salvar": bool(nome)}
        if not nome:
            return {"estado": "vazio", "pode_salvar": False}
        if coach.formas_chamada(nome):
            return {"estado": "ok", "pode_salvar": True, "exemplos": coach.exemplos_chamada(nome)}
        return {"estado": "desconhecida", "pode_salvar": False,
                "sugestoes": [s.capitalize() for s in coach.sugestoes_chamada(nome)]}

    def chamada_testar(self, nome: str) -> dict:
        try:
            texto, acao = coach.testar_chamada(nome.strip())
            return {"texto": texto, "acao": acao}
        except Exception as e:  # noqa: BLE001
            registro.erro("Falha no teste da palavra de chamada", e)
            return {"erro": str(e)}

    def chamada_salvar(self, nome: str) -> dict:
        if not self.chamada_validar(nome)["pode_salvar"]:
            return self.config()
        coach.salvar_config({"palavra_chamada": nome.strip()})
        self.escrever(f"Palavra de chamada: {nome.strip()}. Vale a partir da próxima partida.")
        return self.config()

    def procurar_pasta(self) -> str | None:
        if self._janela is None:
            return None
        import webview
        tipo = getattr(getattr(webview, "FileDialog", None), "FOLDER", None) or webview.FOLDER_DIALOG
        escolha = self._janela.create_file_dialog(tipo,
                                                  directory=coach.CONFIG.get("pasta_lol", ""))
        if escolha:
            pasta = os.path.normpath(escolha[0] if isinstance(escolha, (list, tuple)) else escolha)
            coach.salvar_config({"pasta_lol": pasta})
            return pasta
        return None

    # ---- perfil -----------------------------------------------------------
    def perfil(self) -> dict:
        p = coach.perfil()
        if not p["funcoes"] and self._perfil_sugerido:
            p = p | self._perfil_sugerido
        p["texto"] = coach.texto_perfil()
        p["icone"] = coach.CONFIG.get("perfil", {}).get("icone")
        p["pdl"] = coach.CONFIG.get("perfil", {}).get("pdl")
        p["vitorias"] = coach.CONFIG.get("perfil", {}).get("vitorias")
        p["derrotas"] = coach.CONFIG.get("perfil", {}).get("derrotas")
        return p

    def perfil_salvar(self, dados: dict) -> dict:
        funcoes = [f for f in coach.FUNCOES if f in dados.get("funcoes", [])]
        if not funcoes:
            return {"erro": "Marque pelo menos uma função."}
        pool = {f: list(dados.get("pool", {}).get(f, []))[:6] for f in funcoes}
        if not any(pool.values()):
            return {"erro": "Adicione pelo menos um campeão."}
        riot = (dados.get("riot_id") or "").strip()
        if riot and "#" not in riot:
            return {"erro": "O Riot ID tem o formato Nome#TAG."}
        novo = {"riot_id": riot, "servidor": dados.get("servidor") or "BR",
                "elo": dados.get("elo", ""), "funcoes": funcoes, "pool": pool}
        for k in ("icone", "pdl", "vitorias", "derrotas"):
            if dados.get(k) is not None:
                novo[k] = dados[k]
        coach.salvar_config({"perfil": novo})
        self._precisa_perfil = False
        self._perfil_sugerido = None
        self.escrever("Perfil salvo.")
        return {"ok": True, "perfil": self.perfil()}

    def buscar_invocador(self, riot_id: str = "", proprio: bool = False) -> dict:
        cliente = coach.ClienteLoL(coach.CONFIG["pasta_lol"])
        try:
            regiao = ""
            if proprio:
                eu = cliente.eu()
                if not eu or not eu.get("riot_id"):
                    return {"silencio": True}
                riot_id, regiao = eu["riot_id"], eu.get("regiao", "")
            dados = cliente.buscar_invocador(riot_id)
            if dados.get("erro"):
                return dados
            if not regiao:
                eu = cliente.eu()
                regiao = (eu or {}).get("regiao", "")
            dados["regiao"] = regiao
            # funções e campeões mais jogados (para sugerir no perfil)
            total = dados.get("partidas_lidas", 0)
            por_chave = {c["key"]: k for k, c in self._campeoes.items()}
            funcoes = [f for f, n in dados["funcoes"].most_common(3) if total and n / total >= 0.15]
            dados["sugestao"] = {
                "total": total,
                "resumo": [{"funcao": f, "nome": NOMES_FUNCAO[f], "pct": round(100 * n / total)}
                           for f, n in dados["funcoes"].most_common() if total and n / total >= 0.05],
                "funcoes": funcoes,
                "pool": {f: [por_chave[k] for k, _ in dados["campeoes"][f].most_common(6)
                             if k in por_chave] for f in funcoes},
            }
            dados.pop("funcoes", None)
            dados.pop("campeoes", None)
            return dados
        except Exception as e:  # noqa: BLE001
            registro.erro("Falha ao buscar invocador", e)
            return {"erro": "Não consegui buscar agora. Tente de novo."}

    # ---- campeões e itens -----------------------------------------------------
    def campeoes(self, funcao: str | None = None) -> list[dict]:
        lista = []
        for cid, c in sorted(self._campeoes.items(), key=lambda kv: kv[1]["name"].lower()):
            item = {"id": cid, "nome": c["name"]}
            if funcao:
                item["comum"] = funcoes_comuns.comum(cid, funcao)
            lista.append(item)
        return lista

    def itens_loja(self) -> list[dict]:
        return [{"id": i["id"], "en": i["en"], "nome": i["nome"], "tags": i["tags"]}
                for i in self._itens.lista_loja()]

    # ---- builds -----------------------------------------------------------
    def _item(self, en: str) -> dict:
        return {"en": en, "id": self._itens.id(en), "nome": self._itens.nome_pt(en)}

    def _pagina_runas(self, pag: dict | None) -> dict | None:
        runas = self._runas
        if not pag or not runas.get("detalhe"):
            return None
        escolhidas = {runas["runas"].get(n) for n in pag.get("runas", []) + pag.get("runas2", [])}
        arvores = {a["id"]: a for a in runas["detalhe"]}
        prim = arvores.get(runas["arvores"].get(pag.get("primaria")))
        sec = arvores.get(runas["arvores"].get(pag.get("secundaria")))
        if not prim or not sec:
            return None

        def arvore(a, pular_chave):
            fileiras = [[dict(r, ativa=r["id"] in escolhidas) for r in f]
                        for i, f in enumerate(a["fileiras"]) if not (pular_chave and i == 0)]
            return {"nome": a["nome"], "icone": a["icone"], "fileiras": fileiras,
                    "escolhidas": [r["nome"] for f in fileiras for r in f if r["ativa"]]}

        fragmentos = []
        for opcoes, escolhido in zip(coach.LINHAS_FRAGMENTOS, pag.get("fragmentos", [])):
            fragmentos.append({"opcoes": [{"id": o, "url": coach.url_imagem("fragmento", o),
                                           "ativa": o == escolhido} for o in opcoes],
                               "nome": coach.NOME_FRAGMENTO.get(escolhido, escolhido)})
        return {"primaria": arvore(prim, False), "secundaria": arvore(sec, True),
                "fragmentos": fragmentos}

    def _build_cartao(self, cid: str, stats: dict) -> dict | None:
        b = coach.obter_build(cid, self._campeoes)
        if not b:
            return None
        v, d = stats.get(cid, (0, 0))
        return {
            "id": cid, "nome": self._campeoes.get(cid, {}).get("name", cid),
            "funcao": b.get("funcao"), "funcao_nome": NOMES_FUNCAO.get(b.get("funcao"), b.get("funcao")),
            "selo": ("personalizada" if b.get("personalizado") else
                     "estimativa" if b.get("estimativa") else
                     "genérica" if b.get("generica") else ""),
            "vitorias": v, "derrotas": d,
            "taxa": round(100 * v / (v + d)) if v + d else None,
            "runa": b.get("runas", ""),
            "tipo_ajuste": b.get("tipo_ajuste"),
            "inicio": [self._item(n) for n in (b.get("inicio") or [])[:1]],
            "itens": [self._item(n) for n in b.get("itens", [])],
            "feiticos": [{"nome": FEITICOS_PT.get(f, f), "arq": FEITICOS_ARQ.get(f, "")}
                         for f in b.get("feiticos", [])],
            "pagina": self._pagina_runas(b.get("pagina")),
        }

    def builds(self) -> dict:
        info = coach.INFO_BUILDS
        stats = coach.estatisticas_pool()
        pool = coach.todos_do_pool()
        outros = [c for c in coach.BUILDS if c not in pool]
        return {
            "info": {"patch": info.get("patch"), "fonte": info.get("fonte"),
                     "atualizado": info.get("atualizado")},
            "pool": [x for x in (self._build_cartao(c, stats) for c in pool) if x],
            "outros": [x for x in (self._build_cartao(c, stats) for c in outros) if x],
            "tipos": TIPOS_AJUSTE, "funcoes": NOMES_FUNCAO,
        }

    def build_detalhe(self, cid: str | None) -> dict:
        """Dados para o editor de build."""
        b = (coach.obter_build(cid, self._campeoes) or {}) if cid else {}
        tipo = b.get("tipo_ajuste")
        return {"id": cid, "nome": self._campeoes.get(cid, {}).get("name", cid) if cid else "",
                "funcao": b.get("funcao", "UTILITY"), "tipo": tipo or "mago",
                "runa": b.get("runas", ""), "itens": [self._item(n) for n in b.get("itens", [])]}

    def build_sugerida(self, cid: str, funcao: str | None = None) -> dict:
        """Build padrão para um campeão novo, na função principal dele (ou na escolhida)."""
        import builds_genericas
        if cid not in self._campeoes:
            return {"erro": "Campeão desconhecido."}
        comuns = funcoes_comuns.funcoes_de(cid)
        if not funcao:
            no_pool = next((f for f in coach.FUNCOES if cid in coach.pool_da_funcao(f)), None)
            provavel = builds_genericas.funcao_provavel(self._campeoes[cid])
            pesquisada = coach.BUILDS.get(cid, {}).get("funcao")
            funcao = (no_pool or pesquisada or (provavel if provavel in comuns else None)
                      or (comuns[0] if comuns else provavel))
        pesquisada = coach.BUILDS.get(cid)
        if pesquisada and pesquisada.get("funcao") == funcao:
            b, origem = pesquisada, "pesquisada"
        else:  # sem build pesquisada nessa função: a padrão pelo tipo do campeão
            g = builds_genericas.build_generica(cid, self._campeoes[cid], funcao)
            b, origem = dict(g, tipo_ajuste=g["ajustes"]), "genérica"
        return {"funcao": funcao, "tipo": b.get("tipo_ajuste") or "mago", "runa": b.get("runas", ""),
                "itens": [self._item(n) for n in b.get("itens", [])], "origem": origem,
                "comum": funcoes_comuns.comum(cid, funcao),
                "comuns": [NOMES_FUNCAO[f] for f in comuns]}

    def build_salvar(self, cid: str, dados: dict) -> dict:
        if not cid or cid not in self._campeoes:
            return {"erro": "Escolha um campeão."}
        itens = [n for n in dados.get("itens", []) if n]
        if not itens:
            return {"erro": "Coloque pelo menos um item."}
        nova = {"funcao": dados.get("funcao") or "UTILITY",
                "runas": (dados.get("runa") or "").strip() or "—",
                "itens": itens, "ajustes": dados.get("tipo") or "mago"}
        base = coach.obter_build(cid, self._campeoes, nova["funcao"]) or {}
        for k in ("pagina", "feiticos", "inicio"):
            if base.get(k):
                nova[k] = base[k]
        coach.salvar_build_usuario(cid, nova)
        self.escrever(f"Build de {self._campeoes[cid]['name']} salva.")
        return {"ok": True}

    def build_restaurar(self, cid: str) -> dict:
        coach.restaurar_build(cid)
        self.escrever(f"Build de {self._campeoes.get(cid, {}).get('name', cid)} restaurada.")
        return {"ok": True}

    def pedir_build(self, cid: str):
        from urllib.parse import quote
        nome = self._campeoes.get(cid, {}).get("name", cid)
        b = coach.obter_build(cid, self._campeoes) or {}
        corpo = (f"Campeão: {nome} ({cid})\nFunção: {b.get('funcao', '?')}\n\n"
                 "Pedido feito pelo app Quíron. A tarefa semanal pesquisa a build e adiciona "
                 "ao builds.json.")
        webbrowser.open(f"https://github.com/{coach.REPO_GITHUB}/issues/new?title="
                        f"{quote('Build: ' + nome)}&body={quote(corpo)}")
        self.escrever(f"Abrindo o pedido de build para {nome} no GitHub (precisa estar logado).")

    def buscar_builds(self):
        threading.Thread(target=lambda: self._baixar_builds(manual=True), daemon=True).start()

    def _baixar_builds(self, manual: bool):
        try:
            patch = coach.baixar_builds()
            if patch:
                self.escrever(f"Builds atualizadas para o patch {patch}.")
            elif manual:
                self.escrever("As builds já estão em dia.")
        except Exception as e:  # noqa: BLE001
            registro.erro("Falha ao baixar builds", e)
            if manual:
                self.escrever("Não consegui buscar as builds agora (sem internet?).")
        self.evento("builds", None)

    # ---- relatório ------------------------------------------------------------
    def _teia(self, partidas: list[dict]) -> dict:
        """Notas de 0 a 100 nos cinco eixos (75 = na meta)."""
        def nota(valor, meta):
            return None if valor is None else max(5, min(100, round(valor / meta * 75)))

        def minutos(r):
            try:
                m, s = r.get("duracao", "0:0").split(":")
                return max(int(m) + int(s) / 60, 1)
            except ValueError:
                return None

        cs, vis, kp, kda, m14 = [], [], [], [], []
        metas_visao = {"UTILITY": 2.0, "JUNGLE": 1.2}
        for r in partidas:
            pos = r.get("posicao") or ""
            meta_cs = coach.CONFIG["cs_minimo"].get(pos)
            if meta_cs and r.get("cs_por_min") is not None:
                cs.append(r["cs_por_min"] / meta_cs)
            mins = minutos(r)
            if r.get("placar_visao") is not None and mins:
                vis.append(r["placar_visao"] / mins / metas_visao.get(pos, 0.8))
            if r.get("kp_final") is not None:
                kp.append(r["kp_final"] / 0.6)
            try:
                k, d, a = (int(x) for x in r.get("kda", "").split("/"))
                kda.append(((k + a) / max(d, 1)) / 3)
            except ValueError:
                pass
            m14.append(r.get("mortes_antes_14", 0))
        media = relatorio.media
        notas = {
            "farm": nota(media(cs), 1), "visao": nota(media(vis), 1), "lutas": nota(media(kp), 1),
            "abates": nota(media(kda), 1),
            "sobrevivencia": None if not m14 else max(5, round(100 - 20 * media(m14))),
        }
        validas = {k: v for k, v in notas.items() if v is not None}
        fraco = min(validas, key=validas.get) if validas else None
        dica = None
        if fraco:
            lista = DICAS[fraco]
            dica = {"eixo": dict(EIXOS)[fraco], "texto": lista[datetime.now().toordinal() % len(lista)]}
        return {"eixos": [{"chave": k, "nome": n, "nota": notas[k]} for k, n in EIXOS],
                "fraco": fraco, "dica": dica}

    def relatorio(self, dias: int = 7) -> dict:
        partidas = relatorio.ler_partidas(int(dias))
        dados = relatorio.montar_dados(partidas)
        for c in dados["campeoes"]:
            c["id"] = next((r.get("campeao_id") for r in partidas
                            if r.get("campeao") == c["campeao"] and r.get("campeao_id")), None)
        dados["teia"] = self._teia(partidas)
        dados["dias"] = dias
        return dados

    def exportar_relatorio(self, dias: int = 7):
        _, n = relatorio.gerar(int(dias), abrir=True)
        self.escrever(f"Relatório aberto no navegador ({n} partidas).")

    def ultima_partida(self) -> dict | None:
        partidas = relatorio.ler_partidas(0)
        if not partidas:
            return None
        r = partidas[-1]
        teia = self._teia(relatorio.ler_partidas(7) or [r])
        pontos = []
        kp = r.get("kp_final")
        if kp is not None:
            pontos.append(f"Participação em abates de {round(kp * 100)}% "
                          f"({'acima' if kp >= 0.5 else 'abaixo'} da meta de 50%).")
        m14 = r.get("mortes_antes_14", 0)
        pontos.append("Nenhuma morte antes dos 14 minutos." if not m14 else
                      f"{m14} {'morte' if m14 == 1 else 'mortes'} antes dos 14 minutos.")
        if r.get("posicao") != "UTILITY" and r.get("cs_por_min") is not None:
            meta = coach.CONFIG["cs_minimo"].get(r.get("posicao"))
            if meta:
                pontos.append(f"{_dec(r['cs_por_min'])} de CS por minuto (meta {_dec(meta)}).")
        return {"campeao": r.get("campeao"), "id": r.get("campeao_id") or r.get("campeao"),
                "resultado": r.get("resultado"), "kda": r.get("kda"), "duracao": r.get("duracao"),
                "quando": r["_quando"].strftime("%d/%m %H:%M"), "pontos": pontos, "teia": teia}

    # ---- coach ------------------------------------------------------------
    def _rodando(self) -> bool:
        return bool(self._thread and self._thread.is_alive() and not self._parar.is_set())

    def alternar(self) -> bool:
        if self._rodando():
            self._parar.set()
            self.evento("parando", None)
            return False
        self.iniciar()
        return True

    def iniciar(self):
        if self._thread and self._thread.is_alive():
            return
        self._parar.clear()
        self._thread = threading.Thread(target=self._trabalhar, daemon=True)
        self._thread.start()
        self.evento("rodando", True)
        self._atualizar_bandeja()

    def _trabalhar(self):
        try:
            if self._voz is None:
                self._voz = coach.Voz(ativa=coach.CONFIG["voz_ligada"])
            if self._ouvido is None and coach.CONFIG["comandos_de_voz"]:
                self._ouvido = coach.OuvidoComandos()
            coach.rodar(self._parar, self._voz, self._ouvido, estado=self._mudou_estado)
        except Exception as e:  # noqa: BLE001
            registro.erro("Falha no coach", e)
            self.escrever(f"Erro: {e}")
        finally:
            self._mudou_estado("Parado")
            self.evento("rodando", False)
            self._atualizar_bandeja()

    def _mudou_estado(self, texto: str):
        self._estado = texto
        self.evento("estado", texto)
        if self._bandeja:
            self._bandeja.title = f"Quíron — {texto}"
        if texto.startswith("Aguardando"):
            # voltou a esperar (uma partida pode ter terminado): atualiza resumo e relatório
            self.evento("partidas", None)

    # ---- atualização do app -----------------------------------------------------
    def verificar_atualizacao(self):
        threading.Thread(target=lambda: self._checar_versao(manual=True), daemon=True).start()

    def _checar_versao(self, manual: bool):
        try:
            info = atualizacao.verificar(VERSAO)
        except Exception as e:  # noqa: BLE001
            registro.erro("Falha ao verificar atualização", e)
            if manual:
                self.escrever("Não consegui verificar atualizações agora.")
            return
        if info:
            self._info_atualizacao = info
            self.evento("atualizacao", info)
        elif manual:
            self.escrever(f"Você já está na versão mais recente ({VERSAO}).")
            self.evento("sem_atualizacao", VERSAO)

    def ver_novidades(self):
        if self._info_atualizacao:
            webbrowser.open(self._info_atualizacao["pagina"])

    def atualizar_app(self):
        info = self._info_atualizacao
        if not info or not info.get("url") or not getattr(sys, "frozen", False):
            self.ver_novidades()
            return

        def trabalho():
            try:
                arq = atualizacao.baixar(info, lambda p: self.evento("progresso", int(p * 100)))
                registro.log.info("Instalando atualização %s", info["versao"])
                atualizacao.instalar(arq)
                self.sair()
            except Exception as e:  # noqa: BLE001
                registro.erro("Falha ao atualizar", e)
                self.escrever("Não consegui baixar a atualização. Tente pela página do projeto.")
                self.evento("progresso", None)
        threading.Thread(target=trabalho, daemon=True).start()

    # ---- pequenos atalhos -----------------------------------------------------
    def abrir_url(self, url: str):
        if url in ("builds", "github"):
            url = URL_BUILDS if url == "builds" else atualizacao.PAGINA
        webbrowser.open(url)

    def abrir_pasta_dados(self):
        abrir_arquivo(coach.BASE)

    def abrir_log(self):
        arq = registro.ARQ_LOG
        if arq and arq.exists():
            abrir_arquivo(arq)
        else:
            self.escrever("O log ainda está vazio.")

    def diagnostico(self) -> str:
        return registro.diagnostico(VERSAO, coach.BASE)

    # ---- janela e bandeja -------------------------------------------------------
    def _criar_bandeja(self):
        try:
            import pystray
            from PIL import Image
            imagem = Image.open(PASTA_RECURSOS / "icone.ico")
            menu = pystray.Menu(
                pystray.MenuItem("Abrir Quíron", lambda: self.mostrar(), default=True),
                pystray.MenuItem(lambda _: "Parar coach" if self._rodando() else "Iniciar coach",
                                 lambda: self.alternar()),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Sair", lambda: self.sair()),
            )
            self._bandeja = pystray.Icon("Quiron", imagem, "Quíron", menu)
            self._bandeja.run_detached()
        except Exception:  # noqa: BLE001 (sem bandeja, o app funciona igual)
            self._bandeja = None

    def _atualizar_bandeja(self):
        if self._bandeja:
            try:
                self._bandeja.update_menu()
            except Exception:  # noqa: BLE001
                pass

    def mostrar(self):
        if self._janela is not None:
            try:
                self._janela.show()
                self._janela.restore()
            except Exception:  # noqa: BLE001
                pass

    def _ao_fechar(self):
        """Evento da janela: True deixa fechar; False cancela (vai para a bandeja)."""
        try:  # lembra o tamanho para a próxima vez
            w, h = int(self._janela.width), int(self._janela.height)
            if w >= 900 and h >= 560:
                coach.salvar_config({"janela": [w, h]})
        except Exception:  # noqa: BLE001
            pass
        if self._bandeja and coach.CONFIG["minimizar_para_bandeja"]:
            threading.Thread(target=self._esconder, daemon=True).start()
            return False
        threading.Thread(target=self.sair, daemon=True).start()
        return False

    def _esconder(self):
        try:
            self._janela.hide()
        except Exception:  # noqa: BLE001
            pass
        if not getattr(self, "_avisou_bandeja", False):
            self._avisou_bandeja = True
            try:
                self._bandeja.notify("O Quíron continua rodando aqui. Para sair, clique com o "
                                     "botão direito no ícone.", "Quíron")
            except Exception:  # noqa: BLE001
                pass

    def sair(self):
        self._parar.set()
        if self._thread:
            self._thread.join(timeout=3)
        if self._bandeja:
            try:
                self._bandeja.stop()
            except Exception:  # noqa: BLE001
                pass
        import logging
        logging.shutdown()
        os._exit(0)


# ---------------------------------------------------------------------------
def iniciar_tarefas(api: Api, minimizado: bool):
    threading.Thread(target=api._carregar_dados, daemon=True).start()
    threading.Thread(target=api._verificacoes, daemon=True).start()
    if minimizado or coach.CONFIG["iniciar_coach_ao_abrir"]:
        threading.Timer(0.8, api.iniciar).start()


def main(minimizado: bool = False):
    """Abre a janela nova. Levanta exceção se o pywebview/WebView2 não funcionar."""
    import webview

    api = Api()
    saidas = sys.stdout, sys.stderr
    sys.stdout = SaidaParaTela(api)
    sys.stderr = SaidaParaTela(api)
    try:
        _abrir(webview, api, minimizado)
    except Exception:
        # devolve tudo como estava: quem chamou abre a interface clássica
        sys.stdout, sys.stderr = saidas
        if api._bandeja:
            try:
                api._bandeja.stop()
            except Exception:  # noqa: BLE001
                pass
        api._parar.set()
        raise
    api.sair()


def area_util() -> tuple[int, int, int, int] | None:
    """Área livre da tela principal (sem a barra de tarefas), em pixels lógicos
    (já descontada a escala do Windows, ex.: 125%). (x, y, largura, altura)."""
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        from ctypes import wintypes
        ret = wintypes.RECT()
        ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(ret), 0)  # SPI_GETWORKAREA
        try:
            dpi = ctypes.windll.user32.GetDpiForSystem()
        except AttributeError:
            dpi = 96
        f = 96 / (dpi or 96)
        return (round(ret.left * f), round(ret.top * f),
                round((ret.right - ret.left) * f), round((ret.bottom - ret.top) * f))
    except Exception:  # noqa: BLE001
        return None


def tamanho_janela() -> tuple[int, int, int | None, int | None]:
    """Tamanho salvo da última vez (ou 1120x900), sem passar da área livre da tela."""
    salvo = coach.CONFIG.get("janela") or [1120, 900]
    w, h = int(salvo[0]), int(salvo[1])
    area = area_util()
    if not area:
        return w, h, None, None
    ax, ay, aw, ah = area
    # a moldura da janela e a barra de título também ocupam espaço
    w, h = min(w, aw - 16), min(h, ah - 40)
    return max(w, 900), max(h, 560), ax + (aw - w) // 2, ay + max((ah - h) // 2 - 10, 0)


def _abrir(webview, api: Api, minimizado: bool):
    w, h, x, y = tamanho_janela()
    janela = webview.create_window(
        f"Quíron {VERSAO}", str(PASTA_UI / "index.html"), js_api=api,
        width=w, height=h, x=x, y=y, min_size=(900, 560), hidden=minimizado,
        background_color="#0b1118", text_select=False)
    api._ligar_janela(janela)
    janela.events.closing += api._ao_fechar
    api.escrever(f"Seus dados ficam em: {coach.BASE}")
    if api._migrados:
        api.escrever(f"{api._migrados} partidas antigas foram copiadas da versão anterior.")

    def ao_iniciar():
        # Só depois que a janela abriu de fato: se o WebView2 falhar, nada
        # (bandeja, coach) fica rodando em paralelo com a interface clássica.
        api._criar_bandeja()
        iniciar_tarefas(api, minimizado)
    # gui="edgechromium": sem o WebView2, falha (e o app abre na interface clássica)
    webview.start(ao_iniciar, gui="edgechromium" if sys.platform == "win32" else None,
                  http_server=True, private_mode=False, storage_path=str(coach.BASE / "webview"))


def teste_janela(saida: str):
    """Abre a janela de verdade, percorre as abas e grava o resultado (build do GitHub)."""
    import webview

    api = Api()
    resultado = {"etapas": []}

    def gravar_e_sair(extra=None):
        if extra:
            resultado.update(extra)
        Path(saida).write_text(json.dumps(resultado, ensure_ascii=False, indent=1), encoding="utf-8")
        os._exit(0)

    threading.Timer(120, lambda: gravar_e_sair({"erro": "tempo esgotado"})).start()
    janela = webview.create_window("Quíron (teste)", str(PASTA_UI / "index.html"), js_api=api,
                                   width=1120, height=900, background_color="#0b1118")
    api._ligar_janela(janela)

    def roteiro():
        import time
        threading.Thread(target=api._carregar_dados, daemon=True).start()
        time.sleep(8)
        js = ("JSON.stringify({versao: S.versao, abas: document.querySelectorAll('.aba').length,"
              " tela: S.tela, botao: !!document.querySelector('#bt-coach'), erros: window.__erros})")
        resultado["etapas"].append({"coach": json.loads(janela.evaluate_js(js))})
        for tela, seletor in (("builds", ".build"), ("relatorio", ".tile"), ("config", ".sw")):
            janela.evaluate_js(f"document.querySelectorAll('.veu').forEach(v => v.remove()); irPara('{tela}')")
            time.sleep(4)
            n = janela.evaluate_js(f"document.querySelectorAll('#tela-{tela} {seletor}').length")
            resultado["etapas"].append({tela: n})
        resultado["erros_js"] = json.loads(janela.evaluate_js("JSON.stringify(window.__erros)"))
        resultado["ok"] = (resultado["etapas"][0]["coach"].get("botao") is True
                           and all(list(e.values())[0] for e in resultado["etapas"][1:])
                           and not resultado["erros_js"])
        gravar_e_sair()

    webview.start(roteiro, gui="edgechromium" if sys.platform == "win32" else None,
                  http_server=True, private_mode=True)
