// Three variants of the operator console, switchable via ?variant=, in a
// standalone throwaway page beside its Wayfinder ticket.

const variants = {
  A: { name: "Mesa de trabajo", thesis: "Preparar y ejecutar en una pantalla" },
  B: { name: "Recorrido guiado", thesis: "Avanzar con confianza, paso a paso" },
  C: { name: "Resultados primero", thesis: "Entrar por lo que ocurrio" },
};

const runStates = {
  idle: "Listo",
  queued: "En cola",
  running: "Ejecutando",
  success: "Completado",
  error: "Error",
};

const seriesGroups = {
  potencia: {
    label: "Potencia",
    description: "Demanda y disponibilidad",
    unit: "MW",
    series: [
      { key: "demanda", label: "Demanda", color: "#096b8e", decimals: 1, values: [48.2, 46.9, 45.3, 44.8, 46.1, 50.4, 55.2], versions: [
        { id: "demanda-pronostico-12ago", label: "Pronostico 12 ago", version: "v4", revision: 3, updated: "Hoy, 08:42", delta: 0 },
        { id: "demanda-programa-oficial", label: "Programa oficial agosto", version: "v3", revision: 1, updated: "10 ago, 17:10", delta: -2.4 },
        { id: "demanda-alta", label: "Escenario alta demanda", version: "v2", revision: 2, updated: "8 ago, 12:30", delta: 5.2 },
      ] },
      { key: "renovable", label: "Renovable disponible", color: "#13a779", decimals: 1, values: [12.4, 12.1, 11.8, 11.5, 13.2, 17.8, 21.4], versions: [
        { id: "renovable-pronostico-12ago", label: "Pronostico 12 ago", version: "v6", revision: 2, updated: "Hoy, 08:39", delta: 0 },
        { id: "renovable-conservador", label: "Pronostico conservador", version: "v5", revision: 1, updated: "10 ago, 16:55", delta: -3.1 },
      ] },
    ],
  },
  hidrologia: {
    label: "Hidrologia",
    description: "Caudales de la cuenca",
    unit: "m³/s",
    series: [
      { key: "caudal", label: "Caudal Los Cipreses", color: "#096b8e", decimals: 1, values: [31.4, 31.1, 30.8, 30.8, 30.4, 30.2, 29.9], versions: [
        { id: "caudal-programa-11ago", label: "Programa DGA 11 ago", version: "oficial-v7", revision: 4, updated: "Hoy, 07:55", delta: 0 },
        { id: "caudal-pronostico-base", label: "Pronostico base semanal", version: "v6", revision: 2, updated: "10 ago, 18:20", delta: 2.2 },
        { id: "caudal-seco", label: "Semana seca", version: "v5", revision: 1, updated: "7 ago, 11:05", delta: -5.8 },
      ] },
      { key: "afluente", label: "Afluente natural", color: "#13a779", decimals: 1, values: [8.2, 8.5, 8.1, 7.9, 8.4, 8.8, 9.1], versions: [
        { id: "afluente-programa-11ago", label: "Programa DGA 11 ago", version: "oficial-v4", revision: 2, updated: "Hoy, 07:55", delta: 0 },
        { id: "afluente-base", label: "Pronostico base semanal", version: "v3", revision: 1, updated: "10 ago, 18:20", delta: 1.1 },
      ] },
      { key: "caudal_minimo", label: "Caudal minimo", color: "#d66a2c", decimals: 1, values: [5, 5, 5, 5, 5, 5, 5], versions: [
        { id: "caudal-minimo-vigente", label: "Restriccion vigente", version: "norma-v2", revision: 1, updated: "1 ago, 09:00", delta: 0 },
        { id: "caudal-minimo-contingencia", label: "Restriccion contingencia", version: "norma-v1", revision: 1, updated: "15 jul, 09:00", delta: 1.5 },
      ] },
    ],
  },
  mercado: {
    label: "Mercado",
    description: "Precios de compra y venta",
    unit: "USD/MWh",
    series: [
      { key: "precio_compra", label: "Precio compra", color: "#096b8e", decimals: 2, values: [82.1, 78.4, 75.9, 74.2, 76.8, 89.1, 96.4], versions: [
        { id: "precio-compra-11ago", label: "Proyeccion 11 ago", version: "v8", revision: 3, updated: "Hoy, 08:10", delta: 0 },
        { id: "precio-compra-alto", label: "Mercado alto", version: "v7", revision: 1, updated: "9 ago, 14:30", delta: 12.5 },
      ] },
      { key: "precio_venta", label: "Precio venta", color: "#8b5cf6", decimals: 2, values: [76.2, 73.8, 71.4, 69.8, 72.5, 83.6, 90.2], versions: [
        { id: "precio-venta-11ago", label: "Proyeccion 11 ago", version: "v8", revision: 2, updated: "Hoy, 08:10", delta: 0 },
        { id: "precio-venta-alto", label: "Mercado alto", version: "v7", revision: 1, updated: "9 ago, 14:30", delta: 10.2 },
      ] },
    ],
  },
};

