# BESS-ITER6-005: Publish And Preview Client-Visible Results

Status: Todo
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

- [ ] Internal users can preview a publication before publishing.
- [ ] Preview uses the same renderer and permissions as the live client view.
- [ ] Internal users can publish a draft publication.
- [ ] Internal users can unpublish a published publication.
- [ ] Published publications appear to clients assigned to the publication's
      project.
- [ ] Unpublished or draft publications do not appear to clients.
- [ ] Client project pages list only active publications for assigned projects.
- [ ] Client publication pages show public title and analyst notes.
- [ ] Client publication pages show publication date, scenario version, run date,
      and run status.
- [ ] Client publication pages show summary KPIs when enabled and available.
- [ ] Client publication pages show selected charts when enabled and available.
- [ ] Client publication pages show limited table previews when enabled.
- [ ] Missing chart/table data is hidden or explained gracefully rather than
      breaking the page.
- [ ] Client pages do not render edit, upload, validation, promotion, launch run,
      draft, or internal artifact controls.
- [ ] Unpublishing a publication immediately removes client page access.

## Blocked by

BESS-ITER6-002, BESS-ITER6-004

