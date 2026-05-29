# BESS-ITER3-006: Register And Download Auditable Artifacts

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: `docs/iter3/prd_analyst_web_flow.md`

## User stories covered

27, 28, 29, 30, 31, 32, 33

## What to build

Register the files that make each run auditable and expose safe downloads
through the internal API/UI. The app should index artifact metadata in the
database while leaving the source files on disk under the configured artifact
root.

Downloads should include the existing Julia outputs, the input snapshot, and
captured logs when present.

## Acceptance criteria

- [ ] Successful runs register `summary.json`, `dispatch.csv`,
      `asset_dispatch.csv`, and `model_metadata.json`.
- [ ] Runs register the exact input JSON used for execution.
- [ ] Runs register stdout and stderr logs when present.
- [ ] Artifact metadata includes type, path, and enough display metadata for
      the UI.
- [ ] Artifact paths are constrained to the configured artifact root before
      being exposed.
- [ ] The run detail page lists downloadable artifacts.
- [ ] The API can download each registered artifact.
- [ ] Missing artifact files produce a clear not-found response instead of an
      internal error.
- [ ] Tests cover artifact registration, safe path handling, listing, and
      downloads.

## Blocked by

BESS-ITER3-004, BESS-ITER3-005
