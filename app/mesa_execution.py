"""Electrical mesa preparation over the existing variant, snapshot and worker chain."""

import hashlib
import json
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from app.run_progress import read_run_progress
from app.time_series_bindings import BindingMutationError
from app.variant_staleness import VariantStaleError


class MesaExecutionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    case_id: int = Field(gt=0)
    variant_id: int = Field(gt=0)
    range_start: str
    range_end: str
    timezone: str
    resolution_hours: float = Field(gt=0, allow_inf_nan=False)


class MesaExecutionRunRequest(MesaExecutionRequest):
    expected_preparation_hash: str = Field(min_length=64, max_length=64)
    idempotency_key: str = Field(min_length=1, max_length=160)


class MesaExecutionPreview(BaseModel):
    preparation_hash: str
    period_count: int
    range_start: str
    range_end: str
    timezone: str
    resolution_hours: float
    model_contract: str
    series_bindings: list[dict]


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def context(store, scenario_id, case_id, variant_id):
    case = store.get_or_create_case_for_scenario(scenario_id)
    if case["id"] != case_id:
        raise HTTPException(404, "El caso no pertenece al escenario.")
    return store.get_case_input_variant_for_case(case_id, variant_id)


def local_datetime(value, zone):
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is not None:
        return parsed.astimezone(zone)
    candidates = {candidate.utcoffset(): candidate for fold in (0, 1)
                  if (candidate := parsed.replace(tzinfo=zone, fold=fold)).astimezone(timezone.utc)
                  .astimezone(zone).replace(tzinfo=None) == parsed}
    if not candidates:
        raise ValueError(f"La hora {value} no existe en {zone.key} por el cambio de hora.")
    if len(candidates) != 1:
        raise ValueError(f"La hora {value} es ambigua en {zone.key}; indica un offset explícito.")
    return next(iter(candidates.values()))


def prepare(store, scenario_id, payload, *, revalidate_legacy=False):
    variant = context(store, scenario_id, payload.case_id, payload.variant_id)
    preparation = store.read_input_variant_preparation(scenario_id=scenario_id, variant_id=payload.variant_id)
    if preparation.get("model_contract") not in {"bess_system_dispatch.v1", "bess_system_dispatch.v2"}:
        raise ValueError("La ejecución eléctrica admite modelos v1/v2. Este caso requiere su preparación hidráulica o completar el modelo.")
    try:
        zone = ZoneInfo(payload.timezone)
    except (ZoneInfoNotFoundError, ValueError) as error:
        raise ValueError("Selecciona una zona horaria IANA válida.") from error
    start_dt, end_dt = local_datetime(payload.range_start, zone), local_datetime(payload.range_end, zone)
    if start_dt.astimezone(timezone.utc) >= end_dt.astimezone(timezone.utc):
        raise ValueError("El inicio debe ser anterior al fin exclusivo.")
    start, end = start_dt.isoformat(), end_dt.isoformat()
    from app.rule_applications import guard_uncompiled_run
    guard_uncompiled_run(store, variant_id=payload.variant_id)
    frozen = store.materialize_run_from_canonical_bindings(
        scenario_id=scenario_id, variant_id=payload.variant_id, range_start=start, range_end=end,
        validate_text=None, actor_user={}, request_id="mesa-preview", prepare_only=True,
    )
    if frozen is None:
        store.assert_case_bindings_executable(scenario_id=scenario_id, variant_id=payload.variant_id)
        if revalidate_legacy:
            materialized = store.validate_case_input_variant(scenario_id=scenario_id,
                case_input_variant_id=payload.variant_id, range_start=start, range_end=end)
        else:
            materialized = store.materialize_system_case_for_variant(scenario_id=scenario_id,
                case_input_variant_id=payload.variant_id, range_start=start, range_end=end, record_validation=False)
        frozen = {"system_case": materialized["system_case"], "generation_metadata": {
            "series_bindings": materialized["series_bindings"],
        }}
    metadata = {**frozen["generation_metadata"], "kind": "case_input_variant",
                "input_variant": {"id": payload.variant_id, "display_name": variant["display_name"]},
                "date_range": {"start": start, "end": end},
                "mesa_execution": MesaExecutionRequest(**payload.model_dump(include=set(MesaExecutionRequest.model_fields))).model_dump()}
    document = frozen["system_case"]
    scenario = store.get_scenario(scenario_id)
    for source in metadata["series_bindings"]:
        source_zone = (store.read_canonical_revision(source["set_revision_id"], with_values=False)["timezone"]
                       if source.get("set_revision_id") else
                       store.get_time_series_set(scenario["project_id"], source["time_series_set_id"])["timezone"])
        source["timezone"] = source_zone
        if source_zone != payload.timezone:
            raise ValueError(f"La zona de las entradas es {source_zone}. Usa esa zona; no se reinterpretan las horas del modelo.")
    if any(p["duration_hours"] != payload.resolution_hours for p in document["time_series"]):
        raise ValueError("La resolución debe coincidir con cada intervalo de entrada; no se aplica remuestreo.")
    fingerprint = digest({"document": document, "metadata": metadata})
    preview = {"preparation_hash": fingerprint, "period_count": len(document["time_series"]),
               "range_start": start, "range_end": end, "timezone": payload.timezone,
               "resolution_hours": payload.resolution_hours, "model_contract": document["schema_version"],
               "series_bindings": metadata["series_bindings"]}
    return document, metadata, preview


