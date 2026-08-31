"""TS7-005 transactional catalog projection, keyset pages and idempotency."""

import os
import unittest
import uuid

from app.persistence import AnalystStore
from app.time_series_catalog_fixture import fixture_plan
from app.time_series_canonical import CanonicalRevisionError
from app.time_series_catalog_projection import CatalogQueryError


POSTGRES_TEST_DATABASE_URL = os.environ.get("POSTGRES_TEST_DATABASE_URL")


class CatalogProjectionSpaceTests(unittest.TestCase):
    def setUp(self):
        self.store = AnalystStore("sqlite:///:memory:")

    def tearDown(self):
        self.store.close()

    def test_the_projection_and_its_counters_land_in_the_canonical_space(self):
        physical_names = self.store.catalog_projection_table_names()
        tables = {
            row["name"]
            for row in self.store.connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }

        self.assertEqual(
            {
                "physical_names": physical_names,
                "missing": sorted(set(physical_names.values()) - tables),
                "legacy_signals_survive": "time_series_signals" in tables,
            },
            {
                "physical_names": {
                    "time_series_catalog_entries": "time_series_catalog_entries_next",
                    "time_series_catalog_generations": (
                        "time_series_catalog_generations_next"
                    ),
                    "time_series_operation_idempotency": (
                        "time_series_operation_idempotency_next"
                    ),
                },
                "missing": [],
                "legacy_signals_survive": True,
            },
        )


HOURLY_SIGNALS = [
    {
        "series_key": "energy_price",
        "display_name": "Precio de energia",
        "semantic_type_key": "energy_price",
        "unit_key": "usd_per_mwh",
        "signal_role": "input",
        "aggregation": "mean",
    },
    {
        "series_key": "inflow_node_a",
        "display_name": "Caudal afluente Nodo A",
        "semantic_type_key": "hydro_inflow",
        "unit_key": "m3_per_s",
        "signal_role": "input",
        "aggregation": "mean",
    },
]


def hourly_periods(count, *, start_hour=0):
    return [
        {
            "timestamp_start": f"2026-01-01T{start_hour + index:02d}:00:00",
            "timestamp_end": f"2026-01-01T{start_hour + index + 1:02d}:00:00",
            "duration_hours": 1.0,
        }
        for index in range(count)
    ]


class ProjectionMembershipTests(unittest.TestCase):
    def setUp(self):
        self.store = AnalystStore("sqlite:///:memory:")
        self.project = self.store.create_project(name="Cuenca Norte")

    def tearDown(self):
        self.store.close()

    def _entries(self):
        entries = self.store.catalog_projection_table_names()[
            "time_series_catalog_entries"
        ]
        return [
            dict(row)
            for row in self.store.connection.execute(
                f"SELECT * FROM {entries} ORDER BY series_key"
            ).fetchall()
        ]

    def test_publishing_projects_one_row_per_catalog_signal(self):
        receipt = self.store.publish_canonical_set_revision(
            project_id=self.project["id"],
            name="Precios 2026",
            data_class_key="real",
            timezone="UTC",
            signals=HOURLY_SIGNALS,
            periods=hourly_periods(3),
            values={
                "energy_price": [70.0, 71.0, 72.0],
                "inflow_node_a": [10.0, 11.0, 12.0],
            },
            actor="internal_analyst",
        )

        entries = self._entries()

        self.assertEqual(
            {
                "series_keys": [entry["series_key"] for entry in entries],
                "first": {
                    key: entries[0][key]
                    for key in (
                        "time_series_set_id",
                        "series_kind",
                        "owner_project_id",
                        "visibility_scope",
                        "set_status",
                        "signal_status",
                        "display_name",
                        "display_name_sort",
                        "semantic_type_key",
                        "data_class_key",
                        "unit_key",
                        "source_kind",
                        "current_revision_id",
                        "revision_number",
                        "coverage_start",
                        "coverage_end",
                        "period_count",
                        "value_count",
                        "nominal_resolution_seconds",
                        "regularity",
                        "association_count",
                        "binding_count",
                        "projection_revision",
                    )
                },
            },
            {
                "series_keys": ["energy_price", "inflow_node_a"],
                "first": {
                    "time_series_set_id": receipt["set_id"],
                    "series_kind": "catalog",
                    "owner_project_id": self.project["id"],
                    "visibility_scope": "project",
                    "set_status": "validated",
                    "signal_status": "active",
                    "display_name": "Precio de energia",
                    "display_name_sort": "precio de energia",
                    "semantic_type_key": "energy_price",
                    "data_class_key": "real",
                    "unit_key": "usd_per_mwh",
                    "source_kind": "api",
                    "current_revision_id": receipt["revision_id"],
                    "revision_number": 1,
                    "coverage_start": "2026-01-01T00:00:00",
                    "coverage_end": "2026-01-01T03:00:00",
                    "period_count": 3,
                    "value_count": 3,
                    "nominal_resolution_seconds": 3600.0,
                    "regularity": "regular",
                    "association_count": 0,
                    "binding_count": 0,
                    "projection_revision": 1,
                },
            },
        )

    def test_a_failed_publication_leaves_no_stale_projection_row(self):
        first = self.store.publish_canonical_set_revision(
            project_id=self.project["id"],
            name="Precios 2026",
            data_class_key="real",
            timezone="UTC",
            signals=HOURLY_SIGNALS,
            periods=hourly_periods(3),
            values={
                "energy_price": [70.0, 71.0, 72.0],
                "inflow_node_a": [10.0, 11.0, 12.0],
            },
            actor="internal_analyst",
        )

        with self.assertRaises(CanonicalRevisionError) as refusal:
            self.store.publish_canonical_set_revision(
                project_id=self.project["id"],
                name="Precios 2026",
                data_class_key="real",
                timezone="UTC",
                signals=HOURLY_SIGNALS,
                periods=hourly_periods(4),
                values={
                    "energy_price": [70.0, 71.0, 72.0, 73.0],
                    "inflow_node_a": [10.0, 11.0, 12.0],
                },
                actor="internal_analyst",
            )

        revisions = self.store.canonical_table_names()["time_series_set_revisions"]
        entries = self._entries()
        self.assertEqual(
            {
                "code": refusal.exception.code,
                "revision_count": int(
                    self.store.connection.execute(
                        f"SELECT COUNT(*) AS total FROM {revisions} "
                        "WHERE time_series_set_id = ?",
                        (first["set_id"],),
                    ).fetchone()["total"]
                ),
                "projected_revisions": sorted(
                    {entry["current_revision_id"] for entry in entries}
                ),
                "projected_period_counts": sorted(
                    {entry["period_count"] for entry in entries}
                ),
            },
            {
                "code": "TS_REVISION_VALUE_COUNT_MISMATCH",
                "revision_count": 1,
                "projected_revisions": [first["revision_id"]],
                "projected_period_counts": [3],
            },
        )


