# BESS-REACT-003: Migrate Structured Scenario Draft Editor

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: `docs/react_migration/prd_react_ui_migration.md`

## User stories covered

25 through 34

## What to build

Migrate the structured scenario draft editor as a complete React flow. An
analyst can create or reopen the active draft, edit general one-bus
configuration, add and remove supported assets, edit type-specific settings,
save changes, and understand whether the visible form matches the persisted
draft.

The backend remains the authority for draft shape and domain validation. The UI
should improve local feedback while avoiding parallel saves or stale response
overwrites.

## Acceptance criteria

- [ ] An analyst can create a draft from the scenario context and reopen the
      persisted draft later.
- [ ] The editor supports case identity, schema, time-series metadata, graph,
      grid, and solver settings currently available in the existing UI.
- [ ] The editor can add BESS, load, renewable, and hydro assets supported by the
      backend draft contract.
- [ ] Each asset type exposes its existing physical and economic settings.
- [ ] Asset removal requires an intentional action and persists correctly.
- [ ] Stable client-side constraints provide field-level feedback while the
      backend remains authoritative.
- [ ] The editor visibly distinguishes clean, dirty, saving, saved, and failed
      states.
- [ ] Save requests are serialized and a late response cannot overwrite newer
      local edits.
- [ ] Successful saves reconcile the form with the server representation.
- [ ] Navigation away from unsaved edits requires an explicit keep-editing or
      discard decision.
- [ ] Recoverable save errors do not erase local edits.
- [ ] The editor is keyboard operable and validation errors move focus or expose
      an accessible summary.
- [ ] Browser acceptance covers draft creation, multi-asset editing, save,
      refresh, removal, and one failed-save recovery path.
- [ ] Existing structured draft and hydro editor tests remain green.

## Blocked by

- BESS-REACT-002

