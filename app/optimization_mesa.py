"""Read-only projection for the analyst's optimization desk.

Samples remain in the existing variant sources; this module owns no persistence.
"""

from datetime import datetime, timedelta, timezone
import math
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field

from app.result_indexing import DISPATCH_SIGNAL_KEY_CATALOG
from app.results import ResultReadError, read_csv_artifact
from app.time_series_catalog import TIME_SERIES_SIGNAL_CATALOG


ELECTRICAL_OUTPUTS = {
    "battery": [("battery_charge_mw", "Carga BESS", "MW"),
                ("battery_discharge_mw", "Descarga BESS", "MW"),
                ("battery_energy_mwh", "Energía almacenada", "MWh")],
    "renewable": [("renewable_used_mw", "Generación utilizada", "MW"),
                  ("renewable_curtailed_mw", "Generación vertida", "MW")],
}

BATTERY_PARAMETERS = {
    "charge_power_max_mw": ("Potencia máxima de carga", "MW"),
    "discharge_power_max_mw": ("Potencia máxima de descarga", "MW"),
    "energy_min_mwh": ("Energía mínima", "MWh"),
    "energy_max_mwh": ("Energía máxima", "MWh"),
    "initial_energy_mwh": ("Energía inicial", "MWh"),
    "charge_efficiency": ("Eficiencia de carga", "p.u."),
    "discharge_efficiency": ("Eficiencia de descarga", "p.u."),
    "degradation_cost_per_mwh_delta_soc": ("Costo de degradación", "USD/MWh"),
    "terminal_condition": ("Condición terminal", "—"),
    "terminal_energy_min_mwh": ("Energía terminal mínima", "MWh"),
    "prevent_simultaneous_charge_discharge": ("Evitar carga y descarga simultáneas", "—"),
    "degradation_linear_delta_soc": ("Degradación lineal", "—"),
}

HYDRAULIC_OUTPUTS = {
    "plant": [("hydro_power_mw", "hydro_generation_power_mw", "Potencia hidráulica", "MW"),
              ("hydro_turbine_flow_m3s", "hydro_turbine_flow_m3s", "Caudal turbinado", "m3/s")],
    "unit": [("hydro_power_mw", "hydro_generation_power_mw", "Potencia hidráulica", "MW"),
             ("hydro_turbine_flow_m3s", "hydro_turbine_flow_m3s", "Caudal turbinado", "m3/s")],
    "reservoir": [("hydro_storage_hm3", "hydro_storage_volume_hm3", "Volumen almacenado", "hm3"),
                  ("hydro_reservoir_elevation_masl", "hydro_reservoir_elevation_masl", "Cota del embalse", "m"),
                  ("hydro_spill_flow_m3s", "hydro_spill_flow_m3s", "Caudal vertido", "m3/s")],
    "reach": [("hydraulic_flow_m3s", "hydraulic_flow_m3s", "Caudal del tramo", "m3/s")],
}

HYDRAULIC_PARAMETERS = {
    "storage_min_hm3": ("Volumen mínimo", "hm3"),
    "storage_max_hm3": ("Volumen máximo", "hm3"),
    "initial_storage_hm3": ("Volumen inicial", "hm3"),
    "terminal_condition": ("Condición terminal", "—"),
    "terminal_storage_min_hm3": ("Volumen terminal mínimo", "hm3"),
    "terminal_water_value_usd_per_hm3": ("Valor terminal del agua", "USD/hm3"),
    "min_power_mw": ("Potencia mínima", "MW"), "max_power_mw": ("Potencia máxima", "MW"),
    "min_flow_m3s": ("Caudal mínimo", "m3/s"), "max_flow_m3s": ("Caudal máximo", "m3/s"),
    "flow_min_m3s": ("Caudal mínimo", "m3/s"), "travel_time_hours": ("Tiempo de tránsito", "h"),
}


class MesaContext(BaseModel):
    project_id: int
    project_name: str
    scenario_id: int
    scenario_name: str
    case_id: int
    variant_id: int
    variant_name: str
    model_contract: str | None = None


class MesaPoint(BaseModel):
    start: str
    end: str
    value: float


