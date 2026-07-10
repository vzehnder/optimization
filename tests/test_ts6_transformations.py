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


if __name__ == "__main__":
    unittest.main()
