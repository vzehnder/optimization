import type { RuleObject } from "./RuleObjects";
import { ruleUnit } from "./ruleUnits";

export interface TemporalPolicy {
  first_period: "omit" | "initial";
  initial_values: {
    object_id: number;
    variable: string;
    unit: string;
    value: number | null;
    timestamp: string;
  }[];
}

export function RuleTemporal({
  policy,
  onChange,
  objects,
  battery = false,
  powerVariable,
}: {
  policy: TemporalPolicy | null;
  onChange: (policy: TemporalPolicy | null) => void;
  objects: RuleObject[];
  battery?: boolean;
  powerVariable?: string;
}) {
  const variables = objects.flatMap((object) =>
    Object.entries(object.variables).map(([variable, unit]) => ({
      object_id: object.id,
      variable,
      unit,
      label: `${object.display_name}.${variable} · ${ruleUnit(unit)}`,
    })),
  );
  return (
    <fieldset>
      <legend>Referencias temporales y rampas</legend>
      <label>
        Política del primer período
        <select
          value={policy?.first_period ?? ""}
          onChange={(event) =>
            onChange(
              event.target.value
                ? {
                    first_period: event.target
                      .value as TemporalPolicy["first_period"],
                    initial_values: [],
                  }
                : null,
            )
          }
        >
          <option value="">Sin referencias temporales</option>
          <option value="omit">Omitir la primera comparación</option>
          <option value="initial">Usar condición inicial declarada</option>
        </select>
      </label>
      <p>
        Las rampas entre medias usan la distancia entre inicios, en horas. Cada
        subida y bajada se declara por separado.
      </p>
      {battery && (
        <p>
          Para energía, las transiciones usan los cierres de los intervalos.
        </p>
      )}
      {policy?.first_period === "omit" && (
        <p>
          Se omite la comparación del primer período con el exterior del
          horizonte.
        </p>
      )}
      {policy?.first_period === "initial" && (
        <>
          <p>
            Declara un valor y un instante con UTC u offset para cada variable
            usada en las transiciones.
          </p>
          {policy.initial_values.map((value, index) => {
            const update = (patch: Partial<typeof value>) =>
              onChange({
                ...policy,
                initial_values: policy.initial_values.map((row, i) =>
                  i === index ? { ...row, ...patch } : row,
                ),
              });
            return (
              <div className="rule-parameter" key={index}>
                <label>
                  Variable inicial {index + 1}
                  <select
                    value={`${value.object_id}:${value.variable}`}
                    onChange={(event) => {
                      const selected = variables.find(
                        (v) =>
                          `${v.object_id}:${v.variable}` === event.target.value,
                      );
                      if (selected)
                        update({
                          object_id: selected.object_id,
                          variable: selected.variable,
                          unit: selected.unit,
                        });
                    }}
                  >
                    {variables.map((v) => (
                      <option
                        key={`${v.object_id}:${v.variable}`}
                        value={`${v.object_id}:${v.variable}`}
                      >
                        {v.label}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Valor inicial {index + 1}
                  <input
                    type="number"
                    step="any"
                    value={value.value ?? ""}
                    onChange={(event) =>
                      update({
                        value:
                          event.target.value === ""
                            ? null
                            : Number(event.target.value),
                      })
                    }
                  />
                </label>
                <span>{ruleUnit(value.unit)}</span>
                <label>
                  Instante inicial {index + 1}
                  <input
                    placeholder="2026-01-01T00:00:00Z"
                    value={value.timestamp}
                    onChange={(event) =>
                      update({ timestamp: event.target.value })
                    }
                  />
                </label>
                <button
                  type="button"
                  onClick={() =>
                    onChange({
                      ...policy,
                      initial_values: policy.initial_values.filter(
                        (_, i) => i !== index,
                      ),
                    })
                  }
                >
                  Quitar valor inicial {index + 1}
                </button>
              </div>
            );
          })}
          <button
            type="button"
            disabled={!variables.length || policy.initial_values.length >= 100}
            onClick={() => {
              const first = variables[0];
              onChange({
                ...policy,
                initial_values: [
                  ...policy.initial_values,
                  {
                    object_id: first.object_id,
                    variable: first.variable,
                    unit: first.unit,
                    value: null,
                    timestamp: "",
                  },
                ],
              });
            }}
          >
            Agregar valor inicial
          </button>
        </>
      )}
      <details>
        <summary>Ejemplo de rampas de potencia</summary>
        <p>
          Define subida y bajada en mw_per_h (MW/h).
          {!battery && !powerVariable && " Para caudal, usa m3_per_s_per_h."}
        </p>
        <pre>
          {`def construir(ctx):\n    for paso in ctx.transiciones(ctx.objeto.${powerVariable ?? (battery ? "descarga" : "potencia")}):\n        diferencia = paso.actual - paso.anterior\n        ctx.restriccion("subida", paso.periodo, diferencia <= ctx.parametros.subida * paso.horas)\n        ctx.restriccion("bajada", paso.periodo, -diferencia <= ctx.parametros.bajada * paso.horas)`}
        </pre>
      </details>
    </fieldset>
  );
}
