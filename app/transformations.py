from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Callable


class TransformationError(ValueError):
    pass


@dataclass(frozen=True)
class TransformationInputSet:
    time_series_set_id: int
    revision_number: int
    content_hash: str
    signals: list[dict[str, Any]]
    periods: list[dict[str, Any]]
    values: list[dict[str, Any]]


@dataclass(frozen=True)
class TransformationOutput:
    signals: list[dict[str, Any]]
    periods: list[dict[str, Any]]
    values: list[dict[str, Any]]
    lineage_inputs: list[dict[str, Any]]


@dataclass(frozen=True)
class ScaleSignalParameters:
    signal_key: str
    scale_factor: float


def _validate_scale_signal_parameters(
    raw: dict[str, Any], input_set: TransformationInputSet
) -> ScaleSignalParameters:
    signal_key = str(raw.get("signal_key") or "").strip()
    if not signal_key:
        raise TransformationError("signal_key is required")
    known_signal_keys = {str(signal["signal_key"]) for signal in input_set.signals}
    if signal_key not in known_signal_keys:
        raise TransformationError(
            f"signal_key {signal_key!r} is not part of the input set"
        )

    scale_factor_raw = raw.get("scale_factor")
    try:
        scale_factor = float(scale_factor_raw)
    except (TypeError, ValueError) as error:
        raise TransformationError("scale_factor must be numeric") from error
    if not math.isfinite(scale_factor):
        raise TransformationError("scale_factor must be finite")

    return ScaleSignalParameters(signal_key=signal_key, scale_factor=scale_factor)


def _scale_signal_parameters_to_dict(parameters: ScaleSignalParameters) -> dict[str, Any]:
    return {"signal_key": parameters.signal_key, "scale_factor": parameters.scale_factor}


def _execute_scale_signal(
    input_set: TransformationInputSet, parameters: ScaleSignalParameters
) -> TransformationOutput:
    values = [
        {
            **value,
            "value_numeric": (
                value["value_numeric"] * parameters.scale_factor
                if value["signal_key"] == parameters.signal_key
                else value["value_numeric"]
            ),
        }
        for value in input_set.values
    ]
    return TransformationOutput(
        signals=input_set.signals,
        periods=input_set.periods,
        values=values,
        lineage_inputs=[
            {
                "time_series_set_id": input_set.time_series_set_id,
                "revision_number": input_set.revision_number,
                "content_hash": input_set.content_hash,
                "signals": [parameters.signal_key],
            }
        ],
    )


@dataclass(frozen=True)
class TransformationDefinition:
    transformation_type: str
    implementation_version: int
    parameter_schema_version: int
    validate_parameters: Callable[[dict[str, Any], TransformationInputSet], Any]
    execute: Callable[[TransformationInputSet, Any], TransformationOutput]
    parameters_to_dict: Callable[[Any], dict[str, Any]]


TRANSFORMATION_REGISTRY: dict[str, TransformationDefinition] = {
    "scale_signal": TransformationDefinition(
        transformation_type="scale_signal",
        implementation_version=1,
        parameter_schema_version=1,
        validate_parameters=_validate_scale_signal_parameters,
        execute=_execute_scale_signal,
        parameters_to_dict=_scale_signal_parameters_to_dict,
    ),
}


def get_transformation_definition(transformation_type: str) -> TransformationDefinition:
    definition = TRANSFORMATION_REGISTRY.get(transformation_type)
    if definition is None:
        raise TransformationError(
            f"unsupported transformation_type {transformation_type!r}"
        )
    return definition
