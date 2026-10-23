import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { requestJson } from "./api/client";
import type { components } from "./api/schema";

type Context = components["schemas"]["MesaContext"];
type History = components["schemas"]["MesaHistoryResponse"];
const statuses: Record<string, string> = {
  queued: "En cola",
  running: "En ejecución",
  succeeded: "Completada",
  failed: "Fallida",
};

export function MesaHistory({
  context,
  editing,
}: {
  context: Context;
  editing: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useSearchParams();
  const history = useQuery({
    queryKey: [
      "mesa-history",
      context.scenario_id,
      context.case_id,
      context.variant_id,
    ],
    queryFn: ({ signal }) =>
      requestJson<History>(
        `/api/scenarios/${context.scenario_id}/mesa/history?case_id=${context.case_id}&variant_id=${context.variant_id}`,
        { signal },
      ),
    enabled: open,
    refetchInterval: open ? 5000 : false,
    retry: false,
  });
  return (
    <details
      className="mesa-history"
      onToggle={(event) => setOpen(event.currentTarget.open)}
    >
      <summary>Historial de ejecuciones</summary>
      {open && (
        <section role="region" aria-label="Historial de ejecuciones">
          <p>
            Consulta histórica de solo lectura. La preparación actual se
            conserva.
          </p>
          {history.isPending && <p role="status">Cargando historial…</p>}
          {history.isError ? (
            <p role="alert">
              No se pudo leer el historial. {history.error.message}{" "}
              <button type="button" onClick={() => void history.refetch()}>
                Reintentar historial
              </button>
            </p>
          ) : (
            history.data &&
            (!history.data.runs.length ? (
              <p role="status">Sin ejecuciones en este contexto.</p>
            ) : (
              <div
                className="mesa-history-scroll"
                tabIndex={0}
                role="region"
                aria-label="Ejecuciones del contexto"
              >
                <table>
                  <thead>
                    <tr>
                      <th>Ejecución y estado</th>
                      <th>Período [inicio, fin)</th>
                      <th>Procedencia</th>
                      <th>Acción</th>
                    </tr>
                  </thead>
                  <tbody>
                    {history.data.runs.map((run) => (
                      <tr key={run.id}>
                        <td>
                          Run #{run.id} · {statuses[run.status] ?? run.status}
                          <br />
                          Creada: {run.created_at}
                        </td>
                        <td>
                          {run.range_start ?? "Sin rango registrado"}
                          <br />
                          {run.range_end}
                          <br />
                          Zona:{" "}
                          {run.timezone ??
                            "Offset del snapshot; si no existe, zona no registrada"}
                        </td>
                        <td>
                          Snapshot #{run.scenario_version_id}
                          <br />
                          {run.model_contract}
                          <br />
                          {run.source_scenario_version_id
                            ? `Versión fuente #${run.source_scenario_version_id}`
                            : `Variante #${run.variant_id}`}
                        </td>
                        <td>
                          {run.status === "succeeded" ? (
                            <button
                              type="button"
                              disabled={editing}
                              onClick={() => {
                                const next = new URLSearchParams(search);
                                next.set("run", String(run.id));
                                next.set("comparison", "compare");
                                next.delete("reference");
                                setSearch(next);
                              }}
                            >
                              Consultar
                            </button>
                          ) : (
                            "Sin resultados disponibles"
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ))
          )}
        </section>
      )}
    </details>
  );
}
