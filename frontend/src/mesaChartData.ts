import type { components } from "./api/schema";

export type MesaAxis = "primary" | "secondary";
export function seriesAxis(
  key: string,
  axes?: Record<string, MesaAxis>,
): MesaAxis {
  return axes?.[key] ?? "primary";
}

type ComparisonSeries = components["schemas"]["MesaComparisonSeries"];
type ComparisonMode = "before" | "compare" | "after";

export function comparisonSides(
  comparison: ComparisonSeries,
  mode: ComparisonMode,
) {
  return [
    ...(mode !== "after" && comparison.before?.points?.length
      ? [{ label: "Antes", series: comparison.before }]
      : []),
    ...(mode !== "before" && comparison.after.points?.length
      ? [{ label: "Después", series: comparison.after }]
      : []),
  ];
}

export function comparisonUnaligned(
  comparison: ComparisonSeries,
  mode: ComparisonMode,
) {
  const sides = comparisonSides(comparison, mode);
  return (
    sides.length > 1 &&
    comparison.status === "incompatible" &&
    sides.some((side) =>
      side.series.points?.some(
        (point) => !/(Z|[+-]\d{2}:\d{2})$/.test(point.start),
      ),
    )
  );
}
