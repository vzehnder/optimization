"""TS7-003 closed register of linkable objects and materialized components."""

import json
import os
import unittest
import uuid

from app.linkable_objects import (
    LINKABLE_OBJECT_GUARD_CODES,
    LinkableObjectError,
    linkable_object_table_names,
)
from app.persistence import AnalystStore


POSTGRES_TEST_DATABASE_URL = os.environ.get("POSTGRES_TEST_DATABASE_URL")


def attempt(connection, sql, parameters=()):
    """Run a forbidden statement and report the stable failure it raises."""

    try:
        connection.execute(sql, parameters)
    except Exception as error:  # noqa: BLE001 - the engine decides the class
        text = str(error)
        for code in LINKABLE_OBJECT_GUARD_CODES:
            if code in text:
                return code
        return "refused"
    return "accepted"


class RegisterSpaceTests(unittest.TestCase):
    def setUp(self):
        self.store = AnalystStore("sqlite:///:memory:")
        self.project = self.store.create_project(name="Cuenca Norte")

    def tearDown(self):
        self.store.close()

    def test_the_register_lands_beside_the_legacy_tables(self):
        physical_names = self.store.linkable_object_table_names()
        tables = {
            row["name"]
            for row in self.store.connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }

        self.assertEqual(
            {
                "physical_names": physical_names,
                "missing": sorted(set(physical_names.values()) - tables),
            },
            {
                "physical_names": {
                    "components": "components_next",
                    "global_signal_slots": "global_signal_slots_next",
                    "linkable_objects": "linkable_objects_next",
                },
                "missing": [],
            },
        )

    def test_a_register_row_carries_exactly_one_typed_foreign_key(self):
        tables = self.store.linkable_object_table_names()
        connection = self.store.connection
        other_project = self.store.create_project(name="Cuenca Sur")
        slot_id = self._slot(self.project["id"])
        other_slot_id = self._slot(other_project["id"])
        component_id = self._component(self.project["id"], "load_1", "load")
        bus_id = self._component(self.project["id"], "bus_1", "bus")
        insert = f"""
            INSERT INTO {tables['linkable_objects']} (
                project_id, object_kind, object_type_id, global_slot_id,
                component_id, created_at, created_by
            ) VALUES (?, ?, ?, ?, ?, '2026-01-01T00:00:00', 'test')
        """

        outcomes = {
            "no_subtype": attempt(
                connection,
                insert,
                (self.project["id"], "global_signal_slot", 1, None, None),
            ),
            "two_subtypes": attempt(
                connection,
                insert,
                (self.project["id"], "global_signal_slot", 1, slot_id, component_id),
            ),
            "branch_disagrees_with_kind": attempt(
                connection,
                insert,
                (self.project["id"], "component", 1, slot_id, None),
            ),
            "kind_disagrees_with_type": attempt(
                connection,
                insert,
                (self.project["id"], "component", 1, None, component_id),
            ),
            "type_disagrees_with_component_type": attempt(
                connection,
                insert,
                (self.project["id"], "component", 4, None, component_id),
            ),
            "component_type_outside_the_catalog": attempt(
                connection,
                insert,
                (self.project["id"], "component", 3, None, bus_id),
            ),
            "subtype_of_another_project": attempt(
                connection,
                insert,
                (self.project["id"], "global_signal_slot", 1, other_slot_id, None),
            ),
            "one_typed_reference": attempt(
                connection,
                insert,
                (self.project["id"], "global_signal_slot", 1, slot_id, None),
            ),
        }

        self.assertEqual(
            {
                "refused": sorted(
                    name for name, outcome in outcomes.items() if outcome != "accepted"
                ),
                "accepted": sorted(
                    name for name, outcome in outcomes.items() if outcome == "accepted"
                ),
                "type_mismatch": outcomes["type_disagrees_with_component_type"],
                "bus_is_not_linkable": outcomes["component_type_outside_the_catalog"],
                "project_mismatch": outcomes["subtype_of_another_project"],
                "no_subtype": outcomes["no_subtype"],
            },
            {
                "refused": [
                    "branch_disagrees_with_kind",
                    "component_type_outside_the_catalog",
                    "kind_disagrees_with_type",
                    "no_subtype",
                    "subtype_of_another_project",
                    "two_subtypes",
                    "type_disagrees_with_component_type",
                ],
                "accepted": ["one_typed_reference"],
                "type_mismatch": "TS_OBJECT_TYPE_MISMATCH",
                "bus_is_not_linkable": "TS_OBJECT_TYPE_MISMATCH",
                "project_mismatch": "TS_OBJECT_PROJECT_MISMATCH",
                "no_subtype": "TS_OBJECT_TYPE_MISMATCH",
            },
        )

    def _slot(self, project_id, slot_key="system"):
        tables = self.store.linkable_object_table_names()
        return int(
            self.store.connection.execute(
                f"""
                INSERT INTO {tables['global_signal_slots']}
                    (project_id, slot_key, display_name, created_at, created_by)
                VALUES (?, ?, 'Sistema', '2026-01-01T00:00:00', 'test')
                RETURNING id
                """,
                (project_id, slot_key),
            ).fetchone()["id"]
        )

    def _component(self, project_id, component_key, component_type):
        tables = self.store.linkable_object_table_names()
        return int(
            self.store.connection.execute(
                f"""
                INSERT INTO {tables['components']} (
                    project_id, component_key, component_type, display_name,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, '2026-01-01T00:00:00', '2026-01-01T00:00:00')
                RETURNING id
                """,
                (project_id, component_key, component_type, component_key),
            ).fetchone()["id"]
        )


