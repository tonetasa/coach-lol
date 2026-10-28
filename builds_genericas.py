"""Build genérica para qualquer campeão, a partir da classe e da função.

Serve de ponto de partida quando o campeão ainda não tem build pesquisada em
builds.json. Os nomes (em inglês) seguem o Data Dragon; o teste em
`validar()` confere que todos existem no patch atual.
"""

# Ajustes contra a composição inimiga, por estilo: (descrição, [itens])
AJUSTES_FISICO = {
    "ap": ("muito dano mágico", ["Maw of Malmortius", "Mercury's Treads"]),
    "ad": ("muito dano físico", ["Guardian Angel", "Plated Steelcaps"]),
    "cura": ("muita cura", ["Mortal Reminder", "Chempunk Chainsword"]),
    "tanques": ("dois ou mais tanques", ["Lord Dominik's Regards", "Serylda's Grudge"]),
    "cc": ("muito controle de grupo", ["Mercurial Scimitar", "Mercury's Treads"]),
    "assassinos": ("assassino", ["Guardian Angel", "Death's Dance"]),
}
AJUSTES_TANQUE = {
    "ap": ("muito dano mágico", ["Force of Nature", "Kaenic Rookern"]),
    "ad": ("muito dano físico", ["Randuin's Omen", "Frozen Heart"]),
    "cura": ("muita cura", ["Thornmail"]),
    "tanques": ("dois ou mais tanques", ["Unending Despair"]),
    "cc": ("muito controle de grupo", ["Mercury's Treads"]),
    "assassinos": ("assassino", ["Randuin's Omen", "Plated Steelcaps"]),
}


def _pagina(primaria, runas, secundaria, runas2, fragmentos):
    return {"primaria": primaria, "runas": runas, "secundaria": secundaria,
            "runas2": runas2, "fragmentos": fragmentos}


# Arquétipos: itens na ordem de compra, página de runas, runa (pt) e estilo de ajustes
ARQUETIPOS = {
    "mago": {
        "itens": ["Luden's Echo", "Sorcerer's Shoes", "Shadowflame", "Rabadon's Deathcap"],
        "runas": "Cometa Arcano", "ajustes": "mago",
        "pagina": _pagina("Sorcery", ["Arcane Comet", "Manaflow Band", "Transcendence", "Scorch"],
                          "Inspiration", ["Magical Footwear", "Biscuit Delivery"],
                          ["adaptativo", "adaptativo", "vida_escalavel"]),
    },
    "assassino_ap": {
        "itens": ["Stormsurge", "Sorcerer's Shoes", "Shadowflame", "Rabadon's Deathcap"],
        "runas": "Eletrocutar", "ajustes": "mago",
        "pagina": _pagina("Domination", ["Electrocute", "Sudden Impact", "Grisly Mementos",
                                         "Treasure Hunter"],
                          "Sorcery", ["Manaflow Band", "Transcendence"],
                          ["adaptativo", "adaptativo", "vida_escalavel"]),
    },
    "assassino": {
        "itens": ["Youmuu's Ghostblade", "Ionian Boots of Lucidity", "Edge of Night",
                  "Serylda's Grudge"],
        "runas": "Eletrocutar", "ajustes": "fisico",
        "pagina": _pagina("Domination", ["Electrocute", "Sudden Impact", "Grisly Mementos",
                                         "Treasure Hunter"],
                          "Precision", ["Triumph", "Coup de Grace"],
                          ["adaptativo", "adaptativo", "vida_escalavel"]),
    },
    "atirador": {
        "itens": ["Kraken Slayer", "Berserker's Greaves", "Infinity Edge",
                  "Lord Dominik's Regards"],
        "runas": "Ritmo Fatal", "ajustes": "fisico",
        "pagina": _pagina("Precision", ["Lethal Tempo", "Presence of Mind", "Legend: Alacrity",
                                        "Coup de Grace"],
                          "Inspiration", ["Magical Footwear", "Cosmic Insight"],
                          ["vel_ataque", "adaptativo", "vida_escalavel"]),
    },
    "lutador": {
        "itens": ["Black Cleaver", "Plated Steelcaps", "Sterak's Gage", "Death's Dance"],
        "runas": "Conquistador", "ajustes": "fisico",
        "pagina": _pagina("Precision", ["Conqueror", "Triumph", "Legend: Haste", "Last Stand"],
                          "Resolve", ["Second Wind", "Unflinching"],
                          ["adaptativo", "adaptativo", "vida_escalavel"]),
    },
    "tanque": {
        "itens": ["Sunfire Aegis", "Plated Steelcaps", "Thornmail", "Force of Nature"],
        "runas": "Aperto dos Mortos-Vivos", "ajustes": "tanque",
        "pagina": _pagina("Resolve", ["Grasp of the Undying", "Demolish", "Second Wind",
                                      "Overgrowth"],
                          "Inspiration", ["Biscuit Delivery", "Approach Velocity"],
                          ["adaptativo", "vida_escalavel", "vida"]),
    },
    "encantador": {
        "itens": ["Moonstone Renewer", "Ionian Boots of Lucidity", "Ardent Censer",
                  "Redemption"],
        "runas": "Aery", "ajustes": "encantador",
        "pagina": _pagina("Sorcery", ["Summon Aery", "Manaflow Band", "Transcendence", "Scorch"],
                          "Resolve", ["Bone Plating", "Revitalize"],
                          ["aceleracao", "adaptativo", "vida_escalavel"]),
    },
    "suporte_tanque": {
        "itens": ["Locket of the Iron Solari", "Plated Steelcaps", "Knight's Vow",
                  "Zeke's Convergence"],
        "runas": "Pós-choque", "ajustes": "tanque",
        "pagina": _pagina("Resolve", ["Aftershock", "Font of Life", "Bone Plating",
                                      "Unflinching"],
                          "Inspiration", ["Biscuit Delivery", "Cosmic Insight"],
                          ["aceleracao", "vida_escalavel", "vida"]),
    },
}

