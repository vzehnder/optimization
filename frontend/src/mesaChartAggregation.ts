import type { components } from "./api/schema";

type Series = components["schemas"]["MesaSeries"];
export type ChartRange = { start: number; end: number };
export type ChartPoint = ChartRange & {
  value: number;
  count: number;
  segment: number;
};
export type ChartAggregation = "mean" | "sum";

export function chartAggregation(
  unit: string,
  signalKey: string,
): ChartAggregation {
  // Stored energy/volume are states, even though their units can also describe totals.
  if (
    signalKey === "battery_energy_mwh" ||
    /(?:^|_)(storage|stored|soc)(?:_|$)/i.test(signalKey)
  )
    return "mean";
  const normalized = unit.normalize("NFKC").replace(/[\s^]/g, "").toLowerCase();
  return /^(?:[kmgt]?wh|[kmgt]?j|[cdhk]?m3|ml|l|kg|t|usd|clp|eur)$/.test(
    normalized,
  )
    ? "sum"
    : "mean";
}

export function chartPoints(
  series: Pick<Series, "points" | "status">,
): ChartPoint[] {
  if (series.status !== "available") return [];
  let segment = 0;
  let previousEnd = -Infinity;
  return (series.points ?? [])
    .map((point) => ({
      start: Date.parse(point.start),
      end: Date.parse(point.end),
      value: point.value,
    }))
    .filter(
      (p) =>
        Number.isFinite(p.start) &&
        Number.isFinite(p.end) &&
        Number.isFinite(p.value) &&
        p.end > p.start,
    )
    .sort((a, b) => a.start - b.start)
    .map((p) => {
      if (p.start > previousEnd) segment++;
      previousEnd = Math.max(previousEnd, p.end);
      return { ...p, count: 1, segment };
    });
}

// About eight CSS pixels per value keeps narrow panels readable. Use familiar
// durations and one origin for all series, including before/after comparisons.
export function chartBucketSize(range: ChartRange, plotWidth: number): number {
  const target =
    (range.end - range.start) / Math.max(2, Math.floor(plotWidth / 8));
  const seconds = [
    1, 2, 5, 10, 15, 30, 60, 120, 300, 600, 900, 1800, 3600, 7200, 10800, 21600,
    43200, 86400, 172800, 604800, 1209600, 2592000, 7776000, 15552000, 31536000,
  ];
  return (
    seconds.map((s) => s * 1000).find((step) => step >= target) ??
    Math.ceil(target / 31536000000) * 31536000000
  );
}

export function aggregateChartPoints(
  source: ChartPoint[],
  range: ChartRange,
  plotWidth: number,
  aggregation: ChartAggregation,
  origin: number,
): { points: ChartPoint[]; bucketSize: number | null; sourceCount: number } {
  const selected = source.filter(
    (p) => p.start < range.end && p.end > range.start,
  );
  const budget = Math.max(2, Math.floor(plotWidth / 8));
  const bucketSize =
    selected.length > budget ? chartBucketSize(range, plotWidth) : null;
  if (!bucketSize) {
    return {
      points: selected.map((p) => {
        const start = Math.max(p.start, range.start);
        const end = Math.min(p.end, range.end);
        return {
          ...p,
          start,
          end,
          value:
            aggregation === "sum"
              ? (p.value * (end - start)) / (p.end - p.start)
              : p.value,
        };
      }),
      bucketSize,
      sourceCount: selected.length,
    };
  }
  const buckets = new Map<string, ChartPoint & { weight: number }>();
  for (const point of selected) {
    const start = Math.max(point.start, range.start);
    const end = Math.min(point.end, range.end);
    let index = Math.floor((start - origin) / bucketSize);
    while (origin + index * bucketSize < end) {
      const partStart = Math.max(start, origin + index * bucketSize);
      const partEnd = Math.min(end, origin + (index + 1) * bucketSize);
      const duration = partEnd - partStart;
      const key = `${point.segment}:${index}`;
      const bucket = buckets.get(key) ?? {
        start: partStart,
        end: partEnd,
        value: 0,
        count: 0,
        segment: point.segment,
        weight: 0,
      };
      bucket.end = Math.max(bucket.end, partEnd);
      bucket.value +=
        point.value *
        (aggregation === "mean"
          ? duration
          : duration / (point.end - point.start));
      bucket.weight += duration;
      bucket.count++;
      buckets.set(key, bucket);
      index++;
    }
  }
  return {
    points: [...buckets.values()].map(({ weight, ...p }) => ({
      ...p,
      value: aggregation === "mean" ? p.value / weight : p.value,
    })),
    bucketSize,
    sourceCount: selected.length,
  };
}

export function chartSegments(points: ChartPoint[]): ChartPoint[][] {
  const segments: ChartPoint[][] = [];
  for (const point of points) {
    const last = segments[segments.length - 1];
    if (last?.[0].segment === point.segment) last.push(point);
    else segments.push([point]);
  }
  return segments;
}

export function chartPointAt(
  points: ChartPoint[],
  instant: number,
): ChartPoint | undefined {
  // Intervals are half-open: gaps must never display a neighbouring value.
  let lo = 0;
  let hi = points.length;
  while (lo < hi) {
    const mid = Math.floor((lo + hi) / 2);
    if (points[mid].start <= instant) lo = mid + 1;
    else hi = mid;
  }
  const point = points[lo - 1];
  return point && instant < point.end ? point : undefined;
}
