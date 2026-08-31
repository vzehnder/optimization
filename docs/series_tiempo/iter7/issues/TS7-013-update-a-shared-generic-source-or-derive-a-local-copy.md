# TS7-013: Update A Shared Generic Source From The Object Or Derive A Local Copy

Status: Todo
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

- [ ] Before deciding, the response shows scope, owner, current revision, associations, other objects and projects, and the bindings that will go stale (AC-SHR-01).
- [ ] The local alternative is offered first when the declared intent is local (AC-SHR-02 backend half).
- [ ] Without explicit confirmation the call returns `TS_LINK_CONFIRMATION_REQUIRED` or `TS_SHARED_REVISION_CONFIRMATION_REQUIRED` (AC-SHR-04).
- [ ] An `analyst` against a `global` source returns `TS_SHARED_REVISION_ADMIN_REQUIRED` (AC-SHR-05).
- [ ] If the impact changes between preview and confirmation, the action blocks and requires a new confirmation (AC-SHR-06).
- [ ] Deriving a specific series preserves lineage and reassigns no associations or bindings automatically (AC-SHR-07).
- [ ] Publishing for everyone leaves the stale states visible and does not resolve them in the same action (AC-SHR-08).
- [ ] `SHARED_TARGET` requires an active association matching signal, role and object; a fabricated `association_id` is refused.

## Blocked by

- [TS7-011: Ingest An Object Specific Revision By CSV And XLSX](TS7-011-ingest-an-object-specific-revision-by-csv-and-xlsx.md)
- [TS7-012: Bind, Read And Archive An Object Specific Series](TS7-012-bind-read-and-archive-an-object-specific-series.md)
