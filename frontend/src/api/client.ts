import type { components } from "./schema";
import type { CaseHierarchyProvenance } from "../caseHierarchy";

export type CurrentUser = components["schemas"]["CurrentUser"];
export type CurrentUserResponse = components["schemas"]["CurrentUserResponse"];
export type ProjectCreatePayload =
  components["schemas"]["ProjectCreateRequest"];
export type ScenarioCreatePayload =
  components["schemas"]["ScenarioCreateRequest"];
export type UserCreatePayload = components["schemas"]["UserCreateRequest"];

export type AuthSessionResponse = components["schemas"]["AuthSessionResponse"];

export interface BootstrapAdminPayload {
  email: string;
  display_name: string;
  password: string;
}

export interface LoginPayload {
  email: string;
  password: string;
  next: string;
}

export interface AdminUser extends CurrentUser {
  created_at: string;
  updated_at: string;
  created_by?: string;
  deactivated_at?: string | null;
}

export interface ExternalProjectAccess {
  project_id: number;
  user_id: number;
  email: string;
  display_name: string;
  role: string;
  is_active: boolean;
  assigned_at: string;
  assigned_by: string;
  portal_view: boolean;
  operate: boolean;
  updated_at: string;
  updated_by: string;
}

export interface ExternalProjectCapabilities {
  portal_view: boolean;
  operate: boolean;
}

export interface RunSchedule {
  id: number;
  scenario_id: number;
  case_id: number;
  case_input_variant_id: number;
  display_name: string;
  range_start: string;
  range_end: string;
  range_mode: string;
  rolling_start_offset_hours?: number | null;
  rolling_duration_hours?: number | null;
  cadence: string;
  next_run_at: string;
  topology_hash: string;
  parameter_hash: string;
  is_active: boolean;
  last_fired_at?: string | null;
  created_at: string;
  updated_at: string;
  created_by: string;
  updated_by: string;
}

export interface RunScheduleTick {
  id: number;
  schedule_id: number;
  due_at: string;
  fired_at: string;
  range_start: string;
  range_end: string;
  status: string;
  scenario_version_id?: number | null;
  run_id?: number | null;
  error_message: string;
  error_payload?: unknown;
  created_at: string;
  updated_at: string;
}

export interface RunScheduleCreatePayload {
  scenario_id: number;
  case_input_variant_id: number;
  display_name: string;
  range_start: string;
  range_end: string;
  range_mode: string;
  rolling_start_offset_hours?: number | null;
  rolling_duration_hours?: number | null;
  cadence: string;
  next_run_at: string;
}

export interface RunDueSchedulesPayload {
  now?: string | null;
}

export interface Project {
  id: number;
  name: string;
  description: string;
  created_at: string;
  created_by?: string;
}

export interface ProjectDeletionResult extends Project {
  deleted_scenario_count: number;
  deleted_run_count: number;
}

export interface Scenario {
  id: number;
  project_id: number;
  name: string;
  description: string;
  created_at: string;
  created_by?: string;
}

export interface ScenarioVersion {
  id: number;
  scenario_id: number;
  version_number: number;
  case_name: string;
  schema_version: string;
  period_count: number;
  asset_counts: Record<string, number>;
  generation_metadata: CaseHierarchyProvenance;
  created_at: string;
  created_by?: string;
}

export interface ScenarioVersionDetail extends ScenarioVersion {
  system_case_json: unknown;
  validation_payload: unknown;
}

export interface ScenarioRun {
  id: number;
  scenario_version_id: number;
  status: string;
  created_at: string;
  started_at?: string | null;
  finished_at?: string | null;
  duration_seconds?: number | null;
  exit_code?: number | null;
  error_message?: string | null;
  success_payload?: unknown;
  error_payload?: unknown;
  stdout?: string;
  stderr?: string;
  triggered_by?: string;
  trigger_type?: string;
}

export type ResultCell = string | number | boolean | null;

export interface ResultTable {
  columns: string[];
  rows: Array<Record<string, ResultCell>>;
}

export interface ResultChartSeries {
  key: string;
  label: string;
  unit?: string;
  source?: string;
  values: Array<number | null>;
}

export interface ResultChart {
  id: string;
  title: string;
  available: boolean;
  labels: string[];
  series: ResultChartSeries[];
  missing_columns?: string[];
  message?: string;
}

export interface RunResults {
  summary: Record<string, unknown>;
  dispatch_table: ResultTable;
  asset_dispatch_table: ResultTable;
  charts: Record<string, ResultChart | unknown>;
  plot_series?: unknown[];
}

export interface DashboardResults {
  summary: Record<string, unknown> | null;
  dispatch_table: ResultTable | null;
  asset_dispatch_table: ResultTable | null;
  charts: Record<string, ResultChart | unknown>;
  plot_series?: unknown[];
}

export interface RunComparisonKpi {
  key: string;
  baseline: ResultCell;
  candidate: ResultCell;
  delta: number | null;
}

export interface RunComparisonSeriesPeriod {
  timestamp: string;
  baseline: number | null;
  candidate: number | null;
  delta: number | null;
}

export interface RunComparisonSide {
  run_id: number;
  status: string;
  created_at?: string | null;
  finished_at?: string | null;
  scenario_version_id: number;
  input_variant?: { id: number; display_name?: string } | null;
  date_range?: { start: string; end: string } | null;
}

export interface RunComparison {
  baseline: RunComparisonSide;
  candidate: RunComparisonSide;
  kpis: RunComparisonKpi[];
  available_signal_keys: string[];
  selected_series: string | null;
  series_periods: RunComparisonSeriesPeriod[] | null;
}

export interface RunArtifact {
  id: number;
  run_id: number;
  artifact_type: string;
  path: string;
  display_name: string;
  media_type: string;
  byte_size: number;
  created_at: string;
  download_url: string;
}

export type DashboardTemplatePayload =
  components["schemas"]["DashboardTemplateWriteRequest"];

export interface DashboardTemplate extends DashboardTemplatePayload {
  id: number;
  project_id: number;
  created_at: string;
  updated_at: string;
  created_by?: string | null;
  updated_by?: string | null;
}

export type PublicationPayload =
  components["schemas"]["PublicationDraftWriteRequest"];

export interface Publication {
  id: number;
  project_id: number;
  scenario_id: number;
  scenario_version_id: number;
  run_id: number;
  dashboard_template_id: number;
  public_title: string;
  analyst_notes: string;
  allowed_artifact_types: string[];
  status: "draft" | "published" | "unpublished" | string;
  created_at: string;
  updated_at: string;
  published_at?: string | null;
  unpublished_at?: string | null;
  created_by?: string | null;
  updated_by?: string | null;
  published_by?: string | null;
  unpublished_by?: string | null;
}

export interface PublicationDownload {
  label: string;
  media_type: string;
  byte_size: number;
  download_url: string;
}

export type PortalKpiSign = "auto" | "always" | "never";

export type PortalKpiEmphasis = "normal" | "strong";

export interface PortalKpi {
  id: string;
  label: string;
  value: number | string;
  unit: string | null;
  decimals: number;
  sign: PortalKpiSign;
  emphasis: PortalKpiEmphasis;
}

export interface PortalConfigKpiItem {
  id: string;
  path: string;
  label: string;
  unit: string | null;
  decimals: number;
  sign: PortalKpiSign;
  emphasis: PortalKpiEmphasis;
}

export interface PortalConfigChartSeries {
  key: string;
  label: string;
}

export interface PortalConfigChartItem {
  id: string;
  chart_key: string;
  label: string;
  series: PortalConfigChartSeries[];
}

export interface PortalConfigTableColumn {
  key: string;
  id: string;
  label: string;
  unit: string | null;
}

export interface PortalConfigTableItem {
  id: string;
  table_key: string;
  label: string;
  row_limit: number;
  columns: PortalConfigTableColumn[];
}

export interface PortalConfigSection<TItem> {
  enabled: boolean;
  label: string;
  items: TItem[];
}

export interface PortalConfigDocument {
  schema_version: string;
  display_name: string;
  sections: {
    kpis: PortalConfigSection<PortalConfigKpiItem>;
    charts: PortalConfigSection<PortalConfigChartItem>;
    tables: PortalConfigSection<PortalConfigTableItem>;
    downloads: { enabled: boolean; label: string };
  };
}

export interface PortalCatalogSeries {
  key: string;
  label: string;
  unit: string;
}

export interface PortalCatalogChart {
  key: string;
  label: string;
  series: PortalCatalogSeries[];
}

export interface PortalCatalogColumn {
  key: string;
  label: string;
  unit: string | null;
}

export interface PortalCatalogTable {
  key: string;
  label: string;
  columns: PortalCatalogColumn[];
}

export interface PortalCatalogs {
  charts: PortalCatalogChart[];
  tables: PortalCatalogTable[];
}

export interface SignalCatalogEntry {
  signal_key: string;
  unit: string;
  entity_type: string | null;
  nonnegative: boolean;
}

export type OperatorConsoleStatus = "draft" | "active";

export interface OperatorConsoleSignal {
  entity_type: string;
  entity_id: string;
  signal_key: string;
}

export interface OperatorConsoleSourceOption {
  id: string;
  label: string;
  time_series_set_id: number;
}

export interface OperatorConsoleColumn {
  id: string;
  signal: OperatorConsoleSignal;
  label: string;
  editable: boolean;
  source_options: OperatorConsoleSourceOption[];
  default_source_option_id: string;
}

export interface OperatorConsoleGroup {
  id: string;
  label: string;
  granularities: string[];
  columns: OperatorConsoleColumn[];
}

export interface OperatorConsoleParameter {
  id: string;
  pointer: { asset_id: string; field: string };
  label: string;
  unit: string | null;
  min: number;
  max: number;
  default: number;
}

export interface OperatorConsoleDocument {
  schema_version: "operator_console_config.v1";
  public_identity: { name: string; description: string };
  parameters: OperatorConsoleParameter[];
  groups: OperatorConsoleGroup[];
  results: { kpis: unknown[]; charts: unknown[]; tables: unknown[] };
}

