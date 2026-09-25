"""Project library contracts; executable code stays in sealed publications."""
import ast
import json
import uuid
import copy

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from app.component_rules import (encode, digest, timestamp, RuleDraftRequest, RuleParameter,
                                 RuleInput, RuleObjectAlias, RuleTemporalPolicy, RuleWindowPolicy)


class LibraryPublicationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    publication_id: str


class RuleInstanceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    publication_id: str
    scenario_id: int = Field(gt=0)
    variant_id: int = Field(gt=0)
    name: str = Field(min_length=1, max_length=200)
    parameters: list[RuleParameter] = Field(max_length=50)
    aliases: list[RuleObjectAlias] = Field(max_length=50)
    inputs: list[RuleInput] = Field(max_length=20)
    temporal: RuleTemporalPolicy | None = None
    windows: RuleWindowPolicy | None = None
    request_id: str = Field(min_length=1, max_length=100)
    reason: str = Field(min_length=1, max_length=1000, pattern=r"\S")


def initialize(store):
    with store._lock, store._database_transaction():
        store.connection.execute("""
            CREATE TABLE IF NOT EXISTS component_rule_templates (
                publication_id TEXT PRIMARY KEY REFERENCES component_rule_publications(id),
                rule_id TEXT NOT NULL REFERENCES component_rule_drafts(id),
                contract TEXT NOT NULL
            )
        """)
        store.connection.execute("""
            CREATE TABLE IF NOT EXISTS component_rule_instance_requests (
                project_id INTEGER NOT NULL REFERENCES projects(id),
                actor INTEGER NOT NULL REFERENCES users(id),
                request_id TEXT NOT NULL,
                request_hash TEXT NOT NULL,
                rule_id TEXT NOT NULL REFERENCES component_rule_drafts(id),
                PRIMARY KEY (project_id, actor, request_id)
            )
        """)


def raw_instance(store, rule_id):
    row = store.connection.execute("SELECT document FROM component_rule_drafts WHERE id = ?", (rule_id,)).fetchone()
    document = json.loads(row["document"]) if row else {}
    return document if document.get("template") else None


def effective_publication(repository, rule_id, publication_id, instance):
    pin = instance["template"]
    if pin["publication_id"] != publication_id:
        raise HTTPException(409, "La instancia conserva su revisión fijada")
    shared = repository.publication(pin["rule_id"], publication_id)
    revision = repository.store.connection.execute("SELECT revision FROM component_rule_drafts WHERE id = ?", (rule_id,)).fetchone()["revision"]
    return {**shared, **instance, "id": publication_id, "rule_id": rule_id, "instance_revision": revision, "status": "published"}


def validate_instance(repository, project_id, object_id, body, pin):
    row = repository.store.connection.execute("SELECT contract FROM component_rule_templates WHERE publication_id = ? AND rule_id = ?",
                                              (pin["publication_id"], pin["rule_id"])).fetchone()
    if row is None:
        raise HTTPException(422, "La revisión no está disponible como plantilla")
    expected = json.loads(row["contract"])
    shared = repository.publication(pin["rule_id"], pin["publication_id"])
    if body.code != shared["code"]:
        raise HTTPException(422, "El código compartido solo se modifica en la definición de la plantilla")
    actual = contract_for(repository.store, body.model_dump(), object_id, project_id)
    for key in ("parameters", "inputs"):
        identity = "name" if key == "parameters" else "alias"
        if sorted(actual[key], key=lambda x: x[identity]) != sorted(expected[key], key=lambda x: x[identity]):
            raise HTTPException(422, f"Completa {key} sin modificar el contrato de la revisión compartida")
    actual_aliases = {a["alias"]: a["kind"] for a in actual["aliases"]}
    if set(actual_aliases) != {a["alias"] for a in expected["aliases"]} or any(
            actual_aliases[a["alias"]] not in alias_types(a["kind"]) for a in expected["aliases"]):
        raise HTTPException(422, "Completa aliases con objetos que ofrezcan las variables requeridas por la plantilla")
    if actual["temporal"] != expected.get("temporal") or actual["windows"] != expected.get("windows"):
        raise HTTPException(422, "Conserva las políticas temporales y declara las condiciones iniciales de la plantilla")