const allConfiguredSeries = Object.values(seriesGroups).flatMap((group) => group.series);

const state = {
  variant: variantFromUrl(),
  runState: stateFromUrl(),
  dataGroup: groupFromUrl(),
  dataView: dataViewFromUrl(),
  selectedVersions: versionsFromUrl(),
  savedEdits: {},
  draftEdits: {},
  revisionBumps: {},
  saveStatus: "saved",
  lastSaveMessage: "Datos cargados desde la base SQL",
  step: 1,
  prepOpen: false,
  timers: [],
};

function variantFromUrl() {
  const requested = new URLSearchParams(window.location.search)
    .get("variant")
    ?.toUpperCase();
  return variants[requested] ? requested : "A";
}

function stateFromUrl() {
  const requested = new URLSearchParams(window.location.search).get("state");
  return runStates[requested] ? requested : "idle";
}

function groupFromUrl() {
  const requested = new URLSearchParams(window.location.search).get("group");
  return seriesGroups[requested] ? requested : "potencia";
}

function dataViewFromUrl() {
  const requested = new URLSearchParams(window.location.search).get("view");
  return ["table", "chart"].includes(requested) ? requested : "table";
}

function versionsFromUrl() {
  const params = new URLSearchParams(window.location.search);
  return Object.fromEntries(
    allConfiguredSeries.map((series) => {
      const requested = params.get(`ts_${series.key}`);
      const selected = series.versions.some((version) => version.id === requested)
        ? requested
        : series.versions[0].id;
      return [series.key, selected];
    }),
  );
}

function updateUrl() {
  const url = new URL(window.location.href);
  url.searchParams.set("variant", state.variant);
  url.searchParams.set("state", state.runState);
  url.searchParams.set("group", state.dataGroup);
  url.searchParams.set("view", state.dataView);
  allConfiguredSeries.forEach((series) => {
    url.searchParams.set(`ts_${series.key}`, state.selectedVersions[series.key]);
  });
  window.history.replaceState({}, "", url);
}

function shell(content, navLabel) {
  return `
    <div class="app-shell variant-${state.variant.toLowerCase()}">
      <header class="app-header">
        <a class="brand" href="#" aria-label="Zenergies, inicio">
          <span class="brand-mark">Z</span>
          <span>
            <strong>Zenergies</strong>
            <small>Operaciones</small>
          </span>
        </a>
        <div class="app-context">
          <span class="context-label">Proyecto</span>
          <strong>Complejo Los Cipreses</strong>
        </div>
        <div class="identity">
          <span class="avatar">VA</span>
          <span><strong>Valentina Araya</strong><small>Operadora</small></span>
          <button class="icon-button" aria-label="Abrir menu de usuario">•••</button>
        </div>
      </header>
      <div class="surface-nav">
        <span class="active-dot"></span>
        <strong>${navLabel}</strong>
        <span class="surface-note">Configuracion: Operacion semanal</span>
      </div>
      ${content}
    </div>`;
}

function caseIdentity(compact = false) {
  return `
    <section class="case-identity ${compact ? "compact" : ""}">
      <div>
        <span class="eyebrow">Plan que vas a ejecutar</span>
        <h1>Operacion semanal · Los Cipreses</h1>
        <p>Programa la generacion hidroeléctrica y las compras de energia para cubrir la demanda prevista.</p>
      </div>
      <dl>
        <div><dt>Periodo disponible</dt><dd>1 jul – 30 sep 2026</dd></div>
        <div><dt>Ultima actualizacion</dt><dd>Hoy, 08:42</dd></div>
        <div><dt>Preparado por</dt><dd>Equipo de Planificacion</dd></div>
      </dl>
    </section>`;
}

function dateAndParameters(dense = false) {
  return `
    <section class="panel parameter-panel ${dense ? "dense" : ""}">
      <div class="section-heading">
        <div><span class="section-number">1</span><h2>Periodo y parametros</h2></div>
        <span class="validation-ok">✓ Dentro del rango disponible</span>
      </div>
      <div class="field-grid">
        <label><span>Desde</span><input type="date" value="2026-08-11" /></label>
        <label><span>Hasta</span><input type="date" value="2026-08-17" /></label>
        <label><span>Nivel inicial embalse</span><div class="input-unit"><input type="number" value="72" /><span>%</span></div></label>
        <label><span>Reserva operativa</span><div class="input-unit"><input type="number" value="8" /><span>%</span></div></label>
      </div>
      <div class="availability-track" aria-label="Periodo seleccionado dentro del rango disponible">
        <span class="availability-selection"></span>
      </div>
      <div class="availability-labels"><span>1 jul</span><strong>7 dias seleccionados</strong><span>30 sep</span></div>
    </section>`;
}

