# BESS-ITER6-008: Finalize Iteration 6 Acceptance Suite And Docs

Status: Done
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

- [x] Documentation explains local auth, roles, sessions, and first-admin
      bootstrap.
- [x] Documentation explains admin user management and client project access
      assignment.
- [x] Documentation explains minimal dashboard templates and selected result
      sections.
- [x] Documentation explains publication drafts, publish/unpublish behavior, and
      preview-as-client workflow.
- [x] Documentation explains client portal routes and read-only behavior.
- [x] Documentation explains artifact allowlist defaults and security behavior.
- [x] Documentation explains revocation behavior for deactivated users, removed
      project access, and unpublished publications.
- [x] A focused Iteration 6 acceptance suite proves the full central flow end to
      end.
- [x] Acceptance coverage proves clients see assigned projects and published
      publications only.
- [x] Acceptance coverage proves clients can download only allowlisted
      artifacts.
- [x] Acceptance coverage proves clients cannot access analyst controls or
      internal APIs.
- [x] Acceptance coverage proves publication preview matches the live client
      view.
- [x] Acceptance coverage proves unpublish and assignment removal revoke access
      immediately.
- [x] Regression coverage proves existing analyst flows still work for internal
      users.
- [x] Manual test checklist is added or updated for Iteration 6.
- [x] Full Python web tests pass.
- [x] Julia regression tests pass if Iteration 6 touches Julia-facing contracts
      or artifact formats.
- [x] The Iteration 6 tracker includes final verification instructions.

## Blocked by

BESS-ITER6-001, BESS-ITER6-002, BESS-ITER6-003, BESS-ITER6-004, BESS-ITER6-005, BESS-ITER6-006, BESS-ITER6-007

## Implementation Notes

Completed the closing Iteration 6 acceptance proof. Added
`tests.test_iter6_acceptance` to exercise the central client-publication path:
first-admin bootstrap, admin-created analyst and client users, client project
assignment, scenario version creation, manual run execution through the Python
web queue, dashboard template creation, publication draft creation, preview as
client, publish, read-only client portal review, allowlisted download access,
client denial from analyst controls, unpublish revocation, assignment-removal
revocation, and deactivated-user login denial.

Expanded README documentation for local auth, roles, sessions, admin user
management, project access, dashboard templates, publication lifecycle, client
portal routes, artifact allowlists, and revocation. Updated the manual Iteration
6 checklist with a final closing section and kept tracker verification
instructions in place.

## Verification

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_iter6_acceptance -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Julia regression was not required for this slice because no Julia-facing
contracts, optimizer behavior, or artifact formats changed.
