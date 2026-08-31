# TS7-022: Cut Over To The Single Canonical Writer (C6)

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter7/spec_ts7_catalogo_global_y_series_especificas.md` (10.2 C6, 10.8, 10.9, 11.1, 11.7)

## What to build

The precise moment writes with the old model stop existing. Enable the canonical
reads and the canonical writer for everyone, turn the old routes into adapters
over that writer, make direct legacy writes impossible by code and by
permissions, and release the mutation pause.

The existing contracts keep their shape: `GET /api/time-series/signal-catalog`
and the current set routes answer the same as before, now served canonically.
Temporary aliases stay live through the compatibility window, and the TS-5
hydraulic adapter with its on-demand migration keeps working. Previous rows stay
read-only - nothing is deleted, renumbered, or rewritten into historical
snapshots. Contraction (C7) is not authorized inside this delivery.

After the first canonical write there is no return to the legacy writer: the
only responses are pausing mutations, keeping canonical reads live, and rolling
forward. Land the rollback triggers as monitored conditions, not as prose: the
zero-tolerance list, the measured thresholds, the 72-hour observation window and
the 30-day compatibility window with daily reconciliation.

## Acceptance criteria

- [ ] After the cutover, a direct write to the legacy points, signals or bindings tables fails by code and by permissions (AC-MIG-06).
- [ ] `GET /api/time-series/signal-catalog` and the current set routes keep their shape, served by the canonical writer (AC-REG-02).
- [ ] Legacy hydraulic series stay visible through the adapter with their migration state (AC-LEG-01).
- [ ] Every new link ends in the generic model, even when it starts from a legacy view (AC-LEG-02).
- [ ] No cache or read model turns an internal response into an external one (AC-SEG-06).
- [ ] The catalog and object surfaces open to regular internal users at this point and not before (11.1).
- [ ] Previous rows remain read-only: nothing is deleted, renumbered or rewritten; C7 is not executed.
- [ ] The zero-tolerance triggers and the measured thresholds are monitored and fire observably in a test.
- [ ] Daily reconciliation runs through the compatibility window and any non-reconciling row raises.
- [ ] The TS-5 hydraulic adapter and its on-demand migration still work (AC-REG-04).

## Blocked by

- [TS7-009: Materialize A Run From Its Bindings](TS7-009-materialize-a-run-from-its-bindings.md)
- [TS7-018: Compare Canonical Reads In Shadow And Prove Convergence (C5)](TS7-018-compare-canonical-reads-in-shadow-and-prove-convergence.md)
- [TS7-021: Build The Single Protected Mutation Journey](TS7-021-build-the-single-protected-mutation-journey.md)
