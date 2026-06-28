import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { DragEvent, FormEvent, ReactNode, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { ProjectClientAccessSection } from "./Admin";
import {
  ApiError,
  createManualRun,
  createDashboardTemplate,
  createHydraulicDiagram,
  createProject,
  createRunPublicationDraft,
  createScenario,
  createScenarioVersionFromJson,
  deleteScenarioVersion,
  getHydraulicDiagram,
  getPublicationPreview,
  getRun,
  getProject,
  getScenario,
  getScenarioVersion,
  listDashboardTemplates,
  listProjects,
  listRunArtifacts,
  listRunPublications,
  listScenarioRuns,
  listScenarios,
  listScenarioVersions,
  promoteHydraulicDiagram,
  publishPublication,
  saveHydraulicDiagram,
  unpublishPublication,
  uploadScenarioVersion,
  updateDashboardTemplate,
  updatePublicationDraft,
  validateHydraulicDiagram,
  validateHydraulicV3Preview,
  type DashboardTemplate,
  type DashboardTemplatePayload,
  type HydraulicComponentType,
  type HydraulicCurvePoint,
  type HydraulicCurveSummary,
  type HydraulicDiagram,
  type HydraulicDiagramNodeWrite,
  type HydraulicDiagramReachWrite,
  type HydraulicDiagramValidation,
  type HydraulicDiagramViewport,
  type HydraulicCurveWrite,
  type HydraulicNaturalInflowSeriesPoint,
  type HydraulicNaturalInflowSeriesSummary,
  type HydraulicNaturalInflowSeriesWrite,
  type HydraulicPlantParameters,
  type HydraulicReachType,
  type HydraulicReservoirParameters,
  type HydraulicStorageElevationCurveWrite,
  type HydraulicTerminalCondition,
  type HydraulicUnitWrite,
  type Publication,
  type PublicationPayload,
  type Project,
  type ProjectCreatePayload,
  type RunArtifact,
  type Scenario,
  type ScenarioCreatePayload,
  type ScenarioRun,
  type ScenarioVersion,
  type ScenarioVersionDetail,
} from "./api/client";
import {
  DashboardResultsContent,
  RunArtifactsSection,
  RunResultsSection,
} from "./RunResults";

const projectsQueryKey = ["projects"] as const;
const projectQueryKey = (projectId: number) => ["project", projectId] as const;
const scenariosQueryKey = (projectId: number) =>
  ["project-scenarios", projectId] as const;
const scenarioQueryKey = (scenarioId: number) =>
  ["scenario", scenarioId] as const;
const scenarioVersionsQueryKey = (scenarioId: number) =>
  ["scenario-versions", scenarioId] as const;
const scenarioRunsQueryKey = (scenarioId: number) =>
  ["scenario-runs", scenarioId] as const;
const hydraulicDiagramQueryKey = (scenarioId: number) =>
  ["hydraulic-diagram", scenarioId] as const;
const runQueryKey = (runId: number) => ["run", runId] as const;
const dashboardTemplatesQueryKey = (projectId: number) =>
  ["dashboard-templates", projectId] as const;
const runPublicationsQueryKey = (runId: number) =>
  ["run-publications", runId] as const;
const runArtifactsQueryKey = (runId: number) =>
  ["publication-run-artifacts", runId] as const;
const publicationPreviewQueryKey = (publicationId: number) =>
  ["publication-preview", publicationId] as const;
const terminalRunStatuses = new Set(["succeeded", "failed"]);

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error && error.message) return error.message;
  return "No se pudo completar la accion.";
}

function prettyJson(value: unknown): string {
  return JSON.stringify(value ?? {}, null, 2);
}

function visibleHydraulicValidation(
  validation?: HydraulicDiagramValidation | null,
): HydraulicDiagramValidation | null {
  if (!validation || validation.status === "not_validated") return null;
  return validation;
}

function displayValue(value: unknown, fallback = "Pendiente"): string {
  if (value === null || value === undefined || value === "") return fallback;
  return String(value);
}

function displayDuration(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) return "Pendiente";
  return `${Number(seconds).toFixed(2)} s`;
}

function appendUnique<T extends { id: number }>(
  items: T[] | undefined,
  item: T,
): T[] {
  if (!items) return [item];
  if (items.some((existing) => existing.id === item.id)) return items;
  return [...items, item];
}

function replaceById<T extends { id: number }>(
  items: T[] | undefined,
  item: T,
): T[] {
  if (!items) return [item];
  if (!items.some((existing) => existing.id === item.id))
    return [...items, item];
  return items.map((existing) => (existing.id === item.id ? item : existing));
}

function defaultDashboardTemplatePayload(): DashboardTemplatePayload {
  return {
    name: "",
    show_summary: true,
    show_price_chart: true,
    show_grid_chart: true,
    show_renewable_chart: true,
    show_bess_chart: true,
    show_hydro_chart: true,
    show_profit_chart: true,
    show_system_dispatch_table: true,
    show_asset_dispatch_table: true,
    table_preview_limit: 10,
  };
}

function payloadFromTemplate(
  template: DashboardTemplate,
): DashboardTemplatePayload {
  return {
    name: template.name,
    show_summary: template.show_summary,
    show_price_chart: template.show_price_chart,
    show_grid_chart: template.show_grid_chart,
    show_renewable_chart: template.show_renewable_chart,
    show_bess_chart: template.show_bess_chart,
    show_hydro_chart: template.show_hydro_chart,
    show_profit_chart: template.show_profit_chart,
    show_system_dispatch_table: template.show_system_dispatch_table,
    show_asset_dispatch_table: template.show_asset_dispatch_table,
    table_preview_limit: template.table_preview_limit,
  };
}

function useNumericParam(name: string): number | null {
  const params = useParams();
  const rawValue = params[name];
  const value = Number(rawValue);
  if (!rawValue || !Number.isInteger(value) || value < 1) return null;
  return value;
}

function LoadingView({ label }: { label: string }) {
  return <p role="status">{label}</p>;
}

export function ForbiddenView() {
  return (
    <section className="content-panel">
      <h1>Forbidden</h1>
      <p>No tienes acceso a esta area.</p>
    </section>
  );
}

export function NotFoundView({ children }: { children?: ReactNode }) {
  return (
    <section className="content-panel">
      <h1>No encontrado</h1>
      <p>{children || "El recurso solicitado no existe."}</p>
      <Link className="button-link" to="/projects">
        Volver a proyectos
      </Link>
    </section>
  );
}

function RequestErrorView({
  error,
  retry,
}: {
  error: unknown;
  retry?: () => void;
}) {
  if (error instanceof ApiError && error.status === 404) {
    return <NotFoundView>El recurso solicitado no existe.</NotFoundView>;
  }
  if (error instanceof ApiError && error.status === 403) {
    return <ForbiddenView />;
  }
  return (
    <section className="content-panel">
      <h1>No se pudo cargar</h1>
      <p>{errorMessage(error)}</p>
      {retry ? (
        <button type="button" onClick={retry}>
          Reintentar
        </button>
      ) : null}
    </section>
  );
}

function EmptyState({ children }: { children: ReactNode }) {
  return <p className="empty-state">{children}</p>;
}

function Breadcrumbs({ children }: { children: ReactNode }) {
  return (
    <nav className="breadcrumbs" aria-label="Ruta">
      {children}
    </nav>
  );
}

function ProjectList({ projects }: { projects: Project[] }) {
  if (projects.length === 0) {
    return (
      <EmptyState>
        Crea un proyecto para comenzar a modelar escenarios.
      </EmptyState>
    );
  }
  return (
    <ul className="resource-list">
      {projects.map((project) => (
        <li key={project.id}>
          <Link to={`/projects/${project.id}`}>{project.name}</Link>
          <p>{project.description || "Sin descripcion."}</p>
        </li>
      ))}
    </ul>
  );
}

function CreateProjectForm() {
  const queryClient = useQueryClient();
  const [error, setError] = useState("");
  const mutation = useMutation({
    mutationFn: createProject,
    onSuccess: (project) => {
      setError("");
      queryClient.setQueryData<Project[]>(projectsQueryKey, (projects) =>
        appendUnique(projects, project),
      );
      void queryClient.invalidateQueries({ queryKey: projectsQueryKey });
    },
    onError: (mutationError) => setError(errorMessage(mutationError)),
  });

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    const payload: ProjectCreatePayload = {
      name: String(form.get("name") || ""),
      description: String(form.get("description") || ""),
    };
    mutation.mutate(payload, {
      onSuccess: () => formElement.reset(),
    });
  }

  return (
    <form className="workspace-form" onSubmit={submit}>
      <h2>Nuevo proyecto</h2>
      {error ? <p role="alert">{error}</p> : null}
      <label htmlFor="project-name">Nombre del proyecto</label>
      <input id="project-name" name="name" type="text" required />
      <label htmlFor="project-description">Descripcion del proyecto</label>
      <textarea id="project-description" name="description" rows={3} />
      <button type="submit" disabled={mutation.isPending}>
        Crear proyecto
      </button>
    </form>
  );
}

export function ProjectListView() {
  const projects = useQuery({
    queryKey: projectsQueryKey,
    queryFn: ({ signal }) => listProjects(signal),
    retry: false,
  });

  if (projects.isPending) {
    return <LoadingView label="Cargando proyectos" />;
  }
  if (projects.isError) {
    return (
      <RequestErrorView
        error={projects.error}
        retry={() => void projects.refetch()}
      />
    );
  }

  return (
    <section className="workspace-view">
      <header className="workspace-heading">
        <p className="eyebrow">Analyst workspace</p>
        <h1>Proyectos</h1>
      </header>
      <div className="workspace-grid">
        <section className="workspace-section" aria-labelledby="project-list">
          <h2 id="project-list">Proyectos activos</h2>
          <ProjectList projects={projects.data} />
        </section>
        <CreateProjectForm />
      </div>
    </section>
  );
}

function ScenarioList({ scenarios }: { scenarios: Scenario[] }) {
  if (scenarios.length === 0) {
    return (
      <EmptyState>
        Crea un escenario para guardar variantes del proyecto.
      </EmptyState>
    );
  }
  return (
    <ul className="resource-list">
      {scenarios.map((scenario) => (
        <li key={scenario.id}>
          <Link to={`/scenarios/${scenario.id}`}>{scenario.name}</Link>
          <p>{scenario.description || "Sin descripcion."}</p>
        </li>
      ))}
    </ul>
  );
}

function CreateScenarioForm({ projectId }: { projectId: number }) {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [error, setError] = useState("");
  const mutation = useMutation({
    mutationFn: (payload: ScenarioCreatePayload) =>
      createScenario(projectId, payload),
    onSuccess: (scenario) => {
      setError("");
      queryClient.setQueryData<Scenario[]>(
        scenariosQueryKey(projectId),
        (scenarios) => appendUnique(scenarios, scenario),
      );
      void queryClient.invalidateQueries({
        queryKey: scenariosQueryKey(projectId),
      });
      navigate(`/scenarios/${scenario.id}`);
    },
    onError: (mutationError) => setError(errorMessage(mutationError)),
  });

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    const form = new FormData(event.currentTarget);
    mutation.mutate({
      name: String(form.get("name") || ""),
      description: String(form.get("description") || ""),
    });
  }

  return (
    <form className="workspace-form" onSubmit={submit}>
      <h2>Nuevo escenario</h2>
      {error ? <p role="alert">{error}</p> : null}
      <label htmlFor="scenario-name">Nombre del escenario</label>
      <input id="scenario-name" name="name" type="text" required />
      <label htmlFor="scenario-description">Descripcion del escenario</label>
      <textarea id="scenario-description" name="description" rows={3} />
      <button type="submit" disabled={mutation.isPending}>
        Crear escenario
      </button>
    </form>
  );
}

const templateBooleanFields: Array<[keyof DashboardTemplatePayload, string]> = [
  ["show_summary", "Summary"],
  ["show_price_chart", "Price chart"],
  ["show_grid_chart", "Grid chart"],
  ["show_renewable_chart", "Renewable chart"],
  ["show_bess_chart", "BESS chart"],
  ["show_hydro_chart", "Hydro chart"],
  ["show_profit_chart", "Profit chart"],
  ["show_system_dispatch_table", "System dispatch table"],
  ["show_asset_dispatch_table", "Asset dispatch table"],
];

function DashboardTemplateFields({
  value,
  onChange,
  nameLabel,
}: {
  value: DashboardTemplatePayload;
  onChange: (value: DashboardTemplatePayload) => void;
  nameLabel: string;
}) {
  return (
    <>
      <label htmlFor={`${nameLabel}-name`}>{nameLabel}</label>
      <input
        id={`${nameLabel}-name`}
        type="text"
        value={value.name}
        required
        onChange={(event) => onChange({ ...value, name: event.target.value })}
      />
      <div className="template-toggle-grid">
        {templateBooleanFields.map(([field, label]) => (
          <label key={field} className="checkbox-row">
            <input
              type="checkbox"
              aria-label={label}
              checked={Boolean(value[field])}
              onChange={(event) =>
                onChange({ ...value, [field]: event.target.checked })
              }
            />
            <span>{label}</span>
          </label>
        ))}
      </div>
      <label htmlFor={`${nameLabel}-row-limit`}>Table row limit</label>
      <input
        id={`${nameLabel}-row-limit`}
        type="number"
        min="1"
        value={value.table_preview_limit}
        onChange={(event) =>
          onChange({
            ...value,
            table_preview_limit: Math.max(1, Number(event.target.value) || 1),
          })
        }
      />
    </>
  );
}

