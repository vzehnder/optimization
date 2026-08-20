// Three variants of the configured client portal, switchable via ?variant=,
// in a standalone throwaway page beside its Wayfinder ticket.

const variants = {
  A: {
    name: "Informe ejecutivo",
    thesis: "Una lectura guiada de la publicacion",
    assumption: "Orden fijo, lenguaje del cliente y foco en conclusiones",
  },
  B: {
    name: "Tablero explorable",
    thesis: "El cliente decide que dimension revisar",
    assumption: "Navegacion por temas y comparacion visual",
  },
  C: {
    name: "Dossier tecnico",
    thesis: "Trazabilidad y detalle como primera capa",
    assumption: "Indice estable, tablas y evidencia descargable",
  },
};

const publications = [
  { id: "aug-12", title: "Operacion semanal · 11–17 agosto", date: "12 ago 2026", active: true },
  { id: "aug-05", title: "Operacion semanal · 4–10 agosto", date: "5 ago 2026" },
  { id: "jul-29", title: "Operacion semanal · 28 jul–3 ago", date: "29 jul 2026" },
];

const chartSeries = {
  costo: [68, 64, 59, 53, 48, 50, 57, 63, 71, 77, 73, 69],
  referencia: [72, 69, 66, 64, 63, 65, 68, 74, 79, 83, 81, 76],
  hidro: [31, 34, 39, 45, 48, 47, 43, 39, 35, 32, 31, 30],
};

const state = {
  variant: variantFromUrl(),
  topic: topicFromUrl(),
  view: viewFromUrl(),
  publication: publicationFromUrl(),
  toastTimer: null,
};

function variantFromUrl() {
  const value = new URLSearchParams(window.location.search).get("variant")?.toUpperCase();
  return variants[value] ? value : "A";
}

function topicFromUrl() {
  const value = new URLSearchParams(window.location.search).get("topic");
  return ["resumen", "comercial", "operacion"].includes(value) ? value : "resumen";
}

function viewFromUrl() {
  const value = new URLSearchParams(window.location.search).get("view");
  return ["chart", "table"].includes(value) ? value : "chart";
}

function publicationFromUrl() {
  const value = new URLSearchParams(window.location.search).get("publication");
  return publications.some((item) => item.id === value) ? value : publications[0].id;
}

function updateUrl() {
  const url = new URL(window.location.href);
  url.searchParams.set("variant", state.variant);
  url.searchParams.set("topic", state.topic);
  url.searchParams.set("view", state.view);
  url.searchParams.set("publication", state.publication);
  window.history.replaceState({}, "", url);
}

function shell(content, options = {}) {
  const { compact = false, projectNav = "Resultados compartidos" } = options;
  return `
    <div class="client-shell variant-${state.variant.toLowerCase()} ${compact ? "shell-compact" : ""}">
      <header class="client-header">
        <a class="brand" href="#" aria-label="Zenergies, inicio">
          <span class="brand-mark">Z</span>
          <span><strong>Zenergies</strong><small>Portal clientes</small></span>
        </a>
        <div class="project-context">
          <small>Proyecto</small>
          <strong>Complejo Los Cipreses</strong>
        </div>
        <div class="client-identity">
          <span class="avatar">CM</span>
          <span><strong>Camila Muñoz</strong><small>Andes Energia</small></span>
          <button class="icon-button" aria-label="Abrir menu de usuario">•••</button>
        </div>
      </header>
      <nav class="client-nav" aria-label="Navegacion del proyecto">
        <a href="#" class="active">${projectNav}</a>
        <a href="#downloads">Descargas</a>
        <span class="read-only-badge">Solo lectura</span>
      </nav>
      ${content}
    </div>`;
}

function publicationHeader(mode = "wide") {
  return `
    <header class="publication-header ${mode}">
      <div>
        <nav class="breadcrumbs" aria-label="Ruta">
          <a href="#">Los Cipreses</a><span>/</span><span>Resultados</span>
        </nav>
        <span class="eyebrow">Informe publicado · ${publications[0].date}</span>
        <h1>Operacion semanal · 11–17 agosto</h1>
        <p>Plan de abastecimiento y generacion para cubrir la demanda esperada de la semana.</p>
      </div>
      <div class="publication-actions">
        <span class="freshness"><i></i> Datos actualizados al 11 ago, 08:42</span>
        <button class="secondary-button" data-download="informe-semanal.pdf">↓ Descargar informe</button>
      </div>
    </header>`;
}