def attempt(connection, sql, parameters=()):
    """Report only the observable result of a direct integrity write."""

    try:
        connection.execute(sql, parameters)
    except Exception:  # noqa: BLE001 - the database engine owns the exception type
        return "refused"
    return "accepted"


def build_object_specific_signal(store, project_id, object_id, *, signal_id):
    """Create an object-scoped set and its single signal without the writer."""

    canonical = store.canonical_table_names()
    now = "2026-01-01T00:00:00"
    set_id = int(
        store.connection.execute(
            f"""
            INSERT INTO {canonical['time_series_sets']} (
                owner_project_id, name, version_number, version_label,
                visibility_scope, series_kind, owner_linkable_object_id,
                object_series_key, object_specific_signal_id, status,
                created_at, updated_at, created_by, updated_by
            ) VALUES (?, 'local_price', 1, 'object', 'project',
                      'object_specific', ?, 'local_price', ?, 'draft',
                      ?, ?, 'test', 'test')
            RETURNING id
            """,
            (project_id, object_id, signal_id, now, now),
        ).fetchone()["id"]
    )
    store.connection.execute(
        f"""
        INSERT INTO {canonical['time_series_signals']} (
            id, time_series_set_id, series_kind, series_key, display_name,
            created_at, created_by
        ) VALUES (?, ?, 'object_specific', 'local_price', 'Precio local',
                  ?, 'test')
        """,
        (signal_id, set_id, now),
    )
    return set_id


class ProjectionCatalogBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.store = AnalystStore("sqlite:///:memory:")
        self.project = self.store.create_project(name="Cuenca Norte")
        self.object = self.store.ensure_global_signal_slot(
            project_id=self.project["id"]
        )

    def tearDown(self):
        self.store.close()

    def test_an_object_specific_signal_cannot_enter_the_projection(self):
        signal_id = 100_001
        set_id = build_object_specific_signal(
            self.store, self.project["id"], self.object["id"], signal_id=signal_id
        )
        entries = self.store.catalog_projection_table_names()[
            "time_series_catalog_entries"
        ]
        insert = f"""
            INSERT INTO {entries} (
                signal_id, time_series_set_id, series_kind, owner_project_id,
                owner_project_name_sort, visibility_scope, set_status,
                signal_status, series_key, display_name, display_name_sort,
                search_text_normalized, semantic_type_id, semantic_type_key,
                data_class_id, data_class_key, unit_id, unit_key, source_kind,
                current_revision_id, revision_number, coverage_start,
                coverage_end, period_count, value_count,
                nominal_resolution_seconds, min_resolution_seconds,
                max_resolution_seconds, regularity, updated_at
            ) VALUES (?, ?, ?, ?, 'cuenca norte', 'project', 'draft', 'active',
                      'local_price', 'Precio local', 'precio local',
                      'precio local', 1, 'energy_price', 1, 'real', 1,
                      'usd_per_mwh', 'api', 1, 1, '2026-01-01T00:00:00',
                      '2026-01-01T01:00:00', 1, 1, 3600.0, 3600.0, 3600.0,
                      'regular', '2026-01-01T00:00:00')
        """

        outcomes = {
            "pretend_catalog": attempt(
                self.store.connection,
                insert,
                (signal_id, set_id, "catalog"),
            ),
            "declare_object_specific": attempt(
                self.store.connection,
                insert,
                (signal_id, set_id, "object_specific"),
            ),
        }

        self.assertEqual(
            outcomes,
            {
                "pretend_catalog": "refused",
                "declare_object_specific": "refused",
            },
        )


