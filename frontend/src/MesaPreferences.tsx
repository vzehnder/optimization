import { useEffect, useRef, useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { createPortal } from "react-dom";
import { ApiError, getCsrfToken, requestJson } from "./api/client";
import type { components } from "./api/schema";

type Mesa = components["schemas"]["MesaResponse"];
type Panel = components["schemas"]["MesaPanelPreference"];
type Preferences = components["schemas"]["MesaPreferencesResponse"];
type Configuration = components["schemas"]["MesaConfiguration"];
type Tab = Configuration["tabs"][number];
type Props = {
  data: Mesa;
  creationAction?: ReactNode;
  renderSelectionActions?: (panels: Panel[]) => ReactNode;
  renderPanel: (
    panel: Panel,
    onMode: (mode: Panel["mode"]) => void,
    actions: ReactNode,
  ) => ReactNode;
};

function newPanel(component: Mesa["components"][number]): Panel {
  return {
    id: crypto.randomUUID(),
    title: component.name,
    mode: "chart",
    component: {
      linkable_object_id: component.linkable_object_id,
      entity_id: component.entity_id,
      entity_type: component.entity_type,
    },
    series_keys: [component.series.signal_key ?? "load_demand_mw"],
  };
}

function PanelDialog({
  data,
  initial,
  onApply,
  onClose,
  position,
  count,
  onRemove,
}: {
  data: Mesa;
  initial: Panel;
  onApply: (panel: Panel, position: number) => void;
  onClose: () => void;
  position: number;
  count: number;
  onRemove?: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [draft, setDraft] = useState(initial);
  const [order, setOrder] = useState(position);
  const selected = data.components.findIndex(
    (c) =>
      c.entity_id === draft.component.entity_id &&
      c.entity_type === draft.component.entity_type &&
      c.linkable_object_id === draft.component.linkable_object_id,
  );
  const component = data.components[selected];
  useEffect(() => {
    const element = dialog.current;
    const trigger = document.activeElement as HTMLElement | null;
    element?.showModal();
    return () => {
      element?.close();
      if (trigger?.isConnected) trigger.focus();
      else document.getElementById("mesa-add-view")?.focus();
    };
  }, []);
  return createPortal(
    <dialog
      ref={dialog}
      className="mesa-dialog"
      aria-labelledby="mesa-dialog-title"
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
    >
      <form
        onSubmit={(event) => {
          event.preventDefault();
          if (draft.title.trim() && draft.series_keys.length && component)
            onApply(draft, order);
        }}
      >
        <h2 id="mesa-dialog-title">Configurar vista</h2>
        <label>
          Título
          <input
            autoFocus
            required
            maxLength={120}
            value={draft.title}
            onChange={(e) => setDraft({ ...draft, title: e.target.value })}
          />
        </label>
        <label>
          Componente
          <select
            value={selected}
            onChange={(e) => {
              const next = newPanel(data.components[Number(e.target.value)]);
              setDraft({
                ...draft,
                component: next.component,
                series_keys: next.series_keys,
              });
            }}
          >
            {selected < 0 && (
              <option value={-1}>
                No disponible · {draft.component.entity_id}
              </option>
            )}
            {data.components.map((c, index) => (
              <option key={index} value={index}>
                {c.name} · {c.entity_id} · #{c.linkable_object_id ?? "—"}
                {c.parent_entity_id ? ` · Central ${c.parent_entity_id}` : ""}
                {c.is_active === false ? " · Inactivo" : ""}
              </option>
            ))}
          </select>
        </label>
        <fieldset>
          <legend>Series</legend>
          {component &&
            [component.series, ...(component.additional_series ?? [])].map(
              (series) => (
                <label className="mesa-checkbox" key={series.signal_key}>
                  <input
                    type="checkbox"
                    checked={draft.series_keys.includes(
                      series.signal_key ?? "load_demand_mw",
                    )}
                    onChange={(e) =>
                      setDraft({
                        ...draft,
                        series_keys: e.target.checked
                          ? [
                              ...draft.series_keys,
                              series.signal_key ?? "load_demand_mw",
                            ]
                          : draft.series_keys.filter(
                              (key) => key !== series.signal_key,
                            ),
                      })
                    }
                  />
                  {series.name} · {series.unit}
                </label>
              ),
            )}
        </fieldset>
        <label>
          Presentación
          <select
            value={draft.mode}
            onChange={(e) =>
              setDraft({ ...draft, mode: e.target.value as Panel["mode"] })
            }
          >
            <option value="chart">Gráfico</option>
            <option value="table">Tabla</option>
          </select>
        </label>
        <p>La vista consulta las series del componente seleccionado.</p>
        <label>
          Posición de vista
          <select
            value={order}
            onChange={(e) => setOrder(Number(e.target.value))}
          >
            {Array.from({ length: count }, (_, i) => (
              <option key={i} value={i}>
                {i + 1}
              </option>
            ))}
          </select>
        </label>
        <footer>
          {onRemove && (
            <button type="button" onClick={onRemove}>
              Quitar vista
            </button>
          )}
          <button type="button" onClick={onClose}>
            Cancelar
          </button>
          <button
            type="submit"
            disabled={
              !component || !draft.series_keys.length || !draft.title.trim()
            }
          >
            Aplicar
          </button>
        </footer>
      </form>
    </dialog>,
    document.body,
  );
}

function TabDialog({
  initial,
  count,
  position,
  onApply,
  onClose,
  onRemove,
}: {
  initial: Tab;
  count: number;
  position: number;
  onApply: (tab: Tab, position: number) => void;
  onClose: () => void;
  onRemove?: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [title, setTitle] = useState(initial.title);
  const [order, setOrder] = useState(position);
  useEffect(() => {
    const element = dialog.current;
    const trigger = document.activeElement as HTMLElement | null;
    element?.showModal();
    return () => {
      element?.close();
      trigger?.focus();
    };
  }, []);
  return createPortal(
    <dialog
      ref={dialog}
      className="mesa-dialog"
      aria-labelledby="mesa-tab-title"
      onCancel={(e) => {
        e.preventDefault();
        onClose();
      }}
    >
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (title.trim()) onApply({ ...initial, title: title.trim() }, order);
        }}
      >
        <h2 id="mesa-tab-title">Configurar pestaña</h2>
        <label>
          Nombre de pestaña
          <input
            autoFocus
            required
            maxLength={120}
            value={title}
            onChange={(e) => setTitle(e.target.value)}
          />
        </label>
        <label>
          Posición de pestaña
          <select
            value={order}
            onChange={(e) => setOrder(Number(e.target.value))}
          >
            {Array.from({ length: count }, (_, i) => (
              <option key={i} value={i}>
                {i + 1}
              </option>
            ))}
          </select>
        </label>
        <p>Cada pestaña conserva su distribución y sus vistas.</p>
        <footer>
          {onRemove && (
            <button type="button" onClick={onRemove}>
              Quitar pestaña
            </button>
          )}
          <button type="button" onClick={onClose}>
            Cancelar
          </button>
          <button type="submit" disabled={!title.trim()}>
            Aplicar
          </button>
        </footer>
      </form>
    </dialog>,
    document.body,
  );
}

function ConfiguredMesa({
  data,
  initial,
  path,
  renderPanel,
  renderSelectionActions,
  creationAction,
}: Props & { initial: Preferences; path: string }) {
  const [configuration, setConfiguration] = useState<Configuration>(() => {
    const config = structuredClone(initial.configuration);
    if (initial.revision === 0 && data.components.length)
      config.tabs[0].panels = [newPanel(data.components[0])];
    return config;
  });
  const [revision, setRevision] = useState(initial.revision);
  const [editing, setEditing] = useState<Panel | null>(null);
  const [editingTab, setEditingTab] = useState<Tab | null>(null);
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [conflict, setConflict] = useState(false);
  const tab = configuration.tabs.find(
    (item) => item.id === configuration.active_tab_id,
  )!;
  const capacity = { "1x1": 1, "1x2": 2, "2x2": 4, "2x3": 6 }[tab.layout];
  function update(next: Configuration) {
    setConfiguration(next);
    setNotice("Cambios sin guardar");
  }
  function updatePanel(panel: Panel, position?: number) {
    const previousIndex = tab.panels.findIndex((p) => p.id === panel.id);
    const panels = tab.panels.filter((p) => p.id !== panel.id);
    panels.splice(
      position ?? (previousIndex < 0 ? panels.length : previousIndex),
      0,
      panel,
    );
    update({
      ...configuration,
      tabs: configuration.tabs.map((item) =>
        item.id === tab.id
          ? {
              ...item,
              panels,
            }
          : item,
      ),
    });
  }
  async function save() {
    setSaving(true);
    setError("");
    setNotice("");
    try {
      const result = await requestJson<Preferences>(path, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          "X-CSRF-Token": await getCsrfToken(),
        },
        body: JSON.stringify({ expected_revision: revision, configuration }),
      });
      setRevision(result.revision);
      setNotice("Mesa guardada");
    } catch (cause) {
      setConflict(cause instanceof ApiError && cause.status === 409);
      setError(
        cause instanceof Error ? cause.message : "No se pudo guardar la mesa.",
      );
    } finally {
      setSaving(false);
    }
  }
  async function loadSaved() {
    setSaving(true);
    try {
      const saved = await requestJson<Preferences>(path);
      setConfiguration(saved.configuration);
      setRevision(saved.revision);
      setConflict(false);
      setError("");
      setNotice("Configuración guardada recuperada");
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "No se pudo recuperar la configuración.",
      );
    } finally {
      setSaving(false);
    }
  }
  return (
    <>
      {error && (
        <div role="alert">
          <p>{error}</p>
          {conflict && (
            <>
              <p>
                Tus cambios siguen visibles. Cargar la mesa guardada reemplaza
                esta edición local.
              </p>
              <button
                type="button"
                disabled={saving}
                onClick={() => void loadSaved()}
              >
                Cargar mesa guardada
              </button>
            </>
          )}
        </div>
      )}
      <fieldset className="mesa-editor" disabled={saving}>
        <div
          className="mesa-tabs"
          role="tablist"
          aria-label="Pestañas de la mesa"
        >
          {configuration.tabs.map((item) => (
            <button
              type="button"
              key={item.id}
              role="tab"
              id={`mesa-tab-${item.id}`}
              aria-controls="mesa-tab-content"
              tabIndex={item.id === tab.id ? 0 : -1}
              aria-selected={item.id === tab.id}
              onKeyDown={(event) => {
                const index = configuration.tabs.findIndex(
                  (t) => t.id === item.id,
                );
                const last = configuration.tabs.length - 1;
                const next =
                  event.key === "ArrowRight"
                    ? (index + 1) % (last + 1)
                    : event.key === "ArrowLeft"
                      ? (index + last) % (last + 1)
                      : event.key === "Home"
                        ? 0
                        : event.key === "End"
                          ? last
                          : null;
                if (next === null) return;
                event.preventDefault();
                const target = configuration.tabs[next];
                update({ ...configuration, active_tab_id: target.id });
                document.getElementById(`mesa-tab-${target.id}`)?.focus();
              }}
              onClick={() =>
                update({ ...configuration, active_tab_id: item.id })
              }
            >
              {item.title}
            </button>
          ))}
        </div>
        <div className="mesa-tab-actions">
          {creationAction}
          <button
            type="button"
            disabled={configuration.tabs.length >= 24}
            onClick={() =>
              setEditingTab({
                id: crypto.randomUUID(),
                title: data.components[0]?.name ?? "Nueva pestaña",
                layout: "2x2",
                panels: data.components.length
                  ? [newPanel(data.components[0])]
                  : [],
              })
            }
          >
            Agregar pestaña
          </button>
          <button type="button" onClick={() => setEditingTab(tab)}>
            Configurar pestaña
          </button>
        </div>
        <div className="mesa-toolbar">
          <label>
            Distribución de las vistas
            <select
              value={tab.layout}
              onChange={(e) =>
                update({
                  ...configuration,
                  tabs: configuration.tabs.map((item) =>
                    item.id === tab.id
                      ? { ...item, layout: e.target.value as typeof tab.layout }
                      : item,
                  ),
                })
              }
            >
              <option value="1x1">1 × 1 · 1 vista</option>
              <option value="1x2">1 × 2 · 2 vistas</option>
              <option value="2x2">2 × 2 · 4 vistas</option>
              <option value="2x3">2 × 3 · 6 vistas</option>
            </select>
          </label>
          <button
            type="button"
            id="mesa-add-view"
            disabled={!data.components.length || tab.panels.length >= 6}
            onClick={() => setEditing(newPanel(data.components[0]))}
          >
            Agregar vista
          </button>
          <p aria-live="polite">
            {saving
              ? "Guardando mesa…"
              : notice || `Configuración personal · Revisión ${revision}`}
          </p>
          <button type="button" disabled={conflict} onClick={() => void save()}>
            Guardar mesa
          </button>
          {renderSelectionActions?.(tab.panels.slice(0, capacity))}
        </div>
        <div
          className="mesa-grid"
          data-layout={tab.layout}
          role="tabpanel"
          id="mesa-tab-content"
          aria-labelledby={`mesa-tab-${tab.id}`}
        >
          {tab.panels.slice(0, capacity).map((panel) => (
            <div className="mesa-cell" key={panel.id}>
              {renderPanel(
                panel,
                (mode) => updatePanel({ ...panel, mode }),
                <button
                  type="button"
                  aria-label={`Configurar ${panel.title}`}
                  onClick={() => setEditing(panel)}
                >
                  Configurar
                </button>,
              )}
            </div>
          ))}
        </div>
        {!tab.panels.length && (
          <p role="status">
            {data.components.length
              ? "Esta pestaña no tiene vistas. Agrega una vista para consultar sus series."
              : "Este caso no tiene componentes eléctricos disponibles."}
          </p>
        )}
        {tab.panels.length > capacity && (
          <p>
            {tab.panels.length - capacity} vistas ocultas; se conservan al
            ampliar.
          </p>
        )}
      </fieldset>
      {editing && (
        <PanelDialog
          data={data}
          initial={editing}
          position={Math.max(
            0,
            tab.panels.some((p) => p.id === editing.id)
              ? tab.panels.findIndex((p) => p.id === editing.id)
              : tab.panels.length,
          )}
          count={
            tab.panels.length +
            (tab.panels.some((p) => p.id === editing.id) ? 0 : 1)
          }
          onRemove={
            tab.panels.some((p) => p.id === editing.id)
              ? () => {
                  update({
                    ...configuration,
                    tabs: configuration.tabs.map((t) =>
                      t.id === tab.id
                        ? {
                            ...t,
                            panels: t.panels.filter((p) => p.id !== editing.id),
                          }
                        : t,
                    ),
                  });
                  setEditing(null);
                }
              : undefined
          }
          onApply={(panel, position) => {
            updatePanel(panel, position);
            setEditing(null);
          }}
          onClose={() => setEditing(null)}
        />
      )}
      {editingTab && (
        <TabDialog
          initial={editingTab}
          position={
            configuration.tabs.some((t) => t.id === editingTab.id)
              ? configuration.tabs.findIndex((t) => t.id === editingTab.id)
              : configuration.tabs.length
          }
          count={
            configuration.tabs.length +
            (configuration.tabs.some((t) => t.id === editingTab.id) ? 0 : 1)
          }
          onApply={(next, position) => {
            const tabs = configuration.tabs.filter((t) => t.id !== next.id);
            tabs.splice(position, 0, next);
            update({ ...configuration, tabs, active_tab_id: next.id });
            setEditingTab(null);
          }}
          onRemove={
            configuration.tabs.length > 1 &&
            configuration.tabs.some((t) => t.id === editingTab.id)
              ? () => {
                  const tabs = configuration.tabs.filter(
                    (t) => t.id !== editingTab.id,
                  );
                  update({ ...configuration, tabs, active_tab_id: tabs[0].id });
                  setEditingTab(null);
                }
              : undefined
          }
          onClose={() => setEditingTab(null)}
        />
      )}
    </>
  );
}

export function MesaPreferences(props: Props) {
  const { scenario_id: scenario, case_id: caseId } = props.data.context;
  const path = `/api/scenarios/${scenario}/mesa/preferences?case_id=${caseId}`;
  const query = useQuery({
    queryKey: ["mesa-preferences", scenario, caseId],
    queryFn: ({ signal }) => requestJson<Preferences>(path, { signal }),
    retry: false,
    staleTime: 0,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  });
  if (query.isError)
    return (
      <div role="alert">
        <p>No se pudo cargar la configuración. {query.error.message}</p>
        <button type="button" onClick={() => void query.refetch()}>
          Reintentar configuración
        </button>
      </div>
    );
  if (query.isPending || query.isFetching)
    return <p role="status">Cargando configuración de la mesa…</p>;
  return <ConfiguredMesa {...props} initial={query.data} path={path} />;
}
