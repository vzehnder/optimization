# PRD TS-5: Migracion, Unificacion Y Hardening

Fecha: 2026-07-03

## Grill-Me Questions And Recommended Answers

1. **Debe TS-5 migrar todo historico automaticamente?**

   Respuesta recomendada: no necesariamente. Debe definir que se migra, que se
   adapta y que queda como snapshot legacy valido.

2. **Deben seguir existiendo tablas especificas de series hidraulicas?**

   Respuesta recomendada: pueden seguir como compatibilidad temporal, pero las
   nuevas escrituras deberian ir al modelo generico.

3. **Debe eliminarse `ScenarioDraft`?**

   Respuesta recomendada: no como objetivo obligatorio. Debe revisarse si queda
   como compatibilidad o si su rol se reduce.

4. **Debe cambiar la cardinalidad `Scenario` -> `OptimizationCase`?**

   Respuesta recomendada: decidirlo aqui si no se cerro antes. Si varios casos
   por scenario aportan claridad, TS-5 es el momento de migrar constraints y UI.

5. **Como se protege auditoria durante migraciones?**

   Respuesta recomendada: nunca modificar snapshots historicos ejecutados.
   Cualquier extraccion hacia el modelo nuevo debe guardar metadata de origen.

6. **Que debe pasar con runs antiguos sin resultados BBDD?**

   Respuesta recomendada: deben seguir leyendose desde artifacts y ofrecer
   reconstruccion opcional hacia result series.

7. **Cuando se considera cerrado el cambio de arquitectura?**

   Respuesta recomendada: cuando las nuevas features escriben al modelo comun,
   lo legacy tiene adaptadores claros y la UI ya no mezcla conceptos.

## Problem Statement

Despues de TS-1 a TS-4, el sistema tendra una arquitectura nueva, pero tambien
seguiran existiendo caminos previos: drafts con datos embebidos, tablas
hidraulicas especificas, scenario versions historicas y artifacts antiguos. Sin
una iteracion de consolidacion, el producto quedaria con modelos paralelos para
lo mismo.

Eso aumentaria el costo de mantener validaciones, permisos, auditoria,
publicaciones y performance. TS-5 debe unificar la semantica y cerrar la
migracion con cuidado.

## Solution

Inventariar los caminos legacy, definir estrategias de migracion o adaptacion,
endurecer auditoria, permisos y stale validation, agregar herramientas de
reconstruccion y asegurar que las nuevas escrituras usen el modelo comun de
topologia, parametros, series y resultados.

## User Stories

1. As an analyst, I want old runs to remain readable, so that historical work is preserved.
2. As an analyst, I want old scenario versions to remain immutable, so that auditability is not broken.
3. As an analyst, I want legacy draft sources to be convertible to reusable time-series sets, so that old data can participate in the new workflow.
4. As an analyst, I want hydraulic time series to behave like generic series, so that hydrology is not a special UX island.
5. As an analyst, I want a clear deprecation path for old workflows, so that I know which path to use.
6. As an analyst, I want series edit history to remain available after migration, so that corrections are auditable.
7. As an analyst, I want result indexing rebuilds for old runs, so that comparisons can include historical results.
8. As an admin, I want permissions for input series, result series and publications to be consistent, so that clients see only intended data.
9. As an admin, I want cleanup and retention rules, so that the database does not grow without control.
10. As an analyst, I want stale validations to be reliable after migration, so that runs do not use outdated assumptions.
11. As an analyst, I want UI labels to distinguish case, topology, parameters, input variant and run, so that concepts are not confused.
12. As a backend developer, I want adapters for legacy reads, so that migration can be incremental.
13. As a backend developer, I want new writes routed to the common model, so that parallel systems stop growing.
14. As a backend developer, I want migration scripts or routines to be idempotent, so that local and PostgreSQL environments can be repaired safely.
15. As a backend developer, I want constraints and indexes reviewed, so that common queries remain fast.
16. As a backend developer, I want tests proving old and new flows coexist, so that hardening does not regress behavior.
17. As a product owner, I want a documented final architecture, so that future PRDs do not reopen settled decisions.

## Implementation Decisions

- Historical scenario versions are not rewritten.
- Legacy data may be adapted, migrated on demand or left as read-only depending on risk.
- New time-series writes should use the generic model after this iteration.
- New result writes should use the BBDD result model after this iteration.
- Existing hydraulic-specific series need a compatibility path and eventual write migration.
- Existing draft source data needs an extraction path into generic time-series sets.
- Permissions must account for input series, result series, sources and published outputs separately.
- Retention rules must distinguish audit snapshots from rebuildable derived indexes.
- Performance work should be based on real query patterns from TS-2 through TS-4.
- Deep modules should cover legacy extraction, adapter reads, rebuild routines, permission checks and cleanup decisions.

## Testing Decisions

- Migration tests should run idempotently against representative legacy fixtures.
- Compatibility tests should prove old scenario versions and runs still render.
- Adapter tests should prove hydraulic-specific series can be read through the common semantics.
- Extraction tests should prove draft source data can become generic time-series sets.
- Permission tests should cover internal analyst, admin and client visibility.
- Cleanup tests should prove derived data can be removed without deleting immutable audit artifacts.
- Performance guard tests should focus on query shapes rather than exact timing.

## Out of Scope

- New optimization math.
- Advanced transformations.
- External data connectors.
- Full automatic migration of every historical artifact.
- Removing all legacy tables immediately if adapters are safer.

## Further Notes

TS-5 is less glamorous but important. It turns the new architecture from a
feature path into the stable product baseline.
