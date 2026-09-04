# TS-7 Global Catalog And Object Specific Series Issue Tracker

This document is the local implementation tracker for the global catalog of
generic series and the object-specific series defined by
`docs/series_tiempo/iter7/spec_ts7_catalogo_global_y_series_especificas.md`.

External issue tracker integration has not been configured, so each issue is
stored as a Markdown file in this folder. All issues are AFK slices and carry
the `ready-for-agent` triage label.

The accepted specification is normative, and its chapter 13 decides which
resolution wins when two overlap. Implementation issues may surface evidence
that a contract is impossible, but they must not silently reopen or weaken a
decision from the closed Wayfinder map
[Catalogo global y series especificas vinculadas a objetos](../../../wayfinder/catalogo-global-series-genericas.md).
Reopening one means returning to the map and recording the substitution.

## Why These Slices Are Not All Vertical

The usual rule is one tracer bullet per issue, demoable on its own. Chapter 11.1
of the specification overrides it: the cut is **one single visible delivery that
lands at the C6 cutover**, and no new surface is exposed to a user before the
canonical writer exists, because a catalog that can be read and not mutated
teaches a model that does not yet exist.

So this register is sequenced as **expand, backfill, verify, cut over,
contract**. TS7-001 to TS7-005 expand the schema additively beside the current
tables, which stay the write source. TS7-006 to TS7-014 build the canonical
behaviour behind it. TS7-019 to TS7-021 build the React surfaces, reachable only
by the verification accounts until TS7-022 flips the cutover. Every issue is
still verifiable on its own, by N1/N2 tests rather than by a user-visible demo,
until the cutover makes the whole delivery visible at once.

`C7` (contraction) is destructive and is **not** authorized inside this cut.

## Status Vocabulary

- `Todo`: not started.
- `In Progress`: actively being implemented.
- `Blocked`: waiting on a dependency or newly discovered impossibility.
- `In Review`: implementation is ready for review.
- `Done`: merged or accepted.

## Evidence Levels

Taken from chapter 11.5 of the specification; each acceptance criterion in the
matrix names the levels that prove it.

- `N1`: `unittest` domain tests, no HTTP.
- `N2`: `unittest` HTTP contract tests against the development PostgreSQL.
- `N3`: `vitest` plus `tsc`, `eslint` and the frontend `build`.
- `N4`: manual Chrome verification with the real `.env` credentials
  (`MAIL_USUARIO_TEST`, `PASSWORD_MAIL_USUARIO_TEST`); no test administrators
  are created and authentication is never disabled.
- `N5`: PostgreSQL performance fixture with reference `EXPLAIN (ANALYZE, BUFFERS)`.
- `N6`: migrator execution with manifest, convergence and shadow comparison.

## Issue Register

