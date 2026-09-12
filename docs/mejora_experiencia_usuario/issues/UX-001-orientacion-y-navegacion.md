# UX-001 · Orientación y navegación por tareas

Estado: In Review. Prioridad: P0. Dependencias: UX-000 (Done). Tamaño: M.

F1/F2 y F3 condicional confirmadas por el usuario el 2026-09-12.
[Acuerdo y evidencia de implementación](../evidencia/ux-001/README.md).

## Problema y resultado

Proyecto y escenario muestran numerosas tareas al mismo nivel. Una persona que retoma trabajo debe ver primero su contexto y un acceso claro al paso pendiente, manteniendo visibles las entradas a capacidades avanzadas.

## Código y contratos

- `frontend/src/App.tsx`: `AnalystRoot`, `AuthenticatedRoutes`, `LandingRedirect`.
- `frontend/src/Workspace.tsx`: `ProjectDetailView`, `ScenarioDetailView`, listas y breadcrumbs.
- `frontend/src/styles.css`; cliente público de proyecto, escenario, variantes y corridas en `api/client.ts`.
- Regresión: `ApplicationRoots.test.tsx`, `App.test.tsx`, `frontend/e2e/react-foundation.spec.ts`.

## Pasos de implementación

1. Cambiar las etiquetas de navegación a tareas según el diseño objetivo, sin alterar `landing_path`, permisos o raíces externas.
2. Añadir al escenario un resumen de contexto con accesos a Modelo, Datos, Ejecuciones y Avanzado. La acción de continuidad usa hechos disponibles del servidor; si falta información, muestra carga/reintento, no «listo» por defecto.
3. Organizar el proyecto en secciones que separen escenarios, datos e informes/accesos. Conservar el acceso a creación y borrado, templates, portal y consolas por escenario.
4. Mantener URLs actuales. Utilizar parámetros de sección o anchors validados para enlaces de retorno; conservar consultas existentes. Usar navegación semántica de enlaces, sin simular tabs ARIA si se trata de páginas.
5. Dejar JSON experto, versiones inmutables e hidráulica en destinos explícitos. Una sección cerrada no debe ser el único enlace a una función sin etiqueta descubrible.
6. Gestionar el foco al cambiar de pantalla y al volver; comprobar que la nueva navegación no evita la protección de cambios pendientes del editor.

## Secuencia TDD sugerida

Fronteras propuestas F1/F2, sujetas a UX-000. Ejecutar un ciclo antes de comenzar el siguiente:

1. RED: un analista abre un escenario sin modelo y puede seguir «Crear modelo» hasta el editor del mismo escenario. GREEN: resumen y enlace mínimos.
2. RED: un escenario existente permite entrar a ejecuciones y regresar con el mismo proyecto/escenario. GREEN: navegación local y retorno.
3. RED: al abrir Avanzado siguen disponibles JSON, versiones y diagrama hidráulico aplicable. GREEN: organización sin retirar capacidades.
4. RED si hay comportamiento nuevo: recarga/atrás conserva sección y un externo sigue recibiendo la entrada/restricción correspondiente. GREEN: ajustes de URL y guardas. Reusar los casos existentes de roles donde ya cubran el comportamiento.

## Aceptación y revisión

- Desde escenario se identifica el contexto y se alcanza Modelo, Datos o Ejecuciones con una acción de navegación.
- Se conservan enlaces directos `/scenarios/:id`, `/draft`, `/hydraulic-diagram`, `/scenario-versions/:id`, `/runs/:id` y sus redirects históricos.
- No se inventa estado «preparado» al fallar una consulta. Una sección no disponible explica cómo continuar.
- La identidad externa no recibe navegación interna; administración se muestra solo a admin.
- Teclado, foco, viewport estrecho y breadcrumbs se comprueban en navegador.

Entregar capturas de proyecto y escenario y las filas de paridad afectadas. La reorganización interna de `Workspace.tsx`, si conviene, se evalúa en revisión posterior; no es un requisito previo para empezar el ciclo TDD.

## Resolución

- Responsable: Codex. Inicio y revisión técnica: 2026-09-12.
- Estado: In Review; implementación local completa y pendiente de aceptación del resultado.
- PR o commits: `feat(ux): implement task-oriented workspace navigation`, sobre `aeeb22e`; sin PR creada. Capturas locales excluidas de Git por solicitud del usuario.
- Comportamiento: navegación por tareas, proyecto y escenario divididos en secciones, continuidad basada en la consulta del modelo, errores del historial locales, retorno contextual y foco al destino.
- Fronteras: F1/F2 y F3 condicional confirmadas por el usuario con «confirmo» antes de escribir pruebas nuevas.
- TDD: siete ciclos RED → GREEN registrados; prueba adicional de error/reintento que ya pasaba al añadirse, identificada como cobertura complementaria.
- Validación: 166 pruebas de componentes, 13 de navegador y 18 de API aprobadas. TypeScript, ESLint y formato de los archivos de código cambiados pasan. `npm.cmd run check` conserva un fallo de formato previo en 25 archivos ajenos al cambio.
- Revisión visual: proyecto y escenario a 1440 × 900, 1280 × 720 y 320 × 900; ampliación CSS al 200 %, teclado, foco, recarga e historial. Axe sin serious/critical en las nuevas vistas comprobadas.
- Paridad, comandos, salidas, capturas y límites: [evidencia de UX-001](../evidencia/ux-001/README.md).
- Documentación: guía del analista, manual completo, estrategia, validación y tracker actualizados.
- Aceptación del resultado: pendiente; la confirmación inicial habilitó las fronteras y cerró UX-000, no sustituye la revisión de esta implementación.
