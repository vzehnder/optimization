"""Project-owned Python drafts. Execution is delegated to an OCI sandbox."""
from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from app.linkable_objects import LinkableObjectError


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def digest(value):
    return hashlib.sha256(encode(value).encode()).hexdigest()


def project_enabled(project_id):
    allowed = os.environ.get("RULE_ENABLED_PROJECTS", "*").strip()
    return allowed == "*" or str(project_id) in {item.strip() for item in allowed.split(",")}


class RuleParameter(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    name: str = Field(pattern=r"^[a-zA-Z][a-zA-Z0-9_]{0,63}$")
    type: Literal["number", "integer", "boolean"]
    unit: str = Field(max_length=64)
    value: float | bool
    min: float | None = None
    max: float | None = None


class RuleDraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=200)
    code: str = Field(min_length=1, max_length=65536)
    parameters: list[RuleParameter] = Field(max_length=50)
    expected_revision: int = Field(ge=0)


class RuleTestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(ge=1)


class RuleRepository:
    def __init__(self, store):
        self.store = store
        objects = store.linkable_object_table_names()["linkable_objects"]
        with store._lock, store._database_transaction():
            store.connection.execute(f"""
                CREATE TABLE IF NOT EXISTS component_rule_drafts (
                    id TEXT PRIMARY KEY,
                    project_id INTEGER NOT NULL REFERENCES projects(id),
                    object_id INTEGER NOT NULL REFERENCES {objects}(id),
                    revision INTEGER NOT NULL CHECK (revision > 0),
                    document TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    updated_by INTEGER NOT NULL REFERENCES users(id)
                )
            """)
            store.connection.execute("""
                CREATE TABLE IF NOT EXISTS component_rule_worker (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    owner TEXT NOT NULL,
                    heartbeat DOUBLE PRECISION NOT NULL,
                    runtime TEXT NOT NULL
                )
            """)
            store.connection.execute("""
                CREATE TABLE IF NOT EXISTS component_rule_snapshots (
                    id TEXT PRIMARY KEY,
                    rule_id TEXT NOT NULL REFERENCES component_rule_drafts(id),
                    draft_revision INTEGER NOT NULL,
                    payload TEXT NOT NULL,
                    code_hash TEXT NOT NULL,
                    context_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            store.connection.execute("""
                CREATE TABLE IF NOT EXISTS component_rule_jobs (
                    id TEXT PRIMARY KEY REFERENCES component_rule_snapshots(id),
                    actor INTEGER NOT NULL REFERENCES users(id),
                    status TEXT NOT NULL CHECK (status IN ('queued', 'running', 'succeeded', 'failed', 'cancelled')),
                    cancel_requested INTEGER NOT NULL DEFAULT 0,
                    result TEXT,
                    queued_at DOUBLE PRECISION NOT NULL,
                    updated_at TEXT NOT NULL,
                    worker_owner TEXT
                )
            """)
            store.connection.execute("CREATE INDEX IF NOT EXISTS component_rule_jobs_queue ON component_rule_jobs(status, queued_at)")

    def runtime(self):
        with self.store._lock:
            row = self.store.connection.execute("SELECT * FROM component_rule_worker WHERE id = 1").fetchone()
        if row is None or time.time() - row["heartbeat"] > 10 or row["runtime"] == '{}':
            return None
        return json.loads(row["runtime"])

    def enqueue(self, rule_id, project_id, object_id, expected_revision, actor, obj):
        if not project_enabled(project_id):
            raise HTTPException(503, {"code": "RULE_PROJECT_DISABLED", "message": "Las pruebas están deshabilitadas en este proyecto"})
        with self.store._lock, self.store._database_transaction():
            self.store.connection.execute("UPDATE component_rule_worker SET heartbeat = heartbeat WHERE id = 1")
            runtime = self.runtime()
            if runtime is None:
                raise HTTPException(503, {"code": "RULE_RUNTIME_UNAVAILABLE", "message": "El ejecutor aislado no está disponible"})
            draft = self.get(rule_id, project_id, object_id)
            if draft["revision"] != expected_revision:
                raise HTTPException(409, "El borrador cambió. Guarda o recarga antes de probar.")
            active = self.store.connection.execute(
                "SELECT actor, status FROM component_rule_jobs WHERE status IN ('queued', 'running')"
            ).fetchall()
            if sum(row["status"] == "queued" for row in active) >= 20 or any(row["actor"] == actor for row in active):
                raise HTTPException(429, "Cola completa o ya tienes una prueba pendiente")
            job_id = uuid.uuid4().hex
            context = {"object": {"id": object_id, "key": obj["object_key"], "project_id": project_id},
                       "parameters": draft["parameters"], "runtime": runtime}
            payload = {"code": draft["code"], **context}
            self.store.connection.execute(
                "INSERT INTO component_rule_snapshots VALUES (?, ?, ?, ?, ?, ?, ?)",
                (job_id, rule_id, expected_revision, encode(payload), draft["code_hash"], digest(context), timestamp()),
            )
            self.store.connection.execute(
                "INSERT INTO component_rule_jobs (id, actor, status, queued_at, updated_at) VALUES (?, ?, 'queued', ?, ?)",
                (job_id, actor, time.time(), timestamp()),
            )
            return self.job(job_id, rule_id, project_id, object_id)

    def job(self, job_id, rule_id, project_id, object_id):
        self.get(rule_id, project_id, object_id)
        with self.store._lock:
            row = self.store.connection.execute(
                "SELECT j.*, s.rule_id, s.draft_revision, s.code_hash, s.context_hash, s.payload "
                "FROM component_rule_jobs j JOIN component_rule_snapshots s ON s.id = j.id "
                "WHERE j.id = ? AND s.rule_id = ?", (job_id, rule_id),
            ).fetchone()
        if row is None:
            raise HTTPException(404, "Prueba no encontrada")
        result = dict(row)
        result.pop("worker_owner")
        result["runtime"] = json.loads(result.pop("payload"))["runtime"]
        result["result"] = json.loads(result["result"]) if result["result"] else None
        if result["result"] is not None:
            result["result"]["runtime"] = {**result["runtime"], **result["result"].get("runtime", {})}
        return {**result, "applied": False}

    def get(self, rule_id, project_id, object_id):
        with self.store._lock:
            row = self.store.connection.execute(
                "SELECT * FROM component_rule_drafts WHERE id = ? AND project_id = ? AND object_id = ?",
                (rule_id, project_id, object_id),
            ).fetchone()
        if row is None:
            raise HTTPException(404, "Regla no encontrada")
        data = dict(row)
        data.update(json.loads(data.pop("document")))
        return {**data, "status": "draft", "code_hash": digest(data["code"])}

    def create(self, project_id, object_id, body, actor):
        if body.expected_revision != 0:
            raise HTTPException(409, "La creación requiere revisión 0")
        self.validate(body)
        rule_id, now = uuid.uuid4().hex, timestamp()
        document = body.model_dump(exclude={"expected_revision"})
        with self.store._lock, self.store._database_transaction():
            self.store.connection.execute(
                "INSERT INTO component_rule_drafts VALUES (?, ?, ?, 1, ?, ?, ?, ?)",
                (rule_id, project_id, object_id, encode(document), now, now, actor),
            )
        return self.get(rule_id, project_id, object_id)

    def update(self, rule_id, project_id, object_id, body, actor):
        self.validate(body)
        document = body.model_dump(exclude={"expected_revision"})
        with self.store._lock, self.store._database_transaction():
            self.get(rule_id, project_id, object_id)
            changed = self.store.connection.execute(
                "UPDATE component_rule_drafts SET document = ?, revision = revision + 1, "
                "updated_at = ?, updated_by = ? WHERE id = ? AND revision = ?",
                (encode(document), timestamp(), actor, rule_id, body.expected_revision),
            ).rowcount
            if changed != 1:
                raise HTTPException(409, "El borrador cambió. Recarga antes de guardar.")
            return self.get(rule_id, project_id, object_id)

    def validate(self, body):
        if len(body.code.encode("utf-8")) > 65536:
            raise HTTPException(422, "El código excede 64 KiB")
        names = set()
        for parameter in body.parameters:
            value = parameter.value
            invalid = parameter.name in names
            names.add(parameter.name)
            invalid |= (parameter.type == "boolean") != isinstance(value, bool)
            invalid |= parameter.type == "integer" and not float(value).is_integer()
            invalid |= parameter.min is not None and value < parameter.min
            invalid |= parameter.max is not None and value > parameter.max
            invalid |= parameter.type == "boolean" and parameter.unit != "dimensionless"
            unit = self.store.connection.execute(
                "SELECT unit_key FROM measurement_units WHERE unit_key = ? AND status = 'active'",
                (parameter.unit,),
            ).fetchone()
            if invalid or unit is None:
                raise HTTPException(422, f"Contrato inválido para parámetro {parameter.name}")


def rule_router(store):
    repository = RuleRepository(store)
    router = APIRouter(prefix="/api/projects/{project_id}/linkable-objects/{object_id}/rules", tags=["component-rules"])

    def context(request, project_id, object_id):
        user = getattr(request.state, "current_user", None)
        if not user:
            raise HTTPException(401, "Autenticación requerida")
        if user["role"] not in {"analyst", "admin"}:
            raise HTTPException(403, "Acceso denegado")
        try:
            obj = store.get_linkable_object(object_id)
        except LinkableObjectError:
            raise HTTPException(404, "Objeto no encontrado") from None
        if obj["project_id"] != project_id:
            raise HTTPException(404, "Objeto no encontrado")
        if obj["object_kind"] != "hydraulic_unit" or obj["status"] != "active":
            raise HTTPException(422, "Esta capacidad requiere una unidad hidráulica activa")
        return user, obj

    @router.post("", status_code=201)
    def create_rule(project_id: int, object_id: int, body: RuleDraftRequest, request: Request):
        user, _ = context(request, project_id, object_id)
        return repository.create(project_id, object_id, body, user["id"])

    @router.get("")
    def list_rules(project_id: int, object_id: int, request: Request):
        _, obj = context(request, project_id, object_id)
        with store._lock:
            rows = store.connection.execute(
                "SELECT id, revision, document FROM component_rule_drafts WHERE project_id = ? AND object_id = ? ORDER BY created_at",
                (project_id, object_id),
            ).fetchall()
        return {"object": {"id": obj["id"], "display_name": obj["display_name"]},
                "items": [{"id": row["id"], "name": json.loads(row["document"])["name"], "revision": row["revision"]} for row in rows],
                "runtime": repository.runtime() if project_enabled(project_id) else None,
                "enabled": project_enabled(project_id)}

    @router.get("/{rule_id}")
    def get_rule(project_id: int, object_id: int, rule_id: str, request: Request):
        context(request, project_id, object_id)
        return repository.get(rule_id, project_id, object_id)

    @router.put("/{rule_id}")
    def update_rule(project_id: int, object_id: int, rule_id: str, body: RuleDraftRequest, request: Request):
        user, _ = context(request, project_id, object_id)
        return repository.update(rule_id, project_id, object_id, body, user["id"])

    @router.post("/{rule_id}/tests", status_code=202)
    def start_test(project_id: int, object_id: int, rule_id: str, body: RuleTestRequest, request: Request):
        user, obj = context(request, project_id, object_id)
        return repository.enqueue(rule_id, project_id, object_id, body.expected_revision, user["id"], obj)

    @router.get("/{rule_id}/tests/{job_id}")
    def get_test(project_id: int, object_id: int, rule_id: str, job_id: str, request: Request):
        context(request, project_id, object_id)
        return repository.job(job_id, rule_id, project_id, object_id)

    @router.get("/{rule_id}/revisions/{revision_id}")
    def get_revision(project_id: int, object_id: int, rule_id: str, revision_id: str, request: Request):
        context(request, project_id, object_id)
        repository.get(rule_id, project_id, object_id)
        with store._lock:
            row = store.connection.execute(
                "SELECT * FROM component_rule_snapshots WHERE id = ? AND rule_id = ?", (revision_id, rule_id),
            ).fetchone()
        if row is None:
            raise HTTPException(404, "Revisión no encontrada")
        result = dict(row)
        result.update(json.loads(result.pop("payload")))
        return {**result, "status": "sealed_preview"}

    @router.post("/{rule_id}/tests/{job_id}/cancel")
    def cancel_test(project_id: int, object_id: int, rule_id: str, job_id: str, request: Request):
        user, _ = context(request, project_id, object_id)
        with store._lock, store._database_transaction():
            job = repository.job(job_id, rule_id, project_id, object_id)
            if job["actor"] != user["id"] and user["role"] != "admin":
                raise HTTPException(403, "Solo el autor o un administrador puede cancelar")
            store.connection.execute(
                "UPDATE component_rule_jobs SET cancel_requested = 1, "
                "status = CASE WHEN status = 'queued' THEN 'cancelled' ELSE status END, updated_at = ? "
                "WHERE id = ? AND status IN ('queued', 'running')", (timestamp(), job_id),
            )
            return repository.job(job_id, rule_id, project_id, object_id)

    routes = APIRouter()
    routes.include_router(router)

    @routes.get("/api/scenarios/{scenario_id}/hydraulic-plants/{plant_key}/units/{unit_key}/rule-context", tags=["component-rules"])
    def hydraulic_context(scenario_id: int, plant_key: str, unit_key: str, request: Request):
        user = getattr(request.state, "current_user", None)
        if not user or user["role"] not in {"analyst", "admin"}:
            raise HTTPException(403 if user else 401, "Acceso denegado")
        objects = store.linkable_object_table_names()["linkable_objects"]
        with store._lock:
            row = store.connection.execute(f"""
                SELECT registered.project_id, registered.id AS object_id
                FROM optimization_cases c
                JOIN case_hydraulic_units cu ON cu.case_id = c.id
                JOIN hydraulic_units u ON u.id = cu.hydraulic_unit_id
                JOIN hydraulic_plants p ON p.id = u.hydraulic_plant_id
                JOIN {objects} registered ON registered.hydraulic_unit_id = u.id
                WHERE c.scenario_id = ? AND p.plant_key = ? AND u.unit_key = ?
                  AND cu.is_active = 1 AND registered.status = 'active'
            """, (scenario_id, plant_key, unit_key)).fetchone()
        if row is None:
            raise HTTPException(404, "Guarda primero la unidad activa en el diagrama")
        return dict(row)

    return routes
