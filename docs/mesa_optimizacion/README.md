# Mesa de optimización

Plan de implementación solicitado el **20 de octubre de 2026** a partir del
prototipo que el usuario consideró adecuado. El alcance de este trabajo es
planificación y evidencia visual; la implementación funcional todavía no comienza.

- [Plan y decisiones propuestas](plan_implementacion.md).
- [Tracker de las 14 entregas](tracker.md).
- [Estrategia de validación con TDD](validacion_tdd.md).
- [Capturas y reproducción de la referencia](referencias/README.md).
- [Copia autónoma del prototipo validado](referencias/prototipo-validado.html?variant=A).

El tracker es local, en Markdown, siguiendo la práctica existente del repositorio.
El usuario aprobó el desglose de 14 entregas, sus dependencias y clasificación
AFK/HITL, y confirmó las interfaces de prueba S1/S2 y S3 condicional el 2026-10-20.
Los tickets tienen triage ready-for-agent y criterios de aceptación. La primera
entrega conserva las decisiones técnicas pendientes; la implementación no comenzó.

La propuesta principal es **A · Paneles**: pestañas horizontales, matriz 2×2,
configuración de cada vista, gráficos/tablas y ejecución desde la misma pantalla.
Las alternativas B y C se conservan como referencia, no como tres implementaciones
obligatorias.

## Referencia visual

Estado inicial, 1440×900:

![Mesa de optimización con cuatro paneles antes de simular](referencias/01-mesa-general-antes.png)

Comparación después de una simulación ficticia, con tres gráficos y una tabla:

![Comparación antes y después con gráficos y tabla](referencias/02-mesa-comparacion-graficos-tabla.png)

Las capturas fijan la intención de diseño. Los números son inventados y no
constituyen resultados de referencia del optimizador.
