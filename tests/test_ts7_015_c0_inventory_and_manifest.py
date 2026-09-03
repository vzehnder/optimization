"""TS7-015 C0 inventory, signed manifest and proven restore.

The seams under test are the store's public migration-control surface and the
pure helpers of ``app.time_series_migration``. No HTTP surface is exposed by
this slice, so every contract here is an N1 domain test.
"""

import json
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
    C0_INVENTORY_TABLES,
    C0_RESTORE_TABLES,
    MIGRATION_CONTROL_TABLES,
    MigrationControlError,
    MigrationPhaseStopped,
    migration_actor,
)


POSTGRES_TEST_DATABASE_URL = os.environ.get("POSTGRES_TEST_DATABASE_URL")


def import_legacy_set(
    store: AnalystStore,
    scenario_id: int,
    *,
    name: str,
    signal_key: str,
    first_value: float,
    periods: int = 4,
) -> dict:
    """One legacy catalog set written by the current production writer."""

    start = datetime(2026, 1, 1)
    prepared = prepare_time_series_catalog_import(
        rows=[
            {
                "period_start": (start + timedelta(hours=offset)).isoformat(),
                "hours": "1.0",
                "value": str(first_value + offset),
            }
            for offset in range(periods)
        ],
        request=CatalogImportRequest(
            set_name=name,
            version_label="v1",
            data_kind="real",
            timezone="UTC",
            timestamp_column="period_start",
            duration_hours_column="hours",
            signal_mappings=[
                CatalogSignalMappingRequest(source_column="value", signal_key=signal_key)
            ],
        ),
    )
    return store.import_time_series_catalog_set(
        scenario_id=scenario_id,
        source={
            "id": f"ts7-015-{name.lower().replace(' ', '-')}",
            "original_filename": f"{name}.csv",
            "media_type": "text/csv",
            "checksum": f"sha256:{name}",
        },
        prepared_import=prepared,
    )


