import { useEffect, useRef, useState } from "react";
import type { ScenarioRun } from "./api/client";

const stageLabels: Record<string, string> = {
  queued: "Esperando turno para iniciar",
  running: "Ejecución en curso",
  validating: "Preparando y validando datos en Julia",
  starting: "Iniciando Julia",
  preparing: "Preparando datos en Julia",
  building: "Construyendo el modelo en Julia",
  optimizing: "Optimizando con HiGHS",
  processing: "Preparando resultados",
  saving: "Guardando resultados",
  succeeded: "Simulación finalizada",
  failed: "Simulación interrumpida",
};

function duration(seconds: number | null) {
  if (seconds === null || !Number.isFinite(seconds)) return "—";
  const total = Math.max(0, Math.floor(seconds));
  return [Math.floor(total / 3600), Math.floor((total % 3600) / 60), total % 60]
    .map((part) => String(part).padStart(2, "0"))
    .join(":");
}

export function RunProgressPanel({
  run,
  updatedAt,
}: {
  run: ScenarioRun;
  updatedAt: number;
}) {
  const [now, setNow] = useState(Date.now);
  const [followLog, setFollowLog] = useState(true);
  const logRef = useRef<HTMLPreElement>(null);
  const active = run.status === "running" || run.status === "queued";
  const progress = run.progress;
  useEffect(() => {
    if (!active) return;
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [active, run.id]);
  useEffect(() => {
    if (followLog && logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight;
    }
  }, [followLog, progress?.solver_log]);

  // Historical runs predate instrumentation and have no progress to display.
  if (!active && !progress?.events.length && !progress?.solver_log) return null;

  const stage = active ? (progress?.stage ?? run.status) : run.status;
  const baseElapsed = progress?.elapsed_seconds ?? run.duration_seconds ?? null;
  const elapsed =
    run.status === "queued"
      ? null
      : baseElapsed !== null
        ? baseElapsed + (active ? Math.max(0, (now - updatedAt) / 1000) : 0)
        : run.started_at
          ? Math.max(0, (now - Date.parse(run.started_at)) / 1000)
          : null;
  const hasGap =
    progress?.gap_percent !== null &&
    progress?.gap_percent !== undefined &&
    Number.isFinite(progress.gap_percent);

  return (
    <section
      className="workspace-section run-progress"
      aria-label="Avance de la simulación"
    >
      <div className="run-progress-heading">
        <h2>Avance de la simulación</h2>
        <span className="source-note">
          {active ? "Actualización automática" : "Registro de ejecución"}
        </span>
      </div>
      <p className="run-progress-stage" aria-live="polite">
        {stageLabels[stage] ?? "Ejecución en curso"}
      </p>
      <dl className="run-progress-metrics">
        <div>
          <dt>Tiempo transcurrido</dt>
          <dd>{duration(elapsed)}</dd>
        </div>
        <div>
          <dt>Gap actual</dt>
          <dd>
            {hasGap
              ? `${progress!.gap_percent!.toLocaleString("es-CL", { maximumFractionDigits: 4 })} %`
              : "Sin dato del solver"}
          </dd>
        </div>
        {progress?.solver_seconds != null ? (
          <div>
            <dt>Tiempo reportado por HiGHS</dt>
            <dd>{duration(progress.solver_seconds)}</dd>
          </div>
        ) : null}
      </dl>
      <p className="source-note">
        El tiempo incluye la preparación en Julia. El gap se actualiza cuando
        HiGHS lo reporta; puede no estar disponible en modelos continuos o antes
        de encontrar una solución.
      </p>
      {progress?.events.length ? (
        <ol
          className="run-progress-events"
          aria-label="Etapas de la simulación"
        >
          {progress.events.map((event, index) => (
            <li key={`${event.timestamp}-${index}`}>
              <time dateTime={event.timestamp}>
                {new Date(event.timestamp).toLocaleTimeString("es-CL", {
                  hour12: false,
                })}
              </time>
              <span>{event.message}</span>
            </li>
          ))}
        </ol>
      ) : (
        <p>
          {run.status === "queued"
            ? "La simulación comenzará cuando el ejecutor esté disponible."
            : "Esperando registros de progreso. Las ejecuciones iniciadas antes de activar el log pueden no emitirlos."}
        </p>
      )}
      <div className="run-progress-heading">
        <h3>Log de optimización</h3>
        <label>
          <input
            type="checkbox"
            checked={followLog}
            onChange={(event) => setFollowLog(event.target.checked)}
          />
          Seguir log
        </label>
      </div>
      <pre
        ref={logRef}
        className="json-panel run-progress-log"
        tabIndex={0}
        aria-label="Log de HiGHS"
      >
        {progress?.solver_log || "Esperando la salida de HiGHS…"}
      </pre>
      {progress?.log_truncated ? (
        <p className="source-note">Se muestran las últimas líneas del log.</p>
      ) : null}
    </section>
  );
}
