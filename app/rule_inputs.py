"""Canonical, object-scoped inputs for component rules."""
import math
from datetime import datetime, timedelta

from fastapi import HTTPException


def input_error(port, message, *, code="RULE_INPUT_INVALID", period=None, status=422):
    raise HTTPException(status, {"code": code, "message": message, "alias": port["alias"],
                                 "object_id": port["object_id"], "period": period})


def resolve_input(store, project_id, object_id, port):
    from app.linkable_objects import LinkableObjectError
    try:
        obj = store.get_linkable_object(port["object_id"])
    except LinkableObjectError:
        input_error(port, "Objeto de entrada no disponible")
    allowed = object_id if isinstance(object_id, set) else {object_id}
    if port["object_id"] not in allowed or obj["project_id"] != project_id or obj["status"] != "active":
        input_error(port, "El puerto debe pertenecer al objeto de la regla o a un alias declarado")
    tables = store.canonical_table_names()
    row = store.connection.execute(f"""
        SELECT s.id AS set_id, s.owner_project_id, s.visibility_scope, s.series_kind,
               s.owner_linkable_object_id, s.status AS set_status, s.current_revision_id,
               s.scope_revision, s.name AS set_name, sig.display_name, sig.status AS signal_status,
               rev.state, rev.content_hash, rev.revision_number, rev.timezone, rev.timestamp_convention,
               rev.time_series_source_id AS source_id, rev.metadata_json,
               rs.signal_role, rs.aggregation, sem.semantic_key, unit.unit_key, dim.dimension_key
        FROM {tables['time_series_revision_signals']} rs
        JOIN {tables['time_series_set_revisions']} rev ON rev.id = rs.set_revision_id
        JOIN {tables['time_series_sets']} s ON s.id = rs.time_series_set_id
        JOIN {tables['time_series_signals']} sig ON sig.id = rs.signal_id
        JOIN time_series_semantic_types sem ON sem.id = rs.semantic_type_id
        JOIN measurement_units unit ON unit.id = rs.unit_id
        JOIN measurement_dimensions dim ON dim.id = unit.dimension_id
        WHERE rs.set_revision_id = ? AND rs.signal_id = ?
    """, (port["revision_id"], port["signal_id"])).fetchone()
    if row is None or row["state"] != "sealed" or row["content_hash"] != port["content_hash"]:
        input_error(port, "La señal, revisión sellada y hash no coinciden")
    item = dict(row)
    if (item["set_status"] != "validated" or item["signal_status"] != "active"
            or (item["visibility_scope"] != "global" and item["owner_project_id"] != project_id)
            or (item["series_kind"] == "object_specific" and item["owner_linkable_object_id"] != port["object_id"])):
        input_error(port, "La entrada no está disponible para este objeto")
    if item["semantic_key"] != port["semantic_type_key"] or item["dimension_key"] != port["dimension_key"]:
        input_error(port, "La dimensión o semántica no coincide con la revisión")
    decision = store.evaluate_time_series_compatibility(
        semantic_type_key=item["semantic_key"], binding_role_key=port["binding_role_key"],
        object_type_key=obj["object_type_key"], unit_key=item["unit_key"], usage="execution",
    )
    if not decision["allowed"] or item["signal_role"] != "input" or item["aggregation"] != "mean":
        input_error(port, "La semántica, unidad o agregación no es compatible con este puerto")
    return {**port, **item, "compatibility": decision}


def validate_inputs(store, project_id, object_id, inputs):
    aliases = set()
    for port in inputs:
        if port["alias"] in aliases:
            input_error(port, "Alias de entrada duplicado")
        aliases.add(port["alias"])
        resolve_input(store, project_id, object_id, port)


