from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any


VALID_USER_ROLES = {"admin", "analyst", "client"}
INTERNAL_USER_ROLES = {"admin", "analyst"}


class AuthorizationService:
    def __init__(self, store: Any):
        self.store = store

    def user_for_session_token_hash(self, token_hash: str) -> dict[str, Any] | None:
        return self.store.get_user_for_session(token_hash)

    def require_admin(self, user: dict[str, Any] | None) -> dict[str, Any]:
        if user is None or user["role"] != "admin":
            raise PermissionError("forbidden")
        return user

    def require_internal(self, user: dict[str, Any] | None) -> dict[str, Any]:
        if user is None or user["role"] not in INTERNAL_USER_ROLES:
            raise PermissionError("forbidden")
        return user

    def require_client(self, user: dict[str, Any] | None) -> dict[str, Any]:
        if user is None or user["role"] != "client":
            raise PermissionError("forbidden")
        return user

    def require_client_project_access(self, user: dict[str, Any] | None, project_id: int) -> None:
        client_user = self.require_client(user)
        if not self.store.client_has_project_access(user_id=client_user["id"], project_id=project_id):
            raise KeyError(f"project {project_id} not found")

    def require_published_client_publication(
        self,
        user: dict[str, Any] | None,
        *,
        project_id: int,
        publication_id: int,
    ) -> dict[str, Any]:
        self.require_client_project_access(user, project_id)
        publication = self.store.get_publication(publication_id)
        if publication["project_id"] != project_id or publication["status"] != "published":
            raise KeyError(f"publication {publication_id} not found")
        return publication


def hash_password(password: str, *, iterations: int = 200_000) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return "pbkdf2_sha256${}${}${}".format(
        iterations,
        base64.urlsafe_b64encode(salt).decode("ascii"),
        base64.urlsafe_b64encode(digest).decode("ascii"),
    )


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, iterations_text, salt_text, digest_text = password_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        iterations = int(iterations_text)
        salt = base64.urlsafe_b64decode(salt_text.encode("ascii"))
        expected = base64.urlsafe_b64decode(digest_text.encode("ascii"))
    except (ValueError, TypeError):
        return False

    candidate = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(candidate, expected)


def new_session_token() -> str:
    return secrets.token_urlsafe(32)


def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def session_expires_at(*, hours: int = 12) -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat(timespec="seconds")
