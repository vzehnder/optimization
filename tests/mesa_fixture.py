"""Independent two-hour demand fixture; setup only, observations use HTTP/UI."""

from tests.test_ts3_case_variant_api import grid_battery_draft_document


def seed_mesa_run(store, fixture, artifact_root, *, contract="bess_system_dispatch.v2", naive=False, frozen_zone=True):
    """Known artifact values, not an assertion of solver accuracy."""
    import csv
    import json
    from pathlib import Path
    from app.draft_editor import generate_system_case_from_draft
    from app.result_indexing import index_run_asset_dispatch_results

    document = generate_system_case_from_draft(store.get_scenario_draft(fixture["scenario"]["id"])["document"])
    document["schema_version"] = contract
    for node in document["nodes"]:
        node["display_name"] = {"load_north": "Demanda Norte", "solar_north": "Solar Norte"}.get(node["id"], node["id"])
    document["time_series"] = [
        {"timestamp": "2026-10-20T00:00:00-03:00", "duration_hours": 1.0},
        {"timestamp": "2026-10-20T01:00:00-03:00", "duration_hours": 1.0},
    ]
    if naive:
        for period in document["time_series"]:
            period["timestamp"] = period["timestamp"][:19]
    version = store.create_scenario_version(scenario_id=fixture["scenario"]["id"], system_case_json=document,
        validation_payload={"status": "ok"}, generation_metadata={"input_variant": {"id": fixture["variant"]["id"]},
        "series_bindings": [{"set_revision_id": fixture["receipt"]["revision_id"], "content_hash": fixture["receipt"]["content_hash"]}] if frozen_zone else []})
    run = store.create_run(scenario_version_id=version["id"])
    root = Path(artifact_root) / f"mesa-run-{run['id']}"
    root.mkdir(parents=True, exist_ok=True)
    summary = root / "summary.json"
    summary.write_text(json.dumps({"termination_status": "OPTIMAL"}), encoding="utf8")
    path = root / "asset_dispatch.csv"
    with path.open("w", newline="", encoding="utf8") as output:
        writer = csv.writer(output)
        writer.writerow(["timestamp", "duration_hours", "asset_id", "asset_type", "battery_charge_mw", "battery_discharge_mw", "battery_energy_mwh", "renewable_used_mw", "renewable_curtailed_mw"])
        rows = [
            ["2026-10-20T00:00:00-03:00", 1, "battery_1", "battery", 0, 2, 2, "", ""],
            ["2026-10-20T01:00:00-03:00", 1, "battery_1", "battery", 1, 0, 2.95, "", ""],
            ["2026-10-20T00:00:00-03:00", 1, "solar_north", "renewable", "", "", "", 2, 1],
            ["2026-10-20T01:00:00-03:00", 1, "solar_north", "renewable", "", "", "", 4, 1],
        ]
        if naive:
            for row in rows:
                row[0] = row[0][:19]
        writer.writerows(rows)
    store.mark_run_running(run["id"], workspace_path=str(root), input_snapshot_path=str(root / "input.json"))
    run = store.mark_run_succeeded(run["id"], exit_code=0, stdout="", stderr="", success_payload={"termination_status": "OPTIMAL"}, output_dir=str(root), summary_path=str(summary))
    artifact = store.register_run_artifact(run_id=run["id"], artifact_type="asset_dispatch_csv", path=str(path), display_name="asset_dispatch.csv", media_type="text/csv")
    index_run_asset_dispatch_results(store=store, run=run, artifacts=[artifact], artifact_root=artifact_root)
    return run


