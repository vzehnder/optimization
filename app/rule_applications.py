"""Published rule assignments and frozen compilation contexts."""
from __future__ import annotations

import json
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException

from app.component_rules import digest, encode, timestamp, project_enabled
from app.rule_ir import validate_ir, validate_outputs
from app.rule_runtime import SDK_VERSION
from app.rule_inputs import assert_inputs_current
from app.rule_objects import resolve_aliases


def initialize(store):
    with store._lock, store._database_transaction():
        store.connection.execute("""
            CREATE TABLE IF NOT EXISTS component_rule_applications (
                id TEXT PRIMARY KEY,
                rule_id TEXT NOT NULL REFERENCES component_rule_drafts(id),
                publication_id TEXT NOT NULL REFERENCES component_rule_publications(id),
                job_id TEXT NOT NULL REFERENCES component_rule_snapshots(id),
                variant_id INTEGER NOT NULL REFERENCES case_input_variants(id),
                revision INTEGER NOT NULL,
                status TEXT NOT NULL CHECK (status IN ('active', 'inactive')),
                document TEXT NOT NULL
            )
        """)
        store.connection.execute("CREATE INDEX IF NOT EXISTS rule_applications_variant ON component_rule_applications(variant_id, status)")
        store.connection.execute("""
            CREATE TABLE IF NOT EXISTS component_rule_run_requests (
                variant_id INTEGER NOT NULL REFERENCES case_input_variants(id),
                actor INTEGER NOT NULL REFERENCES users(id),
                request_id TEXT NOT NULL,
                request_hash TEXT NOT NULL,
                run_id INTEGER NOT NULL REFERENCES runs(id),
                PRIMARY KEY (variant_id, actor, request_id)
            )
        """)
        store.connection.execute("""
            CREATE TABLE IF NOT EXISTS component_rule_resolution_requests (
                rule_id TEXT NOT NULL REFERENCES component_rule_drafts(id),
                actor INTEGER NOT NULL REFERENCES users(id),
                request_id TEXT NOT NULL,
                request_hash TEXT NOT NULL,
                response TEXT NOT NULL,
                PRIMARY KEY (rule_id, actor, request_id)
            )
        """)


def instant(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)


@contextmanager
def snapshot_transaction(store):
    """One consistent commit view, without holding a transaction during Julia."""
    try:
        with store._run_materialization_transaction():
            if store.database_backend == "postgresql":
                store.connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
            yield
    except Exception as error:
        if getattr(error, "sqlstate", None) in {"40001", "40P01"}:
            raise HTTPException(409, "Los datos cambiaron al confirmar; vuelve a intentar") from error
        raise


