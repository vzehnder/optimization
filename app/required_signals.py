from __future__ import annotations

from dataclasses import dataclass
from typing import Any

PRICE_SIGNAL_FAMILY: tuple[str, ...] = (
    "price_usd_per_mwh",
    "import_price_usd_per_mwh",
    "export_price_usd_per_mwh",
)

_ONE_BUS_ENTITY_SIGNALS: dict[str, tuple[str, str]] = {
    "grid": ("grid", "price_usd_per_mwh"),
    "load": ("component:load", "load_demand_mw"),
    "renewable": ("component:renewable", "renewable_available_power_mw"),
    "hydro": ("component:hydro", "hydro_inflow_m3s"),
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
    ``generate_system_case_from_draft``; each node type maps to the
    canonical ``signal_key`` its family needs, per the TS-2 signal catalog.
    """
    nodes = system_case.get("nodes")
    if not isinstance(nodes, list):
        return []

    required: list[RequiredSignal] = []
    for node in nodes:
        if not isinstance(node, dict):
            continue
        mapping = _ONE_BUS_ENTITY_SIGNALS.get(node.get("type"))
        if mapping is None:
            continue
        entity_type, signal_key = mapping
        candidates = PRICE_SIGNAL_FAMILY if entity_type == "grid" else (signal_key,)
        required.append(
            RequiredSignal(
                entity_type=entity_type,
                entity_id=str(node.get("id")),
                signal_key=signal_key,
                candidate_signal_keys=candidates,
            )
        )
    return required


def evaluate_variant_completeness(
    required_signals: list[RequiredSignal],
    bindings: list[dict[str, Any]],
) -> list[RequiredSignalStatus]:
    """Report bound/missing state for each required signal against ``bindings``.

    ``case_time_series_bindings`` rows are keyed by ``signal_key`` only (not
    yet entity-scoped; see BESS-TS3-005), so any binding whose ``signal_key``
    is one of a requirement's ``candidate_signal_keys`` satisfies it.
    """
    bindings_by_signal_key = {binding["signal_key"]: binding for binding in bindings}
    statuses: list[RequiredSignalStatus] = []
    for requirement in required_signals:
        bound_binding = next(
            (
                bindings_by_signal_key[key]
                for key in requirement.candidate_signal_keys
                if key in bindings_by_signal_key
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


def required_signal_status_to_dict(status: RequiredSignalStatus) -> dict[str, Any]:
    return {
        "entity_type": status.entity_type,
        "entity_id": status.entity_id,
        "signal_key": status.signal_key,
        "bound": status.bound,
        "bound_signal_key": status.bound_signal_key,
        "time_series_set_id": status.time_series_set_id,
    }
