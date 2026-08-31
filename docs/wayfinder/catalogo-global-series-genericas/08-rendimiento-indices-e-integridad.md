---
id: 08
title: "Rendimiento, indices e integridad transaccional"
map: catalogo-global-series-genericas
label: wayfinder:grilling
status: closed
assignee: codex
blocked_by: [03, 05, 07, 11, 12]
---

## Question

¿Que estrategia fisica de consultas, indices y transacciones sostiene el
catalogo global y la vinculacion masiva con los motores de BBDD soportados?

La respuesta debe partir de las consultas y operaciones ya definidas, no de
indices especulativos. Debe resolver paginacion estable, busqueda textual,
filtros por tipo/proyecto/objeto/cobertura, conteos de vinculos, integridad de
operaciones masivas, concurrencia, diferencias SQLite/PostgreSQL y limites que
obligarian a particionar o introducir una proyeccion de lectura.

Debe incluir las consultas por objeto de las series especificas, la garantia
de que nunca quedan huerfanas ni se filtran al catalogo global, el costo de
crear revisiones mediante API o archivo, deduplicacion/idempotencia de cargas y
transacciones que mantengan consistente definicion, revision, valores y
binding.

## Resolucion

Resuelto el 2026-08-30 con la autorizacion del usuario de adoptar la
recomendacion propuesta para todas las decisiones y preguntas de este ticket.

### Decision

La estrategia fisica tiene una fuente canonica normalizada y proyecciones de
lectura reconstruibles, pero **sin consistencia eventual dentro del contrato
visible**:

- PostgreSQL es el motor productivo y la referencia para concurrencia,
  busqueda, cargas grandes y presupuestos de latencia.
- SQLite conserva la misma semantica de dominio, errores, FKs, unicidad,
  inmutabilidad e idempotencia para pruebas aisladas y uso local de un solo
  proceso. No promete los mismos volumenes, concurrencia ni SLO.
- El catalogo global consulta desde la primera entrega una proyeccion
  transaccional de metadata, una fila por senal `catalog`; nunca recorre
  periodos o valores ni construye la lista mediante un join completo en cada
  request.
- Asociaciones, bindings, revisiones, valores y ledgers siguen teniendo como
  autoridad las tablas canonicas. La proyeccion puede reconstruirse y nunca
  concede permisos ni sustituye las comprobaciones del commit.
- Toda ingesta se prepara y valida en staging. Solo la publicacion copia una
  fotografia completa a las tablas canonicas, la sella, mueve el puntero
  vigente, actualiza la proyeccion y registra idempotencia/auditoria dentro de
  una unidad atomica.
- Se comienza con tablas normales, bulk insert e indices dirigidos por las
  consultas decididas. No se introduce TimescaleDB, deduplicacion fisica de
  puntos, un buscador externo ni particionamiento hasta cruzar los umbrales
  medidos definidos mas abajo.

### Jerarquia de motores

PostgreSQL soporta despliegues con multiples workers y jobs concurrentes. Todo
flujo de varias sentencias usa una transaccion explicita; el modo autocommit
del adaptador actual se admite solo para lecturas independientes y DDL
idempotente. Ninguna publicacion, lote, materializacion o mutacion de alcance
puede depender de una secuencia de sentencias autocommit.

SQLite se configura, para bases en archivo, con:

```text
PRAGMA foreign_keys = ON
PRAGMA journal_mode = WAL
PRAGMA synchronous = NORMAL
PRAGMA busy_timeout = 5000
PRAGMA recursive_triggers = ON
```

Las pruebas en memoria conservan `foreign_keys` y triggers, aunque WAL no
aplique. El servicio rechaza una configuracion SQLite con mas de un proceso
web o mas de un worker de publicacion. Sus escrituras pasan por el lock local
existente y una transaccion `BEGIN IMMEDIATE`; un timeout no se espera de forma
indefinida y se traduce al conflicto operativo estable correspondiente.

Las diferencias fisicas no cambian el resultado funcional:

| Necesidad | PostgreSQL | SQLite |
| --- | --- | --- |
| Bloqueo de agregados | `SELECT ... FOR UPDATE`/`FOR KEY SHARE` | `BEGIN IMMEDIATE`, escritor unico |
| JSON | `JSONB` | `TEXT` con `json_valid` cuando JSON1 esta disponible |
| Timestamps | `TIMESTAMPTZ` UTC | RFC 3339 UTC normalizado en `TEXT` |
| Booleanos | `BOOLEAN` | entero con `CHECK (value IN (0, 1))` |
| Busqueda | `tsvector` + GIN | FTS5; fallback `LIKE` equivalente para fixtures pequenos |
| IDs | `BIGINT`/identity | `INTEGER PRIMARY KEY` |
| Unicidad activa | indice parcial | indice parcial |
| FKs diferibles | `DEFERRABLE INITIALLY DEFERRED` | igual para FKs; no se depende de constraint triggers diferibles |

SQLite es una implementacion de compatibilidad, no una forma silenciosa de
operar produccion degradada. Cargas por archivo pueden reducir sus cuotas; la
API ya anuncia limites por despliegue.

### Presupuesto inicial y datos de referencia

Los planes se verifican en PostgreSQL con una fixture minima de rendimiento de
100.000 entradas de catalogo, 1.000.000 de asociaciones, 1.000.000 de bindings
activos/historicos y 100.000.000 de celdas distribuidas entre revisiones. Debe
incluir un set compartido con muchos consumidores, proyectos mezclados,
series archivadas y datos sesgados; una fixture uniforme ocultaria los peores
planes.

Objetivos p95 del backend, excluyendo red y parseo del archivo:

| Operacion | Presupuesto PostgreSQL |
| --- | --- |
| Pagina de catalogo de 50 filas, sin facets | 300 ms |
| Pagina con `total_count` y facets exactos | 1 s |
| Lista contextual o detalle por objeto | 300 ms |
| Preview de 500 puntos | 500 ms |
| Preview maximo de 2.000 puntos | 1 s |
| Prevalidacion de 200 asociaciones o bindings | 2 s |
| Commit de un lote de 200, sin espera de lock | 2 s |
| Publicacion sincrona de hasta 100.000 celdas | 5 s |

Archivos mayores siguen el trabajo asincrono ya decidido. No se promete que
una publicacion de cinco millones de celdas termine dentro de una request; si
se completa, la revision aparece entera, nunca por partes. SQLite ejecuta una
fixture de correccion menor y no participa en estos SLO.

Cada consulta critica guarda un `EXPLAIN (ANALYZE, BUFFERS)` de referencia en
las pruebas de despliegue PostgreSQL. Las pruebas SQLite usan `EXPLAIN QUERY
PLAN` para impedir full scans accidentales sobre periodos/valores, sin fijar
costos internos del optimizador.

### Proyeccion transaccional del catalogo

`time_series_catalog_entries` contiene una fila por identidad de senal visible
en `/api/time-series/catalog/inputs`. Incluye solo campos indexables de lista:

```text
signal_id, time_series_set_id, series_kind = 'catalog',
owner_project_id, owner_project_name_sort,
visibility_scope, set_status, signal_status,
series_key, display_name, display_name_sort, search_text_normalized,
semantic_type_id/key, data_class_id/key, unit_id/key,
source_kind, current_revision_id, revision_number,
coverage_start/end, period_count, value_count,
nominal/min/max_resolution_seconds, regularity,
updated_at, association_count, binding_count, projection_revision
```

No contiene puntos, metadata libre, permisos de un actor ni estados de
compatibilidad calculados. `association_count` y `binding_count` son conteos
estructurales activos usados para ordenar; se actualizan junto con la mutacion
del vinculo. Los conteos por estado, `has_stale`, `has_invalid`, capacidades y
compatibilidad se calculan para los IDs de la pagina mediante consultas
indexadas. Asi publicar una revision compartida no reescribe un millon de
bindings solo para marcar un cache: staleness se deriva comparando revision y
fingerprints observados.

