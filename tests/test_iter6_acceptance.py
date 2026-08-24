import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from app.persistence import AnalystStore
from app.runner import JuliaRunExecutor
from app.validation import ValidationResult
from tests.auth_test_helpers import (
    bootstrap_admin_with_csrf,
    delete_with_csrf,
    login_json_with_csrf,
    post_json_with_csrf,
    put_json_with_csrf,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


class Iteration6AcceptanceTests(unittest.TestCase):
    def test_external_portal_publication_flow_auth_downloads_and_revocation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_root = Path(temp_dir) / "artifacts"
            store = AnalystStore("sqlite:///:memory:")
            validation_service = Iter6ValidationService()
            run_process = Iter6RunProcess()
            executor = JuliaRunExecutor(
                store=store,
                repo_root=REPO_ROOT,
                artifact_root=artifact_root,
                julia_executable="julia",
                runner=run_process,
                validation_service=validation_service,
            )
            client = TestClient(
                create_app(
                    validation_service=validation_service,
                    store=store,
                    run_queue=SynchronousRunQueue(executor),
                    artifact_root=artifact_root,
                    auth_enabled=True,
                )
            )
            try:
                unauthenticated = client.get("/projects", follow_redirects=False)
                self.assertEqual(unauthenticated.status_code, 303)
                self.assertEqual(unauthenticated.headers["location"], "/react/projects")

                bootstrap = bootstrap_admin_with_csrf(client, "admin@example.local", "admin pass", "Admin")
                self.assertEqual(bootstrap.status_code, 201)
                self.assertEqual(bootstrap.json()["landing_path"], "/react/projects")
                admin_user = store.get_user_by_email("admin@example.local")
                self.assertTrue(admin_user["password_hash"].startswith("pbkdf2_sha256$"))
                self.assertNotEqual(admin_user["password_hash"], "admin pass")

                analyst_user = post_json_with_csrf(
                    client,
                    "/api/admin/users",
                    {
                        "email": "analyst@example.local",
                        "display_name": "Analyst",
                        "role": "analyst",
                        "password": "analyst pass",
                    },
                ).json()["user"]
                client_user = post_json_with_csrf(
                    client,
                    "/api/admin/users",
                    {
                        "email": "client@example.local",
                        "display_name": "Client",
                        "role": "external",
                        "password": "client pass",
                    },
                ).json()["user"]
                self.assertEqual(analyst_user["role"], "analyst")
                self.assertEqual(client_user["role"], "external")

                project = post_json_with_csrf(
                    client,
                    "/api/projects",
                    {"name": "Iter6 Client Publication", "description": "Acceptance"},
                ).json()
                private_project = post_json_with_csrf(
                    client,
                    "/api/projects",
                    {"name": "Unassigned Internal Project", "description": ""},
                ).json()
                assign = put_json_with_csrf(
                    client,
                    f"/api/admin/projects/{project['id']}/external-access/{client_user['id']}",
                    {"portal_view": True, "operate": False},
                )
                self.assertEqual(assign.status_code, 200)

                post_json_with_csrf(client, "/api/auth/logout")
                self.login(client, "analyst@example.local", "analyst pass")

                scenario = post_json_with_csrf(
                    client,
                    f"/api/projects/{project['id']}/scenarios",
                    {"name": "Published Scenario", "description": "Accepted result"},
                ).json()
                sample_text = (REPO_ROOT / "data" / "cases" / "hybrid_system" / "system_case.json").read_text(
                    encoding="utf-8"
                )
                version_response = post_json_with_csrf(
                    client,
                    f"/api/scenarios/{scenario['id']}/versions",
                    {"system_case_json": sample_text},
                )
                self.assertEqual(version_response.status_code, 201)
                version = version_response.json()
                run_response = post_json_with_csrf(
                    client,
                    f"/api/scenario-versions/{version['id']}/runs",
                )
                self.assertEqual(run_response.status_code, 201)
                run_id = run_response.json()["id"]
                run = client.get(f"/api/runs/{run_id}").json()["run"]
                self.assertEqual(run["status"], "succeeded")

                results = client.get(f"/api/runs/{run_id}/results").json()["results"]
                self.assertEqual(results["summary"]["case_name"], "hybrid_system")
                self.assertIn("grid_import_mw", results["dispatch_table"]["columns"])
                self.assertEqual(client.get(f"/api/runs/{run_id}/publications").json()["publications"], [])

                template_response = post_json_with_csrf(
                    client,
                    f"/api/projects/{project['id']}/dashboard-templates",
                    {
                        "name": "Client Summary Template",
                        "show_summary": True,
                        "show_price_chart": False,
                        "show_grid_chart": True,
                        "show_renewable_chart": False,
                        "show_bess_chart": False,
                        "show_hydro_chart": False,
                        "show_profit_chart": False,
                        "show_system_dispatch_table": True,
                        "show_asset_dispatch_table": False,
                        "table_preview_limit": 1,
                    },
                )
                self.assertEqual(template_response.status_code, 201)
                template = template_response.json()["dashboard_template"]

                publication_response = post_json_with_csrf(
                    client,
                    f"/api/runs/{run_id}/publications",
                    {
                        "dashboard_template_id": template["id"],
                        "public_title": "January Hybrid Dispatch Results",
                        "analyst_notes": "Approved assumptions for client review.",
                        "allowed_artifact_types": ["summary_json"],
                    },
                )
                self.assertEqual(publication_response.status_code, 201)
                publication = publication_response.json()["publication"]
                hidden_draft = post_json_with_csrf(
                    client,
                    f"/api/runs/{run_id}/publications",
                    {
                        "dashboard_template_id": template["id"],
                        "public_title": "Internal Draft Only",
                        "allowed_artifact_types": ["summary_json"],
                    },
                ).json()["publication"]

                configure_portal = put_json_with_csrf(
                    client,
                    f"/api/projects/{project['id']}/portal-configuration",
                    {
                        "document": {
    "schema_version": "portal_config.v1",
    "display_name": "Portal cliente",
    "sections": {
        "kpis": {
            "enabled": True,
            "label": "Resumen",
            "items": [
                {
                    "id": "beneficio_total",
                    "path": "objective_value_usd",
                    "label": "Beneficio total",
                    "unit": "USD",
                    "decimals": 0,
                    "sign": "auto",
                    "emphasis": "strong",
                }
            ],
        },
        "charts": {"enabled": False, "label": "Resultados", "items": []},
        "tables": {"enabled": False, "label": "Detalle", "items": []},
        "downloads": {"enabled": True, "label": "Descargas"},
    },
},
                        "status": "active",
                        "expected_revision": 0,
                    },
                )
                self.assertEqual(configure_portal.status_code, 200)

                preview = client.get(f"/api/publications/{publication['id']}/preview")
                self.assertEqual(preview.status_code, 200)
                preview_body = preview.json()
                self.assertEqual(preview_body["publication"]["public_title"], "January Hybrid Dispatch Results")
                self.assertEqual(preview_body["publication"]["analyst_notes"], "Approved assumptions for client review.")
                self.assertEqual(preview_body["results_state"], "available")
                self.assertEqual(
                    [kpi["label"] for kpi in preview_body["results_block"]["kpis"]],
                    ["Beneficio total"],
                )
                self.assertEqual([download["label"] for download in preview_body["downloads"]], ["summary.json"])

                publish = post_json_with_csrf(client, f"/api/publications/{publication['id']}/publish")
                self.assertEqual(publish.status_code, 200)
                self.assertEqual(publish.json()["publication"]["status"], "published")

                post_json_with_csrf(client, "/api/auth/logout")
                self.login(client, "client@example.local", "client pass")

                portal = client.get("/api/client/projects")
                self.assertEqual(portal.status_code, 200)
                self.assertEqual(
                    [
                        project["branding"]["display_name"]
                        for project in portal.json()["projects"]
                    ],
                    ["Portal cliente"],
                )
                self.assertEqual(client.get(f"/api/client/projects/{private_project['id']}/publications").status_code, 404)

                project_page = client.get(f"/api/client/projects/{project['id']}/publications")
                self.assertEqual(project_page.status_code, 200)
                self.assertEqual(
                    [publication["public_title"] for publication in project_page.json()["publications"]],
                    ["January Hybrid Dispatch Results"],
                )

                live = client.get(f"/api/client/projects/{project['id']}/publications/{publication['id']}")
                self.assertEqual(live.status_code, 200)
                live_body = live.json()
                self.assertEqual(live_body["publication"]["public_title"], "January Hybrid Dispatch Results")
                self.assertEqual(live_body["publication"]["analyst_notes"], "Approved assumptions for client review.")
                self.assertEqual(live_body["results_state"], "available")
                self.assertEqual(
                    live_body["results_block"], preview_body["results_block"]
                )
                self.assertEqual([download["label"] for download in live_body["downloads"]], ["summary.json"])
                self.assertEqual(
                    client.get(f"/api/client/projects/{project['id']}/publications/{hidden_draft['id']}").status_code,
                    404,
                )

                download_path = (
                    f"/client/projects/{project['id']}/publications/{publication['id']}"
                    "/artifacts/summary_json/download"
                )
                allowed_download = client.get(download_path)
                self.assertEqual(allowed_download.status_code, 200)
                self.assertEqual(allowed_download.json()["case_name"], "hybrid_system")
                self.assertEqual(
                    client.get(
                        f"/client/projects/{project['id']}/publications/{publication['id']}"
                        "/artifacts/dispatch_csv/download"
                    ).status_code,
                    404,
                )

                legacy_internal = client.get("/projects", follow_redirects=False)
                self.assertEqual(legacy_internal.status_code, 404)

                for method, path, kwargs in [
                    ("post", "/api/projects", {"json": {"name": "Client mutation"}}),
                    ("get", f"/api/runs/{run_id}/results", {}),
                    ("post", f"/api/scenario-versions/{version['id']}/runs", {}),
                ]:
                    with self.subTest(path=path):
                        self.assertEqual(getattr(client, method)(path, **kwargs).status_code, 404)

                post_json_with_csrf(client, "/api/auth/logout")
                self.login(client, "analyst@example.local", "analyst pass")
                unpublish = post_json_with_csrf(client, f"/api/publications/{publication['id']}/unpublish")
                self.assertEqual(unpublish.status_code, 200)
                self.assertEqual(unpublish.json()["publication"]["status"], "unpublished")

                post_json_with_csrf(client, "/api/auth/logout")
                self.login(client, "client@example.local", "client pass")
                self.assertEqual(
                    client.get(f"/api/client/projects/{project['id']}/publications/{publication['id']}").status_code,
                    404,
                )

                post_json_with_csrf(client, "/api/auth/logout")
                self.login(client, "analyst@example.local", "analyst pass")
                post_json_with_csrf(client, f"/api/publications/{publication['id']}/publish")

                post_json_with_csrf(client, "/api/auth/logout")
                self.login(client, "admin@example.local", "admin pass")
                remove = delete_with_csrf(
                    client,
                    f"/api/admin/projects/{project['id']}/external-access/{client_user['id']}",
                )
                self.assertEqual(remove.status_code, 200)

                post_json_with_csrf(client, "/api/auth/logout")
                self.login(client, "client@example.local", "client pass")
                self.assertEqual(client.get("/api/client/projects").status_code, 404)
                self.assertEqual(client.get(download_path).status_code, 404)

                post_json_with_csrf(client, "/api/auth/logout")
                self.login(client, "admin@example.local", "admin pass")
                put_json_with_csrf(
                    client,
                    f"/api/admin/projects/{project['id']}/external-access/{client_user['id']}",
                    {"portal_view": True, "operate": False},
                )
                post_json_with_csrf(client, "/api/auth/logout")
                self.login(client, "client@example.local", "client pass")
                self.assertEqual(client.get(download_path).status_code, 200)

                post_json_with_csrf(client, "/api/auth/logout")
                self.login(client, "admin@example.local", "admin pass")
                deactivate = post_json_with_csrf(client, f"/api/admin/users/{client_user['id']}/deactivate")
                self.assertEqual(deactivate.status_code, 200)
                post_json_with_csrf(client, "/api/auth/logout")
                inactive_login = login_json_with_csrf(client, "client@example.local", "client pass")
                self.assertEqual(inactive_login.status_code, 401)
                self.assertEqual(validation_service.file_validation_count, 1)
                self.assertEqual(run_process.completed_case_names, ["hybrid_system"])
            finally:
                store.close()

    def test_iteration_6_documentation_tracker_and_manual_checklist_are_done(self):
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        issue = (
            REPO_ROOT
            / "docs"
            / "iter6"
            / "issues"
            / "BESS-ITER6-008-finalize-iteration-6-acceptance-suite-and-docs.md"
        ).read_text(encoding="utf-8")
        tracker = (REPO_ROOT / "docs" / "iter6" / "issues" / "tracker_iter6.md").read_text(encoding="utf-8")
        manual = (REPO_ROOT / "docs" / "iter6" / "pruebas_manuales_iteracion6.md").read_text(encoding="utf-8")

        for expected in [
            "Client Publication And Read-Only Portal",
            "Local Auth Roles And Sessions",
            "Admin Users And Project Access",
            "Dashboard Templates",
            "Publication Drafts Preview Publish And Unpublish",
            "Client Portal And Read-Only Routes",
            "Artifact Allowlist And Revocation",
            "Iteration 6 Acceptance Verification",
        ]:
            self.assertIn(expected, readme)

        self.assertIn("Status: Done", issue)
        self.assertNotIn("- [ ]", issue)
        self.assertIn("tests.test_iter6_acceptance", issue)
        self.assertIn("| BESS-ITER6-008 | Finalize Iteration 6 Acceptance Suite And Docs | AFK | ready-for-agent | Done |", tracker)
        self.assertIn("BESS-ITER6-008 | Todo -> Done", tracker)
        self.assertIn("Final Iteration 6 Verification", tracker)
        self.assertIn("Cierre Iteracion 6", manual)
        self.assertIn("tests.test_iter6_acceptance", manual)
        self.assertIn("allowlist", manual.lower())
        self.assertIn("revocacion", manual.lower())

    def login(self, client, email, password):
        response = login_json_with_csrf(client, email, password)
        self.assertEqual(response.status_code, 200, response.text)


class Iter6ValidationService:
    def __init__(self):
        self.text_validation_count = 0
        self.file_validation_count = 0

    def validate_text(self, candidate_text):
        self.text_validation_count += 1
        document = json.loads(candidate_text)
        return validation_success_for(document)

    def validate_file(self, candidate_path):
        self.file_validation_count += 1
        document = json.loads(Path(candidate_path).read_text(encoding="utf-8"))
        return validation_success_for(document)


def validation_success_for(document):
    return ValidationResult(
        ok=True,
        phase="julia",
        message="Validation succeeded",
        payload={
            "status": "ok",
            "case_name": document["case_name"],
            "schema_version": document["schema_version"],
            "period_count": len(document["time_series"]),
        },
        exit_code=0,
        raw_stdout='{"status":"ok"}\n',
        raw_stderr="",
    )


class SynchronousRunQueue:
    def __init__(self, executor):
        self.executor = executor

    def enqueue(self, run_id):
        self.executor.execute(run_id)

    def stop(self):
        pass


class Iter6RunProcess:
    def __init__(self):
        self.completed_case_names = []

    def __call__(self, command, **kwargs):
        input_path = next(Path(item) for item in command if str(item).endswith("system_case.json"))
        output_root = Path(command[command.index("--output-root") + 1])
        system_case = json.loads(input_path.read_text(encoding="utf-8"))
        case_name = system_case["case_name"]
        self.completed_case_names.append(case_name)
        output_dir = output_root / case_name / f"iter6-acceptance-run-{len(self.completed_case_names)}"
        output_dir.mkdir(parents=True)
        summary_path = output_dir / "summary.json"
        summary_path.write_text(
            json.dumps(
                {
                    "case_name": case_name,
                    "run_timestamp": output_dir.name,
                    "solver_name": "HiGHS",
                    "solver_status": "OPTIMAL",
                    "termination_status": "OPTIMAL",
                    "objective_value_usd": 1250.5,
                    "model_version": "0.1.0",
                },
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        (output_dir / "dispatch.csv").write_text(
            "timestamp,duration_hours,price_usd_per_mwh,grid_import_mw,grid_export_mw,net_grid_export_mw,"
            "renewable_used_mw,renewable_curtailed_mw,load_demand_mw,battery_charge_mw,battery_discharge_mw,"
            "battery_net_discharge_mw,battery_energy_mwh,battery_delta_soc_abs_mwh,market_value_usd,"
            "battery_degradation_cost_usd,curtailment_penalty_usd,period_profit_usd\n"
            "2026-01-01T00:00:00,1.0,45.0,2.5,0.0,-2.5,4.0,0.0,6.5,0.0,0.0,0.0,20.0,0.0,-112.5,0.0,0.0,-112.5\n"
            "2026-01-01T01:00:00,1.0,80.0,0.0,1.5,1.5,3.0,1.0,4.0,0.0,1.0,1.0,18.9,1.1,120.0,2.2,0.0,117.8\n",
            encoding="utf-8",
        )
        (output_dir / "asset_dispatch.csv").write_text(
            "timestamp,duration_hours,price_usd_per_mwh,asset_id,asset_type,grid_import_mw,grid_export_mw,"
            "renewable_used_mw,renewable_curtailed_mw,load_demand_mw,battery_charge_mw,battery_discharge_mw,"
            "battery_energy_mwh,battery_delta_soc_abs_mwh\n"
            "2026-01-01T00:00:00,1.0,45.0,grid_1,grid,2.5,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0\n"
            "2026-01-01T00:00:00,1.0,45.0,solar_1,renewable,0.0,0.0,4.0,0.0,0.0,0.0,0.0,0.0,0.0\n"
            "2026-01-01T00:00:00,1.0,45.0,battery_1,battery,0.0,0.0,0.0,0.0,0.0,0.0,0.0,20.0,0.0\n",
            encoding="utf-8",
        )
        (output_dir / "model_metadata.json").write_text(
            json.dumps(
                {
                    "model_name": "one_bus_system_dispatch",
                    "schema_version": system_case["schema_version"],
                },
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=json.dumps(
                {
                    "case_name": case_name,
                    "run_timestamp": output_dir.name,
                    "output_dir": str(output_dir),
                    "summary_path": str(summary_path),
                    "termination_status": "OPTIMAL",
                }
            ),
            stderr="",
        )


if __name__ == "__main__":
    unittest.main()
