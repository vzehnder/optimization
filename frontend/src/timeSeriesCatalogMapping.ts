import type { TimeSeriesSource } from "./api/client";
import { isPerEntitySignal, type SignalCatalogEntry } from "./signalCatalog";

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
  catalog: SignalCatalogEntry[],
): CatalogSignalMappingDraft[] {
  const suggestions = source?.mapping_suggestions;
  const candidateMappings: CatalogSignalMappingDraft[] = [];
  for (const entry of catalog) {
    const suggestedColumn = isPerEntitySignal(entry)
      ? firstNestedMappingColumn(suggestions?.[entry.signal_key])
      : mappingString(suggestions?.[entry.signal_key]);
    if (!suggestedColumn) continue;
    candidateMappings.push({
      source_column: suggestedColumn,
      signal_key: entry.signal_key,
      source_unit: entry.unit,
    });
  }
  const deduped = new Map<string, CatalogSignalMappingDraft>();
  for (const mapping of candidateMappings) {
    const dedupeKey = `${mapping.source_column}::${mapping.signal_key}`;
    if (!deduped.has(dedupeKey)) deduped.set(dedupeKey, mapping);
  }
  return Array.from(deduped.values());
}