def seed_mesa_case(store, *, name="Caso de demanda", values=(10.0, 12.0), key="load_north", variant_name=None, electrical=False):
    project = store.create_project(name=f"Proyecto {name}")
    scenario = store.create_scenario(project_id=project["id"], name=name)
    document = grid_battery_draft_document()
    document["assets"].append({"id": key, "type": "load", "display_name": "Demanda Norte"})
    if electrical:
        document["assets"].append({"id": "solar_north", "type": "renewable", "display_name": "Solar Norte", "curtailment_penalty_usd_per_mwh": 0.0})
    store.create_or_replace_scenario_draft(scenario_id=scenario["id"], document=document)
    store.materialize_project_linkable_objects(project_id=project["id"])
    obj = store.ensure_project_component(
        project_id=project["id"], component_key=key,
        component_type="load", display_name="Demanda Norte",
    )
    case = store.get_or_create_case_for_scenario(scenario["id"])
    default_variant = store.get_or_create_default_input_variant(case["id"])
    variant = store.create_case_input_variant(case_id=case["id"], display_name=variant_name) if variant_name else default_variant
    receipt = store.publish_canonical_set_revision(
        project_id=project["id"], name="Demanda horaria", data_class_key="real",
        timezone="America/Santiago",
        signals=[{
            "series_key": "demand", "display_name": "Demanda medida",
            "semantic_type_key": "load_demand", "unit_key": "mw",
            "signal_role": "input", "aggregation": "mean",
        }],
        periods=[
            {"timestamp_start": "2026-10-20T00:00:00-03:00", "timestamp_end": "2026-10-20T01:00:00-03:00", "duration_hours": 1.0},
            {"timestamp_start": "2026-10-20T01:00:00-03:00", "timestamp_end": "2026-10-20T02:00:00-03:00", "duration_hours": 1.0},
        ],
        values={"demand": list(values)}, actor="mesa-fixture",
    )
    document = {"expected_bindings_revision": 0, "operations": [{
        "client_operation_id": "demand", "action": "create",
        "linkable_object_id": obj["id"], "binding_role_key": "load_demand",
        "signal_id": receipt["signal_ids"]["demand"],
        "revision": {"mode": "current", "revision_id": receipt["revision_id"], "content_hash": receipt["content_hash"]},
        "catalog_association_id": None, "reason_code": "variant_input_selected",
    }]}
    preview = store.prevalidate_case_binding_batch(
        scenario_id=scenario["id"], variant_id=variant["id"], document=document, actor_class="internal",
    )
    store.commit_case_binding_batch(
        scenario_id=scenario["id"], variant_id=variant["id"], document=document,
        actor_user={"id": 1, "email": "mesa-fixture", "role": "analyst"}, actor_class="internal",
        request_id=f"mesa-{scenario['id']}", prevalidation_token=preview["prevalidation_token"],
        if_match=preview["commit_etag"], idempotency_key=f"mesa-{scenario['id']}", confirmed=True,
    )
    if electrical:
        solar = store.ensure_project_component(project_id=project["id"], component_key="solar_north", component_type="renewable", display_name="Solar Norte")
        solar_receipt = store.publish_canonical_set_revision(
            project_id=project["id"], name="Disponibilidad solar", data_class_key="real", timezone="America/Santiago",
            signals=[{"series_key": "solar", "display_name": "Disponibilidad solar", "semantic_type_key": "renewable_available_power", "unit_key": "mw", "signal_role": "input", "aggregation": "mean"}],
            periods=[{"timestamp_start": "2026-10-20T00:00:00-03:00", "timestamp_end": "2026-10-20T01:00:00-03:00", "duration_hours": 1.0},
                     {"timestamp_start": "2026-10-20T01:00:00-03:00", "timestamp_end": "2026-10-20T02:00:00-03:00", "duration_hours": 1.0}],
            values={"solar": [3.0, 5.0]}, actor="mesa-fixture",
        )
        document = {"expected_bindings_revision": 1, "operations": [{
            "client_operation_id": "solar", "action": "create", "linkable_object_id": solar["id"], "binding_role_key": "renewable_available_power",
            "signal_id": solar_receipt["signal_ids"]["solar"],
            "revision": {"mode": "current", "revision_id": solar_receipt["revision_id"], "content_hash": solar_receipt["content_hash"]},
            "catalog_association_id": None, "reason_code": "variant_input_selected",
        }]}
        preview = store.prevalidate_case_binding_batch(scenario_id=scenario["id"], variant_id=variant["id"], document=document, actor_class="internal")
        store.commit_case_binding_batch(scenario_id=scenario["id"], variant_id=variant["id"], document=document,
            actor_user={"id": 1, "email": "mesa-fixture", "role": "analyst"}, actor_class="internal",
            request_id=f"mesa-solar-{scenario['id']}", prevalidation_token=preview["prevalidation_token"],
            if_match=preview["commit_etag"], idempotency_key=f"mesa-solar-{scenario['id']}", confirmed=True)
    return {"project": project, "scenario": scenario, "case": case, "variant": variant, "default_variant": default_variant, "object": obj, "receipt": receipt}
