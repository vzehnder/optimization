# BESS-ITER3-002: Save A Validated Scenario Version Under A Project

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: `docs/iter3/prd_analyst_web_flow.md`

## User stories covered

1, 2, 3, 4, 5, 6, 11, 13, 15, 16, 41, 42, 43, 44, 45

## What to build

Build the first persisted analyst workflow: create a project, create a
scenario under that project, validate a complete `system_case_json`, and save it
as the first immutable scenario version.

The database should own application state, while the scenario version keeps the
full `system_case_json` document as the canonical optimization input.

## Acceptance criteria

- [ ] The app can be configured through `DATABASE_URL`.
- [ ] The persistence layer supports projects, scenarios, scenario versions, and
      basic audit fields.
- [ ] The schema is compatible with PostgreSQL-style deployment while remaining
      lightweight for local tests.
- [ ] A project can be created, listed, and opened from the internal UI/API.
- [ ] A scenario can be created, listed, and opened under a project.
- [ ] A valid `system_case_json` can be saved as a scenario version only after
      Julia validation succeeds.
- [ ] A scenario version stores the complete input document and extracted
      metadata such as case name, schema version, and basic asset counts.
- [ ] The scenario detail view shows saved versions.
- [ ] Invalid cases are not saved as executable versions.
- [ ] Tests cover persistence, API behavior, template smoke rendering, and
      validation-before-save behavior.

## Blocked by

BESS-ITER3-001
