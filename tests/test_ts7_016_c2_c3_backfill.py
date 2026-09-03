"""TS7-016 C2-C3 resumable canonical backfill.

The seam under test is the store's public migration surface.  Assertions read
the returned receipts and canonical read APIs/tables only where the migration
contract itself makes persisted evidence observable; no private helper is
called by a test.
"""

import os
import tempfile
import unittest
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from app.persistence import AnalystStore
from app.time_series_canonical import CanonicalRevisionError
from app.time_series_catalog import (
    CatalogImportRequest,
    CatalogSignalMappingRequest,
    CatalogValueEdit,
    compute_catalog_content_hash,
    prepare_time_series_catalog_import,
)
from app.time_series_catalog_projection import CatalogQueryError
from app.time_series_migration import MigrationPhaseStopped


POSTGRES_TEST_DATABASE_URL = os.environ.get("POSTGRES_TEST_DATABASE_URL")


def system_case(nodes):
    return {
        "schema_version": "bess_system_dispatch.v2",
        "case_name": "caso",
        "nodes": nodes,
        "edges": [],
        "time_series": {
            "periods": [
                {
                    "timestamp": "2026-01-01T00:00:00",
                    "duration_hours": 1.0,
                    "grid_import_price_usd_per_mwh": 10.0,
                    "grid_export_price_usd_per_mwh": 5.0,
                }
            ]
        },
        "constraints": {},
        "solver": {"name": "HiGHS", "options": {}},
    }


def import_legacy_set(store, scenario_id, *, name="Demanda Norte", periods=4):
    start = datetime(2026, 1, 1)
    prepared = prepare_time_series_catalog_import(
        rows=[
            {
                "period_start": (start + timedelta(hours=offset)).isoformat(),
                "hours": "1.0",
                "value": str(100.0 + offset),
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
                CatalogSignalMappingRequest(
                    source_column="value", signal_key="load_demand_mw"
                )
            ],
        ),
    )
    return store.import_time_series_catalog_set(
        scenario_id=scenario_id,
        source={
            "id": f"ts7-016-{name.lower().replace(' ', '-')}",
            "original_filename": f"{name}.csv",
            "media_type": "text/csv",
            "checksum": f"sha256:{name}",
        },
        prepared_import=prepared,
        created_by="legacy_analyst",
    )


def refresh_legacy_hash(store, project_id, set_id):
    current = store.get_time_series_set(project_id, set_id)
    content_hash = compute_catalog_content_hash(
        set_name=current["name"],
        version_label=current["version_label"],
        data_kind=current["data_kind"],
        timezone=current["timezone"],
        signals=current["signals"],
        periods=current["periods"],
        values=[
            {
                **value,
                "source_row_number": position + 2,
                "entity_key": next(
                    signal["entity_key"]
                    for signal in current["signals"]
                    if signal["signal_key"] == value["signal_key"]
                ),
            }
            for position, value in enumerate(current["values"])
        ],
    )
    store.connection.execute(
        "UPDATE time_series_sets SET content_hash = ? WHERE id = ?",
        (content_hash, set_id),
    )
    store.connection.execute(
        """
        UPDATE time_series_set_revisions SET content_hash = ?
        WHERE time_series_set_id = ? AND revision_number = (
            SELECT MAX(revision_number) FROM time_series_set_revisions
            WHERE time_series_set_id = ?
        )
        """,
        (content_hash, set_id, set_id),
    )
    store.connection.commit()
    return content_hash


