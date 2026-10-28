"""Plano de jogo pré-partida e rota inicial da selva.

Tudo aqui usa só o que aparece na tela de carregamento: campeões, times e
funções. As regras são heurísticas simples (força por fase, iniciação,
ameaças); com a chave da API do Claude configurada, o app pode pedir à IA um
plano mais detalhado (ver ia_chat.py).
"""

from funcoes_comuns import comum

# Campeões fortes no início (pressão cedo) e que escalam bem (fim de jogo).
# Ids do Data Dragon. Listas aproximadas: ajuste à vontade.
FORTES_CEDO = {
    "Draven", "Renekton", "LeeSin", "Elise", "Nidalee", "Pantheon", "Darius", "Olaf",
    "XinZhao", "JarvanIV", "Lucian", "Caitlyn", "Leona", "Nautilus", "Pyke", "Blitzcrank",
    "Talon", "Qiyana", "Rengar", "Kalista", "Samira", "Graves", "Kindred", "Ezreal",
    "Taliyah", "Rell", "Thresh", "Sion", "Riven", "Jayce", "TwistedFate", "Udyr",
    "Briar", "Naafiri", "Ambessa", "Viego",
}
ESCALAM = {
    "Kayle", "Kassadin", "Veigar", "Jinx", "Vayne", "KogMaw", "Aphelios", "Smolder",
    "Azir", "Cassiopeia", "Ryze", "Viktor", "Senna", "Sona", "Nasus", "Gwen", "Jax",
    "Kayn", "Karthus", "Zeri", "Twitch", "Yuumi", "Seraphine", "Orianna", "Anivia",
    "Vladimir", "AurelionSol", "Fiddlesticks", "Shyvana", "MasterYi",
    "Belveth", "Sylas", "Hwei", "Mel", "Aurora",
}

LADO_AZUL = "ORDER"   # time azul = base no canto de baixo à esquerda

# Ordem do full clear (6 campos) começando em cada buff
COMECA_VERMELHO = ["Vermelho", "Krugs", "Raptors", "Lobos", "Azul", "Gromp"]
COMECA_AZUL = ["Azul", "Gromp", "Lobos", "Raptors", "Vermelho", "Krugs"]


def _ids(jogadores, id_campeao, campeoes):
    return [id_campeao(p, campeoes) for p in jogadores]


def _iniciacao(ids, campeoes, engaje, muito_cc):
    n = 0
    for cid in ids:
        c = campeoes.get(cid, {})
        if cid in engaje or "Tank" in c.get("tags", []) or cid in muito_cc:
            n += 1
    return n


def _por_posicao(jogadores, id_campeao, campeoes):
    return {p.get("position"): id_campeao(p, campeoes) for p in jogadores if p.get("position")}


