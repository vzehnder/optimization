import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useBlocker } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { getCsrfToken, requestJson } from "./api/client";
import type { components } from "./api/schema";

type Context = components["schemas"]["MesaContext"];
type Options = components["schemas"]["MesaManualOptions"];

async function postManual<T>(path: string, payload: unknown): Promise<T> {
  return requestJson<T>(path, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRF-Token": await getCsrfToken(),
    },
    body: JSON.stringify(payload),
  });
}

export function MesaManualCreate({
  context,
  onClose,
  onSaved,
}: {
  context: Context;
  onClose: () => void;
  onSaved: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const path = `/api/scenarios/${context.scenario_id}/mesa/manual-series`;
  const options = useQuery({
    queryKey: [
      "mesa-manual-options",
      context.scenario_id,
      context.case_id,
      context.variant_id,
    ],
    queryFn: ({ signal }) =>
      requestJson<Options>(
        `${path}?case_id=${context.case_id}&variant_id=${context.variant_id}`,
        { signal },
      ),
    retry: false,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  });
  const [name, setName] = useState("");
  const [choice, setChoice] = useState(0);
  const [start, setStart] = useState("");
  const [zone, setZone] = useState("America/Santiago");
  const [minutes, setMinutes] = useState("60");
  const [values, setValues] = useState("");
  const [reason, setReason] = useState("");
  const [confirm, setConfirm] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [leaving, setLeaving] = useState(false);
  const busy = useRef(false);
  const dirty = !!(name || values || start || reason);
  const blocker = useBlocker(dirty || pending);
  const selected = options.data?.items[choice];
  const owners =
    options.data?.items.filter(
      (item, index, all) =>
        all.findIndex((o) => o.object_id === item.object_id) === index,
    ) ?? [];
  const close = () => {
    if (dirty || pending) setLeaving(true);
    else onClose();
  };
  useEffect(() => {
    const element = dialog.current;
    const trigger = document.activeElement as HTMLElement | null;
    element?.showModal();
    return () => {
      element?.close();
      if (trigger?.isConnected) trigger.focus();
    };
  }, []);
  useEffect(() => {
    const warn = (event: BeforeUnloadEvent) => {
      if (dirty || pending) event.preventDefault();
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty, pending]);
  return createPortal(
    <dialog
      ref={dialog}
      className="mesa-dialog mesa-input-editor"
      aria-labelledby="mesa-manual-create-title"
      onCancel={(event) => {
        event.preventDefault();
        close();
      }}
    >
      <h2 id="mesa-manual-create-title">Crear serie manual</h2>
      <p>
        La serie se publica como apoyo. No participa en la simulación hasta
        vincularla explícitamente a una entrada admitida.
      </p>
      {options.isPending ? (
        <p role="status">Cargando objetos y señales compatibles…</p>
      ) : options.isError ? (
        <>
          <p role="alert">
            No se pudieron consultar las señales. {options.error.message}
          </p>
          <button type="button" onClick={() => void options.refetch()}>
            Reintentar
          </button>
        </>
      ) : !options.data.items.length ? (
        <p role="status">
          Este caso no tiene objetos activos con señales manuales compatibles.
        </p>
      ) : (
        <form
          onSubmit={async (event) => {
            event.preventDefault();
            if (busy.current || !selected || !confirm) return;
            setError("");
            const numbers = values
              .trim()
              .split(/\r?\n/)
              .map((v) => (v.trim() === "" ? NaN : Number(v)));
            const instant = Date.parse(start);
            const step = Number(minutes) * 60000;
            if (
              !/(Z|[+-]\d{2}:\d{2})$/.test(start) ||
              !Number.isFinite(instant) ||
              !Number.isFinite(step) ||
              step <= 0 ||
              numbers.length > 10000 ||
              numbers.some((n) => !Number.isFinite(n))
            ) {
              setError(
                "Indica inicio con offset, duración positiva y un número por línea (hasta 10000 intervalos).",
              );
              return;
            }
            busy.current = true;
            setPending(true);
            try {
              await postManual(path, {
                case_id: context.case_id,
                variant_id: context.variant_id,
                object_id: selected.object_id,
                name,
                binding_role_key: selected.binding_role_key,
                semantic_type_key: selected.semantic_type_key,
                unit_key: selected.unit_key,
                timezone: zone,
                resolution_seconds: Number(minutes) * 60,
                points: numbers.map((value, i) => ({
                  start: new Date(instant + i * step).toISOString(),
                  end: new Date(instant + (i + 1) * step).toISOString(),
                  value,
                })),
                reason,
                confirm,
              });
              onSaved();
            } catch (caught) {
              setError(
                caught instanceof Error
                  ? caught.message
                  : "No se pudo publicar la serie.",
              );
            } finally {
              busy.current = false;
              setPending(false);
            }
          }}
        >
          <fieldset disabled={pending} className="mesa-manual-fields">
            <legend>Serie de apoyo</legend>
            <label>
              Nombre de la serie
              <input
                autoFocus
                required
                maxLength={120}
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </label>
            <label>
              Objeto propietario
              <select
                value={selected?.object_id ?? ""}
                onChange={(e) =>
                  setChoice(
                    options.data.items.findIndex(
                      (o) => o.object_id === Number(e.target.value),
                    ),
                  )
                }
              >
                {owners.map((o) => (
                  <option key={o.object_id} value={o.object_id}>
                    {o.object_name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Señal y unidad
              <select
                value={choice}
                onChange={(e) => setChoice(Number(e.target.value))}
              >
                {options.data.items.map(
                  (o, i) =>
                    o.object_id === selected?.object_id && (
                      <option key={i} value={i}>
                        {o.name}
                      </option>
                    ),
                )}
              </select>
            </label>
            <p>
              Unidad: {selected?.unit} · Rol previsto:{" "}
              {selected?.binding_role_key} · Procedencia manual · Proyección
            </p>
            <label>
              Inicio con offset
              <input
                required
                value={start}
                placeholder="2026-10-20T00:00:00-03:00"
                onChange={(e) => setStart(e.target.value)}
              />
            </label>
            <label>
              Zona horaria
              <input
                required
                value={zone}
                onChange={(e) => setZone(e.target.value)}
              />
            </label>
            <label>
              Duración de cada intervalo (minutos)
              <input
                required
                type="number"
                min="0.0166666667"
                step="any"
                value={minutes}
                onChange={(e) => setMinutes(e.target.value)}
              />
            </label>
            <label>
              Valores por intervalo
              <textarea
                required
                rows={5}
                value={values}
                onChange={(e) => setValues(e.target.value)}
                aria-describedby="mesa-manual-values-help"
              />
            </label>
            <p id="mesa-manual-values-help">
              Un número por línea, en {selected?.unit}. Cada valor cubre un
              intervalo; el fin es exclusivo. Usa punto decimal.
            </p>
            <label>
              Motivo
              <input
                required
                maxLength={1000}
                value={reason}
                onChange={(e) => setReason(e.target.value)}
              />
            </label>
            <label className="mesa-edit-confirm">
              <input
                type="checkbox"
                checked={confirm}
                onChange={(e) => setConfirm(e.target.checked)}
              />
              Confirmo la publicación como apoyo
            </label>
            <button
              type="submit"
              disabled={
                !confirm || !name.trim() || !reason.trim() || !values.trim()
              }
            >
              {pending ? "Publicando…" : "Publicar serie de apoyo"}
            </button>
          </fieldset>
        </form>
      )}
      {error && <p role="alert">{error}</p>}
      {(leaving || blocker.state === "blocked") && (
        <div role="alert">
          <p>
            {pending
              ? "Espera a que termine la publicación."
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
      <button type="button" disabled={pending} onClick={close}>
        Cerrar
      </button>
    </dialog>,
    document.body,
  );
}