class HydraulicFixture:
    """Base hydraulic rows, written directly: the register is the seam here."""

    def __init__(self, store, project_id, prefix="norte"):
        self.store = store
        self.ids = {}
        self.ids["hydraulic_system"] = self._insert(
            "hydraulic_systems",
            "project_id, system_key, display_name",
            (project_id, f"{prefix}_system", "Sistema Norte"),
        )
        self.ids["hydraulic_node"] = self._insert(
            "hydraulic_nodes",
            "hydraulic_system_id, node_key, display_name, node_type",
            (self.ids["hydraulic_system"], f"{prefix}_node", "Embalse", "reservoir"),
        )
        self.downstream_node_id = self._insert(
            "hydraulic_nodes",
            "hydraulic_system_id, node_key, display_name, node_type",
            (self.ids["hydraulic_system"], f"{prefix}_tail", "Descarga", "tailrace"),
        )
        downstream = self.downstream_node_id
        self.ids["hydraulic_reach"] = self._insert(
            "hydraulic_reaches",
            "hydraulic_system_id, reach_key, display_name, from_node_id,"
            " to_node_id, reach_type",
            (
                self.ids["hydraulic_system"],
                f"{prefix}_reach",
                "Tramo",
                self.ids["hydraulic_node"],
                downstream,
                "river",
            ),
        )
        self.ids["hydraulic_plant"] = self._insert(
            "hydraulic_plants",
            "hydraulic_system_id, plant_key, display_name",
            (self.ids["hydraulic_system"], f"{prefix}_plant", "Central"),
        )
        self.ids["hydraulic_unit"] = self._insert(
            "hydraulic_units",
            "hydraulic_plant_id, unit_key, display_name",
            (self.ids["hydraulic_plant"], f"{prefix}_unit", "Unidad 1"),
        )

    def _insert(self, table, columns, values):
        now = "2026-01-01T00:00:00"
        placeholders = ", ".join("?" for _ in values)
        row = self.store.connection.execute(
            f"""
            INSERT INTO {table} ({columns}, created_at, updated_at,
                                 created_by, updated_by)
            VALUES ({placeholders}, ?, ?, 'test', 'test') RETURNING id
            """,
            (*values, now, now),
        ).fetchone()
        return int(row["id"])


class RegistrationTests(unittest.TestCase):
    def setUp(self):
        self.store = AnalystStore("sqlite:///:memory:")
        self.project = self.store.create_project(name="Cuenca Norte")
        self.hydraulic = HydraulicFixture(self.store, self.project["id"])

    def tearDown(self):
        self.store.close()

    def test_each_accepted_family_registers_through_its_own_typed_reference(self):
        registered = {
            "global": self.store.ensure_global_signal_slot(
                project_id=self.project["id"], actor="internal_analyst"
            ),
            "component": self.store.ensure_project_component(
                project_id=self.project["id"],
                component_key="solar_1",
                component_type="renewable",
                display_name="Solar 1",
                actor="internal_analyst",
            ),
        }
        for kind, subtype_id in self.hydraulic.ids.items():
            registered[kind] = self.store.register_linkable_object(
                project_id=self.project["id"],
                object_kind=kind,
                subtype_id=subtype_id,
                actor="internal_analyst",
            )

        listed = self.store.list_linkable_objects(project_id=self.project["id"])

        self.assertEqual(
            {
                "types": {
                    name: entry["object_type_key"]
                    for name, entry in registered.items()
                },
                "keys": {
                    name: entry["object_key"] for name, entry in registered.items()
                },
                "subtype_ids": {
                    name: registered[name]["subtype_id"] == subtype_id
                    for name, subtype_id in self.hydraulic.ids.items()
                },
                "listed": len(listed),
                "owning_projects": sorted(
                    {entry["project_id"] for entry in listed}
                ),
                "all_active": all(entry["status"] == "active" for entry in listed),
            },
            {
                "types": {
                    "global": "global:system",
                    "component": "component:renewable",
                    "hydraulic_system": "hydraulic_system",
                    "hydraulic_node": "hydraulic_node",
                    "hydraulic_reach": "hydraulic_reach",
                    "hydraulic_plant": "hydraulic_plant",
                    "hydraulic_unit": "hydraulic_unit",
                },
                "keys": {
                    "global": "system",
                    "component": "solar_1",
                    "hydraulic_system": "norte_system",
                    "hydraulic_node": "norte_node",
                    "hydraulic_reach": "norte_reach",
                    "hydraulic_plant": "norte_plant",
                    "hydraulic_unit": "norte_unit",
                },
                "subtype_ids": {
                    "hydraulic_system": True,
                    "hydraulic_node": True,
                    "hydraulic_reach": True,
                    "hydraulic_plant": True,
                    "hydraulic_unit": True,
                },
                "listed": 7,
                "owning_projects": [self.project["id"]],
                "all_active": True,
            },
        )


