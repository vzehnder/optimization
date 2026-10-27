import {
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
  type PointerEvent,
} from "react";
import type { components } from "./api/schema";
import { seriesAxis, type MesaAxis } from "./mesaChartData";
import {
  aggregateChartPoints,
  chartAggregation,
  chartPointAt,
  chartPoints,
  chartSegments,
  type ChartRange,
} from "./mesaChartAggregation";

type Series = components["schemas"]["MesaSeries"];
export type MesaChartSeries = {
  id: string;
  signalKey: string;
  series: Series;
  side?: string;
};
type Props = {
  entries: MesaChartSeries[];
  axes?: Record<string, MesaAxis>;
  range?: ChartRange | null;
};
const colors = [
  "#087f80",
  "#a84416",
  "#6654a2",
  "#2168a6",
  "#a12e72",
  "#557523",
];
const axisName = (axis: MesaAxis) =>
  axis === "primary" ? "Eje Y primario" : "Eje Y secundario";
const numberLabel = (value: number) =>
  new Intl.NumberFormat("es-CL", { maximumSignificantDigits: 4 }).format(value);
const valueLabel = (value: number) =>
  new Intl.NumberFormat("es-CL", { maximumSignificantDigits: 8 }).format(value);
const aggregationLabel = (method: "mean" | "sum") =>
  method === "sum" ? "Suma" : "Promedio";
const durationLabel = (ms: number) => {
  if (ms >= 86400000) return `${numberLabel(ms / 86400000)} d`;
  if (ms >= 3600000) return `${numberLabel(ms / 3600000)} h`;
  if (ms >= 60000) return `${numberLabel(ms / 60000)} min`;
  return `${numberLabel(ms / 1000)} s`;
};

export function MesaChart(props: Props) {
  // Reset exploration when switching runs, signals or source revisions.
  const context = props.entries
    .map(({ id, series: s }) =>
      [
        id,
        s.signal_id,
        s.run_id,
        s.revision_id,
        s.content_hash,
        s.status,
        s.points?.length,
        s.points?.[0]?.start,
        s.points?.at(-1)?.end,
      ].join(":"),
    )
    .join("|");
  return (
    <InteractiveMesaChart
      key={`${context}:${props.range?.start}:${props.range?.end}`}
      {...props}
    />
  );
}

