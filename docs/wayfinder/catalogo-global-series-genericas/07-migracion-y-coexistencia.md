---
id: 07
title: "Migracion y coexistencia con el modelo actual"
map: catalogo-global-series-genericas
label: wayfinder:grilling
status: closed
assignee: codex
blocked_by: [01, 02, 03, 11, 12]
---

## Question

¿Como se introducen el nuevo catalogo de tipos, el registro de objetos y los
nuevos vinculos sin perder series, bindings ni lineage existentes?

Debe decidir la migracion idempotente de `time_series_signals`, el registro
Python canonico, `case_time_series_bindings` por set+clave y referencias
textuales de entidad; la convivencia con revisiones actuales; el tratamiento
del adaptador y migracion hidraulica legacy; y la lectura separada de indices
de resultados. Debe fijar compatibilidad temporal, checkpoints, rollback no
destructivo y momento en que las nuevas escrituras dejan de usar el modelo
anterior.

Debe incorporar las nuevas series especificas sin forzar su alta en el
catalogo global: creacion de las estructuras object-scoped, coexistencia de
lecturas y escrituras genericas/especificas, backfill solo cuando exista una
relacion inequivoca con un objeto, y preservacion de revisiones, archivos,
auditoria y bindings. Tambien debe decidir como se detectan y reportan datos
actuales que parecen especificos pero no tienen un objeto estable creado.

## Resolucion

Resuelto el 2026-08-30 con la autorizacion del usuario de adoptar la
recomendacion propuesta para todas las decisiones y preguntas de este ticket.

### Decision

La introduccion usa una migracion **expandir -> backfill -> verificar ->
cutover -> contraer**, sin big bang y sin dual-write prolongado:

- El esquema nuevo se agrega de forma aditiva y las tablas actuales permanecen
  intactas mientras son la fuente de escritura.
- Un journal de cambios marca sets, objetos y bindings legacy que se ensucian
  durante el backfill. No intenta mantener dos representaciones como escritoras
  en la misma solicitud.
- Los backfills son idempotentes, reanudables y verificables por hash. Una
  ejecucion repetida sobre la misma fuente no crea otra identidad ni otra
  revision.
- Las lecturas canonicas se comparan en sombra antes de servir trafico. El
  cutover ocurre tras una pausa corta de mutaciones, drenaje final del journal
  y verificacion de los checkpoints.
- Despues del cutover existe **un solo escritor canonico**. Las rutas antiguas
  que sigan temporalmente disponibles son adaptadores hacia ese escritor; no
  vuelven a escribir periodos, valores, señales o bindings en el formato
  anterior.
- Las filas anteriores se conservan read-only durante la ventana de
  compatibilidad. No hay borrado, renumeracion oportunista ni reescritura de
  snapshots o corridas historicas.

La migracion conserva exactamente lo que puede probar. No convierte un evento
de revision liviano en una fotografia historica inventada, no fabrica objetos
desde texto ambiguo y no declara valido un binding que no pueda resolver por
FK y por el evaluador de compatibilidad.

### Fases y checkpoints

Cada fase registra un checkpoint duradero con `migration_run_id`, version del
migrador, cursor o watermark, conteos de entrada/salida, hashes agregados,
errores y tiempos. Una fase puede reanudarse, pero no saltarse.

#### C0 - inventario y punto de recuperacion

Antes de cambiar el esquema se genera un manifiesto inmutable por proyecto y
global con:

- conteos y hashes de sets, revisiones, señales, periodos, valores, fuentes,
  bindings de variante, bindings hidraulicos y registros de migracion legacy;
- maxima PK y maxima revision por tabla o set;
- referencias rotas, duplicados logicos, claves desconocidas y archivos fuente
  ausentes o con checksum distinto;
- variantes ejecutables y el fingerprint de su materializacion actual;
- copia consistente de la base y prueba de restauracion en un entorno aislado.