class NonLinkableFamilyTests(unittest.TestCase):
    def setUp(self):
        self.store = AnalystStore("sqlite:///:memory:")
        self.project = self.store.create_project(name="Cuenca Norte")

    def tearDown(self):
        self.store.close()

    def _refusal(self, call, **kwargs):
        try:
            call(**kwargs)
        except LinkableObjectError as error:
            return error.code
        return "accepted"

    def test_a_family_outside_the_closed_register_cannot_be_registered(self):
        scenario = self.store.create_scenario(
            project_id=self.project["id"], name="Base"
        )
        refusals = {
            family: self._refusal(
                self.store.register_linkable_object,
                project_id=self.project["id"],
                object_kind=family,
                subtype_id=scenario["id"],
            )
            for family in (
                "project",
                "user",
                "run",
                "publication",
                "operator_console",
                "scenario",
            )
        }
        refusals["component:bus"] = self._refusal(
            self.store.ensure_project_component,
            project_id=self.project["id"],
            component_key="bus_1",
            component_type="bus",
            display_name="Barra",
        )
        refusals["global:forecast"] = self._refusal(
            self.store.ensure_global_signal_slot,
            project_id=self.project["id"],
            slot_key="forecast",
        )

        tables = self.store.linkable_object_table_names()
        leftovers = {
            logical: int(
                self.store.connection.execute(
                    f"SELECT COUNT(*) AS total FROM {physical}"
                ).fetchone()["total"]
            )
            for logical, physical in tables.items()
        }

        self.assertEqual(
            {"refusals": refusals, "leftovers": leftovers},
            {
                "refusals": {
                    "project": "TS_OBJECT_FAMILY_NOT_LINKABLE",
                    "user": "TS_OBJECT_FAMILY_NOT_LINKABLE",
                    "run": "TS_OBJECT_FAMILY_NOT_LINKABLE",
                    "publication": "TS_OBJECT_FAMILY_NOT_LINKABLE",
                    "operator_console": "TS_OBJECT_FAMILY_NOT_LINKABLE",
                    "scenario": "TS_OBJECT_FAMILY_NOT_LINKABLE",
                    "component:bus": "TS_OBJECT_FAMILY_NOT_LINKABLE",
                    "global:forecast": "TS_OBJECT_FAMILY_NOT_LINKABLE",
                },
                "leftovers": {
                    "global_signal_slots": 0,
                    "components": 0,
                    "linkable_objects": 0,
                },
            },
        )


def system_case(nodes):
    return {
        "schema_version": "bess_system_dispatch.v2",
        "case_name": "caso",
        "nodes": nodes,
        "edges": [],
        "time_series": {
            "periods": [
                {
                    "timestamp": "2026-01-01T00:00:00",
                    "duration_hours": 1.0,
                    "grid_import_price_usd_per_mwh": 10.0,
                    "grid_export_price_usd_per_mwh": 5.0,
                }
            ]
        },
        "constraints": {},
        "solver": {"name": "HiGHS", "options": {}},
    }


def editor_draft(assets, grid_id="grid_1", pcc_id="bus_1"):
    return {
        "schema_version": "bess_editor_draft.v1",
        "case": {"name": "caso"},
        "pcc": {"id": pcc_id, "type": "bus"},
        "grid": {"id": grid_id, "type": "grid"},
        "assets": assets,
        "time_series": {"sources": []},
        "solver": {"name": "HiGHS", "options": {}},
    }


