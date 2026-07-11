from __future__ import annotations

import json
import math
from datetime import datetime, timedelta
from typing import Any, Iterable, Protocol

from app.draft_editor import DraftGenerationError
from app.input_variants import InputVariantRangeError
from app.required_signals import MissingRequiredSignalsError
from app.variant_staleness import VariantStaleError


CADENCE_DELTAS = {
    "hourly": timedelta(hours=1),
    "daily": timedelta(days=1),
    "weekly": timedelta(days=7),
}


class ScheduleError(ValueError):
    pass


class ScheduleValidationService(Protocol):
    def validate_text(self, candidate_text: str) -> Any:
        ...


class ScheduleRunQueue(Protocol):
    def enqueue(self, run_id: int) -> None:
        ...


def parse_schedule_datetime(value: str, *, field_name: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise ScheduleError(f"{field_name} must be ISO-8601") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ScheduleError(f"{field_name} must include a timezone offset")
    return parsed


def normalize_schedule_cadence(cadence: str) -> str:
    normalized = cadence.strip().lower()
    if normalized not in CADENCE_DELTAS:
        allowed = ", ".join(sorted(CADENCE_DELTAS))
        raise ScheduleError(f"cadence must be one of: {allowed}")
    return normalized


def due_fixed_range_schedules(
    schedules: Iterable[dict[str, Any]], *, now: str
) -> list[dict[str, Any]]:
    current_time = parse_schedule_datetime(now, field_name="now")
    due: list[dict[str, Any]] = []
    for schedule in schedules:
        if not schedule.get("is_active"):
            continue
        next_run_at = parse_schedule_datetime(
            str(schedule["next_run_at"]), field_name="next_run_at"
        )
        if next_run_at <= current_time:
            due.append(schedule)
    return sorted(due, key=lambda schedule: (schedule["next_run_at"], schedule["id"]))


def next_fixed_range_fire_time(*, cadence: str, due_at: str, now: str) -> str:
    delta = CADENCE_DELTAS[normalize_schedule_cadence(cadence)]
    next_fire = parse_schedule_datetime(due_at, field_name="due_at") + delta
    current_time = parse_schedule_datetime(now, field_name="now")
    while next_fire <= current_time:
        next_fire += delta
    return next_fire.isoformat()


def _float_schedule_field(schedule: dict[str, Any], field_name: str) -> float:
    value = schedule.get(field_name)
    if value is None:
        raise ScheduleError(f"{field_name} is required for rolling schedules")
    try:
        parsed = float(value)
    except (TypeError, ValueError) as error:
        raise ScheduleError(f"{field_name} must be numeric") from error
    if not math.isfinite(parsed):
        raise ScheduleError(f"{field_name} must be numeric")
    return parsed


def resolve_schedule_range(
    *, schedule: dict[str, Any], due_at: str
) -> dict[str, str]:
    range_mode = str(schedule.get("range_mode") or "fixed").strip().lower()
    if range_mode == "fixed":
        return {"start": str(schedule["range_start"]), "end": str(schedule["range_end"])}
    if range_mode != "rolling":
        raise ScheduleError("range_mode must be fixed or rolling")

    anchor = parse_schedule_datetime(due_at, field_name="due_at")
    start_offset_hours = _float_schedule_field(
        schedule, "rolling_start_offset_hours"
    )
    duration_hours = _float_schedule_field(schedule, "rolling_duration_hours")
    if duration_hours <= 0:
        raise ScheduleError("rolling_duration_hours must be positive")

    start = anchor + timedelta(hours=start_offset_hours)
    end = start + timedelta(hours=duration_hours)
    return {"start": start.isoformat(), "end": end.isoformat()}


def fixed_range_schedule_metadata(
    *,
    schedule: dict[str, Any],
    tick: dict[str, Any],
    variant: dict[str, Any],
    materialized: dict[str, Any],
    resolved_range: dict[str, str],
    fired_at: str,
) -> dict[str, Any]:
    return {
        "kind": "case_input_variant",
        "input_variant": {
            "id": int(schedule["case_input_variant_id"]),
            "display_name": variant["display_name"],
        },
        "date_range": {
            "start": resolved_range["start"],
            "end": resolved_range["end"],
        },
        "series_bindings": materialized["series_bindings"],
        "automation": {
            "schedule_id": int(schedule["id"]),
            "schedule_tick_id": int(tick["id"]),
            "schedule_name": schedule["display_name"],
            "due_at": schedule["next_run_at"],
            "fired_at": fired_at,
        },
    }


def execute_fixed_range_schedule(
    *,
    store: Any,
    validation_service: ScheduleValidationService,
    run_queue: ScheduleRunQueue,
    schedule: dict[str, Any],
    now: str,
    triggered_by: str = "schedule",
) -> dict[str, Any]:
    fired_at = parse_schedule_datetime(now, field_name="now").isoformat()
    due_at = parse_schedule_datetime(
        str(schedule["next_run_at"]), field_name="next_run_at"
    ).isoformat()
    resolved_range = resolve_schedule_range(schedule=schedule, due_at=due_at)
    tick = store.create_run_schedule_tick(
        schedule_id=int(schedule["id"]),
        due_at=due_at,
        fired_at=fired_at,
        range_start=resolved_range["start"],
        range_end=resolved_range["end"],
    )
    next_run_at = next_fixed_range_fire_time(
        cadence=schedule["cadence"], due_at=due_at, now=fired_at
    )

    try:
        variant = store.get_case_input_variant_for_case(
            int(schedule["case_id"]), int(schedule["case_input_variant_id"])
        )
        materialized = store.materialize_system_case_for_variant(
            scenario_id=int(schedule["scenario_id"]),
            case_input_variant_id=int(schedule["case_input_variant_id"]),
            range_start=resolved_range["start"],
            range_end=resolved_range["end"],
        )
        candidate_text = json.dumps(materialized["system_case"], sort_keys=True)
        validation_result = validation_service.validate_text(candidate_text)
        if not validation_result.ok:
            tick = store.mark_run_schedule_tick_failed(
                tick["id"],
                error_message=str(validation_result.message),
                error_payload=validation_result.payload,
            )
            return tick

        scenario_version = store.create_scenario_version(
            scenario_id=int(schedule["scenario_id"]),
            system_case_json=materialized["system_case"],
            validation_payload=validation_result.payload,
            generation_metadata=fixed_range_schedule_metadata(
                schedule=schedule,
                tick=tick,
                variant=variant,
                materialized=materialized,
                resolved_range=resolved_range,
                fired_at=fired_at,
            ),
            created_by=triggered_by,
        )
        run = store.create_run(
            scenario_version_id=scenario_version["id"],
            triggered_by=triggered_by,
            trigger_type="scheduled",
        )
        run_queue.enqueue(run["id"])
        tick = store.mark_run_schedule_tick_queued(
            tick["id"], scenario_version_id=scenario_version["id"], run_id=run["id"]
        )
        return tick
    except (
        DraftGenerationError,
        InputVariantRangeError,
        MissingRequiredSignalsError,
        VariantStaleError,
        ValueError,
    ) as error:
        tick = store.mark_run_schedule_tick_failed(
            tick["id"],
            error_message=str(error),
            error_payload={"status": "error", "message": str(error)},
        )
        return tick
    finally:
        store.advance_run_schedule(
            int(schedule["id"]),
            next_run_at=next_run_at,
            last_fired_at=fired_at,
            updated_by=triggered_by,
        )
