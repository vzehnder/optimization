"""Object-specific series: definition, staging, points and file ingestion.

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

import csv
import hashlib
import hmac
import io
import json
import math
import re
import time
import zipfile
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.time_series_canonical import canonical_space_table_name
from app.time_series_ingestion import TimeSeriesIngestionError, parse_xlsx_rows


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
# Chapter 7.9 shows a sample of consumers, never an unbounded collection.
SHARED_CONSUMER_SAMPLE_LIMIT = 50
INGESTION_LIFETIME_SECONDS = 24 * 60 * 60
FILE_CSV_MAX_BYTES = 100 * 1024 * 1024
FILE_XLSX_MAX_BYTES = 25 * 1024 * 1024
FILE_XLSX_MAX_UNCOMPRESSED_BYTES = 100 * 1024 * 1024
FILE_XLSX_MAX_COMPRESSION_RATIO = 100
FILE_MAX_PERIODS = 1_000_000
FILE_MAX_CELLS = 5_000_000
FILE_MAX_COLUMNS = 200
FILE_MAX_ACTIVE_JOBS = 3

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
FILE_INGESTION_OPERATION_KIND = "prepare_object_series_file_ingestion"
PUBLISH_SHARED_OPERATION_KIND = "publish_shared_series_revision"
DERIVE_OBJECT_SERIES_OPERATION_KIND = "derive_object_specific_series"

CSV_MEDIA_TYPES = ("text/csv", "application/csv")
XLSX_MEDIA_TYPE = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)


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
    "TS_SHARED_REVISION_ADMIN_REQUIRED": (
        "https://errors.example/time-series/shared-revision-admin-required",
        "A global source is published only by an administrator",
        403,
    ),
    "TS_LINK_CONFIRMATION_REQUIRED": (
        "https://errors.example/time-series/link-confirmation-required",
        "The operation requires explicit confirmation",
        409,
    ),
    "TS_SHARED_DERIVATION_REQUIRED": (
        "https://errors.example/time-series/shared-derivation-required",
        "The shared source cannot receive this content",
        422,
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
            catalog_association_id {reference},
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


def parse_object_series_file_upload(
    *,
    original_filename: str,
    media_type: str | None,
    content: bytes,
    series_key: str,
    sheet_name: str | None = None,
) -> dict[str, Any]:
    """Inspect an uploaded file without opening a canonical transaction."""

    filename = re.sub(
        r"[^A-Za-z0-9._-]+", "_", original_filename.replace("\\", "/").split("/")[-1]
    ) or "source.csv"
    normalized_media_type = str(media_type or "").split(";", 1)[0].strip().lower()
    is_csv = filename.lower().endswith(".csv") and normalized_media_type in CSV_MEDIA_TYPES
    is_xlsx = filename.lower().endswith(".xlsx") and normalized_media_type == XLSX_MEDIA_TYPE
    if not is_csv and not is_xlsx:
        raise ObjectSeriesError(
            "TS_INGEST_FORMAT_UNSUPPORTED",
            detail="the first file channel accepts CSV or XLSX",
        )
    maximum_bytes = FILE_XLSX_MAX_BYTES if is_xlsx else FILE_CSV_MAX_BYTES
    if len(content) > maximum_bytes:
        raise ObjectSeriesError(
            "TS_INGEST_PAYLOAD_TOO_LARGE",
            detail="the uploaded file exceeds the transport budget",
            maximum_bytes=maximum_bytes,
        )
    if is_xlsx:
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                members = archive.infolist()
                uncompressed_bytes = sum(member.file_size for member in members)
                compressed_bytes = sum(member.compress_size for member in members)
        except zipfile.BadZipFile as error:
            raise ObjectSeriesError(
                "TS_INGEST_VALIDATION_FAILED",
                detail="XLSX source file could not be read",
            ) from error
        if (
            uncompressed_bytes > FILE_XLSX_MAX_UNCOMPRESSED_BYTES
            or uncompressed_bytes
            > max(compressed_bytes, 1) * FILE_XLSX_MAX_COMPRESSION_RATIO
        ):
            raise ObjectSeriesError(
                "TS_INGEST_PAYLOAD_TOO_LARGE",
                detail="the XLSX archive exceeds its expansion budget",
                maximum_uncompressed_bytes=FILE_XLSX_MAX_UNCOMPRESSED_BYTES,
                maximum_compression_ratio=FILE_XLSX_MAX_COMPRESSION_RATIO,
            )
    available_sheets: list[str] = []
    selected_sheet: str | None = None
    if is_xlsx:
        try:
            parsed_sheet, available_sheets, columns, rows = parse_xlsx_rows(
                content, sheet_name=sheet_name
            )
            worksheets = {}
            for available_sheet in available_sheets:
                _, _, sheet_columns, sheet_rows = parse_xlsx_rows(
                    content, sheet_name=available_sheet
                )
                worksheets[available_sheet] = {
                    "columns": sheet_columns,
                    "rows": sheet_rows,
                }
        except TimeSeriesIngestionError as error:
            raise ObjectSeriesError(
                "TS_INGEST_VALIDATION_FAILED",
                detail=str(error),
            ) from error
        selected_sheet = parsed_sheet if sheet_name or len(available_sheets) == 1 else None
    else:
        worksheets = {}
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError as error:
            raise ObjectSeriesError(
                "TS_INGEST_VALIDATION_FAILED",
                detail="CSV files must be UTF-8 encoded",
                errors=[
                    {
                        "code": "TS_INGEST_VALUE_INVALID",
                        "message": "CSV files must be UTF-8 encoded",
                        "location": {"record_index": 0, "source_row_number": 1},
                    }
                ],
            ) from error
        reader = csv.DictReader(io.StringIO(text))
        columns = [str(column or "").strip() for column in (reader.fieldnames or [])]
        rows = [
            {column: str(row.get(column) or "") for column in columns}
            for row in reader
        ]
    if not columns or any(not column for column in columns) or len(set(columns)) != len(columns):
        raise ObjectSeriesError(
            "TS_INGEST_MAPPING_INVALID",
            detail="CSV headers must be non-empty and unique",
        )
    normalized = {
        re.sub(r"[^a-z0-9]+", "_", column.lower()).strip("_"): column
        for column in columns
    }
    quota_errors: list[dict[str, Any]] = []
    if len(columns) > FILE_MAX_COLUMNS:
        quota_errors.append(
            _file_error(
                "TS_INGEST_QUOTA_EXCEEDED",
                "the file exceeds the column quota",
                record_index=0,
                source_row_number=1,
                column=None,
                sheet=selected_sheet,
            )
        )
    if len(rows) > FILE_MAX_PERIODS:
        quota_errors.append(
            _file_error(
                "TS_INGEST_QUOTA_EXCEEDED",
                "the file exceeds the period quota",
                record_index=FILE_MAX_PERIODS,
                source_row_number=FILE_MAX_PERIODS + 2,
                column=None,
                sheet=selected_sheet,
            )
        )
    if len(rows) * len(columns) > FILE_MAX_CELLS:
        quota_errors.append(
            _file_error(
                "TS_INGEST_QUOTA_EXCEEDED",
                "the file exceeds the cell quota",
                record_index=0,
                source_row_number=1,
                column=None,
                sheet=selected_sheet,
            )
        )
    return {
        "original_filename": filename,
        "media_type": normalized_media_type,
        "available_sheets": available_sheets,
        "selected_sheet": selected_sheet,
        "columns": columns,
        "preview_rows": rows[:5],
        "mapping_suggestions": {
            "timestamp_start": next(
                (
                    normalized[key]
                    for key in ("timestamp_start", "timestamp", "datetime")
                    if key in normalized
                ),
                None,
            ),
            "timestamp_end": next(
                (normalized[key] for key in ("timestamp_end", "end") if key in normalized),
                None,
            ),
            "duration_hours": next(
                (
                    normalized[key]
                    for key in ("duration_hours", "duration", "hours")
                    if key in normalized
                ),
                None,
            ),
            "signals": [
                {
                    "series_key": series_key,
                    "value": normalized.get(series_key),
                    "quality_flag": next(
                        (
                            normalized[key]
                            for key in ("quality_flag", "quality")
                            if key in normalized
                        ),
                        None,
                    ),
                }
            ],
        },
        "rows": rows,
        "checksum": f"sha256:{hashlib.sha256(content).hexdigest()}",
        "kind": "xlsx" if is_xlsx else "csv",
        "errors": quota_errors,
        "worksheets": worksheets,
    }


def _file_error(
    code: str,
    message: str,
    *,
    record_index: int,
    source_row_number: int,
    column: str | None,
    sheet: str | None,
) -> dict[str, Any]:
    location: dict[str, Any] = {
        "record_index": record_index,
        "source_row_number": source_row_number,
        "column": column,
    }
    if sheet is not None:
        location["sheet"] = sheet
    return {"code": code, "message": message, "location": location}


def _parse_file_timestamp(
    value: Any,
    *,
    timezone_name: str,
    record_index: int,
    source_row_number: int,
    column: str,
    sheet: str | None,
) -> tuple[datetime | None, dict[str, Any] | None]:
    text = str(value or "").strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None, _file_error(
            "TS_INGEST_TIMESTAMP_INVALID",
            "timestamp must be ISO 8601",
            record_index=record_index,
            source_row_number=source_row_number,
            column=column,
            sheet=sheet,
        )
    if parsed.tzinfo is not None:
        return parsed.astimezone(timezone.utc), None
    try:
        zone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        return None, _file_error(
            "TS_INGEST_TIMESTAMP_INVALID",
            "revision_contract.timezone must be an IANA timezone",
            record_index=record_index,
            source_row_number=source_row_number,
            column=column,
            sheet=sheet,
        )
    candidates = []
    for fold in (0, 1):
        candidate = parsed.replace(tzinfo=zone, fold=fold)
        roundtrip = candidate.astimezone(timezone.utc).astimezone(zone).replace(
            tzinfo=None
        )
        if roundtrip == parsed:
            candidates.append(candidate)
    offsets = {candidate.utcoffset() for candidate in candidates}
    if len(candidates) != 1 and len(offsets) != 1:
        return None, _file_error(
            "TS_INGEST_TIMESTAMP_AMBIGUOUS",
            "local timestamp is ambiguous or does not exist in the declared timezone",
            record_index=record_index,
            source_row_number=source_row_number,
            column=column,
            sheet=sheet,
        )
    if not candidates:
        return None, _file_error(
            "TS_INGEST_TIMESTAMP_AMBIGUOUS",
            "local timestamp is ambiguous or does not exist in the declared timezone",
            record_index=record_index,
            source_row_number=source_row_number,
            column=column,
            sheet=sheet,
        )
    return candidates[0].astimezone(timezone.utc), None


def normalize_file_payload(
    uploaded: Mapping[str, Any],
    mapping: Mapping[str, Any],
    *,
    series_keys: tuple[str, ...],
    contract: Mapping[str, Any],
) -> dict[str, Any]:
    """Normalize mapped file rows into the same staging shape as JSON points."""

    selected_upload = dict(uploaded)
    if uploaded.get("kind") == "xlsx":
        available_sheets = list(uploaded.get("available_sheets") or [])
        requested_sheet = str(mapping.get("sheet_name") or "").strip()
        if len(available_sheets) > 1 and not requested_sheet:
            error = _file_error(
                "TS_INGEST_MAPPING_INVALID",
                "sheet_name is required when the workbook has multiple sheets",
                record_index=0,
                source_row_number=1,
                column=None,
                sheet=None,
            )
            return {
                "periods": [],
                "values": [],
                "errors": [error],
                "uploaded": selected_upload,
            }
        selected_sheet = requested_sheet or (available_sheets[0] if available_sheets else "")
        worksheet = (uploaded.get("worksheets") or {}).get(selected_sheet)
        if not selected_sheet or not isinstance(worksheet, Mapping):
            error = _file_error(
                "TS_INGEST_MAPPING_INVALID",
                "sheet_name does not name a worksheet in the uploaded workbook",
                record_index=0,
                source_row_number=1,
                column=None,
                sheet=selected_sheet or None,
            )
            return {
                "periods": [],
                "values": [],
                "errors": [error],
                "uploaded": selected_upload,
            }
        selected_upload["selected_sheet"] = selected_sheet
        selected_upload["columns"] = list(worksheet.get("columns") or [])
        selected_upload["rows"] = list(worksheet.get("rows") or [])
        selected_upload["preview_rows"] = selected_upload["rows"][:5]

    upload_errors = list(selected_upload.get("errors") or [])
    if upload_errors:
        return {
            "periods": [],
            "values": [],
            "errors": upload_errors,
            "uploaded": selected_upload,
        }
    columns_mapping = mapping.get("columns")
    if not isinstance(columns_mapping, Mapping):
        return {
            "periods": [],
            "values": [],
            "errors": [
                _file_error(
                    "TS_INGEST_MAPPING_INVALID",
                    "columns mapping is required",
                    record_index=0,
                    source_row_number=1,
                    column=None,
                    sheet=selected_upload.get("selected_sheet"),
                )
            ],
            "uploaded": selected_upload,
        }
    available_columns = {str(column) for column in selected_upload.get("columns") or []}
    timestamp_column = str(columns_mapping.get("timestamp_start") or "").strip()
    end_column = str(columns_mapping.get("timestamp_end") or "").strip() or None
    duration_column = str(columns_mapping.get("duration_hours") or "").strip() or None
    signal_mappings = columns_mapping.get("signals")
    mapping_errors: list[dict[str, Any]] = []
    if not timestamp_column or timestamp_column not in available_columns:
        mapping_errors.append(
            _file_error(
                "TS_INGEST_MAPPING_INVALID",
                "timestamp_start must name an uploaded column",
                record_index=0,
                source_row_number=1,
                column=timestamp_column or None,
                sheet=selected_upload.get("selected_sheet"),
            )
        )
    if (end_column is None) == (duration_column is None):
        mapping_errors.append(
            _file_error(
                "TS_INGEST_MAPPING_INVALID",
                "map exactly one of timestamp_end and duration_hours",
                record_index=0,
                source_row_number=1,
                column=end_column or duration_column,
                sheet=selected_upload.get("selected_sheet"),
            )
        )
    for column in (end_column, duration_column):
        if column is not None and column not in available_columns:
            mapping_errors.append(
                _file_error(
                    "TS_INGEST_MAPPING_INVALID",
                    "the mapping names a column the file does not have",
                    record_index=0,
                    source_row_number=1,
                    column=column,
                    sheet=selected_upload.get("selected_sheet"),
                )
            )
    by_series: dict[str, Mapping[str, Any]] = {}
    signal_entries = (
        [entry for entry in signal_mappings if isinstance(entry, Mapping)]
        if isinstance(signal_mappings, list)
        else []
    )
    signal_keys = [str(entry.get("series_key") or "") for entry in signal_entries]
    if len(signal_keys) != len(set(signal_keys)):
        mapping_errors.append(
            _file_error(
                "TS_INGEST_MAPPING_INVALID",
                "a target series cannot be mapped more than once",
                record_index=0,
                source_row_number=1,
                column=None,
                sheet=selected_upload.get("selected_sheet"),
            )
        )
    by_series = dict(zip(signal_keys, signal_entries))
    if set(by_series) != set(series_keys):
        mapping_errors.append(
            _file_error(
                "TS_INGEST_MAPPING_INVALID",
                "signals must map every target series exactly once",
                record_index=0,
                source_row_number=1,
                column=None,
                sheet=selected_upload.get("selected_sheet"),
            )
        )
    for series_key in series_keys:
        entry = by_series.get(series_key) or {}
        value_column = str(entry.get("value") or "").strip()
        quality_column = str(entry.get("quality_flag") or "").strip() or None
        if not value_column or value_column not in available_columns:
            mapping_errors.append(
                _file_error(
                    "TS_INGEST_MAPPING_INVALID",
                    f"'{series_key}' must name a value column",
                    record_index=0,
                    source_row_number=1,
                    column=value_column or None,
                    sheet=selected_upload.get("selected_sheet"),
                )
            )
        if quality_column is not None and quality_column not in available_columns:
            mapping_errors.append(
                _file_error(
                    "TS_INGEST_MAPPING_INVALID",
                    "the quality mapping names a column the file does not have",
                    record_index=0,
                    source_row_number=1,
                    column=quality_column,
                    sheet=selected_upload.get("selected_sheet"),
                )
            )
    if mapping_errors:
        return {
            "periods": [],
            "values": [],
            "errors": mapping_errors,
            "uploaded": selected_upload,
        }

    points: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    rows = selected_upload.get("rows") or []
    sheet = selected_upload.get("selected_sheet")
    for record_index, row in enumerate(rows):
        source_row = record_index + 2
        start, error = _parse_file_timestamp(
            row.get(timestamp_column),
            timezone_name=str(contract.get("timezone") or "UTC"),
            record_index=record_index,
            source_row_number=source_row,
            column=timestamp_column,
            sheet=sheet,
        )
        if error is not None:
            errors.append(error)
            continue
        point: dict[str, Any] = {"timestamp_start": start.isoformat()}
        if end_column is not None:
            end, error = _parse_file_timestamp(
                row.get(end_column),
                timezone_name=str(contract.get("timezone") or "UTC"),
                record_index=record_index,
                source_row_number=source_row,
                column=end_column,
                sheet=sheet,
            )
            if error is not None:
                errors.append(error)
                continue
            point["timestamp_end"] = end.isoformat()
        else:
            raw_duration = str(row.get(duration_column) or "").strip()
            try:
                duration_hours = float(raw_duration)
            except ValueError:
                duration_hours = math.nan
            if not math.isfinite(duration_hours) or duration_hours <= 0:
                errors.append(
                    _file_error(
                        "TS_INGEST_DURATION_INVALID",
                        "duration_hours must be a positive finite number",
                        record_index=record_index,
                        source_row_number=source_row,
                        column=duration_column,
                        sheet=sheet,
                    )
                )
                continue
            point["duration_seconds"] = duration_hours * 3600.0
        point_values: dict[str, Any] = {}
        row_failed = False
        for series_key in series_keys:
            entry = by_series[series_key]
            value_column = str(entry["value"])
            raw_value = str(row.get(value_column) or "").strip()
            try:
                numeric = float(raw_value)
            except ValueError:
                numeric = math.nan
            if not math.isfinite(numeric):
                errors.append(
                    _file_error(
                        "TS_INGEST_VALUE_INVALID",
                        "value must be a finite number",
                        record_index=record_index,
                        source_row_number=source_row,
                        column=value_column,
                        sheet=sheet,
                    )
                )
                row_failed = True
                continue
            quality_column = str(entry.get("quality_flag") or "").strip() or None
            quality = str(row.get(quality_column) or "").strip() if quality_column else ""
            if quality and quality not in QUALITY_FLAGS:
                errors.append(
                    _file_error(
                        "TS_INGEST_VALUE_INVALID",
                        "quality_flag is not in the allowed catalog",
                        record_index=record_index,
                        source_row_number=source_row,
                        column=quality_column,
                        sheet=sheet,
                    )
                )
                row_failed = True
                continue
            point_values[series_key] = {
                "value": numeric,
                "quality_flag": quality or None,
            }
        if not row_failed:
            point["values"] = point_values
            points.append(point)

    if errors:
        return {
            "periods": [],
            "values": [],
            "errors": errors,
            "uploaded": selected_upload,
        }
    normalized = normalize_points_payload(
        {"points": points}, series_keys=series_keys, mapping={}
    )
    file_errors: list[dict[str, Any]] = []
    for entry in normalized["errors"]:
        record_index = int(entry["location"].get("record_index", 0))
        pointer = str(entry["location"].get("json_pointer") or "")
        column = timestamp_column
        if "duration" in pointer or "timestamp_end" in pointer:
            column = end_column or duration_column
        elif "/values/" in pointer:
            series_key = next(
                (key for key in series_keys if f"/values/{key}" in pointer),
                series_keys[0],
            )
            column = str(by_series[series_key].get("value") or "")
        file_errors.append(
            _file_error(
                entry["code"],
                entry["message"],
                record_index=record_index,
                source_row_number=record_index + 2,
                column=column,
                sheet=sheet,
            )
        )
    for period in normalized["periods"]:
        period["source_row_number"] = int(period["period_index"]) + 2
    for value in normalized["values"]:
        value["source_row_number"] = int(value["period_index"]) + 2
    return {
        "periods": normalized["periods"],
        "values": normalized["values"],
        "errors": file_errors,
        "uploaded": selected_upload,
    }


def ingestion_validation_token(
    *, ingestion_key: str, content_hash: str, secret: bytes
) -> str:
    digest = hmac.new(
        secret, f"{ingestion_key}:{content_hash}".encode("utf-8"), hashlib.sha256
    ).hexdigest()[:32]
    return f"tsv_{digest}"


def derivation_prevalidation_token(
    *,
    association_id: int,
    source_revision_id: int,
    content_hash: str,
    object_series_key: str,
    secret: bytes,
) -> str:
    """Pin the comparison to one source revision and one local key (7.9)."""

    material = (
        f"{int(association_id)}:{int(source_revision_id)}:{content_hash}:"
        f"{object_series_key}"
    )
    digest = hmac.new(secret, material.encode("utf-8"), hashlib.sha256).hexdigest()[:32]
    return f"tsd_{digest}"


def shared_source_etag(*, set_id: int, current_revision_id: int | None) -> str:
    """The strong validator of a shared generic source (chapter 8.6)."""

    return f'"shared-{int(set_id)}-{0 if current_revision_id is None else int(current_revision_id)}"'


def shared_impact_fingerprint(impact: Mapping[str, Any]) -> str:
    """Everything the decision was taken on, in one comparable value.

    Chapter 8.6 revalidates the impact at confirmation time: if any of the
    numbers the caller was shown moved, the action blocks and a new
    confirmation is demanded (AC-SHR-06).
    """

    observed = {
        "source": impact["source"],
        "associations": impact["associations"],
        "bindings": impact["bindings"],
        "effect": impact["effect"],
    }
    digest = hashlib.sha256(
        json.dumps(observed, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:32]
    return f"tsi_{digest}"


def shared_decision_alternatives(
    *,
    derivation_href: str,
    shared_href: str,
    derivation_required: bool,
    may_publish_shared: bool,
    requires_admin: bool,
    intent: str,
) -> list[dict[str, Any]]:
    """The two outcomes, ordered, and never labelled `save` or `update`.

    Chapter 8.4 fixes the visible language: the shared branch is
    `Publicar para todos`, so its stable key is `publish_for_everyone` and no
    neutral verb is offered as a synonym (AC-SHR-03 backend half).
    """

    local = {
        "kind": "derive_object_specific",
        "label_key": "create_specific_for_this_object",
        "available": True,
        "requires_admin": False,
        "unavailable_code": None,
        "href": derivation_href,
    }
    shared = {
        "kind": "publish_shared",
        "label_key": "publish_for_everyone",
        "available": bool(may_publish_shared),
        "requires_admin": bool(requires_admin),
        "unavailable_code": (
            None
            if may_publish_shared
            else (
                "TS_SHARED_REVISION_ADMIN_REQUIRED"
                if requires_admin
                else "TS_INGEST_FORBIDDEN"
            )
        ),
        "href": shared_href,
    }
    # The local outcome leads whenever the caller declared a local intent, and
    # whenever deriving is the only outcome left (chapter 8.6 step 3).
    if derivation_required or str(intent).strip().lower() == "local":
        return [local, shared]
    return [shared, local]


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


def check_file_temporal_contract(
    periods: list[dict[str, Any]],
    *,
    contract: Mapping[str, Any],
    mapping: Mapping[str, Any],
    sheet: str | None,
) -> list[dict[str, Any]]:
    """Express temporal validation failures in the file-channel location shape."""

    columns = mapping.get("columns") or {}
    timestamp_column = str(columns.get("timestamp_start") or "") or None
    duration_column = (
        str(columns.get("timestamp_end") or "").strip()
        or str(columns.get("duration_hours") or "").strip()
        or None
    )
    by_index = {
        int(period["period_index"]): period
        for period in periods
    }
    translated = []
    for error in check_temporal_contract(periods, contract=contract):
        record_index = int(error["location"].get("record_index", 0))
        period = by_index.get(record_index) or {}
        translated.append(
            _file_error(
                error["code"],
                error["message"],
                record_index=record_index,
                source_row_number=int(
                    period.get("source_row_number") or record_index + 2
                ),
                column=(
                    timestamp_column
                    if "gap" in str(error["message"])
                    else duration_column
                ),
                sheet=sheet,
            )
        )
    return translated


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
