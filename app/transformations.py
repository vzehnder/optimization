from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Callable

from app.time_series_catalog import TIME_SERIES_SIGNAL_CATALOG


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


ALLOWED_RESAMPLE_METHODS = {"mean", "sum"}


def _resample_methods_for_signal(signal_key: str) -> tuple[str, ...]:
    definition = TIME_SERIES_SIGNAL_CATALOG.get(signal_key)
    if definition is None:
        return ("mean",)
    return definition.resampling_methods


@dataclass(frozen=True)
class ResampleParameters:
    target_resolution_hours: float
    signal_methods: dict[str, str]


def _validate_resample_parameters(
    raw: dict[str, Any], input_set: TransformationInputSet
) -> ResampleParameters:
    target_resolution_hours_raw = raw.get("target_resolution_hours")
    try:
        target_resolution_hours = float(target_resolution_hours_raw)
    except (TypeError, ValueError) as error:
        raise TransformationError("target_resolution_hours must be numeric") from error
    if not math.isfinite(target_resolution_hours) or target_resolution_hours <= 0:
        raise TransformationError(
            "target_resolution_hours must be a positive finite number"
        )

    raw_signal_methods = raw.get("signal_methods")
    if not isinstance(raw_signal_methods, dict) or not raw_signal_methods:
        raise TransformationError(
            "signal_methods is required and must map each signal_key to a method"
        )

    known_signal_keys = {str(signal["signal_key"]) for signal in input_set.signals}
    provided_signal_keys = {str(key) for key in raw_signal_methods}
    missing = known_signal_keys - provided_signal_keys
    if missing:
        raise TransformationError(
            f"signal_methods is missing a method for signal_key(s): {sorted(missing)}"
        )
    unknown = provided_signal_keys - known_signal_keys
    if unknown:
        raise TransformationError(
            f"signal_methods references signal_key(s) not part of the input set: "
            f"{sorted(unknown)}"
        )

    signal_methods: dict[str, str] = {}
    for signal_key, method_raw in raw_signal_methods.items():
        method = str(method_raw or "").strip().lower()
        if method not in ALLOWED_RESAMPLE_METHODS:
            raise TransformationError(
                f"method {method_raw!r} for signal_key {signal_key!r} is not supported "
                f"(allowed: {sorted(ALLOWED_RESAMPLE_METHODS)})"
            )
        allowed_for_signal = _resample_methods_for_signal(str(signal_key))
        if method not in allowed_for_signal:
            raise TransformationError(
                f"method {method!r} is not physically meaningful for signal_key "
                f"{signal_key!r} (allowed: {sorted(allowed_for_signal)})"
            )
        signal_methods[str(signal_key)] = method

    periods = sorted(input_set.periods, key=lambda period: period["period_index"])
    if not periods:
        raise TransformationError("input set has no periods to resample")

    source_resolution_hours = float(periods[0]["duration_hours"])
    if source_resolution_hours <= 0:
        raise TransformationError("source period duration must be positive")
    for period in periods:
        if abs(float(period["duration_hours"]) - source_resolution_hours) > 1e-9:
            raise TransformationError(
                "resample requires a uniform source resolution; found mixed period "
                "durations"
            )
    for previous, current in zip(periods, periods[1:]):
        if previous["timestamp_end"] != current["timestamp_start"]:
            raise TransformationError(
                "resample requires contiguous periods with no gaps; found a gap "
                f"before period_index {current['period_index']}"
            )

    if target_resolution_hours <= source_resolution_hours:
        raise TransformationError(
            "target_resolution_hours must be coarser than the source resolution "
            f"({source_resolution_hours} hours); resample does not support "
            "upsampling"
        )

    groups_per_period_float = target_resolution_hours / source_resolution_hours
    groups_per_period = round(groups_per_period_float)
    if groups_per_period < 1 or abs(groups_per_period_float - groups_per_period) > 1e-6:
        raise TransformationError(
            "target_resolution_hours must be a positive integer multiple of the "
            f"source resolution ({source_resolution_hours} hours)"
        )
    if len(periods) % groups_per_period != 0:
        raise TransformationError(
            "source periods do not evenly divide into the requested "
            "target_resolution_hours"
        )

    return ResampleParameters(
        target_resolution_hours=target_resolution_hours,
        signal_methods=signal_methods,
    )


def _resample_parameters_to_dict(parameters: ResampleParameters) -> dict[str, Any]:
    return {
        "target_resolution_hours": parameters.target_resolution_hours,
        "signal_methods": dict(sorted(parameters.signal_methods.items())),
    }


def _execute_resample(
    input_set: TransformationInputSet, parameters: ResampleParameters
) -> TransformationOutput:
    periods = sorted(input_set.periods, key=lambda period: period["period_index"])
    source_resolution_hours = float(periods[0]["duration_hours"])
    groups_per_period = round(parameters.target_resolution_hours / source_resolution_hours)
    grouped_periods = [
        periods[index : index + groups_per_period]
        for index in range(0, len(periods), groups_per_period)
    ]

    values_by_signal: dict[str, dict[int, float]] = {}
    for value in input_set.values:
        values_by_signal.setdefault(str(value["signal_key"]), {})[
            int(value["period_index"])
        ] = float(value["value_numeric"])

    new_periods = [
        {
            "period_index": new_index,
            "timestamp_start": group[0]["timestamp_start"],
            "timestamp_end": group[-1]["timestamp_end"],
            "duration_hours": parameters.target_resolution_hours,
        }
        for new_index, group in enumerate(grouped_periods)
    ]

    new_values = []
    for signal_key, method in parameters.signal_methods.items():
        series = values_by_signal.get(signal_key, {})
        for new_index, group in enumerate(grouped_periods):
            group_values = [series[int(period["period_index"])] for period in group]
            aggregated = (
                sum(group_values) / len(group_values)
                if method == "mean"
                else sum(group_values)
            )
            new_values.append(
                {
                    "period_index": new_index,
                    "signal_key": signal_key,
                    "value_numeric": aggregated,
                }
            )

    return TransformationOutput(
        signals=input_set.signals,
        periods=new_periods,
        values=new_values,
        lineage_inputs=[
            {
                "time_series_set_id": input_set.time_series_set_id,
                "revision_number": input_set.revision_number,
                "content_hash": input_set.content_hash,
                "signals": sorted(parameters.signal_methods),
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
    "resample": TransformationDefinition(
        transformation_type="resample",
        implementation_version=1,
        parameter_schema_version=1,
        validate_parameters=_validate_resample_parameters,
        execute=_execute_resample,
        parameters_to_dict=_resample_parameters_to_dict,
    ),
}


def get_transformation_definition(transformation_type: str) -> TransformationDefinition:
    definition = TRANSFORMATION_REGISTRY.get(transformation_type)
    if definition is None:
        raise TransformationError(
            f"unsupported transformation_type {transformation_type!r}"
        )
    return definition
