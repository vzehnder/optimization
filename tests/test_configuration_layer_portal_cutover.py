"""BESS-CONFIG-004: the whole portal report comes from the shared safe builder."""

import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from app.portal_configuration import (
    PORTAL_CHART_CATALOG,
    PORTAL_TABLE_CATALOG,
    PortalConfigurationError,
    portal_config_document_from_dashboard_template,
    validate_portal_config_document,
)
from fastapi.testclient import TestClient

from app.auth import hash_password
from app.main import create_app
from app.persistence import AnalystStore
from app.surface_payloads import (
    build_portal_publication_payload,
    build_results_block,
)
from tests.auth_test_helpers import (
    login_json_with_csrf,
    post_json_with_csrf,
    put_json_with_csrf,
)
from tests.test_results_review import create_completed_run_with_result_artifacts


BASE_DOCUMENT = {
    "schema_version": "portal_config.v1",
    "display_name": "Plan operativo Cliente Norte",
    "sections": {
        "kpis": {"enabled": False, "label": "Resumen", "items": []},
        "charts": {"enabled": False, "label": "Resultados", "items": []},
        "tables": {"enabled": False, "label": "Detalle", "items": []},
        "downloads": {"enabled": False, "label": "Descargas"},
    },
}


def document_with_chart(item: dict) -> dict:
    document = deepcopy(BASE_DOCUMENT)
    document["sections"]["charts"] = {
        "enabled": True,
        "label": "Resultados",
        "items": [item],
    }
    return document


def document_with_table(item: dict) -> dict:
    document = deepcopy(BASE_DOCUMENT)
    document["sections"]["tables"] = {
        "enabled": True,
        "label": "Detalle",
        "items": [item],
    }
    return document


GRID_CHART = {
    "id": "intercambio_red",
    "chart_key": "grid_import_export",
    "label": "Intercambio con la red",
    "series": [
        {"key": "grid_import_mw", "label": "Compra"},
        {"key": "grid_export_mw", "label": "Venta"},
    ],
}

SYSTEM_TABLE = {
    "id": "despacho_sistema",
    "table_key": "system_dispatch",
    "label": "Despacho del sistema",
    "row_limit": 24,
    "columns": [
        {"key": "timestamp", "id": "periodo", "label": "Periodo", "unit": None},
        {"key": "grid_import_mw", "id": "compra", "label": "Compra", "unit": "MW"},
    ],
}


class FixedBackendCatalogTests(unittest.TestCase):
    def test_a_chart_and_table_from_the_catalog_are_accepted(self):
        accepted = validate_portal_config_document(document_with_chart(GRID_CHART))

        self.assertEqual(accepted["sections"]["charts"]["items"], [GRID_CHART])
        self.assertEqual(
            validate_portal_config_document(document_with_table(SYSTEM_TABLE))[
                "sections"
            ]["tables"]["items"],
            [SYSTEM_TABLE],
        )

    def test_an_unknown_chart_key_is_rejected(self):
        document = document_with_chart(
            dict(GRID_CHART, chart_key="secret_internal_chart")
        )

        with self.assertRaisesRegex(PortalConfigurationError, "secret_internal_chart"):
            validate_portal_config_document(document)

    def test_a_series_outside_the_chart_catalog_is_rejected(self):
        document = document_with_chart(
            dict(
                GRID_CHART,
                series=[{"key": "battery_energy_mwh", "label": "Bateria"}],
            )
        )

        with self.assertRaisesRegex(PortalConfigurationError, "battery_energy_mwh"):
            validate_portal_config_document(document)

    def test_an_unknown_table_key_is_rejected(self):
        document = document_with_table(dict(SYSTEM_TABLE, table_key="users"))

        with self.assertRaisesRegex(PortalConfigurationError, "users"):
            validate_portal_config_document(document)

    def test_a_column_outside_the_table_catalog_is_rejected(self):
        document = document_with_table(
            dict(
                SYSTEM_TABLE,
                columns=[
                    {
                        "key": "password_hash",
                        "id": "secreto",
                        "label": "Secreto",
                        "unit": None,
                    }
                ],
            )
        )

        with self.assertRaisesRegex(PortalConfigurationError, "password_hash"):
            validate_portal_config_document(document)

    def test_a_column_from_another_table_is_rejected(self):
        document = document_with_table(
            dict(
                SYSTEM_TABLE,
                columns=[
                    {
                        "key": "asset_id",
                        "id": "activo",
                        "label": "Activo",
                        "unit": None,
                    }
                ],
            )
        )

        with self.assertRaisesRegex(PortalConfigurationError, "asset_id"):
            validate_portal_config_document(document)


