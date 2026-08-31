---
id: 03
title: "Ciclo de vida de asociaciones y bindings versionados"
map: catalogo-global-series-genericas
label: wayfinder:grilling
status: closed
assignee: codex
blocked_by: [01, 02]
---

## Question

¿Cual es la semantica completa de crear, reemplazar, desactivar, revalidar y
auditar asociaciones de catalogo y bindings de ejecucion?

Debe fijar la cardinalidad efectiva, revision/hash congelados, deteccion y
resolucion de staleness, historial de reemplazos, archivado y borrado seguro,
motivos/actores de auditoria, concurrencia optimista y comportamiento atomico
de operaciones masivas. Tambien debe explicar como se materializa una corrida
sin debilitar los snapshots inmutables existentes.

## Resolucion

Resuelto el 2026-08-30 con la autorizacion del usuario de adoptar la
recomendacion propuesta para todas las decisiones y preguntas de este ticket.

### Decision

Asociaciones y bindings tienen ciclos de vida distintos y no se actualizan en
sitio para cambiar su significado:

- Una **asociacion de catalogo** declara que una senal es candidata para un
  objeto y rol. Sigue la identidad estable de la senal y su revision vigente;
  no fija valores ni selecciona una variante.
- Un **binding ejecutable** selecciona para una variante una senal, un objeto,
  un rol y una revision sellada exacta con su hash. Nunca sigue
  silenciosamente `current_revision_id`.
- Cambiar senal, objeto, rol o revision crea una fila nueva y conserva la
  anterior. Los cambios de estado (`archived`, `superseded`, `removed`) solo
  retiran una fila de la vista efectiva; no alteran sus referencias
  historicas.
- `stale` y `invalid` son estados derivados. Ningun cliente puede escribirlos
  para saltarse la validacion.
- Toda mutacion y revalidacion queda atribuida a un actor y motivo en un
  ledger inmutable. Una corrida conserva ademas el linaje exacto dentro de su
  `scenario_version` inmutable.

### Cardinalidad efectiva

La asociacion incorpora el `binding_role_id` decidido en el ticket
"Contrato de compatibilidad entre tipos de serie y objetos". Su unicidad
efectiva es:

```text
signal_id + linkable_object_id + binding_role_id
```

Solo puede existir una asociacion activa para esa terna. Un objeto puede tener
muchas senales candidatas para el mismo rol y una senal puede ser candidata
para varios objetos o roles. Agregar otra candidata no reemplaza las
anteriores.

La unicidad efectiva del binding es:

```text
case_input_variant_id + linkable_object_id + binding_role_id
```

Solo puede existir un binding activo para esa terna. La misma senal puede
llenar varios roles, por ejemplo un precio simetrico para importacion y
exportacion. `required` no es una opcion que el cliente pueda desactivar: la
obligatoriedad se deriva del rol y de la topologia vigente; si se conserva la
columna actual, es una fotografia informativa calculada por el backend.

Las transformaciones de una o varias entradas no rompen esta cardinalidad.
Primero materializan una senal de salida en una revision sellada, como decidio
el contrato de compatibilidad, y solo esa salida recibe el binding ordinario.
No hay bindings ejecutables con una lista de senales calculada en vivo.

### Ajustes conceptuales al modelo

Sobre las tablas decididas en "Modelo relacional canonico para series, tipos y
objetos vinculables" se aplican estos ajustes:

```sql
ALTER TABLE time_series_catalog_associations
    ADD COLUMN binding_role_id BIGINT NOT NULL
        REFERENCES time_series_binding_roles(id),
    ADD COLUMN compatibility_rule_id BIGINT NOT NULL
        REFERENCES time_series_role_compatibilities(id),
    ADD COLUMN supersedes_association_id BIGINT NULL
        REFERENCES time_series_catalog_associations(id),
    ADD COLUMN lifecycle_revision INTEGER NOT NULL DEFAULT 1,
    ADD COLUMN archived_reason_code TEXT NULL,
    ADD COLUMN archived_reason_text TEXT NULL;

DROP INDEX one_active_catalog_association;

CREATE UNIQUE INDEX one_active_catalog_association
    ON time_series_catalog_associations(
        signal_id, linkable_object_id, binding_role_id
    )
    WHERE status = 'active';

ALTER TABLE case_time_series_bindings
    ADD COLUMN compatibility_rule_id BIGINT NOT NULL
        REFERENCES time_series_role_compatibilities(id),
    ADD COLUMN lifecycle_revision INTEGER NOT NULL DEFAULT 1,
    ADD COLUMN superseded_at TIMESTAMP NULL,
    ADD COLUMN superseded_by TEXT NULL,
    ADD COLUMN removed_at TIMESTAMP NULL,
    ADD COLUMN removed_by TEXT NULL,
    ADD COLUMN change_reason_code TEXT NOT NULL,
    ADD COLUMN change_reason_text TEXT NULL;

ALTER TABLE case_input_variants
    ADD COLUMN bindings_revision INTEGER NOT NULL DEFAULT 0;
```

`compatibility_rule_id` conserva la regla usada al crear la fila; no concede
un derecho permanente. La validez se vuelve a calcular contra el contrato
activo. Las FK de asociaciones, bindings, validaciones y eventos usan
`RESTRICT`, nunca `CASCADE`, para no borrar historia al retirar una entidad.

Dos ledgers append-only guardan la evidencia de validacion y de mutacion:

```sql
CREATE TABLE time_series_link_validations (
    id                       BIGINT PRIMARY KEY,
    catalog_association_id   BIGINT NULL
        REFERENCES time_series_catalog_associations(id),
    binding_id               BIGINT NULL
        REFERENCES case_time_series_bindings(id),
    subject_lifecycle_revision INTEGER NOT NULL,
    validation_mode          TEXT NOT NULL CHECK (validation_mode IN (
                                 'association_current',
                                 'binding_current',
                                 'binding_pinned')),
    validated_set_revision_id BIGINT NOT NULL
        REFERENCES time_series_set_revisions(id),
    observed_current_revision_id BIGINT NOT NULL
        REFERENCES time_series_set_revisions(id),
    compatibility_rule_id    BIGINT NOT NULL
        REFERENCES time_series_role_compatibilities(id),
    compatibility_fingerprint TEXT NOT NULL,
    object_scope_fingerprint TEXT NOT NULL,
    variant_dependency_fingerprint TEXT NULL,
    validated_range_json     JSON NULL,
    validated_at             TIMESTAMP NOT NULL,
    validated_by             TEXT NOT NULL,
    reason_code              TEXT NOT NULL,
    reason_text              TEXT NULL,
    CHECK (
      (catalog_association_id IS NOT NULL AND binding_id IS NULL)
      OR
      (catalog_association_id IS NULL AND binding_id IS NOT NULL)
    )
);

CREATE TABLE time_series_link_events (
    id                       BIGINT PRIMARY KEY,
    batch_id                 TEXT NULL,
    catalog_association_id   BIGINT NULL
        REFERENCES time_series_catalog_associations(id),
    binding_id               BIGINT NULL
        REFERENCES case_time_series_bindings(id),
    event_type               TEXT NOT NULL,
    actor_user_id            BIGINT NULL REFERENCES users(id),
    actor_identity_snapshot  TEXT NOT NULL,
    actor_role_snapshot      TEXT NOT NULL,
    reason_code              TEXT NOT NULL,
    reason_text              TEXT NULL,
    before_json              JSON NOT NULL DEFAULT '{}',
    after_json               JSON NOT NULL DEFAULT '{}',
    request_id               TEXT NOT NULL,
    occurred_at              TIMESTAMP NOT NULL,
    CHECK (
      (catalog_association_id IS NOT NULL AND binding_id IS NULL)
      OR
      (catalog_association_id IS NULL AND binding_id IS NOT NULL)
    )
);
```

