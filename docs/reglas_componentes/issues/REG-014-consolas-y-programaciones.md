# REG-014: Ejecutar reglas fijadas desde consolas y programaciones

Status: Todo
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

- [ ] El analista puede verificar qué revisiones de reglas usará una consola o programación; su activación exige aplicaciones válidas para las capacidades instaladas.
- [ ] Overrides y copias operativas autorizados se resuelven antes de compilar; las reglas reciben esos valores efectivos y el snapshot conserva su procedencia.
- [ ] Una configuración externa no puede cambiar código, agregar alias, sustituir pins de reglas o escribir parámetros de reglas no expuestos por este corte.
- [ ] Las corridas manuales, de consola y programadas pasan por la misma validación, aislamiento, límites, snapshot e IR; no hay un recorrido que omita restricciones.
- [ ] Un cambio de rango recalcula ventanas y referencias desde entradas exactas; faltantes, obsolescencia o incompatibilidad bloquean sin adoptar revisiones actuales en silencio.
- [ ] Un tick fallido o repetido conserva estado/idempotencia y no crea corridas duplicadas; un reintento de corrida consume su snapshot congelado.
- [ ] El operador recibe causa operativa segura y acceso al recorrido de revisión existente; solo usuarios internos reciben detalle técnico, código o IR.
- [ ] Cada corrida registra actor/origen real y revisiones efectivas. Revocación de permisos y cambios concurrentes se validan en el límite correspondiente.
- [ ] Si la función/runtime se deshabilita, las corridas nuevas con reglas bloquean y el historial permanece accesible; consolas/programaciones sin reglas conservan su flujo anterior.

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
