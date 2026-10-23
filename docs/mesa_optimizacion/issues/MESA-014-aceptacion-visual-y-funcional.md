# MESA-014 · Validar la mesa completa y habilitar su acceso en el producto

Status: In Review
Type: HITL
Triage: ready-for-agent
Assignee: Codex
Source: [Plan de implementación](../plan_implementacion.md)
User stories covered: HU-01, HU-02, HU-03, HU-04, HU-05, HU-06, HU-07, HU-08, HU-09, HU-10, HU-11

## What to build

Realizar la aceptación del recorrido completo, con datos reales de prueba y las capturas del prototipo como referencia de intención visual. Revisar las diferencias justificadas, aprobar la baseline de regresión de la implementación y habilitar su acceso según el mecanismo del producto, preservando los recorridos anteriores.

## Acceptance criteria

- [x] Demostrar desde la mesa: abrir caso, configurar cuatro vistas, editar, guardar, elegir período, ejecutar, comparar y recuperar una corrida.
- [x] Demostrar componente hidráulico nuevo y serie manual de apoyo/vinculada, con sus validaciones reales.
- [ ] Contrastar estado inicial y comparación mixta gráfico/tabla con los dos PNG de referencia a 1440×900; registrar diferencias aceptadas.
- [x] Verificar teclado, foco de diálogos/pestañas, unidades/leyendas legibles y adaptación a 390 px sin scroll horizontal global.
- [x] Revisar carga, vacío, conflicto, fallo de ejecución, pérdida de conexión y preparación obsoleta sin resultados inventados.
- [ ] Recibir conformidad del usuario sobre la experiencia implementada y registrar cualquier ajuste antes de marcar Done.
- [ ] Establecer baselines Playwright de la implementación solo tras la revisión; conservar la referencia original sin sobrescribirla.
- [x] Registrar pruebas/regresiones pertinentes, actualizar ayuda y tracker, y habilitar acceso sin eliminar las rutas existentes ni desplegar fuera de lo autorizado.

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

- Inicio: 2026-10-21, por instrucción del usuario de ejecutar la siguiente issue. Dependencias Done; S1/S2 ya confirmadas. Se preservan los cambios locales previos.
- Evidencia: [seis ciclos TDD, recorridos, capturas y diferencias propuestas](../evidencia/MESA-014/validacion.md). Revisión técnica completada; conformidad HITL pendiente.
- Pruebas: 139 Python distintas verificadas, 336 Vitest, 53 MESA y cinco regresiones generales. Cinco pruebas Python con Julia pasaron al repetir fuera del sandbox. Revisión visual final 4/4 y recorrido eléctrico ampliado 1/1 con Julia real después del ajuste geométrico. PostgreSQL no verificado; Prettier global mantiene 16 archivos ajenos pendientes.
- Implementación: ayuda contextual y [guía de usuario](../guia_usuario.md), cierre visible en móvil, cabecera y matrices con avance completado sin recortar procedencia. Acceso existente desde escenario y versión hidráulica verificado. Runner general separado del servidor MESA y movimiento reducido configurado correctamente.
- Capturas: 1440×900 y 390 px, referencias originales intactas. El contraste técnico está hecho; se deja sin marcar el tercer criterio porque incluye aceptar las diferencias. Se proponen fixtures mínimos de dos intervalos, navegación React y procedencia real en lugar de los datos/KPI ficticios del prototipo.
- Baseline: configuración reproducible preparada en `frontend/playwright.mesa.visual.config.ts`, sin expected aprobado ni actualización automática. Se fijará únicamente después de la conformidad sobre estas capturas.
- Estado: **In Review**, Codex, 2026-10-21. No se marca Done ni se atribuye aprobación al usuario. Sin publicación ni despliegue.
