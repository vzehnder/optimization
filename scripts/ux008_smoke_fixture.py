"""Model and source data for the isolated operator-console browser journey."""

from tests.test_configuration_layer_operator_console import (
    create_console_price_set,
    operator_draft_document,
)


def seed_console_fixture(store):
    project = store.create_project(name="UX-008 Consola de referencia")
    scenario = store.create_scenario(project_id=project["id"], name="Batería Norte")
    store.create_or_replace_scenario_draft(
        scenario_id=scenario["id"], document=operator_draft_document()
    )
    case = store.get_or_create_case_for_scenario(scenario["id"])
    variant = store.get_or_create_default_input_variant(case["id"])
    prices = create_console_price_set(store, scenario["id"])
    store.upsert_case_time_series_binding(
        case_input_variant_id=variant["id"],
        signal_key="import_price_usd_per_mwh",
        time_series_set_id=prices["id"],
    )
    return {
        "project_id": project["id"], "scenario_id": scenario["id"],
        "variant_id": variant["id"], "horizon": prices["horizon"],
    }
