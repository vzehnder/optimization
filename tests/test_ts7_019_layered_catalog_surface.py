"""TS7-019 gate and inspector payload of the layered catalog read surface.

The React surface itself is proven by `vitest`; this module proves the two
server-side halves it stands on: who the identity payload lets reach the
surface before the C6 cutover, and that the inspector can show coverage,
resolution and consumers from the detail alone, without downloading points.
"""

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.auth import hash_password
from app.main import create_app
from app.persistence import AnalystStore
from tests.auth_test_helpers import login_json_with_csrf


SIGNALS = [
    {
        "series_key": "energy_price",
        "display_name": "Precio de energia",
        "semantic_type_key": "energy_price",
        "unit_key": "usd_per_mwh",
        "signal_role": "input",
        "aggregation": "mean",
    },
]


def hourly_periods(count: int) -> list[dict]:
    return [
        {
            "timestamp_start": f"2026-01-01T{index:02d}:00:00",
            "timestamp_end": f"2026-01-01T{index + 1:02d}:00:00",
            "duration_hours": 1.0,
        }
        for index in range(count)
    ]


class CanonicalReadVerificationGateTests(unittest.TestCase):
    """`ts_next_canonical_read` opens only for the verification accounts."""

    def setUp(self):
        self.store = AnalystStore("sqlite:///:memory:")
        self.client = TestClient(create_app(store=self.store, auth_enabled=True))
        for email, role in (
            ("verifier@example.local", "admin"),
            ("analyst@example.local", "analyst"),
        ):
            self.store.create_user(
                email=email,
                display_name=email,
                role=role,
                password_hash=hash_password("secret pass"),
            )

    def tearDown(self):
        self.store.close()

    def _identity(self, email: str) -> tuple[dict, dict]:
        login = login_json_with_csrf(self.client, email, "secret pass")
        self.assertEqual(login.status_code, 200)
        response = self.client.get("/api/auth/me")
        self.assertEqual(response.status_code, 200)
        return login.json(), response.json()

    def test_the_verification_account_named_by_the_environment_reaches_the_surface(self):
        with patch.dict(
            "os.environ",
            {"MAIL_USUARIO_TEST": "verifier@example.local"},
            clear=False,
        ):
            logged_in, current = self._identity("verifier@example.local")
            self.assertTrue(current["ts_next_canonical_read"])
            self.assertTrue(
                logged_in["ts_next_canonical_read"],
                "login and current-user answer the same identity contract",
            )

    def test_a_regular_internal_user_keeps_the_pre_cutover_behaviour(self):
        with patch.dict(
            "os.environ",
            {"MAIL_USUARIO_TEST": "verifier@example.local"},
            clear=False,
        ):
            _, current = self._identity("analyst@example.local")
            self.assertFalse(current["ts_next_canonical_read"])

    def test_an_explicit_allowlist_replaces_the_single_verification_credential(self):
        with patch.dict(
            "os.environ",
            {
                "MAIL_USUARIO_TEST": "verifier@example.local",
                "TS_NEXT_CANONICAL_READ_ACCOUNTS": " Analyst@Example.local ,",
            },
            clear=False,
        ):
            _, verifier = self._identity("verifier@example.local")
            self.assertFalse(verifier["ts_next_canonical_read"])
            _, analyst = self._identity("analyst@example.local")
            self.assertTrue(analyst["ts_next_canonical_read"])

    def test_an_external_identity_never_reaches_the_surface(self):
        self.store.create_user(
            email="client@example.local",
            display_name="Client",
            role="external",
            password_hash=hash_password("secret pass"),
        )
        with patch.dict(
            "os.environ",
            {"TS_NEXT_CANONICAL_READ_ACCOUNTS": "client@example.local"},
            clear=False,
        ):
            _, external = self._identity("client@example.local")
            self.assertFalse(external["ts_next_canonical_read"])


class CatalogInspectorDetailTests(unittest.TestCase):
    """The inspector reads one detail and never a point (AC-DET-01, AC-CAT-04)."""

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
        self.assertEqual(login.status_code, 200)
        self.project = self.store.create_project(name="Cuenca Norte")
        self.receipt = self.store.publish_canonical_set_revision(
            project_id=self.project["id"],
            name="Inputs 2026",
            version_label="v1",
            description="Senales operativas",
            data_class_key="real",
            timezone="UTC",
            signals=SIGNALS,
            periods=hourly_periods(3),
            values={"energy_price": [70.0, 71.0, 72.0]},
            actor="analyst@example.local",
        )

    def tearDown(self):
        self.store.close()

    def _signal_id(self) -> int:
        page = self.client.get("/api/time-series/catalog/inputs")
        self.assertEqual(page.status_code, 200)
        return int(page.json()["items"][0]["signal_id"])

    def test_the_detail_carries_coverage_resolution_and_consumer_counts(self):
        signal_id = self._signal_id()
        listed = self.client.get("/api/time-series/catalog/inputs").json()["items"][0]
        detail = self.client.get(
            f"/api/time-series/catalog/inputs/{signal_id}"
        ).json()

        self.assertEqual(detail["coverage_summary"], listed["coverage_summary"])
        self.assertEqual(detail["origin_summary"], listed["origin_summary"])
        self.assertEqual(detail["link_summary"], listed["link_summary"])
        self.assertEqual(detail["coverage_summary"]["period_count"], 3)
        self.assertEqual(
            detail["coverage_summary"]["nominal_resolution_seconds"], 3600.0
        )
        self.assertEqual(detail["link_summary"]["association_count"], 0)
        self.assertEqual(detail["link_summary"]["binding_count"], 0)
        self.assertNotIn("points", detail)
