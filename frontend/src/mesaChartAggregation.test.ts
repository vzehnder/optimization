import { describe, expect, it } from "vitest";
import {
  aggregateChartPoints,
  chartAggregation,
  chartPointAt,
  chartPoints,
  chartSegments,
  type ChartPoint,
} from "./mesaChartAggregation";

const hour = 3600000;
const point = (start: number, end: number, value: number): ChartPoint => ({
  start: start * hour,
  end: end * hour,
  value,
  count: 1,
  segment: 1,
});

describe("agregación visual de la mesa", () => {
  it.each([
    ["MW", "generation", "mean"],
    ["m³/s", "inflow", "mean"],
    ["USD/MWh", "price", "mean"],
    ["m", "level", "mean"],
    ["%", "availability", "mean"],
    ["MWh", "generation_energy", "sum"],
    ["m^3", "water_total", "sum"],
    ["USD", "cost", "sum"],
    ["MWh", "battery_energy_mwh", "mean"],
    ["hm3", "hydro_storage_volume_hm3", "mean"],
    ["unknown", "manual", "mean"],
  ])("%s / %s usa %s", (unit, key, expected) => {
    expect(chartAggregation(unit, key)).toBe(expected);
  });

  it("promedia por duración y suma cantidades conservando el total", () => {
    const source = [
      point(0, 1, 10),
      point(1, 3, 40),
      point(3, 4, 20),
      point(4, 6, 50),
    ];
    const range = { start: 0, end: 6 * hour };
    const mean = aggregateChartPoints(source, range, 16, "mean", 0);
    expect(mean.bucketSize).toBe(3 * hour);
    expect(mean.points.map((p) => p.value)).toEqual([30, 40]);
    const sum = aggregateChartPoints(source, range, 16, "sum", 0);
    expect(sum.points.map((p) => p.value)).toEqual([50, 70]);
    expect(source.map((p) => p.value)).toEqual([10, 40, 20, 50]);
  });

  it("distribuye cantidades al cruzar bloques y recortar un intervalo", () => {
    const source = [point(0, 1, 10), point(1, 4, 60), point(4, 6, 40)];
    const all = aggregateChartPoints(
      source,
      { start: 0, end: 6 * hour },
      16,
      "sum",
      0,
    );
    expect(all.points.map((p) => p.value)).toEqual([50, 60]);
    const zoom = aggregateChartPoints(
      source,
      { start: 2 * hour, end: 5 * hour },
      500,
      "sum",
      0,
    );
    expect(zoom.points.map((p) => p.value)).toEqual([40, 20]);
    expect(zoom.bucketSize).toBeNull();
  });

  it("reduce 2208 horas según el ancho y recupera las muestras al ampliar", () => {
    const source = Array.from({ length: 2208 }, (_, i) =>
      point(i, i + 1, 20 + (i % 24)),
    );
    const range = { start: 0, end: 2208 * hour };
    const narrow = aggregateChartPoints(source, range, 480, "mean", 0);
    const wide = aggregateChartPoints(source, range, 1200, "mean", 0);
    expect(narrow.points.length).toBeLessThanOrEqual(60);
    expect(wide.points.length).toBeGreaterThan(narrow.points.length);
    const zoom = aggregateChartPoints(
      source,
      { start: 24 * hour, end: 48 * hour },
      480,
      "mean",
      0,
    );
    expect(zoom.bucketSize).toBeNull();
    expect(zoom.points.map((p) => p.value)).toEqual(
      source.slice(24, 48).map((p) => p.value),
    );
  });

  it("conserva huecos incluso dentro del mismo bloque y no inventa valores al consultar", () => {
    const source = [
      point(0, 1, 2),
      point(1, 2, 4),
      { ...point(2.5, 3, 8), segment: 2 },
      { ...point(3, 4, 10), segment: 2 },
    ];
    const result = aggregateChartPoints(
      source,
      { start: 0, end: 4 * hour },
      16,
      "mean",
      0,
    );
    expect(chartSegments(result.points)).toHaveLength(2);
    expect(chartPointAt(result.points, 2.25 * hour)).toBeUndefined();
    expect(chartPointAt(result.points, 2.5 * hour)?.value).toBeCloseTo(28 / 3);
    expect(chartPointAt(result.points, 4 * hour)).toBeUndefined();
    expect(chartPointAt(result.points, 0)?.value).toBe(3);
  });

  it("ordena por instante, excluye datos inválidos y detecta cortes de cobertura", () => {
    const raw = (start: string, end: string, value: number) => ({
      start,
      end,
      value,
    });
    const result = chartPoints({
      status: "available",
      points: [
        raw("2026-08-01T02:00Z", "2026-08-01T03:00Z", 4),
        raw("2026-07-31T20:00-04:00", "2026-07-31T21:00-04:00", 2),
        raw("invalid", "2026-08-01T01:00Z", 2),
        raw("2026-08-01T01:00Z", "2026-08-01T01:00Z", 2),
        raw("2026-08-01T01:00Z", "2026-08-01T02:00Z", NaN),
      ],
    });
    expect(result.map((p) => p.value)).toEqual([2, 4]);
    expect(chartSegments(result)).toHaveLength(2);
    expect(chartPoints({ status: "unavailable", points: [] })).toEqual([]);
  });
});
