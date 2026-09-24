import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { getCsrfToken, requestJson } from "./api/client";
import type { RuleDraft, RuleParameter } from "./ComponentRules";
import { RuleInputs, type RuleInput } from "./RuleInputs";
import type { RuleObject } from "./RuleObjects";
import { ruleErrorMessage } from "./ruleErrors";
import { ruleUnit } from "./ruleUnits";
import type { WindowPolicy } from "./RuleWindows";
import { ruleExamples } from "./ruleExamples";

export interface Template {
  rule_id: string;
  publication_id: string;
  revision: number;
  name: string;
  compatible_types: string[];
  required_capabilities: string[];
  parameters: (Omit<RuleParameter, "value" | "object_id"> & {
    owner: string | null;
  })[];
  aliases: { alias: string; kind: string; compatible_types?: string[] }[];
  inputs: (Pick<
    RuleInput,
    "alias" | "dimension_key" | "semantic_type_key" | "binding_role_key"
  > & { owner: string })[];
  temporal?: null | {
    first_period: "omit" | "initial";
    initial_values: { owner: string; variable: string; unit: string }[];
  };
  windows?: WindowPolicy | null;
}

const capabilityNames: Record<string, string> = {
  "affine_flow.v1": "Límites de caudal",
  "affine_hydraulic.v1": "Relaciones hidráulicas",
  "affine_temporal.v1": "Rampas y períodos anteriores",
  "affine_budget.v1": "Presupuestos por ventana",
};

export function RuleLibrary({
  root,
  scenarioId,
  objectKind = "hydraulic_unit",
  onCreated,
  onOpenChange,
}: {
  root: string;
  scenarioId: number | null;
  objectKind?: string;
  onCreated: (rule: RuleDraft) => void;
  onOpenChange?: (open: boolean) => void;
}) {
  const [open, setOpen] = useState(false);
  const [selection, setSelection] = useState<Template>();
  const [comparison, setComparison] = useState<Template>();
  const [query, setQuery] = useState("");
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState("");
  const projectRoot = root.split("/linkable-objects/")[0];
  const library = useQuery({
    queryKey: [projectRoot, "rule-library"],
    queryFn: () =>
      requestJson<{ items: Template[] }>(`${projectRoot}/rule-library`),
    enabled: open,
    retry: false,
  });
  return (
    <section className="rule-library" aria-label="Biblioteca de reglas">
      <button
        type="button"
        onClick={() => {
          setOpen(!open);
          onOpenChange?.(!open);
          setSelection(undefined);
          void library.refetch();
        }}
      >
        Biblioteca del proyecto
      </button>
      {open && (
        <>
          <h2>Reutilizar una revisión</h2>
          <p>
            El código se comparte. Cada instancia tiene sus propios parámetros,
            referencias, variante y activación.
          </p>
          {!scenarioId && (
            <p>
              Abre la biblioteca desde un componente para elegir su contexto.
            </p>
          )}
          <label>
            Buscar regla
            <input value={query} onChange={(e) => setQuery(e.target.value)} />
          </label>
          {library.isPending && <p role="status">Cargando biblioteca…</p>}
          {library.isError && (
            <p role="alert">{ruleErrorMessage(library.error)}</p>
          )}
          {library.data?.items.length === 0 && (
            <p>
              No hay plantillas. Publica una revisión y ofrécela en la
              biblioteca.
            </p>
          )}
          {library.data?.items
            .filter((t) =>
              t.name.toLocaleLowerCase().includes(query.toLocaleLowerCase()),
            )
            .map((t) => (
              <article key={t.publication_id}>
                <h3>
                  {t.name} · revisión {t.revision}
                </h3>
                <p>
                  Tipos:{" "}
                  {t.compatible_types
                    .map((kind) =>
                      kind === "hydraulic_unit"
                        ? "Unidad hidráulica"
                        : kind === "hydro"
                          ? "Hidro simple"
                          : kind,
                    )
                    .join(", ")}{" "}
                  · Capacidades:{" "}
                  {t.required_capabilities
                    .map((key) => capabilityNames[key] ?? key)
                    .join(", ")}
                </p>
                <button
                  type="button"
                  disabled={
                    !scenarioId || !t.compatible_types.includes(objectKind)
                  }
                  onClick={() => setSelection(t)}
                >
                  Usar {t.name} · revisión {t.revision}
                </button>
                <button type="button" onClick={() => setComparison(t)}>
                  Comparar instancias · {t.name} · revisión {t.revision}
                </button>
              </article>
            ))}
          {comparison && (
            <InstanceComparison
              key={comparison.publication_id}
              path={`${projectRoot}/rule-library/${comparison.publication_id}/instances`}
            />
          )}
          {selection && scenarioId && (
            <InstanceForm
              key={selection.publication_id}
              root={root}
              scenarioId={scenarioId}
              template={selection}
              onCreated={(rule) => {
                setOpen(false);
                onOpenChange?.(false);
                onCreated(rule);
              }}
            />
          )}
          <details>
            <summary>Ejemplos editables</summary>
            <p>
              Se guardan como borradores propios. Completa los alias y entradas
              indicados en el código antes de probarlos.
            </p>
            {ruleExamples.map((example) => (
              <button
                key={example.name}
                type="button"
                disabled={creating || !scenarioId}
                onClick={() => {
                  setCreating(true);
                  setError("");
                  void (async () => {
                    try {
                      const draft = await requestJson<RuleDraft>(root, {
                        method: "POST",
                        headers: {
                          "Content-Type": "application/json",
                          "X-CSRF-Token": await getCsrfToken(),
                        },
                        body: JSON.stringify({
                          ...example,
                          expected_revision: 0,
                          scenario_id: scenarioId,
                          aliases: [],
                          inputs: [],
                        }),
                      });
                      setOpen(false);
                      onOpenChange?.(false);
                      onCreated(draft);
                    } catch (problem) {
                      setError(ruleErrorMessage(problem));
                    } finally {
                      setCreating(false);
                    }
                  })();
                }}
              >
                Crear ejemplo: {example.name}
              </button>
            ))}
          </details>
          {error && <p role="alert">{error}</p>}
        </>
      )}
    </section>
  );
}

