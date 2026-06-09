# BESS-ITER6-006: Allowlist Client Artifact Downloads

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: `docs/iter6/prd_client_publication_portal.md`

## User stories covered

44 through 47, 65, 66, 72, 73

## What to build

Add publication-controlled artifact downloads for clients. A publication should
expose only the run artifacts explicitly enabled by the analyst, and download
routes should enforce authentication, client project assignment, active
publication status, and artifact allowlist membership.

This slice should prevent URL guessing from exposing disabled or internal
artifacts.

## Acceptance criteria

- [ ] Publication configuration can enable or disable each registered run
      artifact for client download.
- [ ] `summary_json`, `dispatch_csv`, and `asset_dispatch_csv` are easy to
      enable as default client artifacts.
- [ ] Technical artifacts such as input snapshots, stdout logs, stderr logs,
      model metadata, and resolved system cases are disabled by default.
- [ ] Client publication pages list only enabled downloads.
- [ ] Clients can download enabled artifacts for active publications in assigned
      projects.
- [ ] Clients cannot download disabled artifacts even if they guess the route.
- [ ] Clients cannot download artifacts from unassigned projects.
- [ ] Clients cannot download artifacts from draft or unpublished publications.
- [ ] Unauthenticated users cannot download client artifacts.
- [ ] Internal users retain access to existing internal artifact downloads.
- [ ] Download responses preserve useful filenames and media types where the
      existing artifact registry provides them.

## Blocked by

BESS-ITER6-005