class C2CatalogAndObjectBackfillTests(unittest.TestCase):
    def setUp(self):
        self.store = AnalystStore("sqlite:///:memory:")
        self.project = self.store.create_project(name="Cuenca Norte")
        self.recovery = tempfile.TemporaryDirectory()
        self.store.take_c0_recovery_point(
            actor="internal_admin", copy_directory=Path(self.recovery.name)
        )

    def tearDown(self):
        self.store.close()
        self.recovery.cleanup()

    def test_c2_materializes_project_objects_and_converges_with_the_same_manifest(self):
        first = self.store.backfill_time_series_c2(actor="internal_admin")
        second = self.store.backfill_time_series_c2(actor="internal_admin")

        objects = self.store.list_linkable_objects(project_id=self.project["id"])
        self.assertEqual(
            {
                "statuses": [first["status"], second["status"]],
                "object_kinds": [item["object_kind"] for item in objects],
                "same_manifest": first["manifest"] == second["manifest"],
                "second_created_rows": second["created_rows"],
                "second_mapping_changes": second["mapping_changes"],
                "technical_actor": objects[0]["created_by"],
            },
            {
                "statuses": ["proven", "proven"],
                "object_kinds": ["global_signal_slot"],
                "same_manifest": True,
                "second_created_rows": 0,
                "second_mapping_changes": 0,
                "technical_actor": f"system:migration:{first['migration_run_id']}",
            },
        )

    def test_c2_records_an_ambiguous_component_and_invents_no_object(self):
        scenario = self.store.create_scenario(
            project_id=self.project["id"], name="Base"
        )
        for component_type in ("renewable", "load"):
            self.store.create_scenario_version(
                scenario_id=scenario["id"],
                system_case_json=system_case(
                    [
                        {"id": "bus_1", "type": "bus"},
                        {"id": "grid_1", "type": "grid"},
                        {"id": "asset_1", "type": component_type},
                    ]
                ),
                validation_payload={"ok": True},
            )

        with self.assertRaises(MigrationPhaseStopped) as stopped:
            self.store.backfill_time_series_c2(actor="internal_admin")

        anomalies = self.store.read_migration_anomalies(
            stopped.exception.migration_run_id
        )
        self.assertEqual(
            {
                "code": stopped.exception.code,
                "anomaly_codes": [item["code"] for item in anomalies],
                "finding": anomalies[0]["evidence"],
                "registered": self.store.list_linkable_objects(
                    project_id=self.project["id"]
                ),
            },
            {
                "code": "TS_MIGRATION_C2_STOPPED",
                "anomaly_codes": ["TS_MIGRATION_OBJECT_AMBIGUOUS"],
                "finding": {
                    "component_key": "asset_1",
                    "component_types": ["load", "renewable"],
                    "project_id": self.project["id"],
                    "reason": "component_type_conflict",
                },
                "registered": [],
            },
        )

    def test_c2_never_creates_a_component_from_a_plausible_entity_string(self):
        scenario = self.store.create_scenario(
            project_id=self.project["id"], name="Base"
        )
        legacy = import_legacy_set(self.store, scenario["id"])
        self.store.connection.execute(
            """
            UPDATE time_series_signals
            SET entity_type = 'component:load', entity_key = 'looks_real'
            WHERE time_series_set_id = ?
            """,
            (legacy["id"],),
        )
        self.store.connection.commit()
        refresh_legacy_hash(self.store, self.project["id"], legacy["id"])
        self.store.take_c0_recovery_point(
            actor="internal_admin",
            copy_directory=Path(self.recovery.name) / "plausible-string",
        )

        self.store.backfill_time_series_c2(actor="internal_admin")

        objects = self.store.list_linkable_objects(project_id=self.project["id"])
        self.assertEqual(
            [(item["object_kind"], item["object_key"]) for item in objects],
            [("global_signal_slot", "system")],
        )


