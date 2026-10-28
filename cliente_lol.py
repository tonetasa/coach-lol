"""Integração com o cliente do League of Legends (API local do lobby, "LCU").

Faz três coisas fora da partida:
  - aceita a fila automaticamente;
  - cria/atualiza a página de runas "Quíron" do campeão escolhido;
  - cria o conjunto de itens "Quíron" do campeão (aparece na loja).

A Riot diz que essa API não tem suporte oficial para apps de terceiros: ela
funciona e é usada por apps conhecidos, mas pode mudar sem aviso.
"""

from pathlib import Path

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
