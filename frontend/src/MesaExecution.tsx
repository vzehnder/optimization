import { useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ApiError,
  getCsrfToken,
  requestJson,
  type ScenarioRun,
} from "./api/client";
import type { components } from "./api/schema";
import { RunProgressPanel } from "./RunProgress";
import {
  executionChartRange,
  initialExecutionWindow,
} from "./mesaExecutionRange";
import type { ChartRange } from "./mesaChartAggregation";

type Mesa = components["schemas"]["MesaResponse"];
type Preparation = components["schemas"]["MesaExecutionRequest"];
type Preview = components["schemas"]["MesaExecutionPreview"];
type RunRequest = components["schemas"]["MesaExecutionRunRequest"];
type Prepared = { preview: Preview; request: RunRequest; source: string };
type MesaRun = ScenarioRun & {
  materialized_lineage?: { mesa_execution?: Preparation };
};

async function post<T>(path: string, payload: unknown): Promise<T> {
  return requestJson<T>(path, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRF-Token": await getCsrfToken(),
    },
    body: JSON.stringify(payload),
  });
}

const statuses: Record<string, string> = {
  queued: "En cola",
  running: "En ejecución",
  succeeded: "Completada",
  failed: "Fallida",
};

export function MesaExecution({
  data,
  editing,
  onResults,
  onRangeChange,
}: {
  data: Mesa;
  editing: boolean;
  onResults: (runId: number) => void;
  onRangeChange: (range: ChartRange) => void;
}) {
  const context = data.context;
  const [form, setForm] = useState<Preparation>(() => ({
    case_id: context.case_id,
    variant_id: context.variant_id,
    ...initialExecutionWindow(data),
  }));
  const [prepared, setPrepared] = useState<Prepared | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const busyRef = useRef(false);
  const queryClient = useQueryClient();
  const path = `/api/scenarios/${context.scenario_id}/mesa/execution`;
  const queryKey = [
    "mesa-execution",
    context.scenario_id,
    context.case_id,
    context.variant_id,
  ];
  const state = useQuery({
    queryKey,
    queryFn: ({ signal }) =>
      requestJson<{ run: MesaRun | null }>(
        `${path}?case_id=${context.case_id}&variant_id=${context.variant_id}`,
        { signal },
      ),
    refetchInterval: (query) =>
      !query.state.data?.run ||
      ["queued", "running"].includes(query.state.data.run.status)
        ? 1500
        : false,
    refetchOnWindowFocus: false,
    retry: false,
  });
  const run = state.data?.run;
  const executed = run?.materialized_lineage?.mesa_execution;
  const active = !!run && ["queued", "running"].includes(run.status);
  const sourceSignature = JSON.stringify(
    data.components
      .filter((c) => c.entity_type !== "manual_series")
      .map((c) => [
        c.entity_id,
        c.parameters,
        c.series,
        ...(c.additional_series ?? []).filter((s) => s.role !== "output"),
      ]),
  );
  const valid = !!prepared && prepared.source === sourceSignature && !editing;
  const enabled = [
    "bess_system_dispatch.v1",
    "bess_system_dispatch.v2",
  ].includes(context.model_contract ?? "");

  function change<K extends keyof Preparation>(key: K, value: Preparation[K]) {
    const next = { ...form, [key]: value };
    setForm(next);
    if (["range_start", "range_end", "timezone"].includes(key)) {
      const range = executionChartRange(next);
      if (range) onRangeChange(range);
    }
    setPrepared(null);
    setError("");
  }

  async function validate() {
    if (busyRef.current) return;
    busyRef.current = true;
    setPending(true);
    setError("");
    setPrepared(null);
    try {
      const preview = await post<Preview>(path + "/preview", form);
      setPrepared({
        preview,
        source: sourceSignature,
        request: {
          ...form,
          expected_preparation_hash: preview.preparation_hash,
          idempotency_key: crypto.randomUUID(),
        },
      });
    } catch (failure) {
      setError((failure as Error).message);
    } finally {
      busyRef.current = false;
      setPending(false);
    }
  }

  async function execute() {
    if (busyRef.current || !valid || !prepared) return;
    busyRef.current = true;
    setPending(true);
    setError("");
    try {
      const accepted = await post<ScenarioRun>(
        path + "/runs",
        prepared.request,
      );
      queryClient.setQueryData(queryKey, { run: accepted });
      setPrepared(null);
      void state.refetch();
    } catch (failure) {
      setError((failure as Error).message);
      if (failure instanceof ApiError && failure.status === 409)
        setPrepared(null);
      void state.refetch();
    } finally {
      busyRef.current = false;
      setPending(false);
    }
  }

  return (
    <section className="mesa-execution" aria-label="Ejecución del caso">
      <div className="mesa-execution-summary">
        <details className="mesa-execution-form">
          <summary>Preparar ejecución eléctrica</summary>
          {enabled ? (
            <form
              onSubmit={(event) => {
                event.preventDefault();
                void validate();
              }}
            >
              <fieldset disabled={pending || editing || active}>
                <label>
                  Inicio de ejecución
                  <input
                    type="datetime-local"
                    required
                    value={form.range_start}
                    onChange={(e) => change("range_start", e.target.value)}
                  />
                </label>
                <label>
                  Fin de ejecución (exclusivo)
                  <input
                    type="datetime-local"
                    required
                    value={form.range_end}
                    onChange={(e) => change("range_end", e.target.value)}
                  />
                </label>
                <label>
                  Zona horaria de ejecución
                  <input
                    required
                    value={form.timezone}
                    onChange={(e) => change("timezone", e.target.value)}
                  />
                </label>
                <label>
                  Resolución de ejecución (horas)
                  <input
                    type="number"
                    min="0.000001"
                    step="any"
                    required
                    value={form.resolution_hours}
                    onChange={(e) =>
                      change("resolution_hours", Number(e.target.value))
                    }
                  />
                </label>
              </fieldset>
              <p>
                Intervalo [inicio, fin): el fin queda excluido. La zona y
                resolución deben coincidir con las entradas; no se remuestrea.{" "}
                Los gráficos se ajustan automáticamente al período elegido.
              </p>
              {!executionChartRange(form) && (
                <p role="status">
                  Indica fechas válidas, con inicio anterior al fin, y una zona
                  horaria válida para ajustar los gráficos.
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
                <p role="status">
                  Preparación válida · {prepared.preview.period_count}{" "}
                  intervalos · {prepared.preview.timezone}
                  <br />
                  {prepared.preview.range_start} → {prepared.preview.range_end}{" "}
                  (fin exclusivo)
                </p>
              )}
              <div className="mesa-execution-actions">
                <button type="submit" disabled={pending || editing || active}>
                  Validar preparación
                </button>
                <button
                  type="button"
                  onClick={() => void execute()}
                  disabled={!valid || pending || active || state.isPending}
                >
                  Ejecutar caso eléctrico
                </button>
                {pending && <span role="status">Validando y preparando…</span>}
              </div>
            </form>
          ) : (
            <p>
              Este modelo requiere la preparación de red hidráulica. La
              ejecución eléctrica admite v1/v2.
            </p>
          )}
        </details>
        <span aria-live="polite">
          {run ? (
            <>
              <strong>Ejecución #{run.id}</strong> ·{" "}
              {statuses[run.status] ?? run.status}
            </>
          ) : (
            "Sin ejecución desde la mesa"
          )}
        </span>
        {run?.status === "succeeded" && (
          <button type="button" onClick={() => onResults(run.id)}>
            Ver resultados en la mesa
          </button>
        )}
      </div>
      {error && (
        <p role="alert">
          {error} Puedes revisar la preparación o reintentar la misma solicitud.
        </p>
      )}
      {state.isError && (
        <p role="alert">
          No se pudo actualizar el avance. La ejecución se conserva.
          <button type="button" onClick={() => void state.refetch()}>
            Reintentar conexión
          </button>
        </p>
      )}
      {run?.status === "failed" && (
        <p role="alert">
          La ejecución falló:{" "}
          {run.error_message || "No se obtuvieron resultados."} Revisa las
          entradas y vuelve a validar. Las entradas guardadas se conservan.
        </p>
      )}
      {run && (
        <details className="mesa-execution-progress">
          <summary>Ver avance y log de ejecución</summary>
          {executed && (
            <p>
              Período del run: {executed.range_start} → {executed.range_end}{" "}
              (fin exclusivo) · {executed.timezone} ·{" "}
              {executed.resolution_hours} h
            </p>
          )}
          <RunProgressPanel run={run} updatedAt={state.dataUpdatedAt} />
        </details>
      )}
    </section>
  );
}