| ID | Title | Type | Triage | Status | Blocked by | Issue file |
| --- | --- | --- | --- | --- | --- | --- |
| TS7-001 | Seed The Persistent Classification Catalogs And Compatibility Matrix | AFK | ready-for-agent | In Review | None | [TS7-001-seed-the-persistent-classification-catalogs-and-compatibility-matrix.md](TS7-001-seed-the-persistent-classification-catalogs-and-compatibility-matrix.md) |
| TS7-002 | Land The Canonical Content Model With Sealed Revisions | AFK | ready-for-agent | In Review | TS7-001 | [TS7-002-land-the-canonical-content-model-with-sealed-revisions.md](TS7-002-land-the-canonical-content-model-with-sealed-revisions.md) |
| TS7-003 | Register Every Linkable Object And Materialize Components | AFK | ready-for-agent | In Review | TS7-002 | [TS7-003-register-every-linkable-object-and-materialize-components.md](TS7-003-register-every-linkable-object-and-materialize-components.md) |
| TS7-004 | Land The Link Layer Tables And Immutable Ledgers | AFK | ready-for-agent | In Review | TS7-003 | [TS7-004-land-the-link-layer-tables-and-immutable-ledgers.md](TS7-004-land-the-link-layer-tables-and-immutable-ledgers.md) |
| TS7-005 | Project The Catalog Transactionally With Its Performance Fixture | AFK | ready-for-agent | In Review | TS7-004 | [TS7-005-project-the-catalog-transactionally-with-its-performance-fixture.md](TS7-005-project-the-catalog-transactionally-with-its-performance-fixture.md) |
| TS7-006 | Read The Global Catalog Signal First | AFK | ready-for-agent | In Review | TS7-005 | [TS7-006-read-the-global-catalog-signal-first.md](TS7-006-read-the-global-catalog-signal-first.md) |
| TS7-007 | Associate A Generic Signal With An Object Atomically | AFK | ready-for-agent | In Review | TS7-006 | [TS7-007-associate-a-generic-signal-with-an-object-atomically.md](TS7-007-associate-a-generic-signal-with-an-object-atomically.md) |
| TS7-008 | Pin A Binding To An Exact Revision And Detect Staleness | AFK | ready-for-agent | In Review | TS7-007 | [TS7-008-pin-a-binding-to-an-exact-revision-and-detect-staleness.md](TS7-008-pin-a-binding-to-an-exact-revision-and-detect-staleness.md) |
| TS7-009 | Materialize A Run From Its Bindings | AFK | ready-for-agent | In Review | TS7-008 | [TS7-009-materialize-a-run-from-its-bindings.md](TS7-009-materialize-a-run-from-its-bindings.md) |
| TS7-010 | Create An Object Specific Series And Ingest It By API | AFK | ready-for-agent | In Review | TS7-006 | [TS7-010-create-an-object-specific-series-and-ingest-it-by-api.md](TS7-010-create-an-object-specific-series-and-ingest-it-by-api.md) |
| TS7-011 | Ingest An Object Specific Revision By CSV And XLSX | AFK | ready-for-agent | In Review | TS7-010 | [TS7-011-ingest-an-object-specific-revision-by-csv-and-xlsx.md](TS7-011-ingest-an-object-specific-revision-by-csv-and-xlsx.md) |
| TS7-012 | Bind, Read And Archive An Object Specific Series | AFK | ready-for-agent | In Review | TS7-008, TS7-010 | [TS7-012-bind-read-and-archive-an-object-specific-series.md](TS7-012-bind-read-and-archive-an-object-specific-series.md) |
| TS7-013 | Update A Shared Generic Source From The Object Or Derive A Local Copy | AFK | ready-for-agent | In Review | TS7-011, TS7-012 | [TS7-013-update-a-shared-generic-source-or-derive-a-local-copy.md](TS7-013-update-a-shared-generic-source-or-derive-a-local-copy.md) |
| TS7-014 | Promote And Demote A Set Scope Administratively | AFK | ready-for-agent | In Review | TS7-007 | [TS7-014-promote-and-demote-a-set-scope-administratively.md](TS7-014-promote-and-demote-a-set-scope-administratively.md) |
| TS7-015 | Take The C0 Inventory, Manifest And Proven Restore | AFK | ready-for-agent | In Review | None | [TS7-015-take-the-c0-inventory-manifest-and-proven-restore.md](TS7-015-take-the-c0-inventory-manifest-and-proven-restore.md) |
| TS7-016 | Backfill Catalogs, Objects And Canonical Content (C2-C3) | AFK | ready-for-agent | In Review | TS7-005, TS7-015 | [TS7-016-backfill-catalogs-objects-and-canonical-content.md](TS7-016-backfill-catalogs-objects-and-canonical-content.md) |
| TS7-017 | Resolve Associations And Bindings With Typed Anomalies (C4) | AFK | ready-for-agent | In Review | TS7-008, TS7-016 | [TS7-017-resolve-associations-and-bindings-with-typed-anomalies.md](TS7-017-resolve-associations-and-bindings-with-typed-anomalies.md) |
| TS7-018 | Compare Canonical Reads In Shadow And Prove Convergence (C5) | AFK | ready-for-agent | In Review | TS7-017 | [TS7-018-compare-canonical-reads-in-shadow-and-prove-convergence.md](TS7-018-compare-canonical-reads-in-shadow-and-prove-convergence.md) |
| TS7-019 | Build The Layered Read Catalog For Verification Accounts | AFK | ready-for-agent | In Review | TS7-006 | [TS7-019-build-the-layered-read-catalog-for-verification-accounts.md](TS7-019-build-the-layered-read-catalog-for-verification-accounts.md) |
| TS7-020 | Build The Contextual Object Summary | AFK | ready-for-agent | In Review | TS7-012, TS7-019 | [TS7-020-build-the-contextual-object-summary.md](TS7-020-build-the-contextual-object-summary.md) |
| TS7-021 | Build The Single Protected Mutation Journey | AFK | ready-for-agent | Todo | TS7-013, TS7-014, TS7-020 | [TS7-021-build-the-single-protected-mutation-journey.md](TS7-021-build-the-single-protected-mutation-journey.md) |
| TS7-022 | Cut Over To The Single Canonical Writer (C6) | AFK | ready-for-agent | Todo | TS7-009, TS7-018, TS7-021 | [TS7-022-cut-over-to-the-single-canonical-writer.md](TS7-022-cut-over-to-the-single-canonical-writer.md) |
| TS7-023 | Prove TS-7 End To End | AFK | ready-for-agent | Todo | TS7-022 | [TS7-023-prove-ts7-end-to-end.md](TS7-023-prove-ts7-end-to-end.md) |

