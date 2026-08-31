# TS7-021: Build The Single Protected Mutation Journey

Status: Todo
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

- [ ] Every mutation goes through the four-step journey; no surface offers an abbreviated mutation path.
- [ ] Both entry points converge on the same prevalidation and the same final review.
- [ ] Incompatible candidates are explained and cannot be selected, showing the stable code.
- [ ] Going back a step preserves the draft; changing object, source, revision or file invalidates the prevalidation and forces recalculation.
- [ ] The rail keeps object and scope visible at every step.
- [ ] Replacing a binding shows the comparison and requires a reason before it can be confirmed (AC-BIN-05 frontend half).
- [ ] `Crear especifica para este objeto` is offered first when the declared intent is local (AC-SHR-02).
- [ ] The shared action is labelled `Publicar para todos` and never `Guardar` or `Actualizar` (AC-SHR-03).
- [ ] A mutation error preserves the draft and the filters and states that nothing was written (AC-SEG-07).
- [ ] Batch operations use the atomic endpoints and report an all-or-nothing outcome.
- [ ] `tsc`, `eslint`, `vitest` and the production build pass, and a Chrome pass with the real `.env` credentials runs the three flows with no console errors.

## Blocked by

- [TS7-013: Update A Shared Generic Source From The Object Or Derive A Local Copy](TS7-013-update-a-shared-generic-source-or-derive-a-local-copy.md)
- [TS7-014: Promote And Demote A Set Scope Administratively](TS7-014-promote-and-demote-a-set-scope-administratively.md)
- [TS7-020: Build The Contextual Object Summary](TS7-020-build-the-contextual-object-summary.md)
