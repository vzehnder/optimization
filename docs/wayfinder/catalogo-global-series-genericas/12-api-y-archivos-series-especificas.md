---
id: 12
title: "API y carga de archivos desde series asociadas a objetos"
map: catalogo-global-series-genericas
label: wayfinder:grilling
status: closed
assignee: codex
blocked_by: [11]
---

## Question

¿Cual es el contrato completo para crear, consultar y actualizar series desde
el contexto de un objeto, tanto mediante API de valores como mediante carga de
archivos, distinguiendo con seguridad una generica compartida de una especifica
que no entra al catalogo global?

El flujo base a especificar es:

```text
crear objeto -> registrar linkable_object -> definir serie especifica
-> cargar/validar primera revision -> dejarla disponible para binding
-> publicar nuevas revisiones por API o archivo
```

Para una generica ya asociada, debe especificar ademas:

```text
abrir serie desde objeto -> identificar fuente generica compartida
-> previsualizar permiso e impacto sobre todos los consumidores
-> publicar revision compartida con confirmacion explicita
   o derivar una serie especifica antes de cargar
```

Debe decidir y justificar:

- recursos y rutas anidadas bajo el objeto, evitando IDs de objeto enviados
  solo como texto, comprobando siempre la FK y el proyecto reales e indicando
  sin ambiguedad si el destino es generico o especifico;
- payload de la definicion (rol, tipo semantico, unidad, clase de datos,
  timezone, resolucion, nombre/clave, fuente y metadata minima) y estados antes
  y despues de la primera carga valida;
- contrato de ingesta directa por API: lotes de puntos, limites, orden,
  duplicados, cobertura, timestamps, reemplazo frente a append y errores por
  fila;
- contrato de carga de archivos: formatos admitidos a partir del importador
  existente, mapeo de columnas, preview, validacion, confirmacion y reporte de
  errores, sin guardar una revision parcial;
- si definicion y primera carga son operaciones separadas o una conveniencia
  atomica adicional, manteniendo siempre la precondicion de objeto existente;
- para una generica compartida, si se permite publicar una revision desde el
  contexto del objeto, que permisos exige, como se muestra el impacto sobre
  asociaciones y bindings, como se respeta la atomicidad del set y cuando se
  debe exigir o recomendar derivar una especifica;
- revisionado inmutable, hash, fuente, ETag/precondiciones, claves de
  idempotencia, reintentos, concurrencia y auditoria para ambos canales;
- endpoints de estado, detalle, historia y preview que no devuelvan todos los
  puntos ni filtren la serie al catalogo global;
- actualizacion de bindings existentes: staleness, seleccion de la revision
  vigente o pin explicito y materializacion de snapshots de corrida;
- autorizacion, cuotas y limites de tamano, y cuando la ingesta debe ser
  sincronica o convertirse en un trabajo asincrono;
- compatibilidad temporal con las rutas actuales de sets/proyecto y que parte
  de "Contrato de consulta y API del catalogo global" queda extendida o
  sustituida para las series object-scoped.

La resolucion debe incluir ejemplos de requests/responses y una matriz comun
de validaciones y errores para API y archivo, de modo que el prototipo y los
criterios de aceptacion puedan observar el mismo comportamiento.

## Resolucion

Resuelto el 2026-08-30 con la autorizacion del usuario de adoptar la
recomendacion propuesta para todas las decisiones y preguntas de este ticket.

### Decision

La superficie canonica nace del objeto normalizado, no de sus tablas de
subtipo ni de pares textuales:

```text
/api/projects/{project_id}/linkable-objects/{linkable_object_id}/time-series
```

El backend resuelve el `linkable_object`, comprueba su FK tipada y exige que su
`project_id` coincida con el de la ruta antes de resolver cualquier serie. No
acepta `entity_type`, `entity_id`, propietario ni proyecto repetidos en el
payload como fuente de autoridad.

La coleccion contextual de lectura muestra juntas las fuentes utilizables por
el objeto, pero cada item lleva un discriminador obligatorio:

- `source_kind = catalog` identifica una asociacion a una senal generica;
- `source_kind = object_specific` identifica una senal propiedad del objeto.

La union es solo un read model. Las mutaciones usan subrecursos distintos y
tipados, de modo que un cliente nunca pueda transformar accidentalmente una
carga local en una revision compartida. Una serie especifica se identifica en
la API por su `signal_id` estable y devuelve tambien su `set_id`; como decidio
"Modelo y ciclo de vida de series especificas por objeto", su set contiene
exactamente esa senal.

Toda publicacion usa una canalizacion comun de **preparar, validar y publicar**:

1. un ingreso temporal recibe puntos JSON o un archivo, normaliza el contenido
   y calcula errores e impacto sin cambiar la revision vigente;
2. el cliente revisa metadata, preview, validaciones e impacto;
3. una publicacion con token, ETag, confirmacion e idempotencia crea y sella la
   revision completa en una transaccion;
