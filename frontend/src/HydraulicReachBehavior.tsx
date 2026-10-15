import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import type {
  HydraulicCurvePoint,
  HydraulicDiagramNodeWrite,
  HydraulicDiagramReachWrite,
  HydraulicFlowBehavior,
} from "./api/client";
import "./hydraulicReachBehavior.css";

function operatingLevels(source?: HydraulicDiagramNodeWrite) {
  const points = source?.storage_elevation_curve?.points ?? [];
  const reservoir = source?.reservoir;
  if (!reservoir || points.length < 2) return null;
  function level(volume: number) {
    for (let i = 1; i < points.length; i++) {
      const a = points[i - 1],
        b = points[i];
      if (a.x_value <= volume && volume <= b.x_value && b.x_value > a.x_value) {
        return (
          a.y_value +
          ((volume - a.x_value) * (b.y_value - a.y_value)) /
            (b.x_value - a.x_value)
        );
      }
    }
    return null;
  }
  const lower = level(reservoir.storage_min_hm3),
    upper = level(reservoir.storage_max_hm3);
  return lower !== null && upper !== null ? [lower, upper] : null;
}

function curveError(points: HydraulicCurvePoint[], levels: number[] | null) {
  if (points.length < 2) return "Agrega al menos dos puntos a la curva.";
  if (
    points.some(
      (p) =>
        !Number.isFinite(p.x_value) ||
        !Number.isFinite(p.y_value) ||
        p.y_value < 0,
    )
  ) {
    return "Usa valores finitos y caudales no negativos.";
  }
  if (points.some((p, i) => i > 0 && p.x_value <= points[i - 1].x_value)) {
    return "Las cotas deben estar ordenadas de menor a mayor, sin repetirse.";
  }
  if (
    levels &&
    (points[0].x_value > levels[0] ||
      points[points.length - 1].x_value < levels[1])
  ) {
    return "La tabla debe cubrir todo el rango de cotas operativo del embalse. No se extrapola.";
  }
  return "";
}

function CurvePlot({ points }: { points: HydraulicCurvePoint[] }) {
  if (points.length < 2 || curveError(points, null)) return null;
  const minX = points[0].x_value,
    maxX = points[points.length - 1].x_value;
  const maxY = Math.max(1, ...points.map((p) => p.y_value));
  const x = (n: number) => 65 + ((n - minX) / (maxX - minX)) * 500;
  const y = (n: number) => 185 - (n / maxY) * 145;
  return (
    <svg
      className="seepage-curve-plot"
      viewBox="0 0 640 240"
      role="img"
      aria-label="Curva cota–caudal de filtración"
    >
      <path d="M65 35 V185 H565" fill="none" stroke="currentColor" />
      <text x="65" y="22">
        Caudal (m³/s)
      </text>
      <text x="315" y="232" textAnchor="middle">
        Cota (m s. n. m.)
      </text>
      <text x="55" y="189" textAnchor="end">
        0
      </text>
      <text x="55" y="44" textAnchor="end">
        {maxY.toLocaleString("es-CL")}
      </text>
      <text x="65" y="207" textAnchor="middle">
        {minX.toLocaleString("es-CL")}
      </text>
      <text x="565" y="207" textAnchor="middle">
        {maxX.toLocaleString("es-CL")}
      </text>
      <polyline
        points={points.map((p) => `${x(p.x_value)},${y(p.y_value)}`).join(" ")}
        fill="none"
        stroke="#087f8c"
        strokeWidth="3"
      />
      {points.map((p, i) => (
        <circle
          key={i}
          cx={x(p.x_value)}
          cy={y(p.y_value)}
          r="4"
          fill="#087f8c"
        >
          <title>
            {p.x_value} m → {p.y_value} m³/s
          </title>
        </circle>
      ))}
    </svg>
  );
}

