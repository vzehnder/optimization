# BESS-ITER6-006: Allowlist Client Artifact Downloads

Status: Done
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

- [x] Publication configuration can enable or disable each registered run
      artifact for client download.
- [x] `summary_json`, `dispatch_csv`, and `asset_dispatch_csv` are easy to
      enable as default client artifacts.
- [x] Technical artifacts such as input snapshots, stdout logs, stderr logs,
      model metadata, and resolved system cases are disabled by default.
- [x] Client publication pages list only enabled downloads.
- [x] Clients can download enabled artifacts for active publications in assigned
      projects.
- [x] Clients cannot download disabled artifacts even if they guess the route.
- [x] Clients cannot download artifacts from unassigned projects.
- [x] Clients cannot download artifacts from draft or unpublished publications.
- [x] Unauthenticated users cannot download client artifacts.
- [x] Internal users retain access to existing internal artifact downloads.
- [x] Download responses preserve useful filenames and media types where the
      existing artifact registry provides them.

## Implementation notes

Completed on 2026-06-12.

- Added client publication download rendering that lists only artifacts selected
  by the publication allowlist and backed by safe registered artifact paths.
- Added a client download route under
  `/client/projects/{project_id}/publications/{publication_id}/artifacts/{artifact_type}/download`
  that enforces client authentication, project assignment, published status,
  allowlist membership, and artifact path safety before returning a file.
- Preserved existing internal artifact download behavior through
  `/api/run-artifacts/{artifact_id}/download`, including preview-as-client
  download links for internal users.
- Kept default publication artifact selection on `summary_json`,
  `dispatch_csv`, and `asset_dispatch_csv`; technical artifacts remain hidden
  from clients unless explicitly selected.

## Verification

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_iter6_client_publications.Iteration6ClientPublicationTests.test_client_downloads_only_allowlisted_artifacts_for_active_assigned_publication -v
.\.venv\Scripts\python.exe -m unittest tests.test_iter6_auth tests.test_iter6_project_access tests.test_iter6_dashboard_templates tests.test_iter6_publications tests.test_iter6_client_publications -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## Blocked by

BESS-ITER6-005