4. si cualquier comprobacion falla, no queda una revision parcial ni cambia
   `current_revision_id`.

La semantica de publicacion admite solo `replace_full` y `append_tail`.
`append_tail` no muta filas: el servidor combina la revision base con el tramo
nuevo y sella otra fotografia completa. No hay `upsert`, reemplazo de rango ni
edicion destructiva de una revision sellada en el primer corte.

### Superficie de recursos del objeto

Se usa `OBJECT_ROOT` para abreviar la raiz canonica anterior.

| Metodo y ruta | Proposito |
| --- | --- |
| `GET OBJECT_ROOT` | Lista contextual paginada de asociaciones genericas y series especificas, sin puntos. |
| `POST OBJECT_ROOT/object-series` | Crear solo la definicion de una serie especifica en estado sin datos. |
| `GET OBJECT_ROOT/object-series/{signal_id}` | Detalle de una serie especifica cuyo propietario es exactamente el objeto de la ruta. |
| `PATCH OBJECT_ROOT/object-series/{signal_id}` | Cambiar solo nombre visible, descripcion y metadata curada, con `If-Match`. |
| `POST OBJECT_ROOT/object-series/{signal_id}/archive` | Archivar la identidad con motivo; no borra historia. |
| `GET OBJECT_ROOT/object-series/{signal_id}/revisions` | Historia paginada de metadata de revisiones. |
| `GET OBJECT_ROOT/object-series/{signal_id}/preview` | Preview acotado de una revision exacta y un rango. |
| `GET OBJECT_ROOT/catalog-associations/{association_id}` | Vista contextual de una asociacion generica; enlaza al recurso canonico global. |
| `POST OBJECT_ROOT/catalog-associations/{association_id}/object-series-derivation-prevalidations` | Comparar la fuente compartida con una copia local propuesta. |
| `POST OBJECT_ROOT/catalog-associations/{association_id}/object-series-derivations` | Crear por copia una identidad especifica sin modificar la fuente generica. |

`GET OBJECT_ROOT` comparte cursores, limites y forma de coleccion con
"Contrato de consulta y API del catalogo global". Acepta `kind=all|catalog|
object_specific`, tipo semantico, clase, rol compatible, estado y texto. Cada
fila contiene identidad, clasificacion, revision vigente, cobertura,
resolucion, estado de binding para el objeto, capacidades del actor y links;
nunca contiene valores ni una coleccion ilimitada de consumidores.

Para evitar ambiguedad se definen dos bases de mutacion:

```text
OBJECT_TARGET = OBJECT_ROOT/object-series/{signal_id}

SHARED_TARGET = OBJECT_ROOT/catalog-associations/{association_id}/shared-series
```

Ambas ofrecen el mismo flujo de ingreso:

| Metodo y ruta relativa al target | Proposito |
| --- | --- |
| `POST /revision-ingestions/points` | Preparar y validar un lote JSON. |
| `POST /revision-ingestions/files` | Subir CSV/XLSX a staging; responde con un trabajo de validacion. |
| `GET /revision-ingestions/{ingestion_id}` | Estado, resumen, errores, impacto y capacidades. |
| `PUT /revision-ingestions/{ingestion_id}/mapping` | Fijar o corregir mapeo de columnas y volver a validar. |
| `GET /revision-ingestions/{ingestion_id}/preview` | Muestra normalizada acotada; no es descarga. |
| `DELETE /revision-ingestions/{ingestion_id}` | Cancelar y retirar staging si aun no se publica. |
| `POST /revision-ingestions/{ingestion_id}/publications` | Confirmar el contenido exacto validado y sellar la revision. |

El ID del ingreso es opaco y queda ligado a actor, target, proyecto, revision
base, hash, canal y payload normalizado. Conocerlo no omite la autorizacion del
objeto o de la serie.

La API no necesita que exista una asociacion de catalogo para crear un binding,
pero `SHARED_TARGET` exige una asociacion activa porque representa
explicitamente la accion iniciada desde este objeto. La mutacion comprueba que
la asociacion, senal, rol y objeto coincidan. Una integracion administrativa
que no parte de un objeto usa el futuro recurso canonico de revisiones del set,
no simula un `association_id`.

### Definicion de una serie especifica

El payload de `POST OBJECT_ROOT/object-series` es:

```json
{
  "object_series_key": "natural_inflow_forecast",
  "display_name": "Afluente previsto",
  "description": "Pronostico horario del nodo",
  "intended_binding_role_key": "natural_inflow",
  "semantic_type_key": "natural_inflow",
  "unit_key": "m3_per_s",
  "data_class_key": "forecast",
  "timezone": "America/Santiago",
  "temporal_contract": {
    "regularity": "regular",
    "nominal_resolution_seconds": 3600,
    "timestamp_convention": "period_start"
  },
  "source_expectation": {
    "kind": "api",
    "display_name": "Pronostico interno"
  },
  "metadata": {
    "tags": ["operacion", "diario"],
    "external_reference": "forecast:nodo-7"
  }
}
```

