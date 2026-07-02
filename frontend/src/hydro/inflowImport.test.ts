import { describe, expect, it } from "vitest";

import * as XLSX from "xlsx";

import {
  InflowImportError,
  parseInflowCsv,
  parseInflowWorkbook,
} from "./inflowImport";

describe("parseInflowCsv", () => {
  it("parses a 3-column csv with header into inflow points", () => {
    const csv = [
      "timestamp,duration_hours,value_m3s",
      "2026-01-01T00:00:00,1,12.5",
      "2026-01-01T01:00:00,2,13",
    ].join("\n");

    expect(parseInflowCsv(csv)).toEqual([
      { timestamp: "2026-01-01T00:00:00", duration_hours: 1, value_m3s: 12.5 },
      { timestamp: "2026-01-01T01:00:00", duration_hours: 2, value_m3s: 13 },
    ]);
  });

  it("throws a helpful error when a required column is missing", () => {
    const csv = ["timestamp,value_m3s", "2026-01-01T00:00:00,12.5"].join("\n");

    expect(() => parseInflowCsv(csv)).toThrow(InflowImportError);
    expect(() => parseInflowCsv(csv)).toThrow(/duration_hours/);
  });

  it("throws pointing at the offending data row when a number is invalid", () => {
    const csv = [
      "timestamp,duration_hours,value_m3s",
      "2026-01-01T00:00:00,1,12.5",
      "2026-01-01T01:00:00,1,abc",
    ].join("\n");

    expect(() => parseInflowCsv(csv)).toThrow(InflowImportError);
    // second data row -> reported as fila 2
    expect(() => parseInflowCsv(csv)).toThrow(/fila 2/);
  });
});

describe("parseInflowWorkbook", () => {
  it("parses the first sheet of an xlsx workbook into inflow points", () => {
    const sheet = XLSX.utils.aoa_to_sheet([
      ["timestamp", "duration_hours", "value_m3s"],
      ["2026-01-01T00:00:00", 1, 12.5],
      ["2026-01-01T01:00:00", 2, 13],
    ]);
    const workbook = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(workbook, sheet, "afluentes");
    const buffer = XLSX.write(workbook, {
      type: "array",
      bookType: "xlsx",
    }) as ArrayBuffer;

    expect(parseInflowWorkbook(buffer)).toEqual([
      { timestamp: "2026-01-01T00:00:00", duration_hours: 1, value_m3s: 12.5 },
      { timestamp: "2026-01-01T01:00:00", duration_hours: 2, value_m3s: 13 },
    ]);
  });
});
