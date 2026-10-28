"""
Relatório LoL — evolução das suas partidas
==========================================

Lê os resumos que o coach salva em ./partidas/ e gera uma página HTML com
gráficos (participação em abates, mortes antes dos 14 min), números por
campeão, por horário e os momentos que você marcou com "Quíron anota".

Uso (na mesma pasta do coach_lol.py):
    python relatorio_lol.py            # últimos 7 dias
    python relatorio_lol.py --dias 30  # últimos 30 dias
    python relatorio_lol.py --dias 0   # tudo

Gera relatorio_lol.html e abre no navegador. Não precisa de internet.
"""

import argparse
import json
import os
import sys
import webbrowser
from datetime import datetime, timedelta
from pathlib import Path

def _pasta_dados() -> Path:
    """Instalado (.exe): %APPDATA%\\Quiron. Rodando o .py: a pasta do script."""
    if getattr(sys, "frozen", False):
        pasta = Path(os.environ.get("APPDATA", str(Path.home()))) / "Quiron"
        pasta.mkdir(parents=True, exist_ok=True)
        return pasta
    return Path(__file__).parent


PASTA = _pasta_dados()
PASTA_PARTIDAS = PASTA / "partidas"
SAIDA = PASTA / "relatorio_lol.html"


def ler_partidas(dias: int) -> list[dict]:
    limite = datetime.now() - timedelta(days=dias) if dias else None
    partidas = []
    for arq in sorted(PASTA_PARTIDAS.glob("*.json")):
        try:
            r = json.loads(arq.read_text(encoding="utf-8"))
            r["_quando"] = datetime.fromisoformat(r["data"])
        except (ValueError, OSError, KeyError):
            continue
        if limite and r["_quando"] < limite:
            continue
        partidas.append(r)
    partidas.sort(key=lambda r: r["_quando"])
    return partidas


def media(valores):
    valores = [v for v in valores if v is not None]
    return sum(valores) / len(valores) if valores else None


def montar_dados(partidas: list[dict]) -> dict:
    jogos = []
    for i, r in enumerate(partidas, 1):
        kp = r.get("kp_final")
        jogos.append({
            "n": i,
            "quando": r["_quando"].strftime("%d/%m %H:%M"),
            "campeao": r.get("campeao", "?"),
            "resultado": r.get("resultado") or "—",
            "kda": r.get("kda", ""),
            "kp": round(kp * 100) if kp is not None else None,
            "mortes14": r.get("mortes_antes_14", 0),
            "cs_min": r.get("cs_por_min"),
            "visao": r.get("placar_visao"),
            "duracao": r.get("duracao", ""),
            "anotacoes": r.get("momentos_anotados", []),
            "posicao": r.get("posicao") or "",
        })

    com_resultado = [j for j in jogos if j["resultado"] in ("vitória", "derrota")]
    vitorias = sum(j["resultado"] == "vitória" for j in com_resultado)

    por_campeao = {}
    for j in jogos:
        por_campeao.setdefault(j["campeao"], []).append(j)
    tabela_campeoes = []
    for c, js in sorted(por_campeao.items(), key=lambda kv: -len(kv[1])):
        res = [j for j in js if j["resultado"] in ("vitória", "derrota")]
        v = sum(j["resultado"] == "vitória" for j in res)
        tabela_campeoes.append({
            "campeao": c, "partidas": len(js), "v": v, "d": len(res) - v,
            "taxa": round(100 * v / len(res)) if res else None,
            "kp": media([j["kp"] for j in js]),
            "mortes14": media([j["mortes14"] for j in js]),
            "cs_min": media([j["cs_min"] for j in js if j["posicao"] != "UTILITY"]),
            "visao": media([j["visao"] for j in js]),
        })

    faixas = [("Madrugada (0h–6h)", 0, 6), ("Manhã (6h–12h)", 6, 12),
              ("Tarde (12h–18h)", 12, 18), ("Noite (18h–24h)", 18, 24)]
    tabela_horarios = []
    for nome, ini, fim in faixas:
        res = [r for r in partidas if ini <= r["_quando"].hour < fim
               and r.get("resultado") in ("vitória", "derrota")]
        if res:
            v = sum(r["resultado"] == "vitória" for r in res)
            tabela_horarios.append({"faixa": nome, "partidas": len(res),
                                    "taxa": round(100 * v / len(res))})

    return {
        "jogos": jogos,
        "resumo": {
            "partidas": len(jogos),
            "taxa": round(100 * vitorias / len(com_resultado)) if com_resultado else None,
            "v": vitorias, "d": len(com_resultado) - vitorias,
            "kp": media([j["kp"] for j in jogos]),
            "mortes14": media([j["mortes14"] for j in jogos]),
            "visao": media([j["visao"] for j in jogos]),
        },
        "campeoes": tabela_campeoes,
        "horarios": tabela_horarios,
        "anotadas": [j for j in jogos if j["anotacoes"]],
    }


