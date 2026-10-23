"""Read-only mesa comparison from immutable execution documents."""

from datetime import datetime, timedelta, timezone
import json
import math
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field

from app.optimization_mesa import ELECTRICAL_OUTPUTS, HYDRAULIC_OUTPUTS, MesaComponent, MesaPoint, MesaRun, MesaSeries, _cover_series, _instant, _output_series, _run_outputs
from app.result_indexing import DISPATCH_SIGNAL_KEY_CATALOG


class MesaComparisonSeries(BaseModel):
    entity_id: str
    entity_type: str
    linkable_object_id: int | None = None
    signal_key: str
    name: str
    unit: str
    role: Literal["input", "output"]
    status: Literal["unchanged_input", "comparable", "no_reference", "incompatible", "unavailable"]
    message: str
    before: MesaSeries | None = None
    after: MesaSeries
    delta: list[MesaPoint] | None = None


class MesaComparisonResponse(BaseModel):
    case_id: int
    selected_run: MesaRun
    reference_run: MesaRun | None = None
    references: list[MesaRun] = Field(default_factory=list)
    series: list[MesaComparisonSeries]
    components: list[MesaComponent] = Field(default_factory=list)


def _topology(document):
    return (document["schema_version"], sorted((n["id"], n["type"]) for n in document.get("nodes", [])),
            sorted(json.dumps(edge, sort_keys=True) for edge in document.get("edges", [])))