class C0StructuralDifferenceTests(unittest.TestCase):
    """Chapter 10.2: an unexplained structural difference stops C0."""

    def setUp(self):
        self.store = AnalystStore("sqlite:///:memory:")
        self.project = self.store.create_project(name="Cuenca Norte")
        self.scenario = self.store.create_scenario(
            project_id=self.project["id"], name="Base 2026"
        )
        self.demand = import_legacy_set(
            self.store,
            self.scenario["id"],
            name="Demanda Norte",
            signal_key="load_demand_mw",
            first_value=100.0,
        )
        self.case = self.store.get_or_create_case_for_scenario(self.scenario["id"])
        self.variant = self.store.get_or_create_default_input_variant(self.case["id"])

    def tearDown(self):
        self.store.close()

    def _inject_duplicate_series_key(self) -> None:
        # The legacy unique key spans ``(set, signal_key, entity_type,
        # entity_key)`` and both engines treat NULL as distinct, so a second
        # entity-less row with the same key commits and two identities collapse
        # onto one ``series_key`` (chapter 10.4).
        self.store.connection.execute(
            """
            INSERT INTO time_series_signals (
                time_series_set_id, signal_key, unit, entity_type, entity_key,
                signal_role, aggregation, created_at, source_column, source_unit
            )
            VALUES (?, 'load_demand_mw', 'MW', NULL, NULL,
                    'input', 'period_average', '2026-01-01T00:00:00+00:00', '', '')
            """,
            (int(self.demand["id"]),),
        )
        self.store.connection.commit()

    def _inject_unresolvable_binding(self) -> None:
        self.store.connection.execute(
            """
            INSERT INTO case_time_series_bindings (
                case_input_variant_id, signal_key, entity_type, entity_id,
                time_series_set_id, required, created_at, updated_at,
                created_by, updated_by
            )
            VALUES (?, 'hydro_inflow_m3s', NULL, NULL, ?, 1,
                    '2026-01-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00',
                    'legacy_analyst', 'legacy_analyst')
            """,
            (int(self.variant["id"]), int(self.demand["id"])),
        )
        self.store.connection.commit()

    def _take(self, explanations=None):
        with tempfile.TemporaryDirectory() as directory:
            return self.store.take_c0_recovery_point(
                actor="internal_admin",
                copy_directory=Path(directory),
                explanations=explanations,
            )

    def test_an_unexplained_structural_difference_stops_c0_without_a_signature(self):
        self._inject_duplicate_series_key()
        self._inject_unresolvable_binding()

        with self.assertRaises(MigrationPhaseStopped) as stopped:
            self._take()

        run = self.store.read_migration_run(stopped.exception.migration_run_id)
        anomalies = self.store.read_migration_anomalies(
            stopped.exception.migration_run_id
        )
        self.assertEqual(
            {
                "code": stopped.exception.code,
                "run_status": run["status"],
                "signature": run["manifest_signature"],
                "anomaly_codes": sorted(anomaly["code"] for anomaly in anomalies),
                "resolutions": sorted({anomaly["resolution"] for anomaly in anomalies}),
                "actors": sorted({anomaly["actor"] for anomaly in anomalies}),
                "unexplained_finding_keys": sorted(
                    stopped.exception.unexplained_finding_keys
                ),
            },
            {
                "code": "TS_MIGRATION_C0_STOPPED",
                "run_status": "stopped",
                "signature": "",
                "anomaly_codes": [
                    "TS_MIGRATION_BINDING_SIGNAL_UNRESOLVED",
                    "TS_MIGRATION_DUPLICATE_SERIES_KEY",
                ],
                "resolutions": ["open"],
                "actors": [
                    migration_actor(stopped.exception.migration_run_id)
                ],
                "unexplained_finding_keys": [
                    "binding_signal_unresolved:binding=1",
                    f"duplicate_series_key:set={self.demand['id']}"
                    ":series_key=load_demand_mw",
                ],
            },
        )

    def test_an_explained_difference_lets_c0_finish_and_stays_on_the_record(self):
        self._inject_duplicate_series_key()
        explanations = {
            f"duplicate_series_key:set={self.demand['id']}:series_key=load_demand_mw": (
                "Fila entity-less heredada del importador 2024; se separa en C3."
            )
        }

        receipt = self._take(explanations=explanations)
        anomalies = self.store.read_migration_anomalies(receipt["migration_run_id"])

        self.assertEqual(
            {
                "status": receipt["status"],
                "signed": bool(receipt["manifest_signature"]),
                "duplicates": [
                    {
                        "code": entry["code"],
                        "finding_key": entry["finding_key"],
                        "row_count": entry["row_count"],
                        "explained": entry["explained"],
                    }
                    for entry in receipt["manifest"]["structural_differences"][
                        "duplicates"
                    ]
                ],
                "anomaly_resolution": [
                    (anomaly["resolution"], anomaly["resolution_note"])
                    for anomaly in anomalies
                ],
            },
            {
                "status": "proven",
                "signed": True,
                "duplicates": [
                    {
                        "code": "TS_MIGRATION_DUPLICATE_SERIES_KEY",
                        "finding_key": (
                            f"duplicate_series_key:set={self.demand['id']}"
                            ":series_key=load_demand_mw"
                        ),
                        "row_count": 2,
                        "explained": True,
                    }
                ],
                "anomaly_resolution": [
                    (
                        "explained",
                        "Fila entity-less heredada del importador 2024;"
                        " se separa en C3.",
                    )
                ],
            },
        )

    def test_a_clean_source_reports_no_structural_difference(self):
        receipt = self._take()

        self.assertEqual(
            receipt["manifest"]["structural_differences"],
            {
                "broken_references": [],
                "duplicates": [],
                "difference_count": 0,
                "explained": {},
            },
        )


