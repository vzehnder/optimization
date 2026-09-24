import { useQuery } from "@tanstack/react-query";
import { autocompletion, completeFromList } from "@codemirror/autocomplete";
import { defaultKeymap, history, historyKeymap } from "@codemirror/commands";
import { python } from "@codemirror/lang-python";
import { Compartment, EditorState } from "@codemirror/state";
import { EditorView, keymap, lineNumbers } from "@codemirror/view";
import { useEffect, useRef, useState } from "react";
import {
  Link,
  Navigate,
  useLocation,
  useParams,
  useSearchParams,
} from "react-router-dom";
import { getCsrfToken, requestJson } from "./api/client";
import { safeReturnPath } from "./journeyRoutes";
import { RuleApplications } from "./RuleApplications";
import { RuleInputs, type RuleInput } from "./RuleInputs";
import { ruleErrorMessage } from "./ruleErrors";
import { RuleObjects, type RuleAlias, type RuleObject } from "./RuleObjects";
import { RuleTemporal, type TemporalPolicy } from "./RuleTemporal";
import { RuleWindows, type WindowPolicy } from "./RuleWindows";
import { RuleLibrary } from "./RuleLibrary";
import { definitionLabel, validationLabel } from "./ruleStatus";

export interface RuleParameter {
  name: string;
  type: "number" | "integer" | "boolean";
  unit: string;
  value: number | boolean;
  min: number | null;
  max: number | null;
  object_id?: number | null;
}
export interface RuleDraft {
  id: string;
  name: string;
  code: string;
  revision: number;
  parameters: RuleParameter[];
  inputs?: RuleInput[];
  aliases?: RuleAlias[];
  scenario_id?: number | null;
  temporal?: TemporalPolicy | null;
  windows?: WindowPolicy | null;
  template?: { rule_id: string; publication_id: string };
  variant_id?: number;
  status?: string;
}
interface RuleList {
  enabled?: boolean;
  object: { display_name: string };
  items: {
    id: string;
    name: string;
    revision: number;
    status?: string;
    applications?: {
      id: string;
      status: string;
      variant_id: number;
      validation_status: string;
      validation_causes?: { message: string }[];
    }[];
  }[];
  runtime: { image: string; sdk: string } | null;
}
const DEFAULT_CODE =
  "def construir(ctx):\n    return ctx.parametros.capacidad * ctx.parametros.disponibilidad\n";
const DEFAULT_PARAMETERS: RuleParameter[] = [
  {
    name: "capacidad",
    type: "number",
    unit: "m3_per_s",
    value: 80,
    min: 0,
    max: null,
  },
  {
    name: "disponibilidad",
    type: "number",
    unit: "dimensionless",
    value: 0.75,
    min: 0,
    max: 1,
  },
];

async function mutate<T>(path: string, body: unknown, method = "POST") {
  return requestJson<T>(path, {
    method,
    headers: {
      "Content-Type": "application/json",
      "X-CSRF-Token": await getCsrfToken(),
    },
    body: JSON.stringify(body),
  });
}

function sameRows<T extends object>(left: T[], right: T[]) {
  return (
    left.length === right.length &&
    left.every((row, index) =>
      (Object.keys(row) as (keyof T)[]).every(
        (key) => row[key] === right[index][key],
      ),
    )
  );
}

