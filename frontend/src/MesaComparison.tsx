import { comparisonSides, comparisonUnaligned } from "./mesaChartData";
import type { components } from "./api/schema";
import { MesaChart } from "./MesaChart";

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
  detailsOnly = false,
}: {
  comparison: ComparisonSeries;
  mode: ComparisonMode;
  presentation: "chart" | "table";
  detailsOnly?: boolean;
}) {
  const { before, after, name, unit } = comparison;
  const sides = comparisonSides(comparison, mode);
  const points = sides.flatMap((side) => side.series.points ?? []);
  const pointKey = (point: { start: string; end: string }, side: string) =>
    comparison.status !== "unchanged_input" &&
    !/(Z|[+-]\d{2}:\d{2})$/.test(point.start)
      ? `${side}:${point.start}:${point.end}`
      : instantKey(point);
  const unaligned = comparisonUnaligned(comparison, mode);
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
      ) : detailsOnly ? null : (
        <MesaChart
          entries={sides.map(({ label, series }) => ({
            id: label,
            signalKey: comparison.signal_key,
            side: label,
            series,
          }))}
        />
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
