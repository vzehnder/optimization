import type { components } from "./schema";

export type CurrentUser = components["schemas"]["CurrentUser"];
export type CurrentUserResponse = components["schemas"]["CurrentUserResponse"];
export type ProjectCreatePayload =
  components["schemas"]["ProjectCreateRequest"];
export type ScenarioCreatePayload =
  components["schemas"]["ScenarioCreateRequest"];

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
  generation_metadata: Record<string, unknown>;
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
  stored_path?: string;
  selected_sheet?: string;
  columns?: string[];
  preview_rows?: TimeSeriesRow[];
  edited_rows?: TimeSeriesRow[];
  mapping_suggestions?: TimeSeriesMapping;
  mapping?: TimeSeriesMapping;
  validation?: TimeSeriesValidation;
  validated_rows?: unknown[];
  [key: string]: unknown;
}

export interface GeneratedCaseValidation {
  ok?: boolean;
  phase?: string;
  message?: string;
  payload?: unknown;
  error_category?: string;
  [key: string]: unknown;
}

export interface GeneratedSystemCaseSnapshot {
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