class ComponentMaterializationTests(unittest.TestCase):
    def setUp(self):
        self.store = AnalystStore("sqlite:///:memory:")
        self.project = self.store.create_project(name="Cuenca Norte")
        self.scenario = self.store.create_scenario(
            project_id=self.project["id"], name="Base"
        )

    def tearDown(self):
        self.store.close()

    def _version(self, nodes):
        return self.store.create_scenario_version(
            scenario_id=self.scenario["id"],
            system_case_json=system_case(nodes),
            validation_payload={"ok": True},
        )

    def test_materialization_is_deterministic_and_repeatable(self):
        self._version(
            [
                {"id": "bus_1", "type": "bus"},
                {"id": "grid_1", "type": "grid"},
                {"id": "solar_1", "type": "renewable"},
                {"id": "load_1", "type": "load"},
            ]
        )
        self.store.create_or_replace_scenario_draft(
            scenario_id=self.scenario["id"],
            document=editor_draft(
                [
                    {"id": "solar_1", "type": "renewable"},
                    {"id": "battery_1", "type": "battery"},
                ]
            ),
        )

        first = self.store.materialize_project_linkable_objects(
            project_id=self.project["id"], actor="internal_analyst"
        )
        first_objects = {
            entry["object_type_key"] + "/" + entry["object_key"]: entry["id"]
            for entry in self.store.list_linkable_objects(
                project_id=self.project["id"]
            )
        }
        second = self.store.materialize_project_linkable_objects(
            project_id=self.project["id"], actor="internal_analyst"
        )
        second_objects = {
            entry["object_type_key"] + "/" + entry["object_key"]: entry["id"]
            for entry in self.store.list_linkable_objects(
                project_id=self.project["id"]
            )
        }

        self.assertEqual(
            {
                "first_created": first["created"],
                "second_created": second["created"],
                "second_unchanged": second["unchanged"],
                "identities_are_stable": first_objects == second_objects,
                "registered": sorted(first_objects),
            },
            {
                "first_created": 5,
                "second_created": 0,
                "second_unchanged": 5,
                "identities_are_stable": True,
                "registered": [
                    "component:battery/battery_1",
                    "component:grid/grid_1",
                    "component:load/load_1",
                    "component:renewable/solar_1",
                    "global:system/system",
                ],
            },
        )

    def test_a_key_that_carries_two_component_types_is_refused(self):
        self._version(
            [
                {"id": "bus_1", "type": "bus"},
                {"id": "grid_1", "type": "grid"},
                {"id": "asset_1", "type": "renewable"},
            ]
        )
        self._version(
            [
                {"id": "bus_1", "type": "bus"},
                {"id": "grid_1", "type": "grid"},
                {"id": "asset_1", "type": "load"},
            ]
        )

        try:
            self.store.materialize_project_linkable_objects(
                project_id=self.project["id"], actor="internal_analyst"
            )
            outcome = "accepted"
            context = {}
        except LinkableObjectError as error:
            outcome = error.code
            context = error.context

        registered = self.store.list_linkable_objects(project_id=self.project["id"])

        self.assertEqual(
            {
                "outcome": outcome,
                "component_key": context.get("component_key"),
                "component_types": context.get("component_types"),
                "nothing_was_guessed": registered,
            },
            {
                "outcome": "TS_MIGRATION_OBJECT_AMBIGUOUS",
                "component_key": "asset_1",
                "component_types": ["load", "renewable"],
                "nothing_was_guessed": [],
            },
        )

    def test_a_component_without_a_valid_key_is_never_invented(self):
        self._version(
            [
                {"id": "bus_1", "type": "bus"},
                {"id": "grid_1", "type": "grid"},
                {"id": "   ", "type": "load"},
                {"type": "battery"},
            ]
        )

        report = self.store.materialize_project_linkable_objects(
            project_id=self.project["id"], actor="internal_analyst"
        )
        registered = sorted(
            entry["object_type_key"]
            for entry in self.store.list_linkable_objects(
                project_id=self.project["id"]
            )
        )

        self.assertEqual(
            {
                "created": report["created"],
                "skipped": sorted(report["skipped"]),
                "registered": registered,
            },
            {
                "created": 2,
                "skipped": ["missing_component_key"],
                "registered": ["component:grid", "global:system"],
            },
        )


