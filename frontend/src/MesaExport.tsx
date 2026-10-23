import { useEffect, useRef, useState } from "react";
import { getCsrfToken } from "./api/client";
import type { components } from "./api/schema";

type Selection = components["schemas"]["MesaExportRequest"];

export function MesaExport({
  scenarioId,
  selection,
  disabled,
}: {
  scenarioId: number;
  selection: Selection;
  disabled: boolean;
}) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const controller = useRef<AbortController | null>(null);
  useEffect(() => () => controller.current?.abort(), []);
  async function download() {
    const request = new AbortController();
    controller.current = request;
    setPending(true);
    setError("");
    try {
      const response = await fetch(
        `/api/scenarios/${scenarioId}/mesa/comparison/export`,
        {
          method: "POST",
          credentials: "same-origin",
          signal: request.signal,
          headers: {
            "Content-Type": "application/json",
            "X-CSRF-Token": await getCsrfToken(),
          },
          body: JSON.stringify(selection),
        },
      );
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(
          typeof body.detail === "string"
            ? body.detail
            : `Error ${response.status}`,
        );
      }
      const blob = await response.blob();
      if (request.signal.aborted) return;
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `mesa-run-${selection.run_id}.csv`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (cause) {
      if (!request.signal.aborted)
        setError(cause instanceof Error ? cause.message : "Error de conexión");
    } finally {
      if (!request.signal.aborted) setPending(false);
    }
  }
  return (
    <>
      <button
        type="button"
        disabled={disabled || pending || !selection.panels.length}
        onClick={() => void download()}
      >
        {pending ? "Preparando CSV…" : "Exportar CSV de vistas visibles"}
      </button>
      {error && (
        <p role="alert">
          No se pudo exportar. {error} Vuelve a intentar la descarga.
        </p>
      )}
    </>
  );
}
