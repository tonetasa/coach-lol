"""Integração com o cliente do League of Legends (API local do lobby, "LCU").

Faz três coisas fora da partida:
  - aceita a fila automaticamente;
  - cria/atualiza a página de runas "Quíron" do campeão escolhido;
  - cria o conjunto de itens "Quíron" do campeão (aparece na loja).

A Riot diz que essa API não tem suporte oficial para apps de terceiros: ela
funciona e é usada por apps conhecidos, mas pode mudar sem aviso.
"""

from collections import Counter
from pathlib import Path
from urllib.parse import quote

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

NOME_PAGINA = "Quíron"
NOMES_ANTIGOS = ("Coach LoL",)  # páginas e conjuntos criados por versões antigas

# Fragmentos (linhas: ataque, flexível, defesa)
FRAGMENTOS = {
    "adaptativo": 5008, "vel_ataque": 5005, "aceleracao": 5007,
    "vel_movimento": 5010, "vida_escalavel": 5001, "vida": 5011, "tenacidade": 5013,
}


TIERS_PT = {"IRON": "Ferro", "BRONZE": "Bronze", "SILVER": "Prata", "GOLD": "Ouro",
            "PLATINUM": "Platina", "EMERALD": "Esmeralda", "DIAMOND": "Diamante",
            "MASTER": "Mestre", "GRANDMASTER": "Grão-Mestre", "CHALLENGER": "Desafiante"}
SEM_DIVISAO = {"MASTER", "GRANDMASTER", "CHALLENGER"}
FILAS_IGNORADAS = {450, 900, 1010, 1300, 1700, 1710, 1900, 2000, 2010, 2020}  # ARAM, arena, etc.


def _riot_id(inv: dict) -> str:
    nome, tag = inv.get("gameName"), inv.get("tagLine")
    return f"{nome}#{tag}" if nome and tag else ""


def _achar_puuid(obj) -> str | None:
    """Acha o primeiro "puuid" numa resposta (objeto ou lista, em qualquer nível)."""
    if isinstance(obj, dict):
        if isinstance(obj.get("puuid"), str) and obj["puuid"]:
            return obj["puuid"]
        valores = obj.values()
    elif isinstance(obj, list):
        valores = obj
    else:
        return None
    for v in valores:
        achado = _achar_puuid(v)
        if achado:
            return achado
    return None


def _funcao(participante: dict) -> str | None:
    """Função jogada a partir do timeline (lane/role) do histórico do cliente."""
    pos = (participante.get("teamPosition") or participante.get("individualPosition") or "").upper()
    if pos in ("TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"):
        return pos
    tl = participante.get("timeline") or {}
    lane, role = (tl.get("lane") or "").upper(), (tl.get("role") or "").upper()
    if lane == "JUNGLE":
        return "JUNGLE"
    if lane == "TOP":
        return "TOP"
    if lane in ("MIDDLE", "MID"):
        return "MIDDLE"
    if lane in ("BOTTOM", "BOT"):
        return "UTILITY" if role == "DUO_SUPPORT" else "BOTTOM"
    return None