class ReferenceResolutionTests(unittest.TestCase):
    """A text pair never grants authority; it is only a lookup key."""

    def setUp(self):
        self.store = AnalystStore("sqlite:///:memory:")
        self.project = self.store.create_project(name="Cuenca Norte")
        self.other_project = self.store.create_project(name="Cuenca Sur")
        self.scenario = self.store.create_scenario(
            project_id=self.project["id"], name="Base"
        )
        self.hydraulic = HydraulicFixture(self.store, self.project["id"])
        self.other_hydraulic = HydraulicFixture(
            self.store, self.other_project["id"], prefix="sur"
        )
        self.case_id = self._case()
        self.store.materialize_project_linkable_objects(
            project_id=self.project["id"], actor="internal_analyst"
        )
        self.store.materialize_project_linkable_objects(
            project_id=self.other_project["id"], actor="internal_analyst"
        )

    def tearDown(self):
        self.store.close()

    def _case(self):
        now = "2026-01-01T00:00:00"
        row = self.store.connection.execute(
            """
            INSERT INTO optimization_cases (
                scenario_id, case_key, display_name, created_at, updated_at,
                created_by, updated_by
            ) VALUES (?, 'base', 'Caso base', ?, ?, 'test', 'test')
            RETURNING id
            """,
            (self.scenario["id"], now, now),
        ).fetchone()
        return int(row["id"])

    def _case_node(self, base_node_id):
        now = "2026-01-01T00:00:00"
        row = self.store.connection.execute(
            """
            INSERT INTO case_hydraulic_nodes (
                case_id, hydraulic_node_id, case_label, is_active,
                created_at, updated_at, created_by, updated_by
            ) VALUES (?, ?, 'copia', 1, ?, ?, 'test', 'test')
            RETURNING id
            """,
            (self.case_id, base_node_id, now, now),
        ).fetchone()
        return int(row["id"])

    def test_a_case_scoped_reference_resolves_to_the_base_entity(self):
        # The copy points at the downstream node, and its own primary key is
        # the primary key of a *different* base node. A resolver that read the
        # copy's key would land on that decoy, and this test would say so.
        base_node_id = self.hydraulic.downstream_node_id
        case_node_id = self._case_node(base_node_id)
        decoy = self.store.connection.execute(
            "SELECT id, node_key FROM hydraulic_nodes WHERE id = ?",
            (case_node_id,),
        ).fetchone()

        resolved = self.store.resolve_linkable_object_reference(
            project_id=self.project["id"],
            entity_type="case_hydraulic_node",
            entity_id=case_node_id,
        )
        base = self.store.resolve_linkable_object_reference(
            project_id=self.project["id"],
            entity_type="hydraulic_node",
            entity_id=base_node_id,
        )

        self.assertEqual(
            {
                "a_decoy_shares_the_copy_id": decoy is not None,
                "decoy_is_a_different_node": (
                    decoy is not None and int(decoy["id"]) != base_node_id
                ),
                "subtype_id": resolved["subtype_id"],
                "base_node_id": base_node_id,
                "object_key": resolved["object_key"],
                "object_type_key": resolved["object_type_key"],
                "same_object_as_the_base_reference": resolved["id"] == base["id"],
            },
            {
                "a_decoy_shares_the_copy_id": True,
                "decoy_is_a_different_node": True,
                "subtype_id": base_node_id,
                "base_node_id": base_node_id,
                "object_key": "norte_tail",
                "object_type_key": "hydraulic_node",
                "same_object_as_the_base_reference": True,
            },
        )

    def test_a_reference_from_another_project_is_refused_before_any_lookup(self):
        case_node_id = self._case_node(self.hydraulic.ids["hydraulic_node"])
        refusals = {}
        for name, kwargs in {
            "case_scoped": {
                "entity_type": "case_hydraulic_node",
                "entity_id": case_node_id,
            },
            "base_entity": {
                "entity_type": "hydraulic_node",
                "entity_id": self.hydraulic.ids["hydraulic_node"],
            },
            "hydraulic_unit": {
                "entity_type": "hydraulic_unit",
                "entity_id": self.hydraulic.ids["hydraulic_unit"],
            },
        }.items():
            try:
                self.store.resolve_linkable_object_reference(
                    project_id=self.other_project["id"], **kwargs
                )
                refusals[name] = "accepted"
            except LinkableObjectError as error:
                refusals[name] = error.code

        own_project = self.store.resolve_linkable_object_reference(
            project_id=self.project["id"],
            entity_type="hydraulic_unit",
            entity_id=self.hydraulic.ids["hydraulic_unit"],
        )

        self.assertEqual(
            {
                "refusals": refusals,
                "own_project_resolves": own_project["object_key"],
                "owning_project": own_project["project_id"],
            },
            {
                "refusals": {
                    "case_scoped": "TS_COMPAT_PROJECT_CONTEXT_MISMATCH",
                    "base_entity": "TS_COMPAT_PROJECT_CONTEXT_MISMATCH",
                    "hydraulic_unit": "TS_COMPAT_PROJECT_CONTEXT_MISMATCH",
                },
                "own_project_resolves": "norte_unit",
                "owning_project": self.project["id"],
            },
        )

    def test_a_plausible_text_pair_never_creates_or_finds_an_object(self):
        refusals = {}
        for name, kwargs in {
            "unknown_component": {
                "entity_type": "component",
                "entity_id": "solar_inventado",
            },
            "unknown_family": {"entity_type": "project", "entity_id": 1},
            "unknown_case_copy": {
                "entity_type": "case_hydraulic_node",
                "entity_id": 987654,
            },
            "unregistered_base_entity": {
                "entity_type": "hydraulic_node",
                "entity_id": 987654,
            },
        }.items():
            try:
                self.store.resolve_linkable_object_reference(
                    project_id=self.project["id"], **kwargs
                )
                refusals[name] = "accepted"
            except LinkableObjectError as error:
                refusals[name] = error.code

        tables = self.store.linkable_object_table_names()
        component_rows = int(
            self.store.connection.execute(
                f"SELECT COUNT(*) AS total FROM {tables['components']}"
            ).fetchone()["total"]
        )

        self.assertEqual(
            {"refusals": refusals, "components_created": component_rows},
            {
                "refusals": {
                    "unknown_component": "TS_OBJECT_NOT_REGISTERED",
                    "unknown_family": "TS_OBJECT_FAMILY_NOT_LINKABLE",
                    "unknown_case_copy": "TS_OBJECT_NOT_REGISTERED",
                    "unregistered_base_entity": "TS_OBJECT_NOT_REGISTERED",
                },
                "components_created": 0,
            },
        )


