# Decision record TS7-024: deleting a project ends the retention of its trail

## Context

Chapter 9.6 of the TS-7 specification states the invariant plainly:

> Todas las FK historicas usan `RESTRICT`; solo staging y filas tecnicas no
> publicadas admiten cascada de limpieza.

and chapter 5.4 allows purging only `building` rows that were never sealed. The
restrictive foreign keys and the immutability triggers are therefore not an
oversight: they are the last defence that keeps an ordinary write from losing
sealed history.

What the specification never contemplated is the deletion of the project that
owns the history. The application has offered `DELETE /api/projects/{id}` since
iteration 3, and its React confirmation has always told the analyst that
deleting a project also deletes "sus escenarios, versiones, corridas, series de
tiempo y publicaciones". After the C6 cutover of TS7-022 moved the series into
the canonical space, that sentence stopped being true on PostgreSQL: the call
raised `ForeignKeyViolation` and the API answered 500. Six foreign keys from
`ts_next` to `projects` blocked it, sixteen tables in the closure were
`NO ACTION`, and the append-only ledgers refused the delete outright.

The evidence that this was known and worked around rather than decided: the
PostgreSQL teardown of `tests/test_ts7_003_linkable_object_register.py` cleared
`time_series_sets` by hand before calling `delete_project`. That workaround was
incomplete, which is why the development database accumulated 41 undeletable
projects.

## Decision

**Deleting a project is the single lifecycle event that ends the retention of
everything the project owns.** It is the only door through which the canonical
trail may leave, and it is opened explicitly, never by cascade.

`AnalystStore.delete_project` declares itself in `ts_next.project_purge_scope`
(`project_purge_scope_next` on SQLite), removes the trail in reverse dependency
order as `app/time_series_purge.py` spells it out, deletes the project row and
clears the declaration - all inside one transaction, so a failure anywhere
restores the whole trail and leaves no declaration behind.

The immutability guards of `time_series_canonical.py` and `time_series_links.py`
consult that scope. They keep the shape the specification gave them, with one
condition added:

- a **DELETE** is allowed while a purge is declared;
- an **UPDATE** is refused always, purge or no purge.

So a sealed revision, a signal identity, an association, a binding and the three
audit ledgers remain exactly as unrewritable as before. Nothing can be altered
and made to look like history that was never there; history can only end, whole,
with the project it belonged to.

## Consequences

- The 9.6 invariant now reads: historical foreign keys stay restrictive, and the
  deletion of the owning project is their one explicit exception.
- `DELETE /api/projects/{id}` answers 200 for a project with a TS-7 trail, and
  the React confirmation text becomes accurate again.
- A cross-project lineage edge leaves with whichever of its two projects goes
  first, because what remained would name a revision that is no longer there.
- The purge scope is not a canonical logical table and takes no part in the
  content model; it exists only for the duration of a delete transaction.
- What is **not** decided here: no cascade was added to any foreign key, and no
  other operation gained the ability to delete a sealed row.

## Verification

`tests/test_ts7_024_project_purge.py` covers the closure on SQLite and mirrors
it on PostgreSQL, where the restrictive keys and the plpgsql guards actually
live. Beyond the purge itself it pins the property that matters most: with no
purge declared a sealed revision and a ledger still refuse deletion, and while a
purge is open they still refuse to be rewritten.
