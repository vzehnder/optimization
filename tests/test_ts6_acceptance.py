"""BESS-TS6-010: closing proof for the TS-6 transformations/automation iteration.

Tells one continuous TS-6 story: every allowlisted transformation derives a
new catalog set with full lineage (inputs, revisions, hashes, validated
parameters, schema and implementation versions) while unknown types are
rejected before anything is written; a source edit marks derived outputs
stale, fail-closes any variant bound to them and regeneration advances a new
revision without rewriting history; mocked external forecast/programmed data
lands through the exact same source/set path as files, with issuer/validity
preserved per revision across reissues; scheduled and rolling-horizon
automation produce the same kind of immutable snapshots and TS-4-indexable
runs as the manual pipeline, keeping gate failures visible; and manual
variant-driven runs remain byte-level unchanged by all of the above.
"""

import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from app.persistence import AnalystStore
from app.result_indexing import rebuild_run_results
from app.time_series_catalog import (
    CatalogValueEdit,
    prepare_time_series_catalog_import,
)
from app.transformations import (
    TRANSFORMATION_REGISTRY,
    TransformationError,
    get_transformation_definition,
)
from app.variant_staleness import VariantStaleError
from tests.test_ts3_case_variant_api import grid_battery_draft_document
from tests.test_ts3_input_variants import price_rows
from tests.test_ts6_006_connector_ingestion import (
    connector_source,
    forecast_import_request,
    forecast_records,
)
from tests.test_ts6_007_program_metadata import (
    program_import_request,
    program_metadata,
    program_records,
)
from tests.test_ts6_008_schedules import (
    AcceptingValidationService,
    CapturingRunQueue,
    price_import_request,
)
from tests.test_ts6_apply_transformation import (
    demand_only_import_request,
    demand_only_rows,
    demand_price_import_request,
    demand_price_rows,
    demand_price_rows_with_gap,
    price_only_import_request,
    price_only_rows,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


def complete_run_with_result_artifacts(store, run_id, artifact_root):
    """Simulate the worker finishing a run: outputs on disk, run succeeded,
    artifacts registered — the same surface TS-4 indexing reads from."""
    output_dir = artifact_root / "runs" / str(run_id) / "outputs"
    output_dir.mkdir(parents=True)
    summary_path = output_dir / "summary.json"
    dispatch_path = output_dir / "dispatch.csv"
    asset_dispatch_path = output_dir / "asset_dispatch.csv"
    summary_path.write_text(
        json.dumps(
            {
                "case_name": "grid_battery",
                "solver_status": "OPTIMAL",
                "termination_status": "OPTIMAL",
                "objective_value_usd": 1250.5,
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    dispatch_path.write_text(
        "timestamp,duration_hours,price_usd_per_mwh,grid_import_mw,grid_export_mw,net_grid_export_mw,"
        "renewable_used_mw,renewable_curtailed_mw,load_demand_mw,battery_charge_mw,battery_discharge_mw,"
        "battery_net_discharge_mw,battery_energy_mwh,battery_delta_soc_abs_mwh,market_value_usd,"
        "battery_degradation_cost_usd,curtailment_penalty_usd,period_profit_usd\n"
        "2026-08-01T00:00:00,1.0,45.0,2.5,0.0,-2.5,4.0,0.0,6.5,0.0,0.0,0.0,20.0,0.0,-112.5,0.0,0.0,-112.5\n",
        encoding="utf-8",
    )
    asset_dispatch_path.write_text(
        "timestamp,duration_hours,price_usd_per_mwh,asset_id,asset_type,grid_import_mw,grid_export_mw,"
        "renewable_used_mw,renewable_curtailed_mw,load_demand_mw,battery_charge_mw,battery_discharge_mw,"
        "battery_energy_mwh,battery_delta_soc_abs_mwh\n"
        "2026-08-01T00:00:00,1.0,45.0,grid_1,grid,2.5,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0\n",
        encoding="utf-8",
    )
    store.mark_run_running(
        run_id,
        workspace_path=str(artifact_root / "runs" / str(run_id)),
        input_snapshot_path=str(
            artifact_root / "runs" / str(run_id) / "input" / "system_case.json"
        ),
    )
    run = store.mark_run_succeeded(
        run_id,
        exit_code=0,
        stdout="{}",
        stderr="",
        success_payload={"termination_status": "OPTIMAL"},
        output_dir=str(output_dir),
        summary_path=str(summary_path),
    )
    for artifact_type, path, display_name, media_type in [
        ("summary_json", summary_path, "summary.json", "application/json"),
        ("dispatch_csv", dispatch_path, "dispatch.csv", "text/csv"),
        ("asset_dispatch_csv", asset_dispatch_path, "asset_dispatch.csv", "text/csv"),
    ]:
        store.register_run_artifact(
            run_id=run_id,
            artifact_type=artifact_type,
            path=str(path),
            display_name=display_name,
            media_type=media_type,
        )
    return run


def import_catalog_set(store, scenario_id, *, rows, request, source_id):
    prepared = prepare_time_series_catalog_import(rows=rows, request=request)
    return store.import_time_series_catalog_set(
        scenario_id=scenario_id,
        source={
            "id": source_id,
            "original_filename": f"{source_id}.csv",
            "media_type": "text/csv",
            "checksum": f"sha256:{source_id}",
        },
        prepared_import=prepared,
    )


class TS6AcceptanceTests(unittest.TestCase):
    def test_allowlist_covers_exactly_the_accepted_transformations_and_rejects_unknown_types(self):
        # Decision 2 of the TS-6 decision record: exactly these four ship.
        self.assertEqual(
            sorted(TRANSFORMATION_REGISTRY),
            ["combine_signals", "interpolate_gaps", "resample", "scale_signal"],
        )
        for definition in TRANSFORMATION_REGISTRY.values():
            self.assertGreaterEqual(definition.implementation_version, 1)
            self.assertGreaterEqual(definition.parameter_schema_version, 1)

        with self.assertRaisesRegex(TransformationError, "unsupported transformation_type"):
            get_transformation_definition("drop_table_users")

        # The store enforces the same allowlist before validating or writing.
        store = AnalystStore("sqlite:///:memory:")
        self.addCleanup(store.close)
        project = store.create_project(name="TS6 acceptance allowlist project")
        scenario = store.create_scenario(project_id=project["id"], name="Allowlist scenario")
        source_set = import_catalog_set(
            store,
            scenario["id"],
            rows=demand_price_rows(datetime(2026, 7, 1), 4),
            request=demand_price_import_request(),
            source_id="ts6-acceptance-allowlist",
        )
        with self.assertRaisesRegex(TransformationError, "unsupported transformation_type"):
            store.apply_time_series_transformation(
                project_id=project["id"],
                time_series_set_id=source_set["id"],
                transformation_type="shift_timezone_display",
                raw_parameters={},
            )
        listed = store.list_time_series_sets(project["id"])
        self.assertEqual([item["id"] for item in listed], [source_set["id"]])

    def test_every_allowlisted_transformation_derives_a_set_with_full_lineage(self):
        store = AnalystStore("sqlite:///:memory:")
        self.addCleanup(store.close)
        project = store.create_project(name="TS6 acceptance lineage project")
        scenario = store.create_scenario(project_id=project["id"], name="Lineage scenario")
        base_set = import_catalog_set(
            store,
            scenario["id"],
            rows=demand_price_rows(datetime(2026, 7, 1), 4),
            request=demand_price_import_request(),
            source_id="ts6-acceptance-base",
        )
        gap_set = import_catalog_set(
            store,
            scenario["id"],
            rows=demand_price_rows_with_gap(datetime(2026, 7, 2), range(5), {3}),
            request=demand_price_import_request(version_label="gap"),
            source_id="ts6-acceptance-gap",
        )
        price_set = import_catalog_set(
            store,
            scenario["id"],
            rows=price_only_rows(datetime(2026, 7, 3), 3),
            request=price_only_import_request(),
            source_id="ts6-acceptance-price-only",
        )
        demand_set = import_catalog_set(
            store,
            scenario["id"],
            rows=demand_only_rows(datetime(2026, 7, 3), 3),
            request=demand_only_import_request(),
            source_id="ts6-acceptance-demand-only",
        )

        scaled = store.apply_time_series_transformation(
            project_id=project["id"],
            time_series_set_id=base_set["id"],
            transformation_type="scale_signal",
            raw_parameters={"signal_key": "load_demand_mw", "scale_factor": 1.5},
        )
        resampled = store.apply_time_series_transformation(
            project_id=project["id"],
            time_series_set_id=base_set["id"],
            transformation_type="resample",
            raw_parameters={
                "target_resolution_hours": 2.0,
                "signal_methods": {
                    "load_demand_mw": "mean",
                    "import_price_usd_per_mwh": "mean",
                },
            },
        )
        interpolated = store.apply_time_series_transformation(
            project_id=project["id"],
            time_series_set_id=gap_set["id"],
            transformation_type="interpolate_gaps",
            raw_parameters={"method": "linear", "max_gap_hours": 2.0},
        )
        combined = store.apply_time_series_combination(
            project_id=project["id"],
            transformation_type="combine_signals",
            raw_parameters={
                "inputs": [
                    {
                        "time_series_set_id": price_set["id"],
                        "signal_keys": ["import_price_usd_per_mwh"],
                    },
                    {
                        "time_series_set_id": demand_set["id"],
                        "signal_keys": ["load_demand_mw"],
                    },
                ]
            },
        )

        expectations = [
            (scaled, "scale_signal", [base_set]),
            (resampled, "resample", [base_set]),
            (interpolated, "interpolate_gaps", [gap_set]),
            (combined, "combine_signals", [price_set, demand_set]),
        ]
        for derived, transformation_type, input_sets in expectations:
            with self.subTest(transformation_type=transformation_type):
                self.assertEqual(derived["data_kind"], "derived")
                lineage = derived["revision_metadata"]["transformation"]
                definition = TRANSFORMATION_REGISTRY[transformation_type]
                self.assertEqual(lineage["type"], transformation_type)
                self.assertEqual(
                    lineage["implementation_version"], definition.implementation_version
                )
                self.assertEqual(
                    lineage["parameter_schema_version"],
                    definition.parameter_schema_version,
                )
                self.assertTrue(lineage["parameters"])
                self.assertEqual(len(lineage["inputs"]), len(input_sets))
                for lineage_input, input_set in zip(lineage["inputs"], input_sets):
                    self.assertEqual(
                        lineage_input["time_series_set_id"], input_set["id"]
                    )
                    self.assertEqual(
                        lineage_input["revision_number"], input_set["revision_number"]
                    )
                    self.assertEqual(
                        lineage_input["content_hash"], input_set["content_hash"]
                    )
                    self.assertTrue(lineage_input["signals"])

                # The same inputs are also registered as generic validation
                # dependencies (Decision 5), including the implementation pin.
                dependencies = store.get_time_series_set_validation_dependencies(
                    derived["id"]
                )
                dependency_pairs = {
                    (item["dependency_type"], item["dependency_id"]): item["hash"]
                    for item in dependencies
                }
                for input_set in input_sets:
                    self.assertEqual(
                        dependency_pairs[("time_series_set", str(input_set["id"]))],
                        input_set["content_hash"],
                    )
                self.assertEqual(
                    dependency_pairs[
                        ("transformation_implementation", transformation_type)
                    ],
                    str(definition.implementation_version),
                )

        # Transformations never mutate their sources: content hashes intact.
        for original in [base_set, gap_set, price_set, demand_set]:
            current = store.get_time_series_set(project["id"], original["id"])
            self.assertEqual(current["content_hash"], original["content_hash"])
            self.assertEqual(current["revision_number"], 1)

        # Correct values on the derived outputs (spot checks, one per type).
        scaled_demand = [
            value["value_numeric"]
            for value in scaled["values"]
            if value["signal_key"] == "load_demand_mw"
        ]
        self.assertEqual(scaled_demand[0], 150.0)
        self.assertEqual(len(resampled["periods"]), 2)
        self.assertEqual(len(interpolated["periods"]), 5)
        self.assertEqual(
            interpolated["revision_metadata"]["transformation"]["execution"][
                "filled_period_indexes"
            ],
            [3],
        )
        self.assertEqual(
            sorted({value["signal_key"] for value in combined["values"]}),
            ["import_price_usd_per_mwh", "load_demand_mw"],
        )

    def test_source_edits_mark_derived_sets_stale_and_regeneration_preserves_history(self):
        store = AnalystStore("sqlite:///:memory:")
        self.addCleanup(store.close)
        project = store.create_project(name="TS6 acceptance staleness project")
        scenario = store.create_scenario(project_id=project["id"], name="Stale scenario")
        store.create_or_replace_scenario_draft(
            scenario_id=scenario["id"], document=grid_battery_draft_document()
        )
        case = store.get_or_create_case_for_scenario(scenario["id"])
        variant = store.get_or_create_default_input_variant(case["id"])
        source_set = import_catalog_set(
            store,
            scenario["id"],
            rows=price_rows(datetime(2026, 8, 1), 24),
            request=price_import_request(),
            source_id="ts6-acceptance-stale-price",
        )
        derived = store.apply_time_series_transformation(
            project_id=project["id"],
            time_series_set_id=source_set["id"],
            transformation_type="scale_signal",
            raw_parameters={
                "signal_key": "import_price_usd_per_mwh",
                "scale_factor": 2.0,
            },
        )
        store.upsert_case_time_series_binding(
            case_input_variant_id=variant["id"],
            signal_key="import_price_usd_per_mwh",
            time_series_set_id=derived["id"],
        )
        store.validate_case_input_variant(
            scenario_id=scenario["id"],
            case_input_variant_id=variant["id"],
            range_start=derived["horizon"]["start"],
            range_end=derived["horizon"]["end"],
        )
        self.assertFalse(
            store.evaluate_time_series_set_staleness(project["id"], derived["id"])["stale"]
        )

        store.edit_time_series_set_values(
            project_id=project["id"],
            time_series_set_id=source_set["id"],
            edits=[
                CatalogValueEdit(
                    period_index=0,
                    signal_key="import_price_usd_per_mwh",
                    value_text="500.0",
                )
            ],
        )

        # Layer 1: the derived set itself is stale relative to its recipe.
        staleness = store.evaluate_time_series_set_staleness(project["id"], derived["id"])
        self.assertTrue(staleness["stale"])
        listed = {item["id"]: item for item in store.list_time_series_sets(project["id"])}
        self.assertTrue(listed[derived["id"]]["stale"])
        self.assertFalse(listed[source_set["id"]]["stale"])

        # Layer 2: a variant bound to a known-stale derived set fails closed,
        # for materialization and for revalidation alike.
        def materialize():
            return store.materialize_system_case_for_variant(
                scenario_id=scenario["id"],
                case_input_variant_id=variant["id"],
                range_start=derived["horizon"]["start"],
                range_end=derived["horizon"]["end"],
            )

        with self.assertRaises(VariantStaleError):
            materialize()
        with self.assertRaises(VariantStaleError):
            store.validate_case_input_variant(
                scenario_id=scenario["id"],
                case_input_variant_id=variant["id"],
                range_start=derived["horizon"]["start"],
                range_end=derived["horizon"]["end"],
            )

        # Regeneration advances a new revision of the same set and never
        # rewrites history: revision 1 keeps its original content hash.
        regenerated = store.regenerate_derived_time_series_set(
            project_id=project["id"], time_series_set_id=derived["id"]
        )
        self.assertEqual(regenerated["id"], derived["id"])
        self.assertEqual(regenerated["revision_number"], 2)
        self.assertNotEqual(regenerated["content_hash"], derived["content_hash"])
        scaled_first = next(
            value["value_numeric"]
            for value in regenerated["values"]
            if value["period_index"] == 0
            and value["signal_key"] == "import_price_usd_per_mwh"
        )
        self.assertEqual(scaled_first, 1000.0)
        revisions = {
            revision["revision_number"]: revision
            for revision in store.list_time_series_set_revisions(
                project["id"], derived["id"]
            )
        }
        self.assertEqual(revisions[1]["content_hash"], derived["content_hash"])
        self.assertFalse(
            store.evaluate_time_series_set_staleness(project["id"], derived["id"])["stale"]
        )

        # The variant is still stale (its recorded hash predates regeneration)
        # until explicitly revalidated; then the manual gate opens again.
        self.assertTrue(
            store.evaluate_case_input_variant_staleness(
                scenario_id=scenario["id"], case_input_variant_id=variant["id"]
            )["stale"]
        )
        with self.assertRaises(VariantStaleError):
            materialize()
        store.validate_case_input_variant(
            scenario_id=scenario["id"],
            case_input_variant_id=variant["id"],
            range_start=derived["horizon"]["start"],
            range_end=derived["horizon"]["end"],
        )
        materialized = materialize()
        self.assertEqual(
            materialized["system_case"]["time_series"][0]["import_price_usd_per_mwh"],
            1000.0,
        )

    def test_mocked_connector_data_lands_through_the_common_source_set_path(self):
        store = AnalystStore("sqlite:///:memory:")
        self.addCleanup(store.close)
        project = store.create_project(name="TS6 acceptance connector project")

        def ingest(rows, *, request=None, program=None, fetched_at="2026-08-01T12:00:00+00:00"):
            prepared = prepare_time_series_catalog_import(
                rows=rows, request=request or forecast_import_request()
            )
            return store.ingest_connector_time_series_set(
                project_id=project["id"],
                source=connector_source(rows, fetched_at=fetched_at),
                prepared_import=prepared,
                program=program,
                created_by="analyst@example.com",
            )

        # First ingestion: a validated forecast set with a connector source,
        # in the same catalog table any CSV/XLSX upload lands in.
        created = ingest(forecast_records())
        self.assertEqual(created["outcome"], "created")
        forecast_set = created["time_series_set"]
        self.assertEqual(forecast_set["data_kind"], "forecast")
        self.assertEqual(forecast_set["status"], "validated")
        self.assertEqual(forecast_set["revision_number"], 1)
        listed_ids = [item["id"] for item in store.list_time_series_sets(project["id"])]
        self.assertIn(forecast_set["id"], listed_ids)

        # Unchanged re-ingest converges without writing anything.
        converged = ingest(forecast_records())
        self.assertEqual(converged["outcome"], "converged")
        self.assertEqual(
            converged["time_series_set"]["revision_number"], 1
        )

        # Changed data advances exactly one revision; revision 1 survives.
        changed_rows = forecast_records()
        changed_rows[0]["demand"] = "150.0"
        new_revision = ingest(changed_rows, fetched_at="2026-08-01T18:00:00+00:00")
        self.assertEqual(new_revision["outcome"], "new_revision")
        self.assertEqual(new_revision["time_series_set"]["revision_number"], 2)
        revisions = {
            revision["revision_number"]: revision
            for revision in store.list_time_series_set_revisions(
                project["id"], forecast_set["id"]
            )
        }
        self.assertEqual(revisions[1]["content_hash"], forecast_set["content_hash"])
        self.assertNotEqual(
            revisions[2]["content_hash"], forecast_set["content_hash"]
        )

        # Programmed official data additionally records issuer and validity,
        # and a reissue with identical values still lands as a new revision so
        # each revision keeps the exact program version it was issued under.
        first_program = program_metadata()
        programmed = ingest(
            program_records(), request=program_import_request(), program=first_program
        )
        self.assertEqual(programmed["outcome"], "created")
        programmed_set = programmed["time_series_set"]
        self.assertEqual(programmed_set["data_kind"], "programmed")
        self.assertEqual(
            programmed_set["revision_metadata"]["program"], first_program
        )

        reissued_program = program_metadata(
            issued_at="2026-08-01T16:00:00+00:00",
            valid_until="2026-08-04T00:00:00+00:00",
        )
        reissued = ingest(
            program_records(),
            request=program_import_request(),
            program=reissued_program,
            fetched_at="2026-08-01T16:30:00+00:00",
        )
        self.assertEqual(reissued["outcome"], "new_revision")
        self.assertEqual(reissued["time_series_set"]["revision_number"], 2)
        self.assertEqual(
            reissued["time_series_set"]["content_hash"], programmed_set["content_hash"]
        )
        program_revisions = {
            revision["revision_number"]: revision["program"]
            for revision in store.list_time_series_set_revisions(
                project["id"], programmed_set["id"]
            )
        }
        self.assertEqual(program_revisions[1], first_program)
        self.assertEqual(program_revisions[2], reissued_program)

    def _scheduling_client(self):
        """API client plus a validated default variant ready to run."""
        run_queue = CapturingRunQueue()
        client = TestClient(
            create_app(
                validation_service=AcceptingValidationService(),
                database_url="sqlite:///:memory:",
                run_queue=run_queue,
            )
        )
        store = client.app.state.analyst_store
        project = store.create_project(name="TS6 acceptance automation project")
        scenario = store.create_scenario(
            project_id=project["id"], name="Automation scenario"
        )
        store.create_or_replace_scenario_draft(
            scenario_id=scenario["id"], document=grid_battery_draft_document()
        )
        case = store.get_or_create_case_for_scenario(scenario["id"])
        variant = store.get_or_create_default_input_variant(case["id"])
        price_set = import_catalog_set(
            store,
            scenario["id"],
            rows=price_rows(datetime(2026, 8, 1), 24),
            request=price_import_request(),
            source_id="ts6-acceptance-automation-price",
        )
        store.upsert_case_time_series_binding(
            case_input_variant_id=variant["id"],
            signal_key="import_price_usd_per_mwh",
            time_series_set_id=price_set["id"],
        )
        store.validate_case_input_variant(
            scenario_id=scenario["id"],
            case_input_variant_id=variant["id"],
            range_start=price_set["horizon"]["start"],
            range_end=price_set["horizon"]["end"],
        )
        return client, store, run_queue, scenario, variant, price_set

    def test_scheduled_runs_create_the_same_snapshots_and_indexed_results_as_manual_runs(self):
        client, store, run_queue, scenario, variant, price_set = self._scheduling_client()

        # Manual variant-driven run first: the reference contract.
        manual_response = client.post(
            f"/api/scenarios/{scenario['id']}/case/variants/{variant['id']}/run",
            json={
                "range_start": price_set["horizon"]["start"],
                "range_end": price_set["horizon"]["end"],
            },
        )
        self.assertEqual(manual_response.status_code, 201, manual_response.text)
        manual_run = store.get_run(manual_response.json()["id"])
        manual_metadata = store.get_scenario_version(manual_run["scenario_version_id"])[
            "generation_metadata"
        ]

        # Scheduled rerun of the same case + variant + range (admin surface).
        create_response = client.post(
            "/api/admin/schedules",
            json={
                "scenario_id": scenario["id"],
                "case_input_variant_id": variant["id"],
                "display_name": "TS6 acceptance daily rerun",
                "range_start": price_set["horizon"]["start"],
                "range_end": price_set["horizon"]["end"],
                "cadence": "daily",
                "next_run_at": "2026-08-06T09:00:00+00:00",
            },
        )
        self.assertEqual(create_response.status_code, 201, create_response.text)
        run_due_response = client.post(
            "/api/admin/schedules/run-due",
            json={"now": "2026-08-06T10:00:00+00:00"},
        )
        self.assertEqual(run_due_response.status_code, 200, run_due_response.text)
        [tick] = run_due_response.json()["ticks"]
        self.assertEqual(tick["status"], "queued")
        scheduled_run = store.get_run(tick["run_id"])
        scheduled_metadata = store.get_scenario_version(
            scheduled_run["scenario_version_id"]
        )["generation_metadata"]

        # Same snapshot contract: identical lineage keys and values, except
        # the scheduled run additionally records its automation lineage.
        for key in ["kind", "input_variant", "date_range", "series_bindings"]:
            self.assertEqual(scheduled_metadata[key], manual_metadata[key])
        self.assertNotIn("automation", manual_metadata)
        self.assertEqual(
            scheduled_metadata["automation"]["schedule_tick_id"], tick["id"]
        )
        self.assertEqual(manual_run["trigger_type"], "manual")
        self.assertEqual(scheduled_run["trigger_type"], "scheduled")
        self.assertEqual(
            run_queue.enqueued_run_ids, [manual_run["id"], scheduled_run["id"]]
        )

        # Both runs list side by side, and the scheduled one indexes through
        # the exact same TS-4 path once the worker completes it.
        listed_ids = [run["id"] for run in store.list_scenario_runs(scenario["id"])]
        self.assertEqual(sorted(listed_ids), sorted([manual_run["id"], scheduled_run["id"]]))
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_root = Path(temp_dir) / "artifacts"
            completed = complete_run_with_result_artifacts(
                store, scheduled_run["id"], artifact_root
            )
            rebuild = rebuild_run_results(
                store=store, run=completed, artifact_root=artifact_root
            )
            self.assertEqual(rebuild["status"], "indexed")
            self.assertIsNotNone(
                store.get_run_dispatch_result_index(scheduled_run["id"])
            )

    def test_rolling_schedules_resolve_ranges_per_tick_and_keep_failures_visible(self):
        client, store, run_queue, scenario, variant, price_set = self._scheduling_client()

        create_response = client.post(
            "/api/admin/schedules",
            json={
                "scenario_id": scenario["id"],
                "case_input_variant_id": variant["id"],
                "display_name": "TS6 acceptance rolling rerun",
                "range_start": "2020-01-01T00:00:00+00:00",
                "range_end": "2020-01-02T00:00:00+00:00",
                "cadence": "daily",
                "next_run_at": price_set["horizon"]["start"],
                "range_mode": "rolling",
                "rolling_start_offset_hours": 0,
                "rolling_duration_hours": 24,
            },
        )
        self.assertEqual(create_response.status_code, 201, create_response.text)
        schedule = create_response.json()["schedule"]
        self.assertEqual(schedule["range_mode"], "rolling")

        # First tick: due window covered by data, snapshot records the
        # per-tick resolved range, not the placeholder creation range.
        first_response = client.post(
            "/api/admin/schedules/run-due",
            json={"now": "2026-08-01T01:00:00-04:00"},
        )
        [first_tick] = first_response.json()["ticks"]
        self.assertEqual(first_tick["status"], "queued")
        self.assertEqual(first_tick["range_start"], price_set["horizon"]["start"])
        first_metadata = store.get_scenario_version(
            store.get_run(first_tick["run_id"])["scenario_version_id"]
        )["generation_metadata"]
        self.assertEqual(
            first_metadata["date_range"],
            {"start": first_tick["range_start"], "end": first_tick["range_end"]},
        )

        # Second tick rolls one day forward, past the covered horizon: the
        # gate fails closed, the failure stays visible, no run is created,
        # and the schedule stays active for the next tick.
        second_response = client.post(
            "/api/admin/schedules/run-due",
            json={"now": "2026-08-02T01:00:00-04:00"},
        )
        [second_tick] = second_response.json()["ticks"]
        self.assertEqual(second_tick["status"], "failed")
        self.assertIsNone(second_tick["run_id"])
        self.assertEqual(second_tick["range_start"], "2026-08-02T00:00:00-04:00")
        self.assertIn("missing coverage", second_tick["error_message"])
        self.assertEqual(run_queue.enqueued_run_ids, [first_tick["run_id"]])
        advanced = store.get_run_schedule(schedule["id"])
        self.assertTrue(advanced["is_active"])

    def test_manual_variant_driven_runs_are_unchanged_by_ts6_features(self):
        client, store, run_queue, scenario, variant, price_set = self._scheduling_client()
        project_id = store.get_scenario(scenario["id"])["project_id"]

        # TS-6 features coexist in the same project: a derived set (created
        # and regenerated) and an active schedule, neither bound to the
        # variant the manual run uses.
        derived = store.apply_time_series_transformation(
            project_id=project_id,
            time_series_set_id=price_set["id"],
            transformation_type="scale_signal",
            raw_parameters={
                "signal_key": "import_price_usd_per_mwh",
                "scale_factor": 3.0,
            },
        )
        store.regenerate_derived_time_series_set(
            project_id=project_id, time_series_set_id=derived["id"]
        )
        create_response = client.post(
            "/api/admin/schedules",
            json={
                "scenario_id": scenario["id"],
                "case_input_variant_id": variant["id"],
                "display_name": "Coexisting schedule",
                "range_start": price_set["horizon"]["start"],
                "range_end": price_set["horizon"]["end"],
                "cadence": "daily",
                "next_run_at": "2027-01-01T09:00:00+00:00",
            },
        )
        self.assertEqual(create_response.status_code, 201, create_response.text)

        # The manual variant-driven flow behaves exactly as it did in TS-3:
        # same endpoint, same lineage contract, no automation fields, and the
        # stale gate still governs it.
        run_response = client.post(
            f"/api/scenarios/{scenario['id']}/case/variants/{variant['id']}/run",
            json={
                "range_start": price_set["horizon"]["start"],
                "range_end": price_set["horizon"]["end"],
            },
        )
        self.assertEqual(run_response.status_code, 201, run_response.text)
        run = store.get_run(run_response.json()["id"])
        self.assertEqual(run["trigger_type"], "manual")
        metadata = store.get_scenario_version(run["scenario_version_id"])[
            "generation_metadata"
        ]
        self.assertEqual(metadata["kind"], "case_input_variant")
        self.assertNotIn("automation", metadata)
        self.assertEqual(
            metadata["series_bindings"][0]["time_series_set_id"], price_set["id"]
        )

        store.edit_time_series_set_values(
            project_id=project_id,
            time_series_set_id=price_set["id"],
            edits=[
                CatalogValueEdit(
                    period_index=0,
                    signal_key="import_price_usd_per_mwh",
                    value_text="123.0",
                )
            ],
        )
        stale_response = client.post(
            f"/api/scenarios/{scenario['id']}/case/variants/{variant['id']}/run",
            json={
                "range_start": price_set["horizon"]["start"],
                "range_end": price_set["horizon"]["end"],
            },
        )
        self.assertEqual(stale_response.status_code, 400)
        self.assertIn("stale", stale_response.text.lower())

    def test_ts6_documentation_tracker_and_issues_are_done(self):
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        issue = (
            REPO_ROOT
            / "docs"
            / "series_tiempo"
            / "iter6"
            / "issues"
            / "BESS-TS6-010-finalize-ts6-acceptance-suite-and-docs.md"
        ).read_text(encoding="utf-8")
        tracker = (
            REPO_ROOT / "docs" / "series_tiempo" / "iter6" / "issues" / "tracker_ts6.md"
        ).read_text(encoding="utf-8")
        manual = (
            REPO_ROOT / "docs" / "series_tiempo" / "iter6" / "pruebas_manuales_ts6.md"
        ).read_text(encoding="utf-8")
        architecture = (
            REPO_ROOT / "docs" / "series_tiempo" / "iter6" / "architecture_ts6_final.md"
        ).read_text(encoding="utf-8")

        self.assertIn("TS-6: Transformations, Connectors And Automation", readme)
        self.assertIn("tests.test_ts6_acceptance", readme)

        self.assertIn("Status: Done", issue)
        self.assertNotIn("- [ ]", issue)
        self.assertIn("tests.test_ts6_acceptance", issue)

        self.assertIn(
            "| BESS-TS6-010 | Finalize TS-6 Acceptance Suite And Docs | AFK | ready-for-agent | Done |",
            tracker,
        )
        self.assertIn("BESS-TS6-010 | Todo -> Done", tracker)
        self.assertNotIn("| Todo |", tracker)
        self.assertNotIn("| In Review |", tracker)
        self.assertIn("tests.test_ts6_acceptance", tracker)

        self.assertIn("Cierre TS-6", manual)
        self.assertIn("tests.test_ts6_acceptance", manual)

        self.assertIn("TRANSFORMATION_REGISTRY", architecture)
        self.assertIn("forecast_connector", architecture)
        self.assertIn("run_schedules", architecture)


if __name__ == "__main__":
    unittest.main()
