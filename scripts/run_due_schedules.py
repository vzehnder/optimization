from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from app.database import database_url_from_env
from app.persistence import AnalystStore, utc_now_iso
from app.runner import JuliaRunExecutor
from app.schedules import due_fixed_range_schedules, execute_fixed_range_schedule
from app.validation import JuliaValidationService


class ImmediateRunQueue:
    def __init__(self, executor: JuliaRunExecutor):
        self.executor = executor
        self.enqueued_run_ids: list[int] = []

    def enqueue(self, run_id: int) -> None:
        self.enqueued_run_ids.append(run_id)
        self.executor.execute(run_id)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run due BESS schedules once.")
    parser.add_argument("--now", default=None, help="ISO-8601 timestamp override")
    parser.add_argument("--triggered-by", default="schedule_cli")
    args = parser.parse_args()

    now = args.now or utc_now_iso()
    store = AnalystStore(database_url_from_env())
    try:
        executor = JuliaRunExecutor(store=store)
        queue = ImmediateRunQueue(executor)
        due = due_fixed_range_schedules(store.list_run_schedules(), now=now)
        ticks = [
            execute_fixed_range_schedule(
                store=store,
                validation_service=JuliaValidationService(),
                run_queue=queue,
                schedule=schedule,
                now=now,
                triggered_by=args.triggered_by,
            )
            for schedule in due
        ]
        print(
            json.dumps(
                {
                    "now": now,
                    "due_count": len(due),
                    "ticks": ticks,
                    "executed_run_ids": queue.enqueued_run_ids,
                },
                sort_keys=True,
            )
        )
        return 0
    finally:
        store.close()


if __name__ == "__main__":
    raise SystemExit(main())
