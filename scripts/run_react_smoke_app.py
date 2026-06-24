from __future__ import annotations

import os
import sys
from pathlib import Path

import uvicorn

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from app.main import create_app
from app.persistence import AnalystStore
from app.validation import ValidationResult


class SmokeValidationService:
    def validate_text(self, candidate_text):
        return ValidationResult(
            ok=True,
            phase="julia",
            message="Validation succeeded",
            payload={"status": "ok"},
            exit_code=0,
            raw_stdout='{"status":"ok"}\n',
            raw_stderr="",
        )

    def validate_file(self, candidate_path):
        return self.validate_text(Path(candidate_path).read_text(encoding="utf-8"))


class NoopRunQueue:
    def __init__(self):
        self.enqueued_run_ids = []

    def enqueue(self, run_id):
        self.enqueued_run_ids.append(run_id)

    def stop(self):
        pass


def main() -> None:
    store = AnalystStore("sqlite:///:memory:")
    app = create_app(
        store=store,
        auth_enabled=True,
        validation_service=SmokeValidationService(),
        run_queue=NoopRunQueue(),
    )
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=int(os.environ.get("REACT_SMOKE_PORT", "8123")),
        log_level="warning",
    )


if __name__ == "__main__":
    main()
