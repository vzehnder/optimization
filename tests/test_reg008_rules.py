"""Reusable rules through authenticated HTTP (confirmed TDD boundary)."""
import os
import unittest
import time

from tests import test_reg004_rules as related
from tests.test_reg001_rules import PAYLOAD
from tests.test_reg002_runtime import CODE, PARAMETERS
from tests.auth_test_helpers import post_json_with_csrf, put_json_with_csrf


class ReusableRuleApiTests(unittest.TestCase):
    database_url = "sqlite:///:memory:"
    setUp = related.RelatedRuleApiTests.setUp
    tearDown = related.RelatedRuleApiTests.tearDown
    hydraulic_scope = related.RelatedRuleApiTests.hydraulic_scope
    related_fixture = related.RelatedRuleApiTests.related_fixture
    preview = related.RelatedRuleApiTests.preview
    source = related.RelatedRuleApiTests.source
    port = related.RelatedRuleApiTests.port

    def template(self, **changes):
        scope, objects = self.related_fixture()
        payload = {**PAYLOAD, "code": CODE, "parameters": PARAMETERS,
                   "scenario_id": scope["scenario_id"], **changes}
        saved = post_json_with_csrf(self.client, self.root, payload)
        self.assertEqual(saved.status_code, 201, saved.text)
        path = self.root + "/" + saved.json()["id"]
        publication = post_json_with_csrf(self.client, path + "/publications", {"expected_revision": 1}).json()
        promoted = post_json_with_csrf(self.client, path + "/library", {"publication_id": publication["id"]})
        self.assertEqual(promoted.status_code, 201, promoted.text)
        return scope, objects, path, publication, promoted.json()

    def test_analyst_discovers_a_published_template_with_its_typed_contract(self):
        scope, objects, path, publication, template = self.template()
        response = self.client.get(f"/api/projects/{self.project['id']}/rule-library")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(len(response.json()["items"]), 1)
        item = response.json()["items"][0]
        self.assertEqual((item["name"], item["publication_id"], item["revision"]),
                         (PAYLOAD["name"], publication["id"], 1))
        self.assertEqual(item["compatible_types"], ["hydraulic_unit"])
        self.assertEqual(item["required_capabilities"], ["affine_flow.v1"])
        self.assertEqual(item["parameters"][0]["name"], "limite")
        self.assertNotIn("object_id", item["parameters"][0])
        self.assertEqual(self.client.get(path).json()["code"], CODE)

    def test_new_instance_keeps_the_shared_revision_and_edits_only_local_values(self):
        scope, objects, path, publication, template = self.template()
        root = self.root.replace(str(objects["unit_1"]["id"]) + "/rules", str(objects["unit_2"]["id"]) + "/rules")
        response = post_json_with_csrf(self.client, root + "/instances", {
            "publication_id": publication["id"], "scenario_id": scope["scenario_id"],
            "variant_id": scope["variant_id"], "name": "Límite unidad 2",
            "parameters": [{**PARAMETERS[0], "value": 12}], "aliases": [], "inputs": [],
            "request_id": "second-unit", "reason": "Capacidad propia",
        })
        self.assertEqual(response.status_code, 201, response.text)
        instance = response.json()
        self.assertEqual(instance["template"], {"rule_id": publication["rule_id"], "publication_id": publication["id"]})
        self.assertEqual((instance["code"], instance["parameters"][0]["value"], instance["object_id"]), (CODE, 12, objects["unit_2"]["id"]))
        instance_path = root + "/" + instance["id"]
        change = {k: instance[k] for k in ("name", "code", "parameters", "aliases", "inputs", "scenario_id", "temporal", "windows")}
        change["parameters"][0]["value"] = 7
        updated = put_json_with_csrf(self.client, instance_path, {**change, "expected_revision": 1})
        self.assertEqual(updated.status_code, 200, updated.text)
        self.assertEqual(self.client.get(instance_path).json()["parameters"][0]["value"], 7)
        self.assertEqual(self.client.get(path).json()["parameters"][0]["value"], 5)
        pinned = post_json_with_csrf(self.client, instance_path + "/publications", {"expected_revision": 2})
        self.assertEqual(pinned.status_code, 201, pinned.text)
        self.assertEqual(pinned.json()["id"], publication["id"])
        self.assertEqual(pinned.json()["parameters"][0]["value"], 7)

    def instance_request(self, scope, publication, **changes):
        return {"publication_id": publication["id"], "scenario_id": scope["scenario_id"],
                "variant_id": scope["variant_id"], "name": "Aplicación local", "parameters": PARAMETERS,
                "aliases": [], "inputs": [], "request_id": "instance", "reason": "Reutilizar", **changes}

    def test_required_contract_cannot_be_removed_or_changed_by_an_instance(self):
        scope, objects, path, publication, template = self.template()
        # Seal a revision with an alias and input bound to that alias.
        source = self.source()
        alias = {"alias": "otra", "object_id": objects["unit_2"]["id"]}
        port = self.port(source, object_id=alias["object_id"])
        definition = {**PAYLOAD, "code": CODE, "parameters": PARAMETERS, "aliases": [alias], "inputs": [port],
                      "scenario_id": scope["scenario_id"], "expected_revision": 1}
        self.assertEqual(put_json_with_csrf(self.client, path, definition).status_code, 200)
        publication = post_json_with_csrf(self.client, path + "/publications", {"expected_revision": 2}).json()
        self.assertEqual(post_json_with_csrf(self.client, path + "/library", {"publication_id": publication["id"]}).status_code, 201)
        body = self.instance_request(scope, publication, aliases=[alias], inputs=[port])
        for change in ({"aliases": []}, {"inputs": []}, {"parameters": []},
                       {"parameters": [{**PARAMETERS[0], "unit": "mw"}]},
                       {"aliases": [{"alias": "otra", "object_id": objects["plant_laja"]["id"]}]},
                       {"inputs": [{**port, "object_id": objects["unit_1"]["id"]}]}):
            with self.subTest(change=change):
                rejected = post_json_with_csrf(self.client, self.root + "/instances", {**body, **change})
                self.assertEqual(rejected.status_code, 422, rejected.text)
        created = post_json_with_csrf(self.client, self.root + "/instances", body)
        self.assertEqual(created.status_code, 201, created.text)
        instance = created.json()
        update = {k: instance[k] for k in ("name", "code", "parameters", "inputs", "aliases", "scenario_id")}
        rejected = put_json_with_csrf(self.client, self.root + "/" + instance["id"],
                                      {**update, "code": "def construir(ctx):\n    pass", "expected_revision": 1})
        self.assertEqual(rejected.status_code, 422, rejected.text)

    def compile_instance(self, path, scope, instance):
        publication = post_json_with_csrf(self.client, path + "/publications", {"expected_revision": instance["revision"]}).json()
        started = post_json_with_csrf(self.client, path + "/tests", {"expected_revision": instance["revision"], "publication_id": publication["id"], "scope": scope})
        self.assertEqual(started.status_code, 202, started.text)
        job = started.json()
        deadline = time.monotonic() + 30
        while job["status"] in {"queued", "running"} and time.monotonic() < deadline:
            time.sleep(0.05)
            job = self.client.get(path + "/tests/" + job["id"]).json()
        self.assertEqual(job["status"], "succeeded", job)
        return job

    @unittest.skipUnless(os.environ.get("RULE_RUNTIME_IMAGE"), "pinned OCI image required")
    def test_two_instances_compile_independently_and_new_publication_marks_both_stale_without_moving_pins(self):
        from app.rule_worker import RuleWorker
        from app.rule_runtime import OCIExecutor
        scope, objects, source_path, publication, template = self.template()
        paths, apps = [], []
        with RuleWorker(self.store, OCIExecutor.from_env()):
            for key, value in (("unit_1", 5), ("unit_2", 12)):
                root = f"/api/projects/{self.project['id']}/linkable-objects/{objects[key]['id']}/rules"
                instance = post_json_with_csrf(self.client, root + "/instances", self.instance_request(scope, publication,
                    request_id=key, parameters=[{**PARAMETERS[0], "value": value}])).json()
                path = root + "/" + instance["id"]
                paths.append(path)
                job = self.compile_instance(path, scope, instance)
                self.assertEqual([r["constant"] for r in job["result"]["ir"]["rows"]], [-value] * 4)
                applied = post_json_with_csrf(self.client, path + "/applications", {"job_id": job["id"], "reason": key})
                self.assertEqual(applied.status_code, 201, applied.text)
                apps.append(applied.json())
            run_path = f"/api/scenarios/{scope['scenario_id']}/case/variants/{scope['variant_id']}/run"
            run = post_json_with_csrf(self.client, run_path, {k: scope[k] for k in ("range_start", "range_end")})
            self.assertEqual(run.status_code, 201, run.text)
            version_path = f"/api/scenario-versions/{run.json()['scenario_version_id']}"
            version = self.client.get(version_path).json()["scenario_version"]
            rows = version["system_case_json"]["component_rules"]["rows"]
            self.assertEqual(len({(r["application_id"], r["name"], r["period"]) for r in rows}), 8)
            self.assertEqual({a["publication_id"] for a in apps}, {publication["id"]})
        update = {**PAYLOAD, "code": CODE.replace("<=", ">="), "parameters": PARAMETERS,
                  "scenario_id": scope["scenario_id"], "expected_revision": 1}
        self.assertEqual(put_json_with_csrf(self.client, source_path, update).status_code, 200)
        newer = post_json_with_csrf(self.client, source_path + "/publications", {"expected_revision": 2})
        self.assertEqual(newer.status_code, 201, newer.text)
        for path in paths:
            application = self.client.get(path + "/applications").json()["items"][0]
            self.assertEqual((application["validation_status"], application["publication_id"]), ("stale", publication["id"]))
            self.assertEqual(self.client.get(path).json()["code"], CODE)
        blocked = post_json_with_csrf(self.client, run_path, {k: scope[k] for k in ("range_start", "range_end")})
        self.assertEqual(blocked.status_code, 409, blocked.text)
        self.assertEqual(self.client.get(version_path).json()["scenario_version"], version)
        revisions = self.client.get(f"/api/projects/{self.project['id']}/rule-library").json()["items"]
        self.assertEqual({r["publication_id"] for r in revisions}, {publication["id"], newer.json()["id"]})

    @unittest.skipUnless(os.environ.get("RULE_RUNTIME_IMAGE"), "pinned OCI image required")
    def test_local_edit_cannot_apply_a_preview_compiled_with_old_parameters_or_another_variant(self):
        from app.rule_worker import RuleWorker
        from app.rule_runtime import OCIExecutor
        scope, _, _, publication, _ = self.template()
        instance = post_json_with_csrf(self.client, self.root + "/instances", self.instance_request(scope, publication)).json()
        path = self.root + "/" + instance["id"]
        with RuleWorker(self.store, OCIExecutor.from_env()):
            job = self.compile_instance(path, scope, instance)
            update = {k: instance[k] for k in ("name", "code", "parameters", "inputs", "aliases", "scenario_id")}
            update["parameters"][0]["value"] = 9
            saved = put_json_with_csrf(self.client, path, {**update, "expected_revision": 1})
            self.assertEqual(saved.status_code, 200, saved.text)
            obsolete = post_json_with_csrf(self.client, path + "/applications", {"job_id": job["id"], "reason": "No mezclar"})
            self.assertEqual(obsolete.status_code, 409, obsolete.text)
            other = post_json_with_csrf(self.client, f"/api/scenarios/{scope['scenario_id']}/case/variants", {"display_name": "Otra"}).json()
            wrong = post_json_with_csrf(self.client, path + "/tests", {"expected_revision": 2,
                "publication_id": publication["id"], "scope": {**scope, "variant_id": other["id"]}})
            self.assertEqual(wrong.status_code, 422, wrong.text)

    @unittest.skipUnless(os.environ.get("RULE_RUNTIME_IMAGE"), "pinned OCI image required")
    def test_clone_preserves_rule_pins_and_origin_but_requires_recompilation(self):
        from app.rule_worker import RuleWorker
        from app.rule_runtime import OCIExecutor
        scope, objects, _, publication, _ = self.template()
        instance = post_json_with_csrf(self.client, self.root + "/instances", self.instance_request(scope, publication)).json()
        path = self.root + "/" + instance["id"]
        with RuleWorker(self.store, OCIExecutor.from_env()):
            job = self.compile_instance(path, scope, instance)
        application = post_json_with_csrf(self.client, path + "/applications", {"job_id": job["id"], "reason": "Original"}).json()
        response = post_json_with_csrf(self.client, f"/api/scenarios/{scope['scenario_id']}/case/variants/{scope['variant_id']}/clone", {"display_name": "Copia"})
        self.assertEqual(response.status_code, 201, response.text)
        clone = response.json()
        drafts = self.client.get(self.root).json()["items"]
        copied = [self.client.get(self.root + "/" + d["id"]).json() for d in drafts if d["id"] != instance["id"]]
        copied = next((d for d in copied if d.get("variant_id") == clone["id"]), None)
        self.assertIsNotNone(copied, "Clonar debe conservar las instancias, no omitir las reglas")
        self.assertEqual(copied["template"]["publication_id"], publication["id"])
        self.assertEqual(copied["origin"]["source_variant_id"], scope["variant_id"])
        cloned_apps = self.client.get(self.root + "/" + copied["id"] + "/applications").json()["items"]
        self.assertEqual(len(cloned_apps), 1)
        self.assertEqual((cloned_apps[0]["publication_id"], cloned_apps[0]["validation_status"]), (publication["id"], "stale"))
        blocked = post_json_with_csrf(self.client, f"/api/scenarios/{scope['scenario_id']}/case/variants/{clone['id']}/run", {k: scope[k] for k in ("range_start", "range_end")})
        self.assertEqual(blocked.status_code, 409, blocked.text)
        original = self.client.get(path + "/applications").json()["items"][0]
        self.assertEqual((original["id"], original["validation_status"]), (application["id"], "valid"))

    @unittest.skipUnless(os.environ.get("RULE_RUNTIME_IMAGE"), "pinned OCI image required")
    def test_comparison_shows_local_values_and_only_current_compiled_rows(self):
        from app.rule_worker import RuleWorker
        from app.rule_runtime import OCIExecutor
        scope, objects, _, publication, _ = self.template()
        instances = []
        for key, value in (("unit_1", 5), ("unit_2", 12)):
            root = f"/api/projects/{self.project['id']}/linkable-objects/{objects[key]['id']}/rules"
            instance = post_json_with_csrf(self.client, root + "/instances", self.instance_request(scope, publication,
                request_id=key, parameters=[{**PARAMETERS[0], "value": value}])).json()
            instances.append((root + "/" + instance["id"], instance))
        with RuleWorker(self.store, OCIExecutor.from_env()):
            self.compile_instance(instances[0][0], scope, instances[0][1])
        comparison_path = f"/api/projects/{self.project['id']}/rule-library/{publication['id']}/instances"
        comparison = self.client.get(comparison_path)
        self.assertEqual(comparison.status_code, 200, comparison.text)
        by_id = {i["id"]: i for i in comparison.json()["items"]}
        first, second = (by_id[i["id"]] for _, i in instances)
        self.assertEqual((first["parameters"][0]["value"], second["parameters"][0]["value"]), (5, 12))
        self.assertEqual([r["constant"] for r in first["preview"]["rows"]], [-5] * 4)
        self.assertIsNone(second["preview"])
        original = instances[0][1]
        update = {k: original[k] for k in ("name", "code", "parameters", "aliases", "inputs", "scenario_id")}
        update["parameters"][0]["value"] = 9
        self.assertEqual(put_json_with_csrf(self.client, instances[0][0], {**update, "expected_revision": 1}).status_code, 200)
        refreshed = self.client.get(comparison_path).json()["items"]
        self.assertIsNone(next(i for i in refreshed if i["id"] == original["id"])["preview"])

    @unittest.skipUnless(os.environ.get("RULE_RUNTIME_IMAGE"), "pinned OCI image required")
    def test_clone_of_a_missing_object_requires_an_explicit_compatible_remap(self):
        from app.rule_worker import RuleWorker
        from app.rule_runtime import OCIExecutor
        scope, objects, _, publication, _ = self.template()
        instance = post_json_with_csrf(self.client, self.root + "/instances", self.instance_request(scope, publication)).json()
        path = self.root + "/" + instance["id"]
        with RuleWorker(self.store, OCIExecutor.from_env()):
            job = self.compile_instance(path, scope, instance)
        self.assertEqual(post_json_with_csrf(self.client, path + "/applications", {"job_id": job["id"], "reason": "Original"}).status_code, 201)
        diagram = self.store.get_hydraulic_diagram(scope["scenario_id"])
        plant = next(n for n in diagram["nodes"] if n["technical_key"] == "plant_laja")
        next(u for u in plant["units"] if u["technical_key"] == "unit_1")["is_active"] = False
        self.store.save_hydraulic_diagram(scenario_id=scope["scenario_id"], revision=diagram["revision"], nodes=diagram["nodes"], reaches=diagram["reaches"])
        base = f"/api/scenarios/{scope['scenario_id']}/case/variants"
        before = self.client.get(base).json()
        rejected = post_json_with_csrf(self.client, base + f"/{scope['variant_id']}/clone", {"display_name": "Sin destino"})
        self.assertEqual(rejected.status_code, 422, rejected.text)
        detail = rejected.json()["detail"]
        self.assertEqual(detail["code"], "RULE_REMAP_REQUIRED")
        self.assertEqual(detail["objects"][0]["object_id"], objects["unit_1"]["id"])
        self.assertEqual([o["id"] for o in detail["objects"][0]["candidates"]], [objects["unit_2"]["id"]])
        self.assertEqual(self.client.get(base).json(), before, "No dejar una variante parcial")
        remapped = post_json_with_csrf(self.client, base + f"/{scope['variant_id']}/clone", {"display_name": "Remapeada",
            "rule_object_map": {str(objects["unit_1"]["id"]): objects["unit_2"]["id"]}})
        self.assertEqual(remapped.status_code, 201, remapped.text)
        target_root = f"/api/projects/{self.project['id']}/linkable-objects/{objects['unit_2']['id']}/rules"
        copied = self.client.get(target_root).json()["items"]
        self.assertEqual(len(copied), 1)
        draft = self.client.get(target_root + "/" + copied[0]["id"]).json()
        self.assertEqual(draft["template"]["publication_id"], publication["id"])
        self.assertEqual(draft["object_id"], objects["unit_2"]["id"])

    def test_temporal_and_window_contracts_are_required_when_reusing_their_capabilities(self):
        scope, _, _, publication, _ = self.template(temporal={"first_period": "omit", "initial_values": []},
            windows={"kind": "horizon", "timezone": "UTC", "partial": "allow"})
        body = self.instance_request(scope, publication)
        missing = post_json_with_csrf(self.client, self.root + "/instances", body)
        self.assertEqual(missing.status_code, 422, missing.text)
        complete = post_json_with_csrf(self.client, self.root + "/instances", {**body,
            "temporal": {"first_period": "omit", "initial_values": []},
            "windows": {"kind": "horizon", "timezone": "UTC", "partial": "allow"}})
        self.assertEqual(complete.status_code, 201, complete.text)

    def test_library_and_instances_enforce_project_type_and_external_access_boundaries(self):
        from app.auth import hash_password
        from tests.auth_test_helpers import login_json_with_csrf
        scope, objects, _, publication, _ = self.template()
        body = self.instance_request(scope, publication)
        missing = post_json_with_csrf(self.client, self.root + "/instances", {**body, "variant_id": 999999999})
        self.assertEqual(missing.status_code, 404, missing.text)
        plant_root = f"/api/projects/{self.project['id']}/linkable-objects/{objects['plant_laja']['id']}/rules"
        self.assertEqual(post_json_with_csrf(self.client, plant_root + "/instances", body).status_code, 422)
        foreign = self.store.create_project(name="Ajeno " + self.token)
        foreign_library = f"/api/projects/{foreign['id']}/rule-library"
        self.assertEqual(self.client.get(foreign_library).json()["items"], [])
        self.assertEqual(self.client.get(foreign_library + f"/{publication['id']}/instances").status_code, 404)
        foreign_root = self.root.replace(f"projects/{self.project['id']}/", f"projects/{foreign['id']}/")
        self.assertEqual(post_json_with_csrf(self.client, foreign_root + "/instances", body).status_code, 404)
        external = self.store.create_user(email=f"external-{self.token}@rules.test", display_name="Externo", role="external", password_hash=hash_password("test password"))
        login_json_with_csrf(self.client, external["email"], "test password")
        library = f"/api/projects/{self.project['id']}/rule-library"
        for route in (library, library + f"/{publication['id']}/instances"):
            self.assertEqual(self.client.get(route).status_code, 404)
        self.assertEqual(post_json_with_csrf(self.client, self.root + "/instances", body).status_code, 404)

    def test_cloning_also_keeps_instances_that_have_not_been_activated(self):
        scope, _, _, publication, _ = self.template()
        instance = post_json_with_csrf(self.client, self.root + "/instances", self.instance_request(scope, publication)).json()
        clone = post_json_with_csrf(self.client, f"/api/scenarios/{scope['scenario_id']}/case/variants/{scope['variant_id']}/clone", {"display_name": "Pendiente"})
        self.assertEqual(clone.status_code, 201, clone.text)
        drafts = [self.client.get(self.root + "/" + d["id"]).json() for d in self.client.get(self.root).json()["items"]]
        copies = [d for d in drafts if d.get("variant_id") == clone.json()["id"]]
        self.assertEqual(len(copies), 1)
        self.assertEqual((copies[0]["template"], copies[0]["parameters"]), (instance["template"], instance["parameters"]))
        self.assertEqual(self.client.get(self.root + "/" + copies[0]["id"] + "/applications").json()["items"], [])

    @unittest.skipUnless(os.environ.get("RULE_RUNTIME_IMAGE"), "pinned OCI image required")
    def test_concurrent_retries_create_one_instance_and_only_one_active_application(self):
        from concurrent.futures import ThreadPoolExecutor
        from tests.auth_test_helpers import csrf_headers
        from app.rule_worker import RuleWorker
        from app.rule_runtime import OCIExecutor
        scope, _, _, publication, _ = self.template()
        body = self.instance_request(scope, publication)
        headers = csrf_headers(self.client)
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(lambda _: self.client.post(self.root + "/instances", json=body, headers=headers), range(2)))
        self.assertEqual([r.status_code for r in responses], [201, 201])
        self.assertEqual(responses[0].json()["id"], responses[1].json()["id"])
        conflict = self.client.post(self.root + "/instances", json={**body, "name": "Otra intención"}, headers=headers)
        self.assertEqual(conflict.status_code, 409, conflict.text)
        instance = responses[0].json()
        path = self.root + "/" + instance["id"]
        with RuleWorker(self.store, OCIExecutor.from_env()):
            job = self.compile_instance(path, scope, instance)
        with ThreadPoolExecutor(max_workers=2) as pool:
            applications = list(pool.map(lambda _: self.client.post(path + "/applications", json={"job_id": job["id"], "reason": "Aplicación concurrente"}, headers=headers), range(2)))
        self.assertEqual(sorted(r.status_code for r in applications), [201, 409])
        self.assertEqual(len(self.client.get(path + "/applications").json()["items"]), 1)


@unittest.skipUnless(os.environ.get("POSTGRES_TEST_DATABASE_URL"), "isolated PostgreSQL required")
class ReusableRulePostgresTests(ReusableRuleApiTests):
    database_url = os.environ.get("POSTGRES_TEST_DATABASE_URL")
