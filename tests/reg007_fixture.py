"""A separate renewable consumer for calculated-power acceptance checks."""
from tests.test_ts3_case_variant_api import grid_battery_draft_document


def renewable_consumer(store, project_id, actor):
    scenario = store.create_scenario(project_id=project_id, name="Consumidor de potencia calculada")
    draft = grid_battery_draft_document()
    draft["case"]["name"] = "reg007_renewable"
    draft["grid"].update(id="reg007_grid", export_power_max_mw=50, import_power_max_mw=50)
    draft["assets"].append({"id": "reg007_solar", "type": "renewable", "category": "solar", "curtailment_penalty_usd_per_mwh": 0})
    store.create_or_replace_scenario_draft(scenario_id=scenario["id"], document=draft)
    solar = store.ensure_project_component(project_id=project_id, component_key="reg007_solar", component_type="renewable", display_name="Solar calculada", actor=actor)
    system = store.ensure_global_signal_slot(project_id=project_id, actor=actor)
    price = store.publish_canonical_set_revision(project_id=project_id, name="Precio consumidor REG007", data_class_key="real",
        signals=[{"series_key": "price", "semantic_type_key": "energy_price", "unit_key": "usd_per_mwh", "aggregation": "mean"}],
        periods=[{"timestamp_start": f"2026-01-01T0{t}:00:00", "timestamp_end": f"2026-01-01T0{t+1}:00:00", "duration_hours": 1} for t in range(4)],
        values={"price": [50, 50, 50, 50]}, actor=actor)
    return {"scenario_id": scenario["id"], "solar_object_id": solar["id"], "system_object_id": system["id"], "price": price}
