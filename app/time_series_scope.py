"""HTTP-contract primitives for TS7 administrative scope changes."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from datetime import datetime, timezone
from typing import Any


SCOPE_ERROR_CATALOG = {
    "TS_SCOPE_ADMIN_REQUIRED": (
        "timeseries.scope.admin_required",
        None,
        "El cambio de alcance requiere un administrador activo.",
    ),
    "TS_SCOPE_CONFIRMATION_REQUIRED": (
        "timeseries.scope.confirmation_required",
        "confirmed",
        "El cambio de alcance requiere confirmacion explicita.",
    ),
    "TS_SCOPE_PRECONDITION_CHANGED": (
        "timeseries.scope.precondition_changed",
        None,
        "El set o su impacto cambiaron desde la prevalidacion.",
    ),
    "TS_SCOPE_ALREADY_EFFECTIVE": (
        "timeseries.scope.already_effective",
        "target_scope",
        "El alcance solicitado ya esta vigente.",
    ),
    "TS_SCOPE_INVALID_STATE": (
        "timeseries.scope.invalid_state",
        None,
        "El set no admite el cambio de alcance solicitado.",
    ),
    "TS_SCOPE_PREVALIDATION_EXPIRED": (
        "timeseries.scope.prevalidation_expired",
        "prevalidation_token",
        "La prevalidacion de alcance expiro.",
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

SCOPE_PREVALIDATION_LIFETIME_SECONDS = 5 * 60


class ScopeMutationError(RuntimeError):
    """Stable refusal raised by the two-phase scope-change contract."""

    def __init__(self, code: str, **context: Any):
        message_key, field, message = SCOPE_ERROR_CATALOG[code]
        self.code = code
        self.message_key = message_key
        self.field = field
        self.message = message
        self.context = context
        super().__init__(f"{code}: {context}" if context else code)


def scope_error_payload(error: ScopeMutationError, *, request_id: str) -> dict[str, Any]:
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


def scope_request_hash(document: dict[str, Any]) -> str:
    encoded = json.dumps(document, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def scope_commit_etag(impact: dict[str, Any], *, actor_class: str) -> str:
    encoded = json.dumps(
        {"impact": impact, "actor_class": actor_class},
        sort_keys=True,
        separators=(",", ":"),
    )
    return f'"{hashlib.sha256(encoded.encode("utf-8")).hexdigest()}"'


def issue_scope_prevalidation_token(
    *, request_hash: str, commit_etag: str, actor_class: str, secret: bytes
) -> tuple[str, str]:
    issued_at = int(time.time())
    expires_at = issued_at + SCOPE_PREVALIDATION_LIFETIME_SECONDS
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


def verify_scope_prevalidation_token(
    token: str,
    *,
    request_hash: str,
    commit_etag: str,
    actor_class: str,
    secret: bytes,
    check_expiry: bool = True,
) -> dict[str, Any]:
    try:
        encoded_payload, encoded_signature = str(token).split(".", 1)
        raw = _decode_base64url(encoded_payload)
        signature = _decode_base64url(encoded_signature)
        expected_signature = hmac.new(secret, raw, hashlib.sha256).digest()
        if not hmac.compare_digest(signature, expected_signature):
            raise ValueError("signature")
        payload = json.loads(raw.decode("utf-8"))
    except (ValueError, TypeError, UnicodeError, json.JSONDecodeError) as error:
        raise ScopeMutationError(
            "TS_SCOPE_PRECONDITION_CHANGED", reason="token_mismatch"
        ) from error
    if check_expiry and int(payload.get("expires_at", 0)) < int(time.time()):
        raise ScopeMutationError("TS_SCOPE_PREVALIDATION_EXPIRED")
    expected = {
        "request_hash": request_hash,
        "commit_etag": commit_etag,
        "actor_class": actor_class,
    }
    if any(payload.get(key) != value for key, value in expected.items()):
        raise ScopeMutationError(
            "TS_SCOPE_PRECONDITION_CHANGED", reason="token_context_mismatch"
        )
    return payload
