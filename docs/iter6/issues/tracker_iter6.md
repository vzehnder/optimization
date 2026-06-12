# BESS Iteration 6 Issue Tracker

This document is the local tracker for the client publication and read-only
portal iteration derived from
`docs/iter6/prd_client_publication_portal.md`.

External issue tracker integration has not been configured, so each issue is
stored as a Markdown file in this folder. All issues carry the `ready-for-agent`
triage label.

## Status Vocabulary

- `Todo`: not started.
- `In Progress`: actively being implemented.
- `Blocked`: waiting on a dependency or decision.
- `In Review`: implementation is ready for review.
- `Done`: merged or accepted.

## Issue Register

| ID | Title | Type | Triage | Status | Blocked by | Issue file |
| --- | --- | --- | --- | --- | --- | --- |
| BESS-ITER6-000 | Review Client Publication Portal PRD | HITL | ready-for-agent | Done | None | [BESS-ITER6-000-review-client-publication-portal-prd.md](BESS-ITER6-000-review-client-publication-portal-prd.md) |
| BESS-ITER6-001 | Add Local Auth And Role-Gated App Entry | AFK | ready-for-agent | Done | BESS-ITER6-000 | [BESS-ITER6-001-add-local-auth-and-role-gated-app-entry.md](BESS-ITER6-001-add-local-auth-and-role-gated-app-entry.md) |
| BESS-ITER6-002 | Manage Users And Client Project Access | AFK | ready-for-agent | Done | BESS-ITER6-001 | [BESS-ITER6-002-manage-users-and-client-project-access.md](BESS-ITER6-002-manage-users-and-client-project-access.md) |
| BESS-ITER6-003 | Create Minimal Dashboard Templates | AFK | ready-for-agent | Done | BESS-ITER6-001 | [BESS-ITER6-003-create-minimal-dashboard-templates.md](BESS-ITER6-003-create-minimal-dashboard-templates.md) |
| BESS-ITER6-004 | Create Publication Drafts From Succeeded Runs | AFK | ready-for-agent | Done | BESS-ITER6-003 | [BESS-ITER6-004-create-publication-drafts-from-succeeded-runs.md](BESS-ITER6-004-create-publication-drafts-from-succeeded-runs.md) |
| BESS-ITER6-005 | Publish And Preview Client-Visible Results | AFK | ready-for-agent | Done | BESS-ITER6-002, BESS-ITER6-004 | [BESS-ITER6-005-publish-and-preview-client-visible-results.md](BESS-ITER6-005-publish-and-preview-client-visible-results.md) |
| BESS-ITER6-006 | Allowlist Client Artifact Downloads | AFK | ready-for-agent | Todo | BESS-ITER6-005 | [BESS-ITER6-006-allowlist-client-artifact-downloads.md](BESS-ITER6-006-allowlist-client-artifact-downloads.md) |
| BESS-ITER6-007 | Harden Authorization And Revocation | AFK | ready-for-agent | Todo | BESS-ITER6-002, BESS-ITER6-005, BESS-ITER6-006 | [BESS-ITER6-007-harden-authorization-and-revocation.md](BESS-ITER6-007-harden-authorization-and-revocation.md) |
| BESS-ITER6-008 | Finalize Iteration 6 Acceptance Suite And Docs | AFK | ready-for-agent | Todo | BESS-ITER6-001 through BESS-ITER6-007 | [BESS-ITER6-008-finalize-iteration-6-acceptance-suite-and-docs.md](BESS-ITER6-008-finalize-iteration-6-acceptance-suite-and-docs.md) |

## Recommended Execution Order

1. BESS-ITER6-000
2. BESS-ITER6-001
3. BESS-ITER6-002 and BESS-ITER6-003 can proceed after auth exists.
4. BESS-ITER6-004 follows dashboard templates because a publication references
   a selected client-facing template.
5. BESS-ITER6-005 joins project access and publication drafts into the first
   client-visible portal path.
6. BESS-ITER6-006 adds secure client artifact downloads after the client portal
   can render active publications.
