import { useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ApiError,
  getCsrfToken,
  listHydraulicPrices,
  requestJson,
  type ScenarioRun,
} from "./api/client";
import type { components } from "./api/schema";
import { RunProgressPanel } from "./RunProgress";

type Mesa = components["schemas"]["MesaResponse"];
type Preparation = components["schemas"]["MesaHydraulicRequest"];
type RunRequest = components["schemas"]["MesaHydraulicRunRequest"];
type Sources = components["schemas"]["MesaHydraulicSources"];
type Preview = {
  preparation_hash: string;
  period_count: number;
  preview_periods: Array<{
    timestamp: string;
    duration_hours: number;
    price_usd_per_mwh?: number;
    natural_inflow_m3s: Record<string, number>;
    minimum_flow_m3s?: Record<string, number>;
  }>;
  generation_metadata: {
    date_range: { start: string; end: string };
    source_scenario_version_id: number;
    hydraulic_simulation: { objective: string; resolution_hours: number };
  };
};
type MesaRun = ScenarioRun & {
  materialized_lineage?: { mesa_hydraulic_execution?: Preparation };
};
const statuses: Record<string, string> = {
  queued: "En cola",
  running: "En ejecución",
  succeeded: "Completada",
  failed: "Fallida",
};

async function post<T>(path: string, payload: unknown) {
  return requestJson<T>(path, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRF-Token": await getCsrfToken(),
    },
    body: JSON.stringify(payload),
  });
}

