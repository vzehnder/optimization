---
id: 05
title: "Contrato de consulta y API del catalogo global"
map: catalogo-global-series-genericas
label: wayfinder:grilling
status: closed
assignee: codex
blocked_by: [01, 02, 04]
---

## Question

¿Que recursos y contratos de API necesita la vista global para buscar señales
individuales y operar sus vinculos sin cargar valores masivos?

Debe definir endpoints, filtros combinables, orden, paginacion estable,
resumenes de cobertura/resolucion/vinculos, detalle y preview acotado, secciones
de entradas/resultados/legacy, descubrimiento de objetos compatibles,
prevalidacion de operaciones masivas, errores y control de concurrencia. Debe
dejar claro que datos se calculan en consulta, cuales se indexan y cuales nunca
cruzan el limite de la lista.

## Resolucion

Resuelto el 2026-08-30 con la autorizacion del usuario de adoptar la
recomendacion propuesta para todas las decisiones y preguntas de este ticket.

### Decision

La API nueva es **signal-first** para entradas y mantiene tres recursos
separados bajo un mismo namespace:

- `inputs` contiene senales canonicas individuales y es la unica seccion que
  permite asociar o vincular;
- `results` expone descriptores y previews de resultados en modo read-only;
- `legacy` expone el adaptador de series antiguas y su estado de migracion,
  pero no permite crear vinculos nuevos.

Las tres secciones comparten convenciones de filtros, cursores, cobertura,
resolucion, errores y capacidades, pero no una lista polimorfica ni un cursor
unico. Esto evita que una identidad de resultado o legacy se confunda con
`time_series_signals.id` y conserva la separacion fisica ya decidida.

Toda lista trabaja solo con metadata y resumenes indexables. Los puntos se
obtienen exclusivamente por endpoints de preview acotados o por los flujos de
edicion/materializacion ya autorizados. Ninguna lista carga valores, archivos
fuente, payloads de corrida ni colecciones de vinculos sin limite.

### Superficie de recursos

El namespace canonico es `/api/time-series/catalog`.

| Metodo y ruta | Proposito |
| --- | --- |
| `GET /inputs` | Buscar senales de entrada visibles en todos los proyectos. |
| `GET /inputs/{signal_id}` | Detalle de la identidad estable y su revision vigente. |
| `GET /inputs/{signal_id}/revisions` | Historia paginada de revisiones en que aparece la senal. |
| `GET /inputs/{signal_id}/preview` | Preview acotado de una revision exacta. |
| `GET /inputs/{signal_id}/object-candidates` | Descubrir objetos compatibles para un rol y uso. |
| `GET /results` | Buscar series de resultados indexadas, read-only. |
| `GET /results/{result_series_id}` | Detalle y linaje de un descriptor de resultado. |
| `GET /results/{result_series_id}/preview` | Preview acotado del resultado. |
| `GET /legacy` | Buscar entradas del adaptador legacy. |
| `GET /legacy/{legacy_entry_ref}` | Detalle y estado de migracion de una entrada legacy. |
| `GET /legacy/{legacy_entry_ref}/preview` | Preview acotado mediante el adaptador. |
| `GET /descriptors` | Catalogos paginados para filtros y selectores. |
| `GET /sets/{set_id}` | Detalle administrativo del set que agrupa senales. |
| `GET /associations` | Consultar asociaciones de catalogo con filtros y cursor. |
| `GET /associations/{association_id}` | Estado, evidencia vigente y ETag de una asociacion. |
| `GET /associations/{association_id}/events` | Historia append-only paginada. |
| `POST /association-prevalidations` | Prevalidar un lote sin escribir. |
| `POST /association-batches` | Confirmar atomicamente el lote prevalido. |
| `POST /sets/{set_id}/scope-prevalidations` | Calcular impacto de promocion o despromocion. |
| `POST /sets/{set_id}/scope-changes` | Confirmar el cambio de alcance administrativo. |

