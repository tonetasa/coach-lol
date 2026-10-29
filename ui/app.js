/* Quíron — interface. Fala com o Python por window.pywebview.api (ponte do pywebview). */
"use strict";
window.__erros = [];
window.addEventListener("error", e => window.__erros.push(String(e.message)));
window.addEventListener("unhandledrejection", e => window.__erros.push("promessa: " + String(e.reason)));

// ---------------------------------------------------------------------------
// Ponte com o Python
// ---------------------------------------------------------------------------
let api = null;
function prepararApi() {
  return new Promise(resolve => {
    if (window.pywebview && window.pywebview.api && window.pywebview.api.inicial) {
      api = window.pywebview.api; return resolve();
    }
    window.addEventListener("pywebviewready", () => { api = window.pywebview.api; resolve(); });
    // Modo de teste (navegador comum + servidor de desenvolvimento)
    if (location.search.includes("dev")) {
      api = new Proxy({}, {get: (_, nome) => (...args) =>
        fetch("/api/" + nome, {method: "POST", body: JSON.stringify(args)}).then(r => r.json())});
      (async function ouvir() {
        for (;;) {
          try {
            const evs = await fetch("/eventos").then(r => r.json());
            evs.forEach(ev => window.quiron.evento(ev));
          } catch (e) { await new Promise(r => setTimeout(r, 1000)); }
        }
      })();
      resolve();
    }
  });
}

// ---------------------------------------------------------------------------
// Utilidades
// ---------------------------------------------------------------------------
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = t => String(t ?? "").replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
const num = (v, d = 0) => v == null ? "—" : Number(v).toFixed(d).replace(".", ",");
const DD = "https://ddragon.leagueoflegends.com/cdn";
const url = {
  camp: id => `${DD}/${S.ddragon}/img/champion/${id}.png`,
  item: id => `${DD}/${S.ddragon}/img/item/${id}.png`,
  perfil: id => `${DD}/${S.ddragon}/img/profileicon/${id}.png`,
  runa: caminho => `${DD}/img/${caminho}`,
  feitico: arq => `${DD}/${S.ddragon}/img/spell/${arq}.png`,
};
const img = (src, cls = "ic", w = 40, lazy = false) =>
  src ? `<img class="${cls}" src="${esc(src)}" width="${w}" height="${w}" alt=""${lazy ? ' loading="lazy"' : ""} onerror="this.style.visibility='hidden'">` :
        `<div class="${cls}" style="width:${w}px;height:${w}px"></div>`;
const icone = (id, w = 40) => `<svg width="${w}" height="${w}"><use href="#i-${id}"/></svg>`;

function toast(texto, ms = 4200) {
  const t = document.createElement("div");
  t.className = "toast"; t.textContent = texto;
  $("#toasts").append(t);
  setTimeout(() => t.remove(), ms);
}
function painel(titulo, sub, corpo, extra = "") {
  return `<div class="painel"><div class="dentro">
    <div class="topo-painel"><div>${titulo ? `<h2>${titulo}</h2>` : ""}${sub ? `<div class="sub">${sub}</div>` : ""}</div>${extra}</div>
    ${corpo}</div></div>`;
}
function interruptor(chave, valor, extra = "") {
  return `<div class="sw ${valor ? "on" : ""}" data-chave="${chave}" ${extra} role="switch" aria-checked="${!!valor}"></div>`;
}

// Emblema de elo (desenho próprio, não é o emblema oficial)
const CORES_ELO = {Ferro: ["#9aa3ab", "#4b5258"], Bronze: ["#e0a27a", "#7a4a2c"], Prata: ["#dfe8ef", "#7d8c98"],
  Ouro: ["#ffe08a", "#b07d1f"], Platina: ["#8ff0e0", "#1d8a80"], Esmeralda: ["#7cf3b6", "#119a63"],
  Diamante: ["#9fd4ff", "#3a62d6"], Mestre: ["#e2a6ff", "#8a3ac2"], "Grão-Mestre": ["#ff9a8f", "#b3261e"],
  Desafiante: ["#fff1b8", "#3aa0e8"]};
function emblema(elo) {
  const tier = (elo || "").split(" ")[0];
  const [c1, c2] = CORES_ELO[tier] || ["#56687a", "#2a3846"];
  const id = "ge" + Math.random().toString(36).slice(2, 7);
  return `<svg viewBox="0 0 32 32"><defs><linearGradient id="${id}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${c1}"/><stop offset="1" stop-color="${c2}"/></linearGradient></defs>
    <path d="M16 2 L28 12 L16 30 L4 12z" fill="url(#${id})" stroke="#f2fbff" stroke-width="1.1"/><path d="M4 12h24M16 2l-5 10 5 18 5-18z" stroke="#000" stroke-opacity=".25" stroke-width="1" fill="none"/></svg>`;
}

// Teia (gráfico de radar) com notas de 0 a 100
function teia(eixos, tam = 230) {
  const m = 34, n = eixos.length, cx = tam / 2 + m, cy = tam / 2 + 6, r = tam * 0.31;
  const ponto = (i, f) => {
    const a = -Math.PI / 2 + i * 2 * Math.PI / n;
    return [cx + Math.cos(a) * r * f, cy + Math.sin(a) * r * f];
  };
  let s = `<svg class="teia" viewBox="0 0 ${tam + 2 * m} ${tam + 6}" width="${tam + 2 * m}" height="${tam + 6}">`;
  for (const f of [0.25, 0.5, 0.75, 1]) {
    s += `<polygon points="${eixos.map((_, i) => ponto(i, f).join(",")).join(" ")}" fill="none" stroke="#3a5166" stroke-width="${f === 1 ? 1.4 : .8}"/>`;
  }
  eixos.forEach((_, i) => { const [x, y] = ponto(i, 1); s += `<line x1="${cx}" y1="${cy}" x2="${x}" y2="${y}" stroke="#2c4255"/>`; });
  const tem = eixos.some(e => e.nota != null);
  if (tem) {
    const pts = eixos.map((e, i) => ponto(i, (e.nota ?? 0) / 100).join(",")).join(" ");
    s += `<polygon points="${pts}" fill="rgba(79,195,247,.22)" stroke="#4fc3f7" stroke-width="2" style="filter:drop-shadow(0 0 6px rgba(79,195,247,.8))"/>`;
    eixos.forEach((e, i) => { if (e.nota != null) { const [x, y] = ponto(i, e.nota / 100); s += `<circle cx="${x}" cy="${y}" r="3" fill="#e8f8ff"/>`; } });
  }
  eixos.forEach((e, i) => {
    const [x, y] = ponto(i, 1.32);
    s += `<text x="${x}" y="${y}" text-anchor="middle" dominant-baseline="middle">${esc(e.nome)}</text>`;
    if (e.nota != null) s += `<text class="val" x="${x}" y="${y + 15}" text-anchor="middle">${e.nota}</text>`;
  });
  return s + "</svg>";
}

// ---------------------------------------------------------------------------
// Estado
// ---------------------------------------------------------------------------
const S = {
  tela: "coach", ddragon: "15.1.1", config: null, perfil: null, rodando: false, estado: "Parado",
  log: [], vistaCoach: "analise", builds: null, buildSel: null, runasAbertas: new Set(),
  dias: 7, relatorio: null, relatorioTudo: null, ultima: null, vozes: null, mics: null,
  dadosProntos: false, atualizacao: null,
};

