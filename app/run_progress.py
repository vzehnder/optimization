"""Bounded, restart-safe progress snapshots from the worker's per-run logs."""

from __future__ import annotations

import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


LOG_TAIL_BYTES = 64 * 1024
MIP_ROW = re.compile(
    r"^\s*(?:[A-Za-z]\s+)?\d+\s+\d+\s+\d+\s+\S+%\s+"
    r"(?P<bound>\S+)\s+(?P<objective>\S+)\s+(?P<gap>\S+)\s+"
    r"\S+\s+\S+\s+\S+\s+\S+\s+(?P<seconds>[\d.]+)s\s*$"
)


def append_run_progress(path: Path, stage: str, message: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    event = {"timestamp": datetime.now(timezone.utc).isoformat(), "stage": stage, "message": message}
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(event, ensure_ascii=False) + "\n")


def _tail(path: Path, root: Path) -> tuple[str, bool]:
    try:
        path.resolve().relative_to(root.resolve())
        with path.open("rb") as stream:
            size = stream.seek(0, 2)
            truncated = size > LOG_TAIL_BYTES
            stream.seek(max(0, size - LOG_TAIL_BYTES))
            data = stream.read(LOG_TAIL_BYTES)
        if truncated:
            data = data.partition(b"\n")[2]
        # Do not expose a line while the worker is still writing it.
        data = data[:data.rfind(b"\n") + 1]
        return data.decode("utf-8", errors="replace"), truncated
    except (OSError, ValueError):
        return "", False


def _finite_number(value: str) -> float | None:
    try:
        number = float(value.rstrip("%"))
        return number if math.isfinite(number) else None
    except ValueError:
        return None


def _timestamp(value: str | None) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00")) if value else None
        return parsed.replace(tzinfo=timezone.utc) if parsed and parsed.tzinfo is None else parsed
    except ValueError:
        return None


def read_run_progress(run: dict[str, Any], artifact_root: Path) -> dict[str, Any]:
    log_dir = artifact_root / "runs" / str(run["id"]) / "logs"
    events_text, events_truncated = _tail(log_dir / "progress.jsonl", artifact_root)
    solver_log, solver_truncated = _tail(log_dir / "solver.log", artifact_root)
    events = []
    for line in events_text.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict) and all(isinstance(event.get(key), str) for key in ("timestamp", "stage", "message")):
            events.append({key: event[key] for key in ("timestamp", "stage", "message")})

    gap_percent = objective = bound = solver_seconds = None
    for line in solver_log.splitlines():
        row = MIP_ROW.match(line)
        if row:
            gap_percent = _finite_number(row["gap"])
            objective = _finite_number(row["objective"])
            bound = _finite_number(row["bound"])
            solver_seconds = _finite_number(row["seconds"])
        else:
            summary = re.match(r"^\s*(Gap|Primal bound|Dual bound)\s+(\S+)", line)
            if summary:
                value = _finite_number(summary[2])
                if summary[1] == "Gap":
                    gap_percent = value
                elif summary[1] == "Primal bound":
                    objective = value
                else:
                    bound = value

    terminal = run["status"] in {"succeeded", "failed"}
    stage = events[-1]["stage"] if events else run["status"]
    if terminal:
        stage = run["status"]
        if events:
            events.append({
                "timestamp": run.get("finished_at") or events[-1]["timestamp"],
                "stage": stage,
                "message": "Ejecución finalizada." if stage == "succeeded" else (run.get("error_message") or "La ejecución falló."),
            })
    start = _timestamp(run.get("started_at"))
    end = _timestamp(run.get("finished_at")) if terminal else datetime.now(timezone.utc)
    elapsed = max(0.0, (end - start).total_seconds()) if start and end else run.get("duration_seconds")
    return {
        "stage": stage,
        "elapsed_seconds": elapsed,
        "gap_percent": gap_percent,
        "best_objective": objective,
        "best_bound": bound,
        "solver_seconds": solver_seconds,
        "events": events,
        "solver_log": solver_log,
        "log_truncated": events_truncated or solver_truncated,
    }