HTML = r"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Relatório Quíron</title>
<style>
:root {
  color-scheme: light;
  --surface-0: #f4f3ef; --surface-1: #fcfcfb; --border: #e3e1da;
  --text-primary: #0b0b0b; --text-secondary: #52514e; --text-muted: #7a7974;
  --grid: #ebe9e3; --series-1: #2a78d6; --ref: #9b9a94;
  --good: #1a7f37; --bad: #c4372f;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    color-scheme: dark;
    --surface-0: #111110; --surface-1: #1a1a19; --border: #2e2e2c;
    --text-primary: #f0efec; --text-secondary: #c3c2b7; --text-muted: #8f8e88;
    --grid: #292927; --series-1: #3987e5; --ref: #6f6e69;
    --good: #4ac26b; --bad: #f0706a;
  }
}
:root[data-theme="dark"] {
  color-scheme: dark;
  --surface-0: #111110; --surface-1: #1a1a19; --border: #2e2e2c;
  --text-primary: #f0efec; --text-secondary: #c3c2b7; --text-muted: #8f8e88;
  --grid: #292927; --series-1: #3987e5; --ref: #6f6e69;
  --good: #4ac26b; --bad: #f0706a;
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--surface-0); color: var(--text-primary);
  font: 15px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif; }
main { max-width: 1040px; margin: 0 auto; padding: 32px 16px 64px; }
h1 { font-size: 26px; margin: 0 0 4px; letter-spacing: -0.01em; }
h2 { font-size: 17px; margin: 0 0 4px; }
.sub { color: var(--text-secondary); margin: 0 0 24px; }
.nota { color: var(--text-secondary); font-size: 13px; margin: 0 0 12px; }
.tiles { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 12px; margin-bottom: 24px; }
.tile, .card { background: var(--surface-1); border: 1px solid var(--border);
  border-radius: 12px; padding: 16px; }
.tile .rot { color: var(--text-secondary); font-size: 13px; }
.tile .val { font-size: 28px; font-weight: 650; font-variant-numeric: tabular-nums; }
.tile .det { color: var(--text-muted); font-size: 12px; }
.card { margin-bottom: 16px; }
.grid2 { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 16px; }
.grid2 .card { margin-bottom: 0; }
svg { display: block; width: 100%; height: auto; overflow: visible; }
svg text { fill: var(--text-muted); font-size: 11px; font-family: inherit; }
.tip { position: fixed; pointer-events: none; background: var(--surface-1);
  border: 1px solid var(--border); border-radius: 8px; padding: 8px 10px;
  font-size: 13px; box-shadow: 0 4px 16px rgba(0,0,0,.12); display: none; z-index: 10; }
.tip b { font-variant-numeric: tabular-nums; }
.tabela { width: 100%; overflow-x: auto; }
table { width: 100%; border-collapse: collapse; font-size: 14px; }
th, td { text-align: left; padding: 8px 10px; border-bottom: 1px solid var(--border);
  white-space: nowrap; }
