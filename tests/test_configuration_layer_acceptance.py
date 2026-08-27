"""End-to-end acceptance narratives for the configured portal and console."""

import json
import sqlite3
import tempfile
import unittest
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path
from unittest import mock

from fastapi.testclient import TestClient

from app.auth import hash_password
from app.main import create_app
from app.persistence import AnalystStore, PORTAL_CONFIGURATION_MIGRATION
from app.time_series_catalog import (
    CatalogImportRequest,
    CatalogSignalMappingRequest,
    TIME_SERIES_SIGNAL_CATALOG,
    TimeSeriesSignalDefinition,
    prepare_time_series_catalog_import,
)
from tests.auth_test_helpers import (
    csrf_headers,
    delete_with_csrf,
    login_json_with_csrf,
    post_json_with_csrf,
    put_json_with_csrf,
)
from tests.test_results_review import create_completed_run_with_result_artifacts
from tests.test_configuration_layer_operator_console import (
    RecordingRunQueue,
    StubValidationService,
    operator_draft_document,
)
from tests.test_configuration_layer_console_fail_closed import (
    CASE_DRAFT_DOCUMENT,
    case_draft_with_discharge_power,
    console_document as recovery_console_document,
    import_demand_set as import_recovery_demand_set,
    import_price_set as import_recovery_price_set,
)


EMPTY_CONSOLE_DOCUMENT = {
    "schema_version": "operator_console_config.v1",
    "public_identity": {
        "name": "Plan diario legado",
        "description": "Consola que el cliente migrado no puede abrir",
    },
    "parameters": [],
    "groups": [],
    "results": {"kpis": [], "charts": [], "tables": []},
}

PORTAL_ACCEPTANCE_DOCUMENT = {
    "schema_version": "portal_config.v1",
    "display_name": "Energia Cliente Norte",
    "sections": {
        "kpis": {
            "enabled": True,
            "label": "Resumen ejecutivo",
            "items": [
                {
                    "id": "beneficio_total",
                    "path": "objective_value_usd",
                    "label": "Beneficio total",
                    "unit": "USD",
                    "decimals": 1,
                    "sign": "auto",
                    "emphasis": "strong",
                }
            ],
        },
        "charts": {"enabled": False, "label": "Resultados", "items": []},
        "tables": {"enabled": False, "label": "Detalle", "items": []},
        "downloads": {"enabled": True, "label": "Descargas autorizadas"},
    },
}


def import_acceptance_set(
    store: AnalystStore,
    scenario_id: int,
    *,
    name: str,
    signal_key: str,
    first_value: float,
) -> dict:
    start = datetime(2026, 1, 1)
    prepared = prepare_time_series_catalog_import(
        rows=[
            {
                "period_start": (start + timedelta(hours=offset)).isoformat(),
                "hours": "1.0",
                "value": str(first_value + offset),
            }
            for offset in range(4)
        ],
        request=CatalogImportRequest(
            set_name=name,
            version_label="v1",
            data_kind="real",
            timezone="America/Santiago",
            timestamp_column="period_start",
            duration_hours_column="hours",
            signal_mappings=[
                CatalogSignalMappingRequest(
                    source_column="value", signal_key=signal_key
                )
            ],
        ),
    )
    return store.import_time_series_catalog_set(
        scenario_id=scenario_id,
        source={
            "id": f"acceptance-{name.lower().replace(' ', '-')}",
            "original_filename": f"{name}.csv",
            "media_type": "text/csv",
            "checksum": f"sha256:{name}",
        },
        prepared_import=prepared,
    )


def operator_acceptance_document(
    *, demand_set_id: int, forecast_set_id: int, price_set_id: int
) -> dict:
    return {
        "schema_version": "operator_console_config.v1",
        "public_identity": {
            "name": "Plan diario Planta Norte",
            "description": "Ajuste operativo de potencia y series",
        },
        "parameters": [
            {
                "id": "potencia_bess",
                "pointer": {
                    "asset_id": "battery_1",
                    "field": "charge_power_max_mw",
                },
                "label": "Potencia maxima BESS",
                "unit": "MW",
                "min": 0,
                "max": 100,
                "default": 40,
            }
        ],
        "groups": [
            {
                "id": "operacion",
                "label": "Operacion",
                "granularities": ["full_horizon"],
                "columns": [
                    {
                        "id": "demanda",
                        "signal": {
                            "entity_type": "component:load",
                            "entity_id": "load_1",
                            "signal_key": "load_demand_mw",
                        },
                        "label": "Demanda",
                        "editable": True,
                        "source_options": [
                            {
                                "id": "base",
                                "label": "Demanda base",
                                "time_series_set_id": demand_set_id,
                            },
                            {
                                "id": "forecast",
                                "label": "Pronostico actualizado",
                                "time_series_set_id": forecast_set_id,
                            },
                        ],
                        "default_source_option_id": "base",
                    },
                    {
                        "id": "precio",
                        "signal": {
                            "entity_type": "component:grid",
                            "entity_id": "grid_1",
                            "signal_key": "import_price_usd_per_mwh",
                        },
                        "label": "Precio de compra",
                        "editable": True,
                        "source_options": [
                            {
                                "id": "base",
                                "label": "Precio base",
                                "time_series_set_id": price_set_id,
                            }
                        ],
                        "default_source_option_id": "base",
                    },
                ],
            }
        ],
        "results": {"kpis": [], "charts": [], "tables": []},
    }


