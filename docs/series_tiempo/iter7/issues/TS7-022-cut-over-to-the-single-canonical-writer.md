# TS7-022: Cut Over To The Single Canonical Writer (C6)

Status: In Review
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

- [x] After the cutover, a direct write to the legacy points, signals or bindings tables fails by code and by permissions (AC-MIG-06).
- [x] `GET /api/time-series/signal-catalog` and the current set routes keep their shape, served by the canonical writer (AC-REG-02).
- [x] Legacy hydraulic series stay visible through the adapter with their migration state (AC-LEG-01).
- [x] Every new link ends in the generic model, even when it starts from a legacy view (AC-LEG-02).
- [x] No cache or read model turns an internal response into an external one (AC-SEG-06).
- [x] The catalog and object surfaces open to regular internal users at this point and not before (11.1).
- [x] Previous rows remain read-only: nothing is deleted, renumbered or rewritten; C7 is not executed.
- [x] The zero-tolerance triggers and the measured thresholds are monitored and fire observably in a test.
- [x] Daily reconciliation runs through the compatibility window and any non-reconciling row raises.
- [x] The TS-5 hydraulic adapter and its on-demand migration still work (AC-REG-04).

## Implementation evidence

- `cut_over_time_series_c6` repeats the final live convergence gate under the
  legacy mutation pause, installs independent code and database barriers, then
  durably enables canonical reads, writes and compatibility aliases. Its
  manifest fixes the 72-hour observation period, 30-day daily-reconciliation
  period, minimum 90-day alias sunset and roll-forward-only response.
- The legacy set catalog, detail, revision, manual-edit, file-replacement and
  binding routes now project or publish through the canonical model. Reads keep
  their TS-2 JSON shape and advertise `Deprecation`, RFC `Sunset`, successor
  `Link` and a private canonical-model marker. Writes require `If-Match` and
  `Idempotency-Key`; retries cannot create a second revision.
- C6 installs SQLite mutation triggers on every legacy content table and emits
  the equivalent PostgreSQL trigger plus `REVOKE INSERT, UPDATE, DELETE FROM
  PUBLIC` statements. The three AC-MIG-06 tables are asserted explicitly and
  the wider legacy closure, including hydraulic rows, is also read-only.
- The TS-5 adapter preserves its legacy read and migration-state response, but
  on-demand migration publishes a canonical catalog set and records a separate
  compatibility ledger. A set created this way is readable through both the
  canonical surface and the temporary legacy alias.
- All seven zero-tolerance conditions and the three measured thresholds are
  executable telemetry inputs. One occurrence records a blocking C6 anomaly,
  pauses canonical mutations, leaves reads active and requires roll-forward.
  Daily projection reconciliation records each day and raises on one divergent
  row.
- N2: `python -m unittest tests.test_ts7_022_c6_cutover` passes 11 tests. The
  directed TS2/TS5/C0-C6 regression passes 142 tests (7 environment skips), and
  full discovery passes 1,214 tests (111 optional-integration skips).
- N3: generated OpenAPI verification, TypeScript, ESLint, Vitest (158 tests),
  and the production build pass. The two regenerated API artifacts pass
  Prettier; the repository-wide Prettier check still reports the same 25
  pre-existing files outside this change.
- No C7 operation, deletion or historical renumbering is introduced. The live
  PostgreSQL integration remains opt-in because `POSTGRES_TEST_DATABASE_URL`
  was not available; its C6 permission script is covered as a generated
  contract in the focused suite.

## Blocked by

- [TS7-009: Materialize A Run From Its Bindings](TS7-009-materialize-a-run-from-its-bindings.md)
- [TS7-018: Compare Canonical Reads In Shadow And Prove Convergence (C5)](TS7-018-compare-canonical-reads-in-shadow-and-prove-convergence.md)
- [TS7-021: Build The Single Protected Mutation Journey](TS7-021-build-the-single-protected-mutation-journey.md)
