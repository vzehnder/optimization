import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { ApiError, getCsrfToken, requestJson } from "./api/client";
import {
  RuleHourlyPreview,
  type HourlyBound,
  type NumericOutput,
} from "./RuleHourlyPreview";
import { ruleErrorMessage } from "./ruleErrors";
import type { RuleAlias, RuleObject } from "./RuleObjects";
import { ruleUnit } from "./ruleUnits";
import type { TemporalPolicy } from "./RuleTemporal";
import type { WindowPolicy } from "./RuleWindows";
import { RuleSeriesPublications } from "./RuleSeriesPublications";
import { RuleRecovery } from "./RuleRecovery";
import { validationLabel } from "./ruleStatus";

interface Scope {
  scenario_id: number;
  variant_id: number;
  range_start: string;
  range_end: string;
}
interface Row {
  name: string;
  period: number;
  line: number;
  relation: string;
  constant: number;
  unit: string;
  window?: {
    start: string;
    end: string;
    duration_hours: number;
    periods: number[];
    partial: boolean;
  };
  terms: {
    coefficient: number;
    object_id?: number;
    variable?: string;
    period?: number;
    unit?: string;
  }[];
}
interface Job {
  id: string;
  status: string;
  publication_id: string;
  compilation_scope: Scope;
  grid?: { timestamp: string }[];
  objects?: RuleObject[];
  aliases?: RuleAlias[];
  diagnostic?: { category: string; action: string };
  result?: {
    ir?: { rows: Row[] };
    bounds?: HourlyBound[];
    outputs?: NumericOutput[];
    temporal?: TemporalPolicy & { omitted_periods: number[] };
    windows?: WindowPolicy;
    error?: {
      code: string;
      message: string;
      line?: number;
      period?: number;
      alias?: string;
    };
  };
}
interface Application {
  id: string;
  revision: number;
  status: string;
  publication_id: string;
  variant_id: number;
  compilation?: { scope: Scope };
  validation_status?: string;
  validation_error?: { message: string; alias?: string };
}
async function post<T>(path: string, body: unknown, requestId?: string) {
  return requestJson<T>(path, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRF-Token": await getCsrfToken(),
      ...(requestId ? { "X-Request-Id": requestId } : {}),
    },
    body: JSON.stringify(body),
  });
}

