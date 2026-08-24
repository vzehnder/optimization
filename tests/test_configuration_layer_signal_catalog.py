"""BESS-CONFIG-007: the canonical signal registry is the single source of truth.

The console configuration editor stops carrying its own signal-to-unit table and
reads the registry through the common authenticated application boundary. These
tests pin the boundary, the payload shape and the fact that a new declarative
entry travels without touching any per-signal code.
"""

import json
import unittest
from unittest import mock

from fastapi.testclient import TestClient

from app.auth import hash_password
from app.main import create_app
from app.persistence import AnalystStore
from app.surface_payloads import build_console_list_entry, build_console_payload
from app.time_series_catalog import (
    TIME_SERIES_SIGNAL_CATALOG,
    TimeSeriesSignalDefinition,
)
from tests.auth_test_helpers import login_json_with_csrf


SIGNAL_CATALOG_PATH = "/api/time-series/signal-catalog"


class SignalCatalogEndpointTests(unittest.TestCase):
    def setUp(self):
        self.store = AnalystStore("sqlite:///:memory:")
        self.client = TestClient(create_app(store=self.store, auth_enabled=True))
        self.store.create_user(
            email="analyst@example.local",
            display_name="Ana Analista",
            role="analyst",
            password_hash=hash_password("analyst pass"),
        )
        self.store.create_user(
            email="operator@example.local",
            display_name="Olga Operadora",
            role="external",
            password_hash=hash_password("operator pass"),
        )

    def tearDown(self):
        self.store.close()

    def login(self, email, password):
        self.assertEqual(
            login_json_with_csrf(self.client, email, password).status_code, 200
        )

    def test_an_internal_user_reads_the_canonical_signal_metadata(self):
        self.login("analyst@example.local", "analyst pass")

        response = self.client.get(SIGNAL_CATALOG_PATH)

        self.assertEqual(response.status_code, 200)
        signals = response.json()["signals"]
        by_key = {signal["signal_key"]: signal for signal in signals}
        self.assertEqual(
            by_key["load_demand_mw"],
            {
                "signal_key": "load_demand_mw",
                "unit": "MW",
                "entity_type": "component:load",
                "nonnegative": True,
            },
        )
        self.assertEqual(
            by_key["price_usd_per_mwh"],
            {
                "signal_key": "price_usd_per_mwh",
                "unit": "USD/MWh",
                "entity_type": None,
                "nonnegative": False,
            },
        )

    def test_every_declarative_definition_reaches_the_frontend(self):
        self.login("analyst@example.local", "analyst pass")

        response = self.client.get(SIGNAL_CATALOG_PATH)

        self.assertEqual(
            [signal["signal_key"] for signal in response.json()["signals"]],
            list(TIME_SERIES_SIGNAL_CATALOG),
        )

    def test_a_new_declarative_entry_needs_no_endpoint_change(self):
        self.login("analyst@example.local", "analyst pass")
        added = TimeSeriesSignalDefinition(
            signal_key="load_reactive_power_mvar",
            unit="MVAr",
            entity_type="component:load",
            nonnegative=False,
        )

        with mock.patch.dict(
            TIME_SERIES_SIGNAL_CATALOG, {"load_reactive_power_mvar": added}
        ):
            response = self.client.get(SIGNAL_CATALOG_PATH)

        self.assertIn(
            {
                "signal_key": "load_reactive_power_mvar",
                "unit": "MVAr",
                "entity_type": "component:load",
                "nonnegative": False,
            },
            response.json()["signals"],
        )

    def test_an_external_operator_is_refused_at_the_application_boundary(self):
        self.login("operator@example.local", "operator pass")

        response = self.client.get(SIGNAL_CATALOG_PATH)

        self.assertEqual(response.status_code, 404)

    def test_an_anonymous_request_is_refused(self):
        response = self.client.get(SIGNAL_CATALOG_PATH)

        self.assertEqual(response.status_code, 401)


class ExternalConsolePayloadBoundaryTests(unittest.TestCase):
    """A catalog-driven configuration never carries its signals outward."""

    def console(self):
        return {
            "id": 4,
            "status": "active",
            "updated_at": "2026-08-23T12:00:00Z",
            "prepared_by_user_id": 7,
            "document": {
                "schema_version": "operator_console_config.v1",
                "public_identity": {
                    "name": "Plan diario Planta Norte",
                    "description": "Ajuste diario",
                },
                "parameters": [
                    {
                        "id": "potencia_bess",
                        "pointer": {"asset_id": "battery_1", "field": "power_max_mw"},
                        "label": "Potencia maxima BESS",
                        "unit": "MW",
                        "min": 0,
                        "max": 100,
                        "default": 40,
                    }
                ],
                "groups": [
                    {
                        "id": "potencia",
                        "label": "Potencia",
                        "granularities": ["day"],
                        "columns": [
                            {
                                "id": "demanda",
                                "signal": {
                                    "entity_type": "component:load",
                                    "entity_id": "load_1",
                                    "signal_key": "load_demand_mw",
                                },
                                "label": "Demanda",
                                "editable": True,
                                "source_options": [
                                    {
                                        "id": "base",
                                        "label": "Demanda base",
                                        "time_series_set_id": 18,
                                    }
                                ],
                                "default_source_option_id": "base",
                            }
                        ],
                    }
                ],
                "results": {"kpis": [], "charts": [], "tables": []},
            },
        }

    def assert_no_canonical_leak(self, payload):
        serialized = json.dumps(payload)
        for signal_key in TIME_SERIES_SIGNAL_CATALOG:
            with self.subTest(signal_key):
                self.assertNotIn(signal_key, serialized)
        for pointer in ["component:load", "load_1", "battery_1", "power_max_mw"]:
            with self.subTest(pointer):
                self.assertNotIn(pointer, serialized)

    def test_the_console_payload_keeps_signals_and_pointers_inside(self):
        payload = build_console_payload(
            console=self.console(), prepared_by="Ana Analista"
        )

        self.assert_no_canonical_leak(payload)

    def test_the_console_list_entry_keeps_signals_and_pointers_inside(self):
        entry = build_console_list_entry(
            console=self.console(), project_name="Planta Norte"
        )

        self.assert_no_canonical_leak(entry)

    def test_configured_column_ids_and_labels_are_what_may_cross(self):
        payload = build_console_payload(
            console=self.console(), prepared_by="Ana Analista"
        )

        self.assertEqual(
            payload["console"]["name"], "Plan diario Planta Norte"
        )
        self.assertNotIn("groups", json.dumps(payload))


if __name__ == "__main__":
    unittest.main()