function CreateDashboardTemplateForm({ projectId }: { projectId: number }) {
  const queryClient = useQueryClient();
  const [payload, setPayload] = useState(defaultDashboardTemplatePayload);
  const [error, setError] = useState("");
  const mutation = useMutation({
    mutationFn: () =>
      createDashboardTemplate(projectId, {
        ...payload,
        name: payload.name.trim(),
      }),
    onSuccess: (template) => {
      setError("");
      setPayload(defaultDashboardTemplatePayload());
      queryClient.setQueryData<DashboardTemplate[]>(
        dashboardTemplatesQueryKey(projectId),
        (templates) => appendUnique(templates, template),
      );
      void queryClient.invalidateQueries({
        queryKey: dashboardTemplatesQueryKey(projectId),
      });
    },
    onError: (mutationError) => setError(errorMessage(mutationError)),
  });

  return (
    <form
      className="workspace-form template-form"
      onSubmit={(event) => {
        event.preventDefault();
        setError("");
        mutation.mutate();
      }}
    >
      <h3>Nuevo template</h3>
      {error ? <p role="alert">{error}</p> : null}
      <DashboardTemplateFields
        value={payload}
        onChange={setPayload}
        nameLabel="Nombre nuevo template"
      />
      <button type="submit" disabled={mutation.isPending}>
        Crear template
      </button>
    </form>
  );
}

function EditDashboardTemplateForm({
  template,
  onDone,
}: {
  template: DashboardTemplate;
  onDone: () => void;
}) {
  const queryClient = useQueryClient();
  const [payload, setPayload] = useState(() => payloadFromTemplate(template));
  const [error, setError] = useState("");
  const mutation = useMutation({
    mutationFn: () =>
      updateDashboardTemplate(template.id, {
        ...payload,
        name: payload.name.trim(),
      }),
    onSuccess: (updated) => {
      setError("");
      queryClient.setQueryData<DashboardTemplate[]>(
        dashboardTemplatesQueryKey(updated.project_id),
        (templates) => replaceById(templates, updated),
      );
      void queryClient.invalidateQueries({
        queryKey: dashboardTemplatesQueryKey(updated.project_id),
      });
      onDone();
    },
    onError: (mutationError) => setError(errorMessage(mutationError)),
  });

  return (
    <form
      className="workspace-form template-form"
      onSubmit={(event) => {
        event.preventDefault();
        setError("");
        mutation.mutate();
      }}
    >
      {error ? <p role="alert">{error}</p> : null}
      <DashboardTemplateFields
        value={payload}
        onChange={setPayload}
        nameLabel="Nombre del template editado"
      />
      <div className="inline-actions">
        <button type="submit" disabled={mutation.isPending}>
          Actualizar template
        </button>
        <button type="button" className="secondary-action" onClick={onDone}>
          Cancelar
        </button>
      </div>
    </form>
  );
}

function DashboardTemplateList({
  templates,
}: {
  templates: DashboardTemplate[];
}) {
  const [editingId, setEditingId] = useState<number | null>(null);
  if (!templates.length) {
    return <EmptyState>Aun no hay templates de dashboard.</EmptyState>;
  }
  return (
    <ul className="resource-list template-list">
      {templates.map((template) => (
        <li key={template.id}>
          <strong>{template.name}</strong>
          <p>
            Summary {template.show_summary ? "on" : "off"} | Charts{" "}
            {[
              template.show_price_chart ? "price" : "",
              template.show_grid_chart ? "grid" : "",
              template.show_renewable_chart ? "renewable" : "",
              template.show_bess_chart ? "BESS" : "",
              template.show_hydro_chart ? "hydro" : "",
              template.show_profit_chart ? "profit" : "",
            ]
              .filter(Boolean)
              .join(", ") || "none"}{" "}
            | rows {template.table_preview_limit}
          </p>
          <button
            type="button"
            className="secondary-action"
            onClick={() => setEditingId(template.id)}
          >
            Editar {template.name}
          </button>
          {editingId === template.id ? (
            <EditDashboardTemplateForm
              template={template}
              onDone={() => setEditingId(null)}
            />
          ) : null}
        </li>
      ))}
    </ul>
  );
}

function DashboardTemplatesSection({ projectId }: { projectId: number }) {
  const templates = useQuery({
    queryKey: dashboardTemplatesQueryKey(projectId),
    queryFn: ({ signal }) => listDashboardTemplates(projectId, signal),
    retry: false,
  });

  return (
    <section
      className="workspace-section"
      aria-labelledby="dashboard-templates"
    >
      <h2 id="dashboard-templates">Dashboard templates</h2>
      {templates.isPending ? (
        <p role="status">Cargando templates</p>
      ) : templates.isError ? (
        <div role="alert">
          <p>{errorMessage(templates.error)}</p>
          <button type="button" onClick={() => void templates.refetch()}>
            Reintentar
          </button>
        </div>
      ) : (
        <DashboardTemplateList templates={templates.data} />
      )}
      <CreateDashboardTemplateForm projectId={projectId} />
    </section>
  );
}

export function ProjectDetailView({
  canManageClientAccess = false,
}: {
  canManageClientAccess?: boolean;
}) {
  const projectId = useNumericParam("projectId");
  const project = useQuery({
    queryKey: projectQueryKey(projectId || 0),
    queryFn: ({ signal }) => getProject(projectId || 0, signal),
    enabled: projectId !== null,
    retry: false,
  });
  const scenarios = useQuery({
    queryKey: scenariosQueryKey(projectId || 0),
    queryFn: ({ signal }) => listScenarios(projectId || 0, signal),
    enabled: projectId !== null,
    retry: false,
  });

  if (projectId === null) {
    return <NotFoundView>El proyecto solicitado no existe.</NotFoundView>;
  }
  if (project.isPending || scenarios.isPending) {
    return <LoadingView label="Cargando proyecto" />;
  }
  if (project.isError) {
    return (
      <RequestErrorView
        error={project.error}
        retry={() => void project.refetch()}
      />
    );
  }
  if (scenarios.isError) {
    return (
      <RequestErrorView
        error={scenarios.error}
        retry={() => void scenarios.refetch()}
      />
    );
  }

  return (
    <section className="workspace-view">
      <Breadcrumbs>
        <Link to="/projects">Proyectos</Link>
        <span aria-hidden="true">/</span>
        <span>{project.data.name}</span>
      </Breadcrumbs>
      <header className="workspace-heading">
        <h1>{project.data.name}</h1>
        <p>{project.data.description || "Sin descripcion."}</p>
      </header>
      <div className="workspace-stack">
        <div className="workspace-grid">
          <section
            className="workspace-section"
            aria-labelledby="scenario-list"
          >
            <h2 id="scenario-list">Escenarios</h2>
            <ScenarioList scenarios={scenarios.data} />
          </section>
          <CreateScenarioForm projectId={projectId} />
        </div>
        {canManageClientAccess ? (
          <ProjectClientAccessSection
            projectId={projectId}
            projectName={project.data.name}
          />
        ) : null}
        <DashboardTemplatesSection projectId={projectId} />
      </div>
    </section>
  );
}

function formatAssetCounts(counts: Record<string, number>): string {
  const entries = Object.entries(counts);
  if (entries.length === 0) return "sin activos";
  return entries
    .map(([assetType, count]) => `${assetType}: ${count}`)
    .join(", ");
}

function ScenarioVersionDeleteControl({
  scenarioId,
  version,
}: {
  scenarioId: number;
  version: ScenarioVersion;
}) {
  const queryClient = useQueryClient();
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState("");
  const mutation = useMutation({
    mutationFn: () => deleteScenarioVersion(version.id),
    onSuccess: () => {
      setError("");
      setConfirming(false);
      queryClient.setQueryData<ScenarioVersion[]>(
        scenarioVersionsQueryKey(scenarioId),
        (versions) =>
          versions?.filter((candidate) => candidate.id !== version.id) || [],
      );
      void queryClient.invalidateQueries({
        queryKey: scenarioVersionsQueryKey(scenarioId),
      });
      void queryClient.invalidateQueries({
        queryKey: scenarioRunsQueryKey(scenarioId),
      });
    },
    onError: (mutationError) => setError(errorMessage(mutationError)),
  });

  return (
    <div className="version-actions">
      {error ? <p role="alert">{error}</p> : null}
      {confirming ? (
        <div className="remove-confirmation">
          <p>Confirma eliminar version {version.version_number}</p>
          <button
            type="button"
            className="danger-button"
            disabled={mutation.isPending}
            onClick={() => mutation.mutate()}
          >
            Confirmar eliminar version {version.version_number}
          </button>
          <button
            type="button"
            className="secondary-action"
            onClick={() => {
              setConfirming(false);
              setError("");
            }}
          >
            Mantener
          </button>
        </div>
      ) : (
        <button
          type="button"
          className="danger-button"
          onClick={() => setConfirming(true)}
        >
          Eliminar version {version.version_number}
        </button>
      )}
    </div>
  );
}

function VersionList({
  scenarioId,
  versions,
}: {
  scenarioId: number;
  versions: ScenarioVersion[];
}) {
  if (versions.length === 0) {
    return <EmptyState>Aun no hay versiones inmutables.</EmptyState>;
  }
  return (
    <ul className="resource-list">
      {versions.map((version) => (
        <li key={version.id}>
          <Link to={`/scenario-versions/${version.id}`}>
            Version {version.version_number}
          </Link>
          <p>
            {version.case_name} | {version.schema_version} |{" "}
            {version.period_count} periodos |{" "}
            {formatAssetCounts(version.asset_counts)}
          </p>
          <ScenarioVersionDeleteControl
            scenarioId={scenarioId}
            version={version}
          />
        </li>
      ))}
    </ul>
  );
}

function ExpertVersionForm({ scenarioId }: { scenarioId: number }) {
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [systemCaseJson, setSystemCaseJson] = useState("");
  const [error, setError] = useState("");
  const [status, setStatus] = useState("");

  function acceptVersion(version: ScenarioVersion) {
    queryClient.setQueryData<ScenarioVersion[]>(
      scenarioVersionsQueryKey(scenarioId),
      (versions) => appendUnique(versions, version),
    );
    void queryClient.invalidateQueries({
      queryKey: scenarioVersionsQueryKey(scenarioId),
    });
    setError("");
    setStatus(`Version ${version.version_number} creada.`);
  }

  const pasteMutation = useMutation({
    mutationFn: () => createScenarioVersionFromJson(scenarioId, systemCaseJson),
    onSuccess: (version) => {
      acceptVersion(version);
      setSystemCaseJson("");
    },
    onError: (mutationError) => {
      setStatus("");
      setError(errorMessage(mutationError));
    },
  });

  const uploadMutation = useMutation({
    mutationFn: (file: File) => uploadScenarioVersion(scenarioId, file),
    onSuccess: (version) => {
      acceptVersion(version);
      if (fileInputRef.current) fileInputRef.current.value = "";
    },
    onError: (mutationError) => {
      setStatus("");
      setError(errorMessage(mutationError));
    },
  });

  function upload() {
    const file = fileInputRef.current?.files?.[0];
    if (!file) {
      setStatus("");
      setError("Selecciona un archivo JSON UTF-8.");
      return;
    }
    uploadMutation.mutate(file);
  }

  return (
    <section className="workspace-section" aria-labelledby="expert-version">
      <h2 id="expert-version">Version experta</h2>
      {error ? <p role="alert">{error}</p> : null}
      {status ? <p className="source-ok">{status}</p> : null}
      <div className="expert-version-grid">
        <label className="field-row field-row-wide" htmlFor="system_case_json">
          <span>system_case JSON</span>
          <textarea
            id="system_case_json"
            rows={8}
            spellCheck={false}
            value={systemCaseJson}
            onChange={(event) => {
              setSystemCaseJson(event.target.value);
              setError("");
              setStatus("");
            }}
          />
        </label>
        <button
          type="button"
          onClick={() => pasteMutation.mutate()}
          disabled={pasteMutation.isPending || !systemCaseJson.trim()}
        >
          {pasteMutation.isPending ? "Creando version" : "Crear version"}
        </button>
      </div>
      <div className="source-upload expert-upload">
        <label className="field-row" htmlFor="system_case_upload">
          <span>Subir system_case JSON</span>
          <input
            id="system_case_upload"
            ref={fileInputRef}
            type="file"
            accept="application/json,.json"
            onChange={() => {
              setError("");
              setStatus("");
            }}
          />
        </label>
        <button
          type="button"
          onClick={upload}
          disabled={uploadMutation.isPending}
        >
          {uploadMutation.isPending ? "Subiendo version" : "Subir version"}
        </button>
      </div>
    </section>
  );
}

function RunList({
  runs,
  versions,
}: {
  runs: ScenarioRun[];
  versions: ScenarioVersion[];
}) {
  if (runs.length === 0) {
    return <EmptyState>Aun no hay corridas para este escenario.</EmptyState>;
  }
  const versionNumbers = new Map(
    versions.map((version) => [version.id, version.version_number]),
  );
  return (
    <ul className="resource-list">
      {runs.map((run) => (
        <li key={run.id}>
          <Link to={`/runs/${run.id}`}>Run {run.id}</Link>
          <p>
            Estado: {run.status} | Version{" "}
            {versionNumbers.get(run.scenario_version_id) || "desconocida"} |
            creado {run.created_at}
          </p>
        </li>
      ))}
    </ul>
  );
}

type HydraulicSaveStatus = "saved" | "dirty" | "saving" | "failed";

const hydraulicComponentLabels: Record<HydraulicComponentType, string> = {
  reservoir: "Embalse",
  junction: "Union",
  plant: "Central",
};

const hydraulicComponentButtonLabels: Record<HydraulicComponentType, string> = {
  reservoir: "Agregar embalse",
  junction: "Agregar union",
  plant: "Agregar central",
};

const hydraulicReachTypes: HydraulicReachType[] = [
  "river",
  "canal",
  "tunnel",
  "gate",
  "spillway",
  "bypass",
  "tailrace",
  "other",
];

function defaultReservoirParameters(): HydraulicReservoirParameters {
  return {
    storage_min_hm3: 0,
    storage_max_hm3: 0,
    initial_storage_hm3: 0,
    terminal_condition: "none",
    terminal_storage_min_hm3: null,
    terminal_water_value_usd_per_hm3: 0,
  };
}

