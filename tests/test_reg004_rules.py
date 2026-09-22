"""Hydraulic relationships at the authenticated HTTP boundary."""
import os
import copy
import unittest

from tests import test_reg003_rules as hourly
from tests.test_reg001_rules import PAYLOAD
from tests.auth_test_helpers import post_json_with_csrf, csrf_headers


class RelatedRuleApiTests(unittest.TestCase):
    database_url = "sqlite:///:memory:"
    setUp = hourly.HourlyRuleApiTests.setUp
    tearDown = hourly.HourlyRuleApiTests.tearDown
    hydraulic_scope = hourly.HourlyRuleApiTests.hydraulic_scope
    preview = hourly.HourlyRuleApiTests.preview
    source = hourly.HourlyRuleApiTests.source
    port = hourly.HourlyRuleApiTests.port

    def test_input_selector_resolves_the_requested_object_in_the_same_model(self):
        scope, objects = self.related_fixture()
        source = self.source()
        second_id = objects["unit_2"]["id"]
        query = {"scenario_id": scope["scenario_id"], "reference_object_id": second_id}
        response = self.client.get(self.root + "/input-candidates", params=query)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual([(r["object_id"], r["signal_id"]) for r in response.json()["items"]], [(second_id, source["signal_ids"]["input"])])
        invalid = self.client.get(self.root + "/input-candidates", params={**query, "reference_object_id": self.obj["id"]})
        self.assertEqual(invalid.status_code, 422, invalid.text)

    def test_parameters_and_series_can_belong_to_a_declared_reference_only(self):
        scope, objects = self.related_fixture()
        second_id = objects["unit_2"]["id"]
        port = self.port(self.source(), object_id=second_id)
        aliases = [{"alias": "segunda", "object_id": second_id}]
        parameter = {"name": "reserva", "type": "number", "unit": "hm3", "value": 10,
                     "object_id": objects["reservoir_alpha"]["id"]}
        payload = {**PAYLOAD, "scenario_id": scope["scenario_id"], "aliases": aliases + [{"alias": "agua", "object_id": parameter["object_id"]}],
                   "inputs": [port], "parameters": [parameter]}
        response = post_json_with_csrf(self.client, self.root, payload)
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()["inputs"], [port])
        self.assertEqual(response.json()["parameters"][0]["object_id"], parameter["object_id"])
        for change in ({"aliases": []}, {"parameters": [{**parameter, "object_id": self.obj["id"]}]}):
            rejected = post_json_with_csrf(self.client, self.root, {**payload, **change})
            self.assertEqual(rejected.status_code, 422, rejected.text)

    @unittest.skipUnless(os.environ.get("RULE_RUNTIME_IMAGE"), "pinned OCI image required")
    def test_specific_series_of_a_reference_preserves_ownership_through_application(self):
        from tests.test_ts7_010_object_specific_series import DEFINITION, POINTS_INGESTION
        from app.rule_runtime import OCIExecutor
        from app.rule_worker import RuleWorker
        scope, objects = self.related_fixture()
        identity = objects["unit_2"]["id"]
        series_root = f"/api/projects/{self.project['id']}/linkable-objects/{identity}/time-series/object-series"
        definition = {**DEFINITION, "object_series_key": "available", "semantic_type_key": "availability_factor", "intended_binding_role_key": "rule_availability", "unit_key": "dimensionless", "timezone": "UTC"}
        created = self.client.post(series_root, json=definition, headers={**csrf_headers(self.client), "Idempotency-Key": self.token})
        self.assertEqual(created.status_code, 201, created.text)
        signal = created.json()["object_series"]["signal_id"]
        target = f"{series_root}/{signal}/revision-ingestions"
        prepared = post_json_with_csrf(self.client, target + "/points", {**POINTS_INGESTION, "revision_contract": {**POINTS_INGESTION["revision_contract"], "timezone": "UTC"},
            "points": [{"timestamp_start": f"2026-01-01T0{t}:00:00Z", "duration_seconds": 3600, "values": {"available": {"value": 0.5}}} for t in range(4)]})
        self.assertEqual(prepared.status_code, 201, prepared.text)
        ingestion = prepared.json()["ingestion"]
        published = self.client.post(f"{target}/{ingestion['ingestion_id']}/publications", json={"validation_token": ingestion["validation_token"], "confirm": False, "reason_code": "forecast_refresh"},
                                     headers={**csrf_headers(self.client), "If-Match": created.headers["etag"], "Idempotency-Key": self.token + "publish"})
        self.assertEqual(published.status_code, 201, published.text)
        candidate = self.client.get(self.root + "/input-candidates", params={"scenario_id": scope["scenario_id"], "reference_object_id": identity}).json()["items"][0]
        port = {k: candidate[k] for k in ("alias", "object_id", "signal_id", "revision_id", "content_hash", "dimension_key", "semantic_type_key", "binding_role_key")}
        payload = {**PAYLOAD, "scenario_id": scope["scenario_id"], "aliases": [{"alias": "segunda", "object_id": identity}], "inputs": [port],
                   "parameters": [{"name": "capacidad", "type": "number", "unit": "m3_per_s", "value": 20, "object_id": identity}],
                   "code": 'def construir(ctx):\n    for t in ctx.periodos:\n        ctx.restriccion("disponible", t, ctx.objetos.segunda.caudal[t] <= ctx.parametros.capacidad * ctx.entradas.entrada[t])\n'}
        saved = post_json_with_csrf(self.client, self.root, payload)
        self.assertEqual(saved.status_code, 201, saved.text)
        forged = post_json_with_csrf(self.client, self.root, {**payload, "inputs": [{**port, "object_id": objects["unit_1"]["id"]}]})
        self.assertEqual(forged.status_code, 422, forged.text)
        path = self.root + "/" + saved.json()["id"]
        publication = post_json_with_csrf(self.client, path + "/publications", {"expected_revision": 1}).json()
        with RuleWorker(self.store, OCIExecutor.from_env()):
            job = self.preview(scope, path, publication)
        self.assertEqual(job["status"], "succeeded", job)
        self.assertEqual([r["constant"] for r in job["result"]["ir"]["rows"]], [-10] * 4)
        applied = post_json_with_csrf(self.client, path + "/applications", {"job_id": job["id"], "reason": "Disponibilidad de segunda unidad"})
        self.assertEqual(applied.status_code, 201, applied.text)
        self.assertEqual(applied.json()["inputs"][0]["owner_linkable_object_id"], identity)
        diagram = self.store.get_hydraulic_diagram(scope["scenario_id"])
        plant = next(n for n in diagram["nodes"] if n["technical_key"] == "plant_laja")
        next(u for u in plant["units"] if u["technical_key"] == "unit_2")["is_active"] = False
        self.store.save_hydraulic_diagram(scenario_id=scope["scenario_id"], revision=diagram["revision"], nodes=diagram["nodes"], reaches=diagram["reaches"])
        with RuleWorker(self.store, OCIExecutor.from_env()):
            rejected = post_json_with_csrf(self.client, path + "/tests", {"expected_revision": 1, "publication_id": publication["id"], "scope": scope})
        self.assertEqual(rejected.status_code, 422, rejected.text)
        self.assertEqual((rejected.json()["detail"]["alias"], rejected.json()["detail"]["line"]), ("segunda", 3))

    def related_fixture(self):
        scope = self.hydraulic_scope()
        diagram = self.store.get_hydraulic_diagram(scope["scenario_id"])
        nodes = diagram["nodes"]
        plant = next(n for n in nodes if n["technical_key"] == "plant_laja")
        from tests.test_hydro_diagram_acceptance import complete_v3_nodes
        second = copy.deepcopy(complete_v3_nodes()[-1]["units"][0])
        second["technical_key"] = "unit_2"
        second["display_name"] = "Segunda unidad"
        plant["units"].append(second)
        self.store.save_hydraulic_diagram(scenario_id=scope["scenario_id"], revision=diagram["revision"], nodes=nodes, reaches=diagram["reaches"])
        candidates = self.client.get(self.root + "/object-candidates", params={"scenario_id": scope["scenario_id"]}).json()["items"]
        return scope, {o["key"]: o for o in candidates}

    @unittest.skipUnless(os.environ.get("RULE_RUNTIME_IMAGE"), "pinned OCI image required")
    def test_preview_rejects_storage_above_the_physical_capacity(self):
        from app.rule_worker import RuleWorker
        from app.rule_runtime import OCIExecutor
        scope, objects = self.related_fixture()
        saved = post_json_with_csrf(self.client, self.root, {**PAYLOAD, "scenario_id": scope["scenario_id"],
            "aliases": [{"alias": "agua", "object_id": objects["reservoir_alpha"]["id"]}],
            "code": 'def construir(ctx):\n    for t in ctx.periodos:\n        ctx.restriccion("reserva", t, ctx.objetos.agua.almacenamiento[t] >= ctx.parametros.reserva)\n',
            "parameters": [{"name": "reserva", "type": "number", "unit": "hm3", "value": 51}]})
        self.assertEqual(saved.status_code, 201, saved.text)
        path = self.root + "/" + saved.json()["id"]
        publication = post_json_with_csrf(self.client, path + "/publications", {"expected_revision": 1}).json()
        with RuleWorker(self.store, OCIExecutor.from_env()):
            job = self.preview(scope, path, publication)
        self.assertEqual(job["status"], "failed", job)
        self.assertEqual(job["result"]["error"]["code"], "RULE_BOUNDS_CONFLICT")
        self.assertEqual(job["result"]["error"]["period"], 0)

    @unittest.skipUnless(os.environ.get("RULE_RUNTIME_IMAGE"), "pinned OCI image required")
    def test_plant_rule_freezes_aliases_and_all_members_in_run_snapshot(self):
        from app.rule_worker import RuleWorker
        from app.rule_runtime import OCIExecutor
        scope, objects = self.related_fixture()
        aliases = [{"alias": "central", "object_id": objects["plant_laja"]["id"]}]
        saved = post_json_with_csrf(self.client, self.root, {**PAYLOAD, "scenario_id": scope["scenario_id"], "aliases": aliases,
            "code": 'def construir(ctx):\n    for t in ctx.periodos:\n        ctx.restriccion("conjunto", t, ctx.objetos.central.potencia[t] <= ctx.parametros.limite)\n',
            "parameters": [{"name": "limite", "type": "number", "unit": "mw", "value": 10}]} )
        self.assertEqual(saved.status_code, 201, saved.text)
        path = self.root + "/" + saved.json()["id"]
        publication = post_json_with_csrf(self.client, path + "/publications", {"expected_revision": 1}).json()
        with RuleWorker(self.store, OCIExecutor.from_env()):
            job = self.preview(scope, path, publication)
        self.assertEqual(job["status"], "succeeded", job)
        self.assertEqual(job["result"].get("bounds", []), [])
        applied = post_json_with_csrf(self.client, path + "/applications", {"job_id": job["id"], "reason": "Potencia conjunta"})
        self.assertEqual(applied.status_code, 201, applied.text)
        unsupported = post_json_with_csrf(self.client, f"/api/scenarios/{scope['scenario_id']}/case/variants/{scope['variant_id']}/run", {k: scope[k] for k in ("range_start", "range_end")})
        self.assertEqual(unsupported.status_code, 409, unsupported.text)
        self.engine.capabilities.append("affine_hydraulic.v1")
        run = post_json_with_csrf(self.client, f"/api/scenarios/{scope['scenario_id']}/case/variants/{scope['variant_id']}/run",
                                 {k: scope[k] for k in ("range_start", "range_end")})
        self.assertEqual(run.status_code, 201, run.text)
        version = self.client.get(f"/api/scenario-versions/{run.json()['scenario_version_id']}").json()["scenario_version"]
        block = version["system_case_json"]["component_rules"]
        self.assertEqual(block["applications"][0]["aliases"], aliases)
        self.assertEqual({o["id"] for o in block["objects"]}, {objects[k]["id"] for k in ("unit_1", "unit_2", "plant_laja")})
        self.assertEqual(len(block["rows"][0]["terms"]), 2)
        diagram = self.store.get_hydraulic_diagram(scope["scenario_id"])
        plant = next(n for n in diagram["nodes"] if n["technical_key"] == "plant_laja")
        next(u for u in plant["units"] if u["technical_key"] == "unit_2")["is_active"] = False
        self.store.save_hydraulic_diagram(scenario_id=scope["scenario_id"], revision=diagram["revision"], nodes=diagram["nodes"], reaches=diagram["reaches"])
        application = self.client.get(path + "/applications").json()["items"][0]
        self.assertEqual(application["validation_status"], "stale")
        blocked = post_json_with_csrf(self.client, f"/api/scenarios/{scope['scenario_id']}/case/variants/{scope['variant_id']}/run",
                                     {k: scope[k] for k in ("range_start", "range_end")})
        self.assertEqual(blocked.status_code, 409, blocked.text)
        self.assertEqual(self.client.get(f"/api/scenario-versions/{run.json()['scenario_version_id']}").json()["scenario_version"], version)

    def test_aliases_are_persisted_by_identity_and_reject_other_cases(self):
        scope = self.hydraulic_scope()
        items = self.client.get(self.root + "/object-candidates", params={"scenario_id": scope["scenario_id"]}).json()["items"]
        plant = next(o for o in items if o["kind"] == "hydraulic_plant")
        aliases = [{"alias": "central", "object_id": plant["id"]}]
        payload = {**PAYLOAD, "scenario_id": scope["scenario_id"], "aliases": aliases}
        saved = post_json_with_csrf(self.client, self.root, payload)
        self.assertEqual(saved.status_code, 201, saved.text)
        path = self.root + "/" + saved.json()["id"]
        self.assertEqual(self.client.get(path).json()["aliases"], aliases)
        publication = post_json_with_csrf(self.client, path + "/publications", {"expected_revision": 1})
        self.assertEqual(publication.json()["aliases"], aliases)
        # The original setUp unit is in the same project, but outside this case.
        rejected = post_json_with_csrf(self.client, self.root, {**payload, "aliases": [{"alias": "externa", "object_id": self.obj["id"]}]})
        self.assertEqual(rejected.status_code, 422, rejected.text)
        self.assertEqual(rejected.json()["detail"]["alias"], "externa")

    def test_editor_discovers_only_real_variables_in_its_hydraulic_model(self):
        scope = self.hydraulic_scope()
        response = self.client.get(self.root + "/object-candidates", params={"scenario_id": scope["scenario_id"]})
        self.assertEqual(response.status_code, 200, response.text)
        by_key = {o["key"]: o for o in response.json()["items"]}
        self.assertEqual(by_key["unit_1"]["variables"], {"caudal": "m3_per_s", "potencia": "mw"})
        self.assertEqual(by_key["plant_laja"]["variables"], {"potencia": "mw"})
        self.assertEqual(by_key["reservoir_alpha"]["variables"], {"almacenamiento": "hm3", "vertimiento": "m3_per_s"})
        self.assertEqual(set(by_key), {"unit_1", "plant_laja", "reservoir_alpha"})
        self.assertEqual(by_key["plant_laja"]["member_ids"], [by_key["unit_1"]["id"]])

    def test_unknown_or_foreign_models_and_objects_are_rejected_without_leaking_context(self):
        from tests.test_ts7_003_linkable_object_register import HydraulicFixture
        scope = self.hydraulic_scope()
        missing = self.client.get(self.root + "/object-candidates", params={"scenario_id": 999999999})
        self.assertEqual(missing.status_code, 404)
        foreign = self.store.create_project(name="Fuera " + self.token)
        fixture = HydraulicFixture(self.store, foreign["id"], prefix=self.token + "foreign")
        obj = self.store.register_linkable_object(project_id=foreign["id"], object_kind="hydraulic_unit", subtype_id=fixture.ids["hydraulic_unit"])
        rejected = post_json_with_csrf(self.client, self.root, {**PAYLOAD, "scenario_id": scope["scenario_id"], "aliases": [{"alias": "externa", "object_id": obj["id"]}]})
        self.assertEqual(rejected.status_code, 422, rejected.text)
        self.assertEqual(rejected.json()["detail"]["alias"], "externa")


@unittest.skipUnless(os.environ.get("POSTGRES_TEST_DATABASE_URL"), "isolated PostgreSQL required")
class RelatedRulePostgresTests(RelatedRuleApiTests):
    database_url = os.environ.get("POSTGRES_TEST_DATABASE_URL")
