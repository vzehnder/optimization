from __future__ import annotations

from typing import Any, Mapping


CLASSIFICATION_CONTRACT_VERSION = 1


COMPATIBILITY_ERROR_CATALOG = {
    "TS_COMPAT_SIGNAL_UNAVAILABLE": (
        "timeseries.compatibility.signal_unavailable",
        "signal_id",
        "La señal no está disponible con una revisión sellada.",
    ),
    "TS_COMPAT_SEMANTIC_TYPE_INACTIVE": (
        "timeseries.compatibility.semantic_type_inactive",
        "semantic_type_key",
        "El tipo semántico no está disponible.",
    ),
    "TS_COMPAT_ROLE_INACTIVE": (
        "timeseries.compatibility.role_inactive",
        "binding_role_key",
        "El rol funcional no está disponible.",
    ),
    "TS_COMPAT_OBJECT_UNAVAILABLE": (
        "timeseries.compatibility.object_unavailable",
        "linkable_object_id",
        "El objeto no está disponible para vinculación.",
    ),
    "TS_COMPAT_OBJECT_OWNER_MISMATCH": (
        "timeseries.compatibility.object_owner_mismatch",
        "linkable_object_id",
        "La serie específica pertenece a otro objeto.",
    ),
    "TS_COMPAT_SIGNAL_PURPOSE_NOT_INPUT": (
        "timeseries.compatibility.signal_purpose_not_input",
        "signal_id",
        "La señal no es una entrada reutilizable.",
    ),
    "TS_COMPAT_ROLE_USAGE_NOT_ALLOWED": (
        "timeseries.compatibility.role_usage_not_allowed",
        "usage",
        "El rol no admite el uso solicitado.",
    ),
    "TS_COMPAT_SEMANTIC_TYPE_NOT_ALLOWED": (
        "timeseries.compatibility.semantic_type_not_allowed",
        "semantic_type_key",
        "El tipo semántico no está permitido para el rol.",
    ),
    "TS_COMPAT_OBJECT_TYPE_NOT_ALLOWED": (
        "timeseries.compatibility.object_type_not_allowed",
        "object_type_key",
        "La serie no admite este tipo de objeto para el rol seleccionado.",
    ),
    "TS_COMPAT_DIMENSION_MISMATCH": (
        "timeseries.compatibility.dimension_mismatch",
        "semantic_type_key",
        "Las dimensiones de la señal, el tipo y el rol no coinciden.",
    ),
    "TS_COMPAT_UNIT_MISMATCH": (
        "timeseries.compatibility.unit_mismatch",
        "unit_key",
        "La unidad no coincide exactamente con la unidad canónica.",
    ),
    "TS_COMPAT_SCOPE_NOT_ACCESSIBLE": (
        "timeseries.compatibility.scope_not_accessible",
        "signal_id",
        "La fuente no es accesible en este contexto.",
    ),
    "TS_COMPAT_PROJECT_CONTEXT_MISMATCH": (
        "timeseries.compatibility.project_context_mismatch",
        "linkable_object_id",
        "El objeto no pertenece al contexto de proyecto.",
    ),
    "TS_COMPAT_ASSOCIATION_MISMATCH": (
        "timeseries.compatibility.association_mismatch",
        "catalog_association_id",
        "La asociación no coincide con la señal, el objeto y el rol.",
    ),
    "TS_COMPAT_CONTRACT_CHANGED": (
        "timeseries.compatibility.contract_changed",
        "compatibility_fingerprint",
        "El contrato de compatibilidad observado ya no está vigente.",
    ),
    "TS_COMPAT_TRANSFORMATION_REQUIRED": (
        "timeseries.compatibility.transformation_required",
        "signal_id",
        "La entrada requiere una transformación explícita.",
    ),
    "TS_COMPAT_TRANSFORM_PORT_MISSING": (
        "timeseries.compatibility.transform_port_missing",
        "port_key",
        "Falta una entrada requerida de la transformación.",
    ),
    "TS_COMPAT_TRANSFORM_PORT_CARDINALITY": (
        "timeseries.compatibility.transform_port_cardinality",
        "port_key",
        "La cardinalidad de entradas de la transformación no es válida.",
    ),
    "TS_COMPAT_TRANSFORM_INPUT_NOT_ALLOWED": (
        "timeseries.compatibility.transform_input_not_allowed",
        "port_key",
        "Una entrada no cumple el contrato de la transformación.",
    ),
    "TS_COMPAT_TRANSFORM_HORIZON_MISMATCH": (
        "timeseries.compatibility.transform_horizon_mismatch",
        "port_key",
        "Las entradas no cumplen la alineación temporal declarada.",
    ),
    "TS_COMPAT_TRANSFORM_OUTPUT_NOT_BINDABLE": (
        "timeseries.compatibility.transform_output_not_bindable",
        "binding_role_key",
        "La salida materializada no cumple el rol de destino.",
    ),
}


