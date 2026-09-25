"""Grid/renewable rules through authenticated HTTP and the real OCI runtime."""
import json
import os
import unittest
from pathlib import Path

from app.draft_editor import structured_draft_document_from_system_case
from tests import test_reg012_rules as battery
from tests.auth_test_helpers import post_json_with_csrf


class ElectricRuleTests(unittest.TestCase):
    database_url = "sqlite:///:memory:"
    setUp = battery.BatteryRuleTests.setUp
    tearDown = battery.BatteryRuleTests.tearDown
    publish_rule = battery.BatteryRuleTests.publish_rule
    preview = battery.BatteryRuleTests.preview
    source = battery.BatteryRuleTests.source
    port = battery.BatteryRuleTests.port

    def electric_scope(self, kind="grid"):
        document = json.loads(Path("tests/fixtures/reg013_electric.json").read_text())
        scenario = self.store.create_scenario(project_id=self.project["id"], name="Red y renovables")
        draft = structured_draft_document_from_system_case(document)
        draft["time_series"] = {"periods": document["time_series"]}
        self.store.create_or_replace_scenario_draft(scenario_id=scenario["id"], document=draft)
        self.store.materialize_project_linkable_objects(project_id=self.project["id"])
        self.obj = next(o for o in self.store.list_linkable_objects(project_id=self.project["id"])
                        if o["object_type_key"] == "component:" + kind)
        self.root = f"/api/projects/{self.project['id']}/linkable-objects/{self.obj['id']}/rules"
        variant = self.client.get(f"/api/scenarios/{scenario['id']}/case/default-variant").json()["variant"]
        return {"scenario_id": scenario["id"], "variant_id": variant["id"],
                "range_start": "2026-01-01T00:00:00", "range_end": "2026-01-01T04:00:00"}

    def test_context_exposes_four_nonnegative_powers_and_known_availability_and_demand(self):
        scope = self.electric_scope()
        response = self.client.get(f"/api/scenarios/{scope['scenario_id']}/components/grid/rule-context")
        self.assertEqual(response.status_code, 200, response.text)
        response = self.client.get(self.root + "/object-candidates", params={"scenario_id": scope["scenario_id"]})
        self.assertEqual(response.status_code, 200, response.text)
        objects = {o["kind"]: o for o in response.json()["items"]}
        self.assertEqual(objects["grid"]["variables"], {"importacion": "mw", "exportacion": "mw"})
        self.assertEqual(objects["renewable"]["variables"], {"generacion": "mw", "recorte": "mw"})
        for kind in ("grid", "renewable"):
            self.assertEqual(set(objects[kind]["conventions"].values()), {"nonnegative_interval_mean"})
        self.assertEqual(objects["renewable"]["known_series"]["disponibilidad"], {"values": [10, 8, 1, 0], "unit": "mw"})
        self.assertEqual(objects["load"]["variables"], {})
        self.assertEqual(objects["load"]["known_series"]["demanda"], {"values": [2, 2, 2, 2], "unit": "mw"})

    @unittest.skipUnless(os.environ.get("RULE_RUNTIME_IMAGE"), "pinned OCI image required")
    def test_export_fraction_compiles_with_known_series_and_pins_the_electric_adapter(self):
        from app.rule_worker import RuleWorker
        from app.rule_runtime import OCIExecutor
        scope = self.electric_scope()
        objects = self.client.get(self.root + "/object-candidates", params={"scenario_id": scope["scenario_id"]}).json()["items"]
        aliases = [{"alias": alias, "object_id": next(o["id"] for o in objects if o["kind"] == kind)}
                   for alias, kind in (("solar", "renewable"), ("consumo", "load"))]
        path, publication = self.publish_rule(scope,
            'def construir(ctx):\n    for t in ctx.periodos:\n'
            '        ctx.restriccion("fraccion", t, ctx.objeto.exportacion[t] <= ctx.parametros.fraccion * ctx.objetos.solar.generacion[t])\n'
            '        ctx.salida("disponible", t, ctx.objetos.solar.disponibilidad[t])\n'
            '        ctx.salida("demanda", t, ctx.objetos.consumo.demanda[t])\n',
            [{"name": "fraccion", "type": "number", "unit": "dimensionless", "value": 0.5}], aliases=aliases)
        with RuleWorker(self.store, OCIExecutor.from_env()):
            job = self.preview(scope, path, publication)
        self.assertEqual(job["status"], "succeeded", job)
        self.assertEqual([(t["variable"], t["coefficient"]) for t in job["result"]["ir"]["rows"][0]["terms"]],
                         [("exportacion", 1), ("generacion", -0.5)])
        self.assertEqual([r["value"] for r in job["result"]["outputs"] if r["name"] == "disponible"], [10, 8, 1, 0])
        self.assertEqual([r["value"] for r in job["result"]["outputs"] if r["name"] == "demanda"], [2, 2, 2, 2])
        applied = post_json_with_csrf(self.client, path + "/applications", {"job_id": job["id"], "reason": "Limitar exportación"})
        self.assertEqual(applied.status_code, 201, applied.text)
        self.assertEqual(applied.json()["adapter"], "electric_system.v1")
        self.assertEqual(applied.json()["validation_status"], "valid")

    @unittest.skipUnless(os.environ.get("RULE_RUNTIME_IMAGE"), "pinned OCI image required")
    def test_hourly_fraction_pins_sources_and_context_changes_block_new_runs_without_rewriting_history(self):
        from app.rule_worker import RuleWorker
        from app.rule_runtime import OCIExecutor
        scope = self.electric_scope()
        solar = next(o for o in self.client.get(self.root + "/object-candidates", params={"scenario_id": scope["scenario_id"]}).json()["items"] if o["kind"] == "renewable")
        source = self.source((0.5, 0.25, 0.5, 1), semantic="availability_factor", unit="dimensionless")
        port = self.port(source, alias="fraccion", dimension_key="dimensionless", semantic_type_key="availability_factor", binding_role_key="rule_availability")
        candidates = self.client.get(self.root + "/input-candidates")
        self.assertEqual([p["signal_id"] for p in candidates.json()["items"]], [port["signal_id"]])
        path, publication = self.publish_rule(scope,
            'def construir(ctx):\n    for t in ctx.periodos:\n'
            '        ctx.restriccion("fraccion", t, ctx.objeto.exportacion[t] <= ctx.entradas.fraccion[t] * ctx.objetos.solar.generacion[t])',
            inputs=[port], aliases=[{"alias": "solar", "object_id": solar["id"]}])
        with RuleWorker(self.store, OCIExecutor.from_env()):
            job = self.preview(scope, path, publication)
        self.assertEqual(job["status"], "succeeded", job)
        applied = post_json_with_csrf(self.client, path + "/applications", {"job_id": job["id"], "reason": "Fracción horaria"})
        self.assertEqual(applied.status_code, 201, applied.text)
        target = f"/api/scenarios/{scope['scenario_id']}/case/variants/{scope['variant_id']}/run"
        body = {k: scope[k] for k in ("range_start", "range_end")}
        self.engine.capabilities = ["affine_hydraulic.v1"]
        self.assertEqual(post_json_with_csrf(self.client, target, body).status_code, 409)
        self.engine.adapters = ["electric_system.v1"]
        run = post_json_with_csrf(self.client, target, body)
        self.assertEqual(run.status_code, 201, run.text)
        version_path = f"/api/scenario-versions/{run.json()['scenario_version_id']}"
        frozen = self.client.get(version_path).json()["scenario_version"]
        block = frozen["system_case_json"]["component_rules"]
        self.assertEqual(block["adapter"], "electric_system.v1")
        self.assertEqual(block["applications"][0]["inputs"][0]["revision_id"], source["revision_id"])
        draft = self.store.get_scenario_draft(scope["scenario_id"])["document"]
        draft["time_series"]["periods"][0]["renewable_available_power_mw"]["solar"] = 12
        self.store.update_scenario_draft(scenario_id=scope["scenario_id"], document=draft)
        self.assertEqual(self.client.get(path + "/applications").json()["items"][0]["validation_status"], "stale")
        self.assertEqual(post_json_with_csrf(self.client, target, body).status_code, 409)
        self.assertEqual(self.client.get(version_path).json()["scenario_version"], frozen)

    @unittest.skipUnless(os.environ.get("RULE_RUNTIME_IMAGE"), "pinned OCI image required")
    def test_scalar_electric_limits_respect_nonnegative_powers_and_period_availability(self):
        from app.rule_worker import RuleWorker
        from app.rule_runtime import OCIExecutor
        scope = self.electric_scope()
        objects = {o["kind"]: o for o in self.client.get(self.root + "/object-candidates", params={"scenario_id": scope["scenario_id"]}).json()["items"]}
        for kind, variable, period, relation, limit, expected in (
            ("grid", "importacion", 0, "<=", -1, "failed"),
            ("grid", "exportacion", 0, ">=", 7, "failed"),
            ("renewable", "generacion", 2, ">=", 2, "failed"),
            ("renewable", "recorte", 1, ">=", 9, "failed"),
            ("renewable", "recorte", 0, "<=", 6, "succeeded"),
        ):
            with self.subTest(variable=variable):
                self.obj = objects[kind]
                self.root = f"/api/projects/{self.project['id']}/linkable-objects/{self.obj['id']}/rules"
                path, publication = self.publish_rule(scope,
                    f'def construir(ctx):\n    ctx.restriccion("limite", {period}, ctx.objeto.{variable}[{period}] {relation} ctx.parametros.limite)',
                    [{"name": "limite", "type": "number", "unit": "mw", "value": limit}])
                with RuleWorker(self.store, OCIExecutor.from_env()):
                    job = self.preview(scope, path, publication)
                self.assertEqual(job["status"], expected, job)
                if expected == "failed":
                    self.assertEqual(job["result"]["error"]["code"], "RULE_BOUNDS_CONFLICT")
                    self.assertEqual(job["result"]["error"]["period"], period)
                    rejected = post_json_with_csrf(self.client, path + "/applications", {"job_id": job["id"], "reason": "Imposible"})
                    self.assertEqual(rejected.status_code, 409)

    def test_electric_templates_keep_known_data_and_alias_capabilities_when_reused(self):
        scope = self.electric_scope("renewable")
        objects = {o["kind"]: o for o in self.client.get(self.root + "/object-candidates", params={"scenario_id": scope["scenario_id"]}).json()["items"]}
        path, publication = self.publish_rule(scope,
            'def construir(ctx):\n    for t in ctx.periodos:\n'
            '        ctx.restriccion("solar", t, ctx.objeto.generacion[t] <= ctx.objeto.disponibilidad[t])\n'
            '        ctx.salida("demanda", t, ctx.objetos.consumo.demanda[t])',
            aliases=[{"alias": "consumo", "object_id": objects["load"]["id"]}])
        template = post_json_with_csrf(self.client, path + "/library", {"publication_id": publication["id"]})
        self.assertEqual(template.status_code, 201, template.text)
        self.assertEqual(template.json()["compatible_types"], ["renewable"])
        self.assertEqual(template.json()["required_capabilities"], ["affine_hydraulic.v1"])
        library = self.client.get(f"/api/projects/{self.project['id']}/rule-library").json()["items"]
        self.assertEqual(library[0]["aliases"][0]["compatible_types"], ["load"])

    def test_aliases_cannot_cross_into_hydraulic_v3_or_another_electrical_snapshot(self):
        foreign_unit = self.obj["id"]
        scope = self.electric_scope()
        self.store.ensure_project_component(project_id=self.project["id"], component_key="foreign_grid", component_type="grid", display_name="Otra red", actor=self.user["email"])
        self.store.materialize_project_linkable_objects(project_id=self.project["id"])
        foreign_grid = next(o["id"] for o in self.store.list_linkable_objects(project_id=self.project["id"]) if o["object_key"] == "foreign_grid")
        for foreign in (foreign_unit, foreign_grid):
            response = post_json_with_csrf(self.client, self.root, {"name": "Cruce", "expected_revision": 0,
                "scenario_id": scope["scenario_id"], "parameters": [], "aliases": [{"alias": "otra", "object_id": foreign}],
                "code": 'def construir(ctx):\n    valor = ctx.objetos.otra.exportacion[0]'})
            self.assertEqual(response.status_code, 422, response.text)
            self.assertEqual(response.json()["detail"]["code"], "RULE_OBJECT_INVALID")

    @unittest.skipUnless(os.environ.get("RULE_RUNTIME_IMAGE"), "pinned OCI image required")
    def test_electric_rules_reject_nonlinearity_wrong_units_and_symbolic_outputs(self):
        from app.rule_worker import RuleWorker
        from app.rule_runtime import OCIExecutor
        scope = self.electric_scope("renewable")
        for expression in ('ctx.objeto.generacion[0] * ctx.objeto.recorte[0]',
                           'ctx.objeto.generacion[0] / ctx.objeto.recorte[0]',
                           'bool(ctx.objeto.generacion[0] >= ctx.objeto.disponibilidad[0])',
                           'ctx.salida("decision", 0, ctx.objeto.generacion[0])',
                           'ctx.objeto.generacion[0] <= ctx.parametros.energia'):
            with self.subTest(expression=expression):
                path, publication = self.publish_rule(scope, f'def construir(ctx):\n    valor = {expression}',
                    [{"name": "energia", "type": "number", "unit": "mwh", "value": 2}])
                with RuleWorker(self.store, OCIExecutor.from_env()):
                    job = self.preview(scope, path, publication)
                self.assertEqual(job["status"], "failed", job)
                self.assertEqual(job["result"]["error"]["code"], "RULE_CODE_ERROR")
                self.assertEqual(job["result"]["error"]["line"], 2)
                self.assertEqual(self.client.get(path + "/applications").json()["items"], [])

    @unittest.skipUnless(os.environ.get("RULE_RUNTIME_IMAGE"), "pinned OCI image required")
    def test_electric_ramps_keep_the_common_explicit_initial_policy(self):
        from app.rule_worker import RuleWorker
        from app.rule_runtime import OCIExecutor
        scope = self.electric_scope()
        path, publication = self.publish_rule(scope,
            'def construir(ctx):\n    for paso in ctx.transiciones(ctx.objeto.exportacion):\n'
            '        ctx.restriccion("rampa", paso.periodo, paso.actual - paso.anterior <= ctx.parametros.rampa * paso.horas)',
            [{"name": "rampa", "type": "number", "unit": "mw_per_h", "value": 1}],
            temporal={"first_period": "initial", "initial_values": [{"object_id": self.obj["id"], "variable": "exportacion",
                      "value": 0, "unit": "mw", "timestamp": "2025-12-31T23:00:00Z"}]})
        with RuleWorker(self.store, OCIExecutor.from_env()):
            job = self.preview(scope, path, publication)
        self.assertEqual(job["status"], "succeeded", job)
        self.assertEqual([r["constant"] for r in job["result"]["ir"]["rows"]], [-1, -1, -1, -1])


@unittest.skipUnless(os.environ.get("POSTGRES_TEST_DATABASE_URL"), "isolated PostgreSQL required")
class PostgresElectricRuleTests(ElectricRuleTests):
    database_url = os.environ.get("POSTGRES_TEST_DATABASE_URL", "sqlite:///:memory:")
