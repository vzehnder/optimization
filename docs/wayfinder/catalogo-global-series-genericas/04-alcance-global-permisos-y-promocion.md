---
id: 04
title: "Alcance global, permisos y promocion entre proyectos"
map: catalogo-global-series-genericas
label: wayfinder:grilling
status: closed
assignee: codex
blocked_by: [01]
---

## Question

¿Como funcionan propiedad, visibilidad, vinculacion y revocacion para series de
alcance `project` y `global`?

Debe resolver las operaciones exactas de `analyst` y `admin`, la promocion y
posible despromocion global, el tratamiento de bindings existentes al perder
acceso, la ausencia de visibilidad para `client`, la prevencion de fugas entre
proyectos y los eventos de auditoria requeridos. Debe encajar con el gate de
autenticacion y la matriz de permisos que ya usa la aplicacion.

## Resolucion

Resuelto el 2026-08-30 con la autorizacion del usuario de adoptar la
recomendacion propuesta para todas las decisiones y preguntas de este ticket.

### Decision

El alcance de una serie controla **donde puede usarse**, no cambia su identidad
ni su propietario:

- Todo set conserva para siempre su `owner_project_id`, incluso cuando su
  `visibility_scope` es `global`.
- Promover cambia la misma fila de `project` a `global`; no copia el set, no
  crea nuevas senales y no transfiere revisiones, asociaciones ni historia.
- Un set `project` solo puede asociarse y vincularse a objetos, variantes y
  slots del proyecto propietario.
- Un set `global` puede asociarse y vincularse a objetos de cualquier proyecto,
  siempre que el objeto y la variante de destino pertenezcan al mismo proyecto.
- `global` no significa que la senal sea funcionalmente global. Una senal de
  precio, por ejemplo, sigue vinculandose al `global:system` real del proyecto
  de destino decidido en "Contrato de compatibilidad entre tipos de serie y
  objetos".
- Promocion, despromocion y toda mutacion de un set global son administrativas.
  El uso ordinario de una serie global sigue disponible para `analyst`.

El catalogo es global como superficie interna de descubrimiento: `admin` y
`analyst` ven metadata de las series `project` y `global` de todos los
proyectos, con propietario y alcance explicitos. En esta primera entrega,
`project` no es una frontera de confidencialidad entre usuarios internos; es
una frontera de reutilizacion. Esto conserva la matriz aceptada por TS-5, donde
ambos roles internos acceden a todos los proyectos, y evita inventar una tabla
de membresias que la aplicacion no tiene.

El rol legacy `client` ya no existe en runtime. Fue migrado a `external`, con
capacidades `portal_view` y `operate` por proyecto. Ninguna de esas capacidades
concede acceso al catalogo, a valores, asociaciones, bindings ni descriptores de
compatibilidad. En este documento, cualquier requisito historico referido a
`client` se aplica a `external`.

### Matriz de permisos

La autorizacion efectiva es la interseccion de rol, accion, estado del set,
alcance de la fuente y proyecto de destino:

| Accion | `analyst` | `admin` | `external` |
| --- | --- | --- | --- |
| Descubrir metadata `project` y `global` | todos los proyectos | todos los proyectos | nunca |
| Leer revision, valores y fuente de entrada | todos los proyectos | todos los proyectos | nunca |
| Crear set `project`, cargar o sellar revision | si | si | nunca |
| Editar metadata o archivar set `project` | si | si | nunca |
| Editar metadata, publicar revision o archivar set `global` | no | si | nunca |
| Promover `project -> global` | no | si | nunca |
| Despromover `global -> project` | no | si | nunca |
| Crear, reemplazar, retirar o revalidar asociaciones/bindings | si, dentro de las reglas de alcance | si, dentro de las reglas de alcance | nunca |
| Administrar tipos, roles y reglas de compatibilidad | no | si | nunca |
| Borrar historia de sets, revisiones, asociaciones o bindings | nunca | nunca por API publica | nunca |

