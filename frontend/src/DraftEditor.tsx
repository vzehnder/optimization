import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  FormEvent,
  ReactNode,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import {
  ApiError,
  createScenarioDraft,
  getGeneratedSystemCasePreview,
  getProject,
  getScenario,
  getScenarioDraft,
  getTimeSeriesRows,
  promoteGeneratedSystemCase,
  saveTimeSeriesMapping,
  saveTimeSeriesRows,
  updateScenarioDraft,
  uploadTimeSeriesSource,
  validateGeneratedSystemCase,
  type DraftAsset,
  type DraftAssetType,
  type GeneratedSystemCaseSnapshot,
  type Project,
  type Scenario,
  type ScenarioDraft,
  type ScenarioDraftDocument,
  type TimeSeriesMapping,
  type TimeSeriesRow,
  type TimeSeriesSource,
} from "./api/client";
import { CaseHierarchyProvenanceSummary } from "./CaseHierarchyProvenance";
import { ForbiddenView, NotFoundView } from "./Workspace";

const scenarioQueryKey = (scenarioId: number) =>
  ["scenario", scenarioId] as const;
const projectQueryKey = (projectId: number) => ["project", projectId] as const;
const draftQueryKey = (scenarioId: number) =>
  ["scenario-draft", scenarioId] as const;
const scenarioVersionsQueryKey = (scenarioId: number) =>
  ["scenario-versions", scenarioId] as const;

type ValidationErrors = Record<string, string>;

type JsonTextState = {
  solverOptions: string;
  timeSeriesSources: string;
  hydroGenerationCurve: string;
  hydroReservoirCurve: string;
};

const assetLabels: Record<DraftAssetType, string> = {
  battery: "BESS",
  load: "load",
  renewable: "renewable",
  hydro: "hydro",
};

const defaultAssets: Record<DraftAssetType, DraftAsset> = {
  battery: {
    id: "battery_1",
    type: "battery",
    charge_power_max_mw: 4,
    discharge_power_max_mw: 4,
    energy_min_mwh: 0,
    energy_max_mwh: 8,
    initial_energy_mwh: 4,
    charge_efficiency: 0.95,
    discharge_efficiency: 0.95,
    degradation_cost_per_mwh_delta_soc: 0,
    terminal_condition: "equal_initial",
    terminal_energy_min_mwh: null,
    prevent_simultaneous_charge_discharge: true,
    degradation_linear_delta_soc: true,
  },
  load: { id: "load_1", type: "load" },
  renewable: {
    id: "solar_1",
    type: "renewable",
    category: "solar",
    curtailment_penalty_usd_per_mwh: 0,
  },
  hydro: {
    id: "hydro_1",
    type: "hydro",
    storage_min_hm3: 1,
    storage_max_hm3: 5,
    initial_storage_hm3: 2.5,
    generation_mode: "linear",
    power_per_flow_mw_per_m3s: 0.08,
    turbine_flow_min_m3s: null,
    turbine_flow_max_m3s: 40,
    power_max_mw: 3,
    minimum_release_m3s: 0,
    spill_penalty_usd_per_hm3: 100,
    terminal_condition: "none",
    terminal_storage_min_hm3: null,
    terminal_water_value_usd_per_hm3: 0,
    reservoir_curve: [
      { storage_hm3: 1, elevation_masl: 700 },
      { storage_hm3: 3, elevation_masl: 710 },
      { storage_hm3: 5, elevation_masl: 720 },
    ],
  },
};

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  return "No se pudo completar la accion.";
}

function useNumericParam(name: string): number | null {
  const params = useParams();
  const rawValue = params[name];
  const value = Number(rawValue);
  if (!rawValue || !Number.isInteger(value) || value < 1) return null;
  return value;
}

function stableJson(value: unknown): string {
  return JSON.stringify(value, (_key, nested) => {
    if (!nested || typeof nested !== "object" || Array.isArray(nested)) {
      return nested;
    }
    return Object.keys(nested as Record<string, unknown>)
      .sort()
      .reduce<Record<string, unknown>>((sorted, key) => {
        sorted[key] = (nested as Record<string, unknown>)[key];
        return sorted;
      }, {});
  });
}

function prettyJson(value: unknown): string {
  return JSON.stringify(value ?? {}, null, 2);
}

function cloneDocument(document: ScenarioDraftDocument): ScenarioDraftDocument {
  return JSON.parse(JSON.stringify(document)) as ScenarioDraftDocument;
}

function jsonText(value: unknown, fallback: unknown): string {
  return JSON.stringify(value ?? fallback, null, 2);
}

function jsonTextsFromDocument(document: ScenarioDraftDocument): JsonTextState {
  const hydro = (document.assets || []).find((asset) => asset.type === "hydro");
  return {
    solverOptions: jsonText(document.solver?.options, {}),
    timeSeriesSources: jsonText(document.time_series?.sources, []),
    hydroGenerationCurve: jsonText(hydro?.generation_curve, []),
    hydroReservoirCurve: jsonText(hydro?.reservoir_curve, [
      { storage_hm3: 1, elevation_masl: 700 },
      { storage_hm3: 3, elevation_masl: 710 },
      { storage_hm3: 5, elevation_masl: 720 },
    ]),
  };
}

function editorSignature(
  document: ScenarioDraftDocument,
  jsonTexts: JsonTextState,
): string {
  return stableJson({ document, jsonTexts });
}

function textValue(value: unknown): string {
  return value === null || value === undefined ? "" : String(value);
}

function numberValue(value: unknown): string {
  return typeof value === "number" && Number.isFinite(value)
    ? String(value)
    : "";
}

function parseOptionalNumber(value: string): number | null {
  const trimmed = value.trim();
  if (!trimmed) return null;
  const parsed = Number(trimmed);
  return Number.isFinite(parsed) ? parsed : null;
}

const scalarMappingKeys = [
  "timestamp",
  "duration_hours",
  "price_usd_per_mwh",
  "import_price_usd_per_mwh",
  "export_price_usd_per_mwh",
] as const;

type ScalarMappingKey = (typeof scalarMappingKeys)[number];

const assetMappingKeys = [
  "renewable_available_power_mw",
  "load_demand_mw",
  "hydro_inflow_m3s",
] as const;

type AssetMappingKey = (typeof assetMappingKeys)[number];

const assetMappingTypes: Record<AssetMappingKey, DraftAssetType> = {
  renewable_available_power_mw: "renewable",
  load_demand_mw: "load",
  hydro_inflow_m3s: "hydro",
};

const rowRenderLimit = 50;

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === "object" && !Array.isArray(value));
}

function isTimeSeriesSource(value: unknown): value is TimeSeriesSource {
  return isRecord(value) && typeof value.id === "string";
}

function timeSeriesSources(
  document: ScenarioDraftDocument,
): TimeSeriesSource[] {
  const sources = document.time_series?.sources;
  return Array.isArray(sources) ? sources.filter(isTimeSeriesSource) : [];
}

function activeTimeSeriesSource(
  document: ScenarioDraftDocument,
): TimeSeriesSource | null {
  const sources = timeSeriesSources(document);
  const activeSourceId = document.time_series?.active_source_id;
  if (activeSourceId) {
    return sources.find((source) => source.id === activeSourceId) ?? null;
  }
  return sources.at(-1) ?? null;
}

function documentWithTimeSeriesSource(
  document: ScenarioDraftDocument,
  source: TimeSeriesSource,
): ScenarioDraftDocument {
  const sources = timeSeriesSources(document).filter(
    (candidate) => candidate.id !== source.id,
  );
  return {
    ...document,
    time_series: {
      ...(document.time_series || {}),
      active_source_id: source.id,
      sources: [...sources, source],
    },
  };
}

function assetIds(
  document: ScenarioDraftDocument,
  assetType: DraftAssetType,
): string[] {
  return (document.assets || [])
    .filter((asset) => asset.type === assetType)
    .map((asset) => String(asset.id || "").trim())
    .filter(Boolean);
}

function mappingString(value: unknown): string {
  return value === null || value === undefined ? "" : String(value);
}

function nestedMapping(
  mapping: TimeSeriesMapping | undefined,
  key: AssetMappingKey,
): Record<string, string | null> {
  const value = mapping?.[key];
  return isRecord(value)
    ? Object.fromEntries(
        Object.entries(value).map(([assetId, column]) => [
          assetId,
          mappingString(column) || null,
        ]),
      )
    : {};
}

function mappingFromSource(
  source: TimeSeriesSource | null,
  document: ScenarioDraftDocument,
): TimeSeriesMapping {
  const base = source?.mapping || source?.mapping_suggestions || {};
  const mapping: TimeSeriesMapping = {};
  for (const key of scalarMappingKeys) {
    mapping[key] = mappingString(base[key]) || null;
  }
  for (const key of assetMappingKeys) {
    const values = nestedMapping(base, key);
    const assetType = assetMappingTypes[key];
    mapping[key] = Object.fromEntries(
      assetIds(document, assetType).map((assetId) => [
        assetId,
        values[assetId] || null,
      ]),
    );
  }
  return mapping;
}

