import json
import subprocess
import tempfile
import threading
import time
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from app.persistence import AnalystStore
from app.runner import JuliaRunExecutor, LocalRunQueue
from app.validation import ValidationResult


REPO_ROOT = Path(__file__).resolve().parents[1]


class StubValidationService:
    def __init__(self):
        self.candidates = []

    def validate_text(self, candidate_text):
        self.candidates.append(candidate_text)
        return ValidationResult(
            ok=True,
            phase="julia",
            message="Validation succeeded",
            payload={"status": "ok", "case_name": "stub_case", "schema_version": "bess_system_dispatch.v1"},
        )


class RecordingRunQueue:
    def __init__(self):
        self.enqueued_run_ids = []

    def enqueue(self, run_id):
        self.enqueued_run_ids.append(run_id)

    def stop(self):
        pass


class AcceptingRunValidationService:
    def validate_file(self, candidate_path):
        return ValidationResult(
            ok=True,
            phase="julia",
            message="Validation succeeded",
            payload={"status": "ok"},
            exit_code=0,
            raw_stdout='{"status":"ok"}\n',
            raw_stderr="",
        )


class ManualRunApiTests(unittest.TestCase):
    def setUp(self):
        self.validation_service = StubValidationService()
        self.run_queue = RecordingRunQueue()
        self.client = TestClient(
            create_app(
                validation_service=self.validation_service,
                database_url="sqlite:///:memory:",
                run_queue=self.run_queue,
            )
        )

    def test_manual_run_can_be_created_from_scenario_version_and_polled(self):
        scenario_version = self._create_scenario_version()

        create_response = self.client.post(f"/api/scenario-versions/{scenario_version['id']}/runs")

        self.assertEqual(create_response.status_code, 201)
        created = create_response.json()
        self.assertEqual(created["scenario_version_id"], scenario_version["id"])
        self.assertEqual(created["status"], "queued")
        self.assertIn("id", created)
        self.assertIn("created_at", created)
        self.assertIsNone(created["started_at"])
        self.assertIsNone(created["finished_at"])
        self.assertEqual(self.run_queue.enqueued_run_ids, [created["id"]])

        poll_response = self.client.get(f"/api/runs/{created['id']}")
        self.assertEqual(poll_response.status_code, 200)
        self.assertEqual(poll_response.json()["run"]["status"], "queued")

    def test_scenario_page_can_launch_run_and_run_page_polls_state(self):
        scenario_version = self._create_scenario_version()

        scenario_page = self.client.get(f"/scenarios/{scenario_version['scenario_id']}")
        self.assertEqual(scenario_page.status_code, 200)
        self.assertIn(f'action="/scenario-versions/{scenario_version["id"]}/runs"', scenario_page.text)
        self.assertIn("Launch Run", scenario_page.text)

        launch_response = self.client.post(
            f"/scenario-versions/{scenario_version['id']}/runs",
            follow_redirects=False,
        )

        self.assertEqual(launch_response.status_code, 303)
        self.assertRegex(launch_response.headers["location"], r"^/runs/\d+$")
        run_id = int(launch_response.headers["location"].rsplit("/", 1)[1])
        self.assertEqual(self.run_queue.enqueued_run_ids, [run_id])

        run_page = self.client.get(f"/runs/{run_id}")
        self.assertEqual(run_page.status_code, 200)
        self.assertIn("queued", run_page.text)
        self.assertIn(f"/api/runs/{run_id}", run_page.text)

    def test_run_detail_api_and_page_show_failure_message(self):
        scenario_version = self._create_scenario_version()
        store = self.client.app.state.analyst_store
        run = store.create_run(scenario_version_id=scenario_version["id"])
        store.mark_run_running(
            run["id"],
            workspace_path="workspace",
            input_snapshot_path="workspace/input/system_case.json",
        )
        store.mark_run_failed(
            run["id"],
            exit_code=23,
            stdout="solver stdout",
            stderr='{"status":"error","message":"optimization failed before solve"}',
            error_payload={"status": "error", "message": "optimization failed before solve"},
        )

        api_response = self.client.get(f"/api/runs/{run['id']}")
        self.assertEqual(api_response.status_code, 200)
        self.assertEqual(api_response.json()["run"]["error_message"], "optimization failed before solve")

        page_response = self.client.get(f"/runs/{run['id']}")
        self.assertEqual(page_response.status_code, 200)
        self.assertIn("failed", page_response.text)
        self.assertIn("optimization failed before solve", page_response.text)

    def _create_scenario_version(self):
        project = self.client.post("/api/projects", json={"name": "Hybrid PMGD"}).json()
        scenario = self.client.post(
            f"/api/projects/{project['id']}/scenarios",
            json={"name": "Base case"},
        ).json()
        sample_text = (REPO_ROOT / "data" / "cases" / "hybrid_system" / "system_case.json").read_text()
        return self.client.post(
            f"/api/scenarios/{scenario['id']}/versions",
            json={"system_case_json": sample_text},
        ).json()


