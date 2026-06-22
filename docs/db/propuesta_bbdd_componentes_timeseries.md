# Propuesta De BBDD Para Componentes, Parametros Por Caso Y Series Versionadas

Fecha: 2026-06-16

## Objetivo

Disenar una base de datos relacional para guardar:

- Caracteristicas de componentes del modelo one-bus.
- Parametros de cada componente por caso de optimizacion.
- Series de tiempo reales y simuladas asociadas a objetos/componentes.
- Versiones reutilizables de conjuntos de series de tiempo.
- La compatibilidad con el flujo actual:
  `Project -> Scenario -> ScenarioVersion -> Run -> Artifacts -> Publication`.

La propuesta no reemplaza los snapshots auditables actuales. El sistema debe
seguir generando y guardando `system_case_json` en `scenario_versions`, porque
esa es la entrada exacta que se ejecuta y audita. La BBDD normalizada propuesta
debe ser la fuente editable y reutilizable desde donde se genera ese snapshot.

Decision aceptada: `optimization_cases` sera el objeto editable normalizado y
`scenario_versions` seguira siendo el snapshot inmutable ejecutable.

## Contexto Relevante Leido En `docs/`

Los documentos actuales definen estos contratos:

- El optimizador es one-bus: un PCC/bus logico, sin red electrica fisica.
- Activos soportados: `bus`, `grid`, `battery`, `renewable`, `load`, `hydro`.
- `scenario_versions` son inmutables y las corridas apuntan a versiones, no a
  drafts.
- `system_case_json` sigue siendo el contrato ejecutable y reproducible.
- Los outputs principales son artefactos: `summary.json`, `dispatch.csv`,
  `asset_dispatch.csv`, `model_metadata.json`, `system_case_resolved.json`.
- La app ya tiene tablas de workflow: proyectos, escenarios, versiones,
  drafts, runs, artefactos, usuarios, templates y publicaciones.
- El editor estructurado actual guarda un documento JSON mutable; esta
  propuesta normaliza ese contenido en tablas.
- Las series de tiempo pueden venir de CSV/XLSX y deben validar timestamp,
  duracion, columnas requeridas, valores no numericos y valores negativos segun
  tipo de senal.
- Hidro usa `bess_system_dispatch.v2` con curvas de generacion y embalse.
- La hidraulica actual representa un `hydro` como un embalse independiente mas
  una planta asociada. La hidraulica futura puede requerir una red hidraulica
  interna con embalses, centrales, unidades y tramos de agua.
- Decision aceptada para hidraulica futura: mantener un solo bus electrico y
  modelar una red hidraulica interna normalizada. Embalses, tramos, centrales y
  unidades quedan como componentes hidraulicos internos; solo las centrales o
  unidades generadoras aportan potencia al balance electrico one-bus.
- Decision aceptada para estructura de hidraulica futura: usar una capa propia
  `hydraulic_systems` con `hydraulic_nodes`, `hydraulic_reaches`,
  `hydraulic_plants` y `hydraulic_units`. La tabla `components` queda para
  objetos publicos/reutilizables del proyecto, sin mezclar todos los detalles
  hidraulicos finos en el catalogo general.
- Decision aceptada para topologia hidraulica: modelar desde el inicio una red
  dirigida general. Un embalse puede recibir agua desde multiples tramos aguas
  arriba y descargar hacia multiples tramos, centrales, unidades, bypasses o
  restituciones. La primera formulacion puede usar un subconjunto simple, pero
  la BBDD no debe imponer una relacion uno-a-uno embalse-central.
- Decision aceptada para tramos hidraulicos: `hydraulic_reaches` no sera solo
  conectividad. Debe guardar propiedades operacionales opcionales como tipo de
  tramo, capacidad minima/maxima, tiempo de viaje, perdidas, evaporacion o
  infiltracion, controlabilidad y metadata. El primer optimizador podra ignorar
  algunas columnas, pero la BBDD debe poder representar canales, tuneles, rios,
  compuertas, vertederos, bypasses y restituciones.
- Decision aceptada para centrales y unidades: las curvas de generacion,
  limites operacionales, disponibilidad y parametros tecnicos principales deben
  vivir a nivel `hydraulic_units`. `hydraulic_plants` agrupa unidades, define
  metadata comun y puede tener limites agregados opcionales cuando el caso lo
  requiera.
- Decision aceptada para balance por unidad: cada `hydraulic_unit` debe tener
  `intake_node_id` y `discharge_node_id`. La central agrupa unidades, pero el
  balance hidraulico debe poder rastrear por donde entra y sale el agua de cada
  unidad.
- Decision aceptada para generacion hidraulica futura: la BBDD debe soportar
  una curva simple caudal-potencia por unidad y quedar preparada para una
  modalidad futura dependiente de head/cota. El optimizador actual puede seguir
  usando `flow_power_curve`, pero el esquema debe reservar `generation_mode =
  head_dependent` y tablas de curvas o superficies por caudal y head neto.
- Decision aceptada para embalses: guardar parametros escalares y curvas
  separadas. Ademas de almacenamiento-cota, el esquema debe contemplar volumen
  muerto, volumen util, cotas operativas, curva almacenamiento-area y series
  futuras para evaporacion, afluente natural y restricciones ambientales.
- Decision aceptada para restricciones ambientales: asociarlas principalmente
  al `hydraulic_reach` donde debe cumplirse el caudal. Si una regla depende de
  un embalse, central o unidad, se puede referenciar en metadata, pero el
  constraint operativo debe vivir sobre el tramo/arco que mide el flujo.
- Decision aceptada para vertimientos: modelarlos como `hydraulic_reaches`
  especiales con `reach_type = spillway`. Asi cada vertedero tiene origen,
  destino, capacidad, penalizaciones, series/curvas y participa en el balance
  hidraulico como cualquier otro flujo.
- Decision aceptada para afluentes naturales: permitir `natural_inflow_m3s`
  como serie asociada a cualquier `hydraulic_node`, no solo a embalses. Esto
  permite representar afluentes laterales, aportes entre embalses, entradas a
  bocatomas o inyecciones en nodos de union.
- Decision aceptada para objetos fisicos versus caso: la BBDD debe distinguir
  entre la red hidraulica base del proyecto y su parametrizacion por caso. Los
  objetos base viven en `hydraulic_systems`, `hydraulic_nodes`,
  `hydraulic_reaches`, `hydraulic_plants` y `hydraulic_units`; los parametros,
  curvas, restricciones, estados iniciales y disponibilidad especificos viven en
  tablas `case_hydraulic_*`.
- Decision aceptada para series hidraulicas: las series de tiempo deben poder
  asociarse tanto a `components` generales como a objetos hidraulicos internos.
  `time_series_signals` usara una asociacion controlada por `entity_type` y
  `entity_id` para soportar senales en `component`, `hydraulic_node`,
  `hydraulic_reach`, `hydraulic_plant`, `hydraulic_unit` y otros objetos
  futuros.
- Decision aceptada para mapeos de importacion: `time_series_import_mappings`
  usara tambien `entity_type` y `entity_id`, no `component_id`, para mapear
  columnas de CSV/XLSX/API directamente a componentes generales u objetos
  hidraulicos internos.
- Decision aceptada para bindings de series: `case_time_series_bindings` usara
  `entity_type` y `entity_id`, no `case_component_id`, para asociar una senal
  a entidades activas del caso como `case_component`,
  `case_hydraulic_node`, `case_hydraulic_reach`, `case_hydraulic_plant` o
  `case_hydraulic_unit`.
- Decision aceptada para reutilizacion de red hidraulica: la red hidraulica
  base pertenece al proyecto y se reutiliza entre casos. Cada
  `optimization_case` selecciona y parametriza esa red mediante tablas
  `case_hydraulic_*`, sin duplicar toda la topologia fisica.
- Decision aceptada para subconjuntos por caso: un `optimization_case` puede
  usar solo una parte de la red hidraulica base. Las tablas
  `case_hydraulic_nodes`, `case_hydraulic_reaches`, `case_hydraulic_plants` y
  `case_hydraulic_units` deben incluir `enabled`, `case_label`, `sort_order` y
  metadata para seleccionar la topologia activa del caso.
- Decision aceptada para validacion topologica hidraulica: antes de promover o
  ejecutar un caso, validar que la red activa sea cerrada y consistente:
  tramos activos conectan nodos activos, unidades activas conectan intake y
  discharge activos, plantas activas tienen unidades activas, embalses activos
  tienen parametros y curvas requeridas, y ciclos hidraulicos solo se permiten
  si el `routing_method` y el modulo Julia los soportan.
- Decision aceptada para islas hidraulicas: permitir multiples componentes
  hidraulicos desconectados dentro del mismo caso solo si cada isla tiene al
  menos una condicion de borde clara, como afluente natural, embalse con estado
  inicial, descarga/salida modelada o unidad conectada a una central. Rechazar
  islas sin fuente, almacenamiento, salida o decision operacional.
- Decision aceptada para persistencia de islas hidraulicas: no crear una tabla
  persistente de islas en el MVP. Las islas se calculan durante la validacion
  desde la red activa del caso y el resultado se guarda en
  `optimization_cases.validation_payload_json`. Si la UI necesita consultarlas
  frecuentemente, se puede agregar despues una tabla/cache derivada.
- Decision aceptada para atributos fisicos versus operacionales: la red base
  guarda atributos estables como nombres oficiales, coordenadas, tipo de obra,
  fabricante, relaciones topologicas y datos de ingenieria. Las tablas por caso
  guardan limites activos, disponibilidad, estados iniciales, restricciones,
  penalizaciones, curvas usadas por la optimizacion, mantenimientos y series
  vinculadas.
- Decision aceptada para curvas hidraulicas: las curvas deben ser versionables
  y reutilizables. Usar `hydraulic_curve_sets`, `hydraulic_curve_points` y
  `case_hydraulic_curve_bindings` para elegir que version de curva usa cada
  caso. El `system_case_json` promovido conserva la copia exacta ejecutada.
- Decision aceptada para bindings de curvas: `case_hydraulic_curve_bindings`
  apunta solo a entidades activas del caso, como `case_hydraulic_node`,
  `case_hydraulic_reach`, `case_hydraulic_plant` o `case_hydraulic_unit`. La
  curva reusable vive en `hydraulic_curve_sets`; el generador valida que la
  curva corresponda al objeto fisico base resuelto desde la entidad activa.
- Decision aceptada para dimensionalidad de curvas: el esquema debe soportar
  curvas 1D y quedar preparado para superficies 2D. `hydraulic_curve_sets`
  debe declarar dimensiones, nombres y unidades de ejes; `hydraulic_curve_points`
  debe permitir `x_value`, `y_value` y opcionalmente `z_value` para relaciones
  futuras como potencia o eficiencia en funcion de caudal y head neto.
- Decision aceptada para mantenimientos e indisponibilidades: representar los
  eventos en una tabla auditable `availability_events` con causa, inicio, fin y
  entidad afectada, y representar la disponibilidad usada por el optimizador
  como serie derivada en `time_series_signals`, por ejemplo
  `unit_availability_factor`.
- Decision aceptada para alcance de indisponibilidades: `availability_events`
  debe usar `entity_type` y `entity_id` para aplicar eventos a
  `hydraulic_unit`, `hydraulic_plant`, `hydraulic_reach`, `hydraulic_node`,
  `hydraulic_system`, `component` u otros objetos futuros. El generador del
  caso expande esos eventos a series numericas segun corresponda.
- Decision aceptada para nivel de `availability_events`: los eventos quedan a
  nivel proyecto y apuntan a entidades base o componentes estables, no a
  entidades activas de un caso. Para ejecutar un caso, esos eventos se filtran
  por horizonte y red activa, y se materializan como series versionadas
  (`time_series_sets`/`time_series_signals`) o directamente en el
  `scenario_version` ejecutable.
- Decision aceptada para trazabilidad de eventos derivados: cuando un evento
  de disponibilidad se transforma en una senal versionada, guardar la relacion
  en `availability_event_time_series_links`. Esto permite auditar que eventos
  explican una serie como `unit_availability_factor` sin duplicar logica dentro
  de `time_series_values`.
- Decision aceptada para solapamiento de eventos: permitir eventos solapados
  para la misma entidad, pero combinarlos de forma deterministica al derivar
  series. Se ignoran eventos `cancelled`; se consideran eventos que intersectan
  el horizonte; y cuando hay multiples limites para el mismo periodo se usa el
  valor mas restrictivo (`min` de `availability_factor`, `capacity_limit_mw` o
  `flow_limit_m3s`). Reglas especiales futuras pueden declararse en
  `metadata_json` o en un catalogo especifico.
- Decision aceptada para tiempo de viaje en tramos: guardar
  `travel_time_hours` como propiedad fisica y `routing_method` opcional
  (`none`, `fixed_delay`, `linear_reservoir`, `custom_curve`). La conversion a
  retardos discretos por periodo depende del horizonte y debe hacerse en el
  generador del caso o en el optimizador, no como dato fijo unico de la BBDD.
- Decision aceptada para tipos de nodos hidraulicos: usar una tabla comun
  `hydraulic_nodes` con `node_type` (`reservoir`, `junction`, `intake`,
  `tailrace`, `river_inflow`, etc.) y tablas especializadas de parametros solo
  para tipos que lo requieran, como embalses.
- Decision aceptada para bombeo y unidades reversibles: dejar el esquema
  preparado con `hydraulic_units.unit_capability` o campo equivalente
  (`generation_only`, `pump_only`, `reversible`). El primer optimizador puede
  ignorarlo, pero la BBDD no debe bloquear pumped storage o unidades reversibles
  futuras.
- Decision aceptada para scripts Julia por caso: separar restricciones y
  terminos de objetivo. Las restricciones viven en `constraint_definitions` y
  `case_constraint_bindings`; los costos, ingresos, penalizaciones o valores
  economicos adicionales viven en `objective_term_definitions` y
  `case_objective_term_bindings`.
- Decision aceptada para entidades de restricciones: los bindings de
  restricciones usan solo `entity_type` y `entity_id` apuntando a entidades
  activas del caso, como `case_component`, `case_hydraulic_node`,
  `case_hydraulic_reach`, `case_hydraulic_plant` o `case_hydraulic_unit`. No
  se usa `case_entity_id` adicional; si Julia necesita el objeto fisico base,
  el generador lo resuelve desde la fila activa del caso.
- Decision aceptada para terminos de objetivo especificos: usar el mismo patron
  allowlisted que restricciones. `objective_term_definitions` declara
  `objective_term_key`, modulo Julia, funcion, version de implementacion y
  esquema de parametros; `case_objective_term_bindings` activa el termino por
  caso. No guardar formulas arbitrarias ejecutables en la BBDD al inicio.
- Decision aceptada para entidades de objetivos: los bindings de terminos de
  objetivo usan entidades activas del caso igual que restricciones:
  `case_component`, `case_hydraulic_node`, `case_hydraulic_reach`,
  `case_hydraulic_plant`, `case_hydraulic_unit`, etc.
- Decision aceptada para versionado de contratos: restricciones y terminos de
  objetivo deben versionar por separado `implementation_version` y
  `parameter_schema_version`. La primera identifica el codigo Julia; la segunda
  identifica la forma de los parametros que guarda la BBDD y que se exporta al
  payload del caso.
- Decision aceptada para snapshot de ejecucion: al promover un
  `optimization_case` a `scenario_versions`, se debe congelar un payload
  expandido con restricciones y terminos de objetivo resueltos:
  `constraint_key`, `objective_term_key`, `implementation_version`,
  `parameter_schema_version`, parametros, entidades y series. La version
  ejecutada no debe depender de cambios futuros en los catalogos allowlisted.
- Decision aceptada sobre versiones de series: `time_series_sets.version_label`
  y `time_series_sets.version_number` existen para cambiar rapidamente entre
  sets de series de tiempo y reutilizarlos en distintas corridas o variantes.
  Esto es distinto de `scenario_versions`, que congela el snapshot completo
  ejecutable.
