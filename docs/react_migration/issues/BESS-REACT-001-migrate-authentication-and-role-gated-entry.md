# BESS-REACT-001: Migrate Authentication And Role-Gated Entry

Status: Done
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

- [x] A fresh installation can create its first admin through a JSON contract
      and React bootstrap screen.
- [x] Bootstrap closes after the first user exists.
- [x] Existing users can log in through React with the same credentials and
      receive the existing HTTP-only server-side session cookie.
- [x] Invalid credentials return a clear, non-enumerating error and do not
      create a session.
- [x] A page refresh restores identity and role from the backend.
- [x] Internal users land in the analyst area and clients land in the client
      area.
- [x] Safe pre-login destinations are restored after authentication; unsafe
      external destinations are rejected.
- [x] Unauthenticated and forbidden states are handled consistently for both
      page navigation and API requests.
- [x] Logout invalidates the server session and clears authenticated frontend
      state immediately.
- [x] Deactivated users cannot establish or continue authenticated access.
- [x] State-changing API requests enforce an explicit cross-site request
      forgery defense compatible with the same-origin SPA.
- [x] Production cookie configuration supports secure transport without
      breaking local development or isolated tests.
- [x] Browser acceptance tests cover bootstrap, valid/invalid login, refresh,
      role landing, logout, and deactivation.
- [x] Existing authentication and authorization regression tests remain green.

## Blocked by

- BESS-REACT-000
