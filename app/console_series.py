"""Pure rules for the console's series editing surface.

Nothing here touches the database. The console resolves external group and
column ids to canonical sets in the store; these functions own the grammar the
operator sees: allowed granularities, the row grid, the opaque concurrency
token and the coordinates a failed save points at.
"""

from __future__ import annotations

import hashlib
import math
from datetime import datetime
from typing import Any, Mapping, Sequence

from app.input_variants import InputVariantRangeError, resolve_bound_signal_series


# A granularity is the widest window the operator may load and edit at once.
# Rows always stay native periods: the console never aggregates values it would
# then have to split again on the way back in.
GRANULARITY_WINDOW_HOURS: dict[str, float | None] = {
    "day": 24.0,
    "week": 24.0 * 7,
    "month": 24.0 * 31,
    "full_horizon": None,
}


class ConsoleSeriesError(ValueError):
    """A console-side series problem stated in external coordinates."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int = 400,
        cells: Sequence[Mapping[str, Any]] = (),
        total_cells: int | None = None,
        configuration_target: Mapping[str, Any] | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.cells = [dict(cell) for cell in cells]
        self.total_cells = len(self.cells) if total_cells is None else total_cells
        self.configuration_target = (
            dict(configuration_target) if configuration_target is not None else None
        )


def range_hours(range_start: str, range_end: str) -> float:
    """How long the requested window is, in hours."""

    start = datetime.fromisoformat(str(range_start))
    end = datetime.fromisoformat(str(range_end))
    return (end - start).total_seconds() / 3600.0


def validate_console_granularity(
    granularity: Any,
    *,
    allowed: Sequence[str],
    hours: float,
) -> str:
    """Accept a granularity the group declares and a window it can hold."""

    if granularity not in GRANULARITY_WINDOW_HOURS:
        raise ConsoleSeriesError(f"unknown granularity: {granularity!r}")
    if granularity not in allowed:
        raise ConsoleSeriesError(
            f"granularity {granularity} is not configured for this group"
        )
    window = GRANULARITY_WINDOW_HOURS[str(granularity)]
    if window is not None and hours > window:
        raise ConsoleSeriesError(
            f"the selected range is longer than the {granularity} granularity allows"
        )
    return str(granularity)


def console_group_values_token(entries: Sequence[tuple[int, str]]) -> str:
    """An opaque token that changes when any set behind the group changes.

    It carries no set id, revision or hash of its own: the operator receives a
    token and hands it back, and only the store can tell what it stood for.
    """

    digest = hashlib.sha256()
    for set_id, content_hash in sorted(entries):
        digest.update(f"{set_id}:{content_hash}\n".encode("utf-8"))
    return digest.hexdigest()[:32]


def build_console_group_rows(
    *,
    columns: Sequence[Mapping[str, Any]],
    range_start: str,
    range_end: str,
) -> list[dict[str, Any]]:
    """Slice every column of a group to one aligned, fully covered grid.

    Each column carries its resolved ``set`` and ``signal_key``. Coverage is
    the existing exact-tiling rule: the console never resamples and never
    invents a period.
    """

    timestamps: list[str] | None = None
    values_by_column: dict[str, list[float]] = {}
    for column in columns:
        time_series_set = column["set"]
        series = resolve_bound_signal_series(
            time_series_set, str(column["signal_key"]), range_start, range_end
        )
        periods = [
            period
            for period in sorted(
                time_series_set["periods"], key=lambda period: period["period_index"]
            )
            if period["timestamp_start"] < range_end
            and period["timestamp_end"] > range_start
        ]
        column_timestamps = [str(period["timestamp_start"]) for period in periods]
        if timestamps is None:
            timestamps = column_timestamps
        elif column_timestamps != timestamps:
            raise InputVariantRangeError(
                "the columns of this group do not share the same periods; "
                "no implicit resampling"
            )
        values_by_column[str(column["id"])] = [
            row[str(column["signal_key"])] for row in series
        ]

    return [
        {
            "index": index,
            "timestamp": timestamp,
            "values": {
                column_id: values[index] for column_id, values in values_by_column.items()
            },
        }
        for index, timestamp in enumerate(timestamps or [])
    ]


def console_range_period_indexes(
    time_series_set: Mapping[str, Any], range_start: str, range_end: str
) -> list[int]:
    """Map each visible row position back to its canonical period index."""

    return [
        int(period["period_index"])
        for period in sorted(
            time_series_set["periods"], key=lambda period: period["period_index"]
        )
        if period["timestamp_start"] < range_end and period["timestamp_end"] > range_start
    ]


MAX_REPORTED_CELLS = 100


def prepare_console_cell_edits(
    *,
    cells: Sequence[Mapping[str, Any]],
    columns: Sequence[Mapping[str, Any]],
    rows: Sequence[Mapping[str, Any]],
    group_id: str,
) -> list[dict[str, Any]]:
    """Validate every cell of an all-or-nothing block in external coordinates.

    All cells are checked; at most ``MAX_REPORTED_CELLS`` are reported back.
    One bad cell rejects the whole block, so nothing is written.
    """

    columns_by_id = {str(column["id"]): column for column in columns}
    failures: list[dict[str, Any]] = []
    prepared: list[dict[str, Any]] = []
    seen: set[tuple[str, int]] = set()

    def fail(column_id: Any, row_index: Any, message: str) -> None:
        failures.append(
            {
                "group_id": group_id,
                "column_id": str(column_id),
                "row_index": row_index if isinstance(row_index, int) else None,
                "message": message,
            }
        )

    for cell in cells:
        column_id = str(cell.get("column_id") or "")
        row_index = cell.get("row_index")
        column = columns_by_id.get(column_id)
        if column is None:
            fail(column_id, row_index, "la columna no existe en este grupo")
            continue
        if not column["editable"]:
            fail(column_id, row_index, "la columna no es editable")
            continue
        if (
            isinstance(row_index, bool)
            or not isinstance(row_index, int)
            or row_index < 0
            or row_index >= len(rows)
        ):
            fail(column_id, row_index, "la fila esta fuera del tramo seleccionado")
            continue
        key = (column_id, int(row_index))
        if key in seen:
            fail(column_id, row_index, "la celda aparece dos veces en el bloque")
            continue
        seen.add(key)
        value = cell.get("value")
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            fail(column_id, row_index, "el valor debe ser numerico")
            continue
        number = float(value)
        if not math.isfinite(number):
            fail(column_id, row_index, "el valor debe ser finito")
            continue
        if column["nonnegative"] and number < 0:
            fail(column_id, row_index, "el valor no admite negativos")
            continue
        prepared.append(
            {
                "column_id": column_id,
                "row_index": int(row_index),
                "value": number,
                "previous_value": rows[int(row_index)]["values"].get(column_id),
            }
        )

    if failures:
        raise ConsoleSeriesError(
            "el bloque tiene celdas invalidas y no se guardo nada",
            cells=failures[:MAX_REPORTED_CELLS],
            total_cells=len(failures),
        )
    return prepared
