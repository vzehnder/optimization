import {
  useEffect,
  useRef,
  useState,
  type CSSProperties,
  type ReactNode,
} from "react";
import { useQuery } from "@tanstack/react-query";
import { createPortal } from "react-dom";
import { ApiError, getCsrfToken, requestJson } from "./api/client";
import type { components } from "./api/schema";
import { seriesAxis, type MesaAxis } from "./mesaChartData";
import { MesaRow } from "./MesaRow";
import { MesaSpacePicker } from "./MesaSpacePicker";
import {
  contains,
  describePlacement,
  firstFree,
  fits,
  gridSize,
  overlaps,
  placePanels,
  type Placement,
} from "./mesaLayout";

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
  tab,
  onRemove,
}: {
  data: Mesa;
  initial: Panel;
  onApply: (panel: Panel) => void;
  onClose: () => void;
  tab: Tab;
  onRemove?: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [draft, setDraft] = useState(initial);
  const [choosingSpace, setChoosingSpace] = useState(false);
  const { rows, columns } = gridSize(tab.layout);
  const validPlacement =
    !!draft.placement &&
    fits(draft.placement, rows, columns) &&
    !tab.panels.some(
      (panel) =>
        panel.id !== draft.id &&
        panel.placement &&
        overlaps(draft.placement!, panel.placement),
    );
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
          if (
            draft.title.trim() &&
            draft.series_keys.length &&
            component &&
            validPlacement &&
            !choosingSpace
          )
            onApply(draft);
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
        <section
          className="mesa-space-setting"
          aria-label="Espacio en la cuadrícula"
        >
          <div className="mesa-space-setting-heading">
            <div>
              <strong>Espacio en la cuadrícula</strong>
              <p>
                {draft.placement
                  ? describePlacement(draft.placement)
                  : "Sin espacio asignado"}
              </p>
            </div>
            <button
              type="button"
              aria-expanded={choosingSpace}
              onClick={() => setChoosingSpace(!choosingSpace)}
            >
              Elegir espacio
            </button>
          </div>
          {choosingSpace && draft.placement && (
            <MesaSpacePicker
              tab={tab}
              panelId={draft.id}
              initial={draft.placement}
              onApply={(placement) => {
                setDraft({ ...draft, placement });
                setChoosingSpace(false);
              }}
              onCancel={() => setChoosingSpace(false)}
            />
          )}
        </section>
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
                series_axes: {},
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
                <div
                  className="mesa-series-axis-choice"
                  key={series.signal_key}
                >
                  <label className="mesa-checkbox">
                    <input
                      type="checkbox"
                      checked={draft.series_keys.includes(
                        series.signal_key ?? "load_demand_mw",
                      )}
                      onChange={(e) => {
                        const axes = { ...draft.series_axes };
                        if (!e.target.checked)
                          delete axes[series.signal_key ?? "load_demand_mw"];
                        else if (series.signal_key === "price_usd_per_mwh")
                          axes[series.signal_key] = "secondary";
                        setDraft({
                          ...draft,
                          series_axes: axes,
                          series_keys: e.target.checked
                            ? [
                                ...draft.series_keys,
                                series.signal_key ?? "load_demand_mw",
                              ]
                            : draft.series_keys.filter(
                                (key) => key !== series.signal_key,
                              ),
                        });
                      }}
                    />
                    {series.name} · {series.unit}
                  </label>
                  {draft.series_keys.includes(
                    series.signal_key ?? "load_demand_mw",
                  ) && (
                    <label>
                      Eje Y · {series.name}
                      <select
                        aria-label={`Eje Y · ${series.name}`}
                        value={seriesAxis(
                          series.signal_key ?? "load_demand_mw",
                          draft.series_axes,
                        )}
                        onChange={(event) =>
                          setDraft({
                            ...draft,
                            series_axes: {
                              ...draft.series_axes,
                              [series.signal_key ?? "load_demand_mw"]: event
                                .target.value as MesaAxis,
                            },
                          })
                        }
                      >
                        <option value="primary">Primario · izquierda</option>
                        <option value="secondary">Secundario · derecha</option>
                      </select>
                    </label>
                  )}
                </div>
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
        <p>
          Puedes asignar todas las series del componente a cualquiera de los dos
          ejes. Si mezclas unidades, el eje indicará cuáles son; los valores
          conservan sus unidades originales.
        </p>
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
              !component ||
              !draft.series_keys.length ||
              !draft.title.trim() ||
              !validPlacement ||
              choosingSpace
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
    return { ...config, tabs: config.tabs.map(placePanels) };
  });
  const [revision, setRevision] = useState(initial.revision);
  const [editing, setEditing] = useState<Panel | null>(null);
  const [editingTab, setEditingTab] = useState<Tab | null>(null);
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [conflict, setConflict] = useState(false);
  const [layoutError, setLayoutError] = useState("");
  const tab = configuration.tabs.find(
    (item) => item.id === configuration.active_tab_id,
  )!;
  const { rows, columns } = gridSize(tab.layout);
  const visiblePanels = tab.panels
    .filter((panel) => panel.placement)
    .sort(
      (a, b) =>
        a.placement!.row - b.placement!.row ||
        a.placement!.column - b.placement!.column,
    );
  const available = firstFree(tab.layout, tab.panels);
  function changeGrid(nextRows: number, nextColumns: number) {
    const outside = visiblePanels.filter(
      (panel) => !fits(panel.placement!, nextRows, nextColumns),
    );
    if (outside.length) {
      setLayoutError(
        `No se puede reducir a ${nextRows} × ${nextColumns}: ${outside.map((panel) => `«${panel.title}»`).join(", ")} quedaría fuera. Mueve o reduce esas vistas desde Configurar → Elegir espacio.`,
      );
      return;
    }
    setLayoutError("");
    update({
      ...configuration,
      tabs: configuration.tabs.map((item) =>
        item.id === tab.id
          ? placePanels({ ...item, layout: `${nextRows}x${nextColumns}` })
          : item,
      ),
    });
  }
  function addView(placement: Placement | null = available) {
    if (!placement || !data.components.length) return;
    setEditing({ ...newPanel(data.components[0]), placement });
  }
  function update(next: Configuration) {
    setConfiguration(next);
    setNotice("Cambios sin guardar");
    setLayoutError("");
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
      setConfiguration({
        ...saved.configuration,
        tabs: saved.configuration.tabs.map(placePanels),
      });
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
              setEditingTab(
                placePanels({
                  id: crypto.randomUUID(),
                  title: data.components[0]?.name ?? "Nueva pestaña",
                  layout: "2x2",
                  panels: data.components.length
                    ? [newPanel(data.components[0])]
                    : [],
                }),
              )
            }
          >
            Agregar pestaña
          </button>
          <button type="button" onClick={() => setEditingTab(tab)}>
            Configurar pestaña
          </button>
        </div>
        <div className="mesa-toolbar">
          <div
            className="mesa-grid-controls"
            role="group"
            aria-label="Distribución de las vistas"
          >
            <span>Cuadrícula</span>
            <label>
              Filas
              <select
                aria-label="Filas"
                value={rows}
                onChange={(e) => changeGrid(Number(e.target.value), columns)}
              >
                {Array.from({ length: 6 }, (_, i) => (
                  <option value={i + 1} key={i}>
                    {i + 1}
                  </option>
                ))}
              </select>
            </label>
            <span aria-hidden="true">×</span>
            <label>
              Columnas
              <select
                aria-label="Columnas"
                value={columns}
                onChange={(e) => changeGrid(rows, Number(e.target.value))}
              >
                {Array.from({ length: 6 }, (_, i) => (
                  <option value={i + 1} key={i}>
                    {i + 1}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <button
            type="button"
            id="mesa-add-view"
            disabled={
              !data.components.length || !available || tab.panels.length >= 36
            }
            onClick={() => addView()}
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
          {renderSelectionActions?.(visiblePanels)}
        </div>
        {layoutError && (
          <p className="mesa-space-error" role="alert">
            {layoutError}
          </p>
        )}
        <div
          className="mesa-grid"
          data-layout={tab.layout}
          style={{
            gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr)) 20px`,
            gridTemplateRows: Array.from({ length: rows }, (_, i) =>
              tab.row_heights?.[i]
                ? `${tab.row_heights[i]}px`
                : "var(--mesa-grid-row-height, 236px)",
            ).join(" "),
          }}
          role="tabpanel"
          id="mesa-tab-content"
          aria-labelledby={`mesa-tab-${tab.id}`}
        >
          {visiblePanels.map((panel) => (
            <div
              className="mesa-cell"
              key={panel.id}
              style={
                {
                  gridRow: `${panel.placement!.row} / span ${panel.placement!.row_span ?? 1}`,
                  gridColumn: `${panel.placement!.column} / span ${panel.placement!.column_span ?? 1}`,
                  "--mesa-panel-height": "100%",
                  "--mesa-mobile-height": tab.row_heights?.[
                    panel.placement!.row - 1
                  ]
                    ? `${tab.row_heights[panel.placement!.row - 1]}px`
                    : undefined,
                } as CSSProperties
              }
            >
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
          {Array.from({ length: rows * columns }, (_, index) => {
            const row = Math.floor(index / columns) + 1;
            const column = (index % columns) + 1;
            if (
              visiblePanels.some((panel) =>
                contains(panel.placement!, row, column),
              )
            )
              return null;
            return (
              <button
                type="button"
                className="mesa-empty-cell"
                key={`empty-${row}-${column}`}
                style={{ gridRow: row, gridColumn: column }}
                disabled={!data.components.length || tab.panels.length >= 36}
                aria-label={`Agregar vista en fila ${row}, columna ${column}`}
                onClick={() =>
                  addView({ row, column, row_span: 1, column_span: 1 })
                }
              >
                <span aria-hidden="true">＋</span>
                <span>Agregar aquí</span>
                <small>
                  Fila {row} · Columna {column}
                </small>
              </button>
            );
          })}
          {Array.from({ length: rows }, (_, index) => (
            <MesaRow
              key={`${tab.id}:${tab.layout}:${index}`}
              index={index}
              height={tab.row_heights?.[index]}
              onResize={(height) => {
                if (tab.row_heights?.[index] === height) return;
                const row_heights = Array.from(
                  {
                    length: Math.max(rows, tab.row_heights?.length ?? 0),
                  },
                  (_, i) =>
                    i === index ? height : (tab.row_heights?.[i] ?? null),
                );
                update({
                  ...configuration,
                  tabs: configuration.tabs.map((item) =>
                    item.id === tab.id ? { ...item, row_heights } : item,
                  ),
                });
              }}
            />
          ))}
        </div>
        {!available && (
          <p className="mesa-grid-hint">
            Cuadrícula completa. Agrega filas o columnas, o reduce el espacio de
            una vista para añadir otra.
          </p>
        )}
        {!tab.panels.length && (
          <p role="status">
            {data.components.length
              ? "Esta pestaña no tiene vistas. Agrega una vista para consultar sus series."
              : "Este caso no tiene componentes eléctricos disponibles."}
          </p>
        )}
        {tab.panels.length > visiblePanels.length && (
          <p>
            {tab.panels.length - visiblePanels.length} vistas ocultas; se
            conservan al ampliar.
          </p>
        )}
      </fieldset>
      {editing && (
        <PanelDialog
          data={data}
          initial={editing}
          tab={tab}
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
          onApply={(panel) => {
            updatePanel(panel);
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
