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
) -> dict[str, Any]:
    """Build the whole external publication payload from a fixed allowlist.

    A technical artifact failure only turns `results_state` to `unavailable`;
    the reason stays on the internal surfaces.
    """

    sections = document.get("sections") or {}
    return {
        "project": {"id": project["id"], "name": project["name"]},
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
