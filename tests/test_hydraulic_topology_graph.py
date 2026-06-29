import unittest

from app.persistence import (
    hydraulic_first_cycle,
    hydraulic_weakly_connected_components,
)


class HydraulicTopologyGraphTests(unittest.TestCase):
    def test_acyclic_chain_has_no_cycle(self):
        cycle = hydraulic_first_cycle(
            ["reservoir", "intake", "tailrace"],
            [("reservoir", "intake"), ("intake", "tailrace")],
        )
        self.assertEqual(cycle, [])

    def test_directed_cycle_is_detected_with_path(self):
        cycle = hydraulic_first_cycle(
            ["a", "b", "c"],
            [("a", "b"), ("b", "c"), ("c", "a")],
        )
        # The path returned is the set of nodes participating in the cycle.
        self.assertEqual(set(cycle), {"a", "b", "c"})

    def test_self_loop_is_a_cycle(self):
        cycle = hydraulic_first_cycle(["a"], [("a", "a")])
        self.assertEqual(set(cycle), {"a"})

    def test_single_connected_graph_is_one_component(self):
        components = hydraulic_weakly_connected_components(
            ["a", "b", "c"],
            [("a", "b"), ("b", "c")],
        )
        self.assertEqual(len(components), 1)
        self.assertEqual(components[0], {"a", "b", "c"})

    def test_disconnected_nodes_form_separate_components(self):
        components = hydraulic_weakly_connected_components(
            ["a", "b", "c", "d"],
            [("a", "b"), ("c", "d")],
        )
        self.assertEqual([set(comp) for comp in components], [{"a", "b"}, {"c", "d"}])

    def test_isolated_node_is_its_own_component(self):
        components = hydraulic_weakly_connected_components(["a", "b"], [])
        self.assertEqual([set(comp) for comp in components], [{"a"}, {"b"}])


if __name__ == "__main__":
    unittest.main()
