"""TS7-017 C4 association and binding migration.

The seam under test is the store's public migration and canonical read surface.
Persisted migration evidence is asserted only where the C4 contract exposes it.
"""

import os
import tempfile
import unittest
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from app.persistence import AnalystStore
from app.time_series_bindings import BindingMutationError
from app.time_series_catalog import (
    CatalogImportRequest,
    CatalogSignalMappingRequest,
    prepare_time_series_catalog_import,
)
from app.time_series_migration import MigrationPhaseStopped


POSTGRES_TEST_DATABASE_URL = os.environ.get("POSTGRES_TEST_DATABASE_URL")


def import_legacy_price_set(store, scenario_id):
    start = datetime(2026, 1, 1)
    prepared = prepare_time_series_catalog_import(
        rows=[
            {
                "period_start": (start + timedelta(hours=offset)).isoformat(),
                "hours": "1.0",
                "value": str(70.0 + offset),
            }
            for offset in range(2)
        ],
        request=CatalogImportRequest(
            set_name="Precio importacion",
            version_label="v1",
            data_kind="real",
            timezone="UTC",
            timestamp_column="period_start",
            duration_hours_column="hours",
            signal_mappings=[
                CatalogSignalMappingRequest(
                    source_column="value",
                    signal_key="import_price_usd_per_mwh",
                )
            ],
        ),
    )
    return store.import_time_series_catalog_set(
        scenario_id=scenario_id,
        source={
            "id": "ts7-017-price",
            "original_filename": "price.csv",
            "media_type": "text/csv",
            "checksum": "sha256:ts7-017-price",
        },
        prepared_import=prepared,
        created_by="legacy_analyst",
    )


def import_legacy_load_set(store, scenario_id):
    start = datetime(2026, 1, 1)
    prepared = prepare_time_series_catalog_import(
        rows=[
            {
                "period_start": (start + timedelta(hours=offset)).isoformat(),
                "hours": "1.0",
                "value": str(10.0 + offset),
            }
            for offset in range(2)
        ],
        request=CatalogImportRequest(
            set_name="Demanda",
            version_label="v1",
            data_kind="real",
            timezone="UTC",
            timestamp_column="period_start",
            duration_hours_column="hours",
            signal_mappings=[
                CatalogSignalMappingRequest(
                    source_column="value", signal_key="load_demand_mw"
                )
            ],
        ),
    )
    return store.import_time_series_catalog_set(
        scenario_id=scenario_id,
        source={
            "id": "ts7-017-load",
            "original_filename": "load.csv",
            "media_type": "text/csv",
            "checksum": "sha256:ts7-017-load",
        },
        prepared_import=prepared,
        created_by="legacy_analyst",
    )


def import_legacy_symmetric_price_set(store, scenario_id):
    prepared = prepare_time_series_catalog_import(
        rows=[
            {"period_start": "2026-01-01T00:00:00", "hours": "1", "value": "70"}
        ],
        request=CatalogImportRequest(
            set_name="Precio simetrico",
            version_label="v1",
            data_kind="real",
            timezone="UTC",
            timestamp_column="period_start",
            duration_hours_column="hours",
            signal_mappings=[
                CatalogSignalMappingRequest(
                    source_column="value", signal_key="price_usd_per_mwh"
                )
            ],
        ),
    )
    return store.import_time_series_catalog_set(
        scenario_id=scenario_id,
        source={
            "id": "ts7-017-symmetric-price",
            "original_filename": "symmetric-price.csv",
            "media_type": "text/csv",
            "checksum": "sha256:ts7-017-symmetric-price",
        },
        prepared_import=prepared,
        created_by="legacy_analyst",
    )


def system_case_with_load(component_key):
    return {
        "schema_version": "bess_system_dispatch.v2",
        "case_name": "caso",
        "nodes": [
            {"id": "bus_1", "type": "bus"},
            {"id": "grid_1", "type": "grid"},
            {"id": component_key, "type": "load"},
        ],
        "edges": [],
        "time_series": {"periods": []},
        "constraints": {},
        "solver": {"name": "HiGHS", "options": {}},
    }


