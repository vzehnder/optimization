// Prototipo desechable del contrato de la tabla editable y del pegado desde
// Excel. Tres variantes de forma de tabla, intercambiables con ?variant=, mas
// un laboratorio de politicas para reaccionar a las decisiones abiertas.
//
// Las reglas de validacion son un espejo de app/time_series_catalog.py
// (validate_catalog_value_edits). El parser de locale NO existe en el backend
// de hoy: es la propuesta que este prototipo pone sobre la mesa.

// ---------------------------------------------------------------------------
// Registro canonico (espejo de TIME_SERIES_SIGNAL_CATALOG)
// ---------------------------------------------------------------------------

const SIGNAL_CATALOG = {
  price_usd_per_mwh: { unit: "USD/MWh", nonnegative: false },
  export_price_usd_per_mwh: { unit: "USD/MWh", nonnegative: false },
  load_demand_mw: { unit: "MW", nonnegative: true },
  renewable_available_power_mw: { unit: "MW", nonnegative: true },
  hydro_inflow_m3s: { unit: "m3/s", nonnegative: true },
  natural_inflow_m3s: { unit: "m3/s", nonnegative: true },
  minimum_flow_m3s: { unit: "m3/s", nonnegative: true },
};

// Copias operativas: cada una es un set plano no derivado con linaje inerte.
const COPIES = {
  demanda: { id: 118, label: "Demanda operativa", origin: "Programa oficial agosto · rev 12", revision: 4 },
  meteo: { id: 119, label: "Meteorologia operativa", origin: "Pronostico 12 ago · rev 6", revision: 2 },
  hidro: { id: 120, label: "Hidrologia operativa", origin: "Programa DGA 11 ago · rev 7", revision: 9 },
  mercado: { id: 121, label: "Mercado operativo", origin: "Proyeccion 11 ago · rev 8", revision: 3 },
};

// Grupos definidos por el analista (decision del cascaron, ticket 02).
const GROUPS = {
  potencia: { label: "Potencia", hint: "Demanda y disponibilidad" },
  hidrologia: { label: "Hidrologia", hint: "Caudales de la cuenca" },
  mercado: { label: "Mercado", hint: "Precios de compra y venta" },
};

// Columnas = señales que el ingeniero habilito en la configuracion.
const COLUMNS = [
  { key: "load_demand_mw", label: "Demanda", copy: "demanda", group: "potencia", decimals: 1, editable: true, seed: 48, swing: 14 },
  { key: "renewable_available_power_mw", label: "Renovable disponible", copy: "meteo", group: "potencia", decimals: 1, editable: true, seed: 14, swing: 12 },
  { key: "hydro_inflow_m3s", label: "Caudal Los Cipreses", copy: "hidro", group: "hidrologia", decimals: 2, editable: true, seed: 31, swing: 4 },
  { key: "natural_inflow_m3s", label: "Afluente natural", copy: "hidro", group: "hidrologia", decimals: 2, editable: true, seed: 8, swing: 2 },
  { key: "minimum_flow_m3s", label: "Caudal minimo", copy: "hidro", group: "hidrologia", decimals: 2, editable: false, lockReason: "Restriccion normativa; el ingeniero no la habilito", seed: 5, swing: 0 },
  { key: "price_usd_per_mwh", label: "Precio compra", copy: "mercado", group: "mercado", decimals: 2, editable: true, seed: 82, swing: 38 },
  { key: "export_price_usd_per_mwh", label: "Precio venta", copy: "mercado", group: "mercado", decimals: 2, editable: true, seed: 76, swing: 34 },
];

const VARIANTS = {
  A: { name: "Por grupo", thesis: "Pestañas del analista; un grupo puede mezclar copias" },
  B: { name: "Unificada por caso", thesis: "Una sola tabla con todas las señales habilitadas" },
  C: { name: "Por copia operativa", thesis: "Una tabla = una copia = un guardado atomico" },
};

const RANGES = {
  anio: { label: "Todo el periodo (8760 h)", from: 0, to: 8759 },
  mes: { label: "Agosto (744 h)", from: 5088, to: 5831 },
  semana: { label: "Semana 10-16 ago (168 h)", from: 5304, to: 5471 },
  dia: { label: "Dia 12 ago (24 h)", from: 5352, to: 5375 },
};

const ROW_H = 28;
const PERIOD_COUNT = 8760;
const BYTES_PER_EDIT = 48; // {"period_index":5352,"signal_key":"...","value_text":"..."}

// ---------------------------------------------------------------------------
// Datos simulados deterministas
// ---------------------------------------------------------------------------