- Decision aceptada para variantes de series: usar `case_input_variants` para
  cambiar bindings de series sobre un mismo `optimization_case` sin duplicar
  todos los parametros fisicos/operacionales. Al promover, el snapshot ejecutable
  se genera desde `optimization_case + case_input_variant`.
- Decision aceptada para trazabilidad de corridas y variantes: `runs` sigue
  apuntando solo a `scenario_versions`, porque esa version congela todo lo
  ejecutable. `scenario_versions` debe guardar metadata explicita como
  `normalized_case_id`, `case_input_variant_id` y
  `time_series_set_versions_json` para filtrar y auditar variantes sin abrir el
  JSON completo.
- Decision aceptada para alcance de `case_input_variants`: las variantes de
  entrada cambian solo bindings de series de tiempo. Estados iniciales, limites,
  curvas, restricciones y otros parametros fisicos u operacionales siguen en
  `optimization_cases` y tablas `case_*_parameters`. Si se necesita variar
  parametros, se crea otro caso o una variante de parametros separada futura.
- Decision aceptada para composicion de variantes: una `case_input_variant`
  puede combinar multiples `time_series_sets`, por ejemplo precios de un set,
  hidrologia de otro, demanda de otro y renovables de otro. La validacion debe
  asegurar que todos los sets vinculados tengan horizonte compatible.
- Decision aceptada para resolucion temporal: en el MVP los bindings
  ejecutables de una variante deben tener horizonte identico, incluyendo
  `timestamp_start`, `timestamp_end` y `duration_hours`. Resampling,
  agregacion o interpolacion quedan como transformaciones versionadas futuras,
  no como comportamiento implicito.
- Decision aceptada para calendario y zona horaria: los periodos de series se
  guardan con `timestamp_start` y `timestamp_end` como `TIMESTAMPTZ`,
  `timezone` vive en `time_series_sets`, `duration_hours` se conserva por
  periodo y la alineacion entre sets ejecutables se valida por `period_index`.
  Esto permite representar cambios de hora, dias de 23/25 horas y resoluciones
  no horarias sin perder el calendario local usado para importar o mostrar los
  datos.
- Decision aceptada para transformaciones de series: resampling, interpolacion,
  escalamiento y combinacion de escenarios deben guardarse como pipelines
  declarativos versionados en `time_series_transformations`, con set de entrada,
  set de salida, tipo de transformacion, parametros, version de implementacion y
  auditoria. No guardar scripts libres como fuente primaria de transformacion.
- Decision aceptada para herencia de variantes: `case_input_variants` puede
  tener `parent_variant_id` opcional. Una variante hija hereda bindings de la
  variante padre y sobrescribe solo algunos. Al promover, la herencia se
  resuelve a bindings explicitos dentro del snapshot ejecutable.
- Decision aceptada para sobrescritura de bindings heredados: agregar
  `binding_action` a `case_time_series_bindings` con valores `set` y `unset`.
  `set` asigna una serie; `unset` elimina un binding heredado. Si una senal
  requerida queda sin binding efectivo, la validacion de la variante debe
  fallar antes de promover.
- Decision aceptada para tipos de series: `time_series_sets.data_kind` y
  `time_series_signals.data_kind` deben distinguir al menos `real`,
  `programmed`, `forecast`, `simulated`, `synthetic` y `mixed`. `programmed`
  representa programas, planes o despachos informados por una entidad externa,
  distinto de una medicion real, un forecast o un output simulado por la
  herramienta.
- Decision aceptada para series programadas: `time_series_sources` debe guardar
  emisor y vigencia estructurada para programas externos o internos:
  `issuer_name`, `issuer_type`, `issued_at`, `valid_from`, `valid_to` y
  `source_reference`.
- Decision aceptada para uso de series programadas: una serie `programmed` puede
  usarse como input directo, baseline, target de una restriccion/objetivo o
  comparacion visual. El uso concreto se define con `binding_role`.
- Decision aceptada para series simuladas: los outputs de la herramienta no se
  cargan automaticamente todos a `time_series_sets`. Siempre quedan como
  artefactos auditables de la corrida; se registran como
  `time_series_sets.data_kind = 'simulated'` solo cuando el usuario decide
  guardar esos outputs como serie reutilizable/comparable. Esos sets simulados
  tambien usan `time_series_sets.version_number` y
  `time_series_sets.version_label`.
- Decision aceptada para versionado de sets de series: separar
  `version_number` y `version_label`. `version_number` es incremental y
  monotono por `(project_id, name)`; `version_label` es la etiqueta humana, por
  ejemplo `cen_program_2026-06-16`, `dry_year_v2` o `sim_run_42_v1`.
- Decision aceptada para unicidad de version labels: `version_label` debe ser
  unico solo dentro de `(project_id, name)`, no global al proyecto. Asi distintos
  sets pueden tener etiquetas simples como `v1` sin colisionar.
- Decision aceptada para edicion de series versionadas: un `time_series_set`
  puede editarse, incluso conservando su `version_number` y `version_label`.
  Para no romper reproducibilidad, cualquier `scenario_version` promovida debe
  congelar el contenido efectivo de las series usadas, o al menos sus hashes y
  payload resuelto, dentro del snapshot ejecutable. La BBDD debe registrar
  auditoria de edicion del set.
- Decision aceptada para historial de edicion de series: usar una tabla liviana
  `time_series_set_revisions` con `revision_number`, `content_hash`,
  `change_summary`, `created_at` y `created_by`. No duplicar todos los valores
  en cada revision al inicio; para auditoria fuerte se puede conservar archivo
  fuente o snapshot compactado como artefacto.
- Decision aceptada para invalidacion por edicion de series: toda edicion de
  valores debe recalcular `content_hash` y marcar como stale las validaciones de
  `case_input_variants` que dependan de ese set. Antes de promover una nueva
  `scenario_version` se debe revalidar la variante con los hashes vigentes.
- Decision aceptada para dependencias de validacion: guardar dependencias
  explicitas entre `case_input_variants` y los hashes de series usados en la
  ultima validacion mediante `validation_dependencies`.
  Si el hash actual de un set difiere del hash validado, la variante queda
  stale y debe revalidarse antes de promover.
- Decision aceptada para materializacion en `scenario_versions`: la version
  promovida debe guardar los valores de series materializados dentro de
  `system_case_json` y, ademas, metadata de trazabilidad con
  `time_series_set_id`, `version_number`, `version_label`, `content_hash` y
  `revision_number` usados al momento de promocion.
- Decision aceptada para almacenamiento fisico de series: mantener
  `time_series_values` en formato long como modelo logico portable. Agregar
  `time_series_set_id` denormalizado y validado para facilitar consultas,
  borrado por set y particionamiento futuro. En MVP basta PostgreSQL normal
  con indices; si el volumen crece, particionar por `time_series_set_id` o usar
  TimescaleDB/hypertables sin cambiar el contrato logico.
- Decision aceptada para invalidacion de restricciones y objetivos: los
  bindings de restricciones y terminos de objetivo deben guardar dependencias de
  validacion para detectar stale cuando cambien series, curvas o parametros que
  usan. En MVP puede aplicarse primero a series; luego extenderse a curvas y
  parametros con hashes o timestamps.
- Decision aceptada para dependencias genericas de validacion: usar una tabla
  unica `validation_dependencies` para variantes de series, restricciones y
  terminos de objetivo. El owner se identifica con `owner_type` y `owner_id`; la
  dependencia con `dependency_type` y `dependency_id`.
- Decision aceptada para hashes de parametros por caso: usar
  `case_parameter_group_hashes` para guardar `content_hash` por grupo de
  parametros, entidad y caso. Esto permite detectar validaciones stale sin
  comparar columna por columna en tablas `case_*_parameters`.
- Decision aceptada para solver settings: `case_solver_settings` forma parte
  del caso promovido y debe quedar en el snapshot/hash de ejecucion cuando se
  genere `scenario_versions`. La reproducibilidad es importante, pero no se
  tratara como garantia absoluta si el usuario edita objetos versionados desde
  la UI; el producto debe mostrar warnings/resguardos cuando una edicion pueda
  afectar corridas o versiones previas.
- Decision aceptada para inmutabilidad de `scenario_versions`: se mantienen
  inmutables. Las ediciones permitidas ocurren en objetos fuente como series,
  variantes, casos draft y parametros normalizados; si se necesita corregir una
  version ejecutable, se promueve una nueva `scenario_version`.
- Decision aceptada para ejecucion: las corridas no se ejecutan directamente
  desde `optimization_case + case_input_variant`. Siempre se crea o reutiliza
  una `scenario_version` promovida. La UI puede ocultar el paso creando la
  version automaticamente al hacer "Run variant", previa validacion y warnings
  si el caso o variante esta stale.
- Decision aceptada para deduplicacion de `scenario_versions`: si al ejecutar
  una variante ya existe una `scenario_version` con el mismo
  `generated_system_case_hash`, se reutiliza esa version. Si el hash cambio, se
  crea una nueva. Esto evita duplicar snapshots identicos.
- Decision aceptada para alcance del hash ejecutable:
  `generated_system_case_hash` considera solo el payload ejecutable canonizado:
  parametros, series materializadas, solver, restricciones y terminos de
  objetivo. Metadata visible o de auditoria como nombre, notas, fuente textual y
  usuario queda en `generation_metadata_json` y no cambia la equivalencia
  matematica.
- Decision aceptada para feedback de UI al correr variantes: la UI debe mostrar
  si se reutilizo una `scenario_version` existente o si se creo una nueva,
  idealmente indicando el motivo, por ejemplo cambios de series, parametros,
  restricciones u objetivo.
- Decision aceptada para comparacion de variantes: la UI debe permitir comparar
  dos `case_input_variants` antes de correrlas, mostrando diferencias de
  bindings de series, `time_series_set.name`, `version_label`, `content_hash` y
  horizonte. Esta comparacion se enfoca en series, no en parametros.

## Principios

1. **No perder auditoria**: cada corrida debe poder reconstruirse desde el
   `scenario_version.system_case_json` exacto.
2. **Caso como eje de parametros**: los parametros escalares pueden cambiar
   entre casos; por eso todas las tablas de parametros incluyen `case_id`.
   En SQL se recomienda `case_id`, no `case`, porque `CASE` es palabra
   reservada.
3. **Componente separado de parametros**: `components` representa el objeto
   estable del proyecto; `case_*_parameters` representa como se modela ese
   objeto dentro de un caso.
4. **Series versionadas por set**: `version_number` y `version_label` viven en
   `time_series_sets`, porque lo reutilizable es el conjunto completo de series
   alineadas.
5. **Series asociadas a objetos**: cada senal puede apuntar a una entidad con
   `entity_type` y `entity_id`, o ser global del caso, como precios.
6. **Tipos fuertes para lo estable, JSONB para extensiones**: parametros
   conocidos deben estar en columnas tipadas; `metadata_json` queda para datos
   auxiliares no usados por el optimizador.

## Relacion Conceptual

```text
projects
  -> scenarios
    -> optimization_cases
      -> case_components
        -> case_*_parameters
      -> case_time_series_bindings
        -> time_series_sets(version_number, version_label)
          -> time_series_periods
          -> time_series_signals
          -> time_series_values
      -> scenario_versions(system_case_json inmutable)
        -> runs
          -> run_artifacts
```

## Tablas Existentes Que Se Mantienen

| Tabla existente | Uso actual | Cambio recomendado |
| --- | --- | --- |
| `projects` | Agrupa trabajo del analista y publicaciones cliente. | Mantener. |
| `scenarios` | Agrupa alternativas de modelacion bajo un proyecto. | Mantener. |
| `scenario_versions` | Snapshot inmutable ejecutable con `system_case_json`. | Agregar `normalized_case_id`, `case_input_variant_id` y `time_series_set_versions_json` nullable si se implementa esta propuesta. |
| `scenario_drafts` | Draft JSON mutable del editor. | Puede convivir durante migracion; luego reemplazarse por `optimization_cases`. |
| `runs` | Corridas manuales sobre una version. | Mantener. |
| `run_artifacts` | Archivos auditables por corrida. | Mantener. |
| `users`, `auth_sessions` | Auth local. | Mantener. |
| `project_client_access` | Acceso cliente-proyecto. | Mantener. |
| `dashboard_templates` | Configuracion visible para cliente. | Mantener. |
| `publications` | Publicacion controlada de runs exitosos. | Mantener. |

## Nueva Capa Normalizada

### `optimization_cases`

Representa un caso editable/validable dentro de un escenario. Es el objeto que
agrupa parametros, componentes y bindings de series.

| Campo | Tipo sugerido | Requerido | Descripcion |
| --- | --- | --- | --- |
| `id` | `BIGSERIAL PK` | Si | Identificador interno. |
| `scenario_id` | `BIGINT FK scenarios(id)` | Si | Escenario al que pertenece. |
| `case_key` | `TEXT` | Si | Identificador estable legible, por ejemplo `hydro_linear_base`. |
| `name` | `TEXT` | Si | Nombre visible del caso. |
| `description` | `TEXT` | No | Descripcion del caso. |
| `schema_version` | `TEXT` | Si | `bess_system_dispatch.v1` o `bess_system_dispatch.v2`. |
| `status` | `TEXT` | Si | `draft`, `validated`, `promoted`, `archived`. |
| `base_scenario_version_id` | `BIGINT FK scenario_versions(id)` | No | Version usada como base, si existe. |
| `generated_system_case_hash` | `TEXT` | No | Hash del ultimo JSON generado y validado. |
| `validation_payload_json` | `JSONB` | Si | Resultado de la ultima validacion. |
| `last_validated_at` | `TIMESTAMPTZ` | No | Fecha de validacion exitosa o fallida. |
| `created_at` | `TIMESTAMPTZ` | Si | Auditoria. |
| `updated_at` | `TIMESTAMPTZ` | Si | Auditoria. |
| `created_by` | `TEXT` | Si | Usuario o servicio. |
| `updated_by` | `TEXT` | Si | Usuario o servicio. |

Restricciones:

- `UNIQUE (scenario_id, case_key)`.
- Si `status = promoted`, no se deben editar parametros ni bindings asociados.
  Recomendacion: trigger de inmutabilidad o crear un nuevo caso.

### `components`

Catalogo de objetos estables dentro de un proyecto. Un componente puede usarse
en muchos casos con parametros distintos.

| Campo | Tipo sugerido | Requerido | Descripcion |
| --- | --- | --- | --- |
| `id` | `BIGSERIAL PK` | Si | Identificador interno. |
| `project_id` | `BIGINT FK projects(id)` | Si | Proyecto dueno. |
| `component_key` | `TEXT` | Si | ID estable del objeto, por ejemplo `battery_1`. |
| `component_type` | `TEXT` | Si | `bus`, `grid`, `battery`, `renewable`, `load`, `hydro`. |
| `display_name` | `TEXT` | Si | Nombre visible. |
| `external_reference` | `TEXT` | No | ID externo, medidor, planta, contrato, etc. |
| `is_active` | `BOOLEAN` | Si | Permite retirar componentes sin borrar historia. |
| `metadata_json` | `JSONB` | Si | Datos descriptivos no usados directamente por Julia. |
| `created_at` | `TIMESTAMPTZ` | Si | Auditoria. |
| `updated_at` | `TIMESTAMPTZ` | Si | Auditoria. |

Restricciones:

- `UNIQUE (project_id, component_key)`.
- `component_type IN ('bus', 'grid', 'battery', 'renewable', 'load', 'hydro')`.

### `case_components`

Relaciona un componente estable con un caso y define el `asset_id` que vera
`system_case_json`.

| Campo | Tipo sugerido | Requerido | Descripcion |
| --- | --- | --- | --- |
| `id` | `BIGSERIAL PK` | Si | Identificador interno. |
| `case_id` | `BIGINT FK optimization_cases(id)` | Si | Caso de optimizacion. |
| `component_id` | `BIGINT FK components(id)` | Si | Componente del proyecto. |
| `case_asset_id` | `TEXT` | Si | ID usado en el JSON, por ejemplo `hydro_1`. |
| `node_type` | `TEXT` | Si | Tipo de nodo en el contrato Julia. |
| `enabled` | `BOOLEAN` | Si | Permite desactivar el activo en un caso. |
| `sort_order` | `INTEGER` | Si | Orden de render/generacion. |
| `metadata_json` | `JSONB` | Si | Metadata especifica del caso. |