El manifiesto se firma con el hash de su contenido y nunca incluye credenciales
ni valores completos. Cualquier diferencia estructural no explicada detiene C0.

#### C1 - expansion y captura de cambios

Se crean las tablas, columnas, FKs permisivas, catalogos, ledgers y vistas del
modelo nuevo. Las restricciones que dependan del backfill se instalan como no
validadas o se activan al final, segun el motor.

Tambien se instala `time_series_legacy_dirty_roots`, alimentado por el servicio
de dominio o por triggers minimos. Registra la raiz afectada, no duplica el
payload: `set_id`, `case_input_variant_id`, objeto legacy, operacion, secuencia y
momento. Asi el modelo viejo sigue siendo el unico escritor durante el
backfill, pero cada mutacion posterior al watermark vuelve a poner su raiz en
la cola.

La expansion no cambia respuestas, permisos ni navegacion. Si falla, se
deshabilita el migrador y se eliminan solo objetos nuevos vacios; no se toca una
fila legacy.

Durante la coexistencia, las estructuras cuyo nombre ya existe pero cuya
semantica cambia viven en un espacio fisico separado: un schema `ts_next` en
PostgreSQL y tablas con sufijo `_next` en SQLite. Esto incluye identidades,
revisiones, señales por revision, periodos, valores, asociaciones y bindings.
Los IDs preservados se insertan explicitamente en esas tablas y sus secuencias
se avanzan despues del maximo migrado.

No se mezclan hijos legacy y canonicos en la misma tabla: el escritor actual
borra y recrea `time_series_signals` y `time_series_periods` durante ciertos
reemplazos, por lo que podria destruir un backfill en sitio. C6 cambia el
repositorio de dominio hacia el espacio nuevo y revoca escrituras en el
anterior. El nombre fisico final puede resolverse mediante vistas o un rename
transaccional por motor; no forma parte del contrato de API. La contraccion de
los nombres legacy queda para C7.

#### C2 - catalogos persistentes y registro de objetos

Se siembran unidades, clases de datos, tipos semanticos, roles y reglas de
compatibilidad. Luego se materializan `components`, `global_signal_slots` y
`linkable_objects` mediante las reglas exactas descritas mas abajo. C2 puede
repetirse hasta converger y no habilita todavia el catalogo nuevo.

#### C3 - contenido canonico

Se migran sets, identidades de señal, fuentes y la fotografia verificable de
cada set. Los puntos canonicos se escriben bajo una revision exacta; el puntero
`current_revision_id` se mueve solo despues de sellarla y comprobar ambos
hashes. Las revisiones historicas se reconstruyen unicamente cuando existe
evidencia suficiente.

Los sets dirty se vuelven a fotografiar desde la raiz legacy. Un intento
anterior no se corrige en sitio: se descarta solo su revision `building` o se
crea otra fotografia sellada si la anterior ya habia sido publicada.

#### C4 - asociaciones y bindings

Se resuelven las referencias textuales contra `linkable_objects`, se crean las
asociaciones de catalogo comprobables y se convierten los bindings vigentes a
senal, objeto, rol y revision exacta. Cada binding se reautoriza y se reevalua;
no hereda validez por haber funcionado en el modelo anterior.

Una referencia ambigua o incompatible conserva su evidencia legacy, produce
una anomalia y deja la variante fail-closed. No se elige el candidato "mas
parecido".

#### C5 - lecturas sombra y drenaje final

Las consultas nuevas se ejecutan en sombra sobre una muestra que incluye listas,
detalle, revision vigente, previews, candidatos, asociaciones, bindings,
materializacion y rutas object-scoped. Se comparan semantica, conteos, valores,
hashes, autorizacion y linaje; las diferencias esperadas de forma se normalizan
antes de comparar.

