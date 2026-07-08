# TS-5 Migration Semantics Decision Record

Fecha: 2026-07-08
Status: Accepted
Issue: `BESS-TS5-000`

## Context Reviewed

This decision was reviewed against:

- `docs/series_tiempo/iter5/prd.md` (TS-5 PRD and its Grill-Me answers);
- `docs/series_tiempo/roadmap_iteraciones_jerarquias_series.md` (TS-5 section
  and detail, the `Scenario -> OptimizationCase` cardinality question, the
  `ScenarioDraft` role question);
- `docs/series_tiempo/propuesta_manejo_series_tiempo.md` (original series
  proposal, phase 3 "convergencia hidraulica" adapter-then-migrate plan);
- `docs/series_tiempo/iter1/decision_record_ts1_hierarchy.md` (cardinality
  explicitly deferred to TS-5; topology/parameter semantics);
- `docs/series_tiempo/iter2/decision_record_ts2_catalog_semantics.md` (catalog
  model, `version_number`/`version_label`/`revision_number`, manual-edit
  policy that TS-5 extraction/migration must reuse, not reinvent);
- `docs/series_tiempo/iter3/decision_record_ts3_variant_semantics.md`
  (`case_input_variants`, `case_time_series_bindings`,
  `validation_dependencies` generic staleness table that TS5-005 must extend
  across storage origins, not replace);
- `docs/series_tiempo/iter4/decision_record_ts4_result_semantics.md` (dedicated
  run-result layer, BBDD-first/artifact-fallback read policy, the
  `rebuild_run_results`/`rebuild_all_run_results` rebuild path TS5-009 must
  close the loop with);
- draft TS-5 issues `BESS-TS5-001` through `BESS-TS5-011`, to confirm this
  record actually closes what each downstream issue expects to consume;
- current schema in `app/persistence.py`: `scenario_drafts`
  (`scenario_id INTEGER NOT NULL UNIQUE`, `document_json`),
  `optimization_cases` (`scenario_id INTEGER NOT NULL UNIQUE`),
  `hydraulic_time_series_sets` / `hydraulic_time_series_points` /
  `case_hydraulic_time_series_bindings`, `time_series_sets` and the TS-2
  catalog tables, `case_input_variants` / `case_time_series_bindings` /
  `validation_dependencies` (generic, `dependency_id TEXT` already supports
  non-integer/legacy dependency keys), `scenario_versions` (DB-trigger
  immutable), `run_artifacts`, and the TS-4 result-index tables
  (`run_dispatch_result_indexes`, `run_dispatch_result_rows`,
  `run_asset_dispatch_result_indexes`, `run_asset_dispatch_result_rows`,
  `run_summary_result_indexes`);
- `app/draft_editor.py` (`generate_system_case_from_draft`,
  `validated_rows` embedded in `scenario_drafts.document_json` — the
  draft-embedded series path TS5-001 extracts from) and
  `frontend/src/DraftEditor.tsx` (confirms the structured editor is still a
  live, routed UI surface today, not already dead code);
- `app/auth.py` (`VALID_USER_ROLES`, `INTERNAL_USER_ROLES`,
  `AuthorizationService`) and the middleware gate in `app/main.py`
  (`/api/client*`/`/client*` require the `client` role, everything else
  requires `INTERNAL_USER_ROLES`; only four narrow `/api/client/...` routes
  exist today: project list, publication list, publication detail, artifact
  download) and `app/persistence.py`'s `project_client_access` table
  (per-project ACL exists only for clients; internal users have no
  per-project scoping today);
- `app/result_indexing.py` (`rebuild_run_results`, `rebuild_all_run_results`)
  and `app/result_comparison.py` (comparison is computed on read, no
  persisted comparison cache to account for in retention).

## Accepted Decisions

