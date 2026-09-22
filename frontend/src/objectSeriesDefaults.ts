import type {
  CatalogDescriptor,
  ObjectTimeSeriesContextRow,
} from "./api/client";

export interface ObjectSeriesDraft {
  objectSeriesKey: string;
  displayName: string;
  description: string;
  semanticTypeKey: string;
  unitKey: string;
  dataClassKey: string;
  timezone: string;
  resolutionSeconds: number;
  pointsText: string;
  reasonText: string;
}

const ROLE_NAMES: Record<string, string> = {
  grid_import_price: "Precio de compra a la red",
  grid_export_price: "Precio de venta a la red",
  load_demand: "Demanda de carga",
  renewable_available_power: "Potencia renovable disponible",
  hydro_inflow: "Afluente hidroeléctrico",
  natural_inflow: "Afluente natural",
  minimum_flow: "Caudal mínimo",
};

function localKey(name: string, existing: ObjectTimeSeriesContextRow[]) {
  let base = name
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
  if (!/^[a-z]/.test(base)) base = `serie_${base}`;
  base = base.slice(0, 96);
  const used = new Set(
    existing
      .filter((series) => series.source_kind === "object_specific")
      .map((series) => series.series_key),
  );
  let key = base;
  for (let number = 2; used.has(key); number += 1) {
    const suffix = `_${number}`;
    key = `${base.slice(0, 96 - suffix.length)}${suffix}`;
  }
  return key;
}

export function objectSeriesDefaults({
  objectName,
  role,
  scenarioId,
  variantId,
  existing,
  semanticTypes,
  units,
  dataClasses,
  edits,
  browserTimezone,
}: {
  objectName: string;
  role: CatalogDescriptor | undefined;
  scenarioId: number | null;
  variantId: number | null;
  existing: ObjectTimeSeriesContextRow[];
  semanticTypes: CatalogDescriptor[];
  units: CatalogDescriptor[];
  dataClasses: CatalogDescriptor[];
  edits: Partial<ObjectSeriesDraft>;
  browserTimezone: string;
}): ObjectSeriesDraft {
  const available = (items: CatalogDescriptor[], key: string | undefined) =>
    items.find((item) => item.key === key && item.status === "active");
  const related = existing.filter(
    (series) =>
      series.need.binding_role_key === role?.key &&
      series.availability === "ready",
  );
  const reference =
    related.find((series) =>
      series.binding_summary.items.some(
        (binding) =>
          binding.scenario_id === scenarioId &&
          binding.variant_id === variantId &&
          binding.binding_role_key === role?.key &&
          !binding.execution_blocked,
      ),
    ) ?? related[0];
  const semanticType =
    available(semanticTypes, role?.key) ??
    available(semanticTypes, reference?.semantic_type_key) ??
    (role?.key === "grid_import_price" || role?.key === "grid_export_price"
      ? available(semanticTypes, "energy_price")
      : undefined);
  const selectedType = available(
    semanticTypes,
    edits.semanticTypeKey ?? semanticType?.key,
  );
  const unitKey = available(
    units,
    selectedType?.canonical_unit_key ?? role?.canonical_unit_key,
  )?.key;
  const name = role ? (ROLE_NAMES[role.key] ?? role.display_name) : "Serie";
  const resolution = reference?.temporal_contract.nominal_resolution_seconds;
  return {
    objectSeriesKey: localKey(
      `${objectName}_${role?.key ?? "serie"}`,
      existing,
    ),
    displayName: `${name} · ${objectName}`,
    description: `${name} para ${objectName}. Serie específica de este objeto.`,
    semanticTypeKey: semanticType?.key ?? "",
    unitKey: unitKey ?? "",
    dataClassKey:
      (
        available(dataClasses, reference?.data_class_key) ??
        available(dataClasses, "forecast")
      )?.key ?? "",
    timezone: reference?.temporal_contract.timezone || browserTimezone || "UTC",
    resolutionSeconds:
      resolution !== undefined && Number.isFinite(resolution) && resolution > 0
        ? resolution
        : 3600,
    pointsText: "",
    reasonText: "",
    // Explicit edits, including clearing a field, always win over suggestions.
    ...edits,
  };
}
