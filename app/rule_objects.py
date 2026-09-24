"""Resolve rule references by stable identity and active case membership."""
import ast
from fastapi import HTTPException

VARIABLES = {
    "hydro": {"caudal": "m3_per_s", "vertimiento": "m3_per_s", "potencia": "mw", "almacenamiento": "hm3"},
    "hydraulic_unit": {"caudal": "m3_per_s", "potencia": "mw"},
    "hydraulic_plant": {"potencia": "mw"},
    "hydraulic_node": {"almacenamiento": "hm3", "vertimiento": "m3_per_s"},
}


def model_document(store, scenario_id, object_id=None):
    """Use the current editor model, or the hydraulic diagram when there is no draft."""
    from app.draft_editor import generate_system_case_from_draft
    if object_id is not None and store.get_linkable_object(object_id)["object_kind"] != "component":
        return store.generate_hydraulic_v3_preview(scenario_id)
    try:
        draft = store.get_scenario_draft(scenario_id)
    except KeyError:
        return store.generate_hydraulic_v3_preview(scenario_id)
    return generate_system_case_from_draft(draft["document"])


def object_error(alias, object_id, code=None):
    line = None
    if code:
        try:
            line = next((node.lineno for node in ast.walk(ast.parse(code)) if isinstance(node, ast.Attribute)
                         and node.attr == alias and isinstance(node.value, ast.Attribute) and node.value.attr == "objetos"), None)
        except SyntaxError:
            pass
    raise HTTPException(422, {"code": "RULE_OBJECT_INVALID", "message": "El objeto no pertenece al mismo snapshot hidráulico activo",
                              "alias": alias, "object_id": object_id, "line": line})


def model_objects(store, project_id, scenario_id, document=None, *, object_id=None):
    try:
        scenario = store.get_scenario(scenario_id)
    except KeyError:
        raise HTTPException(404, "Escenario no disponible") from None
    if scenario["project_id"] != project_id:
        raise HTTPException(404, "Escenario fuera del proyecto")
    if document is None:
        try:
            document = model_document(store, scenario_id, object_id)
        except (KeyError, ValueError) as error:
            raise HTTPException(422, "El modelo hidráulico no está disponible para relacionar objetos") from error
    if document["schema_version"] == "bess_system_dispatch.v2":
        keys = {n["id"] for n in document["nodes"] if n["type"] == "hydro"}
        return [{"id": o["id"], "key": o["object_key"], "component_key": o["object_key"],
                 "display_name": o["display_name"], "kind": "hydro", "variables": VARIABLES["hydro"],
                 "schema_version": document["schema_version"]}
                for o in store.list_linkable_objects(project_id=project_id)
                if o["object_type_key"] == "component:hydro" and o["status"] == "active" and o["object_key"] in keys]
    if document["schema_version"] != "bess_system_dispatch.v3":
        raise HTTPException(422, "Este modelo no admite reglas por componente")
    network = document["hydraulic_network"]
    table = store.linkable_object_table_names()["linkable_objects"]
    result = []
    for kind, plural, key, collection in (("hydraulic_unit", "units", "unit_key", "units"),
                                         ("hydraulic_plant", "plants", "plant_key", "plants"),
                                         ("hydraulic_node", "nodes", "node_key", "nodes")):
        rows = store.connection.execute(f"""
            SELECT o.id, entity.{key} AS key, entity.display_name
            FROM {table} o JOIN hydraulic_{plural} entity ON entity.id = o.{kind}_id
            JOIN case_hydraulic_{plural} member ON member.{kind}_id = entity.id
            JOIN optimization_cases c ON c.id = member.case_id
            WHERE c.scenario_id = ? AND o.project_id = ? AND member.is_active = 1 AND o.status = 'active'
        """, (scenario_id, project_id)).fetchall()
        for row in rows:
            physical = next((item for item in network[collection] if item["id"] == row["key"]), None)
            if physical is None or (kind == "hydraulic_node" and physical["type"] != "reservoir"):
                continue
            result.append({**dict(row), "kind": kind, "variables": VARIABLES[kind], key: row["key"]})
    for plant in (item for item in result if item["kind"] == "hydraulic_plant"):
        keys = {u["id"] for u in network["units"] if u["plant_id"] == plant["key"]}
        plant["member_ids"] = sorted(item["id"] for item in result if item["kind"] == "hydraulic_unit" and item["key"] in keys)
    return sorted(result, key=lambda item: item["id"])


def resolve_aliases(store, project_id, object_id, scenario_id, aliases, document=None, code=None):
    if scenario_id is None:
        if aliases:
            object_error(aliases[0]["alias"], aliases[0]["object_id"], code)
        return []
    candidates = model_objects(store, project_id, scenario_id, document, object_id=object_id)
    by_id = {item["id"]: item for item in candidates}
    if object_id not in by_id:
        object_error("objeto", object_id)
    names = set()
    for ref in aliases:
        if ref["alias"] in names or ref["object_id"] not in by_id:
            object_error(ref["alias"], ref["object_id"], code)
        names.add(ref["alias"])
    selected = {object_id, *(ref["object_id"] for ref in aliases)}
    for identity in list(selected):
        selected.update(by_id[identity].get("member_ids", []))
    return [item for item in candidates if item["id"] in selected]
