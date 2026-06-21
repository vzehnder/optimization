from __future__ import annotations

import json
import csv
from pathlib import Path
from typing import Any


TEMPLATE_CHART_GROUPS = [
    ("show_price_chart", ["price"]),
    ("show_grid_chart", ["grid_import_export"]),
    ("show_renewable_chart", ["renewable_used_curtailed"]),
    ("show_bess_chart", ["bess_charge_discharge_soc"]),
    ("show_profit_chart", ["period_profit"]),
    ("show_hydro_chart", ["hydro_power", "hydro_flows", "hydro_storage", "hydro_reservoir_elevation"]),
]


class ResultReadError(ValueError):
    def __init__(self, message: str, *, status_code: int = 422):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def read_run_results(run: dict[str, Any], artifacts: list[dict[str, Any]], artifact_root: Path | str) -> dict[str, Any]:
    if run["status"] != "succeeded":
        raise ResultReadError("run results are available only for succeeded runs", status_code=409)

    artifacts_by_type = {artifact["artifact_type"]: artifact for artifact in artifacts}
    summary = read_json_artifact(
        artifacts_by_type,
        "summary_json",
        artifact_root,
        display_name="summary.json",
    )
    dispatch_table = read_csv_artifact(
        artifacts_by_type,
        "dispatch_csv",
        artifact_root,
        display_name="dispatch.csv",
    )
    asset_dispatch_table = read_csv_artifact(
        artifacts_by_type,
        "asset_dispatch_csv",
        artifact_root,
        display_name="asset_dispatch.csv",
    )
    return {
        "summary": summary,
        "dispatch_table": dispatch_table,
        "asset_dispatch_table": asset_dispatch_table,
        "charts": build_chart_data(dispatch_table, asset_dispatch_table),
        "plot_series": build_plot_series_catalog(dispatch_table, asset_dispatch_table),
    }


def apply_dashboard_template(results: dict[str, Any], template: dict[str, Any]) -> dict[str, Any]:
    charts: dict[str, Any] = {}
    source_charts = results.get("charts", {})
    for flag, chart_keys in TEMPLATE_CHART_GROUPS:
        if not template.get(flag, False):
            continue
        for chart_key in chart_keys:
            chart = source_charts.get(chart_key)
            if chart is not None:
                charts[chart_key] = chart

    if charts and "all_series" in source_charts:
        charts = {"all_series": source_charts["all_series"], **charts}

    preview_limit = int(template["table_preview_limit"])
    return {
        "summary": results["summary"] if template.get("show_summary", False) else None,
        "charts": charts,
        "plot_series": results.get("plot_series", []) if charts else [],
        "dispatch_table": limit_result_table(results["dispatch_table"], preview_limit)
        if template.get("show_system_dispatch_table", False)
        else None,
        "asset_dispatch_table": limit_result_table(results["asset_dispatch_table"], preview_limit)
        if template.get("show_asset_dispatch_table", False)
        else None,
    }


def limit_result_table(table: dict[str, Any], row_limit: int) -> dict[str, Any]:
    return {
        "columns": list(table["columns"]),
        "rows": [dict(row) for row in table["rows"][:row_limit]],
    }


def build_chart_data(dispatch_table: dict[str, Any], asset_dispatch_table: dict[str, Any]) -> dict[str, Any]:
    return {
        "all_series": build_all_series_chart(dispatch_table),
        "price": build_price_chart(dispatch_table),
        "grid_import_export": build_line_chart(
            "grid-import-export",
            "Grid Import / Export",
            dispatch_table,
            [
                ("grid_import_mw", "Grid Import MW", "MW"),
                ("grid_export_mw", "Grid Export MW", "MW"),
            ],
        ),
        "renewable_used_curtailed": build_line_chart(
            "renewable-used-curtailed",
            "Renewable Used / Curtailed",
            dispatch_table,
            [
                ("renewable_used_mw", "Renewable Used MW", "MW"),
                ("renewable_curtailed_mw", "Renewable Curtailed MW", "MW"),
            ],
        ),
        "bess_charge_discharge_soc": build_line_chart(
            "bess-charge-discharge-soc",
            "BESS Charge / Discharge / SOC",
            dispatch_table,
            [
                ("battery_charge_mw", "BESS Charge MW", "MW"),
                ("battery_discharge_mw", "BESS Discharge MW", "MW"),
                ("battery_energy_mwh", "BESS SOC MWh", "MWh"),
            ],
        ),
        "period_profit": build_line_chart(
            "period-profit",
            "Period Profit",
            dispatch_table,
            [("period_profit_usd", "Period Profit USD", "USD")],
        ),
        "hydro_power": build_line_chart(
            "hydro-power",
            "Hydro Power",
            dispatch_table,
            [("total_hydro_power_mw", "Hydro Power MW", "MW")],
        ),
        "hydro_flows": build_line_chart(
            "hydro-flows",
            "Hydro Flows",
            dispatch_table,
            [
                ("total_hydro_inflow_m3s", "Hydro Inflow m3/s", "m3/s"),
                ("total_hydro_turbine_flow_m3s", "Hydro Turbine Flow m3/s", "m3/s"),
                ("total_hydro_spill_flow_m3s", "Hydro Spill Flow m3/s", "m3/s"),
            ],
        ),
        "hydro_storage": build_line_chart(
            "hydro-storage",
            "Hydro Storage",
            dispatch_table,
            [("total_hydro_storage_hm3", "Hydro Storage hm3", "hm3")],
        ),
        "hydro_reservoir_elevation": build_line_chart(
            "hydro-reservoir-elevation",
            "Hydro Reservoir Elevation",
            asset_dispatch_table,
            [("hydro_reservoir_elevation_masl", "Hydro Reservoir Elevation masl", "masl")],
            source="asset_dispatch.csv",
        ),
        "source_rows": {
            "dispatch": len(dispatch_table["rows"]),
            "asset_dispatch": len(asset_dispatch_table["rows"]),
        },
    }


