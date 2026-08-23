# Arquitectura final: capa de configuración, consola de operador y portal cliente

Fecha: 2026-08-23
Estado: Aceptada; cierra el mapa Wayfinder **Capa de configuración: consola de
operador y portal cliente**.
Este documento consolida las decisiones de `docs/wayfinder/capa-de-configuracion/`
y es la referencia normativa para convertir la capa en tickets de implementación.

## Propósito

La aplicación ya tiene un flujo interno auditable para construir, validar,
versionar, ejecutar y publicar un caso de optimización. Esta capa agrega dos
fachadas fijas sobre ese flujo, sin reemplazarlo:

1. una **consola de operador** donde una persona externa ajusta únicamente los
   parámetros y series expuestos, ejecuta el caso y consulta su historial; y
2. un **portal cliente read-only** que presenta una publicación como informe
   ejecutivo con contenido y vocabulario configurables por proyecto.

El objetivo es flexibilidad para quien configura y estabilidad para quien usa.
No se crea un constructor de pantallas. Tampoco se simplifica la cadena interna
Draft -> Caso -> Variante -> Rango -> Versión inmutable -> Corrida. Las dos
fachadas la reutilizan y esconden sus nombres, ids y detalles técnicos.

El alcance ejecutable de esta especificación es el editor estructurado one-bus
descrito en `docs/final/objetivo_final.md`. El diagrama hidráulico y su topología
permanecen en la superficie del analista.

## Principios que no se pueden debilitar

- **Cascarones fijos.** El orden macro de cada superficie es código. La
  configuración solo decide contenido, etiquetas, rangos, defaults, columnas y
  paneles dentro de lugares predefinidos.
- **Allowlist desde el backend.** Los payloads enumeran campo por campo lo que
  puede salir. Nunca se serializa una fila de base de datos completa ni se
  imprime una clave desconocida de `summary.json` o de un CSV.
- **Autorización por request.** Las capacidades se comprueban en cada endpoint,
  después de `require_authenticated_app_boundary`. Las guardas React son UX, no
  frontera de seguridad.
- **El cambio propio no bloquea; el ajeno sí.** El guardado aceptado por la
  consola refresca solo la dependencia de la copia que acaba de modificar. Un
  cambio de topología o parámetros del ingeniero conserva el fail-closed.
- **Historia matemática inmutable.** La configuración no entra en el snapshot
  de una corrida, pero el caso materializado, los overrides y las revisiones de
  series que realmente corrieron sí quedan en la `scenario_version` y en su
  `generation_metadata`.
- **No hay vocabulario interno en superficies externas.** Drafts, casos,
  variantes, bindings, hashes, revisiones, versiones inmutables, paths,
  `stdout`, `stderr` y `exit_code` no cruzan.
- **MVP explícito.** No hay i18n, linter semántico, historial de configuraciones,
  scheduler de avisos, constructor de layouts ni scripts configurables.

## Arquitectura de extremo a extremo

```text
analyst/admin
  |
  +-- portal_config.v1 -----------------------------+
  |                                                 |
  +-- operator_console_config.v1                    |
          |                                         |
          +-- variante propia de la consola         |
          +-- overrides de parámetros               |
          +-- copias operativas planas de series    |
                    |                               |
                    +-- revisión auditable          |
                    +-- lease + control optimista   |
                                                    v
external + operate                         app/surface_payloads.py
  |                                                 |
  +-- /api/console/* -> materialización común ------+--> console_payload
  |          |                                      |    + results_block
  |          +-> scenario_version inmutable -> run  |
  |                                                 |
external + portal_view                              |
  |                                                 |
  +-- /api/client/* -> publicación + configuración -+--> portal_payload
                                                         + results_block
```

`app/surface_payloads.py` será el único módulo que arma `portal_payload`,
`console_payload` y el `results_block` compartido. El preview del analista usa
el mismo constructor del portal; no mantiene una segunda copia del contrato.

## Identidad, capacidades y permisos

### Roles y asignaciones

Los roles globales pasan a ser `admin`, `analyst` y `external`. No existe un
rol global `operator`: operar o ver el portal depende del proyecto.

Cada asignación de un `external` a un proyecto tiene dos capacidades booleanas
independientes:

- `portal_view`: leer publicaciones y descargas aprobadas;
- `operate`: usar las consolas activas alcanzables desde ese proyecto.

Una cuenta puede tener una, ambas o ninguna, y combinaciones distintas por
proyecto. `operate` no concede acceso al proyecto, escenario, catálogo o
variante fuera de `/api/console/*`.

Para minimizar la migración física, `project_client_access` se conserva como
nombre de tabla en este corte y gana las columnas `portal_view` y `operate`.
Todo SQL que hoy exige el literal `users.role = 'client'` pasa a exigir
`users.role = 'external'`. El nombre físico queda como deuda nominal; no debe
filtrarse a ningún contrato.

### Matriz normativa

| Acción | `admin` | `analyst` | `external` + `portal_view` | `external` + `operate` |
| --- | --- | --- | --- | --- |
| Administrar usuarios/capacidades | Sí | No | No | No |
| Editar configuraciones | Sí | Sí | No | No |
| Probar una consola | Sí | Sí | No | Sí, como operador |
| Ver portal/publicaciones | Sí, preview interno | Sí, preview interno | Sí | Solo si también tiene `portal_view` |
| Editar inputs expuestos | Prueba | Prueba | No | Sí |
| Ejecutar una consola | Prueba | Prueba | No | Sí |
| Ver auditoría técnica | Sí | Sí | No | No |
| Ver historial operativo reducido | Sí | Sí | No | Sí |