class C3CanonicalContentBackfillTests(unittest.TestCase):
    def setUp(self):
        self.store = AnalystStore("sqlite:///:memory:")
        self.project = self.store.create_project(name="Cuenca Norte")
        self.scenario = self.store.create_scenario(
            project_id=self.project["id"], name="Base"
        )
        self.legacy = import_legacy_set(self.store, self.scenario["id"])
        self.recovery = tempfile.TemporaryDirectory()
        self.store.take_c0_recovery_point(
            actor="internal_admin", copy_directory=Path(self.recovery.name)
        )
        self.store.backfill_time_series_c2(actor="internal_admin")

    def tearDown(self):
        self.store.close()
        self.recovery.cleanup()

    def test_c3_seals_a_verified_snapshot_and_a_second_run_is_unchanged(self):
        legacy_revision = self.store.connection.execute(
            """
            SELECT * FROM time_series_set_revisions
            WHERE time_series_set_id = ? ORDER BY revision_number DESC
            """,
            (self.legacy["id"],),
        ).fetchone()

        first = self.store.backfill_time_series_c3(actor="internal_admin")
        second = self.store.backfill_time_series_c3(actor="internal_admin")
        canonical_set = self.store.read_canonical_set(self.legacy["id"])
        canonical_revision = self.store.read_canonical_revision(
            int(canonical_set["current_revision_id"])
        )

        self.assertEqual(
            {
                "statuses": [first["status"], second["status"]],
                "same_manifest": first["manifest"] == second["manifest"],
                "second_created_rows": second["created_rows"],
                "second_mapping_changes": second["mapping_changes"],
                "set_identity": canonical_set["id"],
                "set_owner": canonical_set["owner_project_id"],
                "set_scope": canonical_set["visibility_scope"],
                "set_kind": canonical_set["series_kind"],
                "set_created_by": canonical_set["created_by"],
                "revision_identity": canonical_revision["id"],
                "revision_state": canonical_revision["state"],
                "legacy_hash": canonical_revision["legacy_content_hash"],
                "canonical_hash": canonical_revision["content_hash"],
                "signal_keys": [
                    item["series_key"] for item in canonical_revision["signals"]
                ],
                "counts": (
                    len(canonical_revision["signals"]),
                    len(canonical_revision["periods"]),
                    canonical_revision["value_count"],
                ),
            },
            {
                "statuses": ["proven", "proven"],
                "same_manifest": True,
                "second_created_rows": 0,
                "second_mapping_changes": 0,
                "set_identity": self.legacy["id"],
                "set_owner": self.project["id"],
                "set_scope": "project",
                "set_kind": "catalog",
                "set_created_by": "legacy_analyst",
                "revision_identity": int(legacy_revision["id"]),
                "revision_state": "sealed",
                "legacy_hash": str(legacy_revision["content_hash"]),
                "canonical_hash": canonical_set["content_hash"],
                "signal_keys": ["load_demand_mw"],
                "counts": (1, 4, 4),
            },
        )

    def test_unknown_classification_is_quarantined_until_an_admin_decides(self):
        self.store.connection.execute(
            """
            UPDATE time_series_signals
            SET signal_key = 'vendor_load', unit = 'widgets'
            WHERE time_series_set_id = ?
            """,
            (self.legacy["id"],),
        )
        self.store.connection.commit()
        refresh_legacy_hash(self.store, self.project["id"], self.legacy["id"])
        self.store.take_c0_recovery_point(
            actor="internal_admin", copy_directory=Path(self.recovery.name) / "unknown"
        )
        self.store.backfill_time_series_c2(actor="internal_admin")

        with self.assertRaises(MigrationPhaseStopped) as stopped:
            self.store.backfill_time_series_c3(actor="internal_admin")

        anomalies = self.store.read_migration_anomalies(
            stopped.exception.migration_run_id
        )
        semantic_type = self.store.connection.execute(
            """
            SELECT id FROM time_series_semantic_types
            WHERE semantic_key = 'vendor_load'
            """
        ).fetchone()
        quarantined = self.store.read_canonical_set(self.legacy["id"])
        legacy_value_count = self.store.connection.execute(
            "SELECT COUNT(*) AS total FROM time_series_values WHERE time_series_set_id = ?",
            (self.legacy["id"],),
        ).fetchone()["total"]

        self.assertEqual(
            {
                "stop_code": stopped.exception.code,
                "anomaly_codes": [item["code"] for item in anomalies],
                "resolution": [item["resolution"] for item in anomalies],
                "invented_type": semantic_type,
                "canonical_state": (
                    quarantined["status"], quarantined["current_revision_id"]
                ),
                "legacy_values_preserved": legacy_value_count,
            },
            {
                "stop_code": "TS_MIGRATION_C3_STOPPED",
                "anomaly_codes": ["TS_MIGRATION_UNKNOWN_SEMANTIC_TYPE"],
                "resolution": ["open"],
                "invented_type": None,
                "canonical_state": ("draft", None),
                "legacy_values_preserved": 4,
            },
        )

        decision = self.store.resolve_time_series_migration_classification(
            anomaly_id=anomalies[0]["id"],
            semantic_type_key="load_demand",
            unit_key="mw",
            data_class_key="real",
            actor="internal_admin",
            reason="Proveedor confirmó demanda activa expresada en MW.",
        )
        completed = self.store.backfill_time_series_c3(actor="internal_admin")
        resolved = self.store.read_migration_anomalies(
            stopped.exception.migration_run_id
        )[0]
        revision = self.store.read_canonical_revision(
            self.store.read_canonical_set(self.legacy["id"])["current_revision_id"]
        )
        self.assertEqual(
            {
                "decision": decision["status"],
                "completed": completed["status"],
                "resolution": resolved["resolution"],
                "resolved_by": resolved["resolved_by"],
                "resolution_note": resolved["resolution_note"],
                "semantic_type": revision["signals"][0]["semantic_type_key"],
                "unit": revision["signals"][0]["unit_key"],
            },
            {
                "decision": "recorded",
                "completed": "proven",
                "resolution": "resolved",
                "resolved_by": "internal_admin",
                "resolution_note": "Proveedor confirmó demanda activa expresada en MW.",
                "semantic_type": "load_demand",
                "unit": "mw",
            },
        )

    def test_an_unknown_unit_never_creates_a_conversion_or_a_unit(self):
        self.store.connection.execute(
            "UPDATE time_series_signals SET unit = 'widgets' WHERE time_series_set_id = ?",
            (self.legacy["id"],),
        )
        self.store.connection.commit()
        refresh_legacy_hash(self.store, self.project["id"], self.legacy["id"])
        self.store.take_c0_recovery_point(
            actor="internal_admin", copy_directory=Path(self.recovery.name) / "unit"
        )
        self.store.backfill_time_series_c2(actor="internal_admin")

        with self.assertRaises(MigrationPhaseStopped) as stopped:
            self.store.backfill_time_series_c3(actor="internal_admin")

        anomaly = self.store.read_migration_anomalies(
            stopped.exception.migration_run_id
        )[0]
        invented = self.store.connection.execute(
            "SELECT id FROM measurement_units WHERE symbol = 'widgets'"
        ).fetchone()
        self.assertEqual(
            (anomaly["code"], invented),
            ("TS_MIGRATION_UNKNOWN_UNIT", None),
        )

    def test_an_unknown_data_class_never_creates_a_semantic_placeholder(self):
        self.store.connection.execute(
            "UPDATE time_series_sets SET data_kind = 'vendor_class' WHERE id = ?",
            (self.legacy["id"],),
        )
        self.store.connection.commit()
        refresh_legacy_hash(self.store, self.project["id"], self.legacy["id"])
        self.store.take_c0_recovery_point(
            actor="internal_admin", copy_directory=Path(self.recovery.name) / "class"
        )
        self.store.backfill_time_series_c2(actor="internal_admin")

        with self.assertRaises(MigrationPhaseStopped) as stopped:
            self.store.backfill_time_series_c3(actor="internal_admin")

        anomaly = self.store.read_migration_anomalies(
            stopped.exception.migration_run_id
        )[0]
        invented = self.store.connection.execute(
            """
            SELECT id FROM time_series_data_classes
            WHERE data_class_key = 'vendor_class'
            """
        ).fetchone()
        self.assertEqual(
            (anomaly["code"], anomaly["evidence"]["data_class"], invented),
            ("TS_MIGRATION_UNKNOWN_SEMANTIC_TYPE", "vendor_class", None),
        )

    def test_duplicate_series_keys_quarantine_the_set_instead_of_merging_rows(self):
        self.store.connection.execute(
            """
            INSERT INTO time_series_signals (
                time_series_set_id, signal_key, unit, entity_type, entity_key,
                signal_role, aggregation, created_at, source_column, source_unit
            ) VALUES (?, 'load_demand_mw', 'MW', NULL, NULL, 'input',
                      'period_average', '2026-01-01T00:00:00+00:00', '', 'MW')
            """,
            (self.legacy["id"],),
        )
        self.store.connection.commit()
        refresh_legacy_hash(self.store, self.project["id"], self.legacy["id"])
        finding_key = (
            f"duplicate_series_key:set={self.legacy['id']}:"
            "series_key=load_demand_mw"
        )
        self.store.take_c0_recovery_point(
            actor="internal_admin",
            copy_directory=Path(self.recovery.name) / "duplicate",
            explanations={finding_key: "Dos filas heredadas; C3 debe aislar el set."},
        )
        self.store.backfill_time_series_c2(actor="internal_admin")

        with self.assertRaises(MigrationPhaseStopped) as stopped:
            self.store.backfill_time_series_c3(actor="internal_admin")

        anomalies = self.store.read_migration_anomalies(
            stopped.exception.migration_run_id
        )
        quarantined = self.store.read_canonical_set(self.legacy["id"])
        canonical_signal_count = self.store.connection.execute(
            """
            SELECT COUNT(*) AS total FROM time_series_signals_next
            WHERE time_series_set_id = ?
            """,
            (self.legacy["id"],),
        ).fetchone()["total"]
        self.assertEqual(
            {
                "code": anomalies[0]["code"],
                "series_keys": anomalies[0]["evidence"]["series_keys"],
                "status": quarantined["status"],
                "pointer": quarantined["current_revision_id"],
                "canonical_signal_count": canonical_signal_count,
            },
            {
                "code": "TS_MIGRATION_DUPLICATE_SERIES_KEY",
                "series_keys": ["load_demand_mw"],
                "status": "draft",
                "pointer": None,
                "canonical_signal_count": 0,
            },
        )

    def test_legacy_revision_events_stay_unmaterialized_and_never_gain_children(self):
        self.store.edit_time_series_set_values(
            project_id=self.project["id"],
            time_series_set_id=self.legacy["id"],
            edits=[
                CatalogValueEdit(
                    period_index=0, signal_key="load_demand_mw", value_text="125"
                )
            ],
            created_by="legacy_editor",
        )
        legacy_revisions = self.store.connection.execute(
            """
            SELECT id, revision_number FROM time_series_set_revisions
            WHERE time_series_set_id = ? ORDER BY revision_number
            """,
            (self.legacy["id"],),
        ).fetchall()
        self.store.take_c0_recovery_point(
            actor="internal_admin", copy_directory=Path(self.recovery.name) / "history"
        )
        self.store.backfill_time_series_c2(actor="internal_admin")

        self.store.backfill_time_series_c3(actor="internal_admin")

        revisions = [
            self.store.read_canonical_revision(int(row["id"]))
            for row in legacy_revisions
        ]
        canonical_set = self.store.read_canonical_set(self.legacy["id"])
        baseline = self.store.read_canonical_revision(
            int(canonical_set["current_revision_id"])
        )
        self.assertEqual(
            {
                "ids": [item["id"] for item in revisions],
                "states": [item["state"] for item in revisions],
                "supersedes": [item["supersedes_revision_id"] for item in revisions],
                "historical_children": (
                    revisions[0]["signal_count"],
                    revisions[0]["period_count"],
                    revisions[0]["value_count"],
                ),
                "second_historical_children": (
                    revisions[1]["signal_count"],
                    revisions[1]["period_count"],
                    revisions[1]["value_count"],
                ),
                "baseline": (
                    baseline["id"],
                    baseline["revision_number"],
                    baseline["state"],
                    baseline["change_summary"],
                    baseline["supersedes_revision_id"],
                ),
            },
            {
                "ids": [int(row["id"]) for row in legacy_revisions],
                "states": ["legacy_unmaterialized", "legacy_unmaterialized"],
                "supersedes": [None, int(legacy_revisions[0]["id"])],
                "historical_children": (0, 0, 0),
                "second_historical_children": (0, 0, 0),
                "baseline": (
                    max(int(row["id"]) for row in legacy_revisions) + 1,
                    3,
                    "sealed",
                    "migration_baseline",
                    int(legacy_revisions[1]["id"]),
                ),
            },
        )

    def test_an_unmaterialized_revision_is_never_pinnable_nor_previewable(self):
        self.store.create_scenario_version(
            scenario_id=self.scenario["id"],
            system_case_json=system_case(
                [
                    {"id": "bus_1", "type": "bus"},
                    {"id": "grid_1", "type": "grid"},
                    {"id": "load_1", "type": "load"},
                ]
            ),
            validation_payload={"ok": True},
        )
        self.store.edit_time_series_set_values(
            project_id=self.project["id"],
            time_series_set_id=self.legacy["id"],
            edits=[
                CatalogValueEdit(
                    period_index=0, signal_key="load_demand_mw", value_text="125"
                )
            ],
            created_by="legacy_editor",
        )
        unmaterialized_id = int(
            self.store.connection.execute(
                """
                SELECT MAX(id) AS id FROM time_series_set_revisions
                WHERE time_series_set_id = ?
                """,
                (self.legacy["id"],),
            ).fetchone()["id"]
        )
        self.store.take_c0_recovery_point(
            actor="internal_admin",
            copy_directory=Path(self.recovery.name) / "never-executable",
        )
        self.store.backfill_time_series_c2(actor="internal_admin")
        self.store.backfill_time_series_c3(actor="internal_admin")

        canonical_set = self.store.read_canonical_set(self.legacy["id"])
        sealed_id = int(canonical_set["current_revision_id"])
        sealed_revision = self.store.read_canonical_revision(sealed_id)
        unmaterialized = self.store.read_canonical_revision(unmaterialized_id)
        signal_id = int(sealed_revision["signals"][0]["signal_id"])
        load_object = next(
            item
            for item in self.store.list_linkable_objects(project_id=self.project["id"])
            if item["object_type_key"] == "component:load"
        )
        case = self.store.get_or_create_case_for_scenario(self.scenario["id"])
        variant = self.store.get_or_create_default_input_variant(case["id"])

        def prevalidate(*, revision_id, mode, content_hash):
            return self.store.prevalidate_case_binding_batch(
                scenario_id=self.scenario["id"],
                variant_id=variant["id"],
                document={
                    "expected_bindings_revision": 0,
                    "operations": [
                        {
                            "client_operation_id": "bind-load-demand",
                            "action": "create",
                            "linkable_object_id": load_object["id"],
                            "binding_role_key": "load_demand",
                            "signal_id": signal_id,
                            "revision": {
                                "mode": mode,
                                "revision_id": revision_id,
                                "content_hash": content_hash,
                            },
                            "catalog_association_id": None,
                            "reason_code": "variant_input_selected",
                            "reason_text": "Historia heredada sin datos.",
                        }
                    ],
                },
                actor_class="analyst:1",
            )["operations"][0]

        sealed = prevalidate(
            revision_id=sealed_id,
            mode="current",
            content_hash=str(sealed_revision["content_hash"]),
        )
        pinned = prevalidate(
            revision_id=unmaterialized_id,
            mode="pinned",
            content_hash=str(unmaterialized["legacy_content_hash"]),
        )
        with self.assertRaises(CatalogQueryError) as preview:
            self.store.read_catalog_input_preview(
                signal_id,
                revision_id=unmaterialized_id,
                range_from="2026-01-01T00:00:00",
                range_to="2026-01-02T00:00:00",
                sampling="none",
                max_points=500,
            )

        self.assertEqual(
            {
                "unmaterialized_state": unmaterialized["state"],
                "sealed_verdict": sealed["verdict"],
                "pinned_verdict": pinned["verdict"],
                "pinned_error": pinned["compatibility_decision"]["primary_error"][
                    "code"
                ],
                "preview_error": preview.exception.code,
            },
            {
                "unmaterialized_state": "legacy_unmaterialized",
                "sealed_verdict": "accepted",
                "pinned_verdict": "rejected",
                "pinned_error": "TS_COMPAT_SIGNAL_UNAVAILABLE",
                "preview_error": "TS_PREVIEW_REVISION_UNAVAILABLE",
            },
        )

    def test_a_consumed_hash_mismatch_blocks_instead_of_baselining_silently(self):
        case = self.store.get_or_create_case_for_scenario(self.scenario["id"])
        variant = self.store.get_or_create_default_input_variant(case["id"])
        self.store.upsert_case_time_series_binding(
            case_input_variant_id=variant["id"],
            signal_key="load_demand_mw",
            entity_type="component:load",
            entity_id="load_1",
            time_series_set_id=self.legacy["id"],
            created_by="legacy_analyst",
        )
        self.store.edit_time_series_set_values(
            project_id=self.project["id"],
            time_series_set_id=self.legacy["id"],
            edits=[
                CatalogValueEdit(
                    period_index=0, signal_key="load_demand_mw", value_text="125"
                )
            ],
            created_by="legacy_editor",
        )
        self.store.take_c0_recovery_point(
            actor="internal_admin",
            copy_directory=Path(self.recovery.name) / "consumed-mismatch",
        )
        self.store.backfill_time_series_c2(actor="internal_admin")

        with self.assertRaises(MigrationPhaseStopped) as stopped:
            self.store.backfill_time_series_c3(actor="internal_admin")

        anomaly = self.store.read_migration_anomalies(
            stopped.exception.migration_run_id
        )[0]
        quarantined = self.store.read_canonical_set(self.legacy["id"])
        self.assertEqual(
            {
                "code": anomaly["code"],
                "severity": anomaly["severity"],
                "pointer": quarantined["current_revision_id"],
            },
            {
                "code": "TS_MIGRATION_HASH_MISMATCH",
                "severity": "blocking",
                "pointer": None,
            },
        )

    def test_an_incomplete_snapshot_rolls_back_every_child_before_the_pointer(self):
        self.store.connection.execute(
            """
            DELETE FROM time_series_values WHERE id = (
                SELECT MIN(id) FROM time_series_values
                WHERE time_series_set_id = ?
            )
            """,
            (self.legacy["id"],),
        )
        self.store.connection.commit()
        refresh_legacy_hash(self.store, self.project["id"], self.legacy["id"])
        self.store.take_c0_recovery_point(
            actor="internal_admin",
            copy_directory=Path(self.recovery.name) / "incomplete",
        )
        self.store.backfill_time_series_c2(actor="internal_admin")

        with self.assertRaises(MigrationPhaseStopped) as stopped:
            self.store.backfill_time_series_c3(actor="internal_admin")

        anomaly = self.store.read_migration_anomalies(
            stopped.exception.migration_run_id
        )[0]
        canonical = self.store.read_canonical_set(self.legacy["id"])
        tables = self.store.canonical_table_names()
        child_counts = {
            logical: self.store.connection.execute(
                f"SELECT COUNT(*) AS total FROM {tables[logical]}"
            ).fetchone()["total"]
            for logical in (
                "time_series_signals",
                "time_series_set_revisions",
                "time_series_revision_signals",
                "time_series_periods",
                "time_series_values",
            )
        }
        self.assertEqual(
            {
                "code": anomaly["code"],
                "pointer": canonical["current_revision_id"],
                "child_counts": child_counts,
            },
            {
                "code": "TS_MIGRATION_HASH_MISMATCH",
                "pointer": None,
                "child_counts": {
                    "time_series_signals": 0,
                    "time_series_set_revisions": 0,
                    "time_series_revision_signals": 0,
                    "time_series_periods": 0,
                    "time_series_values": 0,
                },
            },
        )

    def test_proven_local_provenance_stays_object_specific_and_out_of_the_catalog(self):
        self.store.create_scenario_version(
            scenario_id=self.scenario["id"],
            system_case_json=system_case(
                [
                    {"id": "bus_1", "type": "bus"},
                    {"id": "grid_1", "type": "grid"},
                    {"id": "load_1", "type": "load"},
                ]
            ),
            validation_payload={"ok": True},
        )
        self.store.connection.execute(
            """
            UPDATE time_series_sets
            SET name = 'load_demand_mw', version_label = 'object'
            WHERE id = ?
            """,
            (self.legacy["id"],),
        )
        self.store.connection.execute(
            """
            UPDATE time_series_signals
            SET entity_type = 'component:load', entity_key = 'load_1'
            WHERE time_series_set_id = ?
            """,
            (self.legacy["id"],),
        )
        provenance = (
            '{"provenance":{"kind":"object_specific_definition",'
            '"entity_type":"component:load","entity_key":"load_1"}}'
        )
        self.store.connection.execute(
            """
            UPDATE time_series_set_revisions SET metadata_json = ?
            WHERE time_series_set_id = ?
            """,
            (provenance, self.legacy["id"]),
        )
        self.store.connection.commit()
        refresh_legacy_hash(self.store, self.project["id"], self.legacy["id"])
        self.store.take_c0_recovery_point(
            actor="internal_admin", copy_directory=Path(self.recovery.name) / "local"
        )
        self.store.backfill_time_series_c2(actor="internal_admin")
        owner = next(
            item
            for item in self.store.list_linkable_objects(project_id=self.project["id"])
            if item["object_key"] == "load_1"
        )

        result = self.store.backfill_time_series_c3(actor="internal_admin")

        canonical = self.store.read_canonical_set(self.legacy["id"])
        tables = self.store.canonical_table_names()
        catalog_count = self.store.connection.execute(
            f"""
            SELECT COUNT(*) AS total FROM {tables['time_series_signals']} AS signal
            JOIN {tables['time_series_sets']} AS the_set
              ON the_set.id = signal.time_series_set_id
            WHERE the_set.series_kind = 'catalog'
            """
        ).fetchone()["total"]
        local_count = self.store.connection.execute(
            f"""
            SELECT COUNT(*) AS total FROM {tables['time_series_signals']} AS signal
            JOIN {tables['time_series_sets']} AS the_set
              ON the_set.id = signal.time_series_set_id
            WHERE the_set.series_kind = 'object_specific'
            """
        ).fetchone()["total"]
        self.assertEqual(
            {
                "status": result["status"],
                "kind": canonical["series_kind"],
                "owner": canonical["owner_linkable_object_id"],
                "object_key": canonical["object_series_key"],
                "specific_signal": canonical["object_specific_signal_id"],
                "catalog_count": catalog_count,
                "local_count": local_count,
            },
            {
                "status": "proven",
                "kind": "object_specific",
                "owner": owner["id"],
                "object_key": "load_demand_mw",
                "specific_signal": self.store.read_canonical_revision(
                    canonical["current_revision_id"]
                )["signals"][0]["signal_id"],
                "catalog_count": 0,
                "local_count": 1,
            },
        )

    def test_a_local_looking_set_without_provenance_requires_review(self):
        self.store.create_scenario_version(
            scenario_id=self.scenario["id"],
            system_case_json=system_case(
                [
                    {"id": "bus_1", "type": "bus"},
                    {"id": "grid_1", "type": "grid"},
                    {"id": "load_1", "type": "load"},
                ]
            ),
            validation_payload={"ok": True},
        )
        self.store.connection.execute(
            """
            UPDATE time_series_signals SET entity_key = 'load_1'
            WHERE time_series_set_id = ?
            """,
            (self.legacy["id"],),
        )
        self.store.connection.commit()
        refresh_legacy_hash(self.store, self.project["id"], self.legacy["id"])
        self.store.take_c0_recovery_point(
            actor="internal_admin", copy_directory=Path(self.recovery.name) / "review"
        )
        self.store.backfill_time_series_c2(actor="internal_admin")

        with self.assertRaises(MigrationPhaseStopped) as stopped:
            self.store.backfill_time_series_c3(actor="internal_admin")

        anomaly = self.store.read_migration_anomalies(
            stopped.exception.migration_run_id
        )[0]
        quarantined = self.store.read_canonical_set(self.legacy["id"])
        self.assertEqual(
            {
                "code": anomaly["code"],
                "reason": anomaly["evidence"]["reason"],
                "kind": quarantined["series_kind"],
                "status": quarantined["status"],
                "pointer": quarantined["current_revision_id"],
            },
            {
                "code": "TS_MIGRATION_OBJECT_SPECIFIC_REVIEW_REQUIRED",
                "reason": "explicit_local_provenance_missing",
                "kind": "catalog",
                "status": "draft",
                "pointer": None,
            },
        )

    def test_c3_resumes_from_its_checkpoint_and_finishes_with_global_evidence(self):
        second_legacy = import_legacy_set(
            self.store,
            self.scenario["id"],
            name="Demanda Sur",
            periods=2,
        )
        self.store.take_c0_recovery_point(
            actor="internal_admin", copy_directory=Path(self.recovery.name) / "resume"
        )
        self.store.backfill_time_series_c2(actor="internal_admin")

        first_batch = self.store.backfill_time_series_c3(
            actor="internal_admin", batch_size=1
        )
        first_set = self.store.read_canonical_set(self.legacy["id"])
        with self.assertRaises(CanonicalRevisionError):
            self.store.read_canonical_set(second_legacy["id"])

        final_batch = self.store.backfill_time_series_c3(
            actor="internal_admin",
            migration_run_id=first_batch["migration_run_id"],
            batch_size=1,
        )
        repeated = self.store.backfill_time_series_c3(actor="internal_admin")

        self.assertEqual(
            {
                "first_status": first_batch["status"],
                "first_checkpoint": first_batch["checkpoint"],
                "first_pointer": bool(first_set["current_revision_id"]),
                "final_status": final_batch["status"],
                "same_run": (
                    first_batch["migration_run_id"]
                    == final_batch["migration_run_id"]
                ),
                "set_ids": [item["set_id"] for item in final_batch["manifest"]["sets"]],
                "same_manifest": final_batch["manifest"] == repeated["manifest"],
                "repeat_created_rows": repeated["created_rows"],
                "repeat_mapping_changes": repeated["mapping_changes"],
            },
            {
                "first_status": "running",
                "first_checkpoint": {"last_set_id": self.legacy["id"]},
                "first_pointer": True,
                "final_status": "proven",
                "same_run": True,
                "set_ids": [self.legacy["id"], second_legacy["id"]],
                "same_manifest": True,
                "repeat_created_rows": 0,
                "repeat_mapping_changes": 0,
            },
        )

    def test_deleted_legacy_ids_remain_holes_and_are_never_reassigned(self):
        deleted = self.legacy
        self.store.connection.execute(
            "DELETE FROM time_series_sets WHERE id = ?", (deleted["id"],)
        )
        self.store.connection.commit()
        surviving = import_legacy_set(
            self.store, self.scenario["id"], name="Demanda posterior", periods=2
        )
        self.store.take_c0_recovery_point(
            actor="internal_admin", copy_directory=Path(self.recovery.name) / "id-holes"
        )
        self.store.backfill_time_series_c2(actor="internal_admin")

        self.store.backfill_time_series_c3(actor="internal_admin")

        tables = self.store.canonical_table_names()
        set_ids = [
            int(row["id"])
            for row in self.store.connection.execute(
                f"SELECT id FROM {tables['time_series_sets']} ORDER BY id"
            ).fetchall()
        ]
        self.assertEqual(set_ids, [surviving["id"]])
        self.assertNotIn(deleted["id"], set_ids)

    def test_a_preexisting_canonical_id_is_never_reassigned_to_a_legacy_set(self):
        existing = self.store.publish_canonical_set_revision(
            project_id=self.project["id"],
            name="Preexisting canonical",
            signals=[
                {
                    "series_key": "load_demand_mw",
                    "semantic_type_key": "load_demand",
                    "unit_key": "mw",
                    "signal_role": "input",
                    "aggregation": "mean",
                }
            ],
            periods=[
                {
                    "period_index": 0,
                    "timestamp_start": "2026-01-01T00:00:00+00:00",
                    "timestamp_end": "2026-01-01T01:00:00+00:00",
                    "duration_hours": 1.0,
                }
            ],
            values=[
                {
                    "series_key": "load_demand_mw",
                    "period_index": 0,
                    "value": 7.0,
                }
            ],
            data_class_key="real",
            actor="verification_account",
        )
        self.assertEqual(existing["set_id"], self.legacy["id"])

        with self.assertRaises(MigrationPhaseStopped) as stopped:
            self.store.backfill_time_series_c3(actor="internal_admin")

        anomaly = self.store.read_migration_anomalies(
            stopped.exception.migration_run_id
        )[0]
        canonical = self.store.read_canonical_set(existing["set_id"])
        self.assertEqual(
            {
                "code": anomaly["code"],
                "reason": anomaly["evidence"]["reason"],
                "canonical_name": canonical["name"],
                "canonical_actor": canonical["created_by"],
            },
            {
                "code": "TS_MIGRATION_MAPPING_CONFLICT",
                "reason": "canonical_set_id_already_assigned",
                "canonical_name": "Preexisting canonical",
                "canonical_actor": "verification_account",
            },
        )


