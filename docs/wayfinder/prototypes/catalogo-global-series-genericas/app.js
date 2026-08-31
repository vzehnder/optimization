// Three throwaway UI variants for the global time-series catalog, switchable
// through ?variant=. The page is intentionally standalone and uses mock data.

const variants = {
  A: { name: 'Catálogo en capas', thesis: 'Descubrir primero; actuar desde el detalle' },
  B: { name: 'Mesa de vinculación', thesis: 'Objeto, necesidad y fuente en una sola vista' },
  C: { name: 'Recorrido protegido', thesis: 'Decisiones sensibles en pasos explícitos' },
};

const scenarioNames = {
  browse: 'Explorar',
  link: 'Vincular',
  bulk: 'Vínculo masivo',
  replace: 'Reemplazar',
  specific: 'Serie específica',
  shared: 'Actualizar compartida',
};

const statusNames = {
  normal: 'Normal',
  empty: 'Vacío',
  loading: 'Cargando',
  error: 'Error',
  forbidden: 'Sin permiso',
  incompatible: 'Incompatible',
  stale: 'Stale',
  archived: 'Archivado',
};

const signals = [
  {
    id: 'demanda-centro',
    name: 'Demanda horaria · Centro',
    key: 'load_demand',
    kind: 'Demanda',
    dataClass: 'Pronóstico',
    unit: 'MW',
    scope: 'Proyecto',
    project: 'Complejo Los Cipreses',
    set: 'Pronóstico operacional · Semana 36',
    revision: 'r12',
    hash: '91ab…c84f',
    coverage: '31 ago — 7 sep 2026',
    resolution: '1 hora',
    origin: 'API · Planificación',
    associations: 3,
    bindings: 2,
    status: 'Vigente',
  },
  {
    id: 'afluente-maipo',
    name: 'Afluente natural · Maipo',
    key: 'natural_inflow',
    kind: 'Afluente natural',
    dataClass: 'Real',
    unit: 'm³/s',
    scope: 'Global',
    project: 'Publicado por Operaciones',
    set: 'Hidrología oficial · DGA',
    revision: 'r28',
    hash: '5e20…77ad',
    coverage: '1 ene — 30 ago 2026',
    resolution: '1 hora',
    origin: 'XLSX · DGA',
    associations: 14,
    bindings: 9,
    status: 'Vigente',
  },
  {
    id: 'precio-spot',
    name: 'Precio spot · SEN',
    key: 'energy_price',
    kind: 'Precio de energía',
    dataClass: 'Pronóstico',
    unit: 'USD/MWh',
    scope: 'Global',
    project: 'Publicado por Mercado',
    set: 'Mercado eléctrico · Q3',
    revision: 'r41',
    hash: '6fc1…4a02',
    coverage: '1 jul — 30 sep 2026',
    resolution: '1 hora',
    origin: 'API · Coordinador',
    associations: 22,
    bindings: 17,
    status: 'Vigente',
  },
  {
    id: 'solar-norte',
    name: 'Disponible solar · Norte',
    key: 'renewable_available_power',
    kind: 'Potencia renovable',
    dataClass: 'Pronóstico',
    unit: 'MW',
    scope: 'Proyecto',
    project: 'Complejo Los Cipreses',
    set: 'Pronóstico solar · Proveedor A',
    revision: 'r7',
    hash: '2d01…af19',
    coverage: '31 ago — 7 sep 2026',
    resolution: '15 minutos',
    origin: 'CSV · Proveedor A',
    associations: 1,
    bindings: 1,
    status: 'Stale',
  },
  {
    id: 'caudal-minimo',
    name: 'Caudal mínimo · Tramo 4',
    key: 'minimum_flow',
    kind: 'Caudal mínimo',
    dataClass: 'Programado',
    unit: 'm³/s',
    scope: 'Proyecto',
    project: 'Complejo Los Cipreses',
    set: 'Restricciones ambientales 2025',
    revision: 'r4',
    hash: 'aed4…170b',
    coverage: '1 ene — 31 dic 2025',
    resolution: '1 día',
    origin: 'CSV · Cumplimiento',
    associations: 1,
    bindings: 0,
    status: 'Archivado',
  },
];

const state = {
  variant: validParam('variant', Object.keys(variants), 'A').toUpperCase(),
  scenario: validParam('scenario', Object.keys(scenarioNames), 'browse'),
  status: validParam('status', Object.keys(statusNames), 'normal'),
  entry: validParam('entry', ['catalog', 'object'], 'catalog'),
  surface: validParam('surface', ['inputs', 'results', 'legacy'], 'inputs'),
  signal: validParam('signal', signals.map(function (item) { return item.id; }), 'afluente-maipo'),
  step: Number(validParam('step', ['1', '2', '3', '4'], '1')),
  selected: new Set(['afluente-maipo', 'precio-spot']),
  toast: '',
};

function validParam(name, allowed, fallback) {
  const value = new URLSearchParams(window.location.search).get(name);
  if (!value) return fallback;
  const normalized = name === 'variant' ? value.toUpperCase() : value;
  return allowed.includes(normalized) ? normalized : fallback;
}

function selectedSignal() {
  return signals.find(function (item) { return item.id === state.signal; }) || signals[0];
}

function escapeHtml(value) {
  return String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('\"', '&quot;')
    .replaceAll("'", '&#039;');
}

function updateUrl() {
  const url = new URL(window.location.href);
  url.searchParams.set('variant', state.variant);
  url.searchParams.set('scenario', state.scenario);
  url.searchParams.set('status', state.status);
  url.searchParams.set('entry', state.entry);
  url.searchParams.set('surface', state.surface);
  url.searchParams.set('signal', state.signal);
  url.searchParams.set('step', String(state.step));
  window.history.replaceState({}, '', url);
}

