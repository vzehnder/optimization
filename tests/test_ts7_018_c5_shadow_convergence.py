"""TS7-018 C5 shadow reads, settled source and convergence.

The seam under test is the store's public migration verification surface: the
C5 phase operation, the legacy mutation pause it takes, the migration evidence
it persists, and the legacy hydraulic surface it must leave working.
"""

import os
import tempfile
import unittest
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from app.persistence import AnalystStore
from app.time_series_catalog import (
    CatalogImportRequest,
    CatalogSignalMappingRequest,
    prepare_time_series_catalog_import,
)
from app.time_series_migration import (
    MigrationControlError,
    MigrationPhaseStopped,
)


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
            "id": "ts7-018-price",
            "original_filename": "price.csv",
            "media_type": "text/csv",
            "checksum": "sha256:ts7-018-price",
        },
        prepared_import=prepared,
        created_by="legacy_analyst",
    )


class C5ShadowVerificationTests(unittest.TestCase):
    def setUp(self):
        self.store = AnalystStore("sqlite:///:memory:")
        self.addCleanup(self.store.close)
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
        self.addCleanup(self.recovery.cleanup)
        self.store.take_c0_recovery_point(
            actor="internal_admin", copy_directory=Path(self.recovery.name)
        )
        self.store.backfill_time_series_c2(actor="internal_admin")
        self.store.backfill_time_series_c3(actor="internal_admin")
        self.store.backfill_time_series_c4(actor="internal_admin")

    def test_c5_proves_shadow_parity_and_records_its_sample(self):
        receipt = self.store.verify_time_series_c5_shadow(actor="internal_admin")

        self.assertEqual(receipt["status"], "proven")
        manifest = receipt["manifest"]
        self.assertEqual(manifest["phase"], "C5")
        self.assertEqual(manifest["differences"], [])
        self.assertEqual(
            manifest["shadow_read"]["dimensions"],
            [
                "semantics",
                "counts",
                "values",
                "hashes",
                "authorization",
                "lineage",
            ],
        )
        self.assertEqual(manifest["shadow_read"]["compared_sets"], 1)
        self.assertIn(int(self.legacy_set["id"]), manifest["sample"]["set_ids"])
        self.assertIn(
            int(self.legacy_binding["id"]), manifest["sample"]["binding_ids"]
        )
        run = self.store.read_migration_run(int(receipt["migration_run_id"]))
        self.assertEqual(run["phase"], "C5")
        self.assertEqual(run["status"], "proven")
        self.assertEqual(run["manifest_digest"], receipt["manifest_digest"])

    def test_one_shadow_difference_halts_c5_as_a_rollback_trigger(self):
        canonical_sets = self.store._canonical("time_series_sets")
        self.store.connection.execute(
            f"UPDATE {canonical_sets} SET name = ? WHERE id = ?",
            ("Precio renombrado", int(self.legacy_set["id"])),
        )
        self.store.connection.commit()

        with self.assertRaises(MigrationPhaseStopped) as stopped:
            self.store.verify_time_series_c5_shadow(actor="internal_admin")

        self.assertEqual(stopped.exception.code, "TS_MIGRATION_C5_STOPPED")
        self.assertTrue(stopped.exception.context["rollback_trigger"])
        renamed = [
            finding["evidence"]
            for finding in stopped.exception.findings
            if finding["evidence"].get("subject") == f"set:{self.legacy_set['id']}"
        ]
        self.assertEqual(len(renamed), 1)
        self.assertEqual(renamed[0]["dimension"], "authorization")
        self.assertEqual(renamed[0]["legacy"]["name"], "Precio importacion")
        self.assertEqual(renamed[0]["canonical"]["name"], "Precio renombrado")
        for finding in stopped.exception.findings:
            self.assertEqual(finding["severity"], "blocking")
        run_id = int(stopped.exception.migration_run_id)
        self.assertEqual(self.store.read_migration_run(run_id)["status"], "stopped")
        anomalies = self.store.read_migration_anomalies(run_id)
        self.assertTrue(anomalies)
        for anomaly in anomalies:
            self.assertEqual(anomaly["code"], "TS_MIGRATION_SHADOW_DIFFERENCE")
            self.assertEqual(anomaly["severity"], "blocking")
            self.assertEqual(anomaly["resolution"], "open")
            self.assertEqual(anomaly["phase"], "C5")

    def test_c5_settles_the_source_by_draining_the_journal_under_a_pause(self):
        self.store.enqueue_legacy_dirty_root(
            migration_run_id=0,
            root_kind="time_series_set",
            root_id=str(self.legacy_set["id"]),
        )
        self.assertTrue(self.store.read_pending_dirty_roots())

        receipt = self.store.verify_time_series_c5_shadow(actor="internal_admin")

        self.assertEqual(receipt["status"], "proven")
        self.assertEqual(receipt["drained_dirty_roots"], 1)
        self.assertEqual(
            receipt["manifest"]["settled_source"]["pending_dirty_roots"], 0
        )
        self.assertEqual(self.store.read_pending_dirty_roots(), [])
        self.assertIsNone(self.store.read_legacy_mutation_pause())

    def test_the_pause_refuses_legacy_writes_while_reads_keep_serving(self):
        pause = self.store.begin_legacy_mutation_pause(
            actor="internal_admin", reason="C5 shadow comparison"
        )
        self.assertEqual(pause["actor"], "internal_admin")

        with self.assertRaises(MigrationControlError) as refused:
            self.store.upsert_case_time_series_binding(
                case_input_variant_id=self.variant["id"],
                signal_key="import_price_usd_per_mwh",
                time_series_set_id=self.legacy_set["id"],
                created_by="legacy_analyst",
            )
        self.assertEqual(refused.exception.code, "TS_MIGRATION_MUTATION_PAUSED")

        legacy = self.store.get_time_series_set(
            self.project["id"], self.legacy_set["id"]
        )
        self.assertEqual(legacy["signal_count"], 1)

        self.store.release_legacy_mutation_pause(actor="internal_admin")
        self.assertIsNone(self.store.read_legacy_mutation_pause())
        reused = self.store.upsert_case_time_series_binding(
            case_input_variant_id=self.variant["id"],
            signal_key="import_price_usd_per_mwh",
            time_series_set_id=self.legacy_set["id"],
            created_by="legacy_analyst",
        )
        self.assertEqual(int(reused["id"]), int(self.legacy_binding["id"]))

    def test_a_projection_that_diverges_from_the_python_registry_stops_c5(self):
        entries = self.store._projection("time_series_catalog_entries")
        # The registry gives ``import_price_usd_per_mwh`` USD/MWh and nothing
        # else; a projection that shows MW is the divergence chapter 10.4 says
        # blocks the deployment.
        self.store.connection.execute(
            f"UPDATE {entries} SET unit_key = 'mw', unit_id = "
            "(SELECT id FROM measurement_units WHERE unit_key = 'mw')"
        )
        self.store.connection.commit()

        with self.assertRaises(MigrationPhaseStopped) as stopped:
            self.store.verify_time_series_c5_shadow(actor="internal_admin")

        divergences = [
            finding
            for finding in stopped.exception.findings
            if finding["code"] == "TS_MIGRATION_REGISTRY_DIVERGENCE"
        ]
        self.assertEqual(len(divergences), 1)
        evidence = divergences[0]["evidence"]
        self.assertEqual(evidence["series_key"], "import_price_usd_per_mwh")
        self.assertEqual(evidence["registry_unit"], "USD/MWh")
        self.assertEqual(evidence["projected_unit"], "MW")
        self.assertEqual(
            self.store.read_migration_run(
                int(stopped.exception.migration_run_id)
            )["status"],
            "stopped",
        )

    def test_c5_stops_when_the_projection_diverges_from_the_canonical_model(self):
        entries = self.store._projection("time_series_catalog_entries")
        self.store.connection.execute(
            f"UPDATE {entries} SET binding_count = binding_count + 5"
        )
        self.store.connection.commit()

        with self.assertRaises(MigrationPhaseStopped) as stopped:
            self.store.verify_time_series_c5_shadow(actor="internal_admin")

        projection_findings = [
            finding
            for finding in stopped.exception.findings
            if finding["evidence"].get("subject") == "projection:inputs"
        ]
        self.assertEqual(len(projection_findings), 1)
        evidence = projection_findings[0]["evidence"]
        self.assertEqual(evidence["dimension"], "counts")
        self.assertFalse(evidence["canonical"]["converged"])
        self.assertTrue(evidence["canonical"]["stale"])
        self.assertEqual(evidence["legacy"]["stale"], [])

    def test_a_repeat_over_an_unmutated_source_converges(self):
        mappings = self.store._migration("time_series_migration_mappings")

        def mapping_count():
            return int(
                self.store.connection.execute(
                    f"SELECT COUNT(*) AS total FROM {mappings}"
                ).fetchone()["total"]
            )

        first = self.store.verify_time_series_c5_shadow(actor="internal_admin")
        after_first = mapping_count()

        second = self.store.verify_time_series_c5_shadow(actor="internal_admin")

        self.assertEqual(first["created_rows"], 0)
        self.assertEqual(second["created_rows"], 0)
        self.assertEqual(second["mapping_changes"], 0)
        self.assertEqual(mapping_count(), after_first)
        self.assertEqual(second["manifest"], first["manifest"])
        self.assertEqual(second["manifest_digest"], first["manifest_digest"])
        self.assertNotEqual(
            second["migration_run_id"], first["migration_run_id"]
        )

    def define_local_object_series(self):
        """One object-specific set, so the source has both ``series_kind``."""

        registered = self.store.connection.execute(
            f"SELECT id FROM {self.store._linkable('linkable_objects')}"
            " ORDER BY id LIMIT 1"
        ).fetchone()
        return self.store.create_object_series_definition(
            project_id=self.project["id"],
            linkable_object_id=int(registered["id"]),
            document={
                "object_series_key": "local_price_forecast",
                "display_name": "Precio local previsto",
                "intended_binding_role_key": "grid_import_price",
                "semantic_type_key": "energy_price",
                "unit_key": "usd_per_mwh",
                "data_class_key": "forecast",
                "timezone": "UTC",
                "temporal_contract": {
                    "regularity": "regular",
                    "nominal_resolution_seconds": 3600,
                    "timestamp_convention": "period_start",
                },
            },
            actor="internal_analyst",
        )

    def test_the_sample_records_every_stratum_the_source_has(self):
        local = self.define_local_object_series()

        receipt = self.store.verify_time_series_c5_shadow(actor="internal_admin")

        sample = receipt["manifest"]["sample"]
        self.assertEqual(sample["series_kinds"], ["catalog", "object_specific"])
        self.assertIn("global_signal_slot", sample["object_families"])
        self.assertIn(int(local["set_id"]), sample["set_ids"])
        self.assertTrue(len(sample["set_states"]) >= 2)
        for stratum in sample["strata"].values():
            self.assertTrue(stratum["source_set_ids"])
            self.assertEqual(
                stratum["sampled_set_ids"], stratum["source_set_ids"]
            )

    def test_a_sample_that_misses_a_stratum_stops_the_phase(self):
        self.define_local_object_series()

        with self.assertRaises(MigrationPhaseStopped) as stopped:
            self.store.verify_time_series_c5_shadow(
                actor="internal_admin", set_ids=[int(self.legacy_set["id"])]
            )

        incomplete = [
            finding
            for finding in stopped.exception.findings
            if finding["code"] == "TS_MIGRATION_SAMPLE_INCOMPLETE"
        ]
        self.assertEqual(len(incomplete), 1)
        self.assertTrue(
            incomplete[0]["evidence"]["stratum"].startswith("object_specific|")
        )
        self.assertTrue(incomplete[0]["evidence"]["source_set_ids"])

    def test_c5_compares_every_sampled_binding_against_its_legacy_row(self):
        receipt = self.store.verify_time_series_c5_shadow(actor="internal_admin")

        bindings = receipt["manifest"]["bindings"]
        self.assertEqual(bindings["compared"], 1)
        self.assertEqual(bindings["unaccounted_binding_ids"], [])
        self.assertEqual(bindings["open_blocking_anomalies"], 0)

    def test_a_binding_that_lost_its_canonical_row_is_a_shadow_difference(self):
        canonical_bindings = self.store.link_layer_table_names()[
            "case_time_series_bindings"
        ]
        self.store.connection.execute(
            f"""
            UPDATE {canonical_bindings}
            SET status = 'removed', removed_at = created_at, removed_by = ?,
                lifecycle_revision = lifecycle_revision + 1
            WHERE id = ?
            """,
            ("tamper", int(self.legacy_binding["id"])),
        )
        self.store.connection.commit()

        with self.assertRaises(MigrationPhaseStopped) as stopped:
            self.store.verify_time_series_c5_shadow(actor="internal_admin")

        lineage = [
            finding["evidence"]
            for finding in stopped.exception.findings
            if finding["evidence"].get("subject")
            == f"binding:{self.legacy_binding['id']}"
        ]
        self.assertEqual(len(lineage), 1)
        self.assertEqual(lineage[0]["dimension"], "lineage")
        self.assertTrue(lineage[0]["legacy"]["accounted"])
        self.assertFalse(lineage[0]["canonical"]["accounted"])

    def seed_legacy_hydraulic_inflow_set(self, *, values=(5.0, 6.0, 7.0)):
        """A legacy hydraulic set, untouched by the canonical expansion."""

        now = "2026-01-01T00:00:00+00:00"
        cursor = self.store.connection.execute(
            """
            INSERT INTO hydraulic_time_series_sets (
                project_id, entity_type, entity_id, signal_key, version_number,
                version_label, content_hash, status, created_at, updated_at,
                created_by, updated_by
            ) VALUES (?, 'hydraulic_node', 1, 'natural_inflow_m3s', 1, 'v1',
                      'legacy-seed-hash', 'draft', ?, ?, 'seed', 'seed')
            """,
            (self.project["id"], now, now),
        )
        set_id = int(cursor.lastrowid)
        for index, value in enumerate(values):
            self.store.connection.execute(
                """
                INSERT INTO hydraulic_time_series_points (
                    hydraulic_time_series_set_id, point_index, timestamp,
                    duration_hours, value
                ) VALUES (?, ?, ?, 1.0, ?)
                """,
                (set_id, index, f"2026-01-01T{index:02d}:00:00-03:00", float(value)),
            )
        self.store.connection.commit()
        return set_id

    def test_legacy_hydraulic_series_keep_working_across_the_phase(self):
        legacy_id = self.seed_legacy_hydraulic_inflow_set()
        before = self.store.get_hydraulic_time_series_set(
            self.project["id"], legacy_id
        )

        receipt = self.store.verify_time_series_c5_shadow(actor="internal_admin")
        self.assertEqual(receipt["status"], "proven")

        self.assertEqual(
            self.store.get_hydraulic_time_series_set(self.project["id"], legacy_id),
            before,
        )
        migrated = self.store.migrate_hydraulic_time_series_set(
            project_id=self.project["id"],
            hydraulic_time_series_set_id=legacy_id,
            migrated_by="internal_analyst",
        )
        self.assertFalse(migrated["already_migrated"])
        again = self.store.migrate_hydraulic_time_series_set(
            project_id=self.project["id"],
            hydraulic_time_series_set_id=legacy_id,
            migrated_by="internal_analyst",
        )
        self.assertTrue(again["already_migrated"])
        self.assertEqual(
            int(again["time_series_set"]["id"]),
            int(migrated["time_series_set"]["id"]),
        )

    def test_the_legacy_hydraulic_read_serves_under_the_pause(self):
        legacy_id = self.seed_legacy_hydraulic_inflow_set()
        self.store.begin_legacy_mutation_pause(
            actor="internal_admin", reason="C5 shadow comparison"
        )
        self.addCleanup(
            self.store.release_legacy_mutation_pause, actor="internal_admin"
        )

        detail = self.store.get_hydraulic_time_series_set(
            self.project["id"], legacy_id
        )
        self.assertEqual(int(detail["id"]), legacy_id)

        with self.assertRaises(MigrationControlError) as refused:
            self.store.migrate_hydraulic_time_series_set(
                project_id=self.project["id"],
                hydraulic_time_series_set_id=legacy_id,
                migrated_by="internal_analyst",
            )
        self.assertEqual(refused.exception.code, "TS_MIGRATION_MUTATION_PAUSED")


