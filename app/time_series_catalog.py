from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


TIME_SERIES_DATA_KINDS = {
    "real",
    "programmed",
    "forecast",
    "simulated",
    "synthetic",
    "mixed",
}


@dataclass(frozen=True)
class TimeSeriesSignalDefinition:
    signal_key: str
    unit: str
    entity_type: str | None = None
    nonnegative: bool = False


TIME_SERIES_SIGNAL_CATALOG: dict[str, TimeSeriesSignalDefinition] = {
    "price_usd_per_mwh": TimeSeriesSignalDefinition(
        signal_key="price_usd_per_mwh",
        unit="USD/MWh",
    ),
    "import_price_usd_per_mwh": TimeSeriesSignalDefinition(
        signal_key="import_price_usd_per_mwh",
        unit="USD/MWh",
    ),
    "export_price_usd_per_mwh": TimeSeriesSignalDefinition(
        signal_key="export_price_usd_per_mwh",
        unit="USD/MWh",
    ),
    "load_demand_mw": TimeSeriesSignalDefinition(
        signal_key="load_demand_mw",
        unit="MW",
        entity_type="component:load",
        nonnegative=True,
    ),
    "renewable_available_power_mw": TimeSeriesSignalDefinition(
        signal_key="renewable_available_power_mw",
        unit="MW",
        entity_type="component:renewable",
        nonnegative=True,
    ),
    "hydro_inflow_m3s": TimeSeriesSignalDefinition(
        signal_key="hydro_inflow_m3s",
        unit="m3/s",
        entity_type="component:hydro",
        nonnegative=True,
    ),
    "natural_inflow_m3s": TimeSeriesSignalDefinition(
        signal_key="natural_inflow_m3s",
        unit="m3/s",
        entity_type="hydraulic_node",
        nonnegative=True,
    ),
    "minimum_flow_m3s": TimeSeriesSignalDefinition(
        signal_key="minimum_flow_m3s",
        unit="m3/s",
        entity_type="hydraulic_reach",
        nonnegative=True,
    ),
}


class TimeSeriesCatalogError(ValueError):
    pass


@dataclass(frozen=True)
class CatalogSignalMappingRequest:
    source_column: str
    signal_key: str
    source_unit: str | None = None


@dataclass(frozen=True)
class CatalogImportRequest:
    set_name: str
    version_label: str
    data_kind: str
    timezone: str
    timestamp_column: str
    duration_hours_column: str
    signal_mappings: list[CatalogSignalMappingRequest]
    value_column: str | None = None
    signal_key: str | None = None
    source_unit: str | None = None


@dataclass(frozen=True)
class CatalogPeriod:
    period_index: int
    timestamp_start: str
    timestamp_end: str
    duration_hours: float


@dataclass(frozen=True)
class CatalogSignal:
    signal_key: str
    unit: str
    source_column: str
    source_unit: str
    entity_type: str | None = None
    entity_key: str | None = None


@dataclass(frozen=True)
class CatalogValue:
    period_index: int
    signal_key: str
    value_numeric: float
    source_row_number: int


@dataclass(frozen=True)
class CatalogValueEdit:
    period_index: int
    signal_key: str
    value_text: str


@dataclass(frozen=True)
class PreparedCatalogValueEdit:
    period_index: int
    signal_key: str
    value_numeric: float


@dataclass(frozen=True)
class PreparedTimeSeriesCatalogImport:
    set_name: str
    version_label: str
    data_kind: str
    timezone: str
    signals: list[CatalogSignal]
    periods: list[CatalogPeriod]
    values: list[CatalogValue]
    content_hash: str
    mapping_summary: dict[str, Any]


