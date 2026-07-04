# BESS-TS1-008: Finalize TS-1 Acceptance Suite And Docs

Status: Done
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter1/prd.md`
Fecha de inicio planificada: 2026-07-24
Fecha de termino planificada: 2026-07-24
Fecha de inicio real: 2026-07-04
Fecha de termino real: 2026-07-04

## User stories covered

1 through 20

## What to build

Close TS-1 with acceptance coverage, documentation and tracker updates. The
iteration should clearly document the implemented hierarchy semantics, what
remains deferred to TS-2 through TS-5, and how to verify that existing flows
still work.

No new product behavior should be introduced in this slice beyond final
hardening required by acceptance tests.

## Acceptance criteria

- [x] A focused TS-1 acceptance test proves topology/parameter provenance on a representative generated scenario version.
- [x] Acceptance coverage proves stale validation for topology and parameter changes.
- [x] Acceptance coverage proves legacy versions without hierarchy metadata still render and run where applicable.
- [x] Documentation explains the final TS-1 model and known deferred work.
- [x] The issue tracker progress log is updated.
- [x] The README or relevant docs point to the TS-1 hierarchy documentation if appropriate.
- [x] Final verification commands are recorded in the tracker.
- [x] No TS-2 generic time-series behavior is introduced early.

## Blocked by

BESS-TS1-001 through BESS-TS1-007

## Implementation Notes

Closing proof issue; no production code change was needed since TS1-001..007
already implement the full hierarchy, stale-validation and compatibility
behavior. Added `tests.test_ts1_acceptance` (TDD, tracer bullet first) with
two tests: one continuous end-to-end story promoting a hydraulic v3 diagram
(distinct topology/parameters content hashes, `kind: "hydraulic_diagram_v3"`),
launching and completing a manual run, then independently proving a
topology-only edit (unit intake rewire) stales and blocks promotion naming
"topology" while a parameter-only edit (reservoir max storage) stales and
blocks promotion naming "parameters" (and not the other), with revalidated
promotions keeping the untouched hash stable across both cases; and finally
seeding a scenario version the way pre-TS1-001 data looked (direct SQL insert
with `generation_metadata_json='{}'`, bypassing `create_scenario_version`) and
proving it lists, loads and completes a manual run identically to
hierarchy-generated versions. The behavior test passed on the first run,
confirming BESS-TS1-001 through BESS-TS1-007 already satisfy this slice's
acceptance criteria end to end. A second test asserts the README, this issue,
the tracker and the new manual test checklist are all in their closed/final
state.

Added a new README section ("TS-1: Topology And Parameter Hierarchy")
documenting the hierarchy model, the topology/parameters boundary, provenance
and stale-validation behavior, legacy compatibility, and what remains
deferred to TS-2 through TS-6. Added
`docs/series_tiempo/iter1/pruebas_manuales_ts1.md`, a manual checklist for
hydraulic diagram and structured draft provenance/stale flows and legacy
compatibility, following the same shape as the Iteration 6 manual checklist.
Updated `docs/series_tiempo/iter1/issues/tracker_ts1.md` to mark this issue
Done and recorded final verification commands.

Verified end-to-end via chrome-devtools MCP against the real
PostgreSQL-backed app with the real Julia validator and solver: built a
reservoir+junctions+plant/unit hydraulic v3 diagram, promoted it and
confirmed distinct topology/parameters hashes and `Modelo: Diagrama
hidraulico v3` in the "Procedencia" panel; made a topology-only edit
(unit intake rewired) and confirmed the amber "Topologia desactualizada"
badge alone with promotion blocked; revalidated and promoted (topology hash
changed, parameters hash stable); made a parameter-only edit (reservoir max
storage) and confirmed the purple "Parametros desactualizados" badge alone
with promotion blocked; revalidated and promoted (parameters hash changed,
topology hash stable); launched a manual run on the final version that
solved `OPTIMAL` with real HiGHS results. Separately, seeded a
pre-TS1-001-shaped legacy scenario version directly in the real PostgreSQL
database via `psycopg` (bypassing the app) and confirmed it lists, renders
"Sin datos de procedencia" without error, and completes a manual run to
`OPTIMAL` identically to hierarchy-generated versions.

## Verification

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_ts1_acceptance -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Julia regression was not required for this slice because no Julia-facing
contracts, optimizer behavior, or artifact formats changed.
