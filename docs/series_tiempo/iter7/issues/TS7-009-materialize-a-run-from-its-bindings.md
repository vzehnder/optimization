# TS7-009: Materialize A Run From Its Bindings

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter7/spec_ts7_catalogo_global_y_series_especificas.md` (4.8, 2.7)

## What to build

Close the execution path: turn the effective bindings of a variant into the
immutable snapshot a run executes from, inside its `scenario_version`, in one
transaction.

Materialization resolves each binding to its pinned revision and hash, verifies
the hash it recorded still matches what it reads, and writes the exact lineage
into the run so the question "which revision did this run use" is answerable
years later without depending on the current pointer. A stale or invalid binding
does not materialize - it blocks the run - and an interrupted materialization
leaves no partial snapshot.

Result indices stay where they are. TS-4 results remain separately indexed and
rebuildable, and are not fused with inputs.

## Acceptance criteria

- [ ] A run keeps the exact lineage of every binding inside its immutable `scenario_version` (AC-BIN-07).
- [ ] Materialization verifies the pinned hash against what it reads and refuses on mismatch.
- [ ] A stale or invalid binding blocks the run instead of materializing a guess.
- [ ] An interrupted materialization leaves no partially visible snapshot.
- [ ] TS-4 result indices stay rebuildable and are not merged with inputs (AC-LEG-04).
- [ ] Re-materializing an already materialized scenario version is idempotent.

## Blocked by

- [TS7-008: Pin A Binding To An Exact Revision And Detect Staleness](TS7-008-pin-a-binding-to-an-exact-revision-and-detect-staleness.md)
