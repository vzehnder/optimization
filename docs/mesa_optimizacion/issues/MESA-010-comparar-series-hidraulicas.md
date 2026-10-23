# MESA-010 · Comparar resultados hidráulicos sin mezclar objetos o unidades

Status: Done
Type: AFK
Triage: ready-for-agent
Assignee: Codex
Source: [Plan de implementación](../plan_implementacion.md)
User stories covered: HU-03, HU-06

## What to build

Extender la comparación a centrales, unidades, embalses y tramos usando el linaje hidráulico real. Identificar correctamente series de entrada y salida, y emparejar solo trayectorias compatibles. No reconstruir un supuesto estado previo a partir de parámetros iniciales.

## Acceptance criteria

- [x] Potencia de central, caudal, volumen y cota se asignan a la entidad hidráulica correcta y a la ejecución seleccionada.
- [x] Caudales externos invariables no presentan reducciones ficticias; volumen/cota sin trayectoria de referencia muestran ausencia de referencia.
- [x] El volumen inicial escalar se presenta como parámetro y no como una serie antes equivalente a la trayectoria calculada.
- [x] Los paneles multiserie separan m³/s, hm³, MW y m con leyendas y escalas legibles; tabla y gráfico conservan las mismas muestras.
- [x] Referencias de otra topología/identidad, horizonte incompatible o unidad incompatible no producen una Δ engañosa.
- [x] La comparación permanece reproducible tras editar nombres, series o parámetros del caso actual.
- [x] Una red mínima ejecutada proporciona evidencia de comparación por central y embalse a través de interfaces públicas.

## Blocked by

- [MESA-008 · Ejecutar una red hidráulica desde la misma mesa](MESA-008-ejecutar-red-hidraulica.md)
- [MESA-009 · Comparar entradas y resultados eléctricos con procedencia](MESA-009-comparar-series-electricas.md)

## Validación TDD

Interfaces acordadas: S1 + S2

Primer test: un volumen y un caudal no se emparejan aunque compartan nombre. Añadir salida sin referencia y ejecución histórica tras editar el caso.

Aplicar la [estrategia TDD](../validacion_tdd.md) y la definición de terminado del plan. Las interfaces S1/S2 y S3 condicional fueron confirmadas por el usuario el 2026-10-20; registrar en MESA-001 cualquier interfaz adicional antes de probarla. Cada ciclo implementa un solo comportamiento observable.

## Demostración de cierre

Mostrar en una matriz potencia, caudal, volumen y cota; alternar tabla/gráfico y explicar de dónde sale cada lado.

## Evidencia y seguimiento

- Inicio: 2026-10-21, Codex, por instrucción del usuario. MESA-008/009 Done;
  interfaces confirmadas S1 (navegador) y S2 (HTTP). Primer ciclo: separar volumen
  y caudal homónimos desde el snapshot, sin referencia ni Δ inventadas.
- Evidencia: [13 ciclos TDD, revisión AFK y límites](../evidencia/MESA-010/validacion.md).
- Pruebas nuevas: 13 HTTP y dos de navegador. Regresión: 129 Python OK (128 de
  proyección/contratos más una integración con dos corridas reales), 32 MESA y
  cinco regresiones generales de navegador OK. Seis comparaciones revalidadas
  tras el último ajuste móvil. Vitest: 335/336; persiste el fallo de foco de
  ReportExperience ya documentado en MESA-005/007, también al reintentar.
- Capturas: matriz de potencia/caudal/volumen/cota y paneles multiserie a 1440/390
  px, revisadas con geometría, unidades, procedencia, teclado y Axe. Originales intactos.
- Decisiones: comparación v3 desde entidades del snapshot y extensión de señales
  hidro simple v2. Parámetros escalares históricos, índices/CSV y compatibilidad
  explícita. Sin cambios del motor ni persistencia. OpenAPI, build, TypeScript,
  ESLint y formato modificado OK; dieciséis archivos ajenos mantienen formato pendiente.
- Cierre: **Done**, Codex, 2026-10-21, tras revisión técnica AFK y visual.
  Siguiente recomendada: MESA-011.