Un `analyst` que necesite modificar una serie global debe derivar una copia
nueva de alcance `project`, con linaje a la revision de origen. Esa copia tiene
nueva identidad y no cambia consumidores existentes. Solo un `admin` puede
publicar una nueva revision sobre la identidad global compartida.

La aplicacion conserva su gate compartido actual:

- `require_internal` protege toda la superficie de catalogo y admite solo
  `admin` y `analyst` activos.
- `require_admin` protege tipos, reglas, promocion, despromocion y mutaciones de
  sets globales.
- `external` se rechaza antes de resolver IDs o ejecutar consultas del
  catalogo. Sus capacidades `portal_view` y `operate` no se consultan como
  alternativa a `require_internal`.
- Un usuario `external` puede consumir un resultado curado o ejecutar una
  consola configurada por sus contratos existentes, pero nunca recibe la
  fuente, valores, nombres, IDs, conteos, filtros ni bindings internos usados
  para producir ese resultado.

Si en el futuro se incorporan membresias internas por proyecto, se agregan
como otro predicado del autorizador comun; no se cambia la semantica de
`visibility_scope` ni se concede grandfathering a validaciones anteriores.

### Invariantes de proyecto y alcance

Cada operacion de asociacion, binding, prevalidacion, revalidacion y
materializacion comprueba en backend, dentro de su transaccion:

```text
target_project_id = linkable_object.project_id
target_project_id = case_input_variant.project_id        # para bindings

source_scope = project  => source.owner_project_id = target_project_id
source_scope = global   => cualquier target_project_id interno
```

El `project_id` del objeto padre debe coincidir con el proyecto de su subtipo.
No se confia en IDs enviados por la UI, pares textuales de entidad, asociaciones
anteriores ni resultados de una prevalidacion. Una asociacion valida tampoco
concede permiso permanente para crear un binding: el guardado vuelve a
autorizar fuente, objeto, variante y actor.

Estas reglas producen las siguientes consecuencias:

- Una serie `project` puede aparecer en la busqueda interna global, pero queda
  deshabilitada como candidata de un objeto de otro proyecto y el backend la
  rechaza con `TS_COMPAT_SCOPE_NOT_ACCESSIBLE`.
- Si objeto y variante pertenecen a proyectos distintos, se rechaza con
  `TS_COMPAT_PROJECT_CONTEXT_MISMATCH`, aunque la fuente sea global.
- Una serie global no cambia el propietario del objeto ni crea una asociacion
  implicita para cada proyecto.
- Una operacion masiva valida todas las filas con estas mismas reglas y guarda
  todo o nada.
- Consultar por ID, descargar una fuente o leer valores usa el mismo gate que
  la lista. No hay una ruta de detalle que omita la autorizacion de la
  superficie.
- Los read models, exportaciones y caches se segmentan por contexto de
  autorizacion y alcance; ningun cache compartido puede convertir una respuesta
  interna en una respuesta externa.

La comprobacion autoritativa se concentra en una politica de dominio unica,
conceptualmente:

```text
authorize_time_series_action(
  actor,
  action,
  source_set = optional,
  target_project_id = optional,
  linkable_object = optional,
  variant = optional
) -> allowed | stable_reason_code
```

La invocan lista, detalle, candidatos, prevalidacion, mutaciones,
materializacion de snapshots y lanzamiento de corridas. La UI solo representa
el resultado; no posee otra matriz de permisos.

### Promocion a alcance global

La promocion es una publicacion administrativa y explicita, nunca una
consecuencia automatica de que una serie se use en varios lugares.

Antes de confirmar, el backend devuelve una vista de impacto que incluye set,
propietario, revision/hash vigente, asociaciones y bindings activos afectados.
La promocion exige:

1. actor `admin` activo y CSRF valido;
2. set activo de alcance `project` con revision vigente sellada;
3. senales, tipos y unidades vigentes, sin revision `building` que se intente
   publicar como actual;
4. `expected_scope_revision`, revision/hash vigente observados y token de
   prevalidacion aun validos;