Los bindings conservan el contexto de escenario y variante para no aceptar un
`variant_id` aislado como contexto confiable:

| Metodo y ruta | Proposito |
| --- | --- |
| `GET /api/scenarios/{scenario_id}/case-variants/{variant_id}/time-series-bindings` | Lista efectiva e historica de bindings de la variante. |
| `GET /api/scenarios/{scenario_id}/case-variants/{variant_id}/time-series-bindings/{binding_id}` | Detalle, estado derivado y ETag. |
| `GET /api/scenarios/{scenario_id}/case-variants/{variant_id}/time-series-bindings/{binding_id}/events` | Historia append-only paginada. |
| `POST /api/scenarios/{scenario_id}/case-variants/{variant_id}/time-series-binding-prevalidations` | Prevalidar un lote de cambios. |
| `POST /api/scenarios/{scenario_id}/case-variants/{variant_id}/time-series-binding-batches` | Confirmar el lote all-or-nothing. |

Los endpoints de escritura de archivos, revisiones y transformaciones siguen
siendo recursos de set/proyecto. No se convierten en acciones de la fila de
catalogo. El ticket de migracion decidira sus aliases y retiro gradual.

### Contrato comun de colecciones

Toda coleccion nueva responde:

```json
{
  "items": [],
  "page": {
    "limit": 50,
    "has_more": false,
    "next_cursor": null
  },
  "summary": {
    "total_count": 0
  },
  "facets": null,
  "meta": {
    "section": "inputs",
    "catalog_generation": 1842,
    "request_id": "req_..."
  }
}
```

`facets` se calcula solo cuando se solicita `include=facets`; sus conteos se
aplican al conjunto filtrado completo, no solamente a la pagina. `summary` y
facets son exactos para la generacion indicada y nunca recorren
`time_series_values`.

La paginacion es keyset, no acepta `offset` ni numero de pagina:

- `limit` vale 50 por defecto y admite entre 1 y 200;
- el cursor es opaco, firmado, ligado a actor/clase de autorizacion, seccion,
  filtros normalizados, orden, limite y ultima clave;
- cada orden agrega el ID estable como desempate, aunque el cliente no lo
  indique;
- cada seccion tiene una `catalog_generation` monotona. Si cambia un dato que
  podria alterar membresia, orden, resumen o autorizacion entre paginas, el
  cursor no se aplica sobre el estado nuevo: responde
  `TS_QUERY_SNAPSHOT_CHANGED` y el cliente reinicia desde la primera pagina;
- un cursor vence a los 15 minutos y responde `TS_QUERY_CURSOR_EXPIRED`;
- cambiar filtros, orden, seccion o actor al reutilizarlo responde
  `TS_QUERY_CURSOR_MISMATCH`.

Asi la navegacion es estable o falla explicitamente; nunca mezcla en silencio
dos fotografias. La forma fisica del contador de generacion y de los read
models corresponde a "Rendimiento, indices e integridad transaccional".

En filtros repetibles hay OR dentro de la misma dimension y AND entre
dimensiones. Fechas usan RFC 3339 con offset; el servidor las normaliza a UTC.
Claves de catalogo son exactas, case-sensitive y no aceptan nombres visibles.

### Busqueda de entradas

`GET /inputs` acepta los siguientes filtros combinables:

