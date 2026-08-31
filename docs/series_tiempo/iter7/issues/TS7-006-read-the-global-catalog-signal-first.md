# TS7-006: Read The Global Catalog Signal First

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter7/spec_ts7_catalogo_global_y_series_especificas.md` (6.1-6.11)

## What to build

Open the read surface of the global catalog as three separate resources that
share conventions but never a polymorphic list or a shared cursor: `inputs` for
canonical input signals, `results` read-only, and `legacy` as the adapter for
old series and their migration state. Keeping the identities apart is what stops
a result id from being mistaken for a `time_series_signals.id`.

Deliver `GET /inputs` as a signal-first list across every project the caller may
see, with combinable filters over text, semantic type, class, scope, linked
object, state, unit, coverage and resolution; keyset cursor pagination with
`has_more`; and owner and scope visible on every row. Deliver the detail with
contract, provenance, current revision and hash; the paginated revision history;
the bounded preview of an exact revision; `descriptors` for filters and
selectors; and `object-candidates` for a role and use, answered by the single
evaluator so an incompatible candidate is explained and unselectable.

The surface is internal only. `external` is refused before any id is resolved or
any query runs, and the refusal reveals no existence, count or identifier.
Knowing an id never skips the object or project authorization, and there is no
detail route without the same gate the list uses.

## Acceptance criteria

- [ ] The list returns one row per signal with owner, scope, type, class, unit, coverage and resolution (AC-CAT-01).
- [ ] Combinable filters produce the same set as the equivalent query over the canonical tables (AC-CAT-02).
- [ ] A tampered or expired cursor returns `TS_QUERY_CURSOR_MISMATCH` or `TS_QUERY_CURSOR_EXPIRED`, never a quietly different page (AC-CAT-03).
- [ ] An archived signal still reads and keeps its history but accepts no new associations, bindings or revisions (AC-CAT-07).
- [ ] The detail exposes complete contract, provenance, current revision and hash (AC-DET-01).
- [ ] Revision history pages immutable metadata and does not move the current pointer (AC-DET-02).
- [ ] A preview over the limit returns `TS_PREVIEW_TOO_LARGE` instead of truncating silently (AC-DET-03).
- [ ] The preview always cites the exact revision queried, never an implicit `current_revision_id` (AC-DET-04).
- [ ] `object-candidates` explains incompatible candidates and never returns one as selectable.
- [ ] `external` is refused across the whole surface before ids are resolved, revealing no existence, count or identifier (AC-SEG-01, AC-SEG-02).
- [ ] Knowing a `signal_id` does not bypass object or project authorization, and detail uses the same gate as the list (AC-SEG-03, AC-SEG-04).
- [ ] A 500-point preview meets 500 ms p95 and a 2.000-point preview meets 1 s p95 on the fixture (AC-PER-03, AC-PER-04).

## Blocked by

- [TS7-005: Project The Catalog Transactionally With Its Performance Fixture](TS7-005-project-the-catalog-transactionally-with-its-performance-fixture.md)