1. **Per-path strategy** is accepted as follows for every place temporal data
   lives today:

   | Legacy path | Strategy | Landing issue |
   | --- | --- | --- |
   | Series embedded in `scenario_drafts.document_json` (`validated_rows`, structured-editor CSV/XLSX sources) | Extract on demand into the generic catalog. The draft is never rewritten or deleted; extraction adds a new `time_series_set` (+ revision, periods, signals, values) carrying origin metadata (draft id, original source filename/checksum already recorded in the draft document, extracted-by, extracted-at). Idempotent re-extraction. | BESS-TS5-001 |
   | `hydraulic_time_series_sets` / `hydraulic_time_series_points` (hydro diagram legacy series) | Adapt now (read adapter over the common catalog semantics, no row migration), stop new legacy writes once the generic write path lands, migrate existing sets on demand (never automatic/bulk-by-default). | BESS-TS5-002, BESS-TS5-003, BESS-TS5-004 |
   | Historical `scenario_versions.system_case_json` | Freeze as read-only legacy, permanently. Already DB-trigger immutable (`scenario_versions_immutable`); self-contained and reproducible on its own; never decomposed into catalog rows. | No implementation issue needed — already enforced |
   | Old runs whose results exist only as artifacts (no BBDD index) | Rebuild on demand, reusing the TS4-008 rebuild path (`rebuild_run_results` / `rebuild_all_run_results`); never a forced backfill. | BESS-TS5-009 (wires cleanup + rebuild into one lifecycle) |

   No path is fully migrated by default. This matches the PRD's out-of-scope
   line "full automatic migration of every historical artifact" and the
   roadmap's "no necesariamente [migrar todo]; debe definir que se migra, que
   se adapta y que queda como snapshot legacy valido."

2. **Historical scenario versions and executed snapshots are confirmed
   immutable**, already enforced at the DB level. Any extraction (TS5-001) or
   migration (TS5-004) into the new model creates new objects with origin
   metadata; it never rewrites a `scenario_versions` row, a `run` row or a
   `run_artifacts` row. This is a hard constraint on every downstream TS-5
   issue, not just a preference.

3. **`ScenarioDraft`'s future role is a permanent compatibility/authoring
   surface with a labeled deprecation direction, not a forced removal or a
   silent freeze.** `frontend/src/DraftEditor.tsx` is a live, routed UI today
   (confirmed in code, not just docs) and remains the one-bus structured
   editing path. Its role after TS-5: an authoring surface whose validated
   series can be extracted into the generic catalog (BESS-TS5-001) for reuse
   and variant binding, while the draft document itself stays exactly as it
   is — TS-5 does not rewrite or retire `scenario_drafts`. BESS-TS5-007 must
   visibly label the structured/draft path as the legacy-origin,
   deprecation-pointed path relative to the catalog-plus-variant path, so new
   series work is steered toward the common model without breaking existing
   drafts. A full UX replacement of the structured editor is explicitly out
   of TS-5 scope; it is future work, only if usage data justifies it.

4. **`Scenario -> OptimizationCase` cardinality stays one-to-one; the
   migration to many-cases-per-scenario is rejected for TS-5.** Both
   `optimization_cases.scenario_id` and `scenario_drafts.scenario_id` carry a
   `UNIQUE` constraint today, and nothing built across TS-1 through TS-4
   surfaced a concrete need to relax it:
   - `BESS-TS3` already solved the main driver for "alternatives without
     duplicating structure" — input-series sensitivities — with
     `case_input_variants`, scoped under one case.
   - There is no `parameter_versions`/`topology_versions` table; parameter
     and topology alternatives that are *not* series-driven (e.g. a materially
     different topology or a different limit set) already have a working,
     unambiguous home: a new `Scenario` (a "folder/workline" per the roadmap's
     own definition), each holding its one case. This reuses an existing,
     tested concept instead of adding a second one.
   - The roadmap's own framing for this question is conditional, not a
     mandate: "si varios casos por scenario aportan claridad, TS-5 es el
     momento". No TS-1 through TS-4 decision record or issue log recorded
     friction from the one-case-per-scenario constraint, so the "aporta
     claridad" bar is not met.
   - Relaxing the constraint would touch `scenario_drafts`, `optimization_cases`,
     every case-scoped route, case selection UI/navigation, and an idempotent
     SQLite+PostgreSQL migration, for a capability with no evidenced demand —
     exactly the kind of speculative, unrequested surface area TS-5 (a
     hardening iteration) should avoid adding.
   BESS-TS5-006 therefore implements the PRD's "confirmed" branch: keep the
   `UNIQUE` constraints as deliberate (not accidental) design, and remove
   ambiguity in naming, routes and UI so the product says "one case per
   scenario" outright instead of implying hidden multiplicity. This can be
   revisited later if real usage surfaces a concrete need; nothing in this
   decision blocks a future migration.

