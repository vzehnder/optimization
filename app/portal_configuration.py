from __future__ import annotations

import re
from typing import Any, Mapping


PORTAL_CONFIG_SCHEMA_VERSION = "portal_config.v1"

KPI_SIGNS = ("auto", "always", "never")
KPI_EMPHASES = ("normal", "strong")
PORTAL_CONFIGURATION_STATUSES = ("draft", "active")

# `all_series` and `plot_series` are never acceptable catalog keys: they would
# expose every canonical column instead of the declared allowlist.
FORBIDDEN_CATALOG_KEYS = frozenset({"all_series", "plot_series"})

MAX_KPI_PATH_SEGMENTS = 3
MAX_KPI_DECIMALS = 6

EXTERNAL_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
CANONICAL_KEY_PATTERN = re.compile(r"^[A-Za-z0-9_]+$")

SECTION_NAMES = ("kpis", "charts", "tables", "downloads")

DISPATCH_TABLE = "dispatch_table"
ASSET_DISPATCH_TABLE = "asset_dispatch_table"

# Fixed backend catalogs. A configured chart, series, table or column exists
# only if it appears here, so a new canonical column never becomes publishable
# by arriving in dispatch.csv.
PORTAL_CHART_CATALOG: dict[str, dict[str, Any]] = {
    "price": {
        "label": "Precio de energia",
        "source": DISPATCH_TABLE,
        "series": {
            "price_usd_per_mwh": "USD/MWh",
            "import_price_usd_per_mwh": "USD/MWh",
            "export_price_usd_per_mwh": "USD/MWh",
        },
    },
    "grid_import_export": {
        "label": "Intercambio con la red",
        "source": DISPATCH_TABLE,
        "series": {
            "grid_import_mw": "MW",
            "grid_export_mw": "MW",
            "net_grid_export_mw": "MW",
        },
    },
    "renewable_used_curtailed": {
        "label": "Renovable usada y vertida",
        "source": DISPATCH_TABLE,
        "series": {"renewable_used_mw": "MW", "renewable_curtailed_mw": "MW"},
    },
    "bess_charge_discharge_soc": {
        "label": "Bateria",
        "source": DISPATCH_TABLE,
        "series": {
            "battery_charge_mw": "MW",
            "battery_discharge_mw": "MW",
            "battery_net_discharge_mw": "MW",
            "battery_energy_mwh": "MWh",
        },
    },
    "period_profit": {
        "label": "Beneficio por periodo",
        "source": DISPATCH_TABLE,
        "series": {"period_profit_usd": "USD", "market_value_usd": "USD"},
    },
    "hydro_power": {
        "label": "Potencia hidraulica",
        "source": DISPATCH_TABLE,
        "series": {"total_hydro_power_mw": "MW"},
    },
    "hydro_flows": {
        "label": "Caudales hidraulicos",
        "source": DISPATCH_TABLE,
        "series": {
            "total_hydro_inflow_m3s": "m3/s",
            "total_hydro_turbine_flow_m3s": "m3/s",
            "total_hydro_spill_flow_m3s": "m3/s",
        },
    },
    "hydro_storage": {
        "label": "Volumen embalsado",
        "source": DISPATCH_TABLE,
        "series": {"total_hydro_storage_hm3": "hm3"},
    },
    "hydro_reservoir_elevation": {
        "label": "Cota del embalse",
        "source": ASSET_DISPATCH_TABLE,
        "series": {"hydro_reservoir_elevation_masl": "masl"},
    },
}

