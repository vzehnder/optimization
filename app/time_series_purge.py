"""TS7-024 the single door through which a project's TS-7 trail leaves.

Chapter 9.6 makes every historical foreign key restrictive so that no ordinary
write loses sealed history, and chapter 5.4 allows purging only unsealed
technical rows. Deleting the project itself is neither of those: it is the one
lifecycle event that ends the retention of everything the project owns. This
module spells that closure out in dependency order - leaves first - so each
statement runs when its own children are already gone and no restrictive
foreign key is ever violated. The purge scope of ``time_series_canonical``
holds the immutability guards open for exactly the transaction that runs it.
"""

from app.time_series_canonical import canonical_space_table_name


def canonical_trail_statements(backend: str) -> list[str]:
    """The ordered DELETEs that erase the TS-7 trail of one project.

    Every statement binds the project id once per placeholder it carries, and
    scopes itself through the sets and objects the project owns rather than
    through a denormalized column the content model deliberately does not have.
    """

    table = {
        logical: canonical_space_table_name(logical, backend)
        for logical in (
            "time_series_sources",
            "time_series_sets",
            "time_series_signals",
            "time_series_set_revisions",
            "time_series_revision_signals",
            "time_series_periods",
            "time_series_values",
            "time_series_revision_lineage",
            "time_series_catalog_entries",
            "time_series_catalog_associations",
            "case_time_series_bindings",
            "time_series_link_validations",
            "time_series_link_events",
            "time_series_scope_events",
            "object_series_definitions",
            "time_series_ingestions",
            "linkable_objects",
        )
    }
    owned_sets = f"SELECT id FROM {table['time_series_sets']} WHERE owner_project_id = ?"
    owned_revisions = (
        f"SELECT id FROM {table['time_series_set_revisions']} "
        f"WHERE time_series_set_id IN ({owned_sets})"
    )
    # A link belongs to the project when either of its two ends does: the object
    # it hangs on, or the set it points at. A global set associated with an
    # object of this project is the first case, and a set of this project used
    # by nobody else is the second.
    owned_objects = (
        f"SELECT id FROM {table['linkable_objects']} WHERE project_id = ?"
    )
    owned_variants = (
        "SELECT case_input_variants.id FROM case_input_variants"
        " JOIN optimization_cases"
        "   ON optimization_cases.id = case_input_variants.case_id"
        " JOIN scenarios ON scenarios.id = optimization_cases.scenario_id"
        " WHERE scenarios.project_id = ?"
    )
    owned_associations = (
        f"SELECT id FROM {table['time_series_catalog_associations']}"
        f" WHERE linkable_object_id IN ({owned_objects})"
        f" OR time_series_set_id IN ({owned_sets})"
    )
    owned_bindings = (
        f"SELECT id FROM {table['case_time_series_bindings']}"
        f" WHERE linkable_object_id IN ({owned_objects})"
        f" OR time_series_set_id IN ({owned_sets})"
        f" OR case_input_variant_id IN ({owned_variants})"
    )

    return [
        # The staleness ledger names its owner through owner_type/owner_id and
        # not a foreign key, so nothing refuses a delete that would strand it
        # and nothing cascades it away. It leaves first, by both of its owners.
        (
            "DELETE FROM validation_dependencies"
            " WHERE (owner_type = 'case_input_variant'"
            f" AND owner_id IN ({owned_variants}))"
            " OR (owner_type = 'time_series_set'"
            f" AND owner_id IN ({owned_sets}))"
        ),
        # The three ledgers next: they name the links and the revisions that
        # every later statement removes.
                    f"DELETE FROM {table['time_series_link_validations']}"
            f" WHERE catalog_association_id IN ({owned_associations})"
            f" OR binding_id IN ({owned_bindings})"
            f" OR validated_set_revision_id IN ({owned_revisions})"
            f" OR observed_current_revision_id IN ({owned_revisions})",
                    f"DELETE FROM {table['time_series_link_events']}"
            f" WHERE catalog_association_id IN ({owned_associations})"
            f" OR binding_id IN ({owned_bindings})",
                    f"DELETE FROM {table['time_series_scope_events']}"
            f" WHERE owner_project_id = ? OR time_series_set_id IN ({owned_sets})",
                    f"DELETE FROM {table['case_time_series_bindings']}"
            f" WHERE id IN ({owned_bindings})",
                    f"DELETE FROM {table['time_series_catalog_associations']}"
            f" WHERE id IN ({owned_associations})",
        # Staged ingestions take their periods and values by cascade.
                    f"DELETE FROM {table['time_series_ingestions']} WHERE project_id = ?",
                    f"DELETE FROM {table['object_series_definitions']}"
            " WHERE owner_project_id = ?",
        # The projection is maintained by the same transaction that seals a
        # revision (TS7-005), so it leaves with the content it projects.
                    f"DELETE FROM {table['time_series_catalog_entries']}"
            " WHERE owner_project_id = ?",
                    f"DELETE FROM {table['time_series_values']} "
            f"WHERE set_revision_id IN ({owned_revisions})",
        # Lineage names a derived and a source revision, and a copy across
        # projects puts one of each side here. The project that leaves takes
        # the whole edge with it: what remains would name a revision that is
        # no longer there.
                    f"DELETE FROM {table['time_series_revision_lineage']} "
            f"WHERE derived_set_revision_id IN ({owned_revisions}) "
            f"OR source_set_revision_id IN ({owned_revisions})",
                    f"DELETE FROM {table['time_series_revision_signals']} "
            f"WHERE set_revision_id IN ({owned_revisions})",
                    f"DELETE FROM {table['time_series_periods']} "
            f"WHERE set_revision_id IN ({owned_revisions})",
                    f"DELETE FROM {table['time_series_set_revisions']} "
            f"WHERE time_series_set_id IN ({owned_sets})",
                    f"DELETE FROM {table['time_series_signals']} "
            f"WHERE time_series_set_id IN ({owned_sets})",
                    f"DELETE FROM {table['time_series_sets']} WHERE owner_project_id = ?",
                    f"DELETE FROM {table['time_series_sources']} WHERE project_id = ?",
    ]
