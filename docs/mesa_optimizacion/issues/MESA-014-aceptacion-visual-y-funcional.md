# MESA-014 · Validar la mesa completa y habilitar su acceso en el producto

Status: Todo
Type: HITL
Triage: ready-for-agent
Assignee: —
Source: [Plan de implementación](../plan_implementacion.md)
User stories covered: HU-01, HU-02, HU-03, HU-04, HU-05, HU-06, HU-07, HU-08, HU-09, HU-10, HU-11

## What to build

Realizar la aceptación del recorrido completo, con datos reales de prueba y las capturas del prototipo como referencia de intención visual. Revisar las diferencias justificadas, aprobar la baseline de regresión de la implementación y habilitar su acceso según el mecanismo del producto, preservando los recorridos anteriores.

## Acceptance criteria

- [ ] Demostrar desde la mesa: abrir caso, configurar cuatro vistas, editar, guardar, elegir período, ejecutar, comparar y recuperar una corrida.
- [ ] Demostrar componente hidráulico nuevo y serie manual de apoyo/vinculada, con sus validaciones reales.
- [ ] Contrastar estado inicial y comparación mixta gráfico/tabla con los dos PNG de referencia a 1440×900; registrar diferencias aceptadas.
- [ ] Verificar teclado, foco de diálogos/pestañas, unidades/leyendas legibles y adaptación a 390 px sin scroll horizontal global.
- [ ] Revisar carga, vacío, conflicto, fallo de ejecución, pérdida de conexión y preparación obsoleta sin resultados inventados.
- [ ] Recibir conformidad del usuario sobre la experiencia implementada y registrar cualquier ajuste antes de marcar Done.
- [ ] Establecer baselines Playwright de la implementación solo tras la revisión; conservar la referencia original sin sobrescribirla.
- [ ] Registrar pruebas/regresiones pertinentes, actualizar ayuda y tracker, y habilitar acceso sin eliminar las rutas existentes ni desplegar fuera de lo autorizado.

## Blocked by

- [MESA-003 · Guardar pestañas, paneles y distribución por caso](MESA-003-persistir-pestanas-y-paneles.md)
- [MESA-011 · Agregar y editar centrales y embalses ejecutables](MESA-011-agregar-y-editar-activos-hidraulicos.md)
- [MESA-012 · Crear series manuales de apoyo y vincular entradas admitidas](MESA-012-crear-series-manuales.md)
- [MESA-013 · Recuperar ejecuciones y exportar la comparación](MESA-013-historial-y-exportacion.md)

## Validación TDD

Interfaces propuestas: Revisión humana de S1 y evidencia S1/S2/S3 de las entregas previas.

No reemplaza las pruebas de cada entrega por una gran suite al final. Revisar evidencia rojo → verde y comparar capturas expected/actual/diff de la implementación en entorno fijado.

Aplicar la [estrategia TDD](../validacion_tdd.md) y la definición de terminado del plan. Las interfaces S1/S2 y S3 condicional fueron confirmadas por el usuario el 2026-10-20; registrar en MESA-001 cualquier interfaz adicional antes de probarla. Cada ciclo implementa un solo comportamiento observable.

## Demostración de cierre

Sesión de validación con el usuario sobre un caso eléctrico y una red hidráulica, cubriendo la experiencia aceptada.

## Evidencia y seguimiento

- Inicio: pendiente.
- Evidencia rojo → verde / revisión HITL: pendiente.
- Pruebas y comandos ejecutados: pendiente.
- Capturas de implementación y diferencias revisadas: pendiente, cuando aplique.
- Decisiones o desviaciones respecto del plan: pendiente.
- Cierre y responsable: pendiente.
