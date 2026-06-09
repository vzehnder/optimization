# BESS-ITER6-004: Create Publication Drafts From Succeeded Runs

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: `docs/iter6/prd_client_publication_portal.md`

## User stories covered

38 through 50, 56

## What to build

Add publication drafts as the controlled layer between internal succeeded runs
and future client visibility. An internal user should create a publication from
a succeeded run, choose a dashboard template, set a public title and notes, and
select default downloadable artifacts. Creating the publication should not make
it visible to clients until it is explicitly published.

The publication must preserve traceability to project, scenario, scenario
version, run, template, allowed artifacts, status, and audit metadata.

## Acceptance criteria

- [ ] Internal users can create a publication from a succeeded run.
- [ ] Queued, running, failed, or otherwise incomplete runs cannot be published.
- [ ] A publication stores project, scenario, scenario version, and run
      references.
- [ ] A publication stores public title and analyst notes.
- [ ] A publication stores the selected dashboard template.
- [ ] A publication starts in a non-client-visible draft state.
- [ ] Default artifact download candidates are `summary_json`, `dispatch_csv`,
      and `asset_dispatch_csv`.
- [ ] Technical artifacts are disabled by default.
- [ ] Internal users can edit title, notes, selected template, and artifact
      allowlist while the publication is a draft.
- [ ] Creating or editing a publication does not modify the underlying run,
      scenario version, input snapshot, or artifact files.
- [ ] Publication audit fields record creation and update metadata.
- [ ] The publication model remains separate from the run model.

## Blocked by

BESS-ITER6-003

