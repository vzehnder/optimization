# BESS-REACT-005: Migrate Case Validation And Versioning

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: `docs/react_migration/prd_react_ui_migration.md`

## User stories covered

43 through 52

## What to build

Complete the model-authoring loop in React. An analyst can generate and inspect
the exact `system_case`, validate it through the existing Julia boundary,
promote a still-valid snapshot to an immutable scenario version, and retain the
expert paste/upload version workflow.

The UI must make generation, Python validation, Julia validation, stale
validation, and promotion outcomes distinct without changing the underlying
optimizer contract.

## Acceptance criteria

- [ ] The draft editor can request and display a formatted generated
      `system_case` preview.
- [ ] Generation errors navigate or link the analyst to the relevant
      configuration, asset, or source section.
- [ ] Validation executes through the existing backend-to-Julia validation
      boundary.
- [ ] Validation phase, status, message, and structured details are rendered
      clearly.
- [ ] The latest validation snapshot remains visible after refresh.
- [ ] Editing the draft after validation makes the prior result visibly stale
      and prevents promotion.
- [ ] A current valid generated case can be promoted to one immutable scenario
      version.
- [ ] Duplicate submission protection prevents accidental double promotion.
- [ ] The expert workflow can create a version from pasted JSON or a UTF-8 JSON
      upload.
- [ ] Malformed and domain-invalid JSON returns actionable errors and creates no
      version.
- [ ] Version detail exposes stored metadata and the exact immutable input.
- [ ] Eligible versions can be deleted while versions referenced by runs remain
      protected.
- [ ] Browser acceptance proves draft generation through promotion plus paste,
      upload, stale-validation, and protected-delete paths.
- [ ] Existing validation, generated-case, version history, and Julia-facing
      acceptance tests remain green.

## Blocked by

- BESS-REACT-004

