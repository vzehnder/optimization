"""Isolated external forecast connector (TS-6 Decision 7).

External APIs enter the catalog exactly like files: a connector fetches a
payload and hands plain rows to the common source/set ingestion path. All
connector-specific logic (endpoint, authentication, payload parsing) lives
behind the narrow ``ForecastConnector`` interface so the concrete vendor can
be swapped without touching core series logic.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol

import httpx


class ForecastConnectorError(ValueError):
    pass


@dataclass(frozen=True)
class ForecastPayload:
    connector_id: str
    target: str
    fetched_at: str
    payload_checksum: str
    rows: list[dict[str, Any]]


class ForecastConnector(Protocol):
    def fetch(self) -> ForecastPayload: ...


@dataclass(frozen=True)
class HttpJsonForecastConnectorConfig:
    connector_id: str
    base_url: str
    records_path: str | None = None
    auth_token: str | None = None
    timeout_seconds: float = 30.0


def payload_rows_checksum(rows: list[dict[str, Any]]) -> str:
    canonical = json.dumps(rows, sort_keys=True, separators=(",", ":"))
    return f"sha256:{hashlib.sha256(canonical.encode('utf-8')).hexdigest()}"


class HttpJsonForecastConnector:
    """Config-driven HTTP+JSON connector, the only concrete implementation.

    ``transport`` exists so tests can stub the network via
    ``httpx.MockTransport``; production callers leave it as ``None``.
    """

    def __init__(
        self,
        config: HttpJsonForecastConnectorConfig,
        *,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._config = config
        self._transport = transport

    def fetch(self) -> ForecastPayload:
        config = self._config
        headers = {}
        if config.auth_token:
            headers["Authorization"] = f"Bearer {config.auth_token}"
        try:
            with httpx.Client(
                transport=self._transport, timeout=config.timeout_seconds
            ) as client:
                response = client.get(config.base_url, headers=headers)
        except httpx.HTTPError as error:
            raise ForecastConnectorError(
                f"connector {config.connector_id!r} could not reach "
                f"{config.base_url!r}: {error}"
            ) from error
        if response.status_code != 200:
            raise ForecastConnectorError(
                f"connector {config.connector_id!r} received HTTP "
                f"{response.status_code} from {config.base_url!r}"
            )
        try:
            document = response.json()
        except ValueError as error:
            raise ForecastConnectorError(
                f"connector {config.connector_id!r} received a non-JSON payload "
                f"from {config.base_url!r}"
            ) from error

        rows = _extract_records(document, config)
        return ForecastPayload(
            connector_id=config.connector_id,
            target=config.base_url,
            fetched_at=datetime.now(timezone.utc).isoformat(),
            payload_checksum=payload_rows_checksum(rows),
            rows=rows,
        )


def _extract_records(
    document: Any, config: HttpJsonForecastConnectorConfig
) -> list[dict[str, Any]]:
    records = document
    if config.records_path:
        for key in config.records_path.split("."):
            if not isinstance(records, dict) or key not in records:
                raise ForecastConnectorError(
                    f"connector {config.connector_id!r}: records_path "
                    f"{config.records_path!r} was not found in the payload"
                )
            records = records[key]
    if not isinstance(records, list) or not all(
        isinstance(record, dict) for record in records
    ):
        raise ForecastConnectorError(
            f"connector {config.connector_id!r}: expected a JSON list of "
            "records, got a different payload shape"
        )
    return [dict(record) for record in records]
