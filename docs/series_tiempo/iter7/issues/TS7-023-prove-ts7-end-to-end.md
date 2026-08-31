# TS7-023: Prove TS-7 End To End

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter7/spec_ts7_catalogo_global_y_series_especificas.md` (11.4-11.8)

## What to build

Close the delivery by proving it, in one place, against the definition of done.

Write the TS-7 acceptance narrative covering the eighteen observable stories
H-01 to H-18 and run the full blocking matrix on the development PostgreSQL with
the unittest runner of the repository, module by module. Run the TS-2 to TS-6
suites unedited: the regression policy is that no existing suite is modified to
make it pass, and a test edited without a recorded contract change invalidates
the acceptance.

Run the performance fixture and record AC-PER-01 to AC-PER-07 with their saved
plans. Show the migrator converging and the shadow showing no difference. Do a
manual Chrome verification with the real `.env` credentials across the three
complete flows: link a generic source, create and load an object-specific
series, and attempt the shared load from the object with both of its outcomes.
Finally, show the ledger reconstructs who made every mutation and why.

## Acceptance criteria

- [ ] The whole matrix with `Bloquea = si` is green on the development PostgreSQL, run module by module with the unittest runner.
- [ ] The `test_ts2_acceptance` to `test_ts6_acceptance` suites pass without being edited to accommodate the new model (AC-REG-01).
- [ ] Variant flows, run comparison and the configuration console keep their observable behaviour (AC-REG-03).
- [ ] `tsc`, `eslint`, `vitest` and the production build pass.
- [ ] AC-PER-01 to AC-PER-07 are met on the fixture with their reference plans saved.
- [ ] The migrator converges and the shadow comparison shows no difference.
- [ ] A manual Chrome verification with the real `.env` credentials covers the three complete flows.
- [ ] The ledger reconstructs actor and reason for every mutation in the narrative.
- [ ] Any contract change forced during the delivery is documented with an adapter test preserving the previous shape; no suite is edited silently.

## Blocked by

- [TS7-022: Cut Over To The Single Canonical Writer (C6)](TS7-022-cut-over-to-the-single-canonical-writer.md)
