"""TS7-002 canonical content model with sealed revisions."""

import os
import unittest
import uuid

from app.persistence import AnalystStore
from app.time_series_canonical import (
    CANONICAL_IDENTITY_TABLES,
    DATABASE_GUARD_CODES,
    CanonicalRevisionError,
    canonical_schema_statements,
    canonical_table_names,
)


POSTGRES_TEST_DATABASE_URL = os.environ.get("POSTGRES_TEST_DATABASE_URL")


class CanonicalContentSpaceTests(unittest.TestCase):
    def setUp(self):
        self.store = AnalystStore("sqlite:///:memory:")
        self.project = self.store.create_project(name="Cuenca Norte")

    def tearDown(self):
        self.store.close()

    def _sqlite_tables(self) -> set[str]:
        return {
            row["name"]
            for row in self.store.connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }

    def test_the_canonical_tables_live_in_their_own_space_beside_the_legacy_ones(self):
        physical_names = self.store.canonical_table_names()
        tables = self._sqlite_tables()

        self.assertEqual(
            {
                "logical_names": sorted(physical_names),
                "physical_names": sorted(physical_names.values()),
                "missing_canonical": sorted(
                    set(physical_names.values()) - tables
                ),
                "legacy_still_present": sorted(
                    name
                    for name in (
                        "time_series_sets",
                        "time_series_signals",
                        "time_series_set_revisions",
                        "time_series_periods",
                        "time_series_values",
                        "time_series_sources",
                    )
                    if name in tables
                ),
            },
            {
                "logical_names": [
                    "time_series_periods",
                    "time_series_revision_lineage",
                    "time_series_revision_signals",
                    "time_series_set_revisions",
                    "time_series_sets",
                    "time_series_signals",
                    "time_series_sources",
                    "time_series_values",
                ],
                "physical_names": [
                    "time_series_periods_next",
                    "time_series_revision_lineage_next",
                    "time_series_revision_signals_next",
                    "time_series_set_revisions_next",
                    "time_series_sets_next",
                    "time_series_signals_next",
                    "time_series_sources_next",
                    "time_series_values_next",
                ],
                "missing_canonical": [],
                "legacy_still_present": [
                    "time_series_periods",
                    "time_series_set_revisions",
                    "time_series_sets",
                    "time_series_signals",
                    "time_series_sources",
                    "time_series_values",
                ],
            },
        )

    def test_canonical_content_never_lands_in_a_legacy_table(self):
        self.store.publish_canonical_set_revision(
            project_id=self.project["id"],
            name="Afluentes 2026",
            data_class_key="real",
            timezone="UTC",
            signals=[dict(INFLOW_SIGNAL)],
            periods=[dict(period) for period in TWO_HOURS],
            values={"inflow_node_a": [12.5, 13.25]},
            source={"source_key": "fixture", "kind": "api"},
            actor="internal_analyst",
        )

        legacy_rows = {
            table: int(
                self.store.connection.execute(
                    f"SELECT COUNT(*) AS total FROM {table}"
                ).fetchone()["total"]
            )
            for table in (
                "time_series_sets",
                "time_series_signals",
                "time_series_set_revisions",
                "time_series_periods",
                "time_series_values",
                "time_series_sources",
            )
        }
        canonical_rows = {
            logical: int(
                self.store.connection.execute(
                    f"SELECT COUNT(*) AS total FROM {physical}"
                ).fetchone()["total"]
            )
            for logical, physical in self.store.canonical_table_names().items()
        }

        self.assertEqual(
            {"legacy": legacy_rows, "canonical": canonical_rows},
            {
                "legacy": {
                    "time_series_sets": 0,
                    "time_series_signals": 0,
                    "time_series_set_revisions": 0,
                    "time_series_periods": 0,
                    "time_series_values": 0,
                    "time_series_sources": 0,
                },
                "canonical": {
                    "time_series_sets": 1,
                    "time_series_signals": 1,
                    "time_series_set_revisions": 1,
                    "time_series_revision_signals": 1,
                    "time_series_periods": 2,
                    "time_series_values": 2,
                    "time_series_sources": 1,
                    "time_series_revision_lineage": 0,
                },
            },
        )

    def test_every_generated_identity_column_is_declared_as_such(self):
        # On PostgreSQL the compatibility layer cannot append ``RETURNING id``
        # for a schema-qualified name, so the canonical writer spells it out for
        # exactly these tables. A new table with a generated key that is not
        # listed would silently read back id 0.
        declared = {}
        for backend, clause in (
            ("sqlite", "INTEGER PRIMARY KEY AUTOINCREMENT"),
            ("postgresql", "BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY"),
        ):
            statements = canonical_schema_statements(backend)
            declared[backend] = sorted(
                logical
                for logical, physical in canonical_table_names(backend).items()
                if any(
                    f"CREATE TABLE IF NOT EXISTS {physical} (" in statement
                    and clause in statement
                    for statement in statements
                )
            )

        self.assertEqual(
            declared,
            {
                "sqlite": sorted(CANONICAL_IDENTITY_TABLES),
                "postgresql": sorted(CANONICAL_IDENTITY_TABLES),
            },
        )


