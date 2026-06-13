# BESS-ITER3-006: Register And Download Auditable Artifacts

Status: Done
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

- [x] Successful runs register `summary.json`, `dispatch.csv`,
      `asset_dispatch.csv`, and `model_metadata.json`.
- [x] Runs register the exact input JSON used for execution.
- [x] Runs register stdout and stderr logs when present.
- [x] Artifact metadata includes type, path, and enough display metadata for
      the UI.
- [x] Artifact paths are constrained to the configured artifact root before
      being exposed.
- [x] The run detail page lists downloadable artifacts.
- [x] The API can download each registered artifact.
- [x] Missing artifact files produce a clear not-found response instead of an
      internal error.
- [x] Tests cover artifact registration, safe path handling, listing, and
      downloads.

## Implementation notes

- Added persisted `run_artifacts` metadata with artifact type, path, display
  name, media type, byte size, and created timestamp.
- Successful runs now register the exact input snapshot, stdout/stderr logs,
  and the Julia output files `summary.json`, `dispatch.csv`,
  `asset_dispatch.csv`, and `model_metadata.json`.
- Failed runs register the available audit artifacts, including the input
  snapshot and captured logs.
- The runner rejects Julia success payload paths outside the configured
  `ARTIFACT_ROOT` before marking a run succeeded.
- Added artifact listing and download API endpoints with artifact-root
  filtering and clear 404 responses for missing files.
- The run detail page now lists safe registered artifacts as download links.

## Verification

Passed:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
julia --project=. -e "import Pkg; Pkg.test()"
```

Results:

- Python web tests: 29 passed.
- Julia package tests: 351 passed.
- Local app verification: created a real manual run through the API, observed
  `status = succeeded`, confirmed 7 registered artifacts, confirmed `/runs/1`
  renders the artifact section and `summary.json` download returns HTTP 200.

Browser note: attempted the requested in-app browser workflow, but the
`node_repl` browser-control runtime failed to start with a sandbox setup error
in this environment. The local server/UI was verified through the same HTTP
surface after the browser-control retry failed.

## Blocked by

BESS-ITER3-004, BESS-ITER3-005