def freeze_scope(store, project_id, scope, expected_bindings_revision=None):
    scenario_id, variant_id = scope["scenario_id"], scope["variant_id"]
    scenario = store.get_scenario(scenario_id)
    variant = store.get_case_input_variant(variant_id)
    case = store.connection.execute("SELECT scenario_id FROM optimization_cases WHERE id = ?", (variant["case_id"],)).fetchone()
    if scenario["project_id"] != project_id or case["scenario_id"] != scenario_id:
        raise HTTPException(404, "Variante fuera del proyecto o caso")
    canonical = store.materialize_run_from_canonical_bindings(
        scenario_id=scenario_id, variant_id=variant_id, range_start=scope["range_start"], range_end=scope["range_end"],
        validate_text=None, actor_user={}, request_id="rule_preview", prepare_only=True,
        expected_bindings_revision=expected_bindings_revision,
    )
    if canonical is not None:
        document, lineage = canonical["system_case"], canonical["generation_metadata"]
    elif store.list_case_time_series_bindings(variant_id):
        resolved = store.materialize_system_case_for_variant(scenario_id=scenario_id, case_input_variant_id=variant_id,
                                                          range_start=scope["range_start"], range_end=scope["range_end"], record_validation=False)
        document, lineage = resolved["system_case"], {"series_bindings": resolved["series_bindings"]}
    else:
        document = store.generate_hydraulic_v3_preview(scenario_id)
        diagram = store.get_hydraulic_diagram(scenario_id)
        sources = []
        for collection, field, signal in (("nodes", "natural_inflow_series", "natural_inflow_m3s"),
                                           ("reaches", "minimum_flow_series", "minimum_flow_m3s")):
            for entity in diagram[collection]:
                series = entity.get(field)
                if series:
                    sources.append({"entity_type": entity["entity_type"], "entity_id": entity["entity_id"],
                                    "signal_key": signal, "time_series_set_id": series["time_series_set_id"],
                                    "version_number": series["version_number"], "origin": series["origin"],
                                    "content_hash": digest(series["points"])})
        lineage = {"series_bindings": sources}
        start, end = instant(scope["range_start"]), instant(scope["range_end"])
        document["time_series"] = [p for p in document["time_series"] if start <= instant(p["timestamp"]) < end]
    if document["schema_version"] != "bess_system_dispatch.v3" or "component_rules" in document:
        raise HTTPException(422, "Esta capacidad requiere un modelo hidráulico v3 sin reglas incrustadas")
    grid = [{"timestamp": p["timestamp"], "duration_hours": p["duration_hours"]} for p in document["time_series"]]
    if not 1 <= len(grid) <= 8784:
        raise HTTPException(422, "El horizonte debe tener entre 1 y 8784 períodos")
    cursor = instant(scope["range_start"])
    for period in grid:
        duration = period["duration_hours"]
        if not isinstance(duration, (int, float)) or not 0 < duration < float("inf") or instant(period["timestamp"]) != cursor:
            raise HTTPException(422, "La grilla debe tener cobertura exacta y duraciones positivas")
        cursor += timedelta(hours=duration)
    if cursor != instant(scope["range_end"]):
        raise HTTPException(422, "La grilla no cubre exactamente el rango seleccionado")
    return {"scope": scope, "system_case": document, "grid": grid, "timezone": "UTC", "lineage": lineage,
            "fingerprint": digest({"case": document, "lineage": lineage, "variant": variant})}


def compile_context(store, project_id, object_id, scope):
    frozen = freeze_scope(store, project_id, scope)
    objects = store.linkable_object_table_names()["linkable_objects"]
    row = store.connection.execute(f"""
        SELECT u.unit_key, p.plant_key FROM {objects} o
        JOIN hydraulic_units u ON u.id = o.hydraulic_unit_id
        JOIN hydraulic_plants p ON p.id = u.hydraulic_plant_id
        JOIN case_hydraulic_units cu ON cu.hydraulic_unit_id = u.id
        JOIN optimization_cases c ON c.id = cu.case_id
        WHERE o.id = ? AND o.status = 'active' AND cu.is_active = 1 AND c.scenario_id = ?
    """, (object_id, scope["scenario_id"])).fetchone()
    if row is None or not any(u["id"] == row["unit_key"] and u["plant_id"] == row["plant_key"]
                              for u in frozen["system_case"]["hydraulic_network"]["units"]):
        raise HTTPException(422, "La unidad no pertenece al snapshot de esta variante")
    return {**frozen, "unit_key": row["unit_key"]}


def decode_application(row):
    result = dict(row)
    result.update(json.loads(result.pop("document")))
    return result


def list_applications(repository, rule_id):
    with repository.store._lock:
        rows = repository.store.connection.execute("SELECT * FROM component_rule_applications WHERE rule_id = ? ORDER BY id", (rule_id,)).fetchall()
        applications = [decode_application(row) for row in rows]
        for application in applications:
            application.update(validation_details(repository, application))
        return applications