El DDL es conceptual: el ticket de rendimiento e integridad fijara indices,
triggers y la traduccion SQLite/PostgreSQL. Los fingerprints son hashes
canonicos de los IDs, versiones y estados que intervienen; nunca incluyen
textos localizados.

### Ciclo de vida de una asociacion

#### Crear y agregar

1. Se toma la revision vigente sellada de la senal.
2. Se ejecuta `evaluate_compatibility(..., usage = association)` dentro de la
   transaccion.
3. Se inserta la asociacion activa con senal, objeto, rol y regla usada.
4. Se agrega una validacion `association_current` y un evento `created`.

Crear de nuevo la misma terna activa es un no-op idempotente que devuelve la
fila existente. Una asociacion para otra senal del mismo objeto y rol es una
candidata adicional y no afecta a las demas.

#### Reemplazar

"Reemplazar" es una accion explicita, distinta de agregar. Recibe la
asociacion anterior esperada, muestra la comparacion y, tras confirmacion,
archiva la anterior e inserta la nueva con `supersedes_association_id` en la
misma transaccion. No existe un `UPDATE signal_id` ni un `UPDATE role_id`.

#### Archivar y recrear

Archivar cambia la fila a `archived`, registra actor, fecha y motivo y la
retira de las candidatas seleccionables. No borra ni modifica bindings que la
usaron como procedencia. Un binding activo que apunta a ella queda stale; para
volver a ejecutar debe reemplazarse usando una asociacion activa equivalente
o como binding directo sin esa procedencia, si los permisos lo permiten.

Una asociacion archivada no se reactiva. Recrear la misma terna inserta una
fila nueva enlazada por `supersedes_association_id`, conservando la cadena.

#### Vigencia y revalidacion

La asociacion sigue la revision vigente, por lo que un cambio solo de valores
o `content_hash` no la vuelve stale si su fingerprint de compatibilidad no
cambia. Ese fingerprint incluye proposito de la senal, tipo semantico, unidad,
dimension, clase cuando corresponda, rol, tipo de objeto, alcance y version de
la regla; excluye los puntos de la serie.

Un cambio de ese fingerprint, de alcance, de estado del objeto o de regla
deja la asociacion `active_stale`. La revalidacion toma la revision vigente:
si pasa, agrega otra evidencia y vuelve a `active_valid`; si no pasa, queda
`active_incompatible`. No se archiva automaticamente ni puede originar nuevos
bindings mientras sea incompatible. Si la senal desaparece de la revision
vigente, el resultado tambien es incompatible; nunca se sustituye por otra
senal del mismo tipo.

### Ciclo de vida de un binding

#### Crear

Por defecto, crear un binding selecciona la revision vigente sellada al
momento de confirmar. El backend:

1. verifica variante, objeto, rol, senal, revision, alcance y actor;
2. verifica que `bound_content_hash` sea exactamente el hash de la revision;
3. aplica el evaluador unico con `usage = execution`;
4. verifica la asociacion de procedencia cuando fue indicada;
5. inserta el binding y su validacion `binding_current`;
6. incrementa `case_input_variants.bindings_revision` e invalida la validacion
   ejecutable previa de la variante;
7. registra el evento `created`.

Un binding directo sin asociacion previa sigue permitido. Elegir de entrada
una revision que ya no es vigente se trata como una fijacion explicita y usa
el flujo `binding_pinned`, con comparacion y motivo obligatorio.

#### Reemplazar

La UI y la API presentan una comparacion de senal, revision/hash, objeto, rol,
alcance, cobertura y resultado de compatibilidad. Tras confirmacion, una sola
transaccion:

- bloquea/verifica la fila activa esperada;
- inserta el nuevo binding activo con `supersedes_binding_id` apuntando al
  anterior;
