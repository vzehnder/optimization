"""Mesa adapter over canonical object-series publication and variant bindings."""

import uuid
import json
import math

from pydantic import BaseModel, ConfigDict, Field

from app.object_time_series import ObjectSeriesError, object_series_etag
from app.optimization_mesa import MesaSeries, MesaPoint, read_mesa


class MesaEditConflict(ValueError):
    pass


class MesaEditExpected(BaseModel):
    model_config = ConfigDict(extra="forbid")
    binding_id: int
    bindings_revision: int
    revision_id: int
    content_hash: str
    source_revision_id: int


class MesaEditContext(BaseModel):
    series: MesaSeries
    expected: MesaEditExpected
    scope: str
    scope_message: str
    source_reference: str
    actor: str
    validation_rules: dict


class MesaEditPoint(MesaPoint):
    model_config = ConfigDict(extra="forbid")
    value: float = Field(strict=True, allow_inf_nan=False)


class MesaEditRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    case_id: int
    variant_id: int
    expected: MesaEditExpected
    unit: str
    points: list[MesaEditPoint] = Field(min_length=1)
    confirm: bool = False
    reason: str = Field(min_length=1, max_length=1000)


def _edit_source(store, *, scenario_id, case_id, variant_id, object_id, signal_key):
    mesa = read_mesa(store, scenario_id=scenario_id, case_id=case_id, variant_id=variant_id)
    component = next((c for c in mesa["components"] if c["linkable_object_id"] == object_id), None)
    if component is None:
        raise KeyError("El componente no pertenece a este caso.")
    series = next((s for s in [component["series"], *component.get("additional_series", [])]
                   if s["signal_key"] == signal_key), None)
    if not series or series.get("role", "input") != "input" or not series.get("revision_id"):
        raise ValueError("Esta serie es de solo lectura; requiere una entrada canónica vigente.")
    collection = store.read_case_bindings(scenario_id=scenario_id, variant_id=variant_id)
    binding = next((b for b in collection["items"] if b["status"] == "active"
                    and b["object"]["id"] == object_id and b["signal"]["id"] == series["signal_id"]), None)
    if binding and binding["state"] == "stale":
        raise MesaEditConflict("La fuente cambió desde la preparación. Revisa y revalida su vínculo desde Datos antes de editar.")
    if not binding or binding["state"] != "valid_current" or series["status"] != "available":
        raise ValueError("Entrada de solo lectura: revisa su vínculo, vigencia y cobertura desde Datos.")
    project_id = mesa["context"]["project_id"]
    try:
        local = store.read_object_series(project_id=project_id, linkable_object_id=object_id, signal_id=series["signal_id"])
    except ObjectSeriesError:
        local = None
    if local:
        revision = store.read_canonical_revision(local["current_revision"]["revision_id"], with_values=False)
        classification = local["classification"]
        descriptor = next(s for s in store.get_time_series_classification_catalog()["time_series_semantic_types"]
                          if s["semantic_key"] == classification["semantic_type_key"])
        catalog = {
            "contract": {"semantic_type": {"key": classification["semantic_type_key"], "validation_rules": json.loads(descriptor["validation_rules_json"])},
                         "unit": {"key": classification["unit_key"]}, "data_class": {"key": classification["data_class_key"]}},
            "coverage_summary": local["temporal_contract"],
            "current_revision": {"id": revision["id"], "created_by": revision["created_by"]},
            "link_summary": {"binding_count": store.read_object_series_binding_impact(project_id=project_id,
                             linkable_object_id=object_id, signal_id=local["signal_id"])["will_become_stale"], "association_count": 0},
        }
    else:
        catalog = store.read_catalog_input_detail(series["signal_id"])
    reference = f"mesa:scenario:{scenario_id}:variant:{variant_id}:object:{object_id}:signal:{signal_key}"
    reusable = (local and local["metadata"].get("external_reference") == reference
                and catalog["link_summary"]["binding_count"] == 1
                and catalog["link_summary"]["association_count"] == 0)
    context = {
        "series": series,
        "expected": {"binding_id": binding["binding_id"], "bindings_revision": collection["meta"]["bindings_revision"],
                     "revision_id": series["revision_id"], "content_hash": series["content_hash"],
                     "source_revision_id": catalog["current_revision"]["id"]},
        "scope": "local_revision" if reusable else "local_copy",
        "scope_message": ("Se publicará una revisión de la copia local y se actualizará esta variante."
                          if reusable else "La fuente puede ser compartida. Se creará una copia local del objeto para esta variante; los demás consumidores conservarán su fuente."),
        "source_reference": (local["metadata"].get("external_reference", "") if local
                             else catalog.get("provenance", {}).get("source_key") or f"catalog:signal:{series['signal_id']}:revision:{series['revision_id']}"),
        "target_reference": reference,
        "actor": catalog["current_revision"]["created_by"],
        "validation_rules": catalog["contract"]["semantic_type"]["validation_rules"],
    }
    return context, binding, catalog, local if reusable else None, project_id