class C0ExecutableVariantTests(unittest.TestCase):
    """The manifest names which variants a run could materialize, and how."""

    def setUp(self):
        self.store = AnalystStore("sqlite:///:memory:")
        self.project = self.store.create_project(name="Cuenca Norte")
        self.scenario = self.store.create_scenario(
            project_id=self.project["id"], name="Base 2026"
        )
        self.demand = import_legacy_set(
            self.store,
            self.scenario["id"],
            name="Demanda Norte",
            signal_key="load_demand_mw",
            first_value=100.0,
        )
        self.price = import_legacy_set(
            self.store,
            self.scenario["id"],
            name="Precio Spot",
            signal_key="import_price_usd_per_mwh",
            first_value=50.0,
        )
        self.case = self.store.get_or_create_case_for_scenario(self.scenario["id"])
        self.variant = self.store.get_or_create_default_input_variant(self.case["id"])

    def tearDown(self):
        self.store.close()

    def _take(self, explanations=None):
        with tempfile.TemporaryDirectory() as directory:
            return self.store.take_c0_recovery_point(
                actor="internal_admin",
                copy_directory=Path(directory),
                explanations=explanations,
            )

    def test_a_variant_becomes_executable_only_once_every_binding_resolves(self):
        empty = self._take()["manifest"]["executable_variants"]

        self.store.upsert_case_time_series_binding(
            case_input_variant_id=self.variant["id"],
            signal_key="load_demand_mw",
            time_series_set_id=self.demand["id"],
        )
        bound = self._take()["manifest"]["executable_variants"]

        self.store.upsert_case_time_series_binding(
            case_input_variant_id=self.variant["id"],
            signal_key="import_price_usd_per_mwh",
            time_series_set_id=self.price["id"],
        )
        widened = self._take()["manifest"]["executable_variants"]

        self.assertEqual(
            {
                "an_unbound_variant_is_not_executable": empty["count"],
                "unbound_reasons": [
                    entry["blocked_by"] for entry in empty["variants"]
                ],
                "one_resolved_binding_is_executable": bound["count"],
                "binding_counts": [
                    entry["binding_count"] for entry in widened["variants"]
                ],
                "a_new_binding_moves_the_fingerprint": bound["fingerprint"]
                != widened["fingerprint"],
                "the_fingerprint_is_reproducible": self._take()["manifest"][
                    "executable_variants"
                ]["fingerprint"]
                == widened["fingerprint"],
            },
            {
                "an_unbound_variant_is_not_executable": 0,
                "unbound_reasons": [["no_bindings"]],
                "one_resolved_binding_is_executable": 1,
                "binding_counts": [2],
                "a_new_binding_moves_the_fingerprint": True,
                "the_fingerprint_is_reproducible": True,
            },
        )

    def test_the_fingerprint_follows_the_content_the_variant_would_execute(self):
        self.store.upsert_case_time_series_binding(
            case_input_variant_id=self.variant["id"],
            signal_key="load_demand_mw",
            time_series_set_id=self.demand["id"],
        )
        before = self._take()["manifest"]["executable_variants"]["fingerprint"]

        self.store.connection.execute(
            "UPDATE time_series_sets SET content_hash = ? WHERE id = ?",
            ("sha256:rewritten-by-a-later-legacy-write", int(self.demand["id"])),
        )
        self.store.connection.commit()
        after = self._take()["manifest"]["executable_variants"]["fingerprint"]

        self.assertNotEqual(before, after)

    def test_an_unresolvable_binding_leaves_its_variant_blocked_and_named(self):
        self.store.connection.execute(
            """
            INSERT INTO case_time_series_bindings (
                case_input_variant_id, signal_key, entity_type, entity_id,
                time_series_set_id, required, created_at, updated_at,
                created_by, updated_by
            )
            VALUES (?, 'hydro_inflow_m3s', NULL, NULL, ?, 1,
                    '2026-01-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00',
                    'legacy_analyst', 'legacy_analyst')
            """,
            (int(self.variant["id"]), int(self.demand["id"])),
        )
        self.store.connection.commit()

        variants = self._take(
            explanations={
                "binding_signal_unresolved:binding=1": "Binding huerfano; se retira en C4."
            }
        )["manifest"]["executable_variants"]

        self.assertEqual(
            {
                "count": variants["count"],
                "variants": [
                    {
                        "executable": entry["executable"],
                        "binding_count": entry["binding_count"],
                        "blocked_by": entry["blocked_by"],
                    }
                    for entry in variants["variants"]
                ],
            },
            {
                "count": 0,
                "variants": [
                    {
                        "executable": False,
                        "binding_count": 1,
                        "blocked_by": ["binding_signal_unresolved:binding=1"],
                    }
                ],
            },
        )


