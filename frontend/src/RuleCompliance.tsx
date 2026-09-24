import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { requestJson } from "./api/client";
import type { components } from "./api/schema";
import { ruleUnit } from "./ruleUnits";

type Report = components["schemas"]["ComplianceReport"];
type Sample = components["schemas"]["ComplianceSample"];
const number = (value: number | null) =>
  value === null
    ? "No disponible"
    : value.toLocaleString("es-CL", { maximumSignificantDigits: 9 });
const states: Record<string, string> = {
  optimal: "Solución óptima",
  feasible: "Solución factible disponible",
  no_primal: "Sin solución primal disponible",
  primal_available: "Valores primales disponibles; factibilidad no certificada",
  pending: "Ejecución en curso",
};
const rowStates: Record<string, string> = {
  satisfied: "Cumple",
  violated: "Incumple",
  unavailable: "Sin evaluar",
};
const categories: Record<string, string> = {
  code_data: "Código o datos",
  capacity: "Capacidad o cuota",
  timeout: "Tiempo agotado",
  cancelled: "Cancelación o interrupción",
  solve: "Error del solver",
  infeasible: "Modelo infactible",
  bounds_conflict: "Contradicción de cotas",
  result_data: "Resultados incompletos",
};

function SampleChart({ samples, unit }: { samples: Sample[]; unit: string }) {
  const available = samples.filter((s) => (s.margin ?? s.residual) !== null);
  if (!available.length) return null;
  const min = Math.min(0, ...available.map((s) => (s.margin ?? s.residual)!));
  const max = Math.max(0, ...available.map((s) => (s.margin ?? s.residual)!));
  const extent = max - min || 1;
  const y = (v: number) => 150 - ((v - min) / extent) * 120;
  const first = available[0].row_index;
  const last = available[available.length - 1].row_index;
  return (
    <figure>
      <svg
        viewBox="0 0 640 190"
        role="img"
        aria-label={`Muestra de márgenes y residuos en ${ruleUnit(unit)}`}
        style={{ width: "100%", maxWidth: 720 }}
      >
        <line x1="55" y1={y(0)} x2="615" y2={y(0)} stroke="#64748b" />
        <text x="4" y="20" fontSize="12">
          {ruleUnit(unit)}
        </text>
        <text x="4" y="40" fontSize="11">
          {number(max)}
        </text>
        <text x="4" y="150" fontSize="11">
          {number(min)}
        </text>
        {available.map((s) => (
          <circle
            key={s.row_index}
            cx={60 + ((s.row_index - first) / (last - first || 1)) * 540}
            cy={y((s.margin ?? s.residual)!)}
            r="4"
            fill={s.status === "violated" ? "#b91c1c" : "#0369a1"}
          >
            <title>
              {s.name} · fila {s.row_index + 1} · período {s.period + 1}:{" "}
              {number(s.margin ?? s.residual)} {ruleUnit(unit)} ·{" "}
              {rowStates[s.status]}
            </title>
          </circle>
        ))}
        <text x="60" y="180" fontSize="12">
          Fila {first + 1}
        </text>
        <text x="510" y="180" fontSize="12">
          Fila {last + 1}
        </text>
      </svg>
      <figcaption>
        Margen de desigualdades y residuo de igualdades · {ruleUnit(unit)}.
      </figcaption>
    </figure>
  );
}

