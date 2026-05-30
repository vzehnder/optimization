# BESS-ITER3-003: Preserve Immutable Version History From Paste Or Upload

Status: Done
Type: AFK
Triage: ready-for-agent
Source: `docs/iter3/prd_analyst_web_flow.md`

## User stories covered

7, 8, 9, 10, 11, 12, 13, 14, 15

## What to build

Extend scenario version creation so analysts can create versions either by
pasting editable JSON or by uploading a `.json` file. Every successful save
creates a new immutable version and preserves prior versions unchanged.

This slice should make version history usable enough for an analyst to create
multiple alternatives before running them.

## Acceptance criteria

- [x] The UI supports an editable textarea for pasted JSON.
- [x] The UI supports uploading a `.json` file.
- [x] Pasted JSON and uploaded JSON use the same validation and persistence
      path.
- [x] A new scenario version can be created from an existing version's JSON
      without modifying the original version.
- [x] Previously saved versions cannot be overwritten through the API or UI.
- [x] Version listings show enough metadata to distinguish versions.
- [x] Validation errors are visible in the version creation UI.
- [x] Tests prove pasted and uploaded JSON converge to the same stored version
      behavior.
- [x] Tests prove version immutability.

## Implementation notes

- Added multipart JSON upload support for scenario version creation in both API
  and server-rendered UI.
- Pasted textarea JSON and uploaded `.json` files use the same validation and
  persistence helper before a version is inserted.
- Added `from_version_id` support on the scenario page so an analyst can load a
  previous version's JSON into the editable textarea and save a new version.
- Preserved immutable history through insert-only version creation, monotonic
  per-scenario version numbers, and no overwrite route for existing versions.
- Version listings show version number, case name, schema version, period count,
  and asset counts.

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

BESS-ITER3-002
