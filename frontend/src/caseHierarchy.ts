export interface CaseHierarchyProvenanceEntry {
  content_hash: string;
}

export interface CaseInputVariantLineageBinding {
  signal_key: string;
  entity_type: string | null;
  entity_id: string | null;
  time_series_set_id: number;
  version_number: number;
  version_label: string;
  revision_number: number;
  content_hash: string;
  validated_range: { start: string; end: string };
}

export interface CaseHierarchyProvenance {
  kind?: string;
  topology?: CaseHierarchyProvenanceEntry;
  parameters?: CaseHierarchyProvenanceEntry;
  input_variant?: { id: number; display_name?: string };
  date_range?: { start: string; end: string };
  automation?: {
    schedule_id: number;
    schedule_tick_id: number;
    schedule_name?: string;
    due_at?: string;
    fired_at?: string;
  };
  series_bindings?: CaseInputVariantLineageBinding[];
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
