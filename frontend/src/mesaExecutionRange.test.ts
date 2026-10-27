import { describe, expect, it } from "vitest";
import {
  executionChartRange,
  initialExecutionWindow,
} from "./mesaExecutionRange";

describe("execution chart period", () => {
  it("initializes snapshot offsets in UTC when there is no named source zone", () => {
    const data = {
      components: [
        {
          series: {
            role: "input",
            timezone: "Offset del snapshot",
            points: [
              {
                start: "2026-10-01T00:00:00-03:00",
                end: "2026-10-01T01:00:00-03:00",
                value: 50,
              },
            ],
          },
        },
      ],
    } as Parameters<typeof initialExecutionWindow>[0];
    const window = initialExecutionWindow(data);
    expect(window).toEqual({
      range_start: "2026-10-01T03:00",
      range_end: "2026-10-01T04:00",
      timezone: "UTC",
      resolution_hours: 1,
    });
    expect(executionChartRange(window)).toEqual({
      start: Date.parse("2026-10-01T03:00Z"),
      end: Date.parse("2026-10-01T04:00Z"),
    });
  });
  it("uses the execution zone independently of the browser and keeps the exclusive end", () => {
    expect(
      executionChartRange({
        range_start: "2026-10-01T00:00",
        range_end: "2026-10-04T00:00",
        timezone: "UTC",
      }),
    ).toEqual({
      start: Date.parse("2026-10-01T00:00Z"),
      end: Date.parse("2026-10-04T00:00Z"),
    });
    expect(
      executionChartRange({
        range_start: "2026-10-01T00:00",
        range_end: "2026-10-04T00:00",
        timezone: "America/Santiago",
      }),
    ).toEqual({
      start: Date.parse("2026-10-01T03:00Z"),
      end: Date.parse("2026-10-04T03:00Z"),
    });
  });

  it("handles daylight saving and explicit hydraulic UTC instants", () => {
    expect(
      executionChartRange({
        range_start: "2026-03-08T01:00",
        range_end: "2026-03-08T04:00",
        timezone: "America/New_York",
      }),
    ).toEqual({
      start: Date.parse("2026-03-08T06:00Z"),
      end: Date.parse("2026-03-08T08:00Z"),
    });
    expect(
      executionChartRange({
        range_start: "2026-10-01T00:00:00Z",
        range_end: "2026-10-04T00:00:00Z",
        timezone: "UTC",
      }),
    ).toEqual({
      start: Date.parse("2026-10-01T00:00Z"),
      end: Date.parse("2026-10-04T00:00Z"),
    });
  });

  it("rejects invalid, incomplete, reversed and nonexistent local dates", () => {
    const window = {
      range_start: "2026-10-01T00:00",
      range_end: "2026-10-04T00:00",
      timezone: "UTC",
    };
    for (const changes of [
      { range_start: "" },
      { range_end: "2026-09-01T00:00" },
      { range_end: window.range_start },
      { timezone: "invalid" },
      { range_start: "2026-03-08T02:30", timezone: "America/New_York" },
    ]) {
      expect(executionChartRange({ ...window, ...changes })).toBeNull();
    }
  });
});
