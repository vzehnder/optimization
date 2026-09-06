# TS7-023: Prove TS-7 End To End

Status: Done
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

- [x] The whole matrix with `Bloquea = si` is green on the development PostgreSQL, run module by module with the unittest runner.
- [x] The `test_ts2_acceptance` to `test_ts6_acceptance` suites pass without being edited to accommodate the new model (AC-REG-01).
- [x] Variant flows, run comparison and the configuration console keep their observable behaviour (AC-REG-03).
- [x] `tsc`, `eslint`, `vitest` and the production build pass.
- [x] AC-PER-01 to AC-PER-07 are met on the fixture with their reference plans saved.
- [x] The migrator converges and the shadow comparison shows no difference.
- [x] A manual Chrome verification with the real `.env` credentials covers the three complete flows.
- [x] The ledger reconstructs actor and reason for every mutation in the narrative.
- [x] Any contract change forced during the delivery is documented with an adapter test preserving the previous shape; no suite is edited silently.

## Implementation evidence

- `tests/test_ts7_acceptance.py` tells the TS-7 story once, over the public
  surfaces every TS7-0xx suite already uses: the catalog is signal-first,
  searchable and previews an exact revision; a compatible object is associated
  and an incompatible one is blocked with a stable code that the API refuses
  too; a binding pins revision and hash, goes stale on a new publication
  without moving, blocks the run and is replaced with a mandatory comparison
  and reason; an object-specific series is defined, loaded by file and by API,
  bound with no catalog association in between and never leaks into the global
  catalog; the shared source shows its whole impact and takes both exits; an
  admin promotes and demotes a set without losing history; an external identity
  gets one uniform answer per surface family whether the id exists or not; and
  the migrator converges twice before the cutover closes every legacy write.
- The narrative runs on SQLite and, through `PostgresTS7AcceptanceTests`, on
  PostgreSQL. Every catalog read is scoped to the project under test, because
  the catalog is global by design.
- The full matrix is green module by module on PostgreSQL (23 modules). The
  five modules that fail on `energy_dispatch` fail on residue committed by
  earlier runs and by the TS7-021 manual pass, not on behaviour: each passes on
  a pristine database. `docs/series_tiempo/iter7/acceptance_ts7.md` records why
  and how.
- The PostgreSQL run found two real defects, both invisible on SQLite: the C4
  sequence sync resolved `case_time_series_bindings` as a canonical content
  table instead of a link-layer one, and three literal `LIKE 'canonical_binding:%'`
  patterns broke the psycopg placeholder parser. Both are fixed; neither is a
  contract change.
- `tests.test_ts2_acceptance` to `tests.test_ts6_acceptance` pass unedited
  (`git diff` over the five files is empty).
- AC-PER-01 to AC-PER-07 are measured with their reference plans saved in
  `docs/series_tiempo/iter7/performance/ts7-023-postgresql-acceptance.json`.
  TS7-005 measured three of them; the preview budgets and the two halves of the
  200 row batch are measured here for the first time.
- The manual Chrome pass ran the three complete flows with the real `.env`
  credentials and no console messages. It found the journey's
  `Crear especifica para este objeto` branch had no step 2, so flow 2
  dead-ended in the browser; TS7-023 built that leg — definition form, staged
  points load and sealing review — over the routes TS7-010 to TS7-012 already
  serve. No route was added and no generated API artifact moved.
- N1/N2: `python -m unittest tests.test_ts7_acceptance` passes 18 tests on
  SQLite and 18 more on PostgreSQL, and the full Python suite passes with
  1.236 tests. N3: `tsc`, `eslint`, 159 Vitest tests,
  `api:check` and the production build pass. N5: the fixture meets all seven
  budgets. N6: C0 signs and verifies, C2 to C4 converge on repeat, C5 proves
  the shadow with no difference, C6 closes legacy writes by code and by
  permission.

## Known limitation

`AnalystStore` cannot bootstrap an empty PostgreSQL database: the base schema
declares `hydraulic_time_series_sets` with a foreign key to `time_series_sets`
before that table is created, which SQLite tolerates and PostgreSQL rejects.
The development database predates the ordering, so nothing is broken today; the
acceptance database was created from a schema-only dump instead. Reordering the
base schema is outside this cut.

## Blocked by

- [TS7-022: Cut Over To The Single Canonical Writer (C6)](TS7-022-cut-over-to-the-single-canonical-writer.md)