Al iniciar el cutover se bloquean temporalmente las mutaciones de series y
bindings, se drena `time_series_legacy_dirty_roots`, se repiten C3 y C4 para las
raices afectadas y se vuelve a ejecutar el manifiesto. Las lecturas continuan
disponibles durante esta pausa.

#### C6 - cutover de lectura y escritura

En un mismo cambio controlado:

1. se habilitan las lecturas canonicas;
2. se habilita el escritor canonico para revisiones, asociaciones, bindings y
   series especificas;
3. se convierten las rutas antiguas permitidas en adaptadores al mismo servicio;
4. se impide por codigo y permisos de BBDD toda escritura directa en las tablas
   legacy de puntos, señales y bindings;
5. se libera la pausa de mutaciones.

Este es el momento preciso en que dejan de existir nuevas escrituras con el
modelo anterior. Habilitar solo la UI nueva no cuenta como cutover.

#### C7 - estabilizacion y contraccion

Se mantienen telemetria, reconciliacion y rutas de compatibilidad durante el
periodo definido. La eliminacion de columnas, tablas o rutas antiguas es una
migracion posterior, separada y destructiva, con su propia autorizacion. Este
mapa no autoriza esa eliminacion.

### Control, idempotencia y evidencia

La implementacion necesita cuatro superficies de control, comunes a SQLite y
PostgreSQL aunque cambie su DDL fisico:

| Superficie | Funcion |
| --- | --- |
| `time_series_migration_runs` | Estado de fases, version, watermarks, manifiestos y checkpoints. |
| `time_series_migration_mappings` | Correspondencia unica entre identidad legacy y canonica, con hash de la fuente observada. |
| `time_series_migration_anomalies` | Hallazgos tipados, severidad, evidencia, resolucion y actor. |
| `time_series_legacy_dirty_roots` | Cola monotona de raices modificadas despues del watermark. |

Una correspondencia usa una clave unica por `source_kind + source_table +
source_id + target_kind`. Si ya existe, el migrador comprueba que el target y
el hash de fuente coincidan; una diferencia es conflicto, nunca un segundo
insert silencioso.

Los lotes se procesan en orden estable y en transacciones acotadas. El estado
del lote avanza despues del commit de sus datos. Un proceso interrumpido puede
repetir el ultimo lote. La ejecucion final debe demostrar convergencia: cero
filas nuevas, cero cambios de mappings y el mismo manifiesto al repetirla sobre
una fuente sin mutaciones.

Todas las filas creadas por el migrador usan un actor tecnico
`system:migration:<migration_run_id>`. Los `created_by` y timestamps originales
se preservan donde representan la identidad previa, pero no se suplanta a ese
usuario como autor de una decision migratoria. El evento de migracion enlaza
ambos hechos.

### Catalogos persistentes y registro Python

`TIME_SERIES_SIGNAL_CATALOG` deja de ser fuente de verdad en dos pasos:

1. En C1-C2 actua como seed versionado de las ocho claves conocidas, sus
   unidades, restricciones y tipos de objeto. `INSERT ... ON CONFLICT` solo
   acepta igualdad del contrato inmutable; una divergencia bloquea el despliegue
   en vez de sobreescribir la BBDD.
2. Durante la lectura sombra, la aplicacion lee el catalogo persistente y
   compara su proyeccion de compatibilidad con el registro Python. Tras C6, la
   BBDD es autoritativa y el registro queda como seed/adaptador generado para
   clientes internos antiguos. El runtime no puede modificar la BBDD desde esa
   constante.

Las claves de `TIME_SERIES_DATA_KINDS` se siembran en
`time_series_data_classes`. Una `signal_key`, clase o unidad desconocida no se
convierte automaticamente en un tipo canonico:

- se conserva el set y su contenido;
- se crea una anomalia bloqueante si participa en un binding activo;
- un administrador debe mapearla a un contrato existente o crear un tipo
  personalizado completo;
- el backfill se reanuda con esa decision registrada.

