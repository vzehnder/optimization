import type { components } from "./api/schema";

export type Panel = components["schemas"]["MesaPanelPreference"];
export type Placement = components["schemas"]["MesaPanelPlacement"];
export type MesaTab = components["schemas"]["MesaTabPreference"];

export function gridSize(layout: string) {
  const [rows, columns] = layout.split("x").map(Number);
  return { rows, columns };
}

export function rectangle(
  start: { row: number; column: number },
  end: { row: number; column: number },
): Placement {
  return {
    row: Math.min(start.row, end.row),
    column: Math.min(start.column, end.column),
    row_span: Math.abs(start.row - end.row) + 1,
    column_span: Math.abs(start.column - end.column) + 1,
  };
}

export function contains(area: Placement, row: number, column: number) {
  return (
    row >= area.row &&
    row < area.row + (area.row_span ?? 1) &&
    column >= area.column &&
    column < area.column + (area.column_span ?? 1)
  );
}

export function overlaps(a: Placement, b: Placement) {
  return (
    a.row < b.row + (b.row_span ?? 1) &&
    b.row < a.row + (a.row_span ?? 1) &&
    a.column < b.column + (b.column_span ?? 1) &&
    b.column < a.column + (a.column_span ?? 1)
  );
}

export function fits(area: Placement, rows: number, columns: number) {
  return (
    area.row >= 1 &&
    area.column >= 1 &&
    area.row + (area.row_span ?? 1) - 1 <= rows &&
    area.column + (area.column_span ?? 1) - 1 <= columns
  );
}

export function firstFree(layout: string, panels: Panel[]): Placement | null {
  const { rows, columns } = gridSize(layout);
  for (let row = 1; row <= rows; row++) {
    for (let column = 1; column <= columns; column++) {
      const area = { row, column, row_span: 1, column_span: 1 };
      if (!panels.some((p) => p.placement && overlaps(area, p.placement)))
        return area;
    }
  }
  return null;
}

// Reserve explicit rectangles first, then migrate legacy views into free cells.
// Legacy hidden views are retained until the grid has room for them.
export function placePanels(tab: MesaTab): MesaTab {
  const panels = tab.panels.map((panel) => ({ ...panel }));
  for (const panel of panels) {
    if (!panel.placement) panel.placement = firstFree(tab.layout, panels);
  }
  return { ...tab, panels };
}

export function describePlacement(area: Placement) {
  const endRow = area.row + (area.row_span ?? 1) - 1;
  const endColumn = area.column + (area.column_span ?? 1) - 1;
  return `${area.row === endRow ? `Fila ${area.row}` : `Filas ${area.row}–${endRow}`} · ${area.column === endColumn ? `columna ${area.column}` : `columnas ${area.column}–${endColumn}`}`;
}
