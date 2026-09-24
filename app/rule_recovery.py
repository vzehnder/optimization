"""Explicit revision lifecycle and recovery of frozen rule applications."""
import json

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from app.component_rules import (RuleDeactivateRequest, RuleDraftRequest, RuleScope, RuleInput,
                                 RuleParameter, RuleObjectAlias, RuleTemporalPolicy, RuleWindowPolicy,
                                 RuleApplyRequest, digest, encode, timestamp)


class RecoveryMappings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    parameters: list[RuleParameter] = Field(max_length=50)
    aliases: list[RuleObjectAlias] = Field(max_length=50)
    inputs: list[RuleInput] = Field(max_length=20)
    temporal: RuleTemporalPolicy | None = None
    windows: RuleWindowPolicy | None = None


class RecoveryPreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(ge=1)
    source_application_id: str
    expected_application_revision: int = Field(ge=1)
    publication_id: str
    scope: RuleScope
    mappings: RecoveryMappings | None = None


class RuleResolutionRequest(RuleApplyRequest):
    request_id: str = Field(min_length=1, max_length=100)


def recovery_state(store, rule_id, variant_id):
    from app.rule_applications import latest_publication
    definitions = []
    for identity in sorted(lifecycle(store, rule_id)):
        definitions.append(dict(store.connection.execute(
            "SELECT id, revision, document FROM component_rule_drafts WHERE id = ?", (identity,),
        ).fetchone()))
    applications = [dict(r) for r in store.connection.execute(
        "SELECT * FROM component_rule_applications WHERE rule_id = ? AND variant_id = ? ORDER BY id", (rule_id, variant_id),
    ).fetchall()]
    return digest({"definitions": definitions, "applications": applications, "head": latest_publication(store, rule_id)})


def prepare_recovery(repository, rule_id, project_id, object_id, body):
    from app.rule_applications import decode_application
    from app.rule_library import validate_instance
    store = repository.store
    draft = repository.get(rule_id, project_id, object_id)
    row = store.connection.execute("SELECT * FROM component_rule_applications WHERE rule_id = ? AND id = ?",
                                   (rule_id, body.source_application_id)).fetchone()
    if row is None:
        raise HTTPException(404, "Aplicación histórica no encontrada")
    source = decode_application(row)
    if draft["revision"] != body.expected_revision or source["revision"] != body.expected_application_revision:
        raise HTTPException(409, "La definición o aplicación cambió; recarga antes de comparar")
    if body.scope.variant_id != source["variant_id"] or body.scope.scenario_id != source["compilation"]["scope"]["scenario_id"]:
        raise HTTPException(422, "La recuperación conserva la variante y el modelo de la aplicación")
    definition_id = draft.get("template", {}).get("rule_id", rule_id)
    publication = repository.publication(definition_id, body.publication_id)
    mappings = body.mappings.model_dump() if body.mappings else {
        k: source.get(k) for k in ("parameters", "aliases", "inputs", "temporal", "windows")}
    mappings["inputs"] = [{k: p[k] for k in RuleInput.model_fields} for p in mappings["inputs"]]
    candidate = {**publication, **mappings, "name": source["name"], "rule_id": rule_id,
                 "scenario_id": body.scope.scenario_id}
    definition = RuleDraftRequest(**{k: candidate[k] for k in ("name", "code", "scenario_id", *mappings)}, expected_revision=body.expected_revision)
    repository.validate(definition, project_id, object_id)
    if draft.get("template"):
        pin = {"rule_id": definition_id, "publication_id": body.publication_id}
        validate_instance(repository, project_id, object_id, definition, pin)
        candidate.update(template=pin, origin=draft.get("origin"))
    return {"publication": candidate, "source_application_id": source["id"],
            "action": "restore" if source["status"] == "inactive" else "retain" if source["publication_id"] == body.publication_id else "replace",
            "state": recovery_state(store, rule_id, source["variant_id"])}


