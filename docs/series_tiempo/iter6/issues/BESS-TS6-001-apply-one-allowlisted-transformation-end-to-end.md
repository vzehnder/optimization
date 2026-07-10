# BESS-TS6-001: Apply One Allowlisted Transformation End-To-End

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter6/prd.md`
Fecha de inicio planificada: 2026-07-14
Fecha de termino planificada: 2026-07-17

## User stories covered

3, 5, 6, 14, 15, 16

## What to build

The tracer bullet for the TS-6 transformation layer: an analyst opens a
validated time-series set in the project catalog, chooses the simplest
allowlisted transformation (`scale_signal`), provides declarative parameters
(target signal and scale factor) validated against a versioned parameter
schema, and executes it. The result is a new derived set in the same catalog,
carrying full lineage: input set, input revision and content hash, validated
parameters, parameter schema version and transformation implementation
version.

The derived set behaves like any natively created set: it is listed in the
project catalog, browsable, and bindable in a case input variant. The catalog
detail page shows a lineage section explaining that the set was derived, from
what inputs and with what parameters, so derived data is explainable without
leaving the UI. The source set is never mutated; the transformation only adds
a new object.

The allowlist is enforced end-to-end: a transformation type outside the
allowlist is rejected, no user-provided script is ever stored or executed
from the database, and parameters that fail schema validation produce a clear
error before anything is written. Validation, execution and lineage recording
live in a deep module testable without the UI. Re-running the same
transformation with identical inputs and parameters converges without
duplicate sets or values.

The slice cuts through every layer with the thinnest possible path: one
transformation type, one execution surface in the UI, one lineage panel and
one binding proof in a variant. Resampling, interpolation, multi-set
combination, staleness and automation belong to later slices.

## Acceptance criteria

- [ ] An analyst can apply `scale_signal` to a validated catalog set from the UI and obtain a new derived set in the project catalog.
- [ ] Transformation types outside the allowlist are rejected, and no user-provided script is stored or executed from the database.
- [ ] Parameters are validated against a versioned parameter schema, and invalid parameters produce a clear error before any write.
- [ ] The derived set records lineage to the input set, input revision/hash, validated parameters, parameter schema version and implementation version, visible in the catalog detail page.
- [ ] The derived set is bindable in a case input variant like any natively created set.
- [ ] The source set remains unchanged and readable after the transformation.
- [ ] Re-running the transformation with identical inputs and parameters converges without duplicate sets, revisions or values.
- [ ] Transformation validation, execution and lineage recording live in a deep module testable without the UI.

## Blocked by

BESS-TS6-000
