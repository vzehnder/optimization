---
id: 01
title: "Inventario de la superficie configurable existente"
map: capa-de-configuracion
label: wayfinder:research
status: closed
assignee: vzehnder
blocked_by: []
---

## Question

¿Que decide hoy, hardcodeado, lo que ve un usuario no-analista — y cual de esas
decisiones deberia pasar a ser configuracion?

El charting ya confirmo que `dashboard_templates` es un cascaron fijo de 9
booleanos, pero eso es solo una parte. Falta el inventario completo de los
puntos donde el codigo decide por el ingeniero.

Producir una lista, con referencia a archivo y linea, de:

- Cada flag, constante o condicional que gobierna que secciones, tablas,
  graficos o descargas ve un `client` (rutas `/client`, renderer de
  publicaciones, allowlist de artefactos).
- Cada etiqueta visible en el UI que hoy esta fija en el codigo y que un
  ingeniero podria querer renombrar para su usuario final.
- Cada validacion o limite (por ejemplo `table_preview_limit`) que hoy tiene un
  valor por defecto no configurable.
- Que ya es configurable pero no esta expuesto en la UI.
- Las senales canonicas y de donde sale la lista de "senales requeridas" de un
  caso, dado que la tabla editable del operador se apoyara en ella.

El resultado alimenta directamente el modelo de datos de la configuracion: sin
este inventario, ese modelo se disena a ciegas sobre su propia superficie.

**Nota de ejecucion**: este ticket es AFK y se resuelve leyendo el repositorio.
Puede resolverse con un subagente de exploracion si el dev que conduce el mapa
lo autoriza.

## Resolucion

Inventario levantado leyendo el repositorio en la rama `series_tiempo`
(2026-08-01). Todas las referencias fueron verificadas archivo por archivo.

**Titular**: la superficie que hoy ve un no-analista esta gobernada por
**tres** mecanismos, no uno. `dashboard_templates` (9 booleanos) es el unico
que el ingeniero controla. Los otros dos —el **sobre de la publicacion**, que
no filtra nada, y el **catalogo de graficos y etiquetas**, que vive entero en
codigo— son invisibles hoy y son el grueso del trabajo.

### A. Que decide hoy que ve un `client`

**A.1 — La frontera de permisos es binaria y por prefijo de ruta.**
`require_authenticated_app_boundary` (`app/main.py:620-672`) enruta por
prefijo: `/api/client*` y `/client*` exigen `require_client`; **todo lo demas**
cae en `require_internal`. No hay capa de capacidades: `app/auth.py:11-12`
define `VALID_USER_ROLES = {admin, analyst, client}` e
`INTERNAL_USER_ROLES = {admin, analyst}`, y ese es todo el vocabulario. Notar
que `/react*` (`app/main.py:636-638`) **no** pasa por el gate: el shell del SPA
se sirve a cualquiera y el control real es del API mas el gating de cliente.

**A.2 — El acceso del cliente es por proyecto y nada mas fino.**
`require_client_project_access` (`app/auth.py:37-40`) exige fila en
`project_client_access` con `users.role = 'client'` e `is_active = 1`
(`app/persistence.py:1784-1793`). El literal `'client'` esta en el SQL, no solo
en Python.

**A.3 — El React repite la binariedad ruta por ruta.**
`frontend/src/App.tsx:265-371`: cada una de las ~16 rutas es
`isClient ? <ForbiddenView/> : <X/>`. El aterrizaje esta fijo en tres lugares
independientes: `landingRoute` (`App.tsx:66-68`),
`authenticated_landing_path` (`app/main.py:581-587`) y
`react_authenticated_landing_path` (`app/main.py:589-595`).

**A.4 — Los 9 booleanos + el limite de filas.**
`DASHBOARD_TEMPLATE_FLAGS` (`app/persistence.py:65-75`) y
`DEFAULT_TABLE_PREVIEW_LIMIT = 10` (`app/persistence.py:77`); contrato HTTP en
`DashboardTemplateWriteRequest` (`app/main.py:141-152`).