def commit_recovery(repository, rule_id, draft, recovery, body, actor):
    """Called inside the same transaction that inserts the replacement application."""
    store = repository.store
    publication = recovery["publication"]
    event = {"action": recovery["action"], "source_application_id": recovery["source_application_id"],
             "actor": actor, "reason": body.reason.strip(), "at": timestamp()}
    for row in store.connection.execute("SELECT * FROM component_rule_applications WHERE rule_id = ? AND variant_id = ? AND status = 'active'",
                                        (rule_id, recovery["variant_id"])).fetchall():
        previous = json.loads(row["document"])
        previous["events"].append({**event, "action": "supersede"})
        store.connection.execute("UPDATE component_rule_applications SET status = 'inactive', revision = revision + 1, document = ? WHERE id = ?",
                                 (encode(previous), row["id"]))
    if draft.get("template"):
        row = store.connection.execute("SELECT document FROM component_rule_drafts WHERE id = ?", (rule_id,)).fetchone()
        document = json.loads(row["document"])
        document.update({k: publication.get(k) for k in ("parameters", "aliases", "inputs", "temporal", "windows", "template")})
        store.connection.execute("UPDATE component_rule_drafts SET document = ?, revision = revision + 1, updated_at = ?, updated_by = ? WHERE id = ?",
                                 (encode(document), timestamp(), actor, rule_id))
    return event


def comparison_view(document, compilation, inputs, runtime):
    return {"publication_id": document.get("publication_id", document.get("id")),
            "code": document["code"], "code_hash": document["code_hash"], "sdk": runtime.get("sdk"),
            "runtime": runtime, "parameters": document["parameters"],
            "inputs": [{k: v for k, v in p.items() if k != "values"} for p in inputs],
            "aliases": document.get("aliases", []), "objects": compilation.get("objects", []),
            "scope": compilation["scope"], "grid": compilation["grid"], "timezone": compilation["timezone"],
            "temporal": document.get("temporal"), "windows": document.get("windows")}


def compare_recovery(repository, rule_id, project_id, object_id, body):
    from app.rule_applications import compile_context, decode_application
    from app.rule_inputs import freeze_inputs
    from app.rule_objects import resolve_aliases
    store = repository.store
    recovery = prepare_recovery(repository, rule_id, project_id, object_id, body)
    candidate = recovery["publication"]
    source = decode_application(store.connection.execute("SELECT * FROM component_rule_applications WHERE id = ?",
                                                         (body.source_application_id,)).fetchone())
    current = compile_context(store, project_id, object_id, body.scope.model_dump())
    current["aliases"] = candidate["aliases"]
    current["objects"] = resolve_aliases(store, project_id, object_id, body.scope.scenario_id, candidate["aliases"], current["system_case"], candidate["code"])
    inputs = freeze_inputs(store, project_id, object_id, candidate["inputs"], current)
    before = comparison_view(source, source["compilation"], source["inputs"], source["runtime"])
    after = comparison_view(candidate, current, inputs, repository.runtime() or {"sdk": candidate["sdk"]})
    return {"before": before, "after": after, "changed_fields": [k for k in before if before[k] != after[k]],
            "action": recovery["action"]}


def lifecycle(store, rule_id):
    row = store.connection.execute("SELECT document FROM component_rule_drafts WHERE id = ?", (rule_id,)).fetchone()
    document = json.loads(row["document"]) if row else {}
    state = {rule_id: document.get("archive")}
    if document.get("template"):
        state.update(lifecycle(store, document["template"]["rule_id"]))
    return state


def require_available(store, rule_id):
    if any(lifecycle(store, rule_id).values()):
        raise HTTPException(409, "La definición está archivada; resuelve explícitamente sus aplicaciones vigentes")


def consumers(store, project_id, rule_id):
    from app.rule_applications import decode_application
    rows = store.connection.execute("""SELECT a.* FROM component_rule_applications a
        JOIN component_rule_drafts d ON d.id = a.rule_id WHERE d.project_id = ? AND a.status = 'active' ORDER BY a.id""",
        (project_id,)).fetchall()
    items = []
    for row in rows:
        application = decode_application(row)
        if application["rule_id"] == rule_id or (application.get("template") or {}).get("rule_id") == rule_id:
            items.append({"application_id": application["id"], "rule_id": application["rule_id"], "name": application["name"],
                          "project_id": project_id, "object_id": application["object_id"], "variant_id": application["variant_id"],
                          "scenario_id": application["compilation"]["scope"]["scenario_id"]})
    return items


