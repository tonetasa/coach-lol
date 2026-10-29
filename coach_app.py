"""
Quíron — app para Windows
============================

Ponto de entrada do app. Abre a interface nova (quiron_web.py + pasta ui/,
em HTML dentro do WebView2 do Windows). Este arquivo também guarda a
interface clássica (CustomTkinter), usada quando o WebView2 não existe ou
com o parâmetro --interface-classica.

Rodar sem o instalador:   pythonw coach_app.py
Gerar o instalador:       criar_instalador.bat
"""

import os
import queue
import sys
import threading
import webbrowser
from pathlib import Path

import customtkinter as ctk

import atualizacao
import coach_lol as coach
import funcoes_comuns
import registro
import relatorio_lol as relatorio
from versao import AVISO, VERSAO

URL_BUILDS = "https://claude.ai/artifact/DNv4gfXzbRkregwhFNtQ4N"
NOME_REGISTRO = "Quiron"
NOME_REGISTRO_ANTIGO = "CoachLoL"
PASTA_RECURSOS = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))

# Paleta (combina com o ícone). Pares = (tema claro, tema escuro)
AZUL = ("#2a78d6", "#3987e5")
AZUL_HOVER = ("#1f63b5", "#2a78d6")
VERMELHO = ("#c4372f", "#b8423b")
VERMELHO_HOVER = ("#a32d26", "#9c3730")
OURO = "#e9a419"
VERDE = "#4ac26b"
CINZA = ("#8a8984", "#6f6e69")
FUNDO = ("#f4f3ef", "#131417")
CARTAO = ("#ffffff", "#1c1d21")
BORDA = ("#e3e1da", "#2a2b30")
TEXTO = ("#0b0b0b", "#eeedea")
TEXTO2 = ("#52514e", "#a9a8a2")

# Configurações com interruptor: (chave, título, descrição, invertido?)
CLIENTE = [
    ("aceitar_fila", "Aceitar a fila automaticamente",
     "Aceita a partida assim que ela é encontrada.", False),
    ("ajuda_selecao", "Ajuda na seleção de campeões",
     "Seu histórico na função e notas sobre os inimigos.", False),
    ("sugerir_escolha", "Melhor escolha no draft",
     "Na sua vez: o campeão do seu pool que mais combina com o draft.", False),
    ("analise_draft", "Análise do draft",
     "Quando o draft fecha: pontos positivos e de atenção do seu time.", False),
    ("importar_runas", "Importar runas",
     "Cria a página “Quíron” do campeão escolhido.", False),
    ("importar_itens", "Importar itens",
     "Cria o conjunto de itens “Quíron” que aparece na loja.", False),
    ("importar_feiticos", "Trocar feitiços de invocador",
     "Usa os feitiços da build (mantém o Flash na tecla de sempre).", False),
]

INICIO = [
    ("analisar_composicao", "Build e ajustes no início",
     "Fala a build e as opções contra o time inimigo.", False),
    ("plano_pre_partida", "Plano de jogo",
     "Fase forte, iniciação, ameaças e sua rota, na tela de carregamento.", False),
    ("rota_selva", "Rota inicial da selva",
     "Quando você for o caçador: por onde começar e onde terminar.", False),
]

FUNCOES = [
    ("somente_antes_e_depois", "Avisos durante a partida",
     "Desligado: só build no início e resumo no fim.", True),
    ("avisar_diferenca_ouro", "Diferença de ouro dos times",
     "Pelos itens no placar, quando muda de faixa (2 mil).", False),
    ("avisar_cacador_inimigo", "Caçador inimigo",
     "Quando ele aparece em abates e objetivos.", False),
    ("avisar_recompensa", "Recompensa",
     "Quem provavelmente está valendo ouro extra.", False),
    ("avisar_proximo_item", "Ouro para o próximo item",
     "Quanto falta para o próximo item da build.", False),
    ("avisar_cs_baixo", "CS por minuto baixo",
     "Fora do suporte, quando ficar abaixo do mínimo.", False),
    ("avisar_objetivos", "Objetivos neutros nascendo",
     "1 minuto antes de dragão, vastilarvas, arauto e barão (pelos tempos padrão).", False),
]


# ---------------------------------------------------------------------------
# Iniciar com o Windows (registro do usuário, sem administrador)
# ---------------------------------------------------------------------------
def comando_inicializacao() -> str:
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}" --minimizado'
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    return f'"{pythonw}" "{Path(__file__).resolve()}" --minimizado'


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
        try:  # entrada da versão antiga (Coach LoL)
            winreg.DeleteValue(k, NOME_REGISTRO_ANTIGO)
        except FileNotFoundError:
            pass
    return True


