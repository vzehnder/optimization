import { useState } from "react";
import { ruleUnit } from "./ruleUnits";

export interface RuleObject {
  id: number;
  key: string;
  display_name: string;
  kind: string;
  variables: Record<string, string>;
  member_ids?: number[];
  known_values?: Record<string, { value: number; unit: string }>;
  known_series?: Record<string, { values: number[]; unit: string }>;
}
export interface RuleAlias {
  alias: string;
  object_id: number;
}
export function RuleObjects({
  objects,
  objectId,
  aliases,
  onChange,
}: {
  objects: RuleObject[];
  objectId: number;
  aliases: RuleAlias[];
  onChange: (aliases: RuleAlias[]) => void;
}) {
  const [selection, setSelection] = useState("");
  const [alias, setAlias] = useState("");
  const valid =
    /^[a-zA-Z][a-zA-Z0-9_]{0,63}$/.test(alias) &&
    !aliases.some((a) => a.alias === alias) &&
    objects.some((o) => o.id === Number(selection));
  const references = [{ alias: "", object_id: objectId }, ...aliases];
  return (
    <fieldset>
      <legend>Objetos y variables del modelo</legend>
      <p>
        Los alias conservan la identidad del objeto.
        {objects.some((o) => o.kind === "hydraulic_plant") &&
          " La potencia de una planta suma las unidades activas de este caso."}
      </p>
      <label>
        Objeto a relacionar
        <select
          value={selection}
          onChange={(e) => setSelection(e.target.value)}
        >
          <option value="">Selecciona un objeto</option>
          {objects.map((o) => (
            <option key={o.id} value={o.id}>
              {o.display_name} · {o.key}
            </option>
          ))}
        </select>
      </label>
      <label>
        Alias del objeto
        <input
          value={alias}
          onChange={(e) => setAlias(e.target.value)}
          maxLength={64}
        />
      </label>
      <button
        type="button"
        disabled={!valid || aliases.length >= 50}
        onClick={() => {
          onChange([...aliases, { alias, object_id: Number(selection) }]);
          setAlias("");
        }}
      >
        Agregar alias
      </button>
      {references.map((ref) => {
        const object = objects.find((o) => o.id === ref.object_id);
        return (
          <div key={ref.alias}>
            <strong>
              {ref.alias || "Objeto actual"} ·{" "}
              {object?.display_name ?? `Objeto ${ref.object_id} no disponible`}
            </strong>
            {object?.member_ids && (
              <p>{object.member_ids.length} unidades en esta planta.</p>
            )}
            {object?.kind === "battery" && (
              <p>
                Carga y descarga son potencias positivas en MW, medias del
                intervalo. La energía al final del período se expresa en MWh.
              </p>
            )}
            {object?.kind === "grid" && (
              <p>
                Importación y exportación son magnitudes no negativas en MW,
                medias del intervalo. En exportación − importación, positivo
                significa exportación neta; negativo, importación neta.
              </p>
            )}
            {object?.kind === "renewable" && (
              <p>
                Generación y recorte son magnitudes no negativas en MW, medias
                del intervalo. Su suma es la disponibilidad conocida; el solver
                decide cuánto utilizar y recortar.
              </p>
            )}
            {object?.kind === "load" && (
              <p>La demanda fija es un dato conocido en MW.</p>
            )}
            <ul>
              {Object.entries(object?.variables ?? {}).map(([name, unit]) => (
                <li key={name}>
                  <code>{`ctx.${ref.alias ? `objetos.${ref.alias}` : "objeto"}.${name}[t] · ${ruleUnit(unit)}`}</code>
                </li>
              ))}
            </ul>
            {Object.entries(object?.known_values ?? {}).map(([name, value]) => (
              <p key={name}>
                <code>{`ctx.${ref.alias ? `objetos.${ref.alias}` : "objeto"}.${name}`}</code>
                : {value.value} {ruleUnit(value.unit)} · dato conocido
              </p>
            ))}
            {Object.entries(object?.known_series ?? {}).map(
              ([name, series]) => (
                <p key={name}>
                  <code>{`ctx.${ref.alias ? `objetos.${ref.alias}` : "objeto"}.${name}[t] · ${ruleUnit(series.unit)}`}</code>
                  {" · dato conocido del caso por período"}
                </p>
              ),
            )}
            {ref.alias && (
              <button
                type="button"
                onClick={() =>
                  onChange(aliases.filter((a) => a.alias !== ref.alias))
                }
              >
                Quitar alias {ref.alias}
              </button>
            )}
          </div>
        );
      })}
    </fieldset>
  );
}
