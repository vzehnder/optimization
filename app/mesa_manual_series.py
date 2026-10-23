"""Manual support in the mesa, backed by canonical object series, never visual data."""

from contextlib import contextmanager
import json
import uuid
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.mesa_editing import MesaEditConflict, MesaEditPoint
from app.object_time_series import ObjectSeriesError, object_series_etag, object_series_problem
from app.optimization_mesa import MesaSeries, _canonical_time, _cover_series
from app.time_series_bindings import BindingMutationError


class MesaManualContext(BaseModel):
    model_config = ConfigDict(extra="forbid")
    case_id: int = Field(gt=0)
    variant_id: int = Field(gt=0)


class MesaManualCreate(MesaManualContext):
    object_id: int = Field(gt=0)
    name: str = Field(min_length=1, max_length=120)
    binding_role_key: str
    semantic_type_key: str
    unit_key: str
    timezone: str
    resolution_seconds: int = Field(gt=0)
    points: list[MesaEditPoint] = Field(min_length=1, max_length=10000)
    confirm: bool = False
    reason: str = Field(min_length=1, max_length=1000)

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value):
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as error:
            raise ValueError("Selecciona una zona horaria IANA válida.") from error
        return value


class MesaManualReceipt(BaseModel):
    signal_id: int
    revision_id: int
    preparation_status: str


class MesaManualOption(BaseModel):
    object_id: int
    object_name: str
    binding_role_key: str
    semantic_type_key: str
    unit_key: str
    unit: str
    name: str


class MesaManualOptions(BaseModel):
    items: list[MesaManualOption]


def manual_options(store, *, scenario_id, case_id, variant_id):
    from app.optimization_mesa import read_mesa
    project_id = case_context(store, scenario_id, case_id, variant_id)
    mesa = read_mesa(store, scenario_id=scenario_id, case_id=case_id, variant_id=variant_id)
    objects = {o["id"]: o for o in store.list_linkable_objects(project_id=project_id)}
    catalog = store.get_time_series_classification_catalog()
    types = {s["id"]: s for s in catalog["time_series_semantic_types"] if s["status"] == "active"}
    roles = {r["id"]: r for r in catalog["time_series_binding_roles"] if r["status"] == "active"}
    units = {u["id"]: u for u in catalog["measurement_units"] if u["status"] == "active"}
    items = []
    for component in mesa["components"]:
        obj = objects.get(component["linkable_object_id"])
        if not obj or not component.get("is_active", True) or component["entity_type"] == "manual_series":
            continue
        for rule in catalog["time_series_role_compatibilities"]:
            semantic, role = types.get(rule["semantic_type_id"]), roles.get(rule["binding_role_id"])
            if (rule["object_type_id"] != obj["object_type_id"] or rule["status"] != "active"
                    or not rule["association_allowed"] or not semantic or not role):
                continue
            unit = units.get(semantic["canonical_unit_id"])
            if unit:
                items.append(dict(object_id=obj["id"], object_name=f"{component['name']} · {component['entity_id']}",
                    binding_role_key=role["role_key"], semantic_type_key=semantic["semantic_key"],
                    unit_key=unit["unit_key"], unit=unit["symbol"], name=f"{role['display_name']} · {unit['symbol']}"))
    return {"items": items}