Restricciones:

- `UNIQUE (case_id, case_asset_id)`.
- `UNIQUE (case_id, component_id)`, salvo que en el futuro se permita modelar
  el mismo objeto fisico como mas de un activo logico.

### `case_edges`

Guarda conexiones logicas del grafo. En el alcance actual son conexiones al
PCC, no flujos de red.

| Campo | Tipo sugerido | Requerido | Descripcion |
| --- | --- | --- | --- |
| `id` | `BIGSERIAL PK` | Si | Identificador interno. |
| `case_id` | `BIGINT FK optimization_cases(id)` | Si | Caso de optimizacion. |
| `from_case_component_id` | `BIGINT FK case_components(id)` | Si | Activo origen. |
| `to_case_component_id` | `BIGINT FK case_components(id)` | Si | Bus/PCC destino. |
| `edge_type` | `TEXT` | Si | `logical_connection`. |
| `metadata_json` | `JSONB` | Si | Reservado para extensiones. |

Restricciones:

- `UNIQUE (case_id, from_case_component_id, to_case_component_id)`.
- Validacion de aplicacion: exactamente un `bus`/PCC por caso.

### `case_solver_settings`

Configura solver y horizonte del caso.

| Campo | Tipo sugerido | Requerido | Descripcion |
| --- | --- | --- | --- |
| `id` | `BIGSERIAL PK` | Si | Identificador. |
| `case_id` | `BIGINT FK optimization_cases(id)` | Si | Caso. |
| `solver_name` | `TEXT` | Si | Default `HiGHS`. |
| `solver_options_json` | `JSONB` | Si | Opciones avanzadas del solver. |
| `horizon_mode` | `TEXT` | Si | Default `full_horizon`. |
| `start_timestamp` | `TIMESTAMPTZ` | No | Futuro rolling/window. |
| `end_timestamp` | `TIMESTAMPTZ` | No | Futuro rolling/window. |
| `step_hours` | `DOUBLE PRECISION` | No | Futuro rolling horizon. |
| `lookahead_periods` | `INTEGER` | No | Futuro rolling horizon. |

Restricciones:

- `UNIQUE (case_id)`.

## Tablas De Parametros Por Tipo De Componente

Todas las tablas de parametros incluyen `case_id`. Esto hace explicito que los
parametros pueden variar entre casos de optimizacion aunque el componente sea
el mismo.

### `case_bus_parameters`

| Campo | Tipo sugerido | Requerido | Descripcion |
| --- | --- | --- | --- |
| `id` | `BIGSERIAL PK` | Si | Identificador. |
| `case_id` | `BIGINT FK optimization_cases(id)` | Si | Caso. |
| `case_component_id` | `BIGINT FK case_components(id)` | Si | Componente tipo `bus`. |
| `bus_role` | `TEXT` | Si | Default `pcc`. |
| `metadata_json` | `JSONB` | Si | Datos descriptivos. |

Restricciones:

- `UNIQUE (case_id, case_component_id)`.
- Validacion: un solo `bus_role = 'pcc'` por caso.

### `case_grid_parameters`

| Campo | Tipo sugerido | Requerido | Descripcion |
| --- | --- | --- | --- |
| `id` | `BIGSERIAL PK` | Si | Identificador. |
| `case_id` | `BIGINT FK optimization_cases(id)` | Si | Caso. |
| `case_component_id` | `BIGINT FK case_components(id)` | Si | Componente tipo `grid`. |
| `import_power_max_mw` | `DOUBLE PRECISION` | No | Limite de importacion; puede ser `NULL`. |
| `export_power_max_mw` | `DOUBLE PRECISION` | No | Limite de exportacion; puede ser `NULL`. |
| `prevent_simultaneous_grid_import_export` | `BOOLEAN` | Si | Default `TRUE`. |
| `metadata_json` | `JSONB` | Si | Reservado. |

Restricciones:

- `UNIQUE (case_id, case_component_id)`.
- `import_power_max_mw >= 0` si no es `NULL`.
- `export_power_max_mw >= 0` si no es `NULL`.

### `case_battery_parameters`

| Campo | Tipo sugerido | Requerido | Descripcion |
| --- | --- | --- | --- |
| `id` | `BIGSERIAL PK` | Si | Identificador. |
| `case_id` | `BIGINT FK optimization_cases(id)` | Si | Caso. |
| `case_component_id` | `BIGINT FK case_components(id)` | Si | Componente tipo `battery`. |
| `charge_power_max_mw` | `DOUBLE PRECISION` | Si | Potencia maxima de carga. |
| `discharge_power_max_mw` | `DOUBLE PRECISION` | Si | Potencia maxima de descarga. |
| `energy_min_mwh` | `DOUBLE PRECISION` | Si | Energia minima. |
| `energy_max_mwh` | `DOUBLE PRECISION` | Si | Energia maxima. |
| `initial_energy_mwh` | `DOUBLE PRECISION` | Si | Energia inicial. |
| `charge_efficiency` | `DOUBLE PRECISION` | Si | Eficiencia de carga. |
| `discharge_efficiency` | `DOUBLE PRECISION` | Si | Eficiencia de descarga. |
| `degradation_cost_per_mwh_delta_soc` | `DOUBLE PRECISION` | Si | Costo de degradacion lineal. |
| `prevent_simultaneous_charge_discharge` | `BOOLEAN` | Si | Anti-simultaneidad BESS. |
| `terminal_condition` | `TEXT` | Si | `none`, `equal_initial`, `min_terminal`. |
| `terminal_energy_min_mwh` | `DOUBLE PRECISION` | No | Requerido si `terminal_condition = min_terminal`. |
| `degradation_linear_delta_soc` | `BOOLEAN` | Si | Activa degradacion lineal. |

Restricciones:

- `UNIQUE (case_id, case_component_id)`.
- `energy_min_mwh < energy_max_mwh`.
- `energy_min_mwh <= initial_energy_mwh <= energy_max_mwh`.
- `0 < charge_efficiency <= 1`.
- `0 < discharge_efficiency <= 1`.
- `degradation_cost_per_mwh_delta_soc >= 0`.

### `case_renewable_parameters`

| Campo | Tipo sugerido | Requerido | Descripcion |
| --- | --- | --- | --- |
| `id` | `BIGSERIAL PK` | Si | Identificador. |
| `case_id` | `BIGINT FK optimization_cases(id)` | Si | Caso. |
| `case_component_id` | `BIGINT FK case_components(id)` | Si | Componente tipo `renewable`. |
| `renewable_category` | `TEXT` | No | `solar`, `wind`, `other`; metadata de UI. |
| `curtailment_penalty_usd_per_mwh` | `DOUBLE PRECISION` | Si | Default `0`. |
| `metadata_json` | `JSONB` | Si | Reservado. |

Restricciones:

- `UNIQUE (case_id, case_component_id)`.
- `curtailment_penalty_usd_per_mwh >= 0`.

### `case_load_parameters`

Actualmente la carga local tiene casi todo en series de tiempo. Esta tabla deja
un lugar estable para metadata y futuras reglas sin forzar JSON ad hoc.

| Campo | Tipo sugerido | Requerido | Descripcion |
| --- | --- | --- | --- |
| `id` | `BIGSERIAL PK` | Si | Identificador. |
| `case_id` | `BIGINT FK optimization_cases(id)` | Si | Caso. |
| `case_component_id` | `BIGINT FK case_components(id)` | Si | Componente tipo `load`. |
| `demand_required` | `BOOLEAN` | Si | Default `TRUE`; hoy la demanda debe servirse. |
| `metadata_json` | `JSONB` | Si | Categoria, cliente, barra logica, etc. |

Restricciones:

- `UNIQUE (case_id, case_component_id)`.

### `case_hydro_parameters`

| Campo | Tipo sugerido | Requerido | Descripcion |
| --- | --- | --- | --- |
| `id` | `BIGSERIAL PK` | Si | Identificador. |
| `case_id` | `BIGINT FK optimization_cases(id)` | Si | Caso. |
| `case_component_id` | `BIGINT FK case_components(id)` | Si | Componente tipo `hydro`. |
| `storage_min_hm3` | `DOUBLE PRECISION` | Si | Almacenamiento minimo. |
| `storage_max_hm3` | `DOUBLE PRECISION` | Si | Almacenamiento maximo. |
| `initial_storage_hm3` | `DOUBLE PRECISION` | Si | Almacenamiento inicial. |
| `generation_mode` | `TEXT` | Si | `linear` o `piecewise_linear`. |
| `power_per_flow_mw_per_m3s` | `DOUBLE PRECISION` | No | Requerido en modo `linear`. |
| `turbine_flow_min_m3s` | `DOUBLE PRECISION` | No | Limite inferior opcional. |
| `turbine_flow_max_m3s` | `DOUBLE PRECISION` | No | Requerido en modo `linear`; opcional en `piecewise_linear`. |
| `power_max_mw` | `DOUBLE PRECISION` | No | Limite electrico opcional. |
| `minimum_release_m3s` | `DOUBLE PRECISION` | Si | Default `0`. |
| `spill_penalty_usd_per_hm3` | `DOUBLE PRECISION` | Si | Default `0`. |
| `terminal_condition` | `TEXT` | Si | `none`, `equal_initial`, `min_terminal`. |
| `terminal_storage_min_hm3` | `DOUBLE PRECISION` | No | Requerido si `terminal_condition = min_terminal`. |
| `terminal_water_value_usd_per_hm3` | `DOUBLE PRECISION` | Si | Default `0`. |

Restricciones:

- `UNIQUE (case_id, case_component_id)`.
- `storage_min_hm3 < storage_max_hm3`.
- `storage_min_hm3 <= initial_storage_hm3 <= storage_max_hm3`.
- Campos de costo/valor/release no negativos.
- Validar curvas contra dominios antes de generar `system_case_json`.

### `case_hydro_generation_curve_points`

Breakpoints de generacion hidro en modo `piecewise_linear`.

| Campo | Tipo sugerido | Requerido | Descripcion |
| --- | --- | --- | --- |
| `id` | `BIGSERIAL PK` | Si | Identificador. |
| `case_id` | `BIGINT FK optimization_cases(id)` | Si | Caso. |
| `case_component_id` | `BIGINT FK case_components(id)` | Si | Hydro asociado. |
| `point_index` | `INTEGER` | Si | Orden del breakpoint. |
| `flow_m3s` | `DOUBLE PRECISION` | Si | Caudal. |
| `power_mw` | `DOUBLE PRECISION` | Si | Potencia. |

Restricciones:

- `UNIQUE (case_id, case_component_id, point_index)`.
- `flow_m3s >= 0`.
- `power_mw >= 0`.
- Validacion de aplicacion: `flow_m3s` estrictamente creciente por `point_index`.

### `case_hydro_reservoir_curve_points`

Breakpoints de curva almacenamiento-cota.

| Campo | Tipo sugerido | Requerido | Descripcion |
| --- | --- | --- | --- |
| `id` | `BIGSERIAL PK` | Si | Identificador. |
| `case_id` | `BIGINT FK optimization_cases(id)` | Si | Caso. |
| `case_component_id` | `BIGINT FK case_components(id)` | Si | Hydro asociado. |
| `point_index` | `INTEGER` | Si | Orden del breakpoint. |
| `storage_hm3` | `DOUBLE PRECISION` | Si | Almacenamiento. |
| `elevation_masl` | `DOUBLE PRECISION` | Si | Cota. |

Restricciones:

- `UNIQUE (case_id, case_component_id, point_index)`.
- Validacion de aplicacion: `storage_hm3` estrictamente creciente y
  `elevation_masl` no decreciente.

### `case_parameter_group_hashes`

Guarda hashes por grupo de parametros para invalidar validaciones dependientes
cuando cambia un conjunto de parametros del caso.

| Campo | Tipo sugerido | Requerido | Descripcion |
| --- | --- | --- | --- |
| `id` | `BIGSERIAL PK` | Si | Identificador. |
| `case_id` | `BIGINT FK optimization_cases(id)` | Si | Caso. |
| `parameter_group` | `TEXT` | Si | Ejemplo `battery_parameters`, `hydraulic_unit_parameters`, `solver_settings`. |
| `entity_type` | `TEXT` | No | Tipo de entidad asociada, si aplica. |
| `entity_id` | `BIGINT` | No | ID de entidad asociada, si aplica. |
| `content_hash` | `TEXT` | Si | Hash del grupo serializado canonico. |
| `updated_at` | `TIMESTAMPTZ` | Si | Fecha de recalculo. |
| `updated_by` | `TEXT` | Si | Usuario o servicio. |

Restricciones:

- `UNIQUE (case_id, parameter_group, entity_type, entity_id)`.
- Si cambia cualquier tabla incluida en el grupo, recalcular `content_hash`.
- `validation_dependencies.dependency_type = 'case_parameter_group'` puede
  apuntar a esta tabla.

## Tablas Hidraulicas Futuras

Esta seccion normaliza la red hidraulica futura sin abandonar el supuesto
electrico one-bus. La topologia fisica vive a nivel proyecto y los casos
seleccionan/parametrizan subconjuntos de esa red.

### `hydraulic_systems`

Agrupa una red hidraulica base reutilizable dentro de un proyecto.

| Campo | Tipo sugerido | Requerido | Descripcion |
| --- | --- | --- | --- |
| `id` | `BIGSERIAL PK` | Si | Identificador. |
| `project_id` | `BIGINT FK projects(id)` | Si | Proyecto dueno. |
| `system_key` | `TEXT` | Si | ID estable, por ejemplo `cuenca_laja`. |
| `name` | `TEXT` | Si | Nombre visible. |
| `description` | `TEXT` | No | Descripcion de la red. |
| `metadata_json` | `JSONB` | Si | Datos descriptivos. |
| `is_active` | `BOOLEAN` | Si | Permite retirar sin borrar historia. |
| `created_at` | `TIMESTAMPTZ` | Si | Auditoria. |
| `updated_at` | `TIMESTAMPTZ` | Si | Auditoria. |

Restricciones:

- `UNIQUE (project_id, system_key)`.

### `hydraulic_nodes`

Nodos de la red hidraulica: embalses, uniones, bocatomas, restituciones,
entradas de rio, etc.

| Campo | Tipo sugerido | Requerido | Descripcion |
| --- | --- | --- | --- |
| `id` | `BIGSERIAL PK` | Si | Identificador. |
| `hydraulic_system_id` | `BIGINT FK hydraulic_systems(id)` | Si | Red hidraulica. |
| `node_key` | `TEXT` | Si | ID estable dentro de la red. |
| `node_type` | `TEXT` | Si | `reservoir`, `junction`, `intake`, `tailrace`, `river_inflow`, `other`. |
| `display_name` | `TEXT` | Si | Nombre visible. |
| `official_name` | `TEXT` | No | Nombre oficial si existe. |
| `latitude` | `DOUBLE PRECISION` | No | Coordenada opcional. |
| `longitude` | `DOUBLE PRECISION` | No | Coordenada opcional. |
| `elevation_masl` | `DOUBLE PRECISION` | No | Cota referencial si aplica. |
| `metadata_json` | `JSONB` | Si | Datos de ingenieria o GIS. |
| `is_active` | `BOOLEAN` | Si | Estado del nodo. |

Restricciones:

- `UNIQUE (hydraulic_system_id, node_key)`.
- Parametros especializados de embalse no van aqui; van en tablas por caso.

### `hydraulic_reaches`

Tramos/arcos dirigidos por donde circula agua. Incluye canales, rios, tuneles,
compuertas, bypasses, vertederos y restituciones.