export interface OperatorConsoleBlocking {
  reason: string | null;
  reasons: Array<{
    dependency_type: string;
    dependency_id: string | null;
    detail: string;
  }>;
}

export interface OperatorConsole {
  id: number;
  scenario_id: number;
  case_id: number;
  status: OperatorConsoleStatus;
  revision: number;
  document: OperatorConsoleDocument;
  owned_variant: { id: number; display_name: string };
  prepared_by: string | null;
  created_at: string;
  created_by: string | null;
  updated_at: string;
  updated_by: string | null;
  waiting_since: string | null;
  blocking: OperatorConsoleBlocking;
}

export interface OperatorConsoleCreatePayload {
  source_variant_id: number;
  document: OperatorConsoleDocument;
}

export interface OperatorConsoleSavePayload {
  document: OperatorConsoleDocument;
  status: OperatorConsoleStatus;
  expected_revision: number;
}

export interface ConsoleListEntry {
  console: { id: number; name: string; description: string };
  project: { name: string };
  state: string;
}

export interface ConsoleShell {
  console: {
    id: number;
    name: string;
    description: string;
    prepared_by: string | null;
    updated_at: string;
  };
  period?: {
    available_start: string | null;
    available_end: string | null;
    selected_start: string | null;
    selected_end: string | null;
  };
  parameters?: ConsoleParameter[];
  groups?: ConsoleGroup[];
  run_gate?: ConsoleRunGate;
  internal_test?: { return_path: string; tester: string };
}

export interface ConsoleParameter {
  id: string;
  label: string;
  unit: string | null;
  min: number;
  max: number;
  default: number;
  value: number | null;
}

export interface ConsoleRunGate {
  can_run: boolean;
  reason: string | null;
  message: string;
  contact: string | null;
  editing_locked_by: string | null;
}

export interface ConsoleGroupColumn {
  id: string;
  label: string;
  unit: string | null;
  nonnegative: boolean;
  editable: boolean;
}

export interface ConsoleGroup {
  id: string;
  label: string;
  granularities: string[];
  columns: ConsoleGroupColumn[];
}

export interface ConsoleSeriesOption {
  id: string;
  label: string;
}

export interface ConsoleSeriesSelection {
  group_id: string;
  column_id: string;
  selected_source_option_id: string | null;
  options: ConsoleSeriesOption[];
}

export interface ConsoleSeriesOptions {
  selections: ConsoleSeriesSelection[];
}

export interface ConsoleGroupRow {
  index: number;
  timestamp: string;
  values: Record<string, number | null>;
}

export interface ConsoleGroupValues {
  group_id: string;
  granularity: string;
  range: { start: string; end: string };
  columns: ConsoleGroupColumn[];
  rows: ConsoleGroupRow[];
}

/** The grid plus the opaque version the next save must hand back. */
export interface ConsoleGroupValuesSnapshot {
  values: ConsoleGroupValues;
  etag: string;
}

export interface ConsoleLease {
  token: string;
  expires_at: string;
  holder_name: string;
}

export interface ConsoleSaveErrorCell {
  group_id: string;
  column_id: string;
  row_index: number | null;
  message: string;
}

/** A refused save, stated in the coordinates the operator can see. */
export class ConsoleSaveError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly cells: ConsoleSaveErrorCell[],
    readonly totalCells: number,
    readonly shownCells: number,
  ) {
    super(message);
    this.name = "ConsoleSaveError";
  }
}

export interface ConsoleRunEntry {
  id: number;
  started_at: string | null;
  state: "en_espera" | "ejecutando" | "lista" | "fallida";
  duration_seconds: number | null;
  triggered_by: string;
}

export interface ConsoleRunDetail {
  run: ConsoleRunEntry;
  failure: {
    cause: string;
    message: string;
    reference: string | null;
  } | null;
  results_block: PortalResultsBlockPayload | null;
}

export type PortalConfigurationStatus = "draft" | "active";

export interface PortalConfiguration {
  project_id: number;
  status: PortalConfigurationStatus;
  document: PortalConfigDocument;
  revision: number;
  has_logo: boolean;
  updated_at: string | null;
  updated_by: string | null;
}

export interface PortalConfigurationSavePayload {
  document: PortalConfigDocument;
  status: PortalConfigurationStatus;
  expected_revision: number;
}

export interface PortalChartSeries {
  label: string;
  unit: string;
  values: Array<number | null>;
}

export interface PortalChart {
  id: string;
  label: string;
  x_labels: string[];
  series: PortalChartSeries[];
}

export interface PortalTableColumn {
  id: string;
  label: string;
  unit: string | null;
}

export interface PortalTable {
  id: string;
  label: string;
  row_limit: number;
  columns: PortalTableColumn[];
  rows: Array<Record<string, number | string | null>>;
}

export interface PortalResultsBlockPayload {
  labels: {
    kpis: string;
    charts: string;
    tables: string;
    downloads: string;
  };
  kpis: PortalKpi[];
  charts: PortalChart[];
  tables: PortalTable[];
}

export interface PortalBranding {
  display_name: string;
  logo_url: string | null;
}

export interface ClientPortalProject {
  id: number;
  branding: PortalBranding;
}

export interface PortalPublicationIdentity {
  id: number;
  project_id: number;
  public_title: string;
  analyst_notes: string;
  published_at: string | null;
  status: string;
}

export interface PortalPeriod {
  start: string | null;
  end: string | null;
}

export interface PortalPublicationPayload {
  branding: PortalBranding;
  publication: PortalPublicationIdentity;
  period: PortalPeriod;
  results_state: "available" | "unavailable";
  results_block: PortalResultsBlockPayload | null;
  downloads: PublicationDownload[];
}

export interface PublicationPreviewContext {
  run_id: number;
  scenario_version_number: number;
  results_error: string;
}

export interface PublicationPreview extends PortalPublicationPayload {
  preview_context: PublicationPreviewContext;
}

export interface ClientProjectPublications {
  branding: PortalBranding;
  publications: Publication[];
}

export type ClientPublicationDetail = PortalPublicationPayload &
  Partial<Pick<PublicationPreview, "preview_context">>;

export type DraftAssetType = "battery" | "load" | "renewable" | "hydro";

export interface DraftAsset {
  id?: string;
  type?: DraftAssetType | string;
  [key: string]: unknown;
}

export type TimeSeriesCell = string | number | boolean | null;

export type TimeSeriesRow = Record<string, TimeSeriesCell>;

export interface TimeSeriesValidation {
  ok?: boolean;
  error_category?: string;
  errors?: string[];
  [key: string]: unknown;
}

export interface TimeSeriesMapping {
  timestamp?: string | null;
  duration_hours?: string | null;
  price_usd_per_mwh?: string | null;
  import_price_usd_per_mwh?: string | null;
  export_price_usd_per_mwh?: string | null;
  renewable_available_power_mw?: Record<string, string | null>;
  load_demand_mw?: Record<string, string | null>;
  hydro_inflow_m3s?: Record<string, string | null>;
  [key: string]: unknown;
}

export interface TimeSeriesSource {
  id: string;
  kind?: string;
  original_filename?: string;
  media_type?: string;
  checksum?: string;
  stored_path?: string;
  selected_sheet?: string;
  available_sheets?: string[];
  columns?: string[];
  preview_rows?: TimeSeriesRow[];
  edited_rows?: TimeSeriesRow[];
  mapping_suggestions?: TimeSeriesMapping;
  mapping?: TimeSeriesMapping;
  validation?: TimeSeriesValidation;
  validated_rows?: unknown[];
  [key: string]: unknown;
}

export interface TimeSeriesCatalogImportPayload {
  set_name: string;
  version_label: string;
  data_kind: string;
  timezone: string;
  timestamp_column: string;
  duration_hours_column: string;
  signal_mappings: TimeSeriesCatalogSignalMappingPayload[];
  value_column?: string | null;
  signal_key?: string | null;
  source_unit?: string | null;
}

export interface TimeSeriesCatalogSignalMappingPayload {
  source_column: string;
  signal_key: string;
  source_unit?: string | null;
}

export interface DraftSeriesExtractionPayload {
  set_name: string;
  version_label: string;
  data_kind: string;
  timezone: string;
}

export interface ProjectTimeSeriesSetSignal {
  signal_key: string;
  unit: string;
  source_column?: string | null;
  source_unit?: string | null;
  entity_type: string | null;
  entity_key: string | null;
}

export interface ProjectTimeSeriesSetPeriod {
  period_index: number;
  timestamp_start: string;
  timestamp_end: string;
  duration_hours: number;
}

export interface ProjectTimeSeriesSetValue {
  period_index: number;
  signal_key: string;
  value_numeric: number;
}

export interface ProjectTimeSeriesSetSource {
  original_filename: string;
  media_type: string;
  checksum: string;
  selected_sheet?: string | null;
  kind?: string;
  metadata?: Record<string, unknown>;
}

export interface ProjectTimeSeriesSetHorizon {
  period_count: number;
  start: string | null;
  end: string | null;
}

export interface ProjectTimeSeriesSet {
  id: number;
  project_id: number;
  name: string;
  version_number: number;
  version_label: string;
  revision_number: number;
  data_kind: string;
  timezone: string;
  status: string;
  content_hash: string;
  source_checksum: string | null;
  signal_count: number;
  period_count: number;
  created_at?: string;
  updated_at?: string;
  revision_metadata?: Record<string, unknown>;
  staleness?: VariantStaleness;
  source: ProjectTimeSeriesSetSource | null;
  horizon: ProjectTimeSeriesSetHorizon;
  signals: ProjectTimeSeriesSetSignal[];
  periods: ProjectTimeSeriesSetPeriod[];
  values: ProjectTimeSeriesSetValue[];
}

export interface TimeSeriesProgramMetadata {
  issuer: string;
  issued_at: string;
  valid_from: string;
  valid_until: string;
}

