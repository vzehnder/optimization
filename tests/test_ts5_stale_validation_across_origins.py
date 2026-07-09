"""BESS-TS5-005: staleness proofs across storage origins.

Proves the TS-3 fail-closed staleness contract (`evaluate_case_input_variant_staleness`,
`VariantStaleError`) and the hydraulic v3 staleness contract
(`hierarchy_stale_state`, `_stale_validation_after_hydraulic_edit`, the
`promote_hydraulic_diagram` fail-closed gate) survive TS-5 migration: a bound
series set going stale must block runs regardless of whether the set is
natively created, extracted from a legacy draft (TS5-001), migrated from a
legacy hydraulic table (TS5-004), or read live through the legacy hydraulic
adapter (TS5-002) during the compatibility window.
"""

import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from app.persistence import AnalystStore
from app.time_series_catalog import (
    CatalogImportRequest,
    CatalogSignalMappingRequest,
    CatalogValueEdit,
    prepare_time_series_catalog_import,
)
from app.validation import ValidationResult
from app.variant_staleness import VariantStaleError


def grid_battery_draft_document():
    return {
        "schema_version": "bess_editor_draft.v1",
        "case": {"name": "grid_battery_case", "description": ""},
        "pcc": {"id": "bus_1", "type": "bus"},
        "grid": {
            "id": "grid_1",
            "import_power_max_mw": 10.0,
            "export_power_max_mw": 10.0,
            "prevent_simultaneous_grid_import_export": True,
        },
        "assets": [
            {
                "id": "battery_1",
                "type": "battery",
                "charge_power_max_mw": 4.0,
                "discharge_power_max_mw": 4.0,
                "energy_min_mwh": 0.0,
                "energy_max_mwh": 8.0,
                "initial_energy_mwh": 4.0,
                "charge_efficiency": 0.95,
                "discharge_efficiency": 0.95,
                "degradation_cost_per_mwh_delta_soc": 0.0,
                "terminal_condition": "none",
                "prevent_simultaneous_charge_discharge": True,
                "degradation_linear_delta_soc": True,
            },
        ],
        "time_series": {"sources": []},
        "solver": {"name": "HiGHS", "options": {}},
    }


def price_import_request(*, version_label="v1"):
    return CatalogImportRequest(
        set_name="Spot price",
        version_label=version_label,
        data_kind="real",
        timezone="America/Santiago",
        timestamp_column="period_start",
        duration_hours_column="hours",
        signal_mappings=[
            CatalogSignalMappingRequest(source_column="spot_price", signal_key="import_price_usd_per_mwh"),
        ],
    )


def price_rows(start, count, *, value=50.0):
    rows = []
    for hour in range(count):
        instant = start + timedelta(hours=hour)
        rows.append(
            {
                "period_start": instant.isoformat(),
                "hours": "1.0",
                "spot_price": str(value + hour),
            }
        )
    return rows


class DraftBackedCaseStalenessMixin:
    """Shared fixture: a draft-backed case with the price signal natively bound.

    Subclasses add a second binding sourced from a different storage origin
    (extracted or migrated) and prove editing it also trips staleness,
    exactly like editing the native price set does.
    """

    def setUp(self):
        self.store = AnalystStore("sqlite:///:memory:")
        self.addCleanup(self.store.close)
        self.project = self.store.create_project(name="TS5-005 project")
        self.scenario = self.store.create_scenario(
            project_id=self.project["id"], name="TS5-005 scenario"
        )
        self.store.create_or_replace_scenario_draft(
            scenario_id=self.scenario["id"], document=grid_battery_draft_document()
        )
        self.case = self.store.get_or_create_case_for_scenario(self.scenario["id"])
        self.variant = self.store.get_or_create_default_input_variant(self.case["id"])

        prepared_price = prepare_time_series_catalog_import(
            rows=price_rows(datetime(2026, 1, 1), 3),
            request=price_import_request(),
        )
        self.price_set = self.store.import_time_series_catalog_set(
            scenario_id=self.scenario["id"],
            source={
                "id": "csv_source_price",
                "original_filename": "price.csv",
                "media_type": "text/csv",
                "checksum": "sha256:price",
            },
            prepared_import=prepared_price,
        )
        self.store.upsert_case_time_series_binding(
            case_input_variant_id=self.variant["id"],
            signal_key="import_price_usd_per_mwh",
            time_series_set_id=self.price_set["id"],
        )

    def _materialize(self):
        return self.store.materialize_system_case_for_variant(
            scenario_id=self.scenario["id"],
            case_input_variant_id=self.variant["id"],
            range_start=self.price_set["horizon"]["start"],
            range_end=self.price_set["horizon"]["end"],
        )

    def _staleness(self):
        return self.store.evaluate_case_input_variant_staleness(
            scenario_id=self.scenario["id"], case_input_variant_id=self.variant["id"]
        )