La frontera contra fugas se impone tambien en BBDD. La proyeccion lleva
`CHECK (series_kind = 'catalog')` y una FK compuesta
`(time_series_set_id, series_kind) -> time_series_sets(id, series_kind)`.
Insertar por error una serie `object_specific` falla antes de que la ruta
global pueda verla.

`time_series_catalog_generations` mantiene un contador monotono por seccion:

```sql
CREATE TABLE time_series_catalog_generations (
    section     TEXT PRIMARY KEY,
    generation BIGINT NOT NULL CHECK (generation >= 0),
    updated_at  TIMESTAMP NOT NULL
);
```

Una transaccion que pueda cambiar membresia, orden, resumen, facets,
autorizacion o representacion actualiza primero las filas de proyeccion y
sube la generacion una sola vez al final. Un no-op por contenido identico o un
replay idempotente no la incrementa. La lista lee generacion, items,
`total_count` y facets bajo la misma fotografia; las paginas siguientes
comparan el contador incluido en el cursor y fallan con
`TS_QUERY_SNAPSHOT_CHANGED` cuando difiere.

La proyeccion se actualiza sincronicamente por el mismo servicio de dominio y
la misma transaccion que cambia la fuente. Un job de reconciliacion detecta
divergencia, pero no se usa una cola asincrona para obtener correccion normal.
La reconstruccion completa crea una tabla sombra, compara conteos y hashes y
hace un swap controlado que incrementa la generacion una vez; nunca vacia la
vista servida mientras recalcula.

### Forma de las consultas y paginacion

Todos los strings usados para filtrar u ordenar tienen una columna de sort
normalizada en la aplicacion: Unicode normalizado, minusculas, acentos
plegados y colacion binaria estable. La API conserva el texto original para
mostrar. No se depende de la colacion por defecto del servidor.

Cada orden permitido se traduce a una tupla total que termina en `signal_id`.
Los nulos se ordenan mediante una bandera explicita `(value IS NULL, value)` y
esa misma expresion forma parte del indice y del cursor. Para conservar SQL
portable cuando hay direcciones mixtas, el keyset se expresa como una escalera
de comparaciones `>`/`<`; no usa `OFFSET` ni asume que una comparacion de row
values trate los nulos igual en ambos motores.

La busqueda normaliza `q` en tokens y conserva identificadores tecnicos como
terminos buscables. PostgreSQL obtiene candidatos con un `tsvector` de
configuracion `simple` y un indice GIN; SQLite usa FTS5 sobre la misma cadena.
El fallback `LIKE` de SQLite mantiene coincidencia funcional en bases pequenas,
pero no habilita un SLO productivo. Coincidencia exacta de `series_key`, nombre
exacto y prefijos reciben buckets deterministas antes de la relevancia del
motor. El score numerico no se expone y toda igualdad termina en
`updated_at, signal_id`, por lo que el orden permanece paginable.

`total_count` y facets se calculan sobre la proyeccion filtrada en la misma
transaccion read-only que la pagina. Los facets solo se ejecutan con
`include=facets`; un cache privado puede usar
`actor_class + query_hash + generation`, pero un cache nunca mezcla
generaciones ni convierte un conteo aproximado en exacto.

Los filtros de relacion usan `EXISTS`/`NOT EXISTS` contra indices de
asociaciones, bindings y validaciones; no multiplican filas del catalogo con
un join y luego aplican `DISTINCT`. `CompatibilityDecision` se evalua solo
para los candidatos de la pagina.

### Indices obligatorios por consulta

El DDL final puede abreviar nombres, pero debe conservar las siguientes claves
y demostrar su uso en los planes. No se agregan todas las combinaciones de
filtros; PostgreSQL combina indices selectivos y la proyeccion evita joins
costosos.

#### Catalogo y objetos

