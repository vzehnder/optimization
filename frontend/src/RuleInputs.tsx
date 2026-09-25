import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { requestJson } from "./api/client";
import { ProtectedJourneyProgress } from "./ProtectedMutationJourney";
import { ruleUnit } from "./ruleUnits";

export interface RuleInput {
  alias: string;
  object_id: number;
  signal_id: number;
  revision_id: number;
  content_hash: string;
  dimension_key: string;
  semantic_type_key: string;
  binding_role_key: "rule_inflow" | "rule_availability" | "rule_energy_reserve";
}
interface Candidate extends RuleInput {
  display_name: string;
  set_name: string;
  series_kind: "catalog" | "object_specific";
  unit_key: string;
}

export function RuleInputs({
  root,
  inputs,
  onChange,
  scenarioId,
  objects = [],
  requiredPorts,
}: {
  root: string;
  inputs: RuleInput[];
  onChange: (inputs: RuleInput[]) => void;
  scenarioId?: number | null;
  objects?: { id: number; label: string }[];
  requiredPorts?: Pick<
    RuleInput,
    | "alias"
    | "object_id"
    | "dimension_key"
    | "semantic_type_key"
    | "binding_role_key"
  >[];
}) {
  const [step, setStep] = useState<number | null>(null);
  const [kind, setKind] = useState("catalog");
  const [after, setAfter] = useState(0);
  const [selection, setSelection] = useState<Candidate>();
  const [alias, setAlias] = useState("");
  const [objectId, setObjectId] = useState(Number(root.split("/").at(-2)));
  const candidates = useQuery({
    queryKey: [root, "input-candidates", after, objectId, scenarioId],
    queryFn: () =>
      requestJson<{ items: Candidate[]; next_cursor: number | null }>(
        `${root}/input-candidates?after=${after}${scenarioId ? `&scenario_id=${scenarioId}&reference_object_id=${objectId}` : ""}`,
      ),
    enabled: step !== null,
    retry: false,
  });
  const validAlias =
    /^[a-zA-Z][a-zA-Z0-9_]{0,63}$/.test(alias) &&
    !inputs.some((p) => p.alias === alias) &&
    (!requiredPorts ||
      requiredPorts.some(
        (p) => p.alias === alias && selection && matchesPort(p, selection),
      ));
  function matchesPort(
    port: NonNullable<typeof requiredPorts>[number],
    candidate: Candidate,
  ) {
    return (
      port.object_id === candidate.object_id &&
      port.semantic_type_key === candidate.semantic_type_key &&
      port.binding_role_key === candidate.binding_role_key &&
      port.dimension_key === candidate.dimension_key
    );
  }
  const availablePorts = requiredPorts?.filter(
    (p) => !inputs.some((i) => i.alias === p.alias),
  );
  const choices = (candidates.data?.items ?? []).filter(
    (p) =>
      p.series_kind === kind &&
      (!availablePorts || availablePorts.some((port) => matchesPort(port, p))),
  );
  return (
    <fieldset className="rule-inputs">
      <legend>Entradas horarias</legend>
      <p>
        Selecciona entradas compatibles con el objeto. Cada entrada conserva su
        unidad y revisión.
      </p>
      {inputs.map((port, index) => (
        <div className="rule-input-pin" key={port.alias}>
          <strong>{port.alias}</strong>
          <span>
            Señal {port.signal_id} · revisión {port.revision_id} ·{" "}
            {ruleUnit(
              { flow: "m3_per_s", energy: "mwh", power: "mw" }[
                port.dimension_key
              ] ?? port.dimension_key,
            )}
          </span>
          <button
            type="button"
            onClick={() => onChange(inputs.filter((_, i) => i !== index))}
          >
            Quitar entrada {port.alias}
          </button>
        </div>
      ))}
      {step === null ? (
        <button
          type="button"
          disabled={inputs.length >= 20 || availablePorts?.length === 0}
          onClick={() => {
            setStep(0);
            setSelection(undefined);
            setAlias("");
            setAfter(0);
          }}
        >
          Seleccionar entrada
        </button>
      ) : (
        <section aria-label="Seleccionar entrada horaria">
          <ProtectedJourneyProgress step={step} />
          {step === 0 && (
            <div>
              {scenarioId && (
                <label>
                  Objeto de la entrada
                  <select
                    value={objectId}
                    onChange={(e) => {
                      setObjectId(Number(e.target.value));
                      setSelection(undefined);
                      setAfter(0);
                    }}
                  >
                    {objects.map((obj, index) => (
                      <option key={index} value={obj.id}>
                        {obj.label}
                      </option>
                    ))}
                  </select>
                </label>
              )}
              <label>
                <input
                  type="radio"
                  name="rule-input-kind"
                  checked={kind === "catalog"}
                  onChange={() => {
                    setKind("catalog");
                    setSelection(undefined);
                  }}
                />
                Serie genérica del catálogo
              </label>
              <label>
                <input
                  type="radio"
                  name="rule-input-kind"
                  checked={kind === "object_specific"}
                  onChange={() => {
                    setKind("object_specific");
                    setSelection(undefined);
                  }}
                />
                Serie específica de esta unidad
              </label>
            </div>
          )}
          {step === 1 && (
            <div>
              <label>
                Alias de entrada
                <input
                  value={alias}
                  onChange={(event) => setAlias(event.target.value)}
                />
              </label>
              {choices.map((item) => (
                <label key={item.signal_id}>
                  <input
                    type="radio"
                    name="rule-input-signal"
                    checked={selection?.signal_id === item.signal_id}
                    onChange={() => {
                      setSelection(item);
                      setAlias(
                        availablePorts?.find((p) => matchesPort(p, item))
                          ?.alias ??
                          (item.binding_role_key === "rule_availability"
                            ? "disponibilidad"
                            : item.binding_role_key === "rule_energy_reserve"
                              ? "reserva"
                              : "afluente"),
                      );
                    }}
                  />
                  {item.display_name} · {item.set_name} ·{" "}
                  {ruleUnit(item.unit_key)}
                </label>
              ))}
              {candidates.isPending && (
                <p role="status">Buscando entradas compatibles…</p>
              )}
              {candidates.data && choices.length === 0 && (
                <p>No hay entradas compatibles en esta página.</p>
              )}
              {candidates.data?.next_cursor && (
                <button
                  type="button"
                  onClick={() => setAfter(candidates.data!.next_cursor!)}
                >
                  Ver más entradas
                </button>
              )}
              {after > 0 && (
                <button type="button" onClick={() => setAfter(0)}>
                  Volver al inicio de entradas
                </button>
              )}
              {alias && !validAlias && (
                <p role="alert">
                  Usa un alias único que empiece por una letra, sin espacios.
                </p>
              )}
            </div>
          )}
          {step === 2 && selection && (
            <div>
              <p>
                Revisión {selection.revision_id} · {selection.display_name} ·{" "}
                {selection.series_kind === "catalog"
                  ? "Genérica"
                  : "Solo esta unidad"}
              </p>
              <p>
                Semántica: {selection.semantic_type_key}. Unidad:{" "}
                {selection.unit_key}.
              </p>
              <details>
                <summary>Identidad de la revisión</summary>
                <p className="rule-input-hash">{selection.content_hash}</p>
              </details>
            </div>
          )}
          {step === 3 && selection && (
            <p>
              Guardarás <strong>{alias}</strong> en el borrador de este objeto
              con la revisión {selection.revision_id}. Publica y prueba el
              horizonte completo antes de aplicar sus límites.
            </p>
          )}
          {candidates.isError && <p role="alert">{String(candidates.error)}</p>}
          <div className="rule-input-actions">
            <button type="button" onClick={() => setStep(null)}>
              Cancelar selección
            </button>
            {step > 0 && (
              <button type="button" onClick={() => setStep(step - 1)}>
                Paso anterior
              </button>
            )}
            {step < 3 ? (
              <button
                type="button"
                disabled={step > 0 && (!selection || !validAlias)}
                onClick={() => setStep(step + 1)}
              >
                Continuar selección
              </button>
            ) : (
              <button
                type="button"
                disabled={!selection || !validAlias}
                onClick={() => {
                  if (!selection) return;
                  const {
                    signal_id,
                    revision_id,
                    content_hash,
                    dimension_key,
                    semantic_type_key,
                    binding_role_key,
                    object_id,
                  } = selection;
                  onChange([
                    ...inputs,
                    {
                      alias,
                      signal_id,
                      revision_id,
                      content_hash,
                      dimension_key,
                      semantic_type_key,
                      binding_role_key,
                      object_id,
                    },
                  ]);
                  setStep(null);
                }}
              >
                Usar entrada en borrador
              </button>
            )}
          </div>
        </section>
      )}
    </fieldset>
  );
}
