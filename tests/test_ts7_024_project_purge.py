"""TS7-024 deleting a project purges the TS-7 trail it owns.

Chapter 9.6 makes every historical foreign key restrictive so no ordinary write
loses sealed history. Deleting the project itself is the one lifecycle event
that ends that retention, and it is the only door through which the canonical
trail may be removed; see
``docs/series_tiempo/iter7/decision_record_ts7_project_purge.md``.
"""

import os
import unittest
import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.auth import hash_password
from app.main import create_app
from app.persistence import AnalystStore
from app.time_series_canonical import project_purge_scope_table_name
from app.time_series_links import LINK_LEDGER_IMMUTABLE
from app.time_series_purge import canonical_trail_statements
from tests.auth_test_helpers import (
    csrf_headers,
    login_json_with_csrf,
    post_json_with_csrf,
)


POSTGRES_TEST_DATABASE_URL = os.environ.get("POSTGRES_TEST_DATABASE_URL")

PRICE_SIGNAL = {
    "series_key": "energy_price",
    "display_name": "Precio de energia",
    "semantic_type_key": "energy_price",
    "unit_key": "usd_per_mwh",
    "signal_role": "input",
    "aggregation": "mean",
}
INFLOW_SIGNAL = {
    "series_key": "inflow_node_a",
    "display_name": "Afluente nodo A",
    "semantic_type_key": "natural_inflow",
    "unit_key": "m3_per_s",
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


class CanonicalTrailPurgeTests(unittest.TestCase):
    """The sealed content a project owns leaves with the project."""

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

    def _canonical_counts(self) -> dict[str, int]:
        return {
            logical: int(
                self.store.connection.execute(
                    f"SELECT COUNT(*) AS total FROM {physical}"
                ).fetchone()["total"]
            )
            for logical, physical in self.store.canonical_table_names().items()
        }

    def test_deleting_a_project_leaves_no_canonical_row_behind(self):
        self._publish()
        populated = self._canonical_counts()

        self.store.delete_project(self.project["id"])

        self.assertEqual(
            {
                "had_content_before": sorted(
                    logical for logical, total in populated.items() if total
                ),
                "remaining": self._canonical_counts(),
                "projects": int(
                    self.store.connection.execute(
                        "SELECT COUNT(*) AS total FROM projects"
                    ).fetchone()["total"]
                ),
            },
            {
                "had_content_before": [
                    "time_series_periods",
                    "time_series_revision_signals",
                    "time_series_set_revisions",
                    "time_series_sets",
                    "time_series_signals",
                    "time_series_values",
                ],
                "remaining": {
                    "time_series_periods": 0,
                    "time_series_revision_lineage": 0,
                    "time_series_revision_signals": 0,
                    "time_series_set_revisions": 0,
                    "time_series_sets": 0,
                    "time_series_signals": 0,
                    "time_series_sources": 0,
                    "time_series_values": 0,
                },
                "projects": 0,
            },
        )


class AssociatedProjectFixture(unittest.TestCase):
    """One project that has associated a catalog signal with one of its objects.

    The commit leaves an association plus the validation and event rows its two
    ledgers recorded, which is the smallest state in which both the purge and
    the immutability of a ledger can be observed at all.
    """

    def setUp(self):
        self.store = AnalystStore("sqlite:///:memory:")
        self.client = TestClient(create_app(store=self.store, auth_enabled=True))
        self.store.create_user(
            email="analyst@example.local",
            display_name="Analyst",
            role="analyst",
            password_hash=hash_password("analyst pass"),
        )
        login = login_json_with_csrf(
            self.client, "analyst@example.local", "analyst pass"
        )
        self.assertEqual(login.status_code, 200, login.text)
        self.project = self.store.create_project(name="Cuenca Norte")
        self.store.publish_canonical_set_revision(
            project_id=self.project["id"],
            name="Inputs 2026",
            data_class_key="real",
            timezone="UTC",
            signals=[dict(PRICE_SIGNAL)],
            periods=[dict(TWO_HOURS[0])],
            values={"energy_price": [70.0]},
            actor="analyst@example.local",
        )
        self.signal_id = self.client.get(
            "/api/time-series/catalog/inputs"
        ).json()["items"][0]["signal_id"]
        self.object = self.store.ensure_global_signal_slot(
            project_id=self.project["id"], display_name="Sistema"
        )
        self._associate()

    def tearDown(self):
        self.store.close()

    def _associate(self):
        request = {
            "target_project_id": self.project["id"],
            "operations": [
                {
                    "client_operation_id": "op-add-price",
                    "action": "add",
                    "signal_id": self.signal_id,
                    "linkable_object_id": self.object["id"],
                    "binding_role_key": "grid_import_price",
                    "expected_absent": True,
                    "reason_code": "catalog_association_requested",
                }
            ],
        }
        prevalidation = post_json_with_csrf(
            self.client,
            "/api/time-series/catalog/association-prevalidations",
            request,
        )
        self.assertEqual(prevalidation.status_code, 200, prevalidation.text)
        token = prevalidation.json()
        committed = self.client.post(
            "/api/time-series/catalog/association-batches",
            json={
                **request,
                "prevalidation_token": token["prevalidation_token"],
                "confirmed": True,
            },
            headers={
                **csrf_headers(self.client),
                "If-Match": token["commit_etag"],
                "Idempotency-Key": "purge-association",
                "X-Request-Id": "req-purge-association",
            },
        )
        self.assertEqual(committed.status_code, 201, committed.text)

class LinkLayerPurgeTests(AssociatedProjectFixture):
    """The links a project made, and the ledgers that recorded them, leave too."""

    def _link_counts(self) -> dict[str, int]:
        return {
            logical: int(
                self.store.connection.execute(
                    f"SELECT COUNT(*) AS total FROM {physical}"
                ).fetchone()["total"]
            )
            for logical, physical in self.store.link_layer_table_names().items()
        }

    def test_deleting_a_project_takes_its_links_and_ledgers(self):
        populated = self._link_counts()

        self.store.delete_project(self.project["id"])

        self.assertEqual(
            {
                "had_links_before": sorted(
                    logical for logical, total in populated.items() if total
                ),
                "remaining": self._link_counts(),
            },
            {
                "had_links_before": [
                    "time_series_catalog_associations",
                    "time_series_link_events",
                    "time_series_link_validations",
                ],
                "remaining": {
                    "case_time_series_bindings": 0,
                    "time_series_catalog_associations": 0,
                    "time_series_link_events": 0,
                    "time_series_link_validations": 0,
                    "time_series_scope_events": 0,
                },
            },
        )


class NeighbourProjectTests(unittest.TestCase):
    """A purge is scoped to one project: the one beside it does not notice."""

    def setUp(self):
        self.store = AnalystStore("sqlite:///:memory:")
        self.leaving = self.store.create_project(name="Cuenca Norte")
        self.staying = self.store.create_project(name="Cuenca Sur")
        for project in (self.leaving, self.staying):
            self.store.publish_canonical_set_revision(
                project_id=project["id"],
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

    def _rows_of(self, project_id: int) -> dict[str, int]:
        sets = self.store.canonical_table_names()["time_series_sets"]
        revisions = self.store.canonical_table_names()["time_series_set_revisions"]
        values = self.store.canonical_table_names()["time_series_values"]
        counts = {}
        counts["sets"] = int(
            self.store.connection.execute(
                f"SELECT COUNT(*) AS total FROM {sets} WHERE owner_project_id = ?",
                (project_id,),
            ).fetchone()["total"]
        )
        counts["revisions"] = int(
            self.store.connection.execute(
                f"SELECT COUNT(*) AS total FROM {revisions}"
                f" WHERE time_series_set_id IN"
                f" (SELECT id FROM {sets} WHERE owner_project_id = ?)",
                (project_id,),
            ).fetchone()["total"]
        )
        counts["values"] = int(
            self.store.connection.execute(
                f"SELECT COUNT(*) AS total FROM {values}"
                f" WHERE set_revision_id IN (SELECT id FROM {revisions}"
                f" WHERE time_series_set_id IN"
                f" (SELECT id FROM {sets} WHERE owner_project_id = ?))",
                (project_id,),
            ).fetchone()["total"]
        )
        return counts

    def test_purging_one_project_leaves_the_other_untouched(self):
        before = self._rows_of(self.staying["id"])

        self.store.delete_project(self.leaving["id"])

        self.assertEqual(
            {
                "neighbour_before": before,
                "neighbour_after": self._rows_of(self.staying["id"]),
                "purged": self._rows_of(self.leaving["id"]),
                "projects_left": [
                    row["name"]
                    for row in self.store.connection.execute(
                        "SELECT name FROM projects ORDER BY id"
                    ).fetchall()
                ],
            },
            {
                "neighbour_before": {"sets": 1, "revisions": 1, "values": 2},
                "neighbour_after": {"sets": 1, "revisions": 1, "values": 2},
                "purged": {"sets": 0, "revisions": 0, "values": 0},
                "projects_left": ["Cuenca Sur"],
            },
        )


class ImmutabilityOutsideAPurgeTests(unittest.TestCase):
    """The hatch opens DELETE for a declared purge, and nothing else at all."""

    def setUp(self):
        self.store = AnalystStore("sqlite:///:memory:")
        self.project = self.store.create_project(name="Cuenca Norte")
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
        self.tables = self.store.canonical_table_names()

    def tearDown(self):
        self.store.close()

    def _open_purge(self):
        scope = project_purge_scope_table_name(self.store.database_backend)
        self.store.connection.execute(
            f"INSERT INTO {scope} (project_id, opened_at, opened_by)"
            " VALUES (?, ?, ?)",
            (self.project["id"], "2026-09-07T00:00:00", "internal_analyst"),
        )

    def test_a_sealed_revision_still_refuses_deletion_with_no_purge_declared(self):
        with self.assertRaisesRegex(Exception, "TS_REVISION_SEALED"):
            self.store.connection.execute(
                f"DELETE FROM {self.tables['time_series_set_revisions']}"
            )

    def test_the_values_of_a_sealed_revision_still_refuse_deletion(self):
        with self.assertRaisesRegex(Exception, "TS_REVISION_SEALED"):
            self.store.connection.execute(
                f"DELETE FROM {self.tables['time_series_values']}"
            )

    def test_an_open_purge_does_not_make_a_sealed_revision_writable(self):
        self._open_purge()

        with self.assertRaisesRegex(Exception, "TS_REVISION_SEALED"):
            self.store.connection.execute(
                f"UPDATE {self.tables['time_series_set_revisions']}"
                " SET change_summary = 'rewritten'"
            )

    def test_an_open_purge_does_not_make_a_signal_identity_movable(self):
        self._open_purge()

        with self.assertRaisesRegex(Exception, "TS_SIGNAL_IDENTITY_IMMUTABLE"):
            self.store.connection.execute(
                f"UPDATE {self.tables['time_series_signals']}"
                " SET series_key = 'moved'"
            )


class LedgerImmutabilityOutsideAPurgeTests(AssociatedProjectFixture):
    """The three audit ledgers keep refusing every write that is not a purge."""

    @property
    def events(self) -> str:
        return self.store.link_layer_table_names()["time_series_link_events"]

    def test_the_link_event_ledger_still_refuses_deletion(self):
        with self.assertRaisesRegex(Exception, LINK_LEDGER_IMMUTABLE):
            self.store.connection.execute(f"DELETE FROM {self.events}")

    def test_the_link_event_ledger_still_refuses_rewriting_during_a_purge(self):
        scope = project_purge_scope_table_name(self.store.database_backend)
        self.store.connection.execute(
            f"INSERT INTO {scope} (project_id, opened_at, opened_by)"
            " VALUES (?, ?, ?)",
            (1, "2026-09-07T00:00:00", "internal_analyst"),
        )

        with self.assertRaisesRegex(Exception, LINK_LEDGER_IMMUTABLE):
            self.store.connection.execute(
                f"UPDATE {self.events} SET reason_code = 'rewritten'"
            )


class DeleteProjectApiTests(AssociatedProjectFixture):
    """The route the web page calls answers instead of failing (TS7-024)."""

    def test_deleting_a_project_with_a_ts7_trail_answers_the_deleted_project(self):
        response = self.client.delete(
            f"/api/projects/{self.project['id']}",
            headers=csrf_headers(self.client),
        )

        self.assertEqual(response.status_code, 200, response.text)
        deleted = response.json()["deleted_project"]
        self.assertEqual(
            {
                "id": deleted["id"],
                "name": deleted["name"],
                "deleted_time_series_set_count": deleted[
                    "deleted_time_series_set_count"
                ],
                "listed_after": self.client.get("/api/projects").json()["projects"],
            },
            {
                "id": self.project["id"],
                "name": "Cuenca Norte",
                "deleted_time_series_set_count": 1,
                "listed_after": [],
            },
        )


class ValidationDependencyPurgeTests(unittest.TestCase):
    """The staleness ledger names its owner polymorphically, so no key sees it.

    ``validation_dependencies`` records what a variant or a set was validated
    against through ``owner_type``/``owner_id`` instead of a foreign key, which
    means nothing refuses a delete that strands it and nothing cascades it away.
    The rows are seeded directly here because the writers that produce them sit
    behind run materialization and console saves; what is under test is that the
    purge clears them, not how they came to be.
    """

    def setUp(self):
        self.store = AnalystStore("sqlite:///:memory:")
        self.project = self.store.create_project(name="Cuenca Norte")
        scenario = self.store.create_scenario(
            project_id=self.project["id"], name="Escenario base"
        )
        case = self.store.get_or_create_case_for_scenario(scenario["id"])
        self.variant = self.store.get_or_create_default_input_variant(case["id"])
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
        for owner_type, owner_id in (
            ("case_input_variant", self.variant["id"]),
            ("time_series_set", self.receipt["set_id"]),
        ):
            self.store.connection.execute(
                """
                INSERT INTO validation_dependencies (
                    owner_type, owner_id, dependency_type, dependency_id,
                    recorded_hash, created_at, updated_at
                )
                VALUES (?, ?, 'time_series_set', ?, 'sha256:seed', ?, ?)
                """,
                (
                    owner_type,
                    owner_id,
                    str(self.receipt["set_id"]),
                    "2026-09-07T00:00:00",
                    "2026-09-07T00:00:00",
                ),
            )
        self.store.connection.commit()

    def tearDown(self):
        self.store.close()

    def _dependency_owners(self) -> list[str]:
        return [
            f"{row['owner_type']}:{row['owner_id']}"
            for row in self.store.connection.execute(
                "SELECT owner_type, owner_id FROM validation_dependencies"
                " ORDER BY owner_type, owner_id"
            ).fetchall()
        ]

    def test_the_purge_takes_the_dependencies_of_its_variants_and_sets(self):
        before = self._dependency_owners()

        self.store.delete_project(self.project["id"])

        self.assertEqual(
            {"before": before, "after": self._dependency_owners()},
            {
                "before": [
                    f"case_input_variant:{self.variant['id']}",
                    f"time_series_set:{self.receipt['set_id']}",
                ],
                "after": [],
            },
        )


class InterruptedPurgeTests(unittest.TestCase):
    """A purge that fails halfway leaves the project exactly as it was."""

    def setUp(self):
        self.store = AnalystStore("sqlite:///:memory:")
        self.project = self.store.create_project(name="Cuenca Norte")
        self.store.publish_canonical_set_revision(
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

    def _counts(self) -> dict[str, int]:
        counts = {
            logical: int(
                self.store.connection.execute(
                    f"SELECT COUNT(*) AS total FROM {physical}"
                ).fetchone()["total"]
            )
            for logical, physical in self.store.canonical_table_names().items()
        }
        counts["projects"] = int(
            self.store.connection.execute(
                "SELECT COUNT(*) AS total FROM projects"
            ).fetchone()["total"]
        )
        counts["purge_scope"] = int(
            self.store.connection.execute(
                "SELECT COUNT(*) AS total FROM "
                + project_purge_scope_table_name(self.store.database_backend)
            ).fetchone()["total"]
        )
        return counts

    def test_a_failure_halfway_through_restores_the_whole_trail(self):
        before = self._counts()
        statements = canonical_trail_statements(self.store.database_backend)
        half = statements[: len(statements) // 2] + ["DELETE FROM table_that_is_not_there"]

        with patch(
            "app.persistence.canonical_trail_statements", return_value=half
        ):
            with self.assertRaises(Exception):
                self.store.delete_project(self.project["id"])

        self.assertEqual(
            {"before": before, "after": self._counts()},
            {"before": before, "after": before},
        )
        self.assertEqual(before["purge_scope"], 0)
        self.assertEqual(before["projects"], 1)


@unittest.skipUnless(
    POSTGRES_TEST_DATABASE_URL,
    "set POSTGRES_TEST_DATABASE_URL to mirror the purge on PostgreSQL",
)
class PostgresProjectPurgeTests(unittest.TestCase):
    """The same closure on the production-reference engine.

    PostgreSQL is where the defect actually bites: its restrictive foreign keys
    and its plpgsql guards are the two things the SQLite mirror can only
    approximate. The whole case runs inside a transaction that always rolls
    back, so it can be pointed at a populated database without touching it.
    """

    def setUp(self):
        self.store = AnalystStore(POSTGRES_TEST_DATABASE_URL)
        self.rollback = self.store.connection._connection.transaction(  # noqa: SLF001
            force_rollback=True
        )
        self.rollback.__enter__()
        suffix = uuid.uuid4().hex[:10]
        self.project = self.store.create_project(name=f"TS7-024 {suffix}")
        self.store.publish_canonical_set_revision(
            project_id=self.project["id"],
            name=f"Afluentes {suffix}",
            data_class_key="real",
            timezone="UTC",
            signals=[dict(INFLOW_SIGNAL)],
            periods=[dict(period) for period in TWO_HOURS],
            values={"inflow_node_a": [12.5, 13.25]},
            actor="internal_analyst",
        )

    def tearDown(self):
        try:
            self.rollback.__exit__(None, None, None)
        finally:
            self.store.close()

    def _owned_counts(self) -> dict[str, int]:
        tables = self.store.canonical_table_names()
        sets = tables["time_series_sets"]
        revisions = tables["time_series_set_revisions"]
        return {
            "sets": int(
                self.store.connection.execute(
                    f"SELECT COUNT(*) AS total FROM {sets} WHERE owner_project_id = ?",
                    (self.project["id"],),
                ).fetchone()["total"]
            ),
            "revisions": int(
                self.store.connection.execute(
                    f"SELECT COUNT(*) AS total FROM {revisions}"
                    f" WHERE time_series_set_id IN"
                    f" (SELECT id FROM {sets} WHERE owner_project_id = ?)",
                    (self.project["id"],),
                ).fetchone()["total"]
            ),
        }

    def test_the_project_and_its_canonical_trail_leave_together(self):
        before = self._owned_counts()

        deleted = self.store.delete_project(self.project["id"])

        self.assertEqual(
            {
                "before": before,
                "after": self._owned_counts(),
                "deleted_sets": deleted["deleted_time_series_set_count"],
                "project_rows": int(
                    self.store.connection.execute(
                        "SELECT COUNT(*) AS total FROM projects WHERE id = ?",
                        (self.project["id"],),
                    ).fetchone()["total"]
                ),
                "purge_scope": int(
                    self.store.connection.execute(
                        "SELECT COUNT(*) AS total FROM "
                        + project_purge_scope_table_name("postgresql")
                    ).fetchone()["total"]
                ),
            },
            {
                "before": {"sets": 1, "revisions": 1},
                "after": {"sets": 0, "revisions": 0},
                "deleted_sets": 1,
                "project_rows": 0,
                "purge_scope": 0,
            },
        )

    def test_a_sealed_revision_still_refuses_deletion_with_no_purge_declared(self):
        revisions = self.store.canonical_table_names()["time_series_set_revisions"]
        sets = self.store.canonical_table_names()["time_series_sets"]

        with self.assertRaisesRegex(Exception, "TS_REVISION_SEALED"):
            self.store.connection.execute(
                f"DELETE FROM {revisions} WHERE time_series_set_id IN"
                f" (SELECT id FROM {sets} WHERE owner_project_id = ?)",
                (self.project["id"],),
            )


if __name__ == "__main__":
    unittest.main()
