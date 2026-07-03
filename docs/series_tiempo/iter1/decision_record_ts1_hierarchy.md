# TS-1 Hierarchy Semantics Decision Record

Fecha: 2026-07-03
Status: Accepted
Issue: `BESS-TS1-000`

## Context Reviewed

This decision was reviewed against the current `docs/` product context:

- final one-bus optimization objective;
- Iteration 3 through 6 analyst, structured editor, hydro and publication flows;
- React migration plan and current React-only UI direction;
- hydro diagram PRD, database extension and DB checkpoint;
- central database proposal for components, parameters, hydraulic objects and
  versioned time series;
- TS roadmap, TS-1 PRD and downstream TS-2 through TS-6 PRDs.

## Accepted Decisions

1. `OptimizationCase` is the main editable modeling object for TS-1 semantics.
   `Scenario` remains a project-level work branch or container, not the precise
   executable case concept.
2. `ScenarioVersion` remains the immutable executable snapshot. Runs continue
   to reference scenario versions, not mutable cases, topology records,
   parameter records or drafts.
3. Topology means physical/logical structure: component membership,
   one-bus connectivity and, for hydraulic diagram cases, active hydraulic
   nodes, reaches, plants, units and their intake/discharge relationships.
   Layout-only state is not physical topology.
4. Parameters mean executable assumptions over a topology: limits, initial
   states, efficiencies, costs, penalties, terminal settings, active
   constraints, solver settings and selected curve versions.
5. Curve treatment is accepted as split semantics: the fact that an entity
   requires a curve belongs to the model/topology contract, while the concrete
   curve version selected for a run belongs to the parameter version.
6. TS-1 does not change `Scenario -> OptimizationCase` cardinality. The current
   implementation can keep the existing one-case-per-scenario shape where that
   is safest. Multiple cases per scenario remain deferred until a later
   migration/hardening slice, likely TS-5 if product value justifies it.
7. TS-1 should be implemented conservatively with metadata/adapters or nullable
   persistence where useful. It must not force a big-bang migration away from
   `ScenarioDraft`, hydraulic diagram persistence or existing scenario version
   records.
8. New execution snapshots should record machine-readable topology and
   parameter provenance, including stable hashes or revisions suitable for
   stale checks. Old scenario versions without this metadata remain valid and
   loadable.
9. A validated snapshot becomes stale when material topology or parameter
   content changes. Layout-only edits must not stale physical validation.
10. Existing structured draft, paste/upload JSON, hydraulic diagram, manual run,
    artifact, result and publication flows must remain compatible through TS-1.
11. Generic time-series catalog behavior, input variants, result series storage
    and transformations stay out of TS-1. Those remain TS-2 through TS-6 work.

## PRD Corrections

No corrections are required for `docs/series_tiempo/iter1/prd.md`.

The PRD is accepted as written, with one explicit implementation clarification:
TS-1 may preserve current `Scenario -> OptimizationCase` cardinality while it
introduces topology/parameter provenance. Cardinality migration is deferred.

## Acceptance Mapping

- Topology, parameters and execution snapshots were reviewed and accepted.
- Keeping `ScenarioVersion` as the technical immutable snapshot is accepted.
- Changing `Scenario -> OptimizationCase` cardinality is explicitly deferred.
- Curves as parameter-version selections are accepted.
- Compatibility for structured draft and hydraulic diagram flows is accepted.
- No PRD correction is needed before downstream TS-1 implementation begins.
