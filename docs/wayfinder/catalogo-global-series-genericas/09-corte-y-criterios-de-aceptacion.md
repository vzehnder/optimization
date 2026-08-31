---
id: 09
title: "Corte de entrega y criterios de aceptacion"
map: catalogo-global-series-genericas
label: wayfinder:grilling
status: closed
assignee: claude
blocked_by: [03, 04, 06, 07, 08, 11, 12]
---

## Question

¿Cual es el corte implementable minimo que entrega el flujo completo de buscar
y vincular sin dejar ambigua la seguridad, migracion o auditoria?

Debe convertir las decisiones y el prototipo en historias observables y una
matriz de aceptacion: catalogo global, taxonomia, detalle, asociaciones,
bindings, operaciones masivas, revision/staleness, permisos, legacy,
resultados read-only, rendimiento y regresion de los flujos TS-2 a TS-6. Debe
separar explicitamente MVP, extensiones posteriores y condiciones de rollback.

La matriz debe probar ademas ambos caminos completos: vincular una serie
generica existente y crear una serie especifica despues de crear el objeto.
Para esta ultima debe verificar alta de la definicion, carga inicial,
actualizaciones por API y archivo, revision/auditoria, consumo por bindings,
aislamiento al objeto y ausencia en el catalogo global.

Tambien debe probar la carga iniciada desde un objeto sobre una serie generica
asociada: autorizacion, previsualizacion del impacto compartido, confirmacion
explicita, staleness de consumidores y alternativa de crear una especifica sin
modificar la generica.

## Resolucion

Resuelto el 2026-08-30 con la autorizacion del usuario de adoptar la
recomendacion propuesta para todas las decisiones y preguntas de este ticket.

### Decision

El corte es **una sola entrega visible que llega hasta el cutover C6**. No se
expone ninguna superficie nueva al usuario antes de que exista el escritor
canonico. Las banderas separadas que fijo "Migracion y coexistencia con el
modelo actual" (`ts_next_shadow_read`, `ts_next_canonical_read`,
`ts_next_canonical_write`, `ts_legacy_aliases`) se escalonan en operacion, pero
`ts_next_canonical_read` se abre primero solo para las cuentas de verificacion,
nunca para todos los usuarios internos: un catalogo que se puede leer y no se
puede mutar ensena un modelo que todavia no existe y produce reportes falsos.

La regla del corte tiene una sola forma:

```text
entra en el MVP  <=>  sin eso no se puede apagar el escritor legacy
                      sin perder capacidad, seguridad o historia
```

Entra al MVP lo que cumple al menos una de estas cuatro condiciones:

1. preserva una capacidad que TS-2 a TS-6 ya entregan;
2. es necesario para que despues del cutover exista **un unico escritor
   canonico**;
3. completa de punta a punta uno de los dos caminos del destino: vincular una
   generica existente, o crear una serie especifica despues del objeto;
4. cierra una ambiguedad de seguridad, migracion o auditoria, es decir, no deja
   ningun camino de autorizacion o de evidencia sin ejercitar.

Sale del MVP lo que es densidad, comodidad analitica u optimizacion y **puede
agregarse despues sin migrar datos ni cambiar un contrato ya decidido**. Aplazar
una superficie no reabre su contrato: los recursos definidos en "Contrato de
consulta y API del catalogo global" y en "API y carga de archivos desde series
asociadas a objetos" se conservan tal como fueron resueltos; solo cambia el
momento en que se implementan.

Las decisiones de este corte se identifican como iteracion **TS-7**, siguiendo
la numeracion de iteraciones del repositorio. Los tickets de implementacion que
produzca "Especificacion consolidada del catalogo global y series especificas"
usan el prefijo `TS7-0NN`.

### Alcance del MVP