| Campo | Tipo sugerido | Requerido | Descripcion |
| --- | --- | --- | --- |
| `id` | `BIGSERIAL PK` | Si | Identificador. |
| `hydraulic_system_id` | `BIGINT FK hydraulic_systems(id)` | Si | Red hidraulica. |
| `reach_key` | `TEXT` | Si | ID estable. |
| `from_node_id` | `BIGINT FK hydraulic_nodes(id)` | Si | Nodo origen. |
| `to_node_id` | `BIGINT FK hydraulic_nodes(id)` | Si | Nodo destino. |
| `reach_type` | `TEXT` | Si | `river`, `canal`, `tunnel`, `gate`, `spillway`, `bypass`, `tailrace`, `other`. |
| `display_name` | `TEXT` | Si | Nombre visible. |
| `length_km` | `DOUBLE PRECISION` | No | Largo fisico si se conoce. |
| `travel_time_hours` | `DOUBLE PRECISION` | No | Tiempo de viaje fisico. |
| `routing_method` | `TEXT` | Si | `none`, `fixed_delay`, `linear_reservoir`, `custom_curve`. |
| `loss_fraction` | `DOUBLE PRECISION` | No | Perdida proporcional opcional. |
| `is_controllable` | `BOOLEAN` | Si | Si el flujo puede controlarse. |
| `metadata_json` | `JSONB` | Si | Datos de obra/operacion. |
| `is_active` | `BOOLEAN` | Si | Estado del tramo. |

Restricciones:

- `UNIQUE (hydraulic_system_id, reach_key)`.
- `from_node_id <> to_node_id`.
- `travel_time_hours >= 0` si no es `NULL`.
- `0 <= loss_fraction <= 1` si no es `NULL`.

### `hydraulic_plants`

Centrales hidroelectricas como agrupacion de unidades. La potencia efectiva se
modela principalmente a nivel unidad.

| Campo | Tipo sugerido | Requerido | Descripcion |
| --- | --- | --- | --- |
| `id` | `BIGSERIAL PK` | Si | Identificador. |
| `hydraulic_system_id` | `BIGINT FK hydraulic_systems(id)` | Si | Red hidraulica. |
| `plant_key` | `TEXT` | Si | ID estable. |
| `display_name` | `TEXT` | Si | Nombre visible. |
| `official_name` | `TEXT` | No | Nombre oficial. |
| `component_id` | `BIGINT FK components(id)` | No | Componente electrico publico si se expone al one-bus. |
| `latitude` | `DOUBLE PRECISION` | No | Coordenada opcional. |
| `longitude` | `DOUBLE PRECISION` | No | Coordenada opcional. |
| `metadata_json` | `JSONB` | Si | Datos comunes de la central. |
| `is_active` | `BOOLEAN` | Si | Estado. |

Restricciones:

- `UNIQUE (hydraulic_system_id, plant_key)`.

### `hydraulic_units`

Unidades generadoras o de bombeo dentro de una central.

| Campo | Tipo sugerido | Requerido | Descripcion |
| --- | --- | --- | --- |
| `id` | `BIGSERIAL PK` | Si | Identificador. |
| `hydraulic_plant_id` | `BIGINT FK hydraulic_plants(id)` | Si | Central. |
| `unit_key` | `TEXT` | Si | ID estable dentro de la central. |
| `display_name` | `TEXT` | Si | Nombre visible. |
| `unit_capability` | `TEXT` | Si | `generation_only`, `pump_only`, `reversible`. |
| `intake_node_id` | `BIGINT FK hydraulic_nodes(id)` | Si | Nodo de toma. |
| `discharge_node_id` | `BIGINT FK hydraulic_nodes(id)` | Si | Nodo de descarga/restitucion. |
| `turbine_type` | `TEXT` | No | Francis, Pelton, Kaplan, etc. |
| `nameplate_power_mw` | `DOUBLE PRECISION` | No | Potencia nominal. |
| `nameplate_flow_m3s` | `DOUBLE PRECISION` | No | Caudal nominal. |
| `manufacturer` | `TEXT` | No | Fabricante. |
| `commissioning_year` | `INTEGER` | No | Ano de entrada. |
| `metadata_json` | `JSONB` | Si | Datos de ingenieria. |
| `is_active` | `BOOLEAN` | Si | Estado. |

Restricciones:

- `UNIQUE (hydraulic_plant_id, unit_key)`.
- `intake_node_id <> discharge_node_id`.

### `case_hydraulic_systems`

Selecciona una red hidraulica base para un caso.

| Campo | Tipo sugerido | Requerido | Descripcion |
| --- | --- | --- | --- |
| `id` | `BIGSERIAL PK` | Si | Identificador. |
| `case_id` | `BIGINT FK optimization_cases(id)` | Si | Caso. |
| `hydraulic_system_id` | `BIGINT FK hydraulic_systems(id)` | Si | Red base. |
| `enabled` | `BOOLEAN` | Si | Si participa en el caso. |
| `case_label` | `TEXT` | No | Nombre dentro del caso. |
| `metadata_json` | `JSONB` | Si | Metadata del caso. |

Restricciones:

- `UNIQUE (case_id, hydraulic_system_id)`.

### `case_hydraulic_nodes`

Selecciona nodos de la red base para el caso.

| Campo | Tipo sugerido | Requerido | Descripcion |
| --- | --- | --- | --- |
| `id` | `BIGSERIAL PK` | Si | Identificador. |
| `case_id` | `BIGINT FK optimization_cases(id)` | Si | Caso. |
| `hydraulic_node_id` | `BIGINT FK hydraulic_nodes(id)` | Si | Nodo base. |
| `enabled` | `BOOLEAN` | Si | Participa en el caso. |
| `case_label` | `TEXT` | No | Alias en el caso. |
| `sort_order` | `INTEGER` | Si | Orden UI/generacion. |
| `metadata_json` | `JSONB` | Si | Metadata del caso. |

Restricciones:

- `UNIQUE (case_id, hydraulic_node_id)`.

### `case_hydraulic_reservoir_parameters`

Parametros por caso para nodos `reservoir`.

| Campo | Tipo sugerido | Requerido | Descripcion |
| --- | --- | --- | --- |
| `id` | `BIGSERIAL PK` | Si | Identificador. |
| `case_id` | `BIGINT FK optimization_cases(id)` | Si | Caso. |
| `case_hydraulic_node_id` | `BIGINT FK case_hydraulic_nodes(id)` | Si | Nodo embalse del caso. |
| `storage_min_hm3` | `DOUBLE PRECISION` | Si | Almacenamiento minimo. |
| `storage_max_hm3` | `DOUBLE PRECISION` | Si | Almacenamiento maximo. |
| `initial_storage_hm3` | `DOUBLE PRECISION` | Si | Almacenamiento inicial. |
| `dead_storage_hm3` | `DOUBLE PRECISION` | No | Volumen muerto. |
| `usable_storage_hm3` | `DOUBLE PRECISION` | No | Volumen util. |
| `min_operating_elevation_masl` | `DOUBLE PRECISION` | No | Cota operativa minima. |
| `max_operating_elevation_masl` | `DOUBLE PRECISION` | No | Cota operativa maxima. |
| `terminal_condition` | `TEXT` | Si | `none`, `equal_initial`, `min_terminal`. |
| `terminal_storage_min_hm3` | `DOUBLE PRECISION` | No | Requerido si `min_terminal`. |
| `terminal_water_value_usd_per_hm3` | `DOUBLE PRECISION` | Si | Default `0`. |

Restricciones:

- `UNIQUE (case_id, case_hydraulic_node_id)`.
- `storage_min_hm3 < storage_max_hm3`.
- `initial_storage_hm3` dentro de bounds.

### `case_hydraulic_reaches`

Selecciona y parametriza tramos para un caso.

| Campo | Tipo sugerido | Requerido | Descripcion |
| --- | --- | --- | --- |
| `id` | `BIGSERIAL PK` | Si | Identificador. |
| `case_id` | `BIGINT FK optimization_cases(id)` | Si | Caso. |
| `hydraulic_reach_id` | `BIGINT FK hydraulic_reaches(id)` | Si | Tramo base. |
| `enabled` | `BOOLEAN` | Si | Participa en el caso. |
| `case_label` | `TEXT` | No | Alias en el caso. |
| `sort_order` | `INTEGER` | Si | Orden UI/generacion. |
| `flow_min_m3s` | `DOUBLE PRECISION` | No | Limite minimo activo. |
| `flow_max_m3s` | `DOUBLE PRECISION` | No | Limite maximo activo. |
| `travel_time_hours_override` | `DOUBLE PRECISION` | No | Override por caso. |
| `routing_method_override` | `TEXT` | No | Override por caso. |
| `loss_fraction_override` | `DOUBLE PRECISION` | No | Override por caso. |
| `spill_penalty_usd_per_hm3` | `DOUBLE PRECISION` | No | Penalizacion si `reach_type = spillway`. |
| `metadata_json` | `JSONB` | Si | Metadata operacional. |

Restricciones:

- `UNIQUE (case_id, hydraulic_reach_id)`.
- Bounds y costos no negativos cuando aplican.

### `case_hydraulic_plants`

Selecciona centrales y permite limites agregados por caso.

| Campo | Tipo sugerido | Requerido | Descripcion |
| --- | --- | --- | --- |
| `id` | `BIGSERIAL PK` | Si | Identificador. |
| `case_id` | `BIGINT FK optimization_cases(id)` | Si | Caso. |
| `hydraulic_plant_id` | `BIGINT FK hydraulic_plants(id)` | Si | Central base. |
| `enabled` | `BOOLEAN` | Si | Participa en el caso. |
| `case_label` | `TEXT` | No | Alias. |
| `sort_order` | `INTEGER` | Si | Orden. |
| `power_max_mw` | `DOUBLE PRECISION` | No | Limite agregado opcional. |
| `metadata_json` | `JSONB` | Si | Metadata operacional. |

Restricciones:

- `UNIQUE (case_id, hydraulic_plant_id)`.

### `case_hydraulic_units`

Selecciona y parametriza unidades por caso.

| Campo | Tipo sugerido | Requerido | Descripcion |
| --- | --- | --- | --- |
| `id` | `BIGSERIAL PK` | Si | Identificador. |
| `case_id` | `BIGINT FK optimization_cases(id)` | Si | Caso. |
| `hydraulic_unit_id` | `BIGINT FK hydraulic_units(id)` | Si | Unidad base. |
| `enabled` | `BOOLEAN` | Si | Participa en el caso. |
| `case_label` | `TEXT` | No | Alias. |
| `sort_order` | `INTEGER` | Si | Orden. |
| `generation_mode` | `TEXT` | Si | `flow_power_curve`, `head_dependent`. |
| `power_min_mw` | `DOUBLE PRECISION` | No | Potencia minima opcional. |
| `power_max_mw` | `DOUBLE PRECISION` | No | Potencia maxima activa. |
| `turbine_flow_min_m3s` | `DOUBLE PRECISION` | No | Caudal minimo. |
| `turbine_flow_max_m3s` | `DOUBLE PRECISION` | No | Caudal maximo. |
| `minimum_release_m3s` | `DOUBLE PRECISION` | No | Release minimo asociado a unidad si aplica. |
| `metadata_json` | `JSONB` | Si | Metadata operacional. |

Restricciones:

- `UNIQUE (case_id, hydraulic_unit_id)`.
- Bounds no negativos y coherentes.

### `hydraulic_curve_sets`

Curvas hidraulicas versionadas y reutilizables.

| Campo | Tipo sugerido | Requerido | Descripcion |
| --- | --- | --- | --- |
| `id` | `BIGSERIAL PK` | Si | Identificador. |
| `project_id` | `BIGINT FK projects(id)` | Si | Proyecto. |
| `entity_type` | `TEXT` | Si | `hydraulic_node`, `hydraulic_reach`, `hydraulic_unit`, etc. |
| `entity_id` | `BIGINT` | Si | Entidad base. |
| `curve_key` | `TEXT` | Si | `storage_elevation`, `storage_area`, `flow_power`, `flow_head_efficiency`. |
| `version_number` | `INTEGER` | Si | Version incremental. |
| `version_label` | `TEXT` | Si | Etiqueta humana. |
| `curve_dimension` | `INTEGER` | Si | `1` o `2`. |
| `axis_x_name` | `TEXT` | Si | Ejemplo `storage_hm3` o `flow_m3s`. |
| `axis_x_unit` | `TEXT` | Si | Unidad eje x. |
| `axis_y_name` | `TEXT` | Si | Ejemplo `elevation_masl`, `power_mw`, `efficiency`. |
| `axis_y_unit` | `TEXT` | Si | Unidad eje y. |
| `axis_z_name` | `TEXT` | No | Para 2D, ejemplo `net_head_m`. |
| `axis_z_unit` | `TEXT` | No | Unidad eje z. |
| `content_hash` | `TEXT` | No | Hash de puntos vigentes. |
| `source_id` | `BIGINT FK time_series_sources(id)` | No | Fuente documental si aplica. |
| `status` | `TEXT` | Si | `draft`, `validated`, `archived`. |

Restricciones:

- `UNIQUE (project_id, entity_type, entity_id, curve_key, version_number)`.
- `UNIQUE (project_id, entity_type, entity_id, curve_key, version_label)`.

### `hydraulic_curve_points`

Puntos de curvas 1D o superficies 2D.

| Campo | Tipo sugerido | Requerido | Descripcion |
| --- | --- | --- | --- |
| `id` | `BIGSERIAL PK` | Si | Identificador. |
| `hydraulic_curve_set_id` | `BIGINT FK hydraulic_curve_sets(id)` | Si | Curva. |
| `point_index` | `INTEGER` | Si | Orden. |
| `x_value` | `DOUBLE PRECISION` | Si | Eje x. |
| `y_value` | `DOUBLE PRECISION` | Si | Eje y. |
| `z_value` | `DOUBLE PRECISION` | No | Segundo eje independiente para 2D. |
| `metadata_json` | `JSONB` | Si | Metadata de punto. |

Restricciones:

- `UNIQUE (hydraulic_curve_set_id, point_index)`.
- Validaciones por `curve_key`: monotonia, no negatividad y dominio.

### `case_hydraulic_curve_bindings`

Elige que version de curva usa un caso.

| Campo | Tipo sugerido | Requerido | Descripcion |
| --- | --- | --- | --- |
| `id` | `BIGSERIAL PK` | Si | Identificador. |
| `case_id` | `BIGINT FK optimization_cases(id)` | Si | Caso. |
| `entity_type` | `TEXT` | Si | `case_hydraulic_node`, `case_hydraulic_reach`, `case_hydraulic_plant`, `case_hydraulic_unit`. |
| `entity_id` | `BIGINT` | Si | ID de la entidad activa del caso segun `entity_type`. |
| `curve_role` | `TEXT` | Si | `storage_elevation`, `storage_area`, `flow_power`, `head_efficiency`, etc. |
| `hydraulic_curve_set_id` | `BIGINT FK hydraulic_curve_sets(id)` | Si | Curva versionada. |
| `required` | `BOOLEAN` | Si | Si es obligatoria. |

Restricciones:

- `UNIQUE (case_id, entity_type, entity_id, curve_role)`.
- Validar integridad de `entity_id` por aplicacion o triggers.
- Validar que `hydraulic_curve_sets.entity_type` y `hydraulic_curve_sets.entity_id`
  sean compatibles con el objeto fisico base resuelto desde la entidad activa
  del caso. Ejemplo: `case_hydraulic_units.hydraulic_unit_id` debe coincidir
  con una curva `hydraulic_curve_sets.entity_type = 'hydraulic_unit'`.

### `availability_events`

Eventos auditables de mantenimiento, falla o restriccion a nivel proyecto.
Representan hechos, planes o condiciones operacionales reutilizables; no son el
input directo del optimizador. La corrida consume una serie derivada versionada
o la copia materializada dentro de `scenario_versions`.