function defaultPlantParameters(): HydraulicPlantParameters {
  return { non_modeled: false, min_power_mw: null, max_power_mw: null };
}

function emptyCurve(): HydraulicCurveWrite {
  return { curve_set_id: null, version_label: null, points: [] };
}

function defaultHydraulicUnit(technicalKey: string): HydraulicUnitWrite {
  return {
    technical_key: technicalKey,
    display_name: technicalKey,
    is_active: true,
    intake_node_key: null,
    discharge_node_key: null,
    min_power_mw: null,
    max_power_mw: null,
    min_flow_m3s: null,
    max_flow_m3s: null,
    flow_power_curve: emptyCurve(),
  };
}

function editableHydraulicNodes(
  diagram: HydraulicDiagram,
): HydraulicDiagramNodeWrite[] {
  return diagram.nodes.map((node) => {
    const base: HydraulicDiagramNodeWrite = {
      component_type: node.component_type,
      technical_key: node.technical_key,
      display_name: node.display_name,
      x: node.x,
      y: node.y,
      natural_inflow_series:
        node.component_type === "plant"
          ? null
          : node.natural_inflow_series
            ? {
                time_series_set_id: node.natural_inflow_series.time_series_set_id,
                version_label: node.natural_inflow_series.version_label,
                points: node.natural_inflow_series.points.map((point) => ({
                  ...point,
                })),
              }
            : null,
    };
    if (node.component_type === "reservoir") {
      return {
        ...base,
        reservoir: node.reservoir ?? defaultReservoirParameters(),
        storage_elevation_curve: node.storage_elevation_curve
          ? {
              curve_set_id: node.storage_elevation_curve.curve_set_id,
              version_label: node.storage_elevation_curve.version_label,
              points: node.storage_elevation_curve.points.map((point) => ({
                ...point,
              })),
            }
          : { curve_set_id: null, version_label: null, points: [] },
      };
    }
    if (node.component_type === "plant") {
      return {
        ...base,
        plant: node.plant ?? defaultPlantParameters(),
        units: (node.units ?? []).map((unit) => ({
          technical_key: unit.technical_key,
          display_name: unit.display_name,
          is_active: unit.is_active,
          intake_node_key: unit.intake_node_key,
          discharge_node_key: unit.discharge_node_key,
          min_power_mw: unit.min_power_mw,
          max_power_mw: unit.max_power_mw,
          min_flow_m3s: unit.min_flow_m3s,
          max_flow_m3s: unit.max_flow_m3s,
          flow_power_curve: unit.flow_power_curve
            ? {
                curve_set_id: unit.flow_power_curve.curve_set_id,
                version_label: unit.flow_power_curve.version_label,
                points: unit.flow_power_curve.points.map((point) => ({
                  ...point,
                })),
              }
            : emptyCurve(),
        })),
      };
    }
    return base;
  });
}

function curvesByNodeKey(
  diagram: HydraulicDiagram,
): Record<string, HydraulicCurveSummary[]> {
  const map: Record<string, HydraulicCurveSummary[]> = {};
  for (const node of diagram.nodes) {
    if (node.component_type === "reservoir") {
      map[node.technical_key] = node.available_curves ?? [];
    }
  }
  return map;
}

function inflowSeriesByNodeKey(
  diagram: HydraulicDiagram,
): Record<string, HydraulicNaturalInflowSeriesSummary[]> {
  const map: Record<string, HydraulicNaturalInflowSeriesSummary[]> = {};
  for (const node of diagram.nodes) {
    if (node.component_type !== "plant") {
      map[node.technical_key] = node.available_inflow_series ?? [];
    }
  }
  return map;
}

function emptyInflowSeries(): HydraulicNaturalInflowSeriesWrite {
  return { time_series_set_id: null, version_label: null, points: [] };
}

function unitCurvesByKey(
  diagram: HydraulicDiagram,
): Record<string, HydraulicCurveSummary[]> {
  const map: Record<string, HydraulicCurveSummary[]> = {};
  for (const node of diagram.nodes) {
    if (node.component_type === "plant") {
      for (const unit of node.units ?? []) {
        map[unit.technical_key] = unit.available_curves ?? [];
      }
    }
  }
  return map;
}

function nextHydraulicUnitKey(nodes: HydraulicDiagramNodeWrite[]): string {
  const existing = new Set<string>();
  for (const node of nodes) {
    for (const unit of node.units ?? []) existing.add(unit.technical_key);
  }
  let index = 1;
  while (existing.has(`unit_${index}`)) index += 1;
  return `unit_${index}`;
}

function editableHydraulicReaches(
  diagram: HydraulicDiagram,
): HydraulicDiagramReachWrite[] {
  return (diagram.reaches || []).map((reach) => ({
    technical_key: reach.technical_key,
    display_name: reach.display_name,
    from_node_key: reach.from_node_key,
    to_node_key: reach.to_node_key,
    reach_type: reach.reach_type,
  }));
}

function defaultHydraulicViewport(
  diagram: HydraulicDiagram | undefined,
): HydraulicDiagramViewport {
  return diagram?.layout.viewport || { x: 0, y: 0, zoom: 1 };
}

function nextHydraulicNodeKey(
  nodes: HydraulicDiagramNodeWrite[],
  componentType: HydraulicComponentType,
): string {
  let index = 1;
  let candidate = `${componentType}_${index}`;
  while (nodes.some((node) => node.technical_key === candidate)) {
    index += 1;
    candidate = `${componentType}_${index}`;
  }
  return candidate;
}

function nextHydraulicReachKey(
  reaches: HydraulicDiagramReachWrite[],
  fromNodeKey: string,
  toNodeKey: string,
): string {
  const base = `reach_${fromNodeKey}_${toNodeKey}`;
  let candidate = base;
  let index = 2;
  while (reaches.some((reach) => reach.technical_key === candidate)) {
    candidate = `${base}_${index}`;
    index += 1;
  }
  return candidate;
}

function defaultHydraulicNodeLabel(
  componentType: HydraulicComponentType,
  technicalKey: string,
): string {
  const suffix = technicalKey.split("_").pop() || "1";
  if (componentType === "reservoir") return `Reservoir ${suffix}`;
  if (componentType === "junction") return `Junction ${suffix}`;
  return `Plant ${suffix}`;
}

function HydraulicNodeList({
  nodes,
  updateNode,
  createReach,
  beginReachDrag,
  completeReachDrag,
}: {
  nodes: HydraulicDiagramNodeWrite[];
  updateNode: (
    technicalKey: string,
    patch: Partial<HydraulicDiagramNodeWrite>,
  ) => void;
  createReach: (fromNodeKey: string, toNodeKey: string) => void;
  beginReachDrag: (fromNodeKey: string) => void;
  completeReachDrag: (toNodeKey: string) => void;
}) {
  if (!nodes.length) {
    return (
      <EmptyState>
        Agrega nodos para crear la topologia hidraulica visible.
      </EmptyState>
    );
  }
  return (
    <ul className="resource-list hydraulic-node-list">
      {nodes.map((node) => (
        <li
          key={node.technical_key}
          data-testid={`hydraulic-node-${node.technical_key}`}
          draggable={node.component_type !== "plant"}
          onDragStart={(event: DragEvent<HTMLLIElement>) => {
            event.dataTransfer.setData("text/plain", node.technical_key);
            event.dataTransfer.effectAllowed = "link";
          }}
          onPointerDown={() => {
            beginReachDrag(node.technical_key);
          }}
          onPointerUp={() => {
            completeReachDrag(node.technical_key);
          }}
          onDragOver={(event: DragEvent<HTMLLIElement>) => {
            event.preventDefault();
          }}
          onDrop={(event: DragEvent<HTMLLIElement>) => {
            event.preventDefault();
            const fromNodeKey = event.dataTransfer.getData("text/plain");
            if (fromNodeKey) {
              createReach(fromNodeKey, node.technical_key);
            }
          }}
        >
          <strong>{node.display_name}</strong>
          <p>
            {hydraulicComponentLabels[node.component_type]} |{" "}
            {node.technical_key}
          </p>
          <div className="draft-field-grid">
            <label
              className="field-row"
              htmlFor={`hydraulic-label-${node.technical_key}`}
            >
              <span>Etiqueta {node.technical_key}</span>
              <input
                id={`hydraulic-label-${node.technical_key}`}
                type="text"
                value={node.display_name}
                onChange={(event) =>
                  updateNode(node.technical_key, {
                    display_name: event.target.value,
                  })
                }
              />
            </label>
            <label
              className="field-row"
              htmlFor={`hydraulic-x-${node.technical_key}`}
            >
              <span>X {node.technical_key}</span>
              <input
                id={`hydraulic-x-${node.technical_key}`}
                type="number"
                value={node.x}
                onChange={(event) =>
                  updateNode(node.technical_key, {
                    x: Number(event.target.value) || 0,
                  })
                }
              />
            </label>
            <label
              className="field-row"
              htmlFor={`hydraulic-y-${node.technical_key}`}
            >
              <span>Y {node.technical_key}</span>
              <input
                id={`hydraulic-y-${node.technical_key}`}
                type="number"
                value={node.y}
                onChange={(event) =>
                  updateNode(node.technical_key, {
                    y: Number(event.target.value) || 0,
                  })
                }
              />
            </label>
          </div>
        </li>
      ))}
    </ul>
  );
}

function HydraulicReachList({
  nodes,
  reaches,
  updateReach,
}: {
  nodes: HydraulicDiagramNodeWrite[];
  reaches: HydraulicDiagramReachWrite[];
  updateReach: (
    technicalKey: string,
    patch: Partial<HydraulicDiagramReachWrite>,
  ) => void;
}) {
  const nodeKeys = nodes
    .filter((node) => node.component_type !== "plant")
    .map((node) => node.technical_key);
  function endpointOptions(currentKey: string) {
    return nodeKeys.includes(currentKey) ? nodeKeys : [...nodeKeys, currentKey];
  }
  if (!reaches.length) {
    return <EmptyState>No hay tramos hidraulicos.</EmptyState>;
  }
  return (
    <ul className="resource-list hydraulic-reach-list">
      {reaches.map((reach) => (
        <li key={reach.technical_key}>
          <strong>{reach.display_name}</strong>
          <p>
            {reach.technical_key} | {reach.from_node_key} -&gt;{" "}
            {reach.to_node_key} | {reach.reach_type}
          </p>
          <div className="draft-field-grid">
            <label
              className="field-row"
              htmlFor={`hydraulic-reach-label-${reach.technical_key}`}
            >
              <span>Etiqueta {reach.technical_key}</span>
              <input
                id={`hydraulic-reach-label-${reach.technical_key}`}
                type="text"
                value={reach.display_name}
                onChange={(event) =>
                  updateReach(reach.technical_key, {
                    display_name: event.target.value,
                  })
                }
              />
            </label>
            <label
              className="field-row"
              htmlFor={`hydraulic-reach-from-${reach.technical_key}`}
            >
              <span>Origen {reach.technical_key}</span>
              <select
                id={`hydraulic-reach-from-${reach.technical_key}`}
                value={reach.from_node_key}
                onChange={(event) =>
                  updateReach(reach.technical_key, {
                    from_node_key: event.target.value,
                  })
                }
              >
                {endpointOptions(reach.from_node_key).map((nodeKey) => (
                  <option key={nodeKey} value={nodeKey}>
                    {nodeKey}
                  </option>
                ))}
              </select>
            </label>
            <label
              className="field-row"
              htmlFor={`hydraulic-reach-to-${reach.technical_key}`}
            >
              <span>Destino {reach.technical_key}</span>
              <select
                id={`hydraulic-reach-to-${reach.technical_key}`}
                value={reach.to_node_key}
                onChange={(event) =>
                  updateReach(reach.technical_key, {
                    to_node_key: event.target.value,
                  })
                }
              >
                {endpointOptions(reach.to_node_key).map((nodeKey) => (
                  <option key={nodeKey} value={nodeKey}>
                    {nodeKey}
                  </option>
                ))}
              </select>
            </label>
            <label
              className="field-row"
              htmlFor={`hydraulic-reach-type-${reach.technical_key}`}
            >
              <span>Tipo {reach.technical_key}</span>
              <select
                id={`hydraulic-reach-type-${reach.technical_key}`}
                value={reach.reach_type}
                onChange={(event) =>
                  updateReach(reach.technical_key, {
                    reach_type: event.target.value as HydraulicReachType,
                  })
                }
              >
                {hydraulicReachTypes.map((reachType) => (
                  <option key={reachType} value={reachType}>
                    {reachType}
                  </option>
                ))}
              </select>
            </label>
          </div>
        </li>
      ))}
    </ul>
  );
}

const hydraulicTerminalConditions: HydraulicTerminalCondition[] = [
  "none",
  "equal_initial",
  "min_terminal",
];

const hydraulicTerminalConditionLabels: Record<
  HydraulicTerminalCondition,
  string
> = {
  none: "Sin condicion",
  equal_initial: "Igual al inicial",
  min_terminal: "Minimo terminal",
};