export interface ProjectTimeSeriesSetRevision {
  revision_number: number;
  content_hash: string;
  change_summary: string;
  created_at: string;
  created_by: string;
  program?: TimeSeriesProgramMetadata | null;
}

export interface TimeSeriesSetValueEdit {
  period_index: number;
  signal_key: string;
  value: string;
}

export interface TimeSeriesSetValuesEditPayload {
  edits: TimeSeriesSetValueEdit[];
  change_summary?: string;
}

export interface TimeSeriesTransformationPayload {
  transformation_type: string;
  parameters: Record<string, unknown>;
  output_name?: string;
  output_version_label?: string;
}

export interface TimeSeriesConnectorConfigPayload {
  connector_id?: string;
  base_url: string;
  records_path?: string | null;
  auth_token?: string | null;
}

export interface TimeSeriesConnectorIngestionPayload {
  connector: TimeSeriesConnectorConfigPayload;
  set_name: string;
  version_label: string;
  timezone: string;
  timestamp_column: string;
  duration_hours_column: string;
  signal_mappings: TimeSeriesCatalogSignalMappingPayload[];
  program?: TimeSeriesProgramMetadata | null;
}

export interface TimeSeriesConnectorIngestionSummary {
  outcome: string;
  connector_id: string;
  target: string;
  fetched_at: string;
  record_count: number;
  program?: TimeSeriesProgramMetadata;
}

export interface TimeSeriesConnectorIngestionResult {
  time_series_set: ProjectTimeSeriesSet;
  ingestion: TimeSeriesConnectorIngestionSummary;
}

export interface TimeSeriesSetReplacementSource {
  id: string;
  kind: string;
  original_filename: string;
  media_type: string;
  checksum: string;
  stored_path: string;
  selected_sheet?: string | null;
}

export interface TimeSeriesSetReplacePayload {
  source: TimeSeriesSetReplacementSource;
  data_kind: string;
  timezone: string;
  timestamp_column: string;
  duration_hours_column: string;
  signal_mappings: TimeSeriesCatalogSignalMappingPayload[];
  value_column?: string | null;
  signal_key?: string | null;
  source_unit?: string | null;
  change_summary?: string | null;
}

export interface ProjectTimeSeriesSetSummary {
  id: number;
  project_id: number;
  name: string;
  version_number: number;
  version_label: string;
  revision_number: number;
  data_kind: string;
  timezone: string;
  status: string;
  content_hash: string;
  signal_count: number;
  period_count: number;
  stale?: boolean;
  program?: TimeSeriesProgramMetadata | null;
  created_at?: string;
  updated_at?: string;
}

export interface HydraulicTimeSeriesSetOrigin {
  kind: string;
  entity_type: string;
  entity_id: number;
  signal_key: string;
}

export interface HydraulicTimeSeriesSetMigration {
  time_series_set_id: number;
  time_series_set_name: string;
  version_label: string;
  migrated_by: string;
  migrated_at: string;
}

export interface HydraulicTimeSeriesSetSummary {
  id: number;
  project_id: number;
  name: string;
  entity_type: string;
  entity_id: number;
  entity_key: string | null;
  entity_display_name: string;
  hydraulic_system_name: string;
  signal_key: string;
  unit: string;
  version_number: number;
  version_label: string;
  status: string;
  content_hash: string | null;
  period_count: number;
  created_at?: string;
  updated_at?: string;
  origin: HydraulicTimeSeriesSetOrigin;
  migration: HydraulicTimeSeriesSetMigration | null;
}

export interface HydraulicTimeSeriesSetSignal {
  signal_key: string;
  unit: string;
  entity_type: string;
  entity_key: string | null;
}

export interface HydraulicTimeSeriesSetPeriod {
  period_index: number;
  timestamp_start: string;
  timestamp_end: string;
  duration_hours: number;
}

export interface HydraulicTimeSeriesSetValue {
  period_index: number;
  signal_key: string;
  value_numeric: number;
}

export interface HydraulicTimeSeriesSetHorizon {
  period_count: number;
  start: string | null;
  end: string | null;
}

export interface HydraulicTimeSeriesSet extends HydraulicTimeSeriesSetSummary {
  signals: HydraulicTimeSeriesSetSignal[];
  periods: HydraulicTimeSeriesSetPeriod[];
  values: HydraulicTimeSeriesSetValue[];
  horizon: HydraulicTimeSeriesSetHorizon;
}

export interface GeneratedCaseValidation {
  ok?: boolean;
  phase?: string;
  message?: string;
  payload?: unknown;
  error_category?: string;
  [key: string]: unknown;
}

export interface GeneratedSystemCaseSnapshot extends CaseHierarchyProvenance {
  system_case: unknown;
  validation: GeneratedCaseValidation;
}

export interface ScenarioDraftDocument {
  schema_version?: string;
  case?: {
    name?: string;
    description?: string;
    [key: string]: unknown;
  };
  source?: unknown;
  pcc?: {
    id?: string;
    type?: string;
    [key: string]: unknown;
  };
  grid?: {
    id?: string;
    import_power_max_mw?: number | null;
    export_power_max_mw?: number | null;
    prevent_simultaneous_grid_import_export?: boolean;
    [key: string]: unknown;
  };
  assets?: DraftAsset[];
  time_series?: {
    active_source_id?: string | null;
    sources?: unknown[];
    periods?: unknown[];
    [key: string]: unknown;
  };
  solver?: {
    name?: string;
    options?: Record<string, unknown>;
    [key: string]: unknown;
  };
  generated_system_case?: GeneratedSystemCaseSnapshot;
  system_case_seed?: unknown;
  [key: string]: unknown;
}

export interface ScenarioDraft {
  id: number;
  scenario_id: number;
  source_version_id: number | null;
  document: ScenarioDraftDocument;
  created_at: string;
  updated_at: string;
  created_by?: string;
  updated_by?: string;
}

export interface ScenarioDraftWritePayload {
  document?: ScenarioDraftDocument;
  source_version_id?: number | null;
}

export type HydraulicComponentType = "reservoir" | "junction" | "plant";
export type HydraulicReachType =
  | "river"
  | "canal"
  | "tunnel"
  | "gate"
  | "spillway"
  | "bypass"
  | "tailrace"
  | "other";

export type HydraulicTerminalCondition =
  | "none"
  | "equal_initial"
  | "min_terminal";

export interface HydraulicReservoirParameters {
  storage_min_hm3: number;
  storage_max_hm3: number;
  initial_storage_hm3: number;
  terminal_condition: HydraulicTerminalCondition;
  terminal_storage_min_hm3: number | null;
  terminal_water_value_usd_per_hm3: number;
}

export interface HydraulicCurvePoint {
  x_value: number;
  y_value: number;
}

export interface HydraulicCurveSummary {
  curve_set_id: number;
  version_number: number;
  version_label: string;
  points: HydraulicCurvePoint[];
}

export interface HydraulicStorageElevationCurveWrite {
  curve_set_id?: number | null;
  version_label?: string | null;
  points: HydraulicCurvePoint[];
}

export type HydraulicCurveWrite = HydraulicStorageElevationCurveWrite;

export interface HydraulicNaturalInflowSeriesPoint {
  timestamp: string;
  duration_hours: number;
  value_m3s: number;
}

export interface HydraulicSeriesOrigin {
  kind: string;
}

export interface HydraulicNaturalInflowSeriesSummary {
  time_series_set_id: number;
  version_number: number;
  version_label: string;
  origin: HydraulicSeriesOrigin;
  points: HydraulicNaturalInflowSeriesPoint[];
}

export interface HydraulicNaturalInflowSeriesWrite {
  time_series_set_id?: number | null;
  // Which store time_series_set_id refers to when re-sending an existing
  // reference unchanged ("generic" for the TS-5 catalog, absent/omitted for
  // a legacy hydraulic_time_series_sets id). Only meaningful together with
  // time_series_set_id; ignored when submitting brand-new points.
  origin?: HydraulicSeriesOrigin | null;
  version_label?: string | null;
  points: HydraulicNaturalInflowSeriesPoint[];
}

export interface HydraulicPlantParameters {
  non_modeled: boolean;
  min_power_mw: number | null;
  max_power_mw: number | null;
}

export interface HydraulicUnitWrite {
  technical_key: string;
  display_name: string;
  is_active: boolean;
  intake_node_key: string | null;
  discharge_node_key: string | null;
  min_power_mw: number | null;
  max_power_mw: number | null;
  min_flow_m3s: number | null;
  max_flow_m3s: number | null;
  flow_power_curve?: HydraulicCurveWrite | null;
}

export interface HydraulicUnit extends HydraulicUnitWrite {
  flow_power_curve: HydraulicCurveSummary | null;
  available_curves: HydraulicCurveSummary[];
}

export interface HydraulicPlantLinkAnchor {
  from?: number | null;
  to?: number | null;
}

export interface HydraulicDiagramNodeWrite {
  component_type: HydraulicComponentType;
  technical_key: string;
  display_name: string;
  x: number;
  y: number;
  reservoir?: HydraulicReservoirParameters | null;
  storage_elevation_curve?: HydraulicStorageElevationCurveWrite | null;
  natural_inflow_series?: HydraulicNaturalInflowSeriesWrite | null;
  plant?: HydraulicPlantParameters | null;
  units?: HydraulicUnitWrite[];
  // Plant only: border anchors for derived plant links, keyed by
  // "in:<nodeKey>" (intake) / "out:<nodeKey>" (discharge).
  link_anchors?: Record<string, HydraulicPlantLinkAnchor> | null;
}

export interface HydraulicDiagramNode extends HydraulicDiagramNodeWrite {
  layout_item_id: number;
  entity_type: string;
  entity_id: number;
  z_index: number;
  reservoir: HydraulicReservoirParameters | null;
  storage_elevation_curve: HydraulicCurveSummary | null;
  available_curves: HydraulicCurveSummary[];
  natural_inflow_series: HydraulicNaturalInflowSeriesSummary | null;
  available_inflow_series: HydraulicNaturalInflowSeriesSummary[];
  plant: HydraulicPlantParameters | null;
  units: HydraulicUnit[];
}

