# Analyst Web Flow PRD

## Problem Statement

Iteration 2 stabilized the Julia one-bus hybrid optimizer behind a versioned
`system_case.json` contract, a process-friendly CLI, and auditable output files.
That is enough for an engineer to run cases from the command line, but it is
not yet enough for an analyst to manage work as a private application flow.

The current gap is the product wrapper around the optimizer: there is no
backend-owned project structure, no scenario version history, no persisted run
state, no API/UI for launching Julia from a web workflow, and no internal page
for reviewing the resulting artifacts.

Iteration 3 must prove the boundary between the Python web application and the
Julia engine in a real but intentionally narrow analyst workflow. The goal is
not to add more mathematical capabilities or advanced dashboards. The goal is
to turn the existing one-bus hybrid optimizer into a minimal usable private app:

```text
Project -> Scenario -> ScenarioVersion -> Run -> Artifacts -> Basic Results Review
```

## Solution

Build a private FastAPI-backed analyst workflow around the existing Julia
system-dispatch contract.

An analyst can create projects and scenarios, create immutable scenario
versions by pasting or uploading a complete `system_case.json`, validate that
case through Julia, manually launch a run, observe run state, and inspect or
download the auditable artifacts produced by the Julia CLI.

The database becomes the source of truth for application state: projects,
scenarios, scenario versions, runs, and artifact metadata. In Iteration 3, the
canonical optimization input inside a scenario version is still the full
`system_case_json` document, not normalized relational asset tables. This keeps
the web layer aligned with the stable Iteration 2 contract while leaving room
for a structured editor later.

The Julia engine remains the mathematical authority. The backend invokes Julia
as an external process for validation and execution, captures stdout, stderr,
exit code, timestamps, errors, and generated artifact paths, and records that
state for the UI/API.

The first UI is an internal server-side rendered web interface with minimal
JavaScript for polling run status, rendering result tables, and drawing basic
charts from existing output files. It is not a customer portal, not a dashboard
publishing system, and not a visual model editor.

## User Stories

1. As an analyst, I want to create a project, so that related optimization work
   is grouped in one place.
2. As an analyst, I want to list projects, so that I can return to prior work.
3. As an analyst, I want to view a project detail page, so that I can see its
   scenarios and recent runs.
4. As an analyst, I want to create a scenario under a project, so that model
   alternatives can be organized separately.
5. As an analyst, I want to list scenarios in a project, so that I can compare
   available modeling branches.
6. As an analyst, I want to view a scenario detail page, so that I can inspect
   its versions and runs.
7. As an analyst, I want to create a scenario version by pasting JSON, so that I
   can quickly test a `system_case` without file handling.
8. As an analyst, I want to create a scenario version by uploading a JSON file,
   so that I can use an existing `system_case.json`.
9. As an analyst, I want the JSON textarea to be editable before saving, so
   that I can make small changes without leaving the app.
10. As an analyst, I want malformed JSON to fail before validation, so that I
    get immediate feedback on syntax issues.
11. As an analyst, I want a scenario version to be validated when saved, so that
    invalid optimization inputs are caught early.
12. As an analyst, I want validation errors from Julia to be shown clearly, so
    that I can fix invalid graph, time-series, or parameter data.
13. As an analyst, I want saved scenario versions to be immutable, so that every
    run points to an exact input snapshot.
14. As an analyst, I want to create a new version from an existing scenario, so
    that model changes preserve history instead of overwriting prior inputs.
15. As an analyst, I want to see schema version, case name, and basic asset
    counts for a scenario version, so that I can recognize what was saved.
16. As an analyst, I want to manually launch a run from a scenario version, so
    that I can execute a validated optimization case.
17. As an analyst, I want a launched run to return a run identifier quickly, so
    that the web request does not block on Julia solving.
18. As an analyst, I want to see run states such as queued, running, succeeded,
    and failed, so that I know what is happening.
19. As an analyst, I want the run detail page to poll for state changes, so that
    I can watch progress without refreshing manually.
20. As an analyst, I want failed runs to show a structured error message, so
    that I understand whether failure came from validation, execution, or solve
    behavior.
21. As an analyst, I want stdout and stderr from Julia preserved, so that failed
    or suspicious runs can be debugged later.
22. As an analyst, I want the exact input used for a run preserved, so that I can
    reproduce or audit the run.
23. As an analyst, I want each run to record timestamps and duration, so that I
    can understand execution history.
24. As an analyst, I want each run to record the Julia process exit code, so
    that process failures are explicit.
25. As an analyst, I want the backend to parse Julia success JSON from stdout,
    so that generated output paths are registered automatically.
26. As an analyst, I want the backend to parse Julia error JSON from stderr when
    available, so that failures are stored in a structured way.
27. As an analyst, I want output artifacts to stay as files, so that the
    Iteration 2 audit trail remains intact.
28. As an analyst, I want the database to store artifact metadata and paths, so
    that the app can navigate results without storing CSV bodies in the DB.
