import { useEffect, useRef, useState, type RefObject } from "react";
import { useBlocker } from "react-router-dom";
import { createPortal } from "react-dom";
import { useQuery } from "@tanstack/react-query";
import { ApiError, getCsrfToken, requestJson } from "./api/client";
import type { components } from "./api/schema";

type Context = components["schemas"]["MesaEditContext"];
type MesaContext = components["schemas"]["MesaContext"];
type Series = components["schemas"]["MesaSeries"];
type Props = {
  context: MesaContext;
  objectId: number;
  series: Series;
  onClose: () => void;
  onSaved: () => void;
};

function EditForm({
  data: initial,
  target,
  context,
  onSaved,
  onClose,
  closeRequestRef,
}: {
  data: Context;
  target: string;
  context: MesaContext;
  onSaved: () => void;
  onClose: () => void;
  closeRequestRef: RefObject<() => void>;
}) {
  const [data, setData] = useState(initial);
  const points = data.series.points ?? [];
  const [values, setValues] = useState(points.map((p) => String(p.value)));
  const [reason, setReason] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [conflict, setConflict] = useState(false);
  const [latest, setLatest] = useState<Context | null>(null);
  const [leaving, setLeaving] = useState(false);
  const continueButton = useRef<HTMLButtonElement>(null);
  const dirty = values.some((v, i) => v !== String(points[i].value));
  const invalid = values.some((v) => !v.trim() || !Number.isFinite(Number(v)));
  const blocker = useBlocker(dirty || pending);
  const showLeave = leaving || blocker.state === "blocked";
  useEffect(() => {
    closeRequestRef.current = () => {
      if (dirty || pending) setLeaving(true);
      else onClose();
    };
    const warn = (event: BeforeUnloadEvent) => {
      if (dirty || pending) event.preventDefault();
    };
    window.addEventListener("beforeunload", warn);
    return () => {
      window.removeEventListener("beforeunload", warn);
      closeRequestRef.current = onClose;
    };
  }, [dirty, pending, onClose, closeRequestRef]);
  useEffect(() => {
    if (showLeave) continueButton.current?.focus();
  }, [showLeave]);
  return (
    <form
      onSubmit={async (event) => {
        event.preventDefault();
        if (!dirty || invalid || pending || !confirmed) return;
        setPending(true);
        setError("");
        try {
          await requestJson(`${target}/revisions`, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              "X-CSRF-Token": await getCsrfToken(),
            },
            body: JSON.stringify({
              case_id: context.case_id,
              variant_id: context.variant_id,
              expected: data.expected,
              unit: data.series.unit,
              points: points.map((p, i) => ({
                ...p,
                value: Number(values[i]),
              })),
              confirm: confirmed,
              reason,
            }),
          });
          onSaved();
        } catch (caught) {
          setError(
            caught instanceof Error ? caught.message : "No se pudo guardar.",
          );
          setConflict(caught instanceof ApiError && caught.status === 409);
        } finally {
          setPending(false);
        }
      }}
    >
      <p>{data.scope_message}</p>
      <p>
        Revisión {data.series.revision_number} · {data.actor} · Zona:{" "}
        {data.series.timezone}
      </p>
      <p>Se edita la revisión completa. Inicio, fin y unidad se conservan.</p>
      {typeof data.validation_rules.minimum === "number" && (
        <p>
          Mínimo permitido: {data.validation_rules.minimum} {data.series.unit}
        </p>
      )}
      {typeof data.validation_rules.maximum === "number" && (
        <p>
          Máximo permitido: {data.validation_rules.maximum} {data.series.unit}
        </p>
      )}
      <div
        className="mesa-input-table mesa-table-scroll"
        tabIndex={0}
        role="region"
        aria-label="Valores editables"
      >
        <table>
          <thead>
            <tr>
              <th>Inicio</th>
              <th>Fin (exclusivo)</th>
              <th>Valor ({data.series.unit})</th>
            </tr>
          </thead>
          <tbody>
            {points.map((point, index) => (
              <tr key={point.start}>
                <td>{point.start}</td>
                <td>{point.end}</td>
                <td>
                  <input
                    aria-label={`Valor del intervalo ${index + 1} (${data.series.unit})`}
                    type="text"
                    inputMode="decimal"
                    required
                    disabled={pending}
                    value={values[index]}
                    onChange={(event) =>
                      setValues(
                        values.map((v, i) =>
                          i === index ? event.target.value : v,
                        ),
                      )
                    }
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p role="status">{dirty ? "Cambios pendientes" : "Sin cambios"}</p>
      {invalid && (
        <p role="alert">Ingresa un número finito en cada intervalo.</p>
      )}
      {error && <p role="alert">{error}</p>}
      {conflict && (
        <button
          type="button"
          disabled={pending}
          onClick={async () => {
            setPending(true);
            try {
              setLatest(
                await requestJson<Context>(
                  `${target}?case_id=${context.case_id}&variant_id=${context.variant_id}`,
                ),
              );
            } catch (caught) {
              setError(
                caught instanceof Error
                  ? caught.message
                  : "No se pudo recargar.",
              );
            } finally {
              setPending(false);
            }
          }}
        >
          Recargar y comparar
        </button>
      )}
      {latest && (
        <>
          <p>
            Revisión actual {latest.series.revision_number} · {latest.actor}. Tu
            borrador se conserva hasta elegir la revisión actual.
          </p>
          <div
            className="mesa-input-table mesa-table-scroll"
            tabIndex={0}
            role="region"
            aria-label="Diferencias de valores"
          >
            <table aria-label="Comparación de revisiones">
              <thead>
                <tr>
                  <th>Inicio</th>
                  <th>Original</th>
                  <th>Tu borrador</th>
                  <th>Actual</th>
                </tr>
              </thead>
              <tbody>
                {points.map((point, i) => (
                  <tr key={point.start}>
                    <td>{point.start}</td>
                    <td>{point.value}</td>
                    <td>{values[i]}</td>
                    <td>
                      {latest.series.points?.find(
                        (p) => p.start === point.start && p.end === point.end,
                      )?.value ?? "Intervalo diferente"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <button
            type="button"
            onClick={() => {
              setData(latest);
              setValues(
                (latest.series.points ?? []).map((p) => String(p.value)),
              );
              setLatest(null);
              setConflict(false);
              setError("");
              setConfirmed(false);
              setReason("");
            }}
          >
            Usar revisión actual
          </button>
        </>
      )}
      {showLeave && (
        <div role="alert">
          <p>
            {pending
              ? "Espera a que termine el guardado."
              : "Hay cambios sin guardar."}
          </p>
          <button
            type="button"
            ref={continueButton}
            onClick={() => {
              setLeaving(false);
              blocker.reset?.();
            }}
          >
            Seguir editando
          </button>
          <button
            type="button"
            disabled={pending}
            onClick={() => {
              if (blocker.state === "blocked") blocker.proceed();
              else onClose();
            }}
          >
            Descartar cambios
          </button>
        </div>
      )}
      <label>
        Motivo del cambio
        <input
          required
          maxLength={1000}
          value={reason}
          disabled={pending}
          onChange={(e) => setReason(e.target.value)}
        />
      </label>
      <label className="mesa-edit-confirm">
        <input
          type="checkbox"
          checked={confirmed}
          disabled={pending}
          onChange={(e) => setConfirmed(e.target.checked)}
        />
        Confirmo el alcance de esta edición
      </label>
      <div className="mesa-tab-actions">
        <button
          type="submit"
          disabled={
            !dirty ||
            invalid ||
            !confirmed ||
            !reason.trim() ||
            pending ||
            conflict
          }
        >
          {pending ? "Procesando entrada…" : "Guardar entrada"}
        </button>
        <button
          type="button"
          disabled={pending}
          onClick={() => closeRequestRef.current()}
        >
          Descartar
        </button>
      </div>
    </form>
  );
}

export function MesaInputEditor({
  context,
  objectId,
  series,
  onClose,
  onSaved,
}: Props) {
  const dialog = useRef<HTMLDialogElement>(null);
  const closeRequestRef = useRef(onClose);
  const target = `/api/scenarios/${context.scenario_id}/mesa/inputs/${objectId}/${series.signal_key}`;
  const query = useQuery({
    queryKey: [
      "mesa-input-edit",
      context.scenario_id,
      context.case_id,
      context.variant_id,
      objectId,
      series.signal_key,
    ],
    queryFn: ({ signal }) =>
      requestJson<Context>(
        `${target}?case_id=${context.case_id}&variant_id=${context.variant_id}`,
        { signal },
      ),
    staleTime: 0,
    retry: false,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  });
  useEffect(() => {
    const element = dialog.current;
    const trigger = document.activeElement as HTMLElement | null;
    element?.showModal();
    return () => {
      element?.close();
      if (trigger?.isConnected) trigger.focus();
    };
  }, []);
  return createPortal(
    <dialog
      ref={dialog}
      className="mesa-dialog mesa-input-editor"
      aria-labelledby="mesa-input-title"
      onCancel={(event) => {
        event.preventDefault();
        closeRequestRef.current();
      }}
    >
      <h2 id="mesa-input-title">Editar entrada · {series.name}</h2>
      {query.isPending || query.isFetching ? (
        <p role="status">Cargando revisión y alcance…</p>
      ) : query.isError ? (
        <>
          <p role="alert">No se pudo abrir la entrada. {query.error.message}</p>
          <button type="button" onClick={() => void query.refetch()}>
            Reintentar
          </button>
          <button type="button" onClick={onClose}>
            Cerrar
          </button>
        </>
      ) : (
        <EditForm
          key={`${query.data.expected.binding_id}:${query.data.expected.revision_id}`}
          data={query.data}
          target={target}
          context={context}
          onSaved={onSaved}
          onClose={onClose}
          closeRequestRef={closeRequestRef}
        />
      )}
    </dialog>,
    document.body,
  );
}