function kpis(flavour = "default") {
  const items = flavour === "technical"
    ? [
        ["Costo total", "USD 126.840", "−7,4% vs. referencia"],
        ["Energia abastecida", "8.924 MWh", "100% de la demanda"],
        ["Generacion hidrica", "5.286 MWh", "59,2% del total"],
        ["Vertimiento", "18 MWh", "0,3% disponible"],
      ]
    : [
        ["Costo esperado", "USD 126.840", "USD 10.120 bajo referencia"],
        ["Demanda cubierta", "100%", "8.924 MWh"],
        ["Aporte renovable", "59,2%", "+4,1 pp vs. semana anterior"],
        ["Riesgo operativo", "Bajo", "Sin deficit proyectado"],
      ];
  return `<div class="kpi-grid">${items.map(([label, value, note], index) => `
    <article class="kpi-card ${index === 0 ? "emphasis" : ""}">
      <span>${label}</span><strong>${value}</strong><small>${note}</small>
    </article>`).join("")}</div>`;
}

function lineChart({ title = "Costo horario y referencia", series = ["costo", "referencia"], compact = false } = {}) {
  const colors = { costo: "#087f6b", referencia: "#7194a6", hidro: "#d9843d" };
  const labels = { costo: "Plan recomendado", referencia: "Referencia", hidro: "Generacion hidrica" };
  const paths = series.map((key) => {
    const values = chartSeries[key];
    const points = values.map((value, index) => {
      const x = 28 + index * (744 / (values.length - 1));
      const y = 205 - ((value - 25) / 62) * 164;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    }).join(" ");
    return `<polyline points="${points}" fill="none" stroke="${colors[key]}" stroke-width="${key === "costo" ? 4 : 3}" stroke-linecap="round" stroke-linejoin="round" />`;
  }).join("");
  return `
    <figure class="chart-card ${compact ? "compact" : ""}">
      <figcaption>
        <div><span class="eyebrow">Resultado horario</span><h3>${title}</h3></div>
        <div class="legend">${series.map((key) => `<span><i style="background:${colors[key]}"></i>${labels[key]}</span>`).join("")}</div>
      </figcaption>
      <div class="chart-plot">
        <div class="chart-y"><span>100</span><span>75</span><span>50</span><span>25</span></div>
        <svg viewBox="0 0 800 230" preserveAspectRatio="none" role="img" aria-label="${title}">
          <line x1="28" y1="41" x2="772" y2="41"/><line x1="28" y1="95" x2="772" y2="95"/>
          <line x1="28" y1="150" x2="772" y2="150"/><line x1="28" y1="205" x2="772" y2="205"/>
          ${paths}
        </svg>
        <div class="chart-x"><span>Lun</span><span>Mar</span><span>Mie</span><span>Jue</span><span>Vie</span><span>Sab</span><span>Dom</span></div>
      </div>
    </figure>`;
}

function resultsTable(dense = false) {
  const rows = [
    ["Lun 11", "1.282", "792", "490", "18.420"],
    ["Mar 12", "1.306", "811", "495", "17.960"],
    ["Mie 13", "1.341", "824", "517", "17.480"],
    ["Jue 14", "1.297", "801", "496", "17.710"],
    ["Vie 15", "1.354", "824", "530", "18.850"],
    ["Sab 16", "1.188", "703", "485", "18.010"],
    ["Dom 17", "1.156", "531", "625", "18.410"],
  ];
  return `
    <div class="result-table-wrap ${dense ? "dense" : ""}">
      <table>
        <thead><tr><th>Dia</th><th>Demanda<br><small>MWh</small></th><th>Generacion propia<br><small>MWh</small></th><th>Compra a red<br><small>MWh</small></th><th>Costo<br><small>USD</small></th></tr></thead>
        <tbody>${rows.map((row) => `<tr>${row.map((cell) => `<td>${cell}</td>`).join("")}</tr>`).join("")}</tbody>
        <tfoot><tr><th>Total</th><th>8.924</th><th>5.286</th><th>3.638</th><th>126.840</th></tr></tfoot>
      </table>
    </div>`;
}

