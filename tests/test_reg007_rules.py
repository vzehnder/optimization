"""REG-007: confirmed HTTP/catalog seams, real OCI, SQLite and PostgreSQL."""
import os
import time
import unittest

from tests import test_reg003_rules as hourly
from tests.test_reg001_rules import PAYLOAD
from tests.auth_test_helpers import csrf_headers, post_json_with_csrf, put_json_with_csrf


CODE = '''def construir(ctx):
    for t in ctx.periodos:
        ctx.salida("potencia", t, ctx.parametros.capacidad * ctx.entradas.disponibilidad[t])
'''
PARAMETERS = [{"name": "capacidad", "type": "number", "unit": "mw", "value": 20}]


@unittest.skipUnless(os.environ.get("RULE_RUNTIME_IMAGE"), "pinned OCI image required")
class CalculatedSeriesApiTests(unittest.TestCase):
    database_url = "sqlite:///:memory:"
    setUp = hourly.HourlyRuleApiTests.setUp
    tearDown = hourly.HourlyRuleApiTests.tearDown
    hydraulic_scope = hourly.HourlyRuleApiTests.hydraulic_scope
    source = hourly.HourlyRuleApiTests.source
    port = hourly.HourlyRuleApiTests.port
    preview = hourly.HourlyRuleApiTests.preview

    def calculation(self, code=CODE, parameters=PARAMETERS):
        from app.rule_worker import RuleWorker
        from app.rule_runtime import OCIExecutor
        scope = self.hydraulic_scope()
        self.obj = self.store.get_linkable_object(self.client.get(self.root).json()["object"]["id"])
        source = self.source((1, .5, .75, 1), semantic="availability_factor", unit="dimensionless")
        port = self.port(source, alias="disponibilidad", dimension_key="dimensionless",
                         semantic_type_key="availability_factor", binding_role_key="rule_availability")
        body = {**PAYLOAD, "code": code, "parameters": parameters, "inputs": [port]}
        saved = post_json_with_csrf(self.client, self.root, body)
        self.assertEqual(saved.status_code, 201, saved.text)
        path = self.root + "/" + saved.json()["id"]
        publication = post_json_with_csrf(self.client, path + "/publications", {"expected_revision": 1}).json()
        with RuleWorker(self.store, OCIExecutor.from_env()):
            job = self.preview(scope, path, publication)
        self.assertEqual(job["status"], "succeeded", job)
        return path, job, source, body

    def publish(self, path, job, **changes):
        body = {"job_id": job["id"], "output_name": "potencia", "name": "Potencia calculada " + self.token,
                "series_key": "potencia", "semantic_type_key": "renewable_available_power", "unit_key": "mw",
                "series_kind": "catalog", "reason": "Cálculo verificado", **changes}
        return self.client.post(path + "/series-publications", json=body,
                                headers={**csrf_headers(self.client), "Idempotency-Key": self.token})

    def points(self, receipt):
        response = self.client.get(f"/api/time-series/catalog/inputs/{receipt['signal_id']}/preview", params={
            "revision_id": receipt["revision_id"], "from": "2026-01-01T00:00:00Z", "to": "2026-01-01T04:00:00Z",
            "sampling": "none", "max_points": 4})
        self.assertEqual(response.status_code, 200, response.text)
        return [p["value"] for p in response.json()["points"]]

    def changed_job(self, path, scope, body, revision=1):
        from app.rule_worker import RuleWorker
        from app.rule_runtime import OCIExecutor
        saved = put_json_with_csrf(self.client, path, {**body, "expected_revision": revision})
        self.assertEqual(saved.status_code, 200, saved.text)
        published = post_json_with_csrf(self.client, path + "/publications", {"expected_revision": revision + 1}).json()
        with RuleWorker(self.store, OCIExecutor.from_env()):
            response = post_json_with_csrf(self.client, path + "/tests", {"expected_revision": revision + 1,
                "publication_id": published["id"], "scope": scope})
            self.assertEqual(response.status_code, 202, response.text)
            job = response.json()
            deadline = time.monotonic() + 30
            while job["status"] in {"queued", "running"} and time.monotonic() < deadline:
                time.sleep(.05)
                job = self.client.get(f"{path}/tests/{job['id']}").json()
        self.assertEqual(job["status"], "succeeded", job)
        return job

    def test_publishes_complete_numeric_output_in_catalog_with_frozen_recipe(self):
        path, job, source, _ = self.calculation()
        response = self.publish(path, job)
        self.assertEqual(response.status_code, 201, response.text)
        receipt = response.json()
        self.assertEqual(self.points(receipt), [20, 10, 15, 20])
        detail = self.client.get(f"{path}/series-publications/{receipt['id']}")
        self.assertEqual(detail.status_code, 200, detail.text)
        recipe = detail.json()["lineage"]
        self.assertEqual(recipe["publication_id"], job["publication_id"])
        self.assertEqual(recipe["inputs"][0]["revision_id"], source["revision_id"])
        self.assertEqual(recipe["inputs"][0]["content_hash"], source["content_hash"])
        self.assertEqual(recipe["parameters"][0]["value"], 20)
        self.assertEqual(recipe["runtime"], job["runtime"])
        self.assertEqual(len(recipe["output_hash"]), 64)
        self.assertEqual(len(recipe["grid"]), 4)
        self.assertEqual(recipe["code_hash"], job["code_hash"])
        self.assertEqual(detail.json()["validation_status"], "current")

    def test_retry_returns_same_publication_and_key_cannot_change_intent(self):
        path, job, _, _ = self.calculation()
        first = self.publish(path, job)
        self.assertEqual(first.status_code, 201, first.text)
        replay = self.publish(path, job)
        self.assertEqual(replay.status_code, 201, replay.text)
        self.assertEqual(replay.json(), first.json())
        conflict = self.publish(path, job, name="Otra intención")
        self.assertEqual(conflict.status_code, 409, conflict.text)
        history = self.client.get(f"/api/time-series/catalog/inputs/{first.json()['signal_id']}/revisions").json()
        self.assertEqual(len(history["items"]), 1)

    def test_existing_catalog_input_is_never_overwritten_by_a_new_calculation(self):
        path, job, source, _ = self.calculation()
        response = self.publish(path, job, name="Entrada availability_factor")
        self.assertEqual(response.status_code, 409, response.text)
        original = {"signal_id": source["signal_ids"]["input"], "revision_id": source["revision_id"]}
        self.assertEqual(self.points(original), [1, .5, .75, 1])
        history = self.client.get(f"/api/time-series/catalog/inputs/{original['signal_id']}/revisions").json()
        self.assertEqual(len(history["items"]), 1)

    def test_changed_source_marks_recipe_stale_and_old_preview_cannot_publish(self):
        path, job, _, _ = self.calculation()
        receipt = self.publish(path, job).json()
        self.source((.5, .5, .5, .5), semantic="availability_factor", unit="dimensionless")
        detail = self.client.get(f"{path}/series-publications/{receipt['id']}").json()
        self.assertEqual(detail["validation_status"], "stale")
        self.assertIn("entrada", detail["validation_error"]["message"].lower())
        self.assertEqual(self.points(receipt), [20, 10, 15, 20])
        self.token += "new"
        self.assertEqual(self.publish(path, job).status_code, 409)

    def test_regeneration_creates_new_revision_even_for_equal_values_and_keeps_history(self):
        from app.rule_worker import RuleWorker
        from app.rule_runtime import OCIExecutor
        path, job, _, body = self.calculation()
        original = self.publish(path, job).json()
        changed = put_json_with_csrf(self.client, path, {**body, "expected_revision": 1, "code": CODE + "\n# Otra receta\n"})
        self.assertEqual(changed.status_code, 200, changed.text)
        publication = post_json_with_csrf(self.client, path + "/publications", {"expected_revision": 2}).json()
        detail_path = f"{path}/series-publications/{original['id']}"
        self.assertEqual(self.client.get(detail_path).json()["validation_status"], "stale")
        with RuleWorker(self.store, OCIExecutor.from_env()):
            response = post_json_with_csrf(self.client, path + "/tests", {"expected_revision": 2,
                "publication_id": publication["id"], "scope": job["compilation_scope"]})
            self.assertEqual(response.status_code, 202, response.text)
            import time
            pending = response.json()
            deadline = time.monotonic() + 30
            while pending["status"] in {"queued", "running"} and time.monotonic() < deadline:
                time.sleep(.05)
                pending = self.client.get(f"{path}/tests/{pending['id']}").json()
        self.assertEqual(pending["status"], "succeeded", pending)
        request = {"job_id": pending["id"], "expected_revision_id": original["revision_id"], "reason": "Actualizar receta"}
        headers = {**csrf_headers(self.client), "Idempotency-Key": self.token + "regen"}
        response = self.client.post(detail_path + "/regenerations", json=request, headers=headers)
        self.assertEqual(response.status_code, 201, response.text)
        new = response.json()
        self.assertEqual((new["id"], new["set_id"], new["signal_id"]), (original["id"], original["set_id"], original["signal_id"]))
        self.assertNotEqual(new["revision_id"], original["revision_id"])
        self.assertEqual(new["revision_number"], 2)
        self.assertEqual(new["lineage"]["publication_id"], publication["id"])
        self.assertEqual(self.points(original), [20, 10, 15, 20])
        self.assertEqual(self.points(new), [20, 10, 15, 20])
        self.assertEqual(self.client.post(detail_path + "/regenerations", json=request, headers=headers).json(), new)
        headers["Idempotency-Key"] += "conflict"
        self.assertEqual(self.client.post(detail_path + "/regenerations", json=request, headers=headers).status_code, 409)

    def test_object_specific_output_is_visible_only_under_its_immutable_owner(self):
        path, job, _, _ = self.calculation(CODE.replace("ctx.parametros.capacidad * ", ""))
        response = self.publish(path, job, unit_key="dimensionless", semantic_type_key="availability_factor",
                                series_kind="object_specific", intended_binding_role_key="rule_availability")
        self.assertEqual(response.status_code, 201, response.text)
        receipt = response.json()
        candidates = self.client.get(self.root + "/input-candidates").json()["items"]
        selected = next(p for p in candidates if p["signal_id"] == receipt["signal_id"])
        self.assertEqual((selected["series_kind"], selected["owner_linkable_object_id"]), ("object_specific", self.obj["id"]))
        self.assertEqual(self.client.get(f"/api/time-series/catalog/inputs/{receipt['signal_id']}").status_code, 404)
        object_path = self.root.removesuffix("/rules") + f"/time-series/object-series/{receipt['signal_id']}"
        self.assertEqual(self.client.get(object_path).status_code, 200)
        other = self.store.ensure_global_signal_slot(project_id=self.project["id"], display_name="Otro objeto")
        foreign = object_path.replace(f"linkable-objects/{self.obj['id']}/", f"linkable-objects/{other['id']}/")
        self.assertEqual(self.client.get(foreign).status_code, 404)
        target = f"{path}/series-publications/{receipt['id']}/regenerations"
        regenerated = self.client.post(target, json={"job_id": job["id"], "expected_revision_id": receipt["revision_id"], "reason": "Regeneración explícita"},
            headers={**csrf_headers(self.client), "Idempotency-Key": self.token + "specific"})
        self.assertEqual(regenerated.status_code, 201, regenerated.text)
        self.assertEqual((regenerated.json()["signal_id"], regenerated.json()["revision_number"]), (receipt["signal_id"], 2))

    def test_only_complete_numeric_outputs_are_offered_with_compatible_classification(self):
        path, job, _, _ = self.calculation(CODE + '    ctx.salida("parcial", 0, ctx.parametros.capacidad)\n')
        response = self.client.get(f"{path}/tests/{job['id']}/series-options")
        self.assertEqual(response.status_code, 200, response.text)
        options = response.json()["outputs"]
        self.assertEqual([(p["name"], p["unit_key"], p["period_count"]) for p in options], [("potencia", "mw", 4)])
        self.assertIn("renewable_available_power", [s["semantic_type_key"] for s in options[0]["classifications"]])
        self.assertNotIn("natural_inflow", [s["semantic_type_key"] for s in options[0]["classifications"]])
        for change in ({"output_name": "parcial"}, {"unit_key": "m3_per_s"}, {"semantic_type_key": "natural_inflow"}):
            with self.subTest(change=change):
                response = self.publish(path, job, **change)
                self.assertEqual(response.status_code, 422, response.text)

    def test_recipe_cannot_regenerate_from_its_own_published_output(self):
        path, job, _, body = self.calculation(CODE.replace("ctx.parametros.capacidad * ", ""))
        original = self.publish(path, job, unit_key="dimensionless", semantic_type_key="availability_factor").json()
        source = {"signal_ids": {"input": original["signal_id"]}, **original}
        source["signal_ids"] = {"input": original["signal_id"]}
        port = self.port(source, alias="disponibilidad", dimension_key="dimensionless",
                         semantic_type_key="availability_factor", binding_role_key="rule_availability")
        updated = self.changed_job(path, job["compilation_scope"], {**body, "inputs": [port]})
        response = self.client.post(f"{path}/series-publications/{original['id']}/regenerations",
            json={"job_id": updated["id"], "expected_revision_id": original["revision_id"], "reason": "Intento de ciclo"},
            headers={**csrf_headers(self.client), "Idempotency-Key": self.token + "cycle"})
        self.assertEqual(response.status_code, 422, response.text)
        self.assertIn("ciclo", str(response.json()).lower())
        self.assertEqual(len(self.client.get(f"/api/time-series/catalog/inputs/{original['signal_id']}/revisions").json()["items"]), 1)

    def test_failure_after_writing_values_rolls_back_publication_and_allows_retry(self):
        path, job, _, _ = self.calculation()
        rule_id = path.rsplit("/", 1)[-1]
        # Fault at the database boundary, after the canonical writer has sealed values.
        trigger = "fail_reg007_" + self.token
        if self.store.database_backend == "sqlite":
            self.store.connection.execute(f"CREATE TRIGGER {trigger} BEFORE INSERT ON component_rule_series "
                f"WHEN NEW.rule_id = '{rule_id}' BEGIN SELECT RAISE(ABORT, 'injected storage failure'); END")
        else:
            self.store.connection.execute(f"CREATE FUNCTION {trigger}() RETURNS trigger LANGUAGE plpgsql AS $$ "
                "BEGIN RAISE EXCEPTION 'injected storage failure'; END $$")
            self.store.connection.execute(f"CREATE TRIGGER {trigger} BEFORE INSERT ON component_rule_series "
                f"FOR EACH ROW WHEN (NEW.rule_id = '{rule_id}') EXECUTE FUNCTION {trigger}()")
        try:
            with self.assertRaisesRegex(Exception, "injected storage failure"):
                self.publish(path, job)
            listed = self.client.get("/api/time-series/catalog/inputs", params={"q": "Potencia calculada " + self.token}).json()
            self.assertEqual(listed["items"], [])
            self.assertEqual(self.client.get(path + "/series-publications").json()["items"], [])
        finally:
            if self.store.database_backend == "sqlite":
                self.store.connection.execute(f"DROP TRIGGER {trigger}")
            else:
                self.store.connection.execute(f"DROP TRIGGER {trigger} ON component_rule_series")
                self.store.connection.execute(f"DROP FUNCTION {trigger}()")
        retried = self.publish(path, job)
        self.assertEqual(retried.status_code, 201, retried.text)
        self.assertEqual(retried.json()["revision_number"], 1)

    def test_publication_respects_project_switch_scope_and_external_user_boundary(self):
        from unittest.mock import patch
        from app.auth import hash_password
        from tests.auth_test_helpers import login_json_with_csrf
        path, job, _, _ = self.calculation()
        with patch.dict(os.environ, {"RULE_ENABLED_PROJECTS": ""}):
            self.assertEqual(self.publish(path, job).status_code, 503)
        other = self.store.create_project(name="Otro " + self.token)
        foreign = path.replace(f"projects/{self.project['id']}/", f"projects/{other['id']}/")
        self.assertEqual(self.publish(foreign, job).status_code, 404)
        self.assertEqual(self.client.get(foreign + "/series-publications").status_code, 404)
        outsider = self.store.create_user(email=f"external-{self.token}@rules.test", display_name="Externo",
            role="external", password_hash=hash_password("test password"))
        login_json_with_csrf(self.client, outsider["email"], "test password")
        self.assertEqual(self.publish(path, job).status_code, 404)
        self.assertEqual(self.client.get(path + "/series-publications").status_code, 404)

    def test_numeric_values_must_satisfy_the_declared_semantics(self):
        path, job, _, _ = self.calculation(CODE.replace("ctx.parametros.capacidad * ", "2 * "))
        response = self.publish(path, job, unit_key="dimensionless", semantic_type_key="availability_factor")
        self.assertEqual(response.status_code, 422, response.text)
        self.assertIn("semántica", str(response.json()).lower())
        self.assertEqual(self.client.get(path + "/series-publications").json()["items"], [])

    def test_publication_respects_the_canonical_emergency_pause(self):
        import tempfile
        from pathlib import Path
        if self.store.database_backend != "sqlite":
            self.skipTest("C6 migration fixture requires an exclusive database")
        saved = post_json_with_csrf(self.client, self.root, PAYLOAD)
        self.assertEqual(saved.status_code, 201, saved.text)
        path = self.root + "/" + saved.json()["id"]
        with tempfile.TemporaryDirectory() as recovery:
            self.store.take_c0_recovery_point(actor="admin", copy_directory=Path(recovery))
            self.store.backfill_time_series_c2(actor="admin")
            self.store.backfill_time_series_c3(actor="admin")
            self.store.backfill_time_series_c4(actor="admin")
            self.store.verify_time_series_c5_shadow(actor="admin")
            self.store.cut_over_time_series_c6(actor="admin")
        self.store.observe_time_series_c6_health(actor="monitor", observation={"open_blocking_anomalies": 1})
        response = self.publish(path, {"id": "no-preview-during-pause"})
        self.assertEqual(response.status_code, 409, response.text)
        self.assertIn("TS_CUTOVER_MUTATIONS_PAUSED", response.text)
        self.assertEqual(self.client.get(path + "/series-publications").json()["items"], [])

    def test_power_output_runs_in_a_compatible_case_and_regeneration_preserves_its_pin_and_run(self):
        from tests.reg007_fixture import renewable_consumer
        path, job, _, body = self.calculation()
        original = self.publish(path, job).json()
        consumer = renewable_consumer(self.store, self.project["id"], self.user["email"])
        scenario = consumer["scenario_id"]
        variant = self.client.get(f"/api/scenarios/{scenario}/case/default-variant").json()["variant"]["id"]
        root = f"/api/scenarios/{scenario}/case-variants/{variant}"
        operations = []
        for role, owner, signal, revision, content_hash in (
            ("renewable_available_power", consumer["solar_object_id"], original["signal_id"], original["revision_id"], original["content_hash"]),
            *[(role, consumer["system_object_id"], consumer["price"]["signal_ids"]["price"], consumer["price"]["revision_id"], consumer["price"]["content_hash"])
              for role in ("grid_import_price", "grid_export_price")]):
            operations.append({"client_operation_id": role, "action": "create", "linkable_object_id": owner, "binding_role_key": role,
                "signal_id": signal, "revision": {"mode": "current", "revision_id": revision, "content_hash": content_hash},
                "catalog_association_id": None, "reason_code": "variant_input_selected"})
        request = {"expected_bindings_revision": 0, "operations": operations}
        review = post_json_with_csrf(self.client, root + "/time-series-binding-prevalidations", request)
        self.assertEqual(review.status_code, 200, review.text)
        self.assertTrue(review.json()["can_commit"], review.text)
        committed = self.client.post(root + "/time-series-binding-batches", json={**request, "confirmed": True,
            "prevalidation_token": review.json()["prevalidation_token"]}, headers={**csrf_headers(self.client),
            "If-Match": review.json()["commit_etag"], "Idempotency-Key": self.token + "bind"})
        self.assertEqual(committed.status_code, 201, committed.text)
        run_path = f"/api/scenarios/{scenario}/case/variants/{variant}/run"
        run_body = {key: job["compilation_scope"][key] for key in ("range_start", "range_end")}
        run = post_json_with_csrf(self.client, run_path, run_body)
        self.assertEqual(run.status_code, 201, run.text)
        version_path = f"/api/scenario-versions/{run.json()['scenario_version_id']}"
        frozen = self.client.get(version_path).json()["scenario_version"]
        self.assertEqual([p["renewable_available_power_mw"]["reg007_solar"] for p in frozen["system_case_json"]["time_series"]], [20, 10, 15, 20])
        source = self.source((.5, .5, .5, .5), semantic="availability_factor", unit="dimensionless")
        updated = self.changed_job(path, job["compilation_scope"], {**body, "inputs": [{**body["inputs"][0],
            "revision_id": source["revision_id"], "content_hash": source["content_hash"]}]})
        regenerated = self.client.post(f"{path}/series-publications/{original['id']}/regenerations",
            json={"job_id": updated["id"], "expected_revision_id": original["revision_id"], "reason": "Nueva fuente"},
            headers={**csrf_headers(self.client), "Idempotency-Key": self.token + "refresh"})
        self.assertEqual(regenerated.status_code, 201, regenerated.text)
        self.assertEqual(self.points(regenerated.json()), [10, 10, 10, 10])
        bindings = self.client.get(root + "/time-series-bindings").json()["items"]
        power = next(b for b in bindings if b["signal_id"] == original["signal_id"])
        self.assertEqual((power["set_revision_id"], power["state"]), (original["revision_id"], "stale"))
        self.assertEqual(post_json_with_csrf(self.client, run_path, run_body).status_code, 409)
        self.assertEqual(self.client.get(version_path).json()["scenario_version"], frozen)


@unittest.skipUnless(os.environ.get("POSTGRES_TEST_DATABASE_URL"), "isolated PostgreSQL required")
class CalculatedSeriesPostgresTests(CalculatedSeriesApiTests):
    database_url = os.environ.get("POSTGRES_TEST_DATABASE_URL")