class ConfigurationLayerMigrationAcceptanceTests(unittest.TestCase):
    """A pre-cutover identity keeps its portal and gains no operator power."""

    def test_a_legacy_client_keeps_portal_publications_without_gaining_console_access(
        self,
    ):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            database_path = root / "legacy.sqlite3"
            database_url = f"sqlite:///{database_path}"
            artifact_root = root / "artifacts"

            project_id, console_id = self._write_pre_cutover_fixture(
                database_url, database_path, artifact_root
            )
            store = AnalystStore(database_url)
            client = TestClient(
                create_app(
                    store=store,
                    artifact_root=artifact_root,
                    auth_enabled=True,
                )
            )
            try:
                login = login_json_with_csrf(
                    client, "legacy-client@example.local", "client pass"
                )
                self.assertEqual(login.status_code, 200, login.text)
                self.assertEqual(
                    {
                        "role": login.json()["user"]["role"],
                        "landing_path": login.json()["landing_path"],
                    },
                    {"role": "external", "landing_path": "/react/client"},
                )

                projects = client.get("/api/client/projects")
                self.assertEqual(projects.status_code, 200, projects.text)
                visible_project = projects.json()["projects"][0]
                self.assertEqual(
                    visible_project["branding"]["display_name"],
                    "Legacy published project",
                )

                publications = client.get(
                    f"/api/client/projects/{visible_project['id']}/publications"
                )
                self.assertEqual(publications.status_code, 200, publications.text)
                self.assertEqual(
                    [item["public_title"] for item in publications.json()["publications"]],
                    ["Legacy January publication"],
                )
                self.assertEqual(visible_project["id"], project_id)

                consoles = client.get("/api/console")
                self.assertEqual(consoles.status_code, 200, consoles.text)
                self.assertEqual(consoles.json()["consoles"], [])
                self.assertEqual(
                    client.get(f"/api/console/{console_id}").status_code,
                    404,
                )
            finally:
                store.close()

    def _write_pre_cutover_fixture(
        self,
        database_url: str,
        database_path: Path,
        artifact_root: Path,
    ) -> tuple[int, int]:
        store = AnalystStore(database_url)
        try:
            analyst = store.create_user(
                email="analyst@example.local",
                display_name="Analyst",
                role="analyst",
                password_hash=hash_password("analyst pass"),
            )
            external = store.create_user(
                email="legacy-client@example.local",
                display_name="Legacy Client",
                role="external",
                password_hash=hash_password("client pass"),
            )
            run = create_completed_run_with_result_artifacts(store, artifact_root)
            lineage = store.get_run_lineage(run["id"])
            project_id = int(lineage["project_id"])
            store.connection.execute(
                "UPDATE projects SET name = ? WHERE id = ?",
                ("Legacy published project", project_id),
            )
            store.connection.commit()
            store.set_external_project_access(
                project_id=project_id,
                user_id=external["id"],
                portal_view=True,
                operate=False,
                updated_by="legacy-admin@example.local",
            )
            template = store.create_dashboard_template(
                project_id=project_id,
                name="Legacy dashboard",
                created_by="analyst@example.local",
            )
            publication = store.create_publication_draft(
                run_id=run["id"],
                dashboard_template_id=template["id"],
                public_title="Legacy January publication",
                created_by="analyst@example.local",
            )
            store.publish_publication(
                publication["id"], published_by="analyst@example.local"
            )
            case = store.get_or_create_case_for_scenario(int(lineage["scenario_id"]))
            source_variant = store.get_or_create_default_input_variant(case["id"])
            console = store.create_operator_console(
                case_id=case["id"],
                source_variant_id=source_variant["id"],
                document=EMPTY_CONSOLE_DOCUMENT,
                created_by_user_id=analyst["id"],
            )
            console = store.save_operator_console(
                console["id"],
                document=EMPTY_CONSOLE_DOCUMENT,
                status="active",
                expected_revision=1,
                updated_by_user_id=analyst["id"],
            )
        finally:
            store.close()

        connection = sqlite3.connect(database_path)
        try:
            connection.execute("PRAGMA foreign_keys = OFF")
            connection.executescript(
                """
                CREATE TABLE legacy_users (
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
                INSERT INTO legacy_users
                SELECT id, email, display_name,
                       CASE WHEN role = 'external' THEN 'client' ELSE role END,
                       password_hash, is_active, created_at, updated_at,
                       created_by, deactivated_at
                FROM users;
                DROP TABLE users;
                ALTER TABLE legacy_users RENAME TO users;

                CREATE TABLE legacy_project_client_access (
                    project_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    assigned_at TEXT NOT NULL,
                    assigned_by TEXT NOT NULL,
                    PRIMARY KEY (project_id, user_id),
                    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                );
                INSERT INTO legacy_project_client_access
                SELECT project_id, user_id, assigned_at, assigned_by
                FROM project_client_access;
                DROP TABLE project_client_access;
                ALTER TABLE legacy_project_client_access RENAME TO project_client_access;
                """
            )
            connection.execute(
                "DELETE FROM schema_migrations WHERE name = ?",
                (PORTAL_CONFIGURATION_MIGRATION,),
            )
            connection.commit()
        finally:
            connection.close()

        return project_id, int(console["id"])


class ConfigurationLayerCapabilityAcceptanceTests(unittest.TestCase):
    """The two project capabilities stay independent on every request."""

    def setUp(self):
        self.store = AnalystStore("sqlite:///:memory:")
        self.store.create_user(
            email="admin@example.local",
            display_name="Adela Admin",
            role="admin",
            password_hash=hash_password("admin pass"),
        )
        self.admin = TestClient(create_app(store=self.store, auth_enabled=True))
        login = login_json_with_csrf(
            self.admin, "admin@example.local", "admin pass"
        )
        self.assertEqual(login.status_code, 200, login.text)
        self.project = post_json_with_csrf(
            self.admin,
            "/api/projects",
            {"name": "Proyecto con dos superficies", "description": ""},
        ).json()
        scenario = self.store.create_scenario(
            project_id=self.project["id"], name="Operacion configurable"
        )
        case = self.store.get_or_create_case_for_scenario(scenario["id"])
        variant = self.store.get_or_create_default_input_variant(case["id"])
        analyst = self.store.create_user(
            email="analyst@example.local",
            display_name="Ana Analista",
            role="analyst",
            password_hash=hash_password("analyst pass"),
        )
        console = self.store.create_operator_console(
            case_id=case["id"],
            source_variant_id=variant["id"],
            document=EMPTY_CONSOLE_DOCUMENT,
            created_by_user_id=analyst["id"],
        )
        self.console = self.store.save_operator_console(
            console["id"],
            document=EMPTY_CONSOLE_DOCUMENT,
            status="active",
            expected_revision=1,
            updated_by_user_id=analyst["id"],
        )

    def tearDown(self):
        self.store.close()

    def create_external(self, name: str, *, portal_view: bool, operate: bool):
        email = f"{name}@example.local"
        password = f"{name} pass"
        created = post_json_with_csrf(
            self.admin,
            "/api/admin/users",
            {
                "email": email,
                "display_name": name.title(),
                "role": "external",
                "password": password,
            },
        )
        self.assertEqual(created.status_code, 201, created.text)
        user = created.json()["user"]
        access_path = (
            f"/api/admin/projects/{self.project['id']}/external-access/{user['id']}"
        )
        granted = put_json_with_csrf(
            self.admin,
            access_path,
            {"portal_view": portal_view, "operate": operate},
        )
        self.assertEqual(granted.status_code, 200, granted.text)
        session = TestClient(create_app(store=self.store, auth_enabled=True))
        login = login_json_with_csrf(session, email, password)
        self.assertEqual(login.status_code, 200, login.text)
        return user, session, login.json(), access_path

    def test_capabilities_are_independent_revocable_and_choose_one_landing_root(self):
        _, viewer, viewer_login, _ = self.create_external(
            "viewer", portal_view=True, operate=False
        )
        _, operator, operator_login, _ = self.create_external(
            "operator", portal_view=False, operate=True
        )
        _, both, both_login, both_access_path = self.create_external(
            "both", portal_view=True, operate=True
        )
        _, neither, neither_login, _ = self.create_external(
            "neither", portal_view=False, operate=False
        )

        self.assertEqual(viewer_login["landing_path"], "/react/client")
        self.assertEqual(
            operator_login["landing_path"],
            f"/react/console/{self.console['id']}",
        )
        self.assertEqual(
            both_login["landing_path"],
            f"/react/console/{self.console['id']}",
        )
        self.assertEqual(neither_login["landing_path"], "/react/client")
        for session, login in (
            (viewer, viewer_login),
            (operator, operator_login),
            (both, both_login),
            (neither, neither_login),
        ):
            me = session.get("/api/auth/me")
            self.assertEqual(me.status_code, 200, me.text)
            self.assertEqual(me.json()["landing_path"], login["landing_path"])
            self.assertEqual(session.get("/api/projects").status_code, 404)

        self.assertEqual(viewer.get("/api/client/projects").status_code, 200)
        self.assertEqual(
            viewer.get(f"/api/console/{self.console['id']}").status_code, 404
        )
        self.assertEqual(operator.get("/api/client/projects").status_code, 404)
        self.assertEqual(
            operator.get(f"/api/console/{self.console['id']}").status_code, 200
        )
        self.assertEqual(both.get("/api/client/projects").status_code, 200)
        self.assertEqual(
            both.get(f"/api/console/{self.console['id']}").status_code, 200
        )
        self.assertEqual(neither.get("/api/client/projects").status_code, 404)
        self.assertEqual(
            neither.get(f"/api/console/{self.console['id']}").status_code, 404
        )

        safe_next = login_json_with_csrf(
            both,
            "both@example.local",
            "both pass",
            f"/react/client/projects/{self.project['id']}",
        )
        self.assertEqual(
            safe_next.json()["landing_path"],
            f"/react/client/projects/{self.project['id']}",
        )

        portal_only = put_json_with_csrf(
            self.admin,
            both_access_path,
            {"portal_view": True, "operate": False},
        )
        self.assertEqual(portal_only.status_code, 200, portal_only.text)
        self.assertEqual(
            both.get(f"/api/console/{self.console['id']}").status_code,
            404,
        )
        self.assertEqual(both.get("/api/console").json()["consoles"], [])
        self.assertEqual(
            both.get("/api/auth/me").json()["landing_path"], "/react/client"
        )

        revoked = delete_with_csrf(self.admin, both_access_path)
        self.assertEqual(revoked.status_code, 200, revoked.text)
        self.assertEqual(both.get("/api/client/projects").status_code, 404)


