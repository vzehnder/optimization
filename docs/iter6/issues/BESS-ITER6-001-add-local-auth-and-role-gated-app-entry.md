# BESS-ITER6-001: Add Local Auth And Role-Gated App Entry

Status: Todo
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

- [ ] The application supports local users with roles `admin`, `analyst`, and
      `client`.
- [ ] Passwords are stored hashed, never as plaintext.
- [ ] A controlled bootstrap path can create the first `admin` user when the app
      has no users.
- [ ] Users can log in with valid credentials.
- [ ] Invalid credentials fail without creating a session.
- [ ] Deactivated users cannot log in.
- [ ] Logged-in users can log out and lose access to protected pages.
- [ ] Unauthenticated requests to analyst pages redirect to login or return an
      unauthorized response as appropriate for the route.
- [ ] Authenticated internal users can still access the existing analyst app.
- [ ] Authenticated clients are routed to a client area rather than analyst
      pages.
- [ ] Role/session helpers are reusable by later routes and tests.
- [ ] Existing analyst smoke/API behavior is not broken for authenticated
      internal users.

## Blocked by

BESS-ITER6-000