`intended_binding_role_key` es obligatorio para validar que el tipo, unidad y
objeto forman una combinacion util desde el inicio. Se guarda como intencion de
creacion y auditoria, no como el unico rol de la identidad: la compatibilidad
ejecutable sigue derivandose de la matriz positiva y puede admitir mas de un
rol. Esto conserva la decision del ticket anterior de no fijar un rol unico en
la definicion.

`semantic_type_key`, `unit_key`, propietario y `object_series_key` son
inmutables. Cambiarlos crea otra identidad. Nombre visible, descripcion y
metadata curada son editables sin crear una revision de valores. La metadata
acepta solo claves declaradas, hasta 16 KiB serializados, veinte tags de
sesenta caracteres y ningun secreto, credencial, ruta local o fragmento
ejecutable.

`data_class_key`, timezone y contrato temporal se fotografian en cada
revision. La definicion fija sus valores iniciales; una carga posterior puede
proponer un cambio compatible y la vista de impacto debe mostrarlo. Un cambio
de tipo semantico o unidad nunca entra disfrazado como carga.

`source_expectation` es una ayuda de interfaz y politica, no procedencia
ejecutable. La fuente real pertenece a cada revision y se declara en el
ingreso. El servidor calcula checksum, actor y fecha; nunca acepta
`stored_path`, `created_by` ni checksum suministrados como verdad.

La creacion exige `Idempotency-Key`, pero no `If-Match` porque aun no existe el
recurso. La respuesta `201` contiene ETag:

```json
{
  "object_series": {
    "source_kind": "object_specific",
    "signal_id": 901,
    "set_id": 440,
    "owner": {
      "project_id": 12,
      "linkable_object_id": 77,
      "object_kind": "hydraulic_node"
    },
    "object_series_key": "natural_inflow_forecast",
    "set_status": "draft",
    "availability": "awaiting_data",
    "current_revision": null,
    "building_revision": {"revision_id": 1201, "revision_number": 1},
    "binding_ready": false,
    "compatible_role_keys": ["natural_inflow"],
    "resource_version": 1
  }
}
```

En BBDD, esta operacion crea set, senal, revision 1 `building` y evento en una
transaccion, tal como fijo "Modelo y ciclo de vida de series especificas por
objeto". No inserta periodos ni valores. La disponibilidad derivada es:

| Estado persistido | Disponibilidad API | Seleccionable |
| --- | --- | --- |
| `draft`, sin revision vigente | `awaiting_data` | no |
| `validated`, revision vigente sellada y compatible | `ready` | si |
| `archived` | `archived` | no |
| propietario archivado | `owner_archived` | no |

### Definicion y primera carga atomicas

El camino canonico mantiene definicion y carga separadas porque permite que la
UI nombre y clasifique la serie antes de disponer de datos. Adicionalmente se
ofrece una conveniencia atomica para integraciones:

```text
POST OBJECT_ROOT/object-series-creation-ingestions/points
POST OBJECT_ROOT/object-series-creation-ingestions/files
GET  OBJECT_ROOT/object-series-creation-ingestions/{ingestion_id}
PUT  OBJECT_ROOT/object-series-creation-ingestions/{ingestion_id}/mapping
POST OBJECT_ROOT/object-series-creation-ingestions/{ingestion_id}/publications
```

El ingreso temporal contiene definicion y primera carga, pero no crea filas de
dominio. Al publicar, una sola transaccion vuelve a comprobar que el objeto
existe y esta activo, reserva la clave local, crea set/senal/revision, inserta
contenido, sella la revision y mueve `current_revision_id`. Un fallo no deja
una definicion vacia. Por tanto se conserva la precondicion `objeto existente`
y se obtiene una conveniencia verdaderamente atomica, no dos llamadas
compensadas en el cliente.

### Contrato comun de ingesta por puntos

Un ingreso JSON usa la misma forma para una serie especifica y una fuente
generica. En la especifica, `values` contiene exactamente su unica
`object_series_key`; en una generica contiene todas las senales activas del
set:

```json
{
  "mode": "replace_full",
  "expected_base": null,
  "revision_contract": {
    "data_class_key": "forecast",
    "timezone": "America/Santiago",
    "regularity": "regular",
    "nominal_resolution_seconds": 3600
  },
  "source": {
    "kind": "api",
    "display_name": "Pronostico interno",
    "external_reference": "issue:2026-08-30T12:00Z"
  },
  "points": [
    {
      "timestamp_start": "2026-08-31T00:00:00-04:00",
      "duration_seconds": 3600,
      "values": {
        "natural_inflow_forecast": {
          "value": 18.4,
          "quality_flag": "forecast"
        }
      }
    },
    {
      "timestamp_start": "2026-08-31T01:00:00-04:00",
      "duration_seconds": 3600,
      "values": {
        "natural_inflow_forecast": {
          "value": 19.1,
          "quality_flag": "forecast"
        }
      }
    }
  ]
}
```