def compatibility_error(code: str, context: dict[str, Any]) -> dict[str, Any]:
    message_key, field, message = COMPATIBILITY_ERROR_CATALOG[code]
    return {
        "code": code,
        "message_key": message_key,
        "message": message,
        "field": field,
        "context": context,
    }


class ClassificationContractDriftError(RuntimeError):
    code = "TS_CLASSIFICATION_CONTRACT_DIVERGED"

    def __init__(self, *, context: dict[str, Any]):
        self.context = context
        super().__init__(f"{self.code}: {context}")


SIGNAL_REGISTRY_CONTRACT = {
    "price_usd_per_mwh": {
        "signal_key": "price_usd_per_mwh",
        "unit": "USD/MWh",
        "entity_type": None,
        "nonnegative": False,
        "resampling_methods": ("mean",),
    },
    "import_price_usd_per_mwh": {
        "signal_key": "import_price_usd_per_mwh",
        "unit": "USD/MWh",
        "entity_type": None,
        "nonnegative": False,
        "resampling_methods": ("mean",),
    },
    "export_price_usd_per_mwh": {
        "signal_key": "export_price_usd_per_mwh",
        "unit": "USD/MWh",
        "entity_type": None,
        "nonnegative": False,
        "resampling_methods": ("mean",),
    },
    "load_demand_mw": {
        "signal_key": "load_demand_mw",
        "unit": "MW",
        "entity_type": "component:load",
        "nonnegative": True,
        "resampling_methods": ("mean",),
    },
    "renewable_available_power_mw": {
        "signal_key": "renewable_available_power_mw",
        "unit": "MW",
        "entity_type": "component:renewable",
        "nonnegative": True,
        "resampling_methods": ("mean",),
    },
    "hydro_inflow_m3s": {
        "signal_key": "hydro_inflow_m3s",
        "unit": "m3/s",
        "entity_type": "component:hydro",
        "nonnegative": True,
        "resampling_methods": ("mean",),
    },
    "natural_inflow_m3s": {
        "signal_key": "natural_inflow_m3s",
        "unit": "m3/s",
        "entity_type": "hydraulic_node",
        "nonnegative": True,
        "resampling_methods": ("mean",),
    },
    "minimum_flow_m3s": {
        "signal_key": "minimum_flow_m3s",
        "unit": "m3/s",
        "entity_type": "hydraulic_reach",
        "nonnegative": True,
        "resampling_methods": ("mean",),
    },
}


SIGNAL_SEMANTIC_TYPE_KEYS = {
    "price_usd_per_mwh": "energy_price",
    "import_price_usd_per_mwh": "grid_import_price",
    "export_price_usd_per_mwh": "grid_export_price",
    "load_demand_mw": "load_demand",
    "renewable_available_power_mw": "renewable_available_power",
    "hydro_inflow_m3s": "hydro_inflow",
    "natural_inflow_m3s": "natural_inflow",
    "minimum_flow_m3s": "minimum_flow",
}


