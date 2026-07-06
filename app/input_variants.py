from __future__ import annotations

from datetime import datetime
from typing import Any


class InputVariantRangeError(ValueError):
    pass


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
        raise InputVariantRangeError(
            f"time-series set {set_id} has no periods in range [{range_start}, {range_end})"
        )
    if periods[0]["timestamp_start"] != range_start:
        raise InputVariantRangeError(
            f"time-series set {set_id} does not cover range start {range_start}"
        )
    if periods[-1]["timestamp_end"] != range_end:
        raise InputVariantRangeError(
            f"time-series set {set_id} does not cover range end {range_end}"
        )
    for previous, current in zip(periods, periods[1:]):
        if previous["timestamp_end"] != current["timestamp_start"]:
            raise InputVariantRangeError(
                f"time-series set {set_id} has a gap between "
                f"{previous['timestamp_end']} and {current['timestamp_start']}"
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
                f"time-series set {set_id} is missing {signal_key!r} for period "
                f"{period['period_index']}"
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
    bound_signal_series: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    """Merge per-signal period rows sharing identical timestamps into wide rows.

    Each entry in ``bound_signal_series`` is one signal's ordered rows from
    ``resolve_bound_signal_series``. All signals must share the same horizon
    (same length, same timestamps in order); TS-3 does not resample.
    """
    if not bound_signal_series:
        return []

    reference_signal, reference_rows = next(iter(bound_signal_series.items()))
    merged: list[dict[str, Any]] = []
    for index, reference_row in enumerate(reference_rows):
        row = {
            "timestamp": reference_row["timestamp"],
            "duration_hours": reference_row["duration_hours"],
        }
        for signal_key, rows in bound_signal_series.items():
            if len(rows) != len(reference_rows):
                raise InputVariantRangeError(
                    f"bound signal {signal_key!r} horizon length does not match {reference_signal!r}"
                )
            other_row = rows[index]
            if other_row["timestamp"] != row["timestamp"]:
                raise InputVariantRangeError(
                    f"bound signal {signal_key!r} timestamp does not match "
                    f"{reference_signal!r} at index {index}"
                )
            row[signal_key] = other_row[signal_key]
        merged.append(row)
    return merged