Reglas del canal API:

- `timestamp_start` es RFC 3339 con offset obligatorio; se normaliza a UTC y
  se conserva la timezone IANA de presentacion en la revision;
- cada punto envia exactamente uno entre `timestamp_end` y
  `duration_seconds`; el segundo es entero positivo;
- los puntos llegan estrictamente ordenados, no se reordenan de forma
  silenciosa y no pueden duplicarse ni solaparse;
- cada periodo contiene exactamente una celda por senal activa del target;
  no hay valores nulos, `NaN`, infinitos ni strings numericos ambiguos;
- `quality_flag` es opcional y debe pertenecer al catalogo permitido;
- la validacion semantica aplica rango, signo, cobertura, regularidad y unidad
  de la definicion; el valor siempre se expresa en la unidad canonica, sin
  conversion implicita;
- la peticion declara la revision base exacta para actualizaciones:
  `{revision_id, content_hash}`. En la primera carga es `null`;
- `replace_full` define la fotografia completa. `append_tail` exige una
  revision base vigente y agrega solo periodos posteriores a su cobertura;
- en una serie regular, el primer periodo de `append_tail` comienza
  exactamente al final vigente. En una irregular puede comenzar despues, pero
  las reglas de cobertura del tipo pueden rechazar el hueco;
- la primera carga solo admite `replace_full`.

No se permiten varios lotes que construyan parcialmente una misma revision
canonica. Un payload que exceda el limite del canal debe usar archivo. Esto
evita una revision `building` abandonada o un commit final que dependa de
ordenes de llegada no auditables.

Una validacion sin errores responde `201` y aun no publica:

```json
{
  "ingestion": {
    "ingestion_id": "tsi_01J...",
    "channel": "api_points",
    "state": "ready_to_publish",
    "mode": "replace_full",
    "target": {
      "source_kind": "object_specific",
      "signal_id": 901,
      "set_id": 440
    },
    "base": null,
    "normalized": {
      "period_count": 2,
      "value_count": 2,
      "coverage_start": "2026-08-31T04:00:00Z",
      "coverage_end": "2026-08-31T06:00:00Z",
      "content_hash": "sha256:..."
    },
    "validation": {
      "valid": true,
      "error_count": 0,
      "errors": [],
      "errors_truncated": false
    },
    "impact": {
      "bindings_current": 0,
      "bindings_pinned": 0,
      "will_become_stale": 0
    },
    "requires_confirmation": false,
    "validation_token": "tsv_...",
    "expires_at": "2026-08-31T03:00:00Z"
  }
}
```

### Contrato de archivos

El primer corte conserva los dos formatos reales del importador existente:

- CSV delimitado por coma, con encabezado, codificado UTF-8 o UTF-8 con BOM;
- XLSX sin macros, formulas, celdas combinadas ni tablas de Excel, con una
  hoja seleccionada explicitamente cuando el libro contiene mas de una.

No se admiten XLS, ODS, JSONL, ZIP ni URLs remotas. Los encabezados son no
vacios y unicos. Los nombres se sanitizan para presentacion, el archivo se
guarda bajo un ID generado dentro de staging y el wire contract nunca recibe
ni devuelve una ruta local. El checksum SHA-256 se calcula mientras se sube.

`POST .../revision-ingestions/files` es `multipart/form-data` con `file` y,
opcionalmente, partes JSON `mapping` y `publication`. Si falta mapeo, el
trabajo queda `awaiting_mapping` y devuelve hojas, columnas, primeras filas y
sugerencias no vinculantes. El mapeo comun es:

```json
{
  "mode": "replace_full",
  "expected_base": null,
  "sheet_name": "Afluentes",
  "revision_contract": {
    "data_class_key": "forecast",
    "timezone": "America/Santiago",
    "regularity": "regular",
    "nominal_resolution_seconds": 3600
  },
  "columns": {
    "timestamp_start": "timestamp",
    "timestamp_end": null,
    "duration_hours": "duration_hours",
    "signals": [
      {
        "series_key": "natural_inflow_forecast",
        "value": "value_m3s",
        "quality_flag": "quality"
      }
    ]
  },
  "source": {
    "kind": "xlsx",
    "display_name": "Pronostico del proveedor",
    "external_reference": "forecast-2026-08-30"
  }
}
```

Se exige exactamente una columna de fin o duracion. Las fechas con offset se
normalizan directamente. Una fecha local sin offset se interpreta solo con la
timezone IANA declarada; una hora local inexistente o ambigua por DST se
rechaza y debe corregirse o cargarse con offset explicito.