def validate_signal_registry_contract(registry: Mapping[str, Any]) -> None:
    expected_keys = set(SIGNAL_REGISTRY_CONTRACT)
    actual_keys = set(registry)
    if actual_keys != expected_keys:
        raise ClassificationContractDriftError(
            context={
                "catalog": "TIME_SERIES_SIGNAL_CATALOG",
                "key": "*",
                "field": "keys",
                "expected": sorted(expected_keys),
                "actual": sorted(actual_keys),
            }
        )

    for key, expected in SIGNAL_REGISTRY_CONTRACT.items():
        definition = registry[key]
        for field, expected_value in expected.items():
            actual_value = getattr(definition, field, None)
            if actual_value != expected_value:
                raise ClassificationContractDriftError(
                    context={
                        "catalog": "TIME_SERIES_SIGNAL_CATALOG",
                        "key": key,
                        "field": field,
                        "expected": expected_value,
                        "actual": actual_value,
                    }
                )


MEASUREMENT_DIMENSION_SEED = (
    {
        "id": 1,
        "dimension_key": "currency_per_energy",
        "display_name": "Currency per energy",
        "value_kind": "numeric",
        "status": "active",
    },
    {
        "id": 2,
        "dimension_key": "flow",
        "display_name": "Flow",
        "value_kind": "numeric",
        "status": "active",
    },
    {
        "id": 3,
        "dimension_key": "power",
        "display_name": "Power",
        "value_kind": "numeric",
        "status": "active",
    },
)


MEASUREMENT_UNIT_SEED = (
    {
        "id": 1,
        "unit_key": "usd_per_mwh",
        "symbol": "USD/MWh",
        "dimension_id": 1,
        "physical_dimension": "currency_per_energy",
        "status": "active",
    },
    {
        "id": 2,
        "unit_key": "m3_per_s",
        "symbol": "m3/s",
        "dimension_id": 2,
        "physical_dimension": "flow",
        "status": "active",
    },
    {
        "id": 3,
        "unit_key": "mw",
        "symbol": "MW",
        "dimension_id": 3,
        "physical_dimension": "power",
        "status": "active",
    },
)


TIME_SERIES_DATA_CLASS_SEED = tuple(
    {
        "id": row_id,
        "data_class_key": key,
        "display_name": key.replace("_", " ").title(),
        "status": "active",
    }
    for row_id, key in enumerate(
        (
            "real",
            "programmed",
            "forecast",
            "simulated",
            "synthetic",
            "mixed",
            "derived",
        ),
        start=1,
    )
)


_SEEDED_AT = "2026-08-30T00:00:00+00:00"
_SEED_ACTOR = "system:ts7-001"


