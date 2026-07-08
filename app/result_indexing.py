from __future__ import annotations

import csv
import json
import logging
from pathlib import Path
from typing import Any

from app.persistence import AnalystStore


logger = logging.getLogger(__name__)

CORE_DISPATCH_BASE_COLUMNS = {
    "timestamp",
    "grid_import_mw",
    "grid_export_mw",
    "market_value_usd",
    "battery_charge_mw",
    "battery_discharge_mw",
    "battery_energy_mwh",
}
SINGLE_PRICE_COLUMNS = {"price_usd_per_mwh"}
SEPARATE_PRICE_COLUMNS = {"import_price_usd_per_mwh", "export_price_usd_per_mwh"}
ASSET_DISPATCH_BASE_COLUMNS = {"timestamp", "asset_id", "asset_type"}
HYDRO_BASE_COLUMNS = {
    "total_hydro_power_mw",
    "total_hydro_turbine_flow_m3s",
    "total_hydro_spill_flow_m3s",
    "total_hydro_storage_hm3",
}

# Maps raw dispatch.csv column spelling to a canonical signal key so
# downstream read, comparison and publication surfaces do not depend on
# artifact column naming. A missing raw column is simply absent from the
# result, never fabricated.
DISPATCH_SIGNAL_KEY_CATALOG: dict[str, str] = {
    "grid_import_mw": "grid_import_power_mw",
    "grid_export_mw": "grid_export_power_mw",
    "price_usd_per_mwh": "energy_price_usd_per_mwh",
    "import_price_usd_per_mwh": "grid_import_price_usd_per_mwh",
    "export_price_usd_per_mwh": "grid_export_price_usd_per_mwh",
    "market_value_usd": "market_value_usd",
    "battery_charge_mw": "bess_charge_power_mw",
    "battery_discharge_mw": "bess_discharge_power_mw",
    "battery_energy_mwh": "bess_stored_energy_mwh",
    "load_demand_mw": "load_demand_power_mw",
    "renewable_used_mw": "renewable_used_power_mw",
    "renewable_curtailed_mw": "renewable_curtailed_power_mw",
    "total_hydro_power_mw": "hydro_generation_power_mw",
    "total_hydro_inflow_m3s": "hydro_inflow_flow_m3s",
    "total_hydro_turbine_flow_m3s": "hydro_turbine_flow_m3s",
    "total_hydro_spill_flow_m3s": "hydro_spill_flow_m3s",
    "total_hydro_storage_hm3": "hydro_storage_volume_hm3",
    "total_hydro_reservoir_elevation_masl": "hydro_reservoir_elevation_masl",
    "total_hydro_terminal_water_value_usd": "hydro_terminal_water_value_usd",
    "total_hydro_spill_penalty_usd": "hydro_spill_cost_usd",
    "period_profit_usd": "period_profit_usd",
    "battery_degradation_cost_usd": "bess_degradation_cost_usd",
    "curtailment_penalty_usd": "renewable_curtailment_cost_usd",
    "import_cost_usd": "grid_import_cost_usd",
    "export_revenue_usd": "grid_export_revenue_usd",
    "net_market_value_usd": "net_market_value_usd",
}


class ResultIndexingError(ValueError):
    pass


