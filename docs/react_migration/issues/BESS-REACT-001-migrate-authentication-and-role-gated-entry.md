# BESS-REACT-001: Migrate Authentication And Role-Gated Entry

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: `docs/react_migration/prd_react_ui_migration.md`

## User stories covered

9 through 18

## What to build

Deliver the first complete React product flow by migrating bootstrap, login,
session restoration, role-aware landing, forbidden handling, and logout. Add
the JSON authentication contracts needed by the browser while preserving the
existing server-side session model and immediate deactivation behavior.

This slice also establishes protection for state-changing same-origin requests
so all later React mutations inherit a secure default.

## Acceptance criteria

- [ ] A fresh installation can create its first admin through a JSON contract
      and React bootstrap screen.
- [ ] Bootstrap closes after the first user exists.
- [ ] Existing users can log in through React with the same credentials and
      receive the existing HTTP-only server-side session cookie.
- [ ] Invalid credentials return a clear, non-enumerating error and do not
      create a session.
- [ ] A page refresh restores identity and role from the backend.
- [ ] Internal users land in the analyst area and clients land in the client
      area.
- [ ] Safe pre-login destinations are restored after authentication; unsafe
      external destinations are rejected.
- [ ] Unauthenticated and forbidden states are handled consistently for both
      page navigation and API requests.
- [ ] Logout invalidates the server session and clears authenticated frontend
      state immediately.
- [ ] Deactivated users cannot establish or continue authenticated access.
- [ ] State-changing API requests enforce an explicit cross-site request
      forgery defense compatible with the same-origin SPA.
- [ ] Production cookie configuration supports secure transport without
      breaking local development or isolated tests.
- [ ] Browser acceptance tests cover bootstrap, valid/invalid login, refresh,
      role landing, logout, and deactivation.
- [ ] Existing authentication and authorization regression tests remain green.

## Blocked by

- BESS-REACT-000

