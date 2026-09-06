"""TS7-022 single-writer cutover contracts.

The seams under test are the store's public C6 operation and the HTTP aliases
that must keep their old shape while delegating to the canonical model.
"""

import tempfile
import unittest
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from app.auth import hash_password
from app.persistence import AnalystStore
from app.time_series_catalog import (
    CatalogImportRequest,
    CatalogSignalMappingRequest,
    prepare_time_series_catalog_import,
)
from app.time_series_migration import (
    LEGACY_WRITE_PROTECTED_TABLES,
    MigrationControlError,
    MigrationPhaseStopped,
    legacy_write_guard_name,
    legacy_write_protection_script,
)
from tests.auth_test_helpers import login_json_with_csrf


def import_legacy_price_set(store: AnalystStore, scenario_id: int) -> dict:
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
            "id": "ts7-022-price",
            "original_filename": "price.csv",
            "media_type": "text/csv",
            "checksum": "sha256:ts7-022-price",
        },
        prepared_import=prepared,
        created_by="legacy_analyst",
    )


class C6CutoverStateTests(unittest.TestCase):
    def setUp(self):
        self.store = AnalystStore("sqlite:///:memory:")
        self.addCleanup(self.store.close)
        self.sources = tempfile.TemporaryDirectory()
        self.addCleanup(self.sources.cleanup)
        self.client = TestClient(
            create_app(
                store=self.store,
                auth_enabled=False,
                input_source_root=Path(self.sources.name),
            )
        )
        self.project = self.store.create_project(name="Cuenca Norte")
        self.scenario = self.store.create_scenario(
            project_id=self.project["id"], name="Base"
        )
        case = self.store.get_or_create_case_for_scenario(self.scenario["id"])
        variant = self.store.get_or_create_default_input_variant(case["id"])
        self.legacy_set = import_legacy_price_set(self.store, self.scenario["id"])
        self.store.upsert_case_time_series_binding(
            case_input_variant_id=variant["id"],
            signal_key="import_price_usd_per_mwh",
            time_series_set_id=self.legacy_set["id"],
            created_by="legacy_analyst",
        )
        self.recovery = tempfile.TemporaryDirectory()
        self.addCleanup(self.recovery.cleanup)

    def prove_c5(self) -> None:
        self.store.take_c0_recovery_point(
            actor="internal_admin", copy_directory=Path(self.recovery.name)
        )
        self.store.backfill_time_series_c2(actor="internal_admin")
        self.store.backfill_time_series_c3(actor="internal_admin")
        self.store.backfill_time_series_c4(actor="internal_admin")
        self.store.verify_time_series_c5_shadow(actor="internal_admin")

    def test_c6_is_irreversible_and_opens_the_single_writer_windows(self):
        with self.assertRaises(MigrationControlError) as refused:
            self.store.cut_over_time_series_c6(actor="internal_admin")
        self.assertEqual(refused.exception.code, "TS_MIGRATION_PHASE_REQUIRED")
        self.assertEqual(refused.exception.context["required_phase"], "C5")

        self.prove_c5()
        receipt = self.store.cut_over_time_series_c6(actor="internal_admin")

        self.assertEqual(receipt["status"], "proven")
        state = self.store.read_time_series_c6_state()
        self.assertTrue(state["cutover_active"])
        self.assertTrue(state["ts_next_canonical_read"])
        self.assertTrue(state["ts_next_canonical_write"])
        self.assertTrue(state["ts_legacy_aliases"])
        self.assertEqual(state["phase"], "C6")
        self.assertEqual(state["migration_run_id"], receipt["migration_run_id"])
        self.assertIsNone(self.store.read_legacy_mutation_pause())

        activated = datetime.fromisoformat(state["activated_at"])
        self.assertEqual(
            datetime.fromisoformat(state["observation_ends_at"]),
            activated + timedelta(hours=72),
        )
        self.assertEqual(
            datetime.fromisoformat(state["compatibility_reconciliation_ends_at"]),
            activated + timedelta(days=30),
        )
        self.assertEqual(
            datetime.fromisoformat(state["aliases_sunset_at"]),
            activated + timedelta(days=90),
        )

        repeated = self.store.cut_over_time_series_c6(actor="internal_admin")
        self.assertEqual(repeated, receipt)

    def test_c6_refuses_legacy_writes_in_code_and_in_the_database(self):
        self.prove_c5()
        self.store.cut_over_time_series_c6(actor="internal_admin")

        with self.assertRaises(MigrationControlError) as refused:
            import_legacy_price_set(self.store, self.scenario["id"])
        self.assertEqual(refused.exception.code, "TS_LEGACY_WRITE_FORBIDDEN")

        value_before = self.store.connection.execute(
            "SELECT value_numeric FROM time_series_values ORDER BY id LIMIT 1"
        ).fetchone()["value_numeric"]
        signal_before = self.store.connection.execute(
            "SELECT signal_key FROM time_series_signals ORDER BY id LIMIT 1"
        ).fetchone()["signal_key"]
        binding_before = self.store.connection.execute(
            "SELECT signal_key FROM case_time_series_bindings ORDER BY id LIMIT 1"
        ).fetchone()["signal_key"]

        direct_writes = (
            "UPDATE time_series_values SET value_numeric = 999",
            "UPDATE time_series_signals SET signal_key = 'tampered'",
            "UPDATE case_time_series_bindings SET signal_key = 'tampered'",
        )
        for statement in direct_writes:
            with self.subTest(statement=statement):
                with self.assertRaisesRegex(
                    sqlite3.IntegrityError, "TS_LEGACY_WRITE_FORBIDDEN"
                ):
                    self.store.connection.execute(statement)

        protection = self.store.read_legacy_write_protection()
        self.assertTrue(protection["code_guard_enabled"])
        self.assertTrue(protection["database_guard_enabled"])
        self.assertEqual(
            set(protection["required_tables"]),
            {
                "time_series_values",
                "time_series_signals",
                "case_time_series_bindings",
            },
        )
        self.assertEqual(
            self.store.connection.execute(
                "SELECT value_numeric FROM time_series_values ORDER BY id LIMIT 1"
            ).fetchone()["value_numeric"],
            value_before,
        )
        self.assertEqual(
            self.store.connection.execute(
                "SELECT signal_key FROM time_series_signals ORDER BY id LIMIT 1"
            ).fetchone()["signal_key"],
            signal_before,
        )
        self.assertEqual(
            self.store.connection.execute(
                "SELECT signal_key FROM case_time_series_bindings ORDER BY id LIMIT 1"
            ).fetchone()["signal_key"],
            binding_before,
        )

    def test_postgresql_cutover_script_revokes_and_guards_every_legacy_table(self):
        script = legacy_write_protection_script("postgresql")

        self.assertIn("CREATE OR REPLACE FUNCTION reject_legacy_time_series_write", script)
        self.assertIn("RAISE EXCEPTION 'TS_LEGACY_WRITE_FORBIDDEN'", script)
        for table_name in LEGACY_WRITE_PROTECTED_TABLES:
            with self.subTest(table_name=table_name):
                self.assertIn(
                    f"CREATE TRIGGER {legacy_write_guard_name(table_name)}", script
                )
                self.assertIn(
                    f"REVOKE INSERT, UPDATE, DELETE ON TABLE {table_name} FROM PUBLIC",
                    script,
                )

    def test_legacy_reads_keep_their_shape_as_canonical_aliases(self):
        set_root = f"/api/projects/{self.project['id']}/time-series-sets"
        routes = (
            "/api/time-series/signal-catalog",
            set_root,
            f"{set_root}/{self.legacy_set['id']}",
            f"{set_root}/{self.legacy_set['id']}/revisions",
        )
        before = {}
        for route in routes:
            response = self.client.get(route)
            self.assertEqual(response.status_code, 200, response.text)
            before[route] = response.json()

        self.prove_c5()
        state = self.store.cut_over_time_series_c6(actor="internal_admin")

        for route in routes:
            with self.subTest(route=route):
                response = self.client.get(route)
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(response.json(), before[route])
                self.assertEqual(response.headers["Deprecation"], "true")
                self.assertEqual(response.headers["X-Time-Series-Model"], "canonical")
                self.assertIn('rel="successor-version"', response.headers["Link"])
                self.assertIn("GMT", response.headers["Sunset"])
                self.assertEqual(
                    response.headers["X-Time-Series-Alias-Sunset"],
                    state["aliases_sunset_at"],
                )

    def test_legacy_value_edit_publishes_one_idempotent_canonical_revision(self):
        self.prove_c5()
        self.store.cut_over_time_series_c6(actor="internal_admin")
        route = (
            f"/api/projects/{self.project['id']}/time-series-sets/"
            f"{self.legacy_set['id']}/values"
        )
        detail_route = route.removesuffix("/values")
        legacy_value_before = self.store.connection.execute(
            "SELECT value_numeric FROM time_series_values ORDER BY id LIMIT 1"
        ).fetchone()["value_numeric"]

        missing_guards = self.client.put(
            route,
            json={
                "edits": [
                    {
                        "period_index": 0,
                        "signal_key": "import_price_usd_per_mwh",
                        "value": "99.0",
                    }
                ]
            },
        )
        self.assertEqual(missing_guards.status_code, 428, missing_guards.text)
        self.assertEqual(missing_guards.json()["code"], "TS_PRECONDITION_REQUIRED")

        detail = self.client.get(detail_route)
        etag = detail.headers["ETag"]
        payload = {
            "edits": [
                {
                    "period_index": 0,
                    "signal_key": "import_price_usd_per_mwh",
                    "value": "99.0",
                }
            ],
            "change_summary": "Correccion operativa",
        }
        headers = {"If-Match": etag, "Idempotency-Key": "edit-price-once"}
        changed = self.client.put(route, json=payload, headers=headers)
        self.assertEqual(changed.status_code, 200, changed.text)
        self.assertEqual(changed.headers["Deprecation"], "true")
        result = changed.json()["time_series_set"]
        self.assertEqual(result["revision_number"], 2)
        self.assertEqual(result["values"][0]["value_numeric"], 99.0)

        revisions_table = self.store._canonical("time_series_set_revisions")
        canonical_count = self.store.connection.execute(
            f"SELECT COUNT(*) AS total FROM {revisions_table} "
            "WHERE time_series_set_id = ?",
            (self.legacy_set["id"],),
        ).fetchone()["total"]
        replay = self.client.put(route, json=payload, headers=headers)
        self.assertEqual(replay.status_code, 200, replay.text)
        self.assertEqual(replay.json(), changed.json())
        self.assertEqual(
            self.store.connection.execute(
                f"SELECT COUNT(*) AS total FROM {revisions_table} "
                "WHERE time_series_set_id = ?",
                (self.legacy_set["id"],),
            ).fetchone()["total"],
            canonical_count,
        )
        self.assertEqual(
            self.store.connection.execute(
                "SELECT value_numeric FROM time_series_values ORDER BY id LIMIT 1"
            ).fetchone()["value_numeric"],
            legacy_value_before,
        )

    def test_c6_opens_canonical_surfaces_to_internal_users_but_never_external(self):
        for email, role in (
            ("analyst@example.local", "analyst"),
            ("client@example.local", "external"),
        ):
            self.store.create_user(
                email=email,
                display_name=email,
                role=role,
                password_hash=hash_password("secret pass"),
            )
        before_cutover = TestClient(create_app(store=self.store, auth_enabled=True))
        before_login = login_json_with_csrf(
            before_cutover, "analyst@example.local", "secret pass"
        )
        self.assertFalse(before_login.json()["ts_next_canonical_read"])
        self.assertFalse(
            before_cutover.get("/api/auth/me").json()["ts_next_canonical_read"]
        )
        self.prove_c5()
        self.store.cut_over_time_series_c6(actor="internal_admin")
        authenticated = TestClient(create_app(store=self.store, auth_enabled=True))

        internal_login = login_json_with_csrf(
            authenticated, "analyst@example.local", "secret pass"
        )
        self.assertTrue(internal_login.json()["ts_next_canonical_read"])
        internal_identity = authenticated.get("/api/auth/me")
        self.assertTrue(internal_identity.json()["ts_next_canonical_read"])
        internal_catalog = authenticated.get("/api/time-series/catalog/inputs")
        self.assertEqual(internal_catalog.status_code, 200, internal_catalog.text)
        self.assertIn("private", internal_catalog.headers["Cache-Control"])

        external_browser = TestClient(create_app(store=self.store, auth_enabled=True))
        external_login = login_json_with_csrf(
            external_browser, "client@example.local", "secret pass"
        )
        self.assertFalse(external_login.json()["ts_next_canonical_read"])
        external_identity = external_browser.get("/api/auth/me")
        self.assertFalse(external_identity.json()["ts_next_canonical_read"])
        refused = external_browser.get("/api/time-series/catalog/inputs")
        self.assertEqual(refused.status_code, 403)
        self.assertNotIn("items", refused.json())

    def test_cutover_monitor_pauses_mutations_and_daily_reconciliation_raises(self):
        self.prove_c5()
        self.store.cut_over_time_series_c6(actor="internal_admin")

        observed = self.store.observe_time_series_c6_health(
            actor="cutover_monitor",
            observation={
                "open_blocking_anomalies": 1,
                "shadow_read_differences": 1,
                "object_scoped_catalog_rows": 1,
                "cross_project_references": 1,
                "active_unsealed_bindings": 1,
                "legacy_writes": 1,
                "visible_partial_revisions": 1,
                "blocking_operation_latency": {
                    "p95_ms": 451.0,
                    "budget_ms": 300.0,
                    "sustained_minutes": 15,
                },
                "http_5xx": {
                    "error_count": 6,
                    "request_count": 1000,
                    "window_minutes": 30,
                },
                "failed_publications": {
                    "failed_after_retries": 2,
                    "batch_size": 100,
                },
            },
        )

        self.assertEqual(observed["status"], "mutations_paused")
        self.assertTrue(observed["canonical_reads_active"])
        self.assertEqual(
            {trigger["code"] for trigger in observed["triggers"]},
            {
                "TS_CUTOVER_LEGACY_WRITE_OBSERVED",
                "TS_CUTOVER_BLOCKING_ANOMALY_OPEN",
                "TS_CUTOVER_SHADOW_DIFFERENCE_OBSERVED",
                "TS_CUTOVER_OBJECT_SCOPE_LEAK_OBSERVED",
                "TS_CUTOVER_CROSS_PROJECT_REFERENCE_OBSERVED",
                "TS_CUTOVER_UNSEALED_BINDING_OBSERVED",
                "TS_CUTOVER_PARTIAL_REVISION_VISIBLE",
                "TS_CUTOVER_LATENCY_THRESHOLD_EXCEEDED",
                "TS_CUTOVER_5XX_THRESHOLD_EXCEEDED",
                "TS_CUTOVER_PUBLICATION_FAILURE_THRESHOLD_EXCEEDED",
            },
        )
        state = self.store.read_time_series_c6_state()
        self.assertTrue(state["canonical_mutations_paused"])
        self.assertTrue(state["ts_next_canonical_read"])
        with self.assertRaises(MigrationControlError) as paused:
            self.store.publish_canonical_set_revision(
                project_id=self.project["id"],
                name="Should not publish",
                data_class_key="real",
                signals=[
                    {
                        "series_key": "energy_price",
                        "display_name": "Precio",
                        "semantic_type_key": "energy_price",
                        "unit_key": "usd_per_mwh",
                        "signal_role": "input",
                        "aggregation": "mean",
                    }
                ],
                periods=[
                    {
                        "timestamp_start": "2026-02-01T00:00:00",
                        "timestamp_end": "2026-02-01T01:00:00",
                        "duration_hours": 1.0,
                    }
                ],
                values={"energy_price": [80.0]},
                actor="analyst@example.local",
            )
        self.assertEqual(paused.exception.code, "TS_CUTOVER_MUTATIONS_PAUSED")

        # A clean store records the daily pass; a one-row projection drift is
        # then a zero-tolerance reconciliation failure, never a silent repair.
        clean = AnalystStore("sqlite:///:memory:")
        self.addCleanup(clean.close)
        project = clean.create_project(name="Daily reconciliation")
        scenario = clean.create_scenario(project_id=project["id"], name="Base")
        case = clean.get_or_create_case_for_scenario(scenario["id"])
        variant = clean.get_or_create_default_input_variant(case["id"])
        legacy = import_legacy_price_set(clean, scenario["id"])
        clean.upsert_case_time_series_binding(
            case_input_variant_id=variant["id"],
            signal_key="import_price_usd_per_mwh",
            time_series_set_id=legacy["id"],
        )
        daily_copy = tempfile.TemporaryDirectory()
        self.addCleanup(daily_copy.cleanup)
        clean.take_c0_recovery_point(
            actor="internal_admin", copy_directory=Path(daily_copy.name)
        )
        clean.backfill_time_series_c2(actor="internal_admin")
        clean.backfill_time_series_c3(actor="internal_admin")
        clean.backfill_time_series_c4(actor="internal_admin")
        clean.verify_time_series_c5_shadow(actor="internal_admin")
        clean.cut_over_time_series_c6(actor="internal_admin")

        daily = clean.reconcile_time_series_c6_daily(actor="cutover_monitor")
        self.assertEqual(daily["status"], "reconciled")
        self.assertEqual(daily["divergent_rows"], [])
        entries = clean._projection("time_series_catalog_entries")
        clean.connection.execute(
            f"UPDATE {entries} SET binding_count = binding_count + 1"
        )
        clean.connection.commit()
        with self.assertRaises(MigrationControlError) as divergence:
            clean.reconcile_time_series_c6_daily(
                actor="cutover_monitor", force=True
            )
        self.assertEqual(
            divergence.exception.code,
            "TS_CUTOVER_DAILY_RECONCILIATION_DIVERGENCE",
        )
        self.assertTrue(divergence.exception.context["divergent_rows"])

    def test_c6_rechecks_the_live_gate_and_never_cuts_over_on_divergence(self):
        self.prove_c5()
        entries = self.store._projection("time_series_catalog_entries")
        self.store.connection.execute(
            f"UPDATE {entries} SET association_count = association_count + 1"
        )
        self.store.connection.commit()

        with self.assertRaises(MigrationPhaseStopped) as stopped:
            self.store.cut_over_time_series_c6(actor="internal_admin")

        self.assertEqual(stopped.exception.code, "TS_MIGRATION_C6_STOPPED")
        self.assertTrue(stopped.exception.context["rollback_trigger"])
        self.assertFalse(self.store.read_time_series_c6_state()["cutover_active"])
        self.assertIsNone(self.store.read_legacy_mutation_pause())
        # A refused cut does not accidentally install the irreversible guard.
        self.store.connection.execute(
            "UPDATE time_series_values SET value_numeric = value_numeric"
        )
        self.store.connection.commit()

        rebuilt = self.store.rebuild_catalog_projection()
        self.assertEqual(rebuilt["outcome"], "rebuilt")
        self.store.verify_time_series_c5_shadow(actor="internal_admin")
        receipt = self.store.cut_over_time_series_c6(actor="internal_admin")
        self.assertEqual(receipt["status"], "proven")
        self.assertEqual(
            receipt["manifest"]["gate"]["pending_dirty_roots"], 0
        )
        self.assertEqual(
            receipt["manifest"]["gate"]["final_journal_checks"], 2
        )

    def test_hydraulic_adapter_migrates_on_demand_into_the_canonical_catalog(self):
        now = "2026-01-01T00:00:00+00:00"
        cursor = self.store.connection.execute(
            """
            INSERT INTO hydraulic_time_series_sets (
                project_id, entity_type, entity_id, signal_key, version_number,
                version_label, content_hash, status, created_at, updated_at,
                created_by, updated_by
            ) VALUES (?, 'hydraulic_node', 1, 'natural_inflow_m3s', 1, 'v1',
                      'legacy-hydraulic-hash', 'draft', ?, ?, 'seed', 'seed')
            """,
            (self.project["id"], now, now),
        )
        hydraulic_id = int(cursor.lastrowid)
        for index, value in enumerate((5.0, 6.0)):
            self.store.connection.execute(
                """
                INSERT INTO hydraulic_time_series_points (
                    hydraulic_time_series_set_id, point_index, timestamp,
                    duration_hours, value
                ) VALUES (?, ?, ?, 1.0, ?)
                """,
                (hydraulic_id, index, f"2026-01-01T{index:02d}:00:00+00:00", value),
            )
        self.store.connection.commit()
        legacy_before = self.store.get_hydraulic_time_series_set(
            self.project["id"], hydraulic_id
        )
        self.prove_c5()
        self.store.cut_over_time_series_c6(actor="internal_admin")

        route = (
            f"/api/projects/{self.project['id']}/time-series-sets/hydraulic/"
            f"{hydraulic_id}/migrate"
        )
        first = self.client.post(route)
        self.assertEqual(first.status_code, 200, first.text)
        self.assertFalse(first.json()["already_migrated"])
        migrated = first.json()["time_series_set"]
        canonical = self.store.read_canonical_set(migrated["id"])
        self.assertEqual(canonical["series_kind"], "catalog")
        self.assertEqual(
            migrated["revision_metadata"]["origin"]["kind"],
            "hydraulic_legacy_migration",
        )
        legacy_set_alias = self.client.get(
            f"/api/projects/{self.project['id']}/time-series-sets/{migrated['id']}"
        )
        self.assertEqual(legacy_set_alias.status_code, 200, legacy_set_alias.text)
        self.assertEqual(
            legacy_set_alias.json()["time_series_set"]["id"], migrated["id"]
        )

        second = self.client.post(route)
        self.assertEqual(second.status_code, 200, second.text)
        self.assertTrue(second.json()["already_migrated"])
        self.assertEqual(second.json()["time_series_set"]["id"], migrated["id"])
        after = self.store.get_hydraulic_time_series_set(
            self.project["id"], hydraulic_id
        )
        self.assertEqual(after["values"], legacy_before["values"])
        self.assertEqual(after["migration"]["time_series_set_id"], migrated["id"])

    def test_a_link_started_from_the_legacy_route_ends_only_in_the_generic_model(self):
        self.prove_c5()
        self.store.cut_over_time_series_c6(actor="internal_admin")
        scenario = self.store.create_scenario(
            project_id=self.project["id"], name="Post-cutover"
        )
        case = self.store.get_or_create_case_for_scenario(scenario["id"])
        variant = self.store.get_or_create_default_input_variant(case["id"])
        legacy_count = self.store.connection.execute(
            "SELECT COUNT(*) AS total FROM case_time_series_bindings"
        ).fetchone()["total"]
        route = (
            f"/api/scenarios/{scenario['id']}/case/variants/"
            f"{variant['id']}/bindings"
        )
        payload = {
            "signal_key": "import_price_usd_per_mwh",
            "entity_type": None,
            "entity_id": None,
            "time_series_set_id": self.legacy_set["id"],
        }

        created = self.client.post(route, json=payload)
        self.assertEqual(created.status_code, 201, created.text)
        self.assertEqual(created.json()["source_kind"], "catalog")
        self.assertEqual(created.json()["state"], "valid_current")
        self.assertEqual(
            self.store.connection.execute(
                "SELECT COUNT(*) AS total FROM case_time_series_bindings"
            ).fetchone()["total"],
            legacy_count,
        )
        canonical = self.store.read_case_bindings(
            scenario_id=scenario["id"], variant_id=variant["id"]
        )
        self.assertEqual(len(canonical["items"]), 1)
        self.assertEqual(
            canonical["items"][0]["binding_id"], created.json()["binding_id"]
        )

        repeated = self.client.post(route, json=payload)
        self.assertEqual(repeated.status_code, 201, repeated.text)
        self.assertEqual(repeated.json()["binding_id"], created.json()["binding_id"])

    def test_legacy_file_replace_publishes_only_a_complete_canonical_revision(self):
        self.prove_c5()
        self.store.cut_over_time_series_c6(actor="internal_admin")
        route = (
            f"/api/projects/{self.project['id']}/time-series-sets/"
            f"{self.legacy_set['id']}"
        )
        legacy_before = self.store.connection.execute(
            "SELECT content_hash, updated_at FROM time_series_sets WHERE id = ?",
            (self.legacy_set["id"],),
        ).fetchone()
        legacy_values_before = [
            tuple(row)
            for row in self.store.connection.execute(
                """
                SELECT time_series_signal_id, time_series_period_id, value_numeric
                FROM time_series_values WHERE time_series_set_id = ? ORDER BY id
                """,
                (self.legacy_set["id"],),
            ).fetchall()
        ]
        upload = self.client.post(
            f"{route}/replace/upload",
            files={
                "source_file": (
                    "price-corrected.csv",
                    "period_start,hours,value\n"
                    "2026-01-01T00:00:00,1.0,91.0\n"
                    "2026-01-01T01:00:00,1.0,92.0\n",
                    "text/csv",
                )
            },
        )
        self.assertEqual(upload.status_code, 201, upload.text)
        payload = {
            "source": upload.json()["source"],
            "data_kind": "real",
            "timezone": "UTC",
            "timestamp_column": "period_start",
            "duration_hours_column": "hours",
            "signal_mappings": [
                {
                    "source_column": "value",
                    "signal_key": "import_price_usd_per_mwh",
                }
            ],
            "change_summary": "Corrected post-cutover source",
        }

        missing_guards = self.client.post(f"{route}/replace", json=payload)
        self.assertEqual(missing_guards.status_code, 428, missing_guards.text)
        self.assertEqual(missing_guards.json()["code"], "TS_PRECONDITION_REQUIRED")

        etag = self.client.get(route).headers["etag"]
        headers = {"If-Match": etag, "Idempotency-Key": "replace-price-c6"}
        replaced = self.client.post(f"{route}/replace", json=payload, headers=headers)
        self.assertEqual(replaced.status_code, 200, replaced.text)
        updated = replaced.json()["time_series_set"]
        self.assertEqual(updated["revision_number"], 2)
        self.assertEqual(updated["values"][0]["value_numeric"], 91.0)
        self.assertEqual(replaced.headers["x-time-series-model"], "canonical")

        legacy_after = self.store.connection.execute(
            "SELECT content_hash, updated_at FROM time_series_sets WHERE id = ?",
            (self.legacy_set["id"],),
        ).fetchone()
        self.assertEqual(tuple(legacy_after), tuple(legacy_before))
        self.assertEqual(
            [
                tuple(row)
                for row in self.store.connection.execute(
                    """
                    SELECT time_series_signal_id, time_series_period_id, value_numeric
                    FROM time_series_values WHERE time_series_set_id = ? ORDER BY id
                    """,
                    (self.legacy_set["id"],),
                ).fetchall()
            ],
            legacy_values_before,
        )

        replayed = self.client.post(f"{route}/replace", json=payload, headers=headers)
        self.assertEqual(replayed.status_code, 200, replayed.text)
        self.assertEqual(replayed.json(), replaced.json())
        revisions = self.store.connection.execute(
            f"""
            SELECT COUNT(*) AS total
            FROM {self.store.canonical_table_names()['time_series_set_revisions']}
            WHERE time_series_set_id = ?
            """,
            (self.legacy_set["id"],),
        ).fetchone()["total"]
        self.assertEqual(revisions, 2)


if __name__ == "__main__":
    unittest.main()
