"""Pure HTTP-contract helpers for TS7 catalog association mutations."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from datetime import datetime, timezone
from typing import Any, Mapping


PREVALIDATION_LIFETIME_SECONDS = 5 * 60
ASSOCIATION_BATCH_MAX_OPERATIONS = 200


ASSOCIATION_ERROR_CATALOG = {
    "TS_COMPAT_SCOPE_NOT_ACCESSIBLE": (
        "timeseries.compatibility.scope_not_accessible",
        "signal_id",
        "La fuente no es accesible en este contexto.",
    ),
    "TS_LINK_PAYLOAD_INVALID": (
        "timeseries.link.payload_invalid",
        "operations",
        "La solicitud de asociaciones no es valida.",
    ),
    "TS_LINK_CONFLICT": (
        "timeseries.link.conflict",
        "operations",
        "Dos operaciones compiten por la misma asociacion activa.",
    ),
    "TS_LINK_BATCH_REJECTED": (
        "timeseries.link.batch_rejected",
        "operations",
        "El lote de asociaciones fue rechazado.",
    ),
    "TS_LINK_PRECONDITION_CHANGED": (
        "timeseries.link.precondition_changed",
        None,
        "El catalogo cambio desde la prevalidacion.",
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


class AssociationMutationError(RuntimeError):
    """Stable refusal raised by the two-phase association contract."""

    def __init__(self, code: str, **context: Any):
        message_key, field, message = ASSOCIATION_ERROR_CATALOG[code]
        self.code = code
        self.message_key = message_key
        self.field = field
        self.message = message
        self.context = context
        super().__init__(f"{code}: {context}" if context else code)


def _positive_int(value: Any, *, field: str) -> int:
    if isinstance(value, bool):
        raise AssociationMutationError("TS_LINK_PAYLOAD_INVALID", field=field)
    try:
        normalized = int(value)
    except (TypeError, ValueError) as error:
        raise AssociationMutationError(
            "TS_LINK_PAYLOAD_INVALID", field=field
        ) from error
    if normalized < 1:
        raise AssociationMutationError("TS_LINK_PAYLOAD_INVALID", field=field)
    return normalized


def _required_text(value: Any, *, field: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise AssociationMutationError("TS_LINK_PAYLOAD_INVALID", field=field)
    return normalized


def normalize_association_request(document: Mapping[str, Any]) -> dict[str, Any]:
    """Return the one canonical representation signed by both phases."""

    if not isinstance(document, Mapping):
        raise AssociationMutationError("TS_LINK_PAYLOAD_INVALID", field="body")
    target_project_id = _positive_int(
        document.get("target_project_id"), field="target_project_id"
    )
    raw_operations = document.get("operations")
    if not isinstance(raw_operations, list) or not (
        1 <= len(raw_operations) <= ASSOCIATION_BATCH_MAX_OPERATIONS
    ):
        raise AssociationMutationError(
            "TS_LINK_PAYLOAD_INVALID",
            field="operations",
            maximum=ASSOCIATION_BATCH_MAX_OPERATIONS,
        )

    operations: list[dict[str, Any]] = []
    client_ids: set[str] = set()
    for index, raw in enumerate(raw_operations):
        if not isinstance(raw, Mapping):
            raise AssociationMutationError(
                "TS_LINK_PAYLOAD_INVALID", field=f"operations[{index}]"
            )
        client_operation_id = _required_text(
            raw.get("client_operation_id"),
            field=f"operations[{index}].client_operation_id",
        )
        if client_operation_id in client_ids:
            raise AssociationMutationError(
                "TS_LINK_PAYLOAD_INVALID",
                field=f"operations[{index}].client_operation_id",
                reason="duplicate",
            )
        client_ids.add(client_operation_id)
        action = _required_text(
            raw.get("action"), field=f"operations[{index}].action"
        )
        if action not in {"add", "replace", "archive", "revalidate"}:
            raise AssociationMutationError(
                "TS_LINK_PAYLOAD_INVALID", field=f"operations[{index}].action"
            )
        operation: dict[str, Any] = {
            "client_operation_id": client_operation_id,
            "action": action,
        }
        if action in {"add", "replace"}:
            for field in ("signal_id", "linkable_object_id"):
                operation[field] = _positive_int(
                    raw.get(field), field=f"operations[{index}].{field}"
                )
            operation["binding_role_key"] = _required_text(
                raw.get("binding_role_key"),
                field=f"operations[{index}].binding_role_key",
            )
        if action == "add":
            if raw.get("expected_absent") is not True:
                raise AssociationMutationError(
                    "TS_LINK_PAYLOAD_INVALID",
                    field=f"operations[{index}].expected_absent",
                )
            operation["expected_absent"] = True
        if action in {"replace", "archive", "revalidate"}:
            operation["association_id"] = _positive_int(
                raw.get("association_id"),
                field=f"operations[{index}].association_id",
            )
            operation["expected_lifecycle_revision"] = _positive_int(
                raw.get("expected_lifecycle_revision"),
                field=f"operations[{index}].expected_lifecycle_revision",
            )
        reason_code = _required_text(
            raw.get("reason_code"),
            field=f"operations[{index}].reason_code",
        )
        reason_text = str(raw.get("reason_text") or "").strip()
        if action == "archive" and not reason_text:
            raise AssociationMutationError(
                "TS_LINK_PAYLOAD_INVALID",
                field=f"operations[{index}].reason_text",
                reason="required_for_archive",
            )
        operation["reason_code"] = reason_code
        if reason_text:
            operation["reason_text"] = reason_text
        operations.append(operation)
    return {"target_project_id": target_project_id, "operations": operations}


def association_request_hash(document: Mapping[str, Any]) -> str:
    encoded = json.dumps(document, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def association_commit_etag(
    normalized_request: Mapping[str, Any],
    observations: list[Mapping[str, Any]],
    *,
    actor_class: str,
) -> str:
    encoded = json.dumps(
        {
            "request": normalized_request,
            "observations": observations,
            "actor_class": actor_class,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return f'"{hashlib.sha256(encoded.encode("utf-8")).hexdigest()}"'


def issue_prevalidation_token(
    *,
    request_hash: str,
    commit_etag: str,
    actor_class: str,
    secret: bytes,
) -> tuple[str, str]:
    issued_at = int(time.time())
    expires_at = issued_at + PREVALIDATION_LIFETIME_SECONDS
    payload = {
        "request_hash": request_hash,
        "commit_etag": commit_etag,
        "actor_class": actor_class,
        "issued_at": issued_at,
        "expires_at": expires_at,
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    signature = hmac.new(secret, raw, hashlib.sha256).digest()
    token = ".".join(
        (
            base64.urlsafe_b64encode(raw).decode("ascii").rstrip("="),
            base64.urlsafe_b64encode(signature).decode("ascii").rstrip("="),
        )
    )
    expiry = datetime.fromtimestamp(expires_at, timezone.utc).isoformat(timespec="seconds")
    return token, expiry


def _decode_base64url(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode((value + padding).encode("ascii"))


def verify_prevalidation_token(
    token: str,
    *,
    request_hash: str,
    commit_etag: str,
    actor_class: str,
    secret: bytes,
    check_expiry: bool = True,
) -> dict[str, Any]:
    """Verify signature, actor, request, ETag and the five-minute lifetime."""

    try:
        encoded_payload, encoded_signature = str(token).split(".", 1)
        raw = _decode_base64url(encoded_payload)
        signature = _decode_base64url(encoded_signature)
        expected_signature = hmac.new(secret, raw, hashlib.sha256).digest()
        if not hmac.compare_digest(signature, expected_signature):
            raise ValueError("signature")
        payload = json.loads(raw.decode("utf-8"))
    except (ValueError, TypeError, UnicodeError, json.JSONDecodeError) as error:
        raise AssociationMutationError(
            "TS_LINK_PRECONDITION_CHANGED", reason="token_mismatch"
        ) from error
    if check_expiry and int(payload.get("expires_at", 0)) < int(time.time()):
        raise AssociationMutationError("TS_LINK_PREVALIDATION_EXPIRED")
    expected = {
        "request_hash": request_hash,
        "commit_etag": commit_etag,
        "actor_class": actor_class,
    }
    if any(payload.get(key) != value for key, value in expected.items()):
        raise AssociationMutationError(
            "TS_LINK_PRECONDITION_CHANGED", reason="token_context_mismatch"
        )
    return payload


def association_detail_etag(detail: Mapping[str, Any], *, actor_class: str) -> str:
    observed = {
        "association_id": detail["association_id"],
        "lifecycle_revision": detail["lifecycle_revision"],
        "state": detail["state"],
        "compatibility_fingerprint": detail["validation"][
            "compatibility_fingerprint"
        ],
        "actor_class": actor_class,
    }
    encoded = json.dumps(observed, sort_keys=True, separators=(",", ":"))
    return f'"{hashlib.sha256(encoded.encode("utf-8")).hexdigest()}"'


def association_error_payload(
    error: AssociationMutationError, *, request_id: str
) -> dict[str, Any]:
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