class CatalogGenerationTests(unittest.TestCase):
    def setUp(self):
        self.store = AnalystStore("sqlite:///:memory:")
        self.project = self.store.create_project(name="Cuenca Norte")

    def tearDown(self):
        self.store.close()

    def _publish(self, *, name="Precios 2026", periods=3, first_value=70.0):
        return self.store.publish_canonical_set_revision(
            project_id=self.project["id"],
            name=name,
            data_class_key="real",
            timezone="UTC",
            signals=HOURLY_SIGNALS,
            periods=hourly_periods(periods),
            values={
                "energy_price": [
                    first_value + index for index in range(periods)
                ],
                "inflow_node_a": [10.0 + index for index in range(periods)],
            },
            actor="internal_analyst",
        )

    def test_each_publication_raises_the_section_generation_exactly_once(self):
        start = self.store.catalog_generation()
        self._publish()
        after_first = self.store.catalog_generation()
        self._publish(first_value=80.0)
        after_second = self.store.catalog_generation()
        self._publish(name="Caudales 2026")
        after_third = self.store.catalog_generation()

        self.assertEqual(
            {
                "start": start,
                "after_first": after_first,
                "after_second": after_second,
                "after_third": after_third,
            },
            {"start": 0, "after_first": 1, "after_second": 2, "after_third": 3},
        )

    def test_republishing_identical_content_changes_nothing(self):
        first = self._publish()
        second = self._publish()

        revisions = self.store.canonical_table_names()["time_series_set_revisions"]
        entries = self.store.catalog_projection_table_names()[
            "time_series_catalog_entries"
        ]
        set_view = self.store.read_canonical_set(first["set_id"])
        self.assertEqual(
            {
                "first_outcome": first["outcome"],
                "second_outcome": second["outcome"],
                "same_revision": second["revision_id"] == first["revision_id"],
                "same_hash": second["content_hash"] == first["content_hash"],
                "revision_count": int(
                    self.store.connection.execute(
                        f"SELECT COUNT(*) AS total FROM {revisions} "
                        "WHERE time_series_set_id = ?",
                        (first["set_id"],),
                    ).fetchone()["total"]
                ),
                "current_revision_id": set_view["current_revision_id"],
                "generation": self.store.catalog_generation(),
                "projection_revisions": sorted(
                    {
                        int(row["projection_revision"])
                        for row in self.store.connection.execute(
                            f"SELECT projection_revision FROM {entries}"
                        ).fetchall()
                    }
                ),
            },
            {
                "first_outcome": "published",
                "second_outcome": "unchanged",
                "same_revision": True,
                "same_hash": True,
                "revision_count": 1,
                "current_revision_id": first["revision_id"],
                "generation": 1,
                "projection_revisions": [1],
            },
        )


class DurableIdempotencyTests(unittest.TestCase):
    def setUp(self):
        self.store = AnalystStore("sqlite:///:memory:")
        self.project = self.store.create_project(name="Cuenca Norte")

    def tearDown(self):
        self.store.close()

    def _publish(self, *, idempotency_key, periods=3, first_value=70.0):
        return self.store.publish_canonical_set_revision(
            project_id=self.project["id"],
            name="Precios 2026",
            data_class_key="real",
            timezone="UTC",
            signals=HOURLY_SIGNALS,
            periods=hourly_periods(periods),
            values={
                "energy_price": [first_value + index for index in range(periods)],
                "inflow_node_a": [10.0 + index for index in range(periods)],
            },
            actor="internal_analyst",
            idempotency_key=idempotency_key,
        )

    def test_a_retried_publish_returns_the_saved_result_without_writing_twice(self):
        first = self._publish(idempotency_key="publish-2026-01")
        second = self._publish(idempotency_key="publish-2026-01")

        revisions = self.store.canonical_table_names()["time_series_set_revisions"]
        values = self.store.canonical_table_names()["time_series_values"]
        idempotency = self.store.catalog_projection_table_names()[
            "time_series_operation_idempotency"
        ]
        self.assertEqual(
            {
                "converges": second == first,
                "revision_count": int(
                    self.store.connection.execute(
                        f"SELECT COUNT(*) AS total FROM {revisions} "
                        "WHERE time_series_set_id = ?",
                        (first["set_id"],),
                    ).fetchone()["total"]
                ),
                "value_count": int(
                    self.store.connection.execute(
                        f"SELECT COUNT(*) AS total FROM {values}"
                    ).fetchone()["total"]
                ),
                "generation": self.store.catalog_generation(),
                "idempotency_rows": [
                    (row["operation_kind"], row["state"], row["http_status"])
                    for row in self.store.connection.execute(
                        f"SELECT * FROM {idempotency}"
                    ).fetchall()
                ],
            },
            {
                "converges": True,
                "revision_count": 1,
                "value_count": 6,
                "generation": 1,
                "idempotency_rows": [
                    ("publish_set_revision", "completed", 201)
                ],
            },
        )

    def test_the_same_key_with_a_different_request_is_refused(self):
        first = self._publish(idempotency_key="publish-2026-01")

        with self.assertRaises(CanonicalRevisionError) as refusal:
            self._publish(idempotency_key="publish-2026-01", periods=4)

        revisions = self.store.canonical_table_names()["time_series_set_revisions"]
        self.assertEqual(
            {
                "code": refusal.exception.code,
                "field": refusal.exception.field,
                "revision_count": int(
                    self.store.connection.execute(
                        f"SELECT COUNT(*) AS total FROM {revisions} "
                        "WHERE time_series_set_id = ?",
                        (first["set_id"],),
                    ).fetchone()["total"]
                ),
                "generation": self.store.catalog_generation(),
            },
            {
                "code": "TS_IDEMPOTENCY_KEY_CONFLICT",
                "field": "idempotency_key",
                "revision_count": 1,
                "generation": 1,
            },
        )

    def test_the_same_key_over_a_different_body_is_refused(self):
        first = self.store.publish_canonical_set_revision(
            project_id=self.project["id"],
            name="Precios 2026",
            data_class_key="real",
            timezone="UTC",
            signals=HOURLY_SIGNALS,
            periods=hourly_periods(3),
            values={
                "energy_price": [70.0, 71.0, 72.0],
                "inflow_node_a": [10.0, 11.0, 12.0],
            },
            actor="internal_analyst",
            idempotency_key="publish-2026-01",
            request_fingerprint="sha256:body-a",
        )

        with self.assertRaises(CanonicalRevisionError) as refusal:
            self.store.publish_canonical_set_revision(
                project_id=self.project["id"],
                name="Precios 2026",
                data_class_key="real",
                timezone="UTC",
                signals=HOURLY_SIGNALS,
                periods=hourly_periods(3),
                values={
                    "energy_price": [80.0, 81.0, 82.0],
                    "inflow_node_a": [10.0, 11.0, 12.0],
                },
                actor="internal_analyst",
                idempotency_key="publish-2026-01",
                request_fingerprint="sha256:body-b",
            )

        revisions = self.store.canonical_table_names()["time_series_set_revisions"]
        self.assertEqual(
            {
                "code": refusal.exception.code,
                "revision_count": int(
                    self.store.connection.execute(
                        f"SELECT COUNT(*) AS total FROM {revisions} "
                        "WHERE time_series_set_id = ?",
                        (first["set_id"],),
                    ).fetchone()["total"]
                ),
                "generation": self.store.catalog_generation(),
            },
            {
                "code": "TS_IDEMPOTENCY_KEY_CONFLICT",
                "revision_count": 1,
                "generation": 1,
            },
        )


