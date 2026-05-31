from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any


EDITOR_DRAFT_SCHEMA_VERSION = "bess_editor_draft.v1"
SYSTEM_CASE_SCHEMA_VERSION = "bess_system_dispatch.v1"


class DraftGenerationError(ValueError):
    pass


def structured_draft_document_from_form(form: Mapping[str, Any]) -> dict[str, Any]:
    battery_id = _form_text(form, "battery_id")
    renewable_id = _form_text(form, "renewable_id")
    load_id = _form_text(form, "load_id")

    assets: list[dict[str, Any]] = []
    if battery_id:
        assets.append(
            {
                "id": battery_id,
                "type": "battery",
                "charge_power_max_mw": _required_form_float(form, "battery_charge_power_max_mw"),
                "discharge_power_max_mw": _required_form_float(form, "battery_discharge_power_max_mw"),
                "energy_min_mwh": _required_form_float(form, "battery_energy_min_mwh"),
                "energy_max_mwh": _required_form_float(form, "battery_energy_max_mwh"),
                "initial_energy_mwh": _required_form_float(form, "battery_initial_energy_mwh"),
                "charge_efficiency": _required_form_float(form, "battery_charge_efficiency"),
                "discharge_efficiency": _required_form_float(form, "battery_discharge_efficiency"),
                "degradation_cost_per_mwh_delta_soc": _required_form_float(
                    form,
                    "battery_degradation_cost_per_mwh_delta_soc",
                ),
                "terminal_condition": _form_text(form, "battery_terminal_condition") or "equal_initial",
                "terminal_energy_min_mwh": _optional_form_float(form, "battery_terminal_energy_min_mwh"),
                "prevent_simultaneous_charge_discharge": _form_checked(
                    form,
                    "battery_prevent_simultaneous_charge_discharge",
                ),
                "degradation_linear_delta_soc": _form_checked(form, "battery_degradation_linear_delta_soc"),
            }
        )

    if renewable_id:
        assets.append(
            {
                "id": renewable_id,
                "type": "renewable",
                "category": _form_text(form, "renewable_category"),
                "curtailment_penalty_usd_per_mwh": _optional_form_float(
                    form,
                    "renewable_curtailment_penalty_usd_per_mwh",
                    default=0.0,
                ),
            }
        )

    if load_id:
        assets.append({"id": load_id, "type": "load"})

    return {
        "schema_version": EDITOR_DRAFT_SCHEMA_VERSION,
        "case": {
            "name": _form_text(form, "case_name") or "structured_case",
            "description": _form_text(form, "case_description"),
        },
        "pcc": {
            "id": _form_text(form, "pcc_id") or "bus_1",
            "type": "bus",
        },
        "grid": {
            "id": _form_text(form, "grid_id") or "grid_1",
            "import_power_max_mw": _optional_form_float(form, "grid_import_power_max_mw"),
            "export_power_max_mw": _optional_form_float(form, "grid_export_power_max_mw"),
            "prevent_simultaneous_grid_import_export": _form_checked(
                form,
                "grid_prevent_simultaneous_grid_import_export",
            ),
        },
        "assets": assets,
        "time_series": {"sources": []},
        "solver": {
            "name": _form_text(form, "solver_name") or "HiGHS",
            "options": _form_json_object(form, "solver_options_json"),
        },
    }


def structured_draft_document_from_system_case(
    system_case: dict[str, Any],
    *,
    source: dict[str, Any] | None = None,
) -> dict[str, Any]:
    nodes = system_case.get("nodes") if isinstance(system_case.get("nodes"), list) else []
    pcc_node = next(
        (node for node in nodes if isinstance(node, dict) and node.get("type") in {"bus", "pcc"}),
        {"id": "bus_1", "type": "bus"},
    )
    grid_node = next(
        (node for node in nodes if isinstance(node, dict) and node.get("type") == "grid"),
        {"id": "grid_1", "type": "grid"},
    )
    solver = system_case.get("solver") if isinstance(system_case.get("solver"), dict) else {}

    return {
        "schema_version": EDITOR_DRAFT_SCHEMA_VERSION,
        "case": {"name": str(system_case.get("case_name") or "structured_case")},
        "source": source,
        "pcc": _copy_node_attributes(pcc_node),
        "grid": _copy_node_attributes(grid_node),
        "assets": [
            _copy_node_attributes(node)
            for node in nodes
            if isinstance(node, dict) and node.get("type") in {"battery", "renewable", "load"}
        ],
        "time_series": {"sources": []},
        "solver": {
            "name": str(solver.get("name") or "HiGHS"),
            "options": solver.get("options") if isinstance(solver.get("options"), dict) else {},
        },
        "system_case_seed": system_case,
    }