| Bloque | Contenido minimo | Condicion que lo justifica |
| --- | --- | --- |
| Modelo canonico | Identidades, revisiones selladas, senales por revision, periodos, valores, `linkable_objects`, ledgers | 2, 4 |
| Catalogos persistentes | Unidades, clases de datos, tipos semanticos canonicos sembrados, roles y matriz de compatibilidad | 1, 2 |
| Tipos personalizados | Alta administrada con contrato completo y mapeo de una clave desconocida | 4 (desbloquea anomalias de C2/C4) |
| Proyeccion de catalogo | `time_series_catalog_entries` transaccional, una fila por senal `catalog` | 1, 2 |
| Lectura del catalogo | `GET /inputs`, detalle, revisiones, preview, `descriptors`, `object-candidates` | 1, 3 |
| Asociaciones | Lista, detalle, eventos, `association-prevalidations`, `association-batches` atomico | 3 |
| Bindings | Lista efectiva e historica, detalle, eventos, prevalidacion y lote por variante | 1, 3 |
| Series especificas | Definicion local, ingesta por puntos y por archivo CSV/XLSX, preview, publicacion, revisiones, archivado, binding | 3 |
| Generica compartida | `SHARED_TARGET` con impacto, confirmacion reforzada y derivacion a especifica | 3, 4 |
| Alcance | Promocion y despromocion administrativas con prevalidacion de impacto | 4 |
| Autorizacion | `require_internal`, `require_admin`, invariantes de proyecto y alcance, rechazo `external`, no enumeracion | 4 |
| Auditoria | Ledger inmutable con actor, motivo, `request_id` y actor tecnico de migracion | 4 |
| Legacy | Adaptador y detalle de estado de migracion | 1, 4 |
| Migracion | C0 a C6 completos, con manifiestos, mappings, anomalias y journal de raices sucias | 2, 4 |
| Rendimiento | Fixture PostgreSQL y presupuestos bloqueantes de la tabla de aceptacion | 4 |

Dos inclusiones merecen justificarse porque parecen ampliaciones y no lo son:

- **El lote atomico de asociaciones y bindings es MVP**; la mesa masiva tabular
  no. El lote es el unico camino de mutacion decidido, asi que el contrato debe
  nacer completo, hasta 200 operaciones y todo o nada. Lo que se aplaza es la
  superficie de seleccion densa, no el endpoint que la sostiene.
- **La promocion de alcance es MVP.** Sin ella `visibility_scope = global` queda
  como codigo no ejercitado y la regla de reutilizacion entre proyectos nunca se
  prueba. Un camino de autorizacion sin ejercitar es exactamente lo que la
  condicion 4 prohibe dejar abierto.

### Extensiones posteriores

Ninguna de estas requiere migrar datos ni cambiar un contrato ya resuelto:

| Extension | Motivo del aplazamiento |
| --- | --- |
| Mesa masiva tabular con seleccion, prevalidacion visual y reporte descargable | La API atomica ya existe en el MVP; solo falta densidad de UI |
| `total_count` exacto y facets exactos en la lista | Es la consulta mas cara del contrato; el MVP pagina por cursor con `has_more` |
| Superficies `/results` y `/legacy` como pestanas del catalogo | El MVP garantiza la separacion por ausencia, no por una vista nueva |
| Publicacion asincrona sobre el presupuesto sincrono | El MVP rechaza el exceso con `TS_INGEST_PAYLOAD_TOO_LARGE` o `TS_INGEST_QUOTA_EXCEEDED`, que es un limite honesto y estable |
| Administracion avanzada de tipos: deprecacion, fusion, edicion en lote | El alta y el mapeo bastan para desbloquear la migracion |
| Transformaciones versionadas de resultado a entrada | Ya declarado fuera de alcance del mapa |
| Contraccion C7: eliminar columnas, tablas y rutas legacy | Destructiva; exige autorizacion propia y una migracion separada |

### Historias observables

Cada historia es verificable por un tercero sin leer el codigo.

- **H-01** Como `analyst`, busco por texto, tipo semantico, clase, unidad,
  alcance y estado, y obtengo una lista signal-first paginada por cursor con
  propietario y alcance visibles.
- **H-02** Como `analyst`, abro una senal y veo contrato, procedencia, revision
  vigente con hash, cobertura, resolucion y consumidores, sin descargar puntos.
- **H-03** Como `analyst`, pido un preview acotado de una revision exacta y
  recibo una muestra normalizada, nunca la serie completa.