class CatalogKeysetPageTests(unittest.TestCase):
    def setUp(self):
        self.store = AnalystStore("sqlite:///:memory:")
        self.project = self.store.create_project(name="Cuenca Norte")
        for name in ("Precios 2026", "Caudales 2026", "Demanda 2026"):
            self.store.publish_canonical_set_revision(
                project_id=self.project["id"],
                name=name,
                data_class_key="real",
                timezone="UTC",
                signals=HOURLY_SIGNALS,
                periods=hourly_periods(3),
                values={
                    "energy_price": [70.0, 71.0, 72.0],
                    "inflow_node_a": [10.0, 11.0, 12.0],
                },
                actor="internal_analyst",
            )

    def tearDown(self):
        self.store.close()

    def _walk(self, *, limit, order=None):
        walked = []
        pages = 0
        cursor = None
        while True:
            page = self.store.read_catalog_page(
                limit=limit, order=order, cursor=cursor
            )
            pages += 1
            walked.extend(item["signal_id"] for item in page["items"])
            cursor = page["page"]["next_cursor"]
            if not page["page"]["has_more"]:
                return walked, pages, page

    def test_the_keyset_walks_every_row_once_in_a_total_order(self):
        whole = self.store.read_catalog_page(limit=200)
        walked, pages, last_page = self._walk(limit=2)

        self.assertEqual(
            {
                "whole_page_size": len(whole["items"]),
                "walked": walked,
                "walked_matches_whole": walked
                == [item["signal_id"] for item in whole["items"]],
                "pages": pages,
                "last_cursor": last_page["page"]["next_cursor"],
                "ordering": [
                    (item["display_name_sort"], item["series_key"])
                    for item in whole["items"]
                ],
                "meta": whole["meta"],
            },
            {
                "whole_page_size": 6,
                "walked": walked,
                "walked_matches_whole": True,
                "pages": 3,
                "last_cursor": None,
                "ordering": [
                    ("caudal afluente nodo a", "inflow_node_a"),
                    ("caudal afluente nodo a", "inflow_node_a"),
                    ("caudal afluente nodo a", "inflow_node_a"),
                    ("precio de energia", "energy_price"),
                    ("precio de energia", "energy_price"),
                    ("precio de energia", "energy_price"),
                ],
                "meta": {
                    "section": "inputs",
                    "catalog_generation": self.store.catalog_generation(),
                },
            },
        )

    def test_the_page_plan_touches_only_the_projection_and_an_index(self):
        plan = self.store.explain_catalog_page(limit=50)
        plan_text = " ".join(plan["plan"]).lower()

        self.assertEqual(
            {
                "engine": plan["engine"],
                "reads_periods": "time_series_periods" in plan_text,
                "reads_values": "time_series_values" in plan_text,
                "reads_signals": "time_series_signals" in plan_text,
                "reads_projection": "time_series_catalog_entries" in plan_text,
                "uses_an_index": "using index" in plan_text,
                "tables": plan["tables"],
            },
            {
                "engine": "sqlite",
                "reads_periods": False,
                "reads_values": False,
                "reads_signals": False,
                "reads_projection": True,
                "uses_an_index": True,
                "tables": ["time_series_catalog_entries_next"],
            },
        )

    def _refusal(self, **kwargs):
        try:
            self.store.read_catalog_page(**kwargs)
        except CatalogQueryError as error:
            return error.code
        return "accepted"

    def test_a_cursor_never_returns_a_silently_different_page(self):
        page = self.store.read_catalog_page(limit=2)
        cursor = page["page"]["next_cursor"]
        tampered = cursor[:-4] + ("aaaa" if cursor[-4:] != "aaaa" else "bbbb")

        outcomes = {
            "honest": len(
                self.store.read_catalog_page(limit=2, cursor=cursor)["items"]
            ),
            "tampered": self._refusal(limit=2, cursor=tampered),
            "other_order": self._refusal(
                limit=2, order="display_name", cursor=cursor
            ),
            "other_limit": self._refusal(limit=3, cursor=cursor),
        }

        self.store.publish_canonical_set_revision(
            project_id=self.project["id"],
            name="Precios 2027",
            data_class_key="real",
            timezone="UTC",
            signals=HOURLY_SIGNALS,
            periods=hourly_periods(3),
            values={
                "energy_price": [70.0, 71.0, 72.0],
                "inflow_node_a": [10.0, 11.0, 12.0],
            },
            actor="internal_analyst",
        )
        outcomes["after_publication"] = self._refusal(limit=2, cursor=cursor)

        self.assertEqual(
            outcomes,
            {
                "honest": 2,
                "tampered": "TS_QUERY_CURSOR_MISMATCH",
                "other_order": "TS_QUERY_CURSOR_MISMATCH",
                "other_limit": "TS_QUERY_CURSOR_MISMATCH",
                "after_publication": "TS_QUERY_SNAPSHOT_CHANGED",
            },
        )


class ProjectionReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.store = AnalystStore("sqlite:///:memory:")
        self.project = self.store.create_project(name="Cuenca Norte")
        self.receipt = self.store.publish_canonical_set_revision(
            project_id=self.project["id"],
            name="Precios 2026",
            data_class_key="real",
            timezone="UTC",
            signals=HOURLY_SIGNALS,
            periods=hourly_periods(3),
            values={
                "energy_price": [70.0, 71.0, 72.0],
                "inflow_node_a": [10.0, 11.0, 12.0],
            },
            actor="internal_analyst",
        )
        self.entries = self.store.catalog_projection_table_names()[
            "time_series_catalog_entries"
        ]

    def tearDown(self):
        self.store.close()

    def test_a_hand_edited_projection_is_reported_as_divergent(self):
        clean = self.store.catalog_projection_divergence()
        dropped = int(self.receipt["signal_ids"]["energy_price"])
        bent = int(self.receipt["signal_ids"]["inflow_node_a"])
        self.store.connection.execute(
            f"DELETE FROM {self.entries} WHERE signal_id = ?", (dropped,)
        )
        self.store.connection.execute(
            f"UPDATE {self.entries} SET display_name_sort = 'drifted' "
            "WHERE signal_id = ?",
            (bent,),
        )

        divergence = self.store.catalog_projection_divergence()

        self.assertEqual(
            {
                "clean": clean,
                "divergent": divergence,
            },
            {
                "clean": {
                    "section": "inputs",
                    "missing": [],
                    "unexpected": [],
                    "stale": [],
                    "object_specific": [],
                    "converged": True,
                },
                "divergent": {
                    "section": "inputs",
                    "missing": [dropped],
                    "unexpected": [],
                    "stale": [bent],
                    "object_specific": [],
                    "converged": False,
                },
            },
        )

    def test_a_full_rebuild_swaps_a_verified_shadow_and_converges(self):
        dropped = int(self.receipt["signal_ids"]["energy_price"])
        self.store.connection.execute(
            f"DELETE FROM {self.entries} WHERE signal_id = ?", (dropped,)
        )
        generation_before = self.store.catalog_generation()

        receipt = self.store.rebuild_catalog_projection()

        self.assertEqual(
            {
                "shadow_rows": receipt["shadow_rows"],
                "replaced_rows": receipt["replaced_rows"],
                "rows_before": receipt["rows_before"],
                "converged_before": receipt["divergence_before"]["converged"],
                "hash_changed": receipt["content_hash"]
                != receipt["previous_content_hash"],
                "shadow_dropped": receipt["shadow_dropped"],
                "generation": self.store.catalog_generation(),
                "generation_rose_once": self.store.catalog_generation()
                == generation_before + 1,
                "divergence_after": self.store.catalog_projection_divergence()[
                    "converged"
                ],
            },
            {
                "shadow_rows": 2,
                "replaced_rows": 2,
                "rows_before": 1,
                "converged_before": False,
                "hash_changed": True,
                "shadow_dropped": True,
                "generation": generation_before + 1,
                "generation_rose_once": True,
                "divergence_after": True,
            },
        )

    def test_a_rebuild_of_a_converged_projection_does_not_raise_the_generation(self):
        generation_before = self.store.catalog_generation()

        receipt = self.store.rebuild_catalog_projection()

        self.assertEqual(
            {
                "outcome": receipt["outcome"],
                "hash_is_stable": receipt["content_hash"]
                == receipt["previous_content_hash"],
                "generation": self.store.catalog_generation(),
                "shadow_dropped": receipt["shadow_dropped"],
            },
            {
                "outcome": "unchanged",
                "hash_is_stable": True,
                "generation": generation_before,
                "shadow_dropped": True,
            },
        )



