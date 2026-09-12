"""Disposable UX-000 fixture server. Never connects to a working database."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["TS_NEXT_CANONICAL_READ_ACCOUNTS"] = "verification@ux.example.local"

import uvicorn

from app.auth import hash_password
from app.main import create_app
from app.persistence import AnalystStore
from app.time_series_catalog import CatalogValueEdit
from scripts.run_react_smoke_app import SmokeRunQueue, SmokeValidationService
from tests.test_configuration_layer_operator_console import (
    console_document_with_scalar_parameter,
    create_console_price_set,
    operator_draft_document,
)
from tests.test_ts4_run_comparison import create_indexed_run


def main():
    artifact_root = ROOT / ".tmp" / "ux-000" / os.environ["UX_BASELINE_TOKEN"]
    artifact_root.mkdir(parents=True, exist_ok=False)
    store = AnalystStore("sqlite:///:memory:")
    users = {}
    for name, role in [
        ("admin", "admin"), ("analyst", "analyst"),
        ("verification", "analyst"), ("operator", "external"), ("reader", "external"),
    ]:
        users[name] = store.create_user(
            email=f"{name}@ux.example.local", display_name=f"UX {name}", role=role,
            password_hash=hash_password("ux-baseline-only"),
        )
    project = store.create_project(name="UX-000 Planta de prueba")
    scenarios = {}
    for key, name in [
        ("empty", "Sin modelo"), ("partial", "Preparacion parcial"),
        ("ready", "Operacion preparada"), ("stale", "Fuente modificada"),
    ]:
        owner = store.create_project(name="UX-000 Revision de fuente") if key == "stale" else project
        scenario = store.create_scenario(project_id=owner["id"], name=name)
        scenarios[key] = {"id": scenario["id"], "name": name, "project_id": owner["id"]}
        if key == "empty":
            continue
        store.create_or_replace_scenario_draft(
            scenario_id=scenario["id"], document=operator_draft_document(),
        )
        case = store.get_or_create_case_for_scenario(scenario["id"])
        variant = store.get_or_create_default_input_variant(case["id"])
        scenarios[key]["variant_id"] = variant["id"]
        if key == "partial":
            continue
        price_set = create_console_price_set(store, scenario["id"])
        store.upsert_case_time_series_binding(
            case_input_variant_id=variant["id"], signal_key="import_price_usd_per_mwh",
            time_series_set_id=price_set["id"],
        )
        period = {"range_start": price_set["horizon"]["start"], "range_end": price_set["horizon"]["end"]}
        store.validate_case_input_variant(
            scenario_id=scenario["id"], case_input_variant_id=variant["id"], **period,
        )
        scenarios[key].update({"set_id": price_set["id"], **period})
        if key == "stale":
            store.edit_time_series_set_values(
                project_id=owner["id"], time_series_set_id=price_set["id"],
                edits=[CatalogValueEdit(period_index=0, signal_key="import_price_usd_per_mwh", value_text="999.0")],
            )
        else:
            document = console_document_with_scalar_parameter(groups=[])
            document["parameters"][0].update({"min": 0, "max": 4, "default": 4})
            console = store.create_operator_console(
                case_id=case["id"], source_variant_id=variant["id"], document=document,
                created_by_user_id=users["analyst"]["id"],
            )
            store.save_operator_console(
                console["id"], document=document, status="active", expected_revision=1,
                updated_by_user_id=users["analyst"]["id"],
            )
            store.validate_case_input_variant(
                scenario_id=scenario["id"], case_input_variant_id=console["owned_variant_id"], **period,
            )
            scenarios[key]["console_id"] = console["id"]
    for name, portal, operate in [("operator", False, True), ("reader", True, False)]:
        store.set_external_project_access(
            project_id=project["id"], user_id=users[name]["id"],
            portal_view=portal, operate=operate, updated_by="admin@ux.example.local",
        )
    comparison = store.create_scenario(project_id=project["id"], name="Comparacion de referencia")
    comparison_runs = [
        create_indexed_run(
            store, artifact_root, scenario_id=comparison["id"], objective_value_usd=value,
            date_range={"start": "2026-01-01T00:00:00-03:00", "end": "2026-01-01T02:00:00-03:00"},
        )["id"]
        for value in [1000.0, 1500.0]
    ]
    scenarios["comparison"] = {"id": comparison["id"], "name": comparison["name"], "run_ids": comparison_runs}
    manifest = {
        "project": {"id": project["id"], "name": project["name"]},
        "scenarios": scenarios, "c6": store.read_time_series_c6_state(),
        "canonical_read_accounts": ["verification@ux.example.local"],
        "database": "sqlite:///:memory:",
    }
    (artifact_root / "fixture.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    app = create_app(
        store=store, auth_enabled=True, validation_service=SmokeValidationService(),
        run_queue=SmokeRunQueue(store, artifact_root), artifact_root=artifact_root,
    )

    @app.get("/api/auth/smoke-token", include_in_schema=False)
    async def smoke_token():
        return {"token": os.environ["UX_BASELINE_TOKEN"]}

    uvicorn.run(app, host="127.0.0.1", port=8124, log_level="warning")


if __name__ == "__main__":
    main()
