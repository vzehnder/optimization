import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";
import {
  listHydraulicPrices,
  previewHydraulicSimulation,
  runHydraulicSimulation,
  importHydraulicPrices,
  type HydraulicSimulationPreview,
  type HydraulicSimulationRequest,
  type ScenarioVersionDetail,
} from "../api/client";

interface HydraulicDocument {
  time_series?: Array<{ timestamp: string; duration_hours: number }>;
  solver?: { options?: { mip_rel_gap?: number } };
  hydraulic_network?: {
    nodes?: Array<{
      id: string;
      name?: string;
      type: string;
      reservoir?: {
        terminal_water_value_usd_per_hm3?: number;
        terminal_condition?: string;
      };
    }>;
  };
}

function utcDate(value: string) {
  return new Date(/[zZ]|[+-]\d\d:\d\d$/.test(value) ? value : `${value}Z`);
}

export function HydraulicSimulationForm({
  version,
  projectId,
}: {
  version: ScenarioVersionDetail;
  projectId: number;
}) {
  const navigate = useNavigate();
  const document = version.system_case_json as HydraulicDocument;
  const periods = document.time_series ?? [];
  const reservoirs = (document.hydraulic_network?.nodes ?? []).filter(
    (node) => node.type === "reservoir",
  );
  const last = periods.at(-1);
  const [start, setStart] = useState(() =>
    periods.length
      ? utcDate(periods[0].timestamp).toISOString().slice(0, 16)
      : "",
  );
  const [end, setEnd] = useState(() =>
    last
      ? new Date(
          utcDate(last.timestamp).getTime() + last.duration_hours * 3600000,
        )
          .toISOString()
          .slice(0, 16)
      : "",
  );
  const [resolution, setResolution] = useState(
    String(periods[0]?.duration_hours ?? 1),
  );
  const [objective, setObjective] =
    useState<HydraulicSimulationRequest["objective"]>("market_value");
  const [price, setPrice] = useState("");
  const [waterValues, setWaterValues] = useState<Record<string, string>>(() =>
    Object.fromEntries(
      reservoirs.map((node) => [
        node.id,
        String(node.reservoir?.terminal_water_value_usd_per_hm3 ?? 0),
      ]),
    ),
  );
  const [relativeGapPercent, setRelativeGapPercent] = useState(() =>
    String(
      Number(
        ((document.solver?.options?.mip_rel_gap ?? 0.0001) * 100).toPrecision(
          12,
        ),
      ),
    ),
  );
  const [preview, setPreview] = useState<HydraulicSimulationPreview | null>(
    null,
  );
  const [error, setError] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [seriesName, setSeriesName] = useState("");
  const [timezone, setTimezone] = useState("UTC");
  const [dataKind, setDataKind] = useState("forecast");
  const sets = useQuery({
    queryKey: ["hydraulic-simulation-prices", version.scenario_id],
    queryFn: ({ signal }) => listHydraulicPrices(version.scenario_id, signal),
    enabled: projectId > 0,
  });
  const options = (sets.data ?? []).flatMap((set) =>
    set.signals
      .filter((signal) =>
        ["price_usd_per_mwh", "export_price_usd_per_mwh"].includes(
          signal.signal_key,
        ),
      )
      .map((signal) => ({
        value: `${set.id}:${signal.signal_key}`,
        label: `${set.name} · v${set.version_number} · ${signal.signal_key === "export_price_usd_per_mwh" ? "Venta" : "CMg"}`,
      })),
  );
  function changed() {
    setPreview(null);
    setError("");
  }
  function payload(): HydraulicSimulationRequest {
    const [id, signal] = price.split(":");
    return {
      range_start: new Date(`${start}Z`).toISOString(),
      range_end: new Date(`${end}Z`).toISOString(),
      resolution_hours: Number(resolution),
      objective,
      terminal_water_values_usd_per_hm3: Object.fromEntries(
        Object.entries(waterValues).map(([id, value]) => [id, Number(value)]),
      ),
      mip_rel_gap: Number(relativeGapPercent) / 100,
      ...(objective === "market_value"
        ? {
            price_time_series_set_id: Number(id),
            price_signal_key:
              signal as HydraulicSimulationRequest["price_signal_key"],
          }
        : {}),
    };
  }
  const review = useMutation({
    mutationFn: () => previewHydraulicSimulation(version.id, payload()),
    onSuccess: (data) => {
      setPreview(data);
      setError("");
    },
    onError: (error) => {
      setPreview(null);
      setError(error.message);
    },
  });
  const run = useMutation({
    mutationFn: () =>
      runHydraulicSimulation(version.id, {
        ...payload(),
        expected_preparation_hash: preview!.preparation_hash,
      }),
    onSuccess: (result) => navigate(`/runs/${result.id}`),
    onError: (error) => {
      setPreview(null);
      setError(error.message);
    },
  });
  const importPrices = useMutation({
    mutationFn: () =>
      importHydraulicPrices(
        version.scenario_id,
        file!,
        seriesName,
        timezone,
        dataKind,
      ),
    onSuccess: async (result) => {
      await sets.refetch();
      changed();
      setPrice(`${result.id}:price_usd_per_mwh`);
    },
    onError: (error) => setError(error.message),
  });
  const busy = review.isPending || run.isPending || importPrices.isPending;
  const validNonnegative = (value: string) =>
    value.trim() !== "" && Number.isFinite(Number(value)) && Number(value) >= 0;
  const incompatibleWaterValue =
    objective === "energy" &&
    Object.values(waterValues).some((value) => Number(value) > 0);
  const valid = Boolean(
    start &&
    end &&
    Number(resolution) > 0 &&
    (objective === "energy" || price) &&
    validNonnegative(relativeGapPercent) &&
    Object.values(waterValues).every(validNonnegative) &&
    !incompatibleWaterValue,
  );
  return (
    <section
      className="workspace-section"
      aria-labelledby="hydraulic-simulation-heading"
    >
      <h2 id="hydraulic-simulation-heading">Preparar simulación hidráulica</h2>
      <p>
        Red y parámetros de la versión {version.version_number}. Los afluentes
        provienen de esta versión. Cada ejecución guarda el período, la
        resolución y las series utilizadas.
      </p>
      <fieldset disabled={busy} className="workspace-form">
        <legend>Configuración de la corrida</legend>
        <label htmlFor="hydro-objective">Objetivo</label>
        <select
          id="hydro-objective"
          value={objective}
          onChange={(e) => {
            changed();
            setObjective(
              e.target.value as HydraulicSimulationRequest["objective"],
            );
          }}
        >
          <option value="market_value">Optimizar ingresos con CMg</option>
          <option value="energy">Maximizar energía</option>
        </select>
        {objective === "market_value" && (
          <>
            <label htmlFor="hydro-price">CMg (USD/MWh)</label>
            <select
              id="hydro-price"
              value={price}
              onChange={(e) => {
                changed();
                setPrice(e.target.value);
              }}
            >
              <option value="">Seleccionar serie de CMg</option>
              {options.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
            <p className="source-note">
              Este CMg se aplica a la generación de todas las centrales de la
              red.
            </p>
            <details>
              <summary>Importar CMg desde Excel o CSV</summary>
              <div className="workspace-form">
                <p>
                  Archivo .xlsx o .csv con columnas <code>timestamp</code>,{" "}
                  <code>duration_hours</code> y <code>price_usd_per_mwh</code>.
                  En Excel se lee la primera hoja. Usa fechas ISO; los precios
                  pueden ser negativos.
                </p>
                <label htmlFor="hydro-price-name">
                  Nombre de la serie de CMg
                </label>
                <input
                  id="hydro-price-name"
                  value={seriesName}
                  onChange={(e) => setSeriesName(e.target.value)}
                />
                <label htmlFor="hydro-price-timezone">
                  Zona horaria del archivo
                </label>
                <input
                  id="hydro-price-timezone"
                  value={timezone}
                  onChange={(e) => setTimezone(e.target.value)}
                  placeholder="UTC o America/Santiago"
                />
                <label htmlFor="hydro-price-kind">Tipo de datos de CMg</label>
                <select
                  id="hydro-price-kind"
                  value={dataKind}
                  onChange={(e) => setDataKind(e.target.value)}
                >
                  <option value="forecast">Pronóstico</option>
                  <option value="real">Histórico real</option>
                  <option value="synthetic">Ejemplo sintético</option>
                </select>
                <label htmlFor="hydro-price-file">Archivo de CMg</label>
                <input
                  id="hydro-price-file"
                  type="file"
                  accept=".csv,.xlsx"
                  onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                />
                <button
                  type="button"
                  disabled={!file || !seriesName.trim() || !timezone.trim()}
                  onClick={() => importPrices.mutate()}
                >
                  {importPrices.isPending
                    ? "Importando…"
                    : "Guardar CMg en catálogo"}
                </button>
              </div>
            </details>
            {sets.isError && (
              <p role="alert">
                No se pudieron cargar las series de CMg.{" "}
                <button type="button" onClick={() => void sets.refetch()}>
                  Reintentar
                </button>
              </p>
            )}
          </>
        )}
        <fieldset className="workspace-form">
          <legend>Valor del agua al final del período</legend>
          <p className="source-note">
            En la optimización con CMg se suma el valor del agua (USD/hm³)
            multiplicado por el volumen final de cada embalse (hm³), una sola
            vez al cierre. Un valor mayor favorece reservar agua para después
            del período; 0 no agrega valor terminal. 1 hm³ = 1.000.000 m³.
          </p>
          {reservoirs.map((node) => (
            <div key={node.id}>
              <label htmlFor={`hydro-water-${node.id}`}>
                Valor del agua · {node.name || node.id} (USD/hm³)
              </label>
              <input
                id={`hydro-water-${node.id}`}
                type="number"
                min="0"
                step="any"
                value={waterValues[node.id]}
                onChange={(event) => {
                  changed();
                  setWaterValues({
                    ...waterValues,
                    [node.id]: event.target.value,
                  });
                }}
              />
              {node.reservoir?.terminal_condition === "equal_initial" && (
                <p className="source-note">
                  El volumen final de este embalse está fijado al inicial: su
                  valor terminal es constante y no cambia el despacho.
                </p>
              )}
              {node.reservoir?.terminal_condition === "min_terminal" && (
                <p className="source-note">
                  Se conserva el volumen mínimo final configurado.
                </p>
              )}
            </div>
          ))}
          {incompatibleWaterValue && (
            <p role="alert">
              Para usar valores del agua positivos, selecciona «Optimizar
              ingresos con CMg». Para maximizar energía, usa valores iguales a
              cero.
            </p>
          )}
        </fieldset>
        <fieldset className="workspace-form">
          <legend>Criterio de parada de la optimización</legend>
          <label htmlFor="hydro-relative-gap">Gap relativo de parada (%)</label>
          <input
            id="hydro-relative-gap"
            type="number"
            min="0"
            step="any"
            value={relativeGapPercent}
            onChange={(event) => {
              changed();
              setRelativeGapPercent(event.target.value);
            }}
          />
          <p className="source-note">
            Ejemplo: 1 significa 1 %. Se puede detener cuando la brecha entre la
            mejor solución factible y la cota del óptimo alcanza esta
            tolerancia. Aplica a modelos con variables enteras; un modelo
            continuo usa sus propias tolerancias. También puede detenerse por
            otros límites configurados, como tiempo máximo.
          </p>
        </fieldset>
        <label htmlFor="hydro-start">Inicio (UTC)</label>
        <input
          id="hydro-start"
          type="datetime-local"
          value={start}
          onChange={(e) => {
            changed();
            setStart(e.target.value);
          }}
        />
        <label htmlFor="hydro-end">Fin excluido (UTC)</label>
        <input
          id="hydro-end"
          type="datetime-local"
          value={end}
          onChange={(e) => {
            changed();
            setEnd(e.target.value);
          }}
        />
        <label htmlFor="hydro-resolution">Resolución (horas)</label>
        <input
          id="hydro-resolution"
          type="number"
          min="0.0001"
          step="any"
          value={resolution}
          onChange={(e) => {
            changed();
            setResolution(e.target.value);
          }}
        />
        <p className="source-note">
          Ejemplos: 0,25 = 15 minutos; 1 = una hora; 24 = un día. Al agrupar, se
          promedian afluentes y CMg por duración. Los caudales mínimos usan el
          máximo del intervalo. Al subdividir, se repite el valor original.
        </p>
        <p>
          Los volúmenes y caudales iniciales de la versión se aplican al inicio
          elegido. Las llegadas de agua programadas conservan sus fechas. Para
          cambiar estas condiciones, edita el{" "}
          <Link to={`/scenarios/${version.scenario_id}/hydraulic-diagram`}>
            diagrama hidráulico
          </Link>{" "}
          y promueve otra versión.
        </p>
        <div className="workspace-actions">
          <button
            type="button"
            disabled={!valid}
            onClick={() => {
              setPreview(null);
              review.mutate();
            }}
          >
            {review.isPending ? "Revisando…" : "Revisar simulación"}
          </button>
          <button
            type="button"
            disabled={!preview}
            onClick={() => run.mutate()}
          >
            {run.isPending ? "Lanzando…" : "Ejecutar simulación"}
          </button>
        </div>
      </fieldset>
      {error && <p role="alert">{error}</p>}
      {preview && (
        <div role="status">
          <p>
            <strong>{preview.period_count} períodos preparados</strong>
          </p>
          <p>
            {objective === "market_value"
              ? "Optimización de ingresos con CMg"
              : "Maximización de energía"}{" "}
            · Paso: {resolution} h · {start} a {end} UTC (fin excluido).
          </p>
          <p>Gap relativo de parada: {relativeGapPercent} %.</p>
          {reservoirs.map((node) => (
            <p key={node.id}>
              Valor del agua · {node.name || node.id}: {waterValues[node.id]}{" "}
              USD/hm³.
            </p>
          ))}
          <details>
            <summary>Ver primeros períodos</summary>
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>Inicio UTC</th>
                    <th>Horas</th>
                    <th>CMg USD/MWh</th>
                    <th>Afluentes m³/s</th>
                  </tr>
                </thead>
                <tbody>
                  {preview.preview_periods.map((row) => (
                    <tr key={row.timestamp}>
                      <td>{row.timestamp}</td>
                      <td>{row.duration_hours}</td>
                      <td>{row.price_usd_per_mwh ?? "—"}</td>
                      <td>
                        {Object.entries(row.natural_inflow_m3s)
                          .map(([id, value]) => `${id}: ${value}`)
                          .join("; ")}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>
        </div>
      )}
    </section>
  );
}