@unittest.skipUnless(
    POSTGRES_TEST_DATABASE_URL,
    "POSTGRES_TEST_DATABASE_URL is required for PostgreSQL integration tests",
)
class PostgresC2C3BackfillTests(unittest.TestCase):
    def setUp(self):
        self.store = AnalystStore(POSTGRES_TEST_DATABASE_URL)
        self.rollback = self.store.connection._connection.transaction(  # noqa: SLF001
            force_rollback=True
        )
        self.rollback.__enter__()
        suffix = uuid.uuid4().hex[:12]
        self.project = self.store.create_project(name=f"TS7-016 {suffix}")
        self.scenario = self.store.create_scenario(
            project_id=self.project["id"], name=f"Base {suffix}"
        )
        self.legacy = import_legacy_set(
            self.store, self.scenario["id"], name=f"Demanda {suffix}", periods=2
        )
        self.recovery = tempfile.TemporaryDirectory()

    def tearDown(self):
        try:
            self.recovery.cleanup()
            self.rollback.__exit__(None, None, None)
        finally:
            self.store.close()

    def prove_recovery_point(self):
        """Explain what the development source already carries, then prove C0.

        The mirror is about the second engine, not about legacy rows this
        slice does not own: the development database keeps bindings whose
        signal no longer resolves in its set, and C0 refuses to sign a
        manifest that passes over them in silence.  Explaining exactly what it
        reports is the operator gesture the phase asks for, and it keeps the
        refusal itself proven on PostgreSQL.
        """

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

    def test_postgresql_preserves_ids_and_converges_like_sqlite(self):
        recovery = self.prove_recovery_point()
        c2 = self.store.backfill_time_series_c2(actor="internal_admin")
        first = self.store.backfill_time_series_c3(actor="internal_admin")
        repeated = self.store.backfill_time_series_c3(actor="internal_admin")

        canonical = self.store.read_canonical_set(self.legacy["id"])
        self.assertEqual(
            {
                "c0_signed": bool(recovery["manifest_signature"]),
                "c2": c2["status"],
                "c3": first["status"],
                "set_id": canonical["id"],
                "owner": canonical["owner_project_id"],
                "scope": canonical["visibility_scope"],
                "same_manifest": first["manifest"] == repeated["manifest"],
                "repeat_created_rows": repeated["created_rows"],
                "repeat_mapping_changes": repeated["mapping_changes"],
            },
            {
                "c0_signed": True,
                "c2": "proven",
                "c3": "proven",
                "set_id": self.legacy["id"],
                "owner": self.project["id"],
                "scope": "project",
                "same_manifest": True,
                "repeat_created_rows": 0,
                "repeat_mapping_changes": 0,
            },
        )

if __name__ == "__main__":
    unittest.main()