def prepare_time_series_catalog_import(
    *,
    rows: list[dict[str, Any]],
    request: CatalogImportRequest,
) -> PreparedTimeSeriesCatalogImport:
    if request.data_kind not in TIME_SERIES_DATA_KINDS:
        raise TimeSeriesCatalogError(f"unsupported data_kind {request.data_kind!r}")
    if not rows:
        raise TimeSeriesCatalogError("source file does not contain data rows")

    timezone = resolve_timezone(request.timezone)
    signal_mappings = normalize_catalog_signal_mappings(request)
    available_columns = {
        str(column)
        for row in rows
        for column in row
    }
    if request.timestamp_column not in available_columns:
        raise TimeSeriesCatalogError(
            f"timestamp column {request.timestamp_column!r} was not found in source preview"
        )
    if request.duration_hours_column not in available_columns:
        raise TimeSeriesCatalogError(
            f"duration column {request.duration_hours_column!r} was not found in source preview"
        )

    signals: list[CatalogSignal] = []
    definitions_by_signal_key: dict[str, TimeSeriesSignalDefinition] = {}
    seen_source_columns: set[str] = set()
    seen_signal_keys: set[str] = set()
    for signal_mapping in signal_mappings:
        definition = TIME_SERIES_SIGNAL_CATALOG.get(signal_mapping.signal_key)
        if definition is None:
            raise TimeSeriesCatalogError(
                f"unsupported signal_key {signal_mapping.signal_key!r} for column "
                f"{signal_mapping.source_column!r}"
            )
        if signal_mapping.source_column not in available_columns:
            raise TimeSeriesCatalogError(
                f"column {signal_mapping.source_column!r} was not found for signal "
                f"{signal_mapping.signal_key!r}"
            )
        if signal_mapping.source_column in seen_source_columns:
            raise TimeSeriesCatalogError(
                f"column {signal_mapping.source_column!r} is mapped more than once"
            )
        if signal_mapping.signal_key in seen_signal_keys:
            raise TimeSeriesCatalogError(
                f"signal_key {signal_mapping.signal_key!r} is mapped more than once"
            )
        source_unit = normalize_source_unit(signal_mapping.source_unit, definition.unit)
        if not units_match(source_unit, definition.unit):
            raise TimeSeriesCatalogError(
                f"column {signal_mapping.source_column!r}: source unit {source_unit!r} does "
                f"not match canonical unit {definition.unit!r} for signal "
                f"{signal_mapping.signal_key!r}"
            )
        signals.append(
            CatalogSignal(
                signal_key=definition.signal_key,
                unit=definition.unit,
                source_column=signal_mapping.source_column,
                source_unit=source_unit,
                entity_type=definition.entity_type,
                entity_key=None,
            )
        )
        definitions_by_signal_key[definition.signal_key] = definition
        seen_source_columns.add(signal_mapping.source_column)
        seen_signal_keys.add(signal_mapping.signal_key)

    periods: list[CatalogPeriod] = []
    values: list[CatalogValue] = []
    seen_timestamp_rows: dict[datetime, int] = {}
    for period_index, row in enumerate(rows):
        source_row_number = period_index + 2
        timestamp_text = str(row.get(request.timestamp_column) or "").strip()
        if not timestamp_text:
            raise TimeSeriesCatalogError(f"row {source_row_number}: timestamp is required")
        timestamp_start = parse_catalog_timestamp(timestamp_text, timezone, source_row_number)
        duplicate_row_number = seen_timestamp_rows.get(timestamp_start)
        if duplicate_row_number is not None:
            raise TimeSeriesCatalogError(
                f"row {source_row_number}: duplicate timestamp {timestamp_text!r} "
                f"(already used by row {duplicate_row_number})"
            )
        seen_timestamp_rows[timestamp_start] = source_row_number
        if periods:
            previous_period = periods[-1]
            previous_row_number = previous_period.period_index + 2
            if timestamp_start < datetime.fromisoformat(previous_period.timestamp_start):
                raise TimeSeriesCatalogError(
                    f"row {source_row_number}: timestamp {timestamp_text!r} must come "
                    f"after row {previous_row_number} ({previous_period.timestamp_start!r}); "
                    "periods must be ordered"
                )
            if timestamp_start < datetime.fromisoformat(previous_period.timestamp_end):
                raise TimeSeriesCatalogError(
                    f"row {source_row_number}: period starts before row "
                    f"{previous_row_number} ends ({previous_period.timestamp_end!r}); "
                    f"row {previous_row_number} duration is incoherent"
                )

        duration_text = str(row.get(request.duration_hours_column) or "").strip()
        duration_hours = parse_catalog_float(
            duration_text,
            source_row_number,
            request.duration_hours_column,
        )
        if duration_hours <= 0:
            raise TimeSeriesCatalogError(
                f"row {source_row_number}: {request.duration_hours_column} must be positive"
            )
        timestamp_end = timestamp_start + timedelta(hours=duration_hours)

        periods.append(
            CatalogPeriod(
                period_index=period_index,
                timestamp_start=timestamp_start.isoformat(),
                timestamp_end=timestamp_end.isoformat(),
                duration_hours=duration_hours,
            )
        )
        for signal in signals:
            value_text = str(row.get(signal.source_column) or "").strip()
            value_numeric = parse_catalog_float(
                value_text,
                source_row_number,
                signal.source_column,
            )
            definition = definitions_by_signal_key[signal.signal_key]
            if definition.nonnegative and value_numeric < 0:
                raise TimeSeriesCatalogError(
                    f"row {source_row_number}: column {signal.source_column!r} mapped to "
                    f"{signal.signal_key} must be nonnegative"
                )
            values.append(
                CatalogValue(
                    period_index=period_index,
                    signal_key=signal.signal_key,
                    value_numeric=value_numeric,
                    source_row_number=source_row_number,
                )
            )

    mapping_summary = {
        "timestamp_column": request.timestamp_column,
        "duration_hours_column": request.duration_hours_column,
        "signals": [
            {
                "source_column": signal.source_column,
                "signal_key": signal.signal_key,
                "source_unit": signal.source_unit,
                "canonical_unit": signal.unit,
            }
            for signal in signals
        ],
    }
    content_hash = compute_catalog_content_hash(
        set_name=request.set_name,
        version_label=request.version_label,
        data_kind=request.data_kind,
        timezone=request.timezone,
        signals=[signal.__dict__ for signal in signals],
        periods=[period.__dict__ for period in periods],
        values=[value.__dict__ for value in values],
    )
    return PreparedTimeSeriesCatalogImport(
        set_name=request.set_name,
        version_label=request.version_label,
        data_kind=request.data_kind,
        timezone=request.timezone,
        signals=signals,
        periods=periods,
        values=values,
        content_hash=content_hash,
        mapping_summary=mapping_summary,
    )