def validation_details(repository, application):
    from app.rule_inputs import validate_inputs
    store = repository.store
    causes = []

    def check(code, operation):
        try:
            return operation()
        except HTTPException as error:
            detail = error.detail if isinstance(error.detail, dict) else {"message": error.detail}
            causes.append({"code": code, **detail, "status": "invalid" if error.status_code in {404, 422} else "stale"})
        except (KeyError, ValueError) as error:
            causes.append({"code": code, "message": str(error), "status": "invalid"})

    check("RULE_INSTANCE_CHANGED", lambda: assert_instance_current(repository, application))
    runtime = repository.runtime()
    if application["runtime"]["sdk"] != SDK_VERSION or (runtime and runtime != application["runtime"]):
        causes.append({"code": "RULE_RUNTIME_CHANGED", "message": "El runtime cambió; vuelve a probar la regla", "status": "stale"})
    if latest_publication(store, application["rule_id"]) != application["observed_publication"]:
        causes.append({"code": "RULE_PUBLICATION_CHANGED", "message": "Hay una nueva revisión publicada; revalida la aplicación con motivo", "status": "stale"})
    project_id, object_id = application["project_id"], application["object_id"]
    inputs, aliases = application.get("inputs", []), application.get("aliases", [])
    check("RULE_INPUT_INVALID", lambda: validate_inputs(store, project_id, {object_id, *(a["object_id"] for a in aliases)}, inputs))
    check("RULE_INPUT_STALE", lambda: assert_inputs_current(store, project_id, object_id, inputs, aliases))
    current = check("RULE_CONTEXT_INVALID", lambda: compile_context(store, project_id, object_id, application["compilation"]["scope"]))
    if current:
        check("RULE_OBJECT_CHANGED", lambda: assert_objects_current(store, project_id, object_id, application["compilation"], current, application["code"]))
        if current["fingerprint"] != application["compilation"]["fingerprint"]:
            causes.append({"code": "RULE_CONTEXT_CHANGED", "message": "Cambió el modelo o sus entradas; vuelve a probar y aplicar", "status": "stale"})
    status = "invalid" if any(c["status"] == "invalid" for c in causes) else "stale" if causes else "valid"
    return {"validation_status": status, "validation_causes": causes,
            **({"validation_error": next(c for c in causes if c["status"] == status)} if causes else {})}


def latest_publication(store, rule_id):
    from app.rule_library import raw_instance
    instance = raw_instance(store, rule_id)
    if instance:
        rule_id = instance["template"]["rule_id"]
    row = store.connection.execute("SELECT id FROM component_rule_publications WHERE rule_id = ? ORDER BY draft_revision DESC LIMIT 1", (rule_id,)).fetchone()
    return row["id"] if row else None


def assert_instance_current(repository, application):
    from app.rule_recovery import lifecycle
    current_lifecycle = lifecycle(repository.store, application["rule_id"])
    if any(current_lifecycle.values()) and current_lifecycle != application.get("observed_lifecycle"):
        raise HTTPException(409, {"code": "RULE_ARCHIVED", "message": "Definición archivada: revalida con motivo, reemplaza o desactiva esta aplicación"})
    if application.get("requires_revalidation"):
        raise HTTPException(409, "Variante copiada: vuelve a probar y aplicar las reglas con motivo")
    if application.get("template"):
        current = repository.get(application["rule_id"], application["project_id"], application["object_id"])
        if current["revision"] != application.get("instance_revision"):
            raise HTTPException(409, "Cambió la configuración local; vuelve a probar y aplicar con motivo")


def apply(repository, rule_id, project_id, object_id, body, actor, *, resolving=False):
    # Snapshot/publication reads share a connection with HTTP and the worker.
    with repository.store._lock:
        return _apply_locked(repository, rule_id, project_id, object_id, body, actor, resolving=resolving)