class MesaSeries(BaseModel):
    signal_key: str = "load_demand_mw"
    name: str = "Demanda"
    role: Literal["input", "output", "support"] = "input"
    unit: str = "MW"
    editable: bool = False
    status: Literal["available", "unbound", "no_coverage", "unavailable"]
    message: str = ""
    timezone: str | None = None
    revision_id: int | None = None
    revision_number: int | None = None
    content_hash: str | None = None
    time_series_set_id: int | None = None
    signal_id: int | None = None
    binding_state: str | None = None
    run_id: int | None = None
    scenario_version_id: int | None = None
    source: str | None = None
    points: list[MesaPoint] = Field(default_factory=list)


class MesaParameter(BaseModel):
    key: str
    name: str
    value: float | str | bool
    unit: str
    source: Literal["current_preparation", "executed_snapshot"] = "current_preparation"
    scenario_version_id: int | None = None


class MesaComponent(BaseModel):
    linkable_object_id: int | None
    entity_id: str
    entity_type: str
    name: str
    base_entity_id: int | None = None
    case_entity_id: int | None = None
    parent_entity_id: str | None = None
    from_entity_id: str | None = None
    to_entity_id: str | None = None
    component_type: str | None = None
    is_active: bool = True
    series: MesaSeries
    additional_series: list[MesaSeries] = Field(default_factory=list)
    parameters: list[MesaParameter] = Field(default_factory=list)


class MesaRun(BaseModel):
    id: int
    scenario_version_id: int
    model_contract: str
    timezone: str | None = None


class MesaResponse(BaseModel):
    context: MesaContext
    components: list[MesaComponent]
    runs: list[MesaRun] = Field(default_factory=list)
    selected_run: MesaRun | None = None


def _instant(value: str, zone: str | None) -> datetime:
    instant = datetime.fromisoformat(value)
    if instant.tzinfo is None:
        if zone is None:
            return instant
        instant = instant.replace(tzinfo=ZoneInfo(zone))
    return instant.astimezone(timezone.utc)


def _canonical_time(value: str, zone: str) -> str:
    """Canonical storage uses naive UTC; preserve the instant in the source zone."""
    instant = datetime.fromisoformat(value)
    if instant.tzinfo is None:
        instant = instant.replace(tzinfo=timezone.utc)
    return instant.astimezone(ZoneInfo(zone)).isoformat()


def _cover_series(series: dict, range_start: str | None, range_end: str | None) -> dict:
    points = series.get("points", [])
    zone = series["timezone"]
    if points:
        start = _instant(range_start or points[0]["start"], zone)
        end = _instant(range_end or points[-1]["end"], zone)
        points = [point for point in points if _instant(point["start"], zone) < end and _instant(point["end"], zone) > start]
        cursor = start
        for point in points:
            if _instant(point["start"], zone) != cursor or _instant(point["end"], zone) <= cursor:
                break
            cursor = _instant(point["end"], zone)
        else:
            if points and cursor == end:
                return {**series, "points": points}
    return {**series, "status": "no_coverage", "message": "Sin cobertura completa para el período solicitado. No se rellenan huecos ni se remuestrea la serie.", "points": []}


def _frozen_timezone(store, metadata):
    zones = set()
    for source in metadata.get("series_bindings", []):
        if source.get("timezone"):
            zones.add(source["timezone"])
        elif source.get("set_revision_id"):
            try:
                revision = store.read_canonical_revision(source["set_revision_id"])
            except KeyError:
                continue
            if revision["content_hash"] == source.get("content_hash"):
                zones.add(revision["timezone"])
    return next(iter(zones)) if len(zones) == 1 else None


