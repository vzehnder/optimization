"""Add rule ports by canonical keys without reserving IDs used by custom types."""
from app.time_series_classification import ClassificationContractDriftError


def seed_rule_classification(store):
    tables = ("time_series_semantic_types", "time_series_binding_roles", "time_series_role_compatibilities")
    if store.database_backend == "postgresql":
        store.connection.execute("LOCK TABLE " + ", ".join((*tables, "measurement_dimensions", "measurement_units")) + " IN SHARE ROW EXCLUSIVE MODE")
    at = "2026-09-22T00:00:00+00:00"
    audit = {"created_at": at, "created_by": "reg-003"}

    def ensure(table, key, contract, labels):
        where = " AND ".join(f"{column} = ?" for column in key)
        row = store.connection.execute(f"SELECT * FROM {table} WHERE {where}", tuple(key.values())).fetchone()
        if row is not None:
            for field, expected in contract.items():
                if row[field] != expected:
                    raise ClassificationContractDriftError(context={"catalog": table, "key": str(key), "field": field, "expected": expected, "actual": row[field]})
            return row["id"]
        identity = store.connection.execute(f"SELECT COALESCE(MAX(id), 0) + 1 AS id FROM {table}").fetchone()["id"]
        document = {"id": identity, **key, **contract, **labels, "status": "active"}
        store.connection.execute(f"INSERT INTO {table} ({', '.join(document)}) VALUES ({', '.join('?' for _ in document)})", tuple(document.values()))
        if store.database_backend == "postgresql":
            store.connection.execute(f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), GREATEST(MAX(id), nextval(pg_get_serial_sequence('{table}', 'id'))), true) FROM {table}")
        return identity

    def identity(table, key, value):
        return store.connection.execute(f"SELECT id FROM {table} WHERE {key} = ?", (value,)).fetchone()["id"]

    volume = ensure("measurement_dimensions", {"dimension_key": "volume"}, {"value_kind": "numeric"}, {"display_name": "Volume"})
    ensure("measurement_units", {"unit_key": "hm3"}, {"dimension_id": volume, "physical_dimension": "volume"}, {"symbol": "hm³"})

    dimension = identity("measurement_dimensions", "dimension_key", "dimensionless")
    unit = identity("measurement_units", "unit_key", "dimensionless")
    availability = ensure(tables[0], {"semantic_key": "availability_factor"},
        {"dimension_id": dimension, "canonical_unit_id": unit, "value_kind": "numeric", "default_aggregation": "mean",
         "validation_rules_json": '{"minimum":0,"maximum":1}', "is_system": 1},
        {"display_name": "Availability factor", "description": "Known available fraction of a component's capacity.",
         **audit, "updated_at": at, "updated_by": "reg-003"})
    object_type = identity("linkable_object_types", "object_type_key", "hydraulic_unit")
    for key, dimension_key, unit_key, semantics in (
        ("rule_inflow", "flow", "m3_per_s", [identity(tables[0], "semantic_key", key) for key in ("natural_inflow", "hydro_inflow")]),
        ("rule_availability", "dimensionless", "dimensionless", [availability]),
    ):
        role = ensure(tables[1], {"role_key": key},
            {"dimension_id": identity("measurement_dimensions", "dimension_key", dimension_key),
             "canonical_unit_id": identity("measurement_units", "unit_key", unit_key),
             "association_allowed": 1, "execution_allowed": 1, "execution_contract_key": "component_rule_input", "is_system": 1},
            {"display_name": key.replace("_", " ").title()})
        for semantic in semantics:
            ensure(tables[2], {"semantic_type_id": semantic, "binding_role_id": role, "object_type_id": object_type, "rule_version": 1},
                {"association_allowed": 1, "execution_allowed": 1},
                {"supersedes_rule_id": None, **audit, "archived_at": None, "archived_by": None})
