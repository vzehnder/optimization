# TS-7 Acceptance Record (TS7-023)

Closing evidence for `docs/series_tiempo/iter7/spec_ts7_catalogo_global_y_series_especificas.md`,
chapters 11.4 to 11.8. Every claim here is the result of a run, not a plan.

Date: 2026-09-06. Branch `series_tiempo`.

## 1. The Blocking Matrix On PostgreSQL

The whole matrix with `Bloquea = si` is green, run module by module with the
repository's `unittest` runner against PostgreSQL.

| Module | Result |
| --- | --- |
| `tests.test_ts7_001_classification_catalog` | 19 tests, OK |
| `tests.test_ts7_002_canonical_content_model` | 16 tests, OK |
| `tests.test_ts7_003_linkable_object_register` | 19 tests, OK |
| `tests.test_ts7_004_link_layer` | 15 tests, OK |
| `tests.test_ts7_005_catalog_projection` | 25 tests, OK |
| `tests.test_ts7_006_catalog_read_api` | 17 tests, OK |
| `tests.test_ts7_007_catalog_associations` | 19 tests, OK |
| `tests.test_ts7_008_case_time_series_bindings` | 18 tests, OK |
| `tests.test_ts7_009_run_materialization` | 8 tests, OK (2 skips) |
| `tests.test_ts7_010_object_specific_series` | 50 tests, OK (1 skip) |
| `tests.test_ts7_011_object_specific_file_ingestion` | 32 tests, OK |
| `tests.test_ts7_012_object_specific_binding_and_archive` | 16 tests, OK |
| `tests.test_ts7_013_shared_generic_revision` | 30 tests, OK |
| `tests.test_ts7_014_scope_changes` | 15 tests, OK |
| `tests.test_ts7_015_c0_inventory_and_manifest` | 22 tests, OK |
| `tests.test_ts7_016_c2_c3_backfill` | 18 tests, OK |
| `tests.test_ts7_017_c4_links_backfill` | 7 tests, OK |
| `tests.test_ts7_018_c5_shadow_convergence` | 14 tests, OK |
| `tests.test_ts7_019_layered_catalog_surface` | 5 tests, OK |
| `tests.test_ts7_020_contextual_object_summary` | 4 tests, OK |
| `tests.test_ts7_021_protected_journey_preconditions` | 1 test, OK |
| `tests.test_ts7_022_c6_cutover` | 11 tests, OK |
| `tests.test_ts7_acceptance` | 18 tests, OK |

### The database each module runs against

The PostgreSQL contract classes assert over the **whole** database: totals of
catalog entries, of associations, of legacy sets the migrator must convert. The
development database `energy_dispatch` carries committed rows from earlier runs
and from the TS7-021 manual verification, so those totals do not hold there.

The matrix therefore runs on `energy_dispatch_ts7_acceptance`, a database on the
same development server, created from a schema-only dump of `energy_dispatch`
and reset before each module. That is the same server, the same schema and the
same engine; only the residue is gone. Running the matrix against
`energy_dispatch` as it stands today fails five modules on that residue alone
(007, 010, 012, 016, 017), and each of those five passes on a pristine database.

A fresh PostgreSQL database cannot be created by `AnalystStore` alone: the
schema script declares `hydraulic_time_series_sets` with a foreign key to
`time_series_sets` before that table exists, which SQLite tolerates and
PostgreSQL does not. The development database predates the ordering and was
migrated incrementally, so the defect is invisible there. It is recorded here
rather than fixed, because reordering the base schema is outside this cut.

## 2. Two Defects The PostgreSQL Run Found

Both were invisible on SQLite and on the earlier opt-in-skipped runs.

- **C4 sequence sync resolved a link-layer table as a canonical one.**
  `_c4_insert_binding` called `_sync_canonical_identity_sequences(("case_time_series_bindings",))`,
  but that table belongs to the link layer, not to the canonical content model,
  so the resolver raised `KeyError: unknown canonical table`. Only PostgreSQL
  syncs identities, so C4 could never migrate a binding there. The sync now
  resolves a logical name in whichever of the two spaces owns it.
- **Three `LIKE 'canonical_binding:%'` literals broke the psycopg parser.**
  The driver reads a literal `%` in the statement text as a placeholder and
  refused the statement outright, which stopped `read_time_series_c4_cutover_gate`
  and the two binding-history reads. The pattern is now bound as a parameter
  (`CANONICAL_BINDING_KIND_PATTERN`).

Neither is a contract change: no request or response shape moved, and no
existing test was edited. `tests.test_ts7_017_c4_links_backfill` and
`tests.test_ts7_018_c5_shadow_convergence` fail before the fixes and pass after,
on PostgreSQL, unedited.

## 3. Regression, TS-2 To TS-6 (AC-REG-01, AC-REG-03)

| Suite | Result |
| --- | --- |
| `tests.test_ts2_acceptance` | 2 tests, OK |
| `tests.test_ts3_acceptance` | 2 tests, OK |
| `tests.test_ts4_acceptance` | 2 tests, OK |
| `tests.test_ts5_acceptance` | 9 tests, OK |
| `tests.test_ts6_acceptance` | 8 tests, OK |

`git diff` over those five files is empty: none of them was edited to
accommodate the new model. Variant flows, run comparison and the configuration
console keep their observable behaviour, checked both by their own suites and by
the manual regression pass of `pruebas_manuales_ts7.md`.

The full Python suite passes: **1.236 tests, 119 optional-integration skips**.

## 4. Frontend Gates

`npx tsc -b`, `npx eslint .`, `npm test -- --run` (159 tests, 14 files),
`npm run api:check` and `npm run build` all pass. The generated API artifacts
(`frontend/openapi.json`, `frontend/src/api/schema.ts`) are unchanged, because
the frontend work of this cut added no route.

