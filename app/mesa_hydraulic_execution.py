"""Hydraulic mesa execution from an explicit immutable v3 source version."""

import json
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from app.hydraulic_simulation import HydraulicSimulationRequest, prepare_hydraulic_simulation
from app.mesa_execution import digest
from app.run_progress import read_run_progress


class MesaHydraulicRequest(HydraulicSimulationRequest):
    model_config = ConfigDict(extra="forbid")
    case_id: int = Field(gt=0)
    source_scenario_version_id: int = Field(gt=0)


class MesaHydraulicRunRequest(MesaHydraulicRequest):
    expected_preparation_hash: str = Field(min_length=64, max_length=64)
    idempotency_key: str = Field(min_length=1, max_length=160)


class MesaHydraulicComponent(BaseModel):
    entity_id: str
    component_type: str
    name: str


class MesaHydraulicSource(BaseModel):
    id: int
    version_number: int
    range_start: str
    range_end: str
    resolution_hours: float
    terminal_water_values_usd_per_hm3: dict[str, float]
    mip_rel_gap: float
    components: list[MesaHydraulicComponent]


class MesaHydraulicSources(BaseModel):
    sources: list[MesaHydraulicSource]


def describe_source(source):
    document = source["system_case_json"]
    network = document["hydraulic_network"]
    periods = document["time_series"]
    def instant(value):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return (parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)).astimezone(timezone.utc)
    return {"id": source["id"], "version_number": source["version_number"],
        "range_start": instant(periods[0]["timestamp"]).isoformat() if periods else "",
        "range_end": (instant(periods[-1]["timestamp"]) + timedelta(hours=periods[-1]["duration_hours"])).isoformat() if periods else "",
        "resolution_hours": periods[0]["duration_hours"] if periods else 1,
        "terminal_water_values_usd_per_hm3": {n["id"]: n["reservoir"].get("terminal_water_value_usd_per_hm3", 0)
            for n in network["nodes"] if n["type"] == "reservoir"},
        "mip_rel_gap": document.get("solver", {}).get("options", {}).get("mip_rel_gap", 0.0001),
        "components": [{"entity_id": n["id"], "name": n.get("name", n["id"]),
            "component_type": n["type"] if collection == "nodes" else kind}
            for collection, kind in (("nodes", "node"), ("plants", "plant"), ("units", "unit"), ("reaches", "reach"))
            for n in network.get(collection, [])]}


def case_context(store, scenario_id, case_id):
    if store.get_or_create_case_for_scenario(scenario_id)["id"] != case_id:
        raise HTTPException(404, "El caso no pertenece al escenario.")


def prepare(store, scenario_id, payload):
    case_context(store, scenario_id, payload.case_id)
    source = store.get_scenario_version(payload.source_scenario_version_id)
    if source["scenario_id"] != scenario_id:
        raise HTTPException(404, "La versión fuente no pertenece al escenario.")
    source, document, metadata, fingerprint = prepare_hydraulic_simulation(store, source["id"], payload)
    metadata["mesa_hydraulic_execution"] = payload.model_dump(exclude={"expected_preparation_hash", "idempotency_key"})
    preview = {"preparation_hash": fingerprint, "period_count": len(document["time_series"]),
        "preview_periods": document["time_series"][:12], "generation_metadata": metadata}
    return document, metadata, preview


def replay(store, scenario_id, payload, actor):
    case_context(store, scenario_id, payload.case_id)
    for run in store.list_scenario_runs(scenario_id):
        receipt = run.get("materialized_lineage", {}).get("mesa_hydraulic_request", {})
        if receipt.get("key") == payload.idempotency_key and receipt.get("actor_id") == actor.get("id"):
            if receipt["hash"] != digest(payload.model_dump()):
                raise HTTPException(409, "La clave de solicitud ya se usó con otra preparación. Vuelve a validar.")
            return run
    return None


