# BESS-ITER4-004: Upload And Preview A CSV Time-Series Source

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: `docs/iter4/prd_structured_editor_flow.md`

## User stories covered

22, 24, 26 through 29, 34 through 41, 58

## What to build

Add CSV source ingestion for draft time-series data.

An analyst can upload a CSV file, the app stores the original source file under
a controlled input-source area, previews rows and columns, suggests mappings for
common columns, lets the analyst confirm or correct mappings, and validates the
mapped data before it can be used to generate a `system_case`.

## Acceptance criteria

- [ ] A draft can receive a CSV source file upload.
- [ ] Uploaded CSV source files are stored under a configured safe source-file
      root.
- [ ] The app returns preview rows and detected column names for the uploaded
      CSV.
- [ ] The app suggests mappings for common columns such as timestamp, duration,
      legacy price, import price, export price, renewable availability, and load
      demand.
- [ ] The analyst can save manual mapping corrections.
- [ ] Validation catches missing required mappings.
- [ ] Validation catches nonnumeric mapped numeric values.
- [ ] Validation catches duplicate or unsorted timestamps.
- [ ] Validation catches nonpositive durations.
- [ ] Validation catches negative renewable availability and load demand.
- [ ] Tests cover CSV parsing, preview, source-file safety, mapping suggestions,
      manual overrides, and validation errors.

## Blocked by

BESS-ITER4-002
