import { useState } from "react";

export interface HourlyBound {
  period: number;
  minimum: number;
  maximum: number;
  unit: string;
}
export interface NumericOutput {
  name: string;
  period: number;
  value: number;
  unit: string;
}
interface Curve {
  name: string;
  unit: string;
  values: Map<number, number>;
}
const COLORS = [
  "#146c43",
  "#185fa5",
  "#a34b15",
  "#7348a4",
  "#9d2852",
  "#426b73",
];
const unitLabel = (unit: string) =>
  unit === "m3_per_s"
    ? "m³/s"
    : unit === "dimensionless"
      ? "adimensional"
      : unit;

export function RuleHourlyPreview({
  bounds,
  outputs,
  grid,
}: {
  bounds: HourlyBound[];
  outputs: NumericOutput[];
  grid?: { timestamp: string }[];
}) {
  const [page, setPage] = useState(0);
  const periods = [
    ...new Set([
      ...bounds.map((r) => r.period),
      ...outputs.map((r) => r.period),
    ]),
  ].sort((a, b) => a - b);
  const visible = periods.slice(page * 20, (page + 1) * 20);
  const curves: Curve[] = bounds.length
    ? [
        {
          name: "Mínimo efectivo",
          unit: "m3_per_s",
          values: new Map(bounds.map((r) => [r.period, r.minimum])),
        },
        {
          name: "Máximo efectivo",
          unit: "m3_per_s",
          values: new Map(bounds.map((r) => [r.period, r.maximum])),
        },
      ]
    : [];
  const calculated = new Map<string, Curve>();
  for (const output of outputs) {
    if (!calculated.has(output.name))
      calculated.set(output.name, {
        name: output.name,
        unit: output.unit,
        values: new Map(),
      });
    calculated.get(output.name)!.values.set(output.period, output.value);
  }
  curves.push(...calculated.values());
  if (!periods.length) return null;
  return (
    <section aria-label="Preview horaria" className="rule-hourly-preview">
      <h3>Límites y salidas horarias</h3>
      <p>
        Horizonte completo validado: {periods.length} períodos. Tabla y gráficos
        muestran los períodos {visible[0] + 1}–{visible.at(-1)! + 1}. Los
        límites efectivos incluyen la capacidad física.
      </p>
      {[...new Set(curves.map((c) => c.unit))].map((unit) => {
        const series = curves.filter((c) => c.unit === unit);
        const values = series.flatMap((s) =>
          visible.flatMap((p) => (s.values.has(p) ? [s.values.get(p)!] : [])),
        );
        const low = Math.min(0, ...values),
          high = Math.max(1, ...values);
        const x = (i: number) =>
          60 + (i * 540) / Math.max(1, visible.length - 1);
        const y = (v: number) => 175 - ((v - low) * 145) / (high - low);
        return (
          <figure key={unit}>
            <svg
              viewBox="0 0 640 210"
              role="img"
              aria-label={`Curvas horarias (${unitLabel(unit)})`}
            >
              <title>Curvas horarias ({unitLabel(unit)})</title>
              <path d="M60 25 V175 H605" fill="none" stroke="#80928c" />
              <text x="5" y="35">
                {high}
              </text>
              <text x="5" y="175">
                {low}
              </text>
              <text x="60" y="200">
                Período {visible[0] + 1}
              </text>
              <text x="515" y="200">
                {visible.at(-1)! + 1}
              </text>
              {series.map((s, index) => {
                let connected = false;
                const d = visible
                  .map((p, i) => {
                    const value = s.values.get(p);
                    if (value === undefined) {
                      connected = false;
                      return "";
                    }
                    const segment = `${connected ? "L" : "M"}${x(i)},${y(value)}`;
                    connected = true;
                    return segment;
                  })
                  .join(" ");
                return (
                  <g key={s.name}>
                    <path
                      d={d}
                      fill="none"
                      stroke={COLORS[index % COLORS.length]}
                      strokeWidth="2"
                    />
                    {visible.map(
                      (p, i) =>
                        s.values.has(p) && (
                          <circle
                            key={p}
                            cx={x(i)}
                            cy={y(s.values.get(p)!)}
                            r="3"
                            fill={COLORS[index % COLORS.length]}
                          >
                            <title>
                              {s.name}, período {p + 1}: {s.values.get(p)}{" "}
                              {unitLabel(unit)}
                            </title>
                          </circle>
                        ),
                    )}
                  </g>
                );
              })}
            </svg>
            <figcaption>
              {series.map((s, index) => (
                <span
                  key={s.name}
                  style={{ color: COLORS[index % COLORS.length] }}
                >
                  {s.name} ({unitLabel(unit)}){" "}
                </span>
              ))}
            </figcaption>
          </figure>
        );
      })}
      <div className="table-scroll">
        <table aria-label="Límites y salidas horarias">
          <thead>
            <tr>
              <th>Período</th>
              {grid && <th>Inicio UTC</th>}
              {curves.map((s) => (
                <th key={s.name}>
                  {s.name} ({unitLabel(s.unit)})
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {visible.map((period) => (
              <tr key={period}>
                <td>{period + 1}</td>
                {grid && <td>{grid[period]?.timestamp}</td>}
                {curves.map((s) => (
                  <td key={s.name}>{s.values.get(period) ?? "—"}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {periods.length > 20 && (
        <nav aria-label="Páginas de límites horarios">
          <button
            type="button"
            disabled={!page}
            onClick={() => setPage(page - 1)}
          >
            Períodos anteriores
          </button>
          <span>Página {page + 1}</span>
          <button
            type="button"
            disabled={(page + 1) * 20 >= periods.length}
            onClick={() => setPage(page + 1)}
          >
            Siguientes períodos
          </button>
        </nav>
      )}
    </section>
  );
}