def _run_outputs(store, *, scenario_id, variant, run_id, artifact_root):
    runs, selected, snapshot, table = [], None, None, None
    for run in store.list_scenario_runs(scenario_id):
        version = store.get_scenario_version(run["scenario_version_id"])
        document = version["system_case_json"]
        origin = version["generation_metadata"].get("input_variant")
        matches = origin.get("id") == variant["id"] if origin else variant["is_default"]
        hydraulic_origin = version["generation_metadata"].get("mesa_hydraulic_execution")
        if hydraulic_origin and document.get("schema_version") == "bess_system_dispatch.v3":
            matches = hydraulic_origin.get("case_id") == variant["case_id"]
        if not matches or document.get("schema_version") not in ("bess_system_dispatch.v1", "bess_system_dispatch.v2", "bess_system_dispatch.v3"):
            continue
        if run["status"] != "succeeded":
            continue
        item = {"id": run["id"], "scenario_version_id": version["id"], "model_contract": document["schema_version"], "timezone": None}
        runs.append(item)
        if run["id"] == run_id:
            item["timezone"] = _frozen_timezone(store, version["generation_metadata"])
            selected, snapshot = item, document
            table = store.get_run_asset_dispatch_result_index(run_id)
            if table is None:
                artifacts = {a["artifact_type"]: a for a in store.list_run_artifacts(run_id)}
                try:
                    table = read_csv_artifact(artifacts, "asset_dispatch_csv", artifact_root, display_name="asset_dispatch.csv")
                except (ResultReadError, OSError):
                    table = None
    if run_id is not None and selected is None:
        raise KeyError("La ejecución no está disponible en este caso y variante.")
    return runs, selected, snapshot, table


def _output_series(series, *, node, column, selected, snapshot, table, range_start, range_end):
    if selected is None:
        return series
    series = {**series, "run_id": selected["id"], "scenario_version_id": selected["scenario_version_id"],
              "source": "asset_dispatch", "message": "Sin resultado compatible para este componente y señal."}
    if not table or column not in table["columns"]:
        return series
    if not any(n.get("id") == node["id"] and n.get("type") == node["type"] for n in snapshot.get("nodes", [])):
        return series
    periods = snapshot.get("time_series", [])
    rows_by_timestamp = {}
    for row in table["rows"]:
        if row.get("asset_id") == node["id"] and row.get("asset_type") == node["type"]:
            rows_by_timestamp.setdefault(row.get("timestamp"), []).append(row)
    points = []
    try:
        for period in periods:
            start = period["timestamp"]
            matching = rows_by_timestamp.get(start, [])
            if not matching and datetime.fromisoformat(start).tzinfo is not None:
                # Julia's DateTime CSV keeps the snapshot's wall clock, without its offset.
                matching = rows_by_timestamp.get(datetime.fromisoformat(start).replace(tzinfo=None).isoformat(), [])
            if len(matching) != 1:
                return series
            if matching[0].get("duration_hours") not in (None, "") and float(matching[0]["duration_hours"]) != float(period["duration_hours"]):
                return series
            value = float(matching[0][column])
            if not math.isfinite(value):
                return series
            instant = datetime.fromisoformat(start)
            if instant.tzinfo is None:
                if selected["timezone"]:
                    instant = instant.replace(tzinfo=ZoneInfo(selected["timezone"]))
                elif range_start is not None:
                    return {**series, "message": "No se puede recortar por instantes: el snapshot no registra zona horaria."}
            duration = timedelta(hours=float(period["duration_hours"]))
            end = ((instant.astimezone(timezone.utc) + duration).astimezone(instant.tzinfo)
                   if instant.tzinfo else instant + duration).isoformat()
            points.append({"start": instant.isoformat(), "end": end, "value": value})
    except (KeyError, TypeError, ValueError):
        return series
    if not points:
        return series
    zone = selected["timezone"] or ("Offset del snapshot" if datetime.fromisoformat(points[0]["start"]).tzinfo else None)
    return _cover_series({**series, "status": "available", "message": "", "timezone": zone,
                          "points": points}, range_start, range_end)


