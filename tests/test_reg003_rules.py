"""Hourly rule inputs through authenticated HTTP and canonical persistence."""
import os
import time
import unittest

from tests import test_reg002_rules as baseline
from tests.test_reg001_rules import PAYLOAD
from tests.auth_test_helpers import csrf_headers, post_json_with_csrf
from tests.test_reg003_runtime import CODE, PARAMETERS


class HourlyRuleApiTests(unittest.TestCase):
    database_url = "sqlite:///:memory:"
    setUp = baseline.RuleApplicationApiTests.setUp
    tearDown = baseline.RuleApplicationApiTests.tearDown
    hydraulic_scope = baseline.RuleApplicationApiTests.hydraulic_scope

    def hourly_fixture(self, values=(8, 12, 16, 20), *, code=CODE, source_options=None):
        scope = self.hydraulic_scope()
        self.obj = self.store.get_linkable_object(self.client.get(self.root).json()["object"]["id"])
        inflow = self.source(values, **(source_options or {}))
        availability = self.source((1, 0.5, 0.75, 1), semantic="availability_factor", unit="dimensionless")
        ports = [self.port(inflow), self.port(availability, alias="disponibilidad", dimension_key="dimensionless",
                                            semantic_type_key="availability_factor", binding_role_key="rule_availability")]
        saved = post_json_with_csrf(self.client, self.root, {**PAYLOAD, "code": code, "parameters": PARAMETERS, "inputs": ports})
        self.assertEqual(saved.status_code, 201, saved.text)
        path = f"{self.root}/{saved.json()['id']}"
        publication = post_json_with_csrf(self.client, path + "/publications", {"expected_revision": 1}).json()
        return scope, path, publication, ports

    def preview(self, scope, path, publication):
        response = post_json_with_csrf(self.client, path + "/tests", {"expected_revision": 1, "publication_id": publication["id"], "scope": scope})
        self.assertEqual(response.status_code, 202, response.text)
        job = response.json()
        deadline = time.monotonic() + 30
        while job["status"] in {"queued", "running"} and time.monotonic() < deadline:
            time.sleep(0.05)
            job = self.client.get(f"{path}/tests/{job['id']}").json()
        return job

    def source(self, values=(8, 12, 16, 20), *, semantic="natural_inflow", unit="m3_per_s", periods=None, timezone="UTC", **kwargs):
        return self.store.publish_canonical_set_revision(
            project_id=self.project["id"], name=f"Entrada {semantic}", data_class_key="real", timezone=timezone,
            signals=[{"series_key": "input", "display_name": "Entrada", "semantic_type_key": semantic,
                      "unit_key": unit, "signal_role": "input", "aggregation": "mean"}],
            periods=periods if periods is not None else [{"timestamp_start": f"2026-01-01T0{t}:00:00", "timestamp_end": f"2026-01-01T0{t+1}:00:00",
                      "duration_hours": 1} for t in range(len(values))],
            values={"input": list(values)}, actor=self.user["email"], **kwargs,
        )

    def port(self, receipt, **kwargs):
        return {"alias": "afluente", "dimension_key": "flow", "semantic_type_key": "natural_inflow",
                "binding_role_key": "rule_inflow", "object_id": self.obj["id"],
                "signal_id": receipt["signal_ids"]["input"], "revision_id": receipt["revision_id"],
                "content_hash": receipt["content_hash"], **kwargs}

    def test_saved_and_published_input_keeps_exact_canonical_identity_revision_and_hash(self):
        source = self.source()
        port = self.port(source)
        saved = post_json_with_csrf(self.client, self.root, {**PAYLOAD, "inputs": [port]})
        self.assertEqual(saved.status_code, 201, saved.text)
        path = f"{self.root}/{saved.json()['id']}"
        self.assertEqual(self.client.get(path).json()["inputs"], [port])
        published = post_json_with_csrf(self.client, path + "/publications", {"expected_revision": 1})
        self.assertEqual(published.status_code, 201, published.text)
        self.assertEqual(published.json()["inputs"], [port])

    def test_input_contract_rejects_forged_revision_hash_semantics_and_object(self):
        source = self.source()
        for change in ({"content_hash": "0" * 64}, {"revision_id": 999999}, {"signal_id": 999999},
                       {"dimension_key": "power"}, {"semantic_type_key": "energy_price"},
                       {"binding_role_key": "rule_availability"}, {"object_id": 999999}):
            with self.subTest(change=change):
                response = post_json_with_csrf(self.client, self.root, {**PAYLOAD, "inputs": [self.port(source, **change)]})
                self.assertEqual(response.status_code, 422, response.text)
                self.assertEqual(response.json()["detail"]["alias"], "afluente")

    def test_selector_offers_compatible_inflow_and_dimensionless_availability(self):
        inflow = self.source()
        availability = self.source((1, 0.5, 0.75, 1), semantic="availability_factor", unit="dimensionless")
        self.source((1, 2, 3, 4), semantic="energy_price", unit="usd_per_mwh")
        response = self.client.get(self.root + "/input-candidates")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual({(p["signal_id"], p["binding_role_key"], p["series_kind"]) for p in response.json()["items"]},
                         {(inflow["signal_ids"]["input"], "rule_inflow", "catalog"),
                          (availability["signal_ids"]["input"], "rule_availability", "catalog")})

    def test_specific_inputs_remain_owned_by_their_unit_and_foreign_project_inputs_are_hidden(self):
        from tests.test_ts7_010_object_specific_series import DEFINITION, POINTS_INGESTION
        from tests.test_ts7_003_linkable_object_register import HydraulicFixture
        series_root = self.root.removesuffix("/rules") + "/time-series/object-series"
        definition = {**DEFINITION, "object_series_key": "input", "semantic_type_key": "availability_factor",
                      "intended_binding_role_key": "rule_availability", "unit_key": "dimensionless", "timezone": "UTC"}
        created = self.client.post(series_root, json=definition, headers={**csrf_headers(self.client), "Idempotency-Key": self.token})
        self.assertEqual(created.status_code, 201, created.text)
        identity = created.json()["object_series"]["signal_id"]
        target = f"{series_root}/{identity}/revision-ingestions"
        prepared = post_json_with_csrf(self.client, target + "/points", {**POINTS_INGESTION,
            "revision_contract": {**POINTS_INGESTION["revision_contract"], "timezone": "UTC"},
            "points": [{"timestamp_start": f"2026-01-01T0{t}:00:00Z", "duration_seconds": 3600, "values": {"input": {"value": 0.5}}} for t in range(4)]})
        self.assertEqual(prepared.status_code, 201, prepared.text)
        ingestion = prepared.json()["ingestion"]
        publication = self.client.post(f"{target}/{ingestion['ingestion_id']}/publications",
            json={"validation_token": ingestion["validation_token"], "confirm": False, "reason_code": "forecast_refresh"},
            headers={**csrf_headers(self.client), "If-Match": created.headers["etag"], "Idempotency-Key": self.token + "publish"})
        self.assertEqual(publication.status_code, 201, publication.text)
        port = self.client.get(self.root + "/input-candidates").json()["items"][0]
        self.assertEqual((port["signal_id"], port["series_kind"]), (identity, "object_specific"))
        source = self.source()
        for project in (self.project, self.store.create_project(name="Otro proyecto " + self.token)):
            fixture = HydraulicFixture(self.store, project["id"], prefix=self.token + str(project["id"]))
            obj = self.store.register_linkable_object(project_id=project["id"], object_kind="hydraulic_unit", subtype_id=fixture.ids["hydraulic_unit"])
            root = f"/api/projects/{project['id']}/linkable-objects/{obj['id']}/rules"
            candidates = self.client.get(root + "/input-candidates").json()["items"]
            self.assertNotIn(identity, [row["signal_id"] for row in candidates])
            forged = {k: port[k] for k in ("alias", "dimension_key", "semantic_type_key", "binding_role_key", "signal_id", "revision_id", "content_hash")}
            self.assertEqual(post_json_with_csrf(self.client, root, {**PAYLOAD, "inputs": [{**forged, "object_id": obj["id"]}]}).status_code, 422)
            if project != self.project:
                self.assertNotIn(source["signal_ids"]["input"], [row["signal_id"] for row in candidates])
                self.assertEqual(post_json_with_csrf(self.client, root, {**PAYLOAD, "inputs": [self.port(source, object_id=obj["id"])]}).status_code, 422)

    @unittest.skipUnless(os.environ.get("RULE_RUNTIME_IMAGE"), "pinned OCI image required")
    def test_preview_compiles_pinned_inputs_and_returns_complete_hourly_curves(self):
        from app.rule_worker import RuleWorker
        from app.rule_runtime import OCIExecutor
        scope, path, publication, ports = self.hourly_fixture()
        with RuleWorker(self.store, OCIExecutor.from_env()):
            job = self.preview(scope, path, publication)
        self.assertEqual(job["status"], "succeeded", job)
        self.assertEqual([r["constant"] for r in job["result"]["ir"]["rows"]], [-20, -2, -10, -3, -15, -4, -20, -5])
        snapshot = self.client.get(f"{path}/revisions/{job['id']}").json()
        self.assertEqual(snapshot["inputs"][0]["revision_id"], ports[0]["revision_id"])
        self.assertEqual(snapshot["inputs"][0]["values"], [8, 12, 16, 20])
        self.assertEqual(len(job["result"]["outputs"]), 8)

    @unittest.skipUnless(os.environ.get("RULE_RUNTIME_IMAGE"), "pinned OCI image required")
    def test_run_snapshot_preserves_input_values_hashes_and_calculated_outputs(self):
        from app.rule_worker import RuleWorker
        from app.rule_runtime import OCIExecutor
        scope, path, publication, ports = self.hourly_fixture()
        with RuleWorker(self.store, OCIExecutor.from_env()):
            job = self.preview(scope, path, publication)
        applied = post_json_with_csrf(self.client, path + "/applications", {"job_id": job["id"], "reason": "Límites horarios"})
        self.assertEqual(applied.status_code, 201, applied.text)
        response = post_json_with_csrf(self.client, f"/api/scenarios/{scope['scenario_id']}/case/variants/{scope['variant_id']}/run",
                                       {k: scope[k] for k in ("range_start", "range_end")})
        self.assertEqual(response.status_code, 201, response.text)
        version_path = f"/api/scenario-versions/{response.json()['scenario_version_id']}"
        version = self.client.get(version_path).json()["scenario_version"]
        snapshot = version["system_case_json"]["component_rules"]["applications"][0]
        self.assertEqual(snapshot["inputs"][0]["content_hash"], ports[0]["content_hash"])
        self.assertEqual(snapshot["inputs"][0]["values"], [8, 12, 16, 20])
        self.assertEqual(snapshot["outputs"], job["result"]["outputs"])
        self.source((4, 4, 4, 4))
        self.assertEqual(self.client.get(version_path).json()["scenario_version"], version)

    @unittest.skipUnless(os.environ.get("RULE_RUNTIME_IMAGE"), "pinned OCI image required")
    def test_preview_rejects_crossed_hourly_and_physical_bounds_with_the_period(self):
        from app.rule_worker import RuleWorker
        from app.rule_runtime import OCIExecutor
        for values, code in (((8, 12, 80, 20), CODE), ((8, 12, 200, 20), CODE.replace("maximo = ", "maximo = 10 * "))):
            with self.subTest(values=values):
                scope, path, publication, _ = self.hourly_fixture(values, code=code)
                with RuleWorker(self.store, OCIExecutor.from_env()):
                    job = self.preview(scope, path, publication)
                self.assertEqual(job["status"], "failed", job)
                self.assertEqual((job["result"]["error"]["code"], job["result"]["error"]["period"]), ("RULE_BOUNDS_CONFLICT", 2))

    @unittest.skipUnless(os.environ.get("RULE_RUNTIME_IMAGE"), "pinned OCI image required")
    def test_new_input_publication_blocks_runs_until_old_pin_is_explicitly_revalidated(self):
        from app.rule_worker import RuleWorker
        from app.rule_runtime import OCIExecutor
        scope, path, publication, ports = self.hourly_fixture()
        with RuleWorker(self.store, OCIExecutor.from_env()):
            job = self.preview(scope, path, publication)
        applied = post_json_with_csrf(self.client, path + "/applications", {"job_id": job["id"], "reason": "Inicial"}).json()
        newer = self.source((4, 4, 4, 4))
        run_path = f"/api/scenarios/{scope['scenario_id']}/case/variants/{scope['variant_id']}/run"
        body = {k: scope[k] for k in ("range_start", "range_end")}
        refused = post_json_with_csrf(self.client, run_path, body)
        self.assertEqual(refused.status_code, 409, refused.text)
        state = self.client.get(path + "/applications").json()["items"][0]
        self.assertEqual(state["validation_status"], "stale")
        self.assertEqual(state["inputs"][0]["revision_id"], ports[0]["revision_id"])
        with RuleWorker(self.store, OCIExecutor.from_env()):
            revalidated = self.preview(scope, path, publication)
        self.assertEqual(revalidated["status"], "succeeded", revalidated)
        post_json_with_csrf(self.client, f"{path}/applications/{applied['id']}/deactivate", {"expected_revision": 1, "reason": "Revalidar con programa anterior"})
        replacement = post_json_with_csrf(self.client, path + "/applications", {"job_id": revalidated["id"], "reason": "Mantener revisión anterior comprobada"})
        self.assertEqual(replacement.status_code, 201, replacement.text)
        self.assertEqual(replacement.json()["inputs"][0]["revision_id"], ports[0]["revision_id"])
        self.assertEqual(replacement.json()["inputs"][0]["current_revision_id"], newer["revision_id"])
        self.assertEqual(post_json_with_csrf(self.client, run_path, body).status_code, 201)

    @unittest.skipUnless(os.environ.get("RULE_RUNTIME_IMAGE"), "pinned OCI image required")
    def test_input_publication_during_materialization_leaves_no_version_or_run(self):
        from app.rule_worker import RuleWorker
        from app.rule_runtime import OCIExecutor
        scope, path, publication, _ = self.hourly_fixture()
        with RuleWorker(self.store, OCIExecutor.from_env()):
            job = self.preview(scope, path, publication)
        self.assertEqual(post_json_with_csrf(self.client, path + "/applications", {"job_id": job["id"], "reason": "Operación"}).status_code, 201)
        self.engine.after_validation = lambda: self.source((4, 4, 4, 4))
        response = post_json_with_csrf(self.client, f"/api/scenarios/{scope['scenario_id']}/case/variants/{scope['variant_id']}/run",
                                       {k: scope[k] for k in ("range_start", "range_end")})
        self.assertEqual(response.status_code, 409, response.text)
        self.assertEqual(self.client.get(f"/api/scenarios/{scope['scenario_id']}/versions").json()["versions"], [])
        self.assertEqual(self.client.get(f"/api/scenarios/{scope['scenario_id']}/runs").json()["runs"], [])

    @unittest.skipUnless(os.environ.get("RULE_RUNTIME_IMAGE"), "pinned OCI image required")
    def test_incomplete_misaligned_and_ambiguous_grids_block_with_input_location(self):
        from app.rule_worker import RuleWorker
        from app.rule_runtime import OCIExecutor
        normal = [{"timestamp_start": f"2026-01-01T0{t}:00:00", "timestamp_end": f"2026-01-01T0{t+1}:00:00", "duration_hours": 1} for t in range(4)]
        cases = [( (8, 12, 16), {}, 3),
                 ((8, 12, 16), {"periods": [normal[0], normal[2], normal[3]]}, 1),
                 ((8, 12, 16, 20), {"periods": [
                     {"timestamp_start": "2026-01-01T00:00:00+00:00", "timestamp_end": "2026-01-01T01:00:00+00:00", "duration_hours": 1},
                     {"timestamp_start": "2026-01-01T01:00:00+01:00", "timestamp_end": "2026-01-01T02:00:00+01:00", "duration_hours": 1},
                     {"timestamp_start": "2026-01-01T03:00:00+01:00", "timestamp_end": "2026-01-01T04:00:00+01:00", "duration_hours": 1},
                     {"timestamp_start": "2026-01-01T04:00:00+01:00", "timestamp_end": "2026-01-01T05:00:00+01:00", "duration_hours": 1}]}, 0),
                 ((8, 12, 16, 20), {"periods": [{**p, "duration_hours": 0.5} for p in normal]}, 0),
                 ((8, 12, 16, 20), {"timezone": "America/Santiago"}, 0)]
        fixtures = [(self.hourly_fixture(values, source_options=options), options, period) for values, options, period in cases]
        with RuleWorker(self.store, OCIExecutor.from_env()):
            for (scope, path, publication, _), options, period in fixtures:
                with self.subTest(options=options):
                    response = post_json_with_csrf(self.client, path + "/tests", {"expected_revision": 1, "publication_id": publication["id"], "scope": scope})
                    self.assertEqual(response.status_code, 422, response.text)
                    self.assertEqual((response.json()["detail"]["alias"], response.json()["detail"]["period"]), ("afluente", period))


@unittest.skipUnless(os.environ.get("POSTGRES_TEST_DATABASE_URL"), "isolated PostgreSQL URL required")
class PostgresHourlyRuleApiTests(HourlyRuleApiTests):
    database_url = os.environ.get("POSTGRES_TEST_DATABASE_URL")