def _apply_locked(repository, rule_id, project_id, object_id, body, actor, *, resolving=False):
    store = repository.store
    if not project_enabled(project_id):
        raise HTTPException(503, "Reglas deshabilitadas en este proyecto")
    job = repository.job(body.job_id, rule_id, project_id, object_id)
    row = store.connection.execute("SELECT payload FROM component_rule_snapshots WHERE id = ?", (body.job_id,)).fetchone()
    payload = json.loads(row["payload"])
    recovery = payload.get("recovery")
    if bool(recovery) != resolving:
        raise HTTPException(409, "Confirma esta prueba mediante el recorrido de recuperación correspondiente")
    if job["status"] != "succeeded" or "compilation" not in payload:
        raise HTTPException(409, "Prueba una revisión publicada en la variante antes de aplicar")
    frozen = payload["compilation"]
    ir = validate_ir(job["result"]["ir"], object_id, len(frozen["grid"]), frozen.get("objects"),
                     grid=frozen["grid"], windows=payload.get("windows"), temporal=payload.get("temporal"))
    if not ir["rows"] and not body.accept_empty:
        raise HTTPException(422, "La regla no emite restricciones; requiere aceptación explícita")
    publication = recovery["publication"] if recovery else repository.publication(rule_id, payload["publication_id"])
    if publication["sdk"] != SDK_VERSION or job["runtime"]["sdk"] != SDK_VERSION:
        raise HTTPException(409, "El SDK cambió; vuelve a publicar y probar")
    with store._lock, snapshot_transaction(store):
        store.connection.execute("UPDATE case_input_variants SET updated_at = updated_at WHERE id = ?", (frozen["scope"]["variant_id"],))
        from app.rule_recovery import lifecycle
        for identity in sorted(lifecycle(store, rule_id)):
            store.connection.execute("UPDATE component_rule_drafts SET revision = revision WHERE id = ?", (identity,))
        if resolving:
            receipt = store.connection.execute("SELECT * FROM component_rule_resolution_requests WHERE rule_id = ? AND actor = ? AND request_id = ?",
                                               (rule_id, actor, body.request_id)).fetchone()
            if receipt:
                if receipt["request_hash"] != digest(body.model_dump()):
                    raise HTTPException(409, "Solicitud reutilizada con otra resolución")
                return json.loads(receipt["response"])
        runtime = repository.runtime()
        if runtime and runtime != job["runtime"]:
            raise HTTPException(409, "El runtime cambió; vuelve a probar la regla")
        draft = repository.get(rule_id, project_id, object_id)
        if not recovery:
            from app.rule_recovery import require_available
            require_available(store, rule_id)
        if recovery:
            from app.rule_recovery import recovery_state
            if recovery_state(store, rule_id, frozen["scope"]["variant_id"]) != recovery["state"]:
                raise HTTPException(409, "La definición o aplicación cambió desde la comparación; vuelve a probar")
        if draft.get("template") and draft["revision"] != job["draft_revision"]:
            raise HTTPException(409, "Cambió la configuración local durante la prueba; vuelve a compilar")
        if latest_publication(store, rule_id) != payload["publication_head"]:
            raise HTTPException(409, "Cambió la revisión publicada durante la prueba; vuelve a probar")
        assert_inputs_current(store, project_id, object_id, payload.get("inputs", []), payload.get("aliases", []))
        current = compile_context(store, project_id, object_id, frozen["scope"])
        assert_objects_current(store, project_id, object_id, frozen, current, publication["code"])
        if current["fingerprint"] != frozen["fingerprint"]:
            raise HTTPException(409, "El contexto cambió durante la prueba; vuelve a compilar")
        previous = store.connection.execute("SELECT id FROM component_rule_applications WHERE rule_id = ? AND variant_id = ? AND status = 'active'",
                                            (rule_id, frozen["scope"]["variant_id"])).fetchone()
        if previous and not recovery:
            raise HTTPException(409, "Desactiva la aplicación vigente antes de reemplazarla")
        event = None
        if recovery:
            from app.rule_recovery import commit_recovery
            event = commit_recovery(repository, rule_id, draft, recovery, body, actor)
        identity = uuid.uuid4().hex
        document = {"project_id": project_id, "object_id": object_id, "compilation": frozen, "code": publication["code"],
                    "name": publication["name"], "parameters": payload["parameters"], "code_hash": publication["code_hash"],
                    "instance_revision": job["draft_revision"] + int(bool(recovery)) if draft.get("template") else None,
                    "context_hash": job["context_hash"], "runtime": job["runtime"], "ir": ir, "ir_hash": digest(ir),
                    "inputs": payload.get("inputs", []),
                    "aliases": payload.get("aliases", []), "objects": payload.get("objects", []),
                    "temporal": payload.get("temporal"),
                    "windows": payload.get("windows"),
                    "template": publication.get("template"), "origin": publication.get("origin"),
                    "outputs": validate_outputs(job["result"].get("outputs", []), len(frozen["grid"])),
                    "observed_publication": payload["publication_head"], "accept_empty": body.accept_empty,
                    "observed_lifecycle": lifecycle(store, rule_id),
                    "events": [event or {"action": "apply", "actor": actor, "reason": body.reason.strip(), "at": timestamp()}]}
        store.connection.execute("INSERT INTO component_rule_applications VALUES (?, ?, ?, ?, ?, 1, 'active', ?)",
                                 (identity, rule_id, publication["id"], body.job_id, frozen["scope"]["variant_id"], encode(document)))
        response = next(item for item in list_applications(repository, rule_id) if item["id"] == identity)
        if resolving:
            store.connection.execute("INSERT INTO component_rule_resolution_requests VALUES (?, ?, ?, ?, ?)",
                                     (rule_id, actor, body.request_id, digest(body.model_dump()), encode(response)))
        return response