class C0ProvenRestoreTests(unittest.TestCase):
    """An untested backup is not a recovery point (chapter 10.2)."""

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.store = AnalystStore("sqlite:///:memory:")
        self.project = self.store.create_project(name="Cuenca Norte")
        self.scenario = self.store.create_scenario(
            project_id=self.project["id"], name="Base 2026"
        )
        self.demand = import_legacy_set(
            self.store,
            self.scenario["id"],
            name="Demanda Norte",
            signal_key="load_demand_mw",
            first_value=100.5,
        )
        self.case = self.store.get_or_create_case_for_scenario(self.scenario["id"])
        self.variant = self.store.get_or_create_default_input_variant(self.case["id"])
        self.store.upsert_case_time_series_binding(
            case_input_variant_id=self.variant["id"],
            signal_key="load_demand_mw",
            time_series_set_id=self.demand["id"],
        )

    def tearDown(self):
        self.store.close()
        self.directory.cleanup()

    def test_the_copy_is_written_and_its_restore_reproduces_the_inventory(self):
        receipt = self.store.take_c0_recovery_point(
            actor="internal_admin", copy_directory=self.root / "recovery"
        )
        recovery = receipt["manifest"]["recovery_point"]
        copy_path = Path(receipt["copy_path"])

        self.assertEqual(
            {
                "copy_exists": copy_path.is_file(),
                "proven": recovery["proven"],
                "restore_engine": recovery["restore_engine"],
                "restored_inventory_matches": recovery["restored_inventory_digest"]
                == recovery["source_inventory_digest"],
                "copied_tables": sorted(
                    json.loads(copy_path.read_text(encoding="utf-8"))["tables"]
                ),
            },
            {
                "copy_exists": True,
                "proven": True,
                "restore_engine": "sqlite",
                "restored_inventory_matches": True,
                "copied_tables": sorted(C0_RESTORE_TABLES),
            },
        )

    def test_the_restore_preserves_the_previous_identity_of_every_row(self):
        receipt = self.store.take_c0_recovery_point(
            actor="internal_admin", copy_directory=self.root / "recovery"
        )
        copied = json.loads(Path(receipt["copy_path"]).read_text(encoding="utf-8"))
        source = self.store.connection.execute(
            "SELECT id, created_at, created_by FROM time_series_sets ORDER BY id"
        ).fetchall()

        self.assertEqual(
            [
                {
                    "id": row["id"],
                    "created_at": row["created_at"],
                    "created_by": row["created_by"],
                }
                for row in copied["tables"]["time_series_sets"]
            ],
            [
                {
                    "id": int(row["id"]),
                    "created_at": str(row["created_at"]),
                    "created_by": str(row["created_by"]),
                }
                for row in source
            ],
        )

    def test_a_copy_that_lost_a_row_is_refused_as_a_recovery_point(self):
        receipt = self.store.take_c0_recovery_point(
            actor="internal_admin", copy_directory=self.root / "recovery"
        )
        copy_path = Path(receipt["copy_path"])
        tampered = json.loads(copy_path.read_text(encoding="utf-8"))
        tampered["tables"]["time_series_values"].pop()
        copy_path.write_text(json.dumps(tampered), encoding="utf-8")

        with self.assertRaises(MigrationControlError) as refusal:
            self.store.prove_recovery_copy(
                copy_path, restore_directory=self.root / "second-restore"
            )

        self.assertEqual(
            {
                "code": refusal.exception.code,
                "divergent_tables": refusal.exception.context["divergent_tables"],
            },
            {
                "code": "TS_MIGRATION_RESTORE_NOT_PROVEN",
                "divergent_tables": ["time_series_values"],
            },
        )


class MigrationMappingTests(unittest.TestCase):
    """Chapter 10.3: a difference is a conflict, never a second silent insert."""

    def setUp(self):
        self.store = AnalystStore("sqlite:///:memory:")
        with tempfile.TemporaryDirectory() as directory:
            self.receipt = self.store.take_c0_recovery_point(
                actor="internal_admin", copy_directory=Path(directory)
            )
        self.run_id = self.receipt["migration_run_id"]

    def tearDown(self):
        self.store.close()

    def _record(self, *, target_id: str, source_hash: str = "sha256:legacy-set-7"):
        return self.store.record_migration_mapping(
            migration_run_id=self.run_id,
            source_kind="time_series_set",
            source_table="time_series_sets",
            source_id="7",
            target_kind="canonical_set",
            target_id=target_id,
            source_hash=source_hash,
        )

    def _mapping_rows(self) -> list[dict]:
        table = self.store.migration_control_table_names()[
            "time_series_migration_mappings"
        ]
        return [
            dict(row)
            for row in self.store.connection.execute(
                f"SELECT * FROM {table} ORDER BY id"
            ).fetchall()
        ]

    def test_a_repeated_mapping_converges_and_a_different_one_is_a_conflict(self):
        created = self._record(target_id="41")
        repeated = self._record(target_id="41")

        with self.assertRaises(MigrationControlError) as conflict:
            self._record(target_id="42")

        rows = self._mapping_rows()
        self.assertEqual(
            {
                "created": created["status"],
                "repeated": repeated["status"],
                "conflict_code": conflict.exception.code,
                "conflict_context": {
                    "existing_target_id": conflict.exception.context[
                        "existing_target_id"
                    ],
                    "incoming_target_id": conflict.exception.context[
                        "incoming_target_id"
                    ],
                },
                "row_count": len(rows),
                "stored_target_id": rows[0]["target_id"],
                "actor": rows[0]["actor"],
            },
            {
                "created": "created",
                "repeated": "unchanged",
                "conflict_code": "TS_MIGRATION_MAPPING_CONFLICT",
                "conflict_context": {
                    "existing_target_id": "41",
                    "incoming_target_id": "42",
                },
                "row_count": 1,
                "stored_target_id": "41",
                "actor": migration_actor(self.run_id),
            },
        )

    def test_a_changed_source_hash_for_the_same_pair_is_also_a_conflict(self):
        self._record(target_id="41")

        with self.assertRaises(MigrationControlError) as conflict:
            self._record(target_id="41", source_hash="sha256:legacy-set-7-mutated")

        self.assertEqual(
            {
                "code": conflict.exception.code,
                "reason": conflict.exception.context["reason"],
                "row_count": len(self._mapping_rows()),
            },
            {
                "code": "TS_MIGRATION_MAPPING_CONFLICT",
                "reason": "source_hash_changed",
                "row_count": 1,
            },
        )


