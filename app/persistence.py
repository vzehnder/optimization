from __future__ import annotations

import os
import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def elapsed_seconds(started_at: str | None, finished_at: str) -> float | None:
    if not started_at:
        return None

    start = datetime.fromisoformat(started_at)
    finish = datetime.fromisoformat(finished_at)
    return max(0.0, (finish - start).total_seconds())


class AnalystStore:
    def __init__(self, database_url: str | None = None):
        self.database_url = database_url or os.environ.get("DATABASE_URL") or "sqlite:///.tmp/analyst_app.sqlite3"
        self.database_path = sqlite_path_from_url(self.database_url)
        if self.database_path != ":memory:":
            Path(self.database_path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self.connection = sqlite3.connect(self.database_path, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self._initialize_schema()

    def close(self) -> None:
        connection = getattr(self, "connection", None)
        if connection is not None:
            connection.close()
            self.connection = None

    def __del__(self) -> None:
        self.close()

    def _initialize_schema(self) -> None:
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                created_by TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS scenarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                created_by TEXT NOT NULL,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS scenario_versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scenario_id INTEGER NOT NULL,
                version_number INTEGER NOT NULL,
                system_case_json TEXT NOT NULL,
                case_name TEXT NOT NULL,
                schema_version TEXT NOT NULL,
                period_count INTEGER NOT NULL,
                asset_counts_json TEXT NOT NULL,
                validation_payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                created_by TEXT NOT NULL,
                FOREIGN KEY (scenario_id) REFERENCES scenarios(id) ON DELETE CASCADE,
                UNIQUE (scenario_id, version_number)
            );

            CREATE TRIGGER IF NOT EXISTS scenario_versions_immutable
            BEFORE UPDATE ON scenario_versions
            BEGIN
                SELECT RAISE(ABORT, 'scenario versions are immutable');
            END;

            CREATE TABLE IF NOT EXISTS runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scenario_version_id INTEGER NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                started_at TEXT,
                finished_at TEXT,
                duration_seconds REAL,
                exit_code INTEGER,
                workspace_path TEXT,
                input_snapshot_path TEXT,
                output_dir TEXT,
                summary_path TEXT,
                stdout_log_path TEXT,
                stderr_log_path TEXT,
                error_message TEXT NOT NULL DEFAULT '',
                success_payload_json TEXT NOT NULL DEFAULT '{}',
                error_payload_json TEXT NOT NULL DEFAULT '{}',
                stdout TEXT NOT NULL DEFAULT '',
                stderr TEXT NOT NULL DEFAULT '',
                triggered_by TEXT NOT NULL,
                trigger_type TEXT NOT NULL,
                FOREIGN KEY (scenario_version_id) REFERENCES scenario_versions(id) ON DELETE CASCADE,
                CHECK (status IN ('queued', 'running', 'succeeded', 'failed'))
            );
            """
        )
        self._ensure_column("runs", "stdout_log_path", "TEXT")
        self._ensure_column("runs", "stderr_log_path", "TEXT")
        self._ensure_column("runs", "error_message", "TEXT NOT NULL DEFAULT ''")
        self.connection.commit()

    def _ensure_column(self, table_name: str, column_name: str, definition: str) -> None:
        columns = {
            row["name"]
            for row in self.connection.execute(f"PRAGMA table_info({table_name})").fetchall()
        }
        if column_name not in columns:
            self.connection.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}")

    def create_project(self, *, name: str, description: str = "", created_by: str = "internal_analyst") -> dict[str, Any]:
        created_at = utc_now_iso()
        cursor = self.connection.execute(
            """
            INSERT INTO projects (name, description, created_at, created_by)
            VALUES (?, ?, ?, ?)
            """,
            (name, description, created_at, created_by),
        )
        self.connection.commit()
        return self.get_project(cursor.lastrowid)

    def list_projects(self) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            """
            SELECT id, name, description, created_at, created_by
            FROM projects
            ORDER BY id
            """
        ).fetchall()
        return [row_to_dict(row) for row in rows]

    def get_project(self, project_id: int) -> dict[str, Any]:
        row = self.connection.execute(
            """
            SELECT id, name, description, created_at, created_by
            FROM projects
            WHERE id = ?
            """,
            (project_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"project {project_id} not found")
        return row_to_dict(row)

    def create_scenario(
        self,
        *,
        project_id: int,
        name: str,
        description: str = "",
        created_by: str = "internal_analyst",
    ) -> dict[str, Any]:
        self.get_project(project_id)
        created_at = utc_now_iso()
        cursor = self.connection.execute(
            """
            INSERT INTO scenarios (project_id, name, description, created_at, created_by)
            VALUES (?, ?, ?, ?, ?)
            """,
            (project_id, name, description, created_at, created_by),
        )
        self.connection.commit()
        return self.get_scenario(cursor.lastrowid)

    def list_scenarios(self, project_id: int) -> list[dict[str, Any]]:
        self.get_project(project_id)
        rows = self.connection.execute(
            """
            SELECT id, project_id, name, description, created_at, created_by
            FROM scenarios
            WHERE project_id = ?
            ORDER BY id
            """,
            (project_id,),
        ).fetchall()
        return [row_to_dict(row) for row in rows]

    def get_scenario(self, scenario_id: int) -> dict[str, Any]:
        row = self.connection.execute(
            """
            SELECT id, project_id, name, description, created_at, created_by
            FROM scenarios
            WHERE id = ?
            """,
            (scenario_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"scenario {scenario_id} not found")
        return row_to_dict(row)

    def create_scenario_version(
        self,
        *,
        scenario_id: int,
        system_case_json: dict[str, Any],
        validation_payload: dict[str, Any],
        created_by: str = "internal_analyst",
    ) -> dict[str, Any]:
        self.get_scenario(scenario_id)
        metadata = extract_system_case_metadata(system_case_json)
        version_number = self._next_version_number(scenario_id)
        created_at = utc_now_iso()
        cursor = self.connection.execute(
            """
            INSERT INTO scenario_versions (
                scenario_id,
                version_number,
                system_case_json,
                case_name,
                schema_version,
                period_count,
                asset_counts_json,
                validation_payload_json,
                created_at,
                created_by
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                scenario_id,
                version_number,
                json.dumps(system_case_json, sort_keys=True),
                metadata["case_name"],
                metadata["schema_version"],
                metadata["period_count"],
                json.dumps(metadata["asset_counts"], sort_keys=True),
                json.dumps(validation_payload, sort_keys=True),
                created_at,
                created_by,
            ),
        )
        self.connection.commit()
        return self.get_scenario_version(cursor.lastrowid, include_document=False)

    def list_scenario_versions(self, scenario_id: int) -> list[dict[str, Any]]:
        self.get_scenario(scenario_id)
        rows = self.connection.execute(
            """
            SELECT
                id,
                scenario_id,
                version_number,
                case_name,
                schema_version,
                period_count,
                asset_counts_json,
                created_at,
                created_by
            FROM scenario_versions
            WHERE scenario_id = ?
            ORDER BY version_number
            """,
            (scenario_id,),
        ).fetchall()
        return [scenario_version_row_to_dict(row, include_document=False) for row in rows]

    def get_scenario_version(self, scenario_version_id: int, *, include_document: bool = True) -> dict[str, Any]:
        document_column = ", system_case_json, validation_payload_json" if include_document else ""
        row = self.connection.execute(
            f"""
            SELECT
                id,
                scenario_id,
                version_number,
                case_name,
                schema_version,
                period_count,
                asset_counts_json,
                created_at,
                created_by
                {document_column}
            FROM scenario_versions
            WHERE id = ?
            """,
            (scenario_version_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"scenario version {scenario_version_id} not found")
        return scenario_version_row_to_dict(row, include_document=include_document)

    def create_run(
        self,
        *,
        scenario_version_id: int,
        triggered_by: str = "internal_analyst",
        trigger_type: str = "manual",
    ) -> dict[str, Any]:
        with self._lock:
            self.get_scenario_version(scenario_version_id, include_document=False)
            created_at = utc_now_iso()
            cursor = self.connection.execute(
                """
                INSERT INTO runs (
                    scenario_version_id,
                    status,
                    created_at,
                    triggered_by,
                    trigger_type
                )
                VALUES (?, 'queued', ?, ?, ?)
                """,
                (scenario_version_id, created_at, triggered_by, trigger_type),
            )
            self.connection.commit()
            return self.get_run(cursor.lastrowid)

    def get_run(self, run_id: int) -> dict[str, Any]:
        with self._lock:
            row = self.connection.execute(
                """
                SELECT
                    id,
                    scenario_version_id,
                    status,
                    created_at,
                    started_at,
                    finished_at,
                    duration_seconds,
                    exit_code,
                    workspace_path,
                    input_snapshot_path,
                    output_dir,
                    summary_path,
                    stdout_log_path,
                    stderr_log_path,
                    error_message,
                    success_payload_json,
                    error_payload_json,
                    stdout,
                    stderr,
                    triggered_by,
                    trigger_type
                FROM runs
                WHERE id = ?
                """,
                (run_id,),
            ).fetchone()
            if row is None:
                raise KeyError(f"run {run_id} not found")
            return run_row_to_dict(row)

    def mark_run_running(
        self,
        run_id: int,
        *,
        workspace_path: str,
        input_snapshot_path: str,
    ) -> dict[str, Any]:
        with self._lock:
            started_at = utc_now_iso()
            cursor = self.connection.execute(
                """
                UPDATE runs
                SET
                    status = 'running',
                    started_at = ?,
                    workspace_path = ?,
                    input_snapshot_path = ?
                WHERE id = ?
                """,
                (started_at, workspace_path, input_snapshot_path, run_id),
            )
            if cursor.rowcount == 0:
                raise KeyError(f"run {run_id} not found")
            self.connection.commit()
            return self.get_run(run_id)

    def mark_run_succeeded(
        self,
        run_id: int,
        *,
        exit_code: int,
        stdout: str,
        stderr: str,
        success_payload: dict[str, Any],
        output_dir: str | None,
        summary_path: str | None,
        stdout_log_path: str | None = None,
        stderr_log_path: str | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            run = self.get_run(run_id)
            finished_at = utc_now_iso()
            duration_seconds = elapsed_seconds(run.get("started_at"), finished_at)
            self.connection.execute(
                """
                UPDATE runs
                SET
                    status = 'succeeded',
                    finished_at = ?,
                    duration_seconds = ?,
                    exit_code = ?,
                    stdout = ?,
                    stderr = ?,
                    success_payload_json = ?,
                    output_dir = ?,
                    summary_path = ?,
                    stdout_log_path = ?,
                    stderr_log_path = ?,
                    error_message = ''
                WHERE id = ?
                """,
                (
                    finished_at,
                    duration_seconds,
                    exit_code,
                    stdout,
                    stderr,
                    json.dumps(success_payload, sort_keys=True),
                    output_dir,
                    summary_path,
                    stdout_log_path,
                    stderr_log_path,
                    run_id,
                ),
            )
            self.connection.commit()
            return self.get_run(run_id)

    def mark_run_failed(
        self,
        run_id: int,
        *,
        exit_code: int | None,
        stdout: str,
        stderr: str,
        error_payload: dict[str, Any],
        error_message: str | None = None,
        stdout_log_path: str | None = None,
        stderr_log_path: str | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            run = self.get_run(run_id)
            finished_at = utc_now_iso()
            duration_seconds = elapsed_seconds(run.get("started_at"), finished_at)
            stored_error_message = error_message or str(error_payload.get("message") or "")
            self.connection.execute(
                """
                UPDATE runs
                SET
                    status = 'failed',
                    finished_at = ?,
                    duration_seconds = ?,
                    exit_code = ?,
                    stdout = ?,
                    stderr = ?,
                    error_payload_json = ?,
                    error_message = ?,
                    stdout_log_path = ?,
                    stderr_log_path = ?
                WHERE id = ?
                """,
                (
                    finished_at,
                    duration_seconds,
                    exit_code,
                    stdout,
                    stderr,
                    json.dumps(error_payload, sort_keys=True),
                    stored_error_message,
                    stdout_log_path,
                    stderr_log_path,
                    run_id,
                ),
            )
            self.connection.commit()
            return self.get_run(run_id)

    def _next_version_number(self, scenario_id: int) -> int:
        row = self.connection.execute(
            """
            SELECT COALESCE(MAX(version_number), 0) + 1 AS next_version_number
            FROM scenario_versions
            WHERE scenario_id = ?
            """,
            (scenario_id,),
        ).fetchone()
        return int(row["next_version_number"])


def sqlite_path_from_url(database_url: str) -> str:
    if database_url == "sqlite:///:memory:":
        return ":memory:"

    prefix = "sqlite:///"
    if not database_url.startswith(prefix):
        raise ValueError("Only sqlite:/// DATABASE_URL values are supported by the local app store")

    path_text = database_url[len(prefix) :]
    if not path_text:
        raise ValueError("sqlite DATABASE_URL must include a database path")

    return path_text


def row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {key: row[key] for key in row.keys()}


def extract_system_case_metadata(document: dict[str, Any]) -> dict[str, Any]:
    asset_counts = {"battery": 0, "grid": 0, "load": 0, "renewable": 0}
    for node in document.get("nodes", []):
        node_type = node.get("type") if isinstance(node, dict) else None
        if node_type in asset_counts:
            asset_counts[node_type] += 1

    return {
        "case_name": str(document.get("case_name") or "system_case"),
        "schema_version": str(document.get("schema_version") or ""),
        "period_count": len(document.get("time_series", [])),
        "asset_counts": asset_counts,
    }


def scenario_version_row_to_dict(row: sqlite3.Row, *, include_document: bool) -> dict[str, Any]:
    value = row_to_dict(row)
    value["asset_counts"] = json.loads(value.pop("asset_counts_json"))
    if include_document:
        value["system_case_json"] = json.loads(value.pop("system_case_json"))
        value["validation_payload"] = json.loads(value.pop("validation_payload_json"))
    return value


def run_row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    value = row_to_dict(row)
    value["success_payload"] = json.loads(value.pop("success_payload_json") or "{}")
    value["error_payload"] = json.loads(value.pop("error_payload_json") or "{}")
    return value
