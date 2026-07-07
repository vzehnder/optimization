# BESS-TS4-005: Record Full Result Lineage With Drift-Proof Constraints

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter4/prd.md`
Fecha de inicio planificada: 2026-07-17
Fecha de termino planificada: 2026-07-20

## User stories covered

4, 5, 20

## What to build

Complete the lineage of indexed results so any result record can be traced to
the exact combination that produced it: run, execution snapshot, case,
topology hash, parameter hash, input variant, date range and the input series
revisions/hashes that TS-3 froze into the run's generation metadata at launch
time. Lineage values must come from that frozen metadata, never from live case
state, so later edits to series, topology or parameters cannot alter what an
existing result claims about its origin.

Constraints (or equivalent write-path guarantees) must prevent result records
from drifting from the run snapshot: results cannot exist without their run,
and cannot disagree with the snapshot's recorded metadata. Legacy runs that
predate TS-3 variant lineage must index with explicitly absent lineage fields
rather than fabricated ones.

## Acceptance criteria

- [ ] Result records store run, execution snapshot, case, topology hash, parameter hash, input variant, date range and input series hashes.
- [ ] Lineage values are copied from the run's frozen generation metadata, not derived from live case state.
- [ ] Constraints or write-path guarantees prevent result records from existing without their run or disagreeing with its snapshot.
- [ ] Legacy runs without TS-3 variant lineage index with absent (not fabricated) lineage fields.
- [ ] Tests prove lineage presence and consistency, including that later edits to live series, topology or parameters leave indexed lineage unchanged.

## Blocked by

BESS-TS4-001
