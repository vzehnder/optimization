"""Project-owned Python drafts. Execution is delegated to an OCI sandbox."""
from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

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
    object_id: int | None = Field(default=None, gt=0)


class RuleInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    alias: str = Field(pattern=r"^[a-zA-Z][a-zA-Z0-9_]{0,63}$")
    dimension_key: str = Field(max_length=64)
    semantic_type_key: str = Field(max_length=64)
    binding_role_key: Literal["rule_inflow", "rule_availability"]
    object_id: int = Field(gt=0)
    signal_id: int = Field(gt=0)
    revision_id: int = Field(gt=0)
    content_hash: str = Field(pattern=r"^[a-f0-9]{64}$")


class RuleObjectAlias(BaseModel):
    model_config = ConfigDict(extra="forbid")
    alias: str = Field(pattern=r"^[a-zA-Z][a-zA-Z0-9_]{0,63}$")
    object_id: int = Field(gt=0)


class RuleInitialValue(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    object_id: int = Field(gt=0)
    variable: Literal["caudal", "potencia", "almacenamiento", "vertimiento"]
    value: float
    unit: str = Field(max_length=64)
    timestamp: str = Field(max_length=64)

    @field_validator("timestamp")
    @classmethod
    def explicit_instant(cls, value):
        if datetime.fromisoformat(value.replace("Z", "+00:00")).tzinfo is None:
            raise ValueError("El instante inicial requiere UTC u offset explícito")
        return value


class RuleTemporalPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")
    first_period: Literal["omit", "initial"]
    initial_values: list[RuleInitialValue] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def consistent_policy(self):
        if (self.first_period == "initial") != bool(self.initial_values):
            raise ValueError("Declara valores iniciales solo con la política de condición inicial")
        keys = {(v.object_id, v.variable) for v in self.initial_values}
        if len(keys) != len(self.initial_values):
            raise ValueError("Cada variable debe tener un único valor inicial")
        return self


class RuleWindowPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["horizon", "civil_day"]
    timezone: str = Field(min_length=1, max_length=100)
    partial: Literal["reject", "allow"]

    @field_validator("timezone")
    @classmethod
    def iana_zone(cls, value):
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError("Selecciona una zona horaria IANA conocida") from None
        return value


class RuleDraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=200)
    code: str = Field(min_length=1, max_length=65536)
    parameters: list[RuleParameter] = Field(max_length=50)
    inputs: list[RuleInput] = Field(default_factory=list, max_length=20)
    aliases: list[RuleObjectAlias] = Field(default_factory=list, max_length=50)
    scenario_id: int | None = Field(default=None, gt=0)
    temporal: RuleTemporalPolicy | None = None
    windows: RuleWindowPolicy | None = None
    expected_revision: int = Field(ge=0)


