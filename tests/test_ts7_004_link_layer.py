"""TS7-004 link layers and immutable audit ledgers."""

import os
import unittest
import uuid

from app.persistence import AnalystStore
from app.time_series_links import LINK_HISTORY_IMMUTABLE, LINK_LEDGER_IMMUTABLE


POSTGRES_TEST_DATABASE_URL = os.environ.get("POSTGRES_TEST_DATABASE_URL")


def attempt(connection, sql, parameters=()):
    """Report only the observable result of a direct integrity write."""

    try:
        connection.execute(sql, parameters)
    except Exception:  # noqa: BLE001 - the database engine owns the exception type
        return "refused"
    return "accepted"


def guard_attempt(connection, sql, parameters=()):
    try:
        connection.execute(sql, parameters)
    except Exception as error:  # noqa: BLE001 - stable text is the public contract
        for code in (LINK_LEDGER_IMMUTABLE, LINK_HISTORY_IMMUTABLE):
            if code in str(error):
                return code
        return "refused"
    return "accepted"


def postgres_guard_attempt(connection, sql, parameters=()):
    """Isolate expected PostgreSQL failures in a savepoint."""

    try:
        with connection.transaction():
            connection.execute(sql, parameters)
    except Exception as error:  # noqa: BLE001 - stable text is the public contract
        for code in (LINK_LEDGER_IMMUTABLE, LINK_HISTORY_IMMUTABLE):
            if code in str(error):
                return code
        return "refused"
    return "accepted"


class LinkLayerSpaceTests(unittest.TestCase):
    def setUp(self):
        self.store = AnalystStore("sqlite:///:memory:")

    def tearDown(self):
        self.store.close()

    def test_the_link_layers_and_ledgers_land_in_the_canonical_space(self):
        physical_names = self.store.link_layer_table_names()
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
                "legacy_binding_survives": "case_time_series_bindings" in tables,
            },
            {
                "physical_names": {
                    "case_time_series_bindings": "case_time_series_bindings_next",
                    "time_series_catalog_associations": (
                        "time_series_catalog_associations_next"
                    ),
                    "time_series_link_events": "time_series_link_events_next",
                    "time_series_link_validations": (
                        "time_series_link_validations_next"
                    ),
                    "time_series_scope_events": "time_series_scope_events_next",
                },
                "missing": [],
                "legacy_binding_survives": True,
            },
        )


class AssociationCardinalityTests(unittest.TestCase):
    def setUp(self):
        self.store = AnalystStore("sqlite:///:memory:")
        self.project = self.store.create_project(name="Cuenca Norte")
        self.object = self.store.ensure_global_signal_slot(
            project_id=self.project["id"]
        )
        self.receipt = self.store.publish_canonical_set_revision(
            project_id=self.project["id"],
            name="Precios 2026",
            data_class_key="real",
            timezone="UTC",
            signals=[
                {
                    "series_key": "energy_price",
                    "display_name": "Precio de energia",
                    "semantic_type_key": "energy_price",
                    "unit_key": "usd_per_mwh",
                    "signal_role": "input",
                    "aggregation": "mean",
                }
            ],
            periods=[
                {
                    "timestamp_start": "2026-01-01T00:00:00",
                    "timestamp_end": "2026-01-01T01:00:00",
                    "duration_hours": 1.0,
                }
            ],
            values={"energy_price": [75.0]},
            actor="internal_analyst",
        )
        canonical = self.store.canonical_table_names()
        self.signal_id = int(
            self.store.connection.execute(
                f"SELECT id FROM {canonical['time_series_signals']} "
                "WHERE time_series_set_id = ?",
                (self.receipt["set_id"],),
            ).fetchone()["id"]
        )

    def tearDown(self):
        self.store.close()

    def _insert(self, *, role_id, rule_id, status="active"):
        associations = self.store.link_layer_table_names()[
            "time_series_catalog_associations"
        ]
        archived = status == "archived"
        return attempt(
            self.store.connection,
            f"""
            INSERT INTO {associations} (
                signal_id, time_series_set_id, linkable_object_id,
                binding_role_id, compatibility_rule_id, status,
                created_at, created_by, archived_at, archived_by,
                archived_reason_code
            ) VALUES (?, ?, ?, ?, ?, ?, '2026-01-01T00:00:00', 'test',
                      ?, ?, ?)
            """,
            (
                self.signal_id,
                self.receipt["set_id"],
                self.object["id"],
                role_id,
                rule_id,
                status,
                "2026-01-02T00:00:00" if archived else None,
                "test" if archived else None,
                "retired" if archived else None,
            ),
        )

    def test_only_one_active_association_exists_per_signal_object_and_role(self):
        outcomes = {
            "first": self._insert(role_id=1, rule_id=1),
            "duplicate_active": self._insert(role_id=1, rule_id=1),
            "archived_history": self._insert(
                role_id=1, rule_id=1, status="archived"
            ),
            "same_signal_in_another_role": self._insert(role_id=2, rule_id=2),
        }

        self.assertEqual(
            outcomes,
            {
                "first": "accepted",
                "duplicate_active": "refused",
                "archived_history": "accepted",
                "same_signal_in_another_role": "accepted",
            },
        )

    def test_replacing_association_identity_inserts_history_instead_of_editing_it(self):
        self.assertEqual(self._insert(role_id=1, rule_id=1), "accepted")
        associations = self.store.link_layer_table_names()[
            "time_series_catalog_associations"
        ]
        original_id = int(
            self.store.connection.execute(
                f"SELECT id FROM {associations} WHERE status = 'active'"
            ).fetchone()["id"]
        )

        identity_edit = guard_attempt(
            self.store.connection,
            f"UPDATE {associations} SET binding_role_id = 2 WHERE id = ?",
            (original_id,),
        )
        self.store.connection.execute(
            f"""
            UPDATE {associations}
            SET status = 'archived', lifecycle_revision = 2,
                archived_at = '2026-01-02T00:00:00', archived_by = 'test',
                archived_reason_code = 'replaced'
            WHERE id = ?
            """,
            (original_id,),
        )
        replacement_id = int(
            self.store.connection.execute(
                f"""
                INSERT INTO {associations} (
                    signal_id, time_series_set_id, linkable_object_id,
                    binding_role_id, compatibility_rule_id,
                    supersedes_association_id, created_at, created_by
                ) VALUES (?, ?, ?, 2, 2, ?,
                          '2026-01-02T00:00:00', 'test')
                RETURNING id
                """,
                (
                    self.signal_id,
                    self.receipt["set_id"],
                    self.object["id"],
                    original_id,
                ),
            ).fetchone()["id"]
        )
        delete_history = guard_attempt(
            self.store.connection,
            f"DELETE FROM {associations} WHERE id = ?",
            (original_id,),
        )
        history = [
            dict(row)
            for row in self.store.connection.execute(
                f"""
                SELECT id, binding_role_id, status, supersedes_association_id
                FROM {associations}
                ORDER BY id
                """
            ).fetchall()
        ]

        self.assertEqual(
            {
                "identity_edit": identity_edit,
                "delete_history": delete_history,
                "history": history,
            },
            {
                "identity_edit": LINK_HISTORY_IMMUTABLE,
                "delete_history": LINK_HISTORY_IMMUTABLE,
                "history": [
                    {
                        "id": original_id,
                        "binding_role_id": 1,
                        "status": "archived",
                        "supersedes_association_id": None,
                    },
                    {
                        "id": replacement_id,
                        "binding_role_id": 2,
                        "status": "active",
                        "supersedes_association_id": original_id,
                    },
                ],
            },
        )

    def test_association_status_requires_complete_archive_evidence(self):
        associations = self.store.link_layer_table_names()[
            "time_series_catalog_associations"
        ]
        insert = f"""
            INSERT INTO {associations} (
                signal_id, time_series_set_id, linkable_object_id,
                binding_role_id, compatibility_rule_id, status,
                created_at, created_by, archived_at, archived_by,
                archived_reason_code
            ) VALUES (?, ?, ?, ?, ?, ?, '2026-01-01T00:00:00', 'test',
                      ?, ?, ?)
        """
        base = (self.signal_id, self.receipt["set_id"], self.object["id"])
        outcomes = {
            "archived_without_evidence": attempt(
                self.store.connection,
                insert,
                (*base, 1, 1, "archived", None, None, None),
            ),
            "active_with_archive_evidence": attempt(
                self.store.connection,
                insert,
                (
                    *base,
                    2,
                    2,
                    "active",
                    "2026-01-02T00:00:00",
                    "test",
                    "retired",
                ),
            ),
            "complete_archived": self._insert(
                role_id=1, rule_id=1, status="archived"
            ),
            "plain_active": self._insert(role_id=2, rule_id=2),
        }

        self.assertEqual(
            outcomes,
            {
                "archived_without_evidence": "refused",
                "active_with_archive_evidence": "refused",
                "complete_archived": "accepted",
                "plain_active": "accepted",
            },
        )


class AssociationCatalogBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.store = AnalystStore("sqlite:///:memory:")
        self.project = self.store.create_project(name="Cuenca Norte")
        self.object = self.store.ensure_global_signal_slot(
            project_id=self.project["id"]
        )

    def tearDown(self):
        self.store.close()

    def test_an_object_specific_signal_cannot_enter_a_catalog_association(self):
        canonical = self.store.canonical_table_names()
        now = "2026-01-01T00:00:00"
        signal_id = 100_001
        set_id = int(
            self.store.connection.execute(
                f"""
                INSERT INTO {canonical['time_series_sets']} (
                    owner_project_id, name, version_number, version_label,
                    visibility_scope, series_kind, owner_linkable_object_id,
                    object_series_key, object_specific_signal_id, status,
                    created_at, updated_at, created_by, updated_by
                ) VALUES (?, 'local_price', 1, 'object', 'project',
                          'object_specific', ?, 'local_price', ?, 'draft',
                          ?, ?, 'test', 'test')
                RETURNING id
                """,
                (self.project["id"], self.object["id"], signal_id, now, now),
            ).fetchone()["id"]
        )
        self.store.connection.execute(
            f"""
            INSERT INTO {canonical['time_series_signals']} (
                id, time_series_set_id, series_kind, series_key, display_name,
                created_at, created_by
            ) VALUES (?, ?, 'object_specific', 'local_price', 'Precio local',
                      ?, 'test')
            """,
            (signal_id, set_id, now),
        )
        associations = self.store.link_layer_table_names()[
            "time_series_catalog_associations"
        ]
        insert = f"""
            INSERT INTO {associations} (
                signal_id, time_series_set_id, series_kind,
                linkable_object_id, binding_role_id, compatibility_rule_id,
                created_at, created_by
            ) VALUES (?, ?, ?, ?, 1, 1, ?, 'test')
        """

        outcomes = {
            "pretend_catalog": attempt(
                self.store.connection,
                insert,
                (signal_id, set_id, "catalog", self.object["id"], now),
            ),
            "declare_object_specific": attempt(
                self.store.connection,
                insert,
                (signal_id, set_id, "object_specific", self.object["id"], now),
            ),
        }

        self.assertEqual(
            outcomes,
            {
                "pretend_catalog": "refused",
                "declare_object_specific": "refused",
            },
        )