def build_all_series_chart(dispatch_table: dict[str, Any]) -> dict[str, Any]:
    if "timestamp" not in dispatch_table["columns"]:
        return {
            "id": "all-system-series",
            "title": "All System Series",
            "available": False,
            "labels": [],
            "series": [],
            "missing_columns": ["timestamp"],
            "message": "Missing columns: timestamp",
        }

    rows = dispatch_table["rows"]
    series = []
    for column in dispatch_table["columns"]:
        if column == "timestamp":
            continue
        values = [parse_chart_value(row.get(column)) for row in rows]
        if not any(value is not None for value in values):
            continue
        series.append(
            {
                "key": column,
                "label": column,
                "unit": chart_series_unit(column),
                "values": values,
            }
        )

    return {
        "id": "all-system-series",
        "title": "All System Series",
        "available": bool(series),
        "labels": [str(row.get("timestamp") or "") for row in rows],
        "series": series,
        "missing_columns": [],
        "message": "" if series else "No numeric series are available in dispatch.csv",
    }


def chart_series_unit(column: str) -> str:
    for suffix, unit in [
        ("_usd_per_mwh", "USD/MWh"),
        ("_mwh", "MWh"),
        ("_mw", "MW"),
        ("_m3s", "m3/s"),
        ("_hm3", "hm3"),
        ("_masl", "masl"),
        ("_usd", "USD"),
        ("_hours", "hours"),
    ]:
        if column.endswith(suffix):
            return unit
    return ""


def build_plot_series_catalog(
    dispatch_table: dict[str, Any],
    asset_dispatch_table: dict[str, Any],
) -> list[dict[str, Any]]:
    catalog = build_system_plot_series(dispatch_table)
    catalog.extend(build_asset_plot_series(asset_dispatch_table))
    return catalog


def build_system_plot_series(table: dict[str, Any]) -> list[dict[str, Any]]:
    labels = [str(row.get("timestamp") or "") for row in table["rows"]]
    series = []
    for column in table["columns"]:
        if column == "timestamp":
            continue
        values = [parse_chart_value(row.get(column)) for row in table["rows"]]
        if not any(value is not None for value in values):
            continue
        series.append(
            {
                "id": f"system:{column}",
                "label": f"System · {column}",
                "source": "system",
                "source_label": "System dispatch",
                "column": column,
                "unit": chart_series_unit(column),
                "labels": labels,
                "values": values,
            }
        )
    return series


def build_asset_plot_series(table: dict[str, Any]) -> list[dict[str, Any]]:
    rows_by_asset: dict[str, list[dict[str, Any]]] = {}
    asset_types: dict[str, str] = {}
    for row in table["rows"]:
        asset_id = str(row.get("asset_id") or "").strip()
        if not asset_id:
            continue
        rows_by_asset.setdefault(asset_id, []).append(row)
        asset_types.setdefault(asset_id, str(row.get("asset_type") or "asset").strip() or "asset")

    excluded_columns = {
        "timestamp",
        "duration_hours",
        "price_usd_per_mwh",
        "import_price_usd_per_mwh",
        "export_price_usd_per_mwh",
        "asset_id",
        "asset_type",
    }
    catalog = []
    for asset_id, rows in rows_by_asset.items():
        asset_type = asset_types[asset_id]
        labels = [str(row.get("timestamp") or "") for row in rows]
        for column in table["columns"]:
            if column in excluded_columns:
                continue
            values = [parse_chart_value(row.get(column)) for row in rows]
            if not any(value is not None for value in values):
                continue
            if not asset_column_is_relevant(asset_type, column, values):
                continue
            catalog.append(
                {
                    "id": f"asset:{asset_id}:{column}",
                    "label": f"{asset_id} ({asset_type}) · {column}",
                    "source": "asset",
                    "source_label": f"Asset · {asset_id} ({asset_type})",
                    "asset_id": asset_id,
                    "asset_type": asset_type,
                    "column": column,
                    "unit": chart_series_unit(column),
                    "labels": labels,
                    "values": values,
                }
            )
    return catalog