class ConfigurationLayerOperatorEditingAcceptanceTests(unittest.TestCase):
    """Operator mutations remain isolated, transactional and attributable."""

    def setUp(self):
        self.store = AnalystStore("sqlite:///:memory:")
        self.artifact_directory = tempfile.TemporaryDirectory()
        self.run_queue = RecordingRunQueue()
        self.analyst_user = self.store.create_user(
            email="analyst@example.local",
            display_name="Ana Analista",
            role="analyst",
            password_hash=hash_password("analyst pass"),
        )
        self.store.create_user(
            email="admin@example.local",
            display_name="Adela Admin",
            role="admin",
            password_hash=hash_password("admin pass"),
        )
        self.operator_user = self.store.create_user(
            email="operator@example.local",
            display_name="Olga Operadora",
            role="external",
            password_hash=hash_password("operator pass"),
        )
        self.other_operator_user = self.store.create_user(
            email="other@example.local",
            display_name="Oscar Operador",
            role="external",
            password_hash=hash_password("other pass"),
        )
        self.project = self.store.create_project(name="Planta Norte")
        self.scenario = self.store.create_scenario(
            project_id=self.project["id"], name="Operacion diaria"
        )
        self.store.create_or_replace_scenario_draft(
            scenario_id=self.scenario["id"], document=operator_draft_document()
        )
        self.case = self.store.get_or_create_case_for_scenario(self.scenario["id"])
        self.source_variant = self.store.get_or_create_default_input_variant(
            self.case["id"]
        )
        self.demand_set = import_acceptance_set(
            self.store,
            self.scenario["id"],
            name="Demanda base",
            signal_key="load_demand_mw",
            first_value=10,
        )
        self.forecast_set = import_acceptance_set(
            self.store,
            self.scenario["id"],
            name="Pronostico actualizado",
            signal_key="load_demand_mw",
            first_value=20,
        )
        self.price_set = import_acceptance_set(
            self.store,
            self.scenario["id"],
            name="Precio base",
            signal_key="import_price_usd_per_mwh",
            first_value=50,
        )
        for signal_key, time_series_set in (
            ("load_demand_mw", self.demand_set),
            ("import_price_usd_per_mwh", self.price_set),
        ):
            self.store.upsert_case_time_series_binding(
                case_input_variant_id=self.source_variant["id"],
                signal_key=signal_key,
                time_series_set_id=time_series_set["id"],
            )
        document = operator_acceptance_document(
            demand_set_id=self.demand_set["id"],
            forecast_set_id=self.forecast_set["id"],
            price_set_id=self.price_set["id"],
        )
        console = self.store.create_operator_console(
            case_id=self.case["id"],
            source_variant_id=self.source_variant["id"],
            document=document,
            created_by_user_id=self.analyst_user["id"],
        )
        self.console = self.store.save_operator_console(
            console["id"],
            document=document,
            status="active",
            expected_revision=1,
            updated_by_user_id=self.analyst_user["id"],
        )
        for user in (self.operator_user, self.other_operator_user):
            self.store.set_external_project_access(
                project_id=self.project["id"],
                user_id=user["id"],
                portal_view=False,
                operate=True,
                updated_by="admin@example.local",
            )
        self.app = create_app(
            validation_service=StubValidationService(),
            store=self.store,
            auth_enabled=True,
            run_queue=self.run_queue,
            artifact_root=Path(self.artifact_directory.name),
        )
        self.analyst = self.logged_in_client(
            "analyst@example.local", "analyst pass"
        )
        self.operator = self.logged_in_client(
            "operator@example.local", "operator pass"
        )
        self.other_operator = self.logged_in_client(
            "other@example.local", "other pass"
        )
        self.range = {
            "start": self.demand_set["horizon"]["start"],
            "end": self.demand_set["horizon"]["end"],
            "granularity": "full_horizon",
        }
        self.values_path = (
            f"/api/console/{self.console['id']}/groups/operacion/values"
        )
        self.lease_path = (
            f"/api/console/{self.console['id']}/groups/operacion/lease"
        )

    def tearDown(self):
        self.store.close()
        self.artifact_directory.cleanup()

    def logged_in_client(self, email: str, password: str) -> TestClient:
        client = TestClient(self.app)
        response = login_json_with_csrf(client, email, password)
        self.assertEqual(response.status_code, 200, response.text)
        return client

    def load_values(self, client: TestClient) -> object:
        response = client.get(self.values_path, params=self.range)
        self.assertEqual(response.status_code, 200, response.text)
        return response

    def save_values(
        self,
        client: TestClient,
        *,
        cells: list[dict],
        etag: str,
        lease_token: str,
    ):
        headers = csrf_headers(client)
        headers["If-Match"] = etag
        return client.put(
            self.values_path,
            json={
                "range_start": self.range["start"],
                "range_end": self.range["end"],
                "granularity": self.range["granularity"],
                "lease_token": lease_token,
                "note": "Ajuste conjunto de aceptacion",
                "cells": cells,
            },
            headers=headers,
        )

    @staticmethod
    def column_values(payload: dict, column_id: str) -> list[float]:
        return [row["values"][column_id] for row in payload["group_values"]["rows"]]

    def canonical_values(self, time_series_set: dict, signal_key: str) -> list[float]:
        response = self.analyst.get(
            f"/api/projects/{self.project['id']}/time-series-sets/"
            f"{time_series_set['id']}"
        )
        self.assertEqual(response.status_code, 200, response.text)
        values = response.json()["time_series_set"]["values"]
        return [
            value["value_numeric"]
            for value in values
            if value["signal_key"] == signal_key
        ]

    def test_operator_edits_are_isolated_atomic_concurrent_and_auditable(self):
        initial_internal = self.analyst.get(
            f"/api/scenarios/{self.scenario['id']}/consoles/{self.console['id']}"
        ).json()["operator_console"]
        self.assertEqual(initial_internal["series_copies"], [])
        switched = put_json_with_csrf(
            self.operator,
            f"/api/console/{self.console['id']}/series-selections",
            {
                "selections": [
                    {
                        "group_id": "operacion",
                        "column_id": "demanda",
                        "source_option_id": "forecast",
                    }
                ]
            },
        )
        self.assertEqual(switched.status_code, 200, switched.text)
        self.assertEqual(
            switched.json()["selections"][0]["selected_source_option_id"],
            "forecast",
        )
        for forbidden in (
            "time_series_set_id",
            "copy_id",
            "origin_set_id",
            "signal_key",
        ):
            self.assertNotIn(forbidden, switched.text)
        after_switch = self.analyst.get(
            f"/api/scenarios/{self.scenario['id']}/consoles/{self.console['id']}"
        ).json()["operator_console"]
        self.assertEqual(len(after_switch["series_copies"]), 1)

        loaded = self.load_values(self.operator)
        self.assertEqual(
            self.column_values(loaded.json(), "demanda"),
            [20.0, 21.0, 22.0, 23.0],
        )
        self.assertEqual(
            self.column_values(loaded.json(), "precio"),
            [50.0, 51.0, 52.0, 53.0],
        )
        lease = post_json_with_csrf(self.operator, self.lease_path)
        self.assertEqual(lease.status_code, 200, lease.text)
        lease_token = lease.json()["lease"]["token"]
        heartbeat = put_json_with_csrf(
            self.operator, self.lease_path, {"lease_token": lease_token}
        )
        self.assertEqual(heartbeat.status_code, 200, heartbeat.text)
        self.assertEqual(heartbeat.json()["lease"]["holder_name"], "Olga Operadora")

        self.assertEqual(self.load_values(self.other_operator).status_code, 200)
        blocked_lease = post_json_with_csrf(self.other_operator, self.lease_path)
        self.assertEqual(blocked_lease.status_code, 409, blocked_lease.text)

        invalid = self.save_values(
            self.operator,
            cells=[
                {"column_id": "demanda", "row_index": 1, "value": -5},
                {"column_id": "precio", "row_index": 2, "value": 77},
            ],
            etag=loaded.headers["etag"],
            lease_token=lease_token,
        )
        self.assertEqual(invalid.status_code, 400, invalid.text)
        self.assertEqual(invalid.json()["save_error"]["total_cells"], 1)
        unchanged = self.load_values(self.operator)
        self.assertEqual(
            (
                self.column_values(unchanged.json(), "demanda"),
                self.column_values(unchanged.json(), "precio"),
            ),
            ([20.0, 21.0, 22.0, 23.0], [50.0, 51.0, 52.0, 53.0]),
        )

        saved = self.save_values(
            self.operator,
            cells=[
                {"column_id": "demanda", "row_index": 1, "value": 99.5},
                {"column_id": "precio", "row_index": 2, "value": 77},
            ],
            etag=loaded.headers["etag"],
            lease_token=lease_token,
        )
        self.assertEqual(saved.status_code, 200, saved.text)
        self.assertEqual(
            (
                self.column_values(saved.json(), "demanda"),
                self.column_values(saved.json(), "precio"),
            ),
            ([20.0, 99.5, 22.0, 23.0], [50.0, 51.0, 77.0, 53.0]),
        )
        after_save = self.analyst.get(
            f"/api/scenarios/{self.scenario['id']}/consoles/{self.console['id']}"
        ).json()["operator_console"]
        self.assertEqual(len(after_save["series_copies"]), 2)
        self.assertEqual(
            self.canonical_values(self.forecast_set, "load_demand_mw"),
            [20.0, 21.0, 22.0, 23.0],
        )
        self.assertEqual(
            self.canonical_values(self.price_set, "import_price_usd_per_mwh"),
            [50.0, 51.0, 52.0, 53.0],
        )

        stale = self.save_values(
            self.operator,
            cells=[{"column_id": "demanda", "row_index": 0, "value": 88}],
            etag=loaded.headers["etag"],
            lease_token=lease_token,
        )
        self.assertEqual(stale.status_code, 412, stale.text)
        contended_save = self.save_values(
            self.other_operator,
            cells=[{"column_id": "demanda", "row_index": 0, "value": 88}],
            etag=saved.headers["etag"],
            lease_token=lease_token,
        )
        self.assertEqual(contended_save.status_code, 409, contended_save.text)

        history = self.operator.get(
            f"/api/console/{self.console['id']}/groups/operacion/history"
        )
        self.assertEqual(history.status_code, 200, history.text)
        latest_history = history.json()["history"][0]
        self.assertEqual(latest_history["actor"], "Olga Operadora")
        self.assertEqual(latest_history["cell_count"], 2)
        self.assertEqual(
            {(item["column_id"], item["row_index"]) for item in latest_history["comparison"]},
            {("demanda", 1), ("precio", 2)},
        )

        undo_headers = csrf_headers(self.operator)
        undo_headers["If-Match"] = saved.headers["etag"]
        undone = self.operator.post(
            f"/api/console/{self.console['id']}/groups/operacion/undo",
            json={"lease_token": lease_token},
            headers=undo_headers,
        )
        self.assertEqual(undone.status_code, 200, undone.text)
        self.assertEqual(
            (
                self.column_values(undone.json(), "demanda"),
                self.column_values(undone.json(), "precio"),
            ),
            ([20.0, 21.0, 22.0, 23.0], [50.0, 51.0, 52.0, 53.0]),
        )
        released = delete_with_csrf(
            self.operator, f"{self.lease_path}?lease_token={lease_token}"
        )
        self.assertEqual(released.status_code, 204, released.text)

        detail = self.analyst.get(
            f"/api/scenarios/{self.scenario['id']}/consoles/{self.console['id']}"
        ).json()["operator_console"]
        demand_copy = next(
            copy
            for copy in detail["series_copies"]
            if copy["origin"]["name"] == "Pronostico actualizado"
        )
        restored = post_json_with_csrf(
            self.analyst,
            (
                f"/api/scenarios/{self.scenario['id']}/consoles/{self.console['id']}"
                f"/restore-series/{demand_copy['id']}"
            ),
            {
                "revision_number": 2,
                "expected_current_revision": demand_copy["current_revision"],
                "note": "Restaurar ajuste operativo aprobado",
            },
        )
        self.assertEqual(restored.status_code, 200, restored.text)
        self.assertEqual(
            restored.json()["restored"]["revision_number"],
            demand_copy["current_revision"] + 1,
        )
        operator_values = self.load_values(self.operator).json()
        self.assertEqual(
            self.column_values(operator_values, "demanda"),
            [20.0, 99.5, 22.0, 23.0],
        )

    def test_parameter_override_changes_only_the_immutable_effective_run(self):
        parameter_document = {
            **operator_acceptance_document(
                demand_set_id=self.demand_set["id"],
                forecast_set_id=self.forecast_set["id"],
                price_set_id=self.price_set["id"],
            ),
            "groups": [],
        }

        def create_parameter_console(name: str) -> dict:
            document = {
                **parameter_document,
                "public_identity": {
                    "name": name,
                    "description": "Control aislado de parametros",
                },
            }
            created = self.store.create_operator_console(
                case_id=self.case["id"],
                source_variant_id=self.source_variant["id"],
                document=document,
                created_by_user_id=self.analyst_user["id"],
            )
            return self.store.save_operator_console(
                created["id"],
                document=document,
                status="active",
                expected_revision=1,
                updated_by_user_id=self.analyst_user["id"],
            )

        control_console = create_parameter_console("Control sin override")
        override_console = create_parameter_console("Control con override")
        for console in (control_console, override_console):
            validated = post_json_with_csrf(
                self.analyst,
                (
                    f"/api/scenarios/{self.scenario['id']}/case/variants/"
                    f"{console['owned_variant_id']}/validate"
                ),
                {
                    "range_start": self.range["start"],
                    "range_end": self.range["end"],
                },
            )
            self.assertEqual(validated.status_code, 200, validated.text)

        control_run_response = post_json_with_csrf(
            self.operator,
            f"/api/console/{control_console['id']}/runs",
            {
                "range_start": self.range["start"],
                "range_end": self.range["end"],
            },
        )
        self.assertEqual(control_run_response.status_code, 201, control_run_response.text)
        override = put_json_with_csrf(
            self.operator,
            f"/api/console/{override_console['id']}/parameters",
            {"parameters": [{"id": "potencia_bess", "value": 6.5}]},
        )
        self.assertEqual(override.status_code, 200, override.text)
        overridden_run_response = post_json_with_csrf(
            self.operator,
            f"/api/console/{override_console['id']}/runs",
            {
                "range_start": self.range["start"],
                "range_end": self.range["end"],
            },
        )
        self.assertEqual(
            overridden_run_response.status_code, 201, overridden_run_response.text
        )

        control_public_run = control_run_response.json()["run"]
        overridden_public_run = overridden_run_response.json()["run"]
        control_run = self.analyst.get(
            f"/api/runs/{control_public_run['id']}"
        ).json()["run"]
        overridden_run = self.analyst.get(
            f"/api/runs/{overridden_public_run['id']}"
        ).json()["run"]
        control_version = self.analyst.get(
            f"/api/scenario-versions/{control_run['scenario_version_id']}"
        ).json()["scenario_version"]
        overridden_version = self.analyst.get(
            f"/api/scenario-versions/{overridden_run['scenario_version_id']}"
        ).json()["scenario_version"]

        def battery_power(version: dict) -> float:
            battery = next(
                node
                for node in version["system_case_json"]["nodes"]
                if node["id"] == "battery_1"
            )
            return battery["charge_power_max_mw"]

        self.assertEqual(battery_power(control_version), 4.0)
        self.assertEqual(battery_power(overridden_version), 6.5)
        self.assertEqual(
            control_version["generation_metadata"]["parameters"]["content_hash"],
            overridden_version["generation_metadata"]["parameters"]["content_hash"],
        )
        self.assertEqual(
            control_version["generation_metadata"]["parameter_overrides"], []
        )
        self.assertEqual(
            overridden_version["generation_metadata"]["parameter_overrides"],
            [{"id": "potencia_bess", "value": 6.5}],
        )
        self.assertEqual(
            {
                "email": overridden_run["triggered_by"],
                "name": overridden_run["triggered_by_display_name"],
                "console_id": overridden_run["operator_console_id"],
                "console_revision": overridden_run["operator_console_revision"],
            },
            {
                "email": "operator@example.local",
                "name": "Olga Operadora",
                "console_id": override_console["id"],
                "console_revision": override_console["revision"],
            },
        )
        draft = self.analyst.get(
            f"/api/scenarios/{self.scenario['id']}/draft"
        ).json()["draft"]["document"]
        self.assertEqual(draft["assets"][0]["charge_power_max_mw"], 4.0)

        changed_again = put_json_with_csrf(
            self.operator,
            f"/api/console/{override_console['id']}/parameters",
            {"parameters": [{"id": "potencia_bess", "value": 7.5}]},
        )
        self.assertEqual(changed_again.status_code, 200, changed_again.text)
        immutable_version = self.analyst.get(
            f"/api/scenario-versions/{overridden_run['scenario_version_id']}"
        ).json()["scenario_version"]
        self.assertEqual(battery_power(immutable_version), 6.5)
        self.assertEqual(
            self.run_queue.enqueued_run_ids,
            [control_public_run["id"], overridden_public_run["id"]],
        )

    def test_configured_results_comparison_and_failures_share_one_safe_boundary(self):
        results_document = {
            **operator_acceptance_document(
                demand_set_id=self.demand_set["id"],
                forecast_set_id=self.forecast_set["id"],
                price_set_id=self.price_set["id"],
            ),
            "parameters": [],
            "groups": [],
            "results": {
                "kpis": [
                    {
                        "id": "beneficio_total",
                        "path": "objective_value_usd",
                        "label": "Beneficio total",
                        "unit": "USD",
                        "decimals": 1,
                        "sign": "auto",
                        "emphasis": "strong",
                    }
                ],
                "charts": [],
                "tables": [],
            },
        }

        def create_results_console(name: str) -> dict:
            document = {
                **results_document,
                "public_identity": {
                    "name": name,
                    "description": "Resultados configurados",
                },
            }
            created = self.store.create_operator_console(
                case_id=self.case["id"],
                source_variant_id=self.source_variant["id"],
                document=document,
                created_by_user_id=self.analyst_user["id"],
            )
            return self.store.save_operator_console(
                created["id"],
                document=document,
                status="active",
                expected_revision=1,
                updated_by_user_id=self.analyst_user["id"],
            )

        def queued_run(console: dict, display_name: str = "Olga Operadora") -> dict:
            version = self.store.create_scenario_version(
                scenario_id=self.scenario["id"],
                system_case_json={
                    "schema_version": "bess_system_dispatch.v2",
                    "case_name": "configured_results_case",
                    "nodes": [],
                    "edges": [],
                    "time_series": [],
                },
                validation_payload={"status": "ok"},
            )
            return self.store.create_run(
                scenario_version_id=version["id"],
                triggered_by="operator@example.local",
                trigger_type="operator_console",
                triggered_by_user_id=self.operator_user["id"],
                triggered_by_display_name=display_name,
                operator_console_id=console["id"],
                operator_console_revision=console["revision"],
            )

        def succeeded_run(
            console: dict, *, objective: float, display_name: str
        ) -> dict:
            run = queued_run(console, display_name)
            output_dir = (
                Path(self.artifact_directory.name)
                / "runs"
                / str(run["id"])
                / "outputs"
            )
            output_dir.mkdir(parents=True)
            summary_path = output_dir / "summary.json"
            dispatch_path = output_dir / "dispatch.csv"
            asset_dispatch_path = output_dir / "asset_dispatch.csv"
            summary_path.write_text(
                json.dumps(
                    {
                        "objective_value_usd": objective,
                        "case_name": "PRIVATE-CASE-NAME",
                        "workspace_path": "C:/private/server/workspace",
                        "all_series": [1, 2, 3],
                        "unknown_secret": "PRIVATE-UNKNOWN-SUMMARY",
                    }
                ),
                encoding="utf-8",
            )
            dispatch_path.write_text(
                "timestamp,grid_import_mw,source_identifiers\n"
                "2026-01-01T00:00:00,2.5,PRIVATE-SOURCE-ID\n",
                encoding="utf-8",
            )
            asset_dispatch_path.write_text(
                "timestamp,asset_id,asset_type\n"
                "2026-01-01T00:00:00,grid_1,grid\n",
                encoding="utf-8",
            )
            self.store.mark_run_running(
                run["id"],
                workspace_path=str(output_dir.parent),
                input_snapshot_path=str(
                    output_dir.parent / "input" / "system_case.json"
                ),
            )
            self.store.mark_run_succeeded(
                run["id"],
                exit_code=0,
                stdout="PRIVATE-STDOUT",
                stderr="PRIVATE-STDERR",
                success_payload={"schema_version": "private"},
                output_dir=str(output_dir),
                summary_path=str(summary_path),
            )
            for artifact_type, path, media_type in (
                ("summary_json", summary_path, "application/json"),
                ("dispatch_csv", dispatch_path, "text/csv"),
                ("asset_dispatch_csv", asset_dispatch_path, "text/csv"),
            ):
                self.store.register_run_artifact(
                    run_id=run["id"],
                    artifact_type=artifact_type,
                    path=str(path),
                    display_name=path.name,
                    media_type=media_type,
                )
            return self.store.get_run(run["id"])

        console = create_results_console("Comparacion segura")
        left = succeeded_run(console, objective=1000.0, display_name="Olga Operadora")
        right = succeeded_run(
            console, objective=1250.5, display_name="Pedro Operador"
        )
        detail = self.operator.get(
            f"/api/console/{console['id']}/runs/{left['id']}"
        )
        self.assertEqual(detail.status_code, 200, detail.text)
        self.assertEqual(
            detail.json()["results_block"]["kpis"],
            [
                {
                    "id": "beneficio_total",
                    "label": "Beneficio total",
                    "value": 1000.0,
                    "unit": "USD",
                    "decimals": 1,
                    "sign": "auto",
                    "emphasis": "strong",
                }
            ],
        )
        internal_results = self.analyst.get(
            f"/api/runs/{left['id']}/results"
        )
        self.assertEqual(internal_results.status_code, 200, internal_results.text)
        self.assertEqual(
            internal_results.json()["results"]["summary"]["objective_value_usd"],
            detail.json()["results_block"]["kpis"][0]["value"],
        )

        comparison = self.operator.get(
            f"/api/console/{console['id']}/run-comparison",
            params={"left": left["id"], "right": right["id"]},
        )
        self.assertEqual(comparison.status_code, 200, comparison.text)
        self.assertEqual(
            comparison.json()["kpi_differences"],
            [
                {
                    "id": "beneficio_total",
                    "label": "Beneficio total",
                    "unit": "USD",
                    "decimals": 1,
                    "left": 1000.0,
                    "right": 1250.5,
                    "difference": 250.5,
                }
            ],
        )
        self.assertEqual(
            comparison.json()["right"]["run"]["triggered_by"], "Pedro Operador"
        )
        for forbidden in (
            "scenario_version_id",
            "operator_console_revision",
            "workspace_path",
            "input_snapshot_path",
            "PRIVATE-CASE-NAME",
            "PRIVATE-UNKNOWN-SUMMARY",
            "PRIVATE-SOURCE-ID",
            "PRIVATE-STDOUT",
            "PRIVATE-STDERR",
            "all_series",
            "objective_value_usd",
            str(Path(self.artifact_directory.name)),
        ):
            self.assertNotIn(forbidden, detail.text)
            self.assertNotIn(forbidden, comparison.text)

        neighbour = create_results_console("Consola vecina")
        foreign_run = succeeded_run(
            neighbour, objective=2000.0, display_name="Olga Operadora"
        )
        refused_comparison = self.operator.get(
            f"/api/console/{console['id']}/run-comparison",
            params={"left": left["id"], "right": foreign_run["id"]},
        )
        self.assertEqual(refused_comparison.status_code, 404)
        self.assertEqual(self.operator.get(f"/api/runs/{left['id']}").status_code, 404)

        failed = queued_run(console)
        self.store.mark_run_running(
            failed["id"],
            workspace_path="C:/private/failed-run",
            input_snapshot_path="C:/private/failed-run/input/system_case.json",
        )
        self.store.mark_run_failed(
            failed["id"],
            exit_code=17,
            stdout="PRIVATE JULIA STDOUT",
            stderr="PRIVATE JULIA STACK TRACE",
            error_payload={"message": "Julia exploded at C:/private/model.jl"},
            error_message="Julia exploded at C:/private/model.jl",
            stdout_log_path="C:/private/stdout.log",
            stderr_log_path="C:/private/stderr.log",
        )
        failed_detail = self.operator.get(
            f"/api/console/{console['id']}/runs/{failed['id']}"
        )
        self.assertEqual(failed_detail.status_code, 200, failed_detail.text)
        self.assertEqual(
            failed_detail.json()["failure"],
            {
                "cause": "ejecucion_fallida",
                "message": "La ejecucion fallo. Comunica la referencia al ingeniero.",
                "reference": str(failed["id"]),
            },
        )
        self.assertIsNone(failed_detail.json()["results_block"])
        for forbidden in (
            "stdout",
            "stderr",
            "exit_code",
            "C:/private",
            "Julia exploded",
            "PRIVATE JULIA",
        ):
            self.assertNotIn(forbidden, failed_detail.text)
        unavailable_comparison = self.operator.get(
            f"/api/console/{console['id']}/run-comparison",
            params={"left": left["id"], "right": failed["id"]},
        )
        self.assertEqual(unavailable_comparison.status_code, 200)
        self.assertEqual(
            unavailable_comparison.json()["right"]["results_state"], "unavailable"
        )
        self.assertEqual(unavailable_comparison.json()["kpi_differences"], [])