DISPATCH_TABLE_COLUMNS = (
    "timestamp",
    "duration_hours",
    "price_usd_per_mwh",
    "import_price_usd_per_mwh",
    "export_price_usd_per_mwh",
    "grid_import_mw",
    "grid_export_mw",
    "net_grid_export_mw",
    "renewable_used_mw",
    "renewable_curtailed_mw",
    "load_demand_mw",
    "total_hydro_power_mw",
    "total_hydro_inflow_m3s",
    "total_hydro_turbine_flow_m3s",
    "total_hydro_spill_flow_m3s",
    "total_hydro_storage_hm3",
    "total_hydro_spill_penalty_usd",
    "total_hydro_terminal_water_value_usd",
    "battery_charge_mw",
    "battery_discharge_mw",
    "battery_net_discharge_mw",
    "battery_energy_mwh",
    "battery_delta_soc_abs_mwh",
    "import_cost_usd",
    "export_revenue_usd",
    "net_market_value_usd",
    "market_value_usd",
    "battery_degradation_cost_usd",
    "curtailment_penalty_usd",
    "period_profit_usd",
)

ASSET_DISPATCH_TABLE_COLUMNS = (
    "timestamp",
    "duration_hours",
    "price_usd_per_mwh",
    "import_price_usd_per_mwh",
    "export_price_usd_per_mwh",
    "asset_id",
    "asset_type",
    "grid_import_mw",
    "grid_export_mw",
    "renewable_used_mw",
    "renewable_curtailed_mw",
    "load_demand_mw",
    "battery_charge_mw",
    "battery_discharge_mw",
    "battery_energy_mwh",
    "battery_delta_soc_abs_mwh",
    "hydro_power_mw",
    "hydro_inflow_m3s",
    "hydro_turbine_flow_m3s",
    "hydro_spill_flow_m3s",
    "hydro_inflow_volume_hm3",
    "hydro_turbine_volume_hm3",
    "hydro_spill_volume_hm3",
    "hydro_storage_hm3",
    "hydro_reservoir_elevation_masl",
    "hydro_terminal_water_value_usd",
)

PORTAL_TABLE_CATALOG: dict[str, dict[str, Any]] = {
    "system_dispatch": {
        "label": "Despacho del sistema",
        "source": DISPATCH_TABLE,
        "columns": DISPATCH_TABLE_COLUMNS,
    },
    "asset_dispatch": {
        "label": "Despacho por activo",
        "source": ASSET_DISPATCH_TABLE,
        "columns": ASSET_DISPATCH_TABLE_COLUMNS,
    },
}


# Legacy dashboard templates only carried on/off flags. The migration turns each
# visible flag into explicit entries and never enables what the template hid.
# `show_summary` used to print the whole summary document; only the single public
# scalar of that summary becomes a KPI.
MIGRATED_SUMMARY_KPIS: tuple[dict[str, Any], ...] = (
    {
        "id": "beneficio_total",
        "path": "objective_value_usd",
        "label": "Beneficio total",
        "unit": "USD",
        "decimals": 2,
        "sign": "auto",
        "emphasis": "strong",
    },
)

MIGRATED_CHART_ITEMS: tuple[tuple[str, tuple[tuple[str, str, tuple[tuple[str, str], ...]], ...]], ...] = (
    (
        "show_price_chart",
        (
            (
                "precio",
                "price",
                (
                    ("price_usd_per_mwh", "Precio"),
                    ("import_price_usd_per_mwh", "Precio de compra"),
                    ("export_price_usd_per_mwh", "Precio de venta"),
                ),
            ),
        ),
    ),
    (
        "show_grid_chart",
        (
            (
                "intercambio_red",
                "grid_import_export",
                (("grid_import_mw", "Compra"), ("grid_export_mw", "Venta")),
            ),
        ),
    ),
    (
        "show_renewable_chart",
        (
            (
                "renovable",
                "renewable_used_curtailed",
                (
                    ("renewable_used_mw", "Renovable usada"),
                    ("renewable_curtailed_mw", "Renovable vertida"),
                ),
            ),
        ),
    ),
    (
        "show_bess_chart",
        (
            (
                "bess",
                "bess_charge_discharge_soc",
                (
                    ("battery_charge_mw", "Carga"),
                    ("battery_discharge_mw", "Descarga"),
                    ("battery_energy_mwh", "Estado de carga"),
                ),
            ),
        ),
    ),
    (
        "show_profit_chart",
        (
            (
                "beneficio_periodo",
                "period_profit",
                (("period_profit_usd", "Beneficio del periodo"),),
            ),
        ),
    ),
    (
        "show_hydro_chart",
        (
            (
                "hidro_potencia",
                "hydro_power",
                (("total_hydro_power_mw", "Potencia hidraulica"),),
            ),
            (
                "hidro_caudales",
                "hydro_flows",
                (
                    ("total_hydro_inflow_m3s", "Afluente"),
                    ("total_hydro_turbine_flow_m3s", "Turbinado"),
                    ("total_hydro_spill_flow_m3s", "Vertido"),
                ),
            ),
            (
                "hidro_embalse",
                "hydro_storage",
                (("total_hydro_storage_hm3", "Volumen embalsado"),),
            ),
            (
                "hidro_cota",
                "hydro_reservoir_elevation",
                (("hydro_reservoir_elevation_masl", "Cota"),),
            ),
        ),
    ),
)

