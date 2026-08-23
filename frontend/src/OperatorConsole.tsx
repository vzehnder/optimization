import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FormEvent, useState } from "react";
import { Link, useParams } from "react-router-dom";

import {
  ApiError,
  createOperatorConsole,
  listCaseInputVariants,
  getConsoleShell,
  getOperatorConsole,
  listOperableConsoles,
  listOperatorConsoles,
  saveOperatorConsole,
  type OperatorConsole,
  type OperatorConsoleDocument,
  type OperatorConsoleStatus,
} from "./api/client";

const operatorConsolesQueryKey = (scenarioId: number) =>
  ["operator-consoles", scenarioId] as const;
const operatorConsoleQueryKey = (scenarioId: number, consoleId: number) =>
  ["operator-console", scenarioId, consoleId] as const;
const consoleShellListQueryKey = ["console-shell-list"] as const;
const consoleShellQueryKey = (consoleId: number) =>
  ["console-shell", consoleId] as const;

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

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!name.trim() || createMutation.isPending) return;
    createMutation.mutate();
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
                  <Link to={`/scenarios/${scenarioId}/consoles/${console.id}`}>
                    Configurar
                  </Link>{" "}
                  <Link to={`/console/${console.id}`}>Probar</Link>
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

  const consoleQuery = useQuery({
    queryKey: operatorConsoleQueryKey(scenarioId || 0, consoleId || 0),
    queryFn: ({ signal }) =>
      getOperatorConsole(scenarioId || 0, consoleId || 0, signal),
    enabled: scenarioId !== null && consoleId !== null,
    retry: false,
  });

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
      void queryClient.invalidateQueries({
        queryKey: operatorConsolesQueryKey(scenarioId || 0),
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
  if (consoleQuery.isError) {
    return (
      <section className="content-panel">
        <h1>No se pudo cargar</h1>
        <p role="alert">{errorMessage(consoleQuery.error)}</p>
      </section>
    );
  }

  const console = consoleQuery.data;
  const identity = console.document.public_identity;

  function save(
    document: OperatorConsoleDocument,
    status: OperatorConsoleStatus,
  ) {
    saveMutation.mutate({
      document,
      status,
      expected_revision: console.revision,
    });
  }

  return (
    <section
      className="workspace-view"
      aria-labelledby="operator-console-editor"
    >
      <h1 id="operator-console-editor">Configuracion de la consola</h1>
      <p>
        <span className="role-badge">{STATUS_LABELS[console.status]}</span>{" "}
        <span>Revision {console.revision}</span>
      </p>
      {error ? <p role="alert">{error}</p> : null}
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
      <ConsoleDocumentForm
        document={console.document}
        disabled={saveMutation.isPending}
        onSave={(document) => save(document, console.status)}
      />
      <div className="inline-actions">
        {console.status === "draft" ? (
          <button
            type="button"
            disabled={saveMutation.isPending}
            onClick={() => save(console.document, "active")}
          >
            Activar
          </button>
        ) : (
          <button
            type="button"
            disabled={saveMutation.isPending}
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

function ConsoleDocumentForm({
  document,
  disabled,
  onSave,
}: {
  document: OperatorConsoleDocument;
  disabled: boolean;
  onSave: (document: OperatorConsoleDocument) => void;
}) {
  const [name, setName] = useState(document.public_identity.name);
  const [description, setDescription] = useState(
    document.public_identity.description,
  );
  const [documentText, setDocumentText] = useState(() =>
    JSON.stringify(
      {
        parameters: document.parameters,
        groups: document.groups,
        results: document.results,
      },
      null,
      2,
    ),
  );
  const [parseError, setParseError] = useState("");

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    let parsed: Pick<
      OperatorConsoleDocument,
      "parameters" | "groups" | "results"
    >;
    try {
      parsed = JSON.parse(documentText);
    } catch {
      setParseError("El documento no es JSON valido.");
      return;
    }
    setParseError("");
    onSave({
      schema_version: "operator_console_config.v1",
      public_identity: { name: name.trim(), description: description.trim() },
      parameters: parsed.parameters,
      groups: parsed.groups,
      results: parsed.results,
    });
  }

  return (
    <form className="workspace-form console-document-form" onSubmit={submit}>
      {parseError ? <p role="alert">{parseError}</p> : null}
      <label htmlFor="console-identity-name">Nombre publico</label>
      <input
        id="console-identity-name"
        type="text"
        value={name}
        onChange={(event) => setName(event.target.value)}
      />
      <label htmlFor="console-identity-description">Descripcion publica</label>
      <input
        id="console-identity-description"
        type="text"
        value={description}
        onChange={(event) => setDescription(event.target.value)}
      />
      <label htmlFor="console-document">
        Parametros, grupos y resultados (JSON)
      </label>
      <textarea
        id="console-document"
        rows={12}
        value={documentText}
        onChange={(event) => setDocumentText(event.target.value)}
      />
      <button type="submit" disabled={disabled}>
        Guardar configuracion
      </button>
    </form>
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

export function ConsoleShellView() {
  const params = useParams();
  const consoleId = numericParam(params.consoleId);
  const shell = useQuery({
    queryKey: consoleShellQueryKey(consoleId || 0),
    queryFn: ({ signal }) => getConsoleShell(consoleId || 0, signal),
    enabled: consoleId !== null,
    retry: false,
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
  if (shell.isError) {
    return (
      <section className="content-panel">
        <h1>No encontrado</h1>
        <p role="alert">{errorMessage(shell.error)}</p>
      </section>
    );
  }

  const { console: identity, internal_test: internalTest } = shell.data;

  return (
    <>
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
    </>
  );
}