El preview de ingreso devuelve hasta 200 filas normalizadas distribuidas entre
inicio, errores y final. Nunca evalua formulas ni devuelve celdas ocultas fuera
del mapeo. La validacion recorre todo el archivo, acumula conteos por codigo y
devuelve como maximo 200 errores localizados; `errors_truncated` indica que hay
mas. Una sola fila invalida impide publicar el archivo completo.

Estados del trabajo:

```text
uploaded -> queued -> validating -> awaiting_mapping | invalid |
ready_to_publish -> publishing -> published
                          \-> failed
uploaded|queued|awaiting_mapping|invalid|ready_to_publish -> cancelled|expired
```

Un ingreso invalido puede recibir otro mapeo sin volver a subir el archivo. El
contenido binario es inmutable; cambiar el archivo crea otro ingreso. Staging
y reportes expiran a las 24 horas, mientras que un token de validacion listo
para publicar dura cinco minutos y se puede regenerar sin reupload.

### Publicacion, hash e inmutabilidad

`POST .../revision-ingestions/{ingestion_id}/publications` exige:

```http
If-Match: "ts-object-series-901-v1"
Idempotency-Key: publish-natural-inflow-20260830-01
```

```json
{
  "validation_token": "tsv_...",
  "confirm": true,
  "reason_code": "forecast_refresh",
  "reason_text": "Carga operativa para el horizonte del 31 de agosto"
}
```

Para una primera carga local `confirm` puede ser `false` si el ingreso no
reporta impacto ni advertencias. Para una revision compartida siempre es
`true` y ambos motivos son obligatorios.

Dentro de una transaccion, la publicacion vuelve a autorizar, bloquea el set,
comprueba target, objeto, revision/hash base, ETag, contrato, token, checksum y
cuotas, asigna el siguiente `revision_number`, inserta la fotografia completa,
calcula/verifica el hash canonico, sella la revision y mueve
`current_revision_id`. En la primera carga separada completa y sella la
revision 1 `building` ya creada. No se expone un intervalo en que una revision
incompleta sea vigente.

El `content_hash` se calcula sobre contrato ejecutable normalizado, membresia
de senales, clasificacion, periodos, valores y quality flags. Excluye nombre de
archivo, actor, request, comentarios y rutas de storage. El checksum del
archivo o payload se conserva por separado en la fuente. `append_tail`
produce el hash de la fotografia completa resultante, no solo del delta.

Si el hash y contrato resultantes son iguales a la revision vigente, la
publicacion responde `200` con `outcome = unchanged`, no crea otra revision y
no vuelve stale ningun binding. El recibo de la fuente queda en auditoria
operativa. En otro caso responde `201`:

```json
{
  "publication": {
    "outcome": "new_revision",
    "set_id": 440,
    "signal_ids": [901],
    "revision_id": 1201,
    "revision_number": 1,
    "state": "sealed",
    "content_hash": "sha256:...",
    "source": {
      "kind": "api",
      "checksum": "sha256:..."
    },
    "availability": "ready",
    "binding_ready": true,
    "staleness": {
      "bindings_current": 0,
      "bindings_pinned": 0,
      "now_stale": 0
    },
    "resource_version": 2
  }
}
```

Los ETags fuertes incluyen identidad, estado, metadata editable,
`current_revision_id`, hash y version de contrato observada. Crear definicion
o ingreso exige idempotencia; cambiar metadata, archivar y publicar exige
ademas `If-Match`. Falta de precondiciones responde `428`; un cambio observado
responde `412` y obliga a revalidar, nunca recalcula la accion sobre el estado
nuevo. La clave de idempotencia se acota por actor, target y operacion durante
al menos 24 horas: mismo payload repite la respuesta; otro payload responde
`409 TS_INGEST_IDEMPOTENCY_CONFLICT`.

### Revision de una generica compartida desde el objeto

`SHARED_TARGET` identifica la asociacion y devuelve ademas set, todas sus
senales, alcance, propietario y consumidores. Abrir el flujo no concede
permiso para publicar:

- para un set `project`, `analyst` o `admin` puede publicar solo bajo las
  reglas de acceso del proyecto propietario;
- para un set `global`, solo `admin` puede publicar una nueva revision;
- `external` se rechaza antes de resolver IDs;
- una asociacion archivada, incompatible o que no pertenezca al objeto de la
  ruta no habilita el flujo.

Toda revision generica sigue siendo atomica por set. Si el set contiene varias
senales, la carga debe proporcionar el contrato y valores completos de **todas**
las senales activas. El contexto de una asociacion individual no autoriza una
revision parcial. Si el usuario solo quiere cambiar la senal del objeto, debe
derivarla como especifica.

El ingreso compartido siempre devuelve `requires_confirmation = true` y una
vista de impacto ligada al token y ETag:

```json
{
  "impact": {
    "source": {
      "set_id": 80,
      "visibility_scope": "global",
      "current_revision_id": 281,
      "current_content_hash": "sha256:old"
    },
    "associations": {"total": 14, "other_objects": 13},
    "bindings": {
      "total_active": 9,
      "current": 7,
      "pinned": 2,
      "projects_affected": 4,
      "variants_affected": 8
    },
    "effect": {
      "bindings_will_become_stale": 9,
      "associations_will_require_revalidation": 0
    },
    "listed_consumers": [
      {"linkable_object_id": 77, "project_id": 12, "relation": "current"}
    ],
    "consumers_truncated": true
  },
  "recommendation": "derive_object_specific",
  "requires_confirmation": true
}
```

Una actualizacion solo de contenido mantiene asociaciones `active_valid` si su
fingerprint de compatibilidad no cambia, pero vuelve stale todos los bindings
`current` y `pinned` que observaron la revision vigente anterior, conforme al
ciclo ya decidido. Si cambia clase, resolucion, cobertura u otra parte del
contrato, la prevalidacion calcula ademas las asociaciones que quedarian stale
o incompatibles.

Derivar es **obligatorio** cuando el actor no puede editar la fuente, cuando el
payload no cubre todas las senales de un set multisenal o cuando la nueva
definicion cambia tipo semantico o unidad. Se recomienda, sin imponerlo, cuando
hay consumidores ajenos al objeto y la intencion es local. La UI debe ofrecer
ambos caminos con nombres explicitos; nunca presenta "Guardar" sin indicar
`publicar para todos` o `crear copia para este objeto`.

La derivacion usa dos fases y fija revision/hash fuente. El commit crea un set
`object_specific`, su senal y una primera revision sellada copiando solamente
los periodos y valores de la senal identificada por la asociacion, incluso si
la revision fuente pertenece a un set multisenal; no modifica la asociacion ni
reemplaza bindings. Registra linaje y devuelve el request sugerido para el
flujo ordinario de bindings. Esta resolucion **extiende**, sin sustituir, la
tabla de linaje del ticket anterior con el valor:

```text
lineage_kind = catalog_object_specific_copy
```

Para ese valor, la revision y senal fuente de catalogo y el objeto propietario
destino son obligatorios. Es el inverso trazable de
`object_specific_catalog_copy`; ninguna de las dos operaciones comparte
identidad.

### Lectura, historia y preview

`GET OBJECT_TARGET`, historia y preview solo responden si la serie pertenece
exactamente al objeto de la ruta. Para un usuario interno, un `signal_id` de
otro objeto o de catalogo responde `404`; no existe un filtro que ensanche la
ruta. La lista global `/api/time-series/catalog/inputs` continua leyendo solo
`series_kind = catalog`, por lo que una especifica nunca se filtra al catalogo.

El detalle contiene definicion, propietario, revision/hash vigente, cobertura,
resolucion, fuente saneada, validaciones, staleness resumido, capacidades y
links. No embebe puntos, archivo, bindings ni eventos completos. La historia
pagina metadata inmutable.

El preview conserva el contrato del catalogo global:

```text
GET OBJECT_TARGET/preview
  ?revision_id=<id>
  &from=<RFC3339>
  &to=<RFC3339>
  &sampling=minmax|uniform|none
  &max_points=<1..2000>
```

Revision y rango son obligatorios; `max_points` vale 500 y nunca supera 2000.
No se agrega un `GET /values` ilimitado. Una exportacion completa es otra
capacidad y queda fuera del primer corte.

### Bindings y snapshots despues de publicar

Publicar una revision nunca mueve un binding en silencio. La respuesta entrega
conteos y links al flujo de prevalidacion de bindings definido en "Contrato de
consulta y API del catalogo global":

- un binding que seguia la revision vigente queda `stale`;
- un binding fijado tambien queda `stale` porque cambio la revision vigente
  observada cuando se acepto el pin;
- el usuario puede reemplazarlo por la nueva revision vigente o revalidar la
  revision fijada con motivo;
- hasta resolverlo, validacion de variante, materializacion y corridas fallan
  de forma cerrada;
- un `scenario_version` y una corrida ya materializados conservan revision,
  hash, `source_kind` y propietario observados y nunca se reescriben.

La publicacion y el reemplazo de bindings son transacciones separadas. Esto
deja visible el estado stale y evita que una carga cambie configuraciones de
casos no mencionadas. La UI puede encadenar ambas prevalidaciones, pero no
inventar una mutacion compuesta en el cliente.

### Autorizacion, cuotas y ejecucion asincrona

Todas las rutas usan el gate interno comun. `analyst` y `admin` pueden leer y
mutar series especificas en proyectos autorizados; `external` nunca lista,
lee, previsualiza ni carga. CSRF se exige en mutaciones autenticadas por cookie.
Cada operacion vuelve a comprobar actor, objeto, proyecto, target y estado;
`capabilities` de una respuesta anterior no concede permiso.

Limites por defecto del primer corte, configurables hacia abajo por despliegue
y anunciados en la respuesta de capacidades:

| Limite | Valor por defecto |
| --- | --- |
| JSON directo | 10 MiB, 10.000 periodos y 100.000 celdas |
| CSV | 100 MiB |
| XLSX comprimido | 25 MiB; maximo 100 MiB descomprimido y ratio 100:1 |
| Revision por archivo | 1.000.000 periodos, 5.000.000 celdas y 200 columnas |
| Trabajos activos | 3 por actor y proyecto |
| Staging acumulado | 2 GiB por proyecto |
| Errores detallados | 200, mas conteos completos por codigo |
| Preview de ingreso | 200 filas normalizadas |

Exceder el tamano del request responde `413`; exceder filas/celdas detectadas
durante parseo deja el trabajo `invalid`. CSV y XLSX se validan siempre de
forma asincrona y la subida responde `202`. JSON dentro de sus limites se
valida sincronicamente y responde `201 ready_to_publish` o `422`; una
implementacion puede responder `202` por carga operacional, manteniendo el
mismo recurso de trabajo. La publicacion de hasta 100.000 celdas puede cerrar
en la solicitud; sobre ese umbral responde `202 publishing` y se consulta el
mismo ingreso. En ambos casos solo existe revision si la transaccion termina.

### Matriz comun de validaciones y errores

Todos los canales producen el mismo `application/problem+json`. La ubicacion
conserva `record_index` canonico y agrega `json_pointer` para API o
`sheet`/`source_row_number`/`column` para archivo:

```json
{
  "type": "https://errors.example/time-series/ingestion-validation",
  "title": "Time-series ingestion is invalid",
  "status": 422,
  "code": "TS_INGEST_VALIDATION_FAILED",
  "detail": "2 records require correction",
  "request_id": "req_...",
  "errors": [
    {
      "code": "TS_INGEST_VALUE_INVALID",
      "message": "value must be finite",
      "location": {
        "record_index": 17,
        "sheet": "Afluentes",
        "source_row_number": 19,
        "column": "value_m3s"
      }
    }
  ],
  "error_counts": {"TS_INGEST_VALUE_INVALID": 2},
  "errors_truncated": false
}
```

| Validacion | Codigo estable | HTTP/estado | API y archivo |
| --- | --- | --- | --- |
| Actor no interno o accion no autorizada | `TS_INGEST_FORBIDDEN` | 403 antes de resolver IDs | igual |
| Objeto/serie no existe bajo la raiz real | `TS_OBJECT_SERIES_NOT_FOUND` | 404 | igual |
| Objeto y proyecto no coinciden | `TS_COMPAT_PROJECT_CONTEXT_MISMATCH` | 404/422 segun lectura o payload | igual |
| Serie especifica pertenece a otro objeto | `TS_COMPAT_OBJECT_OWNER_MISMATCH` | 404 en lookup; 422 en prevalidacion | igual |
| Clave local ya usada, incluso archivada | `TS_OBJECT_SERIES_KEY_CONFLICT` | 409 | igual |
| Formato o media type no admitido | `TS_INGEST_FORMAT_UNSUPPORTED` | 415 | archivo; no aplica a JSON |
| Request o archivo supera bytes | `TS_INGEST_PAYLOAD_TOO_LARGE` | 413 | igual limite de transporte |
| Supera filas, celdas o columnas | `TS_INGEST_QUOTA_EXCEEDED` | 422 / trabajo `invalid` | igual |
| Mapeo ausente, duplicado o incompleto | `TS_INGEST_MAPPING_INVALID` | 422 / `awaiting_mapping` o `invalid` | pointer o columna |
| Timestamp vacio o no parseable | `TS_INGEST_TIMESTAMP_INVALID` | 422 | igual |
| Hora local DST ambigua/inexistente | `TS_INGEST_TIMESTAMP_AMBIGUOUS` | 422 | archivo; API exige offset |
| Orden, duplicado o solapamiento | `TS_INGEST_PERIOD_CONFLICT` | 422 | igual |
| Duracion no positiva o incoherente | `TS_INGEST_DURATION_INVALID` | 422 | igual |
| Valor ausente, no numerico o no finito | `TS_INGEST_VALUE_INVALID` | 422 | igual |
| Regla semantica de rango/signo falla | `TS_INGEST_VALUE_DOMAIN_VIOLATION` | 422 | igual |
| Faltan senales del set atomico | `TS_INGEST_SIGNAL_SET_INCOMPLETE` | 422 | igual |
| Append solapa, deja hueco prohibido o usa base incorrecta | `TS_INGEST_APPEND_CONFLICT` | 422/412 | igual |
| Cobertura/resolucion no cumple contrato | `TS_INGEST_TEMPORAL_CONTRACT_INVALID` | 422 | igual |
| Falta token, ETag o idempotencia | `TS_INGEST_PRECONDITION_REQUIRED` | 428 | igual |
| Cambio target/base/impacto desde validar | `TS_INGEST_PRECONDITION_CHANGED` | 412 | igual |
| Clave idempotente reutilizada con otro payload | `TS_INGEST_IDEMPOTENCY_CONFLICT` | 409 | igual |
| Publicacion compartida sin confirmacion | `TS_SHARED_REVISION_CONFIRMATION_REQUIRED` | 409 | igual |
| Set global intentado por no-admin | `TS_SHARED_REVISION_ADMIN_REQUIRED` | 403 | igual |
| Trabajo vencido o cancelado | `TS_INGEST_SESSION_UNAVAILABLE` | 410 | igual |

