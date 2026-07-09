import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  DragEvent,
  FormEvent,
  KeyboardEvent,
  PointerEvent,
  ReactNode,
  useMemo,
  useRef,
  useState,
} from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { ProjectClientAccessSection } from "./Admin";
import {
  CaseHierarchyProvenanceSummary,
  HierarchyStaleBadges,
} from "./CaseHierarchyProvenance";
import { hierarchyProvenanceHashLabel } from "./caseHierarchy";
import {
  ApiError,
  bindCaseTimeSeries,
  cloneCaseInputVariant,
  compareRuns,
  createManualRun,
  createDashboardTemplate,
  createHydraulicDiagram,
  createProject,
  createRunPublicationDraft,
  createScenario,
  createScenarioVersionFromJson,
  deleteScenarioVersion,
  editTimeSeriesSetValues,
  getHydraulicDiagram,
  getProjectHydraulicTimeSeriesSet,
  getProjectTimeSeriesSet,
  getPublicationPreview,
  getRun,
  getProject,
  getScenario,
  getScenarioVersion,
  listCaseInputVariants,
  runCaseInputVariant,
  validateCaseInputVariant,
  listDashboardTemplates,
  listProjectHydraulicTimeSeriesSets,
  listProjectTimeSeriesSets,
  listProjects,
  listRunArtifacts,
  listRunPublications,
  listScenarioRuns,
  listScenarios,
  listScenarioVersions,
  listTimeSeriesSetRevisions,
  promoteHydraulicDiagram,
  publishPublication,
  replaceTimeSeriesSetSource,
  saveHydraulicDiagram,
  unpublishPublication,
  uploadScenarioVersion,
  uploadTimeSeriesSetReplacementSource,
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
  type HydraulicTimeSeriesSet,
  type HydraulicTimeSeriesSetSummary,
  type HydraulicUnitWrite,
  type Publication,
  type PublicationPayload,
  type Project,
  type CaseInputVariantDetail,
  type CaseTimeSeriesBinding,
  type RequiredSignalStatus,
  type VariantStalenessReason,
  type ProjectCreatePayload,
  type ProjectTimeSeriesSet,
  type ProjectTimeSeriesSetRevision,
  type ProjectTimeSeriesSetSignal,
  type ProjectTimeSeriesSetSummary,
  type RunArtifact,
  type RunComparison,
  type Scenario,
  type ScenarioCreatePayload,
  type ScenarioRun,
  type ScenarioVersion,
  type ScenarioVersionDetail,
  type TimeSeriesSetReplacePayload,
  type TimeSeriesSource,
} from "./api/client";
import {
  InflowImportError,
  parseInflowCsv,
  parseInflowWorkbook,
} from "./hydro/inflowImport";
import {
  DashboardResultsContent,
  RunArtifactsSection,
  RunResultsSection,
} from "./RunResults";
import {
  catalogSignalUnit,
  findSuggestedCatalogColumn,
  isRecord,
  suggestedCatalogMappings,
  timeSeriesCatalogDataKindOptions,
  timeSeriesCatalogSignalOptions,
  type CatalogSignalMappingDraft,
} from "./timeSeriesCatalogMapping";

const projectsQueryKey = ["projects"] as const;
const projectQueryKey = (projectId: number) => ["project", projectId] as const;
const scenariosQueryKey = (projectId: number) =>
  ["project-scenarios", projectId] as const;
const timeSeriesCatalogQueryKey = (projectId: number) =>
  ["project-time-series-sets", projectId] as const;
const timeSeriesSetQueryKey = (projectId: number, timeSeriesSetId: number) =>
  ["project-time-series-set", projectId, timeSeriesSetId] as const;
const timeSeriesSetRevisionsQueryKey = (
  projectId: number,
  timeSeriesSetId: number,
) => ["project-time-series-set-revisions", projectId, timeSeriesSetId] as const;
const hydraulicTimeSeriesCatalogQueryKey = (projectId: number) =>
  ["project-hydraulic-time-series-sets", projectId] as const;
const hydraulicTimeSeriesSetQueryKey = (
  projectId: number,
  hydraulicTimeSeriesSetId: number,
) =>
  [
    "project-hydraulic-time-series-set",
    projectId,
    hydraulicTimeSeriesSetId,
  ] as const;
const scenarioQueryKey = (scenarioId: number) =>
  ["scenario", scenarioId] as const;
const scenarioVersionsQueryKey = (scenarioId: number) =>
  ["scenario-versions", scenarioId] as const;
const scenarioRunsQueryKey = (scenarioId: number) =>
  ["scenario-runs", scenarioId] as const;
const caseInputVariantsQueryKey = (scenarioId: number) =>
  ["case-input-variants", scenarioId] as const;
const hydraulicDiagramQueryKey = (scenarioId: number) =>
  ["hydraulic-diagram", scenarioId] as const;
const runQueryKey = (runId: number) => ["run", runId] as const;
const dashboardTemplatesQueryKey = (projectId: number) =>
  ["dashboard-templates", projectId] as const;
const runPublicationsQueryKey = (runId: number) =>
  ["run-publications", runId] as const;
const runArtifactsQueryKey = (runId: number) =>
  ["publication-run-artifacts", runId] as const;
const runComparisonQueryKey = (
  baselineRunId: number,
  candidateRunId: number,
  series?: string,
) => ["run-comparison", baselineRunId, candidateRunId, series || null] as const;
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
        <section
          className="workspace-section"
          aria-labelledby="project-time-series-catalog"
        >
          <h2 id="project-time-series-catalog">Series de tiempo</h2>
          <Link to={`/projects/${projectId}/time-series-sets`}>
            Ver catalogo de series de tiempo
          </Link>
        </section>
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

function TimeSeriesCatalogList({
  projectId,
  sets,
}: {
  projectId: number;
  sets: ProjectTimeSeriesSetSummary[];
}) {
  if (sets.length === 0) {
    return <EmptyState>Aun no hay series de tiempo importadas.</EmptyState>;
  }
  return (
    <ul className="resource-list">
      {sets.map((set) => (
        <li key={set.id}>
          <Link to={`/projects/${projectId}/time-series-sets/${set.id}`}>
            {set.name} ({set.version_label})
          </Link>
          <p>
            {set.data_kind} | {set.status} | {set.timezone} | revision{" "}
            {set.revision_number} | {set.signal_count} senales |{" "}
            {set.period_count} periodos
          </p>
          <p>
            <code>{set.content_hash}</code>
          </p>
        </li>
      ))}
    </ul>
  );
}

export function TimeSeriesCatalogView() {
  const projectId = useNumericParam("projectId");
  const project = useQuery({
    queryKey: projectQueryKey(projectId || 0),
    queryFn: ({ signal }) => getProject(projectId || 0, signal),
    enabled: projectId !== null,
    retry: false,
  });
  const timeSeriesSets = useQuery({
    queryKey: timeSeriesCatalogQueryKey(projectId || 0),
    queryFn: ({ signal }) => listProjectTimeSeriesSets(projectId || 0, signal),
    enabled: projectId !== null,
    retry: false,
  });
  const hydraulicTimeSeriesSets = useQuery({
    queryKey: hydraulicTimeSeriesCatalogQueryKey(projectId || 0),
    queryFn: ({ signal }) =>
      listProjectHydraulicTimeSeriesSets(projectId || 0, signal),
    enabled: projectId !== null,
    retry: false,
  });

  if (projectId === null) {
    return <NotFoundView>El proyecto solicitado no existe.</NotFoundView>;
  }
  if (project.isPending || timeSeriesSets.isPending || hydraulicTimeSeriesSets.isPending) {
    return <LoadingView label="Cargando catalogo de series" />;
  }
  if (project.isError) {
    return (
      <RequestErrorView
        error={project.error}
        retry={() => void project.refetch()}
      />
    );
  }
  if (timeSeriesSets.isError) {
    return (
      <RequestErrorView
        error={timeSeriesSets.error}
        retry={() => void timeSeriesSets.refetch()}
      />
    );
  }
  if (hydraulicTimeSeriesSets.isError) {
    return (
      <RequestErrorView
        error={hydraulicTimeSeriesSets.error}
        retry={() => void hydraulicTimeSeriesSets.refetch()}
      />
    );
  }

  return (
    <section className="workspace-view">
      <Breadcrumbs>
        <Link to="/projects">Proyectos</Link>
        <span aria-hidden="true">/</span>
        <Link to={`/projects/${projectId}`}>{project.data.name}</Link>
        <span aria-hidden="true">/</span>
        <span>Catalogo de series</span>
      </Breadcrumbs>
      <header className="workspace-heading">
        <h1>Catalogo de series de tiempo</h1>
        <p>Sets versionados importados a BBDD para {project.data.name}.</p>
      </header>
      <section
        className="workspace-section"
        aria-labelledby="time-series-catalog"
      >
        <h2 id="time-series-catalog">Sets</h2>
        <TimeSeriesCatalogList
          projectId={projectId}
          sets={timeSeriesSets.data}
        />
      </section>
      <section
        className="workspace-section"
        aria-labelledby="hydraulic-time-series-catalog"
      >
        <h2 id="hydraulic-time-series-catalog">
          Series hidraulicas (origen legacy)
        </h2>
        <p>
          Sets creados desde el editor de diagramas hidraulicos, expuestos
          con la misma semantica del catalogo general sin migrar filas.
        </p>
        <HydraulicTimeSeriesCatalogList
          projectId={projectId}
          sets={hydraulicTimeSeriesSets.data}
        />
      </section>
    </section>
  );
}

function HydraulicTimeSeriesCatalogList({
  projectId,
  sets,
}: {
  projectId: number;
  sets: HydraulicTimeSeriesSetSummary[];
}) {
  if (sets.length === 0) {
    return <EmptyState>Aun no hay series hidraulicas legacy.</EmptyState>;
  }
  return (
    <ul className="resource-list">
      {sets.map((set) => (
        <li key={set.id}>
          <Link to={`/projects/${projectId}/time-series-sets/hydraulic/${set.id}`}>
            {set.name}
          </Link>
          <p>
            Origen hidraulico | {set.status} | version {set.version_number} |{" "}
            {set.period_count} periodos
          </p>
        </li>
      ))}
    </ul>
  );
}

function timeSeriesSignalEntityLabel(
  signal: ProjectTimeSeriesSetSignal,
): string {
  if (!signal.entity_type) return "Global";
  return signal.entity_key
    ? `${signal.entity_type}:${signal.entity_key}`
    : signal.entity_type;
}

function TimeSeriesSetSignalList({
  signals,
}: {
  signals: ProjectTimeSeriesSetSignal[];
}) {
  if (signals.length === 0) {
    return <EmptyState>Este set no tiene senales.</EmptyState>;
  }
  return (
    <ul className="resource-list">
      {signals.map((signal) => (
        <li key={signal.signal_key}>
          <strong>{signal.signal_key}</strong>
          <p>
            {signal.unit} | {timeSeriesSignalEntityLabel(signal)}
          </p>
        </li>
      ))}
    </ul>
  );
}

function TimeSeriesSetSourceSummary({
  source,
}: {
  source: ProjectTimeSeriesSet["source"];
}) {
  if (!source) {
    return <EmptyState>Sin fuente registrada.</EmptyState>;
  }
  return (
    <p>
      {source.original_filename} ({source.media_type})
      {source.selected_sheet ? ` | hoja ${source.selected_sheet}` : ""}
    </p>
  );
}

function timeSeriesValueCellKey(
  periodIndex: number,
  signalKey: string,
): string {
  return `${periodIndex}:${signalKey}`;
}

function parseTimeSeriesValueCellKey(key: string): {
  periodIndex: number;
  signalKey: string;
} {
  const separatorIndex = key.indexOf(":");
  return {
    periodIndex: Number(key.slice(0, separatorIndex)),
    signalKey: key.slice(separatorIndex + 1),
  };
}

