import type { CaseHierarchyProvenance } from "./caseHierarchy";
import { Link } from "react-router-dom";
import {
  hierarchyKindLabel,
  hierarchyProvenanceHashLabel,
} from "./caseHierarchy";

export function CaseHierarchyProvenanceSummary({
  provenance,
}: {
  provenance: CaseHierarchyProvenance | undefined;
}) {
  return (
    <dl className="source-metadata hierarchy-provenance">
      {provenance?.kind ? (
        <div>
          <dt>Modelo</dt>
          <dd>{hierarchyKindLabel(provenance.kind)}</dd>
        </div>
      ) : null}
      {provenance?.source_scenario_version_id ? (
        <div>
          <dt>Red de origen</dt>
          <dd>
            <Link
              to={`/scenario-versions/${provenance.source_scenario_version_id}`}
            >
              Versión{" "}
              {provenance.source_version_number ??
                provenance.source_scenario_version_id}
            </Link>
          </dd>
        </div>
      ) : null}
      {provenance?.hydraulic_simulation ? (
        <>
          <div>
            <dt>Objetivo</dt>
            <dd>
              {provenance.hydraulic_simulation.objective === "market_value"
                ? "Ingresos con CMg"
                : "Energía"}
            </dd>
          </div>
          <div>
            <dt>Resolución</dt>
            <dd>{provenance.hydraulic_simulation.resolution_hours} h</dd>
          </div>
          {provenance.hydraulic_simulation.mip_rel_gap !== undefined && (
            <div>
              <dt>Gap relativo de parada</dt>
              <dd>
                {Number(
                  (
                    provenance.hydraulic_simulation.mip_rel_gap * 100
                  ).toPrecision(12),
                )}{" "}
                %
              </dd>
            </div>
          )}
          {Object.entries(
            provenance.hydraulic_simulation.terminal_water_values_usd_per_hm3 ??
              {},
          ).map(([id, value]) => (
            <div key={id}>
              <dt>Valor del agua · {id}</dt>
              <dd>{value} USD/hm³</dd>
            </div>
          ))}
        </>
      ) : null}
      <div>
        <dt>Topologia</dt>
        <dd>{hierarchyProvenanceHashLabel(provenance?.topology)}</dd>
      </div>
      <div>
        <dt>Parametros</dt>
        <dd>{hierarchyProvenanceHashLabel(provenance?.parameters)}</dd>
      </div>
    </dl>
  );
}

export function HierarchyStaleBadges({
  topologyStale,
  parametersStale,
  fallbackMessage,
}: {
  topologyStale?: boolean;
  parametersStale?: boolean;
  fallbackMessage: string;
}) {
  if (topologyStale === undefined && parametersStale === undefined) {
    return (
      <p className="hierarchy-stale-badge" role="status">
        {fallbackMessage}
      </p>
    );
  }
  return (
    <div className="hierarchy-stale-flags" role="status">
      {topologyStale ? (
        <span className="hierarchy-stale-badge hierarchy-stale-badge-topology">
          Topologia desactualizada
        </span>
      ) : null}
      {parametersStale ? (
        <span className="hierarchy-stale-badge hierarchy-stale-badge-parameters">
          Parametros desactualizados
        </span>
      ) : null}
    </div>
  );
}
