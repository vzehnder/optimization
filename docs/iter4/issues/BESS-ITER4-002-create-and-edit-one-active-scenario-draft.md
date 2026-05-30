# BESS-ITER4-002: Create And Edit One Active Scenario Draft

Status: Done
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

- [x] A scenario can have one active draft.
- [x] Creating a draft stores an editable structured draft document.
- [x] Updating a draft replaces or patches the structured draft document without
      creating a scenario version.
- [x] A draft can be initialized from an existing scenario version.
- [x] Updating a draft initialized from a version does not mutate the source
      scenario version.
- [x] API endpoints expose draft read/create/update behavior.
- [x] SSR pages expose a basic draft view and save flow.
- [x] Draft persistence uses the same configured app database as projects,
      scenarios, versions, and runs.
- [x] Tests cover one-active-draft behavior, draft updates, initialization from
      version, and version immutability.

## Verification

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Result: passed, 44 tests.

Browser/DevTools verification: Chrome DevTools loaded the rendered structured
draft page, confirmed the editable `structured_draft_json` textarea with a saved
draft document, found no console messages, and captured a screenshot at
`.tmp/iter4_draft_page.png`. The in-app Browser runtime was attempted but failed
locally with `windows sandbox failed: spawn setup refresh`.

## Blocked by

BESS-ITER4-000
