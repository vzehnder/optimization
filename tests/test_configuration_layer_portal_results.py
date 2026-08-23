import json
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient
from copy import deepcopy

from app.portal_configuration import (
    PortalConfigurationError,
    StalePortalConfigurationError,
    validate_portal_config_document,
)
from app.auth import hash_password
from app.main import create_app
from app.persistence import AnalystStore
from app.surface_payloads import build_results_block
from tests.test_results_review import create_completed_run_with_result_artifacts
from tests.auth_test_helpers import (
    login_json_with_csrf,
    post_json_with_csrf,
    put_json_with_csrf,
)


PORTAL_CONFIG_WITH_ONE_KPI = {
    "schema_version": "portal_config.v1",
    "display_name": "Plan operativo Cliente Norte",
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
}


class PortalConfigurationPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.store = AnalystStore("sqlite:///:memory:")
        self.project = self.store.create_project(name="Cliente Norte", description="")
        self.analyst = self.store.create_user(
            email="analyst@example.local",
            display_name="Analyst",
            role="analyst",
            password_hash="test-hash",
        )

    def tearDown(self):
        self.store.close()

    def test_project_starts_without_a_portal_configuration(self):
        self.assertIsNone(self.store.get_portal_configuration(self.project["id"]))

    def test_first_save_creates_revision_one_with_audit_metadata(self):
        saved = self.store.save_portal_configuration(
            self.project["id"],
            document=PORTAL_CONFIG_WITH_ONE_KPI,
            status="active",
            expected_revision=0,
            updated_by_user_id=self.analyst["id"],
        )

        self.assertEqual(
            {
                "project_id": saved["project_id"],
                "status": saved["status"],
                "revision": saved["revision"],
                "updated_by_user_id": saved["updated_by_user_id"],
                "display_name": saved["document"]["display_name"],
            },
            {
                "project_id": self.project["id"],
                "status": "active",
                "revision": 1,
                "updated_by_user_id": self.analyst["id"],
                "display_name": "Plan operativo Cliente Norte",
            },
        )
        self.assertTrue(saved["updated_at"])
        self.assertEqual(
            self.store.get_portal_configuration(self.project["id"])["document"],
            PORTAL_CONFIG_WITH_ONE_KPI,
        )

    def test_second_save_increments_the_revision(self):
        self.store.save_portal_configuration(
            self.project["id"],
            document=PORTAL_CONFIG_WITH_ONE_KPI,
            status="draft",
            expected_revision=0,
            updated_by_user_id=self.analyst["id"],
        )
        renamed = dict(PORTAL_CONFIG_WITH_ONE_KPI, display_name="Plan revisado")

        saved = self.store.save_portal_configuration(
            self.project["id"],
            document=renamed,
            status="active",
            expected_revision=1,
            updated_by_user_id=self.analyst["id"],
        )

        self.assertEqual(
            {"revision": saved["revision"], "status": saved["status"]},
            {"revision": 2, "status": "active"},
        )

    def test_stale_expected_revision_is_rejected_without_writing(self):
        self.store.save_portal_configuration(
            self.project["id"],
            document=PORTAL_CONFIG_WITH_ONE_KPI,
            status="active",
            expected_revision=0,
            updated_by_user_id=self.analyst["id"],
        )
        other = dict(PORTAL_CONFIG_WITH_ONE_KPI, display_name="Escritura perdida")

        with self.assertRaises(StalePortalConfigurationError) as raised:
            self.store.save_portal_configuration(
                self.project["id"],
                document=other,
                status="active",
                expected_revision=0,
                updated_by_user_id=self.analyst["id"],
            )

        self.assertEqual(raised.exception.current_revision, 1)
        stored = self.store.get_portal_configuration(self.project["id"])
        self.assertEqual(
            {
                "revision": stored["revision"],
                "display_name": stored["document"]["display_name"],
            },
            {"revision": 1, "display_name": "Plan operativo Cliente Norte"},
        )