def create_instance(repository, project_id, object_id, body, actor):
    store = repository.store
    with store._lock, store._database_transaction():
        # Serialize requests for one project across connections as well as threads.
        store.connection.execute("UPDATE projects SET name = name WHERE id = ?", (project_id,))
        request_hash = digest({"object_id": object_id, **body.model_dump()})
        previous = store.connection.execute("SELECT * FROM component_rule_instance_requests WHERE project_id = ? AND actor = ? AND request_id = ?",
                                            (project_id, actor, body.request_id)).fetchone()
        if previous:
            if previous["request_hash"] != request_hash:
                raise HTTPException(409, "Solicitud reutilizada con otra configuración")
            return repository.get(previous["rule_id"], project_id, object_id)
        template = store.connection.execute("""
            SELECT t.* FROM component_rule_templates t JOIN component_rule_drafts d ON d.id = t.rule_id
            WHERE t.publication_id = ? AND d.project_id = ?
        """, (body.publication_id, project_id)).fetchone()
        if template is None:
            raise HTTPException(404, "Plantilla no encontrada en este proyecto")
        store.connection.execute("UPDATE component_rule_drafts SET revision = revision WHERE id = ?", (template["rule_id"],))
        from app.rule_recovery import require_available
        require_available(store, template["rule_id"])
        from app.rule_objects import model_objects
        candidates = model_objects(store, project_id, body.scenario_id, object_id=object_id)
        target = next((o for o in candidates if o["id"] == object_id), None)
        if target is None or target["kind"] not in supported_contract(json.loads(template["contract"]))["compatible_types"]:
            raise HTTPException(422, {"code": "RULE_CAPABILITY_UNSUPPORTED", "message": "El objeto de destino no ofrece las variables requeridas por esta plantilla"})
        try:
            variant = store.get_case_input_variant(body.variant_id)
        except KeyError:
            raise HTTPException(404, "Variante no encontrada") from None
        case = store.get_or_create_case_for_scenario(body.scenario_id)
        if variant["case_id"] != case["id"]:
            raise HTTPException(422, "La variante no pertenece al modelo de destino")
        publication = repository.publication(template["rule_id"], body.publication_id)
        definition = RuleDraftRequest(**body.model_dump(exclude={"publication_id", "variant_id", "request_id", "reason"}),
                                      code=publication["code"], expected_revision=0)
        repository.validate(definition, project_id, object_id)
        validate_instance(repository, project_id, object_id, definition,
                          {"rule_id": template["rule_id"], "publication_id": body.publication_id})
        document = definition.model_dump(exclude={"code", "expected_revision"})
        document.update(template={"rule_id": template["rule_id"], "publication_id": body.publication_id},
                        variant_id=body.variant_id, origin={"action": "instantiate", "actor": actor, "reason": body.reason.strip(), "at": timestamp()})
        identity, now = uuid.uuid4().hex, timestamp()
        store.connection.execute("INSERT INTO component_rule_drafts VALUES (?, ?, ?, 1, ?, ?, ?, ?)",
                                 (identity, project_id, object_id, encode(document), now, now, actor))
        store.connection.execute("INSERT INTO component_rule_instance_requests VALUES (?, ?, ?, ?, ?)",
                                 (project_id, actor, body.request_id, request_hash, identity))
        return repository.get(identity, project_id, object_id)


def require_clone_destinations(store, project_id, object_id, document, object_map):
    from app.rule_objects import model_objects
    candidates = model_objects(store, project_id, document["scenario_id"], object_id=object_map.get(object_id, object_id))
    available = {o["id"]: o for o in candidates}
    missing = []
    for identity in sorted({object_id, *(a["object_id"] for a in document.get("aliases", []))}):
        source = store.get_linkable_object(identity)
        source_kind = source["object_type_key"].removeprefix("component:") if source["object_kind"] == "component" else source["object_kind"]
        target = available.get(object_map.get(identity, identity))
        if target is None or target["kind"] != source_kind:
            missing.append({"object_id": identity, "display_name": source["display_name"],
                            "candidates": [{k: o[k] for k in ("id", "display_name")} for o in candidates
                                           if o["kind"] == source_kind]})
    if missing:
        raise HTTPException(422, {"code": "RULE_REMAP_REQUIRED", "message": "Elige los destinos de las reglas antes de clonar la variante.",
                                  "objects": missing})