function dataTable(dense = false) {
  return `
    <section class="panel data-panel ${dense ? "dense" : ""}">
      <div class="section-heading">
        <div><span class="section-number">2</span><h2>Datos de entrada</h2></div>
        <div class="inline-actions"><span class="validation-ok">✓ 168 horas completas</span><button class="text-button">Pegar desde Excel</button></div>
      </div>
      <p class="section-copy">Revisa los datos habilitados para esta operacion. Puedes pegar una columna completa desde Excel.</p>
      <div class="table-wrap">
        <table>
          <thead><tr><th>Fecha y hora</th><th>Demanda <small>MW</small></th><th>Caudal Los Cipreses <small>m³/s</small></th><th>Precio compra <small>USD/MWh</small></th></tr></thead>
          <tbody>
            <tr><td>11 ago · 00:00</td><td><input value="48,2" aria-label="Demanda 11 agosto 00:00" /></td><td><input value="31,4" aria-label="Caudal 11 agosto 00:00" /></td><td><input value="82,10" aria-label="Precio 11 agosto 00:00" /></td></tr>
            <tr><td>11 ago · 01:00</td><td><input value="46,9" aria-label="Demanda 11 agosto 01:00" /></td><td><input value="31,1" aria-label="Caudal 11 agosto 01:00" /></td><td><input value="78,40" aria-label="Precio 11 agosto 01:00" /></td></tr>
            <tr><td>11 ago · 02:00</td><td><input value="45,3" aria-label="Demanda 11 agosto 02:00" /></td><td><input value="30,8" aria-label="Caudal 11 agosto 02:00" /></td><td><input value="75,90" aria-label="Precio 11 agosto 02:00" /></td></tr>
            <tr class="table-fade"><td>11 ago · 03:00</td><td>44,8</td><td>30,8</td><td>74,20</td></tr>
          </tbody>
        </table>
        <button class="table-more">Mostrar las 164 filas restantes</button>
      </div>
    </section>`;
}

function formatSeriesValue(value, decimals) {
  return value.toFixed(decimals).replace(".", ",");
}

function selectedSeriesVersion(series) {
  return series.versions.find((version) => version.id === state.selectedVersions[series.key]) || series.versions[0];
}

function seriesCellKey(series, rowIndex) {
  return `${series.key}|${rowIndex}`;
}

function seriesCellValue(series, rowIndex) {
  const key = seriesCellKey(series, rowIndex);
  const edited = state.draftEdits[key] ?? state.savedEdits[key];
  if (edited !== undefined) return edited;
  const version = selectedSeriesVersion(series);
  return formatSeriesValue(series.values[rowIndex] + version.delta, series.decimals);
}

function configuredSeriesValues(series) {
  return series.values.map((_, rowIndex) => Number(seriesCellValue(series, rowIndex).replace(",", ".")));
}

function pendingEditCount() {
  return Object.keys(state.draftEdits).length;
}

function versionSelectors(group) {
  const rows = group.series.map((series) => {
    const selected = selectedSeriesVersion(series);
    const revision = selected.revision + (state.revisionBumps[series.key] || 0);
    const options = series.versions
      .map((version) => `<option value="${version.id}" ${selected.id === version.id ? "selected" : ""}>${version.label} · ${version.version}</option>`)
      .join("");
    return `<label class="series-version-row">
      <span class="series-version-name"><i style="background:${series.color}"></i><strong>${series.label}</strong></span>
      <select data-series-version="${series.key}" aria-label="Version de ${series.label}">${options}</select>
      <span class="series-version-meta">Revision ${revision} · ${selected.updated}</span>
    </label>`;
  }).join("");

  return `<section class="version-source-panel" aria-label="Versiones de datos">
    <div class="version-source-heading">
      <div><span class="control-label">Versiones de datos</span><strong>Elige la fuente preparada para cada serie</strong></div>
      <span class="database-badge"><i></i> Base SQL conectada</span>
    </div>
    <div class="series-version-list">${rows}</div>
  </section>`;
}