| Parametro | Semantica |
| --- | --- |
| `q` | Texto de hasta 200 caracteres sobre nombre de senal, `series_key`, nombre/version de set, proyecto propietario y fuente visible. |
| `semantic_type_key` | Uno o varios tipos semanticos. |
| `data_class_key` | Una o varias clases (`real`, `forecast`, `programmed`, etc.). |
| `unit_key` | Una o varias unidades canonicas. |
| `owner_project_id` | Uno o varios proyectos propietarios. |
| `visibility_scope` | `project` o `global`. |
| `set_status` | Estado del set. Archivados no aparecen salvo filtro explicito. |
| `signal_status` | Estado de la senal. Archivadas no aparecen salvo filtro explicito. |
| `source_kind` | CSV, conector, manual, transformacion u origen registrado. |
| `covers_from`, `covers_to` | Exige que la revision vigente cubra completamente el intervalo. Deben enviarse juntos. |
| `resolution_seconds_min`, `resolution_seconds_max` | Rango sobre la resolucion nominal indexada. |
| `regularity` | `regular` o `irregular`. |
| `association_object_id` | Senales asociadas al objeto indicado. |
| `association_role_key` | Rol de una asociacion; puede combinarse con objeto y estado. |
| `association_state` | `none`, `active_valid`, `active_stale` o `active_incompatible`. |
| `scenario_id`, `variant_id` | Contexto para filtrar bindings; se envian juntos y el backend comprueba la pertenencia. |
| `binding_state` | `unbound`, `valid_current`, `valid_pinned`, `stale` o `invalid`; requiere escenario y variante. |

Para abrir el catalogo desde un objeto o selector de variante se agrega un
contexto de candidato:

```text
context_linkable_object_id
context_binding_role_key
context_usage = association | execution
context_scenario_id, context_variant_id = ambos requeridos para execution
compatibility = all | allowed | denied
```

Objeto, rol y uso se envian juntos; ejecucion exige ademas el par
escenario/variante. El backend deriva y comprueba el proyecto del objeto y de
la variante; nunca confia en un `project_id` duplicado enviado por la UI. Cada
fila incluye entonces una `compatibility_decision` producida por el evaluador
unico. `compatibility=all` permite mostrar opciones
deshabilitadas con la misma razon que usara el guardado; `allowed` es el modo
de selector rapido. Sin contexto, la lista global no finge que una senal sea
compatible con todos los objetos.

Ordenes permitidos para entradas:

```text
relevance, updated_at, display_name, owner_project_name, semantic_type,
coverage_start, coverage_end, nominal_resolution_seconds,
association_count, binding_count
```

Se antepone `-` para descendente. `relevance` solo es valido con `q`. El orden
por defecto es `-relevance,-updated_at` con texto y
`-updated_at,display_name` sin texto; `signal_id` se agrega siempre como
desempate final.

### Proyeccion de una fila de entrada

Una fila corresponde a una senal, no a un set. Incluye solamente:

- `entry_kind = input` y `signal_id`;
- identidad: `series_key`, `display_name`, descripcion corta y estado;
- set: ID, nombre, version, estado, propietario y `visibility_scope`;
- clasificacion: tipo semantico, clase de datos, unidad, dimension y proposito;
- revision vigente: ID, numero, estado sellado y fecha; el hash completo queda
  en detalle;
- `coverage_summary`: inicio, fin, zona fuente, cantidad de periodos,
  resolucion nominal/minima/maxima y regularidad;
- `origin_summary`: tipo y nombre visible, sin credenciales, rutas ni payload;
- `link_summary`: conteos de asociaciones y bindings por estado, mas banderas
  `has_stale` y `has_invalid`; nunca la lista completa de objetos o variantes;
- `compatibility_decision` solo cuando se envio contexto;
- `capabilities` calculadas para el actor (`view_detail`, `preview`,
  `associate`, `bind`, `edit_set`, `publish_revision`, etc.);
- `resource_version` y links al detalle/subrecursos.

`capabilities` mejora la interfaz, pero no concede permiso: cada accion vuelve
a autorizar. Los conteos de binding globales no revelan variantes a
`external`, porque ese rol es rechazado antes de ejecutar la consulta.

### Detalle, revisiones y preview

`GET /inputs/{signal_id}` agrega el contrato completo del tipo/unidad, metadata
curada del set, revision/hash vigente, fuente y linaje resumidos, resumen de
validaciones, capacidades y URLs paginadas hacia asociaciones y revisiones.
No embebe puntos, eventos, bindings ni asociaciones completos. Responde un
ETag fuerte que incorpora identidad, revision vigente, `scope_revision`,
estado de ciclo de vida y version de contrato observada.
El ETag tambien incorpora la clase de autorizacion/capacidades que afecta la
representacion, por lo que no se reutiliza entre actores distintos.

