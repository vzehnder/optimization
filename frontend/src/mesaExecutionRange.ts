import type { components } from "./api/schema";
import type { ChartRange } from "./mesaChartAggregation";

export type ExecutionWindow = {
  range_start: string;
  range_end: string;
  timezone: string;
};

export function initialExecutionWindow(
  data: components["schemas"]["MesaResponse"],
) {
  const source = data.components
    .flatMap((c) => [c.series, ...(c.additional_series ?? [])])
    .find((s) => s.role === "input" && s.points?.length);
  let timezone = source?.timezone ?? "UTC";
  try {
    new Intl.DateTimeFormat("en", { timeZone: timezone }).format(0);
  } catch {
    timezone = "UTC";
  }
  const inputDate = (value: string | undefined) => {
    if (!value) return "";
    if (!/(Z|[+-]\d{2}:\d{2})$/.test(value)) return value.slice(0, 16);
    const parts = Object.fromEntries(
      new Intl.DateTimeFormat("en-CA", {
        timeZone: timezone,
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        hourCycle: "h23",
      })
        .formatToParts(new Date(value))
        .map((p) => [p.type, p.value]),
    );
    return `${parts.year}-${parts.month}-${parts.day}T${parts.hour}:${parts.minute}`;
  };
  return {
    range_start: inputDate(source?.points?.[0]?.start),
    range_end: inputDate(source?.points?.at(-1)?.end),
    timezone,
    resolution_hours: source?.points?.[0]
      ? (Date.parse(source.points[0].end) -
          Date.parse(source.points[0].start)) /
        3600000
      : 1,
  };
}

// datetime-local is a wall clock in the execution zone, not the browser zone.
function executionInstant(value: string, zone: string): number {
  if (/(Z|[+-]\d{2}:\d{2})$/.test(value)) return Date.parse(value);
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?$/.test(value)) return NaN;
  const target = Date.parse(`${value}Z`);
  if (!Number.isFinite(target)) return NaN;
  const formatter = new Intl.DateTimeFormat("en-CA", {
    timeZone: zone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hourCycle: "h23",
  });
  const wallTime = (instant: number) => {
    const parts = Object.fromEntries(
      formatter.formatToParts(instant).map((p) => [p.type, p.value]),
    );
    return Date.parse(
      `${parts.year}-${parts.month}-${parts.day}T${parts.hour}:${parts.minute}:${parts.second}Z`,
    );
  };
  // Try both offsets around DST. Reject missing hours; for repeated hours use
  // the earlier instant, matching the backend's default ZoneInfo fold.
  const candidates = [-86400000, 0, 86400000]
    .map((delta) => target - (wallTime(target + delta) - target - delta))
    .filter((instant) => wallTime(instant) === target);
  return candidates.length ? Math.min(...candidates) : NaN;
}

export function executionChartRange(
  window: ExecutionWindow,
): ChartRange | null {
  try {
    const start = executionInstant(window.range_start, window.timezone);
    const end = executionInstant(window.range_end, window.timezone);
    return Number.isFinite(start) && Number.isFinite(end) && start < end
      ? { start, end }
      : null;
  } catch {
    return null;
  }
}
