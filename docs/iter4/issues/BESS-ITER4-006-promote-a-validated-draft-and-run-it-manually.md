# BESS-ITER4-006: Promote A Validated Draft And Run It Manually

Status: Done
Type: AFK
Triage: ready-for-agent
Source: `docs/iter4/prd_structured_editor_flow.md`

## User stories covered

47 through 50, 64

## What to build

Complete the structured editor path by promoting a validated draft into an
immutable scenario version and running it through the existing manual execution
flow.

The promoted version must store the exact generated `system_case_json`, then the
existing run queue, Julia executor, artifact registration, result reader, and
download behavior should work without a second execution path.

## Acceptance criteria

- [x] A successfully validated generated case can be promoted to a new
      immutable scenario version.
- [x] The promoted version stores the exact generated `system_case_json`.
- [x] The source draft remains editable after promotion.
- [x] The promoted scenario version can launch a manual run through the existing
      run endpoint and UI.
- [x] The run executes through the existing Julia process boundary.
- [x] Success and failure artifacts are registered through the existing artifact
      mechanism.
- [x] Results for an editor-created version render summary, tables, charts, and
      downloads.
- [x] The paste/upload JSON path can still promote and run a scenario version.
- [x] Acceptance tests cover draft-to-version-to-run behavior end to end.

## Implementation notes

- Added generated-case promotion endpoints:
  `/api/scenarios/{scenario_id}/draft/generated-system-case/promote` and
  `/scenarios/{scenario_id}/draft/generated-system-case/promote`.
- Promotion requires the draft's stored `generated_system_case` snapshot to be
  successfully validated and still match the current generated draft output.
- Promoted versions reuse the existing scenario-version persistence path, so the
  stored `system_case_json` is the exact generated case and remains immutable.
- The source draft remains mutable after promotion; later draft edits do not
  mutate the promoted scenario version.
- The draft page shows `Promote To Scenario Version` only after successful
  generated-case validation, then redirects to the scenario version list.
- Runs for editor-created versions continue through the existing manual run
  endpoint, Julia runner, artifact registry, result reader, charts, tables, and
  downloads.

## Verification

Passed:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_draft_generated_system_case
.\.venv\Scripts\python.exe -m unittest tests.test_draft_generated_system_case tests.test_manual_runs tests.test_iter3_acceptance tests.test_structured_draft_editor tests.test_csv_time_series_ingestion tests.test_results_review
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Results:

- Focused draft-generation/promotion tests: 7 passed.
- Relevant Iteration 3 and Iteration 4 web tests: 39 passed.
- Full Python web suite: 59 passed. First full run hit a Julia validation
  timeout during warmup; the isolated failing test and rerun passed.
- Local smoke promoted a real validated draft to scenario version 4, launched a
  manual run through the real Julia process boundary, and completed run 4 with
  status `succeeded`, exit code 0, and registered result artifacts.
- Chrome DevTools MCP console inspection reported no console messages.

Browser note: attempted the requested in-app Browser workflow twice, but the
`node_repl` runtime failed locally with `windows sandbox failed: spawn setup
refresh`. HTTP and Chrome DevTools MCP fallback verification was completed.

## Blocked by

BESS-ITER4-005