FEITICOS = {
    "JUNGLE": ["Flash", "Smite"], "UTILITY": ["Flash", "Ignite"], "BOTTOM": ["Flash", "Heal"],
    "MIDDLE": ["Flash", "Ignite"], "TOP": ["Flash", "Teleport"],
}
ENCANTADORES = {"Lulu", "Janna", "Soraka", "Nami", "Sona", "Yuumi", "Karma", "Milio",
                "Renata", "Seraphine", "Bard", "Taric", "Senna"}


def funcao_provavel(campeao: dict) -> str:
    tag = (campeao.get("tags") or ["Fighter"])[0]
    return {"Marksman": "BOTTOM", "Support": "UTILITY", "Assassin": "MIDDLE",
            "Mage": "MIDDLE", "Tank": "TOP", "Fighter": "TOP"}.get(tag, "TOP")


def arquetipo(cid: str, campeao: dict, funcao: str) -> str:
    tags = campeao.get("tags") or ["Fighter"]
    info = campeao.get("info", {})
    magico = info.get("magic", 0) > info.get("attack", 0)
    if funcao == "UTILITY":
        if cid in ENCANTADORES or (tags[0] == "Support" and "Tank" not in tags):
            return "encantador"
        if "Tank" in tags:
            return "suporte_tanque"
        return "mago" if magico else "suporte_tanque"
    if tags[0] == "Marksman" or (funcao == "BOTTOM" and not magico):
        return "atirador"
    if tags[0] == "Tank":
        return "tanque"
    if tags[0] == "Assassin":
        return "assassino_ap" if magico else "assassino"
    if tags[0] == "Mage" or magico:
        return "mago"
    return "lutador"


def build_generica(cid: str, campeao: dict, funcao: str | None = None) -> dict:
    funcao = funcao or funcao_provavel(campeao)
    tipo = arquetipo(cid, campeao, funcao)
    a = ARQUETIPOS[tipo]
    feiticos = FEITICOS.get(funcao, ["Flash", "Ignite"])
    if tipo == "encantador":
        feiticos = ["Flash", "Heal"]
    return {"funcao": funcao, "runas": a["runas"], "itens": list(a["itens"]),
            "pagina": a["pagina"], "feiticos": feiticos,
            "ajustes": a["ajustes"], "generica": True, "arquetipo": tipo}


def validar(itens_en: set, runas: dict) -> list[str]:
    """Lista de problemas (nomes que não existem no Data Dragon)."""
    erros = []
    for nome, a in ARQUETIPOS.items():
        for i in a["itens"]:
            if i not in itens_en:
                erros.append(f"{nome}: item {i}")
        p = a["pagina"]
        for arv in (p["primaria"], p["secundaria"]):
            if arv not in runas["arvores"]:
                erros.append(f"{nome}: árvore {arv}")
        for r in p["runas"] + p["runas2"]:
            if r not in runas["runas"]:
                erros.append(f"{nome}: runa {r}")
    for aj in (AJUSTES_FISICO, AJUSTES_TANQUE):
        for _, itens in aj.values():
            erros += [f"ajuste: item {i}" for i in itens if i not in itens_en]
    return erros