- **H-04** Como `analyst`, desde el catalogo elijo una senal, un objeto y un rol
  compatibles, prevalido y confirmo; la asociacion queda activa y auditada.
- **H-05** Como `analyst`, un candidato incompatible se muestra explicado y
  bloqueado, con codigo estable, y no puedo seleccionarlo ni forzarlo por API.
- **H-06** Como `analyst`, desde una variante fijo un binding a una revision y
  hash exactos; la confirmacion muestra revision, cobertura y resolucion.
- **H-07** Como `analyst`, cuando la fuente publica una revision nueva, el
  binding queda `stale`, bloquea la ejecucion y ofrece comparar, revalidar el
  pin o reemplazar con motivo; el binding anterior sobrevive como historia.
- **H-08** Como `analyst`, desde un objeto existente creo una serie especifica,
  cargo su primera revision por archivo y la publico; la etiqueta
  `Solo este objeto` acompana todos los pasos.
- **H-09** Como `analyst`, actualizo esa serie especifica por API y por archivo;
  cada publicacion sella una revision nueva sin reasignar identidad.
- **H-10** Como `analyst`, vinculo la serie especifica a su propio objeto sin
  crear ninguna asociacion de catalogo.
- **H-11** Como `analyst`, esa serie especifica no aparece nunca en
  `catalog/inputs` ni como candidata de otro objeto.
- **H-12** Como `analyst`, desde un objeto intento cargar valores sobre una
  generica compartida: veo alcance, propietario, revision vigente, cantidad de
  asociaciones y consumidores que quedaran stale antes de decidir.
- **H-13** Como `analyst`, elijo **Crear especifica para este objeto** y obtengo
  una identidad local derivada con linaje, sin tocar la fuente compartida ni sus
  otros consumidores.
- **H-14** Como `admin`, elijo **Publicar para todos**, doy motivo y marco la
  comprension; la revision comun se sella y los consumidores afectados quedan
  visiblemente stale, sin resolverse solos.
- **H-15** Como `admin`, promuevo un set a `global` tras ver su impacto, y lo
  despromuevo despues sin perder historia ni romper consumidores.
- **H-16** Como `external`, cualquier ruta del catalogo, de valores, de
  asociaciones o de bindings me responde igual que si no existiera.
- **H-17** Como operador de la migracion, ejecuto el migrador dos veces sobre
  una fuente sin cambios y obtengo el mismo manifiesto, cero filas nuevas y cero
  mappings alterados.
- **H-18** Como operador, despues del cutover ninguna escritura llega a las
  tablas legacy de puntos, senales o bindings, ni por codigo ni por permisos de
  base de datos.

### Matriz de aceptacion

Niveles de evidencia:

| Nivel | Significado |
| --- | --- |
| N1 | `unittest` de dominio, sin HTTP |
| N2 | `unittest` de contrato HTTP contra el PostgreSQL de desarrollo |
| N3 | `vitest` mas `tsc`, `eslint` y `build` del frontend |
| N4 | Verificacion manual en Chrome con las credenciales reales de `.env` (`MAIL_USUARIO_TEST` y `PASSWORD_MAIL_USUARIO_TEST`); no se crean administradores de prueba ni se desactiva la autenticacion |
| N5 | Fixture de rendimiento PostgreSQL con `EXPLAIN (ANALYZE, BUFFERS)` de referencia |
| N6 | Ejecucion del migrador con manifiesto, convergencia y comparacion en sombra |

`Bloquea = si` significa que el corte no se entrega sin ese criterio verde.

#### Catalogo y taxonomia (H-01, H-02, H-03)