- cambia el anterior a `superseded` y registra actor, fecha y motivo;
- incrementa la revision agregada de bindings de la variante;
- invalida su validacion ejecutable;
- agrega las validaciones y eventos correspondientes.

La restriccion parcial impide que ambos queden activos. La senal y revision de
la fila anterior nunca se sobrescriben.

#### Retirar, restaurar y clonar

Retirar cambia el binding activo a `removed`, exige motivo e invalida la
variante. No se inserta un sustituto y una necesidad requerida queda
incompleta. "Deshacer" no reactiva la fila: crea un binding activo nuevo que
supersede la fila retirada y vuelve a ejecutar todas las validaciones.

Clonar una variante copia las selecciones como bindings nuevos, con nuevos IDs
y eventos `cloned`; conserva referencias a las mismas revisiones exactas solo
si siguen siendo validas. El clon comienza con validacion ejecutable pendiente
y no hereda una aprobacion de staleness de la variante origen.

### Estados derivados y staleness

Una asociacion expone `active_valid`, `active_stale`,
`active_incompatible` o `archived`.

Un binding expone:

| Estado | Significado | Puede ejecutar |
| --- | --- | --- |
| `unvalidated` | No existe validacion exitosa para su revision de ciclo de vida. | no |
| `valid_current` | Fija la revision vigente y todos los fingerprints coinciden. | si |
| `valid_pinned` | Fija una revision anterior aceptada explicitamente frente al contexto vigente. | si |
| `stale` | Cambio una dependencia desde la ultima validacion. | no |
| `invalid` | La seleccion ya no puede cumplir el contrato actual. | no |
| `inactive` | El binding esta `superseded` o `removed`. | no |

Para un binding activo, la validacion exitosa mas reciente debe corresponder a
su `lifecycle_revision`. El estado se deriva fail-closed:

- Si la revision no esta sellada, su hash no coincide, la senal no pertenece a
  ella, o fueron archivados senal, tipo, rol, objeto o set, queda `invalid`.
- Si no existe una regla activa que permita la tupla actual o deja de coincidir
  dimension/unidad, queda `invalid`; una regla historica no da grandfathering.
- Si cambio la regla/fingerprint, el alcance, el estado del objeto en el caso,
  la topologia, los parametros, la asociacion de procedencia o una dependencia
  de una serie derivada, queda `stale` hasta revalidar; si la revalidacion
  encuentra incompatibilidad, pasa a `invalid`.
- Para `binding_current`, si `time_series_sets.current_revision_id` deja de ser
  el `observed_current_revision_id` de la validacion, queda `stale`, aunque el
  nuevo contenido parezca equivalente.
- Para `binding_pinned`, la revision fijada puede diferir de la vigente, pero
  la revision vigente observada al aceptar la fijacion debe seguir siendo la
  actual. Una nueva revision vuelve a dejarlo `stale`.
- Los permisos del actor se comprueban en cada operacion y corrida. Una
  validacion previa nunca concede acceso permanente. Los cambios estructurales
  de alcance forman parte del fingerprint; la matriz exacta la decide
  "Alcance global, permisos y promocion entre proyectos".

El estado de la variante es la composicion de sus bindings, completitud de
roles requeridos y dependencias de topologia/parametros. Cualquier alta,
reemplazo o retiro incrementa `bindings_revision` y vuelve obsoleta la
validacion ejecutable previa. La validacion de un link al crearlo no sustituye
la validacion completa de la variante.

### Resolver staleness

Cuando cambia la revision vigente, la variante se bloquea y el usuario debe
elegir expresamente:

1. **Actualizar a vigente**: crea un binding nuevo hacia la revision actual y
   supersede el anterior. Es la opcion recomendada y predeterminada.
2. **Conservar revision fijada**: reevalua la revision anterior contra el
   contrato, objeto, alcance y dependencias actuales. Si pasa, agrega una
   validacion `binding_pinned`, exige motivo explicito y habilita el estado
   `valid_pinned`. No modifica el binding ni la revision.

