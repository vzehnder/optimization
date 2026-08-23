# BESS-CONFIG-011: Paste And Save Multi-Set Groups Atomically

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: `docs/capa_configuracion/architecture_configuration_layer_final.md`

## What to build

Expand the editable table from a single column to real configured groups that
may span several operational copies. An operator pastes a rectangular Excel
selection, reviews the resulting changes, and saves every touched copy in one
transaction. Ambiguous or invalid input produces public cell coordinates and
no partial revisions, while overflow is visibly truncated and never extends
the time horizon.

## Acceptance criteria

- [ ] A group can display editable and locked columns backed by one or more operational copies.
- [ ] Rectangular paste starts at the anchored cell, skips a header-like first row and reports skipped locked columns.
- [ ] Unambiguous decimal and thousands formats are normalized according to the accepted parser contract.
- [ ] Structurally ambiguous forms including `1.234` and `12,345` are rejected instead of guessed.
- [ ] Number, finiteness, nonnegative, column, period, coverage and optimistic-concurrency validation runs over the entire submission.
- [ ] Errors use group id, column id and row index, report the total count and return at most 100 cell details.
- [ ] One invalid cell or conflict leaves every touched copy, revision, hash and validation dependency unchanged.
- [ ] A valid multi-copy save creates all revisions and refreshes all corresponding copied-set hashes in one transaction.
- [ ] Paste overflow truncates at the configured range, shows a persistent warning and never creates periods.
- [ ] Day, week, month and full-horizon views obey the configured enum and table/chart range contract.
- [ ] The UI virtualizes full-horizon rows, keeps only dirty cells as edit state and offers a non-mandatory review/diff before save.
- [ ] Backend and React tests cover single-copy, multi-copy, invalid, overflow, header, locked-column and full-horizon cases.

## Blocked by

- [BESS-CONFIG-010: Edit One Exposed Series Without Changing Canonical Data](BESS-CONFIG-010-edit-one-exposed-series-without-changing-canonical-data.md)