No se usa una categoria comodin que permita ejecutar datos sin semantica. Para
datos no vinculados puede existir una fila de cuarentena no seleccionable, pero
no aparece en candidatos ni satisface un rol.

### Materializacion de objetos vinculables

El registro se construye con claves deterministas y sin fuzzy matching:

| Origen actual | Objeto canonico |
| --- | --- |
| Señal sin entidad cuyo tipo admite alcance de sistema | `global_signal_slot(project, 'system')` y su `linkable_object`. |
| `component:grid`, `load`, `renewable`, `battery` o `hydro` con clave estable | `components(project_id, component_key, component_type)` y su padre. |
| Sistema, nodo, tramo, planta o unidad hidraulica base | La PK real de la tabla hidraulica y su padre tipado. |
| Referencia a entidad hidraulica de caso | Se sigue su FK hacia la entidad hidraulica base; nunca se usa la PK de la copia de caso como objeto global. |

Los componentes hoy embebidos en casos o drafts se agrupan por
`project_id + component_type + technical_key`. Se crea la fila solo cuando:

- la clave y el tipo son validos y coinciden en todas las apariciones
  autoritativas;
- una referencia de binding se resuelve a exactamente un grupo;
- no existe la misma clave con dos tipos o dos proyectos posibles.

Diferencias de parametros entre casos no crean otra identidad: pertenecen a la
variante o snapshot. En cambio, conflicto de tipo, clave ausente o dos objetos
posibles producen `TS_MIGRATION_OBJECT_AMBIGUOUS`. No se crea un componente solo
porque `entity_id` contenga un texto plausible.

`bus` puede materializarse como componente topologico, pero no recibe
`linkable_object` en este corte. Proyecto, usuario, corrida, publicacion y
consola tampoco se convierten en objetos. El hidro simple conserva
`component:hydro`; no se fusiona con una red hidraulica.

### Sets, señales y procedencia

Para cada set existente:

- se conserva `time_series_sets.id`, nombre, numero y etiqueta de version,
  propietario, estado, actor y timestamps;
- `project_id` pasa a `owner_project_id` y el set inicia con
  `visibility_scope = 'project'`;
- `data_kind`, `timezone` y `content_hash` permanecen como caches de
  compatibilidad hasta el retiro de las rutas antiguas, pero la autoridad pasa
  a la revision vigente;
- la identidad actual de cada señal conserva su `id` y convierte `signal_key`
  en `series_key`; desde C6 esa identidad ya no se borra ni se recicla;
- unidad, clase, tipo semantico, rol, agregacion, columnas fuente y metadata se
  congelan en `time_series_revision_signals`.

El codigo actual puede haber borrado y recreado señales en reemplazos
anteriores. IDs ya eliminados no se inventan ni se reasignan: el migrador
preserva las identidades presentes en C0 y registra esa limitacion en el
manifiesto. Si dos filas actuales del mismo set producen la misma
`series_key`, el set queda en cuarentena hasta resolver el conflicto.

Los `time_series_sources` conservan ID, checksum, filename, media type,
`stored_path` interno y metadata. El migrador verifica el archivo cuando esta
disponible, pero no mueve ni vuelve a cargar bytes como condicion para preservar
la fotografia actual. Un archivo ausente se reporta; nunca se sustituye por el
contenido de otra fuente con igual nombre.

### Revisiones legacy y primera fotografia canonica

Las revisiones actuales son eventos: los puntos se actualizan en sitio o se
borran y recrean bajo el set. Por ello solo la fotografia vigente en C0 esta
garantizada. Se agrega una excepcion migratoria explicita al modelo decidido:

```text
revision.state = legacy_unmaterialized
```

Este estado se permite exclusivamente para filas pre-C6 que no puedan
reconstruirse exactamente. Conserva su ID, numero, hash legacy, fuente,
metadata, actor y fecha, pero:

