# BESS-ITER3-002: Save A Validated Scenario Version Under A Project

Status: Done
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

- [x] The app can be configured through `DATABASE_URL`.
- [x] The persistence layer supports projects, scenarios, scenario versions, and
      basic audit fields.
- [x] The schema is compatible with PostgreSQL-style deployment while remaining
      lightweight for local tests.
- [x] A project can be created, listed, and opened from the internal UI/API.
- [x] A scenario can be created, listed, and opened under a project.
- [x] A valid `system_case_json` can be saved as a scenario version only after
      Julia validation succeeds.
- [x] A scenario version stores the complete input document and extracted
      metadata such as case name, schema version, and basic asset counts.
- [x] The scenario detail view shows saved versions.
- [x] Invalid cases are not saved as executable versions.
- [x] Tests cover persistence, API behavior, template smoke rendering, and
      validation-before-save behavior.

## Implementation notes

- Added a lightweight `DATABASE_URL`-configured SQLite analyst store for
  `Project`, `Scenario`, and immutable `ScenarioVersion` records.
- Added API endpoints for creating, listing, and opening projects, scenarios,
  and scenario versions.
- Added server-rendered internal pages for project list, project detail, and
  scenario detail.
- Scenario version creation delegates validation to the Julia validation
  service before insertion, stores the complete `system_case_json`, and extracts
  case name, schema version, period count, and asset counts for listings.
- Invalid validation results return clear errors and do not create versions.

## Verification

Passed:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
julia --project=. -e "import Pkg; Pkg.test()"
```

Results:

- Python web tests: 17 passed.
- Julia package tests: 351 passed.

## Blocked by

BESS-ITER3-001