class RegisterOrphanTests(unittest.TestCase):
    def setUp(self):
        self.store = AnalystStore("sqlite:///:memory:")
        self.project = self.store.create_project(name="Cuenca Norte")
        self.hydraulic = HydraulicFixture(self.store, self.project["id"])
        self.component = self.store.ensure_project_component(
            project_id=self.project["id"],
            component_key="solar_1",
            component_type="renewable",
            display_name="Solar 1",
        )
        self.node = self.store.register_linkable_object(
            project_id=self.project["id"],
            object_kind="hydraulic_node",
            subtype_id=self.hydraulic.ids["hydraulic_node"],
        )

    def tearDown(self):
        self.store.close()

    def _register_rows(self):
        tables = self.store.linkable_object_table_names()
        return [
            dict(row)
            for row in self.store.connection.execute(
                f"SELECT * FROM {tables['linkable_objects']} ORDER BY id"
            ).fetchall()
        ]

    def test_deleting_a_subtype_row_takes_its_register_row_with_it(self):
        before = len(self._register_rows())
        self.store.connection.execute(
            "DELETE FROM hydraulic_nodes WHERE id = ?",
            (self.hydraulic.ids["hydraulic_node"],),
        )
        after = self._register_rows()

        self.assertEqual(
            {
                "before": before,
                "after": len(after),
                "orphans": [
                    row["id"] for row in after if row["hydraulic_node_id"] is not None
                ],
                "component_survives": [
                    row["object_kind"] for row in after
                ],
            },
            {
                "before": 2,
                "after": 1,
                "orphans": [],
                "component_survives": ["component"],
            },
        )

    def test_archiving_a_component_behind_the_register_is_refused(self):
        tables = self.store.linkable_object_table_names()
        behind_its_back = attempt(
            self.store.connection,
            f"UPDATE {tables['components']} SET is_active = 0 WHERE id = ?",
            (self.component["subtype_id"],),
        )

        archived = self.store.archive_linkable_object(
            linkable_object_id=self.component["id"],
            actor="internal_analyst",
            reason_text="retirada del caso",
        )
        component_row = dict(
            self.store.connection.execute(
                f"SELECT * FROM {tables['components']} WHERE id = ?",
                (self.component["subtype_id"],),
            ).fetchone()
        )
        listed = self.store.list_linkable_objects(project_id=self.project["id"])
        with_archived = self.store.list_linkable_objects(
            project_id=self.project["id"], include_archived=True
        )

        self.assertEqual(
            {
                "behind_its_back": behind_its_back,
                "status": archived["status"],
                "component_is_active": int(component_row["is_active"]),
                "listed_kinds": sorted(entry["object_kind"] for entry in listed),
                "history_kept": sorted(
                    entry["object_kind"] for entry in with_archived
                ),
                "archived_by": archived["archived_by"],
            },
            {
                "behind_its_back": "TS_OBJECT_REGISTER_ORPHAN",
                "status": "archived",
                "component_is_active": 0,
                "listed_kinds": ["hydraulic_node"],
                "history_kept": ["component", "hydraulic_node"],
                "archived_by": "internal_analyst",
            },
        )

    def test_deleting_the_project_leaves_no_register_row_behind(self):
        self.store.delete_project(self.project["id"])
        tables = self.store.linkable_object_table_names()

        remaining = {
            logical: int(
                self.store.connection.execute(
                    f"SELECT COUNT(*) AS total FROM {physical}"
                ).fetchone()["total"]
            )
            for logical, physical in tables.items()
        }

        self.assertEqual(
            remaining,
            {"global_signal_slots": 0, "components": 0, "linkable_objects": 0},
        )


class CrossProjectComponentTests(unittest.TestCase):
    """The same technical key in two projects is two objects, never one."""

    def setUp(self):
        self.store = AnalystStore("sqlite:///:memory:")
        self.north = self.store.create_project(name="Cuenca Norte")
        self.south = self.store.create_project(name="Cuenca Sur")

    def tearDown(self):
        self.store.close()

    def test_a_shared_key_never_merges_two_projects_into_one_object(self):
        north = self.store.ensure_project_component(
            project_id=self.north["id"],
            component_key="solar_1",
            component_type="renewable",
            display_name="Solar norte",
        )
        south = self.store.ensure_project_component(
            project_id=self.south["id"],
            component_key="solar_1",
            component_type="renewable",
            display_name="Solar sur",
        )

        resolved_north = self.store.resolve_linkable_object_reference(
            project_id=self.north["id"],
            entity_type="component:renewable",
            entity_id="solar_1",
        )
        try:
            self.store.resolve_linkable_object_reference(
                project_id=self.north["id"],
                entity_type="component:load",
                entity_id="solar_1",
            )
            declared_type_lie = "accepted"
        except LinkableObjectError as error:
            declared_type_lie = error.code

        self.assertEqual(
            {
                "distinct_objects": north["id"] != south["id"],
                "distinct_components": north["subtype_id"] != south["subtype_id"],
                "north_owner": north["project_id"],
                "south_owner": south["project_id"],
                "resolves_within_its_project": resolved_north["id"] == north["id"],
                "declared_type_lie": declared_type_lie,
            },
            {
                "distinct_objects": True,
                "distinct_components": True,
                "north_owner": self.north["id"],
                "south_owner": self.south["id"],
                "resolves_within_its_project": True,
                "declared_type_lie": "TS_OBJECT_TYPE_MISMATCH",
            },
        )