## Initial Frontier

Two issues can start immediately and in parallel:

- [Seed The Persistent Classification Catalogs And Compatibility Matrix](TS7-001-seed-the-persistent-classification-catalogs-and-compatibility-matrix.md)
  opens the expansion chain.
- [Take The C0 Inventory, Manifest And Proven Restore](TS7-015-take-the-c0-inventory-manifest-and-proven-restore.md)
  is deliberately unblocked: C0 runs against the current source before any DDL,
  and it carries its own additive migration control tables.

Every other issue has at least one open blocker.

## Dependency Waves

1. TS7-001 and TS7-015.
2. TS7-002.
3. TS7-003.
4. TS7-004.
5. TS7-005.
6. TS7-006 and TS7-016.
7. TS7-007, TS7-010 and TS7-019.
8. TS7-008, TS7-011 and TS7-014.
9. TS7-009, TS7-012 and TS7-017.
10. TS7-013, TS7-018 and TS7-020.
11. TS7-021.
12. TS7-022.
13. TS7-023.

Issues in the same wave are independent according to the accepted dependency
graph and may be implemented in parallel.

## Story Coverage

Every observable story of chapter 11.4 lands in at least one issue.

| Stories | Issues |
| --- | --- |
| H-01 to H-03 catalog search, detail and preview | TS7-006, TS7-019 |
| H-04, H-05 associations and blocked candidates | TS7-007, TS7-021 |
| H-06, H-07 bindings, pinning and staleness | TS7-008, TS7-009, TS7-021 |
| H-08 to H-11 object-specific series | TS7-010, TS7-011, TS7-012, TS7-020 |
| H-12 to H-14 shared source from the object | TS7-013, TS7-021 |
| H-15 promotion and demotion | TS7-014 |
| H-16 external is refused everywhere | TS7-006, TS7-022 |
| H-17, H-18 migrator convergence and no legacy writes | TS7-015 to TS7-018, TS7-022 |

## Regression Guard

No existing suite is edited to make it pass. If a contract change turns out to
be unavoidable, the cut stops, the change is documented, and an adapter test
preserving the previous shape is added. A test edited without that record
invalidates the acceptance (chapter 11.6).

Every slice preserves the TS-2 to TS-6 contracts, the immutable scenario-version
and run history, hydraulic behaviour, the publication artifact allowlists and
both supported database engines where persistence changes.

Backend changes run the relevant focused tests and the full Python suite.
Frontend changes run Vitest, TypeScript, ESLint, API schema checks and the
production build. Julia tests are required when a slice changes generated case
payloads, artifact contracts or optimizer behaviour. TS7-023 closes the effort
only after the full acceptance, performance and browser narratives pass.

## Progress Log

