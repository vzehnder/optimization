"""Known electrical result artifacts for comparison, not a solver-accuracy fixture."""

import csv
import json
from pathlib import Path

from app.result_indexing import index_run_asset_dispatch_results


def seed_comparison_runs(store, fixture, artifact_root):
    frozen = store.materialize_run_from_canonical_bindings(scenario_id=fixture["scenario"]["id"],
        variant_id=fixture["variant"]["id"], range_start="2026-10-20T00:00:00-03:00",
        range_end="2026-10-20T02:00:00-03:00", validate_text=None, actor_user={},
        request_id="comparison-fixture", prepare_only=True)
    metadata = {**frozen["generation_metadata"], "input_variant": {"id": fixture["variant"]["id"]}}
    for label, discharge in (("reference", (1, 3)), ("run", (2, 0))):
        version = store.create_scenario_version(scenario_id=fixture["scenario"]["id"],
            system_case_json=frozen["system_case"], generation_metadata=metadata, validation_payload={"status": "ok"})
        run = store.create_run(scenario_version_id=version["id"])
        fixture[label] = complete_comparison_run(store, run, artifact_root, discharge=discharge)
    return fixture


def complete_comparison_run(store, run, artifact_root, *, discharge=(2, 0), energy=(2, 2.95), indexed=True):
    root = Path(artifact_root) / f"comparison-{run['id']}"
    root.mkdir(parents=True, exist_ok=True)
    summary = root / "summary.json"
    summary.write_text(json.dumps({"termination_status": "OPTIMAL"}), encoding="utf8")
    snapshot = store.get_scenario_version(run["scenario_version_id"])["system_case_json"]
    path = root / "asset_dispatch.csv"
    with path.open("w", newline="", encoding="utf8") as output:
        writer = csv.writer(output)
        writer.writerow(["timestamp", "duration_hours", "asset_id", "asset_type", "battery_charge_mw",
                         "battery_discharge_mw", "battery_energy_mwh", "renewable_used_mw", "renewable_curtailed_mw"])
        for index, period in enumerate(snapshot["time_series"]):
            writer.writerow([period["timestamp"], period["duration_hours"], "battery_1", "battery",
                             [0, 1][index], discharge[index], energy[index], "", ""])
            writer.writerow([period["timestamp"], period["duration_hours"], "solar_north", "renewable",
                             "", "", "", [2, 4][index], 1])
    store.mark_run_running(run["id"], workspace_path=str(root), input_snapshot_path=str(root / "input.json"))
    run = store.mark_run_succeeded(run["id"], exit_code=0, stdout="", stderr="",
        success_payload={"termination_status": "OPTIMAL"}, output_dir=str(root), summary_path=str(summary))
    artifact = store.register_run_artifact(run_id=run["id"], artifact_type="asset_dispatch_csv", path=str(path),
        display_name="asset_dispatch.csv", media_type="text/csv")
    if indexed:
        index_run_asset_dispatch_results(store=store, run=run, artifacts=[artifact], artifact_root=artifact_root)
    return run