const ESTADOS = {
  "Parado": {cor: "#f0a85a", rot: "Parado", dica: "Inicie o coach e deixe o app aberto enquanto joga."},
  "Carregando dados dos campeões...": {cor: "#f0a85a", rot: "Carregando", dica: "Baixando os dados do patch atual."},
  "Aguardando partida": {cor: "#e8c77a", rot: "Aguardando", dica: "Entre na fila. O Quíron acompanha a seleção e a partida."},
  "Partida aceita": {cor: "#4fc3f7", rot: "Aceita", dica: "Partida aceita automaticamente."},
  "Seleção de campeões": {cor: "#4fc3f7", rot: "Seleção", dica: "Lendo a seleção: seu histórico e os campeões inimigos."},
};
function infoEstado(t) {
  if (ESTADOS[t]) return ESTADOS[t];
  if (t.startsWith("Em partida")) {
    const p = S.config ? S.config.palavra_chamada : "Quíron";
    return {cor: "#3ddc97", rot: "Em partida", dica: `${t}. Diga “${p} silêncio” para pausar os avisos.`, vivo: true};
  }
  return {cor: "#f0a85a", rot: t.split(" ")[0], dica: t};
}

// ---------------------------------------------------------------------------
// Eventos que chegam do Python
// ---------------------------------------------------------------------------
window.quiron = {
  evento(ev) {
    const {tipo, dados} = ev;
    if (tipo === "log") {
      S.log.push(dados); if (S.log.length > 500) S.log.shift();
      const feed = $("#feed");
      if (feed) { feed.insertAdjacentHTML("beforeend", linhaLog(dados)); feed.scrollTop = feed.scrollHeight; }
      if (!S.rodando || S.estado === "Parado") toast(dados);
    } else if (tipo === "estado") {
      S.estado = dados; desenharStatus();
      if (dados.startsWith("Em partida") && S.vistaCoach !== "avisos") { S.vistaCoach = "avisos"; desenharCoach(); }
    } else if (tipo === "rodando") {
      S.rodando = dados; desenharStatus();
    } else if (tipo === "parando") {
      const b = $("#bt-coach"); if (b) { b.disabled = true; b.lastElementChild.textContent = "Parando…"; }
    } else if (tipo === "dados_prontos") {
      S.ddragon = dados.ddragon; S.dadosProntos = true;
      carregarBuilds(); carregarCoach();
      if (dados.precisa_perfil) setTimeout(() => modalPerfil(true), 300);
    } else if (tipo === "builds") {
      carregarBuilds();
    } else if (tipo === "partidas") {
      carregarCoach(); if (S.tela === "relatorio") carregarRelatorio();
    } else if (tipo === "atualizacao") {
      mostrarFaixa(dados);
    } else if (tipo === "progresso") {
      const b = $("#faixa-atualizar");
      if (dados == null) { b.disabled = false; b.textContent = "Atualizar agora"; }
      else { b.disabled = true; b.textContent = `Baixando… ${dados}%`; }
    }
  },
};
function linhaLog(t) {
  const m = /^(\[\d\d:\d\d\])\s?(.*)$/s.exec(t);
  return `<div>${m ? `<span class="t">${esc(m[1])}</span> ${esc(m[2])}` : esc(t)}</div>`;
}

// ---------------------------------------------------------------------------
// Navegação
// ---------------------------------------------------------------------------
function irPara(tela) {
  S.tela = tela;
  $$(".aba").forEach(a => a.classList.toggle("ativa", a.dataset.tela === tela));
  $$(".tela").forEach(t => t.classList.toggle("ativa", t.id === "tela-" + tela));
  if (tela === "relatorio") carregarRelatorio();
  if (tela === "builds") carregarBuilds();
  if (tela === "config") desenharConfig();
}
$("#abas").addEventListener("click", e => { const a = e.target.closest(".aba"); if (a) irPara(a.dataset.tela); });

function mostrarFaixa(info) {
  S.atualizacao = info;
  $("#faixa-txt").textContent = `Versão ${info.versao} disponível (você tem a ${S.versao}).`;
  $("#faixa").classList.remove("oculto");
  $("#faixa-atualizar").textContent = info.url ? "Atualizar agora" : "Baixar";
}
$("#faixa-novidades").onclick = () => api.ver_novidades();
$("#faixa-atualizar").onclick = () => api.atualizar_app();

// ---------------------------------------------------------------------------
// COACH
// ---------------------------------------------------------------------------
async function carregarCoach() {
  try { S.ultima = await api.ultima_partida(); } catch (e) { S.ultima = null; }
  desenharCoach();
}
function desenharCoach() {
  const u = S.ultima;
  const ultimaHtml = u ? `
    <div><small>Última partida:</small>
      <b class="${u.resultado === "vitória" ? "ok" : u.resultado === "derrota" ? "ruim" : ""}">${esc(u.campeao)}</b>
      <small style="font-size:13px;color:var(--texto2)">${esc(u.resultado || "")} · ${esc(u.kda || "")} · ${esc(u.quando)}</small></div>
    ${img(url.camp(u.id), "ic camp", 52)}` : `<div><small>Última partida:</small><b class="fraco">nenhuma ainda</b></div>`;

  const t = u && u.teia;
  const analise = !u ? `<p class="vazio">Jogue uma partida com o Quíron ligado: aqui aparece o resumo dela e a sua teia de desempenho dos últimos 7 dias.</p>` : `
    <div class="corpo">
      <div>${teia(t.eixos, 250)}</div>
      <ul>${u.pontos.map(p => `<li>${esc(p)}</li>`).join("")}
        ${t.fraco ? `<li>Ponto para melhorar nos últimos 7 dias: <b class="ouro-t">${esc(t.dica.eixo)}</b>.</li>` : ""}</ul>
      <div class="dica cartao"><h4>Dica rápida do dia</h4>
        <p>${esc(t.dica ? t.dica.texto : "Jogue algumas partidas para receber dicas.")}</p>
        ${t.dica ? `<small>Foco: ${esc(t.dica.eixo)}</small>` : ""}</div>
    </div>`;

  $("#tela-coach").innerHTML = painel("", "", `
    <div class="coach">
      <div class="topo">
        <div class="cartao status" id="status"></div>
        <div class="lado">
          <button class="bt grande" id="bt-coach"></button>
          <div class="cartao ultima">${ultimaHtml}</div>
        </div>
      </div>
      <div class="cartao analise">
        <div class="cab"><h3>${S.vistaCoach === "avisos" ? "Avisos ao vivo" : "Última análise (resumo)"}</h3>
          <div class="seg" id="vista-coach">
            <button data-v="analise" class="${S.vistaCoach === "analise" ? "on" : ""}">Análise</button>
            <button data-v="avisos" class="${S.vistaCoach === "avisos" ? "on" : ""}">Avisos</button></div></div>
        ${S.vistaCoach === "avisos" ? `<div class="feed" id="feed">${S.log.map(linhaLog).join("")}</div>` : analise}
      </div>
    </div>`);
  desenharStatus();
  const feed = $("#feed"); if (feed) feed.scrollTop = feed.scrollHeight;
  $("#bt-coach").onclick = () => api.alternar();
  $("#vista-coach").onclick = e => { const b = e.target.closest("button"); if (b) { S.vistaCoach = b.dataset.v; desenharCoach(); } };
}
function desenharStatus() {
  const el = $("#status"); if (!el) return;
  const i = infoEstado(S.estado);
  el.innerHTML = `
    <div class="anel ${i.vivo ? "vivo" : ""}" style="--cor:${i.cor}"><div class="a1"></div><div class="a2"></div><div class="a3"></div>
      <div class="rot"><small>STATUS:</small><b>${esc(i.rot)}</b></div></div>
    <div class="txt" style="--cor-estado:${i.cor}"><h3>${esc(S.estado.replace(/\s*\(.*\)$/, ""))}</h3><p>${esc(i.dica)}</p></div>`;
  const b = $("#bt-coach");
  if (b) {
    b.disabled = false;
    b.classList.toggle("perigo", S.rodando);
    b.innerHTML = S.rodando ? `${icone("parar", 30)}<span>Parar coach</span>` : `${icone("leao", 34)}<span>Iniciar coach</span>`;
  }
}