def read_edit_context(store, **context):
    return _edit_source(store, **context)[0]


def save_edit(store, *, scenario_id, object_id, signal_key, payload, actor_user):
    context, binding, catalog, local, project_id = _edit_source(store, scenario_id=scenario_id,
        case_id=payload.case_id, variant_id=payload.variant_id, object_id=object_id, signal_key=signal_key)
    if payload.expected.model_dump() != context["expected"]:
        raise MesaEditConflict("La entrada cambió desde que abriste la edición. Recarga y compara antes de guardar.")
    if payload.unit != context["series"]["unit"]:
        raise ValueError("La unidad debe coincidir con la señal; no se convierten valores implícitamente.")
    if not payload.confirm or not payload.reason.strip():
        raise ValueError("Confirma el alcance de la edición e indica un motivo antes de guardar.")
    if [(p.start, p.end) for p in payload.points] != [(p["start"], p["end"]) for p in context["series"]["points"]]:
        raise ValueError("La tabla debe conservar todos los intervalos y la cobertura de la revisión; solo se editan valores.")
    rules = context["validation_rules"]
    for index, point in enumerate(payload.points, start=1):
        if (not math.isfinite(point.value)
                or ("minimum" in rules and point.value < rules["minimum"])
                or ("maximum" in rules and point.value > rules["maximum"])):
            raise ObjectSeriesError("TS_INGEST_VALIDATION_FAILED",
                detail=f"Valor inválido en intervalo {index}: respeta los límites de la señal {rules} ({payload.unit}).")
    actor = actor_user["email"]
    root = dict(project_id=project_id, linkable_object_id=object_id)
    if local is None:
        contract = catalog["contract"]
        coverage = catalog["coverage_summary"]
        local = store.create_object_series_definition(**root, actor=actor, document={
            "object_series_key": f"mesa_{uuid.uuid4().hex}",
            "display_name": context["series"]["name"],
            "intended_binding_role_key": binding["binding_role"]["key"],
            "semantic_type_key": contract["semantic_type"]["key"], "unit_key": contract["unit"]["key"],
            "data_class_key": contract["data_class"]["key"], "timezone": context["series"]["timezone"],
            "temporal_contract": {"regularity": coverage["regularity"],
                                  "nominal_resolution_seconds": coverage["nominal_resolution_seconds"],
                                  "timestamp_convention": "period_start"},
            "source_expectation": {"kind": "manual", "display_name": "Edición en mesa"},
            "metadata": {"external_reference": context["target_reference"],
                         "notes": f"Copia de señal {context['series']['signal_id']}, revisión {context['series']['revision_id']}, {context['series']['content_hash']}"},
        })
    key = local["object_series_key"]
    target = dict(**root, signal_id=local["signal_id"])
    ingestion = store.prepare_object_series_points_ingestion(**target, actor=actor, document={
        "mode": "replace_full", "expected_base": local["current_revision"],
        "source": {"kind": "api", "display_name": "Edición manual en mesa", "external_reference": context["target_reference"]},
        "points": [{"timestamp_start": p.start, "timestamp_end": p.end, "values": {key: p.value}} for p in payload.points],
    })
    publication, _ = store.publish_object_series_ingestion(**target, actor=actor,
        ingestion_key=ingestion["ingestion_id"], validation_token=ingestion["validation_token"],
        confirm=True, reason_code="mesa_input_edited", reason_text=payload.reason,
        if_match=object_series_etag(signal_id=local["signal_id"], resource_version=local["resource_version"]),
        idempotency_key=f"mesa-{ingestion['ingestion_id']}")
    document = {"expected_bindings_revision": context["expected"]["bindings_revision"], "operations": [{
        "client_operation_id": "mesa-edit", "action": "replace", "binding_id": binding["binding_id"],
        "expected_lifecycle_revision": binding["lifecycle_revision"], "linkable_object_id": object_id,
        "binding_role_key": binding["binding_role"]["key"], "signal_id": local["signal_id"],
        "revision": {"mode": "current", "revision_id": publication["revision_id"], "content_hash": publication["content_hash"]},
        "catalog_association_id": None, "reason_code": "mesa_input_edited", "reason_text": payload.reason,
    }]}
    preview = store.prevalidate_case_binding_batch(scenario_id=scenario_id, variant_id=payload.variant_id,
                                                   document=document, actor_class="internal")
    store.commit_case_binding_batch(scenario_id=scenario_id, variant_id=payload.variant_id, document=document,
        actor_user=actor_user, actor_class="internal", request_id=f"mesa-{ingestion['ingestion_id']}",
        prevalidation_token=preview["prevalidation_token"], if_match=preview["commit_etag"],
        idempotency_key=f"mesa-{ingestion['ingestion_id']}", confirmed=True)
    return {"revision_id": publication["revision_id"], "preparation_status": "pending_validation"}
