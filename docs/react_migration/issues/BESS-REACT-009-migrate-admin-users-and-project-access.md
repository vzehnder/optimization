# BESS-REACT-009: Migrate Admin Users And Project Access

Status: Done
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

- [x] Admins can list users without receiving password hashes or session secrets.
- [x] Admins can create `admin`, `analyst`, and `client` accounts with validated
      email, display name, password, and role input.
- [x] Duplicate or invalid account input returns a safe actionable error.
- [x] Admins can deactivate an active user through an intentional confirmation.
- [x] Deactivation immediately prevents new and existing session access.
- [x] Project administration lists eligible clients and current assignments.
- [x] Admins can assign a client to a project and remove an existing assignment.
- [x] Assignment state refreshes without a full page reload.
- [x] Analysts and clients cannot call admin user or assignment mutations.
- [x] Cross-project assignment requests remain scoped and auditable.
- [x] Keyboard focus and status feedback are correct after dialogs and mutations.
- [x] Browser acceptance covers account creation, assignment, removal,
      deactivation, and analyst/client denial.
- [x] Existing admin user, project access, session, and authorization tests
      remain green.

## Blocked by

- BESS-REACT-001
- BESS-REACT-002