def _hydraulic_input(store, item, project_id, range_start, range_end, *, obj, bindings, allow_diagram, legacy_sources):
    is_reach = item["component_type"] == "reach"
    signal = "minimum_flow_m3s" if is_reach else "natural_inflow_m3s"
    source = item.get("minimum_flow_series" if is_reach else "natural_inflow_series")
    series = {"signal_key": signal, "name": "Caudal mínimo" if is_reach else "Aporte natural",
              "unit": TIME_SERIES_SIGNAL_CATALOG[signal].unit, "role": "input", "status": "unbound",
              "message": "Serie hidráulica sin preparar: falta vincular una fuente de caudal."}
    role = "minimum_flow" if is_reach else "natural_inflow"
    binding = next((b for b in bindings if obj and b["status"] == "active"
                    and b["object"]["id"] == obj["id"] and b["binding_role"]["key"] == role), None)
    if binding:
        revision = store.read_canonical_revision(binding["set_revision_id"])
        return _cover_series({**series, "status": "available", "message": "", "source": "canonical_binding",
            "name": binding["signal"]["display_name"], "timezone": revision["timezone"],
            "revision_id": binding["set_revision_id"], "revision_number": revision["revision_number"],
            "content_hash": binding["bound_content_hash"], "time_series_set_id": binding["time_series_set_id"],
            "signal_id": binding["signal"]["id"], "binding_state": binding["state"],
            "points": [{"start": _canonical_time(p["timestamp_start"], revision["timezone"]), "end": _canonical_time(p["timestamp_end"], revision["timezone"]), "value": value}
                       for p, value in zip(revision["periods"], revision["values"][binding["signal"]["series_key"]])]}, range_start, range_end)
    legacy = next((s for s in legacy_sources if s["entity_type"] == item["entity_type"]
                   and s["entity_id"] == item["technical_key"] and s["signal_key"] == signal), None)
    if legacy:
        catalog = store.get_time_series_set(project_id, legacy["time_series_set_id"])
        values = {v["period_index"]: v["value_numeric"] for v in catalog["values"] if v["signal_key"] == signal}
        return _cover_series({**series, "status": "available", "message": "", "source": "legacy_variant",
            "name": catalog["name"], "timezone": catalog["timezone"], "time_series_set_id": catalog["id"],
            "revision_number": catalog["revision_number"], "content_hash": catalog["content_hash"],
            "points": [{"start": p["timestamp_start"], "end": p["timestamp_end"], "value": values[p["period_index"]]}
                       for p in catalog["periods"] if p["period_index"] in values]},
            range_start or (catalog["periods"][0]["timestamp_start"] if catalog["periods"] else None),
            range_end or (catalog["periods"][-1]["timestamp_end"] if catalog["periods"] else None))
    if not source or not allow_diagram:
        return series
    kind = source["origin"]["kind"]
    catalog = (store.get_hydraulic_time_series_set(project_id, source["time_series_set_id"])
               if kind == "hydraulic_legacy" else store.get_time_series_set(project_id, source["time_series_set_id"]))
    zone = catalog.get("timezone")
    points = []
    for row in source["points"]:
        start = datetime.fromisoformat(row["timestamp"])
        if start.tzinfo is None and zone:
            start = start.replace(tzinfo=ZoneInfo(zone))
        if start.tzinfo is None and range_start:
            return {**series, "status": "unavailable", "message": "La fuente no registra zona horaria para consultar por instantes."}
        duration = timedelta(hours=row["duration_hours"])
        end = ((start.astimezone(timezone.utc) + duration).astimezone(start.tzinfo) if start.tzinfo else start + duration)
        points.append({"start": start.isoformat(), "end": end.isoformat(), "value": row["value_m3s"]})
    return _cover_series({**series, "status": "available", "message": "", "points": points,
                          "timezone": zone, "source": kind, "time_series_set_id": source["time_series_set_id"],
                          "revision_number": source["version_number"], "content_hash": catalog.get("content_hash")}, range_start, range_end)