export interface HydraulicDiagramReachWrite {
  technical_key: string;
  display_name: string;
  from_node_key: string;
  to_node_key: string;
  reach_type: HydraulicReachType;
  // Fraction (0..1) along the source bottom / target top border where the
  // edge attaches; null/absent means center (0.5).
  from_anchor?: number | null;
  to_anchor?: number | null;
  flow_min_m3s?: number | null;
  spill_penalty_usd_per_hm3?: number | null;
  minimum_flow_series?: HydraulicNaturalInflowSeriesWrite | null;
}

export interface HydraulicDiagramReach extends HydraulicDiagramReachWrite {
  layout_item_id: number | null;
  entity_type: string;
  entity_id: number;
  z_index: number;
  flow_min_m3s: number | null;
  spill_penalty_usd_per_hm3: number | null;
  minimum_flow_series: HydraulicNaturalInflowSeriesSummary | null;
  available_minimum_flow_series: HydraulicNaturalInflowSeriesSummary[];
}

export interface HydraulicDiagramViewport {
  x: number;
  y: number;
  zoom: number;
}

export interface HydraulicDiagram {
  scenario_id: number;
  optimization_case: {
    id: number;
    scenario_id: number;
    case_key: string;
    display_name: string;
    updated_at: string;
  };
  hydraulic_system: {
    id: number;
    project_id: number;
    system_key: string;
    display_name: string;
  };
  layout: {
    id: number;
    case_id: number;
    layout_key: string;
    layout_engine?: string | null;
    layout_version: number;
    revision: string;
    viewport: HydraulicDiagramViewport;
    updated_at: string;
    updated_by: string;
  };
  revision: string;
  validation?: HydraulicDiagramValidation;
  nodes: HydraulicDiagramNode[];
  reaches: HydraulicDiagramReach[];
}

export interface HydraulicDiagramSavePayload {
  revision: string;
  viewport: HydraulicDiagramViewport;
  nodes: HydraulicDiagramNodeWrite[];
  reaches: HydraulicDiagramReachWrite[];
}

export interface HydraulicDiagramLayoutSnapshotNode {
  entity_type: string;
  entity_id: number;
  component_type: HydraulicComponentType;
  technical_key: string;
  display_name: string;
  x: number;
  y: number;
  z_index: number;
}

export interface HydraulicDiagramLayoutSnapshotReach {
  entity_type: string;
  entity_id: number;
  technical_key: string;
  display_name: string;
  from_node_key: string;
  to_node_key: string;
  reach_type: HydraulicReachType;
  z_index: number;
}

export interface HydraulicDiagramLayoutSnapshot {
  id: number;
  scenario_version_id: number;
  source_case_id: number | null;
  layout_key: string;
  layout_content_hash: string | null;
  created_at: string;
  created_by: string;
  layout_snapshot: {
    layout_key: string;
    layout_engine?: string | null;
    viewport: HydraulicDiagramViewport;
    nodes: HydraulicDiagramLayoutSnapshotNode[];
    reaches: HydraulicDiagramLayoutSnapshotReach[];
  };
}

export interface HydraulicDiagramValidationIssue {
  severity?: "error" | "warning";
  code: string;
  message: string;
  entity_type: string;
  entity_id: number;
  technical_key: string;
}

export interface HydraulicDiagramValidation extends CaseHierarchyProvenance {
  kind?: string;
  ok: boolean;
  stale?: boolean;
  status?: string;
  summary: string;
  errors: HydraulicDiagramValidationIssue[];
  warnings: HydraulicDiagramValidationIssue[];
  system_case?: unknown;
  julia_validation?: unknown;
  topology_stale?: boolean;
  parameters_stale?: boolean;
}

interface StructuredErrorBody {
  error?: {
    category?: string;
    message?: string;
    details?: unknown;
  };
  category?: string;
  error_category?: string;
  phase?: string;
  message?: string;
  detail?: unknown;
}

export interface GeneratedSystemCaseValidationResponse {
  status: string;
  phase?: string;
  message?: string;
  error_category?: string;
  detail?: string;
  validation?: unknown;
  system_case?: unknown;
  generated_system_case?: GeneratedSystemCaseSnapshot;
}

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly category: string,
    readonly details?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function requestHeaders(init?: RequestInit): Headers {
  const headers = new Headers(init?.headers);
  if (!headers.has("Accept")) headers.set("Accept", "application/json");
  return headers;
}

async function errorFromResponse(response: Response): Promise<ApiError> {
  const isJson = response.headers
    .get("content-type")
    ?.includes("application/json");
  let body: StructuredErrorBody = {};
  if (isJson) {
    try {
      body = (await response.json()) as StructuredErrorBody;
    } catch {
      body = {};
    }
  }
  const structured = body.error;
  const detailMessage =
    typeof body.detail === "string" ? body.detail : undefined;
  return new ApiError(
    structured?.message ||
      body.message ||
      detailMessage ||
      `Request failed (${response.status})`,
    response.status,
    structured?.category ||
      body.error_category ||
      body.category ||
      `http_${response.status}`,
    structured?.details ?? body.detail ?? body,
  );
}

export async function requestJson<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const response = await fetch(path, {
    ...init,
    credentials: init?.credentials ?? "same-origin",
    headers: requestHeaders(init),
  });
  if (!response.ok) throw await errorFromResponse(response);
  if (response.status === 204) return undefined as T;
  if (!response.headers.get("content-type")?.includes("application/json")) {
    throw new ApiError(
      "Expected a JSON response",
      response.status,
      "unexpected_content_type",
    );
  }
  return response.json() as Promise<T>;
}

export interface ApiDownload {
  blob: Blob;
  filename: string | null;
  contentType: string;
}

function downloadFilename(response: Response): string | null {
  const disposition = response.headers.get("content-disposition");
  const match = disposition?.match(/filename\s*=\s*"?([^";]+)"?/i);
  return match?.[1] ?? null;
}

export async function requestDownload(
  path: string,
  init?: RequestInit,
): Promise<ApiDownload> {
  const headers = new Headers(init?.headers);
  if (!headers.has("Accept")) headers.set("Accept", "*/*");
  const response = await fetch(path, {
    ...init,
    credentials: init?.credentials ?? "same-origin",
    headers,
  });
  if (!response.ok) throw await errorFromResponse(response);
  return {
    blob: await response.blob(),
    filename: downloadFilename(response),
    contentType:
      response.headers.get("content-type") || "application/octet-stream",
  };
}

export async function getCurrentUser(
  signal?: AbortSignal,
): Promise<CurrentUserResponse> {
  try {
    return await requestJson<CurrentUserResponse>("/api/auth/me", { signal });
  } catch (error) {
    if (error instanceof ApiError && error.status === 401)
      return { user: null, bootstrap_required: false };
    throw error;
  }
}

export async function getCsrfToken(): Promise<string> {
  const response = await requestJson<{ csrf_token: string }>("/api/auth/csrf");
  return response.csrf_token;
}

