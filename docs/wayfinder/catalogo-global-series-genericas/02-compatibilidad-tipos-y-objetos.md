---
id: 02
title: "Contrato de compatibilidad entre tipos de serie y objetos"
map: catalogo-global-series-genericas
label: wayfinder:grilling
status: closed
assignee: codex
blocked_by: [01]
---

## Question

¿Como se declara y valida que un tipo semantico de serie puede cumplir un rol
concreto sobre un tipo de objeto?

Debe cerrar el contrato de compatibilidad: tipos canonicos y personalizados,
dimension/unidad canonica, tipos de objeto permitidos, roles de asociacion y de
ejecucion, reglas para señales globales, transformaciones multi-entrada y
mensajes estables para cada incompatibilidad. La UI debe poder derivar sus
opciones desde el mismo contrato que el backend aplica al guardar.

## Resolucion

Resuelto el 2026-08-30 con la autorizacion del usuario de adoptar la
recomendacion propuesta para todas las decisiones de este ticket.

### Decision

La compatibilidad es un **contrato persistente, positivo y fail-closed** entre
cuatro identidades independientes:

1. el tipo semantico de la senal;
2. el rol funcional que debe cumplir;
3. el tipo exacto del objeto vinculable;
4. el uso solicitado: asociacion de catalogo o binding ejecutable.

Una coincidencia de nombre, dimension o unidad nunca concede compatibilidad
por si sola. Debe existir una regla activa que autorice exactamente la tupla
`(semantic_type, role, object_type)` y el uso solicitado. La misma regla
alimenta las opciones de la UI y la validacion autoritativa del backend.

El rol se desacopla del tipo semantico. Por tanto,
`time_series_binding_roles.semantic_type_id`, propuesto en el ticket
"Modelo relacional canonico para series, tipos y objetos vinculables", se
retira del modelo consolidado y se reemplaza por la matriz explicita de este
ticket. La identidad de los roles no cambia.

### Contrato de dimensiones y unidades

Se normaliza la dimension fisica en un catalogo y se deja de usar texto libre
como fuente canonica:

```sql
CREATE TABLE measurement_dimensions (
    id                  BIGINT PRIMARY KEY,
    dimension_key       TEXT NOT NULL UNIQUE,
    display_name        TEXT NOT NULL,
    value_kind          TEXT NOT NULL DEFAULT 'numeric',
    status              TEXT NOT NULL CHECK (status IN ('active', 'archived'))
);

ALTER TABLE measurement_units
    ADD COLUMN dimension_id BIGINT NOT NULL
        REFERENCES measurement_dimensions(id);

ALTER TABLE measurement_units
    ADD CONSTRAINT measurement_units_id_dimension_unique
        UNIQUE (id, dimension_id);

ALTER TABLE time_series_semantic_types
    ADD COLUMN dimension_id BIGINT NOT NULL
        REFERENCES measurement_dimensions(id);

ALTER TABLE time_series_semantic_types
    ADD CONSTRAINT semantic_type_canonical_unit_dimension_fk
        FOREIGN KEY (canonical_unit_id, dimension_id)
        REFERENCES measurement_units(id, dimension_id);
```

`measurement_units.physical_dimension` queda como columna transitoria de
compatibilidad y luego se depreca. Cada tipo semantico tiene una sola dimension
y una sola unidad canonica. Una senal sellada debe usar exactamente esa unidad.

No hay conversion implicita al asociar o vincular. Una fuente con otra unidad
debe convertirse durante la importacion o mediante una transformacion
versionada y auditable; su salida queda materializada en una revision sellada
con la unidad canonica. Esto evita que escala, offset o convenciones de signo
cambien silenciosamente al ejecutar un caso.

### Tipos de objeto normalizados

La compatibilidad necesita distinguir `component:load` de
`component:renewable`, aunque ambos vivan bajo `object_kind = 'component'`.
Se agrega un catalogo cerrado y protegido:

```sql
CREATE TABLE linkable_object_types (
    id                  BIGINT PRIMARY KEY,
    object_type_key     TEXT NOT NULL UNIQUE,
    object_kind         TEXT NOT NULL,
    display_name        TEXT NOT NULL,
    is_system           BOOLEAN NOT NULL DEFAULT TRUE,
    status              TEXT NOT NULL CHECK (status IN ('active', 'archived'))
);

ALTER TABLE linkable_objects
    ADD COLUMN object_type_id BIGINT NOT NULL
        REFERENCES linkable_object_types(id);
```

El backend deriva y verifica el tipo desde la FK tipada del objeto real; el
cliente no puede declararlo. La primera entrega registra:

- `global:system`;
- `component:grid`, `component:load`, `component:renewable`,
  `component:battery` y `component:hydro`;
- `hydraulic_system`, `hydraulic_node`, `hydraulic_reach`,
  `hydraulic_plant` y `hydraulic_unit`.

`component:bus` no se registra como vinculable en esta entrega. Agregar otro
tipo de objeto requiere migracion y codigo de integridad; no basta insertar una
clave textual.

### Roles compartidos por asociacion y ejecucion

`time_series_binding_roles` pasa a describir una necesidad funcional del
dominio, no un tipo de serie. Un mismo rol se usa tanto para indicar que una
senal es candidata para un objeto en el catalogo como para seleccionar la
senal efectiva de una variante.

Se agregan al rol su contrato de medida y los usos permitidos:

```sql
ALTER TABLE time_series_binding_roles
    DROP COLUMN semantic_type_id;

ALTER TABLE time_series_binding_roles
    ADD COLUMN dimension_id BIGINT NOT NULL
        REFERENCES measurement_dimensions(id),
    ADD COLUMN canonical_unit_id BIGINT NOT NULL,
    ADD COLUMN association_allowed BOOLEAN NOT NULL DEFAULT TRUE,
    ADD COLUMN execution_allowed BOOLEAN NOT NULL DEFAULT TRUE,
    ADD COLUMN execution_contract_key TEXT NULL,
    ADD CONSTRAINT binding_role_unit_dimension_fk
        FOREIGN KEY (canonical_unit_id, dimension_id)
        REFERENCES measurement_units(id, dimension_id);
```

Los roles ejecutables son `is_system = TRUE` y se entregan por migracion junto
con el adaptador que construye el payload Julia. Un administrador puede crear
y administrar tipos semanticos y autorizar un tipo personalizado para un rol
existente, pero no inventar desde la UI un rol ejecutable que Julia no conoce.
Agregar un nuevo rol ejecutable requiere una entrega de producto.

La asociacion de catalogo incorpora el rol. Pasa a ser unica por
`signal_id + linkable_object_id + binding_role_id`; una misma senal puede ser
candidata a mas de un rol de un objeto. La asociacion sigue sin seleccionar
una variante ni una revision ejecutable.

Un binding puede nacer directamente sin una asociacion previa. Si conserva
`catalog_association_id` como procedencia, la asociacion debe estar activa y
coincidir exactamente en senal, objeto y rol. En ambos caminos se aplica el
mismo evaluador de compatibilidad.

### Matriz positiva de compatibilidad

```sql
CREATE TABLE time_series_role_compatibilities (
    id                  BIGINT PRIMARY KEY,
    semantic_type_id    BIGINT NOT NULL
                        REFERENCES time_series_semantic_types(id),
    binding_role_id     BIGINT NOT NULL
                        REFERENCES time_series_binding_roles(id),
    object_type_id      BIGINT NOT NULL
                        REFERENCES linkable_object_types(id),
    association_allowed BOOLEAN NOT NULL DEFAULT TRUE,
    execution_allowed   BOOLEAN NOT NULL DEFAULT FALSE,
    rule_version        INTEGER NOT NULL DEFAULT 1 CHECK (rule_version > 0),
    status              TEXT NOT NULL CHECK (status IN ('active', 'archived')),
    supersedes_rule_id  BIGINT NULL
                        REFERENCES time_series_role_compatibilities(id),
    created_at          TIMESTAMP NOT NULL,
    created_by          TEXT NOT NULL,
    archived_at         TIMESTAMP NULL,
    archived_by         TEXT NULL
);

CREATE UNIQUE INDEX one_active_compatibility_rule
    ON time_series_role_compatibilities(
        semantic_type_id, binding_role_id, object_type_id
    )
    WHERE status = 'active';
```

