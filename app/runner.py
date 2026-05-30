from __future__ import annotations

import json
import os
import queue
import subprocess
import threading
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol

from app.persistence import AnalystStore
from app.validation import resolve_julia_executable


Runner = Callable[..., subprocess.CompletedProcess[str]]


class RunExecutor(Protocol):
    def execute(self, run_id: int) -> Any:
        ...


class LocalRunQueue:
    def __init__(self, *, executor: RunExecutor):
        self.executor = executor
        self._queue: queue.Queue[int | None] = queue.Queue()
        self._stop_requested = threading.Event()
        self._thread = threading.Thread(target=self._work, name="bess-run-worker", daemon=True)
        self._started = False
        self._lock = threading.Lock()

    def enqueue(self, run_id: int) -> None:
        self._ensure_started()
        self._queue.put(run_id)

    def stop(self) -> None:
        self._stop_requested.set()
        with self._lock:
            started = self._started
        if started:
            self._queue.put(None)
            self._thread.join(timeout=2.0)

    def _ensure_started(self) -> None:
        with self._lock:
            if not self._started:
                self._thread.start()
                self._started = True

    def _work(self) -> None:
        while not self._stop_requested.is_set():
            run_id = self._queue.get()
            try:
                if run_id is None:
                    return
                self.executor.execute(run_id)
            finally:
                self._queue.task_done()


class JuliaRunExecutor:
    def __init__(
        self,
        *,
        store: AnalystStore,
        repo_root: Path | str | None = None,
        artifact_root: Path | str | None = None,
        julia_executable: str | None = None,
        runner: Runner | None = None,
        timeout_seconds: float = 300.0,
    ):
        self.store = store
        self.repo_root = Path(repo_root) if repo_root is not None else Path(__file__).resolve().parents[1]
        self.artifact_root = Path(
            artifact_root or os.environ.get("ARTIFACT_ROOT") or self.repo_root / ".tmp" / "artifacts"
        )
        self.julia_executable = julia_executable or resolve_julia_executable()
        self.runner = runner or subprocess.run
        self.timeout_seconds = timeout_seconds

    def execute(self, run_id: int) -> dict[str, Any]:
        run = self.store.get_run(run_id)
        scenario_version = self.store.get_scenario_version(run["scenario_version_id"])
        workspace_path = self._workspace_path(run_id)
        input_snapshot_path = self._write_input_snapshot(workspace_path, scenario_version["system_case_json"])
        self.store.mark_run_running(
            run_id,
            workspace_path=str(workspace_path),
            input_snapshot_path=str(input_snapshot_path),
        )

        try:
            completed = self._run_julia(input_snapshot_path, workspace_path / "outputs")
        except subprocess.TimeoutExpired:
            return self.store.mark_run_failed(
                run_id,
                exit_code=None,
                stdout="",
                stderr="",
                error_payload={"status": "error", "message": f"Julia run timed out after {self.timeout_seconds:g} seconds"},
            )
        except FileNotFoundError:
            return self.store.mark_run_failed(
                run_id,
                exit_code=None,
                stdout="",
                stderr="",
                error_payload={"status": "error", "message": f"Julia executable not found: {self.julia_executable}"},
            )
        except OSError as error:
            return self.store.mark_run_failed(
                run_id,
                exit_code=None,
                stdout="",
                stderr="",
                error_payload={"status": "error", "message": f"Julia run could not start: {error}"},
            )

        stdout = completed.stdout or ""
        stderr = completed.stderr or ""
        if completed.returncode == 0:
            payload = parse_json_payload(stdout)
            if payload:
                return self.store.mark_run_succeeded(
                    run_id,
                    exit_code=completed.returncode,
                    stdout=stdout,
                    stderr=stderr,
                    success_payload=payload,
                    output_dir=string_or_none(payload.get("output_dir")),
                    summary_path=string_or_none(payload.get("summary_path")),
                )

            return self.store.mark_run_failed(
                run_id,
                exit_code=completed.returncode,
                stdout=stdout,
                stderr=stderr,
                error_payload={"status": "error", "message": "Julia run succeeded without parseable JSON stdout"},
            )

        payload = parse_json_payload(stderr)
        message = str(payload.get("message") or stderr.strip() or "Julia run failed")
        return self.store.mark_run_failed(
            run_id,
            exit_code=completed.returncode,
            stdout=stdout,
            stderr=stderr,
            error_payload=payload or {"status": "error", "message": message},
        )

    def _workspace_path(self, run_id: int) -> Path:
        return self.artifact_root / "runs" / str(run_id)

    def _write_input_snapshot(self, workspace_path: Path, document: dict[str, Any]) -> Path:
        input_dir = workspace_path / "input"
        input_dir.mkdir(parents=True, exist_ok=True)
        input_snapshot_path = input_dir / "system_case.json"
        input_snapshot_path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return input_snapshot_path

    def _run_julia(self, input_snapshot_path: Path, output_root: Path) -> subprocess.CompletedProcess[str]:
        output_root.mkdir(parents=True, exist_ok=True)
        command = [
            self.julia_executable,
            "--project=.",
            str(self.repo_root / "scripts" / "run_system_case.jl"),
            str(input_snapshot_path),
            "--output-root",
            str(output_root),
        ]
        return self.runner(
            command,
            cwd=str(self.repo_root),
            capture_output=True,
            text=True,
            timeout=self.timeout_seconds,
        )


def parse_json_payload(text: str) -> dict[str, Any]:
    if not text.strip():
        return {}

    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return {}

    if isinstance(payload, Mapping):
        return dict(payload)

    return {}


def string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)