async function postJsonWithCsrf<T>(path: string, body?: unknown): Promise<T> {
  const csrfToken = await getCsrfToken();
  return requestJson<T>(path, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRF-Token": csrfToken,
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}

async function putJsonWithCsrf<T>(path: string, body?: unknown): Promise<T> {
  const csrfToken = await getCsrfToken();
  return requestJson<T>(path, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
      "X-CSRF-Token": csrfToken,
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}

async function patchJsonWithCsrf<T>(path: string, body?: unknown): Promise<T> {
  const csrfToken = await getCsrfToken();
  return requestJson<T>(path, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      "X-CSRF-Token": csrfToken,
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}

export async function bootstrapAdmin(
  payload: BootstrapAdminPayload,
): Promise<AuthSessionResponse> {
  return postJsonWithCsrf<AuthSessionResponse>("/api/auth/bootstrap", payload);
}

export async function login(
  payload: LoginPayload,
): Promise<AuthSessionResponse> {
  return postJsonWithCsrf<AuthSessionResponse>("/api/auth/login", payload);
}

export async function logout(): Promise<void> {
  await postJsonWithCsrf<void>("/api/auth/logout");
}

export async function listAdminUsers(
  signal?: AbortSignal,
): Promise<AdminUser[]> {
  const response = await requestJson<{ users: AdminUser[] }>(
    "/api/admin/users",
    { signal },
  );
  return response.users;
}

export async function createAdminUser(
  payload: UserCreatePayload,
): Promise<AdminUser> {
  const response = await postJsonWithCsrf<{ user: AdminUser }>(
    "/api/admin/users",
    payload,
  );
  return response.user;
}

export async function deactivateAdminUser(userId: number): Promise<AdminUser> {
  const response = await postJsonWithCsrf<{ user: AdminUser }>(
    `/api/admin/users/${userId}/deactivate`,
  );
  return response.user;
}

export async function listProjects(signal?: AbortSignal): Promise<Project[]> {
  const response = await requestJson<{ projects: Project[] }>("/api/projects", {
    signal,
  });
  return response.projects;
}

export async function createProject(
  payload: ProjectCreatePayload,
): Promise<Project> {
  return postJsonWithCsrf<Project>("/api/projects", payload);
}

export async function getProject(
  projectId: number,
  signal?: AbortSignal,
): Promise<Project> {
  const response = await requestJson<{ project: Project }>(
    `/api/projects/${projectId}`,
    { signal },
  );
  return response.project;
}

export async function deleteProject(
  projectId: number,
): Promise<ProjectDeletionResult> {
  const csrfToken = await getCsrfToken();
  const response = await requestJson<{
    deleted_project: ProjectDeletionResult;
  }>(`/api/projects/${projectId}`, {
    method: "DELETE",
    headers: { "X-CSRF-Token": csrfToken },
  });
  return response.deleted_project;
}

export async function listProjectExternalAccess(
  projectId: number,
  signal?: AbortSignal,
): Promise<ExternalProjectAccess[]> {
  const response = await requestJson<{
    external_access: ExternalProjectAccess[];
  }>(`/api/admin/projects/${projectId}/external-access`, { signal });
  return response.external_access;
}

export async function setProjectExternalAccess(
  projectId: number,
  userId: number,
  capabilities: ExternalProjectCapabilities,
): Promise<ExternalProjectAccess> {
  const csrfToken = await getCsrfToken();
  const response = await requestJson<{
    external_access: ExternalProjectAccess;
  }>(`/api/admin/projects/${projectId}/external-access/${userId}`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
      "X-CSRF-Token": csrfToken,
    },
    body: JSON.stringify(capabilities),
  });
  return response.external_access;
}

export async function revokeProjectExternalAccess(
  projectId: number,
  userId: number,
): Promise<ExternalProjectAccess> {
  const csrfToken = await getCsrfToken();
  const response = await requestJson<{
    external_access: ExternalProjectAccess;
  }>(`/api/admin/projects/${projectId}/external-access/${userId}`, {
    method: "DELETE",
    headers: { "X-CSRF-Token": csrfToken },
  });
  return response.external_access;
}

export async function listRunSchedules(signal?: AbortSignal): Promise<{
  schedules: RunSchedule[];
  ticks: RunScheduleTick[];
}> {
  return requestJson<{ schedules: RunSchedule[]; ticks: RunScheduleTick[] }>(
    "/api/admin/schedules",
    { signal },
  );
}

export async function createRunSchedule(
  payload: RunScheduleCreatePayload,
): Promise<RunSchedule> {
  const response = await postJsonWithCsrf<{ schedule: RunSchedule }>(
    "/api/admin/schedules",
    payload,
  );
  return response.schedule;
}

export async function runDueSchedules(
  payload: RunDueSchedulesPayload = {},
): Promise<{
  now: string;
  due_count: number;
  ticks: RunScheduleTick[];
}> {
  return postJsonWithCsrf<{
    now: string;
    due_count: number;
    ticks: RunScheduleTick[];
  }>("/api/admin/schedules/run-due", payload);
}

export async function listScenarios(
  projectId: number,
  signal?: AbortSignal,
): Promise<Scenario[]> {
  const response = await requestJson<{ scenarios: Scenario[] }>(
    `/api/projects/${projectId}/scenarios`,
    { signal },
  );
  return response.scenarios;
}

export async function createScenario(
  projectId: number,
  payload: ScenarioCreatePayload,
): Promise<Scenario> {
  return postJsonWithCsrf<Scenario>(
    `/api/projects/${projectId}/scenarios`,
    payload,
  );
}

export async function getScenario(
  scenarioId: number,
  signal?: AbortSignal,
): Promise<Scenario> {
  const response = await requestJson<{ scenario: Scenario }>(
    `/api/scenarios/${scenarioId}`,
    { signal },
  );
  return response.scenario;
}

export async function listScenarioVersions(
  scenarioId: number,
  signal?: AbortSignal,
): Promise<ScenarioVersion[]> {
  const response = await requestJson<{ versions: ScenarioVersion[] }>(
    `/api/scenarios/${scenarioId}/versions`,
    { signal },
  );
  return response.versions;
}

export async function getScenarioVersion(
  scenarioVersionId: number,
  signal?: AbortSignal,
): Promise<ScenarioVersionDetail> {
  const response = await requestJson<{
    scenario_version: ScenarioVersionDetail;
  }>(`/api/scenario-versions/${scenarioVersionId}`, { signal });
  return response.scenario_version;
}

export async function getScenarioVersionHydraulicDiagramSnapshot(
  scenarioVersionId: number,
  signal?: AbortSignal,
): Promise<HydraulicDiagramLayoutSnapshot> {
  const response = await requestJson<{
    snapshot: HydraulicDiagramLayoutSnapshot;
  }>(`/api/scenario-versions/${scenarioVersionId}/hydraulic-diagram-snapshot`, {
    signal,
  });
  return response.snapshot;
}

export async function deleteScenarioVersion(
  scenarioVersionId: number,
): Promise<ScenarioVersionDetail> {
  const csrfToken = await getCsrfToken();
  const response = await requestJson<{
    deleted_version: ScenarioVersionDetail;
  }>(`/api/scenario-versions/${scenarioVersionId}`, {
    method: "DELETE",
    headers: { "X-CSRF-Token": csrfToken },
  });
  return response.deleted_version;
}

export async function createScenarioVersionFromJson(
  scenarioId: number,
  systemCaseJson: string,
): Promise<ScenarioVersion> {
  return postJsonWithCsrf<ScenarioVersion>(
    `/api/scenarios/${scenarioId}/versions`,
    { system_case_json: systemCaseJson },
  );
}

export async function uploadScenarioVersion(
  scenarioId: number,
  file: File,
): Promise<ScenarioVersion> {
  const csrfToken = await getCsrfToken();
  const body = new FormData();
  body.append("system_case_file", file);
  return requestJson<ScenarioVersion>(
    `/api/scenarios/${scenarioId}/versions/upload`,
    {
      method: "POST",
      headers: { "X-CSRF-Token": csrfToken },
      body,
    },
  );
}

export async function listScenarioRuns(
  scenarioId: number,
  signal?: AbortSignal,
): Promise<ScenarioRun[]> {
  const response = await requestJson<{ runs: ScenarioRun[] }>(
    `/api/scenarios/${scenarioId}/runs`,
    { signal },
  );
  return response.runs;
}

export async function createManualRun(
  scenarioVersionId: number,
): Promise<ScenarioRun> {
  return postJsonWithCsrf<ScenarioRun>(
    `/api/scenario-versions/${scenarioVersionId}/runs`,
  );
}

export interface CaseInputVariant {
  id: number;
  case_id: number;
  variant_key: string;
  display_name: string;
  is_default: boolean;
  created_at: string;
  updated_at: string;
}

export interface CaseTimeSeriesBinding {
  id: number;
  case_input_variant_id: number;
  signal_key: string;
  entity_type: string | null;
  entity_id: string | null;
  time_series_set_id: number;
  required: boolean;
  created_at: string;
  updated_at: string;
}

export interface RequiredSignalStatus {
  entity_type: string;
  entity_id: string;
  signal_key: string;
  bound: boolean;
  bound_signal_key: string | null;
  time_series_set_id: number | null;
}

export interface VariantStalenessReason {
  dependency_type: string;
  dependency_id: string | null;
  detail: string;
}

export interface VariantStaleness {
  validated: boolean;
  stale: boolean;
  reasons: VariantStalenessReason[];
}

export interface DefaultInputVariantResponse {
  case: {
    id: number;
    scenario_id: number;
    case_key: string;
    display_name: string;
    updated_at: string;
  };
  variant: CaseInputVariant;
  bindings: CaseTimeSeriesBinding[];
  required_signals: RequiredSignalStatus[];
  staleness: VariantStaleness;
}

export interface CaseInputVariantDetail {
  variant: CaseInputVariant;
  bindings: CaseTimeSeriesBinding[];
  required_signals: RequiredSignalStatus[];
  staleness: VariantStaleness;
}

export interface CaseInputVariantListResponse {
  case: {
    id: number;
    scenario_id: number;
    case_key: string;
    display_name: string;
    updated_at: string;
  };
  default_variant_id: number;
  variants: CaseInputVariantDetail[];
}

export interface CaseTimeSeriesBindingPayload {
  signal_key: string;
  entity_type?: string | null;
  entity_id?: string | null;
  time_series_set_id: number;
}

export interface CaseInputVariantWritePayload {
  display_name: string;
}

export interface CaseInputVariantRunPayload {
  range_start: string;
  range_end: string;
}

export async function getDefaultInputVariant(
  scenarioId: number,
  signal?: AbortSignal,
): Promise<DefaultInputVariantResponse> {
  return requestJson<DefaultInputVariantResponse>(
    `/api/scenarios/${scenarioId}/case/default-variant`,
    { signal },
  );
}

export async function listCaseInputVariants(
  scenarioId: number,
  signal?: AbortSignal,
): Promise<CaseInputVariantListResponse> {
  return requestJson<CaseInputVariantListResponse>(
    `/api/scenarios/${scenarioId}/case/variants`,
    { signal },
  );
}

export async function createCaseInputVariant(
  scenarioId: number,
  payload: CaseInputVariantWritePayload,
): Promise<CaseInputVariant> {
  return postJsonWithCsrf<CaseInputVariant>(
    `/api/scenarios/${scenarioId}/case/variants`,
    payload,
  );
}

export async function cloneCaseInputVariant(
  scenarioId: number,
  variantId: number,
  payload: CaseInputVariantWritePayload,
): Promise<CaseInputVariant> {
  return postJsonWithCsrf<CaseInputVariant>(
    `/api/scenarios/${scenarioId}/case/variants/${variantId}/clone`,
    payload,
  );
}

export async function updateCaseInputVariant(
  scenarioId: number,
  variantId: number,
  payload: CaseInputVariantWritePayload,
): Promise<CaseInputVariant> {
  return patchJsonWithCsrf<CaseInputVariant>(
    `/api/scenarios/${scenarioId}/case/variants/${variantId}`,
    payload,
  );
}

export async function bindCaseTimeSeries(
  scenarioId: number,
  variantId: number,
  payload: CaseTimeSeriesBindingPayload,
): Promise<CaseTimeSeriesBinding> {
  return postJsonWithCsrf<CaseTimeSeriesBinding>(
    `/api/scenarios/${scenarioId}/case/variants/${variantId}/bindings`,
    payload,
  );
}

export async function runCaseInputVariant(
  scenarioId: number,
  variantId: number,
  payload: CaseInputVariantRunPayload,
): Promise<ScenarioRun> {
  return postJsonWithCsrf<ScenarioRun>(
    `/api/scenarios/${scenarioId}/case/variants/${variantId}/run`,
    payload,
  );
}

export interface CaseInputVariantValidationResult {
  status: string;
  series_bindings: unknown[];
}

export async function validateCaseInputVariant(
  scenarioId: number,
  variantId: number,
  payload: CaseInputVariantRunPayload,
): Promise<CaseInputVariantValidationResult> {
  return postJsonWithCsrf<CaseInputVariantValidationResult>(
    `/api/scenarios/${scenarioId}/case/variants/${variantId}/validate`,
    payload,
  );
}

export async function getRun(
  runId: number,
  signal?: AbortSignal,
): Promise<ScenarioRun> {
  const response = await requestJson<{ run: ScenarioRun }>(
    `/api/runs/${runId}`,
    { signal },
  );
  return response.run;
}

export async function getRunResults(
  runId: number,
  signal?: AbortSignal,
): Promise<RunResults> {
  const response = await requestJson<{ results: RunResults }>(
    `/api/runs/${runId}/results`,
    { signal },
  );
  return response.results;
}

export async function compareRuns(
  params: { baselineRunId: number; candidateRunId: number; series?: string },
  signal?: AbortSignal,
): Promise<RunComparison> {
  const query = new URLSearchParams({
    baseline_run_id: String(params.baselineRunId),
    candidate_run_id: String(params.candidateRunId),
  });
  if (params.series) query.set("series", params.series);
  const response = await requestJson<{ comparison: RunComparison }>(
    `/api/run-comparisons?${query.toString()}`,
    { signal },
  );
  return response.comparison;
}

export async function listRunArtifacts(
  runId: number,
  signal?: AbortSignal,
): Promise<RunArtifact[]> {
  const response = await requestJson<{ artifacts: RunArtifact[] }>(
    `/api/runs/${runId}/artifacts`,
    { signal },
  );
  return response.artifacts;
}

export async function listDashboardTemplates(
  projectId: number,
  signal?: AbortSignal,
): Promise<DashboardTemplate[]> {
  const response = await requestJson<{
    dashboard_templates: DashboardTemplate[];
  }>(`/api/projects/${projectId}/dashboard-templates`, { signal });
  return response.dashboard_templates;
}

export async function createDashboardTemplate(
  projectId: number,
  payload: DashboardTemplatePayload,
): Promise<DashboardTemplate> {
  const response = await postJsonWithCsrf<{
    dashboard_template: DashboardTemplate;
  }>(`/api/projects/${projectId}/dashboard-templates`, payload);
  return response.dashboard_template;
}

export async function updateDashboardTemplate(
  templateId: number,
  payload: DashboardTemplatePayload,
): Promise<DashboardTemplate> {
  const csrfToken = await getCsrfToken();
  const response = await requestJson<{
    dashboard_template: DashboardTemplate;
  }>(`/api/dashboard-templates/${templateId}`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
      "X-CSRF-Token": csrfToken,
    },
    body: JSON.stringify(payload),
  });
  return response.dashboard_template;
}

