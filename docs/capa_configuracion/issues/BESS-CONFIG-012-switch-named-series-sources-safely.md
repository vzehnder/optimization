# BESS-CONFIG-012: Switch Named Series Sources Safely

Status: In Review
Type: AFK
Triage: ready-for-agent
Source: `docs/capa_configuracion/architecture_configuration_layer_final.md`

## What to build

Let an operator choose only among the public source options named by the
console configuration. Selecting a different source creates or activates the
correct operational copy, archives the replaced copy, and atomically repoints
the console-owned variant. The UI updates the table and run inputs without ever
accepting an arbitrary catalog-set identifier from the operator.

## Acceptance criteria

- [x] Each configured column exposes only public source-option ids and labels permitted for that column.
- [x] The operator payload never contains source set ids, copy ids, signal keys or binding ids.
- [x] Selecting the default or another named source resolves its configured set on the backend and validates project, signal, entity and coverage compatibility.
- [x] A new selection creates a flat operational copy with origin set and origin revision recorded.
- [x] Columns that refer to the same source set share one operational copy instead of duplicating it.
- [x] Selection changes and all affected variant bindings commit atomically.
- [x] The replaced copy is archived but not deleted, regenerated or rewritten.
- [x] The next values load and run use the newly selected copy, while canonical sets and other consoles remain unchanged.
- [x] A stale configuration option, guessed option id or incompatible source fails without changing the active selection.
- [x] UI and integration tests cover initial selection, switching, shared-copy reuse, invalid selection and running with the new source.

## Blocked by

- [BESS-CONFIG-010: Edit One Exposed Series Without Changing Canonical Data](BESS-CONFIG-010-edit-one-exposed-series-without-changing-canonical-data.md)

## Implementation notes

- `GET /api/console/{id}/series-options` exposes only configured group/column
  coordinates, public option ids and labels, plus the active public option id.
- `PUT /api/console/{id}/series-selections` resolves every option server-side,
  validates project, signal, entity and current-period coverage, then commits all
  copy creation/reuse, binding changes and archival in one database transaction.
- Operational copies stay flat, record their canonical origin and revision, are
  shared within one console when columns choose the same source, and are archived
  only after no binding in that console-owned variant references them.
- The React console switches by public option id and refreshes the effective
  table and run inputs immediately. Persistence, HTTP, run-materialization and UI
  tests cover the success, reuse, rollback and incompatibility paths.