## 5. Performance (AC-PER-01 To AC-PER-07)

Run on `energy_dispatch_ts7_performance`, a dedicated database on the same
server, at `--scale 0.001 --repetitions 100`, with the reference plans saved in
[`performance/ts7-023-postgresql-acceptance.json`](performance/ts7-023-postgresql-acceptance.json).

| ID | Operation | Budget | p95 | Median |
| --- | --- | --- | --- | --- |
| AC-PER-01 | 50 row catalog page without facets | 300 ms | 3.178 ms | 1.909 ms |
| AC-PER-02 | contextual object list | 300 ms | 3.563 ms | 1.921 ms |
| AC-PER-03 | preview of 500 points | 500 ms | 16.174 ms | 8.298 ms |
| AC-PER-04 | maximum preview of 2.000 points | 1 s | 9.958 ms | 7.898 ms |
| AC-PER-05 | prevalidation of 200 associations | 2 s | 209.519 ms | 186.657 ms |
| AC-PER-06 | commit of 200 associations without lock wait | 2 s | 569.709 ms | — |
| AC-PER-07 | synchronous publication of 50.000 cells | 5 s | 2805.991 ms | — |

TS7-005 measured only AC-PER-01, AC-PER-02 and AC-PER-07. The four remaining
budgets are measured here for the first time: the two previews against an exact
revision, and the two halves of one 200 row batch — the read-only prevalidation
and the commit that reauthorizes and writes it in a single transaction. The
batch runs on hydro components dedicated to the measurement inside the fixture
project, because a batch belongs to one target project and the fixture's shared
consumers deliberately live in others.

Every measurement now reports its spread next to the percentile. AC-PER-03's
maximum of 684.796 ms against a median of 8.298 ms is one cold-cache sample
right after the fixture build; it is left visible rather than smoothed away.

No list or detail plan walks periods or values (AC-CAT-04), and the preview —
the one budgeted query allowed to read values — enters them through the
revision key, not a scan:

```text
Index Scan using time_series_values_pkey on time_series_values value
  Index Cond: ((set_revision_id = '2') AND (signal_id = '51'))
```

## 6. Migrator Convergence And Shadow (H-17, H-18)

`TS7MigrationAcceptanceTests` runs C0 through C6 end to end:

- C0 produces a signed manifest whose signature verifies, before any DDL.
- C2, C3 and C4 each run twice over an unchanged source and produce the **same
  manifest**, zero new rows, zero altered mappings and zero anomalies.
- C5 reports `proven` with `differences: []` over all six required dimensions —
  semantics, counts, values, hashes, authorization and lineage — and drains the
  journal to zero pending dirty roots under its pause.
- C6 flips the cutover, and a legacy write then fails **twice over**: by code
  (`TS_LEGACY_WRITE_FORBIDDEN` from the writer and from the legacy binding
  upsert) and by the database guard on `time_series_values`,
  `time_series_signals` and `case_time_series_bindings`. Legacy reads keep
  answering, now served by the canonical model, and repeating C6 returns the
  same receipt.

## 7. The Ledger (Definition Of Done, Point 6)

`test_the_ledger_reconstructs_who_made_every_mutation_and_why` walks the
association ledger, the binding ledger and the scope ledger after three
mutations made by two different identities. Every event carries actor identity,
actor role, actor id, reason code, request id and moment. The admin scope event
is attributable to the admin, and the analyst events to the analyst — the ledger
distinguishes them rather than recording "somebody".

No public route deletes an event (`DELETE` answers 404/405), and the ledger
refuses the deletion below the API too: a direct `DELETE` or `UPDATE` on the
event table raises `TS_LINK_LEDGER_IMMUTABLE` on both engines.

## 8. Manual Chrome Verification (Definition Of Done, Point 5)

Full record in [`pruebas_manuales_ts7.md`](pruebas_manuales_ts7.md). Run with the
real `.env` credentials (`MAIL_USUARIO_TEST`), with authentication on and
without minting any test administrator. Scoped project `TS7-023 verificacion`
(project 896, object 975, scenario 785, variant 756).

The three complete flows ran end to end with **no console messages**:

1. **Link a generic source** — association batch `asb_7239d0e8…`, then binding
   batch `bnb_896ef1c9…` pinned to revision 914 and its hash. The candidate list
   showed the compatible source selectable and every incompatible one blocked
   with its stable code.
2. **Create and load an object-specific series** — definition saved as
   `awaiting_data` and explicitly *not* selectable, points staged to
   `ready_to_publish`, then sealed as `new_revision` at the hash the staging
   previewed. It never appeared in `catalog/inputs` under any filter.
3. **The shared load from the object, both outcomes** — the impact was shown in
   full before any decision (scope, owner, current revision, associations, other
   projects, bindings that would go stale); the local exit produced
   `Operacion completa (derived)` with lineage and zero reassignments, and the
   shared exit produced `Operacion completa (published)` behind an explicit
   reason and comprehension acknowledgement, leaving the consumer binding
   visibly `Obsoleta` with `Ejecucion bloqueada` and unresolved.

### One gap this pass closed

The journey offered `Crear especifica para este objeto` in step 1 but step 2
rendered nothing for it, so flow 2 dead-ended in the browser: the backend path
was complete and covered by TS7-010 to TS7-012, and only the UI leg was missing.
TS7-023 built it — the definition form, the staged points load and the sealing
review — so H-08 and H-09 are now observable where the spec says they are. No
route was added; the surface it drives already existed.

## 9. Contract Changes

None. No request or response shape changed, no generated API artifact moved, and
no existing suite was edited. The two PostgreSQL fixes of section 2 are internal
to the migrator, so no adapter test is owed.
