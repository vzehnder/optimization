# BESS-ITER6-005: Publish And Preview Client-Visible Results

Status: Done
Type: AFK
Triage: ready-for-agent
Source: `docs/iter6/prd_client_publication_portal.md`

## User stories covered

48 through 64, 67 through 70

## What to build

Connect publication drafts to a real client-visible read-only experience. An
internal user should preview a publication exactly as a client would see it,
publish it, unpublish it, and verify that assigned clients can see active
publications for assigned projects only.

The client view should show publication context, summary KPIs, selected charts,
limited table previews, and no analyst controls.

## Acceptance criteria

- [x] Internal users can preview a publication before publishing.
- [x] Preview uses the same renderer and permissions as the live client view.
- [x] Internal users can publish a draft publication.
- [x] Internal users can unpublish a published publication.
- [x] Published publications appear to clients assigned to the publication's
      project.
- [x] Unpublished or draft publications do not appear to clients.
- [x] Client project pages list only active publications for assigned projects.
- [x] Client publication pages show public title and analyst notes.
- [x] Client publication pages show publication date, scenario version, run date,
      and run status.
- [x] Client publication pages show summary KPIs when enabled and available.
- [x] Client publication pages show selected charts when enabled and available.
- [x] Client publication pages show limited table previews when enabled.
- [x] Missing chart/table data is hidden or explained gracefully rather than
      breaking the page.
- [x] Client pages do not render edit, upload, validation, promotion, launch run,
      draft, or internal artifact controls.
- [x] Unpublishing a publication immediately removes client page access.

## Implementation notes

Completed on 2026-06-12.

- Added publication publish/unpublish state transitions with audit timestamps and
  user attribution while preserving the separate draft entity above runs.
- Added internal API and run-page controls for preview-as-client, publish, and
  unpublish.
- Added client project publication listings that show only active published
  publications for assigned projects.
- Added client publication detail pages that reuse dashboard-template filtered
  result rendering for public title, notes, provenance metadata, summary KPIs,
  selected charts, and limited table previews.
- Kept draft and unpublished publications inaccessible from client routes, so
  unpublishing immediately removes client page access.

## Verification

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_iter6_client_publications -v
.\.venv\Scripts\python.exe -m unittest tests.test_iter6_auth tests.test_iter6_project_access tests.test_iter6_dashboard_templates tests.test_iter6_publications tests.test_iter6_client_publications -v
```

## Blocked by

BESS-ITER6-002, BESS-ITER6-004
