# BESS-TS6-004: Combine Series From Multiple Sets Into A Derived Set

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter6/prd.md`
Fecha de inicio planificada: 2026-07-24
Fecha de termino planificada: 2026-07-27

## User stories covered

4, 5, 6

## What to build

Add the first multi-input transformation to the allowlist: an analyst
composes a derived set by taking signals from two or more existing sets, so
scenarios can be assembled from independently versioned pieces (for example
prices from one set and demand from another, or a composed price scenario
from two price sets).

The transformation is declarative: parameters name each input set, the
revision to read and which signals to take from it, validated against a
versioned parameter schema. Inputs must be temporally compatible — same
resolution and overlapping horizon for the requested range — and
incompatibilities fail with a clear message naming the offending input,
instead of producing a silently misaligned set.

The lineage contract from the tracer bullet extends naturally to multiple
inputs: the derived set records every input set, its revision/hash and which
signals it contributed, so the composition is fully explainable. This slice
proves the transformation framework is not shaped around single-input
operations only.

## Acceptance criteria

- [ ] An analyst can compose a derived set from signals of two or more existing sets from the UI.
- [ ] Input selection (set, revision, signals) is declarative and validated against a versioned parameter schema.
- [ ] Temporally incompatible inputs (resolution mismatch, insufficient horizon overlap) fail with a clear message naming the offending input; nothing is written.
- [ ] The derived set records lineage to every input set, its revision/hash and the signals it contributed, visible in the catalog detail page.
- [ ] The derived set is bindable in a case input variant and usable in a run end-to-end.
- [ ] The combination implementation is a pure/deep module covered by tests without the UI.

## Blocked by

BESS-TS6-001
