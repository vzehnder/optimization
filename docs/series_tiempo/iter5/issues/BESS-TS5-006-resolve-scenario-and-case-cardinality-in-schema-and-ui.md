# BESS-TS5-006: Resolve Scenario And Case Cardinality In Schema And UI

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter5/prd.md`
Fecha de inicio planificada: 2026-07-23
Fecha de termino planificada: 2026-07-24

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

- [ ] The accepted cardinality decision is implemented in schema constraints, API routes and UI navigation.
- [ ] Existing scenarios, cases, versions and runs keep resolving correctly after the change, with an idempotent migration in SQLite and PostgreSQL if constraints change.
- [ ] The UI no longer leaves the scenario/case relationship ambiguous, in either outcome.
- [ ] Hierarchy provenance, variant selection and run lineage surfaces keep working unchanged.

## Blocked by

BESS-TS5-000
