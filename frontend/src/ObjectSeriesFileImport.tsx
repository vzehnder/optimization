import { useRef, useState } from "react";
import {
  ApiError,
  uploadObjectSeriesFile,
  mapObjectSeriesFile,
  previewObjectSeriesFile,
  type ObjectSeriesTarget,
  type IngestionReceipt,
} from "./api/client";

export function ObjectSeriesFileImport({
  target,
  signalId,
  seriesKey,
  revisionContract,
  onReady,
}: {
  target: ObjectSeriesTarget;
  signalId: number;
  seriesKey: string;
  revisionContract: Record<string, unknown>;
  onReady: (receipt: IngestionReceipt | null) => void;
}) {
  const [file, setFile] = useState<File | null>(null);
  const key = useRef(crypto.randomUUID());
  const [receipt, setReceipt] = useState<IngestionReceipt | null>(null);
  const [columns, setColumns] = useState({
    timestamp: "",
    duration: "",
    value: "",
  });
  const [sheet, setSheet] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [preview, setPreview] = useState<Awaited<
    ReturnType<typeof previewObjectSeriesFile>
  > | null>(null);
  function failedReceipt(failure: unknown) {
    if (!(failure instanceof ApiError)) return null;
    return (failure.context?.ingestion as IngestionReceipt | undefined) ?? null;
  }
  async function selectSheet(value: string) {
    if (!receipt || pending) return;
    setPending(true);
    setError("");
    setPreview(null);
    onReady(null);
    try {
      const result = await mapObjectSeriesFile(
        target,
        signalId,
        receipt.ingestion_id,
        { sheet_name: value, revision_contract: revisionContract },
      );
      setReceipt(result);
      setSheet(result.file?.selected_sheet ?? value);
      setColumns({ timestamp: "", duration: "", value: "" });
    } catch (failure) {
      const staged = failedReceipt(failure);
      if (staged?.file?.selected_sheet === value) {
        setReceipt(staged);
        setSheet(value);
        setColumns({ timestamp: "", duration: "", value: "" });
      } else
        setError(failure instanceof Error ? failure.message : String(failure));
    } finally {
      setPending(false);
    }
  }
  async function upload() {
    if (!file || pending) return;
    setPending(true);
    setError("");
    onReady(null);
    try {
      const result = await uploadObjectSeriesFile(
        target,
        signalId,
        file,
        key.current,
      );
      setReceipt(result);
      setSheet(result.file?.selected_sheet ?? "");
      setPreview(null);
    } catch (failure) {
      const staged = failedReceipt(failure);
      if (staged) setReceipt(staged);
      setError(failure instanceof Error ? failure.message : String(failure));
    } finally {
      setPending(false);
    }
  }
  async function validate() {
    if (!receipt || pending) return;
    setPending(true);
    setError("");
    setPreview(null);
    onReady(null);
    try {
      const result = await mapObjectSeriesFile(
        target,
        signalId,
        receipt.ingestion_id,
        {
          mode: "replace_full",
          expected_base: null,
          revision_contract: revisionContract,
          sheet_name: sheet || undefined,
          columns: {
            timestamp_start: columns.timestamp,
            duration_hours: columns.duration,
            signals: [{ series_key: seriesKey, value: columns.value }],
          },
          source: {
            kind: file?.name.toLowerCase().endsWith(".xlsx") ? "xlsx" : "csv",
            display_name: file?.name ?? "Archivo",
          },
        },
      );
      setReceipt(result);
      if (result.validation.valid && result.capabilities.publish) {
        setPreview(
          await previewObjectSeriesFile(target, signalId, result.ingestion_id),
        );
        onReady(result);
      } else
        setError(
          result.validation.errors
            .map((item) => item.message ?? item.code)
            .join("; "),
        );
    } catch (failure) {
      const staged = failedReceipt(failure);
      if (staged) setReceipt(staged);
      setError(failure instanceof Error ? failure.message : String(failure));
    } finally {
      setPending(false);
    }
  }
  function changeColumns(field: keyof typeof columns, value: string) {
    setColumns((current) => ({ ...current, [field]: value }));
    setPreview(null);
    onReady(null);
  }
  return (
    <section aria-label="Importar archivo para esta serie">
      <h3>Archivo → Columnas → Revisión</h3>
      <p>
        Destino: revisión de esta serie, solo para este objeto. La publicación
        se confirma en el paso de impacto.
      </p>
      <fieldset disabled={pending}>
        <label className="field-row">
          <span>Archivo para esta serie</span>
          <input
            type="file"
            accept=".csv,.xlsx"
            onChange={(event) => {
              setFile(event.target.files?.[0] ?? null);
              key.current = crypto.randomUUID();
              setReceipt(null);
              setColumns({ timestamp: "", duration: "", value: "" });
              setPreview(null);
              onReady(null);
            }}
          />
        </label>
        <button type="button" disabled={!file} onClick={() => void upload()}>
          Subir archivo temporal
        </button>
        {receipt?.file && (
          <>
            <p>
              Archivo temporal guardado: {receipt.file.original_filename}. Lote{" "}
              {receipt.ingestion_id}; todavía sin publicar.
            </p>
            {receipt.file.available_sheets.length > 0 && (
              <label className="field-row">
                <span>Hoja del archivo</span>
                <select
                  value={sheet}
                  onChange={(event) => void selectSheet(event.target.value)}
                >
                  <option value="" disabled>
                    Elegir hoja
                  </option>
                  {receipt.file.available_sheets.map((name) => (
                    <option key={name}>{name}</option>
                  ))}
                </select>
              </label>
            )}
            {(
              [
                ["timestamp", "Columna de inicio"],
                ["duration", "Columna de duración en horas"],
                ["value", "Columna de valor"],
              ] as const
            ).map(([field, label]) => (
              <label className="field-row" key={field}>
                <span>{label}</span>
                <select
                  value={columns[field]}
                  onChange={(event) => changeColumns(field, event.target.value)}
                >
                  <option value="">Elegir columna</option>
                  {receipt.file?.columns.map((column) => (
                    <option key={column}>{column}</option>
                  ))}
                </select>
              </label>
            ))}
            <button
              type="button"
              disabled={
                !columns.timestamp || !columns.duration || !columns.value
              }
              onClick={() => void validate()}
            >
              Confirmar columnas y validar archivo
            </button>
          </>
        )}
      </fieldset>
      {pending && <p role="status">Validando archivo…</p>}
      {error && <p role="alert">{error}</p>}
      {error &&
        receipt?.validation.errors.map((issue, index) => (
          <p key={index} role="alert">
            {issue.location?.sheet ? `Hoja ${issue.location.sheet}, ` : ""}
            {issue.location?.source_row_number
              ? `fila ${issue.location.source_row_number}, `
              : ""}
            {issue.location?.column ? `columna ${issue.location.column}: ` : ""}
            {issue.message ?? issue.code}
          </p>
        ))}
      {file && (
        <p>
          Al salir, las decisiones locales se pierden. El archivo temporal
          guardado permanece sin publicar hasta que se confirme el impacto. Para
          cambiar valores, corrige el archivo y vuelve a subirlo; también puedes
          corregir las columnas de este lote.
        </p>
      )}
      {preview && (
        <>
          <p>
            Vista previa: {preview.returned_row_count} de{" "}
            {preview.source_row_count} filas.
          </p>
          <div className="time-series-table-scroll">
            <table aria-label="Revisión del archivo">
              <thead>
                <tr>
                  <th>Inicio</th>
                  <th>Valor</th>
                </tr>
              </thead>
              <tbody>
                {preview.rows.map((row, i) => (
                  <tr key={i}>
                    <td>{String(row.timestamp_start)}</td>
                    <td>{String(row.value)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </section>
  );
}
