"""Trusted operational contexts for the common rule materializer.

Only published applications enter the worker queue. Operational callers never
supply code, aliases, pins or rule parameters.
"""
import time
import uuid
from copy import deepcopy

from fastapi import HTTPException

from app.component_rules import digest, encode, timestamp, project_enabled


def authorize_operation(store, scope, actor, operation):
    user = store.get_user(actor["id"])
    if not user["is_active"] or user["role"] != actor["role"]:
        raise HTTPException(403, "El permiso de ejecución cambió")
    if operation and operation["trigger_type"] == "operator_console":
        console = store.get_operator_console(operation["console_id"])
        location = store.get_operator_console_location(console["id"])
        if console["owned_variant_id"] != scope["variant_id"] or location["scenario_id"] != scope["scenario_id"]:
            raise HTTPException(404, "Consola fuera de la variante")
        if console["status"] != "active" or console["revision"] != operation["console_revision"]:
            raise HTTPException(409, "La configuración de la consola cambió")
        if user["role"] == "external" and not store.external_has_project_capability(
                user_id=user["id"], project_id=location["project_id"], capability="operate"):
            raise HTTPException(403, "El permiso de operación fue revocado")
        return
    if user["role"] not in {"analyst", "admin"}:
        raise HTTPException(403, "Las corridas con reglas requieren un analista autenticado")
    if operation and operation["trigger_type"] == "scheduled":
        expected = operation["schedule_state"]
        current = store.get_run_schedule(expected["id"])
        if not current["is_active"] or any(current[key] != value for key, value in expected.items()):
            raise HTTPException(409, "La programación cambió durante la materialización")


def effective_scope(repository, scope, applications, operation=None, expected_bindings_revision=None):
    from app.rule_applications import freeze_scope
    frozen = freeze_scope(repository.store, applications[0]["project_id"], scope, expected_bindings_revision,
                          object_id=applications[0]["object_id"])
    if operation and operation["trigger_type"] == "operator_console":
        effective = repository.store.materialize_operator_console_run(operation["console_id"],
            range_start=scope["range_start"], range_end=scope["range_end"],
            rule_materialized={"system_case": frozen["system_case"], "series_bindings": frozen["lineage"].get("series_bindings", [])})
        effective["lineage"]["operational_series_copies"] = repository.store.list_operator_console_series_copies(operation["console_id"])
        frozen = {**frozen, "system_case": effective["system_case"], "lineage": effective["lineage"],
                  "fingerprint": digest({"base": frozen["fingerprint"], **effective})}
    return frozen


def operational_validation(repository, application):
    from app.rule_applications import validation_details, compile_context
    details = validation_details(repository, application)
    if details["validation_status"] == "valid" or any(c["code"] not in {"RULE_CONTEXT_CHANGED", "RULE_OBJECT_CHANGED"}
                                                   for c in details["validation_causes"]):
        return details
    store = repository.store
    owner = store.connection.execute("SELECT id FROM operator_consoles WHERE owned_variant_id = ?", (application["variant_id"],)).fetchone()
    if owner is None:
        return details
    console = store.get_operator_console(owner["id"])
    copies = {c["time_series_set_id"]: c for c in store.list_operator_console_series_copies(console["id"])}
    columns = [c for g in console["document"]["groups"] for c in g["columns"]]
    old = application["compilation"]
    current = compile_context(store, application["project_id"], application["object_id"], old["scope"])
    def coordinate(binding):
        return (binding.get("signal_key"), binding.get("entity_type"), binding.get("entity_id"))
    before = {coordinate(b): b for b in old["lineage"].get("series_bindings", [])}
    after = {coordinate(b): b for b in current["lineage"].get("series_bindings", [])}
    if before.keys() != after.keys():
        return details
    changed = [key for key in before if before[key] != after[key]]
    if not changed:
        return details
    old_model, new_model = deepcopy(old["system_case"]), deepcopy(current["system_case"])
    for key in changed:
        column = next((c for c in columns if coordinate(c["signal"]) == key), None)
        copied = copies.get(after[key].get("time_series_set_id"))
        if not column or not copied or copied["archived_at"] is not None:
            return details
        allowed = {o["time_series_set_id"] for o in column["source_options"]}
        old_set = before[key].get("time_series_set_id")
        old_origin = copies.get(old_set, {}).get("origin_set_id", old_set)
        if copied["origin_set_id"] not in allowed or old_origin not in allowed:
            return details
        # Compare every unexposed datum and all physical parameters/topology.
        # Only the configured cell coordinates may differ after an audited copy.
        for model in (old_model, new_model):
            for period in model["time_series"]:
                field = period.get(key[0])
                if isinstance(field, dict):
                    field.pop(key[2], None)
                elif key[1] is None and key[2] is None:
                    period.pop(key[0], None)
                else:
                    return details
    if old_model != new_model:
        return details
    old_objects = [{k: v for k, v in o.items() if k != "known_series"} for o in old.get("objects", [])]
    from app.rule_objects import resolve_aliases
    new_objects = resolve_aliases(store, application["project_id"], application["object_id"], old["scope"]["scenario_id"],
                                 application.get("aliases", []), current["system_case"], application["code"])
    if old_objects != [{k: v for k, v in o.items() if k != "known_series"} for o in new_objects]:
        return details
    return {"validation_status": "valid", "validation_causes": []}


