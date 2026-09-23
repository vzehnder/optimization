import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { getCsrfToken, requestJson } from "./api/client";
import { ProtectedJourneyProgress } from "./ProtectedMutationJourney";
import { RuleHourlyPreview, type NumericOutput } from "./RuleHourlyPreview";
import { ruleErrorMessage } from "./ruleErrors";
import { ruleUnit } from "./ruleUnits";

interface OutputOption {
  name: string;
  unit_key: string;
  period_count: number;
  classifications: {
    semantic_type_key: string;
    display_name: string;
    object_roles: string[];
  }[];
}
interface Definition {
  name: string;
  series_key: string;
  series_kind: "catalog" | "object_specific";
  output_name: string;
  semantic_type_key: string;
  unit_key: string;
  intended_binding_role_key?: string | null;
}
interface Publication {
  id: string;
  signal_id: number;
  revision_id: number;
  revision_number: number;
  definition: Definition;
  validation_status: string;
  validation_error?: { message: string };
}
export interface CalculatedJob {
  id: string;
  status: string;
  grid?: { timestamp: string }[];
  result?: { outputs?: NumericOutput[] };
}

export function RuleSeriesPublications({
  path,
  job,
  disabled,
}: {
  path: string;
  job?: CalculatedJob;
  disabled: boolean;
}) {
  const client = useQueryClient();
  const location = useLocation();
  const publications = useQuery({
    queryKey: [path, "series-publications"],
    queryFn: () =>
      requestJson<{ items: Publication[] }>(`${path}/series-publications`),
    retry: false,
  });
  const options = useQuery({
    queryKey: [path, job?.id, "series-options"],
    queryFn: () =>
      requestJson<{ outputs: OutputOption[] }>(
        `${path}/tests/${job!.id}/series-options`,
      ),
    enabled: job?.status === "succeeded",
    retry: false,
  });
  const [step, setStep] = useState<number | null>(null);
  const [kind, setKind] = useState<Definition["series_kind"]>("catalog");
  const [name, setName] = useState("");
  const [seriesKey, setSeriesKey] = useState("");
  const [outputName, setOutputName] = useState("");
  const [semantic, setSemantic] = useState("");
  const [role, setRole] = useState("");
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [receipt, setReceipt] = useState<Publication>();
  const requestKey = useRef<string | undefined>(undefined);
  const [regeneration, setRegeneration] = useState<Publication>();
  const output = options.data?.outputs.find((p) => p.name === outputName);
  const classification = output?.classifications.find(
    (p) => p.semantic_type_key === semantic,
  );
  const ready =
    !!output &&
    !!classification &&
    !!name.trim() &&
    /^[a-z][a-z0-9_]{0,63}$/.test(seriesKey) &&
    (kind === "catalog" || classification.object_roles.includes(role));
  const projectId = path.split("/")[3];
  const objectId = path.split("/")[5];
  const destination = (item: Publication) =>
    item.definition.series_kind === "catalog"
      ? `/time-series/catalog?${new URLSearchParams({ inspector: String(item.signal_id), project_id: projectId, return_to: location.pathname + location.search })}`
      : `/projects/${projectId}/linkable-objects/${objectId}/time-series`;

  async function publish() {
    if (!ready || !job || busy) return;
    setBusy(true);
    setError("");
    requestKey.current ??= crypto.randomUUID();
    try {
      const result = await requestJson<Publication>(
        `${path}/series-publications${regeneration ? `/${regeneration.id}/regenerations` : ""}`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-CSRF-Token": await getCsrfToken(),
            "Idempotency-Key": requestKey.current,
          },
          body: JSON.stringify(
            regeneration
              ? {
                  job_id: job.id,
                  expected_revision_id: regeneration.revision_id,
                  reason,
                }
              : {
                  job_id: job.id,
                  output_name: outputName,
                  name: name.trim(),
                  series_key: seriesKey,
                  semantic_type_key: semantic,
                  unit_key: output!.unit_key,
                  series_kind: kind,
                  intended_binding_role_key:
                    kind === "object_specific" ? role : null,
                  reason,
                },
          ),
        },
      );
      setReceipt(result);
      setStep(null);
      await publications.refetch();
      await client.invalidateQueries({
        predicate: (q) =>
          [
            "catalog-inputs",
            "catalog-input-detail",
            "object-time-series-summary",
            "journey-object",
            "journey-candidates",
          ].includes(String(q.queryKey[0])),
        refetchType: "none",
      });
    } catch (e) {
      setError(ruleErrorMessage(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="rule-inputs" aria-label="Series calculadas">
      <h2>Series calculadas</h2>
      <p>
        Publica una salida numérica completa de la prueba. Después podrás
        seleccionar su revisión como entrada compatible.
      </p>
      {step === null && (
        <button
          type="button"
          disabled={disabled || !options.data?.outputs.length}
          onClick={() => {
            setStep(0);
            setRegeneration(undefined);
            setReceipt(undefined);
            setError("");
            setName("");
            setSeriesKey("");
            setReason("");
            setKind("catalog");
            setOutputName(options.data?.outputs[0]?.name ?? "");
            setSemantic("");
            setRole("");
            requestKey.current = undefined;
          }}
        >
          Publicar serie calculada
        </button>
      )}
      {job?.status === "succeeded" &&
        options.data &&
        !options.data.outputs.length && (
          <p>No hay salidas numéricas completas para publicar.</p>
        )}
      {step !== null && (
        <section aria-label="Publicar salida calculada">
          <ProtectedJourneyProgress step={step} />
          {step === 0 && (
            <fieldset disabled={!!regeneration}>
              <legend>Destino de la serie</legend>
              <label>
                <input
                  type="radio"
                  checked={kind === "catalog"}
                  onChange={() => setKind("catalog")}
                />
                Catálogo del proyecto
              </label>
              <label>
                <input
                  type="radio"
                  checked={kind === "object_specific"}
                  onChange={() => setKind("object_specific")}
                />
                Solo este objeto
              </label>
              <p>
                {kind === "catalog"
                  ? "Nueva fuente disponible en el proyecto."
                  : "El propietario será este objeto y se conservará en todas las revisiones."}
              </p>
            </fieldset>
          )}
          {step === 1 && (
            <fieldset disabled={!!regeneration}>
              <legend>Salida y clasificación</legend>
              <label>
                Salida numérica
                <select
                  value={outputName}
                  onChange={(e) => {
                    setOutputName(e.target.value);
                    setSemantic("");
                    setRole("");
                  }}
                >
                  {options.data?.outputs.map((p) => (
                    <option key={p.name} value={p.name}>
                      {p.name} · {ruleUnit(p.unit_key)}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Nombre de la serie
                <input
                  disabled={!!regeneration}
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                />
              </label>
              <label>
                Clave de la serie
                <input
                  value={seriesKey}
                  onChange={(e) => setSeriesKey(e.target.value)}
                />
              </label>
              <label>
                Clasificación de la salida
                <select
                  value={semantic}
                  onChange={(e) => {
                    setSemantic(e.target.value);
                    setRole("");
                  }}
                >
                  <option value="">Selecciona una clasificación</option>
                  {output?.classifications
                    .filter((c) => kind === "catalog" || c.object_roles.length)
                    .map((c) => (
                      <option
                        key={c.semantic_type_key}
                        value={c.semantic_type_key}
                      >
                        {c.display_name}
                      </option>
                    ))}
                </select>
              </label>
              <p>
                Unidad: {ruleUnit(output?.unit_key ?? "")} · Datos derivados ·
                UTC
              </p>
              {kind === "object_specific" && (
                <label>
                  Rol de la serie
                  <select
                    value={role}
                    onChange={(e) => setRole(e.target.value)}
                  >
                    <option value="">Selecciona un rol</option>
                    {classification?.object_roles.map((r) => (
                      <option key={r} value={r}>
                        {r}
                      </option>
                    ))}
                  </select>
                </label>
              )}
            </fieldset>
          )}
          {step === 2 && (
            <>
              <p>
                {output?.period_count} intervalos completos ·{" "}
                {ruleUnit(output?.unit_key ?? "")} · UTC
              </p>
              <RuleHourlyPreview
                bounds={[]}
                outputs={
                  job?.result?.outputs?.filter((p) => p.name === outputName) ??
                  []
                }
                grid={job?.grid}
              />
            </>
          )}
          {step === 3 && (
            <>
              <p>
                Se publicará «{name}» en{" "}
                {kind === "catalog"
                  ? "el catálogo del proyecto"
                  : "este objeto"}{" "}
                con la clasificación {semantic}. Las entradas y revisiones
                anteriores se conservan. Usarla en una variante será una
                selección explícita.
              </p>
              {regeneration && (
                <p>
                  Se creará una nueva revisión. Los consumidores conservarán su
                  pin y deberán revalidar o seleccionar otra revisión
                  explícitamente.
                </p>
              )}
              <label>
                Motivo de publicación
                <input
                  value={reason}
                  onChange={(e) => {
                    setReason(e.target.value);
                    requestKey.current = undefined;
                  }}
                />
              </label>
              <button
                type="button"
                disabled={busy || disabled || !ready || !reason.trim()}
                onClick={() => void publish()}
              >
                {busy
                  ? "Publicando…"
                  : regeneration
                    ? "Confirmar regeneración"
                    : "Confirmar publicación"}
              </button>
            </>
          )}
          {step < 3 && (
            <button
              type="button"
              disabled={step === 1 && !ready}
              onClick={() => setStep(step + 1)}
            >
              Continuar publicación
            </button>
          )}
          {step > 0 && (
            <button
              type="button"
              disabled={busy}
              onClick={() => {
                setStep(step - 1);
                requestKey.current = undefined;
              }}
            >
              Anterior
            </button>
          )}
          <button type="button" disabled={busy} onClick={() => setStep(null)}>
            Cancelar publicación
          </button>
        </section>
      )}
      {receipt && (
        <p role="status">
          Serie publicada · revisión {receipt.revision_number}.{" "}
          <Link to={destination(receipt)}>Ver serie publicada</Link>
        </p>
      )}
      {publications.data?.items.map((p) => (
        <article key={p.id}>
          <strong>{p.definition.name}</strong>
          <p>
            Revisión {p.revision_number} ·{" "}
            {p.definition.series_kind === "catalog"
              ? "Catálogo del proyecto"
              : "Solo este objeto"}
          </p>
          <p>
            {p.validation_status === "stale"
              ? `Receta obsoleta: ${p.validation_error?.message}`
              : "Receta vigente"}
          </p>
          <Link to={destination(p)}>Ver {p.definition.name}</Link>
          <button
            type="button"
            disabled={
              disabled ||
              !options.data?.outputs.some(
                (o) =>
                  o.name === p.definition.output_name &&
                  o.unit_key === p.definition.unit_key,
              )
            }
            onClick={() => {
              setRegeneration(p);
              setStep(0);
              setReceipt(undefined);
              setError("");
              setReason("");
              requestKey.current = undefined;
              setKind(p.definition.series_kind);
              setName(p.definition.name);
              setSeriesKey(p.definition.series_key);
              setOutputName(p.definition.output_name);
              setSemantic(p.definition.semantic_type_key);
              setRole(p.definition.intended_binding_role_key ?? "");
            }}
          >
            Regenerar {p.definition.name}
          </button>
        </article>
      ))}
      {(error || options.isError) && (
        <p role="alert">{error || ruleErrorMessage(options.error)}</p>
      )}
    </section>
  );
}
