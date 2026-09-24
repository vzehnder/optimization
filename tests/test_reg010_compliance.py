"""Compliance is observed through authenticated HTTP over frozen solver artifacts."""
import csv
import json
import os
import unittest
from pathlib import Path

from tests import test_reg002_rules as baseline


class ComplianceApiTests(unittest.TestCase):
    database_url = "sqlite:///:memory:"
    setUp = baseline.RuleApplicationApiTests.setUp
    tearDown = baseline.RuleApplicationApiTests.tearDown

    def frozen_run(self, rows=None, values=None, termination="OPTIMAL", failure=None, objects=None, application_override=None):
        from app.component_rules import digest
        from app.rule_runtime import SDK_VERSION
        document = json.loads(Path("tests/fixtures/reg002_hydraulic.json").read_text())
        self.rule_id = "frozen-instance"
        self.application = {"id": "applied-1", "rule_id": self.rule_id, "publication_id": "revision-1",
                            "revision": 2, "object_id": self.obj["id"], "name": "Límite histórico",
                            "code": "# frozen code", "parameters": [], "aliases": [], "runtime": {"sdk": SDK_VERSION}}
        self.application.update(application_override or {})
        self.object = {"id": self.obj["id"], "kind": "hydraulic_unit", "unit_key": "unit", "display_name": "Unidad histórica"}
        if rows is None:
            rows = [self.row("máximo", t, -5) for t in range(4)]
        document["component_rules"] = {"version": "affine_hydraulic.v1", "grid": document["time_series"],
            "objects": objects or [self.object], "applications": [self.application], "rows": rows, "ir_hash": "frozen-ir"}
        scenario = self.store.create_scenario(project_id=self.project["id"], name="Cumplimiento")
        self.version = self.store.create_scenario_version(scenario_id=scenario["id"], system_case_json=document, validation_payload={"status": "ok"}, generation_metadata={"component_rules_hash": digest(document["component_rules"])})
        self.run = self.store.create_run(scenario_version_id=self.version["id"])
        self.url = f"/api/runs/{self.run['id']}/rule-compliance"
        self.output = Path(self.temporary.name) / str(self.run["id"])
        self.output.mkdir()
        self.store.mark_run_running(self.run["id"], workspace_path=str(self.output), input_snapshot_path=str(self.output / "input.json"))
        if failure:
            self.store.mark_run_failed(self.run["id"], exit_code=1, stdout="", stderr="", error_payload=failure)
            return
        self.summary = {"termination_status": termination, "solver_status": termination}
        self.write_summary()
        self.values = values or [5, 3, 5, 4]
        self.write_values()
        self.store.mark_run_succeeded(self.run["id"], exit_code=0, stdout="", stderr="", success_payload={"termination_status": termination}, output_dir=str(self.output), summary_path=str(self.output / "summary.json"))

    def row(self, name, period, constant, relation="<=", coefficient=1, unit="m3_per_s"):
        return {"name": name, "period": period, "line": 3, "relation": relation, "unit": unit,
                "constant": constant, "terms": [{"object_id": self.obj["id"], "variable": "caudal",
                "period": period, "coefficient": coefficient, "unit": "dimensionless"}],
                "application_id": "applied-1", "revision_id": "revision-1"}

    def write_summary(self):
        path = self.output / "summary.json"
        path.write_text(json.dumps(self.summary), encoding="utf-8")
        self.store.register_run_artifact(run_id=self.run["id"], artifact_type="summary_json", path=str(path), display_name=path.name, media_type="application/json")

    def write_values(self):
        path = self.output / "asset_dispatch.csv"
        with path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=["timestamp", "asset_type", "asset_id", "hydro_turbine_flow_m3s"])
            writer.writeheader()
            for t, value in enumerate(self.values):
                writer.writerow({"timestamp": f"2026-01-01T0{t}:00:00", "asset_type": "hydraulic_unit", "asset_id": "unit", "hydro_turbine_flow_m3s": value})
        self.store.register_run_artifact(run_id=self.run["id"], artifact_type="asset_dispatch_csv", path=str(path), display_name=path.name, media_type="text/csv")

    def report(self, query=""):
        response = self.client.get(self.url + query)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_binding_and_slack_limits_are_evaluated_from_frozen_results(self):
        self.frozen_run()
        report = self.report()
        self.assertEqual(report["solution_state"], "optimal")
        self.assertEqual(report["counts"], {"total": 4, "evaluated": 4, "satisfied": 4, "violated": 0, "unavailable": 0})
        self.assertEqual([(r["lhs"], r["rhs"], r["margin"], r["residual"]) for r in report["rows"]],
                         [(5, 5, 0, None), (3, 5, 2, None), (5, 5, 0, None), (4, 5, 1, None)])
        row = report["rows"][0]
        self.assertEqual((row["rule_id"], row["revision_id"], row["application_id"], row["unit"]),
                         ("frozen-instance", "revision-1", "applied-1", "m3_per_s"))
        self.assertEqual(row["components"][0]["display_name"], "Unidad histórica")
        self.assertEqual(row["absolute_tolerance"], 1e-7)
        self.assertEqual(row["relative_tolerance"], 1e-7)
        self.assertIn("frozen-instance", row["rule_url"])

    def test_affine_relations_keep_sign_units_window_and_scaled_tolerances(self):
        budget = self.row("agua", 3, -61200, coefficient=3600, unit="m3")
        budget["terms"] = [{**budget["terms"][0], "period": t, "unit": "s"} for t in range(4)]
        budget["window"] = {"key": "horizon", "periods": [0, 1, 2, 3], "timezone": "UTC"}
        ramp = self.row("rampa", 1, 2, "==")
        ramp["terms"].append({**ramp["terms"][0], "period": 0, "coefficient": -1})
        self.frozen_run(rows=[self.row("mínimo", 0, -4, ">="),
                              self.row("igualdad", 2, -5.0000004, "=="),
                              self.row("violación", 3, -3, "=="), budget, ramp])
        report = self.report()
        self.assertEqual([(r["margin"], r["status"]) for r in report["rows"]],
                         [(1, "satisfied"), (None, "satisfied"), (None, "violated"), (0, "satisfied"), (None, "satisfied")])
        self.assertAlmostEqual(report["rows"][1]["residual"], -0.0000004)
        self.assertEqual(report["rows"][2]["residual"], 1)
        self.assertEqual((report["rows"][3]["lhs"], report["rows"][3]["unit"], report["rows"][3]["window"]), (61200, "m3", budget["window"]))
        self.assertAlmostEqual(report["rows"][3]["tolerance"], 0.0061201)
        self.assertEqual(report["rows"][4]["affected_periods"], [0, 1])

    def test_failed_runs_do_not_invent_primal_values_or_a_unique_infeasibility_cause(self):
        self.frozen_run(failure={"status": "error", "message": "optimization finished without primal values; termination_status=INFEASIBLE"})
        report = self.report()
        self.assertEqual(report["solution_state"], "no_primal")
        self.assertEqual(report["termination_status"], "INFEASIBLE")
        self.assertEqual(report["counts"]["unavailable"], 4)
        self.assertTrue(all(r["lhs"] is None and r["margin"] is None and r["residual"] is None and r["status"] == "unavailable" for r in report["rows"]))
        self.assertEqual(report["diagnostics"][0]["category"], "infeasible")
        self.assertIn("causa única", report["diagnostics"][0]["message"])
        self.assertTrue(report["diagnostics"][0]["action"])

    def test_time_limit_with_feasible_values_is_distinct_from_optimal_and_missing_values(self):
        self.frozen_run(termination="TIME_LIMIT")
        self.summary["primal_status"] = "FEASIBLE_POINT"
        self.write_summary()
        report = self.report()
        self.assertEqual(report["solution_state"], "feasible")
        self.assertEqual(report["counts"]["evaluated"], 4)
        self.assertEqual(report["diagnostics"][0]["category"], "timeout")
        self.summary["primal_status"] = "NO_SOLUTION"
        self.write_summary()
        report = self.report()
        self.assertEqual(report["solution_state"], "no_primal")
        self.assertEqual(report["counts"]["evaluated"], 0)

    def test_nearly_feasible_values_are_not_reported_as_certified_optimal(self):
        self.frozen_run()
        self.summary["primal_status"] = "NEARLY_FEASIBLE_POINT"
        self.write_summary()
        self.assertEqual(self.report()["solution_state"], "primal_available")

    def test_pagination_and_samples_never_limit_the_complete_compliance_check(self):
        self.frozen_run(rows=[self.row(f"fila-{i}", i % 4, -5 if i < 136 else -2) for i in range(137)])
        report = self.report("?limit=25")
        self.assertEqual(report["counts"]["total"], 137)
        self.assertEqual(report["counts"]["violated"], 1)
        self.assertEqual(len(report["rows"]), 25)
        self.assertEqual(report["page"], {"offset": 0, "limit": 25, "total": 137, "next_offset": 25})
        self.assertEqual(len(report["samples"]), 100)
        indices = []
        for offset in range(0, 137, 25):
            page = self.report(f"?offset={offset}&limit=25")
            indices.extend(r["row_index"] for r in page["rows"])
        self.assertEqual(indices, list(range(137)))
        filtered = self.report("?rule_id=frozen-instance&period=1&limit=100")
        self.assertEqual(filtered["page"]["total"], 34)
        self.assertEqual({r["period"] for r in filtered["rows"]}, {1})
        self.assertEqual(self.report("?rule_id=another")["page"]["total"], 0)
        self.assertEqual(self.client.get(self.url + "?limit=0").status_code, 422)

    def test_missing_and_nonfinite_solver_cells_remain_unavailable_without_hiding_other_rows(self):
        self.frozen_run(values=[5, "", "NaN", "Inf"])
        report = self.report()
        self.assertEqual(report["counts"], {"total": 4, "evaluated": 1, "satisfied": 1, "violated": 0, "unavailable": 3})
        self.assertTrue(all(r["lhs"] is None for r in report["rows"][1:]))
        self.assertEqual(report["diagnostics"][0]["category"], "result_data")
        (self.output / "asset_dispatch.csv").unlink()
        self.assertEqual(self.report()["counts"]["unavailable"], 4)

    def test_duplicate_solver_cells_are_ambiguous_and_are_not_silently_selected(self):
        self.frozen_run()
        with (self.output / "asset_dispatch.csv").open("a", encoding="utf-8") as file:
            file.write("2026-01-01T00:00:00Z,hydraulic_unit,unit,2\n")
        report = self.report()
        self.assertIsNone(report["rows"][0]["lhs"])
        self.assertEqual(report["counts"]["evaluated"], 3)

    def test_power_storage_and_spill_use_frozen_object_identity_and_the_correct_columns(self):
        power = self.row("potencia", 0, -3.75, "==", unit="mw")
        power["terms"][0]["variable"] = "potencia"
        storage = self.row("volumen", 0, -10, "<=", unit="hm3")
        storage["terms"][0].update(object_id=987654, variable="almacenamiento")
        spill = self.row("vertimiento", 0, -2, ">=")
        spill["terms"][0].update(object_id=987654, variable="vertimiento")
        self.frozen_run(rows=[power, storage, spill], objects=[
            {"id": self.obj["id"], "kind": "hydraulic_unit", "unit_key": "unit", "display_name": "Unidad antigua"},
            {"id": 987654, "kind": "hydraulic_node", "node_key": "reservoir", "display_name": "Embalse antiguo"}])
        (self.output / "asset_dispatch.csv").write_text(
            "timestamp,asset_type,asset_id,hydro_power_mw,hydro_storage_hm3,hydro_spill_flow_m3s\n"
            "2026-01-01T00:00:00Z,hydraulic_unit,unit,3.75,0,0\n"
            "2025-12-31T21:00:00-03:00,hydraulic_reservoir,reservoir,0,9.9,2\n", encoding="utf-8")
        report = self.report()
        self.assertEqual([r["lhs"] for r in report["rows"]], [3.75, 9.9, 2])
        self.assertEqual(report["counts"]["satisfied"], 3)

    def test_failure_categories_offer_specific_actions_instead_of_claiming_infeasibility(self):
        for code, category in [("RULE_CODE_ERROR", "code_data"), ("RULE_INPUT_INVALID", "code_data"),
                               ("RULE_CAPABILITY_UNSUPPORTED", "capacity"), ("RULE_MEMORY_LIMIT", "capacity"),
                               ("RULE_TIMEOUT", "timeout"), ("RULE_CANCELLED", "cancelled"),
                               ("RULE_INTERRUPTED", "cancelled"), ("SOLVE_ERROR", "solve")]:
            with self.subTest(code=code):
                self.frozen_run(failure={"code": code, "message": "Fallo localizado", "period": 1, "application_id": "applied-1"})
                diagnostic = self.report()["diagnostics"][0]
                self.assertEqual(diagnostic["category"], category)
                self.assertEqual(diagnostic["code"], code)
                self.assertEqual(diagnostic["period"], 1)
                self.assertIn("frozen-instance", diagnostic["rule_url"])
                self.assertTrue(diagnostic["action"])

    def test_simple_contradiction_identifies_both_frozen_bounds_and_their_period(self):
        self.frozen_run(rows=[self.row("máximo", 1, -2), self.row("mínimo", 1, -4, ">=")],
                        failure={"code": "RUN_VALIDATION_ERROR", "message": "Contradictory bounds"})
        report = self.report()
        conflict = next(d for d in report["diagnostics"] if d["category"] == "bounds_conflict")
        self.assertEqual({r["name"] for r in conflict["conflicts"]}, {"máximo", "mínimo"})
        self.assertEqual({r["period"] for r in conflict["conflicts"]}, {1})
        self.assertTrue(all("frozen-instance" in r["rule_url"] for r in conflict["conflicts"]))
        self.assertEqual(report["counts"]["evaluated"], 0)

    def test_report_requires_internal_authentication_and_is_not_added_to_result_payloads(self):
        from app.auth import hash_password
        from tests.auth_test_helpers import login_json_with_csrf
        self.frozen_run()
        # The generic result contract is shared with dashboards; compliance has its own internal route.
        (self.output / "dispatch.csv").write_text("timestamp,value\n2026-01-01T00:00:00,1\n", encoding="utf-8")
        self.store.register_run_artifact(run_id=self.run["id"], artifact_type="dispatch_csv", path=str(self.output / "dispatch.csv"), display_name="dispatch.csv", media_type="text/csv")
        result = self.client.get(f"/api/runs/{self.run['id']}/results")
        self.assertEqual(result.status_code, 200, result.text)
        for forbidden in ("frozen-instance", "frozen code", "applied-1", "rule_compliance", "frozen-ir"):
            self.assertNotIn(forbidden, result.text)
        for role in ("external",):
            user = self.store.create_user(email=f"{self.token}-{role}@rules.test", display_name=role, role=role, password_hash=hash_password("test password"))
            self.client.cookies.clear()
            login_json_with_csrf(self.client, user["email"], "test password")
            response = self.client.get(self.url)
            self.assertIn(response.status_code, (403, 404))
            self.assertNotIn("frozen-instance", response.text)
        self.client.cookies.clear()
        self.assertEqual(self.client.get(self.url).status_code, 401)

    def test_solver_process_timeout_keeps_a_stable_category_in_the_run_report(self):
        import subprocess
        from app.runner import JuliaRunExecutor
        from tests.test_manual_runs import AcceptingRunValidationService
        self.frozen_run(failure={"message": "pending retry"})
        def timeout(*args, **kwargs):
            raise subprocess.TimeoutExpired("julia", 1)
        class CapableRuleEngine(AcceptingRunValidationService):
            def validate_file(self, path):
                result = super().validate_file(path)
                result.payload["component_rule_versions"] = ["affine_hydraulic.v1"]
                return result
        JuliaRunExecutor(store=self.store, artifact_root=self.temporary.name, runner=timeout,
                         validation_service=CapableRuleEngine(), timeout_seconds=1).execute(self.run["id"])
        diagnostic = self.report()["diagnostics"][0]
        self.assertEqual(diagnostic["category"], "timeout")
        self.assertEqual(diagnostic["code"], "RUN_SOLVER_TIMEOUT")

    def test_validation_failure_retains_its_stage_instead_of_becoming_a_solve_error(self):
        from app.runner import JuliaRunExecutor
        from app.validation import ValidationResult
        self.frozen_run(failure={"message": "pending retry"})
        class RejectingEngine:
            def validate_file(self, path):
                return ValidationResult(ok=False, phase="julia", message="Invalid input data", payload={"status": "error"})
        JuliaRunExecutor(store=self.store, artifact_root=self.temporary.name,
                         validation_service=RejectingEngine()).execute(self.run["id"])
        diagnostic = self.report()["diagnostics"][0]
        self.assertEqual(diagnostic["category"], "code_data")
        self.assertEqual(diagnostic["code"], "RUN_VALIDATION_ERROR")

    def test_validation_process_timeout_is_not_reported_as_invalid_python(self):
        import subprocess
        from app.runner import JuliaRunExecutor
        from app.validation import JuliaValidationService
        self.frozen_run(failure={"message": "pending retry"})
        def timeout(*args, **kwargs):
            raise subprocess.TimeoutExpired("julia", 1)
        JuliaRunExecutor(store=self.store, artifact_root=self.temporary.name,
                         validation_service=JuliaValidationService(runner=timeout)).execute(self.run["id"])
        diagnostic = self.report()["diagnostics"][0]
        self.assertEqual((diagnostic["category"], diagnostic["code"]), ("timeout", "RUN_VALIDATION_TIMEOUT"))

    def test_rebuilding_after_editing_the_current_rule_preserves_definition_and_instance_provenance(self):
        from tests.test_reg001_rules import PAYLOAD
        from tests.auth_test_helpers import post_json_with_csrf, put_json_with_csrf
        rule = post_json_with_csrf(self.client, self.root, PAYLOAD).json()
        self.frozen_run(application_override={"rule_id": rule["id"], "template": {"rule_id": "shared-definition"}, "revision": 3})
        before = self.report()
        row = before["rows"][0]
        self.assertEqual((row["definition_id"], row["instance_revision"]), ("shared-definition", 3))
        self.assertEqual(row["terms"][0]["coefficient"], 1)
        self.assertEqual(row["constant"], -5)
        edited = put_json_with_csrf(self.client, self.root + "/" + rule["id"], {**PAYLOAD, "expected_revision": 1, "name": "Regla actual distinta", "code": "def construir(ctx):\n    return 0"})
        self.assertEqual(edited.status_code, 200, edited.text)
        self.assertEqual(self.report(), before)

    @unittest.skipUnless(os.environ.get("RULE_RUNTIME_IMAGE"), "real OCI required")
    def test_compilation_failure_has_a_stable_category_and_corrective_action(self):
        import time
        from app.rule_runtime import OCIExecutor
        from app.rule_worker import RuleWorker
        from tests.test_reg001_rules import PAYLOAD
        from tests.auth_test_helpers import post_json_with_csrf
        with RuleWorker(self.store, OCIExecutor.from_env()):
            rule = post_json_with_csrf(self.client, self.root, {**PAYLOAD, "code": "def construir(ctx):\n    return 1 / 0"}).json()
            path = self.root + "/" + rule["id"] + "/tests"
            response = post_json_with_csrf(self.client, path, {"expected_revision": 1})
            self.assertEqual(response.status_code, 202, response.text)
            job = response.json()
            deadline = time.monotonic() + 20
            while job["status"] in {"queued", "running"} and time.monotonic() < deadline:
                time.sleep(.05)
                job = self.client.get(path + "/" + job["id"]).json()
            self.assertEqual(job["status"], "failed", job)
            self.assertEqual(job["diagnostic"]["category"], "code_data")
            self.assertIn("Corregir", job["diagnostic"]["action"])

    @unittest.skipUnless(os.environ.get("RULE_RUNTIME_IMAGE"), "real OCI required")
    def test_combined_contradictions_return_links_before_a_run_is_queued(self):
        from app.rule_runtime import OCIExecutor
        from app.rule_worker import RuleWorker
        from tests.test_reg002_runtime import CODE
        from tests.auth_test_helpers import post_json_with_csrf
        scope = baseline.RuleApplicationApiTests.hydraulic_scope(self)
        self.engine.capabilities = ["affine_flow.v1", "affine_hydraulic.v1"]
        with RuleWorker(self.store, OCIExecutor.from_env()):
            for code in (CODE.replace("ctx.parametros.limite", "ctx.parametros.limite * 0.4"),
                         CODE.replace('"maximo"', '"minimo"').replace("<=", ">=").replace("ctx.parametros.limite", "ctx.parametros.limite * 0.8")):
                path, _, job = baseline.RuleApplicationApiTests.compile_published(self, scope, code)
                applied = post_json_with_csrf(self.client, path + "/applications", {"job_id": job["id"], "reason": "Cota independiente"})
                self.assertEqual(applied.status_code, 201, applied.text)
        response = post_json_with_csrf(self.client, f"/api/scenarios/{scope['scenario_id']}/case/variants/{scope['variant_id']}/run",
                                       {"range_start": scope["range_start"], "range_end": scope["range_end"]})
        self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual(response.json()["detail"]["code"], "RULE_BOUNDS_CONFLICT")
        self.assertEqual({c["name"] for c in response.json()["detail"]["conflicts"]}, {"maximo", "minimo"})
        self.assertTrue(all(c["rule_url"].startswith("/react/projects/") for c in response.json()["detail"]["conflicts"]))
        self.assertEqual(self.client.get(f"/api/scenarios/{scope['scenario_id']}/runs").json()["runs"], [])


@unittest.skipUnless(os.environ.get("POSTGRES_TEST_DATABASE_URL"), "isolated PostgreSQL required")
class CompliancePostgresTests(ComplianceApiTests):
    database_url = os.environ.get("POSTGRES_TEST_DATABASE_URL", "sqlite:///:memory:")
