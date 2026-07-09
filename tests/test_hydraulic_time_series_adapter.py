import unittest

from app.hydraulic_time_series_adapter import (
    build_hydraulic_catalog_detail,
    build_hydraulic_catalog_summary,
)


def _raw_node_row(**overrides):
    row = {
        "id": 7,
        "project_id": 1,
        "entity_type": "hydraulic_node",
        "entity_id": 3,
        "entity_key": "reservoir_alpha",
        "entity_display_name": "Reservoir Alpha",
        "hydraulic_system_name": "Laja System",
        "signal_key": "natural_inflow_m3s",
        "version_number": 1,
        "version_label": "v1",
        "content_hash": "sha256:abc",
        "status": "draft",
        "period_count": 2,
        "created_at": "2026-07-09T00:00:00",
        "updated_at": "2026-07-09T00:00:00",
    }
    row.update(overrides)
    return row


def _points(*values):
    return [
        {
            "timestamp": f"2026-01-01T{index:02d}:00:00",
            "duration_hours": 1.0,
            "value_m3s": float(value),
        }
        for index, value in enumerate(values)
    ]


class BuildHydraulicCatalogDetailTests(unittest.TestCase):
    def test_shapes_periods_and_values_from_points(self):
        detail = build_hydraulic_catalog_detail(_raw_node_row(), _points(5.0, 6.0))

        self.assertEqual(
            detail["periods"],
            [
                {
                    "period_index": 0,
                    "timestamp_start": "2026-01-01T00:00:00",
                    "timestamp_end": "2026-01-01T01:00:00",
                    "duration_hours": 1.0,
                },
                {
                    "period_index": 1,
                    "timestamp_start": "2026-01-01T01:00:00",
                    "timestamp_end": "2026-01-01T02:00:00",
                    "duration_hours": 1.0,
                },
            ],
        )
        self.assertEqual(
            detail["values"],
            [
                {"period_index": 0, "signal_key": "natural_inflow_m3s", "value_numeric": 5.0},
                {"period_index": 1, "signal_key": "natural_inflow_m3s", "value_numeric": 6.0},
            ],
        )


class BuildHydraulicCatalogSummaryTests(unittest.TestCase):
    def test_labels_origin_and_reach_signal_unit(self):
        summary = build_hydraulic_catalog_summary(
            _raw_node_row(
                entity_type="hydraulic_reach",
                entity_id=9,
                entity_key="reach_alpha_junction",
                entity_display_name="Alpha to Junction",
                signal_key="minimum_flow_m3s",
            )
        )

        self.assertEqual(
            summary["origin"],
            {
                "kind": "hydraulic_legacy",
                "entity_type": "hydraulic_reach",
                "entity_id": 9,
                "signal_key": "minimum_flow_m3s",
            },
        )
        self.assertEqual(summary["unit"], "m3/s")
        self.assertEqual(summary["name"], "Laja System / Alpha to Junction (minimum_flow_m3s)")


if __name__ == "__main__":
    unittest.main()
