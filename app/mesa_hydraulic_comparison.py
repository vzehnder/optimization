"""Hydraulic comparison uses executed entities, never the mutable case inventory."""

from app.optimization_mesa import HYDRAULIC_OUTPUTS, HYDRAULIC_PARAMETERS, _instant, _output_series, _run_outputs, _market_price_comparison


def topology(snapshot):
    network = snapshot["hydraulic_network"]
    return (
        sorted((n["id"], n["type"]) for n in network.get("nodes", [])),
        sorted((p["id"], p.get("non_modeled", False), tuple(sorted(p["units"]))) for p in network.get("plants", [])),
        sorted((u["id"], u["plant_id"], u["intake_node"], u["discharge_node"]) for u in network.get("units", [])),
        sorted((r["id"], r["from_node"], r["to_node"], r.get("type"), r.get("routing_method", "none"),
                r.get("travel_time_hours", 0)) for r in network.get("reaches", [])),
    )


def frozen_outputs(selected, snapshot, table, range_start, range_end):
    network = snapshot["hydraulic_network"]
    for collection, kind in (("nodes", "reservoir"), ("units", "unit"), ("reaches", "reach")):
        for entity in network.get(collection, []):
            if kind == "reservoir" and entity["type"] != "reservoir":
                continue
            node = {"id": entity["id"], "type": f"hydraulic_{kind}"}
            for column, key, name, unit in HYDRAULIC_OUTPUTS[kind]:
                output = _output_series(dict(signal_key=key, name=name, unit=unit, role="output",
                    editable=False, status="unavailable", points=[]), node=node, column=column,
                    selected=selected, snapshot={**snapshot, "nodes": [node]}, table=table,
                    range_start=range_start, range_end=range_end)
                yield dict(entity_id=entity["id"], entity_type="hydraulic_node" if kind == "reservoir" else node["type"],
                    signal_key=key, name=name, unit=unit, role="output", status="no_reference",
                    message="Sin referencia previa", before=None, after=output, delta=None)


def frozen_inputs(selected, snapshot, range_start, range_end):
    for collection, kind, key, name in (
        ("nodes", "hydraulic_node", "natural_inflow_m3s", "Aporte natural"),
        ("reaches", "hydraulic_reach", "minimum_flow_m3s", "Caudal mínimo"),
    ):
        for entity in snapshot["hydraulic_network"].get(collection, []):
            if not any(entity["id"] in p.get(key, {}) for p in snapshot["time_series"]):
                continue
            node = {"id": entity["id"], "type": kind}
            rows = [{"asset_id": entity["id"], "asset_type": kind, "timestamp": p["timestamp"],
                     "duration_hours": p["duration_hours"], key: p.get(key, {}).get(entity["id"])}
                    for p in snapshot["time_series"]]
            frozen = _output_series(dict(signal_key=key, name=name, unit="m3/s", role="input",
                editable=False, status="unavailable", points=[]), node=node, column=key,
                selected=selected, snapshot={**snapshot, "nodes": [node]}, table={"columns": [key], "rows": rows},
                range_start=range_start, range_end=range_end)
            frozen["source"] = "executed_snapshot"
            available = frozen["status"] == "available"
            yield dict(entity_id=entity["id"], entity_type=kind, signal_key=key, name=name, unit="m3/s", role="input",
                status="unchanged_input" if available else "unavailable",
                message="Entrada exógena sin cambio; no representa una mejora." if available else frozen["message"],
                before=frozen, after=frozen, delta=[{**p, "value": 0} for p in frozen["points"]] if available else None)


def frozen_series(selected, snapshot, table, range_start, range_end):
    series = list(frozen_inputs(selected, snapshot, range_start, range_end))
    series.extend(frozen_outputs(selected, snapshot, table, range_start, range_end))
    for plant in snapshot["hydraulic_network"].get("plants", []):
        for _, key, name, unit in HYDRAULIC_OUTPUTS["plant"]:
            members = [s["after"] for s in series if s["entity_type"] == "hydraulic_unit"
                       and s["entity_id"] in plant["units"] and s["signal_key"] == key]
            output = dict(signal_key=key, name=name, unit=unit, role="output", editable=False,
                status="unavailable", message="Sin resultados completos de las unidades de la central.", points=[],
                source="asset_dispatch:plant_units", run_id=selected["id"], scenario_version_id=selected["scenario_version_id"])
            if (not plant.get("non_modeled") and members and len(members) == len(plant["units"])
                    and all(m["status"] == "available" for m in members)):
                output = {**members[0], "source": "asset_dispatch:plant_units", "points": [
                    {**p, "value": sum(m["points"][i]["value"] for m in members)}
                    for i, p in enumerate(members[0]["points"])]}
            series.append(dict(entity_id=plant["id"], entity_type="hydraulic_plant", signal_key=key, name=name,
                unit=unit, role="output", status="no_reference", message="Sin referencia previa",
                before=None, after=output, delta=None))
    for collection, kind in (("plants", "hydraulic_plant"), ("units", "hydraulic_unit")):
        for entity in snapshot["hydraulic_network"].get(collection, []):
            series.append(_market_price_comparison(selected, snapshot, entity["id"], kind, range_start, range_end))
    for signal in series:
        if signal["after"]["status"] != "available":
            signal.update(status="unavailable", message=signal["after"]["message"])
    return series