```text
time_series_catalog_entries:
  (updated_at DESC, display_name_sort, signal_id)
  (display_name_sort, signal_id)
  (owner_project_name_sort, signal_id)
  (semantic_type_key, signal_id)
  (coverage_start, signal_id)
  (coverage_end, signal_id)
  (nominal_resolution_seconds, signal_id)
  (association_count, signal_id)
  (binding_count, signal_id)
  (visibility_scope, owner_project_id, set_status, signal_status,
   updated_at DESC, signal_id)
  GIN(search_vector) en PostgreSQL / FTS5(search_text_normalized) en SQLite

linkable_objects:
  UNIQUE (id, project_id)
  (project_id, object_kind, status, id)

time_series_sets:
  UNIQUE (id, series_kind)
  (owner_project_id, series_kind, status, updated_at DESC, id)
  (owner_linkable_object_id, status, updated_at DESC, id)
  UNIQUE parcial (owner_linkable_object_id, object_series_key)
    WHERE series_kind = 'object_specific'
```

La lista contextual por objeto es un `UNION ALL` de dos brazos acotados:
asociaciones `catalog` del objeto y sets `object_specific` cuyo propietario es
ese objeto. Los brazos conservan su discriminador y no pueden solaparse. Se
aplica el keyset a la union final y nunca se obtiene una serie local buscando
por ID en la proyeccion global.

#### Revisiones y valores

```text
time_series_set_revisions:
  UNIQUE (time_series_set_id, revision_number)
  UNIQUE (id, time_series_set_id)
  UNIQUE (id, time_series_set_id, content_hash)
  (time_series_set_id, state, revision_number DESC, id DESC)

time_series_revision_signals:
  PRIMARY KEY (set_revision_id, signal_id)
  UNIQUE (set_revision_id, ordinal)
  (signal_id, set_revision_id)

time_series_periods:
  UNIQUE (set_revision_id, period_index)
  UNIQUE (set_revision_id, timestamp_start)
  UNIQUE (id, set_revision_id)
  (set_revision_id, timestamp_start, id)

time_series_values:
  PRIMARY KEY (set_revision_id, signal_id, time_series_period_id)
  (set_revision_id, time_series_period_id, signal_id)
```

La PK de valores sirve preview de una senal exacta; el segundo indice sirve
materializacion y validacion por periodo de un set multisenal. Preview comienza
por el rango indexado de `time_series_periods` y enlaza solo los valores de la
senal/revision pedida. Ninguna lista de catalogo toca estas tablas.

#### Asociaciones, bindings y ledgers

```text
time_series_catalog_associations:
  UNIQUE parcial (signal_id, linkable_object_id, binding_role_id)
    WHERE status = 'active'
  (linkable_object_id, status, binding_role_id, signal_id, id)
  (signal_id, status, binding_role_id, linkable_object_id, id)

case_time_series_bindings:
  UNIQUE parcial (case_input_variant_id, linkable_object_id, binding_role_id)
    WHERE status = 'active'
  (case_input_variant_id, status, signal_id, id)
  (signal_id, status, set_revision_id, case_input_variant_id, id)
  (time_series_set_id, status, set_revision_id, id)
  (linkable_object_id, status, binding_role_id, case_input_variant_id, id)

time_series_link_validations:
  (catalog_association_id, subject_lifecycle_revision,
   validated_at DESC, id DESC)
  (binding_id, subject_lifecycle_revision, validated_at DESC, id DESC)

time_series_link_events:
  (catalog_association_id, occurred_at DESC, id DESC)
  (binding_id, occurred_at DESC, id DESC)
  (batch_id, id)
```

Los indices de bindings por set/senal hacen que la vista de impacto y los
conteos de staleness recorran consumidores, no `time_series_values`. Eventos
y validaciones siempre se pagan mediante el ID de su sujeto; no existe una
lista global sin cursor.

### Integridad estructural portable

Las reglas que pueden expresarse con FK/UNIQUE/CHECK no dependen solo del
servicio. En particular:

- Todas las FK historicas usan `RESTRICT`; solo staging y filas tecnicas no
  publicadas admiten cascada de limpieza.
- El binding duplica set/revision/hash para poder tener una FK compuesta
  `(set_revision_id, time_series_set_id, bound_content_hash)` hacia
  `time_series_set_revisions(id, time_series_set_id, content_hash)`. Un hash
  incorrecto no llega a commit.