| Campo | Tipo sugerido | Requerido | Descripcion |
| --- | --- | --- | --- |
| `id` | `BIGSERIAL PK` | Si | Identificador. |
| `project_id` | `BIGINT FK projects(id)` | Si | Proyecto. |
| `entity_type` | `TEXT` | Si | `hydraulic_unit`, `hydraulic_plant`, `hydraulic_reach`, `hydraulic_node`, `hydraulic_system`, `component`. |
| `entity_id` | `BIGINT` | Si | Entidad afectada. |
| `event_type` | `TEXT` | Si | `maintenance`, `forced_outage`, `restriction`, `derating`, `other`. |
| `status` | `TEXT` | Si | `planned`, `active`, `closed`, `cancelled`. |
| `starts_at` | `TIMESTAMPTZ` | Si | Inicio. |
| `ends_at` | `TIMESTAMPTZ` | Si | Termino. |
| `availability_factor` | `DOUBLE PRECISION` | No | Factor resultante si aplica. |
| `capacity_limit_mw` | `DOUBLE PRECISION` | No | Limite de potencia si aplica. |
| `flow_limit_m3s` | `DOUBLE PRECISION` | No | Limite de caudal si aplica. |
| `reason` | `TEXT` | No | Causa. |
| `source_reference` | `TEXT` | No | Documento/ticket/fuente. |
| `metadata_json` | `JSONB` | Si | Detalle adicional. |
| `created_at` | `TIMESTAMPTZ` | Si | Auditoria. |
| `updated_at` | `TIMESTAMPTZ` | Si | Auditoria. |
| `created_by` | `TEXT` | Si | Usuario o servicio. |
| `updated_by` | `TEXT` | Si | Usuario o servicio. |

Restricciones:

- `starts_at < ends_at`.
- Validar integridad de `entity_id` por aplicacion o triggers.
- El generador debe transformar los eventos aplicables a series como
  `unit_availability_factor`, `unit_capacity_limit_mw` o
  `reach_flow_limit_m3s`.
- Para una corrida, considerar solo eventos compatibles con la red activa del
  caso, la variante de series y el horizonte temporal ejecutado.
- Los eventos `cancelled` no participan en la derivacion. Eventos `planned`,
  `active` o `closed` pueden participar si intersectan el horizonte objetivo;
  `closed` permite reconstruir disponibilidad historica.
- Si varios eventos aplican al mismo periodo y entidad, la derivacion usa el
  valor mas restrictivo: `MIN(availability_factor)`, `MIN(capacity_limit_mw)`
  y `MIN(flow_limit_m3s)` ignorando valores `NULL`. Si todos los valores de un
  limite son `NULL`, se usa el limite base del caso.

### `availability_event_time_series_links`

Relaciona eventos de disponibilidad con las senales versionadas generadas desde
ellos. Es una tabla de trazabilidad, no una tabla de valores.

| Campo | Tipo sugerido | Requerido | Descripcion |
| --- | --- | --- | --- |
| `id` | `BIGSERIAL PK` | Si | Identificador. |
| `availability_event_id` | `BIGINT FK availability_events(id)` | Si | Evento origen. |
| `time_series_signal_id` | `BIGINT FK time_series_signals(id)` | Si | Senal derivada. |
| `derived_signal_key` | `TEXT` | Si | Senal generada, por ejemplo `unit_availability_factor`, `unit_capacity_limit_mw` o `reach_flow_limit_m3s`. |
| `derivation_method` | `TEXT` | Si | `step_factor`, `capacity_limit`, `flow_limit`, `custom_rule`, etc. |
| `event_hash_at_derivation` | `TEXT` | No | Hash del evento usado al generar la senal, para detectar stale si el evento cambia. |
| `metadata_json` | `JSONB` | Si | Detalle de regla, prioridad, clipping o combinacion de eventos. |
| `created_at` | `TIMESTAMPTZ` | Si | Auditoria. |
| `created_by` | `TEXT` | Si | Usuario o servicio. |

Restricciones:

- `UNIQUE (availability_event_id, time_series_signal_id, derived_signal_key)`.
- La senal derivada debe pertenecer a un `time_series_set` versionado.
- Si cambia el evento origen, el link no se reescribe automaticamente; queda
  como evidencia historica y la UI debe advertir que la serie derivada puede
  estar stale si `event_hash_at_derivation` ya no coincide.

## Series De Tiempo Versionadas

### Decisiones De Modelado

- Un `time_series_set` representa un conjunto reutilizable de periodos y
  senales alineadas.
- La version requerida por el usuario queda en `time_series_sets` como
  `version_number` y `version_label`.
- Una serie puede ser `real`, `programmed`, `forecast`, `simulated`,
  `synthetic` o `mixed`. Para el requerimiento actual bastan `real`,
  `programmed` y `simulated`, pero conviene dejar el enum abierto por migracion
  futura.
- Las series simuladas pueden venir de una corrida (`source_run_id`) o de una
  fuente externa.
- Los valores se guardan en formato long: periodo + senal + valor. Esto evita
  crear una tabla distinta por cada CSV.

### `time_series_sources`

Registra procedencia de datos: CSV, XLSX, API, manual, artefacto de corrida o
simulacion externa.

| Campo | Tipo sugerido | Requerido | Descripcion |
| --- | --- | --- | --- |
| `id` | `BIGSERIAL PK` | Si | Identificador. |
| `project_id` | `BIGINT FK projects(id)` | Si | Proyecto. |
| `source_kind` | `TEXT` | Si | `csv`, `xlsx`, `manual`, `api`, `artifact`, `simulation`. |
| `original_filename` | `TEXT` | No | Nombre original si aplica. |
| `stored_object_key` | `TEXT` | No | Ruta/clave segura, no path absoluto expuesto. |
| `media_type` | `TEXT` | No | MIME type. |
| `checksum_sha256` | `TEXT` | No | Deduplicacion/auditoria. |
| `sheet_name` | `TEXT` | No | Hoja XLSX usada. |
| `source_run_id` | `BIGINT FK runs(id)` | No | Corrida origen si la serie viene de resultados simulados. |
| `issuer_name` | `TEXT` | No | Entidad emisora, por ejemplo CEN, cliente, operador o planificador interno. |
| `issuer_type` | `TEXT` | No | `market_operator`, `client`, `internal`, `external_model`, `other`. |
| `issued_at` | `TIMESTAMPTZ` | No | Momento en que se emitio/publico la informacion. |
| `valid_from` | `TIMESTAMPTZ` | No | Inicio de vigencia del programa o plan. |
| `valid_to` | `TIMESTAMPTZ` | No | Fin de vigencia del programa o plan. |
| `source_reference` | `TEXT` | No | ID de documento, resolucion, URL, ticket, nombre de corrida externa, etc. |
| `metadata_json` | `JSONB` | Si | Datos de importacion. |
| `created_at` | `TIMESTAMPTZ` | Si | Auditoria. |
| `created_by` | `TEXT` | Si | Usuario o servicio. |

### `time_series_sets`

Version reutilizable del set completo de series.

Uso principal: permitir cambiar rapidamente entre versiones de series de
tiempo, por ejemplo `real_2026_v1`, `programmed_dispatch_cen_v1`,
`forecast_2026_high_inflow`, `simulated_run_42` o `stress_dry_year`,
manteniendo el resto del caso igual cuando corresponda.

| Campo | Tipo sugerido | Requerido | Descripcion |
| --- | --- | --- | --- |
| `id` | `BIGSERIAL PK` | Si | Identificador. |
| `project_id` | `BIGINT FK projects(id)` | Si | Proyecto propietario. |
| `name` | `TEXT` | Si | Nombre del set, por ejemplo `jan_2026_real_inputs`. |
| `version_number` | `INTEGER` | Si | Version incremental por `(project_id, name)`. |
| `version_label` | `TEXT` | Si | Etiqueta humana reutilizable: `v1`, `2026-01-final`, `sim-run-42`, etc. |
| `data_kind` | `TEXT` | Si | `real`, `programmed`, `forecast`, `simulated`, `synthetic`, `mixed`. |
| `source_id` | `BIGINT FK time_series_sources(id)` | No | Fuente principal. |
| `source_run_id` | `BIGINT FK runs(id)` | No | Corrida origen para outputs simulados. |
| `timezone` | `TEXT` | Si | Ejemplo `America/Santiago` o `UTC`. |
| `timestamp_convention` | `TEXT` | Si | Default `period_start`. |
| `status` | `TEXT` | Si | `draft`, `validated`, `archived`. |
| `validation_payload_json` | `JSONB` | Si | Resultado de validacion. |
| `description` | `TEXT` | No | Notas. |
| `content_hash` | `TEXT` | No | Hash del contenido vigente para detectar cambios. |
| `created_at` | `TIMESTAMPTZ` | Si | Auditoria. |
| `updated_at` | `TIMESTAMPTZ` | Si | Auditoria de ultima edicion. |
| `created_by` | `TEXT` | Si | Usuario o servicio. |
| `updated_by` | `TEXT` | Si | Usuario o servicio que edito por ultima vez. |

Restricciones:

- `UNIQUE (project_id, name, version_number)`.
- `UNIQUE (project_id, name, version_label)`.
- `version_number` y `version_label` identifican el set versionado editable.
- Si cambia el contenido, actualizar `updated_at`, `updated_by` y
  `content_hash`.
- Las `scenario_versions` ya promovidas no deben depender del contenido mutable
  vigente del set, sino del snapshot o hash congelado al momento de promocion.

### `time_series_set_revisions`

Historial liviano de ediciones sobre un set versionado editable.

| Campo | Tipo sugerido | Requerido | Descripcion |
| --- | --- | --- | --- |
| `id` | `BIGSERIAL PK` | Si | Identificador. |
| `time_series_set_id` | `BIGINT FK time_series_sets(id)` | Si | Set editado. |
| `revision_number` | `INTEGER` | Si | Revision incremental dentro del set. |
| `content_hash` | `TEXT` | Si | Hash del contenido despues de la edicion. |
| `change_summary` | `TEXT` | No | Resumen humano de la edicion. |
| `source_id` | `BIGINT FK time_series_sources(id)` | No | Fuente o snapshot asociado a la revision. |
| `created_at` | `TIMESTAMPTZ` | Si | Fecha de revision. |
| `created_by` | `TEXT` | Si | Usuario o servicio. |

Restricciones:

- `UNIQUE (time_series_set_id, revision_number)`.
- El `content_hash` de `time_series_sets` debe coincidir con la ultima revision.

### `time_series_periods`

Horizonte comun del set.

| Campo | Tipo sugerido | Requerido | Descripcion |
| --- | --- | --- | --- |
| `id` | `BIGSERIAL PK` | Si | Identificador. |
| `time_series_set_id` | `BIGINT FK time_series_sets(id)` | Si | Set. |
| `period_index` | `INTEGER` | Si | Orden desde 1. |
| `timestamp_start` | `TIMESTAMPTZ` | Si | Inicio del periodo. |
| `timestamp_end` | `TIMESTAMPTZ` | Si | Fin exclusivo del periodo. |
| `duration_hours` | `DOUBLE PRECISION` | Si | Duracion del periodo. |

Restricciones:

- `UNIQUE (time_series_set_id, period_index)`.
- `UNIQUE (time_series_set_id, timestamp_start)`.
- `timestamp_start < timestamp_end`.
- `duration_hours > 0`.
- Validacion: `timestamp_start` y `timestamp_end` estrictamente ordenados por
  `period_index`, sin traslapes dentro del mismo set.
- `duration_hours` debe coincidir con la diferencia entre `timestamp_start` y
  `timestamp_end` en horas, dentro de una tolerancia numerica definida por el
  backend.
- El valor de `timezone` en `time_series_sets` debe ser un identificador IANA
  valido, por ejemplo `America/Santiago`. Los timestamps se guardan como
  instantes absolutos; `timezone` se usa para interpretar/importar/mostrar el
  calendario local.

### `time_series_signals`

Define una senal dentro del set. Puede ser global o asociada a un objeto del
modelo, incluyendo componentes generales y objetos hidraulicos internos.

| Campo | Tipo sugerido | Requerido | Descripcion |
| --- | --- | --- | --- |
| `id` | `BIGSERIAL PK` | Si | Identificador. |
| `time_series_set_id` | `BIGINT FK time_series_sets(id)` | Si | Set. |
| `entity_type` | `TEXT` | No | `component`, `hydraulic_node`, `hydraulic_reach`, `hydraulic_plant`, `hydraulic_unit`; `NULL` para senales globales. |
| `entity_id` | `BIGINT` | No | ID de la entidad segun `entity_type`; `NULL` para senales globales. |
| `signal_key` | `TEXT` | Si | Ejemplo `import_price_usd_per_mwh`, `hydro_inflow_m3s`. |
| `signal_role` | `TEXT` | Si | `input`, `output`, `metadata`. |
| `unit` | `TEXT` | Si | `MW`, `MWh`, `USD/MWh`, `m3/s`, `hm3`, etc. |
| `data_kind` | `TEXT` | No | Override si el set es `mixed`. |
| `aggregation` | `TEXT` | Si | `period_average`, `period_sum`, `end_of_period`, etc. |
| `metadata_json` | `JSONB` | Si | Cualquier dato auxiliar. |

Restricciones:

- `UNIQUE (time_series_set_id, entity_type, entity_id, signal_key)`.
- Si `entity_type IS NULL`, entonces `entity_id IS NULL`.
- Si `entity_type IS NOT NULL`, entonces `entity_id IS NOT NULL`.
- La integridad de `entity_id` debe validarse en aplicacion o con triggers por
  tipo de entidad, porque SQL no permite una FK dinamica simple.

Senales input esperadas inicialmente:

| `signal_key` | Entidad | Unidad |
| --- | --- | --- |
| `price_usd_per_mwh` | Global | `USD/MWh` |
| `import_price_usd_per_mwh` | Global | `USD/MWh` |
| `export_price_usd_per_mwh` | Global | `USD/MWh` |
| `renewable_available_power_mw` | `component:renewable` | `MW` |
| `load_demand_mw` | `component:load` | `MW` |
| `natural_inflow_m3s` | `hydraulic_node` | `m3/s` |
| `observed_reach_flow_m3s` | `hydraulic_reach` | `m3/s` |
| `unit_availability_factor` | `hydraulic_unit` | `p.u.` |

Senales output simuladas recomendadas si se decide indexar resultados en DB:

| `signal_key` | Entidad | Unidad |
| --- | --- | --- |
| `p_grid_import_mw` | `component:grid` | `MW` |
| `p_grid_export_mw` | `component:grid` | `MW` |
| `p_battery_charge_mw` | `component:battery` | `MW` |
| `p_battery_discharge_mw` | `component:battery` | `MW` |
| `energy_mwh` | `component:battery` | `MWh` |
| `p_renewable_used_mw` | `component:renewable` | `MW` |
| `p_renewable_curtailed_mw` | `component:renewable` | `MW` |
| `load_demand_mw` | `component:load` | `MW` |
| `hydro_power_mw` | `hydraulic_unit` o `hydraulic_plant` | `MW` |
| `hydro_turbine_flow_m3s` | `hydraulic_unit` | `m3/s` |
| `hydraulic_reach_flow_m3s` | `hydraulic_reach` | `m3/s` |
| `hydro_storage_hm3` | `hydraulic_node:reservoir` | `hm3` |
| `hydro_reservoir_elevation_masl` | `hydraulic_node:reservoir` | `masl` |

### `time_series_values`

Valores numericos por senal y periodo.

| Campo | Tipo sugerido | Requerido | Descripcion |
| --- | --- | --- | --- |
| `id` | `BIGSERIAL PK` | Si | Identificador. |
| `time_series_set_id` | `BIGINT FK time_series_sets(id)` | Si | Set denormalizado para particion, borrado y consultas eficientes. |
| `time_series_signal_id` | `BIGINT FK time_series_signals(id)` | Si | Senal. |
| `time_series_period_id` | `BIGINT FK time_series_periods(id)` | Si | Periodo. |
| `value_numeric` | `DOUBLE PRECISION` | Si | Valor numerico canonico. |
| `quality_flag` | `TEXT` | No | `measured`, `estimated`, `filled`, `simulated`, etc. |
| `source_row_number` | `INTEGER` | No | Fila de archivo origen. |
| `metadata_json` | `JSONB` | Si | Detalle de calidad/procedencia. |