export function RuleCompliance({
  runId,
  status,
}: {
  runId: number;
  status: string;
}) {
  const [ruleId, setRuleId] = useState("");
  const [period, setPeriod] = useState("");
  const [offset, setOffset] = useState(0);
  const query = useQuery({
    queryKey: ["rule-compliance", runId, status, ruleId, period, offset],
    queryFn: ({ signal }) => {
      const params = new URLSearchParams({
        offset: String(offset),
        limit: "25",
      });
      if (ruleId) params.set("rule_id", ruleId);
      if (period) params.set("period", period);
      return requestJson<Report>(
        `/api/runs/${runId}/rule-compliance?${params}`,
        { signal },
      );
    },
    enabled: ["succeeded", "failed", "cancelled"].includes(status),
    retry: false,
  });
  const data = query.isError ? undefined : query.data;
  return (
    <section
      className="workspace-section"
      aria-labelledby="rule-compliance-heading"
    >
      <h2 id="rule-compliance-heading">Cumplimiento de reglas</h2>
      {!query.isEnabled ? (
        <p>Disponible cuando termine la ejecución.</p>
      ) : query.isPending ? (
        <p role="status">Reconstruyendo cumplimiento…</p>
      ) : query.isError ? (
        <p role="alert">
          No se pudo reconstruir el cumplimiento: {query.error.message}
        </p>
      ) : null}
      {data && (
        <>
          <p>
            <strong>
              {states[data.solution_state] ?? data.solution_state}
            </strong>
            {data.termination_status && ` · ${data.termination_status}`}
          </p>
          <p>
            {data.counts.total} filas totales · {data.counts.evaluated}{" "}
            evaluadas · {data.counts.violated} incumplidas ·{" "}
            {data.counts.unavailable} sin evaluar.
          </p>
          {data.diagnostics.map((d, i) => (
            <div key={i} className="result-alert" role="status">
              <strong>
                {categories[d.category] ?? d.category}
                {d.code && ` · ${d.code}`}
              </strong>
              <p>{d.message}</p>
              <p>{d.action}</p>
              {d.rule_url && (
                <a href={d.rule_url}>
                  Volver a la regla
                  {d.period != null && ` · período ${d.period + 1}`}
                </a>
              )}
              {!!d.conflicts?.length && (
                <ul>
                  {d.conflicts.map((c, n) => (
                    <li key={n}>
                      <a href={c.rule_url}>
                        {c.name} · período {c.period + 1}
                      </a>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          ))}
          {data.solution_state === "no_primal" && (
            <nav aria-label="Reglas del modelo sin solución">
              <ul>
                {data.rules.map((r) => (
                  <li key={r.application_id}>
                    <a href={r.url}>Revisar {r.name}</a>
                  </li>
                ))}
              </ul>
            </nav>
          )}
          <p>
            Expresión congelada normalizada: izquierda = suma de términos;
            derecha = −constante. Margen ≥ 0 indica cumplimiento: derecha −
            izquierda para ≤, izquierda − derecha para ≥. Igualdades: residuo =
            izquierda − derecha.
          </p>
          <p>
            Tolerancia del informe = absoluta + relativa × máximo de los valores
            absolutos de ambos lados. No sustituye la tolerancia interna del
            solver.
          </p>
          <button
            type="button"
            disabled={query.isFetching}
            onClick={() => void query.refetch()}
          >
            Reconstruir informe
          </button>
          <label>
            Filtrar regla
            <select
              value={ruleId}
              onChange={(e) => {
                setRuleId(e.target.value);
                setOffset(0);
              }}
            >
              <option value="">Todas las reglas</option>
              {data.rules.map((r) => (
                <option key={r.application_id} value={r.rule_id}>
                  {r.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Filtrar período
            <select
              value={period}
              onChange={(e) => {
                setPeriod(e.target.value);
                setOffset(0);
              }}
            >
              <option value="">Todos los períodos</option>
              {Array.from({ length: data.period_count }, (_, i) => (
                <option key={i} value={String(i)}>
                  Período {i + 1}
                </option>
              ))}
            </select>
          </label>
          <p>
            Muestra de {data.samples.length} de {data.page.total} filas
            filtradas. La comprobación incluye todas las filas de la corrida.
          </p>
          {[...new Set(data.samples.map((s) => s.unit))].map((unit) => (
            <SampleChart
              key={unit}
              unit={unit}
              samples={data.samples.filter((s) => s.unit === unit)}
            />
          ))}
          <p>
            Filas {data.page.total ? data.page.offset + 1 : 0}–
            {Math.min(data.page.offset + data.rows.length, data.page.total)} de{" "}
            {data.page.total}.
          </p>
          <div
            className="time-series-table-scroll result-table-scroll"
            tabIndex={0}
          >
            <table aria-label="Detalle de cumplimiento">
              <thead>
                <tr>
                  <th>Regla</th>
                  <th>Fila y período</th>
                  <th>Componentes</th>
                  <th>Relación</th>
                  <th>Izquierda</th>
                  <th>Derecha</th>
                  <th>Margen / residuo</th>
                  <th>Tolerancia</th>
                  <th>Estado</th>
                </tr>
              </thead>
              <tbody>
                {data.rows.map((r) => (
                  <tr key={r.row_index}>
                    <td>
                      <a href={r.rule_url}>{r.rule_name}</a>
                      <details>
                        <summary>Revisión congelada</summary>
                        <p>
                          Definición: {r.definition_id} · Instancia: {r.rule_id}{" "}
                          · Revisión local: {r.instance_revision} · Aplicación:{" "}
                          {r.application_id} · Publicación: {r.revision_id} ·
                          Línea {r.line}
                        </p>
                        <pre>
                          {JSON.stringify(
                            { terms: r.terms, constant: r.constant },
                            null,
                            2,
                          )}
                        </pre>
                      </details>
                    </td>
                    <td>
                      {r.name}
                      <p>
                        Período {r.period + 1} · {r.timestamp}
                      </p>
                      <p>
                        Períodos afectados:{" "}
                        {r.affected_periods.map((t) => t + 1).join(", ")}
                      </p>
                      {r.window && (
                        <details>
                          <summary>Ventana congelada</summary>
                          <pre>{JSON.stringify(r.window, null, 2)}</pre>
                        </details>
                      )}
                    </td>
                    <td>
                      {r.components
                        .map((c) => String(c.display_name ?? c.id))
                        .join(", ")}
                    </td>
                    <td>
                      {r.relation} · {ruleUnit(r.unit)}
                    </td>
                    <td>{number(r.lhs)}</td>
                    <td>{number(r.rhs)}</td>
                    <td>
                      {r.relation === "==" ? "Residuo" : "Margen"}:{" "}
                      {number(r.margin ?? r.residual)}
                    </td>
                    <td>
                      {number(r.tolerance)}
                      <details>
                        <summary>Ver tolerancias</summary>Absoluta:{" "}
                        {r.absolute_tolerance} · Relativa:{" "}
                        {r.relative_tolerance}
                      </details>
                    </td>
                    <td>{rowStates[r.status] ?? r.status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <nav className="inline-actions" aria-label="Páginas de cumplimiento">
            <button
              type="button"
              disabled={!offset || query.isFetching}
              onClick={() => setOffset(Math.max(0, offset - 25))}
            >
              Página anterior
            </button>
            <button
              type="button"
              disabled={data.page.next_offset === null || query.isFetching}
              onClick={() => setOffset(data.page.next_offset ?? offset)}
            >
              Página siguiente
            </button>
          </nav>
        </>
      )}
    </section>
  );
}
