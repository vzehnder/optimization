"""BESS-CONFIG-016: comparing two configured console runs safely.

The comparison is the console's own surface: it reads the same configured
results allowlist run detail uses, keeps the analyst's labels and order, and
never lets a public run id become a door into the internal run route.
"""

import json
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.auth import hash_password
from app.main import create_app
from app.persistence import AnalystStore
from tests.auth_test_helpers import login_json_with_csrf
from tests.test_configuration_layer_operator_console import (
    NORMATIVE_DOCUMENT,
    RecordingRunQueue,
    StubValidationService,
)


CONSOLE_RESULTS = {
    "kpis": [
        {
            "id": "beneficio_total",
            "path": "objective_value_usd",
            "label": "Beneficio total",
            "unit": "USD",
            "decimals": 1,
            "sign": "auto",
            "emphasis": "strong",
        },
        {
            "id": "energia_comprada",
            "path": "energy_imported_mwh",
            "label": "Energia comprada",
            "unit": "MWh",
            "decimals": 2,
            "sign": "never",
            "emphasis": "normal",
        },
    ],
    "charts": [
        {
            "id": "intercambio_red",
            "chart_key": "grid_import_export",
            "label": "Intercambio con la red",
            "series": [{"key": "grid_import_mw", "label": "Compra"}],
        }
    ],
    "tables": [
        {
            "id": "despacho_sistema",
            "table_key": "system_dispatch",
            "label": "Despacho del sistema",
            "row_limit": 24,
            "columns": [
                {"key": "timestamp", "id": "periodo", "label": "Periodo", "unit": None},
                {
                    "key": "grid_import_mw",
                    "id": "compra",
                    "label": "Compra",
                    "unit": "MW",
                },
            ],
        }
    ],
}