class OwnerReferenceTests(unittest.TestCase):
    """The reference TS7-002 carried here: a set owned by an object.

    Chapter 9.6 propagates the project only where a real composite foreign key
    allows it, so the check runs against the engine directly rather than through
    an API that could be the only thing enforcing it.
    """

    def setUp(self):
        self.store = AnalystStore("sqlite:///:memory:")
        self.north = self.store.create_project(name="Cuenca Norte")
        self.south = self.store.create_project(name="Cuenca Sur")
        self.north_object = self.store.ensure_global_signal_slot(
            project_id=self.north["id"]
        )
        self.south_object = self.store.ensure_global_signal_slot(
            project_id=self.south["id"]
        )

    def tearDown(self):
        self.store.close()

    def _insert_object_specific_set(self, owner_project_id, owner_object_id):
        sets_table = self.store.canonical_table_names()["time_series_sets"]
        now = "2026-01-01T00:00:00"
        return attempt(
            self.store.connection,
            f"""
            INSERT INTO {sets_table} (
                owner_project_id, name, version_number, version_label,
                visibility_scope, series_kind, owner_linkable_object_id,
                object_series_key, object_specific_signal_id, status,
                created_at, updated_at, created_by, updated_by
            ) VALUES (?, 'afluente_local', 1, 'object', 'project',
                      'object_specific', ?, 'afluente_local', 1, 'draft',
                      ?, ?, 'test', 'test')
            """,
            (owner_project_id, owner_object_id, now, now),
        )

    def test_a_set_cannot_be_owned_by_an_object_of_another_project(self):
        outcomes = {
            "foreign_object": self._insert_object_specific_set(
                self.north["id"], self.south_object["id"]
            ),
            "unregistered_object": self._insert_object_specific_set(
                self.north["id"], 987654
            ),
            "own_object": self._insert_object_specific_set(
                self.north["id"], self.north_object["id"]
            ),
        }

        self.assertEqual(
            outcomes,
            {
                "foreign_object": "refused",
                "unregistered_object": "refused",
                "own_object": "accepted",
            },
        )


