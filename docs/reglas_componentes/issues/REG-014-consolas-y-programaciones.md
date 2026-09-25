# REG-014: Ejecutar reglas fijadas desde consolas y programaciones

Status: Done
Type: AFK
Triage: ready-for-agent
Source: [Plan](../plan.md), secciones 6, 8 y 9.
User stories covered: HU-09, HU-12.

## What to build

Habilitar los recorridos operativos que antes bloqueaban casos con reglas:
una consola configurada y una programación existente ejecutan revisiones
preparadas por el analista mediante el mismo materializador. La consola puede
cambiar únicamente los parámetros/series ya expuestos por su configuración;
no ofrece editor Python ni acceso a parámetros internos de reglas.

## Acceptance criteria

- [x] El analista puede verificar qué revisiones de reglas usará una consola o programación; su activación exige aplicaciones válidas para las capacidades instaladas.
- [x] Overrides y copias operativas autorizados se resuelven antes de compilar; las reglas reciben esos valores efectivos y el snapshot conserva su procedencia.
- [x] Una configuración externa no puede cambiar código, agregar alias, sustituir pins de reglas o escribir parámetros de reglas no expuestos por este corte.
- [x] Las corridas manuales, de consola y programadas pasan por la misma validación, aislamiento, límites, snapshot e IR; no hay un recorrido que omita restricciones.
- [x] Un cambio de rango recalcula ventanas y referencias desde entradas exactas; faltantes, obsolescencia o incompatibilidad bloquean sin adoptar revisiones actuales en silencio.
- [x] Un tick fallido o repetido conserva estado/idempotencia y no crea corridas duplicadas; un reintento de corrida consume su snapshot congelado.
- [x] El operador recibe causa operativa segura y acceso al recorrido de revisión existente; solo usuarios internos reciben detalle técnico, código o IR.
- [x] Cada corrida registra actor/origen real y revisiones efectivas. Revocación de permisos y cambios concurrentes se validan en el límite correspondiente.
- [x] Si la función/runtime se deshabilita, las corridas nuevas con reglas bloquean y el historial permanece accesible; consolas/programaciones sin reglas conservan su flujo anterior.

## Demonstration and validation

Usar la misma regla hidro v2 desde el analista, una consola y un tick programado,
comprobando restricciones equivalentes con los inputs efectivos de cada origen.
Cambiar una serie operativa y verificar lineage. Cubrir tick repetido, runtime
ausente, rango incompleto y payload externo sin filtraciones mediante UI/API y
ejecución real; no habilitar un adaptador de componente que aún no esté entregado.

## Blocked by

- [REG-009](REG-009-revisiones-y-obsolescencia.md).
- [REG-010](REG-010-inspeccionar-cumplimiento.md).
- [REG-011](REG-011-hidro-simple.md).

## Implementación

`app/rule_operations.py` prepara el contexto operativo, comprueba las aplicaciones
fijadas y envía su compilación al worker OCI existente. Consolas y programaciones
usan `materialize_run`: mismas cotas, capacidades, cuotas, snapshot e IR que el
analista. La activación recompila y valida sin crear una versión ni una corrida.
El SDK permanece en `reg-013.1`; no cambia el contrato matemático de Julia.

Los escalares expuestos se aplican antes de compilar. Las copias de series solo
permiten diferencias en columnas configuradas, con origen permitido y propiedad
de la consola; otros cambios siguen exigiendo recuperación del analista.
Los puertos de reglas conservan sus revisiones exactas. Rango, ventanas y datos
conocidos se reconstruyen en cada operación. El snapshot añade trabajo OCI,
copias, overrides y origen real; no modifica aplicaciones ni corridas anteriores.

La configuración interna muestra publicaciones, estado y revisión contextual.
El operador recibe el bloqueo seguro existente y puede solicitar revisión sin
acceder a código, IR o parámetros de reglas. Se comprueban otra vez permisos,
configuración, fuentes, aplicaciones y runtime al confirmar. Una programación
usa la identidad de su creador autorizado y registra además al iniciador del tick.

La reclamación transaccional de `(schedule_id, due_at)` conserva el tick exitoso
o fallido ante entregas repetidas. Versión, corrida y referencias del tick se
confirman juntas. Un cambio concurrente de fecha no se sobrescribe al finalizar.
Los reintentos explícitos de corrida usan la versión congelada. Las operaciones
sin reglas siguen funcionando aunque una variante hermana tenga reglas.

Se utilizó TDD con las fronteras ya adoptadas por el proyecto: HTTP autenticado,
SQLite/PostgreSQL y OCI reales; validación del motor como frontera externa en
las pruebas HTTP y Julia real en Chromium. Se observaron fallos antes de resolver
cada recorrido y las regresiones de concurrencia, enlace, reactivación y variante
hermana. [Configuración y repetición](../runtime.md#consolas-y-programaciones-reg-014).

## Evidencia de entrega

- **22 pruebas HTTP nuevas aprobadas**, once por motor SQLite/PostgreSQL, con
  worker OCI real y sin omisiones. Cubren overrides, procedencia de copias,
  pins y revisión contextual, obsolescencia, rango exacto/móvil, presupuesto,
  faltantes, reintento congelado, idempotencia, runtime ausente o perdido,
  revocación, payloads externos, reactivación y cambios concurrentes de fecha.
  Una variante hermana con reglas no bloquea la operación sin reglas.
- **95 pruebas de regresión aprobadas** de configuración de consola, bloqueo
  seguro y programaciones, además de **13 de hidro simple REG-011** y **34 de
  REG-002/corridas manuales**. La suite final ejecutó 56 casos: los 22 nuevos
  y esas 34 regresiones. Dos expectativas anteriores de programación quedaron
  superadas por REG-014; se actualizaron para exigir runtime al activar y se
  repitieron con éxito en ambas bases. Los otros 54 casos ya habían pasado.
- **64 pruebas React aprobadas** de consola, administración y recuperación,
  incluidas dos nuevas para revisiones fijadas y enlaces de revisión.
- **Chromium con API, OCI y Julia reales aprobado**, repetido tras los últimos
  cambios en 5,2 minutos: una publicación fija
  produce caudales `[5, 5]` desde el analista, `[4, 4]` desde la consola con
  override y `[5, 5]` desde la programación. Las seis restricciones evaluadas
  se cumplen; se comprueban origen, pins y ausencia de duplicados. Capturas
  `frontend/test-results/reg014-console.png` y `reg014-schedule.png` inspeccionadas.
- OpenAPI regenerado y `api:check`, TypeScript, ESLint, build, compilación Python,
  Prettier de archivos modificados y `git diff --check` aprobados. El build
  mantiene la advertencia existente de tamaño de bundles.

CI incorpora las nuevas suites HTTP, React y navegador. No se ejecutó CI remoto.
