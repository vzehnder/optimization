# TS7-018: Compare Canonical Reads In Shadow And Prove Convergence (C5)

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter7/spec_ts7_catalogo_global_y_series_especificas.md` (10.2 C5, 10.3, 10.8, 10.9)

## What to build

Prove the canonical reads are right before they serve any traffic, and prove the
migrator has stopped moving.

Run canonical reads in shadow over a wide sample and compare them against the
legacy reads on semantics, counts, values, hashes, authorization and lineage. In
the same phase, compare the persisted projection against the
`TIME_SERIES_SIGNAL_CATALOG` Python registry, which is the last check before the
database becomes authoritative. Drain the dirty-roots journal with a short
mutation pause so the comparison is taken against a settled source.

Convergence is the gate: a final run over an unmutated source creates zero rows,
changes zero mappings and reproduces the same manifest. Any single shadow
difference is a zero-tolerance rollback trigger, not a finding to triage later.

## Acceptance criteria

- [ ] Shadow comparison shows no difference in semantics, counts, values, hashes, authorization or lineage (AC-MIG-05).
- [ ] The final run demonstrates convergence: zero new rows, zero mapping changes and the same manifest (AC-MIG-02).
- [ ] The persisted projection matches the `TIME_SERIES_SIGNAL_CATALOG` registry, and a divergence stops the phase.
- [ ] The dirty-roots journal drains to empty under a short mutation pause and the comparison runs against the settled source.
- [ ] The sample is wide enough to cover every set state, every object family and both `series_kind` values, and its selection is recorded.
- [ ] A single shadow difference halts the advance and is reported as a rollback trigger.
- [ ] Legacy hydraulic series and their on-demand migration keep working throughout the phase (AC-LEG-01 read half).

## Blocked by

- [TS7-017: Resolve Associations And Bindings With Typed Anomalies (C4)](TS7-017-resolve-associations-and-bindings-with-typed-anomalies.md)