export function RuleApplications({
  root,
  ruleId,
  revision,
  disabled,
  available,
  template,
  instanceVariant,
  onRecovered,
}: {
  root: string;
  ruleId: string;
  revision: number;
  disabled: boolean;
  available: boolean;
  template?: { rule_id: string; publication_id: string };
  instanceVariant?: number;
  onRecovered?: () => Promise<void>;
}) {
  const queryClient = useQueryClient();
  const [search, setSearch] = useSearchParams();
  const navigate = useNavigate();
  const scenario = search.get("scenario_id");
  const path = `${root}/${ruleId}`;
  const scope = useQuery({
    queryKey: [root, "scope", scenario],
    queryFn: () =>
      requestJson<{
        variants: { id: number; display_name: string }[];
        range_start: string;
        range_end: string;
      }>(`${root}/scope?scenario_id=${scenario}`),
    enabled: !!scenario,
    retry: false,
  });
  const apps = useQuery({
    queryKey: [path, "applications", revision],
    queryFn: () =>
      requestJson<{ items: Application[] }>(`${path}/applications`),
    retry: false,
  });
  const [published, setPublished] = useState<{
    id: string;
    draft_revision: number;
    instance_revision?: number;
  }>();
  const [variant, setVariant] = useState<number | undefined>(
    () => Number(search.get("variant_id")) || undefined,
  );
  const [start, setStart] = useState<string>();
  const [end, setEnd] = useState<string>();
  const [reason, setReason] = useState("");
  const [acceptEmpty, setAcceptEmpty] = useState(false);
  const [busy, setBusy] = useState(false);
  const [libraryPublished, setLibraryPublished] = useState<string>();
  const [error, setError] = useState("");
  const [conflicts, setConflicts] = useState<
    { name: string; period: number; rule_url: string }[]
  >([]);
  const [page, setPage] = useState(0);
  const [termPages, setTermPages] = useState<Record<string, number>>({});
  const requestId = useRef<string | undefined>(undefined);
  const jobId = search.get("constraint_test");
  const job = useQuery({
    queryKey: [path, "constraint_test", jobId],
    queryFn: () => requestJson<Job>(`${path}/tests/${jobId}`),
    enabled: !!jobId,
    retry: false,
    refetchInterval: (query) =>
      ["queued", "running"].includes(query.state.data?.status ?? "")
        ? 350
        : false,
  });
  const selected = instanceVariant ?? variant ?? scope.data?.variants[0]?.id;
  const selectedScope: Scope = {
    scenario_id: Number(scenario),
    variant_id: selected ?? 0,
    range_start: start ?? scope.data?.range_start ?? "",
    range_end: end ?? scope.data?.range_end ?? "",
  };
  const active = apps.data?.items.find(
    (item) => item.status === "active" && item.variant_id === selected,
  );
  const rows = job.data?.result?.ir?.rows;
  const temporal = job.data?.result?.temporal;
  const utcMillis = (stamp: string) =>
    Date.parse(/(?:Z|[+-]\d{2}:\d{2})$/.test(stamp) ? stamp : `${stamp}Z`);
  const running = ["queued", "running"].includes(job.data?.status ?? "");
  const matchingScope =
    job.data?.compilation_scope &&
    Object.entries(selectedScope).every(
      ([key, value]) =>
        job.data?.compilation_scope[key as keyof Scope] === value,
    );
  async function act(action: () => Promise<void>) {
    setBusy(true);
    setError("");
    setConflicts([]);
    try {
      await action();
    } catch (error) {
      setError(ruleErrorMessage(error));
      if (
        error instanceof ApiError &&
        error.details &&
        typeof error.details === "object"
      ) {
        const details = error.details as { conflicts?: typeof conflicts };
        if (Array.isArray(details.conflicts)) setConflicts(details.conflicts);
      }
    } finally {
      setBusy(false);
    }
  }
  return (
    <section aria-label="Aplicar restricciones" className="rule-applications">
      <h2>Aplicar a la optimización</h2>
      <p>
        Publica una revisión, prueba todo el horizonte y aplica sus
        restricciones a una variante. Una prueba exitosa no garantiza
        factibilidad.
      </p>
      <button
        type="button"
        disabled={disabled || busy}
        onClick={() =>
          void act(async () => {
            setPublished(
              await post(`${path}/publications`, {
                expected_revision: revision,
              }),
            );
          })
        }
      >
        {template ? "Preparar revisión fijada" : "Publicar revisión"}
      </button>
      {published && !template && (
        <button
          type="button"
          disabled={disabled || busy}
          onClick={() =>
            void act(async () => {
              await post(`${path}/library`, { publication_id: published.id });
              setError("");
              setLibraryPublished(published.id);
            })
          }
        >
          Ofrecer en biblioteca
        </button>
      )}
      {libraryPublished && (
        <p role="status">Revisión disponible en la biblioteca del proyecto.</p>
      )}
      {published && (
        <p role="status">
          Revisión publicada {published.id} · borrador{" "}
          {published.instance_revision ?? published.draft_revision}
        </p>
      )}
      {!scenario && (
        <p>
          Abre esta regla desde la unidad del diagrama para seleccionar la
          variante.
        </p>
      )}
      {scope.data && (
        <fieldset disabled={busy || running}>
          <legend>Variante y horizonte completo (UTC)</legend>
          <label>
            Variante de aplicación
            <select
              disabled={!!instanceVariant}
              value={selected}
              onChange={(event) => setVariant(Number(event.target.value))}
            >
              {scope.data.variants.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.display_name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Inicio UTC
            <input
              value={selectedScope.range_start}
              onChange={(event) => setStart(event.target.value)}
            />
          </label>
          <label>
            Fin UTC exclusivo
            <input
              value={selectedScope.range_end}
              onChange={(event) => setEnd(event.target.value)}
            />
          </label>
        </fieldset>
      )}
      <button
        type="button"
        disabled={
          disabled ||
          busy ||
          running ||
          !available ||
          !selected ||
          !published ||
          (published.instance_revision ?? published.draft_revision) !== revision
        }
        onClick={() =>
          void act(async () => {
            const started = await post<Job>(`${path}/tests`, {
              expected_revision: revision,
              publication_id: published?.id,
              scope: selectedScope,
            });
            const next = new URLSearchParams(search);
            next.set("constraint_test", started.id);
            setSearch(next, { replace: true });
            setPage(0);
          })
        }
      >
        Probar restricciones
      </button>
      {running && (
        <>
          <p role="status">Compilando restricciones…</p>
          <button
            type="button"
            disabled={busy}
            onClick={() =>
              void act(async () => {
                await post(`${path}/tests/${jobId}/cancel`, {});
                await job.refetch();
              })
            }
          >
            Cancelar compilación
          </button>
        </>
      )}
      {job.data?.status === "cancelled" && (
        <p role="status">Compilación cancelada</p>
      )}
      {job.data?.result?.error && (
        <p role="alert">
          {job.data.result.error.alias && `${job.data.result.error.alias} · `}
          {job.data.result.error.period !== undefined &&
            (job.data.result.error.period < 0
              ? `índice ${job.data.result.error.period} · `
              : `período ${job.data.result.error.period + 1} · `)}
          {job.data.result.error.code} · línea {job.data.result.error.line}:{" "}
          {job.data.result.error.message}
        </p>
      )}
      {job.data?.diagnostic && <p>{job.data.diagnostic.action}</p>}
      {rows && (
        <>
          {temporal && (
            <section aria-label="Cobertura temporal">
              <h3>Comparaciones entre períodos</h3>
              {temporal.first_period === "omit" ? (
                <p>
                  Primera comparación omitida: período 1 ·{" "}
                  {job.data?.grid?.[0]?.timestamp}.
                </p>
              ) : (
                <>
                  <p>Primera comparación con condición inicial declarada.</p>
                  {temporal.initial_values.map((value) => (
                    <p key={`${value.object_id}:${value.variable}`}>
                      {job.data?.objects?.find((o) => o.id === value.object_id)
                        ?.display_name ?? `Objeto ${value.object_id}`}
                      .{value.variable}: {value.value} {ruleUnit(value.unit)} ·{" "}
                      {value.timestamp}
                    </p>
                  ))}
                </>
              )}
              <p>
                {new Set(rows.map((row) => row.period)).size} períodos con
                restricciones en esta prueba.
              </p>
            </section>
          )}
          <p>
            {rows.length} {rows.length === 1 ? "restricción" : "restricciones"}{" "}
            · unidad{" "}
            {Array.from(new Set(rows.map((row) => ruleUnit(row.unit)))).join(
              ", ",
            )}{" "}
            · {job.data?.compilation_scope.range_start} a{" "}
            {job.data?.compilation_scope.range_end} UTC
          </p>
          {rows.length > 0 ? (
            <>
              <div className="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>Nombre</th>
                      <th>Período</th>
                      <th>Expresión</th>
                      <th>Línea</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.slice(page * 20, (page + 1) * 20).map((row) => (
                      <tr key={`${row.name}-${row.period}`}>
                        <td>{row.name}</td>
                        <td>
                          {row.period + 1}
                          {row.window && (
                            <>
                              <div>Inicio UTC: {row.window.start}</div>
                              <div>Fin UTC: {row.window.end}</div>
                              <div>
                                Duración real: {row.window.duration_hours} h
                              </div>
                              <div>
                                {row.window.periods.length} períodos ·{" "}
                                {row.terms.length} términos
                              </div>
                              <div>
                                {job.data?.result?.windows?.kind === "horizon"
                                  ? "Horizonte completo"
                                  : row.window.partial
                                    ? "Día parcial aceptado"
                                    : "Día completo"}{" "}
                                · {job.data?.result?.windows?.timezone}
                              </div>
                              <div>
                                Presupuesto efectivo:{" "}
                                {row.relation === "<="
                                  ? "≤"
                                  : row.relation === ">="
                                    ? "≥"
                                    : "="}{" "}
                                {-row.constant} {ruleUnit(row.unit)}
                              </div>
                            </>
                          )}
                          {temporal && (
                            <>
                              <div>
                                {job.data?.grid?.[row.period]?.timestamp}
                              </div>
                              {[
                                ...new Set(
                                  row.terms
                                    .map((t) => t.period)
                                    .filter(
                                      (t): t is number =>
                                        t !== undefined && t < row.period,
                                    ),
                                ),
                              ].map((previous) => {
                                const start =
                                  job.data?.grid?.[row.period]?.timestamp;
                                const before =
                                  job.data?.grid?.[previous]?.timestamp;
                                return start && before ? (
                                  <div key={previous}>
                                    Distancia entre inicios:{" "}
                                    {(utcMillis(start) - utcMillis(before)) /
                                      3600000}{" "}
                                    h (período {previous + 1})
                                  </div>
                                ) : null;
                              })}
                            </>
                          )}
                        </td>
                        <td>
                          {row.terms
                            .slice(
                              row.window
                                ? (termPages[`${row.name}-${row.period}`] ??
                                    0) * 20
                                : 0,
                              row.window
                                ? ((termPages[`${row.name}-${row.period}`] ??
                                    0) +
                                    1) *
                                    20
                                : undefined,
                            )
                            .map((term) => {
                              const object = job.data?.objects?.find(
                                (o) => o.id === term.object_id,
                              );
                              const reference =
                                (temporal || row.window) &&
                                term.period !== undefined
                                  ? `[${term.period + 1} · ${job.data?.grid?.[term.period]?.timestamp}]`
                                  : "";
                              return `${term.coefficient}${row.window && term.unit ? ` ${ruleUnit(term.unit)}` : ""} × ${object ? `${object.display_name}.` : term.object_id ? `Objeto ${term.object_id}.` : ""}${term.variable ?? "caudal"}${reference}`;
                            })
                            .join(" + ") || "0"}{" "}
                          {row.relation} {-row.constant} {ruleUnit(row.unit)}
                          {row.window && row.terms.length > 20 && (
                            <nav aria-label={`Términos de ${row.name}`}>
                              <button
                                type="button"
                                disabled={
                                  !(termPages[`${row.name}-${row.period}`] ?? 0)
                                }
                                onClick={() =>
                                  setTermPages({
                                    ...termPages,
                                    [`${row.name}-${row.period}`]:
                                      (termPages[`${row.name}-${row.period}`] ??
                                        0) - 1,
                                  })
                                }
                              >
                                Términos anteriores de {row.name}
                              </button>
                              <span>
                                Mostrando{" "}
                                {(termPages[`${row.name}-${row.period}`] ?? 0) *
                                  20 +
                                  1}
                                –
                                {Math.min(
                                  ((termPages[`${row.name}-${row.period}`] ??
                                    0) +
                                    1) *
                                    20,
                                  row.terms.length,
                                )}{" "}
                                de {row.terms.length}
                              </span>
                              <button
                                type="button"
                                disabled={
                                  ((termPages[`${row.name}-${row.period}`] ??
                                    0) +
                                    1) *
                                    20 >=
                                  row.terms.length
                                }
                                onClick={() =>
                                  setTermPages({
                                    ...termPages,
                                    [`${row.name}-${row.period}`]:
                                      (termPages[`${row.name}-${row.period}`] ??
                                        0) + 1,
                                  })
                                }
                              >
                                Más términos de {row.name}
                              </button>
                            </nav>
                          )}
                        </td>
                        <td>{row.line}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {rows.length > 20 && (
                <nav aria-label="Páginas de restricciones">
                  <button
                    type="button"
                    disabled={page === 0}
                    onClick={() => setPage(page - 1)}
                  >
                    Anterior
                  </button>
                  <span>Página {page + 1}</span>
                  <button
                    type="button"
                    disabled={(page + 1) * 20 >= rows.length}
                    onClick={() => setPage(page + 1)}
                  >
                    Siguiente
                  </button>
                </nav>
              )}
            </>
          ) : (
            <label>
              <input
                type="checkbox"
                checked={acceptEmpty}
                onChange={(event) => setAcceptEmpty(event.target.checked)}
              />
              Acepto aplicar una regla sin restricciones
            </label>
          )}
          {!matchingScope && (
            <p>
              El horizonte o la variante cambió; vuelve a probar antes de
              aplicar.
            </p>
          )}
        </>
      )}
      {job.data?.status === "succeeded" && (
        <RuleHourlyPreview
          key={jobId}
          bounds={job.data.result?.bounds ?? []}
          outputs={job.data.result?.outputs ?? []}
          grid={job.data.grid}
        />
      )}
      <RuleSeriesPublications
        key={`series-${job.data?.id ?? ruleId}`}
        path={path}
        job={job.data}
        disabled={disabled}
      />
      <label>
        Motivo de aplicación o desactivación
        <input
          value={reason}
          onChange={(event) => setReason(event.target.value)}
        />
      </label>
      <button
        type="button"
        disabled={
          busy ||
          disabled ||
          !reason.trim() ||
          !matchingScope ||
          !rows ||
          (!rows.length && !acceptEmpty) ||
          !!active
        }
        onClick={() =>
          void act(async () => {
            await post(`${path}/applications`, {
              job_id: jobId,
              reason,
              accept_empty: acceptEmpty,
            });
            requestId.current = undefined;
            await apps.refetch();
          })
        }
      >
        Aplicar a variante
      </button>
      {active && (
        <>
          <p role="status">
            Revisión {active.publication_id} aplicada a esta variante.
            {active.validation_status &&
              ` ${validationLabel(active.validation_status)}.`}
          </p>
          {active.validation_error && (
            <p role="alert">
              {active.validation_error.alias &&
                `${active.validation_error.alias}: `}
              {active.validation_error.message}
            </p>
          )}
          {active.validation_status === "stale" && (
            <>
              <p>
                Usa «Comparar y recuperar revisiones» para revalidar o
                reemplazar la aplicación con motivo.
              </p>
              <button
                type="button"
                disabled={busy || disabled || running || !available}
                onClick={() =>
                  void act(async () => {
                    const started = await post<Job>(`${path}/tests`, {
                      expected_revision: revision,
                      publication_id: active.publication_id,
                      scope: selectedScope,
                    });
                    const next = new URLSearchParams(search);
                    next.set("constraint_test", started.id);
                    setSearch(next, { replace: true });
                    setPage(0);
                  })
                }
              >
                Probar revisión fijada
              </button>
            </>
          )}
          <button
            type="button"
            disabled={busy || !reason.trim()}
            onClick={() =>
              void act(async () => {
                await post(`${path}/applications/${active.id}/deactivate`, {
                  expected_revision: active.revision,
                  reason,
                });
                requestId.current = undefined;
                await apps.refetch();
              })
            }
          >
            Desactivar aplicación
          </button>
          <button
            type="button"
            disabled={
              busy ||
              ["stale", "invalid"].includes(active.validation_status ?? "")
            }
            onClick={() =>
              void act(async () => {
                requestId.current ??= crypto.randomUUID();
                const run = await post<{ id: number }>(
                  `/api/scenarios/${scenario}/case/variants/${selected}/run`,
                  {
                    range_start: selectedScope.range_start,
                    range_end: selectedScope.range_end,
                  },
                  requestId.current,
                );
                navigate(`/runs/${run.id}`);
              })
            }
          >
            Ejecutar variante con reglas
          </button>
        </>
      )}
      {apps.data?.items.some((item) => item.status === "inactive") && (
        <p>Las aplicaciones desactivadas se conservan en el historial.</p>
      )}
      <RuleRecovery
        root={root}
        ruleId={ruleId}
        revision={revision}
        scope={selectedScope}
        disabled={disabled || busy}
        available={available}
        onResolved={async () => {
          requestId.current = undefined;
          await apps.refetch();
          await queryClient.invalidateQueries({ queryKey: [root] });
          await onRecovered?.();
        }}
      />
      {(error || scope.isError || apps.isError || job.isError) && (
        <p role="alert">
          {error || String(scope.error ?? apps.error ?? job.error)}
        </p>
      )}
      {!!conflicts.length && (
        <nav aria-label="Reglas con cotas contradictorias">
          <ul>
            {conflicts.map((c, i) => (
              <li key={i}>
                <a href={c.rule_url}>
                  {c.name} · período {c.period + 1}
                </a>
              </li>
            ))}
          </ul>
        </nav>
      )}
    </section>
  );
}

export function RunRuleSummary({ document }: { document: unknown }) {
  const applications = (
    document as
      | {
          component_rules?: {
            applications?: {
              id: string;
              name: string;
              publication_id: string;
              code?: string;
              code_hash?: string;
              context_hash?: string;
              ir_hash?: string;
              runtime?: { sdk: string; image: string };
              inputs?: {
                alias: string;
                revision_id: number;
                content_hash: string;
                unit_key: string;
              }[];
              objects?: RuleObject[];
              events?: {
                action: string;
                actor: number;
                reason?: string;
                at: string;
              }[];
              parameters: {
                name: string;
                value: number | boolean;
                unit: string;
              }[];
            }[];
          };
        }
      | undefined
  )?.component_rules?.applications;
  if (!applications?.length) return null;
  return (
    <section aria-label="Reglas de esta ejecución">
      <h2>Reglas de esta ejecución</h2>
      <ul>
        {applications.map((item) => (
          <li key={item.id}>
            <strong>{item.name}</strong>
            <p>
              Revisión <code>{item.publication_id}</code>
            </p>
            <ul>
              {item.parameters.map((parameter) => (
                <li key={parameter.name}>
                  {parameter.name}: {String(parameter.value)}{" "}
                  {parameter.unit === "m3_per_s"
                    ? "m³/s"
                    : parameter.unit === "dimensionless"
                      ? "adimensional"
                      : parameter.unit}
                </li>
              ))}
            </ul>
            {item.code_hash && (
              <details>
                <summary>Ver revisión exacta consumida</summary>
                <p>Contenido congelado al crear esta corrida.</p>
                <p>
                  Hash de código: <code>{item.code_hash}</code>
                </p>
                <p>
                  Hash de contexto: <code>{item.context_hash}</code>
                </p>
                <p>
                  Hash de restricciones: <code>{item.ir_hash}</code>
                </p>
                <p>
                  SDK: {item.runtime?.sdk} · Imagen:{" "}
                  <code>{item.runtime?.image}</code>
                </p>
                <pre>{item.code}</pre>
                {item.inputs?.map((input) => (
                  <p key={input.alias}>
                    {input.alias} · revisión {input.revision_id} ·{" "}
                    {ruleUnit(input.unit_key)}
                    <br />
                    <code>{input.content_hash}</code>
                  </p>
                ))}
                {item.objects?.map((object) => (
                  <p key={object.id}>
                    {object.display_name ?? object.key} · objeto {object.id}
                  </p>
                ))}
                <ul>
                  {item.events?.map((event, i) => (
                    <li key={i}>
                      {event.at} · {event.action} · Actor {event.actor} ·{" "}
                      {event.reason}
                    </li>
                  ))}
                </ul>
              </details>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
