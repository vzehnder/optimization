# BESS-REACT-009: Migrate Admin Users And Project Access

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: `docs/react_migration/prd_react_ui_migration.md`

## User stories covered

68 and 69

## What to build

Migrate local user administration and client project assignment to React. An
admin can list users, create role-specific accounts, deactivate users, and add
or remove client access within a project. Analysts retain their allowed project
workflow but do not gain admin-only account controls.

The UI should make irreversible or immediately revoking actions explicit while
the backend remains the permission authority.

## Acceptance criteria

- [ ] Admins can list users without receiving password hashes or session secrets.
- [ ] Admins can create `admin`, `analyst`, and `client` accounts with validated
      email, display name, password, and role input.
- [ ] Duplicate or invalid account input returns a safe actionable error.
- [ ] Admins can deactivate an active user through an intentional confirmation.
- [ ] Deactivation immediately prevents new and existing session access.
- [ ] Project administration lists eligible clients and current assignments.
- [ ] Admins can assign a client to a project and remove an existing assignment.
- [ ] Assignment state refreshes without a full page reload.
- [ ] Analysts and clients cannot call admin user or assignment mutations.
- [ ] Cross-project assignment requests remain scoped and auditable.
- [ ] Keyboard focus and status feedback are correct after dialogs and mutations.
- [ ] Browser acceptance covers account creation, assignment, removal,
      deactivation, and analyst/client denial.
- [ ] Existing admin user, project access, session, and authorization tests
      remain green.

## Blocked by

- BESS-REACT-001
- BESS-REACT-002

