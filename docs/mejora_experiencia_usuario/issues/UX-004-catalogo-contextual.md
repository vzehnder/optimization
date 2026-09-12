# UX-004 · Encontrar y usar datos desde la necesidad del modelo

Estado: Todo. Prioridad: P1. Dependencias: UX-001. Tamaño: M.

## Problema y resultado

El catálogo ya es completo, pero exige interpretar tipos, alcances, contratos y revisiones fuera del contexto del componente. La persona debe poder partir de «Falta precio para la red» y llegar a una fuente compatible sin perder su lugar de trabajo.

## Código y contratos

- `frontend/src/GlobalCatalog.tsx`, `ObjectTimeSeriesSummary.tsx`, `ProtectedMutationJourney.tsx`, `journeyRoutes.ts`.
- `Workspace.tsx`: necesidades de variantes y catálogo por proyecto.
- Cliente: `listCatalogInputs`, `listCatalogSourcesForObject`, `getObjectTimeSeriesContext`, funciones de prevalidación/commit existentes.
- Backend: `time_series_catalog_read.py`, `time_series_associations.py`, `time_series_bindings.py`, `object_time_series.py` y rutas de `main.py`.
- Regresión: `GlobalCatalog.test.tsx`, `ObjectTimeSeriesSummary.test.tsx`, `ProtectedMutationJourney.test.tsx`, `tests/test_ts7_021_protected_journey_preconditions.py`.

## Pasos de implementación

1. En cada necesidad, mostrar componente, señal, fuente/revisión y estado. Crear enlaces a la superficie contextual existente con IDs validados y etiquetas del dominio.
2. Reutilizar los endpoints de candidatos/compatibilidad para sugerir fuentes. No descargar todo el catálogo para filtrar en memoria. Una incompatibilidad o ausencia se explica con la respuesta del servidor.
3. En catálogo general, mantener Buscar, Tipo y Unidad accesibles y agrupar el resto como «Más filtros», mostrando cuántos están activos. Todos los filtros actuales y el orden siguen disponibles.
4. Serializar filtros aplicados, inspector y contexto de retorno en URL con allowlist. Reiniciar el cursor al cambiar filtros; conservar cursores válidos para volver. Un cursor vencido permite volver al inicio sin perder filtros y con explicación.
5. Cambiar el título del recorrido según intención y mantener su contexto lateral, cuatro pasos y confirmación. El paso final explica objeto, alcance, fuente/revisión, usos afectados y el cambio que se está confirmando.
6. Distinguir asociación al objeto y uso fijado en variante. Tras asociar, informar si todavía falta fijar el uso; no afirmar «listo para ejecutar» antes de validar la variante y el rango.
7. Mantener creación específica, ingesta, archivo, cambio compartido, derivación local y cambios administrativos de alcance. Los detalles técnicos pueden contraerse en lectura; las decisiones de impacto siguen visibles al confirmar.
8. Volver al objeto/escenario con filtros y selección contextual. Validar el destino como ruta interna permitida; no permitir redirects arbitrarios.

## Secuencia TDD sugerida

F1/F2 propuestas; F3 si se amplía contrato:

1. RED: desde una necesidad de precio, abrir fuentes candidatas con el objeto y unidad visibles; la selección refleja lo que respondió el backend. GREEN: primer enlace y consulta contextual.
2. RED: inspeccionar una fuente, volver y recargar conserva filtros aplicados sin pérdida de contexto. GREEN: URL y navegación.
3. RED: asociar requiere los cuatro pasos y muestra el efecto; completar asociación no anuncia que el binding de la variante ya fue creado. GREEN: lenguaje y retorno.
4. RED: una prevalidación vencida al confirmar conserva la selección, informa el conflicto y exige revisar de nuevo. GREEN: recuperación segura.

Reusar las pruebas de no-mutación al explorar, cursores y límites de preview; no reemplazarlas por tests de estructura del inspector.

## Aceptación

- La búsqueda general sigue siendo accesible, además de la contextual.
- No se actualiza una fuente compartida ni se fija la revisión actual automáticamente al explorar.
- Las mutaciones canónicas conservan el único recorrido protegido y sus precondiciones.
- Lectura canónica deshabilitada conserva el comportamiento compatible y no muestra enlaces muertos a rutas ocultas.
- El catálogo sigue paginado por el servidor y los previews acotados explican sus límites.
- Todas las funciones de Datos avanzado de la matriz permanecen alcanzables.

No eliminar adaptadores legacy bajo este ticket. La revisión posterior puede compartir utilidades de URL pequeñas; no crear un router paralelo.
