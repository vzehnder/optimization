# BESS-ITER6-002: Manage Users And Client Project Access

Status: Done
Type: AFK
Triage: ready-for-agent
Source: `docs/iter6/prd_client_publication_portal.md`

## User stories covered

10 through 22

## What to build

Add minimal admin-controlled user management and explicit client-to-project
assignment. Admins should be able to create internal and client users, view
users, deactivate users, assign clients to projects, and remove assignments.
Clients should only see projects explicitly assigned to them.

This slice should make project access real before any publication is exposed in
the client portal.

## Acceptance criteria

- [x] Admin users can create `client`, `analyst`, and `admin` users.
- [x] Created users have hashed passwords and active status by default.
- [x] Admin users can list users and see role and active/deactivated state.
- [x] Admin users can deactivate a user.
- [x] Deactivated users cannot log in or access protected routes.
- [x] Admin users can assign a client user to a project.
- [x] Admin users can remove a client user's assignment from a project.
- [x] One client can be assigned to multiple projects.
- [x] One project can be assigned to multiple clients.
- [x] Client project lists include only explicitly assigned projects.
- [x] Unassigned projects are inaccessible to client users even if URLs are
      guessed.
- [x] Removing an assignment immediately removes client access to that project.
- [x] Analyst modeling controls remain unavailable to client users.

## Implementation notes

Completed on 2026-06-12.

- Added admin-only user management API and SSR page for creating, listing, and
  deactivating local `admin`, `analyst`, and `client` users without exposing
  password hashes in responses.
- Added `project_client_access` many-to-many assignments with admin-only API and
  project-page forms for assigning and removing clients.
- Added client portal project listing/detail pages that show only explicitly
  assigned projects and return `404` for guessed unassigned project URLs.
- Hardened active-session lookup so deactivated users immediately lose access to
  protected routes.

## Verification

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_iter6_project_access -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## Blocked by

BESS-ITER6-001