def generate_system_case_from_draft(document: dict[str, Any]) -> dict[str, Any]:
    if document.get("schema_version") != EDITOR_DRAFT_SCHEMA_VERSION:
        raise DraftGenerationError("draft schema_version must be bess_editor_draft.v1")

    case = _optional_dict(document.get("case"), "case")
    pcc = _optional_dict(document.get("pcc"), "pcc")
    grid = _optional_dict(document.get("grid"), "grid")
    solver = _solver_config(document.get("solver"))
    assets = _asset_list(document.get("assets"))

    pcc_id = str(pcc.get("id") or "bus_1").strip()
    if not pcc_id:
        raise DraftGenerationError("pcc id is required")
    pcc_type = str(pcc.get("type") or "bus").strip()
    if pcc_type not in {"bus", "pcc"}:
        raise DraftGenerationError("pcc type must be bus or pcc")

    grid_id = str(grid.get("id") or "grid_1").strip()
    if not grid_id:
        raise DraftGenerationError("grid id is required")

    nodes = [_node("id", pcc_id, "type", pcc_type)]
    grid_node = _node("id", grid_id, "type", "grid")
    _copy_optional(grid, grid_node, "import_power_max_mw")
    _copy_optional(grid, grid_node, "export_power_max_mw")
    grid_node["prevent_simultaneous_grid_import_export"] = bool(
        grid.get("prevent_simultaneous_grid_import_export", True)
    )
    nodes.append(grid_node)

    for asset in assets:
        asset_type = str(asset.get("type") or "").strip()
        if asset_type == "battery":
            nodes.append(_battery_node(asset))
        elif asset_type == "renewable":
            nodes.append(_renewable_node(asset))
        elif asset_type == "load":
            nodes.append(_load_node(asset))
        else:
            raise DraftGenerationError(f"asset type must be battery, renewable, or load; got {asset_type!r}")

    _ensure_unique_node_ids(nodes)
    edges = [{"from": node["id"], "to": pcc_id} for node in nodes if node["id"] != pcc_id]

    return {
        "schema_version": SYSTEM_CASE_SCHEMA_VERSION,
        "case_name": str(case.get("name") or "structured_case"),
        "nodes": nodes,
        "edges": edges,
        "time_series": _periods(document),
        "constraints": {},
        "solver": solver,
    }


def _battery_node(asset: dict[str, Any]) -> dict[str, Any]:
    node = _node("id", _required_asset_id(asset), "type", "battery")
    for key in [
        "charge_power_max_mw",
        "discharge_power_max_mw",
        "energy_min_mwh",
        "energy_max_mwh",
        "initial_energy_mwh",
        "charge_efficiency",
        "discharge_efficiency",
        "degradation_cost_per_mwh_delta_soc",
        "terminal_energy_min_mwh",
    ]:
        _copy_optional(asset, node, key)
    node["prevent_simultaneous_charge_discharge"] = bool(
        asset.get("prevent_simultaneous_charge_discharge", True)
    )
    node["terminal_condition"] = str(asset.get("terminal_condition") or "equal_initial")
    node["degradation_linear_delta_soc"] = bool(asset.get("degradation_linear_delta_soc", True))
    return node


def _renewable_node(asset: dict[str, Any]) -> dict[str, Any]:
    node = _node("id", _required_asset_id(asset), "type", "renewable")
    _copy_optional(asset, node, "curtailment_penalty_usd_per_mwh")
    category = str(asset.get("category") or asset.get("display_category") or "").strip()
    if category:
        node["display_category"] = category
    return node


