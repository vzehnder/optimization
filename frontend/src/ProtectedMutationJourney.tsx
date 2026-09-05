import { useQuery } from "@tanstack/react-query";
import { Fragment, ReactNode, useState } from "react";
import { useSearchParams } from "react-router-dom";

import {
  ApiError,
  commitCaseBindings,
  commitCatalogAssociations,
  commitObjectSeriesDerivation,
  getCatalogInputDetail,
  getObjectCatalogAssociation,
  getObjectTimeSeriesContext,
  listCaseInputVariants,
  listCaseTimeSeriesBindings,
  listCatalogDescriptors,
  listCatalogSourcesForObject,
  listObjectCandidatesForSignal,
  listScenarios,
  prepareSharedSeriesIngestion,
  prevalidateCaseBindings,
  prevalidateCatalogAssociations,
  prevalidateObjectSeriesDerivation,
  publishSharedSeriesIngestion,
  type AssociationBatchRequest,
  type BatchCommitResult,
  type BatchPrevalidation,
  type BindingBatchRequest,
  type CaseBindingRow,
  type CatalogCandidateRow,
  type CatalogInputDetail,
  type IngestionPoint,
  type IngestionReceipt,
  type ObjectCandidateRow,
  type ObjectSeriesDerivationPrevalidation,
  type SharedSourceAlternative,
  type SharedSourceImpact,
  type SharedSourceTarget,
} from "./api/client";

// Chapter 8.3: the journey is the only pattern that mutates, so its four steps
// are fixed and always run in this order. The rail names them once and every
// step renders inside it.
const STEPS = [
  { id: "origin", label: "Origen y alcance" },
  { id: "selection", label: "Definicion o seleccion" },
  { id: "data", label: "Datos o revision" },
  { id: "impact", label: "Impacto y confirmacion" },
] as const;

type StepId = (typeof STEPS)[number]["id"];

type SourceChoice = "" | "generic" | "object_specific";

// Chapter 8.4: the two named actions are different and sequential. `binding`
// is never the visible word for the second one.
type LinkIntent = "associate" | "use_revision";

const INTENT_ACTIONS: Record<LinkIntent, string> = {
  associate: "Asociar fuente al objeto",
  use_revision: "Usar revision en una variante",
};

// AC-SHR-03: the shared branch keeps its own words. The server orders the two
// outcomes and names them by a stable key; the surface only translates them,
// and neither key has a neutral synonym.
const ALTERNATIVE_LABELS: Record<string, string> = {
  create_specific_for_this_object: "Crear especifica para este objeto",
  publish_for_everyone: "Publicar para todos",
};

const VERDICT_LABELS: Record<string, string> = {
  accepted: "Aceptada",
  rejected: "Rechazada",
  confirmation_required: "Requiere confirmacion",
};

function numericParam(value: string | null): number | null {
  if (!value || !/^\d+$/.test(value)) return null;
  const parsed = Number(value);
  return Number.isSafeInteger(parsed) && parsed > 0 ? parsed : null;
}

// Chapter 8.5: the local label is not decoration. It travels with the draft so
// no step can quietly present an object-specific series as a shared source.
function scopeLabel(choice: SourceChoice): string {
  if (choice === "object_specific") return "Solo este objeto";
  if (choice === "generic") return "Fuente generica compartida";
  return "Sin declarar";
}