- Asociaciones duplican `time_series_set_id` y el discriminador constante
  `series_kind = 'catalog'`; sus FKs compuestas hacia set y senal impiden crear
  una asociacion para una serie especifica.
- Proyecto se propaga solo donde permite una FK compuesta real con
  `(linkable_object_id, project_id)` o `(set_id, owner_project_id)`. No se usa
  un par textual ni un trigger que intente adivinar pertenencia.
- Checks cierran estados, motivos obligatorios, exclusividad de sujetos en
  ledgers, timestamps y numeros positivos. La aplicacion produce errores
  amigables, pero la BBDD es la ultima defensa.

La condicion de una sola senal por set `object_specific` se implementa de
forma portable con estructura, en vez de depender de un constraint trigger
que SQLite no posee:

1. `time_series_signals` propaga `series_kind` y tiene FK compuesta
   `(time_series_set_id, series_kind) -> time_series_sets(id, series_kind)`.
2. Un indice parcial unico sobre `time_series_signals(time_series_set_id)`
   cuando `series_kind = 'object_specific'` impone como maximo una.
3. `time_series_sets.object_specific_signal_id` es obligatorio solo para
   `object_specific` y nulo para `catalog`.
4. Una FK diferible
   `(object_specific_signal_id, id, object_series_key) ->
   time_series_signals(id, time_series_set_id, series_key)` impone al commit
   que exista esa unica senal, pertenezca al set y tenga la misma clave.

Esta forma cumple el invariante de "exactamente una", permite insertar el set
y la senal dentro de la misma transaccion y funciona en ambos motores. El
servicio reserva primero el ID de la senal: con la secuencia nativa en
PostgreSQL y con un asignador monotono bajo `BEGIN IMMEDIATE` en SQLite. Asi el
set puede guardar desde su `INSERT` un puntero no nulo a la fila que se inserta
antes del commit diferido, sin una ventana en que la identidad local viole el
check. La clave referenciada `(id, time_series_set_id, series_key)` tiene su
propia restriccion `UNIQUE`. Propietario, `series_kind`, clave tecnica y
puntero a la senal se bloquean contra cambios despues de crear la identidad.

Triggers `BEFORE UPDATE OR DELETE` rechazan cualquier cambio a una revision
`sealed` y a sus `revision_signals`, periodos o valores. En estado `building`
solo el servicio de publicacion puede agregar o reemplazar hijos. La transicion
unica `building -> sealed` verifica, antes de mover el puntero vigente:

- revision y set coherentes;
- al menos una senal y un periodo;
- `value_count = signal_count * period_count`, suficiente junto a PK/FK para
  demostrar una celda por cruce;
- cobertura ordenada, periodos no solapados y contrato temporal;
- hash canonico no nulo e igual al calculado sobre la fotografia completa.

El hash se calcula de forma streaming en la aplicacion sobre el orden canonico
`ordinal, period_index`; la BBDD no implementa criptografia de dominio. El
procedimiento de sellado comprueba conteos y el hash esperado y un reconciliador
puede recalcularlo. Nunca se usa una comprobacion posterior para hacer visible
primero una revision dudosa.

Los ledgers de alcance, vinculos, revisiones y definiciones aceptan solo
`INSERT`; triggers identicos en resultado para ambos motores rechazan `UPDATE`
y `DELETE`. Los eventos fallidos permanecen en logs operativos, no en ledgers
de exito.

### Staging, costo y publicacion de revisiones

CSV/XLSX se parsea y valida fuera de una transaccion canonica. Los binarios
quedan en storage de staging bajo un ID generado; metadata, lease y resumen se
guardan en `time_series_ingestions`. Periodos y valores normalizados viven en
tablas de staging indexadas por `ingestion_id`, o en un artefacto tabular
interno verificable. PostgreSQL puede usar `COPY` para poblar staging; SQLite
usa `executemany` en chunks. Ningun dato staged es seleccionable por bindings.