def definition_status(repository, rule_id, revision):
    if any(lifecycle(repository.store, rule_id).values()):
        return "archived"
    from app.rule_library import raw_instance
    if raw_instance(repository.store, rule_id):
        return "published"
    row = repository.store.connection.execute(
        "SELECT 1 FROM component_rule_publications WHERE rule_id = ? AND draft_revision = ?", (rule_id, revision),
    ).fetchone()
    return "published" if row else "draft"


def recovery_router(repository, context):
    store = repository.store
    router = APIRouter(prefix="/api/projects/{project_id}/linkable-objects/{object_id}/rules", tags=["component-rules"])

    @router.get("/{rule_id}/history")
    def history(project_id: int, object_id: int, rule_id: str, request: Request):
        context(request, project_id, object_id)
        from app.rule_applications import list_applications
        with store._lock:
            draft = repository.get(rule_id, project_id, object_id)
            definition_id = draft.get("template", {}).get("rule_id", rule_id)
            rows = store.connection.execute("SELECT p.id, t.contract FROM component_rule_publications p LEFT JOIN component_rule_templates t ON t.publication_id = p.id WHERE p.rule_id = ? ORDER BY p.draft_revision DESC", (definition_id,)).fetchall()
            return {"publications": [repository.publication(definition_id, r["id"]) | {"contract": json.loads(r["contract"]) if r["contract"] else None} for r in rows],
                    "applications": list_applications(repository, rule_id), "lifecycle": lifecycle(store, rule_id),
                    "consumers": consumers(store, project_id, rule_id),
                    "status": definition_status(repository, rule_id, draft["revision"])}

    @router.post("/{rule_id}/comparisons")
    def compare(project_id: int, object_id: int, rule_id: str, body: RecoveryPreviewRequest, request: Request):
        context(request, project_id, object_id)
        with store._lock:
            return compare_recovery(repository, rule_id, project_id, object_id, body)

    @router.post("/{rule_id}/recovery-previews", status_code=202)
    def preview(project_id: int, object_id: int, rule_id: str, body: RecoveryPreviewRequest, request: Request):
        user, obj = context(request, project_id, object_id)
        with store._lock:
            recovery = prepare_recovery(repository, rule_id, project_id, object_id, body)
            recovery["variant_id"] = body.scope.variant_id
            return repository.enqueue(rule_id, project_id, object_id, body.expected_revision, user["id"], obj,
                                      publication_id=body.publication_id, scope=body.scope.model_dump(), recovery=recovery)

    @router.post("/{rule_id}/resolutions", status_code=201)
    def resolve(project_id: int, object_id: int, rule_id: str, body: RuleResolutionRequest, request: Request):
        user, _ = context(request, project_id, object_id)
        from app.rule_applications import apply
        return apply(repository, rule_id, project_id, object_id, body, user["id"], resolving=True)

    @router.post("/{rule_id}/archive")
    def archive(project_id: int, object_id: int, rule_id: str, body: RuleDeactivateRequest, request: Request):
        user, _ = context(request, project_id, object_id)
        with store._lock, store._database_transaction():
            repository.get(rule_id, project_id, object_id)
            row = store.connection.execute("SELECT document FROM component_rule_drafts WHERE id = ?", (rule_id,)).fetchone()
            document = json.loads(row["document"])
            if document.get("archive"):
                raise HTTPException(409, "La definición ya está archivada")
            document["archive"] = {"actor": user["id"], "reason": body.reason.strip(), "at": timestamp()}
            changed = store.connection.execute(
                "UPDATE component_rule_drafts SET document = ?, revision = revision + 1, updated_at = ?, updated_by = ? WHERE id = ? AND revision = ?",
                (encode(document), timestamp(), user["id"], rule_id, body.expected_revision),
            ).rowcount
            if changed != 1:
                raise HTTPException(409, "La definición cambió; recarga antes de archivar")
            return repository.get(rule_id, project_id, object_id)

    return router
