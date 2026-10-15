import type {
  HydraulicDiagramNodeWrite,
  HydraulicDiagramReachWrite,
} from "./api/client";
import guide from "./hydraulicConstraintGuide.md?raw";

export interface DiagramConstraintInfo {
  scenarioId: number;
  scenarioName: string;
  revision: string;
  saved: boolean;
  nodes: HydraulicDiagramNodeWrite[];
  reaches: HydraulicDiagramReachWrite[];
}

const cell = (value: unknown) =>
  String(value ?? "—")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll("|", "&#124;")
    .replaceAll("`", "&#96;")
    .replaceAll("\n", "<br>")
    .replaceAll("\r", "");
const table = (headers: string[], rows: unknown[][]) =>
  [
    `| ${headers.map(cell).join(" | ")} |`,
    `| ${headers.map(() => "---").join(" | ")} |`,
    ...rows.map((row) => `| ${row.map(cell).join(" | ")} |`),
  ].join("\n");
const json = (value: unknown) =>
  "````json\n" +
  JSON.stringify(value, null, 2).replaceAll("`", "\\u0060") +
  "\n````";

/** Export the visible editor state, including explicitly identified unsaved edits. */
export function buildDiagramConstraintInfo(
  info: DiagramConstraintInfo,
  exportedAt = new Date().toISOString(),
) {
  const { nodes, reaches, scenarioId } = info;
  const units = nodes.flatMap((plant) =>
    (plant.units ?? []).map((unit) => ({ plant, unit })),
  );
  const aliasRows: unknown[][] = [];
  const diagramLines = ["flowchart LR"];
  const mermaidIds = new Map(
    nodes.map((node, i) => [node.technical_key, `n${i + 1}`]),
  );
  const mermaidLabel = (value: string) =>
    value
      .replaceAll("&", "&amp;")
      .replaceAll('"', "&quot;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll("`", "&#96;")
      .replaceAll("\n", " ")
      .replaceAll("\r", " ");
  const diagnostics: string[] = [];
  for (const node of nodes) {
    diagramLines.push(
      `  ${mermaidIds.get(node.technical_key)}["${mermaidLabel(node.technical_key + " · " + node.display_name)}"]`,
    );
  }
  reaches.forEach((reach, i) => {
    const from = mermaidIds.get(reach.from_node_key),
      to = mermaidIds.get(reach.to_node_key);
    if (from && to)
      diagramLines.push(
        `  ${from} -->|"${mermaidLabel(reach.technical_key + " · " + reach.reach_type)}"| ${to}`,
      );
    else
      diagnostics.push(
        `Tramo ${reach.technical_key}: falta el nodo de origen o destino.`,
      );
    aliasRows.push([
      `tramo_${i + 1}`,
      "Tramo",
      reach.technical_key,
      reach.display_name,
      `ctx.objetos.tramo_${i + 1}.caudal[t]`,
      "m3_per_s",
    ]);
  });
  units.forEach(({ plant, unit }, i) => {
    const id = `u${i + 1}`;
    diagramLines.push(
      `  ${id}["${mermaidLabel(unit.technical_key + " · " + plant.display_name + (unit.is_active ? "" : " · INACTIVA"))}"]`,
    );
    const from = mermaidIds.get(unit.intake_node_key ?? ""),
      to = mermaidIds.get(unit.discharge_node_key ?? "");
    if (from) diagramLines.push(`  ${from} -->|"toma"| ${id}`);
    if (to) diagramLines.push(`  ${id} -->|"descarga"| ${to}`);
    if (!from || !to)
      diagnostics.push(
        `Unidad ${unit.technical_key}: toma o descarga incompleta.`,
      );
    if (unit.is_active && !plant.plant?.non_modeled)
      aliasRows.push([
        `unidad_${i + 1}`,
        "Unidad",
        unit.technical_key,
        unit.display_name,
        `ctx.objetos.unidad_${i + 1}.caudal[t]; ctx.objetos.unidad_${i + 1}.potencia[t]`,
        "m3_per_s; mw",
      ]);
  });
  nodes
    .filter((n) => n.component_type === "reservoir")
    .forEach((node, i) => {
      aliasRows.push([
        `embalse_${i + 1}`,
        "Embalse",
        node.technical_key,
        node.display_name,
        `ctx.objetos.embalse_${i + 1}.almacenamiento[t]; ctx.objetos.embalse_${i + 1}.vertimiento[t]`,
        "hm3; m3_per_s",
      ]);
    });
  nodes
    .filter((n) => n.component_type === "plant" && !n.plant?.non_modeled)
    .forEach((node, i) => {
      aliasRows.push([
        `central_${i + 1}`,
        "Central",
        node.technical_key,
        node.display_name,
        `ctx.objetos.central_${i + 1}.potencia[t]`,
        "mw",
      ]);
    });
  const sections = [
    "# Información del diagrama y manual de restricciones personalizadas",
    table(
      ["Campo", "Valor"],
      [
        ["Escenario", `${scenarioId} · ${info.scenarioName}`],
        ["Revisión del servidor", info.revision],
        ["Exportación UTC", exportedAt],
        [
          "Estado",
          info.saved
            ? "Guardado"
            : "Borrador con cambios sin guardar; guardar y validar antes de aplicar reglas",
        ],
        ["Origen", `/react/scenarios/${scenarioId}/hydraulic-diagram`],
      ],
    ),
    "Este documento describe el estado visible del editor al exportar. Es una fotografía de trabajo, no un certificado de validación ni una corrida. No incluye las reglas ya guardadas en otras pantallas, resultados ni la selección de una variante. Los valores null del anexo significan no definido, no cero.",
    "## 1. Inventario y conexiones de este diagrama",
    `Hay ${nodes.length} elementos gráficos, ${reaches.length} tramos y ${units.length} unidades (${units.filter((x) => x.unit.is_active).length} activas). Una central agrupa unidades; el agua se conecta por las tomas y descargas de sus unidades.`,
    "### Nodos y centrales",
    table(
      ["Clave técnica", "Nombre", "Tipo", "Posición X", "Posición Y"],
      nodes.map((n) => [
        n.technical_key,
        n.display_name,
        n.component_type,
        n.x,
        n.y,
      ]),
    ),
    "### Tramos dirigidos",
    table(
      [
        "Clave",
        "Nombre",
        "Tipo",
        "Desde",
        "Hacia",
        "Mínimo escalar m³/s",
        "Penalización vertimiento USD/hm³",
        "Puntos de serie mínima",
        "Abrir Python",
      ],
      reaches.map((r) => [
        r.technical_key,
        r.display_name,
        r.reach_type,
        r.from_node_key,
        r.to_node_key,
        r.flow_min_m3s,
        r.spill_penalty_usd_per_hm3,
        r.minimum_flow_series?.points.length ?? 0,
        `/react/scenarios/${scenarioId}/hydraulic-reaches/${encodeURIComponent(r.technical_key)}/rules`,
      ]),
    ),
    "### Unidades y conexión hidráulica efectiva",
    table(
      [
        "Central",
        "Unidad",
        "Nombre",
        "Activa",
        "Toma",
        "Descarga",
        "Q mínimo m³/s",
        "Q máximo m³/s",
        "P mínimo MW",
        "P máximo MW",
        "Abrir Python",
      ],
      units.map(({ plant, unit: u }) => [
        plant.technical_key,
        u.technical_key,
        u.display_name,
        u.is_active,
        u.intake_node_key,
        u.discharge_node_key,
        u.min_flow_m3s,
        u.max_flow_m3s,
        u.min_power_mw,
        u.max_power_mw,
        `/react/scenarios/${scenarioId}/hydraulic-plants/${encodeURIComponent(plant.technical_key)}/units/${encodeURIComponent(u.technical_key)}/rules`,
      ]),
    ),
    "### Embalses",
    table(
      [
        "Embalse",
        "Volumen mínimo hm³",
        "Volumen máximo hm³",
        "Volumen inicial hm³",
        "Condición terminal",
        "Mínimo terminal hm³",
        "Valor terminal USD/hm³",
        "Puntos de afluente",
      ],
      nodes
        .filter((n) => n.component_type === "reservoir")
        .map((n) => [
          n.technical_key,
          n.reservoir?.storage_min_hm3,
          n.reservoir?.storage_max_hm3,
          n.reservoir?.initial_storage_hm3,
          n.reservoir?.terminal_condition,
          n.reservoir?.terminal_storage_min_hm3,
          n.reservoir?.terminal_water_value_usd_per_hm3,
          n.natural_inflow_series?.points.length ?? 0,
        ]),
    ),
    "### Conectividad por nodo",
    table(
      [
        "Nodo",
        "Tramos entrantes",
        "Tramos salientes",
        "Unidades que descargan",
        "Unidades que toman",
      ],
      nodes
        .filter((n) => n.component_type !== "plant")
        .map((n) => [
          n.technical_key,
          reaches
            .filter((r) => r.to_node_key === n.technical_key)
            .map((r) => r.technical_key)
            .join(", "),
          reaches
            .filter((r) => r.from_node_key === n.technical_key)
            .map((r) => r.technical_key)
            .join(", "),
          units
            .filter(
              ({ unit: u }) =>
                u.is_active && u.discharge_node_key === n.technical_key,
            )
            .map(({ unit: u }) => u.technical_key)
            .join(", "),
          units
            .filter(
              ({ unit: u }) =>
                u.is_active && u.intake_node_key === n.technical_key,
            )
            .map(({ unit: u }) => u.technical_key)
            .join(", "),
        ]),
    ),
    "### Esquema de conexiones",
    "Los rectángulos de centrales son agrupadores. Las flechas de unidades describen las conexiones que utiliza el balance. Las tablas siguen siendo legibles si el visor no soporta Mermaid.",
    "```mermaid\n" + diagramLines.join("\n") + "\n```",
    "### Observaciones de esta exportación",
    diagnostics.length
      ? diagnostics.map((d) => `- ${cell(d)}`).join("\n")
      : "No se detectaron extremos ausentes en esta exportación. Ejecutar igualmente «Validar topologia» y «Probar restricciones»; esta comprobación no sustituye esos pasos.",
    "## 2. Diccionario propuesto para los alias",
    "Los siguientes alias son sugerencias reproducibles para este archivo. Debes crearlos manualmente en «Objetos y variables del modelo» seleccionando el objeto de la misma fila. La clave técnica, el nombre visible y el alias son conceptos diferentes. La aplicación conserva la identidad del objeto al guardar. Un elemento nuevo solo aparecerá después de guardar el diagrama. El selector de la variante vigente determina qué objetos están realmente disponibles.",
    table(
      [
        "Alias sugerido",
        "Tipo",
        "Clave técnica",
        "Nombre",
        "Acceso Python",
        "Unidad",
      ],
      aliasRows,
    ),
    reaches.length >= 3
      ? `Para el ejemplo A ≥ B + C, puedes asignar A al tramo ${cell(reaches[0].technical_key)}, b al tramo ${cell(reaches[1].technical_key)} y c al tramo ${cell(reaches[2].technical_key)}. Esta asignación ilustra la sintaxis; el ingeniero debe confirmar que expresa la condición física buscada.`
      : "El ejemplo A ≥ B + C necesita tres objetos con caudal. Selecciónalos entre los tramos y unidades disponibles; no se inventan conexiones ni se crean objetos desde Python.",
    guide,
    "## Anexo: datos completos del estado exportado",
    "Se incluyen curvas, parámetros, puntos horarios, claves y conexiones para poder revisar los números sin depender de la imagen. Las coordenadas y anclajes solo afectan la presentación. Las conexiones físicas están en from_node_key, to_node_key, intake_node_key y discharge_node_key. Este JSON es documental; no es un script de importación ni el snapshot de una corrida.",
    json({
      scenario_id: scenarioId,
      scenario_name: info.scenarioName,
      revision: info.revision,
      saved: info.saved,
      nodes,
      reaches,
    }),
  ];
  return sections.join("\n\n") + "\n";
}

export function downloadDiagramConstraintInfo(info: DiagramConstraintInfo) {
  const blob = new Blob([buildDiagramConstraintInfo(info)], {
    type: "text/markdown;charset=utf-8",
  });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = "diagram_info_constr.md";
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}
