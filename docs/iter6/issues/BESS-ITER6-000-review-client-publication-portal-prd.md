# BESS-ITER6-000: Review Client Publication Portal PRD

Status: Done
Type: HITL
Triage: ready-for-agent
Source: `docs/iter6/prd_client_publication_portal.md`

## User stories covered

All Iteration 6 user stories.

## What to build

Review the Iteration 6 PRD before implementation begins. Confirm that the
iteration should focus on local authentication, role boundaries, client project
assignment, minimal dashboard templates, publication of succeeded runs, a
read-only client portal, allowlisted downloads, and authorization hardening.

This issue should resolve any remaining product or architecture questions before
agents start implementation work.

## Acceptance criteria

- [x] The PRD is reviewed against the final product objective.
- [x] The scope is confirmed as client publication and read-only portal work,
      not scheduled runs or new optimizer modeling.
- [x] The role model is accepted: `admin`, `analyst`, and `client`.
- [x] The local auth approach is accepted: hashed passwords, sessions,
      bootstrap first admin, and no self-signup.
- [x] The project access model is accepted as explicit many-to-many client to
      project assignment.
- [x] The publication model is accepted as a separate entity above succeeded
      runs.
- [x] The dashboard-template scope is accepted as minimal configuration of
      existing result sections.
- [x] The artifact download allowlist behavior is accepted.
- [x] The out-of-scope list is accepted, especially scheduled runs, public
      links, OAuth/SSO, Supabase Auth, advanced dashboard builder, and
      deployment hardening.
- [x] Any accepted corrections are reflected in the PRD before implementation
      slices begin.

## Review outcome

Reviewed on 2026-06-09 against `docs/final/objetivo_final.md`, the completed
Iteration 2 one-bus optimizer contract, the completed Iteration 3 analyst web
workflow, the completed Iteration 4 structured editor and ingestion workflow,
and the completed Iteration 5 simple reservoir hydropower workflow.

Accepted the PRD as the Iteration 6 implementation contract. No corrections
were required before starting downstream client-publication implementation.

## Accepted decisions

- Accepted Iteration 6 as a product-boundary iteration around authentication,
  role-gated app entry, controlled publication, and a read-only client portal,
  without new optimizer modeling.
- Accepted the role model: `admin` manages users and project assignments,
  `analyst` manages internal modeling, templates, previews, and publications,
  and `client` only reads assigned published results.
- Accepted local authentication with hashed passwords, login/logout,
  server-side sessions, a bootstrap path for the first internal admin, and no
  public self-signup.
- Accepted explicit many-to-many client-to-project assignments as the project
  access model, with immediate revocation when assignment is removed.
- Accepted publications as separate entities above succeeded runs so run
  records stay internal, immutable, auditable, and not directly public.
- Accepted minimal dashboard templates as server-enforced visibility settings
  over existing summary, chart, and table sections rather than a dashboard
  builder.
- Accepted artifact allowlisting per publication, with useful business
  artifacts enabled deliberately and internal technical artifacts disabled by
  default.
- Accepted immediate revocation semantics for unpublished publications,
  deactivated users, removed project assignments, and non-allowlisted
  downloads.
- Accepted the out-of-scope list, especially scheduled runs, public links,
  OAuth/SSO, Supabase Auth, customer editing, advanced dashboard building, and
  deployment hardening.
- Accepted the vertical slice breakdown in `tracker_iter6.md` as implementable
  after this review gate.

## Verification

Documentation review only. No executable application code changed, so no
automated test command was required for this issue.

TDD note: this HITL gate has no public runtime interface change; the acceptance
criteria above served as the behavior checklist for the documentation review.

## Blocked by

None - can start immediately.
