from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from app.persistence import AnalystStore


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