def _hydraulic_output(series, *, item, column, selected, snapshot, table, range_start, range_end):
    if (item.get("plant") or {}).get("non_modeled"):
        return {**series, "message": "Central no modelada en la preparación actual; no hay salida compatible."}
    if selected is None:
        return series
    unavailable = {**series, "run_id": selected["id"], "scenario_version_id": selected["scenario_version_id"],
                   "source": "asset_dispatch", "message": "Sin resultado compatible para este componente y señal."}
    network = snapshot.get("hydraulic_network", {})
    kind = item["component_type"]
    collection = {"reservoir": "nodes", "plant": "plants", "unit": "units", "reach": "reaches"}.get(kind)
    frozen = next((n for n in network.get(collection, []) if n["id"] == item["technical_key"]), None)
    if frozen is None:
        return unavailable
    if kind == "plant":
        members = [u for u in item.get("units", []) if u.get("is_active", True)]
        if not members or sorted(u["technical_key"] for u in members) != sorted(frozen.get("units", [])):
            return unavailable
        outputs = [_hydraulic_output(series, item={**u, "component_type": "unit", "parent_entity_id": item["technical_key"]},
                    column=column, selected=selected, snapshot=snapshot, table=table,
                    range_start=range_start, range_end=range_end) for u in members]
        if any(o["status"] != "available" for o in outputs):
            return unavailable
        return {**outputs[0], "source": "asset_dispatch:plant_units", "points": [
            {**point, "value": sum(o["points"][i]["value"] for o in outputs)}
            for i, point in enumerate(outputs[0]["points"])]}
    if kind == "unit":
        frozen = dict(frozen)
        for side, endpoint in (("intake", "to_node"), ("discharge", "from_node")):
            links = [r for r in network.get("reaches", [])
                     if r.get(endpoint) == frozen.get(f"{side}_node")
                     and r.get("diagram_link", {}).get("plant_key") == item.get("parent_entity_id")
                     and r.get("diagram_link", {}).get("side") == side]
            if len(links) == 1:
                frozen[f"{side}_node"] = links[0]["diagram_link"]["node_key"]
    if kind == "unit" and (frozen.get("plant_id") != item.get("parent_entity_id")
                           or frozen.get("intake_node") != item.get("intake_node_key")
                           or frozen.get("discharge_node") != item.get("discharge_node_key")):
        return unavailable
    if kind == "reach" and (frozen.get("from_node") != item.get("from_node_key")
                            or frozen.get("to_node") != item.get("to_node_key")):
        return unavailable
    if kind == "reservoir" and frozen.get("type") != "reservoir":
        return unavailable
    node = {"id": item["technical_key"], "type": f"hydraulic_{kind}"}
    return _output_series(series, node=node, column=column, selected=selected,
                          snapshot={**snapshot, "nodes": [node]}, table=table,
                          range_start=range_start, range_end=range_end)


