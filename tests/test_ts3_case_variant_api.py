import unittest
from datetime import datetime, timedelta

from fastapi.testclient import TestClient

from app.main import create_app
from app.time_series_catalog import CatalogImportRequest, CatalogSignalMappingRequest, prepare_time_series_catalog_import
from app.validation import ValidationResult


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


def complete_hydraulic_v3_nodes():
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
            },
            "storage_elevation_curve": {
                "version_label": "v1",
                "points": [
                    {"x_value": 5.0, "y_value": 700.0},
                    {"x_value": 50.0, "y_value": 760.0},
                ],
            },
            "natural_inflow_series": {
                "version_label": "legacy",
                "points": [
                    {
                        "timestamp": "2026-01-01T00:00:00",
                        "duration_hours": 1.0,
                        "value_m3s": 1.0,
                    },
                    {
                        "timestamp": "2026-01-01T01:00:00",
                        "duration_hours": 1.0,
                        "value_m3s": 1.0,
                    },
                ],
            },
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


class StubValidationService:
    def validate_text(self, candidate_text):
        return ValidationResult(
            ok=True,
            phase="julia",
            message="Validation succeeded",
            payload={"status": "ok", "case_name": "grid_battery_case", "schema_version": "bess_system_dispatch.v1"},
        )


class RecordingRunQueue:
    def __init__(self):
        self.enqueued_run_ids = []

    def enqueue(self, run_id):
        self.enqueued_run_ids.append(run_id)

    def stop(self):
        pass