class ClienteLoL:
    def __init__(self, pasta_lol: str):
        self.pasta = Path(pasta_lol)
        self.sessao: requests.Session | None = None
        self.base = ""

    # -- conexão -------------------------------------------------------------
    def _conectar(self) -> bool:
        try:
            _, _, porta, senha, proto = (self.pasta / "lockfile").read_text().strip().split(":")
        except (OSError, ValueError):
            return False
        self.base = f"{proto}://127.0.0.1:{porta}"
        self.sessao = requests.Session()
        self.sessao.auth = ("riot", senha)
        self.sessao.verify = False
        return True

    def pedir(self, metodo: str, caminho: str, **kw) -> requests.Response | None:
        if not self.sessao and not self._conectar():
            return None
        try:
            # verify=False aqui (e não só na sessão): variáveis de ambiente de
            # certificado não podem sobrescrever o certificado próprio do cliente
            return self.sessao.request(metodo, self.base + caminho, timeout=3, verify=False, **kw)
        except requests.RequestException:
            self.sessao = None  # cliente fechou ou reiniciou
            return None

    def get(self, caminho: str):
        r = self.pedir("GET", caminho)
        if r is not None and r.status_code == 200:
            try:
                return r.json()
            except ValueError:
                return None
        return None

    # -- invocador -----------------------------------------------------------
    def conectado(self) -> bool:
        return self.get("/lol-summoner/v1/current-summoner") is not None

    def eu(self) -> dict | None:
        """Riot ID e região da conta logada no cliente."""
        eu = self.get("/lol-summoner/v1/current-summoner")
        if not eu:
            return None
        regiao = (self.get("/riotclient/region-locale") or {}).get("region", "")
        return {"riot_id": _riot_id(eu), "regiao": regiao.upper(), "puuid": eu.get("puuid")}

    def _puuid_por_riot_id(self, nome: str, tag: str) -> str | None:
        # O cliente mudou de endpoint algumas vezes; tenta os conhecidos.
        tentativas = [
            f"/lol-summoner/v1/alias/lookup?gameName={quote(nome)}&tagLine={quote(tag)}",
            f"/player-account/aliases/v1/lookup?gameName={quote(nome)}&tagLine={quote(tag)}",
            f"/lol-summoner/v1/summoners?name={quote(nome + '#' + tag)}",
        ]
        for caminho in tentativas:
            puuid = _achar_puuid(self.get(caminho))
            if puuid:
                return puuid
        return None

    def buscar_invocador(self, riot_id: str) -> dict:
        """Busca um Riot ID pelo cliente (precisa do cliente aberto e logado).

        Retorna {"erro": ...} ou {"riot_id", "nivel", "icone", "elo", "pdl",
        "vitorias", "derrotas", "funcoes": Counter, "campeoes": {funcao: Counter}}.
        """
        if "#" not in riot_id:
            return {"erro": "O Riot ID tem o formato Nome#TAG."}
        nome, tag = (x.strip() for x in riot_id.rsplit("#", 1))
        if not self.conectado():
            return {"erro": "Abra o cliente do LoL (logado) para buscar."}
        puuid = self._puuid_por_riot_id(nome, tag)
        if not puuid:
            return {"erro": f"Não achei {nome}#{tag} na região do seu cliente."}
        inv = self.get(f"/lol-summoner/v2/summoners/puuid/{puuid}") or {}
        dados = {"riot_id": _riot_id(inv) or f"{nome}#{tag}", "puuid": puuid,
                 "nivel": inv.get("summonerLevel"), "icone": inv.get("profileIconId"),
                 "elo": "", "pdl": None, "vitorias": 0, "derrotas": 0}
        ranque = self.get(f"/lol-ranked/v1/ranked-stats/{puuid}") or {}
        solo = (ranque.get("queueMap") or {}).get("RANKED_SOLO_5x5") or next(
            (q for q in ranque.get("queues", []) if q.get("queueType") == "RANKED_SOLO_5x5"), {})
        tier = (solo.get("tier") or "").upper()
        if tier and tier not in ("NONE", "UNRANKED"):
            nome_tier = TIERS_PT.get(tier, tier.title())
            div = solo.get("division") or ""
            dados["elo"] = nome_tier if tier in SEM_DIVISAO or div in ("", "NA") else f"{nome_tier} {div}"
            dados["pdl"] = solo.get("leaguePoints")
            dados["vitorias"], dados["derrotas"] = solo.get("wins", 0), solo.get("losses", 0)
        dados.update(self.historico_funcoes(puuid))
        return dados

    def historico_funcoes(self, puuid: str, partidas: int = 40) -> dict:
        """Conta funções e campeões nas últimas partidas de Summoner's Rift."""
        h = self.get(f"/lol-match-history/v1/products/lol/{puuid}/matches"
                     f"?begIndex=0&endIndex={partidas - 1}") or {}
        jogos = (h.get("games") or {}).get("games") or []
        funcoes: Counter = Counter()
        campeoes: dict[str, Counter] = {}
        for jogo in jogos:
            if jogo.get("mapId") not in (None, 11) or jogo.get("queueId") in FILAS_IGNORADAS:
                continue
            partes = jogo.get("participants") or []
            if not partes:
                continue
            p = partes[0]  # no histórico do jogador, ele vem primeiro (ou sozinho)
            ids = jogo.get("participantIdentities") or []
            for ident in ids:
                if (ident.get("player") or {}).get("puuid") == puuid:
                    pid = ident.get("participantId")
                    p = next((x for x in partes if x.get("participantId") == pid), p)
            funcao = _funcao(p)
            if not funcao:
                continue
            funcoes[funcao] += 1
            campeoes.setdefault(funcao, Counter())[p.get("championId")] += 1
        return {"funcoes": funcoes, "campeoes": campeoes, "partidas_lidas": sum(funcoes.values())}

    # -- fila ----------------------------------------------------------------
    def aceitar_fila(self) -> bool:
        """Aceita a partida encontrada. Retorna True se aceitou agora."""
        rc = self.get("/lol-matchmaking/v1/ready-check")
        if rc and rc.get("state") == "InProgress" and rc.get("playerResponse") == "None":
            r = self.pedir("POST", "/lol-matchmaking/v1/ready-check/accept")
            return r is not None and r.status_code in (200, 204)
        return False

    # -- runas ---------------------------------------------------------------
    def importar_runas(self, primaria: int, secundaria: int, perks: list[int],
                       nome: str = NOME_PAGINA) -> str:
        """Substitui a página "Quíron" (ou cria). Retorna mensagem do resultado."""
        paginas = self.get("/lol-perks/v1/pages") or []
        for p in paginas:
            if p.get("name", "").startswith((NOME_PAGINA,) + NOMES_ANTIGOS) and p.get("isDeletable", True):
                self.pedir("DELETE", f"/lol-perks/v1/pages/{p['id']}")
        corpo = {"name": nome, "primaryStyleId": primaria, "subStyleId": secundaria,
                 "selectedPerkIds": perks, "current": True}
        r = self.pedir("POST", "/lol-perks/v1/pages", json=corpo)
        if r is not None and r.status_code in (200, 201):
            return "ok"
        # sem espaço: troca a página atual, se for editável
        atual = self.get("/lol-perks/v1/currentpage")
        if atual and atual.get("isEditable") and atual.get("isDeletable", True):
            self.pedir("DELETE", f"/lol-perks/v1/pages/{atual['id']}")
            r = self.pedir("POST", "/lol-perks/v1/pages", json=corpo)
            if r is not None and r.status_code in (200, 201):
                return f"ok (substituiu a página “{atual.get('name')}”)"
        return "sem espaço para páginas de runas"

    # -- itens ---------------------------------------------------------------
    def importar_itens(self, chave_campeao: int, nome_campeao: str,
                       blocos: list[tuple[str, list[str]]]) -> bool:
        """Cria o conjunto de itens "Quíron - <campeão>" para Summoner's Rift."""
        eu = self.get("/lol-summoner/v1/current-summoner")
        if not eu:
            return False
        sid = eu.get("summonerId")
        atual = self.get(f"/lol-item-sets/v1/item-sets/{sid}/sets") or {}
        sets = [s for s in atual.get("itemSets", [])
                if not any(s.get("title", "").startswith(f"{n} - {nome_campeao}")
                           for n in (NOME_PAGINA,) + NOMES_ANTIGOS)]
        sets.insert(0, {
            "title": f"{NOME_PAGINA} - {nome_campeao}",
            "associatedChampions": [chave_campeao],
            "associatedMaps": [11],
            "blocks": [{"type": titulo, "items": [{"id": str(i), "count": 1} for i in ids]}
                       for titulo, ids in blocos if ids],
            "map": "any", "mode": "any", "preferredItemSlots": [], "sortrank": 0,
            "startedFrom": "blank", "type": "custom",
            "uid": f"quiron-{chave_campeao}",
        })
        corpo = {"accountId": atual.get("accountId", eu.get("accountId")),
                 "itemSets": sets, "timestamp": atual.get("timestamp", 0)}
        r = self.pedir("PUT", f"/lol-item-sets/v1/item-sets/{sid}/sets", json=corpo)
        return r is not None and r.status_code in (200, 201, 204)