| ID | Criterio observable | Evidencia | Bloquea |
| --- | --- | --- | --- |
| AC-CAT-01 | La lista devuelve una fila por senal, con propietario, alcance, tipo, clase, unidad, cobertura y resolucion | N2, N3 | si |
| AC-CAT-02 | Los filtros combinables producen el mismo conjunto que la consulta equivalente sobre las tablas canonicas | N2 | si |
| AC-CAT-03 | Un cursor alterado o vencido responde `TS_QUERY_CURSOR_MISMATCH` o `TS_QUERY_CURSOR_EXPIRED`, nunca una pagina silenciosamente distinta | N2 | si |
| AC-CAT-04 | La lista nunca lee periodos ni valores: el plan de la consulta toca solo la proyeccion y sus indices | N5 | si |
| AC-CAT-05 | Los tipos semanticos y unidades provienen de la base de datos; si `TIME_SERIES_SIGNAL_CATALOG` diverge del contrato sembrado, el despliegue se bloquea | N1, N6 | si |
| AC-CAT-06 | Un tipo personalizado creado por `admin` con contrato completo aparece como filtro y como candidato valido | N2, N4 | si |
| AC-CAT-07 | Una senal archivada se lee y conserva historia, pero no admite asociaciones, bindings ni revisiones nuevas | N2 | si |

#### Detalle, revision y preview (H-02, H-03)

| ID | Criterio observable | Evidencia | Bloquea |
| --- | --- | --- | --- |
| AC-DET-01 | El detalle expone contrato completo, procedencia, revision vigente y hash | N2 | si |
| AC-DET-02 | La historia de revisiones pagina metadata inmutable y no altera el puntero vigente | N2 | si |
| AC-DET-03 | Un preview sobre el limite responde `TS_PREVIEW_TOO_LARGE` en vez de truncar en silencio | N2 | si |
| AC-DET-04 | El preview cita siempre la revision exacta consultada, nunca un `current_revision_id` implicito | N2 | si |

#### Asociaciones (H-04, H-05)

| ID | Criterio observable | Evidencia | Bloquea |
| --- | --- | --- | --- |
| AC-ASO-01 | La prevalidacion no escribe nada: repetirla deja la base identica | N1, N2 | si |
| AC-ASO-02 | Un lote con una fila incompatible se rechaza entero con `TS_LINK_BATCH_REJECTED` y no deja exitos parciales | N2 | si |
| AC-ASO-03 | Solo existe una asociacion activa por `signal_id + linkable_object_id + binding_role_id` | N1 | si |
| AC-ASO-04 | Una fuente `project` contra un objeto de otro proyecto responde `TS_COMPAT_SCOPE_NOT_ACCESSIBLE` aunque la prevalidacion previa haya sido correcta | N2 | si |
| AC-ASO-05 | Un cambio del estado del mundo entre prevalidacion y confirmacion responde `TS_LINK_PRECONDITION_CHANGED` y exige recalcular | N2 | si |
| AC-ASO-06 | Cambiar senal, objeto o rol crea una fila nueva y conserva la anterior consultable | N1 | si |

#### Bindings, revision y staleness (H-06, H-07)

| ID | Criterio observable | Evidencia | Bloquea |
| --- | --- | --- | --- |
| AC-BIN-01 | Solo existe un binding activo por `case_input_variant_id + linkable_object_id + binding_role_id` | N1 | si |
| AC-BIN-02 | Un binding fija revision y hash exactos y no sigue `current_revision_id` tras una publicacion nueva | N1, N2 | si |
| AC-BIN-03 | Publicar una revision deja stale a los consumidores y bloquea su ejecucion; ninguna variante se mueve sola | N2, N4 | si |
| AC-BIN-04 | `stale` e `invalid` son derivados: un cliente que los envia no evita la validacion | N2 | si |
| AC-BIN-05 | Reemplazar exige comparacion y motivo, y el binding anterior queda en historial consultable | N2, N3 | si |
| AC-BIN-06 | Objeto y variante de proyectos distintos responden `TS_COMPAT_PROJECT_CONTEXT_MISMATCH` | N2 | si |
| AC-BIN-07 | Una corrida conserva el linaje exacto dentro de su `scenario_version` inmutable | N1, N2 | si |

#### Serie especifica desde el objeto (H-08 a H-11)

