from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import uvicorn
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from app.auth import hash_password
from app.main import create_app
from app.persistence import AnalystStore
from scripts.run_react_smoke_app import SmokeRunQueue, SmokeValidationService
from tests.auth_test_helpers import login_json_with_csrf, post_json_with_csrf
from tests.test_configuration_layer_acceptance import (
    PORTAL_ACCEPTANCE_DOCUMENT,
    import_acceptance_set,
    operator_acceptance_document,
)
from tests.test_configuration_layer_operator_console import operator_draft_document
from tests.test_results_review import create_completed_run_with_result_artifacts


def build_acceptance_app():
    store = AnalystStore("sqlite:///:memory:")
    artifact_directory = tempfile.TemporaryDirectory(
        prefix="configuration-acceptance-"
    )
    artifact_root = Path(artifact_directory.name)
    analyst = store.create_user(
        email="analyst@example.local",
        display_name="Ana Analista",
        role="analyst",
        password_hash=hash_password("analyst pass"),
    )
    operator = store.create_user(
        email="operator@example.local",
        display_name="Olga Operadora",
        role="external",
        password_hash=hash_password("operator pass"),
    )
    viewer = store.create_user(
        email="viewer@example.local",
        display_name="Vera Cliente",
        role="external",
        password_hash=hash_password("viewer pass"),
    )

    project = store.create_project(name="Planta Norte")
    scenario = store.create_scenario(
        project_id=project["id"], name="Operacion diaria"
    )
    store.create_or_replace_scenario_draft(
        scenario_id=scenario["id"], document=operator_draft_document()
    )
    case = store.get_or_create_case_for_scenario(scenario["id"])
    source_variant = store.get_or_create_default_input_variant(case["id"])
    demand_set = import_acceptance_set(
        store,
        scenario["id"],
        name="Demanda base",
        signal_key="load_demand_mw",
        first_value=10,
    )
    forecast_set = import_acceptance_set(
        store,
        scenario["id"],
        name="Pronostico actualizado",
        signal_key="load_demand_mw",
        first_value=20,
    )
    price_set = import_acceptance_set(
        store,
        scenario["id"],
        name="Precio base",
        signal_key="import_price_usd_per_mwh",
        first_value=50,
    )
    for signal_key, time_series_set in (
        ("load_demand_mw", demand_set),
        ("import_price_usd_per_mwh", price_set),
    ):
        store.upsert_case_time_series_binding(
            case_input_variant_id=source_variant["id"],
            signal_key=signal_key,
            time_series_set_id=time_series_set["id"],
        )

    document = operator_acceptance_document(
        demand_set_id=demand_set["id"],
        forecast_set_id=forecast_set["id"],
        price_set_id=price_set["id"],
    )
    document["results"] = {
        "kpis": [
            {
                "id": "beneficio_total",
                "path": "objective_value_usd",
                "label": "Beneficio total",
                "unit": "USD",
                "decimals": 1,
                "sign": "auto",
                "emphasis": "strong",
            }
        ],
        "charts": [],
        "tables": [],
    }
    console = store.create_operator_console(
        case_id=case["id"],
        source_variant_id=source_variant["id"],
        document=document,
        created_by_user_id=analyst["id"],
    )
    console = store.save_operator_console(
        console["id"],
        document=document,
        status="active",
        expected_revision=1,
        updated_by_user_id=analyst["id"],
    )
    store.set_external_project_access(
        project_id=project["id"],
        user_id=operator["id"],
        portal_view=False,
        operate=True,
        updated_by="analyst@example.local",
    )

    portal_run = create_completed_run_with_result_artifacts(store, artifact_root)
    portal_project_id = int(store.get_run_lineage(portal_run["id"])["project_id"])
    store.connection.execute(
        "UPDATE projects SET name = ? WHERE id = ?",
        ("Proyecto interno sin marca publica", portal_project_id),
    )
    store.connection.commit()
    store.set_external_project_access(
        project_id=portal_project_id,
        user_id=viewer["id"],
        portal_view=True,
        operate=False,
        updated_by="analyst@example.local",
    )
    template = store.create_dashboard_template(
        project_id=portal_project_id,
        name="Plantilla de publicacion",
        created_by="analyst@example.local",
    )
    publication = store.create_publication_draft(
        run_id=portal_run["id"],
        dashboard_template_id=template["id"],
        public_title="Resultado configurado de enero",
        analyst_notes="Resultado aprobado para el cliente.",
        allowed_artifact_types=["summary_json"],
        created_by="analyst@example.local",
    )
    store.publish_publication(
        publication["id"], published_by="analyst@example.local"
    )
    configuration = store.save_portal_configuration(
        portal_project_id,
        document=PORTAL_ACCEPTANCE_DOCUMENT,
        status="active",
        expected_revision=0,
        updated_by_user_id=analyst["id"],
    )
    store.save_portal_logo(
        portal_project_id,
        logo_bytes=b"\x89PNG\r\n\x1a\nacceptance-logo",
        logo_media_type="image/png",
        expected_revision=configuration["revision"],
        updated_by_user_id=analyst["id"],
    )

    app = create_app(
        store=store,
        auth_enabled=True,
        validation_service=SmokeValidationService(),
        run_queue=SmokeRunQueue(store, artifact_root),
        artifact_root=artifact_root,
    )
    app.state.configuration_acceptance_artifact_directory = artifact_directory
    analyst_client = TestClient(app)
    login = login_json_with_csrf(
        analyst_client, "analyst@example.local", "analyst pass"
    )
    if login.status_code != 200:
        raise RuntimeError(login.text)
    validated = post_json_with_csrf(
        analyst_client,
        (
            f"/api/scenarios/{scenario['id']}/case/variants/"
            f"{console['owned_variant_id']}/validate"
        ),
        {
            "range_start": demand_set["horizon"]["start"],
            "range_end": demand_set["horizon"]["end"],
        },
    )
    if validated.status_code != 200:
        raise RuntimeError(validated.text)
    return app


if __name__ == "__main__":
    uvicorn.run(build_acceptance_app(), host="127.0.0.1", port=8124, log_level="warning")