function persistenceBar() {
  const count = pendingEditCount();
  const saving = state.saveStatus === "saving";
  const status = saving ? "saving" : count > 0 ? "dirty" : "saved";
  const title = saving
    ? "Guardando cambios…"
    : count > 0
      ? `${count} ${count === 1 ? "cambio sin guardar" : "cambios sin guardar"}`
      : state.lastSaveMessage;
  const detail = saving
    ? "Validando y creando una revision auditable"
    : count > 0
      ? "La ejecucion se habilita despues de guardar"
      : "Los valores visibles coinciden con la ultima revision";

  return `<div class="data-persistence-bar" data-save-status="${status}">
    <span class="persistence-icon">${saving ? "↻" : count > 0 ? "!" : "✓"}</span>
    <div><strong>${title}</strong><small>${detail}</small></div>
    <button class="secondary-button" data-save-series ${count === 0 || saving ? "disabled" : ""}>${saving ? "Guardando…" : "Guardar cambios"}</button>
  </div>`;
}

function configuredSeriesTable(group) {
  const timestamps = ["11 ago · 00:00", "11 ago · 01:00", "11 ago · 02:00", "11 ago · 03:00"];
  const headings = group.series
    .map((series) => `<th>${series.label} <small>${group.unit}</small></th>`)
    .join("");
  const rows = timestamps
    .map((timestamp, rowIndex) => {
      const cells = group.series
        .map((series) => {
          const value = seriesCellValue(series, rowIndex);
          if (rowIndex === timestamps.length - 1) return `<td>${value}</td>`;
          return `<td><input value="${value}" data-series-cell="${seriesCellKey(series, rowIndex)}" aria-label="${series.label} ${timestamp}" /></td>`;
        })
        .join("");
      return `<tr class="${rowIndex === timestamps.length - 1 ? "table-fade" : ""}"><td>${timestamp}</td>${cells}</tr>`;
    })
    .join("");

  return `<div class="table-wrap configured-table">
    <table>
      <thead><tr><th>Fecha y hora</th>${headings}</tr></thead>
      <tbody>${rows}</tbody>
    </table>
    <button class="table-more">Mostrar las 164 filas restantes</button>
  </div>`;
}

function configuredSeriesChart(group) {
  const allValues = group.series.flatMap((series) => configuredSeriesValues(series));
  const minimum = Math.min(...allValues);
  const maximum = Math.max(...allValues);
  const padding = Math.max((maximum - minimum) * 0.12, 1);
  const floor = minimum - padding;
  const ceiling = maximum + padding;
  const range = ceiling - floor;
  const paths = group.series
    .map((series) => {
      const seriesValues = configuredSeriesValues(series);
      const points = seriesValues
        .map((value, index) => {
          const x = 48 + index * (712 / (seriesValues.length - 1));
          const y = 214 - ((value - floor) / range) * 160;
          return `${x.toFixed(1)},${y.toFixed(1)}`;
        })
        .join(" ");
      return `<polyline points="${points}" fill="none" stroke="${series.color}" stroke-width="4" stroke-linecap="round" stroke-linejoin="round" />`;
    })
    .join("");
  const legend = group.series
    .map((series) => `<span><i style="background:${series.color}"></i>${series.label}</span>`)
    .join("");

  return `<div class="series-chart-card">
    <div class="series-chart-heading">
      <div><strong>${group.label}</strong><small>11 ago · primeras 7 horas</small></div>
      <div class="series-legend">${legend}</div>
    </div>
    <div class="series-chart-plot">
      <div class="series-axis"><span>${formatSeriesValue(ceiling, 1)}</span><span>${formatSeriesValue((ceiling + floor) / 2, 1)}</span><span>${formatSeriesValue(floor, 1)} ${group.unit}</span></div>
      <svg viewBox="0 0 800 240" preserveAspectRatio="none" role="img" aria-label="Grafico de ${group.label}">
        <line x1="48" y1="54" x2="760" y2="54" />
        <line x1="48" y1="134" x2="760" y2="134" />
        <line x1="48" y1="214" x2="760" y2="214" />
        ${paths}
      </svg>
      <div class="series-chart-x"><span>00:00</span><span>01:00</span><span>02:00</span><span>03:00</span><span>04:00</span><span>05:00</span><span>06:00</span></div>
    </div>
    <p class="chart-edit-note">El grafico permite inspeccionar tendencias. Cambia a <strong>Tabla</strong> para editar o pegar valores.</p>
  </div>`;
}

