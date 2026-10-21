"""Persisted hydraulic network for HTTP/browser observations, without a solver."""

import csv
import json
from pathlib import Path

from app.result_indexing import index_run_asset_dispatch_results


def bind_hydraulic_mesa_inflow(store, fixture, variant, values=(7, 9), *, reach=False):
    kind, key, role = ("hydraulic_reach", "reach", "minimum_flow") if reach else ("hydraulic_node", "reservoir", "natural_inflow")
    obj = next(o for o in store.list_linkable_objects(project_id=fixture["project"]["id"])
               if o["object_kind"] == kind and o["object_key"] == key)
    receipt = store.publish_canonical_set_revision(project_id=fixture["project"]["id"], name="Aporte canónico", data_class_key="real",
        timezone="UTC", signals=[{"series_key": "inflow", "display_name": "Caudal vinculado", "semantic_type_key": role,
            "unit_key": "m3_per_s", "signal_role": "input", "aggregation": "mean"}],
        periods=[{"timestamp_start": f"2026-10-20T0{i}:00:00+00:00", "timestamp_end": f"2026-10-20T0{i+1}:00:00+00:00", "duration_hours": 1} for i in (0, 1)],
        values={"inflow": list(values)}, actor="mesa-fixture")
    document = {"expected_bindings_revision": 0, "operations": [{"client_operation_id": "inflow", "action": "create",
        "linkable_object_id": obj["id"], "binding_role_key": role, "signal_id": receipt["signal_ids"]["inflow"],
        "revision": {"mode": "current", "revision_id": receipt["revision_id"], "content_hash": receipt["content_hash"]},
        "catalog_association_id": None, "reason_code": "variant_input_selected"}]}
    preview = store.prevalidate_case_binding_batch(scenario_id=fixture["scenario"]["id"], variant_id=variant["id"], document=document, actor_class="internal")
    store.commit_case_binding_batch(scenario_id=fixture["scenario"]["id"], variant_id=variant["id"], document=document,
        actor_user={"id": 1, "email": "mesa-fixture", "role": "analyst"}, actor_class="internal", request_id=f"hydro-{variant['id']}",
        prevalidation_token=preview["prevalidation_token"], if_match=preview["commit_etag"], idempotency_key=f"hydro-{variant['id']}", confirmed=True)
    return receipt


def seed_hydraulic_mesa_run(store, fixture, artifact_root):
    document = store.generate_hydraulic_v3_preview(fixture["scenario"]["id"])
    version = store.create_scenario_version(scenario_id=fixture["scenario"]["id"], system_case_json=document,
        validation_payload={"status": "ok"}, generation_metadata={"kind": "hydraulic_diagram_v3"})
    run = store.create_run(scenario_version_id=version["id"])
    root = Path(artifact_root) / f"hydraulic-mesa-{run['id']}"
    root.mkdir(parents=True)
    summary = root / "summary.json"
    summary.write_text(json.dumps({"termination_status": "OPTIMAL"}), encoding="utf8")
    path = root / "asset_dispatch.csv"
    # Julia writes local DateTime strings without offset; snapshot retains UTC.
    with path.open("w", newline="", encoding="utf8") as output:
        writer = csv.writer(output)
        writer.writerow(["timestamp", "duration_hours", "asset_id", "asset_type", "hydro_power_mw",
                         "hydro_turbine_flow_m3s", "hydro_storage_hm3", "hydro_reservoir_elevation_masl",
                         "hydro_spill_flow_m3s", "hydraulic_flow_m3s"])
        for i in (0, 1):
            start = f"2026-10-20T0{i}:00:00"
            writer.writerows([
                [start, 1, "unit_1", "hydraulic_unit", [3, 6][i], [4, 8][i], 0, 0, 0, 0],
                [start, 1, "unit_2", "hydraulic_unit", [9, 12][i], [12, 16][i], 0, 0, 0, 0],
                [start, 1, "reservoir", "hydraulic_reservoir", 0, 0, [9.8, 9.6][i], [709.8, 709.6][i], [1, 2][i], 0],
                [start, 1, "reach", "hydraulic_reach", 0, 0, 0, 0, 0, [16, 24][i]],
            ])
    store.mark_run_running(run["id"], workspace_path=str(root), input_snapshot_path=str(root / "input.json"))
    run = store.mark_run_succeeded(run["id"], exit_code=0, stdout="", stderr="", success_payload={"termination_status": "OPTIMAL"}, output_dir=str(root), summary_path=str(summary))
    artifact = store.register_run_artifact(run_id=run["id"], artifact_type="asset_dispatch_csv", path=str(path), display_name="asset_dispatch.csv", media_type="text/csv")
    index_run_asset_dispatch_results(store=store, run=run, artifacts=[artifact], artifact_root=artifact_root)
    return run


def seed_hydraulic_mesa(store, *, name="Consulta hidráulica", single_plant=False):
    project = store.create_project(name=f"Proyecto {name}")
    scenario = store.create_scenario(project_id=project["id"], name=name)
    empty = store.get_or_create_hydraulic_diagram(scenario["id"])
    nodes = [
        {"component_type": "reservoir", "technical_key": "reservoir", "display_name": "Embalse Alto", "x": 0, "y": 0,
         "reservoir": {"storage_min_hm3": 0, "storage_max_hm3": 20, "initial_storage_hm3": 10,
                       "terminal_condition": "none", "terminal_water_value_usd_per_hm3": 0},
         "storage_elevation_curve": {"version_label": "v1", "points": [{"x_value": 0, "y_value": 700}, {"x_value": 20, "y_value": 720}]},
         "natural_inflow_series": {"version_label": "v1", "points": [
             {"timestamp": "2026-10-20T00:00:00+00:00", "duration_hours": 1, "value_m3s": 2},
             {"timestamp": "2026-10-20T01:00:00+00:00", "duration_hours": 1, "value_m3s": 4}]}},
        {"component_type": "junction", "technical_key": "intake", "display_name": "Toma", "x": 100, "y": 0},
        {"component_type": "junction", "technical_key": "outlet", "display_name": "Descarga", "x": 400, "y": 0},
    ]
    for index in ((1,) if single_plant else (1, 2)):
        nodes.append({"component_type": "plant", "technical_key": f"plant_{index}", "display_name": "Central Norte",
            "x": 200, "y": index * 100, "plant": {"non_modeled": False, "min_power_mw": 0, "max_power_mw": 30},
            "units": [{"technical_key": f"unit_{index}", "display_name": "Unidad", "is_active": True,
                "intake_node_key": "intake", "discharge_node_key": "outlet", "min_power_mw": 0, "max_power_mw": 30,
                "min_flow_m3s": 0, "max_flow_m3s": 40,
                "flow_power_curve": {"version_label": "v1", "points": [{"x_value": 0, "y_value": 0}, {"x_value": 40, "y_value": 30}]}}]})
    diagram = store.save_hydraulic_diagram(scenario_id=scenario["id"], revision=empty["revision"], nodes=nodes,
        reaches=[{"technical_key": "reach", "display_name": "Canal", "from_node_key": "reservoir", "to_node_key": "intake",
                  "reach_type": "river", "routing_method": "none", "travel_time_hours": 0}])
    store.materialize_project_linkable_objects(project_id=project["id"])
    case = store.get_or_create_case_for_scenario(scenario["id"])
    variant = store.get_or_create_default_input_variant(case["id"])
    return {"project": project, "scenario": scenario, "case": case, "variant": variant, "diagram": diagram}