function PythonEditor({
  initialCode,
  onChange,
  completions,
}: {
  initialCode: string;
  onChange: (code: string) => void;
  completions: string[];
}) {
  const element = useRef<HTMLDivElement>(null);
  const editor = useRef<EditorView | null>(null);
  const [completionConfig] = useState(() => new Compartment());
  useEffect(() => {
    const view = new EditorView({
      parent: element.current!,
      state: EditorState.create({
        doc: initialCode,
        extensions: [
          python(),
          lineNumbers(),
          history(),
          keymap.of([...defaultKeymap, ...historyKeymap]),
          completionConfig.of(
            autocompletion({
              override: [
                completeFromList([
                  { label: "ctx.parametros", type: "property" },
                  { label: "ctx.objeto", type: "property" },
                  { label: "ctx.periodos", type: "property" },
                  { label: "ctx.restriccion", type: "function" },
                  { label: "ctx.entradas", type: "property" },
                  { label: "ctx.salida", type: "function" },
                  { label: "construir", type: "function" },
                  { label: "range", type: "function" },
                ]),
              ],
            }),
          ),
          EditorView.contentAttributes.of({
            "aria-label": "Código Python",
            role: "textbox",
            "aria-multiline": "true",
          }),
          EditorView.updateListener.of((update) => {
            if (update.docChanged) onChange(update.state.doc.toString());
          }),
          EditorView.lineWrapping,
        ],
      }),
    });
    editor.current = view;
    return () => view.destroy();
  }, [initialCode, onChange, completionConfig]);
  useEffect(() => {
    editor.current?.dispatch({
      effects: completionConfig.reconfigure(
        autocompletion({
          override: [
            completeFromList([
              ...completions.map((label) => ({ label, type: "property" })),
              ...[
                "ctx.periodos",
                "ctx.parametros",
                "ctx.entradas",
                "ctx.objetos",
                "ctx.restriccion",
                "ctx.salida",
                "ctx.transiciones",
                "ctx.ventanas",
                "construir",
                "range",
                "sum",
              ].map((label) => ({ label, type: "variable" })),
            ]),
          ],
        }),
      ),
    });
  }, [completions, completionConfig]);
  return <div className="rule-code-editor" ref={element} />;
}

export function ComponentRulesView() {
  const location = useLocation();
  return <RulesContent key={location.pathname} />;
}

export function HydraulicRulesEntryView() {
  const { scenarioId, plantKey, unitKey } = useParams();
  const endpoint = `/api/scenarios/${scenarioId}/hydraulic-plants/${encodeURIComponent(plantKey ?? "")}/units/${encodeURIComponent(unitKey ?? "")}/rule-context`;
  const context = useQuery({
    queryKey: [endpoint],
    queryFn: () =>
      requestJson<{ project_id: number; object_id: number }>(endpoint),
    retry: false,
  });
  const returnTo = `/scenarios/${scenarioId}/hydraulic-diagram`;
  if (context.data)
    return (
      <Navigate
        replace
        to={`/projects/${context.data.project_id}/linkable-objects/${context.data.object_id}/rules?${new URLSearchParams({ return_to: returnTo, scenario_id: scenarioId! })}`}
      />
    );
  return (
    <section className="content-panel rules-surface">
      <h1>Cálculos y restricciones</h1>
      <p role={context.isError ? "alert" : "status"}>
        {context.isError ? String(context.error) : "Abriendo la unidad…"}
      </p>
      <Link to={returnTo}>Volver a la unidad</Link>
    </section>
  );
}

