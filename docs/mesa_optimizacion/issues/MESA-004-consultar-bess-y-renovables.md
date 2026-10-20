# MESA-004 · Consultar BESS, demanda y renovables por componente

Status: Todo
Type: AFK
Triage: ready-for-agent
Assignee: —
Source: [Plan de implementación](../plan_implementacion.md)
User stories covered: HU-01, HU-03, HU-11

## What to build

Ampliar el recorrido de consulta a las familias eléctricas del caso. Usar los descriptores canónicos para distinguir disponibilidad renovable, demanda, parámetros BESS y salidas del optimizador. Incorporar esas series a pestañas y selectores, incluyendo resultados de una ejecución existente cuando corresponda.

## Acceptance criteria

- [ ] Descubrir todas las instancias BESS, carga y generación renovable activas del contexto sin confundir nombres repetidos.
- [ ] Consultar las entradas y parámetros existentes con unidades y procedencia, sin convertir escalares en series horarias ficticias.
- [ ] Exponer carga/descarga, energía o SOC y generación usada/vertida solo cuando exista el resultado correspondiente.
- [ ] Sin run o sin columna compatible, mostrar estado no disponible; no fabricar el perfil que dibuja el prototipo.
- [ ] Los selectores de panel ofrecen solo series compatibles con el componente; gráficos y tablas conservan identidad y unidad.
- [ ] Se preserva el comportamiento de casos v1/v2 existentes y se identifica el contrato soportado.
- [ ] Una prueba real de consulta verifica al menos un BESS y un renovable con datos disponibles y salidas todavía ausentes.

## Blocked by

- [MESA-002 · Abrir un caso real y consultar demanda en la mesa](MESA-002-abrir-caso-y-demanda-real.md)

## Validación TDD

Interfaces acordadas: S1 + S2

Primer test: abrir un caso sin runs, ver disponibilidad renovable y comprobar que potencia de descarga BESS figura sin resultado; luego consultar un run existente por la interfaz pública.

Aplicar la [estrategia TDD](../validacion_tdd.md) y la definición de terminado del plan. Las interfaces S1/S2 y S3 condicional fueron confirmadas por el usuario el 2026-10-20; registrar en MESA-001 cualquier interfaz adicional antes de probarla. Cada ciclo implementa un solo comportamiento observable.

## Demostración de cierre

Cambiar entre BESS, demanda y renovables sin salir de la mesa, con datos reales y estados vacíos honestos.

## Evidencia y seguimiento

- Inicio: pendiente.
- Evidencia rojo → verde / revisión HITL: pendiente.
- Pruebas y comandos ejecutados: pendiente.
- Capturas de implementación y diferencias revisadas: pendiente, cuando aplique.
- Decisiones o desviaciones respecto del plan: pendiente.
- Cierre y responsable: pendiente.