class ConfigurationLayerRecoveryAcceptanceTests(unittest.TestCase):
    """Own edits stay live; external changes require the matching recovery."""

    def setUp(self):
        self.store = AnalystStore("sqlite:///:memory:")
        self.artifact_directory = tempfile.TemporaryDirectory()
        self.run_queue = RecordingRunQueue()
        self.analyst_user = self.store.create_user(
            email="analyst@example.local",
            display_name="Ana Analista",
            role="analyst",
            password_hash=hash_password("analyst pass"),
        )
        self.operator_user = self.store.create_user(
            email="operator@example.local",
            display_name="Olga Operadora",
            role="external",
            password_hash=hash_password("operator pass"),
        )
        self.project = self.store.create_project(name="Planta Norte")
        self.scenario = self.store.create_scenario(
            project_id=self.project["id"], name="Operacion diaria"
        )
        self.store.create_or_replace_scenario_draft(
            scenario_id=self.scenario["id"], document=CASE_DRAFT_DOCUMENT
        )
        case = self.store.get_or_create_case_for_scenario(self.scenario["id"])
        source_variant = self.store.get_or_create_default_input_variant(case["id"])
        self.demand_set = import_recovery_demand_set(
            self.store, self.scenario["id"]
        )
        price_set = import_recovery_price_set(self.store, self.scenario["id"])
        for signal_key, entity_type, entity_id, time_series_set in (
            ("load_demand_mw", "component:load", "load_1", self.demand_set),
            ("price_usd_per_mwh", "grid", "grid_1", price_set),
        ):
            self.store.upsert_case_time_series_binding(
                case_input_variant_id=source_variant["id"],
                signal_key=signal_key,
                entity_type=entity_type,
                entity_id=entity_id,
                time_series_set_id=time_series_set["id"],
            )
        self.store.set_external_project_access(
            project_id=self.project["id"],
            user_id=self.operator_user["id"],
            portal_view=False,
            operate=True,
            updated_by="admin@example.local",
        )

        def create_console(pointer_field: str) -> dict:
            document = recovery_console_document(
                self.demand_set["id"], pointer_field=pointer_field
            )
            created = self.store.create_operator_console(
                case_id=case["id"],
                source_variant_id=source_variant["id"],
                document=document,
                created_by_user_id=self.analyst_user["id"],
            )
            active = self.store.save_operator_console(
                created["id"],
                document=document,
                status="active",
                expected_revision=created["revision"],
                updated_by_user_id=self.analyst_user["id"],
            )
            self.store.validate_case_input_variant(
                scenario_id=self.scenario["id"],
                case_input_variant_id=active["owned_variant_id"],
                range_start=self.demand_set["horizon"]["start"],
                range_end=self.demand_set["horizon"]["end"],
            )
            return active

        self.console = create_console("discharge_power_max_mw")
        self.broken_console = create_console("inexistent_field")
        self.app = create_app(
            validation_service=StubValidationService(),
            store=self.store,
            auth_enabled=True,
            run_queue=self.run_queue,
            artifact_root=Path(self.artifact_directory.name),
        )
        self.analyst = self.logged_in_client(
            "analyst@example.local", "analyst pass"
        )
        self.operator = self.logged_in_client(
            "operator@example.local", "operator pass"
        )
        self.range = {
            "start": self.demand_set["horizon"]["start"],
            "end": self.demand_set["horizon"]["end"],
            "granularity": "full_horizon",
        }

    def tearDown(self):
        self.store.close()
        self.artifact_directory.cleanup()

    def logged_in_client(self, email: str, password: str) -> TestClient:
        client = TestClient(self.app)
        response = login_json_with_csrf(client, email, password)
        self.assertEqual(response.status_code, 200, response.text)
        return client

    def test_external_changes_fail_closed_until_the_matching_engineer_action(self):
        values_path = (
            f"/api/console/{self.console['id']}/groups/potencia/values"
        )
        lease_path = (
            f"/api/console/{self.console['id']}/groups/potencia/lease"
        )
        loaded = self.operator.get(values_path, params=self.range)
        self.assertEqual(loaded.status_code, 200, loaded.text)
        lease = post_json_with_csrf(self.operator, lease_path)
        self.assertEqual(lease.status_code, 200, lease.text)
        headers = csrf_headers(self.operator)
        headers["If-Match"] = loaded.headers["etag"]
        saved = self.operator.put(
            values_path,
            json={
                "range_start": self.range["start"],
                "range_end": self.range["end"],
                "granularity": self.range["granularity"],
                "lease_token": lease.json()["lease"]["token"],
                "note": "Cambio operativo propio",
                "cells": [
                    {"column_id": "demanda", "row_index": 0, "value": 99.5}
                ],
            },
            headers=headers,
        )
        self.assertEqual(saved.status_code, 200, saved.text)
        delete_with_csrf(
            self.operator,
            f"{lease_path}?lease_token={lease.json()['lease']['token']}",
        )
        self.assertTrue(
            self.operator.get(f"/api/console/{self.console['id']}").json()[
                "run_gate"
            ]["can_run"]
        )

        revised_origin = put_json_with_csrf(
            self.analyst,
            (
                f"/api/projects/{self.project['id']}/time-series-sets/"
                f"{self.demand_set['id']}/values"
            ),
            {
                "edits": [
                    {
                        "period_index": 0,
                        "signal_key": "load_demand_mw",
                        "value": "77.0",
                    }
                ],
                "change_summary": "Nueva revision canonica",
            },
        )
        self.assertEqual(revised_origin.status_code, 200, revised_origin.text)
        shell_with_old_origin = self.operator.get(
            f"/api/console/{self.console['id']}"
        ).json()
        self.assertTrue(shell_with_old_origin["run_gate"]["can_run"])
        internal_detail = self.analyst.get(
            f"/api/scenarios/{self.scenario['id']}/consoles/{self.console['id']}"
        ).json()["operator_console"]
        self.assertTrue(internal_detail["series_copies"][0]["origin"]["old"])

        moved = put_json_with_csrf(
            self.analyst,
            f"/api/scenarios/{self.scenario['id']}/draft",
            {"document": case_draft_with_discharge_power(6.0)},
        )
        self.assertEqual(moved.status_code, 200, moved.text)
        blocked_run = post_json_with_csrf(
            self.operator,
            f"/api/console/{self.console['id']}/runs",
            {"range_start": self.range["start"], "range_end": self.range["end"]},
        )
        self.assertEqual(blocked_run.status_code, 409, blocked_run.text)
        self.assertEqual(
            blocked_run.json()["run_gate"]["reason"], "dependencia_movida"
        )
        self.assertEqual(self.run_queue.enqueued_run_ids, [])
        self.assertEqual(
            self.analyst.get(
                f"/api/scenarios/{self.scenario['id']}/versions"
            ).json()["versions"],
            [],
        )
        self.assertEqual(
            self.analyst.get(
                f"/api/scenarios/{self.scenario['id']}/runs"
            ).json()["runs"],
            [],
        )

        normal_review = post_json_with_csrf(
            self.operator, f"/api/console/{self.console['id']}/request-review"
        )
        broken_review = post_json_with_csrf(
            self.operator,
            f"/api/console/{self.broken_console['id']}/request-review",
        )
        self.assertEqual(normal_review.status_code, 200, normal_review.text)
        self.assertEqual(broken_review.status_code, 200, broken_review.text)
        normal_wait = normal_review.json()["run_gate"]["review_requested_at"]
        broken_wait = broken_review.json()["run_gate"]["review_requested_at"]
        self.assertIsNotNone(normal_wait)
        self.assertIsNotNone(broken_wait)

        entries = self.analyst.get(
            f"/api/scenarios/{self.scenario['id']}/consoles"
        ).json()["operator_consoles"]
        normal_entry = next(item for item in entries if item["id"] == self.console["id"])
        broken_entry = next(
            item for item in entries if item["id"] == self.broken_console["id"]
        )
        self.assertEqual(
            normal_entry["blocking"]["action"]["kind"], "revalidate_variant"
        )
        self.assertEqual(
            broken_entry["blocking"]["action"],
            {
                "kind": "edit_configuration",
                "target": {
                    "section": "parameters",
                    "id": "potencia_bess",
                    "label": "Potencia maxima BESS",
                },
            },
        )

        broken_revalidated = post_json_with_csrf(
            self.analyst,
            (
                f"/api/scenarios/{self.scenario['id']}/case/variants/"
                f"{self.broken_console['owned_variant_id']}/validate"
            ),
            {"range_start": self.range["start"], "range_end": self.range["end"]},
        )
        self.assertEqual(
            broken_revalidated.status_code, 200, broken_revalidated.text
        )
        still_broken = self.analyst.get(
            f"/api/scenarios/{self.scenario['id']}/consoles"
        ).json()["operator_consoles"]
        still_broken = next(
            item for item in still_broken if item["id"] == self.broken_console["id"]
        )
        self.assertEqual(still_broken["blocking"]["reason"], "campo_no_disponible")
        self.assertEqual(still_broken["waiting_since"], broken_wait)

        corrected = put_json_with_csrf(
            self.analyst,
            (
                f"/api/scenarios/{self.scenario['id']}/consoles/"
                f"{self.broken_console['id']}"
            ),
            {
                "document": recovery_console_document(self.demand_set["id"]),
                "status": "active",
                "expected_revision": self.broken_console["revision"],
            },
        )
        self.assertEqual(corrected.status_code, 200, corrected.text)
        corrected_entry = corrected.json()["operator_console"]
        self.assertIsNone(corrected_entry["blocking"]["reason"])
        self.assertIsNone(corrected_entry["waiting_since"])

        normal_revalidated = post_json_with_csrf(
            self.analyst,
            (
                f"/api/scenarios/{self.scenario['id']}/case/variants/"
                f"{self.console['owned_variant_id']}/validate"
            ),
            {"range_start": self.range["start"], "range_end": self.range["end"]},
        )
        self.assertEqual(normal_revalidated.status_code, 200, normal_revalidated.text)
        recovered_shell = self.operator.get(
            f"/api/console/{self.console['id']}"
        ).json()
        self.assertTrue(recovered_shell["run_gate"]["can_run"])
        self.assertIsNone(recovered_shell["run_gate"]["review_requested_at"])