interface ComparedInstance {
  id: string;
  name: string;
  object_id: number;
  variant_id: number;
  activation: string;
  validation_status: string;
  parameters: RuleParameter[];
  aliases: { alias: string; object_id: number }[];
  inputs: RuleInput[];
  preview: null | {
    row_count: number;
    rows: {
      name: string;
      period: number;
      relation: string;
      constant: number;
      unit: string;
      terms: { coefficient: number; object_id: number; variable: string }[];
    }[];
  };
}

function InstanceComparison({ path }: { path: string }) {
  const comparison = useQuery({
    queryKey: [path],
    queryFn: () => requestJson<{ items: ComparedInstance[] }>(path),
    retry: false,
  });
  return (
    <section aria-label="Comparación de instancias">
      <h3>Parámetros y filas efectivas</h3>
      {comparison.isPending && <p role="status">Cargando instancias…</p>}
      {comparison.isError && (
        <p role="alert">{ruleErrorMessage(comparison.error)}</p>
      )}
      {comparison.data?.items.length === 0 && (
        <p>Esta revisión aún no tiene instancias.</p>
      )}
      {comparison.data?.items.map((item) => (
        <article key={item.id}>
          <h4>
            {item.name} · objeto {item.object_id} · variante {item.variant_id}
          </h4>
          <p>
            {item.activation === "active" ? "Activa" : "Inactiva"} ·{" "}
            {item.validation_status === "stale"
              ? "Obsoleta"
              : item.validation_status === "valid"
                ? "Validada"
                : "Pendiente"}
          </p>
          <ul>
            {item.parameters.map((p) => (
              <li key={p.name}>
                {p.name}: {String(p.value)} {ruleUnit(p.unit)}
              </li>
            ))}
          </ul>
          {item.aliases.map((a) => (
            <p key={a.alias}>
              Alias {a.alias}: objeto {a.object_id}
            </p>
          ))}
          {item.inputs.map((p) => (
            <p key={p.alias}>
              Entrada {p.alias}: señal {p.signal_id} · revisión {p.revision_id}
            </p>
          ))}
          {item.preview ? (
            <details>
              <summary>
                Ver filas de {item.name} ({item.preview.row_count})
              </summary>
              <p>
                Hasta 100 filas de la última prueba vigente. La prueba no activa
                restricciones.
              </p>
              {item.preview.rows.map((r, index) => (
                <p key={index}>
                  {r.name} · período {r.period + 1}:{" "}
                  {r.terms
                    .map(
                      (t) =>
                        `${t.coefficient} × objeto ${t.object_id}.${t.variable}`,
                    )
                    .join(" + ")}{" "}
                  {r.relation} {-r.constant} {ruleUnit(r.unit)}
                </p>
              ))}
            </details>
          ) : (
            <p>Sin prueba vigente</p>
          )}
        </article>
      ))}
    </section>
  );
}

