"""Explicit publication of pre-solve numeric outputs into the canonical catalog."""
import json
import uuid
from datetime import timedelta

from fastapi import HTTPException

from app.component_rules import digest, encode, timestamp, project_enabled
from app.rule_applications import instant, snapshot_transaction, latest_publication, compile_context
from app.rule_inputs import assert_inputs_current
from app.rule_runtime import SDK_VERSION
from app.rule_ir import validate_outputs
from app.time_series_canonical import normalize_canonical_periods, normalize_canonical_signals
from app.time_series_migration import MigrationControlError


def initialize(store):
    with store._lock, store._database_transaction():
        store.connection.execute(f"""
            CREATE TABLE IF NOT EXISTS component_rule_series (
                id TEXT PRIMARY KEY,
                rule_id TEXT NOT NULL REFERENCES component_rule_drafts(id),
                set_id INTEGER NOT NULL UNIQUE REFERENCES {store._canonical('time_series_sets')}(id),
                document TEXT NOT NULL
            )
        """)


def read(repository, rule_id, identity):
    row = repository.store.connection.execute(
        "SELECT * FROM component_rule_series WHERE id = ? AND rule_id = ?", (identity, rule_id)).fetchone()
    if row is None:
        raise HTTPException(404, "Serie calculada no encontrada")
    result = {**json.loads(row["document"]), "id": row["id"], "validation_status": "current"}
    try:
        assert_current(repository, result["lineage"])
    except HTTPException as error:
        result.update(validation_status="stale", validation_error=error.detail if isinstance(error.detail, dict) else {"message": error.detail})
    return result


def assert_current(repository, lineage):
    if latest_publication(repository.store, lineage["rule_id"]) != lineage["publication_head"]:
        raise HTTPException(409, "Hay una nueva revisión de la regla; prueba y regenera explícitamente")
    if lineage["runtime"]["sdk"] != SDK_VERSION:
        raise HTTPException(409, "El SDK cambió; prueba y regenera explícitamente")
    assert_inputs_current(repository.store, lineage["project_id"], lineage["object_id"], lineage["inputs"], lineage["aliases"])


def options(repository, rule_id, project_id, object_id, job_id):
    store = repository.store
    job = repository.job(job_id, rule_id, project_id, object_id)
    if job["status"] != "succeeded" or not job.get("grid"):
        return {"outputs": []}
    outputs = validate_outputs(job["result"].get("outputs", []), len(job["grid"]))
    result = []
    object_type = store.get_linkable_object(object_id)["object_type_key"]
    roles = store.connection.execute("SELECT role_key FROM time_series_binding_roles WHERE status = 'active'").fetchall()
    grouped = {}
    for point in outputs:
        grouped.setdefault(point["name"], []).append(point)
    for name, rows in sorted(grouped.items()):
        if len(rows) != len(job["grid"]):
            continue
        classifiers = store.connection.execute("""SELECT s.semantic_key, s.display_name FROM time_series_semantic_types s
            JOIN measurement_units u ON u.id = s.canonical_unit_id WHERE s.status = 'active' AND u.status = 'active'
            AND u.unit_key = ? AND s.default_aggregation = 'mean' ORDER BY s.semantic_key""", (rows[0]["unit"],)).fetchall()
        result.append({"name": name, "unit_key": rows[0]["unit"], "period_count": len(rows), "classifications": [
            {"semantic_type_key": c["semantic_key"], "display_name": c["display_name"], "object_roles": [r["role_key"] for r in roles
             if store.evaluate_time_series_compatibility(semantic_type_key=c["semantic_key"], unit_key=rows[0]["unit"],
                binding_role_key=r["role_key"], object_type_key=object_type, usage="execution")["allowed"]]} for c in classifiers]})
    return {"outputs": result}


def reject_cycles(store, rule_id, inputs, target_id):
    pending = {p["set_id"] for p in inputs}
    visited = set()
    while pending:
        set_id = pending.pop()
        if set_id in visited:
            continue
        visited.add(set_id)
        recipe = store.connection.execute("SELECT rule_id FROM component_rule_series WHERE set_id = ?", (set_id,)).fetchone()
        if set_id == target_id or (recipe and recipe["rule_id"] == rule_id):
            raise HTTPException(422, "La publicación crearía un ciclo entre recetas o sus dependencias")
        if len(visited) > 10000:
            raise HTTPException(422, "Demasiadas dependencias para validar la receta")
        rows = store.connection.execute(f"""SELECT DISTINCT source.time_series_set_id AS set_id
            FROM {store._canonical('time_series_revision_lineage')} l
            JOIN {store._canonical('time_series_set_revisions')} derived ON derived.id = l.derived_set_revision_id
            JOIN {store._canonical('time_series_set_revisions')} source ON source.id = l.source_set_revision_id
            WHERE derived.time_series_set_id = ?""", (set_id,)).fetchall()
        pending.update(row["set_id"] for row in rows)