Solo `admin` otorga o revoca capacidades. `analyst` configura superficies pero
no administra identidades. `admin` y `analyst` prueban una consola con su
identidad real; no impersonan a un operador.

Revocar una capacidad afecta el siguiente request. No cancela una corrida ya
iniciada. La corrida conserva su actor y sigue visible para internos; el usuario
revocado deja de consultarla.

### Auditoría mínima

Toda mutación de consola registra:

- `actor_user_id` estable y nombre/correo como snapshot legible;
- origen `operator_console`;
- proyecto, consola y contador de revisión de configuración usado;
- timestamp;
- para cambios de datos, revisión base, celdas antes/después y nota opcional;
- para corridas, revisiones y hashes exactos materializados.

La atribución fija `triggered_by = "internal_analyst"` deja de ser válida. Toda
corrida autenticada registra al actor real.

## Modelo de datos

### `portal_configurations`

Una fila por proyecto, con `UNIQUE(project_id)`:

```text
id
project_id
status                    "draft" | "active"
document_json             portal_config.v1
revision                  INTEGER, inicia en 1 y sube en cada guardado
logo_bytes                BLOB/BYTEA | null
logo_media_type           "image/png" | "image/jpeg" | null
updated_at
updated_by_user_id
```

El binario es la única excepción a la regla de guardar la configuración dentro
del documento. No se codifica como data URI. Subir o borrar el logo incrementa
`revision`.

### `operator_consoles`

N filas por caso, sin límite artificial:

```text
id
case_id
owned_variant_id          variante clonada y exclusiva de la consola
status                    "draft" | "active"
document_json             operator_console_config.v1
revision                  INTEGER, inicia en 1 y sube en cada guardado
prepared_by_user_id
waiting_since             timestamp | null
created_at
created_by_user_id
updated_at
updated_by_user_id
```

La fila es la identidad estable. Cambiar el documento no crea otra consola ni
otra variante. Una consola `draft` no aparece ni responde por id a un
`external`.

### `operator_console_parameter_overrides`

El operador nunca escribe el draft. Sus valores se guardan como overlay propio
de la consola:

```text
console_id
asset_id
field
value
updated_at
updated_by_user_id
PRIMARY KEY (console_id, asset_id, field)
```

El documento expone un parámetro mediante `{asset_id, field}`, pero el frontend
externo solo conoce el `id` opaco declarado en la configuración. Un override
deja de aplicarse si el campo ya no está expuesto o no existe, pero no se borra;
vuelve a aplicar si reaparece el mismo puntero.

El overlay se aplica al `system_case` materializado **después** de calcular la
provenance del caso base. El hash `parameters` sigue representando el caso del
analista. El valor efectivo queda congelado en la versión inmutable de la
corrida.

### `operator_console_series_copies`

Cada selección operativa apunta a un set plano no derivado:

```text
id
console_id
time_series_set_id         copia operativa
origin_set_id
origin_revision_number
created_at
created_by_user_id
archived_at                timestamp | null
lease_holder_user_id       user id | null
lease_heartbeat_at         timestamp | null
lease_expires_at           timestamp | null
```

La revisión vigente no se duplica: es
`MAX(time_series_set_revisions.revision_number)` para el set copiado.

La primera edición aceptada crea la copia y redirige únicamente el binding de
la variante de la consola. Si varias columnas usan el mismo set, comparten una
copia. Elegir otra fuente nombrada crea otra copia y archiva la anterior. Las
copias archivadas no se eliminan automáticamente.

La copia conserva el set y revisión de origen como linaje inerte, no como
`validation_dependencies`. Nunca se regenera y no puede quedar stale por la
receta original.

### Reutilización de entidades existentes

No se crean sistemas paralelos para:

- variantes, bindings y `validation_dependencies`;
- sets, periodos, señales, valores y revisiones;
- versiones inmutables, corridas y artefactos;
- publicaciones y su allowlist de descargas.

`validation_dependencies` ya permite actualizar puntualmente
`(owner_type, owner_id, dependency_type, dependency_id)`. El guardado de la
copia usa esa dirección para refrescar solo el `recorded_hash` correspondiente.

## Documentos de configuración

### Reglas comunes

Los documentos se validan contra esquemas en código y se rechazan completos si
el `schema_version` es desconocido o la forma no coincide. No hay migración
silenciosa entre versiones.

Las listas son ordenadas. Sus `id` son únicos dentro del documento, estables y
aptos para viajar al frontend. Los punteros, claves de señal y claves de
catálogo son internos y nunca sustituyen esos ids en un payload externo.

La configuración no tiene historial: `revision`, `updated_at` y `updated_by`
dan concurrencia y auditoría, no reconstrucción. Un cambio sobre una fila
`active` entra en vivo.

### `portal_config.v1`

Forma normativa:

```json
{
  "schema_version": "portal_config.v1",
  "display_name": "Plan operativo Cliente Norte",
  "sections": {
    "kpis": {
      "enabled": true,
      "label": "Resumen",
      "items": [
        {
          "id": "beneficio_total",
          "path": "objective_value_usd",
          "label": "Beneficio total",
          "unit": "USD",
          "decimals": 0,
          "sign": "auto",
          "emphasis": "strong"
        }
      ]
    },
    "charts": {
      "enabled": true,
      "label": "Resultados",
      "items": [
        {
          "id": "intercambio_red",
          "chart_key": "grid_import_export",
          "label": "Intercambio con la red",
          "series": [
            {"key": "grid_import_mw", "label": "Compra"},
            {"key": "grid_export_mw", "label": "Venta"}
          ]
        }
      ]
    },
    "tables": {
      "enabled": true,
      "label": "Detalle",
      "items": [
        {
          "id": "despacho_sistema",
          "table_key": "system_dispatch",
          "label": "Despacho del sistema",
          "row_limit": 24,
          "columns": [
            {"key": "timestamp", "id": "periodo", "label": "Periodo", "unit": null},
            {"key": "grid_import_mw", "id": "compra", "label": "Compra", "unit": "MW"}
          ]
        }
      ]
    },
    "downloads": {"enabled": true, "label": "Descargas"}
  }
}
```

Reglas:

- el orden macro siempre es identidad/publicación, KPIs, gráficos, tablas y
  descargas;
- `path` admite de uno a tres segmentos separados por punto, sin comodines;
- un KPI inexistente se omite sin romper el informe;
- `chart_key`, claves de serie, `table_key` y claves de columna pertenecen a
  catálogos fijos del backend;
- `all_series` y `plot_series` no son claves aceptadas;
- `display_name` es el único campo textual de marca; el logo vive en columnas;
- la publicación sigue decidiendo corrida, título, comentario, fecha y
  artefactos descargables. La configuración no ensancha esa allowlist.

### `operator_console_config.v1`

Forma normativa:

```json
{
  "schema_version": "operator_console_config.v1",
  "public_identity": {
    "name": "Plan diario Planta Norte",
    "description": "Ajuste de disponibilidad y corrida diaria"
  },
  "parameters": [
    {
      "id": "potencia_bess",
      "pointer": {"asset_id": "battery_1", "field": "power_max_mw"},
      "label": "Potencia máxima BESS",
      "unit": "MW",
      "min": 0,
      "max": 100,
      "default": 40
    }
  ],
  "groups": [
    {
      "id": "potencia",
      "label": "Potencia",
      "granularities": ["day", "week", "month", "full_horizon"],
      "columns": [
        {
          "id": "demanda",
          "signal": {
            "entity_type": "component:load",
            "entity_id": "load_1",
            "signal_key": "load_demand_mw"
          },
          "label": "Demanda",
          "editable": true,
          "source_options": [
            {"id": "base", "label": "Demanda base", "time_series_set_id": 18}
          ],
          "default_source_option_id": "base"
        }
      ]
    }
  ],
  "results": {
    "kpis": [],
    "charts": [],
    "tables": []
  }
}
```

Reglas:

- solo se exponen escalares directos de nodo; no listas, curvas ni campos
  anidados;
- `min`, `max` y `default` son presentación y validación de la consola, no
  cambios al draft;
- cada columna declara una señal, su etiqueta, si es editable y las fuentes
  nombradas que el operador puede elegir;
- `unit` y `nonnegative` no se duplican: se derivan del registro canónico;
- un grupo puede mezclar columnas de copias distintas;
- las granularidades forman el enum cerrado `day | week | month |
  full_horizon`;
- `results` usa la misma gramática de KPI, gráfico y tabla que el portal;
- no existe configuración de locale numérico.

## Contratos de payload

### Regla de construcción

`app/surface_payloads.py` contiene funciones puras que enumeran los campos
permitidos. La configuración se aplica después de esa allowlist fija. Un
`response_model` puede servir de segunda barrera, pero no reemplaza el armado
explícito.

### `portal_payload`

La enmienda de marca reemplaza `project {name}` por `branding`:

```text
portal_payload
  branding      { display_name, logo_url }
  publication   { title, comment, published_at }
  period        { start, end }
  results_state "available" | "unavailable"
  results       results_block | null
  downloads     [ { label, media_type, byte_size, download_url } ]
```

`display_name` llega resuelto por el backend: configuración o, en su ausencia,
`project.name`. `logo_url` es `null` cuando no hay logo; nunca apunta al brand
mark `Z`. `project.description` deja de mostrarse deliberadamente. Es una
regresión consciente: el comentario público vive en la publicación.

El periodo se deriva de los timestamps de resultados. `scenario`,
`scenario_version` y `run` no tienen representación. Un error técnico de
artefacto solo produce `results_state = "unavailable"`.

### `results_block`

```text
results_block
  kpis    [ { id, label, value, unit, decimals, sign, emphasis } ]
  charts  [ { id, label, x_labels,
              series: [ { label, unit, values } ] } ]
  tables  [ { id, label,
              columns: [ { id, label, unit } ],
              rows: [ { <column_id>: value } ],
              row_limit } ]
```

La clave canónica de un KPI, serie o columna no viaja. Las dos superficies usan
este mismo constructor. El registro de salida y el de entrada siguen siendo
vocabularios independientes.

### `console_payload`

```text
console_payload
  console      { id, name, description, prepared_by, updated_at }
  period       { available_start, available_end,
                 selected_start, selected_end }
  parameters   [ { id, label, unit, min, max, default, value } ]
  groups       [ { id, label, granularities,
                   columns: [ { id, label, unit,
                                nonnegative, editable } ] } ]
  run_gate     { can_run, reason, message, contact, editing_locked_by }
  history      [ { id, started_at, state,
                   duration_seconds, triggered_by } ]
```

