# REG-007: Publicar una salida numérica como serie derivada

Status: Done
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

- [x] Solo se ofrecen salidas numéricas completas previas al solve; expresiones con variables de decisión no pueden publicarse como entradas.
- [x] La publicación conserva nombre, semántica, unidad, grilla y alcance/propiedad válidos; la elección de una serie específica respeta el dueño inmutable.
- [x] Se escribe un nuevo set/revisión mediante el escritor canónico en una transacción; los inputs quedan intactos y no hay set parcialmente visible ante fallo.
- [x] Lineage incluye revisión de regla, código/SDK/runtime, parámetros, inputs y sus revisiones/hash, contrato temporal y hash de la salida publicada.
- [x] Reintentar la misma solicitud no duplica sets/revisiones. Regenerar crea una revisión nueva y no modifica bindings ni snapshots históricos.
- [x] Una fuente o regla nueva marca la receta como obsoleta con explicación; regenerar y revalidar consumidores son acciones explícitas conforme a TS-7.
- [x] Se rechazan ciclos de recetas/dependencias; no se crean cadenas automáticas de ejecución ni se reutiliza un resultado de la misma corrida como entrada.
- [x] La serie aparece en la superficie correspondiente y puede vincularse a un rol realmente compatible; el catálogo no ejecuta Python para mostrarla.

## Demonstration and validation

Publicar una serie de potencia disponible calculada y usar su revisión en una
entrada compatible de un caso de prueba. Modificar una fuente, regenerar y
comprobar que una corrida anterior y el pin previo siguen intactos. Probar
atomicidad, idempotencia, propiedad y permisos en SQLite/PostgreSQL y el recorrido UI.

## Blocked by

- [REG-003](REG-003-limites-horarios-series.md).

## Implementación y evidencia (2026-09-23)

Se añadió el recorrido protegido de cuatro pasos para publicar una salida de
una prueba exitosa. API y persistencia conservan el escritor canónico, su
clasificación y propietarios; receta, lineage y recibo idempotente se confirman
en la misma transacción. Una regeneración conserva la identidad y crea una
revisión incluso con valores iguales. Las lecturas solo consultan datos y
vigencia, sin ejecutar el runtime.

- **25 pruebas nuevas HTTP aprobadas**, con OCI real: 13 SQLite y 12 PostgreSQL.
  Cubren salida completa, clasificación/unidad/rango, inputs intactos, identidad,
  idempotencia, fallo después de escribir valores con rollback completo, ciclos,
  propiedad específica, permisos, interruptor del proyecto, obsolescencia,
  regeneración y consumo con pin/snapshot histórico. La pausa operativa C6 se
  comprueba en SQLite; su duplicado PostgreSQL se omite porque ese fixture migra
  la base completa. La suite de REG-007 enumera 26 casos con esa única omisión.
- **172 pruebas distintas de reglas/catálogo aprobadas**, incluidas las anteriores.
  La tanda de 171 pasó 168 y encontró tres colisiones al ejecutar dos suites sobre
  la misma base. Se repitió REG-007 PostgreSQL completo sobre una base exclusiva:
  12 aprobadas y la omisión C6 indicada. Se añadió y verificó la prueba SQLite C6
  tras la tanda amplia. La regresión anual calculó 8784 períodos en 4,502 s.
- **73 pruebas adicionales del escritor canónico y materialización aprobadas**;
  tres fixtures existentes se omiten en PostgreSQL por requerir corrupción/fallo
  SQLite. Las dos expectativas de catálogo vacío que encontraron datos de otra
  suite pasaron al ejecutar series específicas sobre una base PostgreSQL vacía.
- **77 pruebas React distintas aprobadas**. La tanda completa pasó 76 y expuso
  un timeout de espera en la nueva prueba; se ajustó la espera de carga asíncrona
  y pasaron las dos pruebas de publicación/regeneración. Los mocks existentes de
  presupuestos incluyen las nuevas lecturas de series.
- **Chromium con API, OCI y Julia reales**, aprobado en 2,1 minutos: publicación
  `[20, 10, 15, 20]` MW, inspector del catálogo, binding renovable compatible y
  solve exitoso. Cambiar disponibilidad y regenerar produce `[10, 10, 10, 10]`,
  mantiene el pin anterior obsoleto, bloquea otra corrida sin revalidación y
  conserva íntegro el snapshot histórico. Captura revisada visualmente.
- Build, TypeScript, ESLint, `api:check`, `git diff --check` y Prettier de archivos
  modificados aprobados. `npm run check` completo encuentra formato preexistente
  en 17 archivos ajenos a esta entrega; no se reformatearon.

[Operación y reproducción](../runtime.md) y el workflow incluyen REG-007.
El SDK sigue siendo `reg-006.1`; se reutilizó su imagen OCI fijada por digest.
No se ejecutó CI remoto ni se modificaron bases de proyectos reales.
La siguiente issue por orden es REG-008: reutilizar reglas.