Al crear una regla, la dimension y unidad canonica del tipo deben coincidir
exactamente con las del rol. La regla no puede ampliar los usos que el propio
rol prohibe. Las reglas se reemplazan por nuevas filas y se archivan; no se
reescriben en sitio cuando ya fueron usadas.

Las asociaciones y bindings registran el `compatibility_rule_id` con que se
validaron. Es una referencia de auditoria, no una excepcion permanente: si la
regla se archiva o cambia el contrato, la validez vigente se vuelve a calcular
y el elemento queda incompatible o stale. El detalle del ciclo de vida queda
para "Ciclo de vida de asociaciones y bindings versionados".

### Matriz inicial

Las claves antiguas se migran a tipos semanticos sin codificar la unidad en la
identidad nueva. La matriz inicial es:

| Tipo semantico | Rol | Tipo de objeto | Unidad | Asociar | Ejecutar |
| --- | --- | --- | --- | --- | --- |
| `energy_price` | `grid_import_price` | `global:system` | `USD/MWh` | si | si |
| `energy_price` | `grid_export_price` | `global:system` | `USD/MWh` | si | si |
| `grid_import_price` | `grid_import_price` | `global:system` | `USD/MWh` | si | si |
| `grid_export_price` | `grid_export_price` | `global:system` | `USD/MWh` | si | si |
| `load_demand` | `load_demand` | `component:load` | `MW` | si | si |
| `renewable_available_power` | `renewable_available_power` | `component:renewable` | `MW` | si | si |
| `hydro_inflow` | `hydro_inflow` | `component:hydro` | `m3/s` | si | si |
| `natural_inflow` | `natural_inflow` | `hydraulic_node` | `m3/s` | si | si |
| `minimum_flow` | `minimum_flow` | `hydraulic_reach` | `m3/s` | si | si |

`price_usd_per_mwh` migra a `energy_price` y puede llenar ambos roles de
precio con dos bindings que apunten a la misma senal. Las claves direccionales
solo llenan su rol correspondiente. Esto reemplaza la familia debil de tres
strings de `app/required_signals.py` por roles explicitos y conserva la
compatibilidad del precio simetrico legacy.

Que un objeto sea vinculable no implica que ya tenga una regla. Por ejemplo,
`component:battery`, `hydraulic_plant` y `hydraulic_unit` quedan registrados,
pero no aceptan ninguna de las ocho senales iniciales. Se habilitaran solo al
agregar un tipo y una regla completos.

### Senales globales

Toda senal global se asocia y vincula al objeto real `global:system` del
proyecto. No se permite `NULL`, el proyecto como objeto implicito ni un ID
ficticio. La regla debe nombrar expresamente `global:system`; ser visible en el
catalogo global no convierte una senal en una senal funcionalmente global.

Los bindings legacy de precio sin entidad o ligados a `grid` se admiten solo a
traves del adaptador de migracion. Todo vinculo nuevo usa `global:system`.

### Tipos canonicos y personalizados

- Un tipo canonico (`is_system = TRUE`) tiene clave, dimension, unidad,
  `value_kind` y reglas de valores protegidos. Solo se pueden editar nombre y
  descripcion; se archiva un tipo sin uso o se entrega una nueva version del
  contrato.
- Un tipo personalizado requiere clave, descripcion, dimension, unidad
  canonica, agregacion, `value_kind` y reglas de valores completas. Solo un
  administrador puede crearlo o archivarlo.
