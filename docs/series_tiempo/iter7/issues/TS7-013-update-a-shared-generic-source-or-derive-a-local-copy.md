# TS7-013: Update A Shared Generic Source From The Object Or Derive A Local Copy

Status: In Review
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter7/spec_ts7_catalogo_global_y_series_especificas.md` (7.9, 7.4, 8.6)

## What to build

Handle the dangerous case: a user standing on one object wants to load values
onto a source that other objects and other projects also consume.

`SHARED_TARGET` is a distinct mutation base, reachable only through an active
association matching signal, role and object, so a client cannot accidentally
turn a local load into a shared revision. An administrative integration that
does not start from an object uses the set's canonical revision resource; it
does not simulate an `association_id`.

Before deciding, the caller sees the full impact: scope, owner, current
revision, associations, the other objects and projects involved, and exactly
which bindings will go stale. Two outcomes are offered, and the local one comes
first when the declared intent is local. Deriving creates a local identity by
copy, with lineage, without touching the shared source and without reassigning
associations or bindings. Publishing for everyone seals a shared revision, needs
an explicit reason and comprehension mark, requires `admin` when the source is
`global`, and leaves consumers visibly stale without resolving them in the same
action.

If the impact changed between preview and confirmation, the action blocks and
demands a fresh confirmation.

## Acceptance criteria

- [x] Before deciding, the response shows scope, owner, current revision, associations, other objects and projects, and the bindings that will go stale (AC-SHR-01).
- [x] The local alternative is offered first when the declared intent is local (AC-SHR-02 backend half).
- [x] Without explicit confirmation the call returns `TS_LINK_CONFIRMATION_REQUIRED` or `TS_SHARED_REVISION_CONFIRMATION_REQUIRED` (AC-SHR-04).
- [x] An `analyst` against a `global` source returns `TS_SHARED_REVISION_ADMIN_REQUIRED` (AC-SHR-05).
- [x] If the impact changes between preview and confirmation, the action blocks and requires a new confirmation (AC-SHR-06).
- [x] Deriving a specific series preserves lineage and reassigns no associations or bindings automatically (AC-SHR-07).
- [x] Publishing for everyone leaves the stale states visible and does not resolve them in the same action (AC-SHR-08).
- [x] `SHARED_TARGET` requires an active association matching signal, role and object; a fabricated `association_id` is refused.

## Delivered surface

- `GET OBJECT_ROOT/catalog-associations/{association_id}` fills the link the
  TS7-010 context list already emitted. It answers the association identity and
  the complete impact of chapter 7.9 - `source` (set, scope, owner project,
  current revision and hash, signal count), `associations`
  (`total` / `other_objects`), `bindings`
  (`total_active` / `current` / `pinned` / `projects_affected` /
  `variants_affected`), `effect`, a bounded `listed_consumers` sample with
  `consumers_truncated`, and never an unbounded consumer collection. It also
  carries `recommendation`, `requires_confirmation`, `derivation_required` with
  its stable codes, and the two ordered `alternatives`. `intent=local` puts
  `derive_object_specific` first; the shared branch is keyed
  `publish_for_everyone` and is never offered under a neutral verb.
- `SHARED_TARGET = OBJECT_ROOT/catalog-associations/{id}/shared-series` carries
  the JSON ingestion lifecycle: prepare, read, bounded preview, cancel and
  publish. Every entry point resolves the object, then the association, and
  refuses a fabricated or foreign `association_id` with
  `TS_OBJECT_SERIES_NOT_FOUND` before it reads a payload. An archived
  association, an archived source or an inactive role do not open the flow.
  The staged job is bound to its association by a new nullable
  `catalog_association_id` column on `time_series_ingestions`, added additively
  so an already-landed TS7-010 table upgrades in place on both engines.
- The revision stays atomic per set: the payload is validated against every
  active signal of the current revision, so a partial batch on a multi-signal
  set fails with `TS_INGEST_SIGNAL_SET_INCOMPLETE` and the job reports
  `derivation_required`. The publication itself goes through the canonical
  writer of TS7-002, so the projection, the generation and the `unchanged`
  outcome behave exactly as they do for any other generic revision.
- Publishing demands `confirm`, `comprehension_acknowledged`, a `reason_code`,
  the `If-Match` of the shared source, its `Idempotency-Key`, the validation
  token and the `impact_fingerprint` the caller was shown. Missing consent
  answers `TS_SHARED_REVISION_CONFIRMATION_REQUIRED` and repeats the impact; a
  moved ETag, base revision or fingerprint answers
  `TS_INGEST_PRECONDITION_CHANGED` with `requires_new_confirmation`.
  Authority is checked before anything else: `global` sources refuse a
  non-`admin` with `TS_SHARED_REVISION_ADMIN_REQUIRED`, and `external` never
  reaches the namespace.
- The publication receipt states the staleness it created and leaves it
  unresolved: `bindings_now_stale`, `bindings_still_stale`,
  `resolved_in_this_action: 0` and `resolution_required`. Bindings keep their
  pinned revision and read `stale`; replacing them stays a separate
  transaction.
- `POST OBJECT_ROOT/catalog-associations/{id}/object-series-derivation-prevalidations`
  compares the shared source with the local copy it would produce - source
  revision and hash, proposed local definition, `differences`,
  `reassignments: {associations: 0, bindings: 0}` and a `prevalidation_token`
  pinned to that revision, hash and local key.
  `POST .../object-series-derivations` commits it: the copy inherits the source
  classification, copies only the periods and values of the identified signal
  even from a multi-signal revision, seals revision 1, records
  `catalog_object_specific_copy` lineage in
  `time_series_revision_lineage`, and returns the suggested binding request.
  It never touches the source, its associations or its bindings; it demands an
  explicit `confirmed` (`TS_LINK_CONFIRMATION_REQUIRED`), a `reason_code` and a
  pinned `source_revision` or `prevalidation_token`.

## Deliberately not in this slice

- The CSV/XLSX channel of `SHARED_TARGET`. The parser and normalizer of TS7-011
  are already multi-signal, but column mapping for an atomic multi-signal set
  is its own contract and no TS7-013 acceptance criterion depends on it. The
  JSON channel carries the whole decision surface this issue is about.
- `AC-SHR-02` and `AC-SHR-03` keep an `N3`/`N4` half: the ordering and the
  visible label belong to the React journey, which chapter 11.1 holds behind
  the C6 cutover with TS7-021.

## Evidence

- N1/N2: `tests/test_ts7_013_shared_generic_revision.py`, 15 SQLite HTTP and
  query contracts mirrored by the same opt-in PostgreSQL class
  (`POSTGRES_TEST_DATABASE_URL`): 30 tests pass on SQLite and 30 on the
  reference engine, including the additive `catalog_association_id` upgrade.
- Complete Python regression: `1118` tests passed, `103` optional tests
  skipped because PostgreSQL is not configured by default.
- Generated contract regenerated (`npm run api:generate`) and verified with
  `npm run api:check`. TypeScript, ESLint, targeted Prettier on the generated
  files, Vitest (`133` tests) and the production build all pass. The
  repository-wide Prettier phase still reports the same pre-existing files
  outside this slice.
- Three PostgreSQL mirror tests of TS7-010 and TS7-012 fail on the shared
  development database because it already holds catalog rows from earlier
  sessions and those assertions expect an empty global catalog. They fail
  identically on `HEAD` without this change, so they are environment residue
  and not a regression.
- No N4 is applicable: chapter 11.1 keeps the React journey behind C6, so
  browser evidence remains with TS7-020 and TS7-021.

## Blocked by

- [TS7-011: Ingest An Object Specific Revision By CSV And XLSX](TS7-011-ingest-an-object-specific-revision-by-csv-and-xlsx.md)
- [TS7-012: Bind, Read And Archive An Object Specific Series](TS7-012-bind-read-and-archive-an-object-specific-series.md)