5. confirmacion, `reason_code`, motivo textual no vacio e idempotency key.

En una sola transaccion se bloquea la fila, se repiten las precondiciones, se
cambia `visibility_scope` a `global`, se incrementa `scope_revision` y se
inserta el evento de auditoria. `id`, `owner_project_id`, `current_revision_id`,
senales y revisiones no cambian.

El alcance forma parte de `object_scope_fingerprint`. Por eso las asociaciones
activas y bindings existentes no se consideran automaticamente revalidados
despues de promover:

- las asociaciones quedan `active_stale` hasta revalidarse;
- los bindings quedan `stale` y bloquean una nueva materializacion;
- una revalidacion exitosa agrega evidencia bajo el alcance global;
- ninguna revision fijada, asociacion o binding se actualiza silenciosamente.

La promocion amplia candidatos futuros, no repara, copia ni crea asociaciones
en otros proyectos. Publicar despues una nueva revision vigente de un set
global es tambien una operacion `admin` y aplica las reglas de staleness ya
decididas.

### Despromocion y perdida de acceso

La despromocion vuelve el mismo set global a `project` bajo su
`owner_project_id`. Es una revocacion de reutilizacion entre proyectos, no una
transferencia ni una copia.

El backend siempre presenta y exige confirmar el impacto, separado en:

- asociaciones y bindings cuyo destino es el proyecto propietario;
- asociaciones y bindings cuyo destino pertenece a otro proyecto;
- variantes y futuras corridas que quedaran bloqueadas.

Un uso activo en otro proyecto no puede impedir indefinidamente que un
administrador revoque el alcance global. Confirmada con motivo obligatorio, la
despromocion se ejecuta atomicamente y tiene efecto desde el commit:

- asociaciones del proyecto propietario quedan `active_stale` y pueden
  revalidarse;
- bindings del proyecto propietario quedan `stale` y pueden revalidarse o
  reemplazarse;
- asociaciones de otros proyectos se derivan como `active_incompatible`, no
  aparecen como candidatas y no originan bindings nuevos;
- bindings activos de otros proyectos se derivan como `invalid` con
  `TS_COMPAT_SCOPE_NOT_ACCESSIBLE`; bloquean validacion, materializacion y
  nuevas corridas hasta reemplazarse o retirarse;
- no se archiva, elimina, retargetea ni copia automaticamente ninguna fila.

La historia sigue siendo legible para usuarios internos autorizados. Un
`scenario_version` y una corrida ya materializados conservan su snapshot y no
se reescriben ni invalidan retroactivamente. Una operacion que aun no alcanzo
el commit de materializacion vuelve a autorizar y falla si la despromocion ya
ocurrio.

El mismo principio fail-closed se aplica al archivar un set, desactivar un
usuario interno o retirar en el futuro una membresia de proyecto: el permiso se
evalua en cada solicitud y corrida; una validacion anterior nunca funciona
como concesion permanente. Revocar `portal_view` u `operate` a un usuario
`external` no requiere tocar series ni bindings porque ese usuario nunca tuvo
acceso directo a ellos.

### Persistencia y concurrencia conceptual

Se agrega una revision monotona del alcance y un ledger append-only:

```sql
ALTER TABLE time_series_sets
    ADD COLUMN scope_revision INTEGER NOT NULL DEFAULT 0;

CREATE TABLE time_series_scope_events (
    id                       BIGINT PRIMARY KEY,
    time_series_set_id       BIGINT NOT NULL
        REFERENCES time_series_sets(id),
    event_type               TEXT NOT NULL CHECK (event_type IN (
                                 'created_project',
                                 'promoted_global',
                                 'demoted_project')),
    from_scope               TEXT NULL CHECK (
                                 from_scope IS NULL OR
                                 from_scope IN ('project', 'global')),
    to_scope                 TEXT NOT NULL CHECK (
                                 to_scope IN ('project', 'global')),
    scope_revision           INTEGER NOT NULL,
    owner_project_id         BIGINT NOT NULL REFERENCES projects(id),
    observed_set_revision_id BIGINT NULL
        REFERENCES time_series_set_revisions(id),
    observed_content_hash    TEXT NULL,
    actor_user_id            BIGINT NOT NULL REFERENCES users(id),
    actor_identity_snapshot  TEXT NOT NULL,
    actor_role_snapshot      TEXT NOT NULL,
    reason_code              TEXT NOT NULL,
    reason_text              TEXT NOT NULL,
    impact_json              JSON NOT NULL DEFAULT '{}',
    request_id               TEXT NOT NULL,
    idempotency_key          TEXT NOT NULL,
    occurred_at              TIMESTAMP NOT NULL,
    UNIQUE (time_series_set_id, scope_revision),
    UNIQUE (actor_user_id, idempotency_key)
);
```