class MesaManualExpected(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision_id: int
    content_hash: str
    resource_version: int
    bindings_revision: int


class MesaManualDestination(BaseModel):
    object_id: int
    name: str
    binding_role_key: str
    current_signal_id: int | None = None
    current_revision_id: int | None = None


class MesaManualDetail(BaseModel):
    object_id: int
    series: MesaSeries
    expected: MesaManualExpected
    destinations: list[MesaManualDestination]
    scope_message: str


class MesaManualBinding(MesaManualContext):
    expected: MesaManualExpected
    object_id: int
    binding_role_key: str
    confirm: bool = False
    reason: str = Field(min_length=1, max_length=1000)


class MesaManualRevision(MesaManualContext):
    expected: MesaManualExpected
    unit: str
    points: list[MesaEditPoint] = Field(min_length=1, max_length=10000)
    confirm: bool = False
    reason: str = Field(min_length=1, max_length=1000)


def revise_manual(store, *, scenario_id, signal_id, payload, actor):
    detail = manual_detail(store, scenario_id=scenario_id, case_id=payload.case_id,
                           variant_id=payload.variant_id, signal_id=signal_id)
    if payload.expected.model_dump() != detail["expected"]:
        raise MesaEditConflict("La serie o sus vínculos cambiaron. Recarga y compara antes de publicar.")
    if not payload.confirm or not payload.reason.strip():
        raise ValueError("Confirma el alcance de la revisión e indica un motivo.")
    if payload.unit != detail["series"]["unit"]:
        raise ValueError("Conserva la unidad de la serie; no se convierten valores implícitamente.")
    if [(p.start, p.end) for p in payload.points] != [(p["start"], p["end"]) for p in detail["series"]["points"]]:
        raise ValueError("La edición debe conservar todos los intervalos de la revisión.")
    project_id = case_context(store, scenario_id, payload.case_id, payload.variant_id)
    local = store.read_object_series(project_id=project_id, linkable_object_id=detail["object_id"], signal_id=signal_id)
    publication = publish_points(store, project_id=project_id, object_id=detail["object_id"], local=local,
        points=payload.points, actor=actor, reason=payload.reason)
    return dict(signal_id=signal_id, revision_id=publication["revision_id"], preparation_status="pending_validation")


def manual_detail(store, *, scenario_id, case_id, variant_id, signal_id):
    from app.optimization_mesa import read_mesa
    project_id = case_context(store, scenario_id, case_id, variant_id)
    mesa = read_mesa(store, scenario_id=scenario_id, case_id=case_id, variant_id=variant_id)
    component = next((c for c in mesa["components"] if c["entity_type"] == "manual_series"
                      and c["series"]["signal_id"] == signal_id), None)
    if component is None:
        raise KeyError("La serie manual no pertenece a este caso o ya no está disponible.")
    object_id = component["linkable_object_id"]
    local = store.read_object_series(project_id=project_id, linkable_object_id=object_id, signal_id=signal_id)
    bindings = store.read_case_bindings(scenario_id=scenario_id, variant_id=variant_id)
    preparation = store.read_input_variant_preparation(scenario_id=scenario_id, variant_id=variant_id)
    role_catalog = store.get_time_series_classification_catalog()["time_series_binding_roles"]
    required_keys = {r["signal_key"] for r in preparation["required_signals"] if r["linkable_object_id"] == object_id}
    required_roles = {r["role_key"] for r in role_catalog if r["status"] == "active"
                      and r["execution_allowed"] and r["execution_contract_key"] in required_keys}
    versioned_network = preparation["model_contract"] == "bess_system_dispatch.v3"
    if versioned_network:
        required_roles = set()
    destinations = []
    for role in local["compatible_role_keys"]:
        if role not in required_roles:
            continue
        current = next((b for b in bindings["items"] if b["status"] == "active"
                        and b["object"]["id"] == object_id and b["binding_role"]["key"] == role), None)
        destinations.append(dict(object_id=object_id, name=f"{component['parent_entity_id']} · {role}",
            binding_role_key=role, current_signal_id=current["signal"]["id"] if current else None,
            current_revision_id=current["set_revision_id"] if current else None))
    impact = store.read_object_series_binding_impact(project_id=project_id, linkable_object_id=object_id, signal_id=signal_id)
    return dict(object_id=object_id, series=component["series"],
        expected=dict(revision_id=local["current_revision"]["revision_id"], content_hash=local["current_revision"]["content_hash"],
            resource_version=local["resource_version"], bindings_revision=bindings["meta"]["bindings_revision"]),
        destinations=destinations,
        scope_message=("La red v3 se prepara desde una versión promovida. Esta serie es de apoyo en la mesa; "
                       "para cambiar la ejecución usa el editor hidráulico y promueve otra versión. " if versioned_network else "") +
                      f"Publicar una revisión dejará {impact['will_become_stale']} vínculos pendientes de revalidación. "
                      "Vincular reemplaza únicamente una entrada admitida de esta variante. Los runs existentes se conservan.")


def bind_manual(store, *, scenario_id, signal_id, payload, actor_user):
    detail = manual_detail(store, scenario_id=scenario_id, case_id=payload.case_id,
                           variant_id=payload.variant_id, signal_id=signal_id)
    if payload.expected.model_dump() != detail["expected"]:
        raise MesaEditConflict("La serie o los vínculos cambiaron. Recarga y revisa antes de vincular.")
    if not payload.confirm or not payload.reason.strip():
        raise ValueError("Confirma el reemplazo de la entrada e indica un motivo.")
    if not any(d["object_id"] == payload.object_id and d["binding_role_key"] == payload.binding_role_key
               for d in detail["destinations"]):
        raise ValueError("Destino incompatible: elige una señal admitida del objeto propietario en este caso.")
    collection = store.read_case_bindings(scenario_id=scenario_id, variant_id=payload.variant_id)
    current = next((b for b in collection["items"] if b["status"] == "active" and b["object"]["id"] == payload.object_id
                    and b["binding_role"]["key"] == payload.binding_role_key), None)
    operation = dict(client_operation_id="manual-binding", action="replace" if current else "create",
        linkable_object_id=payload.object_id, binding_role_key=payload.binding_role_key, signal_id=signal_id,
        revision=dict(mode="current", revision_id=payload.expected.revision_id, content_hash=payload.expected.content_hash),
        catalog_association_id=None, reason_code="variant_input_selected", reason_text=payload.reason)
    if current:
        operation.update(binding_id=current["binding_id"], expected_lifecycle_revision=current["lifecycle_revision"])
    document = dict(expected_bindings_revision=payload.expected.bindings_revision, operations=[operation])
    preview = store.prevalidate_case_binding_batch(scenario_id=scenario_id, variant_id=payload.variant_id,
                                                   document=document, actor_class="internal")
    key = f"mesa-manual-{uuid.uuid4().hex}"
    store.commit_case_binding_batch(scenario_id=scenario_id, variant_id=payload.variant_id, document=document,
        actor_user=actor_user, actor_class="internal", request_id=key, prevalidation_token=preview["prevalidation_token"],
        if_match=preview["commit_etag"], idempotency_key=key, confirmed=True)
    return dict(signal_id=signal_id, revision_id=payload.expected.revision_id, preparation_status="pending_validation")


def manual_reference(case_id):
    return f"mesa-manual:case:{case_id}"


def case_context(store, scenario_id, case_id, variant_id):
    scenario = store.get_scenario(scenario_id)
    case = store.get_or_create_case_for_scenario(scenario_id)
    if case["id"] != case_id:
        raise KeyError("El caso no pertenece al escenario.")
    store.get_case_input_variant_for_case(case_id, variant_id)
    return scenario["project_id"]


@contextmanager
def manual_transaction(store, scenario_id, variant_id):
    with store._lock, store._run_materialization_transaction():
        previous = getattr(store, "_mesa_transaction_active", False)
        store._mesa_transaction_active = True
        try:
            collection = store.read_case_bindings(scenario_id=scenario_id, variant_id=variant_id)
            store._lock_case_binding_batch(variant_id=variant_id, normalized={"operations": [
                {"binding_id": b["binding_id"], "linkable_object_id": b["object"]["id"]}
                for b in collection["items"] if b["status"] == "active"]})
            yield
        finally:
            store._mesa_transaction_active = previous


def publish_points(store, *, project_id, object_id, local, points, actor, reason):
    descriptor = next(s for s in store.get_time_series_classification_catalog()["time_series_semantic_types"]
                      if s["semantic_key"] == local["classification"]["semantic_type_key"])
    rules = json.loads(descriptor["validation_rules_json"])
    for index, point in enumerate(points, start=1):
        if (("minimum" in rules and point.value < rules["minimum"])
                or ("maximum" in rules and point.value > rules["maximum"])):
            raise ObjectSeriesError("TS_INGEST_VALIDATION_FAILED",
                detail=f"Valor inválido en intervalo {index}: respeta los límites de la señal {rules}.")
    root = dict(project_id=project_id, linkable_object_id=object_id, signal_id=local["signal_id"])
    ingestion = store.prepare_object_series_points_ingestion(**root, actor=actor, document={
        "mode": "replace_full", "expected_base": local["current_revision"],
        "source": {"kind": "api", "display_name": "Serie manual en mesa",
                   "external_reference": local["metadata"]["external_reference"]},
        "points": [{"timestamp_start": p.start, "timestamp_end": p.end,
                    "values": {local["object_series_key"]: p.value}} for p in points],
    })
    publication, _ = store.publish_object_series_ingestion(**root, actor=actor,
        ingestion_key=ingestion["ingestion_id"], validation_token=ingestion["validation_token"],
        confirm=True, reason_code="mesa_manual_published", reason_text=reason,
        if_match=object_series_etag(signal_id=local["signal_id"], resource_version=local["resource_version"]),
        idempotency_key=f"mesa-manual-{ingestion['ingestion_id']}")
    return publication


def create_manual(store, *, scenario_id, payload, actor):
    from app.optimization_mesa import read_mesa
    project_id = case_context(store, scenario_id, payload.case_id, payload.variant_id)
    mesa = read_mesa(store, scenario_id=scenario_id, case_id=payload.case_id, variant_id=payload.variant_id)
    if not any(c["linkable_object_id"] == payload.object_id and c.get("is_active", True)
               and c["entity_type"] != "manual_series" for c in mesa["components"]):
        raise KeyError("El objeto no está activo en este caso.")
    if not payload.confirm or not payload.reason.strip() or not payload.name.strip():
        raise ValueError("Indica nombre, motivo y confirma la publicación como apoyo.")
    local = store.create_object_series_definition(project_id=project_id, linkable_object_id=payload.object_id,
        actor=actor, document={
            "object_series_key": f"manual_{uuid.uuid4().hex}", "display_name": payload.name.strip(),
            "intended_binding_role_key": payload.binding_role_key, "semantic_type_key": payload.semantic_type_key,
            "unit_key": payload.unit_key, "data_class_key": "forecast", "timezone": payload.timezone,
            "temporal_contract": {"regularity": "regular", "nominal_resolution_seconds": payload.resolution_seconds,
                                  "timestamp_convention": "period_start"},
            "source_expectation": {"kind": "manual", "display_name": "Serie manual en mesa"},
            "metadata": {"external_reference": manual_reference(payload.case_id)},
        })
    publication = publish_points(store, project_id=project_id, object_id=payload.object_id, local=local,
                                 points=payload.points, actor=actor, reason=payload.reason)
    return {"signal_id": local["signal_id"], "revision_id": publication["revision_id"],
            "preparation_status": "unchanged"}


def read_manual_components(store, *, project_id, case_id, components, bindings, range_start, range_end):
    result = []
    units = {u["unit_key"]: u["symbol"] for u in store.get_time_series_classification_catalog()["measurement_units"]}
    seen = set()
    for component in components:
        object_id = component["linkable_object_id"]
        if not object_id or object_id in seen or not component.get("is_active", True):
            continue
        seen.add(object_id)
        cursor = None
        while True:
            page = store.read_object_time_series_context(project_id=project_id, linkable_object_id=object_id,
                filters={"kind": "object_specific"}, limit=100, cursor=cursor)
            for item in page["items"]:
                if item["source_kind"] != "object_specific":
                    continue
                local = store.read_object_series(project_id=project_id, linkable_object_id=object_id, signal_id=item["signal_id"])
                if (local["metadata"].get("external_reference") != manual_reference(case_id)
                        or local["availability"] != "ready"):
                    continue
                revision = store.read_canonical_revision(local["current_revision"]["revision_id"])
                bound = next((b for b in bindings if b["status"] == "active" and b["signal"]["id"] == local["signal_id"]
                              and b["object"]["id"] == object_id), None)
                series = dict(signal_key=local["object_series_key"], name=local["display_name"],
                    role="support", unit=units[local["classification"]["unit_key"]], editable=False,
                    status="available", source="manual", timezone=revision["timezone"],
                    revision_id=revision["id"], revision_number=revision["revision_number"],
                    content_hash=revision["content_hash"], time_series_set_id=local["set_id"], signal_id=local["signal_id"],
                    binding_state=bound["state"] if bound else "unbound",
                    message="Serie de apoyo. No participa en esta simulación." if not bound else
                            "Serie manual vinculada; consulta la entrada del objeto para ver la revisión usada por la preparación.",
                    points=[{"start": _canonical_time(p["timestamp_start"], revision["timezone"]),
                             "end": _canonical_time(p["timestamp_end"], revision["timezone"]), "value": value}
                            for p, value in zip(revision["periods"], revision["values"][local["object_series_key"]])])
                result.append(dict(linkable_object_id=object_id, entity_id=str(local["signal_id"]),
                    entity_type="manual_series", name=local["display_name"], parent_entity_id=component["entity_id"],
                    series=_cover_series(series, range_start, range_end)))
            if not page["page"]["has_more"]:
                break
            cursor = page["page"]["next_cursor"]
    return result


def register_mesa_manual_routes(app, store):
    def refuse(error):
        if isinstance(error, MesaEditConflict):
            raise HTTPException(409, str(error)) from error
        if isinstance(error, BindingMutationError):
            raise HTTPException(409, error.message) from error
        if isinstance(error, ObjectSeriesError):
            return JSONResponse(object_series_problem(error, request_id=f"req_{uuid.uuid4().hex}"),
                                status_code=error.status, media_type="application/problem+json")
        raise HTTPException(404 if isinstance(error, KeyError) else 400, str(error)) from error

    @app.get("/api/scenarios/{scenario_id}/mesa/manual-series", response_model=MesaManualOptions)
    async def get_options(scenario_id: int, case_id: int, variant_id: int):
        try:
            with store._lock:
                return manual_options(store, scenario_id=scenario_id, case_id=case_id, variant_id=variant_id)
        except (KeyError, ValueError, ObjectSeriesError) as error:
            return refuse(error)

    @app.get("/api/scenarios/{scenario_id}/mesa/manual-series/{signal_id}", response_model=MesaManualDetail)
    async def get_manual(scenario_id: int, signal_id: int, case_id: int, variant_id: int):
        try:
            with store._lock:
                return manual_detail(store, scenario_id=scenario_id, case_id=case_id, variant_id=variant_id, signal_id=signal_id)
        except (KeyError, ValueError, ObjectSeriesError) as error:
            return refuse(error)

    @app.post("/api/scenarios/{scenario_id}/mesa/manual-series/{signal_id}/binding", status_code=201, response_model=MesaManualReceipt)
    async def post_binding(request: Request, scenario_id: int, signal_id: int, payload: MesaManualBinding):
        try:
            with manual_transaction(store, scenario_id, payload.variant_id):
                return bind_manual(store, scenario_id=scenario_id, signal_id=signal_id, payload=payload,
                    actor_user=request.state.current_user or {"id": None, "email": "auth-disabled", "role": "analyst"})
        except (KeyError, ValueError, ObjectSeriesError, BindingMutationError) as error:
            return refuse(error)

    @app.post("/api/scenarios/{scenario_id}/mesa/manual-series/{signal_id}/revisions", status_code=201, response_model=MesaManualReceipt)
    async def post_revision(request: Request, scenario_id: int, signal_id: int, payload: MesaManualRevision):
        try:
            with manual_transaction(store, scenario_id, payload.variant_id):
                return revise_manual(store, scenario_id=scenario_id, signal_id=signal_id, payload=payload,
                    actor=(request.state.current_user or {"email": "auth-disabled"})["email"])
        except (KeyError, ValueError, ObjectSeriesError, BindingMutationError) as error:
            return refuse(error)

    @app.post("/api/scenarios/{scenario_id}/mesa/manual-series", status_code=201, response_model=MesaManualReceipt)
    async def post_manual(request: Request, scenario_id: int, payload: MesaManualCreate):
        try:
            with manual_transaction(store, scenario_id, payload.variant_id):
                return create_manual(store, scenario_id=scenario_id, payload=payload,
                    actor=(request.state.current_user or {"email": "auth-disabled"})["email"])
        except MesaEditConflict as error:
            raise HTTPException(409, str(error)) from error
        except ObjectSeriesError as error:
            return JSONResponse(object_series_problem(error, request_id=f"req_{uuid.uuid4().hex}"),
                                status_code=error.status, media_type="application/problem+json")
        except KeyError as error:
            raise HTTPException(404, str(error)) from error
        except ValueError as error:
            raise HTTPException(400, str(error)) from error
