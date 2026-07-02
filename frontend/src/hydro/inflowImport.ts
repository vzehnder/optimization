import * as XLSX from "xlsx";

import type { HydraulicNaturalInflowSeriesPoint } from "../api/client";

const REQUIRED_HEADERS = ["timestamp", "duration_hours", "value_m3s"] as const;

export class InflowImportError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "InflowImportError";
  }
}

/** Core: turn a table of string cells (header + body) into inflow points. */
export function parseInflowRows(
  rows: string[][],
): HydraulicNaturalInflowSeriesPoint[] {
  const nonEmpty = rows.filter((cells) =>
    cells.some((cell) => cell !== ""),
  );
  if (nonEmpty.length === 0) {
    throw new InflowImportError("El archivo esta vacio.");
  }

  const [header, ...body] = nonEmpty;
  const index = Object.fromEntries(
    REQUIRED_HEADERS.map((name) => [
      name,
      header.findIndex((cell) => cell.toLowerCase() === name),
    ]),
  );

  const missing = REQUIRED_HEADERS.filter((name) => index[name] < 0);
  if (missing.length) {
    throw new InflowImportError(
      `Faltan columnas requeridas: ${missing.join(", ")}. ` +
        `Se esperan: ${REQUIRED_HEADERS.join(", ")}.`,
    );
  }

  return body.map((cells, row) => {
    const timestamp = cells[index.timestamp];
    if (!timestamp) {
      throw new InflowImportError(`Marca temporal vacia en fila ${row + 1}.`);
    }
    return {
      timestamp,
      duration_hours: parseNumber(
        cells[index.duration_hours],
        "duration_hours",
        row,
      ),
      value_m3s: parseNumber(cells[index.value_m3s], "value_m3s", row),
    };
  });
}

export function parseInflowCsv(
  text: string,
): HydraulicNaturalInflowSeriesPoint[] {
  const rows = text.split(/\r?\n/).map(splitCsvLine);
  return parseInflowRows(rows);
}

export function parseInflowWorkbook(
  data: ArrayBuffer,
): HydraulicNaturalInflowSeriesPoint[] {
  const workbook = XLSX.read(data, { type: "array" });
  const sheetName = workbook.SheetNames[0];
  if (!sheetName) {
    throw new InflowImportError("El libro no tiene hojas.");
  }
  const aoa = XLSX.utils.sheet_to_json<unknown[]>(workbook.Sheets[sheetName], {
    header: 1,
    blankrows: false,
    raw: true,
  });
  const rows = aoa.map((cells) =>
    cells.map((cell) => (cell == null ? "" : String(cell).trim())),
  );
  return parseInflowRows(rows);
}

function splitCsvLine(line: string): string[] {
  return line.split(",").map((cell) => cell.trim().replace(/^"(.*)"$/, "$1"));
}

function parseNumber(raw: string, column: string, row: number): number {
  const value = Number(raw);
  if (raw === "" || Number.isNaN(value)) {
    throw new InflowImportError(
      `Valor invalido "${raw}" en columna ${column}, fila ${row + 1}.`,
    );
  }
  return value;
}