MIGRATED_TABLE_ITEMS: tuple[tuple[str, str, str], ...] = (
    ("show_system_dispatch_table", "despacho_sistema", "system_dispatch"),
    ("show_asset_dispatch_table", "despacho_activos", "asset_dispatch"),
)

COLUMN_UNIT_SUFFIXES: tuple[tuple[str, str], ...] = (
    ("_usd_per_mwh", "USD/MWh"),
    ("_mwh", "MWh"),
    ("_mw", "MW"),
    ("_m3s", "m3/s"),
    ("_hm3", "hm3"),
    ("_masl", "masl"),
    ("_usd", "USD"),
    ("_hours", "hours"),
)


class PortalConfigurationError(ValueError):
    """A portal configuration document or save request was rejected."""

    def __init__(self, message: str, *, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class StalePortalConfigurationError(PortalConfigurationError):
    """The expected revision no longer matches the stored configuration."""

    def __init__(self, message: str, *, current_revision: int):
        super().__init__(message, status_code=409)
        self.current_revision = current_revision


def default_portal_config_document() -> dict[str, Any]:
    """A structurally valid document that exposes nothing."""

    return {
        "schema_version": PORTAL_CONFIG_SCHEMA_VERSION,
        "display_name": "",
        "sections": {
            "kpis": {"enabled": False, "label": "Resumen", "items": []},
            "charts": {"enabled": False, "label": "Resultados", "items": []},
            "tables": {"enabled": False, "label": "Detalle", "items": []},
            "downloads": {"enabled": False, "label": "Descargas"},
        },
    }


def portal_config_document_from_dashboard_template(
    template: Mapping[str, Any],
    *,
    display_name: str,
) -> dict[str, Any]:
    """Translate a legacy dashboard template into an explicit portal document."""

    document = default_portal_config_document()
    document["display_name"] = display_name
    sections = document["sections"]

    if template.get("show_summary"):
        sections["kpis"]["enabled"] = True
        sections["kpis"]["items"] = [dict(item) for item in MIGRATED_SUMMARY_KPIS]

    charts = [
        {
            "id": item_id,
            "chart_key": chart_key,
            "label": PORTAL_CHART_CATALOG[chart_key]["label"],
            "series": [{"key": key, "label": label} for key, label in series],
        }
        for flag, entries in MIGRATED_CHART_ITEMS
        if template.get(flag)
        for item_id, chart_key, series in entries
    ]
    if charts:
        sections["charts"]["enabled"] = True
        sections["charts"]["items"] = charts

    row_limit = max(1, int(template.get("table_preview_limit") or 1))
    tables = [
        {
            "id": item_id,
            "table_key": table_key,
            "label": PORTAL_TABLE_CATALOG[table_key]["label"],
            "row_limit": row_limit,
            "columns": [
                {
                    "key": key,
                    "id": key,
                    "label": canonical_column_label(key),
                    "unit": canonical_column_unit(key),
                }
                for key in PORTAL_TABLE_CATALOG[table_key]["columns"]
            ],
        }
        for flag, item_id, table_key in MIGRATED_TABLE_ITEMS
        if template.get(flag)
    ]
    if tables:
        sections["tables"]["enabled"] = True
        sections["tables"]["items"] = tables

    # The publication allowlist already decided which artifacts a client may
    # download, so the migrated section keeps that decision untouched.
    sections["downloads"]["enabled"] = True
    return document


def portal_catalogs() -> dict[str, Any]:
    """The publishable vocabulary an analyst may choose from."""

    return {
        "charts": [
            {
                "key": chart_key,
                "label": entry["label"],
                "series": [
                    {"key": series_key, "label": canonical_column_label(series_key), "unit": unit}
                    for series_key, unit in entry["series"].items()
                ],
            }
            for chart_key, entry in PORTAL_CHART_CATALOG.items()
        ],
        "tables": [
            {
                "key": table_key,
                "label": entry["label"],
                "columns": [
                    {
                        "key": column,
                        "label": canonical_column_label(column),
                        "unit": canonical_column_unit(column),
                    }
                    for column in entry["columns"]
                ],
            }
            for table_key, entry in PORTAL_TABLE_CATALOG.items()
        ],
    }


def canonical_column_label(key: str) -> str:
    return key.replace("_", " ").capitalize()


def canonical_column_unit(key: str) -> str | None:
    for suffix, unit in COLUMN_UNIT_SUFFIXES:
        if key.endswith(suffix):
            return unit
    return None


def validate_portal_configuration_status(status: Any) -> str:
    if status not in PORTAL_CONFIGURATION_STATUSES:
        raise PortalConfigurationError(f"unknown portal configuration status: {status!r}")
    return str(status)


def validate_portal_config_document(document: Any) -> dict[str, Any]:
    """Reject the whole document unless it matches `portal_config.v1` exactly."""

    mapping = _require_mapping(document, "portal configuration document")
    _reject_unknown_keys(mapping, {"schema_version", "display_name", "sections"}, "document")

    schema_version = mapping.get("schema_version")
    if schema_version != PORTAL_CONFIG_SCHEMA_VERSION:
        raise PortalConfigurationError(
            f"unknown portal configuration schema version: {schema_version!r}"
        )

    display_name = _require_text(mapping.get("display_name"), "display_name")

    sections = _require_mapping(mapping.get("sections"), "sections")
    _reject_unknown_keys(sections, set(SECTION_NAMES), "sections")
    for name in SECTION_NAMES:
        if name not in sections:
            raise PortalConfigurationError(f"sections.{name} is required")

    declared_ids: set[str] = set()
    kpis = _validate_kpi_section(sections["kpis"], declared_ids)
    charts = _validate_chart_section(sections["charts"], declared_ids)
    tables = _validate_table_section(sections["tables"], declared_ids)
    downloads = _validate_downloads_section(sections["downloads"])

    return {
        "schema_version": PORTAL_CONFIG_SCHEMA_VERSION,
        "display_name": display_name,
        "sections": {
            "kpis": kpis,
            "charts": charts,
            "tables": tables,
            "downloads": downloads,
        },
    }


def _validate_kpi_section(section: Any, declared_ids: set[str]) -> dict[str, Any]:
    enabled, label, raw_items = _validate_item_section(section, "kpis")
    items = []
    for position, raw_item in enumerate(raw_items):
        where = f"sections.kpis.items[{position}]"
        item = _require_mapping(raw_item, where)
        _reject_unknown_keys(
            item,
            {"id", "path", "label", "unit", "decimals", "sign", "emphasis"},
            where,
        )
        items.append(
            {
                "id": _register_id(item.get("id"), where, declared_ids),
                "path": _validate_kpi_path(item.get("path"), where),
                "label": _require_text(item.get("label"), f"{where}.label"),
                "unit": _optional_text(item.get("unit"), f"{where}.unit"),
                "decimals": _validate_decimals(item.get("decimals"), where),
                "sign": _validate_enum(item.get("sign"), KPI_SIGNS, f"{where}.sign"),
                "emphasis": _validate_enum(
                    item.get("emphasis"), KPI_EMPHASES, f"{where}.emphasis"
                ),
            }
        )
    return {"enabled": enabled, "label": label, "items": items}


def _validate_chart_section(section: Any, declared_ids: set[str]) -> dict[str, Any]:
    enabled, label, raw_items = _validate_item_section(section, "charts")
    items = []
    for position, raw_item in enumerate(raw_items):
        where = f"sections.charts.items[{position}]"
        item = _require_mapping(raw_item, where)
        _reject_unknown_keys(item, {"id", "chart_key", "label", "series"}, where)
        chart_key = _validate_catalog_member(
            item.get("chart_key"), PORTAL_CHART_CATALOG, f"{where}.chart_key"
        )
        allowed_series = PORTAL_CHART_CATALOG[chart_key]["series"]
        raw_series = item.get("series")
        if not isinstance(raw_series, list) or not raw_series:
            raise PortalConfigurationError(f"{where}.series must be a non-empty list")
        series = []
        series_keys: set[str] = set()
        for series_position, raw_entry in enumerate(raw_series):
            series_where = f"{where}.series[{series_position}]"
            entry = _require_mapping(raw_entry, series_where)
            _reject_unknown_keys(entry, {"key", "label"}, series_where)
            key = _validate_catalog_member(
                entry.get("key"), allowed_series, f"{series_where}.key"
            )
            if key in series_keys:
                raise PortalConfigurationError(f"duplicate series key in {where}: {key}")
            series_keys.add(key)
            series.append(
                {"key": key, "label": _require_text(entry.get("label"), f"{series_where}.label")}
            )
        items.append(
            {
                "id": _register_id(item.get("id"), where, declared_ids),
                "chart_key": chart_key,
                "label": _require_text(item.get("label"), f"{where}.label"),
                "series": series,
            }
        )
    return {"enabled": enabled, "label": label, "items": items}


def _validate_table_section(section: Any, declared_ids: set[str]) -> dict[str, Any]:
    enabled, label, raw_items = _validate_item_section(section, "tables")
    items = []
    for position, raw_item in enumerate(raw_items):
        where = f"sections.tables.items[{position}]"
        item = _require_mapping(raw_item, where)
        _reject_unknown_keys(
            item, {"id", "table_key", "label", "row_limit", "columns"}, where
        )
        table_key = _validate_catalog_member(
            item.get("table_key"), PORTAL_TABLE_CATALOG, f"{where}.table_key"
        )
        allowed_columns = PORTAL_TABLE_CATALOG[table_key]["columns"]
        raw_columns = item.get("columns")
        if not isinstance(raw_columns, list) or not raw_columns:
            raise PortalConfigurationError(f"{where}.columns must be a non-empty list")
        columns = []
        column_ids: set[str] = set()
        for column_position, raw_column in enumerate(raw_columns):
            column_where = f"{where}.columns[{column_position}]"
            column = _require_mapping(raw_column, column_where)
            _reject_unknown_keys(column, {"key", "id", "label", "unit"}, column_where)
            column_id = _validate_external_id(column.get("id"), f"{column_where}.id")
            if column_id in column_ids:
                raise PortalConfigurationError(
                    f"duplicate column id in {where}: {column_id}"
                )
            column_ids.add(column_id)
            columns.append(
                {
                    "key": _validate_catalog_member(
                        column.get("key"), allowed_columns, f"{column_where}.key"
                    ),
                    "id": column_id,
                    "label": _require_text(column.get("label"), f"{column_where}.label"),
                    "unit": _optional_text(column.get("unit"), f"{column_where}.unit"),
                }
            )
        items.append(
            {
                "id": _register_id(item.get("id"), where, declared_ids),
                "table_key": table_key,
                "label": _require_text(item.get("label"), f"{where}.label"),
                "row_limit": _validate_row_limit(item.get("row_limit"), where),
                "columns": columns,
            }
        )
    return {"enabled": enabled, "label": label, "items": items}


def _validate_downloads_section(section: Any) -> dict[str, Any]:
    mapping = _require_mapping(section, "sections.downloads")
    _reject_unknown_keys(mapping, {"enabled", "label"}, "sections.downloads")
    return {
        "enabled": _require_bool(mapping.get("enabled"), "sections.downloads.enabled"),
        "label": _require_text(mapping.get("label"), "sections.downloads.label"),
    }


def _validate_item_section(section: Any, name: str) -> tuple[bool, str, list[Any]]:
    mapping = _require_mapping(section, f"sections.{name}")
    _reject_unknown_keys(mapping, {"enabled", "label", "items"}, f"sections.{name}")
    items = mapping.get("items")
    if not isinstance(items, list):
        raise PortalConfigurationError(f"sections.{name}.items must be a list")
    return (
        _require_bool(mapping.get("enabled"), f"sections.{name}.enabled"),
        _require_text(mapping.get("label"), f"sections.{name}.label"),
        items,
    )


def _validate_kpi_path(value: Any, where: str) -> str:
    if not isinstance(value, str) or not value:
        raise PortalConfigurationError(f"{where}.path must be a non-empty string")
    segments = value.split(".")
    if not 1 <= len(segments) <= MAX_KPI_PATH_SEGMENTS:
        raise PortalConfigurationError(
            f"{where}.path accepts one to {MAX_KPI_PATH_SEGMENTS} segments"
        )
    for segment in segments:
        if not CANONICAL_KEY_PATTERN.fullmatch(segment):
            raise PortalConfigurationError(f"{where}.path has an invalid segment: {segment!r}")
    return value


def _validate_decimals(value: Any, where: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise PortalConfigurationError(f"{where}.decimals must be an integer")
    if not 0 <= value <= MAX_KPI_DECIMALS:
        raise PortalConfigurationError(
            f"{where}.decimals must be between 0 and {MAX_KPI_DECIMALS}"
        )
    return value


def _validate_row_limit(value: Any, where: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise PortalConfigurationError(f"{where}.row_limit must be a positive integer")
    return value


def _validate_enum(value: Any, allowed: tuple[str, ...], where: str) -> str:
    if value not in allowed:
        raise PortalConfigurationError(
            f"{where} must be one of {', '.join(allowed)}; received {value!r}"
        )
    return str(value)


def _validate_catalog_key(value: Any, where: str) -> str:
    if not isinstance(value, str) or not CANONICAL_KEY_PATTERN.fullmatch(value):
        raise PortalConfigurationError(f"{where} is not a valid catalog key: {value!r}")
    if value in FORBIDDEN_CATALOG_KEYS:
        raise PortalConfigurationError(f"{where} may not be {value}")
    return value


def _validate_catalog_member(value: Any, catalog: Any, where: str) -> str:
    key = _validate_catalog_key(value, where)
    if key not in catalog:
        raise PortalConfigurationError(f"{where} is not in the backend catalog: {key}")
    return key


def _validate_external_id(value: Any, where: str) -> str:
    if not isinstance(value, str) or not EXTERNAL_ID_PATTERN.fullmatch(value):
        raise PortalConfigurationError(f"{where} is not a valid id: {value!r}")
    return value


def _register_id(value: Any, where: str, declared_ids: set[str]) -> str:
    identifier = _validate_external_id(value, f"{where}.id")
    if identifier in declared_ids:
        raise PortalConfigurationError(f"duplicate item id in document: {identifier}")
    declared_ids.add(identifier)
    return identifier


def _require_mapping(value: Any, where: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise PortalConfigurationError(f"{where} must be an object")
    return value


def _require_text(value: Any, where: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PortalConfigurationError(f"{where} must be a non-empty string")
    return value.strip()


def _optional_text(value: Any, where: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise PortalConfigurationError(f"{where} must be a non-empty string or null")
    return value.strip()


def _require_bool(value: Any, where: str) -> bool:
    if not isinstance(value, bool):
        raise PortalConfigurationError(f"{where} must be a boolean")
    return value


def _reject_unknown_keys(mapping: Mapping[str, Any], allowed: set[str], where: str) -> None:
    unknown = sorted(set(mapping) - allowed)
    if unknown:
        raise PortalConfigurationError(f"{where} has unknown keys: {', '.join(unknown)}")