class BindingCardinalityTests(unittest.TestCase):
    def setUp(self):
        self.store = AnalystStore("sqlite:///:memory:")
        self.project = self.store.create_project(name="Cuenca Norte")
        self.object = self.store.ensure_global_signal_slot(
            project_id=self.project["id"]
        )
        self.receipt = self.store.publish_canonical_set_revision(
            project_id=self.project["id"],
            name="Precios ejecutables 2026",
            data_class_key="real",
            timezone="UTC",
            signals=[
                {
                    "series_key": "energy_price",
                    "display_name": "Precio de energia",
                    "semantic_type_key": "energy_price",
                    "unit_key": "usd_per_mwh",
                    "signal_role": "input",
                    "aggregation": "mean",
                }
            ],
            periods=[
                {
                    "timestamp_start": "2026-01-01T00:00:00",
                    "timestamp_end": "2026-01-01T01:00:00",
                    "duration_hours": 1.0,
                }
            ],
            values={"energy_price": [75.0]},
            actor="internal_analyst",
        )
        canonical = self.store.canonical_table_names()
        self.signal_id = int(
            self.store.connection.execute(
                f"SELECT id FROM {canonical['time_series_signals']} "
                "WHERE time_series_set_id = ?",
                (self.receipt["set_id"],),
            ).fetchone()["id"]
        )
        scenario = self.store.create_scenario(
            project_id=self.project["id"], name="Operacion"
        )
        case = self.store.get_or_create_case_for_scenario(scenario["id"])
        self.variant = self.store.get_or_create_default_input_variant(case["id"])

    def tearDown(self):
        self.store.close()

    def _insert(self, *, role_id, rule_id, status="active"):
        bindings = self.store.link_layer_table_names()["case_time_series_bindings"]
        superseded = status == "superseded"
        removed = status == "removed"
        return attempt(
            self.store.connection,
            f"""
            INSERT INTO {bindings} (
                case_input_variant_id, linkable_object_id, binding_role_id,
                signal_id, time_series_set_id, set_revision_id,
                bound_content_hash, source_kind, compatibility_rule_id,
                status, change_reason_code, superseded_at, superseded_by,
                removed_at, removed_by, created_at, updated_at,
                created_by, updated_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'catalog', ?, ?, 'selected',
                      ?, ?, ?, ?,
                      '2026-01-01T00:00:00', '2026-01-01T00:00:00',
                      'test', 'test')
            """,
            (
                self.variant["id"],
                self.object["id"],
                role_id,
                self.signal_id,
                self.receipt["set_id"],
                self.receipt["revision_id"],
                self.receipt["content_hash"],
                rule_id,
                status,
                "2026-01-02T00:00:00" if superseded else None,
                "test" if superseded else None,
                "2026-01-02T00:00:00" if removed else None,
                "test" if removed else None,
            ),
        )

    def test_only_one_active_binding_exists_per_variant_object_and_role(self):
        outcomes = {
            "first": self._insert(role_id=1, rule_id=1),
            "duplicate_active": self._insert(role_id=1, rule_id=1),
            "superseded_history": self._insert(
                role_id=1, rule_id=1, status="superseded"
            ),
            "same_object_in_another_role": self._insert(role_id=2, rule_id=2),
        }

        self.assertEqual(
            outcomes,
            {
                "first": "accepted",
                "duplicate_active": "refused",
                "superseded_history": "accepted",
                "same_object_in_another_role": "accepted",
            },
        )

    def test_replacing_a_binding_inserts_history_instead_of_retargeting_it(self):
        self.assertEqual(self._insert(role_id=1, rule_id=1), "accepted")
        bindings = self.store.link_layer_table_names()["case_time_series_bindings"]
        original_id = int(
            self.store.connection.execute(
                f"SELECT id FROM {bindings} WHERE status = 'active'"
            ).fetchone()["id"]
        )

        identity_edit = guard_attempt(
            self.store.connection,
            f"UPDATE {bindings} SET binding_role_id = 2 WHERE id = ?",
            (original_id,),
        )
        self.store.connection.execute(
            f"""
            UPDATE {bindings}
            SET status = 'superseded', lifecycle_revision = 2,
                superseded_at = '2026-01-02T00:00:00',
                superseded_by = 'test', updated_at = '2026-01-02T00:00:00',
                updated_by = 'test'
            WHERE id = ?
            """,
            (original_id,),
        )
        replacement_id = int(
            self.store.connection.execute(
                f"""
                INSERT INTO {bindings} (
                    case_input_variant_id, linkable_object_id, binding_role_id,
                    signal_id, time_series_set_id, set_revision_id,
                    bound_content_hash, source_kind, compatibility_rule_id,
                    supersedes_binding_id, change_reason_code,
                    created_at, updated_at, created_by, updated_by
                ) VALUES (?, ?, 1, ?, ?, ?, ?, 'catalog', 1, ?, 'replaced',
                          '2026-01-02T00:00:00', '2026-01-02T00:00:00',
                          'test', 'test')
                RETURNING id
                """,
                (
                    self.variant["id"],
                    self.object["id"],
                    self.signal_id,
                    self.receipt["set_id"],
                    self.receipt["revision_id"],
                    self.receipt["content_hash"],
                    original_id,
                ),
            ).fetchone()["id"]
        )
        delete_history = guard_attempt(
            self.store.connection,
            f"DELETE FROM {bindings} WHERE id = ?",
            (original_id,),
        )
        history = [
            dict(row)
            for row in self.store.connection.execute(
                f"""
                SELECT id, binding_role_id, set_revision_id,
                       bound_content_hash, status, supersedes_binding_id
                FROM {bindings}
                ORDER BY id
                """
            ).fetchall()
        ]

        self.assertEqual(
            {
                "identity_edit": identity_edit,
                "delete_history": delete_history,
                "history": history,
            },
            {
                "identity_edit": LINK_HISTORY_IMMUTABLE,
                "delete_history": LINK_HISTORY_IMMUTABLE,
                "history": [
                    {
                        "id": original_id,
                        "binding_role_id": 1,
                        "set_revision_id": self.receipt["revision_id"],
                        "bound_content_hash": self.receipt["content_hash"],
                        "status": "superseded",
                        "supersedes_binding_id": None,
                    },
                    {
                        "id": replacement_id,
                        "binding_role_id": 1,
                        "set_revision_id": self.receipt["revision_id"],
                        "bound_content_hash": self.receipt["content_hash"],
                        "status": "active",
                        "supersedes_binding_id": original_id,
                    },
                ],
            },
        )

    def test_a_binding_pins_an_exact_revision_and_hash(self):
        self.assertEqual(self._insert(role_id=1, rule_id=1), "accepted")
        bindings = self.store.link_layer_table_names()["case_time_series_bindings"]
        wrong_hash = attempt(
            self.store.connection,
            f"""
            INSERT INTO {bindings} (
                case_input_variant_id, linkable_object_id, binding_role_id,
                signal_id, time_series_set_id, set_revision_id,
                bound_content_hash, source_kind, compatibility_rule_id,
                change_reason_code, created_at, updated_at,
                created_by, updated_by
            ) VALUES (?, ?, 2, ?, ?, ?, 'not-the-revision-hash', 'catalog', 2,
                      'selected', '2026-01-01T00:00:00',
                      '2026-01-01T00:00:00', 'test', 'test')
            """,
            (
                self.variant["id"],
                self.object["id"],
                self.signal_id,
                self.receipt["set_id"],
                self.receipt["revision_id"],
            ),
        )
        next_receipt = self.store.publish_canonical_set_revision(
            project_id=self.project["id"],
            set_id=self.receipt["set_id"],
            name="Precios ejecutables 2026",
            data_class_key="real",
            timezone="UTC",
            signals=[
                {
                    "series_key": "energy_price",
                    "display_name": "Precio de energia",
                    "semantic_type_key": "energy_price",
                    "unit_key": "usd_per_mwh",
                    "signal_role": "input",
                    "aggregation": "mean",
                }
            ],
            periods=[
                {
                    "timestamp_start": "2026-01-01T00:00:00",
                    "timestamp_end": "2026-01-01T01:00:00",
                    "duration_hours": 1.0,
                }
            ],
            values={"energy_price": [99.0]},
            actor="internal_analyst",
        )
        bound = dict(
            self.store.connection.execute(
                f"""
                SELECT set_revision_id, bound_content_hash
                FROM {bindings}
                WHERE status = 'active'
                """
            ).fetchone()
        )
        columns = {
            row["name"]
            for row in self.store.connection.execute(
                f"PRAGMA table_info({bindings})"
            ).fetchall()
        }

        self.assertEqual(
            {
                "wrong_hash": wrong_hash,
                "pinned_revision_id": bound["set_revision_id"],
                "pinned_hash": bound["bound_content_hash"],
                "new_current_revision_id": next_receipt["revision_id"],
                "has_current_pointer": "current_revision_id" in columns,
            },
            {
                "wrong_hash": "refused",
                "pinned_revision_id": self.receipt["revision_id"],
                "pinned_hash": self.receipt["content_hash"],
                "new_current_revision_id": next_receipt["revision_id"],
                "has_current_pointer": False,
            },
        )

    def test_binding_status_requires_exclusive_lifecycle_evidence(self):
        bindings = self.store.link_layer_table_names()["case_time_series_bindings"]
        insert = f"""
            INSERT INTO {bindings} (
                case_input_variant_id, linkable_object_id, binding_role_id,
                signal_id, time_series_set_id, set_revision_id,
                bound_content_hash, source_kind, compatibility_rule_id,
                status, change_reason_code, superseded_at, superseded_by,
                removed_at, removed_by, created_at, updated_at,
                created_by, updated_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'catalog', ?, ?, 'selected',
                      ?, ?, ?, ?, '2026-01-01T00:00:00',
                      '2026-01-02T00:00:00', 'test', 'test')
        """
        base = (
            self.variant["id"],
            self.object["id"],
            self.signal_id,
            self.receipt["set_id"],
            self.receipt["revision_id"],
            self.receipt["content_hash"],
        )

        def direct(role_id, rule_id, status, superseded_at=None, superseded_by=None,
                   removed_at=None, removed_by=None):
            return attempt(
                self.store.connection,
                insert,
                (
                    base[0], base[1], role_id, *base[2:], rule_id, status,
                    superseded_at, superseded_by, removed_at, removed_by,
                ),
            )

        outcomes = {
            "superseded_without_evidence": direct(1, 1, "superseded"),
            "removed_without_evidence": direct(1, 1, "removed"),
            "active_with_supersede_evidence": direct(
                2,
                2,
                "active",
                "2026-01-02T00:00:00",
                "test",
            ),
            "complete_superseded": self._insert(
                role_id=1, rule_id=1, status="superseded"
            ),
            "complete_removed": self._insert(
                role_id=1, rule_id=1, status="removed"
            ),
            "plain_active": self._insert(role_id=2, rule_id=2),
        }

        self.assertEqual(
            outcomes,
            {
                "superseded_without_evidence": "refused",
                "removed_without_evidence": "refused",
                "active_with_supersede_evidence": "refused",
                "complete_superseded": "accepted",
                "complete_removed": "accepted",
                "plain_active": "accepted",
            },
        )

    def test_parent_deletes_cannot_orphan_an_active_binding(self):
        self.assertEqual(self._insert(role_id=1, rule_id=1), "accepted")
        canonical = self.store.canonical_table_names()
        linkable = self.store.linkable_object_table_names()
        bindings = self.store.link_layer_table_names()["case_time_series_bindings"]

        outcomes = {
            "variant": attempt(
                self.store.connection,
                "DELETE FROM case_input_variants WHERE id = ?",
                (self.variant["id"],),
            ),
            "object": attempt(
                self.store.connection,
                f"DELETE FROM {linkable['linkable_objects']} WHERE id = ?",
                (self.object["id"],),
            ),
            "signal": attempt(
                self.store.connection,
                f"DELETE FROM {canonical['time_series_signals']} WHERE id = ?",
                (self.signal_id,),
            ),
            "revision": attempt(
                self.store.connection,
                f"DELETE FROM {canonical['time_series_set_revisions']} WHERE id = ?",
                (self.receipt["revision_id"],),
            ),
            "set": attempt(
                self.store.connection,
                f"DELETE FROM {canonical['time_series_sets']} WHERE id = ?",
                (self.receipt["set_id"],),
            ),
        }
        orphan_count = int(
            self.store.connection.execute(
                f"""
                SELECT COUNT(*) AS total
                FROM {bindings} AS binding
                LEFT JOIN case_input_variants AS variant
                  ON variant.id = binding.case_input_variant_id
                LEFT JOIN {linkable['linkable_objects']} AS object
                  ON object.id = binding.linkable_object_id
                LEFT JOIN {canonical['time_series_signals']} AS signal
                  ON signal.id = binding.signal_id
                 AND signal.time_series_set_id = binding.time_series_set_id
                LEFT JOIN {canonical['time_series_set_revisions']} AS revision
                  ON revision.id = binding.set_revision_id
                 AND revision.time_series_set_id = binding.time_series_set_id
                 AND revision.content_hash = binding.bound_content_hash
                LEFT JOIN {canonical['time_series_revision_signals']} AS member
                  ON member.set_revision_id = binding.set_revision_id
                 AND member.signal_id = binding.signal_id
                WHERE variant.id IS NULL OR object.id IS NULL OR signal.id IS NULL
                   OR revision.id IS NULL OR member.signal_id IS NULL
                """
            ).fetchone()["total"]
        )

        self.assertEqual(
            {"delete_outcomes": outcomes, "orphan_count": orphan_count},
            {
                "delete_outcomes": {
                    "variant": "refused",
                    "object": "refused",
                    "signal": "refused",
                    "revision": "refused",
                    "set": "refused",
                },
                "orphan_count": 0,
            },
        )