class CaseInputVariantApiTests(unittest.TestCase):
    def setUp(self):
        self.validation_service = StubValidationService()
        self.run_queue = RecordingRunQueue()
        self.client = TestClient(
            create_app(
                validation_service=self.validation_service,
                database_url="sqlite:///:memory:",
                run_queue=self.run_queue,
            )
        )
        self.store = self.client.app.state.analyst_store
        project = self.store.create_project(name="TS-3 project")
        self.scenario = self.store.create_scenario(project_id=project["id"], name="TS-3 scenario")
        self.store.create_or_replace_scenario_draft(
            scenario_id=self.scenario["id"], document=grid_battery_draft_document()
        )
        prepared = prepare_time_series_catalog_import(
            rows=self._price_rows(datetime(2026, 1, 1), 3),
            request=CatalogImportRequest(
                set_name="Spot price",
                version_label="v1",
                data_kind="real",
                timezone="America/Santiago",
                timestamp_column="period_start",
                duration_hours_column="hours",
                signal_mappings=[
                    CatalogSignalMappingRequest(source_column="spot_price", signal_key="import_price_usd_per_mwh"),
                ],
            ),
        )
        self.price_set = self.store.import_time_series_catalog_set(
            scenario_id=self.scenario["id"],
            source={
                "id": "csv_source_1",
                "original_filename": "price.csv",
                "media_type": "text/csv",
                "checksum": "sha256:test",
            },
            prepared_import=prepared,
        )

    @staticmethod
    def _price_rows(start, count, *, value=50.0):
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

    def test_get_default_variant_creates_it_lazily(self):
        response = self.client.get(f"/api/scenarios/{self.scenario['id']}/case/default-variant")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["variant"]["is_default"])
        self.assertEqual(body["bindings"], [])
        self.assertEqual(
            body["required_signals"],
            [
                {
                    "entity_type": "grid",
                    "entity_id": "grid_1",
                    "signal_key": "price_usd_per_mwh",
                    "bound": False,
                    "bound_signal_key": None,
                    "time_series_set_id": None,
                }
            ],
        )

    def test_required_signals_reflect_a_bound_price(self):
        variant_id = self.client.get(
            f"/api/scenarios/{self.scenario['id']}/case/default-variant"
        ).json()["variant"]["id"]

        self.client.post(
            f"/api/scenarios/{self.scenario['id']}/case/variants/{variant_id}/bindings",
            json={"signal_key": "import_price_usd_per_mwh", "time_series_set_id": self.price_set["id"]},
        )

        body = self.client.get(f"/api/scenarios/{self.scenario['id']}/case/default-variant").json()

        self.assertEqual(
            body["required_signals"],
            [
                {
                    "entity_type": "grid",
                    "entity_id": "grid_1",
                    "signal_key": "price_usd_per_mwh",
                    "bound": True,
                    "bound_signal_key": "import_price_usd_per_mwh",
                    "time_series_set_id": self.price_set["id"],
                }
            ],
        )

    def test_run_with_a_missing_required_signal_returns_400(self):
        self.store.create_or_replace_scenario_draft(
            scenario_id=self.scenario["id"], document=self._grid_battery_load_draft_document()
        )
        variant_id = self.client.get(
            f"/api/scenarios/{self.scenario['id']}/case/default-variant"
        ).json()["variant"]["id"]
        self.client.post(
            f"/api/scenarios/{self.scenario['id']}/case/variants/{variant_id}/bindings",
            json={"signal_key": "import_price_usd_per_mwh", "time_series_set_id": self.price_set["id"]},
        )

        run_response = self.client.post(
            f"/api/scenarios/{self.scenario['id']}/case/variants/{variant_id}/run",
            json={
                "range_start": self.price_set["horizon"]["start"],
                "range_end": self.price_set["horizon"]["end"],
            },
        )

        self.assertEqual(run_response.status_code, 400)
        self.assertIn("load_demand_mw", run_response.text)

    @staticmethod
    def _grid_battery_load_draft_document():
        document = grid_battery_draft_document()
        document["assets"].append({"id": "load_1", "type": "load"})
        return document

    def test_bind_price_signal_then_run_launches_a_run(self):
        variant_id = self.client.get(
            f"/api/scenarios/{self.scenario['id']}/case/default-variant"
        ).json()["variant"]["id"]

        bind_response = self.client.post(
            f"/api/scenarios/{self.scenario['id']}/case/variants/{variant_id}/bindings",
            json={"signal_key": "import_price_usd_per_mwh", "time_series_set_id": self.price_set["id"]},
        )
        self.assertEqual(bind_response.status_code, 201)

        run_response = self.client.post(
            f"/api/scenarios/{self.scenario['id']}/case/variants/{variant_id}/run",
            json={
                "range_start": self.price_set["horizon"]["start"],
                "range_end": self.price_set["horizon"]["end"],
            },
        )

        self.assertEqual(run_response.status_code, 201)
        run = run_response.json()
        self.assertEqual(run["status"], "queued")
        self.assertEqual(self.run_queue.enqueued_run_ids, [run["id"]])

    def test_run_with_range_not_covered_returns_400(self):
        variant_id = self.client.get(
            f"/api/scenarios/{self.scenario['id']}/case/default-variant"
        ).json()["variant"]["id"]
        self.client.post(
            f"/api/scenarios/{self.scenario['id']}/case/variants/{variant_id}/bindings",
            json={"signal_key": "import_price_usd_per_mwh", "time_series_set_id": self.price_set["id"]},
        )

        run_response = self.client.post(
            f"/api/scenarios/{self.scenario['id']}/case/variants/{variant_id}/run",
            json={"range_start": self.price_set["horizon"]["start"], "range_end": "2026-01-02T00:00:00-03:00"},
        )

        self.assertEqual(run_response.status_code, 400)

    def test_list_variants_clone_variant_and_rename_it(self):
        default_variant_id = self.client.get(
            f"/api/scenarios/{self.scenario['id']}/case/default-variant"
        ).json()["variant"]["id"]
        self.client.post(
            f"/api/scenarios/{self.scenario['id']}/case/variants/{default_variant_id}/bindings",
            json={"signal_key": "import_price_usd_per_mwh", "time_series_set_id": self.price_set["id"]},
        )

        create_response = self.client.post(
            f"/api/scenarios/{self.scenario['id']}/case/variants",
            json={"display_name": "Dry year"},
        )
        self.assertEqual(create_response.status_code, 201)
        self.assertFalse(create_response.json()["is_default"])

        clone_response = self.client.post(
            f"/api/scenarios/{self.scenario['id']}/case/variants/{default_variant_id}/clone",
            json={"display_name": "Stress prices"},
        )
        self.assertEqual(clone_response.status_code, 201)
        cloned_variant = clone_response.json()

        rename_response = self.client.patch(
            f"/api/scenarios/{self.scenario['id']}/case/variants/{cloned_variant['id']}",
            json={"display_name": "Stress prices renamed"},
        )
        self.assertEqual(rename_response.status_code, 200)
        self.assertEqual(rename_response.json()["display_name"], "Stress prices renamed")

        list_response = self.client.get(f"/api/scenarios/{self.scenario['id']}/case/variants")

        self.assertEqual(list_response.status_code, 200)
        body = list_response.json()
        self.assertEqual(body["default_variant_id"], default_variant_id)
        self.assertEqual([entry["variant"]["display_name"] for entry in body["variants"]], [
            "Default",
            "Dry year",
            "Stress prices renamed",
        ])
        self.assertEqual(body["variants"][0]["bindings"][0]["time_series_set_id"], self.price_set["id"])
        self.assertEqual(body["variants"][2]["bindings"][0]["time_series_set_id"], self.price_set["id"])

    def test_hydraulic_diagram_case_discovers_and_runs_entity_scoped_variant_signals(self):
        hydraulic_scenario = self.store.create_scenario(
            project_id=self.scenario["project_id"], name="Hydraulic TS-3 scenario"
        )
        create_response = self.client.post(
            f"/api/scenarios/{hydraulic_scenario['id']}/hydraulic-diagram"
        )
        self.assertEqual(create_response.status_code, 201, create_response.text)
        revision = create_response.json()["diagram"]["revision"]
        save_response = self.client.put(
            f"/api/scenarios/{hydraulic_scenario['id']}/hydraulic-diagram",
            json={
                "revision": revision,
                "nodes": complete_hydraulic_v3_nodes(),
                "reaches": [
                    {
                        "technical_key": "reach_reservoir_intake",
                        "display_name": "Reservoir to intake",
                        "from_node_key": "reservoir_alpha",
                        "to_node_key": "junction_in",
                        "reach_type": "river",
                        "minimum_flow_series": {
                            "version_label": "legacy",
                            "points": [
                                {
                                    "timestamp": "2026-01-01T00:00:00",
                                    "duration_hours": 1.0,
                                    "value_m3s": 2.0,
                                },
                                {
                                    "timestamp": "2026-01-01T01:00:00",
                                    "duration_hours": 1.0,
                                    "value_m3s": 3.0,
                                },
                            ],
                        },
                    }
                ],
            },
        )
        self.assertEqual(save_response.status_code, 200, save_response.text)

        variant_body = self.client.get(
            f"/api/scenarios/{hydraulic_scenario['id']}/case/default-variant"
        ).json()
        self.assertEqual(
            variant_body["required_signals"],
            [
                {
                    "entity_type": "hydraulic_node",
                    "entity_id": "reservoir_alpha",
                    "signal_key": "natural_inflow_m3s",
                    "bound": False,
                    "bound_signal_key": None,
                    "time_series_set_id": None,
                },
                {
                    "entity_type": "hydraulic_reach",
                    "entity_id": "reach_reservoir_intake",
                    "signal_key": "minimum_flow_m3s",
                    "bound": False,
                    "bound_signal_key": None,
                    "time_series_set_id": None,
                },
            ],
        )

        inflow_set = self.store.import_time_series_catalog_set(
            scenario_id=hydraulic_scenario["id"],
            source={
                "id": "hydro_inflow_source",
                "original_filename": "inflow.csv",
                "media_type": "text/csv",
                "checksum": "sha256:inflow",
            },
            prepared_import=prepare_time_series_catalog_import(
                rows=self._price_rows(datetime(2026, 1, 1), 2, value=5.0),
                request=CatalogImportRequest(
                    set_name="Natural inflow",
                    version_label="v1",
                    data_kind="real",
                    timezone="America/Santiago",
                    timestamp_column="period_start",
                    duration_hours_column="hours",
                    signal_mappings=[
                        CatalogSignalMappingRequest(
                            source_column="spot_price",
                            signal_key="natural_inflow_m3s",
                        ),
                    ],
                ),
            ),
        )
        min_flow_set = self.store.import_time_series_catalog_set(
            scenario_id=hydraulic_scenario["id"],
            source={
                "id": "hydro_min_flow_source",
                "original_filename": "min_flow.csv",
                "media_type": "text/csv",
                "checksum": "sha256:minflow",
            },
            prepared_import=prepare_time_series_catalog_import(
                rows=self._price_rows(datetime(2026, 1, 1), 2, value=2.0),
                request=CatalogImportRequest(
                    set_name="Minimum flow",
                    version_label="v1",
                    data_kind="real",
                    timezone="America/Santiago",
                    timestamp_column="period_start",
                    duration_hours_column="hours",
                    signal_mappings=[
                        CatalogSignalMappingRequest(
                            source_column="spot_price",
                            signal_key="minimum_flow_m3s",
                        ),
                    ],
                ),
            ),
        )
        variant_id = variant_body["variant"]["id"]
        bind_inflow = self.client.post(
            f"/api/scenarios/{hydraulic_scenario['id']}/case/variants/{variant_id}/bindings",
            json={
                "signal_key": "natural_inflow_m3s",
                "entity_type": "hydraulic_node",
                "entity_id": "reservoir_alpha",
                "time_series_set_id": inflow_set["id"],
            },
        )
        self.assertEqual(bind_inflow.status_code, 201, bind_inflow.text)
        bind_min_flow = self.client.post(
            f"/api/scenarios/{hydraulic_scenario['id']}/case/variants/{variant_id}/bindings",
            json={
                "signal_key": "minimum_flow_m3s",
                "entity_type": "hydraulic_reach",
                "entity_id": "reach_reservoir_intake",
                "time_series_set_id": min_flow_set["id"],
            },
        )
        self.assertEqual(bind_min_flow.status_code, 201, bind_min_flow.text)

        run_response = self.client.post(
            f"/api/scenarios/{hydraulic_scenario['id']}/case/variants/{variant_id}/run",
            json={
                "range_start": inflow_set["horizon"]["start"],
                "range_end": inflow_set["horizon"]["end"],
            },
        )

        self.assertEqual(run_response.status_code, 201, run_response.text)
        run = run_response.json()
        self.assertEqual(run["status"], "queued")
        version = self.client.get(
            f"/api/scenario-versions/{run['scenario_version_id']}"
        ).json()["scenario_version"]
        self.assertEqual(
            version["system_case_json"]["time_series"][0]["natural_inflow_m3s"],
            {"reservoir_alpha": 5.0},
        )
        self.assertEqual(
            version["system_case_json"]["time_series"][0]["minimum_flow_m3s"],
            {"reach_reservoir_intake": 2.0},
        )


class DefaultVariantWithoutADraftYetTests(unittest.TestCase):
    """A scenario's editor draft is only created when someone opens it; the
    input-variant panel is shown on the scenario page regardless, so it must
    not 404 just because required-signal discovery has nothing to read yet.
    """

    def setUp(self):
        self.client = TestClient(
            create_app(
                validation_service=StubValidationService(),
                database_url="sqlite:///:memory:",
                run_queue=RecordingRunQueue(),
            )
        )
        self.store = self.client.app.state.analyst_store
        project = self.store.create_project(name="TS-3 project")
        self.scenario = self.store.create_scenario(project_id=project["id"], name="TS-3 scenario")

    def test_get_default_variant_without_a_draft_returns_no_required_signals(self):
        response = self.client.get(f"/api/scenarios/{self.scenario['id']}/case/default-variant")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["required_signals"], [])


if __name__ == "__main__":
    unittest.main()