class RuleScope(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scenario_id: int = Field(gt=0)
    variant_id: int = Field(gt=0)
    range_start: str = Field(max_length=64)
    range_end: str = Field(max_length=64)

    @field_validator("range_start", "range_end")
    @classmethod
    def valid_instant(cls, value):
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        return value


class RuleTestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(ge=1)
    publication_id: str | None = None
    scope: RuleScope | None = None


class RuleApplyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    job_id: str
    reason: str = Field(min_length=1, max_length=1000, pattern=r"\S")
    accept_empty: bool = False


class RuleDeactivateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(ge=1)
    reason: str = Field(min_length=1, max_length=1000, pattern=r"\S")


class SeriesPublicationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    job_id: str
    output_name: str = Field(min_length=1, max_length=200)
    name: str = Field(min_length=1, max_length=200, pattern=r"\S")
    series_key: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    semantic_type_key: str = Field(min_length=1, max_length=64)
    unit_key: str = Field(min_length=1, max_length=64)
    series_kind: Literal["catalog", "object_specific"] = "catalog"
    intended_binding_role_key: str | None = Field(default=None, max_length=64)
    reason: str = Field(min_length=1, max_length=1000, pattern=r"\S")


class SeriesRegenerationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    job_id: str
    expected_revision_id: int = Field(gt=0)
    reason: str = Field(min_length=1, max_length=1000, pattern=r"\S")


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
            store.connection.execute("""
                CREATE TABLE IF NOT EXISTS component_rule_publications (
                    id TEXT PRIMARY KEY,
                    rule_id TEXT NOT NULL REFERENCES component_rule_drafts(id),
                    draft_revision INTEGER NOT NULL,
                    document TEXT NOT NULL,
                    created_by INTEGER NOT NULL REFERENCES users(id),
                    created_at TEXT NOT NULL,
                    UNIQUE (rule_id, draft_revision)
                )
            """)
        from app.rule_applications import initialize
        initialize(store)
        from app.rule_series import initialize as initialize_series
        initialize_series(store)

    def publication(self, rule_id, publication_id):
        row = self.store.connection.execute(
            "SELECT * FROM component_rule_publications WHERE id = ? AND rule_id = ?", (publication_id, rule_id),
        ).fetchone()
        if row is None:
            raise HTTPException(404, "Revisión publicada no encontrada")
        result = dict(row)
        result.update(json.loads(result.pop("document")))
        return {**result, "status": "published"}

    def publish(self, rule_id, project_id, object_id, expected_revision, actor):
        from app.rule_runtime import SDK_VERSION
        with self.store._lock, self.store._database_transaction():
            self.store.connection.execute("UPDATE component_rule_drafts SET revision = revision WHERE id = ?", (rule_id,))
            draft = self.get(rule_id, project_id, object_id)
            if draft["revision"] != expected_revision:
                raise HTTPException(409, "El borrador cambió. Recarga antes de publicar.")
            previous = self.store.connection.execute(
                "SELECT id FROM component_rule_publications WHERE rule_id = ? AND draft_revision = ?", (rule_id, expected_revision),
            ).fetchone()
            if previous:
                return self.publication(rule_id, previous["id"])
            identity = uuid.uuid4().hex
            document = {key: draft[key] for key in ("code", "parameters", "name", "code_hash")}
            document["inputs"] = draft.get("inputs", [])
            document["aliases"] = draft.get("aliases", [])
            document["scenario_id"] = draft.get("scenario_id")
            document["temporal"] = draft.get("temporal")
            document["windows"] = draft.get("windows")
            document["sdk"] = SDK_VERSION
            self.store.connection.execute("INSERT INTO component_rule_publications VALUES (?, ?, ?, ?, ?, ?)",
                                          (identity, rule_id, expected_revision, encode(document), actor, timestamp()))
            return self.publication(rule_id, identity)

    def runtime(self):
        with self.store._lock:
            row = self.store.connection.execute("SELECT * FROM component_rule_worker WHERE id = 1").fetchone()
        if row is None or time.time() - row["heartbeat"] > 10 or row["runtime"] == '{}':
            return None
        return json.loads(row["runtime"])

    def enqueue(self, rule_id, project_id, object_id, expected_revision, actor, obj, *, publication_id=None, scope=None):
        if not project_enabled(project_id):
            raise HTTPException(503, {"code": "RULE_PROJECT_DISABLED", "message": "Las pruebas están deshabilitadas en este proyecto"})
        compilation = None
        if scope is not None:
            from app.rule_applications import compile_context
            try:
                with self.store._lock:
                    compilation = compile_context(self.store, project_id, object_id, scope)
            except KeyError as error:
                raise HTTPException(404, "Contexto de regla no encontrado") from error
            except ValueError as error:
                raise HTTPException(422, str(error)) from error
        if bool(publication_id) != bool(compilation):
            raise HTTPException(422, "Selecciona revisión publicada y variante para probar restricciones")
        with self.store._lock, self.store._database_transaction():
            self.store.connection.execute("UPDATE component_rule_worker SET heartbeat = heartbeat WHERE id = 1")
            runtime = self.runtime()
            if runtime is None:
                raise HTTPException(503, {"code": "RULE_RUNTIME_UNAVAILABLE", "message": "El ejecutor aislado no está disponible"})
            draft = self.get(rule_id, project_id, object_id)
            if draft["revision"] != expected_revision:
                raise HTTPException(409, "El borrador cambió. Guarda o recarga antes de probar.")
            if publication_id:
                draft = self.publication(rule_id, publication_id)
                if draft["sdk"] != runtime["sdk"]:
                    raise HTTPException(409, "La revisión publicada usa otro SDK; vuelve a publicar")
            active = self.store.connection.execute(
                "SELECT actor, status FROM component_rule_jobs WHERE status IN ('queued', 'running')"
            ).fetchall()
            if sum(row["status"] == "queued" for row in active) >= 20 or any(row["actor"] == actor for row in active):
                raise HTTPException(429, "Cola completa o ya tienes una prueba pendiente")
            job_id = uuid.uuid4().hex
            context = {"object": {"id": object_id, "key": obj["object_key"], "project_id": project_id},
                       "parameters": draft["parameters"], "runtime": runtime, "temporal": draft.get("temporal"),
                       "windows": draft.get("windows")}
            if compilation:
                from app.rule_applications import latest_publication
                from app.rule_inputs import freeze_inputs
                from app.rule_objects import resolve_aliases, object_error
                aliases = draft.get("aliases", [])
                if draft.get("scenario_id") not in (None, scope["scenario_id"]):
                    object_error("objeto", object_id)
                objects = resolve_aliases(self.store, project_id, object_id, scope["scenario_id"], aliases, compilation["system_case"], draft["code"])
                compilation.update(objects=objects, aliases=aliases)
                context.update(objects=objects, aliases=aliases)
                context.update(compilation=compilation, grid=compilation["grid"], publication_id=publication_id)
                context["publication_head"] = latest_publication(self.store, rule_id)
                context["inputs"] = freeze_inputs(self.store, project_id, object_id, draft.get("inputs", []), compilation)
            elif draft.get("inputs"):
                raise HTTPException(422, "Las entradas horarias requieren revisión publicada, variante y horizonte")
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
        payload = json.loads(result.pop("payload"))
        result["runtime"] = payload["runtime"]
        if "compilation" in payload:
            result["compilation_scope"] = payload["compilation"]["scope"]
            result["grid"] = payload["grid"]
            result["publication_id"] = payload["publication_id"]
            result["objects"] = payload.get("objects", [])
            result["aliases"] = payload.get("aliases", [])
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
        rule_id, now = uuid.uuid4().hex, timestamp()
        document = body.model_dump(exclude={"expected_revision"})
        with self.store._lock, self.store._database_transaction():
            self.validate(body, project_id, object_id)
            self.store.connection.execute(
                "INSERT INTO component_rule_drafts VALUES (?, ?, ?, 1, ?, ?, ?, ?)",
                (rule_id, project_id, object_id, encode(document), now, now, actor),
            )
        return self.get(rule_id, project_id, object_id)

    def update(self, rule_id, project_id, object_id, body, actor):
        document = body.model_dump(exclude={"expected_revision"})
        with self.store._lock, self.store._database_transaction():
            self.validate(body, project_id, object_id)
            self.get(rule_id, project_id, object_id)
            changed = self.store.connection.execute(
                "UPDATE component_rule_drafts SET document = ?, revision = revision + 1, "
                "updated_at = ?, updated_by = ? WHERE id = ? AND revision = ?",
                (encode(document), timestamp(), actor, rule_id, body.expected_revision),
            ).rowcount
            if changed != 1:
                raise HTTPException(409, "El borrador cambió. Recarga antes de guardar.")
            return self.get(rule_id, project_id, object_id)

    def validate(self, body, project_id, object_id):
        from app.rule_objects import resolve_aliases, object_error
        objects = resolve_aliases(self.store, project_id, object_id, body.scenario_id, [a.model_dump() for a in body.aliases], code=body.code)
        allowed = {object_id, *(a.object_id for a in body.aliases)}
        if body.temporal:
            variables = {o["id"]: o["variables"] for o in objects} or {object_id: {"caudal": "m3_per_s", "potencia": "mw"}}
            for initial in body.temporal.initial_values:
                if initial.object_id not in allowed or variables.get(initial.object_id, {}).get(initial.variable) != initial.unit:
                    raise HTTPException(422, {"code": "RULE_INITIAL_INVALID", "message": "Valor inicial: objeto, variable o dimensión incompatible",
                                              "object_id": initial.object_id, "variable": initial.variable, "period": 0})
        from app.rule_inputs import validate_inputs
        validate_inputs(self.store, project_id, allowed, [p.model_dump() for p in body.inputs])
        if len(body.code.encode("utf-8")) > 65536:
            raise HTTPException(422, "El código excede 64 KiB")
        names = set()
        for parameter in body.parameters:
            if parameter.object_id is not None and parameter.object_id not in allowed:
                object_error(parameter.name, parameter.object_id)
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
            with store._lock:
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

    @router.get("/scope")
    def get_rule_scope(project_id: int, object_id: int, scenario_id: int, request: Request):
        from app.rule_applications import instant
        from datetime import timedelta
        context(request, project_id, object_id)
        with store._lock:
            try:
                scenario = store.get_scenario(scenario_id)
                if scenario["project_id"] != project_id:
                    raise HTTPException(404, "Escenario fuera del proyecto")
                case = store.get_or_create_case_for_scenario(scenario_id)
                store.get_or_create_default_input_variant(case["id"])
                variants = store.list_case_input_variants(case["id"])
                result = {"variants": variants, "range_start": "", "range_end": ""}
                periods = store.generate_hydraulic_v3_preview(scenario_id)["time_series"]
                if periods:
                    result["range_start"] = periods[0]["timestamp"]
                    result["range_end"] = (instant(periods[-1]["timestamp"]) + timedelta(hours=periods[-1]["duration_hours"])).replace(tzinfo=None).isoformat()
                return result
            except KeyError:
                raise HTTPException(404, "Contexto del escenario no encontrado") from None
            except ValueError as error:
                raise HTTPException(422, str(error)) from error

    @router.get("/object-candidates")
    def get_object_candidates(project_id: int, object_id: int, scenario_id: int, request: Request):
        from app.rule_objects import model_objects, object_error
        context(request, project_id, object_id)
        with store._lock:
            items = model_objects(store, project_id, scenario_id)
            if object_id not in {item["id"] for item in items}:
                object_error("objeto", object_id)
            return {"items": items}

    @router.get("/input-candidates")
    def get_input_candidates(project_id: int, object_id: int, request: Request,
                             after: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100),
                             reference_object_id: int | None = Query(None, gt=0), scenario_id: int | None = Query(None, gt=0)):
        from app.rule_inputs import input_candidates
        context(request, project_id, object_id)
        with store._lock:
            if reference_object_id is not None and reference_object_id != object_id:
                from app.rule_objects import resolve_aliases
                resolve_aliases(store, project_id, object_id, scenario_id, [{"alias": "entrada", "object_id": reference_object_id}])
            return input_candidates(store, project_id, reference_object_id or object_id, after, limit)

    @router.post("/{rule_id}/series-publications", status_code=201)
    def publish_series(project_id: int, object_id: int, rule_id: str, body: SeriesPublicationRequest, request: Request):
        from app.rule_series import publish
        from app.time_series_canonical import CanonicalRevisionError
        user, _ = context(request, project_id, object_id)
        repository.get(rule_id, project_id, object_id)
        key = request.headers.get("Idempotency-Key", "").strip()
        if not key or len(key) > 200:
            raise HTTPException(422, "Se requiere una clave idempotente de hasta 200 caracteres")
        try:
            return publish(repository, rule_id, project_id, object_id, body, user, key)
        except CanonicalRevisionError as error:
            raise HTTPException(409 if "IDEMPOTENCY" in error.code else 422, error.as_problem()) from error

    @router.get("/{rule_id}/tests/{job_id}/series-options")
    def get_series_options(project_id: int, object_id: int, rule_id: str, job_id: str, request: Request):
        from app.rule_series import options
        context(request, project_id, object_id)
        with store._lock:
            return options(repository, rule_id, project_id, object_id, job_id)

    @router.get("/{rule_id}/series-publications")
    def list_series(project_id: int, object_id: int, rule_id: str, request: Request):
        from app.rule_series import read
        context(request, project_id, object_id)
        repository.get(rule_id, project_id, object_id)
        with store._lock:
            rows = store.connection.execute("SELECT id FROM component_rule_series WHERE rule_id = ? ORDER BY id", (rule_id,)).fetchall()
            return {"items": [read(repository, rule_id, row["id"]) for row in rows]}

    @router.get("/{rule_id}/series-publications/{series_id}")
    def get_series(project_id: int, object_id: int, rule_id: str, series_id: str, request: Request):
        from app.rule_series import read
        context(request, project_id, object_id)
        repository.get(rule_id, project_id, object_id)
        with store._lock:
            return read(repository, rule_id, series_id)

    @router.post("/{rule_id}/series-publications/{series_id}/regenerations", status_code=201)
    def regenerate_series(project_id: int, object_id: int, rule_id: str, series_id: str,
                          body: SeriesRegenerationRequest, request: Request):
        from app.rule_series import publish, read
        from app.time_series_canonical import CanonicalRevisionError
        user, _ = context(request, project_id, object_id)
        repository.get(rule_id, project_id, object_id)
        key = request.headers.get("Idempotency-Key", "").strip()
        if not key or len(key) > 200:
            raise HTTPException(422, "Se requiere una clave idempotente de hasta 200 caracteres")
        with store._lock:
            previous = read(repository, rule_id, series_id)
        definition = SeriesPublicationRequest(**{**previous["definition"], "job_id": body.job_id, "reason": body.reason})
        try:
            return publish(repository, rule_id, project_id, object_id, definition, user, key,
                           regeneration={"id": series_id, "expected_revision_id": body.expected_revision_id})
        except CanonicalRevisionError as error:
            raise HTTPException(409 if "IDEMPOTENCY" in error.code else 422, error.as_problem()) from error

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
        return repository.enqueue(rule_id, project_id, object_id, body.expected_revision, user["id"], obj,
                                  publication_id=body.publication_id, scope=body.scope.model_dump() if body.scope else None)

    @router.post("/{rule_id}/applications", status_code=201)
    def apply_rule(project_id: int, object_id: int, rule_id: str, body: RuleApplyRequest, request: Request):
        from app.rule_applications import apply
        user, _ = context(request, project_id, object_id)
        return apply(repository, rule_id, project_id, object_id, body, user["id"])

    @router.get("/{rule_id}/applications")
    def get_applications(project_id: int, object_id: int, rule_id: str, request: Request):
        from app.rule_applications import list_applications
        context(request, project_id, object_id)
        repository.get(rule_id, project_id, object_id)
        return {"items": list_applications(repository, rule_id)}

    @router.post("/{rule_id}/applications/{application_id}/deactivate")
    def deactivate_rule(project_id: int, object_id: int, rule_id: str, application_id: str, body: RuleDeactivateRequest, request: Request):
        from app.rule_applications import deactivate
        user, _ = context(request, project_id, object_id)
        repository.get(rule_id, project_id, object_id)
        return deactivate(repository, rule_id, application_id, body, user["id"])

    @router.post("/{rule_id}/publications", status_code=201)
    def publish_rule(project_id: int, object_id: int, rule_id: str, body: RuleTestRequest, request: Request):
        user, _ = context(request, project_id, object_id)
        return repository.publish(rule_id, project_id, object_id, body.expected_revision, user["id"])

    @router.get("/{rule_id}/publications/{publication_id}")
    def get_publication(project_id: int, object_id: int, rule_id: str, publication_id: str, request: Request):
        context(request, project_id, object_id)
        repository.get(rule_id, project_id, object_id)
        return repository.publication(rule_id, publication_id)

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
