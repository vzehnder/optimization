# PRD TS-4: Resultados En BBDD Y Series De Resultado

Fecha: 2026-07-03

## Grill-Me Questions And Recommended Answers

1. **Deben desaparecer los artifacts de corrida?**

   Respuesta recomendada: no. Los artifacts siguen siendo auditoria
   reproducible. La BBDD agrega consulta y comparacion.

2. **Debe guardarse todo `dispatch.csv` y `asset_dispatch.csv`?**

   Respuesta recomendada: inicialmente guardar las columnas que alimentan UI,
   graficos y comparacion, manteniendo artifacts completos como respaldo.

3. **Usamos `time_series_sets` tambien para resultados?**

   Respuesta recomendada: es preferible si el modelo generico soporta
   `data_kind = simulated` y lineage. Si complica permisos o performance, el
   PRD puede justificar `result_series_sets`.

4. **Cuando se escriben resultados a BBDD?**

   Respuesta recomendada: despues de un run exitoso y despues de registrar
   artifacts. Si falla la indexacion, el artifact queda como fuente para
   reconstruir.

5. **Debe la UI leer solo desde BBDD despues de esta iteracion?**

   Respuesta recomendada: no al inicio. Debe leer desde BBDD cuando exista
   indexacion y caer a artifacts para runs historicos.

6. **Que lineage minimo necesita un resultado?**

   Respuesta recomendada: run, snapshot ejecutable, caso, topologia, parametros,
   variante de input, rango y hashes/revisiones de series de entrada.

7. **Debe incluir comparacion de runs?**

   Respuesta recomendada: si, pero basica. Comparar dos runs del mismo caso con
   metricas y series principales.

## Problem Statement

Los resultados actuales son reproducibles porque se guardan artifacts, pero no
son faciles de consultar, comparar o publicar de forma granular. La UI lee
tablas y graficos desde archivos registrados. Eso funciona, pero limita el
analisis historico y la comparacion entre corridas con distintas variantes de
series.

Despues de TS-3, los runs tendran lineage rico de topologia, parametros,
variante y rango. TS-4 debe hacer que los resultados tambien vivan en BBDD como
series consultables, sin eliminar los artifacts.

## Solution

Al completar una corrida exitosa, indexar las principales salidas de
`dispatch.csv`, `asset_dispatch.csv` y `summary.json` en BBDD. Los resultados
deben quedar asociados al run y a todo su lineage. La UI debe poder leer tablas,
graficos y comparaciones desde BBDD cuando existan datos indexados, con fallback
a artifacts para compatibilidad.

## User Stories

1. As an analyst, I want run results stored in BBDD, so that I can query them without reading CSV files each time.
2. As an analyst, I want artifacts preserved, so that every run remains reproducible.
3. As an analyst, I want result series tied to the run, so that outputs have clear provenance.
4. As an analyst, I want result series tied to the input variant, so that I can compare assumptions.
5. As an analyst, I want result series tied to the date range, so that horizons are clear.
6. As an analyst, I want grid import and export stored as result series, so that grid behavior is comparable.
7. As an analyst, I want price and market value outputs stored, so that economics are inspectable.
8. As an analyst, I want BESS charge, discharge and energy stored, so that storage behavior can be reviewed.
9. As an analyst, I want renewable used and curtailed power stored, so that curtailment is visible.
10. As an analyst, I want hydro generation, flow, spill and storage stored, so that hydraulic behavior is visible.
11. As an analyst, I want asset-level rows indexed, so that I can inspect per-asset dispatch.
12. As an analyst, I want summary KPIs linked to result series, so that dashboards can load quickly.
13. As an analyst, I want old runs to still render from artifacts, so that historical data is not lost.
14. As an analyst, I want a rebuild action or tool, so that BBDD results can be regenerated from artifacts.
15. As an analyst, I want to compare two runs of the same case, so that I can see the effect of changing input variants.
16. As an analyst, I want comparison output to show differences in key KPIs, so that conclusions are quick.
17. As an analyst, I want comparison output to show period-level differences for selected series, so that details are inspectable.
18. As a backend developer, I want result ingestion isolated in a deep module, so that artifact parsing and BBDD writes are testable.
19. As a backend developer, I want idempotent result indexing, so that retrying after a partial failure is safe.
20. As a backend developer, I want lineage constraints, so that result records cannot drift from the run snapshot.
21. As a product owner, I want publications and dashboards to eventually use BBDD results, so that client views are faster and controllable.

## Implementation Decisions

- Artifacts remain the durable audit record.
- BBDD result series live in a dedicated run-result layer rooted at the run, not in the editable TS-2 `time_series_sets` catalog.
- Result indexing occurs after run success and artifact registration.
- Result indexing must be idempotent.
- The tracer-bullet indexed scope is core `dispatch.csv` only for the run results table; `asset_dispatch.csv`, `summary.json` and broader signal families land in downstream TS-4 slices.
- Run result endpoints prefer BBDD when indexed data exists for that surface and fall back to artifacts otherwise.
- Result records store lineage to run, execution snapshot, case, topology, parameters, input variant, date range and input series hashes, copied from the frozen run snapshot rather than live mutable state.
- A rebuild path can populate result series for historical successful runs.
- A basic comparison surface compares two runs from the same case.
- Deep modules should cover artifact parsing, result normalization, lineage construction, idempotent write and comparison.

## Testing Decisions

- Backend tests should prove successful run indexing from representative artifacts.
- Backend tests should prove idempotent re-indexing.
- Backend tests should prove fallback to artifacts for old runs.
- Backend tests should prove lineage metadata is present and consistent.
- Result API tests should verify tables and charts can be served from BBDD.
- Comparison tests should cover two runs with different variants or ranges.
- Publication/dashboard regression tests should ensure existing client views still work.
- Julia tests are required only if artifact formats change.

## Out of Scope

- Removing artifacts.
- Full BI or multi-run analytics.
- Saving every possible artifact column if not needed for UI.
- Reusing outputs as inputs, except as a future possibility.
- Transformations or resampling.
- Performance partitioning beyond reasonable indexes.

## Further Notes

This iteration makes outputs as queryable as inputs. It should be implemented
after variant-driven runs exist, because result lineage depends on that context.