| ID | Criterio observable | Evidencia | Bloquea |
| --- | --- | --- | --- |
| AC-ESP-01 | El objeto debe existir antes de la definicion; no hay ruta que cree ambos a la vez | N2 | si |
| AC-ESP-02 | Guardar solo la definicion es valido y la serie queda no seleccionable hasta tener revision sellada | N2, N3 | si |
| AC-ESP-03 | La primera carga por archivo CSV y XLSX valida en staging y solo publica el contenido exacto previsualizado | N2 | si |
| AC-ESP-04 | La actualizacion por API y por archivo produce revisiones nuevas y conserva la identidad | N2 | si |
| AC-ESP-05 | El propietario del objeto es inmutable: ningun `PATCH` lo cambia | N1, N2 | si |
| AC-ESP-06 | La serie especifica no aparece en `catalog/inputs` ni como candidata de otro objeto, en ninguna combinacion de filtros | N2 | si |
| AC-ESP-07 | Su binding se crea sin ninguna asociacion de catalogo intermedia | N1, N2 | si |
| AC-ESP-08 | Archivarla conserva historia, revisiones y bindings pasados | N2 | si |
| AC-ESP-09 | Reenviar la misma ingesta con la misma clave de idempotencia no crea una segunda revision; una clave distinta responde `TS_INGEST_IDEMPOTENCY_CONFLICT` | N2 | si |
| AC-ESP-10 | Una publicacion interrumpida no deja una revision parcial visible: aparece entera o no aparece | N1, N2 | si |

#### Carga desde el objeto sobre una generica compartida (H-12 a H-14)

| ID | Criterio observable | Evidencia | Bloquea |
| --- | --- | --- | --- |
| AC-SHR-01 | Antes de decidir se muestran alcance, propietario, revision vigente, cantidad de asociaciones, otros objetos y proyectos, y bindings que quedaran stale | N2, N4 | si |
| AC-SHR-02 | La alternativa local **Crear especifica para este objeto** se ofrece primero cuando la intencion declarada es local | N3, N4 | si |
| AC-SHR-03 | La accion compartida se rotula **Publicar para todos** y nunca `Guardar` ni `Actualizar` | N3, N4 | si |
| AC-SHR-04 | Sin confirmacion explicita responde `TS_LINK_CONFIRMATION_REQUIRED` o `TS_SHARED_REVISION_CONFIRMATION_REQUIRED` | N2 | si |
| AC-SHR-05 | Un `analyst` sobre una fuente `global` responde `TS_SHARED_REVISION_ADMIN_REQUIRED` | N2 | si |
| AC-SHR-06 | Si el impacto cambia entre preview y confirmacion, la accion se bloquea y exige una confirmacion nueva | N2 | si |
| AC-SHR-07 | Derivar una especifica conserva linaje y no reasigna asociaciones ni bindings automaticamente | N1, N2 | si |
| AC-SHR-08 | Publicar para todos deja los estados stale visibles y no los resuelve en la misma accion | N2, N4 | si |

#### Alcance y promocion (H-15)

| ID | Criterio observable | Evidencia | Bloquea |
| --- | --- | --- | --- |
| AC-SCO-01 | Promover cambia la misma fila y conserva `owner_project_id`, revisiones, asociaciones e historia | N1, N2 | si |
| AC-SCO-02 | `analyst` recibe `TS_SCOPE_ADMIN_REQUIRED` en promocion y despromocion | N2 | si |
| AC-SCO-03 | La despromocion falla cerrada cuando existen consumidores de otros proyectos, con el impacto enumerado | N2 | si |
| AC-SCO-04 | Repetir un cambio ya efectivo responde `TS_SCOPE_ALREADY_EFFECTIVE` sin escribir | N2 | si |

#### Seguridad y auditoria (H-16)

| ID | Criterio observable | Evidencia | Bloquea |
| --- | --- | --- | --- |
| AC-SEG-01 | `external` se rechaza antes de resolver IDs o ejecutar consultas en toda la superficie del catalogo | N2 | si |
| AC-SEG-02 | La respuesta a `external` no revela existencia, conteos ni identificadores fuera de su alcance | N2 | si |
| AC-SEG-03 | Conocer un `ingestion_id`, `association_id` o `signal_id` no omite la autorizacion del objeto ni del proyecto | N2 | si |
| AC-SEG-04 | El detalle usa el mismo gate que la lista: no existe ruta de detalle sin autorizacion de superficie | N2 | si |
| AC-SEG-05 | Toda mutacion deja actor, motivo, `request_id` y momento en un ledger que ninguna ruta publica puede borrar | N1, N2 | si |
| AC-SEG-06 | Ningun cache ni read model convierte una respuesta interna en una respuesta externa | N1, N2 | si |
| AC-SEG-07 | Un error de mutacion confirma que no hubo escritura y conserva el borrador y los filtros | N2, N3 | si |

