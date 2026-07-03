# PRD TS-3: Variantes De Series Por Caso, Default Y Rango De Fechas

Fecha: 2026-07-03

## Grill-Me Questions And Recommended Answers

1. **Debe el dropdown seleccionar sets de series o variantes?**

   Respuesta recomendada: variantes. Un set es una pieza de datos; una variante
   es la combinacion coherente de todos los sets que el caso necesita.

2. **Debe cada caso tener una variante default?**

   Respuesta recomendada: si. Sin default, el flujo de correr se vuelve
   demasiado manual.

3. **Debe una variante copiar valores de series?**

   Respuesta recomendada: no. Debe guardar bindings a sets/senales/revisiones y
   congelar hashes solo al validar o correr.

4. **El rango de fechas pertenece a la variante?**

   Respuesta recomendada: no. La variante define que series usar. El rango se
   elige al correr y queda congelado en el snapshot ejecutable.

5. **Debe haber resampling automatico si los periodos no calzan?**

   Respuesta recomendada: no en TS-3. Los horizontes deben calzar exactamente
   para evitar comportamiento implicito.

6. **Debe el usuario seguir creando `ScenarioVersion` manualmente?**

   Respuesta recomendada: no como paso principal. Al correr, el sistema puede
   crear automaticamente el snapshot tecnico necesario.

7. **Que pasa si cambia un set despues de validar una variante?**

   Respuesta recomendada: la variante queda stale porque el hash/revision
   vigente ya no coincide con el validado.

8. **Debe clonarse una variante existente para crear otra?**

   Respuesta recomendada: si. Clonar default y cambiar solo algunos bindings es
   la UX mas eficiente.

## Problem Statement

El usuario quiere abrir un caso, seleccionar una version de series desde un
dropdown, elegir un rango de fechas y correr. Actualmente, cambiar series suele
implicar generar otro `system_case_json` completo y otra `ScenarioVersion`, lo
que mezcla datos temporales con topologia y parametros.

Con TS-1 y TS-2, el sistema ya debe distinguir topologia/parametros y tener
series en BBDD. Falta unir estas piezas en una experiencia de caso: variantes
de entrada, default, validacion de cobertura temporal y ejecucion con rango.

## Solution

Crear variantes de input por `OptimizationCase`. Cada variante contiene
bindings desde senales requeridas del caso hacia `TimeSeriesSet` y
`TimeSeriesSignal`. El caso tiene una variante default y la UI permite elegir
otra variante desde un dropdown antes de correr.

Al correr, el usuario elige un rango de fechas. El backend valida que todos los
bindings requeridos cubren el rango con periodos compatibles, materializa el
`system_case_json` desde topologia + parametros + variante + rango y crea un
snapshot tecnico inmutable para el `Run`.

## User Stories

1. As an analyst, I want every case to have a default input variant, so that I can run common cases quickly.
2. As an analyst, I want to create a new input variant by cloning an existing one, so that I only change the differing series.
3. As an analyst, I want a dropdown of variants inside the case, so that I can switch scenarios without duplicating topology.
4. As an analyst, I want a variant to bind required price signals, so that grid economics are complete.
5. As an analyst, I want a variant to bind load demand signals, so that demand can change independently of the case.
6. As an analyst, I want a variant to bind renewable availability signals, so that solar or wind profiles can vary.
7. As an analyst, I want a variant to bind hydraulic inflow signals, so that hydrology scenarios can be swapped.
8. As an analyst, I want a variant to bind reach minimum-flow signals when required, so that environmental constraints can vary.
9. As an analyst, I want to see missing required bindings, so that incomplete variants are obvious.
10. As an analyst, I want to select a run date range, so that a large dataset can be sliced for a specific optimization horizon.
11. As an analyst, I want range coverage validation, so that missing dates are caught before Julia runs.
12. As an analyst, I want exact horizon compatibility validation, so that mixed resolutions fail clearly.
13. As an analyst, I want a stale marker when a bound series changes, so that I know to revalidate.
14. As an analyst, I want a stale marker when topology or parameters change, so that variants reflect the current case requirements.
15. As an analyst, I want to run the same case with two variants, so that I can compare data assumptions.
16. As an analyst, I want run detail to show selected variant and date range, so that provenance is clear.
17. As an analyst, I want run detail to show exact input series revisions and hashes, so that data lineage is auditable.
18. As an analyst, I want the generated snapshot hidden unless I need details, so that the normal workflow stays simple.
19. As a backend developer, I want variant validation isolated in a deep module, so that binding and horizon logic is testable.
20. As a backend developer, I want snapshot generation isolated from routes, so that runs from variants can be tested.
21. As a backend developer, I want old scenario-version run APIs preserved, so that legacy execution remains available.
22. As a product owner, I want this iteration to prove the core new workflow, so that later result storage builds on real runs.

## Implementation Decisions

- `InputSeriesVariant` is the user-facing selection for time-series assumptions.
- An `OptimizationCase` has one default input variant.
- Variants store bindings, not copied time-series values.
- Bindings resolve required case signals to time-series sets/signals.
- Date range is selected at run time and stored in the execution snapshot.
- TS-3 requires exact period compatibility; no implicit resampling.
- Validation records input set revisions and hashes.
- A stale state is shown when series, topology or parameters change after validation.
- Running from a variant creates or reuses a technical immutable snapshot compatible with current run infrastructure.
- Run lineage includes topology version, parameter version, input variant, date range and input series hashes.
- Deep modules should cover required-signal discovery, binding resolution, horizon slicing, validation and snapshot generation.

## Testing Decisions

- Backend tests should prove default variant creation and clone behavior.
- Backend tests should prove missing binding errors per required signal.
- Backend tests should prove horizon/range validation for complete, incomplete and mismatched periods.
- Backend tests should prove stale detection when a time-series hash changes.
- End-to-end tests should run the same case with two variants and confirm distinct snapshots.
- React tests should cover dropdown selection, date range inputs, validation states and run submission.
- Existing manual-run and scenario-version tests remain regression guards.
- Julia tests are needed only if generated contracts change; otherwise generated payload validation is enough.

## Out of Scope

- Creating the generic series catalog itself.
- Result series in BBDD.
- Resampling, interpolation or mixed-resolution execution.
- Advanced comparison UI.
- Scheduled runs.
- Client-facing variant editing.

## Further Notes

This is the central UX iteration. It is complete when an analyst can run a case
with different data versions from a dropdown and a date range, without copying
topology or parameters.