export async function listRunPublications(
  runId: number,
  signal?: AbortSignal,
): Promise<Publication[]> {
  const response = await requestJson<{ publications: Publication[] }>(
    `/api/runs/${runId}/publications`,
    { signal },
  );
  return response.publications;
}

export async function createRunPublicationDraft(
  runId: number,
  payload: PublicationPayload,
): Promise<Publication> {
  const response = await postJsonWithCsrf<{ publication: Publication }>(
    `/api/runs/${runId}/publications`,
    payload,
  );
  return response.publication;
}

export async function updatePublicationDraft(
  publicationId: number,
  payload: PublicationPayload,
): Promise<Publication> {
  const csrfToken = await getCsrfToken();
  const response = await requestJson<{ publication: Publication }>(
    `/api/publications/${publicationId}`,
    {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
        "X-CSRF-Token": csrfToken,
      },
      body: JSON.stringify(payload),
    },
  );
  return response.publication;
}

export async function publishPublication(
  publicationId: number,
): Promise<Publication> {
  const response = await postJsonWithCsrf<{ publication: Publication }>(
    `/api/publications/${publicationId}/publish`,
  );
  return response.publication;
}

export async function unpublishPublication(
  publicationId: number,
): Promise<Publication> {
  const response = await postJsonWithCsrf<{ publication: Publication }>(
    `/api/publications/${publicationId}/unpublish`,
  );
  return response.publication;
}

export async function getPortalCatalogs(
  signal?: AbortSignal,
): Promise<PortalCatalogs> {
  return requestJson<PortalCatalogs>("/api/portal-catalogs", { signal });
}

export async function getSignalCatalog(
  signal?: AbortSignal,
): Promise<SignalCatalogEntry[]> {
  const response = await requestJson<{ signals: SignalCatalogEntry[] }>(
    "/api/time-series/signal-catalog",
    { signal },
  );
  return response.signals;
}

export async function listOperatorConsoles(
  scenarioId: number,
  signal?: AbortSignal,
): Promise<OperatorConsole[]> {
  const response = await requestJson<{ operator_consoles: OperatorConsole[] }>(
    `/api/scenarios/${scenarioId}/consoles`,
    { signal },
  );
  return response.operator_consoles;
}

export async function createOperatorConsole(
  scenarioId: number,
  payload: OperatorConsoleCreatePayload,
): Promise<OperatorConsole> {
  const response = await postJsonWithCsrf<{
    operator_console: OperatorConsole;
  }>(`/api/scenarios/${scenarioId}/consoles`, payload);
  return response.operator_console;
}

export async function getOperatorConsole(
  scenarioId: number,
  consoleId: number,
  signal?: AbortSignal,
): Promise<OperatorConsole> {
  const response = await requestJson<{ operator_console: OperatorConsole }>(
    `/api/scenarios/${scenarioId}/consoles/${consoleId}`,
    { signal },
  );
  return response.operator_console;
}

export async function saveOperatorConsole(
  scenarioId: number,
  consoleId: number,
  payload: OperatorConsoleSavePayload,
): Promise<OperatorConsole> {
  const response = await putJsonWithCsrf<{ operator_console: OperatorConsole }>(
    `/api/scenarios/${scenarioId}/consoles/${consoleId}`,
    payload,
  );
  return response.operator_console;
}

export async function listOperableConsoles(
  signal?: AbortSignal,
): Promise<ConsoleListEntry[]> {
  const response = await requestJson<{ consoles: ConsoleListEntry[] }>(
    "/api/console",
    { signal },
  );
  return response.consoles;
}

export async function getConsoleShell(
  consoleId: number,
  signal?: AbortSignal,
): Promise<ConsoleShell> {
  return requestJson<ConsoleShell>(`/api/console/${consoleId}`, { signal });
}

export async function getConsoleSeriesOptions(
  consoleId: number,
  signal?: AbortSignal,
): Promise<ConsoleSeriesOptions> {
  return requestJson<ConsoleSeriesOptions>(
    `/api/console/${consoleId}/series-options`,
    { signal },
  );
}

export async function saveConsoleSeriesSelections(
  consoleId: number,
  selections: Array<{
    group_id: string;
    column_id: string;
    source_option_id: string;
  }>,
): Promise<ConsoleSeriesOptions> {
  return putJsonWithCsrf<ConsoleSeriesOptions>(
    `/api/console/${consoleId}/series-selections`,
    { selections },
  );
}

export async function saveConsoleParameters(
  consoleId: number,
  parameters: Array<{ id: string; value: number }>,
): Promise<ConsoleParameter[]> {
  const response = await putJsonWithCsrf<{ parameters: ConsoleParameter[] }>(
    `/api/console/${consoleId}/parameters`,
    { parameters },
  );
  return response.parameters;
}

function consoleGroupValuesPath(consoleId: number, groupId: string): string {
  return `/api/console/${consoleId}/groups/${encodeURIComponent(groupId)}/values`;
}

function consoleGroupLeasePath(consoleId: number, groupId: string): string {
  return `/api/console/${consoleId}/groups/${encodeURIComponent(groupId)}/lease`;
}

async function consoleGroupValuesSnapshot(
  response: Response,
): Promise<ConsoleGroupValuesSnapshot> {
  const body = (await response.json()) as { group_values: ConsoleGroupValues };
  return {
    values: body.group_values,
    etag: response.headers.get("etag") || "",
  };
}

async function consoleErrorFromResponse(
  response: Response,
): Promise<ConsoleSaveError | ApiError> {
  const isJson = response.headers
    .get("content-type")
    ?.includes("application/json");
  if (!isJson) {
    return new ApiError(
      `Request failed (${response.status})`,
      response.status,
      `http_${response.status}`,
    );
  }
  const body = (await response.json()) as {
    save_error?: {
      message: string;
      cells: ConsoleSaveErrorCell[];
      total_cells: number;
      shown_cells: number;
    };
    detail?: string;
  };
  if (!body.save_error) {
    return new ApiError(
      body.detail || `Request failed (${response.status})`,
      response.status,
      `http_${response.status}`,
    );
  }
  return new ConsoleSaveError(
    body.save_error.message,
    response.status,
    body.save_error.cells,
    body.save_error.total_cells,
    body.save_error.shown_cells,
  );
}

export async function getConsoleGroupValues(
  consoleId: number,
  groupId: string,
  range: { start: string; end: string; granularity: string },
  signal?: AbortSignal,
): Promise<ConsoleGroupValuesSnapshot> {
  const query = new URLSearchParams({
    start: range.start,
    end: range.end,
    granularity: range.granularity,
  });
  const response = await fetch(
    `${consoleGroupValuesPath(consoleId, groupId)}?${query}`,
    {
      credentials: "same-origin",
      headers: { Accept: "application/json" },
      signal,
    },
  );
  if (!response.ok) throw await consoleErrorFromResponse(response);
  return consoleGroupValuesSnapshot(response);
}

