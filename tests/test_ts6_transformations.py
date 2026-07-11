import unittest

from app.transformations import (
    TransformationError,
    TransformationInputSet,
    get_transformation_definition,
)


def price_input_set() -> TransformationInputSet:
    return TransformationInputSet(
        time_series_set_id=7,
        revision_number=2,
        content_hash="sha256:input",
        signals=[
            {
                "signal_key": "import_price_usd_per_mwh",
                "unit": "USD/MWh",
                "source_column": "spot_price",
                "source_unit": "USD/MWh",
                "entity_type": None,
                "entity_key": None,
            },
            {
                "signal_key": "load_demand_mw",
                "unit": "MW",
                "source_column": "demand",
                "source_unit": "MW",
                "entity_type": "component:load",
                "entity_key": None,
            },
        ],
        periods=[
            {
                "period_index": 0,
                "timestamp_start": "2026-01-01T00:00:00-03:00",
                "timestamp_end": "2026-01-01T01:00:00-03:00",
                "duration_hours": 1.0,
            },
            {
                "period_index": 1,
                "timestamp_start": "2026-01-01T01:00:00-03:00",
                "timestamp_end": "2026-01-01T02:00:00-03:00",
                "duration_hours": 1.0,
            },
        ],
        values=[
            {"period_index": 0, "signal_key": "import_price_usd_per_mwh", "value_numeric": 50.0},
            {"period_index": 0, "signal_key": "load_demand_mw", "value_numeric": 100.0},
            {"period_index": 1, "signal_key": "import_price_usd_per_mwh", "value_numeric": 60.0},
            {"period_index": 1, "signal_key": "load_demand_mw", "value_numeric": 110.0},
        ],
    )


class ScaleSignalTransformationTests(unittest.TestCase):
    def test_unknown_transformation_type_is_rejected(self):
        with self.assertRaisesRegex(TransformationError, "unsupported transformation_type"):
            get_transformation_definition("run_arbitrary_script")

    def test_scale_signal_multiplies_only_the_target_signal(self):
        definition = get_transformation_definition("scale_signal")
        input_set = price_input_set()
        parameters = definition.validate_parameters(
            {"signal_key": "load_demand_mw", "scale_factor": 1.2}, input_set
        )
        output = definition.execute(input_set, parameters)

        values_by_key = {
            (value["period_index"], value["signal_key"]): value["value_numeric"]
            for value in output.values
        }
        self.assertAlmostEqual(values_by_key[(0, "load_demand_mw")], 120.0)
        self.assertAlmostEqual(values_by_key[(1, "load_demand_mw")], 132.0)
        # Untouched signal passes through unchanged.
        self.assertAlmostEqual(values_by_key[(0, "import_price_usd_per_mwh")], 50.0)
        self.assertAlmostEqual(values_by_key[(1, "import_price_usd_per_mwh")], 60.0)

    def test_scale_signal_rejects_unknown_signal_key(self):
        definition = get_transformation_definition("scale_signal")
        input_set = price_input_set()
        with self.assertRaisesRegex(TransformationError, "not part of the input set"):
            definition.validate_parameters(
                {"signal_key": "renewable_available_power_mw", "scale_factor": 1.5}, input_set
            )

    def test_scale_signal_rejects_non_finite_scale_factor(self):
        definition = get_transformation_definition("scale_signal")
        input_set = price_input_set()
        with self.assertRaisesRegex(TransformationError, "finite"):
            definition.validate_parameters(
                {"signal_key": "load_demand_mw", "scale_factor": float("nan")}, input_set
            )

    def test_scale_signal_records_lineage_to_the_single_input(self):
        definition = get_transformation_definition("scale_signal")
        input_set = price_input_set()
        parameters = definition.validate_parameters(
            {"signal_key": "load_demand_mw", "scale_factor": 1.2}, input_set
        )
        output = definition.execute(input_set, parameters)

        self.assertEqual(len(output.lineage_inputs), 1)
        lineage = output.lineage_inputs[0]
        self.assertEqual(lineage["time_series_set_id"], 7)
        self.assertEqual(lineage["revision_number"], 2)
        self.assertEqual(lineage["content_hash"], "sha256:input")
        self.assertEqual(lineage["signals"], ["load_demand_mw"])

    def test_implementation_and_schema_versions_are_recorded(self):
        definition = get_transformation_definition("scale_signal")
        self.assertEqual(definition.transformation_type, "scale_signal")
        self.assertIsInstance(definition.implementation_version, int)
        self.assertIsInstance(definition.parameter_schema_version, int)