function RulesContent() {
  const { projectId, linkableObjectId } = useParams();
  const [search, setSearch] = useSearchParams();
  const [libraryOpen, setLibraryOpen] = useState(false);
  const root = `/api/projects/${projectId}/linkable-objects/${linkableObjectId}/rules`;
  const list = useQuery({
    queryKey: [root],
    queryFn: () => requestJson<RuleList>(root),
    retry: false,
  });
  const selected = search.get("rule") ?? list.data?.items[0]?.id;
  const draft = useQuery({
    queryKey: [root, selected],
    queryFn: () => requestJson<RuleDraft>(`${root}/${selected}`),
    enabled: !!selected,
    retry: false,
  });
  const returnTo = safeReturnPath(search.get("return_to"));
  return (
    <section className="content-panel rules-surface">
      <h1>Cálculos y restricciones</h1>
      <p>
        Las pruebas no modifican corridas ni series. Para incorporar
        restricciones, publica, prueba y aplica una revisión a la variante.
      </p>
      {returnTo && <Link to={returnTo}>Volver a la unidad</Link>}
      {list.data && (
        <p>
          Unidad: {list.data.object.display_name} · Proyecto {projectId}
        </p>
      )}
      {list.isError || draft.isError ? (
        <p role="alert">{String(list.error ?? draft.error)}</p>
      ) : null}
      {list.data && !list.data.runtime && (
        <p role="status">
          {list.data.enabled === false
            ? "Pruebas deshabilitadas en este proyecto."
            : "Ejecutor aislado no disponible."}{" "}
          Puedes guardar el borrador.
        </p>
      )}
      {list.data && (
        <RuleLibrary
          root={root}
          scenarioId={Number(search.get("scenario_id")) || null}
          onOpenChange={setLibraryOpen}
          onCreated={(saved) => {
            const next = new URLSearchParams(search);
            next.set("rule", saved.id);
            next.delete("constraint_test");
            next.delete("test");
            setSearch(next);
            void list.refetch();
          }}
        />
      )}
      {list.data && (
        <nav aria-label="Reglas del objeto">
          {list.data.items.map((item) => (
            <div key={item.id}>
              <button
                key={item.id}
                type="button"
                onClick={() => {
                  const next = new URLSearchParams(search);
                  next.set("rule", item.id);
                  setSearch(next);
                }}
              >
                {item.name}
              </button>
              {item.status && <span> · {definitionLabel(item.status)}</span>}
              {item.applications
                ?.filter((a) => a.status === "active")
                .map((a) => (
                  <p key={a.id}>
                    Variante {a.variant_id} ·{" "}
                    {validationLabel(a.validation_status)}
                    {a.validation_causes
                      ?.map((c) => ` · ${c.message}`)
                      .join("")}
                  </p>
                ))}
            </div>
          ))}
        </nav>
      )}
      {list.data && !libraryOpen && (!selected || draft.data) && (
        <RuleForm
          key={selected ?? "new"}
          root={root}
          initial={draft.data}
          available={!!list.data.runtime}
          onSaved={(saved) => {
            const next = new URLSearchParams(search);
            next.set("rule", saved.id);
            setSearch(next, { replace: true });
            void list.refetch();
          }}
        />
      )}
    </section>
  );
}