Las filas se solicitan aparte:

```text
group_values
  group_id
  granularity
  rows [ { index, timestamp,
           values: { <column_id>: number | null } } ]
```

La respuesta de valores incluye un `ETag` opaco. El guardado exige
`If-Match`; así existe control optimista sin exponer `revision`, ids de sets o
ids de copias. Un cambio en cualquiera de las copias del grupo invalida el
token.

`run_gate.reason` usa únicamente:

```text
null | dependencia_movida | campo_no_disponible
     | edicion_sin_guardar | guardado_en_curso | edicion_de_otro_usuario
```

Los dos primeros llevan una frase accionable y `contact` = nombre de quien
preparó la consola. Las razones crudas de `VariantStaleError` permanecen en la
superficie interna.

### Errores de celda y de corrida

Un error de guardado apunta a coordenadas externas:

```text
save_error
  message
  cells [ { group_id, column_id, row_index, message } ]
  total_cells
  shown_cells
```

Se muestran como máximo 100 celdas, aunque se validan todas. El guardado sigue
siendo todo-o-nada.

Los estados de corrida se traducen a:

```text
en_espera | ejecutando | lista | fallida
```

Un fallo usa:

```text
failure { cause, message, reference }
```

`cause` puede ser `rango_sin_cobertura`, `serie_incompleta`,
`parametro_fuera_de_rango` o `ejecucion_fallida`. El último cubre todo fallo de
Julia y entrega como `reference` el id de corrida para que el operador lo
comunique al ingeniero. No se parsea `stderr`.

### Prueba negativa de frontera

Los tests serializan ambos sobres sobre datos completos y fallan si aparece una
de estas claves:

```text
workspace_path      input_snapshot_path   output_dir          summary_path
stdout_log_path     stderr_log_path       stdout              stderr
exit_code           error_message         source_identifiers  system_case
case_name           schema_version        version_number      validation_payload
generation_metadata asset_counts          signal_key          asset_id
dependency_type     dependency_id         content_hash        revision
set_id              variant_id            case_id             scenario_id
scenario_version_id dashboard_template_id created_by          updated_by
all_series          plot_series
```

También falla si una cadena contiene la raíz de artefactos del servidor. Los
ids de activo pueden aparecer como **valores** de una tabla de despacho por
activo, pero nunca como clave de contrato.

## API interna de configuración

Todos estos endpoints requieren `admin` o `analyst`, salvo la administración
de capacidades, que exige `admin`.

### Portal

| Método y ruta | Contrato |
| --- | --- |
| `GET /api/projects/{project_id}/portal-configuration` | Devuelve fila, documento, estado, revisión y metadata de auditoría. |
| `PUT /api/projects/{project_id}/portal-configuration` | Reemplazo total validado; exige revisión esperada y sube el contador. |
| `PUT /api/projects/{project_id}/portal-configuration/logo` | Acepta un único PNG/JPEG de hasta 256 KB; reemplaza bytes y sube revisión. |
| `DELETE /api/projects/{project_id}/portal-configuration/logo` | Deja ambos campos de logo en `null` y sube revisión. |
| `GET /api/publications/{publication_id}/preview` | Conserva la ruta actual, pero usa el constructor real de `portal_payload`. |

No se agrega otro endpoint de preview. El existente debe mostrar exactamente lo
que verá el cliente, incluida marca, omisiones y URLs de descarga adaptadas al
contexto interno.

### Consolas

| Método y ruta | Contrato |
| --- | --- |
| `GET /api/scenarios/{scenario_id}/consoles` | Lista interna con estado, bloqueos, `waiting_since`, origen de copia y detalle técnico. |
| `POST /api/scenarios/{scenario_id}/consoles` | Crea identidad, clona una variante elegida y guarda `operator_console_config.v1` en `draft`. |
| `GET /api/scenarios/{scenario_id}/consoles/{console_id}` | Lee documento, auditoría, variante propia, copias, overrides y razones técnicas. |
| `PUT /api/scenarios/{scenario_id}/consoles/{console_id}` | Reemplaza documento/estado con revisión esperada; edición de `active` entra en vivo. |
| `POST /api/scenarios/{scenario_id}/consoles/{console_id}/restore-series/{copy_id}` | Internos restauran una revisión anterior como revisión nueva; nunca reescribe historia. |

`dependencia_movida` se desbloquea invocando el endpoint existente de validar
la variante propia. `campo_no_disponible` se desbloquea corrigiendo el documento
de configuración. No se crea un gesto único falso para ambos estados.

### Capacidades

| Método y ruta | Contrato |
| --- | --- |
| `GET /api/admin/projects/{project_id}/external-access` | Lista usuarios y capacidades. |
| `PUT /api/admin/projects/{project_id}/external-access/{user_id}` | Reemplaza `{portal_view, operate}`. |
| `DELETE /api/admin/projects/{project_id}/external-access/{user_id}` | Revoca ambas capacidades. |

Las rutas actuales `client-access` se reemplazan junto con el frontend; no son
contrato público y frontend/backend se despliegan juntos.

## API de la consola

El prefijo `/api/console` se registra explícitamente en
`require_authenticated_app_boundary`. Para `external` exige `operate` sobre el
proyecto de la consola. Para `admin`/`analyst` permite la prueba interna.

