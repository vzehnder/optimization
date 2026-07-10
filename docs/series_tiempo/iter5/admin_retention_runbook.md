# TS-5 Admin Retention Runbook

Fecha: 2026-07-10

## Purpose

TS-5 retention cleanup exists to keep the PostgreSQL result-index tables from
growing without touching immutable audit data.

The accepted boundary is strict:

- Rebuildable derived data: TS-4 result indexes only.
- Immutable audit data: `scenario_versions`, `runs`, `run_artifacts`,
  `time_series_sources`, `time_series_set_revisions`, and any legacy source of
  truth that is not yet migrated.

Cleanup never deletes audit data. If an admin asks for an immutable target
through the cleanup API, the response keeps it and explains why.

## Supported Cleanup Targets

These targets are accepted by both cleanup endpoints:

- `dispatch_table`
- `asset_dispatch_table`
- `summary`
- `artifacts`
- `scenario_versions`
- `time_series_sources`
- `time_series_set_revisions`

Behavior:

- `dispatch_table`, `asset_dispatch_table`, `summary`: removable TS-4 BBDD
  indexes. Safe to rebuild later from `run_artifacts`.
- `artifacts`, `scenario_versions`, `time_series_sources`,
  `time_series_set_revisions`: immutable. Cleanup refuses to delete them and
  reports the reason under `kept`.

If `targets` is omitted or empty, cleanup defaults to the rebuildable set only:

- `dispatch_table`
- `asset_dispatch_table`
- `summary`

## Endpoints

Admin only:

- `POST /api/admin/runs/{run_id}/cleanup-results`
- `POST /api/admin/projects/{project_id}/cleanup-results`

Request body:

```json
{
  "targets": ["dispatch_table", "asset_dispatch_table", "summary", "artifacts"]
}
```

Response shape for a run:

```json
{
  "cleanup": {
    "scope": "run",
    "run_id": 28,
    "removed": ["dispatch_table", "asset_dispatch_table", "summary"],
    "kept": {
      "artifacts": "immutable audit data: run artifacts are the rebuild source"
    },
    "failed": {}
  }
}
```

Response shape for a project:

```json
{
  "cleanup": {
    "scope": "project",
    "project_id": 37,
    "runs": [
      {
        "scope": "run",
        "run_id": 28,
        "removed": ["summary"],
        "kept": {
          "artifacts": "immutable audit data: run artifacts are the rebuild source"
        },
        "failed": {}
      }
    ]
  }
}
```

Repeated cleanup is idempotent:

- already removed rebuildable targets move to `kept` with `already absent`
- immutable targets always stay in `kept`
- no audit row is rewritten

## Restore Path

After cleanup, run results must still render through artifact fallback:

- `GET /api/runs/{run_id}/results`

To rebuild BBDD indexes:

- `POST /api/admin/runs/{run_id}/rebuild-results`
- `POST /api/admin/runs/rebuild-results`

Rebuild reuses the existing TS-4 path and restores the same indexed surfaces:

- `dispatch_table`
- `asset_dispatch_table`
- `summary`

## Operational Notes

- Cleanup is safe only for succeeded runs with registered artifacts.
- If a run has missing or broken artifacts, rebuild may report `failed`; cleanup
  still must not delete audit data.
- Project cleanup iterates succeeded runs of that project only; queued, running
  and failed runs have no TS-4 result indexes to remove.