`GET /inputs/{signal_id}/revisions` lista metadata inmutable de revisiones con
el contrato comun de cursor. No contiene valores.

El preview exige una identidad de contenido explicita:

```text
GET /inputs/{signal_id}/preview
  ?revision_id=<id>
  &from=<RFC3339>
  &to=<RFC3339>
  &sampling=minmax|uniform|none
  &max_points=<1..2000>
```

`revision_id`, `from` y `to` son obligatorios. `max_points` vale 500 por
defecto y nunca supera 2000. `minmax` es el muestreo predeterminado y conserva
extremos por bucket sin exceder el limite total; `uniform` entrega una muestra
uniforme. `none` solo funciona si el rango contiene a lo sumo `max_points`, de
lo contrario responde `TS_PREVIEW_TOO_LARGE`.

La respuesta contiene revision y hash, rango pedido/efectivo, estrategia,
cantidad de puntos fuente y devueltos, unidad y una lista de
`{timestamp_start, timestamp_end, value, quality_flag}`. No tiene cursor ni
puede usarse para descargar una serie completa. Su ETag incluye hash de
contenido y query normalizada. El endpoint vuelve a comprobar pertenencia de
la senal a la revision, sellado, integridad y autorizacion.

### Resultados y legacy

`results` usa un `result_series_id` estable del indice de resultados. Sus
filtros agregan proyecto, escenario, corrida, estado de corrida, tipo de
resultado y fechas de produccion. Una fila incluye unidad, cobertura,
resolucion, corrida/snapshot de origen y capacidades exclusivamente de lectura.
Detalle y preview respetan los mismos limites; no exponen el artifact completo
ni `scenario_version.system_case_json`.

Un resultado nunca anuncia `associate` o `bind`. Si una transformacion
allowlisted lo convierte en entrada, la operacion crea un set/revision/senal
nuevos con linaje; la identidad de resultado no cruza al binding.

`legacy` usa un `legacy_entry_ref` opaco y estable emitido por el adaptador.
Sus filtros agregan tipo legacy, proyecto y
`migration_state = unmigrated | migrated | diverged | unavailable`. La fila
incluye IDs canonicos resultantes cuando ya se migro y capacidades
`view_detail`, `preview` y, si corresponde, `migrate`; nunca `associate` ni
`bind`. Una vez migrada, todo vinculo navega hacia la senal canonica.

Los tres previews comparten forma y limites. La implementacion puede leer
almacenes distintos, pero no cambia el contrato visible. No existe busqueda o
paginacion que mezcle `inputs`, `results` y `legacy` en una sola respuesta.

### Descriptores y descubrimiento de objetos

`GET /descriptors` requiere `kind` y pagina independientemente:

```text
kind = semantic_type | data_class | unit | binding_role | object_type |
       source_kind
```

Acepta `q`, `status`, cursor y contexto de uso. Devuelve claves, nombres,
estado, dimension/unidad y capacidades administrativas, pero no descarga la
matriz completa de compatibilidad para que la UI la reimplemente.

`GET /inputs/{signal_id}/object-candidates` exige:

```text
target_project_id
binding_role_key
usage = association | execution
context_scenario_id, context_variant_id = ambos requeridos para execution
```

Admite `q`, `object_type_key`, `include_denied`, orden y cursor. Cada item
contiene el resumen del `linkable_object` real y una
`CompatibilityDecision` con `allowed`, regla/fingerprint observados, error
primario y todos los errores ordenados. Por defecto retorna solo permitidos;
`include_denied=true` permite explicar opciones deshabilitadas. El endpoint
ejecuta `evaluate_compatibility` sobre los candidatos de la pagina y aplica
alcance, proyecto y actor; no devuelve pares textuales `entity_type/id`.