class PortalConfigDocumentValidationTests(unittest.TestCase):
    def test_a_normative_document_is_accepted_and_normalized(self):
        accepted = validate_portal_config_document(PORTAL_CONFIG_WITH_ONE_KPI)

        self.assertEqual(accepted, PORTAL_CONFIG_WITH_ONE_KPI)

    def test_an_unknown_schema_version_is_rejected(self):
        document = dict(PORTAL_CONFIG_WITH_ONE_KPI, schema_version="portal_config.v2")

        with self.assertRaisesRegex(PortalConfigurationError, "schema version"):
            validate_portal_config_document(document)

    def test_a_malformed_document_is_rejected(self):
        for description, document in [
            ("not an object", ["portal_config.v1"]),
            ("missing sections", {"schema_version": "portal_config.v1", "display_name": "X"}),
            (
                "unknown top level key",
                dict(PORTAL_CONFIG_WITH_ONE_KPI, tracking_pixel="https://tracker.example"),
            ),
            (
                "missing kpi label",
                _document_with_kpi_item(
                    {
                        "id": "beneficio_total",
                        "path": "objective_value_usd",
                        "unit": "USD",
                        "decimals": 0,
                        "sign": "auto",
                        "emphasis": "strong",
                    }
                ),
            ),
        ]:
            with self.subTest(description):
                with self.assertRaises(PortalConfigurationError):
                    validate_portal_config_document(document)

    def test_duplicate_item_ids_are_rejected(self):
        document = _document_with_kpi_items(
            [
                _kpi_item("beneficio_total", "objective_value_usd"),
                _kpi_item("beneficio_total", "solver_status"),
            ]
        )

        with self.assertRaisesRegex(PortalConfigurationError, "duplicate item id"):
            validate_portal_config_document(document)

    def test_invalid_enum_values_are_rejected(self):
        for field, value in [("sign", "positivo"), ("emphasis", "huge")]:
            with self.subTest(field):
                document = _document_with_kpi_item(
                    dict(_kpi_item("beneficio_total", "objective_value_usd"), **{field: value})
                )
                with self.assertRaisesRegex(PortalConfigurationError, field):
                    validate_portal_config_document(document)

    def test_a_kpi_path_is_limited_to_three_literal_segments(self):
        for description, path_value in [
            ("wildcard", "summary.*"),
            ("four segments", "a.b.c.d"),
            ("empty", ""),
        ]:
            with self.subTest(description):
                document = _document_with_kpi_item(
                    _kpi_item("beneficio_total", path_value)
                )
                with self.assertRaisesRegex(PortalConfigurationError, "path"):
                    validate_portal_config_document(document)

    def test_all_series_and_plot_series_are_never_accepted_catalog_keys(self):
        for forbidden in ["all_series", "plot_series"]:
            with self.subTest(forbidden):
                document = _document_with_chart_item(
                    {
                        "id": "todo",
                        "chart_key": forbidden,
                        "label": "Todo",
                        "series": [{"key": "grid_import_mw", "label": "Compra"}],
                    }
                )
                with self.assertRaisesRegex(PortalConfigurationError, forbidden):
                    validate_portal_config_document(document)


def _kpi_item(item_id: str, path: str) -> dict:
    return {
        "id": item_id,
        "path": path,
        "label": "Beneficio total",
        "unit": "USD",
        "decimals": 0,
        "sign": "auto",
        "emphasis": "strong",
    }


def _document_with_kpi_item(item: dict) -> dict:
    return _document_with_kpi_items([item])


def _document_with_kpi_items(items: list) -> dict:
    document = deepcopy(PORTAL_CONFIG_WITH_ONE_KPI)
    document["sections"]["kpis"]["items"] = items
    return document


