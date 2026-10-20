# MESA-005 · Consultar centrales, embalses y otros objetos hidráulicos

Status: Todo
Type: AFK
Triage: ready-for-agent
Assignee: —
Source: [Plan de implementación](../plan_implementacion.md)
User stories covered: HU-01, HU-03, HU-11

## What to build

Conectar el inventario de la serie hidráulica construida al espacio de trabajo: centrales, embalses y, cuando existan, unidades y tramos. Reutilizar identidades base y de caso, vínculos de series y resultados existentes. El usuario reconoce los componentes del diagrama en la mesa.

## Acceptance criteria

- [ ] Inventariar centrales y embalses activos del caso; unidades/tramos existentes están disponibles en el selector sin perder su pertenencia.
- [ ] Conservar la correspondencia entre componente de caso, activo base y entidad del resultado incluso con nombres duplicados.
- [ ] Mostrar entradas de caudal, parámetros y salidas reales de potencia, caudal, volumen o cota según su rol y disponibilidad.
- [ ] No usar un volumen inicial escalar como trayectoria «antes» ni atribuir a una central el caudal de otro nodo.
- [ ] Unidades diferentes usan escalas separadas y todas las muestras incluyen período e identidad de fuente.
- [ ] Una serie hidráulica sin preparar, un objeto inactivo y un resultado no compatible producen estados explicativos.
- [ ] Las lecturas respetan caso/proyecto y usan el catálogo/adaptador vigente sin duplicar muestras del sistema hidráulico.
- [ ] Verificar la consulta de una central y un embalse con datos persistidos a través de API y navegador.

## Blocked by

- [MESA-002 · Abrir un caso real y consultar demanda en la mesa](MESA-002-abrir-caso-y-demanda-real.md)

## Validación TDD

Interfaces acordadas: S1 + S2

Primer test: dos centrales con nombre igual conservan series separadas. Añadir un embalse cuyo volumen inicial es parámetro y cuya trayectoria solo existe como resultado.

Aplicar la [estrategia TDD](../validacion_tdd.md) y la definición de terminado del plan. Las interfaces S1/S2 y S3 condicional fueron confirmadas por el usuario el 2026-10-20; registrar en MESA-001 cualquier interfaz adicional antes de probarla. Cada ciclo implementa un solo comportamiento observable.

## Demostración de cierre

Los objetos del diagrama aparecen como pestañas seleccionables y conservan sus unidades y relaciones.

## Evidencia y seguimiento

- Inicio: pendiente.
- Evidencia rojo → verde / revisión HITL: pendiente.
- Pruebas y comandos ejecutados: pendiente.
- Capturas de implementación y diferencias revisadas: pendiente, cuando aplique.
- Decisiones o desviaciones respecto del plan: pendiente.
- Cierre y responsable: pendiente.
