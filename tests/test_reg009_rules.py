"""Revision recovery through the confirmed authenticated HTTP boundary."""
import os
import unittest
import time

from tests import test_reg008_rules as reusable
from tests.auth_test_helpers import post_json_with_csrf, put_json_with_csrf


class RuleRecoveryApiTests(unittest.TestCase):
    database_url = "sqlite:///:memory:"
    setUp = reusable.ReusableRuleApiTests.setUp
    tearDown = reusable.ReusableRuleApiTests.tearDown
    hydraulic_scope = reusable.ReusableRuleApiTests.hydraulic_scope
    related_fixture = reusable.ReusableRuleApiTests.related_fixture
    template = reusable.ReusableRuleApiTests.template
    instance_request = reusable.ReusableRuleApiTests.instance_request
    compile_instance = reusable.ReusableRuleApiTests.compile_instance
    source = reusable.ReusableRuleApiTests.source
    port = reusable.ReusableRuleApiTests.port

    def applied_instance(self, *, related=False, with_input=False):
        from app.rule_worker import RuleWorker
        from app.rule_runtime import OCIExecutor
        scope, objects, source_path, publication, _ = self.template()
        aliases = [{"alias": "otra", "object_id": objects["unit_2"]["id"]}] if related else []
        inputs = [self.port(self.source(), object_id=objects["unit_1"]["id"])] if with_input else []
        if with_input:
            publication = self.newer(source_path, inputs=inputs)
        if related:
            publication = self.newer(source_path, aliases=aliases, code=publication["code"].replace("ctx.objeto.caudal", "ctx.objetos.otra.caudal"))
        instance = post_json_with_csrf(self.client, self.root + "/instances", self.instance_request(scope, publication, aliases=aliases, inputs=inputs)).json()
        path = self.root + "/" + instance["id"]
        with RuleWorker(self.store, OCIExecutor.from_env()):
            job = self.compile_instance(path, scope, instance)
        applied = post_json_with_csrf(self.client, path + "/applications", {"job_id": job["id"], "reason": "Original"})
        self.assertEqual(applied.status_code, 201, applied.text)
        return scope, objects, source_path, publication, path, applied.json()

    def newer(self, path, **changes):
        draft = self.client.get(path).json()
        body = {k: draft[k] for k in ("name", "code", "parameters", "aliases", "inputs", "temporal", "windows", "scenario_id")}
        saved = put_json_with_csrf(self.client, path, {**body, **changes, "expected_revision": draft["revision"]})
        self.assertEqual(saved.status_code, 200, saved.text)
        published = post_json_with_csrf(self.client, path + "/publications", {"expected_revision": saved.json()["revision"]})
        self.assertEqual(published.status_code, 201, published.text)
        return published.json()

    def recovery_preview(self, path, scope, application, publication, **changes):
        body = {"expected_revision": self.client.get(path).json()["revision"],
                "source_application_id": application["id"], "expected_application_revision": application["revision"],
                "publication_id": publication["id"], "scope": scope, **changes}
        response = post_json_with_csrf(self.client, path + "/recovery-previews", body)
        self.assertEqual(response.status_code, 202, response.text)
        job = response.json()
        deadline = time.monotonic() + 40
        while job["status"] in {"queued", "running"} and time.monotonic() < deadline:
            time.sleep(0.05)
            job = self.client.get(path + "/tests/" + job["id"]).json()
        self.assertEqual(job["status"], "succeeded", job)
        return job

    @unittest.skipUnless(os.environ.get("RULE_RUNTIME_IMAGE"), "pinned OCI image required")
    def test_keep_old_pin_revalidates_and_atomically_preserves_previous_application(self):
        from app.rule_worker import RuleWorker
        from app.rule_runtime import OCIExecutor
        scope, _, source_path, publication, path, old = self.applied_instance()
        with RuleWorker(self.store, OCIExecutor.from_env()):
            self.newer(source_path, code=publication["code"].replace("<=", ">="))
            job = self.recovery_preview(path, scope, old, publication)
            self.assertEqual(self.client.get(path + "/applications").json()["items"][0]["id"], old["id"])
            resolved = post_json_with_csrf(self.client, path + "/resolutions", {
                "job_id": job["id"], "reason": "Conservar límite operativo", "request_id": "keep",
            })
            self.assertEqual(resolved.status_code, 201, resolved.text)
            current = resolved.json()
            self.assertEqual((current["publication_id"], current["validation_status"]), (publication["id"], "valid"))
            self.assertNotEqual(current["id"], old["id"])
            history = self.client.get(path + "/applications").json()["items"]
            previous = next(a for a in history if a["id"] == old["id"])
            self.assertEqual(previous["status"], "inactive")
            self.assertEqual(previous["code_hash"], old["code_hash"])
            self.assertEqual(current["events"][-1]["action"], "retain")
            self.assertEqual(current["events"][-1]["source_application_id"], old["id"])

    def test_context_distinguishes_drafts_publications_and_archived_definitions(self):
        scope, _, path, publication, _ = self.template()
        item = self.client.get(self.root).json()["items"][0]
        self.assertEqual(item["status"], "published")
        self.assertEqual(item["applications"], [])
        archived = post_json_with_csrf(self.client, path + "/archive", {
            "expected_revision": 1, "reason": "Plantilla retirada",
        })
        self.assertEqual(archived.status_code, 200, archived.text)
        self.assertEqual(self.client.get(path).json()["status"], "archived")
        self.assertEqual(self.client.get(path + "/publications/" + publication["id"]).json()["code"], publication["code"])
        rejected = post_json_with_csrf(self.client, self.root + "/instances", self.instance_request(scope, publication))
        self.assertEqual(rejected.status_code, 409, rejected.text)
        self.assertEqual(self.client.get(f"/api/projects/{self.project['id']}/rule-library").json()["items"], [])

    def test_history_provides_the_published_contract_for_explicit_remapping(self):
        _, objects, source_path, _, _ = self.template()
        new = self.newer(source_path, aliases=[{"alias": "otra", "object_id": objects["unit_2"]["id"]}])
        response = self.client.get(source_path + "/history")
        self.assertEqual(response.status_code, 200, response.text)
        publication = next(p for p in response.json()["publications"] if p["id"] == new["id"])
        self.assertEqual(publication["contract"]["aliases"], [{"alias": "otra", "kind": "hydraulic_unit"}])
        self.assertNotIn("object_id", publication["contract"]["aliases"][0])

    @unittest.skipUnless(os.environ.get("RULE_RUNTIME_IMAGE"), "pinned OCI image required")
    def test_adopt_revision_with_mappings_is_atomic_and_retries_are_idempotent(self):
        from app.rule_worker import RuleWorker
        from app.rule_runtime import OCIExecutor
        scope, _, source_path, publication, path, old = self.applied_instance()
        new = self.newer(source_path, code=publication["code"].replace("ctx.parametros.limite)", "ctx.parametros.limite / 2)"))
        mappings = {k: self.client.get(path).json()[k] for k in ("parameters", "aliases", "inputs", "temporal", "windows")}
        mappings["parameters"][0]["value"] = 12
        with RuleWorker(self.store, OCIExecutor.from_env()):
            job = self.recovery_preview(path, scope, old, new, mappings=mappings)
        self.assertEqual(self.client.get(path).json()["template"]["publication_id"], publication["id"])
        body = {"job_id": job["id"], "reason": "Adoptar nueva política", "request_id": "replace"}
        response = post_json_with_csrf(self.client, path + "/resolutions", body)
        self.assertEqual(response.status_code, 201, response.text)
        current = response.json()
        self.assertEqual([r["constant"] for r in current["ir"]["rows"]], [-6, -6, -6, -6])
        self.assertEqual(self.client.get(path).json()["template"]["publication_id"], new["id"])
        replay = post_json_with_csrf(self.client, path + "/resolutions", body)
        self.assertEqual(replay.status_code, 201, replay.text)
        self.assertEqual(replay.json(), current)
        changed = post_json_with_csrf(self.client, path + "/resolutions", {**body, "reason": "Otro motivo"})
        self.assertEqual(changed.status_code, 409, changed.text)
        self.assertEqual(len(self.client.get(path + "/applications").json()["items"]), 2)

    @unittest.skipUnless(os.environ.get("RULE_RUNTIME_IMAGE"), "pinned OCI image required")
    def test_archive_blocks_consumers_until_explicit_revalidation_and_conflicts_with_preview(self):
        from app.rule_worker import RuleWorker
        from app.rule_runtime import OCIExecutor
        scope, _, source_path, publication, path, old = self.applied_instance()
        with RuleWorker(self.store, OCIExecutor.from_env()):
            job = self.recovery_preview(path, scope, old, publication)
        archived = post_json_with_csrf(self.client, source_path + "/archive", {"expected_revision": 1, "reason": "Retirada"})
        self.assertEqual(archived.status_code, 200, archived.text)
        application = self.client.get(path + "/applications").json()["items"][0]
        self.assertEqual(application["validation_status"], "stale")
        self.assertIn("RULE_ARCHIVED", [c["code"] for c in application["validation_causes"]])
        run_path = f"/api/scenarios/{scope['scenario_id']}/case/variants/{scope['variant_id']}/run"
        self.assertEqual(post_json_with_csrf(self.client, run_path, {k: scope[k] for k in ("range_start", "range_end")}).status_code, 409)
        conflict = post_json_with_csrf(self.client, path + "/resolutions", {"job_id": job["id"], "reason": "Tarde", "request_id": "late"})
        self.assertEqual(conflict.status_code, 409, conflict.text)
        with RuleWorker(self.store, OCIExecutor.from_env()):
            job = self.recovery_preview(path, scope, old, publication)
        resolved = post_json_with_csrf(self.client, path + "/resolutions", {"job_id": job["id"], "reason": "Mantener consumidor existente", "request_id": "keep-archived"})
        self.assertEqual(resolved.status_code, 201, resolved.text)
        self.assertEqual(resolved.json()["validation_status"], "valid")
        allowed = post_json_with_csrf(self.client, run_path, {k: scope[k] for k in ("range_start", "range_end")})
        self.assertEqual(allowed.status_code, 201, allowed.text)

    @unittest.skipUnless(os.environ.get("RULE_RUNTIME_IMAGE"), "pinned OCI image required")
    def test_comparison_exposes_code_sdk_units_sources_horizon_objects_and_sealed_history(self):
        scope, objects, source_path, publication, path, old = self.applied_instance()
        new = self.newer(source_path, code=publication["code"].replace("<=", ">="))
        response = post_json_with_csrf(self.client, path + "/comparisons", {
            "source_application_id": old["id"], "expected_application_revision": 1, "expected_revision": 1,
            "publication_id": new["id"], "scope": {**scope, "range_end": "2026-01-01T03:00:00"},
        })
        self.assertEqual(response.status_code, 200, response.text)
        comparison = response.json()
        self.assertIn("code", comparison["changed_fields"])
        self.assertIn("scope", comparison["changed_fields"])
        self.assertEqual(comparison["before"]["code"], publication["code"])
        self.assertEqual(comparison["after"]["code"], new["code"])
        self.assertEqual(comparison["after"]["sdk"], new["sdk"])
        self.assertEqual(comparison["after"]["parameters"][0]["unit"], "m3_per_s")
        self.assertEqual(comparison["after"]["objects"][0]["id"], objects["unit_1"]["id"])
        self.assertEqual(comparison["after"]["inputs"], [])
        history = self.client.get(path + "/history")
        self.assertEqual(history.status_code, 200, history.text)
        self.assertEqual({p["id"] for p in history.json()["publications"]}, {publication["id"], new["id"]})
        self.assertEqual(history.json()["applications"][0]["code_hash"], old["code_hash"])

    @unittest.skipUnless(os.environ.get("RULE_RUNTIME_IMAGE"), "pinned OCI image required")
    def test_missing_object_is_invalid_and_cannot_be_accepted_with_a_reason(self):
        scope, _, source_path, publication, path, old = self.applied_instance(related=True)
        self.newer(source_path)
        diagram = self.store.get_hydraulic_diagram(scope["scenario_id"])
        plant = next(n for n in diagram["nodes"] if n["technical_key"] == "plant_laja")
        next(u for u in plant["units"] if u["technical_key"] == "unit_2")["is_active"] = False
        self.store.save_hydraulic_diagram(scenario_id=scope["scenario_id"], revision=diagram["revision"], nodes=diagram["nodes"], reaches=diagram["reaches"])
        current = self.client.get(path + "/applications").json()["items"][0]
        self.assertEqual(current["validation_status"], "invalid")
        self.assertIn("RULE_PUBLICATION_CHANGED", [c["code"] for c in current["validation_causes"]])
        self.assertTrue(any(c.get("alias") == "otra" for c in current["validation_causes"]))
        response = post_json_with_csrf(self.client, path + "/recovery-previews", {
            "source_application_id": old["id"], "expected_application_revision": 1, "expected_revision": 1,
            "publication_id": publication["id"], "scope": scope,
        })
        self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual(self.client.get(path + "/applications").json()["items"][0]["status"], "active")

    @unittest.skipUnless(os.environ.get("RULE_RUNTIME_IMAGE"), "pinned OCI image required")
    def test_restore_old_configuration_creates_new_history_and_preserves_run_snapshot(self):
        from app.rule_worker import RuleWorker
        from app.rule_runtime import OCIExecutor
        scope, _, source_path, publication, path, old = self.applied_instance()
        run_path = f"/api/scenarios/{scope['scenario_id']}/case/variants/{scope['variant_id']}/run"
        run = post_json_with_csrf(self.client, run_path, {k: scope[k] for k in ("range_start", "range_end")}).json()
        version_path = f"/api/scenario-versions/{run['scenario_version_id']}"
        original_version = self.client.get(version_path).json()
        new = self.newer(source_path, code=publication["code"].replace("ctx.parametros.limite)", "ctx.parametros.limite / 2)"))
        with RuleWorker(self.store, OCIExecutor.from_env()):
            job = self.recovery_preview(path, scope, old, new)
        replaced = post_json_with_csrf(self.client, path + "/resolutions", {"job_id": job["id"], "reason": "Actualizar", "request_id": "new"})
        self.assertEqual(replaced.status_code, 201, replaced.text)
        previous = next(a for a in self.client.get(path + "/applications").json()["items"] if a["id"] == old["id"])
        with RuleWorker(self.store, OCIExecutor.from_env()):
            job = self.recovery_preview(path, scope, previous, publication)
        restored = post_json_with_csrf(self.client, path + "/resolutions", {"job_id": job["id"], "reason": "Recuperar límite anterior", "request_id": "restore"})
        self.assertEqual(restored.status_code, 201, restored.text)
        self.assertEqual(restored.json()["events"][-1]["action"], "restore")
        self.assertEqual([r["constant"] for r in restored.json()["ir"]["rows"]], [-5, -5, -5, -5])
        history = self.client.get(path + "/history").json()["applications"]
        self.assertEqual(len(history), 3)
        self.assertEqual(sum(a["status"] == "active" for a in history), 1)
        self.assertEqual(self.client.get(version_path).json(), original_version)
        snapshot = original_version["scenario_version"]["system_case_json"]["component_rules"]["applications"][0]
        self.assertEqual((snapshot["publication_id"], snapshot["code_hash"], snapshot["ir_hash"]), (publication["id"], old["code_hash"], old["ir_hash"]))

    @unittest.skipUnless(os.environ.get("RULE_RUNTIME_IMAGE"), "pinned OCI image required")
    def test_editing_after_preview_rejects_confirmation_without_partial_changes(self):
        from app.rule_worker import RuleWorker
        from app.rule_runtime import OCIExecutor
        scope, _, source_path, publication, path, old = self.applied_instance()
        with RuleWorker(self.store, OCIExecutor.from_env()):
            job = self.recovery_preview(path, scope, old, publication)
        draft = self.client.get(path).json()
        body = {k: draft[k] for k in ("name", "code", "parameters", "aliases", "inputs", "temporal", "windows", "scenario_id")}
        body["parameters"][0]["value"] = 9
        self.assertEqual(put_json_with_csrf(self.client, path, {**body, "expected_revision": 1}).status_code, 200)
        for endpoint in ("resolutions", "applications"):
            confirm = {"job_id": job["id"], "reason": "No sobrescribir"}
            if endpoint == "resolutions":
                confirm["request_id"] = "conflict"
            response = post_json_with_csrf(self.client, path + "/" + endpoint, confirm)
            self.assertEqual(response.status_code, 409, response.text)
        self.assertEqual(self.client.get(path).json()["parameters"][0]["value"], 9)
        history = self.client.get(path + "/applications").json()["items"]
        self.assertEqual([(a["id"], a["status"]) for a in history], [(old["id"], "active")])

    @unittest.skipUnless(os.environ.get("RULE_RUNTIME_IMAGE"), "pinned OCI image required")
    def test_concurrent_confirmations_commit_only_one_replacement(self):
        from concurrent.futures import ThreadPoolExecutor
        from tests.auth_test_helpers import csrf_headers
        from app.rule_worker import RuleWorker
        from app.rule_runtime import OCIExecutor
        scope, _, _, publication, path, old = self.applied_instance()
        with RuleWorker(self.store, OCIExecutor.from_env()):
            job = self.recovery_preview(path, scope, old, publication)
        headers = csrf_headers(self.client)
        def confirm(key):
            return self.client.post(path + "/resolutions", headers=headers, json={"job_id": job["id"], "reason": "Confirmación concurrente", "request_id": key})
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(confirm, ["same", "same"]))
        self.assertEqual([r.status_code for r in responses], [201, 201])
        self.assertEqual(responses[0].json(), responses[1].json())
        self.assertEqual(confirm("another").status_code, 409)
        self.assertEqual(len(self.client.get(path + "/applications").json()["items"]), 2)

    @unittest.skipUnless(os.environ.get("RULE_RUNTIME_IMAGE"), "pinned OCI image required")
    def test_template_history_identifies_consumers_that_must_resolve_an_archive(self):
        scope, _, source_path, _, path, old = self.applied_instance()
        response = self.client.get(source_path + "/history")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["consumers"], [{
            "application_id": old["id"], "rule_id": path.rsplit("/", 1)[-1], "name": old["name"],
            "project_id": self.project["id"], "object_id": old["object_id"],
            "variant_id": scope["variant_id"], "scenario_id": scope["scenario_id"],
        }])

    @unittest.skipUnless(os.environ.get("RULE_RUNTIME_IMAGE"), "pinned OCI image required")
    def test_source_revision_race_blocks_confirmation_and_old_source_pin_can_be_revalidated(self):
        from app.rule_worker import RuleWorker
        from app.rule_runtime import OCIExecutor
        scope, _, _, publication, path, old = self.applied_instance(with_input=True)
        latest = self.source((4, 4, 4, 4))
        comparison = post_json_with_csrf(self.client, path + "/comparisons", {
            "source_application_id": old["id"], "expected_application_revision": 1, "expected_revision": 1,
            "publication_id": publication["id"], "scope": scope,
        }).json()
        self.assertIn("inputs", comparison["changed_fields"])
        self.assertEqual(comparison["after"]["inputs"][0]["unit_key"], "m3_per_s")
        self.assertEqual(comparison["after"]["inputs"][0]["current_revision_id"], latest["revision_id"])
        with RuleWorker(self.store, OCIExecutor.from_env()):
            job = self.recovery_preview(path, scope, old, publication)
        latest = self.source((6, 6, 6, 6))
        rejected = post_json_with_csrf(self.client, path + "/resolutions", {"job_id": job["id"], "reason": "Carrera", "request_id": "input-conflict"})
        self.assertEqual(rejected.status_code, 409, rejected.text)
        self.assertEqual(len(self.client.get(path + "/applications").json()["items"]), 1)
        with RuleWorker(self.store, OCIExecutor.from_env()):
            job = self.recovery_preview(path, scope, old, publication)
        resolved = post_json_with_csrf(self.client, path + "/resolutions", {"job_id": job["id"], "reason": "Conservar fuente comprobada", "request_id": "input-keep"})
        self.assertEqual(resolved.status_code, 201, resolved.text)
        self.assertEqual(resolved.json()["inputs"][0]["revision_id"], old["inputs"][0]["revision_id"])
        self.assertEqual(resolved.json()["inputs"][0]["current_revision_id"], latest["revision_id"])
        self.assertEqual(resolved.json()["validation_status"], "valid")

    def test_history_and_recovery_respect_project_and_role_boundaries(self):
        from app.auth import hash_password
        from tests.auth_test_helpers import login_json_with_csrf
        scope, _, path, publication, _ = self.template()
        foreign = self.store.create_project(name="Foreign " + self.token)
        self.assertEqual(self.client.get(path.replace(f"projects/{self.project['id']}/", f"projects/{foreign['id']}/") + "/history").status_code, 404)
        external = self.store.create_user(email=f"external-{self.token}@rules.test", display_name="Externo", role="external", password_hash=hash_password("test password"))
        login_json_with_csrf(self.client, external["email"], "test password")
        # The authentication middleware hides internal routes from external users.
        self.assertEqual(self.client.get(path + "/history").status_code, 404)
        preview = {"source_application_id": "missing", "expected_application_revision": 1, "expected_revision": 1,
                   "publication_id": publication["id"], "scope": scope}
        for endpoint, body in (("comparisons", preview), ("recovery-previews", preview),
                               ("archive", {"expected_revision": 1, "reason": "No permitido"}),
                               ("resolutions", {"job_id": "missing", "reason": "No permitido", "request_id": "foreign"})):
            with self.subTest(endpoint=endpoint):
                self.assertEqual(post_json_with_csrf(self.client, path + "/" + endpoint, body).status_code, 404)

    @unittest.skipUnless(os.environ.get("RULE_RUNTIME_IMAGE"), "pinned OCI image required")
    def test_archive_cannot_be_bypassed_by_cloning_a_new_consumer(self):
        scope, _, source_path, _, _, _ = self.applied_instance()
        self.assertEqual(post_json_with_csrf(self.client, source_path + "/archive", {"expected_revision": 1, "reason": "Retirada"}).status_code, 200)
        response = post_json_with_csrf(self.client, f"/api/scenarios/{scope['scenario_id']}/case/variants/{scope['variant_id']}/clone", {"display_name": "Consumidor nuevo"})
        self.assertEqual(response.status_code, 409, response.text)

    @unittest.skipUnless(os.environ.get("RULE_RUNTIME_IMAGE"), "pinned OCI image required")
    def test_runtime_image_change_invalidates_preview_before_confirmation(self):
        import uuid
        from app.rule_worker import RuleWorker
        from app.rule_runtime import OCIExecutor
        scope, _, _, publication, path, old = self.applied_instance()
        executor = OCIExecutor.from_env()
        with RuleWorker(self.store, executor):
            job = self.recovery_preview(path, scope, old, publication)
        # A real OCI image with identical code but a new immutable runtime identity.
        container = "reg009-runtime-" + uuid.uuid4().hex
        alternate = None
        executor.control("create", "--name", container, executor.image)
        try:
            alternate = executor.control("commit", "--change", "LABEL reg009_probe=true", container)
            with RuleWorker(self.store, OCIExecutor(executor.command, alternate)):
                application = self.client.get(path + "/applications").json()["items"][0]
                self.assertEqual(application["validation_status"], "stale")
                self.assertIn("RULE_RUNTIME_CHANGED", [c["code"] for c in application["validation_causes"]])
                response = post_json_with_csrf(self.client, path + "/resolutions", {"job_id": job["id"], "reason": "Prueba anterior", "request_id": "runtime-change"})
                self.assertEqual(response.status_code, 409, response.text)
                self.assertEqual(len(self.client.get(path + "/applications").json()["items"]), 1)
        finally:
            executor.control("rm", container)
            if alternate:
                executor.control("image", "rm", alternate)


@unittest.skipUnless(os.environ.get("POSTGRES_TEST_DATABASE_URL"), "isolated PostgreSQL required")
class PostgresRuleRecoveryApiTests(RuleRecoveryApiTests):
    database_url = os.environ.get("POSTGRES_TEST_DATABASE_URL", "sqlite:///:memory:")
