# TS7-008: Pin A Binding To An Exact Revision And Detect Staleness

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter7/spec_ts7_catalogo_global_y_series_especificas.md` (4.3, 4.4, 4.5, 4.7, 6.1)

## What to build

Make a variant execute against one exact revision. The binding routes keep the
scenario and variant context - an isolated `variant_id` is not trusted as
context - and deliver the effective and historical list, the detail with its
derived state and ETag, the append-only event history, the prevalidation and the
all-or-nothing batch.

A binding freezes `set_revision_id` and its hash. When the source publishes a
new revision the binding does not follow it: it becomes `stale`, blocks
execution, and offers compare, revalidate the pin, or replace with a reason. No
variant moves on its own, and the previous binding survives as consultable
history.

`stale` and `invalid` are derived server-side. A client that sends them does not
skip validation. An object and a variant from different projects are refused
with `TS_COMPAT_PROJECT_CONTEXT_MISMATCH`.

Archiving is safe: a signal or type in use is archived, never physically
deleted, and past bindings keep resolving.

## Acceptance criteria

- [ ] Only one active binding exists per `case_input_variant_id + linkable_object_id + binding_role_id` (AC-BIN-01).
- [ ] A binding pins exact revision and hash and does not follow `current_revision_id` after a new publication (AC-BIN-02).
- [ ] Publishing a revision leaves consumers stale and blocks their execution; no variant advances by itself (AC-BIN-03).
- [ ] `stale` and `invalid` are derived: a client that submits them does not avoid validation (AC-BIN-04).
- [ ] Replacing requires comparison and a reason, and the previous binding stays in consultable history (AC-BIN-05 backend half).
- [ ] An object and variant from different projects return `TS_COMPAT_PROJECT_CONTEXT_MISMATCH` (AC-BIN-06).
- [ ] The batch is all-or-nothing per variant and shares the prevalidation contract with associations.
- [ ] Archiving a signal or type in use preserves history and past bindings; nothing is physically deleted.
- [ ] Binding events are append-only and paginated.

## Blocked by

- [TS7-007: Associate A Generic Signal With An Object Atomically](TS7-007-associate-a-generic-signal-with-an-object-atomically.md)
