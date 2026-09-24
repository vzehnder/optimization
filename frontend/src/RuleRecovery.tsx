import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { getCsrfToken, requestJson } from "./api/client";
import { ruleErrorMessage } from "./ruleErrors";
import { ruleUnit } from "./ruleUnits";
import type { RuleParameter } from "./ComponentRules";
import { RuleInputs, type RuleInput } from "./RuleInputs";
import type { RuleAlias, RuleObject } from "./RuleObjects";
import type { TemporalPolicy } from "./RuleTemporal";
import type { WindowPolicy } from "./RuleWindows";
import { definitionLabel, validationLabel } from "./ruleStatus";
import type { Template } from "./RuleLibrary";

interface Scope {
  scenario_id: number;
  variant_id: number;
  range_start: string;
  range_end: string;
}
interface Mappings {
  parameters: RuleParameter[];
  aliases: RuleAlias[];
  inputs: RuleInput[];
  temporal: TemporalPolicy | null;
  windows: WindowPolicy | null;
}
interface HistoricalApplication extends Mappings {
  id: string;
  revision: number;
  status: string;
  publication_id: string;
  variant_id: number;
  code_hash: string;
  context_hash: string;
  ir_hash: string;
  validation_status: string;
  validation_causes?: { code: string; message: string; alias?: string }[];
  events: { action: string; actor: number; reason?: string; at: string }[];
}
interface Publication extends Mappings {
  id: string;
  draft_revision: number;
  code: string;
  contract?: Template | null;
}
interface ComparisonView extends Mappings {
  inputs: (RuleInput & {
    unit_key?: string;
    timezone?: string;
    current_revision_id?: number;
  })[];
  publication_id: string;
  code: string;
  sdk: string;
  scope: Scope;
  objects: RuleObject[];
  grid: { timestamp: string; duration_hours: number }[];
  timezone: string;
  runtime?: { image?: string };
}
interface Comparison {
  before: ComparisonView;
  after: ComparisonView;
  changed_fields: string[];
  action: string;
}
interface RecoveryJob {
  id: string;
  status: string;
  result?: {
    ir?: {
      rows: {
        name: string;
        period: number;
        relation: string;
        constant: number;
        unit: string;
        terms?: {
          object_id: number;
          variable: string;
          period: number;
          coefficient: number;
          unit?: string;
        }[];
      }[];
    };
    error?: { message: string; line?: number; alias?: string; period?: number };
  };
}
async function post<T>(path: string, body: unknown) {
  return requestJson<T>(path, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRF-Token": await getCsrfToken(),
    },
    body: JSON.stringify(body),
  });
}