class LedgerImmutabilityTests(unittest.TestCase):
    def setUp(self):
        self.store = AnalystStore("sqlite:///:memory:")
        self.project = self.store.create_project(name="Cuenca Norte")
        self.object = self.store.ensure_global_signal_slot(
            project_id=self.project["id"]
        )
        self.receipt = self.store.publish_canonical_set_revision(
            project_id=self.project["id"],
            name="Precios auditados 2026",
            data_class_key="real",
            timezone="UTC",
            signals=[
                {
                    "series_key": "energy_price",
                    "display_name": "Precio de energia",
                    "semantic_type_key": "energy_price",
                    "unit_key": "usd_per_mwh",
                    "signal_role": "input",
                    "aggregation": "mean",
                }
            ],
            periods=[
                {
                    "timestamp_start": "2026-01-01T00:00:00",
                    "timestamp_end": "2026-01-01T01:00:00",
                    "duration_hours": 1.0,
                }
            ],
            values={"energy_price": [75.0]},
            actor="internal_analyst",
        )
        canonical = self.store.canonical_table_names()
        signal_id = int(
            self.store.connection.execute(
                f"SELECT id FROM {canonical['time_series_signals']} "
                "WHERE time_series_set_id = ?",
                (self.receipt["set_id"],),
            ).fetchone()["id"]
        )
        tables = self.store.link_layer_table_names()
        self.tables = tables
        self.association_id = int(
            self.store.connection.execute(
                f"""
                INSERT INTO {tables['time_series_catalog_associations']} (
                    signal_id, time_series_set_id, linkable_object_id,
                    binding_role_id, compatibility_rule_id,
                    created_at, created_by
                ) VALUES (?, ?, ?, 1, 1, '2026-01-01T00:00:00', 'test')
                RETURNING id
                """,
                (signal_id, self.receipt["set_id"], self.object["id"]),
            ).fetchone()["id"]
        )
        self.user_id = int(
            self.store.connection.execute(
                """
                INSERT INTO users (
                    email, display_name, role, password_hash, is_active,
                    created_at, updated_at, created_by
                ) VALUES (
                    'auditor@example.com', 'Auditor', 'admin', 'not-used', 1,
                    '2026-01-01T00:00:00', '2026-01-01T00:00:00', 'test'
                ) RETURNING id
                """
            ).fetchone()["id"]
        )

    def tearDown(self):
        self.store.close()

    def _insert_ledgers(self):
        validation_id = int(
            self.store.connection.execute(
                f"""
                INSERT INTO {self.tables['time_series_link_validations']} (
                    catalog_association_id, subject_lifecycle_revision,
                    validation_mode, validated_set_revision_id,
                    observed_current_revision_id, compatibility_rule_id,
                    compatibility_fingerprint, object_scope_fingerprint,
                    validated_at, validated_by, reason_code
                ) VALUES (?, 1, 'association_current', ?, ?, 1,
                          'compat-v1', 'scope-v1',
                          '2026-01-01T00:00:00', 'test', 'created')
                RETURNING id
                """,
                (
                    self.association_id,
                    self.receipt["revision_id"],
                    self.receipt["revision_id"],
                ),
            ).fetchone()["id"]
        )
        event_id = int(
            self.store.connection.execute(
                f"""
                INSERT INTO {self.tables['time_series_link_events']} (
                    catalog_association_id, event_type, actor_user_id,
                    actor_identity_snapshot, actor_role_snapshot, reason_code,
                    request_id, occurred_at
                ) VALUES (?, 'created', ?, 'auditor@example.com', 'admin',
                          'created', 'request-link-1', '2026-01-01T00:00:00')
                RETURNING id
                """,
                (self.association_id, self.user_id),
            ).fetchone()["id"]
        )
        scope_id = int(
            self.store.connection.execute(
                f"""
                INSERT INTO {self.tables['time_series_scope_events']} (
                    time_series_set_id, event_type, to_scope, scope_revision,
                    owner_project_id, observed_set_revision_id,
                    observed_content_hash, actor_user_id,
                    actor_identity_snapshot, actor_role_snapshot, reason_code,
                    reason_text, request_id, idempotency_key, occurred_at
                ) VALUES (?, 'created_project', 'project', 1, ?, ?, ?, ?,
                          'auditor@example.com', 'admin', 'created',
                          'catalog created', 'request-scope-1', 'scope-1',
                          '2026-01-01T00:00:00')
                RETURNING id
                """,
                (
                    self.receipt["set_id"],
                    self.project["id"],
                    self.receipt["revision_id"],
                    self.receipt["content_hash"],
                    self.user_id,
                ),
            ).fetchone()["id"]
        )
        return {
            "time_series_link_validations": validation_id,
            "time_series_link_events": event_id,
            "time_series_scope_events": scope_id,
        }

    def test_each_ledger_accepts_insert_only_and_refuses_update_and_delete(self):
        ledger_rows = self._insert_ledgers()

        outcomes = {}
        for logical_name, row_id in ledger_rows.items():
            physical_name = self.tables[logical_name]
            outcomes[f"{logical_name}:update"] = guard_attempt(
                self.store.connection,
                f"UPDATE {physical_name} SET reason_code = 'rewritten' WHERE id = ?",
                (row_id,),
            )
            outcomes[f"{logical_name}:delete"] = guard_attempt(
                self.store.connection,
                f"DELETE FROM {physical_name} WHERE id = ?",
                (row_id,),
            )

        self.assertEqual(
            outcomes,
            {
                f"{logical_name}:{operation}": LINK_LEDGER_IMMUTABLE
                for logical_name in ledger_rows
                for operation in ("update", "delete")
            },
        )

    def test_parent_deletes_cannot_orphan_associations_or_ledgers(self):
        ledger_rows = self._insert_ledgers()
        canonical = self.store.canonical_table_names()
        linkable = self.store.linkable_object_table_names()
        outcomes = {
            "object": attempt(
                self.store.connection,
                f"DELETE FROM {linkable['linkable_objects']} WHERE id = ?",
                (self.object["id"],),
            ),
            "revision": attempt(
                self.store.connection,
                f"DELETE FROM {canonical['time_series_set_revisions']} WHERE id = ?",
                (self.receipt["revision_id"],),
            ),
            "set": attempt(
                self.store.connection,
                f"DELETE FROM {canonical['time_series_sets']} WHERE id = ?",
                (self.receipt["set_id"],),
            ),
            "user": attempt(
                self.store.connection,
                "DELETE FROM users WHERE id = ?",
                (self.user_id,),
            ),
            "association": guard_attempt(
                self.store.connection,
                f"DELETE FROM {self.tables['time_series_catalog_associations']} "
                "WHERE id = ?",
                (self.association_id,),
            ),
        }
        orphan_counts = {
            "associations": int(
                self.store.connection.execute(
                    f"""
                    SELECT COUNT(*) AS total
                    FROM {self.tables['time_series_catalog_associations']} AS a
                    LEFT JOIN {linkable['linkable_objects']} AS o
                      ON o.id = a.linkable_object_id
                    LEFT JOIN {canonical['time_series_signals']} AS s
                      ON s.id = a.signal_id
                     AND s.time_series_set_id = a.time_series_set_id
                    WHERE o.id IS NULL OR s.id IS NULL
                    """
                ).fetchone()["total"]
            ),
            "validations": int(
                self.store.connection.execute(
                    f"""
                    SELECT COUNT(*) AS total
                    FROM {self.tables['time_series_link_validations']} AS v
                    LEFT JOIN {self.tables['time_series_catalog_associations']} AS a
                      ON a.id = v.catalog_association_id
                    LEFT JOIN {canonical['time_series_set_revisions']} AS vr
                      ON vr.id = v.validated_set_revision_id
                    LEFT JOIN {canonical['time_series_set_revisions']} AS cr
                      ON cr.id = v.observed_current_revision_id
                    WHERE a.id IS NULL OR vr.id IS NULL OR cr.id IS NULL
                    """
                ).fetchone()["total"]
            ),
            "events": int(
                self.store.connection.execute(
                    f"""
                    SELECT COUNT(*) AS total
                    FROM {self.tables['time_series_link_events']} AS e
                    LEFT JOIN {self.tables['time_series_catalog_associations']} AS a
                      ON a.id = e.catalog_association_id
                    WHERE a.id IS NULL
                    """
                ).fetchone()["total"]
            ),
        }

        self.assertEqual(
            {
                "delete_outcomes": outcomes,
                "orphan_counts": orphan_counts,
                "ledger_rows": sorted(ledger_rows),
            },
            {
                "delete_outcomes": {
                    "object": "refused",
                    "revision": "refused",
                    "set": "refused",
                    "user": "refused",
                    "association": LINK_HISTORY_IMMUTABLE,
                },
                "orphan_counts": {
                    "associations": 0,
                    "validations": 0,
                    "events": 0,
                },
                "ledger_rows": [
                    "time_series_link_events",
                    "time_series_link_validations",
                    "time_series_scope_events",
                ],
            },
        )


