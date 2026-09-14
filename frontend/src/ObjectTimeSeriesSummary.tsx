import { useQuery } from "@tanstack/react-query";
import { FormEvent, useState } from "react";
import {
  Link,
  useLocation,
  useParams,
  useSearchParams,
} from "react-router-dom";

import {
  ApiError,
  getObjectTimeSeriesContext,
  type ObjectTimeSeriesBindingUsage,
  type ObjectTimeSeriesContextQuery,
  type ObjectTimeSeriesContextRow,
} from "./api/client";
import { objectJourneyPath, safeReturnPath } from "./journeyRoutes";

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
  const location = useLocation();
  return <ObjectSummaryContent key={location.pathname + location.search} />;
}

function ObjectSummaryContent() {
  const [search, setSearch] = useSearchParams();
  const location = useLocation();
  const params = useParams();
  const projectId = numericParam(params.projectId);
  const linkableObjectId = numericParam(params.linkableObjectId);
  const applied: ObjectTimeSeriesContextQuery = {
    q: (search.get("q") ?? "").slice(0, 200),
    kind:
      search.get("kind") === "catalog"
        ? "catalog"
        : search.get("kind") === "object_specific"
          ? "object_specific"
          : "all",
  };
  const [draft, setDraft] = useState<ObjectTimeSeriesContextQuery>(applied);
  const cursorTrail: (string | null)[] = [
    null,
    ...search
      .getAll("cursor")
      .filter((entry) => entry.length > 0 && entry.length <= 4096)
      .slice(0, 50),
  ];
  const returnTo = safeReturnPath(search.get("return_to"));
  const currentPath = safeReturnPath(location.pathname + location.search)!;
  const scenarioId =
    numericParam(search.get("scenario_id") ?? undefined) ?? undefined;
  const variantId =
    numericParam(search.get("variant_id") ?? undefined) ?? undefined;
  function navigate(
    filters: ObjectTimeSeriesContextQuery,
    trail: (string | null)[],
  ) {
    const next = new URLSearchParams(currentPath.split("?")[1]);
    next.set("q", filters.q ?? "");
    next.set("kind", filters.kind ?? "all");
    next.delete("cursor");
    for (const entry of trail) if (entry) next.append("cursor", entry);
    setSearch(next);
  }
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
        {returnTo && (
          <>
            {" "}
            · <Link to={returnTo}>Volver al escenario</Link>
          </>
        )}
        {" · "}
        <Link
          to={`/time-series/catalog?${new URLSearchParams({ return_to: currentPath })}`}
        >
          Explorar catálogo general
        </Link>
      </nav>
      {summary.isPending ? (
        <p role="status">Cargando series del objeto</p>
      ) : null}
      {summary.isError ? (
        <>
          <ReadRefusal error={summary.error} />
          {cursor ? (
            <button type="button" onClick={() => navigate(applied, [null])}>
              Volver al inicio conservando filtros
            </button>
          ) : (
            <button type="button" onClick={() => void summary.refetch()}>
              Reintentar resumen
            </button>
          )}
        </>
      ) : null}
      {summary.data && !summary.isError ? (
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
              navigate(draft, [null]);
            }}
          >
            <div className="field-row">
              <label htmlFor="object-summary-search">Buscar</label>
              <input
                id="object-summary-search"
                type="search"
                maxLength={200}
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
                scenarioId,
                variantId,
                returnTo: currentPath,
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
                scenarioId,
                variantId,
                returnTo: currentPath,
              })}
            >
              Usar revision en una variante
            </Link>
            <small>
              Ambas acciones abren el recorrido protegido. “Binding de
              ejecucion” es el nombre tecnico del segundo paso.
            </small>
          </div>
          <div
            className="time-series-table-scroll"
            tabIndex={0}
            role="region"
            aria-label="Tabla con desplazamiento horizontal"
          >
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
              onClick={() => navigate(applied, cursorTrail.slice(0, -1))}
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
                navigate(applied, [
                  ...cursorTrail,
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
