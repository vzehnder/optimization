from __future__ import annotations

import copy
import json
import os
import secrets
from contextlib import asynccontextmanager
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any, Literal
from urllib.parse import quote

from fastapi import (
    FastAPI,
    File,
    Form,
    Header,
    HTTPException,
    Request,
    Response,
    UploadFile,
)
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from plotly.offline import get_plotlyjs
from pydantic import BaseModel, ConfigDict, Field

from app.auth import (
    AuthorizationService,
    INTERNAL_USER_ROLES,
    VALID_USER_ROLES,
    hash_password,
    hash_session_token,
    new_session_token,
    session_expires_at,
    verify_password,
)
from app.draft_editor import (
    DraftGenerationError,
    generate_system_case_from_draft,
    structured_draft_document_from_system_case,
)
from app.forecast_connector import (
    ForecastConnector,
    ForecastConnectorError,
    HttpJsonForecastConnector,
    HttpJsonForecastConnectorConfig,
)
from app.input_variants import InputVariantRangeError
from app.legacy_series_extraction import LegacyDraftExtractionError
from app.required_signals import MissingRequiredSignalsError
from app.variant_staleness import VariantStaleError
from app.persistence import (
    AnalystStore,
    CanonicalRunValidationError,
    DEFAULT_PUBLICATION_ARTIFACT_TYPES,
    build_hydraulic_diagram_layout_snapshot,
    derive_case_hierarchy_provenance,
    hierarchy_stale_state,
    hierarchy_stale_summary,
    optimization_case_public_dict,
    utc_now_iso,
)
from app.result_comparison import ComparisonError, compare_runs
from app.result_indexing import rebuild_all_run_results, rebuild_run_results
from app.result_retention import cleanup_project_result_data, cleanup_run_result_data
from app.results import ResultReadError, apply_dashboard_template, read_run_results
from app.console_series import ConsoleSeriesError
from app.operator_console import (
    OperatorConsoleConfigurationError,
    build_console_run_gate,
    validate_operator_console_config_document,
    validate_operator_console_status,
)
from app.portal_configuration import (
    portal_catalogs,
    PortalConfigurationError,
    default_portal_config_document,
    validate_portal_config_document,
    validate_portal_configuration_status,
)
from app.surface_payloads import (
    build_console_group_values,
    build_console_lease,
    build_console_list_entry,
    build_console_payload,
    build_console_run_comparison,
    build_console_run_entry,
    build_console_save_error,
    build_console_series_options,
    build_results_block,
    build_portal_branding,
    build_portal_publication_payload,
)
from app.schedules import (
    ScheduleError,
    due_fixed_range_schedules,
    execute_fixed_range_schedule,
)
from app.time_series_catalog import (
    CatalogImportRequest as PreparedCatalogImportRequest,
    CatalogSignalMappingRequest as PreparedCatalogSignalMappingRequest,
    CatalogValueEdit,
    TimeSeriesCatalogError,
    prepare_time_series_catalog_import,
)
from app.time_series_catalog_projection import CatalogQueryError
from app.time_series_catalog_read import (
    catalog_detail_etag,
    catalog_error_payload,
    catalog_preview_etag,
    input_list_item,
    parse_input_filters,
    parse_legacy_preview_query,
    parse_object_context_filters,
    parse_preview_query,
    parse_result_filters,
)
from app.time_series_associations import (
    AssociationMutationError,
    association_detail_etag,
    association_error_payload,
)
from app.time_series_bindings import (
    BindingMutationError,
    binding_detail_etag,
    binding_error_payload,
)
from app.object_time_series import (
    ObjectSeriesError,
    object_series_etag,
    object_series_problem,
    parse_object_series_file_upload,
)
from app.transformations import TransformationError
from app.runner import JuliaRunExecutor, LocalRunQueue
from app.time_series_ingestion import (
    TimeSeriesIngestionError,
    attach_time_series_source,
    apply_time_series_mapping,
    get_time_series_source_rows,
    ingest_time_series_source,
    read_time_series_source_rows,
    update_time_series_source_rows,
)
from app.validation import JuliaValidationService, ValidationResult


PORTAL_LOGO_MAX_BYTES = 256 * 1024


def portal_logo_signature_matches(media_type: str, payload: bytes) -> bool:
    if media_type == "image/png":
        return payload.startswith(b"\x89PNG\r\n\x1a\n")
    if media_type == "image/jpeg":
        return payload.startswith(b"\xff\xd8\xff")
    return False


class SystemCaseValidationRequest(BaseModel):
    system_case_json: str = Field(min_length=1)


class ProjectCreateRequest(BaseModel):
    name: str = Field(min_length=1)
    description: str = ""


class ScenarioCreateRequest(BaseModel):
    name: str = Field(min_length=1)
    description: str = ""


class UserCreateRequest(BaseModel):
    email: str = Field(min_length=1)
    password: str = Field(min_length=1)
    role: Literal["admin", "analyst", "external"]
    display_name: str = ""


class CustomSemanticTypeCreateRequest(BaseModel):
    semantic_key: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    dimension_key: str = Field(min_length=1)
    canonical_unit_key: str = Field(min_length=1)
    value_kind: str = Field(min_length=1)
    default_aggregation: str = Field(min_length=1)
    validation_rules: dict[str, Any]


class CatalogAssociationOperationBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    client_operation_id: str = Field(min_length=1)
    reason_code: str = Field(min_length=1)
    reason_text: str | None = None


class CatalogAssociationAddRequest(CatalogAssociationOperationBase):
    action: Literal["add"]
    signal_id: int = Field(gt=0)
    linkable_object_id: int = Field(gt=0)
    binding_role_key: str = Field(min_length=1)
    expected_absent: Literal[True]


class CatalogAssociationReplaceRequest(CatalogAssociationOperationBase):
    action: Literal["replace"]
    association_id: int = Field(gt=0)
    expected_lifecycle_revision: int = Field(gt=0)
    signal_id: int = Field(gt=0)
    linkable_object_id: int = Field(gt=0)
    binding_role_key: str = Field(min_length=1)


class CatalogAssociationArchiveRequest(CatalogAssociationOperationBase):
    action: Literal["archive"]
    association_id: int = Field(gt=0)
    expected_lifecycle_revision: int = Field(gt=0)
    reason_text: str = Field(min_length=1)


class CatalogAssociationRevalidateRequest(CatalogAssociationOperationBase):
    action: Literal["revalidate"]
    association_id: int = Field(gt=0)
    expected_lifecycle_revision: int = Field(gt=0)


CatalogAssociationOperationRequest = Annotated[
    CatalogAssociationAddRequest
    | CatalogAssociationReplaceRequest
    | CatalogAssociationArchiveRequest
    | CatalogAssociationRevalidateRequest,
    Field(discriminator="action"),
]


class CatalogAssociationPrevalidationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_project_id: int = Field(gt=0)
    operations: list[CatalogAssociationOperationRequest] = Field(
        min_length=1, max_length=200
    )


class CatalogAssociationCommitRequest(CatalogAssociationPrevalidationRequest):
    prevalidation_token: str = Field(min_length=1)
    confirmed: bool = False


class CaseBindingRevisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["current", "pinned"]
    revision_id: int = Field(gt=0)
    content_hash: str = Field(min_length=1)


class CaseBindingCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    client_operation_id: str = Field(min_length=1)
    action: Literal["create"]
    linkable_object_id: int = Field(gt=0)
    binding_role_key: str = Field(min_length=1)
    signal_id: int = Field(gt=0)
    revision: CaseBindingRevisionRequest
    catalog_association_id: int | None = Field(default=None, gt=0)
    reason_code: str = Field(min_length=1)
    reason_text: str | None = None


class CaseBindingReplaceRequest(CaseBindingCreateRequest):
    action: Literal["replace"]
    binding_id: int = Field(gt=0)
    expected_lifecycle_revision: int = Field(gt=0)
    reason_text: str = Field(min_length=1)


class CaseBindingRevalidateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    client_operation_id: str = Field(min_length=1)
    action: Literal["revalidate_current", "revalidate_pinned"]
    binding_id: int = Field(gt=0)
    expected_lifecycle_revision: int = Field(gt=0)
    reason_code: str = Field(min_length=1)
    reason_text: str | None = None


class CaseBindingLifecycleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    client_operation_id: str = Field(min_length=1)
    action: Literal["remove", "restore"]
    binding_id: int = Field(gt=0)
    expected_lifecycle_revision: int = Field(gt=0)
    reason_code: str = Field(min_length=1)
    reason_text: str = Field(min_length=1)


CaseBindingOperationRequest = Annotated[
    CaseBindingCreateRequest
    | CaseBindingReplaceRequest
    | CaseBindingRevalidateRequest
    | CaseBindingLifecycleRequest,
    Field(discriminator="action"),
]


class CaseBindingPrevalidationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_bindings_revision: int = Field(ge=0)
    operations: list[CaseBindingOperationRequest] = Field(min_length=1, max_length=200)


class CaseBindingCommitRequest(CaseBindingPrevalidationRequest):
    prevalidation_token: str = Field(min_length=1)
    confirmed: bool = False


class BootstrapAdminRequest(BaseModel):
    email: str = Field(min_length=1)
    password: str = Field(min_length=1)
    display_name: str = ""


class LoginRequest(BaseModel):
    email: str = Field(min_length=1)
    password: str = Field(min_length=1)
    next: str = ""


class CurrentUser(BaseModel):
    id: int
    email: str
    display_name: str
    role: Literal["admin", "analyst", "external"]
    is_active: bool


class CurrentUserResponse(BaseModel):
    user: CurrentUser | None
    bootstrap_required: bool = False
    landing_path: str | None = None


class AuthSessionResponse(BaseModel):
    user: CurrentUser
    landing_path: str


class CsrfTokenResponse(BaseModel):
    csrf_token: str


class ExternalProjectAccessRequest(BaseModel):
    portal_view: bool
    operate: bool


class PortalConfigurationWriteRequest(BaseModel):
    document: dict[str, Any]
    status: str
    expected_revision: int


class PortalLogoDeleteRequest(BaseModel):
    expected_revision: int


class OperatorConsoleCreateRequest(BaseModel):
    source_variant_id: int
    document: dict[str, Any]


class OperatorConsoleWriteRequest(BaseModel):
    document: dict[str, Any]
    status: str
    expected_revision: int


class ConsoleParameterOverrideRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    value: float


class ConsoleParametersWriteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    parameters: list[ConsoleParameterOverrideRequest]


class ConsoleSeriesSelectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    group_id: str = Field(min_length=1)
    column_id: str = Field(min_length=1)
    source_option_id: str = Field(min_length=1)


class ConsoleSeriesSelectionsWriteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    selections: list[ConsoleSeriesSelectionRequest] = Field(min_length=1)


class ConsoleLeaseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lease_token: str = Field(min_length=1)


class ConsoleUndoRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lease_token: str = Field(min_length=1)


class ConsoleSeriesRestoreRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    revision_number: int = Field(ge=1)
    expected_current_revision: int = Field(ge=1)
    note: str | None = None


class ConsoleGroupCellRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    column_id: str = Field(min_length=1)
    row_index: int
    value: Any


class ConsoleGroupValuesWriteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    range_start: str = Field(min_length=1)
    range_end: str = Field(min_length=1)
    granularity: str = Field(min_length=1)
    lease_token: str = Field(min_length=1)
    note: str | None = None
    cells: list[ConsoleGroupCellRequest]


class ConsoleRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    range_start: str = Field(min_length=1)
    range_end: str = Field(min_length=1)


class DashboardTemplateWriteRequest(BaseModel):
    name: str = Field(min_length=1)
    show_summary: bool = True
    show_price_chart: bool = True
    show_grid_chart: bool = True
    show_renewable_chart: bool = True
    show_bess_chart: bool = True
    show_hydro_chart: bool = True
    show_profit_chart: bool = True
    show_system_dispatch_table: bool = True
    show_asset_dispatch_table: bool = True
    table_preview_limit: int = Field(default=10, ge=1)


class PublicationDraftWriteRequest(BaseModel):
    dashboard_template_id: int
    public_title: str = Field(min_length=1)
    analyst_notes: str = ""
    allowed_artifact_types: list[str] | None = None


class ScenarioVersionCreateRequest(BaseModel):
    system_case_json: str = Field(min_length=1)


class ScenarioDraftWriteRequest(BaseModel):
    document: dict[str, Any] | None = None
    source_version_id: int | None = None


class CaseTimeSeriesBindingRequest(BaseModel):
    signal_key: str = Field(min_length=1)
    entity_type: str | None = None
    entity_id: str | None = None
    time_series_set_id: int


class ObjectSeriesTemporalContractRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    regularity: Literal["regular", "irregular"]
    nominal_resolution_seconds: float | None = None
    timestamp_convention: Literal["period_start", "period_end"] = "period_start"


class ObjectSeriesSourceExpectationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["api", "csv", "xlsx", "manual"] = "api"
    display_name: str = ""


class ObjectSeriesCreateRequest(BaseModel):
    # ``extra="forbid"`` is the structural half of chapter 7.4: owner, project
    # and entity pair are never accepted in the payload as authority.
    model_config = ConfigDict(extra="forbid")

    object_series_key: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    description: str = ""
    intended_binding_role_key: str = Field(min_length=1)
    semantic_type_key: str = Field(min_length=1)
    unit_key: str = Field(min_length=1)
    data_class_key: str = Field(min_length=1)
    timezone: str = Field(default="UTC", min_length=1)
    temporal_contract: ObjectSeriesTemporalContractRequest
    source_expectation: ObjectSeriesSourceExpectationRequest | None = None
    metadata: dict[str, Any] | None = None


class ObjectSeriesPatchRequest(BaseModel):
    # Only the editable face of chapter 7.5 exists here, so owner, local key,
    # semantic type, unit and ``series_kind`` are refused structurally.
    model_config = ConfigDict(extra="forbid")

    display_name: str | None = Field(default=None, min_length=1)
    description: str | None = None
    metadata: dict[str, Any] | None = None


class ObjectSeriesArchiveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason_code: str = Field(min_length=1)
    reason_text: str = Field(min_length=1)


class ObjectSeriesExpectedBaseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    revision_id: int = Field(gt=0)
    content_hash: str = Field(min_length=1)


class ObjectSeriesRevisionContractRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data_class_key: str | None = None
    timezone: str | None = None
    regularity: Literal["regular", "irregular"] | None = None
    nominal_resolution_seconds: float | None = None


class ObjectSeriesIngestionSourceRequest(BaseModel):
    # ``stored_path``, ``created_by`` and ``checksum`` are computed by the
    # server and are never accepted as truth (chapter 7.5).
    model_config = ConfigDict(extra="forbid")

    kind: Literal["api"] = "api"
    display_name: str = ""
    external_reference: str = ""


class ObjectSeriesPointRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    timestamp_start: str = Field(min_length=1)
    timestamp_end: str | None = None
    duration_seconds: float | None = None
    values: dict[str, Any]


class ObjectSeriesPointsIngestionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["replace_full", "append_tail"] = "replace_full"
    expected_base: ObjectSeriesExpectedBaseRequest | None = None
    revision_contract: ObjectSeriesRevisionContractRequest | None = None
    source: ObjectSeriesIngestionSourceRequest | None = None
    points: list[ObjectSeriesPointRequest] = Field(min_length=1)


class ObjectSeriesIngestionMappingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value_keys: dict[str, str] | None = None
    mode: Literal["replace_full", "append_tail"] | None = None
    expected_base: ObjectSeriesExpectedBaseRequest | None = None
    sheet_name: str | None = None
    revision_contract: ObjectSeriesRevisionContractRequest | None = None
    columns: dict[str, Any] | None = None
    source: dict[str, Any] | None = None


class ObjectSeriesPublicationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    validation_token: str = Field(min_length=1)
    confirm: bool = False
    reason_code: str = Field(min_length=1)
    reason_text: str | None = None


class SharedSeriesPointsIngestionRequest(BaseModel):
    """A load aimed at a shared generic source, started from one object.

    ``expected_base`` is mandatory here: a shared source always has a sealed
    revision, and a blind overwrite of what other projects consume is exactly
    what chapter 7.9 refuses.
    """

    model_config = ConfigDict(extra="forbid")

    mode: Literal["replace_full", "append_tail"] = "replace_full"
    expected_base: ObjectSeriesExpectedBaseRequest
    revision_contract: ObjectSeriesRevisionContractRequest | None = None
    source: ObjectSeriesIngestionSourceRequest | None = None
    points: list[ObjectSeriesPointRequest] = Field(min_length=1)


class SharedSeriesPublicationRequest(BaseModel):
    """`Publicar para todos`: permission, reason, comprehension and impact.

    Chapter 8.6 asks for all four before the shared publication is enabled, and
    revalidates the impact at confirmation time (AC-SHR-04, AC-SHR-06).
    """

    model_config = ConfigDict(extra="forbid")

    validation_token: str = Field(min_length=1)
    impact_fingerprint: str = Field(min_length=1)
    confirm: bool = False
    comprehension_acknowledged: bool = False
    reason_code: str = Field(min_length=1)
    reason_text: str | None = None


class ObjectSeriesDerivationRequest(BaseModel):
    """Copy a shared generic source into a series owned by this object."""

    model_config = ConfigDict(extra="forbid")

    object_series_key: str = Field(min_length=1)
    display_name: str | None = None
    description: str | None = None
    intended_binding_role_key: str | None = None
    metadata: dict[str, Any] | None = None
    source_revision: ObjectSeriesExpectedBaseRequest | None = None
    reason_code: str = Field(min_length=1)
    reason_text: str | None = None
    confirmed: bool = False
    prevalidation_token: str | None = None


class CaseInputVariantRunRequest(BaseModel):
    range_start: str = Field(min_length=1)
    range_end: str = Field(min_length=1)
    expected_bindings_revision: int | None = Field(default=None, ge=0)


class CaseInputVariantWriteRequest(BaseModel):
    display_name: str = Field(min_length=1)


class HydraulicDiagramViewportRequest(BaseModel):
    x: float = 0.0
    y: float = 0.0
    zoom: float = Field(default=1.0, gt=0)


class HydraulicReservoirParametersRequest(BaseModel):
    storage_min_hm3: float
    storage_max_hm3: float
    initial_storage_hm3: float
    terminal_condition: Literal["none", "equal_initial", "min_terminal"] = "none"
    terminal_storage_min_hm3: float | None = None
    terminal_water_value_usd_per_hm3: float = 0.0


class HydraulicCurvePointRequest(BaseModel):
    x_value: float
    y_value: float


class HydraulicStorageElevationCurveRequest(BaseModel):
    curve_set_id: int | None = None
    version_label: str | None = None
    points: list[HydraulicCurvePointRequest] = Field(default_factory=list)


class HydraulicFlowPowerCurveRequest(BaseModel):
    curve_set_id: int | None = None
    version_label: str | None = None
    points: list[HydraulicCurvePointRequest] = Field(default_factory=list)


class HydraulicNaturalInflowSeriesPointRequest(BaseModel):
    timestamp: str = Field(min_length=1)
    duration_hours: float = 1.0
    value_m3s: float


class HydraulicSeriesOriginRequest(BaseModel):
    kind: str


class HydraulicNaturalInflowSeriesRequest(BaseModel):
    time_series_set_id: int | None = None
    origin: HydraulicSeriesOriginRequest | None = None
    version_label: str | None = None
    points: list[HydraulicNaturalInflowSeriesPointRequest] = Field(default_factory=list)


class HydraulicPlantParametersRequest(BaseModel):
    non_modeled: bool = False
    min_power_mw: float | None = None
    max_power_mw: float | None = None


class HydraulicUnitRequest(BaseModel):
    technical_key: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    is_active: bool = True
    operation_mode: str = "generation"
    generation_mode: str = "flow_power_curve"
    intake_node_key: str | None = None
    discharge_node_key: str | None = None
    min_power_mw: float | None = None
    max_power_mw: float | None = None
    min_flow_m3s: float | None = None
    max_flow_m3s: float | None = None
    flow_power_curve: HydraulicFlowPowerCurveRequest | None = None


class HydraulicDiagramNodeRequest(BaseModel):
    component_type: Literal["reservoir", "junction", "plant"]
    technical_key: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    x: float | None = None
    y: float | None = None
    reservoir: HydraulicReservoirParametersRequest | None = None
    storage_elevation_curve: HydraulicStorageElevationCurveRequest | None = None
    natural_inflow_series: HydraulicNaturalInflowSeriesRequest | None = None
    plant: HydraulicPlantParametersRequest | None = None
    units: list[HydraulicUnitRequest] = Field(default_factory=list)
    link_anchors: dict[str, Any] | None = None


class HydraulicDiagramReachRequest(BaseModel):
    technical_key: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    from_node_key: str = Field(min_length=1)
    to_node_key: str = Field(min_length=1)
    reach_type: str = Field(min_length=1)
    routing_method: str = "none"
    travel_time_hours: float = 0.0
    flow_min_m3s: float | None = None
    spill_penalty_usd_per_hm3: float | None = None
    minimum_flow_series: HydraulicNaturalInflowSeriesRequest | None = None
    from_anchor: float | None = None
    to_anchor: float | None = None


class HydraulicDiagramSaveRequest(BaseModel):
    revision: str = Field(min_length=1)
    nodes: list[HydraulicDiagramNodeRequest]
    reaches: list[HydraulicDiagramReachRequest] = Field(default_factory=list)
    viewport: HydraulicDiagramViewportRequest = Field(default_factory=HydraulicDiagramViewportRequest)


class TimeSeriesMappingRequest(BaseModel):
    mapping: dict[str, Any]


class TimeSeriesRowsRequest(BaseModel):
    rows: list[dict[str, Any]]


class TimeSeriesCatalogSignalMappingRequest(BaseModel):
    source_column: str = Field(min_length=1)
    signal_key: str = Field(min_length=1)
    source_unit: str | None = None


class TimeSeriesCatalogImportRequest(BaseModel):
    set_name: str = Field(min_length=1)
    version_label: str = Field(min_length=1)
    data_kind: str = Field(min_length=1)
    timezone: str = Field(min_length=1)
    timestamp_column: str = Field(min_length=1)
    duration_hours_column: str = Field(min_length=1)
    value_column: str | None = None
    signal_key: str | None = None
    source_unit: str | None = None
    signal_mappings: list[TimeSeriesCatalogSignalMappingRequest] = Field(default_factory=list)


class DraftTimeSeriesExtractionRequest(BaseModel):
    set_name: str = Field(min_length=1)
    version_label: str = Field(min_length=1)
    data_kind: str = Field(min_length=1)
    timezone: str = Field(min_length=1)


class TimeSeriesSetValueEditRequest(BaseModel):
    period_index: int
    signal_key: str = Field(min_length=1)
    value: str = Field(min_length=1)


class TimeSeriesSetValuesEditRequest(BaseModel):
    edits: list[TimeSeriesSetValueEditRequest] = Field(default_factory=list)
    change_summary: str | None = None


class TimeSeriesSetReplacementSourceRequest(BaseModel):
    id: str = Field(min_length=1)
    kind: str = Field(min_length=1)
    original_filename: str = Field(min_length=1)
    media_type: str = Field(min_length=1)
    checksum: str = Field(min_length=1)
    stored_path: str = Field(min_length=1)
    selected_sheet: str | None = None


class TimeSeriesTransformationRequest(BaseModel):
    transformation_type: str = Field(min_length=1)
    parameters: dict[str, Any] = Field(default_factory=dict)
    output_name: str | None = None
    output_version_label: str | None = None


class TimeSeriesConnectorConfigRequest(BaseModel):
    connector_id: str = Field(min_length=1, default="http_json_forecast")
    base_url: str = Field(min_length=1)
    records_path: str | None = None
    auth_token: str | None = None


class TimeSeriesProgramMetadataRequest(BaseModel):
    issuer: str = Field(min_length=1)
    issued_at: str = Field(min_length=1)
    valid_from: str = Field(min_length=1)
    valid_until: str = Field(min_length=1)


class TimeSeriesConnectorIngestionRequest(BaseModel):
    connector: TimeSeriesConnectorConfigRequest
    set_name: str = Field(min_length=1)
    version_label: str = Field(min_length=1)
    timezone: str = Field(min_length=1)
    timestamp_column: str = Field(min_length=1)
    duration_hours_column: str = Field(min_length=1)
    value_column: str | None = None
    signal_key: str | None = None
    source_unit: str | None = None
    signal_mappings: list[TimeSeriesCatalogSignalMappingRequest] = Field(default_factory=list)
    program: TimeSeriesProgramMetadataRequest | None = None


class TimeSeriesSetReplaceRequest(BaseModel):
    source: TimeSeriesSetReplacementSourceRequest
    data_kind: str = Field(min_length=1)
    timezone: str = Field(min_length=1)
    timestamp_column: str = Field(min_length=1)
    duration_hours_column: str = Field(min_length=1)
    value_column: str | None = None
    signal_key: str | None = None
    source_unit: str | None = None
    signal_mappings: list[TimeSeriesCatalogSignalMappingRequest] = Field(default_factory=list)
    change_summary: str | None = None


class ResultCleanupRequest(BaseModel):
    targets: list[str] = Field(default_factory=list)


class RunScheduleCreateRequest(BaseModel):
    scenario_id: int
    case_input_variant_id: int
    display_name: str = Field(min_length=1)
    range_start: str = Field(min_length=1)
    range_end: str = Field(min_length=1)
    cadence: str = Field(min_length=1)
    next_run_at: str = Field(min_length=1)
    range_mode: str = "fixed"
    rolling_start_offset_hours: float | None = None
    rolling_duration_hours: float | None = None