th { color: var(--text-secondary); font-weight: 550; font-size: 13px; }
td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; }
.vit { color: var(--good); } .der { color: var(--bad); }
.vazio { color: var(--text-secondary); padding: 48px 0; text-align: center; }
details summary { cursor: pointer; color: var(--text-secondary); font-size: 14px; }
ul.anot { margin: 8px 0 0; padding-left: 20px; }
</style>
</head>
<body>
<main>
  <h1>Relatório Quíron</h1>
  <p class="sub" id="periodo"></p>
  <div id="conteudo"></div>
</main>
<div class="tip" id="tip"></div>
<script>
const DADOS = __DADOS__;
const PERIODO = __PERIODO__;
const $ = (s) => document.querySelector(s);
const fmt = (v, d = 0) => v == null ? "—" : v.toFixed(d).replace(".", ",");
const esc = (s) => String(s).replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));

$("#periodo").textContent = PERIODO + " · gerado em " + new Date().toLocaleString("pt-BR");

const r = DADOS.resumo;
if (!r.partidas) {
  $("#conteudo").innerHTML = '<p class="vazio">Nenhuma partida registrada neste período. ' +
    'Jogue com o coach_lol.py aberto e rode o relatório de novo.</p>';
} else {
  render();
}

function tile(rot, val, det) {
  return `<div class="tile"><div class="rot">${rot}</div><div class="val">${val}</div>` +
         `<div class="det">${det || ""}</div></div>`;
}