function InstanceForm({
  root,
  scenarioId,
  template,
  onCreated,
}: {
  root: string;
  scenarioId: number;
  template: Template;
  onCreated: (rule: RuleDraft) => void;
}) {
  const objectId = Number(root.split("/").at(-2));
  const [name, setName] = useState(template.name);
  const [values, setValues] = useState<Record<string, string | boolean>>({});
  const [aliases, setAliases] = useState<Record<string, number>>({});
  const [initials, setInitials] = useState<
    Record<string, { value?: string; timestamp?: string }>
  >({});
  const [inputs, setInputs] = useState<RuleInput[]>([]);
  const [variant, setVariant] = useState<number>();
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [requestId] = useState(() => crypto.randomUUID());
  const scope = useQuery({
    queryKey: [root, "scope", String(scenarioId)],
    queryFn: () =>
      requestJson<{ variants: { id: number; display_name: string }[] }>(
        `${root}/scope?scenario_id=${scenarioId}`,
      ),
  });
  const objects = useQuery({
    queryKey: [root, "object-candidates", scenarioId],
    queryFn: () =>
      requestJson<{ items: RuleObject[] }>(
        `${root}/object-candidates?scenario_id=${scenarioId}`,
      ),
  });
  const selected = variant ?? scope.data?.variants[0]?.id;
  const owner = (ref: string | null) =>
    ref === "self" ? objectId : ref ? aliases[ref] : null;
  const valid =
    name.trim() &&
    reason.trim() &&
    selected &&
    template.parameters.every(
      (p) => values[p.name] !== undefined && values[p.name] !== "",
    ) &&
    template.aliases.every((a) => aliases[a.alias]) &&
    (template.temporal?.initial_values ?? []).every((v) => {
      const i = initials[`${v.owner}.${v.variable}`];
      return i?.value !== undefined && i.value !== "" && i.timestamp?.trim();
    }) &&
    inputs.length === template.inputs.length &&
    template.inputs.every((p) =>
      inputs.some(
        (i) =>
          i.alias === p.alias &&
          i.object_id === owner(p.owner) &&
          i.binding_role_key === p.binding_role_key &&
          i.semantic_type_key === p.semantic_type_key,
      ),
    );
  async function create() {
    setBusy(true);
    setError("");
    try {
      const result = await requestJson<RuleDraft>(`${root}/instances`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRF-Token": await getCsrfToken(),
        },
        body: JSON.stringify({
          publication_id: template.publication_id,
          scenario_id: scenarioId,
          variant_id: selected,
          name,
          reason,
          request_id: requestId,
          parameters: template.parameters.map(({ owner: ref, ...p }) => ({
            ...p,
            object_id: owner(ref),
            value:
              p.type === "boolean" ? values[p.name] : Number(values[p.name]),
          })),
          aliases: template.aliases.map((a) => ({
            alias: a.alias,
            object_id: aliases[a.alias],
          })),
          inputs,
          windows: template.windows ?? null,
          temporal: template.temporal
            ? {
                first_period: template.temporal.first_period,
                initial_values: template.temporal.initial_values.map((v) => ({
                  object_id: owner(v.owner),
                  variable: v.variable,
                  unit: v.unit,
                  value: Number(initials[`${v.owner}.${v.variable}`]?.value),
                  timestamp: initials[`${v.owner}.${v.variable}`]?.timestamp,
                })),
              }
            : null,
        }),
      });
      onCreated(result);
    } catch (problem) {
      setError(ruleErrorMessage(problem));
    } finally {
      setBusy(false);
    }
  }
  return (
    <fieldset disabled={busy}>
      <legend>Nueva instancia · revisión {template.revision}</legend>
      <label>
        Nombre de la instancia
        <input value={name} onChange={(e) => setName(e.target.value)} />
      </label>
      <label>
        Variante de la instancia
        <select
          value={selected ?? ""}
          onChange={(e) => setVariant(Number(e.target.value))}
        >
          {scope.data?.variants.map((v) => (
            <option key={v.id} value={v.id}>
              {v.display_name}
            </option>
          ))}
        </select>
      </label>
      {template.aliases.map((a) => (
        <label key={a.alias}>
          Referencia {a.alias}
          <select
            value={aliases[a.alias] ?? ""}
            onChange={(e) =>
              setAliases({ ...aliases, [a.alias]: Number(e.target.value) })
            }
          >
            <option value="">Selecciona un objeto compatible</option>
            {objects.data?.items
              .filter((o) => (a.compatible_types ?? [a.kind]).includes(o.kind))
              .map((o) => (
                <option key={o.id} value={o.id}>
                  {o.display_name} · {o.key}
                </option>
              ))}
          </select>
        </label>
      ))}
      {template.parameters.map((p) => (
        <label key={p.name}>
          Valor local {p.name}
          <span>
            {ruleUnit(p.unit)} · {p.type}
          </span>
          {p.type === "boolean" ? (
            <select
              aria-label={`Valor local ${p.name}`}
              value={values[p.name] === undefined ? "" : String(values[p.name])}
              onChange={(e) =>
                setValues({ ...values, [p.name]: e.target.value === "true" })
              }
            >
              <option value="">Selecciona un valor</option>
              <option value="true">Sí</option>
              <option value="false">No</option>
            </select>
          ) : (
            <input
              aria-label={`Valor local ${p.name}`}
              type="number"
              min={p.min ?? undefined}
              max={p.max ?? undefined}
              step={p.type === "integer" ? 1 : "any"}
              value={String(values[p.name] ?? "")}
              onChange={(e) =>
                setValues({ ...values, [p.name]: e.target.value })
              }
            />
          )}
        </label>
      ))}
      {template.inputs.length > 0 && (
        <>
          <p>
            Entradas obligatorias:{" "}
            {template.inputs
              .map((p) => `${p.alias} (${p.semantic_type_key}, ${p.owner})`)
              .join(", ")}
            . Selecciona cada revisión para el destino.
          </p>
          <RuleInputs
            root={root}
            scenarioId={scenarioId}
            inputs={inputs}
            onChange={setInputs}
            requiredPorts={template.inputs.map(({ owner: ref, ...p }) => ({
              ...p,
              object_id: owner(ref) ?? 0,
            }))}
            objects={[
              { id: objectId, label: "Objeto actual" },
              ...Object.entries(aliases).map(([label, id]) => ({ id, label })),
            ]}
          />
        </>
      )}
      {template.temporal && (
        <p>
          Primera transición:{" "}
          {template.temporal.first_period === "omit"
            ? "omitida"
            : "con condición inicial explícita"}
          .
        </p>
      )}
      {template.temporal?.initial_values.map((v) => {
        const key = `${v.owner}.${v.variable}`;
        return (
          <div key={key}>
            <label>
              Valor inicial {key}
              <input
                type="number"
                value={initials[key]?.value ?? ""}
                onChange={(e) =>
                  setInitials({
                    ...initials,
                    [key]: { ...initials[key], value: e.target.value },
                  })
                }
              />
            </label>
            <span>{ruleUnit(v.unit)}</span>
            <label>
              Instante inicial {key}
              <input
                placeholder="2026-01-01T00:00:00Z"
                value={initials[key]?.timestamp ?? ""}
                onChange={(e) =>
                  setInitials({
                    ...initials,
                    [key]: { ...initials[key], timestamp: e.target.value },
                  })
                }
              />
            </label>
          </div>
        );
      })}
      {template.windows && (
        <p>
          Ventana:{" "}
          {template.windows.kind === "horizon"
            ? "horizonte completo"
            : "día civil"}{" "}
          · {template.windows.timezone} · parciales{" "}
          {template.windows.partial === "allow" ? "permitidas" : "rechazadas"}.
        </p>
      )}
      <label>
        Motivo de reutilización
        <input value={reason} onChange={(e) => setReason(e.target.value)} />
      </label>
      <p>La instancia se guardará pendiente de prueba y aplicación.</p>
      <button
        type="button"
        disabled={!valid || busy}
        onClick={() => void create()}
      >
        Crear instancia
      </button>
      {(error || scope.isError || objects.isError) && (
        <p role="alert">
          {error || ruleErrorMessage(scope.error ?? objects.error)}
        </p>
      )}
    </fieldset>
  );
}