def hourly_input_set() -> TransformationInputSet:
    return TransformationInputSet(
        time_series_set_id=9,
        revision_number=1,
        content_hash="sha256:hourly-input",
        signals=[
            {
                "signal_key": "import_price_usd_per_mwh",
                "unit": "USD/MWh",
                "source_column": "price",
                "source_unit": "USD/MWh",
                "entity_type": None,
                "entity_key": None,
            },
            {
                "signal_key": "load_demand_mw",
                "unit": "MW",
                "source_column": "demand",
                "source_unit": "MW",
                "entity_type": "component:load",
                "entity_key": None,
            },
        ],
        periods=[
            {
                "period_index": index,
                "timestamp_start": f"2026-01-01T{index:02d}:00:00-03:00",
                "timestamp_end": f"2026-01-01T{index + 1:02d}:00:00-03:00",
                "duration_hours": 1.0,
            }
            for index in range(4)
        ],
        values=[
            {"period_index": index, "signal_key": "import_price_usd_per_mwh", "value_numeric": price}
            for index, price in enumerate([50.0, 60.0, 70.0, 80.0])
        ]
        + [
            {"period_index": index, "signal_key": "load_demand_mw", "value_numeric": demand}
            for index, demand in enumerate([100.0, 110.0, 120.0, 130.0])
        ],
    )