29. As an analyst, I want to download `summary.json`, so that I can keep or
    share the run summary.
30. As an analyst, I want to download `dispatch.csv`, so that I can inspect
    system totals in a spreadsheet.
31. As an analyst, I want to download `asset_dispatch.csv`, so that I can
    inspect long asset-level results.
32. As an analyst, I want to download `model_metadata.json`, so that I can audit
    the model and unit conventions used.
33. As an analyst, I want to download the input JSON used for the run, so that I
    can reproduce the exact execution.
34. As an analyst, I want to see a run summary from `summary.json`, so that I can
    quickly inspect objective value, solver status, and termination status.
35. As an analyst, I want to view `dispatch.csv` as a table, so that I can review
    period-level system totals in the browser.
36. As an analyst, I want to view `asset_dispatch.csv` as a table, so that I can
    review asset-level dispatch in the browser.
37. As an analyst, I want a chart of grid import and export, so that I can see
    interaction with the grid.
38. As an analyst, I want a chart of renewable used and curtailed power, so that
    I can see how renewable availability was handled.
39. As an analyst, I want a chart of battery charge, discharge, and stored
    energy, so that I can inspect BESS behavior.
40. As an analyst, I want a chart of period profit, so that I can inspect the
    economic shape of the run.
41. As a backend developer, I want a clean internal API for projects, scenarios,
    versions, runs, artifacts, and results, so that templates and future clients
    use stable contracts.
42. As a backend developer, I want the app to use `DATABASE_URL`, so that local
    development can start simply and deployment can use PostgreSQL-compatible
    databases.
43. As a backend developer, I want the local/test setup to work with SQLite or a
    simple local database, so that tests do not require managed infrastructure.
44. As a backend developer, I want the schema to be compatible with PostgreSQL,
    so that Supabase or another hosted Postgres can be used later.
45. As a backend developer, I want the scenario input stored as JSON/JSONB-like
    data, so that the Iteration 2 contract remains the canonical parameter
    document.
46. As a backend developer, I want the runner to process one run at a time, so
    that Iteration 3 avoids premature concurrency complexity.
47. As a backend developer, I want queued runs to be explicit, so that later
    queue or worker infrastructure can replace the local runner.
48. As a backend developer, I want artifact writes contained under a configured
    artifact root, so that paths are predictable and safe to expose through the
    app.
49. As a backend developer, I want validation to use Julia rather than duplicate
    optimizer rules in Python, so that there is one authority for the case
    contract.
50. As a Julia maintainer, I want a validation CLI that loads and normalizes
    without solving, so that the web backend can validate cases before creating
    runs.
51. As a Julia maintainer, I want the existing execution CLI to remain stable,
    so that Iteration 2 integrations are not broken.
52. As a maintainer, I want the full Julia regression suite to remain green, so
    that the optimizer behavior stays intact while the web wrapper is added.
53. As a maintainer, I want backend tests around persistence, validation,
    runner behavior, artifacts, results parsing, and API contracts, so that the
    new app layer has reliable boundaries.
54. As a maintainer, I want smoke tests for server-rendered pages, so that the
    private analyst UI does not regress invisibly.

## Implementation Decisions

- The domain model for Iteration 3 is `Project`, `Scenario`,
  `ScenarioVersion`, `Run`, and `RunArtifact`.
- A `ScenarioVersion` is immutable after creation. Any model change creates a
  new version.
- A `ScenarioVersion` stores the complete `system_case_json` document as the
  canonical optimization input for this iteration.
- The app may extract metadata such as case name, schema version, and asset
  counts from the JSON for listing and filtering, but it does not normalize
  battery, renewable, grid, load, edge, or time-series parameters into separate
  relational tables yet.
- The database is the source of truth for projects, scenarios, scenario
  versions, runs, and artifact metadata.
- Local and test configuration should remain lightweight. The app should be
  designed around a `DATABASE_URL` setting and PostgreSQL-compatible schema,
  with Supabase treated as a valid hosted Postgres option rather than a required
  dependency.
- Supabase Auth, Supabase Storage, Row Level Security, Edge Functions, and
  platform-specific behavior are out of scope for Iteration 3.
- Output artifacts remain files under a configured artifact root. The database
  records paths and metadata rather than storing full CSV or JSON artifact
  bodies.
- The audit artifacts remain the existing output files: `summary.json`,
  `dispatch.csv`, `asset_dispatch.csv`, `model_metadata.json`, plus the input
  JSON used by the run and captured stdout/stderr logs.
- The backend writes the exact `system_case_json` snapshot for a run to a
  controlled input artifact before executing Julia.
- The backend invokes Julia through process boundaries. It does not reimplement
  the mathematical formulation or validation rules.
- Add a small Julia validation CLI that loads and normalizes a system case
  without solving. It should return parseable JSON on success and structured
  error information on failure.
- Continue using the existing Julia system-dispatch execution CLI for actual
  runs.
- Validation happens when saving a scenario version and again immediately before
  execution of a run.