function HydraulicInflowPanel({
  node,
  availableSeries,
  updateInflowSeries,
}: {
  node: HydraulicDiagramNodeWrite;
  availableSeries: HydraulicNaturalInflowSeriesSummary[];
  updateInflowSeries: (
    technicalKey: string,
    series: HydraulicNaturalInflowSeriesWrite,
  ) => void;
}) {
  const key = node.technical_key;
  const series = node.natural_inflow_series ?? emptyInflowSeries();
  const points = series.points;

  function setPoints(nextPoints: HydraulicNaturalInflowSeriesPoint[]) {
    updateInflowSeries(key, {
      time_series_set_id: null,
      version_label: series.version_label ?? null,
      points: nextPoints,
    });
  }

  return (
    <li className="hydraulic-inflow-panel" data-testid={`hydraulic-inflow-${key}`}>
      <div className="draft-section-heading">
        <h3>Afluente natural {node.display_name}</h3>
        <div className="draft-actions">
          {availableSeries.length ? (
            <label htmlFor={`inflow-version-${key}`}>
              <span>Version de serie {key}</span>
              <select
                id={`inflow-version-${key}`}
                value={series.time_series_set_id ?? ""}
                onChange={(event) => {
                  const selectedId = Number(event.target.value);
                  const selected = availableSeries.find(
                    (option) => option.time_series_set_id === selectedId,
                  );
                  if (!selected) return;
                  updateInflowSeries(key, {
                    time_series_set_id: selected.time_series_set_id,
                    version_label: selected.version_label,
                    points: selected.points.map((point) => ({ ...point })),
                  });
                }}
              >
                <option value="">Serie editada</option>
                {availableSeries.map((option) => (
                  <option
                    key={option.time_series_set_id}
                    value={option.time_series_set_id}
                  >
                    {option.version_label} (v{option.version_number})
                  </option>
                ))}
              </select>
            </label>
          ) : null}
          <button
            type="button"
            data-testid={`inflow-add-point-${key}`}
            onClick={() =>
              setPoints([
                ...points,
                {
                  timestamp: "2026-01-01T00:00:00",
                  duration_hours: 1,
                  value_m3s: 0,
                },
              ])
            }
          >
            Agregar punto de afluente {key}
          </button>
        </div>
      </div>
      {points.length ? (
        <ul className="resource-list hydraulic-inflow-points">
          {points.map((point, index) => (
            <li key={index}>
              <label htmlFor={`inflow-timestamp-${key}-${index}`}>
                <span>
                  Marca temporal {index + 1} {key}
                </span>
                <input
                  id={`inflow-timestamp-${key}-${index}`}
                  type="text"
                  value={point.timestamp}
                  onChange={(event) =>
                    setPoints(
                      points.map((current, currentIndex) =>
                        currentIndex === index
                          ? { ...current, timestamp: event.target.value }
                          : current,
                      ),
                    )
                  }
                />
              </label>
              <label htmlFor={`inflow-duration-${key}-${index}`}>
                <span>
                  Duracion horas {index + 1} {key}
                </span>
                <input
                  id={`inflow-duration-${key}-${index}`}
                  type="number"
                  value={point.duration_hours}
                  onChange={(event) =>
                    setPoints(
                      points.map((current, currentIndex) =>
                        currentIndex === index
                          ? {
                              ...current,
                              duration_hours: Number(event.target.value),
                            }
                          : current,
                      ),
                    )
                  }
                />
              </label>
              <label htmlFor={`inflow-value-${key}-${index}`}>
                <span>
                  Caudal m3/s {index + 1} {key}
                </span>
                <input
                  id={`inflow-value-${key}-${index}`}
                  type="number"
                  value={point.value_m3s}
                  onChange={(event) =>
                    setPoints(
                      points.map((current, currentIndex) =>
                        currentIndex === index
                          ? {
                              ...current,
                              value_m3s: Number(event.target.value),
                            }
                          : current,
                      ),
                    )
                  }
                />
              </label>
              <button
                type="button"
                className="secondary-action"
                onClick={() =>
                  setPoints(
                    points.filter(
                      (_, currentIndex) => currentIndex !== index,
                    ),
                  )
                }
              >
                Quitar punto {index + 1} {key}
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <EmptyState>
          Sin afluente natural vinculado a este nodo.
        </EmptyState>
      )}
    </li>
  );
}

function HydraulicReservoirPanel({
  node,
  availableCurves,
  updateReservoir,
  updateCurve,
}: {
  node: HydraulicDiagramNodeWrite;
  availableCurves: HydraulicCurveSummary[];
  updateReservoir: (
    technicalKey: string,
    patch: Partial<HydraulicReservoirParameters>,
  ) => void;
  updateCurve: (
    technicalKey: string,
    curve: HydraulicStorageElevationCurveWrite,
  ) => void;
}) {
  const key = node.technical_key;
  const reservoir = node.reservoir ?? defaultReservoirParameters();
  const curve: HydraulicStorageElevationCurveWrite =
    node.storage_elevation_curve ?? {
      curve_set_id: null,
      version_label: null,
      points: [],
    };
  const points = curve.points;

  function setPoints(nextPoints: HydraulicCurvePoint[]) {
    updateCurve(key, {
      curve_set_id: null,
      version_label: curve.version_label ?? null,
      points: nextPoints,
    });
  }

  return (
    <li
      className="hydraulic-reservoir-panel"
      data-testid={`hydraulic-reservoir-${key}`}
    >
      <strong>{node.display_name}</strong>
      <div className="reservoir-grid">
        <label htmlFor={`reservoir-storage-min-${key}`}>
          <span>Almacenamiento minimo {key}</span>
          <input
            id={`reservoir-storage-min-${key}`}
            type="number"
            value={reservoir.storage_min_hm3}
            onChange={(event) =>
              updateReservoir(key, {
                storage_min_hm3: Number(event.target.value),
              })
            }
          />
        </label>
        <label htmlFor={`reservoir-storage-max-${key}`}>
          <span>Almacenamiento maximo {key}</span>
          <input
            id={`reservoir-storage-max-${key}`}
            type="number"
            value={reservoir.storage_max_hm3}
            onChange={(event) =>
              updateReservoir(key, {
                storage_max_hm3: Number(event.target.value),
              })
            }
          />
        </label>
        <label htmlFor={`reservoir-initial-${key}`}>
          <span>Almacenamiento inicial {key}</span>
          <input
            id={`reservoir-initial-${key}`}
            type="number"
            value={reservoir.initial_storage_hm3}
            onChange={(event) =>
              updateReservoir(key, {
                initial_storage_hm3: Number(event.target.value),
              })
            }
          />
        </label>
        <label htmlFor={`reservoir-terminal-condition-${key}`}>
          <span>Condicion terminal {key}</span>
          <select
            id={`reservoir-terminal-condition-${key}`}
            value={reservoir.terminal_condition}
            onChange={(event) =>
              updateReservoir(key, {
                terminal_condition: event.target
                  .value as HydraulicTerminalCondition,
              })
            }
          >
            {hydraulicTerminalConditions.map((condition) => (
              <option key={condition} value={condition}>
                {hydraulicTerminalConditionLabels[condition]}
              </option>
            ))}
          </select>
        </label>
        {reservoir.terminal_condition === "min_terminal" ? (
          <label htmlFor={`reservoir-terminal-storage-${key}`}>
            <span>Almacenamiento terminal minimo {key}</span>
            <input
              id={`reservoir-terminal-storage-${key}`}
              type="number"
              value={reservoir.terminal_storage_min_hm3 ?? ""}
              onChange={(event) =>
                updateReservoir(key, {
                  terminal_storage_min_hm3:
                    event.target.value === ""
                      ? null
                      : Number(event.target.value),
                })
              }
            />
          </label>
        ) : null}
        <label htmlFor={`reservoir-terminal-value-${key}`}>
          <span>Valor terminal del agua {key}</span>
          <input
            id={`reservoir-terminal-value-${key}`}
            type="number"
            value={reservoir.terminal_water_value_usd_per_hm3}
            onChange={(event) =>
              updateReservoir(key, {
                terminal_water_value_usd_per_hm3: Number(event.target.value),
              })
            }
          />
        </label>
      </div>
      <div className="reservoir-curve">
        <div className="draft-section-heading">
          <h3>Curva cota-volumen {key}</h3>
          <div className="draft-actions">
            {availableCurves.length ? (
              <label htmlFor={`reservoir-curve-version-${key}`}>
                <span>Version de curva {key}</span>
                <select
                  id={`reservoir-curve-version-${key}`}
                  value={curve.curve_set_id ?? ""}
                  onChange={(event) => {
                    const selectedId = Number(event.target.value);
                    const selected = availableCurves.find(
                      (option) => option.curve_set_id === selectedId,
                    );
                    if (!selected) return;
                    updateCurve(key, {
                      curve_set_id: selected.curve_set_id,
                      version_label: selected.version_label,
                      points: selected.points.map((point) => ({ ...point })),
                    });
                  }}
                >
                  <option value="">Curva editada</option>
                  {availableCurves.map((option) => (
                    <option
                      key={option.curve_set_id}
                      value={option.curve_set_id}
                    >
                      {option.version_label} (v{option.version_number})
                    </option>
                  ))}
                </select>
              </label>
            ) : null}
            <button
              type="button"
              onClick={() => setPoints([...points, { x_value: 0, y_value: 0 }])}
            >
              Agregar punto de curva {key}
            </button>
          </div>
        </div>
        {points.length ? (
          <ul className="resource-list reservoir-curve-points">
            {points.map((point, index) => (
              <li key={index}>
                <label htmlFor={`reservoir-curve-x-${key}-${index}`}>
                  <span>
                    Almacenamiento punto {index + 1} {key}
                  </span>
                  <input
                    id={`reservoir-curve-x-${key}-${index}`}
                    type="number"
                    value={point.x_value}
                    onChange={(event) =>
                      setPoints(
                        points.map((current, currentIndex) =>
                          currentIndex === index
                            ? {
                                ...current,
                                x_value: Number(event.target.value),
                              }
                            : current,
                        ),
                      )
                    }
                  />
                </label>
                <label htmlFor={`reservoir-curve-y-${key}-${index}`}>
                  <span>
                    Cota punto {index + 1} {key}
                  </span>
                  <input
                    id={`reservoir-curve-y-${key}-${index}`}
                    type="number"
                    value={point.y_value}
                    onChange={(event) =>
                      setPoints(
                        points.map((current, currentIndex) =>
                          currentIndex === index
                            ? {
                                ...current,
                                y_value: Number(event.target.value),
                              }
                            : current,
                        ),
                      )
                    }
                  />
                </label>
                <button
                  type="button"
                  className="secondary-action"
                  onClick={() =>
                    setPoints(
                      points.filter(
                        (_, currentIndex) => currentIndex !== index,
                      ),
                    )
                  }
                >
                  Quitar punto {index + 1} {key}
                </button>
              </li>
            ))}
          </ul>
        ) : (
          <EmptyState>
            Agrega puntos de almacenamiento y cota para esta curva.
          </EmptyState>
        )}
      </div>
    </li>
  );
}

function HydraulicUnitSubeditor({
  plantKey,
  unit,
  nodeKeys,
  availableCurves,
  updateUnit,
  removeUnit,
  updateUnitCurve,
}: {
  plantKey: string;
  unit: HydraulicUnitWrite;
  nodeKeys: string[];
  availableCurves: HydraulicCurveSummary[];
  updateUnit: (
    plantKey: string,
    unitKey: string,
    patch: Partial<HydraulicUnitWrite>,
  ) => void;
  removeUnit: (plantKey: string, unitKey: string) => void;
  updateUnitCurve: (
    plantKey: string,
    unitKey: string,
    curve: HydraulicCurveWrite,
  ) => void;
}) {
  const key = unit.technical_key;
  const curve = unit.flow_power_curve ?? emptyCurve();
  const points = curve.points;

  function setPoints(nextPoints: HydraulicCurvePoint[]) {
    updateUnitCurve(plantKey, key, {
      curve_set_id: null,
      version_label: curve.version_label ?? null,
      points: nextPoints,
    });
  }

  function numberField(
    label: string,
    field: keyof HydraulicUnitWrite,
    value: number | null,
  ) {
    return (
      <label htmlFor={`unit-${field}-${key}`}>
        <span>
          {label} {key}
        </span>
        <input
          id={`unit-${field}-${key}`}
          type="number"
          value={value ?? ""}
          onChange={(event) =>
            updateUnit(plantKey, key, {
              [field]:
                event.target.value === "" ? null : Number(event.target.value),
            } as Partial<HydraulicUnitWrite>)
          }
        />
      </label>
    );
  }

  return (
    <li className="hydraulic-unit" data-testid={`hydraulic-unit-${key}`}>
      <div className="draft-field-grid">
        <label htmlFor={`unit-label-${key}`}>
          <span>Etiqueta unidad {key}</span>
          <input
            id={`unit-label-${key}`}
            type="text"
            value={unit.display_name}
            onChange={(event) =>
              updateUnit(plantKey, key, { display_name: event.target.value })
            }
          />
        </label>
        <label htmlFor={`unit-active-${key}`}>
          <span>Activa {key}</span>
          <input
            id={`unit-active-${key}`}
            type="checkbox"
            checked={unit.is_active}
            onChange={(event) =>
              updateUnit(plantKey, key, { is_active: event.target.checked })
            }
          />
        </label>
        <label htmlFor={`unit-intake-${key}`}>
          <span>Nodo de toma {key}</span>
          <select
            id={`unit-intake-${key}`}
            value={unit.intake_node_key ?? ""}
            onChange={(event) =>
              updateUnit(plantKey, key, {
                intake_node_key: event.target.value || null,
              })
            }
          >
            <option value="">Sin nodo</option>
            {nodeKeys.map((nodeKey) => (
              <option key={nodeKey} value={nodeKey}>
                {nodeKey}
              </option>
            ))}
          </select>
        </label>
        <label htmlFor={`unit-discharge-${key}`}>
          <span>Nodo de descarga {key}</span>
          <select
            id={`unit-discharge-${key}`}
            value={unit.discharge_node_key ?? ""}
            onChange={(event) =>
              updateUnit(plantKey, key, {
                discharge_node_key: event.target.value || null,
              })
            }
          >
            <option value="">Sin nodo</option>
            {nodeKeys.map((nodeKey) => (
              <option key={nodeKey} value={nodeKey}>
                {nodeKey}
              </option>
            ))}
          </select>
        </label>
        {numberField("Potencia minima", "min_power_mw", unit.min_power_mw)}
        {numberField("Potencia maxima", "max_power_mw", unit.max_power_mw)}
        {numberField("Caudal minimo", "min_flow_m3s", unit.min_flow_m3s)}
        {numberField("Caudal maximo", "max_flow_m3s", unit.max_flow_m3s)}
      </div>
      <div className="unit-curve">
        <div className="draft-section-heading">
          <h4>Curva caudal-potencia {key}</h4>
          <div className="draft-actions">
            {availableCurves.length ? (
              <label htmlFor={`unit-curve-version-${key}`}>
                <span>Version de curva {key}</span>
                <select
                  id={`unit-curve-version-${key}`}
                  value={curve.curve_set_id ?? ""}
                  onChange={(event) => {
                    const selectedId = Number(event.target.value);
                    const selected = availableCurves.find(
                      (option) => option.curve_set_id === selectedId,
                    );
                    if (!selected) return;
                    updateUnitCurve(plantKey, key, {
                      curve_set_id: selected.curve_set_id,
                      version_label: selected.version_label,
                      points: selected.points.map((point) => ({ ...point })),
                    });
                  }}
                >
                  <option value="">Curva editada</option>
                  {availableCurves.map((option) => (
                    <option key={option.curve_set_id} value={option.curve_set_id}>
                      {option.version_label} (v{option.version_number})
                    </option>
                  ))}
                </select>
              </label>
            ) : null}
            <button
              type="button"
              onClick={() => setPoints([...points, { x_value: 0, y_value: 0 }])}
            >
              Agregar punto de curva {key}
            </button>
          </div>
        </div>
        {points.length ? (
          <ul className="resource-list unit-curve-points">
            {points.map((point, index) => (
              <li key={index}>
                <label htmlFor={`unit-curve-x-${key}-${index}`}>
                  <span>
                    Caudal punto {index + 1} {key}
                  </span>
                  <input
                    id={`unit-curve-x-${key}-${index}`}
                    type="number"
                    value={point.x_value}
                    onChange={(event) =>
                      setPoints(
                        points.map((current, currentIndex) =>
                          currentIndex === index
                            ? { ...current, x_value: Number(event.target.value) }
                            : current,
                        ),
                      )
                    }
                  />
                </label>
                <label htmlFor={`unit-curve-y-${key}-${index}`}>
                  <span>
                    Potencia punto {index + 1} {key}
                  </span>
                  <input
                    id={`unit-curve-y-${key}-${index}`}
                    type="number"
                    value={point.y_value}
                    onChange={(event) =>
                      setPoints(
                        points.map((current, currentIndex) =>
                          currentIndex === index
                            ? { ...current, y_value: Number(event.target.value) }
                            : current,
                        ),
                      )
                    }
                  />
                </label>
                <button
                  type="button"
                  className="secondary-action"
                  onClick={() =>
                    setPoints(
                      points.filter((_, currentIndex) => currentIndex !== index),
                    )
                  }
                >
                  Quitar punto {index + 1} {key}
                </button>
              </li>
            ))}
          </ul>
        ) : (
          <EmptyState>Agrega puntos de caudal y potencia.</EmptyState>
        )}
      </div>
      <button
        type="button"
        className="secondary-action"
        onClick={() => removeUnit(plantKey, key)}
      >
        Quitar unidad {key}
      </button>
    </li>
  );
}

function HydraulicPlantPanel({
  node,
  nodeKeys,
  unitCurves,
  updatePlant,
  addUnit,
  updateUnit,
  removeUnit,
  updateUnitCurve,
}: {
  node: HydraulicDiagramNodeWrite;
  nodeKeys: string[];
  unitCurves: Record<string, HydraulicCurveSummary[]>;
  updatePlant: (
    plantKey: string,
    patch: Partial<HydraulicPlantParameters>,
  ) => void;
  addUnit: (plantKey: string) => void;
  updateUnit: (
    plantKey: string,
    unitKey: string,
    patch: Partial<HydraulicUnitWrite>,
  ) => void;
  removeUnit: (plantKey: string, unitKey: string) => void;
  updateUnitCurve: (
    plantKey: string,
    unitKey: string,
    curve: HydraulicCurveWrite,
  ) => void;
}) {
  const key = node.technical_key;
  const plant = node.plant ?? defaultPlantParameters();
  const units = node.units ?? [];
  return (
    <li className="hydraulic-plant-panel" data-testid={`hydraulic-plant-${key}`}>
      <strong>{node.display_name}</strong>
      <div className="plant-grid">
        <label htmlFor={`plant-non-modeled-${key}`}>
          <span>No modelada {key}</span>
          <input
            id={`plant-non-modeled-${key}`}
            type="checkbox"
            checked={plant.non_modeled}
            onChange={(event) =>
              updatePlant(key, { non_modeled: event.target.checked })
            }
          />
        </label>
        <label htmlFor={`plant-min-power-${key}`}>
          <span>Potencia minima central {key}</span>
          <input
            id={`plant-min-power-${key}`}
            type="number"
            value={plant.min_power_mw ?? ""}
            onChange={(event) =>
              updatePlant(key, {
                min_power_mw:
                  event.target.value === "" ? null : Number(event.target.value),
              })
            }
          />
        </label>
        <label htmlFor={`plant-max-power-${key}`}>
          <span>Potencia maxima central {key}</span>
          <input
            id={`plant-max-power-${key}`}
            type="number"
            value={plant.max_power_mw ?? ""}
            onChange={(event) =>
              updatePlant(key, {
                max_power_mw:
                  event.target.value === "" ? null : Number(event.target.value),
              })
            }
          />
        </label>
      </div>
      <div className="plant-units">
        <div className="draft-section-heading">
          <h3>Unidades {key}</h3>
          <button type="button" onClick={() => addUnit(key)}>
            Agregar unidad {key}
          </button>
        </div>
        {units.length ? (
          <ul className="resource-list hydraulic-unit-list">
            {units.map((unit) => (
              <HydraulicUnitSubeditor
                key={unit.technical_key}
                plantKey={key}
                unit={unit}
                nodeKeys={nodeKeys}
                availableCurves={unitCurves[unit.technical_key] ?? []}
                updateUnit={updateUnit}
                removeUnit={removeUnit}
                updateUnitCurve={updateUnitCurve}
              />
            ))}
          </ul>
        ) : (
          <EmptyState>Agrega una unidad generadora a esta central.</EmptyState>
        )}
      </div>
    </li>
  );
}

function HydraulicDiagramEditor({
  scenario,
  project,
  initialDiagram,
}: {
  scenario: Scenario;
  project?: Project;
  initialDiagram: HydraulicDiagram;
}) {
  const queryClient = useQueryClient();
  const [nodes, setNodes] = useState<HydraulicDiagramNodeWrite[]>(() =>
    editableHydraulicNodes(initialDiagram),
  );
  const [reaches, setReaches] = useState<HydraulicDiagramReachWrite[]>(() =>
    editableHydraulicReaches(initialDiagram),
  );
  const [revision, setRevision] = useState(initialDiagram.revision);
  const [viewport, setViewport] = useState<HydraulicDiagramViewport>(() =>
    defaultHydraulicViewport(initialDiagram),
  );
  const [saveStatus, setSaveStatus] = useState<HydraulicSaveStatus>("saved");
  const [error, setError] = useState("");
  const [promotionMessage, setPromotionMessage] = useState("");
  const [validation, setValidation] =
    useState<HydraulicDiagramValidation | null>(() =>
      visibleHydraulicValidation(initialDiagram.validation),
    );
  const [pendingReachSource, setPendingReachSource] = useState<string | null>(
    null,
  );
  const [availableCurves, setAvailableCurves] = useState<
    Record<string, HydraulicCurveSummary[]>
  >(() => curvesByNodeKey(initialDiagram));
  const [unitCurves, setUnitCurves] = useState<
    Record<string, HydraulicCurveSummary[]>
  >(() => unitCurvesByKey(initialDiagram));
  const [availableInflowSeries, setAvailableInflowSeries] = useState<
    Record<string, HydraulicNaturalInflowSeriesSummary[]>
  >(() => inflowSeriesByNodeKey(initialDiagram));

  const saveMutation = useMutation({
    mutationFn: () =>
      saveHydraulicDiagram(scenario.id, {
        revision,
        viewport,
        nodes,
        reaches,
      }),
    onMutate: () => {
      setSaveStatus("saving");
      setError("");
      setPromotionMessage("");
    },
    onSuccess: (savedDiagram) => {
      queryClient.setQueryData(
        hydraulicDiagramQueryKey(savedDiagram.scenario_id),
        savedDiagram,
      );
      setNodes(editableHydraulicNodes(savedDiagram));
      setReaches(editableHydraulicReaches(savedDiagram));
      setAvailableCurves(curvesByNodeKey(savedDiagram));
      setUnitCurves(unitCurvesByKey(savedDiagram));
      setAvailableInflowSeries(inflowSeriesByNodeKey(savedDiagram));
      setRevision(savedDiagram.revision);
      setViewport(defaultHydraulicViewport(savedDiagram));
      setValidation(visibleHydraulicValidation(savedDiagram.validation));
      setSaveStatus("saved");
      setError("");
    },
    onError: (mutationError) => {
      setSaveStatus("failed");
      setError(errorMessage(mutationError));
    },
  });
  const reloadMutation = useMutation({
    mutationFn: () => getHydraulicDiagram(scenario.id),
    onSuccess: (serverDiagram) => {
      queryClient.setQueryData(
        hydraulicDiagramQueryKey(serverDiagram.scenario_id),
        serverDiagram,
      );
      setNodes(editableHydraulicNodes(serverDiagram));
      setReaches(editableHydraulicReaches(serverDiagram));
      setAvailableCurves(curvesByNodeKey(serverDiagram));
      setUnitCurves(unitCurvesByKey(serverDiagram));
      setAvailableInflowSeries(inflowSeriesByNodeKey(serverDiagram));
      setRevision(serverDiagram.revision);
      setViewport(defaultHydraulicViewport(serverDiagram));
      setValidation(visibleHydraulicValidation(serverDiagram.validation));
      setSaveStatus("saved");
      setError("");
    },
    onError: (mutationError) => {
      setSaveStatus("failed");
      setError(errorMessage(mutationError));
    },
  });
  const v3PreviewMutation = useMutation({
    mutationFn: () => validateHydraulicV3Preview(scenario.id),
    onSuccess: (serverValidation) => {
      setValidation(serverValidation);
      setError("");
      setPromotionMessage("");
    },
    onError: (mutationError) => {
      setError(errorMessage(mutationError));
    },
  });
  const promoteV3Mutation = useMutation({
    mutationFn: () => promoteHydraulicDiagram(scenario.id),
    onSuccess: (version) => {
      const key = scenarioVersionsQueryKey(scenario.id);
      const existingVersions = queryClient.getQueryData<ScenarioVersion[]>(key);
      queryClient.setQueryData(
        key,
        appendUnique(
          Array.isArray(existingVersions) ? existingVersions : [],
          version,
        ),
      );
      setPromotionMessage(`Version v3 promovida: ${version.version_number}`);
      setError("");
    },
    onError: (mutationError) => {
      setError(errorMessage(mutationError));
    },
  });
  const validateMutation = useMutation({
    mutationFn: () => validateHydraulicDiagram(scenario.id),
    onSuccess: (serverValidation) => {
      setValidation(serverValidation);
      setError("");
    },
    onError: (mutationError) => {
      setError(errorMessage(mutationError));
    },
  });

  function markDirty() {
    setSaveStatus("dirty");
    setError("");
    setPromotionMessage("");
    setValidation(null);
  }

  function addNode(componentType: HydraulicComponentType) {
    setNodes((current) => {
      const technicalKey = nextHydraulicNodeKey(current, componentType);
      const nextNode: HydraulicDiagramNodeWrite = {
        component_type: componentType,
        technical_key: technicalKey,
        display_name: defaultHydraulicNodeLabel(componentType, technicalKey),
        x: 120 + current.length * 180,
        y: componentType === "plant" ? 180 : 80 + current.length * 30,
      };
      if (componentType === "reservoir") {
        nextNode.reservoir = defaultReservoirParameters();
        nextNode.storage_elevation_curve = {
          curve_set_id: null,
          version_label: null,
          points: [],
        };
      }
      if (componentType === "plant") {
        nextNode.plant = defaultPlantParameters();
        nextNode.units = [];
      }
      return [...current, nextNode];
    });
    markDirty();
  }

  function updateReservoir(
    technicalKey: string,
    patch: Partial<HydraulicReservoirParameters>,
  ) {
    setNodes((current) =>
      current.map((node) =>
        node.technical_key === technicalKey
          ? {
              ...node,
              reservoir: {
                ...(node.reservoir ?? defaultReservoirParameters()),
                ...patch,
              },
            }
          : node,
      ),
    );
    markDirty();
  }

  function updateCurve(
    technicalKey: string,
    curve: HydraulicStorageElevationCurveWrite,
  ) {
    setNodes((current) =>
      current.map((node) =>
        node.technical_key === technicalKey
          ? { ...node, storage_elevation_curve: curve }
          : node,
      ),
    );
    markDirty();
  }

  function updateInflowSeries(
    technicalKey: string,
    series: HydraulicNaturalInflowSeriesWrite,
  ) {
    setNodes((current) =>
      current.map((node) =>
        node.technical_key === technicalKey
          ? { ...node, natural_inflow_series: series }
          : node,
      ),
    );
    markDirty();
  }

  function updatePlant(
    plantKey: string,
    patch: Partial<HydraulicPlantParameters>,
  ) {
    setNodes((current) =>
      current.map((node) =>
        node.technical_key === plantKey
          ? {
              ...node,
              plant: { ...(node.plant ?? defaultPlantParameters()), ...patch },
            }
          : node,
      ),
    );
    markDirty();
  }

  function mapUnits(
    plantKey: string,
    mapper: (units: HydraulicUnitWrite[]) => HydraulicUnitWrite[],
  ) {
    setNodes((current) =>
      current.map((node) =>
        node.technical_key === plantKey
          ? { ...node, units: mapper(node.units ?? []) }
          : node,
      ),
    );
    markDirty();
  }

  function addUnit(plantKey: string) {
    setNodes((current) => {
      const unitKey = nextHydraulicUnitKey(current);
      return current.map((node) =>
        node.technical_key === plantKey
          ? {
              ...node,
              units: [...(node.units ?? []), defaultHydraulicUnit(unitKey)],
            }
          : node,
      );
    });
    markDirty();
  }

  function updateUnit(
    plantKey: string,
    unitKey: string,
    patch: Partial<HydraulicUnitWrite>,
  ) {
    mapUnits(plantKey, (units) =>
      units.map((unit) =>
        unit.technical_key === unitKey ? { ...unit, ...patch } : unit,
      ),
    );
  }

  function removeUnit(plantKey: string, unitKey: string) {
    mapUnits(plantKey, (units) =>
      units.filter((unit) => unit.technical_key !== unitKey),
    );
  }

  function updateUnitCurve(
    plantKey: string,
    unitKey: string,
    curve: HydraulicCurveWrite,
  ) {
    mapUnits(plantKey, (units) =>
      units.map((unit) =>
        unit.technical_key === unitKey
          ? { ...unit, flow_power_curve: curve }
          : unit,
      ),
    );
  }

  function updateNode(
    technicalKey: string,
    patch: Partial<HydraulicDiagramNodeWrite>,
  ) {
    setNodes((current) =>
      current.map((node) =>
        node.technical_key === technicalKey ? { ...node, ...patch } : node,
      ),
    );
    markDirty();
  }

  function createReach(fromNodeKey: string, toNodeKey: string) {
    if (fromNodeKey === toNodeKey) return;
    const validNodeKeys = new Set(
      nodes
        .filter((node) => node.component_type !== "plant")
        .map((node) => node.technical_key),
    );
    if (!validNodeKeys.has(fromNodeKey) || !validNodeKeys.has(toNodeKey)) {
      return;
    }
    setReaches((current) => {
      const technicalKey = nextHydraulicReachKey(
        current,
        fromNodeKey,
        toNodeKey,
      );
      return [
        ...current,
        {
          technical_key: technicalKey,
          display_name: technicalKey,
          from_node_key: fromNodeKey,
          to_node_key: toNodeKey,
          reach_type: "river",
        },
      ];
    });
    markDirty();
  }

  function updateReach(
    technicalKey: string,
    patch: Partial<HydraulicDiagramReachWrite>,
  ) {
    setReaches((current) =>
      current.map((reach) =>
        reach.technical_key === technicalKey ? { ...reach, ...patch } : reach,
      ),
    );
    markDirty();
  }

  function beginReachDrag(fromNodeKey: string) {
    setPendingReachSource(fromNodeKey);
  }

  function completeReachDrag(toNodeKey: string) {
    if (pendingReachSource) {
      createReach(pendingReachSource, toNodeKey);
    }
    setPendingReachSource(null);
  }

  return (
    <section className="workspace-view">
      <Breadcrumbs>
        <Link to="/projects">Proyectos</Link>
        <span aria-hidden="true">/</span>
        <Link to={`/projects/${scenario.project_id}`}>
          {project?.name || "Proyecto"}
        </Link>
        <span aria-hidden="true">/</span>
        <Link to={`/scenarios/${scenario.id}`}>{scenario.name}</Link>
        <span aria-hidden="true">/</span>
        <span>Diagrama hidraulico</span>
      </Breadcrumbs>
      <header className="workspace-heading">
        <h1>Diagrama hidraulico</h1>
        <p>{scenario.name}</p>
      </header>
      <form
        className="hydraulic-editor"
        onSubmit={(event) => {
          event.preventDefault();
          saveMutation.mutate();
        }}
      >
        <div className="draft-toolbar">
          <span className="draft-status" aria-live="polite">
            Estado: {saveStatus}
          </span>
          <span>Revision {revision}</span>
          <button type="submit" disabled={saveMutation.isPending}>
            Guardar diagrama
          </button>
          <button
            type="button"
            className="secondary-action"
            disabled={reloadMutation.isPending || saveMutation.isPending}
            onClick={() => reloadMutation.mutate()}
          >
            Recargar diagrama
          </button>
          <button
            type="button"
            className="secondary-action"
            disabled={validateMutation.isPending || saveMutation.isPending}
            onClick={() => validateMutation.mutate()}
          >
            Validar topologia
          </button>
          <button
            type="button"
            className="secondary-action"
            disabled={
              v3PreviewMutation.isPending ||
              saveMutation.isPending ||
              saveStatus !== "saved"
            }
            onClick={() => v3PreviewMutation.mutate()}
          >
            Generar preview v3
          </button>
          <button
            type="button"
            className="secondary-action"
            disabled={
              promoteV3Mutation.isPending ||
              saveMutation.isPending ||
              saveStatus !== "saved" ||
              !validation?.ok ||
              validation.stale ||
              !validation.system_case
            }
            onClick={() => promoteV3Mutation.mutate()}
          >
            {promoteV3Mutation.isPending
              ? "Promoviendo v3"
              : "Promover version v3"}
          </button>
        </div>
        {error ? <p role="alert">{error}</p> : null}
        {promotionMessage ? <p role="status">{promotionMessage}</p> : null}
        {validation ? (
          <section
            className="workspace-section validation-summary"
            aria-labelledby="hydraulic-validation-summary"
          >
            <h2 id="hydraulic-validation-summary">{validation.summary}</h2>
            {validation.errors.length ? (
              <ul className="resource-list">
                {validation.errors.map((issue) => (
                  <li key={`${issue.code}-${issue.entity_id}`}>
                    <strong>{issue.technical_key}</strong>
                    <p>{issue.message}</p>
                  </li>
                ))}
              </ul>
            ) : null}
            {validation.warnings.length ? (
              <ul className="resource-list">
                {validation.warnings.map((issue) => (
                  <li key={`${issue.code}-${issue.entity_id}`}>
                    <strong>{issue.technical_key}</strong>
                    <p>{issue.message}</p>
                  </li>
                ))}
              </ul>
            ) : null}
            {validation.stale ? (
              <p role="status">Validacion hidraulica v3 stale</p>
            ) : null}
            {validation.system_case ? (
              <section
                className="workspace-section"
                aria-labelledby="hydraulic-v3-preview"
              >
                <h2 id="hydraulic-v3-preview">Payload v3 generado</h2>
                <pre className="json-preview">
                  {prettyJson(validation.system_case)}
                </pre>
              </section>
            ) : null}
          </section>
        ) : null}
        <section className="workspace-section" aria-labelledby="node-tools">
          <div className="draft-section-heading">
            <h2 id="node-tools">Nodos visibles</h2>
            <div className="draft-actions">
              {(
                ["reservoir", "junction", "plant"] as HydraulicComponentType[]
              ).map((componentType) => (
                <button
                  key={componentType}
                  type="button"
                  onClick={() => addNode(componentType)}
                >
                  {hydraulicComponentButtonLabels[componentType]}
                </button>
              ))}
            </div>
          </div>
          <HydraulicNodeList
            nodes={nodes}
            updateNode={updateNode}
            createReach={createReach}
            beginReachDrag={beginReachDrag}
            completeReachDrag={completeReachDrag}
          />
        </section>
        <section className="workspace-section" aria-labelledby="reach-tools">
          <div className="draft-section-heading">
            <h2 id="reach-tools">Tramos dirigidos</h2>
          </div>
          <HydraulicReachList
            nodes={nodes}
            reaches={reaches}
            updateReach={updateReach}
          />
        </section>
        <section
          className="workspace-section"
          aria-labelledby="reservoir-tools"
        >
          <div className="draft-section-heading">
            <h2 id="reservoir-tools">Parametros de embalse</h2>
          </div>
          {nodes.some((node) => node.component_type === "reservoir") ? (
            <ul className="resource-list hydraulic-reservoir-list">
              {nodes
                .filter((node) => node.component_type === "reservoir")
                .map((node) => (
                  <HydraulicReservoirPanel
                    key={node.technical_key}
                    node={node}
                    availableCurves={availableCurves[node.technical_key] ?? []}
                    updateReservoir={updateReservoir}
                    updateCurve={updateCurve}
                  />
                ))}
            </ul>
          ) : (
            <EmptyState>
              Agrega un embalse para editar almacenamiento y curva cota-volumen.
            </EmptyState>
          )}
        </section>
        <section className="workspace-section" aria-labelledby="inflow-tools">
          <div className="draft-section-heading">
            <h2 id="inflow-tools">Afluentes naturales</h2>
          </div>
          {nodes.some((node) => node.component_type !== "plant") ? (
            <ul className="resource-list hydraulic-inflow-list">
              {nodes
                .filter((node) => node.component_type !== "plant")
                .map((node) => (
                  <HydraulicInflowPanel
                    key={node.technical_key}
                    node={node}
                    availableSeries={
                      availableInflowSeries[node.technical_key] ?? []
                    }
                    updateInflowSeries={updateInflowSeries}
                  />
                ))}
            </ul>
          ) : (
            <EmptyState>
              Agrega un nodo hidraulico para vincular afluentes naturales.
            </EmptyState>
          )}
        </section>
        <section className="workspace-section" aria-labelledby="plant-tools">
          <div className="draft-section-heading">
            <h2 id="plant-tools">Centrales y unidades</h2>
          </div>
          {nodes.some((node) => node.component_type === "plant") ? (
            <ul className="resource-list hydraulic-plant-list">
              {nodes
                .filter((node) => node.component_type === "plant")
                .map((node) => (
                  <HydraulicPlantPanel
                    key={node.technical_key}
                    node={node}
                    nodeKeys={nodes
                      .filter((other) => other.component_type !== "plant")
                      .map((other) => other.technical_key)}
                    unitCurves={unitCurves}
                    updatePlant={updatePlant}
                    addUnit={addUnit}
                    updateUnit={updateUnit}
                    removeUnit={removeUnit}
                    updateUnitCurve={updateUnitCurve}
                  />
                ))}
            </ul>
          ) : (
            <EmptyState>
              Agrega una central para editar sus unidades generadoras.
            </EmptyState>
          )}
        </section>
      </form>
    </section>
  );
}

export function HydraulicDiagramEditorView() {
  const scenarioId = useNumericParam("scenarioId");
  const scenario = useQuery({
    queryKey: scenarioQueryKey(scenarioId || 0),
    queryFn: ({ signal }) => getScenario(scenarioId || 0, signal),
    enabled: scenarioId !== null,
    retry: false,
  });
  const project = useQuery({
    queryKey: projectQueryKey(scenario.data?.project_id || 0),
    queryFn: ({ signal }) => getProject(scenario.data!.project_id, signal),
    enabled: scenario.data !== undefined,
    retry: false,
  });
  const diagram = useQuery({
    queryKey: hydraulicDiagramQueryKey(scenarioId || 0),
    queryFn: () => createHydraulicDiagram(scenarioId || 0),
    enabled: scenarioId !== null,
    retry: false,
  });

  if (scenarioId === null) {
    return <NotFoundView>El escenario solicitado no existe.</NotFoundView>;
  }
  if (scenario.isPending || diagram.isPending) {
    return <LoadingView label="Cargando diagrama hidraulico" />;
  }
  if (scenario.isError) {
    return (
      <RequestErrorView
        error={scenario.error}
        retry={() => void scenario.refetch()}
      />
    );
  }
  if (diagram.isError) {
    return (
      <RequestErrorView
        error={diagram.error}
        retry={() => void diagram.refetch()}
      />
    );
  }

  return (
    <HydraulicDiagramEditor
      key={diagram.data.revision}
      scenario={scenario.data}
      project={project.data}
      initialDiagram={diagram.data}
    />
  );
}

export function ScenarioDetailView() {
  const scenarioId = useNumericParam("scenarioId");
  const scenario = useQuery({
    queryKey: scenarioQueryKey(scenarioId || 0),
    queryFn: ({ signal }) => getScenario(scenarioId || 0, signal),
    enabled: scenarioId !== null,
    retry: false,
  });
  const versions = useQuery({
    queryKey: scenarioVersionsQueryKey(scenarioId || 0),
    queryFn: ({ signal }) => listScenarioVersions(scenarioId || 0, signal),
    enabled: scenarioId !== null,
    retry: false,
  });
  const runs = useQuery({
    queryKey: scenarioRunsQueryKey(scenarioId || 0),
    queryFn: ({ signal }) => listScenarioRuns(scenarioId || 0, signal),
    enabled: scenarioId !== null,
    retry: false,
  });
  const project = useQuery({
    queryKey: projectQueryKey(scenario.data?.project_id || 0),
    queryFn: ({ signal }) => getProject(scenario.data!.project_id, signal),
    enabled: scenario.data !== undefined,
    retry: false,
  });

  if (scenarioId === null) {
    return <NotFoundView>El escenario solicitado no existe.</NotFoundView>;
  }
  if (scenario.isPending || versions.isPending || runs.isPending) {
    return <LoadingView label="Cargando escenario" />;
  }
  if (scenario.isError) {
    return (
      <RequestErrorView
        error={scenario.error}
        retry={() => void scenario.refetch()}
      />
    );
  }
  if (versions.isError) {
    return (
      <RequestErrorView
        error={versions.error}
        retry={() => void versions.refetch()}
      />
    );
  }
  if (runs.isError) {
    return (
      <RequestErrorView error={runs.error} retry={() => void runs.refetch()} />
    );
  }

  return (
    <section className="workspace-view">
      <Breadcrumbs>
        <Link to="/projects">Proyectos</Link>
        <span aria-hidden="true">/</span>
        <Link to={`/projects/${scenario.data.project_id}`}>
          {project.data?.name || "Proyecto"}
        </Link>
        <span aria-hidden="true">/</span>
        <span>{scenario.data.name}</span>
      </Breadcrumbs>
      <header className="workspace-heading">
        <h1>{scenario.data.name}</h1>
        <p>{scenario.data.description || "Sin descripcion."}</p>
        <div className="inline-actions">
          <Link
            className="button-link"
            to={`/scenarios/${scenario.data.id}/draft`}
          >
            Abrir draft
          </Link>
          <Link
            className="button-link"
            to={`/scenarios/${scenario.data.id}/hydraulic-diagram`}
          >
            Abrir diagrama hidraulico
          </Link>
        </div>
      </header>
      <div className="workspace-stack">
        <section className="workspace-section" aria-labelledby="version-list">
          <h2 id="version-list">Versiones inmutables</h2>
          <VersionList scenarioId={scenario.data.id} versions={versions.data} />
        </section>
        <ExpertVersionForm scenarioId={scenario.data.id} />
        <section className="workspace-section" aria-labelledby="run-list">
          <h2 id="run-list">Corridas</h2>
          <RunList runs={runs.data} versions={versions.data} />
        </section>
      </div>
    </section>
  );
}

function ScenarioVersionRunControl({
  version,
}: {
  version: ScenarioVersionDetail;
}) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [error, setError] = useState("");
  const mutation = useMutation({
    mutationFn: () => createManualRun(version.id),
    onSuccess: (run) => {
      setError("");
      queryClient.setQueryData<ScenarioRun>(runQueryKey(run.id), run);
      void queryClient.invalidateQueries({
        queryKey: scenarioRunsQueryKey(version.scenario_id),
      });
      navigate(`/runs/${run.id}`);
    },
    onError: (mutationError) => setError(errorMessage(mutationError)),
  });

  return (
    <section className="workspace-section" aria-labelledby="version-run-launch">
      <h2 id="version-run-launch">Manual run</h2>
      {error ? <p role="alert">{error}</p> : null}
      <p className="source-note">
        Lanza una corrida manual desde esta version inmutable.
      </p>
      <button
        type="button"
        disabled={mutation.isPending}
        onClick={() => {
          if (!mutation.isPending) mutation.mutate();
        }}
      >
        {mutation.isPending ? "Lanzando run" : "Lanzar run"}
      </button>
    </section>
  );
}

function VersionMetadata({ version }: { version: ScenarioVersionDetail }) {
  return (
    <dl className="source-metadata version-metadata">
      <div>
        <dt>Case</dt>
        <dd>{version.case_name}</dd>
      </div>
      <div>
        <dt>Schema</dt>
        <dd>{version.schema_version}</dd>
      </div>
      <div>
        <dt>Periodos</dt>
        <dd>{version.period_count}</dd>
      </div>
      <div>
        <dt>Assets</dt>
        <dd>{formatAssetCounts(version.asset_counts)}</dd>
      </div>
      <div>
        <dt>Creada</dt>
        <dd>{version.created_at}</dd>
      </div>
      <div>
        <dt>Scenario ID</dt>
        <dd>{version.scenario_id}</dd>
      </div>
    </dl>
  );
}

export function ScenarioVersionDetailView() {
  const versionId = useNumericParam("versionId");
  const version = useQuery({
    queryKey: ["scenario-version", versionId || 0] as const,
    queryFn: ({ signal }) => getScenarioVersion(versionId || 0, signal),
    enabled: versionId !== null,
    retry: false,
  });
  const scenario = useQuery({
    queryKey: scenarioQueryKey(version.data?.scenario_id || 0),
    queryFn: ({ signal }) => getScenario(version.data!.scenario_id, signal),
    enabled: version.data !== undefined,
    retry: false,
  });

  if (versionId === null) {
    return <NotFoundView>La version solicitada no existe.</NotFoundView>;
  }
  if (version.isPending) {
    return <LoadingView label="Cargando version" />;
  }
  if (version.isError) {
    return (
      <RequestErrorView
        error={version.error}
        retry={() => void version.refetch()}
      />
    );
  }

  return (
    <section className="workspace-view">
      <Breadcrumbs>
        <Link to="/projects">Proyectos</Link>
        <span aria-hidden="true">/</span>
        <Link to={`/scenarios/${version.data.scenario_id}`}>
          {scenario.data?.name || "Escenario"}
        </Link>
        <span aria-hidden="true">/</span>
        <span>Version {version.data.version_number}</span>
      </Breadcrumbs>
      <header className="workspace-heading">
        <h1>Version {version.data.version_number}</h1>
        <p>{version.data.case_name}</p>
      </header>
      <div className="workspace-stack">
        <ScenarioVersionRunControl version={version.data} />
        <section className="workspace-section" aria-labelledby="version-meta">
          <h2 id="version-meta">Metadata</h2>
          <VersionMetadata version={version.data} />
        </section>
        <section
          className="workspace-section"
          aria-labelledby="version-validation"
        >
          <h2 id="version-validation">Validation payload</h2>
          <pre className="json-panel">
            {prettyJson(version.data.validation_payload)}
          </pre>
        </section>
        <section
          className="workspace-section"
          aria-labelledby="version-generation"
        >
          <h2 id="version-generation">Generation metadata</h2>
          <pre className="json-panel">
            {prettyJson(version.data.generation_metadata)}
          </pre>
        </section>
        <section className="workspace-section" aria-labelledby="version-input">
          <h2 id="version-input">Immutable input</h2>
          <label
            className="field-row field-row-wide"
            htmlFor="immutable_system_case"
          >
            <span>Immutable system_case</span>
            <textarea
              id="immutable_system_case"
              value={prettyJson(version.data.system_case_json)}
              readOnly
              spellCheck={false}
              rows={16}
            />
          </label>
        </section>
      </div>
    </section>
  );
}

function isTerminalRun(run: ScenarioRun | undefined): boolean {
  return terminalRunStatuses.has(run?.status || "");
}

function RunMetadata({ run }: { run: ScenarioRun }) {
  return (
    <dl className="source-metadata version-metadata">
      <div>
        <dt>Estado</dt>
        <dd>{run.status}</dd>
      </div>
      <div>
        <dt>Creado</dt>
        <dd>{run.created_at}</dd>
      </div>
      <div>
        <dt>Iniciado</dt>
        <dd>{displayValue(run.started_at)}</dd>
      </div>
      <div>
        <dt>Finalizado</dt>
        <dd>{displayValue(run.finished_at)}</dd>
      </div>
      <div>
        <dt>Duracion</dt>
        <dd>{displayDuration(run.duration_seconds)}</dd>
      </div>
      <div>
        <dt>Exit code</dt>
        <dd>{displayValue(run.exit_code)}</dd>
      </div>
      <div>
        <dt>Trigger</dt>
        <dd>{displayValue(run.trigger_type, "manual")}</dd>
      </div>
      <div>
        <dt>Triggered by</dt>
        <dd>{displayValue(run.triggered_by, "internal_analyst")}</dd>
      </div>
    </dl>
  );
}

function RunLineage({
  run,
  version,
  scenario,
  project,
}: {
  run: ScenarioRun;
  version?: ScenarioVersionDetail;
  scenario?: Scenario;
  project?: Project;
}) {
  return (
    <dl className="source-metadata version-metadata">
      <div>
        <dt>Proyecto</dt>
        <dd>
          {project ? (
            <Link to={`/projects/${project.id}`}>{project.name}</Link>
          ) : (
            "Cargando"
          )}
        </dd>
      </div>
      <div>
        <dt>Escenario</dt>
        <dd>
          {scenario ? (
            <Link to={`/scenarios/${scenario.id}`}>{scenario.name}</Link>
          ) : (
            "Cargando"
          )}
        </dd>
      </div>
      <div>
        <dt>Version</dt>
        <dd>
          {version ? (
            <Link to={`/scenario-versions/${version.id}`}>
              Version {version.version_number}
            </Link>
          ) : (
            `ID ${run.scenario_version_id}`
          )}
        </dd>
      </div>
      <div>
        <dt>Immutable version ID</dt>
        <dd>{run.scenario_version_id}</dd>
      </div>
    </dl>
  );
}

function RunFailureDetails({ run }: { run: ScenarioRun }) {
  if (run.status !== "failed") return null;
  return (
    <section className="workspace-section" aria-labelledby="run-failure">
      <h2 id="run-failure">Failure context</h2>
      <dl className="source-metadata version-metadata">
        <div>
          <dt>Error</dt>
          <dd>{displayValue(run.error_message, "Sin mensaje")}</dd>
        </div>
      </dl>
      <h3>Structured error</h3>
      <pre className="json-panel">{prettyJson(run.error_payload)}</pre>
      <h3>Stdout</h3>
      <pre className="json-panel">{displayValue(run.stdout, "Sin stdout")}</pre>
      <h3>Stderr</h3>
      <pre className="json-panel">{displayValue(run.stderr, "Sin stderr")}</pre>
    </section>
  );
}

const defaultPublicationArtifactTypes = [
  "summary_json",
  "dispatch_csv",
  "asset_dispatch_csv",
];

function artifactTypeOptions(artifacts: RunArtifact[]): string[] {
  return [
    ...new Set(artifacts.map((artifact) => artifact.artifact_type)),
  ].sort();
}

function initialAllowedArtifactTypes(
  artifactTypes: string[],
  publication?: Publication,
): string[] {
  if (publication) return publication.allowed_artifact_types;
  const defaults = defaultPublicationArtifactTypes.filter((artifactType) =>
    artifactTypes.includes(artifactType),
  );
  return defaults.length ? defaults : artifactTypes;
}

function PublicationEditorForm({
  templates,
  artifacts,
  publication,
  titleLabel,
  notesLabel,
  templateLabel,
  submitLabel,
  pending,
  error,
  onSubmit,
  onCancel,
}: {
  templates: DashboardTemplate[];
  artifacts: RunArtifact[];
  publication?: Publication;
  titleLabel: string;
  notesLabel: string;
  templateLabel: string;
  submitLabel: string;
  pending: boolean;
  error: string;
  onSubmit: (payload: PublicationPayload) => void;
  onCancel?: () => void;
}) {
  const artifactTypes = artifactTypeOptions(artifacts);
  const [dashboardTemplateId, setDashboardTemplateId] = useState(
    publication?.dashboard_template_id || templates[0]?.id || 0,
  );
  const [publicTitle, setPublicTitle] = useState(
    publication?.public_title || "",
  );
  const [analystNotes, setAnalystNotes] = useState(
    publication?.analyst_notes || "",
  );
  const [allowedArtifactTypes, setAllowedArtifactTypes] = useState<string[]>(
    () => initialAllowedArtifactTypes(artifactTypes, publication),
  );

  function toggleArtifact(artifactType: string, checked: boolean) {
    setAllowedArtifactTypes((current) => {
      if (checked && !current.includes(artifactType)) {
        return [...current, artifactType];
      }
      if (!checked) {
        return current.filter((candidate) => candidate !== artifactType);
      }
      return current;
    });
  }

  return (
    <form
      className="workspace-form publication-form"
      onSubmit={(event) => {
        event.preventDefault();
        onSubmit({
          dashboard_template_id: dashboardTemplateId,
          public_title: publicTitle.trim(),
          analyst_notes: analystNotes,
          allowed_artifact_types: allowedArtifactTypes,
        });
      }}
    >
      {error ? <p role="alert">{error}</p> : null}
      <label htmlFor={`${titleLabel}-template`}>{templateLabel}</label>
      <select
        id={`${titleLabel}-template`}
        value={dashboardTemplateId || ""}
        required
        onChange={(event) => setDashboardTemplateId(Number(event.target.value))}
      >
        <option value="" disabled>
          Selecciona template
        </option>
        {templates.map((template) => (
          <option key={template.id} value={template.id}>
            {template.name}
          </option>
        ))}
      </select>
      <label htmlFor={`${titleLabel}-title`}>{titleLabel}</label>
      <input
        id={`${titleLabel}-title`}
        type="text"
        value={publicTitle}
        required
        onChange={(event) => setPublicTitle(event.target.value)}
      />
      <label htmlFor={`${titleLabel}-notes`}>{notesLabel}</label>
      <textarea
        id={`${titleLabel}-notes`}
        rows={3}
        value={analystNotes}
        onChange={(event) => setAnalystNotes(event.target.value)}
      />
      <fieldset className="artifact-fieldset">
        <legend>Allowed artifact types</legend>
        {artifactTypes.length ? (
          artifactTypes.map((artifactType) => (
            <label key={artifactType} className="checkbox-row">
              <input
                type="checkbox"
                aria-label={artifactType}
                checked={allowedArtifactTypes.includes(artifactType)}
                onChange={(event) =>
                  toggleArtifact(artifactType, event.target.checked)
                }
              />
              <span>{artifactType}</span>
            </label>
          ))
        ) : (
          <p className="empty-state">No hay artifacts registrados.</p>
        )}
      </fieldset>
      <div className="inline-actions">
        <button type="submit" disabled={pending || !templates.length}>
          {submitLabel}
        </button>
        {onCancel ? (
          <button type="button" className="secondary-action" onClick={onCancel}>
            Cancelar
          </button>
        ) : null}
      </div>
    </form>
  );
}

function CreatePublicationForm({
  runId,
  templates,
  artifacts,
}: {
  runId: number;
  templates: DashboardTemplate[];
  artifacts: RunArtifact[];
}) {
  const queryClient = useQueryClient();
  const [error, setError] = useState("");
  const mutation = useMutation({
    mutationFn: (payload: PublicationPayload) =>
      createRunPublicationDraft(runId, payload),
    onSuccess: (publication) => {
      setError("");
      queryClient.setQueryData<Publication[]>(
        runPublicationsQueryKey(runId),
        (publications) => appendUnique(publications, publication),
      );
      void queryClient.invalidateQueries({
        queryKey: runPublicationsQueryKey(runId),
      });
    },
    onError: (mutationError) => setError(errorMessage(mutationError)),
  });

  if (!templates.length) {
    return (
      <p className="empty-state">
        Crea un dashboard template del proyecto antes de publicar.
      </p>
    );
  }

  return (
    <div className="publication-create">
      <h3>Nueva publicacion</h3>
      <PublicationEditorForm
        templates={templates}
        artifacts={artifacts}
        titleLabel="Public Title"
        notesLabel="Analyst Notes"
        templateLabel="Dashboard Template"
        submitLabel="Crear publicacion"
        pending={mutation.isPending}
        error={error}
        onSubmit={(payload) => {
          setError("");
          mutation.mutate(payload);
        }}
      />
    </div>
  );
}

function PublicationAudit({ publication }: { publication: Publication }) {
  return (
    <dl className="source-metadata version-metadata publication-audit">
      <div>
        <dt>Status</dt>
        <dd>{publication.status}</dd>
      </div>
      <div>
        <dt>Updated by</dt>
        <dd>{displayValue(publication.updated_by)}</dd>
      </div>
      <div>
        <dt>Updated at</dt>
        <dd>{displayValue(publication.updated_at)}</dd>
      </div>
      <div>
        <dt>Published by</dt>
        <dd>{displayValue(publication.published_by)}</dd>
      </div>
      <div>
        <dt>Published at</dt>
        <dd>{displayValue(publication.published_at)}</dd>
      </div>
      <div>
        <dt>Unpublished at</dt>
        <dd>{displayValue(publication.unpublished_at)}</dd>
      </div>
    </dl>
  );
}

function PublicationItem({
  publication,
  templates,
  artifacts,
}: {
  publication: Publication;
  templates: DashboardTemplate[];
  artifacts: RunArtifact[];
}) {
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [editError, setEditError] = useState("");
  const [transitionError, setTransitionError] = useState("");

  function acceptPublication(updated: Publication) {
    queryClient.setQueryData<Publication[]>(
      runPublicationsQueryKey(updated.run_id),
      (publications) => replaceById(publications, updated),
    );
    void queryClient.invalidateQueries({
      queryKey: runPublicationsQueryKey(updated.run_id),
    });
    void queryClient.invalidateQueries({
      queryKey: publicationPreviewQueryKey(updated.id),
    });
  }

  const editMutation = useMutation({
    mutationFn: (payload: PublicationPayload) =>
      updatePublicationDraft(publication.id, payload),
    onSuccess: (updated) => {
      setEditError("");
      setEditing(false);
      acceptPublication(updated);
    },
    onError: (mutationError) => setEditError(errorMessage(mutationError)),
  });
  const publishMutation = useMutation({
    mutationFn: () => publishPublication(publication.id),
    onSuccess: (updated) => {
      setTransitionError("");
      acceptPublication(updated);
    },
    onError: (mutationError) => setTransitionError(errorMessage(mutationError)),
  });
  const unpublishMutation = useMutation({
    mutationFn: () => unpublishPublication(publication.id),
    onSuccess: (updated) => {
      setTransitionError("");
      acceptPublication(updated);
    },
    onError: (mutationError) => setTransitionError(errorMessage(mutationError)),
  });

  return (
    <li>
      <div className="publication-heading-row">
        <strong>{publication.public_title}</strong>
        <span className="role-badge">{publication.status}</span>
      </div>
      <p>{publication.analyst_notes || "Sin notas."}</p>
      <p>{publication.allowed_artifact_types.join(", ") || "Sin downloads"}</p>
      <PublicationAudit publication={publication} />
      {transitionError ? <p role="alert">{transitionError}</p> : null}
      <div className="inline-actions">
        <Link
          className="button-link"
          to={`/publications/${publication.id}/preview`}
        >
          Preview as client {publication.public_title}
        </Link>
        {publication.status === "draft" ? (
          <button
            type="button"
            className="secondary-action"
            onClick={() => setEditing(true)}
          >
            Editar publicacion {publication.public_title}
          </button>
        ) : null}
        {publication.status !== "published" ? (
          <button
            type="button"
            disabled={publishMutation.isPending}
            onClick={() => {
              setTransitionError("");
              publishMutation.mutate();
            }}
          >
            Publicar {publication.public_title}
          </button>
        ) : (
          <button
            type="button"
            disabled={unpublishMutation.isPending}
            onClick={() => {
              setTransitionError("");
              unpublishMutation.mutate();
            }}
          >
            Unpublicar {publication.public_title}
          </button>
        )}
      </div>
      {editing ? (
        <PublicationEditorForm
          templates={templates}
          artifacts={artifacts}
          publication={publication}
          titleLabel="Public Title editado"
          notesLabel="Analyst Notes editadas"
          templateLabel="Dashboard Template editado"
          submitLabel="Actualizar publicacion"
          pending={editMutation.isPending}
          error={editError}
          onCancel={() => {
            setEditing(false);
            setEditError("");
          }}
          onSubmit={(payload) => {
            setEditError("");
            editMutation.mutate(payload);
          }}
        />
      ) : null}
    </li>
  );
}

function PublicationList({
  publications,
  templates,
  artifacts,
}: {
  publications: Publication[];
  templates: DashboardTemplate[];
  artifacts: RunArtifact[];
}) {
  if (!publications.length) {
    return <EmptyState>No publication drafts yet.</EmptyState>;
  }
  return (
    <ul className="resource-list publication-list">
      {publications.map((publication) => (
        <PublicationItem
          key={publication.id}
          publication={publication}
          templates={templates}
          artifacts={artifacts}
        />
      ))}
    </ul>
  );
}

function PublicationSection({
  run,
  projectId,
}: {
  run: ScenarioRun;
  projectId?: number;
}) {
  const templates = useQuery({
    queryKey: dashboardTemplatesQueryKey(projectId || 0),
    queryFn: ({ signal }) => listDashboardTemplates(projectId || 0, signal),
    enabled: run.status === "succeeded" && projectId !== undefined,
    retry: false,
  });
  const publications = useQuery({
    queryKey: runPublicationsQueryKey(run.id),
    queryFn: ({ signal }) => listRunPublications(run.id, signal),
    enabled: run.status === "succeeded",
    retry: false,
  });
  const artifacts = useQuery({
    queryKey: runArtifactsQueryKey(run.id),
    queryFn: ({ signal }) => listRunArtifacts(run.id, signal),
    enabled: run.status === "succeeded",
    retry: false,
  });

  if (run.status !== "succeeded") return null;
  if (
    projectId === undefined ||
    templates.isPending ||
    publications.isPending ||
    artifacts.isPending
  ) {
    return (
      <section className="workspace-section" aria-labelledby="publications">
        <h2 id="publications">Publication Drafts</h2>
        <p role="status">Cargando publicaciones</p>
      </section>
    );
  }
  if (templates.isError || publications.isError || artifacts.isError) {
    return (
      <section className="workspace-section" aria-labelledby="publications">
        <h2 id="publications">Publication Drafts</h2>
        <p role="alert">
          {errorMessage(
            templates.error || publications.error || artifacts.error,
          )}
        </p>
      </section>
    );
  }

  return (
    <section className="workspace-section" aria-labelledby="publications">
      <h2 id="publications">Publication Drafts</h2>
      <PublicationList
        publications={publications.data}
        templates={templates.data}
        artifacts={artifacts.data}
      />
      <CreatePublicationForm
        runId={run.id}
        templates={templates.data}
        artifacts={artifacts.data}
      />
    </section>
  );
}

function PublicationDownloads({
  downloads,
}: {
  downloads: Array<{
    artifact_type: string;
    display_name: string;
    media_type: string;
    byte_size: number;
    download_url: string;
  }>;
}) {
  return (
    <section
      className="workspace-section"
      aria-labelledby="publication-downloads"
    >
      <h2 id="publication-downloads">Downloads</h2>
      {downloads.length ? (
        <ul className="resource-list artifact-list">
          {downloads.map((download) => (
            <li key={download.artifact_type}>
              <a href={download.download_url} download={download.display_name}>
                {download.display_name}
              </a>
              <p>
                {download.artifact_type} | {download.media_type} |{" "}
                {download.byte_size} bytes
              </p>
            </li>
          ))}
        </ul>
      ) : (
        <p className="empty-state">
          No downloads enabled for this publication.
        </p>
      )}
    </section>
  );
}

export function PublicationPreviewView() {
  const publicationId = useNumericParam("publicationId");
  const preview = useQuery({
    queryKey: publicationPreviewQueryKey(publicationId || 0),
    queryFn: ({ signal }) => getPublicationPreview(publicationId || 0, signal),
    enabled: publicationId !== null,
    retry: false,
  });

  if (publicationId === null) {
    return <NotFoundView>La publicacion solicitada no existe.</NotFoundView>;
  }
  if (preview.isPending) {
    return <LoadingView label="Cargando preview" />;
  }
  if (preview.isError) {
    return (
      <RequestErrorView
        error={preview.error}
        retry={() => void preview.refetch()}
      />
    );
  }

  const data = preview.data;
  return (
    <section className="workspace-view">
      <Breadcrumbs>
        <Link to="/projects">Proyectos</Link>
        <span aria-hidden="true">/</span>
        <Link to={`/projects/${data.project.id}`}>{data.project.name}</Link>
        <span aria-hidden="true">/</span>
        <Link to={`/runs/${data.run.id}`}>Run {data.run.id}</Link>
        <span aria-hidden="true">/</span>
        <span>Preview</span>
      </Breadcrumbs>
      <header className="workspace-heading">
        <p className="eyebrow">Client preview</p>
        <h1>{data.publication.public_title}</h1>
        <p>{data.publication.analyst_notes || "Sin notas."}</p>
      </header>
      <div className="workspace-stack">
        <section className="workspace-section" aria-labelledby="preview-meta">
          <h2 id="preview-meta">Publication</h2>
          <dl className="source-metadata version-metadata">
            <div>
              <dt>Template</dt>
              <dd>{data.template.name}</dd>
            </div>
            <div>
              <dt>Status</dt>
              <dd>{data.publication.status}</dd>
            </div>
            <div>
              <dt>Run Status</dt>
              <dd>{data.run.status}</dd>
            </div>
            <div>
              <dt>Scenario Version</dt>
              <dd>{data.scenario_version.version_number}</dd>
            </div>
          </dl>
        </section>
        <DashboardResultsContent
          results={data.results}
          resultsError={data.results_error}
        />
        <PublicationDownloads downloads={data.downloads} />
      </div>
    </section>
  );
}

export function RunDetailView() {
  const runId = useNumericParam("runId");
  const run = useQuery({
    queryKey: runQueryKey(runId || 0),
    queryFn: ({ signal }) => getRun(runId || 0, signal),
    enabled: runId !== null,
    refetchInterval: (query) =>
      isTerminalRun(query.state.data as ScenarioRun | undefined) ? false : 1000,
    retry: (failureCount, error) =>
      failureCount < 2 && (!(error instanceof ApiError) || error.status >= 500),
    retryDelay: 750,
  });
  const version = useQuery({
    queryKey: ["scenario-version", run.data?.scenario_version_id || 0] as const,
    queryFn: ({ signal }) =>
      getScenarioVersion(run.data!.scenario_version_id, signal),
    enabled: run.data !== undefined,
    retry: false,
  });
  const scenario = useQuery({
    queryKey: scenarioQueryKey(version.data?.scenario_id || 0),
    queryFn: ({ signal }) => getScenario(version.data!.scenario_id, signal),
    enabled: version.data !== undefined,
    retry: false,
  });
  const project = useQuery({
    queryKey: projectQueryKey(scenario.data?.project_id || 0),
    queryFn: ({ signal }) => getProject(scenario.data!.project_id, signal),
    enabled: scenario.data !== undefined,
    retry: false,
  });

  if (runId === null) {
    return <NotFoundView>La corrida solicitada no existe.</NotFoundView>;
  }
  if (run.isPending) {
    return <LoadingView label="Cargando run" />;
  }
  if (run.isError && !run.data) {
    return (
      <RequestErrorView error={run.error} retry={() => void run.refetch()} />
    );
  }

  const runData = run.data!;
  const terminal = isTerminalRun(runData);

  return (
    <section className="workspace-view">
      <Breadcrumbs>
        <Link to="/projects">Proyectos</Link>
        <span aria-hidden="true">/</span>
        {scenario.data ? (
          <Link to={`/scenarios/${scenario.data.id}`}>
            {scenario.data.name}
          </Link>
        ) : (
          <span>Escenario</span>
        )}
        <span aria-hidden="true">/</span>
        {version.data ? (
          <Link to={`/scenario-versions/${version.data.id}`}>
            Version {version.data.version_number}
          </Link>
        ) : (
          <span>Version</span>
        )}
        <span aria-hidden="true">/</span>
        <span>Run {runData.id}</span>
      </Breadcrumbs>
      <header className="workspace-heading">
        <h1>Run {runData.id}</h1>
        <p>{terminal ? "Estado terminal" : "Monitoreando ejecucion"}</p>
      </header>
      <div className="workspace-stack">
        {!terminal && run.isFetching ? (
          <p className="source-note" aria-live="polite">
            Actualizando estado del run.
          </p>
        ) : null}
        {!terminal && run.failureCount > 0 ? (
          <p className="polling-recovery" aria-live="polite">
            Reintentando actualizacion de run.
          </p>
        ) : null}
        <section className="workspace-section" aria-labelledby="run-state">
          <h2 id="run-state">Run state</h2>
          <RunMetadata run={runData} />
        </section>
        <section className="workspace-section" aria-labelledby="run-lineage">
          <h2 id="run-lineage">Lineage</h2>
          <RunLineage
            run={runData}
            version={version.data}
            scenario={scenario.data}
            project={project.data}
          />
        </section>
        <RunFailureDetails run={runData} />
        <RunResultsSection run={runData} />
        <PublicationSection run={runData} projectId={project.data?.id} />
        <RunArtifactsSection run={runData} />
      </div>
    </section>
  );
}
