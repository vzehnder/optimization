# BESS TS-6 Issue Tracker

This document is the local tracker for TS-6: declarative transformations and
automation on top of the common series model, derived from
`docs/series_tiempo/iter6/prd.md`.

External issue tracker integration has not been configured, so each issue is
stored as a Markdown file in this folder. All issues carry the
`ready-for-agent` triage label.

TS-6 is deliberately gated: the PRD defers it until real usage of the TS-2
through TS-5 model justifies it (user story 18). BESS-TS6-000 must close the
activation decision before any implementation issue starts.

## Date Policy

All issues generated from this point forward include:

- `Fecha de inicio planificada`
- `Fecha de termino planificada`

Actual start/end dates can be added or corrected by the implementer when work
really begins and ends.

## Status Vocabulary

- `Todo`: not started.
- `In Progress`: actively being implemented.
- `Blocked`: waiting on a dependency or decision.
- `In Review`: implementation is ready for review.
- `Done`: merged or accepted.

## Issue Register

| ID | Title | Type | Triage | Status | Fecha de inicio planificada | Fecha de termino planificada | Blocked by | Issue file |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| BESS-TS6-000 | Review TS-6 PRD And Transformation Semantics | HITL | ready-for-agent | Todo | 2026-07-13 | 2026-07-13 | None | [BESS-TS6-000-review-ts6-prd-and-transformation-semantics.md](BESS-TS6-000-review-ts6-prd-and-transformation-semantics.md) |
| BESS-TS6-001 | Apply One Allowlisted Transformation End-To-End | AFK | ready-for-agent | Todo | 2026-07-14 | 2026-07-17 | BESS-TS6-000 | [BESS-TS6-001-apply-one-allowlisted-transformation-end-to-end.md](BESS-TS6-001-apply-one-allowlisted-transformation-end-to-end.md) |
| BESS-TS6-002 | Resample A Series Set To An Optimization Resolution | AFK | ready-for-agent | Todo | 2026-07-20 | 2026-07-21 | BESS-TS6-001 | [BESS-TS6-002-resample-a-series-set-to-an-optimization-resolution.md](BESS-TS6-002-resample-a-series-set-to-an-optimization-resolution.md) |
| BESS-TS6-003 | Interpolate Small Gaps Explicitly And Auditably | AFK | ready-for-agent | Todo | 2026-07-22 | 2026-07-23 | BESS-TS6-001 | [BESS-TS6-003-interpolate-small-gaps-explicitly-and-auditably.md](BESS-TS6-003-interpolate-small-gaps-explicitly-and-auditably.md) |
| BESS-TS6-004 | Combine Series From Multiple Sets Into A Derived Set | AFK | ready-for-agent | Todo | 2026-07-24 | 2026-07-27 | BESS-TS6-001 | [BESS-TS6-004-combine-series-from-multiple-sets-into-a-derived-set.md](BESS-TS6-004-combine-series-from-multiple-sets-into-a-derived-set.md) |
| BESS-TS6-005 | Mark Derived Sets Stale And Regenerate Them | AFK | ready-for-agent | Todo | 2026-07-28 | 2026-07-29 | BESS-TS6-001 | [BESS-TS6-005-mark-derived-sets-stale-and-regenerate-them.md](BESS-TS6-005-mark-derived-sets-stale-and-regenerate-them.md) |
| BESS-TS6-006 | Ingest Forecast Data Through An Isolated External Connector | AFK | ready-for-agent | Todo | 2026-07-30 | 2026-08-03 | BESS-TS6-000 | [BESS-TS6-006-ingest-forecast-data-through-an-isolated-external-connector.md](BESS-TS6-006-ingest-forecast-data-through-an-isolated-external-connector.md) |
| BESS-TS6-007 | Store Issuer And Validity For Programmed External Data | AFK | ready-for-agent | Todo | 2026-08-04 | 2026-08-05 | BESS-TS6-006 | [BESS-TS6-007-store-issuer-and-validity-for-programmed-external-data.md](BESS-TS6-007-store-issuer-and-validity-for-programmed-external-data.md) |
| BESS-TS6-008 | Schedule Reruns Using Case, Variant And Date Range | AFK | ready-for-agent | Todo | 2026-08-06 | 2026-08-10 | BESS-TS6-000 | [BESS-TS6-008-schedule-reruns-using-case-variant-and-date-range.md](BESS-TS6-008-schedule-reruns-using-case-variant-and-date-range.md) |
| BESS-TS6-009 | Run Rolling-Horizon Automation With Auditable Snapshots | AFK | ready-for-agent | Todo | 2026-08-11 | 2026-08-12 | BESS-TS6-008 | [BESS-TS6-009-run-rolling-horizon-automation-with-auditable-snapshots.md](BESS-TS6-009-run-rolling-horizon-automation-with-auditable-snapshots.md) |
| BESS-TS6-010 | Finalize TS-6 Acceptance Suite And Docs | AFK | ready-for-agent | Todo | 2026-08-13 | 2026-08-14 | BESS-TS6-001 through BESS-TS6-009 | [BESS-TS6-010-finalize-ts6-acceptance-suite-and-docs.md](BESS-TS6-010-finalize-ts6-acceptance-suite-and-docs.md) |

