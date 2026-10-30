"""Força dos campeões por função no patch atual (tier list).

Fonte: MobaTrainer, ranqueada solo, Esmeralda+, patch 26.21
(https://www.mobatrainer.com/lol/tier-list/<top|jungle|mid|adc|support>).
Usada na sugestão de escolha do draft como "força no patch". O builds.json do
GitHub pode trazer uma lista mais nova na chave "tiers" (mesmo formato).
"""

PATCH = "26.21"

_BRUTO = {
    "TOP": {
        "S+": "Quinn, Warwick, Malphite",
        "S": "Kayle, Shen, Garen, Teemo, Darius, Nasus",
        "A": "Poppy, Singed, Lissandra, Zac, Kled, Ornn, Tahm Kench, Sion, Illaoi, Gangplank, Mordekaiser, Cho'Gath",
        "B": "Anivia, Urgot, Sett, Gwen, Tryndamere, Heimerdinger, Fiora, Wukong, Camille, Irelia, Swain, Olaf, Zaahen, Dr. Mundo, Malzahar, Aatrox, Renekton, Yasuo, Akali",
        "C": "Aurora, Riven, Gragas, Kennen, Pantheon, Yorick, Jax, Sylas, Trundle, Vladimir, Master Yi, Yone, Gnar, Volibear, Vayne",
        "D": "Ryze, Udyr, Ambessa, Jayce, Varus, Rumble, K'Sante",
    },
    "JUNGLE": {
        "S+": "Cho'Gath, Briar",
        "S": "Rammus, Warwick, Zyra, Bel'Veth, Lillia, Wukong",
        "A": "Amumu, Sejuani, Ivern, Shyvana, Rek'Sai, Darius, Zac, Udyr, Taliyah, Shaco, Elise, Master Yi",
        "B": "Gwen, Fiddlesticks, Gragas, Evelynn, Nunu & Willump, Fizz, Trundle, Skarner, Xin Zhao, Nidalee, Kindred, Ekko, Kayn, Diana, Aatrox, Talon, Viego, Sylas",
        "C": "Volibear, Teemo, Quinn, Kha'Zix, Naafiri, Jax, Jarvan IV, Graves, Karthus, Nocturne, Vi, Hecarim, Malphite, Rengar, Lee Sin",
        "D": "Pantheon, Ambessa, Jayce, Zed, Locke, Qiyana",
    },
    "MIDDLE": {
        "S+": "Gwen, Vex",
        "S": "Gragas, Vel'Koz, Vladimir, Ekko, Fizz, Ahri",
        "A": "Swain, Lux, Xerath, Twisted Fate, Lissandra, Diana, Talon, Katarina, Malzahar, LeBlanc, Yasuo",
        "B": "Aurora, Annie, Pantheon, Veigar, Aurelion Sol, Garen, Hwei, Kassadin, Kog'Maw, Ziggs, Anivia, Taliyah, Malphite, Zoe, Yone, Syndra, Zed, Locke",
        "C": "Kayle, Sion, Brand, Akshan, Nasus, Naafiri, Galio, Akali, Irelia, Sylas, Qiyana, Viktor, Cassiopeia, Orianna",
        "D": "Jayce, Ryze, Azir, Tristana, Mel, Smolder",
    },
    "BOTTOM": {
        "S+": "Karthus",
        "S": "Vel'Koz, Veigar, Nilah, Yasuo",
        "A": "Swain, Lux, Aurelion Sol, Hwei, Kog'Maw, Xayah, Katarina, Jinx",
        "B": "Xerath, Syndra, Twitch, Ziggs, Miss Fortune, Sivir, Zeri, Smolder, Samira, Kai'Sa, Tristana, Draven",
        "C": "Ashe, Viktor, Jhin, Seraphine, Vayne, Yunara, Aphelios, Varus, Lucian, Caitlyn",
        "D": "Kalista, Corki, Mel, Ezreal",
    },
    "UTILITY": {
        "S+": "Leona, Thresh",
        "S": "Taric, Amumu, Rell, Braum, Blitzcrank",
        "A": "Zilean, Vel'Koz, Sona, Janna, Senna, Soraka, Alistar, Seraphine, Rakan",
        "B": "Poppy, Galio, Maokai, Hwei, Nami, Zyra, Morgana, Milio, Brand, Tahm Kench, Lux, Lulu, Nautilus, Pyke",
        "C": "Elise, Renata Glasc, LeBlanc, Xerath, Swain, Shen, Shaco, Neeko, Bard, Karma, Pantheon, Yuumi",
        "D": "Zoe, Sylas, Camille, Ashe, Mel",
    },
}

# nomes que não viram o id do Data Dragon só tirando espaços e pontuação
_ESPECIAIS = {"Wukong": "MonkeyKing", "Nunu & Willump": "Nunu", "Renata Glasc": "Renata",
              "Kai'Sa": "Kaisa", "Kha'Zix": "Khazix", "Cho'Gath": "Chogath", "Vel'Koz": "Velkoz",
              "Bel'Veth": "Belveth", "Kog'Maw": "KogMaw", "LeBlanc": "Leblanc",
              "Rek'Sai": "RekSai", "K'Sante": "KSante"}


def _id(nome: str) -> str:
    if nome in _ESPECIAIS:
        return _ESPECIAIS[nome]
    return "".join(ch for ch in nome if ch.isalnum())


TIERS: dict[str, dict[str, str]] = {
    funcao: {_id(n.strip()): tier for tier, nomes in grupos.items() for n in nomes.split(",")}
    for funcao, grupos in _BRUTO.items()
}
PONTOS = {"S+": 30, "S": 25, "A": 20, "B": 14, "C": 8, "D": 3}


def tier(cid: str, funcao: str) -> str | None:
    return TIERS.get(funcao, {}).get(cid)


def atualizar(novos: dict):
    """Troca pela lista do builds.json, se vier uma ({funcao: {id: tier}})."""
    for funcao, d in (novos or {}).items():
        if isinstance(d, dict) and d:
            TIERS[funcao] = {str(k): str(v) for k, v in d.items() if str(v) in PONTOS}
