import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, vi } from "vitest";

import { App } from "./App";

const period = {
  start: "2026-01-01T00:00:00-03:00",
  end: "2026-01-01T02:00:00-03:00",
};
const project = { id: 1, name: "Planta Norte", description: "" };
const scenario = { id: 10, project_id: 1, name: "Invierno", description: "" };
const version = {
  id: 41,
  scenario_id: 10,
  version_number: 3,
  case_name: "Caso de invierno",
  schema_version: "bess_system_dispatch.v2",
  period_count: 2,
  asset_counts: { battery: 1 },
  created_at: "2026-09-12T12:00:00Z",
  system_case_json: { case_name: "Snapshot de invierno" },
  validation_payload: { status: "ok" },
  generation_metadata: {
    kind: "case_input_variant",
    date_range: period,
    input_variant: { id: 5, display_name: "Base de invierno" },
  },
};
const run = {
  id: 99,
  scenario_version_id: 41,
  status: "succeeded",
  created_at: "2026-09-12T12:00:00Z",
  started_at: "2026-09-12T12:00:01Z",
  finished_at: "2026-09-12T12:00:03Z",
  duration_seconds: 2,
  exit_code: 0,
  error_message: "",
  error_payload: {},
  stdout: "",
  stderr: "",
};
const results = {
  summary: {
    case_name: "Caso de invierno",
    objective_value_usd: 1250.5,
    solver_status: "OPTIMAL",
  },
  charts: {},
  dispatch_table: { columns: [], rows: [] },
  asset_dispatch_table: { columns: [], rows: [] },
};
function serveResults(
  handler: (
    path: string,
    init?: RequestInit,
  ) => Response | Promise<Response> | undefined = () => undefined,
) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = String(input);
      const handled = handler(path, init);
      if (handled) return handled;
      if (path === "/api/auth/me")
        return Response.json({
          user: {
            id: 7,
            email: "analyst@example.local",
            role: "analyst",
            is_active: true,
          },
          bootstrap_required: false,
          landing_path: "/react/projects",
        });
      if (path === "/api/runs/99") return Response.json({ run });
      if (path === "/api/runs/99/results") return Response.json({ results });
      if (path === "/api/runs/99/artifacts")
        return Response.json({
          artifacts: [
            {
              id: 11,
              display_name: "summary.json",
              artifact_type: "summary_json",
              media_type: "application/json",
              byte_size: 92,
              download_url: "/api/run-artifacts/11/download",
            },
          ],
        });
      if (path === "/api/runs/99/publications")
        return Response.json({ publications: [] });
      if (path === "/api/scenario-versions/41")
        return Response.json({ scenario_version: version });
      if (path === "/api/scenarios/10") return Response.json({ scenario });
      if (path === "/api/scenarios/10/versions")
        return Response.json({ versions: [version] });
      if (path === "/api/scenarios/10/runs")
        return Response.json({ runs: [run] });
      if (path === "/api/projects/1") return Response.json({ project });
      if (path === "/api/projects/1/dashboard-templates")
        return Response.json({ dashboard_templates: [] });
      return Response.json({ detail: `Unhandled ${path}` }, { status: 404 });
    }),
  );
}

it("saves a report draft from the chosen result and opens its client preview without publishing", async () => {
  window.history.replaceState({}, "", "/react/runs/99");
  let publication: Record<string, unknown> | undefined;
  serveResults((path, init) => {
    if (path === "/api/auth/csrf")
      return Response.json({ csrf_token: "test-token" });
    if (path === "/api/projects/1/dashboard-templates")
      return Response.json({
        dashboard_templates: [
          { id: 5, project_id: 1, name: "Informe mensual", config: {} },
        ],
      });
    if (path === "/api/runs/99/publications") {
      if (init?.method === "POST") {
        publication = {
          ...JSON.parse(String(init.body)),
          id: 7,
          run_id: 99,
          project_id: 1,
          status: "draft",
        };
        return Response.json({ publication });
      }
      return Response.json({ publications: publication ? [publication] : [] });
    }
    if (path === "/api/publications/7/preview")
      return Response.json({
        publication,
        branding: { display_name: "Planta Norte", logo_url: null },
        period,
        results_state: "available",
        results_block: {
          labels: { kpis: "Resumen", charts: "", tables: "", downloads: "" },
          kpis: [
            {
              id: "beneficio",
              label: "Beneficio total",
              value: 1250.5,
              unit: "USD",
              decimals: 1,
              sign: "auto",
              emphasis: "normal",
            },
          ],
          charts: [],
          tables: [],
        },
        downloads: [],
        preview_context: {
          run_id: 99,
          scenario_version_number: 3,
          results_error: "",
        },
      });
  });
  const user = userEvent.setup();
  render(<App />);
  await user.click(
    await screen.findByRole("link", { name: "Preparar informe" }),
  );
  await user.type(
    await screen.findByLabelText("Título del informe"),
    "Informe de invierno",
  );
  await user.click(screen.getByRole("button", { name: "Guardar borrador" }));
  expect(
    await screen.findByText(
      "Borrador guardado. Todavía no es visible en el portal.",
    ),
  ).toBeVisible();
  await user.click(
    screen.getByRole("link", { name: "Vista previa de Informe de invierno" }),
  );
  expect(
    await screen.findByRole("heading", { name: "Informe de invierno" }),
  ).toBeVisible();
  expect(screen.getByText("1250.5")).toBeVisible();
  expect(
    screen.getByRole("link", { name: "Volver al resultado" }),
  ).toHaveAttribute("href", "/react/runs/99#publications");
  expect(
    screen.getByRole("navigation", { name: "Preparar informe" }),
  ).toHaveTextContent("ResultadoContenidoVista previaPublicación");
});