function SeepageCurveDialog({
  reach,
  source,
  behavior,
  onApply,
  onClose,
}: {
  reach: HydraulicDiagramReachWrite;
  source?: HydraulicDiagramNodeWrite;
  behavior: HydraulicFlowBehavior;
  onApply: (behavior: HydraulicFlowBehavior) => void;
  onClose: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [draft, setDraft] = useState<HydraulicFlowBehavior>(() => ({
    ...behavior,
    curve: {
      ...behavior.curve,
      points: behavior.curve.points.map((p) => ({ ...p })),
    },
  }));
  useEffect(() => {
    const element = dialog.current;
    element?.showModal();
    return () => element?.close();
  }, []);
  const points = draft.curve.points;
  const levels = operatingLevels(source);
  const error = curveError(points, levels);
  function setPoints(next: HydraulicCurvePoint[]) {
    setDraft({
      ...draft,
      curve: { ...draft.curve, curve_set_id: null, points: next },
    });
  }
  return createPortal(
    <dialog
      ref={dialog}
      className="seepage-curve-dialog"
      aria-labelledby="seepage-curve-title"
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
    >
      <h2 id="seepage-curve-title">
        Curva de filtración · {reach.technical_key}
      </h2>
      <p>
        Embalse de referencia: <strong>{reach.from_node_key}</strong>. El caudal
        del tramo será igual al valor interpolado.
      </p>
      {levels && (
        <p>
          Rango operativo: {levels[0].toLocaleString("es-CL")}–
          {levels[1].toLocaleString("es-CL")} m s. n. m.
        </p>
      )}
      <CurvePlot points={points} />
      <div className="seepage-table-scroll">
        <table className="seepage-curve-table">
          <thead>
            <tr>
              <th scope="col">Cota (m s. n. m.)</th>
              <th scope="col">Filtración (m³/s)</th>
              <th scope="col">Acciones</th>
            </tr>
          </thead>
          <tbody>
            {points.map((point, index) => (
              <tr key={index}>
                <td>
                  <input
                    type="number"
                    step="any"
                    aria-label={`Cota punto ${index + 1}`}
                    value={point.x_value}
                    onChange={(event) =>
                      setPoints(
                        points.map((p, i) =>
                          i === index
                            ? { ...p, x_value: Number(event.target.value) }
                            : p,
                        ),
                      )
                    }
                  />
                </td>
                <td>
                  <input
                    type="number"
                    step="any"
                    min="0"
                    aria-label={`Caudal punto ${index + 1}`}
                    value={point.y_value}
                    onChange={(event) =>
                      setPoints(
                        points.map((p, i) =>
                          i === index
                            ? { ...p, y_value: Number(event.target.value) }
                            : p,
                        ),
                      )
                    }
                  />
                </td>
                <td>
                  <button
                    type="button"
                    className="secondary-action"
                    aria-label={`Quitar punto ${index + 1}`}
                    onClick={() =>
                      setPoints(points.filter((_, i) => i !== index))
                    }
                  >
                    Quitar
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <button
        type="button"
        className="secondary-action"
        onClick={() =>
          setPoints([
            ...points,
            {
              x_value: points.length
                ? points[points.length - 1].x_value + 1
                : (levels?.[0] ?? 0),
              y_value: 0,
            },
          ])
        }
      >
        Agregar punto
      </button>
      {error && (
        <p className="seepage-curve-error" role="status">
          {error}
        </p>
      )}
      <details className="seepage-advanced">
        <summary>Configuración avanzada</summary>
        <label>
          Cota de referencia
          <select
            aria-label="Cota de referencia"
            value={draft.level_timing}
            onChange={(event) =>
              setDraft({
                ...draft,
                level_timing: event.target.value as "start" | "end",
              })
            }
          >
            <option value="start">Cota al inicio del intervalo</option>
            <option value="end">Cota al cierre del intervalo</option>
          </select>
        </label>
        <p>
          Al inicio, el primer intervalo utiliza el volumen inicial del embalse.
          Al cierre, el nivel se resuelve junto con el balance del mismo
          intervalo.
        </p>
      </details>
      <footer className="seepage-dialog-actions">
        <span>Los cambios se guardan al guardar el diagrama.</span>
        <button type="button" className="secondary-action" onClick={onClose}>
          Cancelar
        </button>
        <button
          type="button"
          disabled={!!error}
          onClick={() => {
            onApply(draft);
            onClose();
          }}
        >
          Listo
        </button>
      </footer>
    </dialog>,
    document.body,
  );
}

export function HydraulicReachBehavior({
  reach,
  source,
  onChange,
}: {
  reach: HydraulicDiagramReachWrite;
  source?: HydraulicDiagramNodeWrite;
  onChange: (behavior: HydraulicFlowBehavior | null) => void;
}) {
  const [adding, setAdding] = useState(false);
  const [editing, setEditing] = useState(false);
  const behavior = reach.flow_behavior;
  const validSource = source?.component_type === "reservoir";
  if (!behavior)
    return (
      <div className="seepage-add-behavior">
        <button
          type="button"
          className="secondary-action"
          aria-expanded={adding}
          onClick={() => setAdding(!adding)}
        >
          + Agregar comportamiento
        </button>
        {adding && (
          <div className="seepage-behavior-options">
            <button
              type="button"
              disabled={!validSource}
              onClick={() => {
                onChange({
                  kind: "seepage",
                  level_timing: "start",
                  curve: { points: [] },
                });
                setAdding(false);
              }}
            >
              Filtración según cota
            </button>
            {!validSource && (
              <p>
                Este comportamiento requiere un embalse como origen del tramo.
              </p>
            )}
          </div>
        )}
      </div>
    );
  return (
    <section
      className="seepage-behavior-card"
      aria-label="Comportamiento del tramo"
    >
      <h3>Filtración según cota</h3>
      <p>
        {reach.from_node_key} · {behavior.curve.points.length} puntos ·{" "}
        {behavior.level_timing === "start"
          ? "Cota al inicio"
          : "Cota al cierre"}
      </p>
      {!validSource ? (
        <p role="alert">
          La filtración requiere un embalse como origen. Corrige el origen o
          quita este comportamiento.
        </p>
      ) : (
        curveError(behavior.curve.points, operatingLevels(source)) && (
          <p className="seepage-curve-error">
            {curveError(behavior.curve.points, operatingLevels(source))}
          </p>
        )
      )}
      <div className="seepage-card-actions">
        <button
          type="button"
          className="secondary-action"
          disabled={!validSource}
          onClick={() => setEditing(true)}
        >
          Editar tabla y gráfico
        </button>
        <button
          type="button"
          className="secondary-action"
          onClick={() => onChange(null)}
        >
          Quitar filtración
        </button>
      </div>
      {editing && (
        <SeepageCurveDialog
          reach={reach}
          source={source}
          behavior={behavior}
          onApply={onChange}
          onClose={() => setEditing(false)}
        />
      )}
    </section>
  );
}
