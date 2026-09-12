# UX-006 · Mostrar primero resultados y facilitar la comparación

Estado: Todo. Prioridad: P0. Dependencias: UX-001. Tamaño: M.

## Problema y resultado

La corrida muestra numerosas secciones de auditoría antes de KPIs/gráficos. La persona debe conocer el estado y resultado inmediatamente, con acceso claro al detalle técnico y a la comparación.

## Código y contratos

- `frontend/src/Workspace.tsx`: `RunDetailView`, `RunMetadata`, `RunFailureDetails`, `RunComparisonView`, `PublicationSection`.
- `frontend/src/RunResults.tsx`, `plotly.ts`, `CaseHierarchyProvenance.tsx`.
- `app/results.py`, `app/result_comparison.py`, `app/result_indexing.py`; APIs existentes de resultados, comparación y artefactos.
- Regresión: `App.test.tsx`, `frontend/e2e/react-foundation.spec.ts`, `tests/test_results_review.py`, `tests/test_manual_runs.py`, `tests/test_ts4_run_comparison.py`.

## Pasos de implementación

1. Reordenar detalle: identidad/período/estado → resultado o explicación del fallo → acciones de comparar/informe → datos detallados y auditoría. Reusar las secciones existentes.
2. Traducir estados y etiquetas de UI, conservando valor técnico visible en auditoría. No inventar porcentaje de avance ni tiempo restante para cola/solver.
3. Mostrar KPIs aplicables al tipo de resultado con unidades y formato legible. Conservar el resumen completo consultable; `null`, no disponible y cero se presentan de forma distinta.
4. Agrupar procedencia, entradas, versión, hashes, logs y snapshot en «Detalle técnico y auditoría». Mantener links y descargas para internos. Un fallo relevante debe explicarse arriba aunque su log esté contraído.
5. Conservar paginación de tablas y lifecycle de Plotly al abrir/cerrar paneles. Reintentar consultas fallidas sin ocultar un resultado ya aceptado ni reenviar la ejecución.
6. Desde una corrida, enlazar a comparación con ella preseleccionada y permitir elegir una segunda compatible. La API decide compatibilidad; mostrar nombres, variante, rango y unidades de ambas antes de interpretar diferencias.
7. Conservar comparación sin datos, columnas legacy ausentes, resultados por activo/hidro y fallback a artefactos. No agregar exportaciones nuevas como requisito de este ticket.

## Secuencia TDD sugerida

F1/F2 propuestas:

1. RED: abrir una corrida exitosa y consultar su KPI conocido y período desde el resumen; abrir auditoría permite acceder a su snapshot. GREEN: primera reorganización completa.
2. RED: una corrida en curso pasa a finalizada tras polling y un fallo temporal de consulta permite recuperación, sin lanzar otra corrida. GREEN: estados/reintento.
3. RED: abrir comparación desde una corrida conserva la base elegida, muestra diferencia conocida y permite volver a ambas. GREEN: contexto y preselección.
4. RED: resultado legacy sin una señal explica la ausencia y mantiene el resto de gráficos y descargas; no inventa cero. GREEN: tratamiento de ausencia.

La posición por encima del pliegue se revisa visualmente, no con un test que cuente índices de nodos DOM. Una diferencia numérica esperada viene del fixture independiente, no de recomputar con la función comparadora.

## Aceptación

- En 1280×720 se identifica el estado y comienza el resumen de resultados sin atravesar auditoría.
- Gráficos, tablas, resumen completo y todos los artefactos antes disponibles siguen accesibles.
- La comparación no mezcla casos/rangos incompatibles silenciosamente y mantiene unidades.
- Un resultado faltante, consulta fallida y corrida fallida se explican como condiciones distintas.
- El portal/console no reciben los componentes internos que imprimen JSON o logs. Se mantiene su render allowlisted existente.

Entregar capturas de éxito, fallo y comparación, más regresiones aplicables. Refactorizaciones de render se valoran en revisión posterior.