def assert_objects_current(store, project_id, object_id, frozen, current, code=None):
    objects = resolve_aliases(store, project_id, object_id, frozen["scope"]["scenario_id"], frozen.get("aliases", []), current["system_case"], code)
    if "objects" in frozen and objects != frozen["objects"]:
        raise HTTPException(409, "Los objetos o miembros de planta cambiaron; vuelve a probar y aplicar")


def deactivate(repository, rule_id, application_id, body, actor):
    store = repository.store
    with store._lock, store._database_transaction():
        row = store.connection.execute("SELECT * FROM component_rule_applications WHERE id = ? AND rule_id = ?", (application_id, rule_id)).fetchone()
        if row is None:
            raise HTTPException(404, "Aplicación no encontrada")
        document = json.loads(row["document"])
        document["events"].append({"action": "deactivate", "actor": actor, "reason": body.reason.strip(), "at": timestamp()})
        changed = store.connection.execute("UPDATE component_rule_applications SET status = 'inactive', revision = revision + 1, document = ? WHERE id = ? AND revision = ? AND status = 'active'",
                                            (encode(document), application_id, body.expected_revision)).rowcount
        if changed != 1:
            raise HTTPException(409, "La aplicación cambió; recarga antes de desactivar")
        return next(item for item in list_applications(repository, rule_id) if item["id"] == application_id)


def active_applications(store, *, variant_id=None, scenario_id=None):
    conditions, parameters = [], []
    if variant_id is not None:
        conditions.append("a.variant_id = ?")
        parameters.append(variant_id)
    if scenario_id is not None:
        conditions.append("c.scenario_id = ?")
        parameters.append(scenario_id)
    rows = store.connection.execute("""
        SELECT a.* FROM component_rule_applications a
        JOIN case_input_variants v ON v.id = a.variant_id
        JOIN optimization_cases c ON c.id = v.case_id
        WHERE a.status = 'active'
    """ + (" AND " + " AND ".join(conditions) if conditions else "") + " ORDER BY a.id", parameters).fetchall()
    return [decode_application(row) for row in rows]


def guard_uncompiled_run(store, *, scenario_id=None, variant_id=None):
    if active_applications(store, scenario_id=scenario_id, variant_id=variant_id):
        raise HTTPException(409, "Hay reglas activas. Ejecuta la variante desde Cálculos y restricciones; este recorrido todavía no las soporta.")


def has_run_request(store, variant_id, actor_id, request_id):
    return store.connection.execute(
        "SELECT run_id FROM component_rule_run_requests WHERE variant_id = ? AND actor = ? AND request_id = ?",
        (variant_id, actor_id, request_id),
    ).fetchone() is not None


def guard_version_run(store, version, trigger_type):
    block = version["system_case_json"].get("component_rules")
    if block is None:
        guard_uncompiled_run(store, scenario_id=version["scenario_id"])
        return
    from app.rule_ir import IR_VERSION, HYDRAULIC_IR_VERSION, TEMPORAL_IR_VERSION, BUDGET_IR_VERSION
    project = store.get_scenario(version["scenario_id"])["project_id"]
    if trigger_type != "manual" or not project_enabled(project):
        raise HTTPException(409, "Este recorrido no permite ejecutar las reglas del snapshot")
    if block.get("version") not in {IR_VERSION, HYDRAULIC_IR_VERSION, TEMPORAL_IR_VERSION, BUDGET_IR_VERSION} or version["generation_metadata"].get("component_rules_hash") != digest(block):
        raise HTTPException(409, "El snapshot de reglas no fue materializado con el contrato soportado")
    if any(item["runtime"]["sdk"] != SDK_VERSION for item in block.get("applications", [])):
        raise HTTPException(409, "El SDK del snapshot no está soportado")


