"""Funções em que cada campeão costuma ser jogado (patch 26.21).

Fonte: listas de campeões por função do MobaTrainer (Esmeralda+, ranqueada solo),
https://www.mobatrainer.com/lol/tier-list/<top|jungle|mid|adc|support>. Um campeão
fora da lista da função é "incomum" ali: o app avisa e trata a build como estimativa.
"""

PATCH = "26.21"

COMUNS = {
    "TOP": {
        "Aatrox", "Akali", "Ambessa", "Anivia", "Aurora", "Camille", "Chogath", "Darius",
        "DrMundo", "Fiora", "Gangplank", "Garen", "Gnar", "Gragas", "Gwen", "Heimerdinger",
        "Illaoi", "Irelia", "Jax", "Jayce", "KSante", "Kayle", "Kennen", "Kled",
        "Lissandra", "Malphite", "Malzahar", "MasterYi", "MonkeyKing", "Mordekaiser",
        "Nasus", "Olaf", "Ornn", "Pantheon", "Poppy", "Quinn", "Renekton", "Riven",
        "Rumble", "Ryze", "Sett", "Shen", "Singed", "Sion", "Swain", "Sylas", "TahmKench",
        "Teemo", "Trundle", "Tryndamere", "Udyr", "Urgot", "Varus", "Vayne", "Vladimir",
        "Volibear", "Warwick", "Yasuo", "Yone", "Yorick", "Zaahen", "Zac",
    },
    "JUNGLE": {
        "Aatrox", "Ambessa", "Amumu", "Belveth", "Briar", "Chogath", "Darius", "Diana",
        "Ekko", "Elise", "Evelynn", "Fiddlesticks", "Fizz", "Gragas", "Graves", "Gwen",
        "Hecarim", "Ivern", "JarvanIV", "Jax", "Jayce", "Karthus", "Kayn", "Khazix",
        "Kindred", "LeeSin", "Lillia", "Locke", "Malphite", "MasterYi", "MonkeyKing",
        "Naafiri", "Nidalee", "Nocturne", "Nunu", "Pantheon", "Qiyana", "Quinn", "Rammus",
        "RekSai", "Rengar", "Sejuani", "Shaco", "Shyvana", "Skarner", "Sylas", "Taliyah",
        "Talon", "Teemo", "Trundle", "Udyr", "Vi", "Viego", "Volibear", "Warwick",
        "XinZhao", "Zac", "Zed", "Zyra",
    },
    "MIDDLE": {
        "Ahri", "Akali", "Akshan", "Anivia", "Annie", "AurelionSol", "Aurora", "Azir",
        "Brand", "Cassiopeia", "Diana", "Ekko", "Fizz", "Galio", "Garen", "Gragas", "Gwen",
        "Hwei", "Irelia", "Jayce", "Kassadin", "Katarina", "Kayle", "KogMaw", "Leblanc",
        "Lissandra", "Locke", "Lux", "Malphite", "Malzahar", "Mel", "Naafiri", "Nasus",
        "Orianna", "Pantheon", "Qiyana", "Ryze", "Sion", "Smolder", "Swain", "Sylas",
        "Syndra", "Taliyah", "Talon", "TwistedFate", "Veigar", "Velkoz", "Vex", "Viktor",
        "Vladimir", "Xerath", "Yasuo", "Yone", "Zed", "Ziggs", "Zoe",
    },
    "BOTTOM": {
        "Aphelios", "Ashe", "AurelionSol", "Caitlyn", "Corki", "Draven", "Ezreal", "Hwei",
        "Jhin", "Jinx", "Kaisa", "Kalista", "Karthus", "Katarina", "KogMaw", "Lucian",
        "Lux", "Mel", "MissFortune", "Nilah", "Samira", "Seraphine", "Sivir", "Smolder",
        "Swain", "Syndra", "Tristana", "Twitch", "Varus", "Vayne", "Veigar", "Velkoz",
        "Viktor", "Xayah", "Xerath", "Yasuo", "Yunara", "Zeri", "Ziggs",
    },
    "UTILITY": {
        "Alistar", "Amumu", "Ashe", "Bard", "Blitzcrank", "Brand", "Braum", "Camille",
        "Elise", "Galio", "Hwei", "Janna", "Karma", "Leblanc", "Leona", "Lulu", "Lux",
        "Maokai", "Mel", "Milio", "Morgana", "Nami", "Nautilus", "Neeko", "Pantheon",
        "Poppy", "Pyke", "Rakan", "Rell", "Renata", "Senna", "Seraphine", "Shaco", "Shen",
        "Sona", "Soraka", "Swain", "Sylas", "TahmKench", "Taric", "Thresh", "Velkoz",
        "Xerath", "Yuumi", "Zilean", "Zoe", "Zyra",
    },
}

LUGAR = {"TOP": "no topo", "JUNGLE": "na selva", "MIDDLE": "no meio",
         "BOTTOM": "como atirador", "UTILITY": "como suporte"}


def comum(cid: str, funcao: str) -> bool:
    """True se o campeão é jogado nessa função (ou se a função é desconhecida)."""
    return funcao not in COMUNS or cid in COMUNS[funcao]


def funcoes_de(cid: str) -> list[str]:
    return [f for f, ids in COMUNS.items() if cid in ids]


def aviso(cid: str, nome: str, funcao: str) -> str | None:
    """Frase curta quando o campeão é incomum na função; None se for comum."""
    if comum(cid, funcao):
        return None
    lugares = [LUGAR[f] for f in funcoes_de(cid)]
    onde = (", ".join(lugares[:-1]) + " ou " + lugares[-1]) if len(lugares) > 1 else "".join(lugares)
    extra = f" (costuma ser jogado {onde})" if onde else ""
    return (f"{nome} é pouco jogado {LUGAR.get(funcao, funcao)}{extra}: "
            "a build do Quíron é uma estimativa.")