def clone_rules(repository, source_variant_id, target_variant_id, actor, object_map=None):
    from app.rule_applications import active_applications, compile_context
    from app.rule_recovery import require_available
    store = repository.store
    object_map = object_map or {}
    copied_rules = set()
    for application in active_applications(store, variant_id=source_variant_id):
        require_available(store, application["rule_id"])
        copied_rules.add(application["rule_id"])
        document = copy.deepcopy(application)
        require_clone_destinations(store, application["project_id"], application["object_id"],
                                   {**document, "scenario_id": application["compilation"]["scope"]["scenario_id"]}, object_map)
        target_object = object_map.get(application["object_id"], application["object_id"])
        from app.rule_objects import resolve_aliases
        for field in ("parameters", "aliases", "inputs"):
            for ref in document.get(field, []):
                if ref.get("object_id") is not None:
                    ref["object_id"] = object_map.get(ref["object_id"], ref["object_id"])
        for ref in (document.get("temporal") or {}).get("initial_values", []):
            ref["object_id"] = object_map.get(ref["object_id"], ref["object_id"])
        current = compile_context(store, application["project_id"], target_object, application["compilation"]["scope"])
        resolve_aliases(store, application["project_id"], target_object, application["compilation"]["scope"]["scenario_id"], document.get("aliases", []), current["system_case"], application["code"])
        origin = {"action": "clone", "source_variant_id": source_variant_id, "source_application_id": application["id"],
                  "source_rule_id": application["rule_id"], "object_map": object_map, "actor": actor, "at": timestamp()}
        instance = raw_instance(store, application["rule_id"])
        rule_id = application["rule_id"]
        if instance:
            instance = copy.deepcopy(instance)
            instance.update(variant_id=target_variant_id, origin=origin)
            rule_id = uuid.uuid4().hex
            source = repository.get(application["rule_id"], application["project_id"], application["object_id"])
            # Copy the applied configuration, even if the editor has newer local changes.
            for field in ("parameters", "aliases", "inputs", "temporal", "windows", "name"):
                instance[field] = document.get(field)
            # Frozen inputs contain lineage; the editable contract contains only its public pin fields.
            instance["inputs"] = [{k: p[k] for k in RuleInput.model_fields} for p in document.get("inputs", [])]
            body = RuleDraftRequest(**{k: instance[k] for k in ("name", "parameters", "inputs", "aliases", "temporal", "windows", "scenario_id")}, code=application["code"], expected_revision=0)
            repository.validate(body, application["project_id"], target_object)
            validate_instance(repository, application["project_id"], target_object, body, instance["template"])
            store.connection.execute("INSERT INTO component_rule_drafts VALUES (?, ?, ?, 1, ?, ?, ?, ?)",
                (rule_id, application["project_id"], target_object, encode(instance), timestamp(), timestamp(), source["updated_by"]))
            document["instance_revision"] = 1
        elif object_map:
            raise HTTPException(422, "Convierte la regla en una instancia reutilizable antes de remapear sus objetos")
        document.update(rule_id=rule_id, object_id=target_object, variant_id=target_variant_id, origin=origin, requires_revalidation=True)
        document["compilation"]["scope"]["variant_id"] = target_variant_id
        document["events"].append(origin)
        identity = uuid.uuid4().hex
        for field in ("id", "rule_id", "publication_id", "job_id", "variant_id", "revision", "status"):
            document.pop(field, None)
        store.connection.execute("INSERT INTO component_rule_applications VALUES (?, ?, ?, ?, ?, 1, 'active', ?)",
            (identity, rule_id, application["publication_id"], application["job_id"], target_variant_id, encode(document)))
    # An unactivated instance is still part of the variant's configuration.
    for row in store.connection.execute("SELECT * FROM component_rule_drafts ORDER BY id").fetchall():
        instance = json.loads(row["document"])
        if row["id"] in copied_rules or not instance.get("template") or instance.get("variant_id") != source_variant_id:
            continue
        require_available(store, row["id"])
        require_clone_destinations(store, row["project_id"], row["object_id"], instance, object_map)
        target_object = object_map.get(row["object_id"], row["object_id"])
        instance.update(variant_id=target_variant_id, origin={"action": "clone", "source_variant_id": source_variant_id,
            "source_rule_id": row["id"], "object_map": object_map, "actor": actor, "at": timestamp()})
        for field in ("parameters", "aliases", "inputs"):
            for ref in instance.get(field, []):
                if ref.get("object_id") is not None:
                    ref["object_id"] = object_map.get(ref["object_id"], ref["object_id"])
        for ref in (instance.get("temporal") or {}).get("initial_values", []):
            ref["object_id"] = object_map.get(ref["object_id"], ref["object_id"])
        shared = repository.publication(instance["template"]["rule_id"], instance["template"]["publication_id"])
        body = RuleDraftRequest(**{k: instance[k] for k in ("name", "parameters", "inputs", "aliases", "temporal", "windows", "scenario_id")}, code=shared["code"], expected_revision=0)
        repository.validate(body, row["project_id"], target_object)
        validate_instance(repository, row["project_id"], target_object, body, instance["template"])
        store.connection.execute("INSERT INTO component_rule_drafts VALUES (?, ?, ?, 1, ?, ?, ?, ?)",
            (uuid.uuid4().hex, row["project_id"], target_object, encode(instance), timestamp(), timestamp(), row["updated_by"]))