class ConfigurationLayerSignalCatalogAcceptanceTests(unittest.TestCase):
    """A catalog entry travels through the internal boundary by declaration."""

    def test_a_new_declarative_signal_reaches_only_the_internal_catalog_boundary(self):
        store = AnalystStore("sqlite:///:memory:")
        try:
            store.create_user(
                email="analyst@example.local",
                display_name="Ana Analista",
                role="analyst",
                password_hash=hash_password("analyst pass"),
            )
            store.create_user(
                email="operator@example.local",
                display_name="Olga Operadora",
                role="external",
                password_hash=hash_password("operator pass"),
            )
            app = create_app(store=store, auth_enabled=True)
            analyst = TestClient(app)
            external = TestClient(app)
            self.assertEqual(
                login_json_with_csrf(
                    analyst, "analyst@example.local", "analyst pass"
                ).status_code,
                200,
            )
            self.assertEqual(
                login_json_with_csrf(
                    external, "operator@example.local", "operator pass"
                ).status_code,
                200,
            )
            added = TimeSeriesSignalDefinition(
                signal_key="load_reactive_power_mvar",
                unit="MVAr",
                entity_type="component:load",
                nonnegative=False,
            )

            with mock.patch.dict(
                TIME_SERIES_SIGNAL_CATALOG,
                {"load_reactive_power_mvar": added},
            ):
                internal_response = analyst.get("/api/time-series/signal-catalog")
                external_response = external.get("/api/time-series/signal-catalog")

            self.assertEqual(internal_response.status_code, 200)
            self.assertIn(
                {
                    "signal_key": "load_reactive_power_mvar",
                    "unit": "MVAr",
                    "entity_type": "component:load",
                    "nonnegative": False,
                },
                internal_response.json()["signals"],
            )
            self.assertEqual(external_response.status_code, 404)
        finally:
            store.close()