- no tiene hijos canónicos de periodos o valores;
- nunca puede ser `current_revision_id`, previsualizarse, fijarse ni respaldar
  un binding;
- aparece en historia como evidencia no materializada;
- es inmutable y no puede transformarse en `sealed` sin una reconstruccion cuyo
  hash haya sido verificado.

Esto limita deliberadamente la afirmacion anterior de que toda fila de
`time_series_set_revisions` es una fotografia completa: toda revision **nueva o
ejecutable** sigue siendolo; solo la historia heredada sin datos recibe este
estado. Falsificar valores para cumplir el esquema seria una perdida de linaje
peor que declarar la limitacion.

El algoritmo por set es:

1. Archivar en el ledger la fila original y calcular el hash legacy de los
   puntos vigentes.
2. Si coincide con la ultima revision y el contenido satisface el contrato,
   completar esa misma revision como fotografia `sealed`, conservar su ID y
   guardar `legacy_content_hash` junto al nuevo hash canonico.
3. Si no coincide o no hay ultima revision, crear una revision de baseline con
   numero `max(revision_number) + 1`, motivo `migration_baseline`, y dejar la
   fila previa como `legacy_unmaterialized`. Un mismatch en un set consumido es
   bloqueante.
4. Para revisiones anteriores, reconstruir solo cuando una fuente retenida,
   una cadena completa de diffs, una transformacion reproducible o un origen
   hidraulico permitan obtener exactamente el contenido y verificar su hash.
   Las demas quedan `legacy_unmaterialized`.
5. Encadenar `supersedes_revision_id` por cronologia conocida, sin convertir
   una revision no materializada en fuente ejecutable.

La revision baseline incluye señales, periodos y valores actuales, timezone,
clase, metadata ejecutable, fuente, hash canonico, `migration_run_id` y los
hashes legacy observados. Los bindings migrados apuntan a esta revision o a la
ultima revision sellada exacta; nunca a `current_revision_id` de forma
indirecta.

### Clasificacion de series especificas existentes

Todo set actual se presume `series_kind = catalog`. Solo se clasifica
automaticamente como `object_specific` cuando **todas** estas condiciones son
probables y deterministas:

1. contiene exactamente una señal y una clave valida;
2. señal, origen y todos sus bindings apuntan al mismo `linkable_object` estable
   del mismo proyecto;
3. nunca fue global, combinado, compartido, asociado ni consumido por otro
   objeto;
4. su procedencia declara de forma explicita que nacio como definicion local
   del objeto, no se infiere solo de `entity_type/entity_key`;
5. no proviene de importacion de catalogo, extraccion de draft, transformacion,
   copia de consola ni `hydraulic_legacy_migration`;
6. cumple la igualdad de propietario, unicidad y compatibilidad del modelo
   object-scoped.

En la practica, las procedencias existentes conocidas permanecen `catalog`;
la ruta object-scoped nace canonicamente para definiciones nuevas. Un set que
parece especifico pero no cumple todos los puntos produce
`TS_MIGRATION_OBJECT_SPECIFIC_REVIEW_REQUIRED`. No se oculta del catalogo ni se
reasigna silenciosamente.

Si falta un objeto estable, el contenido y su historia se preservan, pero no se
crea asociacion ni binding nuevo. La anomalia incluye proyecto, set, señal,
texto de entidad, consumidores observados y candidatos exactos. Si afectaba un
binding vigente, la variante queda fail-closed hasta crear o identificar el
objeto y reanudar el backfill.

### Asociaciones y bindings actuales

`time_series_signals.entity_type/entity_key` se interpreta solo como evidencia
para una asociacion de catalogo. Se crea una asociacion activa cuando objeto,
proyecto, tipo, unidad y regla positiva coinciden exactamente. Una señal sin
entidad usa `global:system` solo si su tipo y rol lo permiten; `NULL` no se
convierte universalmente en sistema.

Cada fila vigente de `case_time_series_bindings` se migra asi:

- se conserva su ID como la primera fila canonica activa cuando la
  transformacion en sitio es posible;
- `signal_key + time_series_set_id` debe resolver exactamente una identidad de
  señal vigente;
- `entity_type/entity_id` debe resolver exactamente un `linkable_object` de la
  variante y su proyecto;
- el rol se deriva por tabla explicita de aliases hacia
  `time_series_binding_roles`, no por coincidencia parcial;
- se fija `set_revision_id` y `bound_content_hash` de la fotografia sellada;
- `source_kind` es `catalog` y enlaza la asociacion creada, o
  `object_specific` con propietario exacto y sin asociacion;
- `required`, actores y timestamps se conservan; la fila original completa se
  guarda como evidencia de migracion;
- el evaluador canonico vuelve a comprobar autorizacion, alcance,
  compatibilidad, cobertura y objeto antes de marcarla validada.

El modelo anterior actualiza el binding en sitio y no conserva reemplazos. La
migracion preserva el estado observable en C0, pero no inventa versiones
anteriores. Desde C6 todo reemplazo es append-only y queda en el ledger
canonico.

Un binding que no pueda migrarse no cae de vuelta al lector legacy durante una
corrida canonica. Se registra una anomalia bloqueante y la variante no puede
materializarse hasta resolverla o retirar el binding expresamente. Los
`validation_dependencies` de topologia y parametros se mantienen; la
dependencia del contenido pasa al binding exacto.

Las `scenario_versions`, corridas y publicaciones ya materializadas no se
regeneran. Sus `system_case_json`, artifacts y `generation_metadata_json`
siguen siendo el linaje autoritativo de esa ejecucion, aun si su binding de
origen resulta ambiguo durante la migracion.

### Codigos de anomalia y bloqueo

Como minimo se emiten codigos estables para:

| Codigo | Tratamiento |
| --- | --- |
| `TS_MIGRATION_UNKNOWN_SEMANTIC_TYPE` | Requiere mapeo o alta administrativa; bloquea si esta en uso. |
| `TS_MIGRATION_UNKNOWN_UNIT` | No convierte unidades; bloquea publicacion o binding. |
| `TS_MIGRATION_DUPLICATE_SERIES_KEY` | Cuarentena del set hasta separar identidades. |
| `TS_MIGRATION_OBJECT_NOT_FOUND` | Conserva contenido, omite vinculo y bloquea consumidores. |
| `TS_MIGRATION_OBJECT_AMBIGUOUS` | Exige seleccion humana de una identidad estable. |
| `TS_MIGRATION_PROJECT_MISMATCH` | Nunca cruza el proyecto; bloqueante. |
| `TS_MIGRATION_BINDING_ROLE_UNRESOLVED` | Binding no ejecutable hasta mapear el rol. |
| `TS_MIGRATION_REVISION_UNMATERIALIZED` | Historia visible pero no seleccionable. |
| `TS_MIGRATION_HASH_MISMATCH` | Detiene la raiz y exige investigacion. |
| `TS_MIGRATION_OBJECT_SPECIFIC_REVIEW_REQUIRED` | No reclasifica ni crea propietario automaticamente. |

Cada anomalia tiene severidad `blocking` o `warning`, sujeto, evidencia JSON,
primer/ultimo avistamiento, estado y resolucion. Un waiver no vuelve compatible
un dato: solo permite excluir explicitamente una fila no usada del alcance de
cutover. No se puede dispensar un binding activo, un hash mismatch ni una fuga
de proyecto.

### Compatibilidad temporal de API y escritores

Las rutas actuales `/api/projects/{project_id}/time-series-sets` permanecen
como aliases solo para sets `catalog` del proyecto propietario. Nunca listan,
leen ni mutan `object_specific`.

Despues de C6:

- las lecturas antiguas se construyen desde vistas canonicas y conservan la
  forma anterior mientras sea representable;
