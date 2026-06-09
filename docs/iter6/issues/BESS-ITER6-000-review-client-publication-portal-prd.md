# BESS-ITER6-000: Review Client Publication Portal PRD

Status: Todo
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

- [ ] The PRD is reviewed against the final product objective.
- [ ] The scope is confirmed as client publication and read-only portal work,
      not scheduled runs or new optimizer modeling.
- [ ] The role model is accepted: `admin`, `analyst`, and `client`.
- [ ] The local auth approach is accepted: hashed passwords, sessions,
      bootstrap first admin, and no self-signup.
- [ ] The project access model is accepted as explicit many-to-many client to
      project assignment.
- [ ] The publication model is accepted as a separate entity above succeeded
      runs.
- [ ] The dashboard-template scope is accepted as minimal configuration of
      existing result sections.
- [ ] The artifact download allowlist behavior is accepted.
- [ ] The out-of-scope list is accepted, especially scheduled runs, public
      links, OAuth/SSO, Supabase Auth, advanced dashboard builder, and
      deployment hardening.
- [ ] Any accepted corrections are reflected in the PRD before implementation
      slices begin.

## Blocked by

None - can start immediately.

