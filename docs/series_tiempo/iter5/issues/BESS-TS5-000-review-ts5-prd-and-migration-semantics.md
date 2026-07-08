# BESS-TS5-000: Review TS-5 PRD And Migration Semantics

Status: Todo
Type: HITL
Triage: ready-for-agent
Source: `docs/series_tiempo/iter5/prd.md`
Fecha de inicio planificada: 2026-07-09
Fecha de termino planificada: 2026-07-09

## User stories covered

1 through 17

## What to build

Review and accept the TS-5 PRD before implementation starts. TS-5 consolidates
the architecture built in TS-1 through TS-4: after it, new time-series writes
and new result writes must use the common model, legacy paths must have clear
adapters or migration routes, and the UI must stop mixing concepts.

The review must close a per-path strategy (migrate, adapt with read adapters,
freeze as read-only legacy, or rebuild on demand) for every place temporal
data lives today: series embedded in structured scenario drafts, CSV/XLSX
sources of the structured editor, the hydraulic-specific series tables used by
the hydro diagram editor, historical scenario versions with materialized
`system_case_json`, and old runs whose results only exist as artifacts.

It must also close the decisions the PRD leaves open: the future role of
`ScenarioDraft` (compatibility surface, reduced role or deprecation path,
without forcing removal), the `Scenario -> OptimizationCase` cardinality
question explicitly deferred from TS-1 to TS-5 (whose implementation lands in
BESS-TS5-006), the hydraulic series write strategy and its compatibility
window, the permission matrix for sources, input series, result series and
published outputs across analyst, admin and client roles, and the retention
boundary between immutable audit data and rebuildable derived data.

The outcome should be a short accepted-decision record in the iteration docs
at `docs/series_tiempo/iter5/decision_record_ts5_migration_semantics.md`,
including any corrections to the PRD if scope, strategies or boundaries need
adjustment before downstream issues begin.

## Acceptance criteria

- [ ] A per-path strategy (migrate, adapt, freeze read-only or rebuild on demand) is decided and recorded for draft-embedded series, structured-editor sources, hydraulic-specific series tables, historical scenario versions and artifact-only results.
- [ ] Historical scenario versions and executed snapshots are confirmed as never rewritten; any extraction into the new model records origin metadata.
- [ ] The future role of `ScenarioDraft` is decided (compatibility, reduced role or deprecation path) without forcing its removal.
- [ ] The `Scenario -> OptimizationCase` cardinality decision deferred from TS-1 is closed, including what BESS-TS5-006 must implement.
- [ ] The hydraulic series write strategy (generic-model writes with adapter reads, dual write or on-demand migration) and its compatibility window are decided.
- [ ] The permission matrix for sources, input series, result series and published outputs across analyst, admin and client roles is agreed.
- [ ] Retention boundaries distinguishing immutable audit data from rebuildable derived data are agreed.
- [ ] The architecture-closure criteria (new writes to the common model, adapters for legacy reads, UI no longer mixing concepts) are agreed as the TS-5 definition of done.
- [ ] Any PRD correction is committed before downstream TS-5 implementation issues begin.

## Blocked by

None - can start immediately.
