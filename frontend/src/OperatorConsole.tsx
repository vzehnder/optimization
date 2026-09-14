import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ClipboardEvent,
  FormEvent,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { Link, useMatch, useParams } from "react-router-dom";

import {
  ApiError,
  ConsoleSaveError,
  acquireConsoleGroupLease,
  createConsoleRun,
  createOperatorConsole,
  forceReleaseOperatorConsoleGroupLease,
  getConsoleGroupHistory,
  getConsoleGroupValues,
  getConsoleRun,
  getConsoleRunComparison,
  getConsoleSeriesOptions,
  listCaseInputVariants,
  getConsoleShell,
  getOperatorConsole,
  getScenarioDraft,
  heartbeatConsoleGroupLease,
  listOperableConsoles,
  listConsoleRuns,
  listOperatorConsoles,
  releaseConsoleGroupLease,
  requestConsoleReview,
  restoreOperatorConsoleSeriesRevision,
  saveConsoleGroupValues,
  saveOperatorConsole,
  saveConsoleParameters,
  saveConsoleSeriesSelections,
  type ConsoleComparisonSide,
  type ConsoleGroup,
  type ConsoleGroupHistoryEntry,
  type ConsoleGroupValuesSnapshot,
  type ConsoleKpiDifference,
  type ConsoleLease,
  type ConsoleRunEntry,
  type OperatorConsole,
  type OperatorConsoleColumn,
  type OperatorConsoleDocument,
  type OperatorConsoleGroup,
  type OperatorConsoleStatus,
  undoConsoleGroupSave,
  validateCaseInputVariant,
} from "./api/client";
import { loadPlotly, type PlotlyTrace } from "./plotly";
import { PortalResultsBlock } from "./PortalResults";
import { ConsoleResultsConfiguration } from "./ConsoleResultsConfiguration";
import {
  signalCatalogEntry,
  signalCatalogOptions,
  useSignalCatalog,
  type SignalCatalogEntry,
} from "./signalCatalog";

const operatorConsolesQueryKey = (scenarioId: number) =>
  ["operator-consoles", scenarioId] as const;
const operatorConsoleQueryKey = (scenarioId: number, consoleId: number) =>
  ["operator-console", scenarioId, consoleId] as const;
const consoleShellListQueryKey = ["console-shell-list"] as const;
const consoleShellQueryKey = (consoleId: number) =>
  ["console-shell", consoleId] as const;
const consoleRunsQueryKey = (consoleId: number) =>
  ["console-runs", consoleId] as const;
const consoleComparisonQueryKey = (
  consoleId: number,
  left: number,
  right: number,
) => ["console-run-comparison", consoleId, left, right] as const;
const consoleSeriesOptionsQueryKey = (consoleId: number) =>
  ["console-series-options", consoleId] as const;
const consoleGroupValuesQueryKey = (
  consoleId: number,
  groupId: string,
  start: string,
  end: string,
  granularity: string,
) =>
  [
    "console-group-values",
    consoleId,
    groupId,
    start,
    end,
    granularity,
  ] as const;
const consoleGroupHistoryQueryKey = (consoleId: number, groupId: string) =>
  ["console-group-history", consoleId, groupId] as const;

const STATUS_LABELS: Record<OperatorConsoleStatus, string> = {
  draft: "Borrador",
  active: "Activa",
};

const BLOCKING_LABELS: Record<string, string> = {
  dependencia_movida: "Dependencia movida",
  campo_no_disponible: "Campo no disponible",
};

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error && error.message) return error.message;
  return "No se pudo completar la accion.";
}

function numericParam(value: string | undefined): number | null {
  const parsed = Number(value);
  if (!value || !Number.isInteger(parsed) || parsed < 1) return null;
  return parsed;
}

function datetimeLocalInputValue(value: string | null | undefined): string {
  if (!value) return "";
  const match = value.match(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/);
  return match?.[0] || "";
}

function rangeRequestValue(
  editedValue: string | null,
  originalValue: string | null | undefined,
): string {
  if (editedValue === null) return originalValue || "";
  if (!editedValue) return "";
  const timezone = originalValue?.match(/(Z|[+-]\d{2}:\d{2})$/)?.[1] || "";
  const withSeconds =
    editedValue.length === "2026-01-01T00:00".length
      ? `${editedValue}:00`
      : editedValue;
  return `${withSeconds}${timezone}`;
}

function emptyConsoleDocument(name: string): OperatorConsoleDocument {
  return {
    schema_version: "operator_console_config.v1",
    public_identity: { name, description: "" },
    parameters: [],
    groups: [],
    results: { kpis: [], charts: [], tables: [] },
  };
}

function blockingLabel(reason: string | null): string {
  if (!reason) return "Ninguno";
  return BLOCKING_LABELS[reason] || reason;
}

function configurationTargetId(target: {
  section: "parameters" | "groups";
  group_id?: string;
  id: string;
}): string {
  return target.section === "parameters"
    ? `console-parameter-${target.id}`
    : `console-column-signal-${target.group_id}-${target.id}`;
}

