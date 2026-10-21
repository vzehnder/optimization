# MESA-005 · Consultar centrales, embalses y otros objetos hidráulicos

Status: Done
Type: AFK
Triage: ready-for-agent
Assignee: Codex
Source: [Plan de implementación](../plan_implementacion.md)
User stories covered: HU-01, HU-03, HU-11

## What to build

Conectar el inventario de la serie hidráulica construida al espacio de trabajo: centrales, embalses y, cuando existan, unidades y tramos. Reutilizar identidades base y de caso, vínculos de series y resultados existentes. El usuario reconoce los componentes del diagrama en la mesa.

## Acceptance criteria

- [x] Inventariar centrales y embalses activos del caso; unidades/tramos existentes están disponibles en el selector sin perder su pertenencia.
- [x] Conservar la correspondencia entre componente de caso, activo base y entidad del resultado incluso con nombres duplicados.
- [x] Mostrar entradas de caudal, parámetros y salidas reales de potencia, caudal, volumen o cota según su rol y disponibilidad.
- [x] No usar un volumen inicial escalar como trayectoria «antes» ni atribuir a una central el caudal de otro nodo.
- [x] Unidades diferentes usan escalas separadas y todas las muestras incluyen período e identidad de fuente.
- [x] Una serie hidráulica sin preparar, un objeto inactivo y un resultado no compatible producen estados explicativos.
- [x] Las lecturas respetan caso/proyecto y usan el catálogo/adaptador vigente sin duplicar muestras del sistema hidráulico.
- [x] Verificar la consulta de una central y un embalse con datos persistidos a través de API y navegador.

## Blocked by

- [MESA-002 · Abrir un caso real y consultar demanda en la mesa](MESA-002-abrir-caso-y-demanda-real.md)

## Validación TDD

Interfaces acordadas: S1 + S2

Primer test: dos centrales con nombre igual conservan series separadas. Añadir un embalse cuyo volumen inicial es parámetro y cuya trayectoria solo existe como resultado.

Aplicar la [estrategia TDD](../validacion_tdd.md) y la definición de terminado del plan. Las interfaces S1/S2 y S3 condicional fueron confirmadas por el usuario el 2026-10-20; registrar en MESA-001 cualquier interfaz adicional antes de probarla. Cada ciclo implementa un solo comportamiento observable.

## Demostración de cierre

Los objetos del diagrama aparecen como pestañas seleccionables y conservan sus unidades y relaciones.

## Evidencia y seguimiento

- Inicio: 2026-10-20, por Codex, a petición del usuario. MESA-002 Done; interfaces S1 navegador y S2 HTTP ya confirmadas. Primer ciclo: inventario de centrales homónimas con identidades y pertenencia preservadas.
- Evidencia: [dieciséis ciclos rojo → verde, comandos y revisión AFK](../evidencia/MESA-005/validacion.md).
- Implementación: inventario base/caso y pertenencia, entradas canónicas/legacy,
  parámetros escalares, resultados v3 por entidad y consulta de hidro simple v2.
  Las centrales agregan solo sus unidades completas y compatibles; estados
  explicativos para inactividad, falta de preparación y resultados incompatibles.
- Validación: diecisiete pruebas HTTP y dos de navegador nuevas. 172 pruebas Python
  distintas verificadas entre ejecución amplia y focalizada; cinco PostgreSQL
  omitidas. 15 MESA y cinco regresiones de navegador OK; 336 Vitest verificadas
  entre suite y reintento del archivo con fallo de foco. Build, TypeScript, ESLint,
  OpenAPI y formato modificado OK. El check global conserva 16 avisos de formato
  preexistentes; los logs registran los intentos fallidos y las correcciones.
- Capturas revisadas: [1440×900](../evidencia/MESA-005/mesa-hidraulica-1440.png) y
  [390 px](../evidencia/MESA-005/mesa-hidraulica-390.png), con geometría y accesibilidad
  comprobadas en navegador. Se conservan las referencias originales.
- Alcance: consulta de entradas y artefactos/índices persistidos, sin modificar el
  motor ni duplicar almacenamiento hidráulico. Los resultados de las fixtures son
  deterministas; no se atribuyen a una nueva resolución Julia. Ejecutar desde la
  mesa y comparar permanecen en MESA-008/010. Se actualizó la expectativa antigua
  de artefactos de promoción para incluir el `progress_log` del worker vigente.
- Cierre: **Done**, Codex, 2026-10-20, tras revisión técnica AFK y visual.
  Siguiente entrega recomendada: MESA-006.