class ResampleTransformationTests(unittest.TestCase):
    def test_resample_aggregates_hourly_periods_to_the_target_resolution_using_mean(self):
        definition = get_transformation_definition("resample")
        input_set = hourly_input_set()
        parameters = definition.validate_parameters(
            {
                "target_resolution_hours": 2.0,
                "signal_methods": {
                    "import_price_usd_per_mwh": "mean",
                    "load_demand_mw": "mean",
                },
            },
            input_set,
        )
        output = definition.execute(input_set, parameters)

        self.assertEqual(len(output.periods), 2)
        self.assertEqual(output.periods[0]["duration_hours"], 2.0)
        self.assertEqual(output.periods[0]["timestamp_start"], "2026-01-01T00:00:00-03:00")
        self.assertEqual(output.periods[0]["timestamp_end"], "2026-01-01T02:00:00-03:00")

        values_by_key = {
            (value["period_index"], value["signal_key"]): value["value_numeric"]
            for value in output.values
        }
        self.assertAlmostEqual(values_by_key[(0, "import_price_usd_per_mwh")], 55.0)
        self.assertAlmostEqual(values_by_key[(1, "import_price_usd_per_mwh")], 75.0)
        self.assertAlmostEqual(values_by_key[(0, "load_demand_mw")], 105.0)
        self.assertAlmostEqual(values_by_key[(1, "load_demand_mw")], 125.0)

    def test_resample_records_lineage_with_all_transformed_signals(self):
        definition = get_transformation_definition("resample")
        input_set = hourly_input_set()
        parameters = definition.validate_parameters(
            {
                "target_resolution_hours": 4.0,
                "signal_methods": {
                    "import_price_usd_per_mwh": "mean",
                    "load_demand_mw": "mean",
                },
            },
            input_set,
        )
        output = definition.execute(input_set, parameters)

        self.assertEqual(len(output.lineage_inputs), 1)
        lineage = output.lineage_inputs[0]
        self.assertEqual(lineage["time_series_set_id"], 9)
        self.assertEqual(lineage["revision_number"], 1)
        self.assertEqual(lineage["content_hash"], "sha256:hourly-input")
        self.assertEqual(
            sorted(lineage["signals"]),
            ["import_price_usd_per_mwh", "load_demand_mw"],
        )

    def test_resample_rejects_sum_for_a_signal_that_does_not_allow_it(self):
        definition = get_transformation_definition("resample")
        input_set = hourly_input_set()
        with self.assertRaisesRegex(TransformationError, "not physically meaningful"):
            definition.validate_parameters(
                {
                    "target_resolution_hours": 2.0,
                    "signal_methods": {
                        "import_price_usd_per_mwh": "sum",
                        "load_demand_mw": "mean",
                    },
                },
                input_set,
            )

    def test_resample_rejects_upsampling_to_a_finer_resolution(self):
        definition = get_transformation_definition("resample")
        input_set = hourly_input_set()
        with self.assertRaisesRegex(TransformationError, "coarser than the source resolution"):
            definition.validate_parameters(
                {
                    "target_resolution_hours": 0.5,
                    "signal_methods": {
                        "import_price_usd_per_mwh": "mean",
                        "load_demand_mw": "mean",
                    },
                },
                input_set,
            )

    def test_resample_rejects_a_resolution_that_does_not_evenly_divide_periods(self):
        definition = get_transformation_definition("resample")
        input_set = hourly_input_set()
        with self.assertRaisesRegex(TransformationError, "evenly divide"):
            definition.validate_parameters(
                {
                    "target_resolution_hours": 3.0,
                    "signal_methods": {
                        "import_price_usd_per_mwh": "mean",
                        "load_demand_mw": "mean",
                    },
                },
                input_set,
            )

    def test_resample_rejects_missing_method_for_a_signal_in_the_set(self):
        definition = get_transformation_definition("resample")
        input_set = hourly_input_set()
        with self.assertRaisesRegex(TransformationError, "missing a method"):
            definition.validate_parameters(
                {
                    "target_resolution_hours": 2.0,
                    "signal_methods": {"import_price_usd_per_mwh": "mean"},
                },
                input_set,
            )

    def test_resample_rejects_unknown_signal_key_in_signal_methods(self):
        definition = get_transformation_definition("resample")
        input_set = hourly_input_set()
        with self.assertRaisesRegex(TransformationError, "not part of the input set"):
            definition.validate_parameters(
                {
                    "target_resolution_hours": 2.0,
                    "signal_methods": {
                        "import_price_usd_per_mwh": "mean",
                        "load_demand_mw": "mean",
                        "renewable_available_power_mw": "mean",
                    },
                },
                input_set,
            )


def gappy_input_set() -> TransformationInputSet:
    return TransformationInputSet(
        time_series_set_id=11,
        revision_number=1,
        content_hash="sha256:gappy-input",
        signals=[
            {
                "signal_key": "import_price_usd_per_mwh",
                "unit": "USD/MWh",
                "source_column": "price",
                "source_unit": "USD/MWh",
                "entity_type": None,
                "entity_key": None,
            },
            {
                "signal_key": "load_demand_mw",
                "unit": "MW",
                "source_column": "demand",
                "source_unit": "MW",
                "entity_type": "component:load",
                "entity_key": None,
            },
        ],
        periods=[
            {
                "period_index": 0,
                "timestamp_start": "2026-01-01T00:00:00-03:00",
                "timestamp_end": "2026-01-01T01:00:00-03:00",
                "duration_hours": 1.0,
            },
            {
                "period_index": 1,
                "timestamp_start": "2026-01-01T01:00:00-03:00",
                "timestamp_end": "2026-01-01T02:00:00-03:00",
                "duration_hours": 1.0,
            },
            # Gap: 2026-01-01T02:00:00-03:00 -> 2026-01-01T03:00:00-03:00 is missing.
            {
                "period_index": 2,
                "timestamp_start": "2026-01-01T03:00:00-03:00",
                "timestamp_end": "2026-01-01T04:00:00-03:00",
                "duration_hours": 1.0,
            },
        ],
        values=[
            {"period_index": 0, "signal_key": "import_price_usd_per_mwh", "value_numeric": 50.0},
            {"period_index": 0, "signal_key": "load_demand_mw", "value_numeric": 100.0},
            {"period_index": 1, "signal_key": "import_price_usd_per_mwh", "value_numeric": 60.0},
            {"period_index": 1, "signal_key": "load_demand_mw", "value_numeric": 110.0},
            {"period_index": 2, "signal_key": "import_price_usd_per_mwh", "value_numeric": 80.0},
            {"period_index": 2, "signal_key": "load_demand_mw", "value_numeric": 130.0},
        ],
    )