def _document_with_chart_item(item: dict) -> dict:
    document = deepcopy(PORTAL_CONFIG_WITH_ONE_KPI)
    document["sections"]["charts"] = {
        "enabled": True,
        "label": "Resultados",
        "items": [item],
    }
    return document


class ConfiguredResultsBlockTests(unittest.TestCase):
    def setUp(self):
        self.results = {
            "summary": {
                "case_name": "hybrid_system",
                "objective_value_usd": 1250.5,
                "solver_name": "HiGHS",
                "solver_status": "OPTIMAL",
            },
            "dispatch_table": {"columns": ["timestamp"], "rows": []},
            "asset_dispatch_table": {"columns": ["timestamp"], "rows": []},
            "charts": {"all_series": {"series": []}},
            "plot_series": [{"key": "grid_import_mw"}],
        }

    def test_a_declared_kpi_is_rendered_with_its_public_presentation(self):
        block = build_results_block(PORTAL_CONFIG_WITH_ONE_KPI, self.results)

        self.assertEqual(
            block["kpis"],
            [
                {
                    "id": "beneficio_total",
                    "label": "Beneficio total",
                    "value": 1250.5,
                    "unit": "USD",
                    "decimals": 0,
                    "sign": "auto",
                    "emphasis": "strong",
                }
            ],
        )

    def test_the_canonical_path_never_reaches_the_external_payload(self):
        block = build_results_block(PORTAL_CONFIG_WITH_ONE_KPI, self.results)

        self.assertNotIn("path", block["kpis"][0])
        self.assertNotIn("objective_value_usd", json.dumps(block))

    def test_a_missing_kpi_is_omitted_without_breaking_the_rest(self):
        document = _document_with_kpi_items(
            [
                _kpi_item("beneficio_total", "objective_value_usd"),
                _kpi_item("no_existe", "kpi_que_no_existe"),
                dict(_kpi_item("colgando", "summary.nested.missing"), label="Colgando"),
            ]
        )

        block = build_results_block(document, self.results)

        self.assertEqual(
            [kpi["id"] for kpi in block["kpis"]], ["beneficio_total"]
        )

    def test_unknown_summary_keys_never_reach_the_external_payload(self):
        self.results["summary"]["internal_stdout_path"] = "/var/runs/17/stdout.log"
        self.results["summary"]["exit_code"] = 137

        block = build_results_block(PORTAL_CONFIG_WITH_ONE_KPI, self.results)

        serialized = json.dumps(block)
        self.assertNotIn("internal_stdout_path", serialized)
        self.assertNotIn("stdout.log", serialized)
        self.assertNotIn("exit_code", serialized)

    def test_a_disabled_kpi_section_exposes_no_kpis(self):
        document = deepcopy(PORTAL_CONFIG_WITH_ONE_KPI)
        document["sections"]["kpis"]["enabled"] = False

        self.assertEqual(build_results_block(document, self.results)["kpis"], [])


