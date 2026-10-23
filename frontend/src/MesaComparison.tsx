import type { components } from "./api/schema";

export type Comparison = components["schemas"]["MesaComparisonResponse"];
export type ComparisonSeries = components["schemas"]["MesaComparisonSeries"];
export type ComparisonMode = "before" | "compare" | "after";
type Series = components["schemas"]["MesaSeries"];
const instantKey = (point: { start: string; end: string }) =>
  `${Date.parse(point.start)}:${Date.parse(point.end)}`;
const displayValue = (value: number | undefined) =>
  value === undefined ? "—" : Number(value.toPrecision(10)).toString();

function Origin({
  label,
  series,
}: {
  label: string;
  series: Series | null | undefined;
}) {
  if (!series) return <span>{label} · Sin referencia previa</span>;
  return (
    <span>
      {label} · Run #{series.run_id} · Snapshot #{series.scenario_version_id}
      {series.revision_number
        ? ` · Revisión ${series.revision_number} · Fuente #${series.time_series_set_id}`
        : ""}
    </span>
  );
}

export function MesaComparisonSignal({
  comparison,
  mode,
  presentation,
}: {
  comparison: ComparisonSeries;
  mode: ComparisonMode;
  presentation: "chart" | "table";
}) {
  const { before, after, name, unit } = comparison;
  const sides = [
    ...(mode !== "after" && before?.points?.length
      ? [{ label: "Antes", series: before, color: "#526878", dash: "7 4" }]
      : []),
    ...(mode !== "before" && after.points?.length
      ? [{ label: "Después", series: after, color: "#087f80", dash: undefined }]
      : []),
  ];
  const points = sides.flatMap((side) => side.series.points ?? []);
  const pointKey = (point: { start: string; end: string }, side: string) =>
    comparison.status !== "unchanged_input" &&
    !/(Z|[+-]\d{2}:\d{2})$/.test(point.start)
      ? `${side}:${point.start}:${point.end}`
      : instantKey(point);
  const unaligned =
    sides.length > 1 &&
    comparison.status === "incompatible" &&
    points.some((point) => !/(Z|[+-]\d{2}:\d{2})$/.test(point.start));
  const rows = [
    ...new Map(
      sides.flatMap((side) =>
        (side.series.points ?? []).map((point) => {
          const intervalKey = pointKey(point, side.label);
          return [intervalKey, { ...point, intervalKey }] as const;
        }),
      ),
    ).values(),
  ].sort((a, b) => Date.parse(a.start) - Date.parse(b.start));
  const values = sides.map(
    (side) =>
      new Map(
        (side.series.points ?? []).map((p) => [
          pointKey(p, side.label),
          p.value,
        ]),
      ),
  );
  const delta = new Map(
    (comparison.delta ?? []).map((p) => [pointKey(p, "Después"), p.value]),
  );
  const first = Math.min(...points.map((p) => Date.parse(p.start)));
  const last = Math.max(...points.map((p) => Date.parse(p.end)));
  const min = Math.min(0, ...points.map((p) => p.value));
  const max = Math.max(1, ...points.map((p) => p.value));
  const x = (value: string) =>
    100 + ((Date.parse(value) - first) / (last - first)) * 620;
  const y = (value: number) => 100 - ((value - min) / (max - min)) * 75;
  return (
    <div className="mesa-signal mesa-comparison-signal">
      <div className="mesa-comparison-heading">
        <p className="mesa-series-label">
          {name} · {unit} · {comparison.role === "input" ? "Entrada" : "Salida"}{" "}
          · Solo lectura
        </p>
        <p className="mesa-comparison-message" role="status">
          {comparison.message}
        </p>
      </div>
      {mode !== "after" && !before && comparison.status !== "no_reference" && (
        <p>Sin referencia previa</p>
      )}
      {sides.map(
        (side) =>
          side.series.status !== "available" && (
            <p key={side.label}>{side.series.message}</p>
          ),
      )}
      {unaligned && (
        <p>
          Se muestran intervalos separados; falta zona horaria para superponer.
        </p>
      )}
      {!points.length ? (
        <p>Sin datos disponibles para este modo.</p>
      ) : presentation === "table" || unaligned ? (
        <div
          className="mesa-table-scroll"
          tabIndex={0}
          role="region"
          aria-label={`Intervalos comparados de ${name}`}
        >
          <table aria-label={`${name} · ${unit}`}>
            <thead>
              <tr>
                <th>Inicio</th>
                <th>Fin (exclusivo)</th>
                {mode !== "after" && (
                  <th>
                    {name} · Antes ({unit})
                  </th>
                )}
                {mode !== "before" && (
                  <th>
                    {name} · Después ({unit})
                  </th>
                )}
                {mode === "compare" && <th>Δ ({unit})</th>}
              </tr>
            </thead>
            <tbody>
              {rows.map((point) => {
                const key = point.intervalKey;
                const value = (label: string) =>
                  displayValue(
                    values[
                      sides.findIndex((side) => side.label === label)
                    ]?.get(key),
                  );
                return (
                  <tr key={key}>
                    <td>
                      <time dateTime={point.start} title={point.start}>
                        {point.start.slice(5, 16).replace("T", " ")}
                      </time>
                    </td>
                    <td>
                      <time dateTime={point.end} title={point.end}>
                        {point.end.slice(5, 16).replace("T", " ")}
                      </time>
                    </td>
                    {mode !== "after" && <td>{value("Antes")}</td>}
                    {mode !== "before" && <td>{value("Después")}</td>}
                    {mode === "compare" && (
                      <td>{displayValue(delta.get(key))}</td>
                    )}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : (
        <>
          <div className="mesa-comparison-legend">
            {sides.map((side) => (
              <span key={side.label} style={{ color: side.color }}>
                {side.label === "Antes" ? "┄" : "━"} {name} · {side.label} (
                {unit})
              </span>
            ))}
          </div>
          <svg
            className="mesa-chart"
            viewBox="0 0 760 135"
            role="img"
            aria-label={`${name} · ${unit}`}
          >
            <desc>
              {sides
                .flatMap((side) =>
                  (side.series.points ?? []).map(
                    (p) =>
                      `${p.start} → ${p.end} · ${side.label}: ${p.value} ${unit}`,
                  ),
                )
                .join("; ")}
            </desc>
            {[0, 0.5, 1].map((fraction) => (
              <g key={fraction}>
                <line
                  x1="100"
                  x2="720"
                  y1={y(min + (max - min) * fraction)}
                  y2={y(min + (max - min) * fraction)}
                  stroke="#dce6eb"
                />
                <text
                  x="88"
                  y={y(min + (max - min) * fraction) + 4}
                  textAnchor="end"
                >
                  {(min + (max - min) * fraction).toFixed(1)}
                </text>
              </g>
            ))}
            {sides.map((side) => (
              <g key={side.label}>
                <polyline
                  points={(side.series.points ?? [])
                    .map((p) => `${x(p.start)},${y(p.value)}`)
                    .join(" ")}
                  fill="none"
                  stroke={side.color}
                  strokeWidth="3"
                  strokeDasharray={side.dash}
                />
                {side.series.points?.map((p) => (
                  <circle
                    key={p.start}
                    cx={x(p.start)}
                    cy={y(p.value)}
                    r="4"
                    fill={side.color}
                  >
                    <title>
                      {side.label}: {p.value} {unit} · {p.start} → {p.end}
                    </title>
                  </circle>
                ))}
              </g>
            ))}
            <text x="100" y="125">
              {rows[0].start.slice(0, 16).replace("T", " ")}
            </text>
            <text x="720" y="125" textAnchor="end">
              {rows.at(-1)!.end.slice(0, 16).replace("T", " ")}
            </text>
          </svg>
        </>
      )}
      <footer className="mesa-panel-footer mesa-comparison-origins">
        {mode !== "after" && <Origin label="Antes" series={before} />}
        {mode !== "before" && <Origin label="Después" series={after} />}
        <span>
          Zona: {after.timezone ?? "no registrada; horas del snapshot"}
        </span>
      </footer>
    </div>
  );
}