Los errores de compatibilidad conservan los codigos `TS_COMPAT_*` ya
decididos y pueden aparecer dentro del arreglo comun. Un lote puede tener
muchos errores, pero nunca exitos parciales ni eventos de revision exitosa.

### Auditoria

Cada definicion, cambio de metadata, archivado, derivacion y publicacion
exitosa registra un evento append-only con actor e identidad/rol observados,
request, instante, proyecto, objeto, target tipado, revision/hash base y nueva,
canal, checksum de fuente, mapeo normalizado, modo, contrato, token/hash de
validacion, idempotency key, motivo e impacto confirmado.

Los eventos minimos nuevos son:

```text
object_series_defined
object_series_metadata_changed
object_series_archived
revision_published
shared_revision_published
catalog_object_specific_copy_created
```

Fallos de autenticacion, autorizacion, malware/formato, validacion,
precondicion o cuota se registran en el log operativo y de seguridad con
`request_id`; no insertan un evento de dominio que parezca una mutacion
exitosa. Fuente y metadata nunca conservan credenciales, rutas locales ni el
contenido completo del archivo.

### Compatibilidad con la API actual

La nueva superficie extiende "Contrato de consulta y API del catalogo global"
sin cambiar sus fronteras:

- `/api/time-series/catalog/inputs` continua siendo exclusivamente
  `series_kind = catalog`;
- asociaciones y bindings conservan sus recursos, tokens, ETags y lotes;
- los endpoints object-scoped agregan navegacion, definicion e ingesta local;
- una revision generica iniciada desde un objeto sigue publicando sobre el set
  canonico y respeta todos sus consumidores.

Las rutas existentes `/api/projects/{project_id}/time-series-sets` y su
detalle/revisiones permanecen temporalmente como compatibilidad solo para sets
`catalog` propiedad del proyecto. Nunca listan ni permiten descubrir una serie
`object_specific`. `PUT .../values`, `POST .../replace/upload` y
`POST .../replace` quedan deprecados para clientes nuevos y deben converger
internamente a la misma validacion y publicacion atomica. La API nueva no
acepta el actual `stored_path` suministrado por cliente.

El ticket "Migracion y coexistencia con el modelo actual" decidira aliases,
headers `Deprecation`/`Sunset`, backfill y fecha de retiro; no puede relajar la
separacion de procedencias, ETags, idempotencia ni atomicidad fijadas aqui.

### Relacion con las decisiones anteriores

- **Modelo relacional canonico para series, tipos y objetos vinculables** se
  conserva: la raiz usa `linkable_objects`, el catalogo es signal-first y la
  revision permanece atomica por set.
- **Contrato de compatibilidad entre tipos de serie y objetos** se conserva:
  definicion, ingreso, derivacion, binding y publicacion comparten el mismo
  evaluador y codigos.
- **Ciclo de vida de asociaciones y bindings versionados** se conserva:
  publicar mueve solo la revision vigente y deja fail-closed los bindings que
  observaron otra revision.
- **Alcance global, permisos y promocion entre proyectos** se conserva: un set
  global solo lo revisa `admin`; una especifica nunca sale de su proyecto.
- **Contrato de consulta y API del catalogo global** se extiende con la vista y
  mutaciones object-scoped, sin permitir que una especifica entre en `/inputs`.
- **Modelo y ciclo de vida de series especificas por objeto** se concreta con
  definicion sin datos, primera carga, publicacion y derivacion desde catalogo;
  solo se agrega el tipo de linaje inverso declarado arriba.

### Consecuencias y traspasos

El contrato da a UI e integraciones una sola semantica de validacion para JSON
y archivos, hace visible el impacto de una fuente compartida y mantiene una
frontera fisica imposible de confundir entre catalogo y propiedad local. El
costo es un recurso temporal de ingreso y una confirmacion separada; a cambio,
archivos grandes, reintentos, concurrencia y errores por fila no contaminan la
historia canonica.

No aparecieron preguntas nuevas ni niebla adicional. El prototipo debe mostrar
los dos caminos y sus confirmaciones; migracion debe adaptar las rutas actuales;
integridad debe fijar jobs, locks, indices y limpieza de staging; y los
criterios de aceptacion deben probar no fuga, atomicidad, cuotas, errores
equivalentes, staleness y snapshots.