class ExtractedSeriesStalenessTests(DraftBackedCaseStalenessMixin, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.extracted_set = self._extract_load_series()
        self.store.upsert_case_time_series_binding(
            case_input_variant_id=self.variant["id"],
            signal_key="load_demand_mw",
            entity_type="component:load",
            entity_id="load_1",
            time_series_set_id=self.extracted_set["id"],
        )

    def _extract_load_series(self):
        from app.time_series_ingestion import (
            apply_time_series_mapping,
            attach_time_series_source,
            ingest_csv_source,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            input_source_root = Path(temp_dir) / "input-sources"
            draft = self.store.get_scenario_draft(self.scenario["id"])
            source = ingest_csv_source(
                draft_document=draft["document"],
                original_filename="legacy_load.csv",
                content_type="text/csv",
                content=(
                    b"period_start,hours,load_1_demand\n"
                    b"2026-01-01T00:00:00,1.0,10.0\n"
                    b"2026-01-01T01:00:00,1.0,12.0\n"
                    b"2026-01-01T02:00:00,1.0,14.0\n"
                ),
                input_source_root=input_source_root,
            )
            updated_document = attach_time_series_source(draft["document"], source)
            self.store.update_scenario_draft(
                scenario_id=self.scenario["id"], document=updated_document
            )
            mapping = {
                "timestamp": "period_start",
                "duration_hours": "hours",
                "load_demand_mw": {"load_1": "load_1_demand"},
            }
            draft = self.store.get_scenario_draft(self.scenario["id"])
            mapped_document, mapped_source = apply_time_series_mapping(
                document=draft["document"],
                source_id=source["id"],
                mapping=mapping,
                input_source_root=input_source_root,
            )
            self.store.update_scenario_draft(
                scenario_id=self.scenario["id"], document=mapped_document
            )
            return self.store.extract_draft_time_series_set(
                scenario_id=self.scenario["id"],
                source_id=mapped_source["id"],
                set_name="Legacy load series",
                version_label="v1",
                data_kind="real",
                timezone_name="America/Santiago",
            )

    def test_editing_extracted_series_marks_bound_variant_stale_like_a_native_set(self):
        self._materialize()
        self.assertFalse(self._staleness()["stale"])

        self.store.edit_time_series_set_values(
            project_id=self.project["id"],
            time_series_set_id=self.extracted_set["id"],
            edits=[
                CatalogValueEdit(period_index=0, signal_key="load_demand_mw", value_text="999.0")
            ],
        )

        staleness = self._staleness()
        self.assertTrue(staleness["stale"])
        self.assertEqual(
            [reason["dependency_type"] for reason in staleness["reasons"]],
            ["time_series_set"],
        )
        with self.assertRaises(VariantStaleError):
            self._materialize()

    def test_topology_edit_still_marks_variant_stale_for_a_case_with_an_extracted_series(self):
        self._materialize()

        document = grid_battery_draft_document()
        document["assets"][0]["charge_power_max_mw"] = 999.0
        self.store.update_scenario_draft(scenario_id=self.scenario["id"], document=document)

        staleness = self._staleness()
        self.assertTrue(staleness["stale"])
        self.assertEqual(
            sorted(reason["dependency_type"] for reason in staleness["reasons"]),
            ["parameters"],
        )


class MigratedHydraulicSeriesStalenessTests(DraftBackedCaseStalenessMixin, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.legacy_set_id = self._seed_legacy_inflow_set(values=[5.0, 6.0, 7.0])
        migration = self.store.migrate_hydraulic_time_series_set(
            project_id=self.project["id"],
            hydraulic_time_series_set_id=self.legacy_set_id,
            migrated_by="tester",
        )
        self.migrated_set = migration["time_series_set"]
        self.store.upsert_case_time_series_binding(
            case_input_variant_id=self.variant["id"],
            signal_key="natural_inflow_m3s",
            entity_type="hydraulic_node",
            entity_id="reservoir_alpha",
            time_series_set_id=self.migrated_set["id"],
        )

    def _seed_legacy_inflow_set(self, *, values):
        now = "2026-01-01T00:00:00+00:00"
        cursor = self.store.connection.execute(
            """
            INSERT INTO hydraulic_time_series_sets (
                project_id, entity_type, entity_id, signal_key, version_number,
                version_label, content_hash, status, created_at, updated_at,
                created_by, updated_by
            ) VALUES (?, 'hydraulic_node', 1, 'natural_inflow_m3s', 1, 'v1', 'legacy-seed-hash', 'draft', ?, ?, 'seed', 'seed')
            """,
            (self.project["id"], now, now),
        )
        set_id = int(cursor.lastrowid)
        for index, value in enumerate(values):
            self.store.connection.execute(
                """
                INSERT INTO hydraulic_time_series_points (
                    hydraulic_time_series_set_id, point_index, timestamp,
                    duration_hours, value
                ) VALUES (?, ?, ?, 1.0, ?)
                """,
                (set_id, index, f"2026-01-01T{index:02d}:00:00-03:00", float(value)),
            )
        self.store.connection.commit()
        return set_id

    def test_editing_migrated_series_marks_bound_variant_stale_like_a_native_set(self):
        self._materialize()
        self.assertFalse(self._staleness()["stale"])

        self.store.edit_time_series_set_values(
            project_id=self.project["id"],
            time_series_set_id=self.migrated_set["id"],
            edits=[
                CatalogValueEdit(period_index=0, signal_key="natural_inflow_m3s", value_text="999.0")
            ],
        )

        staleness = self._staleness()
        self.assertTrue(staleness["stale"])
        self.assertEqual(
            [reason["dependency_type"] for reason in staleness["reasons"]],
            ["time_series_set"],
        )
        with self.assertRaises(VariantStaleError):
            self._materialize()

    def test_migrating_the_legacy_set_again_does_not_disturb_an_already_validated_variant(self):
        """Migration is a side path: re-running it must not itself flip staleness."""
        self._materialize()
        self.assertFalse(self._staleness()["stale"])

        second_migration = self.store.migrate_hydraulic_time_series_set(
            project_id=self.project["id"],
            hydraulic_time_series_set_id=self.legacy_set_id,
            migrated_by="tester",
        )

        self.assertTrue(second_migration["already_migrated"])
        self.assertFalse(self._staleness()["stale"])


class StubValidationService:
    def validate_text(self, candidate_text):
        return ValidationResult(
            ok=True,
            phase="julia",
            message="Validation succeeded",
            payload={"status": "ok"},
        )

    def validate_file(self, candidate_path):
        raise AssertionError("file validation not expected in these tests")


class HydraulicV3DiagramFixtureMixin:
    """Shared reservoir+junction+plant v3 diagram fixture (HTTP-level)."""

    def _create_hydraulic_scenario(self):
        self.store = AnalystStore("sqlite:///:memory:")
        self.addCleanup(self.store.close)
        self.client = TestClient(
            create_app(validation_service=StubValidationService(), store=self.store)
        )
        self.project = self.client.post("/api/projects", json={"name": "Hydro Project"}).json()
        self.scenario = self.client.post(
            f"/api/projects/{self.project['id']}/scenarios",
            json={"name": "Hydraulic base case"},
        ).json()

    def _diagram_nodes(self, *, inflow=None):
        return [
            {
                "component_type": "reservoir",
                "technical_key": "reservoir_alpha",
                "display_name": "Reservoir Alpha",
                "x": 120.0,
                "y": 80.0,
                "reservoir": {
                    "storage_min_hm3": 5.0,
                    "storage_max_hm3": 50.0,
                    "initial_storage_hm3": 20.0,
                    "terminal_condition": "none",
                    "terminal_water_value_usd_per_hm3": 0.0,
                },
                "storage_elevation_curve": {
                    "version_label": "v1",
                    "points": [
                        {"x_value": 5.0, "y_value": 700.0},
                        {"x_value": 50.0, "y_value": 760.0},
                    ],
                },
                **({"natural_inflow_series": inflow} if inflow is not None else {}),
            },
            {
                "component_type": "junction",
                "technical_key": "junction_in",
                "display_name": "Intake",
                "x": 300.0,
                "y": 80.0,
            },
            {
                "component_type": "junction",
                "technical_key": "junction_out",
                "display_name": "Tailrace",
                "x": 480.0,
                "y": 120.0,
            },
            {
                "component_type": "plant",
                "technical_key": "plant_laja",
                "display_name": "Plant Laja",
                "x": 390.0,
                "y": 200.0,
                "plant": {"non_modeled": False, "max_power_mw": 30.0},
                "units": [
                    {
                        "technical_key": "unit_1",
                        "display_name": "Unit 1",
                        "is_active": True,
                        "intake_node_key": "junction_in",
                        "discharge_node_key": "junction_out",
                        "min_power_mw": 0.0,
                        "max_power_mw": 30.0,
                        "min_flow_m3s": 0.0,
                        "max_flow_m3s": 40.0,
                        "flow_power_curve": {
                            "version_label": "v1",
                            "points": [
                                {"x_value": 0.0, "y_value": 0.0},
                                {"x_value": 40.0, "y_value": 30.0},
                            ],
                        },
                    }
                ],
            },
        ]

    def _diagram_reaches(self):
        return [
            {
                "technical_key": "reach_reservoir_intake",
                "display_name": "Reservoir to intake",
                "from_node_key": "reservoir_alpha",
                "to_node_key": "junction_in",
                "reach_type": "river",
            }
        ]

    def _save_diagram(self, revision, *, nodes=None):
        return self.client.put(
            f"/api/scenarios/{self.scenario['id']}/hydraulic-diagram",
            json={
                "revision": revision,
                "nodes": nodes if nodes is not None else self._diagram_nodes(),
                "reaches": self._diagram_reaches(),
            },
        )

    def _seed_legacy_inflow_set(self, *, values):
        base_row = self.store.connection.execute(
            "SELECT hydraulic_node_id FROM case_hydraulic_nodes WHERE id = ?",
            (self.case_node_id,),
        ).fetchone()
        base_entity_id = int(base_row[0])
        now = "2026-01-01T00:00:00+00:00"
        cursor = self.store.connection.execute(
            """
            INSERT INTO hydraulic_time_series_sets (
                project_id, entity_type, entity_id, signal_key, version_number,
                version_label, content_hash, status, created_at, updated_at,
                created_by, updated_by
            ) VALUES (?, 'hydraulic_node', ?, 'natural_inflow_m3s', 1, 'v1', 'legacy-seed-hash', 'draft', ?, ?, 'seed', 'seed')
            """,
            (self.project["id"], base_entity_id, now, now),
        )
        set_id = int(cursor.lastrowid)
        for index, value in enumerate(values):
            self.store.connection.execute(
                """
                INSERT INTO hydraulic_time_series_points (
                    hydraulic_time_series_set_id, point_index, timestamp,
                    duration_hours, value
                ) VALUES (?, ?, ?, 1.0, ?)
                """,
                (set_id, index, f"2026-01-01T{index:02d}:00:00", float(value)),
            )
        self.store.connection.execute(
            """
            INSERT INTO case_hydraulic_time_series_bindings (
                case_id, entity_type, entity_id, signal_key,
                hydraulic_time_series_set_id, time_series_set_id, required,
                created_at, updated_at, created_by, updated_by
            ) VALUES (?, 'case_hydraulic_node', ?, 'natural_inflow_m3s', ?, NULL, 1, ?, ?, 'seed', 'seed')
            """,
            (self.case_id, self.case_node_id, set_id, now, now),
        )
        self.store.connection.commit()
        return set_id

    def _validate_v3(self):
        return self.client.post(
            f"/api/scenarios/{self.scenario['id']}/hydraulic-diagram/v3-preview"
        )

    def _promote(self):
        return self.client.post(
            f"/api/scenarios/{self.scenario['id']}/hydraulic-diagram/promote"
        )


class LegacyHydraulicBindingStalenessTests(HydraulicV3DiagramFixtureMixin, unittest.TestCase):
    """BESS-TS5-005 acceptance criterion 3: legacy (adapter-read) hydraulic
    bindings keep the promote-time fail-closed staleness gate during the
    TS5-002/003/004 compatibility window, even though the public API can no
    longer write new legacy rows (TS5-003)."""

    def setUp(self):
        self._create_hydraulic_scenario()
        created = self.client.post(
            f"/api/scenarios/{self.scenario['id']}/hydraulic-diagram"
        ).json()["diagram"]
        save_response = self._save_diagram(created["revision"])
        self.assertEqual(save_response.status_code, 200)
        diagram = save_response.json()["diagram"]
        self.case_id = diagram["optimization_case"]["id"]
        reservoir_node = next(
            node for node in diagram["nodes"] if node["component_type"] == "reservoir"
        )
        self.case_node_id = reservoir_node["entity_id"]
        self.legacy_set_id = self._seed_legacy_inflow_set(values=[5.0, 6.0])

    def test_legacy_bound_inflow_reads_through_adapter_and_validates_clean(self):
        reloaded = self.client.get(
            f"/api/scenarios/{self.scenario['id']}/hydraulic-diagram"
        ).json()["diagram"]
        inflow = reloaded["nodes"][0]["natural_inflow_series"]
        self.assertEqual(inflow["origin"], {"kind": "hydraulic_legacy"})
        self.assertEqual([point["value_m3s"] for point in inflow["points"]], [5.0, 6.0])

        preview = self._validate_v3()
        self.assertEqual(preview.status_code, 200)
        validation = preview.json()["validation"]
        self.assertTrue(validation["ok"])
        self.assertFalse(validation["stale"])
        self.assertEqual(
            [period["natural_inflow_m3s"]["reservoir_alpha"] for period in validation["system_case"]["time_series"]],
            [5.0, 6.0],
        )

    def test_editing_legacy_bound_inflow_series_marks_validation_stale_and_blocks_promotion(self):
        self._validate_v3()
        first_promote = self._promote()
        self.assertEqual(first_promote.status_code, 201)

        reloaded = self.client.get(
            f"/api/scenarios/{self.scenario['id']}/hydraulic-diagram"
        ).json()["diagram"]
        edited_nodes = self._diagram_nodes()
        edited_nodes[0]["natural_inflow_series"] = {
            "version_label": "v2",
            "points": [
                {"timestamp": "2026-01-01T00:00:00", "duration_hours": 1.0, "value_m3s": 55.0},
                {"timestamp": "2026-01-01T01:00:00", "duration_hours": 1.0, "value_m3s": 66.0},
            ],
        }
        stale_save = self._save_diagram(reloaded["revision"], nodes=edited_nodes)
        self.assertEqual(stale_save.status_code, 200)
        self.assertTrue(stale_save.json()["diagram"]["validation"]["stale"])

        blocked_promote = self._promote()
        self.assertEqual(blocked_promote.status_code, 400)
        self.assertIn("stale", blocked_promote.json()["detail"].lower())

        revalidated = self._validate_v3()
        self.assertTrue(revalidated.json()["validation"]["ok"])
        self.assertFalse(revalidated.json()["validation"]["stale"])
        self.assertEqual(
            [
                period["natural_inflow_m3s"]["reservoir_alpha"]
                for period in revalidated.json()["validation"]["system_case"]["time_series"]
            ],
            [55.0, 66.0],
        )

        second_promote = self._promote()
        self.assertEqual(second_promote.status_code, 201)

        # The original legacy set, frozen and untouched, still reads its
        # original values: the compatibility window never rewrites it.
        legacy_detail = self.client.get(
            f"/api/projects/{self.project['id']}/time-series-sets/hydraulic/{self.legacy_set_id}"
        )
        self.assertEqual(
            [value["value_numeric"] for value in legacy_detail.json()["hydraulic_time_series_set"]["values"]],
            [5.0, 6.0],
        )


class NativeHydraulicBindingStalenessTests(HydraulicV3DiagramFixtureMixin, unittest.TestCase):
    """BESS-TS5-005: a natively created (post-TS5-003, generic-from-creation)
    hydraulic-bound series stays fail-closed too, so hardening does not
    regress the baseline case the legacy/migrated/extracted origins are
    compared against."""

    def setUp(self):
        self._create_hydraulic_scenario()
        created = self.client.post(
            f"/api/scenarios/{self.scenario['id']}/hydraulic-diagram"
        ).json()["diagram"]
        inflow = {
            "version_label": "v1",
            "points": [
                {"timestamp": "2026-01-01T00:00:00", "duration_hours": 1.0, "value_m3s": 5.0},
                {"timestamp": "2026-01-01T01:00:00", "duration_hours": 1.0, "value_m3s": 6.0},
            ],
        }
        save_response = self._save_diagram(
            created["revision"], nodes=self._diagram_nodes(inflow=inflow)
        )
        self.assertEqual(save_response.status_code, 200)

    def test_native_generic_inflow_validates_clean_then_editing_it_marks_stale_and_blocks_promotion(self):
        reloaded = self.client.get(
            f"/api/scenarios/{self.scenario['id']}/hydraulic-diagram"
        ).json()["diagram"]
        inflow = reloaded["nodes"][0]["natural_inflow_series"]
        self.assertEqual(inflow["origin"], {"kind": "generic"})

        self._validate_v3()
        first_promote = self._promote()
        self.assertEqual(first_promote.status_code, 201)

        reloaded = self.client.get(
            f"/api/scenarios/{self.scenario['id']}/hydraulic-diagram"
        ).json()["diagram"]
        edited_nodes = self._diagram_nodes()
        edited_nodes[0]["natural_inflow_series"] = {
            "version_label": "v2",
            "points": [
                {"timestamp": "2026-01-01T00:00:00", "duration_hours": 1.0, "value_m3s": 55.0},
                {"timestamp": "2026-01-01T01:00:00", "duration_hours": 1.0, "value_m3s": 66.0},
            ],
        }
        stale_save = self._save_diagram(reloaded["revision"], nodes=edited_nodes)
        self.assertTrue(stale_save.json()["diagram"]["validation"]["stale"])

        blocked_promote = self._promote()
        self.assertEqual(blocked_promote.status_code, 400)

        self._validate_v3()
        second_promote = self._promote()
        self.assertEqual(second_promote.status_code, 201)


if __name__ == "__main__":
    unittest.main()