CANONICAL_RESULTS = {
    "summary": {
        "case_name": "hybrid_system",
        "objective_value_usd": 1250.5,
        "solver_status": "OPTIMAL",
    },
    "dispatch_table": {
        "columns": [
            "timestamp",
            "grid_import_mw",
            "grid_export_mw",
            "period_profit_usd",
        ],
        "rows": [
            {
                "timestamp": "2026-01-01T00:00:00",
                "grid_import_mw": "2.5",
                "grid_export_mw": "0.0",
                "period_profit_usd": "-112.5",
            },
            {
                "timestamp": "2026-01-01T01:00:00",
                "grid_import_mw": "0.0",
                "grid_export_mw": "1.5",
                "period_profit_usd": "67.5",
            },
        ],
    },
    "asset_dispatch_table": {
        "columns": ["timestamp", "asset_id", "asset_type"],
        "rows": [
            {
                "timestamp": "2026-01-01T00:00:00",
                "asset_id": "grid_1",
                "asset_type": "grid",
            }
        ],
    },
    "charts": {"all_series": {"series": ["everything"]}},
    "plot_series": [{"id": "system:grid_import_mw"}],
}


class ConfiguredChartTests(unittest.TestCase):
    def test_a_configured_chart_carries_only_public_labels_and_values(self):
        block = build_results_block(document_with_chart(GRID_CHART), CANONICAL_RESULTS)

        self.assertEqual(
            block["charts"],
            [
                {
                    "id": "intercambio_red",
                    "label": "Intercambio con la red",
                    "x_labels": ["2026-01-01T00:00:00", "2026-01-01T01:00:00"],
                    "series": [
                        {"label": "Compra", "unit": "MW", "values": [2.5, 0.0]},
                        {"label": "Venta", "unit": "MW", "values": [0.0, 1.5]},
                    ],
                }
            ],
        )

    def test_a_canonical_series_key_never_reaches_the_chart_payload(self):
        block = build_results_block(document_with_chart(GRID_CHART), CANONICAL_RESULTS)

        self.assertNotIn("grid_import_mw", json.dumps(block))

    def test_a_series_whose_column_is_missing_is_omitted(self):
        chart = dict(
            GRID_CHART,
            series=[
                {"key": "grid_import_mw", "label": "Compra"},
                {"key": "net_grid_export_mw", "label": "Neto"},
            ],
        )

        block = build_results_block(document_with_chart(chart), CANONICAL_RESULTS)

        self.assertEqual(
            [series["label"] for series in block["charts"][0]["series"]], ["Compra"]
        )

    def test_a_chart_without_any_available_series_is_omitted(self):
        chart = dict(
            GRID_CHART,
            series=[{"key": "net_grid_export_mw", "label": "Neto"}],
        )

        block = build_results_block(document_with_chart(chart), CANONICAL_RESULTS)

        self.assertEqual(block["charts"], [])

    def test_a_disabled_chart_section_exposes_no_charts_and_no_label(self):
        document = document_with_chart(GRID_CHART)
        document["sections"]["charts"]["enabled"] = False

        block = build_results_block(document, CANONICAL_RESULTS)

        self.assertEqual(
            {"charts": block["charts"], "label": block["labels"]["charts"]},
            {"charts": [], "label": ""},
        )

    def test_the_never_acceptable_catalog_entries_never_appear(self):
        block = build_results_block(document_with_chart(GRID_CHART), CANONICAL_RESULTS)

        serialized = json.dumps(block)
        self.assertNotIn("all_series", serialized)
        self.assertNotIn("plot_series", serialized)


