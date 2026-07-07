# BESS-TS4-006: Make Result Indexing Idempotent And Failure-Safe

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter4/prd.md`
Fecha de inicio planificada: 2026-07-21
Fecha de termino planificada: 2026-07-22

## User stories covered

2, 19

## What to build

Harden the result-indexing write path so it is safe to retry and can never
damage a successful run. Indexing the same run twice must converge to the same
indexed state without duplicate records. Retrying after a partial failure
(some series written, then an interruption) must complete the index correctly
rather than duplicating or corrupting it.

An indexing failure must never change the run's `succeeded` status, never
touch its registered artifacts and never block the analyst from reading
results through the artifact path. Failures must be visible (status or log
that identifies the affected run) so the run can be re-indexed later, with the
artifacts remaining the source from which BBDD results can be reconstructed.

## Acceptance criteria

- [ ] Re-indexing an already-indexed run converges without duplicate records.
- [ ] Retrying after a simulated partial failure completes the index correctly.
- [ ] An indexing failure leaves the run `succeeded` and its artifacts untouched, and the run's results remain readable from artifacts.
- [ ] Indexing failures are surfaced so affected runs can be identified and re-indexed.
- [ ] Tests prove idempotent re-indexing and partial-failure retry against representative artifacts.

## Blocked by

BESS-TS4-001
