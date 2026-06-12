# BESS-ITER6-004: Create Publication Drafts From Succeeded Runs

Status: Done
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

- [x] Internal users can create a publication from a succeeded run.
- [x] Queued, running, failed, or otherwise incomplete runs cannot be published.
- [x] A publication stores project, scenario, scenario version, and run
      references.
- [x] A publication stores public title and analyst notes.
- [x] A publication stores the selected dashboard template.
- [x] A publication starts in a non-client-visible draft state.
- [x] Default artifact download candidates are `summary_json`, `dispatch_csv`,
      and `asset_dispatch_csv`.
- [x] Technical artifacts are disabled by default.
- [x] Internal users can edit title, notes, selected template, and artifact
      allowlist while the publication is a draft.
- [x] Creating or editing a publication does not modify the underlying run,
      scenario version, input snapshot, or artifact files.
- [x] Publication audit fields record creation and update metadata.
- [x] The publication model remains separate from the run model.

## Implementation notes

Added a separate `publications` persistence model above succeeded runs. A
publication draft records project, scenario, scenario version, run, dashboard
template, public title, analyst notes, draft status, artifact allowlist, and
creation/update audit metadata without mutating the underlying run or immutable
scenario version.

Added internal API endpoints to list and create run publication drafts and to
edit draft fields. Added server-rendered run-page controls for creating and
editing publication drafts from a succeeded run. Default artifact selections are
limited to `summary_json`, `dispatch_csv`, and `asset_dispatch_csv`; registered
technical artifacts remain available only when explicitly selected by an
internal user.

Queued, running, failed, and incomplete runs are rejected. Dashboard templates
must belong to the run's project. Client users remain blocked from internal
publication routes by the Iteration 6 role boundary.

## Verification

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_iter6_publications -v
.\.venv\Scripts\python.exe -m unittest tests.test_iter6_auth tests.test_iter6_project_access tests.test_iter6_dashboard_templates tests.test_iter6_publications -v
```

## Blocked by

BESS-ITER6-003