#### Legacy y resultados read-only

El MVP no publica pestanas nuevas de resultados ni de legacy en el catalogo;
prueba la separacion por ausencia y por el adaptador que ya existe.

| ID | Criterio observable | Evidencia | Bloquea |
| --- | --- | --- | --- |
| AC-LEG-01 | Las series hidraulicas legacy siguen visibles por adaptador con su estado de migracion | N2, N4 | si |
| AC-LEG-02 | Todo vinculo nuevo termina en el modelo generico, incluso cuando parte de una vista legacy | N2 | si |
| AC-LEG-03 | Ningun descriptor de resultado aparece en `catalog/inputs` ni es seleccionable como fuente de un binding | N2 | si |
| AC-LEG-04 | Los indices de resultados de TS-4 siguen siendo reconstruibles y no se funden con las entradas | N1, N2 | si |

#### Migracion y cutover (H-17, H-18)

| ID | Criterio observable | Evidencia | Bloquea |
| --- | --- | --- | --- |
| AC-MIG-01 | C0 produce un manifiesto firmado y una restauracion probada antes de cualquier DDL | N6 | si |
| AC-MIG-02 | Una segunda ejecucion sobre una fuente sin cambios no crea filas ni altera mappings, y repite el manifiesto | N6 | si |
| AC-MIG-03 | Una referencia ambigua produce anomalia y deja la variante fail-closed; no se elige el candidato mas parecido | N1, N6 | si |
| AC-MIG-04 | Cero anomalias bloqueantes abiertas y 100% de bindings activos revalidados o retirados explicitamente antes de C6 | N6 | si |
| AC-MIG-05 | La comparacion en sombra no muestra diferencias de semantica, conteo, valor, hash, autorizacion ni linaje | N6 | si |
| AC-MIG-06 | Tras C6 una escritura directa a las tablas legacy de puntos, senales o bindings falla por codigo y por permisos | N2, N6 | si |
| AC-MIG-07 | Las claves desconocidas no se convierten en tipos canonicos automaticamente y exigen decision administrativa registrada | N1, N6 | si |

#### Rendimiento

Presupuestos p95 en PostgreSQL sobre la fixture de 100.000 entradas, 1.000.000
de asociaciones, 1.000.000 de bindings y 100.000.000 de celdas.

| ID | Operacion | Presupuesto | Evidencia | Bloquea |
| --- | --- | --- | --- | --- |
| AC-PER-01 | Pagina de catalogo de 50 filas sin facets | 300 ms | N5 | si |
| AC-PER-02 | Lista contextual o detalle por objeto | 300 ms | N5 | si |
| AC-PER-03 | Preview de 500 puntos | 500 ms | N5 | si |
| AC-PER-04 | Preview maximo de 2.000 puntos | 1 s | N5 | si |
| AC-PER-05 | Prevalidacion de 200 asociaciones o bindings | 2 s | N5 | si |
| AC-PER-06 | Commit de un lote de 200 sin espera de lock | 2 s | N5 | si |
| AC-PER-07 | Publicacion sincrona de hasta 100.000 celdas | 5 s | N5 | si |
| AC-PER-08 | Pagina con `total_count` y facets exactos | 1 s | N5 | no, llega con la extension |

Ninguna consulta critica puede hacer un full scan de periodos o valores; cada
una guarda su plan de referencia. SQLite ejecuta la fixture de correccion y no
participa de estos presupuestos, pero conserva semantica, errores, FKs,
unicidad, inmutabilidad e idempotencia identicos.

#### Regresion TS-2 a TS-6

