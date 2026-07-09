# BESS-TS5-006: Resolve Scenario And Case Cardinality In Schema And UI

Status: Done
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter5/prd.md`
Fecha de inicio planificada: 2026-07-23
Fecha de termino planificada: 2026-07-24
Fecha de inicio real: 2026-07-09
Fecha de termino real: 2026-07-09

## User stories covered

11, 17

## What to build

Implement the `Scenario -> OptimizationCase` cardinality decision closed in
BESS-TS5-000 (the question TS-1 explicitly deferred to TS-5), in whichever
direction it lands.

If multiple cases per scenario is accepted: migrate the current
one-case-per-scenario constraint, routes, navigation and case selection so a
scenario can hold several cases, without breaking existing single-case
scenarios, with an idempotent schema migration for local SQLite and
PostgreSQL.

If one case per scenario is confirmed: make the product say so unambiguously —
naming, routes and labels no longer implying hidden multiplicity, and the
constraint kept deliberately rather than by accident.

In either outcome, hierarchy provenance, variant selection and run lineage
surfaces keep resolving correctly, and existing scenarios, cases, versions and
runs remain reachable exactly as before.

## Acceptance criteria

- [x] The accepted cardinality decision is implemented in schema constraints, API routes and UI navigation.
- [x] Existing scenarios, cases, versions and runs keep resolving correctly after the change, with an idempotent migration in SQLite and PostgreSQL if constraints change.
- [x] The UI no longer leaves the scenario/case relationship ambiguous, in either outcome.
- [x] Hierarchy provenance, variant selection and run lineage surfaces keep working unchanged.

## Blocked by

BESS-TS5-000

## Resolution

Decision 4 (`docs/series_tiempo/iter5/decision_record_ts5_migration_semantics.md`)
confirmed one-to-one, no migration. An audit of every "case" surface (schema,
`app/main.py` routes, `frontend/src` navigation) found routes, schema and
navigation already unambiguous by construction: no route ever exposes a case
list or an independent `/cases/{id}` resource, `optimization_cases`/
`scenario_drafts` writes only ever go through a single idempotent
get-or-create path, and no UI text implies multiplicity. The one real
ambiguity found: `ScenarioVersionDetailView`'s metadata panel labeled
`scenario_versions.case_name` (a frozen, free-text label from the payload at
promotion time, which can legitimately differ between versions of the same
scenario) as bare "Case" next to "Scenario ID" — reading as if versions could
belong to different case entities. Fixed by relabeling it "Nombre del caso"
(matching the existing `DraftEditor.tsx` field for the same underlying
concept), making clear it is a name, not a separate entity ID.

Implemented:
- SQL comments on `optimization_cases.scenario_id UNIQUE` and
  `scenario_drafts.scenario_id UNIQUE` in `app/persistence.py`, marking the
  one-to-one constraint as deliberate per Decision 4, not an accidental
  early-implementation limit.
- Docstring on `AnalystStore.get_or_create_case_for_scenario` stating the
  invariant.
- `tests/test_ts5_scenario_case_cardinality.py` (3 tests): idempotent
  get-or-create, a raw duplicate insert rejected by the schema
  (`sqlite3.IntegrityError`), and the `/case/default-variant` and
  `/case/variants` endpoints agreeing on the same case for a scenario.
- `frontend/src/Workspace.tsx`: relabeled `VersionMetadata`'s `<dt>Case</dt>`
  to `<dt>Nombre del caso</dt>`; new focused vitest in `App.test.tsx`.

No schema migration needed (constraint already existed and is unchanged), so
no SQLite/PostgreSQL migration script was required.

Backend suite 379 tests (2 skipped, up from 376), full run green. Frontend 63
vitest (up from 62) + `tsc -b`/`eslint .`/`api:generate`+`api:check`/`build`
all green. Chrome + real Postgres (project `TS5-006 Chrome QA`, id 43,
scenario 52): created a scenario (auto-created its one `optimization_cases`
row and default variant live), promoted a version whose payload
`case_name: "hybrid_system"` differs from the scenario name ("Base case"),
confirmed the version detail page now shows "NOMBRE DEL CASO: hybrid_system"
next to "SCENARIO ID: 52" instead of the ambiguous "CASE" label, confirmed
the input-variant panel, hierarchy provenance and version listing still
resolved correctly, zero console errors.