def latest_run(store, scenario_id, variant_id):
    for run in store.list_scenario_runs(scenario_id):
        execution = run.get("materialized_lineage", {}).get("mesa_execution", {})
        if execution.get("variant_id") == variant_id:
            return run
    return None


def replay_run(store, scenario_id, payload, actor):
    context(store, scenario_id, payload.case_id, payload.variant_id)
    for run in store.list_scenario_runs(scenario_id):
        receipt = run.get("materialized_lineage", {}).get("mesa_request", {})
        if (receipt.get("key") == payload.idempotency_key and receipt.get("actor_id") == actor["id"]
                and receipt.get("variant_id") == payload.variant_id):
            if receipt["hash"] != digest(payload.model_dump()):
                raise HTTPException(409, "La clave de solicitud ya se usó con otra preparación. Vuelve a validar.")
            return run
    return None


def register_mesa_execution_routes(app, store, validation_service, queue, artifact_root):
    def translated(action):
        try:
            return action()
        except KeyError as error:
            raise HTTPException(404, str(error)) from error
        except (BindingMutationError, VariantStaleError) as error:
            raise HTTPException(409, f"La preparación cambió o tiene vínculos inválidos: {error}. Revisa Datos y vuelve a validar.") from error
        except ValueError as error:
            raise HTTPException(400, str(error)) from error

    def validated(document):
        result = validation_service.validate_text(json.dumps(document, sort_keys=True))
        if not result.ok:
            raise HTTPException(400, result.message)
        return result

    @app.get("/api/scenarios/{scenario_id}/mesa/execution")
    def execution_state(scenario_id: int, case_id: int, variant_id: int):
        def read():
            with store._lock:
                context(store, scenario_id, case_id, variant_id)
                run = latest_run(store, scenario_id, variant_id)
            return {"run": {**run, "progress": read_run_progress(run, artifact_root)} if run else None}
        return translated(read)

    @app.post("/api/scenarios/{scenario_id}/mesa/execution/preview", response_model=MesaExecutionPreview)
    def execution_preview(scenario_id: int, payload: MesaExecutionRequest):
        def preview():
            with store._lock:
                document, _, result = prepare(store, scenario_id, payload, revalidate_legacy=True)
            validated(document)
            return result
        return translated(preview)

    @app.post("/api/scenarios/{scenario_id}/mesa/execution/runs", status_code=201)
    def execution_run(scenario_id: int, payload: MesaExecutionRunRequest, request: Request):
        def launch():
            actor = getattr(request.state, "current_user", None) or {"id": None, "email": "internal_analyst", "display_name": "Internal analyst"}
            with store._lock:
                existing = replay_run(store, scenario_id, payload, actor)
                if existing:
                    return existing
                document, metadata, preview = prepare(store, scenario_id, payload)
                if preview["preparation_hash"] != payload.expected_preparation_hash:
                    raise HTTPException(409, "La preparación cambió. Vuelve a validar antes de ejecutar.")
            result = validated(document)
            with store._lock, store._run_materialization_transaction():
                store._lock_canonical_run_inputs(variant_id=payload.variant_id)
                existing = replay_run(store, scenario_id, payload, actor)
                if existing:
                    return existing
                _, _, current = prepare(store, scenario_id, payload)
                if current["preparation_hash"] != payload.expected_preparation_hash:
                    raise HTTPException(409, "La preparación cambió durante la validación. Vuelve a validar.")
                version = store.create_scenario_version(scenario_id=scenario_id, system_case_json=document,
                    validation_payload=result.payload, generation_metadata=metadata, created_by=actor["email"], commit=False)
                run = store.create_run(scenario_version_id=version["id"], triggered_by=actor["email"],
                    triggered_by_user_id=actor["id"], triggered_by_display_name=actor["display_name"],
                    materialized_lineage={**metadata, "preparation_hash": preview["preparation_hash"],
                        "mesa_request": {"key": payload.idempotency_key, "hash": digest(payload.model_dump()),
                                         "actor_id": actor["id"], "variant_id": payload.variant_id}}, commit=False)
            queue.enqueue(run["id"])
            return run
        return translated(launch)