def montar_plano(jogo: dict, eu: dict, meu_time: str, campeoes: dict, id_campeao,
                 engaje: set, muito_cc: set, mergulho: set, nomes) -> list[str]:
    """Frases curtas com o plano: fase forte, iniciação, ameaças e a sua rota."""
    aliados = [p for p in jogo["allPlayers"] if p.get("team") == meu_time]
    inimigos = [p for p in jogo["allPlayers"] if p.get("team") != meu_time]
    ids_a = _ids(aliados, id_campeao, campeoes)
    ids_i = _ids(inimigos, id_campeao, campeoes)
    frases = []

    # 1) força por fase
    fase_a = sum(c in FORTES_CEDO for c in ids_a) - sum(c in ESCALAM for c in ids_a)
    fase_i = sum(c in FORTES_CEDO for c in ids_i) - sum(c in ESCALAM for c in ids_i)
    if fase_a - fase_i >= 2:
        frases.append("Seu time é mais forte no início: vale pressionar e "
                      "disputar objetivos antes dos 20 minutos.")
    elif fase_i - fase_a >= 2:
        frases.append("Seu time escala melhor: lutas arriscadas cedo favorecem o inimigo; "
                      "o time fica mais forte depois dos 25 minutos.")
    else:
        frases.append("Times equilibrados por fase de jogo.")

    # 2) iniciação
    ini_a = _iniciacao(ids_a, campeoes, engaje, muito_cc)
    ini_i = _iniciacao(ids_i, campeoes, engaje, muito_cc)
    if ini_a - ini_i >= 2:
        frases.append("Vocês têm mais iniciação: lutas em grupo favorecem o seu time.")
    elif ini_i - ini_a >= 2:
        frases.append("O inimigo tem mais iniciação: corredores sem visão e time "
                      "espalhado favorecem o lado deles.")

    # 3) ameaças
    ameacas = [nomes(c) for c in ids_i if c in mergulho
               or campeoes.get(c, {}).get("tags", [""])[0] == "Assassin"]
    if ameacas:
        frases.append(f"Ameaças de abate rápido: {' e '.join(dict.fromkeys(ameacas))}.")
    ap = sum(campeoes.get(c, {}).get("info", {}).get("magic", 0) >
             campeoes.get(c, {}).get("info", {}).get("attack", 0) for c in ids_i)
    if ap >= 4:
        frases.append("Dano inimigo quase todo mágico.")
    elif ap <= 1 and len(ids_i) >= 5:
        frases.append("Dano inimigo quase todo físico.")

    # 4) sua rota
    pos_a = _por_posicao(aliados, id_campeao, campeoes)
    pos_i = _por_posicao(inimigos, id_campeao, campeoes)
    minha = eu.get("position")
    if minha == "UTILITY" and pos_a.get("BOTTOM") and pos_i.get("BOTTOM"):
        frases.append(f"No bot: {nomes(pos_a['BOTTOM'])} com você, contra "
                      f"{nomes(pos_i['BOTTOM'])}"
                      + (f" e {nomes(pos_i['UTILITY'])}." if pos_i.get("UTILITY") else "."))
    elif minha in ("TOP", "MIDDLE", "BOTTOM") and pos_i.get(minha):
        frases.append(f"Seu oponente de rota: {nomes(pos_i[minha])}.")
    if pos_i.get("JUNGLE"):
        frases.append(f"Caçador inimigo: {nomes(pos_i['JUNGLE'])}.")
    return frases


def rota_selva(jogo: dict, meu_time: str, campeoes: dict, id_campeao,
               engaje: set, muito_cc: set, nomes) -> str:
    """Sugere o full clear terminando do lado da rota com mais controle de grupo."""
    aliados = [p for p in jogo["allPlayers"] if p.get("team") == meu_time]
    pos = _por_posicao(aliados, id_campeao, campeoes)

    def cc(cid):
        c = campeoes.get(cid, {})
        return int(cid in engaje or cid in muito_cc or "Tank" in c.get("tags", []))

    bot = 2 * cc(pos.get("UTILITY")) + cc(pos.get("BOTTOM"))
    top = 2 * cc(pos.get("TOP"))
    terminar_bot = bot >= top
    lado_azul = meu_time == LADO_AZUL
    # time azul: Azul fica no lado de cima; time vermelho: Azul fica no lado de baixo
    azul_em_cima = lado_azul
    termina_no_azul = (not terminar_bot) == azul_em_cima
    rota = COMECA_VERMELHO if termina_no_azul else COMECA_AZUL
    lado = "azul" if lado_azul else "vermelho"
    alvo = "bot" if terminar_bot else "topo"
    if terminar_bot and pos.get("UTILITY"):
        motivo = f"{nomes(pos['UTILITY'])} no bot tem controle para o gank"
    elif not terminar_bot and pos.get("TOP"):
        motivo = f"{nomes(pos['TOP'])} no topo tem controle para o gank"
    else:
        motivo = "é o lado com mais controle de grupo"
    return (f"Você está no lado {lado}. Rota sugerida: {', '.join(rota)}, "
            f"terminando perto do {alvo}, porque {motivo}.")