| Método y ruta | Contrato |
| --- | --- |
| `GET /api/console` | Lista cruzada por proyecto; cada fila lleva solo `console {id,name,description}`, `project {name}` y estado visible. |
| `GET /api/console/{console_id}` | Devuelve `console_payload`; `draft` o acceso ajeno responde 404 a `external`. |
| `GET /api/console/{console_id}/groups/{group_id}/values?start=&end=&granularity=` | Devuelve `group_values` y `ETag`; el tramo debe estar permitido y cubierto. |
| `POST /api/console/{console_id}/groups/{group_id}/lease` | Adquiere atómicamente los leases de todas las copias que toca el grupo y devuelve token opaco. |
| `PUT /api/console/{console_id}/groups/{group_id}/lease` | Heartbeat del titular. |
| `DELETE /api/console/{console_id}/groups/{group_id}/lease` | Libera los leases del titular. |
| `PUT /api/console/{console_id}/groups/{group_id}/values` | Guardado multi-set, todo-o-nada; exige lease e `If-Match`. |
| `POST /api/console/{console_id}/groups/{group_id}/undo` | Deshace solo el último guardado propio si sigue vigente; crea revisión nueva. |
| `GET /api/console/{console_id}/groups/{group_id}/history` | Historial reducido: actor, fecha, rango, celdas, nota y comparación. |
| `GET /api/console/{console_id}/series-options` | Devuelve ids y nombres externos permitidos por columna. |
| `PUT /api/console/{console_id}/series-selections` | Cambia fuentes nombradas; crea/activa copias y archiva las sustituidas atómicamente. |
| `PUT /api/console/{console_id}/parameters` | Reemplaza overrides por ids externos; valida rangos y guarda actor. |
| `POST /api/console/{console_id}/runs` | Materializa con periodo, overrides y bindings vigentes, crea versión inmutable y encola corrida. |
| `GET /api/console/{console_id}/runs` | Historial operativo reducido y compartido. |
| `GET /api/console/{console_id}/runs/{run_id}` | Estado, fallo traducido y `results_block` configurado. |
| `GET /api/console/{console_id}/run-comparison?left=&right=` | Devuelve los dos bloques configurados para comparación, sin metadata técnica. |
| `POST /api/console/{console_id}/request-review` | Escribe `waiting_since` si existe bloqueo fail-closed; no envía notificación. |

El lease es por copia, aunque la API lo presenta por grupo. La adquisición del
grupo triunfa para todas las copias o para ninguna. Solo el titular guarda o
deshace. El lease coordina personas; `If-Match` es la garantía de integridad.
`admin` puede liberar forzosamente desde la superficie interna.

## API del portal

Se conservan las rutas existentes y se cambia su payload:

| Método y ruta | Contrato |
| --- | --- |
| `GET /api/client/projects` | Proyectos con publicaciones visibles; sin campos internos. |
| `GET /api/client/projects/{project_id}/publications` | Publicaciones `published` del proyecto. |
| `GET /api/client/projects/{project_id}/publications/{publication_id}` | Devuelve `portal_payload`. |
| `GET /api/client/projects/{project_id}/branding/logo` | Sirve bytes solo con `portal_view`, `ETag` por revisión y `Cache-Control: private, must-revalidate`. |
| `GET /api/client/projects/{project_id}/publications/{publication_id}/artifacts/{artifact_type}/download` | Conserva la intersección con la allowlist de la publicación. |

El logo nunca se sirve bajo `/react/*`, porque ese prefijo entrega el shell sin
gate de rol.

## Semántica de edición de series

### Tabla y pegado

La consola muestra una tabla por grupo configurado. El particionado visual no
coincide necesariamente con los sets: un grupo puede tocar N copias y el
backend resuelve esa relación.

- Tabla y gráfico muestran las mismas columnas y el mismo tramo; gráfico es
  read-only.
- El pegado rectangular se alinea desde la celda anclada hacia abajo y a la
  derecha.
- Una primera fila sin dígitos se trata como encabezado accidental, se omite y
  se avisa.
- Las columnas no editables se omiten, se nombran en el aviso y se distinguen
  con candado/trama.
- El tramo seleccionado limita edición y pegado. El excedente se trunca con un
  aviso persistente hasta guardar o descartar.
- El pegado nunca crea periodos ni señales. Extender horizonte es trabajo del
  ingeniero.
- Se permite `full_horizon`; no hay límite contractual menor que el cuerpo HTTP
  general. La tabla virtualiza 8760 filas y solo conserva en memoria celdas
  sucias.
- La revisión previa y el diff siempre están disponibles, pero no son paso
  obligatorio.

### Parser numérico

No hay locale configurable. Si aparecen ambos separadores, el último es
decimal; separadores repetidos forman miles. Se rechaza el caso estructuralmente
ambiguo de un único separador seguido de tres dígitos con grupo de miles válido:
`1.234`, `1,234`, `12,345`.

Ejemplos aceptados:

- `1.234,5` y `1,234.5` -> `1234.5`;
- `1.234.567` -> `1234567`;
- `1234,567` -> `1234.567`;
- `0,001` -> `0.001`.

La validación cubre número, finitud, no negatividad según registro, ambigüedad,
periodo, columna y conflicto de concurrencia. Un error invalida todo el bloque.

### Revisión, deshacer y restaurar

Cada guardado aceptado crea una revisión por copia tocada dentro de una única
transacción. Registra valores antes/después, actor, consola, revisión de
configuración, rango, cantidad de celdas y nota.

