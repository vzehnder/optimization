# BESS-TS3-004: Clone Variants And Switch Them From The Case Dropdown

Status: Done
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter3/prd.md`
Fecha de inicio planificada: 2026-07-16
Fecha de termino planificada: 2026-07-17
Fecha de inicio real: 2026-07-07
Fecha de termino real: 2026-07-07

## User stories covered

2, 3

## What to build

Let a case hold multiple input variants and make switching between them
trivial. An analyst clones an existing variant (typically the default), names
it, and changes only the bindings that differ; the clone copies bindings, not
series values. The case view gains a variant dropdown that lists all variants,
marks the default, and drives which variant the run flow uses.

Cloning and variant listing are backend operations with their own endpoints;
the dropdown selection persists so the analyst can bind, validate and run
against the chosen variant without duplicating topology or parameters.

## Acceptance criteria

- [x] Cloning a variant creates a new named variant with copied bindings and no copied series values.
- [x] Bindings of a cloned variant can be changed without affecting the original variant.
- [x] The case UI shows a dropdown of variants with the default clearly marked, and the selection drives binding, validation and run launch.
- [x] Backend endpoints exist to list, create, clone and update variants scoped to the case.
- [x] Backend tests prove clone independence and that the default variant remains the fallback selection.

## Resolution

Implemented TDD-first.

- Extended `AnalystStore` with case-scoped input-variant CRUD and cloning:
  list, create, update, clone, default lookup, and scenario/case ownership
  validation for every variant-aware route.
- Added backend endpoints for `GET /case/variants`, `POST /case/variants`,
  `POST /case/variants/{variant_id}/clone`, and
  `PATCH /case/variants/{variant_id}`. Run and binding routes now reject a
  variant that does not belong to the scenario's case.
- Reworked the React case variant panel so the scenario page loads the full
  variant list, shows a dropdown with the default marked, clones the active
  variant by name, persists the analyst's selection per scenario, and drives
  binding/validation/run actions from the selected variant instead of always
  falling back to the default.
- Preserved clone independence: bindings are copied at clone time, but later
  rebinding the clone updates only that variant's bindings; the default stays
  unchanged.
- Regenerated the frontend API contract after adding the new backend
  responses and payloads.

## Verification

Passed:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_ts3_input_variants tests.test_ts3_case_variant_api -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Results:

- Python suite: 269 tests passed, 1 skipped.

Frontend:

```powershell
cd frontend
npm.cmd test -- --run src/App.test.tsx
npm.cmd run api:check
npm.cmd run build
```

Results:

- Variant clone/dropdown React tests passed.
- API schema check and production build passed.

Chrome / MCP verification:

- Seeded real PostgreSQL QA data for project `TS3-004 Chrome QA` and
  scenario `Clone variant dropdown`.
- Verified with chrome-devtools MCP on
  `http://127.0.0.1:8000/react/scenarios/32`:
  - cloned `Default` into `Stress clone`;
  - switched the dropdown to `Stress clone`, rebound the price signal to set
    `#17`, and launched a run;
  - watched `Run 10` reach `succeeded` with exit code `0`;
  - switched back to `Default (default)` and confirmed it still points to set
    `#16`, proving clone independence in the live UI.
- Used Chrome extension control as well: connected a named Chrome session and
  opened a controlled local-app tab. That surface reached the login page, but
  deeper automation was then blocked by another extension UI, so the full
  interaction checks remained on chrome-devtools MCP.

## Blocked by

BESS-TS3-001