- `/revisions` incluye las filas legacy con su metadata original y las nuevas
  revisiones; una fila `legacy_unmaterialized` no ofrece preview;
- `PUT .../values` y `POST .../replace` preparan y publican una revision
  canonica completa, nunca actualizan puntos en sitio;
- esas escrituras exigen `If-Match` e `Idempotency-Key`. Si la fuente es global,
  compartida o requiere confirmacion de impacto, el alias responde
  `TS_LINK_CONFIRMATION_REQUIRED` y dirige al flujo canonico de dos fases;
- `POST .../replace/upload` crea un staging server-side. El payload legacy puede
  conservar su forma, pero `stored_path` solo se acepta si resuelve a un staging
  emitido para el mismo actor, proyecto, checksum y TTL; nunca se usa como ruta
  confiable suministrada por el cliente;
- escritores internos como importacion CSV/XLSX, conectores, transformaciones,
  regeneracion, extraccion de draft, copias de consola e hidro generico llaman
  la misma canalizacion de revision canonica.

Desde la primera version con C6, todo alias devuelve:

```text
Deprecation: true
Sunset: <fecha RFC 7231 publicada>
Link: <ruta-canonica>; rel="successor-version"
```

La ventana minima es de 90 dias y dos releases ordinarios, lo que sea mayor. La
ruta no se retira hasta observar 30 dias consecutivos sin consumidores y tener
pruebas de contrato de su sucesora. Al vencer, una escritura responde `410`
con codigo y enlace estable; no revive el escritor anterior. Las lecturas
historicas pueden conservarse mas tiempo si son necesarias para auditoria.

### Hidraulica legacy

El adaptador hidraulico y `hydraulic_time_series_set_migrations` se conservan:

- las tablas legacy siguen visibles bajo la seccion `legacy` y permanecen
  separadas de `inputs`;
- la migracion bajo demanda continua siendo idempotente y registra ID legacy,
  ID de set/señal/revision canonicos, hash legacy, hash canonico, actor y fecha;
- volver a migrar la misma identidad devuelve el mapping existente despues de
  verificar sus hashes;
- el set creado por el flujo actual sigue siendo `catalog`; no se reinterpreta
  como `object_specific` por tener una sola entidad;
- no se ejecuta una migracion masiva automatica ni se reescriben bindings
  hidraulicos existentes;
- una migracion o vinculacion nueva usa el objeto hidraulico base normalizado y
  el modelo canonico; el adaptador puede sostener lecturas y corridas antiguas
  hasta que cada binding se reemplace explicitamente;
- al llegar C6 se detienen nuevas escrituras en tablas hidraulicas de series.
  Una actualizacion nueva debe publicar una revision generica o una serie
  object-scoped creada expresamente desde el objeto.

Una corrida o snapshot antiguo puede seguir leyendo su referencia legacy. Una
corrida nueva no mezcla silenciosamente un binding legacy y uno canonico para
el mismo objeto y rol; la seleccion debe ser unica y explicita.

### Resultados e indices derivados

Los indices de resultados, summaries, artifacts y snapshots de corrida no se
backfillean como entradas y no reciben `time_series_signal_id`. Las rutas
`catalog/results` leen sus descriptores por separado y mantienen el linaje a la
corrida y `scenario_version`.

La limpieza o reconstruccion de indices derivados conserva el contrato TS-5 y
no participa en el checkpoint de contenido de inputs. Un resultado solo puede
entrar al catalogo mediante una transformacion versionada y auditable futura;
la migracion no crea esa transformacion.

### Gates de cutover

C6 requiere evidencia conjunta, no solo que el proceso haya terminado:

- backup restaurado con exito y manifiestos C0/C5 conciliados;
- seeds persistentes iguales a sus contratos y registro Python sin divergencia;
- 100% de los sets activos con revision vigente `sealed`, hash verificado y
  puntos completos;
