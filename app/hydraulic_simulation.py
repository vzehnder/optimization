"""Prepare immutable hydraulic versions for an explicitly selected run horizon."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
from typing import Annotated, Literal

from fastapi import File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field

from app.time_series_catalog import CatalogImportRequest, CatalogSignalMappingRequest, prepare_time_series_catalog_import
from app.time_series_ingestion import ingest_time_series_source, read_time_series_source_rows
from app.time_series_migration import MigrationControlError


class HydraulicSimulationRequest(BaseModel):
    range_start: str
    range_end: str
    resolution_hours: float = Field(gt=0, allow_inf_nan=False)
    objective: Literal["market_value", "energy"] = "market_value"
    price_time_series_set_id: int | None = None
    price_signal_key: Literal["price_usd_per_mwh", "export_price_usd_per_mwh"] = "price_usd_per_mwh"
    terminal_water_values_usd_per_hm3: dict[str, Annotated[float, Field(ge=0, allow_inf_nan=False)]] = Field(default_factory=dict)
    mip_rel_gap: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    expected_preparation_hash: str | None = None


def _instant(value: str) -> datetime:
    value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    # Historical v3 documents used naive timestamps. Their run clock is UTC.
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _hash(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


def _resample(rows, start, end, step, *, maximum=False):
    """Integrate piecewise constant values over each target interval (O(n+m))."""
    intervals = []
    for row in rows:
        left = _instant(row["timestamp"])
        duration = float(row["duration_hours"])
        if not math.isfinite(duration) or duration <= 0:
            raise ValueError("Las duraciones de las fuentes deben ser positivas y finitas.")
        right = left + timedelta(hours=duration)
        if left < end and right > start:
            intervals.append((left, right, row["value"]))
    intervals.sort(key=lambda item: item[0])
    if not intervals or intervals[0][0] > start or intervals[-1][1] < end:
        raise ValueError("La fuente no cubre todo el período solicitado.")
    for previous, current in zip(intervals, intervals[1:]):
        if previous[1] != current[0]:
            raise ValueError("La fuente contiene huecos o períodos superpuestos.")
    result, index, cursor = [], 0, start
    while cursor < end:
        stop = cursor + step
        total, peak, covered = 0.0, -math.inf, 0.0
        while index < len(intervals) and intervals[index][0] < stop:
            left, right, value = intervals[index]
            value = float(value)
            if not math.isfinite(value):
                raise ValueError("Todos los valores de las fuentes deben ser finitos.")
            overlap = (min(right, stop) - max(left, cursor)).total_seconds()
            total += value * overlap
            peak = max(peak, value)
            covered += overlap
            if right <= stop:
                index += 1
            else:
                break
        if not math.isclose(covered, step.total_seconds(), abs_tol=1e-6):
            raise ValueError("La fuente no cubre un intervalo de optimización completo.")
        result.append(peak if maximum else total / covered)
        cursor = stop
    return result


def prepare_hydraulic_simulation(store, version_id, payload):
    version = store.get_scenario_version(version_id)
    document = deepcopy(version["system_case_json"])
    if document.get("schema_version") != "bess_system_dispatch.v3":
        raise ValueError("Selecciona una versión de una red hidráulica v3.")
    reservoirs = {node["id"]: node["reservoir"] for node in document["hydraulic_network"]["nodes"]
                  if node["type"] == "reservoir"}
    unknown = payload.terminal_water_values_usd_per_hm3.keys() - reservoirs.keys()
    if unknown:
        raise ValueError(f"Los valores del agua deben corresponder a embalses de la red: {', '.join(sorted(unknown))}.")
    for reservoir_id, value in payload.terminal_water_values_usd_per_hm3.items():
        reservoirs[reservoir_id]["terminal_water_value_usd_per_hm3"] = value
    water_values = {key: float(params.get("terminal_water_value_usd_per_hm3", 0.0)) for key, params in reservoirs.items()}
    if any(not math.isfinite(value) or value < 0 for value in water_values.values()):
        raise ValueError("Los valores del agua deben ser finitos y no negativos.")
    if payload.objective == "energy" and any(value > 0 for value in water_values.values()):
        raise ValueError("Para usar un valor del agua en USD/hm³ selecciona el objetivo de ingresos con CMg; para maximizar energía usa valores del agua iguales a cero.")
    solver_options = document.setdefault("solver", {"name": "HiGHS"}).setdefault("options", {})
    if payload.mip_rel_gap is not None:
        solver_options["mip_rel_gap"] = payload.mip_rel_gap
    relative_gap = float(solver_options.get("mip_rel_gap", 0.0001))
    if not math.isfinite(relative_gap) or relative_gap < 0:
        raise ValueError("El gap relativo debe ser finito y no negativo.")
    start, end = _instant(payload.range_start), _instant(payload.range_end)
    step = timedelta(hours=payload.resolution_hours)
    if step.total_seconds() <= 0 or end <= start:
        raise ValueError("El período y la resolución deben ser positivos.")
    count = (end - start) / step
    if not math.isclose(count, round(count), abs_tol=1e-8) or not 1 <= count <= 100000:
        raise ValueError("El período debe contener entre 1 y 100000 pasos completos de la resolución seleccionada.")
    source_periods = document["time_series"]
    periods = [{"timestamp": (start + i * step).isoformat(), "duration_hours": payload.resolution_hours,
                "natural_inflow_m3s": {}} for i in range(round(count))]
    # Validate coverage even if a network has no externally supplied inflows.
    _resample([{**row, "value": 0} for row in source_periods], start, end, step)
    for field in ("natural_inflow_m3s", "minimum_flow_m3s"):
        entity_ids = {key for row in source_periods for key in row.get(field, {})}
        for entity_id in sorted(entity_ids):
            try:
                rows = [{**row, "value": row[field][entity_id]} for row in source_periods]
            except KeyError as error:
                raise ValueError(f"Faltan valores de {field} para {entity_id}.") from error
            values = _resample(rows, start, end, step, maximum=field == "minimum_flow_m3s")
            for period, value in zip(periods, values):
                period.setdefault(field, {})[entity_id] = value
    metadata = {
        "kind": "hydraulic_simulation",
        "source_scenario_version_id": version_id,
        "source_version_number": version["version_number"],
        "source_content_hash": _hash(version["system_case_json"]),
        "date_range": {"start": start.isoformat(), "end": end.isoformat()},
        "hydraulic_simulation": {"objective": payload.objective, "resolution_hours": payload.resolution_hours,
                                 "terminal_water_values_usd_per_hm3": water_values, "mip_rel_gap": relative_gap,
                                 "resampling": "duration_weighted_mean; minimum_flow_max; finer_steps_constant"},
        "series_bindings": [],
    }
    if payload.objective == "market_value":
        if payload.price_time_series_set_id is None:
            raise ValueError("Selecciona una serie de CMg para la optimización económica.")
        scenario = store.get_scenario(version["scenario_id"])
        prices = store.get_time_series_set(scenario["project_id"], payload.price_time_series_set_id)
        if store.evaluate_time_series_set_staleness(scenario["project_id"], prices["id"])["stale"]:
            raise ValueError("La serie de CMg derivada está desactualizada. Regénérala desde sus fuentes antes de ejecutar.")
        values = {row["period_index"]: row["value_numeric"] for row in prices["values"]
                  if row["signal_key"] == payload.price_signal_key}
        try:
            price_rows = [{"timestamp": row["timestamp_start"], "duration_hours": row["duration_hours"],
                           "value": values[row["period_index"]]} for row in prices["periods"]]
        except KeyError as error:
            raise ValueError("Faltan valores en la serie de CMg seleccionada.") from error
        for period, value in zip(periods, _resample(price_rows, start, end, step)):
            period["price_usd_per_mwh"] = value
        metadata["series_bindings"].append({
            "signal_key": payload.price_signal_key, "entity_type": None, "entity_id": None,
            "time_series_set_id": prices["id"], "version_number": prices["version_number"],
            "version_label": prices["version_label"], "revision_number": prices["revision_number"],
            "content_hash": prices["content_hash"], "validated_range": metadata["date_range"],
        })
    document["time_series"] = periods
    document["hydraulic_objective"] = payload.objective
    preparation_hash = _hash({"system_case": document, "metadata": metadata})
    return version, document, metadata, preparation_hash


def register_hydraulic_simulation_routes(app, store, validation_service, enqueue_run, input_source_root):
    @app.get("/api/scenarios/{scenario_id}/hydraulic-simulation/prices")
    async def price_options(scenario_id: int):
        try:
            scenario = store.get_scenario(scenario_id)
            options = []
            for summary in store.list_time_series_sets(scenario["project_id"]):
                detail = store.get_time_series_set(scenario["project_id"], summary["id"])
                signals = [signal for signal in detail["signals"] if signal["signal_key"] in ("price_usd_per_mwh", "export_price_usd_per_mwh")]
                if signals:
                    options.append({**summary, "signals": signals, "horizon": detail["horizon"]})
            return {"time_series_sets": options}
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @app.post("/api/scenarios/{scenario_id}/hydraulic-simulation/prices", status_code=201)
    async def import_prices(scenario_id: int, request: Request, source_file: UploadFile = File(...),
                            set_name: str = Form(...), timezone_name: str = Form("UTC"),
                            data_kind: Literal["real", "forecast", "synthetic"] = Form("forecast")):
        try:
            scenario = store.get_scenario(scenario_id)
            source = ingest_time_series_source(draft_document={}, original_filename=source_file.filename or "cmg.csv",
                        content_type=source_file.content_type, content=await source_file.read(), input_source_root=input_source_root)
            _, rows = read_time_series_source_rows(source, input_source_root)
            prepared = prepare_time_series_catalog_import(rows=rows, request=CatalogImportRequest(
                set_name=set_name, version_label="import", data_kind=data_kind, timezone=timezone_name,
                timestamp_column="timestamp", duration_hours_column="duration_hours",
                signal_mappings=[CatalogSignalMappingRequest(source_column="price_usd_per_mwh", signal_key="price_usd_per_mwh")],
            ))
            for existing in store.list_time_series_sets(scenario["project_id"]):
                if existing["name"] == set_name and existing["content_hash"] == prepared.content_hash and existing["data_kind"] == data_kind:
                    return {"time_series_set": store.get_time_series_set(scenario["project_id"], existing["id"])}
            prepared = replace(prepared, version_label=f"import-{data_kind}-{prepared.content_hash}")
            actor = getattr(request.state, "current_user", None) or {}
            imported = store.import_time_series_catalog_set(scenario_id=scenario_id, source=source, prepared_import=prepared,
                                                           created_by=actor.get("email", "internal_analyst"))
            return {"time_series_set": imported}
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except MigrationControlError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        finally:
            await source_file.close()

    @app.post("/api/scenario-versions/{version_id}/hydraulic-simulation/preview")
    @app.post("/api/scenario-versions/{version_id}/hydraulic-simulation/run", status_code=201)
    async def hydraulic_simulation(version_id: int, payload: HydraulicSimulationRequest, request: Request):
        try:
            source, document, metadata, fingerprint = prepare_hydraulic_simulation(store, version_id, payload)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except (ValueError, OverflowError) as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        running = request.url.path.endswith("/run")
        if running and payload.expected_preparation_hash != fingerprint:
            raise HTTPException(status_code=409, detail="La preparación cambió. Revisa nuevamente antes de ejecutar.")
        validation = validation_service.validate_text(json.dumps(document, allow_nan=False))
        if not validation.ok:
            raise HTTPException(status_code=400, detail=validation.message)
        if not running:
            return {"preparation_hash": fingerprint, "period_count": len(document["time_series"]),
                    "preview_periods": document["time_series"][:12], "generation_metadata": metadata}
        actor = getattr(request.state, "current_user", None) or {}
        version = store.create_scenario_version(scenario_id=source["scenario_id"], system_case_json=document,
                    validation_payload=validation.payload, generation_metadata=metadata,
                    created_by=actor.get("email", "internal_analyst"))
        try:
            snapshot = store.get_scenario_version_hydraulic_diagram_snapshot(source["id"])
        except KeyError:
            snapshot = None
        if snapshot is not None:
            store.persist_scenario_version_hydraulic_diagram_snapshot(scenario_version_id=version["id"],
                layout_snapshot=snapshot["layout_snapshot"], source_case_id=snapshot.get("source_case_id"),
                created_by=actor.get("email", "internal_analyst"))
        return enqueue_run(version["id"], triggered_by=actor.get("email", "internal_analyst"),
                           triggered_by_user_id=actor.get("id"), triggered_by_display_name=actor.get("display_name"))