class MigrationPhaseGateTests(unittest.TestCase):
    """No phase opens without a recovery point that still describes the source."""

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.store = AnalystStore("sqlite:///:memory:")
        self.project = self.store.create_project(name="Cuenca Norte")
        self.scenario = self.store.create_scenario(
            project_id=self.project["id"], name="Base 2026"
        )

    def tearDown(self):
        self.store.close()
        self.directory.cleanup()

    def test_c1_is_refused_until_a_proven_c0_describes_the_current_source(self):
        with self.assertRaises(MigrationControlError) as without:
            self.store.open_migration_phase(phase="C1", actor="internal_admin")

        recovery = self.store.take_c0_recovery_point(
            actor="internal_admin", copy_directory=self.root / "first"
        )
        opened = self.store.open_migration_phase(phase="C1", actor="internal_admin")

        import_legacy_set(
            self.store,
            self.scenario["id"],
            name="Demanda Norte",
            signal_key="load_demand_mw",
            first_value=100.0,
        )
        with self.assertRaises(MigrationControlError) as after_drift:
            self.store.open_migration_phase(phase="C2", actor="internal_admin")

        self.assertEqual(
            {
                "without_a_recovery_point": without.exception.code,
                "reason_without": without.exception.context["reason"],
                "opened_phase": opened["phase"],
                "opened_against": opened["recovery_point_run_id"],
                "after_the_source_moved": after_drift.exception.code,
                "reason_after_drift": after_drift.exception.context["reason"],
            },
            {
                "without_a_recovery_point": "TS_MIGRATION_RECOVERY_POINT_REQUIRED",
                "reason_without": "no_proven_c0",
                "opened_phase": "C1",
                "opened_against": recovery["migration_run_id"],
                "after_the_source_moved": "TS_MIGRATION_RECOVERY_POINT_REQUIRED",
                "reason_after_drift": "source_moved_since_recovery_point",
            },
        )

    def test_a_stopped_c0_is_not_a_recovery_point(self):
        demand = import_legacy_set(
            self.store,
            self.scenario["id"],
            name="Demanda Norte",
            signal_key="load_demand_mw",
            first_value=100.0,
        )
        self.store.connection.execute(
            """
            INSERT INTO time_series_signals (
                time_series_set_id, signal_key, unit, entity_type, entity_key,
                signal_role, aggregation, created_at, source_column, source_unit
            )
            VALUES (?, 'load_demand_mw', 'MW', NULL, NULL,
                    'input', 'period_average', '2026-01-01T00:00:00+00:00', '', '')
            """,
            (int(demand["id"]),),
        )
        self.store.connection.commit()

        with self.assertRaises(MigrationPhaseStopped):
            self.store.take_c0_recovery_point(
                actor="internal_admin", copy_directory=self.root / "stopped"
            )
        with self.assertRaises(MigrationControlError) as refusal:
            self.store.open_migration_phase(phase="C1", actor="internal_admin")

        self.assertEqual(refusal.exception.context["reason"], "no_proven_c0")


class LegacyDirtyRootTests(unittest.TestCase):
    """The monotone queue of roots touched after the watermark."""

    def setUp(self):
        self.store = AnalystStore("sqlite:///:memory:")
        with tempfile.TemporaryDirectory() as directory:
            self.run_id = self.store.take_c0_recovery_point(
                actor="internal_admin", copy_directory=Path(directory)
            )["migration_run_id"]

    def tearDown(self):
        self.store.close()

    def test_the_queue_only_moves_forward_and_drains_to_zero(self):
        first = self.store.enqueue_legacy_dirty_root(
            migration_run_id=self.run_id, root_kind="time_series_set", root_id="7"
        )
        second = self.store.enqueue_legacy_dirty_root(
            migration_run_id=self.run_id, root_kind="case_input_variant", root_id="3"
        )
        pending_before = self.store.read_pending_dirty_roots()

        drained = self.store.drain_legacy_dirty_roots(
            through_sequence=second["sequence_number"]
        )
        reopened = self.store.enqueue_legacy_dirty_root(
            migration_run_id=self.run_id, root_kind="time_series_set", root_id="7"
        )

        self.assertEqual(
            {
                "sequence_numbers": [
                    first["sequence_number"],
                    second["sequence_number"],
                ],
                "pending_before": [
                    (entry["root_kind"], entry["root_id"]) for entry in pending_before
                ],
                "drained": drained["drained_count"],
                "pending_after_drain": drained["pending_count"],
                "a_root_dirtied_again_takes_a_new_sequence": reopened[
                    "sequence_number"
                ],
                "pending_after_reopen": [
                    (entry["root_kind"], entry["root_id"])
                    for entry in self.store.read_pending_dirty_roots()
                ],
                "actor": reopened["actor"],
            },
            {
                "sequence_numbers": [1, 2],
                "pending_before": [
                    ("time_series_set", "7"),
                    ("case_input_variant", "3"),
                ],
                "drained": 2,
                "pending_after_drain": 0,
                "a_root_dirtied_again_takes_a_new_sequence": 3,
                "pending_after_reopen": [("time_series_set", "7")],
                "actor": migration_actor(self.run_id),
            },
        )