function seriesExplorer() {
  const group = seriesGroups[state.dataGroup];
  const groupTabs = Object.entries(seriesGroups)
    .map(([key, item]) => `<button role="tab" aria-selected="${state.dataGroup === key}" data-series-group="${key}"><span>${item.label}</span><small>${item.series.length} ${item.series.length === 1 ? "serie" : "series"}</small></button>`)
    .join("");

  return `
    <section class="panel data-panel series-explorer">
      <div class="section-heading">
        <div><span class="section-number">2</span><h2>Datos de entrada</h2></div>
        <div class="inline-actions"><span class="validation-ok">✓ 168 horas completas</span>${state.dataView === "table" ? '<button class="text-button">Pegar desde Excel</button>' : ""}</div>
      </div>
      <p class="section-copy">Revisa los datos habilitados para esta operacion. Los grupos, nombres y orden fueron definidos por el equipo de Planificacion.</p>
      <div class="data-explorer-toolbar">
        <div>
          <span class="control-label">Grupo de series</span>
          <div class="series-tabs" role="tablist" aria-label="Grupos de series configurados">${groupTabs}</div>
        </div>
        <div>
          <span class="control-label">Vista</span>
          <div class="view-toggle" aria-label="Cambiar vista">
            <button aria-pressed="${state.dataView === "table"}" data-data-view="table"><span aria-hidden="true">▦</span> Tabla</button>
            <button aria-pressed="${state.dataView === "chart"}" data-data-view="chart"><span aria-hidden="true">⌁</span> Grafico</button>
          </div>
        </div>
      </div>
      ${versionSelectors(group)}
      <div class="active-group-summary"><div><strong>${group.label}</strong><span>${group.description}</span></div><span>${group.series.length} series · ${group.unit}</span></div>
      ${state.dataView === "table" ? configuredSeriesTable(group) : configuredSeriesChart(group)}
      ${state.dataView === "table" ? persistenceBar() : ""}
    </section>`;
}

function reviewSummary() {
  const pending = pendingEditCount();
  return `
    <div class="review-summary">
      <div><span>Periodo</span><strong>11–17 ago 2026</strong><small>7 dias · 168 horas</small></div>
      <div><span>Datos</span><strong>${pending > 0 ? "Sin guardar" : "Completos"}</strong><small>${pending > 0 ? `${pending} cambios pendientes` : "7 series en 3 grupos"}</small></div>
      <div><span>Parametros</span><strong>2 ajustados</strong><small>Sin advertencias</small></div>
    </div>`;
}

function runButton(label = "Ejecutar plan") {
  const unsaved = pendingEditCount() > 0 || state.saveStatus === "saving";
  const disabled = ["queued", "running"].includes(state.runState) || unsaved;
  return `<button class="run-button" data-run ${disabled ? "disabled" : ""}>
    <span class="run-icon">▶</span><span>${unsaved ? "Guarda los cambios" : disabled ? "Ejecucion en curso" : label}</span>
  </button>`;
}

function runStatus(mode = "full") {
  const content = {
    idle: {
      icon: "✓",
      title: "Todo listo para ejecutar",
      copy: "La cobertura y los parametros fueron revisados.",
      detail: "La ejecucion suele tardar entre 2 y 4 minutos.",
    },
    queued: {
      icon: "2",
      title: "Tu ejecucion esta en cola",
      copy: "Hay una ejecucion antes que la tuya.",
      detail: "Puedes salir de esta pantalla; te avisaremos cuando termine.",
    },
    running: {
      icon: "↻",
      title: "Calculando el plan optimo",
      copy: "Procesando hora 104 de 168 · 62%",
      detail: "Tiempo transcurrido 01:48 · faltan cerca de 01:10.",
    },
    success: {
      icon: "✓",
      title: "Plan completado",
      copy: "Finalizo hoy a las 09:17 en 02:58.",
      detail: "Todos los datos del periodo fueron procesados.",
    },
    error: {
      icon: "!",
      title: "No pudimos completar el plan",
      copy: "Faltan datos de caudal el 14 ago entre 08:00 y 12:00.",
      detail: "Corrige las 5 celdas indicadas y vuelve a ejecutar.",
    },
  }[state.runState];

  return `
    <section class="run-status status-${state.runState} ${mode}">
      <span class="status-icon">${content.icon}</span>
      <div class="status-message"><span class="eyebrow">Estado de la ejecucion</span><h2>${content.title}</h2><p>${content.copy}</p><small>${content.detail}</small></div>
      ${state.runState === "running" ? '<div class="progress"><span></span></div>' : ""}
      ${state.runState === "error" ? '<div class="status-actions"><button class="secondary-button">Ir a los datos</button><button class="text-button">Ver detalle tecnico</button></div>' : ""}
      ${state.runState === "success" ? '<div class="status-actions"><button class="secondary-button">Ver resultado completo</button><button class="text-button">Descargar resumen</button></div>' : ""}
    </section>`;
}

