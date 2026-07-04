import type { CaseHierarchyProvenance } from "./caseHierarchy";
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