function shell(content, context) {
  return '<div class=\"app-shell variant-' + state.variant.toLowerCase() + '\">' +
    '<header class=\"app-header\">' +
      '<a class=\"brand\" href=\"#\" aria-label=\"Zenergies, inicio\">' +
        '<span class=\"brand-mark\">Z</span><span><strong>Zenergies</strong><small>Administración de datos</small></span>' +
      '</a>' +
      '<div class=\"project-context\"><span>Proyecto activo</span><strong>Complejo Los Cipreses</strong><button>⌄</button></div>' +
      '<div class=\"identity\"><span class=\"avatar\">VA</span><span><strong>Valentina Araya</strong><small>Analyst</small></span><button class=\"icon-button\">•••</button></div>' +
    '</header>' +
    '<nav class=\"product-nav\">' +
      '<div><button>Resumen</button><button>Objetos</button><button class=\"active\">Series de tiempo</button><button>Casos</button></div>' +
      '<span>' + context + '</span>' +
    '</nav>' +
    content +
    toastMarkup() +
  '</div>';
}

function pageHeading(title, copy, actions) {
  return '<section class=\"page-heading\"><div><span class=\"eyebrow\">Datos de entrada</span><h1>' + title +
    '</h1><p>' + copy + '</p></div><div class=\"heading-actions\">' + (actions || '') + '</div></section>';
}

function sourceTabs() {
  const tabs = [
    ['inputs', 'Entradas', '38'],
    ['results', 'Resultados', '12'],
    ['legacy', 'Legacy', '6'],
  ];
  return '<nav class=\"source-tabs\" aria-label=\"Procedencia de series\">' + tabs.map(function (tab) {
    return '<button data-surface=\"' + tab[0] + '\" class=\"' + (state.surface === tab[0] ? 'active' : '') + '\">' +
      tab[1] + '<span>' + tab[2] + '</span></button>';
  }).join('') + '</nav>';
}

function entryToggle() {
  return '<div class=\"entry-toggle\" aria-label=\"Punto de entrada\">' +
    '<span>Iniciar desde</span>' +
    '<button data-entry=\"catalog\" class=\"' + (state.entry === 'catalog' ? 'active' : '') + '\">Catálogo</button>' +
    '<button data-entry=\"object\" class=\"' + (state.entry === 'object' ? 'active' : '') + '\">Objeto</button>' +
  '</div>';
}

function statusFrame(content) {
  if (state.status === 'loading') {
    return '<section class=\"system-state loading-state\"><span class=\"spinner\"></span><h2>Cargando catálogo autorizado</h2>' +
      '<p>Estamos verificando alcance, permisos y compatibilidad.</p><div class=\"skeleton-lines\"><i></i><i></i><i></i><i></i></div></section>';
  }
  if (state.status === 'empty') {
    return '<section class=\"system-state\"><span class=\"state-illustration\">∅</span><h2>No hay series que coincidan</h2>' +
      '<p>Quita un filtro o crea una serie específica desde el objeto. Una específica no aparecerá aquí.</p>' +
      '<button class=\"secondary-button\" data-command=\"reset-status\">Limpiar filtros</button></section>';
  }
  if (state.status === 'error') {
    return '<section class=\"system-state danger\"><span class=\"state-illustration\">!</span><h2>No pudimos cargar el catálogo</h2>' +
      '<p>Solicitud req_7J4P. Tus filtros se conservaron y ninguna operación fue enviada.</p>' +
      '<button class=\"secondary-button\" data-command=\"reset-status\">Reintentar</button></section>';
  }
  if (state.status === 'forbidden') {
    return '<section class=\"system-state locked\"><span class=\"state-illustration\">⌁</span><h2>No tienes acceso a esta superficie</h2>' +
      '<p>El catálogo está disponible solo para analyst y admin de proyectos autorizados. No revelamos identificadores ni conteos.</p>' +
      '<button class=\"secondary-button\">Volver al proyecto</button></section>';
  }
  return stateBanner() + content;
}

function stateBanner() {
  const banners = {
    incompatible: ['danger', 'Esta combinación no es compatible', 'La señal energy_price no puede cumplir load_demand sobre component:load. Código TS_COMPAT_OBJECT_TYPE_NOT_ALLOWED.'],
    stale: ['warning', 'El binding observa una revisión anterior', 'Está fijado en r27 · 2a40…b9e1; la fuente vigente es r28 · 5e20…77ad. La ejecución permanece bloqueada.'],
    archived: ['neutral', 'Esta señal está archivada', 'Se mantiene visible por historia y auditoría, pero no admite nuevas asociaciones ni bindings.'],
  };
  if (!banners[state.status]) return '';
  const banner = banners[state.status];
  return '<div class=\"status-banner ' + banner[0] + '\"><span>' + (banner[0] === 'danger' ? '×' : banner[0] === 'warning' ? '!' : 'i') +
    '</span><div><strong>' + banner[1] + '</strong><p>' + banner[2] + '</p></div><button data-command=\"reset-status\">Cerrar</button></div>';
}

function catalogFilters() {
  return '<aside class=\"filters-panel panel\"><div class=\"panel-title\"><h2>Filtros</h2><button class=\"text-button\">Limpiar</button></div>' +
    '<label class=\"search-field\"><span>Buscar</span><div><span>⌕</span><input value=\"\" placeholder=\"Nombre, clave o propietario\" /></div></label>' +
    filterGroup('Tipo semántico', ['Demanda', 'Afluente natural', 'Precio', 'Renovable'], 'Afluente natural') +
    filterGroup('Clase de datos', ['Real', 'Pronóstico', 'Programado'], 'Real') +
    filterGroup('Alcance', ['Mi proyecto', 'Global autorizado'], 'Global autorizado') +
    filterGroup('Estado', ['Vigente', 'Stale', 'Archivado'], 'Vigente') +
    '<details><summary>Más filtros <span>4</span></summary><p>Objeto vinculado, unidad, cobertura y resolución.</p></details>' +
  '</aside>';
}

function filterGroup(label, values, active) {
  return '<fieldset class=\"filter-group\"><legend>' + label + '</legend>' + values.map(function (value) {
    return '<label><input type=\"checkbox\" ' + (value === active ? 'checked' : '') + ' /><span>' + value + '</span><small>' +
      (value === active ? '8' : '12') + '</small></label>';
  }).join('') + '</fieldset>';
}

