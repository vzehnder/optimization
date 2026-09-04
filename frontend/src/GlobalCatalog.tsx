import { useQuery } from "@tanstack/react-query";
import { FormEvent, useState } from "react";

import {
  ApiError,
  getCatalogInputDetail,
  getCatalogInputPreview,
  listCatalogDescriptors,
  listCatalogInputRevisions,
  listCatalogInputs,
  type CatalogCoverageSummary,
  type CatalogDescriptor,
  type CatalogInputQuery,
  type CatalogPreviewQuery,
  type CatalogRevisionRow,
} from "./api/client";

const SCOPE_OPTIONS = [
  { value: "", label: "Todos" },
  { value: "project", label: "Proyecto" },
  { value: "global", label: "Global" },
];

const STATUS_OPTIONS = [
  { value: "active", label: "Activas" },
  { value: "archived", label: "Archivadas" },
];

const ORDER_OPTIONS = [
  { value: "-updated_at,display_name", label: "Actualizacion reciente" },
  { value: "display_name", label: "Nombre" },
  { value: "owner_project_name", label: "Proyecto propietario" },
  { value: "-coverage_end", label: "Fin de cobertura" },
  { value: "-association_count", label: "Asociaciones" },
];

const EMPTY_FILTERS: CatalogInputQuery = {
  q: "",
  semantic_type_key: "",
  data_class_key: "",
  unit_key: "",
  visibility_scope: "",
  signal_status: "active",
  order: ORDER_OPTIONS[0].value,
};

function coverageLabel(coverage: CatalogCoverageSummary): string {
  const { start, end } = coverage;
  if (!start || !end) return "Sin cobertura";
  return `${start} - ${end}`;
}

// The canonical rows use both NULL and the empty string for "not recorded";
// a blank cell would read as a value the inspector simply failed to print.
function orAbsent(value: string | null | undefined, absent: string): string {
  return value && value.trim() ? value : absent;
}

function consumerLabel(
  count: number,
  singular: string,
  plural: string,
): string {
  return `${count} ${count === 1 ? singular : plural}`;
}

// The projection stores seconds; the table reads them as a period a human
// recognizes without doing the arithmetic itself.
function resolutionLabel(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds <= 0) return "Sin resolucion";
  const units: [number, string][] = [
    [86400, "d"],
    [3600, "h"],
    [60, "min"],
  ];
  for (const [size, suffix] of units) {
    if (seconds >= size && seconds % size === 0)
      return `${seconds / size} ${suffix}`;
  }
  return `${seconds} s`;
}

function useDescriptors(kind: string) {
  return useQuery({
    queryKey: ["catalog-descriptors", kind],
    queryFn: ({ signal }) => listCatalogDescriptors(kind, signal),
    staleTime: 5 * 60_000,
  });
}

function DescriptorSelect({
  id,
  label,
  value,
  descriptors,
  onChange,
}: {
  id: string;
  label: string;
  value: string;
  descriptors: CatalogDescriptor[];
  onChange: (value: string) => void;
}) {
  return (
    <div className="field-row">
      <label htmlFor={id}>{label}</label>
      <select
        id={id}
        value={value}
        onChange={(event) => onChange(event.target.value)}
      >
        <option value="">Todos</option>
        {descriptors.map((descriptor) => (
          <option key={descriptor.key} value={descriptor.key}>
            {descriptor.display_name}
          </option>
        ))}
      </select>
    </div>
  );
}

const QUERY_REFUSALS: Record<string, string> = {
  TS_QUERY_INVALID:
    "El servidor rechazo la consulta. Revisa la busqueda, las claves de " +
    "catalogo y el rango de cobertura.",
  TS_QUERY_CURSOR_EXPIRED:
    "El cursor de esta pagina expiro. Vuelve a la primera pagina para leer " +
    "una fotografia coherente.",
  TS_QUERY_CURSOR_MISMATCH:
    "El cursor no corresponde a estos filtros. Vuelve a la primera pagina.",
  TS_QUERY_SNAPSHOT_CHANGED:
    "El catalogo cambio mientras paginabas. Vuelve a la primera pagina para " +
    "no mezclar dos fotografias.",
};

// Chapter 8.7: a refused read keeps the filters, names its `request_id` and
// says out loud that nothing was written, because nothing here ever writes.
function CatalogRefusal({ error }: { error: unknown }) {
  const apiError = error instanceof ApiError ? error : null;
  const code = apiError?.code ?? "TS_QUERY_FAILED";
  return (
    <p role="alert" className="result-alert">
      <strong>{code}</strong>{" "}
      {QUERY_REFUSALS[code] ??
        apiError?.message ??
        "No se pudo leer el catalogo."}
      {apiError?.requestId ? ` (request_id ${apiError.requestId})` : ""} No se
      modifico nada: esta superficie solo lee.
    </p>
  );
}

