# UX-001 · Orientación y navegación por tareas

Estado: Todo. Prioridad: P0. Dependencias: UX-000. Tamaño: M.

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
