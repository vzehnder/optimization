# REG-013: Relacionar generación renovable e intercambio con la red

Status: Done
Type: AFK
Triage: ready-for-agent
Source: [Plan](../plan.md), secciones 5 y 6.
User stories covered: HU-04, HU-11.

## What to build

Completar una relación eléctrica personalizada dentro de un mismo caso: usar
generación renovable utilizada/recortada e importación/exportación de red en
expresiones afines. Un ejemplo demostrable limita la exportación a una fracción
conocida de la generación renovable utilizada.

## Acceptance criteria

- [x] El editor ofrece las cuatro capacidades con unidades MW y convención de magnitudes no negativas; cualquier expresión neta declara su signo.
- [x] La disponibilidad renovable se expone como dato conocido, no se confunde con generación elegida por el solver. La demanda fija tampoco se presenta como decisión libre.
- [x] El analista selecciona alias de red y renovable, parámetros/series, prueba la relación y la aplica a una variante mediante el flujo común.
- [x] Julia agrega la relación sobre variables reales y conserva balance eléctrico, disponibilidad, límites base de red y exclusión de simultaneidad cuando esté configurada.
- [x] Solo se combinan componentes del mismo snapshot; no se inventa acoplamiento eléctrico entre el sistema v3 separado y un despacho v1/v2.
- [x] Unidades, referencias, pins y cambios de contexto usan los mismos validadores y lineage; una relación no lineal se rechaza como en hidráulica.
- [x] Los resultados muestran el efecto conjunto sobre exportación, generación y recorte, y los casos sin reglas siguen iguales.

## Demonstration and validation

Aplicar un límite de exportación igual a una fracción de la generación utilizada
en un caso con excedentes; comprobar la ecuación y el balance, no solo la curva
de exportación. Probar orientación de signos, referencias cruzadas inválidas
y el flujo web a solve con las mismas garantías de contrato.

## Blocked by

- [REG-011](REG-011-hidro-simple.md).

## Fronteras TDD confirmadas (2026-09-25)

El usuario confirmó las tres interfaces: API HTTP autenticada con persistencia
y runtime OCI real, entrada/salida pública de Julia y UI React con recorrido
de navegador. Se implementa una capacidad a la vez mediante ciclos rojo → verde.

## Implementación

Red y renovables guardadas ofrecen el mismo editor contextual, publicación,
preview y aplicación a variante. `importacion`, `exportacion`, `generacion` y
`recorte` son magnitudes no negativas en MW. El editor declara el signo de
exportación neta y autocompleta las capacidades de los alias seleccionados.
`disponibilidad[t]` y `demanda[t]` son series conocidas del snapshot, con unidades;
la demanda se selecciona como alias de lectura y no se convierte en decisión.

El adaptador `electric_system.v1` conserva las variables y ecuaciones existentes
de Julia para sistemas v1/v2. Se negocia antes de encolar; conserva límites,
balance y exclusión de simultaneidad. Las cotas renovables usan la disponibilidad
de cada período. Los alias, parámetros, series canónicas, revisiones, rampas,
biblioteca, hashes y recuperación de obsolescencia conservan los contratos comunes.
El informe reconstruye las cuatro variables desde los artefactos congelados.
El contrato v3 comprueba también que el tipo declarado coincida con la clave
hidráulica: no admite disfrazar un embalse como conexión eléctrica.

El SDK pasa a `reg-013.1`; se reconstruyó la imagen OCI local para las pruebas.
Los workers que adopten este código deben usar ese nuevo digest. Las aplicaciones
anteriores requieren publicar, probar y aplicar de nuevo; los resultados históricos
conservan su interpretación. [Operación y ejemplo reproducible](../runtime.md#red-y-renovables-reg-013).

## Evidencia de entrega

- **16 pruebas nuevas HTTP aprobadas**, ocho por motor SQLite/PostgreSQL, con
  OCI real y sin omisiones. Cubren capacidades, datos conocidos, fracción horaria,
  pins, obsolescencia, historia intacta, cotas por período, biblioteca, rampas,
  referencias ajenas, unidades y rechazo de decisiones no lineales. Junto con
  la instalación aditiva se ejecutaron 17 pruebas en 175,843 s.
- **46 comprobaciones Python de regresión aprobadas**, incluyendo las 44 de
  hidro simple, baterías, reutilización y runtime, la instalación aditiva y el
  recorrido HTTP original. Se actualizaron y repitieron dos expectativas
  superadas por REG-013: renovables ahora compatibles y SDK `reg-013.1`.
  Se verificaron aislamiento, cuotas, agotamiento de memoria y timeout en OCI.
- **663 comprobaciones Julia distintas aprobadas**: 28 eléctricas, 25 de baterías,
  24 de hidro simple, 50 hidráulicas, cuatro de solución primal y 532 generales.
  Cubren roundtrip, cotas, referencias, separación v3 y solución con/sin reglas.
  La primera ejecución general tuvo un error al interpretar JSON porque un
  subproceso emitió mensajes de recompilación. Repetido el test CLI con la caché
  estable, pasaron sus 57 comprobaciones; las otras 475 generales ya habían pasado.
- **89 pruebas React aprobadas** en diez módulos, incluidas dos nuevas de red
  y renovables con selección de alias, unidades, datos conocidos y retorno contextual.
- **Chromium real aprobado** con API temporal, OCI y Julia en 2,4 minutos.
  Se guardó el código desde el editor, se publicaron/probaron/aplicaron doce
  restricciones y se resolvió la variante. La fracción 0,5 produjo exportación
  `[2, 2, 0, 0]`, importación `[0, 0, 1, 2]`, generación `[4, 4, 1, 0]` y recorte
  `[6, 4, 0, 0]` MW; se verificaron balance y disponibilidad. El informe muestra
  doce filas evaluadas y cumplidas. Capturas `frontend/test-results/reg013-applied.png`
  y `reg013-compliance.png` inspeccionadas.
- OpenAPI regenerado y `api:check`, TypeScript, ESLint, build, compilación Python,
  Prettier de archivos modificados y `git diff --check` aprobados. El build
  mantiene la advertencia existente de tamaño de bundles.

CI incluye las nuevas suites HTTP, React, Julia y navegador. No se ejecutó CI remoto.