INFLOW_SIGNAL = {
    "series_key": "inflow_node_a",
    "display_name": "Afluente nodo A",
    "semantic_type_key": "natural_inflow",
    "unit_key": "m3_per_s",
    "signal_role": "input",
}
DEMAND_SIGNAL = {
    "series_key": "demand_plant_a",
    "display_name": "Demanda planta A",
    "semantic_type_key": "load_demand",
    "unit_key": "mw",
    "signal_role": "input",
}
TWO_HOURS = [
    {
        "timestamp_start": "2026-01-01T00:00:00",
        "timestamp_end": "2026-01-01T01:00:00",
        "duration_hours": 1.0,
    },
    {
        "timestamp_start": "2026-01-01T01:00:00",
        "timestamp_end": "2026-01-01T02:00:00",
        "duration_hours": 1.0,
    },
]


class AtomicRevisionProtocolTests(unittest.TestCase):
    def setUp(self):
        self.store = AnalystStore("sqlite:///:memory:")
        self.project = self.store.create_project(name="Cuenca Norte")

    def tearDown(self):
        self.store.close()

    def _publish(self, **overrides):
        payload = {
            "project_id": self.project["id"],
            "name": "Afluentes 2026",
            "data_class_key": "real",
            "timezone": "UTC",
            "signals": [dict(INFLOW_SIGNAL)],
            "periods": [dict(period) for period in TWO_HOURS],
            "values": {"inflow_node_a": [12.5, 13.25]},
            "actor": "internal_analyst",
        }
        payload.update(overrides)
        return self.store.publish_canonical_set_revision(**payload)

    def test_publishing_content_seals_one_complete_revision_and_makes_it_current(self):
        receipt = self._publish()

        set_view = self.store.read_canonical_set(receipt["set_id"])
        revision = self.store.read_canonical_revision(receipt["revision_id"])

        self.assertEqual(
            {
                "revision_number": receipt["revision_number"],
                "state": receipt["state"],
                "hash_is_set": bool(receipt["content_hash"]),
                "counts": (
                    receipt["signal_count"],
                    receipt["period_count"],
                    receipt["value_count"],
                ),
                "current_points_at_revision": (
                    set_view["current_revision_id"] == receipt["revision_id"]
                ),
                "set_hash_matches_revision": (
                    set_view["content_hash"] == receipt["content_hash"]
                ),
                "current_series_keys": [
                    signal["series_key"] for signal in set_view["signals"]
                ],
                "revision_values": revision["values"]["inflow_node_a"],
                "revision_period_starts": [
                    period["timestamp_start"] for period in revision["periods"]
                ],
                "revision_signal_contract": {
                    key: revision["signals"][0][key]
                    for key in (
                        "semantic_type_key",
                        "unit_key",
                        "data_class_key",
                        "signal_role",
                        "aggregation",
                        "ordinal",
                    )
                },
            },
            {
                "revision_number": 1,
                "state": "sealed",
                "hash_is_set": True,
                "counts": (1, 2, 2),
                "current_points_at_revision": True,
                "set_hash_matches_revision": True,
                "current_series_keys": ["inflow_node_a"],
                "revision_values": [12.5, 13.25],
                "revision_period_starts": [
                    "2026-01-01T00:00:00",
                    "2026-01-01T01:00:00",
                ],
                "revision_signal_contract": {
                    "semantic_type_key": "natural_inflow",
                    "unit_key": "m3_per_s",
                    "data_class_key": "real",
                    "signal_role": "input",
                    "aggregation": "mean",
                    "ordinal": 0,
                },
            },
        )


class AtomicityAndIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.store = AnalystStore("sqlite:///:memory:")
        self.project = self.store.create_project(name="Cuenca Norte")
        self.tables = self.store.canonical_table_names()
        self.first = self._publish()

    def tearDown(self):
        self.store.close()

    def _publish(self, **overrides):
        payload = {
            "project_id": self.project["id"],
            "name": "Afluentes 2026",
            "data_class_key": "real",
            "timezone": "UTC",
            "signals": [dict(INFLOW_SIGNAL)],
            "periods": [dict(period) for period in TWO_HOURS],
            "values": {"inflow_node_a": [12.5, 13.25]},
            "actor": "internal_analyst",
        }
        payload.update(overrides)
        return self.store.publish_canonical_set_revision(**payload)

    def _stored_counts(self):
        set_id = self.first["set_id"]
        revisions = self.store.connection.execute(
            f"""
            SELECT state, COUNT(*) AS total
            FROM {self.tables['time_series_set_revisions']}
            WHERE time_series_set_id = ?
            GROUP BY state
            """,
            (set_id,),
        ).fetchall()
        return {
            "revisions_by_state": {row["state"]: int(row["total"]) for row in revisions},
            "periods": int(
                self.store.connection.execute(
                    f"SELECT COUNT(*) AS total FROM {self.tables['time_series_periods']}"
                ).fetchone()["total"]
            ),
            "values": int(
                self.store.connection.execute(
                    f"SELECT COUNT(*) AS total FROM {self.tables['time_series_values']}"
                ).fetchone()["total"]
            ),
        }

    def test_a_publication_that_dies_halfway_leaves_no_partially_visible_revision(self):
        in_flight = {}

        def dying_source():
            # Read the uncommitted state from inside the publication, so a
            # rollback that never happened cannot make this test pass.
            yield {"series_key": "inflow_node_a", "period_index": 0, "value": 99.0}
            in_flight.update(self._stored_counts())
            in_flight["building_hashes"] = [
                row["content_hash"]
                for row in self.store.connection.execute(
                    f"""
                    SELECT content_hash
                    FROM {self.tables['time_series_set_revisions']}
                    WHERE state = 'building'
                    """
                ).fetchall()
            ]
            raise ConnectionError("the ingestion source died mid publication")

        with self.assertRaises(ConnectionError):
            self._publish(values=dying_source())

        self.assertEqual(
            {
                "revisions_by_state": in_flight["revisions_by_state"],
                "periods": in_flight["periods"],
                "building_hashes": in_flight["building_hashes"],
            },
            {
                "revisions_by_state": {"building": 1, "sealed": 1},
                "periods": 4,
                "building_hashes": [None],
            },
        )

        set_view = self.store.read_canonical_set(self.first["set_id"])
        revision = self.store.read_canonical_revision(self.first["revision_id"])

        self.assertEqual(
            {
                "stored": self._stored_counts(),
                "current_revision_id": set_view["current_revision_id"],
                "current_hash": set_view["content_hash"],
                "values": revision["values"]["inflow_node_a"],
            },
            {
                "stored": {
                    "revisions_by_state": {"sealed": 1},
                    "periods": 2,
                    "values": 2,
                },
                "current_revision_id": self.first["revision_id"],
                "current_hash": self.first["content_hash"],
                "values": [12.5, 13.25],
            },
        )

    def test_editing_content_publishes_a_new_revision_and_leaves_the_old_one_intact(
        self,
    ):
        second = self._publish(values={"inflow_node_a": [12.5, 99.0]})

        first_revision = self.store.read_canonical_revision(self.first["revision_id"])
        second_revision = self.store.read_canonical_revision(second["revision_id"])
        set_view = self.store.read_canonical_set(self.first["set_id"])

        self.assertEqual(
            {
                "revision_numbers": (
                    first_revision["revision_number"],
                    second_revision["revision_number"],
                ),
                "supersedes": second["supersedes_revision_id"],
                "first_values": first_revision["values"]["inflow_node_a"],
                "second_values": second_revision["values"]["inflow_node_a"],
                "hashes_differ": (
                    first_revision["content_hash"] != second_revision["content_hash"]
                ),
                "current_revision_id": set_view["current_revision_id"],
                "stored": self._stored_counts(),
            },
            {
                "revision_numbers": (1, 2),
                "supersedes": self.first["revision_id"],
                "first_values": [12.5, 13.25],
                "second_values": [12.5, 99.0],
                "hashes_differ": True,
                "current_revision_id": second["revision_id"],
                "stored": {
                    "revisions_by_state": {"sealed": 2},
                    "periods": 4,
                    "values": 4,
                },
            },
        )

    def test_an_incomplete_or_conflicting_snapshot_is_refused_without_writing(self):
        overlapping = [dict(period) for period in TWO_HOURS]
        overlapping[1]["timestamp_start"] = "2026-01-01T00:30:00"
        unordered = [dict(period) for period in reversed(TWO_HOURS)]
        zero_duration = [dict(period) for period in TWO_HOURS]
        zero_duration[0]["duration_hours"] = 0

        def refusal(**overrides):
            try:
                self._publish(**overrides)
            except CanonicalRevisionError as error:
                return error.code
            return "accepted"

        codes = {
            "short_column": refusal(values={"inflow_node_a": [12.5]}),
            "overlapping_periods": refusal(periods=overlapping),
            "unordered_coverage": refusal(periods=unordered),
            "zero_duration": refusal(periods=zero_duration),
            "no_signals": refusal(signals=[]),
            "duplicated_series_key": refusal(
                signals=[dict(INFLOW_SIGNAL), dict(INFLOW_SIGNAL)],
                values={"inflow_node_a": [1.0, 2.0]},
            ),
        }

        self.assertEqual(
            {"codes": codes, "stored": self._stored_counts()},
            {
                "codes": {
                    "short_column": "TS_REVISION_VALUE_COUNT_MISMATCH",
                    "overlapping_periods": "TS_INGEST_PERIOD_CONFLICT",
                    "unordered_coverage": "TS_INGEST_PERIOD_CONFLICT",
                    "zero_duration": "TS_INGEST_DURATION_INVALID",
                    "no_signals": "TS_INGEST_SIGNAL_SET_INCOMPLETE",
                    "duplicated_series_key": "TS_INGEST_SIGNAL_SET_INCOMPLETE",
                },
                "stored": {
                    "revisions_by_state": {"sealed": 1},
                    "periods": 2,
                    "values": 2,
                },
            },
        )

    def test_the_canonical_hash_follows_the_content_and_not_the_set_it_lives_in(self):
        twin = self._publish(name="Afluentes 2026 (copia)")
        different_value = self._publish(
            name="Otro valor", values={"inflow_node_a": [12.5, 13.5]}
        )
        reordered = self.store.publish_canonical_set_revision(
            project_id=self.project["id"],
            name="Orden invertido",
            data_class_key="real",
            timezone="UTC",
            signals=[dict(DEMAND_SIGNAL), dict(INFLOW_SIGNAL)],
            periods=[dict(period) for period in TWO_HOURS],
            values={
                "inflow_node_a": [12.5, 13.25],
                "demand_plant_a": [40.0, 41.0],
            },
            actor="internal_analyst",
        )
        same_pair_in_order = self.store.publish_canonical_set_revision(
            project_id=self.project["id"],
            name="Orden directo",
            data_class_key="real",
            timezone="UTC",
            signals=[dict(INFLOW_SIGNAL), dict(DEMAND_SIGNAL)],
            periods=[dict(period) for period in TWO_HOURS],
            values={
                "inflow_node_a": [12.5, 13.25],
                "demand_plant_a": [40.0, 41.0],
            },
            actor="internal_analyst",
        )
        other_class = self._publish(name="Otra clase", data_class_key="forecast")

        self.assertEqual(
            {
                "identical_content_hashes_equal": (
                    twin["content_hash"] == self.first["content_hash"]
                ),
                "different_value_changes_hash": (
                    different_value["content_hash"] != self.first["content_hash"]
                ),
                "signal_order_changes_hash": (
                    reordered["content_hash"] != same_pair_in_order["content_hash"]
                ),
                "data_class_changes_hash": (
                    other_class["content_hash"] != self.first["content_hash"]
                ),
                "hash_length": len(self.first["content_hash"]),
            },
            {
                "identical_content_hashes_equal": True,
                "different_value_changes_hash": True,
                "signal_order_changes_hash": True,
                "data_class_changes_hash": True,
                "hash_length": 64,
            },
        )