function catalogTable(compact) {
  const rows = signals.map(function (signal) {
    const selected = signal.id === state.signal;
    const checked = state.selected.has(signal.id);
    return '<tr class=\"' + (selected ? 'selected ' : '') + (signal.status.toLowerCase()) + '\" data-signal=\"' + signal.id + '\">' +
      '<td><input type=\"checkbox\" data-check-signal=\"' + signal.id + '\" ' + (checked ? 'checked' : '') + ' aria-label=\"Seleccionar ' + escapeHtml(signal.name) + '\" /></td>' +
      '<td><button class=\"signal-link\" data-signal=\"' + signal.id + '\"><strong>' + escapeHtml(signal.name) + '</strong><small>' + signal.key + '</small></button></td>' +
      '<td><strong>' + signal.kind + '</strong><small>' + signal.dataClass + '</small></td>' +
      (compact ? '' : '<td><span class=\"scope-badge ' + signal.scope.toLowerCase() + '\">' + signal.scope + '</span><small>' + signal.project + '</small></td>') +
      '<td><strong>' + signal.unit + '</strong><small>' + signal.resolution + '</small></td>' +
      '<td><span class=\"status-chip ' + signal.status.toLowerCase() + '\">' + signal.status + '</span><small>' + signal.revision + '</small></td>' +
    '</tr>';
  }).join('');

  return '<div class=\"catalog-table-wrap\"><table class=\"catalog-table\"><thead><tr><th></th><th>Señal</th><th>Tipo / clase</th>' +
    (compact ? '' : '<th>Alcance / propietario</th>') + '<th>Unidad / resolución</th><th>Estado</th></tr></thead><tbody>' + rows + '</tbody></table>' +
    '<footer><span>1–5 de 38 señales</span><div><button disabled>←</button><strong>1</strong><button>→</button></div></footer></div>';
}

function signalInspector() {
  const signal = selectedSignal();
  return '<aside class=\"inspector panel\"><div class=\"inspector-heading\"><div><span class=\"scope-badge ' + signal.scope.toLowerCase() + '\">' +
    signal.scope + '</span><span class=\"status-chip ' + signal.status.toLowerCase() + '\">' + signal.status + '</span></div><button class=\"icon-button\">×</button></div>' +
    '<span class=\"eyebrow\">Señal dentro de set</span><h2>' + signal.name + '</h2><p class=\"mono\">' + signal.key + '</p>' +
    '<div class=\"revision-card\"><span>Revisión vigente</span><strong>' + signal.revision + '</strong><code>' + signal.hash + '</code><i>Validada y sellada</i></div>' +
    '<dl class=\"metadata-list\"><div><dt>Set atómico</dt><dd>' + signal.set + '</dd></div><div><dt>Cobertura</dt><dd>' + signal.coverage +
    '</dd></div><div><dt>Resolución</dt><dd>' + signal.resolution + '</dd></div><div><dt>Procedencia</dt><dd>' + signal.origin +
    '</dd></div></dl>' +
    '<section class=\"relation-summary\"><div><span>' + signal.associations + '</span><small>objetos asociados</small></div><div><span>' + signal.bindings +
    '</span><small>bindings activos</small></div></section>' +
    '<div class=\"object-relations\"><h3>Objetos y bindings actuales</h3>' +
      relationRow('Carga Centro', 'load_demand', 'Asociada · Binding en Caso Base', 'ok') +
      relationRow('Carga Industrial', 'load_demand', 'Asociada · Sin binding', 'quiet') +
      relationRow('Variante Contingencia', 'load_demand', 'Binding r27 · stale', 'warn') +
    '</div>' +
    '<div class=\"inspector-actions\"><button class=\"primary-button\" data-scenario=\"link\">Vincular a objeto</button><button class=\"secondary-button\">Ver preview</button></div>' +
  '</aside>';
}

function relationRow(name, role, copy, tone) {
  return '<article class=\"relation-row ' + tone + '\"><span class=\"object-icon\">◇</span><div><strong>' + name + '</strong><small>' + role + '</small><p>' +
    copy + '</p></div><button>›</button></article>';
}

function alternateSurface() {
  if (state.surface === 'results') {
    return '<section class=\"alternate-surface panel\"><div><span class=\"source-mark results\">R</span><div><h2>Resultados de corridas</h2>' +
      '<p>Artefactos de salida read-only. No son candidatos del catálogo de entradas.</p></div></div>' +
      '<table><thead><tr><th>Resultado</th><th>Corrida</th><th>Cobertura</th><th>Estado</th></tr></thead><tbody>' +
      '<tr><td>Despacho óptimo · Unidad 2</td><td>RUN-1048</td><td>31 ago — 7 sep</td><td><span class=\"status-chip vigente\">Publicado</span></td></tr>' +
      '<tr><td>Costo marginal · SEN</td><td>RUN-1048</td><td>31 ago — 7 sep</td><td><span class=\"status-chip vigente\">Publicado</span></td></tr>' +
      '</tbody></table><div class=\"info-callout\"><strong>Para reutilizar un resultado</strong><p>Crea una transformación versionada y auditable. El resultado nunca se vincula directamente como entrada.</p></div></section>';
  }
  return '<section class=\"alternate-surface panel\"><div><span class=\"source-mark legacy\">L</span><div><h2>Series hidráulicas legacy</h2>' +
    '<p>Visibles mediante adaptador. Todo vínculo nuevo se guarda en el modelo genérico.</p></div></div>' +
    '<table><thead><tr><th>Serie legacy</th><th>Entidad textual</th><th>Adaptación</th><th>Acción</th></tr></thead><tbody>' +
    '<tr><td>Afluentes Alto Maipo</td><td>hydro_system:maipo</td><td><span class=\"status-chip stale\">Pendiente</span></td><td><button class=\"text-button\">Migrar bajo demanda</button></td></tr>' +
    '<tr><td>Caudal mínimo Tramo 4</td><td>reach:4</td><td><span class=\"status-chip vigente\">Adaptada</span></td><td><button class=\"text-button\">Ver vínculo</button></td></tr>' +
    '</tbody></table><div class=\"info-callout\"><strong>Coexistencia controlada</strong><p>No se eliminan tablas legacy ni se reescriben snapshots históricos.</p></div></section>';
}

function scenarioPanel() {
  if (state.scenario === 'browse') return '';
  if (state.scenario === 'link') return linkPanel();
  if (state.scenario === 'bulk') return bulkPanel();
  if (state.scenario === 'replace') return replacePanel();
  if (state.scenario === 'specific') return specificPanel();
  return sharedPanel();
}

