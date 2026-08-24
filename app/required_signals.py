from __future__ import annotations

from dataclasses import dataclass
from typing import Any

PRICE_SIGNAL_FAMILY: tuple[str, ...] = (
    "price_usd_per_mwh",
    "import_price_usd_per_mwh",
    "export_price_usd_per_mwh",
)



@dataclass(frozen=True)
class OneBusSignalRequirement:
    """One declarative signal a one-bus node type needs.

    ``candidate_signal_keys`` names the interchangeable family that satisfies
    the requirement; it defaults to the declared key alone.
    """

    entity_type: str
    signal_key: str
    candidate_signal_keys: tuple[str, ...] = ()

    def candidates(self) -> tuple[str, ...]:
        return self.candidate_signal_keys or (self.signal_key,)


ONE_BUS_ENTITY_SIGNALS: dict[str, tuple[OneBusSignalRequirement, ...]] = {
    "grid": (
        OneBusSignalRequirement(
            entity_type="grid",
            signal_key="price_usd_per_mwh",
            candidate_signal_keys=PRICE_SIGNAL_FAMILY,
        ),
    ),
    "load": (
        OneBusSignalRequirement(
            entity_type="component:load",
            signal_key="load_demand_mw",
        ),
    ),
    "renewable": (
        OneBusSignalRequirement(
            entity_type="component:renewable",
            signal_key="renewable_available_power_mw",
        ),
    ),
    "hydro": (
        OneBusSignalRequirement(
            entity_type="component:hydro",
            signal_key="hydro_inflow_m3s",
        ),
    ),
}


@dataclass(frozen=True)
class RequiredSignal:
    entity_type: str
    entity_id: str
    signal_key: str
    candidate_signal_keys: tuple[str, ...]


@dataclass(frozen=True)
class RequiredSignalStatus:
    entity_type: str
    entity_id: str
    signal_key: str
    bound: bool
    bound_signal_key: str | None
    time_series_set_id: int | None


class MissingRequiredSignalsError(ValueError):
    def __init__(self, missing: list[RequiredSignalStatus]):
        self.missing = missing
        descriptions = [
            f"{status.entity_type} {status.entity_id} requires {status.signal_key}"
            for status in missing
        ]
        super().__init__("missing required bindings: " + "; ".join(descriptions))


def discover_required_signals(system_case: dict[str, Any]) -> list[RequiredSignal]:
    """Derive the case's required signals from its one-bus topology.

    ``system_case`` is the flat ``nodes``/``edges`` shape produced by
    ``generate_system_case_from_draft``; each node type declares the ordered
    list of canonical signals its family needs, per the TS-2 signal catalog.
    """
    required: list[RequiredSignal] = []
    nodes = system_case.get("nodes")
    if isinstance(nodes, list):
        for node in nodes:
            if not isinstance(node, dict):
                continue
            for requirement in ONE_BUS_ENTITY_SIGNALS.get(node.get("type"), ()):
                required.append(
                    RequiredSignal(
                        entity_type=requirement.entity_type,
                        entity_id=str(node.get("id")),
                        signal_key=requirement.signal_key,
                        candidate_signal_keys=requirement.candidates(),
                    )
                )
    required.extend(_discover_hydraulic_required_signals(system_case.get("hydraulic_network")))
    return required


def _discover_hydraulic_required_signals(hydraulic_network: Any) -> list[RequiredSignal]:
    if not isinstance(hydraulic_network, dict):
        return []
    required: list[RequiredSignal] = []
    seen: set[tuple[str, str, str]] = set()
    for requirement in hydraulic_network.get("required_time_series", []):
        if not isinstance(requirement, dict):
            continue
        entity_type = str(requirement.get("entity_type") or "").strip()
        entity_id = str(requirement.get("entity_id") or "").strip()
        signal_key = str(requirement.get("signal_key") or "").strip()
        if not entity_type or not entity_id or not signal_key:
            continue
        dedupe_key = (entity_type, entity_id, signal_key)
        if dedupe_key in seen:
            continue
        required.append(
            RequiredSignal(
                entity_type=entity_type,
                entity_id=entity_id,
                signal_key=signal_key,
                candidate_signal_keys=(signal_key,),
            )
        )
        seen.add(dedupe_key)

    for reach in hydraulic_network.get("reaches", []):
        if not isinstance(reach, dict) or str(reach.get("flow_min_source") or "") != "series":
            continue
        entity_id = str(reach.get("id") or "").strip()
        if not entity_id:
            continue
        dedupe_key = ("hydraulic_reach", entity_id, "minimum_flow_m3s")
        if dedupe_key in seen:
            continue
        required.append(
            RequiredSignal(
                entity_type="hydraulic_reach",
                entity_id=entity_id,
                signal_key="minimum_flow_m3s",
                candidate_signal_keys=("minimum_flow_m3s",),
            )
        )
        seen.add(dedupe_key)
    return required


def evaluate_variant_completeness(
    required_signals: list[RequiredSignal],
    bindings: list[dict[str, Any]],
) -> list[RequiredSignalStatus]:
    """Report bound/missing state for each required signal against ``bindings``.

    Entity-scoped requirements must match the bound entity exactly. Legacy
    unscoped price bindings remain accepted as a fallback for the single-grid
    tracer-bullet path created before BESS-TS3-005.
    """
    statuses: list[RequiredSignalStatus] = []
    for requirement in required_signals:
        bound_binding = next(
            (
                binding
                for binding in bindings
                if binding["signal_key"] in requirement.candidate_signal_keys
                and _binding_matches_requirement(binding, requirement)
            ),
            None,
        )
        statuses.append(
            RequiredSignalStatus(
                entity_type=requirement.entity_type,
                entity_id=requirement.entity_id,
                signal_key=requirement.signal_key,
                bound=bound_binding is not None,
                bound_signal_key=bound_binding["signal_key"] if bound_binding else None,
                time_series_set_id=bound_binding["time_series_set_id"] if bound_binding else None,
            )
        )
    return statuses


def _binding_matches_requirement(binding: dict[str, Any], requirement: RequiredSignal) -> bool:
    binding_entity_type = _normalize_optional_scope(binding.get("entity_type"))
    binding_entity_id = _normalize_optional_scope(binding.get("entity_id"))
    if binding_entity_type is None and binding_entity_id is None:
        return requirement.signal_key in PRICE_SIGNAL_FAMILY
    return (
        binding_entity_type == requirement.entity_type
        and binding_entity_id == requirement.entity_id
    )


def _normalize_optional_scope(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def required_signal_status_to_dict(status: RequiredSignalStatus) -> dict[str, Any]:
    return {
        "entity_type": status.entity_type,
        "entity_id": status.entity_id,
        "signal_key": status.signal_key,
        "bound": status.bound,
        "bound_signal_key": status.bound_signal_key,
        "time_series_set_id": status.time_series_set_id,
    }
