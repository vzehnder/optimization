import { useQuery } from "@tanstack/react-query";
import { FormEvent, useState } from "react";
import { Link, useParams } from "react-router-dom";

import {
  ApiError,
  getObjectTimeSeriesContext,
  type ObjectTimeSeriesBindingUsage,
  type ObjectTimeSeriesContextQuery,
  type ObjectTimeSeriesContextRow,
} from "./api/client";
import { objectJourneyPath } from "./journeyRoutes";

function numericParam(value: string | undefined): number | null {
  if (!value || !/^\d+$/.test(value)) return null;
  const parsed = Number(value);
  return Number.isSafeInteger(parsed) && parsed > 0 ? parsed : null;
}

function usageStateLabel(usage: ObjectTimeSeriesBindingUsage): string | null {
  if (usage.state === "stale") return "Obsoleta";
  if (usage.state === "invalid") return "Invalida";
  return null;
}

function BindingUsage({ usage }: { usage: ObjectTimeSeriesBindingUsage }) {
  const state = usageStateLabel(usage);
  return (
    <li>
      <span>
        Usada en {usage.variant_name} · revision {usage.revision_number} · hash{" "}
        <code>{usage.content_hash}</code>
      </span>
      <span className="object-summary-secondary">
        {usage.scenario_name} · {usage.binding_role_key}
      </span>
      {state ? <strong className="object-summary-stale">{state}</strong> : null}
      {usage.execution_blocked ? (
        <strong className="object-summary-blocked">Ejecucion bloqueada</strong>
      ) : null}
    </li>
  );
}

function AssociationState({ row }: { row: ObjectTimeSeriesContextRow }) {
  if (row.source_kind === "object_specific") {
    return <span>Sin asociacion de catalogo</span>;
  }
  if (row.association?.state === "active_valid") {
    return <strong>Asociada al objeto</strong>;
  }
  return (
    <strong>Asociacion {row.association?.state ?? "no disponible"}</strong>
  );
}

function UsageState({ row }: { row: ObjectTimeSeriesContextRow }) {
  if (row.binding_summary.items.length === 0) {
    return <span>Aun no usada en una variante</span>;
  }
  return (
    <>
      <ul className="object-summary-usages">
        {row.binding_summary.items.map((usage) => (
          <BindingUsage key={usage.binding_id} usage={usage} />
        ))}
      </ul>
      {row.binding_summary.truncated ? (
        <p>
          Se muestran {row.binding_summary.items.length} de{" "}
          {row.binding_summary.total_count} usos.
        </p>
      ) : null}
    </>
  );
}

function ReadRefusal({ error }: { error: unknown }) {
  const apiError = error instanceof ApiError ? error : null;
  return (
    <p role="alert" className="result-alert">
      <strong>{apiError?.code ?? "TS_OBJECT_SUMMARY_FAILED"}</strong>{" "}
      {apiError?.message ?? "No se pudo leer el resumen del objeto."}
      {apiError?.requestId ? ` (request_id ${apiError.requestId})` : ""} No se
      modifico nada: esta superficie solo lee.
    </p>
  );
}

