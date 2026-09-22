"""Isolated browser acceptance server: real OCI compiler and real Julia solve."""
import os
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


def main():
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

        @app.get("/api/auth/reg002-fixture", include_in_schema=False)
        def fixture():
            return {"scenario_id": scenario["id"], "base_version_id": version["id"]}

        uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("REACT_SMOKE_PORT", "8123")), log_level="warning")


if __name__ == "__main__":
    main()