export function MesaHydraulicExecution({
  data,
  editing,
  onResults,
}: {
  data: Mesa;
  editing: boolean;
  onResults: (id: number) => void;
}) {
  const { scenario_id: scenarioId, case_id: caseId } = data.context;
  const path = `/api/scenarios/${scenarioId}/mesa/hydraulic-execution`;
  const queryClient = useQueryClient();
  const sources = useQuery({
    queryKey: ["mesa-hydraulic-sources", scenarioId, caseId],
    queryFn: ({ signal }) =>
      requestJson<Sources>(`${path}/sources?case_id=${caseId}`, { signal }),
    refetchOnWindowFocus: false,
    retry: false,
  });
  const prices = useQuery({
    queryKey: ["hydraulic-simulation-prices", scenarioId],
    queryFn: ({ signal }) => listHydraulicPrices(scenarioId, signal),
    retry: false,
  });
  const runKey = ["mesa-hydraulic-execution", scenarioId, caseId];
  const state = useQuery({
    queryKey: runKey,
    queryFn: ({ signal }) =>
      requestJson<{ run: MesaRun | null }>(`${path}?case_id=${caseId}`, {
        signal,
      }),
    refetchInterval: (q) =>
      !q.state.data?.run ||
      ["queued", "running"].includes(q.state.data.run.status)
        ? 1500
        : false,
    refetchOnWindowFocus: false,
    retry: false,
  });
  const [form, setForm] = useState<Preparation | null>(null);
  const [prepared, setPrepared] = useState<{
    preview: Preview;
    request: RunRequest;
    source: string;
  } | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const busy = useRef(false);
  const run = state.data?.run;
  const active = !!run && ["queued", "running"].includes(run.status);
  const source = sources.data?.sources.find(
    (s) => s.id === form?.source_scenario_version_id,
  );
  const signature = JSON.stringify(
    data.components.map((c) => [
      c.entity_id,
      c.parameters,
      c.series.role === "output" ? null : c.series,
    ]),
  );
  const valid = !!prepared && prepared.source === signature && !editing;
  const executed = run?.materialized_lineage?.mesa_hydraulic_execution;

  function change(changes: Partial<Preparation>) {
    setForm((previous) => (previous ? { ...previous, ...changes } : null));
    setPrepared(null);
    setError("");
  }
  function selectSource(id: number) {
    const chosen = sources.data?.sources.find((s) => s.id === id);
    setPrepared(null);
    setError("");
    setForm(
      chosen
        ? {
            case_id: caseId,
            source_scenario_version_id: id,
            range_start: chosen.range_start,
            range_end: chosen.range_end,
            resolution_hours: chosen.resolution_hours,
            objective: "market_value",
            terminal_water_values_usd_per_hm3:
              chosen.terminal_water_values_usd_per_hm3,
            mip_rel_gap: chosen.mip_rel_gap,
            price_signal_key: "price_usd_per_mwh",
            price_time_series_set_id: null,
          }
        : null,
    );
  }
  async function validate() {
    if (busy.current || !form) return;
    busy.current = true;
    setPending(true);
    setError("");
    setPrepared(null);
    try {
      const preview = await post<Preview>(path + "/preview", form);
      setPrepared({
        preview,
        source: signature,
        request: {
          ...form,
          expected_preparation_hash: preview.preparation_hash,
          idempotency_key: crypto.randomUUID(),
        },
      });
    } catch (failure) {
      setError((failure as Error).message);
    } finally {
      busy.current = false;
      setPending(false);
    }
  }
  async function execute() {
    if (busy.current || !prepared || !valid) return;
    busy.current = true;
    setPending(true);
    setError("");
    try {
      const accepted = await post<MesaRun>(path + "/runs", prepared.request);
      queryClient.setQueryData(runKey, { run: accepted });
      setPrepared(null);
      void state.refetch();
    } catch (failure) {
      setError((failure as Error).message);
      if (failure instanceof ApiError && failure.status === 409)
        setPrepared(null);
      void state.refetch();
    } finally {
      busy.current = false;
      setPending(false);
    }
  }
  const priceOptions = (prices.data ?? []).flatMap((p) =>
    p.signals
      .filter((s) =>
        ["price_usd_per_mwh", "export_price_usd_per_mwh"].includes(
          s.signal_key,
        ),
      )
      .map((s) => ({
        value: `${p.id}:${s.signal_key}`,
        label: `${p.name} · v${p.version_number} · ${s.signal_key === "export_price_usd_per_mwh" ? "Venta" : "CMg"}`,
      })),
  );
  const incompatibleWater =
    form?.objective === "energy" &&
    Object.values(form.terminal_water_values_usd_per_hm3 ?? {}).some(
      (v) => v > 0,
    );
  return (
    <section
      className="mesa-execution"
      aria-label="Ejecución de red hidráulica"
    >
      <div className="mesa-execution-summary">
        <details className="mesa-execution-form">
          <summary>Preparar ejecución hidráulica</summary>
          <p>
            Red v3 · Entradas de la versión fuente. Los cambios actuales del
            diagrama o de la variante requieren otra versión promovida para
            participar en esta ejecución.
          </p>
          {sources.isPending && (
            <p role="status">Cargando versiones de la red…</p>
          )}
          {sources.isError && (
            <p role="alert">
              No se pudieron cargar las versiones.{" "}
              <button onClick={() => void sources.refetch()}>
                Reintentar versiones
              </button>
            </p>
          )}
          {sources.data?.sources.length === 0 && (
            <p role="status">
              No hay versiones v3. Valida y promueve la red desde el diagrama
              hidráulico del escenario.
            </p>
          )}
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void validate();
            }}
          >
            <fieldset disabled={pending || editing || active}>
              <label>
                Versión fuente de la red
                <select
                  value={form?.source_scenario_version_id ?? ""}
                  required
                  onChange={(e) => selectSource(Number(e.target.value))}
                >
                  <option value="">Selecciona una versión v3</option>
                  {sources.data?.sources.map((s) => (
                    <option key={s.id} value={s.id}>
                      Versión {s.version_number} · #{s.id}
                    </option>
                  ))}
                </select>
              </label>
              <button type="button" onClick={() => void sources.refetch()}>
                Actualizar versiones
              </button>
              {form && (
                <>
                  <label>
                    Inicio hidráulico (UTC)
                    <input
                      type="datetime-local"
                      required
                      value={form.range_start.slice(0, 16)}
                      onChange={(e) =>
                        change({ range_start: `${e.target.value}:00Z` })
                      }
                    />
                  </label>
                  <label>
                    Fin hidráulico exclusivo (UTC)
                    <input
                      type="datetime-local"
                      required
                      value={form.range_end.slice(0, 16)}
                      onChange={(e) =>
                        change({ range_end: `${e.target.value}:00Z` })
                      }
                    />
                  </label>
                  <label>
                    Resolución hidráulica (horas)
                    <input
                      type="number"
                      required
                      min="0.000001"
                      step="any"
                      value={form.resolution_hours}
                      onChange={(e) =>
                        change({ resolution_hours: Number(e.target.value) })
                      }
                    />
                  </label>
                  <label>
                    Objetivo hidráulico
                    <select
                      value={form.objective ?? "market_value"}
                      onChange={(e) =>
                        change({
                          objective: e.target.value as Preparation["objective"],
                          price_time_series_set_id: null,
                        })
                      }
                    >
                      <option value="market_value">
                        Ingresos con CMg (USD)
                      </option>
                      <option value="energy">Energía (MWh)</option>
                    </select>
                  </label>
                  {form.objective === "market_value" && (
                    <label>
                      CMg para la ejecución
                      <select
                        required
                        value={
                          form.price_time_series_set_id
                            ? `${form.price_time_series_set_id}:${form.price_signal_key}`
                            : ""
                        }
                        onChange={(e) => {
                          const [id, key] = e.target.value.split(":");
                          change({
                            price_time_series_set_id: Number(id),
                            price_signal_key:
                              key as Preparation["price_signal_key"],
                          });
                        }}
                      >
                        <option value="">Selecciona CMg</option>
                        {priceOptions.map((p) => (
                          <option key={p.value} value={p.value}>
                            {p.label}
                          </option>
                        ))}
                      </select>
                    </label>
                  )}
                  <label>
                    Gap relativo hidráulico
                    <input
                      type="number"
                      required
                      min="0"
                      step="any"
                      value={form.mip_rel_gap ?? 0.0001}
                      onChange={(e) =>
                        change({ mip_rel_gap: Number(e.target.value) })
                      }
                    />
                  </label>
                  {Object.entries(
                    form.terminal_water_values_usd_per_hm3 ?? {},
                  ).map(([id, value]) => (
                    <label key={id}>
                      Valor terminal {id} (USD/hm³)
                      <input
                        type="number"
                        required
                        min="0"
                        step="any"
                        value={value}
                        onChange={(e) =>
                          change({
                            terminal_water_values_usd_per_hm3: {
                              ...form.terminal_water_values_usd_per_hm3,
                              [id]: Number(e.target.value),
                            },
                          })
                        }
                      />
                    </label>
                  ))}
                </>
              )}
            </fieldset>
            {source && (
              <>
                <p>
                  Fuente #{source.id} · Cobertura: {source.range_start} →{" "}
                  {source.range_end} · [inicio, fin exclusivo), UTC. Resolución
                  original: {source.resolution_hours} h.
                </p>
                <details>
                  <summary>
                    Componentes incluidos ({source.components.length})
                  </summary>
                  <ul>
                    {source.components.map((c) => (
                      <li key={`${c.component_type}:${c.entity_id}`}>
                        {c.name} · {c.entity_id} · {c.component_type}
                      </li>
                    ))}
                  </ul>
                </details>
              </>
            )}
            <p>
              Remuestreo explícito: aportes y CMg por promedio ponderado por
              duración; caudales mínimos por máximo; pasos más finos conservan
              el valor de origen. Entre 1 y 100000 intervalos completos.
            </p>
            {prices.isError && (
              <p role="alert">
                No se pudo cargar el CMg.{" "}
                <button type="button" onClick={() => void prices.refetch()}>
                  Reintentar CMg
                </button>
              </p>
            )}
            {incompatibleWater && (
              <p role="alert">
                El objetivo energético requiere valores terminales del agua
                iguales a cero.
              </p>
            )}
            {editing && (
              <p role="status">
                Guarda o descarta los cambios pendientes antes de validar.
              </p>
            )}
            {prepared && !valid && (
              <p role="status">
                La entrada cambió. Preparación pendiente de revalidación.
              </p>
            )}
            {valid && (
              <div role="status">
                <p>
                  Preparación válida · {prepared.preview.period_count}{" "}
                  intervalos · Cobertura completa · UTC
                  <br />
                  {prepared.preview.generation_metadata.date_range.start} →{" "}
                  {prepared.preview.generation_metadata.date_range.end} (fin
                  exclusivo)
                </p>
                <div
                  className="mesa-table-scroll"
                  tabIndex={0}
                  role="region"
                  aria-label="Intervalos preparados de la red"
                >
                  <table aria-label="Vista previa hidráulica">
                    <thead>
                      <tr>
                        <th>Inicio UTC</th>
                        <th>Horas</th>
                        <th>Aportes (m³/s)</th>
                        <th>Mínimos (m³/s)</th>
                        <th>CMg (USD/MWh)</th>
                      </tr>
                    </thead>
                    <tbody>
                      {prepared.preview.preview_periods.map((p) => (
                        <tr key={p.timestamp}>
                          <td>{p.timestamp}</td>
                          <td>{p.duration_hours}</td>
                          <td>
                            {Object.entries(p.natural_inflow_m3s)
                              .map(([id, v]) => `${id}: ${v}`)
                              .join("; ")}
                          </td>
                          <td>
                            {Object.entries(p.minimum_flow_m3s ?? {})
                              .map(([id, v]) => `${id}: ${v}`)
                              .join("; ") || "—"}
                          </td>
                          <td>{p.price_usd_per_mwh ?? "No aplica"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {prepared.preview.period_count > 12 && (
                  <p>
                    Vista previa: primeros 12 intervalos; la ejecución incluye
                    todos.
                  </p>
                )}
              </div>
            )}
            <div className="mesa-execution-actions">
              <button
                type="submit"
                disabled={
                  !form || pending || editing || active || incompatibleWater
                }
              >
                Validar red hidráulica
              </button>
              <button
                type="button"
                disabled={
                  !valid ||
                  pending ||
                  active ||
                  state.isPending ||
                  state.isError
                }
                onClick={() => void execute()}
              >
                Ejecutar red hidráulica
              </button>
              {pending && <span role="status">Validando y preparando…</span>}
            </div>
          </form>
        </details>
        <span aria-live="polite">
          {run ? (
            <>
              <strong>Ejecución hidráulica #{run.id}</strong> ·{" "}
              {statuses[run.status] ?? run.status}
            </>
          ) : (
            "Sin ejecución hidráulica desde la mesa"
          )}
        </span>
        {run?.status === "succeeded" && (
          <button type="button" onClick={() => onResults(run.id)}>
            Ver resultados hidráulicos en la mesa
          </button>
        )}
      </div>
      {error && (
        <p role="alert">
          {error} Revisa la preparación o reintenta la misma solicitud.
        </p>
      )}
      {state.isError && (
        <p role="alert">
          No se pudo actualizar el avance hidráulico. La ejecución se conserva.{" "}
          <button onClick={() => void state.refetch()}>
            Reintentar conexión hidráulica
          </button>
        </p>
      )}
      {run?.status === "failed" && (
        <p role="alert">
          La ejecución hidráulica falló:{" "}
          {run.error_message || "No se obtuvieron resultados."} Revisa las
          entradas y vuelve a validar.
        </p>
      )}
      {run && (
        <details className="mesa-execution-progress">
          <summary>Ver avance y log hidráulico</summary>
          {executed && (
            <p>
              Fuente #{executed.source_scenario_version_id} · Período del run:{" "}
              {executed.range_start} → {executed.range_end} (fin exclusivo) ·{" "}
              {executed.resolution_hours} h · Objetivo {executed.objective}
            </p>
          )}
          <RunProgressPanel run={run} updatedAt={state.dataUpdatedAt} />
        </details>
      )}
    </section>
  );
}
