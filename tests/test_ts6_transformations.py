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


if __name__ == "__main__":
    unittest.main()
