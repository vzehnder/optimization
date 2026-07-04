# BESS-TS2-009: Finalize TS-2 Acceptance Suite And Docs

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter2/prd.md`
Fecha de inicio planificada: 2026-07-29
Fecha de termino planificada: 2026-07-29

## User stories covered

1 through 23

## What to build

Close TS-2 with acceptance coverage, documentation and tracker updates. The
iteration is complete when time-series sets are first-class database objects:
importable from CSV and XLSX, versioned with labels and revisions, hashed,
correctable manually or by file replacement, and browsable per project, even
though no optimization case uses them yet.

No new product behavior should be introduced in this slice beyond final
hardening required by acceptance tests. Documentation should explain the
catalog model and make explicit that case bindings, dropdown runs and result
series remain deferred to TS-3 and TS-4.

## Acceptance criteria

- [ ] A focused TS-2 acceptance test proves the library story end to end: CSV import, XLSX import, manual edit revision, file replacement revision and catalog visibility.
- [ ] Acceptance coverage proves validation failures are tied to source row and column.
- [ ] Acceptance coverage proves revisions and content hashes are stable audit anchors across edits and replacements.
- [ ] Documentation explains the final TS-2 catalog model and the work deferred to TS-3 and TS-4.
- [ ] A manual test checklist is added under `docs/series_tiempo/iter2/`.
- [ ] The issue tracker progress log is updated and final verification commands are recorded.
- [ ] The README or relevant docs point to the TS-2 catalog documentation if appropriate.
- [ ] No case binding or run-from-series behavior is introduced early.

## Blocked by

BESS-TS2-001 through BESS-TS2-008