## Recommended Execution Order

1. BESS-TS6-000 closes the activation decision (start now versus keep
   deferring, per user story 18) and the transformation-semantics decision
   record (allowlist catalog, output model, lineage contract, derived
   staleness, connector target, scheduling mechanism and permissions).
2. BESS-TS6-001 is the transformation tracer bullet: `scale_signal` applied
   end-to-end — declarative parameters, versioned schema, allowlist
   enforcement, derived set with full lineage, catalog visibility and
   variant binding.
3. BESS-TS6-002 adds resampling to an optimization resolution, keeping
   run-time behavior strict (no implicit resampling).
4. BESS-TS6-003 adds explicit, auditable gap interpolation with a declared
   maximum gap.
5. BESS-TS6-004 adds the first multi-input transformation, composing a
   derived set from signals of several sets.
6. BESS-TS6-005 closes the derived-data lifecycle: stale marking on source
   changes and explicit regeneration, composed with the TS-3 fail-closed
   gates.
7. BESS-TS6-006 is the connector tracer bullet: external forecast data
   ingested through the common source/set model behind an isolated module.
8. BESS-TS6-007 adds issuer and validity metadata for official programmed
   data.
9. BESS-TS6-008 is the automation tracer bullet: scheduled reruns defined as
   case + parameter version + variant + range, reusing the manual pipeline
   including TS-4 result indexing.
10. BESS-TS6-009 extends scheduling with rolling-horizon range rules and
    per-tick auditable snapshots.
11. BESS-TS6-010 closes the iteration with the acceptance suite, the manual
    test checklist, the final architecture note and docs.

The three chains after BESS-TS6-000 (transformations 001-005, connectors
006-007, automation 008-009) are independent and can be reordered or
interleaved if priorities change.

## Progress Log

| Date | Issue | Status change | Notes |
| --- | --- | --- | --- |
| 2026-07-10 | All | Created | Initial local issue set generated from the TS-6 PRD (`docs/series_tiempo/iter6/prd.md`) and the series hierarchy roadmap. TS-6 remains gated on the activation decision (user story 18): BESS-TS6-000 must confirm real usage justifies starting before any implementation issue begins. |

## Final TS-6 Verification

Run before considering TS-6 closed:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

```powershell
cd frontend
npm test -- --run
npx tsc -b
npx eslint .
npm run api:check
npm run build
```

Julia regression is only required if a TS-6 slice changes artifact formats,
the generated `system_case_json` contract or optimizer behavior. Scheduled
and rolling-horizon runs (BESS-TS6-008, BESS-TS6-009) reuse the manual
pipeline, and transformed inputs must materialize through the existing
contract, so run it if any slice touches that boundary:

```powershell
julia --project=. -e "import Pkg; Pkg.test()"
```

## Regression Guard

Every slice that changes backend persistence must keep the existing Python
suite green: scenario versions, structured drafts, hydraulic diagrams, manual
runs, TS-1 hierarchy provenance, TS-2 catalog, TS-3 variants, TS-4 result
indexing and TS-5 migration/permission/retention tests.

Slices changing React should run the relevant frontend unit tests, `tsc -b`
and `eslint .`.

Transformations never mutate their source sets: they only add derived sets or
revisions with full lineage (inputs, revisions/hashes, validated parameters,
parameter schema version, implementation version). No arbitrary user-provided
script is ever stored in or executed from the database; only allowlisted,
versioned transformation types run.

Historical scenario versions, executed snapshots and registered artifacts
remain immutable: regeneration of derived data and scheduled automation must
never rewrite them. Runs keep pointing at the exact revisions/hashes they
consumed, before and after any regeneration.

Automation must not bypass the manual gates: scheduled and rolling-horizon
runs pass through the same staleness, coverage and permission checks as
manual runs, and no implicit resampling or gap filling ever happens at run
time.

Physical storage optimizations (partitioning, TimescaleDB) stay out of scope
unless a measured bottleneck at realistic volume justifies them.