Publicar `replace_full` cuesta `O(periodos * senales)` en escritura, hash y
almacenamiento. `append_tail` tambien crea una fotografia completa: copia por
`INSERT ... SELECT` la base exacta y agrega el tramo, por lo que su costo es el
tamano final, no solo el delta. Esta amplificacion es intencional para conservar
snapshots autocontenidos; el primer corte no comparte fisicamente bloques
entre revisiones.

La transaccion final:

1. reclama la idempotency key y bloquea el ingreso;
2. bloquea el set y, para una serie local, comprueba el propietario activo;
3. repite autorizacion, ETag, token, target, revision/hash base, checksum,
   contrato, impacto, cuota y confirmacion;
4. reserva `revision_number` bajo el lock del set;
5. inserta revision `building`, fotografia de senales, periodos y valores por
   bulk `INSERT ... SELECT`;
6. verifica conteos y hash, sella y mueve `current_revision_id`;
7. agrega fuente, linaje, evento y recibo de dominio;
8. actualiza entradas/contadores de lectura y sube la generacion una vez;
9. completa la respuesta idempotente y hace commit.

La fila vigente anterior nunca se actualiza. Lectores siguen viendo la
revision anterior hasta el commit y luego ven la nueva completa. En PostgreSQL
el insert masivo no bloquea esos lectores; el lock exclusivo se limita al
agregado set. En SQLite bloquea otras escrituras y por eso sus cuotas de archivo
deben mantenerse menores.

Si contrato y hash normalizados coinciden con la revision vigente, el flujo
devuelve `unchanged`, completa la idempotencia y conserva el recibo operativo
de la fuente, pero no crea revision, no mueve puntero, no vuelve stale bindings
ni incrementa generacion.

La deduplicacion es semantica por target, revision base, contrato y hash. No se
deduplican globalmente filas de dos sets o revisiones distintas: hacerlo
debilitaria FKs, inmutabilidad y borrado seguro. Un ingreso listo con el mismo
actor, target, base, checksum y hash normalizado puede reutilizar su validacion
dentro del TTL; despues de publicar, la `Idempotency-Key` es la autoridad del
replay.

### Idempotencia durable

Una tabla comun guarda, como minimo:

```text
actor_id, operation_kind, scope_key, idempotency_key,
request_hash, state, lease_owner, lease_expires_at,
http_status, response_json, resource_refs_json,
created_at, completed_at, expires_at
```

La unicidad es `(actor_id, operation_kind, scope_key, idempotency_key)`.
`request_hash` cubre el payload canonico, headers de precondicion y target. Un
conflicto de clave con otro hash falla; una fila `completed` devuelve exactamente
el resultado guardado.

Para commits sincronos, la reserva y el resultado viven en la misma transaccion
que la mutacion. Dos requests concurrentes se serializan por el indice unico;
si el primero hace rollback, no deja una mutacion sin recibo. Para jobs
asincronos, una reserva `running` usa lease renovable. El job finaliza el
registro dentro de la transaccion que publica; tras un crash, otro worker puede
tomar un lease vencido y repetir con las mismas precondiciones.

Los registros completados se retienen al menos 24 horas. La limpieza elimina
solo el cuerpo de replay vencido y nunca borra la idempotency key/hash que un
evento de auditoria conserve como evidencia.

### Transacciones y orden de locks

No se usa `SERIALIZABLE` por defecto. Las precondiciones explicitas, locks de
agregado, FKs y restricciones unicas dan una semantica mas predecible con menos
reintentos.

En PostgreSQL:

- Lista con summary/facets y prevalidaciones de varias consultas usan una
  transaccion read-only `REPEATABLE READ`.
- Publicaciones, lotes, alcance y cambios administrativos usan `READ COMMITTED`
  y locks explicitos. Despues de bloquear vuelven a leer y validar; ningun dato
  anterior al lock decide el commit.
- Cambiar bindings y materializar una corrida bloquean primero
  `case_input_variants`. Publicar una revision bloquea el set. Materializar
  toma ademas `FOR KEY SHARE` sobre los sets/revisiones exactos para que un
  cambio de puntero observado antes del commit no pase inadvertido.