class C4AssociationAndBindingBackfillTests(unittest.TestCase):
    def setUp(self):
        self.store = AnalystStore("sqlite:///:memory:")
        self.project = self.store.create_project(name="Cuenca Norte")
        self.scenario = self.store.create_scenario(
            project_id=self.project["id"], name="Base"
        )
        self.case = self.store.get_or_create_case_for_scenario(self.scenario["id"])
        self.variant = self.store.get_or_create_default_input_variant(self.case["id"])
        self.legacy_set = import_legacy_price_set(self.store, self.scenario["id"])
        self.legacy_binding = self.store.upsert_case_time_series_binding(
            case_input_variant_id=self.variant["id"],
            signal_key="import_price_usd_per_mwh",
            time_series_set_id=self.legacy_set["id"],
            created_by="legacy_analyst",
        )
        self.recovery = tempfile.TemporaryDirectory()
        self.store.take_c0_recovery_point(
            actor="internal_admin", copy_directory=Path(self.recovery.name)
        )
        self.store.backfill_time_series_c2(actor="internal_admin")
        self.store.backfill_time_series_c3(actor="internal_admin")

    def test_an_ambiguous_object_records_evidence_and_leaves_the_variant_closed(self):
        store = AnalystStore("sqlite:///:memory:")
        recovery = tempfile.TemporaryDirectory()
        self.addCleanup(store.close)
        self.addCleanup(recovery.cleanup)
        project = store.create_project(name="Ambiguous")
        scenario = store.create_scenario(project_id=project["id"], name="Base")
        case = store.get_or_create_case_for_scenario(scenario["id"])
        variant = store.get_or_create_default_input_variant(case["id"])
        store.create_scenario_version(
            scenario_id=scenario["id"],
            system_case_json=system_case_with_load("system"),
            validation_payload={"ok": True},
        )
        legacy_set = import_legacy_load_set(store, scenario["id"])
        legacy_binding = store.upsert_case_time_series_binding(
            case_input_variant_id=variant["id"],
            signal_key="load_demand_mw",
            entity_id="system",
            time_series_set_id=legacy_set["id"],
            created_by="legacy_analyst",
        )
        store.take_c0_recovery_point(
            actor="internal_admin", copy_directory=Path(recovery.name)
        )
        store.backfill_time_series_c2(actor="internal_admin")
        store.backfill_time_series_c3(actor="internal_admin")

        with self.assertRaises(MigrationPhaseStopped) as stopped:
            store.backfill_time_series_c4(actor="internal_admin")

        anomalies = store.read_migration_anomalies(
            stopped.exception.migration_run_id
        )
        canonical = store.read_case_bindings(
            scenario_id=scenario["id"], variant_id=variant["id"]
        )
        with self.assertRaises(BindingMutationError) as blocked:
            store.assert_case_bindings_executable(
                scenario_id=scenario["id"], variant_id=variant["id"]
            )

        self.assertEqual(stopped.exception.code, "TS_MIGRATION_C4_STOPPED")
        self.assertEqual(len(anomalies), 1)
        self.assertEqual(anomalies[0]["code"], "TS_MIGRATION_OBJECT_AMBIGUOUS")
        self.assertEqual(anomalies[0]["severity"], "blocking")
        self.assertEqual(anomalies[0]["resolution"], "open")
        self.assertEqual(
            anomalies[0]["actor"],
            f"system:migration:{stopped.exception.migration_run_id}",
        )
        self.assertEqual(anomalies[0]["evidence"]["binding_id"], legacy_binding["id"])
        self.assertEqual(anomalies[0]["evidence"]["variant_id"], variant["id"])
        self.assertEqual(canonical["summary"], {"total_count": 0})
        self.assertEqual(blocked.exception.code, "TS_BINDING_EXECUTION_BLOCKED")
        self.assertEqual(
            blocked.exception.context["details"][0]["anomaly_code"],
            "TS_MIGRATION_OBJECT_AMBIGUOUS",
        )
    def tearDown(self):
        self.store.close()
        self.recovery.cleanup()

    def test_c4_reauthorizes_exact_links_and_repeats_as_a_noop(self):
        first = self.store.backfill_time_series_c4(actor="internal_admin")
        repeated = self.store.backfill_time_series_c4(actor="internal_admin")

        binding = self.store.read_case_binding(
            scenario_id=self.scenario["id"],
            variant_id=self.variant["id"],
            binding_id=self.legacy_binding["id"],
        )
        association = self.store.read_catalog_association(
            binding["catalog_association_id"]
        )
        canonical_set = self.store.read_canonical_set(self.legacy_set["id"])

        self.assertEqual(
            {
                "statuses": [first["status"], repeated["status"]],
                "same_manifest": first["manifest"] == repeated["manifest"],
                "repeat_created_rows": repeated["created_rows"],
                "repeat_mapping_changes": repeated["mapping_changes"],
                "binding_id": binding["binding_id"],
                "binding_state": binding["state"],
                "binding_role": binding["binding_role"]["key"],
                "binding_actor": binding["created_by"],
                "revision_id": binding["set_revision_id"],
                "association_state": association["state"],
                "association_object": association["object"]["object_type_key"],
            },
            {
                "statuses": ["proven", "proven"],
                "same_manifest": True,
                "repeat_created_rows": 0,
                "repeat_mapping_changes": 0,
                "binding_id": self.legacy_binding["id"],
                "binding_state": "valid_current",
                "binding_role": "grid_import_price",
                "binding_actor": "legacy_analyst",
                "revision_id": canonical_set["current_revision_id"],
                "association_state": "active_valid",
                "association_object": "global:system",
            },
        )

    def test_a_symmetric_legacy_price_expands_to_both_canonical_roles(self):
        store = AnalystStore("sqlite:///:memory:")
        recovery = tempfile.TemporaryDirectory()
        self.addCleanup(store.close)
        self.addCleanup(recovery.cleanup)
        project = store.create_project(name="Retirement")
        scenario = store.create_scenario(project_id=project["id"], name="Base")
        case = store.get_or_create_case_for_scenario(scenario["id"])
        variant = store.get_or_create_default_input_variant(case["id"])
        legacy_set = import_legacy_symmetric_price_set(store, scenario["id"])
        legacy_binding = store.upsert_case_time_series_binding(
            case_input_variant_id=variant["id"],
            signal_key="price_usd_per_mwh",
            time_series_set_id=legacy_set["id"],
            created_by="legacy_analyst",
        )
        store.take_c0_recovery_point(
            actor="internal_admin", copy_directory=Path(recovery.name)
        )
        store.backfill_time_series_c2(actor="internal_admin")
        store.backfill_time_series_c3(actor="internal_admin")

        completed = store.backfill_time_series_c4(actor="internal_admin")
        repeated = store.backfill_time_series_c4(actor="internal_admin")
        bindings = store.read_case_bindings(
            scenario_id=scenario["id"], variant_id=variant["id"]
        )["items"]
        associations = store.read_catalog_associations()["items"]

        self.assertEqual(completed["status"], "proven")
        self.assertEqual(completed["manifest"]["revalidated_bindings"], 1)
        self.assertEqual(completed["manifest"]["retired_bindings"], 0)
        self.assertEqual(len(bindings), 2)
        self.assertEqual(
            {binding["binding_role"]["key"] for binding in bindings},
            {"grid_import_price", "grid_export_price"},
        )
        self.assertEqual({binding["signal_id"] for binding in bindings}, {legacy_set["id"]})
        self.assertIn(legacy_binding["id"], {binding["binding_id"] for binding in bindings})
        self.assertEqual(len(associations), 2)
        self.assertEqual(
            {association["binding_role"]["key"] for association in associations},
            {"grid_import_price", "grid_export_price"},
        )
        self.assertEqual(repeated["created_rows"], 0)
        self.assertEqual(repeated["mapping_changes"], 0)
        self.assertEqual(repeated["manifest"], completed["manifest"])

    def test_an_unresolvable_binding_can_only_close_by_an_audited_retirement(self):
        store = AnalystStore("sqlite:///:memory:")
        recovery = tempfile.TemporaryDirectory()
        self.addCleanup(store.close)
        self.addCleanup(recovery.cleanup)
        project = store.create_project(name="Retirement")
        scenario = store.create_scenario(project_id=project["id"], name="Base")
        case = store.get_or_create_case_for_scenario(scenario["id"])
        variant = store.get_or_create_default_input_variant(case["id"])
        legacy_set = import_legacy_load_set(store, scenario["id"])
        legacy_binding = store.upsert_case_time_series_binding(
            case_input_variant_id=variant["id"],
            signal_key="load_demand_mw",
            entity_type="component:load",
            entity_id="retired_load",
            time_series_set_id=legacy_set["id"],
            created_by="legacy_analyst",
        )
        store.take_c0_recovery_point(
            actor="internal_admin", copy_directory=Path(recovery.name)
        )
        store.backfill_time_series_c2(actor="internal_admin")
        store.backfill_time_series_c3(actor="internal_admin")
        with self.assertRaises(MigrationPhaseStopped) as stopped:
            store.backfill_time_series_c4(actor="internal_admin")
        anomaly = store.read_migration_anomalies(stopped.exception.migration_run_id)[0]

        retired = store.retire_time_series_migration_binding(
            anomaly_id=anomaly["id"],
            actor="migration_admin@example.local",
            reason="The removed legacy load no longer exists in the case.",
        )
        completed = store.backfill_time_series_c4(actor="internal_admin")
        repeated = store.backfill_time_series_c4(actor="internal_admin")
        gate = store.read_time_series_c4_cutover_gate()
        history = store.read_time_series_migration_binding_history(
            legacy_binding["id"]
        )

        self.assertEqual(retired["status"], "retired")
        self.assertEqual(retired["binding_id"], legacy_binding["id"])
        self.assertEqual(retired["retired_by"], "migration_admin@example.local")
        self.assertEqual(
            retired["reason"],
            "The removed legacy load no longer exists in the case.",
        )
        self.assertEqual(history, retired)
        self.assertEqual(completed["status"], "proven")
        self.assertEqual(completed["manifest"]["retired_bindings"], 1)
        self.assertEqual(completed["manifest"]["revalidated_bindings"], 0)
        self.assertTrue(completed["manifest"]["cutover_ready"])
        self.assertEqual(repeated["created_rows"], 0)
        self.assertEqual(repeated["mapping_changes"], 0)
        self.assertEqual(repeated["manifest"], completed["manifest"])
        self.assertEqual(
            gate,
            {
                "active_bindings": 1,
                "revalidated_bindings": 0,
                "retired_bindings": 1,
                "unaccounted_binding_ids": [],
                "open_blocking_anomalies": 0,
                "cutover_ready": True,
            },
        )

    def test_an_explained_c0_cross_project_reference_is_still_refused_by_c4(self):
        store = AnalystStore("sqlite:///:memory:")
        recovery = tempfile.TemporaryDirectory()
        self.addCleanup(store.close)
        self.addCleanup(recovery.cleanup)
        target_project = store.create_project(name="Target")
        target_scenario = store.create_scenario(
            project_id=target_project["id"], name="Target scenario"
        )
        case = store.get_or_create_case_for_scenario(target_scenario["id"])
        variant = store.get_or_create_default_input_variant(case["id"])
        source_project = store.create_project(name="Source")
        source_scenario = store.create_scenario(
            project_id=source_project["id"], name="Source scenario"
        )
        foreign_set = import_legacy_price_set(store, source_scenario["id"])
        legacy_binding = store.upsert_case_time_series_binding(
            case_input_variant_id=variant["id"],
            signal_key="import_price_usd_per_mwh",
            time_series_set_id=foreign_set["id"],
            created_by="legacy_analyst",
        )
        store.take_c0_recovery_point(
            actor="internal_admin",
            copy_directory=Path(recovery.name),
            explanations={
                f"binding_project_mismatch:binding={legacy_binding['id']}": (
                    "Known legacy defect; C4 must reauthorize it."
                )
            },
        )
        store.backfill_time_series_c2(actor="internal_admin")
        store.backfill_time_series_c3(actor="internal_admin")

        with self.assertRaises(MigrationPhaseStopped) as stopped:
            store.backfill_time_series_c4(actor="internal_admin")

        anomaly = store.read_migration_anomalies(
            stopped.exception.migration_run_id
        )[0]
        self.assertEqual(anomaly["code"], "TS_MIGRATION_PROJECT_MISMATCH")
        self.assertEqual(anomaly["severity"], "blocking")
        self.assertEqual(anomaly["evidence"]["binding_id"], legacy_binding["id"])
        self.assertIn(
            "TS_COMPAT_SCOPE_NOT_ACCESSIBLE",
            [item["code"] for item in anomaly["evidence"]["errors"]],
        )
        self.assertEqual(
            store.read_case_bindings(
                scenario_id=target_scenario["id"], variant_id=variant["id"]
            )["summary"],
            {"total_count": 0},
        )

    def test_c4_materializes_an_eligible_unbound_signal_association(self):
        store = AnalystStore("sqlite:///:memory:")
        recovery = tempfile.TemporaryDirectory()
        self.addCleanup(store.close)
        self.addCleanup(recovery.cleanup)
        project = store.create_project(name="Unbound")
        scenario = store.create_scenario(project_id=project["id"], name="Base")
        legacy_set = import_legacy_price_set(store, scenario["id"])
        store.take_c0_recovery_point(
            actor="internal_admin", copy_directory=Path(recovery.name)
        )
        store.backfill_time_series_c2(actor="internal_admin")
        store.backfill_time_series_c3(actor="internal_admin")

        completed = store.backfill_time_series_c4(actor="internal_admin")

        associations = store.read_catalog_associations()
        self.assertEqual(completed["status"], "proven")
        self.assertEqual(associations["summary"], {"total_count": 1})
        association = associations["items"][0]
        self.assertEqual(association["state"], "active_valid")
        self.assertEqual(association["signal"]["series_key"], "import_price_usd_per_mwh")
        self.assertEqual(association["binding_role"]["key"], "grid_import_price")
        self.assertEqual(association["object"]["object_type_key"], "global:system")
        self.assertEqual(
            association["created_by"],
            f"system:migration:{completed['migration_run_id']}",
        )