class MigratorActorAndSourceIntegrityTests(unittest.TestCase):
    """The migrator signs its own rows and never rewrites the previous identity."""

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.store = AnalystStore("sqlite:///:memory:")
        self.project = self.store.create_project(name="Cuenca Norte")
        self.scenario = self.store.create_scenario(
            project_id=self.project["id"], name="Base 2026"
        )
        self.demand = import_legacy_set(
            self.store,
            self.scenario["id"],
            name="Demanda Norte",
            signal_key="load_demand_mw",
            first_value=100.0,
        )

    def tearDown(self):
        self.store.close()
        self.directory.cleanup()

    def _legacy_snapshot(self) -> dict:
        return {
            table: [
                dict(row)
                for row in self.store.connection.execute(
                    f"SELECT * FROM {table} ORDER BY id"
                ).fetchall()
            ]
            for table in C0_INVENTORY_TABLES
        }

    def test_c0_reads_the_legacy_source_without_writing_a_single_row(self):
        before = self._legacy_snapshot()

        self.store.take_c0_recovery_point(
            actor="internal_admin", copy_directory=self.root / "recovery"
        )

        self.assertEqual(self._legacy_snapshot(), before)

    def test_every_row_the_migrator_creates_carries_its_technical_actor(self):
        receipt = self.store.take_c0_recovery_point(
            actor="internal_admin", copy_directory=self.root / "recovery"
        )
        run_id = receipt["migration_run_id"]
        self.store.record_migration_mapping(
            migration_run_id=run_id,
            source_kind="time_series_set",
            source_table="time_series_sets",
            source_id=str(self.demand["id"]),
            target_kind="canonical_set",
            target_id="900",
            source_hash="sha256:observed",
        )
        self.store.enqueue_legacy_dirty_root(
            migration_run_id=run_id,
            root_kind="time_series_set",
            root_id=str(self.demand["id"]),
        )
        phase = self.store.open_migration_phase(phase="C1", actor="internal_admin")

        tables = self.store.migration_control_table_names()
        actors = {
            logical: sorted(
                {
                    str(row["actor"])
                    for row in self.store.connection.execute(
                        f"SELECT actor FROM {physical}"
                    ).fetchall()
                }
            )
            for logical, physical in tables.items()
        }
        run = self.store.read_migration_run(run_id)

        self.assertEqual(
            {
                "actors": actors,
                "the_human_who_asked_is_kept_apart": run["started_by"],
                "the_run_row_is_signed_by_the_migrator": run["actor"],
            },
            {
                "actors": {
                    "time_series_legacy_dirty_roots": [migration_actor(run_id)],
                    "time_series_migration_anomalies": [],
                    "time_series_migration_mappings": [migration_actor(run_id)],
                    "time_series_migration_runs": sorted(
                        {
                            migration_actor(run_id),
                            migration_actor(phase["migration_run_id"]),
                        }
                    ),
                },
                "the_human_who_asked_is_kept_apart": "internal_admin",
                "the_run_row_is_signed_by_the_migrator": migration_actor(run_id),
            },
        )


