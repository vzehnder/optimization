"""Battery rules through authenticated HTTP and the real OCI runtime."""
import json
import os
import unittest
from pathlib import Path

from app.draft_editor import structured_draft_document_from_system_case
from tests import test_reg003_rules as hourly
from tests.auth_test_helpers import post_json_with_csrf


class BatteryRuleTests(unittest.TestCase):
    database_url = "sqlite:///:memory:"
    setUp = hourly.HourlyRuleApiTests.setUp
    tearDown = hourly.HourlyRuleApiTests.tearDown
    preview = hourly.HourlyRuleApiTests.preview
    source = hourly.HourlyRuleApiTests.source
    port = hourly.HourlyRuleApiTests.port

    def publish_rule(self, scope, code, parameters=None, inputs=None, aliases=None, **contract):
        saved = post_json_with_csrf(self.client, self.root, {
            "name": "Reserva batería", "expected_revision": 0, "scenario_id": scope["scenario_id"],
            "code": code, "parameters": parameters or [], "inputs": inputs or [], "aliases": aliases or [], **contract})
        self.assertEqual(saved.status_code, 201, saved.text)
        path = self.root + "/" + saved.json()["id"]
        published = post_json_with_csrf(self.client, path + "/publications", {"expected_revision": 1})
        self.assertEqual(published.status_code, 201, published.text)
        return path, published.json()

    def battery_scope(self):
        document = json.loads(Path("data/cases/linear_hydro_system/system_case.json").read_text())
        battery = next(n for n in document["nodes"] if n["type"] == "battery")
        battery.update(charge_power_max_mw=4, discharge_power_max_mw=4,
                       energy_max_mwh=10, initial_energy_mwh=5,
                       charge_efficiency=0.8, discharge_efficiency=0.9,
                       terminal_condition="equal_initial")
        scenario = self.store.create_scenario(project_id=self.project["id"], name="Batería")
        draft = structured_draft_document_from_system_case(document)
        draft["time_series"] = {"periods": document["time_series"]}
        self.store.create_or_replace_scenario_draft(scenario_id=scenario["id"], document=draft)
        self.store.materialize_project_linkable_objects(project_id=self.project["id"])
        self.obj = next(o for o in self.store.list_linkable_objects(project_id=self.project["id"])
                        if o["object_type_key"] == "component:battery")
        self.root = f"/api/projects/{self.project['id']}/linkable-objects/{self.obj['id']}/rules"
        variant = self.client.get(f"/api/scenarios/{scenario['id']}/case/default-variant").json()["variant"]
        return {"scenario_id": scenario["id"], "variant_id": variant["id"],
                "range_start": "2026-01-01T00:00:00", "range_end": "2026-01-01T02:00:00"}

    def test_context_exposes_battery_units_signs_and_end_of_period_energy(self):
        scope = self.battery_scope()
        response = self.client.get(f"/api/scenarios/{scope['scenario_id']}/components/battery_1/rule-context")
        self.assertEqual(response.status_code, 200, response.text)
        response = self.client.get(self.root + "/object-candidates", params={"scenario_id": scope["scenario_id"]})
        self.assertEqual(response.status_code, 200, response.text)
        battery = next(o for o in response.json()["items"] if o["id"] == self.obj["id"])
        self.assertEqual(battery["variables"], {"carga": "mw", "descarga": "mw", "energia": "mwh"})
        self.assertEqual(battery["conventions"], {"carga": "nonnegative_interval_mean", "descarga": "nonnegative_interval_mean", "energia": "end_of_period"})
        self.assertEqual(battery["known_values"]["energia_inicial"], {"value": 5, "unit": "mwh"})

    def test_reserve_input_uses_canonical_energy_classification_and_excludes_inflow(self):
        scope = self.battery_scope()
        source = self.source((7, 5), semantic="battery_energy_reserve", unit="mwh")
        self.source((3, 4))
        port = self.port(source, alias="reserva", dimension_key="energy",
                         semantic_type_key="battery_energy_reserve", binding_role_key="rule_energy_reserve")
        response = self.client.get(self.root + "/input-candidates")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual([(i["signal_id"], i["binding_role_key"]) for i in response.json()["items"]],
                         [(source["signal_ids"]["input"], "rule_energy_reserve")])
        body = {"name": "Reserva", "expected_revision": 0, "scenario_id": scope["scenario_id"],
                "code": 'def construir(ctx):\n    for t in ctx.periodos:\n        ctx.restriccion("reserva", t, ctx.objeto.energia[t] >= ctx.entradas.reserva[t])',
                "parameters": [], "inputs": [port]}
        saved = post_json_with_csrf(self.client, self.root, body)
        self.assertEqual(saved.status_code, 201, saved.text)
        rejected = post_json_with_csrf(self.client, self.root, {**body, "inputs": [{**port, "binding_role_key": "rule_availability"}]})
        self.assertEqual(rejected.status_code, 422, rejected.text)

    @unittest.skipUnless(os.environ.get("RULE_RUNTIME_IMAGE"), "pinned OCI image required")
    def test_hourly_reserve_and_affine_power_limits_compile_apply_and_pin_the_adapter(self):
        from app.rule_worker import RuleWorker
        from app.rule_runtime import OCIExecutor
        scope = self.battery_scope()
        source = self.source((7, 5), semantic="battery_energy_reserve", unit="mwh")
        port = self.port(source, alias="reserva", dimension_key="energy",
                         semantic_type_key="battery_energy_reserve", binding_role_key="rule_energy_reserve")
        path, publication = self.publish_rule(scope,
            'def construir(ctx):\n    for t in ctx.periodos:\n'
            '        ctx.restriccion("reserva", t, ctx.objeto.energia[t] >= ctx.entradas.reserva[t])\n'
            '        ctx.restriccion("potencia", t, ctx.objeto.carga[t] + ctx.objeto.descarga[t] <= ctx.parametros.limite)\n'
            '        ctx.salida("reserva", t, ctx.entradas.reserva[t])\n',
            [{"name": "limite", "type": "number", "unit": "mw", "value": 3}], [port])
        with RuleWorker(self.store, OCIExecutor.from_env()):
            job = self.preview(scope, path, publication)
        self.assertEqual(job["status"], "succeeded", job)
        self.assertEqual(len(job["result"]["ir"]["rows"]), 4)
        self.assertEqual([r["value"] for r in job["result"]["outputs"]], [7, 5])
        applied = post_json_with_csrf(self.client, path + "/applications", {"job_id": job["id"], "reason": "Reserva operativa"})
        self.assertEqual(applied.status_code, 201, applied.text)
        self.assertEqual(applied.json()["adapter"], "battery_system.v1")
        self.assertEqual(applied.json()["validation_status"], "valid")

    @unittest.skipUnless(os.environ.get("RULE_RUNTIME_IMAGE"), "pinned OCI image required")
    def test_initial_energy_is_a_typed_known_value_in_the_same_sdk(self):
        from app.rule_worker import RuleWorker
        from app.rule_runtime import OCIExecutor
        scope = self.battery_scope()
        path, publication = self.publish_rule(scope,
            'def construir(ctx):\n    for t in ctx.periodos:\n'
            '        ctx.restriccion("inicial", t, ctx.objeto.energia[t] >= ctx.objeto.energia_inicial * 0.5)\n')
        with RuleWorker(self.store, OCIExecutor.from_env()):
            job = self.preview(scope, path, publication)
        self.assertEqual(job["status"], "succeeded", job)
        self.assertEqual([r["constant"] for r in job["result"]["ir"]["rows"]], [-2.5, -2.5])

    @unittest.skipUnless(os.environ.get("RULE_RUNTIME_IMAGE"), "pinned OCI image required")
    def test_reserve_above_capacity_is_diagnosed_before_application(self):
        from app.rule_worker import RuleWorker
        from app.rule_runtime import OCIExecutor
        scope = self.battery_scope()
        path, publication = self.publish_rule(scope,
            'def construir(ctx):\n    ctx.restriccion("reserva", 0, ctx.objeto.energia[0] >= ctx.parametros.reserva)',
            [{"name": "reserva", "type": "number", "unit": "mwh", "value": 11}])
        with RuleWorker(self.store, OCIExecutor.from_env()):
            job = self.preview(scope, path, publication)
        self.assertEqual(job["status"], "failed", job)
        problem = job["result"]["error"]
        self.assertEqual((problem["code"], problem["variable"], problem["period"], problem["line"]),
                         ("RULE_BOUNDS_CONFLICT", "energia", 0, 2))
        self.assertEqual(self.client.get(path + "/applications").json()["items"], [])
        rejected = post_json_with_csrf(self.client, path + "/applications", {"job_id": job["id"], "reason": "Imposible"})
        self.assertEqual(rejected.status_code, 409, rejected.text)

    @unittest.skipUnless(os.environ.get("RULE_RUNTIME_IMAGE"), "pinned OCI image required")
    def test_capacity_changes_block_new_runs_and_preserve_the_frozen_history(self):
        from app.rule_worker import RuleWorker
        from app.rule_runtime import OCIExecutor
        scope = self.battery_scope()
        path, publication = self.publish_rule(scope,
            'def construir(ctx):\n    for t in ctx.periodos:\n        ctx.restriccion("reserva", t, ctx.objeto.energia[t] >= ctx.objeto.energia_inicial)')
        with RuleWorker(self.store, OCIExecutor.from_env()):
            job = self.preview(scope, path, publication)
        applied = post_json_with_csrf(self.client, path + "/applications", {"job_id": job["id"], "reason": "Fijar capacidad"})
        self.assertEqual(applied.status_code, 201, applied.text)
        target = f"/api/scenarios/{scope['scenario_id']}/case/variants/{scope['variant_id']}/run"
        body = {k: scope[k] for k in ("range_start", "range_end")}
        self.engine.capabilities = ["affine_hydraulic.v1"]
        old_engine = post_json_with_csrf(self.client, target, body)
        self.assertEqual(old_engine.status_code, 409, old_engine.text)
        self.engine.adapters = ["battery_system.v1"]
        run = post_json_with_csrf(self.client, target, body)
        self.assertEqual(run.status_code, 201, run.text)
        version_path = f"/api/scenario-versions/{run.json()['scenario_version_id']}"
        frozen = self.client.get(version_path).json()["scenario_version"]
        self.assertEqual(frozen["system_case_json"]["component_rules"]["adapter"], "battery_system.v1")
        draft = self.store.get_scenario_draft(scope["scenario_id"])["document"]
        next(a for a in draft["assets"] if a["type"] == "battery")["energy_max_mwh"] = 8
        self.store.update_scenario_draft(scenario_id=scope["scenario_id"], document=draft)
        current = self.client.get(path + "/applications").json()["items"][0]
        self.assertEqual(current["validation_status"], "stale")
        self.assertEqual(current["compilation"], applied.json()["compilation"])
        self.assertEqual(post_json_with_csrf(self.client, target, body).status_code, 409)
        self.assertEqual(self.client.get(version_path).json()["scenario_version"], frozen)

    @unittest.skipUnless(os.environ.get("RULE_RUNTIME_IMAGE"), "pinned OCI image required")
    def test_battery_templates_and_cloned_variants_preserve_pins_and_require_revalidation(self):
        from app.rule_worker import RuleWorker
        from app.rule_runtime import OCIExecutor
        scope = self.battery_scope()
        path, publication = self.publish_rule(scope,
            'def construir(ctx):\n    for t in ctx.periodos:\n        ctx.restriccion("reserva", t, ctx.objeto.energia[t] >= ctx.objeto.energia_inicial)')
        template = post_json_with_csrf(self.client, path + "/library", {"publication_id": publication["id"]})
        self.assertEqual(template.status_code, 201, template.text)
        self.assertEqual(template.json()["compatible_types"], ["battery"])
        self.assertEqual(template.json()["required_capabilities"], ["affine_hydraulic.v1"])
        with RuleWorker(self.store, OCIExecutor.from_env()):
            job = self.preview(scope, path, publication)
        self.assertEqual(post_json_with_csrf(self.client, path + "/applications", {"job_id": job["id"], "reason": "Original"}).status_code, 201)
        response = post_json_with_csrf(self.client, f"/api/scenarios/{scope['scenario_id']}/case/variants/{scope['variant_id']}/clone", {"display_name": "Copia batería"})
        self.assertEqual(response.status_code, 201, response.text)
        cloned = next(a for a in self.client.get(path + "/applications").json()["items"] if a["variant_id"] == response.json()["id"])
        self.assertEqual(cloned["publication_id"], publication["id"])
        self.assertEqual(cloned["adapter"], "battery_system.v1")
        self.assertEqual(cloned["validation_status"], "stale")

    @unittest.skipUnless(os.environ.get("RULE_RUNTIME_IMAGE"), "pinned OCI image required")
    def test_battery_can_relate_to_hydro_only_in_the_same_snapshot(self):
        from app.rule_worker import RuleWorker
        from app.rule_runtime import OCIExecutor
        foreign_id = self.obj["id"]
        scope = self.battery_scope()
        candidates = self.client.get(self.root + "/object-candidates", params={"scenario_id": scope["scenario_id"]}).json()["items"]
        hydro = next(o for o in candidates if o["kind"] == "hydro")
        code = 'def construir(ctx):\n    for t in ctx.periodos:\n        ctx.restriccion("recarga", t, ctx.objeto.carga[t] <= ctx.objetos.hidro.potencia[t])'
        body = {"name": "Relación", "code": code, "expected_revision": 0, "scenario_id": scope["scenario_id"],
                "parameters": [], "aliases": [{"alias": "hidro", "object_id": foreign_id}]}
        foreign = post_json_with_csrf(self.client, self.root, body)
        self.assertEqual(foreign.status_code, 422, foreign.text)
        self.assertEqual(foreign.json()["detail"]["code"], "RULE_OBJECT_INVALID")
        path, publication = self.publish_rule(scope, code, aliases=[{"alias": "hidro", "object_id": hydro["id"]}])
        with RuleWorker(self.store, OCIExecutor.from_env()):
            job = self.preview(scope, path, publication)
        self.assertEqual(job["status"], "succeeded", job)
        self.assertEqual({t["object_id"] for t in job["result"]["ir"]["rows"][0]["terms"]}, {self.obj["id"], hydro["id"]})

    @unittest.skipUnless(os.environ.get("RULE_RUNTIME_IMAGE"), "pinned OCI image required")
    def test_battery_rejects_nonlinear_decisions_conditions_and_user_variables(self):
        from app.rule_worker import RuleWorker
        from app.rule_runtime import OCIExecutor
        scope = self.battery_scope()
        for expression in ('ctx.objeto.carga[0] * ctx.objeto.descarga[0]',
                           'ctx.objeto.carga[0] / ctx.objeto.descarga[0]',
                           'bool(ctx.objeto.energia[0] >= ctx.objeto.energia_inicial)',
                           'ctx.variable("binaria")'):
            with self.subTest(expression=expression):
                path, publication = self.publish_rule(scope, f'def construir(ctx):\n    valor = {expression}')
                with RuleWorker(self.store, OCIExecutor.from_env()):
                    job = self.preview(scope, path, publication)
                self.assertEqual(job["status"], "failed", job)
                self.assertEqual(job["result"]["error"]["code"], "RULE_CODE_ERROR")
                self.assertEqual(job["result"]["error"]["line"], 2)
                self.assertEqual(self.client.get(path + "/applications").json()["items"], [])

    @unittest.skipUnless(os.environ.get("RULE_RUNTIME_IMAGE"), "pinned OCI image required")
    def test_new_reserve_revision_invalidates_the_application_without_moving_its_pin(self):
        from app.rule_worker import RuleWorker
        from app.rule_runtime import OCIExecutor
        scope = self.battery_scope()
        source = self.source((7, 5), semantic="battery_energy_reserve", unit="mwh")
        port = self.port(source, alias="reserva", dimension_key="energy", semantic_type_key="battery_energy_reserve", binding_role_key="rule_energy_reserve")
        path, publication = self.publish_rule(scope,
            'def construir(ctx):\n    for t in ctx.periodos:\n        ctx.restriccion("reserva", t, ctx.objeto.energia[t] >= ctx.entradas.reserva[t])', inputs=[port])
        with RuleWorker(self.store, OCIExecutor.from_env()):
            job = self.preview(scope, path, publication)
        applied = post_json_with_csrf(self.client, path + "/applications", {"job_id": job["id"], "reason": "Reserva fijada"})
        self.assertEqual(applied.status_code, 201, applied.text)
        self.source((6, 5), semantic="battery_energy_reserve", unit="mwh")
        state = self.client.get(path + "/applications").json()["items"][0]
        self.assertEqual(state["validation_status"], "stale")
        self.assertEqual(state["inputs"][0]["revision_id"], source["revision_id"])
        target = f"/api/scenarios/{scope['scenario_id']}/case/variants/{scope['variant_id']}/run"
        self.assertEqual(post_json_with_csrf(self.client, target, {k: scope[k] for k in ("range_start", "range_end")}).status_code, 409)

    @unittest.skipUnless(os.environ.get("RULE_RUNTIME_IMAGE"), "pinned OCI image required")
    def test_battery_power_integrals_keep_hours_separate_from_stored_energy(self):
        from app.rule_worker import RuleWorker
        from app.rule_runtime import OCIExecutor
        scope = self.battery_scope()
        path, publication = self.publish_rule(scope,
            'def construir(ctx):\n    for ventana in ctx.ventanas():\n'
            '        ctx.restriccion("descarga", ventana, ventana.integral(ctx.objeto.descarga) <= ctx.parametros.presupuesto)\n',
            [{"name": "presupuesto", "type": "number", "unit": "mwh", "value": 3}],
            windows={"kind": "horizon", "timezone": "UTC", "partial": "reject"})
        with RuleWorker(self.store, OCIExecutor.from_env()):
            job = self.preview(scope, path, publication)
        self.assertEqual(job["status"], "succeeded", job)
        row = job["result"]["ir"]["rows"][0]
        self.assertEqual(row["unit"], "mwh")
        self.assertEqual([(t["coefficient"], t["unit"]) for t in row["terms"]], [(1, "h"), (1, "h")])

    @unittest.skipUnless(os.environ.get("RULE_RUNTIME_IMAGE"), "pinned OCI image required")
    def test_charge_ramps_accept_the_explicit_initial_policy(self):
        from app.rule_worker import RuleWorker
        from app.rule_runtime import OCIExecutor
        scope = self.battery_scope()
        path, publication = self.publish_rule(scope,
            'def construir(ctx):\n    for paso in ctx.transiciones(ctx.objeto.carga):\n'
            '        ctx.restriccion("rampa", paso.periodo, paso.actual - paso.anterior <= ctx.parametros.rampa * paso.horas)',
            [{"name": "rampa", "type": "number", "unit": "mw_per_h", "value": 1}],
            temporal={"first_period": "initial", "initial_values": [{"object_id": self.obj["id"], "variable": "carga",
                      "value": 0, "unit": "mw", "timestamp": "2025-12-31T23:00:00Z"}]})
        with RuleWorker(self.store, OCIExecutor.from_env()):
            job = self.preview(scope, path, publication)
        self.assertEqual(job["status"], "succeeded", job)
        self.assertEqual([r["constant"] for r in job["result"]["ir"]["rows"]], [-1, -1])

    @unittest.skipUnless(os.environ.get("RULE_RUNTIME_IMAGE"), "pinned OCI image required")
    def test_energy_transitions_measure_between_interval_ends_and_the_initial_state(self):
        from app.rule_worker import RuleWorker
        from app.rule_runtime import OCIExecutor
        scope = self.battery_scope()
        draft = self.store.get_scenario_draft(scope["scenario_id"])["document"]
        periods = draft["time_series"]["periods"]
        periods[0]["duration_hours"] = 0.5
        periods[1].update(timestamp="2026-01-01T00:30:00", duration_hours=1.5)
        self.store.update_scenario_draft(scenario_id=scope["scenario_id"], document=draft)
        path, publication = self.publish_rule(scope,
            'def construir(ctx):\n    for paso in ctx.transiciones(ctx.objeto.energia):\n'
            '        ctx.salida("tiempo", paso.periodo, paso.horas / ctx.parametros.hora)\n'
            '        ctx.restriccion("reserva", paso.periodo, paso.actual >= paso.anterior)\n',
            [{"name": "hora", "type": "number", "unit": "h", "value": 1}],
            temporal={"first_period": "initial", "initial_values": [{"object_id": self.obj["id"], "variable": "energia",
                      "value": 5, "unit": "mwh", "timestamp": "2026-01-01T00:00:00Z"}]})
        with RuleWorker(self.store, OCIExecutor.from_env()):
            job = self.preview(scope, path, publication)
        self.assertEqual(job["status"], "succeeded", job)
        self.assertEqual([r["value"] for r in job["result"]["outputs"]], [0.5, 1.5])


@unittest.skipUnless(os.environ.get("POSTGRES_TEST_DATABASE_URL"), "isolated PostgreSQL required")
class PostgresBatteryRuleTests(BatteryRuleTests):
    database_url = os.environ.get("POSTGRES_TEST_DATABASE_URL", "sqlite:///:memory:")
