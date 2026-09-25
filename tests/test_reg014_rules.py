"""Operational rules through authenticated HTTP, storage and the OCI worker."""
import os
import unittest

from app.auth import hash_password
from app.rule_runtime import OCIExecutor
from app.rule_worker import RuleWorker
from tests.auth_test_helpers import login_json_with_csrf, post_json_with_csrf, put_json_with_csrf
from tests import test_reg011_rules as hydro


@unittest.skipUnless(os.environ.get("RULE_RUNTIME_IMAGE"), "pinned OCI image required")
class OperationalRuleTests(unittest.TestCase):
    database_url = "sqlite:///:memory:"
    setUp = hydro.SimpleHydroRuleTests.setUp
    tearDown = hydro.SimpleHydroRuleTests.tearDown
    hydro_scope = hydro.SimpleHydroRuleTests.hydro_scope
    compile_published = hydro.SimpleHydroRuleTests.compile_published
    preview = hydro.SimpleHydroRuleTests.preview

    def prepare(self, scope=None):
        scope = scope or self.hydro_scope()
        self.engine.adapters = ["hydro_v2.v1"]
        path, publication, job = self.compile_published(scope)
        applied = post_json_with_csrf(self.client, path + "/applications", {
            "job_id": job["id"], "reason": "Preparar operación"})
        self.assertEqual(applied.status_code, 201, applied.text)
        return scope, path, publication, applied.json()

    def admin(self):
        user = self.store.create_user(email=f"admin-{self.token}@rules.test", display_name="Programador",
            role="admin", password_hash=hash_password("test password"))
        login_json_with_csrf(self.client, user["email"], "test password")
        return user

    def schedule(self, scope, **changes):
        response = post_json_with_csrf(self.client, "/api/admin/schedules", {
            "scenario_id": scope["scenario_id"], "case_input_variant_id": scope["variant_id"],
            "display_name": "Hidro diario", "range_start": scope["range_start"] + "+00:00",
            "range_end": scope["range_end"] + "+00:00", "cadence": "daily",
            "next_run_at": "2026-01-01T00:00:00+00:00", **changes})
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()["schedule"]

    def version(self, run):
        response = self.client.get(f"/api/scenario-versions/{run['scenario_version_id']}")
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["scenario_version"]

    def console(self):
        scope = self.hydro_scope()
        document = {"schema_version": "operator_console_config.v1", "public_identity": {"name": "Hidro operativo", "description": ""},
            "parameters": [{"id": "caudal", "pointer": {"asset_id": "hydro_1", "field": "turbine_flow_max_m3s"},
                            "label": "Caudal máximo", "unit": "m3/s", "min": 1, "max": 30, "default": 20}],
            "groups": [], "results": {"kpis": [], "charts": [], "tables": []}}
        response = post_json_with_csrf(self.client, f"/api/scenarios/{scope['scenario_id']}/consoles", {
            "source_variant_id": scope["variant_id"], "document": document})
        self.assertEqual(response.status_code, 201, response.text)
        console = response.json()["operator_console"]
        return {**scope, "variant_id": console["owned_variant"]["id"]}, console, document

    def activate(self, scope, console, document):
        response = put_json_with_csrf(self.client, f"/api/scenarios/{scope['scenario_id']}/consoles/{console['id']}", {
            "expected_revision": console["revision"], "status": "active", "document": document})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["operator_console"]

    def operator(self):
        user = self.store.create_user(email=f"operator-{self.token}@rules.test", display_name="Operador",
            role="external", password_hash=hash_password("test password"))
        self.store.set_external_project_access(project_id=self.project["id"], user_id=user["id"],
            portal_view=False, operate=True, updated_by=self.user["email"])
        login_json_with_csrf(self.client, user["email"], "test password")
        return user

    def test_console_applies_only_authorized_overrides_before_compiling_and_keeps_operator_identity(self):
        with RuleWorker(self.store, OCIExecutor.from_env()):
            scope, console, document = self.console()
            _, _, publication, _ = self.prepare(scope)
            self.activate(scope, console, document)
            operator = self.operator()
            response = put_json_with_csrf(self.client, f"/api/console/{console['id']}/parameters", {
                "parameters": [{"id": "caudal", "value": 4}]})
            self.assertEqual(response.status_code, 200, response.text)
            response = post_json_with_csrf(self.client, f"/api/console/{console['id']}/runs", {
                key: scope[key] for key in ("range_start", "range_end")})
            self.assertEqual(response.status_code, 201, response.text)
            public = response.json()
            for secret in ("construir", "publication_id", "component_rules", "ir_hash"):
                self.assertNotIn(secret, response.text)
            login_json_with_csrf(self.client, self.user["email"], "test password")
            run = self.client.get(f"/api/runs/{public['run']['id']}").json()["run"]
            version = self.version(run)
            block = version["system_case_json"]["component_rules"]
            self.assertEqual(block["applications"][0]["publication_id"], publication["id"])
            self.assertEqual(len(block["rows"]), 2)
            hydro = next(n for n in version["system_case_json"]["nodes"] if n["id"] == "hydro_1")
            self.assertEqual(hydro["turbine_flow_max_m3s"], 4)
            self.assertEqual(run["trigger_type"], "operator_console")
            self.assertEqual(run["triggered_by_user_id"], operator["id"])
            self.assertEqual(run["operator_console_id"], console["id"])
            self.assertEqual(version["generation_metadata"]["kind"], "operator_console")
            self.assertEqual(version["generation_metadata"]["parameter_overrides"], [{"id": "caudal", "value": 4}])

    def test_schedule_recompiles_the_pinned_hydro_rule_for_its_exact_range(self):
        with RuleWorker(self.store, OCIExecutor.from_env()):
            scope, _, publication, _ = self.prepare()
            manual = post_json_with_csrf(self.client,
                f"/api/scenarios/{scope['scenario_id']}/case/variants/{scope['variant_id']}/run",
                {key: scope[key] for key in ("range_start", "range_end")})
            self.assertEqual(manual.status_code, 201, manual.text)
            original = self.version(manual.json())["system_case_json"]["component_rules"]
            admin = self.admin()
            schedule = self.schedule(scope, range_end="2026-01-01T01:00:00+00:00")
            response = post_json_with_csrf(self.client, "/api/admin/schedules/run-due", {
                "now": "2026-01-01T00:00:00+00:00"})
            self.assertEqual(response.status_code, 200, response.text)
            tick = next(t for t in response.json()["ticks"] if t["schedule_id"] == schedule["id"])
            self.assertEqual(tick["status"], "queued", tick)
            run = self.client.get(f"/api/runs/{tick['run_id']}").json()["run"]
            version = self.version(run)
            block = version["system_case_json"]["component_rules"]
            self.assertEqual(len(block["rows"]), 1)
            self.assertEqual(block["rows"][0], original["rows"][0])
            self.assertEqual(block["applications"][0]["publication_id"], publication["id"])
            self.assertEqual(run["trigger_type"], "scheduled")
            self.assertEqual(run["triggered_by_user_id"], admin["id"])
            self.assertEqual(version["generation_metadata"]["automation"]["schedule_tick_id"], tick["id"])
            self.assertNotEqual(block["context_hash"], original["context_hash"])

    def test_internal_preparation_lists_pins_and_refuses_activation_after_a_new_publication(self):
        from tests.test_reg001_rules import PAYLOAD
        from tests.test_reg002_runtime import CODE, PARAMETERS
        with RuleWorker(self.store, OCIExecutor.from_env()):
            scope, console, document = self.console()
            _, path, publication, application = self.prepare(scope)
            url = f"/api/scenarios/{scope['scenario_id']}/consoles/{console['id']}"
            detail = self.client.get(url).json()["operator_console"]
            self.assertEqual(detail["rules"]["items"][0]["publication_id"], publication["id"])
            self.assertEqual(detail["rules"]["items"][0]["application_id"], application["id"])
            self.assertIn(f"variant_id={scope['variant_id']}", detail["rules"]["items"][0]["rule_url"])
            self.assertTrue(detail["rules"]["ready"])
            updated = put_json_with_csrf(self.client, path, {**PAYLOAD, "code": CODE + "\n# siguiente",
                "parameters": PARAMETERS, "expected_revision": 1})
            self.assertEqual(updated.status_code, 200, updated.text)
            self.assertEqual(post_json_with_csrf(self.client, path + "/publications", {"expected_revision": 2}).status_code, 201)
            rejected = put_json_with_csrf(self.client, url, {"expected_revision": console["revision"],
                "status": "active", "document": document})
            self.assertEqual(rejected.status_code, 409, rejected.text)

            self.assertEqual(self.client.get(url).json()["operator_console"]["status"], "draft")
            self.admin()
            rejected = post_json_with_csrf(self.client, "/api/admin/schedules", {
                "scenario_id": scope["scenario_id"], "case_input_variant_id": scope["variant_id"],
                "display_name": "Obsoleta", "range_start": scope["range_start"] + "+00:00",
                "range_end": scope["range_end"] + "+00:00", "cadence": "daily",
                "next_run_at": "2026-01-01T00:00:00+00:00"})
            self.assertEqual(rejected.status_code, 409, rejected.text)

    def test_repeated_scheduler_delivery_keeps_the_same_tick_and_single_run(self):
        from app.schedules import execute_fixed_range_schedule
        from tests.test_ts6_008_schedules import CapturingRunQueue
        with RuleWorker(self.store, OCIExecutor.from_env()):
            scope, _, _, _ = self.prepare()
            self.admin()
            schedule = self.schedule(scope)
            queue = CapturingRunQueue()
            def deliver():
                return execute_fixed_range_schedule(store=self.store, validation_service=self.engine, run_queue=queue,
                    schedule=schedule, now="2026-01-01T00:00:00+00:00")
            first = deliver()
            self.assertEqual(first["status"], "queued", first)
            repeated = deliver()
            self.assertEqual(repeated, first)
            self.assertEqual(queue.enqueued_run_ids, [first["run_id"]])
            ticks = self.client.get("/api/admin/schedules").json()["ticks"]
            self.assertEqual(len([t for t in ticks if t["schedule_id"] == schedule["id"]]), 1)

    def test_missing_runtime_closes_the_public_gate_and_preserves_a_failed_tick(self):
        from app.schedules import execute_fixed_range_schedule
        from tests.test_ts6_008_schedules import CapturingRunQueue
        with RuleWorker(self.store, OCIExecutor.from_env()):
            scope, console, document = self.console()
            self.prepare(scope)
            self.activate(scope, console, document)
            self.admin()
            schedule = self.schedule(scope)
        self.operator()
        shell = self.client.get(f"/api/console/{console['id']}")
        self.assertEqual(shell.status_code, 200, shell.text)
        self.assertFalse(shell.json()["run_gate"]["can_run"])
        self.assertEqual(shell.json()["run_gate"]["reason"], "dependencia_movida")
        refused = post_json_with_csrf(self.client, f"/api/console/{console['id']}/runs", {
            key: scope[key] for key in ("range_start", "range_end")})
        self.assertEqual(refused.status_code, 409, refused.text)
        self.assertNotIn("construir", refused.text)
        review = post_json_with_csrf(self.client, f"/api/console/{console['id']}/request-review")
        self.assertEqual(review.status_code, 200, review.text)
        queue = CapturingRunQueue()
        def deliver():
            return execute_fixed_range_schedule(store=self.store, validation_service=self.engine,
                run_queue=queue, schedule=schedule, now="2026-01-01T00:00:00+00:00")
        failed = deliver()
        self.assertEqual(failed["status"], "failed", failed)
        self.assertEqual(deliver(), failed)
        self.assertEqual(queue.enqueued_run_ids, [])

    def bind_operational_sources(self, scope):
        from app.time_series_catalog import CatalogImportRequest, CatalogSignalMappingRequest, prepare_time_series_catalog_import
        sources = {}
        for key, entity_type, entity_id, value in (
            ("import_price_usd_per_mwh", None, None, 40), ("export_price_usd_per_mwh", None, None, 120),
            ("renewable_available_power_mw", "component:renewable", "solar_1", 0.8),
            ("hydro_inflow_m3s", "component:hydro", "hydro_1", 30)):
            prepared = prepare_time_series_catalog_import(rows=[{"t": f"2026-01-01T0{t}:00:00", "h": "1", "v": str(value)} for t in range(2)],
                request=CatalogImportRequest(set_name=key, version_label="v1", data_kind="real", timezone="UTC",
                    timestamp_column="t", duration_hours_column="h", signal_mappings=[CatalogSignalMappingRequest("v", key)]))
            source = self.store.import_time_series_catalog_set(scenario_id=scope["scenario_id"],
                source={"id": key, "original_filename": "test.csv", "media_type": "text/csv", "checksum": self.token + key}, prepared_import=prepared)
            sources[key] = source
            self.store.upsert_case_time_series_binding(case_input_variant_id=scope["variant_id"], signal_key=key,
                entity_type=entity_type, entity_id=entity_id, time_series_set_id=source["id"])
        return sources

    def test_an_edited_operational_series_recompiles_known_data_and_records_the_copy(self):
        from tests.auth_test_helpers import csrf_headers
        from tests.test_reg001_rules import PAYLOAD
        with RuleWorker(self.store, OCIExecutor.from_env()):
            scope, console, document = self.console()
            scope = {**scope, "range_start": scope["range_start"] + "+00:00", "range_end": scope["range_end"] + "+00:00"}
            sources = self.bind_operational_sources(scope)
            source = sources["renewable_available_power_mw"]
            document["groups"] = [{"id": "solar", "label": "Solar", "granularities": ["full_horizon"], "columns": [{
                "id": "available", "label": "Disponible", "editable": True,
                "signal": {"entity_type": "component:renewable", "entity_id": "solar_1", "signal_key": "renewable_available_power_mw"},
                "source_options": [{"id": "base", "label": "Base", "time_series_set_id": source["id"]}], "default_source_option_id": "base"}]}]
            solar = next(o for o in self.store.list_linkable_objects(project_id=self.project["id"]) if o["object_key"] == "solar_1")
            saved = post_json_with_csrf(self.client, self.root, {**PAYLOAD, "parameters": [], "scenario_id": scope["scenario_id"],
                "aliases": [{"alias": "solar", "object_id": solar["id"]}],
                "code": 'def construir(ctx):\n    for t in ctx.periodos:\n        ctx.restriccion("solar", t, ctx.objeto.potencia[t] <= ctx.objetos.solar.disponibilidad[t])'}).json()
            path = self.root + "/" + saved["id"]
            publication = post_json_with_csrf(self.client, path + "/publications", {"expected_revision": 1}).json()
            job = self.preview(scope, path, publication)
            self.assertEqual(job["status"], "succeeded", job)
            applied = post_json_with_csrf(self.client, path + "/applications", {"job_id": job["id"], "reason": "Usar disponibilidad operativa"})
            self.assertEqual(applied.status_code, 201, applied.text)
            self.engine.adapters = ["hydro_v2.v1", "electric_system.v1"]
            self.engine.capabilities = ["affine_hydraulic.v1"]
            self.activate(scope, console, document)
            self.operator()
            group = f"/api/console/{console['id']}/groups/solar"
            params = {"range_start": scope["range_start"], "range_end": scope["range_end"], "granularity": "full_horizon"}
            values = self.client.get(group + "/values", params={"start": scope["range_start"], "end": scope["range_end"], "granularity": "full_horizon"})
            self.assertEqual(values.status_code, 200, values.text)
            lease = post_json_with_csrf(self.client, group + "/lease").json()["lease"]
            edited = self.client.put(group + "/values", json={**params, "lease_token": lease["token"],
                "cells": [{"column_id": "available", "row_index": 0, "value": 0.4}], "note": "Ajuste operativo"},
                headers={**csrf_headers(self.client), "If-Match": values.headers["etag"]})
            self.assertEqual(edited.status_code, 200, edited.text)
            response = post_json_with_csrf(self.client, f"/api/console/{console['id']}/runs", {
                key: scope[key] for key in ("range_start", "range_end")})
            self.assertEqual(response.status_code, 201, response.text)
            login_json_with_csrf(self.client, self.user["email"], "test password")
            run = self.client.get(f"/api/runs/{response.json()['run']['id']}").json()["run"]
            version = self.version(run)
            block = version["system_case_json"]["component_rules"]
            self.assertEqual([row["constant"] for row in block["rows"]], [-0.4, -0.8])
            self.assertEqual(block["applications"][0]["publication_id"], publication["id"])
            lineage = version["generation_metadata"]
            binding = next(b for b in lineage["series_bindings"] if b["signal_key"] == "renewable_available_power_mw")
            self.assertNotEqual(binding["time_series_set_id"], source["id"])
            self.assertEqual(lineage["operational_series_copies"][0]["origin_set_id"], source["id"])
            internal = self.client.get(f"/api/scenarios/{scope['scenario_id']}/consoles/{console['id']}").json()["operator_console"]
            self.assertTrue(internal["rules"]["ready"])
            self.activate(scope, internal, document)

    def test_runtime_loss_during_validation_leaves_no_partial_run_or_version(self):
        with RuleWorker(self.store, OCIExecutor.from_env()) as worker:
            scope, console, document = self.console()
            self.prepare(scope)
            self.activate(scope, console, document)
            before = self.client.get(f"/api/scenarios/{scope['scenario_id']}/versions").json()
            self.engine.after_validation = lambda: worker.__exit__()
            self.operator()
            response = post_json_with_csrf(self.client, f"/api/console/{console['id']}/runs", {
                key: scope[key] for key in ("range_start", "range_end")})
            self.assertEqual(response.status_code, 409, response.text)
            self.assertNotIn("construir", response.text)
            self.assertEqual(self.client.get(f"/api/console/{console['id']}/runs").json()["history"], [])
            login_json_with_csrf(self.client, self.user["email"], "test password")
            self.assertEqual(self.client.get(f"/api/scenarios/{scope['scenario_id']}/versions").json(), before)

    def test_revocation_during_compilation_prevents_commit_and_external_payloads_cannot_edit_rules(self):
        with RuleWorker(self.store, OCIExecutor.from_env()):
            scope, console, document = self.console()
            self.prepare(scope)
            self.activate(scope, console, document)
            operator = self.operator()
            url = f"/api/console/{console['id']}/runs"
            body = {key: scope[key] for key in ("range_start", "range_end")}
            for key, value in (("code", "print(1)"), ("aliases", []), ("publication_id", "new"), ("parameters", {"limite": 99})):
                self.assertEqual(post_json_with_csrf(self.client, url, {**body, key: value}).status_code, 422)
            self.assertEqual(self.client.get(self.root).status_code, 404)
            self.engine.after_validation = lambda: self.store.revoke_external_project_access(
                project_id=self.project["id"], user_id=operator["id"], updated_by=self.user["email"])
            response = post_json_with_csrf(self.client, url, body)
            self.assertEqual(response.status_code, 409, response.text)
            login_json_with_csrf(self.client, self.user["email"], "test password")
            self.assertEqual(self.client.get(f"/api/console/{console['id']}/runs").json()["history"], [])

    def test_rolling_range_rebuilds_budget_windows_and_a_retry_uses_the_frozen_snapshot(self):
        from tests.test_reg006_runtime import CODE, POLICY
        from tests.test_reg001_rules import PAYLOAD
        with RuleWorker(self.store, OCIExecutor.from_env()):
            scope = self.hydro_scope()
            self.engine.capabilities = ["affine_budget.v1"]
            self.engine.adapters = ["hydro_v2.v1"]
            saved = post_json_with_csrf(self.client, self.root, {**PAYLOAD, "code": CODE, "windows": POLICY,
                "parameters": [{"name": "energia", "type": "number", "unit": "mwh", "value": 1}]}).json()
            path = self.root + "/" + saved["id"]
            publication = post_json_with_csrf(self.client, path + "/publications", {"expected_revision": 1}).json()
            job = self.preview(scope, path, publication)
            self.assertEqual(job["status"], "succeeded", job)
            self.assertEqual(post_json_with_csrf(self.client, path + "/applications", {"job_id": job["id"], "reason": "Presupuesto operativo"}).status_code, 201)
            self.admin()
            schedule = self.schedule(scope, range_mode="rolling", rolling_start_offset_hours=0, rolling_duration_hours=1)
            response = post_json_with_csrf(self.client, "/api/admin/schedules/run-due", {"now": "2026-01-01T00:00:00+00:00"})
            tick = next(t for t in response.json()["ticks"] if t["schedule_id"] == schedule["id"])
            self.assertEqual(tick["status"], "queued", tick)
            original = self.version(tick)
            row = original["system_case_json"]["component_rules"]["rows"][0]
            self.assertEqual(row["window"]["duration_hours"], 1)
            self.assertEqual(row["window"]["periods"], [0])
            # The next day has no exact source coverage; no current source is adopted.
            missing = post_json_with_csrf(self.client, "/api/admin/schedules/run-due", {"now": "2026-01-02T00:00:00+00:00"}).json()["ticks"]
            failed = next(t for t in missing if t["schedule_id"] == schedule["id"])
            self.assertEqual(failed["status"], "failed")
            self.assertIsNone(failed["run_id"])
        retry = post_json_with_csrf(self.client, f"/api/scenario-versions/{tick['scenario_version_id']}/runs")
        self.assertEqual(retry.status_code, 201, retry.text)
        self.assertEqual(retry.json()["scenario_version_id"], tick["scenario_version_id"])
        self.assertEqual(self.version(retry.json()), original)

    def test_a_concurrent_schedule_change_blocks_commit_and_keeps_the_new_fire_time(self):
        with RuleWorker(self.store, OCIExecutor.from_env()):
            scope, _, _, _ = self.prepare()
            self.admin()
            schedule = self.schedule(scope)
            self.engine.after_validation = lambda: self.store.advance_run_schedule(schedule["id"],
                next_run_at="2030-01-01T00:00:00+00:00", last_fired_at="2026-01-01T00:00:00+00:00")
            response = post_json_with_csrf(self.client, "/api/admin/schedules/run-due", {"now": "2026-01-01T00:00:00+00:00"})
            tick = next(t for t in response.json()["ticks"] if t["schedule_id"] == schedule["id"])
            self.assertEqual(tick["status"], "failed", tick)
            self.assertIsNone(tick["run_id"])
            current = next(s for s in self.client.get("/api/admin/schedules").json()["schedules"] if s["id"] == schedule["id"])
            self.assertEqual(current["next_run_at"], "2030-01-01T00:00:00+00:00")

    def test_operations_without_rules_keep_working_when_a_sibling_variant_has_rules(self):
        with RuleWorker(self.store, OCIExecutor.from_env()):
            scope, console, document = self.console()
            default = self.client.get(f"/api/scenarios/{scope['scenario_id']}/case/default-variant").json()["variant"]
            self.prepare({**scope, "variant_id": default["id"]})
            self.bind_operational_sources(scope)
            scope = {**scope, "range_start": scope["range_start"] + "+00:00", "range_end": scope["range_end"] + "+00:00"}
            self.activate(scope, console, document)
        self.operator()
        response = post_json_with_csrf(self.client, f"/api/console/{console['id']}/runs", {
            key: scope[key] for key in ("range_start", "range_end")})
        self.assertEqual(response.status_code, 201, response.text)
        self.admin()
        schedule = self.schedule({**scope, "range_start": scope["range_start"].removesuffix("+00:00"), "range_end": scope["range_end"].removesuffix("+00:00")})
        response = post_json_with_csrf(self.client, "/api/admin/schedules/run-due", {"now": "2026-01-01T00:00:00+00:00"})
        tick = next(t for t in response.json()["ticks"] if t["schedule_id"] == schedule["id"])
        self.assertEqual(tick["status"], "queued", tick)
        self.assertNotIn("component_rules", self.version(tick)["system_case_json"])



@unittest.skipUnless(os.environ.get("POSTGRES_TEST_DATABASE_URL"), "isolated PostgreSQL required")
class PostgresOperationalRuleTests(OperationalRuleTests):
    database_url = os.environ.get("POSTGRES_TEST_DATABASE_URL", "sqlite:///:memory:")