- Restricciones unicas parciales resuelven la carrera final de asociaciones o
  bindings activos; la excepcion se traduce al codigo estable, nunca a 500.

Todas las mutaciones respetan un orden global: idempotencia; agregados
`time_series_sets` por ID; variantes por ID; objetos por ID; asociaciones o
bindings por ID; ingreso; proyeccion y contador de generacion al final. Los IDs
de un lote se ordenan antes de bloquear. Una violacion detectada hace rollback
completo. Un deadlock excepcional puede reintentarse con jitter un numero
acotado de veces solo porque la operacion lleva idempotency key.

En SQLite, `BEGIN IMMEDIATE` se obtiene antes de releer precondiciones. Parseo,
upload, preview y validacion nunca mantienen abierta esa transaccion. El mismo
orden logico se conserva para que las pruebas detecten dependencias escondidas,
aunque el lock fisico sea global.

#### Lotes de asociaciones y bindings

La prevalidacion de hasta 200 operaciones no toma locks ni reserva filas. El
commit bloquea el agregado correspondiente y todos los sujetos observados en
orden, reautoriza y reevalua el conjunto, luego inserta transiciones,
validaciones, eventos, contadores e incremento de `bindings_revision` en una
transaccion. `bindings_revision` sube una sola vez por variante y el contador
de catalogo una sola vez por lote. Cualquier fila invalida revierte todas.

#### Materializacion de una corrida

Materializacion bloquea la variante, recarga sus bindings activos por el indice
de variante, ordena y bloquea los sets implicados, y verifica revisiones/hashes
exactos antes de leer valores. Crea `scenario_version` y `run` en esa misma
unidad; Julia comienza despues del commit. Por tanto una publicacion anterior
al lock se observa y puede producir stale; una publicacion posterior espera y
no altera el snapshot ya confirmado.

### Consultas por objeto y ausencia de huerfanos

La raiz object-scoped comienza siempre por
`linkable_objects(id, project_id, status)`. No resuelve primero un `signal_id`.
Para `object_specific`, el indice de owner busca sets del objeto y las FK
compuestas prueban simultaneamente propietario y proyecto. Para `catalog`, el
indice de asociaciones por objeto encuentra solamente asociaciones activas o
la historia pedida.

No hay orfandad porque:

- el set especifico referencia por FK compuesta al objeto y proyecto;
- su unica senal se demuestra mediante el puntero/FK diferible descrito;
- revision, periodos y valores forman una cadena de FKs por revision;
- un binding especifico tiene FKs a set, senal, revision/hash y propietario
  igual al objeto destino;
- todo borrado fisico de una raiz referenciada usa `RESTRICT`.

Archivar objeto o serie cambia elegibilidad, no rompe la cadena. La lista
global no ofrece un parametro para ignorar `series_kind`; consume solamente la
proyeccion protegida por FK/CHECK `catalog`. Las pruebas de integridad intentan
insertar directamente la combinacion prohibida en ambos motores, no se limitan
a probar la API.

### Limpieza y reconciliacion

Un worker de mantenimiento reclama jobs por lease. PostgreSQL usa
`FOR UPDATE SKIP LOCKED`; SQLite hace un claim corto bajo su escritor unico.
La limpieza:

- cancela ingresos vencidos que no esten `publishing`;
- marca primero el tombstone en BBDD y elimina luego el binario de staging de
  forma reintentable;
- borra staging normalizado en lotes acotados;
- conserva reportes/ingresos durante las 24 horas ya decididas;
- nunca toca una revision sellada ni la revision 1 `building` que representa
  validamente una definicion local `awaiting_data`.

Se ejecutan reconciliaciones idempotentes de proyeccion, contadores, hashes de
una muestra, completitud de celdas, FKs logicas de migracion y ausencia total
de `object_specific` en la proyeccion global. Una divergencia de seguridad
deshabilita la lectura afectada de forma fail-closed; una reconstruccion solo
se publica si sus conteos y hashes coinciden.