def asset_column_is_relevant(asset_type: str, column: str, values: list[float | None]) -> bool:
    normalized_type = asset_type.lower()
    relevant = {
        "grid": column.startswith("grid_"),
        "renewable": column.startswith("renewable_"),
        "load": column.startswith("load_"),
        "battery": column.startswith("battery_"),
        "bess": column.startswith("battery_"),
        "hydro": column.startswith("hydro_"),
    }.get(normalized_type)
    if relevant is not None:
        return relevant or any(value not in (None, 0.0) for value in values)
    return True


def build_price_chart(dispatch_table: dict[str, Any]) -> dict[str, Any]:
    columns = dispatch_table["columns"]
    if "import_price_usd_per_mwh" in columns and "export_price_usd_per_mwh" in columns:
        return build_line_chart(
            "price",
            "Energy Price",
            dispatch_table,
            [
                ("import_price_usd_per_mwh", "Import Price USD/MWh", "USD/MWh"),
                ("export_price_usd_per_mwh", "Export Price USD/MWh", "USD/MWh"),
            ],
        )

    return build_line_chart(
        "price",
        "Energy Price",
        dispatch_table,
        [("price_usd_per_mwh", "Price USD/MWh", "USD/MWh")],
    )


def build_line_chart(
    chart_id: str,
    title: str,
    table: dict[str, Any],
    series_columns: list[tuple[str, str, str]],
    *,
    source: str = "dispatch.csv",
) -> dict[str, Any]:
    required_columns = ["timestamp"] + [column for column, _, _ in series_columns]
    missing_columns = [column for column in required_columns if column not in table["columns"]]
    if missing_columns:
        return {
            "id": chart_id,
            "title": title,
            "available": False,
            "labels": [],
            "series": [],
            "missing_columns": missing_columns,
            "message": f"Missing columns: {', '.join(missing_columns)}",
        }

    rows = table["rows"]
    return {
        "id": chart_id,
        "title": title,
        "available": True,
        "labels": [str(row.get("timestamp") or "") for row in rows],
        "series": [
            {
                "key": column,
                "label": label,
                "unit": unit,
                "source": source,
                "values": [parse_chart_value(row.get(column)) for row in rows],
            }
            for column, label, unit in series_columns
        ],
        "missing_columns": [],
        "message": "",
    }


def parse_chart_value(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def read_json_artifact(
    artifacts_by_type: dict[str, dict[str, Any]],
    artifact_type: str,
    artifact_root: Path | str,
    *,
    display_name: str,
) -> dict[str, Any]:
    artifact_path = result_artifact_path(artifacts_by_type, artifact_type, artifact_root, display_name=display_name)
    try:
        parsed = json.loads(artifact_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ResultReadError(
            f"{display_name} is malformed JSON: {error.msg} at line {error.lineno}, column {error.colno}"
        ) from error

    if not isinstance(parsed, dict):
        raise ResultReadError(f"{display_name} must contain a JSON object")
    return parsed


def read_csv_artifact(
    artifacts_by_type: dict[str, dict[str, Any]],
    artifact_type: str,
    artifact_root: Path | str,
    *,
    display_name: str,
) -> dict[str, Any]:
    artifact_path = result_artifact_path(artifacts_by_type, artifact_type, artifact_root, display_name=display_name)
    try:
        with artifact_path.open(newline="", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            if not reader.fieldnames:
                raise ResultReadError(f"{display_name} has no header row")
            return {
                "columns": list(reader.fieldnames),
                "rows": [dict(row) for row in reader],
            }
    except csv.Error as error:
        raise ResultReadError(f"{display_name} is malformed CSV: {error}") from error


def result_artifact_path(
    artifacts_by_type: dict[str, dict[str, Any]],
    artifact_type: str,
    artifact_root: Path | str,
    *,
    display_name: str,
) -> Path:
    artifact = artifacts_by_type.get(artifact_type)
    if artifact is None:
        raise ResultReadError(f"{display_name} artifact is not registered", status_code=404)

    path = Path(artifact["path"])
    if not path_is_under(path, Path(artifact_root)):
        raise ResultReadError(f"{display_name} artifact is not available", status_code=404)
    if not path.is_file():
        raise ResultReadError(f"{display_name} artifact file not found", status_code=404)
    return path


def path_is_under(path: Path, root: Path) -> bool:
    resolved_root = root.resolve(strict=False)
    resolved_path = path.resolve(strict=False)
    try:
        resolved_path.relative_to(resolved_root)
    except ValueError:
        return False
    return True