function render() {
  let h = '<div class="tiles">' +
    tile("Partidas", r.partidas, `${r.v} vitórias · ${r.d} derrotas`) +
    tile("Taxa de vitória", r.taxa == null ? "—" : r.taxa + "%", "partidas com resultado") +
    tile("Participação em abates", fmt(r.kp) + "%", "média · meta: 50% ou mais") +
    tile("Mortes antes dos 14 min", fmt(r.mortes14, 1), "média por partida") +
    tile("Placar de visão", fmt(r.visao), "média por partida") +
    '</div>';

  h += '<div class="grid2">' +
    '<div class="card"><h2>Participação em abates por partida</h2>' +
    '<p class="nota">Linha tracejada: 50%, a meta. Passe o mouse para ver cada partida.</p>' +
    '<div id="g-kp"></div></div>' +
    '<div class="card"><h2>Mortes antes dos 14 minutos</h2>' +
    '<p class="nota">Menos é melhor. Mortes cedo custam ouro e objetivos.</p>' +
    '<div id="g-mortes"></div></div></div><div style="height:16px"></div>';

  h += '<div class="card"><h2>Por campeão</h2><div class="tabela"><table><thead><tr>' +
    '<th>Campeão</th><th class="num">Partidas</th><th class="num">V–D</th>' +
    '<th class="num">Vitória</th><th class="num">Part. abates</th>' +
    '<th class="num">Mortes &lt;14</th><th class="num">CS/min</th><th class="num">Visão</th>' +
    '</tr></thead><tbody>' +
    DADOS.campeoes.map(c => `<tr><td>${esc(c.campeao)}</td><td class="num">${c.partidas}</td>` +
      `<td class="num">${c.v}–${c.d}</td><td class="num">${c.taxa == null ? "—" : c.taxa + "%"}</td>` +
      `<td class="num">${fmt(c.kp)}%</td><td class="num">${fmt(c.mortes14, 1)}</td>` +
      `<td class="num">${fmt(c.cs_min, 1)}</td><td class="num">${fmt(c.visao)}</td></tr>`).join("") +
    '</tbody></table></div><p class="nota" style="margin-top:8px">CS/min não conta partidas de suporte.</p></div>';

  if (DADOS.horarios.length) {
    h += '<div class="card"><h2>Por horário</h2><div class="tabela"><table><thead><tr>' +
      '<th>Horário</th><th class="num">Partidas</th><th class="num">Vitória</th></tr></thead><tbody>' +
      DADOS.horarios.map(x => `<tr><td>${x.faixa}</td><td class="num">${x.partidas}</td>` +
        `<td class="num">${x.taxa}%</td></tr>`).join("") + '</tbody></table></div></div>';
  }

  h += '<div class="card"><h2>Momentos anotados</h2>';
  if (DADOS.anotadas.length) {
    h += '<p class="nota">Para revisar: mande o arquivo da partida (pasta partidas) e, se puder, ' +
      'o replay ou um trecho gravado para o Claude comentar cada momento.</p><ul class="anot">' +
      DADOS.anotadas.map(j => `<li>${j.quando} · ${esc(j.campeao)} (${j.resultado}): ` +
        j.anotacoes.join(", ") + '</li>').join("") + '</ul>';
  } else {
    h += '<p class="nota">Nenhum momento anotado. Durante a partida, diga “Quíron anota” (ou a sua palavra de chamada + “anota”).</p>';
  }
  h += '</div>';

  h += '<div class="card"><details><summary>Todas as partidas (' + DADOS.jogos.length + ')</summary>' +
    '<div class="tabela"><table><thead><tr><th>#</th><th>Quando</th><th>Campeão</th><th>Resultado</th>' +
    '<th>KDA</th><th class="num">Part. abates</th><th class="num">Mortes &lt;14</th>' +
    '<th class="num">CS/min</th><th class="num">Visão</th><th>Duração</th></tr></thead><tbody>' +
    DADOS.jogos.slice().reverse().map(j => `<tr><td>${j.n}</td><td>${j.quando}</td><td>${esc(j.campeao)}</td>` +
      `<td class="${j.resultado === "vitória" ? "vit" : j.resultado === "derrota" ? "der" : ""}">${j.resultado}</td>` +
      `<td>${j.kda}</td><td class="num">${j.kp == null ? "—" : j.kp + "%"}</td>` +
      `<td class="num">${j.mortes14}</td><td class="num">${fmt(j.cs_min, 1)}</td>` +
      `<td class="num">${fmt(j.visao)}</td><td>${j.duracao}</td></tr>`).join("") +
    '</tbody></table></div></details></div>';

  $("#conteudo").innerHTML = h;
  grafico("#g-kp", "linha", DADOS.jogos.map(j => j.kp), {min: 0, max: 100, ref: 50, suf: "%"});
  const maxM = Math.max(3, ...DADOS.jogos.map(j => j.mortes14));
  grafico("#g-mortes", "barras", DADOS.jogos.map(j => j.mortes14), {min: 0, max: maxM, suf: ""});
}

