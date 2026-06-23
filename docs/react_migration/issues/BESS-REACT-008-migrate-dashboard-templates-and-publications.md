# BESS-REACT-008: Migrate Dashboard Templates And Publications

Status: Todo
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

- [ ] Analysts can list, create, and update dashboard templates within the
      active project.
- [ ] Template controls cover the existing summary, chart, table, and table-row
      limit options.
- [ ] Templates cannot be read or applied across project boundaries.
- [ ] Analysts can create publication drafts only from succeeded runs.
- [ ] Publication drafts support public title, analyst notes, selected dashboard
      template, and allowed artifact types.
- [ ] Publication edit errors preserve recoverable form state.
- [ ] Preview uses the same client-safe data contract and result presentation as
      a live publication without granting client access to the draft.
- [ ] Analysts can publish eligible drafts and unpublish active publications.
- [ ] Publication state, timestamps, and user attribution refresh after each
      transition.
- [ ] Missing optional result sections degrade gracefully in preview.
- [ ] Client users cannot access template or publication write contracts.
- [ ] Browser acceptance covers template creation, publication draft, edit,
      preview, publish, and unpublish.
- [ ] Existing template, publication, result filtering, and authorization tests
      remain green.

## Blocked by

- BESS-REACT-002
- BESS-REACT-007

