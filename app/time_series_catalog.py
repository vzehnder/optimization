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
class CatalogImportRequest:
    set_name: str
    version_label: str
    data_kind: str
    timezone: str
    timestamp_column: str
    duration_hours_column: str
    value_column: str
    signal_key: str


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
    entity_type: str | None = None
    entity_key: str | None = None


@dataclass(frozen=True)
class CatalogValue:
    period_index: int
    signal_key: str
    value_numeric: float
    source_row_number: int


@dataclass(frozen=True)
class PreparedTimeSeriesCatalogImport:
    set_name: str
    version_label: str
    data_kind: str
    timezone: str
    signal: CatalogSignal
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

    definition = TIME_SERIES_SIGNAL_CATALOG.get(request.signal_key)
    if definition is None:
        raise TimeSeriesCatalogError(f"unsupported signal_key {request.signal_key!r}")

    timezone = resolve_timezone(request.timezone)
    periods: list[CatalogPeriod] = []
    values: list[CatalogValue] = []
    for period_index, row in enumerate(rows):
        source_row_number = period_index + 2
        timestamp_text = str(row.get(request.timestamp_column) or "").strip()
        if not timestamp_text:
            raise TimeSeriesCatalogError(f"row {source_row_number}: timestamp is required")
        timestamp_start = parse_catalog_timestamp(timestamp_text, timezone)

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

        value_text = str(row.get(request.value_column) or "").strip()
        value_numeric = parse_catalog_float(
            value_text,
            source_row_number,
            request.value_column,
        )
        if definition.nonnegative and value_numeric < 0:
            raise TimeSeriesCatalogError(
                f"row {source_row_number}: {request.signal_key} must be nonnegative"
            )

        periods.append(
            CatalogPeriod(
                period_index=period_index,
                timestamp_start=timestamp_start.isoformat(),
                timestamp_end=timestamp_end.isoformat(),
                duration_hours=duration_hours,
            )
        )
        values.append(
            CatalogValue(
                period_index=period_index,
                signal_key=request.signal_key,
                value_numeric=value_numeric,
                source_row_number=source_row_number,
            )
        )

    signal = CatalogSignal(
        signal_key=definition.signal_key,
        unit=definition.unit,
        entity_type=None,
        entity_key=None,
    )
    mapping_summary = {
        "timestamp_column": request.timestamp_column,
        "duration_hours_column": request.duration_hours_column,
        "value_column": request.value_column,
        "signal_key": request.signal_key,
        "unit": definition.unit,
    }
    content_hash = catalog_content_hash(
        {
            "set_name": request.set_name,
            "version_label": request.version_label,
            "data_kind": request.data_kind,
            "timezone": request.timezone,
            "signal": signal.__dict__,
            "periods": [period.__dict__ for period in periods],
            "values": [value.__dict__ for value in values],
        }
    )
    return PreparedTimeSeriesCatalogImport(
        set_name=request.set_name,
        version_label=request.version_label,
        data_kind=request.data_kind,
        timezone=request.timezone,
        signal=signal,
        periods=periods,
        values=values,
        content_hash=content_hash,
        mapping_summary=mapping_summary,
    )


def resolve_timezone(timezone_name: str) -> ZoneInfo:
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as error:
        raise TimeSeriesCatalogError(f"timezone {timezone_name!r} is not a valid IANA timezone") from error


def parse_catalog_timestamp(value: str, timezone: ZoneInfo) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise TimeSeriesCatalogError(f"timestamp {value!r} must be ISO-8601") from error
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
