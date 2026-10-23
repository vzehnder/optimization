import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import type { Comparison } from "./MesaComparison";

function utcInput(value: string | undefined | null) {
  if (
    !value ||
    !/(Z|[+-]\d{2}:\d{2})$/.test(value) ||
    !Number.isFinite(Date.parse(value))
  )
    return "";
  return new Date(value).toISOString().slice(0, 19);
}

export function MesaComparisonRange({
  comparison,
  disabled,
}: {
  comparison: Comparison;
  disabled: boolean;
}) {
  const [search, setSearch] = useSearchParams();
  const points = comparison.series.flatMap(
    (series) => series.after.points ?? [],
  );
  const starts = points
    .map((point) => utcInput(point.start))
    .filter(Boolean)
    .sort();
  const ends = points
    .map((point) => utcInput(point.end))
    .filter(Boolean)
    .sort();
  const [start, setStart] = useState(
    utcInput(search.get("range_start")) || starts[0] || "",
  );
  const [end, setEnd] = useState(
    utcInput(search.get("range_end")) || ends.at(-1) || "",
  );
  const [error, setError] = useState("");
  return (
    <details className="mesa-query-range">
      <summary>Período de consulta</summary>
      <div>
        <p>
          Zona UTC · [inicio, fin). Solo filtra la comparación y el CSV; la
          preparación se conserva.
        </p>
        <label>
          Inicio de consulta (UTC)
          <input
            type="datetime-local"
            step="1"
            value={start}
            onChange={(e) => setStart(e.target.value)}
          />
        </label>
        <label>
          Fin exclusivo de consulta (UTC)
          <input
            type="datetime-local"
            step="1"
            value={end}
            onChange={(e) => setEnd(e.target.value)}
          />
        </label>
        <button
          type="button"
          disabled={disabled || !start || !end}
          onClick={() => {
            if (start >= end) {
              setError("El inicio debe ser anterior al fin.");
              return;
            }
            const next = new URLSearchParams(search);
            next.set("range_start", new Date(`${start}Z`).toISOString());
            next.set("range_end", new Date(`${end}Z`).toISOString());
            setSearch(next);
          }}
        >
          Aplicar período
        </button>
        <button
          type="button"
          disabled={disabled}
          onClick={() => {
            const next = new URLSearchParams(search);
            next.delete("range_start");
            next.delete("range_end");
            setSearch(next);
          }}
        >
          Todo el run
        </button>
        {error && <p role="alert">{error}</p>}
      </div>
    </details>
  );
}
