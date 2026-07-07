import unittest

from app.variant_staleness import VariantStaleError, evaluate_variant_staleness


class EvaluateVariantStalenessTests(unittest.TestCase):
    def test_never_validated_variant_is_not_stale(self):
        result = evaluate_variant_staleness(
            recorded_dependencies=[],
            current_dependencies=[
                {"dependency_type": "topology", "dependency_id": None, "hash": "topo-1"},
            ],
        )

        self.assertFalse(result.validated)
        self.assertFalse(result.stale)
        self.assertEqual(result.reasons, [])

    def test_matching_dependencies_are_not_stale(self):
        dependencies = [
            {"dependency_type": "topology", "dependency_id": None, "hash": "topo-1"},
            {"dependency_type": "parameters", "dependency_id": None, "hash": "params-1"},
            {"dependency_type": "time_series_set", "dependency_id": "14", "hash": "set-14-a"},
        ]

        result = evaluate_variant_staleness(
            recorded_dependencies=dependencies,
            current_dependencies=dependencies,
        )

        self.assertTrue(result.validated)
        self.assertFalse(result.stale)
        self.assertEqual(result.reasons, [])

    def test_time_series_set_hash_change_is_stale_with_series_reason(self):
        recorded = [
            {"dependency_type": "topology", "dependency_id": None, "hash": "topo-1"},
            {"dependency_type": "parameters", "dependency_id": None, "hash": "params-1"},
            {"dependency_type": "time_series_set", "dependency_id": "14", "hash": "set-14-a"},
        ]
        current = [
            {"dependency_type": "topology", "dependency_id": None, "hash": "topo-1"},
            {"dependency_type": "parameters", "dependency_id": None, "hash": "params-1"},
            {"dependency_type": "time_series_set", "dependency_id": "14", "hash": "set-14-b"},
        ]

        result = evaluate_variant_staleness(recorded_dependencies=recorded, current_dependencies=current)

        self.assertTrue(result.validated)
        self.assertTrue(result.stale)
        self.assertEqual(len(result.reasons), 1)
        self.assertEqual(result.reasons[0].dependency_type, "time_series_set")
        self.assertEqual(result.reasons[0].dependency_id, "14")
        self.assertIn("time-series set 14", result.reasons[0].detail)

    def test_topology_hash_change_is_stale_with_topology_reason(self):
        recorded = [
            {"dependency_type": "topology", "dependency_id": None, "hash": "topo-1"},
            {"dependency_type": "parameters", "dependency_id": None, "hash": "params-1"},
        ]
        current = [
            {"dependency_type": "topology", "dependency_id": None, "hash": "topo-2"},
            {"dependency_type": "parameters", "dependency_id": None, "hash": "params-1"},
        ]

        result = evaluate_variant_staleness(recorded_dependencies=recorded, current_dependencies=current)

        self.assertTrue(result.stale)
        self.assertEqual(len(result.reasons), 1)
        self.assertEqual(result.reasons[0].dependency_type, "topology")
        self.assertIn("topology", result.reasons[0].detail)

    def test_parameters_hash_change_is_stale_with_parameters_reason(self):
        recorded = [
            {"dependency_type": "topology", "dependency_id": None, "hash": "topo-1"},
            {"dependency_type": "parameters", "dependency_id": None, "hash": "params-1"},
        ]
        current = [
            {"dependency_type": "topology", "dependency_id": None, "hash": "topo-1"},
            {"dependency_type": "parameters", "dependency_id": None, "hash": "params-2"},
        ]

        result = evaluate_variant_staleness(recorded_dependencies=recorded, current_dependencies=current)

        self.assertTrue(result.stale)
        self.assertEqual(len(result.reasons), 1)
        self.assertEqual(result.reasons[0].dependency_type, "parameters")
        self.assertIn("parameters", result.reasons[0].detail)

    def test_variant_stale_error_message_lists_reasons(self):
        recorded = [{"dependency_type": "topology", "dependency_id": None, "hash": "topo-1"}]
        current = [{"dependency_type": "topology", "dependency_id": None, "hash": "topo-2"}]
        result = evaluate_variant_staleness(recorded_dependencies=recorded, current_dependencies=current)

        error = VariantStaleError(
            [
                {"dependency_type": reason.dependency_type, "dependency_id": reason.dependency_id, "detail": reason.detail}
                for reason in result.reasons
            ]
        )

        self.assertIn("stale", str(error))
        self.assertIn("topology", str(error))


if __name__ == "__main__":
    unittest.main()