export function RuleRecovery({
  root,
  ruleId,
  revision,
  scope,
  disabled,
  available,
  onResolved,
}: {
  root: string;
  ruleId: string;
  revision: number;
  scope: Scope;
  disabled: boolean;
  available: boolean;
  onResolved: () => void | Promise<void>;
}) {
  const path = `${root}/${ruleId}`;
  const [open, setOpen] = useState(false);
  const [sourceId, setSourceId] = useState<string>();
  const [publicationId, setPublicationId] = useState<string>();
  const [mappings, setMappings] = useState<Mappings>();
  const [comparison, setComparison] = useState<Comparison>();
  const [jobId, setJobId] = useState<string>();
  const [reason, setReason] = useState("");
  const [archiveReason, setArchiveReason] = useState("");
  const [acceptEmpty, setAcceptEmpty] = useState(false);
  const [requestId, setRequestId] = useState(() => crypto.randomUUID());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);
  const [comparedRequest, setComparedRequest] = useState("");
  const history = useQuery({
    queryKey: [path, "history", revision],
    queryFn: () =>
      requestJson<{
        status: string;
        publications: Publication[];
        applications: HistoricalApplication[];
        consumers?: {
          application_id: string;
          name: string;
          project_id: number;
          object_id: number;
          rule_id: string;
          scenario_id: number;
          variant_id: number;
        }[];
      }>(`${path}/history`),
    enabled: open,
    retry: false,
  });
  const applications =
    history.data?.applications.filter(
      (a) => a.variant_id === scope.variant_id,
    ) ?? [];
  const source =
    applications.find((a) => a.id === sourceId) ??
    applications.find((a) => a.status === "active") ??
    applications[0];
  const target = publicationId ?? source?.publication_id;
  const publication = history.data?.publications.find((p) => p.id === target);
  const objectId = Number(root.split("/").at(-2));
  const objects = useQuery({
    queryKey: [root, "object-candidates", scope.scenario_id],
    queryFn: () =>
      requestJson<{ items: RuleObject[] }>(
        `${root}/object-candidates?scenario_id=${scope.scenario_id}`,
      ),
    enabled: open,
    retry: false,
  });
  const proposal =
    mappings ??
    (source && publication
      ? proposedMappings(source, publication, objectId)
      : undefined);
  const owner = (ref: string | null) =>
    ref === "self"
      ? objectId
      : ref
        ? (proposal?.aliases.find((a) => a.alias === ref)?.object_id ?? 0)
        : null;
  const requiredPorts = publication?.contract?.inputs.map((p) => ({
    alias: p.alias,
    dimension_key: p.dimension_key,
    semantic_type_key: p.semantic_type_key,
    binding_role_key: p.binding_role_key,
    object_id: owner(p.owner) ?? objectId,
  }));
  const mappingsComplete =
    proposal?.aliases.every((a) => a.object_id > 0) &&
    (!requiredPorts ||
      requiredPorts.every((p) =>
        proposal.inputs.some(
          (i) =>
            i.alias === p.alias &&
            i.object_id === p.object_id &&
            i.semantic_type_key === p.semantic_type_key,
        ),
      ));
  const body = {
    expected_revision: revision,
    source_application_id: source?.id,
    expected_application_revision: source?.revision,
    publication_id: target,
    scope,
    mappings: proposal,
  };
  const currentRequest = JSON.stringify(body);
  const matches = currentRequest === comparedRequest;
  const job = useQuery({
    queryKey: [path, "recovery-test", jobId],
    queryFn: () => requestJson<RecoveryJob>(`${path}/tests/${jobId}`),
    enabled: !!jobId,
    retry: false,
    refetchInterval: (q) =>
      ["queued", "running"].includes(q.state.data?.status ?? "") ? 350 : false,
  });
  const running = ["queued", "running"].includes(job.data?.status ?? "");
  const rows = job.data?.result?.ir?.rows;
  const ready =
    job.data?.status === "succeeded" && matches && !disabled && available;
  async function act(action: () => Promise<void>) {
    setBusy(true);
    setError("");
    setSuccess(false);
    try {
      await action();
    } catch (problem) {
      setError(ruleErrorMessage(problem));
    } finally {
      setBusy(false);
    }
  }
  function reset() {
    setComparison(undefined);
    setJobId(undefined);
    setComparedRequest("");
    setSuccess(false);
    setRequestId(crypto.randomUUID());
  }
  return (
    <section aria-label="Revisiones e historial" className="rule-recovery">
      <button type="button" onClick={() => setOpen(!open)} aria-expanded={open}>
        Comparar y recuperar revisiones
      </button>
      {open && (
        <>
          <h3>Revisiones e historial</h3>
          {!!history.data?.consumers?.length && (
            <div>
              <h4>Consumidores vigentes</h4>
              <ul>
                {history.data.consumers.map((c) => (
                  <li key={c.application_id}>
                    <a
                      href={`/react/projects/${c.project_id}/linkable-objects/${c.object_id}/rules?rule=${c.rule_id}&scenario_id=${c.scenario_id}&variant_id=${c.variant_id}`}
                    >
                      Resolver {c.name} · variante {c.variant_id}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {history.data && (
            <p>Definición: {definitionLabel(history.data.status)}</p>
          )}
          {history.data?.status === "archived" && (
            <p>
              La definición está archivada. Puedes revalidar una aplicación
              existente con motivo o desactivarla.
            </p>
          )}
          {history.data && history.data.status !== "archived" && (
            <details open>
              <summary>Archivar definición</summary>
              <p>
                Archivar impide aplicaciones nuevas y exige resolver
                explícitamente los consumidores vigentes. Las revisiones y
                corridas se conservan.
              </p>
              <label>
                Motivo de archivo
                <input
                  value={archiveReason}
                  maxLength={1000}
                  onChange={(e) => setArchiveReason(e.target.value)}
                />
              </label>
              <button
                type="button"
                disabled={disabled || busy || !archiveReason.trim()}
                onClick={() =>
                  void act(async () => {
                    await post(`${path}/archive`, {
                      expected_revision: revision,
                      reason: archiveReason,
                    });
                    reset();
                    await history.refetch();
                    await onResolved();
                  })
                }
              >
                Archivar definición
              </button>
            </details>
          )}
          {applications.length === 0 && !history.isPending && (
            <p>No hay aplicaciones históricas en esta variante.</p>
          )}
          {applications.map((a) => (
            <details key={a.id}>
              <summary>
                {a.status === "active"
                  ? "Aplicación activa"
                  : "Aplicación histórica"}{" "}
                · {validationLabel(a.validation_status)} · {a.id.slice(0, 8)}
              </summary>
              <p>
                Revisión fijada: <code>{a.publication_id}</code>
              </p>
              {a.validation_causes?.map((c, i) => (
                <p key={i}>
                  {c.alias ? `${c.alias}: ` : ""}
                  {c.message}
                </p>
              ))}
              <ul>
                {a.events.map((e, i) => (
                  <li key={i}>
                    {e.at} · {e.action} · Actor {e.actor}
                    {e.reason ? ` · ${e.reason}` : ""}
                  </li>
                ))}
              </ul>
              <p>
                Hash de código: <code>{a.code_hash}</code>
              </p>
              <p>
                Hash de contexto: <code>{a.context_hash}</code>
              </p>
              <p>
                Hash de restricciones: <code>{a.ir_hash}</code>
              </p>
            </details>
          ))}
          {source && (
            <>
              <label>
                Aplicación de origen
                <select
                  value={source.id}
                  onChange={(e) => {
                    reset();
                    setMappings(undefined);
                    setSourceId(e.target.value);
                    setPublicationId(undefined);
                  }}
                >
                  {applications.map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.status === "active" ? "Activa" : "Histórica"} ·{" "}
                      {a.id.slice(0, 8)} · {a.publication_id.slice(0, 8)}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Revisión a utilizar
                <select
                  value={target}
                  onChange={(e) => {
                    reset();
                    setMappings(undefined);
                    setPublicationId(e.target.value);
                  }}
                >
                  {history.data?.publications.map((p) => (
                    <option key={p.id} value={p.id}>
                      Revisión {p.draft_revision} · {p.id.slice(0, 8)}
                      {p.id === source.publication_id ? " · pin histórico" : ""}
                    </option>
                  ))}
                </select>
              </label>
              {proposal && (
                <fieldset>
                  <legend>Parámetros propuestos</legend>
                  {proposal.parameters.map((p, index) => (
                    <label key={p.name}>
                      Valor propuesto {p.name}
                      <input
                        aria-label={`Valor propuesto ${p.name}`}
                        type={p.type === "boolean" ? "checkbox" : "number"}
                        checked={
                          p.type === "boolean" ? Boolean(p.value) : undefined
                        }
                        value={
                          p.type === "boolean" ? undefined : Number(p.value)
                        }
                        step={p.type === "integer" ? 1 : "any"}
                        min={p.min ?? undefined}
                        max={p.max ?? undefined}
                        onChange={(e) => {
                          reset();
                          setMappings({
                            ...proposal,
                            parameters: proposal.parameters.map((row, i) =>
                              i === index
                                ? {
                                    ...row,
                                    value:
                                      p.type === "boolean"
                                        ? e.target.checked
                                        : Number(e.target.value),
                                  }
                                : row,
                            ),
                          });
                        }}
                      />
                      <span>{ruleUnit(p.unit)}</span>
                    </label>
                  ))}
                </fieldset>
              )}
              {proposal && (
                <fieldset>
                  <legend>Objetos y fuentes propuestos</legend>
                  {proposal.aliases.map((a) => (
                    <label key={a.alias}>
                      Destino propuesto {a.alias}
                      <select
                        value={a.object_id}
                        onChange={(e) => {
                          reset();
                          const destination = Number(e.target.value);
                          const aliases = proposal.aliases.map((row) =>
                            row.alias === a.alias
                              ? { ...row, object_id: destination }
                              : row,
                          );
                          const contract = publication?.contract;
                          setMappings({
                            ...proposal,
                            aliases,
                            parameters: proposal.parameters.map((p) =>
                              contract?.parameters.find(
                                (c) => c.name === p.name,
                              )?.owner === a.alias
                                ? { ...p, object_id: destination }
                                : p,
                            ),
                            inputs: proposal.inputs.filter(
                              (p) =>
                                contract?.inputs.find(
                                  (c) => c.alias === p.alias,
                                )?.owner !== a.alias &&
                                p.object_id !== a.object_id,
                            ),
                            temporal: proposal.temporal
                              ? {
                                  ...proposal.temporal,
                                  initial_values:
                                    proposal.temporal.initial_values.map(
                                      (v, i) =>
                                        contract?.temporal?.initial_values[i]
                                          ?.owner === a.alias
                                          ? {
                                              ...v,
                                              object_id: destination,
                                              value: null,
                                              timestamp: "",
                                            }
                                          : v,
                                    ),
                                }
                              : null,
                          });
                        }}
                      >
                        <option value={0}>Selecciona un destino</option>
                        {objects.data?.items
                          .filter(
                            (o) =>
                              !publication?.contract ||
                              o.kind ===
                                publication.contract.aliases.find(
                                  (p) => p.alias === a.alias,
                                )?.kind,
                          )
                          .map((o) => (
                            <option key={o.id} value={o.id}>
                              {o.display_name}
                            </option>
                          ))}
                      </select>
                    </label>
                  ))}
                  <RuleInputs
                    root={root}
                    scenarioId={scope.scenario_id}
                    inputs={proposal.inputs}
                    onChange={(inputs) => {
                      reset();
                      setMappings({ ...proposal, inputs });
                    }}
                    objects={[
                      { id: objectId, label: "Objeto actual" },
                      ...proposal.aliases
                        .filter((a) => a.object_id > 0)
                        .map((a) => ({ id: a.object_id, label: a.alias })),
                    ]}
                    requiredPorts={requiredPorts}
                  />
                  {proposal.temporal?.initial_values.map((v, index) => (
                    <div key={index}>
                      <label>
                        Valor inicial propuesto {v.variable}
                        <input
                          type="number"
                          step="any"
                          value={v.value ?? ""}
                          onChange={(e) => {
                            reset();
                            setMappings({
                              ...proposal,
                              temporal: {
                                ...proposal.temporal!,
                                initial_values:
                                  proposal.temporal!.initial_values.map(
                                    (row, i) =>
                                      i === index
                                        ? {
                                            ...row,
                                            value:
                                              e.target.value === ""
                                                ? null
                                                : Number(e.target.value),
                                          }
                                        : row,
                                  ),
                              },
                            });
                          }}
                        />
                      </label>
                      <label>
                        Instante inicial propuesto {v.variable}
                        <input
                          value={v.timestamp}
                          onChange={(e) => {
                            reset();
                            setMappings({
                              ...proposal,
                              temporal: {
                                ...proposal.temporal!,
                                initial_values:
                                  proposal.temporal!.initial_values.map(
                                    (row, i) =>
                                      i === index
                                        ? { ...row, timestamp: e.target.value }
                                        : row,
                                  ),
                              },
                            });
                          }}
                        />
                      </label>
                    </div>
                  ))}
                </fieldset>
              )}
              <p>
                Conservar o recuperar una revisión exige probarla contra los
                objetos, fuentes y horizonte actuales. La aplicación vigente
                permanece activa hasta confirmar.
              </p>
              <button
                type="button"
                disabled={disabled || busy || running || !mappingsComplete}
                onClick={() =>
                  void act(async () => {
                    reset();
                    setComparison(
                      await post<Comparison>(`${path}/comparisons`, body),
                    );
                    setComparedRequest(currentRequest);
                  })
                }
              >
                Comparar con la aplicación histórica
              </button>
              {comparison && matches && (
                <>
                  <RevisionComparison comparison={comparison} />
                  <button
                    type="button"
                    disabled={disabled || busy || running || !available}
                    onClick={() =>
                      void act(async () => {
                        setJobId(
                          (
                            await post<RecoveryJob>(
                              `${path}/recovery-previews`,
                              body,
                            )
                          ).id,
                        );
                        setRequestId(crypto.randomUUID());
                      })
                    }
                  >
                    Probar recuperación
                  </button>
                </>
              )}
              {running && (
                <p role="status">
                  Probando la recuperación en todo el horizonte…
                </p>
              )}
              {job.data?.status === "failed" && (
                <p role="alert">
                  {job.data.result?.error?.message ?? "La prueba falló"}
                  {job.data.result?.error?.line
                    ? ` · línea ${job.data.result.error.line}`
                    : ""}
                </p>
              )}
              {ready && (
                <>
                  <p role="status">
                    Prueba completa: {rows?.length ?? 0} restricciones. No
                    garantiza factibilidad.
                  </p>
                  <details>
                    <summary>Ver restricciones de la recuperación</summary>
                    {rows?.slice(0, 100).map((r, i) => (
                      <p key={i}>
                        {r.name} · período {r.period + 1} ·{" "}
                        {r.terms
                          ?.slice(0, 20)
                          .map(
                            (t) =>
                              `${t.coefficient}${t.unit && t.unit !== "dimensionless" ? ` ${ruleUnit(t.unit)}` : ""} × objeto ${t.object_id}.${t.variable}[${t.period + 1}]`,
                          )
                          .join(" + ") || "0"}{" "}
                        {r.relation} {-r.constant} {ruleUnit(r.unit)}
                        {(r.terms?.length ?? 0) > 20 &&
                          ` · primeros 20 de ${r.terms!.length} términos`}
                      </p>
                    ))}
                    {(rows?.length ?? 0) > 100 && (
                      <p>Se muestran las primeras 100 filas.</p>
                    )}
                  </details>
                  {!rows?.length && (
                    <label>
                      <input
                        type="checkbox"
                        checked={acceptEmpty}
                        onChange={(e) => setAcceptEmpty(e.target.checked)}
                      />
                      Aceptar una aplicación sin restricciones
                    </label>
                  )}
                  <label>
                    Motivo de recuperación
                    <textarea
                      value={reason}
                      maxLength={1000}
                      onChange={(e) => setReason(e.target.value)}
                    />
                  </label>
                  <button
                    type="button"
                    disabled={
                      busy || !reason.trim() || (!rows?.length && !acceptEmpty)
                    }
                    onClick={() =>
                      void act(async () => {
                        await post(`${path}/resolutions`, {
                          job_id: jobId,
                          reason,
                          request_id: requestId,
                          accept_empty: acceptEmpty,
                        });
                        setJobId(undefined);
                        setComparison(undefined);
                        setSuccess(true);
                        await history.refetch();
                        await onResolved();
                      })
                    }
                  >
                    Confirmar recuperación
                  </button>
                </>
              )}
            </>
          )}
          {success && (
            <p role="status">
              Recuperación aplicada. La aplicación anterior permanece en el
              historial.
            </p>
          )}
          {(error || history.isError || job.isError) && (
            <p role="alert">
              {error || ruleErrorMessage(history.error ?? job.error)}
            </p>
          )}
        </>
      )}
    </section>
  );
}

function proposedMappings(
  source: HistoricalApplication,
  publication: Publication,
  objectId: number,
): Mappings {
  const contract = publication.contract;
  const aliases = (contract?.aliases ?? publication.aliases ?? []).map((a) => ({
    alias: a.alias,
    object_id: source.aliases.find((p) => p.alias === a.alias)?.object_id ?? 0,
  }));
  const owner = (ref: string | null) =>
    ref === "self"
      ? objectId
      : ref
        ? (aliases.find((a) => a.alias === ref)?.object_id ?? 0)
        : null;
  const parameters = publication.parameters.map((p) => ({
    ...p,
    value:
      source.parameters.find(
        (v) => v.name === p.name && v.unit === p.unit && v.type === p.type,
      )?.value ?? p.value,
    ...(contract
      ? {
          object_id: owner(
            contract.parameters.find((c) => c.name === p.name)?.owner ?? null,
          ),
        }
      : {}),
  }));
  const inputs = source.inputs
    .filter(
      (p) =>
        !contract ||
        contract.inputs.some(
          (c) =>
            c.alias === p.alias &&
            c.semantic_type_key === p.semantic_type_key &&
            c.dimension_key === p.dimension_key &&
            owner(c.owner) === p.object_id,
        ),
    )
    .map(
      ({
        alias,
        object_id,
        signal_id,
        revision_id,
        content_hash,
        dimension_key,
        semantic_type_key,
        binding_role_key,
      }) => ({
        alias,
        object_id,
        signal_id,
        revision_id,
        content_hash,
        dimension_key,
        semantic_type_key,
        binding_role_key,
      }),
    );
  const temporal = contract?.temporal
    ? {
        first_period: contract.temporal.first_period,
        initial_values: contract.temporal.initial_values.map((v) => {
          const previous = source.temporal?.initial_values.find(
            (p) =>
              p.object_id === owner(v.owner) &&
              p.variable === v.variable &&
              p.unit === v.unit,
          );
          return {
            object_id: owner(v.owner) ?? objectId,
            variable: v.variable,
            unit: v.unit,
            value: previous?.value ?? null,
            timestamp: previous?.timestamp ?? "",
          };
        }),
      }
    : (publication.temporal ?? null);
  return {
    parameters,
    aliases,
    inputs,
    temporal,
    windows: publication.windows ?? null,
  };
}

function RevisionComparison({ comparison }: { comparison: Comparison }) {
  const fields = [
    "publication_id",
    "code",
    "sdk",
    "parameters",
    "inputs",
    "aliases",
    "objects",
    "scope",
    "grid",
    "temporal",
    "windows",
  ] as const;
  const labels = {
    publication_id: "Revisión",
    code: "Código Python",
    sdk: "SDK",
    parameters: "Parámetros y unidades",
    inputs: "Fuentes y revisiones",
    aliases: "Referencias de objetos",
    objects: "Objetos y variables",
    scope: "Horizonte",
    grid: "Períodos y duraciones",
    temporal: "Política temporal",
    windows: "Ventanas",
  };
  function value(view: ComparisonView, key: (typeof fields)[number]) {
    if (key === "parameters")
      return view.parameters.map((p) => (
        <p key={p.name}>
          {p.name}: {String(p.value)} {ruleUnit(p.unit)}
          {p.object_id ? ` · objeto ${p.object_id}` : ""}
        </p>
      ));
    if (key === "inputs")
      return view.inputs.length
        ? view.inputs.map((p) => (
            <p key={p.alias}>
              {p.alias} · señal {p.signal_id} · revisión {p.revision_id} ·{" "}
              {p.unit_key ? ruleUnit(p.unit_key) : p.dimension_key} ·{" "}
              {p.semantic_type_key} · {p.timezone ?? "UTC"}
              {p.current_revision_id &&
                ` · última revisión ${p.current_revision_id}`}
              <br />
              <code>{p.content_hash}</code>
            </p>
          ))
        : "Sin entradas";
    if (key === "aliases")
      return view.aliases.length
        ? view.aliases.map((a) => (
            <p key={a.alias}>
              {a.alias} → objeto {a.object_id}
            </p>
          ))
        : "Sin alias";
    if (key === "objects")
      return view.objects.map((o) => (
        <p key={o.id}>
          {o.display_name ?? o.key} · objeto {o.id}
          <br />
          {Object.entries(o.variables ?? {})
            .map(([k, unit]) => `${k}: ${ruleUnit(unit)}`)
            .join(" · ")}
          {o.member_ids ? ` · miembros: ${o.member_ids.join(", ")}` : ""}
        </p>
      ));
    if (key === "scope")
      return (
        <p>
          Variante {view.scope.variant_id}
          <br />
          {view.scope.range_start} → {view.scope.range_end} · {view.timezone}
        </p>
      );
    if (key === "grid")
      return (
        <details>
          <summary>{view.grid.length} períodos</summary>
          <pre>{JSON.stringify(view.grid, null, 2)}</pre>
        </details>
      );
    if (key === "code") return <pre>{view.code}</pre>;
    if (key === "temporal" || key === "windows")
      return view[key] ? (
        <pre>{JSON.stringify(view[key], null, 2)}</pre>
      ) : (
        "Sin política"
      );
    return <code>{view[key]}</code>;
  }
  return (
    <div className="table-scroll">
      <table aria-label="Comparación de revisiones">
        <thead>
          <tr>
            <th>Aspecto</th>
            <th>Aplicación histórica</th>
            <th>Propuesta actual</th>
          </tr>
        </thead>
        <tbody>
          {fields.map((key) => (
            <tr key={key}>
              <th>
                {labels[key]}
                {comparison.changed_fields.includes(key) ? " · cambió" : ""}
              </th>
              <td>{value(comparison.before, key)}</td>
              <td>{value(comparison.after, key)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
