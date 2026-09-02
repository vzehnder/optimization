"""Object-specific series: definition, staging and API-points ingestion.

TS-7 chapter 7 opens a second path into the canonical content model. A series
that is born from an object reuses ``time_series_sets`` / ``signals`` /
``set_revisions`` unchanged - there is no second content hierarchy - and adds
only what the canonical root has nowhere to keep:

* ``object_series_definitions`` holds the editable identity of one local series
  (intended role, curated metadata, source expectation and temporal contract)
  plus its ``resource_version``, the strong validator of the ``If-Match`` patch.
* ``time_series_ingestions`` and its two staging children hold a validated but
  unpublished snapshot. Nothing staged is reachable by a binding: only the
  publication transaction copies it into the canonical tables (chapter 9.7).

Both live in the same physical space as the rest of the expansion: schema
``ts_next`` on PostgreSQL, a ``_next`` suffix on SQLite.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import math
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

from app.time_series_canonical import canonical_space_table_name


OBJECT_SERIES_LOGICAL_TABLES = (
    "object_series_definitions",
    "time_series_ingestions",
    "time_series_ingestion_periods",
    "time_series_ingestion_values",
)

# Chapter 7.10: the JSON channel is bounded so it can be validated inside the
# request that carries it. The file channel (TS7-011) owns the larger budgets.
API_POINTS_MAX_PERIODS = 10_000
API_POINTS_MAX_CELLS = 100_000
INGESTION_ERROR_LIMIT = 200
INGESTION_PREVIEW_MAX_ROWS = 200
INGESTION_LIFETIME_SECONDS = 24 * 60 * 60

OBJECT_SERIES_KEY_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
METADATA_MAX_BYTES = 16 * 1024
METADATA_MAX_TAGS = 20
METADATA_MAX_TAG_LENGTH = 60
METADATA_ALLOWED_KEYS = ("tags", "external_reference", "notes")

# Chapter 7.5 refuses anything that smells like a secret, a credential, a local
# path or an executable fragment inside curated metadata.
METADATA_FORBIDDEN_SUBSTRINGS = (
    "://",
    "\\\\",
    "<script",
    "${",
    "$(",
    "-----begin",
)
METADATA_FORBIDDEN_KEY_HINTS = ("password", "secret", "token", "credential", "key_file")

QUALITY_FLAGS = ("measured", "estimated", "forecast", "interpolated", "suspect")

PUBLISH_INGESTION_OPERATION_KIND = "publish_object_series_revision"


OBJECT_SERIES_ERROR_CATALOG = {
    "TS_INGEST_FORBIDDEN": (
        "https://errors.example/time-series/ingestion-forbidden",
        "Time-series ingestion is not authorized",
        403,
    ),
    "TS_OBJECT_SERIES_NOT_FOUND": (
        "https://errors.example/time-series/object-series-not-found",
        "Object series not found",
        404,
    ),
    "TS_COMPAT_PROJECT_CONTEXT_MISMATCH": (
        "https://errors.example/time-series/project-context-mismatch",
        "Object and project do not match",
        404,
    ),
    "TS_COMPAT_OBJECT_OWNER_MISMATCH": (
        "https://errors.example/time-series/object-owner-mismatch",
        "Series belongs to another object",
        404,
    ),
    "TS_OBJECT_SERIES_KEY_CONFLICT": (
        "https://errors.example/time-series/object-series-key-conflict",
        "Local series key already used",
        409,
    ),
    "TS_OBJECT_SERIES_DEFINITION_INVALID": (
        "https://errors.example/time-series/object-series-definition-invalid",
        "Object series definition is invalid",
        422,
    ),
    "TS_COMPAT_ROLE_NOT_ALLOWED": (
        "https://errors.example/time-series/compatibility-refused",
        "Type, unit, role and object are not compatible",
        422,
    ),
    "TS_INGEST_FORMAT_UNSUPPORTED": (
        "https://errors.example/time-series/ingestion-format-unsupported",
        "Ingestion format is not supported",
        415,
    ),
    "TS_INGEST_PAYLOAD_TOO_LARGE": (
        "https://errors.example/time-series/ingestion-payload-too-large",
        "Ingestion payload is too large",
        413,
    ),
    "TS_INGEST_QUOTA_EXCEEDED": (
        "https://errors.example/time-series/ingestion-quota-exceeded",
        "Ingestion exceeds its quota",
        422,
    ),
    "TS_INGEST_VALIDATION_FAILED": (
        "https://errors.example/time-series/ingestion-validation",
        "Time-series ingestion is invalid",
        422,
    ),
    "TS_INGEST_MAPPING_INVALID": (
        "https://errors.example/time-series/ingestion-mapping-invalid",
        "Ingestion mapping is missing or incomplete",
        422,
    ),
    "TS_INGEST_APPEND_CONFLICT": (
        "https://errors.example/time-series/ingestion-append-conflict",
        "Append does not continue the current coverage",
        422,
    ),
    "TS_INGEST_PRECONDITION_REQUIRED": (
        "https://errors.example/time-series/ingestion-precondition-required",
        "A required precondition is missing",
        428,
    ),
    "TS_INGEST_PRECONDITION_CHANGED": (
        "https://errors.example/time-series/ingestion-precondition-changed",
        "The observed precondition changed",
        412,
    ),
    "TS_INGEST_IDEMPOTENCY_CONFLICT": (
        "https://errors.example/time-series/ingestion-idempotency-conflict",
        "Idempotency key reused with another payload",
        409,
    ),
    "TS_INGEST_SESSION_UNAVAILABLE": (
        "https://errors.example/time-series/ingestion-session-unavailable",
        "Ingestion job expired or was cancelled",
        410,
    ),
    "TS_SHARED_REVISION_CONFIRMATION_REQUIRED": (
        "https://errors.example/time-series/shared-revision-confirmation-required",
        "The publication requires explicit confirmation",
        409,
    ),
    "TS_QUERY_INVALID": (
        "https://errors.example/time-series/query-invalid",
        "The query is not valid",
        400,
    ),
}

class ObjectSeriesError(RuntimeError):
    """Stable refusal of the object-scoped surface (chapter 7.11)."""

    def __init__(
        self,
        code: str,
        *,
        detail: str = "",
        errors: list[dict[str, Any]] | None = None,
        status: int | None = None,
        **context: Any,
    ):
        problem_type, title, default_status = OBJECT_SERIES_ERROR_CATALOG[code]
        self.code = code
        self.problem_type = problem_type
        self.title = title
        self.status = default_status if status is None else status
        self.detail = detail
        self.errors = errors or []
        self.context = context
        super().__init__(f"{code}: {context}" if context else code)


def object_series_problem(
    error: ObjectSeriesError, *, request_id: str
) -> dict[str, Any]:
    """One ``application/problem+json`` body for every channel (chapter 7.11)."""

    counts: dict[str, int] = {}
    for entry in error.errors:
        counts[entry["code"]] = counts.get(entry["code"], 0) + 1
    problem = {
        "type": error.problem_type,
        "title": error.title,
        "status": error.status,
        "code": error.code,
        "detail": error.detail or error.title,
        "request_id": request_id,
        "errors": error.errors[:INGESTION_ERROR_LIMIT],
        "error_counts": counts,
        "errors_truncated": len(error.errors) > INGESTION_ERROR_LIMIT,
    }
    if error.context:
        problem["context"] = error.context
    return problem


def object_series_etag(*, signal_id: int, resource_version: int) -> str:
    """Strong validator of one local identity (chapter 7.8)."""

    return f'"ts-object-series-{int(signal_id)}-v{int(resource_version)}"'


def normalize_object_series_key(value: Any) -> str:
    key = str(value or "").strip()
    if not OBJECT_SERIES_KEY_PATTERN.match(key) or len(key) > 96:
        raise ObjectSeriesError(
            "TS_OBJECT_SERIES_DEFINITION_INVALID",
            field="object_series_key",
            reason="key_shape",
        )
    return key


def normalize_curated_metadata(value: Any) -> dict[str, Any]:
    """Only declared keys, bounded size, and never a secret (chapter 7.5)."""

    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ObjectSeriesError(
            "TS_OBJECT_SERIES_DEFINITION_INVALID", field="metadata", reason="not_object"
        )
    unknown = sorted(set(value) - set(METADATA_ALLOWED_KEYS))
    if unknown:
        raise ObjectSeriesError(
            "TS_OBJECT_SERIES_DEFINITION_INVALID",
            field="metadata",
            reason="undeclared_keys",
            keys=unknown,
        )
    metadata: dict[str, Any] = {}
    tags = value.get("tags")
    if tags is not None:
        if not isinstance(tags, list) or len(tags) > METADATA_MAX_TAGS:
            raise ObjectSeriesError(
                "TS_OBJECT_SERIES_DEFINITION_INVALID",
                field="metadata.tags",
                reason="tag_count",
                maximum=METADATA_MAX_TAGS,
            )
        normalized_tags = []
        for tag in tags:
            text = str(tag or "").strip()
            if not text or len(text) > METADATA_MAX_TAG_LENGTH:
                raise ObjectSeriesError(
                    "TS_OBJECT_SERIES_DEFINITION_INVALID",
                    field="metadata.tags",
                    reason="tag_length",
                    maximum=METADATA_MAX_TAG_LENGTH,
                )
            normalized_tags.append(text)
        metadata["tags"] = normalized_tags
    for field in ("external_reference", "notes"):
        if value.get(field) is None:
            continue
        metadata[field] = str(value[field]).strip()

    serialized = json.dumps(metadata, sort_keys=True, ensure_ascii=False)
    if len(serialized.encode("utf-8")) > METADATA_MAX_BYTES:
        raise ObjectSeriesError(
            "TS_OBJECT_SERIES_DEFINITION_INVALID",
            field="metadata",
            reason="too_large",
            maximum=METADATA_MAX_BYTES,
        )
    lowered = serialized.lower()
    for hint in METADATA_FORBIDDEN_SUBSTRINGS:
        if hint in lowered:
            raise ObjectSeriesError(
                "TS_OBJECT_SERIES_DEFINITION_INVALID",
                field="metadata",
                reason="forbidden_content",
            )
    for hint in METADATA_FORBIDDEN_KEY_HINTS:
        if hint in lowered:
            raise ObjectSeriesError(
                "TS_OBJECT_SERIES_DEFINITION_INVALID",
                field="metadata",
                reason="forbidden_content",
            )
    return metadata


def normalize_temporal_contract(value: Any) -> dict[str, Any]:
    if value is None:
        raise ObjectSeriesError(
            "TS_OBJECT_SERIES_DEFINITION_INVALID",
            field="temporal_contract",
            reason="required",
        )
    if not isinstance(value, Mapping):
        raise ObjectSeriesError(
            "TS_OBJECT_SERIES_DEFINITION_INVALID",
            field="temporal_contract",
            reason="not_object",
        )
    regularity = str(value.get("regularity") or "").strip()
    if regularity not in {"regular", "irregular"}:
        raise ObjectSeriesError(
            "TS_OBJECT_SERIES_DEFINITION_INVALID",
            field="temporal_contract.regularity",
        )
    convention = str(value.get("timestamp_convention") or "period_start").strip()
    if convention not in {"period_start", "period_end"}:
        raise ObjectSeriesError(
            "TS_OBJECT_SERIES_DEFINITION_INVALID",
            field="temporal_contract.timestamp_convention",
        )
    resolution = value.get("nominal_resolution_seconds")
    if regularity == "regular":
        try:
            resolution = float(resolution)
        except (TypeError, ValueError) as error:
            raise ObjectSeriesError(
                "TS_OBJECT_SERIES_DEFINITION_INVALID",
                field="temporal_contract.nominal_resolution_seconds",
            ) from error
        if not resolution > 0:
            raise ObjectSeriesError(
                "TS_OBJECT_SERIES_DEFINITION_INVALID",
                field="temporal_contract.nominal_resolution_seconds",
            )
    else:
        resolution = None if resolution is None else float(resolution)
    return {
        "regularity": regularity,
        "nominal_resolution_seconds": resolution,
        "timestamp_convention": convention,
    }


def normalize_source_expectation(value: Any) -> dict[str, Any]:
    """Interface help and policy - never executable provenance (chapter 7.5)."""

    if value is None:
        return {"kind": "api", "display_name": ""}
    if not isinstance(value, Mapping):
        raise ObjectSeriesError(
            "TS_OBJECT_SERIES_DEFINITION_INVALID",
            field="source_expectation",
            reason="not_object",
        )
    forbidden = sorted(
        {"stored_path", "created_by", "checksum"} & set(value)
    )
    if forbidden:
        raise ObjectSeriesError(
            "TS_OBJECT_SERIES_DEFINITION_INVALID",
            field="source_expectation",
            reason="server_owned_fields",
            keys=forbidden,
        )
    kind = str(value.get("kind") or "api").strip()
    if kind not in {"api", "csv", "xlsx", "manual"}:
        raise ObjectSeriesError(
            "TS_OBJECT_SERIES_DEFINITION_INVALID", field="source_expectation.kind"
        )
    return {
        "kind": kind,
        "display_name": str(value.get("display_name") or "").strip(),
    }


def object_series_schema_statements(backend: str) -> list[str]:
    """Additive DDL for the definition and its staging tables."""

    postgres = backend == "postgresql"
    identity = (
        "BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY"
        if postgres
        else "INTEGER PRIMARY KEY AUTOINCREMENT"
    )
    reference = "BIGINT" if postgres else "INTEGER"
    double = "DOUBLE PRECISION" if postgres else "REAL"
    empty_json = "'{}'"
    table = object_series_table_names(backend)
    canonical = {
        logical: canonical_space_table_name(logical, backend)
        for logical in (
            "time_series_sets",
            "time_series_signals",
            "time_series_set_revisions",
            "linkable_objects",
        )
    }

    statements = [
        f"""
        CREATE TABLE IF NOT EXISTS {table['object_series_definitions']} (
            time_series_set_id {reference} PRIMARY KEY
                REFERENCES {canonical['time_series_sets']}(id),
            signal_id {reference} NOT NULL,
            owner_linkable_object_id {reference} NOT NULL,
            owner_project_id {reference} NOT NULL REFERENCES projects(id),
            object_series_key TEXT NOT NULL,
            intended_binding_role_id {reference} NOT NULL
                REFERENCES time_series_binding_roles(id),
            semantic_type_id {reference} NOT NULL
                REFERENCES time_series_semantic_types(id),
            unit_id {reference} NOT NULL REFERENCES measurement_units(id),
            data_class_id {reference} NOT NULL
                REFERENCES time_series_data_classes(id),
            aggregation TEXT NOT NULL,
            timezone TEXT NOT NULL,
            regularity TEXT NOT NULL,
            nominal_resolution_seconds {double},
            timestamp_convention TEXT NOT NULL DEFAULT 'period_start',
            source_expectation_json TEXT NOT NULL DEFAULT {empty_json},
            metadata_json TEXT NOT NULL DEFAULT {empty_json},
            resource_version INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            created_by TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            updated_by TEXT NOT NULL,
            CHECK (regularity IN ('regular', 'irregular')),
            CHECK (timestamp_convention IN ('period_start', 'period_end')),
            CHECK (resource_version > 0),
            CONSTRAINT ts7_object_series_owner_key_uk
                UNIQUE (owner_linkable_object_id, object_series_key),
            FOREIGN KEY (time_series_set_id, owner_linkable_object_id)
                REFERENCES {canonical['time_series_sets']}
                (id, owner_linkable_object_id),
            FOREIGN KEY (time_series_set_id, owner_project_id)
                REFERENCES {canonical['time_series_sets']}(id, owner_project_id),
            FOREIGN KEY (signal_id, time_series_set_id)
                REFERENCES {canonical['time_series_signals']}
                (id, time_series_set_id),
            FOREIGN KEY (owner_linkable_object_id, owner_project_id)
                REFERENCES {canonical['linkable_objects']}(id, project_id)
        )
        """,
        f"""
        CREATE TABLE IF NOT EXISTS {table['time_series_ingestions']} (
            id {identity},
            ingestion_key TEXT NOT NULL UNIQUE,
            project_id {reference} NOT NULL REFERENCES projects(id),
            linkable_object_id {reference} NOT NULL
                REFERENCES {canonical['linkable_objects']}(id),
            time_series_set_id {reference} NOT NULL
                REFERENCES {canonical['time_series_sets']}(id),
            signal_id {reference} NOT NULL,
            target_kind TEXT NOT NULL,
            channel TEXT NOT NULL,
            state TEXT NOT NULL,
            mode TEXT NOT NULL,
            actor TEXT NOT NULL,
            base_revision_id {reference}
                REFERENCES {canonical['time_series_set_revisions']}(id),
            base_content_hash TEXT,
            contract_json TEXT NOT NULL DEFAULT {empty_json},
            source_json TEXT NOT NULL DEFAULT {empty_json},
            mapping_json TEXT NOT NULL DEFAULT {empty_json},
            submitted_json TEXT NOT NULL DEFAULT '[]',
            normalized_json TEXT NOT NULL DEFAULT {empty_json},
            validation_json TEXT NOT NULL DEFAULT {empty_json},
            payload_checksum TEXT NOT NULL DEFAULT '',
            content_hash TEXT,
            published_revision_id {reference}
                REFERENCES {canonical['time_series_set_revisions']}(id),
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            CHECK (target_kind IN ('object_specific', 'catalog_shared')),
            CHECK (channel IN ('api_points', 'file_csv', 'file_xlsx')),
            CHECK (mode IN ('replace_full', 'append_tail')),
            CHECK (state IN (
                'awaiting_mapping', 'invalid', 'ready_to_publish',
                'published', 'cancelled'
            )),
            FOREIGN KEY (signal_id, time_series_set_id)
                REFERENCES {canonical['time_series_signals']}
                (id, time_series_set_id),
            FOREIGN KEY (linkable_object_id, project_id)
                REFERENCES {canonical['linkable_objects']}(id, project_id)
        )
        """,
        f"""
        CREATE TABLE IF NOT EXISTS {table['time_series_ingestion_periods']} (
            ingestion_id {reference} NOT NULL
                REFERENCES {table['time_series_ingestions']}(id) ON DELETE CASCADE,
            period_index INTEGER NOT NULL,
            timestamp_start TEXT NOT NULL,
            timestamp_end TEXT NOT NULL,
            duration_hours {double} NOT NULL,
            source_row_number INTEGER,
            PRIMARY KEY (ingestion_id, period_index),
            CHECK (duration_hours > 0),
            CHECK (timestamp_start < timestamp_end)
        )
        """,
        f"""
        CREATE TABLE IF NOT EXISTS {table['time_series_ingestion_values']} (
            ingestion_id {reference} NOT NULL
                REFERENCES {table['time_series_ingestions']}(id) ON DELETE CASCADE,
            series_key TEXT NOT NULL,
            period_index INTEGER NOT NULL,
            value_numeric {double} NOT NULL,
            quality_flag TEXT,
            source_row_number INTEGER,
            PRIMARY KEY (ingestion_id, series_key, period_index)
        )
        """,
        f"""
        CREATE INDEX IF NOT EXISTS ts7_object_series_owner_idx
            ON {table['object_series_definitions']}
            (owner_linkable_object_id, object_series_key)
        """,
        f"""
        CREATE INDEX IF NOT EXISTS ts7_ingestion_target_state_idx
            ON {table['time_series_ingestions']}
            (time_series_set_id, state, created_at DESC)
        """,
    ]
    return [statement.strip() for statement in statements]


def object_series_table_names(backend: str) -> dict[str, str]:
    return {
        logical: canonical_space_table_name(logical, backend)
        for logical in OBJECT_SERIES_LOGICAL_TABLES
    }


def new_ingestion_key() -> str:
    return f"tsi_{hashlib.sha256(str(time.time_ns()).encode()).hexdigest()[:24]}"


def ingestion_validation_token(
    *, ingestion_key: str, content_hash: str, secret: bytes
) -> str:
    digest = hmac.new(
        secret, f"{ingestion_key}:{content_hash}".encode("utf-8"), hashlib.sha256
    ).hexdigest()[:32]
    return f"tsv_{digest}"


def parse_offset_timestamp(value: Any, *, record_index: int) -> datetime:
    """RFC 3339 with a mandatory offset, normalized to UTC (chapter 7.6)."""

    text = str(value or "").strip()
    if not text:
        raise _record_error(
            "TS_INGEST_TIMESTAMP_INVALID",
            "timestamp_start is required",
            record_index=record_index,
            json_pointer=f"/points/{record_index}/timestamp_start",
        )
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as error:
        raise _record_error(
            "TS_INGEST_TIMESTAMP_INVALID",
            "timestamp_start must be RFC 3339",
            record_index=record_index,
            json_pointer=f"/points/{record_index}/timestamp_start",
        ) from error
    if parsed.tzinfo is None:
        raise _record_error(
            "TS_INGEST_TIMESTAMP_INVALID",
            "timestamp_start must carry an offset",
            record_index=record_index,
            json_pointer=f"/points/{record_index}/timestamp_start",
        )
    return parsed.astimezone(timezone.utc)


class _RecordError(Exception):
    def __init__(self, entry: dict[str, Any]):
        self.entry = entry
        super().__init__(entry["code"])


def _record_error(
    code: str, message: str, *, record_index: int, json_pointer: str
) -> _RecordError:
    return _RecordError(
        {
            "code": code,
            "message": message,
            "location": {
                "record_index": record_index,
                "json_pointer": json_pointer,
            },
        }
    )


def _utc_text(moment: datetime) -> str:
    return moment.replace(tzinfo=None).isoformat()


def normalize_points_payload(
    document: Mapping[str, Any],
    *,
    series_keys: tuple[str, ...],
    mapping: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Turn one JSON batch into the normalized snapshot, or into its errors.

    The result always carries ``errors``; the caller decides whether an invalid
    batch is staged for a mapping correction or refused outright. Nothing here
    touches the database, so a payload is fully judged before a transaction
    opens (chapter 9.7).
    """

    points = document.get("points")
    if not isinstance(points, list) or not points:
        raise ObjectSeriesError(
            "TS_INGEST_VALIDATION_FAILED",
            detail="the batch carries no point",
            errors=[
                {
                    "code": "TS_INGEST_TEMPORAL_CONTRACT_INVALID",
                    "message": "points must be a non-empty array",
                    "location": {"record_index": 0, "json_pointer": "/points"},
                }
            ],
        )
    if len(points) > API_POINTS_MAX_PERIODS:
        raise ObjectSeriesError(
            "TS_INGEST_QUOTA_EXCEEDED",
            detail="the batch exceeds the JSON channel budget",
            maximum_periods=API_POINTS_MAX_PERIODS,
        )
    if len(points) * max(len(series_keys), 1) > API_POINTS_MAX_CELLS:
        raise ObjectSeriesError(
            "TS_INGEST_QUOTA_EXCEEDED",
            detail="the batch exceeds the JSON channel budget",
            maximum_cells=API_POINTS_MAX_CELLS,
        )

    resolved_mapping = {str(key): str(value) for key, value in (mapping or {}).items()}
    errors: list[dict[str, Any]] = []
    periods: list[dict[str, Any]] = []
    values: list[dict[str, Any]] = []
    previous_end: datetime | None = None
    previous_start: datetime | None = None

    for record_index, point in enumerate(points):
        pointer = f"/points/{record_index}"
        if not isinstance(point, Mapping):
            errors.append(
                _record_error(
                    "TS_INGEST_VALUE_INVALID",
                    "each point must be an object",
                    record_index=record_index,
                    json_pointer=pointer,
                ).entry
            )
            continue
        try:
            start = parse_offset_timestamp(
                point.get("timestamp_start"), record_index=record_index
            )
        except _RecordError as error:
            errors.append(error.entry)
            continue

        has_end = point.get("timestamp_end") is not None
        has_duration = point.get("duration_seconds") is not None
        if has_end == has_duration:
            errors.append(
                _record_error(
                    "TS_INGEST_DURATION_INVALID",
                    "send exactly one of timestamp_end and duration_seconds",
                    record_index=record_index,
                    json_pointer=f"{pointer}/duration_seconds",
                ).entry
            )
            continue
        if has_end:
            try:
                end = parse_offset_timestamp(
                    point.get("timestamp_end"), record_index=record_index
                )
            except _RecordError as error:
                errors.append(error.entry)
                continue
        else:
            try:
                duration_seconds = float(point.get("duration_seconds"))
            except (TypeError, ValueError):
                errors.append(
                    _record_error(
                        "TS_INGEST_DURATION_INVALID",
                        "duration_seconds must be numeric",
                        record_index=record_index,
                        json_pointer=f"{pointer}/duration_seconds",
                    ).entry
                )
                continue
            if not duration_seconds > 0 or not math.isfinite(duration_seconds):
                errors.append(
                    _record_error(
                        "TS_INGEST_DURATION_INVALID",
                        "duration_seconds must be positive",
                        record_index=record_index,
                        json_pointer=f"{pointer}/duration_seconds",
                    ).entry
                )
                continue
            end = start + timedelta(seconds=duration_seconds)
        if end <= start:
            errors.append(
                _record_error(
                    "TS_INGEST_DURATION_INVALID",
                    "the period ends before it starts",
                    record_index=record_index,
                    json_pointer=f"{pointer}/timestamp_end",
                ).entry
            )
            continue
        ordering_failed = False
        if previous_start is not None and start <= previous_start:
            errors.append(
                _record_error(
                    "TS_INGEST_PERIOD_CONFLICT",
                    "points must arrive strictly ordered",
                    record_index=record_index,
                    json_pointer=f"{pointer}/timestamp_start",
                ).entry
            )
            ordering_failed = True
        elif previous_end is not None and start < previous_end:
            errors.append(
                _record_error(
                    "TS_INGEST_PERIOD_CONFLICT",
                    "periods overlap",
                    record_index=record_index,
                    json_pointer=f"{pointer}/timestamp_start",
                ).entry
            )
            ordering_failed = True
        # Order is judged on the submitted timestamps, even when the record is
        # dropped for another reason, so an overlap never hides behind a bad
        # value.
        previous_start = start
        previous_end = end
        if ordering_failed:
            continue

        raw_values = point.get("values")
        if not isinstance(raw_values, Mapping) or not raw_values:
            errors.append(
                _record_error(
                    "TS_INGEST_SIGNAL_SET_INCOMPLETE",
                    "values must carry one cell per active signal",
                    record_index=record_index,
                    json_pointer=f"{pointer}/values",
                ).entry
            )
            continue
        translated: dict[str, Any] = {}
        unmapped: list[str] = []
        for raw_key, cell in raw_values.items():
            series_key = resolved_mapping.get(str(raw_key), str(raw_key))
            if series_key not in series_keys:
                unmapped.append(str(raw_key))
                continue
            translated[series_key] = cell
        if unmapped:
            for raw_key in sorted(unmapped):
                errors.append(
                    _record_error(
                        "TS_INGEST_MAPPING_INVALID",
                        f"'{raw_key}' does not map to a signal of the target",
                        record_index=record_index,
                        json_pointer=f"{pointer}/values/{raw_key}",
                    ).entry
                )
            continue
        missing = [key for key in series_keys if key not in translated]
        if missing:
            for series_key in missing:
                errors.append(
                    _record_error(
                        "TS_INGEST_SIGNAL_SET_INCOMPLETE",
                        f"'{series_key}' has no value in this period",
                        record_index=record_index,
                        json_pointer=f"{pointer}/values",
                    ).entry
                )
            continue

        period_index = len(periods)
        row_values = []
        period_failed = False
        for series_key in series_keys:
            cell = translated[series_key]
            raw_value = cell.get("value") if isinstance(cell, Mapping) else cell
            quality_flag = (
                cell.get("quality_flag") if isinstance(cell, Mapping) else None
            )
            if isinstance(raw_value, bool) or isinstance(raw_value, str):
                errors.append(
                    _record_error(
                        "TS_INGEST_VALUE_INVALID",
                        "value must be a finite number",
                        record_index=record_index,
                        json_pointer=f"{pointer}/values/{series_key}/value",
                    ).entry
                )
                period_failed = True
                continue
            try:
                numeric = float(raw_value)
            except (TypeError, ValueError):
                errors.append(
                    _record_error(
                        "TS_INGEST_VALUE_INVALID",
                        "value must be a finite number",
                        record_index=record_index,
                        json_pointer=f"{pointer}/values/{series_key}/value",
                    ).entry
                )
                period_failed = True
                continue
            if not math.isfinite(numeric):
                errors.append(
                    _record_error(
                        "TS_INGEST_VALUE_INVALID",
                        "value must be finite",
                        record_index=record_index,
                        json_pointer=f"{pointer}/values/{series_key}/value",
                    ).entry
                )
                period_failed = True
                continue
            if quality_flag is not None and str(quality_flag) not in QUALITY_FLAGS:
                errors.append(
                    _record_error(
                        "TS_INGEST_VALUE_INVALID",
                        "quality_flag is not in the allowed catalog",
                        record_index=record_index,
                        json_pointer=f"{pointer}/values/{series_key}/quality_flag",
                    ).entry
                )
                period_failed = True
                continue
            row_values.append(
                {
                    "series_key": series_key,
                    "period_index": period_index,
                    "value": numeric,
                    "quality_flag": None if quality_flag is None else str(quality_flag),
                    "source_row_number": record_index + 1,
                }
            )
        if period_failed:
            continue

        periods.append(
            {
                "period_index": period_index,
                "timestamp_start": _utc_text(start),
                "timestamp_end": _utc_text(end),
                "duration_hours": (end - start).total_seconds() / 3600.0,
                "source_row_number": record_index + 1,
            }
        )
        values.extend(row_values)

    return {"periods": periods, "values": values, "errors": errors}