class SignalIdentityLifetimeTests(unittest.TestCase):
    def setUp(self):
        self.store = AnalystStore("sqlite:///:memory:")
        self.project = self.store.create_project(name="Cuenca Norte")
        self.first = self.store.publish_canonical_set_revision(
            project_id=self.project["id"],
            name="Afluentes 2026",
            data_class_key="real",
            timezone="UTC",
            signals=[dict(INFLOW_SIGNAL), dict(DEMAND_SIGNAL)],
            periods=[dict(period) for period in TWO_HOURS],
            values={
                "inflow_node_a": [12.5, 13.25],
                "demand_plant_a": [40.0, 41.0],
            },
            actor="internal_analyst",
        )

    def tearDown(self):
        self.store.close()

    def test_a_signal_that_leaves_a_revision_survives_as_a_historical_identity(self):
        second = self.store.publish_canonical_set_revision(
            project_id=self.project["id"],
            name="Afluentes 2026",
            data_class_key="real",
            timezone="UTC",
            signals=[dict(INFLOW_SIGNAL)],
            periods=[dict(period) for period in TWO_HOURS],
            values={"inflow_node_a": [20.0, 21.0]},
            actor="internal_analyst",
        )

        identities = {
            identity["series_key"]: identity
            for identity in self.store.list_canonical_signal_identities(
                self.first["set_id"]
            )
        }
        set_view = self.store.read_canonical_set(self.first["set_id"])
        first_revision = self.store.read_canonical_revision(self.first["revision_id"])

        self.assertEqual(
            {
                "inflow_identity_reused": (
                    identities["inflow_node_a"]["signal_id"]
                    == self.first["signal_ids"]["inflow_node_a"]
                    == second["signal_ids"]["inflow_node_a"]
                ),
                "demand_identity_kept": (
                    identities["demand_plant_a"]["signal_id"]
                    == self.first["signal_ids"]["demand_plant_a"]
                ),
                "demand_status": identities["demand_plant_a"]["status"],
                "demand_in_current_revision": identities["demand_plant_a"][
                    "in_current_revision"
                ],
                "demand_last_revision_number": identities["demand_plant_a"][
                    "last_revision_number"
                ],
                "current_series_keys": [
                    signal["series_key"] for signal in set_view["signals"]
                ],
                "history_still_reads_demand": sorted(
                    first_revision["values"]["demand_plant_a"]
                ),
                "revision_numbers": (
                    self.first["revision_number"],
                    second["revision_number"],
                ),
            },
            {
                "inflow_identity_reused": True,
                "demand_identity_kept": True,
                "demand_status": "active",
                "demand_in_current_revision": False,
                "demand_last_revision_number": 1,
                "current_series_keys": ["inflow_node_a"],
                "history_still_reads_demand": [40.0, 41.0],
                "revision_numbers": (1, 2),
            },
        )

    def test_an_archived_identity_is_never_recycled_by_a_later_revision(self):
        self.store.archive_canonical_signal_identity(
            set_id=self.first["set_id"],
            series_key="demand_plant_a",
            actor="internal_analyst",
        )

        with self.assertRaises(CanonicalRevisionError) as raised:
            self.store.publish_canonical_set_revision(
                project_id=self.project["id"],
                name="Afluentes 2026",
                data_class_key="real",
                timezone="UTC",
                signals=[dict(INFLOW_SIGNAL), dict(DEMAND_SIGNAL)],
                periods=[dict(period) for period in TWO_HOURS],
                values={
                    "inflow_node_a": [1.0, 2.0],
                    "demand_plant_a": [3.0, 4.0],
                },
                actor="internal_analyst",
            )

        set_view = self.store.read_canonical_set(self.first["set_id"])
        identities = {
            identity["series_key"]: identity
            for identity in self.store.list_canonical_signal_identities(
                self.first["set_id"]
            )
        }

        self.assertEqual(
            {
                "code": raised.exception.code,
                "context_series_key": raised.exception.context["series_key"],
                "current_revision_id": set_view["current_revision_id"],
                "archived_identity_kept": (
                    identities["demand_plant_a"]["signal_id"]
                    == self.first["signal_ids"]["demand_plant_a"]
                ),
                "archived_status": identities["demand_plant_a"]["status"],
            },
            {
                "code": "TS_OBJECT_SERIES_KEY_CONFLICT",
                "context_series_key": "demand_plant_a",
                "current_revision_id": self.first["revision_id"],
                "archived_identity_kept": True,
                "archived_status": "archived",
            },
        )