@unittest.skipUnless(
    POSTGRES_TEST_DATABASE_URL,
    "POSTGRES_TEST_DATABASE_URL is required for PostgreSQL integration tests",
)
class PostgresC4AssociationAndBindingBackfillTests(unittest.TestCase):
    def setUp(self):
        self.store = AnalystStore(POSTGRES_TEST_DATABASE_URL)
        self.rollback = self.store.connection._connection.transaction(  # noqa: SLF001
            force_rollback=True
        )
        self.rollback.__enter__()
        suffix = uuid.uuid4().hex[:12]
        self.project = self.store.create_project(name=f"TS7-017 {suffix}")
        self.scenario = self.store.create_scenario(
            project_id=self.project["id"], name=f"Base {suffix}"
        )
        case = self.store.get_or_create_case_for_scenario(self.scenario["id"])
        self.variant = self.store.get_or_create_default_input_variant(case["id"])
        legacy_set = import_legacy_price_set(self.store, self.scenario["id"])
        self.legacy_binding = self.store.upsert_case_time_series_binding(
            case_input_variant_id=self.variant["id"],
            signal_key="import_price_usd_per_mwh",
            time_series_set_id=legacy_set["id"],
            created_by="legacy_analyst",
        )
        self.recovery = tempfile.TemporaryDirectory()

    def tearDown(self):
        try:
            self.recovery.cleanup()
            self.rollback.__exit__(None, None, None)
        finally:
            self.store.close()

    def prove_recovery_point(self):
        directory = Path(self.recovery.name)
        try:
            return self.store.take_c0_recovery_point(
                actor="internal_admin", copy_directory=directory
            )
        except MigrationPhaseStopped as stopped:
            explanations = {
                finding["finding_key"]: "pre-existing development row"
                for finding in stopped.findings
            }
        return self.store.take_c0_recovery_point(
            actor="internal_admin",
            copy_directory=directory,
            explanations=explanations,
        )

    def test_postgresql_preserves_and_revalidates_the_exact_binding(self):
        self.prove_recovery_point()
        self.store.backfill_time_series_c2(actor="internal_admin")
        self.store.backfill_time_series_c3(actor="internal_admin")
        try:
            self.store.backfill_time_series_c4(actor="internal_admin")
        except MigrationPhaseStopped:
            # The shared development fixture may contain unrelated defects;
            # C4 commits each resolved root independently and reports all of
            # the others instead of hiding them.
            pass

        binding = self.store.read_case_binding(
            scenario_id=self.scenario["id"],
            variant_id=self.variant["id"],
            binding_id=self.legacy_binding["id"],
        )
        association = self.store.read_catalog_association(
            binding["catalog_association_id"]
        )
        self.assertEqual(binding["binding_id"], self.legacy_binding["id"])
        self.assertEqual(binding["state"], "valid_current")
        self.assertEqual(binding["binding_role"]["key"], "grid_import_price")
        self.assertEqual(association["state"], "active_valid")
        self.assertEqual(association["object"]["object_type_key"], "global:system")


if __name__ == "__main__":
    unittest.main()