def _load_node(asset: dict[str, Any]) -> dict[str, Any]:
    return _node("id", _required_asset_id(asset), "type", "load")


def _solver_config(raw_solver: Any) -> dict[str, Any]:
    solver = _optional_dict(raw_solver, "solver")
    options = solver.get("options", {})
    if options is None:
        options = {}
    if not isinstance(options, dict):
        raise DraftGenerationError("solver options must be a JSON object")
    return {"name": str(solver.get("name") or "HiGHS"), "options": options}


def _periods(document: dict[str, Any]) -> list[dict[str, Any]]:
    time_series = document.get("time_series") or {}
    if not isinstance(time_series, dict):
        raise DraftGenerationError("time_series must be an object")
    periods = time_series.get("periods", [])
    if periods is None:
        periods = []
    if not isinstance(periods, list):
        raise DraftGenerationError("time_series.periods must be an array")
    for index, period in enumerate(periods):
        if not isinstance(period, dict):
            raise DraftGenerationError(f"time_series.periods[{index}] must be an object")
    return periods


def _asset_list(raw_assets: Any) -> list[dict[str, Any]]:
    if raw_assets is None:
        return []
    if not isinstance(raw_assets, list):
        raise DraftGenerationError("assets must be an array")
    for index, asset in enumerate(raw_assets):
        if not isinstance(asset, dict):
            raise DraftGenerationError(f"assets[{index}] must be an object")
    return raw_assets


def _ensure_unique_node_ids(nodes: list[dict[str, Any]]) -> None:
    seen: set[str] = set()
    duplicates: list[str] = []
    for node in nodes:
        node_id = node["id"]
        if node_id in seen:
            duplicates.append(node_id)
        seen.add(node_id)
    if duplicates:
        raise DraftGenerationError(f"duplicate asset id: {duplicates[0]}")


def _required_asset_id(asset: dict[str, Any]) -> str:
    asset_id = str(asset.get("id") or "").strip()
    if not asset_id:
        raise DraftGenerationError("asset id is required")
    return asset_id


def _optional_dict(value: Any, name: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise DraftGenerationError(f"{name} must be an object")
    return value


def _copy_optional(source: dict[str, Any], target: dict[str, Any], key: str) -> None:
    if key in source:
        target[key] = source[key]


def _node(id_key: str, id_value: str, type_key: str, type_value: str) -> dict[str, Any]:
    return {id_key: id_value, type_key: type_value}


def _copy_node_attributes(node: dict[str, Any]) -> dict[str, Any]:
    return dict(node)


def _form_text(form: Mapping[str, Any], key: str) -> str:
    value = form.get(key, "")
    return str(value).strip()


def _form_checked(form: Mapping[str, Any], key: str) -> bool:
    return key in form and str(form.get(key)).lower() not in {"", "false", "0", "off"}


def _required_form_float(form: Mapping[str, Any], key: str) -> float:
    text = _form_text(form, key)
    if not text:
        raise DraftGenerationError(f"{key} is required")
    return _parse_form_float(text, key)


def _optional_form_float(form: Mapping[str, Any], key: str, *, default: float | None = None) -> float | None:
    text = _form_text(form, key)
    if not text:
        return default
    return _parse_form_float(text, key)


def _parse_form_float(text: str, key: str) -> float:
    try:
        return float(text)
    except ValueError as error:
        raise DraftGenerationError(f"{key} must be numeric") from error


def _form_json_object(form: Mapping[str, Any], key: str) -> dict[str, Any]:
    text = _form_text(form, key)
    if not text:
        return {}
    try:
        value = json.loads(text)
    except json.JSONDecodeError as error:
        raise DraftGenerationError(
            f"{key} must be a JSON object: {error.msg} at line {error.lineno}, column {error.colno}"
        ) from error
    if not isinstance(value, dict):
        raise DraftGenerationError(f"{key} must be a JSON object")
    return value