def freeze_inputs(store, project_id, object_id, ports, compilation):
    from app.rule_applications import instant
    tables = store.canonical_table_names()
    start, end = (instant(compilation["scope"][key]) for key in ("range_start", "range_end"))
    frozen = []
    object_id = {object_id, *(a["object_id"] for a in compilation.get("aliases", []))}
    validate_inputs(store, project_id, object_id, ports)
    for port in ports:
        source = resolve_input(store, project_id, object_id, port)
        if source["timestamp_convention"] != "period_start":
            input_error(port, "La entrada debe representar medias al inicio de cada intervalo")
        # Bound the indexed read while allowing explicit UTC offsets in canonical timestamps.
        rows = store.connection.execute(f"""
            SELECT p.timestamp_start, p.timestamp_end, p.duration_hours, v.value_numeric
            FROM {tables['time_series_periods']} p
            LEFT JOIN {tables['time_series_values']} v ON v.time_series_period_id = p.id
                AND v.set_revision_id = p.set_revision_id AND v.signal_id = ?
            WHERE p.set_revision_id = ? AND p.timestamp_start >= ? AND p.timestamp_start < ?
            ORDER BY p.period_index LIMIT 100001
        """, (port["signal_id"], port["revision_id"], (start-timedelta(days=2)).date().isoformat(),
              (end+timedelta(days=2)).date().isoformat())).fetchall()
        if len(rows) > 100000:
            input_error(port, "Cuota de intervalos de entrada excedida")
        periods = {}
        for row in rows:
            try:
                first, last = instant(row["timestamp_start"]), instant(row["timestamp_end"])
            except (TypeError, ValueError):
                input_error(port, "La entrada contiene un instante inválido")
            if first < end and last > start:
                periods.setdefault(first, []).append((row, last))
        values = []
        for t, period in enumerate(compilation["grid"]):
            first = instant(period["timestamp"])
            selected = periods.pop(first, [])
            if len(selected) != 1:
                input_error(port, "Falta un intervalo o está duplicado; transforma la serie explícitamente", period=t)
            row, last = selected[0]
            if source["timezone"] not in {"UTC", "Etc/UTC"} and datetime.fromisoformat(row["timestamp_start"].replace("Z", "+00:00")).tzinfo is None:
                input_error(port, "La entrada necesita instantes UTC explícitos; transforma su zona horaria antes de usarla", period=t)
            duration = row["duration_hours"]
            if duration != period["duration_hours"] or last != first + timedelta(hours=period["duration_hours"]):
                input_error(port, "Duración o alineación incompatible con la grilla", period=t)
            value = row["value_numeric"]
            if type(value) not in (int, float) or not math.isfinite(value):
                input_error(port, "Valor faltante o no finito", period=t)
            if value < 0 or (port["binding_role_key"] == "rule_availability" and value > 1):
                input_error(port, "Valor fuera del rango permitido por la semántica", period=t)
            values.append(value)
        if periods:
            input_error(port, "La entrada incluye intervalos desalineados con la grilla", period=0)
        frozen.append({**source, "values": values})
    return frozen


def assert_inputs_current(store, project_id, object_id, inputs, aliases=()):
    object_id = {object_id, *(a["object_id"] for a in aliases)}
    keys = ("current_revision_id", "scope_revision", "visibility_scope", "owner_project_id",
            "owner_linkable_object_id", "set_status", "signal_status", "compatibility")
    for source in inputs:
        try:
            current = resolve_input(store, project_id, object_id, source)
        except HTTPException as error:
            input_error(source, error.detail["message"], code="RULE_INPUT_STALE", status=409)
        if any(current[key] != source[key] for key in keys):
            input_error(source, "Entrada obsoleta: cambió una publicación o su compatibilidad. Prueba y aplica la revisión fijada con motivo, o selecciona otra.",
                        code="RULE_INPUT_STALE", status=409)


def input_candidates(store, project_id, object_id, after=0, limit=50):
    tables = store.canonical_table_names()
    object_type = store.get_linkable_object(object_id)["object_type_key"]
    rows = store.connection.execute(f"""
        SELECT sig.id AS signal_id, rev.id AS revision_id, rev.content_hash,
               sem.semantic_key AS semantic_type_key, dim.dimension_key, roles.role_key AS binding_role_key
        FROM {tables['time_series_sets']} s
        JOIN {tables['time_series_set_revisions']} rev ON rev.id = s.current_revision_id
        JOIN {tables['time_series_revision_signals']} rs ON rs.set_revision_id = rev.id
        JOIN {tables['time_series_signals']} sig ON sig.id = rs.signal_id
        JOIN time_series_semantic_types sem ON sem.id = rs.semantic_type_id
        JOIN measurement_units unit ON unit.id = rs.unit_id
        JOIN measurement_dimensions dim ON dim.id = unit.dimension_id
        JOIN time_series_role_compatibilities compat ON compat.semantic_type_id = sem.id
        JOIN time_series_binding_roles roles ON roles.id = compat.binding_role_id
        JOIN linkable_object_types ot ON ot.id = compat.object_type_id
        WHERE sig.id > ? AND s.status = 'validated' AND sig.status = 'active' AND rev.state = 'sealed'
          AND (s.visibility_scope = 'global' OR s.owner_project_id = ?)
          AND (s.series_kind = 'catalog' OR s.owner_linkable_object_id = ?)
          AND roles.role_key IN ('rule_inflow', 'rule_availability') AND ot.object_type_key = ?
          AND compat.status = 'active' AND compat.execution_allowed = 1
        ORDER BY sig.id LIMIT ?
    """, (after, project_id, object_id, object_type, limit + 1)).fetchall()
    items = []
    for row in rows[:limit]:
        port = {**dict(row), "object_id": object_id, "alias": "entrada"}
        try:
            item = resolve_input(store, project_id, object_id, port)
        except HTTPException:
            continue
        items.append(item)
    return {"items": items, "next_cursor": rows[limit-1]["signal_id"] if len(rows) > limit else None}
