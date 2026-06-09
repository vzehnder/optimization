# BESS-ITER6-002: Manage Users And Client Project Access

Status: Todo
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

- [ ] Admin users can create `client`, `analyst`, and `admin` users.
- [ ] Created users have hashed passwords and active status by default.
- [ ] Admin users can list users and see role and active/deactivated state.
- [ ] Admin users can deactivate a user.
- [ ] Deactivated users cannot log in or access protected routes.
- [ ] Admin users can assign a client user to a project.
- [ ] Admin users can remove a client user's assignment from a project.
- [ ] One client can be assigned to multiple projects.
- [ ] One project can be assigned to multiple clients.
- [ ] Client project lists include only explicitly assigned projects.
- [ ] Unassigned projects are inaccessible to client users even if URLs are
      guessed.
- [ ] Removing an assignment immediately removes client access to that project.
- [ ] Analyst modeling controls remain unavailable to client users.

## Blocked by

BESS-ITER6-001