Nunca se actualiza automaticamente. Una revision anterior incompatible,
corrupta, no sellada, ausente o afectada por un contrato archivado no puede
fijarse. Los otros motivos de staleness se resuelven revalidando cuando el
mismo binding aun es valido, reemplazandolo, retirandolo o corrigiendo primero
la dependencia externa. La revalidacion no oculta una incompatibilidad.

La validacion puede comprobar anticipadamente un rango y dejarlo como
evidencia, pero la corrida siempre repite cobertura, resolucion y alineacion
para el rango solicitado; una validacion anterior no es un permiso para omitir
esa comprobacion.

### Archivado y borrado seguro

- Series, sets, tipos, roles, reglas y objetos que alguna vez participaron en
  una revision sellada, asociacion, binding, validacion, evento o snapshot se
  archivan; no se borran fisicamente ni se reutilizan sus claves.
- Archivar no hace cascade. Las asociaciones quedan visibles como
  incompatibles y los bindings bloqueados, mientras los snapshots historicos
  siguen legibles y ejecutados con su contenido congelado.
- Asociaciones, bindings, validaciones y eventos nunca tienen una operacion de
  borrado publico.
- Solo pueden purgarse filas tecnicas `building` que nunca se sellaron, nunca
  fueron visibles y no tienen ninguna referencia o evento. Esa limpieza es de
  mantenimiento y queda fuera de las acciones del catalogo.
- Las FK actuales con `ON DELETE CASCADE` que alcancen historia deben migrar a
  `RESTRICT`; la estrategia de coexistencia corresponde a "Migracion y
  coexistencia con el modelo actual".

### Auditoria

Los eventos minimos son `created`, `replaced`, `superseded`, `removed`,
`archived`, `recreated`, `revalidated_current`, `revalidated_pinned` y
`cloned`. Cada uno guarda actor estable, rol observado, instante, request,
motivo, sujeto y referencias antes/despues. Los eventos de una operacion
masiva comparten `batch_id`; cada fila conserva tambien su propio evento para
que la historia sea consultable sin interpretar un payload agregado.

`reason_code` es obligatorio. Acciones ordinarias pueden usar codigos
predefinidos como `user_selection`, `bulk_selection`, `series_updated`,
`object_retired` o `migration`. `revalidated_pinned`, `removed`, `archived` y
`other` exigen ademas texto no vacio. Procesos automaticos usan una identidad
de servicio explicita, nunca un usuario ficticio.

Los ledgers aceptan solo `INSERT`; triggers impiden `UPDATE` y `DELETE`. Los
intentos fallidos de autorizacion, compatibilidad o concurrencia se registran
en el log operativo/seguridad con el mismo `request_id`, pero no crean un
evento de dominio que parezca una mutacion exitosa.

### Concurrencia optimista e idempotencia

- Toda mutacion de bindings recibe `expected_bindings_revision` de la
  variante. Reemplazar o retirar recibe ademas el ID y
  `lifecycle_revision` de la fila activa observada.
- Toda mutacion de asociaciones recibe la fila/version observada o una
  precondicion de ausencia al crear.
- Una prevalidacion devuelve un token opaco que cubre la solicitud canonica,
  sujetos observados, revisiones, fingerprints y actor/contexto. No reserva ni
  bloquea datos.
- El guardado vuelve a autorizar y evaluar dentro de la transaccion. Si cambio
  cualquier precondicion, responde conflicto y no escribe nada; nunca aplica
  la solicitud sobre el estado nuevo por conveniencia.
- Las mutaciones aceptan una clave de idempotencia acotada por actor, proyecto
  y tipo de operacion. Repetir la misma clave y payload devuelve el mismo
  resultado; reutilizarla con otro payload es conflicto.
- Los codigos semanticos nuevos son `TS_LINK_CONFLICT`,
  `TS_LINK_PRECONDITION_CHANGED`, `TS_LINK_CONFIRMATION_REQUIRED` y
  `TS_LINK_BATCH_REJECTED`. El contrato HTTP y el formato final pertenecen a
  "Contrato de consulta y API del catalogo global".