def publish(repository, rule_id, project_id, object_id, body, actor, request_key, *, regeneration=None):
    store = repository.store
    with store._lock, snapshot_transaction(store):
        # Serialize the claim as well as the write across API processes.
        store.connection.execute("UPDATE projects SET name = name WHERE id = ?", (project_id,))
        claim = store._claim_idempotency(actor_id=actor["email"], operation_kind="rule_series_publication",
            scope_key=f"rule:{rule_id}:{regeneration['id'] if regeneration else 'new'}", idempotency_key=request_key,
            request_hash=digest({"definition": body.model_dump(), "regeneration": regeneration}))
        if claim["state"] == "completed":
            return claim["response"]
        if not project_enabled(project_id):
            raise HTTPException(503, "Las reglas están deshabilitadas en este proyecto")
        try:
            store._require_canonical_mutations_available("rule_series_publication")
        except MigrationControlError as error:
            raise HTTPException(409, {"code": error.code, **error.context}) from error
        target_id = None
        if regeneration:
            previous = read(repository, rule_id, regeneration["id"])
            target_id = previous["set_id"]
            target = store._lock_canonical_set(target_id)
            if target["status"] == "archived" or target["current_revision_id"] != regeneration["expected_revision_id"]:
                raise HTTPException(409, "La serie cambió; revisa su revisión actual antes de regenerar")
        elif body.series_kind == "catalog":
            existing = store.connection.execute(f"SELECT id FROM {store._canonical('time_series_sets')} "
                "WHERE owner_project_id = ? AND name = ? AND series_kind = 'catalog'", (project_id, body.name)).fetchone()
            if existing:
                raise HTTPException(409, "Ya existe una fuente con ese nombre; elige otro para publicar una serie nueva")
        job = repository.job(body.job_id, rule_id, project_id, object_id)
        row = store.connection.execute("SELECT payload FROM component_rule_snapshots WHERE id = ?", (body.job_id,)).fetchone()
        payload = json.loads(row["payload"])
        if job["status"] != "succeeded" or "compilation" not in payload:
            raise HTTPException(409, "Prueba una revisión publicada antes de publicar una serie")
        outputs = validate_outputs(job["result"].get("outputs", []), len(payload["grid"]))
        selected = [p for p in outputs if p["name"] == body.output_name]
        if len(selected) != len(payload["grid"]) or any(p["unit"] != body.unit_key for p in selected):
            raise HTTPException(422, "La salida debe ser numérica, completa y conservar su unidad")
        semantic = store.connection.execute("SELECT validation_rules_json, default_aggregation FROM time_series_semantic_types WHERE semantic_key = ? AND status = 'active'", (body.semantic_type_key,)).fetchone()
        if semantic is None or semantic["default_aggregation"] != "mean":
            raise HTTPException(422, "La semántica debe admitir medias por intervalo")
        limits = json.loads(semantic["validation_rules_json"])
        for point in selected:
            if point["value"] < limits.get("minimum", float("-inf")) or point["value"] > limits.get("maximum", float("inf")):
                raise HTTPException(422, {"message": "Valor fuera del rango de la semántica declarada", "period": point["period"]})
        lineage = {key: payload[key] for key in ("code", "parameters", "inputs", "grid", "runtime", "publication_id", "publication_head", "aliases", "temporal", "windows")}
        # Ancestors are pinned by revision/hash; avoid embedding their recipes recursively.
        lineage["inputs"] = [{k: v for k, v in source.items() if k != "metadata_json"} for source in payload["inputs"]]
        lineage.update(rule_id=rule_id, code_hash=job["code_hash"], context_hash=job["context_hash"],
                       project_id=project_id, object_id=object_id, job_id=body.job_id,
                       output_name=body.output_name, output_hash=digest(selected), timezone="UTC", timestamp_convention="period_start")
        for set_id in sorted({p["set_id"] for p in payload["inputs"]}):
            store._lock_canonical_set(set_id)
        reject_cycles(store, rule_id, payload["inputs"], target_id)
        assert_current(repository, lineage)
        current = compile_context(store, project_id, object_id, payload["compilation"]["scope"])
        if current["fingerprint"] != payload["compilation"]["fingerprint"]:
            raise HTTPException(409, "El caso cambió desde la prueba; vuelve a probar")
        periods = normalize_canonical_periods([{"timestamp_start": instant(p["timestamp"]).replace(tzinfo=None).isoformat(),
            "timestamp_end": (instant(p["timestamp"]) + timedelta(hours=p["duration_hours"])).replace(tzinfo=None).isoformat(),
            "duration_hours": p["duration_hours"]} for p in payload["grid"]])
        signals = normalize_canonical_signals([{"series_key": body.series_key, "display_name": body.name,
            "semantic_type_key": body.semantic_type_key, "unit_key": body.unit_key, "signal_role": "input", "aggregation": "mean"}])
        dependencies = [{"series_key": body.series_key, "source_set_revision_id": p["revision_id"],
                      "source_signal_id": p["signal_id"], "source_content_hash": p["content_hash"],
                      "source_owner_linkable_object_id": p["owner_linkable_object_id"],
                      "target_owner_linkable_object_id": object_id if body.series_kind == "object_specific" else None,
                      "lineage_kind": "allowlisted_transformation", "reason_code": "rule_output", "reason_text": body.reason}
                     for p in { (p["revision_id"], p["signal_id"]): p for p in payload["inputs"] }.values()]
        if body.series_kind == "object_specific":
            receipt = write_specific(store, project_id, object_id, body, periods, selected, lineage, dependencies, actor, target_id)
        else:
            receipt = store._publish_canonical_set_revision(project_id=project_id, name=body.name, signals=signals,
            periods=periods, values={body.series_key: [p["value"] for p in selected]}, data_class_key="derived",
            revision_timezone="UTC", timestamp_convention="period_start", version_label=None, description="",
            source=None, change_summary=body.reason, metadata={"component_rule": lineage},
            lineage=dependencies, actor=actor["email"], set_id=target_id, force_revision=bool(regeneration))
        identity = regeneration["id"] if regeneration else uuid.uuid4().hex
        document = {**receipt, "signal_id": receipt["signal_ids"][body.series_key], "lineage": lineage,
                    "definition": body.model_dump(), "created_by": actor["id"], "created_at": timestamp()}
        if regeneration:
            store.connection.execute("UPDATE component_rule_series SET document = ? WHERE id = ?", (encode(document), identity))
        else:
            store.connection.execute("INSERT INTO component_rule_series VALUES (?, ?, ?, ?)",
                                     (identity, rule_id, receipt["set_id"], encode(document)))
        response = read(repository, rule_id, identity)
        store._complete_idempotency(claim_id=claim["id"], response=response, http_status=201)
        return response


