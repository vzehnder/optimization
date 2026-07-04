# BESS-TS2-007: Replace A Set Version With A New File Upload

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter2/prd.md`
Fecha de inicio planificada: 2026-07-23
Fecha de termino planificada: 2026-07-24

## User stories covered

9, 11, 22

## What to build

Let corrected source data become a new revision instead of a new orphan set.
The analyst uploads another CSV or XLSX against an existing set; the
replacement flows through the shared preview, mapping and validation pipeline,
and on confirmation creates a new revision linked to the new source, recording
user, date and a recalculated content hash. The visible set identity (name,
version label) stays stable.

Audit must survive replacement: prior revisions keep their own source
metadata, hashes and values context, so the history of what data existed when
remains reconstructible. A failed or abandoned replacement leaves the current
revision untouched.

## Acceptance criteria

- [ ] An existing set accepts a replacement CSV or XLSX upload.
- [ ] Replacement flows through the shared preview, mapping and validation pipeline.
- [ ] A confirmed replacement creates a new revision linked to the new source.
- [ ] The new revision records user, date and a recalculated content hash.
- [ ] Prior revisions keep their source metadata and hashes after replacement.
- [ ] A failed or abandoned replacement leaves the current revision untouched.
- [ ] React exposes the replacement flow from the set detail view.

## Blocked by

BESS-TS2-004
