# Propuesta Inicial Para Manejo De Series De Tiempo

Fecha: 2026-07-03

## Objetivo

Definir una primera forma de manejar series de tiempo asociadas a componentes,
casos, variantes y versiones ejecutables, manteniendo la compatibilidad con el
flujo actual:

```text
Project -> Scenario -> OptimizationCase / ScenarioDraft
-> ScenarioVersion -> Run -> Artifacts -> Publication
```

La idea central es separar tres conceptos que hoy aparecen mezclados en algunos
flujos:

1. El objeto fisico o logico del proyecto, como BESS, carga, renovable,
   embalse, tramo o unidad.
2. La parametrizacion del objeto dentro de un caso de optimizacion.
3. Las series de tiempo reutilizables que alimentan o comparan ese caso.

El `system_case_json` dentro de `scenario_versions` debe seguir siendo el
snapshot ejecutable e inmutable. La nueva capa de series debe servir para
editar, reutilizar, comparar y trazar datos antes de congelarlos en una version.

## Contexto Leido

El repo ya tiene varias piezas relevantes:

- `scenario_versions` son inmutables y las corridas apuntan a versiones, no a
  drafts.
- El editor estructurado actual guarda fuentes CSV/XLSX, preview, mapping,
  filas editadas y `validated_rows` dentro del `ScenarioDraft` JSON.
- El editor hidraulico ya usa `optimization_cases` como caso editable
  normalizado y `scenario_versions` como snapshot promovido.
- La hidraulica de diagrama ya implemento un subconjunto especifico:
  `hydraulic_time_series_sets`, `hydraulic_time_series_points` y
  `case_hydraulic_time_series_bindings`.
- `docs/db/propuesta_bbdd_componentes_timeseries.md` ya propone un modelo
  amplio con `time_series_sets`, `time_series_periods`,
  `time_series_signals`, `time_series_values`, `case_input_variants` y
  `case_time_series_bindings`.

La conclusion es que no conviene inventar un segundo modelo conceptual. Conviene
destilar esa propuesta en un camino incremental que unifique lo que ya existe.

## Problema A Resolver

El sistema necesitara soportar casos donde la misma estructura fisica y los
mismos parametros se ejecutan con distintas versiones de:

- precios de compra, venta o precio unico;
- demanda;
- disponibilidad solar/eolica;
- afluentes hidraulicos;
- caudales minimos;
- disponibilidad o mantenimiento de unidades;
- programas externos;
- forecasts;
- outputs simulados que se quieran comparar o reutilizar.

Si cada version de datos obliga a duplicar todo el caso, el historial se vuelve
ruidoso. Si las series se guardan solo dentro del JSON del draft, no se pueden
reutilizar bien. Si una `scenario_version` apunta a series mutables, se pierde
reproducibilidad.

## Idea Inicial

Usar un catalogo comun de series versionadas por proyecto. Cada set representa
un paquete reutilizable de periodos y senales alineadas.

```text
time_series_set
  -> periods
  -> signals
  -> values
```

Una senal puede ser global del caso, como `import_price_usd_per_mwh`, o estar
asociada a una entidad base del proyecto:

```text
component:load_1 -> load_demand_mw
component:pv_1 -> renewable_available_power_mw
hydraulic_node:reservoir_a -> natural_inflow_m3s
hydraulic_reach:reach_1 -> minimum_flow_m3s
hydraulic_unit:unit_1 -> unit_availability_factor
```

El caso no deberia copiar valores de series. El caso define componentes,
parametros, curvas y topologia. Luego una variante de inputs define que series
usa ese caso:

```text
optimization_case
  -> case_input_variant
    -> case_time_series_bindings
      -> time_series_signal
        -> time_series_set
```

Al promover o ejecutar, se genera siempre una `scenario_version`. Esa version
materializa las series efectivas dentro de `system_case_json` y guarda metadata
de trazabilidad:

- `time_series_set_id`;
- `version_number`;
- `version_label`;
- `revision_number`;
- `content_hash`;
- senales y entidades vinculadas;
- timestamps de validacion/promocion.

Asi, los sets siguen siendo editables o reemplazables para trabajo futuro, pero
las versiones ejecutadas no cambian.

## Modelo Conceptual Minimo

### Fuentes

`time_series_sources` registra de donde vienen los datos:

- CSV;
- XLSX;
- carga manual;
- API futura;
- artefacto de corrida;
- programa externo;
- forecast externo.

Debe guardar nombre de archivo seguro, checksum, hoja XLSX si aplica, emisor,
fecha de emision, vigencia y metadata de importacion.

### Sets

`time_series_sets` representa una version reutilizable. Campos clave:

- `project_id`;
- `name`;
- `version_number`;
- `version_label`;
- `data_kind`: `real`, `programmed`, `forecast`, `simulated`,
  `synthetic` o `mixed`;
- `timezone`;
- `status`: `draft`, `validated`, `archived`;
- `content_hash`.

La recomendacion inicial es que el set sea el objeto que el usuario selecciona
en UI: "Hidrologia seca v2", "Precios cliente final 2026-01", "Demanda base",
"Salida simulada run 42".

### Periodos

`time_series_periods` define el horizonte comun del set:

- `period_index`;
- `timestamp_start`;
- `timestamp_end`;
- `duration_hours`.

Para el MVP, todas las senales usadas en una variante ejecutable deben calzar
exactamente por `period_index`, timestamps y duracion. Resampling,
interpolacion o agregacion deben ser transformaciones explicitas, no magia
implicita durante la ejecucion.

### Senales

`time_series_signals` define que mide cada columna logica:

- `entity_type`;
- `entity_id`;
- `signal_key`;
- `unit`;
- `signal_role`: `input`, `output`, `baseline`, `target`, `comparison`;
- `aggregation`: `period_average`, `period_sum`, `end_of_period`, etc.

Las senales globales usan `entity_type = NULL` y `entity_id = NULL`.

### Valores

`time_series_values` guarda valores en formato long:

```text
time_series_set_id
time_series_signal_id
time_series_period_id
value_numeric
quality_flag
source_row_number
```

El formato long evita crear una tabla por cada CSV y permite que un mismo set
contenga precios, demanda, renovables e hidrologia.

### Variantes Y Bindings

`case_input_variants` permite correr el mismo caso con distintos insumos sin
duplicar parametros fisicos.

`case_time_series_bindings` conecta una entidad activa del caso con una senal:

```text
case_id
case_input_variant_id
entity_type      -- case_component, case_hydraulic_node, etc.
entity_id
signal_key
time_series_set_id
time_series_signal_id
binding_role     -- optimization_input, baseline, target, comparison
```

El binding debe validar compatibilidad entre la entidad activa del caso y la
entidad base de la senal. Por ejemplo, un `case_hydraulic_node` debe resolver al
mismo `hydraulic_node` base que la senal `natural_inflow_m3s`.

## Flujo De Trabajo Propuesto

### 1. Importar

El usuario carga CSV/XLSX o ingresa datos manualmente. El sistema crea:

- `time_series_source`;
- `time_series_set`;
- `time_series_periods`;
- `time_series_signals`;
- `time_series_values`;
- `time_series_import_mappings`.

El preview y mapping actual del draft puede seguir existiendo, pero el resultado
validado deberia poder convertirse a un set reutilizable.

### 2. Vincular

El usuario selecciona una variante de inputs para un caso. La UI muestra las
senales requeridas por el contrato del caso y permite seleccionar sets/senales
compatibles.

Ejemplo:

```text
Base case: embalse + central + carga + grid
Variant: hidrologia seca + precios altos + demanda base
```

### 3. Validar

La validacion de la variante revisa:

- todas las senales requeridas existen;
- todos los horizontes calzan;
- unidades y `signal_key` son compatibles;
- valores fisicamente invalidos se rechazan;
- el hash vigente de cada set queda registrado.

Si luego cambia un set, la validacion queda stale.

### 4. Promover

La promocion genera `system_case_json` desde:

```text
optimization_case + case_input_variant
```

La `scenario_version` guarda:

- el JSON ejecutable completo;
- metadata de generacion;
- snapshot de bindings de series;
- hashes/revisiones usadas.

Las corridas siguen apuntando solo a `scenario_versions`.

### 5. Reutilizar O Comparar

Un output de corrida puede permanecer solo como artefacto. Si el usuario quiere
compararlo o reutilizarlo, se registra como `time_series_set` con
`data_kind = simulated` y `source_run_id`.

No conviene indexar todos los outputs simulados por defecto hasta conocer el
volumen real.