El flujo inverso, iniciado desde un objeto, usa `GET /inputs` con el contexto
de candidato antes definido. Ambos caminos consumen el mismo evaluador y las
mismas razones estables.

### Prevalidacion de asociaciones

No hay `PATCH` que cambie senal, objeto o rol ni `DELETE` publico. Todas las
acciones usan el lote de dos fases, incluso si contiene una sola fila.

`POST /association-prevalidations` recibe hasta 200 operaciones discriminadas:

- `add`: senal, objeto, rol y precondicion de ausencia;
- `replace`: asociacion y `lifecycle_revision` observadas mas la nueva terna;
- `archive`: asociacion/revision observadas y motivo;
- `revalidate`: asociacion/revision observadas.

Cada operacion lleva un `client_operation_id` unico. La respuesta es 200 aun
cuando haya errores y contiene:

- solicitud normalizada y su hash;
- por fila, `accepted | rejected | confirmation_required`, decisiones de
  compatibilidad, todos los errores, estado observado y comparacion antes/despues;
- `can_commit`, `requires_confirmation`, expiracion a cinco minutos;
- `prevalidation_token` opaco ligado a actor y contexto;
- `commit_etag`, que cubre filas, ausencias, revisiones vigentes,
  fingerprints, alcance y reglas observadas.

Prevalidar no inserta eventos, no reserva filas y no cambia estados.

`POST /association-batches` repite la solicitud canonica e incluye token,
confirmacion y motivos. Requiere headers `If-Match: <commit_etag>` e
`Idempotency-Key`. Dentro de una unica transaccion vuelve a autorizar,
reevaluar y comprobar todas las precondiciones; despues crea/transiciona
asociaciones, validaciones y eventos con un `batch_id`. Cualquier fallo anula
todo el lote.

### Prevalidacion de bindings

El contrato equivalente de variante recibe ademas
`expected_bindings_revision`. Las operaciones permitidas son:

- `create`: objeto, rol, senal y seleccion de revision;
- `replace`: binding y `lifecycle_revision` observados mas la nueva seleccion;
- `remove`: binding observado y motivo obligatorio;
- `restore`: fila inactiva observada y nueva seleccion validada;
- `revalidate_current`: revalidar el binding sin cambiar su identidad;
- `revalidate_pinned`: conservar revision anterior con motivo obligatorio.

Una seleccion de revision siempre es explicita:

```json
{
  "signal_id": 901,
  "revision": {
    "mode": "current",
    "revision_id": 281,
    "content_hash": "sha256:..."
  },
  "catalog_association_id": null
}
```

`mode=current` exige que ID/hash sigan siendo los vigentes al commit.
`mode=pinned` exige una revision exacta anterior, comparacion visible y motivo.
El backend no interpreta la ausencia de revision como "la que sea vigente al
guardar".

La prevalidacion devuelve, por fila, cobertura/resolucion, estado y hash
antes/despues, compatibilidad, cardinalidad y efecto sobre completitud de la
variante. El commit usa el mismo token, ETag, idempotencia y atomicidad que las
asociaciones; incrementa `bindings_revision` una sola vez por lote, invalida
la validacion ejecutable previa y devuelve la nueva revision agregada.

No hay modo parcial. `TS_LINK_BATCH_REJECTED` devuelve errores ordenados por
`client_operation_id`, pero ningun evento de exito ni incremento parcial.

### Promocion y despromocion

Como el alcance pertenece al set, no a una senal, el flujo usa:

```text
POST /sets/{set_id}/scope-prevalidations
POST /sets/{set_id}/scope-changes
```

La prevalidacion requiere `target_scope`, `expected_scope_revision`,
`expected_current_revision_id` y `expected_content_hash`. Solo `admin` puede
invocarla. Devuelve impacto separado por proyecto propietario/otros proyectos,
conteos e IDs acotados de asociaciones, bindings y variantes, estados que
resultarian, token de cinco minutos y `commit_etag`.

