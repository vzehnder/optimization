"""Closed register of linkable objects (TS-7 chapters 2.4, 5.3, 10.4).

Series are linked to heterogeneous things - a project-wide slot, an electrical
component, a hydraulic system, node, reach, plant or unit - and the link layer
needs one normalized identity for all of them. ``linkable_objects`` is that
identity: every row carries exactly one real typed foreign key into its subtype
table, never a ``entity_type``/``entity_id`` text pair, so authorization and
integrity resolve structurally instead of by convention.

The register lives in the canonical space beside the legacy tables, like the
content model of TS7-002: schema ``ts_next`` on PostgreSQL, ``_next`` suffix on
SQLite.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from app.time_series_canonical import (
    CANONICAL_SCHEMA_NAME,
    canonical_space_table_name,
)


REGISTER_LOGICAL_TABLES = (
    "global_signal_slots",
    "components",
    "linkable_objects",
)

# The branch column that carries the typed reference of each accepted family.
# ``object_kind`` repeats the vocabulary of ``linkable_object_types`` so the two
# can be compared directly; there is no second spelling of the same family.
LINKABLE_OBJECT_BRANCHES = {
    "global_signal_slot": "global_slot_id",
    "component": "component_id",
    "hydraulic_system": "hydraulic_system_id",
    "hydraulic_node": "hydraulic_node_id",
    "hydraulic_reach": "hydraulic_reach_id",
    "hydraulic_plant": "hydraulic_plant_id",
    "hydraulic_unit": "hydraulic_unit_id",
}

BRANCH_COLUMNS = tuple(LINKABLE_OBJECT_BRANCHES.values())

# The one slot every project gets: the destination of price and every other
# signal that has no physical asset. It does not make the project a link target.
SYSTEM_SLOT_KEY = "system"

# Component types the case model can hold, and the subset registered as link
# targets in this delivery. ``bus`` exists as topology only (chapter 2.4).
COMPONENT_TYPES = ("bus", "grid", "load", "renewable", "battery", "hydro")
LINKABLE_COMPONENT_TYPES = ("grid", "load", "renewable", "battery", "hydro")

# Families that are deliberately not link targets. Naming them turns a silent
# "no branch column exists" into an explicit refusal with a stable code.
NON_LINKABLE_FAMILIES = (
    "project",
    "user",
    "run",
    "publication",
    "operator_console",
    "scenario",
    "case",
)

# A case copy is never the link target: the register points at the base entity,
# so a case-scoped reference is resolved through its own foreign key first.
CASE_SCOPED_HYDRAULIC_REFERENCES = {
    "case_hydraulic_system": ("case_hydraulic_systems", "hydraulic_system_id"),
    "case_hydraulic_node": ("case_hydraulic_nodes", "hydraulic_node_id"),
    "case_hydraulic_reach": ("case_hydraulic_reaches", "hydraulic_reach_id"),
    "case_hydraulic_plant": ("case_hydraulic_plants", "hydraulic_plant_id"),
    "case_hydraulic_unit": ("case_hydraulic_units", "hydraulic_unit_id"),
}

BASE_HYDRAULIC_REFERENCES = {
    "hydraulic_system": "hydraulic_system",
    "hydraulic_node": "hydraulic_node",
    "hydraulic_reach": "hydraulic_reach",
    "hydraulic_plant": "hydraulic_plant",
    "hydraulic_unit": "hydraulic_unit",
}


LINKABLE_OBJECT_ERROR_CATALOG = {
    "TS_OBJECT_FAMILY_NOT_LINKABLE": (
        "timeseries.object.family_not_linkable",
        "object_kind",
        "Esa familia no es un objeto vinculable.",
    ),
    "TS_OBJECT_TYPE_MISMATCH": (
        "timeseries.object.type_mismatch",
        "object_type_id",
        "El tipo declarado no corresponde al objeto real.",
    ),
    "TS_OBJECT_PROJECT_MISMATCH": (
        "timeseries.object.project_mismatch",
        "project_id",
        "El objeto pertenece a otro proyecto.",
    ),
    "TS_OBJECT_REGISTER_ORPHAN": (
        "timeseries.object.register_orphan",
        "linkable_object_id",
        "El objeto real no puede retirarse dejando el registro activo.",
    ),
    "TS_OBJECT_SUBTYPE_NOT_FOUND": (
        "timeseries.object.subtype_not_found",
        "subtype_id",
        "El objeto real no existe.",
    ),
    "TS_OBJECT_NOT_REGISTERED": (
        "timeseries.object.not_registered",
        "linkable_object_id",
        "El objeto no esta registrado como vinculable.",
    ),
    "TS_MIGRATION_OBJECT_AMBIGUOUS": (
        "timeseries.migration.object_ambiguous",
        "component_key",
        "La referencia no identifica un objeto estable unico.",
    ),
    "TS_COMPAT_PROJECT_CONTEXT_MISMATCH": (
        "timeseries.compatibility.project_context_mismatch",
        "linkable_object_id",
        "El objeto no pertenece al contexto de proyecto.",
    ),
}

# Stable failure names raised by the portable register guards. The application
# produces friendly errors, but the database is the last defence (chapter 9.6).
LINKABLE_OBJECT_GUARD_CODES = (
    "TS_OBJECT_TYPE_MISMATCH",
    "TS_OBJECT_PROJECT_MISMATCH",
    "TS_OBJECT_REGISTER_ORPHAN",
)


class LinkableObjectError(RuntimeError):
    """A refusal from the register, carrying a stable code."""

    def __init__(self, code: str, **context):
        message_key, field, message = LINKABLE_OBJECT_ERROR_CATALOG[code]
        self.code = code
        self.message_key = message_key
        self.message = message
        self.field = field
        self.context = context
        super().__init__(f"{code}: {context}" if context else code)

    def as_problem(self) -> dict[str, object]:
        return {
            "code": self.code,
            "message_key": self.message_key,
            "message": self.message,
            "field": self.field,
            "context": dict(self.context),
        }


def linkable_object_table_names(backend: str) -> dict[str, str]:
    """Physical name of every register table for the given engine."""

    return {
        logical: linkable_object_table_name(logical, backend)
        for logical in REGISTER_LOGICAL_TABLES
    }


def linkable_object_table_name(logical: str, backend: str) -> str:
    if logical not in REGISTER_LOGICAL_TABLES:
        raise KeyError(f"unknown register table: {logical}")
    return canonical_space_table_name(logical, backend)


def _index_name(logical: str, suffix: str) -> str:
    return f"{logical}_next_{suffix}"


def _branch_check() -> str:
    """Each ``object_kind`` pins its own branch and nulls every other one."""

    clauses = []
    for kind, column in LINKABLE_OBJECT_BRANCHES.items():
        others = " AND ".join(
            f"{other} IS NULL" for other in BRANCH_COLUMNS if other != column
        )
        clauses.append(
            f"(object_kind = '{kind}' AND {column} IS NOT NULL AND {others})"
        )
    # PostgreSQL and SQLite agree on the shape; it is spelled once for both.
    return "\n                OR ".join(clauses)


def _owning_project_expression(tables: Mapping[str, str], prefix: str) -> str:
    """SQL for the project the referenced subtype really belongs to.

    Hydraulic nodes, reaches, plants and units carry no ``project_id`` of their
    own: it is reached through their system, which is exactly why the register
    verifies ownership instead of trusting the caller.
    """

    return f"""COALESCE(
            (SELECT slot.project_id FROM {tables['global_signal_slots']} AS slot
              WHERE slot.id = {prefix}global_slot_id),
            (SELECT component.project_id FROM {tables['components']} AS component
              WHERE component.id = {prefix}component_id),
            (SELECT system.project_id FROM hydraulic_systems AS system
              WHERE system.id = {prefix}hydraulic_system_id),
            (SELECT system.project_id FROM hydraulic_systems AS system
              JOIN hydraulic_nodes AS node
                ON node.hydraulic_system_id = system.id
              WHERE node.id = {prefix}hydraulic_node_id),
            (SELECT system.project_id FROM hydraulic_systems AS system
              JOIN hydraulic_reaches AS reach
                ON reach.hydraulic_system_id = system.id
              WHERE reach.id = {prefix}hydraulic_reach_id),
            (SELECT system.project_id FROM hydraulic_systems AS system
              JOIN hydraulic_plants AS plant
                ON plant.hydraulic_system_id = system.id
              WHERE plant.id = {prefix}hydraulic_plant_id),
            (SELECT system.project_id FROM hydraulic_systems AS system
              JOIN hydraulic_plants AS plant
                ON plant.hydraulic_system_id = system.id
              JOIN hydraulic_units AS unit
                ON unit.hydraulic_plant_id = plant.id
              WHERE unit.id = {prefix}hydraulic_unit_id)
        )"""


def _expected_type_key_expression(tables: Mapping[str, str], prefix: str) -> str:
    """SQL for the ``object_type_key`` the real object demands.

    A slot whose key is not ``system`` and a ``component:bus`` both produce a
    key that the closed catalog does not carry, so they are refused by the same
    comparison rather than by a second rule.
    """

    return f"""COALESCE(
            (SELECT 'global:' || slot.slot_key
               FROM {tables['global_signal_slots']} AS slot
              WHERE slot.id = {prefix}global_slot_id),
            (SELECT 'component:' || component.component_type
               FROM {tables['components']} AS component
              WHERE component.id = {prefix}component_id),
            CASE WHEN {prefix}hydraulic_system_id IS NOT NULL
                 THEN 'hydraulic_system' END,
            CASE WHEN {prefix}hydraulic_node_id IS NOT NULL
                 THEN 'hydraulic_node' END,
            CASE WHEN {prefix}hydraulic_reach_id IS NOT NULL
                 THEN 'hydraulic_reach' END,
            CASE WHEN {prefix}hydraulic_plant_id IS NOT NULL
                 THEN 'hydraulic_plant' END,
            CASE WHEN {prefix}hydraulic_unit_id IS NOT NULL
                 THEN 'hydraulic_unit' END
        )"""


def _declared_type_key_expression(prefix: str) -> str:
    return f"""(SELECT object_type.object_type_key
           FROM linkable_object_types AS object_type
          WHERE object_type.id = {prefix}object_type_id
            AND object_type.object_kind = {prefix}object_kind
            AND object_type.status = 'active')"""


def linkable_object_schema_statements(backend: str) -> list[str]:
    """DDL that lands the closed register on the given engine."""

    postgres = backend == "postgresql"
    tables = linkable_object_table_names(backend)
    identity = (
        "BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY"
        if postgres
        else "INTEGER PRIMARY KEY AUTOINCREMENT"
    )
    reference = "BIGINT" if postgres else "INTEGER"

    statements: list[str] = []
    if postgres:
        # The register lands before the content model, so it opens the space.
        statements.append(f"CREATE SCHEMA IF NOT EXISTS {CANONICAL_SCHEMA_NAME}")

    statements.append(
        f"""
        CREATE TABLE IF NOT EXISTS {tables['global_signal_slots']} (
            id {identity},
            project_id {reference} NOT NULL
                REFERENCES projects(id) ON DELETE CASCADE,
            slot_key TEXT NOT NULL,
            display_name TEXT NOT NULL,
            created_at TEXT NOT NULL,
            created_by TEXT NOT NULL,
            UNIQUE (project_id, slot_key),
            UNIQUE (id, project_id)
        )
        """
    )
    statements.append(
        f"""
        CREATE TABLE IF NOT EXISTS {tables['components']} (
            id {identity},
            project_id {reference} NOT NULL
                REFERENCES projects(id) ON DELETE CASCADE,
            component_key TEXT NOT NULL,
            component_type TEXT NOT NULL,
            display_name TEXT NOT NULL,
            external_reference TEXT,
            is_active INTEGER NOT NULL DEFAULT 1,
            metadata_json TEXT NOT NULL DEFAULT '{{}}',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            CHECK (is_active IN (0, 1)),
            CHECK (component_type IN {COMPONENT_TYPES!r}),
            UNIQUE (project_id, component_key),
            UNIQUE (id, project_id),
            UNIQUE (id, component_type)
        )
        """
    )
    statements.append(
        f"""
        CREATE TABLE IF NOT EXISTS {tables['linkable_objects']} (
            id {identity},
            project_id {reference} NOT NULL
                REFERENCES projects(id) ON DELETE CASCADE,
            object_kind TEXT NOT NULL,
            object_type_id {reference} NOT NULL
                REFERENCES linkable_object_types(id),
            global_slot_id {reference} UNIQUE
                REFERENCES {tables['global_signal_slots']}(id) ON DELETE CASCADE,
            component_id {reference} UNIQUE
                REFERENCES {tables['components']}(id) ON DELETE CASCADE,
            hydraulic_system_id {reference} UNIQUE
                REFERENCES hydraulic_systems(id) ON DELETE CASCADE,
            hydraulic_node_id {reference} UNIQUE
                REFERENCES hydraulic_nodes(id) ON DELETE CASCADE,
            hydraulic_reach_id {reference} UNIQUE
                REFERENCES hydraulic_reaches(id) ON DELETE CASCADE,
            hydraulic_plant_id {reference} UNIQUE
                REFERENCES hydraulic_plants(id) ON DELETE CASCADE,
            hydraulic_unit_id {reference} UNIQUE
                REFERENCES hydraulic_units(id) ON DELETE CASCADE,
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL,
            created_by TEXT NOT NULL,
            archived_at TEXT,
            archived_by TEXT,
            CHECK (status IN ('active', 'archived')),
            CONSTRAINT linkable_objects_id_project_uk UNIQUE (id, project_id),
            CONSTRAINT linkable_objects_exactly_one_subtype_ck CHECK (
                {_branch_check()}
            )
        )
        """
    )

    statements.extend(
        [
            f"""
            CREATE INDEX IF NOT EXISTS
                {_index_name('linkable_objects', 'project_status_idx')}
                ON {tables['linkable_objects']}
                (project_id, status, object_kind, id)
            """,
            f"""
            CREATE INDEX IF NOT EXISTS
                {_index_name('linkable_objects', 'project_type_idx')}
                ON {tables['linkable_objects']}
                (project_id, object_type_id, status, id)
            """,
            f"""
            CREATE INDEX IF NOT EXISTS
                {_index_name('components', 'project_type_key_idx')}
                ON {tables['components']}
                (project_id, component_type, component_key)
            """,
        ]
    )
    return [statement.strip() for statement in statements]


def linkable_object_guard_script(backend: str) -> str:
    """Triggers that keep the register honest on both engines (chapter 2.4).

    Resolution 01 authorizes exactly this: the parent and the subtype are
    written in one transaction, and a trigger verifies that the declared project
    is the project of the real object. It verifies; it never guesses.
    """

    tables = linkable_object_table_names(backend)
    register = tables["linkable_objects"]
    components = tables["components"]

    if backend == "postgresql":
        owning_project = _owning_project_expression(tables, "NEW.")
        expected_key = _expected_type_key_expression(tables, "NEW.")
        declared_key = _declared_type_key_expression("NEW.")
        return f"""
        CREATE OR REPLACE FUNCTION ts_next.reject_object_register_mismatch()
        RETURNS trigger AS $$
        BEGIN
            IF {declared_key} IS DISTINCT FROM {expected_key} THEN
                RAISE EXCEPTION 'TS_OBJECT_TYPE_MISMATCH';
            END IF;
            IF NEW.project_id IS DISTINCT FROM {owning_project} THEN
                RAISE EXCEPTION 'TS_OBJECT_PROJECT_MISMATCH';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;

        CREATE OR REPLACE FUNCTION ts_next.reject_component_register_orphan()
        RETURNS trigger AS $$
        BEGIN
            IF OLD.is_active = 1 AND NEW.is_active = 0 AND EXISTS (
                SELECT 1 FROM {register} AS registered
                WHERE registered.component_id = OLD.id
                  AND registered.status = 'active'
            ) THEN
                RAISE EXCEPTION 'TS_OBJECT_REGISTER_ORPHAN';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;

        DROP TRIGGER IF EXISTS ts_next_object_register_insert ON {register};
        CREATE TRIGGER ts_next_object_register_insert
        BEFORE INSERT ON {register}
        FOR EACH ROW EXECUTE FUNCTION ts_next.reject_object_register_mismatch();

        DROP TRIGGER IF EXISTS ts_next_object_register_update ON {register};
        CREATE TRIGGER ts_next_object_register_update
        BEFORE UPDATE ON {register}
        FOR EACH ROW EXECUTE FUNCTION ts_next.reject_object_register_mismatch();

        DROP TRIGGER IF EXISTS ts_next_component_register_orphan ON {components};
        CREATE TRIGGER ts_next_component_register_orphan
        BEFORE UPDATE ON {components}
        FOR EACH ROW EXECUTE FUNCTION ts_next.reject_component_register_orphan();
        """

    owning_project = _owning_project_expression(tables, "NEW.")
    expected_key = _expected_type_key_expression(tables, "NEW.")
    declared_key = _declared_type_key_expression("NEW.")
    statements = []
    for event in ("INSERT", "UPDATE"):
        label = event.lower()
        # One trigger, not two: SQLite does not promise an order between
        # triggers on the same event, and a row that breaks both rules has to
        # report the same failure here as PostgreSQL reports there.
        statements.append(
            f"""
            DROP TRIGGER IF EXISTS ts_next_object_register_type_{label};
            DROP TRIGGER IF EXISTS ts_next_object_register_project_{label};
            DROP TRIGGER IF EXISTS ts_next_object_register_{label};
            CREATE TRIGGER ts_next_object_register_{label}
            BEFORE {event} ON {register}
            FOR EACH ROW WHEN {declared_key} IS NOT {expected_key}
                OR NEW.project_id IS NOT {owning_project}
            BEGIN
                SELECT CASE
                    WHEN {declared_key} IS NOT {expected_key}
                        THEN RAISE(ABORT, 'TS_OBJECT_TYPE_MISMATCH')
                    ELSE RAISE(ABORT, 'TS_OBJECT_PROJECT_MISMATCH')
                END;
            END;
            """
        )
    statements.append(
        f"""
        DROP TRIGGER IF EXISTS ts_next_component_register_orphan;
        CREATE TRIGGER ts_next_component_register_orphan
        BEFORE UPDATE ON {components}
        FOR EACH ROW WHEN OLD.is_active = 1 AND NEW.is_active = 0 AND EXISTS (
            SELECT 1 FROM {register} AS registered
            WHERE registered.component_id = OLD.id
              AND registered.status = 'active'
        )
        BEGIN
            SELECT RAISE(ABORT, 'TS_OBJECT_REGISTER_ORPHAN');
        END;
        """
    )
    return "\n".join(statements)


def subtype_lookup_sql(object_kind: str, tables: Mapping[str, str]) -> str:
    """Read the real object: its project, its stable key and the type it is.

    ``object_type_key`` is derived here, never declared by the caller, so a slot
    that is not ``system`` and a ``component:bus`` produce a key the closed
    catalog does not carry and are refused by the lookup that follows.
    """

    sources = {
        "global_signal_slot": f"""
            SELECT slot.id AS subtype_id,
                   slot.project_id AS project_id,
                   slot.slot_key AS object_key,
                   slot.display_name AS display_name,
                   'global:' || slot.slot_key AS object_type_key
            FROM {tables['global_signal_slots']} AS slot
            WHERE slot.id = ?
        """,
        "component": f"""
            SELECT component.id AS subtype_id,
                   component.project_id AS project_id,
                   component.component_key AS object_key,
                   component.display_name AS display_name,
                   'component:' || component.component_type AS object_type_key
            FROM {tables['components']} AS component
            WHERE component.id = ?
        """,
        "hydraulic_system": """
            SELECT system.id AS subtype_id,
                   system.project_id AS project_id,
                   system.system_key AS object_key,
                   system.display_name AS display_name,
                   'hydraulic_system' AS object_type_key
            FROM hydraulic_systems AS system
            WHERE system.id = ?
        """,
        "hydraulic_node": """
            SELECT node.id AS subtype_id,
                   system.project_id AS project_id,
                   node.node_key AS object_key,
                   node.display_name AS display_name,
                   'hydraulic_node' AS object_type_key
            FROM hydraulic_nodes AS node
            JOIN hydraulic_systems AS system
              ON system.id = node.hydraulic_system_id
            WHERE node.id = ?
        """,
        "hydraulic_reach": """
            SELECT reach.id AS subtype_id,
                   system.project_id AS project_id,
                   reach.reach_key AS object_key,
                   reach.display_name AS display_name,
                   'hydraulic_reach' AS object_type_key
            FROM hydraulic_reaches AS reach
            JOIN hydraulic_systems AS system
              ON system.id = reach.hydraulic_system_id
            WHERE reach.id = ?
        """,
        "hydraulic_plant": """
            SELECT plant.id AS subtype_id,
                   system.project_id AS project_id,
                   plant.plant_key AS object_key,
                   plant.display_name AS display_name,
                   'hydraulic_plant' AS object_type_key
            FROM hydraulic_plants AS plant
            JOIN hydraulic_systems AS system
              ON system.id = plant.hydraulic_system_id
            WHERE plant.id = ?
        """,
        "hydraulic_unit": """
            SELECT unit.id AS subtype_id,
                   system.project_id AS project_id,
                   unit.unit_key AS object_key,
                   unit.display_name AS display_name,
                   'hydraulic_unit' AS object_type_key
            FROM hydraulic_units AS unit
            JOIN hydraulic_plants AS plant
              ON plant.id = unit.hydraulic_plant_id
            JOIN hydraulic_systems AS system
              ON system.id = plant.hydraulic_system_id
            WHERE unit.id = ?
        """,
    }
    if object_kind not in sources:
        raise LinkableObjectError(
            "TS_OBJECT_FAMILY_NOT_LINKABLE", object_kind=object_kind
        )
    return sources[object_kind].strip()


def linkable_object_projection_sql(tables: Mapping[str, str]) -> str:
    """One row per registered object, with the identity of its real subtype."""

    return f"""
        SELECT registered.id AS id,
               registered.project_id AS project_id,
               registered.object_kind AS object_kind,
               registered.object_type_id AS object_type_id,
               registered.status AS status,
               registered.created_at AS created_at,
               registered.created_by AS created_by,
               registered.archived_at AS archived_at,
               registered.archived_by AS archived_by,
               object_type.object_type_key AS object_type_key,
               component.component_type AS component_type,
               COALESCE(
                   registered.global_slot_id, registered.component_id,
                   registered.hydraulic_system_id, registered.hydraulic_node_id,
                   registered.hydraulic_reach_id, registered.hydraulic_plant_id,
                   registered.hydraulic_unit_id
               ) AS subtype_id,
               COALESCE(
                   slot.slot_key, component.component_key, system.system_key,
                   node.node_key, reach.reach_key, plant.plant_key, unit.unit_key
               ) AS object_key,
               COALESCE(
                   slot.display_name, component.display_name,
                   system.display_name, node.display_name, reach.display_name,
                   plant.display_name, unit.display_name
               ) AS display_name
        FROM {tables['linkable_objects']} AS registered
        JOIN linkable_object_types AS object_type
          ON object_type.id = registered.object_type_id
        LEFT JOIN {tables['global_signal_slots']} AS slot
          ON slot.id = registered.global_slot_id
        LEFT JOIN {tables['components']} AS component
          ON component.id = registered.component_id
        LEFT JOIN hydraulic_systems AS system
          ON system.id = registered.hydraulic_system_id
        LEFT JOIN hydraulic_nodes AS node
          ON node.id = registered.hydraulic_node_id
        LEFT JOIN hydraulic_reaches AS reach
          ON reach.id = registered.hydraulic_reach_id
        LEFT JOIN hydraulic_plants AS plant
          ON plant.id = registered.hydraulic_plant_id
        LEFT JOIN hydraulic_units AS unit
          ON unit.id = registered.hydraulic_unit_id
    """.strip()


# -- Materializing components out of cases and drafts (chapter 10.4) --------
#
# Components live inside the JSON of cases and drafts today. They are grouped by
# ``project_id + component_type + technical_key`` with no fuzzy matching at all:
# a key is taken only when it is present and agrees on its type across every
# authoritative appearance, and a plausible-looking string is never enough.

# The editor calls the point of common coupling ``pcc``; the generated case
# writes it as a ``bus`` node. Both name the same topological component.
_COMPONENT_TYPE_ALIASES = {"pcc": "bus"}


def _appearance(raw_key: Any, raw_type: Any, raw_name: Any, origin: str) -> dict | None:
    component_type = _COMPONENT_TYPE_ALIASES.get(
        str(raw_type or "").strip(), str(raw_type or "").strip()
    )
    if component_type not in COMPONENT_TYPES:
        return None
    component_key = str(raw_key or "").strip()
    display_name = str(raw_name or "").strip() or component_key
    if not component_key:
        return {
            "component_key": None,
            "component_type": component_type,
            "display_name": display_name,
            "origin": origin,
            "skipped": "missing_component_key",
        }
    return {
        "component_key": component_key,
        "component_type": component_type,
        "display_name": display_name,
        "origin": origin,
        "skipped": None,
    }


def case_component_appearances(document: Any, origin: str = "case") -> list[dict]:
    """Every component the generated system case declares."""

    if not isinstance(document, Mapping):
        return []
    nodes = document.get("nodes")
    if not isinstance(nodes, list):
        return []
    appearances = []
    for node in nodes:
        if not isinstance(node, Mapping):
            continue
        found = _appearance(
            node.get("id"),
            node.get("type"),
            node.get("display_name") or node.get("display_category"),
            origin,
        )
        if found is not None:
            appearances.append(found)
    return appearances


def draft_component_appearances(document: Any, origin: str = "draft") -> list[dict]:
    """Every component the editor draft declares."""

    if not isinstance(document, Mapping):
        return []
    appearances = []
    for key in ("pcc", "grid"):
        node = document.get(key)
        if isinstance(node, Mapping):
            found = _appearance(
                node.get("id"), node.get("type"), node.get("display_name"), origin
            )
            if found is not None:
                appearances.append(found)
    assets = document.get("assets")
    if isinstance(assets, list):
        for asset in assets:
            if not isinstance(asset, Mapping):
                continue
            found = _appearance(
                asset.get("id"),
                asset.get("type"),
                asset.get("display_name") or asset.get("category"),
                origin,
            )
            if found is not None:
                appearances.append(found)
    return appearances


def group_component_appearances(
    appearances: Iterable[Mapping[str, Any]],
) -> tuple[dict[str, dict], list[dict]]:
    """Fold the appearances into one group per key, or refuse to guess.

    The same key carrying two component types is an ambiguity a migration must
    not resolve on its own, so it raises ``TS_MIGRATION_OBJECT_AMBIGUOUS``
    instead of picking the first, the newest or the most frequent.
    """

    groups: dict[str, dict] = {}
    skipped: list[dict] = []
    for appearance in appearances:
        if appearance.get("skipped"):
            skipped.append(dict(appearance))
            continue
        component_key = str(appearance["component_key"])
        component_type = str(appearance["component_type"])
        group = groups.get(component_key)
        if group is None:
            groups[component_key] = {
                "component_key": component_key,
                "component_type": component_type,
                "display_name": str(appearance.get("display_name") or component_key),
                "origins": [str(appearance.get("origin") or "")],
            }
            continue
        if group["component_type"] != component_type:
            raise LinkableObjectError(
                "TS_MIGRATION_OBJECT_AMBIGUOUS",
                component_key=component_key,
                component_types=sorted(
                    {group["component_type"], component_type}
                ),
                reason="component_type_conflict",
            )
        group["origins"].append(str(appearance.get("origin") or ""))
    return groups, skipped


def canonical_owner_object_reference_script(backend: str) -> str | None:
    """Install the owner reference on a canonical space that predates it.

    A database created before TS7-003 already carries ``time_series_sets``
    without the composite reference to the register. PostgreSQL can add it in
    place; SQLite cannot ``ALTER TABLE ... ADD CONSTRAINT``, and there the
    constraint is part of the create statement instead.
    """

    if backend != "postgresql":
        return None
    register = canonical_space_table_name("linkable_objects", backend)
    sets = canonical_space_table_name("time_series_sets", backend)
    return f"""
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint
            WHERE conname = 'time_series_set_owner_object_fk'
              AND conrelid = '{sets}'::regclass
        ) THEN
            ALTER TABLE {sets}
                ADD CONSTRAINT time_series_set_owner_object_fk
                FOREIGN KEY (owner_linkable_object_id, owner_project_id)
                REFERENCES {register}(id, project_id);
        END IF;
    END $$;
    """