El operador solo deshace su último guardado y solo si sigue vigente. Deshacer
crea revisión. `admin` y `analyst` pueden restaurar cualquier revisión anterior,
también como revisión nueva.

### Fail-closed y atestación

Guardar, deshacer o restaurar por la API de consola:

1. valida todas las celdas y revisiones base;
2. crea todas las revisiones de copia;
3. calcula sus nuevos hashes;
4. refresca únicamente las dependencias `time_series_set` de la variante de la
   consola; y
5. confirma todo en una transacción.

No existe ventana de atestación parcial. Topología y parámetros grabados en la
variante no se refrescan. Cualquier escritura fuera de esta API deja stale la
variante de forma normal.

Editar y correr siguen siendo dos operaciones. Mientras haya cambios sucios o
un guardado en curso, `run_gate.can_run` es falso. La consola nunca llama al
endpoint de revalidar variante.

En cada corrida siguen ejecutándose los chequeos duros existentes: bindings
requeridos, sets derivados vigentes, cobertura exacta, ausencia de huecos o
solapes y valores completos.

## Materialización y ejecución

La consola posee una variante clonada de una variante del analista. Sus
bindings apuntan a las copias operativas. La materialización sigue el pipeline
actual con dos adiciones acotadas:

1. resuelve bindings, cobertura y provenance como hoy;
2. aplica los overrides de parámetros sobre la copia materializada del
   `system_case`, sin tocar el draft ni el hash del caso base;
3. crea una `scenario_version` inmutable con los valores efectivos y la
   revisión exacta de cada copia;
4. crea la corrida con actor y origen `operator_console`; y
5. encola usando el mismo ejecutor Julia e indexador de resultados.

Un stale ajeno o puntero roto bloquea antes de crear versión o corrida. Un
fallo de Julia conserva todo su detalle para internos y devuelve al operador
solo el genérico con referencia.

## Comportamiento de las superficies

### Consola de operador

Es una sola mesa de trabajo, en este orden fijo:

1. identidad pública, rango disponible, última actualización y preparador;
2. periodo y parámetros expuestos;
3. grupos de series con tabs y alternancia Tabla/Gráfico;
4. resumen lateral persistente con cobertura y acción Ejecutar;
5. historial reciente con apertura de resultados y comparación de dos corridas.

Estados obligatorios:

- carga inicial y carga por grupo identificables, sin mostrar ids internos;
- cambios sin guardar y guardado en curso deshabilitan Ejecutar;
- lease ajeno deja lectura habilitada y muestra el nombre del editor;
- `en_espera` permite abandonar la página y muestra espera/posición cuando esté
  disponible;
- `ejecutando` muestra progreso y estimación cuando el runner las entregue;
- fallo previo al motor enlaza al grupo/parámetro corregible;
- fallo del motor muestra mensaje genérico y referencia;
- stale ajeno o puntero roto bloquea, traduce y permite solicitar revisión.

El operador nunca ve escenario, caso, variante, binding, revisión de set ni
versión inmutable.

### Portal cliente

Es un informe lineal de una publicación:

1. marca del proyecto y contexto de publicación;
2. título, periodo, comentario y fecha;
3. KPIs;
4. gráficos configurados;
5. tablas configuradas;
6. descargas aprobadas.

El cliente lee, desplaza y descarga. No reordena, explora un dashboard, edita ni
ejecuta. Carga y vacío usan vocabulario español de producto. Resultados no
disponibles no exponen nombres de artefactos o errores técnicos.

### Superficie interna del ingeniero

La lista de consolas vive en el workspace de escenario, junto a las variantes.
No hay bandeja ni vista global nueva.

Cada fila muestra nombre, `draft|active`, bloqueo
`ninguno|dependencia_movida|campo_no_disponible`, `waiting_since` y un badge si
la revisión de origen de una copia quedó atrás respecto del set canónico.

- `dependencia_movida`: botón sobre la validación existente de variante;
- `campo_no_disponible`: enlace al parámetro roto dentro del editor;
- copia vieja: aviso informativo; no bloquea ni regenera;
- fallo con referencia: enlace interno a `runs/:runId`, donde ya viven
  `exit_code` y `stderr`.

Al guardar topología o parámetros del caso, la respuesta incluye las consolas
`active` que quedarán bloqueadas. La advertencia es síncrona e informativa; no
cancela el guardado. `request-review` solo escribe `waiting_since`. No hay inbox,
email, escalamiento a admin ni caducidad.

## Navegación y aterrizaje

Hay tres raíces hermanas sin header compartido:

| Raíz | Rutas | Layout |
| --- | --- | --- |
| Analista | `/projects/*`, `/scenarios/*`, `/runs/*`, `/scenario-versions/*`, `/publications/*`, `/system`, `/admin/users` | El actual. |
| Consola | `/console`, `/console/:consoleId` | Identidad del plan, usuario y salir. |
| Portal | `/client/*` | Marca del proyecto y navegación de informe. |

Configurar una consola usa
`/scenarios/:scenarioId/consoles/:consoleId`; operar o probar usa
`/console/:consoleId`. Un interno probando ve una franja delgada con enlace de
vuelta, sin impersonación.

`/console` lista consolas cruzadas por proyecto y nunca redirige. No usa
breadcrumbs ni selector de proyecto.

`/api/auth/me` y login devuelven `landing_path`, calculado una sola vez en el
backend:

1. `next` seguro y permitido;
2. interno -> `/projects`;
3. `external` con `operate`: una consola visible -> su ruta; cero o varias ->
   `/console`;
