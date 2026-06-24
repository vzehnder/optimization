# BESS-REACT-010: Migrate Read-Only Client Portal

Status: Done
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

- [x] Client-scoped APIs list only projects assigned to the authenticated client.
- [x] A client project lists only currently published publications for that
      assigned project.
- [x] Publication detail returns public title, notes, provenance, template-
      filtered summary, charts, bounded tables, and enabled downloads.
- [x] The React portal renders those results without analyst editing, upload,
      validation, run, template, publication, or internal artifact controls.
- [x] Missing optional result data is hidden or explained without breaking the
      publication.
- [x] Downloads require an active client session, current project assignment,
      published status, allowlist membership, matching run artifact, and safe
      path.
- [x] Draft and unpublished publications are not discoverable or directly
      accessible by clients.
- [x] Removing project assignment revokes project, publication, and download
      access immediately.
- [x] Unpublishing revokes publication and download access immediately.
- [x] User deactivation and session expiry revoke all portal access immediately.
- [x] Client caches are cleared or invalidated after authorization failures so
      protected data is not left rendered.
- [x] Internal users do not accidentally enter the client portal as a substitute
      for the explicit analyst preview flow.
- [x] Browser acceptance proves the full admin assignment to analyst publish to
      client review/download flow plus all material revocation paths.
- [x] Existing client publication, artifact allowlist, project access, and
      authorization-hardening tests remain green.

## Blocked by

- BESS-REACT-008
- BESS-REACT-009
