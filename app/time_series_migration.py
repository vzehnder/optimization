"""Migration control surface and C0 recovery point (TS-7 chapters 10.2, 10.3).

Unlike the canonical content model, these four tables carry names that do not
exist in the legacy schema, so rule 10.1 - never mix legacy and canonical
children in one table - does not apply to them and they keep the exact names
chapter 10.3 gives them on both engines. They are migration *control*, not
canonical content: C0 runs against the legacy source before the expansion is
authoritative, and the control rows must outlive any rollback of ``ts_next``.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from decimal import Decimal
from typing import Any, Iterable, Mapping


MIGRATION_CONTROL_VERSION = 1
C0_MANIFEST_VERSION = 1

MIGRATION_CONTROL_TABLES = (
    "time_series_migration_runs",
    "time_series_migration_mappings",
    "time_series_migration_anomalies",
    "time_series_legacy_dirty_roots",
)


# The legacy source C0 inventories. Order matters: it is also the order a
# recovery copy is restored in, so a child never lands before its parent.
C0_INVENTORY_TABLES = (
    "time_series_sources",
    "time_series_sets",
    "time_series_set_revisions",
    "time_series_signals",
    "time_series_periods",
    "time_series_values",
    "case_input_variants",
    "case_time_series_bindings",
)

# Ancestors that carry no time-series content of their own but without which a
# restored copy cannot satisfy its foreign keys.
C0_RESTORE_ANCESTOR_TABLES = (
    "projects",
    "scenarios",
    "optimization_cases",
)

C0_RESTORE_TABLES = C0_RESTORE_ANCESTOR_TABLES + C0_INVENTORY_TABLES


def migration_control_table_names(backend: str) -> dict[str, str]:
    """Physical name of every control table for the given engine."""

    return {logical: logical for logical in MIGRATION_CONTROL_TABLES}


def migration_actor(migration_run_id: int) -> str:
    """The technical actor every migrator-created row carries (chapter 10.3)."""

    return f"system:migration:{int(migration_run_id)}"


# Typed findings of chapter 10.7, plus the four structural breaks C0 can prove
# from the legacy source alone. The four extra codes name conditions the 10.7
# table has no entry for; none of them weakens a treatment it already decides.
MIGRATION_ANOMALY_CODES = {
    "duplicate_series_key": "TS_MIGRATION_DUPLICATE_SERIES_KEY",
    "duplicate_binding_target": "TS_MIGRATION_DUPLICATE_BINDING",
    "binding_signal_unresolved": "TS_MIGRATION_BINDING_SIGNAL_UNRESOLVED",
    "binding_project_mismatch": "TS_MIGRATION_PROJECT_MISMATCH",
    "value_set_mismatch": "TS_MIGRATION_VALUE_SET_MISMATCH",
    "revision_chain_broken": "TS_MIGRATION_REVISION_CHAIN_BROKEN",
    "unknown_semantic_type": "TS_MIGRATION_UNKNOWN_SEMANTIC_TYPE",
    "unknown_unit": "TS_MIGRATION_UNKNOWN_UNIT",
    "object_not_found": "TS_MIGRATION_OBJECT_NOT_FOUND",
    "object_ambiguous": "TS_MIGRATION_OBJECT_AMBIGUOUS",
    "binding_role_unresolved": "TS_MIGRATION_BINDING_ROLE_UNRESOLVED",
    "revision_unmaterialized": "TS_MIGRATION_REVISION_UNMATERIALIZED",
    "hash_mismatch": "TS_MIGRATION_HASH_MISMATCH",
    "object_specific_review": "TS_MIGRATION_OBJECT_SPECIFIC_REVIEW_REQUIRED",
}

C0_STOPPED = "TS_MIGRATION_C0_STOPPED"
C2_STOPPED = "TS_MIGRATION_C2_STOPPED"
C3_STOPPED = "TS_MIGRATION_C3_STOPPED"
C4_STOPPED = "TS_MIGRATION_C4_STOPPED"
C0_RESTORE_NOT_PROVEN = "TS_MIGRATION_RESTORE_NOT_PROVEN"
MAPPING_CONFLICT = "TS_MIGRATION_MAPPING_CONFLICT"
RECOVERY_POINT_REQUIRED = "TS_MIGRATION_RECOVERY_POINT_REQUIRED"
MIGRATION_PHASE_REQUIRED = "TS_MIGRATION_PHASE_REQUIRED"


# Chapter 10.7 deliberately resolves the legacy execution field through an
# exact table. Similar-looking spellings are not accepted.
LEGACY_BINDING_ROLE_ALIASES = {
    "import_price_usd_per_mwh": "grid_import_price",
    "export_price_usd_per_mwh": "grid_export_price",
    "load_demand_mw": "load_demand",
    "renewable_available_power_mw": "renewable_available_power",
    "hydro_inflow_m3s": "hydro_inflow",
    "natural_inflow_m3s": "natural_inflow",
    "minimum_flow_m3s": "minimum_flow",
}

# The legacy symmetric tariff is the sole one-to-many transformation mandated
# by the initial compatibility matrix: one energy-price signal supplies both
# explicit grid price roles.
LEGACY_BINDING_ROLE_EXPANSIONS = {
    "price_usd_per_mwh": ("grid_import_price", "grid_export_price"),
}


class MigrationControlError(RuntimeError):
    """Stable refusal raised by the migration control surface."""

    def __init__(self, code: str, **context: Any):
        self.code = code
        self.context = context
        super().__init__(f"{code}: {context}" if context else code)


class MigrationPhaseStopped(MigrationControlError):
    """A phase refused to finish because a difference is unexplained."""

    def __init__(self, code: str, *, migration_run_id: int, findings, **context: Any):
        self.migration_run_id = int(migration_run_id)
        self.findings = list(findings)
        self.unexplained_finding_keys = [
            finding["finding_key"]
            for finding in self.findings
            if not finding["explained"]
        ]
        super().__init__(code, migration_run_id=self.migration_run_id, **context)


def structural_finding(
    probe: str,
    *,
    kind: str,
    row_count: int,
    evidence: Mapping[str, Any],
    finding_key: str,
) -> dict[str, Any]:
    return {
        "probe": probe,
        "kind": kind,
        "code": MIGRATION_ANOMALY_CODES[probe],
        "severity": "blocking",
        "finding_key": finding_key,
        "row_count": int(row_count),
        "evidence": dict(evidence),
        "explained": False,
        "explanation": "",
    }


def normalize_source_value(value: Any) -> Any:
    """One JSON-comparable shape for a legacy cell on either engine.

    PostgreSQL hands back ``Decimal``, ``memoryview`` and native booleans where
    SQLite hands back ``str``, ``bytes`` and integers. The manifest hash is the
    evidence C5 reconciles against, so the two engines must agree on the bytes
    they hash for the same stored row.
    """

    if isinstance(value, bool):
        return int(value)
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (bytes, bytearray, memoryview)):
        return bytes(value).hex()
    if isinstance(value, float):
        # ``repr`` round-trips a double exactly; ``json`` would print the same
        # text but this keeps the contract explicit and engine independent.
        return repr(float(value))
    if value is None or isinstance(value, (int, str)):
        return value
    return str(value)


def normalize_source_row(row: Mapping[str, Any]) -> dict[str, Any]:
    return {str(column): normalize_source_value(row[column]) for column in row}


C0_COPY_VERSION = 1
C0_COPY_FILENAME = "c0_recovery_copy.json"


def transport_value(value: Any) -> Any:
    """One JSON-safe cell that restores to the value the source held.

    Unlike :func:`normalize_source_value` this keeps a float a float: the copy
    has to reload into a database, not only hash the same. ``json`` round-trips
    a Python double exactly, so no precision is traded for portability.
    """

    if isinstance(value, bool):
        return int(value)
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (bytes, bytearray, memoryview)):
        return {"__bytes__": bytes(value).hex()}
    return value


def restored_value(value: Any) -> Any:
    if isinstance(value, Mapping) and "__bytes__" in value:
        return bytes.fromhex(str(value["__bytes__"]))
    return value


def canonical_digest(document: Any) -> str:
    encoded = json.dumps(
        document, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return f"sha256:{hashlib.sha256(encoded.encode('utf-8')).hexdigest()}"


def rows_digest(rows: Iterable[Mapping[str, Any]]) -> str:
    """Streaming hash of an ordered row sequence, one JSON object per row."""

    digest = hashlib.sha256()
    for row in rows:
        encoded = json.dumps(
            normalize_source_row(row),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        digest.update(encoded.encode("utf-8"))
        digest.update(b"\n")
    return f"sha256:{digest.hexdigest()}"


def sign_manifest(manifest_digest: str, *, secret: bytes) -> str:
    """Detached signature over the manifest digest (chapter 10.2)."""

    signature = hmac.new(secret, manifest_digest.encode("utf-8"), hashlib.sha256)
    return f"hmac-sha256:{signature.hexdigest()}"


def manifest_signature_matches(
    manifest_digest: str, signature: str, *, secret: bytes
) -> bool:
    return hmac.compare_digest(
        sign_manifest(manifest_digest, secret=secret), str(signature)
    )


def migration_control_schema_statements(backend: str) -> list[str]:
    """Additive DDL for the four control tables of chapter 10.3."""

    postgres = backend == "postgresql"
    table = migration_control_table_names(backend)
    identity = (
        "BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY"
        if postgres
        else "INTEGER PRIMARY KEY AUTOINCREMENT"
    )
    reference = "BIGINT" if postgres else "INTEGER"

    return [
        f"""
        CREATE TABLE IF NOT EXISTS {table['time_series_migration_runs']} (
            id {identity},
            control_version INTEGER NOT NULL DEFAULT {MIGRATION_CONTROL_VERSION},
            phase TEXT NOT NULL,
            status TEXT NOT NULL,
            source_engine TEXT NOT NULL,
            manifest_json TEXT NOT NULL DEFAULT '{{}}',
            manifest_digest TEXT NOT NULL DEFAULT '',
            manifest_signature TEXT NOT NULL DEFAULT '',
            watermark TEXT NOT NULL DEFAULT '',
            checkpoint_json TEXT NOT NULL DEFAULT '{{}}',
            started_at TEXT NOT NULL,
            finished_at TEXT,
            started_by TEXT NOT NULL,
            actor TEXT NOT NULL,
            CHECK (phase IN ('C0', 'C1', 'C2', 'C3', 'C4', 'C5', 'C6')),
            CHECK (status IN ('running', 'proven', 'stopped'))
        )
        """,
        f"""
        CREATE TABLE IF NOT EXISTS {table['time_series_migration_mappings']} (
            id {identity},
            migration_run_id {reference} NOT NULL
                REFERENCES {table['time_series_migration_runs']}(id),
            source_kind TEXT NOT NULL,
            source_table TEXT NOT NULL,
            source_id TEXT NOT NULL,
            target_kind TEXT NOT NULL,
            target_id TEXT NOT NULL,
            source_hash TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            actor TEXT NOT NULL,
            UNIQUE (source_kind, source_table, source_id, target_kind)
        )
        """,
        f"""
        CREATE TABLE IF NOT EXISTS {table['time_series_migration_anomalies']} (
            id {identity},
            migration_run_id {reference} NOT NULL
                REFERENCES {table['time_series_migration_runs']}(id),
            phase TEXT NOT NULL,
            code TEXT NOT NULL,
            severity TEXT NOT NULL,
            finding_key TEXT NOT NULL,
            evidence_json TEXT NOT NULL DEFAULT '{{}}',
            resolution TEXT NOT NULL DEFAULT 'open',
            resolution_note TEXT NOT NULL DEFAULT '',
            resolved_at TEXT,
            resolved_by TEXT,
            created_at TEXT NOT NULL,
            actor TEXT NOT NULL,
            CHECK (severity IN ('blocking', 'informational')),
            CHECK (resolution IN ('open', 'explained', 'resolved', 'waived'))
        )
        """,
        f"""
        CREATE TABLE IF NOT EXISTS {table['time_series_legacy_dirty_roots']} (
            id {identity},
            sequence_number INTEGER NOT NULL,
            root_kind TEXT NOT NULL,
            root_id TEXT NOT NULL,
            watermark TEXT NOT NULL,
            drained_at TEXT,
            created_at TEXT NOT NULL,
            actor TEXT NOT NULL,
            UNIQUE (sequence_number)
        )
        """,
        f"""
        CREATE INDEX IF NOT EXISTS time_series_legacy_dirty_roots_pending_idx
            ON {table['time_series_legacy_dirty_roots']} (root_kind, root_id)
        """,
        f"""
        CREATE INDEX IF NOT EXISTS time_series_migration_anomalies_open_idx
            ON {table['time_series_migration_anomalies']}
            (migration_run_id, severity, resolution)
        """,
    ]