class InterpolateGapsTransformationTests(unittest.TestCase):
    def test_interpolate_gaps_fills_a_single_missing_period_with_linear_interpolation(self):
        definition = get_transformation_definition("interpolate_gaps")
        input_set = gappy_input_set()
        parameters = definition.validate_parameters(
            {"method": "linear", "max_gap_hours": 2.0}, input_set
        )
        output = definition.execute(input_set, parameters)

        self.assertEqual(len(output.periods), 4)
        values_by_key = {
            (value["period_index"], value["signal_key"]): value["value_numeric"]
            for value in output.values
        }
        self.assertAlmostEqual(values_by_key[(2, "load_demand_mw")], 120.0)
        self.assertAlmostEqual(values_by_key[(2, "import_price_usd_per_mwh")], 70.0)
        # Observed values pass through unchanged (though renumbered after the gap).
        self.assertAlmostEqual(values_by_key[(0, "load_demand_mw")], 100.0)
        self.assertAlmostEqual(values_by_key[(1, "load_demand_mw")], 110.0)
        self.assertAlmostEqual(values_by_key[(3, "load_demand_mw")], 130.0)

    def test_interpolate_gaps_records_filled_periods_and_lineage(self):
        definition = get_transformation_definition("interpolate_gaps")
        input_set = gappy_input_set()
        parameters = definition.validate_parameters(
            {"method": "linear", "max_gap_hours": 2.0}, input_set
        )
        output = definition.execute(input_set, parameters)

        self.assertEqual(output.execution_metadata["filled_period_indexes"], [2])
        self.assertEqual(len(output.lineage_inputs), 1)
        lineage = output.lineage_inputs[0]
        self.assertEqual(lineage["time_series_set_id"], 11)
        self.assertEqual(lineage["revision_number"], 1)
        self.assertEqual(lineage["content_hash"], "sha256:gappy-input")
        self.assertEqual(
            sorted(lineage["signals"]),
            ["import_price_usd_per_mwh", "load_demand_mw"],
        )

    def test_interpolate_gaps_rejects_a_gap_larger_than_the_declared_maximum(self):
        definition = get_transformation_definition("interpolate_gaps")
        input_set = gappy_input_set()
        with self.assertRaisesRegex(TransformationError, "exceeds max_gap_hours") as context:
            definition.validate_parameters(
                {"method": "linear", "max_gap_hours": 0.5}, input_set
            )
        message = str(context.exception)
        self.assertIn("import_price_usd_per_mwh", message)
        self.assertIn("load_demand_mw", message)
        self.assertIn("2026-01-01T02:00:00-03:00", message)
        self.assertIn("2026-01-01T03:00:00-03:00", message)

    def test_interpolate_gaps_rejects_an_unsupported_method(self):
        definition = get_transformation_definition("interpolate_gaps")
        input_set = gappy_input_set()
        with self.assertRaisesRegex(TransformationError, "not supported"):
            definition.validate_parameters(
                {"method": "cubic_spline", "max_gap_hours": 2.0}, input_set
            )

    def test_interpolate_gaps_rejects_a_gap_not_aligned_to_source_resolution(self):
        definition = get_transformation_definition("interpolate_gaps")
        input_set = gappy_input_set()
        input_set.periods[2]["timestamp_start"] = "2026-01-01T02:30:00-03:00"
        input_set.periods[2]["timestamp_end"] = "2026-01-01T03:30:00-03:00"
        with self.assertRaisesRegex(TransformationError, "not an integer multiple"):
            definition.validate_parameters(
                {"method": "linear", "max_gap_hours": 2.0}, input_set
            )

    def test_interpolate_gaps_is_a_noop_on_the_filled_flag_when_source_has_no_gaps(self):
        definition = get_transformation_definition("interpolate_gaps")
        input_set = hourly_input_set()
        parameters = definition.validate_parameters(
            {"method": "linear", "max_gap_hours": 2.0}, input_set
        )
        output = definition.execute(input_set, parameters)

        self.assertEqual(output.execution_metadata["filled_period_indexes"], [])
        self.assertEqual(len(output.periods), len(input_set.periods))