def frozen_components(selected, snapshot, series):
    components = []
    for collection, kind in (("nodes", "node"), ("plants", "plant"), ("units", "unit"), ("reaches", "reach")):
        for entity in snapshot["hydraulic_network"].get(collection, []):
            entity_type = f"hydraulic_{kind}"
            signals = [s["after"] for s in series if s["entity_id"] == entity["id"] and s["entity_type"] == entity_type]
            if not signals:
                continue
            values = {**entity, **entity.get("reservoir", {})}
            parameters = [dict(key=key, name=name, value=values[key], unit=unit,
                source="executed_snapshot", scenario_version_id=selected["scenario_version_id"])
                for key, (name, unit) in HYDRAULIC_PARAMETERS.items() if values.get(key) is not None]
            components.append(dict(entity_id=entity["id"], entity_type=entity_type, linkable_object_id=None,
                name=entity.get("display_name", entity.get("name", entity["id"])),
                component_type=entity.get("type", kind) if kind == "node" else kind,
                parent_entity_id=entity.get("plant_id"), from_entity_id=entity.get("from_node", entity.get("intake_node")),
                to_entity_id=entity.get("to_node", entity.get("discharge_node")),
                series=signals[0], additional_series=signals[1:], parameters=parameters))
    return components


def read_hydraulic_comparison(store, *, case_id, selected, snapshot, table, range_start, range_end,
                              scenario_id, reference_run_id, artifact_root):
    series = frozen_series(selected, snapshot, table, range_start, range_end)
    references = []
    reference = None
    for run in store.list_scenario_runs(scenario_id):
        if run["id"] == selected["id"] or run["status"] != "succeeded":
            continue
        version = store.get_scenario_version(run["scenario_version_id"])
        if version["system_case_json"].get("schema_version") != "bess_system_dispatch.v3":
            continue
        origin = version["generation_metadata"].get("input_variant", {})
        variant = (store.get_case_input_variant_for_case(case_id, origin["id"]) if origin.get("id")
                   else store.get_or_create_default_input_variant(case_id))
        _, item, document, result = _run_outputs(store, scenario_id=scenario_id, variant=variant,
            run_id=run["id"], artifact_root=artifact_root)
        references.append(item)
        if run["id"] == reference_run_id:
            reference = item
            prior = {(s["entity_type"], s["entity_id"], s["signal_key"], s["unit"]): s["after"]
                     for s in frozen_series(item, document, result, range_start, range_end)}
            for signal in series:
                if signal["role"] == "input":
                    continue
                before = prior.get((signal["entity_type"], signal["entity_id"], signal["signal_key"], signal["unit"]))
                signal["before"] = before
                if topology(snapshot) != topology(document):
                    signal.update(status="incompatible", message="La topología o la identidad hidráulica no coinciden; Δ no disponible.")
                elif before and before["status"] == signal["after"]["status"] == "available":
                    before_grid = [(_instant(p["start"], before.get("timezone")), _instant(p["end"], before.get("timezone"))) for p in before["points"]]
                    after_grid = [(_instant(p["start"], signal["after"].get("timezone")), _instant(p["end"], signal["after"].get("timezone"))) for p in signal["after"]["points"]]
                    if any(t.tzinfo is None for interval in before_grid + after_grid for t in interval):
                        signal.update(status="incompatible", message="Falta zona horaria en el snapshot; Δ no disponible.")
                        continue
                    if before_grid != after_grid:
                        signal.update(status="incompatible", message="Los intervalos no coinciden; no se remuestrea ni se calcula Δ.")
                        continue
                    signal.update(status="comparable", message="Diferencia = después − antes.", delta=[
                        {**after, "value": after["value"] - old["value"]}
                        for old, after in zip(before["points"], signal["after"]["points"])])
                else:
                    signal.update(status="unavailable", message="No hay resultados completos para la misma entidad y magnitud.")
    if reference_run_id is not None and reference is None:
        raise KeyError("La referencia debe ser otra ejecución hidráulica exitosa del mismo caso.")
    return dict(case_id=case_id, selected_run=selected, reference_run=reference, references=references, series=series,
                components=frozen_components(selected, snapshot, series))