function linkPanel() {
  const fromObject = state.entry === 'object';
  return '<section class=\"flow-panel panel\"><div class=\"flow-heading\"><div><span class=\"eyebrow\">Selector compatible · iniciado desde ' +
    (fromObject ? 'objeto' : 'catálogo') + '</span><h2>Vincular ' + (fromObject ? 'una fuente a Carga Centro' : selectedSignal().name + ' a un objeto') +
    '</h2></div><button class=\"icon-button\" data-scenario=\"browse\">×</button></div>' +
    '<div class=\"compatibility-path\"><article class=\"chosen\"><span>1</span><small>' + (fromObject ? 'Objeto' : 'Fuente') + '</small><strong>' +
    (fromObject ? 'Carga Centro' : selectedSignal().name) + '</strong></article><i>→</i><article><span>2</span><small>Rol funcional</small><strong>Demanda de carga</strong></article>' +
    '<i>→</i><article><span>3</span><small>' + (fromObject ? 'Fuente' : 'Objeto') + '</small><strong>' + (fromObject ? '3 compatibles' : '2 compatibles') + '</strong></article></div>' +
    '<div class=\"candidate-list\"><label class=\"candidate selected\"><input type=\"radio\" checked name=\"candidate\" /><span class=\"candidate-mark\">✓</span><div><strong>' +
    (fromObject ? 'Demanda horaria · Centro' : 'Carga Centro') + '</strong><p>Tipo, rol, objeto, unidad y alcance compatibles</p></div><span class=\"status-chip vigente\">Compatible</span></label>' +
    '<label class=\"candidate disabled\"><input type=\"radio\" disabled name=\"candidate\" /><span class=\"candidate-mark\">×</span><div><strong>' +
    (fromObject ? 'Precio spot · SEN' : 'Batería BESS-01') + '</strong><p>TS_COMPAT_OBJECT_TYPE_NOT_ALLOWED</p></div><span class=\"status-chip incompatible\">No compatible</span></label></div>' +
    '<div class=\"flow-footer\"><p>El backend volverá a validar el contrato dentro de la transacción.</p><div><button class=\"secondary-button\">Cancelar</button><button class=\"primary-button\" data-command=\"saved\">Previsualizar vínculo</button></div></div></section>';
}

function bulkPanel() {
  return '<section class=\"flow-panel panel\"><div class=\"flow-heading\"><div><span class=\"eyebrow\">Prevalidación masiva</span><h2>3 vínculos · guardado atómico</h2></div>' +
    '<button class=\"icon-button\" data-scenario=\"browse\">×</button></div><div class=\"bulk-summary\"><article><span>3</span><small>filas evaluadas</small></article>' +
    '<article class=\"success\"><span>2</span><small>compatibles</small></article><article class=\"danger\"><span>1</span><small>bloqueada</small></article></div>' +
    '<table class=\"preview-table\"><thead><tr><th>Fuente</th><th>Objeto / rol</th><th>Resultado</th></tr></thead><tbody>' +
    '<tr><td>Demanda horaria · Centro</td><td>Carga Centro · load_demand</td><td><span class=\"status-chip vigente\">Lista</span></td></tr>' +
    '<tr><td>Afluente natural · Maipo</td><td>Nodo Las Vertientes · natural_inflow</td><td><span class=\"status-chip vigente\">Lista</span></td></tr>' +
    '<tr><td>Precio spot · SEN</td><td>Carga Centro · load_demand</td><td><span class=\"status-chip incompatible\">Tipo no permitido</span><small class=\"error-code\">TS_COMPAT_SEMANTIC_TYPE_NOT_ALLOWED</small></td></tr>' +
    '</tbody></table><div class=\"atomic-callout\"><span>!</span><div><strong>Nada se guardará todavía</strong><p>Corrige la fila incompatible y vuelve a prevalidar. No hay éxitos parciales.</p></div></div>' +
    '<div class=\"flow-footer\"><p>Token de validación válido por 5 minutos · contrato v18</p><div><button class=\"secondary-button\">Descargar errores</button><button class=\"primary-button\" disabled>Guardar 3 vínculos</button></div></div></section>';
}

function replacePanel() {
  return '<section class=\"flow-panel panel\"><div class=\"flow-heading\"><div><span class=\"eyebrow\">Reemplazo de binding</span><h2>Compara antes de confirmar</h2></div>' +
    '<button class=\"icon-button\" data-scenario=\"browse\">×</button></div><div class=\"compare-grid\"><article><span class=\"compare-label\">Binding actual</span><h3>Demanda base · r11</h3>' +
    '<dl><div><dt>Hash</dt><dd>04ea…198b</dd></div><div><dt>Cobertura</dt><dd>24–31 ago</dd></div><div><dt>Resolución</dt><dd>1 hora</dd></div><div><dt>Estado</dt><dd><span class=\"status-chip stale\">Stale</span></dd></div></dl></article>' +
    '<div class=\"replace-arrow\">→</div><article class=\"new\"><span class=\"compare-label\">Nueva selección</span><h3>Demanda horaria · Centro · r12</h3>' +
    '<dl><div><dt>Hash</dt><dd>91ab…c84f</dd></div><div><dt>Cobertura</dt><dd>31 ago–7 sep</dd></div><div><dt>Resolución</dt><dd>1 hora</dd></div><div><dt>Estado</dt><dd><span class=\"status-chip vigente\">Vigente</span></dd></div></dl></article></div>' +
    '<label class=\"reason-field\"><span>Motivo del reemplazo</span><textarea>Actualizar horizonte operativo de la variante base</textarea></label>' +
    '<div class=\"info-callout\"><strong>La historia no se pierde</strong><p>El binding anterior quedará superseded con actor, motivo y revisión exacta. Los snapshots existentes no cambian.</p></div>' +
    '<div class=\"flow-footer\"><p>Variante Caso Base · rol load_demand</p><div><button class=\"secondary-button\">Cancelar</button><button class=\"primary-button\" data-command=\"saved\">Confirmar reemplazo</button></div></div></section>';
}