function isAssetType(value: unknown): value is DraftAssetType {
  return (
    value === "battery" ||
    value === "load" ||
    value === "renewable" ||
    value === "hydro"
  );
}

function fieldErrorId(field: string): string {
  return `${field}-error`;
}

function preserveGeneratedSnapshot(
  document: ScenarioDraftDocument,
): ScenarioDraftDocument {
  return document;
}

function generatedSnapshotFromDocument(
  document: ScenarioDraftDocument,
): GeneratedSystemCaseSnapshot | null {
  const snapshot = document.generated_system_case;
  if (!isRecord(snapshot) || !isRecord(snapshot.validation)) return null;
  return snapshot as GeneratedSystemCaseSnapshot;
}

function generatedCaseErrorTarget(category: string): {
  href: string;
  label: string;
} {
  if (category === "mapping" || category === "time_series") {
    return { href: "#time-series-metadata", label: "Ir a source data" };
  }
  if (category === "asset" || category === "assets") {
    return { href: "#asset-settings", label: "Ir a assets" };
  }
  return { href: "#case-settings", label: "Ir a configuracion" };
}

function setNestedValue(
  document: ScenarioDraftDocument,
  section: "case" | "pcc" | "grid" | "solver" | "time_series",
  key: string,
  value: unknown,
): ScenarioDraftDocument {
  return preserveGeneratedSnapshot({
    ...document,
    [section]: {
      ...(document[section] as Record<string, unknown> | undefined),
      [key]: value,
    },
  });
}

function replaceAsset(
  document: ScenarioDraftDocument,
  assetIndex: number,
  patch: Record<string, unknown>,
): ScenarioDraftDocument {
  const assets = [...(document.assets || [])];
  assets[assetIndex] = { ...assets[assetIndex], ...patch };
  return preserveGeneratedSnapshot({ ...document, assets });
}

function parseJsonField<T>(
  text: string,
  fallback: T,
  field: string,
  errors: ValidationErrors,
  shouldBeArray = false,
): T {
  if (!text.trim()) return fallback;
  try {
    const parsed = JSON.parse(text) as T;
    if (shouldBeArray && !Array.isArray(parsed)) {
      errors[field] = "Debe ser un arreglo JSON.";
      return fallback;
    }
    if (!shouldBeArray && (parsed === null || Array.isArray(parsed))) {
      errors[field] = "Debe ser un objeto JSON.";
      return fallback;
    }
    return parsed;
  } catch (error) {
    const message = error instanceof Error ? error.message : "JSON invalido.";
    errors[field] = message;
    return fallback;
  }
}

function buildSaveDocument(
  document: ScenarioDraftDocument,
  jsonTexts: JsonTextState,
): { document: ScenarioDraftDocument; errors: ValidationErrors } {
  const errors: ValidationErrors = {};
  const candidate = cloneDocument(document);
  const options = parseJsonField<Record<string, unknown>>(
    jsonTexts.solverOptions,
    {},
    "solver_options_json",
    errors,
  );
  const sources = parseJsonField<unknown[]>(
    jsonTexts.timeSeriesSources,
    [],
    "time_series_sources_json",
    errors,
    true,
  );
  candidate.solver = { ...(candidate.solver || {}), options };
  candidate.time_series = {
    ...(candidate.time_series || {}),
    sources,
  };

  const hydroIndex = (candidate.assets || []).findIndex(
    (asset) => asset.type === "hydro",
  );
  if (hydroIndex >= 0) {
    const generationCurve = parseJsonField<unknown[]>(
      jsonTexts.hydroGenerationCurve,
      [],
      "hydro_generation_curve_json",
      errors,
      true,
    );
    const reservoirCurve = parseJsonField<unknown[]>(
      jsonTexts.hydroReservoirCurve,
      [],
      "hydro_reservoir_curve_json",
      errors,
      true,
    );
    const hydro: DraftAsset = {
      ...candidate.assets![hydroIndex],
      reservoir_curve: reservoirCurve,
    };
    if (generationCurve.length) hydro.generation_curve = generationCurve;
    else delete hydro.generation_curve;
    candidate.assets![hydroIndex] = hydro;
  }

  Object.assign(errors, validateDocument(candidate));
  return { document: candidate, errors };
}

function validateDocument(document: ScenarioDraftDocument): ValidationErrors {
  const errors: ValidationErrors = {};
  if (!String(document.schema_version || "").trim()) {
    errors.schema_version = "Schema requerido.";
  }
  if (!String(document.case?.name || "").trim()) {
    errors.case_name = "Nombre requerido.";
  }
  if (!String(document.pcc?.id || "").trim()) {
    errors.pcc_id = "PCC requerido.";
  }
  if (!String(document.grid?.id || "").trim()) {
    errors.grid_id = "Grid requerido.";
  }

  const seenIds = new Set<string>();
  for (const [index, asset] of (document.assets || []).entries()) {
    const assetId = String(asset.id || "").trim();
    const type = String(asset.type || "asset");
    const idField = `${type}_id`;
    if (!assetId) errors[idField] = "Asset ID requerido.";
    if (assetId && seenIds.has(assetId)) {
      errors[idField] = `Asset ID duplicado: ${assetId}.`;
    }
    seenIds.add(assetId);

    if (asset.type === "battery") {
      for (const field of [
        "charge_power_max_mw",
        "discharge_power_max_mw",
        "energy_min_mwh",
        "energy_max_mwh",
        "initial_energy_mwh",
        "charge_efficiency",
        "discharge_efficiency",
        "degradation_cost_per_mwh_delta_soc",
      ]) {
        if (typeof asset[field] !== "number") {
          errors[`battery_${field}`] = "Valor numerico requerido.";
        }
      }
      const min = Number(asset.energy_min_mwh);
      const max = Number(asset.energy_max_mwh);
      const initial = Number(asset.initial_energy_mwh);
      if (Number.isFinite(min) && Number.isFinite(max) && min > max) {
        errors.battery_energy_max_mwh =
          "Maximum energy debe ser mayor o igual al minimo.";
      }
      if (
        Number.isFinite(min) &&
        Number.isFinite(max) &&
        Number.isFinite(initial) &&
        (initial < min || initial > max)
      ) {
        errors.battery_initial_energy_mwh =
          "Initial energy debe quedar entre minimo y maximo.";
      }
    }

    if (asset.type === "hydro") {
      for (const field of [
        "storage_min_hm3",
        "storage_max_hm3",
        "initial_storage_hm3",
      ]) {
        if (typeof asset[field] !== "number") {
          errors[`hydro_${field}`] = "Valor numerico requerido.";
        }
      }
      if (
        !Array.isArray(asset.reservoir_curve) ||
        !asset.reservoir_curve.length
      ) {
        errors.hydro_reservoir_curve_json = "Reservoir curve requerida.";
      }
    }

    if (!isAssetType(asset.type)) {
      errors[`asset_${index}_type`] = "Tipo de asset no soportado.";
    }
  }
  return errors;
}

function StatusBadge({
  dirty,
  saving,
  failed,
}: {
  dirty: boolean;
  saving: boolean;
  failed: boolean;
}) {
  let label = "Guardado";
  if (saving) label = "Guardando";
  else if (failed) label = "Error al guardar";
  else if (dirty) label = "Cambios sin guardar";
  return <span className="draft-status">{label}</span>;
}

function FieldError({
  errors,
  field,
}: {
  errors: ValidationErrors;
  field: string;
}) {
  if (!errors[field]) return null;
  return (
    <span className="field-error" id={fieldErrorId(field)}>
      {errors[field]}
    </span>
  );
}

function TextInput({
  id,
  label,
  value,
  onChange,
  errors,
  required,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  errors: ValidationErrors;
  required?: boolean;
}) {
  return (
    <label className="field-row" htmlFor={id}>
      <span>{label}</span>
      <input
        id={id}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        aria-describedby={errors[id] ? fieldErrorId(id) : undefined}
        required={required}
      />
      <FieldError errors={errors} field={id} />
    </label>
  );
}

function NumberInput({
  id,
  label,
  value,
  onChange,
  errors,
  required,
}: {
  id: string;
  label: string;
  value: unknown;
  onChange: (value: number | null) => void;
  errors: ValidationErrors;
  required?: boolean;
}) {
  return (
    <label className="field-row" htmlFor={id}>
      <span>{label}</span>
      <input
        id={id}
        type="number"
        step="any"
        value={numberValue(value)}
        onChange={(event) => onChange(parseOptionalNumber(event.target.value))}
        aria-describedby={errors[id] ? fieldErrorId(id) : undefined}
        required={required}
      />
      <FieldError errors={errors} field={id} />
    </label>
  );
}