def alias_types(kind):
    from app.rule_objects import VARIABLES
    return [target for target, variables in VARIABLES.items() if set(VARIABLES[kind]) <= set(variables)]


def supported_contract(contract):
    # Existing sealed unit templates gain the new adapter without moving their pins.
    result = copy.deepcopy(contract)
    if "hydraulic_unit" in result["compatible_types"] and "hydro" not in result["compatible_types"]:
        result["compatible_types"].append("hydro")
    for alias in result["aliases"]:
        alias["compatible_types"] = alias_types(alias["kind"])
    return result


def contract_for(store, publication, object_id, project_id):
    from app.rule_objects import resolve_aliases, VARIABLES
    objects = resolve_aliases(store, project_id, object_id, publication.get("scenario_id"),
                              publication.get("aliases", []), code=publication["code"])
    by_id = {o["id"]: o for o in objects}
    references = {a["object_id"]: a["alias"] for a in publication.get("aliases", [])}
    references[object_id] = "self"

    def owner(identity):
        return references.get(identity) if identity is not None else None

    try:
        attrs = {n.attr for n in ast.walk(ast.parse(publication["code"])) if isinstance(n, ast.Attribute)}
    except SyntaxError:
        raise HTTPException(422, "Corrige el código antes de ofrecerlo en la biblioteca") from None
    capability = ("affine_budget.v1" if publication.get("windows") else
                  "affine_temporal.v1" if publication.get("temporal") else
                  "affine_hydraulic.v1" if publication.get("aliases") or attrs & {"potencia", "almacenamiento", "vertimiento", "carga", "descarga", "energia", "energia_inicial"} else
                  "affine_flow.v1")
    kind = by_id.get(object_id, {}).get("kind", "hydraulic_unit")
    required = attrs & set(VARIABLES[kind])
    compatible = [target for target in ("hydraulic_unit", "hydro", "battery") if required <= set(VARIABLES[target])
                  and ("energia_inicial" not in attrs or target == "battery")]
    return {
        "compatible_types": compatible, "required_capabilities": [capability],
        "parameters": [{k: v for k, v in p.items() if k not in {"value", "object_id"}} | {"owner": owner(p.get("object_id"))}
                       for p in publication["parameters"]],
        "aliases": [{"alias": a["alias"], "kind": by_id[a["object_id"]]["kind"]} for a in publication.get("aliases", [])],
        "inputs": [{k: p[k] for k in ("alias", "dimension_key", "semantic_type_key", "binding_role_key")}
                   | {"owner": owner(p["object_id"])} for p in publication.get("inputs", [])],
        "temporal": ({"first_period": publication["temporal"]["first_period"],
                      "initial_values": [{"owner": owner(v["object_id"]), "variable": v["variable"], "unit": v["unit"]}
                                         for v in publication["temporal"]["initial_values"]]} if publication.get("temporal") else None),
        "windows": publication.get("windows"),
    }


def promote(repository, rule_id, project_id, object_id, publication_id):
    store = repository.store
    with store._lock, store._database_transaction():
        repository.get(rule_id, project_id, object_id)
        from app.rule_recovery import require_available
        require_available(store, rule_id)
        publication = repository.publication(rule_id, publication_id)
        contract = contract_for(store, publication, object_id, project_id)
        store.connection.execute("INSERT INTO component_rule_templates VALUES (?, ?, ?) ON CONFLICT (publication_id) DO NOTHING",
                                 (publication_id, rule_id, encode(contract)))
        return {"rule_id": rule_id, "publication_id": publication_id, **contract}