def read_mesa(store, *, scenario_id: int, case_id: int, variant_id: int,
              range_start: str | None = None, range_end: str | None = None,
              run_id: int | None = None, artifact_root=".") -> dict:
    scenario = store.get_scenario(scenario_id)
    case = store.get_or_create_case_for_scenario(scenario_id)
    if case["id"] != case_id:
        raise KeyError("El caso no pertenece al escenario.")
    variant = store.get_case_input_variant_for_case(case_id, variant_id)
    project = store.get_project(scenario["project_id"])
    if (range_start is None) != (range_end is None):
        raise ValueError("Indica inicio y fin del período.")
    if range_start is not None and range_end is not None:
        start, end = datetime.fromisoformat(range_start), datetime.fromisoformat(range_end)
        if start.tzinfo is None or end.tzinfo is None or start >= end:
            raise ValueError("El período debe tener inicio anterior al fin e incluir zona horaria.")
    preparation = store.read_input_variant_preparation(scenario_id=scenario_id, variant_id=variant_id)
    bindings = store.read_case_bindings(scenario_id=scenario_id, variant_id=variant_id)["items"]
    runs, selected, snapshot, table = _run_outputs(store, scenario_id=scenario_id, variant=variant, run_id=run_id, artifact_root=artifact_root)
    objects = {(o["object_type_key"], o["object_key"]): o
               for o in store.list_linkable_objects(project_id=project["id"], include_archived=True)}
    components = []
    for requirement in preparation["required_signals"]:
        if requirement["signal_key"] not in ("load_demand_mw", "renewable_available_power_mw", "hydro_inflow_m3s"):
            continue
        signal_key = requirement["signal_key"]
        role_key = {"load_demand_mw": "load_demand", "renewable_available_power_mw": "renewable_available_power",
                    "hydro_inflow_m3s": "hydro_inflow"}[signal_key]
        object_id = requirement["linkable_object_id"]
        obj = objects.get((requirement["entity_type"], requirement["entity_id"]))
        if obj and obj["status"] != "active":
            continue
        series = {"status": "unbound", "message": "Sin fuente de demanda vinculada."}
        binding = next((item for item in bindings if item["status"] == "active"
                        and item["object"]["id"] == object_id
                        and item["binding_role"]["key"] == role_key), None)
        if binding:
            revision = store.read_canonical_revision(binding["set_revision_id"])
            values = revision["values"].get(binding["signal"]["series_key"], [])
            series = {
                "status": "available", "name": binding["signal"]["display_name"],
                "timezone": revision["timezone"], "revision_id": binding["set_revision_id"],
                "revision_number": revision["revision_number"], "content_hash": binding["bound_content_hash"],
                "time_series_set_id": binding["time_series_set_id"], "signal_id": binding["signal"]["id"],
                "binding_state": binding["state"],
                "points": [{"start": _canonical_time(period["timestamp_start"], revision["timezone"]), "end": _canonical_time(period["timestamp_end"], revision["timezone"]), "value": value}
                           for period, value in zip(revision["periods"], values)],
            }
            series = _cover_series(series, range_start, range_end)
        elif preparation["binding_mode"] == "legacy":
            source_ref = next((source for source in preparation["sources"]
                               if source["signal_key"] == signal_key
                               and source.get("entity_type") == requirement["entity_type"]
                               and source.get("entity_id") == requirement["entity_id"]), None)
            if source_ref:
                source = store.get_time_series_set(project["id"], source_ref["time_series_set_id"])
                values = {value["period_index"]: value["value_numeric"] for value in source["values"]
                          if value["signal_key"] == signal_key}
                series = {
                    "status": "available", "name": source["name"], "timezone": source["timezone"],
                    "revision_number": source["revision_number"], "content_hash": source["content_hash"],
                    "time_series_set_id": source["id"], "binding_state": "legacy",
                    "points": [{"start": period["timestamp_start"], "end": period["timestamp_end"], "value": values[period["period_index"]]}
                               for period in source["periods"] if period["period_index"] in values],
                }
                source_start = source["periods"][0]["timestamp_start"] if source["periods"] else None
                source_end = source["periods"][-1]["timestamp_end"] if source["periods"] else None
                series = _cover_series(series, range_start or source_start, range_end or source_end)
        series.update(signal_key=signal_key, unit=TIME_SERIES_SIGNAL_CATALOG[signal_key].unit)
        if not binding and series["status"] == "unbound":
            series.update(name="Demanda" if role_key == "load_demand" else "Disponibilidad renovable",
                          message="Sin fuente de demanda vinculada." if role_key == "load_demand" else "Sin fuente de disponibilidad renovable vinculada.")
            if role_key == "hydro_inflow":
                series.update(name="Aporte hidro simple", message="Sin fuente de aporte vinculada.")
        components.append({
            "linkable_object_id": object_id, "entity_id": requirement["entity_id"],
            "entity_type": requirement["entity_type"],
            "name": obj["display_name"] if obj else requirement["entity_id"], "series": series,
        })
    for node in preparation["model_components"]:
        if node["type"] not in (*ELECTRICAL_OUTPUTS, "hydro"):
            continue
        obj = objects.get((f"component:{node['type']}", node["id"]))
        if obj and obj["status"] != "active":
            continue
        descriptors = (HYDRAULIC_OUTPUTS["plant"] + HYDRAULIC_OUTPUTS["reservoir"] if node["type"] == "hydro" else
                       [(column, DISPATCH_SIGNAL_KEY_CATALOG[column], name, unit) for column, name, unit in ELECTRICAL_OUTPUTS[node["type"]]])
        outputs = [{"signal_key": key, "name": name,
                    "unit": unit, "role": "output", "status": "unavailable",
                    "message": "Sin resultado disponible. Selecciona una ejecución exitosa."}
                   for column, key, name, unit in descriptors]
        outputs = [_output_series(series, node=node, column=descriptor[0], selected=selected,
                                  snapshot=snapshot, table=table, range_start=range_start, range_end=range_end)
                   for series, descriptor in zip(outputs, descriptors)]
        component = next((c for c in components if c["entity_id"] == node["id"] and c["entity_type"] == f"component:{node['type']}"), None)
        if component:
            component["additional_series"] = outputs
        else:
            components.append({"linkable_object_id": obj["id"] if obj else None,
                               "entity_id": node["id"], "entity_type": f"component:{node['type']}",
                               "name": obj["display_name"] if obj else node.get("name", node["id"]),
                               "series": outputs[0], "additional_series": outputs[1:]})
            component = components[-1]
        parameter_descriptors = BATTERY_PARAMETERS if node["type"] == "battery" else {
            "curtailment_penalty_usd_per_mwh": ("Penalización de vertimiento", "USD/MWh")}
        if node["type"] == "hydro":
            parameter_descriptors = HYDRAULIC_PARAMETERS
        component["parameters"] = [{"key": key, "name": name, "unit": unit, "value": node[key]}
                                   for key, (name, unit) in parameter_descriptors.items() if node.get(key) is not None]
    hydraulic_objects = {(o["object_kind"], o["subtype_id"]): o
                         for o in store.list_linkable_objects(project_id=project["id"], include_archived=True)}
    hydraulic_items = store.read_hydraulic_case_inventory(scenario_id)
    for item in hydraulic_items:
        obj = hydraulic_objects.get((item["entity_type"], item["base_entity_id"]))
        item["is_active"] = bool(item["is_active"]) and (obj is None or obj["status"] == "active")
    units = {item["technical_key"]: item for item in hydraulic_items if item["component_type"] == "unit"}
    for item in hydraulic_items:
        if item["component_type"] == "plant":
            item["units"] = [units[u["technical_key"]] for u in item["units"]]

    for item in hydraulic_items:
        obj = hydraulic_objects.get((item["entity_type"], item["base_entity_id"]))
        series = [{"signal_key": key, "name": name, "unit": unit, "role": "output", "status": "unavailable",
                   "message": "Sin resultado disponible. Selecciona una ejecución exitosa."}
                  for _, key, name, unit in HYDRAULIC_OUTPUTS.get(item["component_type"], [])]
        series = [_hydraulic_output(s, item=item, column=descriptor[0], selected=selected, snapshot=snapshot,
                    table=table, range_start=range_start, range_end=range_end)
                  for s, descriptor in zip(series, HYDRAULIC_OUTPUTS.get(item["component_type"], []))]
        has_minimum_binding = any(obj and b["status"] == "active" and b["object"]["id"] == obj["id"]
                                  and b["binding_role"]["key"] == "minimum_flow" for b in bindings)
        legacy_sources = preparation["sources"] if preparation["binding_mode"] == "legacy" else []
        has_minimum_source = any(s["entity_type"] == item["entity_type"] and s["entity_id"] == item["technical_key"]
                                 and s["signal_key"] == "minimum_flow_m3s" for s in legacy_sources)
        if item["entity_type"] == "hydraulic_node" or item.get("minimum_flow_series") or has_minimum_binding or has_minimum_source:
            series.insert(0, _hydraulic_input(store, item, project["id"], range_start, range_end, obj=obj, bindings=bindings,
                allow_diagram=variant["is_default"] and preparation["binding_mode"] == "legacy", legacy_sources=legacy_sources))
        active = bool(item["is_active"]) and (obj is None or obj["status"] == "active")
        if not active:
            series = [{**s, "status": "unavailable", "points": [], "message": "Objeto inactivo en el caso o archivado. No se muestran muestras."} for s in series]
        parameters = item.get("reservoir") or item.get("plant") or item
        components.append({
            "linkable_object_id": obj["id"] if obj else None,
            "entity_type": item["entity_type"], "entity_id": item["technical_key"],
            "name": item["display_name"], "component_type": item["component_type"],
            "is_active": active,
            "base_entity_id": item["base_entity_id"], "case_entity_id": item["case_entity_id"],
            "parent_entity_id": item.get("parent_entity_id"),
            "from_entity_id": item.get("intake_node_key", item.get("from_node_key")),
            "to_entity_id": item.get("discharge_node_key", item.get("to_node_key")),
            "series": series[0], "additional_series": series[1:],
            "parameters": [{"key": key, "name": name, "unit": unit, "value": parameters[key]}
                           for key, (name, unit) in HYDRAULIC_PARAMETERS.items() if parameters.get(key) is not None],
        })
    for component in components:
        for series in [component["series"], *component.get("additional_series", [])]:
            series["editable"] = bool(series.get("role", "input") == "input" and series.get("revision_id")
                                      and series.get("binding_state") == "valid_current" and series["status"] == "available")
    from app.mesa_manual_series import read_manual_components
    components.extend(read_manual_components(store, project_id=project["id"], case_id=case_id,
        components=components, bindings=bindings, range_start=range_start, range_end=range_end))
    return {
        "context": {"project_id": project["id"], "project_name": project["name"],
                    "scenario_id": scenario_id, "scenario_name": scenario["name"],
                    "case_id": case_id, "variant_id": variant_id, "variant_name": variant["display_name"],
                    "model_contract": preparation["model_contract"]},
        "components": components,
        "runs": runs, "selected_run": selected,
    }