class Icones:
    """Imagens do jogo (campeões, itens, runas, fragmentos).

    Baixa em segundo plano, guarda em cache no PC e entrega CTkImage pronta,
    com cantos arredondados e, se pedido, "apagada" (cinza e transparente),
    como as runas não escolhidas no cliente do LoL.
    """

    def __init__(self, fila: queue.Queue):
        from concurrent.futures import ThreadPoolExecutor
        self.fila = fila
        self.cache: dict[tuple, ctk.CTkImage] = {}
        self.pendentes: dict[tuple, list] = {}
        self.pool = ThreadPoolExecutor(max_workers=8)
        self.trava = threading.Lock()

    def _carregar(self, tipo, ident, tamanho, apagada, raio):
        from PIL import Image, ImageDraw, ImageOps
        arq = coach.arquivo_imagem(tipo, ident)
        img = Image.open(arq).convert("RGBA").resize((tamanho * 2, tamanho * 2), Image.LANCZOS)
        if raio:
            mascara = Image.new("L", img.size, 0)
            ImageDraw.Draw(mascara).rounded_rectangle((0, 0, *img.size), radius=raio * 2,
                                                      fill=255)
            alfa = Image.composite(img.getchannel("A"), mascara, mascara)
            img.putalpha(alfa)
        if apagada:
            alfa = img.getchannel("A").point(lambda a: int(a * 0.35))
            img = ImageOps.grayscale(img.convert("RGB")).convert("RGBA")
            img.putalpha(alfa)
        return ctk.CTkImage(light_image=img, dark_image=img, size=(tamanho, tamanho))

    def vazio(self, tamanho: int):
        """Quadrado cinza do tamanho do ícone, enquanto ele baixa."""
        chave = ("", "", tamanho)
        if chave not in self.cache:
            from PIL import Image, ImageDraw
            img = Image.new("RGBA", (tamanho * 2, tamanho * 2), (0, 0, 0, 0))
            ImageDraw.Draw(img).rounded_rectangle((0, 0, *img.size), radius=tamanho // 3,
                                                  fill=(46, 47, 52, 255))
            self.cache[chave] = ctk.CTkImage(light_image=img, dark_image=img,
                                             size=(tamanho, tamanho))
        return self.cache[chave]

    def imagem(self, tipo: str, ident: str, tamanho: int, ao_carregar=None,
               apagada: bool = False, raio: int | None = None):
        """CTkImage se já está no PC; senão baixa e chama ao_carregar() depois."""
        if raio is None:
            raio = {"campeao": tamanho // 3, "item": max(3, tamanho // 8)}.get(tipo, 0)
        chave = (tipo, ident, tamanho, apagada, raio)
        if chave in self.cache:
            return self.cache[chave]
        arq = coach.arquivo_imagem(tipo, ident)
        if arq.exists():
            try:
                self.cache[chave] = self._carregar(tipo, ident, tamanho, apagada, raio)
                return self.cache[chave]
            except Exception:  # noqa: BLE001 (arquivo corrompido: baixa de novo)
                arq.unlink(missing_ok=True)
        pend = (tipo, ident)
        with self.trava:
            ja_baixando = pend in self.pendentes
            self.pendentes.setdefault(pend, [])
            if ao_carregar:
                self.pendentes[pend].append(ao_carregar)
        if not ja_baixando:
            self.pool.submit(self._baixar, tipo, ident)
        return None

    def obter(self, cid: str, tamanho: int, ao_carregar=None):
        """Atalho para o ícone de campeão."""
        return self.imagem("campeao", cid, tamanho, ao_carregar)

    def _baixar(self, tipo: str, ident: str):
        coach.baixar_imagem(tipo, ident)
        with self.trava:
            chamadas = self.pendentes.pop((tipo, ident), [])
        if chamadas:
            self.fila.put(("icone", chamadas))

    def pre_carregar(self, cids):
        for cid in cids:
            if not coach.arquivo_imagem("campeao", cid).exists():
                self.obter(cid, 48)

    def rotulo(self, pai, tipo, ident, tamanho, apagada=False, **kw):
        """CTkLabel com a imagem (mostra um quadrado cinza até baixar)."""
        lb = ctk.CTkLabel(pai, text="", width=tamanho, height=tamanho, **kw)

        def pronto():
            img = self.imagem(tipo, ident, tamanho, apagada=apagada)
            if img and lb.winfo_exists():
                lb.configure(image=img)

        img = self.imagem(tipo, ident, tamanho, ao_carregar=pronto, apagada=apagada)
        lb.configure(image=img or self.vazio(tamanho))
        return lb


class SaidaParaFila:
    """Substitui o print: manda o texto para a janela."""

    def __init__(self, fila: queue.Queue):
        self.fila = fila

    def write(self, texto):
        if texto:
            self.fila.put(("log", texto))
            if texto.strip():
                registro.log.info(texto.strip())

    def flush(self):
        pass


# ---------------------------------------------------------------------------
class App(ctk.CTk):
    def __init__(self, minimizado: bool = False):
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        super().__init__(fg_color=FUNDO)

        self.fila: queue.Queue = queue.Queue()
        self.parar = threading.Event()
        self.thread: threading.Thread | None = None
        self.voz: coach.Voz | None = None
        self.ouvido = None
        self.bandeja = None
        self.itens = coach.Itens({})
        self.campeoes: dict = {}
        self.icones = Icones(self.fila)
        self.runas: dict = {}
        self.builds_abertas: set[str] = set()

        self.migrados = coach.migrar_dados_antigos() if getattr(sys, "frozen", False) else 0
        if not coach.CONFIG.get("chave_ia_apagada"):
            threading.Thread(target=coach.apagar_chave_ia_antiga, daemon=True).start()
            coach.salvar_config({"chave_ia_apagada": True})
        registro.configurar(coach.BASE, VERSAO)
        ja_usava = coach.CONFIG_ARQ.exists()   # quem já usava antes do perfil existir
        coach.carregar_config()
        self.precisa_perfil = not coach.perfil()["funcoes"]
        self.perfil_sugerido = coach.PERFIL_ANTIGO if (self.precisa_perfil and ja_usava) else None
        coach.carregar_builds()
        self.info_atualizacao: dict | None = None
        sys.stdout = SaidaParaFila(self.fila)
        sys.stderr = SaidaParaFila(self.fila)

        self.title(f"Quíron {VERSAO}")
        self.geometry("760x660")
        self.minsize(640, 560)
        try:
            self.iconbitmap(default=str(PASTA_RECURSOS / "icone.ico"))
        except Exception:  # noqa: BLE001 (Linux não aceita .ico)
            pass

        self.f_titulo = ctk.CTkFont("Segoe UI", 22, "bold")
        self.f_sub = ctk.CTkFont("Segoe UI", 14, "bold")
        self.f_txt = ctk.CTkFont("Segoe UI", 13)
        self.f_peq = ctk.CTkFont("Segoe UI", 11)
        self.f_num = ctk.CTkFont("Segoe UI", 26, "bold")

        self._montar()
        self.protocol("WM_DELETE_WINDOW", self.ao_fechar)
        self.after(100, self._ler_fila)
        threading.Thread(target=self._carregar_itens, daemon=True).start()
        threading.Thread(target=self._verificacoes, daemon=True).start()
        self._criar_bandeja()

        if minimizado and self.bandeja:
            self.after(50, self.withdraw)
        if minimizado or coach.CONFIG["iniciar_coach_ao_abrir"]:
            self.after(400, self.iniciar)

    def report_callback_exception(self, exc, val, tb):
        import traceback
        registro.log.error("Erro na janela:\n%s", "".join(traceback.format_exception(exc, val, tb)))
        self._escrever(f"Erro: {val}. Detalhes no log (Configurações → Sobre).\n")

    # =====================================================================
    # Montagem
    # =====================================================================
    def _cartao(self, pai, **kw):
        return ctk.CTkFrame(pai, fg_color=CARTAO, border_color=BORDA, border_width=1,
                            corner_radius=12, **kw)

    def _botao_secundario(self, pai, texto, comando, largura=120):
        return ctk.CTkButton(pai, text=texto, width=largura, fg_color="transparent",
                             border_width=1, border_color=BORDA, text_color=TEXTO,
                             hover_color=BORDA, command=comando)

    def _montar(self):
        topo = ctk.CTkFrame(self, fg_color="transparent")
        topo.pack(fill="x", padx=20, pady=(16, 0))
        ctk.CTkLabel(topo, text="Quíron", font=self.f_titulo).pack(side="left")
        ctk.CTkLabel(topo, text=f"  v{VERSAO}", font=self.f_peq,
                     text_color=TEXTO2).pack(side="left", pady=(8, 0))

        ctk.CTkLabel(self, text=AVISO, font=self.f_peq, text_color=CINZA,
                     wraplength=700, justify="left").pack(side="bottom", anchor="w",
                                                         padx=20, pady=(0, 10))

        # faixa de "versão nova disponível" (aparece só quando há atualização)
        self.faixa = ctk.CTkFrame(self, fg_color=("#fff4dc", "#3a2e12"), corner_radius=10)
        self.faixa_txt = ctk.CTkLabel(self.faixa, text="", font=self.f_txt,
                                      text_color=TEXTO)
        self.faixa_txt.pack(side="left", padx=14, pady=8)
        self.faixa_bt = ctk.CTkButton(self.faixa, text="Atualizar agora", width=130,
                                      fg_color=OURO, hover_color="#c98a10",
                                      text_color="#1a1a19", command=self._atualizar_app)
        self.faixa_bt.pack(side="right", padx=(6, 10), pady=6)
        self._botao_secundario(self.faixa, "Novidades", self._ver_novidades, 100).pack(
            side="right", pady=6)

        self.abas = ctk.CTkTabview(self, fg_color="transparent", anchor="w",
                                   segmented_button_selected_color=AZUL,
                                   segmented_button_selected_hover_color=AZUL_HOVER,
                                   command=self._trocou_aba)
        self.abas.pack(fill="both", expand=True, padx=12, pady=(0, 4))
        self._abas_widget = self.abas
        for nome in ("Coach", "Builds", "Relatório", "Configurações"):
            self.abas.add(nome)
        self._aba_coach(self.abas.tab("Coach"))
        self._aba_builds(self.abas.tab("Builds"))
        self._aba_relatorio(self.abas.tab("Relatório"))
        self._aba_config(self.abas.tab("Configurações"))

    # ---- Coach ------------------------------------------------------------
    def _aba_coach(self, aba):
        card = self._cartao(aba)
        card.pack(fill="x", padx=4, pady=(4, 12))
        esq = ctk.CTkFrame(card, fg_color="transparent")
        esq.pack(side="left", fill="x", expand=True, padx=18, pady=16)
        linha = ctk.CTkFrame(esq, fg_color="transparent")
        linha.pack(anchor="w")
        self.ponto = ctk.CTkLabel(linha, text="●", font=ctk.CTkFont(size=18),
                                  text_color=CINZA)
        self.ponto.pack(side="left", padx=(0, 8))
        self.estado = ctk.CTkLabel(linha, text="Parado", font=self.f_sub)
        self.estado.pack(side="left")
        self.dica = ctk.CTkLabel(esq, text="Inicie o coach e deixe o app aberto enquanto joga.",
                                 font=self.f_txt, text_color=TEXTO2, justify="left",
                                 wraplength=440)
        self.dica.pack(anchor="w", pady=(6, 0))
        self.botao = ctk.CTkButton(card, text="Iniciar coach", width=170, height=44,
                                   font=self.f_sub, fg_color=AZUL, hover_color=AZUL_HOVER,
                                   corner_radius=10, command=self.alternar)
        self.botao.pack(side="right", padx=18)

        ctk.CTkLabel(aba, text="Avisos", font=self.f_sub).pack(anchor="w", padx=6)
        self.log = ctk.CTkTextbox(aba, font=ctk.CTkFont("Consolas", 12), fg_color=CARTAO,
                                  border_color=BORDA, border_width=1, corner_radius=12,
                                  wrap="word")
        self.log.pack(fill="both", expand=True, padx=4, pady=(6, 4))
        self.log.configure(state="disabled")
        self._escrever(f"Seus dados ficam em: {coach.BASE}\n")
        if self.migrados:
            self._escrever(f"{self.migrados} partidas antigas foram copiadas da versão anterior.\n")

    # ---- Builds -----------------------------------------------------------
    def _aba_builds(self, aba):
        cab = ctk.CTkFrame(aba, fg_color="transparent")
        cab.pack(fill="x", padx=4, pady=(4, 8))
        self.info_builds = ctk.CTkLabel(cab, text="", font=self.f_sub)
        self.info_builds.pack(side="left")
        self._botao_secundario(cab, "Documento", lambda: webbrowser.open(URL_BUILDS),
                               100).pack(side="right")
        self._botao_secundario(cab, "Buscar atualização", self._buscar_builds, 150).pack(
            side="right", padx=6)
        ctk.CTkButton(cab, text="+ Campeão", width=100, fg_color=AZUL, hover_color=AZUL_HOVER,
                      command=lambda: self._editar_build(None)).pack(side="right")
        self.lista_builds = ctk.CTkScrollableFrame(aba, fg_color="transparent")
        self.lista_builds.pack(fill="both", expand=True)
        self._preencher_builds()

    def _preencher_builds(self):
        info = coach.INFO_BUILDS
        extra = f" · {info['fonte']}" + (f", {info['atualizado']}" if info.get("atualizado") else "")
        self.info_builds.configure(text=f"Patch {info['patch']}{extra}")
        for w in self.lista_builds.winfo_children():
            w.destroy()
        nomes_funcao = {"JUNGLE": "Caçador", "UTILITY": "Suporte", "TOP": "Topo",
                        "MIDDLE": "Meio", "BOTTOM": "Atirador"}
        stats = coach.estatisticas_pool()
        pool = coach.todos_do_pool()
        outros = [c for c in coach.BUILDS if c not in pool]
        if not pool:
            ctk.CTkLabel(self.lista_builds, text="Configure seu pool em Configurações → Perfil "
                         "para ver as builds dos seus campeões aqui.", font=self.f_txt,
                         text_color=TEXTO2).pack(anchor="w", padx=6, pady=(0, 6))
        for titulo, lista in (("Seu pool", pool), ("Outras builds", outros)):
            if not lista:
                continue
            ctk.CTkLabel(self.lista_builds, text=titulo, font=self.f_sub).pack(
                anchor="w", padx=6, pady=(8, 2))
            for cid in lista:
                b = coach.obter_build(cid, self.campeoes)
                if not b:
                    continue
                card = self._cartao(self.lista_builds)
                card.pack(fill="x", padx=2, pady=4)
                topo = ctk.CTkFrame(card, fg_color="transparent")
                topo.pack(fill="x", padx=16, pady=(10, 2))
                self._icone_label(topo, cid, 36).pack(side="left", padx=(0, 10))
                ctk.CTkLabel(topo, text=self._nome_campeao(cid), font=self.f_sub).pack(side="left")
                ctk.CTkLabel(topo, text=f"   {nomes_funcao.get(b['funcao'], b['funcao'])}",
                             font=self.f_peq, text_color=TEXTO2).pack(side="left", pady=(2, 0))
                selo = ("personalizada" if b.get("personalizado") else
                        "estimativa" if b.get("estimativa") else
                        "genérica" if b.get("generica") else "")
                if selo:
                    ctk.CTkLabel(topo, text=f"  {selo}", font=self.f_peq,
                                 text_color=OURO if selo == "personalizada" else CINZA).pack(
                        side="left", pady=(2, 0))
                aberto = cid in self.builds_abertas
                self._botao_secundario(topo, "Runas ▴" if aberto else "Runas ▾",
                                       lambda c=cid: self._alternar_runas(c), 80).pack(
                    side="right", padx=(6, 0))
                self._botao_secundario(topo, "Editar", lambda c=cid: self._editar_build(c),
                                       70).pack(side="right")
                if b.get("personalizado"):
                    self._botao_secundario(topo, "Restaurar", lambda c=cid: self._restaurar(c),
                                           80).pack(side="right", padx=6)
                if b.get("generica"):
                    self._botao_secundario(topo, "Pedir build",
                                           lambda c=cid: self._pedir_build(c), 100).pack(
                        side="right", padx=6)
                v, d = stats.get(cid, (0, 0))
                if v + d:
                    ctk.CTkLabel(topo, text=f"{round(100 * v / (v + d))}% em {v + d}   ",
                                 font=self.f_peq, text_color=OURO).pack(side="right")
                self._linha_itens(card, b)
                if aberto:
                    self._pagina_runas(card, b)

    # ---- itens e página de runas (visual do cliente) -------------------------
    def _alternar_runas(self, cid):
        self.builds_abertas ^= {cid}
        self._preencher_builds()

    def _linha_itens(self, card, b):
        linha = ctk.CTkFrame(card, fg_color="transparent")
        linha.pack(fill="x", padx=14, pady=(2, 12))
        blocos = []
        if b.get("inicio"):
            blocos.append(("Início", b["inicio"][:1]))
        blocos.append(("", b["itens"]))
        for titulo, itens in blocos:
            for n, nome in enumerate(itens):
                iid = self.itens.id(nome)
                cel = ctk.CTkFrame(linha, fg_color="transparent")
                cel.pack(side="left", padx=(0, 2))
                if iid:
                    self.icones.rotulo(cel, "item", iid, 40).pack()
                rotulo = self.itens.nome_pt(nome)
                ctk.CTkLabel(cel, text=rotulo if len(rotulo) <= 14 else rotulo[:13] + "…",
                             font=self.f_peq, text_color=TEXTO2, width=92).pack()
                if titulo:
                    ctk.CTkLabel(linha, text="|", text_color=BORDA, font=self.f_sub).pack(
                        side="left", padx=6, pady=(0, 18))
                elif n < len(itens) - 1:
                    ctk.CTkLabel(linha, text="›", text_color=CINZA,
                                 font=ctk.CTkFont(size=20)).pack(side="left", pady=(0, 18))

    def _pagina_runas(self, card, b):
        """Página de runas como no cliente: escolhidas acesas, as outras apagadas."""
        pag, runas = b.get("pagina"), self.runas
        if not pag or not runas.get("detalhe"):
            ctk.CTkLabel(card, text="Página de runas indisponível para esta build.",
                         font=self.f_peq, text_color=CINZA).pack(anchor="w", padx=16, pady=(0, 12))
            return
        escolhidas = {runas["runas"].get(n) for n in pag["runas"] + pag["runas2"]}
        arvores = {a["id"]: a for a in runas["detalhe"]}
        prim = arvores.get(runas["arvores"].get(pag["primaria"]))
        sec = arvores.get(runas["arvores"].get(pag["secundaria"]))
        if not prim or not sec:
            return
        painel = ctk.CTkFrame(card, fg_color=FUNDO, corner_radius=10)
        painel.pack(fill="x", padx=14, pady=(0, 14))

        def coluna(arvore, fileiras, tam_chave):
            col = ctk.CTkFrame(painel, fg_color="transparent")
            col.pack(side="left", anchor="n", padx=(14, 18), pady=12)
            cab = ctk.CTkFrame(col, fg_color="transparent")
            cab.pack(anchor="w", pady=(0, 6))
            self.icones.rotulo(cab, "runa", arvore["icone"], 22).pack(side="left", padx=(0, 6))
            ctk.CTkLabel(cab, text=arvore["nome"], font=self.f_sub).pack(side="left")
            nomes = []
            for i, fileira in fileiras:
                lin = ctk.CTkFrame(col, fg_color="transparent")
                lin.pack(anchor="w", pady=3)
                tam = tam_chave if i == 0 else 30
                for r in fileira:
                    ativa = r["id"] in escolhidas
                    if ativa:
                        nomes.append(r["nome"])
                    self.icones.rotulo(lin, "runa", r["icone"], tam, apagada=not ativa).pack(
                        side="left", padx=4)
            ctk.CTkLabel(col, text="\n".join(nomes), font=self.f_peq, text_color=TEXTO2,
                         justify="left").pack(anchor="w", pady=(6, 0))

        coluna(prim, list(enumerate(prim["fileiras"])), 44)
        coluna(sec, [(i, f) for i, f in enumerate(sec["fileiras"]) if i > 0], 30)

        col = ctk.CTkFrame(painel, fg_color="transparent")
        col.pack(side="left", anchor="n", padx=(4, 14), pady=12)
        ctk.CTkLabel(col, text="Fragmentos", font=self.f_sub).pack(anchor="w", pady=(0, 6))
        nomes = []
        for linha_opcoes, escolhido in zip(coach.LINHAS_FRAGMENTOS, pag["fragmentos"]):
            lin = ctk.CTkFrame(col, fg_color="transparent")
            lin.pack(anchor="w", pady=4)
            for op in linha_opcoes:
                self.icones.rotulo(lin, "fragmento", op, 22, apagada=op != escolhido,
                                   fg_color=BORDA if op == escolhido else "transparent",
                                   corner_radius=11).pack(side="left", padx=4)
            nomes.append(coach.NOME_FRAGMENTO.get(escolhido, escolhido))
        ctk.CTkLabel(col, text="\n".join(nomes), font=self.f_peq, text_color=TEXTO2,
                     justify="left").pack(anchor="w", pady=(6, 0))
        if b.get("feiticos"):
            ctk.CTkLabel(col, text="Feitiços: " + " + ".join(
                {"Flash": "Flash", "Smite": "Golpear", "Heal": "Curar", "Ignite": "Incendiar",
                 "Exhaust": "Exaustão", "Barrier": "Barreira", "Teleport": "Teleporte",
                 "Cleanse": "Purificar", "Ghost": "Fantasma"}.get(f, f) for f in b["feiticos"]),
                font=self.f_peq, text_color=TEXTO2).pack(anchor="w", pady=(8, 0))

    def _pedir_build(self, cid):
        from urllib.parse import quote
        nome = self._nome_campeao(cid)
        b = coach.obter_build(cid, self.campeoes) or {}
        corpo = (f"Campeão: {nome} ({cid})\nFunção: {b.get('funcao', '?')}\n\n"
                 "Pedido feito pelo app Quíron. A tarefa semanal pesquisa a build e adiciona "
                 "ao builds.json.")
        webbrowser.open(f"https://github.com/{coach.REPO_GITHUB}/issues/new?title="
                        f"{quote('Build: ' + nome)}&body={quote(corpo)}")
        self._escrever(f"Abrindo o pedido de build para {nome} no GitHub "
                       "(precisa estar logado). A build chega na próxima atualização semanal.\n")

    def _icone_label(self, pai, cid, tamanho):
        """Label com o ícone do campeão (aparece assim que terminar de baixar)."""
        rotulo = ctk.CTkLabel(pai, text="", width=tamanho, height=tamanho,
                              fg_color=BORDA, corner_radius=tamanho // 3)

        def pronto():
            img = self.icones.obter(cid, tamanho)
            if img and rotulo.winfo_exists():
                rotulo.configure(image=img, fg_color="transparent")

        img = self.icones.obter(cid, tamanho, ao_carregar=pronto)
        if img:
            rotulo.configure(image=img, fg_color="transparent")
        return rotulo

    def _nome_campeao(self, cid):
        return self.campeoes.get(cid, {}).get("name", cid)

    def _editar_build(self, cid):
        if not self.itens:
            self._escrever("Aguarde: ainda carregando a lista de itens.\n")
            return
        EditorBuild(self, cid)

    def _restaurar(self, cid):
        coach.restaurar_build(cid)
        self._preencher_builds()
        self._escrever(f"Build de {cid} restaurada.\n")

    def _buscar_builds(self):
        self.info_builds.configure(text="Buscando builds...")
        threading.Thread(target=lambda: self._baixar_builds(manual=True), daemon=True).start()

    def _baixar_builds(self, manual=False):
        try:
            patch = coach.baixar_builds()
            if patch:
                self.fila.put(("log", f"Builds atualizadas para o patch {patch}.\n"))
            elif manual:
                self.fila.put(("log", "As builds já estão em dia.\n"))
        except Exception as e:  # noqa: BLE001
            registro.erro("Falha ao baixar builds", e)
            if manual:
                self.fila.put(("log", "Não consegui buscar as builds agora "
                                      "(sem internet ou repositório indisponível).\n"))
        self.fila.put(("builds", None))

    # ---- Relatório --------------------------------------------------------
    def _aba_relatorio(self, aba):
        cab = ctk.CTkFrame(aba, fg_color="transparent")
        cab.pack(fill="x", padx=4, pady=(4, 10))
        self.periodo = ctk.CTkSegmentedButton(cab, values=["7 dias", "30 dias", "Tudo"],
                                              selected_color=AZUL,
                                              selected_hover_color=AZUL_HOVER,
                                              command=lambda _: self._atualizar_relatorio())
        self.periodo.set("7 dias")
        self.periodo.pack(side="left")
        ctk.CTkButton(cab, text="Relatório completo com gráficos", fg_color=AZUL,
                      hover_color=AZUL_HOVER, command=self._abrir_relatorio).pack(side="right")

        self.tiles = ctk.CTkFrame(aba, fg_color="transparent")
        self.tiles.pack(fill="x")
        self.tabela = ctk.CTkScrollableFrame(aba, fg_color=CARTAO, border_color=BORDA,
                                             border_width=1, corner_radius=12)
        self.tabela.pack(fill="both", expand=True, padx=4, pady=(12, 4))
        self._atualizar_relatorio()

    def _dias(self) -> int:
        return {"7 dias": 7, "30 dias": 30, "Tudo": 0}[self.periodo.get()]

    def _atualizar_relatorio(self):
        dados = relatorio.montar_dados(relatorio.ler_partidas(self._dias()))
        r = dados["resumo"]

        def fmt(v, d=0):
            return "—" if v is None else f"{v:.{d}f}".replace(".", ",")

        for w in self.tiles.winfo_children():
            w.destroy()
        tiles = [("Partidas", str(r["partidas"]), f"{r['v']} vitórias · {r['d']} derrotas"),
                 ("Vitória", "—" if r["taxa"] is None else f"{r['taxa']}%", "das partidas"),
                 ("Part. em abates", "—" if r["kp"] is None else f"{fmt(r['kp'])}%",
                  "meta: 50% ou mais"),
                 ("Mortes antes dos 14", fmt(r["mortes14"], 1), "média por partida")]
        for i, (rot, val, det) in enumerate(tiles):
            t = self._cartao(self.tiles)
            t.grid(row=0, column=i, sticky="nsew", padx=4)
            self.tiles.grid_columnconfigure(i, weight=1, uniform="tile")
            ctk.CTkLabel(t, text=rot, font=self.f_peq, text_color=TEXTO2).pack(
                anchor="w", padx=14, pady=(10, 0))
            ctk.CTkLabel(t, text=val, font=self.f_num).pack(anchor="w", padx=14)
            ctk.CTkLabel(t, text=det, font=self.f_peq, text_color=CINZA).pack(
                anchor="w", padx=14, pady=(0, 10))

        for w in self.tabela.winfo_children():
            w.destroy()
        cols = ["Campeão", "Partidas", "V–D", "Vitória", "Part. abates", "Mortes <14"]
        for j, c in enumerate(cols):
            ctk.CTkLabel(self.tabela, text=c, font=self.f_peq, text_color=TEXTO2).grid(
                row=0, column=j, sticky="w" if j == 0 else "e", padx=12, pady=(8, 4))
            self.tabela.grid_columnconfigure(j, weight=1)
        if not dados["campeoes"]:
            ctk.CTkLabel(self.tabela, text="Nenhuma partida registrada neste período.",
                         font=self.f_txt, text_color=TEXTO2).grid(
                row=1, column=0, columnspan=len(cols), pady=24)
        for i, c in enumerate(dados["campeoes"], start=1):
            vals = [c["campeao"], str(c["partidas"]), f"{c['v']}–{c['d']}",
                    "—" if c["taxa"] is None else f"{c['taxa']}%",
                    "—" if c["kp"] is None else f"{fmt(c['kp'])}%", fmt(c["mortes14"], 1)]
            for j, v in enumerate(vals):
                ctk.CTkLabel(self.tabela, text=v, font=self.f_txt).grid(
                    row=i, column=j, sticky="w" if j == 0 else "e", padx=12, pady=3)

    def _abrir_relatorio(self):
        _, n = relatorio.gerar(self._dias(), abrir=True)
        self._escrever(f"Relatório aberto no navegador ({n} partidas).\n")

    # ---- Configurações ----------------------------------------------------
    def _aba_config(self, aba):
        rolagem = ctk.CTkScrollableFrame(aba, fg_color="transparent")
        rolagem.pack(fill="both", expand=True)

        def secao(titulo):
            ctk.CTkLabel(rolagem, text=titulo, font=self.f_sub).pack(
                anchor="w", padx=6, pady=(10, 4))
            c = self._cartao(rolagem)
            c.pack(fill="x", padx=2, pady=(0, 4))
            return c

        def interruptor(pai, titulo, desc, valor, ao_mudar):
            linha = ctk.CTkFrame(pai, fg_color="transparent")
            linha.pack(fill="x", padx=16, pady=7)
            txt = ctk.CTkFrame(linha, fg_color="transparent")
            txt.pack(side="left", fill="x", expand=True)
            ctk.CTkLabel(txt, text=titulo, font=self.f_txt).pack(anchor="w")
            if desc:
                ctk.CTkLabel(txt, text=desc, font=self.f_peq, text_color=TEXTO2,
                             justify="left", wraplength=540).pack(anchor="w")
            sw = ctk.CTkSwitch(linha, text="", progress_color=AZUL, width=46)
            sw.pack(side="right")
            sw.select() if valor else sw.deselect()
            sw.configure(command=lambda: ao_mudar(bool(sw.get())))
            return sw

        perf = secao("Perfil")
        linha = ctk.CTkFrame(perf, fg_color="transparent")
        linha.pack(fill="x", padx=16, pady=12)
        self.perfil_txt = ctk.CTkLabel(linha, text=coach.texto_perfil(), font=self.f_txt,
                                       wraplength=480, justify="left", anchor="w")
        self.perfil_txt.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(linha, text="Editar perfil", width=110, fg_color=AZUL,
                      hover_color=AZUL_HOVER, command=lambda: EditorPerfil(self)).pack(side="right")

        voz = secao("Voz")
        interruptor(voz, "Falar os avisos", "Usa uma voz instalada no Windows.",
                    coach.CONFIG["voz_ligada"], self._mudar_voz)
        self._linha_voz_windows(voz)
        sw = interruptor(voz, "Comandos de voz", "", coach.CONFIG["comandos_de_voz"],
                         lambda v: coach.salvar_config({"comandos_de_voz": v}))
        txt = sw.master.winfo_children()[0]
        self.chamada_desc = ctk.CTkLabel(txt, text="", font=self.f_peq, text_color=TEXTO2,
                                         justify="left", wraplength=440)
        self.chamada_desc.pack(anchor="w")
        self._botao_secundario(sw.master, "Palavra de chamada",
                               lambda: EditorChamada(self), 150).pack(side="right", padx=(0, 12))
        self._atualizar_chamada()
        interruptor(voz, "Microfone só durante a partida",
                    "Recomendado: microfone aberto deixa fones Bluetooth no modo “telefone” "
                    "e abaixa o som de outros apps (Spotify, Discord).",
                    coach.CONFIG["microfone_so_na_partida"],
                    lambda v: coach.salvar_config({"microfone_so_na_partida": v}))
        linha = ctk.CTkFrame(voz, fg_color="transparent")
        linha.pack(fill="x", padx=16, pady=(4, 12))
        txt = ctk.CTkFrame(linha, fg_color="transparent")
        txt.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(txt, text="Microfone dos comandos", font=self.f_txt).pack(anchor="w")
        ctk.CTkLabel(txt, text="Com fone Bluetooth, usar outro microfone (webcam, mesa) mantém "
                     "o som do fone limpo.", font=self.f_peq, text_color=TEXTO2,
                     wraplength=380, justify="left").pack(anchor="w")
        opcoes = ["Padrão do Windows"] + coach.listar_microfones()
        self.mic = ctk.CTkOptionMenu(linha, values=opcoes, fg_color=AZUL, button_color=AZUL_HOVER,
                                     width=220, dynamic_resizing=False,
                                     command=lambda v: coach.salvar_config(
                                         {"microfone": "" if v == "Padrão do Windows" else v}))
        self.mic.set(coach.CONFIG["microfone"] or "Padrão do Windows")
        self.mic.pack(side="right")

        def grupo(titulo, lista):
            c = secao(titulo)
            for chave, tit, desc, inv in lista:
                valor = (not coach.CONFIG[chave]) if inv else coach.CONFIG[chave]
                interruptor(c, tit, desc, valor,
                            lambda v, k=chave, i=inv: coach.salvar_config({k: (not v) if i else v}))

        grupo("Cliente do LoL (fila e seleção)", CLIENTE)
        grupo("Início da partida", INICIO)

        func = secao("Durante a partida")
        for chave, titulo, desc, inv in FUNCOES:
            valor = (not coach.CONFIG[chave]) if inv else coach.CONFIG[chave]
            interruptor(func, titulo, desc, valor,
                        lambda v, k=chave, i=inv: coach.salvar_config({k: (not v) if i else v}))

        app = secao("Aplicativo")
        interruptor(app, "Iniciar com o Windows",
                    "Abre minimizado na bandeja e já liga o coach.",
                    coach.CONFIG["iniciar_com_windows"], self._mudar_inicializacao)
        interruptor(app, "Minimizar para a bandeja ao fechar",
                    "O X esconde a janela; para sair, use o ícone perto do relógio.",
                    coach.CONFIG["minimizar_para_bandeja"],
                    lambda v: coach.salvar_config({"minimizar_para_bandeja": v}))
        interruptor(app, "Ligar o coach ao abrir o app", "",
                    coach.CONFIG["iniciar_coach_ao_abrir"],
                    lambda v: coach.salvar_config({"iniciar_coach_ao_abrir": v}))
        interruptor(app, "Avisar quando houver versão nova", "Consulta o GitHub ao abrir o app.",
                    coach.CONFIG["verificar_atualizacoes"],
                    lambda v: coach.salvar_config({"verificar_atualizacoes": v}))
        interruptor(app, "Baixar builds atualizadas",
                    "Busca as builds do patch novo ao abrir o app. Suas edições são mantidas.",
                    coach.CONFIG["builds_automaticas"],
                    lambda v: coach.salvar_config({"builds_automaticas": v}))


        pasta = secao("Pasta do League of Legends")
        linha = ctk.CTkFrame(pasta, fg_color="transparent")
        linha.pack(fill="x", padx=16, pady=12)
        self.pasta_var = ctk.StringVar(value=coach.CONFIG["pasta_lol"])
        ctk.CTkEntry(linha, textvariable=self.pasta_var, border_color=BORDA).pack(
            side="left", fill="x", expand=True, padx=(0, 8))
        self._botao_secundario(linha, "Procurar…", self._procurar, 100).pack(side="left")

        dados = secao("Seus dados")
        linha = ctk.CTkFrame(dados, fg_color="transparent")
        linha.pack(fill="x", padx=16, pady=12)
        ctk.CTkLabel(linha, text=str(coach.BASE), font=self.f_peq, text_color=TEXTO2,
                     wraplength=460, justify="left").pack(side="left", fill="x", expand=True)
        self._botao_secundario(linha, "Abrir pasta", self._abrir_pasta_dados, 100).pack(
            side="right")

        sobre = secao("Sobre")
        ctk.CTkLabel(sobre, text=f"Quíron {VERSAO}", font=self.f_sub).pack(
            anchor="w", padx=16, pady=(12, 0))
        ctk.CTkLabel(sobre, text=AVISO, font=self.f_peq, text_color=TEXTO2, wraplength=620,
                     justify="left").pack(anchor="w", padx=16, pady=(2, 8))
        bts = ctk.CTkFrame(sobre, fg_color="transparent")
        bts.pack(fill="x", padx=16, pady=(0, 14))
        self._botao_secundario(bts, "Abrir log de erros", self._abrir_log, 140).pack(
            side="left", padx=(0, 6))
        self._botao_secundario(bts, "Copiar diagnóstico", self._copiar_diagnostico, 150).pack(
            side="left", padx=(0, 6))
        self._botao_secundario(bts, "Verificar atualização",
                               lambda: threading.Thread(target=lambda: self._checar_versao(True),
                                                        daemon=True).start(), 160).pack(
            side="left", padx=(0, 6))
        self._botao_secundario(bts, "Projeto no GitHub",
                               lambda: webbrowser.open(atualizacao.PAGINA), 140).pack(side="left")

    # =====================================================================
    # Ações
    # =====================================================================
    def _trocou_aba(self):
        aba = self.abas.get()
        if aba == "Relatório":
            self._atualizar_relatorio()
        elif aba == "Builds":
            self._preencher_builds()

    def _carregar_itens(self):
        self.fila.put(("itens", coach.carregar_itens()))
        self.fila.put(("campeoes", coach.carregar_campeoes()))
        self.fila.put(("runas", coach.carregar_runas()))

    def _verificacoes(self):
        if coach.CONFIG["builds_automaticas"]:
            self._baixar_builds()
        if coach.CONFIG["verificar_atualizacoes"]:
            self._checar_versao(False)

    def _checar_versao(self, manual):
        try:
            info = atualizacao.verificar(VERSAO)
        except Exception as e:  # noqa: BLE001
            registro.erro("Falha ao verificar atualização", e)
            info = None
            if manual:
                self.fila.put(("log", "Não consegui verificar atualizações agora.\n"))
                return
        if info:
            self.fila.put(("atualizacao", info))
        elif manual:
            self.fila.put(("log", f"Você já está na versão mais recente ({VERSAO}).\n"))

    def _mostrar_faixa(self, info):
        self.info_atualizacao = info
        self.faixa_txt.configure(text=f"Versão {info['versao']} disponível "
                                      f"(você tem a {VERSAO}).")
        self.faixa.pack(fill="x", padx=20, pady=(8, 0), before=self._abas_widget)
        if not info.get("url"):
            self.faixa_bt.configure(text="Baixar", command=self._ver_novidades)

    def _ver_novidades(self):
        if self.info_atualizacao:
            webbrowser.open(self.info_atualizacao["pagina"])

    def _atualizar_app(self):
        info = self.info_atualizacao
        if not info or not info.get("url"):
            return self._ver_novidades()
        if not getattr(sys, "frozen", False):
            self._escrever("Rodando pelo .py: baixe a versão nova na página do projeto.\n")
            return self._ver_novidades()
        self.faixa_bt.configure(text="Baixando...", state="disabled")

        def trabalho():
            try:
                arq = atualizacao.baixar(info, lambda p: self.fila.put(
                    ("progresso", f"Baixando... {int(p * 100)}%")))
                registro.log.info("Instalando atualização %s", info["versao"])
                atualizacao.instalar(arq)
                self.fila.put(("sair", None))
            except Exception as e:  # noqa: BLE001
                registro.erro("Falha ao atualizar", e)
                self.fila.put(("log", "Não consegui baixar a atualização. "
                                      "Tente pela página do projeto.\n"))
                self.fila.put(("progresso", "Atualizar agora"))
        threading.Thread(target=trabalho, daemon=True).start()

    def _abrir_log(self):
        arq = registro.ARQ_LOG
        if arq and arq.exists():
            if sys.platform == "win32":
                os.startfile(arq)
            else:
                webbrowser.open(arq.as_uri())
        else:
            self._escrever("O log ainda está vazio.\n")

    def _copiar_diagnostico(self):
        self.clipboard_clear()
        self.clipboard_append(registro.diagnostico(VERSAO, coach.BASE))
        self._escrever("Diagnóstico copiado. Cole na conversa com o Claude.\n")

    def _atualizar_chamada(self):
        self.chamada_desc.configure(text="Diga " + coach.exemplos_chamada() + ".")

    def _linha_voz_windows(self, pai):
        linha = ctk.CTkFrame(pai, fg_color="transparent")
        linha.pack(fill="x", padx=16, pady=7)
        txt = ctk.CTkFrame(linha, fg_color="transparent")
        txt.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(txt, text="Voz do Quíron", font=self.f_txt).pack(anchor="w")
        ctk.CTkLabel(txt, text="Para ter mais vozes, instale em Configurações do Windows → "
                     "Hora e idioma → Fala.", font=self.f_peq, text_color=TEXTO2,
                     wraplength=300, justify="left").pack(anchor="w")
        self._bt_testar_voz = ctk.CTkButton(linha, text="Ouvir", width=70, fg_color=AZUL,
                                            hover_color=AZUL_HOVER, command=self._testar_voz)
        self._bt_testar_voz.pack(side="right")
        velocidades = {"Lenta": 150, "Normal": 185, "Rápida": 220}
        vel = ctk.CTkOptionMenu(linha, values=list(velocidades), width=95, fg_color=AZUL,
                                button_color=AZUL_HOVER, command=lambda v: coach.salvar_config(
                                    {"velocidade_voz": velocidades[v]}))
        atual = coach.CONFIG.get("velocidade_voz", 185)
        vel.set(min(velocidades, key=lambda k: abs(velocidades[k] - atual)))
        vel.pack(side="right", padx=8)
        vozes = coach.listar_vozes()
        self._vozes = {"Automática (português)": ""} | {n: i for n, i in vozes}
        menu = ctk.CTkOptionMenu(linha, values=list(self._vozes), width=220,
                                 dynamic_resizing=False, fg_color=AZUL, button_color=AZUL_HOVER,
                                 command=lambda v: coach.salvar_config(
                                     {"voz_windows": self._vozes[v]}))
        inv = {i: n for n, i in self._vozes.items()}
        menu.set(inv.get(coach.CONFIG.get("voz_windows", ""), "Automática (português)"))
        menu.pack(side="right")

    def _testar_voz(self):
        frase = f"Olá! Eu sou o Quíron. Diga {coach.CONFIG.get('palavra_chamada', 'Quíron')} itens para ouvir a build."
        voz = self.voz
        if voz is None or not voz.ativa:
            if getattr(self, "_voz_teste", None) is None:
                self._voz_teste = coach.Voz(ativa=True)
            voz = self._voz_teste
        voz.fila.put(frase)

    def _mudar_voz(self, ligada):
        coach.salvar_config({"voz_ligada": ligada})
        if self.voz:
            self.voz.ligar(ligada)

    def _mudar_inicializacao(self, ligar):
        ok = iniciar_com_windows(ligar)
        coach.salvar_config({"iniciar_com_windows": ligar and ok})
        if ligar and not ok:
            self._escrever("“Iniciar com o Windows” só funciona no Windows.\n")

    def _procurar(self):
        from tkinter import filedialog
        pasta = filedialog.askdirectory(title="Pasta de instalação do League of Legends",
                                        initialdir=self.pasta_var.get())
        if pasta:
            self.pasta_var.set(os.path.normpath(pasta))
            coach.salvar_config({"pasta_lol": self.pasta_var.get()})

    def _abrir_pasta_dados(self):
        if sys.platform == "win32":
            os.startfile(coach.BASE)
        else:
            webbrowser.open(coach.BASE.as_uri())

    # ---- ligar / desligar -------------------------------------------------
    def alternar(self):
        if self._rodando():
            self.parar.set()
            self.botao.configure(text="Parando…", state="disabled")
        else:
            self.iniciar()

    def iniciar(self):
        if self.thread and self.thread.is_alive():
            return
        coach.salvar_config({"pasta_lol": self.pasta_var.get()})
        self.parar.clear()
        self.thread = threading.Thread(target=self._trabalhar, daemon=True)
        self.thread.start()
        self.botao.configure(text="Parar coach", fg_color=VERMELHO, hover_color=VERMELHO_HOVER)
        self._atualizar_menu_bandeja()

    def _trabalhar(self):
        try:
            if self.voz is None:
                self.voz = coach.Voz(ativa=coach.CONFIG["voz_ligada"])
            if self.ouvido is None and coach.CONFIG["comandos_de_voz"]:
                self.ouvido = coach.OuvidoComandos()
            coach.rodar(self.parar, self.voz, self.ouvido,
                        estado=lambda t: self.fila.put(("estado", t)))
        except Exception as e:  # noqa: BLE001
            self.fila.put(("log", f"Erro: {e}\n"))
        finally:
            self.fila.put(("parou", None))

    # ---- fila (threads -> janela) -----------------------------------------
    def _escrever(self, texto):
        self.log.configure(state="normal")
        self.log.insert("end", texto)
        linhas = int(self.log.index("end-1c").split(".")[0])
        if linhas > 800:
            self.log.delete("1.0", f"{linhas - 800}.0")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _mostrar_estado(self, texto):
        cor = (VERDE if texto.startswith("Em partida") else
               AZUL if texto.startswith("Seleção") else
               OURO if texto.startswith(("Aguardando", "Carregando")) else CINZA)
        dicas = {
            "Aguardando partida": "Entre na fila. O coach acompanha a seleção e a partida.",
            "Seleção de campeões": "Lendo a seleção: seu histórico e os campeões inimigos.",
            "Parado": "Inicie o coach e deixe o app aberto enquanto joga.",
            "Carregando dados dos campeões...": "Baixando dados do patch atual.",
        }
        padrao = (f"Diga “{coach.CONFIG.get('palavra_chamada', 'Quíron')} silêncio” para pausar os avisos."
                  if coach.CONFIG["comandos_de_voz"] else "Os avisos aparecem abaixo.")
        self.estado.configure(text=texto)
        self.ponto.configure(text_color=cor)
        self.dica.configure(text=dicas.get(texto, padrao))
        if self.bandeja:
            self.bandeja.title = f"Quíron — {texto}"

    def _ler_fila(self):
        try:
            while True:
                tipo, valor = self.fila.get_nowait()
                if tipo == "log":
                    self._escrever(valor)
                elif tipo == "estado":
                    self._mostrar_estado(valor)
                elif tipo == "parou":
                    self.botao.configure(text="Iniciar coach", state="normal",
                                         fg_color=AZUL, hover_color=AZUL_HOVER)
                    self._mostrar_estado("Parado")
                    self._atualizar_menu_bandeja()
                elif tipo == "itens":
                    self.itens = coach.Itens(valor)
                    self._preencher_builds()
                elif tipo == "runas":
                    self.runas = valor
                    if self.builds_abertas:
                        self._preencher_builds()
                elif tipo == "icone":
                    for chamada in valor:
                        try:
                            chamada()
                        except Exception:  # noqa: BLE001 (janela já fechada)
                            pass
                elif tipo == "campeoes":
                    self.campeoes = valor
                    self.icones.pre_carregar(coach.todos_do_pool())
                    self._preencher_builds()
                    if self.precisa_perfil and valor:
                        self.precisa_perfil = False
                        self.after(300, lambda: EditorPerfil(self, primeira_vez=True))
                elif tipo == "builds":
                    self._preencher_builds()
                elif tipo == "atualizacao":
                    self._mostrar_faixa(valor)
                elif tipo == "progresso":
                    pronto = valor == "Atualizar agora"
                    self.faixa_bt.configure(text=valor, state="normal" if pronto else "disabled")
                elif tipo == "mostrar":
                    self.mostrar()
                elif tipo == "alternar":
                    self.alternar()
                elif tipo == "sair":
                    self.sair()
                    return
        except queue.Empty:
            pass
        self.after(100, self._ler_fila)

    # ---- bandeja ----------------------------------------------------------
    def _criar_bandeja(self):
        try:
            import pystray
            from PIL import Image
            imagem = Image.open(PASTA_RECURSOS / "icone.ico")
            menu = pystray.Menu(
                pystray.MenuItem("Abrir Quíron",
                                 lambda: self.fila.put(("mostrar", None)), default=True),
                pystray.MenuItem(lambda _: "Parar coach" if self._rodando() else "Iniciar coach",
                                 lambda: self.fila.put(("alternar", None))),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Sair", lambda: self.fila.put(("sair", None))),
            )
            self.bandeja = pystray.Icon("Quiron", imagem, "Quíron", menu)
            self.bandeja.run_detached()
        except Exception:  # noqa: BLE001 (sem bandeja, o app funciona igual)
            self.bandeja = None

    def _rodando(self) -> bool:
        return bool(self.thread and self.thread.is_alive() and not self.parar.is_set())

    def _atualizar_menu_bandeja(self):
        if self.bandeja:
            try:
                self.bandeja.update_menu()
            except Exception:  # noqa: BLE001
                pass

    def mostrar(self):
        self.deiconify()
        self.lift()
        self.focus_force()

    def ao_fechar(self):
        if self.bandeja and coach.CONFIG["minimizar_para_bandeja"]:
            self.withdraw()
            if not getattr(self, "_avisou_bandeja", False):
                self._avisou_bandeja = True
                try:
                    self.bandeja.notify("O Quíron continua rodando aqui. Para sair, clique "
                                        "com o botão direito no ícone.", "Quíron")
                except Exception:  # noqa: BLE001
                    pass
        else:
            self.sair()

    def sair(self):
        self.parar.set()
        if self.thread:
            self.thread.join(timeout=3)
        if self.bandeja:
            try:
                self.bandeja.stop()
            except Exception:  # noqa: BLE001
                pass
        self.destroy()
        # Garante que o processo termina na hora (threads de download, voz e
        # bandeja não seguram o app aberto; o atualizador depende disso).
        import logging
        logging.shutdown()
        os._exit(0)


class SeletorCampeao(ctk.CTkToplevel):
    """Grade com os ícones dos campeões e busca por nome.

    Com `funcao`, mostra primeiro os campeões comuns nela e depois os incomuns.
    """

    COLUNAS = 7

    def __init__(self, pai, app: App, ao_escolher, excluir=(), titulo="Escolher campeão",
                 funcao: str | None = None):
        super().__init__(pai, fg_color=FUNDO)
        self.app, self.ao_escolher = app, ao_escolher
        self.title(titulo)
        self.geometry("640x620")
        self.transient(pai)
        self.after(100, self.grab_set)
        self.busca = ctk.CTkEntry(self, placeholder_text="Buscar campeão...", height=36,
                                  border_color=BORDA)
        self.busca.pack(fill="x", padx=16, pady=(16, 8))
        self.busca.bind("<KeyRelease>", lambda e: self._filtrar())
        self.after(150, self.busca.focus_set)
        rolagem = ctk.CTkScrollableFrame(self, fg_color="transparent")
        rolagem.pack(fill="both", expand=True, padx=10, pady=(0, 12))

        todos = sorted(((c["name"], cid) for cid, c in app.campeoes.items()
                        if cid not in excluir), key=lambda x: x[0].lower())
        app.icones.pre_carregar(cid for _, cid in todos)
        grupos = [(None, todos)]
        if funcao:
            lugar = funcoes_comuns.LUGAR.get(funcao, "")
            grupos = [(f"Comuns {lugar}", [t for t in todos if funcoes_comuns.comum(t[1], funcao)]),
                      (f"Incomuns {lugar} (build vira estimativa)",
                       [t for t in todos if not funcoes_comuns.comum(t[1], funcao)])]
        self.secoes = []
        for titulo_grupo, lista in grupos:
            cab = None
            if titulo_grupo:
                cab = ctk.CTkLabel(rolagem, text=titulo_grupo, font=app.f_sub)
                cab.pack(anchor="w", padx=6, pady=(6, 2))
            grade = ctk.CTkFrame(rolagem, fg_color="transparent")
            grade.pack(fill="x")
            for c in range(self.COLUNAS):
                grade.grid_columnconfigure(c, weight=1)
            incomum = bool(titulo_grupo and titulo_grupo.startswith("Incomuns"))
            celulas = []
            for nome, cid in lista:
                bt = ctk.CTkButton(grade, text=nome if len(nome) <= 11 else nome[:10] + "…",
                                   width=80, height=86, compound="top", fg_color="transparent",
                                   hover_color=BORDA, text_color=CINZA if incomum else TEXTO,
                                   font=app.f_peq,
                                   image=app.icones.obter(cid, 52) or app.icones.vazio(52),
                                   command=lambda cid=cid: self._escolher(cid))
                celulas.append((nome.lower(), cid, bt))
                self._pendente(cid, bt)
            self.secoes.append((cab, grade, celulas))
        self._filtrar()

    def _pendente(self, cid, bt):
        if not (coach.PASTA_ICONES / f"{cid}.png").exists():
            def pronto():
                img = self.app.icones.obter(cid, 52)
                if img and bt.winfo_exists():
                    bt.configure(image=img)
            self.app.icones.obter(cid, 52, ao_carregar=pronto)

    def _filtrar(self):
        texto = self.busca.get().strip().lower()
        for cab, grade, _ in self.secoes:  # re-empacota na ordem, só o que tem resultado
            if cab is not None:
                cab.pack_forget()
            grade.pack_forget()
        for cab, grade, celulas in self.secoes:
            i = 0
            for nome, _, bt in celulas:
                if texto in nome:
                    bt.grid(row=i // self.COLUNAS, column=i % self.COLUNAS, padx=2, pady=2)
                    i += 1
                else:
                    bt.grid_forget()
            if i:
                if cab is not None:
                    cab.pack(anchor="w", padx=6, pady=(6, 2))
                grade.pack(fill="x")

    def _escolher(self, cid):
        self.ao_escolher(cid)
        self.destroy()


class EditorPerfil(ctk.CTkToplevel):
    """Primeiro uso / editar perfil: Riot ID, elo, funções e pool por função."""

    SERVIDORES = ["BR", "LAN", "LAS", "NA", "EUW", "EUNE", "KR", "JP", "OCE", "TR", "RU",
                  "ME", "SEA", "TW", "VN"]
    NOMES = {"TOP": "Topo", "JUNGLE": "Caçador", "MIDDLE": "Meio", "BOTTOM": "Atirador",
             "UTILITY": "Suporte"}
    MAX_POOL = 6

    def __init__(self, app: App, primeira_vez: bool = False):
        super().__init__(app, fg_color=FUNDO)
        self.app = app
        self.title("Bem-vindo ao Quíron" if primeira_vez else "Seu perfil")
        self.geometry("620x720")
        self.transient(app)
        self.after(100, self.grab_set)
        atual = coach.perfil()
        if not atual["funcoes"] and app.perfil_sugerido:
            atual = coach.perfil() | app.perfil_sugerido
        self.pool = {f: list(c) for f, c in atual["pool"].items()}
        self.por_nome = {c["name"]: k for k, c in app.campeoes.items()}
        self.nomes_campeoes = sorted(self.por_nome)

        corpo = ctk.CTkScrollableFrame(self, fg_color="transparent")
        corpo.pack(fill="both", expand=True, padx=12, pady=(12, 0))
        if primeira_vez:
            ctk.CTkLabel(corpo, text="Vamos configurar o seu coach", font=app.f_titulo).pack(
                anchor="w", pady=(0, 2))
            ctk.CTkLabel(corpo, text="O Quíron usa isso para sugerir campeões no draft, "
                         "importar builds e montar o plano da partida. Dá para mudar depois em "
                         "Configurações → Perfil.", font=app.f_txt, text_color=TEXTO2,
                         wraplength=560, justify="left").pack(anchor="w", pady=(0, 10))

        def rotulo(t):
            ctk.CTkLabel(corpo, text=t, font=app.f_peq, text_color=TEXTO2).pack(
                anchor="w", pady=(10, 2))

        rotulo("Riot ID (Nome#TAG)")
        linha = ctk.CTkFrame(corpo, fg_color="transparent")
        linha.pack(fill="x")
        self.riot = ctk.CTkEntry(linha, border_color=BORDA, placeholder_text="Nome#TAG")
        if atual["riot_id"]:
            self.riot.insert(0, atual["riot_id"])
        self.riot.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.riot.bind("<Return>", lambda e: self._buscar())
        self.bt_buscar = ctk.CTkButton(linha, text="Buscar", width=90, fg_color=AZUL,
                                       hover_color=AZUL_HOVER, command=self._buscar)
        self.bt_buscar.pack(side="left", padx=(0, 8))
        self.servidor = ctk.CTkOptionMenu(linha, values=self.SERVIDORES, width=80,
                                          fg_color=AZUL, button_color=AZUL_HOVER)
        self.servidor.set(atual["servidor"] or "BR")
        self.servidor.pack(side="left")

        # Resultado da busca: ícone, nível e elo (vem do cliente, não se escolhe)
        self.elo = atual["elo"]
        self.card_inv = app._cartao(corpo)
        self.card_inv.pack(fill="x", pady=(10, 0))
        self.inv_icone = ctk.CTkLabel(self.card_inv, text="", width=56, height=56)
        self.inv_icone.pack(side="left", padx=(12, 10), pady=10)
        info = ctk.CTkFrame(self.card_inv, fg_color="transparent")
        info.pack(side="left", fill="x", expand=True, pady=10)
        self.inv_nome = ctk.CTkLabel(info, text="", font=app.f_sub, anchor="w")
        self.inv_nome.pack(anchor="w")
        self.inv_elo = ctk.CTkLabel(info, text="", font=app.f_txt, text_color=TEXTO2,
                                    anchor="w", justify="left", wraplength=440)
        self.inv_elo.pack(anchor="w")
        self.sugestao = ctk.CTkFrame(corpo, fg_color="transparent", height=1)
        self.sugestao.pack(fill="x")
        self._mostrar_invocador(None, atual["riot_id"])
        self.cliente = coach.ClienteLoL(coach.CONFIG["pasta_lol"])
        self.resultado: queue.Queue = queue.Queue()
        # com o cliente aberto, já busca (a conta logada, se o Riot ID estiver vazio)
        self.after(300, lambda: self._buscar(proprio=not atual["riot_id"], silencioso=True))

        rotulo("Funções que você joga")
        linha = ctk.CTkFrame(corpo, fg_color="transparent")
        linha.pack(fill="x")
        self.funcoes = {}
        for f in coach.FUNCOES:
            cb = ctk.CTkCheckBox(linha, text=self.NOMES[f], fg_color=AZUL, hover_color=AZUL_HOVER,
                                 command=self._montar_pools)
            if f in atual["funcoes"]:
                cb.select()
            cb.pack(side="left", padx=(0, 12))
            self.funcoes[f] = cb

        rotulo(f"Campeões por função (até {self.MAX_POOL})")
        self.area_pool = ctk.CTkFrame(corpo, fg_color="transparent")
        self.area_pool.pack(fill="x")
        self._montar_pools()

        bts = ctk.CTkFrame(self, fg_color="transparent")
        bts.pack(fill="x", padx=20, pady=12)
        ctk.CTkButton(bts, text="Salvar", fg_color=AZUL, hover_color=AZUL_HOVER,
                      command=self._salvar).pack(side="right")
        app._botao_secundario(bts, "Agora não" if primeira_vez else "Cancelar",
                              self.destroy, 100).pack(side="right", padx=8)
        self.erro = ctk.CTkLabel(bts, text="", text_color=("#c4372f", "#f0706a"),
                                 font=app.f_peq)
        self.erro.pack(side="left")

    # ---- busca do invocador (pelo cliente do LoL) ----------------------------
    def _mostrar_invocador(self, dados, riot_id=""):
        if dados is None:
            self.inv_icone.configure(image=self.app.icones.vazio(56))
            self.inv_nome.configure(text=riot_id or "Nenhum invocador")
            if self.elo:
                self.inv_elo.configure(text=f"Elo: {self.elo}  ·  clique em Buscar para atualizar")
            else:
                self.inv_elo.configure(text="Digite o Riot ID e clique em Buscar (com o cliente "
                                            "do LoL aberto). O elo é preenchido sozinho.")
            return
        icone = str(dados.get("icone") or "")
        if icone:
            img = self.app.icones.imagem("perfil", icone, 56,
                                         lambda: self._mostrar_icone(icone), raio=12)
            self.inv_icone.configure(image=img or self.app.icones.vazio(56))
        nivel = f"  ·  nível {dados['nivel']}" if dados.get("nivel") else ""
        self.inv_nome.configure(text=dados["riot_id"] + nivel)
        if dados["elo"]:
            jogos = dados["vitorias"] + dados["derrotas"]
            taxa = f"  ·  {round(100 * dados['vitorias'] / jogos)}% de vitórias em {jogos} jogos" \
                if jogos else ""
            pdl = f"  ·  {dados['pdl']} PDL" if dados.get("pdl") is not None else ""
            self.inv_elo.configure(text=f"Solo/Duo: {dados['elo']}{pdl}{taxa}")
        else:
            self.inv_elo.configure(text="Solo/Duo: sem ranque nesta temporada")

    def _mostrar_icone(self, icone):
        img = self.app.icones.imagem("perfil", icone, 56, raio=12)
        if img and self.winfo_exists():
            self.inv_icone.configure(image=img)

    def _buscar(self, proprio: bool = False, silencioso: bool = False):
        if str(self.bt_buscar.cget("state")) == "disabled":
            return
        self.silencioso = silencioso
        riot = self.riot.get().strip()
        if not proprio and "#" not in riot:
            self.erro.configure(text="O Riot ID tem o formato Nome#TAG.")
            return
        self.erro.configure(text="")
        self.bt_buscar.configure(state="disabled", text="...")

        def trabalho():
            try:
                if proprio:
                    eu = self.cliente.eu()
                    if not eu or not eu["riot_id"]:
                        self.resultado.put(("silencio", None))
                        return
                    self.resultado.put(("riot", eu))
                    dados = self.cliente.buscar_invocador(eu["riot_id"])
                else:
                    dados = self.cliente.buscar_invocador(riot)
                    eu = self.cliente.eu()
                    if eu and eu.get("regiao"):
                        dados["regiao"] = eu["regiao"]
                self.resultado.put(("dados", dados))
            except Exception as e:  # noqa: BLE001
                registro.erro("Falha ao buscar invocador", e)
                self.resultado.put(("dados", {"erro": "Não consegui buscar agora. Tente de novo."}))

        threading.Thread(target=trabalho, daemon=True).start()
        self.after(150, self._esperar_busca)

    def _esperar_busca(self):
        if not self.winfo_exists():
            return
        try:
            tipo, valor = self.resultado.get_nowait()
        except queue.Empty:
            self.after(150, self._esperar_busca)
            return
        if tipo == "riot":
            self.riot.delete(0, "end")
            self.riot.insert(0, valor["riot_id"])
            if valor.get("regiao") in self.SERVIDORES:
                self.servidor.set(valor["regiao"])
            self.after(150, self._esperar_busca)
            return
        self.bt_buscar.configure(state="normal", text="Buscar")
        if tipo == "silencio":
            return
        if valor.get("erro"):
            if not self.silencioso:
                self.erro.configure(text=valor["erro"])
            return
        self.elo = valor["elo"]
        self.riot.delete(0, "end")
        self.riot.insert(0, valor["riot_id"])
        if valor.get("regiao") in self.SERVIDORES:
            self.servidor.set(valor["regiao"])
        self._mostrar_invocador(valor)
        self._sugerir_pelo_historico(valor)

    def _sugerir_pelo_historico(self, dados):
        """Mostra funções e campeões mais jogados e oferece usar no perfil."""
        for w in self.sugestao.winfo_children():
            w.destroy()
        total = dados.get("partidas_lidas", 0)
        if not total:
            return
        por_chave = {c["key"]: k for k, c in self.app.campeoes.items()}
        # funções com pelo menos 15% das partidas (no máximo 3)
        funcoes = [f for f, n in dados["funcoes"].most_common(3) if n / total >= 0.15]
        pool = {f: [por_chave[k] for k, _ in dados["campeoes"][f].most_common(self.MAX_POOL)
                    if k in por_chave] for f in funcoes}
        partes = [f"{self.NOMES[f]} {round(100 * n / total)}%"
                  for f, n in dados["funcoes"].most_common() if n / total >= 0.05]
        texto = f"Nas últimas {total} partidas: " + ", ".join(partes)
        if not self._selecionadas():
            self._aplicar(funcoes, pool)
            texto += ". Preenchi as funções e campeões; ajuste se quiser."
            ctk.CTkLabel(self.sugestao, text=texto, font=self.app.f_peq, text_color=TEXTO2,
                         wraplength=560, justify="left").pack(anchor="w", pady=(6, 0))
            return
        linha = ctk.CTkFrame(self.sugestao, fg_color="transparent")
        linha.pack(fill="x", pady=(6, 0))
        ctk.CTkLabel(linha, text=texto, font=self.app.f_peq, text_color=TEXTO2,
                     wraplength=400, justify="left").pack(side="left")
        self.app._botao_secundario(linha, "Usar no perfil",
                                   lambda: self._aplicar(funcoes, pool), 120).pack(side="right")

    def _aplicar(self, funcoes, pool):
        for f, cb in self.funcoes.items():
            cb.select() if f in funcoes else cb.deselect()
        self.pool.update({f: c for f, c in pool.items() if c})
        self._montar_pools()

    def _selecionadas(self):
        return [f for f in coach.FUNCOES if self.funcoes[f].get()]

    def _montar_pools(self):
        for w in self.area_pool.winfo_children():
            w.destroy()
        sel = self._selecionadas()
        if not sel:
            ctk.CTkLabel(self.area_pool, text="Marque pelo menos uma função.",
                         font=self.app.f_peq, text_color=TEXTO2).pack(anchor="w")
        for f in sel:
            card = self.app._cartao(self.area_pool)
            card.pack(fill="x", pady=4)
            cab = ctk.CTkFrame(card, fg_color="transparent")
            cab.pack(fill="x", padx=14, pady=(8, 2))
            ctk.CTkLabel(cab, text=self.NOMES[f], font=self.app.f_sub).pack(side="left")
            if self.pool.get(f):
                ctk.CTkLabel(cab, text="clique num campeão para remover", font=self.app.f_peq,
                             text_color=CINZA).pack(side="right")
            grade = ctk.CTkFrame(card, fg_color="transparent")
            grade.pack(fill="x", padx=12, pady=(0, 10))
            incomuns = [self.app.campeoes.get(c, {}).get("name", c) for c in self.pool.get(f, [])
                        if not funcoes_comuns.comum(c, f)]
            if incomuns:
                ctk.CTkLabel(card, text=f"⚠ Pouco jogado {funcoes_comuns.LUGAR[f]}: "
                             f"{', '.join(incomuns)}. A build vai ser uma estimativa.",
                             font=self.app.f_peq, text_color=OURO, wraplength=520,
                             justify="left").pack(anchor="w", padx=14, pady=(0, 10))
            por_linha = 6
            lista = self.pool.get(f, [])
            for i, cid in enumerate(lista):
                self._bloco_campeao(grade, f, cid).grid(row=i // por_linha, column=i % por_linha,
                                                        padx=2, pady=2)
            if len(lista) < self.MAX_POOL:
                n = len(lista)
                ctk.CTkButton(grade, text="+", width=60, height=60, corner_radius=14,
                              font=ctk.CTkFont(size=26), fg_color="transparent",
                              border_width=2, border_color=BORDA, hover_color=BORDA,
                              text_color=TEXTO2,
                              command=lambda f=f: SeletorCampeao(
                                  self, self.app, lambda cid, f=f: self._adicionar_id(f, cid),
                                  excluir=set(self.pool.get(f, [])),
                                  titulo=f"Adicionar campeão: {self.NOMES[f]}",
                                  funcao=f)).grid(
                    row=n // por_linha, column=n % por_linha, padx=9, pady=(6, 4), sticky="n")

    def _bloco_campeao(self, pai, funcao, cid):
        """Ícone + nome; clicar remove do pool (o fundo fica vermelho ao passar o mouse)."""
        nome = self.app.campeoes.get(cid, {}).get("name", cid)
        bt = ctk.CTkButton(pai, text=nome if len(nome) <= 10 else nome[:9] + "…",
                           image=self.app.icones.obter(cid, 60) or self.app.icones.vazio(60),
                           compound="top", width=78, height=88, fg_color="transparent",
                           hover_color=("#f3d2cf", "#4a2422"),
                           text_color=TEXTO if funcoes_comuns.comum(cid, funcao) else OURO,
                           font=self.app.f_peq, command=lambda: self._remover(funcao, cid))
        if not (coach.PASTA_ICONES / f"{cid}.png").exists():
            def pronto():
                img = self.app.icones.obter(cid, 60)
                if img and bt.winfo_exists():
                    bt.configure(image=img)
            self.app.icones.obter(cid, 60, ao_carregar=pronto)
        return bt

    def _adicionar_id(self, funcao, cid):
        lista = self.pool.setdefault(funcao, [])
        if cid not in lista and len(lista) < self.MAX_POOL:
            lista.append(cid)
        self.erro.configure(text="")
        self._montar_pools()

    def _adicionar(self, funcao, nome):
        cid = self.por_nome.get(nome.strip())
        if not cid:
            self.erro.configure(text="Escolha um campeão da lista.")
            return
        lista = self.pool.setdefault(funcao, [])
        if cid not in lista and len(lista) < self.MAX_POOL:
            lista.append(cid)
        self.erro.configure(text="")
        self._montar_pools()

    def _remover(self, funcao, cid):
        self.pool[funcao] = [c for c in self.pool.get(funcao, []) if c != cid]
        self._montar_pools()

    def _salvar(self):
        funcoes = self._selecionadas()
        if not funcoes:
            self.erro.configure(text="Marque pelo menos uma função.")
            return
        pool = {f: self.pool.get(f, []) for f in funcoes}
        if not any(pool.values()):
            self.erro.configure(text="Adicione pelo menos um campeão.")
            return
        riot = self.riot.get().strip()
        if riot and "#" not in riot:
            self.erro.configure(text="O Riot ID tem o formato Nome#TAG.")
            return
        coach.salvar_config({"perfil": {"riot_id": riot, "servidor": self.servidor.get(),
                                        "elo": self.elo, "funcoes": funcoes, "pool": pool}})
        self.app.perfil_txt.configure(text=coach.texto_perfil())
        self.app._preencher_builds()
        self.app._escrever("Perfil salvo.\n")
        self.destroy()


class EditorChamada(ctk.CTkToplevel):
    """Escolhe a palavra que chama o Quíron nos comandos de voz."""

    def __init__(self, app: App):
        super().__init__(app, fg_color=FUNDO)
        self.app = app
        self.title("Palavra de chamada")
        self.geometry("520x400")
        self.resizable(False, False)
        self.transient(app)
        self.after(100, self.grab_set)
        self.fila: queue.Queue = queue.Queue()
        corpo = ctk.CTkFrame(self, fg_color="transparent")
        corpo.pack(fill="both", expand=True, padx=20, pady=16)
        ctk.CTkLabel(corpo, text="Como você quer chamar o Quíron?", font=app.f_sub).pack(anchor="w")
        ctk.CTkLabel(corpo, text="Você fala essa palavra antes do comando. Ela precisa existir no "
                     "dicionário do reconhecimento de voz (que funciona sem internet).",
                     font=app.f_peq, text_color=TEXTO2, wraplength=470,
                     justify="left").pack(anchor="w", pady=(2, 10))
        linha = ctk.CTkFrame(corpo, fg_color="transparent")
        linha.pack(fill="x")
        self.var = ctk.StringVar(value=coach.CONFIG.get("palavra_chamada", "Quíron"))
        self.entrada = ctk.CTkEntry(linha, textvariable=self.var, border_color=BORDA)
        self.entrada.pack(side="left", fill="x", expand=True, padx=(0, 8))
        app._botao_secundario(linha, "Voltar para Quíron",
                              lambda: self.var.set("Quíron"), 150).pack(side="left")
        self.estado = ctk.CTkLabel(corpo, text="", font=app.f_txt, wraplength=470,
                                   justify="left", anchor="w")
        self.estado.pack(fill="x", pady=(10, 4))
        self.chips = ctk.CTkFrame(corpo, fg_color="transparent", height=1)
        self.chips.pack(fill="x")
        self.teste = ctk.CTkLabel(corpo, text="", font=app.f_peq, text_color=TEXTO2,
                                  wraplength=470, justify="left", anchor="w")
        self.teste.pack(fill="x", pady=(12, 4))
        self.bt_teste = app._botao_secundario(corpo, "Testar no microfone (5 s)", self._testar, 200)
        self.bt_teste.pack(anchor="w")

        bts = ctk.CTkFrame(self, fg_color="transparent")
        bts.pack(fill="x", padx=20, pady=12)
        self.bt_salvar = ctk.CTkButton(bts, text="Salvar", fg_color=AZUL, hover_color=AZUL_HOVER,
                                       command=self._salvar)
        self.bt_salvar.pack(side="right")
        app._botao_secundario(bts, "Cancelar", self.destroy, 100).pack(side="right", padx=8)
        self.var.trace_add("write", lambda *_: self._validar())
        self.entrada.bind("<Return>", lambda e: self._salvar())
        self._validar()

    def _validar(self):
        for w in self.chips.winfo_children():
            w.destroy()
        nome = self.var.get().strip()
        if not coach.vocabulario():
            self.estado.configure(text="O modelo de voz ainda não foi baixado (ele baixa ao ligar "
                                  "o coach com os comandos de voz). Dá para salvar mesmo assim.",
                                  text_color=TEXTO2)
            self.bt_salvar.configure(state="normal" if nome else "disabled")
            return True
        if not nome:
            self.estado.configure(text="Digite uma palavra.", text_color=TEXTO2)
            self.bt_salvar.configure(state="disabled")
            return False
        if coach.formas_chamada(nome):
            self.estado.configure(text="✓ Reconhecida. Diga " + coach.exemplos_chamada(nome) + ".",
                                  text_color=("#1f8a4c", "#4cc38a"))
            self.bt_salvar.configure(state="normal")
            return True
        self.estado.configure(text=f"✗ “{nome}” não está no dicionário de voz. Palavras parecidas:",
                              text_color=("#c4372f", "#f0706a"))
        self.bt_salvar.configure(state="disabled")
        for sug in coach.sugestoes_chamada(nome):
            self.app._botao_secundario(self.chips, sug, lambda t=sug: self.var.set(t.capitalize()),
                                       0).pack(side="left", padx=(0, 6), pady=2)
        return False

    def _testar(self):
        nome = self.var.get().strip()
        if not self._validar() or str(self.bt_teste.cget("state")) == "disabled":
            return
        self.bt_teste.configure(state="disabled")
        self.teste.configure(text=f"Fale agora: “{nome} itens”...")

        def trabalho():
            try:
                self.fila.put(coach.testar_chamada(nome))
            except Exception as e:  # noqa: BLE001
                registro.erro("Falha no teste da palavra de chamada", e)
                self.fila.put(("", f"erro: {e}"))

        threading.Thread(target=trabalho, daemon=True).start()
        self.after(200, self._esperar)

    def _esperar(self):
        if not self.winfo_exists():
            return
        try:
            texto, acao = self.fila.get_nowait()
        except queue.Empty:
            self.after(200, self._esperar)
            return
        self.bt_teste.configure(state="normal")
        nomes = {"build": "itens", "silencio": "silêncio", "volta": "volta", "anota": "anota"}
        if acao and acao.startswith("erro"):
            self.teste.configure(text=f"Não consegui usar o microfone ({acao[6:]}).")
        elif acao:
            self.teste.configure(text=f"✓ Entendi o comando “{nomes[acao]}”. Funcionando!")
        elif texto:
            self.teste.configure(text=f"Ouvi “{texto}”, mas não reconheci o comando. Tente falar "
                                 "mais perto do microfone ou escolha outra palavra.")
        else:
            self.teste.configure(text="Não ouvi nada. Confira o microfone em Configurações → Voz.")

    def _salvar(self):
        if not self._validar():
            return
        coach.salvar_config({"palavra_chamada": self.var.get().strip()})
        self.app._atualizar_chamada()
        self.app._escrever(f"Palavra de chamada: {self.var.get().strip()}. "
                           "Vale a partir da próxima partida.\n")
        self.destroy()


class SeletorItem(ctk.CTkToplevel):
    """Grade com os ícones dos itens da loja, busca e filtro por tipo."""

    COLUNAS = 7
    FILTROS = {
        "Todos": None,
        "Mágico": {"SpellDamage"},
        "Físico": {"Damage", "CriticalStrike", "AttackSpeed", "ArmorPenetration"},
        "Defesa": {"Armor", "SpellBlock", "Health"},
        "Botas": {"Boots"},
        "Suporte": {"ManaRegen", "HealthRegen", "Aura"},
    }

    def __init__(self, pai, app: App, ao_escolher):
        super().__init__(pai, fg_color=FUNDO)
        self.app, self.ao_escolher = app, ao_escolher
        self.title("Escolher item")
        self.geometry("660x640")
        self.transient(pai)
        self.after(100, self.grab_set)
        topo = ctk.CTkFrame(self, fg_color="transparent")
        topo.pack(fill="x", padx=16, pady=(16, 8))
        self.busca = ctk.CTkEntry(topo, placeholder_text="Buscar item...", height=36,
                                  border_color=BORDA)
        self.busca.pack(fill="x")
        self.busca.bind("<KeyRelease>", lambda e: self._filtrar())
        self.filtro = ctk.CTkSegmentedButton(topo, values=list(self.FILTROS),
                                             selected_color=AZUL, selected_hover_color=AZUL_HOVER,
                                             command=lambda _: self._filtrar())
        self.filtro.set("Todos")
        self.filtro.pack(anchor="w", pady=(8, 0))
        self.after(150, self.busca.focus_set)
        self.grade = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.grade.pack(fill="both", expand=True, padx=10, pady=(0, 12))
        for c in range(self.COLUNAS):
            self.grade.grid_columnconfigure(c, weight=1)
        self.celulas = []
        for item in app.itens.lista_loja():
            img = app.icones.imagem("item", item["id"], 44) or app.icones.vazio(44)
            nome = item["nome"]
            bt = ctk.CTkButton(self.grade, text=nome if len(nome) <= 12 else nome[:11] + "…",
                               width=84, height=82, compound="top", image=img,
                               fg_color="transparent", hover_color=BORDA, text_color=TEXTO,
                               font=app.f_peq, command=lambda en=item["en"]: self._escolher(en))
            if not coach.arquivo_imagem("item", item["id"]).exists():
                def pronto(bt=bt, iid=item["id"]):
                    im = self.app.icones.imagem("item", iid, 44)
                    if im and bt.winfo_exists():
                        bt.configure(image=im)
                app.icones.imagem("item", item["id"], 44, ao_carregar=pronto)
            self.celulas.append((nome.lower(), set(item["tags"]), bt))
        self._filtrar()

    def _filtrar(self):
        texto = self.busca.get().strip().lower()
        tags = self.FILTROS[self.filtro.get()]
        i = 0
        for nome, tags_item, bt in self.celulas:
            if texto in nome and (tags is None or tags & tags_item):
                bt.grid(row=i // self.COLUNAS, column=i % self.COLUNAS, padx=2, pady=2)
                i += 1
            else:
                bt.grid_forget()

    def _escolher(self, en):
        self.ao_escolher(en)
        self.destroy()


class EditorBuild(ctk.CTkToplevel):
    """Janela para editar (ou criar) a build de um campeão."""

    FUNCOES = {"Caçador": "JUNGLE", "Suporte": "UTILITY", "Topo": "TOP", "Meio": "MIDDLE",
               "Atirador": "BOTTOM"}
    TIPOS = {"Mago / dano mágico": "mago", "Encantador / proteção": "encantador",
             "Dano físico": "fisico", "Tanque": "tanque"}

    def __init__(self, app: App, cid: str | None):
        super().__init__(app, fg_color=FUNDO)
        self.app, self.cid = app, cid
        self.title("Editar build" if cid else "Nova build")
        self.geometry("560x620")
        self.transient(app)
        self.after(100, self.grab_set)
        b = (coach.obter_build(cid, getattr(app, "campeoes", {})) or {}) if cid else {}
        self.base = b
        f = ctk.CTkFrame(self, fg_color="transparent")
        f.pack(fill="both", expand=True, padx=20, pady=16)

        def rotulo(t):
            ctk.CTkLabel(f, text=t, font=app.f_peq, text_color=TEXTO2).pack(
                anchor="w", pady=(8, 2))

        rotulo("Campeão")
        campeoes = getattr(app, "campeoes", {})
        self.nomes_campeoes = {c["name"]: k for k, c in campeoes.items()}
        if cid:
            ctk.CTkLabel(f, text=app._nome_campeao(cid), font=app.f_sub).pack(anchor="w")
        else:
            self.campeao = ctk.CTkComboBox(f, values=sorted(self.nomes_campeoes), width=300)
            self.campeao.set("")
            self.campeao.pack(anchor="w")

        linha = ctk.CTkFrame(f, fg_color="transparent")
        linha.pack(fill="x")
        col1 = ctk.CTkFrame(linha, fg_color="transparent")
        col1.pack(side="left", fill="x", expand=True)
        col2 = ctk.CTkFrame(linha, fg_color="transparent")
        col2.pack(side="left", fill="x", expand=True, padx=(10, 0))
        ctk.CTkLabel(col1, text="Função", font=app.f_peq, text_color=TEXTO2).pack(
            anchor="w", pady=(8, 2))
        inv_f = {v: k for k, v in self.FUNCOES.items()}
        self.funcao = ctk.CTkOptionMenu(col1, values=list(self.FUNCOES), fg_color=AZUL,
                                        button_color=AZUL_HOVER)
        self.funcao.set(inv_f.get(b.get("funcao"), "Suporte"))
        self.funcao.pack(anchor="w", fill="x")
        ctk.CTkLabel(col2, text="Estilo (ajustes contra o time inimigo)", font=app.f_peq,
                     text_color=TEXTO2).pack(anchor="w", pady=(8, 2))
        inv_t = {v: k for k, v in self.TIPOS.items()}
        self.tipo = ctk.CTkOptionMenu(col2, values=list(self.TIPOS), fg_color=AZUL,
                                      button_color=AZUL_HOVER)
        self.tipo.set(inv_t.get(b.get("tipo_ajuste"), "Mago / dano"))
        self.tipo.pack(anchor="w", fill="x")

        rotulo("Runa principal")
        self.runa = ctk.CTkEntry(f, border_color=BORDA)
        self.runa.insert(0, b.get("runas", ""))
        self.runa.pack(fill="x")

        rotulo("Itens, na ordem de compra (clique para trocar; arraste para mudar a ordem; ✕ tira)")
        self.slots: list[str | None] = (list(b.get("itens", [])) + [None] * 6)[:6]
        self.area_itens = ctk.CTkFrame(f, fg_color="transparent")
        self.area_itens.pack(fill="x", pady=(2, 0))
        self._montar_slots()

        bts = ctk.CTkFrame(f, fg_color="transparent")
        bts.pack(fill="x", pady=(16, 0))
        ctk.CTkButton(bts, text="Salvar", fg_color=AZUL, hover_color=AZUL_HOVER,
                      command=self._salvar).pack(side="right")
        app._botao_secundario(bts, "Cancelar", self.destroy, 100).pack(side="right", padx=8)
        self.erro = ctk.CTkLabel(bts, text="", text_color=("#c4372f", "#f0706a"),
                                 font=app.f_peq)
        self.erro.pack(side="left")

    @staticmethod
    def _filtrar(cb, lista):
        texto = cb.get().lower()
        cb.configure(values=[n for n in lista if texto in n.lower()][:40] or lista)

    # -- espaços de item com imagem ---------------------------------------
    def _montar_slots(self):
        for w in self.area_itens.winfo_children():
            w.destroy()
        self.celulas = []
        for i, nome in enumerate(self.slots):
            cel = ctk.CTkFrame(self.area_itens, fg_color="transparent", corner_radius=10,
                               border_width=2, border_color=FUNDO)
            cel.grid(row=0, column=i, padx=3, sticky="n")
            self.celulas.append(cel)
            iid = self.app.itens.id(nome) if nome else None
            if iid:
                # Ícone que se arrasta para mudar a ordem; clique simples troca o item
                img = (self.app.icones.imagem("item", iid, 56)
                       or self.app.icones.vazio(56))
                bt = ctk.CTkLabel(cel, text="", image=img, width=64, height=64,
                                  corner_radius=10, fg_color="transparent", cursor="fleur")
                if not coach.arquivo_imagem("item", iid).exists():
                    def pronto(bt=bt, iid=iid):
                        im = self.app.icones.imagem("item", iid, 56)
                        if im and bt.winfo_exists():
                            bt.configure(image=im)
                    self.app.icones.imagem("item", iid, 56, ao_carregar=pronto)
                bt.bind("<Enter>", lambda e, b=bt: b.configure(fg_color=BORDA))
                bt.bind("<Leave>", lambda e, b=bt: b.configure(fg_color="transparent"))
                bt.bind("<ButtonPress-1>", lambda e, i=i: self._arrasto_inicio(e, i))
                bt.bind("<B1-Motion>", self._arrasto_mover)
                bt.bind("<ButtonRelease-1>", self._arrasto_fim)
            else:
                bt = ctk.CTkButton(cel, text="+", width=64, height=64, corner_radius=10,
                                   font=ctk.CTkFont(size=24), fg_color="transparent",
                                   border_width=2, border_color=BORDA, hover_color=BORDA,
                                   text_color=TEXTO2, command=lambda i=i: self._escolher_item(i))
            bt.pack(padx=4, pady=(4, 0))
            texto = self.app.itens.nome_pt(nome) if nome else f"Item {i + 1}"
            ctk.CTkLabel(cel, text=texto if len(texto) <= 12 else texto[:11] + "…", width=80,
                         font=self.app.f_peq,
                         text_color=TEXTO if nome else CINZA).pack()
            if nome:
                ctk.CTkButton(cel, text="✕", width=22, height=20, fg_color="transparent",
                              hover_color=BORDA, text_color=TEXTO2, font=self.app.f_peq,
                              command=lambda i=i: self._limpar(i)).pack(pady=(0, 4))

    # ---- arrastar para mudar a ordem ------------------------------------------
    def _arrasto_inicio(self, evento, i):
        self.arrasto = {"de": i, "x": evento.x_root, "y": evento.y_root, "ativo": False,
                        "fantasma": None, "alvo": i}

    def _arrasto_mover(self, evento):
        a = getattr(self, "arrasto", None)
        if not a:
            return
        if not a["ativo"]:
            if abs(evento.x_root - a["x"]) + abs(evento.y_root - a["y"]) < 6:
                return  # ainda é um clique
            a["ativo"] = True
            a["fantasma"] = self._criar_fantasma(a["de"])
        if a["fantasma"]:
            a["fantasma"].geometry(f"+{evento.x_root - 28}+{evento.y_root - 28}")
        alvo = self._slot_em(evento.x_root)
        if alvo != a["alvo"]:
            a["alvo"] = alvo
            for j, cel in enumerate(self.celulas):
                cel.configure(border_color=AZUL if j == alvo and j != a["de"] else FUNDO)

    def _arrasto_fim(self, evento):
        a = getattr(self, "arrasto", None)
        self.arrasto = None
        if not a:
            return
        if not a["ativo"]:
            self._escolher_item(a["de"])  # foi só um clique
            return
        if a["fantasma"]:
            a["fantasma"].destroy()
        cheios = [s for s in self.slots if s]
        alvo = min(self._slot_em(evento.x_root), len(cheios) - 1)
        item = self.slots[a["de"]]
        cheios.remove(item)
        cheios.insert(alvo, item)
        self.slots = (cheios + [None] * 6)[:6]
        self._montar_slots()

    def _slot_em(self, x_root):
        """Índice da célula mais próxima da posição horizontal do mouse."""
        centros = [c.winfo_rootx() + c.winfo_width() / 2 for c in self.celulas]
        return min(range(len(centros)), key=lambda j: abs(centros[j] - x_root))

    def _criar_fantasma(self, i):
        """Cópia do ícone que segue o mouse enquanto arrasta."""
        import tkinter as tk
        from PIL import Image, ImageTk
        iid = self.app.itens.id(self.slots[i])
        arq = coach.arquivo_imagem("item", iid) if iid else None
        if not arq or not arq.exists():
            return None
        try:
            img = ImageTk.PhotoImage(Image.open(arq).convert("RGBA").resize((56, 56)))
        except Exception:  # noqa: BLE001
            return None
        janela = tk.Toplevel(self)
        janela.overrideredirect(True)
        janela.attributes("-topmost", True)
        try:
            janela.attributes("-alpha", 0.85)
        except tk.TclError:
            pass
        rotulo = tk.Label(janela, image=img, bd=0, bg=FUNDO[1] if isinstance(FUNDO, tuple) else FUNDO)
        rotulo.image = img
        rotulo.pack()
        return janela

    def _escolher_item(self, i):
        SeletorItem(self, self.app, lambda en, i=i: self._definir(i, en))

    def _definir(self, i, en):
        self.slots[i] = en
        self._montar_slots()

    def _limpar(self, i):
        self.slots[i] = None
        # mantém os itens juntos, na ordem
        cheios = [s for s in self.slots if s]
        self.slots = (cheios + [None] * 6)[:6]
        self._montar_slots()

    def _salvar(self):
        cid = self.cid
        if not cid:
            nome = self.campeao.get().strip()
            cid = self.nomes_campeoes.get(nome)
            if not cid:
                self.erro.configure(text="Escolha um campeão da lista.")
                return
        itens = [nome for nome in self.slots if nome]
        if not itens:
            self.erro.configure(text="Coloque pelo menos um item.")
            return
        nova = {
            "funcao": self.FUNCOES[self.funcao.get()],
            "runas": self.runa.get().strip() or "—",
            "itens": itens,
            "ajustes": self.TIPOS[self.tipo.get()],
        }
        if not self.cid:  # campeão novo: começa da build genérica (runas e feitiços)
            self.base = coach.obter_build(cid, self.app.campeoes, nova["funcao"]) or {}
        for k in ("pagina", "feiticos", "inicio"):
            if self.base.get(k):
                nova[k] = self.base[k]
        coach.salvar_build_usuario(cid, nova)
        self.app._preencher_builds()
        self.app._escrever(f"Build de {self.app._nome_campeao(cid)} salva.\n")
        self.destroy()


def webview2_instalado() -> bool:
    """O WebView2 (navegador embutido do Windows) é o que desenha a interface nova."""
    if sys.platform != "win32":
        return True
    import winreg
    guid = "{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"
    for raiz, caminho in ((winreg.HKEY_LOCAL_MACHINE, rf"SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{guid}"),
                          (winreg.HKEY_LOCAL_MACHINE, rf"SOFTWARE\Microsoft\EdgeUpdate\Clients\{guid}"),
                          (winreg.HKEY_CURRENT_USER, rf"SOFTWARE\Microsoft\EdgeUpdate\Clients\{guid}")):
        try:
            with winreg.OpenKey(raiz, caminho) as k:
                versao, _ = winreg.QueryValueEx(k, "pv")
                if versao and versao != "0.0.0.0":
                    return True
        except OSError:
            continue
    return False


def verificar_interface(saida: str):
    """Confere se o executável tem tudo para abrir a interface nova."""
    import traceback
    try:
        import quiron_web
        import webview
        if sys.platform == "win32":
            from webview.platforms import winforms  # noqa: F401 (carrega o .NET e o WebView2)
        assert (quiron_web.PASTA_UI / "index.html").exists(), "ui/index.html não veio no pacote"
        assert (quiron_web.PASTA_UI / "fontes").is_dir(), "ui/fontes não veio no pacote"
        texto = f"OK webview {getattr(webview, '__version__', '?')} webview2={webview2_instalado()}"
    except Exception:  # noqa: BLE001
        texto = "ERRO\n" + traceback.format_exc()
    Path(saida).write_text(texto, encoding="utf-8")


def main():
    """Abre a interface nova (HTML); sem WebView2 ou se ela falhar, a clássica."""
    if "--verificar-interface" in sys.argv:   # usado no build do GitHub
        return verificar_interface(sys.argv[sys.argv.index("--verificar-interface") + 1])
    if "--teste-janela" in sys.argv:          # idem: abre a janela e percorre as abas
        import quiron_web
        return quiron_web.teste_janela(sys.argv[sys.argv.index("--teste-janela") + 1])
    minimizado = "--minimizado" in sys.argv
    classica = "--interface-classica" in sys.argv
    if not classica and webview2_instalado():
        try:
            import quiron_web
            quiron_web.main(minimizado)
            return
        except Exception as e:  # noqa: BLE001
            registro.configurar(coach.BASE, VERSAO)
            registro.erro("A interface nova não abriu; usando a clássica", e)
    App(minimizado=minimizado).mainloop()


if __name__ == "__main__":
    main()
