"""Pure builders for the payloads that leave the application boundary.

Every function here enumerates the fields an external surface may receive.
Configuration is applied *after* that fixed allowlist, never instead of it, so
a new canonical column or summary key cannot reach the portal or the operator
console by appearing upstream.
"""

from __future__ import annotations

from typing import Any, Mapping

from app.portal_configuration import PORTAL_CHART_CATALOG, PORTAL_TABLE_CATALOG


SCALAR_TYPES = (int, float, str)

TIMESTAMP_COLUMN = "timestamp"


def build_portal_publication_payload(
    *,
    project: Mapping[str, Any],
    publication: Mapping[str, Any],
    document: Mapping[str, Any],
    results: Mapping[str, Any] | None,
    downloads: list[Mapping[str, Any]],
    logo_url: str | None = None,
) -> dict[str, Any]:
    """Build the whole external publication payload from a fixed allowlist.

    A technical artifact failure only turns `results_state` to `unavailable`;
    the reason stays on the internal surfaces.
    """

    sections = document.get("sections") or {}
    return {
        "branding": build_portal_branding(project, document, logo_url),
        "publication": {
            "id": publication["id"],
            "project_id": publication["project_id"],
            "public_title": publication["public_title"],
            "analyst_notes": publication.get("analyst_notes") or "",
            "published_at": publication.get("published_at"),
            "status": publication["status"],
        },
        "period": build_result_period(results),
        "results_state": "available" if results is not None else "unavailable",
        "results_block": build_results_block(document, results)
        if results is not None
        else None,
        "downloads": build_portal_downloads(
            sections.get("downloads") or {}, downloads
        ),
    }


def build_portal_branding(
    project: Mapping[str, Any],
    document: Mapping[str, Any],
    logo_url: str | None,
) -> dict[str, Any]:
    return {
        "display_name": document.get("display_name") or project["name"],
        "logo_url": logo_url,
    }