function notesCard() {
  return `
    <aside class="notes-card">
      <span class="eyebrow">Comentario del equipo</span>
      <h3>Una semana sin deficit proyectado</h3>
      <p>El programa prioriza la generacion hidrica entre martes y viernes. La compra a red aumenta durante el fin de semana para resguardar el nivel del embalse.</p>
      <div><span>Preparado por</span><strong>Equipo de Planificacion</strong></div>
    </aside>`;
}

function downloads(compact = false) {
  return `
    <section id="downloads" class="downloads-panel ${compact ? "compact" : ""}">
      <div><span class="eyebrow">Archivos de esta entrega</span><h2>Descargas</h2><p>Solo se muestran documentos aprobados para esta publicacion.</p></div>
      <div class="download-list">
        <button data-download="informe-semanal.pdf"><span class="file-icon">PDF</span><span><strong>Informe semanal</strong><small>Resumen · 1,8 MB</small></span><b>↓</b></button>
        <button data-download="detalle-horario.xlsx"><span class="file-icon excel">XLS</span><span><strong>Detalle horario</strong><small>Resultados · 246 KB</small></span><b>↓</b></button>
      </div>
    </section>`;
}

function variantA() {
  return shell(`
    <main class="a-main">
      ${publicationHeader()}
      <section class="executive-summary">
        <div class="section-title"><div><span class="eyebrow">En breve</span><h2>Resultado de la semana</h2></div><span class="configured-note">4 indicadores seleccionados para Los Cipreses</span></div>
        ${kpis()}
      </section>
      <div class="a-story-grid">
        <section class="story-panel">
          <div class="section-title"><div><span class="eyebrow">Costo y abastecimiento</span><h2>El plan reduce el costo esperado en 7,4%</h2></div><span class="positive-chip">Ahorro estimado · USD 10.120</span></div>
          ${lineChart()}
        </section>
        ${notesCard()}
      </div>
      <section class="story-panel table-story">
        <div class="section-title"><div><span class="eyebrow">Detalle diario</span><h2>Como se cubre la demanda</h2></div><button class="text-button" data-scroll-table>Ver tabla completa →</button></div>
        ${resultsTable()}
      </section>
      ${downloads()}
      <p class="publication-footnote">Configuracion de vista: Comercial ejecutivo · compartida con los usuarios asignados al proyecto</p>
    </main>
  `);
}

function topicContent() {
  if (state.topic === "comercial") {
    return `
      <section class="dashboard-panel wide">
        <div class="panel-heading"><div><span class="eyebrow">Vista comercial</span><h2>Costo de abastecimiento</h2></div><span class="positive-chip">−7,4% vs. referencia</span></div>
        ${lineChart({ title: "Costo horario · USD/MWh" })}
      </section>
      <section class="dashboard-panel"><span class="eyebrow">Composicion del costo</span><h2>USD 126.840</h2><div class="donut-layout"><div class="donut"><span>39%</span></div><ul><li><i></i>Compra a red <strong>USD 49.460</strong></li><li><i></i>Operacion hidrica <strong>USD 41.880</strong></li><li><i></i>Otros costos <strong>USD 35.500</strong></li></ul></div></section>
      <section class="dashboard-panel"><span class="eyebrow">Lectura clave</span><h2>La mayor ventaja ocurre entre 04:00 y 09:00</h2><p class="large-copy">El despacho hidrico desplaza compras durante las horas con mayor diferencia frente a referencia.</p></section>`;
  }
  if (state.topic === "operacion") {
    return `
      <section class="dashboard-panel wide">
        <div class="panel-heading"><div><span class="eyebrow">Vista operacional</span><h2>Generacion y cobertura</h2></div><div class="view-toggle"><button data-view="chart" aria-pressed="${state.view === "chart"}">Grafico</button><button data-view="table" aria-pressed="${state.view === "table"}">Tabla</button></div></div>
        ${state.view === "chart" ? lineChart({ title: "Generacion hidrica y demanda cubierta", series: ["hidro", "costo"] }) : resultsTable(true)}
      </section>
      <section class="dashboard-panel"><span class="eyebrow">Demanda</span><h2>8.924 MWh</h2><div class="metric-bar"><span style="width:100%"></span></div><p>100% cubierta en los 168 periodos.</p></section>
      <section class="dashboard-panel"><span class="eyebrow">Embalse al cierre</span><h2>68,4%</h2><div class="metric-bar amber"><span style="width:68.4%"></span></div><p>Dentro del rango acordado.</p></section>`;
  }
  return `
    <section class="dashboard-panel wide dashboard-kpis"><div class="panel-heading"><div><span class="eyebrow">Resumen</span><h2>Resultado de la semana</h2></div><span class="freshness"><i></i> Datos al 11 ago, 08:42</span></div>${kpis()}</section>
    <section class="dashboard-panel wide">${lineChart({ title: "Costo horario y referencia", compact: true })}</section>
    <section class="dashboard-panel">${notesCard()}</section>`;
}