export function ObjectTimeSeriesSummaryView() {
  const params = useParams();
  const projectId = numericParam(params.projectId);
  const linkableObjectId = numericParam(params.linkableObjectId);
  const [draft, setDraft] = useState<ObjectTimeSeriesContextQuery>({
    q: "",
    kind: "all",
  });
  const [applied, setApplied] = useState<ObjectTimeSeriesContextQuery>(draft);
  const [cursorTrail, setCursorTrail] = useState<(string | null)[]>([null]);
  const cursor = cursorTrail[cursorTrail.length - 1];
  const summary = useQuery({
    queryKey: [
      "object-time-series-summary",
      projectId,
      linkableObjectId,
      applied,
      cursor,
    ],
    queryFn: ({ signal }) =>
      getObjectTimeSeriesContext(
        projectId as number,
        linkableObjectId as number,
        { ...applied, cursor },
        signal,
      ),
    enabled: projectId !== null && linkableObjectId !== null,
    retry: false,
  });

  if (projectId === null || linkableObjectId === null) {
    return (
      <section className="content-panel">
        <h1>No encontrado</h1>
        <p>El objeto solicitado no existe.</p>
      </section>
    );
  }

  return (
    <section className="content-panel catalog-surface object-summary-surface">
      <nav aria-label="Ruta del resumen">
        <Link to={`/projects/${projectId}`}>Proyecto</Link> / Series del objeto
      </nav>
      {summary.isPending ? (
        <p role="status">Cargando series del objeto</p>
      ) : null}
      {summary.isError ? <ReadRefusal error={summary.error} /> : null}
      {summary.data ? (
        <>
          <header>
            <p className="eyebrow">Resumen contextual</p>
            <h1>{summary.data.meta.object.display_name}</h1>
            <p>
              Fuentes disponibles, necesidad cubierta y uso exacto en variantes.
            </p>
          </header>
          <form
            className="catalog-filters"
            onSubmit={(event: FormEvent<HTMLFormElement>) => {
              event.preventDefault();
              setApplied({ ...draft });
              setCursorTrail([null]);
            }}
          >
            <div className="field-row">
              <label htmlFor="object-summary-search">Buscar</label>
              <input
                id="object-summary-search"
                type="search"
                value={draft.q ?? ""}
                onChange={(event) =>
                  setDraft((current) => ({
                    ...current,
                    q: event.target.value,
                  }))
                }
              />
            </div>
            <div className="field-row">
              <label htmlFor="object-summary-kind">Origen</label>
              <select
                id="object-summary-kind"
                value={draft.kind ?? "all"}
                onChange={(event) =>
                  setDraft((current) => ({
                    ...current,
                    kind: event.target
                      .value as ObjectTimeSeriesContextQuery["kind"],
                  }))
                }
              >
                <option value="all">Todos</option>
                <option value="catalog">Fuentes genericas</option>
                <option value="object_specific">Series especificas</option>
              </select>
            </div>
            <div className="inline-actions">
              <button type="submit">Filtrar</button>
            </div>
          </form>
          <div
            className="object-summary-actions"
            aria-label="Acciones protegidas"
          >
            <Link
              className="journey-entry-link"
              to={objectJourneyPath({
                projectId,
                linkableObjectId,
                intent: "associate",
              })}
            >
              Asociar fuente al objeto
            </Link>
            <Link
              className="journey-entry-link"
              to={objectJourneyPath({
                projectId,
                linkableObjectId,
                intent: "use_revision",
              })}
            >
              Usar revision en una variante
            </Link>
            <small>
              Ambas acciones abren el recorrido protegido. “Binding de
              ejecucion” es el nombre tecnico del segundo paso.
            </small>
          </div>
          <div className="time-series-table-scroll">
            <table>
              <caption>
                Series del objeto {summary.data.meta.object.display_name}
              </caption>
              <thead>
                <tr>
                  <th scope="col">Serie</th>
                  <th scope="col">Necesidad</th>
                  <th scope="col">Contrato</th>
                  <th scope="col">Asociacion</th>
                  <th scope="col">Uso en variantes</th>
                </tr>
              </thead>
              <tbody>
                {summary.data.items.map((row) => (
                  <tr key={`${row.source_kind}-${row.signal_id}`}>
                    <th scope="row">
                      <span className="catalog-signal-name">
                        {row.display_name}
                      </span>
                      <span className="catalog-series-key">
                        {row.series_key}
                      </span>
                      <span className="object-summary-kind">
                        {row.source_kind === "catalog"
                          ? "Fuente generica"
                          : "Serie especifica"}
                      </span>
                      {row.source_kind === "object_specific" ? (
                        <strong className="object-summary-local">
                          Solo este objeto
                        </strong>
                      ) : null}
                    </th>
                    <td>{row.need.binding_role_key}</td>
                    <td>
                      {row.semantic_type_key} · {row.data_class_key} ·{" "}
                      {row.unit_key}
                    </td>
                    <td>
                      <AssociationState row={row} />
                    </td>
                    <td>
                      <UsageState row={row} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <nav
            className="catalog-pagination"
            aria-label="Paginacion de las series del objeto"
          >
            <button
              className="secondary-button"
              type="button"
              disabled={cursorTrail.length === 1}
              onClick={() => setCursorTrail((trail) => trail.slice(0, -1))}
            >
              Anterior
            </button>
            <span>
              Pagina {cursorTrail.length} · {summary.data.items.length} series
              en esta pagina de {summary.data.summary.total_count}
            </span>
            <button
              className="secondary-button"
              type="button"
              disabled={!summary.data.page.has_more}
              onClick={() =>
                setCursorTrail((trail) => [
                  ...trail,
                  summary.data.page.next_cursor,
                ])
              }
            >
              Siguiente
            </button>
          </nav>
          {summary.data.items.length === 0 ? (
            <p className="empty-state">
              Este objeto aun no tiene fuentes asociadas ni series especificas.
            </p>
          ) : null}
        </>
      ) : null}
    </section>
  );
}