**A.5 — El mapeo flag -> grafico esta en codigo.**
`TEMPLATE_CHART_GROUPS` (`app/results.py:9-16`) liga 6 flags a 10 claves de
grafico. Los otros 3 flags (`show_summary`, `show_system_dispatch_table`,
`show_asset_dispatch_table`) se resuelven aparte en `apply_dashboard_template`
(`app/results.py:88-113`).

**A.6 — Hueco real en el cascaron actual: `all_series` se cuela.**
`app/results.py:99-100` inyecta el grafico `all_series` **siempre que haya al
menos un grafico habilitado**, sin flag que lo gobierne. `all_series`
(`app/results.py:197-234`) grafica *toda* columna numerica de `dispatch.csv`.
Es decir: hoy el ingeniero cree que apago todo menos "precio" y el cliente ve
igual la serie completa del despacho. Cualquier configuracion nueva debe
cerrar esto explicitamente.

**A.7 — El sobre de la publicacion no se filtra.**
`client_publication_payload` (`app/main.py:751-795`) aplica la plantilla **solo
a `results`**. Devuelve crudos `project`, `scenario`, `scenario_version`,
`run`, `publication` y `template`. En concreto cruzan la frontera al cliente:

- `run` = fila completa de `get_run` (`app/persistence.py:6007-6032`):
  `workspace_path`, `input_snapshot_path`, `output_dir`, `summary_path`,
  `stdout_log_path`, `stderr_log_path`, `stdout`, `stderr`, `error_message`,
  `triggered_by`, `exit_code`.
- `scenario` (`app/persistence.py:2224-2235`): `name`, `description`,
  `created_by` internos.
- `scenario_version` (`app/persistence.py:5439-5462`): `case_name`,
  `schema_version`, `generation_metadata_json`.
- `project` via `list_client_projects` (`app/persistence.py:1768-1782`):
  `created_by`.

El portal React renderiza poco de eso, pero el payload lo lleva. El destino del
mapa dice que el usuario final "nunca ve draft, catalogo, variantes, bindings
ni versiones inmutables" — hoy eso se cumple por lo que el React elige pintar,
no por contrato. Esto genero un ticket nuevo (ver mas abajo).

**A.8 — Las descargas: allowlist por publicacion, no por configuracion.**
`publication_download_artifacts` (`app/main.py:714-732`) y
`get_client_publication_download` (`app/main.py:734-749`) filtran contra
`publication.allowed_artifact_types` (columna JSON,
`app/persistence.py:974`), resuelta por
`_resolve_publication_artifact_types` (`app/persistence.py:9719-9735`) desde
`DEFAULT_PUBLICATION_ARTIFACT_TYPES` (`app/persistence.py:79-83`) intersectada
con los artefactos registrados. Se valida ademas ruta bajo el root y existencia
del archivo.

**A.9 — El unico interruptor de visibilidad restante es `status`.**
Solo publicaciones con `status == 'published'` son visibles
(`app/auth.py:50-52`, `app/main.py:736`, `app/main.py:757`).

### B. Etiquetas visibles fijas en codigo

Todas son candidatas a parametrizacion; hoy ninguna es renombrable.

**B.1 — Shell global, que el cliente tambien ve** (`frontend/src/App.tsx`):
marca `"Z"` + `"BESS Workspace"` (229-233), badge que imprime el rol crudo
(237), `"Salir"` (245), link `"Cliente"` (258).