def postgres_attempt(connection, sql, parameters=()):
    """Isolate an expected PostgreSQL refusal in a savepoint."""

    try:
        with connection.transaction():
            connection.execute(sql, parameters)
    except Exception:  # noqa: BLE001 - the engine owns the exception type
        return "refused"
    return "accepted"


@unittest.skipUnless(
    POSTGRES_TEST_DATABASE_URL,
    "set POSTGRES_TEST_DATABASE_URL to run the PostgreSQL contract tests",
)
class PostgresCatalogProjectionTests(unittest.TestCase):
    """The SQLite contract of TS7-005 repeated on development PostgreSQL."""

    def setUp(self):
        self.store = AnalystStore(POSTGRES_TEST_DATABASE_URL)
        self.rollback = self.store.connection._connection.transaction(  # noqa: SLF001
            force_rollback=True
        )
        self.rollback.__enter__()
        self.suffix = uuid.uuid4().hex[:10]
        self.project = self.store.create_project(name=f"TS7-005 {self.suffix}")
        self.entries = self.store.catalog_projection_table_names()[
            "time_series_catalog_entries"
        ]

    def tearDown(self):
        try:
            self.rollback.__exit__(None, None, None)
        finally:
            self.store.close()

    def _publish(
        self, *, first_value=70.0, idempotency_key=None, request_fingerprint=None
    ):
        return self.store.publish_canonical_set_revision(
            project_id=self.project["id"],
            name=f"Precios {self.suffix}",
            data_class_key="real",
            timezone="UTC",
            signals=HOURLY_SIGNALS,
            periods=hourly_periods(3),
            values={
                "energy_price": [first_value + index for index in range(3)],
                "inflow_node_a": [10.0 + index for index in range(3)],
            },
            actor=f"analyst-{self.suffix}",
            idempotency_key=idempotency_key,
            request_fingerprint=request_fingerprint,
        )

    def _projected(self, set_id):
        return [
            dict(row)
            for row in self.store.connection.execute(
                f"SELECT * FROM {self.entries} WHERE time_series_set_id = ? "
                "ORDER BY series_key",
                (set_id,),
            ).fetchall()
        ]

    def test_postgres_projects_the_same_rows_and_raises_one_generation(self):
        before = self.store.catalog_generation()
        first = self._publish()
        after_publish = self.store.catalog_generation()
        second = self._publish()
        after_republish = self.store.catalog_generation()
        rows = self._projected(first["set_id"])

        self.assertEqual(
            {
                "generation_step": after_publish - before,
                "republish_step": after_republish - after_publish,
                "outcomes": [first["outcome"], second["outcome"]],
                "series_keys": [row["series_key"] for row in rows],
                "kinds": sorted({row["series_kind"] for row in rows}),
                "revisions": sorted({row["current_revision_id"] for row in rows}),
                "coverage": sorted(
                    {(row["coverage_start"], row["coverage_end"]) for row in rows}
                ),
                "resolution": sorted(
                    {
                        (row["nominal_resolution_seconds"], row["regularity"])
                        for row in rows
                    }
                ),
                "projection_revisions": sorted(
                    {row["projection_revision"] for row in rows}
                ),
            },
            {
                "generation_step": 1,
                "republish_step": 0,
                "outcomes": ["published", "unchanged"],
                "series_keys": ["energy_price", "inflow_node_a"],
                "kinds": ["catalog"],
                "revisions": [first["revision_id"]],
                "coverage": [("2026-01-01T00:00:00", "2026-01-01T03:00:00")],
                "resolution": [(3600.0, "regular")],
                "projection_revisions": [1],
            },
        )

    def test_postgres_refuses_an_object_specific_row_in_the_projection(self):
        signal_id = 900_000 + int(self.suffix[:4], 16)
        object_row = self.store.ensure_global_signal_slot(
            project_id=self.project["id"]
        )
        set_id = build_object_specific_signal(
            self.store, self.project["id"], object_row["id"], signal_id=signal_id
        )
        insert = f"""
            INSERT INTO {self.entries} (
                signal_id, time_series_set_id, series_kind, owner_project_id,
                owner_project_name_sort, visibility_scope, set_status,
                signal_status, series_key, display_name, display_name_sort,
                search_text_normalized, semantic_type_id, semantic_type_key,
                data_class_id, data_class_key, unit_id, unit_key, source_kind,
                current_revision_id, revision_number, coverage_start,
                coverage_end, period_count, value_count,
                nominal_resolution_seconds, min_resolution_seconds,
                max_resolution_seconds, regularity, updated_at
            ) VALUES (?, ?, ?, ?, 'cuenca', 'project', 'draft', 'active',
                      'local_price', 'Precio local', 'precio local',
                      'precio local', 1, 'energy_price', 1, 'real', 1,
                      'usd_per_mwh', 'api', 1, 1, '2026-01-01T00:00:00',
                      '2026-01-01T01:00:00', 1, 1, 3600.0, 3600.0, 3600.0,
                      'regular', '2026-01-01T00:00:00')
        """

        self.assertEqual(
            {
                "pretend_catalog": postgres_attempt(
                    self.store.connection, insert, (signal_id, set_id, "catalog")
                ),
                "declare_object_specific": postgres_attempt(
                    self.store.connection,
                    insert,
                    (signal_id, set_id, "object_specific"),
                ),
            },
            {"pretend_catalog": "refused", "declare_object_specific": "refused"},
        )

    def test_postgres_page_plan_never_reads_periods_or_values(self):
        self._publish()
        plan = self.store.explain_catalog_page(limit=50, analyze=True)
        plan_text = " ".join(plan["plan"]).lower()

        self.assertEqual(
            {
                "engine": plan["engine"],
                "analyzed": "actual time" in plan_text,
                "buffers": "buffers" in plan_text,
                "reads_periods": "time_series_periods" in plan_text,
                "reads_values": "time_series_values" in plan_text,
                "tables": plan["tables"],
            },
            {
                "engine": "postgresql",
                "analyzed": True,
                "buffers": True,
                "reads_periods": False,
                "reads_values": False,
                "tables": ["time_series_catalog_entries"],
            },
        )

    def test_postgres_keeps_idempotency_durable_and_exclusive(self):
        first = self._publish(
            idempotency_key=f"publish-{self.suffix}", request_fingerprint="body-a"
        )
        replay = self._publish(
            idempotency_key=f"publish-{self.suffix}", request_fingerprint="body-a"
        )

        with self.assertRaises(CanonicalRevisionError) as refusal:
            self._publish(
                idempotency_key=f"publish-{self.suffix}",
                first_value=90.0,
                request_fingerprint="body-b",
            )

        idempotency = self.store.catalog_projection_table_names()[
            "time_series_operation_idempotency"
        ]
        stored = [
            (row["operation_kind"], row["state"], row["http_status"])
            for row in self.store.connection.execute(
                f"SELECT * FROM {idempotency} WHERE actor_id = ?",
                (f"analyst-{self.suffix}",),
            ).fetchall()
        ]
        revisions = self.store.canonical_table_names()["time_series_set_revisions"]

        self.assertEqual(
            {
                "converges": replay == first,
                "conflict_code": refusal.exception.code,
                "stored": stored,
                "revision_count": int(
                    self.store.connection.execute(
                        f"SELECT COUNT(*) AS total FROM {revisions} "
                        "WHERE time_series_set_id = ?",
                        (first["set_id"],),
                    ).fetchone()["total"]
                ),
            },
            {
                "converges": True,
                "conflict_code": "TS_IDEMPOTENCY_KEY_CONFLICT",
                "stored": [("publish_set_revision", "completed", 201)],
                "revision_count": 1,
            },
        )

    def test_postgres_lands_every_mandatory_index_and_the_search_vector(self):
        indexes = {
            row["indexname"]
            for row in self.store.connection.execute(
                """
                SELECT indexname FROM pg_indexes
                WHERE schemaname = 'ts_next'
                  AND tablename = 'time_series_catalog_entries'
                """
            ).fetchall()
        }
        columns = {
            row["column_name"]
            for row in self.store.connection.execute(
                """
                SELECT column_name FROM information_schema.columns
                WHERE table_schema = 'ts_next'
                  AND table_name = 'time_series_catalog_entries'
                """
            ).fetchall()
        }
        expected = {
            f"time_series_catalog_entries_next_{suffix}"
            for suffix in (
                "updated_at_idx",
                "display_name_idx",
                "owner_project_idx",
                "semantic_type_idx",
                "coverage_start_idx",
                "coverage_end_idx",
                "resolution_idx",
                "association_count_idx",
                "binding_count_idx",
                "visibility_idx",
                "set_idx",
                "search_gin",
            )
        }

        self.assertEqual(
            {
                "missing_indexes": sorted(expected - indexes),
                "has_search_vector": "search_vector" in columns,
            },
            {"missing_indexes": [], "has_search_vector": True},
        )

    def test_postgres_pages_the_object_context_union_on_both_arms(self):
        receipt = self._publish()
        object_row = self.store.ensure_global_signal_slot(
            project_id=self.project["id"]
        )
        associated = int(receipt["signal_ids"]["energy_price"])
        self.store.connection.execute(
            f"""
            INSERT INTO {self.store.link_layer_table_names()
                ['time_series_catalog_associations']} (
                signal_id, time_series_set_id, linkable_object_id,
                binding_role_id, compatibility_rule_id, created_at, created_by
            ) VALUES (?, ?, ?, 1, 1, '2026-01-01T00:00:00', 'test')
            """,
            (associated, receipt["set_id"], object_row["id"]),
        )
        local_signal_id = 800_000 + int(self.suffix[:4], 16)
        build_object_specific_signal(
            self.store,
            self.project["id"],
            object_row["id"],
            signal_id=local_signal_id,
        )

        page = self.store.read_object_context_page(
            linkable_object_id=object_row["id"], limit=50
        )
        walked = []
        cursor = None
        while True:
            step = self.store.read_object_context_page(
                linkable_object_id=object_row["id"], limit=1, cursor=cursor
            )
            walked.extend(item["signal_id"] for item in step["items"])
            cursor = step["page"]["next_cursor"]
            if not step["page"]["has_more"]:
                break
        plan = self.store.explain_object_context_page(
            linkable_object_id=object_row["id"], limit=50, analyze=True
        )
        plan_text = " ".join(plan["plan"]).lower()

        self.assertEqual(
            {
                "rows": sorted(
                    (item["source"], item["signal_id"]) for item in page["items"]
                ),
                "keyset_walk": walked == [item["signal_id"] for item in page["items"]],
                "reads_periods": "time_series_periods" in plan_text,
                "reads_values": "time_series_values" in plan_text,
            },
            {
                "rows": [
                    ("catalog", associated),
                    ("object_specific", local_signal_id),
                ],
                "keyset_walk": True,
                "reads_periods": False,
                "reads_values": False,
            },
        )