5. **Hydraulic series write strategy is accepted as generic-model writes with
   adapter reads (no dual write), with an open-ended compatibility
   window**, matching what BESS-TS5-002/003/004 already assume:
   - BESS-TS5-002 adds a read adapter exposing `hydraulic_time_series_sets`
     through common catalog semantics, with no row migration and no change to
     the hydro diagram editor's existing screens or bindings.
   - BESS-TS5-003 routes *new* hydraulic series writes to the generic model.
     From that point, the legacy hydraulic tables stop growing; no dual-write
     path is introduced, because runs already freeze their exact payload into
     `scenario_versions.system_case_json` regardless of which storage produced
     it, so there is nothing for a dual write to protect that the frozen
     snapshot does not already protect.
   - BESS-TS5-004 adds on-demand, per-set migration plus a bulk sweep tool.
     Migration has no forced deadline: old runs never need their legacy set
     migrated to stay reproducible (they read their own frozen snapshot, not
     live hydraulic tables), so the compatibility window closes per-project,
     opportunistically, whenever an admin or analyst chooses to migrate a
     set — not on a schedule TS-5 imposes.

6. **Permission matrix is accepted**, formalizing the coarse split that
   already exists structurally (`INTERNAL_USER_ROLES` vs `client`, with only
   four narrow `/api/client/...` routes) rather than introducing a new access
   model:

   | Data | Analyst | Admin | Client |
   | --- | --- | --- | --- |
   | Sources (`time_series_sources`, uploaded CSV/XLSX, draft-embedded files) | Read/write, all projects | Read/write, all projects | Never |
   | Input series (generic catalog, adapter-read hydraulic sets, extracted sets, variants) | Read/write, all projects | Read/write, all projects | Never, not even via a direct endpoint |
   | Result series (run result indexes, artifacts) | Read, all projects | Read, all projects | Never directly; only via a published publication's `allowed_artifact_types` |
   | Published outputs | Read (as any internal user) | Read | Read, only for projects with `project_client_access`, only `status = 'published'` |
   | User/access management, retention & cleanup (TS5-009), bulk migration sweeps (TS5-004) | No | Yes | No |

   Analysts and admins remain unscoped per-project (as today; no per-analyst
   project ACL is introduced — that would be new, unrequested scope). The
   residual risk TS5-008 must close is not "design a new matrix", it is
   **enforcement consistency**: every new TS-5 endpoint (catalog browse,
   adapter reads, extraction, migration, cleanup) must sit behind the
   existing internal/client gate through a shared deep-module check, with
   tests, so a future route addition cannot accidentally bypass it by
   sitting outside `/api/client` yet skipping `require_internal`.

7. **Retention boundary is accepted**: immutable audit data is
   `scenario_versions`, `runs`, `run_artifacts`, `time_series_sources`,
   `time_series_set_revisions` (and the equivalent extraction/migration origin
   metadata TS5-001/004 add), and legacy `hydraulic_time_series_sets`/
   `..._points` rows that have not been migrated yet (they are the only
   surviving record of that data until migrated). Rebuildable derived data is
   exactly the TS-4 result-index tables — `run_dispatch_result_indexes`,
   `run_dispatch_result_rows`, `run_asset_dispatch_result_indexes`,
   `run_asset_dispatch_result_rows`, `run_summary_result_indexes` — because
   `rebuild_run_results`/`rebuild_all_run_results` already regenerate them
   from `run_artifacts`. There is no persisted comparison cache
   (`app/result_comparison.py` computes on read), so BESS-TS5-009 has nothing
   else to classify.

