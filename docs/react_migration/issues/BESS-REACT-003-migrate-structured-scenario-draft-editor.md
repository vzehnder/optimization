# BESS-REACT-003: Migrate Structured Scenario Draft Editor

Status: Done
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

- [x] An analyst can create a draft from the scenario context and reopen the
      persisted draft later.
- [x] The editor supports case identity, schema, time-series metadata, graph,
      grid, and solver settings currently available in the existing UI.
- [x] The editor can add BESS, load, renewable, and hydro assets supported by the
      backend draft contract.
- [x] Each asset type exposes its existing physical and economic settings.
- [x] Asset removal requires an intentional action and persists correctly.
- [x] Stable client-side constraints provide field-level feedback while the
      backend remains authoritative.
- [x] The editor visibly distinguishes clean, dirty, saving, saved, and failed
      states.
- [x] Save requests are serialized and a late response cannot overwrite newer
      local edits.
- [x] Successful saves reconcile the form with the server representation.
- [x] Navigation away from unsaved edits requires an explicit keep-editing or
      discard decision.
- [x] Recoverable save errors do not erase local edits.
- [x] The editor is keyboard operable and validation errors move focus or expose
      an accessible summary.
- [x] Browser acceptance covers draft creation, multi-asset editing, save,
      refresh, removal, and one failed-save recovery path.
- [x] Existing structured draft and hydro editor tests remain green.

## Verification

- `npm.cmd test`
- `npm.cmd run check`
- `npm.cmd run test:browser`
- `.\\.venv\\Scripts\\python.exe -m unittest tests.test_structured_draft_editor tests.test_iter5_acceptance -v`
- Chrome smoke: created a project/scenario, created a React structured draft,
  added BESS, saved, reloaded, and confirmed persisted form state.

## Blocked by

- BESS-REACT-002
