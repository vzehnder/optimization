# BESS-TS6-005: Mark Derived Sets Stale And Regenerate Them

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter6/prd.md`
Fecha de inicio planificada: 2026-07-28
Fecha de termino planificada: 2026-07-29

## User stories covered

7, 8

## What to build

Close the lifecycle of derived data: when a source set used by a
transformation gets a new revision (manual edit, file replacement or its own
regeneration), every derived set produced from it is marked stale, visibly in
the catalog, so the analyst knows the derived data no longer reflects its
inputs.

A stale derived set offers an explicit regenerate action: the stored recipe
(transformation type, implementation version and validated parameters) is
re-executed against the current input revisions, producing a new derived
revision with updated lineage. Regeneration never rewrites history: runs that
consumed the previous derived revision keep pointing at the exact hash they
used, consistent with the immutability guarantees TS-3 and TS-5 established.

Staleness must compose with the existing variant staleness: a case input
variant bound to a derived set that went stale surfaces the problem through
the same fail-closed gates TS-3 built, so a run cannot silently use derived
data whose sources moved. A change in the allowlisted implementation version
of a transformation also marks its outputs stale, since the same recipe would
no longer produce the same values.

## Acceptance criteria

- [ ] Creating a new revision of a source set marks every derived set produced from it stale, visibly in the catalog list and detail pages.
- [ ] A stale derived set can be regenerated from the UI, re-executing its stored recipe against current input revisions and producing a new revision with updated lineage.
- [ ] Runs that consumed a previous derived revision remain unchanged and reproducible after regeneration.
- [ ] A variant bound to a stale derived set is blocked from materializing through the existing fail-closed staleness gates until resolved.
- [ ] Bumping a transformation's implementation version marks its derived outputs stale.
- [ ] Stale detection and regeneration live in deep modules covered by tests without the UI.

## Blocked by

BESS-TS6-001