class MigrationControlSurfaceTests(unittest.TestCase):
    """The four control tables of chapter 10.3 exist and change nothing else."""

    def setUp(self):
        self.store = AnalystStore("sqlite:///:memory:")

    def tearDown(self):
        self.store.close()

    def _sqlite_tables(self) -> set[str]:
        return {
            row["name"]
            for row in self.store.connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }

    def test_the_four_control_tables_land_beside_the_untouched_legacy_source(self):
        physical = self.store.migration_control_table_names()
        tables = self._sqlite_tables()

        self.assertEqual(
            {
                "logical_names": sorted(physical),
                "physical_names": sorted(physical.values()),
                "missing": sorted(set(physical.values()) - tables),
                "legacy_intact": sorted(
                    name
                    for name in (
                        "time_series_sets",
                        "time_series_signals",
                        "time_series_set_revisions",
                        "time_series_periods",
                        "time_series_values",
                        "time_series_sources",
                        "case_time_series_bindings",
                        "case_input_variants",
                    )
                    if name in tables
                ),
            },
            {
                "logical_names": [
                    "time_series_legacy_dirty_roots",
                    "time_series_migration_anomalies",
                    "time_series_migration_mappings",
                    "time_series_migration_runs",
                ],
                "physical_names": [
                    "time_series_legacy_dirty_roots",
                    "time_series_migration_anomalies",
                    "time_series_migration_mappings",
                    "time_series_migration_runs",
                ],
                "missing": [],
                "legacy_intact": [
                    "case_input_variants",
                    "case_time_series_bindings",
                    "time_series_periods",
                    "time_series_set_revisions",
                    "time_series_sets",
                    "time_series_signals",
                    "time_series_sources",
                    "time_series_values",
                ],
            },
        )
        self.assertEqual(sorted(MIGRATION_CONTROL_TABLES), sorted(physical))

    def test_the_inventory_counts_and_maximum_keys_describe_the_legacy_source(self):
        project = self.store.create_project(name="Cuenca Norte")
        scenario = self.store.create_scenario(
            project_id=project["id"], name="Base 2026"
        )
        first = import_legacy_set(
            self.store,
            scenario["id"],
            name="Demanda Norte",
            signal_key="load_demand_mw",
            first_value=100.0,
        )
        second = import_legacy_set(
            self.store,
            scenario["id"],
            name="Precio Spot",
            signal_key="import_price_usd_per_mwh",
            first_value=50.0,
            periods=6,
        )

        with tempfile.TemporaryDirectory() as directory:
            receipt = self.store.take_c0_recovery_point(
                actor="internal_admin", copy_directory=Path(directory)
            )

        inventory = receipt["manifest"]["inventory"]
        self.assertEqual(
            {
                "tables": sorted(inventory),
                "row_counts": {
                    table: inventory[table]["row_count"] for table in sorted(inventory)
                },
                "maximum_primary_keys": {
                    "time_series_sets": inventory["time_series_sets"][
                        "maximum_primary_key"
                    ],
                    "time_series_signals": inventory["time_series_signals"][
                        "maximum_primary_key"
                    ],
                },
                "hashes_are_sha256": sorted(
                    {
                        len(entry["content_hash"].removeprefix("sha256:"))
                        for entry in inventory.values()
                    }
                ),
            },
            {
                "tables": sorted(C0_INVENTORY_TABLES),
                "row_counts": {
                    "case_input_variants": 0,
                    "case_time_series_bindings": 0,
                    "time_series_periods": 10,
                    "time_series_set_revisions": 2,
                    "time_series_sets": 2,
                    "time_series_signals": 2,
                    "time_series_sources": 2,
                    "time_series_values": 10,
                },
                "maximum_primary_keys": {
                    "time_series_sets": int(second["id"]),
                    "time_series_signals": 2,
                },
                "hashes_are_sha256": [64],
            },
        )
        self.assertEqual(int(first["id"]), int(second["id"]) - 1)

    def test_repeating_c0_over_an_unchanged_source_reproduces_the_same_manifest(self):
        project = self.store.create_project(name="Cuenca Norte")
        scenario = self.store.create_scenario(
            project_id=project["id"], name="Base 2026"
        )
        import_legacy_set(
            self.store,
            scenario["id"],
            name="Demanda Norte",
            signal_key="load_demand_mw",
            first_value=100.0,
        )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = self.store.take_c0_recovery_point(
                actor="internal_admin", copy_directory=root / "first"
            )
            second = self.store.take_c0_recovery_point(
                actor="internal_admin", copy_directory=root / "second"
            )
            import_legacy_set(
                self.store,
                scenario["id"],
                name="Precio Spot",
                signal_key="import_price_usd_per_mwh",
                first_value=50.0,
            )
            third = self.store.take_c0_recovery_point(
                actor="internal_admin", copy_directory=root / "third"
            )

        self.assertEqual(
            {
                "unchanged_source_repeats_the_manifest": first["manifest"]
                == second["manifest"],
                "unchanged_source_repeats_the_digest": first["manifest_digest"]
                == second["manifest_digest"],
                "unchanged_source_repeats_the_signature": first["manifest_signature"]
                == second["manifest_signature"],
                "a_changed_source_changes_the_digest": first["manifest_digest"]
                != third["manifest_digest"],
                "each_repetition_is_its_own_run": len(
                    {
                        first["migration_run_id"],
                        second["migration_run_id"],
                        third["migration_run_id"],
                    }
                ),
                "signature_verifies": self.store.verify_c0_manifest(
                    manifest=second["manifest"],
                    manifest_signature=second["manifest_signature"],
                ),
                "a_foreign_signature_is_refused": self.store.verify_c0_manifest(
                    manifest=third["manifest"],
                    manifest_signature=first["manifest_signature"],
                ),
            },
            {
                "unchanged_source_repeats_the_manifest": True,
                "unchanged_source_repeats_the_digest": True,
                "unchanged_source_repeats_the_signature": True,
                "a_changed_source_changes_the_digest": True,
                "each_repetition_is_its_own_run": 3,
                "signature_verifies": True,
                "a_foreign_signature_is_refused": False,
            },
        )

    def test_the_control_surface_starts_empty_and_names_its_technical_actor(self):
        counts = {
            logical: int(
                self.store.connection.execute(
                    f"SELECT COUNT(*) AS total FROM {physical}"
                ).fetchone()["total"]
            )
            for logical, physical in self.store.migration_control_table_names().items()
        }

        self.assertEqual(
            {"counts": counts, "actor": migration_actor(7)},
            {
                "counts": {logical: 0 for logical in MIGRATION_CONTROL_TABLES},
                "actor": "system:migration:7",
            },
        )