export function OperatorConsolePanel({ scenarioId }: { scenarioId: number }) {
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [sourceVariantId, setSourceVariantId] = useState<number | null>(null);
  const [error, setError] = useState("");
  const consoles = useQuery({
    queryKey: operatorConsolesQueryKey(scenarioId),
    queryFn: ({ signal }) => listOperatorConsoles(scenarioId, signal),
    retry: false,
  });
  const variants = useQuery({
    queryKey: ["operator-console-source-variants", scenarioId] as const,
    queryFn: ({ signal }) => listCaseInputVariants(scenarioId, signal),
    retry: false,
  });
  const selectedVariantId =
    sourceVariantId ?? variants.data?.default_variant_id ?? null;

  const createMutation = useMutation({
    mutationFn: async () => {
      if (selectedVariantId === null) {
        throw new Error("Elige una variante de origen para la consola.");
      }
      return createOperatorConsole(scenarioId, {
        source_variant_id: selectedVariantId,
        document: emptyConsoleDocument(name.trim()),
      });
    },
    onSuccess: () => {
      setName("");
      setError("");
      void queryClient.invalidateQueries({
        queryKey: operatorConsolesQueryKey(scenarioId),
      });
    },
    onError: (mutationError) => setError(errorMessage(mutationError)),
  });
  const revalidateMutation = useMutation({
    mutationFn: ({
      variantId,
      rangeStart,
      rangeEnd,
    }: {
      variantId: number;
      rangeStart: string;
      rangeEnd: string;
    }) =>
      validateCaseInputVariant(scenarioId, variantId, {
        range_start: rangeStart,
        range_end: rangeEnd,
      }),
    onSuccess: async () => {
      setError("");
      await queryClient.invalidateQueries({
        queryKey: operatorConsolesQueryKey(scenarioId),
      });
    },
    onError: (mutationError) => setError(errorMessage(mutationError)),
  });

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!name.trim() || createMutation.isPending) return;
    createMutation.mutate();
  }

  function revalidate(console: OperatorConsole) {
    const action = console.blocking.action;
    if (action?.kind !== "revalidate_variant") return;
    revalidateMutation.mutate({
      variantId: action.variant_id,
      rangeStart: action.range_start,
      rangeEnd: action.range_end,
    });
  }

  return (
    <section
      className="workspace-section"
      aria-labelledby="operator-console-list"
    >
      <h2 id="operator-console-list">Consolas de operador</h2>
      <p className="source-note">
        Cada consola tiene su propia variante clonada; el operador nunca ve la
        variante del analista.
      </p>
      {error ? <p role="alert">{error}</p> : null}
      <form className="console-create-form" onSubmit={submit}>
        <label htmlFor="operator-console-name">Nombre de la consola</label>
        <input
          id="operator-console-name"
          type="text"
          value={name}
          onChange={(event) => setName(event.target.value)}
        />
        <label htmlFor="operator-console-source-variant">
          Variante de origen
        </label>
        <select
          id="operator-console-source-variant"
          value={selectedVariantId ?? ""}
          onChange={(event) => setSourceVariantId(Number(event.target.value))}
        >
          {(variants.data?.variants ?? []).map((entry) => (
            <option key={entry.variant.id} value={entry.variant.id}>
              {entry.variant.display_name}
            </option>
          ))}
        </select>
        <button
          type="submit"
          disabled={!name.trim() || createMutation.isPending}
        >
          Crear consola
        </button>
      </form>
      {consoles.isPending ? <p role="status">Cargando consolas</p> : null}
      {consoles.isError ? (
        <p role="alert">{errorMessage(consoles.error)}</p>
      ) : null}
      {consoles.data && consoles.data.length === 0 ? (
        <p className="empty-state">Este escenario todavia no tiene consolas.</p>
      ) : null}
      {consoles.data && consoles.data.length > 0 ? (
        <table className="console-table">
          <thead>
            <tr>
              <th scope="col">Consola</th>
              <th scope="col">Estado</th>
              <th scope="col">Bloqueo</th>
              <th scope="col">Espera desde</th>
              <th scope="col">Origen de copias</th>
              <th scope="col">Acciones</th>
            </tr>
          </thead>
          <tbody>
            {consoles.data.map((console) => (
              <tr key={console.id}>
                <th scope="row">{console.document.public_identity.name}</th>
                <td>{STATUS_LABELS[console.status]}</td>
                <td>{blockingLabel(console.blocking.reason)}</td>
                <td>{console.waiting_since || "Sin espera"}</td>
                <td>
                  {(console.series_copies ?? []).some(
                    (copy) => !copy.archived && copy.origin?.old,
                  )
                    ? (console.series_copies ?? [])
                        .filter((copy) => !copy.archived && copy.origin?.old)
                        .map((copy) => (
                          <span key={copy.id} className="role-badge">
                            Copia antigua: {copy.origin!.name} (origen{" "}
                            {copy.origin!.copied_revision}, vigente{" "}
                            {copy.origin!.current_revision})
                          </span>
                        ))
                    : "Al dia"}
                </td>
                <td>
                  {console.blocking.action?.kind === "revalidate_variant" ? (
                    <button
                      type="button"
                      disabled={revalidateMutation.isPending}
                      onClick={() => revalidate(console)}
                    >
                      {revalidateMutation.isPending
                        ? "Revalidando variante"
                        : "Revalidar variante"}
                    </button>
                  ) : console.blocking.action?.kind === "edit_configuration" ? (
                    <Link
                      to={
                        `/scenarios/${scenarioId}/consoles/${console.id}` +
                        `#${configurationTargetId(console.blocking.action.target)}`
                      }
                    >
                      Corregir {console.blocking.action.target.label}
                    </Link>
                  ) : null}{" "}
                  <Link to={`/scenarios/${scenarioId}/consoles/${console.id}`}>
                    Configurar
                  </Link>{" "}
                  <Link to={`/console/${console.id}`}>Probar</Link>{" "}
                  {console.technical_failure ? (
                    <Link to={`/runs/${console.technical_failure.run_id}`}>
                      Ver fallo tecnico {console.technical_failure.reference}
                    </Link>
                  ) : null}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}
    </section>
  );
}

export function OperatorConsoleEditorView() {
  const params = useParams();
  const scenarioId = numericParam(params.scenarioId);
  const consoleId = numericParam(params.consoleId);
  const queryClient = useQueryClient();
  const [error, setError] = useState("");
  const [formGeneration, setFormGeneration] = useState(0);
  const [configurationDirty, setConfigurationDirty] = useState(false);

  const consoleQuery = useQuery({
    queryKey: operatorConsoleQueryKey(scenarioId || 0, consoleId || 0),
    queryFn: ({ signal }) =>
      getOperatorConsole(scenarioId || 0, consoleId || 0, signal),
    enabled: scenarioId !== null && consoleId !== null,
    retry: false,
  });

  const signalCatalog = useSignalCatalog();

  const saveMutation = useMutation({
    mutationFn: (payload: {
      document: OperatorConsoleDocument;
      status: OperatorConsoleStatus;
      expected_revision: number;
    }) => saveOperatorConsole(scenarioId || 0, consoleId || 0, payload),
    onSuccess: (saved) => {
      setError("");
      queryClient.setQueryData<OperatorConsole>(
        operatorConsoleQueryKey(scenarioId || 0, consoleId || 0),
        saved,
      );
      setFormGeneration((current) => current + 1);
      void queryClient.invalidateQueries({
        queryKey: operatorConsolesQueryKey(scenarioId || 0),
      });
    },
    onError: (mutationError) =>
      setError(
        mutationError instanceof ApiError && mutationError.status === 409
          ? "La configuración cambió en otra sesión. Tus cambios siguen aquí y no se han guardado."
          : errorMessage(mutationError),
      ),
  });
  const forceRelease = useMutation({
    mutationFn: (groupId: string) =>
      forceReleaseOperatorConsoleGroupLease(
        scenarioId || 0,
        consoleId || 0,
        groupId,
      ),
    onSuccess: async () => {
      setError("");
      await queryClient.invalidateQueries({
        queryKey: operatorConsoleQueryKey(scenarioId || 0, consoleId || 0),
      });
    },
    onError: (mutationError) => setError(errorMessage(mutationError)),
  });
  const restoreSeries = useMutation({
    mutationFn: ({
      copyId,
      revisionNumber,
      currentRevision,
    }: {
      copyId: number;
      revisionNumber: number;
      currentRevision: number;
    }) =>
      restoreOperatorConsoleSeriesRevision(
        scenarioId || 0,
        consoleId || 0,
        copyId,
        {
          revision_number: revisionNumber,
          expected_current_revision: currentRevision,
          note: "Restauracion desde la consola interna",
        },
      ),
    onSuccess: async () => {
      setError("");
      await queryClient.invalidateQueries({
        queryKey: operatorConsoleQueryKey(scenarioId || 0, consoleId || 0),
      });
    },
    onError: (mutationError) => setError(errorMessage(mutationError)),
  });

  if (scenarioId === null || consoleId === null) {
    return (
      <section className="content-panel">
        <h1>No encontrado</h1>
        <p>La consola solicitada no existe.</p>
      </section>
    );
  }
  if (consoleQuery.isPending) {
    return <p role="status">Cargando consola</p>;
  }
  const inaccessible =
    consoleQuery.error instanceof ApiError &&
    [401, 403, 404].includes(consoleQuery.error.status);
  if (consoleQuery.isError && (!consoleQuery.data || inaccessible)) {
    return (
      <section className="content-panel">
        <h1>No se pudo cargar</h1>
        <p role="alert">{errorMessage(consoleQuery.error)}</p>
        <button type="button" onClick={() => void consoleQuery.refetch()}>
          Reintentar configuración
        </button>
      </section>
    );
  }

  const console = consoleQuery.data!;
  const identity = console.document.public_identity;
  const repairTarget =
    console.blocking.action?.kind === "edit_configuration"
      ? console.blocking.action.target
      : null;

  function save(
    document: OperatorConsoleDocument,
    status: OperatorConsoleStatus,
    expectedRevision = console.revision,
  ) {
    saveMutation.mutate({
      document,
      status,
      expected_revision: expectedRevision,
    });
  }

  return (
    <section
      className="workspace-view console-experience"
      aria-labelledby="operator-console-editor"
    >
      <h1 id="operator-console-editor">Configuracion de la consola</h1>
      {consoleQuery.isError ? (
        <p role="alert">
          No se pudo actualizar la configuración. Conservamos tu edición.{" "}
          <button type="button" onClick={() => void consoleQuery.refetch()}>
            Reintentar configuración
          </button>
        </p>
      ) : null}
      <p>
        <span className="role-badge">{STATUS_LABELS[console.status]}</span>{" "}
        <span>Revision {console.revision}</span>
      </p>
      {error ? <p role="alert">{error}</p> : null}
      {saveMutation.error instanceof ApiError &&
      saveMutation.error.status === 409 ? (
        <button
          type="button"
          className="secondary-button"
          onClick={async () => {
            try {
              const latest = await getOperatorConsole(scenarioId, consoleId);
              queryClient.setQueryData(
                operatorConsoleQueryKey(scenarioId, consoleId),
                latest,
              );
              setFormGeneration((current) => current + 1);
              setError("");
              saveMutation.reset();
            } catch (readError) {
              setError(errorMessage(readError));
            }
          }}
        >
          Descartar mis cambios y cargar la configuración vigente
        </button>
      ) : null}
      <dl className="console-detail-list">
        <dt>Identidad publica</dt>
        <dd>{identity.name}</dd>
        <dt>Descripcion</dt>
        <dd>{identity.description || "Sin descripcion."}</dd>
        <dt>Preparada por</dt>
        <dd>{console.prepared_by || "Sin registro"}</dd>
        <dt>Variante propia</dt>
        <dd>{console.owned_variant.display_name}</dd>
        <dt>Bloqueo</dt>
        <dd>{blockingLabel(console.blocking.reason)}</dd>
      </dl>
      {repairTarget?.section === "parameters" ? (
        <p
          id={configurationTargetId(repairTarget)}
          className="stale-banner"
          role="status"
        >
          Campo a corregir: parametro {repairTarget.label} ({repairTarget.id}).
        </p>
      ) : null}
      <ConsoleDocumentForm
        key={`${console.id}:${formGeneration}`}
        document={console.document}
        revision={console.revision}
        catalog={signalCatalog.data ?? []}
        catalogError={
          signalCatalog.isError ? errorMessage(signalCatalog.error) : ""
        }
        disabled={saveMutation.isPending}
        onDirtyChange={setConfigurationDirty}
        onSave={(document, revision) =>
          save(document, console.status, revision)
        }
      />
      <section
        className="content-panel console-series-coordination"
        aria-labelledby="console-series-coordination-title"
      >
        <h2 id="console-series-coordination-title">
          Coordinacion e historial de series
        </h2>
        {console.group_leases?.length ? (
          <ul className="resource-list">
            {console.group_leases.map((lease) => (
              <li key={lease.group_id}>
                <strong>{lease.group_label}</strong>: {lease.holder_name} edita
                hasta {lease.expires_at}.
                {console.can_force_release ? (
                  <button
                    type="button"
                    className="secondary-button"
                    disabled={forceRelease.isPending}
                    onClick={() => forceRelease.mutate(lease.group_id)}
                  >
                    Forzar liberacion de {lease.group_label}
                  </button>
                ) : null}
              </li>
            ))}
          </ul>
        ) : (
          <p className="empty-state">No hay grupos bloqueados.</p>
        )}
        {console.series_copies?.length ? (
          console.series_copies.map((copy) => (
            <article key={copy.id} className="console-copy-history">
              <h3>
                Copia operativa {copy.id} · revision vigente{" "}
                {copy.current_revision}
              </h3>
              {copy.archived ? <p className="source-note">Archivada</p> : null}
              <ol className="resource-list">
                {copy.revisions.map((revision) => (
                  <li key={revision.revision_number}>
                    <strong>Revision {revision.revision_number}</strong> ·{" "}
                    {revision.actor} · {revision.date} · {revision.cell_count}{" "}
                    {revision.cell_count === 1 ? "celda" : "celdas"}
                    <p>{revision.note}</p>
                    {revision.can_restore ? (
                      <button
                        type="button"
                        className="secondary-button"
                        disabled={restoreSeries.isPending}
                        onClick={() =>
                          restoreSeries.mutate({
                            copyId: copy.id,
                            revisionNumber: revision.revision_number,
                            currentRevision: copy.current_revision,
                          })
                        }
                      >
                        Restaurar revision {revision.revision_number}
                      </button>
                    ) : null}
                  </li>
                ))}
              </ol>
            </article>
          ))
        ) : (
          <p className="empty-state">Todavia no hay copias operativas.</p>
        )}
      </section>
      <div className="inline-actions">
        {console.status === "draft" ? (
          <button
            type="button"
            disabled={saveMutation.isPending || configurationDirty}
            onClick={() => save(console.document, "active")}
          >
            Activar
          </button>
        ) : (
          <button
            type="button"
            disabled={saveMutation.isPending || configurationDirty}
            onClick={() => save(console.document, "draft")}
          >
            Desactivar
          </button>
        )}
        <Link className="button-link" to={`/console/${console.id}`}>
          Probar consola
        </Link>
        <Link className="button-link" to={`/scenarios/${scenarioId}`}>
          Volver al escenario
        </Link>
      </div>
    </section>
  );
}

function editableConsoleDocument(
  value: unknown,
): value is OperatorConsoleDocument {
  const record = (item: unknown): item is Record<string, unknown> =>
    item !== null && typeof item === "object" && !Array.isArray(item);
  const texts = (item: Record<string, unknown>, keys: string[]) =>
    keys.every((key) => typeof item[key] === "string");
  const list = (
    items: unknown,
    check: (item: Record<string, unknown>) => boolean,
  ): boolean =>
    Array.isArray(items) && items.every((item) => record(item) && check(item));
  const unit = (item: Record<string, unknown>) =>
    item.unit === null || typeof item.unit === "string";
  if (
    !record(value) ||
    value.schema_version !== "operator_console_config.v1" ||
    !record(value.public_identity) ||
    !texts(value.public_identity, ["name", "description"]) ||
    !record(value.results)
  )
    return false;
  // This is a rendering guard, not a replacement for backend schema/semantic validation.
  return (
    list(
      value.parameters,
      (item) =>
        texts(item, ["id", "label"]) &&
        unit(item) &&
        record(item.pointer) &&
        texts(item.pointer, ["asset_id", "field"]) &&
        ["min", "max", "default"].every(
          (key) => typeof item[key] === "number" && Number.isFinite(item[key]),
        ),
    ) &&
    list(
      value.groups,
      (group) =>
        texts(group, ["id", "label"]) &&
        Array.isArray(group.granularities) &&
        group.granularities.every((item) => typeof item === "string") &&
        list(
          group.columns,
          (column) =>
            texts(column, ["id", "label", "default_source_option_id"]) &&
            typeof column.editable === "boolean" &&
            record(column.signal) &&
            texts(column.signal, ["entity_type", "entity_id", "signal_key"]) &&
            list(
              column.source_options,
              (option) =>
                texts(option, ["id", "label"]) &&
                typeof option.time_series_set_id === "number",
            ),
        ),
    ) &&
    list(
      value.results.kpis,
      (item) =>
        texts(item, ["id", "path", "label", "sign", "emphasis"]) &&
        unit(item) &&
        typeof item.decimals === "number",
    ) &&
    list(
      value.results.charts,
      (item) =>
        texts(item, ["id", "chart_key", "label"]) &&
        list(item.series, (series) => texts(series, ["key", "label"])),
    ) &&
    list(
      value.results.tables,
      (item) =>
        texts(item, ["id", "table_key", "label"]) &&
        typeof item.row_limit === "number" &&
        list(
          item.columns,
          (column) => texts(column, ["id", "key", "label"]) && unit(column),
        ),
    )
  );
}

function ConsoleDocumentForm({
  document,
  revision,
  catalog,
  catalogError,
  disabled,
  onDirtyChange,
  onSave,
}: {
  document: OperatorConsoleDocument;
  revision: number;
  catalog: SignalCatalogEntry[];
  catalogError: string;
  disabled: boolean;
  onDirtyChange: (dirty: boolean) => void;
  onSave: (document: OperatorConsoleDocument, revision: number) => void;
}) {
  const [value, setValue] = useState(document);
  const [baseDocument] = useState(document);
  const [baseRevision] = useState(revision);
  const [expertText, setExpertText] = useState<string | null>(null);
  const [showResults, setShowResults] = useState(false);
  const [formError, setFormError] = useState("");
  const dirty =
    JSON.stringify(value) !== JSON.stringify(baseDocument) ||
    (expertText !== null &&
      expertText !== JSON.stringify(baseDocument, null, 2));
  useEffect(() => {
    onDirtyChange(dirty);
  }, [dirty, onDirtyChange]);
  const { scenarioId } = useParams();
  const model = useQuery({
    queryKey: ["console-parameter-model", scenarioId],
    queryFn: ({ signal }) => getScenarioDraft(Number(scenarioId), signal),
    retry: false,
  });
  const assets = [
    ...(model.data?.document.grid ? [model.data.document.grid] : []),
    ...(model.data?.document.assets ?? []),
  ].filter((asset) => typeof asset.id === "string");
  const [chosenAsset, setChosenAsset] = useState("");
  const [chosenField, setChosenField] = useState("");
  const fieldsFor = (assetId: string) =>
    Object.entries(assets.find((asset) => asset.id === assetId) ?? {})
      .filter(
        ([, fieldValue]) =>
          typeof fieldValue === "number" && Number.isFinite(fieldValue),
      )
      .map(([field, fieldValue]) => ({ field, value: fieldValue as number }));
  const availableFields = fieldsFor(chosenAsset).filter(
    ({ field }) =>
      !value.parameters.some(
        (parameter) =>
          parameter.pointer.asset_id === chosenAsset &&
          parameter.pointer.field === field,
      ),
  );

  function readExpert(): OperatorConsoleDocument | null {
    try {
      const parsed = JSON.parse(expertText || "");
      if (!editableConsoleDocument(parsed)) {
        setFormError(
          "Revisa la estructura de la configuración completa. Conservamos el texto para corregirlo.",
        );
        return null;
      }
      return parsed;
    } catch {
      setFormError(
        "El documento no es JSON válido. Corrígelo antes de guardar o volver al formulario.",
      );
      return null;
    }
  }

  function patchColumn(
    groupId: string,
    columnId: string,
    patch: (column: OperatorConsoleColumn) => OperatorConsoleColumn,
  ) {
    setValue((current) => ({
      ...current,
      groups: current.groups.map((group) =>
        group.id !== groupId
          ? group
          : {
              ...group,
              columns: group.columns.map((column) =>
                column.id !== columnId ? column : patch(column),
              ),
            },
      ),
    }));
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const next = expertText === null ? value : readExpert();
    if (!next) return;
    for (const group of next.groups) {
      for (const column of group.columns) {
        if (!signalCatalogEntry(catalog, column.signal.signal_key)) {
          setFormError(
            `La senal ${column.signal.signal_key} no esta en el catalogo canonico de senales.`,
          );
          return;
        }
      }
    }
    setFormError("");
    onSave(
      {
        ...next,
        public_identity: {
          ...next.public_identity,
          name: next.public_identity.name.trim(),
          description: next.public_identity.description.trim(),
        },
      },
      baseRevision,
    );
  }

  return (
    <form
      className="workspace-form console-document-form"
      onSubmit={submit}
      onInvalidCapture={(event) => {
        event.preventDefault();
        const form = event.currentTarget;
        setShowResults(true);
        setFormError(
          "Completa los campos obligatorios y revisa sus límites antes de guardar.",
        );
        requestAnimationFrame(() =>
          form
            .querySelector<HTMLElement>(
              "input:invalid, select:invalid, textarea:invalid",
            )
            ?.focus(),
        );
      }}
    >
      <p role="status">
        {disabled
          ? "Guardando configuración"
          : dirty
            ? "Cambios sin guardar. Guarda antes de activar o probar."
            : "Configuración guardada"}
      </p>
      {formError ? <p role="alert">{formError}</p> : null}
      {catalogError ? <p role="alert">{catalogError}</p> : null}
      <fieldset disabled={disabled} className="console-config-fields">
        <button
          type="button"
          className="secondary-button"
          onClick={(event) => {
            if (expertText === null) {
              const form = event.currentTarget.form;
              if (form && !form.checkValidity()) {
                setShowResults(true);
                setFormError(
                  "Completa los campos del formulario antes de abrir el JSON avanzado.",
                );
                requestAnimationFrame(() => {
                  form
                    .querySelector<HTMLElement>(
                      "input:invalid, select:invalid, textarea:invalid",
                    )
                    ?.focus();
                  form.reportValidity();
                });
                return;
              }
              setExpertText(JSON.stringify(value, null, 2));
              setFormError("");
            } else {
              const next = readExpert();
              if (next) {
                setValue(next);
                setExpertText(null);
                setFormError("");
              }
            }
          }}
        >
          {expertText === null
            ? "Editar JSON avanzado"
            : "Volver al formulario"}
        </button>
        {expertText !== null ? (
          <label>
            Configuración completa (JSON)
            <textarea
              rows={16}
              value={expertText}
              onChange={(event) => setExpertText(event.target.value)}
            />
          </label>
        ) : (
          <>
            <label htmlFor="console-identity-name">Nombre publico</label>
            <input
              id="console-identity-name"
              type="text"
              required
              value={value.public_identity.name}
              onChange={(event) =>
                setValue({
                  ...value,
                  public_identity: {
                    ...value.public_identity,
                    name: event.target.value,
                  },
                })
              }
            />
            <label htmlFor="console-identity-description">
              Descripcion publica
            </label>
            <input
              id="console-identity-description"
              type="text"
              value={value.public_identity.description}
              onChange={(event) =>
                setValue({
                  ...value,
                  public_identity: {
                    ...value.public_identity,
                    description: event.target.value,
                  },
                })
              }
            />
            <section aria-label="Parámetros expuestos">
              <h2>Parámetros</h2>
              <p>
                Expón campos numéricos del modelo. Los límites y el valor
                inicial configuran el control; no modifican el modelo guardado.
              </p>
              {model.isError ? (
                <p className="source-note">
                  No se pudieron consultar los campos del modelo.{" "}
                  <button type="button" onClick={() => void model.refetch()}>
                    Reintentar campos
                  </button>
                </p>
              ) : null}
              <label>
                Componente del parámetro
                <select
                  value={chosenAsset}
                  onChange={(event) => {
                    setChosenAsset(event.target.value);
                    setChosenField("");
                  }}
                >
                  <option value="">Elegir componente</option>
                  {assets.map((asset) => (
                    <option key={asset.id} value={asset.id}>
                      {String(asset.name || asset.id)}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Campo del modelo
                <select
                  value={chosenField}
                  onChange={(event) => setChosenField(event.target.value)}
                >
                  <option value="">Elegir campo numérico</option>
                  {availableFields.map(({ field }) => (
                    <option key={field} value={field}>
                      {field}
                    </option>
                  ))}
                </select>
              </label>
              <button
                type="button"
                disabled={
                  !availableFields.some((item) => item.field === chosenField)
                }
                onClick={() => {
                  const field = availableFields.find(
                    (item) => item.field === chosenField,
                  );
                  if (!field) return;
                  let number = value.parameters.length + 1;
                  while (
                    value.parameters.some(
                      (item) => item.id === `parametro_${number}`,
                    )
                  )
                    number++;
                  setValue({
                    ...value,
                    parameters: [
                      ...value.parameters,
                      {
                        id: `parametro_${number}`,
                        pointer: { asset_id: chosenAsset, field: chosenField },
                        label: chosenField,
                        unit: null,
                        min: Math.min(0, field.value),
                        max: Math.max(0, field.value),
                        default: field.value,
                      },
                    ],
                  });
                  setChosenField("");
                }}
              >
                Agregar parámetro
              </button>
              {value.parameters.map((parameter, index) => {
                const patch = (changes: Partial<typeof parameter>) =>
                  setValue({
                    ...value,
                    parameters: value.parameters.map((item, position) =>
                      position !== index ? item : { ...item, ...changes },
                    ),
                  });
                return (
                  <fieldset
                    key={parameter.id}
                    className="console-group-fieldset"
                  >
                    <legend>Parámetro {index + 1}</legend>
                    <label>
                      Etiqueta
                      <input
                        required
                        value={parameter.label}
                        onChange={(event) =>
                          patch({ label: event.target.value })
                        }
                      />
                    </label>
                    <label>
                      Unidad
                      <input
                        value={parameter.unit ?? ""}
                        onChange={(event) =>
                          patch({ unit: event.target.value || null })
                        }
                      />
                    </label>
                    {(
                      [
                        ["min", "Mínimo"],
                        ["max", "Máximo"],
                        ["default", "Valor inicial"],
                      ] as const
                    ).map(([field, label]) => (
                      <label key={field}>
                        {label} de {parameter.label}
                        <input
                          type="number"
                          step="any"
                          required
                          value={
                            Number.isFinite(parameter[field])
                              ? parameter[field]
                              : ""
                          }
                          min={field === "default" ? parameter.min : undefined}
                          max={field === "default" ? parameter.max : undefined}
                          onChange={(event) =>
                            patch({ [field]: event.target.valueAsNumber })
                          }
                        />
                      </label>
                    ))}
                    <label>
                      Componente de {parameter.label}
                      <select
                        value={parameter.pointer.asset_id}
                        onChange={(event) =>
                          patch({
                            pointer: {
                              ...parameter.pointer,
                              asset_id: event.target.value,
                            },
                          })
                        }
                      >
                        {!assets.some(
                          (asset) => asset.id === parameter.pointer.asset_id,
                        ) ? (
                          <option value={parameter.pointer.asset_id}>
                            {parameter.pointer.asset_id} (no disponible)
                          </option>
                        ) : null}
                        {assets.map((asset) => (
                          <option key={asset.id} value={asset.id}>
                            {String(asset.name || asset.id)}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label>
                      Campo de {parameter.label}
                      <select
                        value={parameter.pointer.field}
                        onChange={(event) =>
                          patch({
                            pointer: {
                              ...parameter.pointer,
                              field: event.target.value,
                            },
                          })
                        }
                      >
                        {!fieldsFor(parameter.pointer.asset_id).some(
                          (item) => item.field === parameter.pointer.field,
                        ) ? (
                          <option value={parameter.pointer.field}>
                            {parameter.pointer.field} (no disponible)
                          </option>
                        ) : null}
                        {fieldsFor(parameter.pointer.asset_id).map(
                          ({ field }) => (
                            <option key={field} value={field}>
                              {field}
                            </option>
                          ),
                        )}
                      </select>
                    </label>
                    <button
                      type="button"
                      className="secondary-button"
                      onClick={() =>
                        setValue({
                          ...value,
                          parameters: value.parameters.filter(
                            (_, position) => position !== index,
                          ),
                        })
                      }
                    >
                      Quitar parámetro {index + 1}
                    </button>
                  </fieldset>
                );
              })}
            </section>
            <button
              type="button"
              className="secondary-button"
              aria-expanded={showResults}
              aria-controls="console-results-configuration"
              onClick={() => setShowResults(!showResults)}
            >
              Resultados
            </button>
            <div id="console-results-configuration" hidden={!showResults}>
              <ConsoleResultsConfiguration
                value={value.results}
                onChange={(results) => setValue({ ...value, results })}
              />
            </div>
            {value.groups.map((group) => (
              <fieldset key={group.id} className="console-group-fieldset">
                <legend>Grupo {group.label}</legend>
                {group.columns.map((column) => (
                  <ConsoleColumnFields
                    key={column.id}
                    group={group}
                    column={column}
                    catalog={catalog}
                    onChooseSignal={(signalKey) => {
                      const entry = signalCatalogEntry(catalog, signalKey);
                      patchColumn(group.id, column.id, (current) => ({
                        ...current,
                        signal: {
                          ...current.signal,
                          signal_key: signalKey,
                          entity_type:
                            entry?.entity_type || current.signal.entity_type,
                        },
                      }));
                    }}
                    onChangeLabel={(label) =>
                      patchColumn(group.id, column.id, (current) => ({
                        ...current,
                        label,
                      }))
                    }
                    onChangeEntityId={(entityId) =>
                      patchColumn(group.id, column.id, (current) => ({
                        ...current,
                        signal: { ...current.signal, entity_id: entityId },
                      }))
                    }
                  />
                ))}
              </fieldset>
            ))}
          </>
        )}
        <button type="submit" disabled={disabled}>
          Guardar configuracion
        </button>
      </fieldset>
    </form>
  );
}

function ConsoleColumnFields({
  group,
  column,
  catalog,
  onChooseSignal,
  onChangeLabel,
  onChangeEntityId,
}: {
  group: OperatorConsoleGroup;
  column: OperatorConsoleColumn;
  catalog: SignalCatalogEntry[];
  onChooseSignal: (signalKey: string) => void;
  onChangeLabel: (label: string) => void;
  onChangeEntityId: (entityId: string) => void;
}) {
  const signalKey = column.signal.signal_key;
  const entry = signalCatalogEntry(catalog, signalKey);
  const fieldId = `${group.id}-${column.id}`;

  return (
    <fieldset className="console-column-fieldset">
      <legend>Columna {column.id}</legend>
      <label htmlFor={`console-column-label-${fieldId}`}>Etiqueta</label>
      <input
        id={`console-column-label-${fieldId}`}
        type="text"
        value={column.label}
        onChange={(event) => onChangeLabel(event.target.value)}
      />
      <label htmlFor={`console-column-signal-${fieldId}`}>Senal canonica</label>
      <select
        id={`console-column-signal-${fieldId}`}
        value={signalKey}
        onChange={(event) => onChooseSignal(event.target.value)}
      >
        {entry ? null : (
          <option value={signalKey}>{signalKey} (fuera del catalogo)</option>
        )}
        {signalCatalogOptions(catalog).map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
      <label htmlFor={`console-column-entity-${fieldId}`}>Entidad</label>
      <input
        id={`console-column-entity-${fieldId}`}
        type="text"
        value={column.signal.entity_id}
        onChange={(event) => onChangeEntityId(event.target.value)}
      />
      <p className="source-note">
        {entry
          ? `Unidad ${entry.unit}. ${
              entry.nonnegative
                ? "No admite valores negativos."
                : "Admite valores negativos."
            }`
          : "Esta senal no esta declarada en el catalogo canonico."}
      </p>
    </fieldset>
  );
}

function ConsoleGroupChart({
  group,
  snapshot,
}: {
  group: ConsoleGroup;
  snapshot: ConsoleGroupValuesSnapshot | undefined;
}) {
  const chartRef = useRef<HTMLDivElement | null>(null);
  const [renderError, setRenderError] = useState("");
  const rows = useMemo(() => snapshot?.values.rows ?? [], [snapshot]);
  const columns = useMemo(
    () => snapshot?.values.columns ?? group.columns,
    [group.columns, snapshot],
  );
  const traces = useMemo<PlotlyTrace[]>(
    () =>
      columns.map((column) => ({
        x: rows.map((row) => row.timestamp),
        y: rows.map((row) => row.values[column.id] ?? null),
        name: column.label,
        type: "scatter",
        mode: "lines+markers",
        connectgaps: false,
        customdata: rows.map(() => column.unit || ""),
        hovertemplate: `%{x}<br>${column.label}: %{y} %{customdata}<extra></extra>`,
      })),
    [columns, rows],
  );

  useEffect(() => {
    const element = chartRef.current;
    if (!element) return undefined;
    let disposed = false;
    setRenderError("");

    void loadPlotly()
      .then((plotly) => {
        if (disposed) return;
        const units = [
          ...new Set(columns.map((column) => column.unit).filter(Boolean)),
        ];
        plotly.react(
          element,
          traces,
          {
            title: { text: group.label, x: 0.02 },
            autosize: true,
            height: 280,
            hovermode: "closest",
            margin: { l: 62, r: 24, t: 48, b: 72 },
            yaxis: { title: units.length === 1 ? (units[0] ?? "") : "" },
            legend: { orientation: "h", yanchor: "top", y: -0.25 },
            paper_bgcolor: "#ffffff",
            plot_bgcolor: "#ffffff",
            uirevision: group.id,
          },
          { responsive: true, displaylogo: false },
        );
      })
      .catch((error: Error) => {
        if (!disposed) setRenderError(error.message);
      });

    return () => {
      disposed = true;
      if (window.Plotly) window.Plotly.purge(element);
    };
  }, [columns, group, traces]);

  // The chart mirrors the table and never accepts an edit.
  return (
    <div className="console-group-chart">
      <div ref={chartRef} className="plotly-chart" />
      {renderError ? <p className="field-error">{renderError}</p> : null}
      <ul
        className="series-summary"
        data-testid={`console-group-series-${group.id}`}
      >
        {columns.map((column) => (
          <li key={column.id}>
            <strong>{column.label}</strong>
            {column.unit ? <span>{column.unit}</span> : null}
          </li>
        ))}
      </ul>
    </div>
  );
}

function columnHeaderLabel(label: string, unit: string | null): string {
  return unit ? `${label} (${unit})` : label;
}

type ConsoleNumberParseResult =
  | { ok: true; value: number }
  | { ok: false; message: string };

function parseConsoleNumber(text: string): ConsoleNumberParseResult {
  const trimmed = text.trim();
  const match = trimmed.match(/^([+-]?)([0-9.,]+)$/);
  if (!match) return { ok: false, message: "el valor debe ser numerico" };
  const sign = match[1] || "";
  const body = match[2];
  const dots = [...body.matchAll(/\./g)].map((entry) => entry.index);
  const commas = [...body.matchAll(/,/g)].map((entry) => entry.index);
  let normalized: string;

  if (dots.length && commas.length) {
    const decimalSeparator =
      dots[dots.length - 1] > commas[commas.length - 1] ? "." : ",";
    const thousandsSeparator = decimalSeparator === "." ? "," : ".";
    const decimalIndex = body.lastIndexOf(decimalSeparator);
    const integerText = body.slice(0, decimalIndex);
    const fractionText = body.slice(decimalIndex + 1);
    const groups = integerText.split(thousandsSeparator);
    if (
      !fractionText.match(/^\d+$/) ||
      !groups[0]?.match(/^\d{1,3}$/) ||
      groups.slice(1).some((group) => !group.match(/^\d{3}$/)) ||
      integerText.includes(decimalSeparator)
    ) {
      return { ok: false, message: "el formato numerico no es valido" };
    }
    normalized = `${groups.join("")}.${fractionText}`;
  } else if (dots.length + commas.length > 1) {
    const separator = dots.length ? "." : ",";
    const groups = body.split(separator);
    if (
      !groups[0]?.match(/^\d{1,3}$/) ||
      groups.slice(1).some((group) => !group.match(/^\d{3}$/))
    ) {
      return { ok: false, message: "el formato numerico no es valido" };
    }
    normalized = groups.join("");
  } else if (dots.length + commas.length === 1) {
    const separator = dots.length ? "." : ",";
    const [integerText, fractionText] = body.split(separator);
    if (!integerText.match(/^\d+$/) || !fractionText?.match(/^\d+$/)) {
      return { ok: false, message: "el formato numerico no es valido" };
    }
    if (
      fractionText.length === 3 &&
      integerText !== "0" &&
      integerText.length <= 3
    ) {
      return { ok: false, message: "el formato numerico es ambiguo" };
    }
    normalized = `${integerText}.${fractionText}`;
  } else {
    normalized = body;
  }

  const value = Number(`${sign}${normalized}`);
  return Number.isFinite(value)
    ? { ok: true, value }
    : { ok: false, message: "el valor debe ser finito" };
}

interface ConsolePasteCellError {
  group_id: string;
  column_id: string;
  row_index: number;
  message: string;
}

const CONSOLE_TABLE_ROW_HEIGHT = 42;
const CONSOLE_TABLE_WINDOW_ROWS = 80;
const CONSOLE_TABLE_VIRTUALIZE_AFTER = 200;

export function ConsoleGroupEditor({
  consoleId,
  group,
  range,
  lockedBy,
  onDirtyChange,
}: {
  consoleId: number;
  group: ConsoleGroup;
  range: { start: string; end: string };
  lockedBy: string | null;
  onDirtyChange: (dirty: boolean) => void;
}) {
  const queryClient = useQueryClient();
  const [granularity, setGranularity] = useState(group.granularities[0] || "");
  const [edits, setEdits] = useState<Record<string, string>>({});
  const [lease, setLease] = useState<ConsoleLease | null>(null);
  const [saveError, setSaveError] = useState<ConsoleSaveError | Error | null>(
    null,
  );
  const [pasteErrors, setPasteErrors] = useState<ConsolePasteCellError[]>([]);
  const [pasteWarnings, setPasteWarnings] = useState<string[]>([]);
  const [reviewOpen, setReviewOpen] = useState(false);
  const [virtualStart, setVirtualStart] = useState(0);
  const enabled = Boolean(range.start && range.end && granularity);
  const queryKey = consoleGroupValuesQueryKey(
    consoleId,
    group.id,
    range.start,
    range.end,
    granularity,
  );
  const values = useQuery({
    queryKey,
    queryFn: ({ signal }) =>
      getConsoleGroupValues(
        consoleId,
        group.id,
        { start: range.start, end: range.end, granularity },
        signal,
      ),
    enabled,
    retry: false,
  });
  const history = useQuery({
    queryKey: consoleGroupHistoryQueryKey(consoleId, group.id),
    queryFn: ({ signal }) =>
      getConsoleGroupHistory(consoleId, group.id, signal),
    retry: false,
  });

  const rows = values.data?.values.rows ?? [];
  const columns = values.data?.values.columns ?? group.columns;
  const virtualized = rows.length > CONSOLE_TABLE_VIRTUALIZE_AFTER;
  const visibleStart = virtualized
    ? Math.min(
        virtualStart,
        Math.max(0, rows.length - CONSOLE_TABLE_WINDOW_ROWS),
      )
    : 0;
  const visibleRows = virtualized
    ? rows.slice(visibleStart, visibleStart + CONSOLE_TABLE_WINDOW_ROWS)
    : rows;
  const hiddenRowsAfter = Math.max(
    0,
    rows.length - visibleStart - visibleRows.length,
  );
  const dirtyCells = Object.entries(edits)
    .map(([key, text]) => {
      const [columnId, rawIndex] = key.split("|");
      return {
        column_id: columnId,
        row_index: Number(rawIndex),
        value: Number(text),
        text,
      };
    })
    .filter(
      (cell) =>
        cell.text !== "" &&
        Number.isFinite(cell.value) &&
        cell.value !== rows[cell.row_index]?.values[cell.column_id],
    );
  const dirty = Object.keys(edits).length > 0;

  const takeLease = useMutation({
    mutationFn: () => acquireConsoleGroupLease(consoleId, group.id),
    onSuccess: (acquired) => {
      setSaveError(null);
      setLease(acquired);
      void heartbeatConsoleGroupLease(consoleId, group.id, acquired.token)
        .then((renewed) =>
          setLease((current) =>
            current?.token === acquired.token ? renewed : current,
          ),
        )
        .catch((error: Error) => {
          setLease((current) =>
            current?.token === acquired.token ? null : current,
          );
          setSaveError(error);
        });
    },
    onError: (error: Error) => setSaveError(error),
  });
  const dropLease = useMutation({
    mutationFn: async () => {
      if (lease)
        await releaseConsoleGroupLease(consoleId, group.id, lease.token);
    },
    onSuccess: () => {
      setLease(null);
      setEdits({});
      setPasteErrors([]);
      setPasteWarnings([]);
      setReviewOpen(false);
    },
  });
  const save = useMutation({
    mutationFn: () =>
      saveConsoleGroupValues(
        consoleId,
        group.id,
        {
          range_start: range.start,
          range_end: range.end,
          granularity,
          lease_token: lease?.token || "",
          note: "",
          cells: dirtyCells.map((cell) => ({
            column_id: cell.column_id,
            row_index: cell.row_index,
            value: cell.value,
          })),
        },
        values.data?.etag || "",
      ),
    onSuccess: (saved) => {
      setSaveError(null);
      setEdits({});
      setPasteErrors([]);
      setPasteWarnings([]);
      setReviewOpen(false);
      queryClient.setQueryData(queryKey, saved);
      void queryClient.invalidateQueries({
        queryKey: consoleGroupHistoryQueryKey(consoleId, group.id),
      });
    },
    onError: (error: Error) => setSaveError(error),
  });
  const undo = useMutation({
    mutationFn: () =>
      undoConsoleGroupSave(
        consoleId,
        group.id,
        lease?.token || "",
        values.data?.etag || "",
      ),
    onSuccess: (restored) => {
      setSaveError(null);
      queryClient.setQueryData(queryKey, restored);
      void queryClient.invalidateQueries({
        queryKey: consoleGroupHistoryQueryKey(consoleId, group.id),
      });
    },
    onError: (error: Error) => setSaveError(error),
  });

  const activeLeaseToken = lease?.token;
  useEffect(() => {
    if (!activeLeaseToken) return undefined;
    const timer = window.setInterval(() => {
      void heartbeatConsoleGroupLease(consoleId, group.id, activeLeaseToken)
        .then((renewed) =>
          setLease((current) =>
            current?.token === activeLeaseToken ? renewed : current,
          ),
        )
        .catch((error: Error) => {
          setLease((current) =>
            current?.token === activeLeaseToken ? null : current,
          );
          setSaveError(error);
        });
    }, 120_000);
    return () => window.clearInterval(timer);
  }, [activeLeaseToken, consoleId, group.id]);

  useEffect(() => {
    onDirtyChange(dirty || save.isPending);
  }, [dirty, onDirtyChange, save.isPending]);

  const editing = lease !== null && lockedBy === null;
  const cellsInError =
    saveError instanceof ConsoleSaveError ? saveError.cells : [];

  function cellKey(columnId: string, rowIndex: number): string {
    return `${columnId}|${rowIndex}`;
  }

  function cellText(columnId: string, rowIndex: number): string {
    const edited = edits[cellKey(columnId, rowIndex)];
    if (edited !== undefined) return edited;
    const value = rows[rowIndex]?.values[columnId];
    return value === null || value === undefined ? "" : String(value);
  }

  function pasteCells(
    event: ClipboardEvent<HTMLInputElement>,
    anchorColumnId: string,
    anchorRowIndex: number,
  ) {
    event.preventDefault();
    const anchorColumn = columns.findIndex(
      (column) => column.id === anchorColumnId,
    );
    const anchorRow = rows.findIndex((row) => row.index === anchorRowIndex);
    if (anchorColumn < 0 || anchorRow < 0) return;
    const matrix = event.clipboardData
      .getData("text")
      .replace(/\r\n?/g, "\n")
      .split("\n")
      .map((line) => line.split("\t"));
    while (
      matrix.length > 1 &&
      matrix[matrix.length - 1].every((cell) => cell === "")
    ) {
      matrix.pop();
    }
    const warnings: string[] = [];
    let sourceRows = matrix;
    if (matrix[0]?.every((cell) => !/\d/.test(cell)) && matrix.length > 1) {
      warnings.push("Se omitio la primera fila porque parecia un encabezado.");
      sourceRows = matrix.slice(1);
    }
    const prepared: Record<string, string> = {};
    const failures: ConsolePasteCellError[] = [];
    const lockedColumns = new Set<string>();
    let overflow = false;
    sourceRows.forEach((sourceRow, rowOffset) => {
      const targetRow = rows[anchorRow + rowOffset];
      if (!targetRow) {
        overflow = true;
        return;
      }
      sourceRow.forEach((text, columnOffset) => {
        const targetColumn = columns[anchorColumn + columnOffset];
        if (!targetColumn) {
          overflow = true;
          return;
        }
        if (!targetColumn.editable) {
          lockedColumns.add(targetColumn.label);
          return;
        }
        const parsed = parseConsoleNumber(text);
        if (!parsed.ok) {
          failures.push({
            group_id: group.id,
            column_id: targetColumn.id,
            row_index: targetRow.index,
            message: parsed.message,
          });
          return;
        }
        prepared[cellKey(targetColumn.id, targetRow.index)] = String(
          parsed.value,
        );
      });
    });
    lockedColumns.forEach((label) =>
      warnings.push(`${label}: columna bloqueada omitida durante el pegado.`),
    );
    if (overflow) {
      warnings.push(
        "El excedente fue truncado al tramo configurado; no se crearon periodos.",
      );
    }
    setPasteWarnings(warnings);
    if (failures.length) {
      setPasteErrors(failures);
      return;
    }
    setPasteErrors([]);
    setEdits((current) => ({ ...current, ...prepared }));
  }

  return (
    <section
      className="content-panel console-group"
      aria-labelledby={`console-group-${group.id}`}
    >
      <h2 id={`console-group-${group.id}`} tabIndex={-1}>
        {group.label}
      </h2>
      {dirty && !lease && saveError ? (
        <p role="status">
          Se perdió la sesión de edición. Tus cambios siguen aquí; vuelve a
          obtener la edición antes de guardar.
        </p>
      ) : null}
      {lockedBy ? (
        <p className="source-note">
          Solo lectura: {lockedBy} tiene la edicion de este grupo.
        </p>
      ) : null}
      <div className="inline-actions">
        <label htmlFor={`console-granularity-${group.id}`}>Granularidad</label>
        <select
          id={`console-granularity-${group.id}`}
          value={granularity}
          onChange={(event) => {
            setGranularity(event.target.value);
            setVirtualStart(0);
          }}
          disabled={editing}
        >
          {group.granularities.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </select>
        {lockedBy ? null : editing ? (
          <>
            <button
              type="button"
              disabled={
                dirtyCells.length === 0 ||
                pasteErrors.length > 0 ||
                save.isPending
              }
              onClick={() => save.mutate()}
            >
              Guardar valores
            </button>
            <button
              type="button"
              className="secondary-button"
              disabled={dirtyCells.length === 0 || save.isPending}
              onClick={() => setReviewOpen(true)}
            >
              Revisar cambios
            </button>
            <button
              type="button"
              className="secondary-button"
              disabled={save.isPending}
              onClick={() => dropLease.mutate()}
            >
              Liberar edicion
            </button>
          </>
        ) : (
          <button
            type="button"
            disabled={takeLease.isPending || values.isPending}
            onClick={() => takeLease.mutate()}
          >
            Editar valores
          </button>
        )}
      </div>
      {values.isError ? <p role="alert">{errorMessage(values.error)}</p> : null}
      {saveError ? (
        <div role="alert">
          <p>{errorMessage(saveError)}</p>
          {cellsInError.length ? (
            <ul>
              {cellsInError.map((cell) => (
                <li key={`${cell.column_id}-${cell.row_index}`}>
                  {columns.find((column) => column.id === cell.column_id)
                    ?.label || cell.column_id}
                  {cell.row_index === null ? "" : ` fila ${cell.row_index + 1}`}
                  : {cell.message}
                </li>
              ))}
            </ul>
          ) : null}
          {saveError instanceof ConsoleSaveError &&
          saveError.totalCells > saveError.shownCells ? (
            <p className="source-note">
              Se muestran {saveError.shownCells} de {saveError.totalCells}{" "}
              celdas con error.
            </p>
          ) : null}
        </div>
      ) : null}
      {pasteErrors.length ? (
        <div role="alert">
          <p>El pegado tiene celdas invalidas.</p>
          <ul>
            {pasteErrors.slice(0, 100).map((cell) => (
              <li key={`${cell.column_id}-${cell.row_index}`}>
                {columns.find((column) => column.id === cell.column_id)
                  ?.label || cell.column_id}
                {` fila ${cell.row_index + 1}`}: {cell.message}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      {pasteWarnings.length ? (
        <div className="console-paste-warning" role="status">
          {pasteWarnings.map((warning) => (
            <p key={warning}>{warning}</p>
          ))}
        </div>
      ) : null}
      {reviewOpen ? (
        <div
          className="console-change-review"
          role="dialog"
          aria-label="Revision de cambios"
        >
          <h3>Revision de cambios</h3>
          <table>
            <thead>
              <tr>
                <th scope="col">Columna</th>
                <th scope="col">Periodo</th>
                <th scope="col">Anterior</th>
                <th scope="col">Nuevo</th>
              </tr>
            </thead>
            <tbody>
              {dirtyCells.map((cell) => {
                const row = rows.find(
                  (candidate) => candidate.index === cell.row_index,
                );
                return (
                  <tr key={`${cell.column_id}-${cell.row_index}`}>
                    <th scope="row">
                      {columns.find((column) => column.id === cell.column_id)
                        ?.label || cell.column_id}
                    </th>
                    <td>{row?.timestamp || cell.row_index + 1}</td>
                    <td>{row?.values[cell.column_id] ?? ""}</td>
                    <td>{cell.value}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          <button
            type="button"
            className="secondary-button"
            onClick={() => setReviewOpen(false)}
          >
            Cerrar revision
          </button>
        </div>
      ) : null}
      {values.isPending ? <p role="status">Cargando valores</p> : null}
      {values.data ? (
        <>
          <div
            className="console-group-table-viewport"
            data-testid={`console-group-table-viewport-${group.id}`}
            onScroll={(event) => {
              if (!virtualized) return;
              setVirtualStart(
                Math.min(
                  Math.max(0, rows.length - CONSOLE_TABLE_WINDOW_ROWS),
                  Math.floor(
                    event.currentTarget.scrollTop / CONSOLE_TABLE_ROW_HEIGHT,
                  ),
                ),
              );
            }}
          >
            <table className="console-group-table" aria-label={group.label}>
              <caption className="source-note">
                {values.data.values.range.start} a{" "}
                {values.data.values.range.end}
              </caption>
              <thead>
                <tr>
                  <th scope="col">Periodo</th>
                  {columns.map((column) => (
                    <th key={column.id} scope="col">
                      {columnHeaderLabel(column.label, column.unit)}
                      {column.editable ? "" : " 🔒"}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {visibleStart > 0 ? (
                  <tr aria-hidden="true">
                    <td
                      colSpan={columns.length + 1}
                      style={{
                        height: visibleStart * CONSOLE_TABLE_ROW_HEIGHT,
                        padding: 0,
                        border: 0,
                      }}
                    />
                  </tr>
                ) : null}
                {visibleRows.map((row) => (
                  <tr key={row.index}>
                    <th scope="row">{row.timestamp}</th>
                    {columns.map((column) => (
                      <td key={column.id}>
                        {editing && column.editable ? (
                          <input
                            type="number"
                            step="any"
                            min={column.nonnegative ? 0 : undefined}
                            aria-label={`${column.label} ${row.timestamp}`}
                            value={cellText(column.id, row.index)}
                            onPaste={(event) =>
                              pasteCells(event, column.id, row.index)
                            }
                            onChange={(event) => {
                              setPasteErrors([]);
                              setEdits((current) => ({
                                ...current,
                                [cellKey(column.id, row.index)]:
                                  event.target.value,
                              }));
                            }}
                          />
                        ) : (
                          cellText(column.id, row.index)
                        )}
                      </td>
                    ))}
                  </tr>
                ))}
                {hiddenRowsAfter > 0 ? (
                  <tr aria-hidden="true">
                    <td
                      colSpan={columns.length + 1}
                      style={{
                        height: hiddenRowsAfter * CONSOLE_TABLE_ROW_HEIGHT,
                        padding: 0,
                        border: 0,
                      }}
                    />
                  </tr>
                ) : null}
              </tbody>
            </table>
          </div>
          <ConsoleGroupChart group={group} snapshot={values.data} />
        </>
      ) : null}
      <section
        className="console-change-history"
        aria-labelledby={`console-change-history-${group.id}`}
      >
        <h3 id={`console-change-history-${group.id}`}>
          Historial de cambios de {group.label}
        </h3>
        {history.isPending ? <p role="status">Cargando historial</p> : null}
        {history.isError ? (
          <p role="alert">{errorMessage(history.error)}</p>
        ) : null}
        {history.data?.length === 0 ? (
          <p className="empty-state">Todavia no hay cambios guardados.</p>
        ) : null}
        {history.data?.length ? (
          <ol className="resource-list">
            {history.data.map((entry: ConsoleGroupHistoryEntry) => (
              <li key={entry.id}>
                <p>
                  <strong>{entry.actor || "Usuario interno"}</strong> ·{" "}
                  {entry.date}
                </p>
                <p className="source-note">
                  {entry.range.start} a {entry.range.end} · {entry.cell_count}{" "}
                  {entry.cell_count === 1 ? "celda" : "celdas"}
                </p>
                {entry.note ? <p>{entry.note}</p> : null}
                <details>
                  <summary>Ver comparacion</summary>
                  <table>
                    <thead>
                      <tr>
                        <th scope="col">Columna</th>
                        <th scope="col">Fila</th>
                        <th scope="col">Anterior</th>
                        <th scope="col">Nuevo</th>
                      </tr>
                    </thead>
                    <tbody>
                      {entry.comparison.map((change) => (
                        <tr key={`${change.column_id}-${change.row_index}`}>
                          <th scope="row">
                            {columns.find(
                              (column) => column.id === change.column_id,
                            )?.label || change.column_id}
                          </th>
                          <td>{change.row_index + 1}</td>
                          <td>{change.before ?? ""}</td>
                          <td>{change.after ?? ""}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </details>
                {entry.can_undo && editing ? (
                  <button
                    type="button"
                    className="secondary-button"
                    disabled={dirty || save.isPending || undo.isPending}
                    onClick={() => undo.mutate()}
                  >
                    Deshacer
                  </button>
                ) : null}
              </li>
            ))}
          </ol>
        ) : null}
      </section>
    </section>
  );
}

export function ConsoleListView() {
  const consoles = useQuery({
    queryKey: consoleShellListQueryKey,
    queryFn: ({ signal }) => listOperableConsoles(signal),
    retry: false,
  });

  if (consoles.isPending) return <p role="status">Cargando consolas</p>;
  if (consoles.isError) {
    return (
      <section className="content-panel">
        <h1>No se pudo cargar</h1>
        <p role="alert">{errorMessage(consoles.error)}</p>
      </section>
    );
  }

  return (
    <section className="content-panel" aria-labelledby="console-root-list">
      <h1 id="console-root-list">Mis consolas</h1>
      {consoles.data.length === 0 ? (
        <p className="empty-state">No tienes consolas disponibles.</p>
      ) : (
        <ul className="resource-list">
          {consoles.data.map((entry) => (
            <li key={entry.console.id}>
              <Link to={`/console/${entry.console.id}`}>
                {entry.console.name}
              </Link>
              <p>{entry.console.description}</p>
              <p className="source-note">{entry.project.name}</p>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

// The console root names the plan being operated, never the analyst brand.
export function ConsoleRootPlanIdentity() {
  const match = useMatch("/console/:consoleId");
  const consoleId = numericParam(match?.params.consoleId);
  const shell = useQuery({
    queryKey: consoleShellQueryKey(consoleId || 0),
    queryFn: ({ signal }) => getConsoleShell(consoleId || 0, signal),
    enabled: consoleId !== null,
    retry: false,
  });
  if (consoleId !== null && shell.data) {
    return <span className="console-root-plan">{shell.data.console.name}</span>;
  }
  return (
    <Link className="console-root-link" to="/console">
      Mis consolas
    </Link>
  );
}

export function ConsoleShellView() {
  const params = useParams();
  const consoleId = numericParam(params.consoleId);
  const queryClient = useQueryClient();
  const [parameterValues, setParameterValues] = useState<
    Record<string, string>
  >({});
  const [selectedStart, setSelectedStart] = useState<string | null>(null);
  const [selectedEnd, setSelectedEnd] = useState<string | null>(null);
  const [activeRunId, setActiveRunId] = useState<number | null>(null);
  const [comparisonPicks, setComparisonPicks] = useState<number[]>([]);
  const [comparedRuns, setComparedRuns] = useState<[number, number] | null>(
    null,
  );
  const [actionError, setActionError] = useState("");
  const [dirtyGroups, setDirtyGroups] = useState<Record<string, boolean>>({});
  const shell = useQuery({
    queryKey: consoleShellQueryKey(consoleId || 0),
    queryFn: ({ signal }) => getConsoleShell(consoleId || 0, signal),
    enabled: consoleId !== null,
    retry: false,
  });
  const seriesOptions = useQuery({
    queryKey: consoleSeriesOptionsQueryKey(consoleId || 0),
    queryFn: ({ signal }) => getConsoleSeriesOptions(consoleId || 0, signal),
    enabled: consoleId !== null && Boolean(shell.data?.groups?.length),
    retry: false,
  });
  const history = useQuery({
    queryKey: consoleRunsQueryKey(consoleId || 0),
    queryFn: ({ signal }) => listConsoleRuns(consoleId || 0, signal),
    enabled: consoleId !== null,
    retry: false,
  });
  const comparison = useQuery({
    queryKey: consoleComparisonQueryKey(
      consoleId || 0,
      comparedRuns?.[0] || 0,
      comparedRuns?.[1] || 0,
    ),
    queryFn: ({ signal }) =>
      getConsoleRunComparison(
        consoleId || 0,
        (comparedRuns || [0, 0])[0],
        (comparedRuns || [0, 0])[1],
        signal,
      ),
    enabled: consoleId !== null && comparedRuns !== null,
    retry: false,
  });
  const runDetail = useQuery({
    queryKey: ["console-run", consoleId || 0, activeRunId || 0] as const,
    queryFn: ({ signal }) =>
      getConsoleRun(consoleId || 0, activeRunId || 0, signal),
    enabled: consoleId !== null && activeRunId !== null,
    retry: false,
    refetchInterval: (query) => {
      const state = query.state.data?.run.state;
      return state === "en_espera" || state === "ejecutando" ? 1000 : false;
    },
  });

  const saveParameters = useMutation({
    mutationFn: () =>
      saveConsoleParameters(
        consoleId || 0,
        (shell.data?.parameters ?? []).map((parameter) => ({
          id: parameter.id,
          value: Number(parameterValues[parameter.id] ?? parameter.value ?? ""),
        })),
      ),
    onSuccess: (saved) => {
      setActionError("");
      queryClient.setQueryData(
        consoleShellQueryKey(consoleId || 0),
        shell.data ? { ...shell.data, parameters: saved } : shell.data,
      );
      setParameterValues({});
    },
    onError: (error) => setActionError(errorMessage(error)),
  });
  const selectSeriesSource = useMutation({
    mutationFn: (selection: {
      group_id: string;
      column_id: string;
      source_option_id: string;
    }) => saveConsoleSeriesSelections(consoleId || 0, [selection]),
    onSuccess: async (saved) => {
      setActionError("");
      queryClient.setQueryData(
        consoleSeriesOptionsQueryKey(consoleId || 0),
        saved,
      );
      await Promise.all([
        queryClient.invalidateQueries({
          queryKey: ["console-group-values", consoleId || 0],
        }),
        queryClient.invalidateQueries({
          queryKey: consoleShellQueryKey(consoleId || 0),
        }),
      ]);
    },
    onError: (error) => setActionError(errorMessage(error)),
  });
  const requestReview = useMutation({
    mutationFn: () => requestConsoleReview(consoleId || 0),
    onSuccess: (gate) => {
      setActionError("");
      queryClient.setQueryData(
        consoleShellQueryKey(consoleId || 0),
        shell.data ? { ...shell.data, run_gate: gate } : shell.data,
      );
    },
    onError: (error) => setActionError(errorMessage(error)),
  });
  const enqueueRun = useMutation({
    mutationFn: () =>
      createConsoleRun(consoleId || 0, {
        range_start: rangeRequestValue(
          selectedStart,
          shell.data?.period?.selected_start,
        ),
        range_end: rangeRequestValue(
          selectedEnd,
          shell.data?.period?.selected_end,
        ),
      }),
    onSuccess: (run) => {
      setActionError("");
      setActiveRunId(run.id);
      queryClient.setQueryData<ConsoleRunEntry[]>(
        consoleRunsQueryKey(consoleId || 0),
        (current) => [
          run,
          ...(current ?? []).filter((item) => item.id !== run.id),
        ],
      );
    },
    onError: (error) => setActionError(errorMessage(error)),
  });

  if (consoleId === null) {
    return (
      <section className="content-panel">
        <h1>No encontrado</h1>
        <p>La consola solicitada no existe.</p>
      </section>
    );
  }
  if (shell.isPending) return <p role="status">Cargando consola</p>;
  if (
    shell.isError &&
    (!shell.data ||
      (shell.error instanceof ApiError &&
        [401, 403, 404].includes(shell.error.status)))
  ) {
    return (
      <section className="content-panel">
        <h1>No encontrado</h1>
        <p role="alert">{errorMessage(shell.error)}</p>
        <button type="button" onClick={() => void shell.refetch()}>
          Actualizar preparación
        </button>
      </section>
    );
  }

  const {
    console: identity,
    internal_test: internalTest,
    period,
    parameters = [],
    groups = [],
    run_gate: runGate,
  } = shell.data!;
  const effectiveSelectedStart = selectedStart ?? period?.selected_start ?? "";
  const effectiveSelectedEnd = selectedEnd ?? period?.selected_end ?? "";
  const displayedSelectedStart = datetimeLocalInputValue(
    effectiveSelectedStart,
  );
  const displayedSelectedEnd = datetimeLocalInputValue(effectiveSelectedEnd);
  const parameterValuesValid = parameters.every((parameter) => {
    const rawValue = parameterValues[parameter.id] ?? parameter.value ?? "";
    const value = Number(rawValue);
    return (
      rawValue !== "" &&
      Number.isFinite(value) &&
      value >= parameter.min &&
      value <= parameter.max
    );
  });
  const parametersDirty = parameters.some(
    (parameter) =>
      parameterValues[parameter.id] !== undefined &&
      Number(parameterValues[parameter.id]) !== parameter.value,
  );
  const reviewableBlock =
    runGate?.reason === "dependencia_movida" ||
    runGate?.reason === "campo_no_disponible";
  // Editing and running stay two operations: a dirty cell or a save in flight
  // closes the run gate until the values are committed.
  const seriesDirty = Object.values(dirtyGroups).some(Boolean);
  const canRun = Boolean(
    runGate?.can_run &&
    !shell.isError &&
    !shell.isFetching &&
    !parametersDirty &&
    !seriesDirty &&
    parameterValuesValid &&
    effectiveSelectedStart &&
    effectiveSelectedEnd &&
    !saveParameters.isPending &&
    !selectSeriesSource.isPending &&
    !enqueueRun.isPending,
  );
  const visibleRun = runDetail.data?.run || history.data?.[0];
  const runLabels: Record<ConsoleRunEntry["state"], string> = {
    en_espera: "En espera",
    ejecutando: "Ejecutando",
    lista: "Lista",
    fallida: "Fallida",
  };

  return (
    <div className="console-experience">
      {internalTest ? (
        <p
          className="internal-test-strip"
          role="status"
          aria-label="Prueba interna"
        >
          Estas probando esta consola como {internalTest.tester}.{" "}
          <Link to={internalTest.return_path}>Volver al workspace</Link>
        </p>
      ) : null}
      <section className="content-panel" aria-labelledby="console-shell-title">
        <h1 id="console-shell-title">{identity.name}</h1>
        <p>{identity.description}</p>
        <p className="source-note">
          Preparado por {identity.prepared_by || "el equipo interno"}
        </p>
        <p className="source-note">Actualizado {identity.updated_at}</p>
      </section>
      <section
        className="content-panel"
        aria-labelledby="console-preparation-title"
      >
        <h2 id="console-preparation-title">Preparación de la ejecución</h2>
        {shell.isError ? (
          <p role="alert">
            No se pudo actualizar la preparación. Tus cambios siguen aquí.
            Actualiza antes de ejecutar.
          </p>
        ) : null}
        <button
          type="button"
          className="secondary-button"
          disabled={
            shell.isFetching ||
            saveParameters.isPending ||
            selectSeriesSource.isPending ||
            enqueueRun.isPending
          }
          onClick={() => void shell.refetch()}
        >
          Actualizar preparación
        </button>
        <p>
          Período:{" "}
          {rangeRequestValue(selectedStart, period?.selected_start) ||
            "Inicio pendiente"}{" "}
          →{" "}
          {rangeRequestValue(selectedEnd, period?.selected_end) ||
            "Fin pendiente"}
          . Inicio incluido; fin excluido.
        </p>
        <p role="status">
          {enqueueRun.isPending
            ? "Enviando ejecución"
            : saveParameters.isPending
              ? "Guardando parámetros"
              : canRun
                ? "Preparado para ejecutar"
                : parametersDirty || seriesDirty
                  ? "Hay cambios sin guardar"
                  : runGate?.can_run === false
                    ? "La ejecución está bloqueada"
                    : "Revisa la preparación antes de ejecutar"}
        </p>
        <ul className="console-preparation-links">
          {parameters
            .filter((parameter) => {
              const raw =
                parameterValues[parameter.id] ?? parameter.value ?? "";
              const value = Number(raw);
              return (
                raw === "" ||
                !Number.isFinite(value) ||
                value < parameter.min ||
                value > parameter.max ||
                value !== parameter.value
              );
            })
            .map((parameter) => (
              <li key={parameter.id}>
                <a
                  href={`#console-parameter-${parameter.id}`}
                  onClick={(event) => {
                    event.preventDefault();
                    window.document
                      .getElementById(`console-parameter-${parameter.id}`)
                      ?.focus();
                  }}
                >
                  Guardar cambios de {parameter.label}
                </a>
                {parameter.unit ? ` (${parameter.unit})` : ""}
              </li>
            ))}
          {groups
            .filter((group) => dirtyGroups[group.id])
            .map((group) => (
              <li key={group.id}>
                <a
                  href={`#console-group-${group.id}`}
                  onClick={(event) => {
                    event.preventDefault();
                    window.document
                      .getElementById(`console-group-${group.id}`)
                      ?.focus();
                  }}
                >
                  Guardar cambios de {group.label}
                </a>
              </li>
            ))}
          {!effectiveSelectedStart || !effectiveSelectedEnd ? (
            <li>
              <a
                href="#console-period-start"
                onClick={(event) => {
                  event.preventDefault();
                  window.document
                    .getElementById("console-period-start")
                    ?.focus();
                }}
              >
                Completar período
              </a>
            </li>
          ) : null}
          {!runGate || !runGate.can_run ? (
            <li>
              <a
                href="#console-parameters-title"
                onClick={(event) => {
                  event.preventDefault();
                  window.document
                    .getElementById("console-parameters-title")
                    ?.focus();
                }}
              >
                Consultar bloqueo y acciones disponibles
              </a>
            </li>
          ) : null}
        </ul>
        {parametersDirty && seriesDirty ? (
          <p>
            Los parámetros y cada grupo se guardan por separado. Completa los
            guardados pendientes antes de ejecutar.
          </p>
        ) : null}
      </section>
      <section
        className="content-panel"
        aria-labelledby="console-parameters-title"
      >
        <h2 id="console-parameters-title" tabIndex={-1}>
          Periodo y parametros
        </h2>
        {actionError ? <p role="alert">{actionError}</p> : null}
        {runGate && !runGate.can_run ? (
          <p role="alert">
            {runGate.message}
            {runGate.contact ? ` Contacta a ${runGate.contact}.` : ""}
          </p>
        ) : null}
        {/* Only an engineering block is worth a review request: another
            operator's edit lock clears on its own. */}
        {reviewableBlock ? (
          runGate?.review_requested_at ? (
            <p className="source-note">
              Revision solicitada {runGate.review_requested_at}
            </p>
          ) : (
            <button
              type="button"
              className="secondary-button"
              disabled={requestReview.isPending}
              onClick={() => requestReview.mutate()}
            >
              Solicitar revision
            </button>
          )
        ) : null}
        {period ? (
          <div className="console-period-fields">
            <label htmlFor="console-period-start">Inicio</label>
            <input
              id="console-period-start"
              type="datetime-local"
              value={displayedSelectedStart}
              min={datetimeLocalInputValue(period.available_start) || undefined}
              max={datetimeLocalInputValue(period.available_end) || undefined}
              onChange={(event) => setSelectedStart(event.target.value)}
            />
            <label htmlFor="console-period-end">Fin</label>
            <input
              id="console-period-end"
              type="datetime-local"
              value={displayedSelectedEnd}
              min={datetimeLocalInputValue(period.available_start) || undefined}
              max={datetimeLocalInputValue(period.available_end) || undefined}
              onChange={(event) => setSelectedEnd(event.target.value)}
            />
          </div>
        ) : null}
        <div className="console-parameter-grid">
          {parameters.map((parameter) => (
            <label
              key={parameter.id}
              htmlFor={`console-parameter-${parameter.id}`}
            >
              {parameter.label}
              {parameter.unit ? ` (${parameter.unit})` : ""}
              <input
                id={`console-parameter-${parameter.id}`}
                type="number"
                step="any"
                min={parameter.min}
                max={parameter.max}
                value={
                  parameterValues[parameter.id] ??
                  (parameter.value === null ? "" : String(parameter.value))
                }
                onChange={(event) =>
                  setParameterValues((current) => ({
                    ...current,
                    [parameter.id]: event.target.value,
                  }))
                }
              />
            </label>
          ))}
        </div>
        <div className="inline-actions">
          <button
            type="button"
            disabled={
              !parametersDirty ||
              !parameterValuesValid ||
              saveParameters.isPending
            }
            onClick={() => saveParameters.mutate()}
          >
            Guardar parametros
          </button>
          <button
            type="button"
            disabled={!canRun}
            onClick={() => enqueueRun.mutate()}
          >
            Ejecutar
          </button>
        </div>
        {parametersDirty || seriesDirty ? (
          <p className="source-note">Guarda los cambios antes de ejecutar.</p>
        ) : null}
      </section>
      {seriesOptions.data?.selections.length ? (
        <section
          className="content-panel"
          aria-labelledby="console-series-sources-title"
        >
          <h2 id="console-series-sources-title">Fuentes de series</h2>
          <div className="console-parameter-grid">
            {seriesOptions.data.selections.map((selection) => {
              const group = groups.find(
                (entry) => entry.id === selection.group_id,
              );
              const column = group?.columns.find(
                (entry) => entry.id === selection.column_id,
              );
              const label = column?.label || selection.column_id;
              const inputId = `console-source-${selection.group_id}-${selection.column_id}`;
              return (
                <label key={inputId} htmlFor={inputId}>
                  Fuente de {label}
                  <select
                    id={inputId}
                    value={selection.selected_source_option_id || ""}
                    disabled={
                      seriesDirty ||
                      selectSeriesSource.isPending ||
                      selection.selected_source_option_id === null
                    }
                    onChange={(event) =>
                      selectSeriesSource.mutate({
                        group_id: selection.group_id,
                        column_id: selection.column_id,
                        source_option_id: event.target.value,
                      })
                    }
                  >
                    {selection.options.map((option) => (
                      <option key={option.id} value={option.id}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </label>
              );
            })}
          </div>
        </section>
      ) : null}
      {groups.map((group) => (
        <ConsoleGroupEditor
          key={group.id}
          consoleId={consoleId}
          group={group}
          range={{
            start: effectiveSelectedStart,
            end: effectiveSelectedEnd,
          }}
          lockedBy={runGate?.editing_locked_by ?? null}
          onDirtyChange={(dirty) =>
            setDirtyGroups((current) =>
              current[group.id] === dirty
                ? current
                : { ...current, [group.id]: dirty },
            )
          }
        />
      ))}
      <section
        className="content-panel"
        aria-labelledby="console-history-title"
      >
        <h2 id="console-history-title">Historial reciente</h2>
        {history.data?.length ? (
          <>
            <ul className="resource-list">
              {history.data.map((run) => (
                <li key={run.id}>
                  <label>
                    <input
                      type="checkbox"
                      aria-label={`Comparar corrida ${run.id}`}
                      checked={comparisonPicks.includes(run.id)}
                      onChange={() =>
                        setComparisonPicks((picks) =>
                          picks.includes(run.id)
                            ? picks.filter((pick) => pick !== run.id)
                            : [...picks, run.id],
                        )
                      }
                    />
                  </label>
                  <strong>
                    {
                      runLabels[
                        runDetail.data?.run.id === run.id
                          ? runDetail.data.run.state
                          : run.state
                      ]
                    }
                  </strong>{" "}
                  <span>{run.started_at}</span> <span>{run.triggered_by}</span>
                  <button
                    type="button"
                    className="secondary-button"
                    aria-label={`Abrir resultados de corrida ${run.id}`}
                    onClick={() => setActiveRunId(run.id)}
                  >
                    Abrir
                  </button>
                </li>
              ))}
            </ul>
            <button
              type="button"
              className="secondary-button"
              disabled={comparisonPicks.length !== 2}
              onClick={() =>
                setComparedRuns(
                  chronologicalPair(comparisonPicks, history.data || []),
                )
              }
            >
              Comparar corridas
            </button>
          </>
        ) : visibleRun ? (
          <p>
            <strong>{runLabels[visibleRun.state]}</strong>{" "}
            <span>{visibleRun.started_at}</span>
          </p>
        ) : (
          <p className="empty-state">Todavia no hay corridas.</p>
        )}
        {runDetail.data?.failure ? (
          <p role="alert">
            {runDetail.data.failure.message} Referencia{" "}
            {runDetail.data.failure.reference}
          </p>
        ) : null}
      </section>
      {comparedRuns ? (
        <ConsoleRunComparisonView
          left={comparison.data?.left}
          right={comparison.data?.right}
          differences={comparison.data?.kpi_differences}
          onClose={() => setComparedRuns(null)}
        />
      ) : null}
      <PortalResultsBlock block={runDetail.data?.results_block} />
    </div>
  );
}

/** Order two picked runs oldest first; the history arrives newest first. */
function chronologicalPair(
  picks: number[],
  history: ConsoleRunEntry[],
): [number, number] {
  const [first, second] = [...picks].sort(
    (left, right) =>
      history.findIndex((run) => run.id === right) -
      history.findIndex((run) => run.id === left),
  );
  return [first, second];
}

function formatComparisonValue(
  value: number,
  decimals: number,
  unit: string | null,
  signed = false,
): string {
  const magnitude = value.toFixed(decimals);
  const signedMagnitude = signed && value > 0 ? `+${magnitude}` : magnitude;
  return unit ? `${signedMagnitude} ${unit}` : signedMagnitude;
}

function ConsoleComparisonSideView({
  side,
  position,
}: {
  side: ConsoleComparisonSide;
  position: "left" | "right";
}) {
  return (
    <section
      className="console-comparison-side"
      aria-label={`Corrida ${side.run.id}`}
    >
      <PortalResultsBlock
        block={side.results_block}
        resultsState={side.results_state}
        idPrefix={`console-comparison-${position}`}
        unavailableMessage="Los resultados de esta corrida no estan disponibles."
      />
    </section>
  );
}

function ConsoleRunComparisonView({
  left,
  right,
  differences,
  onClose,
}: {
  left: ConsoleComparisonSide | undefined;
  right: ConsoleComparisonSide | undefined;
  differences: ConsoleKpiDifference[] | undefined;
  onClose: () => void;
}) {
  return (
    <section className="content-panel" aria-label="Comparacion de corridas">
      <h2>Comparacion de corridas</h2>
      {left && right ? (
        <>
          {differences?.length ? (
            <table aria-label="Diferencias entre corridas">
              <thead>
                <tr>
                  <th scope="col">Indicador</th>
                  <th scope="col">Corrida {left.run.id}</th>
                  <th scope="col">Corrida {right.run.id}</th>
                  <th scope="col">Diferencia</th>
                </tr>
              </thead>
              <tbody>
                {differences.map((difference) => (
                  <tr key={difference.id}>
                    <td>{difference.label}</td>
                    <td>
                      {formatComparisonValue(
                        difference.left,
                        difference.decimals,
                        difference.unit,
                      )}
                    </td>
                    <td>
                      {formatComparisonValue(
                        difference.right,
                        difference.decimals,
                        difference.unit,
                      )}
                    </td>
                    <td>
                      {formatComparisonValue(
                        difference.difference,
                        difference.decimals,
                        difference.unit,
                        true,
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className="empty-state">No hay indicadores comparables.</p>
          )}
          <div className="console-comparison-grid">
            <ConsoleComparisonSideView side={left} position="left" />
            <ConsoleComparisonSideView side={right} position="right" />
          </div>
        </>
      ) : (
        <p className="empty-state">Cargando comparacion...</p>
      )}
      <button type="button" className="secondary-button" onClick={onClose}>
        Cerrar comparacion
      </button>
    </section>
  );
}
