# TS7-020: Build The Contextual Object Summary

Status: In Review
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter7/spec_ts7_catalogo_global_y_series_especificas.md` (8.1, 8.2, 8.4, 8.5, 7.3)

## What to build

Give each object its own summary: what series it already has, what need each one
covers, and what is still missing. The linking table from the prototype is not a
third main surface - its object to need to source context lives here.

The summary lists generic associations and object-specific series together,
each row explicitly discriminated, with `Solo este objeto` accompanying every
object-specific one so nobody mistakes a local series for a shared source. Rows
show the two states separately, because they are different facts: `asociada al
objeto` and `usada en <variante> con <revision/hash>`.

The visible language does not require the user to know the word `binding`.
`Asociar fuente al objeto` and `Usar revision en una variante` are the two named
actions; `binding de ejecucion` appears only in secondary help.

Like the read catalog, this surface stays behind the verification accounts until
the cutover, and it reads only - every mutation entry point opens the protected
journey delivered in TS7-021.

## Acceptance criteria

- [x] The summary lists generic associations and object-specific series in one view with a visible discriminator per row.
- [x] `Solo este objeto` accompanies every object-specific row and every step that acts on one.
- [x] `asociada al objeto` and `usada en <variante> con <revision/hash>` are shown as two separate states, never collapsed into one.
- [x] The visible language uses `Asociar fuente al objeto` and `Usar revision en una variante`; `binding` appears only in secondary help.
- [x] A stale binding is visibly stale from the object summary, with its blocked execution stated.
- [x] The list pages server-side and never loads points.
- [x] Only verification accounts reach the surface before the cutover.
- [x] `tsc`, `eslint`, `vitest` and the production build pass.
- [x] A Chrome pass with the real `.env` credentials shows an object with both kinds of series and no console errors. Closed on 2026-09-05 during the TS7-021 pass: object 596 of project `TS7-021 verificacion` ends with one generic row (associated, used in `Default` at revision 2) and one object-specific row carrying `Solo este objeto`, with no console messages.

## Blocked by

- [TS7-012: Bind, Read And Archive An Object Specific Series](TS7-012-bind-read-and-archive-an-object-specific-series.md)
- [TS7-019: Build The Layered Read Catalog For Verification Accounts](TS7-019-build-the-layered-read-catalog-for-verification-accounts.md)