def register_mesa_hydraulic_execution_routes(app, store, validation_service, queue, artifact_root):
    def translated(action):
        try:
            return action()
        except KeyError as error:
            raise HTTPException(404, str(error)) from error
        except (ValueError, OverflowError) as error:
            raise HTTPException(400, str(error)) from error

    def validated(document):
        result = validation_service.validate_text(json.dumps(document, allow_nan=False))
        if not result.ok:
            raise HTTPException(400, result.message)
        return result

    @app.get("/api/scenarios/{scenario_id}/mesa/hydraulic-execution/sources", response_model=MesaHydraulicSources)
    def sources(scenario_id: int, case_id: int):
        def read():
            with store._lock:
                case_context(store, scenario_id, case_id)
                return {"sources": [describe_source(store.get_scenario_version(v["id"]))
                    for v in reversed(store.list_scenario_versions(scenario_id))
                    if v["schema_version"] == "bess_system_dispatch.v3"]}
        return translated(read)

    @app.get("/api/scenarios/{scenario_id}/mesa/hydraulic-execution")
    def state(scenario_id: int, case_id: int):
        def read():
            with store._lock:
                case_context(store, scenario_id, case_id)
                run = next((r for r in store.list_scenario_runs(scenario_id)
                    if r.get("materialized_lineage", {}).get("mesa_hydraulic_execution", {}).get("case_id") == case_id), None)
            return {"run": {**run, "progress": read_run_progress(run, artifact_root)} if run else None}
        return translated(read)

    @app.post("/api/scenarios/{scenario_id}/mesa/hydraulic-execution/preview")
    def preview(scenario_id: int, payload: MesaHydraulicRequest):
        def read():
            with store._lock:
                document, _, result = prepare(store, scenario_id, payload)
            validated(document)
            return result
        return translated(read)

    @app.post("/api/scenarios/{scenario_id}/mesa/hydraulic-execution/runs", status_code=201)
    def launch(scenario_id: int, payload: MesaHydraulicRunRequest, request: Request):
        def execute():
            actor = getattr(request.state, "current_user", None) or {}
            with store._lock:
                existing = replay(store, scenario_id, payload, actor)
                if existing:
                    return existing
                document, metadata, preview = prepare(store, scenario_id, payload)
                if preview["preparation_hash"] != payload.expected_preparation_hash:
                    raise HTTPException(409, "La preparación cambió. Vuelve a validar antes de ejecutar.")
            validation = validated(document)
            with store._lock, store._run_materialization_transaction():
                if store.database_backend == "postgresql":
                    store.connection.execute("SELECT id FROM scenarios WHERE id = ? FOR UPDATE", (scenario_id,)).fetchone()
                existing = replay(store, scenario_id, payload, actor)
                if existing:
                    return existing
                if store.database_backend == "postgresql":
                    project_id = store.get_scenario(scenario_id)["project_id"]
                    store.connection.execute("SELECT id FROM time_series_sets WHERE project_id = ? ORDER BY id FOR UPDATE", (project_id,)).fetchall()
                _, _, current = prepare(store, scenario_id, payload)
                if current["preparation_hash"] != payload.expected_preparation_hash:
                    raise HTTPException(409, "La preparación cambió durante la validación. Vuelve a validar.")
                version = store.create_scenario_version(scenario_id=scenario_id, system_case_json=document,
                    validation_payload=validation.payload, generation_metadata=metadata,
                    created_by=actor.get("email", "internal_analyst"), commit=False)
                try:
                    layout = store.get_scenario_version_hydraulic_diagram_snapshot(payload.source_scenario_version_id)
                except KeyError:
                    layout = None
                if layout:
                    store.persist_scenario_version_hydraulic_diagram_snapshot(scenario_version_id=version["id"],
                        layout_snapshot=layout["layout_snapshot"], source_case_id=layout.get("source_case_id"),
                        created_by=actor.get("email", "internal_analyst"), commit=False)
                run = store.create_run(scenario_version_id=version["id"], triggered_by=actor.get("email", "internal_analyst"),
                    triggered_by_user_id=actor.get("id"), triggered_by_display_name=actor.get("display_name"),
                    materialized_lineage={**metadata, "preparation_hash": preview["preparation_hash"],
                        "mesa_hydraulic_request": {"key": payload.idempotency_key, "actor_id": actor.get("id"),
                            "hash": digest(payload.model_dump())}}, commit=False)
            queue.enqueue(run["id"])
            return run
        return translated(execute)