def index_run_dispatch_results(
    *,
    store: AnalystStore,
    run: dict[str, Any],
    artifacts: list[dict[str, Any]],
    artifact_root: Path | str,
) -> dict[str, Any] | None:
    if run["status"] != "succeeded":
        raise ResultIndexingError("run dispatch results can only be indexed for succeeded runs")

    dispatch_artifact = next(
        (artifact for artifact in artifacts if artifact["artifact_type"] == "dispatch_csv"),
        None,
    )
    if dispatch_artifact is None:
        raise ResultIndexingError("dispatch.csv artifact is not registered")

    dispatch_path = resolve_artifact_path(dispatch_artifact["path"], artifact_root)
    try:
        with dispatch_path.open(newline="", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            columns = list(reader.fieldnames or [])
            if not columns:
                raise ResultIndexingError("dispatch.csv is missing a header row")
            if not supports_dispatch_index(columns):
                return None
            rows = [dict(row) for row in reader]
    except OSError as error:
        raise ResultIndexingError(f"dispatch.csv could not be read: {error}") from error

    return store.replace_run_dispatch_result_index(
        run_id=int(run["id"]),
        scenario_version_id=int(run["scenario_version_id"]),
        columns=columns,
        rows=rows,
        signal_keys=dispatch_signal_keys(columns),
    )


def index_run_asset_dispatch_results(
    *,
    store: AnalystStore,
    run: dict[str, Any],
    artifacts: list[dict[str, Any]],
    artifact_root: Path | str,
) -> dict[str, Any] | None:
    if run["status"] != "succeeded":
        raise ResultIndexingError("run asset dispatch results can only be indexed for succeeded runs")

    asset_dispatch_artifact = next(
        (artifact for artifact in artifacts if artifact["artifact_type"] == "asset_dispatch_csv"),
        None,
    )
    if asset_dispatch_artifact is None:
        raise ResultIndexingError("asset_dispatch.csv artifact is not registered")

    asset_dispatch_path = resolve_artifact_path(asset_dispatch_artifact["path"], artifact_root)
    try:
        with asset_dispatch_path.open(newline="", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            columns = list(reader.fieldnames or [])
            if not columns:
                raise ResultIndexingError("asset_dispatch.csv is missing a header row")
            if not supports_asset_dispatch_index(columns):
                return None
            rows = [dict(row) for row in reader]
    except OSError as error:
        raise ResultIndexingError(f"asset_dispatch.csv could not be read: {error}") from error

    return store.replace_run_asset_dispatch_result_index(
        run_id=int(run["id"]),
        scenario_version_id=int(run["scenario_version_id"]),
        columns=columns,
        rows=rows,
    )


def index_run_summary_results(
    *,
    store: AnalystStore,
    run: dict[str, Any],
    artifacts: list[dict[str, Any]],
    artifact_root: Path | str,
) -> dict[str, Any]:
    if run["status"] != "succeeded":
        raise ResultIndexingError("run summary results can only be indexed for succeeded runs")

    summary_artifact = next(
        (artifact for artifact in artifacts if artifact["artifact_type"] == "summary_json"),
        None,
    )
    if summary_artifact is None:
        raise ResultIndexingError("summary.json artifact is not registered")

    summary_path = resolve_artifact_path(summary_artifact["path"], artifact_root)
    try:
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
    except OSError as error:
        raise ResultIndexingError(f"summary.json could not be read: {error}") from error
    except json.JSONDecodeError as error:
        raise ResultIndexingError(
            f"summary.json is malformed JSON: {error.msg} at line {error.lineno}, column {error.colno}"
        ) from error
    if not isinstance(summary, dict):
        raise ResultIndexingError("summary.json must contain a JSON object")

    linked_result_surfaces = []
    if store.get_run_dispatch_result_index(int(run["id"])) is not None:
        linked_result_surfaces.append("dispatch_table")
    if store.get_run_asset_dispatch_result_index(int(run["id"])) is not None:
        linked_result_surfaces.append("asset_dispatch_table")

    return store.replace_run_summary_result_index(
        run_id=int(run["id"]),
        scenario_version_id=int(run["scenario_version_id"]),
        summary=summary,
        linked_result_surfaces=linked_result_surfaces,
    )


def index_run_results(
    *,
    store: AnalystStore,
    run: dict[str, Any],
    artifact_root: Path | str,
) -> dict[str, Any]:
    """Index every TS4 result surface for a succeeded run, never raising.

    Each surface (dispatch, asset dispatch, summary) is indexed independently:
    a failure on one surface is logged and recorded, but never prevents the
    other surfaces from being indexed and never propagates to the caller, so a
    successful run's status and artifacts are never put at risk by indexing.
    Re-invoking this for the same run is safe and will retry any surface that
    previously failed alongside re-affirming the surfaces already indexed.
    """
    run_id = int(run["id"])
    indexed: list[str] = []
    failed: dict[str, str] = {}

    try:
        artifacts = store.list_run_artifacts(run_id)
    except Exception as error:
        logger.error("TS4 result indexing could not list artifacts for run %s: %s", run_id, error)
        return {"run_id": run_id, "indexed": indexed, "failed": {"artifacts": str(error)}}

    for surface, index_fn in (
        ("dispatch_table", index_run_dispatch_results),
        ("asset_dispatch_table", index_run_asset_dispatch_results),
        ("summary", index_run_summary_results),
    ):
        try:
            result = index_fn(store=store, run=run, artifacts=artifacts, artifact_root=artifact_root)
        except Exception as error:
            failed[surface] = str(error)
            logger.error(
                "TS4 result indexing failed for run %s surface %s: %s",
                run_id,
                surface,
                error,
            )
            continue
        if result is not None:
            indexed.append(surface)

    return {"run_id": run_id, "indexed": indexed, "failed": failed}


def run_results_fully_indexed(store: AnalystStore, run_id: int) -> bool:
    """Whether every result surface with a registered artifact already has a BBDD index.

    A run with no registered dispatch/asset-dispatch/summary artifacts at all is
    vacuously "fully indexed": there is nothing a rebuild could add for it.
    """
    artifact_types = {artifact["artifact_type"] for artifact in store.list_run_artifacts(run_id)}
    if "dispatch_csv" in artifact_types and store.get_run_dispatch_result_index(run_id) is None:
        return False
    if "asset_dispatch_csv" in artifact_types and store.get_run_asset_dispatch_result_index(run_id) is None:
        return False
    if "summary_json" in artifact_types and store.get_run_summary_result_index(run_id) is None:
        return False
    return True


def rebuild_run_results(
    *,
    store: AnalystStore,
    run: dict[str, Any],
    artifact_root: Path | str,
    force: bool = False,
) -> dict[str, Any]:
    """Rebuild every TS4 result surface for one historical run from its artifacts.

    Reuses `index_run_results`, so a rebuilt run's indexes are indistinguishable
    from a freshly (live) indexed one: same parsing, normalization, lineage and
    replace-on-write modules. Already fully-indexed runs are skipped unless
    `force` is set, so re-running a bulk rebuild converges without redoing work.
    """
    run_id = int(run["id"])
    if run["status"] != "succeeded":
        return {"run_id": run_id, "status": "failed", "indexed": [], "failed": {"run": "run did not succeed"}}

    if not force and run_results_fully_indexed(store, run_id):
        return {"run_id": run_id, "status": "skipped", "indexed": [], "failed": {}}

    outcome = index_run_results(store=store, run=run, artifact_root=artifact_root)
    status = "failed" if outcome["failed"] else "indexed"
    return {"run_id": run_id, "status": status, "indexed": outcome["indexed"], "failed": outcome["failed"]}


def rebuild_all_run_results(
    *,
    store: AnalystStore,
    artifact_root: Path | str,
    force: bool = False,
) -> dict[str, Any]:
    """Rebuild TS4 result indexes for every historical succeeded run.

    Reports what was indexed, skipped (already fully indexed, not forced),
    partially indexed and failed, keyed by run id.
    """
    report: dict[str, Any] = {"indexed": [], "skipped": [], "failed": {}}
    for run in store.list_succeeded_runs():
        outcome = rebuild_run_results(store=store, run=run, artifact_root=artifact_root, force=force)
        if outcome["status"] == "failed":
            report["failed"][outcome["run_id"]] = outcome["failed"]
        else:
            report[outcome["status"]].append(outcome["run_id"])
    return report


def supports_asset_dispatch_index(columns: list[str]) -> bool:
    return ASSET_DISPATCH_BASE_COLUMNS.issubset(set(columns))


def dispatch_signal_keys(columns: list[str]) -> dict[str, str]:
    return {
        column: DISPATCH_SIGNAL_KEY_CATALOG[column]
        for column in columns
        if column in DISPATCH_SIGNAL_KEY_CATALOG
    }


def supports_dispatch_index(columns: list[str]) -> bool:
    return supports_core_dispatch_index(columns) or supports_hydro_only_dispatch_index(columns)


def supports_core_dispatch_index(columns: list[str]) -> bool:
    column_set = set(columns)
    if not CORE_DISPATCH_BASE_COLUMNS.issubset(column_set):
        return False
    return bool(SINGLE_PRICE_COLUMNS.issubset(column_set) or SEPARATE_PRICE_COLUMNS.issubset(column_set))


def supports_hydro_only_dispatch_index(columns: list[str]) -> bool:
    return HYDRO_BASE_COLUMNS.issubset(set(columns))


def resolve_artifact_path(path_text: str, artifact_root: Path | str) -> Path:
    candidate = Path(path_text)
    if candidate.is_absolute():
        return candidate
    if candidate.is_file():
        return candidate
    joined = Path(artifact_root) / candidate
    if joined.is_file():
        return joined
    return candidate