Restricciones:

- `UNIQUE (time_series_set_id, time_series_signal_id, time_series_period_id)`.
- `time_series_signal_id` y `time_series_period_id` deben pertenecer al mismo
  `time_series_set_id`; validar con constraints compuestas, triggers o
  aplicacion.
- Validaciones por `signal_key`: no negativos para disponibilidad renovable,
  demanda e inflow hidro.

Estrategia fisica recomendada:

- MVP: tabla long normal en PostgreSQL, con bulk insert por set y lectura por
  `time_series_set_id`, `time_series_signal_id` y `period_index`.
- Mantener `time_series_set_id` en `time_series_values` aunque sea derivable
  desde senal/periodo, porque simplifica particionamiento, borrado de un set y
  control de consistencia.
- Si el volumen crece, particionar `time_series_values` por
  `time_series_set_id`, por hash de set o por rango temporal segun el patron de
  consultas real.
- TimescaleDB/hypertables es una optimizacion posible, no requisito del modelo.
- Para sets enormes o outputs simulados no reutilizables, conservar artefactos
  externos y cargar a BBDD solo senales marcadas como reutilizables,
  comparables o publicables.

### `time_series_import_mappings`

Guarda como se transformo una fuente tabular en senales.

| Campo | Tipo sugerido | Requerido | Descripcion |
| --- | --- | --- | --- |
| `id` | `BIGSERIAL PK` | Si | Identificador. |
| `source_id` | `BIGINT FK time_series_sources(id)` | Si | Fuente. |
| `time_series_set_id` | `BIGINT FK time_series_sets(id)` | Si | Set generado. |
| `entity_type` | `TEXT` | No | `component`, `hydraulic_node`, `hydraulic_reach`, `hydraulic_plant`, `hydraulic_unit`; `NULL` para senales globales. |
| `entity_id` | `BIGINT` | No | ID de la entidad segun `entity_type`; `NULL` para senales globales. |
| `signal_key` | `TEXT` | Si | Senal destino. |
| `source_column` | `TEXT` | Si | Columna fuente. |
| `source_unit` | `TEXT` | No | Unidad original si se conoce. |
| `target_unit` | `TEXT` | Si | Unidad canonica guardada. |
| `transform_json` | `JSONB` | Si | Conversiones, scaling, parse rules. |
| `created_at` | `TIMESTAMPTZ` | Si | Auditoria. |

Restricciones:

- Si `entity_type IS NULL`, entonces `entity_id IS NULL`.
- Si `entity_type IS NOT NULL`, entonces `entity_id IS NOT NULL`.
- La integridad de `entity_id` debe validarse con la misma logica usada para
  `time_series_signals`.

### `time_series_transformations`

Transformaciones declarativas versionadas entre sets de series. Se usan para
resampling, interpolacion, escalamiento, combinacion de escenarios o derivacion
de un set nuevo desde uno o mas sets origen. No guardan scripts libres como
fuente primaria de la transformacion.

| Campo | Tipo sugerido | Requerido | Descripcion |
| --- | --- | --- | --- |
| `id` | `BIGSERIAL PK` | Si | Identificador. |
| `project_id` | `BIGINT FK projects(id)` | Si | Proyecto. |
| `transformation_key` | `TEXT` | Si | ID estable, por ejemplo `resample_hourly_to_daily_v1`. |
| `transformation_type` | `TEXT` | Si | `resample`, `interpolate`, `scale`, `combine_sets`, `derive_availability`, `custom_allowlisted`. |
| `input_time_series_set_ids_json` | `JSONB` | Si | Lista ordenada de sets origen y roles. |
| `output_time_series_set_id` | `BIGINT FK time_series_sets(id)` | Si | Set generado. |
| `implementation_version` | `TEXT` | Si | Version del algoritmo allowlisted usado. |
| `parameter_schema_version` | `TEXT` | Si | Version del esquema de parametros. |
| `parameters_json` | `JSONB` | Si | Parametros declarativos de la transformacion. |
| `content_hash` | `TEXT` | No | Hash de inputs, parametros y version de implementacion. |
| `status` | `TEXT` | Si | `draft`, `validated`, `archived`. |
| `created_at` | `TIMESTAMPTZ` | Si | Auditoria. |
| `updated_at` | `TIMESTAMPTZ` | Si | Auditoria. |
| `created_by` | `TEXT` | Si | Usuario o servicio. |
| `updated_by` | `TEXT` | Si | Usuario o servicio. |

Restricciones:

- `UNIQUE (project_id, transformation_key)`.
- `output_time_series_set_id` debe pertenecer al mismo proyecto.
- Todos los sets origen deben pertenecer al mismo proyecto o estar
  explicitamente autorizados para reutilizacion.
- El backend debe validar `parameters_json` contra el contrato de
  `transformation_type`, `implementation_version` y
  `parameter_schema_version`.

## Binding Entre Casos Y Series

### `case_input_variants`

Define una variante reutilizable de insumos para un `optimization_case`. Sirve
para cambiar versiones de series de tiempo sin duplicar todos los parametros del
caso.

| Campo | Tipo sugerido | Requerido | Descripcion |
| --- | --- | --- | --- |
| `id` | `BIGSERIAL PK` | Si | Identificador. |
| `case_id` | `BIGINT FK optimization_cases(id)` | Si | Caso base. |
| `parent_variant_id` | `BIGINT FK case_input_variants(id)` | No | Variante base desde la cual heredar bindings. |
| `variant_key` | `TEXT` | Si | ID estable, por ejemplo `real_2026_v1` o `dry_year_stress_v1`. |
| `name` | `TEXT` | Si | Nombre visible. |
| `description` | `TEXT` | No | Notas de la variante. |
| `status` | `TEXT` | Si | `draft`, `validated`, `archived`. |
| `validation_payload_json` | `JSONB` | Si | Validacion de compatibilidad de series. |
| `created_at` | `TIMESTAMPTZ` | Si | Auditoria. |
| `updated_at` | `TIMESTAMPTZ` | Si | Auditoria. |
| `created_by` | `TEXT` | Si | Usuario o servicio. |
| `updated_by` | `TEXT` | Si | Usuario o servicio. |

Restricciones:

- `UNIQUE (case_id, variant_key)`.
- La variante debe validar que todos los bindings requeridos existan y que los
  horizontes de series sean compatibles.

### `validation_dependencies`

Guarda hashes o versiones de dependencias usadas en la ultima validacion de un
objeto validable. Sirve para detectar si una variante, restriccion o termino de
objetivo quedo stale despues de editar series, curvas o parametros.

| Campo | Tipo sugerido | Requerido | Descripcion |
| --- | --- | --- | --- |
| `id` | `BIGSERIAL PK` | Si | Identificador. |
| `owner_type` | `TEXT` | Si | `case_input_variant`, `case_constraint_binding`, `case_objective_term_binding`, `time_series_set`, `time_series_signal`. |
| `owner_id` | `BIGINT` | Si | ID del objeto owner segun `owner_type`. |
| `dependency_type` | `TEXT` | Si | `time_series_set`, `time_series_signal`, `hydraulic_curve_set`, `availability_event`, `case_parameter_group`. |
| `dependency_id` | `BIGINT` | Si | ID del objeto dependiente segun `dependency_type`. |
| `content_hash_at_validation` | `TEXT` | No | Hash al validar, si aplica. |
| `version_label_at_validation` | `TEXT` | No | Version label al validar, si aplica. |
| `revision_number_at_validation` | `INTEGER` | No | Revision al validar, si aplica. |
| `validated_at` | `TIMESTAMPTZ` | Si | Fecha de validacion. |

Restricciones:

- `UNIQUE (owner_type, owner_id, dependency_type, dependency_id)`.
- Validar integridad de `owner_id` y `dependency_id` por aplicacion o triggers.
- Si el hash/version/revision actual no coincide, el owner requiere
  revalidacion.
- Una serie derivada desde `availability_events` puede registrarse como
  `owner_type = 'time_series_signal'` y `dependency_type =
  'availability_event'` para detectar si debe regenerarse.

### `case_time_series_bindings`

Conecta un caso con las series que debe usar. Permite reutilizar la misma
version de series en muchos casos.

| Campo | Tipo sugerido | Requerido | Descripcion |
| --- | --- | --- | --- |
| `id` | `BIGSERIAL PK` | Si | Identificador. |
| `case_id` | `BIGINT FK optimization_cases(id)` | Si | Caso. |
| `case_input_variant_id` | `BIGINT FK case_input_variants(id)` | No | Variante de series; `NULL` para binding default del caso. |
| `entity_type` | `TEXT` | No | `case_component`, `case_hydraulic_node`, `case_hydraulic_reach`, `case_hydraulic_plant`, `case_hydraulic_unit`; `NULL` para senales globales. |
| `entity_id` | `BIGINT` | No | ID de la entidad activa del caso segun `entity_type`; `NULL` para senales globales. |
| `signal_key` | `TEXT` | Si | Senal requerida. |
| `binding_action` | `TEXT` | Si | `set` para asignar serie; `unset` para desactivar binding heredado. |
| `time_series_set_id` | `BIGINT FK time_series_sets(id)` | No | Set versionado reutilizable; requerido si `binding_action = set`. |
| `time_series_signal_id` | `BIGINT FK time_series_signals(id)` | No | Senal concreta dentro del set; requerida si `binding_action = set`. |
| `required` | `BOOLEAN` | Si | Si debe existir para generar el caso. |
| `binding_role` | `TEXT` | Si | `optimization_input`, `baseline`, `target`, `comparison`, `output_reference`. |
| `created_at` | `TIMESTAMPTZ` | Si | Auditoria. |
| `created_by` | `TEXT` | Si | Usuario o servicio. |

Restricciones:

- `UNIQUE (case_id, case_input_variant_id, entity_type, entity_id, signal_key, binding_role)`.
- Si `entity_type IS NULL`, entonces `entity_id IS NULL`.
- Si `entity_type IS NOT NULL`, entonces `entity_id IS NOT NULL`.
- Si `binding_action = 'unset'`, `time_series_set_id` y
  `time_series_signal_id` deben ser `NULL`.
- Si `binding_action = 'set'`, `time_series_set_id` y
  `time_series_signal_id` deben existir.
- Si `time_series_signal_id` apunta a una entidad base, debe ser compatible con
  la entidad activa del caso. Ejemplo: si `entity_type =
  'case_hydraulic_node'`, entonces `entity_id` apunta a
  `case_hydraulic_nodes.id`; esa fila debe resolver a
  `time_series_signals.entity_type = 'hydraulic_node'` y al
  `case_hydraulic_nodes.hydraulic_node_id` base correspondiente.
- Validacion: todas las senales `optimization_input` deben compartir horizonte
  compatible.

## Mapeo De Restricciones Especificas A Julia

Para restricciones especificas por caso, no conviene guardar codigo Julia
arbitrario en la BBDD. La BBDD debe guardar **que restriccion se activa, con que
parametros, sobre que entidades y con que version de modulo Julia**. El codigo
vive en el repositorio y se versiona con git.

Flujo recomendado:

```text
constraint_definitions
  -> case_constraint_bindings
    -> case_constraint_entity_bindings
    -> case_constraint_time_series_bindings
  -> generador Python/Julia
  -> system_case_json + constraint payload
  -> script/modulo Julia allowlisted
```

### `constraint_definitions`

Catalogo allowlisted de restricciones soportadas por el sistema.

| Campo | Tipo sugerido | Requerido | Descripcion |
| --- | --- | --- | --- |
| `id` | `BIGSERIAL PK` | Si | Identificador. |
| `constraint_key` | `TEXT` | Si | Nombre estable, por ejemplo `reservoir_min_final_storage`. |
| `display_name` | `TEXT` | Si | Nombre visible. |
| `description` | `TEXT` | No | Explicacion funcional. |
| `domain` | `TEXT` | Si | `battery`, `grid`, `hydraulic`, `economic`, `custom_case`. |
| `julia_module` | `TEXT` | Si | Modulo o archivo allowlisted, por ejemplo `HydroConstraints`. |
| `julia_function` | `TEXT` | Si | Funcion que agrega la restriccion al modelo. |
| `implementation_version` | `TEXT` | Si | Version semantica del contrato de la restriccion. |
| `parameter_schema_version` | `TEXT` | Si | Version del esquema de parametros esperado por `schema_json`. |
| `schema_json` | `JSONB` | Si | Esquema de parametros esperados. |
| `supported_schema_versions_json` | `JSONB` | Si | Versiones de `system_case` compatibles. |
| `is_active` | `BOOLEAN` | Si | Permite retirar restricciones sin borrar historia. |
| `created_at` | `TIMESTAMPTZ` | Si | Auditoria. |
| `updated_at` | `TIMESTAMPTZ` | Si | Auditoria. |

Restricciones:

- `UNIQUE (constraint_key, implementation_version, parameter_schema_version)`.
- No ejecutar scripts fuera de este catalogo.

### `case_constraint_bindings`

Activa una restriccion especifica en un caso.

| Campo | Tipo sugerido | Requerido | Descripcion |
| --- | --- | --- | --- |
| `id` | `BIGSERIAL PK` | Si | Identificador. |
| `case_id` | `BIGINT FK optimization_cases(id)` | Si | Caso. |
| `constraint_definition_id` | `BIGINT FK constraint_definitions(id)` | Si | Restriccion del catalogo. |
| `binding_key` | `TEXT` | Si | ID estable dentro del caso, por ejemplo `min_final_laja`. |
| `enabled` | `BOOLEAN` | Si | Activa/desactiva sin borrar. |
| `severity` | `TEXT` | Si | `hard`, `soft`, `report_only`. |
| `priority_order` | `INTEGER` | Si | Orden de aplicacion si importa. |
| `parameter_values_json` | `JSONB` | Si | Parametros simples del binding. |
| `validation_payload_json` | `JSONB` | Si | Resultado de validacion. |
| `created_at` | `TIMESTAMPTZ` | Si | Auditoria. |
| `updated_at` | `TIMESTAMPTZ` | Si | Auditoria. |
| `created_by` | `TEXT` | Si | Usuario o servicio. |
| `updated_by` | `TEXT` | Si | Usuario o servicio. |

Restricciones:

- `UNIQUE (case_id, binding_key)`.
- Validar `parameter_values_json` contra `constraint_definitions.schema_json`
  antes de promover el caso.

### `case_constraint_entity_bindings`

Mapea la restriccion a objetos concretos activos dentro del caso.

| Campo | Tipo sugerido | Requerido | Descripcion |
| --- | --- | --- | --- |
| `id` | `BIGSERIAL PK` | Si | Identificador. |
| `case_constraint_binding_id` | `BIGINT FK case_constraint_bindings(id)` | Si | Binding de restriccion. |
| `role_key` | `TEXT` | Si | Rol esperado por la restriccion: `reservoir`, `unit`, `reach`, `source_node`, `sink_node`, etc. |
| `entity_type` | `TEXT` | Si | `case_component`, `case_hydraulic_node`, `case_hydraulic_reach`, `case_hydraulic_plant`, `case_hydraulic_unit`, etc. |
| `entity_id` | `BIGINT` | Si | ID de la entidad activa del caso segun `entity_type`. |
| `metadata_json` | `JSONB` | Si | Datos auxiliares. |

Restricciones:

- `UNIQUE (case_constraint_binding_id, role_key, entity_type, entity_id)`.
- Validar integridad de `entity_id` por aplicacion o triggers.
- Si la restriccion requiere atributos fisicos base, el generador debe
  resolverlos desde la entidad activa del caso. Ejemplo:
  `entity_type = 'case_hydraulic_unit'` y `entity_id =
  case_hydraulic_units.id`; desde esa fila se obtiene `hydraulic_unit_id`.

### `case_constraint_time_series_bindings`

Mapea restricciones que requieren series, por ejemplo caudales minimos,
disponibilidad o limites variables.

