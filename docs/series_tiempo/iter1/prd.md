# PRD TS-1: Jerarquias De Topologia Y Parametros

Fecha: 2026-07-03

## Grill-Me Questions And Recommended Answers

1. **Debe `ScenarioVersion` seguir siendo el objeto que el analista elige para trabajar?**

   Respuesta recomendada: no. `ScenarioVersion` debe seguir existiendo como
   snapshot inmutable ejecutable, pero la UI debe orientar al analista alrededor
   del `OptimizationCase`. La version ejecutable se deriva del caso, no es la
   superficie principal de edicion.

2. **Que es topologia en este producto?**

   Respuesta recomendada: la estructura de componentes y conexiones. En one-bus
   incluye PCC, grid, BESS, renovables, cargas y activos hidraulicos simples. En
   hidro de diagrama incluye nodos hidraulicos, tramos, centrales, unidades y
   relaciones intake/discharge. El layout visual no es topologia fisica.

3. **Que es parametro y que no debe quedar dentro de topologia?**

   Respuesta recomendada: los parametros son hipotesis operacionales o
   economicas usadas para correr una topologia: limites, estados iniciales,
   eficiencias, costos, penalizaciones, curvas seleccionadas, restricciones y
   solver settings. Si un valor puede cambiar en una sensibilidad sin cambiar la
   estructura, debe vivir en parametros.

4. **Las curvas son topologia o parametros?**

   Respuesta recomendada: la existencia de que una entidad requiere cierta curva
   pertenece al contrato/topologia del modelo; la version concreta de la curva
   usada para correr pertenece a parametros. Esto permite correr la misma
   topologia con otra curva versionada.

5. **Debe permitirse mas de un `OptimizationCase` por `Scenario` desde esta iteracion?**

   Respuesta recomendada: el PRD debe dejar preparada la semantica, pero la
   implementacion inicial puede mantener la cardinalidad actual si cambiarla
   aumenta demasiado el alcance. Lo importante es no seguir usando `Scenario`
   como sinonimo conceptual de caso ejecutable.

6. **Debe esta iteracion migrar todas las pantallas existentes?**

   Respuesta recomendada: no. Debe preservar los flujos existentes y agregar
   metadata/adaptadores que distingan topologia y parametros. La migracion
   completa puede quedar para TS-5.

7. **Que pasa con un snapshot validado si cambia la topologia o parametros?**

   Respuesta recomendada: queda stale. Cualquier cambio material de topologia o
   parametros debe invalidar la validacion vigente y bloquear promocion o run
   hasta revalidar.

8. **Cual es el minimo resultado valioso de TS-1?**

   Respuesta recomendada: poder generar el mismo `system_case_json` que hoy,
   pero con provenance clara: que topologia y que version de parametros lo
   produjeron.

## Problem Statement

El flujo actual permite crear drafts, validar `system_case_json`, promover
`ScenarioVersion` inmutables y ejecutar runs. Ese modelo es auditable, pero
mezcla conceptos que el analista necesita separar: estructura del sistema,
parametros operacionales y datos temporales. En especial, `ScenarioVersion`
congela todo junto y se vuelve el unico objeto claro de versionado, aunque el
usuario normalmente quiere reutilizar la misma topologia con distintos
parametros o series.

La falta de separacion dificulta el siguiente objetivo del producto: elegir
versiones de series de tiempo desde un dropdown y correr sin duplicar el caso
completo. Antes de modelar series como inputs intercambiables, el sistema debe
distinguir que parte del caso es topologia y que parte son parametros.

## Solution

Introducir una jerarquia explicita dentro del `OptimizationCase`:

```text
OptimizationCase
-> TopologyVersion
-> CaseParameterVersion
-> ScenarioVersion / execution snapshot
```

La topologia define estructura y conectividad. La version de parametros define
los valores ejecutables usados sobre esa topologia. La `ScenarioVersion` sigue
siendo el snapshot inmutable que Julia valida y ejecuta, pero se genera desde
topologia + parametros y registra esa procedencia.

La implementacion debe ser conservadora: mantener los flujos existentes verdes,
no reemplazar todavia la ingesta de series ni resultados, y enfocar la iteracion
en corregir el modelo conceptual y el lineage de snapshots.