def check_temporal_contract(
    periods: list[dict[str, Any]], *, contract: Mapping[str, Any]
) -> list[dict[str, Any]]:
    """Coverage and resolution must obey the contract of the definition."""

    errors: list[dict[str, Any]] = []
    if contract.get("regularity") != "regular":
        return errors
    expected = contract.get("nominal_resolution_seconds")
    if not expected:
        return errors
    expected_hours = float(expected) / 3600.0
    for period in periods:
        if abs(period["duration_hours"] - expected_hours) > 1e-9:
            errors.append(
                {
                    "code": "TS_INGEST_TEMPORAL_CONTRACT_INVALID",
                    "message": "the period does not match the nominal resolution",
                    "location": {
                        "record_index": period["period_index"],
                        "json_pointer": f"/points/{period['period_index']}",
                    },
                }
            )
    for position, period in enumerate(periods[1:], start=1):
        if period["timestamp_start"] != periods[position - 1]["timestamp_end"]:
            errors.append(
                {
                    "code": "TS_INGEST_TEMPORAL_CONTRACT_INVALID",
                    "message": "a regular series cannot leave a gap",
                    "location": {
                        "record_index": period["period_index"],
                        "json_pointer": f"/points/{period['period_index']}",
                    },
                }
            )
    return errors


def utc_presentation(value: Any) -> str | None:
    """Canonical rows keep naive UTC; the API always shows the offset."""

    if value is None:
        return None
    text = str(value)
    return text if text.endswith("Z") else f"{text}Z"


def summarize_normalized(periods: list[dict[str, Any]], values: list[dict[str, Any]]):
    return {
        "period_count": len(periods),
        "value_count": len(values),
        "coverage_start": periods[0]["timestamp_start"] if periods else None,
        "coverage_end": periods[-1]["timestamp_end"] if periods else None,
    }


def ingestion_expiry(now: str) -> str:
    moment = datetime.fromisoformat(now) + timedelta(seconds=INGESTION_LIFETIME_SECONDS)
    return moment.isoformat()


def payload_checksum(document: Any) -> str:
    encoded = json.dumps(
        document, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return f"sha256:{hashlib.sha256(encoded.encode('utf-8')).hexdigest()}"