def price_only_input_set() -> TransformationInputSet:
    return TransformationInputSet(
        time_series_set_id=21,
        revision_number=1,
        content_hash="sha256:price-input",
        signals=[
            {
                "signal_key": "import_price_usd_per_mwh",
                "unit": "USD/MWh",
                "source_column": "price",
                "source_unit": "USD/MWh",
                "entity_type": None,
                "entity_key": None,
            },
        ],
        periods=[
            {
                "period_index": index,
                "timestamp_start": f"2026-01-01T{index:02d}:00:00-03:00",
                "timestamp_end": f"2026-01-01T{index + 1:02d}:00:00-03:00",
                "duration_hours": 1.0,
            }
            for index in range(3)
        ],
        values=[
            {"period_index": index, "signal_key": "import_price_usd_per_mwh", "value_numeric": price}
            for index, price in enumerate([50.0, 60.0, 70.0])
        ],
    )


def demand_only_input_set() -> TransformationInputSet:
    return TransformationInputSet(
        time_series_set_id=22,
        revision_number=3,
        content_hash="sha256:demand-input",
        signals=[
            {
                "signal_key": "load_demand_mw",
                "unit": "MW",
                "source_column": "demand",
                "source_unit": "MW",
                "entity_type": "component:load",
                "entity_key": None,
            },
        ],
        periods=[
            {
                "period_index": index,
                "timestamp_start": f"2026-01-01T{index:02d}:00:00-03:00",
                "timestamp_end": f"2026-01-01T{index + 1:02d}:00:00-03:00",
                "duration_hours": 1.0,
            }
            for index in range(3)
        ],
        values=[
            {"period_index": index, "signal_key": "load_demand_mw", "value_numeric": demand}
            for index, demand in enumerate([100.0, 110.0, 120.0])
        ],
    )


