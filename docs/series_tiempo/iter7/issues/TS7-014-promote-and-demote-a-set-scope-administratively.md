# TS7-014: Promote And Demote A Set Scope Administratively

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter7/spec_ts7_catalogo_global_y_series_especificas.md` (5.1-5.4)

## What to build

Make `visibility_scope = 'global'` a reachable, audited state instead of
unexercised code. Without promotion the reuse rule the catalog exists for is
never proven, which is why it is in the MVP.

Deliver `POST /sets/{set_id}/scope-prevalidations`, which enumerates the impact
of promoting or demoting without writing, and
`POST /sets/{set_id}/scope-changes`, which applies it. Both are admin-only.

Promotion changes the same row: `owner_project_id`, revisions, associations and
history are preserved, and the set does not acquire a new identity. Demotion
fails closed when consumers from other projects exist, and it enumerates them
rather than reporting a bare refusal. Repeating a change that is already
effective returns `TS_SCOPE_ALREADY_EFFECTIVE` and writes nothing. Every change
lands in the scope ledger with actor and reason.

## Acceptance criteria

- [ ] Promotion changes the same row and preserves `owner_project_id`, revisions, associations and history (AC-SCO-01).
- [ ] `analyst` receives `TS_SCOPE_ADMIN_REQUIRED` on promotion and on demotion (AC-SCO-02).
- [ ] Demotion fails closed when consumers of other projects exist, with the impact enumerated (AC-SCO-03).
- [ ] Repeating an already effective change returns `TS_SCOPE_ALREADY_EFFECTIVE` without writing (AC-SCO-04).
- [ ] Prevalidation writes nothing and returns the same impact the confirmation will act on.
- [ ] Every scope change records actor, reason, `request_id` and moment in the scope ledger.
- [ ] A `project`-scoped source stays unusable from another project's object, before and after any failed promotion attempt.

## Blocked by

- [TS7-007: Associate A Generic Signal With An Object Atomically](TS7-007-associate-a-generic-signal-with-an-object-atomically.md)
