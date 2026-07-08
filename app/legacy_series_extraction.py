from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from app.time_series_catalog import (
    TIME_SERIES_DATA_KINDS,
    TIME_SERIES_SIGNAL_CATALOG,
    CatalogPeriod,
    CatalogSignal,
    CatalogValue,
    TimeSeriesCatalogError,
    compute_catalog_content_hash,
    parse_catalog_timestamp,
    resolve_timezone,
)
from app.time_series_ingestion import find_source, mapped_asset_columns, mapped_column


class LegacyDraftExtractionError(TimeSeriesCatalogError):
    pass


_ENTITY_TYPE_BY_ASSET_TYPE = {
    "renewable": "component:renewable",
    "load": "component:load",
    "hydro": "component:hydro",
}


@dataclass(frozen=True)
class PreparedDraftSeriesExtraction:
    set_name: str
    version_label: str
    data_kind: str
    timezone: str
    signals: list[CatalogSignal]
    periods: list[CatalogPeriod]
    values: list[CatalogValue]
    content_hash: str


def prepare_draft_series_extraction(
    *,
    document: dict[str, Any],
    source_id: str,
    set_name: str,
    version_label: str,
    data_kind: str,
    timezone_name: str,
) -> PreparedDraftSeriesExtraction:
    if data_kind not in TIME_SERIES_DATA_KINDS:
        raise LegacyDraftExtractionError(f"unsupported data_kind {data_kind!r}")
    timezone = resolve_timezone(timezone_name)

    try:
        source = find_source(document, source_id)
    except KeyError as error:
        raise LegacyDraftExtractionError(str(error)) from error

    validation = source.get("validation")
    if not isinstance(validation, dict) or not validation.get("ok"):
        raise LegacyDraftExtractionError(
            f"time-series source {source_id!r} has not passed mapping validation"
        )
    validated_rows = source.get("validated_rows")
    if not isinstance(validated_rows, list) or not validated_rows:
        raise LegacyDraftExtractionError(
            f"time-series source {source_id!r} has no validated rows to extract"
        )
    mapping = source.get("mapping")
    if not isinstance(mapping, dict):
        raise LegacyDraftExtractionError(
            f"time-series source {source_id!r} has no recorded column mapping"
        )

    signal_specs = _discover_signal_specs(mapping, document)
    if not signal_specs:
        raise LegacyDraftExtractionError(
            f"time-series source {source_id!r} has no mapped signals to extract"
        )

    signals = [
        CatalogSignal(
            signal_key=signal_key,
            unit=TIME_SERIES_SIGNAL_CATALOG[signal_key].unit,
            source_column=source_column,
            source_unit=TIME_SERIES_SIGNAL_CATALOG[signal_key].unit,
            entity_type=entity_type,
            entity_key=entity_key,
        )
        for signal_key, entity_type, entity_key, source_column in signal_specs
    ]

    periods: list[CatalogPeriod] = []
    values: list[CatalogValue] = []
    for period_index, row in enumerate(validated_rows):
        if not isinstance(row, dict):
            raise LegacyDraftExtractionError(f"validated row {period_index} must be an object")
        source_row_number = period_index + 2
        timestamp_text = str(row.get("timestamp") or "").strip()
        if not timestamp_text:
            raise LegacyDraftExtractionError(f"validated row {period_index}: timestamp is required")
        timestamp_start = parse_catalog_timestamp(timestamp_text, timezone, source_row_number)
        duration_hours = row.get("duration_hours")
        if not isinstance(duration_hours, (int, float)):
            raise LegacyDraftExtractionError(
                f"validated row {period_index}: duration_hours must be numeric"
            )
        timestamp_end = timestamp_start + timedelta(hours=float(duration_hours))
        periods.append(
            CatalogPeriod(
                period_index=period_index,
                timestamp_start=timestamp_start.isoformat(),
                timestamp_end=timestamp_end.isoformat(),
                duration_hours=float(duration_hours),
            )
        )
        for signal_key, _entity_type, entity_key, _source_column in signal_specs:
            values.append(
                CatalogValue(
                    period_index=period_index,
                    signal_key=signal_key,
                    value_numeric=_row_signal_value(row, signal_key, entity_key, period_index),
                    source_row_number=source_row_number,
                    entity_key=entity_key,
                )
            )

    content_hash = compute_catalog_content_hash(
        set_name=set_name,
        version_label=version_label,
        data_kind=data_kind,
        timezone=timezone_name,
        signals=[signal.__dict__ for signal in signals],
        periods=[period.__dict__ for period in periods],
        values=[value.__dict__ for value in values],
    )
    return PreparedDraftSeriesExtraction(
        set_name=set_name,
        version_label=version_label,
        data_kind=data_kind,
        timezone=timezone_name,
        signals=signals,
        periods=periods,
        values=values,
        content_hash=content_hash,
    )


def _discover_signal_specs(
    mapping: dict[str, Any],
    document: dict[str, Any],
) -> list[tuple[str, str | None, str | None, str | None]]:
    specs: list[tuple[str, str | None, str | None, str | None]] = []

    import_price_column = mapped_column(mapping, "import_price_usd_per_mwh")
    export_price_column = mapped_column(mapping, "export_price_usd_per_mwh")
    legacy_price_column = mapped_column(mapping, "price_usd_per_mwh")
    if import_price_column or export_price_column:
        specs.append(("import_price_usd_per_mwh", None, None, import_price_column))
        specs.append(("export_price_usd_per_mwh", None, None, export_price_column))
    elif legacy_price_column:
        specs.append(("price_usd_per_mwh", None, None, legacy_price_column))

    for asset_type, signal_key in (
        ("renewable", "renewable_available_power_mw"),
        ("load", "load_demand_mw"),
        ("hydro", "hydro_inflow_m3s"),
    ):
        for asset_id, column in mapped_asset_columns(mapping, document, asset_type, signal_key):
            if column:
                specs.append((signal_key, _ENTITY_TYPE_BY_ASSET_TYPE[asset_type], asset_id, column))

    return specs


def _row_signal_value(
    row: dict[str, Any],
    signal_key: str,
    entity_key: str | None,
    period_index: int,
) -> float:
    if entity_key is None:
        value = row.get(signal_key)
        label = signal_key
    else:
        container = row.get(signal_key)
        if not isinstance(container, dict):
            raise LegacyDraftExtractionError(
                f"validated row {period_index}: {signal_key} must be an object"
            )
        value = container.get(entity_key)
        label = f"{signal_key}.{entity_key}"
    if not isinstance(value, (int, float)):
        raise LegacyDraftExtractionError(f"validated row {period_index}: {label} must be numeric")
    return float(value)
