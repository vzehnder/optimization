# BESS-TS6-000: Review TS-6 PRD And Transformation Semantics

Status: Todo
Type: HITL
Triage: ready-for-agent
Source: `docs/series_tiempo/iter6/prd.md`
Fecha de inicio planificada: 2026-07-13
Fecha de termino planificada: 2026-07-13

## User stories covered

1 through 18

## What to build

Review and accept the TS-6 PRD before implementation starts. TS-6 adds a
declarative transformation layer and automation on top of the common model
consolidated in TS-5: transformations take one or more input sets, validated
parameters and an allowlisted implementation version, and produce a new set or
derived revision with full lineage; automation runs cases using topology,
parameters, input variant and date range, generating snapshots exactly like
the manual flow.

The review must first close the activation decision the PRD itself raises
(user story 18): TS-6 was deliberately deferred until real usage justifies it,
so acceptance must confirm there is enough real usage of the TS-2 through
TS-5 model to know which transformations are worth building, or explicitly
record that the iteration starts anyway and why.

It must also close the decisions the PRD leaves open: the initial allowlist
catalog of transformation types and which ones ship in this iteration; whether
a transformation output is a new set or a derived revision of an existing set,
and when each applies; the exact lineage contract (input sets, input
revisions, validated parameters, parameter schema version and implementation
version); how derived-set staleness composes with the TS-3 variant staleness
already in place; the first external connector target and its mocking
strategy for tests; the scheduling mechanism (in-process scheduler, cron-like
trigger or external invocation) and who may define or execute schedules under
the TS-5 permission matrix; and confirmation that physical storage
optimizations such as partitioning or TimescaleDB stay out of scope until
real volume is measured.

The outcome should be a short accepted-decision record in the iteration docs
at `docs/series_tiempo/iter6/decision_record_ts6_transformation_semantics.md`,
including any corrections to the PRD if scope, allowlist or automation
semantics need adjustment before downstream issues begin.

## Acceptance criteria

- [ ] The activation decision (start TS-6 now versus keep deferring) is explicitly recorded with its justification, per user story 18.
- [ ] The initial allowlist of transformation types is decided, including which transformations this iteration ships and which stay future.
- [ ] The output model is decided: when a transformation produces a new set versus a derived revision, and how derived objects are named and versioned.
- [ ] The lineage contract is agreed: input sets, input revisions/hashes, validated parameters, parameter schema version and implementation version.
- [ ] Derived-set staleness semantics are agreed, including how they compose with the existing TS-3 variant staleness and TS-5 fail-closed guarantees.
- [ ] The first external connector target and its test mocking strategy are decided, keeping ingestion inside the existing source/set model.
- [ ] The scheduling mechanism and its permission rules (who defines, who executes, who sees results) are agreed under the TS-5 permission matrix.
- [ ] Physical storage optimizations (partitioning, TimescaleDB) are confirmed out of scope until real volume is measured.
- [ ] Any PRD correction is committed before downstream TS-6 implementation issues begin.

## Blocked by

None - can start immediately.