class ConfigurationLayerPortalAcceptanceTests(unittest.TestCase):
    """Configuration and publication cross the real analyst/client boundary."""

    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.artifact_root = self.root / "artifacts"
        self.store = AnalystStore("sqlite:///:memory:")
        self.store.create_user(
            email="analyst@example.local",
            display_name="Ana Analista",
            role="analyst",
            password_hash=hash_password("analyst pass"),
        )
        self.viewer = self.store.create_user(
            email="viewer@example.local",
            display_name="Vera Cliente",
            role="external",
            password_hash=hash_password("viewer pass"),
        )
        self.store.create_user(
            email="foreign@example.local",
            display_name="Cliente Ajeno",
            role="external",
            password_hash=hash_password("foreign pass"),
        )
        self.run = create_completed_run_with_result_artifacts(
            self.store, self.artifact_root
        )
        lineage = self.store.get_run_lineage(self.run["id"])
        self.project_id = int(lineage["project_id"])
        self.store.connection.execute(
            "UPDATE projects SET name = ?, description = ? WHERE id = ?",
            (
                "Proyecto interno sin marca publica",
                "PRIVATE-PROJECT-DESCRIPTION",
                self.project_id,
            ),
        )
        self.store.connection.execute(
            "ALTER TABLE publications ADD COLUMN sensitive_note TEXT"
        )
        self.store.connection.commit()
        self.store.set_external_project_access(
            project_id=self.project_id,
            user_id=self.viewer["id"],
            portal_view=True,
            operate=False,
            updated_by="analyst@example.local",
        )
        template = self.store.create_dashboard_template(
            project_id=self.project_id,
            name="Plantilla de publicacion",
            created_by="analyst@example.local",
        )
        publication = self.store.create_publication_draft(
            run_id=self.run["id"],
            dashboard_template_id=template["id"],
            public_title="Resultado configurado de enero",
            analyst_notes="Resultado aprobado para el cliente.",
            allowed_artifact_types=["summary_json"],
            created_by="analyst@example.local",
        )
        self.publication = self.store.publish_publication(
            publication["id"], published_by="analyst@example.local"
        )
        self.store.connection.execute(
            "UPDATE publications SET sensitive_note = ? WHERE id = ?",
            ("PRIVATE-DATABASE-COLUMN", self.publication["id"]),
        )
        self.store.connection.commit()
        summary_artifact = next(
            artifact
            for artifact in self.store.list_run_artifacts(self.run["id"])
            if artifact["artifact_type"] == "summary_json"
        )
        summary_path = Path(summary_artifact["path"])
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        summary.update(
            {
                "secret_unknown": "PRIVATE-UNKNOWN-RESULT",
                "workspace_path": str(self.root / "private-server-workspace"),
            }
        )
        summary_path.write_text(json.dumps(summary), encoding="utf-8")

        self.analyst = self.logged_in_client(
            "analyst@example.local", "analyst pass"
        )
        self.external = self.logged_in_client("viewer@example.local", "viewer pass")
        self.foreign = self.logged_in_client(
            "foreign@example.local", "foreign pass"
        )

    def tearDown(self):
        self.store.close()
        self.temporary_directory.cleanup()

    def logged_in_client(self, email: str, password: str) -> TestClient:
        client = TestClient(
            create_app(
                store=self.store,
                artifact_root=self.artifact_root,
                auth_enabled=True,
            )
        )
        response = login_json_with_csrf(client, email, password)
        self.assertEqual(response.status_code, 200, response.text)
        return client

    def test_active_configuration_drives_the_same_safe_branded_report_in_preview_and_portal(
        self,
    ):
        configuration_path = (
            f"/api/projects/{self.project_id}/portal-configuration"
        )
        rejected = put_json_with_csrf(
            self.analyst,
            configuration_path,
            {
                "document": {
                    **PORTAL_ACCEPTANCE_DOCUMENT,
                    "schema_version": "portal_config.v999",
                },
                "status": "active",
                "expected_revision": 0,
            },
        )
        self.assertEqual(rejected.status_code, 400, rejected.text)
        self.assertEqual(
            self.analyst.get(configuration_path).json()["portal_configuration"][
                "revision"
            ],
            0,
        )

        configured = put_json_with_csrf(
            self.analyst,
            configuration_path,
            {
                "document": PORTAL_ACCEPTANCE_DOCUMENT,
                "status": "active",
                "expected_revision": 0,
            },
        )
        self.assertEqual(configured.status_code, 200, configured.text)
        self.assertEqual(
            {
                "revision": configured.json()["portal_configuration"]["revision"],
                "updated_by": configured.json()["portal_configuration"]["updated_by"],
            },
            {"revision": 1, "updated_by": "analyst@example.local"},
        )
        logo = self.analyst.put(
            f"{configuration_path}/logo",
            data={"expected_revision": "1"},
            files={
                "logo": (
                    "cliente.png",
                    b"\x89PNG\r\n\x1a\nacceptance-logo",
                    "image/png",
                )
            },
            headers=csrf_headers(self.analyst),
        )
        self.assertEqual(logo.status_code, 200, logo.text)
        self.assertEqual(logo.json()["portal_configuration"]["revision"], 2)

        preview = self.analyst.get(
            f"/api/publications/{self.publication['id']}/preview"
        )
        portal = self.external.get(
            f"/api/client/projects/{self.project_id}/publications/"
            f"{self.publication['id']}"
        )
        self.assertEqual(preview.status_code, 200, preview.text)
        self.assertEqual(portal.status_code, 200, portal.text)
        preview_body = preview.json()
        portal_body = portal.json()
        self.assertEqual(
            self._presentation_without_context_urls(preview_body),
            self._presentation_without_context_urls(portal_body),
        )
        self.assertEqual(
            {
                "brand": portal_body["branding"]["display_name"],
                "kpis": [
                    item["label"] for item in portal_body["results_block"]["kpis"]
                ],
                "downloads": [item["label"] for item in portal_body["downloads"]],
            },
            {
                "brand": "Energia Cliente Norte",
                "kpis": ["Beneficio total"],
                "downloads": ["summary.json"],
            },
        )

        for surface in (preview_body, portal_body):
            serialized = json.dumps(surface)
            for forbidden in (
                "PRIVATE-PROJECT-DESCRIPTION",
                "PRIVATE-DATABASE-COLUMN",
                "PRIVATE-UNKNOWN-RESULT",
                str(self.root),
                "objective_value_usd",
                "workspace_path",
                "BESS Workspace",
                '"Z"',
            ):
                self.assertNotIn(forbidden, serialized)

        logo_response = self.external.get(
            f"/api/client/projects/{self.project_id}/branding/logo"
        )
        self.assertEqual(logo_response.status_code, 200, logo_response.text)
        self.assertEqual(logo_response.content, b"\x89PNG\r\n\x1a\nacceptance-logo")
        self.assertIn("etag", logo_response.headers)

        download = self.external.get(portal_body["downloads"][0]["download_url"])
        self.assertEqual(download.status_code, 200, download.text)
        self.assertEqual(download.headers["content-type"], "application/json")

        foreign_detail = self.foreign.get(
            f"/api/client/projects/{self.project_id}/publications/"
            f"{self.publication['id']}"
        )
        foreign_logo = self.foreign.get(
            f"/api/client/projects/{self.project_id}/branding/logo"
        )
        foreign_download = self.foreign.get(
            portal_body["downloads"][0]["download_url"]
        )
        self.assertEqual(
            [
                foreign_detail.status_code,
                foreign_logo.status_code,
                foreign_download.status_code,
            ],
            [404, 404, 404],
        )

    @staticmethod
    def _presentation_without_context_urls(payload: dict) -> dict:
        comparable = deepcopy(payload)
        comparable.pop("preview_context", None)
        comparable["branding"].pop("logo_url", None)
        for download in comparable["downloads"]:
            download.pop("download_url", None)
        return comparable