class ConfiguredTableTests(unittest.TestCase):
    def test_a_configured_table_uses_external_column_ids_only(self):
        block = build_results_block(document_with_table(SYSTEM_TABLE), CANONICAL_RESULTS)

        self.assertEqual(
            block["tables"],
            [
                {
                    "id": "despacho_sistema",
                    "label": "Despacho del sistema",
                    "row_limit": 24,
                    "columns": [
                        {"id": "periodo", "label": "Periodo", "unit": None},
                        {"id": "compra", "label": "Compra", "unit": "MW"},
                    ],
                    "rows": [
                        {"periodo": "2026-01-01T00:00:00", "compra": 2.5},
                        {"periodo": "2026-01-01T01:00:00", "compra": 0.0},
                    ],
                }
            ],
        )

    def test_a_canonical_column_key_never_reaches_the_table_payload(self):
        block = build_results_block(document_with_table(SYSTEM_TABLE), CANONICAL_RESULTS)

        self.assertNotIn("grid_import_mw", json.dumps(block))

    def test_the_configured_row_limit_truncates_the_rows(self):
        block = build_results_block(
            document_with_table(dict(SYSTEM_TABLE, row_limit=1)), CANONICAL_RESULTS
        )

        self.assertEqual(
            block["tables"][0]["rows"],
            [{"periodo": "2026-01-01T00:00:00", "compra": 2.5}],
        )

    def test_a_column_missing_from_the_run_is_omitted(self):
        table = dict(
            SYSTEM_TABLE,
            columns=SYSTEM_TABLE["columns"]
            + [
                {
                    "key": "battery_energy_mwh",
                    "id": "soc",
                    "label": "SOC",
                    "unit": "MWh",
                }
            ],
        )

        block = build_results_block(document_with_table(table), CANONICAL_RESULTS)

        self.assertEqual(
            [column["id"] for column in block["tables"][0]["columns"]],
            ["periodo", "compra"],
        )
        self.assertNotIn("soc", block["tables"][0]["rows"][0])

    def test_a_table_without_any_available_column_is_omitted(self):
        table = dict(
            SYSTEM_TABLE,
            columns=[
                {
                    "key": "battery_energy_mwh",
                    "id": "soc",
                    "label": "SOC",
                    "unit": "MWh",
                }
            ],
        )

        block = build_results_block(document_with_table(table), CANONICAL_RESULTS)

        self.assertEqual(block["tables"], [])

    def test_a_disabled_table_section_exposes_no_tables_and_no_label(self):
        document = document_with_table(SYSTEM_TABLE)
        document["sections"]["tables"]["enabled"] = False

        block = build_results_block(document, CANONICAL_RESULTS)

        self.assertEqual(
            {"tables": block["tables"], "label": block["labels"]["tables"]},
            {"tables": [], "label": ""},
        )

    def test_an_asset_table_reads_its_own_canonical_source(self):
        table = {
            "id": "despacho_activos",
            "table_key": "asset_dispatch",
            "label": "Despacho por activo",
            "row_limit": 10,
            "columns": [
                {"key": "asset_id", "id": "activo", "label": "Activo", "unit": None},
                {"key": "asset_type", "id": "tipo", "label": "Tipo", "unit": None},
            ],
        }

        block = build_results_block(document_with_table(table), CANONICAL_RESULTS)

        self.assertEqual(
            block["tables"][0]["rows"], [{"activo": "grid_1", "tipo": "grid"}]
        )


PROJECT_ROW = {
    "id": 3,
    "name": "Cliente Norte",
    "description": "Interno: contrato 2026 con margen objetivo",
    "created_at": "2026-01-01T00:00:00+00:00",
    "created_by": "analyst@example.local",
}

PUBLICATION_ROW = {
    "id": 9,
    "project_id": 3,
    "scenario_id": 4,
    "scenario_version_id": 5,
    "run_id": 6,
    "dashboard_template_id": 7,
    "public_title": "Plan operativo enero",
    "analyst_notes": "Aprobado para revision del cliente.",
    "status": "published",
    "published_at": "2026-01-15T12:00:00+00:00",
    "published_by": "analyst@example.local",
    "unpublished_at": None,
    "allowed_artifact_types": ["summary_json", "dispatch_csv"],
    "created_by": "analyst@example.local",
}

ALLOWED_DOWNLOADS = [
    {
        "artifact_type": "summary_json",
        "display_name": "summary.json",
        "media_type": "application/json",
        "byte_size": 128,
        "path": "/srv/optimization/artifacts/runs/6/outputs/summary.json",
        "download_url": "/api/client/projects/3/publications/9/artifacts/summary_json/download",
    }
]


def portal_payload(document: dict, **overrides) -> dict:
    arguments = {
        "project": PROJECT_ROW,
        "publication": PUBLICATION_ROW,
        "document": document,
        "results": CANONICAL_RESULTS,
        "downloads": ALLOWED_DOWNLOADS,
    }
    arguments.update(overrides)
    return build_portal_publication_payload(**arguments)


def document_with_downloads(enabled: bool) -> dict:
    document = deepcopy(BASE_DOCUMENT)
    document["sections"]["downloads"] = {"enabled": enabled, "label": "Descargas"}
    return document


