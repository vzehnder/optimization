export interface CaseHierarchyProvenanceEntry {
  content_hash: string;
}

export interface CaseHierarchyProvenance {
  kind?: string;
  topology?: CaseHierarchyProvenanceEntry;
  parameters?: CaseHierarchyProvenanceEntry;
  [key: string]: unknown;
}

const noProvenanceLabel = "Sin datos de procedencia";

export function hierarchyProvenanceHashLabel(
  entry: CaseHierarchyProvenanceEntry | undefined,
): string {
  const hash = entry?.content_hash;
  return hash ? hash.slice(0, 12) : noProvenanceLabel;
}

const hierarchyKindLabels: Record<string, string> = {
  structured_draft: "Draft estructurado",
  hydraulic_diagram_v3: "Diagrama hidraulico v3",
};

export function hierarchyKindLabel(kind: string | undefined): string {
  if (!kind) return "Desconocido";
  return hierarchyKindLabels[kind] || kind;
}