4. `external` sin `operate` -> `/client`.

`operate` gana a `portal_view`. El frontend elimina su cálculo local. Se
reemplazan los diecinueve `isClient` por tres guardas de raíz; `/admin/users`
conserva su chequeo interno de `admin`.

Para un `external`, una raíz u objeto no permitido responde 404, incluido
`runs/:runId` aunque conozca la referencia. Para un interno autenticado sin
permiso, `/admin/users` responde 403.

La regla actual está triplicada en `app/main.py:585`, `app/main.py:589` y
`frontend/src/App.tsx:66`; la implementación debe eliminar las copias, no solo
agregar una cuarta.

## Marca del portal

La marca por proyecto tiene exactamente dos elementos:

- `display_name` en `portal_config.v1`;
- un logo PNG/JPEG de un único slot y hasta 256 KB.

No se validan dimensiones; CSS limita el alto. SVG se rechaza. En rutas del
portal, `<title>` usa `display_name` ya resuelto. Sin `display_name`, se usa
`project.name`; sin logo, no se muestra ninguno. Nunca hay fallback a `Z` o
`BESS Workspace`.

La marca no se versiona y su edición sobre una configuración activa es en vivo.
Un informe histórico reabierto usa la marca vigente, mientras sus resultados
siguen viniendo de su snapshot inmutable.

## Estrategia de validación de la configuración

El corte MVP tiene dos capas y ninguna tercera:

1. **Rechazo estructural al guardar:** schema version, tipos, campos requeridos,
   enums, unicidad de ids y forma del documento.
2. **Fail-closed al cargar/usar:** punteros, señales, fuentes, rangos y
   dependencias se resuelven contra el caso y datos vigentes.

No existe linter semántico al guardar. Un default fuera de rango, señal que el
caso no requiere o puntero que luego quedó colgando puede persistir y se detecta
al probar/abrir. El preview real del portal y la prueba de consola son el ciclo
corto del configurador.

## Compatibilidad y migración

La migración es aditiva y no reescribe historia:

1. `users.role = 'client'` pasa a `external`.
2. Cada fila vigente de `project_client_access` gana `portal_view = true` y
   `operate = false`; ningún permiso se amplía.
3. Se crean tablas/columnas nuevas y esquemas v1.
4. Por proyecto, se crea `portal_configurations` desde la plantilla usada por
   la publicación publicada más reciente. Sus flags se convierten en entradas
   explícitas de catálogos; `table_preview_limit` se conserva por tabla.
5. Si un proyecto con publicaciones no tiene plantilla utilizable, se crea una
   configuración segura con listas explícitas vacías y descargas gobernadas
   solo por la publicación. Nunca se habilita `all_series` por fallback.
6. `dashboard_templates` no se borra ni se sigue leyendo. Queda como dato
   legacy muerto.
7. Las publicaciones conservan corrida, título, comentario, fecha, estado y
   artefactos. `dashboard_template_id` deja de elegir presentación y no cruza
   payloads.
8. El preview de publicación cambia al constructor común.
9. No se crean consolas automáticamente; nacen en `draft` por acción interna.

Frontend y backend se despliegan juntos, por lo que no se emite versión del
payload ni se mantiene negociación entre clientes. Los documentos persistidos
sí llevan `schema_version`.

## Extensibilidad del registro canónico de señales

La tabla editable consume el registro; no conoce señales por nombre. El registro
se expone a internos mediante:

```text
GET /api/time-series/signal-catalog
-> [ { signal_key, unit, entity_type, nonnegative } ]
```

Pasa por `require_authenticated_app_boundary` y reemplaza
`frontend/src/timeSeriesCatalogMapping.ts`. La derivación one-bus cambia
`_ONE_BUS_ENTITY_SIGNALS` de una tupla por tipo a una lista de tuplas. Los
caminos one-bus e hidráulico siguen separados, pero ambos producen
`{entity_type, entity_id, signal_key}`.

Después de esos dos cambios, agregar una señal vectorial sigue esta receta:

1. `app/time_series_catalog.py`: definición declarativa;
2. `app/required_signals.py`: requisito declarativo por tipo;
3. motor Julia: campo/parseo según contrato, irreducible;
4. `app/draft_editor.py`: materialización del campo nombrado;
5. `app/time_series_ingestion.py`: mapeo de importación, aún no declarativo;
6. cada `operator_console_config.v1` que deba mostrarla: etiqueta/fuente;
7. `app/result_indexing.py` solo si además existe una señal de salida.

Agregar una señal vectorial no equivale a convertir un escalar en serie. Lo
segundo mueve un campo del struct del activo a datos por periodo y cambia una
cota JuMP de escalar a indexada. Esa evolución requiere v4 o una ampliación de
v3; nunca se describe como “crear v3”, porque v3 ya es el contrato hidráulico.

La tabla de operador, parser, payload externo y mapeo de unidades frontend ya no
son lugares que se tocan por señal.

## Criterios de aceptación

Una suite `tests/test_configuration_layer_acceptance.py`, complementada por
tests React y browser, debe demostrar al menos estas historias de extremo a
extremo:

1. **Migración sin ampliación:** un `client` queda `external + portal_view`, ve
   las mismas publicaciones y no puede listar ni abrir consolas.
2. **Capacidades independientes:** `portal_view`, `operate` y ambas producen
   exactamente las raíces y endpoints previstos; revocar afecta el siguiente
   request.