| ID | Criterio observable | Evidencia | Bloquea |
| --- | --- | --- | --- |
| AC-REG-01 | Las suites `test_ts2_acceptance` a `test_ts6_acceptance` pasan sin editarse para acomodar el modelo nuevo | N1, N2 | si |
| AC-REG-02 | `GET /api/time-series/signal-catalog` y las rutas actuales de sets responden con la misma forma, ya servidas por el escritor canonico | N2 | si |
| AC-REG-03 | Los flujos de variantes, comparacion de corridas y consola de configuracion conservan su comportamiento observable | N2, N3 | si |
| AC-REG-04 | El adaptador hidraulico de TS-5 y su migracion bajo demanda siguen funcionando | N1, N2 | si |

**Politica de regresion**: ninguna suite existente se modifica para que pase. Si
un cambio de contrato resulta inevitable, se detiene el corte, se documenta el
cambio y se agrega una prueba del adaptador que preserva la forma anterior. Una
prueba editada sin ese registro invalida la aceptacion.

### Condiciones de rollback

Hay dos familias de disparadores. Los de tolerancia cero detienen el avance ante
una sola ocurrencia:

- una anomalia bloqueante abierta;
- cualquier diferencia en la lectura sombra de semantica, conteo, valor, hash,
  autorizacion o linaje;
- una serie object-scoped visible desde `catalog/inputs`;
- una referencia cruzada de proyecto aceptada;
- un binding activo sin revision sellada o sin hash verificado;
- una escritura legacy observada despues del cutover;
- una revision parcial visible.

Los de umbral medido se evaluan sobre la ventana de observacion:

| Disparador | Umbral |
| --- | --- |
| Latencia de una operacion bloqueante | p95 sobre 1,5x su presupuesto durante 15 minutos |
| Errores 5xx de la superficie nueva | mas de 0,5% en 30 minutos |
| Publicaciones fallidas tras reintentos | mas de 1% del lote |
| Divergencia de la reconciliacion diaria | cualquier fila que no concilie |

La accion permitida sigue la tabla de "Migracion y coexistencia con el modelo
actual" y este corte no la amplia. Se agregan los plazos que faltaban:

- **ventana de observacion posterior a C6**: 72 horas con telemetria y
  reconciliacion continuas antes de declarar el corte estable;
- **ventana de compatibilidad**: 30 dias corridos con aliases legacy activos y
  reconciliacion diaria;
- **C7 no se autoriza dentro de este corte**: expirada la ventana y archivados
  los manifiestos, la contraccion es una migracion destructiva separada.

Despues de la primera escritura canonica no se vuelve al escritor legacy: solo
pausa de mutaciones, lecturas canonicas activas y roll-forward. Un rollback que
copiara datos hacia atras seria otra migracion destructiva y no esta autorizado.

### Definicion de hecho

El corte esta entregado cuando, a la vez:

1. toda la matriz con `Bloquea = si` esta verde sobre el PostgreSQL de
   desarrollo, ejecutada por modulo con el runner `unittest` del repositorio;
2. las puertas del frontend `tsc`, `eslint`, `vitest` y `build` pasan;
3. la fixture de rendimiento cumple AC-PER-01 a AC-PER-07 con sus planes
   guardados;
4. el migrador converge y la sombra no muestra diferencias;
5. una verificacion manual en Chrome con las credenciales reales recorre los
   tres flujos completos: vincular una generica, crear y cargar una especifica,
   e intentar la carga compartida desde el objeto con sus dos salidas;
6. el ledger permite reconstruir quien hizo cada mutacion y por que.

### Consecuencias y traspasos

El corte fija tres cosas que la especificacion consolidada debe respetar sin
reabrirlas: el MVP llega hasta C6 y no antes; la mesa masiva, los facets
exactos, las pestanas de resultados y legacy, y la publicacion asincrona son
extensiones declaradas y no huecos; y la regresion TS-2 a TS-6 es una condicion
de entrega, no un objetivo deseable.

No aparecieron preguntas nuevas ni niebla adicional. El siguiente y ultimo
ticket del mapa, "Especificacion consolidada del catalogo global y series
especificas", queda desbloqueado: debe incorporar esta matriz como su capitulo
de aceptacion y enlazar, sin reescribir, las resoluciones anteriores.