def build_console_payload(
    *,
    console: Mapping[str, Any],
    prepared_by: str | None,
    parameters: list[Mapping[str, Any]] | None = None,
    run_gate: Mapping[str, Any] | None = None,
    period: Mapping[str, Any] | None = None,
    history: list[Mapping[str, Any]] | None = None,
    groups: list[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build the console envelope an operator receives.

    Only the public identity the analyst declared crosses the boundary: no
    scenario, case, variant, binding, set revision or configuration document.
    """

    identity = console["document"].get("public_identity") or {}
    return {
        "console": {
            "id": console["id"],
            "name": identity.get("name") or "",
            "description": identity.get("description") or "",
            "prepared_by": prepared_by,
            "updated_at": console["updated_at"],
        },
        "parameters": [
            {
                "id": parameter["id"],
                "label": parameter["label"],
                "unit": parameter.get("unit"),
                "min": parameter["min"],
                "max": parameter["max"],
                "default": parameter["default"],
                "value": parameter.get("value"),
            }
            for parameter in (parameters or [])
        ],
        "period": {
            "available_start": (period or {}).get("available_start"),
            "available_end": (period or {}).get("available_end"),
            "selected_start": (period or {}).get("selected_start"),
            "selected_end": (period or {}).get("selected_end"),
        },
        "run_gate": {
            "can_run": bool((run_gate or {}).get("can_run")),
            "reason": (run_gate or {}).get("reason"),
            "message": str((run_gate or {}).get("message") or ""),
            "contact": (run_gate or {}).get("contact"),
            "editing_locked_by": (run_gate or {}).get("editing_locked_by"),
            # Whether a review was already asked for; the raw staleness detail
            # behind the block stays on the internal surfaces.
            "review_requested_at": (run_gate or {}).get("review_requested_at"),
        },
        "groups": [
            {
                "id": group["id"],
                "label": group["label"],
                "granularities": list(group["granularities"]),
                "columns": [
                    {
                        "id": column["id"],
                        "label": column["label"],
                        "unit": column["unit"],
                        "nonnegative": bool(column["nonnegative"]),
                        "editable": bool(column["editable"]),
                    }
                    for column in group["columns"]
                ],
            }
            for group in (groups or [])
        ],
        "history": [build_console_run_entry(run) for run in (history or [])],
    }


def build_console_group_values(group_values: Mapping[str, Any]) -> dict[str, Any]:
    """Build the editable grid an operator receives for one group.

    Row positions and external column ids are the only coordinates that cross:
    period indexes, signal keys and set ids stay behind the boundary, and the
    concurrency token leaves as an opaque ETag header instead of a field.
    """

    return {
        "group_id": group_values["group_id"],
        "granularity": group_values["granularity"],
        "range": {
            "start": group_values["range"]["start"],
            "end": group_values["range"]["end"],
        },
        "columns": [
            {
                "id": column["id"],
                "label": column["label"],
                "unit": column["unit"],
                "nonnegative": bool(column["nonnegative"]),
                "editable": bool(column["editable"]),
            }
            for column in group_values["columns"]
        ],
        "rows": [
            {
                "index": row["index"],
                "timestamp": row["timestamp"],
                "values": dict(row["values"]),
            }
            for row in group_values["rows"]
        ],
    }


def build_console_series_options(
    resolved: Mapping[str, Any],
) -> dict[str, Any]:
    """Expose named source choices without their configured catalog targets."""

    return {
        "selections": [
            {
                "group_id": selection["group_id"],
                "column_id": selection["column_id"],
                "selected_source_option_id": selection.get(
                    "selected_source_option_id"
                ),
                "options": [
                    {"id": option["id"], "label": option["label"]}
                    for option in selection["options"]
                ],
            }
            for selection in resolved.get("selections") or []
        ]
    }


def build_console_lease(lease: Mapping[str, Any]) -> dict[str, Any]:
    """The edit lock as the operator sees it: a token, a name and a deadline."""

    return {
        "token": lease["token"],
        "expires_at": lease["expires_at"],
        "holder_name": lease.get("holder_name") or "",
    }


def build_console_save_error(
    *,
    message: str,
    cells: list[Mapping[str, Any]],
    total_cells: int,
) -> dict[str, Any]:
    """State a refused save in the coordinates the operator can see."""

    return {
        "message": message,
        "cells": [
            {
                "group_id": cell["group_id"],
                "column_id": cell["column_id"],
                "row_index": cell["row_index"],
                "message": cell["message"],
            }
            for cell in cells
        ],
        "total_cells": total_cells,
        "shown_cells": len(cells),
    }


def build_console_list_entry(
    *,
    console: Mapping[str, Any],
    project_name: str,
) -> dict[str, Any]:
    identity = console["document"].get("public_identity") or {}
    return {
        "console": {
            "id": console["id"],
            "name": identity.get("name") or "",
            "description": identity.get("description") or "",
        },
        "project": {"name": project_name},
        "state": console["status"],
    }


def build_console_run_entry(run: Mapping[str, Any]) -> dict[str, Any]:
    """Translate one internal run row to the reduced operator history grammar."""

    states = {
        "queued": "en_espera",
        "running": "ejecutando",
        "succeeded": "lista",
        "failed": "fallida",
    }
    return {
        "id": run["id"],
        "started_at": run.get("started_at") or run.get("created_at"),
        "state": states.get(str(run.get("status")), "fallida"),
        "duration_seconds": run.get("duration_seconds"),
        "triggered_by": run.get("triggered_by_display_name")
        or run.get("triggered_by")
        or "",
    }


def build_console_run_comparison(
    *,
    left: Mapping[str, Any],
    right: Mapping[str, Any],
) -> dict[str, Any]:
    """Put two already-allowlisted run blocks side by side.

    Nothing new crosses the boundary here: each side carries the reduced run
    entry and the very block run detail returns, and a difference exists only
    where the analyst configured a KPI and both runs produced a number for it.
    """

    sides = {
        name: {
            "run": build_console_run_entry(side["run"]),
            "results_state": (
                "available" if side.get("results_block") is not None else "unavailable"
            ),
            "results_block": side.get("results_block"),
        }
        for name, side in (("left", left), ("right", right))
    }
    return {
        "left": sides["left"],
        "right": sides["right"],
        "kpi_differences": build_console_kpi_differences(
            sides["left"]["results_block"], sides["right"]["results_block"]
        ),
    }


def build_console_kpi_differences(
    left_block: Mapping[str, Any] | None,
    right_block: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    """Difference the KPIs both sides published, in the configured order."""

    if left_block is None or right_block is None:
        return []
    counterparts = {kpi["id"]: kpi for kpi in right_block["kpis"]}
    differences: list[dict[str, Any]] = []
    for kpi in left_block["kpis"]:
        counterpart = counterparts.get(kpi["id"])
        if counterpart is None:
            continue
        left_value = parse_numeric_value(kpi["value"])
        right_value = parse_numeric_value(counterpart["value"])
        if left_value is None or right_value is None:
            continue
        differences.append(
            {
                "id": kpi["id"],
                "label": kpi["label"],
                "unit": kpi["unit"],
                "decimals": kpi["decimals"],
                "left": left_value,
                "right": right_value,
                "difference": right_value - left_value,
            }
        )
    return differences


def build_portal_downloads(
    download_section: Mapping[str, Any],
    downloads: list[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Intersect the configured download section with the publication allowlist."""

    if not download_section.get("enabled"):
        return []
    return [
        {
            "label": download["display_name"],
            "media_type": download["media_type"],
            "byte_size": download["byte_size"],
            "download_url": download["download_url"],
        }
        for download in downloads
    ]


def build_result_period(results: Mapping[str, Any] | None) -> dict[str, Any]:
    rows = ((results or {}).get("dispatch_table") or {}).get("rows") or []
    timestamps = [str(row.get(TIMESTAMP_COLUMN) or "") for row in rows]
    timestamps = [timestamp for timestamp in timestamps if timestamp]
    if not timestamps:
        return {"start": None, "end": None}
    return {"start": timestamps[0], "end": timestamps[-1]}


def build_results_block(
    document: Mapping[str, Any],
    results: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Build the configured, safe results block for a portal publication."""

    sections = document.get("sections") or {}
    kpi_section = sections.get("kpis") or {}
    chart_section = sections.get("charts") or {}
    table_section = sections.get("tables") or {}
    download_section = sections.get("downloads") or {}
    return {
        "labels": {
            "kpis": _section_label(kpi_section),
            "charts": _section_label(chart_section),
            "tables": _section_label(table_section),
            "downloads": _section_label(download_section),
        },
        "kpis": build_configured_kpis(kpi_section, results),
        "charts": build_configured_charts(chart_section, results),
        "tables": build_configured_tables(table_section, results),
    }


def _section_label(section: Mapping[str, Any]) -> str:
    return (section.get("label") or "") if section.get("enabled") else ""


def build_configured_charts(
    chart_section: Mapping[str, Any],
    results: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    if not chart_section.get("enabled"):
        return []
    charts: list[dict[str, Any]] = []
    for item in chart_section.get("items") or []:
        catalog_entry = PORTAL_CHART_CATALOG.get(item.get("chart_key"))
        if catalog_entry is None:
            continue
        table = _source_table(results, catalog_entry["source"])
        if table is None:
            continue
        columns = table.get("columns") or []
        rows = table.get("rows") or []
        series = [
            {
                "label": entry["label"],
                "unit": catalog_entry["series"][entry["key"]],
                "values": [parse_numeric_value(row.get(entry["key"])) for row in rows],
            }
            for entry in item.get("series") or []
            if entry.get("key") in catalog_entry["series"]
            and entry.get("key") in columns
        ]
        if not series:
            continue
        charts.append(
            {
                "id": item["id"],
                "label": item["label"],
                "x_labels": [str(row.get(TIMESTAMP_COLUMN) or "") for row in rows],
                "series": series,
            }
        )
    return charts


def build_configured_tables(
    table_section: Mapping[str, Any],
    results: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    if not table_section.get("enabled"):
        return []
    tables: list[dict[str, Any]] = []
    for item in table_section.get("items") or []:
        catalog_entry = PORTAL_TABLE_CATALOG.get(item.get("table_key"))
        if catalog_entry is None:
            continue
        table = _source_table(results, catalog_entry["source"])
        if table is None:
            continue
        available = table.get("columns") or []
        columns = [
            column
            for column in item.get("columns") or []
            if column.get("key") in catalog_entry["columns"]
            and column.get("key") in available
        ]
        if not columns:
            continue
        row_limit = item["row_limit"]
        tables.append(
            {
                "id": item["id"],
                "label": item["label"],
                "row_limit": row_limit,
                "columns": [
                    {
                        "id": column["id"],
                        "label": column["label"],
                        "unit": column.get("unit"),
                    }
                    for column in columns
                ],
                "rows": [
                    {
                        column["id"]: parse_cell_value(row.get(column["key"]))
                        for column in columns
                    }
                    for row in (table.get("rows") or [])[:row_limit]
                ],
            }
        )
    return tables


def parse_cell_value(value: Any) -> float | str | None:
    """Keep a numeric cell numeric and any other declared cell as public text."""

    if value is None or value == "":
        return None
    number = parse_numeric_value(value)
    if number is not None:
        return number
    return str(value)


def _source_table(
    results: Mapping[str, Any] | None, source: str
) -> Mapping[str, Any] | None:
    table = (results or {}).get(source)
    return table if isinstance(table, Mapping) else None


def parse_numeric_value(value: Any) -> float | None:
    if value is None or value == "" or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def build_configured_kpis(
    kpi_section: Mapping[str, Any],
    results: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    if not kpi_section.get("enabled"):
        return []
    summary = (results or {}).get("summary") or {}
    kpis: list[dict[str, Any]] = []
    for item in kpi_section.get("items") or []:
        value = resolve_canonical_path(summary, item.get("path"))
        if value is None:
            continue
        kpis.append(
            {
                "id": item["id"],
                "label": item["label"],
                "value": value,
                "unit": item.get("unit"),
                "decimals": item["decimals"],
                "sign": item["sign"],
                "emphasis": item["emphasis"],
            }
        )
    return kpis


def resolve_canonical_path(source: Mapping[str, Any], path: Any) -> Any:
    """Resolve a dotted canonical path to a scalar, or None when unavailable."""

    if not isinstance(path, str) or not path:
        return None
    current: Any = source
    for segment in path.split("."):
        if not isinstance(current, Mapping) or segment not in current:
            return None
        current = current[segment]
    if isinstance(current, bool) or not isinstance(current, SCALAR_TYPES):
        return None
    return current
