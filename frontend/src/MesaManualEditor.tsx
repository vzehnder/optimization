import { useEffect, useRef, useState, type RefObject } from "react";
import { createPortal } from "react-dom";
import { useBlocker } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ApiError, getCsrfToken, requestJson } from "./api/client";
import type { components } from "./api/schema";

type Context = components["schemas"]["MesaContext"];
type Detail = components["schemas"]["MesaManualDetail"];
type Series = components["schemas"]["MesaSeries"];

function ManualForm({
  initial,
  context,
  path,
  onChanged,
  onClose,
  closeRef,
}: {
  initial: Detail;
  context: Context;
  path: string;
  onChanged: () => void;
  onClose: () => void;
  closeRef: RefObject<() => void>;
}) {
  const [data, setData] = useState(initial);
  const [values, setValues] = useState(
    (initial.series.points ?? []).map((p) => String(p.value)),
  );
  const [reason, setReason] = useState("");
  const [publishConfirmed, setPublishConfirmed] = useState(false);
  const [bindingConfirmed, setBindingConfirmed] = useState(false);
  const [destination, setDestination] = useState(0);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [conflict, setConflict] = useState(false);
  const [latest, setLatest] = useState<Detail | null>(null);
  const [leaving, setLeaving] = useState(false);
  const busy = useRef(false);
  const points = data.series.points ?? [];
  const dirty = values.some((v, i) => v !== String(points[i].value));
  const invalid = values.some((v) => !v.trim() || !Number.isFinite(Number(v)));
  const blocker = useBlocker(dirty || pending);
  const selection = data.destinations[destination];
  const current = data.series.binding_state === "valid_current";
  const load = () =>
    requestJson<Detail>(
      `${path}?case_id=${context.case_id}&variant_id=${context.variant_id}`,
    );
  function acceptCurrent(next: Detail) {
    setData(next);
    setValues((next.series.points ?? []).map((p) => String(p.value)));
    setConflict(false);
    setLatest(null);
    setError("");
    setPublishConfirmed(false);
    setBindingConfirmed(false);
    setReason("");
  }
  useEffect(() => {
    closeRef.current = () => {
      if (dirty || pending) setLeaving(true);
      else onClose();
    };
    const warn = (event: BeforeUnloadEvent) => {
      if (dirty || pending) event.preventDefault();
    };
    window.addEventListener("beforeunload", warn);
    return () => {
      closeRef.current = onClose;
      window.removeEventListener("beforeunload", warn);
    };
  }, [closeRef, onClose, dirty, pending]);
  async function submit(action: "revisions" | "binding") {
    if (busy.current) return;
    busy.current = true;
    setPending(true);
    setError("");
    let committed = false;
    try {
      await requestJson(`${path}/${action}`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRF-Token": await getCsrfToken(),
        },
        body: JSON.stringify({
          case_id: context.case_id,
          variant_id: context.variant_id,
          expected: data.expected,
          reason,
          ...(action === "revisions"
            ? {
                unit: data.series.unit,
                points: points.map((p, i) => ({
                  ...p,
                  value: Number(values[i]),
                })),
                confirm: publishConfirmed,
              }
            : {
                object_id: selection.object_id,
                binding_role_key: selection.binding_role_key,
                confirm: bindingConfirmed,
              }),
        }),
      });
      committed = true;
      onChanged();
      acceptCurrent(await load());
    } catch (caught) {
      setError(
        committed
          ? "Cambio guardado. Recupera la revisión actual para continuar."
          : caught instanceof Error
            ? caught.message
            : "No se pudo guardar.",
      );
      setConflict(
        committed ||
          (caught instanceof ApiError && [409, 412].includes(caught.status)),
      );
    } finally {
      busy.current = false;
      setPending(false);
    }
  }
  return (
    <>
      <p>
        Revisión {data.series.revision_number} · Fuente #
        {data.series.time_series_set_id} · Zona: {data.series.timezone} ·
        Procedencia manual
      </p>
      <p>{data.scope_message}</p>
      <p role="status">
        {current
          ? "Vínculo vigente en esta variante"
          : data.series.binding_state === "stale"
            ? "Vínculo pendiente de revalidación; la revisión nueva aún no es ejecutable."
            : "Serie de apoyo. No participa en esta simulación."}
      </p>
      <div
        className="mesa-table-scroll mesa-input-table"
        tabIndex={0}
        role="region"
        aria-label="Datos de la serie manual"
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
            {points.map((p, i) => (
              <tr key={p.start}>
                <td>{p.start}</td>
                <td>{p.end}</td>
                <td>
                  <input
                    type="number"
                    step="any"
                    aria-label={`Valor del intervalo ${i + 1} (${data.series.unit})`}
                    value={values[i]}
                    disabled={pending}
                    onChange={(e) => {
                      setValues((previous) =>
                        previous.map((v, index) =>
                          index === i ? e.target.value : v,
                        ),
                      );
                      setBindingConfirmed(false);
                    }}
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <label>
        Motivo
        <input
          required
          maxLength={1000}
          disabled={pending}
          value={reason}
          onChange={(e) => setReason(e.target.value)}
        />
      </label>
      <label className="mesa-edit-confirm">
        <input
          type="checkbox"
          disabled={pending}
          checked={publishConfirmed}
          onChange={(e) => setPublishConfirmed(e.target.checked)}
        />
        Confirmo la publicación de una nueva revisión
      </label>
      <button
        type="button"
        disabled={
          !dirty ||
          invalid ||
          !publishConfirmed ||
          !reason.trim() ||
          pending ||
          conflict
        }
        onClick={() => void submit("revisions")}
      >
        Publicar revisión
      </button>
      <h3>Vincular a una entrada</h3>
      {selection ? (
        <>
          <label>
            Destino compatible
            <select
              value={destination}
              disabled={pending || dirty}
              onChange={(e) => {
                setDestination(Number(e.target.value));
                setBindingConfirmed(false);
              }}
            >
              {data.destinations.map((d, i) => (
                <option key={d.binding_role_key} value={i}>
                  {d.name}
                </option>
              ))}
            </select>
          </label>
          <p>
            {selection.current_signal_id
              ? `Reemplaza señal #${selection.current_signal_id}, revisión #${selection.current_revision_id}.`
              : "La entrada no tiene una fuente vinculada."}{" "}
            Se usará la revisión publicada #{data.series.revision_id} de esta
            serie.
          </p>
          {dirty && <p>Publica o descarta los cambios antes de vincular.</p>}
          <label className="mesa-edit-confirm">
            <input
              type="checkbox"
              disabled={pending || dirty}
              checked={bindingConfirmed}
              onChange={(e) => setBindingConfirmed(e.target.checked)}
            />
            Confirmo el reemplazo de esta entrada en la variante
          </label>
          <button
            type="button"
            disabled={
              dirty ||
              current ||
              !bindingConfirmed ||
              !reason.trim() ||
              pending ||
              conflict
            }
            onClick={() => void submit("binding")}
          >
            Vincular revisión publicada
          </button>
        </>
      ) : (
        <p>
          No hay destinos ejecutables admitidos para esta serie en la
          preparación de la mesa.
        </p>
      )}
      {error && <p role="alert">{error}</p>}
      {conflict && (
        <button
          type="button"
          disabled={pending}
          onClick={async () => {
            setPending(true);
            try {
              setLatest(await load());
            } catch (caught) {
              setError((caught as Error).message);
            } finally {
              setPending(false);
            }
          }}
        >
          Consultar revisión actual
        </button>
      )}
      {latest && (
        <>
          <p>
            Revisión actual {latest.series.revision_number}. Tus valores se
            conservan hasta elegir la revisión actual.
          </p>
          <div className="mesa-table-scroll">
            <table aria-label="Comparar cambios manuales">
              <thead>
                <tr>
                  <th>Inicio</th>
                  <th>Tu valor</th>
                  <th>Actual</th>
                </tr>
              </thead>
              <tbody>
                {points.map((p, i) => (
                  <tr key={p.start}>
                    <td>{p.start}</td>
                    <td>{values[i]}</td>
                    <td>
                      {latest.series.points?.find(
                        (n) => n.start === p.start && n.end === p.end,
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
              acceptCurrent(latest);
              onChanged();
            }}
          >
            Usar revisión actual
          </button>
        </>
      )}
      {(leaving || blocker.state === "blocked") && (
        <div role="alert">
          <p>
            {pending
              ? "Espera a que termine el guardado."
              : "Hay cambios sin publicar."}
          </p>
          <button
            type="button"
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
      <footer>
        <button
          type="button"
          disabled={pending}
          onClick={() => closeRef.current()}
        >
          Cerrar
        </button>
      </footer>
    </>
  );
}

export function MesaManualEditor({
  context,
  series,
  onClose,
  onChanged,
}: {
  context: Context;
  series: Series;
  onClose: () => void;
  onChanged: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const closeRef = useRef(onClose);
  const path = `/api/scenarios/${context.scenario_id}/mesa/manual-series/${series.signal_id}`;
  const query = useQuery({
    queryKey: [
      "mesa-manual-detail",
      context.scenario_id,
      context.case_id,
      context.variant_id,
      series.signal_id,
    ],
    queryFn: ({ signal }) =>
      requestJson<Detail>(
        `${path}?case_id=${context.case_id}&variant_id=${context.variant_id}`,
        { signal },
      ),
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
      else
        document
          .querySelector<HTMLButtonElement>(
            `[data-mesa-manual-manage="${series.signal_id}"]`,
          )
          ?.focus();
    };
  }, [series.signal_id]);
  return createPortal(
    <dialog
      ref={dialog}
      className="mesa-dialog mesa-input-editor"
      aria-labelledby="mesa-manual-editor-title"
      onCancel={(event) => {
        event.preventDefault();
        closeRef.current();
      }}
    >
      <h2 id="mesa-manual-editor-title">Serie manual · {series.name}</h2>
      {query.isPending || query.isFetching ? (
        <p role="status">Cargando revisión y vínculos…</p>
      ) : query.isError ? (
        <>
          <p role="alert">
            No se pudo consultar la serie. {query.error.message}
          </p>
          <button type="button" onClick={() => void query.refetch()}>
            Reintentar
          </button>
          <button type="button" onClick={onClose}>
            Cerrar
          </button>
        </>
      ) : (
        <ManualForm
          initial={query.data}
          context={context}
          path={path}
          onChanged={onChanged}
          onClose={onClose}
          closeRef={closeRef}
        />
      )}
    </dialog>,
    document.body,
  );
}
