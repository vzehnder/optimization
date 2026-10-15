import { useId } from "react";
import type { HydraulicTravelTimeParameters } from "./api/client";

const timeUnits = {
  seconds: { label: "Segundos", hours: 1 / 3600 },
  minutes: { label: "Minutos", hours: 1 / 60 },
  hours: { label: "Horas", hours: 1 },
  days: { label: "Días", hours: 24 },
};

export function HydraulicTravelTime({
  value,
  onChange,
}: {
  value: HydraulicTravelTimeParameters;
  onChange: (patch: HydraulicTravelTimeParameters) => void;
}) {
  const id = useId();
  const unit = value.travel_time_unit ?? "hours";
  const hours = value.travel_time_hours ?? 0;
  return (
    <fieldset className="draft-field-grid">
      <legend>Transporte de agua</legend>
      <label className="field-row" htmlFor={`${id}-time`}>
        <span>Tiempo de viaje</span>
        <input
          id={`${id}-time`}
          type="number"
          min="0"
          step="any"
          required
          value={Number((hours / timeUnits[unit].hours).toPrecision(12))}
          onChange={(event) =>
            onChange({
              travel_time_hours:
                Number(event.target.value) * timeUnits[unit].hours,
            })
          }
        />
      </label>
      <label className="field-row" htmlFor={`${id}-unit`}>
        <span>Unidad del tiempo de viaje</span>
        <select
          id={`${id}-unit`}
          value={unit}
          onChange={(event) =>
            onChange({
              travel_time_unit: event.target.value as keyof typeof timeUnits,
            })
          }
        >
          {Object.entries(timeUnits).map(([key, option]) => (
            <option key={key} value={key}>
              {option.label}
            </option>
          ))}
        </select>
      </label>
      <p className="hydraulic-properties-hint">
        Cero significa llegada en el mismo intervalo. El retardo se calcula con
        las fechas y duraciones de los intervalos, aunque cambien de tamaño.
      </p>
      <details>
        <summary>Condición inicial</summary>
        {value.initial_arrivals != null ? (
          <>
            <p>
              Hay un calendario de llegadas iniciales importado (
              {value.initial_arrivals.length} intervalos).
            </p>
            <button
              type="button"
              className="secondary-action"
              onClick={() =>
                onChange({ initial_arrivals: null, initial_flow_m3s: 0 })
              }
            >
              Usar caudal previo constante
            </button>
          </>
        ) : (
          <>
            <label className="field-row" htmlFor={`${id}-initial`}>
              <span>Caudal previo al inicio (m³/s)</span>
              <input
                id={`${id}-initial`}
                type="number"
                min="0"
                step="any"
                value={value.initial_flow_m3s ?? 0}
                onChange={(event) =>
                  onChange({ initial_flow_m3s: Number(event.target.value) })
                }
              />
            </label>
            <p>
              Agua inicial en tránsito:{" "}
              {Number(
                (hours * (value.initial_flow_m3s ?? 0) * 0.0036).toPrecision(
                  12,
                ),
              )}{" "}
              hm³.
            </p>
            <p className="hydraulic-properties-hint">
              Se supone este caudal constante antes de comenzar. Con cero, el
              tramo comienza sin agua en tránsito.
            </p>
          </>
        )}
      </details>
    </fieldset>
  );
}