# ---------------------------------------------------------------------------
# Draft: perfil dos times, sugestão de escolha e análise final
# ---------------------------------------------------------------------------
# Traços dos campeões do seu pool (usados para casar com o draft)
TRACOS_POOL = {
    "Fiddlesticks": {"teamfight", "dano_magico", "escala"},
    "Karma": {"poke", "protecao", "dano_magico"},
    "Lulu": {"protecao", "anti_mergulho", "dano_magico"},
    "Seraphine": {"teamfight", "controle", "dano_magico", "escala"},
    "Morgana": {"anti_engaje", "controle", "dano_magico"},
    "Milio": {"anti_engaje", "protecao", "anti_mergulho"},
}
ANTI_ENGAJE = {"Morgana", "Milio", "Janna", "Braum", "Taric", "Alistar", "Renata"}
PROTETORES = {"Lulu", "Janna", "Milio", "Braum", "Taric", "Thresh", "Karma", "Nami",
              "Soraka", "Yuumi", "Renata", "Rell", "Alistar"}
POKE = {"Karma", "Lux", "Xerath", "Velkoz", "Zyra", "Ziggs", "Jayce", "Varus", "Ezreal",
        "Hwei", "Brand", "Zoe", "Nidalee", "Caitlyn"}


def tracos_genericos(cid: str, campeoes: dict, muito_cc: set) -> set:
    """Traços aproximados de qualquer campeão, pelas tags oficiais e listas acima."""
    c = campeoes.get(cid, {})
    tags, info = c.get("tags", []), c.get("info", {})
    t = set()
    if info.get("magic", 0) > info.get("attack", 0):
        t.add("dano_magico")
    if cid in muito_cc or "Tank" in tags:
        t.add("controle")
    if cid in ANTI_ENGAJE:
        t.add("anti_engaje")
    if cid in PROTETORES:
        t |= {"protecao", "anti_mergulho"}
    if cid in POKE:
        t.add("poke")
    if cid in ESCALAM:
        t.add("escala")
    if tags[:1] in (["Mage"], ["Tank"]) or cid in muito_cc:
        t.add("teamfight")
    return t


CURADORES = {"Soraka", "Yuumi", "Sona", "Nami", "Milio", "Seraphine", "Renata",
             "Aatrox", "Vladimir", "DrMundo", "Warwick", "Sylas", "Briar", "Swain"}


def perfil_time(ids: list[str], campeoes: dict, engaje: set, muito_cc: set,
                mergulho: set) -> dict:
    """Contagens que descrevem uma composição."""
    p = {"magico": 0, "fisico": 0, "tanques": 0, "iniciacao": 0, "cedo": 0,
         "escala": 0, "mergulho": 0, "engaje": 0, "cura": 0, "n": len(ids)}
    for cid in ids:
        c = campeoes.get(cid, {})
        tags, info = c.get("tags", []), c.get("info", {})
        suporte_puro = tags[:1] == ["Support"] and info.get("magic", 0) < 8
        if not suporte_puro:
            if info.get("magic", 0) > info.get("attack", 0):
                p["magico"] += 1
            else:
                p["fisico"] += 1
        p["tanques"] += "Tank" in tags
        p["iniciacao"] += cid in engaje or "Tank" in tags or cid in muito_cc
        p["cedo"] += cid in FORTES_CEDO
        p["escala"] += cid in ESCALAM
        p["mergulho"] += cid in mergulho or tags[:1] == ["Assassin"]
        p["engaje"] += cid in engaje
        p["cura"] += cid in CURADORES
    return p