class RunDueSchedulesRequest(BaseModel):
    now: str | None = None


class DraftPromotionError(ValueError):
    pass


def create_app(
    validation_service: JuliaValidationService | None = None,
    *,
    database_url: str | None = None,
    store: AnalystStore | None = None,
    run_queue=None,
    artifact_root: Path | str | None = None,
    input_source_root: Path | str | None = None,
    frontend_dist: Path | str | None = None,
    auth_enabled: bool | None = None,
    session_cookie_name: str = "bess_session",
    csrf_cookie_name: str = "bess_csrf",
    session_hours: int = 12,
    session_cookie_secure: bool | None = None,
    forecast_connector_factory=None,
) -> FastAPI:
    service = validation_service or JuliaValidationService()
    analyst_store = store or AnalystStore(database_url)
    auth_required = auth_enabled_from_env(False) if auth_enabled is None else bool(auth_enabled)
    configured_artifact_root = Path(
        artifact_root
        or os.environ.get("ARTIFACT_ROOT")
        or Path(__file__).resolve().parents[1] / ".tmp" / "artifacts"
    )
    configured_input_source_root = Path(
        input_source_root
        or os.environ.get("INPUT_SOURCE_ROOT")
        or Path(__file__).resolve().parents[1] / ".tmp" / "input_sources"
    )
    configured_frontend_dist = Path(
        frontend_dist
        or os.environ.get("FRONTEND_DIST")
        or Path(__file__).resolve().parents[1] / "frontend" / "dist"
    )
    local_run_queue = run_queue or LocalRunQueue(
        executor=JuliaRunExecutor(store=analyst_store, artifact_root=configured_artifact_root)
    )

    def default_forecast_connector(
        config: HttpJsonForecastConnectorConfig,
    ) -> ForecastConnector:
        return HttpJsonForecastConnector(config)

    build_forecast_connector = forecast_connector_factory or default_forecast_connector
    cookie_secure = (
        cookie_secure_from_env(False)
        if session_cookie_secure is None
        else bool(session_cookie_secure)
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        try:
            yield
        finally:
            if local_run_queue is not None:
                local_run_queue.stop()
            analyst_store.close()

    app = FastAPI(title="BESS Analyst App", lifespan=lifespan)
    app.state.analyst_store = analyst_store
    app.state.auth_enabled = auth_required
    authorization = AuthorizationService(analyst_store)

    @app.exception_handler(RequestValidationError)
    async def stable_association_request_validation(
        request: Request, error: RequestValidationError
    ):
        if "/linkable-objects/" in request.url.path:
            # The object-scoped surface answers problem+json on every channel
            # (chapter 7.11), including a payload its schema refuses outright.
            location = [
                str(part)
                for part in error.errors()[0].get("loc", ())
                if str(part) not in {"body", "header"}
            ]
            missing_precondition = any(
                part.lower() in {"if-match", "idempotency-key"} for part in location
            )
            request_id = (
                request.headers.get("x-request-id") or f"req_{secrets.token_hex(8)}"
            )
            refusal = ObjectSeriesError(
                "TS_INGEST_PRECONDITION_REQUIRED"
                if missing_precondition
                else "TS_OBJECT_SERIES_DEFINITION_INVALID",
                detail=error.errors()[0].get("msg", "the payload is not valid"),
                field=".".join(location) or "body",
            )
            return JSONResponse(
                object_series_problem(refusal, request_id=request_id),
                status_code=refusal.status,
                media_type="application/problem+json",
                headers={"Cache-Control": "private, no-store"},
            )
        association_contract = request.url.path in {
            "/api/time-series/catalog/association-prevalidations",
            "/api/time-series/catalog/association-batches",
        }
        binding_contract = request.url.path.endswith(
            "/time-series-binding-prevalidations"
        ) or request.url.path.endswith("/time-series-binding-batches")
        if not association_contract and not binding_contract:
            return await request_validation_exception_handler(request, error)
        location = list(error.errors()[0].get("loc", ()))
        missing_commit_precondition = (
            request.url.path.endswith("-batches")
            and any(
                str(part).lower()
                in {"prevalidation_token", "if-match", "idempotency-key"}
                for part in location
            )
        )
        location = [
            part
            for part in location
            if part
            not in {
                "body",
                "header",
                "add",
                "create",
                "replace",
                "archive",
                "revalidate",
                "revalidate_current",
                "revalidate_pinned",
                "remove",
                "restore",
            }
        ]
        field = ""
        for part in location:
            if isinstance(part, int):
                field += f"[{part}]"
            else:
                field += ("." if field else "") + str(part)
        request_id = request.headers.get("x-request-id") or f"req_{secrets.token_hex(8)}"
        error_type = BindingMutationError if binding_contract else AssociationMutationError
        refusal = error_type(
            "TS_PRECONDITION_REQUIRED"
            if missing_commit_precondition
            else "TS_LINK_PAYLOAD_INVALID",
            field=field or "body",
            reason="request_validation",
        )
        return JSONResponse(
            (
                binding_error_payload(refusal, request_id=request_id)
                if binding_contract
                else association_error_payload(refusal, request_id=request_id)
            ),
            status_code=428 if missing_commit_precondition else 400,
            headers={"Cache-Control": "private, no-store"},
        )

    def current_user_from_request(request: Request) -> dict[str, Any] | None:
        token = request.cookies.get(session_cookie_name)
        if not token:
            return None
        return authorization.user_for_session_token_hash(hash_session_token(token))

    def public_current_user(user: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": user["id"],
            "email": user["email"],
            "display_name": user["display_name"],
            "role": user["role"],
            "is_active": user["is_active"],
        }

    def react_bookmark_path(request: Request) -> str:
        if request.url.path in {"/login", "/bootstrap"}:
            next_path = safe_internal_next_path(request.query_params.get("next", ""))
            return legacy_path_to_react_path(next_path)
        return legacy_path_to_react_path(request.url.path)

    def react_bookmark_redirect(request: Request, status_code: int = 303) -> RedirectResponse:
        target = react_bookmark_path(request)
        if request.url.query and request.url.path not in {"/login", "/bootstrap"}:
            target = f"{target}?{request.url.query}"
        return RedirectResponse(target, status_code=status_code)

    def auth_redirect(request: Request) -> RedirectResponse:
        return react_bookmark_redirect(request)

    def auth_required_response(request: Request) -> Response:
        if request.url.path.startswith("/api/"):
            return JSONResponse({"detail": "authentication required"}, status_code=401)
        return auth_redirect(request)

    def forbidden_response(request: Request) -> Response:
        if request.url.path.startswith("/api/"):
            return JSONResponse({"detail": "forbidden"}, status_code=403)
        return react_bookmark_redirect(request)

    def not_found_response() -> Response:
        return JSONResponse({"detail": "not found"}, status_code=404)

    def external_may_reach_path(path: str) -> bool:
        """The console and portal roots, and nothing else."""

        return (
            path in {"/", "/api/auth/me"}
            or path.startswith("/api/console")
            or path.startswith("/api/client")
            or path == "/client"
            or path.startswith("/client/")
        )

    def require_admin_user(request: Request) -> None:
        if not auth_required:
            return
        try:
            authorization.require_admin(request.state.current_user)
        except PermissionError as error:
            raise HTTPException(status_code=403, detail="forbidden")

    def require_client_project_access(request: Request, project_id: int) -> None:
        if not auth_required:
            return
        try:
            authorization.require_client_project_access(request.state.current_user, project_id)
        except PermissionError as error:
            raise HTTPException(status_code=403, detail="forbidden") from error
        except KeyError as error:
            raise HTTPException(status_code=404, detail="project not found") from error

    def require_client_publication_access(
        request: Request,
        project_id: int,
        publication_id: int,
    ) -> dict[str, Any] | None:
        if not auth_required:
            return None
        try:
            return authorization.require_published_client_publication(
                request.state.current_user,
                project_id=project_id,
                publication_id=publication_id,
            )
        except PermissionError as error:
            raise HTTPException(status_code=403, detail="forbidden") from error
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    def set_session_cookie(response: Response, token: str) -> None:
        response.set_cookie(
            session_cookie_name,
            token,
            max_age=session_hours * 60 * 60,
            httponly=True,
            samesite="lax",
            secure=cookie_secure,
        )

    def set_csrf_cookie(response: Response, token: str) -> None:
        response.set_cookie(
            csrf_cookie_name,
            token,
            max_age=session_hours * 60 * 60,
            httponly=False,
            samesite="lax",
            secure=cookie_secure,
        )

    def user_may_enter_react_root(user: dict[str, Any], root: str) -> bool:
        """Whether the identity is allowed inside one of the three roots."""

        internal = user["role"] in INTERNAL_USER_ROLES
        if root == "analyst":
            return internal
        if root == "console":
            return internal or analyst_store.external_has_any_project_capability(
                user_id=int(user["id"]), capability="operate"
            )
        if root == "portal":
            if user["role"] != "external":
                return False
            return analyst_store.external_has_any_project_capability(
                user_id=int(user["id"]), capability="portal_view"
            )
        return False

    def external_landing_path(user: dict[str, Any]) -> str:
        """`operate` wins over `portal_view`; one visible console opens itself."""

        user_id = int(user["id"])
        consoles = analyst_store.list_operable_operator_consoles(user_id)
        if len(consoles) == 1:
            return f"/react/console/{consoles[0]['id']}"
        if consoles or analyst_store.external_has_any_project_capability(
            user_id=user_id, capability="operate"
        ):
            return "/react/console"
        return "/react/client"

    def react_authenticated_landing_path(user: dict[str, Any], next_path: str = "") -> str:
        """The single landing calculation shared by login and current-user."""

        safe_next = safe_react_next_path(next_path)
        root = react_root_of_path(safe_next)
        if root and user_may_enter_react_root(user, root):
            return safe_next
        if user["role"] in INTERNAL_USER_ROLES:
            return "/react/projects"
        return external_landing_path(user)

    def require_csrf_token(request: Request) -> None:
        expected = request.cookies.get(csrf_cookie_name)
        provided = request.headers.get("x-csrf-token")
        if not expected or not provided or not secrets.compare_digest(expected, provided):
            raise HTTPException(status_code=403, detail="csrf token required")

    def auth_session_response(
        user: dict[str, Any],
        token: str,
        *,
        landing_path: str,
        status_code: int = 200,
    ) -> JSONResponse:
        response = JSONResponse(
            {
                "user": public_current_user(user),
                "landing_path": landing_path,
            },
            status_code=status_code,
        )
        set_session_cookie(response, token)
        return response

    @app.middleware("http")
    async def require_authenticated_app_boundary(request: Request, call_next):
        request.state.current_user = None
        if not auth_required:
            return await call_next(request)

        path = request.url.path
        if path.startswith("/api/auth/"):
            request.state.current_user = current_user_from_request(request)
            if request.method not in {"GET", "HEAD", "OPTIONS"} and path != "/api/auth/csrf":
                try:
                    require_csrf_token(request)
                except HTTPException as error:
                    return JSONResponse({"detail": error.detail}, status_code=error.status_code)
            return await call_next(request)

        if path == "/react" or path.startswith("/react/"):
            request.state.current_user = current_user_from_request(request)
            return await call_next(request)

        if path in {"/favicon.ico", "/login", "/bootstrap", "/logout", "/assets/plotly.min.js"}:
            return await call_next(request)

        user = current_user_from_request(request)
        request.state.current_user = user
        if user is None:
            return auth_required_response(request)

        if user["role"] == "external" and path.startswith(
            "/api/time-series/catalog"
        ):
            # TS7's whole internal catalog is refused at the namespace boundary,
            # before FastAPI resolves a signal/revision id or invokes a query.
            return forbidden_response(request)

        if user["role"] == "external" and not external_may_reach_path(path):
            # A root an external identity may not enter reveals nothing about
            # itself, not even that the route exists.
            return not_found_response()

        if path.startswith("/api/") and request.method not in {"GET", "HEAD", "OPTIONS"}:
            try:
                require_csrf_token(request)
            except HTTPException as error:
                return JSONResponse({"detail": error.detail}, status_code=error.status_code)

        if path == "/" or path == "/api/auth/me":
            return await call_next(request)
        if path.startswith("/api/console"):
            # Operators reach their consoles here and internal users test them
            # with their real identity; per-console `operate` is enforced by the
            # endpoint, which answers 404 so ids stay unguessable.
            if user["role"] not in {"admin", "analyst", "external"}:
                return forbidden_response(request)
            return await call_next(request)
        if path.startswith("/api/client"):
            try:
                authorization.require_client(user)
            except PermissionError:
                return forbidden_response(request)
            return await call_next(request)
        if path.startswith("/client"):
            try:
                authorization.require_client(user)
            except PermissionError:
                return forbidden_response(request)
            return await call_next(request)
        try:
            authorization.require_internal(user)
        except PermissionError:
            return forbidden_response(request)
        return await call_next(request)

    @app.get("/assets/plotly.min.js", include_in_schema=False)
    async def plotly_javascript_bundle():
        return Response(
            content=cached_plotly_javascript(),
            media_type="application/javascript",
            headers={"Cache-Control": "public, max-age=86400"},
        )

    def save_validated_scenario_version(
        scenario_id: int,
        candidate_text: str,
        generation_metadata: dict[str, Any] | None = None,
        created_by: str = "internal_analyst",
    ) -> tuple[dict | None, ValidationResult | None]:
        result = service.validate_text(candidate_text)
        if not result.ok:
            return None, result

        try:
            document = json.loads(candidate_text)
        except json.JSONDecodeError as error:
            return None, ValidationResult(
                ok=False,
                phase="json",
                message=f"Malformed JSON: {error.msg} at line {error.lineno}, column {error.colno}",
                payload={"status": "error", "message": error.msg, "line": error.lineno, "column": error.colno},
            )

        version = analyst_store.create_scenario_version(
            scenario_id=scenario_id,
            system_case_json=document,
            validation_payload=result.payload,
            generation_metadata=generation_metadata,
            created_by=created_by,
        )
        return version, None

    def create_and_enqueue_run(
        scenario_version_id: int,
        *,
        triggered_by: str = "internal_analyst",
        trigger_type: str = "manual",
        triggered_by_user_id: int | None = None,
        triggered_by_display_name: str | None = None,
        operator_console_id: int | None = None,
        operator_console_revision: int | None = None,
        materialized_lineage: dict[str, Any] | None = None,
    ) -> dict:
        run = analyst_store.create_run(
            scenario_version_id=scenario_version_id,
            triggered_by=triggered_by,
            trigger_type=trigger_type,
            triggered_by_user_id=triggered_by_user_id,
            triggered_by_display_name=triggered_by_display_name,
            operator_console_id=operator_console_id,
            operator_console_revision=operator_console_revision,
            materialized_lineage=materialized_lineage,
        )
        local_run_queue.enqueue(run["id"])
        return run

    def publication_download_artifacts(
        publication: dict[str, Any],
        artifacts: list[dict[str, Any]],
        url_builder,
    ) -> list[dict[str, Any]]:
        allowed_types = set(publication.get("allowed_artifact_types") or [])
        downloads: list[dict[str, Any]] = []
        for artifact in artifacts:
            artifact_type = artifact["artifact_type"]
            if artifact_type not in allowed_types:
                continue
            if not artifact_path_is_safe(artifact["path"], configured_artifact_root):
                continue
            if not Path(artifact["path"]).is_file():
                continue
            body = publication_download_response_body(artifact)
            body["download_url"] = url_builder(artifact)
            downloads.append(body)
        return downloads

    def get_client_publication_download(project_id: int, publication_id: int, artifact_type: str) -> dict[str, Any]:
        publication = analyst_store.get_publication(publication_id)
        if publication["project_id"] != project_id or publication["status"] != "published":
            raise KeyError(f"publication {publication_id} not found")
        if artifact_type not in set(publication.get("allowed_artifact_types") or []):
            raise KeyError(f"artifact {artifact_type} not found for publication {publication_id}")
        for artifact in analyst_store.list_run_artifacts(publication["run_id"]):
            if artifact["artifact_type"] != artifact_type:
                continue
            if not artifact_path_is_safe(artifact["path"], configured_artifact_root):
                raise KeyError(f"artifact {artifact_type} not found for publication {publication_id}")
            artifact_path = Path(artifact["path"])
            if not artifact_path.is_file():
                raise KeyError(f"artifact {artifact_type} file not found")
            return artifact
        raise KeyError(f"artifact {artifact_type} not found for publication {publication_id}")

    def client_publication_payload(project_id: int, publication_id: int, request: Request) -> dict[str, Any]:
        try:
            project = analyst_store.get_project(project_id)
            publication = require_client_publication_access(request, project_id, publication_id)
            if publication is None:
                publication = analyst_store.get_publication(publication_id)
                if publication["project_id"] != project_id or publication["status"] != "published":
                    raise KeyError(f"publication {publication_id} not found")
            run = analyst_store.get_run(publication["run_id"])
            artifacts = analyst_store.list_run_artifacts(run["id"])
            downloads = publication_download_artifacts(
                publication,
                artifacts,
                lambda artifact: (
                    f"/api/client/projects/{project_id}/publications/{publication_id}/artifacts/"
                    f"{quote(artifact['artifact_type'], safe='')}/download"
                ),
            )
            canonical_results = read_run_results(
                run, artifacts, configured_artifact_root, store=analyst_store
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ResultReadError:
            # The technical reason stays internal: the portal only learns that
            # the results are unavailable.
            canonical_results = None
        return configured_portal_payload(
            project=project,
            publication=publication,
            results=canonical_results,
            downloads=downloads,
            logo_url=(
                f"/api/client/projects/{project_id}/branding/logo"
            ),
        )

    def configured_portal_payload(
        *,
        project: dict[str, Any],
        publication: dict[str, Any],
        results: dict[str, Any] | None,
        downloads: list[dict[str, Any]],
        logo_url: str,
    ) -> dict[str, Any]:
        configuration = analyst_store.get_portal_configuration(project["id"])
        if configuration is None or configuration["status"] != "active":
            document = default_portal_config_document()
            resolved_logo_url = None
        else:
            document = configuration["document"]
            resolved_logo_url = logo_url if configuration["logo_bytes"] is not None else None
        return build_portal_publication_payload(
            project=project,
            publication=publication,
            document=document,
            results=results,
            downloads=downloads,
            logo_url=resolved_logo_url,
        )

    def resolved_external_portal_branding(project: dict[str, Any]) -> dict[str, Any]:
        configuration = analyst_store.get_portal_configuration(project["id"])
        if configuration is None or configuration["status"] != "active":
            document = default_portal_config_document()
            logo_url = None
        else:
            document = configuration["document"]
            logo_url = (
                f"/api/client/projects/{project['id']}/branding/logo"
                if configuration["logo_bytes"] is not None
                else None
            )
        return build_portal_branding(project, document, logo_url)

    def get_or_create_scenario_draft(scenario_id: int) -> dict:
        try:
            return analyst_store.get_scenario_draft(scenario_id)
        except KeyError:
            draft_document = create_initial_draft_document(analyst_store, scenario_id, None)
            return analyst_store.create_or_replace_scenario_draft(
                scenario_id=scenario_id,
                document=draft_document,
            )

    @app.get("/")
    async def root(request: Request):
        return RedirectResponse("/react", status_code=303)

    @app.get("/favicon.ico")
    async def favicon():
        return Response(status_code=204)

    def react_entry_response() -> FileResponse:
        entry_path = configured_frontend_dist / "index.html"
        if not entry_path.is_file():
            raise HTTPException(status_code=503, detail="React application has not been built")
        return FileResponse(
            entry_path,
            media_type="text/html",
            headers={"Cache-Control": "no-cache"},
        )

    @app.get("/react", include_in_schema=False)
    async def react_entry():
        return react_entry_response()

    @app.get("/react/assets/{asset_path:path}", include_in_schema=False)
    async def react_asset(asset_path: str):
        assets_root = (configured_frontend_dist / "assets").resolve(strict=False)
        candidate = (assets_root / asset_path).resolve(strict=False)
        if not candidate.is_relative_to(assets_root) or not candidate.is_file():
            raise HTTPException(status_code=404, detail="React asset not found")
        return FileResponse(
            candidate,
            headers={"Cache-Control": "public, max-age=31536000, immutable"},
        )

    @app.get("/react/{spa_path:path}", include_in_schema=False)
    async def react_spa_fallback(spa_path: str):
        return react_entry_response()

    @app.get("/login", include_in_schema=False)
    @app.get("/bootstrap", include_in_schema=False)
    @app.get("/logout", include_in_schema=False)
    @app.get("/projects", include_in_schema=False)
    @app.get("/admin/users", include_in_schema=False)
    @app.get("/system-cases/validate", include_in_schema=False)
    async def legacy_static_bookmark(request: Request):
        return react_bookmark_redirect(request)

    @app.get("/projects/{project_id}", include_in_schema=False)
    @app.get("/scenarios/{scenario_id}", include_in_schema=False)
    @app.get("/scenarios/{scenario_id}/draft", include_in_schema=False)
    @app.get("/scenario-versions/{scenario_version_id}", include_in_schema=False)
    @app.get("/runs/{run_id}", include_in_schema=False)
    @app.get("/publications/{publication_id}/preview", include_in_schema=False)
    @app.get("/client", include_in_schema=False)
    @app.get("/client/projects/{project_id}", include_in_schema=False)
    @app.get("/client/projects/{project_id}/publications/{publication_id}", include_in_schema=False)
    async def legacy_dynamic_bookmark(
        request: Request,
        project_id: int | None = None,
        scenario_id: int | None = None,
        scenario_version_id: int | None = None,
        run_id: int | None = None,
        publication_id: int | None = None,
    ):
        return react_bookmark_redirect(request)

    @app.get("/api/auth/csrf", response_model=CsrfTokenResponse)
    async def csrf_token(request: Request):
        token = request.cookies.get(csrf_cookie_name) or secrets.token_urlsafe(32)
        response = JSONResponse({"csrf_token": token})
        set_csrf_cookie(response, token)
        return response

    @app.post("/api/auth/bootstrap", response_model=AuthSessionResponse, status_code=201)
    async def api_bootstrap_first_admin(payload: BootstrapAdminRequest):
        if not auth_required:
            raise HTTPException(status_code=403, detail="authentication is disabled")
        if analyst_store.count_users() > 0:
            raise HTTPException(status_code=403, detail="bootstrap is closed")

        email = payload.email.strip().lower()
        password = payload.password
        display_name = payload.display_name.strip()
        if not email or not password:
            raise HTTPException(status_code=400, detail="email and password are required")

        user = analyst_store.create_user(
            email=email,
            display_name=display_name,
            role="admin",
            password_hash=hash_password(password),
            created_by="bootstrap",
        )
        token = new_session_token()
        analyst_store.create_auth_session(
            user_id=user["id"],
            token_hash=hash_session_token(token),
            expires_at=session_expires_at(hours=session_hours),
        )
        return auth_session_response(
            user,
            token,
            landing_path=react_authenticated_landing_path(user),
            status_code=201,
        )

    @app.post("/api/auth/login", response_model=AuthSessionResponse)
    async def api_login(payload: LoginRequest):
        if not auth_required:
            raise HTTPException(status_code=403, detail="authentication is disabled")

        email = payload.email.strip().lower()
        user = None
        try:
            user = analyst_store.get_user_by_email(email)
        except KeyError:
            pass

        if user is None or not user["is_active"] or not verify_password(payload.password, user["password_hash"]):
            raise HTTPException(status_code=401, detail="Invalid email or password.")

        token = new_session_token()
        analyst_store.create_auth_session(
            user_id=user["id"],
            token_hash=hash_session_token(token),
            expires_at=session_expires_at(hours=session_hours),
        )
        return auth_session_response(
            user,
            token,
            landing_path=react_authenticated_landing_path(user, payload.next),
        )

    @app.post("/api/auth/logout", status_code=204)
    async def api_logout(request: Request):
        token = request.cookies.get(session_cookie_name)
        if token:
            analyst_store.revoke_auth_session(hash_session_token(token))
        response = Response(status_code=204)
        response.delete_cookie(session_cookie_name)
        return response

    @app.get("/api/client/projects")
    async def api_client_projects(request: Request):
        user = request.state.current_user
        if user is not None:
            projects = analyst_store.list_client_projects(user["id"])
            if not projects:
                raise HTTPException(status_code=404, detail="portal not found")
        else:
            projects = analyst_store.list_projects()
        return {
            "projects": [
                {
                    "id": project["id"],
                    "branding": resolved_external_portal_branding(project),
                }
                for project in projects
            ]
        }

    @app.get("/api/client/projects/{project_id}/publications")
    async def api_client_project_publications(project_id: int, request: Request):
        require_client_project_access(request, project_id)
        try:
            project = analyst_store.get_project(project_id)
            publications = analyst_store.list_published_project_publications(project_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return {
            "branding": resolved_external_portal_branding(project),
            "publications": publications,
        }

    @app.get("/api/client/projects/{project_id}/branding/logo")
    async def api_client_project_branding_logo(project_id: int, request: Request):
        require_client_project_access(request, project_id)
        configuration = analyst_store.get_portal_configuration(project_id)
        if (
            configuration is None
            or configuration["status"] != "active"
            or configuration["logo_bytes"] is None
            or configuration["logo_media_type"] is None
        ):
            raise HTTPException(status_code=404, detail="logo not found")
        etag = f'"portal-logo-r{configuration["revision"]}"'
        response_headers = {
            "ETag": etag,
            "Cache-Control": "private, must-revalidate",
            "X-Content-Type-Options": "nosniff",
        }
        if request.headers.get("if-none-match") == etag:
            return Response(status_code=304, headers=response_headers)
        return Response(
            content=configuration["logo_bytes"],
            media_type=configuration["logo_media_type"],
            headers=response_headers,
        )

    @app.get("/api/client/projects/{project_id}/publications/{publication_id}")
    async def api_client_publication_detail(project_id: int, publication_id: int, request: Request):
        return client_publication_payload(project_id, publication_id, request)

    @app.get("/api/client/projects/{project_id}/publications/{publication_id}/artifacts/{artifact_type}/download")
    async def api_download_client_publication_artifact(
        project_id: int,
        publication_id: int,
        artifact_type: str,
        request: Request,
    ):
        require_client_publication_access(request, project_id, publication_id)
        try:
            artifact = get_client_publication_download(project_id, publication_id, artifact_type)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return FileResponse(
            Path(artifact["path"]),
            media_type=artifact["media_type"],
            filename=artifact["display_name"],
        )

    @app.get(
        "/client/projects/{project_id}/publications/{publication_id}/artifacts/{artifact_type}/download",
        include_in_schema=False,
    )
    async def download_client_publication_artifact(
        project_id: int,
        publication_id: int,
        artifact_type: str,
        request: Request,
    ):
        require_client_publication_access(request, project_id, publication_id)
        try:
            artifact = get_client_publication_download(project_id, publication_id, artifact_type)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return FileResponse(
            Path(artifact["path"]),
            media_type=artifact["media_type"],
            filename=artifact["display_name"],
        )

    @app.get("/api/auth/me", response_model=CurrentUserResponse)
    async def current_auth_user(request: Request):
        user = request.state.current_user
        if user is None:
            return {
                "user": None,
                "bootstrap_required": auth_required and analyst_store.count_users() == 0,
                "landing_path": None,
            }
        return {
            "user": public_current_user(user),
            "bootstrap_required": False,
            "landing_path": react_authenticated_landing_path(user),
        }

    @app.get("/api/admin/users")
    async def admin_list_users(request: Request):
        require_admin_user(request)
        return {"users": [public_user_dict(user) for user in analyst_store.list_users()]}

    @app.post("/api/admin/users", status_code=201)
    async def admin_create_user(request: Request, payload: UserCreateRequest):
        require_admin_user(request)
        email = payload.email.strip().lower()
        password = payload.password
        role = payload.role.strip()
        display_name = payload.display_name.strip()
        if not email or not password:
            raise HTTPException(status_code=400, detail="email and password are required")
        if not is_valid_email(email):
            raise HTTPException(status_code=400, detail="valid email is required")
        if role not in VALID_USER_ROLES:
            raise HTTPException(status_code=400, detail="unsupported user role")
        try:
            analyst_store.get_user_by_email(email)
        except KeyError:
            pass
        else:
            raise HTTPException(status_code=400, detail="email already exists")
        try:
            user = analyst_store.create_user(
                email=email,
                display_name=display_name,
                role=role,
                password_hash=hash_password(password),
                created_by=(request.state.current_user or {}).get("email", "admin"),
            )
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        return {"user": public_user_dict(user)}

    @app.post("/api/admin/users/{user_id}/deactivate")
    async def admin_deactivate_user(user_id: int, request: Request):
        require_admin_user(request)
        try:
            user = analyst_store.set_user_active(
                user_id,
                False,
                updated_by=(request.state.current_user or {}).get("email", "admin"),
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return {"user": public_user_dict(user)}

    @app.get("/api/admin/projects/{project_id}/external-access")
    async def admin_list_project_external_access(project_id: int, request: Request):
        require_admin_user(request)
        try:
            assignments = analyst_store.list_project_external_access(project_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return {"external_access": assignments}

    @app.put("/api/admin/projects/{project_id}/external-access/{user_id}")
    async def admin_set_project_external_access(
        project_id: int,
        user_id: int,
        request: Request,
        payload: ExternalProjectAccessRequest,
    ):
        require_admin_user(request)
        try:
            assignment = analyst_store.set_external_project_access(
                project_id=project_id,
                user_id=user_id,
                portal_view=payload.portal_view,
                operate=payload.operate,
                updated_by=(request.state.current_user or {}).get("email", "admin"),
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        return {"external_access": assignment}

    @app.delete("/api/admin/projects/{project_id}/external-access/{user_id}")
    async def admin_remove_project_external_access(
        project_id: int,
        user_id: int,
        request: Request,
    ):
        require_admin_user(request)
        try:
            assignment = analyst_store.revoke_external_project_access(
                project_id=project_id,
                user_id=user_id,
                updated_by=(request.state.current_user or {}).get("email", "admin"),
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return {"external_access": assignment}

    def portal_configuration_response_body(project_id: int) -> dict[str, Any]:
        configuration = analyst_store.get_portal_configuration(project_id)
        if configuration is None:
            return {
                "project_id": project_id,
                "status": "draft",
                "document": default_portal_config_document(),
                "revision": 0,
                "has_logo": False,
                "updated_at": None,
                "updated_by": None,
            }
        return {
            "project_id": configuration["project_id"],
            "status": configuration["status"],
            "document": configuration["document"],
            "revision": configuration["revision"],
            "has_logo": configuration["logo_bytes"] is not None,
            "updated_at": configuration["updated_at"],
            "updated_by": portal_configuration_editor_email(
                configuration["updated_by_user_id"]
            ),
        }

    def portal_configuration_editor_email(user_id: int | None) -> str | None:
        if user_id is None:
            return None
        try:
            return str(analyst_store.get_user(int(user_id))["email"])
        except KeyError:
            return None

    @app.get("/api/portal-catalogs")
    async def get_portal_catalogs():
        return portal_catalogs()

    @app.get("/api/time-series/signal-catalog")
    async def get_signal_catalog():
        """Expose the DB-backed legacy signal adapter to internal surfaces."""

        return {"signals": analyst_store.signal_catalog_entries()}

    @app.get("/api/time-series/catalog/inputs")
    async def get_global_time_series_catalog_inputs(
        request: Request,
        limit: int = 50,
        order: str | None = None,
        cursor: str | None = None,
    ):
        """List canonical input signals; never sets, results or legacy rows."""

        user = request.state.current_user or {}
        role = user.get("role", "analyst")
        actor_class = f"{role}:{user.get('id', 'auth-disabled')}"
        request_id = request.headers.get("x-request-id") or f"req_{secrets.token_hex(8)}"
        try:
            filters = parse_input_filters(request.query_params)
            page = analyst_store.read_catalog_page(
                limit=limit,
                order=order,
                cursor=cursor,
                include_total=True,
                filters=filters,
                actor_class=actor_class,
            )
        except CatalogQueryError as error:
            status_code = 410 if error.code == "TS_QUERY_CURSOR_EXPIRED" else 400
            if error.code == "TS_QUERY_SNAPSHOT_CHANGED":
                status_code = 409
            return JSONResponse(
                catalog_error_payload(error, request_id=request_id),
                status_code=status_code,
                headers={"Cache-Control": "private, no-store"},
            )
        page["items"] = [
            input_list_item(item, actor_role=role) for item in page["items"]
        ]
        if "context_linkable_object_id" in filters:
            for item in page["items"]:
                item["compatibility_decision"] = (
                    analyst_store.evaluate_catalog_signal_for_object(
                        signal_id=item["signal_id"],
                        linkable_object_id=filters["context_linkable_object_id"],
                        binding_role_key=filters["context_binding_role_key"],
                        usage=filters["context_usage"],
                    )
                )
        page["meta"]["request_id"] = request_id
        return JSONResponse(
            page,
            headers={"Cache-Control": "private, must-revalidate"},
        )

    @app.get("/api/time-series/catalog/inputs/{signal_id}")
    async def get_global_time_series_catalog_input(signal_id: int, request: Request):
        user = request.state.current_user or {}
        actor_class = f"{user.get('role', 'analyst')}:{user.get('id', 'auth-disabled')}"
        request_id = request.headers.get("x-request-id") or f"req_{secrets.token_hex(8)}"
        try:
            detail = analyst_store.read_catalog_input_detail(signal_id)
        except KeyError:
            error = CatalogQueryError("TS_CATALOG_SIGNAL_NOT_FOUND")
            return JSONResponse(
                catalog_error_payload(error, request_id=request_id),
                status_code=404,
                headers={"Cache-Control": "private, no-store"},
            )
        active = (
            detail["identity"]["status"] != "archived"
            and detail["set"]["status"] != "archived"
        )
        may_edit = active and (
            detail["set"]["visibility_scope"] == "project"
            or user.get("role") == "admin"
        )
        detail["capabilities"] = {
            "view_detail": True,
            "preview": True,
            "associate": active,
            "bind": active,
            "edit_set": may_edit,
            "publish_revision": may_edit,
        }
        detail["links"] = {
            "revisions": f"/api/time-series/catalog/inputs/{signal_id}/revisions",
            "preview": f"/api/time-series/catalog/inputs/{signal_id}/preview",
            "object_candidates": (
                f"/api/time-series/catalog/inputs/{signal_id}/object-candidates"
            ),
        }
        etag = catalog_detail_etag(detail, actor_class=actor_class)
        if request.headers.get("if-none-match") == etag:
            return Response(
                status_code=304,
                headers={"ETag": etag, "Cache-Control": "private, must-revalidate"},
            )
        detail["request_id"] = request_id
        return JSONResponse(
            detail,
            headers={"ETag": etag, "Cache-Control": "private, must-revalidate"},
        )

    @app.get("/api/time-series/catalog/inputs/{signal_id}/revisions")
    async def get_global_time_series_catalog_input_revisions(
        signal_id: int,
        request: Request,
        limit: int = 50,
        cursor: str | None = None,
    ):
        user = request.state.current_user or {}
        actor_class = f"{user.get('role', 'analyst')}:{user.get('id', 'auth-disabled')}"
        request_id = request.headers.get("x-request-id") or f"req_{secrets.token_hex(8)}"
        try:
            page = analyst_store.read_catalog_input_revisions(
                signal_id,
                limit=limit,
                cursor=cursor,
                actor_class=actor_class,
            )
        except KeyError:
            error = CatalogQueryError("TS_CATALOG_SIGNAL_NOT_FOUND")
            return JSONResponse(
                catalog_error_payload(error, request_id=request_id),
                status_code=404,
                headers={"Cache-Control": "private, no-store"},
            )
        except CatalogQueryError as error:
            status_code = 410 if error.code == "TS_QUERY_CURSOR_EXPIRED" else 400
            if error.code == "TS_QUERY_SNAPSHOT_CHANGED":
                status_code = 409
            return JSONResponse(
                catalog_error_payload(error, request_id=request_id),
                status_code=status_code,
                headers={"Cache-Control": "private, no-store"},
            )
        page["meta"]["request_id"] = request_id
        return JSONResponse(
            page,
            headers={"Cache-Control": "private, must-revalidate"},
        )

    @app.get("/api/time-series/catalog/inputs/{signal_id}/preview")
    async def get_global_time_series_catalog_input_preview(
        signal_id: int, request: Request
    ):
        request_id = request.headers.get("x-request-id") or f"req_{secrets.token_hex(8)}"
        try:
            query = parse_preview_query(request.query_params)
            preview = analyst_store.read_catalog_input_preview(signal_id, **query)
        except KeyError:
            error = CatalogQueryError("TS_CATALOG_SIGNAL_NOT_FOUND")
            return JSONResponse(
                catalog_error_payload(error, request_id=request_id),
                status_code=404,
                headers={"Cache-Control": "private, no-store"},
            )
        except CatalogQueryError as error:
            status_code = 422 if error.code == "TS_PREVIEW_TOO_LARGE" else 400
            return JSONResponse(
                catalog_error_payload(error, request_id=request_id),
                status_code=status_code,
                headers={"Cache-Control": "private, no-store"},
            )
        etag = catalog_preview_etag(preview)
        preview["request_id"] = request_id
        return JSONResponse(
            preview,
            headers={"ETag": etag, "Cache-Control": "private, no-store"},
        )

    @app.get("/api/time-series/catalog/descriptors")
    async def get_global_time_series_catalog_descriptors(
        request: Request,
        kind: str,
        limit: int = 50,
        cursor: str | None = None,
        q: str = "",
    ):
        user = request.state.current_user or {}
        actor_class = f"{user.get('role', 'analyst')}:{user.get('id', 'auth-disabled')}"
        request_id = request.headers.get("x-request-id") or f"req_{secrets.token_hex(8)}"
        try:
            page = analyst_store.read_catalog_descriptors(
                kind=kind,
                limit=limit,
                cursor=cursor,
                q=q,
                statuses=request.query_params.getlist("status") or None,
                actor_class=actor_class,
            )
        except CatalogQueryError as error:
            status_code = 410 if error.code == "TS_QUERY_CURSOR_EXPIRED" else 400
            return JSONResponse(
                catalog_error_payload(error, request_id=request_id),
                status_code=status_code,
                headers={"Cache-Control": "private, no-store"},
            )
        page["meta"]["request_id"] = request_id
        return JSONResponse(
            page,
            headers={"Cache-Control": "private, must-revalidate"},
        )

    @app.get("/api/time-series/catalog/inputs/{signal_id}/object-candidates")
    async def get_global_time_series_catalog_object_candidates(
        signal_id: int,
        request: Request,
        target_project_id: int,
        binding_role_key: str,
        usage: str,
        include_denied: bool = False,
        q: str = "",
        limit: int = 50,
        cursor: str | None = None,
    ):
        user = request.state.current_user or {}
        actor_class = f"{user.get('role', 'analyst')}:{user.get('id', 'auth-disabled')}"
        request_id = request.headers.get("x-request-id") or f"req_{secrets.token_hex(8)}"
        try:
            context_scenario_id = None
            context_variant_id = None
            if usage == "execution":
                raw_scenario_id = request.query_params.get("context_scenario_id")
                raw_variant_id = request.query_params.get("context_variant_id")
                if raw_scenario_id is None or raw_variant_id is None:
                    raise CatalogQueryError(
                        "TS_QUERY_INVALID",
                        field="context_scenario_id",
                        reason="execution_context_required",
                    )
                try:
                    context_scenario_id = int(raw_scenario_id)
                    context_variant_id = int(raw_variant_id)
                except ValueError as error:
                    raise CatalogQueryError(
                        "TS_QUERY_INVALID", field="context_scenario_id"
                    ) from error
            page = analyst_store.read_catalog_object_candidates(
                signal_id,
                target_project_id=target_project_id,
                binding_role_key=binding_role_key,
                usage=usage,
                context_scenario_id=context_scenario_id,
                context_variant_id=context_variant_id,
                include_denied=include_denied,
                object_type_keys=request.query_params.getlist("object_type_key"),
                q=q,
                limit=limit,
                cursor=cursor,
                actor_class=actor_class,
            )
        except KeyError:
            error = CatalogQueryError("TS_CATALOG_SIGNAL_NOT_FOUND")
            return JSONResponse(
                catalog_error_payload(error, request_id=request_id),
                status_code=404,
                headers={"Cache-Control": "private, no-store"},
            )
        except CatalogQueryError as error:
            status_code = 410 if error.code == "TS_QUERY_CURSOR_EXPIRED" else 400
            return JSONResponse(
                catalog_error_payload(error, request_id=request_id),
                status_code=status_code,
                headers={"Cache-Control": "private, no-store"},
            )
        page["meta"]["request_id"] = request_id
        return JSONResponse(
            page,
            headers={"Cache-Control": "private, must-revalidate"},
        )

    @app.get("/api/time-series/catalog/associations")
    async def get_global_time_series_catalog_associations(
        request: Request, limit: int = 50, cursor: str | None = None
    ):
        user = request.state.current_user or {}
        actor_class = f"{user.get('role', 'analyst')}:{user.get('id', 'auth-disabled')}"
        request_id = request.headers.get("x-request-id") or f"req_{secrets.token_hex(8)}"
        try:
            page = analyst_store.read_catalog_associations(
                limit=limit, cursor=cursor, actor_class=actor_class
            )
        except CatalogQueryError as error:
            return JSONResponse(
                catalog_error_payload(error, request_id=request_id),
                status_code=410 if error.code == "TS_QUERY_CURSOR_EXPIRED" else 400,
                headers={"Cache-Control": "private, no-store"},
            )
        page["meta"]["request_id"] = request_id
        return JSONResponse(
            page,
            headers={"Cache-Control": "private, must-revalidate"},
        )

    @app.get("/api/time-series/catalog/associations/{association_id}")
    async def get_global_time_series_catalog_association(
        association_id: int, request: Request
    ):
        user = request.state.current_user or {}
        actor_class = f"{user.get('role', 'analyst')}:{user.get('id', 'auth-disabled')}"
        request_id = request.headers.get("x-request-id") or f"req_{secrets.token_hex(8)}"
        try:
            detail = analyst_store.read_catalog_association(association_id)
        except KeyError:
            return JSONResponse(
                {"detail": "not found"},
                status_code=404,
                headers={"Cache-Control": "private, no-store"},
            )
        etag = association_detail_etag(detail, actor_class=actor_class)
        if request.headers.get("if-none-match") == etag:
            return Response(
                status_code=304,
                headers={"ETag": etag, "Cache-Control": "private, must-revalidate"},
            )
        detail["request_id"] = request_id
        return JSONResponse(
            detail,
            headers={"ETag": etag, "Cache-Control": "private, must-revalidate"},
        )

    @app.get("/api/time-series/catalog/associations/{association_id}/events")
    async def get_global_time_series_catalog_association_events(
        association_id: int,
        request: Request,
        limit: int = 50,
        cursor: str | None = None,
    ):
        user = request.state.current_user or {}
        actor_class = f"{user.get('role', 'analyst')}:{user.get('id', 'auth-disabled')}"
        request_id = request.headers.get("x-request-id") or f"req_{secrets.token_hex(8)}"
        try:
            page = analyst_store.read_catalog_association_events(
                association_id,
                limit=limit,
                cursor=cursor,
                actor_class=actor_class,
            )
        except KeyError:
            return JSONResponse(
                {"detail": "not found"},
                status_code=404,
                headers={"Cache-Control": "private, no-store"},
            )
        except CatalogQueryError as error:
            return JSONResponse(
                catalog_error_payload(error, request_id=request_id),
                status_code=410 if error.code == "TS_QUERY_CURSOR_EXPIRED" else 400,
                headers={"Cache-Control": "private, no-store"},
            )
        page["meta"]["request_id"] = request_id
        return JSONResponse(
            page,
            headers={"Cache-Control": "private, must-revalidate"},
        )

    @app.post(
        "/api/time-series/catalog/association-prevalidations",
        responses={400: {"description": "Stable payload refusal"}},
    )
    async def prevalidate_global_time_series_catalog_associations(
        payload: CatalogAssociationPrevalidationRequest, request: Request
    ):
        user = request.state.current_user or {}
        actor_class = f"{user.get('role', 'analyst')}:{user.get('id', 'auth-disabled')}"
        request_id = request.headers.get("x-request-id") or f"req_{secrets.token_hex(8)}"
        try:
            document = payload.model_dump(exclude_none=True)
            result = analyst_store.prevalidate_catalog_association_batch(
                document, actor_class=actor_class
            )
        except (AssociationMutationError, ValueError, TypeError) as error:
            if not isinstance(error, AssociationMutationError):
                error = AssociationMutationError(
                    "TS_LINK_PAYLOAD_INVALID", field="body"
                )
            return JSONResponse(
                association_error_payload(error, request_id=request_id),
                status_code=400,
                headers={"Cache-Control": "private, no-store"},
            )
        except KeyError:
            error = AssociationMutationError(
                "TS_LINK_PAYLOAD_INVALID", field="target_project_id"
            )
            return JSONResponse(
                association_error_payload(error, request_id=request_id),
                status_code=404,
                headers={"Cache-Control": "private, no-store"},
            )
        result["request_id"] = request_id
        return JSONResponse(
            result,
            headers={"Cache-Control": "private, no-store"},
        )

    @app.post(
        "/api/time-series/catalog/association-batches",
        responses={
            201: {"description": "Association batch created"},
            400: {"description": "Stable payload refusal"},
            409: {"description": "Confirmation or idempotency conflict"},
            410: {"description": "Prevalidation expired"},
            412: {"description": "Observed precondition changed"},
            422: {"description": "Domain batch rejection"},
            428: {"description": "Required commit guard missing"},
        },
    )
    async def commit_global_time_series_catalog_associations(
        payload: CatalogAssociationCommitRequest,
        request: Request,
        if_match: str = Header(alias="If-Match"),
        idempotency_key: str = Header(alias="Idempotency-Key"),
    ):
        user = request.state.current_user or {
            "id": None,
            "email": "internal_analyst",
            "role": "analyst",
        }
        actor_class = f"{user.get('role', 'analyst')}:{user.get('id', 'auth-disabled')}"
        request_id = request.headers.get("x-request-id") or f"req_{secrets.token_hex(8)}"
        document = payload.model_dump(
            exclude={"prevalidation_token", "confirmed"}, exclude_none=True
        )
        try:
            token = payload.prevalidation_token.strip()
            if_match = str(if_match or "").strip()
            idempotency_key = str(idempotency_key or "").strip()
            if not token or not if_match or not idempotency_key:
                missing = (
                    "prevalidation_token"
                    if not token
                    else "If-Match"
                    if not if_match
                    else "Idempotency-Key"
                )
                raise AssociationMutationError(
                    "TS_PRECONDITION_REQUIRED", field=missing
                )
            result, replayed = analyst_store.commit_catalog_association_batch(
                document,
                actor_user=user,
                actor_class=actor_class,
                request_id=request_id,
                prevalidation_token=token,
                if_match=if_match,
                idempotency_key=idempotency_key,
                confirmed=payload.confirmed,
            )
        except (AssociationMutationError, ValueError, TypeError) as error:
            if not isinstance(error, AssociationMutationError):
                error = AssociationMutationError(
                    "TS_LINK_PAYLOAD_INVALID", field="body"
                )
            error.context.setdefault("normalized_request", document)
            status_by_code = {
                "TS_PRECONDITION_REQUIRED": 428,
                "TS_LINK_PREVALIDATION_EXPIRED": 410,
                "TS_LINK_PRECONDITION_CHANGED": 412,
                "TS_COMPAT_SCOPE_NOT_ACCESSIBLE": 412,
                "TS_LINK_BATCH_REJECTED": 422,
                "TS_LINK_CONFLICT": 409,
                "TS_LINK_CONFIRMATION_REQUIRED": 409,
                "TS_IDEMPOTENCY_CONFLICT": 409,
            }
            return JSONResponse(
                association_error_payload(error, request_id=request_id),
                status_code=status_by_code.get(error.code, 400),
                headers={"Cache-Control": "private, no-store"},
            )
        return JSONResponse(
            result,
            status_code=(
                200 if replayed or result.get("outcome") == "unchanged" else 201
            ),
            headers={"Cache-Control": "private, no-store"},
        )

    @app.get(
        "/api/scenarios/{scenario_id}/case-variants/{variant_id}/time-series-bindings"
    )
    async def get_case_time_series_bindings(
        scenario_id: int, variant_id: int, request: Request
    ):
        request_id = request.headers.get("x-request-id") or f"req_{secrets.token_hex(8)}"
        try:
            page = analyst_store.read_case_bindings(
                scenario_id=scenario_id, variant_id=variant_id
            )
        except KeyError:
            return JSONResponse(
                {"detail": "not found"},
                status_code=404,
                headers={"Cache-Control": "private, no-store"},
            )
        page["meta"]["request_id"] = request_id
        return JSONResponse(
            page, headers={"Cache-Control": "private, must-revalidate"}
        )

    @app.get(
        "/api/scenarios/{scenario_id}/case-variants/{variant_id}/time-series-bindings/{binding_id}"
    )
    async def get_case_time_series_binding(
        scenario_id: int, variant_id: int, binding_id: int, request: Request
    ):
        user = request.state.current_user or {}
        actor_class = f"{user.get('role', 'analyst')}:{user.get('id', 'auth-disabled')}"
        request_id = request.headers.get("x-request-id") or f"req_{secrets.token_hex(8)}"
        try:
            detail = analyst_store.read_case_binding(
                scenario_id=scenario_id,
                variant_id=variant_id,
                binding_id=binding_id,
            )
        except KeyError:
            return JSONResponse(
                {"detail": "not found"},
                status_code=404,
                headers={"Cache-Control": "private, no-store"},
            )
        etag = binding_detail_etag(detail, actor_class=actor_class)
        if request.headers.get("if-none-match") == etag:
            return Response(
                status_code=304,
                headers={"ETag": etag, "Cache-Control": "private, must-revalidate"},
            )
        detail["request_id"] = request_id
        return JSONResponse(
            detail,
            headers={"ETag": etag, "Cache-Control": "private, must-revalidate"},
        )

    @app.get(
        "/api/scenarios/{scenario_id}/case-variants/{variant_id}/time-series-bindings/{binding_id}/events"
    )
    async def get_case_time_series_binding_events(
        scenario_id: int,
        variant_id: int,
        binding_id: int,
        request: Request,
        limit: int = 50,
        cursor: str | None = None,
    ):
        user = request.state.current_user or {}
        actor_class = f"{user.get('role', 'analyst')}:{user.get('id', 'auth-disabled')}"
        request_id = request.headers.get("x-request-id") or f"req_{secrets.token_hex(8)}"
        try:
            page = analyst_store.read_case_binding_events(
                scenario_id=scenario_id,
                variant_id=variant_id,
                binding_id=binding_id,
                limit=limit,
                cursor=cursor,
                actor_class=actor_class,
            )
        except KeyError:
            return JSONResponse(
                {"detail": "not found"},
                status_code=404,
                headers={"Cache-Control": "private, no-store"},
            )
        except CatalogQueryError as error:
            return JSONResponse(
                catalog_error_payload(error, request_id=request_id),
                status_code=410 if error.code == "TS_QUERY_CURSOR_EXPIRED" else 400,
                headers={"Cache-Control": "private, no-store"},
            )
        page["meta"]["request_id"] = request_id
        return JSONResponse(
            page, headers={"Cache-Control": "private, must-revalidate"}
        )

    @app.post(
        "/api/scenarios/{scenario_id}/case-variants/{variant_id}/time-series-binding-prevalidations"
    )
    async def prevalidate_case_time_series_bindings(
        scenario_id: int,
        variant_id: int,
        payload: CaseBindingPrevalidationRequest,
        request: Request,
    ):
        user = request.state.current_user or {}
        actor_class = f"{user.get('role', 'analyst')}:{user.get('id', 'auth-disabled')}"
        request_id = request.headers.get("x-request-id") or f"req_{secrets.token_hex(8)}"
        try:
            result = analyst_store.prevalidate_case_binding_batch(
                scenario_id=scenario_id,
                variant_id=variant_id,
                document=payload.model_dump(exclude_none=False),
                actor_class=actor_class,
            )
        except BindingMutationError as error:
            return JSONResponse(
                binding_error_payload(error, request_id=request_id),
                status_code=400,
                headers={"Cache-Control": "private, no-store"},
            )
        except KeyError:
            return JSONResponse(
                {"detail": "not found"},
                status_code=404,
                headers={"Cache-Control": "private, no-store"},
            )
        result["request_id"] = request_id
        return JSONResponse(result, headers={"Cache-Control": "private, no-store"})

    @app.post(
        "/api/scenarios/{scenario_id}/case-variants/{variant_id}/time-series-binding-batches",
        responses={
            201: {"description": "Binding batch created"},
            409: {"description": "Confirmation or idempotency conflict"},
            410: {"description": "Prevalidation expired"},
            412: {"description": "Observed precondition changed"},
            422: {"description": "Domain batch rejection"},
            428: {"description": "Required commit guard missing"},
        },
    )
    async def commit_case_time_series_bindings(
        scenario_id: int,
        variant_id: int,
        payload: CaseBindingCommitRequest,
        request: Request,
        if_match: str = Header(alias="If-Match"),
        idempotency_key: str = Header(alias="Idempotency-Key"),
    ):
        user = request.state.current_user or {
            "id": None,
            "email": "internal_analyst",
            "role": "analyst",
        }
        actor_class = f"{user.get('role', 'analyst')}:{user.get('id', 'auth-disabled')}"
        request_id = request.headers.get("x-request-id") or f"req_{secrets.token_hex(8)}"
        document = payload.model_dump(
            exclude={"prevalidation_token", "confirmed"}, exclude_none=False
        )
        try:
            token = payload.prevalidation_token.strip()
            if_match = str(if_match or "").strip()
            idempotency_key = str(idempotency_key or "").strip()
            if not token or not if_match or not idempotency_key:
                missing = (
                    "prevalidation_token"
                    if not token
                    else "If-Match"
                    if not if_match
                    else "Idempotency-Key"
                )
                raise BindingMutationError(
                    "TS_PRECONDITION_REQUIRED", field=missing
                )
            result, replayed = analyst_store.commit_case_binding_batch(
                scenario_id=scenario_id,
                variant_id=variant_id,
                document=document,
                actor_user=user,
                actor_class=actor_class,
                request_id=request_id,
                prevalidation_token=token,
                if_match=if_match,
                idempotency_key=idempotency_key,
                confirmed=payload.confirmed,
            )
        except BindingMutationError as error:
            error.context.setdefault("normalized_request", document)
            status_by_code = {
                "TS_PRECONDITION_REQUIRED": 428,
                "TS_LINK_PREVALIDATION_EXPIRED": 410,
                "TS_LINK_PRECONDITION_CHANGED": 412,
                "TS_LINK_BATCH_REJECTED": 422,
                "TS_LINK_CONFLICT": 409,
                "TS_LINK_CONFIRMATION_REQUIRED": 409,
                "TS_IDEMPOTENCY_CONFLICT": 409,
            }
            return JSONResponse(
                binding_error_payload(error, request_id=request_id),
                status_code=status_by_code.get(error.code, 400),
                headers={"Cache-Control": "private, no-store"},
            )
        except KeyError:
            return JSONResponse(
                {"detail": "not found"},
                status_code=404,
                headers={"Cache-Control": "private, no-store"},
            )
        return JSONResponse(
            result,
            status_code=200 if replayed else 201,
            headers={"Cache-Control": "private, no-store"},
        )

    @app.get("/api/time-series/catalog/results")
    async def get_global_time_series_catalog_results(
        request: Request, limit: int = 50, cursor: str | None = None
    ):
        request_id = request.headers.get("x-request-id") or f"req_{secrets.token_hex(8)}"
        user = request.state.current_user or {}
        actor_class = f"{user.get('role', 'analyst')}:{user.get('id', 'auth-disabled')}"
        try:
            filters = parse_result_filters(request.query_params)
            page = analyst_store.list_catalog_results(
                limit=limit,
                cursor=cursor,
                actor_class=actor_class,
                filters=filters,
            )
        except CatalogQueryError as error:
            status_code = 410 if error.code == "TS_QUERY_CURSOR_EXPIRED" else 400
            if error.code == "TS_QUERY_SNAPSHOT_CHANGED":
                status_code = 409
            return JSONResponse(
                catalog_error_payload(error, request_id=request_id),
                status_code=status_code,
                headers={"Cache-Control": "private, no-store"},
            )
        page["meta"]["request_id"] = request_id
        return JSONResponse(
            page, headers={"Cache-Control": "private, must-revalidate"}
        )

    @app.get("/api/time-series/catalog/results/{result_series_id}")
    async def get_global_time_series_catalog_result_detail(
        result_series_id: str, request: Request
    ):
        request_id = request.headers.get("x-request-id") or f"req_{secrets.token_hex(8)}"
        try:
            detail = analyst_store.read_catalog_result_detail(result_series_id)
        except KeyError:
            error = CatalogQueryError("TS_CATALOG_RESULT_NOT_FOUND")
            return JSONResponse(
                catalog_error_payload(error, request_id=request_id),
                status_code=404,
                headers={"Cache-Control": "private, no-store"},
            )
        detail["request_id"] = request_id
        return JSONResponse(
            detail, headers={"Cache-Control": "private, must-revalidate"}
        )

    @app.get("/api/time-series/catalog/results/{result_series_id}/preview")
    async def get_global_time_series_catalog_result_preview(
        result_series_id: str, request: Request
    ):
        request_id = request.headers.get("x-request-id") or f"req_{secrets.token_hex(8)}"
        try:
            query = parse_legacy_preview_query(request.query_params)
            preview = analyst_store.read_catalog_result_preview(result_series_id, **query)
        except KeyError:
            error = CatalogQueryError("TS_CATALOG_RESULT_NOT_FOUND")
            return JSONResponse(
                catalog_error_payload(error, request_id=request_id),
                status_code=404,
                headers={"Cache-Control": "private, no-store"},
            )
        except CatalogQueryError as error:
            status_code = 422 if error.code == "TS_PREVIEW_TOO_LARGE" else 400
            return JSONResponse(
                catalog_error_payload(error, request_id=request_id),
                status_code=status_code,
                headers={"Cache-Control": "private, no-store"},
            )
        preview["request_id"] = request_id
        return JSONResponse(
            preview, headers={"Cache-Control": "private, no-store"}
        )

    @app.get("/api/time-series/catalog/legacy")
    async def get_global_time_series_catalog_legacy(
        request: Request, limit: int = 50, cursor: str | None = None
    ):
        request_id = request.headers.get("x-request-id") or f"req_{secrets.token_hex(8)}"
        user = request.state.current_user or {}
        actor_class = f"{user.get('role', 'analyst')}:{user.get('id', 'auth-disabled')}"
        try:
            page = analyst_store.list_catalog_legacy(
                limit=limit, cursor=cursor, actor_class=actor_class
            )
        except CatalogQueryError as error:
            status_code = 410 if error.code == "TS_QUERY_CURSOR_EXPIRED" else 400
            return JSONResponse(
                catalog_error_payload(error, request_id=request_id),
                status_code=status_code,
                headers={"Cache-Control": "private, no-store"},
            )
        page["meta"]["request_id"] = request_id
        return JSONResponse(
            page, headers={"Cache-Control": "private, must-revalidate"}
        )

    @app.get("/api/time-series/catalog/legacy/{legacy_entry_ref}")
    async def get_global_time_series_catalog_legacy_detail(
        legacy_entry_ref: str, request: Request
    ):
        request_id = request.headers.get("x-request-id") or f"req_{secrets.token_hex(8)}"
        try:
            detail = analyst_store.read_catalog_legacy_detail(legacy_entry_ref)
        except KeyError:
            error = CatalogQueryError("TS_CATALOG_LEGACY_NOT_FOUND")
            return JSONResponse(
                catalog_error_payload(error, request_id=request_id),
                status_code=404,
                headers={"Cache-Control": "private, no-store"},
            )
        detail["request_id"] = request_id
        return JSONResponse(
            detail, headers={"Cache-Control": "private, must-revalidate"}
        )

    @app.get("/api/time-series/catalog/legacy/{legacy_entry_ref}/preview")
    async def get_global_time_series_catalog_legacy_preview(
        legacy_entry_ref: str, request: Request
    ):
        request_id = request.headers.get("x-request-id") or f"req_{secrets.token_hex(8)}"
        try:
            query = parse_legacy_preview_query(request.query_params)
            preview = analyst_store.read_catalog_legacy_preview(
                legacy_entry_ref, **query
            )
        except KeyError:
            error = CatalogQueryError("TS_CATALOG_LEGACY_NOT_FOUND")
            return JSONResponse(
                catalog_error_payload(error, request_id=request_id),
                status_code=404,
                headers={"Cache-Control": "private, no-store"},
            )
        except CatalogQueryError as error:
            status_code = 422 if error.code == "TS_PREVIEW_TOO_LARGE" else 400
            return JSONResponse(
                catalog_error_payload(error, request_id=request_id),
                status_code=status_code,
                headers={"Cache-Control": "private, no-store"},
            )
        preview["request_id"] = request_id
        return JSONResponse(
            preview, headers={"Cache-Control": "private, no-store"}
        )

    @app.post("/api/admin/time-series/semantic-types", status_code=201)
    async def admin_create_custom_time_series_semantic_type(
        request: Request,
        payload: CustomSemanticTypeCreateRequest,
    ):
        require_admin_user(request)
        try:
            semantic_type = analyst_store.create_custom_time_series_semantic_type(
                semantic_key=payload.semantic_key,
                display_name=payload.display_name,
                description=payload.description,
                dimension_key=payload.dimension_key,
                canonical_unit_key=payload.canonical_unit_key,
                value_kind=payload.value_kind,
                default_aggregation=payload.default_aggregation,
                validation_rules=payload.validation_rules,
                created_by=(request.state.current_user or {}).get(
                    "email", "internal_admin"
                ),
            )
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        return {"semantic_type": semantic_type}

    # -- Path B: object-specific series (TS7-010, chapter 7) ----------------
    #
    # The canonical root is the normalized object. Every handler resolves the
    # register row and its project first, and refuses before it looks at a
    # signal id, an ingestion id or the payload.

    OBJECT_ROOT = (
        "/api/projects/{project_id}/linkable-objects/{linkable_object_id}/time-series"
    )

    def object_series_actor(request: Request) -> str:
        user = request.state.current_user or {}
        return str(user.get("email") or "internal_analyst")

    def object_series_refusal(
        error: ObjectSeriesError, request: Request
    ) -> JSONResponse:
        request_id = request.headers.get("x-request-id") or f"req_{secrets.token_hex(8)}"
        return JSONResponse(
            object_series_problem(error, request_id=request_id),
            status_code=error.status,
            media_type="application/problem+json",
            headers={"Cache-Control": "private, no-store"},
        )

    def object_series_links(
        project_id: int, linkable_object_id: int, signal_id: int
    ) -> dict[str, str]:
        target = (
            f"/api/projects/{project_id}/linkable-objects/{linkable_object_id}"
            f"/time-series/object-series/{signal_id}"
        )
        return {
            "detail": target,
            "revisions": f"{target}/revisions",
            "preview": f"{target}/preview",
            "archive": f"{target}/archive",
            "point_ingestions": f"{target}/revision-ingestions/points",
            "file_ingestions": f"{target}/revision-ingestions/files",
        }

    def object_series_response(
        series: dict[str, Any],
        *,
        project_id: int,
        linkable_object_id: int,
        request_id: str,
        status_code: int = 200,
    ) -> JSONResponse:
        etag = object_series_etag(
            signal_id=series["signal_id"],
            resource_version=series["resource_version"],
        )
        body = {
            "object_series": series,
            "capabilities": {
                "edit_definition": series["availability"] not in {"archived", "owner_archived"},
                "ingest_points": series["availability"]
                in {"awaiting_data", "ready"},
                "preview": series["current_revision"] is not None,
                "bind": series["binding_ready"],
                "archive": series["availability"]
                not in {"archived", "owner_archived"},
            },
            "links": object_series_links(
                project_id, linkable_object_id, series["signal_id"]
            ),
            "request_id": request_id,
        }
        return JSONResponse(
            body,
            status_code=status_code,
            headers={"ETag": etag, "Cache-Control": "private, must-revalidate"},
        )

    @app.get(OBJECT_ROOT)
    async def get_object_time_series_context(
        project_id: int,
        linkable_object_id: int,
        request: Request,
        limit: int = 50,
        cursor: str | None = None,
    ):
        """Generic associations and local series in one paged read model."""

        user = request.state.current_user or {}
        actor_class = f"{user.get('role', 'analyst')}:{user.get('id', 'auth-disabled')}"
        request_id = request.headers.get("x-request-id") or f"req_{secrets.token_hex(8)}"
        try:
            page = analyst_store.read_object_time_series_context(
                project_id=project_id,
                linkable_object_id=linkable_object_id,
                limit=limit,
                cursor=cursor,
                filters=parse_object_context_filters(request.query_params),
                actor_class=actor_class,
            )
        except ObjectSeriesError as error:
            return object_series_refusal(error, request)
        except CatalogQueryError as error:
            status_code = 410 if error.code == "TS_QUERY_CURSOR_EXPIRED" else 400
            return JSONResponse(
                catalog_error_payload(error, request_id=request_id),
                status_code=status_code,
                headers={"Cache-Control": "private, no-store"},
            )
        page["meta"]["request_id"] = request_id
        return JSONResponse(
            page, headers={"Cache-Control": "private, must-revalidate"}
        )

    @app.post(f"{OBJECT_ROOT}/object-series", status_code=201)
    async def create_object_specific_time_series(
        project_id: int,
        linkable_object_id: int,
        payload: ObjectSeriesCreateRequest,
        request: Request,
        idempotency_key: str = Header(alias="Idempotency-Key"),
    ):
        request_id = request.headers.get("x-request-id") or f"req_{secrets.token_hex(8)}"
        try:
            if not str(idempotency_key or "").strip():
                raise ObjectSeriesError(
                    "TS_INGEST_PRECONDITION_REQUIRED", field="Idempotency-Key"
                )
            series = analyst_store.create_object_series_definition(
                project_id=project_id,
                linkable_object_id=linkable_object_id,
                document=payload.model_dump(exclude_none=True),
                actor=object_series_actor(request),
            )
        except ObjectSeriesError as error:
            return object_series_refusal(error, request)
        return object_series_response(
            series,
            project_id=project_id,
            linkable_object_id=linkable_object_id,
            request_id=request_id,
            status_code=201,
        )

    @app.patch(f"{OBJECT_ROOT}/object-series/{{signal_id}}")
    async def patch_object_specific_time_series(
        project_id: int,
        linkable_object_id: int,
        signal_id: int,
        payload: ObjectSeriesPatchRequest,
        request: Request,
        if_match: str | None = Header(default=None, alias="If-Match"),
    ):
        request_id = request.headers.get("x-request-id") or f"req_{secrets.token_hex(8)}"
        try:
            if not str(if_match or "").strip():
                raise ObjectSeriesError(
                    "TS_INGEST_PRECONDITION_REQUIRED", field="If-Match"
                )
            series = analyst_store.patch_object_series(
                project_id=project_id,
                linkable_object_id=linkable_object_id,
                signal_id=signal_id,
                document=payload.model_dump(exclude_unset=True),
                if_match=if_match,
                actor=object_series_actor(request),
            )
        except ObjectSeriesError as error:
            return object_series_refusal(error, request)
        return object_series_response(
            series,
            project_id=project_id,
            linkable_object_id=linkable_object_id,
            request_id=request_id,
        )

    @app.get(f"{OBJECT_ROOT}/object-series/{{signal_id}}")
    async def get_object_specific_time_series(
        project_id: int, linkable_object_id: int, signal_id: int, request: Request
    ):
        request_id = request.headers.get("x-request-id") or f"req_{secrets.token_hex(8)}"
        try:
            series = analyst_store.read_object_series(
                project_id=project_id,
                linkable_object_id=linkable_object_id,
                signal_id=signal_id,
            )
        except ObjectSeriesError as error:
            return object_series_refusal(error, request)
        etag = object_series_etag(
            signal_id=series["signal_id"],
            resource_version=series["resource_version"],
        )
        if request.headers.get("if-none-match") == etag:
            return Response(
                status_code=304,
                headers={"ETag": etag, "Cache-Control": "private, must-revalidate"},
            )
        return object_series_response(
            series,
            project_id=project_id,
            linkable_object_id=linkable_object_id,
            request_id=request_id,
        )

    @app.post(f"{OBJECT_ROOT}/object-series/{{signal_id}}/archive")
    async def archive_object_specific_time_series(
        project_id: int,
        linkable_object_id: int,
        signal_id: int,
        payload: ObjectSeriesArchiveRequest,
        request: Request,
        if_match: str | None = Header(default=None, alias="If-Match"),
    ):
        request_id = request.headers.get("x-request-id") or f"req_{secrets.token_hex(8)}"
        try:
            if not str(if_match or "").strip():
                raise ObjectSeriesError(
                    "TS_INGEST_PRECONDITION_REQUIRED", field="If-Match"
                )
            series = analyst_store.archive_object_series(
                project_id=project_id,
                linkable_object_id=linkable_object_id,
                signal_id=signal_id,
                if_match=if_match,
                actor=object_series_actor(request),
                reason_code=payload.reason_code,
                reason_text=payload.reason_text,
            )
        except ObjectSeriesError as error:
            return object_series_refusal(error, request)
        return object_series_response(
            series,
            project_id=project_id,
            linkable_object_id=linkable_object_id,
            request_id=request_id,
        )

    # -- SHARED_TARGET: a shared generic source seen from the object -------
    #
    # TS7-013, chapter 7.9. The dangerous branch gets its own base so a client
    # cannot turn a local load into a shared revision by editing a path
    # segment, and the impact is answered before the caller decides.

    ASSOCIATION_ROOT = f"{OBJECT_ROOT}/catalog-associations/{{association_id}}"

    def object_series_actor_role(request: Request) -> str:
        user = request.state.current_user or {}
        return str(user.get("role") or "analyst")

    @app.get(ASSOCIATION_ROOT)
    async def get_object_catalog_association(
        project_id: int,
        linkable_object_id: int,
        association_id: int,
        request: Request,
        intent: str = "shared",
    ):
        request_id = request.headers.get("x-request-id") or f"req_{secrets.token_hex(8)}"
        try:
            view = analyst_store.read_object_catalog_association(
                project_id=project_id,
                linkable_object_id=linkable_object_id,
                association_id=association_id,
                actor_role=object_series_actor_role(request),
                intent=intent,
            )
        except ObjectSeriesError as error:
            return object_series_refusal(error, request)
        view["request_id"] = request_id
        return JSONResponse(
            view, headers={"Cache-Control": "private, no-store"}
        )

    OBJECT_TARGET = f"{OBJECT_ROOT}/object-series/{{signal_id}}"

    @app.get(f"{OBJECT_TARGET}/revisions")
    async def get_object_series_revisions(
        project_id: int,
        linkable_object_id: int,
        signal_id: int,
        request: Request,
        limit: int = 50,
        cursor: str | None = None,
    ):
        user = request.state.current_user or {}
        actor_class = f"{user.get('role', 'analyst')}:{user.get('id', 'auth-disabled')}"
        request_id = request.headers.get("x-request-id") or f"req_{secrets.token_hex(8)}"
        try:
            page = analyst_store.read_object_series_revisions(
                project_id=project_id,
                linkable_object_id=linkable_object_id,
                signal_id=signal_id,
                limit=limit,
                cursor=cursor,
                actor_class=actor_class,
            )
        except ObjectSeriesError as error:
            return object_series_refusal(error, request)
        except CatalogQueryError as error:
            return JSONResponse(
                catalog_error_payload(error, request_id=request_id),
                status_code=410 if error.code == "TS_QUERY_CURSOR_EXPIRED" else 400,
                headers={"Cache-Control": "private, no-store"},
            )
        page["meta"]["request_id"] = request_id
        return JSONResponse(
            page, headers={"Cache-Control": "private, must-revalidate"}
        )

    @app.get(f"{OBJECT_TARGET}/preview")
    async def get_object_series_preview(
        project_id: int,
        linkable_object_id: int,
        signal_id: int,
        request: Request,
    ):
        request_id = request.headers.get("x-request-id") or f"req_{secrets.token_hex(8)}"
        try:
            query = parse_preview_query(request.query_params)
            preview = analyst_store.read_object_series_preview(
                project_id=project_id,
                linkable_object_id=linkable_object_id,
                signal_id=signal_id,
                **query,
            )
        except ObjectSeriesError as error:
            return object_series_refusal(error, request)
        except CatalogQueryError as error:
            return JSONResponse(
                catalog_error_payload(error, request_id=request_id),
                status_code=422 if error.code == "TS_PREVIEW_TOO_LARGE" else 400,
                headers={"Cache-Control": "private, no-store"},
            )
        preview["request_id"] = request_id
        return JSONResponse(
            preview,
            headers={
                "ETag": catalog_preview_etag(preview),
                "Cache-Control": "private, no-store",
            },
        )

    def ingestion_response(
        ingestion: dict[str, Any], request: Request, *, status_code: int = 200
    ) -> JSONResponse:
        request_id = request.headers.get("x-request-id") or f"req_{secrets.token_hex(8)}"
        return JSONResponse(
            {"ingestion": ingestion, "request_id": request_id},
            status_code=status_code,
            headers={"Cache-Control": "private, no-store"},
        )

    @app.post(f"{OBJECT_TARGET}/revision-ingestions/points", status_code=201)
    async def prepare_object_series_points_ingestion(
        project_id: int,
        linkable_object_id: int,
        signal_id: int,
        payload: ObjectSeriesPointsIngestionRequest,
        request: Request,
    ):
        try:
            ingestion = analyst_store.prepare_object_series_points_ingestion(
                project_id=project_id,
                linkable_object_id=linkable_object_id,
                signal_id=signal_id,
                document=payload.model_dump(),
                actor=object_series_actor(request),
            )
        except ObjectSeriesError as error:
            return object_series_refusal(error, request)
        return ingestion_response(ingestion, request, status_code=201)

    @app.post(f"{OBJECT_TARGET}/revision-ingestions/files", status_code=202)
    async def prepare_object_series_file_ingestion(
        project_id: int,
        linkable_object_id: int,
        signal_id: int,
        request: Request,
        file: UploadFile = File(...),
        mapping: str | None = Form(None),
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ):
        try:
            if not str(idempotency_key or "").strip():
                raise ObjectSeriesError(
                    "TS_INGEST_PRECONDITION_REQUIRED", field="Idempotency-Key"
                )
            # Parsing and normalization deliberately happen before the store
            # opens the short staging transaction.
            series = analyst_store.read_object_series(
                project_id=project_id,
                linkable_object_id=linkable_object_id,
                signal_id=signal_id,
            )
            try:
                document = None if mapping is None else json.loads(mapping)
            except json.JSONDecodeError as error:
                raise ObjectSeriesError(
                    "TS_INGEST_MAPPING_INVALID",
                    detail="mapping must be a JSON object",
                ) from error
            if document is not None and not isinstance(document, dict):
                raise ObjectSeriesError(
                    "TS_INGEST_MAPPING_INVALID",
                    detail="mapping must be a JSON object",
                )
            content = await file.read()
            uploaded = parse_object_series_file_upload(
                original_filename=file.filename or "source.csv",
                media_type=file.content_type,
                content=content,
                series_key=series["object_series_key"],
                sheet_name=(
                    None
                    if document is None
                    else str(document.get("sheet_name") or "").strip() or None
                ),
            )
            ingestion = analyst_store.prepare_object_series_file_ingestion(
                project_id=project_id,
                linkable_object_id=linkable_object_id,
                signal_id=signal_id,
                uploaded=uploaded,
                document=document,
                idempotency_key=str(idempotency_key),
                actor=object_series_actor(request),
            )
        except ObjectSeriesError as error:
            return object_series_refusal(error, request)
        finally:
            await file.close()
        return ingestion_response(ingestion, request, status_code=202)

    @app.get(f"{OBJECT_TARGET}/revision-ingestions/{{ingestion_id}}")
    async def get_object_series_ingestion(
        project_id: int,
        linkable_object_id: int,
        signal_id: int,
        ingestion_id: str,
        request: Request,
    ):
        try:
            ingestion = analyst_store.read_object_series_ingestion(
                project_id=project_id,
                linkable_object_id=linkable_object_id,
                signal_id=signal_id,
                ingestion_key=ingestion_id,
            )
        except ObjectSeriesError as error:
            return object_series_refusal(error, request)
        return ingestion_response(ingestion, request)

    @app.put(f"{OBJECT_TARGET}/revision-ingestions/{{ingestion_id}}/mapping")
    async def remap_object_series_ingestion(
        project_id: int,
        linkable_object_id: int,
        signal_id: int,
        ingestion_id: str,
        payload: ObjectSeriesIngestionMappingRequest,
        request: Request,
    ):
        try:
            ingestion = analyst_store.update_object_series_ingestion_mapping(
                project_id=project_id,
                linkable_object_id=linkable_object_id,
                signal_id=signal_id,
                ingestion_key=ingestion_id,
                mapping=payload.model_dump(exclude_none=True),
                actor=object_series_actor(request),
            )
        except ObjectSeriesError as error:
            return object_series_refusal(error, request)
        return ingestion_response(ingestion, request)

    @app.get(f"{OBJECT_TARGET}/revision-ingestions/{{ingestion_id}}/preview")
    async def preview_object_series_ingestion(
        project_id: int,
        linkable_object_id: int,
        signal_id: int,
        ingestion_id: str,
        request: Request,
        max_rows: int | None = None,
    ):
        request_id = request.headers.get("x-request-id") or f"req_{secrets.token_hex(8)}"
        try:
            preview = analyst_store.read_object_series_ingestion_preview(
                project_id=project_id,
                linkable_object_id=linkable_object_id,
                signal_id=signal_id,
                ingestion_key=ingestion_id,
                max_rows=max_rows,
            )
        except ObjectSeriesError as error:
            return object_series_refusal(error, request)
        preview["request_id"] = request_id
        return JSONResponse(preview, headers={"Cache-Control": "private, no-store"})

    @app.delete(
        f"{OBJECT_TARGET}/revision-ingestions/{{ingestion_id}}", status_code=204
    )
    async def cancel_object_series_ingestion(
        project_id: int,
        linkable_object_id: int,
        signal_id: int,
        ingestion_id: str,
        request: Request,
    ):
        try:
            analyst_store.cancel_object_series_ingestion(
                project_id=project_id,
                linkable_object_id=linkable_object_id,
                signal_id=signal_id,
                ingestion_key=ingestion_id,
                actor=object_series_actor(request),
            )
        except ObjectSeriesError as error:
            return object_series_refusal(error, request)
        return Response(status_code=204, headers={"Cache-Control": "private, no-store"})

    @app.post(f"{OBJECT_TARGET}/revision-ingestions/{{ingestion_id}}/publications")
    async def publish_object_series_ingestion(
        project_id: int,
        linkable_object_id: int,
        signal_id: int,
        ingestion_id: str,
        payload: ObjectSeriesPublicationRequest,
        request: Request,
        if_match: str | None = Header(default=None, alias="If-Match"),
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ):
        request_id = request.headers.get("x-request-id") or f"req_{secrets.token_hex(8)}"
        try:
            missing = (
                "If-Match"
                if not str(if_match or "").strip()
                else "Idempotency-Key"
                if not str(idempotency_key or "").strip()
                else None
            )
            if missing is not None:
                raise ObjectSeriesError(
                    "TS_INGEST_PRECONDITION_REQUIRED", field=missing
                )
            publication, replayed = analyst_store.publish_object_series_ingestion(
                project_id=project_id,
                linkable_object_id=linkable_object_id,
                signal_id=signal_id,
                ingestion_key=ingestion_id,
                validation_token=payload.validation_token,
                confirm=payload.confirm,
                reason_code=payload.reason_code,
                reason_text=payload.reason_text or "",
                if_match=if_match,
                idempotency_key=idempotency_key,
                actor=object_series_actor(request),
            )
        except ObjectSeriesError as error:
            return object_series_refusal(error, request)
        series = publication["object_series"]
        return JSONResponse(
            {"publication": publication, "request_id": request_id},
            status_code=(
                200 if replayed or publication["outcome"] == "unchanged" else 201
            ),
            headers={
                "ETag": object_series_etag(
                    signal_id=series["signal_id"],
                    resource_version=series["resource_version"],
                ),
                "Cache-Control": "private, no-store",
            },
        )

    SHARED_TARGET = f"{ASSOCIATION_ROOT}/shared-series"

    @app.post(f"{SHARED_TARGET}/revision-ingestions/points", status_code=201)
    async def prepare_shared_series_points_ingestion(
        project_id: int,
        linkable_object_id: int,
        association_id: int,
        payload: SharedSeriesPointsIngestionRequest,
        request: Request,
        intent: str = "shared",
    ):
        try:
            ingestion = analyst_store.prepare_shared_series_points_ingestion(
                project_id=project_id,
                linkable_object_id=linkable_object_id,
                association_id=association_id,
                document=payload.model_dump(),
                actor=object_series_actor(request),
                actor_role=object_series_actor_role(request),
                intent=intent,
            )
        except ObjectSeriesError as error:
            return object_series_refusal(error, request)
        return ingestion_response(ingestion, request, status_code=201)

    @app.get(f"{SHARED_TARGET}/revision-ingestions/{{ingestion_id}}")
    async def get_shared_series_ingestion(
        project_id: int,
        linkable_object_id: int,
        association_id: int,
        ingestion_id: str,
        request: Request,
        intent: str = "shared",
    ):
        try:
            ingestion = analyst_store.read_shared_series_ingestion(
                project_id=project_id,
                linkable_object_id=linkable_object_id,
                association_id=association_id,
                ingestion_key=ingestion_id,
                actor_role=object_series_actor_role(request),
                intent=intent,
            )
        except ObjectSeriesError as error:
            return object_series_refusal(error, request)
        return ingestion_response(ingestion, request)

    @app.get(f"{SHARED_TARGET}/revision-ingestions/{{ingestion_id}}/preview")
    async def preview_shared_series_ingestion(
        project_id: int,
        linkable_object_id: int,
        association_id: int,
        ingestion_id: str,
        request: Request,
        max_rows: int | None = None,
    ):
        request_id = request.headers.get("x-request-id") or f"req_{secrets.token_hex(8)}"
        try:
            preview = analyst_store.read_shared_series_ingestion_preview(
                project_id=project_id,
                linkable_object_id=linkable_object_id,
                association_id=association_id,
                ingestion_key=ingestion_id,
                max_rows=max_rows,
            )
        except ObjectSeriesError as error:
            return object_series_refusal(error, request)
        preview["request_id"] = request_id
        return JSONResponse(preview, headers={"Cache-Control": "private, no-store"})

    @app.delete(
        f"{SHARED_TARGET}/revision-ingestions/{{ingestion_id}}", status_code=204
    )
    async def cancel_shared_series_ingestion(
        project_id: int,
        linkable_object_id: int,
        association_id: int,
        ingestion_id: str,
        request: Request,
    ):
        try:
            analyst_store.cancel_shared_series_ingestion(
                project_id=project_id,
                linkable_object_id=linkable_object_id,
                association_id=association_id,
                ingestion_key=ingestion_id,
                actor=object_series_actor(request),
            )
        except ObjectSeriesError as error:
            return object_series_refusal(error, request)
        return Response(status_code=204, headers={"Cache-Control": "private, no-store"})

    @app.post(f"{SHARED_TARGET}/revision-ingestions/{{ingestion_id}}/publications")
    async def publish_shared_series_ingestion(
        project_id: int,
        linkable_object_id: int,
        association_id: int,
        ingestion_id: str,
        payload: SharedSeriesPublicationRequest,
        request: Request,
        if_match: str | None = Header(default=None, alias="If-Match"),
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ):
        request_id = request.headers.get("x-request-id") or f"req_{secrets.token_hex(8)}"
        try:
            missing = (
                "If-Match"
                if not str(if_match or "").strip()
                else "Idempotency-Key"
                if not str(idempotency_key or "").strip()
                else None
            )
            if missing is not None:
                raise ObjectSeriesError(
                    "TS_INGEST_PRECONDITION_REQUIRED", field=missing
                )
            publication, replayed = analyst_store.publish_shared_series_ingestion(
                project_id=project_id,
                linkable_object_id=linkable_object_id,
                association_id=association_id,
                ingestion_key=ingestion_id,
                validation_token=payload.validation_token,
                confirm=payload.confirm,
                comprehension_acknowledged=payload.comprehension_acknowledged,
                impact_fingerprint=payload.impact_fingerprint,
                reason_code=payload.reason_code,
                reason_text=payload.reason_text or "",
                if_match=if_match,
                idempotency_key=idempotency_key,
                actor=object_series_actor(request),
                actor_role=object_series_actor_role(request),
            )
        except ObjectSeriesError as error:
            return object_series_refusal(error, request)
        return JSONResponse(
            {"publication": publication, "request_id": request_id},
            status_code=(
                200 if replayed or publication["outcome"] == "unchanged" else 201
            ),
            headers={
                "ETag": publication["etag"],
                "Cache-Control": "private, no-store",
            },
        )

    @app.post(f"{ASSOCIATION_ROOT}/object-series-derivation-prevalidations")
    async def prevalidate_object_series_derivation(
        project_id: int,
        linkable_object_id: int,
        association_id: int,
        payload: ObjectSeriesDerivationRequest,
        request: Request,
    ):
        request_id = request.headers.get("x-request-id") or f"req_{secrets.token_hex(8)}"
        try:
            comparison = analyst_store.prevalidate_object_series_derivation(
                project_id=project_id,
                linkable_object_id=linkable_object_id,
                association_id=association_id,
                document=payload.model_dump(exclude_none=True),
            )
        except ObjectSeriesError as error:
            return object_series_refusal(error, request)
        comparison["request_id"] = request_id
        return JSONResponse(
            comparison, headers={"Cache-Control": "private, no-store"}
        )

    @app.post(f"{ASSOCIATION_ROOT}/object-series-derivations", status_code=201)
    async def commit_object_series_derivation(
        project_id: int,
        linkable_object_id: int,
        association_id: int,
        payload: ObjectSeriesDerivationRequest,
        request: Request,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ):
        request_id = request.headers.get("x-request-id") or f"req_{secrets.token_hex(8)}"
        try:
            if not str(idempotency_key or "").strip():
                raise ObjectSeriesError(
                    "TS_INGEST_PRECONDITION_REQUIRED", field="Idempotency-Key"
                )
            derivation, replayed = analyst_store.commit_object_series_derivation(
                project_id=project_id,
                linkable_object_id=linkable_object_id,
                association_id=association_id,
                document=payload.model_dump(exclude_none=True),
                actor=object_series_actor(request),
                idempotency_key=str(idempotency_key),
            )
        except ObjectSeriesError as error:
            return object_series_refusal(error, request)
        series = derivation["object_series"]
        return JSONResponse(
            {"derivation": derivation, "request_id": request_id},
            status_code=200 if replayed else 201,
            headers={
                "ETag": object_series_etag(
                    signal_id=series["signal_id"],
                    resource_version=series["resource_version"],
                ),
                "Cache-Control": "private, no-store",
            },
        )

    @app.get("/api/projects/{project_id}/portal-configuration")
    async def get_portal_configuration(project_id: int):
        try:
            analyst_store.get_project(project_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return {"portal_configuration": portal_configuration_response_body(project_id)}

    @app.put("/api/projects/{project_id}/portal-configuration")
    async def save_portal_configuration(
        project_id: int,
        request: Request,
        payload: PortalConfigurationWriteRequest,
    ):
        try:
            document = validate_portal_config_document(payload.document)
            status = validate_portal_configuration_status(payload.status)
            analyst_store.save_portal_configuration(
                project_id,
                document=document,
                status=status,
                expected_revision=payload.expected_revision,
                updated_by_user_id=current_user_id(request),
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except PortalConfigurationError as error:
            raise HTTPException(
                status_code=error.status_code, detail=error.message
            ) from error
        return {"portal_configuration": portal_configuration_response_body(project_id)}

    @app.put("/api/projects/{project_id}/portal-configuration/logo")
    async def upload_portal_logo(
        project_id: int,
        request: Request,
        logo: UploadFile = File(...),
        expected_revision: int = Form(...),
    ):
        if logo.content_type not in {"image/png", "image/jpeg"}:
            raise HTTPException(
                status_code=415, detail="portal logo must be a PNG or JPEG image"
            )
        logo_bytes = await logo.read(PORTAL_LOGO_MAX_BYTES + 1)
        if len(logo_bytes) > PORTAL_LOGO_MAX_BYTES:
            raise HTTPException(
                status_code=413, detail="portal logo must not exceed 256 KiB"
            )
        if not portal_logo_signature_matches(str(logo.content_type), logo_bytes):
            raise HTTPException(
                status_code=415,
                detail="portal logo content must match its PNG or JPEG media type",
            )
        try:
            analyst_store.save_portal_logo(
                project_id,
                logo_bytes=logo_bytes,
                logo_media_type=logo.content_type,
                expected_revision=expected_revision,
                updated_by_user_id=current_user_id(request),
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except PortalConfigurationError as error:
            raise HTTPException(
                status_code=error.status_code, detail=error.message
            ) from error
        return {"portal_configuration": portal_configuration_response_body(project_id)}

    @app.get("/api/projects/{project_id}/portal-configuration/logo")
    async def get_portal_logo_for_preview(project_id: int, request: Request):
        configuration = analyst_store.get_portal_configuration(project_id)
        if (
            configuration is None
            or configuration["status"] != "active"
            or configuration["logo_bytes"] is None
            or configuration["logo_media_type"] is None
        ):
            raise HTTPException(status_code=404, detail="logo not found")
        etag = f'"portal-logo-r{configuration["revision"]}"'
        response_headers = {
            "ETag": etag,
            "Cache-Control": "private, must-revalidate",
            "X-Content-Type-Options": "nosniff",
        }
        if request.headers.get("if-none-match") == etag:
            return Response(status_code=304, headers=response_headers)
        return Response(
            content=configuration["logo_bytes"],
            media_type=configuration["logo_media_type"],
            headers=response_headers,
        )

    @app.delete("/api/projects/{project_id}/portal-configuration/logo")
    async def remove_portal_logo(
        project_id: int,
        request: Request,
        payload: PortalLogoDeleteRequest,
    ):
        try:
            analyst_store.save_portal_logo(
                project_id,
                logo_bytes=None,
                logo_media_type=None,
                expected_revision=payload.expected_revision,
                updated_by_user_id=current_user_id(request),
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except PortalConfigurationError as error:
            raise HTTPException(
                status_code=error.status_code, detail=error.message
            ) from error
        return {"portal_configuration": portal_configuration_response_body(project_id)}

    @app.get("/api/projects/{project_id}/dashboard-templates")
    async def list_dashboard_templates(project_id: int):
        try:
            templates = analyst_store.list_dashboard_templates(project_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return {"dashboard_templates": templates}

    @app.post("/api/projects/{project_id}/dashboard-templates", status_code=201)
    async def create_dashboard_template(
        project_id: int,
        request: Request,
        payload: DashboardTemplateWriteRequest,
    ):
        try:
            template = analyst_store.create_dashboard_template(
                project_id=project_id,
                name=payload.name,
                show_summary=payload.show_summary,
                show_price_chart=payload.show_price_chart,
                show_grid_chart=payload.show_grid_chart,
                show_renewable_chart=payload.show_renewable_chart,
                show_bess_chart=payload.show_bess_chart,
                show_hydro_chart=payload.show_hydro_chart,
                show_profit_chart=payload.show_profit_chart,
                show_system_dispatch_table=payload.show_system_dispatch_table,
                show_asset_dispatch_table=payload.show_asset_dispatch_table,
                table_preview_limit=payload.table_preview_limit,
                created_by=current_user_email(request),
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        return {"dashboard_template": template}

    @app.get("/api/dashboard-templates/{template_id}")
    async def get_dashboard_template(template_id: int):
        try:
            template = analyst_store.get_dashboard_template(template_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return {"dashboard_template": template}

    @app.put("/api/dashboard-templates/{template_id}")
    async def update_dashboard_template(
        template_id: int,
        request: Request,
        payload: DashboardTemplateWriteRequest,
    ):
        try:
            template = analyst_store.update_dashboard_template(
                template_id,
                name=payload.name,
                show_summary=payload.show_summary,
                show_price_chart=payload.show_price_chart,
                show_grid_chart=payload.show_grid_chart,
                show_renewable_chart=payload.show_renewable_chart,
                show_bess_chart=payload.show_bess_chart,
                show_hydro_chart=payload.show_hydro_chart,
                show_profit_chart=payload.show_profit_chart,
                show_system_dispatch_table=payload.show_system_dispatch_table,
                show_asset_dispatch_table=payload.show_asset_dispatch_table,
                table_preview_limit=payload.table_preview_limit,
                updated_by=current_user_email(request),
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        return {"dashboard_template": template}

    @app.get("/api/dashboard-templates/{template_id}/runs/{run_id}/results")
    async def get_dashboard_template_run_results(template_id: int, run_id: int):
        try:
            template = analyst_store.get_dashboard_template(template_id)
            if analyst_store.get_run_project_id(run_id) != template["project_id"]:
                raise KeyError(f"run {run_id} not found for dashboard template {template_id}")
            run = analyst_store.get_run(run_id)
            artifacts = analyst_store.list_run_artifacts(run_id)
            results = read_run_results(run, artifacts, configured_artifact_root, store=analyst_store)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ResultReadError as error:
            return JSONResponse(
                {"status": "error", "message": error.message},
                status_code=error.status_code,
            )
        return {
            "dashboard": {
                "template": template,
                "results": apply_dashboard_template(results, template),
            }
        }

    @app.post("/api/system-cases/validate")
    async def validate_system_case(payload: SystemCaseValidationRequest):
        result = service.validate_text(payload.system_case_json)
        body = validation_response_body(result)
        if result.ok:
            return body

        return JSONResponse(body, status_code=400)

    @app.post("/api/projects", status_code=201)
    async def create_project(payload: ProjectCreateRequest):
        project = analyst_store.create_project(
            name=payload.name.strip(),
            description=payload.description.strip(),
        )
        return project

    @app.get("/api/projects")
    async def list_projects():
        return {"projects": analyst_store.list_projects()}

    @app.get("/api/projects/{project_id}")
    async def get_project(project_id: int):
        try:
            project = analyst_store.get_project(project_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return {"project": project}

    @app.delete("/api/projects/{project_id}")
    async def delete_project(project_id: int):
        try:
            deleted_project = analyst_store.delete_project(project_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return {"deleted_project": deleted_project}

    @app.post("/api/projects/{project_id}/scenarios", status_code=201)
    async def create_scenario(project_id: int, payload: ScenarioCreateRequest):
        try:
            scenario = analyst_store.create_scenario(
                project_id=project_id,
                name=payload.name.strip(),
                description=payload.description.strip(),
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return scenario

    @app.get("/api/projects/{project_id}/scenarios")
    async def list_scenarios(project_id: int):
        try:
            scenarios = analyst_store.list_scenarios(project_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return {"scenarios": scenarios}

    @app.get("/api/scenarios/{scenario_id}")
    async def get_scenario(scenario_id: int):
        try:
            scenario = analyst_store.get_scenario(scenario_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return {"scenario": scenario}

    @app.post("/api/scenarios/{scenario_id}/hydraulic-diagram", status_code=201)
    async def create_hydraulic_diagram(scenario_id: int):
        try:
            diagram = analyst_store.get_or_create_hydraulic_diagram(scenario_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return {"diagram": diagram}

    @app.get("/api/scenarios/{scenario_id}/hydraulic-diagram")
    async def get_hydraulic_diagram(scenario_id: int):
        try:
            diagram = analyst_store.get_hydraulic_diagram(scenario_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return {"diagram": diagram}

    @app.put("/api/scenarios/{scenario_id}/hydraulic-diagram")
    async def save_hydraulic_diagram(scenario_id: int, payload: HydraulicDiagramSaveRequest):
        try:
            diagram = analyst_store.save_hydraulic_diagram(
                scenario_id=scenario_id,
                revision=payload.revision,
                nodes=[node.model_dump() for node in payload.nodes],
                reaches=[reach.model_dump() for reach in payload.reaches],
                viewport=payload.viewport.model_dump(),
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            status_code = 409 if str(error) == "stale hydraulic diagram revision" else 400
            raise HTTPException(status_code=status_code, detail=str(error)) from error
        return {"diagram": diagram}

    @app.post("/api/scenarios/{scenario_id}/hydraulic-diagram/validate")
    async def validate_hydraulic_diagram(scenario_id: int):
        try:
            validation = analyst_store.validate_hydraulic_diagram(scenario_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return {"validation": validation}

    @app.post("/api/scenarios/{scenario_id}/hydraulic-diagram/v3-preview")
    async def validate_hydraulic_v3_preview(scenario_id: int):
        try:
            topology_validation = analyst_store.validate_hydraulic_diagram(scenario_id)
            if not topology_validation["ok"]:
                validation = {
                    **topology_validation,
                    "kind": "hydraulic_topology",
                    "stale": False,
                    "status": "error",
                    "system_case": None,
                }
                return {"validation": validation}
            system_case = analyst_store.generate_hydraulic_v3_preview(scenario_id)
            result = service.validate_text(json.dumps(system_case, sort_keys=True))
            if not result.ok:
                validation = {
                    "kind": "hydraulic_v3_preview",
                    "ok": False,
                    "stale": False,
                    "status": "error",
                    "summary": "Hydraulic v3 payload failed Julia validation",
                    "errors": [
                        {
                            "severity": "error",
                            "code": "julia_v3_validation_failed",
                            "message": result.message,
                            "entity_type": "hydraulic_v3_payload",
                            "entity_id": 0,
                            "technical_key": "bess_system_dispatch.v3",
                        }
                    ],
                    "warnings": [],
                    "system_case": system_case,
                    "julia_validation": result.payload,
                }
                return {"validation": validation}
            validation = analyst_store.persist_hydraulic_v3_validation(
                scenario_id=scenario_id,
                system_case=system_case,
                julia_payload=result.payload,
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        return {"validation": validation}

    @app.post("/api/scenarios/{scenario_id}/hydraulic-diagram/promote", status_code=201)
    async def promote_hydraulic_diagram(scenario_id: int):
        try:
            diagram = analyst_store.get_hydraulic_diagram(scenario_id)
            validation = diagram["validation"]
            if validation.get("kind") != "hydraulic_v3_preview":
                raise DraftPromotionError("hydraulic v3 validation must succeed before promotion")
            if validation.get("stale"):
                stale_state = {
                    "topology_stale": bool(validation.get("topology_stale")),
                    "parameters_stale": bool(validation.get("parameters_stale")),
                }
                raise DraftPromotionError(
                    hierarchy_stale_summary("hydraulic v3 validation", stale_state)
                    + "; validate again before promotion"
                )
            if not validation.get("ok"):
                raise DraftPromotionError("hydraulic v3 validation must succeed before promotion")
            system_case = validation.get("system_case")
            if not isinstance(system_case, dict):
                raise DraftPromotionError("hydraulic v3 validation snapshot is missing system_case")
            current_system_case = analyst_store.generate_hydraulic_v3_preview(scenario_id)
            stale_state = hierarchy_stale_state(system_case, current_system_case)
            if stale_state is not None:
                raise DraftPromotionError(
                    hierarchy_stale_summary("hydraulic v3 validation", stale_state)
                    + "; validate again before promotion"
                )
            scenario_version, error = save_validated_scenario_version(
                scenario_id,
                json.dumps(system_case, sort_keys=True),
                {
                    "kind": "hydraulic_diagram_v3",
                    "source_case_id": diagram["optimization_case"]["id"],
                    "validation_hash": validation.get("validation_hash"),
                    "generated_at": utc_now_iso(),
                },
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except DraftPromotionError as error:
            return JSONResponse(error_response_body("promotion", str(error), phase="python_validation"), status_code=400)
        if error is not None:
            return JSONResponse(validation_response_body(error), status_code=400)
        analyst_store.persist_scenario_version_hydraulic_diagram_snapshot(
            scenario_version_id=scenario_version["id"],
            layout_snapshot=build_hydraulic_diagram_layout_snapshot(diagram),
            source_case_id=diagram["optimization_case"]["id"],
            layout_key=diagram["layout"]["layout_key"],
        )
        return scenario_version

    def blocked_console_warning(scenario_id: int) -> dict[str, Any]:
        """The active consoles a just-saved case change left unable to run.

        Purely informative and computed after the write: an engineer learns
        who they broke without the save being refused on their behalf.
        """

        return {
            "affected_consoles": analyst_store.list_blocked_active_operator_consoles(
                scenario_id
            )
        }

    @app.post("/api/scenarios/{scenario_id}/draft", status_code=201)
    async def create_scenario_draft(scenario_id: int, payload: ScenarioDraftWriteRequest):
        try:
            draft_document = payload.document
            if draft_document is None:
                draft_document = create_initial_draft_document(
                    analyst_store,
                    scenario_id,
                    payload.source_version_id,
                )
            draft = analyst_store.create_or_replace_scenario_draft(
                scenario_id=scenario_id,
                document=draft_document,
                source_version_id=payload.source_version_id,
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return {**draft, **blocked_console_warning(scenario_id)}

    @app.get("/api/scenarios/{scenario_id}/draft")
    async def get_scenario_draft(scenario_id: int):
        try:
            draft = analyst_store.get_scenario_draft(scenario_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return {"draft": draft}

    @app.get("/api/scenarios/{scenario_id}/draft/generated-system-case")
    async def get_generated_system_case_preview(scenario_id: int):
        try:
            draft = analyst_store.get_scenario_draft(scenario_id)
            system_case = generate_system_case_from_draft(draft["document"])
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except DraftGenerationError as error:
            return JSONResponse(
                error_response_body(
                    draft_error_category(draft["document"], error),
                    str(error),
                    phase="python_validation",
                ),
                status_code=400,
            )
        return {"system_case": system_case}

    @app.post("/api/scenarios/{scenario_id}/draft/generated-system-case/validate")
    async def validate_generated_system_case(scenario_id: int):
        try:
            draft = analyst_store.get_scenario_draft(scenario_id)
            system_case = generate_system_case_from_draft(draft["document"])
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except DraftGenerationError as error:
            return JSONResponse(
                error_response_body(
                    draft_error_category(draft["document"], error),
                    str(error),
                    phase="python_validation",
                ),
                status_code=400,
            )

        result = service.validate_text(json.dumps(system_case, sort_keys=True))
        updated_document = draft_document_with_generated_validation(
            draft["document"],
            system_case,
            result,
        )
        analyst_store.update_scenario_draft(
            scenario_id=scenario_id,
            document=updated_document,
        )
        body = validation_response_body(result)
        body["system_case"] = system_case
        body["generated_system_case"] = generated_system_case_snapshot(system_case, result)
        if result.ok:
            return body
        return JSONResponse(body, status_code=400)

    @app.post("/api/scenarios/{scenario_id}/draft/generated-system-case/promote", status_code=201)
    async def promote_generated_system_case(scenario_id: int):
        try:
            draft = analyst_store.get_scenario_draft(scenario_id)
            system_case = validated_generated_system_case_from_draft(draft["document"])
            scenario_version, error = save_validated_scenario_version(
                scenario_id,
                json.dumps(system_case, sort_keys=True),
                generation_metadata_from_draft(draft["document"]),
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except (DraftGenerationError, DraftPromotionError) as error:
            category = (
                draft_error_category(draft["document"], error)
                if isinstance(error, DraftGenerationError)
                else "promotion"
            )
            return JSONResponse(error_response_body(category, str(error), phase="python_validation"), status_code=400)
        if error is not None:
            updated_document = draft_document_with_generated_validation(
                draft["document"],
                system_case,
                error,
            )
            analyst_store.update_scenario_draft(
                scenario_id=scenario_id,
                document=updated_document,
            )
            return JSONResponse(validation_response_body(error), status_code=400)
        return scenario_version

    @app.post("/api/scenarios/{scenario_id}/draft/time-series-sources/upload", status_code=201)
    async def upload_draft_time_series_source(
        scenario_id: int,
        source_file: UploadFile = File(...),
        sheet_name: str | None = Form(None),
    ):
        try:
            draft = get_or_create_scenario_draft(scenario_id)
            content = await source_file.read()
            source = ingest_time_series_source(
                draft_document=draft["document"],
                original_filename=source_file.filename or "source.csv",
                content_type=source_file.content_type,
                content=content,
                input_source_root=configured_input_source_root,
                sheet_name=sheet_name,
            )
            updated_document = attach_time_series_source(draft["document"], source)
            analyst_store.update_scenario_draft(
                scenario_id=scenario_id,
                document=updated_document,
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except TimeSeriesIngestionError as error:
            return JSONResponse(error_response_body("source_file", str(error)), status_code=400)
        finally:
            await source_file.close()
        return {"source": source}

    @app.get("/api/scenarios/{scenario_id}/draft/time-series-sources/{source_id}/rows")
    async def get_draft_time_series_rows(scenario_id: int, source_id: str):
        try:
            draft = analyst_store.get_scenario_draft(scenario_id)
            columns, rows = get_time_series_source_rows(
                document=draft["document"],
                source_id=source_id,
                input_source_root=configured_input_source_root,
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except TimeSeriesIngestionError as error:
            return JSONResponse(error_response_body("source_file", str(error)), status_code=400)
        return {"columns": columns, "rows": rows}

    @app.put("/api/scenarios/{scenario_id}/draft/time-series-sources/{source_id}/rows")
    async def save_draft_time_series_rows(
        scenario_id: int,
        source_id: str,
        payload: TimeSeriesRowsRequest,
    ):
        try:
            draft = analyst_store.get_scenario_draft(scenario_id)
            updated_document, source = update_time_series_source_rows(
                document=draft["document"],
                source_id=source_id,
                rows=payload.rows,
                input_source_root=configured_input_source_root,
            )
            analyst_store.update_scenario_draft(
                scenario_id=scenario_id,
                document=updated_document,
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except TimeSeriesIngestionError as error:
            return JSONResponse(error_response_body("source_file", str(error)), status_code=400)
        return {"source": source}

    @app.put("/api/scenarios/{scenario_id}/draft/time-series-sources/{source_id}/mapping")
    async def save_draft_time_series_mapping(
        scenario_id: int,
        source_id: str,
        payload: TimeSeriesMappingRequest,
    ):
        try:
            draft = analyst_store.get_scenario_draft(scenario_id)
            updated_document, source = apply_time_series_mapping(
                document=draft["document"],
                source_id=source_id,
                mapping=payload.mapping,
                input_source_root=configured_input_source_root,
            )
            analyst_store.update_scenario_draft(
                scenario_id=scenario_id,
                document=updated_document,
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except TimeSeriesIngestionError as error:
            return JSONResponse(error_response_body("source_file", str(error)), status_code=400)
        return {"source": source}

    @app.post(
        "/api/scenarios/{scenario_id}/draft/time-series-sources/{source_id}/catalog-import",
        status_code=201,
    )
    async def import_draft_time_series_source_to_catalog(
        scenario_id: int,
        source_id: str,
        payload: TimeSeriesCatalogImportRequest,
    ):
        try:
            draft = analyst_store.get_scenario_draft(scenario_id)
            time_series = draft["document"].get("time_series")
            sources = time_series.get("sources") if isinstance(time_series, dict) else None
            source = next(
                (
                    item
                    for item in sources or []
                    if isinstance(item, dict) and item.get("id") == source_id
                ),
                None,
            )
            if source is None:
                raise KeyError(f"time-series source {source_id} not found")
            _columns, rows = get_time_series_source_rows(
                document=draft["document"],
                source_id=source_id,
                input_source_root=configured_input_source_root,
            )
            prepared_import = prepare_time_series_catalog_import(
                rows=rows,
                request=PreparedCatalogImportRequest(
                    set_name=payload.set_name,
                    version_label=payload.version_label,
                    data_kind=payload.data_kind,
                    timezone=payload.timezone,
                    timestamp_column=payload.timestamp_column,
                    duration_hours_column=payload.duration_hours_column,
                    value_column=payload.value_column,
                    signal_key=payload.signal_key,
                    source_unit=payload.source_unit,
                    signal_mappings=[
                        PreparedCatalogSignalMappingRequest(
                            source_column=item.source_column,
                            signal_key=item.signal_key,
                            source_unit=item.source_unit,
                        )
                        for item in payload.signal_mappings
                    ],
                ),
            )
            created_set = analyst_store.import_time_series_catalog_set(
                scenario_id=scenario_id,
                source=source,
                prepared_import=prepared_import,
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except TimeSeriesIngestionError as error:
            return JSONResponse(error_response_body("source_file", str(error)), status_code=400)
        except (TimeSeriesCatalogError, ValueError) as error:
            return JSONResponse(
                error_response_body(
                    "catalog_import",
                    time_series_source_error_detail(source, str(error)),
                    phase="python_validation",
                ),
                status_code=400,
            )
        return {"time_series_set": created_set}

    @app.post(
        "/api/scenarios/{scenario_id}/draft/time-series-sources/{source_id}/extract",
        status_code=201,
    )
    async def extract_draft_time_series_source_to_catalog(
        scenario_id: int,
        source_id: str,
        payload: DraftTimeSeriesExtractionRequest,
        request: Request,
    ):
        try:
            extracted_set = analyst_store.extract_draft_time_series_set(
                scenario_id=scenario_id,
                source_id=source_id,
                set_name=payload.set_name,
                version_label=payload.version_label,
                data_kind=payload.data_kind,
                timezone_name=payload.timezone,
                created_by=current_user_email(request),
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except (LegacyDraftExtractionError, TimeSeriesCatalogError, ValueError) as error:
            return JSONResponse(
                error_response_body("draft_extraction", str(error), phase="python_validation"),
                status_code=400,
            )
        return {"time_series_set": extracted_set}

    @app.get("/api/projects/{project_id}/time-series-sets")
    async def list_project_time_series_sets(project_id: int):
        try:
            time_series_sets = analyst_store.list_time_series_sets(project_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return {"time_series_sets": time_series_sets}

    @app.post(
        "/api/projects/{project_id}/time-series-sets/connector-ingest",
        status_code=201,
    )
    async def ingest_project_time_series_from_connector(
        project_id: int,
        payload: TimeSeriesConnectorIngestionRequest,
        request: Request,
    ):
        try:
            analyst_store.get_project(project_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

        connector = build_forecast_connector(
            HttpJsonForecastConnectorConfig(
                connector_id=payload.connector.connector_id,
                base_url=payload.connector.base_url,
                records_path=payload.connector.records_path,
                auth_token=payload.connector.auth_token,
            )
        )
        try:
            fetched = connector.fetch()
        except ForecastConnectorError as error:
            return JSONResponse(
                error_response_body("connector_fetch", str(error)),
                status_code=400,
            )

        program = payload.program.model_dump() if payload.program is not None else None
        try:
            prepared_import = prepare_time_series_catalog_import(
                rows=fetched.rows,
                request=PreparedCatalogImportRequest(
                    set_name=payload.set_name,
                    version_label=payload.version_label,
                    data_kind="programmed" if program is not None else "forecast",
                    timezone=payload.timezone,
                    timestamp_column=payload.timestamp_column,
                    duration_hours_column=payload.duration_hours_column,
                    value_column=payload.value_column,
                    signal_key=payload.signal_key,
                    source_unit=payload.source_unit,
                    signal_mappings=[
                        PreparedCatalogSignalMappingRequest(
                            source_column=item.source_column,
                            signal_key=item.signal_key,
                            source_unit=item.source_unit,
                        )
                        for item in payload.signal_mappings
                    ],
                ),
            )
            result = analyst_store.ingest_connector_time_series_set(
                project_id=project_id,
                source={
                    "id": f"connector:{fetched.connector_id}:{fetched.payload_checksum}",
                    "kind": "connector",
                    "original_filename": f"{fetched.connector_id}.json",
                    "media_type": "application/json",
                    "checksum": fetched.payload_checksum,
                    "stored_path": "",
                    "metadata": {
                        "connector_id": fetched.connector_id,
                        "target": fetched.target,
                        "fetched_at": fetched.fetched_at,
                        "record_count": len(fetched.rows),
                    },
                },
                prepared_import=prepared_import,
                program=program,
                created_by=current_user_email(request),
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except (TimeSeriesCatalogError, ValueError) as error:
            return JSONResponse(
                error_response_body(
                    "connector_ingestion", str(error), phase="python_validation"
                ),
                status_code=400,
            )
        ingested_set = result["time_series_set"]
        ingested_set["staleness"] = analyst_store.evaluate_time_series_set_staleness(
            project_id, ingested_set["id"]
        )
        ingestion_summary: dict = {
            "outcome": result["outcome"],
            "connector_id": fetched.connector_id,
            "target": fetched.target,
            "fetched_at": fetched.fetched_at,
            "record_count": len(fetched.rows),
        }
        if program is not None:
            ingestion_summary["program"] = program
        return {
            "time_series_set": ingested_set,
            "ingestion": ingestion_summary,
        }

    @app.get("/api/projects/{project_id}/time-series-sets/hydraulic")
    async def list_project_hydraulic_time_series_sets(project_id: int):
        try:
            hydraulic_time_series_sets = analyst_store.list_hydraulic_time_series_sets(
                project_id
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return {"hydraulic_time_series_sets": hydraulic_time_series_sets}

    @app.get("/api/projects/{project_id}/time-series-sets/hydraulic/{hydraulic_time_series_set_id}")
    async def get_project_hydraulic_time_series_set(
        project_id: int, hydraulic_time_series_set_id: int
    ):
        try:
            hydraulic_time_series_set = analyst_store.get_hydraulic_time_series_set(
                project_id, hydraulic_time_series_set_id
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return {"hydraulic_time_series_set": hydraulic_time_series_set}

    @app.post(
        "/api/projects/{project_id}/time-series-sets/hydraulic/{hydraulic_time_series_set_id}/migrate"
    )
    async def migrate_project_hydraulic_time_series_set(
        project_id: int, hydraulic_time_series_set_id: int, request: Request
    ):
        try:
            result = analyst_store.migrate_hydraulic_time_series_set(
                project_id=project_id,
                hydraulic_time_series_set_id=hydraulic_time_series_set_id,
                migrated_by=current_user_email(request),
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            return JSONResponse(
                error_response_body("hydraulic_migration", str(error), phase="python_validation"),
                status_code=400,
            )
        return result

    @app.post("/api/projects/{project_id}/time-series-sets/hydraulic/migrate-all")
    async def migrate_all_project_hydraulic_time_series_sets(project_id: int, request: Request):
        require_admin_user(request)
        try:
            report = analyst_store.migrate_all_hydraulic_time_series_sets(
                project_id=project_id,
                migrated_by=current_user_email(request),
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return report

    @app.get("/api/projects/{project_id}/time-series-sets/{time_series_set_id}")
    async def get_project_time_series_set(project_id: int, time_series_set_id: int):
        try:
            time_series_set = analyst_store.get_time_series_set(project_id, time_series_set_id)
            time_series_set["staleness"] = analyst_store.evaluate_time_series_set_staleness(
                project_id, time_series_set_id
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return {"time_series_set": time_series_set}

    @app.post(
        "/api/projects/{project_id}/time-series-sets/{time_series_set_id}/regenerate"
    )
    async def regenerate_project_derived_time_series_set(
        project_id: int, time_series_set_id: int, request: Request
    ):
        try:
            regenerated_set = analyst_store.regenerate_derived_time_series_set(
                project_id=project_id,
                time_series_set_id=time_series_set_id,
                created_by=current_user_email(request),
            )
            regenerated_set["staleness"] = analyst_store.evaluate_time_series_set_staleness(
                project_id, time_series_set_id
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except (TransformationError, ValueError) as error:
            return JSONResponse(
                error_response_body(
                    "time_series_regeneration", str(error), phase="python_validation"
                ),
                status_code=400,
            )
        return {"time_series_set": regenerated_set}

    @app.get("/api/projects/{project_id}/time-series-sets/{time_series_set_id}/revisions")
    async def list_project_time_series_set_revisions(
        project_id: int, time_series_set_id: int
    ):
        try:
            revisions = analyst_store.list_time_series_set_revisions(
                project_id, time_series_set_id
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return {"time_series_set_revisions": revisions}

    @app.post(
        "/api/projects/{project_id}/time-series-sets/{time_series_set_id}/transformations",
        status_code=201,
    )
    async def apply_project_time_series_transformation(
        project_id: int,
        time_series_set_id: int,
        payload: TimeSeriesTransformationRequest,
        request: Request,
    ):
        try:
            derived_set = analyst_store.apply_time_series_transformation(
                project_id=project_id,
                time_series_set_id=time_series_set_id,
                transformation_type=payload.transformation_type,
                raw_parameters=payload.parameters,
                output_name=payload.output_name,
                output_version_label=payload.output_version_label,
                created_by=current_user_email(request),
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except (TransformationError, ValueError) as error:
            return JSONResponse(
                error_response_body(
                    "time_series_transformation", str(error), phase="python_validation"
                ),
                status_code=400,
            )
        return {"time_series_set": derived_set}

    @app.post(
        "/api/projects/{project_id}/time-series-transformations",
        status_code=201,
    )
    async def apply_project_time_series_combination(
        project_id: int,
        payload: TimeSeriesTransformationRequest,
        request: Request,
    ):
        try:
            derived_set = analyst_store.apply_time_series_combination(
                project_id=project_id,
                transformation_type=payload.transformation_type,
                raw_parameters=payload.parameters,
                output_name=payload.output_name,
                output_version_label=payload.output_version_label,
                created_by=current_user_email(request),
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except (TransformationError, ValueError) as error:
            return JSONResponse(
                error_response_body(
                    "time_series_transformation", str(error), phase="python_validation"
                ),
                status_code=400,
            )
        return {"time_series_set": derived_set}

    @app.put("/api/projects/{project_id}/time-series-sets/{time_series_set_id}/values")
    async def edit_project_time_series_set_values(
        project_id: int,
        time_series_set_id: int,
        payload: TimeSeriesSetValuesEditRequest,
        request: Request,
    ):
        try:
            updated_set = analyst_store.edit_time_series_set_values(
                project_id=project_id,
                time_series_set_id=time_series_set_id,
                edits=[
                    CatalogValueEdit(
                        period_index=item.period_index,
                        signal_key=item.signal_key,
                        value_text=item.value,
                    )
                    for item in payload.edits
                ],
                change_summary=payload.change_summary,
                created_by=current_user_email(request),
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except (TimeSeriesCatalogError, ValueError) as error:
            return JSONResponse(
                error_response_body(
                    "time_series_set_values", str(error), phase="python_validation"
                ),
                status_code=400,
            )
        return {"time_series_set": updated_set}

    @app.post(
        "/api/projects/{project_id}/time-series-sets/{time_series_set_id}/replace/upload",
        status_code=201,
    )
    async def upload_time_series_set_replacement_source(
        project_id: int,
        time_series_set_id: int,
        source_file: UploadFile = File(...),
        sheet_name: str | None = Form(None),
    ):
        try:
            analyst_store.get_time_series_set(project_id, time_series_set_id)
            content = await source_file.read()
            source = ingest_time_series_source(
                draft_document={},
                original_filename=source_file.filename or "source.csv",
                content_type=source_file.content_type,
                content=content,
                input_source_root=configured_input_source_root,
                sheet_name=sheet_name,
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except TimeSeriesIngestionError as error:
            return JSONResponse(error_response_body("source_file", str(error)), status_code=400)
        finally:
            await source_file.close()
        return {"source": source}

    @app.post("/api/projects/{project_id}/time-series-sets/{time_series_set_id}/replace")
    async def replace_project_time_series_set(
        project_id: int,
        time_series_set_id: int,
        payload: TimeSeriesSetReplaceRequest,
        request: Request,
    ):
        try:
            existing_set = analyst_store.get_time_series_set(project_id, time_series_set_id)
            source = payload.source.model_dump()
            _columns, rows = read_time_series_source_rows(source, configured_input_source_root)
            prepared_import = prepare_time_series_catalog_import(
                rows=rows,
                request=PreparedCatalogImportRequest(
                    set_name=existing_set["name"],
                    version_label=existing_set["version_label"],
                    data_kind=payload.data_kind,
                    timezone=payload.timezone,
                    timestamp_column=payload.timestamp_column,
                    duration_hours_column=payload.duration_hours_column,
                    value_column=payload.value_column,
                    signal_key=payload.signal_key,
                    source_unit=payload.source_unit,
                    signal_mappings=[
                        PreparedCatalogSignalMappingRequest(
                            source_column=item.source_column,
                            signal_key=item.signal_key,
                            source_unit=item.source_unit,
                        )
                        for item in payload.signal_mappings
                    ],
                ),
            )
            updated_set = analyst_store.replace_time_series_set_source(
                project_id=project_id,
                time_series_set_id=time_series_set_id,
                source=source,
                prepared_import=prepared_import,
                created_by=current_user_email(request),
                change_summary=payload.change_summary,
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except TimeSeriesIngestionError as error:
            return JSONResponse(error_response_body("source_file", str(error)), status_code=400)
        except (TimeSeriesCatalogError, ValueError) as error:
            return JSONResponse(
                error_response_body(
                    "catalog_import",
                    time_series_source_error_detail(source, str(error)),
                    phase="python_validation",
                ),
                status_code=400,
            )
        return {"time_series_set": updated_set}

    @app.put("/api/scenarios/{scenario_id}/draft")
    async def update_scenario_draft(scenario_id: int, payload: ScenarioDraftWriteRequest):
        if payload.document is None:
            raise HTTPException(status_code=400, detail="draft document is required")
        try:
            draft = analyst_store.update_scenario_draft(
                scenario_id=scenario_id,
                document=payload.document,
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return {**draft, **blocked_console_warning(scenario_id)}

    def build_case_input_variant_detail(scenario_id: int, variant: dict[str, Any]) -> dict[str, Any]:
        return {
            "variant": variant,
            "bindings": analyst_store.list_case_time_series_bindings(variant["id"]),
            "required_signals": analyst_store.evaluate_case_input_variant_required_signals(
                scenario_id=scenario_id, case_input_variant_id=variant["id"]
            ),
            "staleness": analyst_store.evaluate_case_input_variant_staleness(
                scenario_id=scenario_id, case_input_variant_id=variant["id"]
            ),
        }

    def get_case_and_variant_for_scenario(scenario_id: int, variant_id: int) -> tuple[dict[str, Any], dict[str, Any]]:
        case = analyst_store.get_or_create_case_for_scenario(scenario_id)
        variant = analyst_store.get_case_input_variant_for_case(case["id"], variant_id)
        return case, variant

    @app.get("/api/scenarios/{scenario_id}/case/default-variant")
    async def get_default_input_variant(scenario_id: int):
        try:
            case = analyst_store.get_or_create_case_for_scenario(scenario_id)
            variant = analyst_store.get_or_create_default_input_variant(case["id"])
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return {"case": optimization_case_public_dict(case), **build_case_input_variant_detail(scenario_id, variant)}

    @app.get("/api/scenarios/{scenario_id}/case/variants")
    async def list_case_input_variants(scenario_id: int):
        try:
            case = analyst_store.get_or_create_case_for_scenario(scenario_id)
            default_variant = analyst_store.get_or_create_default_input_variant(case["id"])
            variants = analyst_store.list_case_input_variants(case["id"])
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return {
            "case": optimization_case_public_dict(case),
            "default_variant_id": default_variant["id"],
            "variants": [build_case_input_variant_detail(scenario_id, variant) for variant in variants],
        }

    @app.post("/api/scenarios/{scenario_id}/case/variants", status_code=201)
    async def create_case_input_variant(
        scenario_id: int, payload: CaseInputVariantWriteRequest, request: Request
    ):
        try:
            case = analyst_store.get_or_create_case_for_scenario(scenario_id)
            variant = analyst_store.create_case_input_variant(
                case_id=case["id"],
                display_name=payload.display_name,
                created_by=current_user_email(request),
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        return variant

    @app.post("/api/scenarios/{scenario_id}/case/variants/{variant_id}/clone", status_code=201)
    async def clone_case_input_variant(
        scenario_id: int,
        variant_id: int,
        payload: CaseInputVariantWriteRequest,
        request: Request,
    ):
        try:
            case, _ = get_case_and_variant_for_scenario(scenario_id, variant_id)
            clone = analyst_store.clone_case_input_variant(
                case_id=case["id"],
                source_variant_id=variant_id,
                display_name=payload.display_name,
                created_by=current_user_email(request),
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        return clone

    @app.patch("/api/scenarios/{scenario_id}/case/variants/{variant_id}")
    async def update_case_input_variant(
        scenario_id: int,
        variant_id: int,
        payload: CaseInputVariantWriteRequest,
        request: Request,
    ):
        try:
            case, _ = get_case_and_variant_for_scenario(scenario_id, variant_id)
            variant = analyst_store.update_case_input_variant(
                case_id=case["id"],
                variant_id=variant_id,
                display_name=payload.display_name,
                updated_by=current_user_email(request),
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        return variant

    @app.post("/api/scenarios/{scenario_id}/case/variants/{variant_id}/bindings", status_code=201)
    async def bind_case_time_series(
        scenario_id: int, variant_id: int, payload: CaseTimeSeriesBindingRequest, request: Request
    ):
        try:
            case, _ = get_case_and_variant_for_scenario(scenario_id, variant_id)
            binding = analyst_store.upsert_case_time_series_binding(
                case_input_variant_id=variant_id,
                signal_key=payload.signal_key,
                entity_type=payload.entity_type,
                entity_id=payload.entity_id,
                time_series_set_id=payload.time_series_set_id,
                created_by=current_user_email(request),
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return binding

    @app.post("/api/scenarios/{scenario_id}/case/variants/{variant_id}/validate")
    async def validate_case_input_variant(
        scenario_id: int, variant_id: int, payload: CaseInputVariantRunRequest
    ):
        try:
            case, _ = get_case_and_variant_for_scenario(scenario_id, variant_id)
            validated = analyst_store.validate_case_input_variant(
                scenario_id=scenario_id,
                case_input_variant_id=variant_id,
                range_start=payload.range_start,
                range_end=payload.range_end,
            )
            analyst_store.clear_resolved_operator_console_wait_for_variant(
                variant_id
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except (DraftGenerationError, InputVariantRangeError, MissingRequiredSignalsError) as error:
            return JSONResponse(
                error_response_body("input_variant", str(error), phase="python_validation"),
                status_code=400,
            )
        return {"status": "valid", "series_bindings": validated["series_bindings"]}

    @app.post("/api/scenarios/{scenario_id}/case/variants/{variant_id}/run", status_code=201)
    async def run_case_input_variant(
        scenario_id: int,
        variant_id: int,
        payload: CaseInputVariantRunRequest,
        request: Request,
    ):
        request_id = request.headers.get("x-request-id") or f"req_{secrets.token_hex(8)}"
        try:
            case, variant = get_case_and_variant_for_scenario(scenario_id, variant_id)
            actor_user = getattr(request.state, "current_user", None) or {
                "id": None,
                "email": "internal_analyst",
                "display_name": "Internal analyst",
                "role": "analyst",
            }
            canonical = analyst_store.materialize_run_from_canonical_bindings(
                scenario_id=scenario_id,
                variant_id=variant_id,
                range_start=payload.range_start,
                range_end=payload.range_end,
                validate_text=service.validate_text,
                actor_user=actor_user,
                request_id=request_id,
                expected_bindings_revision=payload.expected_bindings_revision,
            )
            if canonical is not None:
                run = canonical["run"]
                local_run_queue.enqueue(run["id"])
                return run
            analyst_store.assert_case_bindings_executable(
                scenario_id=scenario_id, variant_id=variant_id
            )
            materialized = analyst_store.materialize_system_case_for_variant(
                scenario_id=scenario_id,
                case_input_variant_id=variant_id,
                range_start=payload.range_start,
                range_end=payload.range_end,
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except BindingMutationError as error:
            return JSONResponse(
                binding_error_payload(error, request_id=request_id),
                status_code=409,
                headers={"Cache-Control": "private, no-store"},
            )
        except CanonicalRunValidationError as error:
            return JSONResponse(
                validation_response_body(error.validation_result), status_code=400
            )
        except (DraftGenerationError, InputVariantRangeError, MissingRequiredSignalsError, VariantStaleError) as error:
            return JSONResponse(
                error_response_body("input_variant", str(error), phase="python_validation"),
                status_code=400,
            )

        generation_metadata = {
            "kind": "case_input_variant",
            "input_variant": {"id": variant_id, "display_name": variant["display_name"]},
            "date_range": {"start": payload.range_start, "end": payload.range_end},
            "series_bindings": materialized["series_bindings"],
        }
        scenario_version, error = save_validated_scenario_version(
            scenario_id,
            json.dumps(materialized["system_case"], sort_keys=True),
            generation_metadata,
        )
        if error is not None:
            return JSONResponse(validation_response_body(error), status_code=400)
        run = create_and_enqueue_run(scenario_version["id"])
        return run

    def operator_console_blocking(console_id: int) -> dict[str, Any]:
        """The internal view of a block: public reason plus its raw detail.

        Structural validation of the document never resolves pointers, so a
        dependency that moved under the console shows up here instead. The raw
        reasons stay on this internal surface and never reach the operator.
        """

        block = analyst_store.describe_operator_console_block(console_id)
        gate = build_console_run_gate(
            unavailable_parameter=block["unavailable_parameter"],
            unavailable_series=block["unavailable_series"],
            moved_dependency=block["moved_dependency"],
        )
        response = {"reason": gate["reason"], "reasons": block["reasons"]}
        if gate["reason"] == "dependencia_movida":
            console = analyst_store.get_operator_console(console_id)
            period = analyst_store.resolve_operator_console_period(console_id)
            response["action"] = {
                "kind": "revalidate_variant",
                "variant_id": int(console["owned_variant_id"]),
                "range_start": period["selected_start"],
                "range_end": period["selected_end"],
            }
        elif gate["reason"] == "campo_no_disponible":
            console = analyst_store.get_operator_console(console_id)
            unavailable_parameters = analyst_store.resolve_operator_console_parameters(
                console_id
            )["unavailable_ids"]
            if unavailable_parameters:
                parameter_id = str(unavailable_parameters[0])
                parameter = next(
                    configured
                    for configured in console["document"].get("parameters") or []
                    if str(configured["id"]) == parameter_id
                )
                response["action"] = {
                    "kind": "edit_configuration",
                    "target": {
                        "section": "parameters",
                        "id": parameter_id,
                        "label": str(parameter["label"]),
                    },
                }
            else:
                unavailable_columns = analyst_store.resolve_operator_console_group_metadata(
                    console_id
                )["unavailable_columns"]
                if unavailable_columns:
                    column = unavailable_columns[0]
                    response["action"] = {
                        "kind": "edit_configuration",
                        "target": {
                            "section": "groups",
                            "group_id": column["group_id"],
                            "id": column["column_id"],
                            "label": column["column_label"],
                        },
                    }
        return response

    def console_run_gate(
        console: Mapping[str, Any],
        *,
        viewer_user_id: int | None = None,
    ) -> dict[str, Any]:
        """The one gate every console surface answers with."""

        block = analyst_store.describe_operator_console_block(
            int(console["id"]), viewer_user_id=viewer_user_id
        )
        return build_console_run_gate(
            editing_locked_by=block["editing_locked_by"],
            unavailable_parameter=block["unavailable_parameter"],
            unavailable_series=block["unavailable_series"],
            moved_dependency=block["moved_dependency"],
            contact=console_preparer_name(console["prepared_by_user_id"]),
            review_requested_at=console["waiting_since"],
        )

    def operator_console_detail(
        scenario_id: int,
        console: dict[str, Any],
        request: Request | None = None,
    ) -> dict[str, Any]:
        owned_variant = analyst_store.get_case_input_variant(int(console["owned_variant_id"]))
        latest_failed_run = next(
            (
                run
                for run in analyst_store.list_operator_console_runs(
                    int(console["id"])
                )
                if run["status"] == "failed"
            ),
            None,
        )
        group_leases = []
        for group in console["document"].get("groups") or []:
            lease = analyst_store.describe_operator_console_group_lease(
                int(console["id"]), group_id=str(group["id"])
            )
            if lease["holder_user_id"] is None:
                continue
            group_leases.append(
                {
                    "group_id": str(group["id"]),
                    "group_label": str(group.get("label") or group["id"]),
                    "holder_name": lease["holder_name"],
                    "expires_at": lease["expires_at"],
                }
            )
        viewer = getattr(request.state, "current_user", None) if request else None
        return {
            "id": console["id"],
            "scenario_id": scenario_id,
            "case_id": console["case_id"],
            "status": console["status"],
            "revision": console["revision"],
            "document": console["document"],
            "owned_variant": {
                "id": owned_variant["id"],
                "display_name": owned_variant["display_name"],
            },
            "prepared_by": portal_configuration_editor_email(console["prepared_by_user_id"]),
            "created_at": console["created_at"],
            "created_by": portal_configuration_editor_email(console["created_by_user_id"]),
            "updated_at": console["updated_at"],
            "updated_by": portal_configuration_editor_email(console["updated_by_user_id"]),
            "waiting_since": console["waiting_since"],
            "blocking": operator_console_blocking(int(console["id"])),
            "technical_failure": (
                {
                    "reference": str(latest_failed_run["id"]),
                    "run_id": int(latest_failed_run["id"]),
                }
                if latest_failed_run is not None
                else None
            ),
            "can_force_release": bool(
                not auth_required or (viewer and viewer.get("role") == "admin")
            ),
            "group_leases": group_leases,
            "series_copies": analyst_store.list_operator_console_series_copy_audit(
                int(console["id"])
            ),
        }

    def get_console_for_scenario(scenario_id: int, console_id: int) -> dict[str, Any]:
        case = analyst_store.get_or_create_case_for_scenario(scenario_id)
        console = analyst_store.get_operator_console(console_id)
        if int(console["case_id"]) != int(case["id"]):
            raise KeyError(f"operator console {console_id} not found in scenario {scenario_id}")
        return console

    @app.get("/api/scenarios/{scenario_id}/consoles")
    async def list_operator_consoles(scenario_id: int, request: Request):
        try:
            case = analyst_store.get_or_create_case_for_scenario(scenario_id)
            consoles = analyst_store.list_operator_consoles(case["id"])
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return {
            "operator_consoles": [
                operator_console_detail(scenario_id, console, request)
                for console in consoles
            ]
        }

    @app.post("/api/scenarios/{scenario_id}/consoles", status_code=201)
    async def create_operator_console(
        scenario_id: int,
        payload: OperatorConsoleCreateRequest,
        request: Request,
    ):
        try:
            document = validate_operator_console_config_document(payload.document)
            case = analyst_store.get_or_create_case_for_scenario(scenario_id)
            console = analyst_store.create_operator_console(
                case_id=case["id"],
                source_variant_id=payload.source_variant_id,
                document=document,
                created_by_user_id=current_user_id(request),
                created_by=current_user_email(request),
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except OperatorConsoleConfigurationError as error:
            raise HTTPException(status_code=error.status_code, detail=error.message) from error
        return {
            "operator_console": operator_console_detail(
                scenario_id, console, request
            )
        }

    @app.get("/api/scenarios/{scenario_id}/consoles/{console_id}")
    async def get_operator_console(
        scenario_id: int, console_id: int, request: Request
    ):
        try:
            console = get_console_for_scenario(scenario_id, console_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return {
            "operator_console": operator_console_detail(
                scenario_id, console, request
            )
        }

    @app.put("/api/scenarios/{scenario_id}/consoles/{console_id}")
    async def save_operator_console(
        scenario_id: int,
        console_id: int,
        payload: OperatorConsoleWriteRequest,
        request: Request,
    ):
        try:
            get_console_for_scenario(scenario_id, console_id)
            document = validate_operator_console_config_document(payload.document)
            status = validate_operator_console_status(payload.status)
            console = analyst_store.save_operator_console(
                console_id,
                document=document,
                status=status,
                expected_revision=payload.expected_revision,
                updated_by_user_id=current_user_id(request),
            )
            analyst_store.clear_resolved_operator_console_wait(console_id)
            console = analyst_store.get_operator_console(console_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except OperatorConsoleConfigurationError as error:
            raise HTTPException(status_code=error.status_code, detail=error.message) from error
        return {
            "operator_console": operator_console_detail(
                scenario_id, console, request
            )
        }

    @app.delete(
        "/api/scenarios/{scenario_id}/consoles/{console_id}"
        "/groups/{group_id}/lease",
        status_code=204,
    )
    async def force_release_console_group_lease(
        scenario_id: int,
        console_id: int,
        group_id: str,
        request: Request,
    ):
        require_admin_user(request)
        try:
            get_console_for_scenario(scenario_id, console_id)
            analyst_store.force_release_operator_console_group_lease(
                console_id, group_id=group_id
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return Response(status_code=204)

    @app.post(
        "/api/scenarios/{scenario_id}/consoles/{console_id}"
        "/restore-series/{copy_id}"
    )
    async def restore_console_series_revision(
        scenario_id: int,
        console_id: int,
        copy_id: int,
        payload: ConsoleSeriesRestoreRequest,
        request: Request,
    ):
        try:
            get_console_for_scenario(scenario_id, console_id)
            restored = analyst_store.restore_operator_console_series_copy_revision(
                console_id,
                copy_id=copy_id,
                revision_number=payload.revision_number,
                expected_current_revision=payload.expected_current_revision,
                actor_user_id=current_user_id(request),
                note=payload.note,
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ConsoleSeriesError as error:
            raise HTTPException(
                status_code=error.status_code, detail=error.message
            ) from error
        return {"restored": restored}

    def console_preparer_name(user_id: int | None) -> str | None:
        if user_id is None:
            return None
        try:
            user = analyst_store.get_user(int(user_id))
        except KeyError:
            return None
        return str(user["display_name"] or user["email"])

    def operator_console_for_viewer(request: Request, console_id: int) -> dict[str, Any]:
        """Resolve a console for whoever is asking, or refuse to admit it exists."""

        try:
            console = analyst_store.get_operator_console(console_id)
            location = analyst_store.get_operator_console_location(console_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail="console not found") from error

        user = getattr(request.state, "current_user", None)
        if user is None or user.get("role") in {"admin", "analyst"}:
            return {"console": console, "location": location, "internal": True}
        if console["status"] != "active" or not analyst_store.external_has_project_capability(
            user_id=int(user["id"]),
            project_id=int(location["project_id"]),
            capability="operate",
        ):
            raise HTTPException(status_code=404, detail="console not found")
        return {"console": console, "location": location, "internal": False}

    @app.get("/api/console")
    async def list_operable_consoles(request: Request):
        user = getattr(request.state, "current_user", None)
        if user is None or user.get("role") in {"admin", "analyst"}:
            # Internal users see every active console so they can test them.
            consoles = []
            for console in analyst_store.list_all_operator_consoles():
                if console["status"] != "active":
                    continue
                location = analyst_store.get_operator_console_location(console["id"])
                consoles.append(
                    {**console, "project_name": location["project_name"]}
                )
        else:
            consoles = analyst_store.list_operable_operator_consoles(int(user["id"]))
        return {
            "consoles": [
                build_console_list_entry(
                    console=console, project_name=console["project_name"]
                )
                for console in consoles
            ]
        }

    @app.get("/api/console/{console_id}")
    async def get_console_shell(console_id: int, request: Request):
        resolved = operator_console_for_viewer(request, console_id)
        resolved_parameters = analyst_store.resolve_operator_console_parameters(console_id)
        resolved_period = analyst_store.resolve_operator_console_period(console_id)
        contact = console_preparer_name(resolved["console"]["prepared_by_user_id"])
        resolved_groups = analyst_store.resolve_operator_console_group_metadata(
            console_id
        )
        run_gate = console_run_gate(
            resolved["console"], viewer_user_id=current_user_id(request)
        )
        payload = build_console_payload(
            console=resolved["console"],
            prepared_by=contact,
            parameters=resolved_parameters["parameters"],
            run_gate=run_gate,
            period=resolved_period,
            history=analyst_store.list_operator_console_runs(console_id),
            groups=resolved_groups["groups"],
        )
        if resolved["internal"]:
            payload["internal_test"] = {
                "return_path": (
                    f"/scenarios/{resolved['location']['scenario_id']}"
                    f"/consoles/{console_id}"
                ),
                "tester": current_user_email(request),
            }
        return payload

    @app.post("/api/console/{console_id}/request-review")
    async def request_console_review(console_id: int, request: Request):
        """Mark that the operator is waiting on the preparer, and nothing else.

        No inbox, mail, push, escalation or expiry follows: the engineer reads
        `waiting_since` on the console list they already open.
        """

        resolved = operator_console_for_viewer(request, console_id)
        try:
            console = analyst_store.request_operator_console_review(console_id)
        except OperatorConsoleConfigurationError:
            return JSONResponse(
                {
                    "run_gate": console_run_gate(
                        resolved["console"], viewer_user_id=current_user_id(request)
                    )
                },
                status_code=409,
            )
        return {
            "run_gate": console_run_gate(
                console, viewer_user_id=current_user_id(request)
            )
        }

    @app.get("/api/console/{console_id}/series-options")
    async def get_console_series_options(console_id: int, request: Request):
        operator_console_for_viewer(request, console_id)
        try:
            resolved = analyst_store.resolve_operator_console_series_options(
                console_id
            )
        except ConsoleSeriesError as error:
            raise HTTPException(
                status_code=error.status_code, detail=error.message
            ) from error
        return build_console_series_options(resolved)

    @app.put("/api/console/{console_id}/series-selections")
    async def replace_console_series_selections(
        console_id: int,
        payload: ConsoleSeriesSelectionsWriteRequest,
        request: Request,
    ):
        operator_console_for_viewer(request, console_id)
        try:
            analyst_store.replace_operator_console_series_selections(
                console_id,
                selections=[selection.model_dump() for selection in payload.selections],
                actor_user_id=current_user_id(request),
            )
            resolved = analyst_store.resolve_operator_console_series_options(
                console_id
            )
        except ConsoleSeriesError as error:
            raise HTTPException(
                status_code=error.status_code, detail=error.message
            ) from error
        return build_console_series_options(resolved)

    @app.put("/api/console/{console_id}/parameters")
    async def replace_console_parameters(
        console_id: int,
        payload: ConsoleParametersWriteRequest,
        request: Request,
    ):
        resolved = operator_console_for_viewer(request, console_id)
        try:
            analyst_store.replace_operator_console_parameter_overrides(
                console_id,
                parameters=[parameter.model_dump() for parameter in payload.parameters],
                updated_by_user_id=current_user_id(request),
            )
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        parameters = analyst_store.resolve_operator_console_parameters(console_id)
        shell = build_console_payload(
            console=resolved["console"],
            prepared_by=console_preparer_name(resolved["console"]["prepared_by_user_id"]),
            parameters=parameters["parameters"],
        )
        return {"parameters": shell["parameters"]}

    def console_group_values_response(
        console_id: int,
        *,
        group_id: str,
        range_start: str,
        range_end: str,
        granularity: str,
        status_code: int = 200,
    ) -> JSONResponse:
        loaded = analyst_store.resolve_operator_console_group_values(
            console_id,
            group_id=group_id,
            range_start=range_start,
            range_end=range_end,
            granularity=granularity,
        )
        return JSONResponse(
            {"group_values": build_console_group_values(loaded)},
            status_code=status_code,
            headers={"ETag": f'"{loaded["token"]}"'},
        )

    def console_group_or_404(console: Mapping[str, Any], group_id: str) -> None:
        declared = {
            str(group["id"]) for group in console["document"].get("groups") or []
        }
        if str(group_id) not in declared:
            raise HTTPException(status_code=404, detail="group not found")

    def console_save_failure(error: ConsoleSeriesError) -> JSONResponse:
        return JSONResponse(
            {
                "save_error": build_console_save_error(
                    message=error.message,
                    cells=error.cells,
                    total_cells=error.total_cells,
                )
            },
            status_code=error.status_code,
        )

    @app.get("/api/console/{console_id}/groups/{group_id}/values")
    async def get_console_group_values(
        console_id: int,
        group_id: str,
        request: Request,
        start: str,
        end: str,
        granularity: str,
    ):
        resolved = operator_console_for_viewer(request, console_id)
        console_group_or_404(resolved["console"], group_id)
        try:
            return console_group_values_response(
                console_id,
                group_id=group_id,
                range_start=start,
                range_end=end,
                granularity=granularity,
            )
        except ConsoleSeriesError as error:
            return console_save_failure(error)
        except InputVariantRangeError as error:
            return JSONResponse(
                {
                    "failure": {
                        "cause": "rango_sin_cobertura",
                        "message": "El tramo elegido no tiene cobertura completa.",
                        "reference": None,
                    }
                },
                status_code=400,
            )

    @app.get("/api/console/{console_id}/groups/{group_id}/history")
    async def get_console_group_history(
        console_id: int, group_id: str, request: Request
    ):
        resolved = operator_console_for_viewer(request, console_id)
        console_group_or_404(resolved["console"], group_id)
        return {
            "history": analyst_store.list_operator_console_group_history(
                console_id,
                group_id=group_id,
                viewer_user_id=current_user_id(request),
            )
        }

    @app.post("/api/console/{console_id}/groups/{group_id}/undo")
    async def undo_console_group_save(
        console_id: int,
        group_id: str,
        payload: ConsoleUndoRequest,
        request: Request,
    ):
        resolved = operator_console_for_viewer(request, console_id)
        console_group_or_404(resolved["console"], group_id)
        expected_token = request.headers.get("if-match")
        if not expected_token:
            return JSONResponse(
                {
                    "save_error": build_console_save_error(
                        message=(
                            "vuelve a cargar el tramo antes de deshacer: falta la "
                            "referencia de version"
                        ),
                        cells=[],
                        total_cells=0,
                    )
                },
                status_code=428,
            )
        try:
            loaded = analyst_store.undo_operator_console_group_save(
                console_id,
                group_id=group_id,
                expected_token=expected_token.strip().strip('"'),
                actor_user_id=current_user_id(request),
                lease_token=payload.lease_token,
            )
        except ConsoleSeriesError as error:
            return console_save_failure(error)
        return JSONResponse(
            {"group_values": build_console_group_values(loaded)},
            headers={"ETag": f'"{loaded["token"]}"'},
        )

    @app.post("/api/console/{console_id}/groups/{group_id}/lease")
    async def acquire_console_group_lease(
        console_id: int, group_id: str, request: Request
    ):
        resolved = operator_console_for_viewer(request, console_id)
        console_group_or_404(resolved["console"], group_id)
        try:
            lease = analyst_store.acquire_operator_console_group_lease(
                console_id, group_id=group_id, user_id=current_user_id(request)
            )
        except ConsoleSeriesError as error:
            return console_save_failure(error)
        return {"lease": build_console_lease(lease)}

    @app.put("/api/console/{console_id}/groups/{group_id}/lease")
    async def heartbeat_console_group_lease(
        console_id: int,
        group_id: str,
        payload: ConsoleLeaseRequest,
        request: Request,
    ):
        resolved = operator_console_for_viewer(request, console_id)
        console_group_or_404(resolved["console"], group_id)
        try:
            lease = analyst_store.heartbeat_operator_console_group_lease(
                console_id,
                group_id=group_id,
                user_id=current_user_id(request),
                lease_token=payload.lease_token,
            )
        except ConsoleSeriesError as error:
            return console_save_failure(error)
        return {"lease": build_console_lease(lease)}

    @app.delete(
        "/api/console/{console_id}/groups/{group_id}/lease", status_code=204
    )
    async def release_console_group_lease(
        console_id: int, group_id: str, lease_token: str, request: Request
    ):
        resolved = operator_console_for_viewer(request, console_id)
        console_group_or_404(resolved["console"], group_id)
        analyst_store.release_operator_console_group_lease(
            console_id,
            group_id=group_id,
            user_id=current_user_id(request),
            lease_token=lease_token,
        )
        return Response(status_code=204)

    @app.put("/api/console/{console_id}/groups/{group_id}/values")
    async def save_console_group_values(
        console_id: int,
        group_id: str,
        payload: ConsoleGroupValuesWriteRequest,
        request: Request,
    ):
        resolved = operator_console_for_viewer(request, console_id)
        console_group_or_404(resolved["console"], group_id)
        expected_token = request.headers.get("if-match")
        if not expected_token:
            return JSONResponse(
                {
                    "save_error": build_console_save_error(
                        message=(
                            "vuelve a cargar el tramo antes de guardar: falta la "
                            "referencia de version"
                        ),
                        cells=[],
                        total_cells=0,
                    )
                },
                status_code=428,
            )
        try:
            analyst_store.save_operator_console_group_values(
                console_id,
                group_id=group_id,
                range_start=payload.range_start,
                range_end=payload.range_end,
                granularity=payload.granularity,
                expected_token=expected_token.strip().strip('"'),
                cells=[cell.model_dump() for cell in payload.cells],
                note=payload.note,
                actor_user_id=current_user_id(request),
                lease_token=payload.lease_token,
            )
        except ConsoleSeriesError as error:
            return console_save_failure(error)
        except InputVariantRangeError:
            return JSONResponse(
                {
                    "failure": {
                        "cause": "rango_sin_cobertura",
                        "message": "El tramo elegido no tiene cobertura completa.",
                        "reference": None,
                    }
                },
                status_code=400,
            )
        return console_group_values_response(
            console_id,
            group_id=group_id,
            range_start=payload.range_start,
            range_end=payload.range_end,
            granularity=payload.granularity,
        )

    @app.post("/api/console/{console_id}/runs", status_code=201)
    async def create_console_run(
        console_id: int,
        payload: ConsoleRunRequest,
        request: Request,
    ):
        resolved = operator_console_for_viewer(request, console_id)
        contact = console_preparer_name(resolved["console"]["prepared_by_user_id"])
        # Fail closed before anything immutable exists: the same gate the shell
        # showed decides here too.
        gate = console_run_gate(
            resolved["console"], viewer_user_id=current_user_id(request)
        )
        if not gate["can_run"]:
            return JSONResponse({"run_gate": gate}, status_code=409)
        try:
            materialized = analyst_store.materialize_operator_console_run(
                console_id,
                range_start=payload.range_start,
                range_end=payload.range_end,
            )
        except InputVariantRangeError:
            return JSONResponse(
                {
                    "failure": {
                        "cause": "rango_sin_cobertura",
                        "message": "El periodo elegido no tiene cobertura completa.",
                        "reference": None,
                    }
                },
                status_code=400,
            )
        except (DraftGenerationError, MissingRequiredSignalsError):
            return JSONResponse(
                {
                    "failure": {
                        "cause": "serie_incompleta",
                        "message": "Faltan datos requeridos para el periodo elegido.",
                        "reference": None,
                    }
                },
                status_code=400,
            )
        except VariantStaleError:
            # The materialization refuses in its own right; the operator still
            # only ever learns the public reason.
            return JSONResponse(
                {
                    "run_gate": build_console_run_gate(
                        moved_dependency=True,
                        contact=contact,
                        review_requested_at=resolved["console"]["waiting_since"],
                    )
                },
                status_code=409,
            )
        except ValueError as error:
            return JSONResponse(
                {
                    "failure": {
                        "cause": "parametro_fuera_de_rango",
                        "message": str(error),
                        "reference": None,
                    }
                },
                status_code=400,
            )

        actor = getattr(request.state, "current_user", None) or {}
        actor_email = current_user_email(request)
        actor_display_name = str(actor.get("display_name") or actor_email)
        lineage = materialized["lineage"]
        scenario_version, error = save_validated_scenario_version(
            int(resolved["location"]["scenario_id"]),
            json.dumps(materialized["system_case"], sort_keys=True),
            lineage,
            created_by=actor_email,
        )
        if error is not None:
            return JSONResponse(
                {
                    "failure": {
                        "cause": "serie_incompleta",
                        "message": error.message,
                        "reference": None,
                    }
                },
                status_code=400,
            )
        run = create_and_enqueue_run(
            scenario_version["id"],
            triggered_by=actor_email,
            trigger_type="operator_console",
            triggered_by_user_id=current_user_id(request),
            triggered_by_display_name=actor_display_name,
            operator_console_id=console_id,
            operator_console_revision=int(resolved["console"]["revision"]),
            materialized_lineage=lineage,
        )
        return {"run": build_console_run_entry(run)}

    @app.get("/api/console/{console_id}/runs")
    async def list_console_runs(console_id: int, request: Request):
        operator_console_for_viewer(request, console_id)
        return {
            "history": [
                build_console_run_entry(run)
                for run in analyst_store.list_operator_console_runs(console_id)
            ]
        }

    def console_run_or_404(console_id: int, run_id: int) -> dict[str, Any]:
        """A public history id only ever names a run of its own console."""

        try:
            run = analyst_store.get_run(run_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail="run not found") from error
        if int(run.get("operator_console_id") or 0) != int(console_id):
            raise HTTPException(status_code=404, detail="run not found")
        return run

    def console_results_block(
        console: Mapping[str, Any], run: Mapping[str, Any]
    ) -> dict[str, Any] | None:
        """The single configured allowlist run detail and comparison share.

        A run that has not succeeded, or whose artifacts cannot be read, has no
        block at all: the technical reason stays on the internal surfaces.
        """

        if run["status"] != "succeeded":
            return None
        configured = console["document"].get("results") or {}
        results_document = {
            "sections": {
                "kpis": {
                    "enabled": bool(configured.get("kpis")),
                    "label": "Indicadores" if configured.get("kpis") else "",
                    "items": configured.get("kpis") or [],
                },
                "charts": {
                    "enabled": bool(configured.get("charts")),
                    "label": "Graficos" if configured.get("charts") else "",
                    "items": configured.get("charts") or [],
                },
                "tables": {
                    "enabled": bool(configured.get("tables")),
                    "label": "Tablas" if configured.get("tables") else "",
                    "items": configured.get("tables") or [],
                },
                "downloads": {"enabled": False, "label": ""},
            }
        }
        try:
            results = read_run_results(
                run,
                analyst_store.list_run_artifacts(int(run["id"])),
                configured_artifact_root,
            )
        except ResultReadError:
            return None
        return build_results_block(results_document, results)

    @app.get("/api/console/{console_id}/runs/{run_id}")
    async def get_console_run(console_id: int, run_id: int, request: Request):
        resolved = operator_console_for_viewer(request, console_id)
        run = console_run_or_404(console_id, run_id)
        failure = None
        if run["status"] == "failed":
            failure = {
                "cause": "ejecucion_fallida",
                "message": "La ejecucion fallo. Comunica la referencia al ingeniero.",
                "reference": str(run_id),
            }
        return {
            "run": build_console_run_entry(run),
            "failure": failure,
            "results_block": console_results_block(resolved["console"], run),
        }

    @app.get("/api/console/{console_id}/run-comparison")
    async def get_console_run_comparison(
        console_id: int, request: Request, left: int, right: int
    ):
        resolved = operator_console_for_viewer(request, console_id)
        console = resolved["console"]
        sides = {
            side: {"run": run, "results_block": console_results_block(console, run)}
            for side, run in (
                ("left", console_run_or_404(console_id, left)),
                ("right", console_run_or_404(console_id, right)),
            )
        }
        return build_console_run_comparison(
            left=sides["left"], right=sides["right"]
        )

    @app.post("/api/scenarios/{scenario_id}/versions", status_code=201)
    async def create_scenario_version(scenario_id: int, payload: ScenarioVersionCreateRequest):
        try:
            scenario_version, error = save_validated_scenario_version(scenario_id, payload.system_case_json)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        if error is not None:
            return JSONResponse(validation_response_body(error), status_code=400)
        return scenario_version

    @app.post("/api/scenarios/{scenario_id}/versions/upload", status_code=201)
    async def upload_scenario_version(scenario_id: int, system_case_file: UploadFile = File(...)):
        try:
            candidate_text = (await system_case_file.read()).decode("utf-8")
        except UnicodeDecodeError:
            error = ValidationResult(
                ok=False,
                phase="json",
                message="Uploaded file must be UTF-8 encoded JSON",
                payload={"status": "error"},
            )
            return JSONResponse(validation_response_body(error), status_code=400)
        finally:
            await system_case_file.close()
        try:
            scenario_version, error = save_validated_scenario_version(scenario_id, candidate_text)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        if error is not None:
            return JSONResponse(validation_response_body(error), status_code=400)
        return scenario_version

    @app.get("/api/scenarios/{scenario_id}/versions")
    async def list_scenario_versions(scenario_id: int):
        try:
            versions = analyst_store.list_scenario_versions(scenario_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return {"versions": versions}

    @app.get("/api/scenarios/{scenario_id}/runs")
    async def list_scenario_runs(scenario_id: int):
        try:
            runs = analyst_store.list_scenario_runs(scenario_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return {"runs": runs}

    @app.get("/api/scenario-versions/{scenario_version_id}")
    async def get_scenario_version(scenario_version_id: int):
        try:
            scenario_version = analyst_store.get_scenario_version(scenario_version_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return {"scenario_version": scenario_version}

    @app.get("/api/scenario-versions/{scenario_version_id}/hydraulic-diagram-snapshot")
    async def get_scenario_version_hydraulic_diagram_snapshot(scenario_version_id: int):
        try:
            snapshot = analyst_store.get_scenario_version_hydraulic_diagram_snapshot(
                scenario_version_id
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return {"snapshot": snapshot}

    @app.delete("/api/scenario-versions/{scenario_version_id}")
    async def delete_scenario_version(scenario_version_id: int):
        try:
            deleted_version = analyst_store.delete_scenario_version(scenario_version_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return {"deleted_version": deleted_version}

    @app.post("/api/scenario-versions/{scenario_version_id}/runs", status_code=201)
    async def create_manual_run(scenario_version_id: int):
        try:
            run = create_and_enqueue_run(scenario_version_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return run

    @app.get("/api/runs/{run_id}")
    async def get_run(run_id: int):
        try:
            run = analyst_store.get_run(run_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return {"run": run}

    @app.get("/api/runs/{run_id}/results")
    async def get_run_results(run_id: int):
        try:
            run = analyst_store.get_run(run_id)
            artifacts = analyst_store.list_run_artifacts(run_id)
            results = read_run_results(run, artifacts, configured_artifact_root, store=analyst_store)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ResultReadError as error:
            return JSONResponse(
                {"status": "error", "message": error.message},
                status_code=error.status_code,
            )
        return {"results": results}

    @app.get("/api/admin/schedules")
    async def admin_list_run_schedules(request: Request):
        require_admin_user(request)
        return {
            "schedules": analyst_store.list_run_schedules(),
            "ticks": analyst_store.list_run_schedule_ticks(),
        }

    @app.post("/api/admin/schedules", status_code=201)
    async def admin_create_run_schedule(payload: RunScheduleCreateRequest, request: Request):
        require_admin_user(request)
        try:
            schedule = analyst_store.create_run_schedule(
                scenario_id=payload.scenario_id,
                case_input_variant_id=payload.case_input_variant_id,
                display_name=payload.display_name,
                range_start=payload.range_start,
                range_end=payload.range_end,
                cadence=payload.cadence,
                next_run_at=payload.next_run_at,
                range_mode=payload.range_mode,
                rolling_start_offset_hours=payload.rolling_start_offset_hours,
                rolling_duration_hours=payload.rolling_duration_hours,
                created_by=current_user_email(request),
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except (DraftGenerationError, ScheduleError, ValueError) as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        return {"schedule": schedule}

    @app.post("/api/admin/schedules/run-due")
    async def admin_run_due_schedules(payload: RunDueSchedulesRequest, request: Request):
        require_admin_user(request)
        now = payload.now or utc_now_iso()
        try:
            due_schedules = due_fixed_range_schedules(
                analyst_store.list_run_schedules(), now=now
            )
        except ScheduleError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

        ticks = [
            execute_fixed_range_schedule(
                store=analyst_store,
                validation_service=service,
                run_queue=local_run_queue,
                schedule=schedule,
                now=now,
                triggered_by=current_user_email(request),
            )
            for schedule in due_schedules
        ]
        return {"now": now, "due_count": len(due_schedules), "ticks": ticks}

    @app.post("/api/admin/runs/rebuild-results")
    async def admin_rebuild_all_run_results(request: Request, force: bool = False):
        require_admin_user(request)
        report = rebuild_all_run_results(store=analyst_store, artifact_root=configured_artifact_root, force=force)
        return {"rebuild": report}

    @app.post("/api/admin/runs/{run_id}/rebuild-results")
    async def admin_rebuild_run_results(run_id: int, request: Request, force: bool = False):
        require_admin_user(request)
        try:
            run = analyst_store.get_run(run_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        outcome = rebuild_run_results(store=analyst_store, run=run, artifact_root=configured_artifact_root, force=force)
        return {"rebuild": outcome}

    @app.post("/api/admin/runs/{run_id}/cleanup-results")
    async def admin_cleanup_run_results(run_id: int, payload: ResultCleanupRequest, request: Request):
        require_admin_user(request)
        try:
            cleanup = cleanup_run_result_data(
                store=analyst_store,
                run_id=run_id,
                targets=payload.targets,
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return {"cleanup": cleanup}

    @app.post("/api/admin/projects/{project_id}/cleanup-results")
    async def admin_cleanup_project_results(project_id: int, payload: ResultCleanupRequest, request: Request):
        require_admin_user(request)
        try:
            cleanup = cleanup_project_result_data(
                store=analyst_store,
                project_id=project_id,
                targets=payload.targets,
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return {"cleanup": cleanup}

    @app.get("/api/run-comparisons")
    async def get_run_comparison(baseline_run_id: int, candidate_run_id: int, series: str | None = None):
        try:
            comparison = compare_runs(
                store=analyst_store,
                baseline_run_id=baseline_run_id,
                candidate_run_id=candidate_run_id,
                series=series,
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ComparisonError as error:
            return JSONResponse(
                {"status": "error", "message": error.message},
                status_code=error.status_code,
            )
        return {"comparison": comparison}

    @app.get("/api/runs/{run_id}/publications")
    async def list_run_publications(run_id: int):
        try:
            publications = analyst_store.list_run_publications(run_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return {"publications": publications}

    @app.get("/api/publications/{publication_id}/preview")
    async def get_publication_preview(publication_id: int):
        try:
            publication = analyst_store.get_publication(publication_id)
            project = analyst_store.get_project(publication["project_id"])
            version = analyst_store.get_scenario_version(
                publication["scenario_version_id"],
                include_document=False,
            )
            run = analyst_store.get_run(publication["run_id"])
            artifacts = analyst_store.list_run_artifacts(run["id"])
            downloads = publication_download_artifacts(
                publication,
                artifacts,
                lambda artifact: f"/api/run-artifacts/{artifact['id']}/download",
            )
            canonical_results = read_run_results(
                run, artifacts, configured_artifact_root, store=analyst_store
            )
            results_error = ""
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ResultReadError as error:
            canonical_results = None
            results_error = error.message
        payload = configured_portal_payload(
            project=project,
            publication=publication,
            results=canonical_results,
            downloads=downloads,
            logo_url=(
                f"/api/projects/{project['id']}/portal-configuration/logo"
            ),
        )
        # The preview shows the client surface verbatim; navigation and the
        # technical reason for an unavailable result stay in this internal block.
        payload["preview_context"] = {
            "run_id": run["id"],
            "scenario_version_number": version["version_number"],
            "results_error": results_error,
        }
        return payload

    @app.post("/api/runs/{run_id}/publications", status_code=201)
    async def create_run_publication_draft(
        run_id: int,
        request: Request,
        payload: PublicationDraftWriteRequest,
    ):
        try:
            publication = analyst_store.create_publication_draft(
                run_id=run_id,
                dashboard_template_id=payload.dashboard_template_id,
                public_title=payload.public_title,
                analyst_notes=payload.analyst_notes,
                allowed_artifact_types=payload.allowed_artifact_types,
                created_by=current_user_email(request),
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        return {"publication": publication}

    @app.put("/api/publications/{publication_id}")
    async def update_publication_draft(
        publication_id: int,
        request: Request,
        payload: PublicationDraftWriteRequest,
    ):
        try:
            publication = analyst_store.update_publication_draft(
                publication_id,
                dashboard_template_id=payload.dashboard_template_id,
                public_title=payload.public_title,
                analyst_notes=payload.analyst_notes,
                allowed_artifact_types=payload.allowed_artifact_types,
                updated_by=current_user_email(request),
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        return {"publication": publication}

    @app.post("/api/publications/{publication_id}/publish")
    async def publish_publication(publication_id: int, request: Request):
        try:
            publication = analyst_store.publish_publication(
                publication_id,
                published_by=current_user_email(request),
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        return {"publication": publication}

    @app.post("/api/publications/{publication_id}/unpublish")
    async def unpublish_publication(publication_id: int, request: Request):
        try:
            publication = analyst_store.unpublish_publication(
                publication_id,
                unpublished_by=current_user_email(request),
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        return {"publication": publication}

    @app.get("/api/runs/{run_id}/artifacts")
    async def list_run_artifacts(run_id: int):
        try:
            artifacts = analyst_store.list_run_artifacts(run_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return {
            "artifacts": [
                artifact_response_body(artifact)
                for artifact in artifacts
                if artifact_path_is_safe(artifact["path"], configured_artifact_root)
            ]
        }

    @app.get("/api/run-artifacts/{artifact_id}/download")
    async def download_run_artifact(artifact_id: int):
        try:
            artifact = analyst_store.get_run_artifact(artifact_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        if not artifact_path_is_safe(artifact["path"], configured_artifact_root):
            raise HTTPException(status_code=404, detail="artifact not found")

        artifact_path = Path(artifact["path"])
        if not artifact_path.is_file():
            raise HTTPException(status_code=404, detail="artifact file not found")

        return FileResponse(
            artifact_path,
            media_type=artifact["media_type"],
            filename=artifact["display_name"],
        )

    return app


def validation_response_body(result: ValidationResult) -> dict:
    if result.ok:
        return {
            "status": "ok",
            "phase": result.phase,
            "message": result.message,
            "validation": result.payload,
        }

    return {
        "status": "error",
        "phase": result.phase,
        "error_category": validation_error_category(result),
        "message": result.message,
        "validation": result.payload,
    }


def validation_error_category(result: ValidationResult) -> str:
    if result.phase == "julia":
        return "julia_validation"
    return result.phase or "validation"


def error_response_body(error_category: str, detail: str, *, phase: str | None = None) -> dict:
    return {
        "status": "error",
        "phase": phase or error_category,
        "error_category": error_category,
        "detail": detail,
    }


def time_series_source_error_detail(source: dict[str, Any] | None, detail: str) -> str:
    if not isinstance(source, dict):
        return detail
    original_filename = str(source.get("original_filename") or "").strip()
    selected_sheet = str(source.get("selected_sheet") or "").strip()
    source_context = f"source {original_filename!r}" if original_filename else "source"
    if selected_sheet:
        source_context = f"{source_context}, sheet {selected_sheet!r}"
    return f"{source_context}: {detail}"


def draft_error_category(document: dict[str, Any], error: Exception) -> str:
    source_category = active_source_validation_category(document)
    if source_category:
        return source_category
    message = str(error)
    if message.startswith("Python time-series validation failed"):
        return "python_validation"
    return "python_validation"


def active_source_validation_category(document: dict[str, Any]) -> str:
    active_source = active_time_series_source(document)
    validation = active_source.get("validation") if isinstance(active_source, dict) else None
    if not isinstance(validation, dict):
        return ""
    category = validation.get("error_category")
    return str(category) if category else ""


def generation_metadata_from_draft(document: dict[str, Any]) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "kind": "structured_draft",
        "generated_at": utc_now_iso(),
    }
    source = active_time_series_source(document)
    if not isinstance(source, dict):
        return metadata

    source_metadata: dict[str, Any] = {
        "source_id": str(source.get("id") or ""),
        "kind": str(source.get("kind") or ""),
        "original_filename": str(source.get("original_filename") or ""),
        "media_type": str(source.get("media_type") or ""),
    }
    stored_path = source.get("stored_path")
    if stored_path:
        source_metadata["stored_filename"] = Path(str(stored_path)).name
    if source.get("selected_sheet"):
        source_metadata["selected_sheet"] = str(source.get("selected_sheet"))

    mapping = source.get("mapping") if isinstance(source.get("mapping"), dict) else {}
    metadata["source"] = source_metadata
    metadata["mapping"] = copy.deepcopy(mapping)
    return metadata


def active_time_series_source(document: dict[str, Any]) -> dict[str, Any] | None:
    time_series = document.get("time_series")
    if not isinstance(time_series, dict):
        return None
    sources = time_series.get("sources")
    if not isinstance(sources, list):
        return None
    active_source_id = time_series.get("active_source_id")
    active_source = None
    for source in sources:
        if isinstance(source, dict) and source.get("id") == active_source_id:
            active_source = source
            break
    if active_source is None:
        for source in sources:
            if isinstance(source, dict):
                active_source = source
                break
    return active_source


def draft_document_with_generated_validation(
    document: dict[str, Any],
    system_case: dict[str, Any],
    result: ValidationResult,
) -> dict[str, Any]:
    updated = copy.deepcopy(document)
    updated["generated_system_case"] = generated_system_case_snapshot(system_case, result)
    return updated


def generated_system_case_snapshot(system_case: dict[str, Any], result: ValidationResult) -> dict[str, Any]:
    validation = {
        "ok": result.ok,
        "phase": result.phase,
        "message": result.message,
        "payload": copy.deepcopy(result.payload),
    }
    if not result.ok:
        validation["error_category"] = validation_error_category(result)
    return {
        "system_case": copy.deepcopy(system_case),
        "validation": validation,
        **derive_case_hierarchy_provenance(system_case),
    }


def validated_generated_system_case_from_draft(document: dict[str, Any]) -> dict[str, Any]:
    system_case = generate_system_case_from_draft(document)
    if draft_has_current_successful_generated_validation(document, system_case):
        return system_case

    snapshot = document.get("generated_system_case")
    if not isinstance(snapshot, dict):
        raise DraftPromotionError("generated system case must be validated before promotion")

    validation = snapshot.get("validation")
    if not isinstance(validation, dict) or not validation.get("ok"):
        raise DraftPromotionError("generated system case validation must succeed before promotion")

    previous_system_case = snapshot.get("system_case")
    if isinstance(previous_system_case, dict):
        stale_state = hierarchy_stale_state(previous_system_case, system_case)
        if stale_state is not None:
            raise DraftPromotionError(
                hierarchy_stale_summary("generated system case validation", stale_state)
                + "; validate again before promotion"
            )

    raise DraftPromotionError("generated system case validation is stale; validate again before promotion")


def draft_has_current_successful_generated_validation(
    document: dict[str, Any],
    system_case: dict[str, Any],
) -> bool:
    snapshot = document.get("generated_system_case")
    if not isinstance(snapshot, dict):
        return False
    validation = snapshot.get("validation")
    if not isinstance(validation, dict) or not validation.get("ok"):
        return False
    return snapshot.get("system_case") == system_case


def artifact_response_body(artifact: dict) -> dict:
    return {
        "id": artifact["id"],
        "run_id": artifact["run_id"],
        "artifact_type": artifact["artifact_type"],
        "path": artifact["path"],
        "display_name": artifact["display_name"],
        "media_type": artifact["media_type"],
        "byte_size": artifact["byte_size"],
        "created_at": artifact["created_at"],
        "download_url": f"/api/run-artifacts/{artifact['id']}/download",
    }


def publication_download_response_body(artifact: dict) -> dict:
    return {
        "artifact_type": artifact["artifact_type"],
        "display_name": artifact["display_name"],
        "media_type": artifact["media_type"],
        "byte_size": artifact["byte_size"],
    }


def artifact_path_is_safe(path: str, artifact_root: Path) -> bool:
    root = artifact_root.resolve(strict=False)
    resolved_path = Path(path).resolve(strict=False)
    try:
        resolved_path.relative_to(root)
    except ValueError:
        return False
    return True


def create_initial_draft_document(
    analyst_store: AnalystStore,
    scenario_id: int,
    source_version_id: int | None,
) -> dict[str, Any]:
    if source_version_id is None:
        scenario = analyst_store.get_scenario(scenario_id)
        return empty_scenario_draft_document(scenario["name"])

    source_version = analyst_store.get_scenario_version(source_version_id)
    if source_version["scenario_id"] != scenario_id:
        raise KeyError(f"scenario version {source_version_id} not found for scenario {scenario_id}")
    return scenario_draft_document_from_version(source_version)


def empty_scenario_draft_document(case_name: str) -> dict[str, Any]:
    return {
        "schema_version": "bess_editor_draft.v1",
        "case": {"name": case_name},
        "source": None,
        "pcc": {"id": "bus_1", "type": "bus"},
        "grid": {
            "id": "grid_1",
            "import_power_max_mw": None,
            "export_power_max_mw": None,
            "prevent_simultaneous_grid_import_export": True,
        },
        "assets": [],
        "time_series": {"sources": []},
        "solver": {"name": "HiGHS", "options": {}},
    }


def scenario_draft_document_from_version(source_version: dict[str, Any]) -> dict[str, Any]:
    system_case = source_version["system_case_json"]
    return structured_draft_document_from_system_case(
        system_case,
        source={
            "kind": "scenario_version",
            "scenario_version_id": source_version["id"],
            "version_number": source_version["version_number"],
        },
    )


def legacy_path_to_react_path(path: str) -> str:
    safe_path = safe_internal_next_path(path)
    if not safe_path or safe_path == "/":
        return "/react"
    if safe_path == "/system-cases/validate":
        return "/react/system"
    if safe_path in {"/login", "/bootstrap", "/logout"}:
        return "/react"
    if safe_path == "/react" or safe_path.startswith("/react/"):
        return safe_path
    return f"/react{safe_path}"


def current_user_id(request: Request) -> int | None:
    user = getattr(request.state, "current_user", None)
    if isinstance(user, dict) and user.get("id") is not None:
        return int(user["id"])
    return None


def current_user_email(request: Request) -> str:
    user = getattr(request.state, "current_user", None)
    if isinstance(user, dict) and user.get("email"):
        return str(user["email"])
    return "internal_analyst"


def auth_enabled_from_env(default: bool) -> bool:
    raw_value = os.environ.get("BESS_AUTH_ENABLED")
    if raw_value is None:
        return default
    return raw_value.strip().lower() not in {"0", "false", "no", "off"}


def cookie_secure_from_env(default: bool) -> bool:
    raw_value = os.environ.get("BESS_SESSION_COOKIE_SECURE")
    if raw_value is None:
        return default
    return raw_value.strip().lower() not in {"0", "false", "no", "off"}


def safe_internal_next_path(next_path: str) -> str:
    if not next_path:
        return ""
    if not next_path.startswith("/") or next_path.startswith("//"):
        return ""
    return next_path


def react_root_of_path(path: str) -> str:
    """Which sibling application root a React path belongs to, if any."""

    if path != "/react" and not path.startswith("/react/"):
        return ""
    route = path[len("/react") :]
    if not route or route == "/":
        return ""
    if route == "/client" or route.startswith("/client/"):
        return "portal"
    if route == "/console" or route.startswith("/console/"):
        return "console"
    return "analyst"


def safe_react_next_path(next_path: str) -> str:
    safe_next = safe_internal_next_path(next_path)
    if not safe_next:
        return ""
    if safe_next in {"/react/login", "/react/bootstrap", "/react/logout"}:
        return ""
    if safe_next == "/react" or safe_next.startswith("/react/"):
        return safe_next
    return ""


def public_user_dict(user: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": user["id"],
        "email": user["email"],
        "display_name": user["display_name"],
        "role": user["role"],
        "is_active": user["is_active"],
        "created_at": user["created_at"],
        "updated_at": user["updated_at"],
    }


def is_valid_email(value: str) -> bool:
    return "@" in value and "." in value.rsplit("@", 1)[-1]


@lru_cache(maxsize=1)
def cached_plotly_javascript() -> str:
    return get_plotlyjs()


app = create_app(auth_enabled=auth_enabled_from_env(True))