function variantB() {
  const publicationItems = publications.map((item) => `
    <button class="publication-item ${state.publication === item.id ? "active" : ""}" data-publication="${item.id}">
      <span>${item.date}</span><strong>${item.title}</strong>${item.active ? "<small>Ultima publicacion</small>" : ""}
    </button>`).join("");
  const topics = [
    ["resumen", "Resumen", "Indicadores clave"],
    ["comercial", "Comercial", "Costos y ahorros"],
    ["operacion", "Operacion", "Energia y recursos"],
  ];
  return shell(`
    <div class="b-layout">
      <aside class="publication-rail">
        <div><span class="eyebrow">Complejo Los Cipreses</span><h2>Resultados publicados</h2></div>
        <div class="publication-list">${publicationItems}</div>
        <button class="archive-link">Ver archivo completo →</button>
      </aside>
      <main class="b-main">
        ${publicationHeader("compact")}
        <nav class="topic-tabs" aria-label="Temas del informe">${topics.map(([key, label, note]) => `<button data-topic="${key}" aria-selected="${state.topic === key}"><strong>${label}</strong><small>${note}</small></button>`).join("")}</nav>
        <div class="dashboard-grid">${topicContent()}</div>
        <div class="b-download-row"><span>Esta publicacion incluye 2 archivos aprobados.</span><button class="secondary-button" data-download="paquete-los-cipreses.zip">↓ Descargar paquete</button></div>
      </main>
    </div>
  `, { projectNav: "Tablero" });
}

function evidenceList() {
  return `
    <dl class="evidence-list">
      <div><dt>Periodo informado</dt><dd>11–17 agosto 2026</dd></div>
      <div><dt>Publicado</dt><dd>12 agosto 2026 · 09:15</dd></div>
      <div><dt>Cobertura temporal</dt><dd>168 de 168 periodos</dd></div>
      <div><dt>Estado de validacion</dt><dd><span class="verified">✓ Verificado</span></dd></div>
      <div><dt>Responsable</dt><dd>Equipo de Planificacion</dd></div>
      <div><dt>Edicion del informe</dt><dd>2026.08 · revision 1</dd></div>
    </dl>`;
}