class PortalPublicationPayloadTests(unittest.TestCase):
    def test_the_payload_exposes_only_the_public_publication_identity(self):
        payload = portal_payload(deepcopy(BASE_DOCUMENT))

        self.assertEqual(
            payload["publication"],
            {
                "id": 9,
                "project_id": 3,
                "public_title": "Plan operativo enero",
                "analyst_notes": "Aprobado para revision del cliente.",
                "published_at": "2026-01-15T12:00:00+00:00",
                "status": "published",
            },
        )
        self.assertEqual(payload["project"], {"id": 3, "name": "Cliente Norte"})

    def test_internal_publication_and_project_fields_never_cross_the_boundary(self):
        serialized = json.dumps(portal_payload(deepcopy(BASE_DOCUMENT)))

        for forbidden in [
            "dashboard_template_id",
            "scenario_version_id",
            "run_id",
            "allowed_artifact_types",
            "published_by",
            "created_by",
            "analyst@example.local",
            "contrato 2026",
        ]:
            self.assertNotIn(forbidden, serialized)

    def test_the_period_is_derived_from_the_result_timestamps(self):
        payload = portal_payload(deepcopy(BASE_DOCUMENT))

        self.assertEqual(
            payload["period"],
            {"start": "2026-01-01T00:00:00", "end": "2026-01-01T01:00:00"},
        )

    def test_unreadable_results_become_an_unavailable_state_without_detail(self):
        payload = portal_payload(deepcopy(BASE_DOCUMENT), results=None)

        self.assertEqual(
            {
                "results_state": payload["results_state"],
                "results_block": payload["results_block"],
                "period": payload["period"],
            },
            {
                "results_state": "unavailable",
                "results_block": None,
                "period": {"start": None, "end": None},
            },
        )

    def test_available_results_carry_the_configured_block(self):
        payload = portal_payload(document_with_chart(GRID_CHART))

        self.assertEqual(payload["results_state"], "available")
        self.assertEqual(
            [chart["id"] for chart in payload["results_block"]["charts"]],
            ["intercambio_red"],
        )

    def test_downloads_are_the_intersection_of_configuration_and_allowlist(self):
        payload = portal_payload(document_with_downloads(True))

        self.assertEqual(
            payload["downloads"],
            [
                {
                    "label": "summary.json",
                    "media_type": "application/json",
                    "byte_size": 128,
                    "download_url": (
                        "/api/client/projects/3/publications/9"
                        "/artifacts/summary_json/download"
                    ),
                }
            ],
        )

    def test_a_disabled_download_section_hides_every_allowed_artifact(self):
        payload = portal_payload(document_with_downloads(False))

        self.assertEqual(payload["downloads"], [])

    def test_a_server_artifact_path_never_reaches_the_payload(self):
        serialized = json.dumps(portal_payload(document_with_downloads(True)))

        self.assertNotIn("/srv/optimization", serialized)
        self.assertNotIn("path", serialized)


def template_row(**flags) -> dict:
    row = {
        "id": 1,
        "project_id": 3,
        "name": "Plantilla heredada",
        "show_summary": False,
        "show_price_chart": False,
        "show_grid_chart": False,
        "show_renewable_chart": False,
        "show_bess_chart": False,
        "show_hydro_chart": False,
        "show_profit_chart": False,
        "show_system_dispatch_table": False,
        "show_asset_dispatch_table": False,
        "table_preview_limit": 10,
    }
    row.update(flags)
    return row


