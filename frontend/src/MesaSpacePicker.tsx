import { useState } from "react";
import {
  contains,
  describePlacement,
  gridSize,
  overlaps,
  rectangle,
  type MesaTab,
  type Placement,
} from "./mesaLayout";

export function MesaSpacePicker({
  tab,
  panelId,
  initial,
  onApply,
  onCancel,
}: {
  tab: MesaTab;
  panelId: string;
  initial: Placement;
  onApply: (area: Placement) => void;
  onCancel: () => void;
}) {
  const { rows, columns } = gridSize(tab.layout);
  const [selection, setSelection] = useState(initial);
  const [anchor, setAnchor] = useState<{ row: number; column: number } | null>(
    null,
  );
  const [hovered, setHovered] = useState<{
    row: number;
    column: number;
  } | null>(null);
  const candidate = anchor && hovered ? rectangle(anchor, hovered) : selection;
  const others = tab.panels.filter((p) => p.id !== panelId && p.placement);
  const conflicts = others.filter((p) => overlaps(candidate, p.placement!));
  return (
    <section
      className="mesa-space-picker"
      aria-label="Elegir espacio de la vista"
    >
      <p id="mesa-space-instructions">
        Marca una celda o dos esquinas para ocupar un rectángulo. Las celdas
        ocupadas por otras vistas no se pueden utilizar.
      </p>
      <div className="mesa-space-legend" aria-hidden="true">
        <span>
          <i className="is-selected" /> Tu selección
        </span>
        <span>
          <i className="is-occupied" /> Ocupada
        </span>
        <span>
          <i /> Libre
        </span>
      </div>
      <div
        className="mesa-space-map"
        style={{
          gridTemplateColumns: `1.4rem repeat(${columns}, minmax(0, 1fr))`,
        }}
        role="group"
        aria-label={`${rows} filas por ${columns} columnas`}
        aria-describedby="mesa-space-instructions"
      >
        <span aria-hidden="true" />
        {Array.from({ length: columns }, (_, c) => (
          <span
            className="mesa-space-coordinate"
            aria-hidden="true"
            key={`c${c}`}
          >
            {c + 1}
          </span>
        ))}
        {Array.from({ length: rows }, (_, r) => [
          <span
            className="mesa-space-coordinate"
            aria-hidden="true"
            key={`r${r}`}
          >
            {r + 1}
          </span>,
          ...Array.from({ length: columns }, (_, c) => {
            const row = r + 1;
            const column = c + 1;
            const owner = others.find((p) =>
              contains(p.placement!, row, column),
            );
            const selected = contains(candidate, row, column);
            return (
              <button
                type="button"
                key={`${row}:${column}`}
                className={`mesa-space-cell${owner ? " is-occupied" : ""}${selected ? " is-selected" : ""}${selected && conflicts.length ? " is-invalid" : ""}`}
                aria-label={`Fila ${row}, columna ${column}${owner ? ` · Ocupada por ${owner.title}` : " · Libre"}`}
                aria-pressed={selected}
                aria-disabled={!!owner}
                title={
                  owner
                    ? `Ocupada por ${owner.title}`
                    : `Fila ${row}, columna ${column}`
                }
                onPointerEnter={() => {
                  if (anchor) setHovered({ row, column });
                }}
                onFocus={() => {
                  if (anchor) setHovered({ row, column });
                }}
                onKeyDown={(event) => {
                  const offset = {
                    ArrowRight: 1,
                    ArrowLeft: -1,
                    ArrowDown: columns,
                    ArrowUp: -columns,
                  }[event.key];
                  if (offset === undefined) return;
                  event.preventDefault();
                  const buttons =
                    event.currentTarget.parentElement!.querySelectorAll<HTMLButtonElement>(
                      "button",
                    );
                  buttons[r * columns + c + offset]?.focus();
                }}
                onClick={() => {
                  if (owner) return;
                  const cell = { row, column };
                  if (!anchor) {
                    setSelection(rectangle(cell, cell));
                    setAnchor(cell);
                    setHovered(cell);
                  } else {
                    const area = rectangle(anchor, cell);
                    setHovered(cell);
                    if (others.some((p) => overlaps(area, p.placement!)))
                      return;
                    setSelection(area);
                    setAnchor(null);
                    setHovered(null);
                  }
                }}
              >
                <span aria-hidden="true">
                  {owner ? owner.title : selected ? "✓" : "·"}
                </span>
              </button>
            );
          }),
        ])}
      </div>
      <p
        className={conflicts.length ? "mesa-space-error" : "mesa-space-summary"}
        role="status"
      >
        {conflicts.length
          ? `Ese rectángulo se solapa con ${conflicts.map((p) => `«${p.title}»`).join(", ")}. Elige un espacio libre.`
          : `${describePlacement(candidate)} · ${candidate.row_span ?? 1} × ${candidate.column_span ?? 1} celdas`}
      </p>
      <div className="mesa-space-actions">
        <button
          type="button"
          onClick={() => {
            setAnchor(null);
            setHovered(null);
          }}
        >
          Reiniciar selección
        </button>
        <button type="button" onClick={onCancel}>
          Cancelar selección
        </button>
        <button
          type="button"
          disabled={!!conflicts.length}
          onClick={() => onApply(candidate)}
        >
          Usar este espacio
        </button>
      </div>
    </section>
  );
}
