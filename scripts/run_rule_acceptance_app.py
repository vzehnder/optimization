"""Isolated browser acceptance server: real OCI compiler and real Julia solve."""
import os
import copy
import json
import sys
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from app.main import create_app
from app.persistence import AnalystStore
from app.rule_runtime import OCIExecutor
from app.rule_worker import RuleWorker
from tests.test_hydro_diagram_acceptance import complete_v3_nodes
from tests.test_reg005_runtime import GRID
from tests.reg007_fixture import renewable_consumer


def main():
    os.environ["TS_NEXT_CANONICAL_READ_ACCOUNTS"] = "admin@example.local"
    with tempfile.TemporaryDirectory(prefix="reg002-browser-") as temporary:
        store = AnalystStore(f"sqlite:///{temporary}/acceptance.sqlite3")
        project = store.create_project(name="REG-002 · Caudal operativo")
        scenario = store.create_scenario(project_id=project["id"], name="Cuatro horas")
        diagram = store.get_or_create_hydraulic_diagram(scenario["id"])
        nodes = complete_v3_nodes()
        nodes[0]["natural_inflow_series"]["points"] = [
            {"timestamp": f"2026-01-01T0{t}:00:00", "duration_hours": 1, "value_m3s": 0} for t in range(4)]
        store.save_hydraulic_diagram(scenario_id=scenario["id"], revision=diagram["revision"], nodes=nodes,
                                    reaches=[{"technical_key": "reach", "display_name": "Tramo", "from_node_key": "reservoir_alpha", "to_node_key": "junction_in", "reach_type": "river"}])
        version = store.create_scenario_version(scenario_id=scenario["id"], system_case_json=store.generate_hydraulic_v3_preview(scenario["id"]), validation_payload={"status": "ok"})
        def source(name, semantic, unit, values):
            return store.publish_canonical_set_revision(project_id=project["id"], name=name, data_class_key="real", timezone="UTC",
                signals=[{"series_key": "input", "display_name": name, "semantic_type_key": semantic, "unit_key": unit, "signal_role": "input", "aggregation": "mean"}],
                periods=[{"timestamp_start": f"2026-01-01T0{t}:00:00", "timestamp_end": f"2026-01-01T0{t+1}:00:00", "duration_hours": 1} for t in range(len(values))],
                values={"input": values}, actor="reg003-browser")
        source("Afluente operativo", "natural_inflow", "m3_per_s", [8, 12, 16, 20])
        source("Disponibilidad programada", "availability_factor", "dimensionless", [1, 0.5, 0.75, 1])
        source("Afluente incompleto", "natural_inflow", "m3_per_s", [8, 12, 16])
        source("Afluente con cruce", "natural_inflow", "m3_per_s", [8, 12, 80, 20])
        related = store.create_scenario(project_id=project["id"], name="Dos unidades y embalse")
        related_diagram = store.get_or_create_hydraulic_diagram(related["id"])
        related_nodes = copy.deepcopy(nodes)
        second = copy.deepcopy(related_nodes[-1]["units"][0])
        second.update(technical_key="unit_2", display_name="Unit 2", max_flow_m3s=20.0, max_power_mw=15.0)
        related_nodes[-1]["units"].append(second)
        store.save_hydraulic_diagram(scenario_id=related["id"], revision=related_diagram["revision"], nodes=related_nodes,
            reaches=[{"technical_key": "related_reach", "display_name": "Tramo", "from_node_key": "reservoir_alpha", "to_node_key": "junction_in", "reach_type": "river"}])
        temporal = store.create_scenario(project_id=project["id"], name="Rampas con duraciones distintas")
        temporal_diagram = store.get_or_create_hydraulic_diagram(temporal["id"])
        temporal_nodes = copy.deepcopy(nodes)
        temporal_nodes[0]["natural_inflow_series"] = {"points": [{**p, "value_m3s": 0} for p in GRID]}
        store.save_hydraulic_diagram(scenario_id=temporal["id"], revision=temporal_diagram["revision"], nodes=temporal_nodes,
            reaches=[{"technical_key": "temporal_reach", "display_name": "Tramo", "from_node_key": "reservoir_alpha", "to_node_key": "junction_in", "reach_type": "river"}])
        budget_base = store.create_scenario_version(scenario_id=temporal["id"], system_case_json=store.generate_hydraulic_v3_preview(temporal["id"]), validation_payload={"status": "ok"})
        calculated_consumer = renewable_consumer(store, project["id"], "reg007-browser")
        from app.draft_editor import structured_draft_document_from_system_case
        simple_document = json.loads((REPO_ROOT / "data/cases/linear_hydro_system/system_case.json").read_text())
        simple_draft = structured_draft_document_from_system_case(simple_document)
        simple_draft["time_series"] = {"periods": simple_document["time_series"]}
        simple_hydro = store.create_scenario(project_id=project["id"], name="REG-011 · Hidro simple")
        store.create_or_replace_scenario_draft(scenario_id=simple_hydro["id"], document=simple_draft)
        simple_source = source("REG-011 · Caudal horario", "hydro_inflow", "m3_per_s", [4, 6])
        battery_document = json.loads((REPO_ROOT / "tests/fixtures/reg012_battery.json").read_text())
        battery_draft = structured_draft_document_from_system_case(battery_document)
        battery_draft["time_series"] = {"periods": battery_document["time_series"]}
        battery_scenario = store.create_scenario(project_id=project["id"], name="REG-012 · Reserva batería")
        store.create_or_replace_scenario_draft(scenario_id=battery_scenario["id"], document=battery_draft)
        battery_source = source("REG-012 · Reserva horaria", "battery_energy_reserve", "mwh", [0, 4, 1, 2])
        electric_document = json.loads((REPO_ROOT / "tests/fixtures/reg013_electric.json").read_text())
        electric_draft = structured_draft_document_from_system_case(electric_document)
        electric_draft["time_series"] = {"periods": electric_document["time_series"]}
        electric_scenario = store.create_scenario(project_id=project["id"], name="REG-013 · Red y renovables")
        store.create_or_replace_scenario_draft(scenario_id=electric_scenario["id"], document=electric_draft)
        app = create_app(store=store, auth_enabled=True, artifact_root=Path(temporary) / "artifacts", input_source_root=Path(temporary) / "sources")
        original_lifespan = app.router.lifespan_context

        @asynccontextmanager
        async def lifespan(application):
            async with original_lifespan(application):
                with RuleWorker(store, OCIExecutor.from_env()):
                    yield

        app.router.lifespan_context = lifespan

        @app.get("/api/auth/smoke-token", include_in_schema=False)
        def token():
            return {"token": os.environ.get("REACT_SMOKE_TOKEN", "")}

        @app.get("/api/auth/reg011-fixture", include_in_schema=False)
        def simple_fixture():
            return {"scenario_id": simple_hydro["id"], "source": simple_source}

        @app.get("/api/auth/reg012-fixture", include_in_schema=False)
        def battery_fixture():
            return {"scenario_id": battery_scenario["id"], "source": battery_source}

        @app.get("/api/auth/reg013-fixture", include_in_schema=False)
        def electric_fixture():
            return {"scenario_id": electric_scenario["id"]}

        @app.get("/api/auth/reg002-fixture", include_in_schema=False)
        def fixture():
            return {"scenario_id": scenario["id"], "base_version_id": version["id"]}

        @app.post("/api/auth/reg003-republish", include_in_schema=False)
        def republish():
            return source("Disponibilidad programada", "availability_factor", "dimensionless", [0.5, 0.5, 0.5, 0.5])

        @app.get("/api/auth/reg004-fixture", include_in_schema=False)
        def related_fixture():
            return {"scenario_id": related["id"]}

        @app.get("/api/auth/reg005-fixture", include_in_schema=False)
        def temporal_fixture():
            return {"scenario_id": temporal["id"]}

        @app.get("/api/auth/reg006-fixture", include_in_schema=False)
        def budget_fixture():
            return {"scenario_id": temporal["id"], "base_version_id": budget_base["id"]}

        @app.get("/api/auth/reg007-fixture", include_in_schema=False)
        def calculated_fixture():
            return calculated_consumer

        @app.post("/api/auth/reg004-membership", include_in_schema=False)
        def change_membership():
            diagram = store.get_hydraulic_diagram(related["id"])
            plant = next(n for n in diagram["nodes"] if n["technical_key"] == "plant_laja")
            next(u for u in plant["units"] if u["technical_key"] == "unit_2")["is_active"] = False
            store.save_hydraulic_diagram(scenario_id=related["id"], revision=diagram["revision"], nodes=diagram["nodes"], reaches=diagram["reaches"])
            return {"changed": True}

        uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("REACT_SMOKE_PORT", "8123")), log_level="warning")


if __name__ == "__main__":
    main()
