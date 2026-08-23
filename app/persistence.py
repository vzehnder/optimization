from __future__ import annotations

import hashlib
import json
import math
import sqlite3
import threading
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping

from app.auth import VALID_USER_ROLES
from app.database import connect_database, database_url_from_env, postgres_schema_from_sqlite
from app.draft_editor import DraftGenerationError, generate_system_case_from_draft
from app.input_variants import materialize_variant_time_series, resolve_bound_signal_series
from app.required_signals import (
    MissingRequiredSignalsError,
    discover_required_signals,
    evaluate_variant_completeness,
    required_signal_status_to_dict,
)
from app.variant_staleness import (
    VariantStaleError,
    evaluate_variant_staleness,
    variant_staleness_result_to_dict,
)
from app.schedules import (
    normalize_schedule_cadence,
    parse_schedule_datetime,
    resolve_schedule_range,
)
from app.time_series_catalog import (
    TIME_SERIES_SIGNAL_CATALOG,
    CatalogPeriod,
    CatalogSignal,
    CatalogValue,
    CatalogValueEdit,
    PreparedTimeSeriesCatalogImport,
    TimeSeriesCatalogError,
    catalog_content_hash,
    compute_catalog_content_hash,
    normalize_optional_text,
    validate_catalog_value_edits,
    validate_program_metadata,
)
from app.transformations import (
    TransformationDefinition,
    TransformationError,
    TransformationInputSet,
    TransformationOutput,
    get_transformation_definition,
)
from app.legacy_series_extraction import (
    PreparedDraftSeriesExtraction,
    prepare_draft_series_extraction,
)
from app.hydraulic_time_series_adapter import (
    build_hydraulic_catalog_detail,
    build_hydraulic_catalog_summary,
)
from app.time_series_ingestion import find_source
from app.portal_configuration import (
    StalePortalConfigurationError,
    default_portal_config_document,
    portal_config_document_from_dashboard_template,
)


DASHBOARD_TEMPLATE_FLAGS = [
    "show_summary",
    "show_price_chart",
    "show_grid_chart",
    "show_renewable_chart",
    "show_bess_chart",
    "show_hydro_chart",
    "show_profit_chart",
    "show_system_dispatch_table",
    "show_asset_dispatch_table",
]

DEFAULT_TABLE_PREVIEW_LIMIT = 10

PORTAL_CONFIGURATION_MIGRATION = "portal_configurations_from_dashboard_templates"

DEFAULT_PUBLICATION_ARTIFACT_TYPES = [
    "summary_json",
    "dispatch_csv",
    "asset_dispatch_csv",
]

HYDRAULIC_NODE_COMPONENT_TYPES = {"reservoir", "junction"}
HYDRAULIC_VISIBLE_COMPONENT_TYPES = HYDRAULIC_NODE_COMPONENT_TYPES | {"plant"}
HYDRAULIC_REACH_TYPES = {
    "river",
    "canal",
    "tunnel",
    "gate",
    "spillway",
    "bypass",
    "tailrace",
    "other",
}
HYDRAULIC_TERMINAL_CONDITIONS = {"none", "equal_initial", "min_terminal"}
# Routing methods the schema can store; the MVP v3 solver only runs `none`
# (no travel-time delay). Other values are persisted but rejected before
# promotion by topology validation.
HYDRAULIC_ROUTING_METHODS = {"none", "fixed_delay", "linear_reservoir", "custom_curve"}
HYDRAULIC_SUPPORTED_ROUTING_METHODS = {"none"}
# Unit capability/generation modes the schema can store. The MVP v3 solver only
# runs generation-only units with a flow-power curve; pumping, reversibility and
# head-dependent generation are rejected before promotion.
HYDRAULIC_UNIT_OPERATION_MODES = {"generation", "pump_only", "reversible"}
HYDRAULIC_SUPPORTED_UNIT_OPERATION_MODES = {"generation"}
HYDRAULIC_UNIT_GENERATION_MODES = {"flow_power_curve", "head_dependent"}
HYDRAULIC_SUPPORTED_UNIT_GENERATION_MODES = {"flow_power_curve"}
STORAGE_ELEVATION_CURVE_KEY = "storage_elevation"
FLOW_POWER_CURVE_KEY = "flow_power"

# Each curve role maps a versioned curve set to its base entity scope and axes.
STORAGE_ELEVATION_CURVE_SPEC = {
    "curve_key": STORAGE_ELEVATION_CURVE_KEY,
    "base_entity_type": "hydraulic_node",
    "axis_x_name": "storage_hm3",
    "axis_x_unit": "hm3",
    "axis_y_name": "elevation_masl",
    "axis_y_unit": "masl",
}
FLOW_POWER_CURVE_SPEC = {
    "curve_key": FLOW_POWER_CURVE_KEY,
    "base_entity_type": "hydraulic_unit",
    "axis_x_name": "flow_m3s",
    "axis_x_unit": "m3s",
    "axis_y_name": "power_mw",
    "axis_y_unit": "mw",
}

NATURAL_INFLOW_SIGNAL_KEY = "natural_inflow_m3s"
MINIMUM_FLOW_SIGNAL_KEY = "minimum_flow_m3s"
HYDRAULIC_GENERIC_SERIES_DATA_KIND = "real"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def elapsed_seconds(started_at: str | None, finished_at: str) -> float | None:
    if not started_at:
        return None

    start = datetime.fromisoformat(started_at)
    finish = datetime.fromisoformat(finished_at)
    return max(0.0, (finish - start).total_seconds())


class AnalystStore:
    def __init__(self, database_url: str | None = None):
        self.database_url = database_url or database_url_from_env()
        self._lock = threading.RLock()
        self.database_backend, self.database_path, self.connection = connect_database(self.database_url)
        self._initialize_schema()

    def close(self) -> None:
        connection = getattr(self, "connection", None)
        if connection is not None:
            connection.close()
            self.connection = None

    def __del__(self) -> None:
        self.close()

    def _initialize_schema(self) -> None:
        schema = """
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                created_by TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS scenarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                created_by TEXT NOT NULL,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
            );

            -- Scenario -> OptimizationCase is deliberately one-to-one (confirmed,
            -- not migrated, in docs/series_tiempo/iter5/decision_record_ts5_migration_semantics.md
            -- decision 4). The UNIQUE constraint below is intentional design, not
            -- a leftover early-implementation limit: keep it unless a future
            -- decision record explicitly reopens the cardinality question.
            CREATE TABLE IF NOT EXISTS optimization_cases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scenario_id INTEGER NOT NULL UNIQUE,
                case_key TEXT NOT NULL,
                display_name TEXT NOT NULL,
                validation_payload_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                created_by TEXT NOT NULL,
                updated_by TEXT NOT NULL,
                FOREIGN KEY (scenario_id) REFERENCES scenarios(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS hydraulic_systems (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                system_key TEXT NOT NULL,
                display_name TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                created_by TEXT NOT NULL,
                updated_by TEXT NOT NULL,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
                UNIQUE (project_id, system_key)
            );

            CREATE TABLE IF NOT EXISTS hydraulic_nodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                hydraulic_system_id INTEGER NOT NULL,
                node_key TEXT NOT NULL,
                display_name TEXT NOT NULL,
                node_type TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                created_by TEXT NOT NULL,
                updated_by TEXT NOT NULL,
                FOREIGN KEY (hydraulic_system_id) REFERENCES hydraulic_systems(id) ON DELETE CASCADE,
                UNIQUE (hydraulic_system_id, node_key),
                CHECK (node_type IN ('reservoir', 'junction', 'intake', 'tailrace', 'river_inflow', 'other'))
            );

            CREATE TABLE IF NOT EXISTS hydraulic_reaches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                hydraulic_system_id INTEGER NOT NULL,
                reach_key TEXT NOT NULL,
                display_name TEXT NOT NULL,
                from_node_id INTEGER NOT NULL,
                to_node_id INTEGER NOT NULL,
                reach_type TEXT NOT NULL,
                travel_time_hours REAL NOT NULL DEFAULT 0,
                routing_method TEXT NOT NULL DEFAULT 'none',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                created_by TEXT NOT NULL,
                updated_by TEXT NOT NULL,
                FOREIGN KEY (hydraulic_system_id) REFERENCES hydraulic_systems(id) ON DELETE CASCADE,
                FOREIGN KEY (from_node_id) REFERENCES hydraulic_nodes(id) ON DELETE CASCADE,
                FOREIGN KEY (to_node_id) REFERENCES hydraulic_nodes(id) ON DELETE CASCADE,
                UNIQUE (hydraulic_system_id, reach_key),
                CHECK (reach_type IN ('river', 'canal', 'tunnel', 'gate', 'spillway', 'bypass', 'tailrace', 'other'))
            );

            CREATE TABLE IF NOT EXISTS hydraulic_plants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                hydraulic_system_id INTEGER NOT NULL,
                plant_key TEXT NOT NULL,
                display_name TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                created_by TEXT NOT NULL,
                updated_by TEXT NOT NULL,
                FOREIGN KEY (hydraulic_system_id) REFERENCES hydraulic_systems(id) ON DELETE CASCADE,
                UNIQUE (hydraulic_system_id, plant_key)
            );

            CREATE TABLE IF NOT EXISTS case_hydraulic_systems (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id INTEGER NOT NULL,
                hydraulic_system_id INTEGER NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                created_by TEXT NOT NULL,
                updated_by TEXT NOT NULL,
                FOREIGN KEY (case_id) REFERENCES optimization_cases(id) ON DELETE CASCADE,
                FOREIGN KEY (hydraulic_system_id) REFERENCES hydraulic_systems(id) ON DELETE CASCADE,
                UNIQUE (case_id, hydraulic_system_id)
            );

            CREATE TABLE IF NOT EXISTS case_hydraulic_nodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id INTEGER NOT NULL,
                hydraulic_node_id INTEGER NOT NULL,
                case_label TEXT NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                created_by TEXT NOT NULL,
                updated_by TEXT NOT NULL,
                FOREIGN KEY (case_id) REFERENCES optimization_cases(id) ON DELETE CASCADE,
                FOREIGN KEY (hydraulic_node_id) REFERENCES hydraulic_nodes(id) ON DELETE CASCADE,
                UNIQUE (case_id, hydraulic_node_id)
            );

            CREATE TABLE IF NOT EXISTS case_hydraulic_reaches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id INTEGER NOT NULL,
                hydraulic_reach_id INTEGER NOT NULL,
                case_label TEXT NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1,
                flow_min_m3s REAL,
                spill_penalty_usd_per_hm3 REAL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                created_by TEXT NOT NULL,
                updated_by TEXT NOT NULL,
                FOREIGN KEY (case_id) REFERENCES optimization_cases(id) ON DELETE CASCADE,
                FOREIGN KEY (hydraulic_reach_id) REFERENCES hydraulic_reaches(id) ON DELETE CASCADE,
                UNIQUE (case_id, hydraulic_reach_id)
            );

            CREATE TABLE IF NOT EXISTS hydraulic_units (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                hydraulic_plant_id INTEGER NOT NULL,
                unit_key TEXT NOT NULL,
                display_name TEXT NOT NULL,
                intake_node_id INTEGER,
                discharge_node_id INTEGER,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                created_by TEXT NOT NULL,
                updated_by TEXT NOT NULL,
                FOREIGN KEY (hydraulic_plant_id) REFERENCES hydraulic_plants(id) ON DELETE CASCADE,
                FOREIGN KEY (intake_node_id) REFERENCES hydraulic_nodes(id) ON DELETE SET NULL,
                FOREIGN KEY (discharge_node_id) REFERENCES hydraulic_nodes(id) ON DELETE SET NULL,
                UNIQUE (hydraulic_plant_id, unit_key)
            );

            CREATE TABLE IF NOT EXISTS case_hydraulic_plants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id INTEGER NOT NULL,
                hydraulic_plant_id INTEGER NOT NULL,
                case_label TEXT NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1,
                non_modeled INTEGER NOT NULL DEFAULT 0,
                min_power_mw REAL,
                max_power_mw REAL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                created_by TEXT NOT NULL,
                updated_by TEXT NOT NULL,
                FOREIGN KEY (case_id) REFERENCES optimization_cases(id) ON DELETE CASCADE,
                FOREIGN KEY (hydraulic_plant_id) REFERENCES hydraulic_plants(id) ON DELETE CASCADE,
                UNIQUE (case_id, hydraulic_plant_id)
            );

            CREATE TABLE IF NOT EXISTS case_hydraulic_units (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id INTEGER NOT NULL,
                hydraulic_unit_id INTEGER NOT NULL,
                case_hydraulic_plant_id INTEGER NOT NULL,
                case_label TEXT NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1,
                min_power_mw REAL,
                max_power_mw REAL,
                min_flow_m3s REAL,
                max_flow_m3s REAL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                created_by TEXT NOT NULL,
                updated_by TEXT NOT NULL,
                FOREIGN KEY (case_id) REFERENCES optimization_cases(id) ON DELETE CASCADE,
                FOREIGN KEY (hydraulic_unit_id) REFERENCES hydraulic_units(id) ON DELETE CASCADE,
                FOREIGN KEY (case_hydraulic_plant_id) REFERENCES case_hydraulic_plants(id) ON DELETE CASCADE,
                UNIQUE (case_id, hydraulic_unit_id)
            );

            CREATE TABLE IF NOT EXISTS case_hydraulic_reservoir_parameters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id INTEGER NOT NULL,
                case_hydraulic_node_id INTEGER NOT NULL,
                storage_min_hm3 REAL NOT NULL,
                storage_max_hm3 REAL NOT NULL,
                initial_storage_hm3 REAL NOT NULL,
                terminal_condition TEXT NOT NULL DEFAULT 'none',
                terminal_storage_min_hm3 REAL,
                terminal_water_value_usd_per_hm3 REAL NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                created_by TEXT NOT NULL,
                updated_by TEXT NOT NULL,
                FOREIGN KEY (case_id) REFERENCES optimization_cases(id) ON DELETE CASCADE,
                FOREIGN KEY (case_hydraulic_node_id) REFERENCES case_hydraulic_nodes(id) ON DELETE CASCADE,
                UNIQUE (case_id, case_hydraulic_node_id),
                CHECK (terminal_condition IN ('none', 'equal_initial', 'min_terminal'))
            );

            CREATE TABLE IF NOT EXISTS hydraulic_curve_sets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                entity_type TEXT NOT NULL,
                entity_id INTEGER NOT NULL,
                curve_key TEXT NOT NULL,
                version_number INTEGER NOT NULL,
                version_label TEXT NOT NULL,
                curve_dimension INTEGER NOT NULL DEFAULT 1,
                axis_x_name TEXT NOT NULL,
                axis_x_unit TEXT NOT NULL,
                axis_y_name TEXT NOT NULL,
                axis_y_unit TEXT NOT NULL,
                content_hash TEXT,
                status TEXT NOT NULL DEFAULT 'draft',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                created_by TEXT NOT NULL,
                updated_by TEXT NOT NULL,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
                UNIQUE (project_id, entity_type, entity_id, curve_key, version_number),
                CHECK (status IN ('draft', 'validated', 'archived'))
            );

            CREATE TABLE IF NOT EXISTS hydraulic_curve_points (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                hydraulic_curve_set_id INTEGER NOT NULL,
                point_index INTEGER NOT NULL,
                x_value REAL NOT NULL,
                y_value REAL NOT NULL,
                FOREIGN KEY (hydraulic_curve_set_id) REFERENCES hydraulic_curve_sets(id) ON DELETE CASCADE,
                UNIQUE (hydraulic_curve_set_id, point_index)
            );

            CREATE TABLE IF NOT EXISTS case_hydraulic_curve_bindings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id INTEGER NOT NULL,
                entity_type TEXT NOT NULL,
                entity_id INTEGER NOT NULL,
                curve_role TEXT NOT NULL,
                hydraulic_curve_set_id INTEGER NOT NULL,
                required INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                created_by TEXT NOT NULL,
                updated_by TEXT NOT NULL,
                FOREIGN KEY (case_id) REFERENCES optimization_cases(id) ON DELETE CASCADE,
                FOREIGN KEY (hydraulic_curve_set_id) REFERENCES hydraulic_curve_sets(id) ON DELETE CASCADE,
                UNIQUE (case_id, entity_type, entity_id, curve_role)
            );

            CREATE TABLE IF NOT EXISTS hydraulic_time_series_sets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                entity_type TEXT NOT NULL,
                entity_id INTEGER NOT NULL,
                signal_key TEXT NOT NULL,
                version_number INTEGER NOT NULL,
                version_label TEXT NOT NULL,
                content_hash TEXT,
                status TEXT NOT NULL DEFAULT 'draft',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                created_by TEXT NOT NULL,
                updated_by TEXT NOT NULL,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
                UNIQUE (project_id, entity_type, entity_id, signal_key, version_number),
                CHECK (status IN ('draft', 'validated', 'archived'))
            );

            CREATE TABLE IF NOT EXISTS hydraulic_time_series_points (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                hydraulic_time_series_set_id INTEGER NOT NULL,
                point_index INTEGER NOT NULL,
                timestamp TEXT NOT NULL,
                duration_hours REAL NOT NULL,
                value REAL NOT NULL,
                FOREIGN KEY (hydraulic_time_series_set_id)
                    REFERENCES hydraulic_time_series_sets(id) ON DELETE CASCADE,
                UNIQUE (hydraulic_time_series_set_id, point_index)
            );

            CREATE TABLE IF NOT EXISTS case_hydraulic_time_series_bindings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id INTEGER NOT NULL,
                entity_type TEXT NOT NULL,
                entity_id INTEGER NOT NULL,
                signal_key TEXT NOT NULL,
                hydraulic_time_series_set_id INTEGER,
                time_series_set_id INTEGER,
                required INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                created_by TEXT NOT NULL,
                updated_by TEXT NOT NULL,
                FOREIGN KEY (case_id) REFERENCES optimization_cases(id) ON DELETE CASCADE,
                FOREIGN KEY (hydraulic_time_series_set_id)
                    REFERENCES hydraulic_time_series_sets(id) ON DELETE CASCADE,
                FOREIGN KEY (time_series_set_id)
                    REFERENCES time_series_sets(id) ON DELETE CASCADE,
                UNIQUE (case_id, entity_type, entity_id, signal_key),
                CHECK (
                    (hydraulic_time_series_set_id IS NOT NULL AND time_series_set_id IS NULL)
                    OR (hydraulic_time_series_set_id IS NULL AND time_series_set_id IS NOT NULL)
                )
            );

            CREATE TABLE IF NOT EXISTS case_hydraulic_diagram_layouts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id INTEGER NOT NULL,
                layout_key TEXT NOT NULL,
                viewport_x REAL NOT NULL DEFAULT 0,
                viewport_y REAL NOT NULL DEFAULT 0,
                zoom REAL NOT NULL DEFAULT 1,
                layout_engine TEXT,
                layout_version INTEGER NOT NULL DEFAULT 1,
                content_hash TEXT,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                updated_by TEXT NOT NULL,
                FOREIGN KEY (case_id) REFERENCES optimization_cases(id) ON DELETE CASCADE,
                UNIQUE (case_id, layout_key),
                CHECK (zoom > 0)
            );

            CREATE TABLE IF NOT EXISTS case_hydraulic_diagram_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                diagram_layout_id INTEGER NOT NULL,
                entity_type TEXT NOT NULL,
                entity_id INTEGER NOT NULL,
                x REAL NOT NULL,
                y REAL NOT NULL,
                width REAL,
                height REAL,
                z_index INTEGER NOT NULL DEFAULT 0,
                collapsed INTEGER NOT NULL DEFAULT 0,
                style_json TEXT NOT NULL DEFAULT '{}',
                metadata_json TEXT NOT NULL DEFAULT '{}',
                updated_at TEXT NOT NULL,
                FOREIGN KEY (diagram_layout_id) REFERENCES case_hydraulic_diagram_layouts(id) ON DELETE CASCADE,
                UNIQUE (diagram_layout_id, entity_type, entity_id),
                CHECK (entity_type IN ('case_hydraulic_node', 'case_hydraulic_reach', 'case_hydraulic_plant'))
            );

            CREATE TABLE IF NOT EXISTS scenario_versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scenario_id INTEGER NOT NULL,
                version_number INTEGER NOT NULL,
                system_case_json TEXT NOT NULL,
                case_name TEXT NOT NULL,
                schema_version TEXT NOT NULL,
                period_count INTEGER NOT NULL,
                asset_counts_json TEXT NOT NULL,
                validation_payload_json TEXT NOT NULL,
                generation_metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                created_by TEXT NOT NULL,
                FOREIGN KEY (scenario_id) REFERENCES scenarios(id) ON DELETE CASCADE,
                UNIQUE (scenario_id, version_number)
            );

            CREATE TRIGGER IF NOT EXISTS scenario_versions_immutable
            BEFORE UPDATE ON scenario_versions
            BEGIN
                SELECT RAISE(ABORT, 'scenario versions are immutable');
            END;

            CREATE TABLE IF NOT EXISTS scenario_version_hydraulic_diagram_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scenario_version_id INTEGER NOT NULL,
                source_case_id INTEGER,
                layout_key TEXT NOT NULL,
                layout_snapshot_json TEXT NOT NULL,
                layout_content_hash TEXT,
                created_at TEXT NOT NULL,
                created_by TEXT NOT NULL,
                FOREIGN KEY (scenario_version_id) REFERENCES scenario_versions(id) ON DELETE CASCADE,
                FOREIGN KEY (source_case_id) REFERENCES optimization_cases(id) ON DELETE SET NULL,
                UNIQUE (scenario_version_id, layout_key)
            );

            -- scenario_id UNIQUE mirrors the same one-to-one decision as
            -- optimization_cases (see decision_record_ts5_migration_semantics.md
            -- decision 4): the structured draft stays a single compatibility
            -- surface per scenario, not a list.
            CREATE TABLE IF NOT EXISTS scenario_drafts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scenario_id INTEGER NOT NULL UNIQUE,
                source_version_id INTEGER,
                document_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                created_by TEXT NOT NULL,
                updated_by TEXT NOT NULL,
                FOREIGN KEY (scenario_id) REFERENCES scenarios(id) ON DELETE CASCADE,
                FOREIGN KEY (source_version_id) REFERENCES scenario_versions(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS time_series_sources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                source_key TEXT NOT NULL,
                kind TEXT NOT NULL,
                original_filename TEXT NOT NULL,
                media_type TEXT NOT NULL,
                checksum TEXT NOT NULL,
                stored_path TEXT NOT NULL,
                selected_sheet TEXT,
                created_at TEXT NOT NULL,
                created_by TEXT NOT NULL,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
                UNIQUE (project_id, source_key)
            );

            CREATE TABLE IF NOT EXISTS time_series_sets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                version_number INTEGER NOT NULL,
                version_label TEXT NOT NULL,
                data_kind TEXT NOT NULL,
                timezone TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'draft',
                content_hash TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                created_by TEXT NOT NULL,
                updated_by TEXT NOT NULL,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
                UNIQUE (project_id, name, version_number),
                UNIQUE (project_id, name, version_label),
                CHECK (status IN ('draft', 'validated', 'archived'))
            );

            CREATE TABLE IF NOT EXISTS time_series_set_revisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                time_series_set_id INTEGER NOT NULL,
                revision_number INTEGER NOT NULL,
                time_series_source_id INTEGER,
                superseded_revision_number INTEGER,
                content_hash TEXT NOT NULL,
                change_summary TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                created_by TEXT NOT NULL,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                FOREIGN KEY (time_series_set_id) REFERENCES time_series_sets(id) ON DELETE CASCADE,
                FOREIGN KEY (time_series_source_id) REFERENCES time_series_sources(id) ON DELETE SET NULL,
                UNIQUE (time_series_set_id, revision_number)
            );

            CREATE TABLE IF NOT EXISTS time_series_periods (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                time_series_set_id INTEGER NOT NULL,
                period_index INTEGER NOT NULL,
                timestamp_start TEXT NOT NULL,
                timestamp_end TEXT NOT NULL,
                duration_hours REAL NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (time_series_set_id) REFERENCES time_series_sets(id) ON DELETE CASCADE,
                UNIQUE (time_series_set_id, period_index),
                UNIQUE (time_series_set_id, timestamp_start)
            );

            CREATE TABLE IF NOT EXISTS time_series_signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                time_series_set_id INTEGER NOT NULL,
                signal_key TEXT NOT NULL,
                unit TEXT NOT NULL,
                entity_type TEXT,
                entity_key TEXT,
                signal_role TEXT NOT NULL DEFAULT 'input',
                aggregation TEXT NOT NULL DEFAULT 'period_average',
                created_at TEXT NOT NULL,
                FOREIGN KEY (time_series_set_id) REFERENCES time_series_sets(id) ON DELETE CASCADE,
                UNIQUE (time_series_set_id, signal_key, entity_type, entity_key)
            );

            CREATE TABLE IF NOT EXISTS time_series_values (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                time_series_set_id INTEGER NOT NULL,
                time_series_signal_id INTEGER NOT NULL,
                time_series_period_id INTEGER NOT NULL,
                value_numeric REAL NOT NULL,
                source_row_number INTEGER,
                created_at TEXT NOT NULL,
                FOREIGN KEY (time_series_set_id) REFERENCES time_series_sets(id) ON DELETE CASCADE,
                FOREIGN KEY (time_series_signal_id) REFERENCES time_series_signals(id) ON DELETE CASCADE,
                FOREIGN KEY (time_series_period_id) REFERENCES time_series_periods(id) ON DELETE CASCADE,
                UNIQUE (time_series_signal_id, time_series_period_id)
            );

            CREATE TABLE IF NOT EXISTS time_series_set_extractions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                time_series_set_id INTEGER NOT NULL,
                scenario_id INTEGER NOT NULL,
                source_id TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                extracted_at TEXT NOT NULL,
                extracted_by TEXT NOT NULL,
                FOREIGN KEY (time_series_set_id) REFERENCES time_series_sets(id) ON DELETE CASCADE,
                FOREIGN KEY (scenario_id) REFERENCES scenarios(id) ON DELETE CASCADE,
                UNIQUE (scenario_id, source_id)
            );

            CREATE TABLE IF NOT EXISTS hydraulic_time_series_set_migrations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                hydraulic_time_series_set_id INTEGER NOT NULL UNIQUE,
                time_series_set_id INTEGER NOT NULL,
                content_hash TEXT NOT NULL,
                migrated_at TEXT NOT NULL,
                migrated_by TEXT NOT NULL,
                FOREIGN KEY (hydraulic_time_series_set_id)
                    REFERENCES hydraulic_time_series_sets(id) ON DELETE CASCADE,
                FOREIGN KEY (time_series_set_id) REFERENCES time_series_sets(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS case_input_variants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id INTEGER NOT NULL,
                variant_key TEXT NOT NULL,
                display_name TEXT NOT NULL,
                is_default INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                created_by TEXT NOT NULL,
                updated_by TEXT NOT NULL,
                FOREIGN KEY (case_id) REFERENCES optimization_cases(id) ON DELETE CASCADE,
                UNIQUE (case_id, variant_key)
            );

            CREATE UNIQUE INDEX IF NOT EXISTS case_input_variants_default_unique
                ON case_input_variants (case_id)
                WHERE is_default = 1;

            CREATE TABLE IF NOT EXISTS case_time_series_bindings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_input_variant_id INTEGER NOT NULL,
                signal_key TEXT NOT NULL,
                entity_type TEXT,
                entity_id TEXT,
                time_series_set_id INTEGER NOT NULL,
                required INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                created_by TEXT NOT NULL,
                updated_by TEXT NOT NULL,
                FOREIGN KEY (case_input_variant_id) REFERENCES case_input_variants(id) ON DELETE CASCADE,
                FOREIGN KEY (time_series_set_id) REFERENCES time_series_sets(id) ON DELETE CASCADE,
                UNIQUE (case_input_variant_id, signal_key, entity_type, entity_id)
            );

            CREATE TABLE IF NOT EXISTS validation_dependencies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                owner_type TEXT NOT NULL,
                owner_id INTEGER NOT NULL,
                dependency_type TEXT NOT NULL,
                dependency_id TEXT NOT NULL DEFAULT '',
                recorded_hash TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE (owner_type, owner_id, dependency_type, dependency_id)
            );

            CREATE TABLE IF NOT EXISTS runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scenario_version_id INTEGER NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                started_at TEXT,
                finished_at TEXT,
                duration_seconds REAL,
                exit_code INTEGER,
                workspace_path TEXT,
                input_snapshot_path TEXT,
                output_dir TEXT,
                summary_path TEXT,
                stdout_log_path TEXT,
                stderr_log_path TEXT,
                error_message TEXT NOT NULL DEFAULT '',
                success_payload_json TEXT NOT NULL DEFAULT '{}',
                error_payload_json TEXT NOT NULL DEFAULT '{}',
                stdout TEXT NOT NULL DEFAULT '',
                stderr TEXT NOT NULL DEFAULT '',
                triggered_by TEXT NOT NULL,
                trigger_type TEXT NOT NULL,
                FOREIGN KEY (scenario_version_id) REFERENCES scenario_versions(id) ON DELETE CASCADE,
                CHECK (status IN ('queued', 'running', 'succeeded', 'failed'))
            );

            CREATE TABLE IF NOT EXISTS run_schedules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scenario_id INTEGER NOT NULL,
                case_id INTEGER NOT NULL,
                case_input_variant_id INTEGER NOT NULL,
                display_name TEXT NOT NULL,
                range_start TEXT NOT NULL,
                range_end TEXT NOT NULL,
                range_mode TEXT NOT NULL DEFAULT 'fixed',
                rolling_start_offset_hours REAL,
                rolling_duration_hours REAL,
                cadence TEXT NOT NULL,
                next_run_at TEXT NOT NULL,
                topology_hash TEXT NOT NULL,
                parameter_hash TEXT NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1,
                last_fired_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                created_by TEXT NOT NULL,
                updated_by TEXT NOT NULL,
                FOREIGN KEY (scenario_id) REFERENCES scenarios(id) ON DELETE CASCADE,
                FOREIGN KEY (case_id) REFERENCES optimization_cases(id) ON DELETE CASCADE,
                FOREIGN KEY (case_input_variant_id) REFERENCES case_input_variants(id) ON DELETE CASCADE,
                CHECK (cadence IN ('hourly', 'daily', 'weekly'))
            );

            CREATE TABLE IF NOT EXISTS run_schedule_ticks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                schedule_id INTEGER NOT NULL,
                due_at TEXT NOT NULL,
                fired_at TEXT NOT NULL,
                range_start TEXT NOT NULL,
                range_end TEXT NOT NULL,
                status TEXT NOT NULL,
                scenario_version_id INTEGER,
                run_id INTEGER,
                error_message TEXT NOT NULL DEFAULT '',
                error_payload_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (schedule_id) REFERENCES run_schedules(id) ON DELETE CASCADE,
                FOREIGN KEY (scenario_version_id) REFERENCES scenario_versions(id) ON DELETE SET NULL,
                FOREIGN KEY (run_id) REFERENCES runs(id) ON DELETE SET NULL,
                CHECK (status IN ('queued', 'failed'))
            );

            CREATE TABLE IF NOT EXISTS run_artifacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER NOT NULL,
                artifact_type TEXT NOT NULL,
                path TEXT NOT NULL,
                display_name TEXT NOT NULL,
                media_type TEXT NOT NULL,
                byte_size INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (run_id) REFERENCES runs(id) ON DELETE CASCADE,
                UNIQUE (run_id, artifact_type)
            );

            CREATE TABLE IF NOT EXISTS run_dispatch_result_indexes (
                run_id INTEGER PRIMARY KEY,
                scenario_version_id INTEGER NOT NULL,
                dispatch_columns_json TEXT NOT NULL,
                signal_keys_json TEXT NOT NULL DEFAULT '{}',
                lineage_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                FOREIGN KEY (run_id) REFERENCES runs(id) ON DELETE CASCADE,
                FOREIGN KEY (scenario_version_id) REFERENCES scenario_versions(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS run_dispatch_result_rows (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER NOT NULL,
                period_index INTEGER NOT NULL,
                row_json TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                duration_hours TEXT,
                price_usd_per_mwh TEXT,
                import_price_usd_per_mwh TEXT,
                export_price_usd_per_mwh TEXT,
                market_value_usd TEXT,
                grid_import_mw TEXT,
                grid_export_mw TEXT,
                battery_charge_mw TEXT,
                battery_discharge_mw TEXT,
                battery_energy_mwh TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (run_id) REFERENCES runs(id) ON DELETE CASCADE,
                UNIQUE (run_id, period_index),
                UNIQUE (run_id, timestamp)
            );

            CREATE TABLE IF NOT EXISTS run_asset_dispatch_result_indexes (
                run_id INTEGER PRIMARY KEY,
                scenario_version_id INTEGER NOT NULL,
                asset_dispatch_columns_json TEXT NOT NULL,
                lineage_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                FOREIGN KEY (run_id) REFERENCES runs(id) ON DELETE CASCADE,
                FOREIGN KEY (scenario_version_id) REFERENCES scenario_versions(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS run_asset_dispatch_result_rows (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER NOT NULL,
                period_index INTEGER NOT NULL,
                asset_id TEXT NOT NULL,
                asset_type TEXT NOT NULL,
                row_json TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (run_id) REFERENCES runs(id) ON DELETE CASCADE,
                UNIQUE (run_id, period_index)
            );

            CREATE TABLE IF NOT EXISTS run_summary_result_indexes (
                run_id INTEGER PRIMARY KEY,
                scenario_version_id INTEGER NOT NULL,
                summary_json TEXT NOT NULL,
                solver_status TEXT,
                termination_status TEXT,
                objective_value_usd REAL,
                linked_result_surfaces_json TEXT NOT NULL DEFAULT '[]',
                lineage_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                FOREIGN KEY (run_id) REFERENCES runs(id) ON DELETE CASCADE,
                FOREIGN KEY (scenario_version_id) REFERENCES scenario_versions(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                display_name TEXT NOT NULL DEFAULT '',
                role TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                created_by TEXT NOT NULL,
                deactivated_at TEXT,
                CHECK (role IN ('admin', 'analyst', 'external'))
            );

            CREATE TABLE IF NOT EXISTS auth_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                token_hash TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                revoked_at TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS project_client_access (
                project_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                assigned_at TEXT NOT NULL,
                assigned_by TEXT NOT NULL,
                portal_view INTEGER NOT NULL DEFAULT 1,
                operate INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL,
                updated_by TEXT NOT NULL,
                PRIMARY KEY (project_id, user_id),
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS schema_migrations (
                name TEXT PRIMARY KEY,
                applied_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS portal_configurations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL UNIQUE,
                status TEXT NOT NULL DEFAULT 'draft',
                document_json TEXT NOT NULL,
                revision INTEGER NOT NULL DEFAULT 1,
                updated_at TEXT NOT NULL,
                updated_by_user_id INTEGER,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
                FOREIGN KEY (updated_by_user_id) REFERENCES users(id) ON DELETE SET NULL,
                CHECK (status IN ('draft', 'active'))
            );

            CREATE TABLE IF NOT EXISTS dashboard_templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                show_summary INTEGER NOT NULL DEFAULT 1,
                show_price_chart INTEGER NOT NULL DEFAULT 1,
                show_grid_chart INTEGER NOT NULL DEFAULT 1,
                show_renewable_chart INTEGER NOT NULL DEFAULT 1,
                show_bess_chart INTEGER NOT NULL DEFAULT 1,
                show_hydro_chart INTEGER NOT NULL DEFAULT 1,
                show_profit_chart INTEGER NOT NULL DEFAULT 1,
                show_system_dispatch_table INTEGER NOT NULL DEFAULT 1,
                show_asset_dispatch_table INTEGER NOT NULL DEFAULT 1,
                table_preview_limit INTEGER NOT NULL DEFAULT 10,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                created_by TEXT NOT NULL,
                updated_by TEXT NOT NULL,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
                CHECK (table_preview_limit >= 1)
            );

            CREATE TABLE IF NOT EXISTS publications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                scenario_id INTEGER NOT NULL,
                scenario_version_id INTEGER NOT NULL,
                run_id INTEGER NOT NULL,
                dashboard_template_id INTEGER NOT NULL,
                public_title TEXT NOT NULL,
                analyst_notes TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'draft',
                allowed_artifact_types_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                published_at TEXT,
                unpublished_at TEXT,
                created_by TEXT NOT NULL,
                updated_by TEXT NOT NULL,
                published_by TEXT,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
                FOREIGN KEY (scenario_id) REFERENCES scenarios(id) ON DELETE CASCADE,
                FOREIGN KEY (scenario_version_id) REFERENCES scenario_versions(id) ON DELETE CASCADE,
                FOREIGN KEY (run_id) REFERENCES runs(id) ON DELETE CASCADE,
                FOREIGN KEY (dashboard_template_id) REFERENCES dashboard_templates(id),
                CHECK (status IN ('draft', 'published', 'unpublished'))
            );
            """
        if self.database_backend == "postgresql":
            schema = postgres_schema_from_sqlite(schema)
        self.connection.executescript(schema)
        self._ensure_external_user_role_constraint()
        self._ensure_column(
            "project_client_access", "portal_view", "INTEGER NOT NULL DEFAULT 1"
        )
        self._ensure_column(
            "project_client_access", "operate", "INTEGER NOT NULL DEFAULT 0"
        )
        self._ensure_column("project_client_access", "updated_at", "TEXT")
        self._ensure_column("project_client_access", "updated_by", "TEXT")
        self._migrate_legacy_external_access()
        self._ensure_column("runs", "stdout_log_path", "TEXT")
        self._ensure_column("runs", "stderr_log_path", "TEXT")
        self._ensure_column("runs", "error_message", "TEXT NOT NULL DEFAULT ''")
        self._ensure_column("scenario_versions", "generation_metadata_json", "TEXT NOT NULL DEFAULT '{}'")
        self._ensure_column("time_series_signals", "source_column", "TEXT")
        self._ensure_column("time_series_signals", "source_unit", "TEXT")
        self._ensure_column("time_series_set_revisions", "superseded_revision_number", "INTEGER")
        self._ensure_case_time_series_bindings_entity_scope()
        self._ensure_case_hydraulic_time_series_bindings_generic_support()
        self._ensure_hydraulic_diagram_items_support_reaches()
        self._ensure_hydraulic_diagram_items_entity_types_postgres()
        self._ensure_column("case_hydraulic_plants", "non_modeled", "INTEGER NOT NULL DEFAULT 0")
        self._ensure_column("case_hydraulic_plants", "min_power_mw", "REAL")
        self._ensure_column("case_hydraulic_plants", "max_power_mw", "REAL")
        self._ensure_column(
            "hydraulic_units", "operation_mode", "TEXT NOT NULL DEFAULT 'generation'"
        )
        self._ensure_column(
            "hydraulic_units",
            "generation_mode",
            "TEXT NOT NULL DEFAULT 'flow_power_curve'",
        )
        self._ensure_column("run_dispatch_result_indexes", "signal_keys_json", "TEXT NOT NULL DEFAULT '{}'")
        self._ensure_column("run_dispatch_result_indexes", "lineage_json", "TEXT NOT NULL DEFAULT '{}'")
        self._ensure_column("run_asset_dispatch_result_indexes", "lineage_json", "TEXT NOT NULL DEFAULT '{}'")
        self._ensure_column("run_summary_result_indexes", "lineage_json", "TEXT NOT NULL DEFAULT '{}'")
        self._ensure_column("run_schedules", "range_mode", "TEXT NOT NULL DEFAULT 'fixed'")
        self._ensure_column("run_schedules", "rolling_start_offset_hours", "REAL")
        self._ensure_column("run_schedules", "rolling_duration_hours", "REAL")
        self._ensure_query_shape_indexes()
        self.connection.commit()
        self._apply_migration_once(
            PORTAL_CONFIGURATION_MIGRATION,
            self.migrate_dashboard_templates_to_portal_configurations,
        )

    def _ensure_external_user_role_constraint(self) -> None:
        if self.database_backend == "postgresql":
            self.connection.execute(
                "ALTER TABLE users DROP CONSTRAINT IF EXISTS users_role_check"
            )
            self.connection.execute(
                "UPDATE users SET role = 'external' WHERE role = 'client'"
            )
            self.connection.execute(
                "ALTER TABLE users ADD CONSTRAINT users_role_check "
                "CHECK (role IN ('admin', 'analyst', 'external'))"
            )
            return

        row = self.connection.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'users'"
        ).fetchone()
        if row is None or "'client'" not in str(row["sql"]):
            return

        self.connection.commit()
        self.connection.execute("PRAGMA foreign_keys = OFF")
        try:
            self.connection.executescript(
                """
                CREATE TABLE users_without_legacy_client_role (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                    display_name TEXT NOT NULL DEFAULT '',
                    role TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    created_by TEXT NOT NULL,
                    deactivated_at TEXT,
                    CHECK (role IN ('admin', 'analyst', 'external'))
                );
                INSERT INTO users_without_legacy_client_role (
                    id, email, display_name, role, password_hash, is_active,
                    created_at, updated_at, created_by, deactivated_at
                )
                SELECT id, email, display_name,
                       CASE WHEN role = 'client' THEN 'external' ELSE role END,
                       password_hash, is_active,
                       created_at, updated_at, created_by, deactivated_at
                FROM users;
                DROP TABLE users;
                ALTER TABLE users_without_legacy_client_role RENAME TO users;
                """
            )
        finally:
            self.connection.execute("PRAGMA foreign_keys = ON")

    def _migrate_legacy_external_access(self) -> None:
        self.connection.execute(
            """
            UPDATE project_client_access
            SET updated_at = assigned_at
            WHERE updated_at IS NULL OR updated_at = ''
            """
        )
        self.connection.execute(
            """
            UPDATE project_client_access
            SET updated_by = assigned_by
            WHERE updated_by IS NULL OR updated_by = ''
            """
        )
        self.connection.execute("UPDATE users SET role = 'external' WHERE role = 'client'")

    def _apply_migration_once(self, name: str, migration) -> None:
        """Run a one-shot data migration and remember that it already ran.

        Without the marker a project published after the cutover would be
        configured from its dashboard template on the next start, silently
        enabling panels the analyst never declared.
        """

        applied = self.connection.execute(
            "SELECT 1 FROM schema_migrations WHERE name = ?", (name,)
        ).fetchone()
        if applied is not None:
            return
        migration()
        with self._lock:
            self.connection.execute(
                "INSERT INTO schema_migrations (name, applied_at) VALUES (?, ?)",
                (name, utc_now_iso()),
            )
            self.connection.commit()

    def _ensure_column(self, table_name: str, column_name: str, definition: str) -> None:
        if self.database_backend == "postgresql":
            row = self.connection.execute(
                """
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = current_schema()
                  AND table_name = ?
                  AND column_name = ?
                """,
                (table_name, column_name),
            ).fetchone()
            if row is None:
                self.connection.execute(
                    f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}"
                )
            return

        columns = {
            row["name"]
            for row in self.connection.execute(f"PRAGMA table_info({table_name})").fetchall()
        }
        if column_name not in columns:
            self.connection.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}")

    def _ensure_query_shape_indexes(self) -> None:
        self.connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_time_series_values_set_period_signal
            ON time_series_values (time_series_set_id, time_series_period_id, time_series_signal_id)
            """
        )
        self.connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_runs_status_scenario_version
            ON runs (status, scenario_version_id, id)
            """
        )
        self.connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_scenario_versions_scenario
            ON scenario_versions (scenario_id, id)
            """
        )
        self.connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_scenarios_project
            ON scenarios (project_id, id)
            """
        )
        self.connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_run_schedules_due
            ON run_schedules (is_active, next_run_at, id)
            """
        )
        self.connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_run_schedule_ticks_schedule
            ON run_schedule_ticks (schedule_id, id)
            """
        )

    def _ensure_hydraulic_diagram_items_support_reaches(self) -> None:
        if self.database_backend != "sqlite":
            return
        row = self.connection.execute(
            """
            SELECT sql
            FROM sqlite_master
            WHERE type = 'table' AND name = 'case_hydraulic_diagram_items'
            """
        ).fetchone()
        if row is None or "case_hydraulic_reach" in str(row["sql"]):
            return
        self.connection.execute("PRAGMA foreign_keys = OFF")
        self.connection.executescript(
            """
            ALTER TABLE case_hydraulic_diagram_items
            RENAME TO case_hydraulic_diagram_items_old;

            CREATE TABLE case_hydraulic_diagram_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                diagram_layout_id INTEGER NOT NULL,
                entity_type TEXT NOT NULL,
                entity_id INTEGER NOT NULL,
                x REAL NOT NULL,
                y REAL NOT NULL,
                width REAL,
                height REAL,
                z_index INTEGER NOT NULL DEFAULT 0,
                collapsed INTEGER NOT NULL DEFAULT 0,
                style_json TEXT NOT NULL DEFAULT '{}',
                metadata_json TEXT NOT NULL DEFAULT '{}',
                updated_at TEXT NOT NULL,
                FOREIGN KEY (diagram_layout_id) REFERENCES case_hydraulic_diagram_layouts(id) ON DELETE CASCADE,
                UNIQUE (diagram_layout_id, entity_type, entity_id),
                CHECK (entity_type IN ('case_hydraulic_node', 'case_hydraulic_reach', 'case_hydraulic_plant'))
            );

            INSERT INTO case_hydraulic_diagram_items (
                id,
                diagram_layout_id,
                entity_type,
                entity_id,
                x,
                y,
                width,
                height,
                z_index,
                collapsed,
                style_json,
                metadata_json,
                updated_at
            )
            SELECT
                id,
                diagram_layout_id,
                entity_type,
                entity_id,
                x,
                y,
                width,
                height,
                z_index,
                collapsed,
                style_json,
                metadata_json,
                updated_at
            FROM case_hydraulic_diagram_items_old;

            DROP TABLE case_hydraulic_diagram_items_old;
            """
        )
        self.connection.execute("PRAGMA foreign_keys = ON")

    def _ensure_case_time_series_bindings_entity_scope(self) -> None:
        if self.database_backend == "postgresql":
            rows = self.connection.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = current_schema()
                  AND table_name = 'case_time_series_bindings'
                """
            ).fetchall()
            columns = {str(row["column_name"]) for row in rows}
            if {"entity_type", "entity_id"}.issubset(columns):
                return
            self.connection.execute(
                "ALTER TABLE case_time_series_bindings RENAME TO case_time_series_bindings_old"
            )
            self.connection.execute(
                """
                CREATE TABLE case_time_series_bindings (
                    id INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                    case_input_variant_id INTEGER NOT NULL,
                    signal_key TEXT NOT NULL,
                    entity_type TEXT,
                    entity_id TEXT,
                    time_series_set_id INTEGER NOT NULL,
                    required INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    created_by TEXT NOT NULL,
                    updated_by TEXT NOT NULL,
                    FOREIGN KEY (case_input_variant_id) REFERENCES case_input_variants(id) ON DELETE CASCADE,
                    FOREIGN KEY (time_series_set_id) REFERENCES time_series_sets(id) ON DELETE CASCADE,
                    UNIQUE (case_input_variant_id, signal_key, entity_type, entity_id)
                )
                """
            )
            self.connection.execute(
                """
                INSERT INTO case_time_series_bindings (
                    id,
                    case_input_variant_id,
                    signal_key,
                    entity_type,
                    entity_id,
                    time_series_set_id,
                    required,
                    created_at,
                    updated_at,
                    created_by,
                    updated_by
                )
                SELECT
                    id,
                    case_input_variant_id,
                    signal_key,
                    NULL,
                    NULL,
                    time_series_set_id,
                    required,
                    created_at,
                    updated_at,
                    created_by,
                    updated_by
                FROM case_time_series_bindings_old
                """
            )
            self.connection.execute("DROP TABLE case_time_series_bindings_old")
            self.connection.execute(
                """
                SELECT setval(
                    pg_get_serial_sequence('case_time_series_bindings', 'id'),
                    COALESCE((SELECT MAX(id) FROM case_time_series_bindings), 1),
                    true
                )
                """
            )
            return

        columns = {
            row["name"]
            for row in self.connection.execute("PRAGMA table_info(case_time_series_bindings)").fetchall()
        }
        if {"entity_type", "entity_id"}.issubset(columns):
            return
        self.connection.execute("PRAGMA foreign_keys = OFF")
        self.connection.executescript(
            """
            ALTER TABLE case_time_series_bindings
            RENAME TO case_time_series_bindings_old;

            CREATE TABLE case_time_series_bindings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_input_variant_id INTEGER NOT NULL,
                signal_key TEXT NOT NULL,
                entity_type TEXT,
                entity_id TEXT,
                time_series_set_id INTEGER NOT NULL,
                required INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                created_by TEXT NOT NULL,
                updated_by TEXT NOT NULL,
                FOREIGN KEY (case_input_variant_id) REFERENCES case_input_variants(id) ON DELETE CASCADE,
                FOREIGN KEY (time_series_set_id) REFERENCES time_series_sets(id) ON DELETE CASCADE,
                UNIQUE (case_input_variant_id, signal_key, entity_type, entity_id)
            );

            INSERT INTO case_time_series_bindings (
                id,
                case_input_variant_id,
                signal_key,
                entity_type,
                entity_id,
                time_series_set_id,
                required,
                created_at,
                updated_at,
                created_by,
                updated_by
            )
            SELECT
                id,
                case_input_variant_id,
                signal_key,
                NULL,
                NULL,
                time_series_set_id,
                required,
                created_at,
                updated_at,
                created_by,
                updated_by
            FROM case_time_series_bindings_old;

            DROP TABLE case_time_series_bindings_old;
            """
        )
        self.connection.execute("PRAGMA foreign_keys = ON")

    def _ensure_case_hydraulic_time_series_bindings_generic_support(self) -> None:
        """Allow a binding to target either a legacy or a generic series set.

        Existing databases created ``hydraulic_time_series_set_id`` as
        ``NOT NULL``. From this iteration on, new hydraulic series writes land
        in the generic catalog instead, so a binding row needs to reference
        either store through a nullable column, never both.
        """
        if self.database_backend == "postgresql":
            rows = self.connection.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = current_schema()
                  AND table_name = 'case_hydraulic_time_series_bindings'
                """
            ).fetchall()
            columns = {str(row["column_name"]) for row in rows}
            if "time_series_set_id" in columns:
                return
            self.connection.execute(
                "ALTER TABLE case_hydraulic_time_series_bindings "
                "RENAME TO case_hydraulic_time_series_bindings_old"
            )
            self.connection.execute(
                """
                CREATE TABLE case_hydraulic_time_series_bindings (
                    id INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                    case_id INTEGER NOT NULL,
                    entity_type TEXT NOT NULL,
                    entity_id INTEGER NOT NULL,
                    signal_key TEXT NOT NULL,
                    hydraulic_time_series_set_id INTEGER,
                    time_series_set_id INTEGER,
                    required INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    created_by TEXT NOT NULL,
                    updated_by TEXT NOT NULL,
                    FOREIGN KEY (case_id) REFERENCES optimization_cases(id) ON DELETE CASCADE,
                    FOREIGN KEY (hydraulic_time_series_set_id)
                        REFERENCES hydraulic_time_series_sets(id) ON DELETE CASCADE,
                    FOREIGN KEY (time_series_set_id)
                        REFERENCES time_series_sets(id) ON DELETE CASCADE,
                    UNIQUE (case_id, entity_type, entity_id, signal_key),
                    CHECK (
                        (hydraulic_time_series_set_id IS NOT NULL AND time_series_set_id IS NULL)
                        OR (hydraulic_time_series_set_id IS NULL AND time_series_set_id IS NOT NULL)
                    )
                )
                """
            )
            self.connection.execute(
                """
                INSERT INTO case_hydraulic_time_series_bindings (
                    id, case_id, entity_type, entity_id, signal_key,
                    hydraulic_time_series_set_id, time_series_set_id,
                    required, created_at, updated_at, created_by, updated_by
                )
                SELECT
                    id, case_id, entity_type, entity_id, signal_key,
                    hydraulic_time_series_set_id, NULL,
                    required, created_at, updated_at, created_by, updated_by
                FROM case_hydraulic_time_series_bindings_old
                """
            )
            self.connection.execute("DROP TABLE case_hydraulic_time_series_bindings_old")
            self.connection.execute(
                """
                SELECT setval(
                    pg_get_serial_sequence('case_hydraulic_time_series_bindings', 'id'),
                    COALESCE((SELECT MAX(id) FROM case_hydraulic_time_series_bindings), 1),
                    true
                )
                """
            )
            return

        columns = {
            row["name"]
            for row in self.connection.execute(
                "PRAGMA table_info(case_hydraulic_time_series_bindings)"
            ).fetchall()
        }
        if "time_series_set_id" in columns:
            return
        self.connection.execute("PRAGMA foreign_keys = OFF")
        self.connection.executescript(
            """
            ALTER TABLE case_hydraulic_time_series_bindings
            RENAME TO case_hydraulic_time_series_bindings_old;

            CREATE TABLE case_hydraulic_time_series_bindings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id INTEGER NOT NULL,
                entity_type TEXT NOT NULL,
                entity_id INTEGER NOT NULL,
                signal_key TEXT NOT NULL,
                hydraulic_time_series_set_id INTEGER,
                time_series_set_id INTEGER,
                required INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                created_by TEXT NOT NULL,
                updated_by TEXT NOT NULL,
                FOREIGN KEY (case_id) REFERENCES optimization_cases(id) ON DELETE CASCADE,
                FOREIGN KEY (hydraulic_time_series_set_id)
                    REFERENCES hydraulic_time_series_sets(id) ON DELETE CASCADE,
                FOREIGN KEY (time_series_set_id)
                    REFERENCES time_series_sets(id) ON DELETE CASCADE,
                UNIQUE (case_id, entity_type, entity_id, signal_key),
                CHECK (
                    (hydraulic_time_series_set_id IS NOT NULL AND time_series_set_id IS NULL)
                    OR (hydraulic_time_series_set_id IS NULL AND time_series_set_id IS NOT NULL)
                )
            );

            INSERT INTO case_hydraulic_time_series_bindings (
                id, case_id, entity_type, entity_id, signal_key,
                hydraulic_time_series_set_id, time_series_set_id,
                required, created_at, updated_at, created_by, updated_by
            )
            SELECT
                id, case_id, entity_type, entity_id, signal_key,
                hydraulic_time_series_set_id, NULL,
                required, created_at, updated_at, created_by, updated_by
            FROM case_hydraulic_time_series_bindings_old;

            DROP TABLE case_hydraulic_time_series_bindings_old;
            """
        )
        self.connection.execute("PRAGMA foreign_keys = ON")

    def _ensure_hydraulic_diagram_items_entity_types_postgres(self) -> None:
        """Refresh the diagram-item entity-type check on PostgreSQL.

        The constraint may predate reach and plant layout support on databases
        created before those iterations, because the SQLite rebuild path does
        not apply to PostgreSQL. Dropping and re-adding it is idempotent and
        only widens the allowed set, so existing rows always remain valid.
        """
        if self.database_backend != "postgresql":
            return
        self.connection.execute(
            "ALTER TABLE case_hydraulic_diagram_items "
            "DROP CONSTRAINT IF EXISTS case_hydraulic_diagram_items_entity_type_check"
        )
        self.connection.execute(
            "ALTER TABLE case_hydraulic_diagram_items "
            "ADD CONSTRAINT case_hydraulic_diagram_items_entity_type_check "
            "CHECK (entity_type IN "
            "('case_hydraulic_node', 'case_hydraulic_reach', 'case_hydraulic_plant'))"
        )

    def count_users(self) -> int:
        row = self.connection.execute("SELECT COUNT(*) AS user_count FROM users").fetchone()
        return int(row["user_count"])

    def create_user(
        self,
        *,
        email: str,
        password_hash: str,
        role: str,
        display_name: str = "",
        is_active: bool = True,
        created_by: str = "system",
    ) -> dict[str, Any]:
        normalized_email = email.strip().lower()
        if not normalized_email:
            raise ValueError("email is required")
        if role not in VALID_USER_ROLES:
            raise ValueError(f"unsupported user role: {role}")
        now = utc_now_iso()
        with self._lock:
            cursor = self.connection.execute(
                """
                INSERT INTO users (
                    email,
                    display_name,
                    role,
                    password_hash,
                    is_active,
                    created_at,
                    updated_at,
                    created_by,
                    deactivated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    normalized_email,
                    display_name.strip(),
                    role,
                    password_hash,
                    1 if is_active else 0,
                    now,
                    now,
                    created_by,
                    None if is_active else now,
                ),
            )
            self.connection.commit()
            return self.get_user(cursor.lastrowid)

    def list_users(self) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            """
            SELECT id, email, display_name, role, password_hash, is_active,
                   created_at, updated_at, created_by, deactivated_at
            FROM users
            ORDER BY id
            """
        ).fetchall()
        return [user_row_to_dict(row) for row in rows]

    def get_user(self, user_id: int) -> dict[str, Any]:
        row = self.connection.execute(
            """
            SELECT id, email, display_name, role, password_hash, is_active,
                   created_at, updated_at, created_by, deactivated_at
            FROM users
            WHERE id = ?
            """,
            (user_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"user {user_id} not found")
        return user_row_to_dict(row)

    def get_user_by_email(self, email: str) -> dict[str, Any]:
        row = self.connection.execute(
            """
            SELECT id, email, display_name, role, password_hash, is_active,
                   created_at, updated_at, created_by, deactivated_at
            FROM users
            WHERE email = ?
            """,
            (email.strip().lower(),),
        ).fetchone()
        if row is None:
            raise KeyError(f"user {email} not found")
        return user_row_to_dict(row)

    def set_user_active(self, user_id: int, is_active: bool, *, updated_by: str = "system") -> dict[str, Any]:
        now = utc_now_iso()
        with self._lock:
            cursor = self.connection.execute(
                """
                UPDATE users
                SET is_active = ?,
                    updated_at = ?,
                    deactivated_at = ?
                WHERE id = ?
                """,
                (1 if is_active else 0, now, None if is_active else now, user_id),
            )
            if cursor.rowcount == 0:
                raise KeyError(f"user {user_id} not found")
            self.connection.commit()
            return self.get_user(user_id)

    def create_auth_session(self, *, user_id: int, token_hash: str, expires_at: str) -> dict[str, Any]:
        self.get_user(user_id)
        now = utc_now_iso()
        with self._lock:
            cursor = self.connection.execute(
                """
                INSERT INTO auth_sessions (user_id, token_hash, created_at, expires_at, revoked_at)
                VALUES (?, ?, ?, ?, NULL)
                """,
                (user_id, token_hash, now, expires_at),
            )
            self.connection.commit()
            return row_to_dict(
                self.connection.execute(
                    """
                    SELECT id, user_id, token_hash, created_at, expires_at, revoked_at
                    FROM auth_sessions
                    WHERE id = ?
                    """,
                    (cursor.lastrowid,),
                ).fetchone()
            )

    def get_user_for_session(self, token_hash: str, *, now: str | None = None) -> dict[str, Any] | None:
        current_time = now or utc_now_iso()
        row = self.connection.execute(
            """
            SELECT
                users.id,
                users.email,
                users.display_name,
                users.role,
                users.password_hash,
                users.is_active,
                users.created_at,
                users.updated_at,
                users.created_by,
                users.deactivated_at
            FROM auth_sessions
            JOIN users ON users.id = auth_sessions.user_id
            WHERE auth_sessions.token_hash = ?
              AND auth_sessions.revoked_at IS NULL
              AND auth_sessions.expires_at > ?
              AND users.is_active = 1
            """,
            (token_hash, current_time),
        ).fetchone()
        if row is None:
            return None
        return user_row_to_dict(row)

    def revoke_auth_session(self, token_hash: str) -> None:
        with self._lock:
            self.connection.execute(
                """
                UPDATE auth_sessions
                SET revoked_at = ?
                WHERE token_hash = ? AND revoked_at IS NULL
                """,
                (utc_now_iso(), token_hash),
            )
            self.connection.commit()

    def create_project(self, *, name: str, description: str = "", created_by: str = "internal_analyst") -> dict[str, Any]:
        created_at = utc_now_iso()
        cursor = self.connection.execute(
            """
            INSERT INTO projects (name, description, created_at, created_by)
            VALUES (?, ?, ?, ?)
            """,
            (name, description, created_at, created_by),
        )
        self.connection.commit()
        return self.get_project(cursor.lastrowid)

    def list_projects(self) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            """
            SELECT id, name, description, created_at, created_by
            FROM projects
            ORDER BY id
            """
        ).fetchall()
        return [row_to_dict(row) for row in rows]

    def get_project(self, project_id: int) -> dict[str, Any]:
        row = self.connection.execute(
            """
            SELECT id, name, description, created_at, created_by
            FROM projects
            WHERE id = ?
            """,
            (project_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"project {project_id} not found")
        return row_to_dict(row)

    def delete_project(self, project_id: int) -> dict[str, Any]:
        with self._lock:
            project = self.get_project(project_id)
            scenario_row = self.connection.execute(
                "SELECT COUNT(*) AS scenario_count FROM scenarios WHERE project_id = ?",
                (project_id,),
            ).fetchone()
            run_row = self.connection.execute(
                """
                SELECT COUNT(*) AS run_count
                FROM runs
                JOIN scenario_versions
                    ON scenario_versions.id = runs.scenario_version_id
                JOIN scenarios
                    ON scenarios.id = scenario_versions.scenario_id
                WHERE scenarios.project_id = ?
                """,
                (project_id,),
            ).fetchone()
            scenario_count = int(scenario_row["scenario_count"])
            run_count = int(run_row["run_count"])
            self.connection.execute(
                "DELETE FROM projects WHERE id = ?",
                (project_id,),
            )
            self.connection.commit()
            return {
                **project,
                "deleted_scenario_count": scenario_count,
                "deleted_run_count": run_count,
            }

    def set_external_project_access(
        self,
        *,
        project_id: int,
        user_id: int,
        portal_view: bool,
        operate: bool,
        updated_by: str,
    ) -> dict[str, Any]:
        self.get_project(project_id)
        user = self.get_user(user_id)
        if user["role"] != "external":
            raise ValueError("project capabilities can only be assigned to external users")
        now = utc_now_iso()
        with self._lock:
            self.connection.execute(
                """
                INSERT INTO project_client_access (
                    project_id, user_id, assigned_at, assigned_by,
                    portal_view, operate, updated_at, updated_by
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(project_id, user_id) DO UPDATE SET
                    portal_view = excluded.portal_view,
                    operate = excluded.operate,
                    updated_at = excluded.updated_at,
                    updated_by = excluded.updated_by
                """,
                (
                    project_id,
                    user_id,
                    now,
                    updated_by,
                    1 if portal_view else 0,
                    1 if operate else 0,
                    now,
                    updated_by,
                ),
            )
            self.connection.commit()
        return self.get_project_external_access(project_id, user_id)

    def get_project_external_access(self, project_id: int, user_id: int) -> dict[str, Any]:
        row = self.connection.execute(
            """
            SELECT project_client_access.project_id,
                   project_client_access.user_id,
                   project_client_access.portal_view,
                   project_client_access.operate,
                   project_client_access.assigned_at,
                   project_client_access.assigned_by,
                   project_client_access.updated_at,
                   project_client_access.updated_by,
                   users.email,
                   users.display_name,
                   users.role,
                   users.is_active
            FROM project_client_access
            JOIN users ON users.id = project_client_access.user_id
            WHERE project_client_access.project_id = ?
              AND project_client_access.user_id = ?
            """,
            (project_id, user_id),
        ).fetchone()
        if row is None:
            raise KeyError(f"external user {user_id} is not assigned to project {project_id}")
        return external_access_row_to_dict(row)

    def list_project_external_access(self, project_id: int) -> list[dict[str, Any]]:
        self.get_project(project_id)
        rows = self.connection.execute(
            """
            SELECT project_client_access.project_id,
                   project_client_access.user_id,
                   project_client_access.portal_view,
                   project_client_access.operate,
                   project_client_access.assigned_at,
                   project_client_access.assigned_by,
                   project_client_access.updated_at,
                   project_client_access.updated_by,
                   users.email,
                   users.display_name,
                   users.role,
                   users.is_active
            FROM project_client_access
            JOIN users ON users.id = project_client_access.user_id
            WHERE project_client_access.project_id = ?
            ORDER BY users.email
            """,
            (project_id,),
        ).fetchall()
        return [external_access_row_to_dict(row) for row in rows]

    def external_has_project_capability(
        self,
        *,
        user_id: int,
        project_id: int,
        capability: str,
    ) -> bool:
        if capability not in {"portal_view", "operate"}:
            raise ValueError(f"unsupported external capability: {capability}")
        row = self.connection.execute(
            f"""
            SELECT 1
            FROM project_client_access
            JOIN users ON users.id = project_client_access.user_id
            WHERE project_client_access.user_id = ?
              AND project_client_access.project_id = ?
              AND users.role = 'external'
              AND users.is_active = 1
              AND project_client_access.{capability} = 1
            """,
            (user_id, project_id),
        ).fetchone()
        return row is not None

    def list_client_projects(self, user_id: int) -> list[dict[str, Any]]:
        user = self.get_user(user_id)
        if user["role"] != "external" or not user["is_active"]:
            return []
        rows = self.connection.execute(
            """
            SELECT projects.id, projects.name, projects.description, projects.created_at, projects.created_by
            FROM project_client_access
            JOIN projects ON projects.id = project_client_access.project_id
            WHERE project_client_access.user_id = ?
              AND project_client_access.portal_view = 1
            ORDER BY projects.id
            """,
            (user_id,),
        ).fetchall()
        return [row_to_dict(row) for row in rows]

    def client_has_project_access(self, *, user_id: int, project_id: int) -> bool:
        return self.external_has_project_capability(
            user_id=user_id,
            project_id=project_id,
            capability="portal_view",
        )

    def revoke_external_project_access(
        self,
        *,
        project_id: int,
        user_id: int,
        updated_by: str,
    ) -> dict[str, Any]:
        self.get_project_external_access(project_id, user_id)
        with self._lock:
            self.connection.execute(
                """
                UPDATE project_client_access
                SET portal_view = 0,
                    operate = 0,
                    updated_at = ?,
                    updated_by = ?
                WHERE project_id = ? AND user_id = ?
                """,
                (utc_now_iso(), updated_by, project_id, user_id),
            )
            self.connection.commit()
        return self.get_project_external_access(project_id, user_id)

    def get_portal_configuration(self, project_id: int) -> dict[str, Any] | None:
        row = self.connection.execute(
            """
            SELECT id, project_id, status, document_json, revision,
                   updated_at, updated_by_user_id
            FROM portal_configurations
            WHERE project_id = ?
            """,
            (project_id,),
        ).fetchone()
        if row is None:
            return None
        return portal_configuration_row_to_dict(row)

    def save_portal_configuration(
        self,
        project_id: int,
        *,
        document: Mapping[str, Any],
        status: str,
        expected_revision: int,
        updated_by_user_id: int | None,
    ) -> dict[str, Any]:
        self.get_project(project_id)
        now = utc_now_iso()
        document_json = json.dumps(document, sort_keys=True)
        with self._lock:
            current = self.get_portal_configuration(project_id)
            current_revision = 0 if current is None else int(current["revision"])
            if int(expected_revision) != current_revision:
                raise StalePortalConfigurationError(
                    "stale portal configuration revision",
                    current_revision=current_revision,
                )
            if current is None:
                self.connection.execute(
                    """
                    INSERT INTO portal_configurations (
                        project_id, status, document_json, revision,
                        updated_at, updated_by_user_id
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (project_id, status, document_json, 1, now, updated_by_user_id),
                )
            else:
                self.connection.execute(
                    """
                    UPDATE portal_configurations
                    SET status = ?,
                        document_json = ?,
                        revision = revision + 1,
                        updated_at = ?,
                        updated_by_user_id = ?
                    WHERE project_id = ?
                    """,
                    (status, document_json, now, updated_by_user_id, project_id),
                )
            self.connection.commit()
        return self.get_portal_configuration(project_id)

    def migrate_dashboard_templates_to_portal_configurations(self) -> int:
        """Give every published project an explicit portal configuration.

        Presentation used to come from the dashboard template attached to each
        publication. Projects that already carry a configuration are left alone,
        and a project without a usable template gets an empty portal instead of
        a permissive fallback.
        """

        rows = self.connection.execute(
            """
            SELECT DISTINCT p.id AS project_id, p.name AS project_name
            FROM projects AS p
            JOIN publications AS pub ON pub.project_id = p.id
            LEFT JOIN portal_configurations AS pc ON pc.project_id = p.id
            WHERE pc.id IS NULL
            ORDER BY p.id
            """
        ).fetchall()
        if not rows:
            return 0

        now = utc_now_iso()
        migrated = 0
        with self._lock:
            for row in rows:
                template = self.connection.execute(
                    """
                    SELECT *
                    FROM dashboard_templates
                    WHERE project_id = ?
                    ORDER BY updated_at DESC, id DESC
                    LIMIT 1
                    """,
                    (row["project_id"],),
                ).fetchone()
                if template is None:
                    document = default_portal_config_document()
                    document["display_name"] = row["project_name"]
                else:
                    document = portal_config_document_from_dashboard_template(
                        dashboard_template_row_to_dict(template),
                        display_name=row["project_name"],
                    )
                self.connection.execute(
                    """
                    INSERT INTO portal_configurations (
                        project_id, status, document_json, revision,
                        updated_at, updated_by_user_id
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row["project_id"],
                        "active",
                        json.dumps(document, sort_keys=True),
                        1,
                        now,
                        None,
                    ),
                )
                migrated += 1
            self.connection.commit()
        return migrated

    def create_dashboard_template(
        self,
        *,
        project_id: int,
        name: str,
        show_summary: bool = True,
        show_price_chart: bool = True,
        show_grid_chart: bool = True,
        show_renewable_chart: bool = True,
        show_bess_chart: bool = True,
        show_hydro_chart: bool = True,
        show_profit_chart: bool = True,
        show_system_dispatch_table: bool = True,
        show_asset_dispatch_table: bool = True,
        table_preview_limit: int = DEFAULT_TABLE_PREVIEW_LIMIT,
        created_by: str = "internal_analyst",
    ) -> dict[str, Any]:
        self.get_project(project_id)
        clean_name = name.strip()
        if not clean_name:
            raise ValueError("dashboard template name is required")
        preview_limit = validate_table_preview_limit(table_preview_limit)
        now = utc_now_iso()
        with self._lock:
            cursor = self.connection.execute(
                """
                INSERT INTO dashboard_templates (
                    project_id,
                    name,
                    show_summary,
                    show_price_chart,
                    show_grid_chart,
                    show_renewable_chart,
                    show_bess_chart,
                    show_hydro_chart,
                    show_profit_chart,
                    show_system_dispatch_table,
                    show_asset_dispatch_table,
                    table_preview_limit,
                    created_at,
                    updated_at,
                    created_by,
                    updated_by
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    project_id,
                    clean_name,
                    bool_to_int(show_summary),
                    bool_to_int(show_price_chart),
                    bool_to_int(show_grid_chart),
                    bool_to_int(show_renewable_chart),
                    bool_to_int(show_bess_chart),
                    bool_to_int(show_hydro_chart),
                    bool_to_int(show_profit_chart),
                    bool_to_int(show_system_dispatch_table),
                    bool_to_int(show_asset_dispatch_table),
                    preview_limit,
                    now,
                    now,
                    created_by,
                    created_by,
                ),
            )
            self.connection.commit()
            return self.get_dashboard_template(cursor.lastrowid)

    def list_dashboard_templates(self, project_id: int) -> list[dict[str, Any]]:
        self.get_project(project_id)
        rows = self.connection.execute(
            """
            SELECT id, project_id, name,
                   show_summary, show_price_chart, show_grid_chart,
                   show_renewable_chart, show_bess_chart, show_hydro_chart,
                   show_profit_chart, show_system_dispatch_table,
                   show_asset_dispatch_table, table_preview_limit,
                   created_at, updated_at, created_by, updated_by
            FROM dashboard_templates
            WHERE project_id = ?
            ORDER BY id
            """,
            (project_id,),
        ).fetchall()
        return [dashboard_template_row_to_dict(row) for row in rows]

    def get_dashboard_template(self, template_id: int) -> dict[str, Any]:
        row = self.connection.execute(
            """
            SELECT id, project_id, name,
                   show_summary, show_price_chart, show_grid_chart,
                   show_renewable_chart, show_bess_chart, show_hydro_chart,
                   show_profit_chart, show_system_dispatch_table,
                   show_asset_dispatch_table, table_preview_limit,
                   created_at, updated_at, created_by, updated_by
            FROM dashboard_templates
            WHERE id = ?
            """,
            (template_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"dashboard template {template_id} not found")
        return dashboard_template_row_to_dict(row)

    def update_dashboard_template(
        self,
        template_id: int,
        *,
        name: str,
        show_summary: bool,
        show_price_chart: bool,
        show_grid_chart: bool,
        show_renewable_chart: bool,
        show_bess_chart: bool,
        show_hydro_chart: bool,
        show_profit_chart: bool,
        show_system_dispatch_table: bool,
        show_asset_dispatch_table: bool,
        table_preview_limit: int,
        updated_by: str = "internal_analyst",
    ) -> dict[str, Any]:
        clean_name = name.strip()
        if not clean_name:
            raise ValueError("dashboard template name is required")
        preview_limit = validate_table_preview_limit(table_preview_limit)
        now = utc_now_iso()
        with self._lock:
            cursor = self.connection.execute(
                """
                UPDATE dashboard_templates
                SET name = ?,
                    show_summary = ?,
                    show_price_chart = ?,
                    show_grid_chart = ?,
                    show_renewable_chart = ?,
                    show_bess_chart = ?,
                    show_hydro_chart = ?,
                    show_profit_chart = ?,
                    show_system_dispatch_table = ?,
                    show_asset_dispatch_table = ?,
                    table_preview_limit = ?,
                    updated_at = ?,
                    updated_by = ?
                WHERE id = ?
                """,
                (
                    clean_name,
                    bool_to_int(show_summary),
                    bool_to_int(show_price_chart),
                    bool_to_int(show_grid_chart),
                    bool_to_int(show_renewable_chart),
                    bool_to_int(show_bess_chart),
                    bool_to_int(show_hydro_chart),
                    bool_to_int(show_profit_chart),
                    bool_to_int(show_system_dispatch_table),
                    bool_to_int(show_asset_dispatch_table),
                    preview_limit,
                    now,
                    updated_by,
                    template_id,
                ),
            )
            if cursor.rowcount == 0:
                raise KeyError(f"dashboard template {template_id} not found")
            self.connection.commit()
            return self.get_dashboard_template(template_id)

    def create_publication_draft(
        self,
        *,
        run_id: int,
        dashboard_template_id: int,
        public_title: str,
        analyst_notes: str = "",
        allowed_artifact_types: list[str] | None = None,
        created_by: str = "internal_analyst",
    ) -> dict[str, Any]:
        lineage = self.get_run_lineage(run_id)
        if lineage["run_status"] != "succeeded":
            raise ValueError("only succeeded runs can be published")
        template = self.get_dashboard_template(dashboard_template_id)
        if template["project_id"] != lineage["project_id"]:
            raise KeyError(f"dashboard template {dashboard_template_id} not found for run {run_id}")
        clean_title = public_title.strip()
        if not clean_title:
            raise ValueError("publication title is required")
        resolved_artifact_types = self._resolve_publication_artifact_types(run_id, allowed_artifact_types)
        now = utc_now_iso()
        with self._lock:
            cursor = self.connection.execute(
                """
                INSERT INTO publications (
                    project_id,
                    scenario_id,
                    scenario_version_id,
                    run_id,
                    dashboard_template_id,
                    public_title,
                    analyst_notes,
                    status,
                    allowed_artifact_types_json,
                    created_at,
                    updated_at,
                    created_by,
                    updated_by
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, 'draft', ?, ?, ?, ?, ?)
                """,
                (
                    lineage["project_id"],
                    lineage["scenario_id"],
                    lineage["scenario_version_id"],
                    run_id,
                    dashboard_template_id,
                    clean_title,
                    analyst_notes.strip(),
                    json.dumps(resolved_artifact_types),
                    now,
                    now,
                    created_by,
                    created_by,
                ),
            )
            self.connection.commit()
            return self.get_publication(cursor.lastrowid)

    def list_run_publications(self, run_id: int) -> list[dict[str, Any]]:
        self.get_run(run_id)
        rows = self.connection.execute(
            """
            SELECT id, project_id, scenario_id, scenario_version_id, run_id,
                   dashboard_template_id, public_title, analyst_notes, status,
                   allowed_artifact_types_json, created_at, updated_at,
                   published_at, unpublished_at, created_by, updated_by,
                   published_by
            FROM publications
            WHERE run_id = ?
            ORDER BY id
            """,
            (run_id,),
        ).fetchall()
        return [publication_row_to_dict(row) for row in rows]

    def get_publication(self, publication_id: int) -> dict[str, Any]:
        row = self.connection.execute(
            """
            SELECT id, project_id, scenario_id, scenario_version_id, run_id,
                   dashboard_template_id, public_title, analyst_notes, status,
                   allowed_artifact_types_json, created_at, updated_at,
                   published_at, unpublished_at, created_by, updated_by,
                   published_by
            FROM publications
            WHERE id = ?
            """,
            (publication_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"publication {publication_id} not found")
        return publication_row_to_dict(row)

    def update_publication_draft(
        self,
        publication_id: int,
        *,
        dashboard_template_id: int,
        public_title: str,
        analyst_notes: str = "",
        allowed_artifact_types: list[str] | None = None,
        updated_by: str = "internal_analyst",
    ) -> dict[str, Any]:
        publication = self.get_publication(publication_id)
        if publication["status"] != "draft":
            raise ValueError("only draft publications can be edited")
        template = self.get_dashboard_template(dashboard_template_id)
        if template["project_id"] != publication["project_id"]:
            raise KeyError(f"dashboard template {dashboard_template_id} not found for publication {publication_id}")
        clean_title = public_title.strip()
        if not clean_title:
            raise ValueError("publication title is required")
        resolved_artifact_types = self._resolve_publication_artifact_types(
            publication["run_id"],
            allowed_artifact_types,
        )
        now = utc_now_iso()
        with self._lock:
            self.connection.execute(
                """
                UPDATE publications
                SET dashboard_template_id = ?,
                    public_title = ?,
                    analyst_notes = ?,
                    allowed_artifact_types_json = ?,
                    updated_at = ?,
                    updated_by = ?
                WHERE id = ?
                """,
                (
                    dashboard_template_id,
                    clean_title,
                    analyst_notes.strip(),
                    json.dumps(resolved_artifact_types),
                    now,
                    updated_by,
                    publication_id,
                ),
            )
            self.connection.commit()
            return self.get_publication(publication_id)

    def publish_publication(
        self,
        publication_id: int,
        *,
        published_by: str = "internal_analyst",
    ) -> dict[str, Any]:
        publication = self.get_publication(publication_id)
        if publication["status"] == "published":
            return publication
        now = utc_now_iso()
        with self._lock:
            self.connection.execute(
                """
                UPDATE publications
                SET status = 'published',
                    updated_at = ?,
                    published_at = ?,
                    unpublished_at = NULL,
                    updated_by = ?,
                    published_by = ?
                WHERE id = ?
                """,
                (now, now, published_by, published_by, publication_id),
            )
            self.connection.commit()
            return self.get_publication(publication_id)

    def unpublish_publication(
        self,
        publication_id: int,
        *,
        unpublished_by: str = "internal_analyst",
    ) -> dict[str, Any]:
        publication = self.get_publication(publication_id)
        if publication["status"] != "published":
            raise ValueError("only published publications can be unpublished")
        now = utc_now_iso()
        with self._lock:
            self.connection.execute(
                """
                UPDATE publications
                SET status = 'unpublished',
                    updated_at = ?,
                    unpublished_at = ?,
                    updated_by = ?
                WHERE id = ?
                """,
                (now, now, unpublished_by, publication_id),
            )
            self.connection.commit()
            return self.get_publication(publication_id)

    def list_published_project_publications(self, project_id: int) -> list[dict[str, Any]]:
        self.get_project(project_id)
        rows = self.connection.execute(
            """
            SELECT id, project_id, scenario_id, scenario_version_id, run_id,
                   dashboard_template_id, public_title, analyst_notes, status,
                   allowed_artifact_types_json, created_at, updated_at,
                   published_at, unpublished_at, created_by, updated_by,
                   published_by
            FROM publications
            WHERE project_id = ?
              AND status = 'published'
            ORDER BY published_at DESC, id DESC
            """,
            (project_id,),
        ).fetchall()
        return [publication_row_to_dict(row) for row in rows]

    def create_scenario(
        self,
        *,
        project_id: int,
        name: str,
        description: str = "",
        created_by: str = "internal_analyst",
    ) -> dict[str, Any]:
        self.get_project(project_id)
        created_at = utc_now_iso()
        cursor = self.connection.execute(
            """
            INSERT INTO scenarios (project_id, name, description, created_at, created_by)
            VALUES (?, ?, ?, ?, ?)
            """,
            (project_id, name, description, created_at, created_by),
        )
        self.connection.commit()
        return self.get_scenario(cursor.lastrowid)

    def list_scenarios(self, project_id: int) -> list[dict[str, Any]]:
        self.get_project(project_id)
        rows = self.connection.execute(
            """
            SELECT id, project_id, name, description, created_at, created_by
            FROM scenarios
            WHERE project_id = ?
            ORDER BY id
            """,
            (project_id,),
        ).fetchall()
        return [row_to_dict(row) for row in rows]

    def get_scenario(self, scenario_id: int) -> dict[str, Any]:
        row = self.connection.execute(
            """
            SELECT id, project_id, name, description, created_at, created_by
            FROM scenarios
            WHERE id = ?
            """,
            (scenario_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"scenario {scenario_id} not found")
        return row_to_dict(row)

    def import_time_series_catalog_set(
        self,
        *,
        scenario_id: int,
        source: dict[str, Any],
        prepared_import: PreparedTimeSeriesCatalogImport,
        created_by: str = "internal_analyst",
    ) -> dict[str, Any]:
        with self._lock:
            scenario = self.get_scenario(scenario_id)
            project_id = int(scenario["project_id"])
            return self._create_time_series_catalog_set(
                project_id=project_id,
                source=source,
                prepared_import=prepared_import,
                created_by=created_by,
            )

    def ingest_connector_time_series_set(
        self,
        *,
        project_id: int,
        source: dict[str, Any],
        prepared_import: PreparedTimeSeriesCatalogImport,
        program: dict[str, Any] | None = None,
        created_by: str = "internal_analyst",
    ) -> dict[str, Any]:
        """Land connector-fetched rows through the common source/set path.

        Same semantics as a file import, different origin: first ingestion
        creates a validated set, an unchanged re-ingest converges without
        writing anything, and changed data advances the set one revision via
        the existing replace path.

        Programmed external data (TS6-007) additionally carries issuer and
        validity metadata, stored per revision so reissues never overwrite
        earlier program versions.
        """
        with self._lock:
            self.get_project(project_id)
            if str(source.get("kind") or "") != "connector":
                raise ValueError(
                    "connector ingestion requires a source with kind 'connector'"
                )
            validated_program: dict[str, Any] | None = None
            if program is not None:
                if prepared_import.data_kind != "programmed":
                    raise ValueError(
                        "program metadata is only allowed for data_kind 'programmed'"
                    )
                validated_program = validate_program_metadata(program)
            elif prepared_import.data_kind == "programmed":
                raise ValueError(
                    "programmed connector data requires program metadata "
                    "(issuer, issued_at, valid_from, valid_until)"
                )
            existing = self.connection.execute(
                """
                SELECT id
                FROM time_series_sets
                WHERE project_id = ? AND name = ? AND version_label = ?
                """,
                (project_id, prepared_import.set_name, prepared_import.version_label),
            ).fetchone()
            extra_revision_metadata = (
                {"program": validated_program} if validated_program else None
            )
            if existing is None:
                created = self._create_time_series_catalog_set(
                    project_id=project_id,
                    source=source,
                    prepared_import=prepared_import,
                    created_by=created_by,
                    change_summary="Initial connector ingestion",
                    extra_revision_metadata=extra_revision_metadata,
                )
                return {"time_series_set": created, "outcome": "created"}

            time_series_set_id = int(existing["id"])
            connector_revision = self.connection.execute(
                """
                SELECT 1
                FROM time_series_set_revisions
                JOIN time_series_sources
                  ON time_series_sources.id = time_series_set_revisions.time_series_source_id
                WHERE time_series_set_revisions.time_series_set_id = ?
                  AND time_series_sources.kind = 'connector'
                LIMIT 1
                """,
                (time_series_set_id,),
            ).fetchone()
            if connector_revision is None:
                raise ValueError(
                    f"time-series set {prepared_import.set_name!r} version "
                    f"{prepared_import.version_label!r} already exists from a "
                    "non-connector source; pick a different set name"
                )
            current = self.get_time_series_set(project_id, time_series_set_id)
            content_unchanged = (
                str(current["content_hash"]) == prepared_import.content_hash
            )
            recorded_program = current.get("revision_metadata", {}).get("program")
            if content_unchanged and (
                validated_program is None or recorded_program == validated_program
            ):
                return {"time_series_set": current, "outcome": "converged"}

            fetched_at = ""
            metadata = source.get("metadata")
            if isinstance(metadata, dict):
                fetched_at = str(metadata.get("fetched_at") or "")
            if content_unchanged:
                # Same values, new issuer/validity: a reissue is its own
                # revision, never an overwrite of the earlier program.
                change_summary = (
                    f"Program re-issued via connector at {fetched_at}"
                    if fetched_at
                    else "Program re-issued via connector"
                )
            else:
                change_summary = (
                    f"Re-ingested from connector at {fetched_at}"
                    if fetched_at
                    else "Re-ingested from connector"
                )
            updated = self.replace_time_series_set_source(
                project_id=project_id,
                time_series_set_id=time_series_set_id,
                source=source,
                prepared_import=prepared_import,
                created_by=created_by,
                change_summary=change_summary,
                extra_revision_metadata=extra_revision_metadata,
            )
            return {"time_series_set": updated, "outcome": "new_revision"}

    def _create_time_series_catalog_set(
        self,
        *,
        project_id: int,
        source: dict[str, Any],
        prepared_import: PreparedTimeSeriesCatalogImport,
        created_by: str = "internal_analyst",
        change_summary: str = "Initial CSV/XLSX catalog import",
        extra_revision_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            now = utc_now_iso()
            source_record = self._get_or_create_time_series_source_record(
                project_id=project_id,
                source=source,
                created_by=created_by,
                now=now,
            )
            existing = self.connection.execute(
                """
                SELECT id
                FROM time_series_sets
                WHERE project_id = ? AND name = ? AND version_label = ?
                """,
                (project_id, prepared_import.set_name, prepared_import.version_label),
            ).fetchone()
            if existing is not None:
                raise ValueError(
                    f"time-series set {prepared_import.set_name!r} already has version_label "
                    f"{prepared_import.version_label!r}"
                )

            version_row = self.connection.execute(
                """
                SELECT COALESCE(MAX(version_number), 0) AS max_version
                FROM time_series_sets
                WHERE project_id = ? AND name = ?
                """,
                (project_id, prepared_import.set_name),
            ).fetchone()
            version_number = int(version_row["max_version"]) + 1
            cursor = self.connection.execute(
                """
                INSERT INTO time_series_sets (
                    project_id,
                    name,
                    version_number,
                    version_label,
                    data_kind,
                    timezone,
                    status,
                    content_hash,
                    created_at,
                    updated_at,
                    created_by,
                    updated_by
                )
                VALUES (?, ?, ?, ?, ?, ?, 'validated', ?, ?, ?, ?, ?)
                """,
                (
                    project_id,
                    prepared_import.set_name,
                    version_number,
                    prepared_import.version_label,
                    prepared_import.data_kind,
                    prepared_import.timezone,
                    prepared_import.content_hash,
                    now,
                    now,
                    created_by,
                    created_by,
                ),
            )
            time_series_set_id = int(cursor.lastrowid)
            try:
                self._insert_time_series_catalog_children(
                    time_series_set_id=time_series_set_id,
                    source=source,
                    source_record=source_record,
                    prepared_import=prepared_import,
                    created_by=created_by,
                    now=now,
                    change_summary=change_summary,
                    extra_revision_metadata=extra_revision_metadata,
                )
            except Exception:
                # PostgreSQL runs autocommit, so a mid-import failure must clean
                # up the already-inserted rows instead of relying on rollback.
                self.connection.rollback()
                self.connection.execute(
                    "DELETE FROM time_series_sets WHERE id = ?",
                    (time_series_set_id,),
                )
                self.connection.commit()
                raise

            self.connection.commit()
            return self.get_time_series_set(project_id, time_series_set_id)

    def _insert_time_series_catalog_children(
        self,
        *,
        time_series_set_id: int,
        source: dict[str, Any],
        source_record: dict[str, Any],
        prepared_import: PreparedTimeSeriesCatalogImport,
        created_by: str,
        now: str,
        change_summary: str = "Initial CSV/XLSX catalog import",
        extra_revision_metadata: dict[str, Any] | None = None,
    ) -> None:
        revision_metadata: dict[str, Any] = {
            "mapping": prepared_import.mapping_summary,
            "source_key": source.get("id"),
        }
        if extra_revision_metadata:
            revision_metadata.update(extra_revision_metadata)
        self.connection.execute(
            """
            INSERT INTO time_series_set_revisions (
                time_series_set_id,
                revision_number,
                time_series_source_id,
                superseded_revision_number,
                content_hash,
                change_summary,
                created_at,
                created_by,
                metadata_json
            )
            VALUES (?, 1, ?, NULL, ?, ?, ?, ?, ?)
            """,
            (
                time_series_set_id,
                int(source_record["id"]),
                prepared_import.content_hash,
                change_summary,
                now,
                created_by,
                json.dumps(revision_metadata, sort_keys=True),
            ),
        )

        self._insert_time_series_signals_periods_values(
            time_series_set_id=time_series_set_id,
            prepared_import=prepared_import,
            now=now,
        )

    def _insert_time_series_signals_periods_values(
        self,
        *,
        time_series_set_id: int,
        prepared_import: PreparedTimeSeriesCatalogImport,
        now: str,
    ) -> None:
        signal_ids_by_key: dict[tuple[str, str | None], int] = {}
        for signal in prepared_import.signals:
            signal_cursor = self.connection.execute(
                """
                INSERT INTO time_series_signals (
                    time_series_set_id,
                    signal_key,
                    unit,
                    source_column,
                    source_unit,
                    entity_type,
                    entity_key,
                    signal_role,
                    aggregation,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, 'input', 'period_average', ?)
                """,
                (
                    time_series_set_id,
                    signal.signal_key,
                    signal.unit,
                    signal.source_column,
                    signal.source_unit,
                    signal.entity_type,
                    signal.entity_key,
                    now,
                ),
            )
            signal_ids_by_key[(signal.signal_key, signal.entity_key)] = int(signal_cursor.lastrowid)
        period_ids_by_index: dict[int, int] = {}
        for period in prepared_import.periods:
            period_cursor = self.connection.execute(
                """
                INSERT INTO time_series_periods (
                    time_series_set_id,
                    period_index,
                    timestamp_start,
                    timestamp_end,
                    duration_hours,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    time_series_set_id,
                    period.period_index,
                    period.timestamp_start,
                    period.timestamp_end,
                    period.duration_hours,
                    now,
                ),
            )
            period_ids_by_index[period.period_index] = int(period_cursor.lastrowid)

        self._bulk_insert_time_series_values(
            time_series_set_id=time_series_set_id,
            values=[
                (
                    signal_ids_by_key[(value.signal_key, value.entity_key)],
                    period_ids_by_index[value.period_index],
                    value.value_numeric,
                    value.source_row_number,
                )
                for value in prepared_import.values
            ],
            now=now,
        )

    def _bulk_insert_time_series_values(
        self,
        *,
        time_series_set_id: int,
        values: list[tuple[int, int, float, int | None]],
        now: str,
    ) -> None:
        self.connection.executemany(
            """
            INSERT INTO time_series_values (
                time_series_set_id,
                time_series_signal_id,
                time_series_period_id,
                value_numeric,
                source_row_number,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    time_series_set_id,
                    signal_id,
                    period_id,
                    value_numeric,
                    source_row_number,
                    now,
                )
                for signal_id, period_id, value_numeric, source_row_number in values
            ],
        )

    def apply_time_series_transformation(
        self,
        *,
        project_id: int,
        time_series_set_id: int,
        transformation_type: str,
        raw_parameters: dict[str, Any],
        output_name: str | None = None,
        output_version_label: str | None = None,
        created_by: str = "internal_analyst",
    ) -> dict[str, Any]:
        with self._lock:
            self.get_project(project_id)
            source_set = self.get_time_series_set(project_id, time_series_set_id)
            definition = get_transformation_definition(transformation_type)
            if definition.multi_input:
                raise TransformationError(
                    f"transformation_type {transformation_type!r} requires multiple "
                    "inputs; apply it via apply_time_series_combination"
                )
            input_set = TransformationInputSet(
                time_series_set_id=time_series_set_id,
                revision_number=source_set["revision_number"],
                content_hash=source_set["content_hash"],
                signals=source_set["signals"],
                periods=source_set["periods"],
                values=source_set["values"],
            )
            parameters = definition.validate_parameters(raw_parameters, input_set)
            parameters_dict = definition.parameters_to_dict(parameters)
            output = definition.execute(input_set, parameters)

            return self._write_derived_time_series_set(
                project_id=project_id,
                transformation_type=transformation_type,
                definition=definition,
                parameters_dict=parameters_dict,
                output=output,
                timezone=source_set["timezone"],
                default_name=f"{source_set['name']}__{transformation_type}",
                output_name=output_name,
                output_version_label=output_version_label,
                created_by=created_by,
            )

    def apply_time_series_combination(
        self,
        *,
        project_id: int,
        transformation_type: str,
        raw_parameters: dict[str, Any],
        output_name: str | None = None,
        output_version_label: str | None = None,
        created_by: str = "internal_analyst",
    ) -> dict[str, Any]:
        with self._lock:
            self.get_project(project_id)
            definition = get_transformation_definition(transformation_type)
            if not definition.multi_input:
                raise TransformationError(
                    f"transformation_type {transformation_type!r} does not accept "
                    "multiple inputs; apply it via apply_time_series_transformation"
                )

            raw_inputs = raw_parameters.get("inputs")
            if not isinstance(raw_inputs, list) or not raw_inputs:
                raise TransformationError(
                    "combine_signals requires a non-empty 'inputs' list"
                )

            source_sets: list[dict[str, Any]] = []
            input_sets: list[TransformationInputSet] = []
            for raw_input in raw_inputs:
                if not isinstance(raw_input, dict) or "time_series_set_id" not in raw_input:
                    raise TransformationError(
                        "each input must be an object naming a time_series_set_id"
                    )
                input_set_id = int(raw_input["time_series_set_id"])
                source_set = self.get_time_series_set(project_id, input_set_id)
                source_sets.append(source_set)
                input_sets.append(
                    TransformationInputSet(
                        time_series_set_id=input_set_id,
                        revision_number=source_set["revision_number"],
                        content_hash=source_set["content_hash"],
                        signals=source_set["signals"],
                        periods=source_set["periods"],
                        values=source_set["values"],
                    )
                )

            parameters = definition.validate_parameters(raw_parameters, input_sets)
            parameters_dict = definition.parameters_to_dict(parameters)
            output = definition.execute(input_sets, parameters)

            default_name = (
                "__".join(source_set["name"] for source_set in source_sets)
                + f"__{transformation_type}"
            )
            return self._write_derived_time_series_set(
                project_id=project_id,
                transformation_type=transformation_type,
                definition=definition,
                parameters_dict=parameters_dict,
                output=output,
                timezone=source_sets[0]["timezone"],
                default_name=default_name,
                output_name=output_name,
                output_version_label=output_version_label,
                created_by=created_by,
            )

    def _write_derived_time_series_set(
        self,
        *,
        project_id: int,
        transformation_type: str,
        definition: TransformationDefinition,
        parameters_dict: dict[str, Any],
        output: TransformationOutput,
        timezone: str,
        default_name: str,
        output_name: str | None,
        output_version_label: str | None,
        created_by: str,
    ) -> dict[str, Any]:
        recipe_hash = self._derived_recipe_hash(
            transformation_type=transformation_type,
            definition=definition,
            parameters_dict=parameters_dict,
            lineage_inputs=output.lineage_inputs,
        )
        existing = self._find_derived_time_series_set_by_recipe_hash(
            project_id=project_id, recipe_hash=recipe_hash
        )
        if existing is not None:
            return existing

        resolved_name = normalize_optional_text(output_name) or default_name
        version_row = self.connection.execute(
            """
            SELECT COALESCE(MAX(version_number), 0) AS max_version
            FROM time_series_sets
            WHERE project_id = ? AND name = ?
            """,
            (project_id, resolved_name),
        ).fetchone()
        version_number = int(version_row["max_version"]) + 1
        resolved_version_label = normalize_optional_text(output_version_label) or (
            f"{transformation_type} v{version_number}"
        )

        prepared_import = self._prepare_derived_catalog_import(
            output=output,
            set_name=resolved_name,
            version_label=resolved_version_label,
            timezone=timezone,
        )
        content_hash = prepared_import.content_hash

        now = utc_now_iso()
        existing_label = self.connection.execute(
            """
            SELECT id FROM time_series_sets
            WHERE project_id = ? AND name = ? AND version_label = ?
            """,
            (project_id, resolved_name, resolved_version_label),
        ).fetchone()
        if existing_label is not None:
            raise ValueError(
                f"time-series set {resolved_name!r} already has version_label "
                f"{resolved_version_label!r}"
            )

        cursor = self.connection.execute(
            """
            INSERT INTO time_series_sets (
                project_id,
                name,
                version_number,
                version_label,
                data_kind,
                timezone,
                status,
                content_hash,
                created_at,
                updated_at,
                created_by,
                updated_by
            )
            VALUES (?, ?, ?, ?, 'derived', ?, 'validated', ?, ?, ?, ?, ?)
            """,
            (
                project_id,
                resolved_name,
                version_number,
                resolved_version_label,
                timezone,
                content_hash,
                now,
                now,
                created_by,
                created_by,
            ),
        )
        derived_set_id = int(cursor.lastrowid)
        try:
            metadata = self._derived_transformation_metadata(
                transformation_type=transformation_type,
                definition=definition,
                parameters_dict=parameters_dict,
                recipe_hash=recipe_hash,
                output=output,
            )
            self.connection.execute(
                """
                INSERT INTO time_series_set_revisions (
                    time_series_set_id,
                    revision_number,
                    time_series_source_id,
                    superseded_revision_number,
                    content_hash,
                    change_summary,
                    created_at,
                    created_by,
                    metadata_json
                )
                VALUES (?, 1, NULL, NULL, ?, ?, ?, ?, ?)
                """,
                (
                    derived_set_id,
                    content_hash,
                    f"Derived via {transformation_type}",
                    now,
                    created_by,
                    json.dumps(metadata, sort_keys=True),
                ),
            )
            self._insert_time_series_signals_periods_values(
                time_series_set_id=derived_set_id,
                prepared_import=prepared_import,
                now=now,
            )
            self._record_derived_set_dependencies(
                derived_set_id=derived_set_id,
                transformation_type=transformation_type,
                definition=definition,
                lineage_inputs=output.lineage_inputs,
                now=now,
            )
        except Exception:
            # PostgreSQL runs autocommit, so a mid-write failure must clean
            # up the already-inserted rows instead of relying on rollback.
            self.connection.rollback()
            self.connection.execute(
                "DELETE FROM time_series_sets WHERE id = ?",
                (derived_set_id,),
            )
            self.connection.commit()
            raise

        self.connection.commit()
        return self.get_time_series_set(project_id, derived_set_id)

    def _find_derived_time_series_set_by_recipe_hash(
        self, *, project_id: int, recipe_hash: str
    ) -> dict[str, Any] | None:
        rows = self.connection.execute(
            """
            SELECT id FROM time_series_sets
            WHERE project_id = ? AND data_kind = 'derived'
            """,
            (project_id,),
        ).fetchall()
        for row in rows:
            derived_set_id = int(row["id"])
            derived_set = self.get_time_series_set(project_id, derived_set_id)
            transformation_meta = derived_set.get("revision_metadata", {}).get(
                "transformation", {}
            )
            if transformation_meta.get("recipe_hash") == recipe_hash:
                return derived_set
        return None

    @staticmethod
    def _derived_recipe_hash(
        *,
        transformation_type: str,
        definition: TransformationDefinition,
        parameters_dict: dict[str, Any],
        lineage_inputs: list[dict[str, Any]],
    ) -> str:
        return catalog_content_hash(
            {
                "transformation_type": transformation_type,
                "implementation_version": definition.implementation_version,
                "parameter_schema_version": definition.parameter_schema_version,
                "parameters": parameters_dict,
                "inputs": lineage_inputs,
            }
        )

    @staticmethod
    def _derived_transformation_metadata(
        *,
        transformation_type: str,
        definition: TransformationDefinition,
        parameters_dict: dict[str, Any],
        recipe_hash: str,
        output: TransformationOutput,
    ) -> dict[str, Any]:
        return {
            "transformation": {
                "type": transformation_type,
                "implementation_version": definition.implementation_version,
                "parameter_schema_version": definition.parameter_schema_version,
                "parameters": parameters_dict,
                "recipe_hash": recipe_hash,
                "inputs": output.lineage_inputs,
                **(
                    {"execution": output.execution_metadata}
                    if output.execution_metadata
                    else {}
                ),
            }
        }

    @staticmethod
    def _prepare_derived_catalog_import(
        *,
        output: TransformationOutput,
        set_name: str,
        version_label: str,
        timezone: str,
    ) -> PreparedTimeSeriesCatalogImport:
        entity_key_by_signal_key = {
            str(signal["signal_key"]): signal.get("entity_key")
            for signal in output.signals
        }
        prepared_signals = [
            CatalogSignal(
                signal_key=str(signal["signal_key"]),
                unit=str(signal["unit"]),
                source_column=str(signal.get("source_column") or ""),
                source_unit=str(signal.get("source_unit") or signal["unit"]),
                entity_type=signal.get("entity_type"),
                entity_key=signal.get("entity_key"),
            )
            for signal in output.signals
        ]
        prepared_periods = [
            CatalogPeriod(
                period_index=int(period["period_index"]),
                timestamp_start=str(period["timestamp_start"]),
                timestamp_end=str(period["timestamp_end"]),
                duration_hours=float(period["duration_hours"]),
            )
            for period in output.periods
        ]
        prepared_values = [
            CatalogValue(
                period_index=int(value["period_index"]),
                signal_key=str(value["signal_key"]),
                value_numeric=float(value["value_numeric"]),
                source_row_number=0,
                entity_key=entity_key_by_signal_key.get(str(value["signal_key"])),
            )
            for value in output.values
        ]
        content_hash = compute_catalog_content_hash(
            set_name=set_name,
            version_label=version_label,
            data_kind="derived",
            timezone=timezone,
            signals=[signal.__dict__ for signal in prepared_signals],
            periods=[period.__dict__ for period in prepared_periods],
            values=[value.__dict__ for value in prepared_values],
        )
        return PreparedTimeSeriesCatalogImport(
            set_name=set_name,
            version_label=version_label,
            data_kind="derived",
            timezone=timezone,
            signals=prepared_signals,
            periods=prepared_periods,
            values=prepared_values,
            content_hash=content_hash,
            mapping_summary={},
        )

    def _record_derived_set_dependencies(
        self,
        *,
        derived_set_id: int,
        transformation_type: str,
        definition: TransformationDefinition,
        lineage_inputs: list[dict[str, Any]],
        now: str,
    ) -> None:
        self.connection.execute(
            "DELETE FROM validation_dependencies WHERE owner_type = 'time_series_set' AND owner_id = ?",
            (derived_set_id,),
        )
        for lineage_input in lineage_inputs:
            self.connection.execute(
                """
                INSERT INTO validation_dependencies (
                    owner_type, owner_id, dependency_type, dependency_id,
                    recorded_hash, created_at, updated_at
                )
                VALUES ('time_series_set', ?, 'time_series_set', ?, ?, ?, ?)
                """,
                (
                    derived_set_id,
                    str(lineage_input["time_series_set_id"]),
                    lineage_input["content_hash"],
                    now,
                    now,
                ),
            )
        self.connection.execute(
            """
            INSERT INTO validation_dependencies (
                owner_type, owner_id, dependency_type, dependency_id,
                recorded_hash, created_at, updated_at
            )
            VALUES ('time_series_set', ?, 'transformation_implementation', ?, ?, ?, ?)
            """,
            (
                derived_set_id,
                transformation_type,
                str(definition.implementation_version),
                now,
                now,
            ),
        )

    def _transformation_input_set(
        self, project_id: int, time_series_set_id: int
    ) -> TransformationInputSet:
        source_set = self.get_time_series_set(project_id, time_series_set_id)
        return TransformationInputSet(
            time_series_set_id=time_series_set_id,
            revision_number=source_set["revision_number"],
            content_hash=source_set["content_hash"],
            signals=source_set["signals"],
            periods=source_set["periods"],
            values=source_set["values"],
        )

    def regenerate_derived_time_series_set(
        self,
        *,
        project_id: int,
        time_series_set_id: int,
        created_by: str = "internal_analyst",
    ) -> dict[str, Any]:
        """Re-execute a derived set's stored recipe against current input revisions.

        Produces a new revision of the same set (never a new set). Converges to
        a no-op when the recipe hash is unchanged, so regenerating a fresh set
        writes nothing. History stays immutable: previous revisions keep their
        content hashes so runs that consumed them remain reproducible.
        """
        with self._lock:
            derived_set = self.get_time_series_set(project_id, time_series_set_id)
            transformation_meta = derived_set.get("revision_metadata", {}).get(
                "transformation"
            )
            if derived_set["data_kind"] != "derived" or not isinstance(
                transformation_meta, dict
            ):
                raise TransformationError(
                    f"time-series set {time_series_set_id} is not a derived set "
                    "with a stored transformation recipe"
                )
            transformation_type = str(transformation_meta.get("type"))
            definition = get_transformation_definition(transformation_type)
            raw_parameters = transformation_meta.get("parameters")
            if not isinstance(raw_parameters, dict):
                raise TransformationError(
                    f"derived time-series set {time_series_set_id} has no stored "
                    "validated parameters"
                )
            stored_inputs = transformation_meta.get("inputs") or []
            if definition.multi_input:
                input_set_ids = [
                    int(entry["time_series_set_id"])
                    for entry in raw_parameters.get("inputs", [])
                    if isinstance(entry, dict)
                ]
            else:
                input_set_ids = [
                    int(entry["time_series_set_id"])
                    for entry in stored_inputs[:1]
                    if isinstance(entry, dict)
                ]
            if not input_set_ids:
                raise TransformationError(
                    f"derived time-series set {time_series_set_id} has no stored "
                    "lineage inputs"
                )
            input_sets = [
                self._transformation_input_set(project_id, input_set_id)
                for input_set_id in input_set_ids
            ]
            validate_arg: Any = input_sets if definition.multi_input else input_sets[0]
            parameters = definition.validate_parameters(raw_parameters, validate_arg)
            parameters_dict = definition.parameters_to_dict(parameters)
            output = definition.execute(validate_arg, parameters)

            recipe_hash = self._derived_recipe_hash(
                transformation_type=transformation_type,
                definition=definition,
                parameters_dict=parameters_dict,
                lineage_inputs=output.lineage_inputs,
            )
            if recipe_hash == transformation_meta.get("recipe_hash"):
                return derived_set

            prepared_import = self._prepare_derived_catalog_import(
                output=output,
                set_name=derived_set["name"],
                version_label=derived_set["version_label"],
                timezone=derived_set["timezone"],
            )
            metadata = self._derived_transformation_metadata(
                transformation_type=transformation_type,
                definition=definition,
                parameters_dict=parameters_dict,
                recipe_hash=recipe_hash,
                output=output,
            )
            now = utc_now_iso()
            previous_revision_number = int(derived_set["revision_number"])
            next_revision_number = previous_revision_number + 1

            snapshot_signals = [
                row_to_dict(row)
                for row in self.connection.execute(
                    """
                    SELECT signal_key, unit, source_column, source_unit, entity_type,
                           entity_key, signal_role, aggregation
                    FROM time_series_signals
                    WHERE time_series_set_id = ?
                    ORDER BY id
                    """,
                    (time_series_set_id,),
                ).fetchall()
            ]
            snapshot_periods = [
                row_to_dict(row)
                for row in self.connection.execute(
                    """
                    SELECT period_index, timestamp_start, timestamp_end, duration_hours
                    FROM time_series_periods
                    WHERE time_series_set_id = ?
                    ORDER BY period_index
                    """,
                    (time_series_set_id,),
                ).fetchall()
            ]
            snapshot_values = [
                row_to_dict(row)
                for row in self.connection.execute(
                    """
                    SELECT
                        time_series_signals.signal_key AS signal_key,
                        time_series_periods.period_index AS period_index,
                        time_series_values.value_numeric AS value_numeric,
                        time_series_values.source_row_number AS source_row_number
                    FROM time_series_values
                    JOIN time_series_signals
                      ON time_series_signals.id = time_series_values.time_series_signal_id
                    JOIN time_series_periods
                      ON time_series_periods.id = time_series_values.time_series_period_id
                    WHERE time_series_values.time_series_set_id = ?
                    """,
                    (time_series_set_id,),
                ).fetchall()
            ]
            snapshot_dependencies = self.get_time_series_set_validation_dependencies(
                time_series_set_id
            )

            try:
                self.connection.execute(
                    "DELETE FROM time_series_signals WHERE time_series_set_id = ?",
                    (time_series_set_id,),
                )
                self.connection.execute(
                    "DELETE FROM time_series_periods WHERE time_series_set_id = ?",
                    (time_series_set_id,),
                )
                self._insert_time_series_signals_periods_values(
                    time_series_set_id=time_series_set_id,
                    prepared_import=prepared_import,
                    now=now,
                )
                self.connection.execute(
                    """
                    INSERT INTO time_series_set_revisions (
                        time_series_set_id,
                        revision_number,
                        time_series_source_id,
                        superseded_revision_number,
                        content_hash,
                        change_summary,
                        created_at,
                        created_by,
                        metadata_json
                    )
                    VALUES (?, ?, NULL, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        time_series_set_id,
                        next_revision_number,
                        previous_revision_number,
                        prepared_import.content_hash,
                        f"Regenerated via {transformation_type}",
                        now,
                        created_by,
                        json.dumps(metadata, sort_keys=True),
                    ),
                )
                self.connection.execute(
                    """
                    UPDATE time_series_sets
                    SET content_hash = ?, updated_at = ?, updated_by = ?
                    WHERE id = ?
                    """,
                    (prepared_import.content_hash, now, created_by, time_series_set_id),
                )
                self._record_derived_set_dependencies(
                    derived_set_id=time_series_set_id,
                    transformation_type=transformation_type,
                    definition=definition,
                    lineage_inputs=output.lineage_inputs,
                    now=now,
                )
            except Exception:
                # PostgreSQL runs autocommit, so a mid-regeneration failure must
                # undo the destructive delete by restoring the captured snapshot
                # and the previous recipe dependencies instead of relying on
                # rollback.
                self.connection.rollback()
                self.connection.execute(
                    """
                    DELETE FROM time_series_set_revisions
                    WHERE time_series_set_id = ? AND revision_number = ?
                    """,
                    (time_series_set_id, next_revision_number),
                )
                self.connection.execute(
                    "DELETE FROM time_series_signals WHERE time_series_set_id = ?",
                    (time_series_set_id,),
                )
                self.connection.execute(
                    "DELETE FROM time_series_periods WHERE time_series_set_id = ?",
                    (time_series_set_id,),
                )
                self._restore_time_series_catalog_snapshot(
                    time_series_set_id=time_series_set_id,
                    signals=snapshot_signals,
                    periods=snapshot_periods,
                    values=snapshot_values,
                    now=now,
                )
                self.connection.execute(
                    "DELETE FROM validation_dependencies WHERE owner_type = 'time_series_set' AND owner_id = ?",
                    (time_series_set_id,),
                )
                for dependency in snapshot_dependencies:
                    self.connection.execute(
                        """
                        INSERT INTO validation_dependencies (
                            owner_type, owner_id, dependency_type, dependency_id,
                            recorded_hash, created_at, updated_at
                        )
                        VALUES ('time_series_set', ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            time_series_set_id,
                            dependency["dependency_type"],
                            dependency["dependency_id"] or "",
                            dependency["hash"],
                            now,
                            now,
                        ),
                    )
                self.connection.commit()
                raise

            self.connection.commit()
            return self.get_time_series_set(project_id, time_series_set_id)

    def get_time_series_set_validation_dependencies(
        self, time_series_set_id: int
    ) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            """
            SELECT dependency_type, dependency_id, recorded_hash
            FROM validation_dependencies
            WHERE owner_type = 'time_series_set' AND owner_id = ?
            ORDER BY dependency_type, dependency_id
            """,
            (time_series_set_id,),
        ).fetchall()
        return [
            {
                "dependency_type": row["dependency_type"],
                "dependency_id": row["dependency_id"] or None,
                "hash": row["recorded_hash"],
            }
            for row in rows
        ]

    def _latest_time_series_set_content_hash(self, time_series_set_id: int) -> str | None:
        row = self.connection.execute(
            """
            SELECT content_hash
            FROM time_series_set_revisions
            WHERE time_series_set_id = ?
            ORDER BY revision_number DESC, id DESC
            LIMIT 1
            """,
            (time_series_set_id,),
        ).fetchone()
        return str(row["content_hash"]) if row is not None else None

    def evaluate_time_series_set_staleness(
        self, project_id: int, time_series_set_id: int
    ) -> dict[str, Any]:
        """Layer-1 derived staleness: does the stored recipe still match its inputs?

        Non-derived sets have no recorded dependencies and are never stale.
        """
        self.get_project(project_id)
        set_row = self.connection.execute(
            "SELECT id FROM time_series_sets WHERE project_id = ? AND id = ?",
            (project_id, time_series_set_id),
        ).fetchone()
        if set_row is None:
            raise KeyError(f"time-series set {time_series_set_id} not found")

        recorded = self.get_time_series_set_validation_dependencies(time_series_set_id)
        current: list[dict[str, Any]] = []
        for dependency in recorded:
            dependency_type = dependency["dependency_type"]
            dependency_id = dependency["dependency_id"]
            if dependency_type == "time_series_set":
                current_hash = self._latest_time_series_set_content_hash(int(dependency_id))
                if current_hash is not None:
                    current.append(
                        {
                            "dependency_type": dependency_type,
                            "dependency_id": dependency_id,
                            "hash": current_hash,
                        }
                    )
            elif dependency_type == "transformation_implementation":
                try:
                    definition = get_transformation_definition(str(dependency_id))
                except TransformationError:
                    continue
                current.append(
                    {
                        "dependency_type": dependency_type,
                        "dependency_id": dependency_id,
                        "hash": str(definition.implementation_version),
                    }
                )
            else:
                current.append(dependency)
        result = evaluate_variant_staleness(
            recorded_dependencies=recorded, current_dependencies=current
        )
        return variant_staleness_result_to_dict(result)

    def replace_time_series_set_source(
        self,
        *,
        project_id: int,
        time_series_set_id: int,
        source: dict[str, Any],
        prepared_import: PreparedTimeSeriesCatalogImport,
        created_by: str = "internal_analyst",
        change_summary: str | None = None,
        extra_revision_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            self.get_project(project_id)
            set_row = self.connection.execute(
                "SELECT id FROM time_series_sets WHERE project_id = ? AND id = ?",
                (project_id, time_series_set_id),
            ).fetchone()
            if set_row is None:
                raise KeyError(f"time-series set {time_series_set_id} not found")

            now = utc_now_iso()
            source_record = self._get_or_create_time_series_source_record(
                project_id=project_id,
                source=source,
                created_by=created_by,
                now=now,
            )

            snapshot_signals = [
                row_to_dict(row)
                for row in self.connection.execute(
                    """
                    SELECT signal_key, unit, source_column, source_unit, entity_type,
                           entity_key, signal_role, aggregation
                    FROM time_series_signals
                    WHERE time_series_set_id = ?
                    ORDER BY id
                    """,
                    (time_series_set_id,),
                ).fetchall()
            ]
            snapshot_periods = [
                row_to_dict(row)
                for row in self.connection.execute(
                    """
                    SELECT period_index, timestamp_start, timestamp_end, duration_hours
                    FROM time_series_periods
                    WHERE time_series_set_id = ?
                    ORDER BY period_index
                    """,
                    (time_series_set_id,),
                ).fetchall()
            ]
            snapshot_values = [
                row_to_dict(row)
                for row in self.connection.execute(
                    """
                    SELECT
                        time_series_signals.signal_key AS signal_key,
                        time_series_periods.period_index AS period_index,
                        time_series_values.value_numeric AS value_numeric,
                        time_series_values.source_row_number AS source_row_number
                    FROM time_series_values
                    JOIN time_series_signals
                      ON time_series_signals.id = time_series_values.time_series_signal_id
                    JOIN time_series_periods
                      ON time_series_periods.id = time_series_values.time_series_period_id
                    WHERE time_series_values.time_series_set_id = ?
                    """,
                    (time_series_set_id,),
                ).fetchall()
            ]

            latest_revision_row = self.connection.execute(
                """
                SELECT revision_number
                FROM time_series_set_revisions
                WHERE time_series_set_id = ?
                ORDER BY revision_number DESC
                LIMIT 1
                """,
                (time_series_set_id,),
            ).fetchone()
            latest_revision_number = int(latest_revision_row["revision_number"]) if latest_revision_row else 0
            next_revision_number = latest_revision_number + 1

            try:
                self.connection.execute(
                    "DELETE FROM time_series_signals WHERE time_series_set_id = ?",
                    (time_series_set_id,),
                )
                self.connection.execute(
                    "DELETE FROM time_series_periods WHERE time_series_set_id = ?",
                    (time_series_set_id,),
                )
                self._insert_time_series_signals_periods_values(
                    time_series_set_id=time_series_set_id,
                    prepared_import=prepared_import,
                    now=now,
                )
                self.connection.execute(
                    """
                    INSERT INTO time_series_set_revisions (
                        time_series_set_id,
                        revision_number,
                        time_series_source_id,
                        superseded_revision_number,
                        content_hash,
                        change_summary,
                        created_at,
                        created_by,
                        metadata_json
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        time_series_set_id,
                        next_revision_number,
                        int(source_record["id"]),
                        latest_revision_number or None,
                        prepared_import.content_hash,
                        change_summary or "Replaced via new file upload",
                        now,
                        created_by,
                        json.dumps(
                            {
                                "mapping": prepared_import.mapping_summary,
                                "source_key": source.get("id"),
                                **(extra_revision_metadata or {}),
                            },
                            sort_keys=True,
                        ),
                    ),
                )
                self.connection.execute(
                    """
                    UPDATE time_series_sets
                    SET content_hash = ?, updated_at = ?, updated_by = ?
                    WHERE id = ?
                    """,
                    (prepared_import.content_hash, now, created_by, time_series_set_id),
                )
            except Exception:
                # PostgreSQL runs autocommit, so a mid-replace failure must undo
                # the destructive delete by restoring the captured snapshot
                # instead of relying on rollback.
                self.connection.rollback()
                self.connection.execute(
                    """
                    DELETE FROM time_series_set_revisions
                    WHERE time_series_set_id = ? AND revision_number = ?
                    """,
                    (time_series_set_id, next_revision_number),
                )
                self.connection.execute(
                    "DELETE FROM time_series_signals WHERE time_series_set_id = ?",
                    (time_series_set_id,),
                )
                self.connection.execute(
                    "DELETE FROM time_series_periods WHERE time_series_set_id = ?",
                    (time_series_set_id,),
                )
                self._restore_time_series_catalog_snapshot(
                    time_series_set_id=time_series_set_id,
                    signals=snapshot_signals,
                    periods=snapshot_periods,
                    values=snapshot_values,
                    now=now,
                )
                self.connection.commit()
                raise

            self.connection.commit()
            return self.get_time_series_set(project_id, time_series_set_id)

    def _restore_time_series_catalog_snapshot(
        self,
        *,
        time_series_set_id: int,
        signals: list[dict[str, Any]],
        periods: list[dict[str, Any]],
        values: list[dict[str, Any]],
        now: str,
    ) -> None:
        signal_ids_by_key: dict[str, int] = {}
        for signal in signals:
            signal_cursor = self.connection.execute(
                """
                INSERT INTO time_series_signals (
                    time_series_set_id,
                    signal_key,
                    unit,
                    source_column,
                    source_unit,
                    entity_type,
                    entity_key,
                    signal_role,
                    aggregation,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    time_series_set_id,
                    signal["signal_key"],
                    signal["unit"],
                    signal["source_column"],
                    signal["source_unit"],
                    signal["entity_type"],
                    signal["entity_key"],
                    signal["signal_role"],
                    signal["aggregation"],
                    now,
                ),
            )
            signal_ids_by_key[str(signal["signal_key"])] = int(signal_cursor.lastrowid)

        period_ids_by_index: dict[int, int] = {}
        for period in periods:
            period_cursor = self.connection.execute(
                """
                INSERT INTO time_series_periods (
                    time_series_set_id,
                    period_index,
                    timestamp_start,
                    timestamp_end,
                    duration_hours,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    time_series_set_id,
                    period["period_index"],
                    period["timestamp_start"],
                    period["timestamp_end"],
                    period["duration_hours"],
                    now,
                ),
            )
            period_ids_by_index[int(period["period_index"])] = int(period_cursor.lastrowid)

        self._bulk_insert_time_series_values(
            time_series_set_id=time_series_set_id,
            values=[
                (
                    signal_ids_by_key[str(value["signal_key"])],
                    period_ids_by_index[int(value["period_index"])],
                    float(value["value_numeric"]),
                    int(value["source_row_number"]) if value["source_row_number"] is not None else None,
                )
                for value in values
            ],
            now=now,
        )

    def extract_draft_time_series_set(
        self,
        *,
        scenario_id: int,
        source_id: str,
        set_name: str,
        version_label: str,
        data_kind: str,
        timezone_name: str,
        created_by: str = "internal_analyst",
    ) -> dict[str, Any]:
        with self._lock:
            scenario = self.get_scenario(scenario_id)
            project_id = int(scenario["project_id"])
            draft = self.get_scenario_draft(scenario_id)
            prepared = prepare_draft_series_extraction(
                document=draft["document"],
                source_id=source_id,
                set_name=set_name,
                version_label=version_label,
                data_kind=data_kind,
                timezone_name=timezone_name,
            )
            source = find_source(draft["document"], source_id)
            now = utc_now_iso()

            existing_extraction = self.connection.execute(
                """
                SELECT time_series_set_id, content_hash
                FROM time_series_set_extractions
                WHERE scenario_id = ? AND source_id = ?
                """,
                (scenario_id, source_id),
            ).fetchone()
            if existing_extraction is not None:
                time_series_set_id = int(existing_extraction["time_series_set_id"])
                if str(existing_extraction["content_hash"]) == prepared.content_hash:
                    return self.get_time_series_set(project_id, time_series_set_id)
                raise ValueError(
                    f"time-series source {source_id!r} was already extracted into "
                    f"time-series set {time_series_set_id}; its validated data has since "
                    "changed. Edit values on the extracted set or use a new version_label "
                    "instead of re-extracting."
                )

            name_conflict = self.connection.execute(
                """
                SELECT id FROM time_series_sets
                WHERE project_id = ? AND name = ? AND version_label = ?
                """,
                (project_id, prepared.set_name, prepared.version_label),
            ).fetchone()
            if name_conflict is not None:
                raise ValueError(
                    f"time-series set {prepared.set_name!r} already has version_label "
                    f"{prepared.version_label!r}"
                )

            time_series_set_id = self._insert_draft_extraction_set(
                project_id=project_id,
                scenario_id=scenario_id,
                source_id=source_id,
                source=source,
                prepared=prepared,
                created_by=created_by,
                now=now,
            )
            self.connection.execute(
                """
                INSERT INTO time_series_set_extractions (
                    time_series_set_id, scenario_id, source_id, content_hash,
                    extracted_at, extracted_by
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (time_series_set_id, scenario_id, source_id, prepared.content_hash, now, created_by),
            )
            self.connection.commit()
            return self.get_time_series_set(project_id, time_series_set_id)

    def _insert_draft_extraction_set(
        self,
        *,
        project_id: int,
        scenario_id: int,
        source_id: str,
        source: dict[str, Any],
        prepared: PreparedDraftSeriesExtraction,
        created_by: str,
        now: str,
    ) -> int:
        source_record = self._get_or_create_time_series_source_record(
            project_id=project_id,
            source=source,
            created_by=created_by,
            now=now,
        )
        version_row = self.connection.execute(
            """
            SELECT COALESCE(MAX(version_number), 0) AS max_version
            FROM time_series_sets
            WHERE project_id = ? AND name = ?
            """,
            (project_id, prepared.set_name),
        ).fetchone()
        version_number = int(version_row["max_version"]) + 1
        cursor = self.connection.execute(
            """
            INSERT INTO time_series_sets (
                project_id,
                name,
                version_number,
                version_label,
                data_kind,
                timezone,
                status,
                content_hash,
                created_at,
                updated_at,
                created_by,
                updated_by
            )
            VALUES (?, ?, ?, ?, ?, ?, 'validated', ?, ?, ?, ?, ?)
            """,
            (
                project_id,
                prepared.set_name,
                version_number,
                prepared.version_label,
                prepared.data_kind,
                prepared.timezone,
                prepared.content_hash,
                now,
                now,
                created_by,
                created_by,
            ),
        )
        time_series_set_id = int(cursor.lastrowid)
        try:
            origin_metadata = {
                "origin": {
                    "kind": "legacy_draft_extraction",
                    "scenario_id": scenario_id,
                    "source_id": source_id,
                    "source_filename": source.get("original_filename"),
                    "source_checksum": source.get("checksum"),
                    "extracted_by": created_by,
                    "extracted_at": now,
                }
            }
            self.connection.execute(
                """
                INSERT INTO time_series_set_revisions (
                    time_series_set_id,
                    revision_number,
                    time_series_source_id,
                    superseded_revision_number,
                    content_hash,
                    change_summary,
                    created_at,
                    created_by,
                    metadata_json
                )
                VALUES (?, 1, ?, NULL, ?, ?, ?, ?, ?)
                """,
                (
                    time_series_set_id,
                    int(source_record["id"]),
                    prepared.content_hash,
                    "Extracted from legacy draft",
                    now,
                    created_by,
                    json.dumps(origin_metadata, sort_keys=True),
                ),
            )
            self._insert_time_series_signals_periods_values(
                time_series_set_id=time_series_set_id,
                prepared_import=prepared,
                now=now,
            )
        except Exception:
            self.connection.rollback()
            self.connection.execute(
                "DELETE FROM time_series_sets WHERE id = ?",
                (time_series_set_id,),
            )
            self.connection.commit()
            raise
        return time_series_set_id

    def list_time_series_sets(self, project_id: int) -> list[dict[str, Any]]:
        self.get_project(project_id)
        rows = self.connection.execute(
            """
            SELECT
                time_series_sets.id AS id,
                time_series_sets.name AS name,
                time_series_sets.version_number AS version_number,
                time_series_sets.version_label AS version_label,
                time_series_sets.data_kind AS data_kind,
                time_series_sets.timezone AS timezone,
                time_series_sets.status AS status,
                time_series_sets.created_at AS created_at,
                time_series_sets.updated_at AS updated_at,
                latest_revision.revision_number AS revision_number,
                latest_revision.content_hash AS content_hash,
                latest_revision.metadata_json AS metadata_json,
                (
                    SELECT COUNT(*) FROM time_series_signals
                    WHERE time_series_signals.time_series_set_id = time_series_sets.id
                ) AS signal_count,
                (
                    SELECT COUNT(*) FROM time_series_periods
                    WHERE time_series_periods.time_series_set_id = time_series_sets.id
                ) AS period_count
            FROM time_series_sets
            JOIN (
                SELECT r1.time_series_set_id, r1.revision_number, r1.content_hash,
                       r1.metadata_json
                FROM time_series_set_revisions AS r1
                WHERE r1.revision_number = (
                    SELECT MAX(r2.revision_number)
                    FROM time_series_set_revisions AS r2
                    WHERE r2.time_series_set_id = r1.time_series_set_id
                )
            ) AS latest_revision
              ON latest_revision.time_series_set_id = time_series_sets.id
            WHERE time_series_sets.project_id = ?
            ORDER BY time_series_sets.name, time_series_sets.version_number
            """,
            (project_id,),
        ).fetchall()
        current_hash_by_set_id = {int(row["id"]): str(row["content_hash"]) for row in rows}
        stale_by_set_id = self._derived_staleness_flags(current_hash_by_set_id)
        return [
            {
                "id": int(row["id"]),
                "project_id": project_id,
                "name": str(row["name"]),
                "version_number": int(row["version_number"]),
                "version_label": str(row["version_label"]),
                "data_kind": str(row["data_kind"]),
                "timezone": str(row["timezone"]),
                "status": str(row["status"]),
                "revision_number": int(row["revision_number"]),
                "content_hash": str(row["content_hash"]),
                "signal_count": int(row["signal_count"]),
                "period_count": int(row["period_count"]),
                "stale": stale_by_set_id.get(int(row["id"]), False),
                "program": _parse_program_from_metadata_json(row["metadata_json"]),
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
            for row in rows
        ]

    def _derived_staleness_flags(
        self, current_hash_by_set_id: dict[int, str]
    ) -> dict[int, bool]:
        """Batch Layer-1 staleness for one project's catalog listing.

        Input hashes come from the listing itself: transformation inputs always
        live in the same project as their derived set.
        """
        if not current_hash_by_set_id:
            return {}
        rows = self.connection.execute(
            """
            SELECT owner_id, dependency_type, dependency_id, recorded_hash
            FROM validation_dependencies
            WHERE owner_type = 'time_series_set'
            """
        ).fetchall()
        stale_by_set_id: dict[int, bool] = {}
        for row in rows:
            owner_id = int(row["owner_id"])
            if owner_id not in current_hash_by_set_id:
                continue
            if stale_by_set_id.get(owner_id):
                continue
            dependency_type = str(row["dependency_type"])
            recorded_hash = str(row["recorded_hash"])
            if dependency_type == "time_series_set":
                current_hash = current_hash_by_set_id.get(int(row["dependency_id"]))
                stale_by_set_id[owner_id] = current_hash != recorded_hash
            elif dependency_type == "transformation_implementation":
                try:
                    definition = get_transformation_definition(str(row["dependency_id"]))
                except TransformationError:
                    stale_by_set_id[owner_id] = True
                    continue
                stale_by_set_id[owner_id] = (
                    str(definition.implementation_version) != recorded_hash
                )
        return stale_by_set_id

    _HYDRAULIC_TIME_SERIES_CATALOG_COLUMNS = """
        hydraulic_time_series_sets.id AS id,
        hydraulic_time_series_sets.project_id AS project_id,
        hydraulic_time_series_sets.entity_type AS entity_type,
        hydraulic_time_series_sets.entity_id AS entity_id,
        hydraulic_time_series_sets.signal_key AS signal_key,
        hydraulic_time_series_sets.version_number AS version_number,
        hydraulic_time_series_sets.version_label AS version_label,
        hydraulic_time_series_sets.content_hash AS content_hash,
        hydraulic_time_series_sets.status AS status,
        hydraulic_time_series_sets.created_at AS created_at,
        hydraulic_time_series_sets.updated_at AS updated_at,
        COALESCE(hydraulic_nodes.display_name, hydraulic_reaches.display_name) AS entity_display_name,
        COALESCE(hydraulic_nodes.node_key, hydraulic_reaches.reach_key) AS entity_key,
        COALESCE(node_system.display_name, reach_system.display_name) AS hydraulic_system_name,
        (
            SELECT COUNT(*) FROM hydraulic_time_series_points
            WHERE hydraulic_time_series_points.hydraulic_time_series_set_id = hydraulic_time_series_sets.id
        ) AS period_count,
        hydraulic_time_series_set_migrations.time_series_set_id AS migrated_time_series_set_id,
        migrated_time_series_set.name AS migrated_time_series_set_name,
        migrated_time_series_set.version_label AS migrated_time_series_set_version_label,
        hydraulic_time_series_set_migrations.migrated_by AS migrated_by,
        hydraulic_time_series_set_migrations.migrated_at AS migrated_at
    """

    _HYDRAULIC_TIME_SERIES_CATALOG_JOINS = """
        FROM hydraulic_time_series_sets
        LEFT JOIN hydraulic_nodes
          ON hydraulic_time_series_sets.entity_type = 'hydraulic_node'
         AND hydraulic_nodes.id = hydraulic_time_series_sets.entity_id
        LEFT JOIN hydraulic_reaches
          ON hydraulic_time_series_sets.entity_type = 'hydraulic_reach'
         AND hydraulic_reaches.id = hydraulic_time_series_sets.entity_id
        LEFT JOIN hydraulic_systems AS node_system
          ON node_system.id = hydraulic_nodes.hydraulic_system_id
        LEFT JOIN hydraulic_systems AS reach_system
          ON reach_system.id = hydraulic_reaches.hydraulic_system_id
        LEFT JOIN hydraulic_time_series_set_migrations
          ON hydraulic_time_series_set_migrations.hydraulic_time_series_set_id = hydraulic_time_series_sets.id
        LEFT JOIN time_series_sets AS migrated_time_series_set
          ON migrated_time_series_set.id = hydraulic_time_series_set_migrations.time_series_set_id
    """

    def list_hydraulic_time_series_sets(self, project_id: int) -> list[dict[str, Any]]:
        self.get_project(project_id)
        rows = self.connection.execute(
            "SELECT " + self._HYDRAULIC_TIME_SERIES_CATALOG_COLUMNS
            + self._HYDRAULIC_TIME_SERIES_CATALOG_JOINS
            + """
            WHERE hydraulic_time_series_sets.project_id = ?
            ORDER BY hydraulic_time_series_sets.entity_type, hydraulic_time_series_sets.entity_id,
                     hydraulic_time_series_sets.signal_key, hydraulic_time_series_sets.version_number
            """,
            (project_id,),
        ).fetchall()
        return [
            build_hydraulic_catalog_summary(row_to_dict(row))
            for row in rows
        ]

    def get_hydraulic_time_series_set(
        self, project_id: int, hydraulic_time_series_set_id: int
    ) -> dict[str, Any]:
        self.get_project(project_id)
        row = self.connection.execute(
            "SELECT " + self._HYDRAULIC_TIME_SERIES_CATALOG_COLUMNS
            + self._HYDRAULIC_TIME_SERIES_CATALOG_JOINS
            + """
            WHERE hydraulic_time_series_sets.project_id = ?
              AND hydraulic_time_series_sets.id = ?
            """,
            (project_id, hydraulic_time_series_set_id),
        ).fetchone()
        if row is None:
            raise KeyError(f"hydraulic time-series set {hydraulic_time_series_set_id} not found")
        points = self._load_inflow_series_points(hydraulic_time_series_set_id)
        return build_hydraulic_catalog_detail(row_to_dict(row), points)

    def migrate_hydraulic_time_series_set(
        self,
        *,
        project_id: int,
        hydraulic_time_series_set_id: int,
        migrated_by: str = "internal_analyst",
    ) -> dict[str, Any]:
        """Migrate one legacy hydraulic series set into the generic catalog.

        On demand, per BESS-TS5-004: never automatic/bulk-by-default. Reuses
        ``_write_generic_hydraulic_time_series_set``'s name/content-hash
        idempotency so a migrated set converges with any generic set already
        written for the same entity+signal (e.g. by a live diagram resave
        after TS5-003). A dedicated ledger table
        (``hydraulic_time_series_set_migrations``) makes re-running the same
        migration a stable no-op even before that content-hash check runs.
        """
        with self._lock:
            self.get_project(project_id)
            legacy_row = self.connection.execute(
                """
                SELECT id, entity_type, entity_id, signal_key, version_number,
                       version_label, content_hash
                FROM hydraulic_time_series_sets
                WHERE project_id = ? AND id = ?
                """,
                (project_id, hydraulic_time_series_set_id),
            ).fetchone()
            if legacy_row is None:
                raise KeyError(
                    f"hydraulic time-series set {hydraulic_time_series_set_id} not found"
                )

            existing_migration = self.connection.execute(
                """
                SELECT time_series_set_id
                FROM hydraulic_time_series_set_migrations
                WHERE hydraulic_time_series_set_id = ?
                """,
                (hydraulic_time_series_set_id,),
            ).fetchone()
            if existing_migration is not None:
                return {
                    "time_series_set": self.get_time_series_set(
                        project_id, int(existing_migration["time_series_set_id"])
                    ),
                    "hydraulic_time_series_set_id": hydraulic_time_series_set_id,
                    "already_migrated": True,
                }

            points = self._load_inflow_series_points(hydraulic_time_series_set_id)
            if not points:
                raise ValueError(
                    f"hydraulic time-series set {hydraulic_time_series_set_id} has no "
                    "points to migrate"
                )

            entity_type = str(legacy_row["entity_type"])
            entity_id = int(legacy_row["entity_id"])
            signal_key = str(legacy_row["signal_key"])
            now = utc_now_iso()
            revision_metadata = {
                "origin": {
                    "kind": "hydraulic_legacy_migration",
                    "hydraulic_time_series_set_id": hydraulic_time_series_set_id,
                    "entity_type": entity_type,
                    "entity_id": entity_id,
                    "signal_key": signal_key,
                    "legacy_version_number": int(legacy_row["version_number"]),
                    "legacy_version_label": str(legacy_row["version_label"]),
                    "legacy_content_hash": legacy_row["content_hash"],
                    "migrated_by": migrated_by,
                    "migrated_at": now,
                }
            }
            time_series_set_id = self._write_generic_hydraulic_time_series_set(
                project_id=project_id,
                base_entity_type=entity_type,
                base_entity_id=entity_id,
                signal_key=signal_key,
                points=points,
                version_label=f"migrated-{legacy_row['version_label']}",
                updated_by=migrated_by,
                now=now,
                status="validated",
                revision_metadata=revision_metadata,
                change_summary="Migrated from legacy hydraulic series set",
            )
            self.connection.execute(
                """
                INSERT INTO hydraulic_time_series_set_migrations (
                    hydraulic_time_series_set_id, time_series_set_id, content_hash,
                    migrated_at, migrated_by
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    hydraulic_time_series_set_id,
                    time_series_set_id,
                    hydraulic_inflow_series_content_hash(points),
                    now,
                    migrated_by,
                ),
            )
            self.connection.commit()
            return {
                "time_series_set": self.get_time_series_set(project_id, time_series_set_id),
                "hydraulic_time_series_set_id": hydraulic_time_series_set_id,
                "already_migrated": False,
            }

    def migrate_all_hydraulic_time_series_sets(
        self,
        *,
        project_id: int,
        migrated_by: str = "internal_analyst",
    ) -> dict[str, Any]:
        """Sweep every legacy hydraulic set of a project, converging stably.

        Reports migrated/skipped/failed lists rather than raising, so a
        partial failure (e.g. one empty legacy set) does not abort the sweep
        for the rest of the project, and repeated runs report the same shape
        (everything ends up ``skipped`` once migrated).
        """
        self.get_project(project_id)
        legacy_ids = [
            int(row["id"])
            for row in self.connection.execute(
                "SELECT id FROM hydraulic_time_series_sets WHERE project_id = ? ORDER BY id",
                (project_id,),
            ).fetchall()
        ]
        migrated: list[int] = []
        skipped: list[int] = []
        failed: list[dict[str, Any]] = []
        for legacy_id in legacy_ids:
            try:
                result = self.migrate_hydraulic_time_series_set(
                    project_id=project_id,
                    hydraulic_time_series_set_id=legacy_id,
                    migrated_by=migrated_by,
                )
            except ValueError as error:
                failed.append({"hydraulic_time_series_set_id": legacy_id, "error": str(error)})
                continue
            if result["already_migrated"]:
                skipped.append(legacy_id)
            else:
                migrated.append(legacy_id)
        return {"migrated": migrated, "skipped": skipped, "failed": failed}

    def get_time_series_set(self, project_id: int, time_series_set_id: int) -> dict[str, Any]:
        self.get_project(project_id)
        row = self.connection.execute(
            """
            SELECT
                id,
                project_id,
                name,
                version_number,
                version_label,
                data_kind,
                timezone,
                status,
                content_hash,
                created_at,
                updated_at
            FROM time_series_sets
            WHERE project_id = ? AND id = ?
            """,
            (project_id, time_series_set_id),
        ).fetchone()
        if row is None:
            raise KeyError(f"time-series set {time_series_set_id} not found")

        revision_row = self.connection.execute(
            """
            SELECT
                id,
                revision_number,
                time_series_source_id,
                superseded_revision_number,
                content_hash,
                change_summary,
                created_at,
                created_by,
                metadata_json
            FROM time_series_set_revisions
            WHERE time_series_set_id = ?
            ORDER BY revision_number DESC, id DESC
            LIMIT 1
            """,
            (time_series_set_id,),
        ).fetchone()
        if revision_row is None:
            raise KeyError(f"time-series set {time_series_set_id} has no revisions")

        signal_rows = self.connection.execute(
            """
            SELECT
                signal_key,
                unit,
                entity_type,
                entity_key,
                source_column,
                source_unit
            FROM time_series_signals
            WHERE time_series_set_id = ?
            ORDER BY id
            """,
            (time_series_set_id,),
        ).fetchall()
        period_rows = self.connection.execute(
            """
            SELECT period_index, timestamp_start, timestamp_end, duration_hours
            FROM time_series_periods
            WHERE time_series_set_id = ?
            ORDER BY period_index
            """,
            (time_series_set_id,),
        ).fetchall()
        value_rows = self.connection.execute(
            """
            SELECT
                time_series_periods.period_index,
                time_series_signals.signal_key,
                time_series_values.value_numeric
            FROM time_series_values
            JOIN time_series_periods
              ON time_series_periods.id = time_series_values.time_series_period_id
            JOIN time_series_signals
              ON time_series_signals.id = time_series_values.time_series_signal_id
            WHERE time_series_values.time_series_set_id = ?
            ORDER BY time_series_periods.period_index, time_series_signals.signal_key
            """,
            (time_series_set_id,),
        ).fetchall()

        revision_metadata: dict[str, Any] = {}
        metadata_json = revision_row["metadata_json"]
        if metadata_json:
            try:
                parsed_metadata = json.loads(str(metadata_json))
            except json.JSONDecodeError:
                parsed_metadata = {}
            if isinstance(parsed_metadata, dict):
                revision_metadata = parsed_metadata

        source = self._get_time_series_source_by_id(
            int(revision_row["time_series_source_id"])
            if revision_row["time_series_source_id"] is not None
            else None
        )

        return {
            "id": int(row["id"]),
            "project_id": int(row["project_id"]),
            "name": str(row["name"]),
            "version_number": int(row["version_number"]),
            "version_label": str(row["version_label"]),
            "revision_number": int(revision_row["revision_number"]),
            "data_kind": str(row["data_kind"]),
            "timezone": str(row["timezone"]),
            "status": str(row["status"]),
            "content_hash": str(revision_row["content_hash"]),
            "source_checksum": source["checksum"] if isinstance(source, dict) else None,
            "signal_count": len(signal_rows),
            "period_count": len(period_rows),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "source": source,
            "horizon": {
                "period_count": len(period_rows),
                "start": str(period_rows[0]["timestamp_start"]) if period_rows else None,
                "end": str(period_rows[-1]["timestamp_end"]) if period_rows else None,
            },
            "revision_metadata": revision_metadata,
            "signals": [
                {
                    "signal_key": signal_row["signal_key"],
                    "unit": signal_row["unit"],
                    "source_column": signal_row["source_column"],
                    "source_unit": signal_row["source_unit"],
                    "entity_type": signal_row["entity_type"],
                    "entity_key": signal_row["entity_key"],
                }
                for signal_row in signal_rows
            ],
            "periods": [
                {
                    "period_index": int(period_row["period_index"]),
                    "timestamp_start": str(period_row["timestamp_start"]),
                    "timestamp_end": str(period_row["timestamp_end"]),
                    "duration_hours": float(period_row["duration_hours"]),
                }
                for period_row in period_rows
            ],
            "values": [
                {
                    "period_index": int(value_row["period_index"]),
                    "signal_key": str(value_row["signal_key"]),
                    "value_numeric": float(value_row["value_numeric"]),
                }
                for value_row in value_rows
            ],
        }

    def list_time_series_set_revisions(
        self, project_id: int, time_series_set_id: int
    ) -> list[dict[str, Any]]:
        self.get_project(project_id)
        set_row = self.connection.execute(
            "SELECT id FROM time_series_sets WHERE project_id = ? AND id = ?",
            (project_id, time_series_set_id),
        ).fetchone()
        if set_row is None:
            raise KeyError(f"time-series set {time_series_set_id} not found")

        rows = self.connection.execute(
            """
            SELECT
                revision_number,
                time_series_source_id,
                superseded_revision_number,
                content_hash,
                change_summary,
                created_at,
                created_by,
                metadata_json
            FROM time_series_set_revisions
            WHERE time_series_set_id = ?
            ORDER BY revision_number DESC
            """,
            (time_series_set_id,),
        ).fetchall()
        revisions: list[dict[str, Any]] = []
        for row in rows:
            source = self._get_time_series_source_by_id(
                int(row["time_series_source_id"]) if row["time_series_source_id"] is not None else None
            )
            revisions.append(
                {
                    "revision_number": int(row["revision_number"]),
                    "superseded_revision_number": (
                        int(row["superseded_revision_number"])
                        if row["superseded_revision_number"] is not None
                        else None
                    ),
                    "content_hash": str(row["content_hash"]),
                    "change_summary": str(row["change_summary"]),
                    "created_at": row["created_at"],
                    "created_by": row["created_by"],
                    "source": source,
                    "program": _parse_program_from_metadata_json(row["metadata_json"]),
                }
            )
        return revisions

    def edit_time_series_set_values(
        self,
        *,
        project_id: int,
        time_series_set_id: int,
        edits: list[CatalogValueEdit],
        created_by: str = "internal_analyst",
        change_summary: str | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            self.get_project(project_id)
            set_row = self.connection.execute(
                """
                SELECT id, name, version_label, data_kind, timezone
                FROM time_series_sets
                WHERE project_id = ? AND id = ?
                """,
                (project_id, time_series_set_id),
            ).fetchone()
            if set_row is None:
                raise KeyError(f"time-series set {time_series_set_id} not found")

            signal_rows = self.connection.execute(
                """
                SELECT id, signal_key, unit, source_column, source_unit, entity_type, entity_key
                FROM time_series_signals
                WHERE time_series_set_id = ?
                ORDER BY id
                """,
                (time_series_set_id,),
            ).fetchall()
            signals_by_key = {
                str(row["signal_key"]): row_to_dict(row) for row in signal_rows
            }

            period_rows = self.connection.execute(
                """
                SELECT id, period_index, timestamp_start, timestamp_end, duration_hours
                FROM time_series_periods
                WHERE time_series_set_id = ?
                ORDER BY period_index
                """,
                (time_series_set_id,),
            ).fetchall()
            periods_by_index = {
                int(row["period_index"]): row_to_dict(row) for row in period_rows
            }

            value_rows = self.connection.execute(
                """
                SELECT
                    time_series_values.id AS id,
                    time_series_periods.period_index AS period_index,
                    time_series_signals.signal_key AS signal_key,
                    time_series_values.value_numeric AS value_numeric,
                    time_series_values.source_row_number AS source_row_number
                FROM time_series_values
                JOIN time_series_periods
                  ON time_series_periods.id = time_series_values.time_series_period_id
                JOIN time_series_signals
                  ON time_series_signals.id = time_series_values.time_series_signal_id
                WHERE time_series_values.time_series_set_id = ?
                """,
                (time_series_set_id,),
            ).fetchall()
            values_by_key: dict[tuple[int, str], dict[str, Any]] = {
                (int(row["period_index"]), str(row["signal_key"])): row_to_dict(row)
                for row in value_rows
            }

            signal_definitions = {
                signal_key: TIME_SERIES_SIGNAL_CATALOG[signal_key]
                for signal_key in signals_by_key
                if signal_key in TIME_SERIES_SIGNAL_CATALOG
            }
            prepared_edits = validate_catalog_value_edits(
                edits=edits,
                signal_definitions=signal_definitions,
                known_period_indexes=set(periods_by_index),
            )

            now = utc_now_iso()
            change_diff: list[dict[str, Any]] = []
            for prepared_edit in prepared_edits:
                key = (prepared_edit.period_index, prepared_edit.signal_key)
                existing_value = values_by_key.get(key)
                if existing_value is None:
                    raise TimeSeriesCatalogError(
                        f"no existing value for signal_key {prepared_edit.signal_key!r} "
                        f"at period {prepared_edit.period_index}"
                    )
                change_diff.append(
                    {
                        "period_index": prepared_edit.period_index,
                        "signal_key": prepared_edit.signal_key,
                        "previous_value": existing_value["value_numeric"],
                        "new_value": prepared_edit.value_numeric,
                    }
                )
                values_by_key[key] = {
                    **existing_value,
                    "value_numeric": prepared_edit.value_numeric,
                }

            latest_revision_row = self.connection.execute(
                """
                SELECT revision_number, time_series_source_id
                FROM time_series_set_revisions
                WHERE time_series_set_id = ?
                ORDER BY revision_number DESC
                LIMIT 1
                """,
                (time_series_set_id,),
            ).fetchone()
            latest_revision_number = int(latest_revision_row["revision_number"]) if latest_revision_row else 0
            latest_time_series_source_id = (
                int(latest_revision_row["time_series_source_id"])
                if latest_revision_row and latest_revision_row["time_series_source_id"] is not None
                else None
            )
            next_revision_number = latest_revision_number + 1

            content_hash = compute_catalog_content_hash(
                set_name=str(set_row["name"]),
                version_label=str(set_row["version_label"]),
                data_kind=str(set_row["data_kind"]),
                timezone=str(set_row["timezone"]),
                signals=[
                    {
                        "signal_key": row["signal_key"],
                        "unit": row["unit"],
                        "source_column": row["source_column"],
                        "source_unit": row["source_unit"],
                        "entity_type": row["entity_type"],
                        "entity_key": row["entity_key"],
                    }
                    for row in signals_by_key.values()
                ],
                periods=[
                    {
                        "period_index": row["period_index"],
                        "timestamp_start": row["timestamp_start"],
                        "timestamp_end": row["timestamp_end"],
                        "duration_hours": row["duration_hours"],
                    }
                    for row in periods_by_index.values()
                ],
                values=[
                    {
                        "period_index": row["period_index"],
                        "signal_key": row["signal_key"],
                        "value_numeric": row["value_numeric"],
                        "source_row_number": row["source_row_number"],
                    }
                    for row in sorted(
                        values_by_key.values(),
                        key=lambda item: (item["period_index"], item["signal_key"]),
                    )
                ],
            )

            try:
                self.connection.execute(
                    """
                    INSERT INTO time_series_set_revisions (
                        time_series_set_id,
                        revision_number,
                        time_series_source_id,
                        superseded_revision_number,
                        content_hash,
                        change_summary,
                        created_at,
                        created_by,
                        metadata_json
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        time_series_set_id,
                        next_revision_number,
                        latest_time_series_source_id,
                        latest_revision_number or None,
                        content_hash,
                        change_summary or "Manual value correction",
                        now,
                        created_by,
                        json.dumps({"edits": change_diff}, sort_keys=True),
                    ),
                )
                for prepared_edit in prepared_edits:
                    key = (prepared_edit.period_index, prepared_edit.signal_key)
                    self.connection.execute(
                        "UPDATE time_series_values SET value_numeric = ? WHERE id = ?",
                        (prepared_edit.value_numeric, int(values_by_key[key]["id"])),
                    )
                self.connection.execute(
                    """
                    UPDATE time_series_sets
                    SET content_hash = ?, updated_at = ?, updated_by = ?
                    WHERE id = ?
                    """,
                    (content_hash, now, created_by, time_series_set_id),
                )
            except Exception:
                self.connection.rollback()
                self.connection.execute(
                    """
                    DELETE FROM time_series_set_revisions
                    WHERE time_series_set_id = ? AND revision_number = ?
                    """,
                    (time_series_set_id, next_revision_number),
                )
                self.connection.commit()
                raise

            self.connection.commit()
            return self.get_time_series_set(project_id, time_series_set_id)

    def _get_or_create_time_series_source_record(
        self,
        *,
        project_id: int,
        source: dict[str, Any],
        created_by: str,
        now: str,
    ) -> dict[str, Any]:
        source_key = str(source.get("id") or "").strip()
        if not source_key:
            raise ValueError("time-series source is missing id")
        existing = self.connection.execute(
            """
            SELECT id, checksum
            FROM time_series_sources
            WHERE project_id = ? AND source_key = ?
            """,
            (project_id, source_key),
        ).fetchone()
        if existing is not None:
            return row_to_dict(existing)

        cursor = self.connection.execute(
            """
            INSERT INTO time_series_sources (
                project_id,
                source_key,
                kind,
                original_filename,
                media_type,
                checksum,
                stored_path,
                selected_sheet,
                created_at,
                created_by,
                metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                project_id,
                source_key,
                str(source.get("kind") or "csv"),
                str(source.get("original_filename") or "source.csv"),
                str(source.get("media_type") or "text/csv"),
                str(source.get("checksum") or ""),
                str(source.get("stored_path") or ""),
                source.get("selected_sheet"),
                now,
                created_by,
                json.dumps(
                    source.get("metadata")
                    if isinstance(source.get("metadata"), dict)
                    else {},
                    sort_keys=True,
                ),
            ),
        )
        return {"id": int(cursor.lastrowid), "checksum": str(source.get("checksum") or "")}

    def _time_series_source_public_dict(self, source_row: Mapping[str, Any] | None) -> dict[str, Any] | None:
        if source_row is None:
            return None
        metadata: dict[str, Any] = {}
        try:
            raw_metadata = source_row["metadata_json"]
        except (KeyError, IndexError):
            raw_metadata = None
        if raw_metadata:
            try:
                parsed_metadata = json.loads(str(raw_metadata))
            except json.JSONDecodeError:
                parsed_metadata = {}
            if isinstance(parsed_metadata, dict):
                metadata = parsed_metadata
        return {
            "source_key": source_row["source_key"],
            "kind": source_row["kind"],
            "original_filename": source_row["original_filename"],
            "media_type": source_row["media_type"],
            "checksum": source_row["checksum"],
            "selected_sheet": source_row["selected_sheet"],
            "created_at": source_row["created_at"],
            "metadata": metadata,
        }

    def _get_time_series_source_by_id(self, time_series_source_id: int | None) -> dict[str, Any] | None:
        if time_series_source_id is None:
            return None
        source_row = self.connection.execute(
            """
            SELECT
                source_key,
                kind,
                original_filename,
                media_type,
                checksum,
                selected_sheet,
                created_at,
                metadata_json
            FROM time_series_sources
            WHERE id = ?
            """,
            (int(time_series_source_id),),
        ).fetchone()
        return self._time_series_source_public_dict(source_row)

    def get_or_create_hydraulic_diagram(self, scenario_id: int) -> dict[str, Any]:
        with self._lock:
            scenario = self.get_scenario(scenario_id)
            case = self._get_or_create_optimization_case(scenario)
            system = self._get_or_create_hydraulic_system(scenario)
            self._get_or_create_case_hydraulic_system(case["id"], system["id"])
            self._get_or_create_hydraulic_layout(case["id"])
            self.connection.commit()
            return self.get_hydraulic_diagram(scenario_id)

    def get_hydraulic_diagram(self, scenario_id: int) -> dict[str, Any]:
        self.get_scenario(scenario_id)
        context = self._get_hydraulic_diagram_context(scenario_id)
        if context is None:
            raise KeyError(f"hydraulic diagram for scenario {scenario_id} not found")
        return self._hydraulic_diagram_response(context)

    def save_hydraulic_diagram(
        self,
        *,
        scenario_id: int,
        revision: str,
        nodes: list[dict[str, Any]],
        reaches: list[dict[str, Any]] | None = None,
        viewport: dict[str, Any] | None = None,
        updated_by: str = "internal_analyst",
    ) -> dict[str, Any]:
        with self._lock:
            self.get_or_create_hydraulic_diagram(scenario_id)
            context = self._get_hydraulic_diagram_context(scenario_id)
            if context is None:
                raise KeyError(f"hydraulic diagram for scenario {scenario_id} not found")
            layout = context["layout"]
            current_revision = str(layout["layout_version"])
            if str(revision) != current_revision:
                raise ValueError("stale hydraulic diagram revision")

            previous_validation = hydraulic_validation_public_dict(
                context["optimization_case"].get("validation_payload_json")
            )
            normalized_nodes = normalize_hydraulic_diagram_nodes(nodes)
            normalized_reaches = normalize_hydraulic_diagram_reaches(reaches or [])
            resolved_viewport = {
                "x": float(layout["viewport_x"]),
                "y": float(layout["viewport_y"]),
                "zoom": float(layout["zoom"]),
            }
            if viewport is not None:
                resolved_viewport = normalize_hydraulic_viewport(viewport)

            now = utc_now_iso()
            layout_id = int(layout["id"])
            case_id = int(context["optimization_case"]["id"])
            system_id = int(context["hydraulic_system"]["id"])

            self.connection.execute(
                "DELETE FROM case_hydraulic_diagram_items WHERE diagram_layout_id = ?",
                (layout_id,),
            )
            self.connection.execute(
                "DELETE FROM case_hydraulic_reaches WHERE case_id = ?",
                (case_id,),
            )
            self.connection.execute(
                "DELETE FROM case_hydraulic_nodes WHERE case_id = ?",
                (case_id,),
            )
            self.connection.execute(
                "DELETE FROM case_hydraulic_units WHERE case_id = ?",
                (case_id,),
            )
            self.connection.execute(
                "DELETE FROM case_hydraulic_plants WHERE case_id = ?",
                (case_id,),
            )
            self.connection.execute(
                "DELETE FROM case_hydraulic_curve_bindings WHERE case_id = ?",
                (case_id,),
            )
            self.connection.execute(
                "DELETE FROM case_hydraulic_time_series_bindings WHERE case_id = ?",
                (case_id,),
            )
            self.connection.execute(
                "DELETE FROM case_hydraulic_reservoir_parameters WHERE case_id = ?",
                (case_id,),
            )

            project_id = int(context["hydraulic_system"]["project_id"])
            active_nodes_by_key: dict[str, dict[str, Any]] = {}
            plant_unit_specs: list[dict[str, Any]] = []
            for index, node in enumerate(normalized_nodes):
                if node["component_type"] == "plant":
                    created_plant = self._create_case_hydraulic_plant(
                        case_id=case_id,
                        system_id=system_id,
                        plant_key=node["technical_key"],
                        display_name=node["display_name"],
                        plant=node.get("plant"),
                        updated_by=updated_by,
                        now=now,
                    )
                    active_id = created_plant["case_hydraulic_plant_id"]
                    if node.get("units"):
                        plant_unit_specs.append(
                            {
                                "hydraulic_plant_id": created_plant["hydraulic_plant_id"],
                                "case_hydraulic_plant_id": active_id,
                                "units": node["units"],
                            }
                        )
                    entity_type = "case_hydraulic_plant"
                else:
                    created_node = self._create_case_hydraulic_node(
                        case_id=case_id,
                        system_id=system_id,
                        node_key=node["technical_key"],
                        display_name=node["display_name"],
                        node_type=node["component_type"],
                        updated_by=updated_by,
                        now=now,
                    )
                    active_id = created_node["case_hydraulic_node_id"]
                    active_nodes_by_key[node["technical_key"]] = {
                        "case_hydraulic_node_id": active_id,
                        "hydraulic_node_id": created_node["hydraulic_node_id"],
                        "x": node["x"],
                        "y": node["y"],
                    }
                    entity_type = "case_hydraulic_node"
                    if node.get("natural_inflow_series") is not None:
                        self._persist_hydraulic_inflow_series(
                            project_id=project_id,
                            base_entity_id=created_node["hydraulic_node_id"],
                            case_id=case_id,
                            binding_entity_type="case_hydraulic_node",
                            binding_entity_id=active_id,
                            series=node["natural_inflow_series"],
                            updated_by=updated_by,
                            now=now,
                        )
                    if node["component_type"] == "reservoir":
                        if node.get("reservoir") is not None:
                            self._persist_reservoir_parameters(
                                case_id=case_id,
                                case_hydraulic_node_id=active_id,
                                reservoir=node["reservoir"],
                                updated_by=updated_by,
                                now=now,
                            )
                        if node.get("storage_elevation_curve") is not None:
                            self._persist_hydraulic_curve(
                                project_id=project_id,
                                base_entity_id=created_node["hydraulic_node_id"],
                                case_id=case_id,
                                binding_entity_type="case_hydraulic_node",
                                binding_entity_id=active_id,
                                curve=node["storage_elevation_curve"],
                                spec=STORAGE_ELEVATION_CURVE_SPEC,
                                updated_by=updated_by,
                                now=now,
                            )
                item_metadata: dict[str, Any] = {}
                if node["component_type"] == "plant" and node.get("link_anchors"):
                    item_metadata["link_anchors"] = node["link_anchors"]
                self.connection.execute(
                    """
                    INSERT INTO case_hydraulic_diagram_items (
                        diagram_layout_id,
                        entity_type,
                        entity_id,
                        x,
                        y,
                        z_index,
                        collapsed,
                        style_json,
                        metadata_json,
                        updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, 0, '{}', ?, ?)
                    """,
                    (
                        layout_id,
                        entity_type,
                        active_id,
                        node["x"],
                        node["y"],
                        index,
                        json.dumps(item_metadata),
                        now,
                    ),
                )

            for spec in plant_unit_specs:
                for unit in spec["units"]:
                    self._persist_case_hydraulic_unit(
                        project_id=project_id,
                        system_id=system_id,
                        case_id=case_id,
                        hydraulic_plant_id=spec["hydraulic_plant_id"],
                        case_hydraulic_plant_id=spec["case_hydraulic_plant_id"],
                        unit=unit,
                        active_nodes_by_key=active_nodes_by_key,
                        updated_by=updated_by,
                        now=now,
                    )

            for index, reach in enumerate(normalized_reaches):
                from_node = self._resolve_hydraulic_node_for_reach(
                    system_id,
                    reach["from_node_key"],
                    active_nodes_by_key,
                )
                to_node = self._resolve_hydraulic_node_for_reach(
                    system_id,
                    reach["to_node_key"],
                    active_nodes_by_key,
                )
                created_reach = self._create_case_hydraulic_reach(
                    case_id=case_id,
                    system_id=system_id,
                    reach_key=reach["technical_key"],
                    display_name=reach["display_name"],
                    from_node_id=from_node["hydraulic_node_id"],
                    to_node_id=to_node["hydraulic_node_id"],
                    reach_type=reach["reach_type"],
                    updated_by=updated_by,
                    now=now,
                    flow_min_m3s=reach.get("flow_min_m3s"),
                    spill_penalty_usd_per_hm3=reach.get("spill_penalty_usd_per_hm3"),
                    routing_method=reach.get("routing_method", "none"),
                    travel_time_hours=reach.get("travel_time_hours", 0.0),
                )
                if reach.get("minimum_flow_series") is not None:
                    self._persist_hydraulic_inflow_series(
                        project_id=project_id,
                        base_entity_id=created_reach["hydraulic_reach_id"],
                        case_id=case_id,
                        binding_entity_type="case_hydraulic_reach",
                        binding_entity_id=created_reach["case_hydraulic_reach_id"],
                        series=reach["minimum_flow_series"],
                        updated_by=updated_by,
                        now=now,
                        signal_key=MINIMUM_FLOW_SIGNAL_KEY,
                        base_entity_type="hydraulic_reach",
                    )
                active_endpoints = [
                    node
                    for node in (from_node, to_node)
                    if "case_hydraulic_node_id" in node
                ]
                if active_endpoints:
                    x = sum(float(node["x"]) for node in active_endpoints) / len(active_endpoints)
                    y = sum(float(node["y"]) for node in active_endpoints) / len(active_endpoints)
                else:
                    x = 0.0
                    y = 0.0
                reach_metadata: dict[str, Any] = {}
                if reach.get("from_anchor") is not None:
                    reach_metadata["from_anchor"] = reach["from_anchor"]
                if reach.get("to_anchor") is not None:
                    reach_metadata["to_anchor"] = reach["to_anchor"]
                self.connection.execute(
                    """
                    INSERT INTO case_hydraulic_diagram_items (
                        diagram_layout_id,
                        entity_type,
                        entity_id,
                        x,
                        y,
                        z_index,
                        collapsed,
                        style_json,
                        metadata_json,
                        updated_at
                    )
                    VALUES (?, 'case_hydraulic_reach', ?, ?, ?, ?, 0, '{}', ?, ?)
                    """,
                    (
                        layout_id,
                        created_reach["case_hydraulic_reach_id"],
                        x,
                        y,
                        len(normalized_nodes) + index,
                        json.dumps(reach_metadata),
                        now,
                    ),
                )

            self.connection.execute(
                """
                UPDATE case_hydraulic_diagram_layouts
                SET viewport_x = ?,
                    viewport_y = ?,
                    zoom = ?,
                    layout_engine = 'manual',
                    layout_version = layout_version + 1,
                    updated_at = ?,
                    updated_by = ?
                WHERE id = ?
                """,
                (
                    resolved_viewport["x"],
                    resolved_viewport["y"],
                    resolved_viewport["zoom"],
                    now,
                    updated_by,
                    layout_id,
                ),
            )
            stale_validation = self._stale_validation_after_hydraulic_edit(
                previous_validation,
                scenario_id=scenario_id,
                updated_at=now,
            )
            if stale_validation is not None:
                self.connection.execute(
                    """
                    UPDATE optimization_cases
                    SET validation_payload_json = ?,
                        updated_at = ?,
                        updated_by = ?
                    WHERE id = ?
                    """,
                    (
                        json.dumps(stale_validation, sort_keys=True),
                        now,
                        updated_by,
                        case_id,
                    ),
                )
            self.connection.commit()
            updated_context = self._get_hydraulic_diagram_context(scenario_id)
            if updated_context is None:
                raise KeyError(f"hydraulic diagram for scenario {scenario_id} not found")
            return self._hydraulic_diagram_response(updated_context)

    def generate_hydraulic_v3_preview(self, scenario_id: int) -> dict[str, Any]:
        diagram = self.get_hydraulic_diagram(scenario_id)
        network_nodes: list[dict[str, Any]] = []
        reaches: list[dict[str, Any]] = []
        plants: list[dict[str, Any]] = []
        units: list[dict[str, Any]] = []
        curves: list[dict[str, Any]] = []
        required_time_series: list[dict[str, Any]] = []
        inflow_series_by_key: dict[str, list[dict[str, float]]] = {}

        for node in diagram["nodes"]:
            component_type = str(node["component_type"])
            if component_type == "plant":
                plant = node.get("plant") or {}
                plant_units = [unit["technical_key"] for unit in node.get("units", []) if unit.get("is_active", True)]
                plants.append(
                    {
                        "id": node["technical_key"],
                        "display_name": node["display_name"],
                        "non_modeled": bool(plant.get("non_modeled", False)),
                        "min_power_mw": plant.get("min_power_mw"),
                        "max_power_mw": plant.get("max_power_mw"),
                        "units": plant_units,
                    }
                )
                for unit in node.get("units", []):
                    if not unit.get("is_active", True):
                        continue
                    flow_power = hydraulic_flow_power_curve_points(unit.get("flow_power_curve"))
                    units.append(
                        {
                            "id": unit["technical_key"],
                            "display_name": unit["display_name"],
                            "plant_id": node["technical_key"],
                            "intake_node": unit.get("intake_node_key"),
                            "discharge_node": unit.get("discharge_node_key"),
                            "min_power_mw": unit.get("min_power_mw"),
                            "max_power_mw": unit.get("max_power_mw"),
                            "min_flow_m3s": unit.get("min_flow_m3s"),
                            "max_flow_m3s": unit.get("max_flow_m3s"),
                            "curves": {FLOW_POWER_CURVE_KEY: flow_power},
                        }
                    )
                    curves.append(
                        {
                            "entity_type": "hydraulic_unit",
                            "entity_id": unit["technical_key"],
                            "curve_role": FLOW_POWER_CURVE_KEY,
                            "points": flow_power,
                        }
                    )
                continue

            network_node = {
                "id": node["technical_key"],
                "display_name": node["display_name"],
                "type": component_type,
            }
            node_series = hydraulic_natural_inflow_series_points(
                node.get("natural_inflow_series")
            )
            if node_series:
                inflow_series_by_key[node["technical_key"]] = node_series
            if component_type == "reservoir":
                network_node["reservoir"] = node.get("reservoir")
                storage_elevation = hydraulic_storage_elevation_curve_points(
                    node.get("storage_elevation_curve")
                )
                network_node["curves"] = {STORAGE_ELEVATION_CURVE_KEY: storage_elevation}
                curves.append(
                    {
                        "entity_type": "hydraulic_node",
                        "entity_id": node["technical_key"],
                        "curve_role": STORAGE_ELEVATION_CURVE_KEY,
                        "points": storage_elevation,
                    }
                )
                required_time_series.append(
                    {
                        "entity_type": "hydraulic_node",
                        "entity_id": node["technical_key"],
                        "signal_key": NATURAL_INFLOW_SIGNAL_KEY,
                        "binding_status": "required",
                    }
                )
            elif node_series:
                required_time_series.append(
                    {
                        "entity_type": "hydraulic_node",
                        "entity_id": node["technical_key"],
                        "signal_key": NATURAL_INFLOW_SIGNAL_KEY,
                        "binding_status": "bound",
                    }
                )
            network_nodes.append(network_node)

        minimum_flow_series_by_key: dict[str, list[dict[str, float]]] = {}
        for reach in diagram["reaches"]:
            series_points = hydraulic_natural_inflow_series_points(
                reach.get("minimum_flow_series")
            )
            has_series = bool(series_points)
            if has_series:
                minimum_flow_series_by_key[reach["technical_key"]] = series_points
            reaches.append(
                {
                    "id": reach["technical_key"],
                    "display_name": reach["display_name"],
                    "from_node": reach["from_node_key"],
                    "to_node": reach["to_node_key"],
                    "type": reach["reach_type"],
                    "routing_method": "none",
                    "travel_time_hours": 0.0,
                    "flow_min_m3s": None if has_series else reach.get("flow_min_m3s"),
                    "flow_min_source": "series" if has_series else "scalar",
                    "spill_penalty_usd_per_hm3": reach.get("spill_penalty_usd_per_hm3"),
                }
            )

        time_series = hydraulic_v3_time_series_from_inflows(
            required_time_series, inflow_series_by_key
        )
        hydraulic_v3_apply_minimum_flow_series(time_series, minimum_flow_series_by_key)

        return {
            "schema_version": "bess_system_dispatch.v3",
            "case_name": diagram["optimization_case"]["case_key"],
            "solver": {"name": "HiGHS", "options": {}},
            "time_series": time_series,
            "hydraulic_network": {
                "nodes": network_nodes,
                "reaches": reaches,
                "plants": plants,
                "units": units,
                "curves": curves,
                "required_time_series": required_time_series,
            },
        }

    def persist_hydraulic_v3_validation(
        self,
        *,
        scenario_id: int,
        system_case: dict[str, Any],
        julia_payload: dict[str, Any],
    ) -> dict[str, Any]:
        with self._lock:
            context = self._get_hydraulic_diagram_context(scenario_id)
            if context is None:
                raise KeyError(f"hydraulic diagram for scenario {scenario_id} not found")
            payload_hash = hydraulic_payload_hash(system_case)
            validation = {
                "kind": "hydraulic_v3_preview",
                "ok": True,
                "stale": False,
                "status": "ok",
                "summary": "Hydraulic v3 payload validated",
                "errors": [],
                "warnings": [],
                "validation_hash": payload_hash,
                "system_case": system_case,
                "julia_validation": julia_payload,
                **derive_case_hierarchy_provenance(system_case),
            }
            self.connection.execute(
                """
                UPDATE optimization_cases
                SET validation_payload_json = ?,
                    updated_at = ?,
                    updated_by = 'hydraulic_v3_validator'
                WHERE id = ?
                """,
                (
                    json.dumps(validation, sort_keys=True),
                    utc_now_iso(),
                    int(context["optimization_case"]["id"]),
                ),
            )
            self.connection.commit()
            return validation

    def _stale_validation_after_hydraulic_edit(
        self,
        previous_validation: Mapping[str, Any],
        *,
        scenario_id: int,
        updated_at: str,
    ) -> dict[str, Any] | None:
        if (
            previous_validation.get("kind") != "hydraulic_v3_preview"
            or not previous_validation.get("ok")
            or previous_validation.get("stale")
        ):
            return None

        previous_system_case = previous_validation.get("system_case")
        try:
            current_system_case = self.generate_hydraulic_v3_preview(scenario_id)
        except Exception:
            current_system_case = None

        if current_system_case is None or not isinstance(previous_system_case, dict):
            stale_state = {"topology_stale": True, "parameters_stale": True}
        else:
            stale_state = hierarchy_stale_state(previous_system_case, current_system_case)
            if stale_state is None:
                return None

        stale = dict(previous_validation)
        stale["ok"] = False
        stale["stale"] = True
        stale["status"] = "stale"
        stale["topology_stale"] = stale_state["topology_stale"]
        stale["parameters_stale"] = stale_state["parameters_stale"]
        stale["summary"] = hierarchy_stale_summary("Hydraulic v3 validation", stale_state)
        stale["stale_at"] = updated_at
        return stale

    def validate_hydraulic_diagram(self, scenario_id: int) -> dict[str, Any]:
        self.get_scenario(scenario_id)
        context = self._get_hydraulic_diagram_context(scenario_id)
        if context is None:
            raise KeyError(f"hydraulic diagram for scenario {scenario_id} not found")
        case_id = int(context["optimization_case"]["id"])
        active_node_ids = {
            int(row["hydraulic_node_id"])
            for row in self.connection.execute(
                """
                SELECT hydraulic_node_id
                FROM case_hydraulic_nodes
                WHERE case_id = ? AND is_active = 1
                """,
                (case_id,),
            ).fetchall()
        }
        reach_rows = self.connection.execute(
            """
            SELECT
                case_hydraulic_reaches.id AS case_hydraulic_reach_id,
                case_hydraulic_reaches.case_label,
                hydraulic_reaches.reach_key,
                hydraulic_reaches.reach_type,
                hydraulic_reaches.from_node_id,
                hydraulic_reaches.to_node_id
            FROM case_hydraulic_reaches
            JOIN hydraulic_reaches
              ON hydraulic_reaches.id = case_hydraulic_reaches.hydraulic_reach_id
            WHERE case_hydraulic_reaches.case_id = ?
              AND case_hydraulic_reaches.is_active = 1
            ORDER BY case_hydraulic_reaches.id
            """,
            (case_id,),
        ).fetchall()
        errors: list[dict[str, Any]] = []
        for row in reach_rows:
            reach_key = str(row["reach_key"])
            if row["reach_type"] not in HYDRAULIC_REACH_TYPES:
                errors.append(
                    {
                        "severity": "error",
                        "code": "unsupported_reach_type",
                        "message": f"Reach {reach_key} has unsupported type {row['reach_type']}.",
                        "entity_type": "case_hydraulic_reach",
                        "entity_id": int(row["case_hydraulic_reach_id"]),
                        "technical_key": reach_key,
                    }
                )
            if int(row["from_node_id"]) not in active_node_ids or int(row["to_node_id"]) not in active_node_ids:
                errors.append(
                    {
                        "severity": "error",
                        "code": "inactive_or_missing_endpoint",
                        "message": f"Reach {reach_key} must connect active hydraulic nodes in this case.",
                        "entity_type": "case_hydraulic_reach",
                        "entity_id": int(row["case_hydraulic_reach_id"]),
                        "technical_key": reach_key,
                    }
                )

        errors.extend(self._validate_active_reservoirs(case_id))
        errors.extend(self._validate_active_plants_and_units(case_id, active_node_ids))
        errors.extend(self._validate_node_inflow_series(case_id))
        errors.extend(self._validate_reach_controls(case_id))
        errors.extend(self._validate_unsupported_topology(case_id, active_node_ids))

        validation = {
            "ok": not errors,
            "errors": errors,
            "warnings": [],
            "summary": "Hydraulic topology valid" if not errors else "Hydraulic topology has errors",
        }
        self.connection.execute(
            """
            UPDATE optimization_cases
            SET validation_payload_json = ?,
                updated_at = ?,
                updated_by = 'hydraulic_diagram_validator'
            WHERE id = ?
            """,
            (json.dumps(validation, sort_keys=True), utc_now_iso(), case_id),
        )
        self.connection.commit()
        return validation

    def create_scenario_version(
        self,
        *,
        scenario_id: int,
        system_case_json: dict[str, Any],
        validation_payload: dict[str, Any],
        generation_metadata: dict[str, Any] | None = None,
        created_by: str = "internal_analyst",
    ) -> dict[str, Any]:
        self.get_scenario(scenario_id)
        metadata = extract_system_case_metadata(system_case_json)
        version_number = self._next_version_number(scenario_id)
        created_at = utc_now_iso()
        full_generation_metadata = {
            **(generation_metadata or {}),
            **derive_case_hierarchy_provenance(system_case_json),
        }
        cursor = self.connection.execute(
            """
            INSERT INTO scenario_versions (
                scenario_id,
                version_number,
                system_case_json,
                case_name,
                schema_version,
                period_count,
                asset_counts_json,
                validation_payload_json,
                generation_metadata_json,
                created_at,
                created_by
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                scenario_id,
                version_number,
                json.dumps(system_case_json, sort_keys=True),
                metadata["case_name"],
                metadata["schema_version"],
                metadata["period_count"],
                json.dumps(metadata["asset_counts"], sort_keys=True),
                json.dumps(validation_payload, sort_keys=True),
                json.dumps(full_generation_metadata, sort_keys=True),
                created_at,
                created_by,
            ),
        )
        self.connection.commit()
        return self.get_scenario_version(cursor.lastrowid, include_document=False)

    def list_scenario_versions(self, scenario_id: int) -> list[dict[str, Any]]:
        self.get_scenario(scenario_id)
        rows = self.connection.execute(
            """
            SELECT
                id,
                scenario_id,
                version_number,
                case_name,
                schema_version,
                period_count,
                asset_counts_json,
                generation_metadata_json,
                created_at,
                created_by
            FROM scenario_versions
            WHERE scenario_id = ?
            ORDER BY version_number
            """,
            (scenario_id,),
        ).fetchall()
        return [scenario_version_row_to_dict(row, include_document=False) for row in rows]

    def get_scenario_version(self, scenario_version_id: int, *, include_document: bool = True) -> dict[str, Any]:
        document_column = ", system_case_json, validation_payload_json" if include_document else ""
        row = self.connection.execute(
            f"""
            SELECT
                id,
                scenario_id,
                version_number,
                case_name,
                schema_version,
                period_count,
                asset_counts_json,
                generation_metadata_json,
                created_at,
                created_by
                {document_column}
            FROM scenario_versions
            WHERE id = ?
            """,
            (scenario_version_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"scenario version {scenario_version_id} not found")
        return scenario_version_row_to_dict(row, include_document=include_document)

    def persist_scenario_version_hydraulic_diagram_snapshot(
        self,
        *,
        scenario_version_id: int,
        layout_snapshot: dict[str, Any],
        source_case_id: int | None = None,
        layout_key: str = "default",
        created_by: str = "internal_analyst",
    ) -> dict[str, Any]:
        self.get_scenario_version(scenario_version_id, include_document=False)
        snapshot_text = json.dumps(layout_snapshot, sort_keys=True)
        content_hash = hashlib.sha256(snapshot_text.encode("utf-8")).hexdigest()
        created_at = utc_now_iso()
        self.connection.execute(
            """
            INSERT INTO scenario_version_hydraulic_diagram_snapshots (
                scenario_version_id,
                source_case_id,
                layout_key,
                layout_snapshot_json,
                layout_content_hash,
                created_at,
                created_by
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                scenario_version_id,
                source_case_id,
                layout_key,
                snapshot_text,
                content_hash,
                created_at,
                created_by,
            ),
        )
        self.connection.commit()
        return self.get_scenario_version_hydraulic_diagram_snapshot(
            scenario_version_id, layout_key=layout_key
        )

    def get_scenario_version_hydraulic_diagram_snapshot(
        self,
        scenario_version_id: int,
        *,
        layout_key: str = "default",
    ) -> dict[str, Any]:
        self.get_scenario_version(scenario_version_id, include_document=False)
        row = self.connection.execute(
            """
            SELECT id, scenario_version_id, source_case_id, layout_key,
                   layout_snapshot_json, layout_content_hash, created_at, created_by
            FROM scenario_version_hydraulic_diagram_snapshots
            WHERE scenario_version_id = ? AND layout_key = ?
            """,
            (scenario_version_id, layout_key),
        ).fetchone()
        if row is None:
            raise KeyError(
                f"hydraulic diagram snapshot for scenario version {scenario_version_id} not found"
            )
        return scenario_version_hydraulic_diagram_snapshot_row_to_dict(row)

    def delete_scenario_version(self, scenario_version_id: int) -> dict[str, Any]:
        with self._lock:
            version = self.get_scenario_version(scenario_version_id, include_document=False)
            run_row = self.connection.execute(
                "SELECT COUNT(*) AS run_count FROM runs WHERE scenario_version_id = ?",
                (scenario_version_id,),
            ).fetchone()
            publication_row = self.connection.execute(
                "SELECT COUNT(*) AS publication_count FROM publications WHERE scenario_version_id = ?",
                (scenario_version_id,),
            ).fetchone()
            run_count = int(run_row["run_count"])
            publication_count = int(publication_row["publication_count"])
            if run_count:
                raise ValueError("scenario versions referenced by runs cannot be deleted")
            if publication_count:
                raise ValueError("scenario versions referenced by publications cannot be deleted")
            self.connection.execute(
                "DELETE FROM scenario_versions WHERE id = ?",
                (scenario_version_id,),
            )
            self.connection.commit()
            return {
                **version,
                "deleted_run_count": run_count,
                "deleted_publication_count": publication_count,
            }

    def create_or_replace_scenario_draft(
        self,
        *,
        scenario_id: int,
        document: dict[str, Any],
        source_version_id: int | None = None,
        created_by: str = "internal_analyst",
    ) -> dict[str, Any]:
        with self._lock:
            self.get_scenario(scenario_id)
            self._ensure_source_version_belongs_to_scenario(scenario_id, source_version_id)
            now = utc_now_iso()
            existing = self.connection.execute(
                """
                SELECT id
                FROM scenario_drafts
                WHERE scenario_id = ?
                """,
                (scenario_id,),
            ).fetchone()
            if existing is None:
                cursor = self.connection.execute(
                    """
                    INSERT INTO scenario_drafts (
                        scenario_id,
                        source_version_id,
                        document_json,
                        created_at,
                        updated_at,
                        created_by,
                        updated_by
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        scenario_id,
                        source_version_id,
                        json.dumps(document, sort_keys=True),
                        now,
                        now,
                        created_by,
                        created_by,
                    ),
                )
                draft_id = cursor.lastrowid
            else:
                draft_id = int(existing["id"])
                self.connection.execute(
                    """
                    UPDATE scenario_drafts
                    SET
                        source_version_id = ?,
                        document_json = ?,
                        updated_at = ?,
                        updated_by = ?
                    WHERE id = ?
                    """,
                    (
                        source_version_id,
                        json.dumps(document, sort_keys=True),
                        now,
                        created_by,
                        draft_id,
                    ),
                )
            self.connection.commit()
            return self.get_scenario_draft(scenario_id)

    def get_scenario_draft(self, scenario_id: int) -> dict[str, Any]:
        self.get_scenario(scenario_id)
        row = self.connection.execute(
            """
            SELECT
                id,
                scenario_id,
                source_version_id,
                document_json,
                created_at,
                updated_at,
                created_by,
                updated_by
            FROM scenario_drafts
            WHERE scenario_id = ?
            """,
            (scenario_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"scenario draft for scenario {scenario_id} not found")
        return scenario_draft_row_to_dict(row)

    def update_scenario_draft(
        self,
        *,
        scenario_id: int,
        document: dict[str, Any],
        updated_by: str = "internal_analyst",
    ) -> dict[str, Any]:
        with self._lock:
            self.get_scenario_draft(scenario_id)
            updated_at = utc_now_iso()
            self.connection.execute(
                """
                UPDATE scenario_drafts
                SET
                    document_json = ?,
                    updated_at = ?,
                    updated_by = ?
                WHERE scenario_id = ?
                """,
                (
                    json.dumps(document, sort_keys=True),
                    updated_at,
                    updated_by,
                    scenario_id,
                ),
            )
            self.connection.commit()
            return self.get_scenario_draft(scenario_id)

    def create_run(
        self,
        *,
        scenario_version_id: int,
        triggered_by: str = "internal_analyst",
        trigger_type: str = "manual",
    ) -> dict[str, Any]:
        with self._lock:
            self.get_scenario_version(scenario_version_id, include_document=False)
            created_at = utc_now_iso()
            cursor = self.connection.execute(
                """
                INSERT INTO runs (
                    scenario_version_id,
                    status,
                    created_at,
                    triggered_by,
                    trigger_type
                )
                VALUES (?, 'queued', ?, ?, ?)
                """,
                (scenario_version_id, created_at, triggered_by, trigger_type),
            )
            self.connection.commit()
            return self.get_run(cursor.lastrowid)

    def _get_case_for_schedule(self, *, scenario_id: int, case_input_variant_id: int) -> dict[str, Any]:
        self.get_scenario(scenario_id)
        variant = self.get_case_input_variant(case_input_variant_id)
        row = self.connection.execute(
            """
            SELECT id, scenario_id, case_key, display_name, validation_payload_json,
                   created_at, updated_at, created_by, updated_by
            FROM optimization_cases
            WHERE id = ?
            """,
            (variant["case_id"],),
        ).fetchone()
        if row is None or int(row["scenario_id"]) != int(scenario_id):
            raise KeyError(
                f"case input variant {case_input_variant_id} not found for scenario {scenario_id}"
            )
        return row_to_dict(row)

    def create_run_schedule(
        self,
        *,
        scenario_id: int,
        case_input_variant_id: int,
        display_name: str,
        range_start: str,
        range_end: str,
        cadence: str,
        next_run_at: str,
        range_mode: str = "fixed",
        rolling_start_offset_hours: float | None = None,
        rolling_duration_hours: float | None = None,
        created_by: str = "internal_analyst",
    ) -> dict[str, Any]:
        clean_name = normalize_optional_text(display_name)
        if not clean_name:
            raise ValueError("display_name is required")
        normalized_cadence = normalize_schedule_cadence(cadence)
        normalized_next_run_at = parse_schedule_datetime(
            next_run_at, field_name="next_run_at"
        ).isoformat()
        normalized_range_mode = str(range_mode or "fixed").strip().lower()
        if normalized_range_mode not in {"fixed", "rolling"}:
            raise ValueError("range_mode must be fixed or rolling")
        if normalized_range_mode == "rolling":
            resolved_range = resolve_schedule_range(
                schedule={
                    "range_mode": normalized_range_mode,
                    "rolling_start_offset_hours": rolling_start_offset_hours,
                    "rolling_duration_hours": rolling_duration_hours,
                },
                due_at=normalized_next_run_at,
            )
            range_start_at = parse_schedule_datetime(
                resolved_range["start"], field_name="range_start"
            )
            range_end_at = parse_schedule_datetime(
                resolved_range["end"], field_name="range_end"
            )
            normalized_rolling_start_offset_hours = float(rolling_start_offset_hours)
            normalized_rolling_duration_hours = float(rolling_duration_hours)
        else:
            range_start_at = parse_schedule_datetime(range_start, field_name="range_start")
            range_end_at = parse_schedule_datetime(range_end, field_name="range_end")
            if range_start_at >= range_end_at:
                raise ValueError("range_start must be before range_end")
            normalized_rolling_start_offset_hours = None
            normalized_rolling_duration_hours = None
        case = self._get_case_for_schedule(
            scenario_id=scenario_id, case_input_variant_id=case_input_variant_id
        )
        base_system_case = self._generate_base_system_case_for_variant(scenario_id)
        provenance = derive_case_hierarchy_provenance(base_system_case)
        now = utc_now_iso()
        with self._lock:
            cursor = self.connection.execute(
                """
                INSERT INTO run_schedules (
                    scenario_id,
                    case_id,
                    case_input_variant_id,
                    display_name,
                    range_start,
                    range_end,
                    range_mode,
                    rolling_start_offset_hours,
                    rolling_duration_hours,
                    cadence,
                    next_run_at,
                    topology_hash,
                    parameter_hash,
                    is_active,
                    created_at,
                    updated_at,
                    created_by,
                    updated_by
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?)
                """,
                (
                    scenario_id,
                    case["id"],
                    case_input_variant_id,
                    clean_name,
                    range_start_at.isoformat(),
                    range_end_at.isoformat(),
                    normalized_range_mode,
                    normalized_rolling_start_offset_hours,
                    normalized_rolling_duration_hours,
                    normalized_cadence,
                    normalized_next_run_at,
                    provenance["topology"]["content_hash"],
                    provenance["parameters"]["content_hash"],
                    now,
                    now,
                    created_by,
                    created_by,
                ),
            )
            self.connection.commit()
            return self.get_run_schedule(cursor.lastrowid)

    def get_run_schedule(self, schedule_id: int) -> dict[str, Any]:
        row = self.connection.execute(
            """
            SELECT id, scenario_id, case_id, case_input_variant_id, display_name,
                   range_start, range_end, range_mode, rolling_start_offset_hours,
                   rolling_duration_hours, cadence, next_run_at, topology_hash,
                   parameter_hash, is_active, last_fired_at, created_at, updated_at,
                   created_by, updated_by
            FROM run_schedules
            WHERE id = ?
            """,
            (schedule_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"run schedule {schedule_id} not found")
        return run_schedule_row_to_dict(row)

    def list_run_schedules(self) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            """
            SELECT id, scenario_id, case_id, case_input_variant_id, display_name,
                   range_start, range_end, range_mode, rolling_start_offset_hours,
                   rolling_duration_hours, cadence, next_run_at, topology_hash,
                   parameter_hash, is_active, last_fired_at, created_at, updated_at,
                   created_by, updated_by
            FROM run_schedules
            ORDER BY is_active DESC, next_run_at ASC, id ASC
            """
        ).fetchall()
        return [run_schedule_row_to_dict(row) for row in rows]

    def advance_run_schedule(
        self,
        schedule_id: int,
        *,
        next_run_at: str,
        last_fired_at: str,
        updated_by: str = "internal_analyst",
    ) -> dict[str, Any]:
        with self._lock:
            self.get_run_schedule(schedule_id)
            updated_at = utc_now_iso()
            self.connection.execute(
                """
                UPDATE run_schedules
                SET
                    next_run_at = ?,
                    last_fired_at = ?,
                    updated_at = ?,
                    updated_by = ?
                WHERE id = ?
                """,
                (next_run_at, last_fired_at, updated_at, updated_by, schedule_id),
            )
            self.connection.commit()
            return self.get_run_schedule(schedule_id)

    def create_run_schedule_tick(
        self,
        *,
        schedule_id: int,
        due_at: str,
        fired_at: str,
        range_start: str,
        range_end: str,
    ) -> dict[str, Any]:
        with self._lock:
            self.get_run_schedule(schedule_id)
            now = utc_now_iso()
            cursor = self.connection.execute(
                """
                INSERT INTO run_schedule_ticks (
                    schedule_id,
                    due_at,
                    fired_at,
                    range_start,
                    range_end,
                    status,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, 'queued', ?, ?)
                """,
                (schedule_id, due_at, fired_at, range_start, range_end, now, now),
            )
            self.connection.commit()
            return self.get_run_schedule_tick(cursor.lastrowid)

    def get_run_schedule_tick(self, tick_id: int) -> dict[str, Any]:
        row = self.connection.execute(
            """
            SELECT id, schedule_id, due_at, fired_at, range_start, range_end,
                   status, scenario_version_id, run_id, error_message,
                   error_payload_json, created_at, updated_at
            FROM run_schedule_ticks
            WHERE id = ?
            """,
            (tick_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"run schedule tick {tick_id} not found")
        return run_schedule_tick_row_to_dict(row)

    def list_run_schedule_ticks(self, schedule_id: int | None = None) -> list[dict[str, Any]]:
        if schedule_id is None:
            rows = self.connection.execute(
                """
                SELECT id, schedule_id, due_at, fired_at, range_start, range_end,
                       status, scenario_version_id, run_id, error_message,
                       error_payload_json, created_at, updated_at
                FROM run_schedule_ticks
                ORDER BY id DESC
                """
            ).fetchall()
        else:
            self.get_run_schedule(schedule_id)
            rows = self.connection.execute(
                """
                SELECT id, schedule_id, due_at, fired_at, range_start, range_end,
                       status, scenario_version_id, run_id, error_message,
                       error_payload_json, created_at, updated_at
                FROM run_schedule_ticks
                WHERE schedule_id = ?
                ORDER BY id DESC
                """,
                (schedule_id,),
            ).fetchall()
        return [run_schedule_tick_row_to_dict(row) for row in rows]

    def mark_run_schedule_tick_queued(
        self,
        tick_id: int,
        *,
        scenario_version_id: int,
        run_id: int,
    ) -> dict[str, Any]:
        with self._lock:
            self.get_run_schedule_tick(tick_id)
            updated_at = utc_now_iso()
            self.connection.execute(
                """
                UPDATE run_schedule_ticks
                SET
                    status = 'queued',
                    scenario_version_id = ?,
                    run_id = ?,
                    error_message = '',
                    error_payload_json = '{}',
                    updated_at = ?
                WHERE id = ?
                """,
                (scenario_version_id, run_id, updated_at, tick_id),
            )
            self.connection.commit()
            return self.get_run_schedule_tick(tick_id)

    def mark_run_schedule_tick_failed(
        self,
        tick_id: int,
        *,
        error_message: str,
        error_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            self.get_run_schedule_tick(tick_id)
            updated_at = utc_now_iso()
            self.connection.execute(
                """
                UPDATE run_schedule_ticks
                SET
                    status = 'failed',
                    error_message = ?,
                    error_payload_json = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    error_message,
                    json.dumps(error_payload or {}, sort_keys=True),
                    updated_at,
                    tick_id,
                ),
            )
            self.connection.commit()
            return self.get_run_schedule_tick(tick_id)

    def get_run(self, run_id: int) -> dict[str, Any]:
        with self._lock:
            row = self.connection.execute(
                """
                SELECT
                    id,
                    scenario_version_id,
                    status,
                    created_at,
                    started_at,
                    finished_at,
                    duration_seconds,
                    exit_code,
                    workspace_path,
                    input_snapshot_path,
                    output_dir,
                    summary_path,
                    stdout_log_path,
                    stderr_log_path,
                    error_message,
                    success_payload_json,
                    error_payload_json,
                    stdout,
                    stderr,
                    triggered_by,
                    trigger_type
                FROM runs
                WHERE id = ?
                """,
                (run_id,),
            ).fetchone()
            if row is None:
                raise KeyError(f"run {run_id} not found")
            return run_row_to_dict(row)

    def list_scenario_runs(self, scenario_id: int) -> list[dict[str, Any]]:
        self.get_scenario(scenario_id)
        rows = self.connection.execute(
            """
            SELECT
                runs.id,
                runs.scenario_version_id,
                runs.status,
                runs.created_at,
                runs.started_at,
                runs.finished_at,
                runs.duration_seconds,
                runs.exit_code,
                runs.workspace_path,
                runs.input_snapshot_path,
                runs.output_dir,
                runs.summary_path,
                runs.stdout_log_path,
                runs.stderr_log_path,
                runs.error_message,
                runs.success_payload_json,
                runs.error_payload_json,
                runs.stdout,
                runs.stderr,
                runs.triggered_by,
                runs.trigger_type
            FROM runs
            JOIN scenario_versions ON scenario_versions.id = runs.scenario_version_id
            WHERE scenario_versions.scenario_id = ?
            ORDER BY scenario_versions.version_number DESC, runs.id DESC
            """,
            (scenario_id,),
        ).fetchall()
        return [run_row_to_dict(row) for row in rows]

    def list_succeeded_runs(self) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            """
            SELECT
                id,
                scenario_version_id,
                status,
                created_at,
                started_at,
                finished_at,
                duration_seconds,
                exit_code,
                workspace_path,
                input_snapshot_path,
                output_dir,
                summary_path,
                stdout_log_path,
                stderr_log_path,
                error_message,
                success_payload_json,
                error_payload_json,
                stdout,
                stderr,
                triggered_by,
                trigger_type
            FROM runs
            WHERE status = 'succeeded'
            ORDER BY id
            """
        ).fetchall()
        return [run_row_to_dict(row) for row in rows]

    def list_project_succeeded_runs(self, project_id: int) -> list[dict[str, Any]]:
        self.get_project(project_id)
        rows = self.connection.execute(
            """
            SELECT
                runs.id,
                runs.scenario_version_id,
                runs.status,
                runs.created_at,
                runs.started_at,
                runs.finished_at,
                runs.duration_seconds,
                runs.exit_code,
                runs.workspace_path,
                runs.input_snapshot_path,
                runs.output_dir,
                runs.summary_path,
                runs.stdout_log_path,
                runs.stderr_log_path,
                runs.error_message,
                runs.success_payload_json,
                runs.error_payload_json,
                runs.stdout,
                runs.stderr,
                runs.triggered_by,
                runs.trigger_type
            FROM runs
            JOIN scenario_versions ON scenario_versions.id = runs.scenario_version_id
            JOIN scenarios ON scenarios.id = scenario_versions.scenario_id
            WHERE runs.status = 'succeeded' AND scenarios.project_id = ?
            ORDER BY runs.id
            """,
            (project_id,),
        ).fetchall()
        return [run_row_to_dict(row) for row in rows]

    def get_run_project_id(self, run_id: int) -> int:
        row = self.connection.execute(
            """
            SELECT scenarios.project_id
            FROM runs
            JOIN scenario_versions ON scenario_versions.id = runs.scenario_version_id
            JOIN scenarios ON scenarios.id = scenario_versions.scenario_id
            WHERE runs.id = ?
            """,
            (run_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"run {run_id} not found")
        return int(row["project_id"])

    def get_run_lineage(self, run_id: int) -> dict[str, Any]:
        row = self.connection.execute(
            """
            SELECT runs.id AS run_id,
                   runs.status AS run_status,
                   scenario_versions.id AS scenario_version_id,
                   scenarios.id AS scenario_id,
                   projects.id AS project_id
            FROM runs
            JOIN scenario_versions ON scenario_versions.id = runs.scenario_version_id
            JOIN scenarios ON scenarios.id = scenario_versions.scenario_id
            JOIN projects ON projects.id = scenarios.project_id
            WHERE runs.id = ?
            """,
            (run_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"run {run_id} not found")
        return row_to_dict(row)

    def mark_run_running(
        self,
        run_id: int,
        *,
        workspace_path: str,
        input_snapshot_path: str,
    ) -> dict[str, Any]:
        with self._lock:
            started_at = utc_now_iso()
            cursor = self.connection.execute(
                """
                UPDATE runs
                SET
                    status = 'running',
                    started_at = ?,
                    workspace_path = ?,
                    input_snapshot_path = ?
                WHERE id = ?
                """,
                (started_at, workspace_path, input_snapshot_path, run_id),
            )
            if cursor.rowcount == 0:
                raise KeyError(f"run {run_id} not found")
            self.connection.commit()
            return self.get_run(run_id)

    def mark_run_succeeded(
        self,
        run_id: int,
        *,
        exit_code: int,
        stdout: str,
        stderr: str,
        success_payload: dict[str, Any],
        output_dir: str | None,
        summary_path: str | None,
        stdout_log_path: str | None = None,
        stderr_log_path: str | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            run = self.get_run(run_id)
            finished_at = utc_now_iso()
            duration_seconds = elapsed_seconds(run.get("started_at"), finished_at)
            self.connection.execute(
                """
                UPDATE runs
                SET
                    status = 'succeeded',
                    finished_at = ?,
                    duration_seconds = ?,
                    exit_code = ?,
                    stdout = ?,
                    stderr = ?,
                    success_payload_json = ?,
                    output_dir = ?,
                    summary_path = ?,
                    stdout_log_path = ?,
                    stderr_log_path = ?,
                    error_message = ''
                WHERE id = ?
                """,
                (
                    finished_at,
                    duration_seconds,
                    exit_code,
                    stdout,
                    stderr,
                    json.dumps(success_payload, sort_keys=True),
                    output_dir,
                    summary_path,
                    stdout_log_path,
                    stderr_log_path,
                    run_id,
                ),
            )
            self.connection.commit()
            return self.get_run(run_id)

    def mark_run_failed(
        self,
        run_id: int,
        *,
        exit_code: int | None,
        stdout: str,
        stderr: str,
        error_payload: dict[str, Any],
        error_message: str | None = None,
        stdout_log_path: str | None = None,
        stderr_log_path: str | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            run = self.get_run(run_id)
            finished_at = utc_now_iso()
            duration_seconds = elapsed_seconds(run.get("started_at"), finished_at)
            stored_error_message = error_message or str(error_payload.get("message") or "")
            self.connection.execute(
                """
                UPDATE runs
                SET
                    status = 'failed',
                    finished_at = ?,
                    duration_seconds = ?,
                    exit_code = ?,
                    stdout = ?,
                    stderr = ?,
                    error_payload_json = ?,
                    error_message = ?,
                    stdout_log_path = ?,
                    stderr_log_path = ?
                WHERE id = ?
                """,
                (
                    finished_at,
                    duration_seconds,
                    exit_code,
                    stdout,
                    stderr,
                    json.dumps(error_payload, sort_keys=True),
                    stored_error_message,
                    stdout_log_path,
                    stderr_log_path,
                    run_id,
                ),
            )
            self.connection.commit()
            return self.get_run(run_id)

    def register_run_artifact(
        self,
        *,
        run_id: int,
        artifact_type: str,
        path: str,
        display_name: str,
        media_type: str,
        byte_size: int | None = None,
    ) -> dict[str, Any]:
        self.get_run(run_id)
        resolved_byte_size = byte_size
        if resolved_byte_size is None:
            resolved_byte_size = Path(path).stat().st_size
        created_at = utc_now_iso()
        with self._lock:
            cursor = self.connection.execute(
                """
                INSERT INTO run_artifacts (
                    run_id,
                    artifact_type,
                    path,
                    display_name,
                    media_type,
                    byte_size,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (run_id, artifact_type) DO UPDATE SET
                    path = excluded.path,
                    display_name = excluded.display_name,
                    media_type = excluded.media_type,
                    byte_size = excluded.byte_size,
                    created_at = excluded.created_at
                """,
                (
                    run_id,
                    artifact_type,
                    path,
                    display_name,
                    media_type,
                    resolved_byte_size,
                    created_at,
                ),
            )
            self.connection.commit()
            artifact_id = cursor.lastrowid
            if artifact_id == 0:
                row = self.connection.execute(
                    """
                    SELECT id
                    FROM run_artifacts
                    WHERE run_id = ? AND artifact_type = ?
                    """,
                    (run_id, artifact_type),
                ).fetchone()
                artifact_id = int(row["id"])
            return self.get_run_artifact(artifact_id)

    def list_run_artifacts(self, run_id: int) -> list[dict[str, Any]]:
        self.get_run(run_id)
        rows = self.connection.execute(
            """
            SELECT id, run_id, artifact_type, path, display_name, media_type, byte_size, created_at
            FROM run_artifacts
            WHERE run_id = ?
            ORDER BY id
            """,
            (run_id,),
        ).fetchall()
        return [row_to_dict(row) for row in rows]

    def replace_run_dispatch_result_index(
        self,
        *,
        run_id: int,
        scenario_version_id: int,
        columns: list[str],
        rows: list[dict[str, Any]],
        signal_keys: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            run = self.get_run(run_id)
            if int(run["scenario_version_id"]) != scenario_version_id:
                raise ValueError("run_dispatch_result_index scenario_version_id does not match the run")
            scenario_version = self.get_scenario_version(scenario_version_id, include_document=False)
            lineage = result_lineage_from_scenario_version(run_id=run_id, scenario_version=scenario_version)
            now = utc_now_iso()
            try:
                self.connection.execute(
                    """
                    INSERT INTO run_dispatch_result_indexes (
                        run_id,
                        scenario_version_id,
                        dispatch_columns_json,
                        signal_keys_json,
                        lineage_json,
                        created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT (run_id) DO UPDATE SET
                        scenario_version_id = excluded.scenario_version_id,
                        dispatch_columns_json = excluded.dispatch_columns_json,
                        signal_keys_json = excluded.signal_keys_json,
                        lineage_json = excluded.lineage_json,
                        created_at = excluded.created_at
                    """,
                    (
                        run_id,
                        scenario_version_id,
                        json.dumps(columns),
                        json.dumps(signal_keys or {}),
                        json.dumps(lineage, sort_keys=True),
                        now,
                    ),
                )
                self.connection.execute(
                    "DELETE FROM run_dispatch_result_rows WHERE run_id = ?",
                    (run_id,),
                )
                self.connection.executemany(
                    """
                    INSERT INTO run_dispatch_result_rows (
                        run_id,
                        period_index,
                        row_json,
                        timestamp,
                        duration_hours,
                        price_usd_per_mwh,
                        import_price_usd_per_mwh,
                        export_price_usd_per_mwh,
                        market_value_usd,
                        grid_import_mw,
                        grid_export_mw,
                        battery_charge_mw,
                        battery_discharge_mw,
                        battery_energy_mwh,
                        created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            run_id,
                            period_index,
                            json.dumps(row, ensure_ascii=True),
                            str(row.get("timestamp") or ""),
                            normalize_optional_text(row.get("duration_hours")),
                            normalize_optional_text(row.get("price_usd_per_mwh")),
                            normalize_optional_text(row.get("import_price_usd_per_mwh")),
                            normalize_optional_text(row.get("export_price_usd_per_mwh")),
                            normalize_optional_text(row.get("market_value_usd")),
                            normalize_optional_text(row.get("grid_import_mw")),
                            normalize_optional_text(row.get("grid_export_mw")),
                            normalize_optional_text(row.get("battery_charge_mw")),
                            normalize_optional_text(row.get("battery_discharge_mw")),
                            normalize_optional_text(row.get("battery_energy_mwh")),
                            now,
                        )
                        for period_index, row in enumerate(rows)
                    ],
                )
            except Exception:
                self._discard_run_dispatch_result_index(run_id)
                raise
            self.connection.commit()
            return self.get_run_dispatch_result_index(run_id)

    def _discard_run_dispatch_result_index(self, run_id: int) -> None:
        # A failed replace-write must never leave a header row paired with
        # missing or partial detail rows: that mismatch would make BBDD-first
        # reads silently prefer corrupt data over the complete artifact.
        self.connection.execute("DELETE FROM run_dispatch_result_rows WHERE run_id = ?", (run_id,))
        self.connection.execute("DELETE FROM run_dispatch_result_indexes WHERE run_id = ?", (run_id,))
        self.connection.commit()

    def delete_run_dispatch_result_index(self, run_id: int) -> bool:
        with self._lock:
            if self.get_run_dispatch_result_index(run_id) is None:
                return False
            self._discard_run_dispatch_result_index(run_id)
            return True

    def get_run_dispatch_result_index(self, run_id: int) -> dict[str, Any] | None:
        self.get_run(run_id)
        index_row = self.connection.execute(
            """
            SELECT run_id, scenario_version_id, dispatch_columns_json, signal_keys_json, lineage_json, created_at
            FROM run_dispatch_result_indexes
            WHERE run_id = ?
            """,
            (run_id,),
        ).fetchone()
        if index_row is None:
            return None

        row_records = self.connection.execute(
            """
            SELECT row_json
            FROM run_dispatch_result_rows
            WHERE run_id = ?
            ORDER BY period_index
            """,
            (run_id,),
        ).fetchall()
        return {
            "run_id": int(index_row["run_id"]),
            "scenario_version_id": int(index_row["scenario_version_id"]),
            "columns": json.loads(index_row["dispatch_columns_json"]),
            "signal_keys": json.loads(index_row["signal_keys_json"] or "{}"),
            "lineage": json.loads(index_row["lineage_json"] or "{}"),
            "rows": [json.loads(str(row["row_json"])) for row in row_records],
            "created_at": str(index_row["created_at"]),
        }

    def replace_run_asset_dispatch_result_index(
        self,
        *,
        run_id: int,
        scenario_version_id: int,
        columns: list[str],
        rows: list[dict[str, Any]],
    ) -> dict[str, Any]:
        with self._lock:
            run = self.get_run(run_id)
            if int(run["scenario_version_id"]) != scenario_version_id:
                raise ValueError("run_asset_dispatch_result_index scenario_version_id does not match the run")
            scenario_version = self.get_scenario_version(scenario_version_id, include_document=False)
            lineage = result_lineage_from_scenario_version(run_id=run_id, scenario_version=scenario_version)
            now = utc_now_iso()
            try:
                self.connection.execute(
                    """
                    INSERT INTO run_asset_dispatch_result_indexes (
                        run_id,
                        scenario_version_id,
                        asset_dispatch_columns_json,
                        lineage_json,
                        created_at
                    )
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT (run_id) DO UPDATE SET
                        scenario_version_id = excluded.scenario_version_id,
                        asset_dispatch_columns_json = excluded.asset_dispatch_columns_json,
                        lineage_json = excluded.lineage_json,
                        created_at = excluded.created_at
                    """,
                    (run_id, scenario_version_id, json.dumps(columns), json.dumps(lineage, sort_keys=True), now),
                )
                self.connection.execute(
                    "DELETE FROM run_asset_dispatch_result_rows WHERE run_id = ?",
                    (run_id,),
                )
                self.connection.executemany(
                    """
                    INSERT INTO run_asset_dispatch_result_rows (
                        run_id,
                        period_index,
                        asset_id,
                        asset_type,
                        row_json,
                        timestamp,
                        created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            run_id,
                            period_index,
                            str(row.get("asset_id") or ""),
                            str(row.get("asset_type") or ""),
                            json.dumps(row, ensure_ascii=True),
                            str(row.get("timestamp") or ""),
                            now,
                        )
                        for period_index, row in enumerate(rows)
                    ],
                )
            except Exception:
                self._discard_run_asset_dispatch_result_index(run_id)
                raise
            self.connection.commit()
            return self.get_run_asset_dispatch_result_index(run_id)

    def _discard_run_asset_dispatch_result_index(self, run_id: int) -> None:
        self.connection.execute("DELETE FROM run_asset_dispatch_result_rows WHERE run_id = ?", (run_id,))
        self.connection.execute("DELETE FROM run_asset_dispatch_result_indexes WHERE run_id = ?", (run_id,))
        self.connection.commit()

    def delete_run_asset_dispatch_result_index(self, run_id: int) -> bool:
        with self._lock:
            if self.get_run_asset_dispatch_result_index(run_id) is None:
                return False
            self._discard_run_asset_dispatch_result_index(run_id)
            return True

    def get_run_asset_dispatch_result_index(self, run_id: int) -> dict[str, Any] | None:
        self.get_run(run_id)
        index_row = self.connection.execute(
            """
            SELECT run_id, scenario_version_id, asset_dispatch_columns_json, lineage_json, created_at
            FROM run_asset_dispatch_result_indexes
            WHERE run_id = ?
            """,
            (run_id,),
        ).fetchone()
        if index_row is None:
            return None

        row_records = self.connection.execute(
            """
            SELECT row_json
            FROM run_asset_dispatch_result_rows
            WHERE run_id = ?
            ORDER BY period_index
            """,
            (run_id,),
        ).fetchall()
        return {
            "run_id": int(index_row["run_id"]),
            "scenario_version_id": int(index_row["scenario_version_id"]),
            "columns": json.loads(index_row["asset_dispatch_columns_json"]),
            "lineage": json.loads(index_row["lineage_json"] or "{}"),
            "rows": [json.loads(str(row["row_json"])) for row in row_records],
            "created_at": str(index_row["created_at"]),
        }

    def replace_run_summary_result_index(
        self,
        *,
        run_id: int,
        scenario_version_id: int,
        summary: dict[str, Any],
        linked_result_surfaces: list[str] | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            run = self.get_run(run_id)
            if int(run["scenario_version_id"]) != scenario_version_id:
                raise ValueError("run_summary_result_index scenario_version_id does not match the run")
            scenario_version = self.get_scenario_version(scenario_version_id, include_document=False)
            lineage = result_lineage_from_scenario_version(run_id=run_id, scenario_version=scenario_version)
            now = utc_now_iso()
            try:
                self.connection.execute(
                    """
                    INSERT INTO run_summary_result_indexes (
                        run_id,
                        scenario_version_id,
                        summary_json,
                        solver_status,
                        termination_status,
                        objective_value_usd,
                        linked_result_surfaces_json,
                        lineage_json,
                        created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT (run_id) DO UPDATE SET
                        scenario_version_id = excluded.scenario_version_id,
                        summary_json = excluded.summary_json,
                        solver_status = excluded.solver_status,
                        termination_status = excluded.termination_status,
                        objective_value_usd = excluded.objective_value_usd,
                        linked_result_surfaces_json = excluded.linked_result_surfaces_json,
                        lineage_json = excluded.lineage_json,
                        created_at = excluded.created_at
                    """,
                    (
                        run_id,
                        scenario_version_id,
                        json.dumps(summary, ensure_ascii=True),
                        normalize_optional_text(summary.get("solver_status")),
                        normalize_optional_text(summary.get("termination_status")),
                        float(summary["objective_value_usd"])
                        if isinstance(summary.get("objective_value_usd"), (int, float))
                        else None,
                        json.dumps(linked_result_surfaces or []),
                        json.dumps(lineage, sort_keys=True),
                        now,
                    ),
                )
            except Exception:
                self._discard_run_summary_result_index(run_id)
                raise
            self.connection.commit()
            return self.get_run_summary_result_index(run_id)

    def _discard_run_summary_result_index(self, run_id: int) -> None:
        self.connection.execute("DELETE FROM run_summary_result_indexes WHERE run_id = ?", (run_id,))
        self.connection.commit()

    def delete_run_summary_result_index(self, run_id: int) -> bool:
        with self._lock:
            if self.get_run_summary_result_index(run_id) is None:
                return False
            self._discard_run_summary_result_index(run_id)
            return True

    def get_run_summary_result_index(self, run_id: int) -> dict[str, Any] | None:
        self.get_run(run_id)
        row = self.connection.execute(
            """
            SELECT
                run_id,
                scenario_version_id,
                summary_json,
                solver_status,
                termination_status,
                objective_value_usd,
                linked_result_surfaces_json,
                lineage_json,
                created_at
            FROM run_summary_result_indexes
            WHERE run_id = ?
            """,
            (run_id,),
        ).fetchone()
        if row is None:
            return None
        return {
            "run_id": int(row["run_id"]),
            "scenario_version_id": int(row["scenario_version_id"]),
            "summary": json.loads(str(row["summary_json"])),
            "solver_status": normalize_optional_text(row["solver_status"]),
            "termination_status": normalize_optional_text(row["termination_status"]),
            "objective_value_usd": row["objective_value_usd"],
            "linked_result_surfaces": json.loads(row["linked_result_surfaces_json"] or "[]"),
            "lineage": json.loads(row["lineage_json"] or "{}"),
            "created_at": str(row["created_at"]),
        }

    def get_run_artifact(self, artifact_id: int) -> dict[str, Any]:
        row = self.connection.execute(
            """
            SELECT id, run_id, artifact_type, path, display_name, media_type, byte_size, created_at
            FROM run_artifacts
            WHERE id = ?
            """,
            (artifact_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"run artifact {artifact_id} not found")
        return row_to_dict(row)

    def get_or_create_case_for_scenario(self, scenario_id: int) -> dict[str, Any]:
        """Resolve the scenario's one `OptimizationCase`, creating it lazily.

        Cardinality is deliberately one-to-one (confirmed in TS-5 decision 4,
        not migrated); this is the only creation path and it is idempotent.
        """
        scenario = self.get_scenario(scenario_id)
        return self._get_or_create_optimization_case(scenario)

    def get_or_create_default_input_variant(self, case_id: int) -> dict[str, Any]:
        row = self.connection.execute(
            """
            SELECT id, case_id, variant_key, display_name, is_default,
                   created_at, updated_at, created_by, updated_by
            FROM case_input_variants
            WHERE case_id = ? AND is_default = 1
            """,
            (case_id,),
        ).fetchone()
        if row is not None:
            return case_input_variant_row_to_dict(row)

        now = utc_now_iso()
        cursor = self.connection.execute(
            """
            INSERT INTO case_input_variants (
                case_id,
                variant_key,
                display_name,
                is_default,
                created_at,
                updated_at,
                created_by,
                updated_by
            )
            VALUES (?, 'default', 'Default', 1, ?, ?, ?, ?)
            """,
            (case_id, now, now, "internal_analyst", "internal_analyst"),
        )
        self.connection.commit()
        return case_input_variant_row_to_dict(
            self.connection.execute(
                """
                SELECT id, case_id, variant_key, display_name, is_default,
                       created_at, updated_at, created_by, updated_by
                FROM case_input_variants
                WHERE id = ?
                """,
                (cursor.lastrowid,),
            ).fetchone()
        )

    def get_case_input_variant(self, variant_id: int) -> dict[str, Any]:
        row = self.connection.execute(
            """
            SELECT id, case_id, variant_key, display_name, is_default,
                   created_at, updated_at, created_by, updated_by
            FROM case_input_variants
            WHERE id = ?
            """,
            (variant_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"case input variant {variant_id} not found")
        return case_input_variant_row_to_dict(row)

    def get_case_input_variant_for_case(self, case_id: int, variant_id: int) -> dict[str, Any]:
        row = self.connection.execute(
            """
            SELECT id, case_id, variant_key, display_name, is_default,
                   created_at, updated_at, created_by, updated_by
            FROM case_input_variants
            WHERE case_id = ? AND id = ?
            """,
            (case_id, variant_id),
        ).fetchone()
        if row is None:
            raise KeyError(f"case input variant {variant_id} not found for case {case_id}")
        return case_input_variant_row_to_dict(row)

    def list_case_input_variants(self, case_id: int) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            """
            SELECT id, case_id, variant_key, display_name, is_default,
                   created_at, updated_at, created_by, updated_by
            FROM case_input_variants
            WHERE case_id = ?
            ORDER BY is_default DESC, id ASC
            """,
            (case_id,),
        ).fetchall()
        return [case_input_variant_row_to_dict(row) for row in rows]

    def _next_case_input_variant_key(self, case_id: int, display_name: str) -> str:
        base_key = normalize_variant_key(display_name)
        candidate = base_key
        suffix = 2
        while (
            self.connection.execute(
                """
                SELECT 1
                FROM case_input_variants
                WHERE case_id = ? AND variant_key = ?
                """,
                (case_id, candidate),
            ).fetchone()
            is not None
        ):
            candidate = f"{base_key}_{suffix}"
            suffix += 1
        return candidate

    def create_case_input_variant(
        self,
        *,
        case_id: int,
        display_name: str,
        created_by: str = "internal_analyst",
    ) -> dict[str, Any]:
        clean_name = display_name.strip()
        if clean_name == "":
            raise ValueError("variant display name is required")
        now = utc_now_iso()
        cursor = self.connection.execute(
            """
            INSERT INTO case_input_variants (
                case_id,
                variant_key,
                display_name,
                is_default,
                created_at,
                updated_at,
                created_by,
                updated_by
            )
            VALUES (?, ?, ?, 0, ?, ?, ?, ?)
            """,
            (
                case_id,
                self._next_case_input_variant_key(case_id, clean_name),
                clean_name,
                now,
                now,
                created_by,
                created_by,
            ),
        )
        self.connection.commit()
        return self.get_case_input_variant(int(cursor.lastrowid))

    def update_case_input_variant(
        self,
        *,
        case_id: int,
        variant_id: int,
        display_name: str,
        updated_by: str = "internal_analyst",
    ) -> dict[str, Any]:
        self.get_case_input_variant_for_case(case_id, variant_id)
        clean_name = display_name.strip()
        if clean_name == "":
            raise ValueError("variant display name is required")
        now = utc_now_iso()
        self.connection.execute(
            """
            UPDATE case_input_variants
            SET display_name = ?, updated_at = ?, updated_by = ?
            WHERE case_id = ? AND id = ?
            """,
            (clean_name, now, updated_by, case_id, variant_id),
        )
        self.connection.commit()
        return self.get_case_input_variant_for_case(case_id, variant_id)

    def clone_case_input_variant(
        self,
        *,
        case_id: int,
        source_variant_id: int,
        display_name: str,
        created_by: str = "internal_analyst",
    ) -> dict[str, Any]:
        source_variant = self.get_case_input_variant_for_case(case_id, source_variant_id)
        clone = self.create_case_input_variant(
            case_id=case_id,
            display_name=display_name,
            created_by=created_by,
        )
        for binding in self.list_case_time_series_bindings(source_variant["id"]):
            self.upsert_case_time_series_binding(
                case_input_variant_id=clone["id"],
                signal_key=str(binding["signal_key"]),
                entity_type=binding.get("entity_type"),
                entity_id=binding.get("entity_id"),
                time_series_set_id=int(binding["time_series_set_id"]),
                created_by=created_by,
            )
        return clone

    def upsert_case_time_series_binding(
        self,
        *,
        case_input_variant_id: int,
        signal_key: str,
        entity_type: str | None = None,
        entity_id: str | None = None,
        time_series_set_id: int,
        created_by: str = "internal_analyst",
    ) -> dict[str, Any]:
        now = utc_now_iso()
        normalized_entity_type = normalize_optional_text(entity_type)
        normalized_entity_id = normalize_optional_text(entity_id)
        existing = self.connection.execute(
            """
            SELECT id
            FROM case_time_series_bindings
            WHERE case_input_variant_id = ? AND signal_key = ?
              AND ((entity_type IS NULL AND CAST(? AS TEXT) IS NULL) OR entity_type = ?)
              AND ((entity_id IS NULL AND CAST(? AS TEXT) IS NULL) OR entity_id = ?)
            """,
            (
                case_input_variant_id,
                signal_key,
                normalized_entity_type,
                normalized_entity_type,
                normalized_entity_id,
                normalized_entity_id,
            ),
        ).fetchone()
        if existing is not None:
            self.connection.execute(
                """
                UPDATE case_time_series_bindings
                SET time_series_set_id = ?, updated_at = ?, updated_by = ?
                WHERE id = ?
                """,
                (time_series_set_id, now, created_by, int(existing["id"])),
            )
            self.connection.commit()
            return self._get_case_time_series_binding(int(existing["id"]))

        cursor = self.connection.execute(
            """
            INSERT INTO case_time_series_bindings (
                case_input_variant_id,
                signal_key,
                entity_type,
                entity_id,
                time_series_set_id,
                required,
                created_at,
                updated_at,
                created_by,
                updated_by
            )
            VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?, ?)
            """,
            (
                case_input_variant_id,
                signal_key,
                normalized_entity_type,
                normalized_entity_id,
                time_series_set_id,
                now,
                now,
                created_by,
                created_by,
            ),
        )
        self.connection.commit()
        return self._get_case_time_series_binding(int(cursor.lastrowid))

    def _get_case_time_series_binding(self, binding_id: int) -> dict[str, Any]:
        row = self.connection.execute(
            """
            SELECT id, case_input_variant_id, signal_key, entity_type, entity_id, time_series_set_id, required,
                   created_at, updated_at, created_by, updated_by
            FROM case_time_series_bindings
            WHERE id = ?
            """,
            (binding_id,),
        ).fetchone()
        value = row_to_dict(row)
        value["required"] = bool(value["required"])
        return value

    def list_case_time_series_bindings(self, case_input_variant_id: int) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            """
            SELECT id, case_input_variant_id, signal_key, entity_type, entity_id, time_series_set_id, required,
                   created_at, updated_at, created_by, updated_by
            FROM case_time_series_bindings
            WHERE case_input_variant_id = ?
            ORDER BY signal_key, entity_type, entity_id
            """,
            (case_input_variant_id,),
        ).fetchall()
        results = []
        for row in rows:
            value = row_to_dict(row)
            value["required"] = bool(value["required"])
            results.append(value)
        return results

    def _generate_base_system_case_from_draft(self, scenario_id: int) -> dict[str, Any]:
        draft = self.get_scenario_draft(scenario_id)
        # The draft's own (legacy) time_series/sources are irrelevant here: TS-3
        # supplies time_series from variant bindings below, so any unvalidated
        # source left attached to the draft must not block generation.
        draft_document = dict(draft["document"])
        draft_document["time_series"] = {"periods": []}
        return generate_system_case_from_draft(draft_document)

    def _generate_base_system_case_from_hydraulic_diagram(self, scenario_id: int) -> dict[str, Any]:
        system_case = deepcopy(self.generate_hydraulic_v3_preview(scenario_id))
        system_case["time_series"] = []
        return system_case

    def _generate_base_system_case_for_variant(self, scenario_id: int) -> dict[str, Any]:
        try:
            return self._generate_base_system_case_from_draft(scenario_id)
        except (KeyError, DraftGenerationError):
            return self._generate_base_system_case_from_hydraulic_diagram(scenario_id)

    def evaluate_case_input_variant_required_signals(
        self, *, scenario_id: int, case_input_variant_id: int
    ) -> list[dict[str, Any]]:
        try:
            base_system_case = self._generate_base_system_case_for_variant(scenario_id)
        except (KeyError, DraftGenerationError):
            # No editor draft yet (not opened, or a hydraulic-diagram case that
            # never has one): nothing to discover required signals from.
            return []
        required = discover_required_signals(base_system_case)
        bindings = self.list_case_time_series_bindings(case_input_variant_id)
        statuses = evaluate_variant_completeness(required, bindings)
        return [required_signal_status_to_dict(status) for status in statuses]

    def _current_case_input_variant_dependencies(
        self, *, scenario_id: int, case_input_variant_id: int
    ) -> list[dict[str, Any]]:
        try:
            base_system_case = self._generate_base_system_case_for_variant(scenario_id)
        except (KeyError, DraftGenerationError):
            # No editor draft yet: nothing to hash topology/parameters from, and
            # no bindings can meaningfully be validated either.
            return []
        scenario = self.get_scenario(scenario_id)
        provenance = derive_case_hierarchy_provenance(base_system_case)
        dependencies: list[dict[str, Any]] = [
            {
                "dependency_type": "topology",
                "dependency_id": None,
                "hash": provenance["topology"]["content_hash"],
            },
            {
                "dependency_type": "parameters",
                "dependency_id": None,
                "hash": provenance["parameters"]["content_hash"],
            },
        ]
        bound_set_ids = sorted(
            {
                int(binding["time_series_set_id"])
                for binding in self.list_case_time_series_bindings(case_input_variant_id)
            }
        )
        for time_series_set_id in bound_set_ids:
            time_series_set = self.get_time_series_set(int(scenario["project_id"]), time_series_set_id)
            dependencies.append(
                {
                    "dependency_type": "time_series_set",
                    "dependency_id": str(time_series_set_id),
                    "hash": time_series_set["content_hash"],
                }
            )
            # A bound derived set that is stale relative to its own recipe
            # (Layer 1) surfaces as an extra current dependency, so the variant
            # trips the existing fail-closed gate even before regeneration
            # changes the derived set's content hash.
            derived_staleness = self.evaluate_time_series_set_staleness(
                int(scenario["project_id"]), time_series_set_id
            )
            if derived_staleness["stale"]:
                dependencies.append(
                    {
                        "dependency_type": "time_series_set_derived_staleness",
                        "dependency_id": str(time_series_set_id),
                        "hash": "stale",
                    }
                )
        return dependencies

    def get_case_input_variant_validation_dependencies(
        self, case_input_variant_id: int
    ) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            """
            SELECT dependency_type, dependency_id, recorded_hash
            FROM validation_dependencies
            WHERE owner_type = 'case_input_variant' AND owner_id = ?
            ORDER BY dependency_type, dependency_id
            """,
            (case_input_variant_id,),
        ).fetchall()
        return [
            {
                "dependency_type": row["dependency_type"],
                "dependency_id": row["dependency_id"] or None,
                "hash": row["recorded_hash"],
            }
            for row in rows
        ]

    def _record_case_input_variant_validation(
        self, case_input_variant_id: int, dependencies: list[dict[str, Any]]
    ) -> None:
        now = utc_now_iso()
        self.connection.execute(
            "DELETE FROM validation_dependencies WHERE owner_type = 'case_input_variant' AND owner_id = ?",
            (case_input_variant_id,),
        )
        for dependency in dependencies:
            self.connection.execute(
                """
                INSERT INTO validation_dependencies (
                    owner_type, owner_id, dependency_type, dependency_id, recorded_hash, created_at, updated_at
                )
                VALUES ('case_input_variant', ?, ?, ?, ?, ?, ?)
                """,
                (
                    case_input_variant_id,
                    dependency["dependency_type"],
                    dependency.get("dependency_id") or "",
                    dependency["hash"],
                    now,
                    now,
                ),
            )
        self.connection.commit()

    def evaluate_case_input_variant_staleness(
        self, *, scenario_id: int, case_input_variant_id: int
    ) -> dict[str, Any]:
        recorded = self.get_case_input_variant_validation_dependencies(case_input_variant_id)
        current = self._current_case_input_variant_dependencies(
            scenario_id=scenario_id, case_input_variant_id=case_input_variant_id
        )
        result = evaluate_variant_staleness(recorded_dependencies=recorded, current_dependencies=current)
        return variant_staleness_result_to_dict(result)

    def _resolve_variant_series_for_range(
        self,
        *,
        scenario_id: int,
        case_input_variant_id: int,
        range_start: str,
        range_end: str,
    ) -> dict[str, Any]:
        scenario = self.get_scenario(scenario_id)
        base_system_case = self._generate_base_system_case_for_variant(scenario_id)
        bindings = self.list_case_time_series_bindings(case_input_variant_id)

        # Fail closed on bound derived sets whose sources moved: neither an
        # unvalidated variant nor an explicit revalidation may consume derived
        # data that no longer reflects its inputs. Regenerating (or unbinding)
        # the derived set is the only way through.
        stale_derived_reasons: list[dict[str, Any]] = []
        for bound_set_id in sorted(
            {int(binding["time_series_set_id"]) for binding in bindings}
        ):
            derived_staleness = self.evaluate_time_series_set_staleness(
                int(scenario["project_id"]), bound_set_id
            )
            if derived_staleness["stale"]:
                stale_derived_reasons.append(
                    {
                        "dependency_type": "time_series_set_derived_staleness",
                        "dependency_id": str(bound_set_id),
                        "detail": (
                            f"derived time-series set {bound_set_id} is stale "
                            "relative to its transformation inputs; regenerate "
                            "it before validating or running"
                        ),
                    }
                )
        if stale_derived_reasons:
            raise VariantStaleError(stale_derived_reasons)

        required = discover_required_signals(base_system_case)
        missing = [status for status in evaluate_variant_completeness(required, bindings) if not status.bound]
        if missing:
            raise MissingRequiredSignalsError(missing)

        bound_signal_series: dict[Any, list[dict[str, Any]]] = {}
        series_bindings: list[dict[str, Any]] = []
        for binding in bindings:
            time_series_set = self.get_time_series_set(
                int(scenario["project_id"]), int(binding["time_series_set_id"])
            )
            binding_key: Any = binding["signal_key"]
            if binding.get("entity_type") is not None or binding.get("entity_id") is not None:
                binding_key = (
                    binding["signal_key"],
                    binding.get("entity_type"),
                    binding.get("entity_id"),
                )
            bound_signal_series[binding_key] = resolve_bound_signal_series(
                time_series_set, binding["signal_key"], range_start, range_end
            )
            series_bindings.append(
                {
                    "signal_key": binding["signal_key"],
                    "entity_type": binding.get("entity_type"),
                    "entity_id": binding.get("entity_id"),
                    "time_series_set_id": time_series_set["id"],
                    "version_number": time_series_set["version_number"],
                    "version_label": time_series_set["version_label"],
                    "revision_number": time_series_set["revision_number"],
                    "content_hash": time_series_set["content_hash"],
                    "validated_range": {"start": range_start, "end": range_end},
                }
            )

        system_case = dict(base_system_case)
        system_case["time_series"] = materialize_variant_time_series(bound_signal_series)

        provenance = derive_case_hierarchy_provenance(base_system_case)
        dependencies = [
            {"dependency_type": "topology", "dependency_id": None, "hash": provenance["topology"]["content_hash"]},
            {"dependency_type": "parameters", "dependency_id": None, "hash": provenance["parameters"]["content_hash"]},
        ]
        for time_series_set_id in sorted({binding["time_series_set_id"] for binding in series_bindings}):
            matching = next(
                binding for binding in series_bindings if binding["time_series_set_id"] == time_series_set_id
            )
            dependencies.append(
                {
                    "dependency_type": "time_series_set",
                    "dependency_id": str(time_series_set_id),
                    "hash": matching["content_hash"],
                }
            )
        self._record_case_input_variant_validation(case_input_variant_id, dependencies)

        return {"system_case": system_case, "series_bindings": series_bindings}

    def materialize_system_case_for_variant(
        self,
        *,
        scenario_id: int,
        case_input_variant_id: int,
        range_start: str,
        range_end: str,
    ) -> dict[str, Any]:
        staleness = self.evaluate_case_input_variant_staleness(
            scenario_id=scenario_id, case_input_variant_id=case_input_variant_id
        )
        if staleness["stale"]:
            raise VariantStaleError(staleness["reasons"])
        return self._resolve_variant_series_for_range(
            scenario_id=scenario_id,
            case_input_variant_id=case_input_variant_id,
            range_start=range_start,
            range_end=range_end,
        )

    def validate_case_input_variant(
        self,
        *,
        scenario_id: int,
        case_input_variant_id: int,
        range_start: str,
        range_end: str,
    ) -> dict[str, Any]:
        """Re-run variant validation and refresh its recorded dependency hashes.

        Unlike ``materialize_system_case_for_variant``, this does not check
        staleness first: it is the revalidation path that clears the stale
        marker, so it must succeed even when the variant is currently stale.
        """
        return self._resolve_variant_series_for_range(
            scenario_id=scenario_id,
            case_input_variant_id=case_input_variant_id,
            range_start=range_start,
            range_end=range_end,
        )

    def _get_or_create_optimization_case(self, scenario: dict[str, Any]) -> dict[str, Any]:
        row = self.connection.execute(
            """
            SELECT id, scenario_id, case_key, display_name, validation_payload_json,
                   created_at, updated_at, created_by, updated_by
            FROM optimization_cases
            WHERE scenario_id = ?
            """,
            (scenario["id"],),
        ).fetchone()
        if row is not None:
            return row_to_dict(row)

        now = utc_now_iso()
        cursor = self.connection.execute(
            """
            INSERT INTO optimization_cases (
                scenario_id,
                case_key,
                display_name,
                validation_payload_json,
                created_at,
                updated_at,
                created_by,
                updated_by
            )
            VALUES (?, ?, ?, '{}', ?, ?, ?, ?)
            """,
            (
                scenario["id"],
                f"scenario_{scenario['id']}_hydraulic_case",
                scenario["name"],
                now,
                now,
                scenario.get("created_by") or "internal_analyst",
                scenario.get("created_by") or "internal_analyst",
            ),
        )
        return row_to_dict(
            self.connection.execute(
                """
                SELECT id, scenario_id, case_key, display_name, validation_payload_json,
                       created_at, updated_at, created_by, updated_by
                FROM optimization_cases
                WHERE id = ?
                """,
                (cursor.lastrowid,),
            ).fetchone()
        )

    def _get_or_create_hydraulic_system(self, scenario: dict[str, Any]) -> dict[str, Any]:
        system_key = "default_hydraulic_system"
        row = self.connection.execute(
            """
            SELECT id, project_id, system_key, display_name, created_at, updated_at,
                   created_by, updated_by
            FROM hydraulic_systems
            WHERE project_id = ? AND system_key = ?
            """,
            (scenario["project_id"], system_key),
        ).fetchone()
        if row is not None:
            return row_to_dict(row)

        now = utc_now_iso()
        cursor = self.connection.execute(
            """
            INSERT INTO hydraulic_systems (
                project_id,
                system_key,
                display_name,
                created_at,
                updated_at,
                created_by,
                updated_by
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                scenario["project_id"],
                system_key,
                "Default hydraulic system",
                now,
                now,
                scenario.get("created_by") or "internal_analyst",
                scenario.get("created_by") or "internal_analyst",
            ),
        )
        return row_to_dict(
            self.connection.execute(
                """
                SELECT id, project_id, system_key, display_name, created_at, updated_at,
                       created_by, updated_by
                FROM hydraulic_systems
                WHERE id = ?
                """,
                (cursor.lastrowid,),
            ).fetchone()
        )

    def _get_or_create_case_hydraulic_system(self, case_id: int, system_id: int) -> dict[str, Any]:
        row = self.connection.execute(
            """
            SELECT id, case_id, hydraulic_system_id, is_active, created_at, updated_at,
                   created_by, updated_by
            FROM case_hydraulic_systems
            WHERE case_id = ? AND hydraulic_system_id = ?
            """,
            (case_id, system_id),
        ).fetchone()
        if row is not None:
            return row_to_dict(row)

        now = utc_now_iso()
        cursor = self.connection.execute(
            """
            INSERT INTO case_hydraulic_systems (
                case_id,
                hydraulic_system_id,
                is_active,
                created_at,
                updated_at,
                created_by,
                updated_by
            )
            VALUES (?, ?, 1, ?, ?, 'internal_analyst', 'internal_analyst')
            """,
            (case_id, system_id, now, now),
        )
        return row_to_dict(
            self.connection.execute(
                """
                SELECT id, case_id, hydraulic_system_id, is_active, created_at, updated_at,
                       created_by, updated_by
                FROM case_hydraulic_systems
                WHERE id = ?
                """,
                (cursor.lastrowid,),
            ).fetchone()
        )

    def _get_or_create_hydraulic_layout(self, case_id: int) -> dict[str, Any]:
        row = self.connection.execute(
            """
            SELECT id, case_id, layout_key, viewport_x, viewport_y, zoom,
                   layout_engine, layout_version, content_hash, metadata_json,
                   created_at, updated_at, updated_by
            FROM case_hydraulic_diagram_layouts
            WHERE case_id = ? AND layout_key = 'default'
            """,
            (case_id,),
        ).fetchone()
        if row is not None:
            return row_to_dict(row)

        now = utc_now_iso()
        cursor = self.connection.execute(
            """
            INSERT INTO case_hydraulic_diagram_layouts (
                case_id,
                layout_key,
                viewport_x,
                viewport_y,
                zoom,
                layout_engine,
                layout_version,
                metadata_json,
                created_at,
                updated_at,
                updated_by
            )
            VALUES (?, 'default', 0, 0, 1, 'auto_dag', 1, '{}', ?, ?, 'internal_analyst')
            """,
            (case_id, now, now),
        )
        return row_to_dict(
            self.connection.execute(
                """
                SELECT id, case_id, layout_key, viewport_x, viewport_y, zoom,
                       layout_engine, layout_version, content_hash, metadata_json,
                       created_at, updated_at, updated_by
                FROM case_hydraulic_diagram_layouts
                WHERE id = ?
                """,
                (cursor.lastrowid,),
            ).fetchone()
        )

    def _get_hydraulic_diagram_context(self, scenario_id: int) -> dict[str, Any] | None:
        case_row = self.connection.execute(
            """
            SELECT id, scenario_id, case_key, display_name, validation_payload_json,
                   created_at, updated_at, created_by, updated_by
            FROM optimization_cases
            WHERE scenario_id = ?
            """,
            (scenario_id,),
        ).fetchone()
        if case_row is None:
            return None
        case = row_to_dict(case_row)
        system_row = self.connection.execute(
            """
            SELECT hydraulic_systems.id, hydraulic_systems.project_id,
                   hydraulic_systems.system_key, hydraulic_systems.display_name,
                   hydraulic_systems.created_at, hydraulic_systems.updated_at,
                   hydraulic_systems.created_by, hydraulic_systems.updated_by
            FROM case_hydraulic_systems
            JOIN hydraulic_systems ON hydraulic_systems.id = case_hydraulic_systems.hydraulic_system_id
            WHERE case_hydraulic_systems.case_id = ?
              AND case_hydraulic_systems.is_active = 1
            ORDER BY hydraulic_systems.id
            """,
            (case["id"],),
        ).fetchone()
        layout_row = self.connection.execute(
            """
            SELECT id, case_id, layout_key, viewport_x, viewport_y, zoom,
                   layout_engine, layout_version, content_hash, metadata_json,
                   created_at, updated_at, updated_by
            FROM case_hydraulic_diagram_layouts
            WHERE case_id = ? AND layout_key = 'default'
            """,
            (case["id"],),
        ).fetchone()
        if system_row is None or layout_row is None:
            return None
        return {
            "scenario_id": scenario_id,
            "optimization_case": case,
            "hydraulic_system": row_to_dict(system_row),
            "layout": row_to_dict(layout_row),
        }

    def _hydraulic_diagram_response(self, context: dict[str, Any]) -> dict[str, Any]:
        layout = context["layout"]
        layout_id = int(layout["id"])
        node_rows = self.connection.execute(
            """
            SELECT
                case_hydraulic_diagram_items.id AS layout_item_id,
                case_hydraulic_diagram_items.entity_type,
                case_hydraulic_diagram_items.entity_id,
                case_hydraulic_diagram_items.x,
                case_hydraulic_diagram_items.y,
                case_hydraulic_diagram_items.z_index,
                case_hydraulic_diagram_items.metadata_json,
                hydraulic_nodes.node_type AS component_type,
                hydraulic_nodes.node_key AS technical_key,
                case_hydraulic_nodes.case_label AS display_name
            FROM case_hydraulic_diagram_items
            JOIN case_hydraulic_nodes
              ON case_hydraulic_nodes.id = case_hydraulic_diagram_items.entity_id
            JOIN hydraulic_nodes
              ON hydraulic_nodes.id = case_hydraulic_nodes.hydraulic_node_id
            WHERE case_hydraulic_diagram_items.diagram_layout_id = ?
              AND case_hydraulic_diagram_items.entity_type = 'case_hydraulic_node'
            """,
            (layout_id,),
        ).fetchall()
        plant_rows = self.connection.execute(
            """
            SELECT
                case_hydraulic_diagram_items.id AS layout_item_id,
                case_hydraulic_diagram_items.entity_type,
                case_hydraulic_diagram_items.entity_id,
                case_hydraulic_diagram_items.x,
                case_hydraulic_diagram_items.y,
                case_hydraulic_diagram_items.z_index,
                case_hydraulic_diagram_items.metadata_json,
                'plant' AS component_type,
                hydraulic_plants.plant_key AS technical_key,
                case_hydraulic_plants.case_label AS display_name
            FROM case_hydraulic_diagram_items
            JOIN case_hydraulic_plants
              ON case_hydraulic_plants.id = case_hydraulic_diagram_items.entity_id
            JOIN hydraulic_plants
              ON hydraulic_plants.id = case_hydraulic_plants.hydraulic_plant_id
            WHERE case_hydraulic_diagram_items.diagram_layout_id = ?
              AND case_hydraulic_diagram_items.entity_type = 'case_hydraulic_plant'
            """,
            (layout_id,),
        ).fetchall()
        nodes = [hydraulic_diagram_node_row_to_dict(row) for row in node_rows + plant_rows]
        nodes.sort(key=lambda node: (node["z_index"], node["layout_item_id"]))
        case_id = int(context["optimization_case"]["id"])
        project_id = int(context["hydraulic_system"]["project_id"])
        for node in nodes:
            self._attach_reservoir_detail(node, case_id=case_id, project_id=project_id)
            self._attach_inflow_detail(node, case_id=case_id, project_id=project_id)
            self._attach_plant_detail(node, case_id=case_id, project_id=project_id)
        reach_rows = self.connection.execute(
            """
            SELECT
                case_hydraulic_diagram_items.id AS layout_item_id,
                case_hydraulic_diagram_items.z_index,
                case_hydraulic_diagram_items.metadata_json,
                case_hydraulic_reaches.id AS entity_id,
                case_hydraulic_reaches.hydraulic_reach_id AS base_reach_id,
                case_hydraulic_reaches.flow_min_m3s,
                case_hydraulic_reaches.spill_penalty_usd_per_hm3,
                hydraulic_reaches.reach_key AS technical_key,
                case_hydraulic_reaches.case_label AS display_name,
                hydraulic_reaches.reach_type,
                hydraulic_reaches.routing_method,
                hydraulic_reaches.travel_time_hours,
                from_nodes.node_key AS from_node_key,
                to_nodes.node_key AS to_node_key
            FROM case_hydraulic_reaches
            JOIN hydraulic_reaches
              ON hydraulic_reaches.id = case_hydraulic_reaches.hydraulic_reach_id
            JOIN hydraulic_nodes AS from_nodes
              ON from_nodes.id = hydraulic_reaches.from_node_id
            JOIN hydraulic_nodes AS to_nodes
              ON to_nodes.id = hydraulic_reaches.to_node_id
            LEFT JOIN case_hydraulic_diagram_items
              ON case_hydraulic_diagram_items.entity_type = 'case_hydraulic_reach'
             AND case_hydraulic_diagram_items.entity_id = case_hydraulic_reaches.id
             AND case_hydraulic_diagram_items.diagram_layout_id = ?
            WHERE case_hydraulic_reaches.case_id = ?
              AND case_hydraulic_reaches.is_active = 1
            ORDER BY COALESCE(case_hydraulic_diagram_items.z_index, 0),
                     case_hydraulic_reaches.id
            """,
            (layout_id, int(context["optimization_case"]["id"])),
        ).fetchall()
        reaches = [hydraulic_diagram_reach_row_to_dict(row) for row in reach_rows]
        for reach, row in zip(reaches, reach_rows):
            self._attach_reach_minimum_flow_detail(
                reach,
                case_id=case_id,
                project_id=project_id,
                base_reach_id=int(row["base_reach_id"]),
            )
        return {
            "scenario_id": context["scenario_id"],
            "optimization_case": optimization_case_public_dict(context["optimization_case"]),
            "hydraulic_system": hydraulic_system_public_dict(context["hydraulic_system"]),
            "layout": hydraulic_layout_public_dict(layout),
            "revision": str(layout["layout_version"]),
            "validation": hydraulic_validation_public_dict(
                context["optimization_case"].get("validation_payload_json")
            ),
            "nodes": nodes,
            "reaches": reaches,
        }

    def _validate_active_reservoirs(self, case_id: int) -> list[dict[str, Any]]:
        reservoir_rows = self.connection.execute(
            """
            SELECT case_hydraulic_nodes.id AS case_hydraulic_node_id,
                   hydraulic_nodes.node_key
            FROM case_hydraulic_nodes
            JOIN hydraulic_nodes
              ON hydraulic_nodes.id = case_hydraulic_nodes.hydraulic_node_id
            WHERE case_hydraulic_nodes.case_id = ?
              AND case_hydraulic_nodes.is_active = 1
              AND hydraulic_nodes.node_type = 'reservoir'
            ORDER BY case_hydraulic_nodes.id
            """,
            (case_id,),
        ).fetchall()
        errors: list[dict[str, Any]] = []
        for row in reservoir_rows:
            case_hydraulic_node_id = int(row["case_hydraulic_node_id"])
            node_key = str(row["node_key"])

            def add_error(code: str, message: str) -> None:
                errors.append(
                    {
                        "severity": "error",
                        "code": code,
                        "message": message,
                        "entity_type": "case_hydraulic_node",
                        "entity_id": case_hydraulic_node_id,
                        "technical_key": node_key,
                    }
                )

            params_row = self.connection.execute(
                """
                SELECT storage_min_hm3, storage_max_hm3, initial_storage_hm3,
                       terminal_condition, terminal_storage_min_hm3,
                       terminal_water_value_usd_per_hm3
                FROM case_hydraulic_reservoir_parameters
                WHERE case_id = ? AND case_hydraulic_node_id = ?
                """,
                (case_id, case_hydraulic_node_id),
            ).fetchone()
            binding_row = self.connection.execute(
                """
                SELECT hydraulic_curve_set_id
                FROM case_hydraulic_curve_bindings
                WHERE case_id = ?
                  AND entity_type = 'case_hydraulic_node'
                  AND entity_id = ?
                  AND curve_role = ?
                """,
                (case_id, case_hydraulic_node_id, STORAGE_ELEVATION_CURVE_KEY),
            ).fetchone()

            if params_row is None:
                add_error(
                    "missing_reservoir_parameters",
                    f"Reservoir {node_key} requires storage parameters before validation.",
                )
            if binding_row is None:
                add_error(
                    "missing_storage_elevation_curve",
                    f"Reservoir {node_key} requires a storage_elevation curve binding.",
                )

            points: list[dict[str, float]] = []
            if binding_row is not None:
                points = self._load_curve_set_points(
                    int(binding_row["hydraulic_curve_set_id"])
                )
                storages = [point["x_value"] for point in points]
                elevations = [point["y_value"] for point in points]
                if any(
                    storages[index] >= storages[index + 1]
                    for index in range(len(storages) - 1)
                ):
                    add_error(
                        "non_increasing_storage_points",
                        f"Reservoir {node_key} storage points must strictly increase.",
                    )
                if any(
                    elevations[index] > elevations[index + 1]
                    for index in range(len(elevations) - 1)
                ):
                    add_error(
                        "decreasing_elevation_points",
                        f"Reservoir {node_key} elevation points must be non-decreasing.",
                    )

            if params_row is not None:
                storage_min = float(params_row["storage_min_hm3"])
                storage_max = float(params_row["storage_max_hm3"])
                if points:
                    domain_min = min(point["x_value"] for point in points)
                    domain_max = max(point["x_value"] for point in points)
                    if storage_min < domain_min or storage_max > domain_max:
                        add_error(
                            "storage_bounds_outside_curve_domain",
                            f"Reservoir {node_key} storage bounds fall outside the curve domain.",
                        )
                terminal_condition = str(params_row["terminal_condition"])
                terminal_storage_min = params_row["terminal_storage_min_hm3"]
                terminal_water_value = float(
                    params_row["terminal_water_value_usd_per_hm3"]
                )
                terminal_invalid = False
                if terminal_condition == "min_terminal":
                    if terminal_storage_min is None:
                        terminal_invalid = True
                    elif not (storage_min <= float(terminal_storage_min) <= storage_max):
                        terminal_invalid = True
                if terminal_water_value < 0:
                    terminal_invalid = True
                if terminal_invalid:
                    add_error(
                        "invalid_terminal_settings",
                        f"Reservoir {node_key} has invalid terminal condition settings.",
                    )
        return errors

    def _reference_inflow_horizon(
        self, case_id: int
    ) -> tuple[tuple[Any, ...], ...] | None:
        binding_row = self.connection.execute(
            """
            SELECT hydraulic_time_series_set_id, time_series_set_id
            FROM case_hydraulic_time_series_bindings
            WHERE case_id = ?
              AND entity_type = 'case_hydraulic_node'
              AND signal_key = ?
            ORDER BY entity_id
            LIMIT 1
            """,
            (case_id, NATURAL_INFLOW_SIGNAL_KEY),
        ).fetchone()
        if binding_row is None:
            return None
        points = self._load_bound_hydraulic_points(
            hydraulic_time_series_set_id=binding_row["hydraulic_time_series_set_id"],
            time_series_set_id=binding_row["time_series_set_id"],
        )
        return tuple((point["timestamp"], point["duration_hours"]) for point in points)

    def _validate_reach_controls(self, case_id: int) -> list[dict[str, Any]]:
        reach_rows = self.connection.execute(
            """
            SELECT
                case_hydraulic_reaches.id AS case_hydraulic_reach_id,
                hydraulic_reaches.reach_key,
                hydraulic_reaches.reach_type,
                case_hydraulic_reaches.flow_min_m3s,
                case_hydraulic_reaches.spill_penalty_usd_per_hm3
            FROM case_hydraulic_reaches
            JOIN hydraulic_reaches
              ON hydraulic_reaches.id = case_hydraulic_reaches.hydraulic_reach_id
            WHERE case_hydraulic_reaches.case_id = ?
              AND case_hydraulic_reaches.is_active = 1
            ORDER BY case_hydraulic_reaches.id
            """,
            (case_id,),
        ).fetchall()
        errors: list[dict[str, Any]] = []
        reference_horizon = self._reference_inflow_horizon(case_id)
        for row in reach_rows:
            reach_key = str(row["reach_key"])
            case_reach_id = int(row["case_hydraulic_reach_id"])

            def make_error(code: str, message: str) -> dict[str, Any]:
                return {
                    "severity": "error",
                    "code": code,
                    "message": message,
                    "entity_type": "case_hydraulic_reach",
                    "entity_id": case_reach_id,
                    "technical_key": reach_key,
                }

            flow_min = row["flow_min_m3s"]
            if flow_min is not None and float(flow_min) < 0:
                errors.append(
                    make_error(
                        "negative_minimum_flow",
                        f"Reach {reach_key} minimum_flow_m3s must be nonnegative.",
                    )
                )
            spill_penalty = row["spill_penalty_usd_per_hm3"]
            if spill_penalty is not None:
                if float(spill_penalty) < 0:
                    errors.append(
                        make_error(
                            "negative_spill_penalty",
                            f"Reach {reach_key} spill_penalty_usd_per_hm3 must be "
                            "nonnegative.",
                        )
                    )
                if str(row["reach_type"]) != "spillway":
                    errors.append(
                        make_error(
                            "spill_penalty_requires_spillway",
                            f"Reach {reach_key} spill penalty requires a spillway "
                            "reach type.",
                        )
                    )

            binding_row = self.connection.execute(
                """
                SELECT hydraulic_time_series_set_id, time_series_set_id
                FROM case_hydraulic_time_series_bindings
                WHERE case_id = ?
                  AND entity_type = 'case_hydraulic_reach'
                  AND entity_id = ?
                  AND signal_key = ?
                """,
                (case_id, case_reach_id, MINIMUM_FLOW_SIGNAL_KEY),
            ).fetchone()
            if binding_row is None:
                continue
            points = self._load_bound_hydraulic_points(
                hydraulic_time_series_set_id=binding_row["hydraulic_time_series_set_id"],
                time_series_set_id=binding_row["time_series_set_id"],
            )
            has_negative = any(
                math.isfinite(point["value_m3s"]) and point["value_m3s"] < 0
                for point in points
            )
            if has_negative:
                errors.append(
                    make_error(
                        "negative_minimum_flow",
                        f"Reach {reach_key} minimum_flow_m3s values must be "
                        "nonnegative.",
                    )
                )
            horizon = tuple(
                (point["timestamp"], point["duration_hours"]) for point in points
            )
            if reference_horizon is not None and horizon != reference_horizon:
                errors.append(
                    make_error(
                        "minimum_flow_horizon_mismatch",
                        f"Reach {reach_key} minimum_flow_m3s horizon must match the "
                        "natural inflow horizon.",
                    )
                )
        return errors

    def _validate_node_inflow_series(self, case_id: int) -> list[dict[str, Any]]:
        node_rows = self.connection.execute(
            """
            SELECT case_hydraulic_nodes.id AS case_hydraulic_node_id,
                   hydraulic_nodes.node_key,
                   hydraulic_nodes.node_type
            FROM case_hydraulic_nodes
            JOIN hydraulic_nodes
              ON hydraulic_nodes.id = case_hydraulic_nodes.hydraulic_node_id
            WHERE case_hydraulic_nodes.case_id = ?
              AND case_hydraulic_nodes.is_active = 1
            ORDER BY case_hydraulic_nodes.id
            """,
            (case_id,),
        ).fetchall()
        errors: list[dict[str, Any]] = []
        bound_horizons: list[tuple[int, str, tuple[tuple[str, float], ...]]] = []
        for row in node_rows:
            case_node_id = int(row["case_hydraulic_node_id"])
            node_key = str(row["node_key"])
            binding_row = self.connection.execute(
                """
                SELECT hydraulic_time_series_set_id, time_series_set_id
                FROM case_hydraulic_time_series_bindings
                WHERE case_id = ?
                  AND entity_type = 'case_hydraulic_node'
                  AND entity_id = ?
                  AND signal_key = ?
                """,
                (case_id, case_node_id, NATURAL_INFLOW_SIGNAL_KEY),
            ).fetchone()
            if binding_row is None:
                if str(row["node_type"]) == "reservoir":
                    errors.append(
                        {
                            "severity": "error",
                            "code": "missing_natural_inflow_series",
                            "message": (
                                f"Reservoir {node_key} requires a natural_inflow_m3s "
                                "series binding."
                            ),
                            "entity_type": "case_hydraulic_node",
                            "entity_id": case_node_id,
                            "technical_key": node_key,
                        }
                    )
                continue

            points = self._load_bound_hydraulic_points(
                hydraulic_time_series_set_id=binding_row["hydraulic_time_series_set_id"],
                time_series_set_id=binding_row["time_series_set_id"],
            )
            horizon = tuple(
                (point["timestamp"], point["duration_hours"]) for point in points
            )
            bound_horizons.append((case_node_id, node_key, horizon))
            has_negative = False
            has_nonnumeric = False
            for point in points:
                value = point["value_m3s"]
                if not math.isfinite(value):
                    has_nonnumeric = True
                elif value < 0:
                    has_negative = True
            if has_negative:
                errors.append(
                    {
                        "severity": "error",
                        "code": "negative_inflow_value",
                        "message": (
                            f"Node {node_key} natural_inflow_m3s values must be "
                            "nonnegative."
                        ),
                        "entity_type": "case_hydraulic_node",
                        "entity_id": case_node_id,
                        "technical_key": node_key,
                    }
                )
            if has_nonnumeric:
                errors.append(
                    {
                        "severity": "error",
                        "code": "nonnumeric_inflow_value",
                        "message": (
                            f"Node {node_key} natural_inflow_m3s values must be "
                            "finite numbers."
                        ),
                        "entity_type": "case_hydraulic_node",
                        "entity_id": case_node_id,
                        "technical_key": node_key,
                    }
                )

        if bound_horizons:
            reference_horizon = bound_horizons[0][2]
            for case_node_id, node_key, horizon in bound_horizons[1:]:
                if horizon != reference_horizon:
                    errors.append(
                        {
                            "severity": "error",
                            "code": "inflow_horizon_mismatch",
                            "message": (
                                f"Node {node_key} natural_inflow_m3s horizon must match "
                                "the other bound inflow series."
                            ),
                            "entity_type": "case_hydraulic_node",
                            "entity_id": case_node_id,
                            "technical_key": node_key,
                        }
                    )
        return errors

    def _validate_unsupported_topology(
        self, case_id: int, active_node_ids: set[int]
    ) -> list[dict[str, Any]]:
        """Reject graph shapes outside the MVP v3 solver capability.

        Detects unsupported routing/travel-time, cycles, disconnected islands
        without boundary conditions, and head-dependent/pump-only/reversible
        unit modes. Each error carries an entity reference so the UI can focus
        the affected component.
        """

        errors: list[dict[str, Any]] = []
        node_rows = self.connection.execute(
            """
            SELECT case_hydraulic_nodes.id AS case_node_id,
                   case_hydraulic_nodes.hydraulic_node_id AS base_node_id,
                   hydraulic_nodes.node_key,
                   hydraulic_nodes.node_type
            FROM case_hydraulic_nodes
            JOIN hydraulic_nodes
              ON hydraulic_nodes.id = case_hydraulic_nodes.hydraulic_node_id
            WHERE case_hydraulic_nodes.case_id = ?
              AND case_hydraulic_nodes.is_active = 1
            ORDER BY case_hydraulic_nodes.id
            """,
            (case_id,),
        ).fetchall()
        node_key_by_base_id: dict[int, str] = {}
        case_node_id_by_key: dict[str, int] = {}
        node_keys: list[str] = []
        boundary_keys: set[str] = set()
        for row in node_rows:
            key = str(row["node_key"])
            node_key_by_base_id[int(row["base_node_id"])] = key
            case_node_id_by_key[key] = int(row["case_node_id"])
            node_keys.append(key)
            if str(row["node_type"]) == "reservoir":
                boundary_keys.add(key)

        inflow_rows = self.connection.execute(
            """
            SELECT hydraulic_nodes.node_key
            FROM case_hydraulic_time_series_bindings
            JOIN case_hydraulic_nodes
              ON case_hydraulic_nodes.id = case_hydraulic_time_series_bindings.entity_id
            JOIN hydraulic_nodes
              ON hydraulic_nodes.id = case_hydraulic_nodes.hydraulic_node_id
            WHERE case_hydraulic_time_series_bindings.case_id = ?
              AND case_hydraulic_time_series_bindings.entity_type = 'case_hydraulic_node'
              AND case_hydraulic_time_series_bindings.signal_key = ?
              AND case_hydraulic_nodes.is_active = 1
            """,
            (case_id, NATURAL_INFLOW_SIGNAL_KEY),
        ).fetchall()
        for row in inflow_rows:
            boundary_keys.add(str(row["node_key"]))

        edges: list[tuple[str, str]] = []
        reach_by_edge: dict[tuple[str, str], dict[str, Any]] = {}
        reach_rows = self.connection.execute(
            """
            SELECT case_hydraulic_reaches.id AS case_reach_id,
                   hydraulic_reaches.reach_key,
                   hydraulic_reaches.from_node_id,
                   hydraulic_reaches.to_node_id,
                   hydraulic_reaches.routing_method,
                   hydraulic_reaches.travel_time_hours
            FROM case_hydraulic_reaches
            JOIN hydraulic_reaches
              ON hydraulic_reaches.id = case_hydraulic_reaches.hydraulic_reach_id
            WHERE case_hydraulic_reaches.case_id = ?
              AND case_hydraulic_reaches.is_active = 1
            ORDER BY case_hydraulic_reaches.id
            """,
            (case_id,),
        ).fetchall()
        for row in reach_rows:
            reach_key = str(row["reach_key"])
            case_reach_id = int(row["case_reach_id"])
            entity = {
                "entity_type": "case_hydraulic_reach",
                "entity_id": case_reach_id,
                "technical_key": reach_key,
            }
            routing_method = str(row["routing_method"] or "none")
            if routing_method not in HYDRAULIC_SUPPORTED_ROUTING_METHODS:
                errors.append(
                    {
                        "severity": "error",
                        "code": "unsupported_reach_routing",
                        "message": (
                            f"Reach {reach_key} uses unsupported routing method "
                            f"{routing_method}; only 'none' runs in the MVP solver."
                        ),
                        **entity,
                    }
                )
            travel_time = float(row["travel_time_hours"] or 0.0)
            if travel_time != 0.0:
                errors.append(
                    {
                        "severity": "error",
                        "code": "unsupported_reach_travel_time",
                        "message": (
                            f"Reach {reach_key} has travel_time_hours {travel_time}; "
                            "the MVP solver only supports non-delayed reaches."
                        ),
                        **entity,
                    }
                )
            from_key = node_key_by_base_id.get(int(row["from_node_id"]))
            to_key = node_key_by_base_id.get(int(row["to_node_id"]))
            if from_key is not None and to_key is not None:
                edges.append((from_key, to_key))
                reach_by_edge[(from_key, to_key)] = entity

        unit_rows = self.connection.execute(
            """
            SELECT case_hydraulic_units.id AS case_unit_id,
                   hydraulic_units.unit_key,
                   hydraulic_units.intake_node_id,
                   hydraulic_units.discharge_node_id,
                   hydraulic_units.operation_mode,
                   hydraulic_units.generation_mode
            FROM case_hydraulic_units
            JOIN hydraulic_units
              ON hydraulic_units.id = case_hydraulic_units.hydraulic_unit_id
            WHERE case_hydraulic_units.case_id = ?
              AND case_hydraulic_units.is_active = 1
            ORDER BY case_hydraulic_units.id
            """,
            (case_id,),
        ).fetchall()
        for row in unit_rows:
            unit_key = str(row["unit_key"])
            entity = {
                "entity_type": "case_hydraulic_unit",
                "entity_id": int(row["case_unit_id"]),
                "technical_key": unit_key,
            }
            operation_mode = str(row["operation_mode"] or "generation")
            if operation_mode not in HYDRAULIC_SUPPORTED_UNIT_OPERATION_MODES:
                errors.append(
                    {
                        "severity": "error",
                        "code": "unsupported_unit_operation_mode",
                        "message": (
                            f"Unit {unit_key} operation mode {operation_mode} is "
                            "unsupported; only generation runs in the MVP solver."
                        ),
                        **entity,
                    }
                )
            generation_mode = str(row["generation_mode"] or "flow_power_curve")
            if generation_mode not in HYDRAULIC_SUPPORTED_UNIT_GENERATION_MODES:
                errors.append(
                    {
                        "severity": "error",
                        "code": "unsupported_unit_generation_mode",
                        "message": (
                            f"Unit {unit_key} generation mode {generation_mode} is "
                            "unsupported; head-dependent generation is not in the MVP "
                            "solver."
                        ),
                        **entity,
                    }
                )
            intake_id = row["intake_node_id"]
            discharge_id = row["discharge_node_id"]
            if intake_id is None or discharge_id is None:
                continue
            from_key = node_key_by_base_id.get(int(intake_id))
            to_key = node_key_by_base_id.get(int(discharge_id))
            if from_key is not None and to_key is not None:
                edges.append((from_key, to_key))

        cycle = hydraulic_first_cycle(node_keys, edges)
        if cycle:
            cycle_set = set(cycle)
            cycle_path = " -> ".join(cycle + [cycle[0]])
            flagged_reaches = [
                entity
                for (from_key, to_key), entity in reach_by_edge.items()
                if from_key in cycle_set and to_key in cycle_set
            ]
            if flagged_reaches:
                for entity in flagged_reaches:
                    errors.append(
                        {
                            "severity": "error",
                            "code": "unsupported_cycle",
                            "message": (
                                "Reach "
                                f"{entity['technical_key']} closes an unsupported "
                                f"hydraulic cycle ({cycle_path}); the MVP solver only "
                                "runs acyclic networks."
                            ),
                            **entity,
                        }
                    )
            else:
                representative = sorted(cycle_set)[0]
                errors.append(
                    {
                        "severity": "error",
                        "code": "unsupported_cycle",
                        "message": (
                            f"Hydraulic cycle ({cycle_path}) is unsupported; the MVP "
                            "solver only runs acyclic networks."
                        ),
                        "entity_type": "case_hydraulic_node",
                        "entity_id": case_node_id_by_key.get(representative, 0),
                        "technical_key": representative,
                    }
                )

        components = hydraulic_weakly_connected_components(node_keys, edges)
        if len(components) > 1:
            for component in components:
                if any(key in boundary_keys for key in component):
                    continue
                representative = sorted(component)[0]
                member_list = ", ".join(sorted(component))
                errors.append(
                    {
                        "severity": "error",
                        "code": "island_without_boundary",
                        "message": (
                            f"Disconnected hydraulic island ({member_list}) has no "
                            "boundary condition (reservoir or natural inflow); add one "
                            "or remove the island before promotion."
                        ),
                        "entity_type": "case_hydraulic_node",
                        "entity_id": case_node_id_by_key.get(representative, 0),
                        "technical_key": representative,
                    }
                )
        return errors

    def _validate_active_plants_and_units(
        self, case_id: int, active_node_ids: set[int]
    ) -> list[dict[str, Any]]:
        errors: list[dict[str, Any]] = []
        plant_rows = self.connection.execute(
            """
            SELECT case_hydraulic_plants.id AS case_hydraulic_plant_id,
                   case_hydraulic_plants.non_modeled,
                   hydraulic_plants.plant_key
            FROM case_hydraulic_plants
            JOIN hydraulic_plants
              ON hydraulic_plants.id = case_hydraulic_plants.hydraulic_plant_id
            WHERE case_hydraulic_plants.case_id = ?
              AND case_hydraulic_plants.is_active = 1
            ORDER BY case_hydraulic_plants.id
            """,
            (case_id,),
        ).fetchall()
        for plant in plant_rows:
            case_plant_id = int(plant["case_hydraulic_plant_id"])
            plant_key = str(plant["plant_key"])
            unit_rows = self.connection.execute(
                """
                SELECT case_hydraulic_units.id AS case_unit_id,
                       case_hydraulic_units.hydraulic_unit_id AS base_unit_id,
                       case_hydraulic_units.is_active,
                       hydraulic_units.unit_key,
                       hydraulic_units.intake_node_id,
                       hydraulic_units.discharge_node_id
                FROM case_hydraulic_units
                JOIN hydraulic_units
                  ON hydraulic_units.id = case_hydraulic_units.hydraulic_unit_id
                WHERE case_hydraulic_units.case_id = ?
                  AND case_hydraulic_units.case_hydraulic_plant_id = ?
                ORDER BY case_hydraulic_units.id
                """,
                (case_id, case_plant_id),
            ).fetchall()
            active_units = [row for row in unit_rows if int(row["is_active"]) == 1]
            if not bool(plant["non_modeled"]) and not active_units:
                errors.append(
                    {
                        "severity": "error",
                        "code": "plant_without_active_units",
                        "message": f"Plant {plant_key} requires at least one active unit.",
                        "entity_type": "case_hydraulic_plant",
                        "entity_id": case_plant_id,
                        "technical_key": plant_key,
                    }
                )
            for unit in active_units:
                case_unit_id = int(unit["case_unit_id"])
                unit_key = str(unit["unit_key"])

                def add_unit_error(code: str, message: str) -> None:
                    errors.append(
                        {
                            "severity": "error",
                            "code": code,
                            "message": message,
                            "entity_type": "case_hydraulic_unit",
                            "entity_id": case_unit_id,
                            "technical_key": unit_key,
                        }
                    )

                intake_id = unit["intake_node_id"]
                discharge_id = unit["discharge_node_id"]
                if (
                    intake_id is None
                    or discharge_id is None
                    or int(intake_id) not in active_node_ids
                    or int(discharge_id) not in active_node_ids
                    or int(intake_id) == int(discharge_id)
                ):
                    add_unit_error(
                        "inactive_or_equal_unit_nodes",
                        f"Unit {unit_key} requires distinct active intake and discharge nodes.",
                    )

                binding_row = self.connection.execute(
                    """
                    SELECT hydraulic_curve_set_id
                    FROM case_hydraulic_curve_bindings
                    WHERE case_id = ?
                      AND entity_type = 'case_hydraulic_unit'
                      AND entity_id = ?
                      AND curve_role = ?
                    """,
                    (case_id, case_unit_id, FLOW_POWER_CURVE_KEY),
                ).fetchone()
                if binding_row is None:
                    add_unit_error(
                        "missing_flow_power_curve",
                        f"Unit {unit_key} requires a flow_power curve binding.",
                    )
                    continue
                points = self._load_curve_set_points(
                    int(binding_row["hydraulic_curve_set_id"])
                )
                flows = [point["x_value"] for point in points]
                powers = [point["y_value"] for point in points]
                invalid_curve = len(points) < 2
                if any(
                    flows[index] >= flows[index + 1] for index in range(len(flows) - 1)
                ):
                    invalid_curve = True
                if any(
                    powers[index] > powers[index + 1]
                    for index in range(len(powers) - 1)
                ):
                    invalid_curve = True
                if invalid_curve:
                    add_unit_error(
                        "invalid_flow_power_curve",
                        f"Unit {unit_key} flow_power curve must have increasing flow and non-decreasing power.",
                    )
        return errors

    def _attach_reservoir_detail(
        self,
        node: dict[str, Any],
        *,
        case_id: int,
        project_id: int,
    ) -> None:
        node["reservoir"] = None
        node["storage_elevation_curve"] = None
        node["available_curves"] = []
        if node.get("component_type") != "reservoir":
            return
        case_hydraulic_node_id = int(node["entity_id"])
        base_row = self.connection.execute(
            "SELECT hydraulic_node_id FROM case_hydraulic_nodes WHERE id = ?",
            (case_hydraulic_node_id,),
        ).fetchone()
        if base_row is None:
            return
        base_node_id = int(base_row["hydraulic_node_id"])

        params_row = self.connection.execute(
            """
            SELECT storage_min_hm3, storage_max_hm3, initial_storage_hm3,
                   terminal_condition, terminal_storage_min_hm3,
                   terminal_water_value_usd_per_hm3
            FROM case_hydraulic_reservoir_parameters
            WHERE case_id = ? AND case_hydraulic_node_id = ?
            """,
            (case_id, case_hydraulic_node_id),
        ).fetchone()
        if params_row is not None:
            node["reservoir"] = {
                "storage_min_hm3": float(params_row["storage_min_hm3"]),
                "storage_max_hm3": float(params_row["storage_max_hm3"]),
                "initial_storage_hm3": float(params_row["initial_storage_hm3"]),
                "terminal_condition": str(params_row["terminal_condition"]),
                "terminal_storage_min_hm3": (
                    None
                    if params_row["terminal_storage_min_hm3"] is None
                    else float(params_row["terminal_storage_min_hm3"])
                ),
                "terminal_water_value_usd_per_hm3": float(
                    params_row["terminal_water_value_usd_per_hm3"]
                ),
            }

        bound, available = self._entity_curve_detail(
            project_id=project_id,
            base_entity_type="hydraulic_node",
            base_entity_id=base_node_id,
            case_id=case_id,
            binding_entity_type="case_hydraulic_node",
            binding_entity_id=case_hydraulic_node_id,
            curve_key=STORAGE_ELEVATION_CURVE_KEY,
        )
        node["available_curves"] = available
        node["storage_elevation_curve"] = bound

    def _attach_inflow_detail(
        self,
        node: dict[str, Any],
        *,
        case_id: int,
        project_id: int,
    ) -> None:
        node["natural_inflow_series"] = None
        node["available_inflow_series"] = []
        if node.get("entity_type") != "case_hydraulic_node":
            return
        case_hydraulic_node_id = int(node["entity_id"])
        base_row = self.connection.execute(
            "SELECT hydraulic_node_id FROM case_hydraulic_nodes WHERE id = ?",
            (case_hydraulic_node_id,),
        ).fetchone()
        if base_row is None:
            return
        bound, available = self._entity_inflow_series_detail(
            project_id=project_id,
            base_entity_id=int(base_row["hydraulic_node_id"]),
            case_id=case_id,
            binding_entity_id=case_hydraulic_node_id,
        )
        node["natural_inflow_series"] = bound
        node["available_inflow_series"] = available

    def _attach_reach_minimum_flow_detail(
        self,
        reach: dict[str, Any],
        *,
        case_id: int,
        project_id: int,
        base_reach_id: int,
    ) -> None:
        bound, available = self._entity_inflow_series_detail(
            project_id=project_id,
            base_entity_id=base_reach_id,
            case_id=case_id,
            binding_entity_id=int(reach["entity_id"]),
            signal_key=MINIMUM_FLOW_SIGNAL_KEY,
            base_entity_type="hydraulic_reach",
            binding_entity_type="case_hydraulic_reach",
        )
        reach["minimum_flow_series"] = bound
        reach["available_minimum_flow_series"] = available

    def _entity_curve_detail(
        self,
        *,
        project_id: int,
        base_entity_type: str,
        base_entity_id: int,
        case_id: int,
        binding_entity_type: str,
        binding_entity_id: int,
        curve_key: str,
    ) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
        curve_rows = self.connection.execute(
            """
            SELECT id, version_number, version_label
            FROM hydraulic_curve_sets
            WHERE project_id = ?
              AND entity_type = ?
              AND entity_id = ?
              AND curve_key = ?
            ORDER BY version_number
            """,
            (project_id, base_entity_type, base_entity_id, curve_key),
        ).fetchall()
        available = [
            {
                "curve_set_id": int(row["id"]),
                "version_number": int(row["version_number"]),
                "version_label": str(row["version_label"]),
                "points": self._load_curve_set_points(int(row["id"])),
            }
            for row in curve_rows
        ]
        binding_row = self.connection.execute(
            """
            SELECT hydraulic_curve_set_id
            FROM case_hydraulic_curve_bindings
            WHERE case_id = ?
              AND entity_type = ?
              AND entity_id = ?
              AND curve_role = ?
            """,
            (case_id, binding_entity_type, binding_entity_id, curve_key),
        ).fetchone()
        bound = None
        if binding_row is not None:
            bound_id = int(binding_row["hydraulic_curve_set_id"])
            bound = next(
                (curve for curve in available if curve["curve_set_id"] == bound_id),
                None,
            )
        return bound, available

    def _attach_plant_detail(
        self,
        node: dict[str, Any],
        *,
        case_id: int,
        project_id: int,
    ) -> None:
        node["plant"] = None
        node["units"] = []
        if node.get("component_type") != "plant":
            return
        case_hydraulic_plant_id = int(node["entity_id"])
        plant_row = self.connection.execute(
            """
            SELECT non_modeled, min_power_mw, max_power_mw
            FROM case_hydraulic_plants
            WHERE id = ?
            """,
            (case_hydraulic_plant_id,),
        ).fetchone()
        if plant_row is None:
            return
        node["plant"] = {
            "non_modeled": bool(plant_row["non_modeled"]),
            "min_power_mw": _optional_float(plant_row["min_power_mw"]),
            "max_power_mw": _optional_float(plant_row["max_power_mw"]),
        }
        unit_rows = self.connection.execute(
            """
            SELECT
                case_hydraulic_units.id AS case_unit_id,
                case_hydraulic_units.hydraulic_unit_id AS base_unit_id,
                hydraulic_units.unit_key,
                hydraulic_units.operation_mode,
                hydraulic_units.generation_mode,
                case_hydraulic_units.case_label,
                case_hydraulic_units.is_active,
                case_hydraulic_units.min_power_mw,
                case_hydraulic_units.max_power_mw,
                case_hydraulic_units.min_flow_m3s,
                case_hydraulic_units.max_flow_m3s,
                intake_nodes.node_key AS intake_node_key,
                discharge_nodes.node_key AS discharge_node_key
            FROM case_hydraulic_units
            JOIN hydraulic_units
              ON hydraulic_units.id = case_hydraulic_units.hydraulic_unit_id
            LEFT JOIN hydraulic_nodes AS intake_nodes
              ON intake_nodes.id = hydraulic_units.intake_node_id
            LEFT JOIN hydraulic_nodes AS discharge_nodes
              ON discharge_nodes.id = hydraulic_units.discharge_node_id
            WHERE case_hydraulic_units.case_id = ?
              AND case_hydraulic_units.case_hydraulic_plant_id = ?
            ORDER BY case_hydraulic_units.id
            """,
            (case_id, case_hydraulic_plant_id),
        ).fetchall()
        units: list[dict[str, Any]] = []
        for row in unit_rows:
            bound, available = self._entity_curve_detail(
                project_id=project_id,
                base_entity_type="hydraulic_unit",
                base_entity_id=int(row["base_unit_id"]),
                case_id=case_id,
                binding_entity_type="case_hydraulic_unit",
                binding_entity_id=int(row["case_unit_id"]),
                curve_key=FLOW_POWER_CURVE_KEY,
            )
            units.append(
                {
                    "technical_key": str(row["unit_key"]),
                    "display_name": str(row["case_label"]),
                    "is_active": bool(row["is_active"]),
                    "operation_mode": str(row["operation_mode"] or "generation"),
                    "generation_mode": str(row["generation_mode"] or "flow_power_curve"),
                    "intake_node_key": row["intake_node_key"],
                    "discharge_node_key": row["discharge_node_key"],
                    "min_power_mw": _optional_float(row["min_power_mw"]),
                    "max_power_mw": _optional_float(row["max_power_mw"]),
                    "min_flow_m3s": _optional_float(row["min_flow_m3s"]),
                    "max_flow_m3s": _optional_float(row["max_flow_m3s"]),
                    "flow_power_curve": bound,
                    "available_curves": available,
                }
            )
        node["units"] = units

    def _create_case_hydraulic_node(
        self,
        *,
        case_id: int,
        system_id: int,
        node_key: str,
        display_name: str,
        node_type: str,
        updated_by: str,
        now: str,
    ) -> dict[str, int]:
        self.connection.execute(
            """
            INSERT INTO hydraulic_nodes (
                hydraulic_system_id,
                node_key,
                display_name,
                node_type,
                created_at,
                updated_at,
                created_by,
                updated_by
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (hydraulic_system_id, node_key) DO UPDATE SET
                display_name = excluded.display_name,
                node_type = excluded.node_type,
                updated_at = excluded.updated_at,
                updated_by = excluded.updated_by
            """,
            (system_id, node_key, display_name, node_type, now, now, updated_by, updated_by),
        )
        node_row = self.connection.execute(
            """
            SELECT id
            FROM hydraulic_nodes
            WHERE hydraulic_system_id = ? AND node_key = ?
            """,
            (system_id, node_key),
        ).fetchone()
        cursor = self.connection.execute(
            """
            INSERT INTO case_hydraulic_nodes (
                case_id,
                hydraulic_node_id,
                case_label,
                is_active,
                created_at,
                updated_at,
                created_by,
                updated_by
            )
            VALUES (?, ?, ?, 1, ?, ?, ?, ?)
            """,
            (case_id, int(node_row["id"]), display_name, now, now, updated_by, updated_by),
        )
        return {
            "case_hydraulic_node_id": int(cursor.lastrowid),
            "hydraulic_node_id": int(node_row["id"]),
        }

    def _resolve_hydraulic_node_for_reach(
        self,
        system_id: int,
        node_key: str,
        active_nodes_by_key: Mapping[str, dict[str, Any]],
    ) -> dict[str, Any]:
        if node_key in active_nodes_by_key:
            return active_nodes_by_key[node_key]
        row = self.connection.execute(
            """
            SELECT id
            FROM hydraulic_nodes
            WHERE hydraulic_system_id = ? AND node_key = ?
            """,
            (system_id, node_key),
        ).fetchone()
        if row is None:
            raise ValueError(f"hydraulic reach endpoint not found: {node_key}")
        return {"hydraulic_node_id": int(row["id"])}

    def _create_case_hydraulic_reach(
        self,
        *,
        case_id: int,
        system_id: int,
        reach_key: str,
        display_name: str,
        from_node_id: int,
        to_node_id: int,
        reach_type: str,
        updated_by: str,
        now: str,
        flow_min_m3s: float | None = None,
        spill_penalty_usd_per_hm3: float | None = None,
        routing_method: str = "none",
        travel_time_hours: float = 0.0,
    ) -> dict[str, int]:
        self.connection.execute(
            """
            INSERT INTO hydraulic_reaches (
                hydraulic_system_id,
                reach_key,
                display_name,
                from_node_id,
                to_node_id,
                reach_type,
                travel_time_hours,
                routing_method,
                created_at,
                updated_at,
                created_by,
                updated_by
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (hydraulic_system_id, reach_key) DO UPDATE SET
                display_name = excluded.display_name,
                from_node_id = excluded.from_node_id,
                to_node_id = excluded.to_node_id,
                reach_type = excluded.reach_type,
                travel_time_hours = excluded.travel_time_hours,
                routing_method = excluded.routing_method,
                updated_at = excluded.updated_at,
                updated_by = excluded.updated_by
            """,
            (
                system_id,
                reach_key,
                display_name,
                from_node_id,
                to_node_id,
                reach_type,
                travel_time_hours,
                routing_method,
                now,
                now,
                updated_by,
                updated_by,
            ),
        )
        reach_row = self.connection.execute(
            """
            SELECT id
            FROM hydraulic_reaches
            WHERE hydraulic_system_id = ? AND reach_key = ?
            """,
            (system_id, reach_key),
        ).fetchone()
        cursor = self.connection.execute(
            """
            INSERT INTO case_hydraulic_reaches (
                case_id,
                hydraulic_reach_id,
                case_label,
                is_active,
                flow_min_m3s,
                spill_penalty_usd_per_hm3,
                created_at,
                updated_at,
                created_by,
                updated_by
            )
            VALUES (?, ?, ?, 1, ?, ?, ?, ?, ?, ?)
            """,
            (
                case_id,
                int(reach_row["id"]),
                display_name,
                flow_min_m3s,
                spill_penalty_usd_per_hm3,
                now,
                now,
                updated_by,
                updated_by,
            ),
        )
        return {
            "case_hydraulic_reach_id": int(cursor.lastrowid),
            "hydraulic_reach_id": int(reach_row["id"]),
        }

    def _create_case_hydraulic_plant(
        self,
        *,
        case_id: int,
        system_id: int,
        plant_key: str,
        display_name: str,
        plant: Mapping[str, Any] | None,
        updated_by: str,
        now: str,
    ) -> dict[str, int]:
        self.connection.execute(
            """
            INSERT INTO hydraulic_plants (
                hydraulic_system_id,
                plant_key,
                display_name,
                created_at,
                updated_at,
                created_by,
                updated_by
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (hydraulic_system_id, plant_key) DO UPDATE SET
                display_name = excluded.display_name,
                updated_at = excluded.updated_at,
                updated_by = excluded.updated_by
            """,
            (system_id, plant_key, display_name, now, now, updated_by, updated_by),
        )
        plant_row = self.connection.execute(
            """
            SELECT id
            FROM hydraulic_plants
            WHERE hydraulic_system_id = ? AND plant_key = ?
            """,
            (system_id, plant_key),
        ).fetchone()
        non_modeled = 1 if (plant or {}).get("non_modeled") else 0
        min_power = (plant or {}).get("min_power_mw")
        max_power = (plant or {}).get("max_power_mw")
        cursor = self.connection.execute(
            """
            INSERT INTO case_hydraulic_plants (
                case_id,
                hydraulic_plant_id,
                case_label,
                is_active,
                non_modeled,
                min_power_mw,
                max_power_mw,
                created_at,
                updated_at,
                created_by,
                updated_by
            )
            VALUES (?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                case_id,
                int(plant_row["id"]),
                display_name,
                non_modeled,
                min_power,
                max_power,
                now,
                now,
                updated_by,
                updated_by,
            ),
        )
        return {
            "case_hydraulic_plant_id": int(cursor.lastrowid),
            "hydraulic_plant_id": int(plant_row["id"]),
        }

    def _persist_case_hydraulic_unit(
        self,
        *,
        project_id: int,
        system_id: int,
        case_id: int,
        hydraulic_plant_id: int,
        case_hydraulic_plant_id: int,
        unit: Mapping[str, Any],
        active_nodes_by_key: Mapping[str, dict[str, Any]],
        updated_by: str,
        now: str,
    ) -> None:
        intake_node_id = self._resolve_unit_node_id(
            system_id, unit.get("intake_node_key"), active_nodes_by_key
        )
        discharge_node_id = self._resolve_unit_node_id(
            system_id, unit.get("discharge_node_key"), active_nodes_by_key
        )
        unit_key = unit["technical_key"]
        display_name = unit["display_name"]
        self.connection.execute(
            """
            INSERT INTO hydraulic_units (
                hydraulic_plant_id,
                unit_key,
                display_name,
                intake_node_id,
                discharge_node_id,
                operation_mode,
                generation_mode,
                created_at,
                updated_at,
                created_by,
                updated_by
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (hydraulic_plant_id, unit_key) DO UPDATE SET
                display_name = excluded.display_name,
                intake_node_id = excluded.intake_node_id,
                discharge_node_id = excluded.discharge_node_id,
                operation_mode = excluded.operation_mode,
                generation_mode = excluded.generation_mode,
                updated_at = excluded.updated_at,
                updated_by = excluded.updated_by
            """,
            (
                hydraulic_plant_id,
                unit_key,
                display_name,
                intake_node_id,
                discharge_node_id,
                str(unit.get("operation_mode") or "generation"),
                str(unit.get("generation_mode") or "flow_power_curve"),
                now,
                now,
                updated_by,
                updated_by,
            ),
        )
        unit_row = self.connection.execute(
            """
            SELECT id
            FROM hydraulic_units
            WHERE hydraulic_plant_id = ? AND unit_key = ?
            """,
            (hydraulic_plant_id, unit_key),
        ).fetchone()
        base_unit_id = int(unit_row["id"])
        cursor = self.connection.execute(
            """
            INSERT INTO case_hydraulic_units (
                case_id,
                hydraulic_unit_id,
                case_hydraulic_plant_id,
                case_label,
                is_active,
                min_power_mw,
                max_power_mw,
                min_flow_m3s,
                max_flow_m3s,
                created_at,
                updated_at,
                created_by,
                updated_by
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                case_id,
                base_unit_id,
                case_hydraulic_plant_id,
                display_name,
                1 if unit.get("is_active", True) else 0,
                unit.get("min_power_mw"),
                unit.get("max_power_mw"),
                unit.get("min_flow_m3s"),
                unit.get("max_flow_m3s"),
                now,
                now,
                updated_by,
                updated_by,
            ),
        )
        case_unit_id = int(cursor.lastrowid)
        if unit.get("flow_power_curve") is not None:
            self._persist_hydraulic_curve(
                project_id=project_id,
                base_entity_id=base_unit_id,
                case_id=case_id,
                binding_entity_type="case_hydraulic_unit",
                binding_entity_id=case_unit_id,
                curve=unit["flow_power_curve"],
                spec=FLOW_POWER_CURVE_SPEC,
                updated_by=updated_by,
                now=now,
            )

    def _resolve_unit_node_id(
        self,
        system_id: int,
        node_key: str | None,
        active_nodes_by_key: Mapping[str, dict[str, Any]],
    ) -> int | None:
        if not node_key:
            return None
        return self._resolve_hydraulic_node_for_reach(
            system_id, node_key, active_nodes_by_key
        )["hydraulic_node_id"]

    def _persist_reservoir_parameters(
        self,
        *,
        case_id: int,
        case_hydraulic_node_id: int,
        reservoir: Mapping[str, Any],
        updated_by: str,
        now: str,
    ) -> None:
        self.connection.execute(
            """
            INSERT INTO case_hydraulic_reservoir_parameters (
                case_id,
                case_hydraulic_node_id,
                storage_min_hm3,
                storage_max_hm3,
                initial_storage_hm3,
                terminal_condition,
                terminal_storage_min_hm3,
                terminal_water_value_usd_per_hm3,
                created_at,
                updated_at,
                created_by,
                updated_by
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                case_id,
                case_hydraulic_node_id,
                reservoir["storage_min_hm3"],
                reservoir["storage_max_hm3"],
                reservoir["initial_storage_hm3"],
                reservoir["terminal_condition"],
                reservoir["terminal_storage_min_hm3"],
                reservoir["terminal_water_value_usd_per_hm3"],
                now,
                now,
                updated_by,
                updated_by,
            ),
        )

    def _persist_hydraulic_curve(
        self,
        *,
        project_id: int,
        base_entity_id: int,
        case_id: int,
        binding_entity_type: str,
        binding_entity_id: int,
        curve: Mapping[str, Any],
        spec: Mapping[str, str],
        updated_by: str,
        now: str,
    ) -> None:
        curve_set_id = self._resolve_hydraulic_curve_set(
            project_id=project_id,
            base_entity_id=base_entity_id,
            curve=curve,
            spec=spec,
            updated_by=updated_by,
            now=now,
        )
        if curve_set_id is None:
            return
        self.connection.execute(
            """
            INSERT INTO case_hydraulic_curve_bindings (
                case_id,
                entity_type,
                entity_id,
                curve_role,
                hydraulic_curve_set_id,
                required,
                created_at,
                updated_at,
                created_by,
                updated_by
            )
            VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?, ?)
            """,
            (
                case_id,
                binding_entity_type,
                binding_entity_id,
                spec["curve_key"],
                curve_set_id,
                now,
                now,
                updated_by,
                updated_by,
            ),
        )

    def _resolve_hydraulic_curve_set(
        self,
        *,
        project_id: int,
        base_entity_id: int,
        curve: Mapping[str, Any],
        spec: Mapping[str, str],
        updated_by: str,
        now: str,
    ) -> int | None:
        entity_type = spec["base_entity_type"]
        curve_key = spec["curve_key"]
        if curve.get("curve_set_id") is not None:
            row = self.connection.execute(
                """
                SELECT id
                FROM hydraulic_curve_sets
                WHERE id = ?
                  AND project_id = ?
                  AND entity_type = ?
                  AND entity_id = ?
                  AND curve_key = ?
                """,
                (
                    int(curve["curve_set_id"]),
                    project_id,
                    entity_type,
                    base_entity_id,
                    curve_key,
                ),
            ).fetchone()
            if row is None:
                raise ValueError(f"{curve_key} curve set not found for entity")
            return int(row["id"])

        points = curve.get("points") or []
        if not points:
            return None

        content_hash = hydraulic_curve_content_hash(points)
        existing = self.connection.execute(
            """
            SELECT id
            FROM hydraulic_curve_sets
            WHERE project_id = ?
              AND entity_type = ?
              AND entity_id = ?
              AND curve_key = ?
              AND content_hash = ?
            ORDER BY version_number
            LIMIT 1
            """,
            (project_id, entity_type, base_entity_id, curve_key, content_hash),
        ).fetchone()
        if existing is not None:
            return int(existing["id"])

        next_version_row = self.connection.execute(
            """
            SELECT COALESCE(MAX(version_number), 0) + 1 AS next_version
            FROM hydraulic_curve_sets
            WHERE project_id = ?
              AND entity_type = ?
              AND entity_id = ?
              AND curve_key = ?
            """,
            (project_id, entity_type, base_entity_id, curve_key),
        ).fetchone()
        version_number = int(next_version_row["next_version"])
        version_label = curve.get("version_label") or f"v{version_number}"
        cursor = self.connection.execute(
            """
            INSERT INTO hydraulic_curve_sets (
                project_id,
                entity_type,
                entity_id,
                curve_key,
                version_number,
                version_label,
                curve_dimension,
                axis_x_name,
                axis_x_unit,
                axis_y_name,
                axis_y_unit,
                content_hash,
                status,
                created_at,
                updated_at,
                created_by,
                updated_by
            )
            VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?, 'draft', ?, ?, ?, ?)
            """,
            (
                project_id,
                entity_type,
                base_entity_id,
                curve_key,
                version_number,
                version_label,
                spec["axis_x_name"],
                spec["axis_x_unit"],
                spec["axis_y_name"],
                spec["axis_y_unit"],
                content_hash,
                now,
                now,
                updated_by,
                updated_by,
            ),
        )
        curve_set_id = int(cursor.lastrowid)
        for point_index, point in enumerate(points):
            self.connection.execute(
                """
                INSERT INTO hydraulic_curve_points (
                    hydraulic_curve_set_id,
                    point_index,
                    x_value,
                    y_value
                )
                VALUES (?, ?, ?, ?)
                """,
                (curve_set_id, point_index, point["x_value"], point["y_value"]),
            )
        return curve_set_id

    def _load_curve_set_points(self, curve_set_id: int) -> list[dict[str, float]]:
        rows = self.connection.execute(
            """
            SELECT x_value, y_value
            FROM hydraulic_curve_points
            WHERE hydraulic_curve_set_id = ?
            ORDER BY point_index
            """,
            (curve_set_id,),
        ).fetchall()
        return [
            {"x_value": float(row["x_value"]), "y_value": float(row["y_value"])}
            for row in rows
        ]

    def _persist_hydraulic_inflow_series(
        self,
        *,
        project_id: int,
        base_entity_id: int,
        case_id: int,
        binding_entity_type: str,
        binding_entity_id: int,
        series: Mapping[str, Any],
        updated_by: str,
        now: str,
        signal_key: str = NATURAL_INFLOW_SIGNAL_KEY,
        base_entity_type: str = "hydraulic_node",
    ) -> None:
        hydraulic_set_id, generic_set_id = self._resolve_hydraulic_inflow_series_binding(
            project_id=project_id,
            base_entity_id=base_entity_id,
            series=series,
            updated_by=updated_by,
            now=now,
            signal_key=signal_key,
            base_entity_type=base_entity_type,
        )
        if hydraulic_set_id is None and generic_set_id is None:
            return
        self.connection.execute(
            """
            INSERT INTO case_hydraulic_time_series_bindings (
                case_id,
                entity_type,
                entity_id,
                signal_key,
                hydraulic_time_series_set_id,
                time_series_set_id,
                required,
                created_at,
                updated_at,
                created_by,
                updated_by
            )
            VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?)
            """,
            (
                case_id,
                binding_entity_type,
                binding_entity_id,
                signal_key,
                hydraulic_set_id,
                generic_set_id,
                now,
                now,
                updated_by,
                updated_by,
            ),
        )

    def _resolve_hydraulic_inflow_series_binding(
        self,
        *,
        project_id: int,
        base_entity_id: int,
        series: Mapping[str, Any],
        updated_by: str,
        now: str,
        signal_key: str = NATURAL_INFLOW_SIGNAL_KEY,
        base_entity_type: str = "hydraulic_node",
    ) -> tuple[int | None, int | None]:
        """Resolve a saved node/reach series to a binding target.

        Returns ``(hydraulic_time_series_set_id, time_series_set_id)`` with
        exactly one populated, or ``(None, None)`` when there is no series to
        bind. An existing reference is looked up in whichever store
        ``series["origin_kind"]`` names (default: the legacy table, so
        already-bound pre-TS5-003 sets keep resolving the same way). A
        brand-new series (raw ``points``, no existing reference) is always
        written to the generic catalog model: the legacy hydraulic tables no
        longer grow from this point on.
        """
        existing_id = series.get("time_series_set_id")
        if existing_id is not None:
            if series.get("origin_kind") == "generic":
                row = self.connection.execute(
                    "SELECT id FROM time_series_sets WHERE id = ? AND project_id = ?",
                    (int(existing_id), project_id),
                ).fetchone()
                if row is None:
                    raise ValueError(f"{signal_key} series set not found for entity")
                return None, int(row["id"])
            row = self.connection.execute(
                """
                SELECT id
                FROM hydraulic_time_series_sets
                WHERE id = ?
                  AND project_id = ?
                  AND entity_type = ?
                  AND entity_id = ?
                  AND signal_key = ?
                """,
                (
                    int(existing_id),
                    project_id,
                    base_entity_type,
                    base_entity_id,
                    signal_key,
                ),
            ).fetchone()
            if row is None:
                raise ValueError(f"{signal_key} series set not found for entity")
            return int(row["id"]), None

        points = series.get("points") or []
        if not points:
            return None, None

        generic_set_id = self._write_generic_hydraulic_time_series_set(
            project_id=project_id,
            base_entity_type=base_entity_type,
            base_entity_id=base_entity_id,
            signal_key=signal_key,
            points=points,
            version_label=series.get("version_label"),
            updated_by=updated_by,
            now=now,
        )
        return None, generic_set_id

    def _write_generic_hydraulic_time_series_set(
        self,
        *,
        project_id: int,
        base_entity_type: str,
        base_entity_id: int,
        signal_key: str,
        points: list[Mapping[str, Any]],
        version_label: str | None,
        updated_by: str,
        now: str,
        status: str = "draft",
        revision_metadata: dict[str, Any] | None = None,
        change_summary: str = "Hydro diagram series write",
    ) -> int:
        name = _generic_hydraulic_series_name(base_entity_type, base_entity_id, signal_key)
        content_hash = hydraulic_inflow_series_content_hash(points)
        existing = self.connection.execute(
            """
            SELECT id
            FROM time_series_sets
            WHERE project_id = ? AND name = ? AND content_hash = ?
            ORDER BY version_number
            LIMIT 1
            """,
            (project_id, name, content_hash),
        ).fetchone()
        if existing is not None:
            return int(existing["id"])

        next_version_row = self.connection.execute(
            """
            SELECT COALESCE(MAX(version_number), 0) + 1 AS next_version
            FROM time_series_sets
            WHERE project_id = ? AND name = ?
            """,
            (project_id, name),
        ).fetchone()
        version_number = int(next_version_row["next_version"])
        resolved_version_label = version_label or f"v{version_number}"
        definition = TIME_SERIES_SIGNAL_CATALOG[signal_key]
        entity_key = str(base_entity_id)

        periods: list[CatalogPeriod] = []
        values: list[CatalogValue] = []
        for index, point in enumerate(points):
            timestamp_start = datetime.fromisoformat(str(point["timestamp"]))
            duration_hours = float(point["duration_hours"])
            timestamp_end = timestamp_start + timedelta(hours=duration_hours)
            periods.append(
                CatalogPeriod(
                    period_index=index,
                    timestamp_start=timestamp_start.isoformat(),
                    timestamp_end=timestamp_end.isoformat(),
                    duration_hours=duration_hours,
                )
            )
            values.append(
                CatalogValue(
                    period_index=index,
                    signal_key=signal_key,
                    value_numeric=float(point["value_m3s"]),
                    source_row_number=index + 2,
                    entity_key=entity_key,
                )
            )
        signals = [
            CatalogSignal(
                signal_key=signal_key,
                unit=definition.unit,
                source_column="value_m3s",
                source_unit=definition.unit,
                entity_type=base_entity_type,
                entity_key=entity_key,
            )
        ]
        prepared = PreparedTimeSeriesCatalogImport(
            set_name=name,
            version_label=resolved_version_label,
            data_kind=HYDRAULIC_GENERIC_SERIES_DATA_KIND,
            timezone="UTC",
            signals=signals,
            periods=periods,
            values=values,
            content_hash=content_hash,
            mapping_summary={
                "origin": "hydraulic_diagram",
                "entity_type": base_entity_type,
                "entity_id": base_entity_id,
            },
        )

        cursor = self.connection.execute(
            """
            INSERT INTO time_series_sets (
                project_id,
                name,
                version_number,
                version_label,
                data_kind,
                timezone,
                status,
                content_hash,
                created_at,
                updated_at,
                created_by,
                updated_by
            )
            VALUES (?, ?, ?, ?, ?, 'UTC', ?, ?, ?, ?, ?, ?)
            """,
            (
                project_id,
                name,
                version_number,
                resolved_version_label,
                HYDRAULIC_GENERIC_SERIES_DATA_KIND,
                status,
                content_hash,
                now,
                now,
                updated_by,
                updated_by,
            ),
        )
        time_series_set_id = int(cursor.lastrowid)
        resolved_revision_metadata = revision_metadata or {
            "origin": "hydraulic_diagram",
            "entity_type": base_entity_type,
            "entity_id": base_entity_id,
        }
        self.connection.execute(
            """
            INSERT INTO time_series_set_revisions (
                time_series_set_id,
                revision_number,
                time_series_source_id,
                superseded_revision_number,
                content_hash,
                change_summary,
                created_at,
                created_by,
                metadata_json
            )
            VALUES (?, 1, NULL, NULL, ?, ?, ?, ?, ?)
            """,
            (
                time_series_set_id,
                content_hash,
                change_summary,
                now,
                updated_by,
                json.dumps(resolved_revision_metadata, sort_keys=True),
            ),
        )
        self._insert_time_series_signals_periods_values(
            time_series_set_id=time_series_set_id,
            prepared_import=prepared,
            now=now,
        )
        return time_series_set_id

    def _load_generic_hydraulic_series_points(
        self, time_series_set_id: int
    ) -> list[dict[str, float]]:
        rows = self.connection.execute(
            """
            SELECT time_series_periods.timestamp_start AS timestamp,
                   time_series_periods.duration_hours AS duration_hours,
                   time_series_values.value_numeric AS value
            FROM time_series_values
            JOIN time_series_periods
              ON time_series_periods.id = time_series_values.time_series_period_id
            WHERE time_series_values.time_series_set_id = ?
            ORDER BY time_series_periods.period_index
            """,
            (time_series_set_id,),
        ).fetchall()
        return [
            {
                "timestamp": str(row["timestamp"]),
                "duration_hours": float(row["duration_hours"]),
                "value_m3s": float(row["value"]),
            }
            for row in rows
        ]

    def _load_bound_hydraulic_points(
        self,
        *,
        hydraulic_time_series_set_id: int | None,
        time_series_set_id: int | None,
    ) -> list[dict[str, float]]:
        if hydraulic_time_series_set_id is not None:
            return self._load_inflow_series_points(int(hydraulic_time_series_set_id))
        return self._load_generic_hydraulic_series_points(int(time_series_set_id))

    def _load_inflow_series_points(self, set_id: int) -> list[dict[str, float]]:
        rows = self.connection.execute(
            """
            SELECT timestamp, duration_hours, value
            FROM hydraulic_time_series_points
            WHERE hydraulic_time_series_set_id = ?
            ORDER BY point_index
            """,
            (set_id,),
        ).fetchall()
        return [
            {
                "timestamp": str(row["timestamp"]),
                "duration_hours": float(row["duration_hours"]),
                "value_m3s": float(row["value"]),
            }
            for row in rows
        ]

    def _entity_inflow_series_detail(
        self,
        *,
        project_id: int,
        base_entity_id: int,
        case_id: int,
        binding_entity_id: int,
        signal_key: str = NATURAL_INFLOW_SIGNAL_KEY,
        base_entity_type: str = "hydraulic_node",
        binding_entity_type: str = "case_hydraulic_node",
    ) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
        legacy_rows = self.connection.execute(
            """
            SELECT id, version_number, version_label
            FROM hydraulic_time_series_sets
            WHERE project_id = ?
              AND entity_type = ?
              AND entity_id = ?
              AND signal_key = ?
            ORDER BY version_number
            """,
            (project_id, base_entity_type, base_entity_id, signal_key),
        ).fetchall()
        generic_name = _generic_hydraulic_series_name(
            base_entity_type, base_entity_id, signal_key
        )
        generic_rows = self.connection.execute(
            """
            SELECT id, version_number, version_label
            FROM time_series_sets
            WHERE project_id = ? AND name = ?
            ORDER BY version_number
            """,
            (project_id, generic_name),
        ).fetchall()
        available = [
            {
                "time_series_set_id": int(row["id"]),
                "version_number": int(row["version_number"]),
                "version_label": str(row["version_label"]),
                "origin": {"kind": "hydraulic_legacy"},
                "points": self._load_inflow_series_points(int(row["id"])),
            }
            for row in legacy_rows
        ] + [
            {
                "time_series_set_id": int(row["id"]),
                "version_number": int(row["version_number"]),
                "version_label": str(row["version_label"]),
                "origin": {"kind": "generic"},
                "points": self._load_generic_hydraulic_series_points(int(row["id"])),
            }
            for row in generic_rows
        ]
        binding_row = self.connection.execute(
            """
            SELECT hydraulic_time_series_set_id, time_series_set_id
            FROM case_hydraulic_time_series_bindings
            WHERE case_id = ?
              AND entity_type = ?
              AND entity_id = ?
              AND signal_key = ?
            """,
            (case_id, binding_entity_type, binding_entity_id, signal_key),
        ).fetchone()
        bound = None
        if binding_row is not None:
            if binding_row["hydraulic_time_series_set_id"] is not None:
                bound_kind = "hydraulic_legacy"
                bound_id = int(binding_row["hydraulic_time_series_set_id"])
            else:
                bound_kind = "generic"
                bound_id = int(binding_row["time_series_set_id"])
            bound = next(
                (
                    item
                    for item in available
                    if item["origin"]["kind"] == bound_kind
                    and item["time_series_set_id"] == bound_id
                ),
                None,
            )
        return bound, available

    def _next_version_number(self, scenario_id: int) -> int:
        row = self.connection.execute(
            """
            SELECT COALESCE(MAX(version_number), 0) + 1 AS next_version_number
            FROM scenario_versions
            WHERE scenario_id = ?
            """,
            (scenario_id,),
        ).fetchone()
        return int(row["next_version_number"])

    def _ensure_source_version_belongs_to_scenario(
        self,
        scenario_id: int,
        source_version_id: int | None,
    ) -> None:
        if source_version_id is None:
            return

        source_version = self.get_scenario_version(source_version_id, include_document=False)
        if source_version["scenario_id"] != scenario_id:
            raise KeyError(f"scenario version {source_version_id} not found for scenario {scenario_id}")

    def _resolve_publication_artifact_types(
        self,
        run_id: int,
        requested_artifact_types: list[str] | None,
    ) -> list[str]:
        registered_types = {artifact["artifact_type"] for artifact in self.list_run_artifacts(run_id)}
        if requested_artifact_types is None:
            return [
                artifact_type
                for artifact_type in DEFAULT_PUBLICATION_ARTIFACT_TYPES
                if artifact_type in registered_types
            ]

        resolved: list[str] = []
        for artifact_type in requested_artifact_types:
            clean_type = str(artifact_type).strip()
            if not clean_type:
                continue
            if clean_type not in registered_types:
                raise ValueError(f"artifact type {clean_type} is not registered for run {run_id}")
            if clean_type not in resolved:
                resolved.append(clean_type)
        return resolved


def row_to_dict(row: Mapping[str, Any] | sqlite3.Row) -> dict[str, Any]:
    return {key: row[key] for key in row.keys()}


def external_access_row_to_dict(
    row: Mapping[str, Any] | sqlite3.Row,
) -> dict[str, Any]:
    value = row_to_dict(row)
    value["portal_view"] = bool(value["portal_view"])
    value["operate"] = bool(value["operate"])
    value["is_active"] = bool(value["is_active"])
    return value


def _parse_program_from_metadata_json(metadata_json: Any) -> dict[str, Any] | None:
    if not metadata_json:
        return None
    try:
        parsed = json.loads(str(metadata_json))
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    program = parsed.get("program")
    return program if isinstance(program, dict) else None


def user_row_to_dict(row: Mapping[str, Any] | sqlite3.Row) -> dict[str, Any]:
    value = row_to_dict(row)
    value["is_active"] = bool(value["is_active"])
    return value


def normalize_variant_key(display_name: str) -> str:
    characters: list[str] = []
    previous_was_separator = False
    for character in display_name.strip().lower():
        if character.isalnum():
            characters.append(character)
            previous_was_separator = False
            continue
        if not previous_was_separator:
            characters.append("_")
            previous_was_separator = True
    normalized = "".join(characters).strip("_")
    return normalized or "variant"


def case_input_variant_row_to_dict(row: Mapping[str, Any] | sqlite3.Row) -> dict[str, Any]:
    value = row_to_dict(row)
    value["is_default"] = bool(value["is_default"])
    return value


def portal_configuration_row_to_dict(row: Mapping[str, Any] | sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "project_id": row["project_id"],
        "status": row["status"],
        "document": json.loads(row["document_json"]),
        "revision": int(row["revision"]),
        "updated_at": row["updated_at"],
        "updated_by_user_id": row["updated_by_user_id"],
    }


def dashboard_template_row_to_dict(row: Mapping[str, Any] | sqlite3.Row) -> dict[str, Any]:
    value = row_to_dict(row)
    for field in DASHBOARD_TEMPLATE_FLAGS:
        value[field] = bool(value[field])
    return value


def publication_row_to_dict(row: Mapping[str, Any] | sqlite3.Row) -> dict[str, Any]:
    value = row_to_dict(row)
    value["allowed_artifact_types"] = json.loads(value.pop("allowed_artifact_types_json") or "[]")
    return value


def bool_to_int(value: bool) -> int:
    return 1 if bool(value) else 0


def validate_table_preview_limit(value: int) -> int:
    try:
        preview_limit = int(value)
    except (TypeError, ValueError) as error:
        raise ValueError("table preview limit must be a positive integer") from error
    if preview_limit < 1:
        raise ValueError("table preview limit must be a positive integer")
    return preview_limit


def normalize_hydraulic_viewport(viewport: Mapping[str, Any]) -> dict[str, float]:
    zoom = float(viewport.get("zoom", 1.0))
    if zoom <= 0:
        raise ValueError("hydraulic diagram zoom must be positive")
    return {
        "x": float(viewport.get("x", 0.0)),
        "y": float(viewport.get("y", 0.0)),
        "zoom": zoom,
    }


HYDRAULIC_AUTOLAYOUT_ORIGIN_X = 120.0
HYDRAULIC_AUTOLAYOUT_ORIGIN_Y = 80.0
HYDRAULIC_AUTOLAYOUT_COLUMN_SPACING = 180.0
HYDRAULIC_AUTOLAYOUT_ROW_SPACING = 140.0
HYDRAULIC_AUTOLAYOUT_COLUMNS = 4


def hydraulic_autolayout_position(index: int) -> tuple[float, float]:
    """Deterministic grid position for an entity that has no saved position."""
    column = index % HYDRAULIC_AUTOLAYOUT_COLUMNS
    row = index // HYDRAULIC_AUTOLAYOUT_COLUMNS
    return (
        HYDRAULIC_AUTOLAYOUT_ORIGIN_X + column * HYDRAULIC_AUTOLAYOUT_COLUMN_SPACING,
        HYDRAULIC_AUTOLAYOUT_ORIGIN_Y + row * HYDRAULIC_AUTOLAYOUT_ROW_SPACING,
    )


def hydraulic_weakly_connected_components(
    node_keys: list[str], edges: list[tuple[str, str]]
) -> list[set[str]]:
    """Group node keys into weakly-connected components (edge direction ignored).

    Components are returned in the first-seen order of ``node_keys`` so the
    result is deterministic for stable validation output.
    """

    parent: dict[str, str] = {key: key for key in node_keys}

    def find(key: str) -> str:
        root = key
        while parent[root] != root:
            root = parent[root]
        while parent[key] != root:
            parent[key], key = root, parent[key]
        return root

    for from_key, to_key in edges:
        if from_key in parent and to_key in parent:
            root_a, root_b = find(from_key), find(to_key)
            if root_a != root_b:
                parent[root_b] = root_a

    members: dict[str, set[str]] = {}
    for key in node_keys:
        members.setdefault(find(key), set()).add(key)

    ordered: list[set[str]] = []
    seen_roots: set[str] = set()
    for key in node_keys:
        root = find(key)
        if root not in seen_roots:
            seen_roots.add(root)
            ordered.append(members[root])
    return ordered


def hydraulic_first_cycle(
    node_keys: list[str], edges: list[tuple[str, str]]
) -> list[str]:
    """Return the node keys forming the first directed cycle, or ``[]`` if none.

    The MVP hydraulic solver only supports acyclic directed networks, so this
    powers the topology validation that rejects unsupported cycles.
    """

    adjacency: dict[str, list[str]] = {key: [] for key in node_keys}
    for from_key, to_key in edges:
        if from_key in adjacency and to_key in adjacency:
            adjacency[from_key].append(to_key)

    white, gray, black = 0, 1, 2
    color = {key: white for key in node_keys}
    stack: list[str] = []

    def visit(node: str) -> list[str]:
        color[node] = gray
        stack.append(node)
        for neighbor in adjacency[node]:
            if color[neighbor] == gray:
                return stack[stack.index(neighbor):]
            if color[neighbor] == white:
                found = visit(neighbor)
                if found:
                    return found
        stack.pop()
        color[node] = black
        return []

    for key in node_keys:
        if color[key] == white:
            found = visit(key)
            if found:
                return found
    return []


def normalize_hydraulic_diagram_nodes(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, str]] = set()
    for index, node in enumerate(nodes):
        component_type = str(node.get("component_type") or "").strip()
        if component_type not in HYDRAULIC_VISIBLE_COMPONENT_TYPES:
            raise ValueError(f"unsupported hydraulic component type: {component_type}")
        technical_key = str(node.get("technical_key") or "").strip()
        if not technical_key:
            raise ValueError("hydraulic component technical_key is required")
        identity = (component_type, technical_key)
        if identity in seen_keys:
            raise ValueError(f"duplicate hydraulic component key: {technical_key}")
        seen_keys.add(identity)
        display_name = str(node.get("display_name") or "").strip() or technical_key
        raw_x = node.get("x")
        raw_y = node.get("y")
        if raw_x is None or raw_y is None:
            auto_x, auto_y = hydraulic_autolayout_position(index)
            x = float(raw_x) if raw_x is not None else auto_x
            y = float(raw_y) if raw_y is not None else auto_y
        else:
            x = float(raw_x)
            y = float(raw_y)
        normalized_node = {
            "component_type": component_type,
            "technical_key": technical_key,
            "display_name": display_name,
            "x": x,
            "y": y,
            "reservoir": None,
            "storage_elevation_curve": None,
            "natural_inflow_series": None,
        }
        if component_type != "plant" and node.get("natural_inflow_series") is not None:
            normalized_node["natural_inflow_series"] = (
                normalize_hydraulic_natural_inflow_series(node["natural_inflow_series"])
            )
        if component_type == "reservoir":
            if node.get("reservoir") is not None:
                normalized_node["reservoir"] = normalize_hydraulic_reservoir_parameters(
                    node["reservoir"]
                )
            if node.get("storage_elevation_curve") is not None:
                normalized_node["storage_elevation_curve"] = (
                    normalize_hydraulic_storage_elevation_curve(
                        node["storage_elevation_curve"]
                    )
                )
        if component_type == "plant":
            normalized_node["plant"] = normalize_hydraulic_plant_parameters(
                node.get("plant") or {}
            )
            normalized_node["units"] = normalize_hydraulic_units(node.get("units") or [])
            normalized_node["link_anchors"] = normalize_hydraulic_link_anchors(
                node.get("link_anchors")
            )
        normalized.append(normalized_node)
    return normalized


def _optional_float(value: Any) -> float | None:
    return None if value is None else float(value)


def _optional_anchor(value: Any) -> float | None:
    if value is None:
        return None
    anchor = float(value)
    if not 0.0 <= anchor <= 1.0:
        raise ValueError("hydraulic anchor must be between 0 and 1")
    return anchor


def normalize_hydraulic_link_anchors(raw: Any) -> dict[str, dict[str, float | None]]:
    anchors: dict[str, dict[str, float | None]] = {}
    if not isinstance(raw, Mapping):
        return anchors
    for key, value in raw.items():
        if not isinstance(value, Mapping):
            continue
        entry = {
            "from": _optional_anchor(value.get("from")),
            "to": _optional_anchor(value.get("to")),
        }
        if entry["from"] is None and entry["to"] is None:
            continue
        anchors[str(key)] = entry
    return anchors


def normalize_hydraulic_plant_parameters(plant: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "non_modeled": bool(plant.get("non_modeled", False)),
        "min_power_mw": _optional_float(plant.get("min_power_mw")),
        "max_power_mw": _optional_float(plant.get("max_power_mw")),
    }


def normalize_hydraulic_units(units: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    seen_keys: set[str] = set()
    for unit in units:
        technical_key = str(unit.get("technical_key") or "").strip()
        if not technical_key:
            raise ValueError("hydraulic unit technical_key is required")
        if technical_key in seen_keys:
            raise ValueError(f"duplicate hydraulic unit key: {technical_key}")
        seen_keys.add(technical_key)
        intake_node_key = str(unit.get("intake_node_key") or "").strip() or None
        discharge_node_key = str(unit.get("discharge_node_key") or "").strip() or None
        curve = unit.get("flow_power_curve")
        operation_mode = str(unit.get("operation_mode") or "generation").strip() or "generation"
        if operation_mode not in HYDRAULIC_UNIT_OPERATION_MODES:
            raise ValueError(f"unsupported hydraulic unit operation mode: {operation_mode}")
        generation_mode = (
            str(unit.get("generation_mode") or "flow_power_curve").strip()
            or "flow_power_curve"
        )
        if generation_mode not in HYDRAULIC_UNIT_GENERATION_MODES:
            raise ValueError(
                f"unsupported hydraulic unit generation mode: {generation_mode}"
            )
        normalized.append(
            {
                "technical_key": technical_key,
                "display_name": str(unit.get("display_name") or "").strip()
                or technical_key,
                "is_active": bool(unit.get("is_active", True)),
                "operation_mode": operation_mode,
                "generation_mode": generation_mode,
                "intake_node_key": intake_node_key,
                "discharge_node_key": discharge_node_key,
                "min_power_mw": _optional_float(unit.get("min_power_mw")),
                "max_power_mw": _optional_float(unit.get("max_power_mw")),
                "min_flow_m3s": _optional_float(unit.get("min_flow_m3s")),
                "max_flow_m3s": _optional_float(unit.get("max_flow_m3s")),
                "flow_power_curve": (
                    None if curve is None else normalize_hydraulic_curve_points(curve)
                ),
            }
        )
    return normalized


def normalize_hydraulic_reservoir_parameters(reservoir: Mapping[str, Any]) -> dict[str, Any]:
    terminal_condition = str(reservoir.get("terminal_condition") or "none").strip()
    if terminal_condition not in HYDRAULIC_TERMINAL_CONDITIONS:
        raise ValueError(f"unsupported reservoir terminal condition: {terminal_condition}")
    terminal_storage_min = reservoir.get("terminal_storage_min_hm3")
    return {
        "storage_min_hm3": float(reservoir.get("storage_min_hm3", 0.0)),
        "storage_max_hm3": float(reservoir.get("storage_max_hm3", 0.0)),
        "initial_storage_hm3": float(reservoir.get("initial_storage_hm3", 0.0)),
        "terminal_condition": terminal_condition,
        "terminal_storage_min_hm3": (
            None if terminal_storage_min is None else float(terminal_storage_min)
        ),
        "terminal_water_value_usd_per_hm3": float(
            reservoir.get("terminal_water_value_usd_per_hm3", 0.0)
        ),
    }


def normalize_hydraulic_curve_points(curve: Mapping[str, Any]) -> dict[str, Any]:
    curve_set_id = curve.get("curve_set_id")
    points = [
        {"x_value": float(point.get("x_value", 0.0)), "y_value": float(point.get("y_value", 0.0))}
        for point in curve.get("points", [])
    ]
    return {
        "curve_set_id": None if curve_set_id is None else int(curve_set_id),
        "version_label": (
            str(curve["version_label"]).strip()
            if curve.get("version_label") not in (None, "")
            else None
        ),
        "points": points,
    }


def normalize_hydraulic_storage_elevation_curve(curve: Mapping[str, Any]) -> dict[str, Any]:
    return normalize_hydraulic_curve_points(curve)


def hydraulic_curve_content_hash(points: list[dict[str, Any]]) -> str:
    serialized = json.dumps(
        [[round(point["x_value"], 9), round(point["y_value"], 9)] for point in points],
        sort_keys=True,
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def normalize_hydraulic_natural_inflow_series(series: Mapping[str, Any]) -> dict[str, Any]:
    set_id = series.get("time_series_set_id")
    origin = series.get("origin")
    origin_kind = origin.get("kind") if isinstance(origin, Mapping) else None
    points = [
        {
            "timestamp": str(point.get("timestamp") or "").strip(),
            "duration_hours": float(point.get("duration_hours", 1.0)),
            "value_m3s": float(point.get("value_m3s", 0.0)),
        }
        for point in series.get("points", [])
    ]
    return {
        "time_series_set_id": None if set_id is None else int(set_id),
        "origin_kind": origin_kind if origin_kind == "generic" else None,
        "version_label": (
            str(series["version_label"]).strip()
            if series.get("version_label") not in (None, "")
            else None
        ),
        "points": points,
    }


def _generic_hydraulic_series_name(
    base_entity_type: str, base_entity_id: int, signal_key: str
) -> str:
    """Stable catalog name chaining a hydraulic entity+signal's generic sets.

    Keyed on the entity's numeric id (not its technical/display name, which
    can be renamed) so repeated saves keep landing on the same
    ``time_series_sets`` version chain.
    """
    return f"hydro_{base_entity_type}_{base_entity_id}_{signal_key}"


def hydraulic_inflow_series_content_hash(points: list[dict[str, Any]]) -> str:
    serialized = json.dumps(
        [
            [
                point["timestamp"],
                round(point["duration_hours"], 9),
                round(point["value_m3s"], 9),
            ]
            for point in points
        ],
        sort_keys=True,
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def hydraulic_v3_time_series_from_inflows(
    required_time_series: list[dict[str, Any]],
    inflow_series_by_key: Mapping[str, list[dict[str, float]]],
) -> list[dict[str, Any]]:
    """Resolve bound inflow series into the v3 ``time_series`` period blocks.

    The horizon is taken from the first required entity that has a bound series.
    When no entity is bound, a single zero period keeps the payload generatable
    for incomplete diagrams; validation is responsible for blocking promotion.
    """

    required_ids = [requirement["entity_id"] for requirement in required_time_series]
    reference_points: list[dict[str, float]] | None = None
    for entity_id in required_ids:
        points = inflow_series_by_key.get(entity_id)
        if points:
            reference_points = points
            break
    if reference_points is None:
        return [
            {
                "timestamp": "2026-01-01T00:00:00",
                "duration_hours": 1.0,
                "natural_inflow_m3s": {entity_id: 0.0 for entity_id in required_ids},
            }
        ]
    periods: list[dict[str, Any]] = []
    for index, reference in enumerate(reference_points):
        inflows: dict[str, float] = {}
        for entity_id in required_ids:
            points = inflow_series_by_key.get(entity_id, [])
            inflows[entity_id] = (
                float(points[index]["value_m3s"]) if index < len(points) else 0.0
            )
        periods.append(
            {
                "timestamp": reference["timestamp"],
                "duration_hours": float(reference["duration_hours"]),
                "natural_inflow_m3s": inflows,
            }
        )
    return periods


def hydraulic_v3_apply_minimum_flow_series(
    time_series: list[dict[str, Any]],
    minimum_flow_series_by_key: Mapping[str, list[dict[str, float]]],
) -> None:
    """Inject series-backed reach minimum flow into the v3 ``time_series`` block.

    Each period gains a ``minimum_flow_m3s`` map keyed by reach id. Reaches with a
    scalar (or no) minimum flow are absent from the map and are handled by the
    per-reach ``flow_min_m3s`` attribute instead.
    """

    if not minimum_flow_series_by_key:
        return
    for index, period in enumerate(time_series):
        period["minimum_flow_m3s"] = {
            reach_id: (
                float(points[index]["value_m3s"]) if index < len(points) else 0.0
            )
            for reach_id, points in minimum_flow_series_by_key.items()
        }


def hydraulic_natural_inflow_series_points(
    series: Mapping[str, Any] | None,
) -> list[dict[str, float]]:
    if not isinstance(series, Mapping):
        return []
    return [
        {
            "timestamp": str(point["timestamp"]),
            "duration_hours": float(point["duration_hours"]),
            "value_m3s": float(point["value_m3s"]),
        }
        for point in series.get("points", [])
    ]


def normalize_hydraulic_diagram_reaches(reaches: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    seen_keys: set[str] = set()
    for reach in reaches:
        technical_key = str(reach.get("technical_key") or "").strip()
        if not technical_key:
            raise ValueError("hydraulic reach technical_key is required")
        if technical_key in seen_keys:
            raise ValueError(f"duplicate hydraulic reach key: {technical_key}")
        seen_keys.add(technical_key)
        from_node_key = str(reach.get("from_node_key") or "").strip()
        to_node_key = str(reach.get("to_node_key") or "").strip()
        if not from_node_key or not to_node_key:
            raise ValueError("hydraulic reach endpoints are required")
        reach_type = str(reach.get("reach_type") or "").strip()
        if reach_type not in HYDRAULIC_REACH_TYPES:
            raise ValueError(f"unsupported hydraulic reach type: {reach_type}")
        routing_method = str(reach.get("routing_method") or "none").strip() or "none"
        if routing_method not in HYDRAULIC_ROUTING_METHODS:
            raise ValueError(f"unsupported hydraulic routing method: {routing_method}")
        travel_time_hours = float(reach.get("travel_time_hours") or 0.0)
        if travel_time_hours < 0:
            raise ValueError("hydraulic reach travel_time_hours must be nonnegative")
        minimum_flow_series = None
        if reach.get("minimum_flow_series") is not None:
            minimum_flow_series = normalize_hydraulic_natural_inflow_series(
                reach["minimum_flow_series"]
            )
        normalized.append(
            {
                "technical_key": technical_key,
                "display_name": str(reach.get("display_name") or "").strip() or technical_key,
                "from_node_key": from_node_key,
                "to_node_key": to_node_key,
                "reach_type": reach_type,
                "routing_method": routing_method,
                "travel_time_hours": travel_time_hours,
                "flow_min_m3s": _optional_float(reach.get("flow_min_m3s")),
                "spill_penalty_usd_per_hm3": _optional_float(
                    reach.get("spill_penalty_usd_per_hm3")
                ),
                "minimum_flow_series": minimum_flow_series,
                "from_anchor": _optional_anchor(reach.get("from_anchor")),
                "to_anchor": _optional_anchor(reach.get("to_anchor")),
            }
        )
    return normalized


def optimization_case_public_dict(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "scenario_id": row["scenario_id"],
        "case_key": row["case_key"],
        "display_name": row["display_name"],
        "updated_at": row["updated_at"],
    }


def hydraulic_validation_public_dict(raw_payload: Any) -> dict[str, Any]:
    if isinstance(raw_payload, Mapping):
        payload = dict(raw_payload)
    else:
        try:
            payload = json.loads(str(raw_payload or "{}"))
        except json.JSONDecodeError:
            payload = {}
    if not isinstance(payload, dict) or not payload:
        return {
            "kind": "hydraulic_validation",
            "ok": False,
            "stale": True,
            "status": "not_validated",
            "summary": "Hydraulic diagram has not been validated",
            "errors": [],
            "warnings": [],
        }
    payload.setdefault("stale", False)
    payload.setdefault("errors", [])
    payload.setdefault("warnings", [])
    payload.setdefault("summary", "Hydraulic validation available")
    return payload


def hydraulic_payload_hash(payload: Mapping[str, Any]) -> str:
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def hydraulic_storage_elevation_curve_points(curve: Mapping[str, Any] | None) -> list[dict[str, float]]:
    if not isinstance(curve, Mapping):
        return []
    return [
        {
            "storage_hm3": float(point["x_value"]),
            "elevation_masl": float(point["y_value"]),
        }
        for point in curve.get("points", [])
    ]


def hydraulic_flow_power_curve_points(curve: Mapping[str, Any] | None) -> list[dict[str, float]]:
    if not isinstance(curve, Mapping):
        return []
    return [
        {
            "flow_m3s": float(point["x_value"]),
            "power_mw": float(point["y_value"]),
        }
        for point in curve.get("points", [])
    ]


def hydraulic_system_public_dict(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "project_id": row["project_id"],
        "system_key": row["system_key"],
        "display_name": row["display_name"],
    }


def hydraulic_layout_public_dict(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "case_id": row["case_id"],
        "layout_key": row["layout_key"],
        "layout_engine": row["layout_engine"],
        "layout_version": row["layout_version"],
        "revision": str(row["layout_version"]),
        "viewport": {
            "x": float(row["viewport_x"]),
            "y": float(row["viewport_y"]),
            "zoom": float(row["zoom"]),
        },
        "updated_at": row["updated_at"],
        "updated_by": row["updated_by"],
    }


def _hydraulic_item_metadata(value: Mapping[str, Any]) -> dict[str, Any]:
    try:
        metadata = json.loads(str(value.get("metadata_json") or "{}"))
    except json.JSONDecodeError:
        metadata = {}
    return metadata if isinstance(metadata, dict) else {}


def hydraulic_diagram_node_row_to_dict(row: Mapping[str, Any] | sqlite3.Row) -> dict[str, Any]:
    value = row_to_dict(row)
    node = {
        "layout_item_id": value["layout_item_id"],
        "entity_type": value["entity_type"],
        "entity_id": value["entity_id"],
        "component_type": value["component_type"],
        "technical_key": value["technical_key"],
        "display_name": value["display_name"],
        "x": float(value["x"]),
        "y": float(value["y"]),
        "z_index": int(value["z_index"]),
    }
    if value["component_type"] == "plant":
        metadata = _hydraulic_item_metadata(value)
        anchors = metadata.get("link_anchors")
        node["link_anchors"] = anchors if isinstance(anchors, dict) else {}
    return node


def hydraulic_diagram_reach_row_to_dict(row: Mapping[str, Any] | sqlite3.Row) -> dict[str, Any]:
    value = row_to_dict(row)
    metadata = _hydraulic_item_metadata(value)
    return {
        "layout_item_id": value["layout_item_id"],
        "entity_type": "case_hydraulic_reach",
        "entity_id": value["entity_id"],
        "technical_key": value["technical_key"],
        "display_name": value["display_name"],
        "from_node_key": value["from_node_key"],
        "to_node_key": value["to_node_key"],
        "reach_type": value["reach_type"],
        "routing_method": str(value.get("routing_method") or "none"),
        "travel_time_hours": float(value.get("travel_time_hours") or 0.0),
        "flow_min_m3s": _optional_float(value.get("flow_min_m3s")),
        "spill_penalty_usd_per_hm3": _optional_float(
            value.get("spill_penalty_usd_per_hm3")
        ),
        "minimum_flow_series": None,
        "available_minimum_flow_series": [],
        "from_anchor": _optional_float(metadata.get("from_anchor")),
        "to_anchor": _optional_float(metadata.get("to_anchor")),
        "z_index": int(value["z_index"] or 0),
    }


def _content_hash(value: Any) -> str:
    canonical = json.dumps(value, sort_keys=True, default=str)
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def derive_case_hierarchy_views(document: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Split a ``system_case_json`` document into topology and parameter views.

    Topology is component membership and connectivity: which nodes exist, what
    type each node is, and how they are connected. Parameters are the
    executable assumptions layered on that structure: scalar limits, initial
    states, costs, curves, time series and solver settings. The split is
    shape-driven on purpose: a flat ``nodes``/``edges`` document is treated as
    the one-bus case shape, a ``hydraulic_network`` document is treated as the
    hydraulic-diagram (v3) case shape with its own node/reach/plant/unit
    membership and connectivity, and anything else falls back to a
    schema-version-only topology so it still stays valid without a per-schema
    migration.

    This is the read side of the hierarchy generation boundary; see
    ``generate_system_case_from_hierarchy`` for the inverse.
    """
    nodes = document.get("nodes")
    hydraulic_network = document.get("hydraulic_network")
    if isinstance(nodes, list) and all(isinstance(node, dict) for node in nodes):
        topology_view = {
            "schema_version": document.get("schema_version"),
            "nodes": sorted(
                (
                    {"id": node.get("id"), "type": node.get("type")}
                    for node in nodes
                ),
                key=lambda node: (str(node["id"]), str(node["type"])),
            ),
            "edges": sorted(
                (
                    {"from": edge.get("from"), "to": edge.get("to")}
                    for edge in document.get("edges", [])
                    if isinstance(edge, dict)
                ),
                key=lambda edge: (str(edge["from"]), str(edge["to"])),
            ),
        }
        parameters_view = {
            key: value for key, value in document.items() if key not in {"nodes", "edges", "schema_version"}
        }
        parameters_view["node_parameters"] = {
            str(node.get("id")): {k: v for k, v in node.items() if k not in {"id", "type"}}
            for node in nodes
        }
    elif isinstance(hydraulic_network, dict):
        network_nodes = [n for n in hydraulic_network.get("nodes", []) if isinstance(n, dict)]
        reaches = [r for r in hydraulic_network.get("reaches", []) if isinstance(r, dict)]
        plants = [p for p in hydraulic_network.get("plants", []) if isinstance(p, dict)]
        units = [u for u in hydraulic_network.get("units", []) if isinstance(u, dict)]

        topology_view = {
            "schema_version": document.get("schema_version"),
            "nodes": sorted(
                (
                    {"id": node.get("id"), "type": node.get("type")}
                    for node in network_nodes
                ),
                key=lambda node: str(node["id"]),
            ),
            "reaches": sorted(
                (
                    {
                        "id": reach.get("id"),
                        "from_node": reach.get("from_node"),
                        "to_node": reach.get("to_node"),
                        "type": reach.get("type"),
                    }
                    for reach in reaches
                ),
                key=lambda reach: str(reach["id"]),
            ),
            "plants": sorted(
                (
                    {"id": plant.get("id"), "units": sorted(str(unit) for unit in plant.get("units", []))}
                    for plant in plants
                ),
                key=lambda plant: str(plant["id"]),
            ),
            "units": sorted(
                (
                    {
                        "id": unit.get("id"),
                        "plant_id": unit.get("plant_id"),
                        "intake_node": unit.get("intake_node"),
                        "discharge_node": unit.get("discharge_node"),
                    }
                    for unit in units
                ),
                key=lambda unit: str(unit["id"]),
            ),
        }
        parameters_view = {
            key: value for key, value in document.items() if key not in {"hydraulic_network", "schema_version"}
        }
        parameters_view["hydraulic_network_parameters"] = {
            "nodes": {
                str(node.get("id")): {k: v for k, v in node.items() if k not in {"id", "type"}}
                for node in network_nodes
            },
            "reaches": {
                str(reach.get("id")): {
                    k: v for k, v in reach.items() if k not in {"id", "from_node", "to_node", "type"}
                }
                for reach in reaches
            },
            "plants": {
                str(plant.get("id")): {k: v for k, v in plant.items() if k not in {"id", "units"}}
                for plant in plants
            },
            "units": {
                str(unit.get("id")): {
                    k: v
                    for k, v in unit.items()
                    if k not in {"id", "plant_id", "intake_node", "discharge_node"}
                }
                for unit in units
            },
            "curves": hydraulic_network.get("curves", []),
            "required_time_series": hydraulic_network.get("required_time_series", []),
        }
    else:
        topology_view = {"schema_version": document.get("schema_version")}
        parameters_view = {key: value for key, value in document.items() if key != "schema_version"}

    return {"topology": topology_view, "parameters": parameters_view}


def derive_case_hierarchy_provenance(document: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Hash the topology/parameter views from ``derive_case_hierarchy_views``."""
    views = derive_case_hierarchy_views(document)
    return {
        "topology": {"content_hash": _content_hash(views["topology"])},
        "parameters": {"content_hash": _content_hash(views["parameters"])},
    }


def hierarchy_stale_state(
    previous_system_case: dict[str, Any], current_system_case: dict[str, Any]
) -> dict[str, bool] | None:
    """Identify whether topology and/or parameters drifted between two cases.

    Compares the topology/parameter provenance hashes of a previously
    validated ``system_case_json`` against a freshly generated one. Returns
    ``None`` when both hashes still match (validation is still current), or a
    dict with ``topology_stale``/``parameters_stale`` booleans otherwise.
    """
    previous_provenance = derive_case_hierarchy_provenance(previous_system_case)
    current_provenance = derive_case_hierarchy_provenance(current_system_case)
    topology_stale = (
        previous_provenance["topology"]["content_hash"] != current_provenance["topology"]["content_hash"]
    )
    parameters_stale = (
        previous_provenance["parameters"]["content_hash"] != current_provenance["parameters"]["content_hash"]
    )
    if not topology_stale and not parameters_stale:
        return None
    return {"topology_stale": topology_stale, "parameters_stale": parameters_stale}


def hierarchy_stale_summary(label: str, stale_state: Mapping[str, bool]) -> str:
    """Human-readable summary naming which hierarchy part(s) went stale."""
    if stale_state["topology_stale"] and stale_state["parameters_stale"]:
        changed = "topology and parameters"
    elif stale_state["topology_stale"]:
        changed = "topology"
    else:
        changed = "parameters"
    return f"{label} is stale after {changed} edits"


def generate_system_case_from_hierarchy(
    topology: dict[str, Any], parameters: dict[str, Any]
) -> dict[str, Any]:
    """Reassemble an executable ``system_case_json`` from its topology/parameter views.

    This is the shared generation boundary: the inverse of
    ``derive_case_hierarchy_views``. It dispatches on the same shape signals
    (flat ``edges`` for one-bus, ``reaches`` for hydraulic v3, otherwise the
    schema-version-only fallback) so a case built from its own topology and
    parameter views regenerates a document whose hierarchy views are
    identical to the inputs.
    """
    if "edges" in topology:
        node_parameters = parameters.get("node_parameters", {})
        document = {key: value for key, value in parameters.items() if key != "node_parameters"}
        document["schema_version"] = topology.get("schema_version")
        document["nodes"] = [
            {
                "id": node.get("id"),
                "type": node.get("type"),
                **node_parameters.get(str(node.get("id")), {}),
            }
            for node in topology.get("nodes", [])
        ]
        document["edges"] = [dict(edge) for edge in topology.get("edges", [])]
        return document

    if "reaches" in topology:
        network_parameters = parameters.get("hydraulic_network_parameters", {})
        node_parameters = network_parameters.get("nodes", {})
        reach_parameters = network_parameters.get("reaches", {})
        plant_parameters = network_parameters.get("plants", {})
        unit_parameters = network_parameters.get("units", {})

        document = {
            key: value for key, value in parameters.items() if key != "hydraulic_network_parameters"
        }
        document["schema_version"] = topology.get("schema_version")
        document["hydraulic_network"] = {
            "nodes": [
                {
                    "id": node.get("id"),
                    "type": node.get("type"),
                    **node_parameters.get(str(node.get("id")), {}),
                }
                for node in topology.get("nodes", [])
            ],
            "reaches": [
                {
                    "id": reach.get("id"),
                    "from_node": reach.get("from_node"),
                    "to_node": reach.get("to_node"),
                    "type": reach.get("type"),
                    **reach_parameters.get(str(reach.get("id")), {}),
                }
                for reach in topology.get("reaches", [])
            ],
            "plants": [
                {
                    "id": plant.get("id"),
                    **plant_parameters.get(str(plant.get("id")), {}),
                    "units": list(plant.get("units", [])),
                }
                for plant in topology.get("plants", [])
            ],
            "units": [
                {
                    "id": unit.get("id"),
                    "plant_id": unit.get("plant_id"),
                    "intake_node": unit.get("intake_node"),
                    "discharge_node": unit.get("discharge_node"),
                    **unit_parameters.get(str(unit.get("id")), {}),
                }
                for unit in topology.get("units", [])
            ],
            "curves": network_parameters.get("curves", []),
            "required_time_series": network_parameters.get("required_time_series", []),
        }
        return document

    document = dict(parameters)
    document["schema_version"] = topology.get("schema_version")
    return document


def extract_system_case_metadata(document: dict[str, Any]) -> dict[str, Any]:
    asset_counts = {"battery": 0, "grid": 0, "load": 0, "renewable": 0}
    for node in document.get("nodes", []):
        node_type = node.get("type") if isinstance(node, dict) else None
        if node_type in asset_counts:
            asset_counts[node_type] += 1

    return {
        "case_name": str(document.get("case_name") or "system_case"),
        "schema_version": str(document.get("schema_version") or ""),
        "period_count": len(document.get("time_series", [])),
        "asset_counts": asset_counts,
    }


def build_hydraulic_diagram_layout_snapshot(
    diagram: Mapping[str, Any],
) -> dict[str, Any]:
    """Build a lightweight, non-executable visual snapshot of a diagram.

    The snapshot captures only the visual arrangement (positions, viewport,
    visible labels and connectivity) and deliberately omits hydraulic physics
    such as reservoir parameters, curves and time series. The executable
    contract remains ``scenario_versions.system_case_json``.
    """
    layout = diagram.get("layout") or {}
    nodes = [
        {
            "entity_type": node["entity_type"],
            "entity_id": node["entity_id"],
            "component_type": node["component_type"],
            "technical_key": node["technical_key"],
            "display_name": node["display_name"],
            "x": float(node["x"]),
            "y": float(node["y"]),
            "z_index": int(node.get("z_index", 0)),
        }
        for node in diagram.get("nodes", [])
    ]
    reaches = [
        {
            "entity_type": "case_hydraulic_reach",
            "entity_id": reach["entity_id"],
            "technical_key": reach["technical_key"],
            "display_name": reach["display_name"],
            "from_node_key": reach["from_node_key"],
            "to_node_key": reach["to_node_key"],
            "reach_type": reach["reach_type"],
            "z_index": int(reach.get("z_index", 0)),
        }
        for reach in diagram.get("reaches", [])
    ]
    return {
        "layout_key": layout.get("layout_key", "default"),
        "layout_engine": layout.get("layout_engine"),
        "viewport": layout.get("viewport") or {"x": 0.0, "y": 0.0, "zoom": 1.0},
        "nodes": nodes,
        "reaches": reaches,
    }


def scenario_version_hydraulic_diagram_snapshot_row_to_dict(
    row: Mapping[str, Any] | sqlite3.Row,
) -> dict[str, Any]:
    value = row_to_dict(row)
    value["layout_snapshot"] = json.loads(value.pop("layout_snapshot_json"))
    return value


def result_lineage_from_scenario_version(
    *, run_id: int, scenario_version: Mapping[str, Any]
) -> dict[str, Any]:
    generation_metadata = scenario_version.get("generation_metadata") or {}
    topology = generation_metadata.get("topology") if isinstance(generation_metadata, Mapping) else {}
    parameters = generation_metadata.get("parameters") if isinstance(generation_metadata, Mapping) else {}
    input_variant = generation_metadata.get("input_variant") if isinstance(generation_metadata, Mapping) else None
    date_range = generation_metadata.get("date_range") if isinstance(generation_metadata, Mapping) else None
    raw_bindings = generation_metadata.get("series_bindings") if isinstance(generation_metadata, Mapping) else []
    input_series: list[dict[str, Any]] = []
    for binding in raw_bindings or []:
        if not isinstance(binding, Mapping):
            continue
        input_series.append(
            {
                "signal_key": normalize_optional_text(binding.get("signal_key")),
                "entity_type": normalize_optional_text(binding.get("entity_type")),
                "entity_id": normalize_optional_text(binding.get("entity_id")),
                "time_series_set_id": binding.get("time_series_set_id"),
                "version_number": binding.get("version_number"),
                "version_label": normalize_optional_text(binding.get("version_label")),
                "revision_number": binding.get("revision_number"),
                "content_hash": normalize_optional_text(binding.get("content_hash")),
            }
        )
    input_series.sort(
        key=lambda binding: (
            str(binding.get("signal_key") or ""),
            str(binding.get("entity_type") or ""),
            str(binding.get("entity_id") or ""),
            str(binding.get("time_series_set_id") or ""),
        )
    )
    return {
        "run_id": int(run_id),
        "scenario_version_id": int(scenario_version["id"]),
        "case": {
            "scenario_id": int(scenario_version["scenario_id"]),
            "case_name": str(scenario_version.get("case_name") or ""),
        },
        "topology_hash": normalize_optional_text(
            topology.get("content_hash") if isinstance(topology, Mapping) else None
        ),
        "parameters_hash": normalize_optional_text(
            parameters.get("content_hash") if isinstance(parameters, Mapping) else None
        ),
        "input_variant": dict(input_variant) if isinstance(input_variant, Mapping) else None,
        "date_range": dict(date_range) if isinstance(date_range, Mapping) else None,
        "input_series": input_series,
    }


def scenario_version_row_to_dict(
    row: Mapping[str, Any] | sqlite3.Row,
    *,
    include_document: bool,
) -> dict[str, Any]:
    value = row_to_dict(row)
    value["asset_counts"] = json.loads(value.pop("asset_counts_json"))
    value["generation_metadata"] = json.loads(value.pop("generation_metadata_json") or "{}")
    if include_document:
        value["system_case_json"] = json.loads(value.pop("system_case_json"))
        value["validation_payload"] = json.loads(value.pop("validation_payload_json"))
    return value


def scenario_draft_row_to_dict(row: Mapping[str, Any] | sqlite3.Row) -> dict[str, Any]:
    value = row_to_dict(row)
    value["document"] = json.loads(value.pop("document_json"))
    return value


def run_row_to_dict(row: Mapping[str, Any] | sqlite3.Row) -> dict[str, Any]:
    value = row_to_dict(row)
    value["success_payload"] = json.loads(value.pop("success_payload_json") or "{}")
    value["error_payload"] = json.loads(value.pop("error_payload_json") or "{}")
    return value


def run_schedule_row_to_dict(row: Mapping[str, Any] | sqlite3.Row) -> dict[str, Any]:
    value = row_to_dict(row)
    value["is_active"] = bool(value["is_active"])
    return value


def run_schedule_tick_row_to_dict(row: Mapping[str, Any] | sqlite3.Row) -> dict[str, Any]:
    value = row_to_dict(row)
    value["error_payload"] = json.loads(value.pop("error_payload_json") or "{}")
    return value
