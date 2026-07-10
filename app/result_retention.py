from __future__ import annotations

from typing import Any

from app.persistence import AnalystStore

DEFAULT_RESULT_CLEANUP_TARGETS = [
    "dispatch_table",
    "asset_dispatch_table",
    "summary",
]

IMMUTABLE_AUDIT_TARGET_REASONS = {
    "artifacts": "immutable audit data: run artifacts are the rebuild source",
    "scenario_versions": "immutable audit data: executable snapshots cannot be deleted",
    "time_series_sources": "immutable audit data: uploaded sources cannot be deleted",
    "time_series_set_revisions": "immutable audit data: revision history cannot be deleted",
}


def cleanup_run_result_data(
    *,
    store: AnalystStore,
    run_id: int,
    targets: list[str] | None = None,
) -> dict[str, Any]:
    """Remove only rebuildable TS-4 result indexes for one run.

    The accepted TS-5 retention boundary is deliberately narrow: cleanup may
    delete only the TS-4 BBDD indexes because they are fully rebuildable from
    immutable `run_artifacts`. Any audit object requested through this path is
    refused with a stable reason instead of being deleted.
    """
    store.get_run(run_id)
    report: dict[str, Any] = {
        "scope": "run",
        "run_id": run_id,
        "removed": [],
        "kept": {},
        "failed": {},
    }
    for target in _normalized_targets(targets):
        immutable_reason = IMMUTABLE_AUDIT_TARGET_REASONS.get(target)
        if immutable_reason is not None:
            report["kept"][target] = immutable_reason
            continue

        cleanup_fn = _RUN_RESULT_CLEANUP_FNS.get(target)
        if cleanup_fn is None:
            report["failed"][target] = f"unsupported cleanup target: {target}"
            continue
        try:
            removed = cleanup_fn(store, run_id)
        except Exception as error:
            report["failed"][target] = str(error)
            continue
        if removed:
            report["removed"].append(target)
        else:
            report["kept"][target] = "already absent"
    return report


def cleanup_project_result_data(
    *,
    store: AnalystStore,
    project_id: int,
    targets: list[str] | None = None,
) -> dict[str, Any]:
    store.get_project(project_id)
    return {
        "scope": "project",
        "project_id": project_id,
        "runs": [
            cleanup_run_result_data(store=store, run_id=int(run["id"]), targets=targets)
            for run in store.list_project_succeeded_runs(project_id)
        ],
    }


def _normalized_targets(targets: list[str] | None) -> list[str]:
    ordered = DEFAULT_RESULT_CLEANUP_TARGETS if not targets else list(targets)
    normalized: list[str] = []
    seen: set[str] = set()
    for target in ordered:
        name = str(target).strip()
        if not name or name in seen:
            continue
        seen.add(name)
        normalized.append(name)
    return normalized


_RUN_RESULT_CLEANUP_FNS = {
    "dispatch_table": lambda store, run_id: store.delete_run_dispatch_result_index(run_id),
    "asset_dispatch_table": lambda store, run_id: store.delete_run_asset_dispatch_result_index(run_id),
    "summary": lambda store, run_id: store.delete_run_summary_result_index(run_id),
}
