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
