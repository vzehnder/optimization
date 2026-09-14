import { act, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { App } from "./App";

const values = [
  { timestamp: "2026-01-01T00:00:00+00:00", hours: "1", price: "55" },
  { timestamp: "2026-01-01T01:00:00+00:00", hours: "1", price: "60" },
];
function serveImport(
  options: {
    xlsx?: boolean;
    protected?: boolean;
    uncertain?: boolean;
    manyRows?: boolean;
    lastRowError?: boolean;
  } = {},
) {
  let storedRows = values.map((row) => ({ ...row }));
  if (options.xlsx) storedRows[0].price = "1,234";
  if (options.manyRows)
    storedRows = [
      ...Array.from({ length: 50 }, () => ({ ...values[0] })),
      { ...values[1], price: "999" },
    ];
  const source = {
    id: "csv_1",
    kind: "csv",
    original_filename: "precios.csv",
    columns: ["timestamp", "hours", "price"],
    preview_rows: values,
  };
  const doc = {
    schema_version: "bess_editor_draft.v1",
    case: { name: "Invierno" },
    pcc: { id: "bus_1", type: "bus" },
    grid: { id: "grid_1" },
    assets: [],
    solver: { name: "HiGHS" },
    time_series: { sources: [] },
  };
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = String(input);
      if (path === "/api/auth/me")
        return Response.json({
          user: {
            id: 1,
            email: "test@example.local",
            role: "analyst",
            is_active: true,
          },
          bootstrap_required: false,
        });
      if (path === "/api/auth/csrf")
        return Response.json({ csrf_token: "test" });
      if (path === "/api/projects/1")
        return Response.json({ project: { id: 1, name: "Planta Norte" } });
      if (path === "/api/scenarios/10")
        return Response.json({
          scenario: { id: 10, project_id: 1, name: "Invierno" },
        });
      if (path === "/api/scenarios/10/draft")
        return Response.json({
          draft: { id: 1, scenario_id: 10, document: doc },
        });
      if (path.endsWith("/time-series-import-options"))
        return Response.json({
          mode: options.protected ? "protected" : "project_catalog",
        });
      if (path === "/api/time-series/signal-catalog")
        return Response.json({
          signals: [
            {
              signal_key: "price_usd_per_mwh",
              unit: "USD/MWh",
              entity_type: null,
              nonnegative: false,
            },
          ],
        });
      if (
        path.endsWith("/upload") &&
        ((init?.body as FormData).get("source_file") as File)?.name ===
          "unreadable.xlsx"
      )
        return Response.json({ detail: "Archivo ilegible" }, { status: 400 });
      if (path.endsWith("/upload"))
        return Response.json(
          {
            source: options.xlsx
              ? {
                  ...source,
                  id: "xlsx_1",
                  kind: "xlsx",
                  available_sheets: ["Notas", "Precios"],
                  selected_sheet:
                    (init?.body as FormData).get("sheet_name") || "Notas",
                  original_filename: "precios.xlsx",
                }
              : source,
          },
          { status: 201 },
        );
      if (path.endsWith("/rows")) {
        if (init?.method === "PUT") {
          storedRows = JSON.parse(String(init.body)).rows;
          return Response.json({
            source: { ...source, preview_rows: storedRows },
          });
        }
        return Response.json({ columns: source.columns, rows: storedRows });
      }
      if (path.endsWith("/catalog-preview")) {
        if (options.lastRowError)
          return Response.json(
            {
              detail: "Valor inválido",
              location: { sheet: null, row: 52, column: "price" },
            },
            { status: 400 },
          );
        if (storedRows[0].price === "1,234")
          return Response.json(
            {
              detail: "Valor numérico ambiguo",
              location: { sheet: "Precios", row: 2, column: "price" },
            },
            { status: 400 },
          );
        return Response.json({
          preview: {
            period_count: 2,
            coverage_start: values[0].timestamp,
            coverage_end: "2026-01-01T02:00:00+00:00",
            resolution_hours: 1,
            signals: [
              {
                signal_key: "price_usd_per_mwh",
                unit: "USD/MWh",
                source_column: "price",
              },
            ],
            rows: storedRows.map((row) => ({
              timestamp_start: row.timestamp,
              price_usd_per_mwh: Number(row.price),
            })),
          },
        });
      }
      if (path.endsWith("/catalog-import") && options.uncertain)
        throw new TypeError("Failed to fetch");
      if (path.endsWith("/catalog-import"))
        return Response.json(
          {
            time_series_set: {
              id: 31,
              project_id: 1,
              name: "Precios enero",
              revision_number: 1,
              period_count: 2,
              signals: [{ signal_key: "price_usd_per_mwh", unit: "USD/MWh" }],
            },
          },
          { status: 201 },
        );
      return Response.json({ detail: path }, { status: 404 });
    }),
  );
}