def assert_prepared(repository, applications):
    for application in applications:
        details = operational_validation(repository, application)
        if details["validation_status"] != "valid":
            raise HTTPException(409, {"code": "RULE_OPERATION_STALE", "message": "Revisa las reglas preparadas antes de ejecutar",
                                      "causes": details["validation_causes"]})


def prepared_summary(repository, variant_id):
    from app.rule_applications import active_applications
    from app.rule_compliance import rule_url
    with repository.store._lock:
        applications = active_applications(repository.store, variant_id=variant_id)
        items = [{"application_id": a["id"], "publication_id": a["publication_id"], "name": a["name"],
                  "rule_url": rule_url(a["project_id"], a["compilation"]["scope"]["scenario_id"], a) + f"&variant_id={variant_id}",
                  **operational_validation(repository, a)} for a in applications]
        available = not applications or (project_enabled(applications[0]["project_id"]) and repository.runtime() is not None)
        return {"ready": bool(available and all(a["validation_status"] == "valid" for a in items)),
                "runtime_available": bool(available), "items": items}


def validate_activation(repository, variant_id, actor, validate_text):
    from app.rule_applications import active_applications, materialize_run
    with repository.store._lock:
        applications = active_applications(repository.store, variant_id=variant_id)
        if not applications:
            return
        if not prepared_summary(repository, variant_id)["ready"]:
            raise HTTPException(409, "Las reglas preparadas requieren revisión o un runtime disponible")
        scope = applications[0]["compilation"]["scope"]
    materialize_run(repository, scope, actor, uuid.uuid4().hex, validate_text,
                    operation={"trigger_type": "rule_preparation", "lineage": {}}, prepare_only=True)


def compile_operation(repository, applications, frozen, actor):
    """Recompile exact pins on the trusted worker, outside a database transaction."""
    from app.rule_inputs import freeze_inputs
    from app.rule_objects import resolve_aliases
    from app.rule_ir import validate_ir, validate_outputs
    store = repository.store
    compiled = []
    for application in applications:
        with store._lock, store._database_transaction():
            store.connection.execute("UPDATE component_rule_worker SET heartbeat = heartbeat WHERE id = 1")
            runtime = repository.runtime()
            if runtime is None:
                raise HTTPException(503, "El ejecutor aislado no está disponible")
            if runtime != application["runtime"]:
                raise HTTPException(409, "El runtime cambió; vuelve a probar la regla")
            active = store.connection.execute("SELECT actor, status FROM component_rule_jobs WHERE status IN ('queued', 'running')").fetchall()
            if any(row["actor"] == actor["id"] for row in active) or sum(row["status"] == "queued" for row in active) >= 20:
                raise HTTPException(429, "Cola completa o ya tienes una compilación pendiente")
            project_id, object_id = application["project_id"], application["object_id"]
            objects = resolve_aliases(store, project_id, object_id, frozen["scope"]["scenario_id"],
                                      application.get("aliases", []), frozen["system_case"], application["code"])
            compilation = {**frozen, "objects": objects, "aliases": application.get("aliases", [])}
            compilation.update({key: application["compilation"][key] for key in ("component_key", "unit_key", "adapter")
                                if key in application["compilation"]})
            inputs = freeze_inputs(store, project_id, object_id, application.get("inputs", []), compilation)
            payload = {"code": application["code"], "parameters": application["parameters"], "runtime": runtime,
                       "object": {"id": object_id, "project_id": project_id}, "objects": objects,
                       "aliases": application.get("aliases", []), "inputs": inputs, "grid": frozen["grid"],
                       "compilation": compilation, "publication_id": application["publication_id"],
                       "temporal": application.get("temporal"), "windows": application.get("windows")}
            job_id = uuid.uuid4().hex
            store.connection.execute("INSERT INTO component_rule_snapshots VALUES (?, ?, ?, ?, ?, ?, ?)",
                (job_id, application["rule_id"], application.get("instance_revision") or 1, encode(payload),
                 application["code_hash"], digest(payload), timestamp()))
            store.connection.execute("INSERT INTO component_rule_jobs (id, actor, status, queued_at, updated_at) VALUES (?, ?, 'queued', ?, ?)",
                                    (job_id, actor["id"], time.time(), timestamp()))
        deadline = time.monotonic() + 65
        while True:
            job = repository.job(job_id, application["rule_id"], project_id, object_id)
            if job["status"] not in {"queued", "running"}:
                break
            if time.monotonic() >= deadline:
                with store._lock, store._database_transaction():
                    store.connection.execute("UPDATE component_rule_jobs SET cancel_requested = 1 WHERE id = ?", (job_id,))
                raise HTTPException(503, "Tiempo de compilación operativa agotado")
            time.sleep(0.05)
        if job["status"] != "succeeded":
            raise HTTPException(422, {"code": "RULE_OPERATION_FAILED", "job_id": job_id,
                                      "message": "No se pudo compilar la regla preparada", "error": job["result"]})
        ir = validate_ir(job["result"]["ir"], object_id, len(frozen["grid"]), objects,
                         grid=frozen["grid"], windows=application.get("windows"), temporal=application.get("temporal"))
        outputs = validate_outputs(job["result"].get("outputs", []), len(frozen["grid"]))
        if not ir["rows"] and not application["accept_empty"]:
            raise HTTPException(422, "La regla no emite restricciones en este rango")
        compiled.append({**application, "ir": ir, "ir_hash": digest(ir), "objects": objects,
                         "inputs": inputs, "outputs": outputs, "context_hash": digest(payload),
                         "compilation": compilation, "compilation_job_id": job_id})
    return compiled