**B.2 — Portal cliente** (`frontend/src/ClientPortal.tsx`): `"Portal cliente"`
(226, 272, 327), `"Proyectos asignados"` (229), `"Publicaciones"` (285),
eyebrows `"Cliente"` / `"Proyecto"` / `"Publicacion"` (225, 277, 336), vacios
`"No hay proyectos asignados."` (103), `"No hay publicaciones activas."` (123),
`"Sin descripcion."` (110, 279), `"Sin notas."` (134, 338),
`"No hay downloads habilitados."` (194), errores `"No encontrado"` /
`"El recurso solicitado no existe."` / `"Volver al portal"` (80-84),
`"No se pudo cargar"` (90), cargas `"Cargando portal cliente"` (211),
`"Cargando publicaciones"` (258), `"Cargando publicacion"` (313).

**B.3 — Vocabulario interno filtrado en ingles al cliente**, en el bloque
`PublicationMetadata` (`ClientPortal.tsx:142-166`): titulo `"Publication"`, y
las etiquetas `"Template"`, `"Published at"`, `"Run Status"`,
`"Scenario Version"`. Mas `"Downloads"` (178). Este bloque es el ejemplo mas
claro del problema que motiva el mapa.

**B.4 — Resultados, compartidos analista/cliente** (`frontend/src/RunResults.tsx`,
via `DashboardResultsContent` que el portal reusa): `"Run Results"` (167),
`"Result Charts"` (440), `"Unavailable charts"` (452),
`"System Dispatch"` / `"Asset Dispatch"` (512, 518), `"Dashboard"` +
`"No hay secciones habilitadas para esta publicacion."` (496-499),
`"Results Error"` / `"No se pudieron cargar resultados"` (477-479),
`"Summary vacio."` (178), `"Mostrando N de M filas."` (285),
`"No hay series disponibles para graficar."` (448). Encabezados de las tablas
de KPI anidados: `"kpi"`, `"value"`, `"asset_id"` (226-228, 249-251).

**B.5 — Los KPIs del summary se etiquetan con un diccionario de 8 claves.**
`summaryLabel` (`RunResults.tsx:187-199`) traduce `case_name`, `run_timestamp`,
`solver_name`, `solver_status`, `termination_status`, `objective_value_usd`,
`model_version`, `schema_version`; **cualquier otra clave se imprime cruda**.
Un `summary.json` real (`.tmp/artifacts/runs/1/.../summary.json`) trae ademas
`price_mode` y `source_identifiers`, y este ultimo contiene la **ruta absoluta
del `system_case.json` en el disco del servidor**, que hoy se renderiza tal
cual si `show_summary` esta encendido.

**B.6 — Titulos, series y unidades de los graficos viven en el backend.**
`build_chart_data` (`app/results.py:123-194`) fija los 10 graficos con sus
titulos (`"Energy Price"`, `"Grid Import / Export"`,
`"Renewable Used / Curtailed"`, `"BESS Charge / Discharge / SOC"`,
`"Period Profit"`, `"Hydro Power"`, `"Hydro Flows"`, `"Hydro Storage"`,
`"Hydro Reservoir Elevation"`, `"All System Series"`) y las etiquetas por serie
(`"Grid Import MW"`, `"BESS SOC MWh"`, ...). Todo en ingles tecnico.

**B.7 — Los encabezados de tabla son el nombre crudo de la columna del CSV.**
`RunResults.tsx:297-305` pinta `table.columns` sin traducir. Los ejes de Plotly
son `"timestamp"` y la unidad o `"value"` (`RunResults.tsx:373-374`).

### C. Validaciones y limites con default no configurable

- `table_preview_limit`: default `10`, `ge=1`, **sin tope superior**
  (`app/main.py:152`; `app/persistence.py:77`). Es el unico limite de esta lista
  que ya es configurable.
- `DEFAULT_PUBLICATION_ARTIFACT_TYPES` (`app/persistence.py:79-83`).
- Sesion de 12 horas: `session_expires_at(hours=12)` (`app/auth.py:89`).
- **Parser numerico**: `parse_catalog_float` (`app/time_series_catalog.py:400-407`)
  y `validate_catalog_value_edits` (`app/time_series_catalog.py:511-517`) usan
  `float(value)` pelado. Sin locale: `"1.234,5"` levanta error y `"1.234"` se
  lee como mil doscientos treinta y cuatro milesimas. Dato duro para el ticket
  del pegado desde Excel.
