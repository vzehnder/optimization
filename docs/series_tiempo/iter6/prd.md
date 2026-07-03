# PRD TS-6: Transformaciones Y Automatizacion De Series

Fecha: 2026-07-03

## Grill-Me Questions And Recommended Answers

1. **Debe TS-6 implementarse inmediatamente despues de TS-5?**

   Respuesta recomendada: no necesariamente. Debe activarse cuando haya uso real
   suficiente para saber que transformaciones valen la pena.

2. **Deben permitirse scripts libres guardados en BBDD?**

   Respuesta recomendada: no. Las transformaciones deben ser declarativas y
   allowlisted.

3. **Una transformacion modifica el set origen?**

   Respuesta recomendada: no. Produce un nuevo set o revision derivada con
   lineage hacia inputs, parametros y version de implementacion.

4. **Debe el run hacer resampling implicito si faltan datos?**

   Respuesta recomendada: no. Las transformaciones deben ejecutarse antes y
   producir una version explicita que luego se selecciona.

5. **Los conectores externos cambian el modelo de datos?**

   Respuesta recomendada: no. Una API externa debe ingresar como
   `TimeSeriesSource` y producir `TimeSeriesSet`, igual que un archivo.

6. **La automatizacion debe correr JSONs o casos + variantes?**

   Respuesta recomendada: casos + versiones de parametros + variantes + rango.
   El JSON sigue siendo snapshot generado, no la configuracion principal.

7. **Debe incluir TimescaleDB desde el principio?**

   Respuesta recomendada: solo si el volumen real lo exige. El modelo logico no
   debe depender de una optimizacion fisica prematura.

## Problem Statement

Una vez que las series viven en BBDD, se seleccionan por variantes y los
resultados son consultables, apareceran necesidades avanzadas: resampling,
interpolacion, combinacion de escenarios, ingestion automatica de forecasts,
programas externos, rolling horizon y reruns programados.

Implementar estas capacidades antes de validar el modelo base puede generar
sobrediseno. TS-6 las agrupa como una iteracion futura, basada en patrones de
uso reales.

## Solution

Agregar una capa de transformaciones declarativas y automatizacion. Las
transformaciones toman uno o mas sets de entrada, parametros validados y una
version de implementacion allowlisted, y producen un nuevo set o revision con
lineage completo. La automatizacion corre casos usando topologia, parametros,
variante de input y rango, generando snapshots ejecutables igual que el flujo
manual.

## User Stories

1. As an analyst, I want to resample a time-series set, so that I can align data to an optimization resolution.
2. As an analyst, I want to interpolate small gaps explicitly, so that missing data handling is auditable.
3. As an analyst, I want to scale a signal, so that I can create sensitivities such as high demand.
4. As an analyst, I want to combine series from multiple sets, so that scenarios can be composed.
5. As an analyst, I want derived sets to show lineage, so that I know what source data and transformation produced them.
6. As an analyst, I want transformation parameters visible, so that derived data is explainable.
7. As an analyst, I want stale derived sets when source data changes, so that I know they need regeneration.
8. As an analyst, I want to regenerate a derived set, so that updated inputs can flow forward.
9. As an analyst, I want forecast data ingested into the same catalog, so that external data uses the same workflow.
10. As an analyst, I want programmed external data to store issuer and validity, so that official schedules are traceable.
11. As an analyst, I want scheduled reruns to use variants and date ranges, so that automation matches manual semantics.
12. As an analyst, I want rolling-horizon runs to generate auditable snapshots, so that automation remains reproducible.
13. As an analyst, I want automated run results indexed in BBDD, so that they can be compared like manual runs.
14. As an admin, I want allowlisted transformation types, so that arbitrary code is not stored or executed from BBDD.
15. As a backend developer, I want transformation implementations versioned, so that derived data can be traced to code behavior.
16. As a backend developer, I want transformation parameter schemas versioned, so that old derived sets remain interpretable.
17. As a backend developer, I want connector ingestion isolated from core series logic, so that external APIs are replaceable.
18. As a product owner, I want TS-6 delayed until real usage justifies it, so that the product does not overbuild early.

## Implementation Decisions

- Transformations are explicit, declarative and versioned.
- No arbitrary user-provided scripts are stored as executable transformations.
- Each transformation has a type, implementation version, parameter schema version and validated parameters.
- Transformations produce new sets or revisions; they do not mutate source sets silently.
- Derived sets store lineage to input sets, input revisions, transformation parameters and implementation version.
- Source changes mark derived outputs stale or require regeneration.
- External connectors write through the same source/set model used by files.
- Scheduled runs use cases, parameter versions, input variants and date ranges, not hand-authored JSON.
- Physical storage optimizations such as partitioning or TimescaleDB are considered only after measuring real volume.
- Deep modules should cover transformation validation, execution, lineage, stale detection, connector ingestion and scheduled run planning.

## Testing Decisions

- Transformation tests should cover each allowlisted transformation as a pure/deep module.
- Lineage tests should prove derived sets record inputs, revisions, parameters and implementation version.
- Stale tests should prove source changes affect derived outputs.
- Connector tests should use mocked external data and assert common source/set creation.
- Scheduled run tests should prove automation creates the same kind of snapshots as manual runs.
- Regression tests should ensure manual variant-driven runs still work.
- Performance tests should be added only for measured bottlenecks or realistic volumes.

## Out of Scope

- Implementing every possible transformation type upfront.
- Arbitrary Python, Julia or SQL scripts as user-defined transformations.
- Replacing manual run flows.
- Real-time SCADA or control.
- Optimizer changes not required by transformed inputs.
- Mandatory TimescaleDB adoption.

## Further Notes

TS-6 should be treated as future work until the core architecture has been used
with real datasets. Its value is high, but only after the product can already
load, version, select, run and index time-series data reliably.
