# TS7-007: Associate A Generic Signal With An Object Atomically

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter7/spec_ts7_catalogo_global_y_series_especificas.md` (4.2, 4.6, 4.7, 6.8, 6.9)

## What to build

Make the catalog association a real, audited, atomic operation. Deliver
`GET /associations`, its detail and its append-only event history, plus the only
mutation path there is: `POST /association-prevalidations` followed by
`POST /association-batches`.

Prevalidation writes nothing at all - running it twice leaves the database
byte-identical - and returns per-row verdicts from the same evaluator the
confirmation uses. The batch is all-or-nothing up to 200 operations: one
incompatible row rejects the whole batch with `TS_LINK_BATCH_REJECTED` and
leaves no partial success. This endpoint is in the MVP even though the dense
tabular selection surface is not; what is deferred is the UI, not the contract.

Between prevalidation and confirmation the world can move. If it did, the
confirmation refuses with `TS_LINK_PRECONDITION_CHANGED` rather than applying a
verdict computed against a state that no longer exists. A `project` source
against another project's object is refused with
`TS_COMPAT_SCOPE_NOT_ACCESSIBLE` even when the earlier prevalidation passed.

Every mutation leaves actor, reason, `request_id` and timestamp in the link
ledger, and every failure confirms that nothing was written.

## Acceptance criteria

- [ ] Prevalidation writes nothing: repeating it leaves the database identical (AC-ASO-01).
- [ ] A batch with one incompatible row is rejected whole with `TS_LINK_BATCH_REJECTED` and leaves no partial successes (AC-ASO-02).
- [ ] The batch accepts up to 200 operations and is all-or-nothing at that size.
- [ ] A `project` source against another project's object returns `TS_COMPAT_SCOPE_NOT_ACCESSIBLE` even after a passing prevalidation (AC-ASO-04).
- [ ] A world-state change between prevalidation and confirmation returns `TS_LINK_PRECONDITION_CHANGED` (AC-ASO-05).
- [ ] Association events are append-only and paginated; no public route deletes one.
- [ ] Every mutation records actor, reason, `request_id` and moment in a ledger no public route can erase (AC-SEG-05).
- [ ] A mutation error confirms no write happened and preserves the caller's draft and filters (AC-SEG-07 backend half).
- [ ] Prevalidating 200 associations meets 2 s p95 and committing a 200-row batch meets 2 s p95 without lock wait (AC-PER-05, AC-PER-06).
- [ ] Replaying the same idempotency key returns the original result instead of creating a second batch.

## Blocked by

- [TS7-006: Read The Global Catalog Signal First](TS7-006-read-the-global-catalog-signal-first.md)
