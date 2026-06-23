# BESS-REACT-010: Migrate Read-Only Client Portal

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: `docs/react_migration/prd_react_ui_migration.md`

## User stories covered

70 through 73

## What to build

Deliver the complete read-only React client portal and the client-scoped JSON
contracts it requires. A client can list assigned projects, discover active
publications, review the curated result view, and download allowlisted artifacts.

Every client API must independently enforce role, project assignment,
publication status, selected template, artifact allowlist, and safe file path.
Stale cached UI data must not preserve access after revocation.

## Acceptance criteria

- [ ] Client-scoped APIs list only projects assigned to the authenticated client.
- [ ] A client project lists only currently published publications for that
      assigned project.
- [ ] Publication detail returns public title, notes, provenance, template-
      filtered summary, charts, bounded tables, and enabled downloads.
- [ ] The React portal renders those results without analyst editing, upload,
      validation, run, template, publication, or internal artifact controls.
- [ ] Missing optional result data is hidden or explained without breaking the
      publication.
- [ ] Downloads require an active client session, current project assignment,
      published status, allowlist membership, matching run artifact, and safe
      path.
- [ ] Draft and unpublished publications are not discoverable or directly
      accessible by clients.
- [ ] Removing project assignment revokes project, publication, and download
      access immediately.
- [ ] Unpublishing revokes publication and download access immediately.
- [ ] User deactivation and session expiry revoke all portal access immediately.
- [ ] Client caches are cleared or invalidated after authorization failures so
      protected data is not left rendered.
- [ ] Internal users do not accidentally enter the client portal as a substitute
      for the explicit analyst preview flow.
- [ ] Browser acceptance proves the full admin assignment to analyst publish to
      client review/download flow plus all material revocation paths.
- [ ] Existing client publication, artifact allowlist, project access, and
      authorization-hardening tests remain green.

## Blocked by

- BESS-REACT-008
- BESS-REACT-009