function mulberry32(a) {
  return function () {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const MONTHS = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"];

const periods = (() => {
  const start = Date.UTC(2026, 0, 1, 0, 0, 0);
  const list = new Array(PERIOD_COUNT);
  for (let i = 0; i < PERIOD_COUNT; i += 1) {
    const at = new Date(start + i * 3600000);
    const day = String(at.getUTCDate()).padStart(2, "0");
    const hour = String(at.getUTCHours()).padStart(2, "0");
    list[i] = { index: i, label: `${day} ${MONTHS[at.getUTCMonth()]} ${hour}:00` };
  }
  return list;
})();

const baseValues = (() => {
  const store = {};
  COLUMNS.forEach((column, columnNumber) => {
    const random = mulberry32(1337 + columnNumber * 977);
    const series = new Float64Array(PERIOD_COUNT);
    for (let i = 0; i < PERIOD_COUNT; i += 1) {
      const daily = Math.sin(((i % 24) / 24) * Math.PI * 2 - Math.PI / 2);
      const seasonal = Math.sin((i / PERIOD_COUNT) * Math.PI * 2);
      const noise = random() - 0.5;
      const raw = column.seed + column.swing * (0.55 * daily + 0.3 * seasonal + 0.35 * noise);
      const definition = SIGNAL_CATALOG[column.key];
      const bounded = definition.nonnegative ? Math.max(0, raw) : raw;
      series[i] = Number(bounded.toFixed(column.decimals));
    }
    store[column.key] = series;
  });
  return store;
})();

// ---------------------------------------------------------------------------
// Estado
// ---------------------------------------------------------------------------

const state = {
  variant: "A",
  group: "potencia",
  copy: "demanda",
  range: "semana",
  format: "rechazar",
  align: "truncar",
  saveRule: "todo-o-nada",
  lease: "propia",
  nextSaveConflicts: false,
  edits: new Map(), // "periodIndex|signalKey" -> { text, value, error, ambiguous, alt, was }
  anchor: null,
  scrollTop: 0,
  sheet: null,
  notice: null,
  revisions: Object.fromEntries(Object.entries(COPIES).map(([key, value]) => [key, value.revision])),
  lastSave: null,
  attested: false,
  saving: false,
};

const editKey = (periodIndex, signalKey) => `${periodIndex}|${signalKey}`;

// ---------------------------------------------------------------------------
// Columnas visibles y copias tocadas
// ---------------------------------------------------------------------------

function visibleColumns() {
  if (state.variant === "B") return COLUMNS;
  if (state.variant === "C") return COLUMNS.filter((column) => column.copy === state.copy);
  return COLUMNS.filter((column) => column.group === state.group);
}

function touchedCopies() {
  const copies = new Set();
  state.edits.forEach((_edit, key) => {
    const signalKey = key.split("|")[1];
    const column = COLUMNS.find((item) => item.key === signalKey);
    if (column) copies.add(column.copy);
  });
  return [...copies];
}

function reachableCopies() {
  return [...new Set(visibleColumns().map((column) => column.copy))];
}

const readOnly = () => state.lease === "ajena";

// ---------------------------------------------------------------------------
// Formato y parseo numerico
// ---------------------------------------------------------------------------

function formatValue(value, decimals) {
  return new Intl.NumberFormat("es-CL", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(value);
}

// Devuelve { value, ambiguous, alt, error }. `alt` es la lectura alternativa
// cuando el texto admite dos interpretaciones de locale.
function parseNumber(raw, signalKey) {
  const text = String(raw).trim().replace(/\s| /g, "");
  if (text === "") return { error: "vacio" };

  const hasComma = text.includes(",");
  const hasDot = text.includes(".");

  // Ambiguedad estructural, simetrica entre separadores: un unico separador
  // seguido de exactamente tres digitos, y precedido por un grupo de miles
  // valido (1 a 3 digitos sin cero a la izquierda). "1.234" vale 1234 o 1,234;
  // "1,234" tambien. En cambio "0,001" no es ambiguo, porque "0" no es un grupo
  // de miles: solo puede ser un decimal. Con dos o cuatro decimales, con cuatro
  // digitos por delante, o con ambos separadores presentes, la lectura tambien
  // es unica. Fuera de este caso no hace falta locale alguno.
  const separators = (text.match(/[.,]/g) || []).length;
  const structurallyAmbiguous = separators === 1 && /^[-+]?[1-9]\d{0,2}[.,]\d{3}$/.test(text);

  let mode = state.format;
  if (mode === "rechazar") {
    if (structurallyAmbiguous) {
      const separator = hasComma ? "," : ".";
      return {
        error: "ambiguo",
        detail: text,
        alt: Number(text.replace(separator, ".")),
        value: Number(text.replace(separator, "")),
      };
    }
    // Sin ambiguedad, el ultimo separador es el decimal.
    mode = hasComma && hasDot
      ? text.lastIndexOf(",") > text.lastIndexOf(".") ? "es" : "en"
      : hasComma ? (separators > 1 ? "en" : "es") : (separators > 1 ? "es" : "en");
  } else if (mode === "auto") {
    if (hasComma && hasDot) mode = text.lastIndexOf(",") > text.lastIndexOf(".") ? "es" : "en";
    else if (hasComma) mode = "es";
    else mode = "en";
  }

  const cleaned = mode === "es" ? text.replace(/\./g, "").replace(",", ".") : text.replace(/,/g, "");
  if (!/^[-+]?\d*\.?\d+([eE][-+]?\d+)?$/.test(cleaned)) {
    return { error: "no-numerico", detail: text };
  }

  const value = Number(cleaned);
  if (!Number.isFinite(value)) return { error: "no-finito", detail: text };

  // En los modos de comparacion la ambiguedad no bloquea: se resuelve por
  // locale y se marca, para poder contrastarla con la regla decidida.
  const ambiguous = structurallyAmbiguous;
  let alt = null;
  if (ambiguous) {
    const separator = hasComma ? "," : ".";
    const asDecimal = Number(text.replace(separator, "."));
    const asThousands = Number(text.replace(separator, ""));
    const separatorIsDecimal = mode === "es" ? separator === "," : separator === ".";
    alt = separatorIsDecimal ? asThousands : asDecimal;
  }

  const definition = SIGNAL_CATALOG[signalKey];
  if (definition.nonnegative && value < 0) {
    return { value, ambiguous, alt, error: "negativo", detail: text };
  }
  return { value, ambiguous, alt, error: null };
}

const ERROR_TEXT = {
  vacio: "celda vacia",
  "no-numerico": "no es numerico",
  "no-finito": "no es finito",
  negativo: "negativo no permitido en esta señal",
  ambiguo: "formato ambiguo: un separador con tres digitos detras vale mil o una fraccion",
  bloqueada: "columna no habilitada",
  "fuera-de-rango": "periodo fuera del tramo",
};

// ---------------------------------------------------------------------------
// Edicion
// ---------------------------------------------------------------------------

function commitCell(periodIndex, signalKey, rawText) {
  const column = COLUMNS.find((item) => item.key === signalKey);
  if (!column || !column.editable || readOnly()) return;
  const range = RANGES[state.range];
  if (periodIndex < range.from || periodIndex > range.to) return;

  const key = editKey(periodIndex, signalKey);
  const was = baseValues[signalKey][periodIndex];
  const text = String(rawText).trim();

  if (text === "" || text === formatValue(was, column.decimals)) {
    state.edits.delete(key);
    return;
  }
  const parsed = parseNumber(text, signalKey);
  state.edits.set(key, {
    text,
    value: parsed.value,
    error: parsed.error,
    ambiguous: Boolean(parsed.ambiguous),
    alt: parsed.alt,
    was,
  });
}

function parseClipboard(text) {
  const rows = String(text)
    .replace(/\r\n/g, "\n")
    .replace(/\r/g, "\n")
    .split("\n")
    .filter((row, index, all) => row !== "" || index < all.length - 1)
    .map((row) => row.split("\t"));
  if (!rows.length) return { rows: [], header: false };

  // Encabezado pegado por accidente: primera fila sin ningun valor numerico.
  const first = rows[0];
  const numericInFirst = first.some((cell) => cell.trim() !== "" && /\d/.test(cell));
  const header = rows.length > 1 && !numericInFirst;
  return { rows: header ? rows.slice(1) : rows, header };
}

function applyPaste(clipboardText) {
  if (readOnly()) {
    state.notice = { kind: "bad", text: "Camila Rojas tiene el lease de edicion. La tabla esta en solo lectura." };
    return;
  }
  if (!state.anchor) {
    state.notice = { kind: "warn", text: "Selecciona la celda donde empieza el bloque antes de pegar." };
    return;
  }

  const { rows, header } = parseClipboard(clipboardText);
  if (!rows.length) return;

  const columns = visibleColumns();
  const range = RANGES[state.range];
  const anchorColumn = columns.findIndex((column) => column.key === state.anchor.key);
  const anchorRow = state.anchor.period;

  const blockRows = rows.length;
  const blockCols = Math.max(...rows.map((row) => row.length));
  const roomRows = range.to - anchorRow + 1;
  const roomCols = columns.length - anchorColumn;

  const overflowRows = Math.max(0, blockRows - roomRows);
  const overflowCols = Math.max(0, blockCols - roomCols);

  if ((overflowRows || overflowCols) && state.align === "rechazar") {
    state.notice = {
      kind: "bad",
      text:
        `Bloque rechazado completo: trae ${blockRows} fila(s) x ${blockCols} columna(s) y ` +
        `desde la celda anclada caben ${roomRows} x ${roomCols}. ` +
        "El pegado nunca extiende el horizonte: los periodos no existen en la copia operativa.",
    };
    return;
  }

  const usableRows = Math.min(blockRows, roomRows);
  const usableCols = Math.min(blockCols, roomCols);
  const lockedHits = [];
  let applied = 0;

  for (let r = 0; r < usableRows; r += 1) {
    for (let c = 0; c < usableCols; c += 1) {
      const cell = rows[r][c];
      if (cell === undefined || cell.trim() === "") continue;
      const column = columns[anchorColumn + c];
      if (!column.editable) {
        if (!lockedHits.includes(column.label)) lockedHits.push(column.label);
        continue;
      }
      commitCell(anchorRow + r, column.key, cell);
      applied += 1;
    }
  }

  const parts = [`Se aplicaron ${applied} celda(s) desde ${periods[anchorRow].label}.`];
  if (header) parts.push("Se detecto y descarto una fila de encabezado.");
  if (overflowRows) parts.push(`Se truncaron ${overflowRows} fila(s) que caian fuera del tramo.`);
  if (overflowCols) parts.push(`Se truncaron ${overflowCols} columna(s) a la derecha.`);
  if (lockedHits.length) parts.push(`Se omitieron columnas no habilitadas: ${lockedHits.join(", ")}.`);

  const problems = [...state.edits.values()].filter((edit) => edit.error).length;
  if (problems) parts.push(`${problems} celda(s) quedaron marcadas con error.`);

  state.notice = {
    kind: overflowRows || overflowCols || lockedHits.length || problems ? "warn" : "good",
    text: parts.join(" "),
  };
}

// ---------------------------------------------------------------------------
// Diff y guardado
// ---------------------------------------------------------------------------

function buildDiff() {
  const bySignal = new Map();
  const invalid = [];
  const ambiguous = [];

  state.edits.forEach((edit, key) => {
    const [periodText, signalKey] = key.split("|");
    const periodIndex = Number(periodText);
    const column = COLUMNS.find((item) => item.key === signalKey);
    if (!bySignal.has(signalKey)) {
      bySignal.set(signalKey, { column, cells: [], wasMin: Infinity, wasMax: -Infinity, nowMin: Infinity, nowMax: -Infinity });
    }
    const bucket = bySignal.get(signalKey);
    bucket.cells.push({ periodIndex, edit });
    bucket.wasMin = Math.min(bucket.wasMin, edit.was);
    bucket.wasMax = Math.max(bucket.wasMax, edit.was);
    if (edit.error) invalid.push({ periodIndex, column, edit });
    else {
      bucket.nowMin = Math.min(bucket.nowMin, edit.value);
      bucket.nowMax = Math.max(bucket.nowMax, edit.value);
    }
    if (edit.ambiguous) ambiguous.push({ periodIndex, column, edit });
  });

  const rows = [...bySignal.values()].sort((a, b) => a.column.label.localeCompare(b.column.label));
  const periodsTouched = new Set([...state.edits.keys()].map((key) => key.split("|")[0])).size;
  return { rows, invalid, ambiguous, periodsTouched, copies: touchedCopies() };
}

function confirmSave() {
  const diff = buildDiff();
  const valid = state.edits.size - diff.invalid.length;
  if (!valid) return;

  state.saving = true;
  state.sheet = null;
  render();

  window.setTimeout(() => {
    state.saving = false;
    if (state.nextSaveConflicts) {
      state.nextSaveConflicts = false;
      diff.copies.forEach((copy) => {
        state.revisions[copy] += 1;
      });
      state.sheet = { kind: "conflicto", diff };
      render();
      return;
    }

    const snapshot = [];
    state.edits.forEach((edit, key) => {
      if (edit.error) return; // invalidas nunca cruzan; la regla decide si bloquean al resto
      const [periodText, signalKey] = key.split("|");
      const periodIndex = Number(periodText);
      snapshot.push({ periodIndex, signalKey, was: edit.was });
      baseValues[signalKey][periodIndex] = edit.value;
    });

    const keptErrors = new Map();
    if (state.saveRule === "guardar-validas") {
      state.edits.forEach((edit, key) => {
        if (edit.error) keptErrors.set(key, edit);
      });
    }
    state.edits = keptErrors;

    diff.copies.forEach((copy) => {
      state.revisions[copy] += 1;
    });
    state.lastSave = { snapshot, copies: diff.copies, cells: snapshot.length, at: new Date() };
    state.attested = true;
    state.sheet = { kind: "guardado", diff, cells: snapshot.length };
    render();
  }, 850);
}

function undoLastSave() {
  if (!state.lastSave) return;
  state.lastSave.snapshot.forEach(({ periodIndex, signalKey, was }) => {
    baseValues[signalKey][periodIndex] = was;
  });
  state.lastSave.copies.forEach((copy) => {
    state.revisions[copy] += 1;
  });
  state.notice = {
    kind: "good",
    text: `Se deshizo tu ultimo guardado (${state.lastSave.cells} celdas). Se creo una revision nueva; nada se reescribio.`,
  };
  state.lastSave = null;
  render();
}

// ---------------------------------------------------------------------------
// Render
// ---------------------------------------------------------------------------

function leaseBar() {
  if (readOnly()) {
    return `<div class="lease-bar foreign">
      <strong>Camila Rojas esta editando</strong>
      <span>El lease vence en 09:12. Tu vista es solo lectura y se actualiza al liberarse.</span>
      <span class="spacer"></span>
      <button class="button quiet" data-request-lease>Avisarme cuando se libere</button>
    </div>`;
  }
  return `<div class="lease-bar">
    <strong>Tienes la edicion</strong>
    <span>Lease exclusivo hasta las 16:42 · se renueva mientras trabajas.</span>
    <span class="spacer"></span>
    <span>Revision vigente <code>${reachableCopies().map((copy) => `${COPIES[copy].label} r${state.revisions[copy]}`).join(" · ")}</code></span>
  </div>`;
}

function tabsMarkup() {
  if (state.variant === "B") {
    return `<div class="tabs"><span class="set-hint">Una sola tabla: ${COLUMNS.length} señales de ${reachableCopies().length} copias operativas</span></div>`;
  }
  if (state.variant === "C") {
    const buttons = Object.entries(COPIES)
      .map(([key, copy]) => `<button data-copy="${key}" aria-pressed="${state.copy === key}">${copy.label}</button>`)
      .join("");
    return `<div class="tabs">${buttons}<span class="set-hint">Origen: ${COPIES[state.copy].origin}</span></div>`;
  }
  const buttons = Object.entries(GROUPS)
    .map(([key, group]) => `<button data-group="${key}" aria-pressed="${state.group === key}">${group.label}</button>`)
    .join("");
  const copies = reachableCopies();
  return `<div class="tabs">${buttons}<span class="set-hint">${GROUPS[state.group].hint} · toca ${copies.length} copia(s) operativa(s)</span></div>`;
}

function rangeBar() {
  const options = Object.entries(RANGES)
    .map(([key, range]) => `<option value="${key}" ${state.range === key ? "selected" : ""}>${range.label}</option>`)
    .join("");
  const range = RANGES[state.range];
  return `<div class="range-bar">
    <label>Tramo editable <select data-range>${options}</select></label>
    <span>${periods[range.from].label} → ${periods[range.to].label}</span>
    <span class="spacer">Fuera del tramo la tabla se ve, pero no se edita ni recibe pegado.</span>
  </div>`;
}

function toolbar() {
  const invalid = [...state.edits.values()].filter((edit) => edit.error).length;
  const ambiguous = [...state.edits.values()].filter((edit) => edit.ambiguous && !edit.error).length;
  const copies = touchedCopies();
  const bytes = state.edits.size * BYTES_PER_EDIT;
  const chip = state.saving
    ? `<span class="chip dirty">Guardando…</span>`
    : state.edits.size === 0
      ? `<span class="chip clean">Sin cambios pendientes</span>`
      : invalid
        ? `<span class="chip error">${state.edits.size} cambio(s) · ${invalid} con error</span>`
        : `<span class="chip dirty">${state.edits.size} cambio(s) sin guardar</span>`;

  return `<div class="grid-toolbar">
    ${chip}
    ${ambiguous ? `<span class="chip dirty">${ambiguous} lectura(s) ambigua(s)</span>` : ""}
    ${copies.length > 1 ? `<span class="chip error">${copies.length} copias en un mismo guardado</span>` : ""}
    <span class="spacer"></span>
    <span>${state.edits.size ? `~${(bytes / 1024).toFixed(1)} KB en el PUT` : `${PERIOD_COUNT} periodos · ${visibleColumns().length} columnas`}</span>
  </div>`;
}

function headerRow() {
  const cells = visibleColumns()
    .map((column) => {
      const definition = SIGNAL_CATALOG[column.key];
      const meta = state.variant === "C"
        ? `${definition.unit}${definition.nonnegative ? " · ≥ 0" : ""}`
        : `${definition.unit} · ${COPIES[column.copy].label}`;
      return `<th class="${column.editable ? "" : "locked"}" title="${column.editable ? column.key : column.lockReason}">
        <span class="sig-label">${column.label}${column.editable ? "" : " 🔒"}</span>
        <span class="sig-meta">${meta}</span>
      </th>`;
    })
    .join("");
  return `<tr><th class="stamp">Periodo</th>${cells}</tr>`;
}

function renderRows() {
  const body = document.querySelector("#grid-body");
  if (!body) return;
  const scroller = document.querySelector("#grid-scroll");
  const columns = visibleColumns();
  const range = RANGES[state.range];
  const viewHeight = scroller ? scroller.clientHeight || 416 : 416;
  const first = Math.max(0, Math.floor(state.scrollTop / ROW_H) - 4);
  const last = Math.min(PERIOD_COUNT, first + Math.ceil(viewHeight / ROW_H) + 10);
  const span = columns.length + 1;

  let html = first ? `<tr style="height:${first * ROW_H}px"><td colspan="${span}"></td></tr>` : "";
  for (let index = first; index < last; index += 1) {
    const inRange = index >= range.from && index <= range.to;
    const cells = columns
      .map((column) => {
        const edit = state.edits.get(editKey(index, column.key));
        const locked = !column.editable || !inRange || readOnly();
        const classes = ["cell"];
        if (locked) classes.push("locked");
        if (edit) classes.push(edit.error ? "invalid" : edit.ambiguous ? "ambiguous" : "edited");
        if (state.anchor && state.anchor.period === index && state.anchor.key === column.key) classes.push("anchor");
        const shown = edit
          ? edit.error
            ? edit.text
            : formatValue(edit.value, column.decimals)
          : formatValue(baseValues[column.key][index], column.decimals);
        const title = edit && edit.error
          ? `${ERROR_TEXT[edit.error]} · ${column.key} · periodo ${index}`
          : edit && edit.ambiguous
            ? `Lectura ambigua: «${edit.text}» se interpreto como ${formatValue(edit.value, column.decimals)}; la otra lectura es ${formatValue(edit.alt, column.decimals)}`
            : `${column.key} · periodo ${index}`;
        return `<td><span class="${classes.join(" ")}" title="${title}"
          data-period="${index}" data-signal="${column.key}"
          ${locked ? "" : 'contenteditable="true" spellcheck="false"'}>${shown}</span></td>`;
      })
      .join("");
    html += `<tr style="height:${ROW_H}px" class="${inRange ? "" : "out-of-range"}"><td class="stamp">${periods[index].label}</td>${cells}</tr>`;
  }
  if (last < PERIOD_COUNT) html += `<tr style="height:${(PERIOD_COUNT - last) * ROW_H}px"><td colspan="${span}"></td></tr>`;
  body.innerHTML = html;
}

function noticeMarkup() {
  if (!state.notice) return "";
  return `<div class="notice ${state.notice.kind}">${state.notice.text}</div>`;
}

function actionBar() {
  const invalid = [...state.edits.values()].filter((edit) => edit.error).length;
  const blocked = invalid > 0 && state.saveRule === "todo-o-nada";
  // Revisar siempre esta disponible: es la unica superficie que explica los
  // errores. Lo que se bloquea es confirmar, dentro de la hoja de revision.
  const canReview = state.edits.size > 0 && !readOnly() && !state.saving;
  return `<div class="action-bar">
    <button class="button" data-review ${canReview ? "" : "disabled"}>${blocked ? "Revisar errores" : "Revisar y guardar"}</button>
    <button class="button quiet" data-discard ${state.edits.size && !state.saving ? "" : "disabled"}>Descartar cambios</button>
    ${state.lastSave ? `<button class="button ghost" data-undo>Deshacer mi ultimo guardado</button>` : ""}
    <span class="spacer"></span>
    <span class="hint">${
      state.saving
        ? "Guardando el bloque…"
        : blocked
          ? `<strong>${invalid} celda(s) invalidas</strong> bloquean el guardado completo (regla todo-o-nada).`
          : state.attested && !state.edits.size
            ? "<strong>Ejecutar habilitado:</strong> el guardado refresco la atestacion de la consola."
            : state.edits.size
              ? "Ejecutar esta deshabilitado mientras haya cambios sin guardar."
              : "Pega una columna desde Excel sobre la celda anclada."
    }</span>
  </div>`;
}

function diffSheet(sheet) {
  const diff = sheet.diff || buildDiff();
  if (sheet.kind === "conflicto") {
    return `<div class="sheet">
      <header>
        <h2>Tu guardado no se aplico</h2>
        <p>Otro guardado dejo la revision base obsoleta mientras revisabas.</p>
      </header>
      <div class="body">
        <div class="notice bad">
          El bloque se rechazo completo. <strong>Nada se mezclo automaticamente</strong> y tus valores
          siguen en pantalla.
          <ul>
            ${diff.copies.map((copy) => `<li>${COPIES[copy].label}: la revision vigente ahora es r${state.revisions[copy]}.</li>`).join("")}
          </ul>
        </div>
        <p class="hint">Recargar trae los valores vigentes y descarta tu bloque. Es la unica salida que
        el contrato de revisiones optimistas permite hoy.</p>
      </div>
      <footer>
        <button class="button" data-reload>Recargar valores vigentes</button>
        <span class="spacer"></span>
        <button class="button quiet" data-close>Volver a la tabla</button>
      </footer>
    </div>`;
  }

  if (sheet.kind === "guardado") {
    return `<div class="sheet">
      <header>
        <h2>Guardado</h2>
        <p>${sheet.cells} celda(s) persistidas en ${diff.copies.length} copia(s) operativa(s).</p>
      </header>
      <div class="body">
        <div class="notice good">
          ${diff.copies.map((copy) => `${COPIES[copy].label} → revision r${state.revisions[copy]}`).join("<br />")}
          <br /><br />
          <strong>El guardado es la atestacion.</strong> La misma transaccion refresco el hash registrado
          de la dependencia de la consola, asi que ejecutar quedo habilitado sin revalidar nada.
        </div>
        ${state.edits.size ? `<div class="notice warn">Quedaron ${state.edits.size} celda(s) invalidas sin guardar, marcadas en la tabla.</div>` : ""}
      </div>
      <footer>
        <span class="spacer"></span>
        <button class="button" data-close>Volver a la tabla</button>
      </footer>
    </div>`;
  }

  const rows = diff.rows
    .map((row) => {
      const sample = row.cells
        .slice(0, 2)
        .map(({ periodIndex, edit }) => `${periods[periodIndex].label}: ${formatValue(edit.was, row.column.decimals)} → ${edit.error ? edit.text : formatValue(edit.value, row.column.decimals)}`)
        .join("<br />");
      const now = Number.isFinite(row.nowMin)
        ? `${formatValue(row.nowMin, row.column.decimals)} … ${formatValue(row.nowMax, row.column.decimals)}`
        : "—";
      return `<tr>
        <td class="label">${row.column.label}<br /><span class="was" style="font-weight:400">${COPIES[row.column.copy].label}</span></td>
        <td>${row.cells.length}</td>
        <td class="was">${formatValue(row.wasMin, row.column.decimals)} … ${formatValue(row.wasMax, row.column.decimals)}</td>
        <td class="now">${now}</td>
        <td>${sample}</td>
      </tr>`;
    })
    .join("");

  const invalidList = diff.invalid
    .slice(0, 6)
    .map(({ periodIndex, column, edit }) => `<li>${periods[periodIndex].label} · ${column.label}: "${edit.text}" ${ERROR_TEXT[edit.error]}</li>`)
    .join("");
  const ambiguousList = diff.ambiguous
    .slice(0, 6)
    .map(({ periodIndex, column, edit }) => `<li>${periods[periodIndex].label} · ${column.label}: "${edit.text}" se leyo ${formatValue(edit.value, column.decimals)}; la otra lectura es ${formatValue(edit.alt, column.decimals)}</li>`)
    .join("");

  const blocked = diff.invalid.length > 0 && state.saveRule === "todo-o-nada";
  const savable = state.edits.size - (state.saveRule === "todo-o-nada" ? 0 : diff.invalid.length);

  return `<div class="sheet">
    <header>
      <h2>Revisa antes de guardar</h2>
      <p>Este es el bloque que cruzara hacia la copia operativa. Nada se ha escrito todavia.</p>
    </header>
    <div class="body">
      <dl class="diff-summary">
        <div><dt>Celdas</dt><dd>${state.edits.size}</dd></div>
        <div><dt>Periodos</dt><dd>${diff.periodsTouched}</dd></div>
        <div><dt>Copias operativas</dt><dd>${diff.copies.length}</dd></div>
      </dl>
      ${diff.copies.length > 1 ? `<div class="notice warn">Este guardado toca <strong>${diff.copies.length} copias operativas</strong>: ${diff.copies.map((copy) => COPIES[copy].label).join(", ")}. La primitiva de backend escribe una revision <em>por set</em>, asi que la atomicidad de todo el bloque exige envolver las ${diff.copies.length} escrituras en una sola transaccion.</div>` : ""}
      ${diff.invalid.length ? `<div class="notice bad"><strong>${diff.invalid.length} celda(s) invalidas.</strong>${blocked ? " Con la regla todo-o-nada el guardado completo queda bloqueado." : " Se guardaran solo las validas y las invalidas quedaran marcadas."}<ul>${invalidList}</ul></div>` : ""}
      ${diff.ambiguous.length ? `<div class="notice warn"><strong>${diff.ambiguous.length} lectura(s) ambigua(s)</strong> por formato numerico (${state.format === "es" ? "es-CL" : state.format === "en" ? "en-US" : "auto"}).<ul>${ambiguousList}</ul></div>` : ""}
      <table class="diff">
        <thead><tr><th>Señal</th><th>Celdas</th><th>Rango antes</th><th>Rango despues</th><th>Muestra</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>
    </div>
    <footer>
      <button class="button" data-confirm ${savable > 0 && !blocked ? "" : "disabled"}>Confirmar ${savable} celda(s)</button>
      <span class="spacer"></span>
      <button class="button quiet" data-close>Volver a la tabla</button>
    </footer>
  </div>`;
}

function renderLab() {
  const node = document.querySelector("#policy-lab");
  node.innerHTML = `
    <h3>Laboratorio de politicas</h3>
    <label>Formato numerico al pegar
      <select data-lab="format">
        <option value="rechazar" ${state.format === "rechazar" ? "selected" : ""}>Rechazar lo ambiguo (decidido)</option>
        <option value="es" ${state.format === "es" ? "selected" : ""}>es-CL (1.234,5)</option>
        <option value="en" ${state.format === "en" ? "selected" : ""}>en-US (1,234.5)</option>
        <option value="auto" ${state.format === "auto" ? "selected" : ""}>Auto-detectar</option>
      </select>
      <span class="lab-note">Decidido: se rechaza toda cadena ambigua. Los otros modos quedan solo para contrastar.</span>
    </label>
    <label>Bloque mas largo que el tramo
      <select data-lab="align">
        <option value="truncar" ${state.align === "truncar" ? "selected" : ""}>Truncar y avisar</option>
        <option value="rechazar" ${state.align === "rechazar" ? "selected" : ""}>Rechazar el bloque</option>
      </select>
    </label>
    <label>Celdas invalidas al guardar
      <select data-lab="saveRule">
        <option value="todo-o-nada" ${state.saveRule === "todo-o-nada" ? "selected" : ""}>Todo o nada</option>
        <option value="guardar-validas" ${state.saveRule === "guardar-validas" ? "selected" : ""}>Guardar solo las validas</option>
      </select>
    </label>
    <label>Lease de edicion
      <div class="lab-row">
        <button data-lease="propia" aria-pressed="${state.lease === "propia"}">Mia</button>
        <button data-lease="ajena" aria-pressed="${state.lease === "ajena"}">De otro</button>
      </div>
    </label>
    <label>Proximo guardado
      <div class="lab-row">
        <button data-conflict="off" aria-pressed="${!state.nextSaveConflicts}">Normal</button>
        <button data-conflict="on" aria-pressed="${state.nextSaveConflicts}">Conflicto de revision</button>
      </div>
    </label>`;
}

function renderSwitcher() {
  const node = document.querySelector("#variant-switcher");
  const buttons = Object.entries(VARIANTS)
    .map(([key, variant]) => `<button data-variant="${key}" aria-pressed="${state.variant === key}">${key} · ${variant.name}</button>`)
    .join("");
  node.innerHTML = `${buttons}<span class="thesis">${VARIANTS[state.variant].thesis}</span>`;
}

function render() {
  const columns = visibleColumns();
  document.querySelector("#prototype-root").innerHTML = `
    <div class="app-shell">
      <header class="app-header">
        <span class="brand"><span class="brand-mark">Z</span><span><strong>BESS Quillota · Plan semanal</strong><small>Consola de operador</small></span></span>
        <span class="header-note">Prototipo del ticket 07 · datos de entrada</span>
      </header>
      <div class="workspace">
        ${leaseBar()}
        <div class="table-head">
          <div>
            <span class="eyebrow">Datos de entrada</span>
            <h1>${state.variant === "C" ? COPIES[state.copy].label : state.variant === "B" ? "Todas las señales del caso" : GROUPS[state.group].label}</h1>
            <p>${columns.length} columna(s) · ${columns.filter((column) => !column.editable).length} bloqueada(s) · pegado desde Excel habilitado</p>
          </div>
        </div>
        ${tabsMarkup()}
        ${rangeBar()}
        ${noticeMarkup()}
        <div class="grid-shell">
          ${toolbar()}
          <div class="grid-scroll" id="grid-scroll">
            <table class="grid">
              <thead>${headerRow()}</thead>
              <tbody id="grid-body"></tbody>
            </table>
          </div>
          <div class="legend">
            <span><i class="swatch edited"></i> editado</span>
            <span><i class="swatch ambiguous"></i> lectura ambigua</span>
            <span><i class="swatch invalid"></i> invalido</span>
            <span><i class="swatch locked"></i> no habilitado por el ingeniero</span>
            <span>Los valores se muestran en formato es-CL.</span>
          </div>
        </div>
        ${actionBar()}
      </div>
    </div>`;

  const scroller = document.querySelector("#grid-scroll");
  renderRows();
  scroller.scrollTop = state.scrollTop;

  const overlay = document.querySelector("#overlay");
  overlay.hidden = !state.sheet;
  overlay.innerHTML = state.sheet ? diffSheet(state.sheet) : "";

  renderLab();
  renderSwitcher();
  bind();
  document.title = `${state.variant} · ${VARIANTS[state.variant].name} · Prototipo tabla`;
}

// ---------------------------------------------------------------------------
// Eventos
// ---------------------------------------------------------------------------

function bind() {
  const scroller = document.querySelector("#grid-scroll");

  scroller.addEventListener("scroll", () => {
    state.scrollTop = scroller.scrollTop;
    renderRows();
  });

  scroller.addEventListener("mousedown", (event) => {
    const cell = event.target.closest(".cell");
    if (!cell) return;
    state.anchor = { period: Number(cell.dataset.period), key: cell.dataset.signal };
    scroller.querySelectorAll(".cell.anchor").forEach((node) => node.classList.remove("anchor"));
    cell.classList.add("anchor");
  });

  scroller.addEventListener("paste", (event) => {
    event.preventDefault();
    const text = (event.clipboardData || window.clipboardData).getData("text/plain");
    const cell = event.target.closest(".cell");
    if (cell) state.anchor = { period: Number(cell.dataset.period), key: cell.dataset.signal };
    applyPaste(text);
    render();
  });

  scroller.addEventListener("keydown", (event) => {
    if (event.key !== "Enter") return;
    event.preventDefault();
    event.target.blur();
  });

  scroller.addEventListener(
    "blur",
    (event) => {
      const cell = event.target.closest && event.target.closest(".cell");
      if (!cell || !cell.isContentEditable) return;
      commitCell(Number(cell.dataset.period), cell.dataset.signal, cell.textContent);
      // El aviso del pegado sobrevive a las ediciones manuales: es la unica
      // superficie que reporta filas truncadas y debe seguir ahi al guardar.
      render();
    },
    true,
  );

  document.querySelectorAll("[data-group]").forEach((button) =>
    button.addEventListener("click", () => {
      state.group = button.dataset.group;
      state.anchor = null;
      state.notice = null;
      render();
    }),
  );
  document.querySelectorAll("[data-copy]").forEach((button) =>
    button.addEventListener("click", () => {
      state.copy = button.dataset.copy;
      state.anchor = null;
      state.notice = null;
      render();
    }),
  );
  document.querySelectorAll("[data-variant]").forEach((button) =>
    button.addEventListener("click", () => {
      state.variant = button.dataset.variant;
      state.anchor = null;
      state.notice = null;
      updateUrl();
      render();
    }),
  );
  document.querySelectorAll("[data-lease]").forEach((button) =>
    button.addEventListener("click", () => {
      state.lease = button.dataset.lease;
      render();
    }),
  );
  document.querySelectorAll("[data-conflict]").forEach((button) =>
    button.addEventListener("click", () => {
      state.nextSaveConflicts = button.dataset.conflict === "on";
      render();
    }),
  );

  const range = document.querySelector("[data-range]");
  if (range) {
    range.addEventListener("change", () => {
      state.range = range.value;
      state.scrollTop = Math.max(0, (RANGES[state.range].from - 2) * ROW_H);
      state.anchor = null;
      state.notice = null;
      render();
    });
  }

  document.querySelectorAll("[data-lab]").forEach((select) =>
    select.addEventListener("change", () => {
      state[select.dataset.lab] = select.value;
      // Re-evaluar las celdas ya pegadas con la politica nueva.
      const pending = [...state.edits.entries()];
      state.edits = new Map();
      pending.forEach(([key, edit]) => {
        const [periodText, signalKey] = key.split("|");
        commitCell(Number(periodText), signalKey, edit.text);
      });
      render();
    }),
  );

  const review = document.querySelector("[data-review]");
  if (review) review.addEventListener("click", () => {
    state.sheet = { kind: "diff" };
    render();
  });
  const discard = document.querySelector("[data-discard]");
  if (discard) discard.addEventListener("click", () => {
    state.edits = new Map();
    state.notice = { kind: "good", text: "Cambios descartados. La copia operativa no se toco." };
    render();
  });
  const undo = document.querySelector("[data-undo]");
  if (undo) undo.addEventListener("click", undoLastSave);

  const overlay = document.querySelector("#overlay");
  overlay.querySelectorAll("[data-close]").forEach((button) =>
    button.addEventListener("click", () => {
      state.sheet = null;
      render();
    }),
  );
  const confirm = overlay.querySelector("[data-confirm]");
  if (confirm) confirm.addEventListener("click", confirmSave);
  const reload = overlay.querySelector("[data-reload]");
  if (reload) reload.addEventListener("click", () => {
    state.edits = new Map();
    state.sheet = null;
    state.notice = { kind: "warn", text: "Valores recargados desde la revision vigente. Tu bloque se descarto." };
    render();
  });
}

function updateUrl() {
  const url = new URL(window.location.href);
  url.searchParams.set("variant", state.variant);
  window.history.replaceState({}, "", url);
}

state.variant = (new URL(window.location.href).searchParams.get("variant") || "A").toUpperCase();
if (!VARIANTS[state.variant]) state.variant = "A";
state.scrollTop = Math.max(0, (RANGES[state.range].from - 2) * ROW_H);
updateUrl();
render();