function specificPanel() {
  return '<section class=\"flow-panel panel specific-flow\"><div class=\"flow-heading\"><div><span class=\"eyebrow\">Objeto → definición → primera carga</span><h2>Nueva serie específica de Carga Centro</h2></div>' +
    '<button class=\"icon-button\" data-scenario=\"browse\">×</button></div><div class=\"ownership-lock\"><span>◇</span><div><strong>Propietario inmutable: Carga Centro</strong>' +
    '<p>Proyecto Complejo Los Cipreses · no se puede reasignar ni aparece en el catálogo global.</p></div><span class=\"scope-badge proyecto\">Específica</span></div>' +
    '<div class=\"specific-grid\"><section><h3>1 · Definición local</h3><label><span>Nombre</span><input value=\"Demanda ajustada · Carga Centro\" /></label>' +
    '<label><span>Clave local</span><input value=\"load_adjusted\" /></label><div class=\"field-pair\"><label><span>Tipo semántico</span><select><option>Demanda</option></select></label>' +
    '<label><span>Unidad canónica</span><input value=\"MW\" disabled /></label></div><p class=\"validation-note\">✓ Contrato compatible con load_demand</p></section>' +
    '<section><h3>2 · Primera carga</h3><div class=\"channel-switch\"><button class=\"active\">Archivo</button><button>API</button></div><div class=\"dropzone\"><span>⇧</span><strong>demanda_ajustada.xlsx</strong>' +
    '<small>Hoja Datos · 168 filas · SHA-256 calculado</small><button class=\"text-button\">Cambiar archivo</button></div><p class=\"api-hint\">API: POST /objects/components/carga-centro/time-series</p></section></div>' +
    '<section class=\"upload-preview\"><div><h3>3 · Preview normalizado</h3><span class=\"status-chip vigente\">Validación completa · 0 errores</span></div>' +
    '<table><thead><tr><th>Timestamp</th><th>Duración</th><th>Valor MW</th><th>Calidad</th></tr></thead><tbody><tr><td>2026-08-31 00:00 -04:00</td><td>1 h</td><td>48,2</td><td>ok</td></tr>' +
    '<tr><td>2026-08-31 01:00 -04:00</td><td>1 h</td><td>46,9</td><td>ok</td></tr><tr><td>… 166 filas validadas</td><td>—</td><td>—</td><td>—</td></tr></tbody></table></section>' +
    '<div class=\"flow-footer\"><p>Publicará la revisión 1 sellada · fuente XLSX · hash de contenido pendiente</p><div><button class=\"secondary-button\">Guardar definición sin datos</button><button class=\"primary-button\" data-command=\"saved\">Crear y publicar primera revisión</button></div></div></section>';
}

function sharedPanel() {
  return '<section class=\"flow-panel panel shared-flow\"><div class=\"flow-heading\"><div><span class=\"eyebrow\">Actualización de fuente genérica compartida</span><h2>Afluente natural · Maipo</h2></div>' +
    '<button class=\"icon-button\" data-scenario=\"browse\">×</button></div><div class=\"shared-warning\"><span>!</span><div><strong>Esta acción no afecta solo a Nodo Las Vertientes</strong>' +
    '<p>Publicar una nueva revisión cambia la fuente común y deja stale los bindings que observan r28.</p></div></div>' +
    '<div class=\"impact-grid\"><article><span>14</span><small>objetos asociados</small></article><article><span>13</span><small>otros objetos</small></article>' +
    '<article><span>9</span><small>bindings quedarán stale</small></article><article><span>4</span><small>proyectos afectados</small></article></div>' +
    '<section class=\"consumers\"><div class=\"panel-title\"><h3>Consumidores afectados</h3><span>3 de 13 mostrados</span></div>' +
    relationRow('Nodo Las Vertientes', 'Proyecto Los Cipreses', 'Binding actual · Caso Base', 'warn') + relationRow('Nodo San Alfonso', 'Proyecto Maipo Alto', 'Binding fijado · Caso Sequía', 'warn') +
    relationRow('Sistema hidráulico Maipo', 'Proyecto Planificación', 'Asociación sin binding', 'quiet') + '</section>' +
    '<div class=\"decision-cards\"><article class=\"recommended\"><span>Recomendado para un cambio local</span><h3>Crear específica para este objeto</h3>' +
    '<p>Copia solo esta señal desde r28, conserva linaje y permite cambiar valores sin tocar a los otros consumidores.</p><button class=\"primary-button\" data-command=\"derive\">Derivar serie específica</button></article>' +
    '<article><span>Requiere permiso admin</span><h3>Publicar para todos</h3><p>El archivo debe cubrir todas las señales activas del set. Requiere motivo y confirmación explícita.</p>' +
    '<label class=\"confirm-check\"><input type=\"checkbox\" /> Comprendo que 9 bindings quedarán stale</label><button class=\"danger-button\" data-command=\"shared-confirm\">Continuar con publicación global</button></article></div></section>';
}

function renderVariantA() {
  const heading = pageHeading('Catálogo global de series', 'Busca señales reutilizables, inspecciona su procedencia y vincúlalas con el mismo contrato que valida el backend.',
    entryToggle() + '<button class=\"primary-button\" data-scenario=\"bulk\">Prevalidar selección (' + state.selected.size + ')</button>');
  let body = '';
  if (state.surface === 'inputs') {
    body = '<div class=\"catalog-layout\">' + catalogFilters() + '<section class=\"catalog-center panel\"><div class=\"catalog-toolbar\"><span>38 señales autorizadas</span>' +
      '<div><button class=\"secondary-button\" data-scenario=\"specific\">Nueva específica desde objeto</button><button class=\"icon-button\">↕</button></div></div>' +
      catalogTable(false) + '</section>' + signalInspector() + '</div>';
  } else {
    body = alternateSurface();
  }
  return shell('<main class=\"a-main\">' + heading + sourceTabs() + statusFrame(body) + scenarioPanel() + '</main>', 'Catálogo global');
}

function objectTree() {
  return '<aside class=\"object-tree\"><div class=\"tree-heading\"><span>Objetos del proyecto</span><button>＋</button></div><label class=\"tree-search\"><span>⌕</span><input placeholder=\"Buscar objeto\" /></label>' +
    '<ul><li><button><span>▾</span><strong>Componentes</strong><small>5</small></button><ul><li class=\"active\"><button><span class=\"object-icon\">◇</span><div><strong>Carga Centro</strong><small>component:load</small></div><i>2/3</i></button></li>' +
    '<li><button><span class=\"object-icon\">◇</span><div><strong>Solar Norte</strong><small>component:renewable</small></div><i>1/1</i></button></li><li><button><span class=\"object-icon\">◇</span><div><strong>BESS-01</strong><small>component:battery</small></div><i>0/0</i></button></li></ul></li>' +
    '<li><button><span>▸</span><strong>Hidráulica</strong><small>12</small></button></li><li><button><span>▸</span><strong>Sistema global</strong><small>1</small></button></li></ul></aside>';
}

