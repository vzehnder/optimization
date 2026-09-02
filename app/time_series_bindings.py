"""Public two-phase contract helpers for canonical TS7 case bindings."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from app.time_series_associations import (
    AssociationMutationError,
    issue_prevalidation_token,
    verify_prevalidation_token,
)


BINDING_BATCH_MAX_OPERATIONS = 200

BINDING_ERROR_CATALOG = {
    "TS_BINDING_EXECUTION_BLOCKED": (
        "timeseries.binding.execution_blocked",
        "bindings",
        "La variante contiene bindings que no son ejecutables.",
    ),
    "TS_LINK_PAYLOAD_INVALID": (
        "timeseries.link.payload_invalid",
        "operations",
        "La solicitud de bindings no es valida.",
    ),
    "TS_LINK_CONFLICT": (
        "timeseries.link.conflict",
        "operations",
        "Dos operaciones compiten por el mismo binding activo.",
    ),
    "TS_LINK_BATCH_REJECTED": (
        "timeseries.link.batch_rejected",
        "operations",
        "El lote de bindings fue rechazado.",
    ),
    "TS_LINK_PRECONDITION_CHANGED": (
        "timeseries.link.precondition_changed",
        None,
        "El contexto de la variante cambio desde la prevalidacion.",
    ),
    "TS_LINK_CONFIRMATION_REQUIRED": (
        "timeseries.link.confirmation_required",
        "confirmed",
        "La operacion requiere confirmacion explicita.",
    ),
    "TS_LINK_PREVALIDATION_EXPIRED": (
        "timeseries.link.prevalidation_expired",
        "prevalidation_token",
        "La prevalidacion expiro.",
    ),
    "TS_PRECONDITION_REQUIRED": (
        "timeseries.precondition.required",
        None,
        "Falta una precondicion obligatoria.",
    ),
    "TS_IDEMPOTENCY_CONFLICT": (
        "timeseries.idempotency.key_conflict",
        "idempotency_key",
        "La clave de idempotencia ya se uso para otra solicitud.",
    ),
}


class BindingMutationError(RuntimeError):
    """Stable refusal raised by the canonical binding API."""

    def __init__(self, code: str, **context: Any):
        message_key, field, message = BINDING_ERROR_CATALOG[code]
        self.code = code
        self.message_key = message_key
        self.field = field
        self.message = message
        self.context = context
        super().__init__(f"{code}: {context}" if context else code)


def _positive_int(value: Any, *, field: str) -> int:
    if isinstance(value, bool):
        raise BindingMutationError("TS_LINK_PAYLOAD_INVALID", field=field)
    try:
        normalized = int(value)
    except (TypeError, ValueError) as error:
        raise BindingMutationError("TS_LINK_PAYLOAD_INVALID", field=field) from error
    if normalized < 1:
        raise BindingMutationError("TS_LINK_PAYLOAD_INVALID", field=field)
    return normalized


def _non_negative_int(value: Any, *, field: str) -> int:
    if isinstance(value, bool):
        raise BindingMutationError("TS_LINK_PAYLOAD_INVALID", field=field)
    try:
        normalized = int(value)
    except (TypeError, ValueError) as error:
        raise BindingMutationError("TS_LINK_PAYLOAD_INVALID", field=field) from error
    if normalized < 0:
        raise BindingMutationError("TS_LINK_PAYLOAD_INVALID", field=field)
    return normalized


def _required_text(value: Any, *, field: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise BindingMutationError("TS_LINK_PAYLOAD_INVALID", field=field)
    return normalized


def normalize_binding_request(document: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(document, Mapping):
        raise BindingMutationError("TS_LINK_PAYLOAD_INVALID", field="body")
    expected_revision = _non_negative_int(
        document.get("expected_bindings_revision"),
        field="expected_bindings_revision",
    )
    raw_operations = document.get("operations")
    if not isinstance(raw_operations, list) or not (
        1 <= len(raw_operations) <= BINDING_BATCH_MAX_OPERATIONS
    ):
        raise BindingMutationError(
            "TS_LINK_PAYLOAD_INVALID",
            field="operations",
            maximum=BINDING_BATCH_MAX_OPERATIONS,
        )
    operations = []
    client_ids: set[str] = set()
    for index, raw in enumerate(raw_operations):
        if not isinstance(raw, Mapping):
            raise BindingMutationError(
                "TS_LINK_PAYLOAD_INVALID", field=f"operations[{index}]"
            )
        client_operation_id = _required_text(
            raw.get("client_operation_id"),
            field=f"operations[{index}].client_operation_id",
        )
        if client_operation_id in client_ids:
            raise BindingMutationError(
                "TS_LINK_PAYLOAD_INVALID",
                field=f"operations[{index}].client_operation_id",
                reason="duplicate",
            )
        client_ids.add(client_operation_id)
        action = _required_text(raw.get("action"), field=f"operations[{index}].action")
        if action not in {
            "create",
            "replace",
            "revalidate_current",
            "revalidate_pinned",
            "remove",
            "restore",
        }:
            raise BindingMutationError(
                "TS_LINK_PAYLOAD_INVALID", field=f"operations[{index}].action"
            )
        operation = {
            "client_operation_id": client_operation_id,
            "action": action,
            "reason_code": _required_text(
                raw.get("reason_code"), field=f"operations[{index}].reason_code"
            ),
        }
        mode = None
        if action in {"create", "replace"}:
            raw_revision = raw.get("revision")
            if not isinstance(raw_revision, Mapping):
                raise BindingMutationError(
                    "TS_LINK_PAYLOAD_INVALID", field=f"operations[{index}].revision"
                )
            mode = _required_text(
                raw_revision.get("mode"), field=f"operations[{index}].revision.mode"
            )
            if mode not in {"current", "pinned"}:
                raise BindingMutationError(
                    "TS_LINK_PAYLOAD_INVALID",
                    field=f"operations[{index}].revision.mode",
                )
            operation.update(
                {
                    "linkable_object_id": _positive_int(
                        raw.get("linkable_object_id"),
                        field=f"operations[{index}].linkable_object_id",
                    ),
                    "binding_role_key": _required_text(
                        raw.get("binding_role_key"),
                        field=f"operations[{index}].binding_role_key",
                    ),
                    "signal_id": _positive_int(
                        raw.get("signal_id"),
                        field=f"operations[{index}].signal_id",
                    ),
                    "revision": {
                        "mode": mode,
                        "revision_id": _positive_int(
                            raw_revision.get("revision_id"),
                            field=f"operations[{index}].revision.revision_id",
                        ),
                        "content_hash": _required_text(
                            raw_revision.get("content_hash"),
                            field=f"operations[{index}].revision.content_hash",
                        ),
                    },
                    "catalog_association_id": (
                        None
                        if raw.get("catalog_association_id") is None
                        else _positive_int(
                            raw.get("catalog_association_id"),
                            field=f"operations[{index}].catalog_association_id",
                        )
                    ),
                }
            )
        if action in {
            "replace",
            "revalidate_current",
            "revalidate_pinned",
            "remove",
            "restore",
        }:
            operation["binding_id"] = _positive_int(
                raw.get("binding_id"), field=f"operations[{index}].binding_id"
            )
            operation["expected_lifecycle_revision"] = _positive_int(
                raw.get("expected_lifecycle_revision"),
                field=f"operations[{index}].expected_lifecycle_revision",
            )
        reason_text = str(raw.get("reason_text") or "").strip()
        if (
            mode == "pinned"
            or action in {"replace", "revalidate_pinned", "remove", "restore"}
        ) and not reason_text:
            raise BindingMutationError(
                "TS_LINK_PAYLOAD_INVALID",
                field=f"operations[{index}].reason_text",
                reason=(
                    "required_for_pinned_revision"
                    if mode == "pinned"
                    else "required_for_pinned_revalidation"
                    if action == "revalidate_pinned"
                    else "required_for_lifecycle_transition"
                    if action in {"remove", "restore"}
                    else "required_for_replace"
                ),
            )
        if reason_text:
            operation["reason_text"] = reason_text
        operations.append(operation)
    return {
        "expected_bindings_revision": expected_revision,
        "operations": operations,
    }


def binding_request_hash(document: Mapping[str, Any]) -> str:
    encoded = json.dumps(document, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def binding_commit_etag(
    normalized_request: Mapping[str, Any],
    observations: list[Mapping[str, Any]],
    *,
    scenario_id: int,
    variant_id: int,
    actor_class: str,
) -> str:
    encoded = json.dumps(
        {
            "request": normalized_request,
            "observations": observations,
            "scenario_id": int(scenario_id),
            "variant_id": int(variant_id),
            "actor_class": actor_class,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return f'"{hashlib.sha256(encoded.encode("utf-8")).hexdigest()}"'


def issue_binding_prevalidation_token(**kwargs: Any) -> tuple[str, str]:
    return issue_prevalidation_token(**kwargs)


def verify_binding_prevalidation_token(token: str, **kwargs: Any) -> dict[str, Any]:
    try:
        return verify_prevalidation_token(token, **kwargs)
    except AssociationMutationError as error:
        raise BindingMutationError(error.code, **error.context) from error


def binding_detail_etag(detail: Mapping[str, Any], *, actor_class: str) -> str:
    observed = {
        "binding_id": detail["binding_id"],
        "lifecycle_revision": detail["lifecycle_revision"],
        "state": detail["state"],
        "set_revision_id": detail["set_revision_id"],
        "bound_content_hash": detail["bound_content_hash"],
        "validation_fingerprint": detail["validation"].get(
            "compatibility_fingerprint"
        ),
        "validation_mode": detail["validation"].get("mode"),
        "observed_current_revision_id": detail["revision"].get(
            "observed_current_revision_id"
        ),
        "validated_at": detail["validation"].get("validated_at"),
        "actor_class": actor_class,
    }
    encoded = json.dumps(observed, sort_keys=True, separators=(",", ":"))
    return f'"{hashlib.sha256(encoded.encode("utf-8")).hexdigest()}"'


def binding_error_payload(error: BindingMutationError, *, request_id: str) -> dict[str, Any]:
    return {
        "error": {
            "code": error.code,
            "message_key": error.message_key,
            "message": error.message,
            "field": error.context.get("field", error.field),
            "context": error.context,
            "details": error.context.get("details", []),
        },
        "request_id": request_id,
    }
