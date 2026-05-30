# BESS-ITER4-002: Create And Edit One Active Scenario Draft

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: `docs/iter4/prd_structured_editor_flow.md`

## User stories covered

1 through 5, 55

## What to build

Add the first structured-editor persistence slice: one mutable active draft per
scenario.

An analyst can create, view, and update a draft under a scenario. A draft can be
initialized from an existing immutable scenario version, but draft edits must
never mutate that version. The draft stores a structured application JSON
document and is not directly executable.

## Acceptance criteria

- [ ] A scenario can have one active draft.
- [ ] Creating a draft stores an editable structured draft document.
- [ ] Updating a draft replaces or patches the structured draft document without
      creating a scenario version.
- [ ] A draft can be initialized from an existing scenario version.
- [ ] Updating a draft initialized from a version does not mutate the source
      scenario version.
- [ ] API endpoints expose draft read/create/update behavior.
- [ ] SSR pages expose a basic draft view and save flow.
- [ ] Draft persistence uses the same configured app database as projects,
      scenarios, versions, and runs.
- [ ] Tests cover one-active-draft behavior, draft updates, initialization from
      version, and version immutability.

## Blocked by

BESS-ITER4-000