function RuleForm({
  root,
  initial,
  available,
  onSaved,
}: {
  root: string;
  initial?: RuleDraft;
  available: boolean;
  onSaved: (rule: RuleDraft) => void;
}) {
  const [name, setName] = useState(
    initial?.name ?? "Capacidad por disponibilidad",
  );
  const [code, setCode] = useState(initial?.code ?? DEFAULT_CODE);
  const [parameters, setParameters] = useState(
    initial?.parameters ?? DEFAULT_PARAMETERS,
  );
  const [saved, setSaved] = useState(initial);
  const [inputs, setInputs] = useState(initial?.inputs ?? []);
  const [aliases, setAliases] = useState(initial?.aliases ?? []);
  const [temporal, setTemporal] = useState(initial?.temporal ?? null);
  const [windows, setWindows] = useState(initial?.windows ?? null);
  const [search] = useSearchParams();
  const scenarioId =
    initial?.scenario_id ?? (Number(search.get("scenario_id")) || null);
  const objectId = Number(root.split("/").at(-2));
  const candidates = useQuery({
    queryKey: [root, "object-candidates", scenarioId],
    queryFn: () =>
      requestJson<{ items: RuleObject[] }>(
        `${root}/object-candidates?scenario_id=${scenarioId}`,
      ),
    enabled: !!scenarioId,
    retry: false,
  });
  const objects = candidates.data?.items ?? [];
  const references = [{ alias: "", object_id: objectId }, ...aliases];
  const completions = references.flatMap((ref) =>
    Object.keys(
      objects.find((o) => o.id === ref.object_id)?.variables ?? {},
    ).map(
      (variable) =>
        `ctx.${ref.alias ? `objetos.${ref.alias}` : "objeto"}.${variable}`,
    ),
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const dirty =
    !saved ||
    code !== saved.code ||
    name !== saved.name ||
    !sameRows(aliases, saved.aliases ?? []) ||
    !sameRows(inputs, saved.inputs ?? []) ||
    JSON.stringify(temporal) !== JSON.stringify(saved.temporal ?? null) ||
    windows?.kind !== saved.windows?.kind ||
    windows?.timezone !== saved.windows?.timezone ||
    windows?.partial !== saved.windows?.partial ||
    !sameRows(parameters, saved.parameters);
  function parameterChange(index: number, patch: Partial<RuleParameter>) {
    setParameters((rows) =>
      rows.map((row, i) => (i === index ? { ...row, ...patch } : row)),
    );
  }
  async function save() {
    setBusy(true);
    setError("");
    try {
      if (
        temporal?.first_period === "initial" &&
        (!temporal.initial_values.length ||
          temporal.initial_values.some(
            (v) => v.value === null || !v.timestamp.trim(),
          ))
      ) {
        throw new Error(
          "Completa el valor y el instante de cada condición inicial.",
        );
      }
      const result = await mutate<RuleDraft>(
        saved ? `${root}/${saved.id}` : root,
        {
          name,
          code,
          parameters,
          inputs,
          aliases,
          temporal,
          windows,
          scenario_id: scenarioId,
          expected_revision: saved?.revision ?? 0,
        },
        saved ? "PUT" : "POST",
      );
      setSaved(result);
      onSaved(result);
    } catch (error) {
      setError(ruleErrorMessage(error));
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="rule-form">
      <label>
        Nombre de la regla
        <input
          value={name}
          maxLength={200}
          onChange={(event) => setName(event.target.value)}
        />
      </label>
      <p>
        Define <code>construir(ctx)</code>. Para un cálculo numérico, devuelve
        una cantidad en m³/s. Para relacionar variables, recorre{" "}
        <code>ctx.periodos</code>y emite filas con <code>ctx.restriccion</code>.
      </p>
      <details>
        <summary>Ejemplo de máximo de caudal</summary>
        <pre>
          {
            'def construir(ctx):\n    for t in ctx.periodos:\n        ctx.restriccion("maximo", t, ctx.objeto.caudal[t] <= ctx.parametros.capacidad * ctx.parametros.disponibilidad)'
          }
        </pre>
      </details>
      <details>
        <summary>Ejemplo de límites horarios con series</summary>
        <p>
          Selecciona entradas con alias afluente y disponibilidad; agrega un
          parámetro adimensional fraccion.
        </p>
        <pre>
          {
            'def construir(ctx):\n    for t in ctx.periodos:\n        minimo = ctx.entradas.afluente[t] * ctx.parametros.fraccion\n        maximo = ctx.parametros.capacidad * ctx.entradas.disponibilidad[t]\n        ctx.restriccion("minimo", t, ctx.objeto.caudal[t] >= minimo)\n        ctx.restriccion("maximo", t, ctx.objeto.caudal[t] <= maximo)\n        ctx.salida("limite_calculado", t, maximo)'
          }
        </pre>
      </details>
      {saved?.template ? (
        <>
          <p>Revisión compartida fijada: {saved.template.publication_id}</p>
          <pre>{code}</pre>
        </>
      ) : (
        <PythonEditor
          initialCode={initial?.code ?? DEFAULT_CODE}
          onChange={setCode}
          completions={completions}
        />
      )}
      {scenarioId && (
        <RuleObjects
          objects={objects}
          objectId={objectId}
          aliases={aliases}
          onChange={setAliases}
        />
      )}
      {candidates.isError && (
        <p role="alert">{ruleErrorMessage(candidates.error)}</p>
      )}
      <RuleTemporal
        policy={temporal}
        onChange={setTemporal}
        objects={objects.filter((o) =>
          references.some((ref) => ref.object_id === o.id),
        )}
      />
      <RuleWindows policy={windows} onChange={setWindows} />
      <details>
        <summary>Ejemplo de potencia conjunta</summary>
        <p>
          Selecciona la planta con alias central y define un parámetro limite de
          10 MW.
        </p>
        <pre>
          {
            'def construir(ctx):\n    for t in ctx.periodos:\n        ctx.restriccion("conjunto", t, ctx.objetos.central.potencia[t] <= ctx.parametros.limite)'
          }
        </pre>
      </details>
      <fieldset>
        <legend>Parámetros tipados</legend>
        {parameters.map((p, index) => (
          <div className="rule-parameter" key={index}>
            <label>
              Parámetro {index + 1}
              <input
                value={p.name}
                disabled={!!saved?.template}
                onChange={(e) =>
                  parameterChange(index, { name: e.target.value })
                }
              />
            </label>
            <label>
              Tipo {p.name}
              <select
                value={p.type}
                disabled={!!saved?.template}
                onChange={(e) =>
                  parameterChange(index, {
                    type: e.target.value as RuleParameter["type"],
                    value: e.target.value === "boolean" ? false : 0,
                    unit:
                      e.target.value === "boolean" ? "dimensionless" : p.unit,
                  })
                }
              >
                <option value="number">Número</option>
                <option value="integer">Entero</option>
                <option value="boolean">Booleano</option>
              </select>
            </label>
            <label>
              Unidad {p.name}
              <input
                value={p.unit}
                disabled={!!saved?.template}
                onChange={(e) =>
                  parameterChange(index, { unit: e.target.value })
                }
              />
            </label>
            {scenarioId && (
              <label>
                Objeto del parámetro {p.name}
                <select
                  value={p.object_id ?? ""}
                  onChange={(e) =>
                    parameterChange(index, {
                      object_id: Number(e.target.value) || null,
                    })
                  }
                >
                  <option value="">Parámetro de la regla</option>
                  {references.map((ref) => (
                    <option key={ref.alias} value={ref.object_id}>
                      {ref.alias || "Objeto actual"} ·{" "}
                      {objects.find((o) => o.id === ref.object_id)
                        ?.display_name ?? ref.object_id}
                    </option>
                  ))}
                </select>
              </label>
            )}
            <label>
              Valor {p.name}
              {p.type === "boolean" ? (
                <input
                  type="checkbox"
                  checked={Boolean(p.value)}
                  onChange={(e) =>
                    parameterChange(index, { value: e.target.checked })
                  }
                />
              ) : (
                <input
                  type="number"
                  value={Number(p.value)}
                  onChange={(e) =>
                    parameterChange(index, { value: Number(e.target.value) })
                  }
                />
              )}
            </label>
            <label>
              Mínimo {p.name}
              <input
                type="number"
                value={p.min ?? ""}
                disabled={!!saved?.template}
                onChange={(e) =>
                  parameterChange(index, {
                    min: e.target.value === "" ? null : Number(e.target.value),
                  })
                }
              />
            </label>
            <label>
              Máximo {p.name}
              <input
                type="number"
                value={p.max ?? ""}
                disabled={!!saved?.template}
                onChange={(e) =>
                  parameterChange(index, {
                    max: e.target.value === "" ? null : Number(e.target.value),
                  })
                }
              />
            </label>
            <button
              type="button"
              disabled={!!saved?.template}
              onClick={() =>
                setParameters(parameters.filter((_, i) => i !== index))
              }
            >
              Quitar parámetro {index + 1}
            </button>
          </div>
        ))}
        <button
          type="button"
          disabled={!!saved?.template || parameters.length >= 50}
          onClick={() =>
            setParameters([
              ...parameters,
              {
                name: `parametro${parameters.length + 1}`,
                type: "number",
                value: 1,
                unit: "dimensionless",
                min: null,
                max: null,
              },
            ])
          }
        >
          Agregar parámetro
        </button>
      </fieldset>
      <RuleInputs
        root={root}
        inputs={inputs}
        onChange={setInputs}
        scenarioId={scenarioId}
        objects={references.map((ref) => ({
          id: ref.object_id,
          label: ref.alias || "Objeto actual",
        }))}
      />
      <button type="button" disabled={busy} onClick={() => void save()}>
        Guardar borrador
      </button>
      {saved && (
        <p role="status">
          Borrador guardado · revisión {saved.revision}
          {dirty ? " · cambios sin guardar" : ""}
        </p>
      )}
      <RulePreview
        root={root}
        saved={saved}
        disabled={dirty || busy || !available || inputs.length > 0}
      />
      {saved && (
        <RuleApplications
          root={root}
          ruleId={saved.id}
          revision={saved.revision}
          disabled={dirty || busy}
          available={available}
          template={saved.template}
          instanceVariant={saved.variant_id}
          onRecovered={async () => {
            const fresh = await requestJson<RuleDraft>(`${root}/${saved.id}`);
            setSaved(fresh);
            setName(fresh.name);
            setCode(fresh.code);
            setParameters(fresh.parameters);
            setAliases(fresh.aliases ?? []);
            setInputs(fresh.inputs ?? []);
            setTemporal(fresh.temporal ?? null);
            setWindows(fresh.windows ?? null);
            onSaved(fresh);
          }}
        />
      )}
      {error && <p role="alert">{error}</p>}
    </div>
  );
}

interface RuleJob {
  id: string;
  status: "queued" | "running" | "succeeded" | "failed" | "cancelled";
  draft_revision: number;
  code_hash: string;
  context_hash: string;
  diagnostic?: { category: string; action: string };
  result: {
    output?: { value: number; unit: string };
    error?: { code: string; message: string; line?: number };
    runtime?: { image: string; sdk: string; python: string };
    logs?: string;
  } | null;
}
const STATUS = {
  queued: "En cola",
  running: "Ejecutando",
  succeeded: "Terminada",
  failed: "Fallida",
  cancelled: "Cancelada",
};

function RulePreview({
  root,
  saved,
  disabled,
}: {
  root: string;
  saved?: RuleDraft;
  disabled: boolean;
}) {
  const [search, setSearch] = useSearchParams();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const jobId = search.get("test");
  const path = `${root}/${saved?.id}/tests`;
  const job = useQuery({
    queryKey: [path, jobId],
    queryFn: () => requestJson<RuleJob>(`${path}/${jobId}`),
    enabled: !!jobId && !!saved,
    retry: false,
    refetchInterval: (query) =>
      ["queued", "running"].includes(query.state.data?.status ?? "")
        ? 350
        : false,
  });
  const running = job.data && ["queued", "running"].includes(job.data.status);
  async function start() {
    setBusy(true);
    setError("");
    try {
      const started = await mutate<RuleJob>(path, {
        expected_revision: saved?.revision,
      });
      const next = new URLSearchParams(search);
      next.set("test", started.id);
      setSearch(next, { replace: true });
    } catch (error) {
      setError(
        error instanceof Error ? error.message : "No se pudo iniciar la prueba",
      );
    } finally {
      setBusy(false);
    }
  }
  async function cancel() {
    setBusy(true);
    setError("");
    try {
      await mutate(`${path}/${jobId}/cancel`, {});
      await job.refetch();
    } catch (error) {
      setError(error instanceof Error ? error.message : "No se pudo cancelar");
    } finally {
      setBusy(false);
    }
  }
  return (
    <section aria-label="Prueba de la regla">
      <button
        type="button"
        disabled={disabled || busy || !!running}
        onClick={() => void start()}
      >
        Probar borrador
      </button>
      {running && (
        <button type="button" disabled={busy} onClick={() => void cancel()}>
          Cancelar prueba
        </button>
      )}
      {(error || job.isError) && (
        <p role="alert">{error || String(job.error)}</p>
      )}
      {job.data && (
        <>
          <p role="status">{STATUS[job.data.status]}</p>
          {job.data.draft_revision !== saved?.revision && (
            <p>
              Resultado de una revisión anterior. Vuelve a probar el borrador.
            </p>
          )}
          {job.data.result?.output && (
            <p>
              Máximo calculado:{" "}
              <strong>{job.data.result.output.value} m³/s</strong>
            </p>
          )}
          {job.data.result?.error && (
            <p role="alert">
              {job.data.result.error.code}
              {job.data.result.error.line
                ? ` · línea ${job.data.result.error.line}`
                : ""}
              : {job.data.result.error.message}
            </p>
          )}
          {job.data.diagnostic && <p>{job.data.diagnostic.action}</p>}
          <details>
            <summary>Identidad de la prueba</summary>
            <p>Revisión {job.data.draft_revision}</p>
            <p>
              Código: <code>{job.data.code_hash}</code>
            </p>
            <p>
              Contexto: <code>{job.data.context_hash}</code>
            </p>
            <p>
              SDK {job.data.result?.runtime?.sdk} · Python{" "}
              {job.data.result?.runtime?.python}
            </p>
            <p>
              <code>{job.data.result?.runtime?.image}</code>
            </p>
          </details>
          {job.data.result?.logs && (
            <details>
              <summary>Logs de la prueba</summary>
              <pre>{job.data.result.logs}</pre>
            </details>
          )}
        </>
      )}
    </section>
  );
}
