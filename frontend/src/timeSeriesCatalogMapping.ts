import type { TimeSeriesSource } from "./api/client";

export function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === "object" && !Array.isArray(value));
}

export function mappingString(value: unknown): string {
  return value === null || value === undefined ? "" : String(value);
}

export function normalizeColumnName(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_");
}

export function findSuggestedCatalogColumn(
  columns: string[],
  aliases: string[],
): string {
  const aliasSet = new Set(aliases.map((alias) => normalizeColumnName(alias)));
  return (
    columns.find((column) => aliasSet.has(normalizeColumnName(column))) || ""
  );
}

export const timeSeriesCatalogSignalOptions = [
  { value: "price_usd_per_mwh", label: "price_usd_per_mwh (USD/MWh)" },
  {
    value: "import_price_usd_per_mwh",
    label: "import_price_usd_per_mwh (USD/MWh)",
  },
  {
    value: "export_price_usd_per_mwh",
    label: "export_price_usd_per_mwh (USD/MWh)",
  },
  { value: "load_demand_mw", label: "load_demand_mw (MW)" },
  {
    value: "renewable_available_power_mw",
    label: "renewable_available_power_mw (MW)",
  },
  { value: "hydro_inflow_m3s", label: "hydro_inflow_m3s (m3/s)" },
  { value: "natural_inflow_m3s", label: "natural_inflow_m3s (m3/s)" },
  { value: "minimum_flow_m3s", label: "minimum_flow_m3s (m3/s)" },
] as const;

const timeSeriesCatalogSignalUnits: Record<string, string> = {
  price_usd_per_mwh: "USD/MWh",
  import_price_usd_per_mwh: "USD/MWh",
  export_price_usd_per_mwh: "USD/MWh",
  load_demand_mw: "MW",
  renewable_available_power_mw: "MW",
  hydro_inflow_m3s: "m3/s",
  natural_inflow_m3s: "m3/s",
  minimum_flow_m3s: "m3/s",
};

export function catalogSignalUnit(signalKey: string): string {
  return timeSeriesCatalogSignalUnits[signalKey] || "";
}

export const timeSeriesCatalogDataKindOptions = [
  { value: "real", label: "real" },
  { value: "programmed", label: "programmed" },
  { value: "forecast", label: "forecast" },
  { value: "simulated", label: "simulated" },
  { value: "synthetic", label: "synthetic" },
  { value: "mixed", label: "mixed" },
] as const;

export type CatalogSignalMappingDraft = {
  source_column: string;
  signal_key: string;
  source_unit: string;
};

function firstNestedMappingColumn(value: unknown): string {
  if (!isRecord(value)) return "";
  for (const nestedValue of Object.values(value)) {
    const text = mappingString(nestedValue);
    if (text) return text;
  }
  return "";
}

export function suggestedCatalogMappings(
  source: TimeSeriesSource | null,
): CatalogSignalMappingDraft[] {
  const suggestions = source?.mapping_suggestions;
  const candidateMappings: CatalogSignalMappingDraft[] = [];
  const scalarKeys = [
    "price_usd_per_mwh",
    "import_price_usd_per_mwh",
    "export_price_usd_per_mwh",
    "load_demand_mw",
    "renewable_available_power_mw",
    "hydro_inflow_m3s",
    "natural_inflow_m3s",
    "minimum_flow_m3s",
  ] as const;
  for (const key of scalarKeys) {
    const suggestedColumn =
      key === "load_demand_mw" ||
      key === "renewable_available_power_mw" ||
      key === "hydro_inflow_m3s"
        ? firstNestedMappingColumn(suggestions?.[key])
        : mappingString(suggestions?.[key]);
    if (!suggestedColumn) continue;
    candidateMappings.push({
      source_column: suggestedColumn,
      signal_key: key,
      source_unit: catalogSignalUnit(key),
    });
  }
  const deduped = new Map<string, CatalogSignalMappingDraft>();
  for (const mapping of candidateMappings) {
    const dedupeKey = `${mapping.source_column}::${mapping.signal_key}`;
    if (!deduped.has(dedupeKey)) deduped.set(dedupeKey, mapping);
  }
  return Array.from(deduped.values());
}
