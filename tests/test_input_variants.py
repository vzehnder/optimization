import unittest

from app.input_variants import (
    InputVariantRangeError,
    materialize_variant_time_series,
    resolve_bound_signal_series,
)


def price_set(periods, values):
    return {"id": 1, "periods": periods, "values": values}


def hourly_periods(start_hour, count):
    return [
        {
            "period_index": index,
            "timestamp_start": f"2026-01-01T{start_hour + index:02d}:00:00",
            "timestamp_end": f"2026-01-01T{start_hour + index + 1:02d}:00:00",
            "duration_hours": 1.0,
        }
        for index in range(count)
    ]


class ResolveBoundSignalSeriesTests(unittest.TestCase):
    def test_full_range_coverage_returns_ordered_rows(self):
        periods = hourly_periods(0, 3)
        values = [
            {"period_index": index, "signal_key": "import_price_usd_per_mwh", "value_numeric": 50.0 + index}
            for index in range(3)
        ]
        time_series_set = price_set(periods, values)

        rows = resolve_bound_signal_series(
            time_series_set,
            "import_price_usd_per_mwh",
            "2026-01-01T00:00:00",
            "2026-01-01T03:00:00",
        )

        self.assertEqual(
            rows,
            [
                {"timestamp": "2026-01-01T00:00:00", "duration_hours": 1.0, "import_price_usd_per_mwh": 50.0},
                {"timestamp": "2026-01-01T01:00:00", "duration_hours": 1.0, "import_price_usd_per_mwh": 51.0},
                {"timestamp": "2026-01-01T02:00:00", "duration_hours": 1.0, "import_price_usd_per_mwh": 52.0},
            ],
        )

    def test_range_shorter_than_full_set_slices_correctly(self):
        periods = hourly_periods(0, 5)
        values = [
            {"period_index": index, "signal_key": "import_price_usd_per_mwh", "value_numeric": float(index)}
            for index in range(5)
        ]
        time_series_set = price_set(periods, values)

        rows = resolve_bound_signal_series(
            time_series_set,
            "import_price_usd_per_mwh",
            "2026-01-01T01:00:00",
            "2026-01-01T03:00:00",
        )

        self.assertEqual([row["timestamp"] for row in rows], ["2026-01-01T01:00:00", "2026-01-01T02:00:00"])

    def test_gap_in_range_names_binding_and_missing_span(self):
        periods = [
            {
                "period_index": 0,
                "timestamp_start": "2026-01-01T00:00:00",
                "timestamp_end": "2026-01-01T01:00:00",
                "duration_hours": 1.0,
            },
            {
                "period_index": 1,
                "timestamp_start": "2026-01-01T02:00:00",
                "timestamp_end": "2026-01-01T03:00:00",
                "duration_hours": 1.0,
            },
        ]
        values = [
            {"period_index": 0, "signal_key": "import_price_usd_per_mwh", "value_numeric": 50.0},
            {"period_index": 1, "signal_key": "import_price_usd_per_mwh", "value_numeric": 55.0},
        ]
        time_series_set = price_set(periods, values)

        with self.assertRaisesRegex(
            InputVariantRangeError,
            "binding 'import_price_usd_per_mwh'.*time-series set 1.*missing coverage.*2026-01-01T01:00:00.*2026-01-01T02:00:00",
        ):
            resolve_bound_signal_series(
                time_series_set,
                "import_price_usd_per_mwh",
                "2026-01-01T00:00:00",
                "2026-01-01T03:00:00",
            )

    def test_range_start_gap_names_binding_and_missing_span(self):
        periods = hourly_periods(1, 2)
        values = [
            {"period_index": index, "signal_key": "import_price_usd_per_mwh", "value_numeric": float(index)}
            for index in range(2)
        ]
        time_series_set = price_set(periods, values)

        with self.assertRaisesRegex(
            InputVariantRangeError,
            "binding 'import_price_usd_per_mwh'.*time-series set 1.*missing coverage.*2026-01-01T00:00:00.*2026-01-01T01:00:00",
        ):
            resolve_bound_signal_series(
                time_series_set,
                "import_price_usd_per_mwh",
                "2026-01-01T00:00:00",
                "2026-01-01T03:00:00",
            )

    def test_range_extending_past_set_end_raises(self):
        periods = hourly_periods(0, 2)
        values = [
            {"period_index": index, "signal_key": "import_price_usd_per_mwh", "value_numeric": float(index)}
            for index in range(2)
        ]
        time_series_set = price_set(periods, values)

        with self.assertRaises(InputVariantRangeError):
            resolve_bound_signal_series(
                time_series_set,
                "import_price_usd_per_mwh",
                "2026-01-01T00:00:00",
                "2026-01-01T05:00:00",
            )

    def test_timezone_offset_periods_produce_naive_timestamps(self):
        periods = [
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
        ]
        values = [
            {"period_index": index, "signal_key": "price_usd_per_mwh", "value_numeric": float(index)}
            for index in range(2)
        ]
        time_series_set = price_set(periods, values)

        rows = resolve_bound_signal_series(
            time_series_set,
            "price_usd_per_mwh",
            "2026-01-01T00:00:00-03:00",
            "2026-01-01T02:00:00-03:00",
        )

        self.assertEqual(
            [row["timestamp"] for row in rows],
            ["2026-01-01T00:00:00", "2026-01-01T01:00:00"],
        )

    def test_missing_value_for_signal_raises(self):
        periods = hourly_periods(0, 2)
        values = [{"period_index": 0, "signal_key": "import_price_usd_per_mwh", "value_numeric": 50.0}]
        time_series_set = price_set(periods, values)

        with self.assertRaises(InputVariantRangeError):
            resolve_bound_signal_series(
                time_series_set,
                "import_price_usd_per_mwh",
                "2026-01-01T00:00:00",
                "2026-01-01T02:00:00",
            )