Metricas minimas: latencia y filas examinadas por query fingerprint, cache hit,
espera/duracion de transacciones, deadlocks, `SQLITE_BUSY`, celdas por segundo,
bytes de staging, jobs/leases vencidos, replays/conflictos idempotentes,
generacion, divergencias de proyeccion, filas/bytes e indice bloat de valores.

### Umbrales de escalamiento

La proyeccion de catalogo no espera un umbral: es obligatoria desde el primer
corte porque texto, facets, conteos y ordenes globales ya la justifican.

`time_series_values` comienza sin particionar. Se prepara una migracion a
particiones `HASH(set_revision_id)` en PostgreSQL, inicialmente 32, cuando se
cumpla cualquiera de estas condiciones y un benchmark confirme beneficio:

- mas de 100 millones de filas o 50 GiB de heap+indices;
- mantenimiento/vacuum deja de caber en la ventana operativa;
- preview o materializacion exceden dos veces su presupuesto p95 en tres
  mediciones consecutivas pese a estadisticas, indices y bloat sanos.

La clave por revision coincide con todas las lecturas canonicas y evita que un
rango temporal mezcle revisiones inmutables. Se co-particiona
`time_series_periods` solo si los planes demuestran que es necesario. La
migracion conserva PK/FK y se valida en sombra; no cambia IDs ni hashes.

Se evalua una proyeccion object-scoped adicional cuando un solo objeto supera
100.000 fuentes visibles o su lista p95 excede 300 ms con los indices
anteriores. Un motor de busqueda externo solo se considera al superar un
millón de entradas o mantener busqueda/facets por encima de 1 s despues de
optimizar la proyeccion. Seria siempre derivado, ligado a `catalog_generation`
y con autorizacion/revalidacion en BBDD; nunca fuente de permisos o commits.

Elevar el limite de cinco millones de celdas por revision exige un benchmark y
una decision explicita sobre almacenamiento/particionamiento. No se elude el
limite fragmentando una revision canonica en varias publicaciones parciales.

### Relacion con decisiones anteriores

- **Modelo relacional canonico para series, tipos y objetos vinculables** se
  conserva y recibe FK compuestas para hash, proyecto, discriminador y la
  unica senal local, mas indices para revision/preview/materializacion.
- **Ciclo de vida de asociaciones y bindings versionados** se concreta con
  locks de agregado, unicidad parcial, ledgers inmutables y estados derivados
  sin fan-out destructivo.
- **Alcance global, permisos y promocion entre proyectos** usa la misma
  transaccion para alcance, evento, proyeccion y generacion. Los indices no
  sustituyen el gate de actor.
- **Contrato de consulta y API del catalogo global** obtiene keyset fisico,
  busqueda, snapshot de generacion, exactitud de summary/facets y limites de
  pagina sin tocar valores.
- **Migracion y coexistencia con el modelo actual** debe construir la
  proyeccion y los indices en el espacio `ts_next`, comprobar planes y activar
  los triggers/FKs antes de C6.
- **Modelo y ciclo de vida de series especificas por objeto** conserva su raiz
  comun; el invariante de una senal se implementa con FK diferible y unicidad
  parcial portable en lugar de un trigger de conteo.
- **API y carga de archivos desde series asociadas a objetos** obtiene staging,
  leases, costo copy-on-write, deduplicacion, idempotencia y publicacion
  atomica para JSON/CSV/XLSX.

### Consecuencias y traspasos

La solucion paga almacenamiento por snapshots completos y una proyeccion
transaccional adicional, pero mantiene lecturas previsibles, historia exacta y
fallos cerrados sin imponer infraestructura externa al primer corte. La
diferencia entre motores queda explicita: SQLite prueba el contrato; PostgreSQL
prueba y sostiene la operacion concurrente.

No aparecieron preguntas nuevas ni niebla adicional. Los SLO, planes, intentos
de fuga, carreras, recuperacion de jobs, invariantes directos de BBDD y
umbrales anteriores pasan a "Corte de entrega y criterios de aceptacion" para
convertirse en pruebas. El DDL y los flujos completos pasan a
"Especificacion consolidada del catalogo global y series especificas".