function resultOverview() {
  return `
    <section class="result-overview">
      <div class="result-heading"><div><span class="eyebrow">Ultimo resultado · hoy, 09:17</span><h2>Operacion semanal · 11–17 ago</h2></div><span class="success-badge">Completado</span></div>
      <div class="kpi-grid">
        <article><span>Costo total</span><strong>US$ 286.420</strong><small>−4,8% vs. plan anterior</small></article>
        <article><span>Generacion propia</span><strong>71%</strong><small>3.842 MWh</small></article>
        <article><span>Compra a red</span><strong>1.567 MWh</strong><small>Principalmente 18:00–22:00</small></article>
        <article><span>Vertimiento</span><strong>0,6%</strong><small>Dentro del objetivo</small></article>
      </div>
      <div class="chart-card">
        <div class="chart-heading"><strong>Demanda y abastecimiento</strong><span><i class="legend-own"></i> Generacion propia <i class="legend-grid"></i> Compra a red</span></div>
        <div class="chart" aria-label="Grafico simulado de demanda y abastecimiento">
          <div class="chart-y"><span>80 MW</span><span>40 MW</span><span>0</span></div>
          <svg viewBox="0 0 800 180" preserveAspectRatio="none" role="img" aria-label="Curvas simuladas de generacion y compra">
            <path class="area-grid" d="M0 145 C80 140 90 100 160 110 S250 150 320 120 S410 50 480 82 S570 135 640 90 S730 60 800 72 L800 180 L0 180 Z" />
            <path class="line-own" d="M0 118 C80 106 90 86 160 94 S250 125 320 100 S410 70 480 74 S570 102 640 82 S730 90 800 62" />
          </svg>
          <div class="chart-x"><span>Mar 11</span><span>Mie 12</span><span>Jue 13</span><span>Vie 14</span><span>Sab 15</span><span>Dom 16</span><span>Lun 17</span></div>
        </div>
      </div>
    </section>`;
}

function runHistory(compact = false) {
  return `
    <section class="history ${compact ? "compact" : ""}">
      <div class="section-heading"><div><h2>Historial reciente</h2><p>Selecciona dos resultados para compararlos.</p></div><button class="secondary-button" data-compare disabled>Comparar <span data-compare-count>0</span>/2</button></div>
      <div class="history-list">
        <label class="history-row current"><input type="checkbox" data-compare-item /><span class="history-date"><strong>11–17 ago</strong><small>Hoy, 09:17 · Valentina</small></span><span><strong>US$ 286.420</strong><small>02:58</small></span><span class="success-badge">Completado</span><button class="icon-button" aria-label="Abrir resultado">→</button></label>
        <label class="history-row"><input type="checkbox" data-compare-item /><span class="history-date"><strong>4–10 ago</strong><small>4 ago, 08:55 · Martin</small></span><span><strong>US$ 300.910</strong><small>03:14</small></span><span class="success-badge">Completado</span><button class="icon-button" aria-label="Abrir resultado">→</button></label>
        <label class="history-row"><input type="checkbox" data-compare-item /><span class="history-date"><strong>28 jul–3 ago</strong><small>28 jul, 09:06 · Valentina</small></span><span><strong>—</strong><small>01:12</small></span><span class="error-badge">Error</span><button class="icon-button" aria-label="Abrir resultado">→</button></label>
      </div>
    </section>`;
}

function variantA() {
  return shell(`
    <main class="a-main">
      ${caseIdentity()}
      <div class="a-workspace">
        <div class="a-inputs">${dateAndParameters()}${seriesExplorer()}</div>
        <aside class="a-run-panel">
          <span class="eyebrow">Revision antes de ejecutar</span>
          <h2>Este es el plan que vas a correr</h2>
          ${reviewSummary()}
          ${runStatus("compact")}
          ${runButton()}
          <button class="text-button" data-fail>Simular una falla</button>
        </aside>
      </div>
      ${runHistory()}
    </main>`, "Nueva ejecucion");
}

function wizardStepContent() {
  if (state.step === 1) return dateAndParameters();
  if (state.step === 2) return dataTable();
  if (state.step === 3) {
    return `<section class="panel wizard-review"><div class="section-heading"><div><span class="section-number">3</span><h2>Revisa antes de ejecutar</h2></div><span class="validation-ok">✓ Sin observaciones</span></div>${reviewSummary()}${runStatus()}<div class="wizard-run-actions">${runButton("Confirmar y ejecutar")}<button class="text-button" data-fail>Simular una falla</button></div></section>`;
  }
  return `<section class="panel wizard-result">${state.runState === "success" ? resultOverview() : runStatus()}${runHistory(true)}</section>`;
}