function grafico(sel, tipo, valores, o) {
  const W = 480, H = 220, m = {t: 10, r: 12, b: 26, l: 34};
  const iw = W - m.l - m.r, ih = H - m.t - m.b, n = valores.length;
  const x = i => m.l + (n === 1 ? iw / 2 : (tipo === "barras" ? (i + 0.5) * iw / n : i * iw / (n - 1)));
  const y = v => m.t + ih - (v - o.min) / (o.max - o.min) * ih;
  let s = `<svg viewBox="0 0 ${W} ${H}" role="img">`;
  const passo = o.max <= 6 ? 1 : (o.max <= 20 ? 5 : 25);
  for (let v = o.min; v <= o.max; v += passo) {
    s += `<line x1="${m.l}" x2="${W - m.r}" y1="${y(v)}" y2="${y(v)}" stroke="var(--grid)" stroke-width="1"/>`;
    s += `<text x="${m.l - 6}" y="${y(v) + 4}" text-anchor="end">${v}${o.suf}</text>`;
  }
  if (o.ref != null)
    s += `<line x1="${m.l}" x2="${W - m.r}" y1="${y(o.ref)}" y2="${y(o.ref)}" stroke="var(--ref)" stroke-width="1.5" stroke-dasharray="4 4"/>`;
  const rotulos = [0, Math.floor((n - 1) / 2), n - 1].filter((v, i, a) => a.indexOf(v) === i);
  rotulos.forEach(i => s += `<text x="${x(i)}" y="${H - 6}" text-anchor="middle">#${i + 1}</text>`);
  if (tipo === "linha") {
    const pts = valores.map((v, i) => v == null ? null : [x(i), y(v)]);
    let d = "", novo = true;
    pts.forEach(p => { if (!p) { novo = true; return; } d += (novo ? "M" : "L") + p[0] + " " + p[1]; novo = false; });
    s += `<path d="${d}" fill="none" stroke="var(--series-1)" stroke-width="2" stroke-linejoin="round"/>`;
    pts.forEach(p => { if (p) s += `<circle cx="${p[0]}" cy="${p[1]}" r="4" fill="var(--series-1)" stroke="var(--surface-1)" stroke-width="2"/>`; });
  } else {
    const bw = Math.max(2, Math.min(18, iw / n - 2));
    valores.forEach((v, i) => {
      if (!v) return;
      const top = y(v), alt = y(o.min) - top, rr = Math.min(4, bw / 2, alt);
      const xl = x(i) - bw / 2, xr = x(i) + bw / 2, base = y(o.min);
      s += `<path d="M${xl} ${base}V${top + rr}Q${xl} ${top} ${xl + rr} ${top}H${xr - rr}Q${xr} ${top} ${xr} ${top + rr}V${base}Z" fill="var(--series-1)"/>`;
    });
  }
  // alvos de hover (maiores que a marca)
  valores.forEach((v, i) => {
    const w = n === 1 ? iw : iw / n;
    s += `<rect class="hit" data-i="${i}" x="${x(i) - w / 2}" y="${m.t}" width="${w}" height="${ih}" fill="transparent"/>`;
  });
  s += "</svg>";
  const el = $(sel); el.innerHTML = s;
  const tip = $("#tip");
  el.querySelectorAll(".hit").forEach(h => {
    h.addEventListener("mousemove", ev => {
      const j = DADOS.jogos[+h.dataset.i], v = valores[+h.dataset.i];
      tip.innerHTML = `Partida #${j.n} · ${j.quando}<br>${esc(j.campeao)} · ${j.resultado}<br>` +
        `<b>${v == null ? "—" : v + o.suf}</b>`;
      tip.style.display = "block";
      tip.style.left = Math.min(ev.clientX + 14, innerWidth - 200) + "px";
      tip.style.top = (ev.clientY + 14) + "px";
    });
    h.addEventListener("mouseleave", () => tip.style.display = "none");
  });
}
</script>
</body>
</html>
"""


def gerar(dias: int = 7, abrir: bool = True) -> tuple[Path, int]:
    """Gera relatorio_lol.html e (opcionalmente) abre no navegador."""
    partidas = ler_partidas(dias)
    dados = montar_dados(partidas)
    periodo = f"Últimos {dias} dias" if dias else "Todas as partidas registradas"
    html = (HTML.replace("__DADOS__", json.dumps(dados, ensure_ascii=False))
                .replace("__PERIODO__", json.dumps(periodo, ensure_ascii=False)))
    SAIDA.write_text(html, encoding="utf-8")
    if abrir:
        webbrowser.open(SAIDA.as_uri())
    return SAIDA, len(partidas)


def main():
    ap = argparse.ArgumentParser(description="Relatório das partidas registradas pelo coach")
    ap.add_argument("--dias", type=int, default=7, help="quantos dias para trás (0 = tudo)")
    ap.add_argument("--nao-abrir", action="store_true", help="só gera o arquivo")
    args = ap.parse_args()
    saida, n = gerar(args.dias, not args.nao_abrir)
    print(f"Relatório gerado: {saida} ({n} partidas)")


if __name__ == "__main__":
    main()
