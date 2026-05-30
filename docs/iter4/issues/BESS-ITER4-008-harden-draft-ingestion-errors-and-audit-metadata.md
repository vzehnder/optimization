# BESS-ITER4-008: Harden Draft Ingestion Errors And Audit Metadata

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: `docs/iter4/prd_structured_editor_flow.md`

## User stories covered

34 through 41, 46, 49, 60

## What to build

Harden the structured editor ingestion path so errors are clear and promoted
versions retain useful input provenance.

The app should distinguish source-file parsing errors, mapping errors, Python
validation errors, Julia validation errors, and execution errors. Promoted
versions should retain enough metadata to audit the source file and mapping used
to generate the immutable `system_case`.

## Acceptance criteria

- [ ] CSV parsing errors are shown as source-file errors.
- [ ] XLSX parsing errors are shown as source-file errors.
- [ ] Missing or invalid mappings are shown as mapping errors.
- [ ] Data quality failures are shown as Python validation errors.
- [ ] Julia contract failures are shown separately from Python validation
      errors.
- [ ] Run execution failures continue to use the Iteration 3 failed-run audit
      path.
- [ ] Promoted versions retain source filename, source media type, stored source
      path or safe source identifier, mapping metadata, and generation timestamp.
- [ ] Unsafe source-file paths are not exposed through API or UI.
- [ ] Tests cover the error categories and version-level audit metadata.

## Blocked by

BESS-ITER4-005, BESS-ITER4-007
