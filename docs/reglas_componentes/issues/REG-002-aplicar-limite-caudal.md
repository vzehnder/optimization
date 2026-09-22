# REG-002: Aplicar un máximo de caudal Python en una corrida hidráulica

Status: Done
Type: AFK
Triage: ready-for-agent
Source: [Plan](../plan.md), secciones 4, 5, 6 y 9.
User stories covered: HU-01, HU-02, HU-09.

## What to build

Completar el primer recorrido hasta el optimizador: el analista escribe una
restricción afín que limita el caudal turbinado de una unidad v3 con un parámetro
escalar, publica una revisión, la aplica a una variante y ejecuta el caso.
La corrida demuestra que el límite personalizado modifica el resultado y deja
trazabilidad. El camino usa un contrato genérico de filas afines aunque esta
entrega solo exponga el caudal de una unidad.

## Acceptance criteria

- [x] El SDK produce restricciones simbólicas mediante `<=`, `>=` y `==`, con nombres y referencias de origen; nunca las evalúa como booleanos Python.
- [x] Publicar crea una revisión inmutable; aplicar fija esa revisión, parámetros, objeto y variante. Desactivar registra actor/motivo y no borra historia.
- [x] Preview muestra filas, unidades y alcance temporal; una regla sin filas requiere aceptación explícita antes de aplicarse como restricción.
- [x] Servidor y Julia validan IR, coeficientes finitos, unidades y referencias a la unidad/grilla del snapshot. Un producto de decisiones o condición simbólica se rechaza.
- [x] Materializar congela código, contexto, runtime e IR con hashes, comprueba concurrencia al confirmar y es atómico/idempotente; Python no se ejecuta dentro de Julia ni durante un reintento del mismo snapshot.
- [x] JuMP agrega el límite junto a los límites y balances base. No se sustituye la capacidad física ni se omite una regla contradictoria.
- [x] Una capacidad/versión desconocida, motor sin soporte, aplicación inválida u obsoleta bloquea antes de resolver. Los cambios de topología/parámetros/código publicado no actualizan pins automáticamente.
- [x] Todos los productores de corridas preservan las reglas o bloquean con motivo; consolas/programaciones con reglas activas aún no soportadas bloquean. Desactivar la funcionalidad tampoco permite omitirlas.
- [x] La pantalla de corrida permite identificar revisión de regla y parámetros usados; modelos sin reglas conservan su ejecución anterior.

## Demonstration and validation

En un caso de cuatro períodos con solución base por encima del límite elegido,
aplicar un máximo de 5 m³/s y comprobar caudales/resultado. Desactivar y recuperar
el comportamiento base. Verificar en Julia el efecto real, snapshots históricos,
roundtrip de IR, cambio concurrente y negativa de un motor viejo; completar la
prueba desde UI hasta resultados usando el runtime aislado.

### Evidencia de implementación (2026-09-21)

Interfaces de TDD confirmadas por el usuario: HTTP SQLite/PostgreSQL, editor
contextual, runtime OCI y carga/optimización pública de Julia, incluido el efecto
real del límite de 5 m³/s. Los ciclos rojo–verde cubrieron emisión simbólica,
publicación, aplicación, snapshots, integración JuMP, linaje e idempotencia.
Se observaron y corrigieron, entre otros, reintentos tras desactivar, publicaciones
nuevas durante preview, apagado durante validación, pérdida de fuentes, fechas
inválidas y aceptación silenciosa de un término desconocido por Julia.

- `tests.test_reg002_rules`: **22 pruebas aprobadas sin omisiones**, ejecutadas
  en SQLite y PostgreSQL 18 aislado con compilación OCI real. Incluyen rechazo de
  motor sin capacidad, regla vacía, fuentes legadas, conflicto concurrente por HTTP,
  revisión inmutable y bloqueo de programaciones/versiones sin reglas.
- `tests.test_reg001_rules`, `tests.test_reg001_runtime` y
  `tests.test_reg002_runtime`: **36 pruebas aprobadas sin omisiones**. Docker
  28.5.1 en Ubuntu WSL, CPython 3.12.14, SDK `reg-002.1`, política `reg-001.1`.
  El aislamiento, cancelación, límites y recuperación anteriores siguen pasando.
- `julia --project=. test/component_rules.jl`: **18 comprobaciones aprobadas**
  con Julia 1.11.7/HiGHS. Base **40 m³/s** y máximo **5 m³/s** en los cuatro
  períodos, igualdad, contradicción con mínimo físico, IR inválido y conservación
  exacta del bloque de reglas en el documento resuelto.
- `julia --project=. test/runtests.jl`: **532 comprobaciones aprobadas** de la
  suite general existente, incluidos modelos sin reglas y comandos CLI.
- React: **23 pruebas aprobadas** en `ComponentRules.test.tsx` y
  `RunExperience.test.tsx`; TypeScript, ESLint, Prettier de archivos modificados,
  build y OpenAPI regenerado/`api:check` verificados.
- Chromium: ambos recorridos `component-rules.spec.ts` y
  `component-rules-execution.spec.ts` aprobados. El segundo usa worker OCI y Julia
  reales: aplica desde UI, resuelve a **5 m³/s**, desactiva, recupera **40 m³/s**
  y conserva el resultado histórico a **5 m³/s**. Capturas revisadas visualmente.
- Regresión Python de variantes, materialización canónica, programaciones y
  consolas: **74 pruebas, 69 aprobadas y 5 omitidas** por las condiciones de esas
  suites. La persistencia nueva sí se verificó en ambos motores en las 22 anteriores.

El workflow incluye los contratos HTTP/OCI, Julia y ambos recorridos de navegador;
no se ejecutó CI remoto. No se repitió la suite global de frontend, cuyos fallos
preexistentes están registrados en REG-001. No se desplegó ni se modificaron bases
de proyectos. Configuración, límites y reproducción: [runtime.md](../runtime.md).

El alcance sigue siendo caudal de una unidad hidráulica v3 con parámetros escalares.
Series horarias son REG-003; ejecución desde consolas y programaciones es REG-014.

## Blocked by

- [REG-001](REG-001-probar-regla-python.md).
