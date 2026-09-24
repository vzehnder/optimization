# REG-008: Reutilizar una regla parametrizada en varios componentes

Status: Done
Type: AFK
Triage: ready-for-agent
Source: [Plan](../plan.md), secciones 4 y 5.
User stories covered: HU-08.

## What to build

Un analista convierte una definición en plantilla reutilizable dentro del
proyecto y la aplica a varios componentes compatibles. El código y contrato de
puertos se comparten por revisión; cada instancia conserva sus propios parámetros,
alias, entradas, variante y activación. La biblioteca ofrece ejemplos editables
de las capacidades ya implementadas, no una segunda representación del modelo.

## Acceptance criteria

- [x] La biblioteca del proyecto permite descubrir una regla por nombre, revisión, capacidades requeridas y tipos compatibles, sin exponer contenido a externos.
- [x] Aplicar a otro componente crea una instancia independiente de la misma revisión; no copia referencias al componente original silenciosamente.
- [x] El formulario solicita los puertos/alias y parámetros tipados obligatorios; las opciones se filtran por capacidades del motor y contexto del nuevo objeto.
- [x] La previsualización muestra diferencias entre instancias y sus filas efectivas; cambiar un parámetro local no modifica código ni otras aplicaciones.
- [x] Varias instancias de la misma regla coexisten con identificadores de restricción únicos, lineage y activación independientes.
- [x] Publicar otra revisión conserva todas las asignaciones fijadas y marca las afectadas para resolución; no actualiza código ejecutado por todas las centrales de forma automática.
- [x] Copiar o clonar una variante conserva pins, exige remapear objetos inexistentes y deja constancia de origen; no hereda una validación válida si cambió el contexto.
- [x] Aplicaciones a tipos incompatibles, otro proyecto o alias faltantes se rechazan también por API.

## Demonstration and validation

Aplicar la misma regla de caudal a dos unidades con capacidades distintas.
Modificar parámetros de una y comprobar resultados independientes. Publicar
una revisión nueva y comprobar pins/obsolescencia. Verificar el flujo de biblioteca,
concurrencia al aplicar y la ausencia de colisiones en la IR y en JuMP.

## Blocked by

- [REG-004](REG-004-relacionar-componentes-hidraulicos.md).

## Fronteras TDD acordadas (2026-09-24)

El usuario confirmó API HTTP sobre SQLite/PostgreSQL y runtime OCI real,
interfaz React/navegador y snapshot consumido por Julia. Las pruebas nuevas
observan esas fronteras sin sustituir el compilador propio por mocks.

Los ciclos cubren biblioteca y contrato tipado, valores locales con código
compartido, referencias obligatorias, coexistencia y obsolescencia, rechazo de
previews anteriores a una edición local, clonación con pins y remapeo explícito,
comparación de filas vigentes y el recorrido de creación desde ejemplos.

## Evidencia de entrega (2026-09-24)

Biblioteca local por proyecto, contratos sin referencias heredadas e instancias
que resuelven el código desde su publicación inmutable. El formulario separa
valores locales de tipos/unidades compartidos y filtra objetos y entradas. La
comparación muestra parámetros, activación, obsolescencia y filas vigentes.
Clonar variantes conserva pins y origen, exige nueva validación y permite elegir
destinos compatibles desde la interfaz, sin dejar copias parciales ante un rechazo.

- **24 pruebas HTTP nuevas aprobadas**, 12 SQLite y 12 PostgreSQL, sin omisiones,
  usando OCI real. Incluyen límites de proyecto/rol/tipo, contratos requeridos,
  valores independientes, edición local frente a previews anteriores, pins al
  publicar, filas sin colisiones, clones activos/pendientes, remapeo con rollback
  y reintentos concurrentes de creación/aplicación.
- **63 pruebas de regresión de reglas aprobadas** en SQLite/OCI (REG-001 a
  REG-007). La tanda enumera 84 y omite los 21 duplicados PostgreSQL al no activar
  esa base para la regresión. PostgreSQL se verificó por separado en los 12 casos
  nuevos anteriores. **34 pruebas de variantes y su API** también aprobadas.
- **81 pruebas React distintas aprobadas**: 23 de reglas y 58 de la aplicación,
  con biblioteca, contrato de puertos, comparación y clonación/remapeo. La primera
  tanda expuso una expectativa antigua del diagrama: agregar un objeto ya lo
  seleccionaba. Se movió la comprobación del estado vacío antes de agregarlo y
  se repitieron las 58 pruebas de la aplicación, todas aprobadas.
- **50 comprobaciones Julia** de reglas aprobadas; se mantienen las matemáticas
  y el SDK existentes.
- **Chromium con API, OCI y Julia reales** comprueba creación desde ejemplo,
  segunda revisión compartida y dos unidades con capacidades distintas. Resuelve
  17 m³/s (5 + 12) y, tras editar únicamente Sur, 13 m³/s (5 + 8). Comprueba ocho
  identificadores de filas únicos, comparación, obsolescencia por nueva publicación
  y snapshot histórico intacto. Captura de comparación revisada visualmente.
  La repetición final pasó en 4,0 minutos; también pasó REG-004 en Chromium.
  El primer comando conjunto encontró el bootstrap ya consumido por REG-004:
  REG-008 se repitió con su propio servidor/base, como se ejecuta en CI.
- Build, TypeScript, ESLint, `api:check`, `git diff --check` y Prettier de archivos modificados
  aprobados. `npm run check` completo encuentra formato preexistente en 17 archivos
  ajenos a la entrega, igual que REG-007; no se reformatearon.

[Operación y reproducción](../runtime.md) y el workflow incluyen REG-008.
El SDK continúa en `reg-006.1`, con imagen OCI fijada por digest. No se ejecutó
CI remoto ni se modificaron bases de proyectos reales.
La siguiente issue por orden es REG-009: comparar revisiones y resolver obsolescencia.