- Python performs only lightweight JSON parsing and request validation before
  delegating contract validation to Julia.
- Run states are `queued`, `running`, `succeeded`, and `failed`.
- Iteration 3 uses a local asynchronous runner with concurrency one. It should
  make queued state real while avoiding external queue infrastructure.
- The runner captures stdout, stderr, exit code, created timestamp, started
  timestamp, finished timestamp, duration, and structured error message when
  available.
- The runner parses the Julia success payload from stdout to register generated
  artifacts and mark the run succeeded.
- If Julia exits nonzero, the runner stores the failure and preserves stderr for
  debugging.
- The first web interface is server-side rendered by FastAPI with minimal
  JavaScript for polling, tables, and charts.
- The UI supports creating versions by pasting JSON into an editable textarea
  and by uploading a `.json` file.
- The UI shows validation errors before saving invalid versions.
- The UI supports manual run creation only. Scheduled runs are out of scope.
- The UI supports basic results review from existing output files: summary,
  dispatch table, asset dispatch table, grid import/export chart, renewable
  used/curtailed chart, BESS charge/discharge/SOC chart, and period profit
  chart.
- The UI/API supports downloading the auditable artifacts for a completed run.
- The app has an internal API for the same domain actions used by the
  server-side pages. It is not a public external API contract yet, but it should
  be clean enough for tests and a future SPA.
- There is no real authentication in Iteration 3. Records can use an implicit
  internal analyst identity for `created_by` and `triggered_by` audit fields.
- The Julia optimizer must remain intact and covered by the existing regression
  suite.

## Testing Decisions

- Tests should focus on external behavior and contracts rather than
  implementation details.
- Persistence tests should prove projects, scenarios, immutable scenario
  versions, runs, and artifact metadata can be created, listed, and retrieved.
- Scenario version tests should prove pasted JSON and uploaded JSON converge to
  the same stored `system_case_json` behavior.
- Validation service tests should prove malformed JSON fails in Python, valid
  cases pass through Julia validation, and invalid cases surface Julia error
  messages without creating executable versions.
- Julia validation CLI tests should prove success stdout is parseable JSON,
  failure exits nonzero, and failure stderr is parseable structured error data.
- Runner tests should prove queued-to-running-to-succeeded behavior, failure
  behavior, stdout/stderr capture, exit-code recording, timestamp recording, and
  artifact registration.
- Artifact registry tests should prove only paths under the configured artifact
  root are exposed and registered.
- Results reader tests should prove `summary.json`, `dispatch.csv`,
  `asset_dispatch.csv`, and `model_metadata.json` are read into API/UI-friendly
  structures without changing the source files.
- API tests should cover project, scenario, version, validation, manual run,
  run status, artifact listing, artifact download, and basic results endpoints.
- Template smoke tests should cover the main analyst pages: project list,
  project detail, scenario detail, scenario version creation, run detail, and
  results view.
- A minimal web-flow smoke test can be added if it stays lightweight; a large
  browser E2E suite is not required for Iteration 3.
- The existing Julia regression command remains the required guard for any
  optimizer or CLI change.
- Prior art exists in the current Julia test suite for CLI success/failure JSON,
  validation failures, output artifact assertions, and sample acceptance flows.

## Out of Scope

- Customer read-only portal.
- Published dashboards.
- Configurable dashboard templates.
- Daily, weekly, monthly, or cron-like scheduled runs.
- Multi-worker or distributed run execution.
- Celery, Redis, or external queue infrastructure.
- Full SPA frontend.
- Advanced browser E2E suite.
- Structured visual editor for assets, time series, and constraints.
- Canvas-based model editing.
- Normalized relational tables for every asset parameter and time-series row.
- CSV/Excel column mapping into `system_case`.
- Hydropower modeling.
- Separate import and export prices.
- Mathematical model changes beyond the validation CLI needed by the web flow.
- Supabase-specific features such as Auth, Storage, Edge Functions, and RLS.
- Granular authentication, authorization, roles, or multi-user administration.
- Client-facing downloads or publication workflows.
- Replacing or hiding the existing auditable Julia output files.

## Further Notes

Iteration 3 should be treated as the first product proof around the stable
Julia optimizer. It intentionally chooses a document-shaped scenario version
over a fully normalized model editor because the `system_case.json` contract is
already stable and audited.

The database should prepare the product for PostgreSQL and hosted options such
as Supabase, but the iteration should not depend on managed platform services.

The most important acceptance proof is a complete private analyst flow:

```text
Create Project
-> Create Scenario
-> Create immutable ScenarioVersion from system_case_json
-> Validate through Julia
-> Launch manual Run
-> Observe queued/running/succeeded or failed state
-> Persist logs, input, outputs, and artifact metadata
-> Review summary, tables, and basic charts
-> Download auditable artifacts
```

The Julia regression suite remains a non-negotiable guardrail. Iteration 3
wraps the optimizer; it does not destabilize it.