it("publishes explicitly from the preview and offers the authorized portal link and unpublishing", async () => {
  window.history.replaceState({}, "", "/react/publications/7/preview");
  let status = "draft";
  serveResults((path, init) => {
    const publication = () => ({
      id: 7,
      project_id: 1,
      run_id: 99,
      public_title: "Informe de invierno",
      status,
      allowed_artifact_types: [],
    });
    if (path === "/api/auth/csrf")
      return Response.json({ csrf_token: "test-token" });
    if (init?.method === "POST" && path === "/api/publications/7/publish") {
      status = "published";
      return Response.json({ publication: publication() });
    }
    if (init?.method === "POST" && path === "/api/publications/7/unpublish") {
      status = "unpublished";
      return Response.json({ publication: publication() });
    }
    if (path === "/api/publications/7/preview")
      return Response.json({
        publication: publication(),
        branding: { display_name: "Planta Norte", logo_url: null },
        period,
        results_state: "unavailable",
        results_block: null,
        downloads: [],
        preview_context: {
          run_id: 99,
          scenario_version_number: 3,
          results_error: "No hay resultados",
        },
      });
  });
  const user = userEvent.setup();
  render(<App />);
  await user.click(
    await screen.findByRole("button", { name: "Publicar informe" }),
  );
  const actions = await screen.findByRole("region", { name: "Publicación" });
  expect(await within(actions).findByText("Publicado")).toBeVisible();
  expect(
    within(actions).getByRole("link", { name: "Enlace para el cliente" }),
  ).toHaveAttribute("href", "/react/client/projects/1/publications/7");
  await user.click(screen.getByRole("button", { name: "Despublicar informe" }));
  expect(await within(actions).findByText("Despublicado")).toBeVisible();
  expect(
    within(actions).queryByRole("link", { name: "Enlace para el cliente" }),
  ).not.toBeInTheDocument();
});

it("leads from an unconfigured report to the activation field and back to the chosen result", async () => {
  window.history.replaceState({}, "", "/react/runs/99");
  serveResults((path) => {
    if (path === "/api/projects/1/portal-configuration")
      return Response.json({
        portal_configuration: {
          project_id: 1,
          revision: 0,
          has_logo: false,
          status: "draft",
          document: {
            schema_version: "portal_config.v1",
            display_name: "",
            sections: {
              kpis: { enabled: false, label: "Resumen", items: [] },
              charts: { enabled: false, label: "Gráficos", items: [] },
              tables: { enabled: false, label: "Tablas", items: [] },
              downloads: { enabled: false, label: "Descargas" },
            },
          },
        },
      });
    if (path === "/api/projects/1/scenarios")
      return Response.json({ scenarios: [] });
    if (path === "/api/portal-catalogs")
      return Response.json({ charts: [], tables: [] });
  });
  const user = userEvent.setup();
  render(<App />);
  await user.click(
    await screen.findByRole("link", {
      name: "Activar configuración del informe",
    }),
  );
  expect(await screen.findByLabelText("Estado")).toHaveFocus();
  expect(screen.getByLabelText("Estado")).toHaveValue("draft");
  await user.click(
    screen.getByRole("link", {
      name: "Volver a preparar el informe de la ejecución 99",
    }),
  );
  expect(await screen.findByText("1.250,5 USD")).toBeVisible();
  expect(window.location.pathname).toBe("/react/runs/99");
});

it("requires saving or cancelling an edited draft before previewing or publishing it", async () => {
  window.history.replaceState({}, "", "/react/runs/99");
  serveResults((path) => {
    if (path === "/api/projects/1/dashboard-templates")
      return Response.json({
        dashboard_templates: [
          { id: 5, project_id: 1, name: "Mensual", config: {} },
        ],
      });
    if (path === "/api/runs/99/publications")
      return Response.json({
        publications: [
          {
            id: 7,
            project_id: 1,
            run_id: 99,
            dashboard_template_id: 5,
            public_title: "Invierno",
            status: "draft",
            allowed_artifact_types: ["summary_json"],
          },
        ],
      });
  });
  const user = userEvent.setup();
  render(<App />);
  await user.click(
    await screen.findByRole("button", { name: "Editar borrador Invierno" }),
  );
  await user.type(
    screen.getByLabelText("Título del informe editado"),
    " revisado",
  );
  expect(
    screen.getByRole("button", { name: "Publicar Invierno" }),
  ).toBeDisabled();
  expect(
    screen.queryByRole("link", { name: "Vista previa de Invierno" }),
  ).not.toBeInTheDocument();
  expect(
    screen.getByText(
      "Guarda o cancela la edición antes de abrir la vista previa o publicar.",
    ),
  ).toBeVisible();
  await user.click(screen.getByRole("button", { name: "Cancelar" }));
  expect(
    screen.getByRole("link", { name: "Vista previa de Invierno" }),
  ).toBeVisible();
});
