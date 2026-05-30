from __future__ import annotations

import json
import csv
from pathlib import Path
from typing import Any


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
    }


def build_chart_data(dispatch_table: dict[str, Any], asset_dispatch_table: dict[str, Any]) -> dict[str, Any]:
    return {
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
        "source_rows": {
            "dispatch": len(dispatch_table["rows"]),
            "asset_dispatch": len(asset_dispatch_table["rows"]),
        },
    }


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
                "source": "dispatch.csv",
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