7. BESS-ITER6-007 hardens authorization and revocation across the completed
   surface.
8. BESS-ITER6-008 closes the iteration with acceptance coverage and docs.

## Progress Log

| Date | Issue | Status change | Notes |
| --- | --- | --- | --- |
| 2026-06-09 | All | Created | Initial local issue set generated from the Iteration 6 PRD and approved vertical-slice breakdown. |
| 2026-06-09 | BESS-ITER6-000 | Todo -> Done | Reviewed and accepted the client publication and read-only portal PRD against the final objective, completed Iteration 2 optimizer contract, completed Iteration 3 analyst workflow, completed Iteration 4 structured editor workflow, and completed Iteration 5 hydro workflow. No PRD corrections were required. |
| 2026-06-09 | BESS-ITER6-001 | Todo -> Done | Added local users, hashed passwords, bootstrap first-admin flow, login/logout, server-side sessions, reusable auth helpers, role-gated internal/client routing, and focused auth acceptance coverage while preserving previous analyst regression suites. |
| 2026-06-12 | BESS-ITER6-002 | Todo -> Done | Added admin user management, deactivation-immediate session blocking, many-to-many client-project assignments, filtered client project portal pages, and focused authorization/project-access coverage. |
| 2026-06-12 | BESS-ITER6-003 | Todo -> Done | Added project-scoped dashboard templates with section toggles, table preview limits, SSR project-page controls, internal APIs, template-filtered result rendering over existing result readers, missing-column fallbacks, and focused dashboard-template acceptance coverage. |
| 2026-06-12 | BESS-ITER6-004 | Todo -> Done | Added publication draft persistence above succeeded runs, internal API and SSR run-page controls for creating/editing draft title, notes, template, and artifact allowlist, default business artifact selection, project-template scoping, incomplete-run rejection, and focused publication draft coverage. |
| 2026-06-12 | BESS-ITER6-005 | Todo -> Done | Added preview-as-client, publish/unpublish state transitions, client project active-publication listings, client publication result pages with template-filtered summary/charts/table previews, and immediate client revocation on unpublish. |

## Regression Guard

Every Iteration 6 slice that changes the Python web application should run the
relevant backend/API/template tests introduced for Iterations 3, 4, 5, and 6.

Slices touching authorization must prove both positive internal access and
negative client access for the affected routes.

The Julia regression suite is required only if the slice changes Julia-facing
contracts, optimizer behavior, or artifact formats. Iteration 6 is expected to
avoid those changes.

## Final Iteration 6 Verification

The closing acceptance slice must run the focused Iteration 6 acceptance suite:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_iter6_acceptance -v
```

It must also run the full Python web acceptance suite:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

If any Iteration 6 work changes Julia-facing contracts or artifact formats, it
must also keep the Julia optimizer regression suite green:

```powershell
julia --project=. -e "import Pkg; Pkg.test()"
```

The final acceptance coverage must prove local auth, role-gated analyst access,
admin-created client users, client project assignment, dashboard templates,
publication drafts, preview-as-client, publish/unpublish, client portal result
review, allowlisted downloads, revocation, and preservation of previous analyst
flows.

## Dependency Notes

- BESS-ITER6-000 is HITL because the publication and portal scope should be
  accepted before implementation.
- BESS-ITER6-001 creates the authentication and role boundary that all other
  slices depend on.
- BESS-ITER6-002 creates client project access before any client-visible
  publication path exists.
- BESS-ITER6-003 creates the minimal dashboard template that publications
  reference.
- BESS-ITER6-004 creates the publication draft layer over succeeded runs without
  exposing it to clients yet.
- BESS-ITER6-005 creates the first complete client-visible read-only path.
- BESS-ITER6-006 secures artifact downloads after the client result page exists.
- BESS-ITER6-007 is intentionally late because it audits the full route and API
  surface created by the previous slices.
- BESS-ITER6-008 is the final proof that the iteration satisfies the PRD and
  preserves previous iteration behavior.