## Camino Incremental Recomendado

### Fase 1: Catalogo Comun Sin Romper Lo Actual

- Definir el catalogo canonico de `signal_key`, unidad y validacion.
- Agregar tablas genericas de series en paralelo a lo existente.
- Permitir crear un `time_series_set` desde el flujo CSV/XLSX actual.
- Mantener `scenario_versions.system_case_json` como fuente ejecutable.

### Fase 2: Variantes De Inputs

- Agregar `case_input_variants`.
- Agregar bindings genericos para precios, carga, renovables e hidrologia.
- Validar horizontes exactos y hashes.
- Generar una `scenario_version` desde caso + variante.

### Fase 3: Convergencia Hidraulica

- Crear un adaptador desde las tablas actuales
  `hydraulic_time_series_sets` hacia el modelo generico.
- Migrar nuevas series hidraulicas al modelo comun.
- Mantener compatibilidad de lectura para casos ya creados.

### Fase 4: Transformaciones Y Outputs Simulados

- Agregar transformaciones versionadas para resampling, escalamiento,
  interpolacion o combinacion de escenarios.
- Permitir guardar outputs seleccionados como series simuladas.
- Agregar vistas de comparacion entre variantes o corridas.

## Preguntas Abiertas

1. Las variantes deben cambiar solo series de tiempo, o tambien parametros como
   limites, estados iniciales, curvas y costos?
2. Que senales son prioritarias para el primer MVP generico: precios, demanda,
   renovables, hidrologia, caudales minimos, disponibilidad de unidades u
   outputs simulados?
3. Un `time_series_set` debe ser editable manteniendo `version_label`, o cada
   cambio de valores debe crear una nueva version inmutable?
4. El usuario piensa en sets como "paquetes de escenario" con muchas senales
   alineadas, o como series individuales que luego se combinan?
5. Los sets pueden mezclar fuentes distintas, por ejemplo precios de un archivo
   e hidrologia de otro, o eso debe resolverse solo mediante variantes?
6. La primera version debe exigir horizontes identicos, o ya se necesita
   resampling/interpolacion?
7. Cual sera la convencion canonica de timezone y DST para Chile:
   `America/Santiago` con timestamps absolutos, o todo en UTC para ejecucion?
8. Que entidad debe recibir el binding en la UI: componente base del proyecto,
   entidad activa del caso, o ambas con resolucion automatica?
9. Que nivel de trazabilidad necesita el usuario para datos editados
   manualmente: revision liviana con hash, snapshot completo o archivo fuente
   versionado?
10. Los datos programados externos necesitan vigencia formal (`issued_at`,
    `valid_from`, `valid_to`) desde el inicio?
11. Los outputs simulados deben poder convertirse en inputs de otro caso desde
    el MVP, o basta con comparacion visual?
12. Que volumen esperado de datos hay por proyecto: cientos, miles, millones o
    cientos de millones de puntos?
13. Los clientes podran ver o descargar series de input, o solo resultados
    publicados?
14. Deben existir series compartidas entre proyectos, o en el MVP todo queda
    estrictamente dentro de `project_id`?
15. La UI necesita comparar dos variantes antes de correr, mostrando diferencias
    de bindings, hashes y horizontes?
16. Como se deben nombrar versiones para que sean utiles al analista:
    incremental automatico, etiqueta obligatoria, convencion por fecha, o todas?
17. Debe haber control de calidad por valor (`measured`, `estimated`, `filled`)
    desde el inicio, o puede quedar en metadata futura?
18. La validacion de Julia debe recibir solo el `system_case_json` materializado
    o tambien metadata de series para mensajes de error mas explicativos?

## Recomendacion Inicial

Adoptar el modelo generico de `time_series_sets + signals + values + bindings`,
pero implementarlo por fases. No conviene reemplazar de golpe el flujo actual
de draft CSV/XLSX ni las tablas hidraulicas especificas ya implementadas.

La primera entrega deberia probar un flujo vertical pequeno:

```text
CSV/XLSX -> time_series_set generico
-> case_input_variant
-> generated system_case_json
-> scenario_version inmutable
-> run
```

El criterio de exito es que el mismo caso se pueda ejecutar con dos versiones
distintas de series sin duplicar parametros fisicos, y que cada corrida siga
siendo reproducible desde su `scenario_version`.
