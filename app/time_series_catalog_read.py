"""HTTP representations for the TS-7 signal-first catalog read surface."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from app.time_series_catalog_projection import CatalogQueryError, normalize_search_text
from app.time_series_classification import CLASSIFICATION_CONTRACT_VERSION


_REPEATABLE_FILTERS = {
    "semantic_type_key": "semantic_type_key",
    "data_class_key": "data_class_key",
    "unit_key": "unit_key",
    "owner_project_id": "owner_project_id",
    "visibility_scope": "visibility_scope",
    "set_status": "set_status",
    "signal_status": "signal_status",
    "source_kind": "source_kind",
    "regularity": "regularity",
}


def _utc_filter_timestamp(value: str, *, field: str) -> str:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise CatalogQueryError("TS_QUERY_INVALID", field=field) from error
    if parsed.tzinfo is None:
        raise CatalogQueryError("TS_QUERY_INVALID", field=field, reason="offset_required")
    return parsed.astimezone(timezone.utc).replace(tzinfo=None).isoformat()


def parse_input_filters(query_params) -> dict[str, Any]:
    """Normalize the combinable query dimensions into a cursor-bound value."""

    filters: dict[str, Any] = {}
    q = str(query_params.get("q") or "").strip()
    if len(q) > 200:
        raise CatalogQueryError("TS_QUERY_INVALID", field="q", maximum=200)
    if q:
        filters["q"] = normalize_search_text(q)

    for parameter in _REPEATABLE_FILTERS:
        raw_values = query_params.getlist(parameter)
        if not raw_values:
            continue
        if parameter == "owner_project_id":
            try:
                values = sorted({int(value) for value in raw_values})
            except ValueError as error:
                raise CatalogQueryError(
                    "TS_QUERY_INVALID", field=parameter
                ) from error
        else:
            values = sorted({str(value).strip() for value in raw_values if str(value).strip()})
        if values:
            filters[parameter] = values

    for parameter, numeric in (
        ("association_object_id", True),
        ("association_role_key", False),
        ("association_state", False),
        ("binding_state", False),
    ):
        raw_values = query_params.getlist(parameter)
        if not raw_values:
            continue
        try:
            values = sorted(
                {
                    int(value) if numeric else str(value).strip()
                    for value in raw_values
                    if str(value).strip()
                }
            )
        except ValueError as error:
            raise CatalogQueryError("TS_QUERY_INVALID", field=parameter) from error
        if values:
            filters[parameter] = values

    scenario_id = query_params.get("scenario_id")
    variant_id = query_params.get("variant_id")
    if bool(scenario_id) != bool(variant_id):
        raise CatalogQueryError(
            "TS_QUERY_INVALID", field="scenario_id", reason="variant_pair_required"
        )
    if scenario_id and variant_id:
        try:
            filters["scenario_id"] = int(scenario_id)
            filters["variant_id"] = int(variant_id)
        except ValueError as error:
            raise CatalogQueryError("TS_QUERY_INVALID", field="scenario_id") from error

    context_fields = {
        "context_linkable_object_id": query_params.get("context_linkable_object_id"),
        "context_binding_role_key": query_params.get("context_binding_role_key"),
        "context_usage": query_params.get("context_usage"),
    }
    compatibility = str(query_params.get("compatibility") or "all")
    if compatibility not in {"all", "allowed", "denied"}:
        raise CatalogQueryError("TS_QUERY_INVALID", field="compatibility")
    if any(value is not None for value in context_fields.values()):
        missing_context = [
            name for name, value in context_fields.items() if value is None
        ]
        if missing_context:
            raise CatalogQueryError(
                "TS_QUERY_INVALID", field=missing_context[0], reason="context_required"
            )
        try:
            filters["context_linkable_object_id"] = int(
                context_fields["context_linkable_object_id"]
            )
        except ValueError as error:
            raise CatalogQueryError(
                "TS_QUERY_INVALID", field="context_linkable_object_id"
            ) from error
        filters["context_binding_role_key"] = str(
            context_fields["context_binding_role_key"]
        )
        filters["context_usage"] = str(context_fields["context_usage"])
        if filters["context_usage"] not in {"association", "execution"}:
            raise CatalogQueryError("TS_QUERY_INVALID", field="context_usage")
        filters["compatibility"] = compatibility
        if filters["context_usage"] == "execution":
            context_scenario = query_params.get("context_scenario_id")
            context_variant = query_params.get("context_variant_id")
            if context_scenario is None or context_variant is None:
                raise CatalogQueryError(
                    "TS_QUERY_INVALID",
                    field="context_scenario_id",
                    reason="execution_context_required",
                )
            try:
                filters["context_scenario_id"] = int(context_scenario)
                filters["context_variant_id"] = int(context_variant)
            except ValueError as error:
                raise CatalogQueryError(
                    "TS_QUERY_INVALID", field="context_scenario_id"
                ) from error
    elif query_params.get("compatibility") is not None:
        raise CatalogQueryError(
            "TS_QUERY_INVALID", field="compatibility", reason="context_required"
        )

    covers_from = query_params.get("covers_from")
    covers_to = query_params.get("covers_to")
    if bool(covers_from) != bool(covers_to):
        raise CatalogQueryError(
            "TS_QUERY_INVALID", field="covers_from", reason="range_pair_required"
        )
    if covers_from and covers_to:
        filters["covers_from"] = _utc_filter_timestamp(
            str(covers_from), field="covers_from"
        )
        filters["covers_to"] = _utc_filter_timestamp(str(covers_to), field="covers_to")
        if filters["covers_from"] >= filters["covers_to"]:
            raise CatalogQueryError(
                "TS_QUERY_INVALID", field="covers_to", reason="range_order"
            )

    for parameter in ("resolution_seconds_min", "resolution_seconds_max"):
        value = query_params.get(parameter)
        if value is None:
            continue
        try:
            numeric = float(value)
        except ValueError as error:
            raise CatalogQueryError("TS_QUERY_INVALID", field=parameter) from error
        if numeric <= 0:
            raise CatalogQueryError("TS_QUERY_INVALID", field=parameter)
        filters[parameter] = numeric
    if (
        "resolution_seconds_min" in filters
        and "resolution_seconds_max" in filters
        and filters["resolution_seconds_min"] > filters["resolution_seconds_max"]
    ):
        raise CatalogQueryError(
            "TS_QUERY_INVALID", field="resolution_seconds_max", reason="range_order"
        )
    return filters


def input_filters_sql(
    filters: dict[str, Any],
    *,
    associations_table: str | None = None,
    bindings_table: str | None = None,
) -> tuple[str, tuple]:
    """SQL predicate over projection columns only (AC-CAT-02/04)."""

    clauses: list[str] = []
    parameters: list[Any] = []
    for token in filters.get("q", "").split():
        clauses.append("search_text_normalized LIKE ?")
        parameters.append(f"%{token}%")
    for filter_name, column in _REPEATABLE_FILTERS.items():
        values = filters.get(filter_name)
        if not values:
            continue
        placeholders = ", ".join("?" for _ in values)
        clauses.append(f"{column} IN ({placeholders})")
        parameters.extend(values)

    # Archived identities remain queryable, but they never pollute the default
    # discovery list; asking for a status explicitly opts into them.
    if "set_status" not in filters:
        clauses.append("set_status <> 'archived'")
    if "signal_status" not in filters:
        clauses.append("signal_status <> 'archived'")
    if "covers_from" in filters:
        clauses.extend(("coverage_start <= ?", "coverage_end >= ?"))
        parameters.extend((filters["covers_from"], filters["covers_to"]))
    if "resolution_seconds_min" in filters:
        clauses.append("nominal_resolution_seconds >= ?")
        parameters.append(filters["resolution_seconds_min"])
    if "resolution_seconds_max" in filters:
        clauses.append("nominal_resolution_seconds <= ?")
        parameters.append(filters["resolution_seconds_max"])

    association_dimensions = (
        "association_object_id",
        "association_role_key",
        "association_state",
    )
    if any(name in filters for name in association_dimensions):
        if associations_table is None:
            raise CatalogQueryError("TS_QUERY_INVALID", field="association")
        association_clauses = ["association.signal_id = entry.signal_id"]
        if filters.get("association_object_id"):
            values = filters["association_object_id"]
            association_clauses.append(
                "association.linkable_object_id IN ("
                + ", ".join("?" for _ in values)
                + ")"
            )
            parameters.extend(values)
        if filters.get("association_role_key"):
            values = filters["association_role_key"]
            association_clauses.append(
                "role.role_key IN (" + ", ".join("?" for _ in values) + ")"
            )
            parameters.extend(values)
        if filters.get("association_state"):
            values = filters["association_state"]
            association_clauses.append(
                "association.status IN (" + ", ".join("?" for _ in values) + ")"
            )
            parameters.extend(values)
        clauses.append(
            "EXISTS (SELECT 1 FROM "
            f"{associations_table} AS association "
            "JOIN time_series_binding_roles AS role "
            "ON role.id = association.binding_role_id WHERE "
            + " AND ".join(association_clauses)
            + ")"
        )

    binding_dimensions = ("scenario_id", "variant_id", "binding_state")
    if any(name in filters for name in binding_dimensions):
        if bindings_table is None:
            raise CatalogQueryError("TS_QUERY_INVALID", field="binding")
        binding_clauses = ["binding.signal_id = entry.signal_id"]
        if "scenario_id" in filters:
            binding_clauses.extend(
                (
                    "variant.id = ?",
                    "optimization_case.scenario_id = ?",
                )
            )
            parameters.extend((filters["variant_id"], filters["scenario_id"]))
        if filters.get("binding_state"):
            values = filters["binding_state"]
            binding_clauses.append(
                "binding.status IN (" + ", ".join("?" for _ in values) + ")"
            )
            parameters.extend(values)
        clauses.append(
            "EXISTS (SELECT 1 FROM "
            f"{bindings_table} AS binding "
            "JOIN case_input_variants AS variant "
            "ON variant.id = binding.case_input_variant_id "
            "JOIN optimization_cases AS optimization_case "
            "ON optimization_case.id = variant.case_id WHERE "
            + " AND ".join(binding_clauses)
            + ")"
        )

    if "context_linkable_object_id" in filters:
        usage_column = (
            "association_allowed"
            if filters["context_usage"] == "association"
            else "execution_allowed"
        )
        allowed_sql = (
            "entry.set_status <> 'archived' "
            "AND entry.signal_status <> 'archived' "
            "AND ? = 'active' "
            "AND (entry.visibility_scope = 'global' OR entry.owner_project_id = ?) "
            "AND EXISTS ("
            "SELECT 1 FROM time_series_role_compatibilities AS compatibility_rule "
            "JOIN time_series_binding_roles AS context_role "
            "ON context_role.id = compatibility_rule.binding_role_id "
            "WHERE compatibility_rule.semantic_type_id = entry.semantic_type_id "
            "AND compatibility_rule.object_type_id = ? "
            "AND context_role.role_key = ? "
            "AND context_role.status = 'active' "
            f"AND context_role.{usage_column} = 1 "
            "AND context_role.canonical_unit_id = entry.unit_id "
            "AND compatibility_rule.status = 'active' "
            f"AND compatibility_rule.{usage_column} = 1)"
        )
        context_parameters = (
            filters["_context_object_status"],
            filters["_context_project_id"],
            filters["_context_object_type_id"],
            filters["context_binding_role_key"],
        )
        if filters["compatibility"] == "allowed":
            clauses.append(f"({allowed_sql})")
            parameters.extend(context_parameters)
        elif filters["compatibility"] == "denied":
            clauses.append(f"NOT ({allowed_sql})")
            parameters.extend(context_parameters)
    return " AND ".join(clauses), tuple(parameters)


def input_filters_hash(filters: dict[str, Any]) -> str:
    canonical = json.dumps(filters, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def catalog_error_payload(error: CatalogQueryError, *, request_id: str) -> dict:
    return {
        "error": {
            "code": error.code,
            "message_key": "timeseries.query.refused",
            "message": "La consulta del catalogo no es valida.",
            "field": error.context.get("field"),
            "context": error.context,
            "details": [],
        },
        "request_id": request_id,
    }


def catalog_detail_etag(detail: dict[str, Any], *, actor_class: str) -> str:
    """Strong validator segmented by authorization identity."""

    observed = {
        "signal_id": detail["signal_id"],
        "set_id": detail["set"]["id"],
        "scope_revision": detail["set"]["scope_revision"],
        "set_status": detail["set"]["status"],
        "signal_status": detail["identity"]["status"],
        "revision_id": detail["current_revision"]["id"],
        "content_hash": detail["current_revision"]["content_hash"],
        "contract_version": CLASSIFICATION_CONTRACT_VERSION,
        "actor_class": actor_class,
    }
    encoded = json.dumps(observed, sort_keys=True, separators=(",", ":"))
    return f'"{hashlib.sha256(encoded.encode("utf-8")).hexdigest()}"'


def parse_preview_query(query_params) -> dict[str, Any]:
    required = {
        "revision_id": query_params.get("revision_id"),
        "from": query_params.get("from"),
        "to": query_params.get("to"),
    }
    missing = [name for name, value in required.items() if value is None]
    if missing:
        raise CatalogQueryError(
            "TS_QUERY_INVALID", field=missing[0], reason="required"
        )
    try:
        revision_id = int(required["revision_id"])
        max_points = int(query_params.get("max_points") or 500)
    except (TypeError, ValueError) as error:
        raise CatalogQueryError("TS_QUERY_INVALID", field="revision_id") from error
    if revision_id < 1:
        raise CatalogQueryError("TS_QUERY_INVALID", field="revision_id")
    if max_points > 2000:
        raise CatalogQueryError(
            "TS_PREVIEW_TOO_LARGE", field="max_points", maximum=2000
        )
    if max_points < 1:
        raise CatalogQueryError("TS_QUERY_INVALID", field="max_points")
    strategy = str(query_params.get("sampling") or "minmax")
    if strategy not in {"minmax", "uniform", "none"}:
        raise CatalogQueryError("TS_QUERY_INVALID", field="sampling")
    range_from = _utc_filter_timestamp(str(required["from"]), field="from")
    range_to = _utc_filter_timestamp(str(required["to"]), field="to")
    if range_from >= range_to:
        raise CatalogQueryError("TS_QUERY_INVALID", field="to", reason="range_order")
    return {
        "revision_id": revision_id,
        "range_from": range_from,
        "range_to": range_to,
        "sampling": strategy,
        "max_points": max_points,
    }


def parse_legacy_preview_query(query_params) -> dict[str, Any]:
    required = {"from": query_params.get("from"), "to": query_params.get("to")}
    missing = [name for name, value in required.items() if value is None]
    if missing:
        raise CatalogQueryError("TS_QUERY_INVALID", field=missing[0], reason="required")
    try:
        max_points = int(query_params.get("max_points") or 500)
    except ValueError as error:
        raise CatalogQueryError("TS_QUERY_INVALID", field="max_points") from error
    if max_points > 2000:
        raise CatalogQueryError(
            "TS_PREVIEW_TOO_LARGE", field="max_points", maximum=2000
        )
    if max_points < 1:
        raise CatalogQueryError("TS_QUERY_INVALID", field="max_points")
    sampling = str(query_params.get("sampling") or "minmax")
    if sampling not in {"minmax", "uniform", "none"}:
        raise CatalogQueryError("TS_QUERY_INVALID", field="sampling")
    range_from = _utc_filter_timestamp(str(required["from"]), field="from")
    range_to = _utc_filter_timestamp(str(required["to"]), field="to")
    if range_from >= range_to:
        raise CatalogQueryError("TS_QUERY_INVALID", field="to", reason="range_order")
    return {
        "range_from": range_from,
        "range_to": range_to,
        "sampling": sampling,
        "max_points": max_points,
    }


def parse_result_filters(query_params) -> dict[str, Any]:
    """Normalize the independent result-index collection filters."""

    filters: dict[str, Any] = {}
    for parameter in ("owner_project_id", "scenario_id", "run_id"):
        raw_values = query_params.getlist(parameter)
        if not raw_values:
            continue
        try:
            values = sorted({int(value) for value in raw_values})
        except ValueError as error:
            raise CatalogQueryError("TS_QUERY_INVALID", field=parameter) from error
        if any(value < 1 for value in values):
            raise CatalogQueryError("TS_QUERY_INVALID", field=parameter)
        filters[parameter] = values
    for parameter in ("run_status", "result_type"):
        values = sorted(
            {
                str(value).strip()
                for value in query_params.getlist(parameter)
                if str(value).strip()
            }
        )
        if values:
            filters[parameter] = values
    for parameter in ("produced_from", "produced_to"):
        value = query_params.get(parameter)
        if value is not None:
            filters[parameter] = _utc_filter_timestamp(str(value), field=parameter)
    if (
        "produced_from" in filters
        and "produced_to" in filters
        and filters["produced_from"] >= filters["produced_to"]
    ):
        raise CatalogQueryError(
            "TS_QUERY_INVALID", field="produced_to", reason="range_order"
        )
    return filters


def sample_preview_rows(rows: list[dict[str, Any]], *, strategy: str, limit: int):
    if len(rows) <= limit or strategy == "none":
        return rows
    if strategy == "uniform":
        if limit == 1:
            return [rows[0]]
        indices = {
            round(position * (len(rows) - 1) / (limit - 1))
            for position in range(limit)
        }
        return [rows[index] for index in sorted(indices)]

    if limit == 1:
        return [min(rows, key=lambda row: (row["value_numeric"], row["timestamp_start"]))]
    bucket_count = max(1, limit // 2)
    selected: dict[int, dict[str, Any]] = {}
    for bucket in range(bucket_count):
        start = bucket * len(rows) // bucket_count
        end = (bucket + 1) * len(rows) // bucket_count
        indexed = list(enumerate(rows[start:end], start=start))
        for index, row in (
            min(indexed, key=lambda item: (item[1]["value_numeric"], item[0])),
            max(indexed, key=lambda item: (item[1]["value_numeric"], -item[0])),
        ):
            selected[index] = row
    if limit % 2 and (len(rows) - 1) not in selected:
        selected[len(rows) - 1] = rows[-1]
    return [selected[index] for index in sorted(selected)[:limit]]


def catalog_preview_etag(preview: dict[str, Any]) -> str:
    observed = {
        "signal_id": preview["signal_id"],
        "content_hash": preview["revision"]["content_hash"],
        "requested_range": preview["requested_range"],
        "sampling": preview["sampling"],
        "max_points": preview["max_points"],
    }
    encoded = json.dumps(observed, sort_keys=True, separators=(",", ":"))
    return f'"{hashlib.sha256(encoded.encode("utf-8")).hexdigest()}"'


def input_list_item(row: dict[str, Any], *, actor_role: str) -> dict[str, Any]:
    """Project one catalog row without exposing persistence-only columns."""

    active = row["set_status"] != "archived" and row["signal_status"] != "archived"
    may_edit = active and (
        row["visibility_scope"] == "project" or actor_role == "admin"
    )
    signal_id = int(row["signal_id"])
    return {
        "entry_kind": "input",
        "signal_id": signal_id,
        "identity": {
            "series_key": row["series_key"],
            "display_name": row["display_name"],
            "description": row["signal_description"],
            "status": row["signal_status"],
        },
        "owner": {
            "project_id": int(row["owner_project_id"]),
            "project_name": row["owner_project_name"],
        },
        "set": {
            "id": int(row["time_series_set_id"]),
            "name": row["set_name"],
            "version_number": int(row["set_version_number"]),
            "version_label": row["set_version_label"],
            "description": row["set_description"],
            "status": row["set_status"],
            "visibility_scope": row["visibility_scope"],
        },
        "classification": {
            "semantic_type_key": row["semantic_type_key"],
            "data_class_key": row["data_class_key"],
            "unit_key": row["unit_key"],
        },
        "current_revision": {
            "id": int(row["current_revision_id"]),
            "number": int(row["revision_number"]),
            "sealed": True,
            "created_at": row["revision_created_at"],
        },
        "coverage_summary": {
            "start": row["coverage_start"],
            "end": row["coverage_end"],
            "period_count": int(row["period_count"]),
            "nominal_resolution_seconds": float(
                row["nominal_resolution_seconds"]
            ),
            "minimum_resolution_seconds": float(row["min_resolution_seconds"]),
            "maximum_resolution_seconds": float(row["max_resolution_seconds"]),
            "regularity": row["regularity"],
            "source_timezone": row["source_timezone"],
        },
        "origin_summary": {"source_kind": row["source_kind"]},
        "link_summary": {
            "association_count": int(row["association_count"]),
            "binding_count": int(row["binding_count"]),
        },
        "capabilities": {
            "view_detail": True,
            "preview": True,
            "associate": active,
            "bind": active,
            "edit_set": may_edit,
            "publish_revision": may_edit,
        },
        "resource_version": int(row["projection_revision"]),
        "links": {
            "detail": f"/api/time-series/catalog/inputs/{signal_id}",
            "preview": f"/api/time-series/catalog/inputs/{signal_id}/preview",
            "revisions": f"/api/time-series/catalog/inputs/{signal_id}/revisions",
        },
    }