def normalize_catalog_signal_mappings(
    request: CatalogImportRequest,
) -> list[CatalogSignalMappingRequest]:
    normalized = [
        CatalogSignalMappingRequest(
            source_column=str(item.source_column).strip(),
            signal_key=str(item.signal_key).strip(),
            source_unit=normalize_optional_text(item.source_unit),
        )
        for item in request.signal_mappings
        if str(item.source_column).strip() and str(item.signal_key).strip()
    ]
    if normalized:
        return normalized
    if request.value_column and request.signal_key:
        return [
            CatalogSignalMappingRequest(
                source_column=str(request.value_column).strip(),
                signal_key=str(request.signal_key).strip(),
                source_unit=normalize_optional_text(request.source_unit),
            )
        ]
    raise TimeSeriesCatalogError("at least one signal mapping is required")


def normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def normalize_source_unit(source_unit: str | None, canonical_unit: str) -> str:
    return normalize_optional_text(source_unit) or canonical_unit


def units_match(source_unit: str, canonical_unit: str) -> bool:
    return normalize_unit_token(source_unit) == normalize_unit_token(canonical_unit)


def normalize_unit_token(value: str) -> str:
    return "".join(value.split()).lower()


def resolve_timezone(timezone_name: str) -> ZoneInfo:
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as error:
        raise TimeSeriesCatalogError(f"timezone {timezone_name!r} is not a valid IANA timezone") from error


def parse_catalog_timestamp(value: str, timezone: ZoneInfo, row_number: int) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise TimeSeriesCatalogError(
            f"row {row_number}: timestamp {value!r} must be ISO-8601"
        ) from error
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone)
    return parsed.astimezone(timezone)


def parse_catalog_float(value: str, row_number: int, column_name: str) -> float:
    try:
        number = float(value)
    except ValueError as error:
        raise TimeSeriesCatalogError(f"row {row_number}: {column_name} must be numeric") from error
    if not math.isfinite(number):
        raise TimeSeriesCatalogError(f"row {row_number}: {column_name} must be finite")
    return number


def catalog_content_hash(value: Any) -> str:
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def compute_catalog_content_hash(
    *,
    set_name: str,
    version_label: str,
    data_kind: str,
    timezone: str,
    signals: list[dict[str, Any]],
    periods: list[dict[str, Any]],
    values: list[dict[str, Any]],
) -> str:
    return catalog_content_hash(
        {
            "set_name": set_name,
            "version_label": version_label,
            "data_kind": data_kind,
            "timezone": timezone,
            "signals": signals,
            "periods": periods,
            "values": values,
        }
    )


def validate_catalog_value_edits(
    *,
    edits: list[CatalogValueEdit],
    signal_definitions: dict[str, TimeSeriesSignalDefinition],
    known_period_indexes: set[int],
) -> list[PreparedCatalogValueEdit]:
    if not edits:
        raise TimeSeriesCatalogError("at least one edit is required")

    prepared: list[PreparedCatalogValueEdit] = []
    for edit_number, edit in enumerate(edits, start=1):
        if edit.period_index not in known_period_indexes:
            raise TimeSeriesCatalogError(
                f"edit {edit_number}: period {edit.period_index} is not part of "
                "this time-series set"
            )
        definition = signal_definitions.get(edit.signal_key)
        if definition is None:
            raise TimeSeriesCatalogError(
                f"edit {edit_number}: signal_key {edit.signal_key!r} is not part of "
                "this time-series set"
            )
        try:
            value_numeric = float(edit.value_text)
        except ValueError as error:
            raise TimeSeriesCatalogError(
                f"edit {edit_number}: {edit.signal_key} at period {edit.period_index} "
                "must be numeric"
            ) from error
        if not math.isfinite(value_numeric):
            raise TimeSeriesCatalogError(
                f"edit {edit_number}: {edit.signal_key} at period {edit.period_index} "
                "must be finite"
            )
        if definition.nonnegative and value_numeric < 0:
            raise TimeSeriesCatalogError(
                f"edit {edit_number}: {edit.signal_key} at period {edit.period_index} "
                "must be nonnegative"
            )
        prepared.append(
            PreparedCatalogValueEdit(
                period_index=edit.period_index,
                signal_key=edit.signal_key,
                value_numeric=value_numeric,
            )
        )
    return prepared
