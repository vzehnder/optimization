"""BESS-TS5-011: closing proof for the TS-5 migration/unification iteration.

Tells one continuous TS-5 story: a legacy draft's embedded series extracts
into the generic catalog and binds to a variant; legacy hydraulic sets keep
reading through the common adapter while new hydraulic writes land in the
generic model, side by side; on-demand migration is idempotent and preserves
audit metadata; stale validation stays fail-closed for both an extracted and
a migrated series binding; the accepted permission matrix holds for analyst,
admin and client; and cleanup removes only rebuildable result indexes,
restorable through the existing rebuild path, while old runs stay readable
and historical scenario versions stay immutable throughout.
"""

import sqlite3
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.auth import hash_password
from app.main import create_app
from app.persistence import AnalystStore
from app.result_indexing import rebuild_run_results
from app.result_retention import cleanup_run_result_data
from app.time_series_catalog import (
    CatalogValueEdit,
    prepare_time_series_catalog_import,
)
from app.time_series_ingestion import (
    apply_time_series_mapping,
    attach_time_series_source,
    ingest_csv_source,
)
from app.variant_staleness import VariantStaleError
from tests.auth_test_helpers import login_json_with_csrf, post_json_with_csrf, put_json_with_csrf
from tests.test_results_review import (
    create_completed_run_with_result_artifacts,
    create_persisted_scenario_version,
)
from tests.test_ts5_draft_series_extraction import (
    csv_source_bytes,
    draft_document_with_load_and_renewable,
)
from tests.test_ts5_stale_validation_across_origins import (
    grid_battery_draft_document,
    price_import_request,
    price_rows,
)
from datetime import datetime


REPO_ROOT = Path(__file__).resolve().parents[1]


def _inflow_series(*values, version_label="v1"):
    return {
        "version_label": version_label,
        "points": [
            {
                "timestamp": f"2026-01-01T{index:02d}:00:00",
                "duration_hours": 1.0,
                "value_m3s": float(value),
            }
            for index, value in enumerate(values)
        ],
    }


def _reservoir_node(technical_key, display_name, x, y, *, inflow=None):
    node = {
        "component_type": "reservoir",
        "technical_key": technical_key,
        "display_name": display_name,
        "x": x,
        "y": y,
        "reservoir": {
            "storage_min_hm3": 5.0,
            "storage_max_hm3": 50.0,
            "initial_storage_hm3": 20.0,
            "terminal_condition": "none",
            "terminal_water_value_usd_per_hm3": 0.0,
        },
        "storage_elevation_curve": {
            "version_label": "v1",
            "points": [
                {"x_value": 5.0, "y_value": 700.0},
                {"x_value": 50.0, "y_value": 760.0},
            ],
        },
    }
    if inflow is not None:
        node["natural_inflow_series"] = inflow
    return node


def _seed_legacy_hydraulic_set(store, *, project_id, case_id, case_node_id, values, version_label="v1", version_number=1):
    """Insert a legacy ``hydraulic_time_series_sets`` row directly, simulating
    data written before TS5-003 (the public API can no longer produce it)."""
    base_row = store.connection.execute(
        "SELECT hydraulic_node_id FROM case_hydraulic_nodes WHERE id = ?",
        (case_node_id,),
    ).fetchone()
    base_entity_id = int(base_row[0])
    now = "2026-01-01T00:00:00+00:00"
    cursor = store.connection.execute(
        """
        INSERT INTO hydraulic_time_series_sets (
            project_id, entity_type, entity_id, signal_key, version_number,
            version_label, content_hash, status, created_at, updated_at,
            created_by, updated_by
        ) VALUES (?, 'hydraulic_node', ?, 'natural_inflow_m3s', ?, ?,
                  'legacy-seed-hash', 'draft', ?, ?, 'seed', 'seed')
        """,
        (project_id, base_entity_id, version_number, version_label, now, now),
    )
    set_id = int(cursor.lastrowid)
    for index, value in enumerate(values):
        store.connection.execute(
            """
            INSERT INTO hydraulic_time_series_points (
                hydraulic_time_series_set_id, point_index, timestamp,
                duration_hours, value
            ) VALUES (?, ?, ?, 1.0, ?)
            """,
            (set_id, index, f"2026-01-01T{index:02d}:00:00", float(value)),
        )
    store.connection.execute(
        """
        INSERT INTO case_hydraulic_time_series_bindings (
            case_id, entity_type, entity_id, signal_key,
            hydraulic_time_series_set_id, time_series_set_id, required,
            created_at, updated_at, created_by, updated_by
        ) VALUES (?, 'case_hydraulic_node', ?, 'natural_inflow_m3s', ?, NULL, 1, ?, ?, 'seed', 'seed')
        """,
        (case_id, case_node_id, set_id, now, now),
    )
    store.connection.commit()
    return set_id