function roleSlots() {
  return '<section class=\"role-slots\"><div class=\"object-heading\"><div><span class=\"object-icon large\">◇</span><div><span class=\"eyebrow\">Component · Load</span><h1>Carga Centro</h1><p>Proyecto Complejo Los Cipreses · Región centro</p></div></div>' +
    '<div><button class=\"secondary-button\" data-scenario=\"specific\">＋ Serie específica</button><button class=\"icon-button\">•••</button></div></div>' +
    '<div class=\"slot-summary\"><span><strong>2</strong> configurados</span><span><strong>1</strong> pendiente</span><span><strong>1</strong> stale</span></div>' +
    '<article class=\"slot selected\"><header><span class=\"slot-status ok\">✓</span><div><strong>Demanda de carga</strong><small>load_demand · obligatorio</small></div><button>•••</button></header>' +
      '<div class=\"bound-source\"><span class=\"source-type generic\">G</span><div><strong>Demanda horaria · Centro</strong><small>Genérica · r12 · 91ab…c84f</small></div><span class=\"status-chip vigente\">Actual</span></div>' +
      '<footer><span>Asociada al objeto</span><span>Binding en Caso Base</span><button data-scenario=\"replace\">Reemplazar</button></footer></article>' +
    '<article class=\"slot\"><header><span class=\"slot-status warn\">!</span><div><strong>Demanda contingencia</strong><small>load_demand · Variante Sequía</small></div><button>•••</button></header>' +
      '<div class=\"bound-source\"><span class=\"source-type specific\">E</span><div><strong>Demanda ajustada · Carga Centro</strong><small>Específica · r3 · pertenece a este objeto</small></div><span class=\"status-chip stale\">Stale</span></div>' +
      '<footer><span>Solo visible aquí</span><span>Ejecución bloqueada</span><button data-status=\"stale\">Resolver</button></footer></article>' +
    '<article class=\"slot empty-slot\"><header><span class=\"slot-status empty\">3</span><div><strong>Perfil de respaldo</strong><small>load_demand · opcional</small></div></header>' +
      '<p>Sin fuente asociada. Selecciona una genérica compatible o crea una específica para Carga Centro.</p><div><button class=\"primary-button\" data-scenario=\"link\">Buscar compatible</button><button class=\"secondary-button\" data-scenario=\"specific\">Crear específica</button></div></article></section>';
}

function candidateWorkbench() {
  return '<aside class=\"candidate-workbench\"><div class=\"workbench-heading\"><div><span class=\"eyebrow\">Candidatos compatibles</span><h2>Demanda de carga</h2></div><span>3</span></div>' +
    '<div class=\"candidate-filters\"><button class=\"active\">Todas</button><button>Genéricas</button><button>Específicas</button></div>' +
    '<label class=\"tree-search\"><span>⌕</span><input placeholder=\"Buscar entre compatibles\" /></label>' +
    '<div class=\"workbench-list\"><button class=\"candidate-card selected\" data-signal=\"demanda-centro\"><div><span class=\"source-type generic\">G</span><span class=\"scope-badge proyecto\">Proyecto</span></div><strong>Demanda horaria · Centro</strong>' +
      '<p>Pronóstico · MW · 1 hora</p><small>r12 · validada · 31 ago–7 sep</small><i>✓ Compatible</i></button>' +
    '<button class=\"candidate-card\"><div><span class=\"source-type generic\">G</span><span class=\"scope-badge global\">Global</span></div><strong>Demanda oficial · SEN</strong><p>Real · MW · 1 hora</p><small>r20 · validada · 1–30 ago</small><i>✓ Compatible</i></button>' +
    '<button class=\"candidate-card\"><div><span class=\"source-type specific\">E</span><span class=\"scope-badge proyecto\">Solo este objeto</span></div><strong>Demanda ajustada</strong><p>Pronóstico · MW · 1 hora</p><small>r3 · stale · 24–31 ago</small><i class=\"warn\">! Requiere resolver</i></button></div>' +
    '<div class=\"workbench-detail\"><span class=\"eyebrow\">Por qué es compatible</span><ul><li>Tipo demand → rol load_demand</li><li>Objeto component:load permitido</li><li>Unidad canónica MW exacta</li><li>Alcance accesible en este proyecto</li></ul>' +
    '<button class=\"primary-button\" data-scenario=\"link\">Usar esta fuente</button><button class=\"text-button\" data-status=\"incompatible\">Ver ejemplo incompatible</button></div></aside>';
}

function renderVariantB() {
  const contextual = state.entry === 'catalog'
    ? '<div class=\"context-trail\"><span>Catálogo</span><b>›</b><strong>Demanda horaria · Centro</strong><b>›</b><span>Objetos compatibles</span><button data-entry=\"object\">Cambiar: empezar desde objeto</button></div>'
    : '<div class=\"context-trail\"><span>Objetos</span><b>›</b><strong>Carga Centro</strong><b>›</b><span>Series asociadas</span><button data-entry=\"catalog\">Cambiar: empezar desde catálogo</button></div>';
  const body = '<main class=\"b-main\">' + contextual + '<div class=\"binding-workspace\">' + objectTree() + roleSlots() + candidateWorkbench() + '</div>' + scenarioPanel() + '</main>';
  return shell(statusFrame(body), 'Mesa de vinculación');
}

function wizardRail() {
  const steps = [
    ['1', 'Origen', 'Genérica o específica'],
    ['2', 'Definición', 'Contrato y propietario'],
    ['3', 'Datos', 'Archivo o API'],
    ['4', 'Revisión', 'Impacto y publicación'],
  ];
  return '<aside class=\"wizard-rail\"><div><span class=\"eyebrow\">Asistente de series</span><h1>Carga Centro</h1><p>Configura una fuente sin perder de vista su alcance.</p></div><ol>' +
    steps.map(function (step) {
      const number = Number(step[0]);
      return '<li class=\"' + (state.step === number ? 'active' : state.step > number ? 'done' : '') + '\"><button data-step=\"' + step[0] + '\"><span>' +
        (state.step > number ? '✓' : step[0]) + '</span><div><strong>' + step[1] + '</strong><small>' + step[2] + '</small></div></button></li>';
    }).join('') + '</ol><div class=\"wizard-rule\"><span>Regla permanente</span><p>Una serie específica pertenece para siempre al objeto donde nace.</p></div></aside>';
}