class ObjectContextPageTests(unittest.TestCase):
    def setUp(self):
        self.store = AnalystStore("sqlite:///:memory:")
        self.project = self.store.create_project(name="Cuenca Norte")
        self.object = self.store.ensure_global_signal_slot(
            project_id=self.project["id"]
        )
        self.receipt = self.store.publish_canonical_set_revision(
            project_id=self.project["id"],
            name="Precios 2026",
            data_class_key="real",
            timezone="UTC",
            signals=HOURLY_SIGNALS,
            periods=hourly_periods(3),
            values={
                "energy_price": [70.0, 71.0, 72.0],
                "inflow_node_a": [10.0, 11.0, 12.0],
            },
            actor="internal_analyst",
        )
        self.associated = int(self.receipt["signal_ids"]["energy_price"])
        self.store.connection.execute(
            f"""
            INSERT INTO {self.store.link_layer_table_names()
                ['time_series_catalog_associations']} (
                signal_id, time_series_set_id, linkable_object_id,
                binding_role_id, compatibility_rule_id, created_at, created_by
            ) VALUES (?, ?, ?, 1, 1, '2026-01-01T00:00:00', 'test')
            """,
            (self.associated, self.receipt["set_id"], self.object["id"]),
        )
        self.local_signal_id = 100_002
        build_object_specific_signal(
            self.store,
            self.project["id"],
            self.object["id"],
            signal_id=self.local_signal_id,
        )

    def tearDown(self):
        self.store.close()

    def test_the_object_list_unions_its_two_arms_without_overlapping(self):
        page = self.store.read_object_context_page(
            linkable_object_id=self.object["id"], limit=50
        )
        elsewhere = self.store.read_object_context_page(
            linkable_object_id=self.object["id"] + 999, limit=50
        )

        self.assertEqual(
            {
                "rows": sorted(
                    (item["source"], item["signal_id"], item["series_key"])
                    for item in page["items"]
                ),
                "has_more": page["page"]["has_more"],
                "other_object_rows": elsewhere["items"],
                "meta": page["meta"],
            },
            {
                "rows": [
                    ("catalog", self.associated, "energy_price"),
                    ("object_specific", self.local_signal_id, "local_price"),
                ],
                "has_more": False,
                "other_object_rows": [],
                "meta": {
                    "linkable_object_id": self.object["id"],
                    "catalog_generation": self.store.catalog_generation(),
                },
            },
        )

    def test_the_object_keyset_visits_both_arms_exactly_once(self):
        walked = []
        pages = 0
        cursor = None
        while True:
            page = self.store.read_object_context_page(
                linkable_object_id=self.object["id"], limit=1, cursor=cursor
            )
            pages += 1
            walked.extend(
                (item["source"], item["signal_id"]) for item in page["items"]
            )
            cursor = page["page"]["next_cursor"]
            if not page["page"]["has_more"]:
                break

        whole = self.store.read_object_context_page(
            linkable_object_id=self.object["id"], limit=50
        )
        self.assertEqual(
            {
                "pages": pages,
                "walked": walked,
                "matches_whole_page": walked
                == [(item["source"], item["signal_id"]) for item in whole["items"]],
                "final_cursor": cursor,
            },
            {
                "pages": 2,
                "walked": walked,
                "matches_whole_page": True,
                "final_cursor": None,
            },
        )


