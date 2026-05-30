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
    }


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