function InteractiveMesaChart({ entries, axes, range: requestedRange }: Props) {
  const plot = useRef<HTMLDivElement>(null);
  const helpId = useId();
  const tooltipId = useId();
  const [size, setSize] = useState({ width: 600, height: 150 });
  const [zoom, setZoom] = useState<ChartRange | null>(null);
  const [hover, setHover] = useState<number | null>(null);
  const [tooltipPosition, setTooltipPosition] = useState({ x: 0, y: 0 });
  const [selection, setSelection] = useState<ChartRange | null>(null);
  useEffect(() => {
    const element = plot.current;
    if (!element) return;
    const observer = new ResizeObserver(([entry]) => {
      setSize({
        width: Math.max(200, entry.contentRect.width),
        height: Math.max(40, entry.contentRect.height),
      });
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  const source = useMemo(() => {
    const signals = [...new Set(entries.map((entry) => entry.signalKey))];
    return entries.map((entry) => ({
      ...entry,
      axis: seriesAxis(entry.signalKey, axes),
      color: colors[signals.indexOf(entry.signalKey) % colors.length],
      aggregation: chartAggregation(entry.series.unit, entry.signalKey),
      points: chartPoints(entry.series),
    }));
  }, [entries, axes]);
  const domain = useMemo(
    () =>
      requestedRange ??
      source.reduce(
        (range, entry) =>
          entry.points.reduce(
            (r, p) => ({
              start: Math.min(r.start, p.start),
              end: Math.max(r.end, p.end),
            }),
            range,
          ),
        { start: Infinity, end: -Infinity },
      ),
    [source, requestedRange],
  );
  const range = zoom ?? domain;
  const { start, end } = range;
  const left = source.some((e) => e.axis === "primary") ? 62 : 12;
  const right =
    size.width - (source.some((e) => e.axis === "secondary") ? 62 : 12);
  const width = right - left;
  const top = Math.min(12, size.height * 0.15);
  const bottom = size.height - Math.min(28, size.height * 0.3);
  const visible = useMemo(
    () =>
      source.map((entry) => ({
        ...entry,
        ...aggregateChartPoints(
          entry.points,
          { start, end },
          width,
          entry.aggregation,
          domain.start,
        ),
      })),
    [source, start, end, width, domain.start],
  );
  const hasData = visible.some((entry) => entry.points.length > 0);
  const scales = useMemo(
    () =>
      (["primary", "secondary"] as const).map((axis) => {
        const series = visible.filter((entry) => entry.axis === axis);
        const units = [...new Set(series.map((entry) => entry.series.unit))];
        const values = series.flatMap((entry) => entry.points);
        const min = values.reduce((value, p) => Math.min(value, p.value), 0);
        const max = values.reduce((value, p) => Math.max(value, p.value), 0);
        const padding = (max - min || 1) * 0.08;
        return {
          axis,
          units,
          min: min < 0 ? min - padding : 0,
          max: max + padding,
          active: series.length > 0,
          hasValues: values.length > 0,
        };
      }),
    [visible],
  );
  const tickCount = Math.max(2, Math.min(12, Math.floor((bottom - top) / 60)));
  const x = (instant: number) =>
    left + ((instant - start) / (end - start || 1)) * width;
  const instant = (pixel: number) =>
    start + ((pixel - left) / width) * (end - start);
  const y = (value: number, axis: MesaAxis) => {
    const scale = scales[axis === "primary" ? 0 : 1];
    return (
      bottom - ((value - scale.min) / (scale.max - scale.min)) * (bottom - top)
    );
  };
  const timeZone =
    entries.find((e) => e.series.timezone)?.series.timezone ?? undefined;
  const dateFormatter = useMemo(() => {
    const options: Intl.DateTimeFormatOptions = {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      hourCycle: "h23",
    };
    try {
      return new Intl.DateTimeFormat("es-CL", { ...options, timeZone });
    } catch {
      return new Intl.DateTimeFormat("es-CL", { ...options, timeZone: "UTC" });
    }
  }, [timeZone]);
  const dateLabel = (time: number) => dateFormatter.format(time);
  const names = [
    ...new Set(entries.map(({ series }) => `${series.name} · ${series.unit}`)),
  ];
  const emptyMessages = [
    ...new Set(
      entries.map(
        ({ series }) =>
          series.message ||
          (requestedRange && series.points?.length
            ? "Sin datos en el período de ejecución seleccionado."
            : "Sin datos disponibles."),
      ),
    ),
  ];
  const summaries = [
    ...new Set(
      visible
        .filter((e) => e.bucketSize)
        .map(
          (e) =>
            `${aggregationLabel(e.aggregation)} cada ${durationLabel(e.bucketSize!)}`,
        ),
    ),
  ];
  const hovered =
    hover === null
      ? []
      : visible.map((entry) => ({
          ...entry,
          point: chartPointAt(entry.points, hover),
        }));
  const tooltipWidth = Math.min(320, window.innerWidth - 16);
  const resetZoom = () => {
    setZoom(null);
    setSelection(null);
    setHover(null);
  };
  const applySelection = (selected: ChartRange) => {
    if (Math.abs(x(selected.end) - x(selected.start)) >= 8) {
      setZoom({
        start: Math.min(selected.start, selected.end),
        end: Math.max(selected.start, selected.end),
      });
      setHover(null);
    }
    setSelection(null);
  };
  const pointer = (event: PointerEvent<SVGSVGElement>) => {
    const rect = event.currentTarget.getBoundingClientRect();
    const px = ((event.clientX - rect.left) * size.width) / rect.width;
    const py = ((event.clientY - rect.top) * size.height) / rect.height;
    return {
      time: Math.min(end - 1, instant(Math.max(left, Math.min(right, px)))),
      inside: px >= left && px <= right && py >= top && py <= bottom,
    };
  };
  return (
    <div className="mesa-combined-chart">
      <div className="mesa-axis-labels">
        {scales.map(({ axis, active, units }) => (
          <span key={axis} data-axis={axis}>
            {active && (
              <>
                {axisName(axis)} ·{" "}
                {units.length > 1
                  ? `Múltiples unidades: ${units.join(" / ")}`
                  : units[0]}
              </>
            )}
          </span>
        ))}
      </div>
      {hasData && (summaries.length > 0 || zoom) && (
        <div className="mesa-chart-toolbar">
          <span>
            {summaries.length ? summaries.join(" · ") : "Resolución original"}
          </span>
          <span title="Con teclado: flechas para consultar; Mayús + flechas y Enter para ampliar; Escape para restablecer.">
            Arrastra para ampliar
          </span>
          {zoom && (
            <button type="button" onClick={resetZoom}>
              Restablecer zoom
            </button>
          )}
        </div>
      )}
      <div
        className="mesa-chart-plot"
        ref={plot}
        onPointerLeave={() => {
          if (!selection) setHover(null);
        }}
      >
        <svg
          className="mesa-chart"
          viewBox={`0 0 ${size.width} ${size.height}`}
          role="img"
          aria-label={names.join("; ")}
          tabIndex={hasData ? 0 : undefined}
          aria-describedby={
            hasData
              ? `${helpId}${hover !== null ? ` ${tooltipId}` : ""}`
              : undefined
          }
          data-range-start={hasData ? start : undefined}
          data-range-end={hasData ? end : undefined}
          onPointerDown={(event) => {
            if (!hasData || event.button !== 0) return;
            const position = pointer(event);
            if (!position.inside) return;
            event.preventDefault();
            event.currentTarget.focus();
            event.currentTarget.setPointerCapture(event.pointerId);
            setSelection({ start: position.time, end: position.time });
            setHover(null);
          }}
          onPointerMove={(event) => {
            if (!hasData) return;
            const position = pointer(event);
            setTooltipPosition({ x: event.clientX, y: event.clientY });
            if (selection) setSelection({ ...selection, end: position.time });
            else setHover(position.inside ? position.time : null);
          }}
          onPointerUp={(event) => {
            if (!selection) return;
            applySelection({ ...selection, end: pointer(event).time });
            if (event.currentTarget.hasPointerCapture(event.pointerId))
              event.currentTarget.releasePointerCapture(event.pointerId);
          }}
          onPointerCancel={() => {
            setSelection(null);
            setHover(null);
          }}
          onLostPointerCapture={() => setSelection(null)}
          onBlur={() => {
            setHover(null);
            setSelection(null);
          }}
          onKeyDown={(event) => {
            if (!hasData) return;
            if (event.key === "Escape") {
              event.preventDefault();
              resetZoom();
              return;
            }
            if (event.key === "Enter" && selection) {
              event.preventDefault();
              applySelection(selection);
              return;
            }
            if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key))
              return;
            event.preventDefault();
            const positions = [
              ...new Set(visible.flatMap((e) => e.points.map((p) => p.start))),
            ].sort((a, b) => a - b);
            const current = hover ?? positions[0] ?? start;
            const next =
              event.key === "Home"
                ? start
                : event.key === "End"
                  ? end - 1
                  : event.key === "ArrowRight"
                    ? (positions.find((t) => t > current) ?? end - 1)
                    : (positions.filter((t) => t < current).at(-1) ?? start);
            if (event.shiftKey)
              setSelection({ start: selection?.start ?? current, end: next });
            else setSelection(null);
            const rect = event.currentTarget.getBoundingClientRect();
            setTooltipPosition({
              x: rect.left + (x(next) * rect.width) / size.width,
              y: rect.top + top,
            });
            setHover(next);
          }}
        >
          <desc id={helpId}>
            Arrastra para ampliar. Con teclado: flechas para consultar; Mayús y
            flechas para seleccionar, Enter para ampliar y Escape para
            restablecer.
            {visible
              .flatMap(({ series, side, points }) =>
                points.map(
                  (p) =>
                    `${series.name} · ${dateLabel(p.start)} → ${dateLabel(p.end)}${side ? ` · ${side}` : ""}: ${p.value} ${series.unit}`,
                ),
              )
              .join("; ")}
          </desc>
          {Array.from(
            { length: tickCount + 1 },
            (_, index) => index / tickCount,
          ).map((fraction) => (
            <g key={fraction}>
              <line
                x1={left}
                x2={right}
                y1={bottom - fraction * (bottom - top)}
                y2={bottom - fraction * (bottom - top)}
                stroke="#dce6eb"
              />
              {scales
                .filter((scale) => scale.hasValues)
                .map((scale) => (
                  <text
                    key={scale.axis}
                    x={scale.axis === "primary" ? left - 7 : right + 7}
                    y={bottom - fraction * (bottom - top) + 4}
                    textAnchor={scale.axis === "primary" ? "end" : "start"}
                  >
                    {numberLabel(
                      scale.min + (scale.max - scale.min) * fraction,
                    )}
                  </text>
                ))}
            </g>
          ))}
          {visible
            .filter((entry) => entry.points.length > 0)
            .map(
              ({ id, points, axis, color, side, bucketSize, sourceCount }) => (
                <g
                  key={id}
                  data-series={id}
                  data-axis={axis}
                  data-source-count={sourceCount}
                  data-point-count={points.length}
                  data-bucket-size={bucketSize ?? 0}
                >
                  {chartSegments(points).map((segment) => (
                    <polyline
                      key={segment[0].segment}
                      points={segment
                        .map((p) => `${x(p.start)},${y(p.value, axis)}`)
                        .join(" ")}
                      fill="none"
                      stroke={color}
                      strokeWidth="2"
                      strokeLinejoin="round"
                      strokeDasharray={side === "Antes" ? "7 4" : undefined}
                    />
                  ))}
                  {(points.length <= width / 16
                    ? points
                    : chartSegments(points)
                        .filter((s) => s.length === 1)
                        .flat()
                  ).map((p, index) => (
                    <circle
                      key={index}
                      cx={x(p.start)}
                      cy={y(p.value, axis)}
                      r="2.5"
                      fill={color}
                    />
                  ))}
                </g>
              ),
            )}
          {hasData && (
            <>
              <text x={left} y={size.height - 6}>
                {dateLabel(start)}
              </text>
              <text x={right} y={size.height - 6} textAnchor="end">
                {dateLabel(end)}
              </text>
              <rect
                className="mesa-chart-hit-area"
                x={left}
                y={top}
                width={width}
                height={bottom - top}
                fill="transparent"
              />
            </>
          )}
          {selection && (
            <rect
              className="mesa-chart-selection"
              x={Math.min(x(selection.start), x(selection.end))}
              y={top}
              width={Math.abs(x(selection.end) - x(selection.start))}
              height={bottom - top}
            />
          )}
          {hover !== null && !selection && (
            <g className="mesa-chart-crosshair" aria-hidden="true">
              <line
                x1={x(hover)}
                x2={x(hover)}
                y1={top}
                y2={bottom}
                stroke="#526878"
                strokeDasharray="4 3"
              />
              {hovered.map(
                ({ id, point, color, axis }) =>
                  point && (
                    <circle
                      key={id}
                      cx={x(hover)}
                      cy={y(point.value, axis)}
                      r="4"
                      fill={color}
                      stroke="white"
                      strokeWidth="1.5"
                    />
                  ),
              )}
            </g>
          )}
        </svg>
        {hover !== null && !selection && (
          <div
            role="tooltip"
            id={tooltipId}
            className="mesa-chart-tooltip"
            tabIndex={0}
            style={{
              width: tooltipWidth,
              left: Math.max(
                8,
                Math.min(
                  window.innerWidth - tooltipWidth - 8,
                  tooltipPosition.x + 12 + tooltipWidth <= window.innerWidth
                    ? tooltipPosition.x + 12
                    : tooltipPosition.x - tooltipWidth - 12,
                ),
              ),
              ...(tooltipPosition.y > window.innerHeight / 2
                ? {
                    bottom: Math.max(
                      8,
                      window.innerHeight - tooltipPosition.y + 12,
                    ),
                  }
                : { top: Math.max(8, tooltipPosition.y + 12) }),
            }}
          >
            <strong>
              {dateLabel(hover)}
              {timeZone ? ` · ${timeZone}` : ""}
            </strong>
            {hovered.map(
              ({ id, series, side, color, point, aggregation, bucketSize }) => (
                <div key={id} className="mesa-chart-tooltip-series">
                  <span>
                    <span style={{ color }} aria-hidden="true">
                      ━{" "}
                    </span>
                    {series.name}
                    {side ? ` · ${side}` : ""}
                  </span>
                  <b>
                    {point
                      ? `${valueLabel(point.value)} ${series.unit}`
                      : "Sin datos"}
                  </b>
                  {point && (
                    <small>
                      {dateLabel(point.start)} → {dateLabel(point.end)}
                      {bucketSize
                        ? ` · ${aggregationLabel(aggregation)} · ${point.count} muestras`
                        : ""}
                    </small>
                  )}
                </div>
              ),
            )}
          </div>
        )}
        {!hasData && (
          <div className="mesa-chart-empty">
            <p role="status">
              {emptyMessages.length === 1
                ? emptyMessages[0]
                : "Sin datos disponibles. Revisa el detalle de las series."}
            </p>
          </div>
        )}
      </div>
      <div
        className="mesa-chart-legend"
        tabIndex={entries.length > 1 ? 0 : undefined}
        role="group"
        aria-label="Leyenda del gráfico"
      >
        {visible.map(({ id, series, axis, color, side, points }) => (
          <span key={id}>
            <span aria-hidden="true" style={{ color }}>
              {side === "Antes" ? "┄" : "━"}
            </span>{" "}
            {series.name}
            {side ? ` · ${side}` : ""} ({series.unit}) ·{" "}
            {axis === "primary" ? "Primario" : "Secundario"}
            {!points.length && " · Sin datos"}
          </span>
        ))}
      </div>
    </div>
  );
}
