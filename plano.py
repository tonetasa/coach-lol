"""Plano de jogo pré-partida e rota inicial da selva.

Tudo aqui usa só o que aparece na tela de carregamento: campeões, times e
funções. As regras são heurísticas simples (força por fase, iniciação,
ameaças); com a chave da API do Claude configurada, o app pode pedir à IA um
plano mais detalhado (ver ia_chat.py).
"""

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
