"""Structural validation for `operator_console_config.v1`.

The document declares what an operator may see and touch. Validation here is
purely structural: it never resolves a pointer, signal, source set or range
against the current case. A semantic problem is not a malformed document; it
surfaces later as a fail-closed console state.
"""

from __future__ import annotations

import re
from typing import Any, Mapping


OPERATOR_CONSOLE_CONFIG_SCHEMA_VERSION = "operator_console_config.v1"

OPERATOR_CONSOLE_STATUSES = ("draft", "active")

GRANULARITIES = ("day", "week", "month", "full_horizon")

EXTERNAL_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
CANONICAL_KEY_PATTERN = re.compile(r"^[A-Za-z0-9_:.-]+$")


class OperatorConsoleConfigurationError(Exception):
    """The console document or status does not match the accepted contract."""

    def __init__(self, message: str, *, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class StaleOperatorConsoleError(OperatorConsoleConfigurationError):
    """The expected revision no longer matches the stored console."""

    def __init__(self, message: str, *, current_revision: int):
        super().__init__(message, status_code=409)
        self.current_revision = current_revision


def default_operator_console_config_document(name: str) -> dict[str, Any]:
    """A structurally valid console that exposes nothing yet."""

    return {
        "schema_version": OPERATOR_CONSOLE_CONFIG_SCHEMA_VERSION,
        "public_identity": {"name": name, "description": ""},
        "parameters": [],
        "groups": [],
        "results": {"kpis": [], "charts": [], "tables": []},
    }


def validate_operator_console_status(status: Any) -> str:
    if status not in OPERATOR_CONSOLE_STATUSES:
        raise OperatorConsoleConfigurationError(f"unknown operator console status: {status!r}")
    return str(status)


def validate_operator_console_config_document(document: Any) -> dict[str, Any]:
    """Reject the whole document unless it matches `operator_console_config.v1`."""

    mapping = _require_mapping(document, "operator console document")
    _reject_unknown_keys(
        mapping,
        {"schema_version", "public_identity", "parameters", "groups", "results"},
        "document",
    )

    schema_version = mapping.get("schema_version")
    if schema_version != OPERATOR_CONSOLE_CONFIG_SCHEMA_VERSION:
        raise OperatorConsoleConfigurationError(
            f"unknown operator console schema version: {schema_version!r}"
        )

    return {
        "schema_version": OPERATOR_CONSOLE_CONFIG_SCHEMA_VERSION,
        "public_identity": _validate_public_identity(mapping.get("public_identity")),
        "parameters": _validate_parameters(mapping.get("parameters")),
        "groups": _validate_groups(mapping.get("groups")),
        "results": _validate_results(mapping.get("results")),
    }


def _validate_public_identity(value: Any) -> dict[str, Any]:
    mapping = _require_mapping(value, "public_identity")
    _reject_unknown_keys(mapping, {"name", "description"}, "public_identity")
    return {
        "name": _require_text(mapping.get("name"), "public_identity.name"),
        "description": _require_optional_text(
            mapping.get("description"), "public_identity.description"
        ),
    }


def _validate_parameters(value: Any) -> list[dict[str, Any]]:
    raw_items = _require_list(value, "parameters")
    declared_ids: set[str] = set()
    parameters = []
    for position, raw_item in enumerate(raw_items):
        where = f"parameters[{position}]"
        item = _require_mapping(raw_item, where)
        _reject_unknown_keys(
            item, {"id", "pointer", "label", "unit", "min", "max", "default"}, where
        )
        parameters.append(
            {
                "id": _register_id(item.get("id"), where, declared_ids),
                "pointer": _validate_pointer(item.get("pointer"), f"{where}.pointer"),
                "label": _require_text(item.get("label"), f"{where}.label"),
                "unit": _optional_text(item.get("unit"), f"{where}.unit"),
                "min": _require_number(item.get("min"), f"{where}.min"),
                "max": _require_number(item.get("max"), f"{where}.max"),
                "default": _require_number(item.get("default"), f"{where}.default"),
            }
        )
    return parameters


def _validate_pointer(value: Any, where: str) -> dict[str, Any]:
    mapping = _require_mapping(value, where)
    _reject_unknown_keys(mapping, {"asset_id", "field"}, where)
    return {
        "asset_id": _require_canonical_key(mapping.get("asset_id"), f"{where}.asset_id"),
        "field": _require_canonical_key(mapping.get("field"), f"{where}.field"),
    }


def _validate_groups(value: Any) -> list[dict[str, Any]]:
    raw_groups = _require_list(value, "groups")
    declared_ids: set[str] = set()
    groups = []
    for position, raw_group in enumerate(raw_groups):
        where = f"groups[{position}]"
        group = _require_mapping(raw_group, where)
        _reject_unknown_keys(group, {"id", "label", "granularities", "columns"}, where)
        groups.append(
            {
                "id": _register_id(group.get("id"), where, declared_ids),
                "label": _require_text(group.get("label"), f"{where}.label"),
                "granularities": _validate_granularities(
                    group.get("granularities"), f"{where}.granularities"
                ),
                "columns": _validate_columns(group.get("columns"), where),
            }
        )
    return groups


def _validate_granularities(value: Any, where: str) -> list[str]:
    raw_values = _require_list(value, where)
    if not raw_values:
        raise OperatorConsoleConfigurationError(f"{where} must declare at least one granularity")
    granularities: list[str] = []
    for granularity in raw_values:
        if granularity not in GRANULARITIES:
            raise OperatorConsoleConfigurationError(
                f"{where} must be one of {', '.join(GRANULARITIES)}; received {granularity!r}"
            )
        if granularity in granularities:
            raise OperatorConsoleConfigurationError(f"duplicate granularity in {where}: {granularity}")
        granularities.append(str(granularity))
    return granularities


def _validate_columns(value: Any, group_where: str) -> list[dict[str, Any]]:
    raw_columns = _require_list(value, f"{group_where}.columns")
    if not raw_columns:
        raise OperatorConsoleConfigurationError(
            f"{group_where}.columns must declare at least one column"
        )
    column_ids: set[str] = set()
    columns = []
    for position, raw_column in enumerate(raw_columns):
        where = f"{group_where}.columns[{position}]"
        column = _require_mapping(raw_column, where)
        _reject_unknown_keys(
            column,
            {
                "id",
                "signal",
                "label",
                "editable",
                "source_options",
                "default_source_option_id",
            },
            where,
        )
        column_id = _validate_external_id(column.get("id"), f"{where}.id")
        if column_id in column_ids:
            raise OperatorConsoleConfigurationError(
                f"duplicate column id in {group_where}: {column_id}"
            )
        column_ids.add(column_id)
        source_options = _validate_source_options(column.get("source_options"), where)
        default_source_option_id = _validate_external_id(
            column.get("default_source_option_id"), f"{where}.default_source_option_id"
        )
        if default_source_option_id not in {option["id"] for option in source_options}:
            raise OperatorConsoleConfigurationError(
                f"{where}.default_source_option_id is not one of its source options"
            )
        columns.append(
            {
                "id": column_id,
                "signal": _validate_signal(column.get("signal"), f"{where}.signal"),
                "label": _require_text(column.get("label"), f"{where}.label"),
                "editable": _require_bool(column.get("editable"), f"{where}.editable"),
                "source_options": source_options,
                "default_source_option_id": default_source_option_id,
            }
        )
    return columns


def _validate_signal(value: Any, where: str) -> dict[str, Any]:
    mapping = _require_mapping(value, where)
    _reject_unknown_keys(mapping, {"entity_type", "entity_id", "signal_key"}, where)
    return {
        "entity_type": _require_canonical_key(
            mapping.get("entity_type"), f"{where}.entity_type"
        ),
        "entity_id": _require_canonical_key(mapping.get("entity_id"), f"{where}.entity_id"),
        "signal_key": _require_canonical_key(
            mapping.get("signal_key"), f"{where}.signal_key"
        ),
    }


def _validate_source_options(value: Any, column_where: str) -> list[dict[str, Any]]:
    raw_options = _require_list(value, f"{column_where}.source_options")
    if not raw_options:
        raise OperatorConsoleConfigurationError(
            f"{column_where}.source_options must declare at least one named source"
        )
    option_ids: set[str] = set()
    options = []
    for position, raw_option in enumerate(raw_options):
        where = f"{column_where}.source_options[{position}]"
        option = _require_mapping(raw_option, where)
        _reject_unknown_keys(option, {"id", "label", "time_series_set_id"}, where)
        option_id = _validate_external_id(option.get("id"), f"{where}.id")
        if option_id in option_ids:
            raise OperatorConsoleConfigurationError(
                f"duplicate source option id in {column_where}: {option_id}"
            )
        option_ids.add(option_id)
        options.append(
            {
                "id": option_id,
                "label": _require_text(option.get("label"), f"{where}.label"),
                "time_series_set_id": _require_positive_int(
                    option.get("time_series_set_id"), f"{where}.time_series_set_id"
                ),
            }
        )
    return options


def _validate_results(value: Any) -> dict[str, Any]:
    mapping = _require_mapping(value, "results")
    _reject_unknown_keys(mapping, {"kpis", "charts", "tables"}, "results")
    return {
        "kpis": _require_list(mapping.get("kpis"), "results.kpis"),
        "charts": _require_list(mapping.get("charts"), "results.charts"),
        "tables": _require_list(mapping.get("tables"), "results.tables"),
    }


def _require_mapping(value: Any, where: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise OperatorConsoleConfigurationError(f"{where} must be an object")
    return value


def _require_list(value: Any, where: str) -> list[Any]:
    if not isinstance(value, list):
        raise OperatorConsoleConfigurationError(f"{where} must be a list")
    return value


def _require_text(value: Any, where: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise OperatorConsoleConfigurationError(f"{where} must be a non-empty string")
    return value.strip()


def _require_optional_text(value: Any, where: str) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise OperatorConsoleConfigurationError(f"{where} must be a string")
    return value.strip()


def _optional_text(value: Any, where: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise OperatorConsoleConfigurationError(f"{where} must be a non-empty string or null")
    return value.strip()


def _require_bool(value: Any, where: str) -> bool:
    if not isinstance(value, bool):
        raise OperatorConsoleConfigurationError(f"{where} must be a boolean")
    return value


def _require_number(value: Any, where: str) -> float | int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise OperatorConsoleConfigurationError(f"{where} must be a number")
    return value


def _require_positive_int(value: Any, where: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise OperatorConsoleConfigurationError(f"{where} must be a positive integer")
    return value


def _require_canonical_key(value: Any, where: str) -> str:
    if not isinstance(value, str) or not CANONICAL_KEY_PATTERN.fullmatch(value):
        raise OperatorConsoleConfigurationError(f"{where} is not a valid key: {value!r}")
    return value


def _validate_external_id(value: Any, where: str) -> str:
    if not isinstance(value, str) or not EXTERNAL_ID_PATTERN.fullmatch(value):
        raise OperatorConsoleConfigurationError(f"{where} is not a valid id: {value!r}")
    return value


def _register_id(value: Any, where: str, declared_ids: set[str]) -> str:
    identifier = _validate_external_id(value, f"{where}.id")
    if identifier in declared_ids:
        raise OperatorConsoleConfigurationError(f"duplicate item id in document: {identifier}")
    declared_ids.add(identifier)
    return identifier


def _reject_unknown_keys(mapping: Mapping[str, Any], allowed: set[str], where: str) -> None:
    unknown = sorted(set(mapping) - allowed)
    if unknown:
        raise OperatorConsoleConfigurationError(
            f"{where} has unknown keys: {', '.join(unknown)}"
        )