def read_comparison(store, *, scenario_id, case_id, variant_id, run_id,
                    reference_run_id=None, range_start=None, range_end=None, artifact_root="."):
    case = store.get_or_create_case_for_scenario(scenario_id)
    if case["id"] != case_id:
        raise KeyError("El caso no pertenece al escenario.")
    variant = store.get_case_input_variant_for_case(case_id, variant_id)
    if (range_start is None) != (range_end is None):
        raise ValueError("Indica inicio y fin del período.")
    if range_start is not None:
        start, end = datetime.fromisoformat(range_start), datetime.fromisoformat(range_end)
        if start.tzinfo is None or end.tzinfo is None or start >= end:
            raise ValueError("El período debe tener inicio anterior al fin e incluir zona horaria.")
    _, selected, snapshot, table = _run_outputs(store, scenario_id=scenario_id, variant=variant,
        run_id=run_id, artifact_root=artifact_root)
    if selected["model_contract"] == "bess_system_dispatch.v3":
        from app.mesa_hydraulic_comparison import read_hydraulic_comparison
        return read_hydraulic_comparison(store, case_id=case_id, selected=selected, snapshot=snapshot,
            table=table, range_start=range_start, range_end=range_end, scenario_id=scenario_id,
            reference_run_id=reference_run_id, artifact_root=artifact_root)
    metadata = store.get_scenario_version(selected["scenario_version_id"])["generation_metadata"]
    reference = reference_snapshot = reference_table = None
    references = []
    for run in store.list_scenario_runs(scenario_id):
        if run["id"] == run_id or run["status"] != "succeeded":
            continue
        version = store.get_scenario_version(run["scenario_version_id"])
        if version["system_case_json"].get("schema_version") not in {"bess_system_dispatch.v1", "bess_system_dispatch.v2"}:
            continue
        origin = version["generation_metadata"].get("input_variant", {})
        source_variant = (store.get_case_input_variant_for_case(case_id, origin["id"]) if origin.get("id")
                          else store.get_or_create_default_input_variant(case_id))
        _, item, document, result = _run_outputs(store, scenario_id=scenario_id, variant=source_variant,
            run_id=run["id"], artifact_root=artifact_root)
        references.append(item)
        if run["id"] == reference_run_id:
            reference, reference_snapshot, reference_table = item, document, result
    if reference_run_id is not None and reference is None:
        raise KeyError("La referencia debe ser otra ejecución exitosa del mismo caso.")
    series = []
    for node in snapshot.get("nodes", []):
        descriptor = {"load": ("load_demand_mw", "Demanda", "MW"),
                      "renewable": ("renewable_available_power_mw", "Disponibilidad renovable", "MW"),
                      "hydro": ("hydro_inflow_m3s", "Aporte hidráulico", "m3/s")}.get(node["type"])
        if descriptor is None:
            continue
        key, name, unit = descriptor
        source = next((s for s in metadata.get("series_bindings", []) if s.get("signal_key") == key
                       and s.get("object_key", s.get("entity_id")) == node["id"]
                       and s.get("object_type_key", s.get("entity_type")) == f"component:{node['type']}"), {})
        frozen = dict(signal_key=key, name=name, role="input", unit=unit, editable=False,
            status="unavailable", message="Entrada no disponible en el snapshot ejecutado.",
            timezone=selected["timezone"], run_id=run_id, scenario_version_id=selected["scenario_version_id"],
            source="executed_snapshot", revision_id=source.get("set_revision_id"),
            revision_number=source.get("revision_number"), content_hash=source.get("content_hash"),
            time_series_set_id=source.get("time_series_set_id"), signal_id=source.get("signal_id"), points=[])
        points = []
        try:
            for period in snapshot.get("time_series", []):
                value = float(period[key][node["id"]])
                duration = float(period["duration_hours"])
                if not math.isfinite(value) or not math.isfinite(duration) or duration <= 0:
                    raise ValueError("Muestra inválida")
                start = datetime.fromisoformat(period["timestamp"])
                if start.tzinfo is None and selected["timezone"]:
                    start = start.replace(tzinfo=ZoneInfo(selected["timezone"]))
                if start.tzinfo is None and range_start:
                    raise ValueError("Sin zona horaria")
                end = ((start.astimezone(timezone.utc) + timedelta(hours=duration)).astimezone(start.tzinfo)
                       if start.tzinfo else start + timedelta(hours=duration))
                points.append(dict(start=start.isoformat(), end=end.isoformat(), value=value))
        except (KeyError, TypeError, ValueError):
            points = []
        if points:
            frozen = _cover_series({**frozen, "status": "available", "message": "", "points": points}, range_start, range_end)
        available = frozen["status"] == "available"
        series.append(dict(entity_id=node["id"], entity_type=f"component:{node['type']}",
            linkable_object_id=source.get("linkable_object_id"), signal_key=key, name=name, unit=unit, role="input",
            status="unchanged_input" if available else "unavailable",
            message="Entrada exógena sin cambio; no representa una mejora." if available else frozen["message"],
            before=frozen, after=frozen,
            delta=[{**p, "value": 0} for p in frozen["points"]] if available else None))
    for node in snapshot.get("nodes", []):
        descriptors = (HYDRAULIC_OUTPUTS["plant"] + HYDRAULIC_OUTPUTS["reservoir"] if node["type"] == "hydro" else
                       [(column, DISPATCH_SIGNAL_KEY_CATALOG[column], name, unit) for column, name, unit in ELECTRICAL_OUTPUTS.get(node["type"], [])])
        for column, key, name, unit in descriptors:
            output = _output_series(dict(signal_key=key, name=name, unit=unit, role="output", editable=False,
                status="unavailable", points=[]), node=node, column=column, selected=selected,
                snapshot=snapshot, table=table, range_start=range_start, range_end=range_end)
            before = None
            delta = None
            status, message = "no_reference", "Sin referencia previa"
            if reference:
                before = _output_series(dict(signal_key=key, name=name, unit=unit, role="output", editable=False,
                    status="unavailable", points=[]), node=node, column=column, selected=reference,
                    snapshot=reference_snapshot, table=reference_table, range_start=range_start, range_end=range_end)
                if before["status"] == output["status"] == "available":
                    before_grid = [(_instant(p["start"], before.get("timezone")), _instant(p["end"], before.get("timezone"))) for p in before["points"]]
                    after_grid = [(_instant(p["start"], output.get("timezone")), _instant(p["end"], output.get("timezone"))) for p in output["points"]]
                    if any(instant.tzinfo is None for interval in before_grid + after_grid for instant in interval):
                        status, message = "incompatible", "Falta zona horaria en el snapshot; no se pueden alinear instantes para Δ."
                    elif _topology(snapshot) != _topology(reference_snapshot):
                        status, message = "incompatible", "La topología o el modelo de las ejecuciones no coinciden; Δ no disponible."
                    elif before_grid != after_grid:
                        status, message = "incompatible", "Los intervalos no coinciden; no se remuestrea ni se calcula Δ."
                    else:
                        status, message = "comparable", "Diferencia = después − antes."
                        delta = [{**after, "value": after["value"] - prior["value"]}
                                 for prior, after in zip(before["points"], output["points"])]
                else:
                    status, message = "unavailable", "No hay resultados completos para ambos lados."
            series.append(dict(entity_id=node["id"], entity_type=f"component:{node['type']}",
                signal_key=key, name=name, unit=unit, role="output", status=status,
                message=message, before=before, after=output, delta=delta))
    components = []
    for node in snapshot.get("nodes", []):
        entity_type = f"component:{node['type']}"
        signals = [s for s in series if s["entity_id"] == node["id"] and s["entity_type"] == entity_type]
        if signals:
            components.append(dict(entity_id=node["id"], entity_type=entity_type,
                linkable_object_id=next((s.get("linkable_object_id") for s in signals if s.get("linkable_object_id")), None),
                name=node.get("display_name", node.get("name", node["id"])),
                component_type=node["type"], series=signals[0]["after"],
                additional_series=[s["after"] for s in signals[1:]]))
    return dict(case_id=case_id, selected_run=selected, reference_run=reference, references=references,
                series=series, components=components)
