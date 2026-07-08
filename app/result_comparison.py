from __future__ import annotations

from typing import Any

from app.persistence import AnalystStore
from app.result_indexing import run_results_fully_indexed


class ComparisonError(ValueError):
    def __init__(self, message: str, *, status_code: int = 409):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def compare_runs(
    *,
    store: AnalystStore,
    baseline_run_id: int,
    candidate_run_id: int,
    series: str | None = None,
) -> dict[str, Any]:
    baseline_run = store.get_run(baseline_run_id)
    candidate_run = store.get_run(candidate_run_id)

    for label, run in (("baseline", baseline_run), ("candidate", candidate_run)):
        if run["status"] != "succeeded":
            raise ComparisonError(f"the {label} run has not succeeded and cannot be compared")

    baseline_scenario_id = store.get_run_lineage(int(baseline_run["id"]))["scenario_id"]
    candidate_scenario_id = store.get_run_lineage(int(candidate_run["id"]))["scenario_id"]
    if baseline_scenario_id != candidate_scenario_id:
        raise ComparisonError(
            "the baseline and candidate runs must belong to the same case to be compared",
            status_code=422,
        )

    for label, run in (("baseline", baseline_run), ("candidate", candidate_run)):
        if not run_results_fully_indexed(store, int(run["id"])):
            raise ComparisonError(
                f"the {label} run {run['id']} has no indexed results yet; rebuild it via "
                f"POST /api/admin/runs/{run['id']}/rebuild-results before comparing"
            )

    baseline_summary = store.get_run_summary_result_index(int(baseline_run["id"]))
    candidate_summary = store.get_run_summary_result_index(int(candidate_run["id"]))
    baseline_dispatch = store.get_run_dispatch_result_index(int(baseline_run["id"]))
    candidate_dispatch = store.get_run_dispatch_result_index(int(candidate_run["id"]))

    kpis = diff_summary_kpis(
        (baseline_summary or {}).get("summary", {}),
        (candidate_summary or {}).get("summary", {}),
    )

    available_signal_keys = sorted(
        set((baseline_dispatch or {}).get("signal_keys", {}).values())
        & set((candidate_dispatch or {}).get("signal_keys", {}).values())
    )
    selected_series = series if series in available_signal_keys else None
    if selected_series is None and available_signal_keys:
        selected_series = available_signal_keys[0]
    series_periods = None
    if selected_series is not None:
        series_periods = diff_series_periods(baseline_dispatch, candidate_dispatch, selected_series)

    return {
        "baseline": run_comparison_context(baseline_run, baseline_summary, baseline_dispatch),
        "candidate": run_comparison_context(candidate_run, candidate_summary, candidate_dispatch),
        "kpis": kpis,
        "available_signal_keys": available_signal_keys,
        "selected_series": selected_series,
        "series_periods": series_periods,
    }


def run_comparison_context(
    run: dict[str, Any],
    summary_index: dict[str, Any] | None,
    dispatch_index: dict[str, Any] | None,
) -> dict[str, Any]:
    lineage = (dispatch_index or summary_index or {}).get("lineage", {})
    return {
        "run_id": int(run["id"]),
        "status": run["status"],
        "created_at": run.get("created_at"),
        "finished_at": run.get("finished_at"),
        "scenario_version_id": int(run["scenario_version_id"]),
        "input_variant": lineage.get("input_variant"),
        "date_range": lineage.get("date_range"),
    }


def diff_summary_kpis(
    baseline_summary: dict[str, Any],
    candidate_summary: dict[str, Any],
) -> list[dict[str, Any]]:
    keys = sorted(set(baseline_summary) | set(candidate_summary))
    kpis = []
    for key in keys:
        baseline_value = baseline_summary.get(key)
        candidate_value = candidate_summary.get(key)
        if isinstance(baseline_value, (dict, list)) or isinstance(candidate_value, (dict, list)):
            continue
        delta = None
        if _is_numeric(baseline_value) and _is_numeric(candidate_value):
            delta = candidate_value - baseline_value
        kpis.append(
            {
                "key": key,
                "baseline": baseline_value,
                "candidate": candidate_value,
                "delta": delta,
            }
        )
    return kpis


def diff_series_periods(
    baseline_dispatch: dict[str, Any] | None,
    candidate_dispatch: dict[str, Any] | None,
    signal_key: str,
) -> list[dict[str, Any]]:
    baseline_values = series_values_by_timestamp(baseline_dispatch, signal_key)
    candidate_values = series_values_by_timestamp(candidate_dispatch, signal_key)
    timestamps = sorted(set(baseline_values) | set(candidate_values))
    periods = []
    for timestamp in timestamps:
        baseline_value = baseline_values.get(timestamp)
        candidate_value = candidate_values.get(timestamp)
        delta = None
        if baseline_value is not None and candidate_value is not None:
            delta = candidate_value - baseline_value
        periods.append(
            {
                "timestamp": timestamp,
                "baseline": baseline_value,
                "candidate": candidate_value,
                "delta": delta,
            }
        )
    return periods


def series_values_by_timestamp(
    dispatch_index: dict[str, Any] | None,
    signal_key: str,
) -> dict[str, float]:
    if dispatch_index is None:
        return {}
    signal_keys = dispatch_index.get("signal_keys", {})
    raw_column = next((column for column, key in signal_keys.items() if key == signal_key), None)
    if raw_column is None:
        return {}
    values: dict[str, float] = {}
    for row in dispatch_index["rows"]:
        timestamp = row.get("timestamp")
        raw_value = row.get(raw_column)
        if not timestamp or raw_value in (None, ""):
            continue
        try:
            values[str(timestamp)] = float(raw_value)
        except (TypeError, ValueError):
            continue
    return values


def _is_numeric(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)