8. **Architecture-closure criteria (TS-5 definition of done) are accepted**
   as: (a) new time-series and result writes go through the common model —
   TS5-003 for hydraulic input series, already true for generic series since
   TS-2 and results since TS-4; (b) every legacy read path has a working
   adapter or is frozen as an immutable read-only snapshot — TS5-002 for
   hydraulic series, already true for `scenario_versions`; (c) the UI no
   longer mixes concepts — TS5-006 and TS5-007; (d) stale validation, audit
   and permissions hold across every storage origin, not just the newest one
   — TS5-005 and TS5-008; (e) rebuildable derived data can be cleaned and
   restored without touching audit data — TS5-009; (f) real query patterns
   from TS-2 through TS-4 are indexed, not speculative ones — TS5-010.

## PRD Corrections

No corrections are required to `docs/series_tiempo/iter5/prd.md` text. One
clarification is recorded for downstream implementers: the PRD's open
questions 1-7 are answered by Decisions 1-8 above; where the PRD offered
multiple strategies per path (e.g. "dual write or on-demand migration" for
hydraulic writes), the single accepted strategy is the one written in
Decision 5, and downstream issues should not re-litigate the alternatives.

## Acceptance Mapping

- Per-path strategy for draft-embedded series, structured-editor sources,
  hydraulic-specific tables, historical scenario versions and artifact-only
  results: accepted (Decision 1).
- Historical scenario versions/executed snapshots never rewritten, extraction
  always records origin metadata: accepted (Decision 2), already DB-enforced
  for scenario versions.
- `ScenarioDraft` future role (compatibility surface with a labeled
  deprecation direction, not forced removal): accepted (Decision 3).
- `Scenario -> OptimizationCase` cardinality: closed as one-to-one, confirmed
  rather than migrated (Decision 4); BESS-TS5-006 implements the "confirmed"
  branch.
- Hydraulic series write strategy and compatibility window: accepted as
  generic-model writes with adapter reads, no dual write, open-ended
  per-project migration window (Decision 5).
- Permission matrix for sources, input series, result series and published
  outputs across analyst/admin/client: agreed (Decision 6).
- Retention boundary between immutable audit data and rebuildable derived
  data: agreed (Decision 7).
- Architecture-closure criteria: agreed as the TS-5 definition of done
  (Decision 8).
- No PRD text correction needed before downstream TS-5 implementation begins.

## Verification

- Confirmed in `app/persistence.py` that `optimization_cases.scenario_id` and
  `scenario_drafts.scenario_id` both carry `UNIQUE`, grounding Decision 4's
  "nothing has relaxed this yet" premise, and that `case_input_variants`/
  `case_time_series_bindings`/`validation_dependencies` already exist from
  TS-3, grounding Decision 4's "sensitivities already have a home" claim.
- Confirmed in `app/draft_editor.py` (`generate_system_case_from_draft`,
  `validated_rows` handling) and `frontend/src/DraftEditor.tsx` that the
  structured draft path is live code and a live route today, not legacy dead
  code, grounding Decision 3's "compatibility surface, not forced removal"
  framing in actual usage rather than assumption.
- Confirmed in `app/persistence.py` (`hydraulic_time_series_sets`,
  `hydraulic_time_series_points`, `case_hydraulic_time_series_bindings`) and
  `docs/series_tiempo/iter5/issues/BESS-TS5-002/003/004*.md` that the
  drafted issues already assume exactly the adapter-then-migrate-on-demand
  sequence accepted in Decision 5, so no downstream issue needs rewriting.
- Confirmed in `app/main.py` (`require_internal_user`/`require_admin_user`
  middleware gate, four `/api/client/...` routes) and `app/persistence.py`
  (`project_client_access`) that the accepted permission matrix (Decision 6)
  matches what is structurally enforced today, so BESS-TS5-008's job is
  enforcement consistency and tests for new TS-5 surfaces, not a new access
  model.
- Confirmed in `app/result_indexing.py` (`rebuild_run_results`,
  `rebuild_all_run_results`) and `app/persistence.py`'s TS-4 result-index
  table definitions that the rebuildable set named in Decision 7 is exactly
  what the existing rebuild path already regenerates, and in
  `app/result_comparison.py` that no comparison cache exists to add to that
  set.

## Blocked by

None - can start immediately.