class DashboardTemplateMigrationTests(unittest.TestCase):
    def test_the_migrated_document_is_structurally_valid(self):
        document = portal_config_document_from_dashboard_template(
            template_row(
                show_summary=True,
                show_price_chart=True,
                show_grid_chart=True,
                show_renewable_chart=True,
                show_bess_chart=True,
                show_hydro_chart=True,
                show_profit_chart=True,
                show_system_dispatch_table=True,
                show_asset_dispatch_table=True,
                table_preview_limit=24,
            ),
            display_name="Cliente Norte",
        )

        self.assertEqual(validate_portal_config_document(document), document)

    def test_only_the_flags_that_were_visible_are_enabled(self):
        document = portal_config_document_from_dashboard_template(
            template_row(
                show_summary=True,
                show_grid_chart=True,
                show_system_dispatch_table=True,
                table_preview_limit=5,
            ),
            display_name="Cliente Norte",
        )

        sections = document["sections"]
        self.assertEqual(
            {
                "kpis": sections["kpis"]["enabled"],
                "charts": [item["chart_key"] for item in sections["charts"]["items"]],
                "tables": [item["table_key"] for item in sections["tables"]["items"]],
                "row_limit": sections["tables"]["items"][0]["row_limit"],
            },
            {
                "kpis": True,
                "charts": ["grid_import_export"],
                "tables": ["system_dispatch"],
                "row_limit": 5,
            },
        )

    def test_a_template_that_hid_everything_migrates_to_an_empty_portal(self):
        document = portal_config_document_from_dashboard_template(
            template_row(), display_name="Cliente Norte"
        )

        sections = document["sections"]
        self.assertEqual(
            {
                "kpis": (sections["kpis"]["enabled"], sections["kpis"]["items"]),
                "charts": (sections["charts"]["enabled"], sections["charts"]["items"]),
                "tables": (sections["tables"]["enabled"], sections["tables"]["items"]),
            },
            {"kpis": (False, []), "charts": (False, []), "tables": (False, [])},
        )

    def test_the_hydro_flag_migrates_to_every_hydro_chart(self):
        document = portal_config_document_from_dashboard_template(
            template_row(show_hydro_chart=True), display_name="Cliente Norte"
        )

        self.assertEqual(
            [item["chart_key"] for item in document["sections"]["charts"]["items"]],
            [
                "hydro_power",
                "hydro_flows",
                "hydro_storage",
                "hydro_reservoir_elevation",
            ],
        )

    def test_downloads_stay_available_because_the_allowlist_already_gated_them(self):
        document = portal_config_document_from_dashboard_template(
            template_row(), display_name="Cliente Norte"
        )

        self.assertTrue(document["sections"]["downloads"]["enabled"])


class DashboardTemplateStoreMigrationTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.artifact_root = Path(self.temporary_directory.name) / "artifacts"
        self.store = AnalystStore("sqlite:///:memory:")
        self.run = create_completed_run_with_result_artifacts(
            self.store, self.artifact_root
        )
        self.project_id = self.store.get_run_lineage(self.run["id"])["project_id"]

    def tearDown(self):
        self.store.close()
        self.temporary_directory.cleanup()

    def publish(self, template_id: int) -> dict:
        publication = self.store.create_publication_draft(
            run_id=self.run["id"],
            dashboard_template_id=template_id,
            public_title="Plan operativo enero",
        )
        return self.store.publish_publication(
            publication["id"], published_by="analyst@example.local"
        )

    def test_a_published_project_migrates_from_its_most_recent_template(self):
        self.store.create_dashboard_template(
            project_id=self.project_id,
            name="Antigua",
            show_summary=False,
            show_price_chart=False,
            show_grid_chart=False,
            show_renewable_chart=False,
            show_bess_chart=False,
            show_hydro_chart=False,
            show_profit_chart=False,
            show_system_dispatch_table=False,
            show_asset_dispatch_table=False,
            created_by="analyst@example.local",
        )
        recent = self.store.create_dashboard_template(
            project_id=self.project_id,
            name="Vigente",
            show_summary=True,
            show_price_chart=False,
            show_grid_chart=True,
            show_renewable_chart=False,
            show_bess_chart=False,
            show_hydro_chart=False,
            show_profit_chart=False,
            show_system_dispatch_table=True,
            show_asset_dispatch_table=False,
            table_preview_limit=7,
            created_by="analyst@example.local",
        )
        self.publish(recent["id"])

        self.store.migrate_dashboard_templates_to_portal_configurations()

        configuration = self.store.get_portal_configuration(self.project_id)
        sections = configuration["document"]["sections"]
        self.assertEqual(
            {
                "status": configuration["status"],
                "revision": configuration["revision"],
                "display_name": configuration["document"]["display_name"],
                "charts": [item["chart_key"] for item in sections["charts"]["items"]],
                "row_limit": sections["tables"]["items"][0]["row_limit"],
            },
            {
                "status": "active",
                "revision": 1,
                "display_name": self.store.get_project(self.project_id)["name"],
                "charts": ["grid_import_export"],
                "row_limit": 7,
            },
        )

    def test_a_published_project_without_a_usable_template_gets_an_empty_portal(self):
        template = self.store.create_dashboard_template(
            project_id=self.project_id,
            name="Solo para publicar",
            created_by="analyst@example.local",
        )
        self.publish(template["id"])
        # Legacy data where the template behind a publication is already gone.
        self.store.connection.execute("PRAGMA foreign_keys = OFF")
        self.store.connection.execute("DELETE FROM dashboard_templates")
        self.store.connection.commit()
        self.store.connection.execute("PRAGMA foreign_keys = ON")

        self.store.migrate_dashboard_templates_to_portal_configurations()

        sections = self.store.get_portal_configuration(self.project_id)["document"][
            "sections"
        ]
        self.assertEqual(
            [
                sections["kpis"]["enabled"],
                sections["charts"]["enabled"],
                sections["tables"]["enabled"],
                sections["downloads"]["enabled"],
            ],
            [False, False, False, False],
        )

    def test_a_project_without_publications_is_never_configured_automatically(self):
        self.store.create_dashboard_template(
            project_id=self.project_id,
            name="Sin publicar",
            created_by="analyst@example.local",
        )

        self.store.migrate_dashboard_templates_to_portal_configurations()

        self.assertIsNone(self.store.get_portal_configuration(self.project_id))

    def test_an_existing_configuration_is_never_overwritten(self):
        template = self.store.create_dashboard_template(
            project_id=self.project_id,
            name="Vigente",
            created_by="analyst@example.local",
        )
        self.publish(template["id"])
        chosen = deepcopy(BASE_DOCUMENT)
        self.store.save_portal_configuration(
            self.project_id,
            document=chosen,
            status="draft",
            expected_revision=0,
            updated_by_user_id=None,
        )

        self.store.migrate_dashboard_templates_to_portal_configurations()
        self.store.migrate_dashboard_templates_to_portal_configurations()

        configuration = self.store.get_portal_configuration(self.project_id)
        self.assertEqual(
            {
                "status": configuration["status"],
                "revision": configuration["revision"],
                "document": configuration["document"],
            },
            {"status": "draft", "revision": 1, "document": chosen},
        )

    def test_migrating_twice_does_not_change_the_migrated_configuration(self):
        template = self.store.create_dashboard_template(
            project_id=self.project_id,
            name="Vigente",
            created_by="analyst@example.local",
        )
        self.publish(template["id"])

        self.store.migrate_dashboard_templates_to_portal_configurations()
        first = self.store.get_portal_configuration(self.project_id)
        self.store.migrate_dashboard_templates_to_portal_configurations()

        self.assertEqual(self.store.get_portal_configuration(self.project_id), first)