def sugerir_escolha(pool: list[str], aliados: list[str], inimigos: list[str],
                    indisponiveis: set, stats: dict, campeoes: dict, engaje: set,
                    muito_cc: set, mergulho: set, nomes,
                    funcao: str | None = None) -> list[tuple[str, float, list[str]]]:
    """Ordena o seu pool para este draft. Retorna [(campeão, nota, motivos)]."""
    a = perfil_time(aliados, campeoes, engaje, muito_cc, mergulho)
    i = perfil_time(inimigos, campeoes, engaje, muito_cc, mergulho)
    resultado = []
    for cid in pool:
        if cid in indisponiveis or cid in aliados or cid in inimigos:
            continue
        v, d = stats.get(cid, (0, 0))
        taxa = (v + 1) / (v + d + 2)  # suaviza poucas partidas
        nota = taxa * 100
        motivos = [f"{round(100 * v / (v + d))}% em {v + d} partidas"] if v + d >= 5 else []
        tracos = TRACOS_POOL.get(cid) or tracos_genericos(cid, campeoes, muito_cc)
        if i["engaje"] and "anti_engaje" in tracos:
            nota += 6
            alvo = " e ".join(nomes(c) for c in inimigos if c in engaje)
            motivos.append(f"anula o engajamento de {alvo}")
        if i["mergulho"] >= 1 and "anti_mergulho" in tracos:
            nota += 5
            motivos.append("protege o carry contra quem mergulha")
        if a["magico"] == 0 and a["n"] >= 2 and "dano_magico" in tracos:
            nota += 4
            motivos.append("seu time ainda não tem dano mágico")
        if a["iniciacao"] == 0 and a["n"] >= 2 and "controle" in tracos:
            nota += 3
            motivos.append("seu time está sem controle de grupo")
        if a["escala"] >= 2 and "teamfight" in tracos:
            nota += 2
            motivos.append("combina com um time que escala para lutas")
        if i["cura"] >= 2 and cid == "Morgana":
            nota += 1
        if funcao and not comum(cid, funcao):
            nota -= 4
            motivos.append("incomum nesta função")
        resultado.append((cid, round(nota, 1), motivos))
    resultado.sort(key=lambda r: -r[1])
    return resultado


def analisar_draft(aliados: list[str], inimigos: list[str], campeoes: dict, engaje: set,
                   muito_cc: set, mergulho: set, nomes) -> tuple[list[str], list[str]]:
    """Pontos positivos e negativos do seu time em relação ao inimigo."""
    a = perfil_time(aliados, campeoes, engaje, muito_cc, mergulho)
    i = perfil_time(inimigos, campeoes, engaje, muito_cc, mergulho)
    bons, ruins = [], []

    # dano
    if a["magico"] >= 2 and a["fisico"] >= 2:
        bons.append("Dano misto: fica difícil para o inimigo montar resistência.")
    elif a["magico"] <= 1 and a["n"] >= 5:
        ruins.append("Dano quase todo físico: o inimigo pode comprar armadura e anular o time.")
    elif a["fisico"] <= 1 and a["n"] >= 5:
        ruins.append("Dano quase todo mágico: o inimigo pode comprar resistência mágica.")

    # linha de frente
    if a["tanques"] >= 1:
        bons.append("Tem linha de frente para segurar as lutas.")
    else:
        ruins.append("Sem tanque: lutas longas e de frente favorecem o inimigo.")

    # iniciação
    if a["iniciacao"] - i["iniciacao"] >= 2:
        bons.append("Mais iniciação que o inimigo: vocês escolhem quando lutar.")
    elif i["iniciacao"] - a["iniciacao"] >= 2:
        ruins.append("O inimigo tem mais iniciação: cuidado com corredores sem visão.")

    # fase de jogo
    fase = (a["cedo"] - a["escala"]) - (i["cedo"] - i["escala"])
    if fase >= 2:
        bons.append("Mais forte no início: dá para pressionar antes dos 20 minutos.")
    elif fase <= -2:
        bons.append("Escala melhor: o time fica mais forte no fim do jogo.")
        ruins.append("Mais fraco no início: o inimigo vai tentar pressionar cedo.")

    # ameaças
    if i["mergulho"] >= 2:
        alvo = " e ".join(nomes(c) for c in inimigos
                          if c in mergulho or campeoes.get(c, {}).get("tags", [""])[0] == "Assassin")
        ruins.append(f"Muitas ameaças de mergulho no inimigo: {alvo}.")
    if i["cura"] >= 2:
        ruins.append("O inimigo tem bastante cura: item de corte de cura vale a pena.")
    if a["cura"] >= 2:
        bons.append("Boa sustentação no seu time.")

    if not bons:
        bons.append("Composição sem grande vantagem clara.")
    if not ruins:
        ruins.append("Nenhuma fraqueza clara na composição.")
    return bons, ruins
