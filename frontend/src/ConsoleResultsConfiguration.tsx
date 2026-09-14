import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import {
  getPortalCatalogs,
  type OperatorConsoleDocument,
  type PortalConfigKpiItem,
  type PortalConfigChartItem,
  type PortalConfigTableItem,
} from "./api/client";

type Results = OperatorConsoleDocument["results"];

function nextId(prefix: string, items: Array<{ id: string }>) {
  let number = items.length + 1;
  while (items.some((item) => item.id === `${prefix}_${number}`)) number++;
  return `${prefix}_${number}`;
}

export function ConsoleResultsConfiguration({
  value,
  onChange,
}: {
  value: Results;
  onChange: (value: Results) => void;
}) {
  const catalog = useQuery({
    queryKey: ["portal-catalogs"],
    queryFn: ({ signal }) => getPortalCatalogs(signal),
    retry: false,
  });
  const [chartKey, setChartKey] = useState("");
  const [tableKey, setTableKey] = useState("");
  const kpis = value.kpis as PortalConfigKpiItem[];
  const charts = value.charts as PortalConfigChartItem[];
  const tables = value.tables as PortalConfigTableItem[];
  const selectedChart =
    catalog.data?.charts.find((item) => item.key === chartKey) ??
    catalog.data?.charts[0];
  const selectedTable =
    catalog.data?.tables.find((item) => item.key === tableKey) ??
    catalog.data?.tables[0];

  return (
    <section aria-label="Contenido de resultados">
      <h2>Resultados de la consola</h2>
      <p>
        Elige el contenido que verá el operador al abrir una ejecución
        finalizada.
      </p>
      {catalog.isPending ? (
        <p role="status">Consultando opciones de resultados</p>
      ) : null}
      {catalog.isError ? (
        <p role="alert">
          No se pudieron consultar las opciones.{" "}
          <button type="button" onClick={() => void catalog.refetch()}>
            Reintentar opciones
          </button>
        </p>
      ) : null}
      <h3>Indicadores</h3>
      {kpis.map((item, index) => {
        const patch = (changes: Partial<PortalConfigKpiItem>) =>
          onChange({
            ...value,
            kpis: kpis.map((entry, position) =>
              position !== index ? entry : { ...entry, ...changes },
            ),
          });
        return (
          <fieldset key={item.id} className="console-group-fieldset">
            <legend>Indicador {index + 1}</legend>
            <label>
              Resultado (ruta del resumen)
              <input
                required
                value={item.path}
                onChange={(event) => patch({ path: event.target.value })}
                placeholder="objective_value_usd"
              />
            </label>
            <label>
              Etiqueta
              <input
                required
                value={item.label}
                onChange={(event) => patch({ label: event.target.value })}
              />
            </label>
            <label>
              Unidad
              <input
                value={item.unit ?? ""}
                onChange={(event) =>
                  patch({ unit: event.target.value || null })
                }
              />
            </label>
            <label>
              Decimales
              <input
                type="number"
                required
                min={0}
                max={6}
                value={Number.isFinite(item.decimals) ? item.decimals : ""}
                onChange={(event) =>
                  patch({ decimals: event.target.valueAsNumber })
                }
              />
            </label>
            <label>
              Signo
              <select
                value={item.sign}
                onChange={(event) =>
                  patch({
                    sign: event.target.value as PortalConfigKpiItem["sign"],
                  })
                }
              >
                <option value="auto">Automático</option>
                <option value="always">Siempre con signo</option>
                <option value="never">Sin signo</option>
              </select>
            </label>
            <label>
              Énfasis
              <select
                value={item.emphasis}
                onChange={(event) =>
                  patch({
                    emphasis: event.target
                      .value as PortalConfigKpiItem["emphasis"],
                  })
                }
              >
                <option value="normal">Normal</option>
                <option value="strong">Destacado</option>
              </select>
            </label>
            <button
              type="button"
              className="secondary-button"
              onClick={() =>
                onChange({
                  ...value,
                  kpis: kpis.filter((_, position) => position !== index),
                })
              }
            >
              Quitar indicador {index + 1}
            </button>
          </fieldset>
        );
      })}
      <button
        type="button"
        onClick={() =>
          onChange({
            ...value,
            kpis: [
              ...kpis,
              {
                id: nextId("indicador", kpis),
                path: "objective_value_usd",
                label: "Beneficio total",
                unit: "USD",
                decimals: 2,
                sign: "auto",
                emphasis: "normal",
              },
            ],
          })
        }
      >
        Agregar indicador
      </button>
      <h3>Gráficos</h3>
      <label>
        Gráfico disponible
        <select
          value={selectedChart?.key ?? ""}
          onChange={(event) => setChartKey(event.target.value)}
        >
          {!selectedChart ? (
            <option value="">Sin opciones disponibles</option>
          ) : null}
          {catalog.data?.charts.map((item) => (
            <option key={item.key} value={item.key}>
              {item.label}
            </option>
          ))}
        </select>
      </label>
      <button
        type="button"
        disabled={!selectedChart}
        onClick={() => {
          if (selectedChart)
            onChange({
              ...value,
              charts: [
                ...charts,
                {
                  id: nextId("grafico", charts),
                  chart_key: selectedChart.key,
                  label: selectedChart.label,
                  series: selectedChart.series.map((item) => ({
                    key: item.key,
                    label: item.label,
                  })),
                },
              ],
            });
        }}
      >
        Agregar gráfico
      </button>
      {charts.map((item, index) => {
        const patch = (changes: Partial<PortalConfigChartItem>) =>
          onChange({
            ...value,
            charts: charts.map((entry, position) =>
              position !== index ? entry : { ...entry, ...changes },
            ),
          });
        const definition = catalog.data?.charts.find(
          (entry) => entry.key === item.chart_key,
        );
        return (
          <fieldset key={item.id} className="console-group-fieldset">
            <legend>Gráfico {index + 1}</legend>
            <label>
              Etiqueta
              <input
                required
                value={item.label}
                onChange={(event) => patch({ label: event.target.value })}
              />
            </label>
            {definition?.series.map((series) => (
              <label className="checkbox-field" key={series.key}>
                <input
                  type="checkbox"
                  checked={item.series.some(
                    (entry) => entry.key === series.key,
                  )}
                  onChange={(event) =>
                    patch({
                      series: event.target.checked
                        ? [
                            ...item.series,
                            { key: series.key, label: series.label },
                          ]
                        : item.series.filter(
                            (entry) => entry.key !== series.key,
                          ),
                    })
                  }
                />
                {series.label} ({series.unit})
              </label>
            ))}
            {item.series.map((series, position) => (
              <label key={series.key}>
                Etiqueta de {series.key}
                <input
                  required
                  value={series.label}
                  onChange={(event) =>
                    patch({
                      series: item.series.map((entry, row) =>
                        row !== position
                          ? entry
                          : { ...entry, label: event.target.value },
                      ),
                    })
                  }
                />
              </label>
            ))}
            <button
              type="button"
              className="secondary-button"
              onClick={() =>
                onChange({
                  ...value,
                  charts: charts.filter((_, position) => position !== index),
                })
              }
            >
              Quitar gráfico {index + 1}
            </button>
          </fieldset>
        );
      })}
      <h3>Tablas</h3>
      <label>
        Tabla disponible
        <select
          value={selectedTable?.key ?? ""}
          onChange={(event) => setTableKey(event.target.value)}
        >
          {!selectedTable ? (
            <option value="">Sin opciones disponibles</option>
          ) : null}
          {catalog.data?.tables.map((item) => (
            <option key={item.key} value={item.key}>
              {item.label}
            </option>
          ))}
        </select>
      </label>
      <button
        type="button"
        disabled={!selectedTable}
        onClick={() => {
          if (selectedTable)
            onChange({
              ...value,
              tables: [
                ...tables,
                {
                  id: nextId("tabla", tables),
                  table_key: selectedTable.key,
                  label: selectedTable.label,
                  row_limit: 24,
                  columns: [],
                },
              ],
            });
        }}
      >
        Agregar tabla
      </button>
      {tables.map((item, index) => {
        const patch = (changes: Partial<PortalConfigTableItem>) =>
          onChange({
            ...value,
            tables: tables.map((entry, position) =>
              position !== index ? entry : { ...entry, ...changes },
            ),
          });
        const definition = catalog.data?.tables.find(
          (entry) => entry.key === item.table_key,
        );
        return (
          <fieldset key={item.id} className="console-group-fieldset">
            <legend>Tabla {index + 1}</legend>
            <label>
              Etiqueta
              <input
                required
                value={item.label}
                onChange={(event) => patch({ label: event.target.value })}
              />
            </label>
            <label>
              Filas visibles
              <input
                type="number"
                required
                min={1}
                value={Number.isFinite(item.row_limit) ? item.row_limit : ""}
                onChange={(event) =>
                  patch({ row_limit: event.target.valueAsNumber })
                }
              />
            </label>
            {definition?.columns.map((column) => (
              <label className="checkbox-field" key={column.key}>
                <input
                  type="checkbox"
                  checked={item.columns.some(
                    (entry) => entry.key === column.key,
                  )}
                  onChange={(event) =>
                    patch({
                      columns: event.target.checked
                        ? [...item.columns, { ...column, id: column.key }]
                        : item.columns.filter(
                            (entry) => entry.key !== column.key,
                          ),
                    })
                  }
                />
                {column.label}
                {column.unit ? ` (${column.unit})` : ""}
              </label>
            ))}
            {item.columns.map((column, position) => (
              <div key={column.key}>
                <label>
                  Etiqueta de {column.key}
                  <input
                    required
                    value={column.label}
                    onChange={(event) =>
                      patch({
                        columns: item.columns.map((entry, row) =>
                          row !== position
                            ? entry
                            : { ...entry, label: event.target.value },
                        ),
                      })
                    }
                  />
                </label>
                <label>
                  Unidad de {column.key}
                  <input
                    value={column.unit ?? ""}
                    onChange={(event) =>
                      patch({
                        columns: item.columns.map((entry, row) =>
                          row !== position
                            ? entry
                            : { ...entry, unit: event.target.value || null },
                        ),
                      })
                    }
                  />
                </label>
              </div>
            ))}
            <button
              type="button"
              className="secondary-button"
              onClick={() =>
                onChange({
                  ...value,
                  tables: tables.filter((_, position) => position !== index),
                })
              }
            >
              Quitar tabla {index + 1}
            </button>
          </fieldset>
        );
      })}
    </section>
  );
}
