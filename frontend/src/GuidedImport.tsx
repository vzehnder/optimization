import { useEffect, useRef, useState } from "react";
import { flushSync } from "react-dom";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import {
  uploadTimeSeriesSource,
  previewTimeSeriesCatalogImport,
  importTimeSeriesSourceToCatalog,
  type CatalogImportPreview,
  type TimeSeriesSource,
  type TimeSeriesCatalogImportPayload,
  type ProjectTimeSeriesSet,
  getTimeSeriesRows,
  saveTimeSeriesRows,
  type TimeSeriesRow,
  ApiError,
  type ImportErrorLocation,
  getTimeSeriesImportOptions,
} from "./api/client";
import { useSignalCatalog } from "./signalCatalog";

function Column({
  label,
  value,
  columns,
  onChange,
}: {
  label: string;
  value: string;
  columns: string[];
  onChange: (value: string) => void;
}) {
  return (
    <label className="field-row">
      <span>{label}</span>
      <select value={value} onChange={(event) => onChange(event.target.value)}>
        <option value="">Elegir columna</option>
        {columns.map((column) => (
          <option key={column}>{column}</option>
        ))}
      </select>
    </label>
  );
}

export function GuidedImport({
  scenarioId,
  projectId,
  disabled,
  onSourcePersisted,
  onPendingChange,
}: {
  scenarioId: number;
  projectId: number;
  disabled: boolean;
  onSourcePersisted: (source: TimeSeriesSource) => void;
  onPendingChange: (notice: string) => void;
}) {
  const catalog = useSignalCatalog();
  const options = useQuery({
    queryKey: ["time-series-import-options", scenarioId],
    queryFn: ({ signal }) => getTimeSeriesImportOptions(scenarioId, signal),
    retry: false,
  });
  const [file, setFile] = useState<File | null>(null);
  const uploadedFile = useRef<File | null>(null);
  const [source, setSource] = useState<TimeSeriesSource | null>(null);
  const [step, setStep] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [uncertain, setUncertain] = useState(false);
  const [preview, setPreview] = useState<CatalogImportPreview | null>(null);
  const [created, setCreated] = useState<ProjectTimeSeriesSet | null>(null);
  const [rows, setRows] = useState<TimeSeriesRow[]>([]);
  const [rowsDirty, setRowsDirty] = useState(false);
  const [page, setPage] = useState(0);
  const [location, setLocation] = useState<ImportErrorLocation | undefined>();
  const region = useRef<HTMLElement>(null);
  const [payload, setPayload] = useState<TimeSeriesCatalogImportPayload>({
    set_name: "",
    version_label: "v1",
    data_kind: "real",
    timezone: "UTC",
    timestamp_column: "",
    duration_hours_column: "",
    signal_mappings: [{ source_column: "", signal_key: "", source_unit: "" }],
  });
  const sheets = useRef(
    new Map<
      string,
      {
        source: TimeSeriesSource;
        payload: TimeSeriesCatalogImportPayload;
        rows: TimeSeriesRow[];
        rowsDirty: boolean;
        page: number;
      }
    >(),
  );
  useEffect(() => {
    onPendingChange(
      created || (!file && !source)
        ? ""
        : source
          ? "La fuente temporal permanece guardada en el modelo. El mapeo y las correcciones pendientes no se publicaron; al salir se pierden las decisiones locales."
          : "El archivo seleccionado aún no se guardó en el servidor.",
    );
  }, [created, file, source, onPendingChange]);
  function update(patch: Partial<TimeSeriesCatalogImportPayload>) {
    setPayload((current) => ({ ...current, ...patch }));
    setPreview(null);
  }
  async function upload(sheet = "") {
    if (!file || busy) return;
    if (!sheet && source && uploadedFile.current === file) {
      setStep(1);
      return;
    }
    if (sheet && source) {
      sheets.current.set(source.selected_sheet ?? "", {
        source,
        payload,
        rows,
        rowsDirty,
        page,
      });
      const cached = sheets.current.get(sheet);
      if (cached) {
        setSource(cached.source);
        setPayload(cached.payload);
        setRows(cached.rows);
        setRowsDirty(cached.rowsDirty);
        setPage(cached.page);
        setPreview(null);
        setError("");
        setLocation(undefined);
        return;
      }
    }
    setBusy(true);
    setError("");
    try {
      const saved = await uploadTimeSeriesSource(scenarioId, file, sheet);
      if (!sheet) sheets.current.clear();
      uploadedFile.current = file;
      setSource(saved);
      onSourcePersisted(saved);
      setRows([]);
      setPage(0);
      setRowsDirty(false);
      setPreview(null);
      setLocation(undefined);
      const columns = saved.columns ?? [];
      setPayload((current) => ({
        ...current,
        set_name: file.name.replace(/\.[^.]+$/, ""),
        timestamp_column: columns.includes("timestamp") ? "timestamp" : "",
        duration_hours_column: columns.includes("hours") ? "hours" : "",
        signal_mappings: [
          { source_column: "", signal_key: "", source_unit: "" },
        ],
      }));
      setStep(1);
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : String(failure));
    } finally {
      setBusy(false);
    }
  }
  async function review() {
    if (!source || busy) return;
    setBusy(true);
    setError("");
    try {
      if (!rows.length)
        setRows((await getTimeSeriesRows(scenarioId, source.id)).rows);
      setStep(2);
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : String(failure));
    } finally {
      setBusy(false);
    }
  }
  async function saveRows() {
    if (!source || busy) return;
    setBusy(true);
    setError("");
    setPreview(null);
    setLocation(undefined);
    try {
      const saved = await saveTimeSeriesRows(scenarioId, source.id, rows);
      setSource(saved);
      onSourcePersisted(saved);
      setRowsDirty(false);
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : String(failure));
    } finally {
      setBusy(false);
    }
  }
  async function check() {
    if (!source || busy) return;
    setBusy(true);
    setError("");
    setPreview(null);
    try {
      setPreview(
        await previewTimeSeriesCatalogImport(scenarioId, source.id, payload),
      );
      setLocation(undefined);
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : String(failure));
      if (failure instanceof ApiError) setLocation(failure.location);
    } finally {
      setBusy(false);
    }
  }
  async function confirm() {
    if (!source || !preview || busy || created || uncertain) return;
    setBusy(true);
    setError("");
    try {
      setCreated(
        await importTimeSeriesSourceToCatalog(scenarioId, source.id, {
          ...payload,
          expected_preview_hash: preview.content_hash,
        }),
      );
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : String(failure));
      if (!(failure instanceof ApiError) || failure.status >= 500)
        setUncertain(true);
      if (failure instanceof ApiError && failure.status === 409) {
        setPreview(null);
        setRows([]);
        setStep(1);
      }
    } finally {
      setBusy(false);
    }
  }
  const columns = source?.columns ?? [];
  const complete =
    payload.set_name.trim() &&
    payload.timezone.trim() &&
    payload.timestamp_column &&
    payload.duration_hours_column &&
    payload.signal_mappings.every(
      (mapping) =>
        mapping.source_column && mapping.signal_key && mapping.source_unit,
    );
  if (options.isPending)
    return <p role="status">Consultando destinos de importación…</p>;
  if (options.isError)
    return (
      <div role="alert">
        No pudimos consultar el destino de importación.{" "}
        <button type="button" onClick={() => void options.refetch()}>
          Reintentar destinos
        </button>
      </div>
    );
  if (options.data.mode === "protected")
    return (
      <section aria-label="Importar series de tiempo">
        <h3>Importar series de tiempo</h3>
        <p>
          Elige el componente y su señal para crear una serie específica o
          actualizar una fuente compartida. El recorrido existente revisa el
          alcance y confirma la revisión antes de usarla.
        </p>
        <Link to={`/scenarios/${scenarioId}?section=data`}>
          Elegir la necesidad del modelo para importar
        </Link>
      </section>
    );
  return (
    <section
      ref={region}
      aria-labelledby="guided-import-title"
      className="guided-import"
    >
      <h3 id="guided-import-title">Importar series de tiempo</h3>
      <ol aria-label="Pasos de importación" className="import-steps">
        {["Archivo", "Columnas", "Revisión", "Importación"].map(
          (label, index) => (
            <li key={label} aria-current={step === index ? "step" : undefined}>
              {label}
            </li>
          ),
        )}
      </ol>
      <p>
        Destino: conjunto nuevo del proyecto. Importar permite reutilizar los
        datos; su uso en una variante se confirma después.
      </p>
      {source && !created && (
        <p role="status">
          Fuente temporal guardada: {source.original_filename} ({source.id}).
          Aún no se ha importado al catálogo.
        </p>
      )}
      {disabled && <p>Guarda los cambios del modelo antes de importar.</p>}
      {error && <p role="alert">{error}</p>}
      {uncertain && (
        <div role="alert">
          <p>
            No pudimos confirmar si se importó. Se conserva la revisión;
            comprueba el catálogo antes de volver a enviar.
          </p>
          <Link
            to={`/projects/${projectId}/time-series-sets`}
            target="_blank"
            rel="noopener"
          >
            Comprobar el catálogo
          </Link>
          <button type="button" onClick={() => setUncertain(false)}>
            Ya revisé el catálogo; permitir nuevo intento
          </button>
        </div>
      )}
      {error && location?.row && location.column && (
        <button
          type="button"
          onClick={() => {
            flushSync(() => {
              setStep(2);
              setPage(Math.max(0, Math.floor(((location.row ?? 2) - 2) / 50)));
            });
            const label = `Fila ${location.row}, ${location.column}`;
            const cell = Array.from(
              region.current?.querySelectorAll("input") ?? [],
            ).find((input) => input.getAttribute("aria-label") === label);
            cell?.focus();
          }}
        >
          Corregir {location.sheet ? `hoja ${location.sheet}, ` : ""}fila{" "}
          {location.row}, columna {location.column}
        </button>
      )}
      <fieldset disabled={disabled || busy}>
        {step === 0 && (
          <>
            {file && <p>{file.name}</p>}
            {source && (
              <button
                type="button"
                onClick={() => {
                  setFile(uploadedFile.current);
                  setError("");
                  setStep(1);
                }}
              >
                Continuar con la fuente guardada
              </button>
            )}
            <label className="field-row">
              <span>Archivo CSV o XLSX</span>
              <input
                type="file"
                accept=".csv,.xlsx"
                onChange={(event) => setFile(event.target.files?.[0] ?? null)}
              />
            </label>
            <button
              type="button"
              disabled={!file}
              onClick={() => void upload()}
            >
              Continuar a columnas
            </button>
          </>
        )}
        {step === 1 && (
          <>
            <h4>Hoja y columnas</h4>
            <p>
              Propuestas por coincidencia exacta: timestamp para fecha y hours
              para duración, cuando existen. Revisa los ejemplos y confirma las
              columnas; ninguna propuesta publica datos.
            </p>
            {catalog.isError && (
              <p role="alert">
                No pudimos consultar las señales.{" "}
                <button type="button" onClick={() => void catalog.refetch()}>
                  Reintentar señales
                </button>
              </p>
            )}
            {source?.kind === "xlsx" && (
              <label className="field-row">
                <span>Hoja</span>
                <select
                  value={source.selected_sheet ?? ""}
                  onChange={(event) => void upload(event.target.value)}
                >
                  {source.available_sheets?.map((sheet) => (
                    <option key={sheet}>{sheet}</option>
                  ))}
                </select>
              </label>
            )}
            <div className="draft-field-grid">
              <label className="field-row">
                <span>Nombre del conjunto</span>
                <input
                  value={payload.set_name}
                  onChange={(event) => update({ set_name: event.target.value })}
                />
              </label>
              <label className="field-row">
                <span>Zona horaria (IANA)</span>
                <input
                  value={payload.timezone}
                  onChange={(event) => update({ timezone: event.target.value })}
                />
              </label>
              <Column
                label="Columna de fecha y hora"
                columns={columns}
                value={payload.timestamp_column}
                onChange={(value) => update({ timestamp_column: value })}
              />
              <Column
                label="Columna de duración (horas)"
                columns={columns}
                value={payload.duration_hours_column}
                onChange={(value) => update({ duration_hours_column: value })}
              />
            </div>
            {payload.signal_mappings.map((mapping, index) => (
              <div className="draft-field-grid" key={index}>
                <Column
                  label={`Columna de valores ${index + 1}`}
                  columns={columns}
                  value={mapping.source_column}
                  onChange={(value) =>
                    update({
                      signal_mappings: payload.signal_mappings.map((item, i) =>
                        i === index ? { ...item, source_column: value } : item,
                      ),
                    })
                  }
                />
                <label className="field-row">
                  <span>Señal {index + 1}</span>
                  <select
                    value={mapping.signal_key}
                    onChange={(event) =>
                      update({
                        signal_mappings: payload.signal_mappings.map(
                          (item, i) =>
                            i === index
                              ? {
                                  ...item,
                                  signal_key: event.target.value,
                                  source_unit:
                                    catalog.data?.find(
                                      (entry) =>
                                        entry.signal_key === event.target.value,
                                    )?.unit ?? "",
                                }
                              : item,
                        ),
                      })
                    }
                  >
                    <option value="">Elegir señal</option>
                    {catalog.data?.map((entry) => (
                      <option key={entry.signal_key} value={entry.signal_key}>
                        {entry.signal_key} ({entry.unit})
                      </option>
                    ))}
                  </select>
                </label>
                <label className="field-row">
                  <span>Unidad de origen {index + 1}</span>
                  <input
                    value={mapping.source_unit ?? ""}
                    onChange={(event) =>
                      update({
                        signal_mappings: payload.signal_mappings.map(
                          (item, i) =>
                            i === index
                              ? { ...item, source_unit: event.target.value }
                              : item,
                        ),
                      })
                    }
                  />
                </label>
                {payload.signal_mappings.length > 1 && (
                  <button
                    type="button"
                    onClick={() =>
                      update({
                        signal_mappings: payload.signal_mappings.filter(
                          (_item, i) => i !== index,
                        ),
                      })
                    }
                  >
                    Quitar señal {index + 1}
                  </button>
                )}
              </div>
            ))}
            <button
              type="button"
              onClick={() =>
                update({
                  signal_mappings: [
                    ...payload.signal_mappings,
                    { source_column: "", signal_key: "", source_unit: "" },
                  ],
                })
              }
            >
              Agregar señal
            </button>
            <div
              className="time-series-table-scroll"
              tabIndex={0}
              role="region"
              aria-label="Ejemplos del archivo"
            >
              <table aria-label="Ejemplos de columnas seleccionadas">
                <thead>
                  <tr>
                    <th>Uso</th>
                    <th>Columna</th>
                    <th>Unidad y componente</th>
                    <th>Ejemplos (hasta 3)</th>
                  </tr>
                </thead>
                <tbody>
                  {[
                    {
                      label: "Fecha y hora",
                      column: payload.timestamp_column,
                      context: payload.timezone,
                    },
                    {
                      label: "Duración",
                      column: payload.duration_hours_column,
                      context: "horas",
                    },
                    ...payload.signal_mappings.map((mapping) => ({
                      label: mapping.signal_key || "Señal sin elegir",
                      column: mapping.source_column,
                      context: `${mapping.source_unit || "Unidad sin elegir"} · ${catalog.data?.find((entry) => entry.signal_key === mapping.signal_key)?.entity_type ?? "Global"}`,
                    })),
                  ].map((item, index) => (
                    <tr key={index}>
                      <th scope="row">{item.label}</th>
                      <td>{item.column || "Sin elegir"}</td>
                      <td>{item.context}</td>
                      <td>
                        {(rows.length ? rows : (source?.preview_rows ?? []))
                          .slice(0, 3)
                          .map((row) => String(row[item.column] ?? ""))
                          .join(" · ")}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p>
              La elección del componente concreto se confirma al usar la fuente
              en la variante. Los números usan punto decimal sin separadores de
              miles; no se convierten unidades ni se rellenan huecos.
            </p>
            <details>
              <summary>Metadatos del conjunto</summary>
              <label className="field-row">
                <span>Etiqueta de versión</span>
                <input
                  value={payload.version_label}
                  onChange={(event) =>
                    update({ version_label: event.target.value })
                  }
                />
              </label>
              <label className="field-row">
                <span>Clase de datos</span>
                <select
                  value={payload.data_kind}
                  onChange={(event) =>
                    update({
                      data_kind: event.target
                        .value as TimeSeriesCatalogImportPayload["data_kind"],
                    })
                  }
                >
                  <option value="real">Real</option>
                  <option value="forecast">Pronóstico</option>
                  <option value="programmed">Programada</option>
                  <option value="simulated">Simulada</option>
                  <option value="synthetic">Sintética</option>
                  <option value="mixed">Mixta</option>
                  <option value="derived">Derivada</option>
                </select>
              </label>
            </details>
            <button type="button" onClick={() => setStep(0)}>
              Volver a archivo
            </button>
            <button
              type="button"
              disabled={!complete}
              onClick={() => void review()}
            >
              Confirmar columnas y revisar
            </button>
          </>
        )}
        {step === 2 && (
          <>
            <h4>Revisar datos</h4>
            <p>
              Filas {page * 50 + 2}–{Math.min(rows.length, (page + 1) * 50) + 1}{" "}
              de {rows.length} filas de datos. La fila 1 contiene las cabeceras.
            </p>
            <div
              className="time-series-table-scroll"
              tabIndex={0}
              role="region"
              aria-label="Filas editables"
            >
              <table aria-label="Corregir datos de la fuente">
                <thead>
                  <tr>
                    <th>Fila del archivo</th>
                    {columns.map((column) => (
                      <th key={column}>{column}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {rows.slice(page * 50, (page + 1) * 50).map((row, offset) => {
                    const index = page * 50 + offset;
                    return (
                      <tr key={index}>
                        <th scope="row">{index + 2}</th>
                        {columns.map((column) => (
                          <td key={column}>
                            <input
                              aria-label={`Fila ${index + 2}, ${column}`}
                              value={String(row[column] ?? "")}
                              onChange={(event) => {
                                setRows((current) =>
                                  current.map((item, i) =>
                                    i === index
                                      ? {
                                          ...item,
                                          [column]: event.target.value,
                                        }
                                      : item,
                                  ),
                                );
                                setRowsDirty(true);
                                setPreview(null);
                              }}
                            />
                          </td>
                        ))}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <button
              type="button"
              disabled={page === 0}
              onClick={() => setPage((current) => current - 1)}
            >
              Filas anteriores
            </button>
            <button
              type="button"
              disabled={(page + 1) * 50 >= rows.length}
              onClick={() => setPage((current) => current + 1)}
            >
              Filas siguientes
            </button>
            {rowsDirty && (
              <p role="status">
                Correcciones sin guardar. Guarda la fuente temporal antes de
                comprobar.
              </p>
            )}
            <button
              type="button"
              disabled={!rowsDirty}
              onClick={() => void saveRows()}
            >
              Guardar correcciones en la fuente temporal
            </button>
            <button type="button" onClick={() => setStep(1)}>
              Volver a columnas
            </button>
            <button
              type="button"
              disabled={rowsDirty}
              onClick={() => void check()}
            >
              Comprobar datos
            </button>
          </>
        )}
        {preview && step >= 2 && (
          <>
            <p>
              {preview.period_count} períodos · {preview.coverage_start} →{" "}
              {preview.coverage_end} (fin exclusivo). Resolución:{" "}
              {preview.resolution_hours ?? "variable"} horas.
            </p>
            <p>
              Vista previa: {preview.rows.length} de {preview.period_count}{" "}
              filas.
            </p>
            <div
              className="time-series-table-scroll"
              tabIndex={0}
              role="region"
              aria-label="Valores revisados"
            >
              <table aria-label="Datos que se importarán">
                <thead>
                  <tr>
                    <th>Inicio</th>
                    {preview.signals.map((signal) => (
                      <th key={signal.signal_key}>
                        {signal.signal_key} ({signal.unit})
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {preview.rows.map((row, index) => (
                    <tr key={index}>
                      <td>{String(row.timestamp_start)}</td>
                      {preview.signals.map((signal) => (
                        <td key={signal.signal_key}>
                          {String(row[signal.signal_key])}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {step === 2 && (
              <button type="button" onClick={() => setStep(3)}>
                Continuar a importación
              </button>
            )}
          </>
        )}
        {step === 3 && !created && (
          <>
            <h4>Confirmar destino</h4>
            <p>
              Conjunto nuevo del proyecto: {payload.set_name}. Se creará la
              revisión 1. No se modifica una revisión existente.
            </p>
            <button type="button" onClick={() => setStep(2)}>
              Volver a revisión
            </button>
            <button
              type="button"
              disabled={uncertain}
              onClick={() => void confirm()}
            >
              Confirmar importación
            </button>
          </>
        )}
      </fieldset>
      {created && (
        <div role="status">
          <p>
            Datos importados: {created.name}, revisión {created.revision_number}
            .
          </p>
          <Link to={`/projects/${projectId}/time-series-sets/${created.id}`}>
            Abrir {created.name}
          </Link>
          <p>
            Falta elegir esta fuente en la variante y revisar el período de
            ejecución.
          </p>
          <Link to={`/scenarios/${scenarioId}?section=data`}>
            Volver a los datos del escenario
          </Link>
        </div>
      )}
      {busy && <p role="status">Procesando solicitud…</p>}
    </section>
  );
}
