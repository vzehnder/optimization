# TS7-007: Associate A Generic Signal With An Object Atomically

Status: In Review
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

- [x] Prevalidation writes nothing: repeating it leaves the database identical (AC-ASO-01).
- [x] A batch with one incompatible row is rejected whole with `TS_LINK_BATCH_REJECTED` and leaves no partial successes (AC-ASO-02).
- [x] The batch accepts up to 200 operations and is all-or-nothing at that size.
- [x] A `project` source against another project's object returns `TS_COMPAT_SCOPE_NOT_ACCESSIBLE` even after a passing prevalidation (AC-ASO-04).
- [x] A world-state change between prevalidation and confirmation returns `TS_LINK_PRECONDITION_CHANGED` (AC-ASO-05).
- [x] Association events are append-only and paginated; no public route deletes one.
- [x] Every mutation records actor, reason, `request_id` and moment in a ledger no public route can erase (AC-SEG-05).
- [x] A mutation error confirms no write happened and preserves the caller's draft and filters (AC-SEG-07 backend half).
- [ ] Prevalidating 200 associations meets 2 s p95 and committing a 200-row batch meets 2 s p95 without lock wait (AC-PER-05, AC-PER-06).
- [x] Replaying the same idempotency key returns the original result instead of creating a second batch.

## Implementation evidence

- `app/time_series_associations.py` owns canonical request normalization, the
  five-minute actor-bound HMAC prevalidation token, commit ETags and stable
  `TS_LINK_*` / idempotency error envelopes.
- `app/persistence.py` exposes the association list, detail and independent
  signed event cursor, derives `active_valid`, `active_stale`,
  `active_incompatible` and `archived`, and implements add, replace, archive and
  revalidate through one transaction. Commit claims durable idempotency first,
  locks sets, objects and existing associations in deterministic ID order on
  PostgreSQL, reauthorizes and re-evaluates the whole batch, then writes one
  batch or rolls everything back.
- `app/main.py` exposes the three read routes plus the two-phase mutation
  routes. The commit requires `If-Match`, `Idempotency-Key`, the opaque token
  and explicit confirmation where needed; failed commits return the normalized
  draft and never expose a delete route.
- `tests.test_ts7_007_catalog_associations` covers the public HTTP/domain seams:
  read-only repeatable prevalidation, all four actions, a full 200-row commit,
  mixed-batch rollback, scope and revision races, durable replay beyond token
  expiry, actor binding, conflict cases, immutable audit evidence, effective
  states and independent cursor tampering. The same create/replay/rollback
  contract passes on the configured PostgreSQL engine; five disjoint 200-row
  PostgreSQL batches also keep every observed prevalidation and commit sample
  below the 2 s operation budget.
- Verification on 2026-09-01: 76 focused TS7-004 through TS7-007 tests pass
  (11 environment-gated variants skipped); the explicit TS7-007 PostgreSQL
  contract passes; OpenAPI generation and drift check, generated-schema
  formatting and the frontend production build pass. The full Python regression
  also passes 964 tests with 26 environment-gated skips. The build retains its
  pre-existing warning for the JavaScript chunk over 500 kB.
- AC-PER-05 and AC-PER-06 remain open because the configured database contains
  only a development-scale catalog, not the normative 100,000-entry / 1,000,000-
  association N5 fixture. The five-sample development guard is useful regression
  evidence but is not presented as normative p95 acceptance evidence.

## Blocked by

- [TS7-006: Read The Global Catalog Signal First](TS7-006-read-the-global-catalog-signal-first.md)
