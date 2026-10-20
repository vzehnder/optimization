import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from app.persistence import AnalystStore
from app.run_progress import LOG_TAIL_BYTES, append_run_progress, read_run_progress
from app.runner import JuliaRunExecutor
from tests.test_manual_runs import (
    AcceptingRunValidationService, RecordingRunQueue, create_persisted_scenario_version,
)


MIP_LINE = " S 12 3 4 23.50% 1200 1100 9.09% 10 5 120 450 12.3s\n"


class RunProgressTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.logs = self.root / "runs" / "1" / "logs"
        self.logs.mkdir(parents=True)
        self.run = {"id": 1, "status": "running", "started_at": "2026-10-16T12:00:00Z"}

    def test_reads_current_mip_gap_instead_of_explored_tree_percentage(self):
        append_run_progress(self.logs / "progress.jsonl", "optimizing", "Optimizando")
        (self.logs / "solver.log").write_text(MIP_LINE, encoding="utf-8")
        progress = read_run_progress(self.run, self.root)
        self.assertEqual(progress["stage"], "optimizing")
        self.assertEqual(progress["gap_percent"], 9.09)
        self.assertEqual(progress["best_objective"], 1100)
        self.assertEqual(progress["best_bound"], 1200)
        self.assertEqual(progress["solver_seconds"], 12.3)

    def test_no_solution_and_continuous_models_do_not_invent_a_gap(self):
        for log in ["", "Iteration Objective Infeasibilities\n", MIP_LINE.replace("9.09%", "inf").replace("1100", "-inf")]:
            with self.subTest(log=log):
                (self.logs / "solver.log").write_text(log, encoding="utf-8")
                progress = read_run_progress(self.run, self.root)
                self.assertIsNone(progress["gap_percent"])
                json.dumps(progress, allow_nan=False)

    def test_final_gap_and_duration_freeze_and_partial_lines_are_ignored(self):
        append_run_progress(self.logs / "progress.jsonl", "saving", "Guardando")
        with (self.logs / "progress.jsonl").open("a") as stream:
            stream.write('{"timestamp":')
        (self.logs / "solver.log").write_text(MIP_LINE + "  Gap 0.01% (tolerance: 0.1%)\n  Gap 99", encoding="utf-8")
        self.run.update(status="succeeded", finished_at="2026-10-16T12:01:02Z")
        progress = read_run_progress(self.run, self.root)
        self.assertEqual(progress["gap_percent"], 0.01)
        self.assertEqual(progress["elapsed_seconds"], 62)
        self.assertEqual(progress["events"][-1]["stage"], "succeeded")

    def test_log_reads_are_bounded_and_queued_runs_have_no_elapsed_time(self):
        (self.logs / "solver.log").write_text("old log\n" * LOG_TAIL_BYTES + MIP_LINE, encoding="utf-8")
        progress = read_run_progress(self.run, self.root)
        self.assertTrue(progress["log_truncated"])
        self.assertLessEqual(len(progress["solver_log"]), LOG_TAIL_BYTES)
        self.assertEqual(progress["gap_percent"], 9.09)
        queued = read_run_progress({"id": 2, "status": "queued"}, self.root)
        self.assertEqual(queued["stage"], "queued")
        self.assertIsNone(queued["elapsed_seconds"])

    def test_api_exposes_progress_before_process_exit_and_keeps_it_after_timeout(self):
        store = AnalystStore("sqlite:///:memory:")
        self.addCleanup(store.close)
        version = create_persisted_scenario_version(store)
        run = store.create_run(scenario_version_id=version["id"])
        client = TestClient(create_app(store=store, artifact_root=self.root, run_queue=RecordingRunQueue()))
        test = self

        class Validation(AcceptingRunValidationService):
            def validate_file(self, path):
                snapshot = client.get(f"/api/runs/{run['id']}").json()["run"]
                test.assertEqual(snapshot["progress"]["stage"], "validating")
                return super().validate_file(path)

        def runner(command, **kwargs):
            append_run_progress(Path(kwargs["env"]["BESS_RUN_PROGRESS_PATH"]), "optimizing", "Iniciando optimización")
            Path(kwargs["env"]["BESS_SOLVER_LOG_PATH"]).write_text(MIP_LINE, encoding="utf-8")
            snapshot = client.get(f"/api/runs/{run['id']}").json()["run"]
            self.assertEqual(snapshot["status"], "running")
            self.assertEqual(snapshot["progress"]["gap_percent"], 9.09)
            raise subprocess.TimeoutExpired(command, 1, output=b"partial stdout", stderr=b"partial stderr")

        executor = JuliaRunExecutor(store=store, artifact_root=self.root, runner=runner, validation_service=Validation())
        executor.execute(run["id"])
        finished = client.get(f"/api/runs/{run['id']}").json()["run"]
        self.assertEqual(finished["status"], "failed")
        self.assertEqual(finished["stdout"], "partial stdout")
        self.assertEqual(finished["progress"]["gap_percent"], 9.09)
        self.assertEqual(finished["progress"]["stage"], "failed")
        self.assertEqual(finished["progress"]["events"][-1]["stage"], "failed")
        self.assertIn("solver_log", {a["artifact_type"] for a in store.list_run_artifacts(run["id"])})
