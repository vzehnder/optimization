# BESS-ITER3-003: Preserve Immutable Version History From Paste Or Upload

Status: Todo
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

- [ ] The UI supports an editable textarea for pasted JSON.
- [ ] The UI supports uploading a `.json` file.
- [ ] Pasted JSON and uploaded JSON use the same validation and persistence
      path.
- [ ] A new scenario version can be created from an existing version's JSON
      without modifying the original version.
- [ ] Previously saved versions cannot be overwritten through the API or UI.
- [ ] Version listings show enough metadata to distinguish versions.
- [ ] Validation errors are visible in the version creation UI.
- [ ] Tests prove pasted and uploaded JSON converge to the same stored version
      behavior.
- [ ] Tests prove version immutability.

## Blocked by

BESS-ITER3-002