@unittest.skipUnless(
    POSTGRES_TEST_DATABASE_URL,
    "set POSTGRES_TEST_DATABASE_URL to run the PostgreSQL contract tests",
)
class PostgresRegisterTests(unittest.TestCase):
    """The same register, the same refusals, on the development PostgreSQL."""

    def setUp(self):
        self.store = AnalystStore(POSTGRES_TEST_DATABASE_URL)
        self.suffix = uuid.uuid4().hex[:8]
        self.project = self.store.create_project(name=f"TS7-003 {self.suffix}")
        self.other = self.store.create_project(name=f"TS7-003 otro {self.suffix}")

    def tearDown(self):
        try:
            sets_table = self.store.canonical_table_names()["time_series_sets"]
            for project in (self.project, self.other):
                self.store.connection.execute(
                    f"DELETE FROM {sets_table} WHERE owner_project_id = ?",
                    (project["id"],),
                )
                self.store.delete_project(project["id"])
        finally:
            self.store.close()

    def test_postgres_lands_the_register_in_the_canonical_schema(self):
        tables = self.store.linkable_object_table_names()
        schemas = sorted(
            {
                str(row["table_schema"])
                for row in self.store.connection.execute(
                    """
                    SELECT table_schema
                    FROM information_schema.tables
                    WHERE table_name IN
                        ('linkable_objects', 'components', 'global_signal_slots')
                    """
                ).fetchall()
            }
        )

        self.assertEqual(
            {"tables": tables, "schemas": schemas},
            {
                "tables": {
                    "components": "ts_next.components",
                    "global_signal_slots": "ts_next.global_signal_slots",
                    "linkable_objects": "ts_next.linkable_objects",
                },
                "schemas": ["ts_next"],
            },
        )

    def test_postgres_refuses_the_same_register_writes_by_the_same_name(self):
        tables = self.store.linkable_object_table_names()
        connection = self.store.connection
        own = self.store.ensure_global_signal_slot(project_id=self.project["id"])
        foreign = self.store.ensure_global_signal_slot(project_id=self.other["id"])
        component = self.store.ensure_project_component(
            project_id=self.project["id"],
            component_key=f"solar_{self.suffix}",
            component_type="renewable",
        )
        insert = f"""
            INSERT INTO {tables['linkable_objects']} (
                project_id, object_kind, object_type_id, global_slot_id,
                component_id, created_at, created_by
            ) VALUES (?, ?, ?, ?, ?, '2026-01-01T00:00:00', 'test')
        """

        outcomes = {
            "no_subtype": attempt(
                connection,
                insert,
                (self.project["id"], "global_signal_slot", 1, None, None),
            ),
            "two_subtypes": attempt(
                connection,
                insert,
                (
                    self.project["id"],
                    "global_signal_slot",
                    1,
                    own["subtype_id"],
                    component["subtype_id"],
                ),
            ),
            "kind_disagrees_with_type": attempt(
                connection,
                insert,
                (self.project["id"], "component", 1, None, component["subtype_id"]),
            ),
            "subtype_of_another_project": attempt(
                connection,
                insert,
                (
                    self.project["id"],
                    "global_signal_slot",
                    1,
                    foreign["subtype_id"],
                    None,
                ),
            ),
            "component_retired_behind_the_register": attempt(
                connection,
                f"UPDATE {tables['components']} SET is_active = 0 WHERE id = ?",
                (component["subtype_id"],),
            ),
        }

        self.assertEqual(
            outcomes,
            {
                "no_subtype": "TS_OBJECT_TYPE_MISMATCH",
                "two_subtypes": "refused",
                "kind_disagrees_with_type": "TS_OBJECT_TYPE_MISMATCH",
                "subtype_of_another_project": "TS_OBJECT_PROJECT_MISMATCH",
                "component_retired_behind_the_register": "TS_OBJECT_REGISTER_ORPHAN",
            },
        )

    def test_postgres_refuses_a_set_owned_by_an_object_of_another_project(self):
        sets_table = self.store.canonical_table_names()["time_series_sets"]
        own = self.store.ensure_global_signal_slot(project_id=self.project["id"])
        foreign = self.store.ensure_global_signal_slot(project_id=self.other["id"])
        now = "2026-01-01T00:00:00"
        statement = f"""
            INSERT INTO {sets_table} (
                owner_project_id, name, version_number, version_label,
                visibility_scope, series_kind, owner_linkable_object_id,
                object_series_key, object_specific_signal_id, status,
                created_at, updated_at, created_by, updated_by
            ) VALUES (?, ?, 1, 'object', 'project', 'object_specific', ?, ?, 1,
                      'draft', ?, ?, 'test', 'test')
        """

        outcomes = {
            "foreign_object": attempt(
                self.store.connection,
                statement,
                (
                    self.project["id"],
                    f"afluente_{self.suffix}",
                    foreign["id"],
                    f"afluente_{self.suffix}",
                    now,
                    now,
                ),
            ),
            "unregistered_object": attempt(
                self.store.connection,
                statement,
                (
                    self.project["id"],
                    f"afluente_x_{self.suffix}",
                    987654321,
                    f"afluente_x_{self.suffix}",
                    now,
                    now,
                ),
            ),
            "own_object": attempt(
                self.store.connection,
                statement,
                (
                    self.project["id"],
                    f"afluente_ok_{self.suffix}",
                    own["id"],
                    f"afluente_ok_{self.suffix}",
                    now,
                    now,
                ),
            ),
        }

        self.assertEqual(
            outcomes,
            {
                "foreign_object": "refused",
                "unregistered_object": "refused",
                "own_object": "accepted",
            },
        )

    def test_postgres_materializes_the_same_objects_and_repeats(self):
        scenario = self.store.create_scenario(
            project_id=self.project["id"], name=f"Base {self.suffix}"
        )
        self.store.create_scenario_version(
            scenario_id=scenario["id"],
            system_case_json=system_case(
                [
                    {"id": "bus_1", "type": "bus"},
                    {"id": "grid_1", "type": "grid"},
                    {"id": "solar_1", "type": "renewable"},
                ]
            ),
            validation_payload={"ok": True},
        )

        first = self.store.materialize_project_linkable_objects(
            project_id=self.project["id"], actor="internal_analyst"
        )
        second = self.store.materialize_project_linkable_objects(
            project_id=self.project["id"], actor="internal_analyst"
        )
        registered = sorted(
            entry["object_type_key"] + "/" + entry["object_key"]
            for entry in self.store.list_linkable_objects(
                project_id=self.project["id"]
            )
        )

        self.assertEqual(
            {
                "first_created": first["created"],
                "second_created": second["created"],
                "second_unchanged": second["unchanged"],
                "registered": registered,
            },
            {
                "first_created": 3,
                "second_created": 0,
                "second_unchanged": 3,
                "registered": [
                    "component:grid/grid_1",
                    "component:renewable/solar_1",
                    "global:system/system",
                ],
            },
        )


if __name__ == "__main__":
    unittest.main()