export async function acquireConsoleGroupLease(
  consoleId: number,
  groupId: string,
): Promise<ConsoleLease> {
  const csrfToken = await getCsrfToken();
  const response = await fetch(consoleGroupLeasePath(consoleId, groupId), {
    method: "POST",
    credentials: "same-origin",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      "X-CSRF-Token": csrfToken,
    },
  });
  if (!response.ok) throw await consoleErrorFromResponse(response);
  const body = (await response.json()) as { lease: ConsoleLease };
  return body.lease;
}

export async function releaseConsoleGroupLease(
  consoleId: number,
  groupId: string,
  leaseToken: string,
): Promise<void> {
  const csrfToken = await getCsrfToken();
  const query = new URLSearchParams({ lease_token: leaseToken });
  await fetch(`${consoleGroupLeasePath(consoleId, groupId)}?${query}`, {
    method: "DELETE",
    credentials: "same-origin",
    headers: { Accept: "application/json", "X-CSRF-Token": csrfToken },
  });
}

export async function saveConsoleGroupValues(
  consoleId: number,
  groupId: string,
  payload: {
    range_start: string;
    range_end: string;
    granularity: string;
    lease_token: string;
    note: string;
    cells: Array<{ column_id: string; row_index: number; value: number }>;
  },
  etag: string,
): Promise<ConsoleGroupValuesSnapshot> {
  const csrfToken = await getCsrfToken();
  const response = await fetch(consoleGroupValuesPath(consoleId, groupId), {
    method: "PUT",
    credentials: "same-origin",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      "X-CSRF-Token": csrfToken,
      "If-Match": etag,
    },
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw await consoleErrorFromResponse(response);
  return consoleGroupValuesSnapshot(response);
}

export async function createConsoleRun(
  consoleId: number,
  payload: { range_start: string; range_end: string },
): Promise<ConsoleRunEntry> {
  const response = await postJsonWithCsrf<{ run: ConsoleRunEntry }>(
    `/api/console/${consoleId}/runs`,
    payload,
  );
  return response.run;
}

export async function listConsoleRuns(
  consoleId: number,
  signal?: AbortSignal,
): Promise<ConsoleRunEntry[]> {
  const response = await requestJson<{ history: ConsoleRunEntry[] }>(
    `/api/console/${consoleId}/runs`,
    { signal },
  );
  return response.history;
}

export async function getConsoleRun(
  consoleId: number,
  runId: number,
  signal?: AbortSignal,
): Promise<ConsoleRunDetail> {
  return requestJson<ConsoleRunDetail>(
    `/api/console/${consoleId}/runs/${runId}`,
    { signal },
  );
}

export async function getPortalConfiguration(
  projectId: number,
  signal?: AbortSignal,
): Promise<PortalConfiguration> {
  const response = await requestJson<{
    portal_configuration: PortalConfiguration;
  }>(`/api/projects/${projectId}/portal-configuration`, { signal });
  return response.portal_configuration;
}

export async function savePortalConfiguration(
  projectId: number,
  payload: PortalConfigurationSavePayload,
): Promise<PortalConfiguration> {
  const csrfToken = await getCsrfToken();
  const response = await requestJson<{
    portal_configuration: PortalConfiguration;
  }>(`/api/projects/${projectId}/portal-configuration`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
      "X-CSRF-Token": csrfToken,
    },
    body: JSON.stringify(payload),
  });
  return response.portal_configuration;
}

export async function uploadPortalLogo(
  projectId: number,
  logo: File,
  expectedRevision: number,
): Promise<PortalConfiguration> {
  const csrfToken = await getCsrfToken();
  const body = new FormData();
  body.append("logo", logo);
  body.append("expected_revision", String(expectedRevision));
  const response = await requestJson<{
    portal_configuration: PortalConfiguration;
  }>(`/api/projects/${projectId}/portal-configuration/logo`, {
    method: "PUT",
    headers: { "X-CSRF-Token": csrfToken },
    body,
  });
  return response.portal_configuration;
}

export async function removePortalLogo(
  projectId: number,
  expectedRevision: number,
): Promise<PortalConfiguration> {
  const csrfToken = await getCsrfToken();
  const response = await requestJson<{
    portal_configuration: PortalConfiguration;
  }>(`/api/projects/${projectId}/portal-configuration/logo`, {
    method: "DELETE",
    headers: {
      "Content-Type": "application/json",
      "X-CSRF-Token": csrfToken,
    },
    body: JSON.stringify({ expected_revision: expectedRevision }),
  });
  return response.portal_configuration;
}

export async function getPublicationPreview(
  publicationId: number,
  signal?: AbortSignal,
): Promise<PublicationPreview> {
  return requestJson<PublicationPreview>(
    `/api/publications/${publicationId}/preview`,
    { signal },
  );
}

export async function listClientProjects(
  signal?: AbortSignal,
): Promise<ClientPortalProject[]> {
  const response = await requestJson<{ projects: ClientPortalProject[] }>(
    "/api/client/projects",
    { signal },
  );
  return response.projects;
}

export async function listClientProjectPublications(
  projectId: number,
  signal?: AbortSignal,
): Promise<ClientProjectPublications> {
  return requestJson<ClientProjectPublications>(
    `/api/client/projects/${projectId}/publications`,
    { signal },
  );
}

export async function getClientPublication(
  projectId: number,
  publicationId: number,
  signal?: AbortSignal,
): Promise<ClientPublicationDetail> {
  return requestJson<ClientPublicationDetail>(
    `/api/client/projects/${projectId}/publications/${publicationId}`,
    { signal },
  );
}

export async function getScenarioDraft(
  scenarioId: number,
  signal?: AbortSignal,
): Promise<ScenarioDraft> {
  const response = await requestJson<{ draft: ScenarioDraft }>(
    `/api/scenarios/${scenarioId}/draft`,
    { signal },
  );
  return response.draft;
}

export async function createScenarioDraft(
  scenarioId: number,
  payload: ScenarioDraftWritePayload = {},
): Promise<ScenarioDraft> {
  return postJsonWithCsrf<ScenarioDraft>(
    `/api/scenarios/${scenarioId}/draft`,
    payload,
  );
}

export async function updateScenarioDraft(
  scenarioId: number,
  document: ScenarioDraftDocument,
): Promise<ScenarioDraft> {
  const csrfToken = await getCsrfToken();
  return requestJson<ScenarioDraft>(`/api/scenarios/${scenarioId}/draft`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
      "X-CSRF-Token": csrfToken,
    },
    body: JSON.stringify({ document }),
  });
}

export async function createHydraulicDiagram(
  scenarioId: number,
): Promise<HydraulicDiagram> {
  const response = await postJsonWithCsrf<{ diagram: HydraulicDiagram }>(
    `/api/scenarios/${scenarioId}/hydraulic-diagram`,
  );
  return response.diagram;
}

export async function getHydraulicDiagram(
  scenarioId: number,
  signal?: AbortSignal,
): Promise<HydraulicDiagram> {
  const response = await requestJson<{ diagram: HydraulicDiagram }>(
    `/api/scenarios/${scenarioId}/hydraulic-diagram`,
    { signal },
  );
  return response.diagram;
}

export async function saveHydraulicDiagram(
  scenarioId: number,
  payload: HydraulicDiagramSavePayload,
): Promise<HydraulicDiagram> {
  const csrfToken = await getCsrfToken();
  const response = await requestJson<{ diagram: HydraulicDiagram }>(
    `/api/scenarios/${scenarioId}/hydraulic-diagram`,
    {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
        "X-CSRF-Token": csrfToken,
      },
      body: JSON.stringify(payload),
    },
  );
  return response.diagram;
}

export async function validateHydraulicDiagram(
  scenarioId: number,
): Promise<HydraulicDiagramValidation> {
  const response = await postJsonWithCsrf<{
    validation: HydraulicDiagramValidation;
  }>(`/api/scenarios/${scenarioId}/hydraulic-diagram/validate`);
  return response.validation;
}

export async function validateHydraulicV3Preview(
  scenarioId: number,
): Promise<HydraulicDiagramValidation> {
  const response = await postJsonWithCsrf<{
    validation: HydraulicDiagramValidation;
  }>(`/api/scenarios/${scenarioId}/hydraulic-diagram/v3-preview`);
  return response.validation;
}

export async function promoteHydraulicDiagram(
  scenarioId: number,
): Promise<ScenarioVersion> {
  return postJsonWithCsrf<ScenarioVersion>(
    `/api/scenarios/${scenarioId}/hydraulic-diagram/promote`,
  );
}

export async function getGeneratedSystemCasePreview(
  scenarioId: number,
): Promise<unknown> {
  const response = await requestJson<{ system_case: unknown }>(
    `/api/scenarios/${scenarioId}/draft/generated-system-case`,
  );
  return response.system_case;
}

export async function validateGeneratedSystemCase(
  scenarioId: number,
): Promise<GeneratedSystemCaseValidationResponse> {
  return postJsonWithCsrf<GeneratedSystemCaseValidationResponse>(
    `/api/scenarios/${scenarioId}/draft/generated-system-case/validate`,
  );
}

export async function promoteGeneratedSystemCase(
  scenarioId: number,
): Promise<ScenarioVersion> {
  return postJsonWithCsrf<ScenarioVersion>(
    `/api/scenarios/${scenarioId}/draft/generated-system-case/promote`,
  );
}

export async function uploadTimeSeriesSource(
  scenarioId: number,
  file: File,
  sheetName = "",
): Promise<TimeSeriesSource> {
  const csrfToken = await getCsrfToken();
  const body = new FormData();
  body.append("source_file", file);
  if (sheetName.trim()) body.append("sheet_name", sheetName.trim());
  const response = await requestJson<{ source: TimeSeriesSource }>(
    `/api/scenarios/${scenarioId}/draft/time-series-sources/upload`,
    {
      method: "POST",
      headers: { "X-CSRF-Token": csrfToken },
      body,
    },
  );
  return response.source;
}