- Crear el tipo no lo habilita para ningun objeto o rol. Cada compatibilidad se
  aprueba con una regla separada y auditada.
- Un tipo personalizado puede cumplir un rol ejecutable existente si su
  dimension y unidad coinciden y el administrador habilita expresamente
  `execution_allowed`. El rol, no el nombre del tipo, determina el campo del
  payload Julia.
- No se permiten formulas ni codigo en un tipo o regla. Cualquier conversion o
  derivacion vive en el registro allowlisted de transformaciones.

La revision se sella solo si cada senal cumple el contrato vigente de su tipo,
incluyendo unidad y reglas de valores. Asociar o vincular no vuelve a recorrer
todos los valores: exige una revision sellada y valida su clasificacion,
unidad, estado y huella de contrato.

### Transformaciones multi-entrada

No existe un binding ejecutable que calcule sobre varias senales en vivo. Una
transformacion multi-entrada debe estar declarada en el registro allowlisted,
con puertos de entrada nombrados, cardinalidad, tipos semanticos, dimensiones y
unidades admitidas, regla de alineacion temporal y tipo/unidad de salida.

La ejecucion materializa un set/revision derivado, sellado y con linaje hacia
cada revision de entrada, los parametros y la version de implementacion. Solo
la senal de salida se asocia o vincula mediante la matriz ordinaria. De este
modo el optimizador sigue viendo un binding por variante, objeto y rol.

`combine_signals` existente solo combina senales distintas sobre una grilla
comun; no convierte por si mismo varias entradas en una nueva senal apta para
un rol. Si se necesita suma, promedio, conversion o derivacion, debe existir
otra definicion allowlisted con contrato de salida explicito.

### Evaluador unico y orden de validacion

El backend expone un unico servicio de dominio conceptual:

```text
evaluate_compatibility(
  signal_id,
  revision_id,
  linkable_object_id,
  binding_role_id,
  usage = association | execution,
  actor_context
) -> CompatibilityDecision
```

El mismo evaluador se usa al consultar candidatos, prevalidar una operacion
individual o masiva, guardar asociaciones, guardar bindings, validar una
variante y lanzar una corrida. La UI consume sus descriptores y resultados;
no mantiene otra matriz ni replica reglas en TypeScript.

La validacion se ejecuta en este orden determinista:

1. existencia, estado activo y revision sellada de senal, tipo, rol y objeto;
2. proposito de la senal (`input` para asociar o ejecutar en este catalogo);
3. permiso del rol para el uso solicitado;
4. existencia de la regla positiva para tipo, rol y tipo exacto de objeto;
5. igualdad de dimension y unidad entre senal, tipo y rol;
6. alcance, proyecto y autorizacion del actor;
7. coincidencia de la asociacion de procedencia, si fue indicada;
8. restricciones de cardinalidad y completitud de la variante.

La semantica detallada de alcance y permisos se toma de "Alcance global,
permisos y promocion entre proyectos". La cardinalidad, reemplazo, staleness e
historia se toman de "Ciclo de vida de asociaciones y bindings versionados".

La prevalidacion devuelve todos los errores ordenados y el primero es el error
primario. El guardado vuelve a evaluar dentro de la transaccion y compara la
huella/version del contrato para evitar una carrera entre previsualizacion y
persistencia. Una operacion masiva es atomica: si una fila falla, ninguna se
guarda.

### Codigos estables de incompatibilidad

Los textos visibles son localizables y pueden mejorar; el contrato estable es
el codigo mas contexto estructurado. Toda violacion tiene la forma:

```json
{
  "code": "TS_COMPAT_OBJECT_TYPE_NOT_ALLOWED",
  "message_key": "timeseries.compatibility.object_type_not_allowed",
  "message": "La serie no admite este tipo de objeto para el rol seleccionado.",
  "field": "linkable_object_id",
  "context": {
    "semantic_type_key": "load_demand",
    "role_key": "load_demand",
    "object_type_key": "component:battery",
    "usage": "execution"
  }
}
```