describe("guided time-series import", () => {
  it("keeps one submission in flight when confirmation is double clicked", async () => {
    window.history.replaceState({}, "", "/react/scenarios/10/draft");
    serveImport();
    const respond = vi.mocked(fetch).getMockImplementation()!;
    let release = () => {};
    const pending = new Promise<void>((resolve) => {
      release = resolve;
    });
    let submissions = 0;
    vi.mocked(fetch).mockImplementation(async (input, init) => {
      if (String(input).endsWith("/catalog-import")) {
        submissions += 1;
        await pending;
      }
      return respond(input, init);
    });
    const user = userEvent.setup();
    render(<App />);
    const wizard = await screen.findByRole("region", {
      name: "Importar series de tiempo",
    });
    await user.upload(
      within(wizard).getByLabelText("Archivo CSV o XLSX"),
      new File(["timestamp,hours,price\n"], "precios.csv", {
        type: "text/csv",
      }),
    );
    await user.click(
      within(wizard).getByRole("button", { name: "Continuar a columnas" }),
    );
    await user.selectOptions(
      await within(wizard).findByLabelText("Columna de valores 1"),
      "price",
    );
    await user.selectOptions(
      within(wizard).getByLabelText("Señal 1"),
      "price_usd_per_mwh",
    );
    await user.click(
      within(wizard).getByRole("button", {
        name: "Confirmar columnas y revisar",
      }),
    );
    await user.click(
      await within(wizard).findByRole("button", { name: "Comprobar datos" }),
    );
    await user.click(
      await within(wizard).findByRole("button", {
        name: "Continuar a importación",
      }),
    );
    const confirm = within(wizard).getByRole("button", {
      name: "Confirmar importación",
    });
    await user.dblClick(confirm);
    expect(confirm).toBeDisabled();
    expect(submissions).toBe(1);
    await act(async () => release());
    expect(
      await within(wizard).findByRole("link", { name: "Abrir Precios enero" }),
    ).toBeVisible();
    expect(submissions).toBe(1);
  });
  it("opens the page containing a reported error and focuses that cell", async () => {
    window.history.replaceState({}, "", "/react/scenarios/10/draft");
    serveImport({ manyRows: true, lastRowError: true });
    const user = userEvent.setup();
    render(<App />);
    const wizard = await screen.findByRole("region", {
      name: "Importar series de tiempo",
    });
    await user.upload(
      within(wizard).getByLabelText("Archivo CSV o XLSX"),
      new File(["timestamp,hours,price\n"], "precios.csv", {
        type: "text/csv",
      }),
    );
    await user.click(
      within(wizard).getByRole("button", { name: "Continuar a columnas" }),
    );
    await user.selectOptions(
      await within(wizard).findByLabelText("Columna de valores 1"),
      "price",
    );
    await user.selectOptions(
      within(wizard).getByLabelText("Señal 1"),
      "price_usd_per_mwh",
    );
    await user.click(
      within(wizard).getByRole("button", {
        name: "Confirmar columnas y revisar",
      }),
    );
    await user.click(
      await within(wizard).findByRole("button", { name: "Comprobar datos" }),
    );
    await user.click(
      await within(wizard).findByRole("button", {
        name: "Corregir fila 52, columna price",
      }),
    );
    expect(within(wizard).getByLabelText("Fila 52, price")).toHaveFocus();
  });
  it("labels proposed columns and shows source examples, units and scope before explicit confirmation", async () => {
    window.history.replaceState({}, "", "/react/scenarios/10/draft");
    serveImport();
    const user = userEvent.setup();
    render(<App />);
    const wizard = await screen.findByRole("region", {
      name: "Importar series de tiempo",
    });
    await user.upload(
      within(wizard).getByLabelText("Archivo CSV o XLSX"),
      new File(["timestamp,hours,price\n"], "precios.csv", {
        type: "text/csv",
      }),
    );
    await user.click(
      within(wizard).getByRole("button", { name: "Continuar a columnas" }),
    );
    expect(
      await within(wizard).findByText(/Propuestas por coincidencia exacta/),
    ).toBeVisible();
    await user.selectOptions(
      within(wizard).getByLabelText("Columna de valores 1"),
      "price",
    );
    await user.selectOptions(
      within(wizard).getByLabelText("Señal 1"),
      "price_usd_per_mwh",
    );
    const examples = within(wizard).getByRole("table", {
      name: "Ejemplos de columnas seleccionadas",
    });
    expect(examples).toHaveTextContent("55");
    expect(examples).toHaveTextContent("USD/MWh");
    expect(examples).toHaveTextContent("Global");
    expect(examples).toHaveTextContent("2026-01-01T00:00:00+00:00");
    expect(
      within(wizard).getByRole("button", {
        name: "Confirmar columnas y revisar",
      }),
    ).toBeEnabled();
  });
  it("lets the analyst correct rows beyond the first window without losing earlier edits", async () => {
    window.history.replaceState({}, "", "/react/scenarios/10/draft");
    serveImport({ manyRows: true });
    const user = userEvent.setup();
    render(<App />);
    const wizard = await screen.findByRole("region", {
      name: "Importar series de tiempo",
    });
    await user.upload(
      within(wizard).getByLabelText("Archivo CSV o XLSX"),
      new File(["timestamp,hours,price\n"], "precios.csv", {
        type: "text/csv",
      }),
    );
    await user.click(
      within(wizard).getByRole("button", { name: "Continuar a columnas" }),
    );
    await user.selectOptions(
      await within(wizard).findByLabelText("Columna de valores 1"),
      "price",
    );
    await user.selectOptions(
      within(wizard).getByLabelText("Señal 1"),
      "price_usd_per_mwh",
    );
    await user.click(
      within(wizard).getByRole("button", {
        name: "Confirmar columnas y revisar",
      }),
    );
    await user.clear(await within(wizard).findByLabelText("Fila 2, price"));
    await user.type(within(wizard).getByLabelText("Fila 2, price"), "70");
    await user.click(
      within(wizard).getByRole("button", { name: "Filas siguientes" }),
    );
    expect(within(wizard).getByLabelText("Fila 52, price")).toHaveValue("999");
    await user.click(
      within(wizard).getByRole("button", { name: "Filas anteriores" }),
    );
    expect(within(wizard).getByLabelText("Fila 2, price")).toHaveValue("70");
  });
  it("explains staging and preserves the import when cancelling navigation away", async () => {
    window.history.replaceState({}, "", "/react/scenarios/10/draft");
    serveImport();
    const user = userEvent.setup();
    render(<App />);
    const wizard = await screen.findByRole("region", {
      name: "Importar series de tiempo",
    });
    await user.upload(
      within(wizard).getByLabelText("Archivo CSV o XLSX"),
      new File(["timestamp,hours,price\n"], "precios.csv", {
        type: "text/csv",
      }),
    );
    await user.click(
      within(wizard).getByRole("button", { name: "Continuar a columnas" }),
    );
    await within(wizard).findByLabelText("Columna de valores 1");
    await user.click(screen.getAllByRole("link", { name: "Proyectos" })[0]);
    const dialog = await screen.findByRole("dialog", {
      name: "Cambios sin guardar",
    });
    expect(dialog).toHaveTextContent("La fuente temporal permanece guardada");
    expect(dialog).toHaveTextContent(
      "El mapeo y las correcciones pendientes no se publicaron",
    );
    await user.click(
      within(dialog).getByRole("button", { name: "Seguir editando" }),
    );
    expect(within(wizard).getByLabelText("Nombre del conjunto")).toHaveValue(
      "precios",
    );
  });
  it("preserves an uncertain import and requires checking the catalog before another attempt", async () => {
    window.history.replaceState({}, "", "/react/scenarios/10/draft");
    serveImport({ uncertain: true });
    const user = userEvent.setup();
    render(<App />);
    const wizard = await screen.findByRole("region", {
      name: "Importar series de tiempo",
    });
    await user.upload(
      within(wizard).getByLabelText("Archivo CSV o XLSX"),
      new File(["timestamp,hours,price\n"], "precios.csv", {
        type: "text/csv",
      }),
    );
    await user.click(
      within(wizard).getByRole("button", { name: "Continuar a columnas" }),
    );
    await user.selectOptions(
      await within(wizard).findByLabelText("Columna de valores 1"),
      "price",
    );
    await user.selectOptions(
      within(wizard).getByLabelText("Señal 1"),
      "price_usd_per_mwh",
    );
    await user.click(
      within(wizard).getByRole("button", {
        name: "Confirmar columnas y revisar",
      }),
    );
    await user.click(
      await within(wizard).findByRole("button", { name: "Comprobar datos" }),
    );
    await user.click(
      await within(wizard).findByRole("button", {
        name: "Continuar a importación",
      }),
    );
    await user.click(
      within(wizard).getByRole("button", { name: "Confirmar importación" }),
    );
    expect(
      await within(wizard).findByText(/No pudimos confirmar si se importó/),
    ).toBeVisible();
    expect(
      within(wizard).getByRole("button", { name: "Confirmar importación" }),
    ).toBeDisabled();
    expect(
      within(wizard).getByRole("link", { name: "Comprobar el catálogo" }),
    ).toHaveAttribute("href", "/react/projects/1/time-series-sets");
    expect(
      within(wizard).getByRole("table", { name: "Datos que se importarán" }),
    ).toHaveTextContent("55");
    await user.click(
      within(wizard).getByRole("button", {
        name: "Ya revisé el catálogo; permitir nuevo intento",
      }),
    );
    expect(
      within(wizard).getByRole("button", { name: "Confirmar importación" }),
    ).toBeEnabled();
  });
  it("directs canonical imports to the model need instead of offering a legacy writer", async () => {
    window.history.replaceState({}, "", "/react/scenarios/10/draft");
    serveImport({ protected: true });
    render(<App />);
    expect(
      await screen.findByRole("link", {
        name: "Elegir la necesidad del modelo para importar",
      }),
    ).toHaveAttribute("href", "/react/scenarios/10?section=data");
    expect(
      screen.queryByLabelText("Archivo CSV o XLSX"),
    ).not.toBeInTheDocument();
  });
  it("selects an XLSX sheet and focuses the invalid cell so it can be corrected", async () => {
    window.history.replaceState({}, "", "/react/scenarios/10/draft");
    serveImport({ xlsx: true });
    const user = userEvent.setup();
    render(<App />);
    const wizard = await screen.findByRole("region", {
      name: "Importar series de tiempo",
    });
    await user.upload(
      within(wizard).getByLabelText("Archivo CSV o XLSX"),
      new File(["xlsx"], "precios.xlsx", {
        type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      }),
    );
    await user.click(
      within(wizard).getByRole("button", { name: "Continuar a columnas" }),
    );
    await user.selectOptions(
      await within(wizard).findByRole("combobox", { name: "Hoja" }),
      "Precios",
    );
    await user.selectOptions(
      within(wizard).getByLabelText("Columna de valores 1"),
      "price",
    );
    await user.selectOptions(
      within(wizard).getByLabelText("Señal 1"),
      "price_usd_per_mwh",
    );
    await user.click(
      within(wizard).getByRole("button", {
        name: "Confirmar columnas y revisar",
      }),
    );
    await user.click(
      await within(wizard).findByRole("button", { name: "Comprobar datos" }),
    );
    await user.click(
      await within(wizard).findByRole("button", {
        name: "Corregir hoja Precios, fila 2, columna price",
      }),
    );
    expect(within(wizard).getByLabelText("Fila 2, price")).toHaveFocus();
    await user.clear(within(wizard).getByLabelText("Fila 2, price"));
    await user.type(within(wizard).getByLabelText("Fila 2, price"), "70");
    await user.click(
      within(wizard).getByRole("button", { name: "Volver a columnas" }),
    );
    await user.click(
      within(wizard).getByRole("button", { name: "Volver a archivo" }),
    );
    await user.upload(
      within(wizard).getByLabelText("Archivo CSV o XLSX"),
      new File(["bad"], "unreadable.xlsx", {
        type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      }),
    );
    await user.click(
      within(wizard).getByRole("button", { name: "Continuar a columnas" }),
    );
    expect(await within(wizard).findByText("Archivo ilegible")).toBeVisible();
    await user.click(
      within(wizard).getByRole("button", {
        name: "Continuar con la fuente guardada",
      }),
    );
    await user.selectOptions(
      within(wizard).getByRole("combobox", { name: "Hoja" }),
      "Notas",
    );
    expect(within(wizard).getByRole("combobox", { name: "Hoja" })).toHaveValue(
      "Notas",
    );
    await user.selectOptions(
      within(wizard).getByRole("combobox", { name: "Hoja" }),
      "Precios",
    );
    await user.click(
      within(wizard).getByRole("button", {
        name: "Confirmar columnas y revisar",
      }),
    );
    expect(await within(wizard).findByLabelText("Fila 2, price")).toHaveValue(
      "70",
    );
    await user.click(
      within(wizard).getByRole("button", {
        name: "Guardar correcciones en la fuente temporal",
      }),
    );
    await user.click(
      within(wizard).getByRole("button", { name: "Comprobar datos" }),
    );
    expect(
      await within(wizard).findByRole("table", {
        name: "Datos que se importarán",
      }),
    ).toBeVisible();
  });
  it("keeps column choices and edited values when going back before saving and checking", async () => {
    window.history.replaceState({}, "", "/react/scenarios/10/draft");
    serveImport();
    const user = userEvent.setup();
    render(<App />);
    const wizard = await screen.findByRole("region", {
      name: "Importar series de tiempo",
    });
    await user.upload(
      within(wizard).getByLabelText("Archivo CSV o XLSX"),
      new File(["timestamp,hours,price\n"], "precios.csv", {
        type: "text/csv",
      }),
    );
    await user.click(
      within(wizard).getByRole("button", { name: "Continuar a columnas" }),
    );
    await user.selectOptions(
      await within(wizard).findByLabelText("Columna de valores 1"),
      "price",
    );
    await user.selectOptions(
      within(wizard).getByLabelText("Señal 1"),
      "price_usd_per_mwh",
    );
    await user.click(
      within(wizard).getByRole("button", {
        name: "Confirmar columnas y revisar",
      }),
    );
    await user.clear(await within(wizard).findByLabelText("Fila 2, price"));
    await user.type(within(wizard).getByLabelText("Fila 2, price"), "70");
    expect(
      within(wizard).getByRole("button", { name: "Comprobar datos" }),
    ).toBeDisabled();
    await user.click(
      within(wizard).getByRole("button", { name: "Volver a columnas" }),
    );
    expect(within(wizard).getByLabelText("Columna de valores 1")).toHaveValue(
      "price",
    );
    await user.click(
      within(wizard).getByRole("button", { name: "Volver a archivo" }),
    );
    expect(
      within(wizard).getByText("precios.csv", { exact: true }),
    ).toBeVisible();
    await user.click(
      within(wizard).getByRole("button", {
        name: "Continuar a columnas",
      }),
    );
    await user.click(
      within(wizard).getByRole("button", {
        name: "Confirmar columnas y revisar",
      }),
    );
    expect(await within(wizard).findByLabelText("Fila 2, price")).toHaveValue(
      "70",
    );
    await user.click(
      within(wizard).getByRole("button", {
        name: "Guardar correcciones en la fuente temporal",
      }),
    );
    await user.click(
      within(wizard).getByRole("button", { name: "Comprobar datos" }),
    );
    const preview = await within(wizard).findByRole("table", {
      name: "Datos que se importarán",
    });
    expect(within(preview).getByRole("cell", { name: "70" })).toBeVisible();
  });
  it("reviews a CSV and explicitly imports it with a link to its resource and original scenario", async () => {
    window.history.replaceState({}, "", "/react/scenarios/10/draft");
    serveImport();
    const user = userEvent.setup();
    render(<App />);
    const wizard = await screen.findByRole("region", {
      name: "Importar series de tiempo",
    });
    await user.upload(
      within(wizard).getByLabelText("Archivo CSV o XLSX"),
      new File(["timestamp,hours,price\n"], "precios.csv", {
        type: "text/csv",
      }),
    );
    await user.click(
      within(wizard).getByRole("button", { name: "Continuar a columnas" }),
    );
    expect(
      await within(wizard).findByText(/Fuente temporal guardada/),
    ).toBeVisible();
    expect(
      within(wizard).queryByRole("combobox", { name: "Hoja" }),
    ).not.toBeInTheDocument();
    await user.clear(within(wizard).getByLabelText("Nombre del conjunto"));
    await user.type(
      within(wizard).getByLabelText("Nombre del conjunto"),
      "Precios enero",
    );
    await user.selectOptions(
      within(wizard).getByLabelText("Columna de valores 1"),
      "price",
    );
    await user.selectOptions(
      within(wizard).getByLabelText("Señal 1"),
      "price_usd_per_mwh",
    );
    await user.click(
      within(wizard).getByRole("button", {
        name: "Confirmar columnas y revisar",
      }),
    );
    expect(
      await within(wizard).findByRole("heading", { name: "Revisar datos" }),
    ).toBeVisible();
    await user.click(
      within(wizard).getByRole("button", { name: "Comprobar datos" }),
    );
    const preview = await within(wizard).findByRole("table", {
      name: "Datos que se importarán",
    });
    expect(within(preview).getByRole("cell", { name: "55" })).toBeVisible();
    expect(within(preview).getByRole("cell", { name: "60" })).toBeVisible();
    await user.click(
      within(wizard).getByRole("button", { name: "Continuar a importación" }),
    );
    expect(
      within(wizard).getByText(/Conjunto nuevo del proyecto/),
    ).toBeVisible();
    await user.click(
      within(wizard).getByRole("button", { name: "Confirmar importación" }),
    );
    expect(
      await within(wizard).findByRole("link", { name: "Abrir Precios enero" }),
    ).toHaveAttribute("href", "/react/projects/1/time-series-sets/31");
    expect(
      within(wizard).getByRole("link", {
        name: "Volver a los datos del escenario",
      }),
    ).toHaveAttribute("href", "/react/scenarios/10?section=data");
    expect(within(wizard).getByText(/Falta elegir esta fuente/)).toBeVisible();
  });
});
