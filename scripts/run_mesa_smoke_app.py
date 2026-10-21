"""Isolated authenticated HTTP fixture for MESA-002 browser acceptance."""

import os
import sys
import tempfile
from pathlib import Path

import uvicorn

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from app.auth import hash_password
from app.main import create_app
from app.persistence import AnalystStore
from tests.mesa_fixture import seed_mesa_case, seed_mesa_run
from tests.mesa_hydraulic_fixture import seed_hydraulic_mesa, seed_hydraulic_mesa_run
from tests.mesa_execution_fixture import seed_executable_mesa
from tests.mesa_hydraulic_execution_fixture import seed_executable_hydraulic_mesa


def main():
    store = AnalystStore("sqlite:///:memory:")
    store.create_user(
        email="mesa@example.local", display_name="Analista mesa", role="analyst",
        password_hash=hash_password("mesa test pass"),
    )
    fixture = seed_mesa_case(store, variant_name="Demanda alternativa")
    artifact_dir = tempfile.TemporaryDirectory()
    app = create_app(store=store, auth_enabled=True, artifact_root=artifact_dir.name)

    @app.get("/api/auth/mesa-fixture", include_in_schema=False)
    async def mesa_test_fixture(case_name: str | None = None, with_replacement: bool = False, electrical: bool = False, with_run: bool = False, hydraulic: bool = False, executable: bool = False, hydraulic_execution: bool = False):
        result = (seed_executable_hydraulic_mesa(store, name=case_name or "Ejecución hidráulica") if hydraulic_execution else
                  seed_executable_mesa(store, name=case_name or "Ejecución eléctrica") if executable else
                  seed_hydraulic_mesa(store, name=case_name or "Consulta hidráulica") if hydraulic else
                  seed_mesa_case(store, name=case_name, variant_name="Demanda alternativa", electrical=electrical) if case_name else fixture)
        if with_run:
            result["run"] = (seed_hydraulic_mesa_run if hydraulic else seed_mesa_run)(store, result, artifact_dir.name)
        if with_replacement:
            result["replacement"] = store.ensure_project_component(
                project_id=result["project"]["id"], component_key="load_replacement",
                component_type="load", display_name="Demanda Norte",
            )
        return result

    @app.get("/api/auth/smoke-token", include_in_schema=False)
    async def smoke_token():
        return {"token": os.environ.get("REACT_SMOKE_TOKEN", "")}

    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("REACT_SMOKE_PORT", "8141")), log_level="warning")


if __name__ == "__main__":
    main()
