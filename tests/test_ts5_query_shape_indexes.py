"""BESS-TS5-010: query-shape guard tests for TS-2 through TS-4 hot paths."""

import tempfile
import unittest
from pathlib import Path

from app.persistence import AnalystStore


class QueryShapeIndexTests(unittest.TestCase):
    HOT_PATHS = [
        {
            "label": "catalog browse",
            "sql": """
                SELECT
                    time_series_sets.id,
                    latest_revision.revision_number,
                    (
                        SELECT COUNT(*) FROM time_series_signals
                        WHERE time_series_signals.time_series_set_id = time_series_sets.id
                    ) AS signal_count,
                    (
                        SELECT COUNT(*) FROM time_series_periods
                        WHERE time_series_periods.time_series_set_id = time_series_sets.id
                    ) AS period_count
                FROM time_series_sets
                JOIN (
                    SELECT r1.time_series_set_id, r1.revision_number, r1.content_hash
                    FROM time_series_set_revisions AS r1
                    WHERE r1.revision_number = (
                        SELECT MAX(r2.revision_number)
                        FROM time_series_set_revisions AS r2
                        WHERE r2.time_series_set_id = r1.time_series_set_id
                    )
                ) AS latest_revision
                  ON latest_revision.time_series_set_id = time_series_sets.id
                WHERE time_series_sets.project_id = 1
                ORDER BY time_series_sets.name, time_series_sets.version_number
            """,
            "forbidden_scan_prefixes": ["SCAN time_series_sets"],
            "expected_index_fragments": [
                "sqlite_autoindex_time_series_sets_1",
                "sqlite_autoindex_time_series_set_revisions_1",
            ],
        },
        {
            "label": "variant bindings",
            "sql": """
                SELECT
                    id, case_input_variant_id, signal_key, entity_type, entity_id,
                    time_series_set_id, required, created_at, updated_at, created_by, updated_by
                FROM case_time_series_bindings
                WHERE case_input_variant_id = 1
                ORDER BY signal_key, entity_type, entity_id
            """,
            "forbidden_scan_prefixes": ["SCAN case_time_series_bindings"],
            "expected_index_fragments": ["sqlite_autoindex_case_time_series_bindings_1"],
        },
        {
            "label": "variant validation dependencies",
            "sql": """
                SELECT dependency_type, dependency_id, recorded_hash
                FROM validation_dependencies
                WHERE owner_type = 'case_input_variant' AND owner_id = 1
                ORDER BY dependency_type, dependency_id
            """,
            "forbidden_scan_prefixes": ["SCAN validation_dependencies"],
            "expected_index_fragments": ["sqlite_autoindex_validation_dependencies_1"],
        },
        {
            "label": "run dispatch read",
            "sql": """
                SELECT row_json
                FROM run_dispatch_result_rows
                WHERE run_id = 1
                ORDER BY period_index
            """,
            "forbidden_scan_prefixes": ["SCAN run_dispatch_result_rows"],
            "expected_index_fragments": ["sqlite_autoindex_run_dispatch_result_rows_1"],
        },
        {
            "label": "run asset dispatch read",
            "sql": """
                SELECT row_json
                FROM run_asset_dispatch_result_rows
                WHERE run_id = 1
                ORDER BY period_index
            """,
            "forbidden_scan_prefixes": ["SCAN run_asset_dispatch_result_rows"],
            "expected_index_fragments": ["sqlite_autoindex_run_asset_dispatch_result_rows_1"],
        },
        {
            "label": "run comparison lineage lookup",
            "sql": """
                SELECT scenarios.project_id
                FROM runs
                JOIN scenario_versions ON scenario_versions.id = runs.scenario_version_id
                JOIN scenarios ON scenarios.id = scenario_versions.scenario_id
                WHERE runs.id = 1
            """,
            "forbidden_scan_prefixes": ["SCAN runs", "SCAN scenario_versions", "SCAN scenarios"],
            "expected_index_fragments": [
                "SEARCH runs USING INTEGER PRIMARY KEY",
                "SEARCH scenario_versions USING INTEGER PRIMARY KEY",
                "SEARCH scenarios USING INTEGER PRIMARY KEY",
            ],
        },
    ]

    def setUp(self):
        self.store = AnalystStore("sqlite:///:memory:")
        self.addCleanup(self.store.close)

    def _plan_details(self, sql: str) -> list[str]:
        return [
            str(row["detail"])
            for row in self.store.connection.execute(f"EXPLAIN QUERY PLAN {sql}").fetchall()
        ]

    def test_time_series_set_value_reads_use_indexed_lookup_not_full_scan(self):
        details = self._plan_details(
            """
            SELECT
                time_series_periods.period_index,
                time_series_signals.signal_key,
                time_series_values.value_numeric
            FROM time_series_values
            JOIN time_series_periods
              ON time_series_periods.id = time_series_values.time_series_period_id
            JOIN time_series_signals
              ON time_series_signals.id = time_series_values.time_series_signal_id
            WHERE time_series_values.time_series_set_id = 1
            ORDER BY time_series_periods.period_index, time_series_signals.signal_key
            """
        )

        self.assertFalse(
            any(detail.startswith("SCAN time_series_values") for detail in details),
            details,
        )
        self.assertTrue(
            any(
                "time_series_values" in detail
                and "USING INDEX idx_time_series_values_set_period_signal" in detail
                for detail in details
            ),
            details,
        )

    def test_project_succeeded_run_scans_use_indexed_status_lookup_not_full_scan(self):
        details = self._plan_details(
            """
            SELECT runs.id
            FROM runs
            JOIN scenario_versions ON scenario_versions.id = runs.scenario_version_id
            JOIN scenarios ON scenarios.id = scenario_versions.scenario_id
            WHERE runs.status = 'succeeded' AND scenarios.project_id = 1
            ORDER BY runs.id
            """
        )

        self.assertFalse(any(detail.startswith("SCAN runs") for detail in details), details)
        self.assertTrue(
            any(
                "runs" in detail
                and "idx_runs_status_scenario_version" in detail
                for detail in details
            ),
            details,
        )

    def test_existing_constraints_and_indexes_cover_other_ts2_to_ts4_hot_paths(self):
        for hot_path in self.HOT_PATHS:
            with self.subTest(hot_path=hot_path["label"]):
                details = self._plan_details(hot_path["sql"])
                for forbidden_prefix in hot_path["forbidden_scan_prefixes"]:
                    self.assertFalse(
                        any(detail.startswith(forbidden_prefix) for detail in details),
                        details,
                    )
                for expected_fragment in hot_path["expected_index_fragments"]:
                    self.assertTrue(
                        any(expected_fragment in detail for detail in details),
                        details,
                    )

    def test_query_shape_indexes_are_created_idempotently_when_reopening_same_database(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "query-shapes.sqlite3"
            database_url = f"sqlite:///{database_path.as_posix()}"

            first_store = AnalystStore(database_url)
            first_store.close()
            second_store = AnalystStore(database_url)
            try:
                rows = second_store.connection.execute(
                    """
                    SELECT name
                    FROM sqlite_master
                    WHERE type = 'index'
                      AND name IN (
                          'idx_time_series_values_set_period_signal',
                          'idx_runs_status_scenario_version',
                          'idx_scenario_versions_scenario',
                          'idx_scenarios_project'
                      )
                    ORDER BY name
                    """
                ).fetchall()
            finally:
                second_store.close()

        self.assertEqual(
            [str(row["name"]) for row in rows],
            [
                "idx_runs_status_scenario_version",
                "idx_scenario_versions_scenario",
                "idx_scenarios_project",
                "idx_time_series_values_set_period_signal",
            ],
        )


if __name__ == "__main__":
    unittest.main()
