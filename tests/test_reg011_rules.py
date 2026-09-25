"""REG-011 through authenticated HTTP, canonical storage and the real OCI worker."""
import json
import copy
import os
import unittest
from pathlib import Path

from app.draft_editor import structured_draft_document_from_system_case
from tests import test_reg003_rules as hourly
from tests.auth_test_helpers import post_json_with_csrf
from tests.test_reg001_rules import PAYLOAD
from tests import test_reg004_rules as related


class SimpleHydroRuleTests(unittest.TestCase):
    database_url = "sqlite:///:memory:"
    setUp = hourly.HourlyRuleApiTests.setUp
    tearDown = hourly.HourlyRuleApiTests.tearDown
    preview = hourly.HourlyRuleApiTests.preview
    source = hourly.HourlyRuleApiTests.source
    port = hourly.HourlyRuleApiTests.port
    compile_published = hourly.baseline.RuleApplicationApiTests.compile_published
    hydraulic_scope = hourly.HourlyRuleApiTests.hydraulic_scope
    related_fixture = related.RelatedRuleApiTests.related_fixture

    def hydro_scope(self):
        document = json.loads(Path("data/cases/linear_hydro_system/system_case.json").read_text())
        scenario = self.store.create_scenario(project_id=self.project["id"], name="Hidro simple")
        draft = structured_draft_document_from_system_case(document)
        draft["time_series"] = {"periods": document["time_series"]}
        self.store.create_or_replace_scenario_draft(scenario_id=scenario["id"],
            document=draft)
        self.store.materialize_project_linkable_objects(project_id=self.project["id"])
        self.obj = next(o for o in self.store.list_linkable_objects(project_id=self.project["id"])
                        if o["object_type_key"] == "component:hydro")
        self.root = f"/api/projects/{self.project['id']}/linkable-objects/{self.obj['id']}/rules"
        variant = self.client.get(f"/api/scenarios/{scenario['id']}/case/default-variant").json()["variant"]
        return {"scenario_id": scenario["id"], "variant_id": variant["id"],
                "range_start": "2026-01-01T00:00:00", "range_end": "2026-01-01T02:00:00"}

    def test_context_exposes_only_real_v2_variables_and_exact_horizon(self):
        scope = self.hydro_scope()
        context = self.client.get(f"/api/scenarios/{scope['scenario_id']}/components/hydro_1/rule-context")
        self.assertEqual(context.status_code, 200, context.text)
        self.assertEqual(context.json()["object_id"], self.obj["id"])
        response = self.client.get(self.root + "/object-candidates", params={"scenario_id": scope["scenario_id"]})
        self.assertEqual(response.status_code, 200, response.text)
        objects = [o for o in response.json()["items"] if o["kind"] == "hydro"]
        self.assertEqual(len(objects), 1)
        self.assertEqual(objects[0]["kind"], "hydro")
        self.assertEqual(objects[0]["schema_version"], "bess_system_dispatch.v2")
        self.assertEqual(objects[0]["variables"], {"caudal": "m3_per_s", "vertimiento": "m3_per_s",
                                                "potencia": "mw", "almacenamiento": "hm3"})
        selected = self.client.get(self.root + "/scope", params={"scenario_id": scope["scenario_id"]})
        self.assertEqual(selected.status_code, 200, selected.text)
        self.assertEqual(selected.json()["range_end"], scope["range_end"])

    def test_context_registers_a_new_saved_hydro_but_rejects_unsupported_component_types(self):
        scope = self.hydro_scope()
        draft = self.store.get_scenario_draft(scope["scenario_id"])["document"]
        hydro = next(a for a in draft["assets"] if a["type"] == "hydro")
        hydro["id"] = "new_hydro"
        for p in draft["time_series"]["periods"]:
            p["hydro_inflow_m3s"]["new_hydro"] = p["hydro_inflow_m3s"].pop("hydro_1")
        self.store.update_scenario_draft(scenario_id=scope["scenario_id"], document=draft)
        path = f"/api/scenarios/{scope['scenario_id']}/components"
        response = self.client.get(path + "/new_hydro/rule-context")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertNotEqual(response.json()["object_id"], self.obj["id"])
        self.assertEqual(self.client.get(path + "/hydro_1/rule-context").status_code, 404)
        self.assertEqual(self.client.get(path + "/solar_1/rule-context").status_code, 200)
        self.assertEqual(self.client.get(path + "/bus_1/rule-context").status_code, 404)

    def test_v2_code_and_context_keep_project_and_internal_role_boundaries(self):
        scope = self.hydro_scope()
        hourly.baseline.baseline.RuleApiTests.test_external_users_and_foreign_object_routes_cannot_access_code_or_jobs(self)
        response = self.client.get(f"/api/scenarios/{scope['scenario_id']}/components/hydro_1/rule-context")
        self.assertEqual(response.status_code, 404, response.text)

    @unittest.skipUnless(os.environ.get("RULE_RUNTIME_IMAGE"), "pinned OCI image required")
    def test_v3_context_keeps_its_own_snapshot_when_the_scenario_also_has_a_simple_editor(self):
        from app.rule_worker import RuleWorker
        from app.rule_runtime import OCIExecutor
        scope = self.hydraulic_scope()
        document = json.loads(Path("data/cases/linear_hydro_system/system_case.json").read_text())
        draft = structured_draft_document_from_system_case(document)
        draft["time_series"] = {"periods": document["time_series"]}
        self.store.create_or_replace_scenario_draft(scenario_id=scope["scenario_id"], document=draft)
        self.store.materialize_project_linkable_objects(project_id=self.project["id"])
        objects = self.client.get(self.root + "/object-candidates", params={"scenario_id": scope["scenario_id"]})
        self.assertEqual(objects.status_code, 200, objects.text)
        self.assertNotIn("hydro", {o["kind"] for o in objects.json()["items"]})
        with RuleWorker(self.store, OCIExecutor.from_env()):
            path, _, job = self.compile_published(scope)
        self.assertEqual(len(job["result"]["ir"]["rows"]), 4)
        applied = post_json_with_csrf(self.client, path + "/applications", {"job_id": job["id"], "reason": "Conservar hidráulica v3"})
        self.assertEqual(applied.status_code, 201, applied.text)
        self.assertEqual(applied.json()["compilation"]["system_case"]["schema_version"], "bess_system_dispatch.v3")

    @unittest.skipUnless(os.environ.get("RULE_RUNTIME_IMAGE"), "pinned OCI image required")
    def test_hourly_rule_compiles_all_variables_and_pins_v2_adapter(self):
        from app.rule_worker import RuleWorker
        from app.rule_runtime import OCIExecutor
        scope = self.hydro_scope()
        source = self.source((4, 6))
        code = ('def construir(ctx):\n    for t in ctx.periodos:\n'
                '        ctx.restriccion("caudal", t, ctx.objeto.caudal[t] <= ctx.entradas.afluente[t])\n'
                '        ctx.restriccion("potencia", t, ctx.objeto.potencia[t] >= ctx.parametros.potencia)\n'
                '        ctx.restriccion("volumen", t, ctx.objeto.almacenamiento[t] >= ctx.parametros.volumen)\n'
                '        ctx.restriccion("vertimiento", t, ctx.objeto.vertimiento[t] <= ctx.entradas.afluente[t])\n')
        response = post_json_with_csrf(self.client, self.root, {**PAYLOAD, "code": code,
            "scenario_id": scope["scenario_id"], "inputs": [self.port(source)],
            "parameters": [{"name": "potencia", "type": "number", "unit": "mw", "value": 0.1},
                           {"name": "volumen", "type": "number", "unit": "hm3", "value": 2.5}]})
        self.assertEqual(response.status_code, 201, response.text)
        path = self.root + "/" + response.json()["id"]
        publication = post_json_with_csrf(self.client, path + "/publications", {"expected_revision": 1}).json()
        with RuleWorker(self.store, OCIExecutor.from_env()):
            job = self.preview(scope, path, publication)
        self.assertEqual(job["status"], "succeeded", job)
        self.assertEqual(len(job["result"]["ir"]["rows"]), 8)
        applied = post_json_with_csrf(self.client, path + "/applications", {"job_id": job["id"], "reason": "Hidro horario"})
        self.assertEqual(applied.status_code, 201, applied.text)
        pin = applied.json()
        self.assertEqual(pin["adapter"], "hydro_v2.v1")
        self.assertEqual(pin["required_capabilities"], ["affine_hydraulic.v1"])
        self.assertEqual(pin["objects"][0]["schema_version"], "bess_system_dispatch.v2")
        self.assertEqual(pin["validation_status"], "valid")

    @unittest.skipUnless(os.environ.get("RULE_RUNTIME_IMAGE"), "pinned OCI image required")
    def test_materialized_run_negotiates_adapter_and_keeps_the_frozen_pin(self):
        from app.rule_worker import RuleWorker
        from app.rule_runtime import OCIExecutor
        scope = self.hydro_scope()
        with RuleWorker(self.store, OCIExecutor.from_env()):
            path, publication, job = self.compile_published(scope)
        applied = post_json_with_csrf(self.client, path + "/applications", {"job_id": job["id"], "reason": "Máximo 5"})
        self.assertEqual(applied.status_code, 201, applied.text)
        target = f"/api/scenarios/{scope['scenario_id']}/case/variants/{scope['variant_id']}/run"
        body = {k: scope[k] for k in ("range_start", "range_end")}
        old_engine = post_json_with_csrf(self.client, target, body)
        self.assertEqual(old_engine.status_code, 409, old_engine.text)
        self.assertIn("adaptador", old_engine.text)
        self.engine.adapters = ["hydro_v2.v1"]
        response = post_json_with_csrf(self.client, target, body)
        self.assertEqual(response.status_code, 201, response.text)
        version = self.client.get(f"/api/scenario-versions/{response.json()['scenario_version_id']}").json()["scenario_version"]
        block = version["system_case_json"]["component_rules"]
        self.assertEqual(block["adapter"], "hydro_v2.v1")
        self.assertEqual(block["objects"][0]["component_key"], "hydro_1")
        self.assertEqual(block["applications"][0]["adapter"], "hydro_v2.v1")
        self.assertEqual(block["applications"][0]["publication_id"], publication["id"])

    def test_v3_flow_template_can_be_explicitly_applied_to_a_v2_object(self):
        from tests.test_reg002_runtime import CODE, PARAMETERS
        original = self.hydraulic_scope()
        source_id = int(self.root.split("/")[-2])
        saved = post_json_with_csrf(self.client, self.root, {**PAYLOAD, "code": CODE,
            "parameters": PARAMETERS, "scenario_id": original["scenario_id"]}).json()
        path = self.root + "/" + saved["id"]
        publication = post_json_with_csrf(self.client, path + "/publications", {"expected_revision": 1}).json()
        promoted = post_json_with_csrf(self.client, path + "/library", {"publication_id": publication["id"]})
        self.assertEqual(promoted.status_code, 201, promoted.text)
        self.assertIn("hydro", promoted.json()["compatible_types"])
        scope = self.hydro_scope()
        response = post_json_with_csrf(self.client, self.root + "/instances", {
            "publication_id": publication["id"], "scenario_id": scope["scenario_id"], "variant_id": scope["variant_id"],
            "name": "Hidro remapeado", "parameters": PARAMETERS, "inputs": [], "aliases": [],
            "request_id": "explicit-hydro", "reason": "Reutilizar límite en hidro simple"})
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()["object_id"], self.obj["id"])
        self.assertNotEqual(response.json()["object_id"], source_id)
        self.assertEqual(response.json()["code"], CODE)
        self.assertEqual(response.json()["template"]["publication_id"], publication["id"])

    def test_template_aliases_are_explicitly_remapped_to_compatible_v2_variables(self):
        from tests.test_reg002_runtime import PARAMETERS
        original, objects = self.related_fixture()
        code = ('def construir(ctx):\n    for t in ctx.periodos:\n'
                '        ctx.restriccion("conjunto", t, ctx.objeto.caudal[t] + ctx.objetos.otro.caudal[t] <= ctx.parametros.limite)\n')
        saved = post_json_with_csrf(self.client, self.root, {**PAYLOAD, "code": code, "parameters": PARAMETERS,
            "scenario_id": original["scenario_id"], "aliases": [{"alias": "otro", "object_id": objects["unit_2"]["id"]}]}).json()
        path = self.root + "/" + saved["id"]
        publication = post_json_with_csrf(self.client, path + "/publications", {"expected_revision": 1}).json()
        self.assertEqual(post_json_with_csrf(self.client, path + "/library", {"publication_id": publication["id"]}).status_code, 201)
        scope = self.hydro_scope()
        draft = self.store.get_scenario_draft(scope["scenario_id"])["document"]
        second = copy.deepcopy(next(a for a in draft["assets"] if a["type"] == "hydro"))
        second["id"] = "hydro_2"
        draft["assets"].append(second)
        for p in draft["time_series"]["periods"]:
            p["hydro_inflow_m3s"]["hydro_2"] = 0
        self.store.update_scenario_draft(scenario_id=scope["scenario_id"], document=draft)
        self.store.materialize_project_linkable_objects(project_id=self.project["id"])
        second_id = next(o["id"] for o in self.store.list_linkable_objects(project_id=self.project["id"]) if o["object_key"] == "hydro_2")
        body = {"publication_id": publication["id"], "scenario_id": scope["scenario_id"], "variant_id": scope["variant_id"],
                "name": "Caudal conjunto", "parameters": PARAMETERS, "inputs": [], "request_id": "alias-v2", "reason": "Elegir ambos hidros"}
        foreign = post_json_with_csrf(self.client, self.root + "/instances", {**body,
            "aliases": [{"alias": "otro", "object_id": objects["unit_2"]["id"]}]})
        self.assertEqual(foreign.status_code, 422, foreign.text)
        response = post_json_with_csrf(self.client, self.root + "/instances", {**body,
            "aliases": [{"alias": "otro", "object_id": second_id}]})
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()["aliases"], [{"alias": "otro", "object_id": second_id}])

    @unittest.skipUnless(os.environ.get("RULE_RUNTIME_IMAGE"), "pinned OCI image required")
    def test_height_is_rejected_during_preview_without_creating_an_application(self):
        from app.rule_worker import RuleWorker
        from app.rule_runtime import OCIExecutor
        scope = self.hydro_scope()
        saved = post_json_with_csrf(self.client, self.root, {**PAYLOAD, "scenario_id": scope["scenario_id"],
            "code": 'def construir(ctx):\n    ctx.restriccion("cota", 0, ctx.objeto.cota[0] >= ctx.parametros.capacidad)'}).json()
        path = self.root + "/" + saved["id"]
        publication = post_json_with_csrf(self.client, path + "/publications", {"expected_revision": 1}).json()
        with RuleWorker(self.store, OCIExecutor.from_env()):
            job = self.preview(scope, path, publication)
        self.assertEqual(job["status"], "failed", job)
        self.assertIn("cota", job["result"]["error"]["message"])
        self.assertEqual(job["result"]["error"]["line"], 2)
        self.assertEqual(self.client.get(path + "/applications").json()["items"], [])

    def test_storage_template_refuses_a_unit_without_storage_capability(self):
        scope = self.hydro_scope()
        parameters = [{"name": "volumen", "type": "number", "unit": "hm3", "value": 2.5}]
        saved = post_json_with_csrf(self.client, self.root, {**PAYLOAD, "scenario_id": scope["scenario_id"],
            "parameters": parameters, "code": 'def construir(ctx):\n    ctx.restriccion("volumen", 0, ctx.objeto.almacenamiento[0] >= ctx.parametros.volumen)'}).json()
        path = self.root + "/" + saved["id"]
        publication = post_json_with_csrf(self.client, path + "/publications", {"expected_revision": 1}).json()
        template = post_json_with_csrf(self.client, path + "/library", {"publication_id": publication["id"]}).json()
        self.assertEqual(template["compatible_types"], ["hydro"])
        target = self.hydraulic_scope()
        response = post_json_with_csrf(self.client, self.root + "/instances", {
            "publication_id": publication["id"], "scenario_id": target["scenario_id"], "variant_id": target["variant_id"],
            "name": "Incompatible", "parameters": parameters, "aliases": [], "inputs": [],
            "request_id": "incompatible-storage", "reason": "Verificar capacidades"})
        self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual(response.json()["detail"]["code"], "RULE_CAPABILITY_UNSUPPORTED")

    @unittest.skipUnless(os.environ.get("RULE_RUNTIME_IMAGE"), "pinned OCI image required")
    def test_queued_run_fails_if_the_worker_no_longer_supports_the_adapter(self):
        from app.rule_worker import RuleWorker
        from app.rule_runtime import OCIExecutor
        from app.runner import JuliaRunExecutor
        from tests.test_manual_runs import AcceptingRunValidationService
        import subprocess
        scope = self.hydro_scope()
        with RuleWorker(self.store, OCIExecutor.from_env()):
            path, _, job = self.compile_published(scope)
        self.assertEqual(post_json_with_csrf(self.client, path + "/applications", {"job_id": job["id"], "reason": "Fijar límite"}).status_code, 201)
        self.engine.adapters = ["hydro_v2.v1"]
        target = f"/api/scenarios/{scope['scenario_id']}/case/variants/{scope['variant_id']}/run"
        response = post_json_with_csrf(self.client, target, {k: scope[k] for k in ("range_start", "range_end")})
        self.assertEqual(response.status_code, 201, response.text)
        executor = JuliaRunExecutor(store=self.store, artifact_root=self.temporary.name,
            validation_service=AcceptingRunValidationService(),
            runner=lambda *args, **kwargs: subprocess.CompletedProcess(args, 0, stdout='{}', stderr=''))
        executor.execute(response.json()["id"])
        run = self.client.get(f"/api/runs/{response.json()['id']}").json()["run"]
        self.assertEqual(run["status"], "failed")
        self.assertEqual(run["error_payload"]["code"], "RULE_CAPABILITY_UNSUPPORTED")

    @unittest.skipUnless(os.environ.get("RULE_RUNTIME_IMAGE"), "pinned OCI image required")
    def test_changing_hydro_parameters_invalidates_the_pin_without_rewriting_it(self):
        from app.rule_worker import RuleWorker
        from app.rule_runtime import OCIExecutor
        scope = self.hydro_scope()
        with RuleWorker(self.store, OCIExecutor.from_env()):
            path, _, job = self.compile_published(scope)
        applied = post_json_with_csrf(self.client, path + "/applications", {"job_id": job["id"], "reason": "Fijar modelo"}).json()
        frozen = copy.deepcopy(applied["compilation"])
        draft = self.store.get_scenario_draft(scope["scenario_id"])["document"]
        next(a for a in draft["assets"] if a["type"] == "hydro")["turbine_flow_max_m3s"] = 9
        self.store.update_scenario_draft(scenario_id=scope["scenario_id"], document=draft)
        current = self.client.get(path + "/applications").json()["items"][0]
        self.assertEqual(current["validation_status"], "stale")
        self.assertEqual(current["compilation"], frozen)
        target = f"/api/scenarios/{scope['scenario_id']}/case/variants/{scope['variant_id']}/run"
        response = post_json_with_csrf(self.client, target, {k: scope[k] for k in ("range_start", "range_end")})
        self.assertEqual(response.status_code, 409, response.text)

    @unittest.skipUnless(os.environ.get("RULE_RUNTIME_IMAGE"), "pinned OCI image required")
    def test_cloning_a_v2_variant_keeps_its_pin_and_requires_revalidation(self):
        from app.rule_worker import RuleWorker
        from app.rule_runtime import OCIExecutor
        scope = self.hydro_scope()
        with RuleWorker(self.store, OCIExecutor.from_env()):
            path, publication, job = self.compile_published(scope)
        self.assertEqual(post_json_with_csrf(self.client, path + "/applications", {"job_id": job["id"], "reason": "Original"}).status_code, 201)
        response = post_json_with_csrf(self.client, f"/api/scenarios/{scope['scenario_id']}/case/variants/{scope['variant_id']}/clone", {"display_name": "Copia hidro"})
        self.assertEqual(response.status_code, 201, response.text)
        cloned = next(a for a in self.client.get(path + "/applications").json()["items"] if a["variant_id"] == response.json()["id"])
        self.assertEqual(cloned["publication_id"], publication["id"])
        self.assertEqual(cloned["adapter"], "hydro_v2.v1")
        self.assertEqual(cloned["validation_status"], "stale")


@unittest.skipUnless(os.environ.get("POSTGRES_TEST_DATABASE_URL"), "isolated PostgreSQL required")
class PostgresSimpleHydroRuleTests(SimpleHydroRuleTests):
    database_url = os.environ.get("POSTGRES_TEST_DATABASE_URL", "sqlite:///:memory:")