class PortalConfigurationApiTests(unittest.TestCase):
    def setUp(self):
        self.store = AnalystStore("sqlite:///:memory:")
        self.client = TestClient(create_app(store=self.store, auth_enabled=True))
        self.store.create_user(
            email="analyst@example.local",
            display_name="Analyst",
            role="analyst",
            password_hash=hash_password("analyst pass"),
        )
        self.assertEqual(
            login_json_with_csrf(
                self.client, "analyst@example.local", "analyst pass"
            ).status_code,
            200,
        )
        self.project = post_json_with_csrf(
            self.client, "/api/projects", {"name": "Cliente Norte", "description": ""}
        ).json()
        self.path = f"/api/projects/{self.project['id']}/portal-configuration"

    def tearDown(self):
        self.store.close()

    def test_an_unconfigured_project_reports_revision_zero(self):
        response = self.client.get(self.path)

        self.assertEqual(response.status_code, 200)
        configuration = response.json()["portal_configuration"]
        self.assertEqual(
            {
                "status": configuration["status"],
                "revision": configuration["revision"],
                "schema_version": configuration["document"]["schema_version"],
            },
            {"status": "draft", "revision": 0, "schema_version": "portal_config.v1"},
        )

    def test_saving_a_valid_active_configuration_records_revision_and_audit(self):
        response = put_json_with_csrf(
            self.client,
            self.path,
            {
                "document": PORTAL_CONFIG_WITH_ONE_KPI,
                "status": "active",
                "expected_revision": 0,
            },
        )

        self.assertEqual(response.status_code, 200)
        configuration = response.json()["portal_configuration"]
        self.assertEqual(
            {
                "status": configuration["status"],
                "revision": configuration["revision"],
                "updated_by": configuration["updated_by"],
            },
            {"status": "active", "revision": 1, "updated_by": "analyst@example.local"},
        )

    def test_an_invalid_document_is_rejected_without_writing(self):
        response = put_json_with_csrf(
            self.client,
            self.path,
            {
                "document": dict(
                    PORTAL_CONFIG_WITH_ONE_KPI, schema_version="portal_config.v9"
                ),
                "status": "active",
                "expected_revision": 0,
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            self.client.get(self.path).json()["portal_configuration"]["revision"], 0
        )

    def test_a_stale_expected_revision_is_rejected_with_conflict(self):
        put_json_with_csrf(
            self.client,
            self.path,
            {
                "document": PORTAL_CONFIG_WITH_ONE_KPI,
                "status": "active",
                "expected_revision": 0,
            },
        )

        response = put_json_with_csrf(
            self.client,
            self.path,
            {
                "document": dict(PORTAL_CONFIG_WITH_ONE_KPI, display_name="Perdido"),
                "status": "active",
                "expected_revision": 0,
            },
        )

        self.assertEqual(response.status_code, 409)
        current = self.client.get(self.path).json()["portal_configuration"]
        self.assertEqual(
            {
                "revision": current["revision"],
                "display_name": current["document"]["display_name"],
            },
            {"revision": 1, "display_name": "Plan operativo Cliente Norte"},
        )

    def test_an_external_user_cannot_read_or_write_the_configuration(self):
        self.store.create_user(
            email="external@example.local",
            display_name="External",
            role="external",
            password_hash=hash_password("external pass"),
        )
        external_client = TestClient(create_app(store=self.store, auth_enabled=True))
        self.assertEqual(
            login_json_with_csrf(
                external_client, "external@example.local", "external pass"
            ).status_code,
            200,
        )

        self.assertEqual(external_client.get(self.path).status_code, 403)
        self.assertEqual(
            put_json_with_csrf(
                external_client,
                self.path,
                {
                    "document": PORTAL_CONFIG_WITH_ONE_KPI,
                    "status": "active",
                    "expected_revision": 0,
                },
            ).status_code,
            403,
        )


class ConfiguredPortalResultEndToEndTests(unittest.TestCase):
    def setUp(self):
        self.store = AnalystStore("sqlite:///:memory:")
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.artifact_root = Path(self.temporary_directory.name) / "artifacts"
        self.store.create_user(
            email="analyst@example.local",
            display_name="Analyst",
            role="analyst",
            password_hash=hash_password("analyst pass"),
        )
        self.external_user = self.store.create_user(
            email="external@example.local",
            display_name="External",
            role="external",
            password_hash=hash_password("external pass"),
        )
        self.run = create_completed_run_with_result_artifacts(
            self.store, self.artifact_root
        )
        self.project_id = self.store.get_run_lineage(self.run["id"])["project_id"]
        self.store.set_external_project_access(
            project_id=self.project_id,
            user_id=self.external_user["id"],
            portal_view=True,
            operate=False,
            updated_by="analyst@example.local",
        )
        template = self.store.create_dashboard_template(
            project_id=self.project_id,
            name="Portal Template",
            created_by="analyst@example.local",
        )
        self.analyst = self.logged_in_client("analyst@example.local", "analyst pass")
        self.publication = post_json_with_csrf(
            self.analyst,
            f"/api/runs/{self.run['id']}/publications",
            {
                "dashboard_template_id": template["id"],
                "public_title": "Plan operativo enero",
                "allowed_artifact_types": ["summary_json"],
            },
        ).json()["publication"]
        post_json_with_csrf(
            self.analyst, f"/api/publications/{self.publication['id']}/publish"
        )

    def tearDown(self):
        self.store.close()
        self.temporary_directory.cleanup()

    def logged_in_client(self, email: str, password: str) -> TestClient:
        client = TestClient(
            create_app(
                store=self.store, artifact_root=self.artifact_root, auth_enabled=True
            )
        )
        self.assertEqual(
            login_json_with_csrf(client, email, password).status_code, 200
        )
        return client

    def configure_active_portal(self, document=None) -> None:
        response = put_json_with_csrf(
            self.analyst,
            f"/api/projects/{self.project_id}/portal-configuration",
            {
                "document": document or PORTAL_CONFIG_WITH_ONE_KPI,
                "status": "active",
                "expected_revision": 0,
            },
        )
        self.assertEqual(response.status_code, 200)

    def test_the_client_sees_the_configured_kpi_the_analyst_declared(self):
        self.configure_active_portal()
        external = self.logged_in_client("external@example.local", "external pass")

        detail = external.get(
            f"/api/client/projects/{self.project_id}"
            f"/publications/{self.publication['id']}"
        )

        self.assertEqual(detail.status_code, 200)
        self.assertEqual(
            detail.json()["results_block"],
            {
                "labels": {
                    "kpis": "Resumen",
                    "charts": "",
                    "tables": "",
                    "downloads": "Descargas",
                },
                "kpis": [
                    {
                        "id": "beneficio_total",
                        "label": "Beneficio total",
                        "value": 1250.5,
                        "unit": "USD",
                        "decimals": 0,
                        "sign": "auto",
                        "emphasis": "strong",
                    }
                ],
                "charts": [],
                "tables": [],
            },
        )

    def test_the_preview_shows_the_same_configured_kpi_as_the_portal(self):
        self.configure_active_portal()
        external = self.logged_in_client("external@example.local", "external pass")

        preview = self.analyst.get(f"/api/publications/{self.publication['id']}/preview")
        detail = external.get(
            f"/api/client/projects/{self.project_id}"
            f"/publications/{self.publication['id']}"
        )

        self.assertEqual(preview.status_code, 200)
        self.assertEqual(
            preview.json()["results_block"], detail.json()["results_block"]
        )

    def test_a_draft_configuration_is_not_live_for_the_client(self):
        put_json_with_csrf(
            self.analyst,
            f"/api/projects/{self.project_id}/portal-configuration",
            {
                "document": PORTAL_CONFIG_WITH_ONE_KPI,
                "status": "draft",
                "expected_revision": 0,
            },
        )
        external = self.logged_in_client("external@example.local", "external pass")

        detail = external.get(
            f"/api/client/projects/{self.project_id}"
            f"/publications/{self.publication['id']}"
        )

        self.assertEqual(detail.status_code, 200)
        self.assertEqual(
            detail.json()["results_block"],
            {
                "labels": {"kpis": "", "charts": "", "tables": "", "downloads": ""},
                "kpis": [],
                "charts": [],
                "tables": [],
            },
        )

    def test_an_edit_to_an_active_configuration_is_visible_immediately(self):
        self.configure_active_portal()
        external = self.logged_in_client("external@example.local", "external pass")
        relabelled = deepcopy(PORTAL_CONFIG_WITH_ONE_KPI)
        relabelled["sections"]["kpis"]["items"][0]["label"] = "Beneficio del periodo"

        put_json_with_csrf(
            self.analyst,
            f"/api/projects/{self.project_id}/portal-configuration",
            {"document": relabelled, "status": "active", "expected_revision": 1},
        )

        detail = external.get(
            f"/api/client/projects/{self.project_id}"
            f"/publications/{self.publication['id']}"
        )
        self.assertEqual(
            detail.json()["results_block"]["kpis"][0]["label"], "Beneficio del periodo"
        )

    def test_the_configured_block_carries_no_canonical_or_internal_metadata(self):
        self.configure_active_portal()
        external = self.logged_in_client("external@example.local", "external pass")

        detail = external.get(
            f"/api/client/projects/{self.project_id}"
            f"/publications/{self.publication['id']}"
        )

        serialized = json.dumps(detail.json()["results_block"])
        for forbidden in ["objective_value_usd", "solver_status", "path", "run_id"]:
            self.assertNotIn(forbidden, serialized)

    def test_the_portal_and_preview_expose_only_the_resolved_current_branding(self):
        self.configure_active_portal()
        self.store.save_portal_logo(
            self.project_id,
            logo_bytes=b"\x89PNG\r\n\x1a\ncurrent-logo",
            logo_media_type="image/png",
            expected_revision=1,
            updated_by_user_id=None,
        )
        external = self.logged_in_client("external@example.local", "external pass")

        detail = external.get(
            f"/api/client/projects/{self.project_id}"
            f"/publications/{self.publication['id']}"
        ).json()
        preview = self.analyst.get(
            f"/api/publications/{self.publication['id']}/preview"
        ).json()

        self.assertEqual(
            detail["branding"],
            {
                "display_name": "Plan operativo Cliente Norte",
                "logo_url": f"/api/client/projects/{self.project_id}/branding/logo",
            },
        )
        self.assertEqual(
            preview["branding"],
            {
                "display_name": "Plan operativo Cliente Norte",
                "logo_url": f"/api/projects/{self.project_id}/portal-configuration/logo",
            },
        )
        for payload in (detail, preview):
            self.assertNotIn("project", payload)
            serialized = json.dumps(payload)
            self.assertNotIn("logo_bytes", serialized)
            self.assertNotIn("Interno", serialized)

    def test_project_portal_routes_use_resolved_branding_without_project_metadata(self):
        self.configure_active_portal()
        self.store.save_portal_logo(
            self.project_id,
            logo_bytes=b"\x89PNG\r\n\x1a\ncurrent-logo",
            logo_media_type="image/png",
            expected_revision=1,
            updated_by_user_id=None,
        )
        external = self.logged_in_client("external@example.local", "external pass")
        expected_branding = {
            "display_name": "Plan operativo Cliente Norte",
            "logo_url": f"/api/client/projects/{self.project_id}/branding/logo",
        }

        projects = external.get("/api/client/projects").json()["projects"]
        publications = external.get(
            f"/api/client/projects/{self.project_id}/publications"
        ).json()

        self.assertEqual(
            projects,
            [{"id": self.project_id, "branding": expected_branding}],
        )
        self.assertEqual(publications["branding"], expected_branding)
        self.assertNotIn("project", publications)
        for payload in (projects, publications):
            serialized = json.dumps(payload)
            self.assertNotIn("description", serialized)
            self.assertNotIn('"name"', serialized)

    def test_missing_brand_fields_fall_back_to_the_project_name_and_no_logo(self):
        unbranded = deepcopy(PORTAL_CONFIG_WITH_ONE_KPI)
        unbranded["display_name"] = ""
        self.configure_active_portal(unbranded)
        external = self.logged_in_client("external@example.local", "external pass")

        detail = external.get(
            f"/api/client/projects/{self.project_id}"
            f"/publications/{self.publication['id']}"
        ).json()

        self.assertEqual(
            detail["branding"],
            {"display_name": "Hybrid PMGD", "logo_url": None},
        )



if __name__ == "__main__":
    unittest.main()
