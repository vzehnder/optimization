import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useBlocker } from "react-router-dom";
import { createHydraulicDiagram, getScenario } from "./api/client";
import { HydraulicDiagramEditor } from "./Workspace";

export function MesaHydraulicAssets({
  scenarioId,
  onClose,
  onSaved,
}: {
  scenarioId: number;
  onClose: () => void;
  onSaved: () => void;
}) {
  const queryClient = useQueryClient();
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [leaving, setLeaving] = useState(false);
  const blocker = useBlocker(dirty);
  useEffect(() => {
    const warn = (event: BeforeUnloadEvent) => {
      if (dirty) event.preventDefault();
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);
  const context = useQuery({
    queryKey: ["mesa-hydraulic-editor", scenarioId],
    queryFn: async () => {
      const scenario = await getScenario(scenarioId);
      const diagram = await createHydraulicDiagram(scenarioId);
      return { scenario, diagram };
    },
    retry: false,
    refetchOnWindowFocus: false,
    gcTime: 0,
  });
  return (
    <section
      className="mesa-hydraulic-assets"
      aria-label="Activos hidráulicos del caso"
    >
      <div className="mesa-toolbar">
        <h2>Activos hidráulicos del caso</h2>
        <button
          type="button"
          disabled={saving}
          onClick={() => (dirty ? setLeaving(true) : onClose())}
        >
          Cerrar edición hidráulica
        </button>
      </div>
      <p>
        Los activos incompletos quedan como borradores. Guarda, valida el modelo
        y promueve una versión para ejecutarlos.
      </p>
      <p>Almacenamiento en hm³, cota en m, potencia en MW y caudal en m³/s.</p>
      {(leaving || blocker.state === "blocked") && (
        <div role="alert">
          <p>
            {saving
              ? "Espera a que termine el guardado hidráulico."
              : "Hay cambios hidráulicos sin guardar."}
          </p>
          <button
            type="button"
            onClick={() => {
              setLeaving(false);
              blocker.reset?.();
            }}
          >
            Seguir editando activos
          </button>
          <button
            type="button"
            disabled={saving}
            onClick={() => {
              if (blocker.state === "blocked") blocker.proceed();
              else onClose();
            }}
          >
            Descartar cambios hidráulicos
          </button>
        </div>
      )}
      {context.isPending && <p role="status">Cargando edición hidráulica…</p>}
      {context.isError && (
        <p role="alert">
          No se pudo cargar el diagrama. {context.error.message}
          <button type="button" onClick={() => void context.refetch()}>
            Reintentar edición hidráulica
          </button>
        </p>
      )}
      {context.data && (
        <HydraulicDiagramEditor
          embedded
          scenario={context.data.scenario}
          initialDiagram={context.data.diagram}
          onDirtyChange={setDirty}
          onSavingChange={setSaving}
          onPrepare={() => {
            void queryClient.invalidateQueries({
              queryKey: ["mesa-hydraulic-sources", scenarioId],
            });
            onClose();
          }}
          onSaved={() => {
            void queryClient.invalidateQueries({
              queryKey: ["optimization-mesa"],
            });
            onSaved();
          }}
        />
      )}
    </section>
  );
}