- 100% de los bindings activos migrados y revalidados, o retirados
  explicitamente; cero anomalias bloqueantes;
- cero referencias de proyecto cruzadas y cero series object-scoped visibles
  desde `catalog/inputs`;
- repeticion idempotente sin nuevas filas ni mappings cambiados;
- paridad de lecturas, materializacion y autorizacion en la muestra acordada;
- prueba de los aliases, headers, telemetria y ruta de staging;
- drenaje final del journal a secuencia cero y segunda comprobacion despues de
  liberar una ventana de prueba;
- ejercicio de rollback anterior a escrituras canonicas y ejercicio de pausa +
  roll-forward para el estado posterior.

Los presupuestos exactos de volumen, latencia, locks e indices pertenecen a
"Rendimiento, indices e integridad transaccional"; C6 tambien debe cumplirlos
cuando ese ticket los fije.

### Rollback no destructivo

El rollback depende del checkpoint:

| Momento | Accion permitida |
| --- | --- |
| Antes de lecturas canonicas | Detener migrador y volver al binario anterior; legacy no cambio. |
| Lecturas canonicas activas, escritor legacy aun activo | Desactivar el flag de lectura, drenar o descartar solo artefactos nuevos no publicados y continuar legacy. |
| Pausa final antes de C6 | Cancelar el cutover, liberar la pausa y volver a ensuciar las raices; repetir C3-C5 despues. |
| Despues de la primera escritura canonica | No volver al escritor legacy. Pausar mutaciones, mantener lecturas canonicas y hacer roll-forward o desplegar un binario compatible con el esquema nuevo. |

El ultimo limite es intencional: alcance global, revisiones inmutables,
asociaciones append-only y series especificas no se representan sin perdida en
el modelo anterior. Un "rollback" que copiara esos datos hacia atras seria otra
migracion destructiva y no se autoriza.

Las flags son separadas para lectura sombra, lectura canonica, escritura
canonica y aliases legacy. Ninguna flag elimina datos. La contraccion ocurre
solo despues de expirar la ventana, archivar los manifiestos y aprobar una
migracion independiente.

### Relacion con decisiones anteriores

- **Modelo relacional canonico para series, tipos y objetos vinculables** se
  conserva. Se agrega unicamente el estado migratorio
  `legacy_unmaterialized` para historia que no puede convertirse honestamente
  en snapshot; nunca es ejecutable.
- **Contrato de compatibilidad entre tipos de serie y objetos** se aplica al
  backfill y al cutover. Los aliases no pueden saltarlo.
- **Ciclo de vida de asociaciones y bindings versionados** comienza de forma
  append-only en C6. La migracion conserva el estado vigente observable, no
  inventa reemplazos historicos ausentes.
- **Alcance global, permisos y promocion entre proyectos** se conserva. Todos
  los sets existentes parten `project`; ninguna migracion promueve por uso.
- **Contrato de consulta y API del catalogo global** se conserva y recibe los
  aliases, headers y condiciones de retiro definidos aqui.
- **Modelo y ciclo de vida de series especificas por objeto** se conserva. Las
  definiciones nuevas nacen object-scoped; el backfill antiguo exige evidencia
  inequivoca y nunca crea una asociacion ficticia.
- **API y carga de archivos desde series asociadas a objetos** se conserva. Los
  endpoints antiguos convergen a staging y publicacion canonicos sin confiar en
  `stored_path` ni relajar ETags, confirmacion o idempotencia.

No aparecieron preguntas nuevas ni niebla adicional. Locks, triggers, indices,
particionamiento, jobs de reconciliacion y limpieza de staging pasan a
"Rendimiento, indices e integridad transaccional". Los gates anteriores pasan a
"Corte de entrega y criterios de aceptacion" para convertirse en pruebas
ejecutables, y el detalle completo pasa a "Especificacion consolidada del
catalogo global y series especificas".