def write_specific(store, project_id, object_id, body, periods, selected, lineage, dependencies, actor, target_id):
    from app.object_time_series import object_series_etag
    linkable = store.authorize_object_series_root(project_id=project_id, linkable_object_id=object_id)
    durations = {p["duration_hours"] for p in periods}
    contract = {"regularity": "regular" if len(durations) == 1 else "irregular",
                "nominal_resolution_seconds": next(iter(durations)) * 3600 if len(durations) == 1 else None,
                "timestamp_convention": "period_start"}
    if target_id is None:
        signal_id = store._insert_object_series_definition(linkable=linkable, document={
            "object_series_key": body.series_key, "display_name": body.name, "semantic_type_key": body.semantic_type_key,
            "unit_key": body.unit_key, "data_class_key": "derived", "timezone": "UTC",
            "intended_binding_role_key": body.intended_binding_role_key, "temporal_contract": contract,
            "source_expectation": {"kind": "api", "display_name": "Salida de regla"}}, actor=actor["email"])
    else:
        target = store._lock_canonical_set(target_id)
        if target["owner_linkable_object_id"] != object_id or target["series_kind"] != "object_specific":
            raise HTTPException(409, "La serie específica debe conservar su propietario")
        signal_id = target["object_specific_signal_id"]
    row = store._object_series_row(linkable_object_id=object_id, signal_id=signal_id)
    document = {"mode": "replace_full", "revision_contract": {**contract, "data_class_key": "derived", "timezone": "UTC"},
                "source": {"kind": "api", "display_name": "Salida de regla"},
                "points": [{"timestamp_start": p["timestamp_start"] + "Z", "duration_seconds": p["duration_hours"] * 3600,
                            "values": {body.series_key: {"value": value["value"]}}} for p, value in zip(periods, selected)]}
    if row["current_revision_id"] is not None:
        current = store.read_canonical_revision(row["current_revision_id"], with_values=False)
        document["expected_base"] = {"revision_id": current["id"], "content_hash": current["content_hash"]}
    staged, refusal = store._stage_object_series_points(linkable=linkable, row=row, document=document, actor=actor["email"])
    if refusal:
        raise refusal
    ingestion = store._ingestion_row_by_key(staged["ingestion_id"])
    receipt = store._publish_object_series_revision(linkable=linkable, row=row, ingestion=ingestion,
        validation_token=staged["validation_token"], confirm=True, reason_code="rule_output", reason_text=body.reason,
        if_match=object_series_etag(signal_id=signal_id, resource_version=row["resource_version"]), actor=actor["email"],
        derivation_metadata={"component_rule": lineage}, lineage=dependencies, force_revision=target_id is not None)
    return {**receipt, "signal_ids": {body.series_key: signal_id}, "content_hash": receipt["content_hash"].removeprefix("sha256:")}
