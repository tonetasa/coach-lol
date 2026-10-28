"""Chat com IA sobre as suas partidas (API do Claude, da Anthropic).

Precisa de uma chave da API (console.anthropic.com). A chave fica guardada no
Gerenciador de Credenciais do Windows, não em arquivo. Cada pergunta custa
centavos; o modelo pode ser trocado em Configurações.
"""

import json
from datetime import datetime

import requests

import coach_lol as coach

URL = "https://api.anthropic.com/v1/messages"
MODELOS = {"Sonnet 5.5 (melhor)": "claude-sonnet-5-5",
           "Haiku 5.5 (mais barato)": "claude-haiku-5-5"}
SERVICO = "Quiron"
SERVICO_ANTIGO = "CoachLoL"

SISTEMA = """Você é o coach de League of Legends do jogador, dentro do app Quíron.
Responda em português do Brasil, direto e prático, como um coach de alto elo.
Use os dados das partidas abaixo como base: cite números quando ajudar e diga
quando os dados não bastam para concluir algo. Prefira 1 a 3 pontos de ação.
Nunca sugira ferramentas ou práticas que violem as regras da Riot (timers de
ultimate ou de feitiços inimigos, scripts, leitura de memória, etc.)."""


# ---------------------------------------------------------------------------
# Chave da API
# ---------------------------------------------------------------------------
def obter_chave() -> str | None:
    try:
        import keyring
        chave = keyring.get_password(SERVICO, "anthropic")
        if not chave:  # chave salva pela versão antiga (Coach LoL): migra
            chave = keyring.get_password(SERVICO_ANTIGO, "anthropic")
            if chave:
                keyring.set_password(SERVICO, "anthropic", chave)
        return chave
    except Exception:  # noqa: BLE001
        return coach.CONFIG.get("chave_api_reserva") or None


def salvar_chave(chave: str | None) -> str:
    """Guarda (ou apaga, com None) a chave. Retorna onde ficou guardada."""
    try:
        import keyring
        if chave:
            keyring.set_password(SERVICO, "anthropic", chave)
        else:
            try:
                keyring.delete_password(SERVICO, "anthropic")
            except Exception:  # noqa: BLE001
                pass
        return "Gerenciador de Credenciais do Windows"
    except Exception:  # noqa: BLE001
        coach.salvar_config({"chave_api_reserva": chave or ""})
        return "arquivo de configuração (o Gerenciador de Credenciais não está disponível)"


# ---------------------------------------------------------------------------
# Contexto: o que a IA sabe sobre você
# ---------------------------------------------------------------------------
def contexto(max_partidas: int = 25) -> str:
    partidas = coach.ler_partidas()[-max_partidas:]
    linhas = []
    for r in partidas:
        mortes = ", ".join(m["tempo"] for m in r.get("mortes", [])) or "nenhuma"
        linhas.append(
            f"- {r['data'][:16].replace('T', ' ')} · {r.get('campeao')} ({r.get('posicao') or '?'})"
            f" · {r.get('resultado') or 'sem resultado'} · KDA {r.get('kda')} · "
            f"part. abates {round((r.get('kp_final') or 0) * 100)}% · CS/min {r.get('cs_por_min')}"
            f" · visão {r.get('placar_visao')} · duração {r.get('duracao')} · mortes em {mortes}"
            + (f" · momentos anotados {', '.join(r['momentos_anotados'])}"
               if r.get("momentos_anotados") else "")
            + f" · aliados {', '.join(r.get('aliados', []))} · inimigos {', '.join(r.get('inimigos', []))}")
    stats = coach.estatisticas_pool()
    pool = "; ".join(f"{c}: {v}V {d}D" for c, (v, d) in stats.items() if v + d)
    builds = "; ".join(f"{c}: {', '.join(b['itens'])}" for c, b in coach.BUILDS.items())
    return (f"Hoje: {datetime.now():%d/%m/%Y %H:%M}\n"
            f"Perfil: {coach.texto_perfil()}\n"
            f"Pool (temporada + partidas registradas): {pool}\n"
            f"Builds usadas (patch {coach.INFO_BUILDS.get('patch')}): {builds}\n\n"
            f"Últimas {len(partidas)} partidas registradas pelo coach:\n"
            + ("\n".join(linhas) if linhas else "(nenhuma ainda)"))


# ---------------------------------------------------------------------------
# Conversa
# ---------------------------------------------------------------------------
class ErroIA(Exception):
    pass


def perguntar(historico: list[dict], pergunta: str, chave: str,
              modelo: str = "claude-sonnet-5-5", max_tokens: int = 900) -> str:
    """historico = [{"role": "user"|"assistant", "content": "..."}]. Não altera a lista."""
    mensagens = historico[-12:] + [{"role": "user", "content": pergunta}]
    corpo = {"model": modelo, "max_tokens": max_tokens,
             "system": SISTEMA + "\n\nDADOS DO JOGADOR\n" + contexto(),
             "messages": mensagens}
    try:
        r = requests.post(URL, timeout=60, json=corpo, headers={
            "x-api-key": chave, "anthropic-version": "2023-06-01",
            "content-type": "application/json"})
    except requests.RequestException as e:
        raise ErroIA("Sem conexão com a API do Claude.") from e
    if r.status_code == 401:
        raise ErroIA("Chave da API inválida. Confira em Configurações.")
    if r.status_code == 429:
        raise ErroIA("Muitas perguntas seguidas ou limite da conta. Tente em instantes.")
    if r.status_code >= 400:
        try:
            msg = r.json().get("error", {}).get("message", r.text)
        except ValueError:
            msg = r.text
        raise ErroIA(f"Erro da API ({r.status_code}): {msg[:200]}")
    dados = r.json()
    return "".join(b.get("text", "") for b in dados.get("content", [])
                   if b.get("type") == "text").strip()


def plano_por_ia(jogo_resumo: dict, chave: str, modelo: str) -> str:
    """Plano curto de pré-partida (3 frases) para ser falado na tela de carregamento."""
    pergunta = ("A partida está carregando. Composição (campeão e função): "
                + json.dumps(jogo_resumo, ensure_ascii=False)
                + "\nDê um plano de jogo em no máximo 3 frases curtas, para ser falado em voz: "
                  "condição de vitória do meu time, a principal ameaça e o que eu devo fazer "
                  "nos primeiros 10 minutos na minha função. Sem listas, sem títulos.")
    return perguntar([], pergunta, chave, modelo, max_tokens=250)