// ---------------------------------------------------------------------------
// BUILDS
// ---------------------------------------------------------------------------
async function carregarBuilds() {
  if (!S.dadosProntos) { $("#tela-builds").innerHTML = painel("", "", `<p class="vazio">Carregando campeões e itens do patch…</p>`); return; }
  const [b, r] = await Promise.all([api.builds(), api.relatorio(0)]);
  S.builds = b; S.relatorioTudo = r;
  if (!S.buildSel || ![...b.pool, ...b.outros].some(x => x.id === S.buildSel)) S.buildSel = (b.pool[0] || b.outros[0] || {}).id;
  desenharBuilds();
}
function cartaoBuild(b) {
  const itens = b.itens.map((it, i) => `<div class="it">${img(it.id && url.item(it.id), "", 44)}<span title="${esc(it.nome)}">${esc(it.nome)}</span></div>${i < b.itens.length - 1 ? `<div class="seta">›</div>` : ""}`).join("");
  const inicio = b.inicio.length ? `<div class="it">${img(b.inicio[0].id && url.item(b.inicio[0].id), "", 44)}<span>${esc(b.inicio[0].nome)}</span></div><div class="barra"></div>` : "";
  const selo = b.selo ? `<span class="tag ${b.selo === "personalizada" ? "ouro" : "cinza"}">${esc(b.selo)}</span>` : "";
  const aberto = S.runasAbertas.has(b.id);
  return `<div class="cartao build ${S.buildSel === b.id ? "sel" : ""}" data-id="${b.id}">
    <div class="topo">${img(url.camp(b.id), "ic camp", 46)}
      <div><div class="nome">${esc(b.nome)}</div><div class="func">${esc(b.funcao_nome)} ${selo}</div></div>
      ${b.taxa != null ? `<div class="wr">${b.taxa}% WR <small class="fraco">(${b.vitorias + b.derrotas})</small></div>` : ""}</div>
    <div class="seq">${inicio}${itens}</div>
    <div class="acoes">
      ${b.selo === "genérica" ? `<button class="bt sec pequeno" data-acao="pedir">Pedir build</button>` : ""}
      ${b.selo === "personalizada" ? `<button class="bt sec pequeno" data-acao="restaurar">Restaurar</button>` : ""}
      <button class="bt sec pequeno" data-acao="editar">Editar</button>
      <button class="bt sec pequeno" data-acao="runas">Runas ${aberto ? "▴" : "▾"}</button></div>
    ${aberto ? paginaRunas(b) : ""}
  </div>`;
}
function paginaRunas(b) {
  const p = b.pagina;
  if (!p) return `<div class="runas"><span class="vazio">Página de runas indisponível para esta build${b.runa ? ` (runa principal: ${esc(b.runa)})` : ""}.</span></div>`;
  const col = (a, chave) => `<div class="col"><h5>${img(url.runa(a.icone), "", 22)}${esc(a.nome)}</h5>
    ${a.fileiras.map((f, i) => `<div class="fileira ${chave && i === 0 ? "chave" : ""}">${f.map(r => `<img class="${r.ativa ? "on" : "off"}" src="${esc(url.runa(r.icone))}" title="${esc(r.nome)}" alt="">`).join("")}</div>`).join("")}
    <div class="nomes">${a.escolhidas.map(esc).join("<br>")}</div></div>`;
  const frag = `<div class="col frag"><h5>Fragmentos</h5>${p.fragmentos.map(l => `<div class="fileira">${l.opcoes.map(o => `<img class="${o.ativa ? "on" : "off"}" src="${esc(o.url)}" alt="">`).join("")}</div>`).join("")}
    <div class="nomes">${p.fragmentos.map(f => esc(f.nome)).join("<br>")}</div>
    ${b.feiticos.length ? `<h5 style="margin-top:10px">Feitiços</h5><div class="fileira">${b.feiticos.map(f => `<img class="on" style="border-radius:6px" src="${esc(url.feitico(f.arq))}" title="${esc(f.nome)}" alt="">`).join("")}</div>` : ""}</div>`;
  return `<div class="runas">${col(p.primaria, true)}${col(p.secundaria, false)}${frag}</div>`;
}
function desenharBuilds() {
  const b = S.builds, info = b.info;
  const lista = `
    ${b.pool.length ? `<div class="grupo-tit">Seu pool</div>${b.pool.map(cartaoBuild).join("")}` :
      `<p class="vazio">Configure seu pool no perfil (Configurações) para ver as builds dos seus campeões aqui.</p>`}
    ${b.outros.length ? `<div class="grupo-tit">Outras builds</div>${b.outros.map(cartaoBuild).join("")}` : ""}`;
  $("#tela-builds").innerHTML = `
    <div class="builds-cab"><div class="info">Patch ${esc(info.patch)} <small>· ${esc(info.fonte)}${info.atualizado ? ", " + esc(info.atualizado) : ""}</small></div>
      <button class="bt" id="bt-nova">+ Campeão</button>
      <button class="bt sec" id="bt-buscar-builds">Buscar atualização</button>
      <button class="bt sec" id="bt-doc">Documento</button></div>
    <div class="builds">
      ${painel("", "", `<div class="rolagem lista-builds" style="margin-top:0">${lista}</div>`)}
      ${painel("Desempenho", "do campeão selecionado", `<div class="rolagem desemp" id="desemp"></div>`)}
    </div>`;
  $("#bt-nova").onclick = () => editorBuild(null);
  $("#bt-buscar-builds").onclick = () => { api.buscar_builds(); toast("Buscando builds…"); };
  $("#bt-doc").onclick = () => api.abrir_url("builds");
  $(".lista-builds").onclick = async e => {
    const card = e.target.closest(".build"); if (!card) return;
    const id = card.dataset.id, acao = e.target.closest("[data-acao]")?.dataset.acao;
    if (e.target.closest(".runas")) return;
    if (acao === "editar") return editorBuild(id);
    if (acao === "restaurar") { await api.build_restaurar(id); return carregarBuilds(); }
    if (acao === "pedir") return api.pedir_build(id);
    if (acao === "runas") { S.runasAbertas.has(id) ? S.runasAbertas.delete(id) : S.runasAbertas.add(id); }
    S.buildSel = id;
    const rol = $(".lista-builds").scrollTop; desenharBuilds(); $(".lista-builds").scrollTop = rol;
  };
  desenharDesempenho();
}
function desenharDesempenho() {
  const el = $("#desemp"); if (!el) return;
  const b = [...S.builds.pool, ...S.builds.outros].find(x => x.id === S.buildSel);
  if (!b) { el.innerHTML = `<p class="vazio">Escolha uma build ao lado.</p>`; return; }
  const c = (S.relatorioTudo?.campeoes || []).find(x => x.id === b.id || x.campeao === b.nome);
  el.innerHTML = `
    <div class="heroi">${img(url.camp(b.id), "ic camp", 64)}<div><b>${esc(b.nome)}</b><span class="tag">${esc(b.funcao_nome)}</span></div></div>
    ${c ? `<div class="tiles">
      <div class="tile"><small>Partidas</small><b>${c.partidas}</b><span>${c.v}V · ${c.d}D</span></div>
      <div class="tile"><small>Vitória</small><b>${c.taxa == null ? "—" : c.taxa + "%"}</b><span>com o Quíron</span></div>
      <div class="tile"><small>Part. em abates</small><b>${c.kp == null ? "—" : num(c.kp) + "%"}</b><span>meta 50%</span></div>
      <div class="tile"><small>Mortes &lt; 14</small><b>${num(c.mortes14, 1)}</b><span>por partida</span></div>
      ${c.cs_min != null ? `<div class="tile"><small>CS/min</small><b>${num(c.cs_min, 1)}</b><span>média</span></div>` : ""}
      ${c.visao != null ? `<div class="tile"><small>Visão</small><b>${num(c.visao)}</b><span>placar médio</span></div>` : ""}
    </div>` : `<p class="vazio" style="margin-top:14px">Nenhuma partida registrada com ${esc(b.nome)} ainda.${b.taxa != null ? ` Histórico da temporada: ${b.taxa}% em ${b.vitorias + b.derrotas} jogos.` : ""}</p>`}
    <div class="rot-campo" style="margin-top:18px">Runa principal</div><div style="font-family:var(--titulo);font-weight:700;font-size:18px">${esc(b.runa || "—")}</div>
    ${b.feiticos.length ? `<div class="rot-campo">Feitiços</div><div class="chips">${b.feiticos.map(f => `<span class="chip">${esc(f.nome)}</span>`).join("")}</div>` : ""}
    <button class="bt" style="margin-top:18px;width:100%" id="bt-rel-completo">Relatório completo com gráficos</button>`;
  $("#bt-rel-completo").onclick = () => api.exportar_relatorio(0);
}

