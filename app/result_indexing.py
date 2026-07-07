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
            if not supports_core_dispatch_index(columns):
                return None
            rows = [dict(row) for row in reader]
    except OSError as error:
        raise ResultIndexingError(f"dispatch.csv could not be read: {error}") from error

    return store.replace_run_dispatch_result_index(
        run_id=int(run["id"]),
        scenario_version_id=int(run["scenario_version_id"]),
        columns=columns,
        rows=rows,
    )


def supports_core_dispatch_index(columns: list[str]) -> bool:
    column_set = set(columns)
    if not CORE_DISPATCH_BASE_COLUMNS.issubset(column_set):
        return False
    return bool(SINGLE_PRICE_COLUMNS.issubset(column_set) or SEPARATE_PRICE_COLUMNS.issubset(column_set))


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