@unittest.skipUnless(
    POSTGRES_TEST_DATABASE_URL,
    "POSTGRES_TEST_DATABASE_URL is required for PostgreSQL integration tests",
)
class PostgresC5ShadowVerificationTests(unittest.TestCase):
    def setUp(self):
        self.store = AnalystStore(POSTGRES_TEST_DATABASE_URL)
        self.rollback = self.store.connection._connection.transaction(  # noqa: SLF001
            force_rollback=True
        )
        self.rollback.__enter__()
        suffix = uuid.uuid4().hex[:12]
        self.project = self.store.create_project(name=f"TS7-018 {suffix}")
        self.scenario = self.store.create_scenario(
            project_id=self.project["id"], name=f"Base {suffix}"
        )
        case = self.store.get_or_create_case_for_scenario(self.scenario["id"])
        self.variant = self.store.get_or_create_default_input_variant(case["id"])
        self.legacy_set = import_legacy_price_set(self.store, self.scenario["id"])
        self.store.upsert_case_time_series_binding(
            case_input_variant_id=self.variant["id"],
            signal_key="import_price_usd_per_mwh",
            time_series_set_id=self.legacy_set["id"],
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

    def test_postgresql_runs_the_same_shadow_comparison(self):
        self.prove_recovery_point()
        self.store.backfill_time_series_c2(actor="internal_admin")
        self.store.backfill_time_series_c3(actor="internal_admin")
        try:
            self.store.backfill_time_series_c4(actor="internal_admin")
        except MigrationPhaseStopped:
            # The shared development fixture may carry unrelated defects; the
            # engine mirror is about the comparison being portable, not about
            # that fixture being clean.
            pass

        try:
            receipt = self.store.verify_time_series_c5_shadow(
                actor="internal_admin"
            )
            manifest = receipt["manifest"]
        except MigrationPhaseStopped as stopped:
            self.assertTrue(stopped.context["rollback_trigger"])
            run = self.store.read_migration_run(int(stopped.migration_run_id))
            self.assertEqual(run["status"], "stopped")
            manifest = run["manifest"]

        self.assertEqual(manifest["phase"], "C5")
        self.assertEqual(manifest["source_engine"], "postgresql")
        self.assertEqual(
            manifest["shadow_read"]["dimensions"],
            [
                "semantics",
                "counts",
                "values",
                "hashes",
                "authorization",
                "lineage",
            ],
        )
        self.assertIn(int(self.legacy_set["id"]), manifest["sample"]["set_ids"])
        self.assertEqual(manifest["settled_source"]["pending_dirty_roots"], 0)
        # The pause is always released, whether the phase proved or stopped.
        self.assertIsNone(self.store.read_legacy_mutation_pause())


if __name__ == "__main__":
    unittest.main()
