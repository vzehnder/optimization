import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient
from openpyxl import Workbook

from app.main import create_app
from app.validation import ValidationResult

REPO_ROOT = Path(__file__).resolve().parents[1]


class StubValidationService:
    def validate_text(self, candidate_text):
        return ValidationResult(
            ok=True,
            phase="julia",
            message="Validation succeeded",
            payload={"status": "ok"},
        )


def make_renewables_xlsx_bytes(rows):
    workbook = Workbook()
    default_sheet = workbook.active
    default_sheet.title = "Notes"
    default_sheet.append(["ignored"])
    sheet = workbook.create_sheet("Renewables")
    for row in rows:
        sheet.append(row)
    from io import BytesIO

    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


class TS2AcceptanceTests(unittest.TestCase):
    """BESS-TS2-009: closing proof for the TS-2 generic time-series catalog.

    Exercises one continuous library story: a multi-signal CSV import and a
    single-signal XLSX import (with sheet selection) both become first-class,
    project-browsable database objects; a manual value edit and a file
    replacement each create a new revision with a recalculated content hash
    while leaving prior revisions (and their hashes) intact as stable audit
    anchors; and validation failures during import, edit and replacement all
    surface with source row/column (or edit/period) context without mutating
    the set.
    """

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        input_source_root = Path(self.temp_dir.name) / "input-sources"
        self.client = TestClient(
            create_app(
                validation_service=StubValidationService(),
                database_url="sqlite:///:memory:",
                input_source_root=input_source_root,
            )
        )
        self.project = self.client.post(
            "/api/projects", json={"name": "TS-2 Acceptance"}
        ).json()
        self.scenario = self.client.post(
            f"/api/projects/{self.project['id']}/scenarios",
            json={"name": "Catalog import"},
        ).json()
        self.client.post(
            f"/api/scenarios/{self.scenario['id']}/draft",
            json={
                "document": {
                    "schema_version": "bess_editor_draft.v1",
                    "case": {"name": "ts2_acceptance_case"},
                    "pcc": {"id": "bus_1", "type": "bus"},
                    "grid": {"id": "grid_1"},
                    "assets": [],
                    "time_series": {"sources": []},
                    "solver": {"name": "HiGHS", "options": {}},
                }
            },
        )

    def test_ts2_catalog_library_story_end_to_end(self):
        project_id = self.project["id"]
        scenario_id = self.scenario["id"]

        # 1. CSV import: a multi-signal package becomes a first-class set.
        price_demand_csv = (
            "period_start,hours,spot_price,demand\n"
            "2026-01-01T00:00:00,1.0,55.0,12.0\n"
            "2026-01-01T01:00:00,1.0,60.0,14.0\n"
        )
        upload_response = self.client.post(
            f"/api/scenarios/{scenario_id}/draft/time-series-sources/upload",
            files={"source_file": ("price_demand.csv", price_demand_csv, "text/csv")},
        )
        self.assertEqual(upload_response.status_code, 201)
        csv_source = upload_response.json()["source"]

        import_response = self.client.post(
            f"/api/scenarios/{scenario_id}/draft/time-series-sources/{csv_source['id']}/catalog-import",
            json={
                "set_name": "Price and demand Jan 2026",
                "version_label": "v1",
                "data_kind": "real",
                "timezone": "America/Santiago",
                "timestamp_column": "period_start",
                "duration_hours_column": "hours",
                "signal_mappings": [
                    {"source_column": "spot_price", "signal_key": "price_usd_per_mwh"},
                    {"source_column": "demand", "signal_key": "load_demand_mw"},
                ],
            },
        )
        self.assertEqual(import_response.status_code, 201)
        set_a = import_response.json()["time_series_set"]
        self.assertEqual(set_a["revision_number"], 1)
        self.assertTrue(set_a["content_hash"].startswith("sha256:"))
        set_a_signal_keys = {signal["signal_key"] for signal in set_a["signals"]}
        self.assertEqual(set_a_signal_keys, {"price_usd_per_mwh", "load_demand_mw"})
        set_a_original_hash = set_a["content_hash"]

        # A CSV import with a row/column-tied validation failure must not
        # leave a partial set behind, and the error must name the bad row.
        bad_csv = (
            "period_start,hours,spot_price\n"
            "2026-01-01T00:00:00,1.0,55.0\n"
            "2026-01-01T00:00:00,1.0,61.0\n"
        )
        bad_upload_response = self.client.post(
            f"/api/scenarios/{scenario_id}/draft/time-series-sources/upload",
            files={"source_file": ("price_dupe.csv", bad_csv, "text/csv")},
        )
        bad_source = bad_upload_response.json()["source"]
        bad_import_response = self.client.post(
            f"/api/scenarios/{scenario_id}/draft/time-series-sources/{bad_source['id']}/catalog-import",
            json={
                "set_name": "Bad price set",
                "version_label": "v1",
                "data_kind": "real",
                "timezone": "America/Santiago",
                "timestamp_column": "period_start",
                "duration_hours_column": "hours",
                "signal_mappings": [
                    {"source_column": "spot_price", "signal_key": "price_usd_per_mwh"}
                ],
            },
        )
        self.assertEqual(bad_import_response.status_code, 400)
        self.assertIn("price_dupe.csv", bad_import_response.json()["detail"])
        self.assertIn("row 3", bad_import_response.json()["detail"])
        self.assertIn("duplicate timestamp", bad_import_response.json()["detail"])

        # 2. XLSX import with sheet selection: a single-signal set.
        renewables_xlsx = make_renewables_xlsx_bytes(
            [
                ["period_start", "hours", "available_power"],
                ["2026-01-01T00:00:00", 1.0, 30.0],
                ["2026-01-01T01:00:00", 1.0, 45.0],
            ]
        )
        xlsx_upload_response = self.client.post(
            f"/api/scenarios/{scenario_id}/draft/time-series-sources/upload",
            data={"sheet_name": "Renewables"},
            files={
                "source_file": (
                    "renewables.xlsx",
                    renewables_xlsx,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
        )
        self.assertEqual(xlsx_upload_response.status_code, 201)
        xlsx_source = xlsx_upload_response.json()["source"]
        self.assertEqual(xlsx_source["kind"], "xlsx")
        self.assertEqual(xlsx_source["selected_sheet"], "Renewables")
        self.assertEqual(xlsx_source["available_sheets"], ["Notes", "Renewables"])

        xlsx_import_response = self.client.post(
            f"/api/scenarios/{scenario_id}/draft/time-series-sources/{xlsx_source['id']}/catalog-import",
            json={
                "set_name": "Renewable availability Jan 2026",
                "version_label": "v1",
                "data_kind": "real",
                "timezone": "America/Santiago",
                "timestamp_column": "period_start",
                "duration_hours_column": "hours",
                "signal_mappings": [
                    {
                        "source_column": "available_power",
                        "signal_key": "renewable_available_power_mw",
                    }
                ],
            },
        )
        self.assertEqual(xlsx_import_response.status_code, 201)
        set_b = xlsx_import_response.json()["time_series_set"]
        self.assertEqual(set_b["revision_number"], 1)
        set_b_original_hash = set_b["content_hash"]
        self.assertEqual(set_b["source"]["selected_sheet"], "Renewables")

        # 3. Catalog visibility: both sets are browsable per project.
        catalog = self.client.get(
            f"/api/projects/{project_id}/time-series-sets"
        ).json()["time_series_sets"]
        self.assertEqual(
            {item["name"] for item in catalog},
            {"Price and demand Jan 2026", "Renewable availability Jan 2026"},
        )
        catalog_by_name = {item["name"]: item for item in catalog}
        self.assertEqual(catalog_by_name["Price and demand Jan 2026"]["signal_count"], 2)
        self.assertEqual(catalog_by_name["Price and demand Jan 2026"]["period_count"], 2)
        self.assertEqual(
            catalog_by_name["Renewable availability Jan 2026"]["signal_count"], 1
        )

        # 4. Manual edit on set A creates revision 2 and a fresh hash while
        # revision 1's hash stays a stable audit anchor.
        edit_response = self.client.put(
            f"/api/projects/{project_id}/time-series-sets/{set_a['id']}/values",
            json={
                "edits": [
                    {
                        "period_index": 0,
                        "signal_key": "price_usd_per_mwh",
                        "value": "57.5",
                    }
                ],
                "change_summary": "Corrected spike on Jan 1st",
            },
        )
        self.assertEqual(edit_response.status_code, 200)
        set_a_after_edit = edit_response.json()["time_series_set"]
        self.assertEqual(set_a_after_edit["revision_number"], 2)
        self.assertNotEqual(set_a_after_edit["content_hash"], set_a_original_hash)

        set_a_revisions = self.client.get(
            f"/api/projects/{project_id}/time-series-sets/{set_a['id']}/revisions"
        ).json()["time_series_set_revisions"]
        self.assertEqual(
            [revision["revision_number"] for revision in set_a_revisions], [2, 1]
        )
        self.assertEqual(set_a_revisions[1]["content_hash"], set_a_original_hash)
        self.assertEqual(set_a_revisions[0]["superseded_revision_number"], 1)

        # An invalid manual edit is rejected with edit/period context and
        # leaves set A untouched at revision 2.
        invalid_edit_response = self.client.put(
            f"/api/projects/{project_id}/time-series-sets/{set_a['id']}/values",
            json={
                "edits": [
                    {
                        "period_index": 1,
                        "signal_key": "load_demand_mw",
                        "value": "-3.0",
                    }
                ]
            },
        )
        self.assertEqual(invalid_edit_response.status_code, 400)
        self.assertIn("must be nonnegative", invalid_edit_response.json()["detail"])
        set_a_detail_after_bad_edit = self.client.get(
            f"/api/projects/{project_id}/time-series-sets/{set_a['id']}"
        ).json()["time_series_set"]
        self.assertEqual(set_a_detail_after_bad_edit["revision_number"], 2)
        self.assertEqual(
            set_a_detail_after_bad_edit["content_hash"], set_a_after_edit["content_hash"]
        )

        # 5. File replacement on set B creates revision 2, keeps identity
        # stable, and revision 1's hash remains the original audit anchor.
        corrected_renewables_csv = (
            "period_start,hours,available_power\n"
            "2026-01-01T00:00:00,1.0,32.0\n"
            "2026-01-01T01:00:00,1.0,48.0\n"
        )
        replace_upload_response = self.client.post(
            f"/api/projects/{project_id}/time-series-sets/{set_b['id']}/replace/upload",
            files={
                "source_file": (
                    "renewables_corrected.csv",
                    corrected_renewables_csv,
                    "text/csv",
                )
            },
        )
        self.assertEqual(replace_upload_response.status_code, 201)
        replacement_source = replace_upload_response.json()["source"]

        replace_response = self.client.post(
            f"/api/projects/{project_id}/time-series-sets/{set_b['id']}/replace",
            json={
                "source": replacement_source,
                "data_kind": "real",
                "timezone": "America/Santiago",
                "timestamp_column": "period_start",
                "duration_hours_column": "hours",
                "signal_mappings": [
                    {
                        "source_column": "available_power",
                        "signal_key": "renewable_available_power_mw",
                    }
                ],
                "change_summary": "Corrected sensor reading",
            },
        )
        self.assertEqual(replace_response.status_code, 200)
        set_b_after_replace = replace_response.json()["time_series_set"]
        self.assertEqual(set_b_after_replace["name"], set_b["name"])
        self.assertEqual(set_b_after_replace["version_label"], set_b["version_label"])
        self.assertEqual(set_b_after_replace["revision_number"], 2)
        self.assertNotEqual(set_b_after_replace["content_hash"], set_b_original_hash)
        self.assertEqual(
            set_b_after_replace["source"]["original_filename"], "renewables_corrected.csv"
        )

        set_b_revisions = self.client.get(
            f"/api/projects/{project_id}/time-series-sets/{set_b['id']}/revisions"
        ).json()["time_series_set_revisions"]
        self.assertEqual(
            [revision["revision_number"] for revision in set_b_revisions], [2, 1]
        )
        self.assertEqual(set_b_revisions[1]["content_hash"], set_b_original_hash)
        self.assertEqual(set_b_revisions[0]["superseded_revision_number"], 1)

        # A replacement upload with a row-tied validation failure is rejected
        # and leaves set B untouched at revision 2 with its own hash stable.
        duplicate_renewables_csv = (
            "period_start,hours,available_power\n"
            "2026-01-01T00:00:00,1.0,32.0\n"
            "2026-01-01T00:00:00,1.0,48.0\n"
        )
        bad_replace_upload_response = self.client.post(
            f"/api/projects/{project_id}/time-series-sets/{set_b['id']}/replace/upload",
            files={
                "source_file": (
                    "renewables_dupe.csv",
                    duplicate_renewables_csv,
                    "text/csv",
                )
            },
        )
        bad_replacement_source = bad_replace_upload_response.json()["source"]
        bad_replace_response = self.client.post(
            f"/api/projects/{project_id}/time-series-sets/{set_b['id']}/replace",
            json={
                "source": bad_replacement_source,
                "data_kind": "real",
                "timezone": "America/Santiago",
                "timestamp_column": "period_start",
                "duration_hours_column": "hours",
                "signal_mappings": [
                    {
                        "source_column": "available_power",
                        "signal_key": "renewable_available_power_mw",
                    }
                ],
            },
        )
        self.assertEqual(bad_replace_response.status_code, 400)
        self.assertIn("renewables_dupe.csv", bad_replace_response.json()["detail"])
        self.assertIn("row 3", bad_replace_response.json()["detail"])

        set_b_final_detail = self.client.get(
            f"/api/projects/{project_id}/time-series-sets/{set_b['id']}"
        ).json()["time_series_set"]
        self.assertEqual(set_b_final_detail["revision_number"], 2)
        self.assertEqual(
            set_b_final_detail["content_hash"], set_b_after_replace["content_hash"]
        )

        # 6. Final catalog visibility reflects the settled state of both sets.
        final_catalog = self.client.get(
            f"/api/projects/{project_id}/time-series-sets"
        ).json()["time_series_sets"]
        final_catalog_by_name = {item["name"]: item for item in final_catalog}
        self.assertEqual(
            final_catalog_by_name["Price and demand Jan 2026"]["revision_number"], 2
        )
        self.assertEqual(
            final_catalog_by_name["Renewable availability Jan 2026"]["revision_number"], 2
        )

    def test_ts2_documentation_tracker_and_issue_are_done(self):
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        issue = (
            REPO_ROOT
            / "docs"
            / "series_tiempo"
            / "iter2"
            / "issues"
            / "BESS-TS2-009-finalize-ts2-acceptance-suite-and-docs.md"
        ).read_text(encoding="utf-8")
        tracker = (
            REPO_ROOT / "docs" / "series_tiempo" / "iter2" / "issues" / "tracker_ts2.md"
        ).read_text(encoding="utf-8")
        manual = (
            REPO_ROOT / "docs" / "series_tiempo" / "iter2" / "pruebas_manuales_ts2.md"
        ).read_text(encoding="utf-8")

        self.assertIn("TS-2: Generic Time-Series Catalog", readme)
        self.assertIn("tests.test_ts2_acceptance", readme)

        self.assertIn("Status: Done", issue)
        self.assertNotIn("- [ ]", issue)
        self.assertIn("tests.test_ts2_acceptance", issue)

        self.assertIn(
            "| BESS-TS2-009 | Finalize TS-2 Acceptance Suite And Docs | AFK | ready-for-agent | Done |",
            tracker,
        )
        self.assertIn("BESS-TS2-009 | Todo -> Done", tracker)
        self.assertIn("Final TS-2 Verification", tracker)
        self.assertIn("tests.test_ts2_acceptance", tracker)

        self.assertIn("Cierre TS-2", manual)
        self.assertIn("tests.test_ts2_acceptance", manual)


if __name__ == "__main__":
    unittest.main()
