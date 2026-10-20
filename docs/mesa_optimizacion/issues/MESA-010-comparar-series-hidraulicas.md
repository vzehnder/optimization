# MESA-010 · Comparar resultados hidráulicos sin mezclar objetos o unidades

Status: Todo
Type: AFK
Triage: ready-for-agent
Assignee: —
Source: [Plan de implementación](../plan_implementacion.md)
User stories covered: HU-03, HU-06

## What to build

Extender la comparación a centrales, unidades, embalses y tramos usando el linaje hidráulico real. Identificar correctamente series de entrada y salida, y emparejar solo trayectorias compatibles. No reconstruir un supuesto estado previo a partir de parámetros iniciales.

## Acceptance criteria

- [ ] Potencia de central, caudal, volumen y cota se asignan a la entidad hidráulica correcta y a la ejecución seleccionada.
- [ ] Caudales externos invariables no presentan reducciones ficticias; volumen/cota sin trayectoria de referencia muestran ausencia de referencia.
- [ ] El volumen inicial escalar se presenta como parámetro y no como una serie antes equivalente a la trayectoria calculada.
- [ ] Los paneles multiserie separan m³/s, hm³, MW y m con leyendas y escalas legibles; tabla y gráfico conservan las mismas muestras.
- [ ] Referencias de otra topología/identidad, horizonte incompatible o unidad incompatible no producen una Δ engañosa.
- [ ] La comparación permanece reproducible tras editar nombres, series o parámetros del caso actual.
- [ ] Una red mínima ejecutada proporciona evidencia de comparación por central y embalse a través de interfaces públicas.

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

- Inicio: pendiente.
- Evidencia rojo → verde / revisión HITL: pendiente.
- Pruebas y comandos ejecutados: pendiente.
- Capturas de implementación y diferencias revisadas: pendiente, cuando aplique.
- Decisiones o desviaciones respecto del plan: pendiente.
- Cierre y responsable: pendiente.