| Date | Issue | Status change | Notes |
| --- | --- | --- | --- |
| 2026-09-04 | TS7-020 | Todo -> In Review | The normalized object root now projects the object identity, the need each row covers and a bounded executable-use summary with scenario, variant, exact revision/hash, derived state and an explicit execution-blocked flag. The React route `/react/projects/:projectId/linkable-objects/:linkableObjectId/time-series` combines associated generic sources and object-specific series in one server-filtered, cursor-paged table, keeps association and variant usage separate, labels every local row `Solo este objeto`, and exposes the accepted action language only as disabled entry points until TS7-021 delivers the protected journey. Stale uses are visibly blocked, reads issue GETs only, and the route remains absent outside verification accounts. Two new SQLite HTTP contracts plus their opt-in PostgreSQL mirror, four new Vitest behaviours, the full Python suite (1,201 tests), all 147 frontend tests, `tsc`, `eslint`, generated OpenAPI verification and the production build pass. The required real-credential Chrome pass remains open because the installed extension could not connect without its native-host registration; no N4 evidence is claimed. |
| 2026-09-04 | TS7-019 | Todo -> In Review | The layered catalog landed as `/react/time-series/catalog`, a read-only React surface that opens only for the verification accounts: `ts_next_canonical_read` travels on the login and current-user answers, is computed from `TS_NEXT_CANONICAL_READ_ACCOUNTS` and falls back to the single `.env` verification credential, so it never opens by omission; a regular internal identity gets the pre-cutover behaviour of a route that is not there and an `external` one keeps the not-found root. The table is one row per signal with owner, scope, type, class, unit, coverage and resolution; every filter dimension and the keyset cursor are server-side, `Anterior` replays the trail instead of slicing a page in memory, and a refused read keeps the filters, names its stable code and `request_id` and says out loud that nothing was written. The inspector answers from one detail plus one page of immutable revision metadata - contract, procedence, sealed revision with hash, coverage, resolution and consumer counts - and the bounded preview cites the exact revision it asked for, while an over-limit answer renders `TS_PREVIEW_TOO_LARGE` as a readable refusal rather than a silent truncation. The detail endpoint now carries the `coverage_summary`, `origin_summary` and `link_summary` chapter 6.5 says it adds to the row projection, read from the same projection columns and never from values. No mutation affordance exists and every request is a GET. Five new Python contracts, ten new Vitest behaviours, the full Python suite (1,199 tests), `tsc`, `eslint`, the generated OpenAPI check, the production build and a Chrome pass with the real `.env` credentials over search, filter, inspect and preview with a clean console. |
| 2026-09-04 | TS7-017 | Todo -> In Review | C4 now projects provable signal associations, resolves every legacy binding by exact signal identity and real object FK, reauthorizes project scope, applies the single compatibility evaluator, pins the sealed revision/hash, preserves binding IDs where possible and appends migration validation/event evidence. Exact aliases never guess, while the specified symmetric `energy_price` case expands atomically into import and export roles with stable mappings; ambiguous, missing, cross-project, unmaterialized or incompatible references become typed blocking anomalies and keep the variant fail-closed, including the no-canonical-binding fallback. An explicit actor-and-reason retirement removes any canonical links and retains the legacy row as consultable history instead of waiving compatibility, while the C4 cutover gate requires zero unresolved blockers and 100% revalidated-or-retired coverage. Stable mappings, anomaly evidence and manifests make unchanged repeats no-ops. Six SQLite contracts pass, an opt-in PostgreSQL mirror is present, the 92-test focused regression is green and the full Python suite passes (1,180 tests). |
| 2026-09-03 | TS7-016 | Todo -> In Review | C2 now converges the persistent classification seeds and materializes the deterministic closed object register under the proven C0 gate, recording stable manifests and mappings while ambiguous authoritative appearances stop with `TS_MIGRATION_OBJECT_AMBIGUOUS` and plausible legacy strings never create objects. C3 backfills legacy sources, sets, signal identities, revision contracts, periods and values in independently atomic resumable batches; preserves provable IDs, owners, state, actors and timestamps; verifies the observed legacy and streamed canonical hashes before sealing and moving the current pointer; retains lightweight history as `legacy_unmaterialized`; creates a technical baseline only for an unconsumed hash mismatch; and blocks a consumed mismatch. Unknown semantic keys, units and classes remain quarantined until an explicit dimensionally valid administrative mapping resolves the anomaly. Duplicate identities, incomplete snapshots, unproven local ownership and pre-existing canonical ID collisions fail closed without partial children. Proven local definitions become `object_specific` and stay structurally outside the global catalog. An unmaterialized revision is also refused by the two surfaces that could still execute it: a binding cannot pin it, and the preview now answers `TS_PREVIEW_REVISION_UNAVAILABLE` instead of claiming a revision the history shows does not exist. Seventeen SQLite domain contracts pass and the PostgreSQL mirror runs C0, C2 and C3 over the development database in a rolled-back transaction, explaining the legacy rows it already carries. Full Python regression green (1,173 tests). |
| 2026-09-03 | TS7-015 | Todo -> In Review | The migration control surface of chapter 10.3 landed additively on both engines with the exact names the specification gives it, outside `ts_next` so the control rows survive a rollback of the expansion. `take_c0_recovery_point` inventories sources, sets, revisions, signals, periods, values, variants and bindings with counts, maximum primary keys and streaming content hashes; probes six structural differences the legacy engine cannot refuse by itself - duplicate series keys and binding targets under NULL-distinct unique keys, unresolvable binding signals, cross-project bindings, cross-set values and broken revision chains; fingerprints every variant and the executable set; writes a consistent copy of the restore closure and proves it by reloading it and recomputing the same inventory. An unexplained difference stops C0 with typed open anomalies and no signature, an explained one travels in the manifest and on the record, and a repeated C0 over an unchanged source reproduces the same manifest, digest and signature. Mappings are unique per `source_kind + source_table + source_id + target_kind` and answer `unchanged` or a conflict, never a second insert; the dirty-root queue is monotone and drains to zero; every migrator-created row carries `system:migration:<run_id>` while the human requester stays in `started_by`; and C0 never writes a row into the legacy source. `open_migration_phase` refuses `TS_MIGRATION_RECOVERY_POINT_REQUIRED` without a proven C0 that still describes the source, which is the enforceable form of AC-MIG-01 now that C1 has already landed. Twenty SQLite contracts and an opt-in PostgreSQL mirror pass; the full Python suite is green and no response, permission or navigation changed. |
| 2026-09-03 | TS7-014 | Todo -> In Review | Administrative two-phase scope changes now prevalidate the exact set/revision/hash and enumerate active associations and bindings without writing. Admin-only confirmation is guarded by CSRF, signed actor-bound token, strong impact ETag, observed scope/revision/hash, explicit confirmation, nonblank reason and durable idempotency. Promotion mutates the same set identity, preserves owner/content/links, updates the canonical projection and leaves fingerprint-derived consumers stale; valid demotion returns it to its owner project, while cross-project consumers make demotion fail closed with enumerated impact. Every success appends the immutable scope ledger with actor, role, reason, request, key and moment. Fourteen SQLite HTTP contracts pass and the promotion/demotion transaction has an opt-in PostgreSQL mirror; generated OpenAPI/TypeScript contracts, frontend tests and production build are green. |
| 2026-09-02 | TS7-013 | Todo -> In Review | The dangerous branch now has its own base. `GET OBJECT_ROOT/catalog-associations/{id}` answers the whole impact before the decision - scope, owner, current revision and hash, associations, other objects and projects, the bindings that will go stale and a bounded consumer sample - plus the two ordered outcomes, with the local one first when the declared intent is local and the shared one keyed `publish_for_everyone`. `SHARED_TARGET` stages, previews, cancels and publishes a JSON revision only through an active association matching signal, role and object; a fabricated or foreign id is refused before the payload is read, the revision stays atomic per set, and `global` sources refuse a non-`admin`. Publication demands confirmation, comprehension, reason, ETag, idempotency and the exact impact fingerprint; any movement blocks with a fresh confirmation, and the stale states it creates stay visible and unresolved. Deriving copies the identified signal into a new local identity with `catalog_object_specific_copy` lineage, without touching the source, its associations or its bindings. Thirty tests pass on SQLite and on PostgreSQL; the CSV/XLSX shared channel is deliberately left out of this slice. |
| 2026-09-02 | TS7-012 | Todo -> In Review | Sealed local series now bind directly to their exact owner with typed provenance and no catalog association; the contextual read reflects the binding. Canonical catalog/local views and filter/candidate contracts make the read split structural. Terminal archival preserves revisions, previews and past bindings while all later mutations and execution fail closed. The catalog writer rejects reuse of a local set, and the future copy lineage is proven to create a distinct generic identity. SQLite, opt-in PostgreSQL, full Python and generated API/frontend contracts are covered; no React surface is exposed before C6. |
| 2026-09-02 | TS7-011 | Todo -> In Review | The file channel now joins the points ingestion lifecycle through multipart CSV/XLSX staging, durable idempotency, safe source metadata, file-local validation errors, worksheet and column remapping without reupload, bounded normalized preview, cancellation and exact staged-snapshot publication. Replacement and append updates preserve identity and immutable revision history; byte, expanded-size, compression-ratio, period, cell, column, error and active-job limits refuse malformed or oversized uploads without partial canonical writes. Sixteen SQLite HTTP contracts pass and are mirrored as an opt-in PostgreSQL suite; the complete Python regression and generated OpenAPI contract are green. No React surface is exposed before C6. |
| 2026-09-02 | TS7-010 | Todo -> In Review | Path B opened on the normalized object root: contextual `source_kind` list over the filtered two-armed union with the shared cursor, definition-only creation that leaves revision 1 `building` and the series unselectable, `If-Match` patch limited to name, description and curated metadata, revision history and bounded preview. Points ingestion stages a validated snapshot outside the canonical tables, survives its own refusal so the mapping can be corrected and revalidated, previews, cancels, and publishes in one transaction that seals the building revision, moves the pointer and answers `unchanged` for identical content. Durable idempotency, opaque job ids that never skip authorization, and `application/problem+json` on every refusal. SQLite HTTP coverage passes with the same contract available as an opt-in PostgreSQL suite; file ingestion, archival and the shared-source journey stay with TS7-011 to TS7-013. |
| 2026-09-02 | TS7-009 | Todo -> In Review | Canonical run materialization now locks and rereads the variant and exact revisions in one transaction, recalculates the sealed content hash, maps binding roles into the Julia payload, records the complete immutable lineage, accepts explicit pins, reuses byte-identical snapshots and creates the run atomically before enqueue. Interrupted writes roll back without a partial scenario version, while TS-4 result indices remain separate. SQLite HTTP/domain coverage passes and the same happy-path contract is available as an opt-in PostgreSQL suite. |
| 2026-09-01 | TS7-008 | Todo -> In Review | Exact-revision binding API landed with scenario/variant context, two-phase all-or-nothing batches, derived `valid_current`/`valid_pinned`/`stale`/`invalid` states, execution blocking, explicit replace/revalidate/remove/restore journeys, catalog-provenance validation, strong ETags, durable idempotency, transactional catalog counts and append-only paginated events. The complete HTTP contract passes on SQLite and is mirrored as an opt-in PostgreSQL suite. |
| 2026-09-01 | TS7-007 | Todo -> In Review | Atomic two-phase association API landed with read-only prevalidation, guarded all-or-nothing batches of up to 200 add/replace/archive/revalidate operations, deterministic PostgreSQL locks, durable idempotent replay, stable scope/precondition refusals, effective-state reads and immutable paginated audit history. Functional SQLite and PostgreSQL contracts pass; the normative N5 p95 fixture remains explicitly open. |
| 2026-09-01 | TS7-006 | Todo -> In Review | Reconciled the local tracker with the catalog read API already landed in `fc4f3d6`, which is the dependency consumed by TS7-007. |
| 2026-08-31 | TS7-005 | Todo -> In Review | Catalog projection landed in `ts_next` / `_next`, maintained by the same transaction that seals a revision, with the mandatory indexes, a signed keyset cursor whose leading bound keeps a deep page an index seek, the two-armed object union, durable idempotency with an `unchanged` no-op, shadow rebuild and divergence reconciliation. Reference plans and budgets saved under `docs/series_tiempo/iter7/performance/`; AC-PER-07 carried forward to TS7-011 with its measurement. |
| 2026-08-31 | TS7-004 | Todo -> In Review | Separate catalog associations and exact-revision bindings landed in `ts_next` / `_next` with partial active cardinalities, composite catalog/source/revision/hash integrity, coherent append-only lifecycle history, three identically immutable ledgers, restrictive orphan closure and matching SQLite/PostgreSQL contract coverage. |
| 2026-08-31 | TS7-003 | Todo -> In Review | Closed register of linkable objects landed in `ts_next` / `_next`: one typed foreign key per row with the object type derived from the real object and verified by a portable guard, deterministic component materialization out of cases and drafts with no fuzzy matching, case-scoped references resolved through their own foreign key to the base entity, cascade-closed orphans and the composite owner reference TS7-002 carried forward. |
| 2026-08-31 | TS7-002 | Todo -> In Review | Canonical content model landed in `ts_next` / `_next` beside the intact legacy tables, with the atomic revision protocol as the only writer, portable sealed/pointer/identity/ledger guards, and a streaming canonical hash proven equal on SQLite and PostgreSQL. |
| 2026-08-31 | TS7-001 | Todo -> In Review | Persistent classification catalogs, versioned convergent seed, immutable contracts, fail-closed compatibility evaluator, database-backed legacy adapter and protected custom semantic-type creation implemented and verified on SQLite and PostgreSQL. |
| 2026-08-30 | All | Created | Twenty-three AFK issues published from the accepted TS-7 specification after the Wayfinder map closed. Sequenced as expand/backfill/verify/cutover because chapter 11.1 forbids exposing a new surface before the canonical writer exists. TS7-001 and TS7-015 are the initial frontier. |