class MaterializeVariantTimeSeriesTests(unittest.TestCase):
    def test_single_bound_signal_passes_through(self):
        rows = [
            {"timestamp": "2026-01-01T00:00:00", "duration_hours": 1.0, "import_price_usd_per_mwh": 50.0},
        ]

        merged = materialize_variant_time_series({"import_price_usd_per_mwh": rows})

        self.assertEqual(merged, rows)

    def test_two_bound_signals_merge_into_wide_rows(self):
        price_rows = [
            {"timestamp": "2026-01-01T00:00:00", "duration_hours": 1.0, "import_price_usd_per_mwh": 50.0},
        ]
        demand_rows = [
            {"timestamp": "2026-01-01T00:00:00", "duration_hours": 1.0, "load_demand_mw": 12.0},
        ]

        merged = materialize_variant_time_series(
            {"import_price_usd_per_mwh": price_rows, "load_demand_mw": demand_rows}
        )

        self.assertEqual(
            merged,
            [
                {
                    "timestamp": "2026-01-01T00:00:00",
                    "duration_hours": 1.0,
                    "import_price_usd_per_mwh": 50.0,
                    "load_demand_mw": 12.0,
                }
            ],
        )

    def test_mismatched_timestamps_between_signals_raises(self):
        price_rows = [
            {"timestamp": "2026-01-01T00:00:00", "duration_hours": 1.0, "import_price_usd_per_mwh": 50.0},
        ]
        demand_rows = [
            {"timestamp": "2026-01-01T01:00:00", "duration_hours": 1.0, "load_demand_mw": 12.0},
        ]

        with self.assertRaises(InputVariantRangeError):
            materialize_variant_time_series(
                {"import_price_usd_per_mwh": price_rows, "load_demand_mw": demand_rows}
            )

    def test_mismatched_duration_between_signals_raises(self):
        price_rows = [
            {"timestamp": "2026-01-01T00:00:00", "duration_hours": 1.0, "import_price_usd_per_mwh": 50.0},
        ]
        demand_rows = [
            {"timestamp": "2026-01-01T00:00:00", "duration_hours": 2.0, "load_demand_mw": 12.0},
        ]

        with self.assertRaisesRegex(
            InputVariantRangeError,
            "horizon incompatible.*load_demand_mw.*duration.*import_price_usd_per_mwh",
        ):
            materialize_variant_time_series(
                {"import_price_usd_per_mwh": price_rows, "load_demand_mw": demand_rows}
            )


if __name__ == "__main__":
    unittest.main()
