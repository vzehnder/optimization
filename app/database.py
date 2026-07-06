from __future__ import annotations

import os
import re
import sqlite3
from pathlib import Path
from typing import Any
from urllib.parse import quote

from dotenv import load_dotenv


load_dotenv(Path(__file__).resolve().parents[1] / ".env")


POSTGRESQL_URL_PREFIXES = ("postgresql://", "postgres://")
POSTGRES_ENV_FIELDS = {
    "DB_HOST": "host",
    "DB_PORT": "port",
    "DB_NAME": "database name",
    "DB_USER": "user",
    "DB_PASSWORD": "password",
}

ID_TABLES = {
    "auth_sessions",
    "case_hydraulic_curve_bindings",
    "case_hydraulic_diagram_items",
    "case_hydraulic_diagram_layouts",
    "case_hydraulic_nodes",
    "case_hydraulic_plants",
    "case_hydraulic_reaches",
    "case_hydraulic_reservoir_parameters",
    "case_hydraulic_systems",
    "case_hydraulic_time_series_bindings",
    "case_hydraulic_units",
    "dashboard_templates",
    "hydraulic_curve_points",
    "hydraulic_curve_sets",
    "hydraulic_nodes",
    "hydraulic_plants",
    "hydraulic_reaches",
    "hydraulic_systems",
    "hydraulic_time_series_points",
    "hydraulic_time_series_sets",
    "hydraulic_units",
    "optimization_cases",
    "projects",
    "publications",
    "run_artifacts",
    "runs",
    "scenario_drafts",
    "scenario_version_hydraulic_diagram_snapshots",
    "scenario_versions",
    "scenarios",
    "time_series_periods",
    "time_series_set_revisions",
    "time_series_sets",
    "time_series_signals",
    "time_series_sources",
    "time_series_values",
    "users",
}


class PostgresCursor:
    def __init__(self, cursor: Any, *, lastrowid: int = 0):
        self._cursor = cursor
        self.lastrowid = lastrowid
        self.rowcount = cursor.rowcount

    def fetchone(self):
        return self._cursor.fetchone()

    def fetchall(self):
        return self._cursor.fetchall()


class PostgresConnection:
    """Small DB-API compatibility layer for the store's existing SQL."""

    backend = "postgresql"

    def __init__(self, database_url: str):
        try:
            import psycopg
            from psycopg.rows import dict_row
        except ImportError as error:
            raise RuntimeError(
                "PostgreSQL support requires psycopg; install requirements.txt"
            ) from error

        self._connection = psycopg.connect(
            normalize_postgresql_url(database_url),
            autocommit=True,
            row_factory=dict_row,
        )

    def execute(self, sql: str, parameters: tuple[Any, ...] | list[Any] = ()) -> PostgresCursor:
        translated_sql, inserted_table = translate_postgresql_sql(sql)
        should_return_id = (
            inserted_table in ID_TABLES
            and not re.search(r"\bRETURNING\b", translated_sql, flags=re.IGNORECASE)
        )
        if should_return_id:
            translated_sql = f"{translated_sql.rstrip().rstrip(';')} RETURNING id"

        cursor = self._connection.execute(translated_sql, parameters)
        lastrowid = 0
        if should_return_id:
            row = cursor.fetchone()
            if row is not None:
                lastrowid = int(row["id"])
        return PostgresCursor(cursor, lastrowid=lastrowid)

    def executemany(
        self,
        sql: str,
        seq_of_parameters: list[tuple[Any, ...]] | tuple[tuple[Any, ...], ...],
    ) -> PostgresCursor:
        translated_sql, _inserted_table = translate_postgresql_sql(sql)
        cursor = self._connection.cursor()
        cursor.executemany(translated_sql, seq_of_parameters)
        return PostgresCursor(cursor)

    def executescript(self, script: str) -> None:
        self._connection.execute(script)

    def commit(self) -> None:
        # PostgreSQL runs in autocommit mode because the existing store manages
        # one logical write per statement and does not consistently roll back
        # after expected constraint errors.
        return None

    def rollback(self) -> None:
        return None

    def close(self) -> None:
        self._connection.close()