function wizardStage() {
  if (state.scenario === 'shared') return sharedPanel();
  if (state.scenario === 'bulk') return bulkPanel();
  if (state.scenario === 'replace') return replacePanel();
  if (state.step === 1) {
    return '<section class=\"wizard-stage\"><div class=\"wizard-heading\"><span class=\"eyebrow\">Paso 1 de 4 · Origen</span><h2>¿Cómo quieres cubrir Demanda de carga?</h2><p>Ambos caminos cumplen el mismo rol, pero tienen distinto alcance y ciclo de vida.</p></div>' +
      '<div class=\"origin-choice\"><article><span class=\"source-type generic large\">G</span><h3>Usar una serie genérica</h3><p>Reutiliza una fuente autorizada del catálogo. Puede tener otros objetos y proyectos consumidores.</p>' +
      '<ul><li>Se descubre y mantiene en el catálogo</li><li>Puede ser project o global</li><li>Actualizar exige revisar impacto compartido</li></ul><button class=\"primary-button\" data-scenario=\"link\">Buscar 3 compatibles</button></article>' +
      '<article class=\"recommended\"><span class=\"recommend-label\">Recomendado para ajustes locales</span><span class=\"source-type specific large\">E</span><h3>Crear una serie específica</h3><p>Nace desde Carga Centro y no necesita una entrada genérica como antecedente.</p>' +
      '<ul><li>Solo se descubre desde este objeto</li><li>No se puede reasignar</li><li>Archivo y API comparten validación</li></ul><button class=\"primary-button\" data-step=\"2\">Definir específica</button></article></div>' +
      '<div class=\"wizard-note\"><strong>¿Ya existe una serie asociada?</strong><button data-scenario=\"shared\">Actualizar valores con impacto visible</button></div></section>';
  }
  if (state.step === 2) {
    return '<section class=\"wizard-stage\"><div class=\"wizard-heading\"><span class=\"eyebrow\">Paso 2 de 4 · Definición</span><h2>Define la serie específica</h2><p>La definición puede guardarse sin valores. El propietario queda fijado al crearla.</p></div>' +
      '<div class=\"ownership-lock\"><span>◇</span><div><strong>Propietario inmutable: Carga Centro</strong><p>component:load · Complejo Los Cipreses</p></div><span class=\"scope-badge proyecto\">No catalogable</span></div>' +
      '<div class=\"form-grid\"><label><span>Nombre visible</span><input value=\"Demanda ajustada · Carga Centro\" /></label><label><span>Clave local</span><input value=\"load_adjusted\" /></label>' +
      '<label><span>Rol que cubre</span><select><option>Demanda de carga</option></select></label><label><span>Tipo semántico</span><select><option>Demanda</option></select></label>' +
      '<label><span>Clase de datos</span><select><option>Pronóstico</option></select></label><label><span>Unidad canónica</span><input value=\"MW\" disabled /></label></div>' +
      '<div class=\"validation-strip\"><span>✓</span><div><strong>Contrato válido</strong><p>Demand + load_demand + component:load + MW está autorizado por la regla v18.</p></div></div>' +
      wizardFooter('Volver', 'Guardar y elegir datos', 1, 3) + '</section>';
  }
  if (state.step === 3) {
    return '<section class=\"wizard-stage\"><div class=\"wizard-heading\"><span class=\"eyebrow\">Paso 3 de 4 · Datos</span><h2>Carga la primera revisión</h2><p>Archivo y API terminan en la misma fotografía completa, inmutable y validada.</p></div>' +
      '<div class=\"channel-switch large\"><button class=\"active\">Archivo CSV / XLSX</button><button>Payload API</button></div>' +
      '<div class=\"dropzone large\"><span>⇧</span><strong>demanda_ajustada.xlsx</strong><small>412 KiB · Hoja “Demanda” · checksum 314a…9f00</small><button class=\"text-button\">Elegir otro archivo</button></div>' +
      '<div class=\"mapping-card\"><div><h3>Mapeo detectado</h3><span class=\"status-chip vigente\">Listo</span></div><div><span>timestamp</span><b>→</b><strong>timestamp_start</strong></div><div><span>value_mw</span><b>→</b><strong>load_adjusted.value</strong></div><div><span>quality</span><b>→</b><strong>quality_flag</strong></div></div>' +
      '<div class=\"validation-strip\"><span>✓</span><div><strong>168 de 168 filas válidas</strong><p>Zona America/Santiago · 1 hora · sin duplicados, huecos ni valores no finitos.</p></div><button class=\"text-button\">Ver preview</button></div>' +
      wizardFooter('Volver a definición', 'Revisar publicación', 2, 4) + '</section>';
  }
  return '<section class=\"wizard-stage\"><div class=\"wizard-heading\"><span class=\"eyebrow\">Paso 4 de 4 · Revisión</span><h2>Crear y publicar la revisión 1</h2><p>Esta operación no modifica fuentes genéricas ni otros objetos.</p></div>' +
    '<div class=\"review-card\"><header><span class=\"source-type specific large\">E</span><div><h3>Demanda ajustada · Carga Centro</h3><p>Específica · Pronóstico · MW</p></div><span class=\"status-chip vigente\">Lista para publicar</span></header>' +
    '<dl><div><dt>Propietario</dt><dd>Carga Centro · inmutable</dd></div><div><dt>Fuente</dt><dd>XLSX · 314a…9f00</dd></div><div><dt>Cobertura</dt><dd>31 ago — 7 sep 2026</dd></div><div><dt>Validación</dt><dd>168 filas · 0 errores</dd></div><div><dt>Visibilidad</dt><dd>Solo desde Carga Centro</dd></div><div><dt>Catálogo global</dt><dd>No aparecerá</dd></div></dl></div>' +
    '<div class=\"info-callout\"><strong>Después de publicar</strong><p>La revisión queda sellada con hash. Podrás prevalidar el binding por separado; una publicación nunca mueve bindings en silencio.</p></div>' +
    '<div class=\"wizard-actions\"><button class=\"secondary-button\" data-step=\"3\">Volver a datos</button><button class=\"primary-button\" data-command=\"saved\">Crear serie y publicar r1</button></div></section>';
}

