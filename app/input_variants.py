from __future__ import annotations

from datetime import datetime
from typing import Any

from app.time_series_catalog import TIME_SERIES_SIGNAL_CATALOG


class InputVariantRangeError(ValueError):
    pass


def _parse_bound_signal_key(
    bound_signal_key: Any,
) -> tuple[str, str | None, str | None]:
    if isinstance(bound_signal_key, tuple):
        if len(bound_signal_key) != 3:
            raise InputVariantRangeError(
                f"unsupported bound signal key {bound_signal_key!r}; expected "
                "(signal_key, entity_type, entity_id)"
            )
        signal_key, entity_type, entity_id = bound_signal_key
        return str(signal_key), _optional_scope_value(entity_type), _optional_scope_value(entity_id)
    return str(bound_signal_key), None, None


def _optional_scope_value(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _binding_label(signal_key: str, set_id: Any) -> str:
    return f"binding {signal_key!r} on time-series set {set_id}"


def _missing_coverage_error(signal_key: str, set_id: Any, start: str, end: str) -> InputVariantRangeError:
    return InputVariantRangeError(
        f"{_binding_label(signal_key, set_id)} missing coverage for [{start}, {end})"
    )


def _horizon_incompatible_error(signal_key: str, set_id: Any, reason: str) -> InputVariantRangeError:
    return InputVariantRangeError(
        f"horizon incompatible for {_binding_label(signal_key, set_id)}: {reason}; no implicit resampling"
    )


def _naive_iso_timestamp(value: str) -> str:
    """Drop the UTC offset ``time_series_periods`` timestamps carry.

    ``system_case_json.time_series[].timestamp`` is the legacy, pre-TS-2
    contract: a naive local wall-clock ISO-8601 string with no offset. TS-2
    period timestamps are instants with the set's timezone offset attached
    (e.g. ``...-03:00``); stripping the offset recovers the same wall-clock
    value the analyst originally entered, without any UTC conversion.
    """
    return datetime.fromisoformat(value).replace(tzinfo=None).isoformat()


def resolve_bound_signal_series(
    time_series_set: dict[str, Any],
    signal_key: str,
    range_start: str,
    range_end: str,
) -> list[dict[str, Any]]:
    """Slice one bound signal's periods/values to ``[range_start, range_end)``.

    TS-3 requires exact period coverage: no gaps, no resampling. Raises
    ``InputVariantRangeError`` if the set's periods do not exactly tile the
    requested range or a value is missing for ``signal_key``.
    """
    set_id = time_series_set["id"]
    periods = sorted(
        (period for period in time_series_set["periods"] if period["timestamp_start"] < range_end),
        key=lambda period: period["period_index"],
    )
    periods = [period for period in periods if period["timestamp_end"] > range_start]

    if not periods:
        raise _missing_coverage_error(signal_key, set_id, range_start, range_end)
    if periods[0]["timestamp_start"] != range_start:
        actual_start = periods[0]["timestamp_start"]
        if actual_start > range_start:
            raise _missing_coverage_error(signal_key, set_id, range_start, actual_start)
        raise _horizon_incompatible_error(
            signal_key,
            set_id,
            f"first period starts at {actual_start}, before requested range start {range_start}",
        )
    if periods[-1]["timestamp_end"] != range_end:
        actual_end = periods[-1]["timestamp_end"]
        if actual_end < range_end:
            raise _missing_coverage_error(signal_key, set_id, actual_end, range_end)
        raise _horizon_incompatible_error(
            signal_key,
            set_id,
            f"last period ends at {actual_end}, after requested range end {range_end}",
        )
    for previous, current in zip(periods, periods[1:]):
        if previous["timestamp_end"] != current["timestamp_start"]:
            if previous["timestamp_end"] < current["timestamp_start"]:
                raise _missing_coverage_error(
                    signal_key, set_id, previous["timestamp_end"], current["timestamp_start"]
                )
            raise _horizon_incompatible_error(
                signal_key,
                set_id,
                f"period ending {previous['timestamp_end']} overlaps next period start {current['timestamp_start']}",
            )

    values_by_period = {
        value["period_index"]: value["value_numeric"]
        for value in time_series_set["values"]
        if value["signal_key"] == signal_key
    }
    rows: list[dict[str, Any]] = []
    for period in periods:
        if period["period_index"] not in values_by_period:
            raise InputVariantRangeError(
                f"{_binding_label(signal_key, set_id)} missing value for period "
                f"{period['period_index']} [{period['timestamp_start']}, {period['timestamp_end']})"
            )
        rows.append(
            {
                "timestamp": _naive_iso_timestamp(period["timestamp_start"]),
                "duration_hours": period["duration_hours"],
                signal_key: values_by_period[period["period_index"]],
            }
        )
    return rows


def materialize_variant_time_series(
    bound_signal_series: dict[Any, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    """Merge per-signal period rows sharing identical timestamps into wide rows.

    Each entry in ``bound_signal_series`` is one signal's ordered rows from
    ``resolve_bound_signal_series``. All signals must share the same horizon
    (same length, same timestamps in order); TS-3 does not resample.
    """
    if not bound_signal_series:
        return []

    reference_binding_key, reference_rows = next(iter(bound_signal_series.items()))
    reference_signal, _, _ = _parse_bound_signal_key(reference_binding_key)
    merged: list[dict[str, Any]] = []
    for index, reference_row in enumerate(reference_rows):
        row = {
            "timestamp": reference_row["timestamp"],
            "duration_hours": reference_row["duration_hours"],
        }
        for binding_key, rows in bound_signal_series.items():
            signal_key, _, entity_id = _parse_bound_signal_key(binding_key)
            if len(rows) != len(reference_rows):
                raise InputVariantRangeError(
                    f"horizon incompatible: bound signal {signal_key!r} has {len(rows)} periods, "
                    f"but {reference_signal!r} has {len(reference_rows)} periods; no implicit resampling"
                )
            other_row = rows[index]
            if other_row["timestamp"] != row["timestamp"]:
                raise InputVariantRangeError(
                    f"horizon incompatible: bound signal {signal_key!r} timestamp "
                    f"{other_row['timestamp']} does not match {reference_signal!r} timestamp "
                    f"{row['timestamp']} at index {index}; no implicit resampling"
                )
            if other_row["duration_hours"] != row["duration_hours"]:
                raise InputVariantRangeError(
                    f"horizon incompatible: bound signal {signal_key!r} duration "
                    f"{other_row['duration_hours']} does not match {reference_signal!r} duration "
                    f"{row['duration_hours']} at timestamp {row['timestamp']}; no implicit resampling"
                )
            signal_definition = TIME_SERIES_SIGNAL_CATALOG.get(signal_key)
            if signal_definition is not None and signal_definition.entity_type is not None and entity_id is not None:
                signal_map = row.setdefault(signal_key, {})
                if not isinstance(signal_map, dict):
                    raise InputVariantRangeError(
                        f"bound signal {signal_key!r} mixes scalar and entity-scoped materialization"
                    )
                signal_map[entity_id] = other_row[signal_key]
            else:
                row[signal_key] = other_row[signal_key]
        merged.append(row)
    return merged