def compare_instances(repository, project_id, publication_id):
    from app.rule_applications import list_applications, compile_context, assert_objects_current, latest_publication
    from app.rule_inputs import assert_inputs_current
    store = repository.store
    template = store.connection.execute("""SELECT t.rule_id FROM component_rule_templates t
        JOIN component_rule_drafts d ON d.id = t.rule_id WHERE t.publication_id = ? AND d.project_id = ?""",
        (publication_id, project_id)).fetchone()
    if not template:
        raise HTTPException(404, "Plantilla no encontrada en este proyecto")
    items = []
    for row in store.connection.execute("SELECT id, object_id, document FROM component_rule_drafts WHERE project_id = ? ORDER BY created_at", (project_id,)).fetchall():
        document = json.loads(row["document"])
        if document.get("template", {}).get("publication_id") != publication_id:
            continue
        draft = repository.get(row["id"], project_id, row["object_id"])
        application = next((a for a in list_applications(repository, draft["id"]) if a["status"] == "active"), None)
        preview = None
        job = store.connection.execute("""SELECT s.payload, j.result FROM component_rule_snapshots s
            JOIN component_rule_jobs j ON j.id = s.id
            WHERE s.rule_id = ? AND s.draft_revision = ? AND j.status = 'succeeded'
            ORDER BY s.created_at DESC LIMIT 1""", (draft["id"], draft["revision"])).fetchone()
        if job:
            payload = json.loads(job["payload"])
            try:
                current = compile_context(store, project_id, row["object_id"], payload["compilation"]["scope"])
                assert_objects_current(store, project_id, row["object_id"], payload["compilation"], current, draft["code"])
                assert_inputs_current(store, project_id, row["object_id"], payload.get("inputs", []), payload.get("aliases", []))
                if current["fingerprint"] == payload["compilation"]["fingerprint"] and latest_publication(store, draft["id"]) == payload["publication_head"]:
                    ir = json.loads(job["result"])["ir"]
                    preview = {"row_count": len(ir["rows"]), "rows": ir["rows"][:100], "scope": payload["compilation"]["scope"]}
            except (HTTPException, KeyError, ValueError):
                pass
        items.append({k: draft[k] for k in ("id", "name", "object_id", "variant_id", "revision", "parameters", "aliases", "inputs")}
                     | {"preview": preview, "activation": "active" if application else "inactive",
                        "validation_status": application["validation_status"] if application else "pending"})
    return {"items": items}


def library_router(repository, context):
    store = repository.store
    router = APIRouter(tags=["component-rules"])

    def internal_user(request):
        user = getattr(request.state, "current_user", None)
        if not user or user["role"] not in {"analyst", "admin"}:
            raise HTTPException(403 if user else 401, "Acceso denegado")
        return user

    @router.get("/api/projects/{project_id}/rule-library/{publication_id}/instances")
    def instances(project_id: int, publication_id: str, request: Request):
        internal_user(request)
        with store._lock:
            return compare_instances(repository, project_id, publication_id)

    @router.post("/api/projects/{project_id}/linkable-objects/{object_id}/rules/instances", status_code=201)
    def instantiate(project_id: int, object_id: int, body: RuleInstanceRequest, request: Request):
        user, _ = context(request, project_id, object_id)
        return create_instance(repository, project_id, object_id, body, user["id"])

    @router.post("/api/projects/{project_id}/linkable-objects/{object_id}/rules/{rule_id}/library", status_code=201)
    def publish_template(project_id: int, object_id: int, rule_id: str, body: LibraryPublicationRequest, request: Request):
        context(request, project_id, object_id)
        return promote(repository, rule_id, project_id, object_id, body.publication_id)

    @router.get("/api/projects/{project_id}/rule-library")
    def list_templates(project_id: int, request: Request):
        internal_user(request)
        with store._lock:
            rows = store.connection.execute("""
                SELECT t.*, p.draft_revision, p.document FROM component_rule_templates t
                JOIN component_rule_drafts d ON d.id = t.rule_id
                JOIN component_rule_publications p ON p.id = t.publication_id
                WHERE d.project_id = ? ORDER BY p.created_at DESC
            """, (project_id,)).fetchall()
            from app.rule_recovery import lifecycle
            return {"items": [{"rule_id": r["rule_id"], "publication_id": r["publication_id"],
                               "revision": r["draft_revision"], "name": json.loads(r["document"])["name"],
                               **supported_contract(json.loads(r["contract"]))} for r in rows if not any(lifecycle(store, r["rule_id"]).values())]}

    return router