El commit repite la solicitud, exige confirmacion, `reason_code`, motivo no
vacio, `If-Match` e `Idempotency-Key`. Reautoriza y recalcula dentro de la
transaccion; cambia la misma fila, incrementa `scope_revision` e inserta el
evento. No copia senales ni modifica vinculos en silencio.

### ETags, precondiciones e idempotencia

- Detalles, asociaciones, bindings y sets devuelven ETag fuerte basado en sus
  revisiones/fingerprints relevantes; `If-None-Match` puede responder 304.
- El ETag de una prevalidacion representa el conjunto completo observado, no
  solamente el JSON de respuesta.
- Falta de `If-Match`, token o `Idempotency-Key` en un commit responde 428.
- Cambio entre prevalidacion y commit responde 412 y no recalcula una accion
  conveniente sobre el estado nuevo.
- La idempotency key se acota por actor, contexto y tipo de operacion. Se
  conserva al menos 24 horas. Mismo payload devuelve el mismo resultado;
  payload distinto responde conflicto.
- Restricciones unicas y locks son la ultima defensa; no sustituyen token,
  ETag ni revisiones esperadas.

Las respuestas de metadata son `Cache-Control: private, must-revalidate` y
varian por sesion/autorizacion. Previews y respuestas de mutacion son
`private, no-store`. Ninguna respuesta interna es cacheable de forma publica.

### Errores HTTP

El contrato nuevo normaliza errores internos:

```json
{
  "error": {
    "code": "TS_LINK_PRECONDITION_CHANGED",
    "message_key": "timeseries.link.precondition_changed",
    "message": "El catalogo cambio desde la prevalidacion.",
    "field": null,
    "context": {},
    "details": []
  },
  "request_id": "req_..."
}
```

Los textos son localizables; `code`, `field`, `context` y orden de `details`
son el contrato estable. Las razones `TS_COMPAT_*` ya decididas se insertan
sin traducir dentro de `details`.

| HTTP | Uso |
| --- | --- |
| 200 | Consulta, prevalidacion valida o rechazada e idempotent replay. |
| 201 | Lote o cambio de alcance creado por primera vez. |
| 304 | ETag de lectura aun vigente. |
| 400 | Query, cursor o payload sintacticamente incoherente. |
| 401 | Sesion interna ausente o expirada. |
| 403 | Frontera interna o accion no autorizada. Para `external` es generico. |
| 404 | Recurso inexistente para un actor interno ya autorizado. |
| 409 | Unicidad/cardinalidad, confirmacion faltante o idempotency key reutilizada con otro payload. |
| 410 | Cursor o token de prevalidacion expirado. |
| 412 | ETag, revision, hash, alcance o fingerprint cambiaron. |
| 422 | Lote confirmado que no cumple compatibilidad o reglas de dominio. |
| 428 | Falta token, `If-Match` o `Idempotency-Key` requerido. |

Codigos adicionales de transporte:

- `TS_QUERY_INVALID`, `TS_QUERY_CURSOR_MISMATCH`,
  `TS_QUERY_CURSOR_EXPIRED`, `TS_QUERY_SNAPSHOT_CHANGED`;
- `TS_PREVIEW_TOO_LARGE`;
- `TS_PRECONDITION_REQUIRED`, `TS_IDEMPOTENCY_CONFLICT` y
  `TS_LINK_PREVALIDATION_EXPIRED`.

Los codigos `TS_LINK_CONFLICT`, `TS_LINK_PRECONDITION_CHANGED`,
`TS_LINK_CONFIRMATION_REQUIRED`, `TS_LINK_BATCH_REJECTED`, `TS_SCOPE_*` y
`TS_COMPAT_*` conservan los significados fijados por los tickets anteriores.

### Autorizacion y no enumeracion

`require_internal` se ejecuta antes de resolver IDs, cursores o filtros.
`external` recibe el forbidden comun y nunca conoce existencia, conteos,
descriptores, hashes, IDs o razones de compatibilidad. Las mutaciones exigen
CSRF ademas de rol y politica de dominio.