class StubValidationService:
    def validate_text(self, candidate_text):
        raise AssertionError("validation not expected in these tests")

    def validate_file(self, candidate_path):
        raise AssertionError("validation not expected in these tests")


class TS5AcceptanceTests(unittest.TestCase):
    def test_legacy_draft_extraction_binds_to_variant_and_materializes_the_case(self):
        store = AnalystStore("sqlite:///:memory:")
        self.addCleanup(store.close)
        project = store.create_project(name="TS5 acceptance extraction project")
        scenario = store.create_scenario(
            project_id=project["id"], name="Legacy draft scenario"
        )
        store.create_or_replace_scenario_draft(
            scenario_id=scenario["id"],
            document=draft_document_with_load_and_renewable(),
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            input_source_root = Path(temp_dir) / "input-sources"
            draft = store.get_scenario_draft(scenario["id"])
            source = ingest_csv_source(
                draft_document=draft["document"],
                original_filename="legacy_prices.csv",
                content_type="text/csv",
                content=csv_source_bytes().encode("utf-8"),
                input_source_root=input_source_root,
            )
            updated_document = attach_time_series_source(draft["document"], source)
            store.update_scenario_draft(scenario_id=scenario["id"], document=updated_document)
            mapping = {
                "timestamp": "period_start",
                "duration_hours": "hours",
                "import_price_usd_per_mwh": "buy_price",
                "export_price_usd_per_mwh": "sell_price",
                "load_demand_mw": {"load_1": "load_1_demand"},
                "renewable_available_power_mw": {"solar_1": "solar_1_avail"},
            }
            draft = store.get_scenario_draft(scenario["id"])
            mapped_document, mapped_source = apply_time_series_mapping(
                document=draft["document"],
                source_id=source["id"],
                mapping=mapping,
                input_source_root=input_source_root,
            )
            store.update_scenario_draft(scenario_id=scenario["id"], document=mapped_document)

            created_set = store.extract_draft_time_series_set(
                scenario_id=scenario["id"],
                source_id=mapped_source["id"],
                set_name="Legacy case series",
                version_label="v1",
                data_kind="real",
                timezone_name="America/Santiago",
                created_by="analyst@example.local",
            )

        self.assertEqual(created_set["revision_metadata"]["origin"]["kind"], "legacy_draft_extraction")
        listed = store.list_time_series_sets(project["id"])
        self.assertIn(created_set["id"], [item["id"] for item in listed])

        case = store.get_or_create_case_for_scenario(scenario["id"])
        variant = store.get_or_create_default_input_variant(case["id"])
        for signal_key, entity_type, entity_id in [
            ("import_price_usd_per_mwh", None, None),
            ("export_price_usd_per_mwh", None, None),
            ("load_demand_mw", "component:load", "load_1"),
            ("renewable_available_power_mw", "component:renewable", "solar_1"),
        ]:
            store.upsert_case_time_series_binding(
                case_input_variant_id=variant["id"],
                signal_key=signal_key,
                entity_type=entity_type,
                entity_id=entity_id,
                time_series_set_id=created_set["id"],
            )

        self.assertFalse(
            store.evaluate_case_input_variant_staleness(
                scenario_id=scenario["id"], case_input_variant_id=variant["id"]
            )["stale"]
        )

        materialized = store.materialize_system_case_for_variant(
            scenario_id=scenario["id"],
            case_input_variant_id=variant["id"],
            range_start=created_set["horizon"]["start"],
            range_end=created_set["horizon"]["end"],
        )
        system_case = materialized["system_case"]
        self.assertEqual(system_case["case_name"], "legacy_case")
        self.assertEqual(len(system_case["time_series"]), 2)
        self.assertEqual(system_case["time_series"][0]["import_price_usd_per_mwh"], 55.0)
        self.assertEqual(system_case["time_series"][0]["load_demand_mw"]["load_1"], 10.0)

        # The draft document itself is never rewritten by extraction.
        draft_after = store.get_scenario_draft(scenario["id"])
        self.assertIn("time_series", draft_after["document"])

    def test_hydraulic_legacy_adapter_reads_coexist_with_new_generic_writes(self):
        store = AnalystStore("sqlite:///:memory:")
        self.addCleanup(store.close)
        client = TestClient(create_app(validation_service=StubValidationService(), store=store))
        project = client.post("/api/projects", json={"name": "TS5 acceptance hydro project"}).json()
        scenario = client.post(
            f"/api/projects/{project['id']}/scenarios", json={"name": "Hydraulic base case"}
        ).json()
        created = client.post(f"/api/scenarios/{scenario['id']}/hydraulic-diagram").json()["diagram"]

        save_response = client.put(
            f"/api/scenarios/{scenario['id']}/hydraulic-diagram",
            json={
                "revision": created["revision"],
                "nodes": [
                    _reservoir_node(
                        "reservoir_alpha", "Reservoir Alpha", 120.0, 80.0,
                        inflow=_inflow_series(5.0, 6.0),
                    ),
                    _reservoir_node("reservoir_beta", "Reservoir Beta", 320.0, 80.0),
                ],
            },
        )
        self.assertEqual(save_response.status_code, 200)
        diagram = save_response.json()["diagram"]
        alpha_node = next(node for node in diagram["nodes"] if node["technical_key"] == "reservoir_alpha")
        beta_node = next(node for node in diagram["nodes"] if node["technical_key"] == "reservoir_beta")
        self.assertEqual(alpha_node["natural_inflow_series"]["origin"], {"kind": "generic"})

        _seed_legacy_hydraulic_set(
            store,
            project_id=project["id"],
            case_id=diagram["optimization_case"]["id"],
            case_node_id=beta_node["entity_id"],
            values=[3.0, 4.0],
        )

        generic_list = client.get(f"/api/projects/{project['id']}/time-series-sets").json()["time_series_sets"]
        self.assertEqual(len(generic_list), 1)

        legacy_list = client.get(
            f"/api/projects/{project['id']}/time-series-sets/hydraulic"
        ).json()["hydraulic_time_series_sets"]
        self.assertEqual(len(legacy_list), 1)
        self.assertEqual(legacy_list[0]["origin"]["kind"], "hydraulic_legacy")
        self.assertEqual(legacy_list[0]["signal_key"], "natural_inflow_m3s")

        reloaded = client.get(f"/api/scenarios/{scenario['id']}/hydraulic-diagram").json()["diagram"]
        reloaded_alpha = next(node for node in reloaded["nodes"] if node["technical_key"] == "reservoir_alpha")
        reloaded_beta = next(node for node in reloaded["nodes"] if node["technical_key"] == "reservoir_beta")
        self.assertEqual(reloaded_alpha["natural_inflow_series"]["origin"], {"kind": "generic"})
        self.assertEqual(
            [p["value_m3s"] for p in reloaded_alpha["natural_inflow_series"]["points"]], [5.0, 6.0]
        )
        self.assertEqual(reloaded_beta["natural_inflow_series"]["origin"], {"kind": "hydraulic_legacy"})
        self.assertEqual(
            [p["value_m3s"] for p in reloaded_beta["natural_inflow_series"]["points"]], [3.0, 4.0]
        )

    def test_on_demand_hydraulic_migration_is_idempotent_and_preserves_audit_metadata(self):
        store = AnalystStore("sqlite:///:memory:")
        self.addCleanup(store.close)
        client = TestClient(create_app(validation_service=StubValidationService(), store=store))
        project = client.post("/api/projects", json={"name": "TS5 acceptance migration project"}).json()
        scenario = client.post(
            f"/api/projects/{project['id']}/scenarios", json={"name": "Hydraulic base case"}
        ).json()
        created = client.post(f"/api/scenarios/{scenario['id']}/hydraulic-diagram").json()["diagram"]
        save_response = client.put(
            f"/api/scenarios/{scenario['id']}/hydraulic-diagram",
            json={
                "revision": created["revision"],
                "nodes": [_reservoir_node("reservoir_alpha", "Reservoir Alpha", 120.0, 80.0)],
            },
        )
        diagram = save_response.json()["diagram"]
        node = diagram["nodes"][0]
        legacy_id = _seed_legacy_hydraulic_set(
            store,
            project_id=project["id"],
            case_id=diagram["optimization_case"]["id"],
            case_node_id=node["entity_id"],
            values=[5.0, 6.0],
        )

        migrate_url = f"/api/projects/{project['id']}/time-series-sets/hydraulic/{legacy_id}/migrate"
        first = client.post(migrate_url)
        self.assertEqual(first.status_code, 200)
        self.assertFalse(first.json()["already_migrated"])
        migrated_set = first.json()["time_series_set"]
        origin = migrated_set["revision_metadata"]["origin"]
        self.assertEqual(origin["kind"], "hydraulic_legacy_migration")
        self.assertEqual(origin["hydraulic_time_series_set_id"], legacy_id)

        second = client.post(migrate_url)
        self.assertTrue(second.json()["already_migrated"])
        self.assertEqual(second.json()["time_series_set"]["id"], migrated_set["id"])

        generic_list = client.get(f"/api/projects/{project['id']}/time-series-sets").json()["time_series_sets"]
        self.assertEqual(len(generic_list), 1)

        # Migration never rewrites the legacy row or its case binding: a
        # reload of the diagram still resolves the exact original values.
        reloaded = client.get(f"/api/scenarios/{scenario['id']}/hydraulic-diagram").json()["diagram"]
        legacy_series = reloaded["nodes"][0]["natural_inflow_series"]
        self.assertEqual(legacy_series["origin"], {"kind": "hydraulic_legacy"})
        self.assertEqual([p["value_m3s"] for p in legacy_series["points"]], [5.0, 6.0])

    def test_stale_validation_fails_closed_for_an_extracted_series_binding(self):
        store = AnalystStore("sqlite:///:memory:")
        self.addCleanup(store.close)
        project = store.create_project(name="TS5 acceptance stale extracted project")
        scenario = store.create_scenario(project_id=project["id"], name="TS5 stale scenario")
        store.create_or_replace_scenario_draft(
            scenario_id=scenario["id"], document=grid_battery_draft_document()
        )
        case = store.get_or_create_case_for_scenario(scenario["id"])
        variant = store.get_or_create_default_input_variant(case["id"])

        prepared_price = prepare_time_series_catalog_import(
            rows=price_rows(datetime(2026, 1, 1), 3), request=price_import_request()
        )
        price_set = store.import_time_series_catalog_set(
            scenario_id=scenario["id"],
            source={
                "id": "csv_source_price",
                "original_filename": "price.csv",
                "media_type": "text/csv",
                "checksum": "sha256:price",
            },
            prepared_import=prepared_price,
        )
        store.upsert_case_time_series_binding(
            case_input_variant_id=variant["id"],
            signal_key="import_price_usd_per_mwh",
            time_series_set_id=price_set["id"],
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            input_source_root = Path(temp_dir) / "input-sources"
            draft = store.get_scenario_draft(scenario["id"])
            source = ingest_csv_source(
                draft_document=draft["document"],
                original_filename="legacy_load.csv",
                content_type="text/csv",
                content=(
                    b"period_start,hours,load_1_demand\n"
                    b"2026-01-01T00:00:00,1.0,10.0\n"
                    b"2026-01-01T01:00:00,1.0,12.0\n"
                    b"2026-01-01T02:00:00,1.0,14.0\n"
                ),
                input_source_root=input_source_root,
            )
            updated_document = attach_time_series_source(draft["document"], source)
            store.update_scenario_draft(scenario_id=scenario["id"], document=updated_document)
            draft = store.get_scenario_draft(scenario["id"])
            mapped_document, mapped_source = apply_time_series_mapping(
                document=draft["document"],
                source_id=source["id"],
                mapping={
                    "timestamp": "period_start",
                    "duration_hours": "hours",
                    "load_demand_mw": {"load_1": "load_1_demand"},
                },
                input_source_root=input_source_root,
            )
            store.update_scenario_draft(scenario_id=scenario["id"], document=mapped_document)
            extracted_set = store.extract_draft_time_series_set(
                scenario_id=scenario["id"],
                source_id=mapped_source["id"],
                set_name="Legacy load series",
                version_label="v1",
                data_kind="real",
                timezone_name="America/Santiago",
            )

        store.upsert_case_time_series_binding(
            case_input_variant_id=variant["id"],
            signal_key="load_demand_mw",
            entity_type="component:load",
            entity_id="load_1",
            time_series_set_id=extracted_set["id"],
        )

        def materialize():
            return store.materialize_system_case_for_variant(
                scenario_id=scenario["id"],
                case_input_variant_id=variant["id"],
                range_start=price_set["horizon"]["start"],
                range_end=price_set["horizon"]["end"],
            )

        materialize()
        self.assertFalse(
            store.evaluate_case_input_variant_staleness(
                scenario_id=scenario["id"], case_input_variant_id=variant["id"]
            )["stale"]
        )

        store.edit_time_series_set_values(
            project_id=project["id"],
            time_series_set_id=extracted_set["id"],
            edits=[CatalogValueEdit(period_index=0, signal_key="load_demand_mw", value_text="999.0")],
        )

        staleness = store.evaluate_case_input_variant_staleness(
            scenario_id=scenario["id"], case_input_variant_id=variant["id"]
        )
        self.assertTrue(staleness["stale"])
        with self.assertRaises(VariantStaleError):
            materialize()

    def test_stale_validation_fails_closed_for_a_migrated_hydraulic_series_binding(self):
        store = AnalystStore("sqlite:///:memory:")
        self.addCleanup(store.close)
        client = TestClient(create_app(validation_service=StubValidationService(), store=store))
        project = client.post("/api/projects", json={"name": "TS5 acceptance stale migrated project"}).json()
        scenario = client.post(
            f"/api/projects/{project['id']}/scenarios", json={"name": "Hydraulic base case"}
        ).json()
        created = client.post(f"/api/scenarios/{scenario['id']}/hydraulic-diagram").json()["diagram"]
        save_response = client.put(
            f"/api/scenarios/{scenario['id']}/hydraulic-diagram",
            json={
                "revision": created["revision"],
                "nodes": [_reservoir_node("reservoir_alpha", "Reservoir Alpha", 120.0, 80.0)],
            },
        )
        diagram = save_response.json()["diagram"]
        node = diagram["nodes"][0]
        legacy_id = _seed_legacy_hydraulic_set(
            store,
            project_id=project["id"],
            case_id=diagram["optimization_case"]["id"],
            case_node_id=node["entity_id"],
            values=[5.0, 6.0, 7.0],
        )
        migration = store.migrate_hydraulic_time_series_set(
            project_id=project["id"], hydraulic_time_series_set_id=legacy_id, migrated_by="tester"
        )
        migrated_set = migration["time_series_set"]

        scenario_id = scenario["id"]
        case_id = diagram["optimization_case"]["id"]
        variant = store.get_or_create_default_input_variant(case_id)
        store.upsert_case_time_series_binding(
            case_input_variant_id=variant["id"],
            signal_key="natural_inflow_m3s",
            entity_type="hydraulic_node",
            entity_id="reservoir_alpha",
            time_series_set_id=migrated_set["id"],
        )

        def staleness():
            return store.evaluate_case_input_variant_staleness(
                scenario_id=scenario_id, case_input_variant_id=variant["id"]
            )

        def materialize():
            return store.materialize_system_case_for_variant(
                scenario_id=scenario_id,
                case_input_variant_id=variant["id"],
                range_start=migrated_set["horizon"]["start"],
                range_end=migrated_set["horizon"]["end"],
            )

        materialize()
        self.assertFalse(staleness()["stale"])

        store.edit_time_series_set_values(
            project_id=project["id"],
            time_series_set_id=migrated_set["id"],
            edits=[CatalogValueEdit(period_index=0, signal_key="natural_inflow_m3s", value_text="999.0")],
        )

        self.assertTrue(staleness()["stale"])
        with self.assertRaises(VariantStaleError):
            materialize()

        # Re-running the migration itself is a side path: it must not
        # silently clear (or otherwise disturb) the stale marker.
        second_migration = store.migrate_hydraulic_time_series_set(
            project_id=project["id"], hydraulic_time_series_set_id=legacy_id, migrated_by="tester"
        )
        self.assertTrue(second_migration["already_migrated"])
        self.assertTrue(staleness()["stale"])

    def test_permission_matrix_holds_across_catalog_hydraulic_and_case_surfaces(self):
        store = AnalystStore("sqlite:///:memory:")
        self.addCleanup(store.close)
        store.create_user(
            email="admin@example.local", display_name="Admin", role="admin",
            password_hash=hash_password("admin pass"), created_by="test",
        )
        store.create_user(
            email="analyst@example.local", display_name="Analyst", role="analyst",
            password_hash=hash_password("analyst pass"), created_by="test",
        )
        store.create_user(
            email="client@example.local", display_name="Client", role="external",
            password_hash=hash_password("client pass"), created_by="test",
        )

        def client_as(email, password):
            test_client = TestClient(create_app(store=store, auth_enabled=True))
            response = login_json_with_csrf(test_client, email, password)
            self.assertEqual(response.status_code, 200)
            return test_client

        admin = client_as("admin@example.local", "admin pass")
        project = post_json_with_csrf(admin, "/api/projects", {"name": "TS5 acceptance permissions"}).json()
        scenario = post_json_with_csrf(
            admin, f"/api/projects/{project['id']}/scenarios", {"name": "Base case"}
        ).json()
        diagram = post_json_with_csrf(admin, f"/api/scenarios/{scenario['id']}/hydraulic-diagram").json()["diagram"]
        save_response = put_json_with_csrf(
            admin,
            f"/api/scenarios/{scenario['id']}/hydraulic-diagram",
            {
                "revision": diagram["revision"],
                "nodes": [
                    _reservoir_node("reservoir_alpha", "Reservoir Alpha", 120.0, 80.0, inflow=_inflow_series(5.0, 6.0)),
                    _reservoir_node("reservoir_beta", "Reservoir Beta", 320.0, 80.0),
                ],
            },
        )
        self.assertEqual(save_response.status_code, 200)
        saved_diagram = save_response.json()["diagram"]
        beta_node = next(node for node in saved_diagram["nodes"] if node["technical_key"] == "reservoir_beta")
        _seed_legacy_hydraulic_set(
            store,
            project_id=project["id"],
            case_id=saved_diagram["optimization_case"]["id"],
            case_node_id=beta_node["entity_id"],
            values=[1.5],
        )

        analyst = client_as("analyst@example.local", "analyst pass")
        client_user = client_as("client@example.local", "client pass")

        routes = [
            f"/api/projects/{project['id']}/time-series-sets",
            f"/api/projects/{project['id']}/time-series-sets/hydraulic",
            f"/api/scenarios/{scenario['id']}/case/default-variant",
        ]
        for path in routes:
            with self.subTest(actor="client", path=path):
                self.assertEqual(client_user.get(path).status_code, 403)
            for actor_name, actor in [("analyst", analyst), ("admin", admin)]:
                with self.subTest(actor=actor_name, path=path):
                    self.assertEqual(actor.get(path).status_code, 200)

    def test_old_runs_stay_readable_while_cleanup_and_rebuild_manage_derived_indexes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_root = Path(temp_dir) / "artifacts"
            store = AnalystStore("sqlite:///:memory:")
            try:
                run = create_completed_run_with_result_artifacts(store, artifact_root)
                client = TestClient(create_app(store=store, artifact_root=artifact_root))

                # Old run, never indexed: still readable straight from artifacts.
                before_index = client.get(f"/api/runs/{run['id']}/results")
                self.assertEqual(before_index.status_code, 200)
                self.assertEqual(before_index.json()["results"]["summary"]["termination_status"], "OPTIMAL")

                rebuild_run_results(store=store, run=run, artifact_root=artifact_root)
                self.assertIsNotNone(store.get_run_dispatch_result_index(run["id"]))

                outcome = cleanup_run_result_data(
                    store=store,
                    run_id=run["id"],
                    targets=["dispatch_table", "asset_dispatch_table", "summary", "artifacts", "scenario_versions"],
                )
                self.assertEqual(outcome["removed"], ["dispatch_table", "asset_dispatch_table", "summary"])
                self.assertIn("immutable audit data", outcome["kept"]["artifacts"])
                self.assertIn("immutable audit data", outcome["kept"]["scenario_versions"])
                self.assertIsNone(store.get_run_dispatch_result_index(run["id"]))

                after_cleanup = client.get(f"/api/runs/{run['id']}/results")
                self.assertEqual(after_cleanup.status_code, 200)
                self.assertEqual(after_cleanup.json()["results"]["summary"]["termination_status"], "OPTIMAL")
                self.assertEqual(len(store.list_run_artifacts(run["id"])), 3)
                self.assertEqual(
                    store.get_scenario_version(run["scenario_version_id"])["id"], run["scenario_version_id"]
                )

                # Cleanup is idempotent, and the removed indexes are provably
                # restorable through the existing TS-4 rebuild path.
                second_cleanup = cleanup_run_result_data(store=store, run_id=run["id"])
                self.assertEqual(second_cleanup["removed"], [])

                rebuild = rebuild_run_results(store=store, run=run, artifact_root=artifact_root)
                self.assertEqual(rebuild["status"], "indexed")
                self.assertIsNotNone(store.get_run_dispatch_result_index(run["id"]))
            finally:
                store.close()

    def test_historical_scenario_version_is_immutable_at_db_level(self):
        store = AnalystStore("sqlite:///:memory:")
        self.addCleanup(store.close)
        scenario_version = create_persisted_scenario_version(store)
        before = store.get_scenario_version(scenario_version["id"], include_document=True)

        with self.assertRaises(sqlite3.DatabaseError) as raised:
            store.connection.execute(
                "UPDATE scenario_versions SET system_case_json = '{}' WHERE id = ?",
                (scenario_version["id"],),
            )
        self.assertIn("immutable", str(raised.exception).lower())

        after = store.get_scenario_version(scenario_version["id"], include_document=True)
        self.assertEqual(after["system_case_json"], before["system_case_json"])

    def test_ts5_documentation_tracker_and_issues_are_done(self):
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        issue = (
            REPO_ROOT
            / "docs"
            / "series_tiempo"
            / "iter5"
            / "issues"
            / "BESS-TS5-011-finalize-ts5-acceptance-suite-and-docs.md"
        ).read_text(encoding="utf-8")
        tracker = (
            REPO_ROOT / "docs" / "series_tiempo" / "iter5" / "issues" / "tracker_ts5.md"
        ).read_text(encoding="utf-8")
        manual = (
            REPO_ROOT / "docs" / "series_tiempo" / "iter5" / "pruebas_manuales_ts5.md"
        ).read_text(encoding="utf-8")
        architecture = (
            REPO_ROOT / "docs" / "series_tiempo" / "iter5" / "architecture_ts5_final.md"
        ).read_text(encoding="utf-8")

        self.assertIn("TS-5: Migration, Unification And Hardening", readme)
        self.assertIn("tests.test_ts5_acceptance", readme)

        self.assertIn("Status: Done", issue)
        self.assertNotIn("- [ ]", issue)
        self.assertIn("tests.test_ts5_acceptance", issue)

        self.assertIn(
            "| BESS-TS5-011 | Finalize TS-5 Acceptance Suite And Docs | AFK | ready-for-agent | Done |",
            tracker,
        )
        self.assertIn("BESS-TS5-011 | Todo -> Done", tracker)
        self.assertNotIn("| Todo |", tracker)
        self.assertNotIn("| In Review |", tracker)
        self.assertIn("tests.test_ts5_acceptance", tracker)

        self.assertIn("Cierre TS-5", manual)
        self.assertIn("tests.test_ts5_acceptance", manual)

        self.assertIn("Scenario -> OptimizationCase", architecture)
        self.assertIn("hydraulic_legacy_migration", architecture)


if __name__ == "__main__":
    unittest.main()
