import unittest

from app.required_signals import (
    MissingRequiredSignalsError,
    discover_required_signals,
    evaluate_variant_completeness,
)


def grid_battery_system_case():
    return {
        "schema_version": "bess_system_dispatch.v2",
        "case_name": "grid_battery_case",
        "nodes": [
            {"id": "bus_1", "type": "bus"},
            {"id": "grid_1", "type": "grid"},
            {"id": "battery_1", "type": "battery"},
        ],
        "edges": [],
    }


def hybrid_system_case():
    return {
        "schema_version": "bess_system_dispatch.v2",
        "case_name": "hybrid_case",
        "nodes": [
            {"id": "bus_1", "type": "bus"},
            {"id": "grid_1", "type": "grid"},
            {"id": "battery_1", "type": "battery"},
            {"id": "load_1", "type": "load"},
            {"id": "solar_1", "type": "renewable"},
            {"id": "hydro_1", "type": "hydro"},
        ],
        "edges": [],
    }


def hydraulic_v3_system_case():
    return {
        "schema_version": "bess_system_dispatch.v3",
        "case_name": "hydraulic_case",
        "time_series": [],
        "hydraulic_network": {
            "nodes": [
                {"id": "reservoir_alpha", "type": "reservoir"},
                {"id": "junction_in", "type": "junction"},
            ],
            "reaches": [
                {
                    "id": "reach_reservoir_intake",
                    "from_node": "reservoir_alpha",
                    "to_node": "junction_in",
                    "flow_min_m3s": None,
                    "flow_min_source": "series",
                }
            ],
            "plants": [],
            "units": [],
            "curves": [],
            "required_time_series": [
                {
                    "entity_type": "hydraulic_node",
                    "entity_id": "reservoir_alpha",
                    "signal_key": "natural_inflow_m3s",
                    "binding_status": "required",
                }
            ],
        },
    }


class DiscoverRequiredSignalsTests(unittest.TestCase):
    def test_grid_only_case_requires_only_price(self):
        required = discover_required_signals(grid_battery_system_case())

        self.assertEqual(len(required), 1)
        self.assertEqual(required[0].entity_type, "grid")
        self.assertEqual(required[0].entity_id, "grid_1")
        self.assertEqual(required[0].signal_key, "price_usd_per_mwh")

    def test_hybrid_case_requires_one_signal_per_asset_family(self):
        required = discover_required_signals(hybrid_system_case())

        signal_keys_by_entity_id = {item.entity_id: item.signal_key for item in required}
        self.assertEqual(
            signal_keys_by_entity_id,
            {
                "grid_1": "price_usd_per_mwh",
                "load_1": "load_demand_mw",
                "solar_1": "renewable_available_power_mw",
                "hydro_1": "hydro_inflow_m3s",
            },
        )

    def test_hydraulic_v3_case_requires_inflow_and_series_backed_minimum_flow(self):
        required = discover_required_signals(hydraulic_v3_system_case())

        self.assertEqual(
            {(item.entity_type, item.entity_id, item.signal_key) for item in required},
            {
                ("hydraulic_node", "reservoir_alpha", "natural_inflow_m3s"),
                ("hydraulic_reach", "reach_reservoir_intake", "minimum_flow_m3s"),
            },
        )


class EvaluateVariantCompletenessTests(unittest.TestCase):
    def test_no_bindings_reports_every_required_signal_missing(self):
        required = discover_required_signals(grid_battery_system_case())

        statuses = evaluate_variant_completeness(required, bindings=[])

        self.assertEqual(len(statuses), 1)
        self.assertFalse(statuses[0].bound)
        self.assertIsNone(statuses[0].bound_signal_key)
        self.assertIsNone(statuses[0].time_series_set_id)

    def test_binding_a_candidate_signal_key_marks_family_bound(self):
        required = discover_required_signals(grid_battery_system_case())
        bindings = [
            {"signal_key": "import_price_usd_per_mwh", "time_series_set_id": 5},
        ]

        statuses = evaluate_variant_completeness(required, bindings=bindings)

        self.assertTrue(statuses[0].bound)
        self.assertEqual(statuses[0].bound_signal_key, "import_price_usd_per_mwh")
        self.assertEqual(statuses[0].time_series_set_id, 5)

    def test_entity_scoped_requirements_need_matching_entity_binding(self):
        required = discover_required_signals(
            {
                "schema_version": "bess_system_dispatch.v2",
                "case_name": "two_load_case",
                "nodes": [
                    {"id": "bus_1", "type": "bus"},
                    {"id": "grid_1", "type": "grid"},
                    {"id": "load_1", "type": "load"},
                    {"id": "load_2", "type": "load"},
                ],
                "edges": [],
            }
        )
        bindings = [
            {
                "signal_key": "load_demand_mw",
                "entity_type": "component:load",
                "entity_id": "load_1",
                "time_series_set_id": 5,
            },
        ]

        statuses = evaluate_variant_completeness(required, bindings=bindings)
        load_statuses = {
            status.entity_id: status for status in statuses if status.signal_key == "load_demand_mw"
        }

        self.assertTrue(load_statuses["load_1"].bound)
        self.assertFalse(load_statuses["load_2"].bound)


class MissingRequiredSignalsErrorTests(unittest.TestCase):
    def test_message_names_each_missing_required_signal(self):
        required = discover_required_signals(hybrid_system_case())
        statuses = evaluate_variant_completeness(required, bindings=[])
        missing = [status for status in statuses if not status.bound]

        error = MissingRequiredSignalsError(missing)

        self.assertIn("grid grid_1 requires price_usd_per_mwh", str(error))
        self.assertIn("component:load load_1 requires load_demand_mw", str(error))
        self.assertIn("component:renewable solar_1 requires renewable_available_power_mw", str(error))
        self.assertIn("component:hydro hydro_1 requires hydro_inflow_m3s", str(error))
        self.assertEqual(error.missing, missing)


if __name__ == "__main__":
    unittest.main()
