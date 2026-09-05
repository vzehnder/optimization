# TS7-021: Build The Single Protected Mutation Journey

Status: In Review
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter7/spec_ts7_catalogo_global_y_series_especificas.md` (8.1, 8.3, 8.6, 8.7)

## What to build

Build the one pattern that governs every mutation: creating an object-specific
series, associating a generic one, creating or replacing a binding, loading
values, publishing a revision and running batch operations. There is no
abbreviated mutation anywhere else - the read catalog and the object summary
hand off to this journey the moment intent to change state appears.

Four steps, always in this order. Origin and scope: the object, the functional
role, and an explicit choice between a reusable generic source and an
object-specific series. Definition or selection: compatible contract, identity,
owner, scope and candidate, where incompatible candidates may be explained but
never chosen. Data or executable revision: file or API with preview for loads,
revision and hash for associations and bindings. Impact and confirmation: exact
changes, permissions, consumers, staleness, atomicity and history, shown before
saving.

Both entry points - from the catalog and from the object - converge on the same
prevalidation and the same final review. The rail keeps object and scope visible
throughout. Going back a step does not lose the draft; changing object, source,
revision or file invalidates the later prevalidation and forces a recalculation.

For a shared source, the destructive action is labelled `Publicar para todos` -
never `Guardar` or `Actualizar` - and `Crear especifica para este objeto` is
offered first when the declared intent is local.

## Acceptance criteria

- [x] Every mutation goes through the four-step journey; no surface offers an abbreviated mutation path.
- [x] Both entry points converge on the same prevalidation and the same final review.
- [x] Incompatible candidates are explained and cannot be selected, showing the stable code.
- [x] Going back a step preserves the draft; changing object, source, revision or file invalidates the prevalidation and forces recalculation.
- [x] The rail keeps object and scope visible at every step.
- [x] Replacing a binding shows the comparison and requires a reason before it can be confirmed (AC-BIN-05 frontend half).
- [x] `Crear especifica para este objeto` is offered first when the declared intent is local (AC-SHR-02).
- [x] The shared action is labelled `Publicar para todos` and never `Guardar` or `Actualizar` (AC-SHR-03).
- [x] A mutation error preserves the draft and the filters and states that nothing was written (AC-SEG-07).
- [x] Batch operations use the atomic endpoints and report an all-or-nothing outcome.
- [x] `tsc`, `eslint`, `vitest` and the production build pass, and a Chrome pass with the real `.env` credentials runs the three flows with no console errors.

## How it was built

The journey is one route, `/react/time-series/journey`, behind the same
verification-account gate as the other two surfaces. Both entry points land on
it: the object summary links in with `entry=object`, the catalog inspector with
`entry=catalog`. Three branches share one `JourneyShell` - the rail, the four
steps and the navigation - so "the same final review" is a fact of the code:
`BatchReview` is a single component that both link flows and the catalog batch
render.

- `LinkFlow` covers `associate` and `use_revision`. A need already covered in
  the chosen variant turns the operation into a `replace`, which renders the
  comparison and refuses to advance until a reason is written.
- `CatalogFlow` covers the reverse path: one generic signal, many objects. This
  is where the real bulk operation lives, because a single source can cover the
  same need on several objects in one atomic batch.
- `SharedSourceFlow` covers chapter 8.6. The server already orders the two
  outcomes by the declared intent and names them by a stable key; the surface
  only translates `create_specific_for_this_object` and `publish_for_everyone`,
  so no neutral verb can leak in.

The prevalidation is keyed by a signature built from object, source, revision
and observed `bindings_revision`. Changing any of them produces a different key,
so the earlier answer is discarded and recalculated rather than confirmed
against.

## Backend addition

`GET /api/scenarios/{id}/case-variants/{id}/time-series-bindings` now returns
`meta.bindings_revision`. Chapter 6.8 makes `expected_bindings_revision`
mandatory on every binding batch and nothing exposed it, so the journey could
not have sent an observed value - only a guessed one. Covered by
`tests/test_ts7_021_protected_journey_preconditions.py` (N2).

## Evidence

- N2: `python -m unittest tests.test_ts7_021_protected_journey_preconditions`;
  the whole `test_ts7_*` suite passes (370 tests).
- N3: `tsc -b`, `eslint .`, `vitest run` (158 tests, 10 of them the journey's)
  and `npm run build` all pass.
- N4: Chrome with the real `.env` credentials, 2026-09-05. A scoped project
  `TS7-021 verificacion` (project 652, object 596, scenario 717) was created to
  hold the run, because no project in the development database had a linkable
  object and a catalog signal in the same scope. The four flows ran end to end
  with no console messages: association `asb_4a614bfc...`, binding create
  `bnb_c1408200...`, `Publicar para todos` (revision 2, which left the binding
  visibly stale), the binding replace `bnb_e24a539a...` with its comparison and
  mandatory reason, and the local derivation. The same pass also closes the
  outstanding N4 criterion of TS7-020, since the object summary ends with one
  generic and one object-specific row.

## Known limitation

The catalog entry point targets the project the source belongs to. Associating a
`global` source onto objects of a different project needs a target-project
selector in step 1; the compatibility evaluator already refuses the cross-scope
case with `TS_COMPAT_SCOPE_NOT_ACCESSIBLE`, so nothing is silently wrong, but
the selector is not built.

## Blocked by

- [TS7-013: Update A Shared Generic Source From The Object Or Derive A Local Copy](TS7-013-update-a-shared-generic-source-or-derive-a-local-copy.md)
- [TS7-014: Promote And Demote A Set Scope Administratively](TS7-014-promote-and-demote-a-set-scope-administratively.md)
- [TS7-020: Build The Contextual Object Summary](TS7-020-build-the-contextual-object-summary.md)