| Campo | Tipo sugerido | Requerido | Descripcion |
| --- | --- | --- | --- |
| `id` | `BIGSERIAL PK` | Si | Identificador. |
| `case_constraint_binding_id` | `BIGINT FK case_constraint_bindings(id)` | Si | Binding. |
| `role_key` | `TEXT` | Si | Ejemplo `minimum_flow`, `maximum_generation`, `availability`. |
| `time_series_signal_id` | `BIGINT FK time_series_signals(id)` | Si | Senal versionada. |
| `required` | `BOOLEAN` | Si | Si es obligatoria. |

Restricciones:

- `UNIQUE (case_constraint_binding_id, role_key)`.

### Ejemplos De Restricciones Especificas

| `constraint_key` | Entidades | Parametros | Julia |
| --- | --- | --- | --- |
| `reservoir_min_final_storage` | `case_hydraulic_node:reservoir` | `min_storage_hm3` | `HydroConstraints.add_reservoir_min_final_storage!` |
| `reach_min_environmental_flow` | `case_hydraulic_reach` | serie `minimum_flow_m3s` o escalar | `HydroConstraints.add_reach_min_flow!` |
| `unit_forced_outage` | `case_hydraulic_unit` | serie `unit_availability_factor` | `HydroConstraints.add_unit_availability!` |
| `plant_total_generation_cap` | `case_hydraulic_plant` + unidades | `power_max_mw` o serie | `HydroConstraints.add_plant_generation_cap!` |
| `case_specific_water_transfer_limit` | `case_hydraulic_node:source`, `case_hydraulic_node:sink`, `case_hydraulic_reach` | limites y penalizacion | `CustomCaseConstraints.add_transfer_limit!` |

### Contrato Con Julia

Cada restriccion allowlisted deberia exponer una funcion con firma estable,
por ejemplo:

```julia
add_constraint!(
    model,
    normalized_case,
    binding_payload,
    index_maps,
)
```

Donde `binding_payload` se genera desde:

- `case_constraint_bindings.parameter_values_json`
- `case_constraint_entity_bindings`
- `case_constraint_time_series_bindings`
- metadata de `constraint_definitions`

Reglas:

- La BBDD no guarda codigo ejecutable.
- La BBDD guarda claves, parametros, entidades y version del contrato.
- El backend valida que la restriccion exista en el catalogo allowlisted.
- El generador exporta esas restricciones al `system_case_json` o a un archivo
  auxiliar versionado.
- Julia rechaza cualquier `constraint_key` desconocido o version incompatible.

### Recomendacion Para Scripts Por Caso

Si necesitas scripts Julia especificos por caso, que sean modulos versionados
en el repo, no blobs en la BBDD:

```text
src/cases/
  hydro_laja.jl
  maule_special_constraints.jl
  client_x_contract_constraints.jl
```

La BBDD mapea el caso a esos modulos con:

```text
constraint_definitions.constraint_key = "client_x_contract_limit"
constraint_definitions.julia_module = "ClientXContractConstraints"
constraint_definitions.julia_function = "add_contract_limit!"
case_constraint_bindings.case_id = ...
case_constraint_bindings.parameter_values_json = {...}
```

Asi puedes tener restricciones especificas por cliente/caso sin perder:

- trazabilidad,
- validacion,
- reproducibilidad,
- seguridad,
- comparabilidad entre casos.

## Mapeo De Terminos De Objetivo A Julia

Los terminos de objetivo siguen el mismo patron allowlisted de restricciones,
pero viven en tablas separadas para no mezclar factibilidad fisica con costos,
ingresos, penalizaciones o valores economicos.

Flujo recomendado:

```text
objective_term_definitions
  -> case_objective_term_bindings
    -> case_objective_entity_bindings
    -> case_objective_time_series_bindings
  -> generador Python/Julia
  -> system_case_json + objective payload
  -> script/modulo Julia allowlisted
```

### `objective_term_definitions`

Catalogo allowlisted de terminos de objetivo soportados por el sistema.

| Campo | Tipo sugerido | Requerido | Descripcion |
| --- | --- | --- | --- |
| `id` | `BIGSERIAL PK` | Si | Identificador. |
| `objective_term_key` | `TEXT` | Si | Nombre estable, por ejemplo `hydro_spill_penalty`. |
| `display_name` | `TEXT` | Si | Nombre visible. |
| `description` | `TEXT` | No | Explicacion funcional. |
| `domain` | `TEXT` | Si | `battery`, `grid`, `hydraulic`, `economic`, `custom_case`. |
| `term_category` | `TEXT` | Si | `cost`, `revenue`, `penalty`, `terminal_value`, `regularization`, `custom`. |
| `julia_module` | `TEXT` | Si | Modulo o archivo allowlisted, por ejemplo `HydroObjectiveTerms`. |
| `julia_function` | `TEXT` | Si | Funcion que agrega el termino al objetivo. |
| `implementation_version` | `TEXT` | Si | Version semantica del contrato del termino. |
| `parameter_schema_version` | `TEXT` | Si | Version del esquema de parametros esperado por `schema_json`. |
| `schema_json` | `JSONB` | Si | Esquema de parametros esperados. |
| `supported_schema_versions_json` | `JSONB` | Si | Versiones de `system_case` compatibles. |
| `default_weight` | `DOUBLE PRECISION` | Si | Multiplicador por defecto del termino. |
| `is_active` | `BOOLEAN` | Si | Permite retirar terminos sin borrar historia. |
| `created_at` | `TIMESTAMPTZ` | Si | Auditoria. |
| `updated_at` | `TIMESTAMPTZ` | Si | Auditoria. |

Restricciones:

- `UNIQUE (objective_term_key, implementation_version, parameter_schema_version)`.
- No ejecutar scripts fuera de este catalogo.

### `case_objective_term_bindings`

Activa un termino de objetivo especifico en un caso.

| Campo | Tipo sugerido | Requerido | Descripcion |
| --- | --- | --- | --- |
| `id` | `BIGSERIAL PK` | Si | Identificador. |
| `case_id` | `BIGINT FK optimization_cases(id)` | Si | Caso. |
| `objective_term_definition_id` | `BIGINT FK objective_term_definitions(id)` | Si | Termino del catalogo. |
| `binding_key` | `TEXT` | Si | ID estable dentro del caso, por ejemplo `spill_penalty_laja`. |
| `enabled` | `BOOLEAN` | Si | Activa/desactiva sin borrar. |
| `weight` | `DOUBLE PRECISION` | Si | Multiplicador del termino en este caso. |
| `priority_order` | `INTEGER` | Si | Orden de ensamblaje si importa. |
| `parameter_values_json` | `JSONB` | Si | Parametros simples del binding. |
| `validation_payload_json` | `JSONB` | Si | Resultado de validacion. |
| `created_at` | `TIMESTAMPTZ` | Si | Auditoria. |
| `updated_at` | `TIMESTAMPTZ` | Si | Auditoria. |
| `created_by` | `TEXT` | Si | Usuario o servicio. |
| `updated_by` | `TEXT` | Si | Usuario o servicio. |

Restricciones:

- `UNIQUE (case_id, binding_key)`.
- Validar `parameter_values_json` contra
  `objective_term_definitions.schema_json` antes de promover el caso.
- `weight` puede ser negativo solo si el termino esta definido para ingresos o
  beneficios y el contrato Julia lo permite explicitamente.

### `case_objective_entity_bindings`

Mapea el termino de objetivo a objetos concretos activos dentro del caso.

| Campo | Tipo sugerido | Requerido | Descripcion |
| --- | --- | --- | --- |
| `id` | `BIGSERIAL PK` | Si | Identificador. |
| `case_objective_term_binding_id` | `BIGINT FK case_objective_term_bindings(id)` | Si | Binding de termino. |
| `role_key` | `TEXT` | Si | Rol esperado por el termino: `asset`, `reservoir`, `unit`, `reach`, `plant`, etc. |
| `entity_type` | `TEXT` | Si | `case_component`, `case_hydraulic_node`, `case_hydraulic_reach`, `case_hydraulic_plant`, `case_hydraulic_unit`, etc. |
| `entity_id` | `BIGINT` | Si | ID de la entidad activa del caso segun `entity_type`. |
| `metadata_json` | `JSONB` | Si | Datos auxiliares. |

Restricciones:

- `UNIQUE (case_objective_term_binding_id, role_key, entity_type, entity_id)`.
- Validar integridad de `entity_id` por aplicacion o triggers.
- Si el termino requiere atributos fisicos base, el generador debe resolverlos
  desde la entidad activa del caso.

### `case_objective_time_series_bindings`

Mapea terminos que requieren series, por ejemplo precios, penalizaciones
variables, valor de agua o costo marginal externo.

| Campo | Tipo sugerido | Requerido | Descripcion |
| --- | --- | --- | --- |
| `id` | `BIGSERIAL PK` | Si | Identificador. |
| `case_objective_term_binding_id` | `BIGINT FK case_objective_term_bindings(id)` | Si | Binding de termino. |
| `role_key` | `TEXT` | Si | Ejemplo `price`, `penalty`, `terminal_value`, `reference_dispatch`. |
| `time_series_signal_id` | `BIGINT FK time_series_signals(id)` | Si | Senal versionada. |
| `required` | `BOOLEAN` | Si | Si es obligatoria. |

Restricciones:

- `UNIQUE (case_objective_term_binding_id, role_key)`.
- La serie debe compartir horizonte compatible con los inputs ejecutables si
  participa periodo a periodo en el objetivo.

### Ejemplos De Terminos De Objetivo

| `objective_term_key` | Entidades | Parametros/series | Julia |
| --- | --- | --- | --- |
| `grid_import_energy_cost` | `case_component:grid` | serie `import_price_usd_per_mwh` | `EconomicObjective.add_import_cost!` |
| `grid_export_revenue` | `case_component:grid` | serie `export_price_usd_per_mwh` | `EconomicObjective.add_export_revenue!` |
| `battery_degradation_cost` | `case_component:battery` | `degradation_cost_usd_per_mwh` | `BatteryObjective.add_degradation_cost!` |
| `renewable_curtailment_penalty` | `case_component:renewable` | `curtailment_penalty_usd_per_mwh` | `RenewableObjective.add_curtailment_penalty!` |
| `hydro_spill_penalty` | `case_hydraulic_reach:spillway` | `spill_penalty_usd_per_m3` | `HydroObjective.add_spill_penalty!` |
| `reservoir_terminal_water_value` | `case_hydraulic_node:reservoir` | escalar o serie `terminal_water_value_usd_per_hm3` | `HydroObjective.add_terminal_water_value!` |

### Contrato Con Julia Para Objetivos

Cada termino allowlisted deberia exponer una funcion con firma estable, por
ejemplo:

```julia
add_objective_term!(
    objective_accumulator,
    model,
    normalized_case,
    term_payload,
    index_maps,
)
```

Donde `term_payload` se genera desde:

- `case_objective_term_bindings.parameter_values_json`
- `case_objective_entity_bindings`
- `case_objective_time_series_bindings`
- metadata de `objective_term_definitions`

Reglas:

- La BBDD no guarda formulas ejecutables arbitrarias.
- La BBDD guarda claves, pesos, parametros, entidades, series y version del
  contrato.
- El backend valida que el termino exista en el catalogo allowlisted.
- El generador exporta esos terminos al `system_case_json` o a un archivo
  auxiliar versionado.
- Julia rechaza cualquier `objective_term_key` desconocido o version
  incompatible.

## Como Generar `system_case_json`

1. Leer `optimization_cases`.
2. Leer `case_input_variants` si la promocion o corrida usa una variante de
   series especifica.
3. Leer `case_components` y generar `nodes`.
4. Leer tablas `case_*_parameters` segun tipo de componente.
5. Leer `case_edges` y generar `edges`; si no hay edges explicitos, generarlos
   automaticamente desde cada activo al PCC.
6. Leer `case_time_series_bindings` del default del caso o de la
   `case_input_variant` seleccionada.
7. Leer `case_constraint_bindings` y sus entidades/series asociadas.
8. Leer `case_objective_term_bindings` y sus entidades/series asociadas.
9. Validar que el horizonte de todas las senales requeridas este alineado.
10. Construir `time_series` periodo por periodo:
   - `timestamp_start`
   - `timestamp_end`
   - `duration_hours`
   - precio legacy o par import/export
   - mapas por asset ID: renovable, load, hydro.
11. Agregar `solver` desde `case_solver_settings`.
12. Agregar payload de restricciones y terminos de objetivo allowlisted.
13. Delegar validacion final al CLI Julia.
14. Guardar el JSON validado en `scenario_versions.system_case_json`.

## Manejo De Series Reales Y Simuladas

Recomendacion:

- Guardar inputs reales como `time_series_sets.data_kind = 'real'`.
- Guardar programas o planes externos como
  `time_series_sets.data_kind = 'programmed'`.
- Guardar outputs de corrida que se quieran reutilizar como
  `time_series_sets.data_kind = 'simulated'`, con `version_number`,
  `version_label`, y
  `source_run_id = runs.id`.
- Mantener los CSV/JSON originales como artefactos; la BBDD indexa valores para
  busqueda, comparacion y reutilizacion.
- No guardar todos los outputs simulados por defecto si el volumen crece mucho.
  Ingerir a BBDD solo senales marcadas como reutilizables o publicables.

Ejemplo:

```text
time_series_sets:
  name = "enero_2026_inputs"
  version_number = 1
  version_label = "real_v1"
  data_kind = "real"

time_series_sets:
  name = "run_42_dispatch"
  version_number = 1
  version_label = "sim_v1"
  data_kind = "simulated"
  source_run_id = 42

time_series_sets:
  name = "programa_externo_cen"
  version_number = 1
  version_label = "programmed_v1"
  data_kind = "programmed"
```

## Indices Recomendados

| Tabla | Indice |
| --- | --- |
| `optimization_cases` | `(scenario_id, case_key)` |
| `components` | `(project_id, component_key)` |
| `case_components` | `(case_id, case_asset_id)` |
| `case_edges` | `(case_id)` |
| `case_bus_parameters` | `(case_id, case_component_id)` |
| `case_battery_parameters` | `(case_id, case_component_id)` |
| `case_grid_parameters` | `(case_id, case_component_id)` |
| `case_renewable_parameters` | `(case_id, case_component_id)` |
| `case_load_parameters` | `(case_id, case_component_id)` |
| `case_hydro_parameters` | `(case_id, case_component_id)` |
| `case_parameter_group_hashes` | `(case_id, parameter_group, entity_type, entity_id)` |
| `hydraulic_systems` | `(project_id, system_key)` |
| `hydraulic_nodes` | `(hydraulic_system_id, node_key)` |
| `hydraulic_reaches` | `(hydraulic_system_id, reach_key)` y `(from_node_id, to_node_id)` |
| `hydraulic_plants` | `(hydraulic_system_id, plant_key)` |
| `hydraulic_units` | `(hydraulic_plant_id, unit_key)` |
| `case_hydraulic_systems` | `(case_id, hydraulic_system_id)` |
| `case_hydraulic_nodes` | `(case_id, hydraulic_node_id)` |
| `case_hydraulic_reservoir_parameters` | `(case_id, case_hydraulic_node_id)` |
| `case_hydraulic_reaches` | `(case_id, hydraulic_reach_id)` |
| `case_hydraulic_plants` | `(case_id, hydraulic_plant_id)` |
| `case_hydraulic_units` | `(case_id, hydraulic_unit_id)` |
| `hydraulic_curve_sets` | `(project_id, entity_type, entity_id, curve_key, version_number)` y `(project_id, entity_type, entity_id, curve_key, version_label)` |
| `hydraulic_curve_points` | `(hydraulic_curve_set_id, point_index)` |
| `time_series_sets` | `(project_id, name, version_number)` y `(project_id, name, version_label)` |
| `time_series_periods` | `(time_series_set_id, period_index)` y `(time_series_set_id, timestamp_start)` |
| `time_series_signals` | `(time_series_set_id, entity_type, entity_id, signal_key)` |
| `time_series_import_mappings` | `(time_series_set_id, entity_type, entity_id, signal_key)` |
| `time_series_transformations` | `(project_id, transformation_key)` y `(output_time_series_set_id)` |
| `time_series_values` | `(time_series_set_id, time_series_signal_id, time_series_period_id)` y `(time_series_set_id, time_series_period_id)` |
| `case_time_series_bindings` | `(case_id, case_input_variant_id, entity_type, entity_id, signal_key)` |
| `validation_dependencies` | `(owner_type, owner_id, dependency_type, dependency_id)` |
| `case_hydraulic_curve_bindings` | `(case_id, entity_type, entity_id, curve_role)` |
| `availability_events` | `(project_id, entity_type, entity_id, starts_at, ends_at)` |
| `availability_event_time_series_links` | `(availability_event_id, time_series_signal_id)` |
| `constraint_definitions` | `(constraint_key, implementation_version, parameter_schema_version)` |
| `case_constraint_bindings` | `(case_id, binding_key)` |
| `case_constraint_entity_bindings` | `(case_constraint_binding_id, role_key, entity_type, entity_id)` |
| `case_constraint_time_series_bindings` | `(case_constraint_binding_id, role_key)` |
| `objective_term_definitions` | `(objective_term_key, implementation_version, parameter_schema_version)` |
| `case_objective_term_bindings` | `(case_id, binding_key)` |
| `case_objective_entity_bindings` | `(case_objective_term_binding_id, role_key, entity_type, entity_id)` |
| `case_objective_time_series_bindings` | `(case_objective_term_binding_id, role_key)` |

