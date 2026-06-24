# BESS-REACT-008: Migrate Dashboard Templates And Publications

Status: Done
Type: AFK
Triage: ready-for-agent
Source: `docs/react_migration/prd_react_ui_migration.md`

## User stories covered

63 through 67

## What to build

Migrate the internal curation workflow to React. An analyst can create and edit
project-scoped dashboard templates, create and edit publication drafts from
succeeded runs, preview client-visible results, and publish or unpublish them.

Preview must consume the same client-safe result contract used by the live
portal, while write operations and unpublished data remain restricted to
internal users.

## Acceptance criteria

- [x] Analysts can list, create, and update dashboard templates within the
      active project.
- [x] Template controls cover the existing summary, chart, table, and table-row
      limit options.
- [x] Templates cannot be read or applied across project boundaries.
- [x] Analysts can create publication drafts only from succeeded runs.
- [x] Publication drafts support public title, analyst notes, selected dashboard
      template, and allowed artifact types.
- [x] Publication edit errors preserve recoverable form state.
- [x] Preview uses the same client-safe data contract and result presentation as
      a live publication without granting client access to the draft.
- [x] Analysts can publish eligible drafts and unpublish active publications.
- [x] Publication state, timestamps, and user attribution refresh after each
      transition.
- [x] Missing optional result sections degrade gracefully in preview.
- [x] Client users cannot access template or publication write contracts.
- [x] Browser acceptance covers template creation, publication draft, edit,
      preview, publish, and unpublish.
- [x] Existing template, publication, result filtering, and authorization tests
      remain green.

## Blocked by

- BESS-REACT-002
- BESS-REACT-007
