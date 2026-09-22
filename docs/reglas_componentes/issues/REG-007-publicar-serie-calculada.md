# REG-007: Publicar una salida numérica como serie derivada

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: [Plan](../plan.md), secciones 2, 6 y 7.
User stories covered: HU-03, HU-07.

## What to build

Tras probar una regla, el analista selecciona una salida numérica, declara
clasificación/unidad y la publica como serie derivada del catálogo o específica
del objeto. La publicación reutiliza el escritor y recorrido canónicos. Más
adelante puede regenerar una revisión explícitamente y seleccionar esa serie
en un caso compatible, sin ejecutar código al leer el catálogo.

## Acceptance criteria

- [ ] Solo se ofrecen salidas numéricas completas previas al solve; expresiones con variables de decisión no pueden publicarse como entradas.
- [ ] La publicación conserva nombre, semántica, unidad, grilla y alcance/propiedad válidos; la elección de una serie específica respeta el dueño inmutable.
- [ ] Se escribe un nuevo set/revisión mediante el escritor canónico en una transacción; los inputs quedan intactos y no hay set parcialmente visible ante fallo.
- [ ] Lineage incluye revisión de regla, código/SDK/runtime, parámetros, inputs y sus revisiones/hash, contrato temporal y hash de la salida publicada.
- [ ] Reintentar la misma solicitud no duplica sets/revisiones. Regenerar crea una revisión nueva y no modifica bindings ni snapshots históricos.
- [ ] Una fuente o regla nueva marca la receta como obsoleta con explicación; regenerar y revalidar consumidores son acciones explícitas conforme a TS-7.
- [ ] Se rechazan ciclos de recetas/dependencias; no se crean cadenas automáticas de ejecución ni se reutiliza un resultado de la misma corrida como entrada.
- [ ] La serie aparece en la superficie correspondiente y puede vincularse a un rol realmente compatible; el catálogo no ejecuta Python para mostrarla.

## Demonstration and validation

Publicar una serie de potencia disponible calculada y usar su revisión en una
entrada compatible de un caso de prueba. Modificar una fuente, regenerar y
comprobar que una corrida anterior y el pin previo siguen intactos. Probar
atomicidad, idempotencia, propiedad y permisos en SQLite/PostgreSQL y el recorrido UI.

## Blocked by

- [REG-003](REG-003-limites-horarios-series.md).