// A new idempotency key per confirmed attempt: the guard exists so a retry of
// the same click cannot write twice, not so two different intents collapse.
function idempotencyKey(): string {
  const source = globalThis.crypto;
  if (source && typeof source.randomUUID === "function") {
    return `journey-${source.randomUUID()}`;
  }
  return `journey-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function resolutionLabel(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds <= 0) return "Sin resolucion";
  const units: [number, string][] = [
    [86400, "d"],
    [3600, "h"],
    [60, "min"],
  ];
  for (const [size, suffix] of units) {
    if (seconds >= size && seconds % size === 0)
      return `${seconds / size} ${suffix}`;
  }
  return `${seconds} s`;
}

interface RailContext {
  objectName: string;
  scope: string;
  need: string;
  action: string;
}

function JourneyRail({ step, rail }: { step: StepId; rail: RailContext }) {
  return (
    <aside className="journey-rail" aria-label="Contexto del recorrido">
      <dl className="journey-context">
        <dt>Objeto</dt>
        <dd>{rail.objectName}</dd>
        <dt>Alcance</dt>
        <dd>{rail.scope}</dd>
        <dt>Necesidad</dt>
        <dd>{rail.need}</dd>
        <dt>Accion</dt>
        <dd>{rail.action}</dd>
      </dl>
      <ol className="journey-steps" aria-label="Pasos del recorrido">
        {STEPS.map((entry, index) => (
          <li
            key={entry.id}
            aria-current={entry.id === step ? "step" : undefined}
          >
            <span className="journey-step-number">{index + 1}</span>
            <span>{entry.label}</span>
          </li>
        ))}
      </ol>
    </aside>
  );
}

// The rail and the step navigation are the same for every flow, because there
// is only one protected pattern and the flows are its branches, not surfaces
// of their own.
function JourneyShell({
  step,
  rail,
  canAdvance,
  onStep,
  children,
}: {
  step: StepId;
  rail: RailContext;
  canAdvance: boolean;
  onStep: (step: StepId) => void;
  children: ReactNode;
}) {
  const stepIndex = STEPS.findIndex((entry) => entry.id === step);
  return (
    <section className="workspace-view journey-surface">
      <header className="workspace-heading">
        <h1>Recorrido protegido</h1>
        <p>
          Toda mutacion pasa por estos cuatro pasos: no hay atajos desde el
          catalogo ni desde el objeto.
        </p>
      </header>
      <div className="journey-layout">
        <JourneyRail step={step} rail={rail} />
        <div className="journey-step-panel">
          {children}
          <nav className="journey-navigation" aria-label="Pasos">
            <button
              className="secondary-button"
              type="button"
              disabled={stepIndex === 0}
              onClick={() => onStep(STEPS[stepIndex - 1].id)}
            >
              Volver
            </button>
            <button
              type="button"
              disabled={!canAdvance}
              onClick={() => onStep(STEPS[stepIndex + 1].id)}
            >
              Siguiente
            </button>
          </nav>
        </div>
      </div>
    </section>
  );
}

// Chapter 8.7: a refused mutation keeps the draft and says out loud that
// nothing was written, naming the stable code and the request id.
function MutationRefusal({ error }: { error: unknown }) {
  const apiError = error instanceof ApiError ? error : null;
  return (
    <p role="alert" className="result-alert">
      <strong>{apiError?.code ?? "TS_LINK_MUTATION_FAILED"}</strong>{" "}
      {apiError?.message ?? "No se pudo completar la operacion."}
      {apiError?.requestId ? ` (request_id ${apiError.requestId})` : ""} No se
      escribio nada y el borrador se conserva.
    </p>
  );
}

function useObjectName(
  projectId: number | null,
  linkableObjectId: number | null,
): string {
  const context = useQuery({
    queryKey: ["journey-object", projectId, linkableObjectId],
    queryFn: ({ signal }) =>
      getObjectTimeSeriesContext(
        projectId as number,
        linkableObjectId as number,
        {},
        signal,
      ),
    enabled: projectId !== null && linkableObjectId !== null,
    retry: false,
  });
  return context.data?.meta.object.display_name ?? "Sin objeto";
}

// -- The link flow: associate a generic source, or use a revision ---------

interface LinkDraft {
  bindingRoleKey: string;
  sourceChoice: SourceChoice;
  signalId: number | null;
  scenarioId: number | null;
  variantId: number | null;
  reasonText: string;
}

const EMPTY_LINK_DRAFT: LinkDraft = {
  bindingRoleKey: "",
  sourceChoice: "",
  signalId: null,
  scenarioId: null,
  variantId: null,
  reasonText: "",
};

function OriginStep({
  draft,
  intent,
  roles,
  scenarios,
  variants,
  onChange,
}: {
  draft: LinkDraft;
  intent: LinkIntent;
  roles: { key: string; display_name: string }[];
  scenarios: { id: number; name: string }[];
  variants: { id: number; display_name: string }[];
  onChange: (patch: Partial<LinkDraft>) => void;
}) {
  return (
    <section aria-label="Origen y alcance">
      <h2>Origen y alcance</h2>
      <div className="field-row">
        <label htmlFor="journey-role">Necesidad funcional</label>
        <select
          id="journey-role"
          value={draft.bindingRoleKey}
          onChange={(event) => onChange({ bindingRoleKey: event.target.value })}
        >
          <option value="">Elegir necesidad</option>
          {roles.map((role) => (
            <option key={role.key} value={role.key}>
              {role.display_name}
            </option>
          ))}
        </select>
      </div>
      <fieldset className="journey-origin-choice">
        <legend>Origen de la serie</legend>
        {/* AC-SHR-02: the local outcome is always the one offered first. */}
        <label>
          <input
            type="radio"
            name="journey-source-choice"
            value="object_specific"
            checked={draft.sourceChoice === "object_specific"}
            onChange={() => onChange({ sourceChoice: "object_specific" })}
          />
          Crear especifica para este objeto
        </label>
        <label>
          <input
            type="radio"
            name="journey-source-choice"
            value="generic"
            checked={draft.sourceChoice === "generic"}
            onChange={() => onChange({ sourceChoice: "generic" })}
          />
          Reutilizar una fuente generica
        </label>
      </fieldset>
      {intent === "use_revision" ? (
        <>
          <div className="field-row">
            <label htmlFor="journey-scenario">Escenario</label>
            <select
              id="journey-scenario"
              value={draft.scenarioId === null ? "" : String(draft.scenarioId)}
              onChange={(event) =>
                onChange({
                  scenarioId: numericParam(event.target.value),
                  variantId: null,
                })
              }
            >
              <option value="">Elegir escenario</option>
              {scenarios.map((scenario) => (
                <option key={scenario.id} value={String(scenario.id)}>
                  {scenario.name}
                </option>
              ))}
            </select>
          </div>
          <div className="field-row">
            <label htmlFor="journey-variant">Variante</label>
            <select
              id="journey-variant"
              value={draft.variantId === null ? "" : String(draft.variantId)}
              onChange={(event) =>
                onChange({ variantId: numericParam(event.target.value) })
              }
            >
              <option value="">Elegir variante</option>
              {variants.map((variant) => (
                <option key={variant.id} value={String(variant.id)}>
                  {variant.display_name}
                </option>
              ))}
            </select>
          </div>
        </>
      ) : null}
    </section>
  );
}

// Chapter 8.7: an incompatible row is blocked and readable at once - the human
// reason plus the stable code, never one without the other.
function CandidateSelection({
  rows,
  selectedSignalId,
  onSelect,
}: {
  rows: CatalogCandidateRow[];
  selectedSignalId: number | null;
  onSelect: (signalId: number) => void;
}) {
  return (
    <div className="time-series-table-scroll">
      <table>
        <caption>Fuentes genericas candidatas</caption>
        <thead>
          <tr>
            <th scope="col">Elegir</th>
            <th scope="col">Senal</th>
            <th scope="col">Propietario</th>
            <th scope="col">Contrato</th>
            <th scope="col">Compatibilidad</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const decision = row.compatibility_decision;
            return (
              <tr key={row.signal_id}>
                <td>
                  <input
                    type="radio"
                    name="journey-candidate"
                    aria-label={`Elegir ${row.identity.display_name}`}
                    value={String(row.signal_id)}
                    disabled={!decision.allowed}
                    checked={selectedSignalId === row.signal_id}
                    onChange={() => onSelect(row.signal_id)}
                  />
                </td>
                <th scope="row">
                  <span className="catalog-signal-name">
                    {row.identity.display_name}
                  </span>
                  <span className="catalog-series-key">
                    {row.identity.series_key}
                  </span>
                </th>
                <td>
                  {row.owner.project_name} - {row.set.visibility_scope}
                </td>
                <td>
                  {row.classification.semantic_type_key} -{" "}
                  {row.classification.data_class_key} -{" "}
                  {row.classification.unit_key}
                </td>
                <td>
                  {decision.allowed ? (
                    <span>Compatible</span>
                  ) : (
                    <>
                      <strong className="journey-denied">
                        No seleccionable
                      </strong>
                      {decision.errors.map((error) => (
                        <span key={error.code} className="journey-denial">
                          <span>{error.message}</span>
                          <code>{error.code}</code>
                        </span>
                      ))}
                    </>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// AC-BIN-05: a replacement is never a silent overwrite. Source, revision, hash
// and state are shown side by side, and the reason is taken before the review
// step can even be reached.
function ReplacementComparison({
  before,
  detail,
  reasonText,
  onReason,
}: {
  before: CaseBindingRow;
  detail: CatalogInputDetail;
  reasonText: string;
  onReason: (value: string) => void;
}) {
  return (
    <section aria-label="Reemplazo de un uso vigente">
      <h3>Reemplazo de un uso vigente</h3>
      <div className="time-series-table-scroll">
        <table>
          <caption>Comparacion del reemplazo</caption>
          <thead>
            <tr>
              <th scope="col">Dato</th>
              <th scope="col">Antes</th>
              <th scope="col">Despues</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <th scope="row">Fuente</th>
              <td>{before.signal.display_name}</td>
              <td>{detail.identity.display_name}</td>
            </tr>
            <tr>
              <th scope="row">Revision</th>
              <td>Revision fijada {before.revision.id}</td>
              <td>Revision {detail.current_revision.number}</td>
            </tr>
            <tr>
              <th scope="row">Hash</th>
              <td className="catalog-hash">{before.bound_content_hash}</td>
              <td className="catalog-hash">
                {detail.current_revision.content_hash}
              </td>
            </tr>
            <tr>
              <th scope="row">Estado</th>
              <td>{before.state}</td>
              <td>Vigente al confirmar</td>
            </tr>
            <tr>
              <th scope="row">Cobertura</th>
              <td>La revision fijada conserva la cobertura que sello</td>
              <td>
                {detail.coverage_summary.start ?? "Sin inicio"} -{" "}
                {detail.coverage_summary.end ?? "Sin fin"}
              </td>
            </tr>
            <tr>
              <th scope="row">Resolucion</th>
              <td>{before.revision.mode ?? "Sin modo declarado"}</td>
              <td>
                {resolutionLabel(
                  detail.coverage_summary.nominal_resolution_seconds,
                )}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div className="field-row">
        <label htmlFor="journey-reason">Motivo del reemplazo</label>
        <textarea
          id="journey-reason"
          value={reasonText}
          rows={3}
          onChange={(event) => onReason(event.target.value)}
        />
      </div>
      <p>
        El binding anterior no se borra: queda como historia consultable del
        uso.
      </p>
    </section>
  );
}

function DataStep({
  detail,
  intent,
  replacing,
  reasonText,
  onReason,
}: {
  detail: CatalogInputDetail;
  intent: LinkIntent;
  replacing: CaseBindingRow | null;
  reasonText: string;
  onReason: (value: string) => void;
}) {
  return (
    <section aria-label="Datos o revision">
      <h2>Datos o revision ejecutable</h2>
      <p>
        {intent === "associate"
          ? "Asociar deja la fuente disponible para esta necesidad siguiendo la identidad vigente de la senal generica. No activa ninguna variante."
          : "Usar una revision fija revision y hash para ejecutar la variante elegida. El nombre tecnico de ese vinculo es binding de ejecucion."}
      </p>
      <dl className="catalog-definition-list">
        <dt>Fuente</dt>
        <dd>{detail.identity.display_name}</dd>
        <dt>Revision observada</dt>
        <dd>Revision {detail.current_revision.number}</dd>
        <dt>Hash de contenido</dt>
        <dd className="catalog-hash">{detail.current_revision.content_hash}</dd>
        <dt>Cobertura</dt>
        <dd>
          {detail.coverage_summary.start ?? "Sin inicio"} -{" "}
          {detail.coverage_summary.end ?? "Sin fin"}
        </dd>
        <dt>Propietario y alcance</dt>
        <dd>
          {detail.owner.project_name} - {detail.set.visibility_scope}
        </dd>
      </dl>
      {replacing ? (
        <ReplacementComparison
          before={replacing}
          detail={detail}
          reasonText={reasonText}
          onReason={onReason}
        />
      ) : null}
    </section>
  );
}

// Chapter 8.2: both entry points end here. The review is one component, so
// "the same final review" is a fact of the code and not a promise.
function BatchReview({
  facts,
  prevalidation,
  isFetching,
  error,
  commitLabel,
  onCommit,
  commitError,
  commitResult,
  commitPending,
}: {
  facts: { term: string; value: ReactNode }[];
  prevalidation: BatchPrevalidation | undefined;
  isFetching: boolean;
  error: unknown;
  commitLabel: string;
  onCommit: () => void;
  commitError: unknown;
  commitResult: BatchCommitResult | null;
  commitPending: boolean;
}) {
  return (
    <section aria-label="Impacto y confirmacion">
      <h2>Impacto y confirmacion</h2>
      {isFetching ? <p role="status">Recalculando la prevalidacion</p> : null}
      {error ? <MutationRefusal error={error} /> : null}
      {prevalidation && !isFetching ? (
        <>
          <div className="time-series-table-scroll">
            <table>
              <caption>Prevalidacion por fila</caption>
              <thead>
                <tr>
                  <th scope="col">Operacion</th>
                  <th scope="col">Veredicto</th>
                  <th scope="col">Razones</th>
                </tr>
              </thead>
              <tbody>
                {prevalidation.operations.map((operation) => (
                  <tr key={operation.client_operation_id}>
                    <th scope="row">{operation.client_operation_id}</th>
                    <td>
                      <strong>
                        {VERDICT_LABELS[operation.verdict] ?? operation.verdict}
                      </strong>
                    </td>
                    <td>
                      {operation.errors.length === 0
                        ? "Sin observaciones"
                        : operation.errors.map((item) => (
                            <span key={item.code} className="journey-denial">
                              <span>{item.message}</span>
                              <code>{item.code}</code>
                            </span>
                          ))}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <dl className="catalog-definition-list">
            {facts.map((fact) => (
              <Fragment key={fact.term}>
                <dt>{fact.term}</dt>
                <dd>{fact.value}</dd>
              </Fragment>
            ))}
            <dt>Atomicidad</dt>
            <dd>
              El guardado es todo o nada: una fila incompatible bloquea el lote
              completo y no deja exitos parciales.
            </dd>
            <dt>Historia</dt>
            <dd>
              La operacion queda registrada con su lote, actor y motivo, y la
              prevalidacion vence el {prevalidation.expires_at}.
            </dd>
          </dl>
          {commitError ? <MutationRefusal error={commitError} /> : null}
          {commitResult ? (
            <p role="status" className="journey-committed">
              Guardado atomico completo ({commitResult.outcome}) en el lote{" "}
              {commitResult.batch_id}.
            </p>
          ) : (
            <button
              type="button"
              disabled={!prevalidation.can_commit || commitPending}
              onClick={onCommit}
            >
              {commitLabel}
            </button>
          )}
        </>
      ) : null}
    </section>
  );
}

// The facts a link mutation states before it is confirmed.
function linkReviewFacts(
  detail: CatalogInputDetail,
  intent: LinkIntent,
): { term: string; value: ReactNode }[] {
  return [
    {
      term: "Consumidores actuales",
      value: `${detail.link_summary.association_count} asociaciones y ${detail.link_summary.binding_count} bindings de ejecucion`,
    },
    {
      term: "Permisos",
      value: `El servidor reautoriza al confirmar; el alcance observado es ${detail.set.visibility_scope}.`,
    },
    {
      term: "Staleness",
      value:
        intent === "associate"
          ? "Asociar no mueve ningun binding: los usos vigentes conservan su revision fijada."
          : "Solo cambia el uso de esta variante; los demas usos conservan su revision fijada.",
    },
  ];
}

function LinkFlow({
  projectId,
  linkableObjectId,
  intent,
  step,
  onStep,
}: {
  projectId: number | null;
  linkableObjectId: number | null;
  intent: LinkIntent;
  step: StepId;
  onStep: (step: StepId) => void;
}) {
  const [draft, setDraft] = useState<LinkDraft>(EMPTY_LINK_DRAFT);
  const [commitResult, setCommitResult] = useState<BatchCommitResult | null>(
    null,
  );
  const [commitError, setCommitError] = useState<unknown>(null);
  const [commitPending, setCommitPending] = useState(false);

  const objectName = useObjectName(projectId, linkableObjectId);
  const roles = useQuery({
    queryKey: ["catalog-descriptors", "binding_role"],
    queryFn: ({ signal }) => listCatalogDescriptors("binding_role", signal),
    staleTime: 5 * 60_000,
  });
  const scenarios = useQuery({
    queryKey: ["journey-scenarios", projectId],
    queryFn: ({ signal }) => listScenarios(projectId as number, signal),
    enabled: intent === "use_revision" && projectId !== null,
    retry: false,
  });
  const variants = useQuery({
    queryKey: ["journey-variants", draft.scenarioId],
    queryFn: ({ signal }) =>
      listCaseInputVariants(draft.scenarioId as number, signal),
    enabled: intent === "use_revision" && draft.scenarioId !== null,
    retry: false,
  });
  const bindings = useQuery({
    queryKey: ["journey-bindings", draft.scenarioId, draft.variantId],
    queryFn: ({ signal }) =>
      listCaseTimeSeriesBindings(
        draft.scenarioId as number,
        draft.variantId as number,
        signal,
      ),
    enabled:
      intent === "use_revision" &&
      draft.scenarioId !== null &&
      draft.variantId !== null,
    retry: false,
  });
  const candidates = useQuery({
    queryKey: [
      "journey-candidates",
      linkableObjectId,
      draft.bindingRoleKey,
      intent,
      draft.scenarioId,
      draft.variantId,
    ],
    queryFn: ({ signal }) =>
      listCatalogSourcesForObject(
        {
          linkableObjectId: linkableObjectId as number,
          bindingRoleKey: draft.bindingRoleKey,
          usage: intent === "use_revision" ? "execution" : "association",
          scenarioId: draft.scenarioId,
          variantId: draft.variantId,
        },
        signal,
      ),
    enabled:
      linkableObjectId !== null &&
      draft.sourceChoice === "generic" &&
      Boolean(draft.bindingRoleKey) &&
      (intent === "associate" ||
        (draft.scenarioId !== null && draft.variantId !== null)),
    retry: false,
  });
  const detail = useQuery({
    queryKey: ["catalog-input-detail", draft.signalId],
    queryFn: ({ signal }) =>
      getCatalogInputDetail(draft.signalId as number, signal),
    enabled: draft.signalId !== null,
    retry: false,
  });

  // The need already covered in this variant is what turns a create into a
  // replace, so the journey reads it instead of asking the user to know it.
  const replacing =
    intent === "use_revision"
      ? (bindings.data?.items.find(
          (row) =>
            row.binding_role.key === draft.bindingRoleKey &&
            row.status === "active",
        ) ?? null)
      : null;
  const reasonRequired = replacing !== null;

  // Chapter 8.3: the prevalidation belongs to one exact draft. Its key carries
  // the object, the source and the revision, so changing any of them discards
  // the earlier answer instead of confirming against it.
  const prevalidationSignature = [
    projectId,
    linkableObjectId,
    intent,
    draft.bindingRoleKey,
    draft.signalId,
    draft.scenarioId,
    draft.variantId,
    detail.data?.current_revision.id ?? null,
    detail.data?.current_revision.content_hash ?? null,
    bindings.data?.meta.bindings_revision ?? null,
  ].join("|");

  const associationRequest: AssociationBatchRequest | null =
    intent === "associate" &&
    projectId !== null &&
    linkableObjectId !== null &&
    draft.signalId !== null
      ? {
          target_project_id: projectId,
          operations: [
            {
              client_operation_id: `assoc-${draft.signalId}-${draft.bindingRoleKey}`,
              action: "add",
              signal_id: draft.signalId,
              linkable_object_id: linkableObjectId,
              binding_role_key: draft.bindingRoleKey,
              expected_absent: true,
              reason_code: "catalog_association_requested",
            },
          ],
        }
      : null;

  const revision = detail.data
    ? {
        mode: "current" as const,
        revision_id: detail.data.current_revision.id,
        content_hash: detail.data.current_revision.content_hash,
      }
    : null;

  const bindingRequest: BindingBatchRequest | null =
    intent === "use_revision" &&
    linkableObjectId !== null &&
    draft.signalId !== null &&
    revision !== null &&
    bindings.data !== undefined
      ? {
          expected_bindings_revision: bindings.data.meta.bindings_revision,
          operations: [
            replacing
              ? {
                  client_operation_id: `bind-${draft.signalId}-${draft.bindingRoleKey}`,
                  action: "replace",
                  binding_id: replacing.binding_id,
                  expected_lifecycle_revision: replacing.lifecycle_revision,
                  linkable_object_id: linkableObjectId,
                  binding_role_key: draft.bindingRoleKey,
                  signal_id: draft.signalId,
                  revision,
                  catalog_association_id: replacing.catalog_association_id,
                  reason_code: "new_source_revision_accepted",
                  reason_text: draft.reasonText.trim(),
                }
              : {
                  client_operation_id: `bind-${draft.signalId}-${draft.bindingRoleKey}`,
                  action: "create",
                  linkable_object_id: linkableObjectId,
                  binding_role_key: draft.bindingRoleKey,
                  signal_id: draft.signalId,
                  revision,
                  catalog_association_id: null,
                  reason_code: "variant_input_selected",
                },
          ],
        }
      : null;

  const hasRequest =
    intent === "associate"
      ? associationRequest !== null
      : bindingRequest !== null;

  const prevalidation = useQuery({
    queryKey: ["journey-prevalidation", prevalidationSignature],
    queryFn: () =>
      intent === "associate"
        ? prevalidateCatalogAssociations(
            associationRequest as AssociationBatchRequest,
          )
        : prevalidateCaseBindings(
            draft.scenarioId as number,
            draft.variantId as number,
            bindingRequest as BindingBatchRequest,
          ),
    enabled: step === "impact" && hasRequest && detail.data !== undefined,
    retry: false,
    gcTime: 0,
  });

  async function commit() {
    if (!prevalidation.data) return;
    const guards = {
      prevalidationToken: prevalidation.data.prevalidation_token,
      commitEtag: prevalidation.data.commit_etag,
      idempotencyKey: idempotencyKey(),
    };
    setCommitPending(true);
    setCommitError(null);
    try {
      setCommitResult(
        intent === "associate"
          ? await commitCatalogAssociations(
              associationRequest as AssociationBatchRequest,
              guards,
            )
          : await commitCaseBindings(
              draft.scenarioId as number,
              draft.variantId as number,
              bindingRequest as BindingBatchRequest,
              guards,
            ),
      );
    } catch (error) {
      setCommitError(error);
    } finally {
      setCommitPending(false);
    }
  }

  function update(patch: Partial<LinkDraft>) {
    setDraft((current) => ({ ...current, ...patch }));
    // A changed draft can never keep an answer computed for the old one.
    setCommitResult(null);
    setCommitError(null);
  }

  const originComplete =
    Boolean(draft.bindingRoleKey && draft.sourceChoice) &&
    (intent === "associate" ||
      (draft.scenarioId !== null && draft.variantId !== null));
  const canAdvance =
    step === "origin"
      ? originComplete
      : step === "selection"
        ? draft.signalId !== null
        : step === "data"
          ? detail.data !== undefined &&
            (!reasonRequired || draft.reasonText.trim().length > 0)
          : false;

  return (
    <JourneyShell
      step={step}
      canAdvance={canAdvance}
      onStep={onStep}
      rail={{
        objectName,
        scope: scopeLabel(draft.sourceChoice),
        need: draft.bindingRoleKey || "Sin declarar",
        action: INTENT_ACTIONS[intent],
      }}
    >
      {step === "origin" ? (
        <OriginStep
          draft={draft}
          intent={intent}
          roles={roles.data?.items ?? []}
          scenarios={scenarios.data ?? []}
          variants={(variants.data?.variants ?? []).map(
            (entry) => entry.variant,
          )}
          onChange={update}
        />
      ) : null}
      {step === "selection" ? (
        <section aria-label="Definicion o seleccion">
          <h2>Definicion o seleccion</h2>
          {draft.sourceChoice === "generic" ? (
            <>
              {candidates.isPending ? (
                <p role="status">Buscando fuentes compatibles</p>
              ) : null}
              {candidates.data ? (
                <CandidateSelection
                  rows={candidates.data.items}
                  selectedSignalId={draft.signalId}
                  onSelect={(signalId) => update({ signalId })}
                />
              ) : null}
            </>
          ) : null}
        </section>
      ) : null}
      {step === "data" && detail.data ? (
        <DataStep
          detail={detail.data}
          intent={intent}
          replacing={replacing}
          reasonText={draft.reasonText}
          onReason={(reasonText) => update({ reasonText })}
        />
      ) : null}
      {step === "impact" && detail.data ? (
        <BatchReview
          facts={linkReviewFacts(detail.data, intent)}
          prevalidation={prevalidation.data}
          isFetching={prevalidation.isFetching}
          error={prevalidation.isError ? prevalidation.error : null}
          commitLabel={INTENT_ACTIONS[intent]}
          onCommit={commit}
          commitError={commitError}
          commitResult={commitResult}
          commitPending={commitPending}
        />
      ) : null}
    </JourneyShell>
  );
}

// -- The shared-source flow: chapter 8.6 ---------------------------------

function plural(count: number, singular: string, many: string): string {
  return `${count} ${count === 1 ? singular : many}`;
}

function SharedImpactSummary({ impact }: { impact: SharedSourceImpact }) {
  return (
    <section aria-label="Impacto de la fuente compartida">
      <h3>Que hay del otro lado de esta fuente</h3>
      <dl className="catalog-definition-list">
        <dt>Alcance y propietario</dt>
        <dd>
          {impact.source.visibility_scope ?? "Sin alcance"} -{" "}
          {impact.source.owner_project_name ?? "Sin propietario"}
        </dd>
        <dt>Revision vigente</dt>
        <dd>
          Revision {impact.source.current_revision_number ?? "?"} -{" "}
          <span className="catalog-hash">
            {impact.source.current_content_hash ?? "Sin hash"}
          </span>
        </dd>
        <dt>Asociaciones</dt>
        <dd>
          {plural(impact.associations.total, "asociacion", "asociaciones")} en
          total, en{" "}
          {plural(
            impact.associations.other_objects,
            "objeto distinto",
            "objetos distintos",
          )}{" "}
          ademas de este.
        </dd>
        <dt>Proyectos y variantes</dt>
        <dd>
          {plural(impact.bindings.projects_affected, "proyecto", "proyectos")} y{" "}
          {plural(impact.bindings.variants_affected, "variante", "variantes")}{" "}
          usan esta fuente hoy.
        </dd>
        <dt>Efecto de publicar</dt>
        <dd>
          {impact.effect.bindings_will_become_stale === 1
            ? "1 binding quedara obsoleto"
            : `${impact.effect.bindings_will_become_stale} bindings quedaran obsoletos`}{" "}
          y la publicacion no los resuelve: quedan visibles para decidirlos
          despues.
        </dd>
      </dl>
      <div className="time-series-table-scroll">
        <table>
          <caption>Muestra de consumidores</caption>
          <thead>
            <tr>
              <th scope="col">Objeto</th>
              <th scope="col">Proyecto</th>
              <th scope="col">Relacion</th>
            </tr>
          </thead>
          <tbody>
            {impact.listed_consumers.map((consumer) => (
              <tr key={consumer.linkable_object_id}>
                <th scope="row">{consumer.linkable_object_id}</th>
                <td>{consumer.project_id}</td>
                <td>{consumer.relation}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {impact.consumers_truncated ? (
        <p>
          La muestra esta recortada; la lista completa se consulta en el
          catalogo de asociaciones.
        </p>
      ) : null}
    </section>
  );
}

// One point per line: instante ISO, duracion en segundos y valor. The parser
// is deliberately strict, because a silently dropped row would publish a
// revision nobody reviewed.
function parsePoints(
  text: string,
  seriesKey: string,
): { points: IngestionPoint[]; errors: string[] } {
  const points: IngestionPoint[] = [];
  const errors: string[] = [];
  text
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line.length > 0)
    .forEach((line, index) => {
      const parts = line.split(",").map((part) => part.trim());
      if (parts.length !== 3) {
        errors.push(`Linea ${index + 1}: se esperaban tres columnas.`);
        return;
      }
      const duration = Number(parts[1]);
      const value = Number(parts[2]);
      if (!Number.isFinite(duration) || duration <= 0) {
        errors.push(`Linea ${index + 1}: duracion invalida.`);
        return;
      }
      if (!Number.isFinite(value)) {
        errors.push(`Linea ${index + 1}: valor invalido.`);
        return;
      }
      points.push({
        timestamp_start: parts[0],
        duration_seconds: duration,
        values: { [seriesKey]: { value } },
      });
    });
  return { points, errors };
}

interface SharedDraft {
  declaredIntent: "" | "local" | "shared";
  alternativeKind: "" | "derive_object_specific" | "publish_shared";
  pointsText: string;
  localSeriesKey: string;
  localDisplayName: string;
  reasonText: string;
  comprehension: boolean;
}

const EMPTY_SHARED_DRAFT: SharedDraft = {
  declaredIntent: "",
  alternativeKind: "",
  pointsText: "",
  localSeriesKey: "",
  localDisplayName: "",
  reasonText: "",
  comprehension: false,
};

function SharedSourceFlow({
  target,
  step,
  onStep,
}: {
  target: SharedSourceTarget;
  step: StepId;
  onStep: (step: StepId) => void;
}) {
  const [draft, setDraft] = useState<SharedDraft>(EMPTY_SHARED_DRAFT);
  const [ingestion, setIngestion] = useState<IngestionReceipt | null>(null);
  const [derivation, setDerivation] =
    useState<ObjectSeriesDerivationPrevalidation | null>(null);
  const [stepError, setStepError] = useState<unknown>(null);
  const [commitError, setCommitError] = useState<unknown>(null);
  const [committed, setCommitted] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  const objectName = useObjectName(target.projectId, target.linkableObjectId);
  const view = useQuery({
    queryKey: [
      "journey-association",
      target.associationId,
      draft.declaredIntent,
    ],
    queryFn: ({ signal }) =>
      getObjectCatalogAssociation(
        target,
        draft.declaredIntent === "local" ? "local" : "shared",
        signal,
      ),
    enabled: draft.declaredIntent !== "",
    retry: false,
  });

  function update(patch: Partial<SharedDraft>) {
    setDraft((current) => ({ ...current, ...patch }));
    // Chapter 8.6 step 6: any change from the preview invalidates what was
    // previewed, so the prepared revision and its fingerprint are dropped.
    setIngestion(null);
    setDerivation(null);
    setCommitError(null);
    setCommitted(null);
  }

  const association = view.data?.association;
  const seriesKey = association?.series_key ?? "";
  const parsed = parsePoints(draft.pointsText, seriesKey);

  async function prepare() {
    if (!view.data) return;
    setPending(true);
    setStepError(null);
    try {
      if (draft.alternativeKind === "publish_shared") {
        setIngestion(
          await prepareSharedSeriesIngestion(target, {
            mode: "replace_full",
            expected_base: {
              revision_id: view.data.impact.source
                .current_revision_id as number,
              content_hash: view.data.impact.source
                .current_content_hash as string,
            },
            source: { kind: "api", display_name: "Recorrido protegido" },
            points: parsed.points,
          }),
        );
      } else {
        setDerivation(
          await prevalidateObjectSeriesDerivation(target, {
            object_series_key: draft.localSeriesKey.trim(),
            display_name: draft.localDisplayName.trim(),
            reason_code: "local_copy_preferred",
            reason_text: draft.reasonText.trim() || "Copia local del objeto",
          }),
        );
      }
    } catch (error) {
      setStepError(error);
    } finally {
      setPending(false);
    }
  }

  async function confirm() {
    if (!view.data) return;
    setPending(true);
    setCommitError(null);
    try {
      if (draft.alternativeKind === "publish_shared" && ingestion) {
        const publication = await publishSharedSeriesIngestion(
          target,
          ingestion.ingestion_id,
          {
            validation_token: ingestion.validation_token as string,
            impact_fingerprint: ingestion.impact_fingerprint as string,
            confirm: true,
            comprehension_acknowledged: draft.comprehension,
            reason_code: "shared_revision_published",
            reason_text: draft.reasonText.trim(),
          },
          {
            prevalidationToken: ingestion.validation_token as string,
            commitEtag: ingestion.etag as string,
            idempotencyKey: idempotencyKey(),
          },
        );
        setCommitted(String(publication.outcome ?? "published"));
      } else if (derivation) {
        const result = await commitObjectSeriesDerivation(
          target,
          {
            object_series_key: draft.localSeriesKey.trim(),
            display_name: draft.localDisplayName.trim(),
            reason_code: "local_copy_preferred",
            reason_text: draft.reasonText.trim() || "Copia local del objeto",
            prevalidation_token: derivation.prevalidation_token,
            confirmed: true,
            source_revision: {
              revision_id: derivation.source.revision_id,
              content_hash: derivation.source.content_hash,
            },
          },
          idempotencyKey(),
        );
        setCommitted(String(result.outcome ?? "created"));
      }
    } catch (error) {
      setCommitError(error);
    } finally {
      setPending(false);
    }
  }

  const local = draft.alternativeKind === "derive_object_specific";
  const shared = draft.alternativeKind === "publish_shared";
  const actionLabel = local
    ? ALTERNATIVE_LABELS.create_specific_for_this_object
    : shared
      ? ALTERNATIVE_LABELS.publish_for_everyone
      : "Fuente compartida del objeto";

  const dataReady = shared
    ? ingestion !== null && ingestion.capabilities.publish === true
    : derivation !== null && derivation.can_commit;
  const canAdvance =
    step === "origin"
      ? draft.declaredIntent !== ""
      : step === "selection"
        ? draft.alternativeKind !== ""
        : step === "data"
          ? dataReady
          : false;
  const mayConfirm =
    draft.reasonText.trim().length > 0 && (!shared || draft.comprehension);

  return (
    <JourneyShell
      step={step}
      canAdvance={canAdvance}
      onStep={onStep}
      rail={{
        objectName,
        // The source is shared before any branch is taken; only choosing the
        // local outcome narrows the scope, and the rail says so from step one.
        scope: local ? "Solo este objeto" : scopeLabel("generic"),
        need: association?.binding_role_key ?? "Sin declarar",
        action: actionLabel,
      }}
    >
      {step === "origin" ? (
        <section aria-label="Origen y alcance">
          <h2>Origen y alcance</h2>
          <p>
            Esta fuente es compartida. Antes de tocarla, declara para quien es
            el cambio: la respuesta ordena las alternativas del paso siguiente.
          </p>
          <fieldset className="journey-origin-choice">
            <legend>Para quien es el cambio</legend>
            <label>
              <input
                type="radio"
                name="journey-declared-intent"
                value="local"
                checked={draft.declaredIntent === "local"}
                onChange={() => update({ declaredIntent: "local" })}
              />
              Solo este objeto necesita otra curva
            </label>
            <label>
              <input
                type="radio"
                name="journey-declared-intent"
                value="shared"
                checked={draft.declaredIntent === "shared"}
                onChange={() => update({ declaredIntent: "shared" })}
              />
              Todos los consumidores deben ver la curva nueva
            </label>
          </fieldset>
        </section>
      ) : null}

      {step === "selection" ? (
        <section aria-label="Definicion o seleccion">
          <h2>Definicion o seleccion</h2>
          {view.isPending ? <p role="status">Leyendo el impacto</p> : null}
          {view.isError ? <MutationRefusal error={view.error} /> : null}
          {view.data ? (
            <>
              <SharedImpactSummary impact={view.data.impact} />
              <fieldset
                className="journey-origin-choice"
                aria-label="Como seguir con la fuente compartida"
              >
                <legend>Como seguir con la fuente compartida</legend>
                {view.data.alternatives.map((alternative) => (
                  <SharedAlternativeChoice
                    key={alternative.kind}
                    alternative={alternative}
                    checked={draft.alternativeKind === alternative.kind}
                    onSelect={() =>
                      update({ alternativeKind: alternative.kind })
                    }
                  />
                ))}
              </fieldset>
            </>
          ) : null}
        </section>
      ) : null}

      {step === "data" ? (
        <section aria-label="Datos o revision">
          <h2>Datos o revision ejecutable</h2>
          {shared ? (
            <>
              <div className="field-row">
                <label htmlFor="journey-points">
                  Puntos (instante, duracion en segundos, valor)
                </label>
                <textarea
                  id="journey-points"
                  rows={6}
                  value={draft.pointsText}
                  onChange={(event) =>
                    update({ pointsText: event.target.value })
                  }
                />
              </div>
              {parsed.errors.map((message) => (
                <p key={message} role="alert" className="result-alert">
                  {message}
                </p>
              ))}
              <button
                type="button"
                disabled={parsed.points.length === 0 || pending}
                onClick={prepare}
              >
                Preparar y previsualizar
              </button>
            </>
          ) : (
            <>
              <p>
                La copia local conserva el linaje de la fuente y no reasigna
                asociaciones ni bindings. Solo este objeto la vera.
              </p>
              <div className="field-row">
                <label htmlFor="journey-local-key">Clave de la serie</label>
                <input
                  id="journey-local-key"
                  type="text"
                  value={draft.localSeriesKey}
                  onChange={(event) =>
                    update({ localSeriesKey: event.target.value })
                  }
                />
              </div>
              <div className="field-row">
                <label htmlFor="journey-local-name">Nombre visible</label>
                <input
                  id="journey-local-name"
                  type="text"
                  value={draft.localDisplayName}
                  onChange={(event) =>
                    update({ localDisplayName: event.target.value })
                  }
                />
              </div>
              <button
                type="button"
                disabled={
                  !draft.localSeriesKey.trim() ||
                  !draft.localDisplayName.trim() ||
                  pending
                }
                onClick={prepare}
              >
                Prevalidar la copia local
              </button>
            </>
          )}
          {stepError ? <MutationRefusal error={stepError} /> : null}
          {ingestion ? (
            <dl className="catalog-definition-list">
              <dt>Preview de la revision preparada</dt>
              <dd>
                {ingestion.normalized.coverage_start ?? "Sin inicio"} -{" "}
                {ingestion.normalized.coverage_end ?? "Sin fin"}
              </dd>
              <dt>Hash propuesto</dt>
              <dd className="catalog-hash">
                {ingestion.normalized.content_hash ?? "Sin hash"}
              </dd>
              <dt>Validacion</dt>
              <dd>
                {ingestion.validation.valid
                  ? "Sin errores"
                  : `${ingestion.validation.error_count} errores`}
              </dd>
            </dl>
          ) : null}
          {derivation ? (
            <dl className="catalog-definition-list">
              <dt>Revision de origen</dt>
              <dd className="catalog-hash">{derivation.source.content_hash}</dd>
              <dt>Periodos copiados</dt>
              <dd>{derivation.proposed.period_count}</dd>
              <dt>Reasignaciones</dt>
              <dd>
                {derivation.reassignments.associations} asociaciones y{" "}
                {derivation.reassignments.bindings} bindings: ninguna se mueve.
              </dd>
            </dl>
          ) : null}
        </section>
      ) : null}

      {step === "impact" && view.data ? (
        <section aria-label="Impacto y confirmacion">
          <h2>Impacto y confirmacion</h2>
          <SharedImpactSummary impact={view.data.impact} />
          <div className="field-row">
            <label htmlFor="journey-shared-reason">Motivo</label>
            <textarea
              id="journey-shared-reason"
              rows={3}
              value={draft.reasonText}
              onChange={(event) =>
                setDraft((current) => ({
                  ...current,
                  reasonText: event.target.value,
                }))
              }
            />
          </div>
          {shared ? (
            <label className="journey-comprehension">
              <input
                type="checkbox"
                checked={draft.comprehension}
                onChange={(event) =>
                  setDraft((current) => ({
                    ...current,
                    comprehension: event.target.checked,
                  }))
                }
              />
              Entiendo que esta revision la veran todos los consumidores de la
              fuente y que los usos vigentes quedaran obsoletos.
            </label>
          ) : null}
          {commitError ? <MutationRefusal error={commitError} /> : null}
          {committed ? (
            <p role="status" className="journey-committed">
              Operacion completa ({committed}).
            </p>
          ) : (
            <button
              type="button"
              disabled={!mayConfirm || pending || !dataReady}
              onClick={confirm}
            >
              {actionLabel}
            </button>
          )}
        </section>
      ) : null}
    </JourneyShell>
  );
}

function SharedAlternativeChoice({
  alternative,
  checked,
  onSelect,
}: {
  alternative: SharedSourceAlternative;
  checked: boolean;
  onSelect: () => void;
}) {
  const label =
    ALTERNATIVE_LABELS[alternative.label_key] ?? alternative.label_key;
  return (
    <label>
      <input
        type="radio"
        name="journey-shared-alternative"
        value={alternative.kind}
        checked={checked}
        disabled={!alternative.available}
        onChange={onSelect}
      />
      {label}
      {alternative.available ? null : (
        <span className="journey-denial">
          <code>{alternative.unavailable_code}</code>
        </span>
      )}
    </label>
  );
}

// -- The catalog entry point: one generic signal, many objects -----------
//
// Chapter 8.2: the reverse path. It converges on the same prevalidation and
// the same review, and it is where a real bulk operation lives, because one
// signal can cover the same need on many objects at once.

function ObjectCandidateSelection({
  rows,
  selected,
  onToggle,
}: {
  rows: ObjectCandidateRow[];
  selected: number[];
  onToggle: (objectId: number) => void;
}) {
  return (
    <div className="time-series-table-scroll">
      <table>
        <caption>Objetos candidatos</caption>
        <thead>
          <tr>
            <th scope="col">Elegir</th>
            <th scope="col">Objeto</th>
            <th scope="col">Tipo</th>
            <th scope="col">Compatibilidad</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const decision = row.compatibility_decision;
            return (
              <tr key={row.object.id}>
                <td>
                  <input
                    type="checkbox"
                    aria-label={`Elegir ${row.object.display_name}`}
                    value={String(row.object.id)}
                    disabled={!row.selectable}
                    checked={selected.includes(row.object.id)}
                    onChange={() => onToggle(row.object.id)}
                  />
                </td>
                <th scope="row">{row.object.display_name}</th>
                <td>{row.object.object_type_key}</td>
                <td>
                  {decision.allowed ? (
                    <span>Compatible</span>
                  ) : (
                    <>
                      <strong className="journey-denied">
                        No seleccionable
                      </strong>
                      {decision.errors.map((error) => (
                        <span key={error.code} className="journey-denial">
                          <span>{error.message}</span>
                          <code>{error.code}</code>
                        </span>
                      ))}
                    </>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function CatalogFlow({
  signalId,
  projectId,
  step,
  onStep,
}: {
  signalId: number;
  projectId: number;
  step: StepId;
  onStep: (step: StepId) => void;
}) {
  const [bindingRoleKey, setBindingRoleKey] = useState("");
  const [selected, setSelected] = useState<number[]>([]);
  const [commitResult, setCommitResult] = useState<BatchCommitResult | null>(
    null,
  );
  const [commitError, setCommitError] = useState<unknown>(null);
  const [commitPending, setCommitPending] = useState(false);

  const roles = useQuery({
    queryKey: ["catalog-descriptors", "binding_role"],
    queryFn: ({ signal }) => listCatalogDescriptors("binding_role", signal),
    staleTime: 5 * 60_000,
  });
  const detail = useQuery({
    queryKey: ["catalog-input-detail", signalId],
    queryFn: ({ signal }) => getCatalogInputDetail(signalId, signal),
    retry: false,
  });
  const candidates = useQuery({
    queryKey: [
      "journey-object-candidates",
      signalId,
      projectId,
      bindingRoleKey,
    ],
    queryFn: ({ signal }) =>
      listObjectCandidatesForSignal(
        signalId,
        {
          targetProjectId: projectId,
          bindingRoleKey,
          usage: "association",
        },
        signal,
      ),
    enabled: Boolean(bindingRoleKey),
    retry: false,
  });

  const request: AssociationBatchRequest | null =
    selected.length > 0
      ? {
          target_project_id: projectId,
          operations: selected.map((objectId) => ({
            client_operation_id: `assoc-${signalId}-${objectId}-${bindingRoleKey}`,
            action: "add" as const,
            signal_id: signalId,
            linkable_object_id: objectId,
            binding_role_key: bindingRoleKey,
            expected_absent: true,
            reason_code: "catalog_association_requested",
          })),
        }
      : null;

  const prevalidationSignature = [
    projectId,
    signalId,
    bindingRoleKey,
    selected.join(","),
    detail.data?.current_revision.id ?? null,
    detail.data?.current_revision.content_hash ?? null,
  ].join("|");

  const prevalidation = useQuery({
    queryKey: ["journey-prevalidation", prevalidationSignature],
    queryFn: () =>
      prevalidateCatalogAssociations(request as AssociationBatchRequest),
    enabled: step === "impact" && request !== null && detail.data !== undefined,
    retry: false,
    gcTime: 0,
  });

  async function commit() {
    if (!request || !prevalidation.data) return;
    setCommitPending(true);
    setCommitError(null);
    try {
      setCommitResult(
        await commitCatalogAssociations(request, {
          prevalidationToken: prevalidation.data.prevalidation_token,
          commitEtag: prevalidation.data.commit_etag,
          idempotencyKey: idempotencyKey(),
        }),
      );
    } catch (error) {
      setCommitError(error);
    } finally {
      setCommitPending(false);
    }
  }

  function toggle(objectId: number) {
    setSelected((current) =>
      current.includes(objectId)
        ? current.filter((id) => id !== objectId)
        : [...current, objectId].sort((left, right) => left - right),
    );
    setCommitResult(null);
    setCommitError(null);
  }

  const canAdvance =
    step === "origin"
      ? Boolean(bindingRoleKey)
      : step === "selection"
        ? selected.length > 0
        : step === "data"
          ? detail.data !== undefined
          : false;

  return (
    <JourneyShell
      step={step}
      canAdvance={canAdvance}
      onStep={onStep}
      rail={{
        objectName:
          selected.length === 0
            ? "Sin objetos elegidos"
            : `${selected.length} objetos elegidos`,
        scope: "Fuente generica compartida",
        need: bindingRoleKey || "Sin declarar",
        action: INTENT_ACTIONS.associate,
      }}
    >
      {step === "origin" ? (
        <section aria-label="Origen y alcance">
          <h2>Origen y alcance</h2>
          <p>
            Vienes del catalogo con una fuente generica ya elegida. Declara la
            necesidad que cubrira en los objetos del proyecto.
          </p>
          <dl className="catalog-definition-list">
            <dt>Fuente</dt>
            <dd>{detail.data?.identity.display_name ?? "Cargando"}</dd>
            <dt>Alcance</dt>
            <dd>Fuente generica compartida</dd>
          </dl>
          <div className="field-row">
            <label htmlFor="journey-role">Necesidad funcional</label>
            <select
              id="journey-role"
              value={bindingRoleKey}
              onChange={(event) => {
                setBindingRoleKey(event.target.value);
                setSelected([]);
              }}
            >
              <option value="">Elegir necesidad</option>
              {(roles.data?.items ?? []).map((role) => (
                <option key={role.key} value={role.key}>
                  {role.display_name}
                </option>
              ))}
            </select>
          </div>
        </section>
      ) : null}
      {step === "selection" ? (
        <section aria-label="Definicion o seleccion">
          <h2>Definicion o seleccion</h2>
          {candidates.isPending ? (
            <p role="status">Buscando objetos compatibles</p>
          ) : null}
          {candidates.isError ? (
            <MutationRefusal error={candidates.error} />
          ) : null}
          {candidates.data ? (
            <ObjectCandidateSelection
              rows={candidates.data.items}
              selected={selected}
              onToggle={toggle}
            />
          ) : null}
        </section>
      ) : null}
      {step === "data" && detail.data ? (
        <DataStep
          detail={detail.data}
          intent="associate"
          replacing={null}
          reasonText=""
          onReason={() => undefined}
        />
      ) : null}
      {step === "impact" && detail.data ? (
        <BatchReview
          facts={[
            ...linkReviewFacts(detail.data, "associate"),
            {
              term: "Filas del lote",
              value: `${selected.length} objetos en una sola transaccion`,
            },
          ]}
          prevalidation={prevalidation.data}
          isFetching={prevalidation.isFetching}
          error={prevalidation.isError ? prevalidation.error : null}
          commitLabel={INTENT_ACTIONS.associate}
          onCommit={commit}
          commitError={commitError}
          commitResult={commitResult}
          commitPending={commitPending}
        />
      ) : null}
    </JourneyShell>
  );
}

export function ProtectedMutationJourneyView() {
  const [params] = useSearchParams();
  const projectId = numericParam(params.get("project_id"));
  const linkableObjectId = numericParam(params.get("object_id"));
  const associationId = numericParam(params.get("association_id"));
  const rawIntent = params.get("intent");
  const [step, setStep] = useState<StepId>("origin");

  const signalId = numericParam(params.get("signal_id"));
  if (
    params.get("entry") === "catalog" &&
    signalId !== null &&
    projectId !== null
  ) {
    return (
      <CatalogFlow
        signalId={signalId}
        projectId={projectId}
        step={step}
        onStep={setStep}
      />
    );
  }

  if (
    rawIntent === "update_shared" &&
    projectId !== null &&
    linkableObjectId !== null &&
    associationId !== null
  ) {
    return (
      <SharedSourceFlow
        target={{ projectId, linkableObjectId, associationId }}
        step={step}
        onStep={setStep}
      />
    );
  }

  return (
    <LinkFlow
      projectId={projectId}
      linkableObjectId={linkableObjectId}
      intent={rawIntent === "use_revision" ? "use_revision" : "associate"}
      step={step}
      onStep={setStep}
    />
  );
}
