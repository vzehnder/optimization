# BESS-ITER6-007: Harden Authorization And Revocation

Status: Done
Type: AFK
Triage: ready-for-agent
Source: `docs/iter6/prd_client_publication_portal.md`

## User stories covered

14 through 22, 52, 66 through 69, 71 through 76

## What to build

Harden the security boundary created by the earlier Iteration 6 slices. This
issue should centralize or thoroughly cover authorization checks so clients
cannot access analyst pages, internal APIs, drafts, source uploads, generated
case validation, promotion, manual run launch, internal run pages, unassigned
projects, unpublished publications, or disabled artifacts.

Revocation must be immediate when a user is deactivated, project access is
removed, or a publication is unpublished.

## Acceptance criteria

- [x] Authorization checks use reusable route dependencies or service boundaries
      rather than one-off ad hoc checks.
- [x] Clients cannot access analyst project, scenario, draft, version, run,
      validation, upload, promotion, or run-launch pages.
- [x] Clients cannot use analyst APIs for drafts, source files, validation,
      promotion, run launch, artifacts, or result review.
- [x] Clients cannot access unassigned projects through guessed URLs.
- [x] Clients cannot access draft or unpublished publications through guessed
      URLs.
- [x] Clients cannot access disabled publication artifacts through guessed URLs.
- [x] Deactivated users lose access immediately.
- [x] Removing a client project assignment revokes access to that project's
      publications and downloads immediately.
- [x] Unpublishing a publication revokes client page and download access
      immediately.
- [x] Internal users can still complete existing analyst flows after auth is
      enabled.
- [x] Regression coverage proves Iteration 3/4/5 analyst workflows still work
      for internal users.
- [x] Negative authorization tests cover both SSR routes and API/download routes.

## Implementation notes

Completed on 2026-06-12.

- Added a reusable `AuthorizationService` for active-session lookup, internal,
  admin, client, project-access, and published-publication authorization.
- Routed middleware and client project/publication/download checks through that
  shared boundary instead of repeating project/publication status logic inline.
- Kept `/api/auth/me` available to any active authenticated session while
  preserving the client block on analyst APIs.
- Added focused hardening tests for client SSR denial, analyst API denial,
  allowlisted download access, project-access revocation, unpublish revocation,
  and deactivated-session revocation.

## Verification

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_iter6_authorization_hardening -v
.\.venv\Scripts\python.exe -m unittest tests.test_iter6_auth tests.test_iter6_project_access tests.test_iter6_dashboard_templates tests.test_iter6_publications tests.test_iter6_client_publications tests.test_iter6_authorization_hardening -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## Blocked by

BESS-ITER6-002, BESS-ITER6-005, BESS-ITER6-006