- **La edicion manual no puede crecer**: `validate_catalog_value_edits`
  (`app/time_series_catalog.py:489-535`) rechaza todo `period_index` que no
  exista ya en el set y todo `signal_key` que no este ya en el set. Solo
  reemplaza valores. Extender el horizonte o agregar una senal **no es una
  edicion**, es un import o un set nuevo. Dato duro para el ticket de
  fail-closed y para el del contrato de la tabla.
- Reglas por senal: `nonnegative` y unidad canonica, declarativas en
  `TIME_SERIES_SIGNAL_CATALOG`; finitud en ambos parsers.
- `TIME_SERIES_DATA_KINDS`: 7 valores fijos (`app/time_series_catalog.py:12-20`).
  `PROGRAM_METADATA_FIELDS` (438).
- **Sin limite de tamano en la edicion**: `TimeSeriesSetValuesEditRequest.edits`
  es una lista sin cota (`app/main.py:334`). Un ano horario por N senales entra
  en un solo `PUT`. No hay paginacion ni batching en el contrato.
- Layout de Plotly fijo: alto 340, margenes, fondo blanco, leyenda horizontal
  (`RunResults.tsx:364-391`).
- Tabla sufijo -> unidad **duplicada** en dos lugares que pueden divergir:
  `chart_series_unit` (`app/results.py:237-250`) y `unitForColumn`
  (`RunResults.tsx:89-101`); 8 sufijos cada una.
- Capacidades hidraulicas recortadas: `HYDRAULIC_SUPPORTED_ROUTING_METHODS`,
  `..._UNIT_OPERATION_MODES`, `..._UNIT_GENERATION_MODES`
  (`app/persistence.py:102, 107, 109`).
- Retencion: `DEFAULT_RESULT_CLEANUP_TARGETS` e
  `IMMUTABLE_AUDIT_TARGET_REASONS` (`app/result_retention.py:7-18`).

### D. Ya configurable u operable, pero no expuesto en la UI

- **`GET /api/dashboard-templates/{id}/runs/{run_id}/results`**
  (`app/main.py:1183-1201`) aplica una plantilla a **cualquier** corrida. Esta
  en el OpenAPI (`frontend/src/api/schema.ts:368`) y **no tiene wrapper en
  `client.ts`**. Es exactamente "previsualizar la configuracion contra una
  corrida" y esta muerto: la UI solo previsualiza via
  `/api/publications/{id}/preview`, es decir obliga a crear una publicacion
  para ver el efecto de una plantilla.
- `GET /api/dashboard-templates/{id}` (lectura individual): sin wrapper.
- Sin wrapper en `client.ts`: `POST /api/admin/runs/rebuild-results`,
  `POST /api/admin/runs/{id}/rebuild-results`,
  `POST /api/admin/runs/{id}/cleanup-results`,
  `POST /api/admin/projects/{id}/cleanup-results`.
- **No existe `DELETE` de `dashboard_templates` ni de publicaciones.** Se
  acumulan sin ciclo de vida. Relevante para decidir si la configuracion nueva
  absorbe la tabla actual.
- **Atribucion de corridas manuales rota**: `create_run` acepta `triggered_by`
  y `trigger_type` (`app/persistence.py:5674-5680`), y las corridas programadas
  los usan (`app/schedules.py:202-205`), pero `create_and_enqueue_run`
  (`app/main.py:709-712`) **no los pasa**. Toda corrida manual queda estampada
  `triggered_by = "internal_analyst"`, sea quien sea el usuario. En contraste,
  la edicion de series si atribuye correctamente
  (`created_by=current_user_email(request)`, `app/main.py:2007`). Si un operador
  ejecuta, hoy no queda registro de quien fue. Insumo directo para
  **Rol y permisos del operador**.

