from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class StaleReason:
    dependency_type: str
    dependency_id: str | None
    detail: str


@dataclass(frozen=True)
class VariantStalenessResult:
    validated: bool
    stale: bool
    reasons: list[StaleReason]


class VariantStaleError(ValueError):
    def __init__(self, reasons: list[dict[str, Any]]):
        self.reasons = reasons
        descriptions = [str(reason["detail"]) for reason in reasons]
        super().__init__(
            "input variant is stale; revalidate before running: " + "; ".join(descriptions)
        )


def _dependency_label(dependency_type: str, dependency_id: str | None) -> str:
    if dependency_type == "time_series_set":
        return f"time-series set {dependency_id}"
    if dependency_type == "topology":
        return "case topology"
    if dependency_type == "parameters":
        return "case parameters"
    return f"{dependency_type} {dependency_id}"


def evaluate_variant_staleness(
    *,
    recorded_dependencies: list[dict[str, Any]],
    current_dependencies: list[dict[str, Any]],
) -> VariantStalenessResult:
    """Compare a variant's last-validated dependency hashes against current ones.

    ``recorded_dependencies`` is empty when the variant has never been
    validated; an unvalidated variant is not considered stale since there is
    nothing recorded yet to have drifted from.
    """
    if not recorded_dependencies:
        return VariantStalenessResult(validated=False, stale=False, reasons=[])

    recorded_by_key = {
        (dep["dependency_type"], dep["dependency_id"]): dep["hash"] for dep in recorded_dependencies
    }
    current_by_key = {
        (dep["dependency_type"], dep["dependency_id"]): dep["hash"] for dep in current_dependencies
    }

    reasons: list[StaleReason] = []
    for key, current_hash in current_by_key.items():
        dependency_type, dependency_id = key
        recorded_hash = recorded_by_key.get(key)
        if recorded_hash is None:
            reasons.append(
                StaleReason(
                    dependency_type=dependency_type,
                    dependency_id=dependency_id,
                    detail=f"{_dependency_label(dependency_type, dependency_id)} added since last validation",
                )
            )
        elif recorded_hash != current_hash:
            reasons.append(
                StaleReason(
                    dependency_type=dependency_type,
                    dependency_id=dependency_id,
                    detail=f"{_dependency_label(dependency_type, dependency_id)} changed since last validation",
                )
            )
    for key in recorded_by_key:
        if key not in current_by_key:
            dependency_type, dependency_id = key
            reasons.append(
                StaleReason(
                    dependency_type=dependency_type,
                    dependency_id=dependency_id,
                    detail=f"{_dependency_label(dependency_type, dependency_id)} no longer bound",
                )
            )

    return VariantStalenessResult(validated=True, stale=bool(reasons), reasons=reasons)


def variant_staleness_result_to_dict(result: VariantStalenessResult) -> dict[str, Any]:
    return {
        "validated": result.validated,
        "stale": result.stale,
        "reasons": [
            {
                "dependency_type": reason.dependency_type,
                "dependency_id": reason.dependency_id,
                "detail": reason.detail,
            }
            for reason in result.reasons
        ],
    }