La implementacion usa las primitivas transaccionales de cada motor y la
restriccion unica como ultima defensa. Los niveles de aislamiento, locks e
indices concretos pertenecen a "Rendimiento, indices e integridad
transaccional".

### Operaciones masivas

Una operacion masiva tiene dos fases:

1. **Prevalidar** todas las filas, devolver decisiones y errores ordenados,
   comparaciones de reemplazo y un token que representa el conjunto completo.
2. **Confirmar** exactamente ese conjunto con token, revisiones esperadas,
   motivo y clave de idempotencia.

El guardado es atomico y all-or-nothing. Si falla permiso, compatibilidad,
confirmacion, cardinalidad, staleness o concurrencia en una fila, no se cambia
ninguna. No existe modo parcial en esta entrega. La transaccion crea un
`batch_id`, las filas nuevas, transiciones anteriores, validaciones, eventos e
incrementos de variante juntos. Una respuesta fallida conserva los errores
por fila pero no deja eventos de exito ni revisiones parcialmente incrementadas.

### Materializacion de una corrida

Materializar y crear la corrida es una unidad de trabajo autoritativa:

1. Recarga la variante y sus bindings activos bajo una vista transaccional
   consistente y verifica el token/revision esperado.
2. Repite autorizacion, compatibilidad, estados derivados, completitud,
   topologia/parametros y cobertura/alineacion del rango. Un binding
   `valid_pinned` es valido; `unvalidated`, `stale` o `invalid` bloquean.
3. Lee valores exclusivamente de cada `set_revision_id` fijado y verifica de
   nuevo `bound_content_hash`. Nunca resuelve por `current_revision_id` en
   este paso.
4. Mapea roles a los campos del payload Julia y materializa el
   `system_case_json` autocontenido.
5. Crea, o reutiliza solo por igualdad byte-a-byte del payload canonico y del
   fingerprint completo de linaje, un `scenario_version` inmutable.
6. Crea el `run` que apunta a ese snapshot en la misma unidad de trabajo. La
   ejecucion Julia comienza despues del commit y lee solo el snapshot.

`scenario_versions.generation_metadata_json` conserva, como minimo:

- variante y `bindings_revision`;
- rango solicitado;
- IDs y hashes de topologia y parametros;
- por entrada: `binding_id`, objeto, rol, senal, set, revision y
  `content_hash`;
- regla/version/fingerprint de compatibilidad y validacion usada;
- modo `current` o `pinned`, revision vigente observada y motivo de la
  fijacion cuando corresponda;
- actor y request que materializaron.

El snapshot sigue siendo el unico contrato ejecutable e inmutable de la
corrida. Una revision, asociacion, binding o regla que cambie despues del
commit puede bloquear corridas futuras, pero nunca altera una corrida o
`scenario_version` ya materializado. Una carrera detectada antes del commit
aborta toda la unidad de trabajo; una revision publicada despues del commit no
invalida retroactivamente el snapshot que ya capturo el estado anterior.

### Consecuencias y traspasos

La recomendacion permite conservar intencionalmente una revision antigua sin
perder el fail-closed: la fijacion es explicita, revalidada, motivada y vuelve
a caducar ante el siguiente cambio. A cambio, el modelo necesita ledgers y
tokens de concurrencia en vez de un `upsert` destructivo como el actual.

No aparecieron decisiones nuevas fuera del mapa. Alcance y autorizacion exacta
pasan a "Alcance global, permisos y promocion entre proyectos"; transporte,
ETags y payloads pasan a "Contrato de consulta y API del catalogo global";
migracion de los upserts y `ON DELETE CASCADE` actuales pasa a "Migracion y
coexistencia con el modelo actual"; y locks, indices y triggers por motor pasan
a "Rendimiento, indices e integridad transaccional".