TIME_SERIES_SEMANTIC_TYPE_SEED = (
    {
        "id": 1,
        "semantic_key": "energy_price",
        "display_name": "Energy price",
        "description": "Symmetric legacy energy price.",
        "dimension_id": 1,
        "canonical_unit_id": 1,
        "value_kind": "numeric",
        "default_aggregation": "mean",
        "validation_rules_json": "{}",
        "is_system": 1,
        "status": "active",
        "created_at": _SEEDED_AT,
        "updated_at": _SEEDED_AT,
        "created_by": _SEED_ACTOR,
        "updated_by": _SEED_ACTOR,
    },
    {
        "id": 2,
        "semantic_key": "grid_import_price",
        "display_name": "Grid import price",
        "description": "Price paid for imported energy.",
        "dimension_id": 1,
        "canonical_unit_id": 1,
        "value_kind": "numeric",
        "default_aggregation": "mean",
        "validation_rules_json": "{}",
        "is_system": 1,
        "status": "active",
        "created_at": _SEEDED_AT,
        "updated_at": _SEEDED_AT,
        "created_by": _SEED_ACTOR,
        "updated_by": _SEED_ACTOR,
    },
    {
        "id": 3,
        "semantic_key": "grid_export_price",
        "display_name": "Grid export price",
        "description": "Price received for exported energy.",
        "dimension_id": 1,
        "canonical_unit_id": 1,
        "value_kind": "numeric",
        "default_aggregation": "mean",
        "validation_rules_json": "{}",
        "is_system": 1,
        "status": "active",
        "created_at": _SEEDED_AT,
        "updated_at": _SEEDED_AT,
        "created_by": _SEED_ACTOR,
        "updated_by": _SEED_ACTOR,
    },
    {
        "id": 4,
        "semantic_key": "load_demand",
        "display_name": "Load demand",
        "description": "Electrical power consumed by a load.",
        "dimension_id": 3,
        "canonical_unit_id": 3,
        "value_kind": "numeric",
        "default_aggregation": "mean",
        "validation_rules_json": '{"minimum":0}',
        "is_system": 1,
        "status": "active",
        "created_at": _SEEDED_AT,
        "updated_at": _SEEDED_AT,
        "created_by": _SEED_ACTOR,
        "updated_by": _SEED_ACTOR,
    },
    {
        "id": 5,
        "semantic_key": "renewable_available_power",
        "display_name": "Renewable available power",
        "description": "Electrical power available from a renewable asset.",
        "dimension_id": 3,
        "canonical_unit_id": 3,
        "value_kind": "numeric",
        "default_aggregation": "mean",
        "validation_rules_json": '{"minimum":0}',
        "is_system": 1,
        "status": "active",
        "created_at": _SEEDED_AT,
        "updated_at": _SEEDED_AT,
        "created_by": _SEED_ACTOR,
        "updated_by": _SEED_ACTOR,
    },
    {
        "id": 6,
        "semantic_key": "hydro_inflow",
        "display_name": "Hydro inflow",
        "description": "Water inflow assigned to a hydro component.",
        "dimension_id": 2,
        "canonical_unit_id": 2,
        "value_kind": "numeric",
        "default_aggregation": "mean",
        "validation_rules_json": '{"minimum":0}',
        "is_system": 1,
        "status": "active",
        "created_at": _SEEDED_AT,
        "updated_at": _SEEDED_AT,
        "created_by": _SEED_ACTOR,
        "updated_by": _SEED_ACTOR,
    },
    {
        "id": 7,
        "semantic_key": "natural_inflow",
        "display_name": "Natural inflow",
        "description": "Natural water inflow at a hydraulic node.",
        "dimension_id": 2,
        "canonical_unit_id": 2,
        "value_kind": "numeric",
        "default_aggregation": "mean",
        "validation_rules_json": '{"minimum":0}',
        "is_system": 1,
        "status": "active",
        "created_at": _SEEDED_AT,
        "updated_at": _SEEDED_AT,
        "created_by": _SEED_ACTOR,
        "updated_by": _SEED_ACTOR,
    },
    {
        "id": 8,
        "semantic_key": "minimum_flow",
        "display_name": "Minimum flow",
        "description": "Minimum required flow on a hydraulic reach.",
        "dimension_id": 2,
        "canonical_unit_id": 2,
        "value_kind": "numeric",
        "default_aggregation": "mean",
        "validation_rules_json": '{"minimum":0}',
        "is_system": 1,
        "status": "active",
        "created_at": _SEEDED_AT,
        "updated_at": _SEEDED_AT,
        "created_by": _SEED_ACTOR,
        "updated_by": _SEED_ACTOR,
    },
)


TIME_SERIES_BINDING_ROLE_SEED = tuple(
    {
        "id": row_id,
        "role_key": role_key,
        "display_name": role_key.replace("_", " ").title(),
        "dimension_id": dimension_id,
        "canonical_unit_id": canonical_unit_id,
        "association_allowed": 1,
        "execution_allowed": 1,
        "execution_contract_key": execution_contract_key,
        "is_system": 1,
        "status": "active",
    }
    for row_id, role_key, dimension_id, canonical_unit_id, execution_contract_key in (
        (1, "grid_import_price", 1, 1, "import_price_usd_per_mwh"),
        (2, "grid_export_price", 1, 1, "export_price_usd_per_mwh"),
        (3, "load_demand", 3, 3, "load_demand_mw"),
        (4, "renewable_available_power", 3, 3, "renewable_available_power_mw"),
        (5, "hydro_inflow", 2, 2, "hydro_inflow_m3s"),
        (6, "natural_inflow", 2, 2, "natural_inflow_m3s"),
        (7, "minimum_flow", 2, 2, "minimum_flow_m3s"),
    )
)