Nota de implementacion SQL:

- En PostgreSQL, `UNIQUE` permite multiples filas con `NULL`. Para constraints
  que incluyen `entity_type`, `entity_id` o `case_input_variant_id` nullable
  se debe usar `UNIQUE NULLS NOT DISTINCT` si esta disponible, o indices
  parciales/expresiones equivalentes.
- Esto aplica especialmente a senales globales (`entity_type IS NULL`) y
  bindings default de caso (`case_input_variant_id IS NULL`), donde no se
  deben permitir duplicados logicos.

## Validaciones Minimas

Validaciones de caso:

- Exactamente un PCC/bus por caso.
- IDs unicos por caso.
- Componentes electricos conectados al PCC.
- `schema_version` compatible con los tipos de activo usados.
- Si hay componente `hydro` simple legacy, usar `bess_system_dispatch.v2`.
- Si hay red hidraulica futura, validar que el contrato Julia declarado soporte
  las entidades `case_hydraulic_*` activas.

Validaciones topologicas hidraulicas:

- Todo registro activo en `case_hydraulic_systems` debe pertenecer al mismo
  proyecto del caso.
- Todo `case_hydraulic_node`, `case_hydraulic_reach`,
  `case_hydraulic_plant` y `case_hydraulic_unit` activo debe resolver, desde
  su objeto base, a un sistema hidraulico activo del caso.
- Todo `case_hydraulic_reach` activo debe resolver a un `hydraulic_reach` base
  cuyos `from_node_id` y `to_node_id` tambien esten activos como
  `case_hydraulic_nodes` en el mismo caso.
- Toda `case_hydraulic_unit` activa debe tener intake y discharge activos en
  el caso. Si pertenece a una planta, la `case_hydraulic_plant` tambien debe
  estar activa.
- Toda `case_hydraulic_plant` activa debe tener al menos una
  `case_hydraulic_unit` activa, salvo que `metadata_json` la marque
  explicitamente como agregada/no modelada.
- Todo embalse activo (`node_type = 'reservoir'`) debe tener
  `case_hydraulic_reservoir_parameters`, estado inicial, limites operativos y
  curvas obligatorias segun el contrato del modelo.
- Todo tramo activo con `reach_type = 'spillway'`, `canal`, `river` o
  `bypass` debe tener limites y direccion compatibles con el modelo Julia que
  lo consumira.
- Las curvas requeridas por unidades, embalses, tramos o plantas activas deben
  existir en `case_hydraulic_curve_bindings` y ser compatibles con el objeto
  fisico base.
- Los afluentes naturales requeridos por nodos activos deben existir como
  bindings de series (`natural_inflow_m3s`) o como parametro/valor por defecto
  aceptado por el contrato del caso.
- No permitir entidades activas huerfanas: una unidad no puede descargar a un
  nodo desactivado, y un tramo no puede terminar en un nodo fuera del
  subconjunto activo.
- La red hidraulica activa puede tener multiples islas desconectadas. Cada
  isla debe tener al menos una condicion de borde que haga resoluble el balance:
  afluente natural, embalse con estado inicial, salida/descarga modelada,
  unidad conectada a una central o parametro explicito aceptado por el contrato
  del modelo.
- Rechazar islas que solo contienen nodos/tramos pasivos sin fuente,
  almacenamiento, salida o decision operacional. Marcar la validacion con el
  identificador de la isla y las entidades que la componen.
- Calcular las islas durante la validacion; no persistir `island_id` en las
  tablas `case_hydraulic_*` en el MVP. Guardar el resultado en
  `optimization_cases.validation_payload_json.hydraulic_islands` con al menos:
  `island_key`, entidades incluidas, condiciones de borde detectadas,
  advertencias, errores y estado `valid`/`invalid`.
- El `island_key` puede ser deterministico y derivado de las entidades activas
  ordenadas; no debe usarse como identificador estable de negocio.
- Los ciclos hidraulicos se permiten solo si todos los tramos del ciclo tienen
  `routing_method` soportado por el optimizador. En MVP, si el modelo no
  soporta ciclos, rechazarlos antes de generar `system_case_json`.
- Si existe tiempo de viaje (`travel_time_hours` o override por caso), validar
  que pueda discretizarse con el horizonte elegido o que el `routing_method`
  declare como manejar fracciones de periodo.
- Si una restriccion u objetivo apunta a una entidad hidraulica, esa entidad
  debe estar activa en el caso y pasar las validaciones anteriores.

Validaciones de parametros:

- BESS: bounds de energia, eficiencia, terminal condition y degradacion.
- Grid: limites no negativos y anti-sim configurada.
- Renewable: curtailment penalty no negativa.
- Hydro simple legacy: storage bounds, curvas, terminal condition, release,
  spill penalty y terminal water value.
- Hidraulica futura: usar validaciones topologicas hidraulicas, curvas
  versionadas y parametros `case_hydraulic_*`.

Validaciones de series:

- `timestamp_start` y `timestamp_end` unicos, ordenados y sin traslapes por
  set.
- `timestamp_start < timestamp_end`.
- `duration_hours > 0`.
- `duration_hours` consistente con `timestamp_start`/`timestamp_end`.
- `time_series_sets.timezone` debe ser IANA valido.
- Precio legacy completo o par import/export completo.
- Disponibilidad renovable no negativa.
- Demanda no negativa.
- Inflow hidro no negativo.
- Cada activo que requiere serie tiene binding valido.
- Sets usados por un caso tienen horizonte compatible por `period_index`,
  `timestamp_start`, `timestamp_end` y `duration_hours`.

## Migracion Recomendada

1. Crear tablas nuevas sin tocar la ejecucion actual.
2. Agregar `scenario_versions.normalized_case_id` nullable.
3. Implementar generador `normalized DB -> system_case_json`.
4. Poblar un caso desde un `scenario_draft` existente.
5. Validar que el JSON generado sea equivalente al actual.
6. Promover a `scenario_versions` y ejecutar por el flujo existente.
7. Migrar el editor para escribir en tablas normalizadas.
8. Mantener import/export JSON avanzado como compatibilidad.

## Preguntas Generales Para Resolver

Estas son las preguntas que conviene responder antes de implementar. Incluyo mi
respuesta recomendada para no dejar la decision abierta.

| Pregunta | Respuesta recomendada |
| --- | --- |
| 1. El `caso` debe ser editable o inmutable? | Editable mientras esta en `optimization_cases.status = draft`; inmutable al promover a `scenario_versions`. |
| 2. Reutilizamos componentes entre casos o duplicamos activos por caso? | Reutilizar `components` por proyecto y guardar parametros por `case_id`. |
| 3. La version de series va por cada punto o por set? | Por set en `time_series_sets.version_number` y `time_series_sets.version_label`; evita inconsistencias y permite reutilizar conjuntos completos. |
| 4. Un set puede mezclar series reales, programadas y simuladas? | Si: usar `time_series_sets.data_kind = 'mixed'` y `time_series_signals.data_kind` por senal. Para casos simples, preferir un solo `data_kind` por set. |
| 5. Guardamos outputs simulados en la misma estructura de series? | Si, pero solo para senales que se quieran comparar o reutilizar; los artefactos siguen siendo la fuente auditable. |
| 6. Conviene una tabla generica key/value de parametros? | No como modelo principal. Usar tablas tipadas por activo y `metadata_json` solo para extensiones. |
| 7. Los cambios de parametros crean nuevo caso o actualizan el mismo? | Si el caso ya fue promovido o ejecutado, crear nuevo caso/version. Antes de eso se puede editar. |
| 8. La unidad se guarda como viene del archivo o canonica? | Guardar valores canonicos para el modelo y conservar unidad original en `time_series_import_mappings`. |
| 9. Un caso puede usar varios sets de series? | Si, mediante `case_time_series_bindings`, pero todos los inputs ejecutables deben tener horizonte compatible. |
| 10. Componentes pueden pertenecer a mas de un proyecto? | No en MVP; scope por proyecto reduce problemas de permisos y publicaciones. |

## Riesgos Abiertos Y Controles

| Riesgo | Control recomendado |
| --- | --- |
| El contrato Julia para red hidraulica futura aun no existe completo. | Implementar primero generacion de payload y validacion contra un modelo Julia minimo antes de migrar UI compleja. |
| Las FK polimorficas (`entity_type`/`entity_id`) no tienen integridad SQL simple. | Validar en aplicacion y, si se requiere mayor rigor, agregar triggers por tipo de entidad. |
| Los sets de series editables pueden invalidar validaciones previas. | Usar `content_hash`, `time_series_set_revisions` y `validation_dependencies`; advertir en UI antes de correr con dependencias stale. |
| `time_series_values` puede crecer mucho. | Mantener modelo long portable y particionar/optimizar solo cuando el volumen real lo justifique. |
| La topologia hidraulica puede permitir casos fisicamente incompletos si la validacion es debil. | Ejecutar validaciones topologicas antes de promover y guardar resultados en `validation_payload_json`. |
| Restricciones/objetivos custom pueden romper seguridad si se ejecuta codigo arbitrario. | Mantener catalogos allowlisted con `implementation_version`, `parameter_schema_version` y rechazo en Julia de claves desconocidas. |
| La migracion desde `scenario_drafts` puede generar payloads no equivalentes. | Usar pruebas de equivalencia JSON y corridas comparativas antes de cambiar el editor principal. |

## Implementacion Recomendada Por Fases

La recomendacion es no implementar todo el modelo en una sola entrega. Conviene
avanzar por fases verticales que mantengan compatibilidad con el flujo actual
de `scenario_versions.system_case_json`.

### Fase 1: Caso Normalizado Core

Objetivo: separar el caso editable normalizado del snapshot ejecutable actual.

Tablas principales:

1. `optimization_cases`
2. `components`
3. `case_components`
4. `case_edges`
5. `case_solver_settings`
6. Parametros tipados actuales: bus/grid, battery, renewable, load e hydro
   simple.
7. `case_parameter_group_hashes`

Trabajo de aplicacion:

- Agregar `scenario_versions.normalized_case_id` nullable.
- Implementar generador `normalized DB -> system_case_json`.
- Validar equivalencia contra un `scenario_draft` existente.
- Mantener import/export JSON como compatibilidad avanzada.

Criterio de salida:

- Un caso simple existente se puede cargar desde tablas normalizadas, promover a
  `scenario_versions` y ejecutar sin cambiar el optimizador.

### Fase 2: Series Versionadas Y Variantes

Objetivo: permitir cambiar versiones de series reales, programadas, forecast y
simuladas sin duplicar todo el caso.

Tablas principales:

1. `time_series_sources`
2. `time_series_sets`
3. `time_series_set_revisions`
4. `time_series_periods`
5. `time_series_signals`
6. `time_series_values`
7. `time_series_import_mappings`
8. `case_input_variants`
9. `case_time_series_bindings`
10. `validation_dependencies`

Trabajo de aplicacion:

- Validar horizonte por `period_index`, `timestamp_start`, `timestamp_end` y
  `duration_hours`.
- Calcular `content_hash` por set.
- Materializar en `scenario_versions` las series usadas o su payload resuelto.
- Permitir comparar variantes antes de correrlas.

Criterio de salida:

- El usuario puede correr el mismo caso con distintas versiones de precios,
  hidrologia, demanda o renovables, y la UI muestra si se reutilizo o creo una
  nueva `scenario_version`.

### Fase 3: Red Hidraulica Futura

Objetivo: representar embalses, nodos, tramos, centrales y unidades hidraulicas
sin forzar todo a un unico componente `hydro`.

Tablas principales:

1. `hydraulic_systems`
2. `hydraulic_nodes`
3. `hydraulic_reaches`
4. `hydraulic_plants`
5. `hydraulic_units`
6. `case_hydraulic_systems`
7. `case_hydraulic_nodes`
8. `case_hydraulic_reservoir_parameters`
9. `case_hydraulic_reaches`
10. `case_hydraulic_plants`
11. `case_hydraulic_units`
12. `hydraulic_curve_sets`
13. `hydraulic_curve_points`
14. `case_hydraulic_curve_bindings`
15. `availability_events`
16. `availability_event_time_series_links`

Trabajo de aplicacion:

- Validar topologia activa, islas hidraulicas, ciclos, curvas requeridas,
  afluentes naturales y compatibilidad con el modulo Julia.
- Calcular islas en validacion y guardar resultado en
  `optimization_cases.validation_payload_json.hydraulic_islands`.
- Derivar eventos de disponibilidad hacia series versionadas cuando
  corresponda.

Criterio de salida:

- Un caso puede activar un subconjunto de una red hidraulica base, validar su
  topologia y generar un payload ejecutable para el modelo hidraulico soportado.

### Fase 4: Restricciones Y Objetivos Allowlisted

Objetivo: mapear restricciones y terminos de objetivo especificos por caso sin
guardar codigo Julia arbitrario en la BBDD.

Tablas principales:

1. `constraint_definitions`
2. `case_constraint_bindings`
3. `case_constraint_entity_bindings`
4. `case_constraint_time_series_bindings`
5. `objective_term_definitions`
6. `case_objective_term_bindings`
7. `case_objective_entity_bindings`
8. `case_objective_time_series_bindings`

Trabajo de aplicacion:

- Implementar catalogos allowlisted con `implementation_version` y
  `parameter_schema_version`.
- Validar parametros contra `schema_json`.
- Resolver entidades activas del caso hacia objetos base cuando Julia lo
  requiera.
- Congelar restricciones y objetivos resueltos dentro del snapshot ejecutable.

Criterio de salida:

- Un caso puede activar restricciones y terminos economicos especificos sin
  romper trazabilidad, validacion ni seguridad de ejecucion.

### Fase 5: Optimizaciones Fisicas Y Auditoria Avanzada

Objetivo: escalar volumen, auditoria y ergonomia sin cambiar el contrato logico.

Mejoras candidatas:

1. Particionar `time_series_values` por `time_series_set_id`, hash de set o
   rango temporal.
2. Evaluar TimescaleDB/hypertables si el volumen de series lo justifica.
3. Implementar `time_series_transformations` para resampling, interpolacion,
   escalamiento y combinacion de escenarios.
4. Agregar cache derivada de islas hidraulicas si la UI lo necesita.
5. Endurecer historial de edicion de series con snapshots compactados o
   artefactos versionados.
6. Agregar politicas de retencion para outputs simulados no reutilizables.

Criterio de salida:

- La BBDD soporta mayor volumen y auditoria mas estricta sin reescribir el
  modelo conceptual ni el contrato con `system_case_json`.