def attempt(connection, sql, parameters=()):
    """Run a forbidden statement and report the stable failure it raises."""

    try:
        connection.execute(sql, parameters)
    except Exception as error:  # noqa: BLE001 - the engine decides the class
        text = str(error)
        for code in DATABASE_GUARD_CODES:
            if code in text:
                return code
        return f"unexpected: {text}"
    return "accepted"


class SealedRevisionGuardTests(unittest.TestCase):
    """Chapter 9.6: the application is friendly, the database is the last defence."""

    def setUp(self):
        self.store = AnalystStore("sqlite:///:memory:")
        self.project = self.store.create_project(name="Cuenca Norte")
        self.tables = self.store.canonical_table_names()
        self.receipt = self.store.publish_canonical_set_revision(
            project_id=self.project["id"],
            name="Afluentes 2026",
            data_class_key="real",
            timezone="UTC",
            signals=[dict(INFLOW_SIGNAL)],
            periods=[dict(period) for period in TWO_HOURS],
            values={"inflow_node_a": [12.5, 13.25]},
            actor="internal_analyst",
        )

    def tearDown(self):
        self.store.close()

    def test_a_sealed_revision_and_its_children_refuse_every_update_and_delete(self):
        revision_id = self.receipt["revision_id"]
        connection = self.store.connection
        outcomes = {
            "revision_update": attempt(
                connection,
                f"UPDATE {self.tables['time_series_set_revisions']} "
                "SET change_summary = 'rewritten' WHERE id = ?",
                (revision_id,),
            ),
            "revision_delete": attempt(
                connection,
                f"DELETE FROM {self.tables['time_series_set_revisions']} WHERE id = ?",
                (revision_id,),
            ),
            "revision_signal_update": attempt(
                connection,
                f"UPDATE {self.tables['time_series_revision_signals']} "
                "SET aggregation = 'sum' WHERE set_revision_id = ?",
                (revision_id,),
            ),
            "revision_signal_delete": attempt(
                connection,
                f"DELETE FROM {self.tables['time_series_revision_signals']} "
                "WHERE set_revision_id = ?",
                (revision_id,),
            ),
            "period_update": attempt(
                connection,
                f"UPDATE {self.tables['time_series_periods']} "
                "SET duration_hours = 2 WHERE set_revision_id = ?",
                (revision_id,),
            ),
            "period_delete": attempt(
                connection,
                f"DELETE FROM {self.tables['time_series_periods']} "
                "WHERE set_revision_id = ?",
                (revision_id,),
            ),
            "value_update": attempt(
                connection,
                f"UPDATE {self.tables['time_series_values']} "
                "SET value_numeric = 99 WHERE set_revision_id = ?",
                (revision_id,),
            ),
            "value_delete": attempt(
                connection,
                f"DELETE FROM {self.tables['time_series_values']} "
                "WHERE set_revision_id = ?",
                (revision_id,),
            ),
        }
        revision = self.store.read_canonical_revision(revision_id)

        self.assertEqual(
            {
                "outcomes": outcomes,
                "content_hash_unchanged": (
                    revision["content_hash"] == self.receipt["content_hash"]
                ),
                "values": revision["values"]["inflow_node_a"],
                "period_durations": [
                    period["duration_hours"] for period in revision["periods"]
                ],
            },
            {
                "outcomes": {
                    "revision_update": "TS_REVISION_SEALED",
                    "revision_delete": "TS_REVISION_SEALED",
                    "revision_signal_update": "TS_REVISION_SEALED",
                    "revision_signal_delete": "TS_REVISION_SEALED",
                    "period_update": "TS_REVISION_SEALED",
                    "period_delete": "TS_REVISION_SEALED",
                    "value_update": "TS_REVISION_SEALED",
                    "value_delete": "TS_REVISION_SEALED",
                },
                "content_hash_unchanged": True,
                "values": [12.5, 13.25],
                "period_durations": [1.0, 1.0],
            },
        )

    def test_the_current_pointer_only_accepts_a_sealed_revision_of_its_own_set(self):
        set_id = self.receipt["set_id"]
        connection = self.store.connection
        neighbour = self.store.publish_canonical_set_revision(
            project_id=self.project["id"],
            name="Demanda 2026",
            data_class_key="real",
            timezone="UTC",
            signals=[dict(DEMAND_SIGNAL)],
            periods=[dict(period) for period in TWO_HOURS],
            values={"demand_plant_a": [40.0, 41.0]},
            actor="internal_analyst",
        )
        building_id = int(
            connection.execute(
                f"""
                INSERT INTO {self.tables['time_series_set_revisions']} (
                    time_series_set_id, revision_number, data_class_id, timezone,
                    state, created_at, created_by
                )
                SELECT ?, 99, id, 'UTC', 'building', '2026-01-01T00:00:00', 'test'
                FROM time_series_data_classes WHERE data_class_key = 'real'
                RETURNING id
                """,
                (set_id,),
            ).fetchone()["id"]
        )

        outcomes = {
            "point_at_building": attempt(
                connection,
                f"UPDATE {self.tables['time_series_sets']} "
                "SET current_revision_id = ? WHERE id = ?",
                (building_id, set_id),
            ),
            "point_at_another_sets_revision": attempt(
                connection,
                f"UPDATE {self.tables['time_series_sets']} "
                "SET current_revision_id = ? WHERE id = ?",
                (self.receipt["revision_id"], neighbour["set_id"]),
            ),
        }
        set_view = self.store.read_canonical_set(set_id)
        neighbour_view = self.store.read_canonical_set(neighbour["set_id"])

        self.assertEqual(
            {
                "outcomes": outcomes,
                "current_revision_id": set_view["current_revision_id"],
                "neighbour_current_revision_id": (
                    neighbour_view["current_revision_id"]
                ),
            },
            {
                "outcomes": {
                    "point_at_building": "TS_REVISION_NOT_SEALED",
                    "point_at_another_sets_revision": "TS_REVISION_NOT_SEALED",
                },
                "current_revision_id": self.receipt["revision_id"],
                "neighbour_current_revision_id": neighbour["revision_id"],
            },
        )

    def test_an_identity_is_never_redirected_and_the_lineage_ledger_only_appends(self):
        set_id = self.receipt["set_id"]
        signal_id = self.receipt["signal_ids"]["inflow_node_a"]
        connection = self.store.connection
        derived = self.store.publish_canonical_set_revision(
            project_id=self.project["id"],
            name="Afluentes derivados",
            data_class_key="derived",
            timezone="UTC",
            signals=[dict(INFLOW_SIGNAL)],
            periods=[dict(period) for period in TWO_HOURS],
            values={"inflow_node_a": [12.5, 13.25]},
            actor="internal_analyst",
            lineage=[
                {
                    "series_key": "inflow_node_a",
                    "source_set_revision_id": self.receipt["revision_id"],
                    "source_signal_id": signal_id,
                    "lineage_kind": "allowlisted_transformation",
                    "source_content_hash": self.receipt["content_hash"],
                    "reason_code": "TS_LINEAGE_COPY",
                }
            ],
        )

        outcomes = {
            "redirect_identity": attempt(
                connection,
                f"UPDATE {self.tables['time_series_signals']} "
                "SET series_key = 'inflow_node_b' WHERE id = ?",
                (signal_id,),
            ),
            "move_identity_to_another_set": attempt(
                connection,
                f"UPDATE {self.tables['time_series_signals']} "
                "SET time_series_set_id = ? WHERE id = ?",
                (derived["set_id"], signal_id),
            ),
            "rewrite_lineage": attempt(
                connection,
                f"UPDATE {self.tables['time_series_revision_lineage']} "
                "SET reason_code = 'rewritten' WHERE derived_set_revision_id = ?",
                (derived["revision_id"],),
            ),
            "erase_lineage": attempt(
                connection,
                f"DELETE FROM {self.tables['time_series_revision_lineage']} "
                "WHERE derived_set_revision_id = ?",
                (derived["revision_id"],),
            ),
        }
        lineage = [
            dict(row)
            for row in connection.execute(
                f"""
                SELECT source_set_revision_id, source_signal_id, lineage_kind,
                       source_content_hash, reason_code
                FROM {self.tables['time_series_revision_lineage']}
                WHERE derived_set_revision_id = ?
                """,
                (derived["revision_id"],),
            ).fetchall()
        ]

        self.assertEqual(
            {"outcomes": outcomes, "lineage": lineage},
            {
                "outcomes": {
                    "redirect_identity": "TS_SIGNAL_IDENTITY_IMMUTABLE",
                    "move_identity_to_another_set": "TS_SIGNAL_IDENTITY_IMMUTABLE",
                    "rewrite_lineage": "TS_LEDGER_APPEND_ONLY",
                    "erase_lineage": "TS_LEDGER_APPEND_ONLY",
                },
                "lineage": [
                    {
                        "source_set_revision_id": self.receipt["revision_id"],
                        "source_signal_id": signal_id,
                        "lineage_kind": "allowlisted_transformation",
                        "source_content_hash": self.receipt["content_hash"],
                        "reason_code": "TS_LINEAGE_COPY",
                    }
                ],
            },
        )

    def test_a_hash_belongs_to_a_sealed_revision_and_only_to_a_sealed_one(self):
        set_id = self.receipt["set_id"]
        connection = self.store.connection
        data_class_id = int(
            connection.execute(
                "SELECT id FROM time_series_data_classes WHERE data_class_key = 'real'"
            ).fetchone()["id"]
        )

        def insert_revision(revision_number, state, content_hash):
            try:
                connection.execute(
                    f"""
                    INSERT INTO {self.tables['time_series_set_revisions']} (
                        time_series_set_id, revision_number, data_class_id,
                        timezone, state, content_hash, created_at, created_by
                    ) VALUES (?, ?, ?, 'UTC', ?, ?, '2026-01-01T00:00:00', 'test')
                    """,
                    (set_id, revision_number, data_class_id, state, content_hash),
                )
            except Exception:  # noqa: BLE001 - the CHECK decides the class
                return "refused"
            return "accepted"

        self.assertEqual(
            {
                "building_with_hash": insert_revision(90, "building", "deadbeef"),
                "building_without_hash": insert_revision(91, "building", None),
                "sealed_without_hash": insert_revision(92, "sealed", None),
                "sealed_with_hash": insert_revision(93, "sealed", "deadbeef"),
            },
            {
                "building_with_hash": "refused",
                "building_without_hash": "accepted",
                "sealed_without_hash": "refused",
                "sealed_with_hash": "accepted",
            },
        )