function SelectInput({
  id,
  label,
  value,
  options,
  onChange,
}: {
  id: string;
  label: string;
  value: string;
  options: Array<{ value: string; label: string }>;
  onChange: (value: string) => void;
}) {
  return (
    <label className="field-row" htmlFor={id}>
      <span>{label}</span>
      <select
        id={id}
        value={value}
        onChange={(event) => onChange(event.target.value)}
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  );
}

function JsonTextarea({
  id,
  label,
  value,
  onChange,
  errors,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  errors: ValidationErrors;
}) {
  return (
    <label className="field-row field-row-wide" htmlFor={id}>
      <span>{label}</span>
      <textarea
        id={id}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        spellCheck={false}
        rows={5}
        aria-describedby={errors[id] ? fieldErrorId(id) : undefined}
      />
      <FieldError errors={errors} field={id} />
    </label>
  );
}

function CheckboxInput({
  label,
  checked,
  onChange,
}: {
  label: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
}) {
  return (
    <label className="checkbox-row">
      <input
        type="checkbox"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
      />
      <span>{label}</span>
    </label>
  );
}

function columnList(source: TimeSeriesSource): string[] {
  return Array.isArray(source.columns) ? source.columns.map(String) : [];
}

function previewRows(source: TimeSeriesSource): TimeSeriesRow[] {
  return Array.isArray(source.preview_rows)
    ? (source.preview_rows as TimeSeriesRow[])
    : [];
}

function cellText(value: unknown): string {
  return value === null || value === undefined ? "" : String(value);
}

function mappingValue(
  mapping: TimeSeriesMapping,
  key: ScalarMappingKey,
): string {
  return mappingString(mapping[key]);
}

function assetMappingValue(
  mapping: TimeSeriesMapping,
  key: AssetMappingKey,
  assetId: string,
): string {
  const values = mapping[key];
  return isRecord(values) ? mappingString(values[assetId]) : "";
}

function assetMappingLabel(key: AssetMappingKey, assetId: string): string {
  if (key === "renewable_available_power_mw") {
    return `Renewable ${assetId} available column`;
  }
  if (key === "load_demand_mw") return `Load ${assetId} demand column`;
  return `Hydro ${assetId} inflow column`;
}

function ColumnSelect({
  id,
  label,
  value,
  columns,
  onChange,
  disabled,
}: {
  id: string;
  label: string;
  value: string;
  columns: string[];
  onChange: (value: string) => void;
  disabled?: boolean;
}) {
  return (
    <label className="field-row" htmlFor={id}>
      <span>{label}</span>
      <select
        id={id}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        disabled={disabled}
      >
        <option value="">No column</option>
        {columns.map((column) => (
          <option key={column} value={column}>
            {column}
          </option>
        ))}
      </select>
    </label>
  );
}

function SourceValidation({ source }: { source: TimeSeriesSource }) {
  const validation = source.validation;
  if (!validation) return null;
  if (validation.ok) {
    const count = Array.isArray(source.validated_rows)
      ? source.validated_rows.length
      : 0;
    return <p className="source-ok">Valid mapped rows: {count}</p>;
  }
  const errors = Array.isArray(validation.errors) ? validation.errors : [];
  return (
    <div className="source-validation" role="alert">
      <p>{mappingString(validation.error_category) || "Validation"} errors</p>
      <ul>
        {errors.map((error) => (
          <li key={error}>{error}</li>
        ))}
      </ul>
    </div>
  );
}

