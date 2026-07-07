import type { components } from "./schema";
import type { CaseHierarchyProvenance } from "../caseHierarchy";

export type CurrentUser = components["schemas"]["CurrentUser"];
export type CurrentUserResponse = components["schemas"]["CurrentUserResponse"];
export type ProjectCreatePayload =
  components["schemas"]["ProjectCreateRequest"];
export type ScenarioCreatePayload =
  components["schemas"]["ScenarioCreateRequest"];
export type UserCreatePayload = components["schemas"]["UserCreateRequest"];

export interface AuthSessionResponse {
  user: CurrentUser;
  redirect_path: string;
}

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

export interface ProjectClientAccess {
  project_id: number;
  user_id: number;
  email: string;
  display_name: string;
  role: string;
  is_active: boolean;
  assigned_at: string;
  assigned_by: string;
}

export interface Project {
  id: number;
  name: string;
  description: string;
  created_at: string;
  created_by?: string;
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
  created_at: string;
  created_by?: string;
}

export interface ScenarioVersionDetail extends ScenarioVersion {
  system_case_json: unknown;
  validation_payload: unknown;
  generation_metadata: CaseHierarchyProvenance;
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
  artifact_type: string;
  display_name: string;
  media_type: string;
  byte_size: number;
  download_url: string;
}

export interface PublicationPreview {
  project: Project;
  scenario: Scenario;
  scenario_version: ScenarioVersion;
  run: ScenarioRun;
  publication: Publication;
  template: DashboardTemplate;
  results: DashboardResults | null;
  results_error: string;
  downloads: PublicationDownload[];
}

export interface ClientProjectPublications {
  project: Project;
  publications: Publication[];
}

export type ClientPublicationDetail = PublicationPreview;

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
  source: ProjectTimeSeriesSetSource | null;
  horizon: ProjectTimeSeriesSetHorizon;
  signals: ProjectTimeSeriesSetSignal[];
  periods: ProjectTimeSeriesSetPeriod[];
  values: ProjectTimeSeriesSetValue[];
}

export interface ProjectTimeSeriesSetRevision {
  revision_number: number;
  content_hash: string;
  change_summary: string;
  created_at: string;
  created_by: string;
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
  created_at?: string;
  updated_at?: string;
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

export interface HydraulicNaturalInflowSeriesSummary {
  time_series_set_id: number;
  version_number: number;
  version_label: string;
  points: HydraulicNaturalInflowSeriesPoint[];
}

export interface HydraulicNaturalInflowSeriesWrite {
  time_series_set_id?: number | null;
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

export async function listProjectClientAccess(
  projectId: number,
  signal?: AbortSignal,
): Promise<ProjectClientAccess[]> {
  const response = await requestJson<{
    client_access: ProjectClientAccess[];
  }>(`/api/admin/projects/${projectId}/client-access`, { signal });
  return response.client_access;
}

export async function assignProjectClientAccess(
  projectId: number,
  userId: number,
): Promise<ProjectClientAccess> {
  const response = await postJsonWithCsrf<{
    client_access: ProjectClientAccess;
  }>(`/api/admin/projects/${projectId}/client-access`, { user_id: userId });
  return response.client_access;
}

export async function removeProjectClientAccess(
  projectId: number,
  userId: number,
): Promise<void> {
  const csrfToken = await getCsrfToken();
  await requestJson<{ removed: boolean }>(
    `/api/admin/projects/${projectId}/client-access/${userId}`,
    {
      method: "DELETE",
      headers: { "X-CSRF-Token": csrfToken },
    },
  );
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
}

export interface CaseInputVariantDetail {
  variant: CaseInputVariant;
  bindings: CaseTimeSeriesBinding[];
  required_signals: RequiredSignalStatus[];
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
): Promise<Project[]> {
  const response = await requestJson<{ projects: Project[] }>(
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