function variantC() {
  return shell(`
    <main class="c-main">
      <aside class="document-index">
        <span class="index-title">Contenido</span>
        <a href="#c-summary" class="active"><span>01</span>Resumen ejecutivo</a>
        <a href="#c-cost"><span>02</span>Costo y abastecimiento</a>
        <a href="#c-operation"><span>03</span>Detalle operacional</a>
        <a href="#c-evidence"><span>04</span>Datos del informe</a>
        <a href="#downloads"><span>05</span>Archivos</a>
        <button class="primary-button" data-download="dossier-los-cipreses.pdf">↓ Exportar dossier</button>
      </aside>
      <article class="dossier">
        <header class="dossier-cover">
          <div><span class="eyebrow">Andes Energia · Complejo Los Cipreses</span><h1>Informe de operacion semanal</h1><p class="cover-period">11–17 agosto 2026</p></div>
          <div class="cover-seal"><span>Informe</span><strong>2026.08</strong><small>Publicado</small></div>
        </header>
        <section id="c-summary" class="dossier-section">
          <div class="dossier-number">01</div><div class="dossier-content"><span class="eyebrow">Resumen ejecutivo</span><h2>Abastecimiento completo con menor costo esperado</h2><p class="lead">La programacion cubre el 100% de la demanda y reduce en USD 10.120 el costo respecto de la referencia semanal.</p>${kpis("technical")}${notesCard()}</div>
        </section>
        <section id="c-cost" class="dossier-section">
          <div class="dossier-number">02</div><div class="dossier-content"><span class="eyebrow">Costo y abastecimiento</span><h2>Comparacion con la referencia</h2>${lineChart({ title: "Costo horario · USD/MWh" })}<p class="figure-note">Figura 1. Resultado horario calculado para el periodo informado. Los nombres y unidades corresponden al vocabulario acordado para el proyecto.</p></div>
        </section>
        <section id="c-operation" class="dossier-section">
          <div class="dossier-number">03</div><div class="dossier-content"><span class="eyebrow">Detalle operacional</span><h2>Balance diario de energia</h2>${resultsTable(true)}<p class="figure-note">Tabla 1. Valores diarios consolidados desde los 168 periodos horarios.</p></div>
        </section>
        <section id="c-evidence" class="dossier-section">
          <div class="dossier-number">04</div><div class="dossier-content"><span class="eyebrow">Datos del informe</span><h2>Trazabilidad de la entrega</h2>${evidenceList()}</div>
        </section>
        <section class="dossier-section dossier-downloads"><div class="dossier-number">05</div><div class="dossier-content">${downloads(true)}</div></section>
        <footer class="dossier-footer">Vista de proyecto · todos los usuarios cliente asignados ven la misma configuracion y publicacion.</footer>
      </article>
    </main>
  `, { compact: true, projectNav: "Dossier" });
}

function render() {
  const root = document.querySelector("#prototype-root");
  root.innerHTML = state.variant === "A" ? variantA() : state.variant === "B" ? variantB() : variantC();
  renderSwitcher();
  updateUrl();
  bindInteractions();
}

function renderSwitcher() {
  const switcher = document.querySelector("#variant-switcher");
  const variant = variants[state.variant];
  switcher.innerHTML = `
    <button type="button" data-cycle="-1" aria-label="Variante anterior">←</button>
    <div><span>Variante ${state.variant}</span><strong>${variant.name}</strong><small>${variant.assumption}</small></div>
    <button type="button" data-cycle="1" aria-label="Variante siguiente">→</button>`;
}

function bindInteractions() {
  document.querySelectorAll("[data-cycle]").forEach((button) => button.addEventListener("click", () => cycleVariant(Number(button.dataset.cycle))));
  document.querySelectorAll("[data-topic]").forEach((button) => button.addEventListener("click", () => { state.topic = button.dataset.topic; render(); }));
  document.querySelectorAll("[data-view]").forEach((button) => button.addEventListener("click", () => { state.view = button.dataset.view; render(); }));
  document.querySelectorAll("[data-publication]").forEach((button) => button.addEventListener("click", () => { state.publication = button.dataset.publication; showToast("Prototipo: se conserva el contenido de ejemplo para comparar la estructura."); render(); }));
  document.querySelectorAll("[data-download]").forEach((button) => button.addEventListener("click", () => showToast(`Descarga simulada: ${button.dataset.download}`)));
  document.querySelectorAll("[data-scroll-table]").forEach((button) => button.addEventListener("click", () => document.querySelector(".table-story")?.scrollIntoView({ behavior: "smooth" })));
}

function cycleVariant(direction) {
  const keys = Object.keys(variants);
  const current = keys.indexOf(state.variant);
  state.variant = keys[(current + direction + keys.length) % keys.length];
  window.scrollTo({ top: 0, behavior: "smooth" });
  render();
}

function showToast(message) {
  const toast = document.querySelector("#prototype-toast");
  toast.textContent = message;
  toast.classList.add("visible");
  window.clearTimeout(state.toastTimer);
  state.toastTimer = window.setTimeout(() => toast.classList.remove("visible"), 2600);
}

document.addEventListener("keydown", (event) => {
  const target = event.target;
  if (target instanceof HTMLElement && (target.matches("input, textarea, select") || target.isContentEditable)) return;
  if (event.key === "ArrowLeft") cycleVariant(-1);
  if (event.key === "ArrowRight") cycleVariant(1);
});

render();
