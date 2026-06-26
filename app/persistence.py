from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from app.auth import VALID_USER_ROLES
from app.database import connect_database, database_url_from_env, postgres_schema_from_sqlite


DASHBOARD_TEMPLATE_FLAGS = [
    "show_summary",
    "show_price_chart",
    "show_grid_chart",
    "show_renewable_chart",
    "show_bess_chart",
    "show_hydro_chart",
    "show_profit_chart",
    "show_system_dispatch_table",
    "show_asset_dispatch_table",
]

DEFAULT_TABLE_PREVIEW_LIMIT = 10

DEFAULT_PUBLICATION_ARTIFACT_TYPES = [
    "summary_json",
    "dispatch_csv",
    "asset_dispatch_csv",
]

HYDRAULIC_NODE_COMPONENT_TYPES = {"reservoir", "junction"}
HYDRAULIC_VISIBLE_COMPONENT_TYPES = HYDRAULIC_NODE_COMPONENT_TYPES | {"plant"}
HYDRAULIC_REACH_TYPES = {
    "river",
    "canal",
    "tunnel",
    "gate",
    "spillway",
    "bypass",
    "tailrace",
    "other",
}


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
        self.database_url = database_url or database_url_from_env()
        self._lock = threading.RLock()
        self.database_backend, self.database_path, self.connection = connect_database(self.database_url)
        self._initialize_schema()

    def close(self) -> None:
        connection = getattr(self, "connection", None)
        if connection is not None:
            connection.close()
            self.connection = None

    def __del__(self) -> None:
        self.close()

    def _initialize_schema(self) -> None:
        schema = """
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

            CREATE TABLE IF NOT EXISTS optimization_cases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scenario_id INTEGER NOT NULL UNIQUE,
                case_key TEXT NOT NULL,
                display_name TEXT NOT NULL,
                validation_payload_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                created_by TEXT NOT NULL,
                updated_by TEXT NOT NULL,
                FOREIGN KEY (scenario_id) REFERENCES scenarios(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS hydraulic_systems (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                system_key TEXT NOT NULL,
                display_name TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                created_by TEXT NOT NULL,
                updated_by TEXT NOT NULL,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
                UNIQUE (project_id, system_key)
            );

            CREATE TABLE IF NOT EXISTS hydraulic_nodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                hydraulic_system_id INTEGER NOT NULL,
                node_key TEXT NOT NULL,
                display_name TEXT NOT NULL,
                node_type TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                created_by TEXT NOT NULL,
                updated_by TEXT NOT NULL,
                FOREIGN KEY (hydraulic_system_id) REFERENCES hydraulic_systems(id) ON DELETE CASCADE,
                UNIQUE (hydraulic_system_id, node_key),
                CHECK (node_type IN ('reservoir', 'junction', 'intake', 'tailrace', 'river_inflow', 'other'))
            );

            CREATE TABLE IF NOT EXISTS hydraulic_reaches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                hydraulic_system_id INTEGER NOT NULL,
                reach_key TEXT NOT NULL,
                display_name TEXT NOT NULL,
                from_node_id INTEGER NOT NULL,
                to_node_id INTEGER NOT NULL,
                reach_type TEXT NOT NULL,
                travel_time_hours REAL NOT NULL DEFAULT 0,
                routing_method TEXT NOT NULL DEFAULT 'none',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                created_by TEXT NOT NULL,
                updated_by TEXT NOT NULL,
                FOREIGN KEY (hydraulic_system_id) REFERENCES hydraulic_systems(id) ON DELETE CASCADE,
                FOREIGN KEY (from_node_id) REFERENCES hydraulic_nodes(id) ON DELETE CASCADE,
                FOREIGN KEY (to_node_id) REFERENCES hydraulic_nodes(id) ON DELETE CASCADE,
                UNIQUE (hydraulic_system_id, reach_key),
                CHECK (reach_type IN ('river', 'canal', 'tunnel', 'gate', 'spillway', 'bypass', 'tailrace', 'other'))
            );

            CREATE TABLE IF NOT EXISTS hydraulic_plants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                hydraulic_system_id INTEGER NOT NULL,
                plant_key TEXT NOT NULL,
                display_name TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                created_by TEXT NOT NULL,
                updated_by TEXT NOT NULL,
                FOREIGN KEY (hydraulic_system_id) REFERENCES hydraulic_systems(id) ON DELETE CASCADE,
                UNIQUE (hydraulic_system_id, plant_key)
            );

            CREATE TABLE IF NOT EXISTS case_hydraulic_systems (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id INTEGER NOT NULL,
                hydraulic_system_id INTEGER NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                created_by TEXT NOT NULL,
                updated_by TEXT NOT NULL,
                FOREIGN KEY (case_id) REFERENCES optimization_cases(id) ON DELETE CASCADE,
                FOREIGN KEY (hydraulic_system_id) REFERENCES hydraulic_systems(id) ON DELETE CASCADE,
                UNIQUE (case_id, hydraulic_system_id)
            );

            CREATE TABLE IF NOT EXISTS case_hydraulic_nodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id INTEGER NOT NULL,
                hydraulic_node_id INTEGER NOT NULL,
                case_label TEXT NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                created_by TEXT NOT NULL,
                updated_by TEXT NOT NULL,
                FOREIGN KEY (case_id) REFERENCES optimization_cases(id) ON DELETE CASCADE,
                FOREIGN KEY (hydraulic_node_id) REFERENCES hydraulic_nodes(id) ON DELETE CASCADE,
                UNIQUE (case_id, hydraulic_node_id)
            );

            CREATE TABLE IF NOT EXISTS case_hydraulic_reaches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id INTEGER NOT NULL,
                hydraulic_reach_id INTEGER NOT NULL,
                case_label TEXT NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1,
                flow_min_m3s REAL,
                spill_penalty_usd_per_hm3 REAL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                created_by TEXT NOT NULL,
                updated_by TEXT NOT NULL,
                FOREIGN KEY (case_id) REFERENCES optimization_cases(id) ON DELETE CASCADE,
                FOREIGN KEY (hydraulic_reach_id) REFERENCES hydraulic_reaches(id) ON DELETE CASCADE,
                UNIQUE (case_id, hydraulic_reach_id)
            );

            CREATE TABLE IF NOT EXISTS case_hydraulic_plants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id INTEGER NOT NULL,
                hydraulic_plant_id INTEGER NOT NULL,
                case_label TEXT NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                created_by TEXT NOT NULL,
                updated_by TEXT NOT NULL,
                FOREIGN KEY (case_id) REFERENCES optimization_cases(id) ON DELETE CASCADE,
                FOREIGN KEY (hydraulic_plant_id) REFERENCES hydraulic_plants(id) ON DELETE CASCADE,
                UNIQUE (case_id, hydraulic_plant_id)
            );

            CREATE TABLE IF NOT EXISTS case_hydraulic_diagram_layouts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id INTEGER NOT NULL,
                layout_key TEXT NOT NULL,
                viewport_x REAL NOT NULL DEFAULT 0,
                viewport_y REAL NOT NULL DEFAULT 0,
                zoom REAL NOT NULL DEFAULT 1,
                layout_engine TEXT,
                layout_version INTEGER NOT NULL DEFAULT 1,
                content_hash TEXT,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                updated_by TEXT NOT NULL,
                FOREIGN KEY (case_id) REFERENCES optimization_cases(id) ON DELETE CASCADE,
                UNIQUE (case_id, layout_key),
                CHECK (zoom > 0)
            );

            CREATE TABLE IF NOT EXISTS case_hydraulic_diagram_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                diagram_layout_id INTEGER NOT NULL,
                entity_type TEXT NOT NULL,
                entity_id INTEGER NOT NULL,
                x REAL NOT NULL,
                y REAL NOT NULL,
                width REAL,
                height REAL,
                z_index INTEGER NOT NULL DEFAULT 0,
                collapsed INTEGER NOT NULL DEFAULT 0,
                style_json TEXT NOT NULL DEFAULT '{}',
                metadata_json TEXT NOT NULL DEFAULT '{}',
                updated_at TEXT NOT NULL,
                FOREIGN KEY (diagram_layout_id) REFERENCES case_hydraulic_diagram_layouts(id) ON DELETE CASCADE,
                UNIQUE (diagram_layout_id, entity_type, entity_id),
                CHECK (entity_type IN ('case_hydraulic_node', 'case_hydraulic_reach', 'case_hydraulic_plant'))
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
                generation_metadata_json TEXT NOT NULL DEFAULT '{}',
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

            CREATE TABLE IF NOT EXISTS scenario_drafts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scenario_id INTEGER NOT NULL UNIQUE,
                source_version_id INTEGER,
                document_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                created_by TEXT NOT NULL,
                updated_by TEXT NOT NULL,
                FOREIGN KEY (scenario_id) REFERENCES scenarios(id) ON DELETE CASCADE,
                FOREIGN KEY (source_version_id) REFERENCES scenario_versions(id) ON DELETE SET NULL
            );

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

            CREATE TABLE IF NOT EXISTS run_artifacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER NOT NULL,
                artifact_type TEXT NOT NULL,
                path TEXT NOT NULL,
                display_name TEXT NOT NULL,
                media_type TEXT NOT NULL,
                byte_size INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (run_id) REFERENCES runs(id) ON DELETE CASCADE,
                UNIQUE (run_id, artifact_type)
            );

            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                display_name TEXT NOT NULL DEFAULT '',
                role TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                created_by TEXT NOT NULL,
                deactivated_at TEXT,
                CHECK (role IN ('admin', 'analyst', 'client'))
            );

            CREATE TABLE IF NOT EXISTS auth_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                token_hash TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                revoked_at TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS project_client_access (
                project_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                assigned_at TEXT NOT NULL,
                assigned_by TEXT NOT NULL,
                PRIMARY KEY (project_id, user_id),
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS dashboard_templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                show_summary INTEGER NOT NULL DEFAULT 1,
                show_price_chart INTEGER NOT NULL DEFAULT 1,
                show_grid_chart INTEGER NOT NULL DEFAULT 1,
                show_renewable_chart INTEGER NOT NULL DEFAULT 1,
                show_bess_chart INTEGER NOT NULL DEFAULT 1,
                show_hydro_chart INTEGER NOT NULL DEFAULT 1,
                show_profit_chart INTEGER NOT NULL DEFAULT 1,
                show_system_dispatch_table INTEGER NOT NULL DEFAULT 1,
                show_asset_dispatch_table INTEGER NOT NULL DEFAULT 1,
                table_preview_limit INTEGER NOT NULL DEFAULT 10,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                created_by TEXT NOT NULL,
                updated_by TEXT NOT NULL,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
                CHECK (table_preview_limit >= 1)
            );

            CREATE TABLE IF NOT EXISTS publications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                scenario_id INTEGER NOT NULL,
                scenario_version_id INTEGER NOT NULL,
                run_id INTEGER NOT NULL,
                dashboard_template_id INTEGER NOT NULL,
                public_title TEXT NOT NULL,
                analyst_notes TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'draft',
                allowed_artifact_types_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                published_at TEXT,
                unpublished_at TEXT,
                created_by TEXT NOT NULL,
                updated_by TEXT NOT NULL,
                published_by TEXT,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
                FOREIGN KEY (scenario_id) REFERENCES scenarios(id) ON DELETE CASCADE,
                FOREIGN KEY (scenario_version_id) REFERENCES scenario_versions(id) ON DELETE CASCADE,
                FOREIGN KEY (run_id) REFERENCES runs(id) ON DELETE CASCADE,
                FOREIGN KEY (dashboard_template_id) REFERENCES dashboard_templates(id),
                CHECK (status IN ('draft', 'published', 'unpublished'))
            );
            """
        if self.database_backend == "postgresql":
            schema = postgres_schema_from_sqlite(schema)
        self.connection.executescript(schema)
        self._ensure_column("runs", "stdout_log_path", "TEXT")
        self._ensure_column("runs", "stderr_log_path", "TEXT")
        self._ensure_column("runs", "error_message", "TEXT NOT NULL DEFAULT ''")
        self._ensure_column("scenario_versions", "generation_metadata_json", "TEXT NOT NULL DEFAULT '{}'")
        self._ensure_hydraulic_diagram_items_support_reaches()
        self.connection.commit()

    def _ensure_column(self, table_name: str, column_name: str, definition: str) -> None:
        if self.database_backend == "postgresql":
            row = self.connection.execute(
                """
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = current_schema()
                  AND table_name = ?
                  AND column_name = ?
                """,
                (table_name, column_name),
            ).fetchone()
            if row is None:
                self.connection.execute(
                    f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}"
                )
            return

        columns = {
            row["name"]
            for row in self.connection.execute(f"PRAGMA table_info({table_name})").fetchall()
        }
        if column_name not in columns:
            self.connection.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}")

    def _ensure_hydraulic_diagram_items_support_reaches(self) -> None:
        if self.database_backend != "sqlite":
            return
        row = self.connection.execute(
            """
            SELECT sql
            FROM sqlite_master
            WHERE type = 'table' AND name = 'case_hydraulic_diagram_items'
            """
        ).fetchone()
        if row is None or "case_hydraulic_reach" in str(row["sql"]):
            return
        self.connection.execute("PRAGMA foreign_keys = OFF")
        self.connection.executescript(
            """
            ALTER TABLE case_hydraulic_diagram_items
            RENAME TO case_hydraulic_diagram_items_old;

            CREATE TABLE case_hydraulic_diagram_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                diagram_layout_id INTEGER NOT NULL,
                entity_type TEXT NOT NULL,
                entity_id INTEGER NOT NULL,
                x REAL NOT NULL,
                y REAL NOT NULL,
                width REAL,
                height REAL,
                z_index INTEGER NOT NULL DEFAULT 0,
                collapsed INTEGER NOT NULL DEFAULT 0,
                style_json TEXT NOT NULL DEFAULT '{}',
                metadata_json TEXT NOT NULL DEFAULT '{}',
                updated_at TEXT NOT NULL,
                FOREIGN KEY (diagram_layout_id) REFERENCES case_hydraulic_diagram_layouts(id) ON DELETE CASCADE,
                UNIQUE (diagram_layout_id, entity_type, entity_id),
                CHECK (entity_type IN ('case_hydraulic_node', 'case_hydraulic_reach', 'case_hydraulic_plant'))
            );

            INSERT INTO case_hydraulic_diagram_items (
                id,
                diagram_layout_id,
                entity_type,
                entity_id,
                x,
                y,
                width,
                height,
                z_index,
                collapsed,
                style_json,
                metadata_json,
                updated_at
            )
            SELECT
                id,
                diagram_layout_id,
                entity_type,
                entity_id,
                x,
                y,
                width,
                height,
                z_index,
                collapsed,
                style_json,
                metadata_json,
                updated_at
            FROM case_hydraulic_diagram_items_old;

            DROP TABLE case_hydraulic_diagram_items_old;
            """
        )
        self.connection.execute("PRAGMA foreign_keys = ON")

    def count_users(self) -> int:
        row = self.connection.execute("SELECT COUNT(*) AS user_count FROM users").fetchone()
        return int(row["user_count"])

    def create_user(
        self,
        *,
        email: str,
        password_hash: str,
        role: str,
        display_name: str = "",
        is_active: bool = True,
        created_by: str = "system",
    ) -> dict[str, Any]:
        normalized_email = email.strip().lower()
        if not normalized_email:
            raise ValueError("email is required")
        if role not in VALID_USER_ROLES:
            raise ValueError(f"unsupported user role: {role}")
        now = utc_now_iso()
        with self._lock:
            cursor = self.connection.execute(
                """
                INSERT INTO users (
                    email,
                    display_name,
                    role,
                    password_hash,
                    is_active,
                    created_at,
                    updated_at,
                    created_by,
                    deactivated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    normalized_email,
                    display_name.strip(),
                    role,
                    password_hash,
                    1 if is_active else 0,
                    now,
                    now,
                    created_by,
                    None if is_active else now,
                ),
            )
            self.connection.commit()
            return self.get_user(cursor.lastrowid)

    def list_users(self) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            """
            SELECT id, email, display_name, role, password_hash, is_active,
                   created_at, updated_at, created_by, deactivated_at
            FROM users
            ORDER BY id
            """
        ).fetchall()
        return [user_row_to_dict(row) for row in rows]

    def get_user(self, user_id: int) -> dict[str, Any]:
        row = self.connection.execute(
            """
            SELECT id, email, display_name, role, password_hash, is_active,
                   created_at, updated_at, created_by, deactivated_at
            FROM users
            WHERE id = ?
            """,
            (user_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"user {user_id} not found")
        return user_row_to_dict(row)

    def get_user_by_email(self, email: str) -> dict[str, Any]:
        row = self.connection.execute(
            """
            SELECT id, email, display_name, role, password_hash, is_active,
                   created_at, updated_at, created_by, deactivated_at
            FROM users
            WHERE email = ?
            """,
            (email.strip().lower(),),
        ).fetchone()
        if row is None:
            raise KeyError(f"user {email} not found")
        return user_row_to_dict(row)

    def set_user_active(self, user_id: int, is_active: bool, *, updated_by: str = "system") -> dict[str, Any]:
        now = utc_now_iso()
        with self._lock:
            cursor = self.connection.execute(
                """
                UPDATE users
                SET is_active = ?,
                    updated_at = ?,
                    deactivated_at = ?
                WHERE id = ?
                """,
                (1 if is_active else 0, now, None if is_active else now, user_id),
            )
            if cursor.rowcount == 0:
                raise KeyError(f"user {user_id} not found")
            self.connection.commit()
            return self.get_user(user_id)

    def create_auth_session(self, *, user_id: int, token_hash: str, expires_at: str) -> dict[str, Any]:
        self.get_user(user_id)
        now = utc_now_iso()
        with self._lock:
            cursor = self.connection.execute(
                """
                INSERT INTO auth_sessions (user_id, token_hash, created_at, expires_at, revoked_at)
                VALUES (?, ?, ?, ?, NULL)
                """,
                (user_id, token_hash, now, expires_at),
            )
            self.connection.commit()
            return row_to_dict(
                self.connection.execute(
                    """
                    SELECT id, user_id, token_hash, created_at, expires_at, revoked_at
                    FROM auth_sessions
                    WHERE id = ?
                    """,
                    (cursor.lastrowid,),
                ).fetchone()
            )

    def get_user_for_session(self, token_hash: str, *, now: str | None = None) -> dict[str, Any] | None:
        current_time = now or utc_now_iso()
        row = self.connection.execute(
            """
            SELECT
                users.id,
                users.email,
                users.display_name,
                users.role,
                users.password_hash,
                users.is_active,
                users.created_at,
                users.updated_at,
                users.created_by,
                users.deactivated_at
            FROM auth_sessions
            JOIN users ON users.id = auth_sessions.user_id
            WHERE auth_sessions.token_hash = ?
              AND auth_sessions.revoked_at IS NULL
              AND auth_sessions.expires_at > ?
              AND users.is_active = 1
            """,
            (token_hash, current_time),
        ).fetchone()
        if row is None:
            return None
        return user_row_to_dict(row)

    def revoke_auth_session(self, token_hash: str) -> None:
        with self._lock:
            self.connection.execute(
                """
                UPDATE auth_sessions
                SET revoked_at = ?
                WHERE token_hash = ? AND revoked_at IS NULL
                """,
                (utc_now_iso(), token_hash),
            )
            self.connection.commit()

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

    def assign_client_to_project(
        self,
        *,
        project_id: int,
        user_id: int,
        assigned_by: str = "system",
    ) -> dict[str, Any]:
        self.get_project(project_id)
        user = self.get_user(user_id)
        if user["role"] != "client":
            raise ValueError("project access can only be assigned to client users")
        now = utc_now_iso()
        with self._lock:
            self.connection.execute(
                """
                INSERT OR IGNORE INTO project_client_access (
                    project_id,
                    user_id,
                    assigned_at,
                    assigned_by
                )
                VALUES (?, ?, ?, ?)
                """,
                (project_id, user_id, now, assigned_by),
            )
            self.connection.commit()
        return self.get_project_client_access(project_id, user_id)

    def get_project_client_access(self, project_id: int, user_id: int) -> dict[str, Any]:
        row = self.connection.execute(
            """
            SELECT project_client_access.project_id,
                   project_client_access.user_id,
                   project_client_access.assigned_at,
                   project_client_access.assigned_by,
                   users.email,
                   users.display_name,
                   users.role,
                   users.is_active
            FROM project_client_access
            JOIN users ON users.id = project_client_access.user_id
            WHERE project_client_access.project_id = ?
              AND project_client_access.user_id = ?
            """,
            (project_id, user_id),
        ).fetchone()
        if row is None:
            raise KeyError(f"client {user_id} is not assigned to project {project_id}")
        value = row_to_dict(row)
        value["is_active"] = bool(value["is_active"])
        return value

    def list_project_client_access(self, project_id: int) -> list[dict[str, Any]]:
        self.get_project(project_id)
        rows = self.connection.execute(
            """
            SELECT project_client_access.project_id,
                   project_client_access.user_id,
                   project_client_access.assigned_at,
                   project_client_access.assigned_by,
                   users.email,
                   users.display_name,
                   users.role,
                   users.is_active
            FROM project_client_access
            JOIN users ON users.id = project_client_access.user_id
            WHERE project_client_access.project_id = ?
            ORDER BY users.email
            """,
            (project_id,),
        ).fetchall()
        values = [row_to_dict(row) for row in rows]
        for value in values:
            value["is_active"] = bool(value["is_active"])
        return values

    def list_client_projects(self, user_id: int) -> list[dict[str, Any]]:
        user = self.get_user(user_id)
        if user["role"] != "client" or not user["is_active"]:
            return []
        rows = self.connection.execute(
            """
            SELECT projects.id, projects.name, projects.description, projects.created_at, projects.created_by
            FROM project_client_access
            JOIN projects ON projects.id = project_client_access.project_id
            WHERE project_client_access.user_id = ?
            ORDER BY projects.id
            """,
            (user_id,),
        ).fetchall()
        return [row_to_dict(row) for row in rows]

    def client_has_project_access(self, *, user_id: int, project_id: int) -> bool:
        row = self.connection.execute(
            """
            SELECT 1
            FROM project_client_access
            JOIN users ON users.id = project_client_access.user_id
            WHERE project_client_access.user_id = ?
              AND project_client_access.project_id = ?
              AND users.role = 'client'
              AND users.is_active = 1
            """,
            (user_id, project_id),
        ).fetchone()
        return row is not None

    def remove_client_project_access(self, *, project_id: int, user_id: int) -> None:
        with self._lock:
            cursor = self.connection.execute(
                """
                DELETE FROM project_client_access
                WHERE project_id = ? AND user_id = ?
                """,
                (project_id, user_id),
            )
            if cursor.rowcount == 0:
                raise KeyError(f"client {user_id} is not assigned to project {project_id}")
            self.connection.commit()

    def create_dashboard_template(
        self,
        *,
        project_id: int,
        name: str,
        show_summary: bool = True,
        show_price_chart: bool = True,
        show_grid_chart: bool = True,
        show_renewable_chart: bool = True,
        show_bess_chart: bool = True,
        show_hydro_chart: bool = True,
        show_profit_chart: bool = True,
        show_system_dispatch_table: bool = True,
        show_asset_dispatch_table: bool = True,
        table_preview_limit: int = DEFAULT_TABLE_PREVIEW_LIMIT,
        created_by: str = "internal_analyst",
    ) -> dict[str, Any]:
        self.get_project(project_id)
        clean_name = name.strip()
        if not clean_name:
            raise ValueError("dashboard template name is required")
        preview_limit = validate_table_preview_limit(table_preview_limit)
        now = utc_now_iso()
        with self._lock:
            cursor = self.connection.execute(
                """
                INSERT INTO dashboard_templates (
                    project_id,
                    name,
                    show_summary,
                    show_price_chart,
                    show_grid_chart,
                    show_renewable_chart,
                    show_bess_chart,
                    show_hydro_chart,
                    show_profit_chart,
                    show_system_dispatch_table,
                    show_asset_dispatch_table,
                    table_preview_limit,
                    created_at,
                    updated_at,
                    created_by,
                    updated_by
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    project_id,
                    clean_name,
                    bool_to_int(show_summary),
                    bool_to_int(show_price_chart),
                    bool_to_int(show_grid_chart),
                    bool_to_int(show_renewable_chart),
                    bool_to_int(show_bess_chart),
                    bool_to_int(show_hydro_chart),
                    bool_to_int(show_profit_chart),
                    bool_to_int(show_system_dispatch_table),
                    bool_to_int(show_asset_dispatch_table),
                    preview_limit,
                    now,
                    now,
                    created_by,
                    created_by,
                ),
            )
            self.connection.commit()
            return self.get_dashboard_template(cursor.lastrowid)

    def list_dashboard_templates(self, project_id: int) -> list[dict[str, Any]]:
        self.get_project(project_id)
        rows = self.connection.execute(
            """
            SELECT id, project_id, name,
                   show_summary, show_price_chart, show_grid_chart,
                   show_renewable_chart, show_bess_chart, show_hydro_chart,
                   show_profit_chart, show_system_dispatch_table,
                   show_asset_dispatch_table, table_preview_limit,
                   created_at, updated_at, created_by, updated_by
            FROM dashboard_templates
            WHERE project_id = ?
            ORDER BY id
            """,
            (project_id,),
        ).fetchall()
        return [dashboard_template_row_to_dict(row) for row in rows]

    def get_dashboard_template(self, template_id: int) -> dict[str, Any]:
        row = self.connection.execute(
            """
            SELECT id, project_id, name,
                   show_summary, show_price_chart, show_grid_chart,
                   show_renewable_chart, show_bess_chart, show_hydro_chart,
                   show_profit_chart, show_system_dispatch_table,
                   show_asset_dispatch_table, table_preview_limit,
                   created_at, updated_at, created_by, updated_by
            FROM dashboard_templates
            WHERE id = ?
            """,
            (template_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"dashboard template {template_id} not found")
        return dashboard_template_row_to_dict(row)

    def update_dashboard_template(
        self,
        template_id: int,
        *,
        name: str,
        show_summary: bool,
        show_price_chart: bool,
        show_grid_chart: bool,
        show_renewable_chart: bool,
        show_bess_chart: bool,
        show_hydro_chart: bool,
        show_profit_chart: bool,
        show_system_dispatch_table: bool,
        show_asset_dispatch_table: bool,
        table_preview_limit: int,
        updated_by: str = "internal_analyst",
    ) -> dict[str, Any]:
        clean_name = name.strip()
        if not clean_name:
            raise ValueError("dashboard template name is required")
        preview_limit = validate_table_preview_limit(table_preview_limit)
        now = utc_now_iso()
        with self._lock:
            cursor = self.connection.execute(
                """
                UPDATE dashboard_templates
                SET name = ?,
                    show_summary = ?,
                    show_price_chart = ?,
                    show_grid_chart = ?,
                    show_renewable_chart = ?,
                    show_bess_chart = ?,
                    show_hydro_chart = ?,
                    show_profit_chart = ?,
                    show_system_dispatch_table = ?,
                    show_asset_dispatch_table = ?,
                    table_preview_limit = ?,
                    updated_at = ?,
                    updated_by = ?
                WHERE id = ?
                """,
                (
                    clean_name,
                    bool_to_int(show_summary),
                    bool_to_int(show_price_chart),
                    bool_to_int(show_grid_chart),
                    bool_to_int(show_renewable_chart),
                    bool_to_int(show_bess_chart),
                    bool_to_int(show_hydro_chart),
                    bool_to_int(show_profit_chart),
                    bool_to_int(show_system_dispatch_table),
                    bool_to_int(show_asset_dispatch_table),
                    preview_limit,
                    now,
                    updated_by,
                    template_id,
                ),
            )
            if cursor.rowcount == 0:
                raise KeyError(f"dashboard template {template_id} not found")
            self.connection.commit()
            return self.get_dashboard_template(template_id)

    def create_publication_draft(
        self,
        *,
        run_id: int,
        dashboard_template_id: int,
        public_title: str,
        analyst_notes: str = "",
        allowed_artifact_types: list[str] | None = None,
        created_by: str = "internal_analyst",
    ) -> dict[str, Any]:
        lineage = self.get_run_lineage(run_id)
        if lineage["run_status"] != "succeeded":
            raise ValueError("only succeeded runs can be published")
        template = self.get_dashboard_template(dashboard_template_id)
        if template["project_id"] != lineage["project_id"]:
            raise KeyError(f"dashboard template {dashboard_template_id} not found for run {run_id}")
        clean_title = public_title.strip()
        if not clean_title:
            raise ValueError("publication title is required")
        resolved_artifact_types = self._resolve_publication_artifact_types(run_id, allowed_artifact_types)
        now = utc_now_iso()
        with self._lock:
            cursor = self.connection.execute(
                """
                INSERT INTO publications (
                    project_id,
                    scenario_id,
                    scenario_version_id,
                    run_id,
                    dashboard_template_id,
                    public_title,
                    analyst_notes,
                    status,
                    allowed_artifact_types_json,
                    created_at,
                    updated_at,
                    created_by,
                    updated_by
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, 'draft', ?, ?, ?, ?, ?)
                """,
                (
                    lineage["project_id"],
                    lineage["scenario_id"],
                    lineage["scenario_version_id"],
                    run_id,
                    dashboard_template_id,
                    clean_title,
                    analyst_notes.strip(),
                    json.dumps(resolved_artifact_types),
                    now,
                    now,
                    created_by,
                    created_by,
                ),
            )
            self.connection.commit()
            return self.get_publication(cursor.lastrowid)

    def list_run_publications(self, run_id: int) -> list[dict[str, Any]]:
        self.get_run(run_id)
        rows = self.connection.execute(
            """
            SELECT id, project_id, scenario_id, scenario_version_id, run_id,
                   dashboard_template_id, public_title, analyst_notes, status,
                   allowed_artifact_types_json, created_at, updated_at,
                   published_at, unpublished_at, created_by, updated_by,
                   published_by
            FROM publications
            WHERE run_id = ?
            ORDER BY id
            """,
            (run_id,),
        ).fetchall()
        return [publication_row_to_dict(row) for row in rows]

    def get_publication(self, publication_id: int) -> dict[str, Any]:
        row = self.connection.execute(
            """
            SELECT id, project_id, scenario_id, scenario_version_id, run_id,
                   dashboard_template_id, public_title, analyst_notes, status,
                   allowed_artifact_types_json, created_at, updated_at,
                   published_at, unpublished_at, created_by, updated_by,
                   published_by
            FROM publications
            WHERE id = ?
            """,
            (publication_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"publication {publication_id} not found")
        return publication_row_to_dict(row)

    def update_publication_draft(
        self,
        publication_id: int,
        *,
        dashboard_template_id: int,
        public_title: str,
        analyst_notes: str = "",
        allowed_artifact_types: list[str] | None = None,
        updated_by: str = "internal_analyst",
    ) -> dict[str, Any]:
        publication = self.get_publication(publication_id)
        if publication["status"] != "draft":
            raise ValueError("only draft publications can be edited")
        template = self.get_dashboard_template(dashboard_template_id)
        if template["project_id"] != publication["project_id"]:
            raise KeyError(f"dashboard template {dashboard_template_id} not found for publication {publication_id}")
        clean_title = public_title.strip()
        if not clean_title:
            raise ValueError("publication title is required")
        resolved_artifact_types = self._resolve_publication_artifact_types(
            publication["run_id"],
            allowed_artifact_types,
        )
        now = utc_now_iso()
        with self._lock:
            self.connection.execute(
                """
                UPDATE publications
                SET dashboard_template_id = ?,
                    public_title = ?,
                    analyst_notes = ?,
                    allowed_artifact_types_json = ?,
                    updated_at = ?,
                    updated_by = ?
                WHERE id = ?
                """,
                (
                    dashboard_template_id,
                    clean_title,
                    analyst_notes.strip(),
                    json.dumps(resolved_artifact_types),
                    now,
                    updated_by,
                    publication_id,
                ),
            )
            self.connection.commit()
            return self.get_publication(publication_id)

    def publish_publication(
        self,
        publication_id: int,
        *,
        published_by: str = "internal_analyst",
    ) -> dict[str, Any]:
        publication = self.get_publication(publication_id)
        if publication["status"] == "published":
            return publication
        now = utc_now_iso()
        with self._lock:
            self.connection.execute(
                """
                UPDATE publications
                SET status = 'published',
                    updated_at = ?,
                    published_at = ?,
                    unpublished_at = NULL,
                    updated_by = ?,
                    published_by = ?
                WHERE id = ?
                """,
                (now, now, published_by, published_by, publication_id),
            )
            self.connection.commit()
            return self.get_publication(publication_id)

    def unpublish_publication(
        self,
        publication_id: int,
        *,
        unpublished_by: str = "internal_analyst",
    ) -> dict[str, Any]:
        publication = self.get_publication(publication_id)
        if publication["status"] != "published":
            raise ValueError("only published publications can be unpublished")
        now = utc_now_iso()
        with self._lock:
            self.connection.execute(
                """
                UPDATE publications
                SET status = 'unpublished',
                    updated_at = ?,
                    unpublished_at = ?,
                    updated_by = ?
                WHERE id = ?
                """,
                (now, now, unpublished_by, publication_id),
            )
            self.connection.commit()
            return self.get_publication(publication_id)

    def list_published_project_publications(self, project_id: int) -> list[dict[str, Any]]:
        self.get_project(project_id)
        rows = self.connection.execute(
            """
            SELECT id, project_id, scenario_id, scenario_version_id, run_id,
                   dashboard_template_id, public_title, analyst_notes, status,
                   allowed_artifact_types_json, created_at, updated_at,
                   published_at, unpublished_at, created_by, updated_by,
                   published_by
            FROM publications
            WHERE project_id = ?
              AND status = 'published'
            ORDER BY published_at DESC, id DESC
            """,
            (project_id,),
        ).fetchall()
        return [publication_row_to_dict(row) for row in rows]

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

    def get_or_create_hydraulic_diagram(self, scenario_id: int) -> dict[str, Any]:
        with self._lock:
            scenario = self.get_scenario(scenario_id)
            case = self._get_or_create_optimization_case(scenario)
            system = self._get_or_create_hydraulic_system(scenario)
            self._get_or_create_case_hydraulic_system(case["id"], system["id"])
            self._get_or_create_hydraulic_layout(case["id"])
            self.connection.commit()
            return self.get_hydraulic_diagram(scenario_id)

    def get_hydraulic_diagram(self, scenario_id: int) -> dict[str, Any]:
        self.get_scenario(scenario_id)
        context = self._get_hydraulic_diagram_context(scenario_id)
        if context is None:
            raise KeyError(f"hydraulic diagram for scenario {scenario_id} not found")
        return self._hydraulic_diagram_response(context)

    def save_hydraulic_diagram(
        self,
        *,
        scenario_id: int,
        revision: str,
        nodes: list[dict[str, Any]],
        reaches: list[dict[str, Any]] | None = None,
        viewport: dict[str, Any] | None = None,
        updated_by: str = "internal_analyst",
    ) -> dict[str, Any]:
        with self._lock:
            self.get_or_create_hydraulic_diagram(scenario_id)
            context = self._get_hydraulic_diagram_context(scenario_id)
            if context is None:
                raise KeyError(f"hydraulic diagram for scenario {scenario_id} not found")
            layout = context["layout"]
            current_revision = str(layout["layout_version"])
            if str(revision) != current_revision:
                raise ValueError("stale hydraulic diagram revision")

            normalized_nodes = normalize_hydraulic_diagram_nodes(nodes)
            normalized_reaches = normalize_hydraulic_diagram_reaches(reaches or [])
            resolved_viewport = {
                "x": float(layout["viewport_x"]),
                "y": float(layout["viewport_y"]),
                "zoom": float(layout["zoom"]),
            }
            if viewport is not None:
                resolved_viewport = normalize_hydraulic_viewport(viewport)

            now = utc_now_iso()
            layout_id = int(layout["id"])
            case_id = int(context["optimization_case"]["id"])
            system_id = int(context["hydraulic_system"]["id"])

            self.connection.execute(
                "DELETE FROM case_hydraulic_diagram_items WHERE diagram_layout_id = ?",
                (layout_id,),
            )
            self.connection.execute(
                "DELETE FROM case_hydraulic_reaches WHERE case_id = ?",
                (case_id,),
            )
            self.connection.execute(
                "DELETE FROM case_hydraulic_nodes WHERE case_id = ?",
                (case_id,),
            )
            self.connection.execute(
                "DELETE FROM case_hydraulic_plants WHERE case_id = ?",
                (case_id,),
            )

            active_nodes_by_key: dict[str, dict[str, Any]] = {}
            for index, node in enumerate(normalized_nodes):
                if node["component_type"] == "plant":
                    active_id = self._create_case_hydraulic_plant(
                        case_id=case_id,
                        system_id=system_id,
                        plant_key=node["technical_key"],
                        display_name=node["display_name"],
                        updated_by=updated_by,
                        now=now,
                    )
                    entity_type = "case_hydraulic_plant"
                else:
                    created_node = self._create_case_hydraulic_node(
                        case_id=case_id,
                        system_id=system_id,
                        node_key=node["technical_key"],
                        display_name=node["display_name"],
                        node_type=node["component_type"],
                        updated_by=updated_by,
                        now=now,
                    )
                    active_id = created_node["case_hydraulic_node_id"]
                    active_nodes_by_key[node["technical_key"]] = {
                        "case_hydraulic_node_id": active_id,
                        "hydraulic_node_id": created_node["hydraulic_node_id"],
                        "x": node["x"],
                        "y": node["y"],
                    }
                    entity_type = "case_hydraulic_node"
                self.connection.execute(
                    """
                    INSERT INTO case_hydraulic_diagram_items (
                        diagram_layout_id,
                        entity_type,
                        entity_id,
                        x,
                        y,
                        z_index,
                        collapsed,
                        style_json,
                        metadata_json,
                        updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, 0, '{}', '{}', ?)
                    """,
                    (
                        layout_id,
                        entity_type,
                        active_id,
                        node["x"],
                        node["y"],
                        index,
                        now,
                    ),
                )

            for index, reach in enumerate(normalized_reaches):
                from_node = self._resolve_hydraulic_node_for_reach(
                    system_id,
                    reach["from_node_key"],
                    active_nodes_by_key,
                )
                to_node = self._resolve_hydraulic_node_for_reach(
                    system_id,
                    reach["to_node_key"],
                    active_nodes_by_key,
                )
                created_reach = self._create_case_hydraulic_reach(
                    case_id=case_id,
                    system_id=system_id,
                    reach_key=reach["technical_key"],
                    display_name=reach["display_name"],
                    from_node_id=from_node["hydraulic_node_id"],
                    to_node_id=to_node["hydraulic_node_id"],
                    reach_type=reach["reach_type"],
                    updated_by=updated_by,
                    now=now,
                )
                active_endpoints = [
                    node
                    for node in (from_node, to_node)
                    if "case_hydraulic_node_id" in node
                ]
                if active_endpoints:
                    x = sum(float(node["x"]) for node in active_endpoints) / len(active_endpoints)
                    y = sum(float(node["y"]) for node in active_endpoints) / len(active_endpoints)
                else:
                    x = 0.0
                    y = 0.0
                self.connection.execute(
                    """
                    INSERT INTO case_hydraulic_diagram_items (
                        diagram_layout_id,
                        entity_type,
                        entity_id,
                        x,
                        y,
                        z_index,
                        collapsed,
                        style_json,
                        metadata_json,
                        updated_at
                    )
                    VALUES (?, 'case_hydraulic_reach', ?, ?, ?, ?, 0, '{}', '{}', ?)
                    """,
                    (
                        layout_id,
                        created_reach["case_hydraulic_reach_id"],
                        x,
                        y,
                        len(normalized_nodes) + index,
                        now,
                    ),
                )

            self.connection.execute(
                """
                UPDATE case_hydraulic_diagram_layouts
                SET viewport_x = ?,
                    viewport_y = ?,
                    zoom = ?,
                    layout_engine = 'manual',
                    layout_version = layout_version + 1,
                    updated_at = ?,
                    updated_by = ?
                WHERE id = ?
                """,
                (
                    resolved_viewport["x"],
                    resolved_viewport["y"],
                    resolved_viewport["zoom"],
                    now,
                    updated_by,
                    layout_id,
                ),
            )
            self.connection.commit()
            updated_context = self._get_hydraulic_diagram_context(scenario_id)
            if updated_context is None:
                raise KeyError(f"hydraulic diagram for scenario {scenario_id} not found")
            return self._hydraulic_diagram_response(updated_context)

    def validate_hydraulic_diagram(self, scenario_id: int) -> dict[str, Any]:
        self.get_scenario(scenario_id)
        context = self._get_hydraulic_diagram_context(scenario_id)
        if context is None:
            raise KeyError(f"hydraulic diagram for scenario {scenario_id} not found")
        case_id = int(context["optimization_case"]["id"])
        active_node_ids = {
            int(row["hydraulic_node_id"])
            for row in self.connection.execute(
                """
                SELECT hydraulic_node_id
                FROM case_hydraulic_nodes
                WHERE case_id = ? AND is_active = 1
                """,
                (case_id,),
            ).fetchall()
        }
        reach_rows = self.connection.execute(
            """
            SELECT
                case_hydraulic_reaches.id AS case_hydraulic_reach_id,
                case_hydraulic_reaches.case_label,
                hydraulic_reaches.reach_key,
                hydraulic_reaches.reach_type,
                hydraulic_reaches.from_node_id,
                hydraulic_reaches.to_node_id
            FROM case_hydraulic_reaches
            JOIN hydraulic_reaches
              ON hydraulic_reaches.id = case_hydraulic_reaches.hydraulic_reach_id
            WHERE case_hydraulic_reaches.case_id = ?
              AND case_hydraulic_reaches.is_active = 1
            ORDER BY case_hydraulic_reaches.id
            """,
            (case_id,),
        ).fetchall()
        errors: list[dict[str, Any]] = []
        for row in reach_rows:
            reach_key = str(row["reach_key"])
            if row["reach_type"] not in HYDRAULIC_REACH_TYPES:
                errors.append(
                    {
                        "severity": "error",
                        "code": "unsupported_reach_type",
                        "message": f"Reach {reach_key} has unsupported type {row['reach_type']}.",
                        "entity_type": "case_hydraulic_reach",
                        "entity_id": int(row["case_hydraulic_reach_id"]),
                        "technical_key": reach_key,
                    }
                )
            if int(row["from_node_id"]) not in active_node_ids or int(row["to_node_id"]) not in active_node_ids:
                errors.append(
                    {
                        "severity": "error",
                        "code": "inactive_or_missing_endpoint",
                        "message": f"Reach {reach_key} must connect active hydraulic nodes in this case.",
                        "entity_type": "case_hydraulic_reach",
                        "entity_id": int(row["case_hydraulic_reach_id"]),
                        "technical_key": reach_key,
                    }
                )
        validation = {
            "ok": not errors,
            "errors": errors,
            "warnings": [],
            "summary": "Hydraulic topology valid" if not errors else "Hydraulic topology has errors",
        }
        self.connection.execute(
            """
            UPDATE optimization_cases
            SET validation_payload_json = ?,
                updated_at = ?,
                updated_by = 'hydraulic_diagram_validator'
            WHERE id = ?
            """,
            (json.dumps(validation, sort_keys=True), utc_now_iso(), case_id),
        )
        self.connection.commit()
        return validation

    def create_scenario_version(
        self,
        *,
        scenario_id: int,
        system_case_json: dict[str, Any],
        validation_payload: dict[str, Any],
        generation_metadata: dict[str, Any] | None = None,
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
                generation_metadata_json,
                created_at,
                created_by
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                json.dumps(generation_metadata or {}, sort_keys=True),
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
                generation_metadata_json,
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
                generation_metadata_json,
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

    def delete_scenario_version(self, scenario_version_id: int) -> dict[str, Any]:
        with self._lock:
            version = self.get_scenario_version(scenario_version_id, include_document=False)
            run_row = self.connection.execute(
                "SELECT COUNT(*) AS run_count FROM runs WHERE scenario_version_id = ?",
                (scenario_version_id,),
            ).fetchone()
            publication_row = self.connection.execute(
                "SELECT COUNT(*) AS publication_count FROM publications WHERE scenario_version_id = ?",
                (scenario_version_id,),
            ).fetchone()
            run_count = int(run_row["run_count"])
            publication_count = int(publication_row["publication_count"])
            if run_count:
                raise ValueError("scenario versions referenced by runs cannot be deleted")
            if publication_count:
                raise ValueError("scenario versions referenced by publications cannot be deleted")
            self.connection.execute(
                "DELETE FROM scenario_versions WHERE id = ?",
                (scenario_version_id,),
            )
            self.connection.commit()
            return {
                **version,
                "deleted_run_count": run_count,
                "deleted_publication_count": publication_count,
            }

    def create_or_replace_scenario_draft(
        self,
        *,
        scenario_id: int,
        document: dict[str, Any],
        source_version_id: int | None = None,
        created_by: str = "internal_analyst",
    ) -> dict[str, Any]:
        with self._lock:
            self.get_scenario(scenario_id)
            self._ensure_source_version_belongs_to_scenario(scenario_id, source_version_id)
            now = utc_now_iso()
            existing = self.connection.execute(
                """
                SELECT id
                FROM scenario_drafts
                WHERE scenario_id = ?
                """,
                (scenario_id,),
            ).fetchone()
            if existing is None:
                cursor = self.connection.execute(
                    """
                    INSERT INTO scenario_drafts (
                        scenario_id,
                        source_version_id,
                        document_json,
                        created_at,
                        updated_at,
                        created_by,
                        updated_by
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        scenario_id,
                        source_version_id,
                        json.dumps(document, sort_keys=True),
                        now,
                        now,
                        created_by,
                        created_by,
                    ),
                )
                draft_id = cursor.lastrowid
            else:
                draft_id = int(existing["id"])
                self.connection.execute(
                    """
                    UPDATE scenario_drafts
                    SET
                        source_version_id = ?,
                        document_json = ?,
                        updated_at = ?,
                        updated_by = ?
                    WHERE id = ?
                    """,
                    (
                        source_version_id,
                        json.dumps(document, sort_keys=True),
                        now,
                        created_by,
                        draft_id,
                    ),
                )
            self.connection.commit()
            return self.get_scenario_draft(scenario_id)

    def get_scenario_draft(self, scenario_id: int) -> dict[str, Any]:
        self.get_scenario(scenario_id)
        row = self.connection.execute(
            """
            SELECT
                id,
                scenario_id,
                source_version_id,
                document_json,
                created_at,
                updated_at,
                created_by,
                updated_by
            FROM scenario_drafts
            WHERE scenario_id = ?
            """,
            (scenario_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"scenario draft for scenario {scenario_id} not found")
        return scenario_draft_row_to_dict(row)

    def update_scenario_draft(
        self,
        *,
        scenario_id: int,
        document: dict[str, Any],
        updated_by: str = "internal_analyst",
    ) -> dict[str, Any]:
        with self._lock:
            self.get_scenario_draft(scenario_id)
            updated_at = utc_now_iso()
            self.connection.execute(
                """
                UPDATE scenario_drafts
                SET
                    document_json = ?,
                    updated_at = ?,
                    updated_by = ?
                WHERE scenario_id = ?
                """,
                (
                    json.dumps(document, sort_keys=True),
                    updated_at,
                    updated_by,
                    scenario_id,
                ),
            )
            self.connection.commit()
            return self.get_scenario_draft(scenario_id)

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

    def list_scenario_runs(self, scenario_id: int) -> list[dict[str, Any]]:
        self.get_scenario(scenario_id)
        rows = self.connection.execute(
            """
            SELECT
                runs.id,
                runs.scenario_version_id,
                runs.status,
                runs.created_at,
                runs.started_at,
                runs.finished_at,
                runs.duration_seconds,
                runs.exit_code,
                runs.workspace_path,
                runs.input_snapshot_path,
                runs.output_dir,
                runs.summary_path,
                runs.stdout_log_path,
                runs.stderr_log_path,
                runs.error_message,
                runs.success_payload_json,
                runs.error_payload_json,
                runs.stdout,
                runs.stderr,
                runs.triggered_by,
                runs.trigger_type
            FROM runs
            JOIN scenario_versions ON scenario_versions.id = runs.scenario_version_id
            WHERE scenario_versions.scenario_id = ?
            ORDER BY scenario_versions.version_number DESC, runs.id DESC
            """,
            (scenario_id,),
        ).fetchall()
        return [run_row_to_dict(row) for row in rows]

    def get_run_project_id(self, run_id: int) -> int:
        row = self.connection.execute(
            """
            SELECT scenarios.project_id
            FROM runs
            JOIN scenario_versions ON scenario_versions.id = runs.scenario_version_id
            JOIN scenarios ON scenarios.id = scenario_versions.scenario_id
            WHERE runs.id = ?
            """,
            (run_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"run {run_id} not found")
        return int(row["project_id"])

    def get_run_lineage(self, run_id: int) -> dict[str, Any]:
        row = self.connection.execute(
            """
            SELECT runs.id AS run_id,
                   runs.status AS run_status,
                   scenario_versions.id AS scenario_version_id,
                   scenarios.id AS scenario_id,
                   projects.id AS project_id
            FROM runs
            JOIN scenario_versions ON scenario_versions.id = runs.scenario_version_id
            JOIN scenarios ON scenarios.id = scenario_versions.scenario_id
            JOIN projects ON projects.id = scenarios.project_id
            WHERE runs.id = ?
            """,
            (run_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"run {run_id} not found")
        return row_to_dict(row)

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

    def register_run_artifact(
        self,
        *,
        run_id: int,
        artifact_type: str,
        path: str,
        display_name: str,
        media_type: str,
        byte_size: int | None = None,
    ) -> dict[str, Any]:
        self.get_run(run_id)
        resolved_byte_size = byte_size
        if resolved_byte_size is None:
            resolved_byte_size = Path(path).stat().st_size
        created_at = utc_now_iso()
        with self._lock:
            cursor = self.connection.execute(
                """
                INSERT INTO run_artifacts (
                    run_id,
                    artifact_type,
                    path,
                    display_name,
                    media_type,
                    byte_size,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (run_id, artifact_type) DO UPDATE SET
                    path = excluded.path,
                    display_name = excluded.display_name,
                    media_type = excluded.media_type,
                    byte_size = excluded.byte_size,
                    created_at = excluded.created_at
                """,
                (
                    run_id,
                    artifact_type,
                    path,
                    display_name,
                    media_type,
                    resolved_byte_size,
                    created_at,
                ),
            )
            self.connection.commit()
            artifact_id = cursor.lastrowid
            if artifact_id == 0:
                row = self.connection.execute(
                    """
                    SELECT id
                    FROM run_artifacts
                    WHERE run_id = ? AND artifact_type = ?
                    """,
                    (run_id, artifact_type),
                ).fetchone()
                artifact_id = int(row["id"])
            return self.get_run_artifact(artifact_id)

    def list_run_artifacts(self, run_id: int) -> list[dict[str, Any]]:
        self.get_run(run_id)
        rows = self.connection.execute(
            """
            SELECT id, run_id, artifact_type, path, display_name, media_type, byte_size, created_at
            FROM run_artifacts
            WHERE run_id = ?
            ORDER BY id
            """,
            (run_id,),
        ).fetchall()
        return [row_to_dict(row) for row in rows]

    def get_run_artifact(self, artifact_id: int) -> dict[str, Any]:
        row = self.connection.execute(
            """
            SELECT id, run_id, artifact_type, path, display_name, media_type, byte_size, created_at
            FROM run_artifacts
            WHERE id = ?
            """,
            (artifact_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"run artifact {artifact_id} not found")
        return row_to_dict(row)

    def _get_or_create_optimization_case(self, scenario: dict[str, Any]) -> dict[str, Any]:
        row = self.connection.execute(
            """
            SELECT id, scenario_id, case_key, display_name, validation_payload_json,
                   created_at, updated_at, created_by, updated_by
            FROM optimization_cases
            WHERE scenario_id = ?
            """,
            (scenario["id"],),
        ).fetchone()
        if row is not None:
            return row_to_dict(row)

        now = utc_now_iso()
        cursor = self.connection.execute(
            """
            INSERT INTO optimization_cases (
                scenario_id,
                case_key,
                display_name,
                validation_payload_json,
                created_at,
                updated_at,
                created_by,
                updated_by
            )
            VALUES (?, ?, ?, '{}', ?, ?, ?, ?)
            """,
            (
                scenario["id"],
                f"scenario_{scenario['id']}_hydraulic_case",
                scenario["name"],
                now,
                now,
                scenario.get("created_by") or "internal_analyst",
                scenario.get("created_by") or "internal_analyst",
            ),
        )
        return row_to_dict(
            self.connection.execute(
                """
                SELECT id, scenario_id, case_key, display_name, validation_payload_json,
                       created_at, updated_at, created_by, updated_by
                FROM optimization_cases
                WHERE id = ?
                """,
                (cursor.lastrowid,),
            ).fetchone()
        )

    def _get_or_create_hydraulic_system(self, scenario: dict[str, Any]) -> dict[str, Any]:
        system_key = "default_hydraulic_system"
        row = self.connection.execute(
            """
            SELECT id, project_id, system_key, display_name, created_at, updated_at,
                   created_by, updated_by
            FROM hydraulic_systems
            WHERE project_id = ? AND system_key = ?
            """,
            (scenario["project_id"], system_key),
        ).fetchone()
        if row is not None:
            return row_to_dict(row)

        now = utc_now_iso()
        cursor = self.connection.execute(
            """
            INSERT INTO hydraulic_systems (
                project_id,
                system_key,
                display_name,
                created_at,
                updated_at,
                created_by,
                updated_by
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                scenario["project_id"],
                system_key,
                "Default hydraulic system",
                now,
                now,
                scenario.get("created_by") or "internal_analyst",
                scenario.get("created_by") or "internal_analyst",
            ),
        )
        return row_to_dict(
            self.connection.execute(
                """
                SELECT id, project_id, system_key, display_name, created_at, updated_at,
                       created_by, updated_by
                FROM hydraulic_systems
                WHERE id = ?
                """,
                (cursor.lastrowid,),
            ).fetchone()
        )

    def _get_or_create_case_hydraulic_system(self, case_id: int, system_id: int) -> dict[str, Any]:
        row = self.connection.execute(
            """
            SELECT id, case_id, hydraulic_system_id, is_active, created_at, updated_at,
                   created_by, updated_by
            FROM case_hydraulic_systems
            WHERE case_id = ? AND hydraulic_system_id = ?
            """,
            (case_id, system_id),
        ).fetchone()
        if row is not None:
            return row_to_dict(row)

        now = utc_now_iso()
        cursor = self.connection.execute(
            """
            INSERT INTO case_hydraulic_systems (
                case_id,
                hydraulic_system_id,
                is_active,
                created_at,
                updated_at,
                created_by,
                updated_by
            )
            VALUES (?, ?, 1, ?, ?, 'internal_analyst', 'internal_analyst')
            """,
            (case_id, system_id, now, now),
        )
        return row_to_dict(
            self.connection.execute(
                """
                SELECT id, case_id, hydraulic_system_id, is_active, created_at, updated_at,
                       created_by, updated_by
                FROM case_hydraulic_systems
                WHERE id = ?
                """,
                (cursor.lastrowid,),
            ).fetchone()
        )

    def _get_or_create_hydraulic_layout(self, case_id: int) -> dict[str, Any]:
        row = self.connection.execute(
            """
            SELECT id, case_id, layout_key, viewport_x, viewport_y, zoom,
                   layout_engine, layout_version, content_hash, metadata_json,
                   created_at, updated_at, updated_by
            FROM case_hydraulic_diagram_layouts
            WHERE case_id = ? AND layout_key = 'default'
            """,
            (case_id,),
        ).fetchone()
        if row is not None:
            return row_to_dict(row)

        now = utc_now_iso()
        cursor = self.connection.execute(
            """
            INSERT INTO case_hydraulic_diagram_layouts (
                case_id,
                layout_key,
                viewport_x,
                viewport_y,
                zoom,
                layout_engine,
                layout_version,
                metadata_json,
                created_at,
                updated_at,
                updated_by
            )
            VALUES (?, 'default', 0, 0, 1, 'auto_dag', 1, '{}', ?, ?, 'internal_analyst')
            """,
            (case_id, now, now),
        )
        return row_to_dict(
            self.connection.execute(
                """
                SELECT id, case_id, layout_key, viewport_x, viewport_y, zoom,
                       layout_engine, layout_version, content_hash, metadata_json,
                       created_at, updated_at, updated_by
                FROM case_hydraulic_diagram_layouts
                WHERE id = ?
                """,
                (cursor.lastrowid,),
            ).fetchone()
        )

    def _get_hydraulic_diagram_context(self, scenario_id: int) -> dict[str, Any] | None:
        case_row = self.connection.execute(
            """
            SELECT id, scenario_id, case_key, display_name, validation_payload_json,
                   created_at, updated_at, created_by, updated_by
            FROM optimization_cases
            WHERE scenario_id = ?
            """,
            (scenario_id,),
        ).fetchone()
        if case_row is None:
            return None
        case = row_to_dict(case_row)
        system_row = self.connection.execute(
            """
            SELECT hydraulic_systems.id, hydraulic_systems.project_id,
                   hydraulic_systems.system_key, hydraulic_systems.display_name,
                   hydraulic_systems.created_at, hydraulic_systems.updated_at,
                   hydraulic_systems.created_by, hydraulic_systems.updated_by
            FROM case_hydraulic_systems
            JOIN hydraulic_systems ON hydraulic_systems.id = case_hydraulic_systems.hydraulic_system_id
            WHERE case_hydraulic_systems.case_id = ?
              AND case_hydraulic_systems.is_active = 1
            ORDER BY hydraulic_systems.id
            """,
            (case["id"],),
        ).fetchone()
        layout_row = self.connection.execute(
            """
            SELECT id, case_id, layout_key, viewport_x, viewport_y, zoom,
                   layout_engine, layout_version, content_hash, metadata_json,
                   created_at, updated_at, updated_by
            FROM case_hydraulic_diagram_layouts
            WHERE case_id = ? AND layout_key = 'default'
            """,
            (case["id"],),
        ).fetchone()
        if system_row is None or layout_row is None:
            return None
        return {
            "scenario_id": scenario_id,
            "optimization_case": case,
            "hydraulic_system": row_to_dict(system_row),
            "layout": row_to_dict(layout_row),
        }

    def _hydraulic_diagram_response(self, context: dict[str, Any]) -> dict[str, Any]:
        layout = context["layout"]
        layout_id = int(layout["id"])
        node_rows = self.connection.execute(
            """
            SELECT
                case_hydraulic_diagram_items.id AS layout_item_id,
                case_hydraulic_diagram_items.entity_type,
                case_hydraulic_diagram_items.entity_id,
                case_hydraulic_diagram_items.x,
                case_hydraulic_diagram_items.y,
                case_hydraulic_diagram_items.z_index,
                hydraulic_nodes.node_type AS component_type,
                hydraulic_nodes.node_key AS technical_key,
                case_hydraulic_nodes.case_label AS display_name
            FROM case_hydraulic_diagram_items
            JOIN case_hydraulic_nodes
              ON case_hydraulic_nodes.id = case_hydraulic_diagram_items.entity_id
            JOIN hydraulic_nodes
              ON hydraulic_nodes.id = case_hydraulic_nodes.hydraulic_node_id
            WHERE case_hydraulic_diagram_items.diagram_layout_id = ?
              AND case_hydraulic_diagram_items.entity_type = 'case_hydraulic_node'
            """,
            (layout_id,),
        ).fetchall()
        plant_rows = self.connection.execute(
            """
            SELECT
                case_hydraulic_diagram_items.id AS layout_item_id,
                case_hydraulic_diagram_items.entity_type,
                case_hydraulic_diagram_items.entity_id,
                case_hydraulic_diagram_items.x,
                case_hydraulic_diagram_items.y,
                case_hydraulic_diagram_items.z_index,
                'plant' AS component_type,
                hydraulic_plants.plant_key AS technical_key,
                case_hydraulic_plants.case_label AS display_name
            FROM case_hydraulic_diagram_items
            JOIN case_hydraulic_plants
              ON case_hydraulic_plants.id = case_hydraulic_diagram_items.entity_id
            JOIN hydraulic_plants
              ON hydraulic_plants.id = case_hydraulic_plants.hydraulic_plant_id
            WHERE case_hydraulic_diagram_items.diagram_layout_id = ?
              AND case_hydraulic_diagram_items.entity_type = 'case_hydraulic_plant'
            """,
            (layout_id,),
        ).fetchall()
        nodes = [hydraulic_diagram_node_row_to_dict(row) for row in node_rows + plant_rows]
        nodes.sort(key=lambda node: (node["z_index"], node["layout_item_id"]))
        reach_rows = self.connection.execute(
            """
            SELECT
                case_hydraulic_diagram_items.id AS layout_item_id,
                case_hydraulic_diagram_items.z_index,
                case_hydraulic_reaches.id AS entity_id,
                hydraulic_reaches.reach_key AS technical_key,
                case_hydraulic_reaches.case_label AS display_name,
                hydraulic_reaches.reach_type,
                from_nodes.node_key AS from_node_key,
                to_nodes.node_key AS to_node_key
            FROM case_hydraulic_reaches
            JOIN hydraulic_reaches
              ON hydraulic_reaches.id = case_hydraulic_reaches.hydraulic_reach_id
            JOIN hydraulic_nodes AS from_nodes
              ON from_nodes.id = hydraulic_reaches.from_node_id
            JOIN hydraulic_nodes AS to_nodes
              ON to_nodes.id = hydraulic_reaches.to_node_id
            LEFT JOIN case_hydraulic_diagram_items
              ON case_hydraulic_diagram_items.entity_type = 'case_hydraulic_reach'
             AND case_hydraulic_diagram_items.entity_id = case_hydraulic_reaches.id
             AND case_hydraulic_diagram_items.diagram_layout_id = ?
            WHERE case_hydraulic_reaches.case_id = ?
              AND case_hydraulic_reaches.is_active = 1
            ORDER BY COALESCE(case_hydraulic_diagram_items.z_index, 0),
                     case_hydraulic_reaches.id
            """,
            (layout_id, int(context["optimization_case"]["id"])),
        ).fetchall()
        reaches = [hydraulic_diagram_reach_row_to_dict(row) for row in reach_rows]
        return {
            "scenario_id": context["scenario_id"],
            "optimization_case": optimization_case_public_dict(context["optimization_case"]),
            "hydraulic_system": hydraulic_system_public_dict(context["hydraulic_system"]),
            "layout": hydraulic_layout_public_dict(layout),
            "revision": str(layout["layout_version"]),
            "nodes": nodes,
            "reaches": reaches,
        }

    def _create_case_hydraulic_node(
        self,
        *,
        case_id: int,
        system_id: int,
        node_key: str,
        display_name: str,
        node_type: str,
        updated_by: str,
        now: str,
    ) -> dict[str, int]:
        self.connection.execute(
            """
            INSERT INTO hydraulic_nodes (
                hydraulic_system_id,
                node_key,
                display_name,
                node_type,
                created_at,
                updated_at,
                created_by,
                updated_by
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (hydraulic_system_id, node_key) DO UPDATE SET
                display_name = excluded.display_name,
                node_type = excluded.node_type,
                updated_at = excluded.updated_at,
                updated_by = excluded.updated_by
            """,
            (system_id, node_key, display_name, node_type, now, now, updated_by, updated_by),
        )
        node_row = self.connection.execute(
            """
            SELECT id
            FROM hydraulic_nodes
            WHERE hydraulic_system_id = ? AND node_key = ?
            """,
            (system_id, node_key),
        ).fetchone()
        cursor = self.connection.execute(
            """
            INSERT INTO case_hydraulic_nodes (
                case_id,
                hydraulic_node_id,
                case_label,
                is_active,
                created_at,
                updated_at,
                created_by,
                updated_by
            )
            VALUES (?, ?, ?, 1, ?, ?, ?, ?)
            """,
            (case_id, int(node_row["id"]), display_name, now, now, updated_by, updated_by),
        )
        return {
            "case_hydraulic_node_id": int(cursor.lastrowid),
            "hydraulic_node_id": int(node_row["id"]),
        }

    def _resolve_hydraulic_node_for_reach(
        self,
        system_id: int,
        node_key: str,
        active_nodes_by_key: Mapping[str, dict[str, Any]],
    ) -> dict[str, Any]:
        if node_key in active_nodes_by_key:
            return active_nodes_by_key[node_key]
        row = self.connection.execute(
            """
            SELECT id
            FROM hydraulic_nodes
            WHERE hydraulic_system_id = ? AND node_key = ?
            """,
            (system_id, node_key),
        ).fetchone()
        if row is None:
            raise ValueError(f"hydraulic reach endpoint not found: {node_key}")
        return {"hydraulic_node_id": int(row["id"])}

    def _create_case_hydraulic_reach(
        self,
        *,
        case_id: int,
        system_id: int,
        reach_key: str,
        display_name: str,
        from_node_id: int,
        to_node_id: int,
        reach_type: str,
        updated_by: str,
        now: str,
    ) -> dict[str, int]:
        self.connection.execute(
            """
            INSERT INTO hydraulic_reaches (
                hydraulic_system_id,
                reach_key,
                display_name,
                from_node_id,
                to_node_id,
                reach_type,
                travel_time_hours,
                routing_method,
                created_at,
                updated_at,
                created_by,
                updated_by
            )
            VALUES (?, ?, ?, ?, ?, ?, 0, 'none', ?, ?, ?, ?)
            ON CONFLICT (hydraulic_system_id, reach_key) DO UPDATE SET
                display_name = excluded.display_name,
                from_node_id = excluded.from_node_id,
                to_node_id = excluded.to_node_id,
                reach_type = excluded.reach_type,
                updated_at = excluded.updated_at,
                updated_by = excluded.updated_by
            """,
            (
                system_id,
                reach_key,
                display_name,
                from_node_id,
                to_node_id,
                reach_type,
                now,
                now,
                updated_by,
                updated_by,
            ),
        )
        reach_row = self.connection.execute(
            """
            SELECT id
            FROM hydraulic_reaches
            WHERE hydraulic_system_id = ? AND reach_key = ?
            """,
            (system_id, reach_key),
        ).fetchone()
        cursor = self.connection.execute(
            """
            INSERT INTO case_hydraulic_reaches (
                case_id,
                hydraulic_reach_id,
                case_label,
                is_active,
                created_at,
                updated_at,
                created_by,
                updated_by
            )
            VALUES (?, ?, ?, 1, ?, ?, ?, ?)
            """,
            (case_id, int(reach_row["id"]), display_name, now, now, updated_by, updated_by),
        )
        return {
            "case_hydraulic_reach_id": int(cursor.lastrowid),
            "hydraulic_reach_id": int(reach_row["id"]),
        }

    def _create_case_hydraulic_plant(
        self,
        *,
        case_id: int,
        system_id: int,
        plant_key: str,
        display_name: str,
        updated_by: str,
        now: str,
    ) -> int:
        self.connection.execute(
            """
            INSERT INTO hydraulic_plants (
                hydraulic_system_id,
                plant_key,
                display_name,
                created_at,
                updated_at,
                created_by,
                updated_by
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (hydraulic_system_id, plant_key) DO UPDATE SET
                display_name = excluded.display_name,
                updated_at = excluded.updated_at,
                updated_by = excluded.updated_by
            """,
            (system_id, plant_key, display_name, now, now, updated_by, updated_by),
        )
        plant_row = self.connection.execute(
            """
            SELECT id
            FROM hydraulic_plants
            WHERE hydraulic_system_id = ? AND plant_key = ?
            """,
            (system_id, plant_key),
        ).fetchone()
        cursor = self.connection.execute(
            """
            INSERT INTO case_hydraulic_plants (
                case_id,
                hydraulic_plant_id,
                case_label,
                is_active,
                created_at,
                updated_at,
                created_by,
                updated_by
            )
            VALUES (?, ?, ?, 1, ?, ?, ?, ?)
            """,
            (case_id, int(plant_row["id"]), display_name, now, now, updated_by, updated_by),
        )
        return int(cursor.lastrowid)

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

    def _ensure_source_version_belongs_to_scenario(
        self,
        scenario_id: int,
        source_version_id: int | None,
    ) -> None:
        if source_version_id is None:
            return

        source_version = self.get_scenario_version(source_version_id, include_document=False)
        if source_version["scenario_id"] != scenario_id:
            raise KeyError(f"scenario version {source_version_id} not found for scenario {scenario_id}")

    def _resolve_publication_artifact_types(
        self,
        run_id: int,
        requested_artifact_types: list[str] | None,
    ) -> list[str]:
        registered_types = {artifact["artifact_type"] for artifact in self.list_run_artifacts(run_id)}
        if requested_artifact_types is None:
            return [
                artifact_type
                for artifact_type in DEFAULT_PUBLICATION_ARTIFACT_TYPES
                if artifact_type in registered_types
            ]

        resolved: list[str] = []
        for artifact_type in requested_artifact_types:
            clean_type = str(artifact_type).strip()
            if not clean_type:
                continue
            if clean_type not in registered_types:
                raise ValueError(f"artifact type {clean_type} is not registered for run {run_id}")
            if clean_type not in resolved:
                resolved.append(clean_type)
        return resolved


def row_to_dict(row: Mapping[str, Any] | sqlite3.Row) -> dict[str, Any]:
    return {key: row[key] for key in row.keys()}


def user_row_to_dict(row: Mapping[str, Any] | sqlite3.Row) -> dict[str, Any]:
    value = row_to_dict(row)
    value["is_active"] = bool(value["is_active"])
    return value


def dashboard_template_row_to_dict(row: Mapping[str, Any] | sqlite3.Row) -> dict[str, Any]:
    value = row_to_dict(row)
    for field in DASHBOARD_TEMPLATE_FLAGS:
        value[field] = bool(value[field])
    return value


def publication_row_to_dict(row: Mapping[str, Any] | sqlite3.Row) -> dict[str, Any]:
    value = row_to_dict(row)
    value["allowed_artifact_types"] = json.loads(value.pop("allowed_artifact_types_json") or "[]")
    return value


def bool_to_int(value: bool) -> int:
    return 1 if bool(value) else 0


def validate_table_preview_limit(value: int) -> int:
    try:
        preview_limit = int(value)
    except (TypeError, ValueError) as error:
        raise ValueError("table preview limit must be a positive integer") from error
    if preview_limit < 1:
        raise ValueError("table preview limit must be a positive integer")
    return preview_limit


def normalize_hydraulic_viewport(viewport: Mapping[str, Any]) -> dict[str, float]:
    zoom = float(viewport.get("zoom", 1.0))
    if zoom <= 0:
        raise ValueError("hydraulic diagram zoom must be positive")
    return {
        "x": float(viewport.get("x", 0.0)),
        "y": float(viewport.get("y", 0.0)),
        "zoom": zoom,
    }


def normalize_hydraulic_diagram_nodes(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, str]] = set()
    for node in nodes:
        component_type = str(node.get("component_type") or "").strip()
        if component_type not in HYDRAULIC_VISIBLE_COMPONENT_TYPES:
            raise ValueError(f"unsupported hydraulic component type: {component_type}")
        technical_key = str(node.get("technical_key") or "").strip()
        if not technical_key:
            raise ValueError("hydraulic component technical_key is required")
        identity = (component_type, technical_key)
        if identity in seen_keys:
            raise ValueError(f"duplicate hydraulic component key: {technical_key}")
        seen_keys.add(identity)
        display_name = str(node.get("display_name") or "").strip() or technical_key
        normalized.append(
            {
                "component_type": component_type,
                "technical_key": technical_key,
                "display_name": display_name,
                "x": float(node.get("x", 0.0)),
                "y": float(node.get("y", 0.0)),
            }
        )
    return normalized


def normalize_hydraulic_diagram_reaches(reaches: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    seen_keys: set[str] = set()
    for reach in reaches:
        technical_key = str(reach.get("technical_key") or "").strip()
        if not technical_key:
            raise ValueError("hydraulic reach technical_key is required")
        if technical_key in seen_keys:
            raise ValueError(f"duplicate hydraulic reach key: {technical_key}")
        seen_keys.add(technical_key)
        from_node_key = str(reach.get("from_node_key") or "").strip()
        to_node_key = str(reach.get("to_node_key") or "").strip()
        if not from_node_key or not to_node_key:
            raise ValueError("hydraulic reach endpoints are required")
        reach_type = str(reach.get("reach_type") or "").strip()
        if reach_type not in HYDRAULIC_REACH_TYPES:
            raise ValueError(f"unsupported hydraulic reach type: {reach_type}")
        normalized.append(
            {
                "technical_key": technical_key,
                "display_name": str(reach.get("display_name") or "").strip() or technical_key,
                "from_node_key": from_node_key,
                "to_node_key": to_node_key,
                "reach_type": reach_type,
            }
        )
    return normalized


def optimization_case_public_dict(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "scenario_id": row["scenario_id"],
        "case_key": row["case_key"],
        "display_name": row["display_name"],
        "updated_at": row["updated_at"],
    }


def hydraulic_system_public_dict(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "project_id": row["project_id"],
        "system_key": row["system_key"],
        "display_name": row["display_name"],
    }


def hydraulic_layout_public_dict(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "case_id": row["case_id"],
        "layout_key": row["layout_key"],
        "layout_engine": row["layout_engine"],
        "layout_version": row["layout_version"],
        "revision": str(row["layout_version"]),
        "viewport": {
            "x": float(row["viewport_x"]),
            "y": float(row["viewport_y"]),
            "zoom": float(row["zoom"]),
        },
        "updated_at": row["updated_at"],
        "updated_by": row["updated_by"],
    }


def hydraulic_diagram_node_row_to_dict(row: Mapping[str, Any] | sqlite3.Row) -> dict[str, Any]:
    value = row_to_dict(row)
    return {
        "layout_item_id": value["layout_item_id"],
        "entity_type": value["entity_type"],
        "entity_id": value["entity_id"],
        "component_type": value["component_type"],
        "technical_key": value["technical_key"],
        "display_name": value["display_name"],
        "x": float(value["x"]),
        "y": float(value["y"]),
        "z_index": int(value["z_index"]),
    }


def hydraulic_diagram_reach_row_to_dict(row: Mapping[str, Any] | sqlite3.Row) -> dict[str, Any]:
    value = row_to_dict(row)
    return {
        "layout_item_id": value["layout_item_id"],
        "entity_type": "case_hydraulic_reach",
        "entity_id": value["entity_id"],
        "technical_key": value["technical_key"],
        "display_name": value["display_name"],
        "from_node_key": value["from_node_key"],
        "to_node_key": value["to_node_key"],
        "reach_type": value["reach_type"],
        "z_index": int(value["z_index"] or 0),
    }


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


def scenario_version_row_to_dict(
    row: Mapping[str, Any] | sqlite3.Row,
    *,
    include_document: bool,
) -> dict[str, Any]:
    value = row_to_dict(row)
    value["asset_counts"] = json.loads(value.pop("asset_counts_json"))
    value["generation_metadata"] = json.loads(value.pop("generation_metadata_json") or "{}")
    if include_document:
        value["system_case_json"] = json.loads(value.pop("system_case_json"))
        value["validation_payload"] = json.loads(value.pop("validation_payload_json"))
    return value


def scenario_draft_row_to_dict(row: Mapping[str, Any] | sqlite3.Row) -> dict[str, Any]:
    value = row_to_dict(row)
    value["document"] = json.loads(value.pop("document_json"))
    return value


def run_row_to_dict(row: Mapping[str, Any] | sqlite3.Row) -> dict[str, Any]:
    value = row_to_dict(row)
    value["success_payload"] = json.loads(value.pop("success_payload_json") or "{}")
    value["error_payload"] = json.loads(value.pop("error_payload_json") or "{}")
    return value
