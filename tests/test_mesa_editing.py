"""MESA-006: edit/reload through the authenticated HTTP boundary (S2)."""

import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi.testclient import TestClient

from app.auth import hash_password
from app.main import create_app
from app.persistence import AnalystStore
from tests.auth_test_helpers import login_json_with_csrf, post_json_with_csrf
from tests.mesa_fixture import seed_mesa_case, seed_mesa_run
from tests.mesa_hydraulic_fixture import seed_hydraulic_mesa, bind_hydraulic_mesa_inflow


class MesaEditingApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = AnalystStore(f"sqlite:///{Path(self.temp.name) / 'mesa.sqlite3'}")
        self.store.create_user(email="mesa@example.local", display_name="Analista", role="analyst",
                               password_hash=hash_password("mesa test pass"))
        self.fixture = seed_mesa_case(self.store)
        self.client = TestClient(create_app(store=self.store, auth_enabled=True))
        self.addCleanup(self.store.close)
        self.addCleanup(self.client.close)
        login_json_with_csrf(self.client, "mesa@example.local", "mesa test pass")
        self.path = f"/api/scenarios/{self.fixture['scenario']['id']}/mesa"
        self.params = {"case_id": self.fixture["case"]["id"], "variant_id": self.fixture["variant"]["id"]}
        self.target = f"{self.path}/inputs/{self.fixture['object']['id']}/load_demand_mw"

    def edit(self):
        response = self.client.get(self.target, params=self.params)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def save(self, edit, value=15):
        return post_json_with_csrf(self.client, self.target + "/revisions", self.payload(edit, value))

    def payload(self, edit, value=15):
        points = [dict(p) for p in edit["series"]["points"]]
        points[1]["value"] = value
        return {
            **self.params, "expected": edit["expected"], "unit": edit["series"]["unit"], "points": points,
            "confirm": True, "reason": "Corrección de demanda medida",
        }

    def test_edit_creates_a_canonical_revision_recoverable_with_actor_and_source(self):
        edit = self.edit()
        saved = self.save(edit)
        self.assertEqual(saved.status_code, 201, saved.text)
        for _ in range(2):
            body = self.client.get(self.path, params=self.params).json()
            series = next(c["series"] for c in body["components"] if c["entity_id"] == "load_north")
            self.assertEqual([p["value"] for p in series["points"]], [10.0, 15.0])
            self.assertEqual([(p["start"], p["end"]) for p in series["points"]], [
                ("2026-10-20T00:00:00-03:00", "2026-10-20T01:00:00-03:00"),
                ("2026-10-20T01:00:00-03:00", "2026-10-20T02:00:00-03:00"),
            ])
            self.assertNotEqual(series["revision_id"], edit["series"]["revision_id"])
            revisions = self.client.get(f"/api/projects/{self.fixture['project']['id']}/linkable-objects/{self.fixture['object']['id']}/time-series/object-series/{series['signal_id']}/revisions")
            self.assertEqual(revisions.status_code, 200, revisions.text)
            self.assertEqual(revisions.json()["items"][0]["created_by"], "mesa@example.local")
            self.assertEqual(revisions.json()["items"][0]["change_summary"], "mesa_input_edited")
        again = self.edit()
        self.assertIn("mesa", again["source_reference"])
        self.assertEqual(again["series"]["revision_id"], saved.json()["revision_id"])

    def test_a_concurrent_editor_cannot_overwrite_the_saved_revision(self):
        first, second = self.edit(), self.edit()
        saved = self.save(first, 15)
        self.assertEqual(saved.status_code, 201, saved.text)
        rejected = self.save(second, 99)
        self.assertEqual(rejected.status_code, 409, rejected.text)
        current = self.edit()
        self.assertEqual([p["value"] for p in current["series"]["points"]], [10, 15])
        self.assertEqual(current["series"]["revision_id"], saved.json()["revision_id"])

    def test_edit_refuses_a_changed_unit_instead_of_reinterpreting_values(self):
        edit = self.edit()
        payload = {**self.payload(edit), "unit": "MWh"}
        rejected = post_json_with_csrf(self.client, self.target + "/revisions", payload)
        self.assertEqual(rejected.status_code, 400, rejected.text)
        self.assertEqual(self.edit()["series"]["revision_id"], edit["series"]["revision_id"])

    def publish_changed_source(self):
        self.store.publish_canonical_set_revision(project_id=self.fixture["project"]["id"],
            set_id=self.fixture["receipt"]["set_id"], name="Demanda horaria", data_class_key="real",
            timezone="America/Santiago", actor="other-session",
            signals=[{"series_key": "demand", "display_name": "Demanda medida", "semantic_type_key": "load_demand", "unit_key": "mw", "signal_role": "input", "aggregation": "mean"}],
            periods=[{"timestamp_start": "2026-10-20T00:00:00-03:00", "timestamp_end": "2026-10-20T01:00:00-03:00", "duration_hours": 1},
                     {"timestamp_start": "2026-10-20T01:00:00-03:00", "timestamp_end": "2026-10-20T02:00:00-03:00", "duration_hours": 1}],
            values={"demand": [11, 16]})

    def test_source_revision_changed_outside_the_mesa_is_a_conflict(self):
        edit = self.edit()
        self.publish_changed_source()
        response = self.save(edit)
        self.assertEqual(response.status_code, 409, response.text)
        mesa = self.client.get(self.path, params=self.params).json()
        series = next(c["series"] for c in mesa["components"] if c["entity_id"] == "load_north")
        self.assertFalse(series["editable"])
        self.assertEqual(series["revision_id"], edit["series"]["revision_id"])

    def test_table_edit_preserves_full_coverage_and_interval_identity(self):
        edit = self.edit()
        payload = self.payload(edit)
        payload["points"] = payload["points"][:1]
        rejected = post_json_with_csrf(self.client, self.target + "/revisions", payload)
        self.assertEqual(rejected.status_code, 400, rejected.text)
        self.assertEqual([p["value"] for p in self.edit()["series"]["points"]], [10, 12])

    def test_save_requires_confirmation_of_the_local_copy_scope(self):
        edit = self.edit()
        self.assertEqual(edit["scope"], "local_copy")
        payload = {**self.payload(edit), "confirm": False}
        rejected = post_json_with_csrf(self.client, self.target + "/revisions", payload)
        self.assertEqual(rejected.status_code, 400, rejected.text)
        self.assertEqual(self.edit()["series"]["revision_id"], edit["series"]["revision_id"])

    def test_subsequent_edits_version_the_local_copy_and_keep_previous_revisions(self):
        self.assertEqual(self.save(self.edit(), 15).status_code, 201)
        second = self.edit()
        self.assertEqual(second["scope"], "local_revision")
        saved = self.save(second, 18)
        self.assertEqual(saved.status_code, 201, saved.text)
        current = self.edit()["series"]
        self.assertEqual(current["time_series_set_id"], second["series"]["time_series_set_id"])
        self.assertEqual(current["revision_number"], 2)
        self.assertEqual([p["value"] for p in current["points"]], [10, 18])
        revisions = self.client.get(f"/api/projects/{self.fixture['project']['id']}/linkable-objects/{self.fixture['object']['id']}/time-series/object-series/{current['signal_id']}/revisions").json()
        self.assertEqual([r["number"] for r in revisions["items"]], [2, 1])

    def test_invalid_demand_rolls_back_without_publishing_or_leaving_a_local_definition(self):
        edit = self.edit()
        root = f"/api/projects/{self.fixture['project']['id']}/linkable-objects/{self.fixture['object']['id']}/time-series"
        before = self.client.get(root).json()
        rejected = self.save(edit, -1)
        self.assertEqual(rejected.status_code, 422, rejected.text)
        self.assertEqual(self.edit()["series"]["revision_id"], edit["series"]["revision_id"])
        self.assertEqual(self.client.get(root).json()["summary"], before["summary"])

    def test_edit_invalidates_previous_preparation_but_preserves_historical_run(self):
        run = seed_mesa_run(self.store, self.fixture, Path(self.temp.name))
        before = self.client.get(self.path, params={**self.params, "run_id": run["id"]}).json()
        edit = self.edit()
        saved = self.save(edit)
        self.assertEqual(saved.status_code, 201, saved.text)
        self.assertEqual(saved.json()["preparation_status"], "pending_validation")
        obsolete = post_json_with_csrf(self.client,
            f"/api/scenarios/{self.fixture['scenario']['id']}/case/variants/{self.fixture['variant']['id']}/validate",
            {"range_start": "2026-10-20T00:00:00-03:00", "range_end": "2026-10-20T02:00:00-03:00",
             "expected_bindings_revision": edit["expected"]["bindings_revision"]})
        self.assertEqual(obsolete.status_code, 409, obsolete.text)
        after = self.client.get(self.path, params={**self.params, "run_id": run["id"]}).json()
        self.assertEqual(after["selected_run"], before["selected_run"])
        battery = lambda body: next(c for c in body["components"] if c["entity_id"] == "battery_1")
        self.assertEqual(battery(after), battery(before))

    def test_shared_source_and_other_variant_are_unchanged_by_the_local_copy(self):
        variant = self.store.create_case_input_variant(case_id=self.fixture["case"]["id"], display_name="Consumidor compartido")
        document = {"expected_bindings_revision": 0, "operations": [{
            "client_operation_id": "share", "action": "create", "linkable_object_id": self.fixture["object"]["id"],
            "binding_role_key": "load_demand", "signal_id": self.fixture["receipt"]["signal_ids"]["demand"],
            "revision": {"mode": "current", "revision_id": self.fixture["receipt"]["revision_id"], "content_hash": self.fixture["receipt"]["content_hash"]},
            "catalog_association_id": None, "reason_code": "variant_input_selected",
        }]}
        preview = self.store.prevalidate_case_binding_batch(scenario_id=self.fixture["scenario"]["id"], variant_id=variant["id"], document=document, actor_class="internal")
        self.store.commit_case_binding_batch(scenario_id=self.fixture["scenario"]["id"], variant_id=variant["id"], document=document,
            actor_user={"id": 1, "email": "mesa-fixture", "role": "analyst"}, actor_class="internal", request_id="shared-fixture",
            prevalidation_token=preview["prevalidation_token"], if_match=preview["commit_etag"], idempotency_key="shared-fixture", confirmed=True)
        self.assertEqual(self.save(self.edit()).status_code, 201)
        other = self.client.get(self.path, params={**self.params, "variant_id": variant["id"]}).json()
        demand = next(c["series"] for c in other["components"] if c["entity_id"] == "load_north")
        self.assertEqual([p["value"] for p in demand["points"]], [10, 12])
        self.assertEqual(demand["revision_id"], self.fixture["receipt"]["revision_id"])
        self.assertEqual(demand["binding_state"], "valid_current")

    def test_foreign_context_outputs_and_unauthorized_writers_are_refused(self):
        edit = self.edit()
        other = seed_mesa_case(self.store, name="Otro")
        payload = self.payload(edit)
        for changed in ({"case_id": other["case"]["id"]}, {"variant_id": other["variant"]["id"]}):
            rejected = post_json_with_csrf(self.client, self.target + "/revisions", {**payload, **changed})
            self.assertEqual(rejected.status_code, 404, rejected.text)
        inventory = self.client.get(self.path, params=self.params).json()
        battery = next(c for c in inventory["components"] if c["entity_id"] == "battery_1")
        output = f"{self.path}/inputs/{battery['linkable_object_id']}/bess_charge_power_mw/revisions"
        self.assertEqual(post_json_with_csrf(self.client, output, payload).status_code, 400)
        self.assertEqual(self.client.post(self.target + "/revisions", json=payload).status_code, 403)
        self.store.create_user(email="external@example.local", display_name="Externo", role="external", password_hash=hash_password("external pass"))
        external = TestClient(self.client.app)
        self.addCleanup(external.close)
        self.assertEqual(external.post(self.target + "/revisions", json=payload).status_code, 401)
        login_json_with_csrf(external, "external@example.local", "external pass")
        self.assertEqual(post_json_with_csrf(external, self.target + "/revisions", payload).status_code, 404)
        self.assertEqual(self.edit()["series"]["revision_id"], edit["series"]["revision_id"])

    def test_a_boolean_is_not_a_numeric_measurement(self):
        edit = self.edit()
        rejected = self.save(edit, True)
        self.assertEqual(rejected.status_code, 422, rejected.text)
        self.assertEqual(self.edit()["series"]["revision_id"], edit["series"]["revision_id"])

    def test_two_database_connections_racing_publish_only_one_edit(self):
        second_store = AnalystStore(f"sqlite:///{Path(self.temp.name) / 'mesa.sqlite3'}")
        second = TestClient(create_app(store=second_store, auth_enabled=True))
        self.addCleanup(second_store.close)
        self.addCleanup(second.close)
        login_json_with_csrf(second, "mesa@example.local", "mesa test pass")
        edit = self.edit()
        with ThreadPoolExecutor(max_workers=2) as workers:
            requests = [workers.submit(post_json_with_csrf, client, self.target + "/revisions", self.payload(edit, value))
                        for client, value in ((self.client, 15), (second, 18))]
            responses = [request.result() for request in requests]
        self.assertEqual(sorted(r.status_code for r in responses), [201, 409], [r.text for r in responses])
        current = second.get(self.target, params=self.params).json()
        winner = 15 if responses[0].status_code == 201 else 18
        self.assertEqual([p["value"] for p in current["series"]["points"]], [10, winner])
        self.assertEqual(current["series"]["revision_number"], 1)

    def test_pinned_historical_input_remains_read_only(self):
        edit = self.edit()
        self.publish_changed_source()
        document = {"expected_bindings_revision": edit["expected"]["bindings_revision"], "operations": [{
            "client_operation_id": "pin", "action": "revalidate_pinned", "binding_id": edit["expected"]["binding_id"],
            "expected_lifecycle_revision": 1, "revision": {"mode": "pinned", "revision_id": edit["series"]["revision_id"], "content_hash": edit["series"]["content_hash"]},
            "reason_code": "revalidated_pinned", "reason_text": "Conservar referencia histórica",
        }]}
        preview = self.store.prevalidate_case_binding_batch(scenario_id=self.fixture["scenario"]["id"], variant_id=self.fixture["variant"]["id"], document=document, actor_class="internal")
        self.store.commit_case_binding_batch(scenario_id=self.fixture["scenario"]["id"], variant_id=self.fixture["variant"]["id"], document=document,
            actor_user={"id": 1, "email": "mesa-fixture", "role": "analyst"}, actor_class="internal", request_id="pin-fixture",
            prevalidation_token=preview["prevalidation_token"], if_match=preview["commit_etag"], idempotency_key="pin-fixture", confirmed=True)
        mesa = self.client.get(self.path, params=self.params).json()
        series = next(c["series"] for c in mesa["components"] if c["entity_id"] == "load_north")
        self.assertEqual(series["binding_state"], "valid_pinned")
        self.assertFalse(series["editable"])
        self.assertEqual(self.save(edit).status_code, 400)

    def test_the_same_edit_contract_supports_canonical_renewable_and_inflow_inputs(self):
        for hydraulic in (False, True):
            with self.subTest(hydraulic=hydraulic):
                self.fixture = seed_hydraulic_mesa(self.store) if hydraulic else seed_mesa_case(self.store, electrical=True)
                if hydraulic:
                    bind_hydraulic_mesa_inflow(self.store, self.fixture, self.fixture["variant"])
                self.path = f"/api/scenarios/{self.fixture['scenario']['id']}/mesa"
                self.params = {"case_id": self.fixture["case"]["id"], "variant_id": self.fixture["variant"]["id"]}
                entity = "reservoir" if hydraulic else "solar_north"
                body = self.client.get(self.path, params=self.params).json()
                component = next(c for c in body["components"] if c["entity_id"] == entity)
                self.target = f"{self.path}/inputs/{component['linkable_object_id']}/{component['series']['signal_key']}"
                saved = self.save(self.edit(), 13)
                self.assertEqual(saved.status_code, 201, saved.text)
                current = self.edit()["series"]
                self.assertEqual(current["unit"], "m3/s" if hydraulic else "MW")
                self.assertEqual([p["value"] for p in current["points"]], [7, 13] if hydraulic else [3, 13])

