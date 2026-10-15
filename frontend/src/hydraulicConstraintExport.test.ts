import { expect, it } from "vitest";
import {
  buildDiagramConstraintInfo,
  type DiagramConstraintInfo,
} from "./hydraulicConstraintExport";

const info: DiagramConstraintInfo = {
  scenarioId: 788,
  scenarioName: "Canal | Norte <obra>",
  revision: "r17",
  saved: false,
  nodes: [
    {
      technical_key: "embalse",
      display_name: "Embalse",
      component_type: "reservoir",
      x: 0,
      y: 0,
      reservoir: {
        storage_min_hm3: 0,
        storage_max_hm3: 20,
        initial_storage_hm3: 10,
        terminal_condition: "none",
        terminal_storage_min_hm3: null,
        terminal_water_value_usd_per_hm3: 0,
      },
    },
    {
      technical_key: "salida",
      display_name: "Salida",
      component_type: "junction",
      x: 10,
      y: 10,
    },
  ],
  reaches: [
    {
      technical_key: "canal_norte",
      display_name: "Canal Norte",
      from_node_key: "embalse",
      to_node_key: "salida",
      reach_type: "canal",
      flow_min_m3s: 3,
      minimum_flow_series: {
        points: [
          {
            timestamp: "2026-01-01T00:00:00Z",
            duration_hours: 1,
            value_m3s: 4,
          },
        ],
      },
    },
  ],
};

it("exports the current topology, exact data and a detailed independently usable Python guide", () => {
  const markdown = buildDiagramConstraintInfo(info, "2026-09-25T12:00:00Z");
  expect(markdown).toContain("Borrador con cambios sin guardar");
  expect(markdown).toContain("Canal &#124; Norte &lt;obra&gt;");
  expect(markdown).toContain(
    "| canal_norte | Canal Norte | canal | embalse | salida | 3 |",
  );
  expect(markdown).toContain(
    "/react/scenarios/788/hydraulic-reaches/canal_norte/rules",
  );
  expect(markdown).toContain('n1 -->|"canal_norte · canal"| n2');
  expect(markdown).toContain("ctx.objetos.tramo_1.caudal[t]");
  expect(markdown).toContain(
    "ctx.objetos.b.caudal[t] + ctx.objetos.c.caudal[t]",
  );
  expect(markdown).toContain("0.0036");
  expect(markdown).toContain("Fin UTC exclusivo");
  expect(markdown).toContain("Probar restricciones");
  const appendix = markdown.match(/````json\n([\s\S]*?)\n````/)!;
  expect(JSON.parse(appendix[1])).toEqual({
    scenario_id: 788,
    scenario_name: info.scenarioName,
    revision: "r17",
    saved: false,
    nodes: info.nodes,
    reaches: info.reaches,
  });
});

it("reports missing endpoints without fabricating a Mermaid connection or claiming validity", () => {
  const markdown = buildDiagramConstraintInfo({
    ...info,
    saved: true,
    nodes: [],
  });
  expect(markdown).toContain("falta el nodo de origen o destino");
  expect(markdown).not.toContain("undefined -->");
  expect(markdown).toContain("| Estado | Guardado |");
});
