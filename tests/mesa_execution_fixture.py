"""Executable two-hour case, using the same canonical sources as the mesa."""

from tests.mesa_fixture import seed_mesa_case
from tests.test_ts7_009_run_materialization import PRICE_SIGNAL


def seed_executable_mesa(store, *, name="Ejecución eléctrica"):
    fixture = seed_mesa_case(store, name=name, electrical=True)
    source = store.read_canonical_revision(fixture["receipt"]["revision_id"])
    price = store.publish_canonical_set_revision(
        project_id=fixture["project"]["id"], name="Precio eléctrico", data_class_key="real",
        timezone="America/Santiago", signals=[PRICE_SIGNAL], periods=source["periods"],
        values={"energy_price": [50.0, 100.0]}, actor="mesa-fixture",
    )
    obj = store.ensure_global_signal_slot(project_id=fixture["project"]["id"], display_name="Sistema")
    document = {"expected_bindings_revision": 2, "operations": [{
        "client_operation_id": role, "action": "create", "linkable_object_id": obj["id"],
        "binding_role_key": role, "signal_id": price["signal_ids"]["energy_price"],
        "revision": {"mode": "current", "revision_id": price["revision_id"], "content_hash": price["content_hash"]},
        "catalog_association_id": None, "reason_code": "variant_input_selected",
    } for role in ("grid_import_price", "grid_export_price")]}
    preview = store.prevalidate_case_binding_batch(scenario_id=fixture["scenario"]["id"],
        variant_id=fixture["variant"]["id"], document=document, actor_class="internal")
    store.commit_case_binding_batch(scenario_id=fixture["scenario"]["id"], variant_id=fixture["variant"]["id"],
        document=document, actor_user={"id": 1, "email": "mesa-fixture", "role": "analyst"}, actor_class="internal",
        request_id=f"mesa-prices-{fixture['scenario']['id']}", prevalidation_token=preview["prevalidation_token"],
        if_match=preview["commit_etag"], idempotency_key=f"mesa-prices-{fixture['scenario']['id']}", confirmed=True)
    return fixture
