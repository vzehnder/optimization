# BESS-ITER6-001: Add Local Auth And Role-Gated App Entry

Status: Done
Type: AFK
Triage: ready-for-agent
Source: `docs/iter6/prd_client_publication_portal.md`

## User stories covered

1 through 9

## What to build

Add the first authenticated application boundary. Internal and client users
should log in through a local account, receive a session, be routed according to
role, and be blocked from protected pages when unauthenticated. This slice
creates the foundation for later user management, project access, publication,
and client portal work.

The implementation should include a controlled bootstrap path for the first
admin user and should preserve the existing analyst workflow for authenticated
internal users.

## Acceptance criteria

- [x] The application supports local users with roles `admin`, `analyst`, and
      `client`.
- [x] Passwords are stored hashed, never as plaintext.
- [x] A controlled bootstrap path can create the first `admin` user when the app
      has no users.
- [x] Users can log in with valid credentials.
- [x] Invalid credentials fail without creating a session.
- [x] Deactivated users cannot log in.
- [x] Logged-in users can log out and lose access to protected pages.
- [x] Unauthenticated requests to analyst pages redirect to login or return an
      unauthorized response as appropriate for the route.
- [x] Authenticated internal users can still access the existing analyst app.
- [x] Authenticated clients are routed to a client area rather than analyst
      pages.
- [x] Role/session helpers are reusable by later routes and tests.
- [x] Existing analyst smoke/API behavior is not broken for authenticated
      internal users.

## Blocked by

BESS-ITER6-000

## Implementation notes

Completed on 2026-06-09.

- Added local `users` and `auth_sessions` tables to the SQLite-backed
  `AnalystStore`.
- Added PBKDF2-SHA256 password hashing and opaque server-side session tokens.
- Added `/bootstrap`, `/login`, `/logout`, `/client`, and `/api/auth/me`.
- Added a central FastAPI auth/role boundary. Internal routes require `admin`
  or `analyst`; client users land in `/client` and receive `403` for analyst
  pages and APIs.
- Kept `create_app()` programmatic tests unauthenticated by default to preserve
  previous iteration tests, while `app.main:app` starts with auth enabled for
  local `uvicorn` usage.

## Verification

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_iter6_auth -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```