class PerformanceFixturePlanTests(unittest.TestCase):
    """The fixture keeps the documented proportions at every scale."""

    def test_the_reference_scale_is_the_one_chapter_9_2_documents(self):
        reference = fixture_plan(1.0)

        self.assertEqual(
            {
                "entries": reference["entries"],
                "associations": reference["associations"],
                "bindings": reference["bindings"],
                "cells": reference["cells"],
                "entries_match_sets": reference["sets"] * reference["signals_per_set"]
                == reference["entries"],
                "cells_match_coverage": reference["entries"] * reference["periods"]
                == reference["cells"],
            },
            {
                "entries": 100_000,
                "associations": 1_000_000,
                "bindings": 1_000_000,
                "cells": 100_000_000,
                "entries_match_sets": True,
                "cells_match_coverage": True,
            },
        )

    def test_a_reduced_scale_keeps_the_proportions_and_stays_buildable(self):
        reduced = fixture_plan(0.001)

        self.assertEqual(
            {
                "entries": reduced["entries"],
                "cells": reduced["cells"],
                "associations_per_entry": reduced["associations"] // reduced["entries"],
                "bindings_per_entry": reduced["bindings"] // reduced["entries"],
                "everything_positive": all(
                    value > 0
                    for key, value in reduced.items()
                    if isinstance(value, int)
                ),
            },
            {
                "entries": 100,
                "cells": 100_000,
                "associations_per_entry": 10,
                "bindings_per_entry": 10,
                "everything_positive": True,
            },
        )
