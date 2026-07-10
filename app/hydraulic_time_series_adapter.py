from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Mapping


HYDRAULIC_LEGACY_ORIGIN_KIND = "hydraulic_legacy"


def _hydraulic_signal_unit(signal_key: str) -> str:
    from app.time_series_catalog import TIME_SERIES_SIGNAL_CATALOG

    definition = TIME_SERIES_SIGNAL_CATALOG.get(signal_key)
    return definition.unit if definition is not None else ""


def _hydraulic_migration_status(raw: Mapping[str, Any]) -> dict[str, Any] | None:
    migrated_time_series_set_id = raw.get("migrated_time_series_set_id")
    if migrated_time_series_set_id is None:
        return None
    return {
        "time_series_set_id": int(migrated_time_series_set_id),
        "time_series_set_name": str(raw.get("migrated_time_series_set_name")),
        "version_label": str(raw.get("migrated_time_series_set_version_label")),
        "migrated_by": str(raw.get("migrated_by")),
        "migrated_at": str(raw.get("migrated_at")),
    }


def build_hydraulic_catalog_summary(raw: Mapping[str, Any]) -> dict[str, Any]:
    signal_key = str(raw["signal_key"])
    entity_type = str(raw["entity_type"])
    entity_id = int(raw["entity_id"])
    entity_display_name = str(raw["entity_display_name"])
    hydraulic_system_name = str(raw["hydraulic_system_name"])
    return {
        "id": int(raw["id"]),
        "project_id": int(raw["project_id"]),
        "name": f"{hydraulic_system_name} / {entity_display_name} ({signal_key})",
        "entity_type": entity_type,
        "entity_id": entity_id,
        "entity_key": raw.get("entity_key"),
        "entity_display_name": entity_display_name,
        "hydraulic_system_name": hydraulic_system_name,
        "signal_key": signal_key,
        "unit": _hydraulic_signal_unit(signal_key),
        "version_number": int(raw["version_number"]),
        "version_label": str(raw["version_label"]),
        "status": str(raw["status"]),
        "content_hash": raw.get("content_hash"),
        "period_count": int(raw["period_count"]),
        "created_at": raw["created_at"],
        "updated_at": raw["updated_at"],
        "migration": _hydraulic_migration_status(raw),
        "origin": {
            "kind": HYDRAULIC_LEGACY_ORIGIN_KIND,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "signal_key": signal_key,
        },
    }


def _period_from_point(period_index: int, point: Mapping[str, Any]) -> dict[str, Any]:
    timestamp_start = datetime.fromisoformat(str(point["timestamp"]))
    duration_hours = float(point["duration_hours"])
    timestamp_end = timestamp_start + timedelta(hours=duration_hours)
    return {
        "period_index": period_index,
        "timestamp_start": timestamp_start.isoformat(),
        "timestamp_end": timestamp_end.isoformat(),
        "duration_hours": duration_hours,
    }


def build_hydraulic_catalog_detail(
    raw: Mapping[str, Any], points: list[Mapping[str, Any]]
) -> dict[str, Any]:
    detail = build_hydraulic_catalog_summary(raw)
    signal_key = detail["signal_key"]
    periods = [_period_from_point(index, point) for index, point in enumerate(points)]
    values = [
        {
            "period_index": index,
            "signal_key": signal_key,
            "value_numeric": float(point["value_m3s"]),
        }
        for index, point in enumerate(points)
    ]
    detail["signals"] = [
        {
            "signal_key": signal_key,
            "unit": detail["unit"],
            "entity_type": detail["entity_type"],
            "entity_key": detail["entity_key"],
        }
    ]
    detail["periods"] = periods
    detail["values"] = values
    detail["horizon"] = {
        "period_count": len(periods),
        "start": periods[0]["timestamp_start"] if periods else None,
        "end": periods[-1]["timestamp_end"] if periods else None,
    }
    return detail