class ConfigurationLayerDocumentationAcceptanceTests(unittest.TestCase):
    def test_the_closing_issue_and_report_are_complete_and_reproducible(self) -> None:
        repository_root = Path(__file__).resolve().parents[1]
        issue_path = (
            repository_root
            / "docs"
            / "capa_configuracion"
            / "issues"
            / "BESS-CONFIG-017-prove-the-configuration-layer-end-to-end.md"
        )
        tracker_path = issue_path.parent / "tracker_configuration_layer.md"
        report_path = (
            repository_root
            / "docs"
            / "capa_configuracion"
            / "verification_configuration_layer_final.md"
        )

        issue = issue_path.read_text(encoding="utf-8")
        tracker = tracker_path.read_text(encoding="utf-8")
        self.assertIn("Status: In Review", issue)
        self.assertNotIn("- [ ]", issue)
        self.assertIn(
            "| BESS-CONFIG-017 | Prove The Configuration Layer End To End "
            "| AFK | ready-for-agent | In Review |",
            tracker,
        )
        self.assertIn(
            "| 2026-08-27 | BESS-CONFIG-017 | In Progress -> In Review |",
            tracker,
        )

        report = report_path.read_text(encoding="utf-8")
        for required_evidence in (
            "tests.test_configuration_layer_acceptance",
            "unittest discover -s tests",
            "npm test",
            "npm run api:check",
            "npm run build",
            "npm run test:browser",
            "julia --project=. -e",
            "Chrome",
            "operator login",
            "client login",
            "## Fuera de alcance confirmado",
        ):
            with self.subTest(required_evidence=required_evidence):
                self.assertIn(required_evidence, report)


if __name__ == "__main__":
    unittest.main()
