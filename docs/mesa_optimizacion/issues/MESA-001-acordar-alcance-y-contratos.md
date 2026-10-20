# MESA-001 · Acordar el alcance de la mesa y sus contratos observables

Status: Todo
Type: HITL
Triage: ready-for-agent
Assignee: —
Source: [Plan de implementación](../plan_implementacion.md)
User stories covered: HU-01, HU-05, HU-06, HU-11

## What to build

Revisar las decisiones propuestas contra un caso real de uso y fijar qué significa preparar, ejecutar y comparar desde la mesa. La aprobación conceptual del prototipo ya existe; este ticket resuelve ubicación, contexto, capacidades del motor, significado de «antes», persistencia visual e interfaces públicas de prueba. Registrar las decisiones para que las entregas AFK no dependan de interpretaciones distintas.

## Acceptance criteria

- [ ] Registrar A · Paneles como diseño principal o el ajuste indicado por el usuario, manteniendo la pantalla única solicitada.
- [ ] Confirmar superficie interna del analista, contexto de caso/variante y alcance de la configuración por usuario/caso.
- [ ] Documentar qué combinaciones de BESS, demanda, renovables y red hidráulica son ejecutables hoy. Resolver si el caso objetivo exige cooptimización en un único modelo; si falta soporte, agregar una entrega vertical del motor y enlazarla como dependencia antes de prometer ejecución mixta.
- [ ] Acordar las reglas de entradas, outputs sin referencia, ejecución de referencia y Δ; no aceptar ceros o series ficticias como comparación.
- [x] Confirmar S1 (navegador), S2 (HTTP) y S3 condicional (contrato público del motor) con el usuario antes de escribir tests, conforme a la habilidad TDD. Confirmado el 2026-10-20.
- [x] Revisar granularidad, dependencias y clasificación AFK/HITL del tracker y registrar cambios sin dar por aprobadas decisiones no discutidas. El usuario pidió mantener el desglose propuesto el 2026-10-20.
- [ ] Comprobar disponibilidad e integración del trabajo local de simulación hidráulica y progreso; registrar cualquier dependencia externa concreta.

## Blocked by

Ninguna. Puede revisarse de inmediato.

## Validación TDD

Interfaces acordadas: S1, S2 y uso condicional de S3, confirmadas el 2026-10-20. No escribir pruebas como parte de este trabajo de planificación.

Evidencia: decisión fechada con alternativas resueltas, aprobación de interfaces de prueba y tracker actualizado. No se marca Done por haber creado este documento.

Aplicar la [estrategia TDD](../validacion_tdd.md) y la definición de terminado del plan. Las interfaces S1/S2 y S3 condicional fueron confirmadas por el usuario el 2026-10-20; registrar en MESA-001 cualquier interfaz adicional antes de probarla. Cada ciclo implementa un solo comportamiento observable.

## Demostración de cierre

Un caso eléctrico y una red hidráulica de ejemplo ilustran el recorrido y sus diferencias; cada dato «antes» tiene una procedencia definida.

## Evidencia y seguimiento

- Inicio de implementación: pendiente; acuerdos de planificación registrados el 2026-10-20.
- Evidencia rojo → verde / revisión HITL: pendiente.
- Pruebas y comandos ejecutados: pendiente.
- Capturas de implementación y diferencias revisadas: pendiente, cuando aplique.
- Decisiones: el usuario respondió «Mantener el desglose propuesto» y «Confirmar las interfaces propuestas» el 2026-10-20. Faltan las decisiones técnicas restantes; no marcar este ticket Done todavía.
- Cierre y responsable: pendiente.