function variantB() {
  const steps = [
    [1, "Periodo y parametros", "Define que vas a ejecutar"],
    [2, "Datos de entrada", "Revisa y corrige las series"],
    [3, "Confirmar", "Comprueba todo antes de correr"],
    [4, "Resultado", "Sigue la ejecucion y revisa"],
  ];
  return shell(`
    <main class="b-main">
      <aside class="step-rail">
        <span class="eyebrow">Nueva ejecucion</span>
        <h1>Operacion semanal</h1>
        <p>Completa los pasos en orden. Puedes volver sin perder cambios.</p>
        <ol>${steps.map(([number, title, copy]) => `<li class="${state.step === number ? "active" : ""} ${state.step > number ? "done" : ""}"><button data-step="${number}"><span>${state.step > number ? "✓" : number}</span><strong>${title}</strong><small>${copy}</small></button></li>`).join("")}</ol>
        <a href="#history" data-step="4">Ver historial de ejecuciones →</a>
      </aside>
      <section class="wizard-stage">
        <div class="wizard-context">${caseIdentity(true)}</div>
        ${wizardStepContent()}
        <div class="wizard-footer">
          <button class="secondary-button" data-step="${Math.max(1, state.step - 1)}" ${state.step === 1 ? "disabled" : ""}>← Volver</button>
          <span>Paso ${state.step} de 4</span>
          ${state.step < 3 ? `<button data-step="${state.step + 1}">Continuar →</button>` : ""}
        </div>
      </section>
    </main>`, "Preparar ejecucion");
}

function preparationDrawer() {
  if (!state.prepOpen) return "";
  return `<div class="drawer-backdrop" data-close-prep><aside class="prep-drawer" role="dialog" aria-modal="true" aria-labelledby="prep-title" onclick="event.stopPropagation()"><div class="drawer-heading"><div><span class="eyebrow">Nueva ejecucion</span><h2 id="prep-title">Preparar Operacion semanal</h2></div><button class="icon-button" data-close-prep aria-label="Cerrar">×</button></div>${dateAndParameters(true)}${dataTable(true)}<div class="drawer-footer"><div><strong>168 horas completas</strong><small>Sin observaciones</small></div>${runButton("Revisar y ejecutar")}</div></aside></div>`;
}

function variantC() {
  return shell(`
    <main class="c-main">
      <section class="c-hero">
        <div><span class="eyebrow">Operacion semanal · Los Cipreses</span><h1>Buenos dias, Valentina</h1><p>El ultimo plan termino correctamente. Tienes datos disponibles hasta el 30 de septiembre.</p></div>
        <button class="new-run-button" data-open-prep><span>＋</span> Preparar nueva ejecucion</button>
      </section>
      ${state.runState === "idle" ? "" : runStatus("banner")}
      <div class="c-layout">
        <div>${resultOverview()}</div>
        <aside class="activity-rail">
          <div class="rail-heading"><h2>Actividad</h2><button class="text-button">Ver todo</button></div>
          <ol class="timeline">
            <li class="complete"><span></span><div><strong>Plan completado</strong><p>11–17 ago · US$ 286.420</p><small>Hoy, 09:17 · Valentina</small></div></li>
            <li><span></span><div><strong>Datos actualizados</strong><p>Caudal Los Cipreses</p><small>Hoy, 08:42 · Martin</small></div></li>
            <li class="error"><span></span><div><strong>Ejecucion con error</strong><p>28 jul–3 ago · faltaron datos</p><small>28 jul, 09:07 · Valentina</small></div></li>
          </ol>
          <div class="next-window"><span class="eyebrow">Proximo periodo sugerido</span><strong>18–24 ago 2026</strong><p>Los datos estan completos para 168 horas.</p><button class="secondary-button" data-open-prep>Usar este periodo</button></div>
        </aside>
      </div>
      ${runHistory()}
    </main>
    ${preparationDrawer()}`, "Inicio");
}

function renderStateLab() {
  document.querySelector("#state-lab").innerHTML = `
    <span>Forzar estado</span>
    <div>${Object.entries(runStates).map(([key, label]) => `<button data-state="${key}" class="${state.runState === key ? "active" : ""}">${label}</button>`).join("")}</div>`;
}

function renderSwitcher() {
  const keys = Object.keys(variants);
  document.querySelector("#variant-switcher").innerHTML = `
    <button data-variant-direction="-1" aria-label="Variante anterior">←</button>
    <div><span>Variante ${state.variant} de ${keys.length}</span><strong>${variants[state.variant].name}</strong><small>${variants[state.variant].thesis}</small></div>
    <button data-variant-direction="1" aria-label="Variante siguiente">→</button>`;
}

function clearTimers() {
  state.timers.forEach(window.clearTimeout);
  state.timers = [];
}

function setRunState(next) {
  clearTimers();
  state.runState = next;
  if (["queued", "running", "success", "error"].includes(next) && state.variant === "B") state.step = next === "success" ? 4 : 3;
  updateUrl();
  render();
}

function simulateRun() {
  setRunState("queued");
  state.timers.push(window.setTimeout(() => setRunState("running"), 1300));
  state.timers.push(window.setTimeout(() => setRunState("success"), 4300));
}

