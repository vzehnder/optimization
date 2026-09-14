"""Canonical catalog fixture for the isolated React smoke server only."""

from tests.test_ts3_case_variant_api import grid_battery_draft_document
from tests.test_ts7_009_run_materialization import PRICE_SIGNAL


def seed_catalog_fixture(store):
    project = store.create_project(name="UX-004 Fuentes de referencia")
    scenario = store.create_scenario(project_id=project["id"], name="Modelo con precios")
    store.create_or_replace_scenario_draft(
        scenario_id=scenario["id"], document=grid_battery_draft_document()
    )
    case = store.get_or_create_case_for_scenario(scenario["id"])
    variant = store.get_or_create_default_input_variant(case["id"])
    target = store.ensure_global_signal_slot(project_id=project["id"], display_name="Red del modelo")
    periods = [
        {"timestamp_start": "2026-01-01T00:00:00+00:00", "timestamp_end": "2026-01-01T01:00:00+00:00", "duration_hours": 1},
        {"timestamp_start": "2026-01-01T01:00:00+00:00", "timestamp_end": "2026-01-01T02:00:00+00:00", "duration_hours": 1},
    ]
    receipts = []
    for name, values in [("Precio original", [70, 72]), ("Precio alternativo", [55, 60])]:
        receipts.append(store.publish_canonical_set_revision(
            project_id=project["id"], name=name, data_class_key="real", timezone="UTC",
            signals=[{**PRICE_SIGNAL, "display_name": name}], periods=periods,
            values={"energy_price": values}, actor="smoke-fixture",
        ))
    original = receipts[0]
    document = {"expected_bindings_revision": 0, "operations": [
        {"client_operation_id": role, "action": "create", "linkable_object_id": target["id"],
         "binding_role_key": role, "signal_id": original["signal_ids"]["energy_price"],
         "revision": {"mode": "current", "revision_id": original["revision_id"], "content_hash": original["content_hash"]},
         "catalog_association_id": None, "reason_code": "variant_input_selected"}
        for role in ("grid_import_price", "grid_export_price")
    ]}
    review = store.prevalidate_case_binding_batch(
        scenario_id=scenario["id"], variant_id=variant["id"], document=document, actor_class="internal_analyst",
    )
    store.commit_case_binding_batch(
        scenario_id=scenario["id"], variant_id=variant["id"], document=document,
        actor_user={"id": None, "email": "smoke-fixture", "role": "analyst"}, actor_class="internal_analyst",
        request_id="ux004-fixture", prevalidation_token=review["prevalidation_token"],
        if_match=review["commit_etag"], idempotency_key="ux004-fixture", confirmed=True,
    )
    return {"project_id": project["id"], "scenario_id": scenario["id"], "variant_id": variant["id"], "object_id": target["id"]}
