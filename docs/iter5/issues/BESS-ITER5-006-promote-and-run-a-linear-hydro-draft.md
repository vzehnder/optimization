# BESS-ITER5-006: Promote And Run A Linear Hydro Draft

Status: Done
Type: AFK
Triage: ready-for-agent
Source: `docs/iter5/prd_hydro_simple_dispatch.md`

## User stories covered

43 through 48, 66

## What to build

Connect the structured linear hydro draft path to generated-case validation,
promotion, manual run execution, and artifact registration.

The analyst should be able to create a linear hydro draft, upload and map
hydro inflows, preview a generated `v2` case, validate it through Julia, promote
the current validation snapshot to an immutable scenario version, launch a
manual run, and see the run succeed with registered hydro artifacts.

## Acceptance criteria

- [x] A linear hydro draft can generate a complete `bess_system_dispatch.v2`
      preview from structured fields and mapped source rows.
- [x] Python generation errors appear before Julia validation when editor or
      mapping data is incomplete.
- [x] Julia validation success and failure for generated hydro cases are
      surfaced through API and SSR UI.
- [x] Promotion requires a current successful validation snapshot.
- [x] Promoted scenario versions store the exact generated hydro `system_case`.
- [x] Promoted versions retain safe source-file and mapping provenance.
- [x] A promoted linear hydro version can launch a manual run.
- [x] The manual run completes successfully through the existing Julia process
      boundary.
- [x] Run artifacts are registered for input snapshot, logs, summary,
      dispatch, asset dispatch, resolved case, and metadata.
- [x] The existing paste/upload JSON version path remains intact.

## Implementation notes

- Added end-to-end API coverage for a promoted linear hydro structured draft
  with mapped CSV rows, Julia-style successful validation snapshot, promotion to
  an immutable scenario version, manual run launch, successful completion, hydro
  result payloads, and safe source/mapping provenance.
- Aligned the hydro draft fixture with the current Julia one-bus normalizer by
  including the required zero-power BESS and zero-availability renewable assets
  alongside the linear hydro asset.
- Registered `system_case_resolved.json` as
  `system_case_resolved_json` when Julia writes it under the run output folder,
  completing the promoted-run artifact set.

## Verification

Passed:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_draft_generated_system_case.DraftGeneratedSystemCaseTests.test_promoted_linear_hydro_generated_version_runs_and_registers_hydro_artifacts -v
.\.venv\Scripts\python.exe -m unittest tests.test_draft_generated_system_case -v
.\.venv\Scripts\python.exe -m unittest tests.test_manual_runs -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Results:

- Focused promoted linear hydro draft test: passed.
- Draft generated system case suite: 11 passed.
- Manual run suite: 12 passed.
- Full Python web/API/template/results suite: 78 passed.
- Chrome DevTools local smoke: started the app on `http://127.0.0.1:8026`,
  created a linear hydro structured draft with mapped CSV rows, validated it
  through real Julia, promoted it, launched a manual run, observed
  `status = succeeded`, confirmed `system_case_resolved_json` was registered,
  and verified hydro totals/result tables on `/runs/5`.

Browser note: attempted the requested in-app Browser workflow twice, including a
runtime reset, but the browser-control runtime failed to start with
`windows sandbox failed: spawn setup refresh`. Chrome DevTools MCP verification
completed successfully.

## Blocked by

BESS-ITER5-005
