import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FormEvent, ReactNode, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import {
  ApiError,
  createManualRun,
  createProject,
  createScenario,
  createScenarioVersionFromJson,
  deleteScenarioVersion,
  getRun,
  getProject,
  getScenario,
  getScenarioVersion,
  listProjects,
  listScenarioRuns,
  listScenarios,
  listScenarioVersions,
  uploadScenarioVersion,
  type Project,
  type ProjectCreatePayload,
  type Scenario,
  type ScenarioCreatePayload,
  type ScenarioRun,
  type ScenarioVersion,
  type ScenarioVersionDetail,
} from "./api/client";
import { RunArtifactsSection, RunResultsSection } from "./RunResults";

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
const runQueryKey = (runId: number) => ["run", runId] as const;
const terminalRunStatuses = new Set(["succeeded", "failed"]);

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  return "No se pudo completar la accion.";
}

function prettyJson(value: unknown): string {
  return JSON.stringify(value ?? {}, null, 2);
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

export function ProjectDetailView() {
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
      <div className="workspace-grid">
        <section className="workspace-section" aria-labelledby="scenario-list">
          <h2 id="scenario-list">Escenarios</h2>
          <ScenarioList scenarios={scenarios.data} />
        </section>
        <CreateScenarioForm projectId={projectId} />
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
        <Link
          className="button-link"
          to={`/scenarios/${scenario.data.id}/draft`}
        >
          Abrir draft
        </Link>
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
        <RunArtifactsSection run={runData} />
      </div>
    </section>
  );
}