function TimeSeriesSetValuesEditor({
  projectId,
  timeSeriesSet,
}: {
  projectId: number;
  timeSeriesSet: ProjectTimeSeriesSet;
}) {
  const queryClient = useQueryClient();
  const [valueEdits, setValueEdits] = useState<Record<string, string>>({});
  const [changeSummary, setChangeSummary] = useState("");
  const [error, setError] = useState("");

  const baseValueByKey = useMemo(() => {
    const map = new Map<string, number>();
    for (const value of timeSeriesSet.values) {
      map.set(
        timeSeriesValueCellKey(value.period_index, value.signal_key),
        value.value_numeric,
      );
    }
    return map;
  }, [timeSeriesSet.values]);

  function cellValue(periodIndex: number, signalKey: string): string {
    const key = timeSeriesValueCellKey(periodIndex, signalKey);
    if (Object.prototype.hasOwnProperty.call(valueEdits, key)) {
      return valueEdits[key];
    }
    const original = baseValueByKey.get(key);
    return original === undefined ? "" : String(original);
  }

  function updateCell(periodIndex: number, signalKey: string, text: string) {
    setValueEdits((current) => ({
      ...current,
      [timeSeriesValueCellKey(periodIndex, signalKey)]: text,
    }));
    setError("");
  }

  const mutation = useMutation({
    mutationFn: () =>
      editTimeSeriesSetValues(projectId, timeSeriesSet.id, {
        edits: Object.entries(valueEdits).map(([key, value]) => {
          const { periodIndex, signalKey } = parseTimeSeriesValueCellKey(key);
          return { period_index: periodIndex, signal_key: signalKey, value };
        }),
        change_summary: changeSummary.trim() || undefined,
      }),
    onSuccess: (updatedSet) => {
      setError("");
      setValueEdits({});
      setChangeSummary("");
      queryClient.setQueryData(
        timeSeriesSetQueryKey(projectId, timeSeriesSet.id),
        updatedSet,
      );
      void queryClient.invalidateQueries({
        queryKey: timeSeriesSetRevisionsQueryKey(projectId, timeSeriesSet.id),
      });
    },
    onError: (mutationError) => setError(errorMessage(mutationError)),
  });

  const hasEdits = Object.keys(valueEdits).length > 0;

  return (
    <section className="workspace-section" aria-labelledby="set-values">
      <h2 id="set-values">Valores</h2>
      {error ? <p role="alert">{error}</p> : null}
      {timeSeriesSet.periods.length && timeSeriesSet.signals.length ? (
        <div className="time-series-table-scroll editable-table-scroll">
          <table aria-label="Valores editables del set">
            <thead>
              <tr>
                <th scope="col">Periodo</th>
                {timeSeriesSet.signals.map((signal) => (
                  <th key={signal.signal_key} scope="col">
                    {signal.signal_key} ({signal.unit})
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {timeSeriesSet.periods.map((period) => (
                <tr key={period.period_index}>
                  <th scope="row">{period.timestamp_start}</th>
                  {timeSeriesSet.signals.map((signal) => (
                    <td key={signal.signal_key}>
                      <input
                        aria-label={`Periodo ${period.timestamp_start} ${signal.signal_key}`}
                        value={cellValue(
                          period.period_index,
                          signal.signal_key,
                        )}
                        onChange={(event) =>
                          updateCell(
                            period.period_index,
                            signal.signal_key,
                            event.target.value,
                          )
                        }
                        disabled={mutation.isPending}
                      />
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <EmptyState>Este set no tiene valores.</EmptyState>
      )}
      <div className="version-actions">
        <label htmlFor="value-edit-change-summary">
          Resumen del cambio (opcional)
        </label>
        <input
          id="value-edit-change-summary"
          value={changeSummary}
          onChange={(event) => setChangeSummary(event.target.value)}
          disabled={mutation.isPending}
        />
        <button
          type="button"
          onClick={() => mutation.mutate()}
          disabled={!hasEdits || mutation.isPending}
        >
          {mutation.isPending
            ? "Guardando correcciones"
            : "Guardar correcciones"}
        </button>
        <button
          type="button"
          className="secondary-action"
          onClick={() => {
            setValueEdits({});
            setError("");
          }}
          disabled={!hasEdits || mutation.isPending}
        >
          Descartar cambios
        </button>
      </div>
    </section>
  );
}

type TimeSeriesSetReplaceFormState = {
  data_kind: string;
  timezone: string;
  timestamp_column: string;
  duration_hours_column: string;
  signal_mappings: CatalogSignalMappingDraft[];
  change_summary: string;
};

function defaultTimeSeriesSetReplaceFormState(
  source: TimeSeriesSource,
  timeSeriesSet: ProjectTimeSeriesSet,
): TimeSeriesSetReplaceFormState {
  const columns = Array.isArray(source.columns) ? source.columns : [];
  const signalMappings = suggestedCatalogMappings(source);
  return {
    data_kind: timeSeriesSet.data_kind,
    timezone: timeSeriesSet.timezone,
    timestamp_column: findSuggestedCatalogColumn(columns, [
      "timestamp",
      "period_start",
      "datetime",
      "time",
    ]),
    duration_hours_column: findSuggestedCatalogColumn(columns, [
      "duration_hours",
      "hours",
      "duration",
    ]),
    signal_mappings:
      signalMappings.length > 0
        ? signalMappings
        : [{ source_column: "", signal_key: "", source_unit: "" }],
    change_summary: "",
  };
}

function TimeSeriesSetReplacePanel({
  projectId,
  timeSeriesSet,
}: {
  projectId: number;
  timeSeriesSet: ProjectTimeSeriesSet;
}) {
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [uploadedSource, setUploadedSource] = useState<TimeSeriesSource | null>(
    null,
  );
  const [form, setForm] = useState<TimeSeriesSetReplaceFormState | null>(null);
  const [uploadError, setUploadError] = useState("");
  const [replaceError, setReplaceError] = useState("");

  const uploadMutation = useMutation({
    mutationFn: ({ file, sheet }: { file: File; sheet: string }) =>
      uploadTimeSeriesSetReplacementSource(
        projectId,
        timeSeriesSet.id,
        file,
        sheet,
      ),
    onSuccess: (source) => {
      setUploadError("");
      setUploadedSource(source);
      setForm(defaultTimeSeriesSetReplaceFormState(source, timeSeriesSet));
      setReplaceError("");
    },
    onError: (mutationError) => setUploadError(errorMessage(mutationError)),
  });

  const replaceMutation = useMutation({
    mutationFn: () => {
      if (!uploadedSource || !form) {
        throw new Error("Upload a replacement file first.");
      }
      const payload: TimeSeriesSetReplacePayload = {
        source: {
          id: uploadedSource.id,
          kind: String(uploadedSource.kind || "csv"),
          original_filename: String(uploadedSource.original_filename || ""),
          media_type: String(uploadedSource.media_type || ""),
          checksum: String(uploadedSource.checksum || ""),
          stored_path: String(uploadedSource.stored_path || ""),
          selected_sheet: uploadedSource.selected_sheet || null,
        },
        data_kind: form.data_kind,
        timezone: form.timezone,
        timestamp_column: form.timestamp_column,
        duration_hours_column: form.duration_hours_column,
        signal_mappings: form.signal_mappings.map((mapping) => ({
          source_column: mapping.source_column,
          signal_key: mapping.signal_key,
          source_unit: mapping.source_unit || null,
        })),
        change_summary: form.change_summary.trim() || null,
      };
      return replaceTimeSeriesSetSource(projectId, timeSeriesSet.id, payload);
    },
    onSuccess: (updatedSet) => {
      setReplaceError("");
      setUploadedSource(null);
      setForm(null);
      if (fileInputRef.current) fileInputRef.current.value = "";
      queryClient.setQueryData(
        timeSeriesSetQueryKey(projectId, timeSeriesSet.id),
        updatedSet,
      );
      void queryClient.invalidateQueries({
        queryKey: timeSeriesSetRevisionsQueryKey(projectId, timeSeriesSet.id),
      });
    },
    onError: (mutationError) => setReplaceError(errorMessage(mutationError)),
  });

  function uploadFile(sheet = "") {
    const file = fileInputRef.current?.files?.[0];
    if (!file) {
      setUploadError("Selecciona un archivo CSV o XLSX.");
      return;
    }
    setUploadError("");
    uploadMutation.mutate({ file, sheet });
  }

  function updateForm(patch: Partial<TimeSeriesSetReplaceFormState>) {
    setForm((current) => (current ? { ...current, ...patch } : current));
  }

  function updateSignalMapping(
    index: number,
    patch: Partial<CatalogSignalMappingDraft>,
  ) {
    setForm((current) => {
      if (!current) return current;
      const nextMappings = [...current.signal_mappings];
      const existing = nextMappings[index] || {
        source_column: "",
        signal_key: "",
        source_unit: "",
      };
      const nextMapping = { ...existing, ...patch };
      if (
        patch.signal_key !== undefined &&
        !patch.source_unit &&
        !String(existing.source_unit || "").trim()
      ) {
        nextMapping.source_unit = catalogSignalUnit(patch.signal_key);
      }
      nextMappings[index] = nextMapping;
      return { ...current, signal_mappings: nextMappings };
    });
  }

  function addSignalMapping() {
    setForm((current) =>
      current
        ? {
            ...current,
            signal_mappings: [
              ...current.signal_mappings,
              { source_column: "", signal_key: "", source_unit: "" },
            ],
          }
        : current,
    );
  }

  function removeSignalMapping(index: number) {
    setForm((current) =>
      current
        ? {
            ...current,
            signal_mappings: current.signal_mappings.filter(
              (_mapping, mappingIndex) => mappingIndex !== index,
            ),
          }
        : current,
    );
  }

  const controlsDisabled =
    uploadMutation.isPending || replaceMutation.isPending;
  const columnOptions = [
    { value: "", label: "Selecciona columna" },
    ...((uploadedSource?.columns || []).map((column) => ({
      value: String(column),
      label: String(column),
    })) as Array<{ value: string; label: string }>),
  ];
  const signalMappings = form?.signal_mappings || [];
  const completeSignalMappings = signalMappings.filter(
    (mapping) =>
      Boolean(mapping.source_column.trim()) &&
      Boolean(mapping.signal_key.trim()),
  );
  const canReplace =
    Boolean(form) &&
    Boolean(form?.timezone.trim()) &&
    Boolean(form?.timestamp_column) &&
    Boolean(form?.duration_hours_column) &&
    completeSignalMappings.length > 0 &&
    completeSignalMappings.length === signalMappings.length;

  return (
    <section className="workspace-section" aria-labelledby="set-replace">
      <h2 id="set-replace">Reemplazar con nuevo archivo</h2>
      <p>
        Sube un CSV o XLSX corregido para crear una nueva revision. El nombre y
        la etiqueta de version del set no cambian.
      </p>
      <div className="source-upload">
        <label className="field-row" htmlFor="time_series_replace_file">
          <span>Archivo de reemplazo</span>
          <input
            id="time_series_replace_file"
            ref={fileInputRef}
            type="file"
            accept="text/csv,.csv,.xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            disabled={controlsDisabled}
          />
        </label>
        <button
          type="button"
          onClick={() => uploadFile()}
          disabled={controlsDisabled}
        >
          {uploadMutation.isPending
            ? "Subiendo archivo"
            : "Subir archivo de reemplazo"}
        </button>
      </div>
      {uploadError ? <p role="alert">{uploadError}</p> : null}
      {uploadedSource?.kind === "xlsx" &&
      (uploadedSource.available_sheets?.length ?? 0) > 1 ? (
        <label className="field-row" htmlFor="time_series_replace_sheet">
          <span>Hoja</span>
          <select
            id="time_series_replace_sheet"
            value={uploadedSource.selected_sheet || ""}
            onChange={(event) => uploadFile(event.target.value)}
            disabled={controlsDisabled}
          >
            {uploadedSource.available_sheets?.map((sheet) => (
              <option key={sheet} value={sheet}>
                {sheet}
              </option>
            ))}
          </select>
        </label>
      ) : null}
      {uploadedSource ? <p>{uploadedSource.original_filename}</p> : null}
      {uploadedSource && form ? (
        <>
          <div className="draft-field-grid">
            <label
              className="field-row"
              htmlFor="time_series_replace_data_kind"
            >
              <span>Tipo de dato</span>
              <select
                id="time_series_replace_data_kind"
                value={form.data_kind}
                onChange={(event) =>
                  updateForm({ data_kind: event.target.value })
                }
                disabled={replaceMutation.isPending}
              >
                {timeSeriesCatalogDataKindOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="field-row" htmlFor="time_series_replace_timezone">
              <span>Zona horaria</span>
              <input
                id="time_series_replace_timezone"
                value={form.timezone}
                onChange={(event) =>
                  updateForm({ timezone: event.target.value })
                }
                disabled={replaceMutation.isPending}
              />
            </label>
            <label
              className="field-row"
              htmlFor="time_series_replace_timestamp_column"
            >
              <span>Columna de marca de tiempo</span>
              <select
                id="time_series_replace_timestamp_column"
                value={form.timestamp_column}
                onChange={(event) =>
                  updateForm({ timestamp_column: event.target.value })
                }
                disabled={replaceMutation.isPending}
              >
                {columnOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
            <label
              className="field-row"
              htmlFor="time_series_replace_duration_column"
            >
              <span>Columna de duracion (horas)</span>
              <select
                id="time_series_replace_duration_column"
                value={form.duration_hours_column}
                onChange={(event) =>
                  updateForm({ duration_hours_column: event.target.value })
                }
                disabled={replaceMutation.isPending}
              >
                {columnOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <div className="source-mapping">
            <h3>Mapeo de senales</h3>
            {signalMappings.map((mapping, mappingIndex) => (
              <div
                className="draft-field-grid"
                key={`replace-signal-${mappingIndex}`}
              >
                <label
                  className="field-row"
                  htmlFor={`time_series_replace_signal_source_${mappingIndex}`}
                >
                  <span>{`Columna de origen ${mappingIndex + 1}`}</span>
                  <select
                    id={`time_series_replace_signal_source_${mappingIndex}`}
                    value={mapping.source_column}
                    onChange={(event) =>
                      updateSignalMapping(mappingIndex, {
                        source_column: event.target.value,
                      })
                    }
                    disabled={replaceMutation.isPending}
                  >
                    {columnOptions.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </label>
                <label
                  className="field-row"
                  htmlFor={`time_series_replace_signal_key_${mappingIndex}`}
                >
                  <span>{`Senal canonica ${mappingIndex + 1}`}</span>
                  <select
                    id={`time_series_replace_signal_key_${mappingIndex}`}
                    value={mapping.signal_key}
                    onChange={(event) =>
                      updateSignalMapping(mappingIndex, {
                        signal_key: event.target.value,
                      })
                    }
                    disabled={replaceMutation.isPending}
                  >
                    <option value="">Selecciona senal</option>
                    {timeSeriesCatalogSignalOptions.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </label>
                <label
                  className="field-row"
                  htmlFor={`time_series_replace_signal_unit_${mappingIndex}`}
                >
                  <span>{`Unidad de origen ${mappingIndex + 1}`}</span>
                  <input
                    id={`time_series_replace_signal_unit_${mappingIndex}`}
                    value={mapping.source_unit}
                    onChange={(event) =>
                      updateSignalMapping(mappingIndex, {
                        source_unit: event.target.value,
                      })
                    }
                    disabled={replaceMutation.isPending}
                  />
                </label>
                {signalMappings.length > 1 ? (
                  <button
                    type="button"
                    onClick={() => removeSignalMapping(mappingIndex)}
                    disabled={replaceMutation.isPending}
                  >
                    {`Quitar mapeo ${mappingIndex + 1}`}
                  </button>
                ) : null}
              </div>
            ))}
          </div>
          <button
            type="button"
            onClick={addSignalMapping}
            disabled={replaceMutation.isPending}
          >
            Agregar mapeo de senal
          </button>
          <div className="version-actions">
            <label htmlFor="time_series_replace_change_summary">
              Resumen del reemplazo (opcional)
            </label>
            <input
              id="time_series_replace_change_summary"
              value={form.change_summary}
              onChange={(event) =>
                updateForm({ change_summary: event.target.value })
              }
              disabled={replaceMutation.isPending}
            />
            <button
              type="button"
              onClick={() => replaceMutation.mutate()}
              disabled={!canReplace || replaceMutation.isPending}
            >
              {replaceMutation.isPending
                ? "Reemplazando set"
                : "Reemplazar set"}
            </button>
          </div>
          {replaceError ? <p role="alert">{replaceError}</p> : null}
        </>
      ) : null}
    </section>
  );
}

function TimeSeriesSetOriginSummary({
  revisionMetadata,
}: {
  revisionMetadata: Record<string, unknown> | undefined;
}) {
  const origin = revisionMetadata?.origin;
  if (!isRecord(origin) || origin.kind !== "legacy_draft_extraction") {
    return null;
  }
  return (
    <section className="workspace-section" aria-labelledby="set-origin">
      <h2 id="set-origin">Origen</h2>
      <p>
        Extraido desde borrador legacy (scenario {String(origin.scenario_id)},
        fuente {String(origin.source_filename || origin.source_id)})
      </p>
      <p>
        Extraido por {String(origin.extracted_by)} el{" "}
        {String(origin.extracted_at)}
      </p>
    </section>
  );
}

function TimeSeriesSetRevisionHistory({
  revisions,
}: {
  revisions: ProjectTimeSeriesSetRevision[];
}) {
  if (revisions.length === 0) {
    return <EmptyState>Aun no hay revisiones registradas.</EmptyState>;
  }
  return (
    <ul className="resource-list">
      {revisions.map((revision) => (
        <li key={revision.revision_number}>
          <strong>Revision {revision.revision_number}</strong>
          <p>
            {revision.created_by} | {revision.created_at}
          </p>
          <p>{revision.change_summary}</p>
          <p>
            <code>{revision.content_hash}</code>
          </p>
        </li>
      ))}
    </ul>
  );
}

export function TimeSeriesSetDetailView() {
  const projectId = useNumericParam("projectId");
  const timeSeriesSetId = useNumericParam("timeSeriesSetId");
  const timeSeriesSet = useQuery({
    queryKey: timeSeriesSetQueryKey(projectId || 0, timeSeriesSetId || 0),
    queryFn: ({ signal }) =>
      getProjectTimeSeriesSet(projectId || 0, timeSeriesSetId || 0, signal),
    enabled: projectId !== null && timeSeriesSetId !== null,
    retry: false,
  });
  const timeSeriesSetRevisions = useQuery({
    queryKey: timeSeriesSetRevisionsQueryKey(
      projectId || 0,
      timeSeriesSetId || 0,
    ),
    queryFn: ({ signal }) =>
      listTimeSeriesSetRevisions(projectId || 0, timeSeriesSetId || 0, signal),
    enabled: projectId !== null && timeSeriesSetId !== null,
    retry: false,
  });

  if (projectId === null || timeSeriesSetId === null) {
    return <NotFoundView>El set de series solicitado no existe.</NotFoundView>;
  }
  if (timeSeriesSet.isPending) {
    return <LoadingView label="Cargando set de series" />;
  }
  if (timeSeriesSet.isError) {
    return (
      <RequestErrorView
        error={timeSeriesSet.error}
        retry={() => void timeSeriesSet.refetch()}
      />
    );
  }

  const set = timeSeriesSet.data;
  return (
    <section className="workspace-view">
      <Breadcrumbs>
        <Link to="/projects">Proyectos</Link>
        <span aria-hidden="true">/</span>
        <Link to={`/projects/${projectId}/time-series-sets`}>
          Catalogo de series
        </Link>
        <span aria-hidden="true">/</span>
        <span>{set.name}</span>
      </Breadcrumbs>
      <header className="workspace-heading">
        <h1>
          {set.name} ({set.version_label})
        </h1>
        <p>
          {set.data_kind} | {set.status} | {set.timezone}
        </p>
      </header>
      <div className="workspace-stack">
        <section className="workspace-section" aria-labelledby="set-revision">
          <h2 id="set-revision">Revision</h2>
          <p>Revision {set.revision_number}</p>
          <p>
            <code>{set.content_hash}</code>
          </p>
        </section>
        <TimeSeriesSetOriginSummary revisionMetadata={set.revision_metadata} />
        <section className="workspace-section" aria-labelledby="set-horizon">
          <h2 id="set-horizon">Horizonte</h2>
          <p>{set.horizon.period_count} periodos</p>
          <p>
            {set.horizon.start || "Sin datos"} -{" "}
            {set.horizon.end || "Sin datos"}
          </p>
        </section>
        <section className="workspace-section" aria-labelledby="set-signals">
          <h2 id="set-signals">Senales</h2>
          <TimeSeriesSetSignalList signals={set.signals} />
        </section>
        <section className="workspace-section" aria-labelledby="set-source">
          <h2 id="set-source">Origen</h2>
          <TimeSeriesSetSourceSummary source={set.source} />
        </section>
        <TimeSeriesSetValuesEditor projectId={projectId} timeSeriesSet={set} />
        <TimeSeriesSetReplacePanel projectId={projectId} timeSeriesSet={set} />
        <section
          className="workspace-section"
          aria-labelledby="set-revision-history"
        >
          <h2 id="set-revision-history">Historial de revisiones</h2>
          {timeSeriesSetRevisions.isPending ? (
            <p>Cargando historial de revisiones.</p>
          ) : timeSeriesSetRevisions.isError ? (
            <RequestErrorView
              error={timeSeriesSetRevisions.error}
              retry={() => void timeSeriesSetRevisions.refetch()}
            />
          ) : (
            <TimeSeriesSetRevisionHistory
              revisions={timeSeriesSetRevisions.data}
            />
          )}
        </section>
      </div>
    </section>
  );
}

function HydraulicTimeSeriesSetSignalList({
  set,
}: {
  set: HydraulicTimeSeriesSet;
}) {
  return (
    <ul className="resource-list">
      {set.signals.map((signal) => (
        <li key={signal.signal_key}>
          <strong>{signal.signal_key}</strong>
          <p>
            {signal.unit} | {signal.entity_type}
            {signal.entity_key ? `:${signal.entity_key}` : ""}
          </p>
        </li>
      ))}
    </ul>
  );
}

export function HydraulicTimeSeriesSetDetailView() {
  const projectId = useNumericParam("projectId");
  const hydraulicTimeSeriesSetId = useNumericParam("hydraulicTimeSeriesSetId");
  const hydraulicTimeSeriesSet = useQuery({
    queryKey: hydraulicTimeSeriesSetQueryKey(
      projectId || 0,
      hydraulicTimeSeriesSetId || 0,
    ),
    queryFn: ({ signal }) =>
      getProjectHydraulicTimeSeriesSet(
        projectId || 0,
        hydraulicTimeSeriesSetId || 0,
        signal,
      ),
    enabled: projectId !== null && hydraulicTimeSeriesSetId !== null,
    retry: false,
  });

  if (projectId === null || hydraulicTimeSeriesSetId === null) {
    return <NotFoundView>El set de series solicitado no existe.</NotFoundView>;
  }
  if (hydraulicTimeSeriesSet.isPending) {
    return <LoadingView label="Cargando set de series hidraulico" />;
  }
  if (hydraulicTimeSeriesSet.isError) {
    return (
      <RequestErrorView
        error={hydraulicTimeSeriesSet.error}
        retry={() => void hydraulicTimeSeriesSet.refetch()}
      />
    );
  }

  const set = hydraulicTimeSeriesSet.data;
  return (
    <section className="workspace-view">
      <Breadcrumbs>
        <Link to="/projects">Proyectos</Link>
        <span aria-hidden="true">/</span>
        <Link to={`/projects/${projectId}/time-series-sets`}>
          Catalogo de series
        </Link>
        <span aria-hidden="true">/</span>
        <span>{set.name}</span>
      </Breadcrumbs>
      <header className="workspace-heading">
        <h1>{set.name}</h1>
        <p>
          Origen hidraulico (legacy) | {set.status} | version{" "}
          {set.version_number} ({set.version_label})
        </p>
      </header>
      <div className="workspace-stack">
        <section
          className="workspace-section"
          aria-labelledby="hydraulic-set-origin"
        >
          <h2 id="hydraulic-set-origin">Origen</h2>
          <p>
            {set.hydraulic_system_name} / {set.entity_display_name} (
            {set.entity_type})
          </p>
        </section>
        <section
          className="workspace-section"
          aria-labelledby="hydraulic-set-horizon"
        >
          <h2 id="hydraulic-set-horizon">Horizonte</h2>
          <p>{set.horizon.period_count} periodos</p>
          <p>
            {set.horizon.start || "Sin datos"} -{" "}
            {set.horizon.end || "Sin datos"}
          </p>
        </section>
        <section
          className="workspace-section"
          aria-labelledby="hydraulic-set-signals"
        >
          <h2 id="hydraulic-set-signals">Senales</h2>
          <HydraulicTimeSeriesSetSignalList set={set} />
        </section>
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
  const versionsById = new Map(versions.map((version) => [version.id, version]));
  return (
    <ul className="resource-list">
      {runs.map((run) => {
        const version = versionsById.get(run.scenario_version_id);
        const variantDisplayName =
          version?.generation_metadata?.kind === "case_input_variant"
            ? version.generation_metadata.input_variant?.display_name
            : undefined;
        return (
          <li key={run.id}>
            <Link to={`/runs/${run.id}`}>Run {run.id}</Link>
            <p>
              Estado: {run.status} | Version{" "}
              {version?.version_number || "desconocida"}
              {variantDisplayName ? ` | Variante: ${variantDisplayName}` : ""} |
              creado {run.created_at}
            </p>
          </li>
        );
      })}
    </ul>
  );
}

export function RunComparisonView() {
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

  const succeededRuns = useMemo(
    () => (runs.data || []).filter((run) => run.status === "succeeded"),
    [runs.data],
  );
  const versionsById = useMemo(
    () => new Map((versions.data || []).map((version) => [version.id, version])),
    [versions.data],
  );

  const [baselineRunId, setBaselineRunId] = useState<number | null>(null);
  const [candidateRunId, setCandidateRunId] = useState<number | null>(null);
  const [series, setSeries] = useState<string | undefined>(undefined);

  const effectiveBaselineId = baselineRunId ?? succeededRuns[0]?.id ?? null;
  const effectiveCandidateId =
    candidateRunId ??
    succeededRuns.find((run) => run.id !== effectiveBaselineId)?.id ??
    null;
  const canCompare =
    effectiveBaselineId !== null &&
    effectiveCandidateId !== null &&
    effectiveBaselineId !== effectiveCandidateId;

  const comparison = useQuery({
    queryKey: runComparisonQueryKey(
      effectiveBaselineId ?? 0,
      effectiveCandidateId ?? 0,
      series,
    ),
    queryFn: ({ signal }) =>
      compareRuns(
        {
          baselineRunId: effectiveBaselineId as number,
          candidateRunId: effectiveCandidateId as number,
          series,
        },
        signal,
      ),
    enabled: canCompare,
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
  if (runs.isError) {
    return (
      <RequestErrorView error={runs.error} retry={() => void runs.refetch()} />
    );
  }

  function runOptionLabel(run: ScenarioRun): string {
    const version = versionsById.get(run.scenario_version_id);
    const variantDisplayName =
      version?.generation_metadata?.kind === "case_input_variant"
        ? version.generation_metadata.input_variant?.display_name
        : undefined;
    return `Run ${run.id}${variantDisplayName ? ` - ${variantDisplayName}` : ""} (${run.created_at})`;
  }

  return (
    <section className="workspace-view">
      <Breadcrumbs>
        <Link to="/projects">Proyectos</Link>
        <span aria-hidden="true">/</span>
        <Link to={`/scenarios/${scenario.data.id}`}>{scenario.data.name}</Link>
        <span aria-hidden="true">/</span>
        <span>Comparar corridas</span>
      </Breadcrumbs>
      <header className="workspace-heading">
        <h1>Comparar corridas</h1>
        <p>Compara dos corridas exitosas de este mismo caso.</p>
      </header>
      {succeededRuns.length < 2 ? (
        <EmptyState>
          Se necesitan al menos dos corridas exitosas de este escenario para
          comparar.
        </EmptyState>
      ) : (
        <div className="workspace-stack">
          <section
            className="workspace-section"
            aria-labelledby="run-comparison-picker"
          >
            <h2 id="run-comparison-picker">Seleccionar corridas</h2>
            <div className="inline-actions">
              <label>
                Corrida base{" "}
                <select
                  value={effectiveBaselineId === null ? "" : String(effectiveBaselineId)}
                  onChange={(event) => setBaselineRunId(Number(event.target.value))}
                >
                  {succeededRuns.map((run) => (
                    <option key={run.id} value={run.id}>
                      {runOptionLabel(run)}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Corrida candidata{" "}
                <select
                  value={
                    effectiveCandidateId === null ? "" : String(effectiveCandidateId)
                  }
                  onChange={(event) => setCandidateRunId(Number(event.target.value))}
                >
                  {succeededRuns.map((run) => (
                    <option key={run.id} value={run.id}>
                      {runOptionLabel(run)}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            {effectiveBaselineId !== null &&
            effectiveCandidateId !== null &&
            effectiveBaselineId === effectiveCandidateId ? (
              <p className="result-alert" role="alert">
                Selecciona dos corridas distintas.
              </p>
            ) : null}
          </section>
          {comparison.isPending && canCompare ? (
            <LoadingView label="Cargando comparacion" />
          ) : null}
          {comparison.isError ? (
            <div className="result-alert" role="alert">
              <strong>No se pudo comparar</strong>
              <p>{errorMessage(comparison.error)}</p>
            </div>
          ) : null}
          {comparison.data ? (
            <RunComparisonResult
              comparison={comparison.data}
              series={series}
              onSelectSeries={setSeries}
            />
          ) : null}
        </div>
      )}
    </section>
  );
}

function RunComparisonSideSummary({
  title,
  side,
}: {
  title: string;
  side: RunComparison["baseline"];
}) {
  return (
    <div>
      <h3>{title}</h3>
      <dl className="source-metadata version-metadata">
        <div>
          <dt>Run</dt>
          <dd>
            <Link to={`/runs/${side.run_id}`}>Run {side.run_id}</Link>
          </dd>
        </div>
        <div>
          <dt>Variante</dt>
          <dd>
            {side.input_variant?.display_name ||
              (side.input_variant ? `ID ${side.input_variant.id}` : "Sin variante")}
          </dd>
        </div>
        <div>
          <dt>Rango de fechas</dt>
          <dd>
            {side.date_range
              ? `${side.date_range.start} - ${side.date_range.end}`
              : "Sin rango"}
          </dd>
        </div>
        <div>
          <dt>Finalizado</dt>
          <dd>{displayValue(side.finished_at)}</dd>
        </div>
      </dl>
    </div>
  );
}

function RunComparisonResult({
  comparison,
  series,
  onSelectSeries,
}: {
  comparison: RunComparison;
  series: string | undefined;
  onSelectSeries: (series: string) => void;
}) {
  return (
    <>
      <section
        className="workspace-section"
        aria-labelledby="run-comparison-context"
      >
        <h2 id="run-comparison-context">Contexto de las corridas</h2>
        <div className="inline-actions">
          <RunComparisonSideSummary title="Base" side={comparison.baseline} />
          <RunComparisonSideSummary
            title="Candidata"
            side={comparison.candidate}
          />
        </div>
      </section>
      <section
        className="workspace-section"
        aria-labelledby="run-comparison-kpis"
      >
        <h2 id="run-comparison-kpis">Diferencias en KPIs</h2>
        {comparison.kpis.length === 0 ? (
          <EmptyState>No hay KPIs escalares para comparar.</EmptyState>
        ) : (
          <div className="time-series-table-scroll result-table-scroll" tabIndex={0}>
            <table>
              <thead>
                <tr>
                  <th>KPI</th>
                  <th>Base</th>
                  <th>Candidata</th>
                  <th>Diferencia</th>
                </tr>
              </thead>
              <tbody>
                {comparison.kpis.map((kpi) => (
                  <tr key={kpi.key}>
                    <td>{kpi.key}</td>
                    <td>{displayValue(kpi.baseline, "-")}</td>
                    <td>{displayValue(kpi.candidate, "-")}</td>
                    <td>{kpi.delta === null ? "-" : kpi.delta}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
      <section
        className="workspace-section"
        aria-labelledby="run-comparison-series"
      >
        <h2 id="run-comparison-series">Diferencias por periodo</h2>
        {comparison.available_signal_keys.length === 0 ? (
          <EmptyState>Ninguna serie de resultado en comun para comparar.</EmptyState>
        ) : (
          <>
            <label>
              Serie{" "}
              <select
                value={series || comparison.selected_series || ""}
                onChange={(event) => onSelectSeries(event.target.value)}
              >
                {comparison.available_signal_keys.map((key) => (
                  <option key={key} value={key}>
                    {key}
                  </option>
                ))}
              </select>
            </label>
            {comparison.series_periods && comparison.series_periods.length > 0 ? (
              <div className="time-series-table-scroll result-table-scroll" tabIndex={0}>
                <table>
                  <thead>
                    <tr>
                      <th>Periodo</th>
                      <th>Base</th>
                      <th>Candidata</th>
                      <th>Diferencia</th>
                    </tr>
                  </thead>
                  <tbody>
                    {comparison.series_periods.map((period) => (
                      <tr key={period.timestamp}>
                        <td>{period.timestamp}</td>
                        <td>{displayValue(period.baseline, "-")}</td>
                        <td>{displayValue(period.candidate, "-")}</td>
                        <td>{period.delta === null ? "-" : period.delta}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <EmptyState>Sin datos de periodo para esta serie.</EmptyState>
            )}
          </>
        )}
      </section>
    </>
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

// Colorblind-safe (Okabe-Ito based) tints so each reach type reads apart on
// the light canvas; plant links keep the dashed teal used since they exist.
const hydraulicReachTypeColors: Record<HydraulicReachType, string> = {
  river: "#0072b2",
  canal: "#56b4e9",
  tunnel: "#cc79a7",
  gate: "#e69f00",
  spillway: "#d55e00",
  bypass: "#009e73",
  tailrace: "#8c7a00",
  other: "#6b7280",
};

const hydraulicReachTypeLabels: Record<HydraulicReachType, string> = {
  river: "Rio",
  canal: "Canal",
  tunnel: "Tunel",
  gate: "Compuerta",
  spillway: "Vertedero",
  bypass: "Bypass",
  tailrace: "Restitucion",
  other: "Otro",
};

const hydraulicPlantLinkColor = "#0f766e";

const hydraulicCanvasNodeWidth = 150;
const hydraulicCanvasNodeHeight = 76;
const hydraulicCanvasMinWidth = 940;
const hydraulicCanvasMinHeight = 480;

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
                time_series_set_id:
                  node.natural_inflow_series.time_series_set_id,
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
        link_anchors: node.link_anchors ?? null,
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
    from_anchor: reach.from_anchor ?? null,
    to_anchor: reach.to_anchor ?? null,
    flow_min_m3s: reach.flow_min_m3s ?? null,
    spill_penalty_usd_per_hm3: reach.spill_penalty_usd_per_hm3 ?? null,
    minimum_flow_series: reach.minimum_flow_series
      ? {
          time_series_set_id: reach.minimum_flow_series.time_series_set_id,
          version_label: reach.minimum_flow_series.version_label,
          points: reach.minimum_flow_series.points.map((point) => ({
            timestamp: point.timestamp,
            duration_hours: point.duration_hours,
            value_m3s: point.value_m3s,
          })),
        }
      : null,
  }));
}

function minimumFlowSeriesByReachKey(
  diagram: HydraulicDiagram,
): Record<string, HydraulicNaturalInflowSeriesSummary[]> {
  const map: Record<string, HydraulicNaturalInflowSeriesSummary[]> = {};
  for (const reach of diagram.reaches || []) {
    map[reach.technical_key] = reach.available_minimum_flow_series ?? [];
  }
  return map;
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

const hydraulicPlantLinkPrefix = "plant-link:";

function hydraulicPlantLinkKey(fromKey: string, toKey: string): string {
  return `${hydraulicPlantLinkPrefix}${fromKey}->${toKey}`;
}

function parseHydraulicPlantLinkKey(
  key: string | null,
): { fromKey: string; toKey: string } | null {
  if (!key || !key.startsWith(hydraulicPlantLinkPrefix)) return null;
  const [fromKey, toKey] = key
    .slice(hydraulicPlantLinkPrefix.length)
    .split("->");
  if (!fromKey || !toKey) return null;
  return { fromKey, toKey };
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

function HydraulicDiagramCanvas({
  nodes,
  reaches,
  viewport,
  updateNode,
  connectPorts,
  focusEntity,
  focusedEntityKey,
}: {
  nodes: HydraulicDiagramNodeWrite[];
  reaches: HydraulicDiagramReachWrite[];
  viewport: HydraulicDiagramViewport;
  updateNode: (
    technicalKey: string,
    patch: Partial<HydraulicDiagramNodeWrite>,
  ) => void;
  connectPorts: (
    fromNodeKey: string,
    toNodeKey: string,
    fromAnchor: number,
    toAnchor: number,
  ) => void;
  focusEntity: (technicalKey: string | null) => void;
  focusedEntityKey: string | null;
}) {
  const surfaceRef = useRef<HTMLDivElement>(null);
  const [draggingNode, setDraggingNode] = useState<{
    technicalKey: string;
    offsetX: number;
    offsetY: number;
  } | null>(null);
  const [pendingConnector, setPendingConnector] = useState<{
    nodeKey: string;
    anchor: number;
  } | null>(null);
  const nodeByKey = new Map(nodes.map((node) => [node.technical_key, node]));
  const canvasWidth = Math.max(
    hydraulicCanvasMinWidth,
    ...nodes.map((node) => node.x + hydraulicCanvasNodeWidth + 120),
  );
  const canvasHeight = Math.max(
    hydraulicCanvasMinHeight,
    ...nodes.map((node) => node.y + hydraulicCanvasNodeHeight + 120),
  );
  const zoom =
    Number.isFinite(viewport.zoom) && viewport.zoom > 0 ? viewport.zoom : 1;

  function pointFromEvent(event: { clientX: number; clientY: number }) {
    const surface = surfaceRef.current;
    if (!surface) return { x: 0, y: 0 };
    const rect = surface.getBoundingClientRect();
    return {
      x: (event.clientX - rect.left + surface.scrollLeft) / zoom,
      y: (event.clientY - rect.top + surface.scrollTop) / zoom,
    };
  }

  function anchorFromEvent(
    event: { clientX: number; clientY: number },
    node: HydraulicDiagramNodeWrite,
  ) {
    // Synthetic events without coordinates fall back to the border center.
    if (!event.clientX && !event.clientY) return 0.5;
    const raw = (pointFromEvent(event).x - node.x) / hydraulicCanvasNodeWidth;
    return Math.min(0.95, Math.max(0.05, Math.round(raw * 1000) / 1000));
  }

  function startNodeDrag(
    event: PointerEvent<HTMLDivElement>,
    node: HydraulicDiagramNodeWrite,
  ) {
    if (event.button !== 0) return;
    if (
      event.target instanceof HTMLElement &&
      event.target.closest("[data-hydraulic-connector]")
    ) {
      return;
    }
    const point = pointFromEvent(event);
    setDraggingNode({
      technicalKey: node.technical_key,
      offsetX: point.x - node.x,
      offsetY: point.y - node.y,
    });
    focusEntity(node.technical_key);
    event.currentTarget.setPointerCapture?.(event.pointerId);
  }

  function moveNode(event: PointerEvent<HTMLDivElement>) {
    if (!draggingNode) return;
    const point = pointFromEvent(event);
    updateNode(draggingNode.technicalKey, {
      x: Math.max(16, Math.round(point.x - draggingNode.offsetX)),
      y: Math.max(16, Math.round(point.y - draggingNode.offsetY)),
    });
  }

  function endNodeDrag(event: PointerEvent<HTMLDivElement>) {
    if (!draggingNode) return;
    event.currentTarget.releasePointerCapture?.(event.pointerId);
    setDraggingNode(null);
  }

  function moveNodeWithKeyboard(
    event: KeyboardEvent<HTMLDivElement>,
    node: HydraulicDiagramNodeWrite,
  ) {
    const step = event.shiftKey ? 40 : 12;
    const deltas: Record<string, [number, number]> = {
      ArrowDown: [0, step],
      ArrowLeft: [-step, 0],
      ArrowRight: [step, 0],
      ArrowUp: [0, -step],
    };
    const delta = deltas[event.key];
    if (!delta) return;
    event.preventDefault();
    focusEntity(node.technical_key);
    updateNode(node.technical_key, {
      x: Math.max(16, Math.round(node.x + delta[0])),
      y: Math.max(16, Math.round(node.y + delta[1])),
    });
  }

  function beginConnection(nodeKey: string, anchor: number) {
    setPendingConnector({ nodeKey, anchor });
    focusEntity(nodeKey);
  }

  function finishConnection(
    toNodeKey: string,
    toAnchor: number,
    fromNodeKey?: string,
  ) {
    const source = fromNodeKey || pendingConnector?.nodeKey;
    const fromAnchor =
      pendingConnector && pendingConnector.nodeKey === source
        ? pendingConnector.anchor
        : 0.5;
    setPendingConnector(null);
    if (!source || source === toNodeKey) return;
    connectPorts(source, toNodeKey, fromAnchor, toAnchor);
  }

  function edgePath(
    fromNode: HydraulicDiagramNodeWrite,
    toNode: HydraulicDiagramNodeWrite,
    fromAnchor = 0.5,
    toAnchor = 0.5,
  ) {
    // Connections leave the source's bottom border and arrive at the target's
    // top border, each at the fraction where the user anchored them.
    const start = {
      x: fromNode.x + hydraulicCanvasNodeWidth * fromAnchor,
      y: fromNode.y + hydraulicCanvasNodeHeight,
    };
    const end = {
      x: toNode.x + hydraulicCanvasNodeWidth * toAnchor,
      y: toNode.y,
    };
    const dy = end.y - start.y;
    const curve =
      (dy === 0 ? 1 : Math.sign(dy)) * Math.max(40, Math.abs(dy) * 0.4);
    return `M ${start.x} ${start.y} C ${start.x} ${start.y + curve}, ${
      end.x
    } ${end.y - curve}, ${end.x} ${end.y}`;
  }

  const plantEdges: {
    fromKey: string;
    toKey: string;
    plantKey: string;
    fromAnchor: number;
    toAnchor: number;
  }[] = [];
  for (const node of nodes) {
    if (node.component_type !== "plant") continue;
    const intakes = new Set<string>();
    const discharges = new Set<string>();
    for (const unit of node.units ?? []) {
      if (unit.intake_node_key) intakes.add(unit.intake_node_key);
      if (unit.discharge_node_key) discharges.add(unit.discharge_node_key);
    }
    for (const key of intakes) {
      const anchors = node.link_anchors?.[`in:${key}`];
      plantEdges.push({
        fromKey: key,
        toKey: node.technical_key,
        plantKey: node.technical_key,
        fromAnchor: anchors?.from ?? 0.5,
        toAnchor: anchors?.to ?? 0.5,
      });
    }
    for (const key of discharges) {
      const anchors = node.link_anchors?.[`out:${key}`];
      plantEdges.push({
        fromKey: node.technical_key,
        toKey: key,
        plantKey: node.technical_key,
        fromAnchor: anchors?.from ?? 0.5,
        toAnchor: anchors?.to ?? 0.5,
      });
    }
  }

  return (
    <>
      <div
        className="hydraulic-canvas"
        ref={surfaceRef}
        role="group"
        aria-label="Editor visual de diagrama hidraulico"
      >
        <div
          className="hydraulic-canvas-surface"
          style={{
            width: canvasWidth * zoom,
            height: canvasHeight * zoom,
          }}
        >
          <div
            className="hydraulic-canvas-content"
            style={{
              width: canvasWidth,
              height: canvasHeight,
              transform: `scale(${zoom})`,
            }}
          >
            <svg
              className="hydraulic-canvas-links"
              width={canvasWidth}
              height={canvasHeight}
              aria-hidden="true"
            >
              <defs>
                <marker
                  id="hydraulic-arrowhead"
                  markerUnits="userSpaceOnUse"
                  markerWidth="10"
                  markerHeight="10"
                  refX="8.5"
                  refY="5"
                  orient="auto"
                >
                  <path d="M 0 0 L 10 5 L 0 10 z" />
                </marker>
              </defs>
              {reaches.map((reach) => {
                const fromNode = nodeByKey.get(reach.from_node_key);
                const toNode = nodeByKey.get(reach.to_node_key);
                if (!fromNode || !toNode) return null;
                return (
                  <path
                    key={reach.technical_key}
                    className="hydraulic-canvas-link"
                    data-testid={`hydraulic-link-${reach.technical_key}`}
                    data-reach-type={reach.reach_type}
                    data-focused={
                      focusedEntityKey === reach.technical_key
                        ? "true"
                        : undefined
                    }
                    // Presentation attribute: the CSS focused rule wins over it.
                    stroke={hydraulicReachTypeColors[reach.reach_type]}
                    style={{ cursor: "pointer", pointerEvents: "stroke" }}
                    onClick={() => focusEntity(reach.technical_key)}
                    d={edgePath(
                      fromNode,
                      toNode,
                      reach.from_anchor ?? 0.5,
                      reach.to_anchor ?? 0.5,
                    )}
                    markerEnd="url(#hydraulic-arrowhead)"
                  />
                );
              })}
              {plantEdges.map((edge) => {
                const fromNode = nodeByKey.get(edge.fromKey);
                const toNode = nodeByKey.get(edge.toKey);
                if (!fromNode || !toNode) return null;
                const linkKey = hydraulicPlantLinkKey(edge.fromKey, edge.toKey);
                return (
                  <path
                    key={`plant-${edge.fromKey}-${edge.toKey}`}
                    className="hydraulic-canvas-link hydraulic-canvas-link-plant"
                    data-testid={`hydraulic-plant-link-${edge.fromKey}-${edge.toKey}`}
                    data-focused={
                      focusedEntityKey === linkKey ? "true" : undefined
                    }
                    style={{ cursor: "pointer", pointerEvents: "stroke" }}
                    onClick={() => focusEntity(linkKey)}
                    d={edgePath(
                      fromNode,
                      toNode,
                      edge.fromAnchor,
                      edge.toAnchor,
                    )}
                    markerEnd="url(#hydraulic-arrowhead)"
                  />
                );
              })}
            </svg>
            {nodes.map((node) => {
              return (
                <div
                  key={node.technical_key}
                  className={`hydraulic-canvas-node hydraulic-canvas-node-${node.component_type}`}
                  data-testid={`hydraulic-canvas-node-${node.technical_key}`}
                  data-focused={
                    focusedEntityKey === node.technical_key ? "true" : undefined
                  }
                  data-connecting={
                    pendingConnector?.nodeKey === node.technical_key
                      ? "true"
                      : undefined
                  }
                  role="group"
                  tabIndex={0}
                  aria-label={`${hydraulicComponentLabels[node.component_type]} ${node.technical_key}`}
                  style={{
                    left: node.x,
                    top: node.y,
                    width: hydraulicCanvasNodeWidth,
                    height: hydraulicCanvasNodeHeight,
                  }}
                  onPointerDown={(event) => startNodeDrag(event, node)}
                  onPointerMove={moveNode}
                  onPointerUp={endNodeDrag}
                  onPointerCancel={endNodeDrag}
                  onKeyDown={(event) => moveNodeWithKeyboard(event, node)}
                >
                  <button
                    type="button"
                    className="hydraulic-canvas-port hydraulic-canvas-port-in"
                    data-hydraulic-connector="true"
                    data-testid={`hydraulic-node-in-${node.technical_key}`}
                    aria-label={`Entrada ${node.technical_key}`}
                    title={`Entrada ${node.technical_key}`}
                    onClick={(event) => {
                      event.stopPropagation();
                      finishConnection(
                        node.technical_key,
                        anchorFromEvent(event, node),
                      );
                    }}
                    onDragOver={(event: DragEvent<HTMLButtonElement>) => {
                      event.preventDefault();
                      if (event.dataTransfer) {
                        event.dataTransfer.dropEffect = "link";
                      }
                    }}
                    onDrop={(event: DragEvent<HTMLButtonElement>) => {
                      event.preventDefault();
                      event.stopPropagation();
                      finishConnection(
                        node.technical_key,
                        anchorFromEvent(event, node),
                        event.dataTransfer.getData("text/plain") || undefined,
                      );
                    }}
                  />
                  <span className="hydraulic-canvas-node-type">
                    {hydraulicComponentLabels[node.component_type]}
                  </span>
                  <strong>{node.display_name}</strong>
                  <span className="hydraulic-canvas-node-key">
                    {node.technical_key}
                  </span>
                  <button
                    type="button"
                    className="hydraulic-canvas-port hydraulic-canvas-port-out"
                    data-hydraulic-connector="true"
                    data-testid={`hydraulic-node-out-${node.technical_key}`}
                    draggable
                    aria-label={`Salida ${node.technical_key}`}
                    title={`Salida ${node.technical_key}`}
                    onClick={(event) => {
                      event.stopPropagation();
                      beginConnection(
                        node.technical_key,
                        anchorFromEvent(event, node),
                      );
                    }}
                    onDragStart={(event: DragEvent<HTMLButtonElement>) => {
                      event.stopPropagation();
                      event.dataTransfer.setData(
                        "text/plain",
                        node.technical_key,
                      );
                      event.dataTransfer.effectAllowed = "link";
                      setPendingConnector({
                        nodeKey: node.technical_key,
                        anchor: anchorFromEvent(event, node),
                      });
                    }}
                    onDragEnd={() => setPendingConnector(null)}
                  />
                </div>
              );
            })}
            {!nodes.length ? (
              <div className="hydraulic-canvas-empty">
                <EmptyState>
                  Agrega componentes para construir la topologia hidraulica.
                </EmptyState>
              </div>
            ) : null}
          </div>
        </div>
      </div>
      <ul
        className="hydraulic-reach-legend"
        data-testid="hydraulic-reach-legend"
        aria-label="Leyenda de tipos de tramo"
      >
        {hydraulicReachTypes.map((reachType) => (
          <li key={reachType}>
            <span
              className="hydraulic-reach-legend-swatch"
              style={{ background: hydraulicReachTypeColors[reachType] }}
              aria-hidden="true"
            />
            {hydraulicReachTypeLabels[reachType]}
          </li>
        ))}
        <li>
          <span
            className="hydraulic-reach-legend-swatch hydraulic-reach-legend-swatch-plant"
            style={{ background: hydraulicPlantLinkColor }}
            aria-hidden="true"
          />
          Central
        </li>
      </ul>
    </>
  );
}

function HydraulicReachList({
  nodes,
  reaches,
  updateReach,
  minimumFlowSeriesByReach,
  focusedEntityKey,
}: {
  nodes: HydraulicDiagramNodeWrite[];
  reaches: HydraulicDiagramReachWrite[];
  updateReach: (
    technicalKey: string,
    patch: Partial<HydraulicDiagramReachWrite>,
  ) => void;
  minimumFlowSeriesByReach: Record<
    string,
    HydraulicNaturalInflowSeriesSummary[]
  >;
  focusedEntityKey: string | null;
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
        <li
          key={reach.technical_key}
          data-testid={`hydraulic-reach-${reach.technical_key}`}
          data-focused={
            focusedEntityKey === reach.technical_key ? "true" : undefined
          }
          aria-current={
            focusedEntityKey === reach.technical_key ? "true" : undefined
          }
        >
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
            <label
              className="field-row"
              htmlFor={`hydraulic-reach-flow-min-${reach.technical_key}`}
            >
              <span>Caudal minimo m3/s {reach.technical_key}</span>
              <input
                id={`hydraulic-reach-flow-min-${reach.technical_key}`}
                type="number"
                value={reach.flow_min_m3s ?? ""}
                onChange={(event) =>
                  updateReach(reach.technical_key, {
                    flow_min_m3s:
                      event.target.value === ""
                        ? null
                        : Number(event.target.value),
                  })
                }
              />
            </label>
            {reach.reach_type === "spillway" ? (
              <label
                className="field-row"
                htmlFor={`hydraulic-reach-spill-penalty-${reach.technical_key}`}
              >
                <span>Penalidad vertedero USD/hm3 {reach.technical_key}</span>
                <input
                  id={`hydraulic-reach-spill-penalty-${reach.technical_key}`}
                  type="number"
                  value={reach.spill_penalty_usd_per_hm3 ?? ""}
                  onChange={(event) =>
                    updateReach(reach.technical_key, {
                      spill_penalty_usd_per_hm3:
                        event.target.value === ""
                          ? null
                          : Number(event.target.value),
                    })
                  }
                />
              </label>
            ) : null}
          </div>
          <HydraulicReachMinimumFlowSeries
            reach={reach}
            availableSeries={
              minimumFlowSeriesByReach[reach.technical_key] ?? []
            }
            updateReach={updateReach}
          />
        </li>
      ))}
    </ul>
  );
}

function HydraulicReachMinimumFlowSeries({
  reach,
  availableSeries,
  updateReach,
}: {
  reach: HydraulicDiagramReachWrite;
  availableSeries: HydraulicNaturalInflowSeriesSummary[];
  updateReach: (
    technicalKey: string,
    patch: Partial<HydraulicDiagramReachWrite>,
  ) => void;
}) {
  const key = reach.technical_key;
  const series = reach.minimum_flow_series ?? emptyInflowSeries();
  const points = series.points;

  function setPoints(nextPoints: HydraulicNaturalInflowSeriesPoint[]) {
    updateReach(key, {
      minimum_flow_series: {
        time_series_set_id: null,
        version_label: series.version_label ?? null,
        points: nextPoints,
      },
    });
  }

  return (
    <div
      className="hydraulic-reach-minimum-flow"
      data-testid={`reach-minimum-flow-${key}`}
    >
      <div className="draft-section-heading">
        <h4>Caudal minimo por serie {key}</h4>
        <div className="draft-actions">
          {availableSeries.length ? (
            <label htmlFor={`reach-min-flow-version-${key}`}>
              <span>Version de serie {key}</span>
              <select
                id={`reach-min-flow-version-${key}`}
                value={series.time_series_set_id ?? ""}
                onChange={(event) => {
                  const selectedId = Number(event.target.value);
                  const selected = availableSeries.find(
                    (option) => option.time_series_set_id === selectedId,
                  );
                  if (!selected) return;
                  updateReach(key, {
                    minimum_flow_series: {
                      time_series_set_id: selected.time_series_set_id,
                      version_label: selected.version_label,
                      points: selected.points.map((point) => ({ ...point })),
                    },
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
            data-testid={`reach-min-flow-add-point-${key}`}
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
            Agregar punto de caudal minimo {key}
          </button>
          {points.length ? (
            <button
              type="button"
              className="secondary-action"
              onClick={() => updateReach(key, { minimum_flow_series: null })}
            >
              Quitar serie de caudal minimo {key}
            </button>
          ) : null}
        </div>
      </div>
      {points.length ? (
        <ul className="resource-list hydraulic-reach-minimum-flow-points">
          {points.map((point, index) => (
            <li key={index}>
              <label htmlFor={`reach-min-flow-timestamp-${key}-${index}`}>
                <span>
                  Marca temporal {index + 1} {key}
                </span>
                <input
                  id={`reach-min-flow-timestamp-${key}-${index}`}
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
              <label htmlFor={`reach-min-flow-duration-${key}-${index}`}>
                <span>
                  Duracion horas {index + 1} {key}
                </span>
                <input
                  id={`reach-min-flow-duration-${key}-${index}`}
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
              <label htmlFor={`reach-min-flow-value-${key}-${index}`}>
                <span>
                  Caudal minimo m3/s {index + 1} {key}
                </span>
                <input
                  id={`reach-min-flow-value-${key}-${index}`}
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
                    points.filter((_, currentIndex) => currentIndex !== index),
                  )
                }
              >
                Quitar punto {index + 1} {key}
              </button>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
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

export function HydraulicInflowPanel({
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
  const [importError, setImportError] = useState<string | null>(null);

  function setPoints(nextPoints: HydraulicNaturalInflowSeriesPoint[]) {
    updateInflowSeries(key, {
      time_series_set_id: null,
      version_label: series.version_label ?? null,
      points: nextPoints,
    });
  }

  async function importFile(file: File) {
    try {
      const imported = /\.(xlsx|xls)$/i.test(file.name)
        ? parseInflowWorkbook(await file.arrayBuffer())
        : parseInflowCsv(await file.text());
      setImportError(null);
      setPoints(imported);
    } catch (error) {
      setImportError(
        error instanceof InflowImportError
          ? error.message
          : "No se pudo importar el archivo.",
      );
    }
  }

  return (
    <li
      className="hydraulic-inflow-panel"
      data-testid={`hydraulic-inflow-${key}`}
    >
      <div className="draft-section-heading">
        <h3>Afluente natural {node.display_name}</h3>
        <div className="draft-actions">
          <label
            className="inflow-import-control"
            htmlFor={`inflow-import-${key}`}
          >
            <span>Importar afluentes {key}</span>
            <input
              id={`inflow-import-${key}`}
              data-testid={`inflow-import-${key}`}
              type="file"
              accept=".csv,.xlsx,.xls"
              onChange={(event) => {
                const file = event.target.files?.[0];
                event.target.value = "";
                if (file) void importFile(file);
              }}
            />
          </label>
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
        </div>
      </div>
      {importError ? (
        <p
          className="field-error"
          role="alert"
          data-testid={`inflow-import-error-${key}`}
        >
          {importError}
        </p>
      ) : null}
      {points.length ? (
        <ul className="resource-list hydraulic-inflow-points">
          <li className="hydraulic-inflow-row hydraulic-inflow-head">
            <span>Marca temporal</span>
            <span>Duracion (h)</span>
            <span>Caudal (m3/s)</span>
          </li>
          {points.map((point, index) => (
            <li key={index} className="hydraulic-inflow-row">
              <span>{point.timestamp}</span>
              <span>{point.duration_hours}</span>
              <span>{point.value_m3s}</span>
            </li>
          ))}
        </ul>
      ) : (
        <EmptyState>
          Importa un archivo CSV o Excel con columnas timestamp, duration_hours
          y value_m3s para cargar los afluentes de este nodo.
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
    <li
      className="hydraulic-plant-panel"
      data-testid={`hydraulic-plant-${key}`}
    >
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

function HydraulicNodeLabelField({
  node,
  updateNode,
}: {
  node: HydraulicDiagramNodeWrite;
  updateNode: (
    technicalKey: string,
    patch: Partial<HydraulicDiagramNodeWrite>,
  ) => void;
}) {
  return (
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
          updateNode(node.technical_key, { display_name: event.target.value })
        }
      />
    </label>
  );
}

function HydraulicPropertiesPanel({
  nodes,
  reaches,
  focusedEntityKey,
  deleteEntity,
  updateNode,
  updateReservoir,
  updateCurve,
  updateInflowSeries,
  updatePlant,
  addUnit,
  updateUnit,
  removeUnit,
  updateUnitCurve,
  updateReach,
  availableCurves,
  unitCurves,
  availableInflowSeries,
  availableMinimumFlowSeries,
}: {
  nodes: HydraulicDiagramNodeWrite[];
  reaches: HydraulicDiagramReachWrite[];
  focusedEntityKey: string | null;
  deleteEntity: (technicalKey: string) => void;
  updateNode: (
    technicalKey: string,
    patch: Partial<HydraulicDiagramNodeWrite>,
  ) => void;
  updateReservoir: (
    technicalKey: string,
    patch: Partial<HydraulicReservoirParameters>,
  ) => void;
  updateCurve: (
    technicalKey: string,
    curve: HydraulicStorageElevationCurveWrite,
  ) => void;
  updateInflowSeries: (
    technicalKey: string,
    series: HydraulicNaturalInflowSeriesWrite,
  ) => void;
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
  updateReach: (
    technicalKey: string,
    patch: Partial<HydraulicDiagramReachWrite>,
  ) => void;
  availableCurves: Record<string, HydraulicCurveSummary[]>;
  unitCurves: Record<string, HydraulicCurveSummary[]>;
  availableInflowSeries: Record<string, HydraulicNaturalInflowSeriesSummary[]>;
  availableMinimumFlowSeries: Record<
    string,
    HydraulicNaturalInflowSeriesSummary[]
  >;
}) {
  const plantLink = parseHydraulicPlantLinkKey(focusedEntityKey);
  if (plantLink && focusedEntityKey) {
    return (
      <div
        className="hydraulic-properties-panel"
        data-testid={`hydraulic-properties-plant-link-${plantLink.fromKey}-${plantLink.toKey}`}
      >
        <div className="draft-section-heading">
          <p className="hydraulic-properties-heading">
            Conexion central | {plantLink.fromKey} -&gt; {plantLink.toKey}
          </p>
          <button
            type="button"
            className="secondary-action"
            onClick={() => deleteEntity(focusedEntityKey)}
          >
            Eliminar conexion
          </button>
        </div>
        <p className="hydraulic-properties-hint">
          Eliminar la conexion desvincula la toma o descarga de todas las
          unidades de la central; los componentes se conservan.
        </p>
      </div>
    );
  }

  const node = focusedEntityKey
    ? (nodes.find(
        (candidate) => candidate.technical_key === focusedEntityKey,
      ) ?? null)
    : null;
  const reach = focusedEntityKey
    ? (reaches.find(
        (candidate) => candidate.technical_key === focusedEntityKey,
      ) ?? null)
    : null;

  if (!node && !reach) {
    return (
      <EmptyState>
        Selecciona un objeto del diagrama para editar sus propiedades.
      </EmptyState>
    );
  }

  if (reach) {
    return (
      <div
        className="hydraulic-properties-panel"
        data-testid={`hydraulic-properties-${reach.technical_key}`}
      >
        <div className="draft-section-heading">
          <p className="hydraulic-properties-heading">
            Tramo | {reach.technical_key}
          </p>
          <button
            type="button"
            className="secondary-action"
            onClick={() => deleteEntity(reach.technical_key)}
          >
            Eliminar componente
          </button>
        </div>
        <HydraulicReachList
          nodes={nodes}
          reaches={[reach]}
          updateReach={updateReach}
          minimumFlowSeriesByReach={availableMinimumFlowSeries}
          focusedEntityKey={focusedEntityKey}
        />
      </div>
    );
  }

  const selected = node as HydraulicDiagramNodeWrite;
  return (
    <div
      className="hydraulic-properties-panel"
      data-testid={`hydraulic-properties-${selected.technical_key}`}
    >
      <div className="draft-section-heading">
        <p className="hydraulic-properties-heading">
          {hydraulicComponentLabels[selected.component_type]} |{" "}
          {selected.technical_key}
        </p>
        <button
          type="button"
          className="secondary-action"
          onClick={() => deleteEntity(selected.technical_key)}
        >
          Eliminar componente
        </button>
      </div>
      <div className="draft-field-grid">
        <HydraulicNodeLabelField node={selected} updateNode={updateNode} />
      </div>
      {selected.component_type === "reservoir" ? (
        <ul className="resource-list hydraulic-reservoir-list">
          <HydraulicReservoirPanel
            node={selected}
            availableCurves={availableCurves[selected.technical_key] ?? []}
            updateReservoir={updateReservoir}
            updateCurve={updateCurve}
          />
        </ul>
      ) : null}
      {selected.component_type !== "plant" ? (
        <ul className="resource-list hydraulic-inflow-list">
          <HydraulicInflowPanel
            node={selected}
            availableSeries={
              availableInflowSeries[selected.technical_key] ?? []
            }
            updateInflowSeries={updateInflowSeries}
          />
        </ul>
      ) : null}
      {selected.component_type === "plant" ? (
        <ul className="resource-list hydraulic-plant-list">
          <HydraulicPlantPanel
            node={selected}
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
        </ul>
      ) : null}
    </div>
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
  const [focusedEntityKey, setFocusedEntityKey] = useState<string | null>(null);
  const [availableCurves, setAvailableCurves] = useState<
    Record<string, HydraulicCurveSummary[]>
  >(() => curvesByNodeKey(initialDiagram));
  const [unitCurves, setUnitCurves] = useState<
    Record<string, HydraulicCurveSummary[]>
  >(() => unitCurvesByKey(initialDiagram));
  const [availableInflowSeries, setAvailableInflowSeries] = useState<
    Record<string, HydraulicNaturalInflowSeriesSummary[]>
  >(() => inflowSeriesByNodeKey(initialDiagram));
  const [availableMinimumFlowSeries, setAvailableMinimumFlowSeries] = useState<
    Record<string, HydraulicNaturalInflowSeriesSummary[]>
  >(() => minimumFlowSeriesByReachKey(initialDiagram));

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
      setAvailableMinimumFlowSeries(minimumFlowSeriesByReachKey(savedDiagram));
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
      setAvailableMinimumFlowSeries(minimumFlowSeriesByReachKey(serverDiagram));
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

  function createReach(
    fromNodeKey: string,
    toNodeKey: string,
    fromAnchor = 0.5,
    toAnchor = 0.5,
  ) {
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
          from_anchor: fromAnchor,
          to_anchor: toAnchor,
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

  function setPlantConnection(
    plantKey: string,
    nodeKey: string,
    side: "intake" | "discharge",
    fromAnchor = 0.5,
    toAnchor = 0.5,
  ) {
    const field = side === "intake" ? "intake_node_key" : "discharge_node_key";
    const anchorKey = side === "intake" ? `in:${nodeKey}` : `out:${nodeKey}`;
    setNodes((current) =>
      current.map((node) => {
        if (node.technical_key !== plantKey) return node;
        const existing = node.units ?? [];
        const units = existing.length
          ? existing
          : [defaultHydraulicUnit(nextHydraulicUnitKey(current))];
        return {
          ...node,
          units: units.map((unit) => ({ ...unit, [field]: nodeKey })),
          link_anchors: {
            ...(node.link_anchors ?? {}),
            [anchorKey]: { from: fromAnchor, to: toAnchor },
          },
        };
      }),
    );
    markDirty();
  }

  function connectPorts(
    fromNodeKey: string,
    toNodeKey: string,
    fromAnchor = 0.5,
    toAnchor = 0.5,
  ) {
    if (fromNodeKey === toNodeKey) return;
    const fromNode = nodes.find((node) => node.technical_key === fromNodeKey);
    const toNode = nodes.find((node) => node.technical_key === toNodeKey);
    if (!fromNode || !toNode) return;
    const fromPlant = fromNode.component_type === "plant";
    const toPlant = toNode.component_type === "plant";
    if (fromPlant && toPlant) return;
    if (toPlant) {
      setPlantConnection(
        toNodeKey,
        fromNodeKey,
        "intake",
        fromAnchor,
        toAnchor,
      );
      setFocusedEntityKey(toNodeKey);
      return;
    }
    if (fromPlant) {
      setPlantConnection(
        fromNodeKey,
        toNodeKey,
        "discharge",
        fromAnchor,
        toAnchor,
      );
      setFocusedEntityKey(fromNodeKey);
      return;
    }
    const nextKey = nextHydraulicReachKey(reaches, fromNodeKey, toNodeKey);
    createReach(fromNodeKey, toNodeKey, fromAnchor, toAnchor);
    setFocusedEntityKey(nextKey);
  }

  function deleteEntity(technicalKey: string) {
    const plantLink = parseHydraulicPlantLinkKey(technicalKey);
    if (plantLink) {
      setNodes((current) =>
        current.map((node) => {
          if (node.component_type !== "plant" || !node.units?.length) {
            return node;
          }
          if (node.technical_key === plantLink.toKey) {
            const anchors = { ...(node.link_anchors ?? {}) };
            delete anchors[`in:${plantLink.fromKey}`];
            return {
              ...node,
              units: node.units.map((unit) =>
                unit.intake_node_key === plantLink.fromKey
                  ? { ...unit, intake_node_key: null }
                  : unit,
              ),
              link_anchors: anchors,
            };
          }
          if (node.technical_key === plantLink.fromKey) {
            const anchors = { ...(node.link_anchors ?? {}) };
            delete anchors[`out:${plantLink.toKey}`];
            return {
              ...node,
              units: node.units.map((unit) =>
                unit.discharge_node_key === plantLink.toKey
                  ? { ...unit, discharge_node_key: null }
                  : unit,
              ),
              link_anchors: anchors,
            };
          }
          return node;
        }),
      );
      setFocusedEntityKey(null);
      markDirty();
      return;
    }
    const isNode = nodes.some((node) => node.technical_key === technicalKey);
    if (isNode) {
      setNodes((current) =>
        current
          .filter((node) => node.technical_key !== technicalKey)
          .map((node) =>
            node.units?.length
              ? {
                  ...node,
                  units: node.units.map((unit) => ({
                    ...unit,
                    intake_node_key:
                      unit.intake_node_key === technicalKey
                        ? null
                        : unit.intake_node_key,
                    discharge_node_key:
                      unit.discharge_node_key === technicalKey
                        ? null
                        : unit.discharge_node_key,
                  })),
                }
              : node,
          ),
      );
      setReaches((current) =>
        current.filter(
          (reach) =>
            reach.from_node_key !== technicalKey &&
            reach.to_node_key !== technicalKey,
        ),
      );
    } else {
      setReaches((current) =>
        current.filter((reach) => reach.technical_key !== technicalKey),
      );
    }
    setFocusedEntityKey(null);
    markDirty();
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
                    <button
                      type="button"
                      className="hydraulic-validation-focus"
                      onClick={() => setFocusedEntityKey(issue.technical_key)}
                      aria-label={`Enfocar ${issue.technical_key}`}
                    >
                      <strong>{issue.technical_key}</strong>
                      <p>{issue.message}</p>
                    </button>
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
              <HierarchyStaleBadges
                topologyStale={validation.topology_stale}
                parametersStale={validation.parameters_stale}
                fallbackMessage="Validacion hidraulica v3 stale"
              />
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
        <section className="workspace-section" aria-labelledby="diagram-tools">
          <div className="draft-section-heading">
            <h2 id="diagram-tools">Diagrama</h2>
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
          <HydraulicDiagramCanvas
            nodes={nodes}
            reaches={reaches}
            viewport={viewport}
            updateNode={updateNode}
            connectPorts={connectPorts}
            focusEntity={setFocusedEntityKey}
            focusedEntityKey={focusedEntityKey}
          />
        </section>
        <section
          className="workspace-section"
          aria-labelledby="properties-tools"
        >
          <div className="draft-section-heading">
            <h2 id="properties-tools">Propiedades</h2>
          </div>
          <HydraulicPropertiesPanel
            nodes={nodes}
            reaches={reaches}
            focusedEntityKey={focusedEntityKey}
            deleteEntity={deleteEntity}
            updateNode={updateNode}
            updateReservoir={updateReservoir}
            updateCurve={updateCurve}
            updateInflowSeries={updateInflowSeries}
            updatePlant={updatePlant}
            addUnit={addUnit}
            updateUnit={updateUnit}
            removeUnit={removeUnit}
            updateUnitCurve={updateUnitCurve}
            updateReach={updateReach}
            availableCurves={availableCurves}
            unitCurves={unitCurves}
            availableInflowSeries={availableInflowSeries}
            availableMinimumFlowSeries={availableMinimumFlowSeries}
          />
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

const INPUT_VARIANT_PRICE_SIGNAL_KEY = "price_usd_per_mwh";
const INPUT_VARIANT_PRICE_SIGNAL_KEYS = [
  "price_usd_per_mwh",
  "import_price_usd_per_mwh",
  "export_price_usd_per_mwh",
] as const;
const INPUT_VARIANT_SELECTION_STORAGE_KEY = "case-input-variant-selection";

function inputVariantSelectionStorageKey(scenarioId: number): string {
  return `${INPUT_VARIANT_SELECTION_STORAGE_KEY}:${scenarioId}`;
}

function readStoredInputVariantId(scenarioId: number): number | null {
  const rawValue = window.localStorage.getItem(
    inputVariantSelectionStorageKey(scenarioId),
  );
  if (!rawValue) return null;
  const parsed = Number(rawValue);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : null;
}

function persistInputVariantId(scenarioId: number, variantId: number): void {
  window.localStorage.setItem(
    inputVariantSelectionStorageKey(scenarioId),
    String(variantId),
  );
}

function resolveSelectedInputVariantId(
  scenarioId: number,
  preferredVariantId: number | null,
  variants: CaseInputVariantDetail[],
  defaultVariantId: number | null,
): number | null {
  if (variants.length === 0) return preferredVariantId;
  const availableVariantIds = new Set(
    variants.map((entry) => entry.variant.id),
  );
  if (
    preferredVariantId !== null &&
    availableVariantIds.has(preferredVariantId)
  ) {
    return preferredVariantId;
  }
  const storedVariantId = readStoredInputVariantId(scenarioId);
  if (storedVariantId !== null && availableVariantIds.has(storedVariantId)) {
    return storedVariantId;
  }
  if (defaultVariantId !== null && availableVariantIds.has(defaultVariantId)) {
    return defaultVariantId;
  }
  return variants[0].variant.id;
}

type InputVariantRangeValidation = {
  kind: "idle" | "valid" | "incomplete_coverage" | "horizon_mismatch";
  message: string;
};

function inputVariantRequirementKey(signal: RequiredSignalStatus): string {
  return `${signal.entity_type}:${signal.entity_id}:${signal.signal_key}`;
}

function candidateSignalKeysForRequiredSignal(
  signal: RequiredSignalStatus,
): readonly string[] {
  return signal.signal_key === INPUT_VARIANT_PRICE_SIGNAL_KEY
    ? INPUT_VARIANT_PRICE_SIGNAL_KEYS
    : [signal.signal_key];
}

function bindingMatchesRequiredSignal(
  binding: CaseTimeSeriesBinding,
  signal: RequiredSignalStatus,
): boolean {
  if (binding.entity_type == null && binding.entity_id == null) {
    return (
      signal.signal_key === INPUT_VARIANT_PRICE_SIGNAL_KEY &&
      candidateSignalKeysForRequiredSignal(signal).includes(binding.signal_key)
    );
  }
  return (
    candidateSignalKeysForRequiredSignal(signal).includes(binding.signal_key) &&
    binding.entity_type === signal.entity_type &&
    binding.entity_id === signal.entity_id
  );
}

function requiredSignalSelectLabel(signal: RequiredSignalStatus): string {
  if (
    signal.entity_type === "grid" &&
    signal.signal_key === INPUT_VARIANT_PRICE_SIGNAL_KEY
  ) {
    return "Serie de precio (price_usd_per_mwh)";
  }
  return `Serie ${signal.signal_key} (${signal.entity_id})`;
}

function requiredSignalSelectId(signal: RequiredSignalStatus): string {
  return `input_variant_binding_${signal.entity_type.replaceAll(":", "_")}_${signal.entity_id}_${signal.signal_key}`;
}

function selectedPeriodsForInputVariantRange(
  set: ProjectTimeSeriesSet | undefined,
  rangeStart: string,
  rangeEnd: string,
): ProjectTimeSeriesSet["periods"] {
  if (!set) return [];
  return set.periods
    .filter(
      (period) =>
        period.timestamp_start < rangeEnd && period.timestamp_end > rangeStart,
    )
    .sort((left, right) => left.period_index - right.period_index);
}

function validateSingleInputVariantRange(
  set: ProjectTimeSeriesSet | undefined,
  rangeStart: string,
  rangeEnd: string,
): InputVariantRangeValidation {
  if (!set || rangeStart.trim() === "" || rangeEnd.trim() === "") {
    return { kind: "idle", message: "" };
  }

  const periods = selectedPeriodsForInputVariantRange(set, rangeStart, rangeEnd);
  if (periods.length === 0) {
    return {
      kind: "incomplete_coverage",
      message: `Cobertura incompleta: set #${set.id} no tiene periodos en el rango seleccionado.`,
    };
  }

  const first = periods[0];
  if (first.timestamp_start !== rangeStart) {
    if (first.timestamp_start > rangeStart) {
      return {
        kind: "incomplete_coverage",
        message: `Cobertura incompleta: falta ${rangeStart} a ${first.timestamp_start}.`,
      };
    }
    return {
      kind: "horizon_mismatch",
      message: `Horizonte incompatible: el rango debe comenzar en limite de periodo (${first.timestamp_start}).`,
    };
  }

  const last = periods[periods.length - 1];
  if (last.timestamp_end !== rangeEnd) {
    if (last.timestamp_end < rangeEnd) {
      return {
        kind: "incomplete_coverage",
        message: `Cobertura incompleta: falta ${last.timestamp_end} a ${rangeEnd}.`,
      };
    }
    return {
      kind: "horizon_mismatch",
      message: `Horizonte incompatible: el rango debe terminar en limite de periodo (${last.timestamp_end}).`,
    };
  }

  for (let index = 1; index < periods.length; index += 1) {
    const previous = periods[index - 1];
    const current = periods[index];
    if (previous.timestamp_end !== current.timestamp_start) {
      if (previous.timestamp_end < current.timestamp_start) {
        return {
          kind: "incomplete_coverage",
          message: `Cobertura incompleta: falta ${previous.timestamp_end} a ${current.timestamp_start}.`,
        };
      }
      return {
        kind: "horizon_mismatch",
        message: `Horizonte incompatible: periodos solapados cerca de ${current.timestamp_start}.`,
      };
    }
  }

  return { kind: "valid", message: "Rango valido para correr." };
}

function validateInputVariantRange(
  sets: ProjectTimeSeriesSet[],
  rangeStart: string,
  rangeEnd: string,
): InputVariantRangeValidation {
  if (sets.length === 0 || rangeStart.trim() === "" || rangeEnd.trim() === "") {
    return { kind: "idle", message: "" };
  }

  const referenceSet = sets[0];
  const referenceValidation = validateSingleInputVariantRange(
    referenceSet,
    rangeStart,
    rangeEnd,
  );
  if (referenceValidation.kind !== "valid") {
    return referenceValidation;
  }
  const referencePeriods = selectedPeriodsForInputVariantRange(
    referenceSet,
    rangeStart,
    rangeEnd,
  );

  for (const set of sets.slice(1)) {
    const setValidation = validateSingleInputVariantRange(set, rangeStart, rangeEnd);
    if (setValidation.kind !== "valid") {
      return {
        kind: setValidation.kind,
        message: `Set #${set.id}: ${setValidation.message}`,
      };
    }
    const periods = selectedPeriodsForInputVariantRange(set, rangeStart, rangeEnd);
    if (periods.length !== referencePeriods.length) {
      return {
        kind: "horizon_mismatch",
        message: `Horizonte incompatible: set #${set.id} no coincide con set #${referenceSet.id}; no hay resampling implicito.`,
      };
    }
    for (let index = 0; index < referencePeriods.length; index += 1) {
      const referencePeriod = referencePeriods[index];
      const period = periods[index];
      if (period.timestamp_start !== referencePeriod.timestamp_start) {
        return {
          kind: "horizon_mismatch",
          message: `Horizonte incompatible: set #${set.id} no coincide con set #${referenceSet.id} en ${referencePeriod.timestamp_start}.`,
        };
      }
      if (period.duration_hours !== referencePeriod.duration_hours) {
        return {
          kind: "horizon_mismatch",
          message: `Horizonte incompatible: set #${set.id} tiene distinta duracion en ${referencePeriod.timestamp_start}.`,
        };
      }
    }
  }

  return { kind: "valid", message: "Rango valido para correr." };
}

function resolveRequiredSignalBindingKey(
  signal: RequiredSignalStatus,
  set: ProjectTimeSeriesSet | undefined,
): string {
  if (!set) {
    return signal.signal_key;
  }
  const candidateSignalKeys = candidateSignalKeysForRequiredSignal(signal);
  const matchingSignal = set.signals.find((setSignal: ProjectTimeSeriesSetSignal) =>
    candidateSignalKeys.includes(setSignal.signal_key),
  );
  return matchingSignal?.signal_key ?? signal.signal_key;
}

function buildRequiredSignalBindingPayload(
  signal: RequiredSignalStatus,
  timeSeriesSetId: number,
  set: ProjectTimeSeriesSet | undefined,
): Parameters<typeof bindCaseTimeSeries>[2] {
  if (
    signal.entity_type === "grid" &&
    signal.signal_key === INPUT_VARIANT_PRICE_SIGNAL_KEY
  ) {
    return {
      signal_key: resolveRequiredSignalBindingKey(signal, set),
      time_series_set_id: timeSeriesSetId,
    };
  }
  return {
    signal_key: resolveRequiredSignalBindingKey(signal, set),
    entity_type: signal.entity_type,
    entity_id: signal.entity_id,
    time_series_set_id: timeSeriesSetId,
  };
}

function CaseInputVariantBindingEditor({
  scenarioId,
  projectId,
  variantDetail,
  timeSeriesSets,
}: {
  scenarioId: number;
  projectId: number;
  variantDetail: CaseInputVariantDetail;
  timeSeriesSets: ProjectTimeSeriesSetSummary[];
}) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [error, setError] = useState("");
  const requiredSignals = variantDetail.required_signals || [];
  const [selectedSetIds, setSelectedSetIds] = useState<
    Record<string, number | "">
  >(() =>
    Object.fromEntries(
      requiredSignals.map((signal: RequiredSignalStatus) => {
        const matchedBinding = variantDetail.bindings.find(
          (binding: CaseTimeSeriesBinding) =>
            bindingMatchesRequiredSignal(binding, signal),
        );
        return [
          inputVariantRequirementKey(signal),
          matchedBinding?.time_series_set_id ?? "",
        ];
      }),
    ),
  );
  const priceSignal = requiredSignals.find(
    (signal: RequiredSignalStatus) =>
      signal.entity_type === "grid" &&
      signal.signal_key === INPUT_VARIANT_PRICE_SIGNAL_KEY,
  );
  const selectedPriceSetId = priceSignal
    ? selectedSetIds[inputVariantRequirementKey(priceSignal)]
    : "";
  const [rangeStartDraft, setRangeStartDraft] = useState<string | null>(null);
  const [rangeEndDraft, setRangeEndDraft] = useState<string | null>(null);

  const selectedSetIdList = Array.from(
    new Set(
      Object.values(selectedSetIds).filter(
        (value): value is number => typeof value === "number",
      ),
    ),
  ).sort((left, right) => left - right);
  const selectedSetDetailsQuery = useQuery({
    queryKey: [
      "case-input-variant-set-details",
      projectId,
      ...selectedSetIdList,
    ] as const,
    queryFn: async ({ signal }) =>
      Promise.all(
        selectedSetIdList.map((timeSeriesSetId) =>
          getProjectTimeSeriesSet(projectId, timeSeriesSetId, signal),
        ),
      ),
    enabled: selectedSetIdList.length > 0,
    retry: false,
  });
  const selectedSetDetailsById = new Map(
    (selectedSetDetailsQuery.data || []).map((set) => [set.id, set]),
  );
  const orderedSelectedSets = requiredSignals
    .map((signal: RequiredSignalStatus) => {
      const selectedSetId = selectedSetIds[inputVariantRequirementKey(signal)];
      return typeof selectedSetId === "number"
        ? selectedSetDetailsById.get(selectedSetId)
        : undefined;
    })
    .filter((set): set is ProjectTimeSeriesSet => set !== undefined);

  const rangeStart =
    rangeStartDraft ?? orderedSelectedSets[0]?.horizon.start ?? "";
  const rangeEnd = rangeEndDraft ?? orderedSelectedSets[0]?.horizon.end ?? "";
  const rangeValidation = validateInputVariantRange(
    orderedSelectedSets,
    rangeStart,
    rangeEnd,
  );
  const allRequiredSignalsSelected = requiredSignals.every(
    (signal: RequiredSignalStatus) =>
      typeof selectedSetIds[inputVariantRequirementKey(signal)] === "number",
  );
  const isStale = variantDetail.staleness.stale;
  const canRun =
    allRequiredSignalsSelected &&
    rangeStart.trim() !== "" &&
    rangeEnd.trim() !== "" &&
    rangeValidation.kind === "valid" &&
    !isStale;

  const revalidateMutation = useMutation({
    mutationFn: async () =>
      validateCaseInputVariant(scenarioId, variantDetail.variant.id, {
        range_start: rangeStart,
        range_end: rangeEnd,
      }),
    onSuccess: () => {
      setError("");
      void queryClient.invalidateQueries({
        queryKey: caseInputVariantsQueryKey(scenarioId),
      });
    },
    onError: (mutationError) => setError(errorMessage(mutationError)),
  });

  const runMutation = useMutation({
    mutationFn: async () => {
      for (const signal of requiredSignals) {
        const selectedSetId = selectedSetIds[inputVariantRequirementKey(signal)];
        if (typeof selectedSetId !== "number") {
          throw new Error(`Falta vincular ${signal.signal_key}.`);
        }
        await bindCaseTimeSeries(scenarioId, variantDetail.variant.id, {
          ...buildRequiredSignalBindingPayload(
            signal,
            selectedSetId,
            selectedSetDetailsById.get(selectedSetId),
          ),
        });
      }
      return runCaseInputVariant(scenarioId, variantDetail.variant.id, {
        range_start: rangeStart,
        range_end: rangeEnd,
      });
    },
    onSuccess: (run) => {
      setError("");
      void queryClient.invalidateQueries({
        queryKey: caseInputVariantsQueryKey(scenarioId),
      });
      void queryClient.invalidateQueries({
        queryKey: scenarioRunsQueryKey(scenarioId),
      });
      navigate(`/runs/${run.id}`);
    },
    onError: (mutationError) => setError(errorMessage(mutationError)),
  });

  return (
    <>
      {error ? <p role="alert">{error}</p> : null}
      {isStale ? (
        <div className="stale-banner" role="alert">
          <p>Variante desactualizada: revalida antes de correr.</p>
          <ul aria-label="Motivos de desactualizacion">
            {variantDetail.staleness.reasons.map(
              (reason: VariantStalenessReason, index: number) => (
                <li key={`${reason.dependency_type}:${reason.dependency_id ?? ""}:${index}`}>
                  {reason.detail}
                </li>
              ),
            )}
          </ul>
          <button
            type="button"
            disabled={revalidateMutation.isPending}
            onClick={() => {
              if (!revalidateMutation.isPending) revalidateMutation.mutate();
            }}
          >
            {revalidateMutation.isPending
              ? "Revalidando variante"
              : "Revalidar variante"}
          </button>
        </div>
      ) : null}
      {priceSignal ? (
        <p className="source-note">
          {typeof selectedPriceSetId === "number"
            ? `Precio vinculado: set #${selectedPriceSetId}.`
            : "Aun no hay una serie de precio vinculada."}
        </p>
      ) : null}
      <ul aria-label="Senales requeridas">
        {requiredSignals.map(
          (signal: RequiredSignalStatus) => (
            <li
              key={`${signal.entity_type}:${signal.entity_id}:${signal.signal_key}`}
            >
              {signal.bound
                ? `${signal.signal_key} (${signal.entity_id}): vinculada (set #${signal.time_series_set_id})`
                : `${signal.signal_key} (${signal.entity_id}): falta vincular`}
            </li>
          ),
        )}
      </ul>
      {requiredSignals.map((signal: RequiredSignalStatus) => (
        <div
          className="field-row"
          key={`binding-select:${inputVariantRequirementKey(signal)}`}
        >
          <label htmlFor={requiredSignalSelectId(signal)}>
            {requiredSignalSelectLabel(signal)}
          </label>
          <select
            id={requiredSignalSelectId(signal)}
            value={selectedSetIds[inputVariantRequirementKey(signal)] ?? ""}
            onChange={(event) => {
              const value = event.target.value;
              setError("");
              setRangeStartDraft(null);
              setRangeEndDraft(null);
              setSelectedSetIds((current) => ({
                ...current,
                [inputVariantRequirementKey(signal)]:
                  value === "" ? "" : Number(value),
              }));
            }}
          >
            <option value="">Selecciona una serie</option>
            {timeSeriesSets.map((set: ProjectTimeSeriesSetSummary) => (
              <option key={`${signal.entity_id}:${set.id}`} value={set.id}>
                {set.name} - {set.version_label}
              </option>
            ))}
          </select>
        </div>
      ))}
      <div className="field-row">
        <label htmlFor="input_variant_range_start">Inicio de rango</label>
        <input
          id="input_variant_range_start"
          type="text"
          value={rangeStart}
          onChange={(event) => setRangeStartDraft(event.target.value)}
          placeholder="2026-01-01T00:00:00-03:00"
        />
      </div>
      <div className="field-row">
        <label htmlFor="input_variant_range_end">Fin de rango</label>
        <input
          id="input_variant_range_end"
          type="text"
          value={rangeEnd}
          onChange={(event) => setRangeEndDraft(event.target.value)}
          placeholder="2026-01-02T00:00:00-03:00"
        />
      </div>
      {rangeValidation.message ? (
        <p role={rangeValidation.kind === "valid" ? "status" : "alert"}>
          {rangeValidation.message}
        </p>
      ) : null}
      <button
        type="button"
        disabled={!canRun || runMutation.isPending}
        onClick={() => {
          if (canRun && !runMutation.isPending) runMutation.mutate();
        }}
      >
        {runMutation.isPending
          ? "Corriendo variante"
          : "Vincular y correr variante"}
      </button>
    </>
  );
}

function CaseInputVariantPanel({
  scenarioId,
  projectId,
}: {
  scenarioId: number;
  projectId: number;
}) {
  const queryClient = useQueryClient();
  const [cloneError, setCloneError] = useState("");
  const [selectedVariantPreference, setSelectedVariantPreference] = useState<
    number | null
  >(() => readStoredInputVariantId(scenarioId));
  const [cloneName, setCloneName] = useState("");

  const variantQuery = useQuery({
    queryKey: caseInputVariantsQueryKey(scenarioId),
    queryFn: ({ signal }) => listCaseInputVariants(scenarioId, signal),
    retry: false,
  });
  const timeSeriesSetsQuery = useQuery({
    queryKey: timeSeriesCatalogQueryKey(projectId),
    queryFn: ({ signal }) => listProjectTimeSeriesSets(projectId, signal),
    retry: false,
  });

  const selectedVariantId = resolveSelectedInputVariantId(
    scenarioId,
    selectedVariantPreference,
    variantQuery.data?.variants ?? [],
    variantQuery.data?.default_variant_id ?? null,
  );
  const activeVariantDetail =
    variantQuery.data?.variants.find(
      (entry: CaseInputVariantDetail) => entry.variant.id === selectedVariantId,
    ) ?? variantQuery.data?.variants[0];
  const activeVariant = activeVariantDetail?.variant;

  const cloneMutation = useMutation({
    mutationFn: async () => {
      if (!activeVariant) throw new Error("No hay una variante activa.");
      return cloneCaseInputVariant(scenarioId, activeVariant.id, {
        display_name: cloneName.trim(),
      });
    },
    onSuccess: (variant) => {
      setCloneName("");
      setCloneError("");
      setSelectedVariantPreference(variant.id);
      persistInputVariantId(scenarioId, variant.id);
      void queryClient.invalidateQueries({
        queryKey: caseInputVariantsQueryKey(scenarioId),
      });
    },
    onError: (mutationError) => setCloneError(errorMessage(mutationError)),
  });

  if (variantQuery.isPending || timeSeriesSetsQuery.isPending) {
    return <LoadingView label="Cargando variantes de entrada" />;
  }
  if (variantQuery.isError) {
    return (
      <RequestErrorView
        error={variantQuery.error}
        retry={() => void variantQuery.refetch()}
      />
    );
  }
  if (timeSeriesSetsQuery.isError) {
    return (
      <RequestErrorView
        error={timeSeriesSetsQuery.error}
        retry={() => void timeSeriesSetsQuery.refetch()}
      />
    );
  }
  if (!activeVariant || !activeVariantDetail) {
    return (
      <section
        className="workspace-section"
        aria-labelledby="input-variant-panel"
      >
        <h2 id="input-variant-panel">Variantes de entrada</h2>
        <p className="empty-state">Aun no hay variantes para este caso.</p>
      </section>
    );
  }

  const canClone =
    cloneName.trim() !== "" &&
    activeVariant !== undefined &&
    !cloneMutation.isPending;

  return (
    <section
      className="workspace-section"
      aria-labelledby="input-variant-panel"
    >
      <h2 id="input-variant-panel">
        Variante de entrada: {activeVariant.display_name}
      </h2>
      {cloneError ? <p role="alert">{cloneError}</p> : null}
      <div className="field-row">
        <label htmlFor="input_variant_active">Variante activa</label>
        <select
          id="input_variant_active"
          value={selectedVariantId ?? ""}
          onChange={(event) => {
            const nextVariantId = Number(event.target.value);
            setSelectedVariantPreference(nextVariantId);
            persistInputVariantId(scenarioId, nextVariantId);
          }}
        >
          {variantQuery.data.variants.map((entry: CaseInputVariantDetail) => (
            <option key={entry.variant.id} value={entry.variant.id}>
              {entry.variant.is_default
                ? `${entry.variant.display_name} (default)`
                : entry.variant.display_name}
              {entry.staleness.stale ? " (desactualizada)" : ""}
            </option>
          ))}
        </select>
      </div>
      <div className="field-row">
        <label htmlFor="input_variant_clone_name">Nombre nueva variante</label>
        <input
          id="input_variant_clone_name"
          type="text"
          value={cloneName}
          onChange={(event) => setCloneName(event.target.value)}
          placeholder="Stress prices"
        />
        <button
          type="button"
          disabled={!canClone}
          onClick={() => {
            if (canClone) cloneMutation.mutate();
          }}
        >
          {cloneMutation.isPending
            ? "Clonando variante"
            : "Clonar variante activa"}
        </button>
      </div>
      <CaseInputVariantBindingEditor
        key={activeVariant.id}
        scenarioId={scenarioId}
        projectId={projectId}
        variantDetail={activeVariantDetail}
        timeSeriesSets={timeSeriesSetsQuery.data || []}
      />
    </section>
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
        </div>
      </header>
      <div className="workspace-stack">
        <CaseInputVariantPanel
          scenarioId={scenario.data.id}
          projectId={scenario.data.project_id}
        />
        <section className="workspace-section" aria-labelledby="version-list">
          <h2 id="version-list">Versiones inmutables</h2>
          <VersionList scenarioId={scenario.data.id} versions={versions.data} />
        </section>
        <ExpertVersionForm scenarioId={scenario.data.id} />
        <section className="workspace-section" aria-labelledby="run-list">
          <h2 id="run-list">Corridas</h2>
          <div className="inline-actions">
            <Link
              className="button-link"
              to={`/scenarios/${scenario.data.id}/runs/compare`}
            >
              Comparar corridas
            </Link>
          </div>
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

function VersionProvenance({ version }: { version: ScenarioVersionDetail }) {
  return (
    <CaseHierarchyProvenanceSummary provenance={version.generation_metadata} />
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
          aria-labelledby="version-provenance"
        >
          <h2 id="version-provenance">Procedencia</h2>
          <VersionProvenance version={version.data} />
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
      {version?.generation_metadata.input_variant ? (
        <div>
          <dt>Variante</dt>
          <dd>
            {version.generation_metadata.input_variant.display_name ||
              `ID ${version.generation_metadata.input_variant.id}`}
          </dd>
        </div>
      ) : null}
      {version?.generation_metadata.date_range ? (
        <div>
          <dt>Rango de fechas</dt>
          <dd>
            {version.generation_metadata.date_range.start} -{" "}
            {version.generation_metadata.date_range.end}
          </dd>
        </div>
      ) : null}
    </dl>
  );
}

function RunProvenance({ version }: { version?: ScenarioVersionDetail }) {
  if (!version) {
    return <p className="source-note">Cargando procedencia de la version.</p>;
  }
  return (
    <CaseHierarchyProvenanceSummary provenance={version.generation_metadata} />
  );
}

function RunSeriesBindingsLineage({
  version,
}: {
  version?: ScenarioVersionDetail;
}) {
  if (!version) {
    return <p className="source-note">Cargando series de entrada.</p>;
  }
  const bindings = version.generation_metadata.series_bindings;
  if (!bindings || bindings.length === 0) {
    return (
      <p className="source-note">
        Esta corrida no proviene de una variante de entrada.
      </p>
    );
  }
  return (
    <ul aria-label="Series vinculadas" className="resource-list">
      {bindings.map((binding, index) => (
        <li
          key={`${binding.signal_key}:${binding.entity_id ?? ""}:${index}`}
        >
          {binding.signal_key}
          {binding.entity_id ? ` (${binding.entity_id})` : ""}: set #
          {binding.time_series_set_id} - {binding.version_label} (v
          {binding.version_number}, revision {binding.revision_number}) - hash{" "}
          {hierarchyProvenanceHashLabel(binding)}
        </li>
      ))}
    </ul>
  );
}

function RunTechnicalSnapshot({
  version,
}: {
  version?: ScenarioVersionDetail;
}) {
  const [open, setOpen] = useState(false);
  if (!version) {
    return <p className="source-note">Cargando snapshot tecnico.</p>;
  }
  return (
    <details
      open={open}
      onToggle={(event) => setOpen(event.currentTarget.open)}
    >
      <summary>Ver snapshot tecnico</summary>
      {open ? (
        <>
          <pre className="json-panel">
            {prettyJson(version.system_case_json)}
          </pre>
          <pre className="json-panel">
            {prettyJson(version.generation_metadata)}
          </pre>
        </>
      ) : null}
    </details>
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
        <section className="workspace-section" aria-labelledby="run-provenance">
          <h2 id="run-provenance">Procedencia</h2>
          <RunProvenance version={version.data} />
        </section>
        <section
          className="workspace-section"
          aria-labelledby="run-series-lineage"
        >
          <h2 id="run-series-lineage">Series de entrada</h2>
          <RunSeriesBindingsLineage version={version.data} />
        </section>
        <section
          className="workspace-section"
          aria-labelledby="run-technical-snapshot"
        >
          <h2 id="run-technical-snapshot">Snapshot tecnico</h2>
          <RunTechnicalSnapshot version={version.data} />
        </section>
        <RunFailureDetails run={runData} />
        <RunResultsSection run={runData} />
        <PublicationSection run={runData} projectId={project.data?.id} />
        <RunArtifactsSection run={runData} />
      </div>
    </section>
  );
}