def materialize_run(repository, scope, actor, request_id, validate_text, expected_bindings_revision=None):
    from app.persistence import extract_system_case_metadata
    from app.rule_ir import IR_VERSION, HYDRAULIC_IR_VERSION, TEMPORAL_IR_VERSION, BUDGET_IR_VERSION
    store = repository.store
    scenario = store.get_scenario(scope["scenario_id"])
    project_id = scenario["project_id"]
    request_hash = digest({"scope": scope, "bindings_revision": expected_bindings_revision})
    if not actor.get("id") or actor.get("role") not in {"analyst", "admin"}:
        raise HTTPException(403, "Las corridas con reglas requieren un analista autenticado")

    def replay():
        row = store.connection.execute("SELECT * FROM component_rule_run_requests WHERE variant_id = ? AND actor = ? AND request_id = ?",
                                       (scope["variant_id"], actor["id"], request_id)).fetchone()
        if row is None:
            return None
        if row["request_hash"] != request_hash:
            raise HTTPException(409, "La clave idempotente ya se usó con otro rango")
        return store.get_run(row["run_id"])

    with store._lock:
        existing = replay()
        if existing:
            return existing, False
        if not project_enabled(project_id):
            raise HTTPException(503, "Las reglas están deshabilitadas; no se pueden omitir al ejecutar")
        applications = active_applications(store, variant_id=scope["variant_id"])
        if not applications or len(applications) > 50:
            raise HTTPException(409, "Se requieren entre 1 y 50 aplicaciones activas")
        frozen = freeze_scope(store, project_id, scope, expected_bindings_revision)
        rows, objects, snapshots = [], {}, []
        runtime = repository.runtime()
        for application in applications:
            assert_instance_current(repository, application)
            assert_inputs_current(store, project_id, application["object_id"], application.get("inputs", []), application.get("aliases", []))
            if application["compilation"]["fingerprint"] != frozen["fingerprint"] or application["compilation"]["scope"] != scope:
                raise HTTPException(409, "Regla obsoleta: cambió el modelo, las entradas o el rango; vuelve a probar y aplicar con motivo")
            if latest_publication(store, application["rule_id"]) != application["observed_publication"]:
                raise HTTPException(409, "Hay una nueva revisión publicada; revalida la aplicación con motivo")
            if application["runtime"]["sdk"] != SDK_VERSION or (runtime and runtime != application["runtime"]):
                raise HTTPException(409, "El runtime cambió; vuelve a probar la regla")
            current = compile_context(store, project_id, application["object_id"], scope)
            assert_objects_current(store, project_id, application["object_id"], application["compilation"], current, application["code"])
            ir = validate_ir(application["ir"], application["object_id"], len(frozen["grid"]), application.get("objects"),
                             grid=frozen["grid"], windows=application.get("windows"), temporal=application.get("temporal"))
            if digest(ir) != application["ir_hash"] or digest(application["code"]) != application["code_hash"]:
                raise HTTPException(409, "La integridad de la regla no coincide")
            rows.extend({**row, "application_id": application["id"], "revision_id": application["publication_id"]} for row in ir["rows"])
            for obj in application.get("objects", [{"id": application["object_id"], "unit_key": application["compilation"]["unit_key"]}]):
                objects[obj["id"]] = obj
            snapshots.append({key: application[key] for key in (
                "id", "rule_id", "publication_id", "revision", "object_id", "name", "code", "parameters", "code_hash",
                "context_hash", "runtime", "ir", "ir_hash", "events", "accept_empty")}
                             | {"inputs": application.get("inputs", []), "outputs": application.get("outputs", []),
                                "temporal": application.get("temporal"),
                                "windows": application.get("windows"),
                                "template": application.get("template"), "origin": application.get("origin"),
                                "aliases": application.get("aliases", []), "objects": application.get("objects", [])})
        if len(rows) > 100000 or sum(len(row["terms"]) for row in rows) > 500000:
            raise HTTPException(422, "Cuota de restricciones excedida")
        block_version = next((v for v in (BUDGET_IR_VERSION, TEMPORAL_IR_VERSION, HYDRAULIC_IR_VERSION) if any(a["ir"]["version"] == v for a in applications)), IR_VERSION)
        block = {"version": block_version, "objects": list(objects.values()), "grid": frozen["grid"], "timezone": "UTC",
                 "rows": rows, "applications": snapshots, "context_hash": frozen["fingerprint"], "ir_hash": digest(rows)}
        document = {**frozen["system_case"], "component_rules": block}
        text = encode(document)
        if len(text.encode()) > 64 * 1024 * 1024:
            raise HTTPException(422, "Snapshot de reglas excede 64 MiB")
        application_hash = digest(applications)

    # Neither the sandbox nor Julia runs while holding a database transaction.
    validation = validate_text(text)
    if not validation.ok:
        raise HTTPException(422, validation.message)
    if block_version not in validation.payload.get("component_rule_versions", []):
        raise HTTPException(409, "El motor no declara soporte para estas reglas")

    with store._lock, snapshot_transaction(store):
        store.connection.execute("UPDATE case_input_variants SET updated_at = updated_at WHERE id = ?", (scope["variant_id"],))
        existing = replay()
        if existing:
            return existing, False
        if not project_enabled(project_id):
            raise HTTPException(409, "Las reglas se deshabilitaron durante la materialización")
        current = freeze_scope(store, project_id, scope, expected_bindings_revision)
        if current["fingerprint"] != frozen["fingerprint"] or digest(active_applications(store, variant_id=scope["variant_id"])) != application_hash:
            raise HTTPException(409, "El contexto cambió al materializar; vuelve a compilar")
        if any(latest_publication(store, item["rule_id"]) != item["observed_publication"] for item in applications):
            raise HTTPException(409, "Una regla cambió al materializar")
        for set_id in sorted({source["set_id"] for item in applications for source in item.get("inputs", [])}):
            store._lock_canonical_set(set_id)
        for item in applications:
            assert_instance_current(repository, item)
            assert_objects_current(store, project_id, item["object_id"], item["compilation"], current, item["code"])
            assert_inputs_current(store, project_id, item["object_id"], item.get("inputs", []), item.get("aliases", []))
        metadata = extract_system_case_metadata(document)
        generation = {**frozen["lineage"], "kind": "case_input_variant", "input_variant": {
                          "id": scope["variant_id"], "display_name": store.get_case_input_variant(scope["variant_id"])["display_name"]},
                      "date_range": {"start": scope["range_start"], "end": scope["range_end"]},
                      "component_rules_hash": digest(block), "request_id": request_id}
        version = store.connection.execute("""
            INSERT INTO scenario_versions (scenario_id, version_number, system_case_json, case_name, schema_version,
                period_count, asset_counts_json, validation_payload_json, generation_metadata_json, created_at, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (scope["scenario_id"], store._next_version_number(scope["scenario_id"]), text, metadata["case_name"], metadata["schema_version"],
              metadata["period_count"], encode(metadata["asset_counts"]), encode(validation.payload), encode(generation), timestamp(), actor["email"]))
        lineage = {"component_rules": [{key: item[key] for key in ("id", "name", "publication_id", "parameters", "ir_hash")}
                                       | {"windows": item.get("windows")} for item in applications],
                   "component_rules_hash": digest(block)}
        run = store.connection.execute("""INSERT INTO runs (scenario_version_id, status, created_at, triggered_by, trigger_type,
            triggered_by_user_id, triggered_by_display_name, materialized_lineage_json) VALUES (?, 'queued', ?, ?, 'manual', ?, ?, ?)""",
            (version.lastrowid, timestamp(), actor["email"], actor["id"], actor["display_name"], encode(lineage)))
        store.connection.execute("INSERT INTO component_rule_run_requests VALUES (?, ?, ?, ?, ?)",
                                 (scope["variant_id"], actor["id"], request_id, request_hash, run.lastrowid))
        return store.get_run(run.lastrowid), True