`impact_json` es evidencia resumida y estable: IDs y conteos de asociaciones,
bindings, proyectos y variantes observados al confirmar. No es fuente de
autorizacion ni sustituye las FK. La implementacion puede normalizar esta
evidencia si el volumen lo exige; la semantica no cambia.

Promocion y despromocion aceptan `expected_scope_revision` y la revision/hash
vigente observados. Una carrera responde conflicto sin escribir el cambio ni
su evento. Repetir la misma idempotency key y payload devuelve el mismo
resultado; reutilizarla con otro payload es conflicto.

Los eventos minimos son `created_project`, `promoted_global` y
`demoted_project`. Creacion/publicacion de revisiones, archivado de sets y las
mutaciones de asociaciones/bindings conservan sus propios eventos de dominio.
Los intentos fallidos de autenticacion, autorizacion, CSRF, precondicion o
alcance se registran en el log operativo/seguridad con el mismo `request_id`,
pero no insertan un evento que parezca una mutacion exitosa. El ledger impide
`UPDATE` y `DELETE`; los triggers concretos corresponden al ticket de
rendimiento e integridad.

### Codigos y respuestas de dominio

Se reutilizan los codigos ya decididos por compatibilidad:

- `TS_COMPAT_SCOPE_NOT_ACCESSIBLE` para fuente fuera del alcance utilizable;
- `TS_COMPAT_PROJECT_CONTEXT_MISMATCH` para objeto, variante o slot en
  proyectos incoherentes;
- `TS_COMPAT_CONTRACT_CHANGED` cuando cambio el fingerprint entre
  prevalidacion y guardado.

Las mutaciones de alcance agregan descriptores semanticos que el contrato HTTP
terminara de mapear:

- `TS_SCOPE_ADMIN_REQUIRED`;
- `TS_SCOPE_CONFIRMATION_REQUIRED`;
- `TS_SCOPE_PRECONDITION_CHANGED`;
- `TS_SCOPE_ALREADY_EFFECTIVE` para el no-op idempotente;
- `TS_SCOPE_INVALID_STATE` para un set sin revision vigente sellada o no apto
  para publicacion.

No se revela la existencia de recursos del catalogo a `external`. La frontera
interna responde con el comportamiento forbidden comun antes de buscar el
recurso; las rutas externas no exponen estos codigos ni descriptores.

### Consecuencias y traspasos

La decision conserva el modelo de acceso ya desplegado y hace que
`visibility_scope` tenga un significado verificable: limita el proyecto de
destino sin fingir aislamiento entre los usuarios internos actuales. A cambio,
los sets globales tienen una politica de publicacion mas estricta y todo cambio
de alcance exige revalidar consumidores.

No aparecieron decisiones nuevas fuera del mapa. El transporte, filtros,
tokens de impacto y forma exacta de respuestas pasan a "Contrato de consulta y
API del catalogo global"; la incorporacion de `scope_revision`, ledger y
adaptacion del rol legacy pasan a "Migracion y coexistencia con el modelo
actual"; indices, locks y triggers append-only pasan a "Rendimiento, indices e
integridad transaccional"; y las pruebas de no fuga, promocion y despromocion
forman parte de "Corte de entrega y criterios de aceptacion".