## User Stories

1. As an analyst, I want a case to distinguish topology from parameters, so that I can understand what changed between model alternatives.
2. As an analyst, I want topology to represent components and connectivity, so that structural changes are separated from input data changes.
3. As an analyst, I want parameters to represent limits, states, costs and solver settings, so that I can vary operational assumptions without copying topology.
4. As an analyst, I want the same topology to support different parameter versions, so that sensitivities are easy to manage.
5. As an analyst, I want generated execution snapshots to record their topology version, so that runs can be traced to structure.
6. As an analyst, I want generated execution snapshots to record their parameter version, so that runs can be traced to assumptions.
7. As an analyst, I want prior `ScenarioVersion` records to remain immutable, so that existing run auditability is preserved.
8. As an analyst, I want current structured draft and hydraulic diagram workflows to keep working, so that this refactor does not block model creation.
9. As an analyst, I want stale validation warnings after topology edits, so that I do not promote outdated snapshots.
10. As an analyst, I want stale validation warnings after parameter edits, so that I do not run with old assumptions.
11. As an analyst, I want topology metadata visible in case or version details, so that I can inspect provenance without opening raw JSON.
12. As an analyst, I want parameter metadata visible in case or version details, so that I can compare alternatives.
13. As an analyst, I want layout-only edits not to create a new physical topology, so that visual organization does not pollute model history.
14. As an analyst, I want structural edits to invalidate topology validation, so that invalid connectivity cannot be executed.
15. As an analyst, I want curve version selection to be treated as parameterization, so that I can test alternate curves over the same asset.
16. As a backend developer, I want topology and parameter generation encapsulated in deep modules, so that `system_case_json` generation remains testable.
17. As a backend developer, I want compatibility adapters for current draft and hydraulic data, so that existing flows do not need a big-bang migration.
18. As a backend developer, I want execution snapshots to include topology and parameter hashes, so that stale checks are deterministic.
19. As a backend developer, I want old runs to continue resolving through their existing scenario versions, so that historical data remains readable.
20. As a product owner, I want the new hierarchy introduced before generic time-series variants, so that later work has a stable foundation.

## Implementation Decisions

- `OptimizationCase` becomes the main editable modeling object for this area.
- `ScenarioVersion` remains the immutable executable snapshot and continues to be the object a `Run` references.
- A topology version represents structural model state, including components, graph connectivity and hydraulic topology where applicable.
- A parameter version represents executable assumptions over a topology, including scalar limits, initial states, selected curve versions, costs, penalties, constraints and solver settings.
- Layout metadata remains separate from topology unless the user changes actual connectivity or component membership.
- The first implementation may use tables, metadata adapters or hybrid persistence if that is safer than a full migration.
- The generation path must produce the same effective `system_case_json` accepted by the current Julia contracts.
- Existing `ScenarioDraft` and hydraulic diagram flows must continue to validate, promote and run.
- Validation snapshots must become stale when topology or parameter content hashes change.
- Execution snapshots must record topology and parameter provenance in machine-readable metadata.
- Deep modules should encapsulate topology normalization, parameter normalization, stale detection and `system_case_json` generation.

## Testing Decisions

- Tests should focus on externally visible behavior: generation equivalence, provenance, stale validation and preserved run flow.
- Existing web acceptance tests for drafts, hydraulic diagrams, manual runs and scenario versions remain regression guards.
- New backend tests should prove that the same case generates the same `system_case_json` through the hierarchy.
- New backend tests should prove that topology edits and parameter edits independently mark validations stale.
- React tests should verify provenance display and stale-state presentation without depending on implementation details.
- Julia tests are required only if the generated contract or optimizer behavior changes; otherwise current Julia regression can be run as a guard.

## Out of Scope

- Generic time-series storage in BBDD.
- Input series variants and dropdown-driven runs.
- Result series in BBDD.
- Resampling, interpolation or transformations.
- Full migration away from `ScenarioDraft`.
- Client-facing changes beyond preserving existing publication behavior.

## Further Notes

This iteration is primarily architectural and semantic. It should not try to
deliver the full dropdown series workflow. Its success is measured by whether
future iterations can attach time-series variants to a stable case hierarchy
without duplicating topology or parameters.