function cycleVariant(direction) {
  const keys = Object.keys(variants);
  const index = keys.indexOf(state.variant);
  state.variant = keys[(index + direction + keys.length) % keys.length];
  state.step = 1;
  state.prepOpen = false;
  updateUrl();
  render();
}

function clearSeriesEdits(seriesKey) {
  [state.savedEdits, state.draftEdits].forEach((edits) => {
    Object.keys(edits)
      .filter((key) => key.startsWith(`${seriesKey}|`))
      .forEach((key) => delete edits[key]);
  });
}

function saveDataEdits() {
  if (pendingEditCount() === 0 || state.saveStatus === "saving") return;
  const touchedSeries = new Set(Object.keys(state.draftEdits).map((key) => key.split("|")[0]));
  state.saveStatus = "saving";
  render();
  state.timers.push(window.setTimeout(() => {
    Object.assign(state.savedEdits, state.draftEdits);
    state.draftEdits = {};
    touchedSeries.forEach((seriesKey) => {
      state.revisionBumps[seriesKey] = (state.revisionBumps[seriesKey] || 0) + 1;
    });
    state.saveStatus = "saved";
    state.lastSaveMessage = "Guardado en base de datos · ahora";
    render();
  }, 1100));
}

function bindInteractions() {
  document.querySelectorAll("[data-variant-direction]").forEach((button) => button.addEventListener("click", () => cycleVariant(Number(button.dataset.variantDirection))));
  document.querySelectorAll("[data-state]").forEach((button) => button.addEventListener("click", () => setRunState(button.dataset.state)));
  document.querySelectorAll("[data-run]").forEach((button) => button.addEventListener("click", simulateRun));
  document.querySelectorAll("[data-fail]").forEach((button) => button.addEventListener("click", () => setRunState("error")));
  document.querySelectorAll("[data-step]").forEach((button) => button.addEventListener("click", (event) => { event.preventDefault(); state.step = Number(button.dataset.step); render(); }));
  document.querySelectorAll("[data-open-prep]").forEach((button) => button.addEventListener("click", () => { state.prepOpen = true; render(); }));
  document.querySelectorAll("[data-close-prep]").forEach((button) => button.addEventListener("click", () => { state.prepOpen = false; render(); }));
  document.querySelectorAll("[data-series-group]").forEach((button) => button.addEventListener("click", () => {
    state.dataGroup = button.dataset.seriesGroup;
    updateUrl();
    render();
  }));
  document.querySelectorAll("[data-data-view]").forEach((button) => button.addEventListener("click", () => {
    state.dataView = button.dataset.dataView;
    updateUrl();
    render();
  }));
  document.querySelectorAll("[data-series-version]").forEach((select) => select.addEventListener("change", () => {
    const seriesKey = select.dataset.seriesVersion;
    state.selectedVersions[seriesKey] = select.value;
    clearSeriesEdits(seriesKey);
    state.revisionBumps[seriesKey] = 0;
    state.saveStatus = "saved";
    state.lastSaveMessage = "Version cargada desde la base SQL";
    updateUrl();
    render();
  }));
  document.querySelectorAll("[data-series-cell]").forEach((input) => {
    input.addEventListener("input", () => {
      state.draftEdits[input.dataset.seriesCell] = input.value;
      state.saveStatus = "dirty";
    });
    input.addEventListener("blur", () => {
      if (state.saveStatus === "dirty") render();
    });
  });
  document.querySelectorAll("[data-save-series]").forEach((button) => button.addEventListener("click", saveDataEdits));
  const checks = [...document.querySelectorAll("[data-compare-item]")];
  checks.forEach((check) => check.addEventListener("change", () => {
    if (checks.filter((item) => item.checked).length > 2) check.checked = false;
    const count = checks.filter((item) => item.checked).length;
    document.querySelectorAll("[data-compare-count]").forEach((node) => { node.textContent = count; });
    document.querySelectorAll("[data-compare]").forEach((button) => { button.disabled = count !== 2; });
  }));
}

function render() {
  const views = { A: variantA, B: variantB, C: variantC };
  document.querySelector("#prototype-root").innerHTML = views[state.variant]();
  renderStateLab();
  renderSwitcher();
  bindInteractions();
  document.title = `${state.variant} · ${variants[state.variant].name} · Prototipo`;
}

document.addEventListener("keydown", (event) => {
  const target = event.target;
  if (target.matches("input, textarea, select, [contenteditable='true']")) return;
  if (event.key === "ArrowLeft") cycleVariant(-1);
  if (event.key === "ArrowRight") cycleVariant(1);
});

window.addEventListener("popstate", () => {
  state.variant = variantFromUrl();
  state.runState = stateFromUrl();
  state.dataGroup = groupFromUrl();
  state.dataView = dataViewFromUrl();
  state.selectedVersions = versionsFromUrl();
  render();
});

updateUrl();
render();