def connect_database(database_url: str):
    if database_url.startswith("sqlite:///"):
        database_path = sqlite_path_from_url(database_url)
        if database_path != ":memory:":
            Path(database_path).parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(database_path, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return "sqlite", database_path, connection

    if database_url.startswith(POSTGRESQL_URL_PREFIXES):
        return "postgresql", None, PostgresConnection(database_url)

    raise ValueError(
        "DATABASE_URL must start with sqlite:/// or postgresql://"
    )


def database_url_from_env() -> str:
    explicit_url = os.environ.get("DATABASE_URL", "").strip()
    if explicit_url:
        return explicit_url

    configured = {
        variable: os.environ.get(variable, "").strip()
        for variable in POSTGRES_ENV_FIELDS
    }
    if not any(configured.values()):
        return "sqlite:///.tmp/analyst_app.sqlite3"

    missing = [
        variable
        for variable, value in configured.items()
        if not value
    ]
    if missing:
        raise ValueError(
            "incomplete PostgreSQL configuration; missing "
            + ", ".join(sorted(missing))
        )

    try:
        port = int(configured["DB_PORT"])
    except ValueError as error:
        raise ValueError("DB_PORT must be an integer") from error
    if port < 1 or port > 65535:
        raise ValueError("DB_PORT must be between 1 and 65535")

    host = configured["DB_HOST"]
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    user = quote(configured["DB_USER"], safe="")
    password = quote(configured["DB_PASSWORD"], safe="")
    database_name = quote(configured["DB_NAME"], safe="")
    return f"postgresql://{user}:{password}@{host}:{port}/{database_name}"


def sqlite_path_from_url(database_url: str) -> str:
    if database_url == "sqlite:///:memory:":
        return ":memory:"

    prefix = "sqlite:///"
    if not database_url.startswith(prefix):
        raise ValueError("sqlite DATABASE_URL must start with sqlite:///")

    path_text = database_url[len(prefix) :]
    if not path_text:
        raise ValueError("sqlite DATABASE_URL must include a database path")
    return path_text


def normalize_postgresql_url(database_url: str) -> str:
    if database_url.startswith("postgres://"):
        return f"postgresql://{database_url[len('postgres://') :]}"
    return database_url


def translate_postgresql_sql(sql: str) -> tuple[str, str | None]:
    translated = sql
    ignore_conflicts = bool(
        re.match(r"^\s*INSERT\s+OR\s+IGNORE\s+INTO\b", translated, flags=re.IGNORECASE)
    )
    if ignore_conflicts:
        translated = re.sub(
            r"^(\s*)INSERT\s+OR\s+IGNORE\s+INTO\b",
            r"\1INSERT INTO",
            translated,
            count=1,
            flags=re.IGNORECASE,
        )

    inserted_table_match = re.match(
        r"^\s*INSERT\s+INTO\s+([a-z_][a-z0-9_]*)\b",
        translated,
        flags=re.IGNORECASE,
    )
    inserted_table = inserted_table_match.group(1).lower() if inserted_table_match else None

    translated = translated.replace("?", "%s")
    if ignore_conflicts:
        translated = f"{translated.rstrip().rstrip(';')} ON CONFLICT DO NOTHING"
    return translated, inserted_table


def postgres_schema_from_sqlite(sqlite_schema: str) -> str:
    schema = re.sub(
        r"""
        \s*CREATE\s+TRIGGER\s+IF\s+NOT\s+EXISTS\s+scenario_versions_immutable
        .*?
        \s*END;
        """,
        "",
        sqlite_schema,
        count=1,
        flags=re.IGNORECASE | re.DOTALL | re.VERBOSE,
    )
    schema = schema.replace(
        "INTEGER PRIMARY KEY AUTOINCREMENT",
        "INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY",
    )
    schema = schema.replace(" UNIQUE COLLATE NOCASE", " UNIQUE")
    schema += """

    CREATE OR REPLACE FUNCTION reject_scenario_version_update()
    RETURNS trigger AS $$
    BEGIN
        RAISE EXCEPTION 'scenario versions are immutable';
    END;
    $$ LANGUAGE plpgsql;

    DROP TRIGGER IF EXISTS scenario_versions_immutable ON scenario_versions;
    CREATE TRIGGER scenario_versions_immutable
    BEFORE UPDATE ON scenario_versions
    FOR EACH ROW EXECUTE FUNCTION reject_scenario_version_update();
    """
    return schema