Catalogo inicial de codigos:

| Codigo | Condicion |
| --- | --- |
| `TS_COMPAT_SIGNAL_UNAVAILABLE` | Senal ausente, archivada, sin revision aplicable o revision no sellada. |
| `TS_COMPAT_SEMANTIC_TYPE_INACTIVE` | Tipo semantico archivado o no disponible. |
| `TS_COMPAT_ROLE_INACTIVE` | Rol archivado o no disponible. |
| `TS_COMPAT_OBJECT_UNAVAILABLE` | Objeto ausente, archivado o no vinculable. |
| `TS_COMPAT_SIGNAL_PURPOSE_NOT_INPUT` | La senal es output/metadata y no una entrada reutilizable. |
| `TS_COMPAT_ROLE_USAGE_NOT_ALLOWED` | El rol no admite asociacion o ejecucion, segun el uso solicitado. |
| `TS_COMPAT_SEMANTIC_TYPE_NOT_ALLOWED` | El tipo no tiene regla para el rol. |
| `TS_COMPAT_OBJECT_TYPE_NOT_ALLOWED` | El tipo y rol existen, pero no para el tipo exacto de objeto. |
| `TS_COMPAT_DIMENSION_MISMATCH` | Las dimensiones de senal, tipo y rol no coinciden. |
| `TS_COMPAT_UNIT_MISMATCH` | La unidad no es exactamente la canonica del tipo y rol. |
| `TS_COMPAT_SCOPE_NOT_ACCESSIBLE` | La serie no es visible o utilizable por el actor en el contexto solicitado. |
| `TS_COMPAT_PROJECT_CONTEXT_MISMATCH` | Objeto, caso o slot global no pertenece al contexto de proyecto valido. |
| `TS_COMPAT_ASSOCIATION_MISMATCH` | La asociacion indicada no coincide en senal, objeto y rol o esta archivada. |
| `TS_COMPAT_CONTRACT_CHANGED` | La regla o huella usada en la prevalidacion/binding ya no es vigente. |
| `TS_COMPAT_TRANSFORMATION_REQUIRED` | La entrada necesita una conversion o derivacion explicita antes de vincularse. |
| `TS_COMPAT_TRANSFORM_PORT_MISSING` | Falta una entrada requerida de una transformacion declarada. |
| `TS_COMPAT_TRANSFORM_PORT_CARDINALITY` | Un puerto recibe menos o mas entradas que las permitidas. |
| `TS_COMPAT_TRANSFORM_INPUT_NOT_ALLOWED` | Una entrada no cumple el contrato de su puerto. |
| `TS_COMPAT_TRANSFORM_HORIZON_MISMATCH` | Las entradas no cumplen la alineacion temporal declarada. |
| `TS_COMPAT_TRANSFORM_OUTPUT_NOT_BINDABLE` | La salida materializada no cumple el rol de destino. |

La ausencia de regla nunca se degrada a advertencia. La UI muestra la misma
razon para deshabilitar una opcion que el backend devolveria al intentar
guardarla; el backend sigue siendo autoritativo.

### Consecuencias y traspasos

El contrato permite que tipos personalizados satisfagan necesidades existentes
sin acoplar el optimizador a nombres creados por usuarios, y evita que dos
senales con la misma unidad se vuelvan intercambiables accidentalmente. El
costo es administrar catalogos y reglas versionadas, asumido para obtener
auditoria y comportamiento fail-closed.

No aparecen preguntas nuevas fuera de los tickets ya trazados. El ciclo de
vida de una regla archivada pasa a "Ciclo de vida de asociaciones y bindings
versionados"; permisos y alcance pasan a "Alcance global, permisos y promocion
entre proyectos"; el read model y transporte de estos descriptores pasan a
"Contrato de consulta y API del catalogo global"; y la migracion de la familia
de strings actual pasa a "Migracion y coexistencia con el modelo actual".