class ManualRunPollingTests(unittest.TestCase):
    def test_manual_run_progress_is_visible_through_status_endpoint(self):
        store = AnalystStore("sqlite:///:memory:")

        class ControlledExecutor:
            def __init__(self):
                self.running = threading.Event()
                self.allow_finish = threading.Event()
                self.done = threading.Event()

            def execute(self, run_id):
                store.mark_run_running(
                    run_id,
                    workspace_path="workspace",
                    input_snapshot_path="workspace/input/system_case.json",
                )
                self.running.set()
                self.allow_finish.wait(timeout=2.0)
                store.mark_run_succeeded(
                    run_id,
                    exit_code=0,
                    stdout=json.dumps({"status": "ok"}),
                    stderr="",
                    success_payload={"status": "ok", "termination_status": "OPTIMAL"},
                    output_dir="workspace/outputs/hybrid_system/run",
                    summary_path="workspace/outputs/hybrid_system/run/summary.json",
                )
                self.done.set()

        executor = ControlledExecutor()
        queue = LocalRunQueue(executor=executor)
        client = TestClient(
            create_app(
                validation_service=StubValidationService(),
                store=store,
                run_queue=queue,
            )
        )
        try:
            project = client.post("/api/projects", json={"name": "Hybrid PMGD"}).json()
            scenario = client.post(
                f"/api/projects/{project['id']}/scenarios",
                json={"name": "Base case"},
            ).json()
            sample_text = (REPO_ROOT / "data" / "cases" / "hybrid_system" / "system_case.json").read_text()
            scenario_version = client.post(
                f"/api/scenarios/{scenario['id']}/versions",
                json={"system_case_json": sample_text},
            ).json()

            create_response = client.post(f"/api/scenario-versions/{scenario_version['id']}/runs")
            self.assertEqual(create_response.status_code, 201)
            run_id = create_response.json()["id"]
            self.assertEqual(create_response.json()["status"], "queued")

            self.assertTrue(executor.running.wait(timeout=2.0))
            running_response = client.get(f"/api/runs/{run_id}")
            self.assertEqual(running_response.json()["run"]["status"], "running")

            executor.allow_finish.set()
            self.assertTrue(executor.done.wait(timeout=2.0))
            succeeded_response = client.get(f"/api/runs/{run_id}")
            self.assertEqual(succeeded_response.json()["run"]["status"], "succeeded")
            self.assertEqual(succeeded_response.json()["run"]["exit_code"], 0)
        finally:
            queue.stop()
            store.close()


