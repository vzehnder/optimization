# UX-006 · Mostrar primero resultados y facilitar la comparación

Estado: In Review. Prioridad: P0. Dependencias: UX-001. Tamaño: M.

Preparación del 2026-09-12 sobre `61dc87a`: lectura del paquete y 130 regresiones
existentes aprobadas. [Acuerdo F1/F2, ciclos y resultados](../evidencia/ux-006/README.md).
F1/F2 confirmadas por el usuario con «confirmo» antes de la primera prueba nueva.

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

F1/F2 confirmadas para este alcance:

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

## Resolución

- Responsable: Codex. Inicio y entrega para revisión: 2026-09-12.
- Estado final: In Review; aceptación de producto pendiente.
- Commit: `feat(ux): prioritize results and contextual run comparison`, sobre
  `61dc87a`, solicitado por el usuario. Sin PR.
- Implementación: resultado y acciones antes de auditoría; estados en español,
  KPIs con unidades, resumen completo, diagnóstico con foco, tablas paginadas,
  reintentos y comparación contextual con selección validada en URL.
- Compatibilidad: API conserva autoridad sobre caso e indexación. Los rangos
  distintos muestran advertencia y los valores ausentes no se convierten a cero.
- Fronteras: usuario confirmó F1/F2 con «confirmo» antes de la primera prueba.
  F3 solo regresiones existentes; F4 no aplica.
- Evidencia: [ciclos RED → GREEN, paridad, capturas y comandos](../evidencia/ux-006/README.md).
  273 pruebas aprobadas: 195 componentes, 15 navegador y 63 Python.
- Revisión visual: resultado en 1280×720, 1440×900, 320×900 y ampliación CSS al
  200 %; comparación a 1280 y 320; fallo a 1280; teclado y axe sin serious/critical
  en las tres vistas comprobadas. Capturas locales regenerables, excluidas de Git.
- Conservación: polling/logs, KPIs/gráficos/tablas/archivos, snapshot/linaje y
  comparación; publicaciones y portal allowlisted cubiertos por la regresión.
- Límites: `npm.cmd run check` falla por formato previo en 23 archivos ajenos;
  TypeScript, ESLint y formato modificado pasan. Sin Julia real, PostgreSQL,
  suite Python completa ni estudio de usabilidad con participantes.
- Tutoriales actualizados; no hay cambios en APIs ni datos históricos.
- Persona que acepta: pendiente de revisión del usuario.
