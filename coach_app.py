"""
Coach LoL — app para Windows
============================

Interface do coach: abas Coach, Builds, Relatório e Configurações, ícone na
bandeja (perto do relógio) e opção de iniciar junto com o Windows.

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
import ia_chat
import registro
import relatorio_lol as relatorio
from versao import AVISO, VERSAO

URL_BUILDS = "https://claude.ai/artifact/DNv4gfXzbRkregwhFNtQ4N"
NOME_REGISTRO = "CoachLoL"
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
     "Cria a página “Coach LoL” do campeão escolhido.", False),
    ("importar_itens", "Importar itens",
     "Cria o conjunto de itens “Coach LoL” que aparece na loja.", False),
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
    return True


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

        self.migrados = coach.migrar_dados_antigos() if getattr(sys, "frozen", False) else 0
        registro.configurar(coach.BASE, VERSAO)
        coach.carregar_config()
        coach.carregar_builds()
        self.info_atualizacao: dict | None = None
        sys.stdout = SaidaParaFila(self.fila)
        sys.stderr = SaidaParaFila(self.fila)

        self.title(f"Coach LoL {VERSAO}")
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
        ctk.CTkLabel(topo, text="Coach LoL", font=self.f_titulo).pack(side="left")
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
        for nome in ("Coach", "Builds", "Relatório", "Chat", "Configurações"):
            self.abas.add(nome)
        self._aba_coach(self.abas.tab("Coach"))
        self._aba_builds(self.abas.tab("Builds"))
        self._aba_relatorio(self.abas.tab("Relatório"))
        self._aba_chat(self.abas.tab("Chat"))
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
        for cid, b in coach.BUILDS.items():
            card = self._cartao(self.lista_builds)
            card.pack(fill="x", padx=2, pady=4)
            topo = ctk.CTkFrame(card, fg_color="transparent")
            topo.pack(fill="x", padx=16, pady=(10, 2))
            ctk.CTkLabel(topo, text=self._nome_campeao(cid), font=self.f_sub).pack(side="left")
            ctk.CTkLabel(topo, text=f"   {nomes_funcao.get(b['funcao'], b['funcao'])} · "
                         f"runa {b['runas']}", font=self.f_peq,
                         text_color=TEXTO2).pack(side="left", pady=(2, 0))
            if b.get("personalizado"):
                ctk.CTkLabel(topo, text="  personalizada", font=self.f_peq,
                             text_color=OURO).pack(side="left", pady=(2, 0))
            self._botao_secundario(topo, "Editar", lambda c=cid: self._editar_build(c),
                                   70).pack(side="right")
            if b.get("personalizado"):
                self._botao_secundario(topo, "Restaurar", lambda c=cid: self._restaurar(c),
                                       80).pack(side="right", padx=6)
            v, d = stats.get(cid, (0, 0))
            if v + d:
                ctk.CTkLabel(topo, text=f"{round(100 * v / (v + d))}% em {v + d}   ",
                             font=self.f_peq, text_color=OURO).pack(side="right")
            itens = "   →   ".join(self.itens.nome_pt(i) for i in b["itens"]) or "(sem itens)"
            ctk.CTkLabel(card, text=itens, font=self.f_txt, justify="left",
                         wraplength=640).pack(anchor="w", padx=16, pady=(0, 12))

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

    # ---- Chat ---------------------------------------------------------------
    SUGESTOES = ["Por que estou perdendo?", "O que treinar esta semana?",
                 "Analise minha última partida", "Qual campeão devo priorizar?"]

    def _aba_chat(self, aba):
        self.historico_chat: list[dict] = []
        self.chat = ctk.CTkTextbox(aba, font=self.f_txt, fg_color=CARTAO, border_color=BORDA,
                                   border_width=1, corner_radius=12, wrap="word")
        self.chat.pack(fill="both", expand=True, padx=4, pady=(4, 8))
        self.chat.tag_config("eu", foreground=AZUL[1])
        self.chat.tag_config("ia_nome", foreground=OURO)
        self.chat.tag_config("info", foreground=CINZA[1])
        self.chat.configure(state="disabled")

        chips = ctk.CTkFrame(aba, fg_color="transparent")
        chips.pack(fill="x", padx=4)
        for sug in self.SUGESTOES:
            self._botao_secundario(chips, sug, lambda t=sug: self._enviar_chat(t),
                                   20).pack(side="left", padx=(0, 6), pady=(0, 6))

        linha = ctk.CTkFrame(aba, fg_color="transparent")
        linha.pack(fill="x", padx=4, pady=(0, 4))
        self.chat_entrada = ctk.CTkEntry(linha, placeholder_text="Pergunte sobre suas partidas...",
                                         border_color=BORDA, height=38)
        self.chat_entrada.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.chat_entrada.bind("<Return>", lambda e: self._enviar_chat())
        self.chat_bt = ctk.CTkButton(linha, text="Enviar", width=90, height=38, fg_color=AZUL,
                                     hover_color=AZUL_HOVER, command=self._enviar_chat)
        self.chat_bt.pack(side="left")
        self._chat_escrever("O coach responde com base nas partidas que ele registrou, no seu "
                            "pool e nas builds. Configure a chave da API em Configurações → "
                            "Chat com IA.\n\n", "info")

    def _chat_escrever(self, texto, tag=None):
        self.chat.configure(state="normal")
        self.chat.insert("end", texto, tag)
        self.chat.see("end")
        self.chat.configure(state="disabled")

    def _enviar_chat(self, texto=None):
        texto = (texto or self.chat_entrada.get()).strip()
        if not texto or str(self.chat_bt.cget("state")) == "disabled":
            return
        chave = ia_chat.obter_chave()
        if not chave:
            self._chat_escrever("Configure a chave da API em Configurações → Chat com IA.\n\n",
                                "info")
            return
        self.chat_entrada.delete(0, "end")
        self._chat_escrever("Você: ", "eu")
        self._chat_escrever(texto + "\n\n")
        self._chat_escrever("Coach: ", "ia_nome")
        self._chat_escrever("pensando...", "info")
        self.chat_bt.configure(state="disabled", text="...")
        historico = list(self.historico_chat)

        def trabalho():
            try:
                resp = ia_chat.perguntar(historico, texto, chave, coach.CONFIG["modelo_ia"])
                self.fila.put(("chat", (texto, resp, None)))
            except Exception as e:  # noqa: BLE001
                registro.erro("Falha no chat", e)
                self.fila.put(("chat", (texto, None, str(e))))
        threading.Thread(target=trabalho, daemon=True).start()

    def _resposta_chat(self, pergunta, resposta, erro):
        self.chat.configure(state="normal")
        inicio = self.chat._textbox.search("pensando...", "end-1c", backwards=True)
        if inicio:
            self.chat.delete(inicio, f"{inicio}+11c")
        self.chat.configure(state="disabled")
        if erro:
            self._chat_escrever(erro + "\n\n", "info")
        else:
            self._chat_escrever(resposta + "\n\n")
            self.historico_chat += [{"role": "user", "content": pergunta},
                                    {"role": "assistant", "content": resposta}]
        self.chat_bt.configure(state="normal", text="Enviar")

    def _salvar_chave(self):
        chave = self.chave_var.get().strip()
        if not chave.startswith("sk-"):
            self.chave_status.configure(text="Isso não parece uma chave da API (começa com sk-ant-).")
            return
        onde = ia_chat.salvar_chave(chave)
        self.chave_var.set("")
        self._atualizar_status_chave(f"Chave salva no {onde}.")

    def _remover_chave(self):
        ia_chat.salvar_chave(None)
        self._atualizar_status_chave("Chave removida.")

    def _atualizar_status_chave(self, msg=None):
        tem = bool(ia_chat.obter_chave())
        self.chave_status.configure(text=msg or ("Chave configurada." if tem else
                                                 "Nenhuma chave configurada."))

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
                             justify="left").pack(anchor="w")
            sw = ctk.CTkSwitch(linha, text="", progress_color=AZUL, width=46)
            sw.pack(side="right")
            sw.select() if valor else sw.deselect()
            sw.configure(command=lambda: ao_mudar(bool(sw.get())))
            return sw

        voz = secao("Voz")
        interruptor(voz, "Falar os avisos", "Usa a voz do Windows.",
                    coach.CONFIG["voz_ligada"], self._mudar_voz)
        interruptor(voz, "Comandos de voz",
                    "“coach itens”, “coach silêncio”, “coach volta”, “coach anota”.",
                    coach.CONFIG["comandos_de_voz"],
                    lambda v: coach.salvar_config({"comandos_de_voz": v}))

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

        ia = secao("Chat com IA")
        linha = ctk.CTkFrame(ia, fg_color="transparent")
        linha.pack(fill="x", padx=16, pady=(12, 4))
        ctk.CTkLabel(linha, text="Chave da API do Claude", font=self.f_txt).pack(anchor="w")
        ctk.CTkLabel(linha, text="Crie em console.anthropic.com → API Keys. Cada pergunta custa "
                     "centavos de dólar. A chave fica no Gerenciador de Credenciais do Windows.",
                     font=self.f_peq, text_color=TEXTO2, wraplength=600,
                     justify="left").pack(anchor="w")
        linha = ctk.CTkFrame(ia, fg_color="transparent")
        linha.pack(fill="x", padx=16, pady=(4, 8))
        self.chave_var = ctk.StringVar(value="")
        self.chave_entry = ctk.CTkEntry(linha, textvariable=self.chave_var, show="•",
                                        border_color=BORDA,
                                        placeholder_text="sk-ant-..." )
        self.chave_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        ctk.CTkButton(linha, text="Salvar", width=80, fg_color=AZUL, hover_color=AZUL_HOVER,
                      command=self._salvar_chave).pack(side="left")
        self._botao_secundario(linha, "Remover", self._remover_chave, 80).pack(
            side="left", padx=(6, 0))
        self.chave_status = ctk.CTkLabel(ia, text="", font=self.f_peq, text_color=TEXTO2)
        self.chave_status.pack(anchor="w", padx=16)
        linha = ctk.CTkFrame(ia, fg_color="transparent")
        linha.pack(fill="x", padx=16, pady=(6, 4))
        ctk.CTkLabel(linha, text="Modelo", font=self.f_txt).pack(side="left")
        inv_m = {v: k for k, v in ia_chat.MODELOS.items()}
        self.modelo = ctk.CTkOptionMenu(linha, values=list(ia_chat.MODELOS), fg_color=AZUL,
                                        button_color=AZUL_HOVER, width=220,
                                        command=lambda v: coach.salvar_config(
                                            {"modelo_ia": ia_chat.MODELOS[v]}))
        self.modelo.set(inv_m.get(coach.CONFIG["modelo_ia"], list(ia_chat.MODELOS)[0]))
        self.modelo.pack(side="right")
        interruptor(ia, "Plano pré-partida pela IA",
                    "Além do plano automático, a IA fala um plano de 3 frases (custa centavos "
                    "por partida).", coach.CONFIG["plano_por_ia"],
                    lambda v: coach.salvar_config({"plano_por_ia": v}))
        ctk.CTkFrame(ia, fg_color="transparent", height=6).pack()
        self._atualizar_status_chave()

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
        ctk.CTkLabel(sobre, text=f"Coach LoL {VERSAO}", font=self.f_sub).pack(
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
        padrao = ("Diga “coach silêncio” para pausar os avisos."
                  if coach.CONFIG["comandos_de_voz"] else "Os avisos aparecem abaixo.")
        self.estado.configure(text=texto)
        self.ponto.configure(text_color=cor)
        self.dica.configure(text=dicas.get(texto, padrao))
        if self.bandeja:
            self.bandeja.title = f"Coach LoL — {texto}"

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
                elif tipo == "campeoes":
                    self.campeoes = valor
                    self._preencher_builds()
                elif tipo == "builds":
                    self._preencher_builds()
                elif tipo == "chat":
                    self._resposta_chat(*valor)
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
                pystray.MenuItem("Abrir Coach LoL",
                                 lambda: self.fila.put(("mostrar", None)), default=True),
                pystray.MenuItem(lambda _: "Parar coach" if self._rodando() else "Iniciar coach",
                                 lambda: self.fila.put(("alternar", None))),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Sair", lambda: self.fila.put(("sair", None))),
            )
            self.bandeja = pystray.Icon("CoachLoL", imagem, "Coach LoL", menu)
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
                    self.bandeja.notify("O Coach LoL continua rodando aqui. Para sair, clique "
                                        "com o botão direito no ícone.", "Coach LoL")
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


class EditorBuild(ctk.CTkToplevel):
    """Janela para editar (ou criar) a build de um campeão."""

    FUNCOES = {"Caçador": "JUNGLE", "Suporte": "UTILITY", "Topo": "TOP", "Meio": "MIDDLE",
               "Atirador": "BOTTOM"}
    TIPOS = {"Mago / dano": "mago", "Encantador / proteção": "encantador"}

    def __init__(self, app: App, cid: str | None):
        super().__init__(app, fg_color=FUNDO)
        self.app, self.cid = app, cid
        self.title("Editar build" if cid else "Nova build")
        self.geometry("520x600")
        self.transient(app)
        self.after(100, self.grab_set)
        b = coach.BUILDS.get(cid, {}) if cid else {}
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

        rotulo("Itens, na ordem de compra (digite para filtrar)")
        lista = app.itens.nomes_loja()
        self.itens = []
        atuais = [app.itens.nome_pt(i) for i in b.get("itens", [])]
        for i in range(6):
            cb = ctk.CTkComboBox(f, values=lista, border_color=BORDA)
            cb.set(atuais[i] if i < len(atuais) else "")
            cb.pack(fill="x", pady=2)
            cb.bind("<KeyRelease>", lambda e, c=cb, l=lista: self._filtrar(c, l))
            self.itens.append(cb)

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

    def _salvar(self):
        cid = self.cid
        if not cid:
            nome = self.campeao.get().strip()
            cid = self.nomes_campeoes.get(nome)
            if not cid:
                self.erro.configure(text="Escolha um campeão da lista.")
                return
        itens = [self.app.itens.en_de_pt(c.get().strip()) for c in self.itens if c.get().strip()]
        if not itens:
            self.erro.configure(text="Coloque pelo menos um item.")
            return
        coach.salvar_build_usuario(cid, {
            "funcao": self.FUNCOES[self.funcao.get()],
            "runas": self.runa.get().strip() or "—",
            "itens": itens,
            "ajustes": self.TIPOS[self.tipo.get()],
        })
        self.app._preencher_builds()
        self.app._escrever(f"Build de {self.app._nome_campeao(cid)} salva.\n")
        self.destroy()


def main():
    App(minimizado="--minimizado" in sys.argv).mainloop()


if __name__ == "__main__":
    main()