// ---------------------------------------------------------------------------
// RELATÓRIO
// ---------------------------------------------------------------------------
async function carregarRelatorio() {
  S.relatorio = await api.relatorio(S.dias);
  desenharRelatorio();
}
function graficoKp(jogos) {
  const js = jogos.slice(-20), W = 440, H = 150, p = 28;
  if (js.length < 2) return `<p class="vazio">Jogue pelo menos duas partidas para ver a evolução.</p>`;
  const x = i => p + i * (W - 2 * p) / (js.length - 1), y = v => H - 20 - (v / 100) * (H - 36);
  const pts = js.map((j, i) => j.kp == null ? null : `${x(i)},${y(j.kp)}`).filter(Boolean).join(" ");
  const barras = js.map((j, i) => j.mortes14 ? `<rect x="${x(i) - 5}" y="${H - 20 - j.mortes14 * 10}" width="10" height="${j.mortes14 * 10}" fill="rgba(240,168,90,.55)" rx="2"/>` : "").join("");
  return `<svg class="grafico" viewBox="0 0 ${W} ${H}" width="100%">
    <line x1="${p}" x2="${W - p}" y1="${y(50)}" y2="${y(50)}" stroke="#e8c77a" stroke-dasharray="4 4" stroke-opacity=".6"/>
    <text x="${W - p}" y="${y(50) - 5}" text-anchor="end">meta 50%</text>
    ${barras}
    <polyline points="${pts}" fill="none" stroke="#4fc3f7" stroke-width="2.2" style="filter:drop-shadow(0 0 4px rgba(79,195,247,.8))"/>
    ${js.map((j, i) => j.kp == null ? "" : `<circle cx="${x(i)}" cy="${y(j.kp)}" r="3.2" fill="${j.resultado === "vitória" ? "#3ddc97" : j.resultado === "derrota" ? "#ff6b6b" : "#e8f8ff"}"><title>${esc(j.quando)} · ${esc(j.campeao)} · ${j.kp}%</title></circle>`).join("")}
    <text x="${p}" y="${H - 4}">${esc(js[0].quando)}</text><text x="${W - p}" y="${H - 4}" text-anchor="end">${esc(js[js.length - 1].quando)}</text>
  </svg>
  <div class="fraco" style="font-size:12px;margin-top:4px">Linha: participação em abates (bolinha verde = vitória, vermelha = derrota). Barras: mortes antes dos 14 min.</div>`;
}
function desenharRelatorio() {
  const d = S.relatorio, r = d.resumo;
  const filtro = `<div class="seg" id="periodo">${[[7, "7 dias"], [30, "30 dias"], [0, "Tudo"]].map(([v, t]) => `<button data-d="${v}" class="${S.dias === v ? "on" : ""}">${t}</button>`).join("")}</div>`;
  const esq = `<div class="rolagem">
      <div style="display:flex;justify-content:center">${teia(d.teia.eixos, 260)}</div>
      <div class="tiles quatro">
        <div class="tile"><small>Partidas</small><b>${r.partidas}</b><span>${r.v}V · ${r.d}D</span></div>
        <div class="tile"><small>Vitória</small><b>${r.taxa == null ? "—" : r.taxa + "%"}</b><span>das partidas</span></div>
        <div class="tile"><small>Part. em abates</small><b>${r.kp == null ? "—" : num(r.kp) + "%"}</b><span>meta 50%</span></div>
        <div class="tile"><small>Mortes &lt; 14</small><b>${num(r.mortes14, 1)}</b><span>por partida</span></div></div>
      <button class="bt grande" style="width:100%;margin-top:14px;font-size:21px;padding:10px" id="bt-exportar">Exportar relatório detalhado</button>
      <div class="cartao" style="margin-top:14px;padding:8px 10px">
        <table class="tabela"><tr><th>Top campeões</th><th>Partidas</th><th>V–D</th><th>Part.</th><th>Mortes</th></tr>
        ${d.campeoes.length ? d.campeoes.map(c => `<tr><td>${c.id ? img(url.camp(c.id), "", 26) : ""}${esc(c.campeao)}</td><td>${c.partidas}</td>
          <td><span class="ok">${c.v}</span>–<span class="ruim">${c.d}</span></td><td>${c.kp == null ? "—" : num(c.kp) + "%"}</td><td>${num(c.mortes14, 1)}</td></tr>`).join("") :
          `<tr><td colspan="5" class="vazio" style="padding:14px 8px">Nenhuma partida neste período.</td></tr>`}</table></div>
    </div>`;
  const dir = `<div class="rolagem">
      <div class="secao-tit">Evolução</div><div style="margin-top:8px">${graficoKp(d.jogos)}</div>
      <div class="secao-tit" style="margin-top:18px">Por horário</div>
      ${d.horarios.length ? `<table class="tabela" style="margin-top:6px"><tr><th>Horário</th><th>Partidas</th><th>Vitória</th></tr>
        ${d.horarios.map(h => `<tr><td>${esc(h.faixa)}</td><td>${h.partidas}</td><td>${h.taxa}%</td></tr>`).join("")}</table>` : `<p class="vazio" style="margin-top:6px">Sem partidas com resultado.</p>`}
      <div class="secao-tit" style="margin-top:18px">Momentos anotados</div>
      ${d.anotadas.length ? d.anotadas.slice(-8).reverse().map(j => `<div class="anotado"><b>${esc(j.campeao)}</b> · ${esc(j.quando)} — ${j.anotacoes.map(esc).join(", ")}</div>`).join("") :
        `<p class="vazio" style="margin-top:6px">Durante a partida, diga “${esc(S.config?.palavra_chamada || "Quíron")} anota” para marcar um momento e revisar aqui.</p>`}
      ${d.teia.dica ? `<div class="cartao dica" style="margin-top:18px;border-left:0"><h4>Dica rápida do dia</h4><p>${esc(d.teia.dica.texto)}</p><small>Foco: ${esc(d.teia.dica.eixo)}</small></div>` : ""}
    </div>`;
  $("#tela-relatorio").innerHTML = `<div class="grade2">
    ${painel("Relatório de desempenho", "Métricas das partidas", esq, filtro)}
    ${painel("Histórico", "Como você vem jogando", dir)}</div>`;
  $("#periodo").onclick = e => { const b = e.target.closest("button"); if (b) { S.dias = +b.dataset.d; carregarRelatorio(); } };
  $("#bt-exportar").onclick = () => api.exportar_relatorio(S.dias);
}

// ---------------------------------------------------------------------------
// CONFIGURAÇÕES
// ---------------------------------------------------------------------------
const TIT_GRUPO = {cliente: ["cliente", "Cliente do LoL"], inicio: ["bandeira", "Início da partida"],
  partida: ["controle", "Durante a partida"], aplicativo: ["app", "Aplicativo"]};
function cartaoPerfil(p) {
  const pool = Object.entries(p.pool || {});
  const nomes = {TOP: "Topo", JUNGLE: "Caçador", MIDDLE: "Meio", BOTTOM: "Atirador", UTILITY: "Suporte"};
  const jogos = (p.vitorias || 0) + (p.derrotas || 0);
  return `<div class="cartao perfil">
    ${p.icone ? img(url.perfil(p.icone), "foto", 66) : `<div class="foto"></div>`}
    <div><div class="nome">${esc(p.riot_id || "Perfil sem Riot ID")}</div>
      <div class="elo">${emblema(p.elo)}<span>${esc(p.elo || "Sem ranque")}</span>
        ${p.pdl != null ? `<small>${p.pdl} PDL${jogos ? `<br>${Math.round(100 * p.vitorias / jogos)}% em ${jogos} jogos` : ""}</small>` : ""}</div>
      <div class="funcoes-mini">${pool.length ? pool.map(([f, cs]) => `<span class="tag">${nomes[f]}</span>${cs.map(c => img(url.camp(c), "", 26)).join("")}`).join("") : `<span class="fraco">Nenhuma função escolhida</span>`}</div>
    </div><button class="bt pequeno" id="bt-perfil" style="align-self:flex-start">Editar</button></div>`;
}
async function desenharConfig() {
  const [cfg, perfil] = await Promise.all([api.config(), api.perfil()]);
  S.config = cfg; S.perfil = perfil;
  if (!S.vozes) [S.vozes, S.mics] = await Promise.all([api.vozes(), api.microfones()]);
  const c = cfg, vel = {150: "Lenta", 185: "Normal", 220: "Rápida"};
  const velAtual = [150, 185, 220].reduce((a, b) => Math.abs(b - c.velocidade_voz) < Math.abs(a - c.velocidade_voz) ? b : a);
  const comandos = ["itens", "placar", "farm", "ameaça", "rota", "plano", "repete", "menos", "silêncio", "volta", "anota", "mais alto", "mais baixo"];
  const grupo = g => {
    const [ic, tit] = TIT_GRUPO[g];
    return `<div class="secao"><div class="secao-tit">${icone(ic, 26)}<b>[</b>${tit}<b>]</b></div>
      ${c.grupos[g].map(s => `<div class="linha"><div class="rot">${esc(s.titulo)}${s.desc ? `<small>${esc(s.desc)}</small>` : ""}</div>${interruptor(s.chave, s.valor)}</div>`).join("")}
      ${g === "aplicativo" ? `<div class="linha"><div class="rot">Pasta do League of Legends<small id="pasta-lol">${esc(c.pasta_lol)}</small></div><button class="bt sec" id="bt-pasta">Procurar</button></div>` : ""}
    </div><div class="sep"></div>`;
  };
  const esq = `<div class="rolagem">
    ${cartaoPerfil(perfil)}
    <div class="secao"><div class="secao-tit">${icone("som", 26)}<b>[</b>Voz<b>]</b></div>
      <div class="linha"><div class="rot">Falar os avisos<small>Pela voz do Windows.</small></div>${interruptor("voz_ligada", c.voz_ligada)}</div>
      <div class="linha"><div class="rot">Voz do Quíron<small>Mais vozes: Windows → Hora e idioma → Fala.</small></div>
        <select id="sel-voz">${S.vozes.map(v => `<option value="${esc(v.id)}" ${v.id === c.voz_windows ? "selected" : ""}>${esc(v.nome)}</option>`).join("")}</select>
        <button class="bt sec" id="bt-ouvir">${icone("play", 12)}Ouvir</button></div>
      <div class="linha"><div class="rot">Velocidade</div><div class="seg" id="seg-vel">${[150, 185, 220].map(v => `<button data-v="${v}" class="${v === velAtual ? "on" : ""}">${vel[v]}</button>`).join("")}</div></div>
      <div class="linha"><div class="rot">Volume</div><input type="range" id="volume" min="20" max="100" step="5" value="${c.volume_voz}" style="--p:${(c.volume_voz - 20) / .8}%"><div class="valor" id="volume-v">${c.volume_voz}%</div></div>
    </div><div class="sep"></div>
    <div class="secao"><div class="secao-tit">${icone("mic", 26)}<b>[</b>Comandos de voz<b>]</b></div>
      <div class="linha"><div class="rot">Ouvir comandos<small>Reconhecimento offline, sem internet.</small></div>${interruptor("comandos_de_voz", c.comandos_de_voz)}</div>
      <div class="linha"><div class="rot">Palavra de chamada<small id="chamada-estado"></small></div>
        <input class="campo ouro" id="chamada" value="${esc(c.palavra_chamada)}" spellcheck="false" style="width:150px">
        <button class="bt sec" id="bt-testar">Testar</button></div>
      <div class="chips" id="chamada-sug" style="margin:0 0 4px 38px"></div>
      <div class="chips" id="lista-comandos" style="margin:4px 0 6px 38px">${comandos.map(x => `<span class="chip"><b>${esc(c.palavra_chamada)}</b> ${x}</span>`).join("")}</div>
      <div class="linha"><div class="rot">Microfone<small>Com fone Bluetooth, outro microfone mantém o som do fone limpo.</small></div>
        <select id="sel-mic"><option value="">Padrão do Windows</option>${S.mics.map(m => `<option ${m === c.microfone ? "selected" : ""}>${esc(m)}</option>`).join("")}</select></div>
      <div class="linha"><div class="rot">Microfone só durante a partida<small>Evita o modo “telefone” do fone Bluetooth fora do jogo.</small></div>${interruptor("microfone_so_na_partida", c.microfone_so_na_partida)}</div>
    </div></div>`;
  const dir = `<div class="rolagem">
    ${["cliente", "inicio", "partida", "aplicativo"].map(grupo).join("")}
    <div class="secao"><div class="secao-tit">${icone("info", 26)}<b>[</b>Sobre<b>]</b></div>
      <div class="linha"><div class="rot">Quíron v${esc(S.versao)}<small id="sobre-versao">Clique para procurar uma versão nova.</small></div><button class="bt sec" id="bt-verificar">Verificar</button></div>
      <div class="linha"><div class="rot">Seus dados<small>${esc(S.base)}</small></div><button class="bt sec" id="bt-dados">Abrir pasta</button></div>
      <div class="linha"><div class="rot">Diagnóstico<small>Copia as informações para enviar quando algo der errado.</small></div><button class="bt sec" id="bt-log">Log</button><button class="bt sec" id="bt-diag">Copiar</button></div>
      <div class="linha"><div class="rot">Projeto no GitHub</div><button class="bt sec" id="bt-github">Abrir</button></div>
    </div></div>`;
  $("#tela-config").innerHTML = `<div class="grade2">
    ${painel("Perfil e voz", "Quem é você e como o Quíron fala", esq)}
    ${painel("Partida e aplicativo", "O que o Quíron faz no cliente e no jogo", dir)}</div>`;
  ligarConfig();
}
function ligarConfig() {
  const tela = $("#tela-config");
  tela.addEventListener("click", async e => {
    const sw = e.target.closest(".sw");
    if (sw) {
      const novo = !sw.classList.contains("on");
      sw.classList.toggle("on", novo); sw.setAttribute("aria-checked", novo);
      S.config = await api.definir(sw.dataset.chave, novo);
      if (sw.dataset.chave === "iniciar_com_windows") {
        const real = S.config.grupos.aplicativo.find(x => x.chave === "iniciar_com_windows").valor;
        sw.classList.toggle("on", real);
      }
    }
  });
  $("#bt-perfil").onclick = () => modalPerfil(false);
  $("#sel-voz").onchange = e => api.definir("voz_windows", e.target.value);
  $("#bt-ouvir").onclick = () => api.testar_voz();
  $("#seg-vel").onclick = e => { const b = e.target.closest("button"); if (!b) return; $$("#seg-vel button").forEach(x => x.classList.toggle("on", x === b)); api.definir("velocidade_voz", +b.dataset.v); };
  const vol = $("#volume");
  vol.oninput = () => { vol.style.setProperty("--p", (vol.value - 20) / .8 + "%"); $("#volume-v").textContent = vol.value + "%"; };
  vol.onchange = () => api.definir("volume_voz", +vol.value);
  $("#sel-mic").onchange = e => api.definir("microfone", e.target.value);
  let tempo = null;
  const campo = $("#chamada");
  campo.oninput = () => { clearTimeout(tempo); tempo = setTimeout(validarChamada, 250); };
  campo.onkeydown = e => { if (e.key === "Enter") salvarChamada(); };
  campo.onblur = () => salvarChamada();
  $("#bt-testar").onclick = testarChamada;
  validarChamada();
  $("#bt-pasta").onclick = async () => { const p = await api.procurar_pasta(); if (p) $("#pasta-lol").textContent = p; };
  $("#bt-verificar").onclick = () => { api.verificar_atualizacao(); $("#sobre-versao").textContent = "Procurando…"; };
  $("#bt-dados").onclick = () => api.abrir_pasta_dados();
  $("#bt-log").onclick = () => api.abrir_log();
  $("#bt-diag").onclick = async () => {
    const t = await api.diagnostico();
    try { await navigator.clipboard.writeText(t); toast("Diagnóstico copiado. Cole na conversa com o Claude."); }
    catch (e) { toast("Não consegui copiar automaticamente."); }
  };
  $("#bt-github").onclick = () => api.abrir_url("github");
}
async function validarChamada() {
  const nome = $("#chamada").value.trim();
  const r = await api.chamada_validar(nome);
  const est = $("#chamada-estado"), sug = $("#chamada-sug");
  sug.innerHTML = "";
  if (r.estado === "ok") est.innerHTML = `<span class="ok">✓ reconhecida</span>`;
  else if (r.estado === "sem_modelo") est.innerHTML = `O modelo de voz baixa ao ligar o coach; dá para salvar.`;
  else if (r.estado === "vazio") est.innerHTML = `<span class="ruim">Digite uma palavra.</span>`;
  else {
    est.innerHTML = `<span class="ruim">✗ fora do dicionário de voz. Parecidas:</span>`;
    sug.innerHTML = r.sugestoes.map(s => `<button class="chip">${esc(s)}</button>`).join("");
    sug.onclick = e => { const b = e.target.closest("button"); if (b) { $("#chamada").value = b.textContent; validarChamada().then(salvarChamada); } };
  }
  $$("#lista-comandos b").forEach(b => b.textContent = nome || "…");
  return r;
}
async function salvarChamada() {
  const nome = $("#chamada").value.trim();
  if (!S.config || nome === S.config.palavra_chamada) return;
  const r = await api.chamada_validar(nome);
  if (r.pode_salvar) { S.config = await api.chamada_salvar(nome); }
}
async function testarChamada() {
  const nome = $("#chamada").value.trim(), est = $("#chamada-estado"), bt = $("#bt-testar");
  const v = await validarChamada(); if (!v.pode_salvar) return;
  bt.disabled = true; est.innerHTML = `<span class="ciano-t">Fale agora: “${esc(nome)} itens”…</span>`;
  const r = await api.chamada_testar(nome);
  bt.disabled = false;
  const nomes = {build: "itens", silencio: "silêncio", volta: "volta", anota: "anota", placar: "placar", farm: "farm", ameaca: "ameaça", rota: "rota", plano: "plano", repete: "repete", menos: "menos", mais_alto: "mais alto", mais_baixo: "mais baixo"};
  if (r.erro) est.innerHTML = `<span class="ruim">Não consegui usar o microfone (${esc(r.erro)}).</span>`;
  else if (r.acao) est.innerHTML = `<span class="ok">✓ Entendi “${esc(nomes[r.acao] || r.acao)}”. Funcionando!</span>`;
  else if (r.texto) est.innerHTML = `<span class="ouro-t">Ouvi “${esc(r.texto)}”, mas não reconheci o comando.</span>`;
  else est.innerHTML = `<span class="ruim">Não ouvi nada. Confira o microfone.</span>`;
}

// ---------------------------------------------------------------------------
// Janelas (modais)
// ---------------------------------------------------------------------------
function abrirModal(html, classe = "") {
  const veu = document.createElement("div");
  veu.className = "veu";
  veu.innerHTML = `<div class="painel modal ${classe}"><div class="dentro">${html}</div></div>`;
  $("#modais").append(veu);
  const fechar = () => veu.remove();
  veu.addEventListener("mousedown", e => { if (e.target === veu) fechar(); });
  veu.addEventListener("keydown", e => { if (e.key === "Escape") fechar(); });
  return {el: veu, fechar};
}

// Seletor de campeão (com grupos comuns/incomuns na função)
function seletorCampeao({titulo = "Escolher campeão", funcao = null, excluir = []} = {}) {
  return new Promise(async resolve => {
    const lista = (await api.campeoes(funcao)).filter(c => !excluir.includes(c.id));
    const lugar = {TOP: "no topo", JUNGLE: "na selva", MIDDLE: "no meio", BOTTOM: "no bot (atirador)", UTILITY: "no suporte"}[funcao] || "";
    const m = abrirModal(`<h2>${esc(titulo)}</h2>
      <input class="campo" id="busca-camp" placeholder="Buscar campeão..." style="margin-top:12px;width:100%">
      <div class="rolagem" id="grade-camp"></div>
      <div class="rodape-modal"><button class="bt sec" id="cancelar">Cancelar</button></div>`);
    const desenhar = () => {
      const t = $("#busca-camp", m.el).value.trim().toLowerCase();
      const filtrados = lista.filter(c => c.nome.toLowerCase().includes(t));
      const grupos = funcao ? [[`Comuns ${lugar}`, filtrados.filter(c => c.comum), false],
        [`Incomuns ${lugar} (a build vira estimativa)`, filtrados.filter(c => !c.comum), true]] : [[null, filtrados, false]];
      $("#grade-camp", m.el).innerHTML = grupos.filter(g => g[1].length).map(([tit, cs, inc]) =>
        `${tit ? `<div class="grade-tit">${esc(tit)}</div>` : ""}<div class="grade-sel">${cs.map(c =>
          `<button data-id="${c.id}" class="${inc ? "incomum" : ""}">${img(url.camp(c.id), "", 52, true)}<span>${esc(c.nome)}</span></button>`).join("")}</div>`).join("") ||
        `<p class="vazio" style="margin-top:14px">Nenhum campeão com esse nome.</p>`;
    };
    desenhar();
    $("#busca-camp", m.el).oninput = desenhar;
    $("#busca-camp", m.el).focus();
    $("#grade-camp", m.el).onclick = e => { const b = e.target.closest("button[data-id]"); if (b) { m.fechar(); resolve(b.dataset.id); } };
    $("#cancelar", m.el).onclick = () => { m.fechar(); resolve(null); };
  });
}

// Seletor de item com busca e filtro por tipo
const FILTROS_ITEM = {"Todos": null, "Mágico": ["SpellDamage"], "Físico": ["Damage", "CriticalStrike", "AttackSpeed", "ArmorPenetration"],
  "Defesa": ["Armor", "SpellBlock", "Health"], "Botas": ["Boots"], "Suporte": ["ManaRegen", "HealthRegen", "Aura"]};
function seletorItem() {
  return new Promise(async resolve => {
    const lista = await api.itens_loja();
    let filtro = "Todos";
    const m = abrirModal(`<h2>Escolher item</h2>
      <input class="campo" id="busca-item" placeholder="Buscar item..." style="margin-top:12px;width:100%">
      <div class="seg" id="filtro-item" style="margin-top:10px;width:max-content">${Object.keys(FILTROS_ITEM).map(f => `<button class="${f === filtro ? "on" : ""}">${f}</button>`).join("")}</div>
      <div class="rolagem" id="grade-item"></div>
      <div class="rodape-modal"><button class="bt sec" id="cancelar">Cancelar</button></div>`);
    const desenhar = () => {
      const t = $("#busca-item", m.el).value.trim().toLowerCase(), tags = FILTROS_ITEM[filtro];
      const fs = lista.filter(i => i.nome.toLowerCase().includes(t) && (!tags || i.tags.some(x => tags.includes(x))));
      $("#grade-item", m.el).innerHTML = `<div class="grade-sel">${fs.map(i => `<button data-en="${esc(i.en)}" data-id="${i.id}" data-nome="${esc(i.nome)}">${img(url.item(i.id), "", 46, true)}<span>${esc(i.nome)}</span></button>`).join("")}</div>`;
    };
    desenhar();
    $("#busca-item", m.el).oninput = desenhar;
    $("#busca-item", m.el).focus();
    $("#filtro-item", m.el).onclick = e => { const b = e.target.closest("button"); if (!b) return; filtro = b.textContent; $$("#filtro-item button", m.el).forEach(x => x.classList.toggle("on", x === b)); desenhar(); };
    $("#grade-item", m.el).onclick = e => { const b = e.target.closest("button[data-en]"); if (b) { m.fechar(); resolve({en: b.dataset.en, id: b.dataset.id, nome: b.dataset.nome}); } };
    $("#cancelar", m.el).onclick = () => { m.fechar(); resolve(null); };
  });
}

// Editor de build: 6 espaços de item, arrastar para mudar a ordem
async function editorBuild(cid) {
  const d = await api.build_detalhe(cid);
  const funcoes = S.builds.funcoes, tipos = S.builds.tipos;
  let slots = [...d.itens, null, null, null, null, null, null].slice(0, 6);
  let campeao = cid, nomeCamp = d.nome;
  const m = abrirModal(`<h2>${cid ? "Editar build" : "Nova build"}</h2>
    <div class="rot-campo">Campeão</div>
    <div id="camp-ed" style="display:flex;align-items:center;gap:10px"></div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
      <div><div class="rot-campo">Função</div><select id="ed-funcao" style="width:100%;max-width:none">${Object.entries(funcoes).map(([k, v]) => `<option value="${k}" ${k === d.funcao ? "selected" : ""}>${v}</option>`).join("")}</select></div>
      <div><div class="rot-campo">Estilo (ajustes contra o time inimigo)</div><select id="ed-tipo" style="width:100%;max-width:none">${Object.entries(tipos).map(([k, v]) => `<option value="${k}" ${k === d.tipo ? "selected" : ""}>${v}</option>`).join("")}</select></div>
    </div>
    <div class="rot-campo">Runa principal</div><input class="campo" id="ed-runa" value="${esc(d.runa)}" style="width:100%">
    <div class="rot-campo">Itens, na ordem de compra (clique para trocar; arraste para mudar a ordem; ✕ tira)</div>
    <div class="slots" id="slots"></div>
    <div class="rodape-modal"><span class="erro" id="ed-erro"></span><button class="bt sec" id="cancelar">Cancelar</button><button class="bt" id="salvar">Salvar</button></div>`, "estreito");
  const desenharCamp = () => {
    $("#camp-ed", m.el).innerHTML = campeao ? `${img(url.camp(campeao), "ic camp", 44)}<b style="font-family:var(--titulo);font-size:21px">${esc(nomeCamp)}</b>${cid ? "" : `<button class="bt sec pequeno" id="trocar-camp">Trocar</button>`}`
      : `<button class="bt" id="trocar-camp">Escolher campeão</button>`;
    const t = $("#trocar-camp", m.el);
    if (t) t.onclick = async () => {
      const id = await seletorCampeao({funcao: $("#ed-funcao", m.el).value});
      if (id) { campeao = id; nomeCamp = (await api.campeoes()).find(c => c.id === id)?.nome || id; desenharCamp(); }
    };
  };
  const desenharSlots = () => {
    $("#slots", m.el).innerHTML = slots.map((it, i) => `<div class="slot" data-i="${i}">
      ${it ? `<img class="ic-slot" draggable="true" src="${esc(url.item(it.id))}" title="${esc(it.nome)}" alt=""><span>${esc(it.nome)}</span><button class="tirar" title="Tirar">✕</button>`
           : `<button class="vazio-slot">+</button><span class="fraco">Item ${i + 1}</span>`}</div>`).join("");
  };
  desenharCamp(); desenharSlots();
  const area = $("#slots", m.el);
  let arrastando = null;
  area.addEventListener("click", async e => {
    const slot = e.target.closest(".slot"); if (!slot) return;
    const i = +slot.dataset.i;
    if (e.target.closest(".tirar")) { slots[i] = null; slots = [...slots.filter(Boolean), null, null, null, null, null, null].slice(0, 6); return desenharSlots(); }
    if (e.target.closest(".ic-slot") || e.target.closest(".vazio-slot")) {
      const it = await seletorItem(); if (it) { slots[i] = it; desenharSlots(); }
    }
  });
  area.addEventListener("dragstart", e => { const s = e.target.closest(".slot"); arrastando = +s.dataset.i; e.dataTransfer.effectAllowed = "move"; });
  area.addEventListener("dragover", e => { e.preventDefault(); const s = e.target.closest(".slot"); $$(".slot", area).forEach(x => x.classList.toggle("alvo", x === s && +s.dataset.i !== arrastando)); });
  area.addEventListener("dragleave", e => { if (!area.contains(e.relatedTarget)) $$(".slot", area).forEach(x => x.classList.remove("alvo")); });
  area.addEventListener("drop", e => {
    e.preventDefault(); const s = e.target.closest(".slot"); if (!s || arrastando == null) return;
    const cheios = slots.filter(Boolean), item = slots[arrastando];
    cheios.splice(cheios.indexOf(item), 1);
    cheios.splice(Math.min(+s.dataset.i, cheios.length), 0, item);
    slots = [...cheios, null, null, null, null, null, null].slice(0, 6); arrastando = null; desenharSlots();
  });
  area.addEventListener("dragend", () => { arrastando = null; $$(".slot", area).forEach(x => x.classList.remove("alvo")); });
  $("#cancelar", m.el).onclick = m.fechar;
  $("#salvar", m.el).onclick = async () => {
    const r = await api.build_salvar(campeao, {funcao: $("#ed-funcao", m.el).value, tipo: $("#ed-tipo", m.el).value,
      runa: $("#ed-runa", m.el).value, itens: slots.filter(Boolean).map(x => x.en)});
    if (r.erro) { $("#ed-erro", m.el).textContent = r.erro; return; }
    m.fechar(); S.buildSel = campeao; carregarBuilds();
  };
}

// Perfil: busca do invocador pelo cliente, funções e pool
async function modalPerfil(primeira) {
  const p = await api.perfil();
  const NOMES = {TOP: "Topo", JUNGLE: "Caçador", MIDDLE: "Meio", BOTTOM: "Atirador", UTILITY: "Suporte"};
  const SERV = ["BR", "LAN", "LAS", "NA", "EUW", "EUNE", "KR", "JP", "OCE", "TR", "RU", "ME", "SEA", "TW", "VN"];
  const st = {riot_id: p.riot_id, servidor: p.servidor || "BR", elo: p.elo, icone: p.icone, pdl: p.pdl,
    vitorias: p.vitorias, derrotas: p.derrotas, funcoes: [...p.funcoes], pool: JSON.parse(JSON.stringify(p.pool || {}))};
  const campeoes = await api.campeoes();
  const nomeDe = id => (campeoes.find(c => c.id === id) || {}).nome || id;
  const m = abrirModal(`
    <h2>${primeira ? "Vamos configurar o seu coach" : "Seu perfil"}</h2>
    ${primeira ? `<div class="sub" style="font-size:16px">O Quíron usa isso para sugerir campeões no draft, importar builds e montar o plano da partida.</div>` : ""}
    <div class="rolagem">
      <div class="rot-campo">Riot ID (Nome#TAG)</div>
      <div class="linha-campos"><input class="campo" id="pf-riot" placeholder="Nome#TAG" value="${esc(st.riot_id)}" spellcheck="false">
        <button class="bt" id="pf-buscar">Buscar</button>
        <select id="pf-serv" style="min-width:80px">${SERV.map(s => `<option ${s === st.servidor ? "selected" : ""}>${s}</option>`).join("")}</select></div>
      <div id="pf-card" style="margin-top:10px"></div>
      <div id="pf-sug" class="fraco" style="font-size:13px;margin-top:8px"></div>
      <div class="rot-campo">Funções que você joga</div>
      <div class="funcoes-sel" id="pf-funcoes">${Object.entries(NOMES).map(([k, v]) => `<button data-f="${k}" class="${st.funcoes.includes(k) ? "on" : ""}">${v}</button>`).join("")}</div>
      <div class="rot-campo">Campeões por função (até 6)</div>
      <div id="pf-pools"></div>
    </div>
    <div class="rodape-modal"><span class="erro" id="pf-erro"></span><button class="bt sec" id="cancelar">${primeira ? "Agora não" : "Cancelar"}</button><button class="bt" id="salvar">Salvar</button></div>`);
  const card = () => {
    const jogos = (st.vitorias || 0) + (st.derrotas || 0);
    $("#pf-card", m.el).innerHTML = `<div class="cartao perfil">${st.icone ? img(url.perfil(st.icone), "foto", 60) : `<div class="foto" style="width:60px;height:60px"></div>`}
      <div><div class="nome">${esc(st.riot_id || "Nenhum invocador")}${st.nivel ? ` <small class="fraco">· nível ${st.nivel}</small>` : ""}</div>
        <div class="elo">${emblema(st.elo)}<span>${esc(st.elo || "Sem ranque")}</span>
          <small>${st.pdl != null ? `${st.pdl} PDL` : ""}${jogos ? ` · ${Math.round(100 * st.vitorias / jogos)}% em ${jogos} jogos` : ""}</small></div>
        <div class="fraco" style="font-size:12px;margin-top:4px">O elo vem do cliente do LoL (aberto e logado) ao clicar em Buscar.</div></div></div>`;
  };
  const pools = () => {
    const el = $("#pf-pools", m.el);
    if (!st.funcoes.length) { el.innerHTML = `<p class="vazio">Marque pelo menos uma função.</p>`; return; }
    el.innerHTML = st.funcoes.map(f => {
      const lista = st.pool[f] || [];
      return `<div class="cartao pool" data-f="${f}"><h5>${NOMES[f]}${lista.length ? `<small>clique num campeão para remover</small>` : ""}</h5>
        <div class="camps">${lista.map(c => `<div class="camp-bloco" data-c="${c}" title="Remover">${img(url.camp(c), "", 56)}<span>${esc(nomeDe(c))}</span></div>`).join("")}
          ${lista.length < 6 ? `<button class="mais" data-add="${f}">+</button>` : ""}</div></div>`;
    }).join("");
  };
  card(); pools();
  const buscar = async (proprio, silencioso) => {
    const bt = $("#pf-buscar", m.el); bt.disabled = true; bt.textContent = "…";
    const r = await api.buscar_invocador($("#pf-riot", m.el).value.trim(), proprio);
    bt.disabled = false; bt.textContent = "Buscar";
    if (!r || r.silencio) return;
    if (r.erro) { if (!silencioso) $("#pf-erro", m.el).textContent = r.erro; return; }
    $("#pf-erro", m.el).textContent = "";
    Object.assign(st, {riot_id: r.riot_id, elo: r.elo, icone: r.icone, pdl: r.pdl, vitorias: r.vitorias, derrotas: r.derrotas, nivel: r.nivel});
    $("#pf-riot", m.el).value = r.riot_id;
    if (SERV.includes(r.regiao)) { st.servidor = r.regiao; $("#pf-serv", m.el).value = r.regiao; }
    card();
    const sg = r.sugestao;
    if (sg && sg.total) {
      const txt = `Nas últimas ${sg.total} partidas: ` + sg.resumo.map(x => `${x.nome} ${x.pct}%`).join(", ");
      const aplicar = () => { st.funcoes = [...sg.funcoes]; Object.assign(st.pool, sg.pool); $$("#pf-funcoes button", m.el).forEach(b => b.classList.toggle("on", st.funcoes.includes(b.dataset.f))); pools(); };
      if (!st.funcoes.length) { aplicar(); $("#pf-sug", m.el).textContent = txt + ". Preenchi as funções e campeões; ajuste se quiser."; }
      else { $("#pf-sug", m.el).innerHTML = `${esc(txt)} <button class="bt sec pequeno" id="pf-usar" style="margin-left:6px">Usar no perfil</button>`; $("#pf-usar", m.el).onclick = aplicar; }
    }
  };
  $("#pf-buscar", m.el).onclick = () => buscar(false, false);
  $("#pf-riot", m.el).onkeydown = e => { if (e.key === "Enter") buscar(false, false); };
  setTimeout(() => buscar(!st.riot_id, true), 200);
  $("#pf-funcoes", m.el).onclick = e => {
    const b = e.target.closest("button"); if (!b) return;
    const f = b.dataset.f;
    st.funcoes = st.funcoes.includes(f) ? st.funcoes.filter(x => x !== f) : Object.keys(NOMES).filter(x => x === f || st.funcoes.includes(x));
    b.classList.toggle("on", st.funcoes.includes(f)); pools();
  };
  $("#pf-pools", m.el).onclick = async e => {
    const add = e.target.closest("[data-add]"), bloco = e.target.closest(".camp-bloco");
    if (add) {
      const f = add.dataset.add;
      const id = await seletorCampeao({titulo: `Adicionar campeão: ${NOMES[f]}`, funcao: f, excluir: st.pool[f] || []});
      if (id) { st.pool[f] = [...(st.pool[f] || []), id].slice(0, 6); pools(); }
    } else if (bloco) {
      const f = bloco.closest(".pool").dataset.f;
      st.pool[f] = st.pool[f].filter(c => c !== bloco.dataset.c); pools();
    }
  };
  $("#cancelar", m.el).onclick = m.fechar;
  $("#salvar", m.el).onclick = async () => {
    st.riot_id = $("#pf-riot", m.el).value.trim(); st.servidor = $("#pf-serv", m.el).value;
    const r = await api.perfil_salvar(st);
    if (r.erro) { $("#pf-erro", m.el).textContent = r.erro; return; }
    m.fechar(); S.perfil = r.perfil;
    if (S.tela === "config") desenharConfig();
    carregarBuilds();
  };
}

// ---------------------------------------------------------------------------
// Início
// ---------------------------------------------------------------------------
(async function iniciar() {
  await prepararApi();
  const ini = await api.inicial();
  Object.assign(S, {versao: ini.versao, base: ini.base, ddragon: ini.ddragon, estado: ini.estado, rodando: ini.rodando,
    log: ini.log, config: ini.config, perfil: ini.perfil, dadosProntos: ini.dados_prontos});
  $("#versao").textContent = "v" + ini.versao;
  $("#rodape").textContent = ini.aviso;
  if (ini.atualizacao) mostrarFaixa(ini.atualizacao);
  desenharCoach();
  carregarCoach();
  if (ini.dados_prontos) carregarBuilds(); else $("#tela-builds").innerHTML = painel("", "", `<p class="vazio">Carregando campeões e itens do patch…</p>`);
  if (ini.precisa_perfil) setTimeout(() => modalPerfil(true), 300);
  document.addEventListener("contextmenu", e => { if (!e.target.closest("input")) e.preventDefault(); });
})();