3. **Aterrizaje único:** login y `/api/auth/me` entregan el mismo
   `landing_path`; no existe cálculo React alternativo.
4. **Configuración estructural:** versiones o formas inválidas se rechazan sin
   escribir; una configuración activa válida incrementa revisión y auditoría.
5. **Fail-closed semántico:** un puntero colgando puede estar persistido pero
   bloquea la consola con `campo_no_disponible` y no crea corrida.
6. **Aislamiento de parámetros:** editar un parámetro no toca el draft ni el
   hash `parameters`; la versión de corrida contiene el valor efectivo.
7. **Primera edición de serie:** crea un set plano, conserva origen, redirige
   solo la variante propia y no modifica el set canónico ni variantes ajenas.
8. **Guardado multi-set:** un grupo que toca dos copias crea ambas revisiones y
   refresca ambos hashes en una transacción; un conflicto en una deja todo
   intacto.
9. **Stale propio/ajeno:** el guardado propio permite correr sin revalidación;
   un cambio de topología o parámetros del analista bloquea y no se limpia por
   guardar otra serie.
10. **Lease y concurrencia:** solo el titular guarda; heartbeat y expiración
    funcionan; un `If-Match` viejo rechaza sin `last-write-wins`.
11. **Parser y pegado:** acepta formatos inequívocos, rechaza `1.234` y
    `12,345`, direcciona errores por celda, limita la respuesta a 100 y no
    escribe parcialmente.
12. **Tramo:** un pegado desbordado se trunca con aviso persistente y nunca crea
    periodos fuera del set.
13. **Deshacer:** solo revierte el último guardado propio vigente y lo hace con
    una revisión nueva; restauración interna tampoco reescribe historia.
14. **Corrida operativa:** actor, configuración, overrides y revisiones exactas
    quedan en lineage; el pipeline Julia e indexado son los comunes.
15. **Fallo seguro:** un error pre-motor es accionable; un fallo Julia entrega
    referencia pero nunca `stdout`, `stderr` o `exit_code` al operador.
16. **Frontera de payload:** al agregar columnas sensibles falsas a filas de
    DB y claves desconocidas a `summary.json`, ninguna aparece en portal,
    consola o preview.
17. **Resultados configurados:** solo salen KPIs, gráficos, series, tablas y
    columnas declarados; KPI ausente se omite; `all_series` nunca sale.
18. **Preview fiel:** preview interno y portal producen el mismo cuerpo salvo
    URLs adaptadas al contexto.
19. **Marca:** nombre configurado/fallback y ausencia de logo cumplen la regla;
    PNG/JPEG <= 256 KB funciona con ETag; SVG, otro MIME o exceso se rechaza;
    la ruta requiere acceso.
20. **Regresión consciente:** `project.description`, `Z` y `BESS Workspace` no
    aparecen en el portal.
21. **Ingeniero advertido:** guardar un caso enumera consolas activas afectadas
    sin bloquear el guardado; `request-review` marca `waiting_since`.
22. **Dos desbloqueos:** validar variante resuelve `dependencia_movida`; editar
    configuración resuelve `campo_no_disponible`; una acción no finge resolver
    el otro estado.
23. **Copia vieja:** una nueva revisión canónica produce badge interno y no
    bloquea al operador.
24. **404 externo:** una consola draft/ajena, una ruta interna y
    `/runs/{reference}` responden 404 a `external`; un `analyst` sin admin ve
    403 en `/admin/users`.
25. **Catálogo de señales:** el frontend deriva opciones/unidades del endpoint;
    una entrada nueva no requiere editar la tabla, parser ni payload externo.

La prueba browser mínima recorre: login de operador -> aterrizaje -> adquisición
de lease -> pegado -> guardado -> corrida -> resultado -> comparación; y login
de cliente -> publicación -> marca -> resultados -> descarga autorizada.

## Fuera de alcance

- Simplificar o fusionar Draft, Caso, Variante, Rango y Versión inmutable.
- Exponer o editar el diagrama hidráulico/topología desde la consola. Los casos
  hidráulicos y la unificación de editores requieren un esfuerzo separado.
- Implementar límites de potencia por unidad variables en el tiempo o cambiar
  ahora el contrato Julia.
- Unificar los mecanismos one-bus e hidráulico de señales requeridas.
- Carga CSV/XLSX por el operador; el mecanismo es tabla y pegado.
- Edición de modelos por el cliente read-only.
- Colores, tipografía, tema, favicon, dominio propio o white-label.
- Marca propia en la consola de operador.
- i18n y negociación de idioma.
- Historial/reversión de configuraciones o marca histórica.
- Linter semántico al guardar.
- Paginación nueva de resultados/historial, límites de payload menores o
  optimizaciones físicas sin una medición que las justifique.
- Inbox, email, push, caducidad o escalamiento automático de bloqueos.
- Registrar quién movió una dependencia.
- Regenerar automáticamente copias operativas desde su origen.
- Onboarding o manual del ingeniero configurador. Se redacta después de
  implementar y estabilizar el spec, como documentación de producto separada.

## Handoff

Este documento termina el wayfinding. El siguiente paso es convertirlo en
tickets de implementación con `/to-tickets`, manteniendo slices verticales que
atraviesen persistencia, autorización, payload, UI y aceptación. Ningún ticket
de implementación debe reabrir las decisiones anteriores salvo evidencia de
que una invariantes existente hace el contrato imposible.