const PREVIEW_REFUSALS: Record<string, string> = {
  TS_PREVIEW_TOO_LARGE:
    "El rango pedido supera el limite del preview. Acorta el rango, baja el " +
    "maximo de puntos o elige un muestreo que conserve extremos.",
  TS_PREVIEW_REVISION_UNAVAILABLE:
    "Esa revision existe en la historia pero no tiene contenido materializado, " +
    "por lo que no se puede previsualizar.",
};

// The catalog cursor is bound to filters, so a preview refusal always names its
// stable code: the surface repeats it instead of quietly showing fewer points.
function PreviewRefusal({ error }: { error: unknown }) {
  const apiError = error instanceof ApiError ? error : null;
  const code = apiError?.code ?? "TS_PREVIEW_FAILED";
  return (
    <p role="alert" className="result-alert">
      <strong>{code}</strong>{" "}
      {PREVIEW_REFUSALS[code] ??
        apiError?.message ??
        "No se pudo leer el preview."}
      {apiError?.requestId ? ` (request_id ${apiError.requestId})` : ""}
    </p>
  );
}

// The catalog stores naive timestamps; the preview contract demands an offset.
function withOffset(timestamp: string | null): string {
  if (!timestamp) return "";
  if (/(Z|[+-]\d{2}:\d{2})$/.test(timestamp)) return timestamp;
  return `${timestamp}Z`;
}

