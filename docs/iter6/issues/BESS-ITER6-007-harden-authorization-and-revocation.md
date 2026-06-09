# BESS-ITER6-007: Harden Authorization And Revocation

Status: Todo
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

- [ ] Authorization checks use reusable route dependencies or service boundaries
      rather than one-off ad hoc checks.
- [ ] Clients cannot access analyst project, scenario, draft, version, run,
      validation, upload, promotion, or run-launch pages.
- [ ] Clients cannot use analyst APIs for drafts, source files, validation,
      promotion, run launch, artifacts, or result review.
- [ ] Clients cannot access unassigned projects through guessed URLs.
- [ ] Clients cannot access draft or unpublished publications through guessed
      URLs.
- [ ] Clients cannot access disabled publication artifacts through guessed URLs.
- [ ] Deactivated users lose access immediately.
- [ ] Removing a client project assignment revokes access to that project's
      publications and downloads immediately.
- [ ] Unpublishing a publication revokes client page and download access
      immediately.
- [ ] Internal users can still complete existing analyst flows after auth is
      enabled.
- [ ] Regression coverage proves Iteration 3/4/5 analyst workflows still work
      for internal users.
- [ ] Negative authorization tests cover both SSR routes and API/download routes.

## Blocked by

BESS-ITER6-002, BESS-ITER6-005, BESS-ITER6-006