`analyst` y `admin` pueden descubrir metadata interna. Vincular vuelve a
comprobar fuente, alcance, objeto, variante y actor. Solo `admin` cambia
alcance, tipos, roles/reglas y una identidad global. Consultar por ID, preview,
fuente o eventos no omite el mismo gate aplicado a la lista.

Los descriptores administrativos usan `/api/admin/time-series`:

- tipos personalizados: crear, editar solo metadata descriptiva, reemplazar
  contrato y archivar;
- reglas de compatibilidad: crear, reemplazar y archivar, nunca reescribir una
  regla usada;
- roles ejecutables de sistema: read-only para la UI; agregarlos o cambiar su
  contrato requiere una entrega de producto. Un rol personalizado creado por
  admin solo puede ser de asociacion (`execution_allowed = false`).

Estas mutaciones usan ETag, idempotencia, ledger y el mismo error envelope. El
detalle de campos es el contrato relacional ya fijado; no se descarga codigo
ni formulas al cliente.

### Datos indexados, calculados y excluidos

Se calculan al sellar una revision y quedan disponibles para el read model:

- inicio/fin de cobertura, cantidad de periodos y valores;
- resolucion nominal, minima, maxima y regularidad;
- tipo, clase, unidad, dimension, proposito, zona y fuente resumida;
- hash, estado y linaje identificador de la revision.

Se mantienen incrementalmente o mediante una proyeccion reconstruible:

- texto normalizado de busqueda y campos de orden/facetas;
- conteos de asociaciones y bindings por estado;
- ultima mutacion, propietario, alcance y generacion de seccion;
- claves necesarias para filtrar por objeto, rol y variante.

Se calculan en consulta, sobre metadata/indexes y solo para una pagina o
contexto acotado:

- autorizacion y `capabilities` del actor;
- estado derivado vigente y staleness;
- `CompatibilityDecision` contextual;
- resumen/facetas de la query normalizada.

Nunca cruzan el limite de una lista:

- puntos o muestras de valores;
- filas/bytes del archivo fuente, rutas internas, URLs firmadas, tokens o
  credenciales de conectores;
- `metadata_json` arbitrario, payloads completos de validacion o transformacion;
- listas completas de objetos, asociaciones, bindings, eventos o revisiones;
- artifacts de resultados, payload Julia o `system_case_json`;
- historia detallada, fingerprints completos o motivos sensibles.

Detalle y preview solo amplian lo que su contrato enumera; no funcionan como
un escape para JSON o colecciones sin limite.

### Coexistencia con la API actual

`GET /api/time-series/signal-catalog` deja de ser la fuente de verdad y se
convierte temporalmente en un adaptador de descriptores canonicos. No es alias
de `/inputs`, porque hoy enumera tipos Python y no identidades de senal.

`GET /api/projects/{project_id}/time-series-sets` y las rutas actuales de
reemplazo, valores, transformacion y bindings siguen operativas durante la
migracion, pero la interfaz nueva consume el namespace global. El ticket
"Migracion y coexistencia con el modelo actual" fijara dual-read, dual-write,
backfill, aliases y fechas de retiro sin cambiar este contrato destino.

### Consecuencias y traspasos

La API hace explicita la diferencia entre descubrir una senal, inspeccionar
sus valores acotados y mutar una relacion. El costo es una superficie mayor y
el flujo de prevalidacion/commit; a cambio, la UI no replica compatibilidad, no
realiza upserts destructivos y puede explicar conflictos sin debilitar el
guardado fail-closed.

No aparecieron preguntas nuevas fuera del mapa. Los indices, contadores de
generacion, locks, triggers y estrategia de facets pasan a "Rendimiento,
indices e integridad transaccional". Los aliases, backfill y coexistencia con
las rutas actuales pasan a "Migracion y coexistencia con el modelo actual".
El prototipo puede usar directamente estas rutas y capacidades sin decidir de
nuevo identidades o semantica HTTP.