function PreviewTable({ source }: { source: TimeSeriesSource }) {
  const columns = columnList(source);
  const rows = previewRows(source);
  if (!columns.length || !rows.length) {
    return <p className="empty-state">No preview rows detected.</p>;
  }
  return (
    <div className="time-series-table-scroll">
      <table aria-label="Source preview">
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column} scope="col">
                {column}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, rowIndex) => (
            <tr key={rowIndex}>
              {columns.map((column) => (
                <td key={column}>{cellText(row[column])}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function SourceSummary({ source }: { source: TimeSeriesSource }) {
  const columns = columnList(source);
  return (
    <section className="source-summary" aria-labelledby="active-source-title">
      <h3 id="active-source-title">Time-series source</h3>
      <dl className="source-metadata">
        <div>
          <dt>File</dt>
          <dd>{source.original_filename || source.id}</dd>
        </div>
        <div>
          <dt>Kind</dt>
          <dd>{source.kind || "source"}</dd>
        </div>
        <div>
          <dt>Source ID</dt>
          <dd>{source.id}</dd>
        </div>
        {source.selected_sheet ? (
          <div>
            <dt>Sheet</dt>
            <dd>Selected sheet: {source.selected_sheet}</dd>
          </div>
        ) : null}
      </dl>
      {columns.length ? (
        <p className="source-columns">Detected columns: {columns.join(", ")}</p>
      ) : null}
      <PreviewTable source={source} />
      <SourceValidation source={source} />
    </section>
  );
}

function TimeSeriesMappingPanel({
  scenarioId,
  source,
  document,
  disabled,
  onSourcePersisted,
}: {
  scenarioId: number;
  source: TimeSeriesSource;
  document: ScenarioDraftDocument;
  disabled: boolean;
  onSourcePersisted: (source: TimeSeriesSource) => void;
}) {
  const [mappingDraft, setMappingDraft] = useState<TimeSeriesMapping>(() =>
    mappingFromSource(source, document),
  );
  const [mappingError, setMappingError] = useState("");
  const columns = columnList(source);

  const mutation = useMutation({
    mutationFn: () =>
      saveTimeSeriesMapping(scenarioId, source.id, mappingDraft),
    onSuccess: (savedSource) => {
      setMappingError("");
      onSourcePersisted(savedSource);
    },
    onError: (mutationError) => setMappingError(errorMessage(mutationError)),
  });

  function setScalar(key: ScalarMappingKey, value: string) {
    setMappingDraft((current) => ({ ...current, [key]: value || null }));
    setMappingError("");
  }

  function setAsset(key: AssetMappingKey, assetId: string, value: string) {
    setMappingDraft((current) => {
      const currentValues = isRecord(current[key]) ? current[key] : {};
      return {
        ...current,
        [key]: {
          ...currentValues,
          [assetId]: value || null,
        },
      };
    });
    setMappingError("");
  }

  return (
    <section className="source-mapping" aria-labelledby="source-mapping-title">
      <h3 id="source-mapping-title">Column mapping</h3>
      {mappingError ? <p role="alert">{mappingError}</p> : null}
      <div className="draft-field-grid">
        <ColumnSelect
          id="mapping_timestamp"
          label="Timestamp column"
          value={mappingValue(mappingDraft, "timestamp")}
          columns={columns}
          onChange={(value) => setScalar("timestamp", value)}
          disabled={disabled || mutation.isPending}
        />
        <ColumnSelect
          id="mapping_duration_hours"
          label="Duration column"
          value={mappingValue(mappingDraft, "duration_hours")}
          columns={columns}
          onChange={(value) => setScalar("duration_hours", value)}
          disabled={disabled || mutation.isPending}
        />
        <ColumnSelect
          id="mapping_price_usd_per_mwh"
          label="Legacy price column"
          value={mappingValue(mappingDraft, "price_usd_per_mwh")}
          columns={columns}
          onChange={(value) => setScalar("price_usd_per_mwh", value)}
          disabled={disabled || mutation.isPending}
        />
        <ColumnSelect
          id="mapping_import_price_usd_per_mwh"
          label="Import price column"
          value={mappingValue(mappingDraft, "import_price_usd_per_mwh")}
          columns={columns}
          onChange={(value) => setScalar("import_price_usd_per_mwh", value)}
          disabled={disabled || mutation.isPending}
        />
        <ColumnSelect
          id="mapping_export_price_usd_per_mwh"
          label="Export price column"
          value={mappingValue(mappingDraft, "export_price_usd_per_mwh")}
          columns={columns}
          onChange={(value) => setScalar("export_price_usd_per_mwh", value)}
          disabled={disabled || mutation.isPending}
        />
        {assetMappingKeys.flatMap((key) =>
          assetIds(document, assetMappingTypes[key]).map((assetId) => (
            <ColumnSelect
              key={`${key}-${assetId}`}
              id={`mapping_${key}_${assetId}`}
              label={assetMappingLabel(key, assetId)}
              value={assetMappingValue(mappingDraft, key, assetId)}
              columns={columns}
              onChange={(value) => setAsset(key, assetId, value)}
              disabled={disabled || mutation.isPending}
            />
          )),
        )}
      </div>
      <button
        type="button"
        onClick={() => mutation.mutate()}
        disabled={disabled || mutation.isPending}
      >
        {mutation.isPending ? "Saving mapping" : "Save mapping"}
      </button>
    </section>
  );
}

function TimeSeriesRowsEditor({
  scenarioId,
  source,
  disabled,
  onSourcePersisted,
}: {
  scenarioId: number;
  source: TimeSeriesSource;
  disabled: boolean;
  onSourcePersisted: (source: TimeSeriesSource) => void;
}) {
  const queryClient = useQueryClient();
  const rowsQueryKey = ["time-series-rows", scenarioId, source.id] as const;
  const rows = useQuery({
    queryKey: rowsQueryKey,
    queryFn: ({ signal }) => getTimeSeriesRows(scenarioId, source.id, signal),
    enabled: Boolean(source.id),
    retry: false,
  });
  const [rowEdits, setRowEdits] = useState<Record<string, string>>({});
  const [rowError, setRowError] = useState("");
  const [rowStatus, setRowStatus] = useState("");
  const columns = useMemo(() => rows.data?.columns || [], [rows.data]);
  const baseRows = useMemo(() => rows.data?.rows || [], [rows.data]);
  const rowDrafts = useMemo(
    () =>
      baseRows.map((row, rowIndex) => {
        const draft = { ...row };
        for (const column of columns) {
          const key = `${rowIndex}:${column}`;
          if (Object.prototype.hasOwnProperty.call(rowEdits, key)) {
            draft[column] = rowEdits[key];
          }
        }
        return draft;
      }),
    [baseRows, columns, rowEdits],
  );

  const saveMutation = useMutation({
    mutationFn: () => saveTimeSeriesRows(scenarioId, source.id, rowDrafts),
    onSuccess: (savedSource) => {
      queryClient.setQueryData(rowsQueryKey, {
        columns: columns.length ? columns : columnList(source),
        rows: rowDrafts,
      });
      setRowEdits({});
      setRowError("");
      setRowStatus("Rows saved");
      onSourcePersisted(savedSource);
    },
    onError: (mutationError) => setRowError(errorMessage(mutationError)),
  });

  function updateCell(rowIndex: number, column: string, value: string) {
    setRowEdits((current) => ({
      ...current,
      [`${rowIndex}:${column}`]: value,
    }));
    setRowError("");
    setRowStatus("");
  }

  if (rows.isPending) {
    return <p className="empty-state">Loading editable rows.</p>;
  }
  if (rows.isError) {
    return <p role="alert">{errorMessage(rows.error)}</p>;
  }

  const renderedRows = rowDrafts.slice(0, rowRenderLimit);

  return (
    <section className="source-rows" aria-labelledby="source-rows-title">
      <h3 id="source-rows-title">Editable rows</h3>
      {rowError ? <p role="alert">{rowError}</p> : null}
      {rowStatus ? <p className="source-ok">{rowStatus}</p> : null}
      {rowDrafts.length > rowRenderLimit ? (
        <p className="source-note">
          Showing first {rowRenderLimit} of {rowDrafts.length} rows.
        </p>
      ) : null}
      {columns.length && renderedRows.length ? (
        <div className="time-series-table-scroll editable-table-scroll">
          <table aria-label="Editable source rows">
            <thead>
              <tr>
                <th scope="col">Row</th>
                {columns.map((column) => (
                  <th key={column} scope="col">
                    {column}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {renderedRows.map((row, rowIndex) => (
                <tr key={rowIndex}>
                  <th scope="row">{rowIndex + 1}</th>
                  {columns.map((column) => (
                    <td key={column}>
                      <input
                        aria-label={`Row ${rowIndex + 1} ${column}`}
                        value={cellText(row[column])}
                        onChange={(event) =>
                          updateCell(rowIndex, column, event.target.value)
                        }
                        disabled={disabled || saveMutation.isPending}
                      />
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="empty-state">No editable rows detected.</p>
      )}
      <button
        type="button"
        onClick={() => saveMutation.mutate()}
        disabled={disabled || saveMutation.isPending || !rowDrafts.length}
      >
        {saveMutation.isPending ? "Saving rows" : "Save rows"}
      </button>
    </section>
  );
}

function TimeSeriesWorkflow({
  scenarioId,
  document,
  dirty,
  onSourcePersisted,
}: {
  scenarioId: number;
  document: ScenarioDraftDocument;
  dirty: boolean;
  onSourcePersisted: (source: TimeSeriesSource) => void;
}) {
  const source = activeTimeSeriesSource(document);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [sheetName, setSheetName] = useState("");
  const [uploadError, setUploadError] = useState("");
  const uploadMutation = useMutation({
    mutationFn: ({ file, sheet }: { file: File; sheet: string }) =>
      uploadTimeSeriesSource(scenarioId, file, sheet),
    onSuccess: (savedSource) => {
      setUploadError("");
      onSourcePersisted(savedSource);
    },
    onError: (mutationError) => setUploadError(errorMessage(mutationError)),
  });

  function uploadSource() {
    const file = fileInputRef.current?.files?.[0];
    if (!file) {
      setUploadError("Select a CSV or XLSX file.");
      return;
    }
    setUploadError("");
    uploadMutation.mutate({ file, sheet: sheetName });
  }

  const controlsDisabled = dirty || uploadMutation.isPending;

  return (
    <div className="time-series-workflow">
      {dirty ? (
        <p className="source-note">
          Save draft before uploading or changing time-series sources.
        </p>
      ) : null}
      <div className="source-upload">
        <label className="field-row" htmlFor="time_series_source_file">
          <span>Source file</span>
          <input
            id="time_series_source_file"
            ref={fileInputRef}
            type="file"
            accept="text/csv,.csv,.xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            disabled={controlsDisabled}
          />
        </label>
        <TextInput
          id="time_series_sheet_name"
          label="XLSX sheet"
          value={sheetName}
          onChange={setSheetName}
          errors={{}}
        />
        <button
          type="button"
          onClick={uploadSource}
          disabled={controlsDisabled}
        >
          {uploadMutation.isPending ? "Uploading source" : "Upload source"}
        </button>
      </div>
      {uploadError ? <p role="alert">{uploadError}</p> : null}
      {source ? (
        <>
          <SourceSummary source={source} />
          <TimeSeriesMappingPanel
            key={`mapping-${source.id}`}
            scenarioId={scenarioId}
            source={source}
            document={document}
            disabled={dirty}
            onSourcePersisted={onSourcePersisted}
          />
          <TimeSeriesRowsEditor
            key={`rows-${source.id}`}
            scenarioId={scenarioId}
            source={source}
            disabled={dirty}
            onSourcePersisted={onSourcePersisted}
          />
        </>
      ) : (
        <p className="empty-state">Upload a CSV or XLSX source to begin.</p>
      )}
    </div>
  );
}

function GeneratedSystemCasePanel({
  scenario,
  document,
  dirty,
  validationStale,
  onSnapshotPersisted,
}: {
  scenario: Scenario;
  document: ScenarioDraftDocument;
  dirty: boolean;
  validationStale: boolean;
  onSnapshotPersisted: (snapshot: GeneratedSystemCaseSnapshot) => void;
}) {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const snapshot = generatedSnapshotFromDocument(document);
  const [previewCase, setPreviewCase] = useState<unknown | null>(
    () => snapshot?.system_case ?? null,
  );
  const [actionError, setActionError] = useState<{
    message: string;
    category: string;
  } | null>(null);
  const validation = snapshot?.validation;
  const hasCurrentValidation =
    Boolean(validation?.ok) && !dirty && !validationStale;
  const hasStaleValidation = Boolean(snapshot) && (dirty || validationStale);

  function setError(error: unknown) {
    if (error instanceof ApiError) {
      setActionError({ message: error.message, category: error.category });
      return;
    }
    setActionError({
      message: "No se pudo completar la accion.",
      category: "validation",
    });
  }

  const previewMutation = useMutation({
    mutationFn: () => getGeneratedSystemCasePreview(scenario.id),
    onSuccess: (systemCase) => {
      setPreviewCase(systemCase);
      setActionError(null);
    },
    onError: setError,
  });

  const validateMutation = useMutation({
    mutationFn: () => validateGeneratedSystemCase(scenario.id),
    onSuccess: (response) => {
      const nextSnapshot = response.generated_system_case;
      if (nextSnapshot) {
        onSnapshotPersisted(nextSnapshot);
        setPreviewCase(nextSnapshot.system_case);
      } else if (response.system_case) {
        setPreviewCase(response.system_case);
      }
      setActionError(null);
    },
    onError: setError,
  });

  const promoteMutation = useMutation({
    mutationFn: () => promoteGeneratedSystemCase(scenario.id),
    onSuccess: () => {
      setActionError(null);
      void queryClient.invalidateQueries({
        queryKey: scenarioVersionsQueryKey(scenario.id),
      });
      navigate(`/scenarios/${scenario.id}`);
    },
    onError: setError,
  });

  const target = actionError
    ? generatedCaseErrorTarget(actionError.category)
    : null;

  return (
    <section className="workspace-section" aria-labelledby="generated-case">
      <div className="draft-section-heading">
        <h2 id="generated-case">Caso generado</h2>
        <div className="draft-actions">
          <button
            type="button"
            className="secondary-action"
            onClick={() => previewMutation.mutate()}
            disabled={previewMutation.isPending}
          >
            {previewMutation.isPending
              ? "Generando preview"
              : "Generar preview"}
          </button>
          <button
            type="button"
            onClick={() => validateMutation.mutate()}
            disabled={dirty || validateMutation.isPending}
          >
            {validateMutation.isPending ? "Validando" : "Validar con Julia"}
          </button>
          <button
            type="button"
            onClick={() => promoteMutation.mutate()}
            disabled={
              !hasCurrentValidation ||
              promoteMutation.isPending ||
              validateMutation.isPending
            }
          >
            {promoteMutation.isPending ? "Promoviendo" : "Promover version"}
          </button>
        </div>
      </div>
      {dirty ? (
        <p className="source-note">
          Guarda el draft antes de validar o promover.
        </p>
      ) : null}
      {snapshot ? (
        <>
          <dl className="generated-validation">
            <div>
              <dt>Ultima validacion guardada</dt>
              <dd>{validation?.phase || "validation"}</dd>
            </div>
            <div>
              <dt>Status</dt>
              <dd>{validation?.ok ? "ok" : "error"}</dd>
            </div>
            <div>
              <dt>Mensaje</dt>
              <dd>{validation?.message || "Sin mensaje."}</dd>
            </div>
          </dl>
          <CaseHierarchyProvenanceSummary provenance={snapshot} />
        </>
      ) : (
        <p className="empty-state">
          Genera y valida el caso antes de crear una version.
        </p>
      )}
      {hasStaleValidation ? (
        <p className="validation-stale">
          Validacion stale; valida de nuevo antes de promover.
        </p>
      ) : null}
      {hasCurrentValidation ? (
        <p className="source-ok">Validacion vigente</p>
      ) : null}
      {actionError ? (
        <p role="alert">
          {actionError.message}
          {target ? (
            <>
              {" "}
              <a href={target.href}>{target.label}</a>
            </>
          ) : null}
        </p>
      ) : null}
      <label className="field-row field-row-wide" htmlFor="generated_case_json">
        <span>Generated system_case</span>
        <textarea
          id="generated_case_json"
          value={prettyJson(previewCase)}
          readOnly
          spellCheck={false}
          rows={12}
        />
      </label>
    </section>
  );
}

function AssetShell({
  asset,
  pendingRemovalId,
  onStartRemove,
  onCancelRemove,
  onConfirmRemove,
  children,
}: {
  asset: DraftAsset;
  pendingRemovalId: string | null;
  onStartRemove: (assetId: string) => void;
  onCancelRemove: () => void;
  onConfirmRemove: (assetId: string) => void;
  children: ReactNode;
}) {
  const assetId = String(asset.id || "");
  return (
    <fieldset className="asset-settings">
      <legend>{assetLabels[asset.type as DraftAssetType] || "asset"}</legend>
      {children}
      {pendingRemovalId === assetId ? (
        <div className="remove-confirmation">
          <p>Confirma para quitar {assetId}</p>
          <button type="button" onClick={() => onConfirmRemove(assetId)}>
            Confirmar quitar {assetId}
          </button>
          <button
            type="button"
            className="secondary-action"
            onClick={onCancelRemove}
          >
            Mantener
          </button>
        </div>
      ) : (
        <button
          type="button"
          className="danger-button"
          onClick={() => onStartRemove(assetId)}
        >
          Quitar {assetId}
        </button>
      )}
    </fieldset>
  );
}

function BatteryFields({
  asset,
  assetIndex,
  document,
  setDocument,
  errors,
  removalProps,
}: AssetFieldProps) {
  const patch = (field: string, value: unknown) =>
    setDocument((current) =>
      replaceAsset(current, assetIndex, { [field]: value }),
    );
  return (
    <AssetShell asset={asset} {...removalProps}>
      <div className="draft-field-grid">
        <TextInput
          id="battery_id"
          label="BESS asset ID"
          value={textValue(asset.id)}
          onChange={(value) => patch("id", value)}
          errors={errors}
          required
        />
        <NumberInput
          id="battery_charge_power_max_mw"
          label="Maximum charge (MW)"
          value={asset.charge_power_max_mw}
          onChange={(value) => patch("charge_power_max_mw", value)}
          errors={errors}
          required
        />
        <NumberInput
          id="battery_discharge_power_max_mw"
          label="Maximum discharge (MW)"
          value={asset.discharge_power_max_mw}
          onChange={(value) => patch("discharge_power_max_mw", value)}
          errors={errors}
          required
        />
        <NumberInput
          id="battery_energy_min_mwh"
          label="Minimum energy (MWh)"
          value={asset.energy_min_mwh}
          onChange={(value) => patch("energy_min_mwh", value)}
          errors={errors}
          required
        />
        <NumberInput
          id="battery_energy_max_mwh"
          label="Maximum energy (MWh)"
          value={asset.energy_max_mwh}
          onChange={(value) => patch("energy_max_mwh", value)}
          errors={errors}
          required
        />
        <NumberInput
          id="battery_initial_energy_mwh"
          label="Initial energy (MWh)"
          value={asset.initial_energy_mwh}
          onChange={(value) => patch("initial_energy_mwh", value)}
          errors={errors}
          required
        />
        <NumberInput
          id="battery_charge_efficiency"
          label="Charge efficiency"
          value={asset.charge_efficiency}
          onChange={(value) => patch("charge_efficiency", value)}
          errors={errors}
          required
        />
        <NumberInput
          id="battery_discharge_efficiency"
          label="Discharge efficiency"
          value={asset.discharge_efficiency}
          onChange={(value) => patch("discharge_efficiency", value)}
          errors={errors}
          required
        />
        <NumberInput
          id="battery_degradation_cost_per_mwh_delta_soc"
          label="Degradation cost (USD/MWh)"
          value={asset.degradation_cost_per_mwh_delta_soc}
          onChange={(value) =>
            patch("degradation_cost_per_mwh_delta_soc", value)
          }
          errors={errors}
          required
        />
        <SelectInput
          id="battery_terminal_condition"
          label="Terminal condition"
          value={String(asset.terminal_condition || "equal_initial")}
          onChange={(value) => patch("terminal_condition", value)}
          options={[
            { value: "none", label: "None" },
            { value: "equal_initial", label: "Equal initial" },
            { value: "min_terminal", label: "Minimum terminal" },
          ]}
        />
        <NumberInput
          id="battery_terminal_energy_min_mwh"
          label="Minimum terminal energy (MWh)"
          value={asset.terminal_energy_min_mwh}
          onChange={(value) => patch("terminal_energy_min_mwh", value)}
          errors={errors}
        />
      </div>
      <CheckboxInput
        label="Prevent simultaneous charge and discharge"
        checked={asset.prevent_simultaneous_charge_discharge !== false}
        onChange={(value) =>
          patch("prevent_simultaneous_charge_discharge", value)
        }
      />
      <CheckboxInput
        label="Apply linear degradation"
        checked={asset.degradation_linear_delta_soc !== false}
        onChange={(value) => patch("degradation_linear_delta_soc", value)}
      />
      <input type="hidden" value={String(document.schema_version || "")} />
    </AssetShell>
  );
}

function RenewableFields({
  asset,
  assetIndex,
  setDocument,
  errors,
  removalProps,
}: AssetFieldProps) {
  const patch = (field: string, value: unknown) =>
    setDocument((current) =>
      replaceAsset(current, assetIndex, { [field]: value }),
    );
  return (
    <AssetShell asset={asset} {...removalProps}>
      <div className="draft-field-grid">
        <TextInput
          id="renewable_id"
          label="Renewable asset ID"
          value={textValue(asset.id)}
          onChange={(value) => patch("id", value)}
          errors={errors}
          required
        />
        <SelectInput
          id="renewable_category"
          label="Technology"
          value={String(asset.category || asset.display_category || "solar")}
          onChange={(value) => patch("category", value)}
          options={[
            { value: "solar", label: "Solar" },
            { value: "wind", label: "Wind" },
          ]}
        />
        <NumberInput
          id="renewable_curtailment_penalty_usd_per_mwh"
          label="Curtailment penalty (USD/MWh)"
          value={asset.curtailment_penalty_usd_per_mwh}
          onChange={(value) => patch("curtailment_penalty_usd_per_mwh", value)}
          errors={errors}
        />
      </div>
    </AssetShell>
  );
}

function LoadFields({
  asset,
  assetIndex,
  setDocument,
  errors,
  removalProps,
}: AssetFieldProps) {
  const patch = (field: string, value: unknown) =>
    setDocument((current) =>
      replaceAsset(current, assetIndex, { [field]: value }),
    );
  return (
    <AssetShell asset={asset} {...removalProps}>
      <TextInput
        id="load_id"
        label="Load asset ID"
        value={textValue(asset.id)}
        onChange={(value) => patch("id", value)}
        errors={errors}
        required
      />
    </AssetShell>
  );
}

function HydroFields({
  asset,
  assetIndex,
  setDocument,
  errors,
  jsonTexts,
  setJsonTexts,
  removalProps,
  onOpenHydraulicDiagram,
}: AssetFieldProps) {
  const patch = (field: string, value: unknown) =>
    setDocument((current) =>
      replaceAsset(current, assetIndex, { [field]: value }),
    );
  const hasHydroError = Object.keys(errors).some((key) =>
    key.startsWith("hydro_"),
  );
  return (
    <AssetShell asset={asset} {...removalProps}>
      <div className="draft-field-grid">
        <TextInput
          id="hydro_id"
          label="Hydro asset ID"
          value={textValue(asset.id)}
          onChange={(value) => patch("id", value)}
          errors={errors}
          required
        />
      </div>
      <p className="source-note">
        Define la topologia y los parametros completos en el diagrama
        hidraulico. Los campos de abajo son un resumen editable.
      </p>
      {onOpenHydraulicDiagram ? (
        <button
          type="button"
          className="hydraulic-diagram-link"
          onClick={onOpenHydraulicDiagram}
        >
          Editar diagrama hidraulico
        </button>
      ) : null}
      <details className="hydro-detail" open={hasHydroError || undefined}>
        <summary>Parametros hidraulicos (resumen)</summary>
        <div className="draft-field-grid">
          <NumberInput
            id="hydro_storage_min_hm3"
            label="Minimum storage (hm3)"
            value={asset.storage_min_hm3}
            onChange={(value) => patch("storage_min_hm3", value)}
            errors={errors}
            required
          />
          <NumberInput
            id="hydro_storage_max_hm3"
            label="Maximum storage (hm3)"
            value={asset.storage_max_hm3}
            onChange={(value) => patch("storage_max_hm3", value)}
            errors={errors}
            required
          />
          <NumberInput
            id="hydro_initial_storage_hm3"
            label="Initial storage (hm3)"
            value={asset.initial_storage_hm3}
            onChange={(value) => patch("initial_storage_hm3", value)}
            errors={errors}
            required
          />
          <SelectInput
            id="hydro_generation_mode"
            label="Generation mode"
            value={String(asset.generation_mode || "linear")}
            onChange={(value) => patch("generation_mode", value)}
            options={[
              { value: "linear", label: "Linear" },
              { value: "piecewise_linear", label: "Piecewise linear" },
            ]}
          />
          <NumberInput
            id="hydro_power_per_flow_mw_per_m3s"
            label="Power per flow (MW per m3/s)"
            value={asset.power_per_flow_mw_per_m3s}
            onChange={(value) => patch("power_per_flow_mw_per_m3s", value)}
            errors={errors}
          />
          <NumberInput
            id="hydro_turbine_flow_min_m3s"
            label="Minimum turbine flow (m3/s)"
            value={asset.turbine_flow_min_m3s}
            onChange={(value) => patch("turbine_flow_min_m3s", value)}
            errors={errors}
          />
          <NumberInput
            id="hydro_turbine_flow_max_m3s"
            label="Maximum turbine flow (m3/s)"
            value={asset.turbine_flow_max_m3s}
            onChange={(value) => patch("turbine_flow_max_m3s", value)}
            errors={errors}
          />
          <NumberInput
            id="hydro_power_max_mw"
            label="Maximum power (MW)"
            value={asset.power_max_mw}
            onChange={(value) => patch("power_max_mw", value)}
            errors={errors}
          />
          <NumberInput
            id="hydro_minimum_release_m3s"
            label="Minimum release (m3/s)"
            value={asset.minimum_release_m3s}
            onChange={(value) => patch("minimum_release_m3s", value)}
            errors={errors}
          />
          <NumberInput
            id="hydro_spill_penalty_usd_per_hm3"
            label="Spill penalty (USD/hm3)"
            value={asset.spill_penalty_usd_per_hm3}
            onChange={(value) => patch("spill_penalty_usd_per_hm3", value)}
            errors={errors}
          />
          <SelectInput
            id="hydro_terminal_condition"
            label="Terminal condition"
            value={String(asset.terminal_condition || "none")}
            onChange={(value) => patch("terminal_condition", value)}
            options={[
              { value: "none", label: "None" },
              { value: "equal_initial", label: "Equal initial" },
              { value: "min_terminal", label: "Minimum terminal" },
            ]}
          />
          <NumberInput
            id="hydro_terminal_storage_min_hm3"
            label="Minimum terminal storage (hm3)"
            value={asset.terminal_storage_min_hm3}
            onChange={(value) => patch("terminal_storage_min_hm3", value)}
            errors={errors}
          />
          <NumberInput
            id="hydro_terminal_water_value_usd_per_hm3"
            label="Terminal water value (USD/hm3)"
            value={asset.terminal_water_value_usd_per_hm3}
            onChange={(value) =>
              patch("terminal_water_value_usd_per_hm3", value)
            }
            errors={errors}
          />
        </div>
        <JsonTextarea
          id="hydro_generation_curve_json"
          label="Generation curve (JSON)"
          value={jsonTexts.hydroGenerationCurve}
          onChange={(value) =>
            setJsonTexts((current) => ({
              ...current,
              hydroGenerationCurve: value,
            }))
          }
          errors={errors}
        />
        <JsonTextarea
          id="hydro_reservoir_curve_json"
          label="Reservoir curve (JSON)"
          value={jsonTexts.hydroReservoirCurve}
          onChange={(value) =>
            setJsonTexts((current) => ({
              ...current,
              hydroReservoirCurve: value,
            }))
          }
          errors={errors}
        />
      </details>
    </AssetShell>
  );
}

type AssetFieldProps = {
  asset: DraftAsset;
  assetIndex: number;
  document: ScenarioDraftDocument;
  setDocument: React.Dispatch<React.SetStateAction<ScenarioDraftDocument>>;
  errors: ValidationErrors;
  jsonTexts: JsonTextState;
  setJsonTexts: React.Dispatch<React.SetStateAction<JsonTextState>>;
  removalProps: {
    pendingRemovalId: string | null;
    onStartRemove: (assetId: string) => void;
    onCancelRemove: () => void;
    onConfirmRemove: (assetId: string) => void;
  };
  onOpenHydraulicDiagram?: () => void;
};

function LoadingView({ label }: { label: string }) {
  return <p role="status">{label}</p>;
}

function RequestErrorView({
  error,
  retry,
}: {
  error: unknown;
  retry?: () => void;
}) {
  if (error instanceof ApiError && error.status === 404) {
    return <NotFoundView>El recurso solicitado no existe.</NotFoundView>;
  }
  if (error instanceof ApiError && error.status === 403) {
    return <ForbiddenView />;
  }
  return (
    <section className="content-panel">
      <h1>No se pudo cargar</h1>
      <p>{errorMessage(error)}</p>
      {retry ? (
        <button type="button" onClick={retry}>
          Reintentar
        </button>
      ) : null}
    </section>
  );
}

function Breadcrumbs({
  scenario,
  project,
  draft,
}: {
  scenario: Scenario;
  project?: Project;
  draft?: boolean;
}) {
  return (
    <nav className="breadcrumbs" aria-label="Ruta">
      <Link to="/projects">Proyectos</Link>
      <span aria-hidden="true">/</span>
      <Link to={`/projects/${scenario.project_id}`}>
        {project?.name || "Proyecto"}
      </Link>
      <span aria-hidden="true">/</span>
      {draft ? (
        <>
          <Link to={`/scenarios/${scenario.id}`}>{scenario.name}</Link>
          <span aria-hidden="true">/</span>
          <span>Draft</span>
        </>
      ) : (
        <span>{scenario.name}</span>
      )}
    </nav>
  );
}

function EmptyDraftView({ scenario }: { scenario: Scenario }) {
  const queryClient = useQueryClient();
  const [error, setError] = useState("");
  const mutation = useMutation({
    mutationFn: () => createScenarioDraft(scenario.id),
    onSuccess: (draft) => {
      setError("");
      queryClient.setQueryData(draftQueryKey(scenario.id), draft);
    },
    onError: (mutationError) => setError(errorMessage(mutationError)),
  });
  return (
    <section className="workspace-section">
      <h2>Sin draft activo</h2>
      {error ? <p role="alert">{error}</p> : null}
      <p className="empty-state">
        Crea un draft para editar el modelo antes de crear una version.
      </p>
      <button
        type="button"
        disabled={mutation.isPending}
        onClick={() => mutation.mutate()}
      >
        Crear draft
      </button>
    </section>
  );
}

function DraftEditor({
  draft,
  scenario,
}: {
  draft: ScenarioDraft;
  scenario: Scenario;
}) {
  const queryClient = useQueryClient();
  const [document, setDocument] = useState<ScenarioDraftDocument>(() =>
    cloneDocument(draft.document),
  );
  const [jsonTexts, setJsonTexts] = useState<JsonTextState>(() =>
    jsonTextsFromDocument(draft.document),
  );
  const [persistedSignature, setPersistedSignature] = useState(() =>
    editorSignature(draft.document, jsonTextsFromDocument(draft.document)),
  );
  const [validationErrors, setValidationErrors] = useState<ValidationErrors>(
    {},
  );
  const [saveError, setSaveError] = useState("");
  const [generatedValidationStale, setGeneratedValidationStale] =
    useState(false);
  const [pendingRemovalId, setPendingRemovalId] = useState<string | null>(null);
  const [pendingNavigation, setPendingNavigation] = useState<string | null>(
    null,
  );
  const validationSummaryRef = useRef<HTMLDivElement | null>(null);
  const currentSignatureRef = useRef("");
  const navigate = useNavigate();

  const currentSignature = useMemo(
    () => editorSignature(document, jsonTexts),
    [document, jsonTexts],
  );
  const dirty = currentSignature !== persistedSignature;
  useEffect(() => {
    currentSignatureRef.current = currentSignature;
  }, [currentSignature]);

  useEffect(() => {
    function handleBeforeUnload(event: BeforeUnloadEvent) {
      if (!dirty) return;
      event.preventDefault();
    }
    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => window.removeEventListener("beforeunload", handleBeforeUnload);
  }, [dirty]);
  useEffect(() => {
    function handleLinkClick(event: MouseEvent) {
      if (!dirty || event.defaultPrevented || event.button !== 0) return;
      const target = event.target as HTMLElement | null;
      const anchor = target?.closest("a[href]");
      if (!anchor) return;
      const href = anchor.getAttribute("href");
      if (!href || href.startsWith("#")) return;
      const destination = new URL(
        (anchor as HTMLAnchorElement).href,
        window.location.href,
      );
      if (destination.origin !== window.location.origin) return;
      const currentPath = `${window.location.pathname}${window.location.search}${window.location.hash}`;
      const nextPath = `${destination.pathname}${destination.search}${destination.hash}`;
      if (nextPath === currentPath) return;
      event.preventDefault();
      setPendingNavigation(
        nextPath.startsWith("/react")
          ? nextPath.slice("/react".length) || "/"
          : nextPath,
      );
    }
    window.document.addEventListener("click", handleLinkClick, true);
    return () =>
      window.document.removeEventListener("click", handleLinkClick, true);
  }, [dirty]);

  const saveMutation = useMutation({
    mutationFn: (variables: {
      candidate: ScenarioDraftDocument;
      submittedSignature: string;
    }) => updateScenarioDraft(scenario.id, variables.candidate),
    onSuccess: (savedDraft, variables) => {
      setSaveError("");
      queryClient.setQueryData(draftQueryKey(scenario.id), savedDraft);
      const savedTexts = jsonTextsFromDocument(savedDraft.document);
      const savedSignature = editorSignature(savedDraft.document, savedTexts);
      setPersistedSignature(savedSignature);
      if (currentSignatureRef.current === variables.submittedSignature) {
        setDocument(cloneDocument(savedDraft.document));
        setJsonTexts(savedTexts);
      }
    },
    onError: (mutationError) => setSaveError(errorMessage(mutationError)),
  });

  function updateDocumentState(
    value: React.SetStateAction<ScenarioDraftDocument>,
  ) {
    setDocument((current) => {
      if (generatedSnapshotFromDocument(current)) {
        setGeneratedValidationStale(true);
      }
      return typeof value === "function" ? value(current) : value;
    });
    setSaveError("");
    setValidationErrors({});
  }

  function updateDocument(
    updater: (current: ScenarioDraftDocument) => ScenarioDraftDocument,
  ) {
    updateDocumentState((current) => updater(current));
  }

  function updateJsonTexts(value: React.SetStateAction<JsonTextState>) {
    if (generatedSnapshotFromDocument(document)) {
      setGeneratedValidationStale(true);
    }
    setJsonTexts(value);
    setSaveError("");
    setValidationErrors({});
  }

  function acceptGeneratedSnapshot(snapshot: GeneratedSystemCaseSnapshot) {
    const updatedDocument: ScenarioDraftDocument = {
      ...document,
      generated_system_case: snapshot,
    };
    const updatedTexts = jsonTextsFromDocument(updatedDocument);
    setDocument(cloneDocument(updatedDocument));
    setJsonTexts(updatedTexts);
    setPersistedSignature(editorSignature(updatedDocument, updatedTexts));
    setGeneratedValidationStale(false);
    queryClient.setQueryData<ScenarioDraft>(
      draftQueryKey(scenario.id),
      (current) =>
        current
          ? {
              ...current,
              document: updatedDocument,
              updated_at: new Date().toISOString(),
            }
          : current,
    );
  }

  function addAsset(assetType: DraftAssetType) {
    updateDocument((current) => {
      if ((current.assets || []).some((asset) => asset.type === assetType)) {
        return current;
      }
      return preserveGeneratedSnapshot({
        ...current,
        assets: [
          ...(current.assets || []),
          cloneDocument(defaultAssets[assetType] as ScenarioDraftDocument),
        ] as DraftAsset[],
      });
    });
    if (assetType === "hydro") {
      updateJsonTexts((current) => ({
        ...current,
        hydroGenerationCurve: jsonText(
          defaultAssets.hydro.generation_curve,
          [],
        ),
        hydroReservoirCurve: jsonText(defaultAssets.hydro.reservoir_curve, []),
      }));
    }
  }

  function confirmRemoveAsset(assetId: string) {
    updateDocument((current) =>
      preserveGeneratedSnapshot({
        ...current,
        assets: (current.assets || []).filter(
          (asset) => String(asset.id || "") !== assetId,
        ),
      }),
    );
    setPendingRemovalId(null);
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (saveMutation.isPending) return;
    const built = buildSaveDocument(document, jsonTexts);
    if (Object.keys(built.errors).length) {
      setValidationErrors(built.errors);
      setSaveError("");
      window.requestAnimationFrame(() => validationSummaryRef.current?.focus());
      return;
    }
    setDocument(cloneDocument(built.document));
    setValidationErrors({});
    const submittedSignature = editorSignature(built.document, jsonTexts);
    saveMutation.mutate({
      candidate: built.document,
      submittedSignature,
    });
  }

  function openHydraulicDiagram() {
    if (saveMutation.isPending) return;
    const built = buildSaveDocument(document, jsonTexts);
    if (Object.keys(built.errors).length) {
      setValidationErrors(built.errors);
      setSaveError("");
      window.requestAnimationFrame(() => validationSummaryRef.current?.focus());
      return;
    }
    setDocument(cloneDocument(built.document));
    setValidationErrors({});
    const submittedSignature = editorSignature(built.document, jsonTexts);
    saveMutation.mutate(
      { candidate: built.document, submittedSignature },
      {
        onSuccess: () =>
          navigate(`/scenarios/${scenario.id}/hydraulic-diagram`),
      },
    );
  }

  function persistTimeSeriesSource(source: TimeSeriesSource) {
    const updatedDocument = documentWithTimeSeriesSource(document, source);
    const updatedTexts = jsonTextsFromDocument(updatedDocument);
    setDocument(cloneDocument(updatedDocument));
    setJsonTexts(updatedTexts);
    setPersistedSignature(editorSignature(updatedDocument, updatedTexts));
    setSaveError("");
    setValidationErrors({});
    if (generatedSnapshotFromDocument(document)) {
      setGeneratedValidationStale(true);
    }
    queryClient.setQueryData<ScenarioDraft>(
      draftQueryKey(scenario.id),
      (current) =>
        current
          ? {
              ...current,
              document: updatedDocument,
            }
          : current,
    );
  }

  const presentTypes = new Set(
    (document.assets || [])
      .map((asset) => asset.type)
      .filter((type): type is DraftAssetType => isAssetType(type)),
  );
  const missingTypes = (
    ["battery", "load", "renewable", "hydro"] as DraftAssetType[]
  ).filter((assetType) => !presentTypes.has(assetType));
  const removalProps = {
    pendingRemovalId,
    onStartRemove: setPendingRemovalId,
    onCancelRemove: () => setPendingRemovalId(null),
    onConfirmRemove: confirmRemoveAsset,
  };

  return (
    <>
      {pendingNavigation ? (
        <div className="modal-backdrop" role="presentation">
          <section
            className="draft-leave-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="leave-draft-title"
          >
            <h2 id="leave-draft-title">Cambios sin guardar</h2>
            <p>Guarda o descarta cambios antes de salir del editor.</p>
            <button type="button" onClick={() => setPendingNavigation(null)}>
              Seguir editando
            </button>
            <button
              type="button"
              className="secondary-action"
              onClick={() => {
                const target = pendingNavigation;
                setPendingNavigation(null);
                navigate(target);
              }}
            >
              Descartar cambios
            </button>
          </section>
        </div>
      ) : null}
      <form className="draft-editor" onSubmit={submit}>
        <div className="draft-toolbar">
          <StatusBadge
            dirty={dirty}
            saving={saveMutation.isPending}
            failed={Boolean(saveError)}
          />
          <span>Ultimo guardado: {draft.updated_at}</span>
          <button type="submit" disabled={saveMutation.isPending}>
            Guardar draft
          </button>
        </div>
        {saveError ? <p role="alert">{saveError}</p> : null}
        {Object.keys(validationErrors).length ? (
          <div
            className="validation-summary"
            role="alert"
            tabIndex={-1}
            ref={validationSummaryRef}
          >
            Corrige los campos marcados antes de guardar.
          </div>
        ) : null}
        <section className="workspace-section" aria-labelledby="case-settings">
          <h2 id="case-settings">Caso</h2>
          <div className="draft-field-grid">
            <TextInput
              id="case_name"
              label="Nombre del caso"
              value={textValue(document.case?.name ?? scenario.name)}
              onChange={(value) =>
                updateDocument((current) =>
                  setNestedValue(current, "case", "name", value),
                )
              }
              errors={validationErrors}
              required
            />
            <TextInput
              id="schema_version"
              label="Draft schema"
              value={textValue(
                document.schema_version ?? "bess_editor_draft.v1",
              )}
              onChange={(value) =>
                updateDocument((current) =>
                  preserveGeneratedSnapshot({
                    ...current,
                    schema_version: value,
                  }),
                )
              }
              errors={validationErrors}
              required
            />
            <label
              className="field-row field-row-wide"
              htmlFor="case_description"
            >
              <span>Descripcion</span>
              <textarea
                id="case_description"
                value={textValue(document.case?.description)}
                onChange={(event) =>
                  updateDocument((current) =>
                    setNestedValue(
                      current,
                      "case",
                      "description",
                      event.target.value,
                    ),
                  )
                }
                rows={3}
              />
            </label>
          </div>
        </section>
        <section className="workspace-section" aria-labelledby="graph-settings">
          <h2 id="graph-settings">Graph, grid y solver</h2>
          <div className="draft-field-grid">
            <TextInput
              id="pcc_id"
              label="PCC ID"
              value={textValue(document.pcc?.id ?? "bus_1")}
              onChange={(value) =>
                updateDocument((current) =>
                  setNestedValue(current, "pcc", "id", value),
                )
              }
              errors={validationErrors}
              required
            />
            <SelectInput
              id="pcc_type"
              label="PCC type"
              value={textValue(document.pcc?.type ?? "bus")}
              onChange={(value) =>
                updateDocument((current) =>
                  setNestedValue(current, "pcc", "type", value),
                )
              }
              options={[
                { value: "bus", label: "bus" },
                { value: "pcc", label: "pcc" },
              ]}
            />
            <TextInput
              id="grid_id"
              label="Grid ID"
              value={textValue(document.grid?.id ?? "grid_1")}
              onChange={(value) =>
                updateDocument((current) =>
                  setNestedValue(current, "grid", "id", value),
                )
              }
              errors={validationErrors}
              required
            />
            <NumberInput
              id="grid_import_power_max_mw"
              label="Maximum import (MW)"
              value={document.grid?.import_power_max_mw}
              onChange={(value) =>
                updateDocument((current) =>
                  setNestedValue(current, "grid", "import_power_max_mw", value),
                )
              }
              errors={validationErrors}
            />
            <NumberInput
              id="grid_export_power_max_mw"
              label="Maximum export (MW)"
              value={document.grid?.export_power_max_mw}
              onChange={(value) =>
                updateDocument((current) =>
                  setNestedValue(current, "grid", "export_power_max_mw", value),
                )
              }
              errors={validationErrors}
            />
            <TextInput
              id="solver_name"
              label="Solver"
              value={textValue(document.solver?.name ?? "HiGHS")}
              onChange={(value) =>
                updateDocument((current) =>
                  setNestedValue(current, "solver", "name", value),
                )
              }
              errors={validationErrors}
            />
          </div>
          <CheckboxInput
            label="Prevent simultaneous import and export"
            checked={
              document.grid?.prevent_simultaneous_grid_import_export !== false
            }
            onChange={(value) =>
              updateDocument((current) =>
                setNestedValue(
                  current,
                  "grid",
                  "prevent_simultaneous_grid_import_export",
                  value,
                ),
              )
            }
          />
          <JsonTextarea
            id="solver_options_json"
            label="Solver options (JSON)"
            value={jsonTexts.solverOptions}
            onChange={(value) =>
              updateJsonTexts((current) => ({
                ...current,
                solverOptions: value,
              }))
            }
            errors={validationErrors}
          />
        </section>
        <section
          className="workspace-section"
          aria-labelledby="time-series-metadata"
        >
          <h2 id="time-series-metadata">Time-series metadata</h2>
          <TimeSeriesWorkflow
            scenarioId={scenario.id}
            document={document}
            dirty={dirty}
            onSourcePersisted={persistTimeSeriesSource}
          />
        </section>
        <section className="workspace-section" aria-labelledby="asset-settings">
          <div className="draft-section-heading">
            <h2 id="asset-settings">Assets</h2>
            <div className="draft-actions">
              {missingTypes.map((assetType) => (
                <button
                  key={assetType}
                  type="button"
                  className="secondary-action"
                  onClick={() => addAsset(assetType)}
                >
                  Agregar {assetLabels[assetType]}
                </button>
              ))}
            </div>
          </div>
          {(document.assets || []).length === 0 ? (
            <p className="empty-state">
              Agrega BESS, load, renewable o hydro para modelar recursos.
            </p>
          ) : null}
          {(document.assets || []).map((asset, assetIndex) => {
            const props = {
              asset,
              assetIndex,
              document,
              setDocument: updateDocumentState,
              errors: validationErrors,
              jsonTexts,
              setJsonTexts: updateJsonTexts,
              removalProps,
              onOpenHydraulicDiagram: openHydraulicDiagram,
            };
            if (asset.type === "battery")
              return <BatteryFields key={assetIndex} {...props} />;
            if (asset.type === "renewable")
              return <RenewableFields key={assetIndex} {...props} />;
            if (asset.type === "load")
              return <LoadFields key={assetIndex} {...props} />;
            if (asset.type === "hydro")
              return <HydroFields key={assetIndex} {...props} />;
            return null;
          })}
        </section>
        <GeneratedSystemCasePanel
          scenario={scenario}
          document={document}
          dirty={dirty}
          validationStale={generatedValidationStale}
          onSnapshotPersisted={acceptGeneratedSnapshot}
        />
      </form>
    </>
  );
}

export function ScenarioDraftEditorView() {
  const scenarioId = useNumericParam("scenarioId");
  const scenario = useQuery({
    queryKey: scenarioQueryKey(scenarioId || 0),
    queryFn: ({ signal }) => getScenario(scenarioId || 0, signal),
    enabled: scenarioId !== null,
    retry: false,
  });
  const project = useQuery({
    queryKey: projectQueryKey(scenario.data?.project_id || 0),
    queryFn: ({ signal }) => getProject(scenario.data!.project_id, signal),
    enabled: scenario.data !== undefined,
    retry: false,
  });
  const draft = useQuery({
    queryKey: draftQueryKey(scenarioId || 0),
    queryFn: ({ signal }) => getScenarioDraft(scenarioId || 0, signal),
    enabled: scenarioId !== null,
    retry: false,
  });

  if (scenarioId === null) {
    return <NotFoundView>El escenario solicitado no existe.</NotFoundView>;
  }
  if (scenario.isPending || draft.isPending) {
    return <LoadingView label="Cargando draft" />;
  }
  if (scenario.isError) {
    return (
      <RequestErrorView
        error={scenario.error}
        retry={() => void scenario.refetch()}
      />
    );
  }
  if (
    draft.isError &&
    !(draft.error instanceof ApiError && draft.error.status === 404)
  ) {
    return (
      <RequestErrorView
        error={draft.error}
        retry={() => void draft.refetch()}
      />
    );
  }

  return (
    <section className="workspace-view">
      <Breadcrumbs scenario={scenario.data} project={project.data} draft />
      <header className="workspace-heading">
        <h1>Draft estructurado</h1>
        <p>{scenario.data.name}</p>
      </header>
      {draft.isError ? (
        <EmptyDraftView scenario={scenario.data} />
      ) : (
        <DraftEditor
          key={draft.data.id}
          draft={draft.data}
          scenario={scenario.data}
        />
      )}
    </section>
  );
}
