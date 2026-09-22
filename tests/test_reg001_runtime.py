"""Real OCI contract tests. Never replace these with mocked execution."""
import os
import threading
import time
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor

from tests.test_reg001_rules import FORMULA, PAYLOAD


@unittest.skipUnless(os.environ.get("RULE_RUNTIME_IMAGE"), "pinned OCI image required")
class RuleRuntimeTests(unittest.TestCase):
    def test_real_python_computes_typed_flow_and_reports_its_runtime(self):
        from app.rule_runtime import OCIExecutor
        executor = OCIExecutor.from_env()
        result = executor.execute(
            {"code": FORMULA, "parameters": PAYLOAD["parameters"], "object": {"id": 1, "key": "u1"}},
            uuid.uuid4().hex, threading.Event(),
        )
        self.assertEqual(result["status"], "succeeded", result)
        self.assertEqual(result["output"], {"value": 60.0, "unit": "m3_per_s"})
        self.assertEqual(result["runtime"]["sdk"], "reg-003.1")
        self.assertRegex(result["runtime"]["python"], r"^3\.12\.")

    def test_excessive_logs_are_bounded_and_reported_as_a_limit_error(self):
        from app.rule_runtime import OCIExecutor
        result = OCIExecutor.from_env().execute(
            {"code": "def construir(ctx):\n    for i in range(1000):\n        print('x' * 1000)\n    return ctx.parametros.capacidad\n",
             "parameters": PAYLOAD["parameters"], "object": {"id": 1}}, uuid.uuid4().hex, threading.Event(),
        )
        self.assertEqual(result["status"], "failed", result)
        self.assertEqual(result["error"]["code"], "RULE_LOG_LIMIT")
        self.assertEqual(result["error"]["line"], 3)

    def test_invalid_or_disallowed_python_fails_with_bounded_line_errors(self):
        from app.rule_runtime import OCIExecutor
        for code, line in [
            ("def construir(ctx)\n    return 1", 1),
            ("import os\ndef construir(ctx):\n    return ctx.parametros.capacidad", 1),
            ("def construir(ctx):\n    return ctx.parametros.capacidad * float('inf')", 2),
            ("def construir(ctx):\n    ctx.objeto.id = 4\n    return ctx.parametros.capacidad", 2),
            ("def construir(ctx):\n    return ctx.objeto.__class__", 2),
        ]:
            with self.subTest(code=code):
                result = OCIExecutor.from_env().execute({"code": code, "parameters": PAYLOAD["parameters"], "object": {"id": 1}}, uuid.uuid4().hex, threading.Event())
                self.assertEqual(result["status"], "failed", result)
                self.assertEqual(result["error"]["line"], line, result)
                self.assertLessEqual(len(result["error"]["message"]), 1000)

    def test_infinite_loop_times_out_and_leaves_no_container(self):
        from app.rule_runtime import OCIExecutor
        executor = OCIExecutor.from_env()
        job_id = uuid.uuid4().hex
        started = time.monotonic()
        result = executor.execute({"code": "def construir(ctx):\n    while True: pass", "parameters": [], "object": {"id": 1}}, job_id, threading.Event())
        self.assertEqual(result["error"]["code"], "RULE_TIMEOUT", result)
        self.assertLess(time.monotonic() - started, 20)
        self.assertEqual(executor.control("ps", "-aq", "--filter", f"name=^/component-rule-{job_id}$"), "")

    def test_running_container_has_the_required_os_isolation_and_quotas(self):
        import json
        from app.rule_runtime import OCIExecutor
        executor = OCIExecutor.from_env()
        job_id, cancel = uuid.uuid4().hex, threading.Event()
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(executor.execute, {"code": "def construir(ctx):\n    while True: pass", "parameters": [], "object": {}}, job_id, cancel)
            try:
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline:
                    if executor.control("ps", "-q", "--filter", f"name=^/component-rule-{job_id}$"):
                        break
                    time.sleep(0.05)
                container = json.loads(executor.control("inspect", f"component-rule-{job_id}"))[0]
                host = container["HostConfig"]
                self.assertEqual(container["Config"]["User"], "65532:65532")
                self.assertEqual(host["NetworkMode"], "none")
                self.assertTrue(host["ReadonlyRootfs"])
                self.assertFalse(host["Privileged"])
                self.assertEqual(host["CapDrop"], ["ALL"])
                self.assertIn("no-new-privileges", host["SecurityOpt"])
                self.assertNotIn("seccomp=unconfined", host["SecurityOpt"])
                self.assertEqual((host["NanoCpus"], host["Memory"], host["MemorySwap"], host["PidsLimit"]), (1_000_000_000, 536870912, 536870912, 32))
                self.assertFalse(host["Binds"])
                self.assertEqual(container["Mounts"], [])
            finally:
                cancel.set()
                future.result(timeout=20)

    def test_memory_exhaustion_ends_the_sandbox_with_a_bounded_error(self):
        from app.rule_runtime import OCIExecutor
        executor = OCIExecutor.from_env()
        job_id = uuid.uuid4().hex
        result = executor.execute({"code": "def construir(ctx):\n    data = [0] * 100000000\n    return ctx.parametros.capacidad", "parameters": PAYLOAD["parameters"], "object": {}}, job_id, threading.Event())
        self.assertEqual(result["status"], "failed", result)
        self.assertEqual(result["error"]["code"], "RULE_MEMORY_LIMIT", result)
        self.assertEqual(executor.control("ps", "-aq", "--filter", f"name=^/component-rule-{job_id}$"), "")
