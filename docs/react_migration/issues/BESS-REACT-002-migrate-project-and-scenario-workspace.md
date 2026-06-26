# BESS-REACT-002: Migrate Project And Scenario Workspace

Status: Done
Type: AFK
Triage: ready-for-agent
Source: `docs/react_migration/prd_react_ui_migration.md`

## User stories covered

19 through 24

## What to build

Create the first authenticated analyst workspace in React. Internal users can
list and create projects, open project details, list and create scenarios, and
open scenario history. The flow should use normalized typed API contracts and
preserve entered form data when recoverable failures occur.

This slice should establish the reusable application layout, breadcrumbs,
resource not-found behavior, and empty-state patterns used by later analyst
flows.

## Acceptance criteria

- [ ] Internal users can list projects and open a project directly by URL.
- [ ] Internal users can create a project and see it in the project list without
      a full page reload.
- [ ] Project details show project context and its scenarios.
- [ ] Internal users can create a scenario under the active project and open it.
- [ ] Scenario details show immutable versions and runs when present.
- [ ] Empty project, scenario, version, and run lists explain the appropriate
      next action.
- [ ] Validation and transient request errors preserve recoverable form input.
- [ ] Not-found and forbidden resources produce distinct views.
- [ ] Query invalidation keeps project and scenario lists consistent after
      mutations.
- [ ] Direct links, breadcrumbs, back/forward navigation, and refresh preserve
      the selected project or scenario.
- [ ] Client users cannot access the analyst workspace or its data APIs.
- [ ] Browser acceptance tests prove project creation through scenario creation
      and direct scenario refresh.
- [ ] Existing project, scenario, and authorization tests remain green.

## Blocked by

- BESS-REACT-001
