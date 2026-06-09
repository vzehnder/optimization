# BESS-ITER6-008: Finalize Iteration 6 Acceptance Suite And Docs

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: `docs/iter6/prd_client_publication_portal.md`

## User stories covered

77 and full Iteration 6 regression coverage.

## What to build

Finalize Iteration 6 with acceptance coverage and documentation proving the
complete publication workflow: local auth, role-gated analyst access, admin user
management, client project assignment, dashboard templates, publication draft,
client preview, publish/unpublish, read-only portal, allowlisted downloads,
authorization hardening, and regression compatibility with the existing analyst
flows.

This is the closing proof issue, not the first implementation of core behavior.

## Acceptance criteria

- [ ] Documentation explains local auth, roles, sessions, and first-admin
      bootstrap.
- [ ] Documentation explains admin user management and client project access
      assignment.
- [ ] Documentation explains minimal dashboard templates and selected result
      sections.
- [ ] Documentation explains publication drafts, publish/unpublish behavior, and
      preview-as-client workflow.
- [ ] Documentation explains client portal routes and read-only behavior.
- [ ] Documentation explains artifact allowlist defaults and security behavior.
- [ ] Documentation explains revocation behavior for deactivated users, removed
      project access, and unpublished publications.
- [ ] A focused Iteration 6 acceptance suite proves the full central flow end to
      end.
- [ ] Acceptance coverage proves clients see assigned projects and published
      publications only.
- [ ] Acceptance coverage proves clients can download only allowlisted
      artifacts.
- [ ] Acceptance coverage proves clients cannot access analyst controls or
      internal APIs.
- [ ] Acceptance coverage proves publication preview matches the live client
      view.
- [ ] Acceptance coverage proves unpublish and assignment removal revoke access
      immediately.
- [ ] Regression coverage proves existing analyst flows still work for internal
      users.
- [ ] Manual test checklist is added or updated for Iteration 6.
- [ ] Full Python web tests pass.
- [ ] Julia regression tests pass if Iteration 6 touches Julia-facing contracts
      or artifact formats.
- [ ] The Iteration 6 tracker includes final verification instructions.

## Blocked by

BESS-ITER6-001, BESS-ITER6-002, BESS-ITER6-003, BESS-ITER6-004, BESS-ITER6-005, BESS-ITER6-006, BESS-ITER6-007