class ConsoleRunComparisonTests(unittest.TestCase):
    def setUp(self):
        self.store = AnalystStore("sqlite:///:memory:")
        self.artifact_temp = tempfile.TemporaryDirectory()
        self.client = TestClient(
            create_app(
                validation_service=StubValidationService(),
                store=self.store,
                auth_enabled=True,
                run_queue=RecordingRunQueue(),
                artifact_root=Path(self.artifact_temp.name),
            )
        )
        self.analyst = self.store.create_user(
            email="analyst@example.local",
            display_name="Ana Analista",
            role="analyst",
            password_hash=hash_password("analyst pass"),
        )
        self.operator = self.store.create_user(
            email="operator@example.local",
            display_name="Olga Operadora",
            role="external",
            password_hash=hash_password("operator pass"),
        )
        self.project = self.store.create_project(name="Planta Norte")
        self.scenario = self.store.create_scenario(
            project_id=self.project["id"], name="Operacion diaria"
        )
        self.store.get_or_create_case_for_scenario(self.scenario["id"])
        self.store.set_external_project_access(
            project_id=self.project["id"],
            user_id=self.operator["id"],
            portal_view=False,
            operate=True,
            updated_by="admin@example.local",
        )

    def tearDown(self):
        self.store.close()
        self.artifact_temp.cleanup()

    def login(self, email="operator@example.local", password="operator pass"):
        self.assertEqual(
            login_json_with_csrf(self.client, email, password).status_code, 200
        )

    def create_console(self, *, status="active", scenario=None, results=None):
        scenario = scenario or self.scenario
        case = self.store.get_or_create_case_for_scenario(scenario["id"])
        variant = self.store.get_or_create_default_input_variant(case["id"])
        document = {
            **NORMATIVE_DOCUMENT,
            "results": CONSOLE_RESULTS if results is None else results,
        }
        console = self.store.create_operator_console(
            case_id=case["id"],
            source_variant_id=variant["id"],
            document=document,
            created_by_user_id=self.analyst["id"],
        )
        if status == "active":
            console = self.store.save_operator_console(
                console["id"],
                document=document,
                status="active",
                expected_revision=1,
                updated_by_user_id=None,
            )
        return console

    def succeeded_run(
        self,
        console,
        *,
        objective,
        imported_mwh,
        import_mw,
        scenario=None,
        display_name="Olga Operadora",
    ):
        """One finished console run with the artifacts the allowlist reads."""

        run = self.queued_run(console, scenario=scenario, display_name=display_name)
        output_dir = Path(self.artifact_temp.name) / "runs" / str(run["id"]) / "outputs"
        output_dir.mkdir(parents=True)
        summary_path = output_dir / "summary.json"
        dispatch_path = output_dir / "dispatch.csv"
        asset_dispatch_path = output_dir / "asset_dispatch.csv"
        summary_path.write_text(
            json.dumps(
                {
                    "objective_value_usd": objective,
                    "energy_imported_mwh": imported_mwh,
                    "workspace_path": "C:/secret/artifacts",
                    "stdout": "private",
                    "case_name": "comparison_case",
                    "all_series": [1, 2, 3],
                }
            ),
            encoding="utf-8",
        )
        dispatch_path.write_text(
            "timestamp,grid_import_mw,source_identifiers\n"
            + "".join(
                f"2026-01-01T0{index}:00:00,{value},secret\n"
                for index, value in enumerate(import_mw)
            ),
            encoding="utf-8",
        )
        asset_dispatch_path.write_text(
            "timestamp,asset_id,asset_type\n2026-01-01T00:00:00,grid_1,grid\n",
            encoding="utf-8",
        )
        self.store.mark_run_running(
            run["id"],
            workspace_path=str(output_dir.parent),
            input_snapshot_path=str(output_dir.parent / "input" / "system_case.json"),
        )
        self.store.mark_run_succeeded(
            run["id"],
            exit_code=0,
            stdout="sensitive stdout",
            stderr="sensitive stderr",
            success_payload={"schema_version": "internal"},
            output_dir=str(output_dir),
            summary_path=str(summary_path),
        )
        for artifact_type, path, media_type in [
            ("summary_json", summary_path, "application/json"),
            ("dispatch_csv", dispatch_path, "text/csv"),
            ("asset_dispatch_csv", asset_dispatch_path, "text/csv"),
        ]:
            self.store.register_run_artifact(
                run_id=run["id"],
                artifact_type=artifact_type,
                path=str(path),
                display_name=path.name,
                media_type=media_type,
            )
        return self.store.get_run(run["id"])

    def queued_run(self, console, *, scenario=None, display_name="Olga Operadora"):
        scenario = scenario or self.scenario
        version = self.store.create_scenario_version(
            scenario_id=scenario["id"],
            system_case_json={
                "schema_version": "bess_system_dispatch.v2",
                "case_name": "comparison_case",
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
            triggered_by_user_id=self.operator["id"],
            triggered_by_display_name=display_name,
            operator_console_id=console["id"],
            operator_console_revision=console["revision"],
        )

    def compare(self, console_id, left, right):
        return self.client.get(
            f"/api/console/{console_id}/run-comparison?left={left}&right={right}"
        )

    def test_an_operator_compares_two_runs_with_configured_labels_and_order(self):
        console = self.create_console()
        left = self.succeeded_run(
            console, objective=1000.0, imported_mwh=12.5, import_mw=[2.5, 3.0]
        )
        right = self.succeeded_run(
            console,
            objective=1250.5,
            imported_mwh=9.25,
            import_mw=[1.5, 4.0],
            display_name="Pedro Operador",
        )
        self.login()

        response = self.compare(console["id"], left["id"], right["id"])

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["left"]["run"]["id"], left["id"])
        self.assertEqual(payload["right"]["run"]["triggered_by"], "Pedro Operador")
        self.assertEqual(payload["left"]["results_state"], "available")
        self.assertEqual(payload["right"]["results_state"], "available")
        self.assertEqual(
            [kpi["label"] for kpi in payload["left"]["results_block"]["kpis"]],
            ["Beneficio total", "Energia comprada"],
        )
        self.assertEqual(payload["right"]["results_block"]["kpis"][0]["value"], 1250.5)
        self.assertEqual(
            [chart["label"] for chart in payload["left"]["results_block"]["charts"]],
            ["Intercambio con la red"],
        )
        self.assertEqual(
            payload["right"]["results_block"]["charts"][0]["series"][0]["values"],
            [1.5, 4.0],
        )
        self.assertEqual(
            [
                column["label"]
                for column in payload["left"]["results_block"]["tables"][0]["columns"]
            ],
            ["Periodo", "Compra"],
        )
        self.assertEqual(
            payload["left"]["results_block"]["labels"],
            {
                "kpis": "Indicadores",
                "charts": "Graficos",
                "tables": "Tablas",
                "downloads": "",
            },
        )


    def test_the_comparison_states_the_difference_of_every_shared_kpi(self):
        console = self.create_console()
        left = self.succeeded_run(
            console, objective=1000.0, imported_mwh=12.5, import_mw=[2.5, 3.0]
        )
        right = self.succeeded_run(
            console, objective=1250.5, imported_mwh=9.25, import_mw=[1.5, 4.0]
        )
        self.login()

        payload = self.compare(console["id"], left["id"], right["id"]).json()

        self.assertEqual(
            payload["kpi_differences"],
            [
                {
                    "id": "beneficio_total",
                    "label": "Beneficio total",
                    "unit": "USD",
                    "decimals": 1,
                    "left": 1000.0,
                    "right": 1250.5,
                    "difference": 250.5,
                },
                {
                    "id": "energia_comprada",
                    "label": "Energia comprada",
                    "unit": "MWh",
                    "decimals": 2,
                    "left": 12.5,
                    "right": 9.25,
                    "difference": -3.25,
                },
            ],
        )


    def test_only_runs_of_the_requested_console_can_be_compared(self):
        console = self.create_console()
        mine = self.succeeded_run(
            console, objective=1000.0, imported_mwh=12.5, import_mw=[2.5]
        )
        neighbour = self.create_console()
        theirs = self.succeeded_run(
            neighbour, objective=2000.0, imported_mwh=20.0, import_mw=[5.0]
        )
        analyst_run = self.store.create_run(
            scenario_version_id=self.store.create_scenario_version(
                scenario_id=self.scenario["id"],
                system_case_json={
                    "schema_version": "bess_system_dispatch.v2",
                    "case_name": "manual_case",
                    "nodes": [],
                    "edges": [],
                    "time_series": [],
                },
                validation_payload={"status": "ok"},
            )["id"],
            triggered_by="analyst@example.local",
        )
        self.login()

        for label, right in [
            ("another console", theirs["id"]),
            ("an analyst run", analyst_run["id"]),
            ("a guessed id", mine["id"] + 5000),
        ]:
            with self.subTest(label):
                self.assertEqual(
                    self.compare(console["id"], mine["id"], right).status_code, 404
                )
                self.assertEqual(
                    self.compare(console["id"], right, mine["id"]).status_code, 404
                )

    def test_a_draft_console_and_a_revoked_operator_get_no_comparison(self):
        draft = self.create_console(status="draft")
        draft_run = self.succeeded_run(
            draft, objective=1000.0, imported_mwh=12.5, import_mw=[2.5]
        )
        console = self.create_console()
        left = self.succeeded_run(
            console, objective=1000.0, imported_mwh=12.5, import_mw=[2.5]
        )
        right = self.succeeded_run(
            console, objective=1100.0, imported_mwh=11.0, import_mw=[2.0]
        )
        self.login()

        self.assertEqual(
            self.compare(draft["id"], draft_run["id"], draft_run["id"]).status_code,
            404,
        )
        self.assertEqual(
            self.compare(console["id"], left["id"], right["id"]).status_code, 200
        )

        self.store.set_external_project_access(
            project_id=self.project["id"],
            user_id=self.operator["id"],
            portal_view=False,
            operate=False,
            updated_by="admin@example.local",
        )

        self.assertEqual(
            self.compare(console["id"], left["id"], right["id"]).status_code, 404
        )

    def test_a_public_run_id_does_not_open_the_internal_run_route(self):
        console = self.create_console()
        run = self.succeeded_run(
            console, objective=1000.0, imported_mwh=12.5, import_mw=[2.5]
        )
        self.login()

        self.assertEqual(
            self.compare(console["id"], run["id"], run["id"]).status_code, 200
        )
        for internal_path in [
            f"/api/runs/{run['id']}",
            f"/api/runs/{run['id']}/results",
            f"/api/runs/{run['id']}/artifacts",
        ]:
            with self.subTest(internal_path):
                self.assertEqual(self.client.get(internal_path).status_code, 404)


    def test_a_side_without_results_stays_unavailable_and_silent(self):
        console = self.create_console()
        ready = self.succeeded_run(
            console, objective=1000.0, imported_mwh=12.5, import_mw=[2.5]
        )
        broken = self.queued_run(console)
        self.store.mark_run_running(
            broken["id"],
            workspace_path="C:/secret/artifacts/runs/99",
            input_snapshot_path="C:/secret/artifacts/runs/99/input/system_case.json",
        )
        self.store.mark_run_failed(
            broken["id"],
            exit_code=137,
            stdout="sensitive stdout",
            stderr="Traceback: HiGHS crashed reading C:/secret/artifacts",
            error_payload={"schema_version": "internal", "detail": "solver aborted"},
            error_message="solver aborted",
            stdout_log_path="C:/secret/artifacts/runs/99/stdout.log",
            stderr_log_path="C:/secret/artifacts/runs/99/stderr.log",
        )
        self.login()

        response = self.compare(console["id"], ready["id"], broken["id"])

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["right"]["results_state"], "unavailable")
        self.assertIsNone(payload["right"]["results_block"])
        self.assertEqual(payload["right"]["run"]["state"], "fallida")
        self.assertEqual(payload["left"]["results_state"], "available")
        # Nothing on this side may be compared, so nothing is claimed about it.
        self.assertEqual(payload["kpi_differences"], [])

    def test_the_comparison_payload_carries_no_internal_metadata(self):
        console = self.create_console()
        left = self.succeeded_run(
            console, objective=1000.0, imported_mwh=12.5, import_mw=[2.5, 3.0]
        )
        right = self.succeeded_run(
            console, objective=1250.5, imported_mwh=9.25, import_mw=[1.5, 4.0]
        )
        self.login()

        response = self.compare(console["id"], left["id"], right["id"])

        self.assertEqual(response.status_code, 200, response.text)
        for forbidden in [
            "scenario_version_id",
            "scenario_id",
            "operator_console_revision",
            "revision",
            "input_variant",
            "binding",
            "checksum",
            "sha256",
            "system_case",
            "case_name",
            "schema_version",
            "workspace_path",
            "input_snapshot_path",
            "summary_path",
            "artifact",
            "stdout",
            "stderr",
            "exit_code",
            "source_identifiers",
            "asset_id",
            "all_series",
            "objective_value_usd",
            "energy_imported_mwh",
            "grid_import_mw",
            str(Path(self.artifact_temp.name)),
        ]:
            with self.subTest(forbidden):
                self.assertNotIn(forbidden, response.text)


if __name__ == "__main__":
    unittest.main()
