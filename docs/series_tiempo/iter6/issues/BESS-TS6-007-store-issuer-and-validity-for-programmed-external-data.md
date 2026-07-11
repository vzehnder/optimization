# BESS-TS6-007: Store Issuer And Validity For Programmed External Data

Status: Done
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter6/prd.md`
Fecha de inicio planificada: 2026-08-04
Fecha de termino planificada: 2026-08-05
Fecha de inicio real: 2026-07-11
Fecha de termino real: 2026-07-11

## User stories covered

10

## What to build

Make official programmed data traceable: when external data represents a
program or schedule issued by an authority (for example an official dispatch
or price program), its ingestion records who issued it, when it was issued
and for what validity window, on top of the connector-origin metadata from
BESS-TS6-006.

The catalog surfaces this metadata so an analyst browsing programmed sets can
tell which issuer and validity window each version covers, and can pick the
correct program version when binding a variant. When several versions of the
same program exist (reissues, corrections), each is its own revision or
version with its own issuer/validity metadata, never an overwrite, so a run
can always answer "which official program did I use".

This slice extends the `programado` data kind the catalog already
distinguishes, keeping the semantics identical to any other set: validation,
binding, staleness and lineage all keep working; issuer and validity are
metadata, not a new model.

## Acceptance criteria

- [x] Programmed external data records issuer, issue date and validity window at ingestion.
- [x] The catalog list and detail pages surface issuer and validity for programmed sets.
- [x] Reissued or corrected programs land as new revisions/versions with their own metadata; earlier versions remain readable and unchanged.
- [x] A run using a programmed set can be traced back to the exact issuer and validity window it consumed.
- [x] Existing validation, binding and staleness behavior is unchanged for programmed sets.
- [x] Issuer/validity handling is covered by tests with mocked external data.

## Blocked by

BESS-TS6-006