export async function getTimeSeriesRows(
  scenarioId: number,
  sourceId: string,
  signal?: AbortSignal,
): Promise<{ columns: string[]; rows: TimeSeriesRow[] }> {
  return requestJson<{ columns: string[]; rows: TimeSeriesRow[] }>(
    `/api/scenarios/${scenarioId}/draft/time-series-sources/${encodeURIComponent(
      sourceId,
    )}/rows`,
    { signal },
  );
}

export async function saveTimeSeriesRows(
  scenarioId: number,
  sourceId: string,
  rows: TimeSeriesRow[],
): Promise<TimeSeriesSource> {
  const csrfToken = await getCsrfToken();
  const response = await requestJson<{ source: TimeSeriesSource }>(
    `/api/scenarios/${scenarioId}/draft/time-series-sources/${encodeURIComponent(
      sourceId,
    )}/rows`,
    {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
        "X-CSRF-Token": csrfToken,
      },
      body: JSON.stringify({ rows }),
    },
  );
  return response.source;
}

export async function saveTimeSeriesMapping(
  scenarioId: number,
  sourceId: string,
  mapping: TimeSeriesMapping,
): Promise<TimeSeriesSource> {
  const csrfToken = await getCsrfToken();
  const response = await requestJson<{ source: TimeSeriesSource }>(
    `/api/scenarios/${scenarioId}/draft/time-series-sources/${encodeURIComponent(
      sourceId,
    )}/mapping`,
    {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
        "X-CSRF-Token": csrfToken,
      },
      body: JSON.stringify({ mapping }),
    },
  );
  return response.source;
}

export async function importTimeSeriesSourceToCatalog(
  scenarioId: number,
  sourceId: string,
  payload: TimeSeriesCatalogImportPayload,
): Promise<ProjectTimeSeriesSet> {
  const csrfToken = await getCsrfToken();
  const response = await requestJson<{ time_series_set: ProjectTimeSeriesSet }>(
    `/api/scenarios/${scenarioId}/draft/time-series-sources/${encodeURIComponent(
      sourceId,
    )}/catalog-import`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRF-Token": csrfToken,
      },
      body: JSON.stringify(payload),
    },
  );
  return response.time_series_set;
}

export async function extractDraftTimeSeriesSourceToCatalog(
  scenarioId: number,
  sourceId: string,
  payload: DraftSeriesExtractionPayload,
): Promise<ProjectTimeSeriesSet> {
  const csrfToken = await getCsrfToken();
  const response = await requestJson<{ time_series_set: ProjectTimeSeriesSet }>(
    `/api/scenarios/${scenarioId}/draft/time-series-sources/${encodeURIComponent(
      sourceId,
    )}/extract`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRF-Token": csrfToken,
      },
      body: JSON.stringify(payload),
    },
  );
  return response.time_series_set;
}

export async function listProjectTimeSeriesSets(
  projectId: number,
  signal?: AbortSignal,
): Promise<ProjectTimeSeriesSetSummary[]> {
  const response = await requestJson<{
    time_series_sets: ProjectTimeSeriesSetSummary[];
  }>(`/api/projects/${projectId}/time-series-sets`, { signal });
  return response.time_series_sets;
}

export async function getProjectTimeSeriesSet(
  projectId: number,
  timeSeriesSetId: number,
  signal?: AbortSignal,
): Promise<ProjectTimeSeriesSet> {
  const response = await requestJson<{ time_series_set: ProjectTimeSeriesSet }>(
    `/api/projects/${projectId}/time-series-sets/${timeSeriesSetId}`,
    { signal },
  );
  return response.time_series_set;
}

export async function listProjectHydraulicTimeSeriesSets(
  projectId: number,
  signal?: AbortSignal,
): Promise<HydraulicTimeSeriesSetSummary[]> {
  const response = await requestJson<{
    hydraulic_time_series_sets: HydraulicTimeSeriesSetSummary[];
  }>(`/api/projects/${projectId}/time-series-sets/hydraulic`, { signal });
  return response.hydraulic_time_series_sets;
}

export async function getProjectHydraulicTimeSeriesSet(
  projectId: number,
  hydraulicTimeSeriesSetId: number,
  signal?: AbortSignal,
): Promise<HydraulicTimeSeriesSet> {
  const response = await requestJson<{
    hydraulic_time_series_set: HydraulicTimeSeriesSet;
  }>(
    `/api/projects/${projectId}/time-series-sets/hydraulic/${hydraulicTimeSeriesSetId}`,
    { signal },
  );
  return response.hydraulic_time_series_set;
}

export interface HydraulicTimeSeriesSetMigrationResult {
  time_series_set: ProjectTimeSeriesSet;
  hydraulic_time_series_set_id: number;
  already_migrated: boolean;
}

export async function migrateHydraulicTimeSeriesSet(
  projectId: number,
  hydraulicTimeSeriesSetId: number,
): Promise<HydraulicTimeSeriesSetMigrationResult> {
  return postJsonWithCsrf<HydraulicTimeSeriesSetMigrationResult>(
    `/api/projects/${projectId}/time-series-sets/hydraulic/${hydraulicTimeSeriesSetId}/migrate`,
  );
}

export interface HydraulicTimeSeriesSetBulkMigrationFailure {
  hydraulic_time_series_set_id: number;
  error: string;
}

export interface HydraulicTimeSeriesSetBulkMigrationReport {
  migrated: number[];
  skipped: number[];
  failed: HydraulicTimeSeriesSetBulkMigrationFailure[];
}

export async function migrateAllHydraulicTimeSeriesSets(
  projectId: number,
): Promise<HydraulicTimeSeriesSetBulkMigrationReport> {
  return postJsonWithCsrf<HydraulicTimeSeriesSetBulkMigrationReport>(
    `/api/projects/${projectId}/time-series-sets/hydraulic/migrate-all`,
  );
}

export async function listTimeSeriesSetRevisions(
  projectId: number,
  timeSeriesSetId: number,
  signal?: AbortSignal,
): Promise<ProjectTimeSeriesSetRevision[]> {
  const response = await requestJson<{
    time_series_set_revisions: ProjectTimeSeriesSetRevision[];
  }>(
    `/api/projects/${projectId}/time-series-sets/${timeSeriesSetId}/revisions`,
    { signal },
  );
  return response.time_series_set_revisions;
}

export async function editTimeSeriesSetValues(
  projectId: number,
  timeSeriesSetId: number,
  payload: TimeSeriesSetValuesEditPayload,
): Promise<ProjectTimeSeriesSet> {
  const csrfToken = await getCsrfToken();
  const response = await requestJson<{ time_series_set: ProjectTimeSeriesSet }>(
    `/api/projects/${projectId}/time-series-sets/${timeSeriesSetId}/values`,
    {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
        "X-CSRF-Token": csrfToken,
      },
      body: JSON.stringify(payload),
    },
  );
  return response.time_series_set;
}

export async function regenerateTimeSeriesSet(
  projectId: number,
  timeSeriesSetId: number,
): Promise<ProjectTimeSeriesSet> {
  const response = await postJsonWithCsrf<{
    time_series_set: ProjectTimeSeriesSet;
  }>(
    `/api/projects/${projectId}/time-series-sets/${timeSeriesSetId}/regenerate`,
  );
  return response.time_series_set;
}

export async function applyTimeSeriesTransformation(
  projectId: number,
  timeSeriesSetId: number,
  payload: TimeSeriesTransformationPayload,
): Promise<ProjectTimeSeriesSet> {
  const csrfToken = await getCsrfToken();
  const response = await requestJson<{ time_series_set: ProjectTimeSeriesSet }>(
    `/api/projects/${projectId}/time-series-sets/${timeSeriesSetId}/transformations`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRF-Token": csrfToken,
      },
      body: JSON.stringify(payload),
    },
  );
  return response.time_series_set;
}

export async function applyTimeSeriesCombination(
  projectId: number,
  payload: TimeSeriesTransformationPayload,
): Promise<ProjectTimeSeriesSet> {
  const csrfToken = await getCsrfToken();
  const response = await requestJson<{ time_series_set: ProjectTimeSeriesSet }>(
    `/api/projects/${projectId}/time-series-transformations`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRF-Token": csrfToken,
      },
      body: JSON.stringify(payload),
    },
  );
  return response.time_series_set;
}

export async function ingestTimeSeriesConnector(
  projectId: number,
  payload: TimeSeriesConnectorIngestionPayload,
): Promise<TimeSeriesConnectorIngestionResult> {
  const csrfToken = await getCsrfToken();
  return requestJson<TimeSeriesConnectorIngestionResult>(
    `/api/projects/${projectId}/time-series-sets/connector-ingest`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRF-Token": csrfToken,
      },
      body: JSON.stringify(payload),
    },
  );
}

export async function uploadTimeSeriesSetReplacementSource(
  projectId: number,
  timeSeriesSetId: number,
  file: File,
  sheetName = "",
): Promise<TimeSeriesSource> {
  const csrfToken = await getCsrfToken();
  const body = new FormData();
  body.append("source_file", file);
  if (sheetName.trim()) body.append("sheet_name", sheetName.trim());
  const response = await requestJson<{ source: TimeSeriesSource }>(
    `/api/projects/${projectId}/time-series-sets/${timeSeriesSetId}/replace/upload`,
    {
      method: "POST",
      headers: { "X-CSRF-Token": csrfToken },
      body,
    },
  );
  return response.source;
}

export async function replaceTimeSeriesSetSource(
  projectId: number,
  timeSeriesSetId: number,
  payload: TimeSeriesSetReplacePayload,
): Promise<ProjectTimeSeriesSet> {
  const csrfToken = await getCsrfToken();
  const response = await requestJson<{ time_series_set: ProjectTimeSeriesSet }>(
    `/api/projects/${projectId}/time-series-sets/${timeSeriesSetId}/replace`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRF-Token": csrfToken,
      },
      body: JSON.stringify(payload),
    },
  );
  return response.time_series_set;
}
