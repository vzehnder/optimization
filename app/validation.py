from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping


Runner = Callable[..., subprocess.CompletedProcess[str]]


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    phase: str
    message: str
    payload: dict[str, Any] = field(default_factory=dict)
    exit_code: int | None = None
    raw_stdout: str = ""
    raw_stderr: str = ""


class JuliaValidationService:
    def __init__(
        self,
        *,
        repo_root: Path | str | None = None,
        julia_executable: str | None = None,
        runner: Runner | None = None,
        timeout_seconds: float = 60.0,
    ):
        self.repo_root = Path(repo_root) if repo_root is not None else Path(__file__).resolve().parents[1]
        self.julia_executable = julia_executable or resolve_julia_executable()
        self.runner = runner or subprocess.run
        self.timeout_seconds = timeout_seconds

    def validate_text(self, candidate_text: str) -> ValidationResult:
        try:
            document = json.loads(candidate_text)
        except json.JSONDecodeError as error:
            return ValidationResult(
                ok=False,
                phase="json",
                message=f"Malformed JSON: {error.msg} at line {error.lineno}, column {error.colno}",
                payload={
                    "status": "error",
                    "message": error.msg,
                    "line": error.lineno,
                    "column": error.colno,
                },
            )

        temp_path = self._write_candidate_file(document)
        try:
            completed = self._run_julia_validation(temp_path)
        except subprocess.TimeoutExpired:
            return ValidationResult(
                ok=False,
                phase="julia",
                message=f"Julia validation timed out after {self.timeout_seconds:g} seconds",
                payload={"status": "error"},
            )
        except FileNotFoundError:
            return ValidationResult(
                ok=False,
                phase="julia",
                message=f"Julia executable not found: {self.julia_executable}",
                payload={"status": "error"},
            )
        except OSError as error:
            return ValidationResult(
                ok=False,
                phase="julia",
                message=f"Julia validation could not start: {error}",
                payload={"status": "error"},
            )
        finally:
            temp_path.unlink(missing_ok=True)

        stdout = completed.stdout or ""
        stderr = completed.stderr or ""

        if completed.returncode == 0:
            payload = self._parse_json_payload(stdout)
            if not payload:
                return ValidationResult(
                    ok=False,
                    phase="julia",
                    message="Julia validation succeeded without parseable JSON stdout",
                    payload={"status": "error"},
                    exit_code=completed.returncode,
                    raw_stdout=stdout,
                    raw_stderr=stderr,
                )

            return ValidationResult(
                ok=True,
                phase="julia",
                message="Validation succeeded",
                payload=payload,
                exit_code=completed.returncode,
                raw_stdout=stdout,
                raw_stderr=stderr,
            )

        payload = self._parse_json_payload(stderr)
        message = str(payload.get("message") or stderr.strip() or "Julia validation failed")
        return ValidationResult(
            ok=False,
            phase="julia",
            message=message,
            payload=payload or {"status": "error", "message": message},
            exit_code=completed.returncode,
            raw_stdout=stdout,
            raw_stderr=stderr,
        )

    def _write_candidate_file(self, document: Any) -> Path:
        with tempfile.NamedTemporaryFile("w", suffix=".json", encoding="utf-8", delete=False) as temp_file:
            json.dump(document, temp_file, indent=2, sort_keys=True)
            temp_file.write("\n")
            return Path(temp_file.name)

    def _run_julia_validation(self, candidate_path: Path) -> subprocess.CompletedProcess[str]:
        command = [
            self.julia_executable,
            "--project=.",
            str(self.repo_root / "scripts" / "validate_system_case.jl"),
            str(candidate_path),
        ]
        return self.runner(
            command,
            cwd=str(self.repo_root),
            capture_output=True,
            text=True,
            timeout=self.timeout_seconds,
        )

    @staticmethod
    def _parse_json_payload(text: str) -> dict[str, Any]:
        if not text.strip():
            return {}

        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            return {}

        if isinstance(payload, Mapping):
            return dict(payload)

        return {}


def resolve_julia_executable() -> str:
    configured = os.environ.get("JULIA")
    if configured:
        return configured

    discovered = shutil.which("julia")
    if discovered and "Microsoft\\WindowsApps" not in discovered:
        return discovered

    for candidate in julia_install_candidates():
        if candidate.is_file():
            return str(candidate)

    return discovered or "julia"


def julia_install_candidates() -> list[Path]:
    home = Path.home()
    local_app_data = Path(os.environ.get("LOCALAPPDATA", ""))
    candidates = list((home / ".julia" / "juliaup").glob("**/bin/julia.exe"))
    if local_app_data != Path("."):
        candidates.extend(local_app_data.glob("Programs/Julia-*/bin/julia.exe"))

    return sorted(candidates, reverse=True)