class JuliaRunExecutorTests(unittest.TestCase):
    def test_runner_revalidates_input_snapshot_and_fails_before_solving_when_invalid(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = AnalystStore("sqlite:///:memory:")
            try:
                scenario_version = create_persisted_scenario_version(store)
                run = store.create_run(scenario_version_id=scenario_version["id"])

                class RejectingValidationService:
                    def __init__(self):
                        self.validated_paths = []

                    def validate_file(self, candidate_path):
                        self.validated_paths.append(Path(candidate_path))
                        return ValidationResult(
                            ok=False,
                            phase="julia",
                            message="schema_version is required",
                            payload={"status": "error", "message": "schema_version is required"},
                            exit_code=7,
                            raw_stdout="validation stdout",
                            raw_stderr='{"status":"error","message":"schema_version is required"}\n',
                        )

                validation_service = RejectingValidationService()

                def solver_runner(command, **kwargs):
                    raise AssertionError("solver should not run after validation failure")

                executor = JuliaRunExecutor(
                    store=store,
                    repo_root=REPO_ROOT,
                    artifact_root=Path(temp_dir),
                    julia_executable="julia",
                    runner=solver_runner,
                    validation_service=validation_service,
                )

                executor.execute(run["id"])

                completed = store.get_run(run["id"])
                input_snapshot_path = Path(completed["input_snapshot_path"])
                self.assertEqual(completed["status"], "failed")
                self.assertEqual(completed["exit_code"], 7)
                self.assertEqual(completed["error_message"], "schema_version is required")
                self.assertEqual(completed["error_payload"]["message"], "schema_version is required")
                self.assertEqual(completed["stdout"], "validation stdout")
                self.assertIn("schema_version is required", completed["stderr"])
                self.assertTrue(input_snapshot_path.is_file())
                self.assertEqual(Path(completed["stdout_log_path"]).read_text(encoding="utf-8"), "validation stdout")
                self.assertIn(
                    "schema_version is required",
                    Path(completed["stderr_log_path"]).read_text(encoding="utf-8"),
                )
                self.assertEqual(validation_service.validated_paths, [input_snapshot_path])
            finally:
                store.close()

    def test_runner_writes_input_snapshot_invokes_julia_and_marks_run_succeeded(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = AnalystStore("sqlite:///:memory:")
            try:
                scenario_version = create_persisted_scenario_version(store)
                run = store.create_run(scenario_version_id=scenario_version["id"])
                completed_commands = []

                def fake_runner(command, **kwargs):
                    completed_commands.append((command, kwargs))
                    output_root = Path(command[command.index("--output-root") + 1])
                    output_dir = output_root / "hybrid_system" / "2026-01-01T00:00:00"
                    return subprocess.CompletedProcess(
                        command,
                        0,
                        stdout=json.dumps(
                            {
                                "case_name": "hybrid_system",
                                "run_timestamp": "2026-01-01T00:00:00",
                                "output_dir": str(output_dir),
                                "summary_path": str(output_dir / "summary.json"),
                                "termination_status": "OPTIMAL",
                            }
                        ),
                        stderr="",
                    )

                executor = JuliaRunExecutor(
                    store=store,
                    repo_root=REPO_ROOT,
                    artifact_root=Path(temp_dir),
                    julia_executable="julia",
                    runner=fake_runner,
                    validation_service=AcceptingRunValidationService(),
                )

                executor.execute(run["id"])

                completed = store.get_run(run["id"])
                self.assertEqual(completed["status"], "succeeded")
                self.assertIsNotNone(completed["started_at"])
                self.assertIsNotNone(completed["finished_at"])
                self.assertEqual(completed["exit_code"], 0)
                self.assertEqual(completed["success_payload"]["termination_status"], "OPTIMAL")
                self.assertTrue(completed["output_dir"].endswith("hybrid_system\\2026-01-01T00:00:00") or completed["output_dir"].endswith("hybrid_system/2026-01-01T00:00:00"))

                input_snapshot_path = Path(completed["input_snapshot_path"])
                self.assertTrue(input_snapshot_path.is_file())
                self.assertEqual(
                    json.loads(input_snapshot_path.read_text(encoding="utf-8")),
                    store.get_scenario_version(scenario_version["id"])["system_case_json"],
                )

                command, kwargs = completed_commands[0]
                self.assertEqual(command[:2], ["julia", "--project=."])
                self.assertIn(str(REPO_ROOT / "scripts" / "run_system_case.jl"), command)
                self.assertIn(str(input_snapshot_path), command)
                self.assertEqual(kwargs["cwd"], str(REPO_ROOT))
                self.assertTrue(kwargs["capture_output"])
                self.assertTrue(kwargs["text"])
            finally:
                store.close()

    def test_runner_records_process_failure_with_structured_error_and_log_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = AnalystStore("sqlite:///:memory:")
            try:
                scenario_version = create_persisted_scenario_version(store)
                run = store.create_run(scenario_version_id=scenario_version["id"])

                def failing_runner(command, **kwargs):
                    return subprocess.CompletedProcess(
                        command,
                        23,
                        stdout="solver stdout\nsecond line\n",
                        stderr='{"status":"error","message":"optimization failed before solve"}\n',
                    )

                executor = JuliaRunExecutor(
                    store=store,
                    repo_root=REPO_ROOT,
                    artifact_root=Path(temp_dir),
                    julia_executable="julia",
                    runner=failing_runner,
                    validation_service=AcceptingRunValidationService(),
                )

                executor.execute(run["id"])

                completed = store.get_run(run["id"])
                self.assertEqual(completed["status"], "failed")
                self.assertEqual(completed["exit_code"], 23)
                self.assertEqual(completed["error_message"], "optimization failed before solve")
                self.assertEqual(completed["error_payload"]["message"], "optimization failed before solve")
                self.assertEqual(completed["stdout"], "solver stdout\nsecond line\n")
                self.assertIn("optimization failed before solve", completed["stderr"])
                self.assertIsNotNone(completed["started_at"])
                self.assertIsNotNone(completed["finished_at"])
                self.assertIsNotNone(completed["duration_seconds"])

                stdout_log_path = Path(completed["stdout_log_path"])
                stderr_log_path = Path(completed["stderr_log_path"])
                self.assertEqual(stdout_log_path.read_text(encoding="utf-8"), "solver stdout\nsecond line\n")
                self.assertEqual(
                    stderr_log_path.read_text(encoding="utf-8"),
                    '{"status":"error","message":"optimization failed before solve"}\n',
                )
            finally:
                store.close()


class LocalRunQueueTests(unittest.TestCase):
    def test_local_run_queue_processes_one_run_at_a_time(self):
        class BlockingExecutor:
            def __init__(self):
                self.active_count = 0
                self.max_active_count = 0
                self.completed_run_ids = []
                self.lock = threading.Lock()
                self.done = threading.Event()

            def execute(self, run_id):
                with self.lock:
                    self.active_count += 1
                    self.max_active_count = max(self.max_active_count, self.active_count)
                time.sleep(0.05)
                with self.lock:
                    self.active_count -= 1
                    self.completed_run_ids.append(run_id)
                    if len(self.completed_run_ids) == 2:
                        self.done.set()

        executor = BlockingExecutor()
        queue = LocalRunQueue(executor=executor)
        try:
            queue.enqueue(101)
            queue.enqueue(102)

            self.assertTrue(executor.done.wait(timeout=2.0))
            self.assertEqual(executor.completed_run_ids, [101, 102])
            self.assertEqual(executor.max_active_count, 1)
        finally:
            queue.stop()


def create_persisted_scenario_version(store):
    project = store.create_project(name="Hybrid PMGD")
    scenario = store.create_scenario(project_id=project["id"], name="Base case")
    sample_document = json.loads((REPO_ROOT / "data" / "cases" / "hybrid_system" / "system_case.json").read_text())
    return store.create_scenario_version(
        scenario_id=scenario["id"],
        system_case_json=sample_document,
        validation_payload={"status": "ok"},
    )


if __name__ == "__main__":
    unittest.main()