class CombineSignalsTransformationTests(unittest.TestCase):
    def test_combine_signals_merges_signals_from_two_inputs(self):
        definition = get_transformation_definition("combine_signals")
        price_set = price_only_input_set()
        demand_set = demand_only_input_set()
        parameters = definition.validate_parameters(
            {
                "inputs": [
                    {"time_series_set_id": 21, "signal_keys": ["import_price_usd_per_mwh"]},
                    {"time_series_set_id": 22, "signal_keys": ["load_demand_mw"]},
                ]
            },
            [price_set, demand_set],
        )
        output = definition.execute([price_set, demand_set], parameters)

        self.assertEqual(len(output.periods), 3)
        values_by_key = {
            (value["period_index"], value["signal_key"]): value["value_numeric"]
            for value in output.values
        }
        self.assertAlmostEqual(values_by_key[(0, "import_price_usd_per_mwh")], 50.0)
        self.assertAlmostEqual(values_by_key[(2, "import_price_usd_per_mwh")], 70.0)
        self.assertAlmostEqual(values_by_key[(0, "load_demand_mw")], 100.0)
        self.assertAlmostEqual(values_by_key[(2, "load_demand_mw")], 120.0)

    def test_combine_signals_records_lineage_for_every_input(self):
        definition = get_transformation_definition("combine_signals")
        price_set = price_only_input_set()
        demand_set = demand_only_input_set()
        parameters = definition.validate_parameters(
            {
                "inputs": [
                    {"time_series_set_id": 21, "signal_keys": ["import_price_usd_per_mwh"]},
                    {"time_series_set_id": 22, "signal_keys": ["load_demand_mw"]},
                ]
            },
            [price_set, demand_set],
        )
        output = definition.execute([price_set, demand_set], parameters)

        self.assertEqual(len(output.lineage_inputs), 2)
        by_id = {entry["time_series_set_id"]: entry for entry in output.lineage_inputs}
        self.assertEqual(by_id[21]["revision_number"], 1)
        self.assertEqual(by_id[21]["content_hash"], "sha256:price-input")
        self.assertEqual(by_id[21]["signals"], ["import_price_usd_per_mwh"])
        self.assertEqual(by_id[22]["revision_number"], 3)
        self.assertEqual(by_id[22]["content_hash"], "sha256:demand-input")
        self.assertEqual(by_id[22]["signals"], ["load_demand_mw"])

    def test_combine_signals_rejects_fewer_than_two_inputs(self):
        definition = get_transformation_definition("combine_signals")
        price_set = price_only_input_set()
        with self.assertRaisesRegex(TransformationError, "at least two inputs"):
            definition.validate_parameters(
                {"inputs": [{"time_series_set_id": 21, "signal_keys": ["import_price_usd_per_mwh"]}]},
                [price_set],
            )

    def test_combine_signals_rejects_a_signal_key_requested_from_two_inputs(self):
        definition = get_transformation_definition("combine_signals")
        price_set = price_only_input_set()
        other_price_set = price_only_input_set()
        with self.assertRaisesRegex(TransformationError, "more than one input"):
            definition.validate_parameters(
                {
                    "inputs": [
                        {"time_series_set_id": 21, "signal_keys": ["import_price_usd_per_mwh"]},
                        {"time_series_set_id": 21, "signal_keys": ["import_price_usd_per_mwh"]},
                    ]
                },
                [price_set, other_price_set],
            )

    def test_combine_signals_rejects_an_unknown_signal_key(self):
        definition = get_transformation_definition("combine_signals")
        price_set = price_only_input_set()
        demand_set = demand_only_input_set()
        with self.assertRaisesRegex(TransformationError, "not part of input set"):
            definition.validate_parameters(
                {
                    "inputs": [
                        {"time_series_set_id": 21, "signal_keys": ["renewable_available_power_mw"]},
                        {"time_series_set_id": 22, "signal_keys": ["load_demand_mw"]},
                    ]
                },
                [price_set, demand_set],
            )

    def test_combine_signals_rejects_mismatched_resolutions(self):
        definition = get_transformation_definition("combine_signals")
        price_set = price_only_input_set()
        coarse_demand_set = demand_only_input_set()
        coarse_demand_set.periods[0]["duration_hours"] = 2.0
        coarse_demand_set.periods[1]["duration_hours"] = 2.0
        coarse_demand_set.periods[2]["duration_hours"] = 2.0
        with self.assertRaisesRegex(TransformationError, "input set 22 has resolution"):
            definition.validate_parameters(
                {
                    "inputs": [
                        {"time_series_set_id": 21, "signal_keys": ["import_price_usd_per_mwh"]},
                        {"time_series_set_id": 22, "signal_keys": ["load_demand_mw"]},
                    ]
                },
                [price_set, coarse_demand_set],
            )

    def test_combine_signals_rejects_non_overlapping_horizons(self):
        definition = get_transformation_definition("combine_signals")
        price_set = price_only_input_set()
        later_demand_set = demand_only_input_set()
        for period in later_demand_set.periods:
            period["timestamp_start"] = period["timestamp_start"].replace("2026-01-01", "2026-02-01")
            period["timestamp_end"] = period["timestamp_end"].replace("2026-01-01", "2026-02-01")
        with self.assertRaisesRegex(TransformationError, "do not share an overlapping horizon"):
            definition.validate_parameters(
                {
                    "inputs": [
                        {"time_series_set_id": 21, "signal_keys": ["import_price_usd_per_mwh"]},
                        {"time_series_set_id": 22, "signal_keys": ["load_demand_mw"]},
                    ]
                },
                [price_set, later_demand_set],
            )


if __name__ == "__main__":
    unittest.main()