### E. Senales canonicas y derivacion de "senales requeridas"

- **Registro canonico**: `TIME_SERIES_SIGNAL_CATALOG`
  (`app/time_series_catalog.py:32-75`), 8 claves. Cada
  `TimeSeriesSignalDefinition` (23-29) declara `signal_key`, `unit`,
  `entity_type`, `nonnegative`, `resampling_methods`. Confirmado: **no existe**
  ninguna senal de limite de potencia por unidad.
- **Derivacion de lo requerido**: `discover_required_signals`
  (`app/required_signals.py:48-75`) recorre `system_case["nodes"]` y mapea el
  tipo de nodo a una senal via `_ONE_BUS_ENTITY_SIGNALS`
  (`app/required_signals.py:12-17`) — `grid`, `load`, `renewable`, `hydro`. La
  parte hidraulica sale aparte de `hydraulic_network`
  (`app/required_signals.py:78-122`): consume la lista declarativa
  `required_time_series` y ademas deriva `minimum_flow_m3s` para todo tramo con
  `flow_min_source == "series"`.
- **La familia de precios es un caso especial**: `PRICE_SIGNAL_FAMILY`
  (`app/required_signals.py:6-10`) permite tres claves alternativas para el
  mismo requisito, y `_binding_matches_requirement`
  (`app/required_signals.py:159-167`) acepta bindings de precio sin scope de
  entidad como legado.
- **Como llega a la UI**: `evaluate_case_input_variant_required_signals`
  (`app/persistence.py:7076-7088`) -> `"required_signals"` en el detalle de la
  variante (`app/main.py:2122`) -> `frontend/src/Workspace.tsx:6990-7170`, que
  hoy los renderiza como selectores de binding para el analista.
- **Conclusion para la tabla editable**: la lista de columnas del operador es
  derivable sin inventar nada — `required_signals` de la variante da el eje de
  senales, y las columnas realmente editables son la interseccion con los
  `time_series_signals` del set vinculado. La derivacion **no** requiere que la
  consola conozca nombres de senal.
- **Contraste util**: `DISPATCH_SIGNAL_KEY_CATALOG`
  (`app/result_indexing.py:37-64`) es el registro canonico del lado de
  *salida*, con 24 claves, independiente del de entrada. Son dos vocabularios
  distintos; el spec no debe confundirlos.

### F. Que le entrega este inventario al modelo de datos

La superficie a cubrir tiene cuatro capas, y solo la primera existe hoy:

1. **Visibilidad de seccion** — los 9 booleanos. Existe; hay que decidir si se
   absorbe o se reemplaza, y hay que tapar el hueco de `all_series` (A.6).
2. **Etiquetas** — ~40 cadenas fijas en 3 archivos, en dos idiomas mezclados,
   repartidas entre backend (titulos y series de grafico) y frontend (secciones,
   vacios, KPIs). No hay hoy ningun punto unico donde interceptarlas.
3. **Contrato del payload** — hoy inexistente: el sobre pasa crudo (A.7) y el
   summary puede filtrar rutas del servidor (B.5).
4. **Punteros al caso** — el registro de senales de entrada (E) es la unica
   parte que ya es declarativa y derivable; es el modelo a imitar para el resto.

### Tickets y ajustes derivados

- **Creado**: *Contrato del payload de las superficies configuradas* (id 11),
  bloqueado por los dos tickets de cascaron. Sale de A.7 y B.5.
- **Insumo registrado** en *Rol y permisos del operador*: la atribucion de
  corridas manuales esta rota (D). No se corrige aqui — este mapa planifica.
- **Insumo registrado** en *Contrato de la tabla editable y del pegado desde
  Excel* y en *Edicion del operador frente a la regla fail-closed*: la edicion
  manual no puede crear periodos ni senales (C), y el parser no entiende
  formato es-CL (C).