function BoundedPreview({
  signalId,
  revisions,
  defaultRevisionId,
  coverage,
}: {
  signalId: number;
  revisions: CatalogRevisionRow[];
  defaultRevisionId: number;
  coverage: CatalogCoverageSummary;
}) {
  const [form, setForm] = useState({
    revisionId: String(defaultRevisionId),
    from: withOffset(coverage.start),
    to: withOffset(coverage.end),
    sampling: "minmax",
    maxPoints: "500",
  });
  const [request, setRequest] = useState<CatalogPreviewQuery | null>(null);

  const preview = useQuery({
    queryKey: ["catalog-input-preview", signalId, request],
    queryFn: ({ signal }) =>
      getCatalogInputPreview(signalId, request as CatalogPreviewQuery, signal),
    enabled: request !== null,
    retry: false,
  });

  return (
    <section aria-label="Preview acotado">
      <h3>Preview acotado</h3>
      <form
        className="workspace-form catalog-preview-form"
        onSubmit={(event) => {
          event.preventDefault();
          setRequest({
            revisionId: Number(form.revisionId),
            from: form.from,
            to: form.to,
            sampling: form.sampling,
            maxPoints: Number(form.maxPoints),
          });
        }}
      >
        <div className="field-row">
          <label htmlFor="preview-revision">Revision</label>
          <select
            id="preview-revision"
            value={form.revisionId}
            onChange={(event) =>
              setForm((current) => ({
                ...current,
                revisionId: event.target.value,
              }))
            }
          >
            {revisions.map((revision) => (
              <option key={revision.id} value={String(revision.id)}>
                Revision {revision.number}
              </option>
            ))}
          </select>
        </div>
        <div className="field-row">
          <label htmlFor="preview-from">Desde</label>
          <input
            id="preview-from"
            type="text"
            value={form.from}
            onChange={(event) =>
              setForm((current) => ({ ...current, from: event.target.value }))
            }
          />
        </div>
        <div className="field-row">
          <label htmlFor="preview-to">Hasta</label>
          <input
            id="preview-to"
            type="text"
            value={form.to}
            onChange={(event) =>
              setForm((current) => ({ ...current, to: event.target.value }))
            }
          />
        </div>
        <div className="field-row">
          <label htmlFor="preview-sampling">Muestreo</label>
          <select
            id="preview-sampling"
            value={form.sampling}
            onChange={(event) =>
              setForm((current) => ({
                ...current,
                sampling: event.target.value,
              }))
            }
          >
            <option value="minmax">Extremos por bucket</option>
            <option value="uniform">Uniforme</option>
            <option value="none">Sin muestreo</option>
          </select>
        </div>
        <div className="field-row">
          <label htmlFor="preview-max-points">Maximo de puntos</label>
          <input
            id="preview-max-points"
            type="number"
            min={1}
            max={2000}
            value={form.maxPoints}
            onChange={(event) =>
              setForm((current) => ({
                ...current,
                maxPoints: event.target.value,
              }))
            }
          />
        </div>
        <div className="inline-actions">
          <button type="submit">Previsualizar</button>
        </div>
      </form>

      {preview.isFetching ? <p role="status">Leyendo el preview</p> : null}
      {preview.isError ? <PreviewRefusal error={preview.error} /> : null}
      {preview.data && !preview.isError ? (
        <>
          <p className="catalog-preview-summary">
            {`Revision ${
              revisions.find(
                (revision) => revision.id === preview.data.revision.id,
              )?.number ?? "?"
            } (id ${preview.data.revision.id}) - hash ${preview.data.revision.content_hash} - ${preview.data.returned_point_count} de ${preview.data.source_point_count} puntos - ${preview.data.unit.symbol}`}
          </p>
          <div className="time-series-table-scroll">
            <table>
              <caption>Preview</caption>
              <thead>
                <tr>
                  <th scope="col">Inicio</th>
                  <th scope="col">Fin</th>
                  <th scope="col">Valor</th>
                  <th scope="col">Calidad</th>
                </tr>
              </thead>
              <tbody>
                {preview.data.points.map((point) => (
                  <tr key={`${point.timestamp_start}-${point.timestamp_end}`}>
                    <td>{point.timestamp_start}</td>
                    <td>{point.timestamp_end}</td>
                    <td>{point.value}</td>
                    <td>{orAbsent(point.quality_flag, "Sin marca")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      ) : null}
    </section>
  );
}

// The inspector answers from metadata only: one detail and one page of
// immutable revision metadata. Points arrive only when a preview is asked for.
function SignalInspector({ signalId }: { signalId: number }) {
  const detail = useQuery({
    queryKey: ["catalog-input-detail", signalId],
    queryFn: ({ signal }) => getCatalogInputDetail(signalId, signal),
    retry: false,
  });
  const revisions = useQuery({
    queryKey: ["catalog-input-revisions", signalId],
    queryFn: ({ signal }) => listCatalogInputRevisions(signalId, signal),
    retry: false,
  });

  return (
    <section
      className="workspace-section catalog-inspector"
      aria-label="Inspector de senal"
    >
      {detail.isPending ? <p role="status">Cargando la senal</p> : null}
      {detail.isError ? <CatalogRefusal error={detail.error} /> : null}
      {detail.data ? (
        <>
          <h2>{detail.data.identity.display_name}</h2>
          <p className="catalog-series-key">
            {detail.data.identity.series_key}
          </p>

          <section aria-label="Contrato">
            <h3>Contrato</h3>
            <dl className="catalog-definition-list">
              <dt>Tipo semantico</dt>
              <dd>{detail.data.contract.semantic_type.display_name}</dd>
              <dt>Dimension</dt>
              <dd>{detail.data.contract.semantic_type.dimension_key}</dd>
              <dt>Clase</dt>
              <dd>{detail.data.contract.data_class.display_name}</dd>
              <dt>Unidad</dt>
              <dd>{detail.data.contract.unit.symbol}</dd>
              <dt>Rol y agregacion</dt>
              <dd>
                {detail.data.contract.signal_role} /{" "}
                {detail.data.contract.aggregation}
              </dd>
              <dt>Alcance</dt>
              <dd>{detail.data.set.visibility_scope}</dd>
              <dt>Propietario</dt>
              <dd>{detail.data.owner.project_name}</dd>
            </dl>
          </section>

          <section aria-label="Procedencia">
            <h3>Procedencia</h3>
            <dl className="catalog-definition-list">
              <dt>Origen</dt>
              <dd>{detail.data.provenance.kind}</dd>
              <dt>Clave de fuente</dt>
              <dd>
                {orAbsent(detail.data.provenance.source_key, "Sin clave")}
              </dd>
              <dt>Archivo</dt>
              <dd>
                {orAbsent(detail.data.provenance.filename, "Sin archivo")}
              </dd>
              <dt>Checksum</dt>
              <dd>
                {orAbsent(detail.data.provenance.checksum, "Sin checksum")}
              </dd>
            </dl>
          </section>

          <section aria-label="Revision vigente">
            <h3>Revision vigente</h3>
            <dl className="catalog-definition-list">
              <dt>Revision</dt>
              <dd>Revision {detail.data.current_revision.number}</dd>
              <dt>Estado</dt>
              <dd>{detail.data.current_revision.state}</dd>
              <dt>Hash de contenido</dt>
              <dd className="catalog-hash">
                {detail.data.current_revision.content_hash}
              </dd>
              <dt>Sellada</dt>
              <dd>{detail.data.current_revision.created_at}</dd>
            </dl>
          </section>

          <section aria-label="Cobertura y resolucion">
            <h3>Cobertura y resolucion</h3>
            <dl className="catalog-definition-list">
              <dt>Cobertura</dt>
              <dd>{coverageLabel(detail.data.coverage_summary)}</dd>
              <dt>Resolucion nominal</dt>
              <dd>
                {resolutionLabel(
                  detail.data.coverage_summary.nominal_resolution_seconds,
                )}
              </dd>
              <dt>Regularidad</dt>
              <dd>{detail.data.coverage_summary.regularity}</dd>
              <dt>Periodos</dt>
              <dd>{detail.data.coverage_summary.period_count}</dd>
              <dt>Zona de la fuente</dt>
              <dd>
                {orAbsent(
                  detail.data.coverage_summary.source_timezone,
                  "Sin zona",
                )}
              </dd>
            </dl>
          </section>

          <section aria-label="Consumidores">
            <h3>Consumidores</h3>
            <ul className="catalog-consumers">
              <li>
                {consumerLabel(
                  detail.data.link_summary.association_count,
                  "asociacion",
                  "asociaciones",
                )}
              </li>
              <li>
                {consumerLabel(
                  detail.data.link_summary.binding_count,
                  "binding de ejecucion",
                  "bindings de ejecucion",
                )}
              </li>
            </ul>
          </section>
        </>
      ) : null}

      {detail.data && revisions.data ? (
        <BoundedPreview
          signalId={signalId}
          revisions={revisions.data.items}
          defaultRevisionId={detail.data.current_revision.id}
          coverage={detail.data.coverage_summary}
        />
      ) : null}

      <section aria-label="Historia de revisiones">
        <h3>Historia de revisiones</h3>
        {revisions.isError ? <CatalogRefusal error={revisions.error} /> : null}
        {revisions.data ? (
          <ul className="catalog-revision-history">
            {revisions.data.items.map((revision) => (
              <li key={revision.id}>
                <span>Revision {revision.number}</span>
                <span className="catalog-hash">
                  {orAbsent(revision.content_hash, "Sin hash")}
                </span>
                <span>{revision.created_at}</span>
                <span>{orAbsent(revision.change_summary, "Sin resumen")}</span>
              </li>
            ))}
          </ul>
        ) : null}
      </section>
    </section>
  );
}

export function GlobalCatalogView() {
  const [draft, setDraft] = useState<CatalogInputQuery>(EMPTY_FILTERS);
  const [applied, setApplied] = useState<CatalogInputQuery>(EMPTY_FILTERS);
  // Keyset pagination only walks forward, so going back means replaying the
  // cursor that opened each visited page. The first page has none.
  const [cursorTrail, setCursorTrail] = useState<(string | null)[]>([null]);
  const [inspected, setInspected] = useState<number | null>(null);

  const semanticTypes = useDescriptors("semantic_type");
  const dataClasses = useDescriptors("data_class");
  const units = useDescriptors("unit");

  const cursor = cursorTrail[cursorTrail.length - 1];
  const inputs = useQuery({
    queryKey: ["catalog-inputs", applied, cursor],
    queryFn: ({ signal }) => listCatalogInputs({ ...applied, cursor }, signal),
    // A refused query is deterministic; repeating it only hides the reason.
    retry: false,
  });

  function submitFilters(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setApplied({ ...draft });
    setCursorTrail([null]);
  }

  function update(patch: Partial<CatalogInputQuery>) {
    setDraft((current) => ({ ...current, ...patch }));
  }

  return (
    <section className="workspace-view catalog-surface">
      <header className="workspace-heading">
        <h1>Catalogo de series genericas</h1>
        <p>
          Superficie de solo lectura: explorar, inspeccionar procedencia y
          consultar historia no modifica ninguna fuente.
        </p>
      </header>

      <form className="workspace-form catalog-filters" onSubmit={submitFilters}>
        <div className="field-row">
          <label htmlFor="catalog-q">Buscar</label>
          <input
            id="catalog-q"
            type="search"
            value={draft.q ?? ""}
            maxLength={200}
            onChange={(event) => update({ q: event.target.value })}
          />
        </div>
        <DescriptorSelect
          id="catalog-semantic-type"
          label="Tipo semantico"
          value={draft.semantic_type_key ?? ""}
          descriptors={semanticTypes.data?.items ?? []}
          onChange={(value) => update({ semantic_type_key: value })}
        />
        <DescriptorSelect
          id="catalog-data-class"
          label="Clase"
          value={draft.data_class_key ?? ""}
          descriptors={dataClasses.data?.items ?? []}
          onChange={(value) => update({ data_class_key: value })}
        />
        <DescriptorSelect
          id="catalog-unit"
          label="Unidad"
          value={draft.unit_key ?? ""}
          descriptors={units.data?.items ?? []}
          onChange={(value) => update({ unit_key: value })}
        />
        <div className="field-row">
          <label htmlFor="catalog-scope">Alcance</label>
          <select
            id="catalog-scope"
            value={draft.visibility_scope ?? ""}
            onChange={(event) =>
              update({ visibility_scope: event.target.value })
            }
          >
            {SCOPE_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>
        <div className="field-row">
          <label htmlFor="catalog-status">Estado</label>
          <select
            id="catalog-status"
            value={draft.signal_status ?? "active"}
            onChange={(event) => update({ signal_status: event.target.value })}
          >
            {STATUS_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>
        <div className="field-row">
          <label htmlFor="catalog-order">Orden</label>
          <select
            id="catalog-order"
            value={draft.order ?? ORDER_OPTIONS[0].value}
            onChange={(event) => update({ order: event.target.value })}
          >
            {ORDER_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>
        <div className="inline-actions">
          <button type="submit">Filtrar</button>
          <button
            className="secondary-button"
            type="button"
            onClick={() => {
              setDraft(EMPTY_FILTERS);
              setApplied(EMPTY_FILTERS);
              setCursorTrail([null]);
            }}
          >
            Limpiar
          </button>
        </div>
      </form>

      {inputs.isPending ? <p role="status">Cargando el catalogo</p> : null}
      {inputs.isError ? <CatalogRefusal error={inputs.error} /> : null}
      {inputs.data ? (
        <div className="time-series-table-scroll">
          <table>
            <caption>Senales genericas del catalogo</caption>
            <thead>
              <tr>
                <th scope="col">Senal</th>
                <th scope="col">Propietario</th>
                <th scope="col">Alcance</th>
                <th scope="col">Tipo</th>
                <th scope="col">Clase</th>
                <th scope="col">Unidad</th>
                <th scope="col">Cobertura</th>
                <th scope="col">Resolucion</th>
                <th scope="col">Detalle</th>
              </tr>
            </thead>
            <tbody>
              {inputs.data.items.map((row) => (
                <tr key={row.signal_id}>
                  <th scope="row">
                    <span className="catalog-signal-name">
                      {row.identity.display_name}
                    </span>
                    <span className="catalog-series-key">
                      {row.identity.series_key}
                    </span>
                  </th>
                  <td>{row.owner.project_name}</td>
                  <td>{row.set.visibility_scope}</td>
                  <td>{row.classification.semantic_type_key}</td>
                  <td>{row.classification.data_class_key}</td>
                  <td>{row.classification.unit_key}</td>
                  <td>{coverageLabel(row.coverage_summary)}</td>
                  <td>
                    {resolutionLabel(
                      row.coverage_summary.nominal_resolution_seconds,
                    )}
                  </td>
                  <td>
                    <button
                      className="secondary-button"
                      type="button"
                      aria-pressed={inspected === row.signal_id}
                      onClick={() => setInspected(row.signal_id)}
                    >
                      Inspeccionar
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
      {inputs.data ? (
        <nav
          className="catalog-pagination"
          aria-label="Paginacion del catalogo"
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
            Pagina {cursorTrail.length} - {inputs.data.items.length} senales en
            esta pagina
            {inputs.data.summary
              ? ` de ${inputs.data.summary.total_count}`
              : ""}
          </span>
          <button
            className="secondary-button"
            type="button"
            disabled={!inputs.data.page.has_more}
            onClick={() =>
              setCursorTrail((trail) => [
                ...trail,
                inputs.data.page.next_cursor,
              ])
            }
          >
            Siguiente
          </button>
        </nav>
      ) : null}
      {inputs.data && inputs.data.items.length === 0 ? (
        <p className="empty-state">
          Ningun resultado con estos filtros. Ajusta la busqueda, el tipo, la
          clase, la unidad o el alcance.
        </p>
      ) : null}
      {inspected === null ? null : (
        <SignalInspector key={inspected} signalId={inspected} />
      )}
    </section>
  );
}