@unittest.skipUnless(
    POSTGRES_TEST_DATABASE_URL,
    "POSTGRES_TEST_DATABASE_URL is required for PostgreSQL integration tests",
)
class PostgresMigrationControlTests(unittest.TestCase):
    """The same control surface and the same probes on the second engine."""

    def setUp(self):
        self.store = AnalystStore(POSTGRES_TEST_DATABASE_URL)
        self.suffix = uuid.uuid4().hex[:12]

    def tearDown(self):
        table = self.store.migration_control_table_names()[
            "time_series_migration_mappings"
        ]
        self.store.connection.execute(
            f"DELETE FROM {table} WHERE source_kind = ?", (f"ts7-015-{self.suffix}",)
        )
        self.store.close()

    def test_the_control_tables_and_the_c0_probes_run_on_postgresql(self):
        present = sorted(
            row["table_name"]
            for row in self.store.connection.execute(
                """
                SELECT table_name FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name IN (
                    'time_series_migration_runs',
                    'time_series_migration_mappings',
                    'time_series_migration_anomalies',
                    'time_series_legacy_dirty_roots'
                )
                """
            ).fetchall()
        )
        inventory = self.store._c0_inventory()
        differences, findings = self.store._c0_structural_differences(None)
        variants = self.store._c0_executable_variants(findings)

        self.assertEqual(
            {
                "control_tables": present,
                "inventory_tables": sorted(inventory),
                "hash_prefixes": sorted(
                    {entry["content_hash"].split(":")[0] for entry in inventory.values()}
                ),
                "difference_kinds": sorted(
                    key for key in differences if key.endswith("s") or "count" in key
                ),
                "variant_keys": sorted(variants),
            },
            {
                "control_tables": sorted(MIGRATION_CONTROL_TABLES),
                "inventory_tables": sorted(C0_INVENTORY_TABLES),
                "hash_prefixes": ["sha256"],
                "difference_kinds": [
                    "broken_references",
                    "difference_count",
                    "duplicates",
                ],
                "variant_keys": ["count", "fingerprint", "variants"],
            },
        )

    def test_a_mapping_conflict_is_refused_on_postgresql_too(self):
        runs = self.store.migration_control_table_names()[
            "time_series_migration_runs"
        ]
        run_id = self.store._insert_migration_row(
            f"""
            INSERT INTO {runs} (
                control_version, phase, status, source_engine, watermark,
                started_at, started_by, actor
            )
            VALUES (1, 'C0', 'running', 'postgresql', '', ?, 'internal_admin', ?)
            """,
            ("2026-09-03T00:00:00+00:00", "system:migration:0"),
        )
        common = {
            "migration_run_id": run_id,
            "source_kind": f"ts7-015-{self.suffix}",
            "source_table": "time_series_sets",
            "source_id": "7",
            "target_kind": "canonical_set",
            "source_hash": "sha256:observed",
        }
        created = self.store.record_migration_mapping(**common, target_id="41")
        repeated = self.store.record_migration_mapping(**common, target_id="41")

        with self.assertRaises(MigrationControlError) as conflict:
            self.store.record_migration_mapping(**common, target_id="42")

        self.assertEqual(
            {
                "created": created["status"],
                "repeated": repeated["status"],
                "code": conflict.exception.code,
                "actor": self.store.read_migration_run(run_id)["actor"],
            },
            {
                "created": "created",
                "repeated": "unchanged",
                "code": "TS_MIGRATION_MAPPING_CONFLICT",
                "actor": "system:migration:0",
            },
        )
