"""TS7-001 persistent classification catalog acceptance tests."""

import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from fastapi.testclient import TestClient

from app.auth import hash_password
from app.main import create_app
from app.persistence import AnalystStore
from app.time_series_catalog import (
    TIME_SERIES_DATA_KINDS,
    TIME_SERIES_SIGNAL_CATALOG,
    TimeSeriesSignalDefinition,
)
from app.time_series_classification import ClassificationContractDriftError
from tests.auth_test_helpers import login_json_with_csrf, post_json_with_csrf


POSTGRES_TEST_DATABASE_URL = os.environ.get("POSTGRES_TEST_DATABASE_URL")


class PersistentClassificationCatalogTests(unittest.TestCase):
    def setUp(self):
        self.store = AnalystStore("sqlite:///:memory:")

    def tearDown(self):
        self.store.close()

    def test_a_new_store_exposes_its_seeded_measurement_dimensions(self):
        catalog = self.store.get_time_series_classification_catalog()

        self.assertEqual(
            [row["dimension_key"] for row in catalog["measurement_dimensions"]],
            ["currency_per_energy", "flow", "power"],
        )

    def test_a_new_store_exposes_the_complete_initial_classification_contract(self):
        catalog = self.store.get_time_series_classification_catalog()

        self.assertEqual(
            {
                "units": [row["unit_key"] for row in catalog["measurement_units"]],
                "data_classes": [
                    row["data_class_key"]
                    for row in catalog["time_series_data_classes"]
                ],
                "semantic_types": [
                    row["semantic_key"]
                    for row in catalog["time_series_semantic_types"]
                ],
                "roles": [
                    row["role_key"]
                    for row in catalog["time_series_binding_roles"]
                ],
                "object_types": [
                    row["object_type_key"]
                    for row in catalog["linkable_object_types"]
                ],
                "compatibility_rules": len(
                    catalog["time_series_role_compatibilities"]
                ),
                "role_columns": sorted(catalog["time_series_binding_roles"][0]),
            },
            {
                "units": ["m3_per_s", "mw", "usd_per_mwh"],
                "data_classes": [
                    "derived",
                    "forecast",
                    "mixed",
                    "programmed",
                    "real",
                    "simulated",
                    "synthetic",
                ],
                "semantic_types": [
                    "energy_price",
                    "grid_export_price",
                    "grid_import_price",
                    "hydro_inflow",
                    "load_demand",
                    "minimum_flow",
                    "natural_inflow",
                    "renewable_available_power",
                ],
                "roles": [
                    "grid_export_price",
                    "grid_import_price",
                    "hydro_inflow",
                    "load_demand",
                    "minimum_flow",
                    "natural_inflow",
                    "renewable_available_power",
                ],
                "object_types": [
                    "component:battery",
                    "component:grid",
                    "component:hydro",
                    "component:load",
                    "component:renewable",
                    "global:system",
                    "hydraulic_node",
                    "hydraulic_plant",
                    "hydraulic_reach",
                    "hydraulic_system",
                    "hydraulic_unit",
                ],
                "compatibility_rules": 9,
                "role_columns": [
                    "association_allowed",
                    "canonical_unit_id",
                    "dimension_id",
                    "display_name",
                    "execution_allowed",
                    "execution_contract_key",
                    "id",
                    "is_system",
                    "role_key",
                    "status",
                ],
            },
        )

    def test_reapplying_the_seed_reports_convergence_without_changing_the_catalog(self):
        before = self.store.get_time_series_classification_catalog()

        result = self.store.seed_time_series_classification_catalog()

        self.assertEqual(
            {
                "result": result,
                "catalog_unchanged": self.store.get_time_series_classification_catalog()
                == before,
            },
            {
                "result": {
                    "contract_version": 1,
                    "status": "converged",
                    "inserted_rows": 0,
                },
                "catalog_unchanged": True,
            },
        )

    def test_registry_drift_blocks_the_seed_with_a_named_failure(self):
        divergent = TimeSeriesSignalDefinition(
            signal_key="load_demand_mw",
            unit="kW",
            entity_type="component:load",
            nonnegative=True,
        )

        with mock.patch.dict(
            TIME_SERIES_SIGNAL_CATALOG,
            {"load_demand_mw": divergent},
        ):
            with self.assertRaises(ClassificationContractDriftError) as raised:
                self.store.seed_time_series_classification_catalog()

        self.assertEqual(
            {"code": raised.exception.code, "context": raised.exception.context},
            {
                "code": "TS_CLASSIFICATION_CONTRACT_DIVERGED",
                "context": {
                    "catalog": "TIME_SERIES_SIGNAL_CATALOG",
                    "key": "load_demand_mw",
                    "field": "unit",
                    "expected": "MW",
                    "actual": "kW",
                },
            },
        )

    def test_unknown_python_data_class_does_not_become_canonical(self):
        with mock.patch(
            "app.persistence.TIME_SERIES_DATA_KINDS",
            {*TIME_SERIES_DATA_KINDS, "mystery"},
        ):
            with self.assertRaises(ClassificationContractDriftError) as raised:
                self.store.seed_time_series_classification_catalog()

        self.assertEqual(
            {"code": raised.exception.code, "context": raised.exception.context},
            {
                "code": "TS_CLASSIFICATION_CONTRACT_DIVERGED",
                "context": {
                    "catalog": "TIME_SERIES_DATA_KINDS",
                    "key": "*",
                    "field": "keys",
                    "expected": [
                        "derived",
                        "forecast",
                        "mixed",
                        "programmed",
                        "real",
                        "simulated",
                        "synthetic",
                    ],
                    "actual": [
                        "derived",
                        "forecast",
                        "mixed",
                        "mystery",
                        "programmed",
                        "real",
                        "simulated",
                        "synthetic",
                    ],
                },
            },
        )

    def test_persisted_contract_drift_blocks_bootstrap_before_any_partial_seed(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            database_path = Path(temporary_directory) / "classification.sqlite3"
            connection = sqlite3.connect(database_path)
            connection.execute(
                """
                CREATE TABLE measurement_dimensions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    dimension_key TEXT NOT NULL UNIQUE,
                    display_name TEXT NOT NULL,
                    value_kind TEXT NOT NULL,
                    status TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                INSERT INTO measurement_dimensions (
                    id, dimension_key, display_name, value_kind, status
                ) VALUES (1, 'currency_per_energy', 'Currency per energy', 'text', 'active')
                """
            )
            connection.commit()
            connection.close()

            with self.assertRaises(ClassificationContractDriftError) as raised:
                AnalystStore(f"sqlite:///{database_path.as_posix()}")

            connection = sqlite3.connect(database_path)
            unit_count = connection.execute(
                "SELECT COUNT(*) FROM measurement_units"
            ).fetchone()[0]
            connection.close()

        self.assertEqual(
            {
                "code": raised.exception.code,
                "context": raised.exception.context,
                "unit_count": unit_count,
            },
            {
                "code": "TS_CLASSIFICATION_CONTRACT_DIVERGED",
                "context": {
                    "catalog": "measurement_dimensions",
                    "key": "currency_per_energy",
                    "field": "value_kind",
                    "expected": "numeric",
                    "actual": "text",
                },
                "unit_count": 0,
            },
        )

    def test_system_semantic_contract_is_immutable_but_descriptive_metadata_is_editable(self):
        with self.assertRaises(sqlite3.DatabaseError) as raised:
            self.store.connection.execute(
                """
                UPDATE time_series_semantic_types
                SET canonical_unit_id = 2, dimension_id = 2
                WHERE semantic_key = 'load_demand'
                """
            )

        self.store.connection.execute(
            """
            UPDATE time_series_semantic_types
            SET display_name = 'Demand profile'
            WHERE semantic_key = 'load_demand'
            """
        )
        row = self.store.connection.execute(
            """
            SELECT display_name, canonical_unit_id, dimension_id
            FROM time_series_semantic_types
            WHERE semantic_key = 'load_demand'
            """
        ).fetchone()

        self.assertEqual(
            {
                "failure": str(raised.exception),
                "display_name": row["display_name"],
                "canonical_unit_id": row["canonical_unit_id"],
                "dimension_id": row["dimension_id"],
            },
            {
                "failure": "TS_CLASSIFICATION_IMMUTABLE",
                "display_name": "Demand profile",
                "canonical_unit_id": 3,
                "dimension_id": 3,
            },
        )

    def test_every_classification_table_rejects_contract_rewrites_and_deletes(self):
        mutations = (
            "UPDATE measurement_dimensions SET value_kind = 'text' WHERE id = 1",
            "UPDATE measurement_units SET symbol = 'kW' WHERE id = 3",
            "UPDATE time_series_data_classes SET data_class_key = 'observed' WHERE id = 1",
            "UPDATE time_series_binding_roles SET execution_allowed = 0 WHERE id = 3",
            "UPDATE linkable_object_types SET object_kind = 'text_pair' WHERE id = 3",
            "UPDATE time_series_role_compatibilities SET execution_allowed = 0 WHERE id = 5",
            "DELETE FROM time_series_semantic_types WHERE id = 4",
        )

        failures = []
        for statement in mutations:
            with self.subTest(statement=statement):
                with self.assertRaises(sqlite3.DatabaseError) as raised:
                    self.store.connection.execute(statement)
                failures.append(str(raised.exception))

        self.assertEqual(
            failures,
            ["TS_CLASSIFICATION_IMMUTABLE"] * len(mutations),
        )

    def test_the_legacy_signal_adapter_reads_known_classification_from_the_database(self):
        client = TestClient(create_app(store=self.store, auth_enabled=False))
        divergent = TimeSeriesSignalDefinition(
            signal_key="load_demand_mw",
            unit="kW",
            entity_type="component:load",
            nonnegative=False,
        )

        with mock.patch.dict(
            TIME_SERIES_SIGNAL_CATALOG,
            {"load_demand_mw": divergent},
        ):
            response = client.get("/api/time-series/signal-catalog")

        by_key = {
            row["signal_key"]: row for row in response.json()["signals"]
        }
        self.assertEqual(
            by_key["load_demand_mw"],
            {
                "signal_key": "load_demand_mw",
                "unit": "MW",
                "entity_type": "component:load",
                "nonnegative": True,
            },
        )


class CompatibilityEvaluatorTests(unittest.TestCase):
    def setUp(self):
        self.store = AnalystStore("sqlite:///:memory:")

    def tearDown(self):
        self.store.close()

    def test_an_exact_positive_matrix_rule_is_allowed(self):
        decision = self.store.evaluate_time_series_compatibility(
            semantic_type_key="load_demand",
            binding_role_key="load_demand",
            object_type_key="component:load",
            unit_key="mw",
            usage="execution",
        )

        self.assertEqual(
            decision,
            {
                "allowed": True,
                "compatibility_rule_id": 5,
                "rule_version": 1,
                "contract_version": 1,
                "errors": [],
                "primary_error": None,
            },
        )


    def test_unit_compatibility_is_an_exact_key_match_without_implicit_conversion(self):
        decision = self.store.evaluate_time_series_compatibility(
            semantic_type_key="load_demand",
            binding_role_key="load_demand",
            object_type_key="component:load",
            unit_key="MW",
            usage="execution",
        )

        self.assertEqual(
            {
                "allowed": decision["allowed"],
                "rule_id": decision["compatibility_rule_id"],
                "codes": [error["code"] for error in decision["errors"]],
                "primary_code": decision["primary_error"]["code"],
                "context": decision["primary_error"]["context"],
            },
            {
                "allowed": False,
                "rule_id": 5,
                "codes": ["TS_COMPAT_UNIT_MISMATCH"],
                "primary_code": "TS_COMPAT_UNIT_MISMATCH",
                "context": {
                    "semantic_type_key": "load_demand",
                    "role_key": "load_demand",
                    "object_type_key": "component:load",
                    "usage": "execution",
                    "expected_unit_key": "mw",
                    "actual_unit_key": "MW",
                },
            },
        )


    def test_unavailable_catalog_identities_are_reported_in_documented_order(self):
        decision = self.store.evaluate_time_series_compatibility(
            semantic_type_key="mystery_type",
            binding_role_key="mystery_role",
            object_type_key="mystery_object",
            unit_key="mw",
            usage="association",
        )

        self.assertEqual(
            {
                "allowed": decision["allowed"],
                "codes": [error["code"] for error in decision["errors"]],
                "primary_code": decision["primary_error"]["code"],
            },
            {
                "allowed": False,
                "codes": [
                    "TS_COMPAT_SEMANTIC_TYPE_INACTIVE",
                    "TS_COMPAT_ROLE_INACTIVE",
                    "TS_COMPAT_OBJECT_UNAVAILABLE",
                ],
                "primary_code": "TS_COMPAT_SEMANTIC_TYPE_INACTIVE",
            },
        )

    def test_positive_rules_fail_closed_without_type_or_object_wildcards(self):
        cases = (
            (
                {
                    "semantic_type_key": "load_demand",
                    "binding_role_key": "grid_import_price",
                    "object_type_key": "global:system",
                    "unit_key": "mw",
                    "usage": "association",
                },
                "TS_COMPAT_SEMANTIC_TYPE_NOT_ALLOWED",
            ),
            (
                {
                    "semantic_type_key": "load_demand",
                    "binding_role_key": "load_demand",
                    "object_type_key": "component:battery",
                    "unit_key": "mw",
                    "usage": "association",
                },
                "TS_COMPAT_OBJECT_TYPE_NOT_ALLOWED",
            ),
        )

        actual = []
        for request, expected_code in cases:
            with self.subTest(expected_code=expected_code):
                decision = self.store.evaluate_time_series_compatibility(**request)
                actual.append(
                    (
                        decision["allowed"],
                        decision["primary_error"]["code"],
                    )
                )

        self.assertEqual(
            actual,
            [
                (False, "TS_COMPAT_SEMANTIC_TYPE_NOT_ALLOWED"),
                (False, "TS_COMPAT_OBJECT_TYPE_NOT_ALLOWED"),
            ],
        )

    def test_a_complete_custom_type_is_persisted_without_automatic_compatibility(self):
        created = self.store.create_custom_time_series_semantic_type(
            semantic_key="site_net_power",
            display_name="Site net power",
            description="Signed net power measured at the site boundary.",
            dimension_key="power",
            canonical_unit_key="mw",
            value_kind="numeric",
            default_aggregation="mean",
            validation_rules={"minimum": -1000, "maximum": 1000},
            created_by="admin@example.local",
        )
        decision = self.store.evaluate_time_series_compatibility(
            semantic_type_key="site_net_power",
            binding_role_key="load_demand",
            object_type_key="component:load",
            unit_key="mw",
            usage="association",
        )

        self.assertEqual(
            {
                "semantic_key": created["semantic_key"],
                "dimension_key": created["dimension_key"],
                "canonical_unit_key": created["canonical_unit_key"],
                "validation_rules": created["validation_rules"],
                "is_system": created["is_system"],
                "compatibility_code": decision["primary_error"]["code"],
            },
            {
                "semantic_key": "site_net_power",
                "dimension_key": "power",
                "canonical_unit_key": "mw",
                "validation_rules": {"minimum": -1000, "maximum": 1000},
                "is_system": False,
                "compatibility_code": "TS_COMPAT_SEMANTIC_TYPE_NOT_ALLOWED",
            },
        )

class CustomSemanticTypeApiTests(unittest.TestCase):
    def setUp(self):
        self.store = AnalystStore("sqlite:///:memory:")
        self.client = TestClient(create_app(store=self.store, auth_enabled=True))
        self.store.create_user(
            email="admin@example.local",
            display_name="Ada Admin",
            role="admin",
            password_hash=hash_password("admin pass"),
        )
        self.store.create_user(
            email="analyst@example.local",
            display_name="Ana Analyst",
            role="analyst",
            password_hash=hash_password("analyst pass"),
        )
        self.store.create_user(
            email="external@example.local",
            display_name="Eli External",
            role="external",
            password_hash=hash_password("external pass"),
        )

    def tearDown(self):
        self.store.close()

    def test_an_admin_creates_a_complete_custom_semantic_type(self):
        self.assertEqual(
            login_json_with_csrf(
                self.client, "admin@example.local", "admin pass"
            ).status_code,
            200,
        )

        response = post_json_with_csrf(
            self.client,
            "/api/admin/time-series/semantic-types",
            {
                "semantic_key": "site_net_power",
                "display_name": "Site net power",
                "description": "Signed net power measured at the site boundary.",
                "dimension_key": "power",
                "canonical_unit_key": "mw",
                "value_kind": "numeric",
                "default_aggregation": "mean",
                "validation_rules": {"minimum": -1000, "maximum": 1000},
            },
        )

        self.assertEqual(
            {
                "status": response.status_code,
                "semantic_key": response.json()["semantic_type"]["semantic_key"],
                "canonical_unit_key": response.json()["semantic_type"][
                    "canonical_unit_key"
                ],
                "is_system": response.json()["semantic_type"]["is_system"],
                "created_by": response.json()["semantic_type"]["created_by"],
            },
            {
                "status": 201,
                "semantic_key": "site_net_power",
                "canonical_unit_key": "mw",
                "is_system": False,
                "created_by": "admin@example.local",
            },
        )

    def test_an_incomplete_custom_contract_is_rejected_without_writing(self):
        login_json_with_csrf(self.client, "admin@example.local", "admin pass")
        before = len(
            self.store.get_time_series_classification_catalog()[
                "time_series_semantic_types"
            ]
        )

        response = post_json_with_csrf(
            self.client,
            "/api/admin/time-series/semantic-types",
            {
                "semantic_key": "site_net_power",
                "display_name": "Site net power",
                "description": "Signed net power.",
                "dimension_key": "power",
                "canonical_unit_key": "mw",
                "value_kind": "numeric",
                "default_aggregation": "mean",
            },
        )

        self.assertEqual(
            {
                "status": response.status_code,
                "missing_field": response.json()["detail"][0]["loc"][-1],
                "semantic_type_count": len(
                    self.store.get_time_series_classification_catalog()[
                        "time_series_semantic_types"
                    ]
                ),
            },
            {
                "status": 422,
                "missing_field": "validation_rules",
                "semantic_type_count": before,
            },
        )

    def test_non_admin_roles_cannot_create_custom_semantic_types(self):
        payload = {
            "semantic_key": "site_net_power",
            "display_name": "Site net power",
            "description": "Signed net power.",
            "dimension_key": "power",
            "canonical_unit_key": "mw",
            "value_kind": "numeric",
            "default_aggregation": "mean",
            "validation_rules": {},
        }
        statuses = []
        for email, password in (
            ("analyst@example.local", "analyst pass"),
            ("external@example.local", "external pass"),
        ):
            with self.subTest(email=email):
                login_json_with_csrf(self.client, email, password)
                statuses.append(
                    post_json_with_csrf(
                        self.client,
                        "/api/admin/time-series/semantic-types",
                        payload,
                    ).status_code
                )

        self.assertEqual(statuses, [403, 404])


@unittest.skipUnless(
    POSTGRES_TEST_DATABASE_URL,
    "POSTGRES_TEST_DATABASE_URL is required for PostgreSQL integration tests",
)
class PostgresClassificationCatalogTests(unittest.TestCase):
    def test_postgres_converges_and_evaluates_the_same_seeded_contract(self):
        store = AnalystStore(POSTGRES_TEST_DATABASE_URL)
        try:
            result = store.seed_time_series_classification_catalog()
            decision = store.evaluate_time_series_compatibility(
                semantic_type_key="natural_inflow",
                binding_role_key="natural_inflow",
                object_type_key="hydraulic_node",
                unit_key="m3_per_s",
                usage="execution",
            )
            role_columns = sorted(
                store.get_time_series_classification_catalog()[
                    "time_series_binding_roles"
                ][0]
            )
        finally:
            store.close()

        self.assertEqual(
            {
                "seed_status": result["status"],
                "inserted_rows": result["inserted_rows"],
                "allowed": decision["allowed"],
                "semantic_type_id_column": "semantic_type_id" in role_columns,
            },
            {
                "seed_status": "converged",
                "inserted_rows": 0,
                "allowed": True,
                "semantic_type_id_column": False,
            },
        )

    def test_postgres_rejects_an_immutable_contract_rewrite(self):
        store = AnalystStore(POSTGRES_TEST_DATABASE_URL)
        try:
            with self.assertRaises(Exception) as raised:
                store.connection.execute(
                    """
                    UPDATE time_series_semantic_types
                    SET canonical_unit_id = 2, dimension_id = 2
                    WHERE semantic_key = 'load_demand'
                    """
                )
            row = store.connection.execute(
                """
                SELECT canonical_unit_id, dimension_id
                FROM time_series_semantic_types
                WHERE semantic_key = 'load_demand'
                """
            ).fetchone()
        finally:
            store.close()

        self.assertEqual(
            {
                "named_failure": "TS_CLASSIFICATION_IMMUTABLE"
                in str(raised.exception),
                "canonical_unit_id": row["canonical_unit_id"],
                "dimension_id": row["dimension_id"],
            },
            {
                "named_failure": True,
                "canonical_unit_id": 3,
                "dimension_id": 3,
            },
        )


if __name__ == "__main__":
    unittest.main()