@unittest.skipUnless(
    POSTGRES_TEST_DATABASE_URL,
    "set POSTGRES_TEST_DATABASE_URL to run the PostgreSQL contract tests",
)
class PostgresLinkLayerTests(unittest.TestCase):
    """The SQLite structural contract repeated on development PostgreSQL."""

    def setUp(self):
        self.store = AnalystStore(POSTGRES_TEST_DATABASE_URL)
        self.rollback = self.store.connection._connection.transaction(  # noqa: SLF001
            force_rollback=True
        )
        self.rollback.__enter__()
        self.suffix = uuid.uuid4().hex[:10]
        self.project = self.store.create_project(name=f"TS7-004 {self.suffix}")
        self.object = self.store.ensure_global_signal_slot(
            project_id=self.project["id"]
        )
        self.receipt = self.store.publish_canonical_set_revision(
            project_id=self.project["id"],
            name=f"Precios {self.suffix}",
            data_class_key="real",
            timezone="UTC",
            signals=[
                {
                    "series_key": "energy_price",
                    "display_name": "Precio de energia",
                    "semantic_type_key": "energy_price",
                    "unit_key": "usd_per_mwh",
                    "signal_role": "input",
                    "aggregation": "mean",
                }
            ],
            periods=[
                {
                    "timestamp_start": "2026-01-01T00:00:00",
                    "timestamp_end": "2026-01-01T01:00:00",
                    "duration_hours": 1.0,
                }
            ],
            values={"energy_price": [75.0]},
            actor="internal_analyst",
        )
        canonical = self.store.canonical_table_names()
        self.signal_id = int(
            self.store.connection.execute(
                f"SELECT id FROM {canonical['time_series_signals']} "
                "WHERE time_series_set_id = ?",
                (self.receipt["set_id"],),
            ).fetchone()["id"]
        )
        scenario = self.store.create_scenario(
            project_id=self.project["id"], name=f"Operacion {self.suffix}"
        )
        case = self.store.get_or_create_case_for_scenario(scenario["id"])
        self.variant = self.store.get_or_create_default_input_variant(case["id"])
        self.user_id = int(
            self.store.connection.execute(
                """
                INSERT INTO users (
                    email, display_name, role, password_hash, is_active,
                    created_at, updated_at, created_by
                ) VALUES (?, 'Auditor', 'admin', 'not-used', 1,
                          '2026-01-01T00:00:00', '2026-01-01T00:00:00', 'test')
                RETURNING id
                """,
                (f"auditor-{self.suffix}@example.com",),
            ).fetchone()["id"]
        )

    def tearDown(self):
        try:
            self.rollback.__exit__(None, None, None)
        finally:
            self.store.close()

    def _insert_association(self, *, role_id=1, rule_id=1, status="active"):
        associations = self.store.link_layer_table_names()[
            "time_series_catalog_associations"
        ]
        archived = status == "archived"
        return postgres_guard_attempt(
            self.store.connection,
            f"""
            INSERT INTO {associations} (
                signal_id, time_series_set_id, linkable_object_id,
                binding_role_id, compatibility_rule_id, status,
                created_at, created_by, archived_at, archived_by,
                archived_reason_code
            ) VALUES (?, ?, ?, ?, ?, ?, '2026-01-01T00:00:00', 'test',
                      ?, ?, ?)
            """,
            (
                self.signal_id,
                self.receipt["set_id"],
                self.object["id"],
                role_id,
                rule_id,
                status,
                "2026-01-02T00:00:00" if archived else None,
                "test" if archived else None,
                "retired" if archived else None,
            ),
        )

    def _insert_binding(self, *, role_id=1, rule_id=1, content_hash=None):
        bindings = self.store.link_layer_table_names()["case_time_series_bindings"]
        return postgres_guard_attempt(
            self.store.connection,
            f"""
            INSERT INTO {bindings} (
                case_input_variant_id, linkable_object_id, binding_role_id,
                signal_id, time_series_set_id, set_revision_id,
                bound_content_hash, source_kind, compatibility_rule_id,
                change_reason_code, created_at, updated_at,
                created_by, updated_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'catalog', ?, 'selected',
                      '2026-01-01T00:00:00', '2026-01-01T00:00:00',
                      'test', 'test')
            """,
            (
                self.variant["id"],
                self.object["id"],
                role_id,
                self.signal_id,
                self.receipt["set_id"],
                self.receipt["revision_id"],
                content_hash or self.receipt["content_hash"],
                rule_id,
            ),
        )

    def test_postgres_lands_the_same_canonical_tables_and_variant_counter(self):
        tables = self.store.link_layer_table_names()
        landed = {
            str(row["table_name"])
            for row in self.store.connection.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'ts_next'
                  AND table_name IN (
                    'time_series_catalog_associations',
                    'case_time_series_bindings',
                    'time_series_link_validations',
                    'time_series_link_events',
                    'time_series_scope_events'
                  )
                """
            ).fetchall()
        }
        counter = self.store.connection.execute(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'case_input_variants'
              AND column_name = 'bindings_revision'
            """
        ).fetchone()

        self.assertEqual(
            {
                "physical_names": tables,
                "landed": sorted(landed),
                "bindings_revision": counter is not None,
            },
            {
                "physical_names": {
                    "case_time_series_bindings": "ts_next.case_time_series_bindings",
                    "time_series_catalog_associations": (
                        "ts_next.time_series_catalog_associations"
                    ),
                    "time_series_link_events": "ts_next.time_series_link_events",
                    "time_series_link_validations": (
                        "ts_next.time_series_link_validations"
                    ),
                    "time_series_scope_events": "ts_next.time_series_scope_events",
                },
                "landed": [
                    "case_time_series_bindings",
                    "time_series_catalog_associations",
                    "time_series_link_events",
                    "time_series_link_validations",
                    "time_series_scope_events",
                ],
                "bindings_revision": True,
            },
        )

    def test_postgres_enforces_both_cardinalities_hash_and_append_only_history(self):
        self.assertEqual(self._insert_association(), "accepted")
        self.assertEqual(self._insert_binding(), "accepted")
        tables = self.store.link_layer_table_names()
        canonical = self.store.canonical_table_names()
        association_id = int(
            self.store.connection.execute(
                f"SELECT id FROM {tables['time_series_catalog_associations']} "
                "WHERE signal_id = ? AND status = 'active'",
                (self.signal_id,),
            ).fetchone()["id"]
        )
        binding_id = int(
            self.store.connection.execute(
                f"SELECT id FROM {tables['case_time_series_bindings']} "
                "WHERE case_input_variant_id = ? AND status = 'active'",
                (self.variant["id"],),
            ).fetchone()["id"]
        )
        local_signal_id = int(
            self.store.connection.execute(
                """
                SELECT nextval(
                    pg_get_serial_sequence('ts_next.time_series_signals', 'id')
                ) AS id
                """
            ).fetchone()["id"]
        )
        local_key = f"local_price_{self.suffix}"
        local_set_id = int(
            self.store.connection.execute(
                f"""
                INSERT INTO {canonical['time_series_sets']} (
                    owner_project_id, name, version_number, version_label,
                    visibility_scope, series_kind, owner_linkable_object_id,
                    object_series_key, object_specific_signal_id, status,
                    created_at, updated_at, created_by, updated_by
                ) VALUES (?, ?, 1, 'object', 'project', 'object_specific', ?, ?, ?,
                          'draft', '2026-01-01T00:00:00',
                          '2026-01-01T00:00:00', 'test', 'test')
                RETURNING id
                """,
                (
                    self.project["id"],
                    local_key,
                    self.object["id"],
                    local_key,
                    local_signal_id,
                ),
            ).fetchone()["id"]
        )
        self.store.connection.execute(
            f"""
            INSERT INTO {canonical['time_series_signals']} (
                id, time_series_set_id, series_kind, series_key, display_name,
                created_at, created_by
            ) VALUES (?, ?, 'object_specific', ?, 'Precio local',
                      '2026-01-01T00:00:00', 'test')
            """,
            (local_signal_id, local_set_id, local_key),
        )

        outcomes = {
            "association_duplicate": self._insert_association(),
            "association_archived": self._insert_association(status="archived"),
            "association_other_role": self._insert_association(role_id=2, rule_id=2),
            "binding_duplicate": self._insert_binding(),
            "binding_other_role_wrong_hash": self._insert_binding(
                role_id=2, rule_id=2, content_hash="not-the-revision-hash"
            ),
            "superseded_without_evidence": postgres_guard_attempt(
                self.store.connection,
                f"""
                INSERT INTO {tables['case_time_series_bindings']} (
                    case_input_variant_id, linkable_object_id, binding_role_id,
                    signal_id, time_series_set_id, set_revision_id,
                    bound_content_hash, source_kind, compatibility_rule_id,
                    status, change_reason_code, created_at, updated_at,
                    created_by, updated_by
                ) VALUES (?, ?, 2, ?, ?, ?, ?, 'catalog', 2, 'superseded',
                          'selected', '2026-01-01T00:00:00',
                          '2026-01-01T00:00:00', 'test', 'test')
                """,
                (
                    self.variant["id"],
                    self.object["id"],
                    self.signal_id,
                    self.receipt["set_id"],
                    self.receipt["revision_id"],
                    self.receipt["content_hash"],
                ),
            ),
            "object_specific_association": postgres_guard_attempt(
                self.store.connection,
                f"""
                INSERT INTO {tables['time_series_catalog_associations']} (
                    signal_id, time_series_set_id, linkable_object_id,
                    binding_role_id, compatibility_rule_id,
                    created_at, created_by
                ) VALUES (?, ?, ?, 1, 1, '2026-01-01T00:00:00', 'test')
                """,
                (local_signal_id, local_set_id, self.object["id"]),
            ),
            "archived_without_evidence": postgres_guard_attempt(
                self.store.connection,
                f"""
                INSERT INTO {tables['time_series_catalog_associations']} (
                    signal_id, time_series_set_id, linkable_object_id,
                    binding_role_id, compatibility_rule_id, status,
                    created_at, created_by
                ) VALUES (?, ?, ?, 1, 1, 'archived',
                          '2026-01-01T00:00:00', 'test')
                """,
                (self.signal_id, self.receipt["set_id"], self.object["id"]),
            ),
            "association_identity_edit": postgres_guard_attempt(
                self.store.connection,
                f"UPDATE {tables['time_series_catalog_associations']} "
                "SET binding_role_id = 2 WHERE id = ?",
                (association_id,),
            ),
            "association_delete": postgres_guard_attempt(
                self.store.connection,
                f"DELETE FROM {tables['time_series_catalog_associations']} WHERE id = ?",
                (association_id,),
            ),
            "binding_identity_edit": postgres_guard_attempt(
                self.store.connection,
                f"UPDATE {tables['case_time_series_bindings']} "
                "SET binding_role_id = 2 WHERE id = ?",
                (binding_id,),
            ),
            "binding_delete": postgres_guard_attempt(
                self.store.connection,
                f"DELETE FROM {tables['case_time_series_bindings']} WHERE id = ?",
                (binding_id,),
            ),
        }

        self.assertEqual(
            outcomes,
            {
                "association_duplicate": "refused",
                "association_archived": "accepted",
                "association_other_role": "accepted",
                "binding_duplicate": "refused",
                "binding_other_role_wrong_hash": "refused",
                "superseded_without_evidence": "refused",
                "object_specific_association": "refused",
                "archived_without_evidence": "refused",
                "association_identity_edit": LINK_HISTORY_IMMUTABLE,
                "association_delete": LINK_HISTORY_IMMUTABLE,
                "binding_identity_edit": LINK_HISTORY_IMMUTABLE,
                "binding_delete": LINK_HISTORY_IMMUTABLE,
            },
        )

    def test_postgres_ledgers_are_insert_only_and_parent_deletes_are_restricted(self):
        associations = self.store.link_layer_table_names()[
            "time_series_catalog_associations"
        ]
        association_id = int(
            self.store.connection.execute(
                f"""
                INSERT INTO {associations} (
                    signal_id, time_series_set_id, linkable_object_id,
                    binding_role_id, compatibility_rule_id,
                    created_at, created_by
                ) VALUES (?, ?, ?, 1, 1, '2026-01-01T00:00:00', 'test')
                RETURNING id
                """,
                (self.signal_id, self.receipt["set_id"], self.object["id"]),
            ).fetchone()["id"]
        )
        tables = self.store.link_layer_table_names()
        validation_id = int(
            self.store.connection.execute(
                f"""
                INSERT INTO {tables['time_series_link_validations']} (
                    catalog_association_id, subject_lifecycle_revision,
                    validation_mode, validated_set_revision_id,
                    observed_current_revision_id, compatibility_rule_id,
                    compatibility_fingerprint, object_scope_fingerprint,
                    validated_at, validated_by, reason_code
                ) VALUES (?, 1, 'association_current', ?, ?, 1,
                          'compat-v1', 'scope-v1',
                          '2026-01-01T00:00:00', 'test', 'created')
                RETURNING id
                """,
                (
                    association_id,
                    self.receipt["revision_id"],
                    self.receipt["revision_id"],
                ),
            ).fetchone()["id"]
        )
        event_id = int(
            self.store.connection.execute(
                f"""
                INSERT INTO {tables['time_series_link_events']} (
                    catalog_association_id, event_type, actor_user_id,
                    actor_identity_snapshot, actor_role_snapshot, reason_code,
                    request_id, occurred_at
                ) VALUES (?, 'created', ?, ?, 'admin', 'created', ?,
                          '2026-01-01T00:00:00')
                RETURNING id
                """,
                (
                    association_id,
                    self.user_id,
                    f"auditor-{self.suffix}@example.com",
                    f"request-link-{self.suffix}",
                ),
            ).fetchone()["id"]
        )
        scope_id = int(
            self.store.connection.execute(
                f"""
                INSERT INTO {tables['time_series_scope_events']} (
                    time_series_set_id, event_type, to_scope, scope_revision,
                    owner_project_id, observed_set_revision_id,
                    observed_content_hash, actor_user_id,
                    actor_identity_snapshot, actor_role_snapshot, reason_code,
                    reason_text, request_id, idempotency_key, occurred_at
                ) VALUES (?, 'created_project', 'project', 1, ?, ?, ?, ?, ?,
                          'admin', 'created', 'catalog created', ?, ?,
                          '2026-01-01T00:00:00')
                RETURNING id
                """,
                (
                    self.receipt["set_id"],
                    self.project["id"],
                    self.receipt["revision_id"],
                    self.receipt["content_hash"],
                    self.user_id,
                    f"auditor-{self.suffix}@example.com",
                    f"request-scope-{self.suffix}",
                    f"scope-{self.suffix}",
                ),
            ).fetchone()["id"]
        )
        ledger_rows = {
            "time_series_link_validations": validation_id,
            "time_series_link_events": event_id,
            "time_series_scope_events": scope_id,
        }
        outcomes = {}
        for logical_name, row_id in ledger_rows.items():
            physical_name = tables[logical_name]
            outcomes[f"{logical_name}:update"] = postgres_guard_attempt(
                self.store.connection,
                f"UPDATE {physical_name} SET reason_code = 'rewritten' WHERE id = ?",
                (row_id,),
            )
            outcomes[f"{logical_name}:delete"] = postgres_guard_attempt(
                self.store.connection,
                f"DELETE FROM {physical_name} WHERE id = ?",
                (row_id,),
            )
        outcomes["delete_object"] = postgres_guard_attempt(
            self.store.connection,
            f"DELETE FROM {self.store.linkable_object_table_names()['linkable_objects']} "
            "WHERE id = ?",
            (self.object["id"],),
        )
        outcomes["delete_user"] = postgres_guard_attempt(
            self.store.connection,
            "DELETE FROM users WHERE id = ?",
            (self.user_id,),
        )

        expected = {
            f"{logical_name}:{operation}": LINK_LEDGER_IMMUTABLE
            for logical_name in ledger_rows
            for operation in ("update", "delete")
        }
        expected.update({"delete_object": "refused", "delete_user": "refused"})
        self.assertEqual(outcomes, expected)

if __name__ == "__main__":
    unittest.main()