@unittest.skipUnless(
    POSTGRES_TEST_DATABASE_URL,
    "POSTGRES_TEST_DATABASE_URL is required for PostgreSQL integration tests",
)
class PostgresCanonicalContentModelTests(unittest.TestCase):
    """The same observable result on the second supported engine."""

    def _publish(self, store, project_id, name):
        return store.publish_canonical_set_revision(
            project_id=project_id,
            name=name,
            data_class_key="real",
            timezone="UTC",
            signals=[dict(INFLOW_SIGNAL), dict(DEMAND_SIGNAL)],
            periods=[dict(period) for period in TWO_HOURS],
            values={
                "inflow_node_a": [12.5, 13.25],
                "demand_plant_a": [40.0, 41.0],
            },
            source={
                "source_key": f"{name}:source",
                "kind": "api",
                "checksum": "sha256:fixture",
            },
            actor="internal_analyst",
        )

    def test_postgres_seals_the_same_content_under_the_ts_next_schema(self):
        name = f"Afluentes {uuid.uuid4().hex[:8]}"
        sqlite_store = AnalystStore("sqlite:///:memory:")
        try:
            sqlite_receipt = self._publish(
                sqlite_store,
                sqlite_store.create_project(name="Cuenca Norte")["id"],
                name,
            )
        finally:
            sqlite_store.close()

        store = AnalystStore(POSTGRES_TEST_DATABASE_URL)
        try:
            project = store.create_project(name=f"TS7-002 {uuid.uuid4().hex[:8]}")
            receipt = self._publish(store, project["id"], name)
            schemas = sorted(
                row["table_schema"]
                for row in store.connection.execute(
                    """
                    SELECT DISTINCT table_schema
                    FROM information_schema.tables
                    WHERE table_name IN (
                        'time_series_sets', 'time_series_signals',
                        'time_series_set_revisions', 'time_series_periods',
                        'time_series_values', 'time_series_revision_signals',
                        'time_series_revision_lineage'
                    )
                    """
                ).fetchall()
            )
            revision = store.read_canonical_revision(receipt["revision_id"])
            set_view = store.read_canonical_set(receipt["set_id"])
        finally:
            store.close()

        self.assertEqual(
            {
                "hash_matches_sqlite": (
                    receipt["content_hash"] == sqlite_receipt["content_hash"]
                ),
                "state": receipt["state"],
                "counts": (
                    receipt["signal_count"],
                    receipt["period_count"],
                    receipt["value_count"],
                ),
                "source_registered": receipt["time_series_source_id"] is not None,
                "schemas": schemas,
                "values": revision["values"],
                "current_points_at_revision": (
                    set_view["current_revision_id"] == receipt["revision_id"]
                ),
            },
            {
                "hash_matches_sqlite": True,
                "state": "sealed",
                "counts": (2, 2, 4),
                "source_registered": True,
                "schemas": ["public", "ts_next"],
                "values": {
                    "inflow_node_a": [12.5, 13.25],
                    "demand_plant_a": [40.0, 41.0],
                },
                "current_points_at_revision": True,
            },
        )

    def test_postgres_refuses_the_same_forbidden_writes_by_the_same_name(self):
        store = AnalystStore(POSTGRES_TEST_DATABASE_URL)
        try:
            project = store.create_project(name=f"TS7-002 {uuid.uuid4().hex[:8]}")
            receipt = self._publish(store, project["id"], f"Guards {uuid.uuid4().hex[:8]}")
            tables = store.canonical_table_names()
            connection = store.connection
            data_class_id = int(
                connection.execute(
                    "SELECT id FROM time_series_data_classes "
                    "WHERE data_class_key = 'real'"
                ).fetchone()["id"]
            )
            building_id = int(
                connection.execute(
                    f"""
                    INSERT INTO {tables['time_series_set_revisions']} (
                        time_series_set_id, revision_number, data_class_id,
                        timezone, state, created_at, created_by
                    ) VALUES (?, 99, ?, 'UTC', 'building',
                              '2026-01-01T00:00:00', 'test')
                    RETURNING id
                    """,
                    (receipt["set_id"], data_class_id),
                ).fetchone()["id"]
            )
            outcomes = {
                "revision_update": attempt(
                    connection,
                    f"UPDATE {tables['time_series_set_revisions']} "
                    "SET change_summary = 'rewritten' WHERE id = ?",
                    (receipt["revision_id"],),
                ),
                "revision_delete": attempt(
                    connection,
                    f"DELETE FROM {tables['time_series_set_revisions']} WHERE id = ?",
                    (receipt["revision_id"],),
                ),
                "value_update": attempt(
                    connection,
                    f"UPDATE {tables['time_series_values']} "
                    "SET value_numeric = 99 WHERE set_revision_id = ?",
                    (receipt["revision_id"],),
                ),
                "value_delete": attempt(
                    connection,
                    f"DELETE FROM {tables['time_series_values']} "
                    "WHERE set_revision_id = ?",
                    (receipt["revision_id"],),
                ),
                "period_update": attempt(
                    connection,
                    f"UPDATE {tables['time_series_periods']} "
                    "SET duration_hours = 2 WHERE set_revision_id = ?",
                    (receipt["revision_id"],),
                ),
                "point_at_building": attempt(
                    connection,
                    f"UPDATE {tables['time_series_sets']} "
                    "SET current_revision_id = ? WHERE id = ?",
                    (building_id, receipt["set_id"]),
                ),
                "redirect_identity": attempt(
                    connection,
                    f"UPDATE {tables['time_series_signals']} "
                    "SET series_key = 'redirected' WHERE id = ?",
                    (receipt["signal_ids"]["inflow_node_a"],),
                ),
            }
            revision = store.read_canonical_revision(receipt["revision_id"])
            set_view = store.read_canonical_set(receipt["set_id"])
        finally:
            store.close()

        self.assertEqual(
            {
                "outcomes": outcomes,
                "content_hash_unchanged": (
                    revision["content_hash"] == receipt["content_hash"]
                ),
                "values": revision["values"]["inflow_node_a"],
                "current_revision_id": set_view["current_revision_id"],
            },
            {
                "outcomes": {
                    "revision_update": "TS_REVISION_SEALED",
                    "revision_delete": "TS_REVISION_SEALED",
                    "value_update": "TS_REVISION_SEALED",
                    "value_delete": "TS_REVISION_SEALED",
                    "period_update": "TS_REVISION_SEALED",
                    "point_at_building": "TS_REVISION_NOT_SEALED",
                    "redirect_identity": "TS_SIGNAL_IDENTITY_IMMUTABLE",
                },
                "content_hash_unchanged": True,
                "values": [12.5, 13.25],
                "current_revision_id": receipt["revision_id"],
            },
        )


if __name__ == "__main__":
    unittest.main()