LINKABLE_OBJECT_TYPE_SEED = tuple(
    {
        "id": row_id,
        "object_type_key": object_type_key,
        "object_kind": object_kind,
        "display_name": object_type_key.replace(":", " ").replace("_", " ").title(),
        "is_system": 1,
        "status": "active",
    }
    for row_id, object_type_key, object_kind in (
        (1, "global:system", "global_signal_slot"),
        (2, "component:grid", "component"),
        (3, "component:load", "component"),
        (4, "component:renewable", "component"),
        (5, "component:battery", "component"),
        (6, "component:hydro", "component"),
        (7, "hydraulic_system", "hydraulic_system"),
        (8, "hydraulic_node", "hydraulic_node"),
        (9, "hydraulic_reach", "hydraulic_reach"),
        (10, "hydraulic_plant", "hydraulic_plant"),
        (11, "hydraulic_unit", "hydraulic_unit"),
    )
)


TIME_SERIES_ROLE_COMPATIBILITY_SEED = tuple(
    {
        "id": row_id,
        "semantic_type_id": semantic_type_id,
        "binding_role_id": binding_role_id,
        "object_type_id": object_type_id,
        "association_allowed": 1,
        "execution_allowed": 1,
        "rule_version": 1,
        "status": "active",
        "supersedes_rule_id": None,
        "created_at": _SEEDED_AT,
        "created_by": _SEED_ACTOR,
        "archived_at": None,
        "archived_by": None,
    }
    for row_id, semantic_type_id, binding_role_id, object_type_id in (
        (1, 1, 1, 1),
        (2, 1, 2, 1),
        (3, 2, 1, 1),
        (4, 3, 2, 1),
        (5, 4, 3, 3),
        (6, 5, 4, 4),
        (7, 6, 5, 6),
        (8, 7, 6, 8),
        (9, 8, 7, 9),
    )
)


CLASSIFICATION_SEED_TABLES = (
    (
        "measurement_dimensions",
        "dimension_key",
        MEASUREMENT_DIMENSION_SEED,
        ("id", "dimension_key", "value_kind"),
    ),
    (
        "measurement_units",
        "unit_key",
        MEASUREMENT_UNIT_SEED,
        (
            "id",
            "unit_key",
            "symbol",
            "dimension_id",
            "physical_dimension",
        ),
    ),
    (
        "time_series_data_classes",
        "data_class_key",
        TIME_SERIES_DATA_CLASS_SEED,
        ("id", "data_class_key"),
    ),
    (
        "time_series_semantic_types",
        "semantic_key",
        TIME_SERIES_SEMANTIC_TYPE_SEED,
        (
            "id",
            "semantic_key",
            "dimension_id",
            "canonical_unit_id",
            "value_kind",
            "default_aggregation",
            "validation_rules_json",
            "is_system",
        ),
    ),
    (
        "time_series_binding_roles",
        "role_key",
        TIME_SERIES_BINDING_ROLE_SEED,
        (
            "id",
            "role_key",
            "dimension_id",
            "canonical_unit_id",
            "association_allowed",
            "execution_allowed",
            "execution_contract_key",
            "is_system",
        ),
    ),
    (
        "linkable_object_types",
        "object_type_key",
        LINKABLE_OBJECT_TYPE_SEED,
        ("id", "object_type_key", "object_kind", "is_system"),
    ),
    (
        "time_series_role_compatibilities",
        "id",
        TIME_SERIES_ROLE_COMPATIBILITY_SEED,
        (
            "id",
            "semantic_type_id",
            "binding_role_id",
            "object_type_id",
            "association_allowed",
            "execution_allowed",
            "rule_version",
        ),
    ),
)
