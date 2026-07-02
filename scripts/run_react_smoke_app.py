from __future__ import annotations

import json
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


class SmokeRunQueue:
    def __init__(self, store: AnalystStore, artifact_root: Path):
        self.store = store
        self.artifact_root = artifact_root
        self.enqueued_run_ids = []

    def enqueue(self, run_id: int):
        self.enqueued_run_ids.append(run_id)
        workspace = self.artifact_root / "runs" / str(run_id)
        input_dir = workspace / "input"
        output_dir = workspace / "outputs"
        input_dir.mkdir(parents=True, exist_ok=True)
        output_dir.mkdir(parents=True, exist_ok=True)
        input_snapshot_path = input_dir / "system_case.json"
        input_snapshot_path.write_text("{}\n", encoding="utf-8")

        self.store.mark_run_running(
            run_id,
            workspace_path=str(workspace),
            input_snapshot_path=str(input_snapshot_path),
        )

        summary_path = output_dir / "summary.json"
        dispatch_path = output_dir / "dispatch.csv"
        asset_dispatch_path = output_dir / "asset_dispatch.csv"
        metadata_path = output_dir / "model_metadata.json"

        summary_path.write_text(
            json.dumps(
                {
                    "case_name": "hybrid_system",
                    "schema_version": "bess_system_dispatch.v1",
                    "solver_name": "HiGHS",
                    "solver_status": "OPTIMAL",
                    "termination_status": "OPTIMAL",
                    "objective_value_usd": 1250.5,
                },
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        dispatch_path.write_text(
            "\n".join(
                [
                    "timestamp,price_usd_per_mwh,grid_import_mw,grid_export_mw,renewable_used_mw,renewable_curtailed_mw,battery_charge_mw,battery_discharge_mw,battery_energy_mwh,period_profit_usd",
                    "2026-01-01T00:00:00,70,0,2.0,1.5,0.0,0.0,0.6,8.5,140",
                    "2026-01-01T01:00:00,90,0,3.0,1.8,0.0,0.0,0.4,8.1,270",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        asset_dispatch_path.write_text(
            "\n".join(
                [
                    "timestamp,asset_id,asset_type,battery_charge_mw,battery_discharge_mw,battery_energy_mwh",
                    "2026-01-01T00:00:00,bess_1,battery,0.0,0.6,8.5",
                    "2026-01-01T01:00:00,bess_1,battery,0.0,0.4,8.1",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        metadata_path.write_text(
            '{"schema_version":"bess_system_dispatch.v1"}\n',
            encoding="utf-8",
        )

        self.store.mark_run_succeeded(
            run_id,
            exit_code=0,
            stdout='{"termination_status":"OPTIMAL"}\n',
            stderr="",
            success_payload={"termination_status": "OPTIMAL"},
            output_dir=str(output_dir),
            summary_path=str(summary_path),
        )
        for artifact_type, path, display_name, media_type in [
            ("summary_json", summary_path, "summary.json", "application/json"),
            ("dispatch_csv", dispatch_path, "dispatch.csv", "text/csv"),
            (
                "asset_dispatch_csv",
                asset_dispatch_path,
                "asset_dispatch.csv",
                "text/csv",
            ),
            (
                "model_metadata_json",
                metadata_path,
                "model_metadata.json",
                "application/json",
            ),
        ]:
            self.store.register_run_artifact(
                run_id=run_id,
                artifact_type=artifact_type,
                path=str(path),
                display_name=display_name,
                media_type=media_type,
            )

    def stop(self):
        pass


def main() -> None:
    store = AnalystStore("sqlite:///:memory:")
    artifact_root = REPO_ROOT / ".tmp" / "react-smoke-artifacts"
    app = create_app(
        store=store,
        auth_enabled=True,
        validation_service=SmokeValidationService(),
        run_queue=SmokeRunQueue(store, artifact_root),
        artifact_root=artifact_root,
    )

    @app.get("/api/auth/smoke-token", include_in_schema=False)
    async def smoke_token():
        return {"token": os.environ.get("REACT_SMOKE_TOKEN", "")}

    uvicorn.run(
        app,
        host="127.0.0.1",
        port=int(os.environ.get("REACT_SMOKE_PORT", "8123")),
        log_level="warning",
    )


if __name__ == "__main__":
    main()
