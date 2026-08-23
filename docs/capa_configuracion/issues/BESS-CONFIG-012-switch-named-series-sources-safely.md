# BESS-CONFIG-012: Switch Named Series Sources Safely

Status: Todo
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

- [ ] Each configured column exposes only public source-option ids and labels permitted for that column.
- [ ] The operator payload never contains source set ids, copy ids, signal keys or binding ids.
- [ ] Selecting the default or another named source resolves its configured set on the backend and validates project, signal, entity and coverage compatibility.
- [ ] A new selection creates a flat operational copy with origin set and origin revision recorded.
- [ ] Columns that refer to the same source set share one operational copy instead of duplicating it.
- [ ] Selection changes and all affected variant bindings commit atomically.
- [ ] The replaced copy is archived but not deleted, regenerated or rewritten.
- [ ] The next values load and run use the newly selected copy, while canonical sets and other consoles remain unchanged.
- [ ] A stale configuration option, guessed option id or incompatible source fails without changing the active selection.
- [ ] UI and integration tests cover initial selection, switching, shared-copy reuse, invalid selection and running with the new source.

## Blocked by

- [BESS-CONFIG-010: Edit One Exposed Series Without Changing Canonical Data](BESS-CONFIG-010-edit-one-exposed-series-without-changing-canonical-data.md)