FULL_PORTAL_DOCUMENT = {
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
        "charts": {"enabled": True, "label": "Resultados", "items": [GRID_CHART]},
        "tables": {"enabled": True, "label": "Detalle", "items": [SYSTEM_TABLE]},
        "downloads": {"enabled": True, "label": "Descargas"},
    },
}

PORTAL_PAYLOAD_KEYS = (
    "project",
    "publication",
    "period",
    "results_state",
    "results_block",
)


class PortalCutoverApiTests(unittest.TestCase):
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
        self.template = self.store.create_dashboard_template(
            project_id=self.project_id,
            name="Plantilla heredada",
            created_by="analyst@example.local",
        )
        self.analyst = self.logged_in_client("analyst@example.local", "analyst pass")
        self.publication = post_json_with_csrf(
            self.analyst,
            f"/api/runs/{self.run['id']}/publications",
            {
                "dashboard_template_id": self.template["id"],
                "public_title": "Plan operativo enero",
                "analyst_notes": "Aprobado.",
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
        self.assertEqual(login_json_with_csrf(client, email, password).status_code, 200)
        return client

    def configure_portal(self, document: dict) -> None:
        current = self.analyst.get(
            f"/api/projects/{self.project_id}/portal-configuration"
        ).json()["portal_configuration"]
        response = put_json_with_csrf(
            self.analyst,
            f"/api/projects/{self.project_id}/portal-configuration",
            {
                "document": document,
                "status": "active",
                "expected_revision": current["revision"],
            },
        )
        self.assertEqual(response.status_code, 200)

    def portal_detail(self) -> dict:
        external = self.logged_in_client("external@example.local", "external pass")
        response = external.get(
            f"/api/client/projects/{self.project_id}"
            f"/publications/{self.publication['id']}"
        )
        self.assertEqual(response.status_code, 200)
        return response.json()

    def test_the_portal_renders_every_configured_section(self):
        self.configure_portal(FULL_PORTAL_DOCUMENT)

        detail = self.portal_detail()

        block = detail["results_block"]
        self.assertEqual(
            {
                "results_state": detail["results_state"],
                "labels": block["labels"],
                "kpis": [kpi["id"] for kpi in block["kpis"]],
                "charts": [chart["id"] for chart in block["charts"]],
                "tables": [table["id"] for table in block["tables"]],
                "downloads": [download["label"] for download in detail["downloads"]],
            },
            {
                "results_state": "available",
                "labels": {
                    "kpis": "Resumen",
                    "charts": "Resultados",
                    "tables": "Detalle",
                    "downloads": "Descargas",
                },
                "kpis": ["beneficio_total"],
                "charts": ["intercambio_red"],
                "tables": ["despacho_sistema"],
                "downloads": ["summary.json"],
            },
        )

    def test_the_portal_no_longer_exposes_internal_run_or_template_records(self):
        self.configure_portal(FULL_PORTAL_DOCUMENT)

        detail = self.portal_detail()

        for absent in ["results", "template", "run", "scenario", "scenario_version"]:
            self.assertNotIn(absent, detail)

    def test_the_preview_and_the_portal_share_the_same_builder(self):
        self.configure_portal(FULL_PORTAL_DOCUMENT)

        preview = self.analyst.get(
            f"/api/publications/{self.publication['id']}/preview"
        ).json()
        detail = self.portal_detail()

        self.assertEqual(
            {key: preview[key] for key in PORTAL_PAYLOAD_KEYS},
            {key: detail[key] for key in PORTAL_PAYLOAD_KEYS},
        )
        self.assertEqual(
            [download["label"] for download in preview["downloads"]],
            [download["label"] for download in detail["downloads"]],
        )

    def test_the_dashboard_template_no_longer_decides_what_the_client_sees(self):
        self.configure_portal(FULL_PORTAL_DOCUMENT)
        before = self.portal_detail()

        put_json_with_csrf(
            self.analyst,
            f"/api/dashboard-templates/{self.template['id']}",
            {
                "name": "Plantilla heredada",
                "show_summary": False,
                "show_price_chart": False,
                "show_grid_chart": False,
                "show_renewable_chart": False,
                "show_bess_chart": False,
                "show_hydro_chart": False,
                "show_profit_chart": False,
                "show_system_dispatch_table": False,
                "show_asset_dispatch_table": False,
                "table_preview_limit": 1,
            },
        )

        self.assertEqual(self.portal_detail(), before)

    def test_a_disabled_download_section_hides_the_allowed_artifact(self):
        document = deepcopy(FULL_PORTAL_DOCUMENT)
        document["sections"]["downloads"]["enabled"] = False
        self.configure_portal(document)

        self.assertEqual(self.portal_detail()["downloads"], [])

    def test_no_canonical_key_artifact_path_or_database_field_crosses_the_boundary(self):
        self.configure_portal(FULL_PORTAL_DOCUMENT)

        serialized = json.dumps(self.portal_detail())

        for forbidden in [
            "objective_value_usd",
            "solver_status",
            "termination_status",
            "grid_import_mw",
            "all_series",
            "plot_series",
            "dashboard_template_id",
            "scenario_version_id",
            "run_id",
            "allowed_artifact_types",
            "analyst@example.local",
            str(self.artifact_root),
            "summary.json artifact",
        ]:
            self.assertNotIn(forbidden, serialized)

    def test_an_unreadable_run_reports_an_unavailable_state_without_detail(self):
        self.configure_portal(FULL_PORTAL_DOCUMENT)
        for artifact in self.store.list_run_artifacts(self.run["id"]):
            Path(artifact["path"]).unlink()
        for table in [
            "run_summary_result_indexes",
            "run_dispatch_result_indexes",
            "run_asset_dispatch_result_indexes",
        ]:
            self.store.connection.execute(
                f"DELETE FROM {table} WHERE run_id = ?", (self.run["id"],)
            )
        self.store.connection.commit()

        detail = self.portal_detail()

        self.assertEqual(
            {
                "results_state": detail["results_state"],
                "results_block": detail["results_block"],
            },
            {"results_state": "unavailable", "results_block": None},
        )
        self.assertNotIn("summary.json", json.dumps(detail))


class PortalConfigurationBootstrapMigrationTests(unittest.TestCase):
    """The cutover migration runs once, on the databases that predate it."""

    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.artifact_root = Path(self.temporary_directory.name) / "artifacts"
        self.database_url = (
            f"sqlite:///{Path(self.temporary_directory.name) / 'analyst.sqlite3'}"
        )
        store = AnalystStore(self.database_url)
        run = create_completed_run_with_result_artifacts(store, self.artifact_root)
        self.project_id = store.get_run_lineage(run["id"])["project_id"]
        template = store.create_dashboard_template(
            project_id=self.project_id,
            name="Vigente",
            show_summary=True,
            show_price_chart=False,
            show_grid_chart=True,
            show_renewable_chart=False,
            show_bess_chart=False,
            show_hydro_chart=False,
            show_profit_chart=False,
            show_system_dispatch_table=False,
            show_asset_dispatch_table=False,
            created_by="analyst@example.local",
        )
        publication = store.create_publication_draft(
            run_id=run["id"],
            dashboard_template_id=template["id"],
            public_title="Plan operativo enero",
        )
        store.publish_publication(
            publication["id"], published_by="analyst@example.local"
        )
        store.close()
        self.opened_stores: list[AnalystStore] = []

    def tearDown(self):
        for store in self.opened_stores:
            store.close()
        self.temporary_directory.cleanup()

    def reopen(self) -> AnalystStore:
        store = AnalystStore(self.database_url)
        self.opened_stores.append(store)
        return store

    def forget_the_cutover_migration(self) -> None:
        store = AnalystStore(self.database_url)
        store.connection.execute("DELETE FROM schema_migrations")
        store.connection.commit()
        store.close()

    def test_a_database_that_predates_the_cutover_is_migrated_when_it_opens(self):
        self.forget_the_cutover_migration()

        store = self.reopen()

        configuration = store.get_portal_configuration(self.project_id)
        self.assertEqual(
            {
                "status": configuration["status"],
                "charts": [
                    item["chart_key"]
                    for item in configuration["document"]["sections"]["charts"]["items"]
                ],
            },
            {"status": "active", "charts": ["grid_import_export"]},
        )

    def test_a_project_published_after_the_cutover_is_never_configured_for_the_analyst(
        self,
    ):
        store = self.reopen()

        self.assertIsNone(store.get_portal_configuration(self.project_id))


class PortalCatalogApiTests(unittest.TestCase):
    """The analyst UI can only offer what the backend catalogs declare."""

    def setUp(self):
        self.store = AnalystStore("sqlite:///:memory:")
        self.store.create_user(
            email="analyst@example.local",
            display_name="Analyst",
            role="analyst",
            password_hash=hash_password("analyst pass"),
        )
        self.client = TestClient(create_app(store=self.store, auth_enabled=True))
        self.assertEqual(
            login_json_with_csrf(
                self.client, "analyst@example.local", "analyst pass"
            ).status_code,
            200,
        )

    def tearDown(self):
        self.store.close()

    def test_the_catalog_lists_every_publishable_chart_and_table(self):
        response = self.client.get("/api/portal-catalogs")

        self.assertEqual(response.status_code, 200)
        catalogs = response.json()
        self.assertEqual(
            [chart["key"] for chart in catalogs["charts"]],
            list(PORTAL_CHART_CATALOG),
        )
        self.assertEqual(
            [table["key"] for table in catalogs["tables"]],
            list(PORTAL_TABLE_CATALOG),
        )

    def test_each_catalog_entry_carries_the_keys_the_document_may_declare(self):
        catalogs = self.client.get("/api/portal-catalogs").json()

        grid = next(
            chart
            for chart in catalogs["charts"]
            if chart["key"] == "grid_import_export"
        )
        system = next(
            table
            for table in catalogs["tables"]
            if table["key"] == "system_dispatch"
        )
        self.assertEqual(
            {
                "label": grid["label"],
                "series": [series["key"] for series in grid["series"]],
                "unit": grid["series"][0]["unit"],
            },
            {
                "label": "Intercambio con la red",
                "series": ["grid_import_mw", "grid_export_mw", "net_grid_export_mw"],
                "unit": "MW",
            },
        )
        self.assertIn(
            {"key": "grid_import_mw", "label": "Grid import mw", "unit": "MW"},
            system["columns"],
        )

    def test_the_catalog_never_offers_the_forbidden_bulk_keys(self):
        serialized = json.dumps(self.client.get("/api/portal-catalogs").json())

        self.assertNotIn("all_series", serialized)
        self.assertNotIn("plot_series", serialized)

    def test_an_external_user_cannot_read_the_catalog(self):
        self.store.create_user(
            email="external@example.local",
            display_name="External",
            role="external",
            password_hash=hash_password("external pass"),
        )
        external = TestClient(create_app(store=self.store, auth_enabled=True))
        self.assertEqual(
            login_json_with_csrf(
                external, "external@example.local", "external pass"
            ).status_code,
            200,
        )

        self.assertEqual(external.get("/api/portal-catalogs").status_code, 403)


if __name__ == "__main__":
    unittest.main()