function wizardFooter(backLabel, nextLabel, backStep, nextStep) {
  return '<div class=\"wizard-actions\"><button class=\"secondary-button\" data-step=\"' + backStep + '\">' + backLabel + '</button><button class=\"primary-button\" data-step=\"' + nextStep + '\">' + nextLabel + '</button></div>';
}

function renderVariantC() {
  const body = '<main class=\"c-main\"><div class=\"c-context\"><span>Objetos</span><b>›</b><span>Carga Centro</span><b>›</b><strong>Nueva serie</strong>' +
    '<button data-entry=\"catalog\">Abrir catálogo completo</button></div><div class=\"wizard-layout\">' + wizardRail() + wizardStage() + '</div></main>';
  return shell(statusFrame(body), 'Asistente contextual');
}

function stateLab() {
  return '<div class=\"lab-heading\"><strong>LABORATORIO</strong><button data-command=\"toggle-lab\">−</button></div><div class=\"lab-body\">' +
    '<span>Punto de entrada</span><div class=\"lab-buttons\"><button data-entry=\"catalog\" class=\"' + (state.entry === 'catalog' ? 'active' : '') + '\">Catálogo</button>' +
    '<button data-entry=\"object\" class=\"' + (state.entry === 'object' ? 'active' : '') + '\">Objeto</button></div><span>Escenario</span><select data-lab-scenario>' +
    Object.keys(scenarioNames).map(function (key) { return '<option value=\"' + key + '\" ' + (state.scenario === key ? 'selected' : '') + '>' + scenarioNames[key] + '</option>'; }).join('') +
    '</select><span>Estado de pantalla</span><select data-lab-status>' +
    Object.keys(statusNames).map(function (key) { return '<option value=\"' + key + '\" ' + (state.status === key ? 'selected' : '') + '>' + statusNames[key] + '</option>'; }).join('') +
    '</select></div>';
}

function switcher() {
  const keys = Object.keys(variants);
  const current = variants[state.variant];
  return '<button data-cycle=\"-1\" aria-label=\"Variante anterior\">←</button><div><span>Variante ' + state.variant + ' de ' + keys.length +
    '</span><strong>' + current.name + '</strong><small>' + current.thesis + '</small></div><button data-cycle=\"1\" aria-label=\"Variante siguiente\">→</button>';
}

function toastMarkup() {
  if (!state.toast) return '';
  return '<div class=\"toast\"><span>✓</span><div><strong>Simulación completada</strong><p>' + state.toast + '</p></div><button data-command=\"dismiss-toast\">×</button></div>';
}

function render() {
  const renderers = { A: renderVariantA, B: renderVariantB, C: renderVariantC };
  document.getElementById('prototype-root').innerHTML = renderers[state.variant]();
  document.getElementById('state-lab').innerHTML = stateLab();
  document.getElementById('variant-switcher').innerHTML = switcher();
  updateUrl();
}

function cycleVariant(direction) {
  const keys = Object.keys(variants);
  const index = keys.indexOf(state.variant);
  state.variant = keys[(index + direction + keys.length) % keys.length];
  state.toast = '';
  render();
}

document.addEventListener('click', function (event) {
  const cycle = event.target.closest('[data-cycle]');
  if (cycle) return cycleVariant(Number(cycle.dataset.cycle));
  const variant = event.target.closest('[data-variant]');
  if (variant) { state.variant = variant.dataset.variant; return render(); }
  const surface = event.target.closest('[data-surface]');
  if (surface) { state.surface = surface.dataset.surface; state.scenario = 'browse'; return render(); }
  const entry = event.target.closest('[data-entry]');
  if (entry) { state.entry = entry.dataset.entry; if (state.variant === 'C' && state.entry === 'object') state.step = 1; return render(); }
  const scenario = event.target.closest('[data-scenario]');
  if (scenario) { state.scenario = scenario.dataset.scenario; if (state.scenario === 'specific' && state.variant === 'C') state.step = 2; return render(); }
  const status = event.target.closest('[data-status]');
  if (status) { state.status = status.dataset.status; return render(); }
  const step = event.target.closest('[data-step]');
  if (step) { state.step = Number(step.dataset.step); state.scenario = 'specific'; return render(); }
  const check = event.target.closest('[data-check-signal]');
  if (check) {
    event.stopPropagation();
    if (check.checked) state.selected.add(check.dataset.checkSignal);
    else state.selected.delete(check.dataset.checkSignal);
    return render();
  }
  const signal = event.target.closest('[data-signal]');
  if (signal) { state.signal = signal.dataset.signal; return render(); }
  const command = event.target.closest('[data-command]');
  if (!command) return;
  if (command.dataset.command === 'reset-status') state.status = 'normal';
  if (command.dataset.command === 'dismiss-toast') state.toast = '';
  if (command.dataset.command === 'saved') state.toast = 'Se registraría una nueva fila de historia; en este prototipo no se persiste nada.';
  if (command.dataset.command === 'derive') {
    state.scenario = 'specific';
    state.step = 2;
    state.toast = 'La derivación fijaría la revisión y el hash fuente antes de crear la identidad local.';
  }
  if (command.dataset.command === 'shared-confirm') state.toast = 'La publicación aún exigiría motivo, ETag, token e idempotencia antes de afectar a todos.';
  if (command.dataset.command === 'toggle-lab') document.getElementById('state-lab').classList.toggle('collapsed');
  render();
});

document.addEventListener('change', function (event) {
  if (event.target.matches('[data-lab-scenario]')) { state.scenario = event.target.value; if (state.scenario === 'specific' && state.variant === 'C') state.step = 2; render(); }
  if (event.target.matches('[data-lab-status]')) { state.status = event.target.value; render(); }
});

document.addEventListener('keydown', function (event) {
  const target = event.target;
  if (target.matches('input, textarea, select, [contenteditable]')) return;
  if (event.key === 'ArrowLeft') cycleVariant(-1);
  if (event.key === 'ArrowRight') cycleVariant(1);
});

render();
