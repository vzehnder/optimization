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


class StubValidationService:
    def __init__(self):
        self.validated_texts = []
        self.file_validation_count = 0

    def validate_text(self, candidate_text):
        self.validated_texts.append(candidate_text)
        document = json.loads(candidate_text)
        return ValidationResult(
            ok=True,
            phase="julia",
            message="Validation succeeded",
            payload={
                "status": "ok",
                "schema_version": document["schema_version"],
                "case_name": document["case_name"],
                "hydraulic_network": {"nodes": 3, "reaches": 1, "plants": 1, "units": 1},
            },
            exit_code=0,
            raw_stdout='{"status":"ok"}\n',
            raw_stderr="",
        )

    def validate_file(self, candidate_path):
        self.file_validation_count += 1
        return ValidationResult(
            ok=True,
            phase="julia",
            message="Validation succeeded",
            payload={"status": "ok"},
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


class HydraulicV3RunProcess:
    def __init__(self):
        self.completed_commands = []

    def __call__(self, command, **kwargs):
        self.completed_commands.append((command, kwargs))
        input_path = next(Path(item) for item in command if str(item).endswith("system_case.json"))
        system_case = json.loads(input_path.read_text(encoding="utf-8"))
        output_root = Path(command[command.index("--output-root") + 1])
        output_dir = output_root / "scenario_1_hydraulic_case" / "hydraulic-v3-run"
        output_dir.mkdir(parents=True)
        summary_path = output_dir / "summary.json"
        summary_path.write_text(
            json.dumps(
                {
                    "case_name": "scenario_1_hydraulic_case",
                    "schema_version": "bess_system_dispatch.v3",
                    "solver_name": "HiGHS",
                    "solver_status": "OPTIMAL",
                    "termination_status": "OPTIMAL",
                    "objective_value_usd": 120.0,
                    "hydraulic_v3_totals": {
                        "total_generation_mwh": 30.0,
                        "final_storage_hm3": 19.856,
                    },
                },
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        (output_dir / "dispatch.csv").write_text(
            "timestamp,duration_hours,total_hydro_power_mw,total_hydro_turbine_flow_m3s,"
            "total_hydro_storage_hm3,total_hydro_reservoir_elevation_masl\n"
            "2026-01-01T00:00:00,1.0,30.0,40.0,19.856,719.808\n",
            encoding="utf-8",
        )
        (output_dir / "asset_dispatch.csv").write_text(
            "timestamp,duration_hours,asset_id,asset_type,hydro_power_mw,"
            "hydro_turbine_flow_m3s,hydro_storage_hm3,hydro_reservoir_elevation_masl\n"
            "2026-01-01T00:00:00,1.0,unit_1,hydraulic_unit,30.0,40.0,19.856,719.808\n",
            encoding="utf-8",
        )
        (output_dir / "system_case_resolved.json").write_text(
            json.dumps(system_case, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        (output_dir / "model_metadata.json").write_text(
            json.dumps(
                {
                    "schema_version": "bess_system_dispatch.v3",
                    "hydraulic_nodes": ["reservoir_alpha", "junction_in", "junction_out"],
                    "hydraulic_units": ["unit_1"],
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
                    "case_name": "scenario_1_hydraulic_case",
                    "run_timestamp": "hydraulic-v3-run",
                    "output_dir": str(output_dir),
                    "summary_path": str(summary_path),
                    "termination_status": "OPTIMAL",
                }
            ),
            stderr="",
        )


class HydraulicDiagramApiTests(unittest.TestCase):
    def setUp(self):
        self.validation_service = StubValidationService()
        self.client = TestClient(
            create_app(
                validation_service=self.validation_service,
                database_url="sqlite:///:memory:",
            )
        )
        project = self.client.post("/api/projects", json={"name": "Hydro Project"}).json()
        self.scenario = self.client.post(
            f"/api/projects/{project['id']}/scenarios",
            json={"name": "Hydraulic base case"},
        ).json()

    def test_minimal_hydraulic_diagram_can_be_saved_reloaded_and_rejects_stale_revision(self):
        create_response = self.client.post(
            f"/api/scenarios/{self.scenario['id']}/hydraulic-diagram"
        )

        self.assertEqual(create_response.status_code, 201)
        created = create_response.json()["diagram"]
        self.assertEqual(created["scenario_id"], self.scenario["id"])
        self.assertEqual(created["nodes"], [])
        self.assertEqual(created["layout"]["layout_key"], "default")
        first_revision = created["revision"]

        save_response = self.client.put(
            f"/api/scenarios/{self.scenario['id']}/hydraulic-diagram",
            json={
                "revision": first_revision,
                "viewport": {"x": 10.0, "y": 20.0, "zoom": 0.85},
                "nodes": [
                    {
                        "component_type": "reservoir",
                        "technical_key": "reservoir_alpha",
                        "display_name": "Reservoir Alpha",
                        "x": 120.0,
                        "y": 80.0,
                    },
                    {
                        "component_type": "junction",
                        "technical_key": "junction_a",
                        "display_name": "Junction A",
                        "x": 300.0,
                        "y": 110.0,
                    },
                    {
                        "component_type": "plant",
                        "technical_key": "plant_laja",
                        "display_name": "Plant Laja",
                        "x": 480.0,
                        "y": 140.0,
                    },
                ],
            },
        )

        self.assertEqual(save_response.status_code, 200)
        saved = save_response.json()["diagram"]
        self.assertNotEqual(saved["revision"], first_revision)
        self.assertEqual(saved["layout"]["viewport"], {"x": 10.0, "y": 20.0, "zoom": 0.85})
        self.assertEqual(
            [(node["component_type"], node["technical_key"], node["display_name"]) for node in saved["nodes"]],
            [
                ("reservoir", "reservoir_alpha", "Reservoir Alpha"),
                ("junction", "junction_a", "Junction A"),
                ("plant", "plant_laja", "Plant Laja"),
            ],
        )

        reload_response = self.client.get(
            f"/api/scenarios/{self.scenario['id']}/hydraulic-diagram"
        )
        self.assertEqual(reload_response.status_code, 200)
        reloaded = reload_response.json()["diagram"]
        self.assertEqual(reloaded["revision"], saved["revision"])
        self.assertEqual(reloaded["nodes"], saved["nodes"])

        stale_response = self.client.put(
            f"/api/scenarios/{self.scenario['id']}/hydraulic-diagram",
            json={"revision": first_revision, "nodes": saved["nodes"]},
        )
        self.assertEqual(stale_response.status_code, 409)
        self.assertIn("stale hydraulic diagram revision", stale_response.json()["detail"])

    def test_directed_reaches_can_be_saved_reloaded_and_validated(self):
        created = self.client.post(
            f"/api/scenarios/{self.scenario['id']}/hydraulic-diagram"
        ).json()["diagram"]

        save_response = self.client.put(
            f"/api/scenarios/{self.scenario['id']}/hydraulic-diagram",
            json={
                "revision": created["revision"],
                "nodes": [
                    {
                        "component_type": "junction",
                        "technical_key": "junction_up",
                        "display_name": "Junction Up",
                        "x": 120.0,
                        "y": 80.0,
                    },
                    {
                        "component_type": "junction",
                        "technical_key": "junction_a",
                        "display_name": "Junction A",
                        "x": 300.0,
                        "y": 110.0,
                    },
                ],
                "reaches": [
                    {
                        "technical_key": "reach_alpha_junction",
                        "display_name": "Alpha to Junction",
                        "from_node_key": "junction_up",
                        "to_node_key": "junction_a",
                        "reach_type": "river",
                    }
                ],
            },
        )

        self.assertEqual(save_response.status_code, 200)
        saved = save_response.json()["diagram"]
        self.assertEqual(
            [
                (
                    reach["technical_key"],
                    reach["from_node_key"],
                    reach["to_node_key"],
                    reach["reach_type"],
                    reach["entity_type"],
                )
                for reach in saved["reaches"]
            ],
            [
                (
                    "reach_alpha_junction",
                    "junction_up",
                    "junction_a",
                    "river",
                    "case_hydraulic_reach",
                )
            ],
        )

        reloaded = self.client.get(
            f"/api/scenarios/{self.scenario['id']}/hydraulic-diagram"
        ).json()["diagram"]
        self.assertEqual(reloaded["reaches"], saved["reaches"])

        validation_response = self.client.post(
            f"/api/scenarios/{self.scenario['id']}/hydraulic-diagram/validate"
        )
        self.assertEqual(validation_response.status_code, 200)
        validation = validation_response.json()["validation"]
        self.assertTrue(validation["ok"])
        self.assertEqual(validation["errors"], [])

    def test_directed_reach_validation_identifies_missing_inactive_and_bad_type_errors(self):
        created = self.client.post(
            f"/api/scenarios/{self.scenario['id']}/hydraulic-diagram"
        ).json()["diagram"]

        invalid_type_response = self.client.put(
            f"/api/scenarios/{self.scenario['id']}/hydraulic-diagram",
            json={
                "revision": created["revision"],
                "nodes": [
                    {
                        "component_type": "junction",
                        "technical_key": "junction_up",
                        "display_name": "Junction Up",
                        "x": 120.0,
                        "y": 80.0,
                    },
                    {
                        "component_type": "junction",
                        "technical_key": "junction_a",
                        "display_name": "Junction A",
                        "x": 300.0,
                        "y": 110.0,
                    },
                ],
                "reaches": [
                    {
                        "technical_key": "bad_reach",
                        "display_name": "Bad Reach",
                        "from_node_key": "junction_up",
                        "to_node_key": "junction_a",
                        "reach_type": "siphon",
                    }
                ],
            },
        )
        self.assertEqual(invalid_type_response.status_code, 400)
        self.assertIn("unsupported hydraulic reach type", invalid_type_response.json()["detail"])

        missing_endpoint_response = self.client.put(
            f"/api/scenarios/{self.scenario['id']}/hydraulic-diagram",
            json={
                "revision": created["revision"],
                "nodes": [
                    {
                        "component_type": "junction",
                        "technical_key": "junction_up",
                        "display_name": "Junction Up",
                        "x": 120.0,
                        "y": 80.0,
                    },
                    {
                        "component_type": "junction",
                        "technical_key": "junction_a",
                        "display_name": "Junction A",
                        "x": 300.0,
                        "y": 110.0,
                    },
                ],
                "reaches": [
                    {
                        "technical_key": "reach_missing",
                        "display_name": "Missing endpoint",
                        "from_node_key": "junction_up",
                        "to_node_key": "junction_missing",
                        "reach_type": "canal",
                    }
                ],
            },
        )
        self.assertEqual(missing_endpoint_response.status_code, 400)
        self.assertIn("hydraulic reach endpoint not found", missing_endpoint_response.json()["detail"])

        first_save_response = self.client.put(
            f"/api/scenarios/{self.scenario['id']}/hydraulic-diagram",
            json={
                "revision": created["revision"],
                "nodes": [
                    {
                        "component_type": "junction",
                        "technical_key": "junction_up",
                        "display_name": "Junction Up",
                        "x": 120.0,
                        "y": 80.0,
                    },
                    {
                        "component_type": "junction",
                        "technical_key": "junction_a",
                        "display_name": "Junction A",
                        "x": 300.0,
                        "y": 110.0,
                    },
                ],
                "reaches": [
                    {
                        "technical_key": "reach_missing",
                        "display_name": "Missing endpoint",
                        "from_node_key": "junction_up",
                        "to_node_key": "junction_a",
                        "reach_type": "canal",
                    }
                ],
            },
        )
        self.assertEqual(first_save_response.status_code, 200)

        save_response = self.client.put(
            f"/api/scenarios/{self.scenario['id']}/hydraulic-diagram",
            json={
                "revision": first_save_response.json()["diagram"]["revision"],
                "nodes": [
                    {
                        "component_type": "junction",
                        "technical_key": "junction_up",
                        "display_name": "Junction Up",
                        "x": 120.0,
                        "y": 80.0,
                    }
                ],
                "reaches": [
                    {
                        "technical_key": "reach_missing",
                        "display_name": "Missing endpoint",
                        "from_node_key": "junction_up",
                        "to_node_key": "junction_a",
                        "reach_type": "canal",
                    }
                ],
            },
        )
        self.assertEqual(save_response.status_code, 200)

        validation_response = self.client.post(
            f"/api/scenarios/{self.scenario['id']}/hydraulic-diagram/validate"
        )
        self.assertEqual(validation_response.status_code, 200)
        validation = validation_response.json()["validation"]
        self.assertFalse(validation["ok"])
        self.assertEqual(validation["warnings"], [])
        self.assertEqual(
            [
                (
                    error["code"],
                    error["entity_type"],
                    error["entity_id"],
                    error["technical_key"],
                )
                for error in validation["errors"]
            ],
            [
                (
                    "inactive_or_missing_endpoint",
                    "case_hydraulic_reach",
                    save_response.json()["diagram"]["reaches"][0]["entity_id"],
                    "reach_missing",
                )
            ],
        )


    def _create_diagram(self):
        return self.client.post(
            f"/api/scenarios/{self.scenario['id']}/hydraulic-diagram"
        ).json()["diagram"]

    def _save(self, revision, *, reservoir=None, curve=None, inflow=None):
        node = {
            "component_type": "reservoir",
            "technical_key": "reservoir_alpha",
            "display_name": "Reservoir Alpha",
            "x": 120.0,
            "y": 80.0,
        }
        if reservoir is not None:
            node["reservoir"] = reservoir
        if curve is not None:
            node["storage_elevation_curve"] = curve
        if inflow is not None:
            node["natural_inflow_series"] = inflow
        return self.client.put(
            f"/api/scenarios/{self.scenario['id']}/hydraulic-diagram",
            json={"revision": revision, "nodes": [node]},
        )

    def _reservoir_node(self, diagram):
        return next(
            node for node in diagram["nodes"] if node["component_type"] == "reservoir"
        )

    def test_reservoir_parameters_and_storage_elevation_curve_persist_and_reload(self):
        created = self._create_diagram()
        reservoir = {
            "storage_min_hm3": 5.0,
            "storage_max_hm3": 50.0,
            "initial_storage_hm3": 20.0,
            "terminal_condition": "equal_initial",
            "terminal_water_value_usd_per_hm3": 12.5,
        }
        curve = {
            "version_label": "v1",
            "points": [
                {"x_value": 5.0, "y_value": 700.0},
                {"x_value": 50.0, "y_value": 760.0},
            ],
        }
        response = self._save(created["revision"], reservoir=reservoir, curve=curve)
        self.assertEqual(response.status_code, 200)
        node = self._reservoir_node(response.json()["diagram"])
        self.assertEqual(node["reservoir"]["storage_min_hm3"], 5.0)
        self.assertEqual(node["reservoir"]["storage_max_hm3"], 50.0)
        self.assertEqual(node["reservoir"]["initial_storage_hm3"], 20.0)
        self.assertEqual(node["reservoir"]["terminal_condition"], "equal_initial")
        self.assertIsNone(node["reservoir"]["terminal_storage_min_hm3"])
        self.assertEqual(node["reservoir"]["terminal_water_value_usd_per_hm3"], 12.5)
        self.assertEqual(node["storage_elevation_curve"]["version_number"], 1)
        self.assertEqual(node["storage_elevation_curve"]["version_label"], "v1")
        self.assertEqual(
            node["storage_elevation_curve"]["points"],
            [
                {"x_value": 5.0, "y_value": 700.0},
                {"x_value": 50.0, "y_value": 760.0},
            ],
        )
        self.assertEqual(len(node["available_curves"]), 1)
        first_curve_set_id = node["storage_elevation_curve"]["curve_set_id"]

        reloaded = self.client.get(
            f"/api/scenarios/{self.scenario['id']}/hydraulic-diagram"
        ).json()["diagram"]
        self.assertEqual(self._reservoir_node(reloaded), node)

        # Editing points to a new shape creates a new version.
        edited_curve = {
            "version_label": "v2",
            "points": [
                {"x_value": 5.0, "y_value": 705.0},
                {"x_value": 50.0, "y_value": 765.0},
            ],
        }
        edited = self._save(
            reloaded["revision"], reservoir=reservoir, curve=edited_curve
        )
        edited_node = self._reservoir_node(edited.json()["diagram"])
        self.assertEqual(edited_node["storage_elevation_curve"]["version_number"], 2)
        self.assertNotEqual(
            edited_node["storage_elevation_curve"]["curve_set_id"], first_curve_set_id
        )
        self.assertEqual(len(edited_node["available_curves"]), 2)

        # Selecting an existing version by id reuses it without a new version.
        selected = self._save(
            edited.json()["diagram"]["revision"],
            reservoir=reservoir,
            curve={"curve_set_id": first_curve_set_id},
        )
        selected_node = self._reservoir_node(selected.json()["diagram"])
        self.assertEqual(
            selected_node["storage_elevation_curve"]["curve_set_id"], first_curve_set_id
        )
        self.assertEqual(selected_node["storage_elevation_curve"]["version_number"], 1)
        self.assertEqual(len(selected_node["available_curves"]), 2)

    def _inflow_series(self, *values, version_label="v1"):
        return {
            "version_label": version_label,
            "points": [
                {
                    "timestamp": f"2026-01-01T{index:02d}:00:00",
                    "duration_hours": 1.0,
                    "value_m3s": float(value),
                }
                for index, value in enumerate(values)
            ],
        }

    def _save_reservoir_with_inflow(self, revision, series):
        node = {
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
            "natural_inflow_series": series,
        }
        return self.client.put(
            f"/api/scenarios/{self.scenario['id']}/hydraulic-diagram",
            json={"revision": revision, "nodes": [node]},
        )

    def test_natural_inflow_series_binds_to_node_persists_and_reloads(self):
        created = self._create_diagram()
        response = self._save_reservoir_with_inflow(
            created["revision"], self._inflow_series(5.0, 6.0)
        )
        self.assertEqual(response.status_code, 200)
        node = self._reservoir_node(response.json()["diagram"])
        series = node["natural_inflow_series"]
        self.assertEqual(series["version_number"], 1)
        self.assertEqual(series["version_label"], "v1")
        self.assertEqual(
            series["points"],
            [
                {"timestamp": "2026-01-01T00:00:00", "duration_hours": 1.0, "value_m3s": 5.0},
                {"timestamp": "2026-01-01T01:00:00", "duration_hours": 1.0, "value_m3s": 6.0},
            ],
        )
        self.assertEqual(len(node["available_inflow_series"]), 1)

        reloaded = self.client.get(
            f"/api/scenarios/{self.scenario['id']}/hydraulic-diagram"
        ).json()["diagram"]
        self.assertEqual(self._reservoir_node(reloaded), node)

    def test_validation_requires_reservoir_parameters_and_curve(self):
        created = self._create_diagram()
        save_response = self._save(created["revision"])
        self.assertEqual(save_response.status_code, 200)

        validation = self.client.post(
            f"/api/scenarios/{self.scenario['id']}/hydraulic-diagram/validate"
        ).json()["validation"]
        self.assertFalse(validation["ok"])
        codes = {error["code"] for error in validation["errors"]}
        self.assertIn("missing_reservoir_parameters", codes)
        self.assertIn("missing_storage_elevation_curve", codes)
        for error in validation["errors"]:
            if error["code"] in {
                "missing_reservoir_parameters",
                "missing_storage_elevation_curve",
            }:
                self.assertEqual(error["entity_type"], "case_hydraulic_node")
                self.assertEqual(error["technical_key"], "reservoir_alpha")

    def test_validation_rejects_bad_curve_and_terminal_settings(self):
        created = self._create_diagram()
        bad_reservoir = {
            "storage_min_hm3": 1.0,
            "storage_max_hm3": 200.0,
            "initial_storage_hm3": 20.0,
            "terminal_condition": "min_terminal",
            "terminal_water_value_usd_per_hm3": 0.0,
        }
        bad_curve = {
            "version_label": "bad",
            "points": [
                {"x_value": 50.0, "y_value": 760.0},
                {"x_value": 5.0, "y_value": 700.0},
            ],
        }
        save_response = self._save(
            created["revision"], reservoir=bad_reservoir, curve=bad_curve
        )
        self.assertEqual(save_response.status_code, 200)

        validation = self.client.post(
            f"/api/scenarios/{self.scenario['id']}/hydraulic-diagram/validate"
        ).json()["validation"]
        self.assertFalse(validation["ok"])
        codes = {error["code"] for error in validation["errors"]}
        self.assertIn("non_increasing_storage_points", codes)
        self.assertIn("storage_bounds_outside_curve_domain", codes)
        self.assertIn("invalid_terminal_settings", codes)

    def _plant_node(self, diagram):
        return next(
            node for node in diagram["nodes"] if node["component_type"] == "plant"
        )

    def _save_plant(self, revision, *, plant=None, units=None, extra_nodes=None):
        nodes = list(extra_nodes or [])
        plant_node = {
            "component_type": "plant",
            "technical_key": "plant_laja",
            "display_name": "Plant Laja",
            "x": 480.0,
            "y": 140.0,
        }
        if plant is not None:
            plant_node["plant"] = plant
        if units is not None:
            plant_node["units"] = units
        nodes.append(plant_node)
        return self.client.put(
            f"/api/scenarios/{self.scenario['id']}/hydraulic-diagram",
            json={"revision": revision, "nodes": nodes},
        )

    def _intake_discharge_nodes(self):
        return [
            {
                "component_type": "junction",
                "technical_key": "junction_in",
                "display_name": "Intake",
                "x": 120.0,
                "y": 80.0,
            },
            {
                "component_type": "junction",
                "technical_key": "junction_out",
                "display_name": "Tailrace",
                "x": 300.0,
                "y": 110.0,
            },
        ]

    def test_plant_units_and_flow_power_curve_persist_and_reload(self):
        created = self._create_diagram()
        unit = {
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
        response = self._save_plant(
            created["revision"],
            plant={"non_modeled": False, "min_power_mw": None, "max_power_mw": 60.0},
            units=[unit],
            extra_nodes=self._intake_discharge_nodes(),
        )
        self.assertEqual(response.status_code, 200)
        node = self._plant_node(response.json()["diagram"])
        self.assertEqual(node["plant"]["non_modeled"], False)
        self.assertIsNone(node["plant"]["min_power_mw"])
        self.assertEqual(node["plant"]["max_power_mw"], 60.0)
        self.assertEqual(len(node["units"]), 1)
        saved_unit = node["units"][0]
        self.assertEqual(saved_unit["technical_key"], "unit_1")
        self.assertEqual(saved_unit["is_active"], True)
        self.assertEqual(saved_unit["intake_node_key"], "junction_in")
        self.assertEqual(saved_unit["discharge_node_key"], "junction_out")
        self.assertEqual(saved_unit["max_power_mw"], 30.0)
        self.assertEqual(saved_unit["max_flow_m3s"], 40.0)
        self.assertEqual(saved_unit["flow_power_curve"]["version_number"], 1)
        self.assertEqual(saved_unit["flow_power_curve"]["version_label"], "v1")
        self.assertEqual(
            saved_unit["flow_power_curve"]["points"],
            [
                {"x_value": 0.0, "y_value": 0.0},
                {"x_value": 40.0, "y_value": 30.0},
            ],
        )
        self.assertEqual(len(saved_unit["available_curves"]), 1)
        first_curve_set_id = saved_unit["flow_power_curve"]["curve_set_id"]

        reloaded = self.client.get(
            f"/api/scenarios/{self.scenario['id']}/hydraulic-diagram"
        ).json()["diagram"]
        self.assertEqual(self._plant_node(reloaded), node)

        # Editing curve points to a new shape creates a new version.
        edited_unit = dict(unit)
        edited_unit["flow_power_curve"] = {
            "version_label": "v2",
            "points": [
                {"x_value": 0.0, "y_value": 0.0},
                {"x_value": 40.0, "y_value": 28.0},
            ],
        }
        edited = self._save_plant(
            reloaded["revision"],
            plant={"non_modeled": False, "min_power_mw": None, "max_power_mw": 60.0},
            units=[edited_unit],
            extra_nodes=self._intake_discharge_nodes(),
        )
        edited_unit_out = self._plant_node(edited.json()["diagram"])["units"][0]
        self.assertEqual(edited_unit_out["flow_power_curve"]["version_number"], 2)
        self.assertNotEqual(
            edited_unit_out["flow_power_curve"]["curve_set_id"], first_curve_set_id
        )
        self.assertEqual(len(edited_unit_out["available_curves"]), 2)

        # Selecting an existing version by id reuses it without a new version.
        selected_unit = dict(unit)
        selected_unit["flow_power_curve"] = {"curve_set_id": first_curve_set_id}
        selected = self._save_plant(
            edited.json()["diagram"]["revision"],
            plant={"non_modeled": False, "min_power_mw": None, "max_power_mw": 60.0},
            units=[selected_unit],
            extra_nodes=self._intake_discharge_nodes(),
        )
        selected_unit_out = self._plant_node(selected.json()["diagram"])["units"][0]
        self.assertEqual(
            selected_unit_out["flow_power_curve"]["curve_set_id"], first_curve_set_id
        )
        self.assertEqual(selected_unit_out["flow_power_curve"]["version_number"], 1)
        self.assertEqual(len(selected_unit_out["available_curves"]), 2)

    def _valid_unit(self, **overrides):
        unit = {
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
        unit.update(overrides)
        return unit

    def test_validation_requires_active_plant_to_have_units(self):
        created = self._create_diagram()
        save = self._save_plant(
            created["revision"],
            plant={"non_modeled": False},
            units=[],
        )
        self.assertEqual(save.status_code, 200)
        validation = self.client.post(
            f"/api/scenarios/{self.scenario['id']}/hydraulic-diagram/validate"
        ).json()["validation"]
        self.assertFalse(validation["ok"])
        codes = {error["code"] for error in validation["errors"]}
        self.assertIn("plant_without_active_units", codes)
        plant_error = next(
            error
            for error in validation["errors"]
            if error["code"] == "plant_without_active_units"
        )
        self.assertEqual(plant_error["entity_type"], "case_hydraulic_plant")
        self.assertEqual(plant_error["technical_key"], "plant_laja")

    def test_validation_skips_non_modeled_plant_without_units(self):
        created = self._create_diagram()
        save = self._save_plant(
            created["revision"],
            plant={"non_modeled": True},
            units=[],
        )
        self.assertEqual(save.status_code, 200)
        validation = self.client.post(
            f"/api/scenarios/{self.scenario['id']}/hydraulic-diagram/validate"
        ).json()["validation"]
        codes = {error["code"] for error in validation["errors"]}
        self.assertNotIn("plant_without_active_units", codes)

    def test_validation_rejects_bad_unit_nodes_and_flow_power_curve(self):
        created = self._create_diagram()
        equal_no_curve = self._valid_unit(
            intake_node_key="junction_in",
            discharge_node_key="junction_in",
            flow_power_curve=None,
        )
        save = self._save_plant(
            created["revision"],
            plant={"non_modeled": False},
            units=[equal_no_curve],
            extra_nodes=self._intake_discharge_nodes(),
        )
        self.assertEqual(save.status_code, 200)
        validation = self.client.post(
            f"/api/scenarios/{self.scenario['id']}/hydraulic-diagram/validate"
        ).json()["validation"]
        self.assertFalse(validation["ok"])
        codes = {error["code"] for error in validation["errors"]}
        self.assertIn("inactive_or_equal_unit_nodes", codes)
        self.assertIn("missing_flow_power_curve", codes)
        for error in validation["errors"]:
            if error["code"] in {
                "inactive_or_equal_unit_nodes",
                "missing_flow_power_curve",
            }:
                self.assertEqual(error["entity_type"], "case_hydraulic_unit")
                self.assertEqual(error["technical_key"], "unit_1")

    def test_validation_rejects_invalid_flow_power_curve_shape(self):
        created = self._create_diagram()
        bad_curve_unit = self._valid_unit(
            flow_power_curve={
                "version_label": "bad",
                "points": [
                    {"x_value": 40.0, "y_value": 30.0},
                    {"x_value": 10.0, "y_value": 20.0},
                ],
            }
        )
        save = self._save_plant(
            created["revision"],
            plant={"non_modeled": False},
            units=[bad_curve_unit],
            extra_nodes=self._intake_discharge_nodes(),
        )
        self.assertEqual(save.status_code, 200)
        validation = self.client.post(
            f"/api/scenarios/{self.scenario['id']}/hydraulic-diagram/validate"
        ).json()["validation"]
        codes = {error["code"] for error in validation["errors"]}
        self.assertIn("invalid_flow_power_curve", codes)

    def test_validation_passes_for_complete_plant_with_unit(self):
        created = self._create_diagram()
        save = self._save_plant(
            created["revision"],
            plant={"non_modeled": False},
            units=[self._valid_unit()],
            extra_nodes=self._intake_discharge_nodes(),
        )
        self.assertEqual(save.status_code, 200)
        validation = self.client.post(
            f"/api/scenarios/{self.scenario['id']}/hydraulic-diagram/validate"
        ).json()["validation"]
        self.assertTrue(validation["ok"])
        self.assertEqual(validation["errors"], [])

    def test_validation_passes_for_complete_reservoir(self):
        created = self._create_diagram()
        reservoir = {
            "storage_min_hm3": 5.0,
            "storage_max_hm3": 50.0,
            "initial_storage_hm3": 20.0,
            "terminal_condition": "min_terminal",
            "terminal_storage_min_hm3": 10.0,
            "terminal_water_value_usd_per_hm3": 8.0,
        }
        curve = {
            "version_label": "v1",
            "points": [
                {"x_value": 5.0, "y_value": 700.0},
                {"x_value": 25.0, "y_value": 730.0},
                {"x_value": 50.0, "y_value": 760.0},
            ],
        }
        save_response = self._save(
            created["revision"],
            reservoir=reservoir,
            curve=curve,
            inflow=self._inflow_series(5.0, 6.0),
        )
        self.assertEqual(save_response.status_code, 200)

        validation = self.client.post(
            f"/api/scenarios/{self.scenario['id']}/hydraulic-diagram/validate"
        ).json()["validation"]
        self.assertTrue(validation["ok"])
        self.assertEqual(validation["errors"], [])

    def test_natural_inflow_series_binds_to_non_reservoir_node(self):
        created = self._create_diagram()
        save_response = self.client.put(
            f"/api/scenarios/{self.scenario['id']}/hydraulic-diagram",
            json={
                "revision": created["revision"],
                "nodes": [
                    {
                        "component_type": "junction",
                        "technical_key": "junction_lat",
                        "display_name": "Lateral inflow",
                        "x": 200.0,
                        "y": 90.0,
                        "natural_inflow_series": self._inflow_series(2.0, 3.0),
                    }
                ],
            },
        )
        self.assertEqual(save_response.status_code, 200)
        node = next(
            n
            for n in save_response.json()["diagram"]["nodes"]
            if n["technical_key"] == "junction_lat"
        )
        self.assertEqual(node["component_type"], "junction")
        self.assertEqual(
            [point["value_m3s"] for point in node["natural_inflow_series"]["points"]],
            [2.0, 3.0],
        )

    def test_validation_requires_inflow_binding_on_reservoir(self):
        created = self._create_diagram()
        reservoir = {
            "storage_min_hm3": 5.0,
            "storage_max_hm3": 50.0,
            "initial_storage_hm3": 20.0,
            "terminal_condition": "none",
            "terminal_water_value_usd_per_hm3": 0.0,
        }
        curve = {
            "version_label": "v1",
            "points": [
                {"x_value": 5.0, "y_value": 700.0},
                {"x_value": 50.0, "y_value": 760.0},
            ],
        }
        save_response = self._save(created["revision"], reservoir=reservoir, curve=curve)
        self.assertEqual(save_response.status_code, 200)

        validation = self.client.post(
            f"/api/scenarios/{self.scenario['id']}/hydraulic-diagram/validate"
        ).json()["validation"]
        self.assertFalse(validation["ok"])
        missing = [
            error
            for error in validation["errors"]
            if error["code"] == "missing_natural_inflow_series"
        ]
        self.assertEqual(len(missing), 1)
        self.assertEqual(missing[0]["entity_type"], "case_hydraulic_node")
        self.assertEqual(missing[0]["technical_key"], "reservoir_alpha")

    def test_validation_rejects_negative_inflow_values(self):
        created = self._create_diagram()
        reservoir = {
            "storage_min_hm3": 5.0,
            "storage_max_hm3": 50.0,
            "initial_storage_hm3": 20.0,
            "terminal_condition": "none",
            "terminal_water_value_usd_per_hm3": 0.0,
        }
        curve = {
            "version_label": "v1",
            "points": [
                {"x_value": 5.0, "y_value": 700.0},
                {"x_value": 50.0, "y_value": 760.0},
            ],
        }
        save_response = self._save(
            created["revision"],
            reservoir=reservoir,
            curve=curve,
            inflow=self._inflow_series(5.0, -3.0),
        )
        self.assertEqual(save_response.status_code, 200)

        validation = self.client.post(
            f"/api/scenarios/{self.scenario['id']}/hydraulic-diagram/validate"
        ).json()["validation"]
        self.assertFalse(validation["ok"])
        codes = {error["code"] for error in validation["errors"]}
        self.assertIn("negative_inflow_value", codes)
        negative = next(
            error
            for error in validation["errors"]
            if error["code"] == "negative_inflow_value"
        )
        self.assertEqual(negative["entity_type"], "case_hydraulic_node")
        self.assertEqual(negative["technical_key"], "reservoir_alpha")

    def test_validation_rejects_inflow_horizon_mismatch(self):
        created = self._create_diagram()
        save_response = self.client.put(
            f"/api/scenarios/{self.scenario['id']}/hydraulic-diagram",
            json={
                "revision": created["revision"],
                "nodes": [
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
                        "natural_inflow_series": self._inflow_series(5.0, 6.0),
                    },
                    {
                        "component_type": "junction",
                        "technical_key": "junction_lat",
                        "display_name": "Lateral",
                        "x": 300.0,
                        "y": 80.0,
                        "natural_inflow_series": self._inflow_series(1.0),
                    },
                ],
            },
        )
        self.assertEqual(save_response.status_code, 200)

        validation = self.client.post(
            f"/api/scenarios/{self.scenario['id']}/hydraulic-diagram/validate"
        ).json()["validation"]
        self.assertFalse(validation["ok"])
        codes = {error["code"] for error in validation["errors"]}
        self.assertIn("inflow_horizon_mismatch", codes)

    def test_v3_preview_generation_validates_with_julia_persists_snapshot_and_marks_stale_after_edit(self):
        self._save_complete_v3_diagram()

        preview_response = self.client.post(
            f"/api/scenarios/{self.scenario['id']}/hydraulic-diagram/v3-preview"
        )

        self.assertEqual(preview_response.status_code, 200)
        validation = preview_response.json()["validation"]
        preview = validation["system_case"]
        self.assertTrue(validation["ok"])
        self.assertFalse(validation["stale"])
        self.assertEqual(preview["schema_version"], "bess_system_dispatch.v3")
        self.assertEqual(preview["hydraulic_network"]["nodes"][0]["id"], "reservoir_alpha")
        self.assertEqual(
            preview["hydraulic_network"]["nodes"][0]["curves"]["storage_elevation"],
            [
                {"storage_hm3": 5.0, "elevation_masl": 700.0},
                {"storage_hm3": 50.0, "elevation_masl": 760.0},
            ],
        )
        self.assertEqual(
            preview["hydraulic_network"]["units"][0]["curves"]["flow_power"],
            [
                {"flow_m3s": 0.0, "power_mw": 0.0},
                {"flow_m3s": 40.0, "power_mw": 30.0},
            ],
        )
        self.assertEqual(
            preview["hydraulic_network"]["required_time_series"],
            [
                {
                    "entity_type": "hydraulic_node",
                    "entity_id": "reservoir_alpha",
                    "signal_key": "natural_inflow_m3s",
                    "binding_status": "required",
                }
            ],
        )
        self.assertEqual(len(self.validation_service.validated_texts), 1)
        self.assertIn('"schema_version": "bess_system_dispatch.v3"', self.validation_service.validated_texts[0])

        reloaded = self.client.get(
            f"/api/scenarios/{self.scenario['id']}/hydraulic-diagram"
        ).json()["diagram"]
        self.assertTrue(reloaded["validation"]["ok"])
        self.assertFalse(reloaded["validation"]["stale"])

        edited_nodes = reloaded["nodes"]
        edited_nodes[0]["display_name"] = "Reservoir Alpha Edited"
        stale_response = self.client.put(
            f"/api/scenarios/{self.scenario['id']}/hydraulic-diagram",
            json={
                "revision": reloaded["revision"],
                "nodes": edited_nodes,
                "reaches": reloaded["reaches"],
                "viewport": reloaded["layout"]["viewport"],
            },
        )
        self.assertEqual(stale_response.status_code, 200)
        self.assertTrue(stale_response.json()["diagram"]["validation"]["stale"])

    def test_v3_preview_resolves_bound_inflow_series_into_time_series(self):
        self._save_complete_v3_diagram()
        preview = self.client.post(
            f"/api/scenarios/{self.scenario['id']}/hydraulic-diagram/v3-preview"
        ).json()["validation"]["system_case"]
        self.assertEqual(
            preview["time_series"],
            [
                {
                    "timestamp": "2026-01-01T00:00:00",
                    "duration_hours": 1.0,
                    "natural_inflow_m3s": {"reservoir_alpha": 5.0},
                },
                {
                    "timestamp": "2026-01-01T01:00:00",
                    "duration_hours": 1.0,
                    "natural_inflow_m3s": {"reservoir_alpha": 6.0},
                },
            ],
        )

    def test_validated_v3_diagram_promotes_to_version_and_manual_run_artifacts(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_root = Path(temp_dir) / "artifacts"
            store = AnalystStore("sqlite:///:memory:")
            validation_service = StubValidationService()
            run_process = HydraulicV3RunProcess()
            executor = JuliaRunExecutor(
                store=store,
                artifact_root=artifact_root,
                runner=run_process,
                validation_service=validation_service,
            )
            client = TestClient(
                create_app(
                    validation_service=validation_service,
                    store=store,
                    run_queue=SynchronousRunQueue(executor),
                    artifact_root=artifact_root,
                )
            )
            try:
                project = client.post("/api/projects", json={"name": "Hydro Project"}).json()
                scenario = client.post(
                    f"/api/projects/{project['id']}/scenarios",
                    json={"name": "Hydraulic v3 run"},
                ).json()
                self.client = client
                self.scenario = scenario
                self.validation_service = validation_service
                self._save_complete_v3_diagram()

                preview_response = client.post(
                    f"/api/scenarios/{scenario['id']}/hydraulic-diagram/v3-preview"
                )
                self.assertEqual(preview_response.status_code, 200)
                system_case = preview_response.json()["validation"]["system_case"]

                promote_response = client.post(
                    f"/api/scenarios/{scenario['id']}/hydraulic-diagram/promote"
                )

                self.assertEqual(promote_response.status_code, 201)
                version = promote_response.json()
                stored_version = client.get(f"/api/scenario-versions/{version['id']}").json()[
                    "scenario_version"
                ]
                self.assertEqual(stored_version["schema_version"], "bess_system_dispatch.v3")
                self.assertEqual(stored_version["system_case_json"], system_case)
                self.assertEqual(stored_version["generation_metadata"]["kind"], "hydraulic_diagram_v3")

                run_response = client.post(f"/api/scenario-versions/{version['id']}/runs")
                self.assertEqual(run_response.status_code, 201)
                run = client.get(f"/api/runs/{run_response.json()['id']}").json()["run"]
                self.assertEqual(run["status"], "succeeded")
                self.assertEqual(validation_service.file_validation_count, 1)
                self.assertTrue(run_process.completed_commands)

                artifacts = client.get(f"/api/runs/{run['id']}/artifacts").json()["artifacts"]
                artifacts_by_type = {artifact["artifact_type"]: artifact for artifact in artifacts}
                self.assertEqual(
                    set(artifacts_by_type),
                    {
                        "input_snapshot",
                        "stdout_log",
                        "stderr_log",
                        "summary_json",
                        "dispatch_csv",
                        "asset_dispatch_csv",
                        "system_case_resolved_json",
                        "model_metadata_json",
                    },
                )
                resolved = json.loads(
                    Path(artifacts_by_type["system_case_resolved_json"]["path"]).read_text(
                        encoding="utf-8"
                    )
                )
                self.assertEqual(resolved["schema_version"], "bess_system_dispatch.v3")
                metadata = json.loads(
                    Path(artifacts_by_type["model_metadata_json"]["path"]).read_text(
                        encoding="utf-8"
                    )
                )
                self.assertEqual(metadata["schema_version"], "bess_system_dispatch.v3")
            finally:
                store.close()

    def _save_complete_v3_diagram(self):
        created = self._create_diagram()
        save_response = self.client.put(
            f"/api/scenarios/{self.scenario['id']}/hydraulic-diagram",
            json={
                "revision": created["revision"],
                "nodes": [
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
                            "terminal_condition": "min_terminal",
                            "terminal_storage_min_hm3": 10.0,
                            "terminal_water_value_usd_per_hm3": 8.0,
                        },
                        "storage_elevation_curve": {
                            "version_label": "v1",
                            "points": [
                                {"x_value": 5.0, "y_value": 700.0},
                                {"x_value": 50.0, "y_value": 760.0},
                            ],
                        },
                        "natural_inflow_series": {
                            "version_label": "v1",
                            "points": [
                                {
                                    "timestamp": "2026-01-01T00:00:00",
                                    "duration_hours": 1.0,
                                    "value_m3s": 5.0,
                                },
                                {
                                    "timestamp": "2026-01-01T01:00:00",
                                    "duration_hours": 1.0,
                                    "value_m3s": 6.0,
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
                ],
                "reaches": [
                    {
                        "technical_key": "reach_reservoir_intake",
                        "display_name": "Reservoir to intake",
                        "from_node_key": "reservoir_alpha",
                        "to_node_key": "junction_in",
                        "reach_type": "river",
                    },
                ],
            },
        )
        self.assertEqual(save_response.status_code, 200)
        return save_response.json()["diagram"]


if __name__ == "__main__":
    unittest.main()
