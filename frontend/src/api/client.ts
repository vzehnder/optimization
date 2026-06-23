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
  triggered_by?: string;
  trigger_type?: string;
}

interface StructuredErrorBody {
  error?: {
    category?: string;
    message?: string;
    details?: unknown;
  };
  category?: string;
  message?: string;
  detail?: unknown;
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
    structured?.category || body.category || `http_${response.status}`,
    structured?.details ?? body.detail,
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
