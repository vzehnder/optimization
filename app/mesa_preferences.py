"""Visual-only desk preferences. Series and mathematical inputs live elsewhere."""

import json
from datetime import datetime, timezone
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator


class VisualModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class MesaComponentReference(VisualModel):
    linkable_object_id: int | None = Field(default=None, gt=0)
    entity_type: str = Field(min_length=1, max_length=80)
    entity_id: str = Field(min_length=1, max_length=160)


class MesaPanelPlacement(VisualModel):
    row: int = Field(ge=1, le=6)
    column: int = Field(ge=1, le=6)
    row_span: int = Field(default=1, ge=1, le=6)
    column_span: int = Field(default=1, ge=1, le=6)


class MesaPanelPreference(VisualModel):
    id: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=120)
    component: MesaComponentReference
    series_keys: list[Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]] = Field(min_length=1)
    series_axes: dict[str, Literal["primary", "secondary"]] = Field(default_factory=dict)
    mode: Literal["chart", "table"]
    placement: MesaPanelPlacement | None = None

    @model_validator(mode="after")
    def valid_axes(self):
        if not set(self.series_axes).issubset(self.series_keys):
            raise ValueError("Los ejes solo pueden asignarse a series seleccionadas.")
        return self

    @field_validator("series_keys")
    @classmethod
    def unique_series(cls, keys):
        if len(keys) != len(set(keys)):
            raise ValueError("Las series de una vista no se repiten.")
        return keys


class MesaTabPreference(VisualModel):
    id: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=120)
    layout: str = Field(pattern=r"^[1-6]x[1-6]$")
    panels: list[MesaPanelPreference] = Field(max_length=36)
    row_heights: list[Annotated[int, Field(ge=180)] | None] = Field(default_factory=list, max_length=6)

    @field_validator("panels")
    @classmethod
    def unique_panels(cls, panels):
        if len(panels) != len({panel.id for panel in panels}):
            raise ValueError("Las vistas de una pestaña deben tener identificadores distintos.")
        return panels

    @model_validator(mode="after")
    def valid_placements(self):
        rows, columns = map(int, self.layout.split("x"))
        occupied = set()
        for panel in self.panels:
            area = panel.placement
            # Old configurations use sequential, single-cell placement.
            if area is None:
                continue
            if area.row + area.row_span - 1 > rows or area.column + area.column_span - 1 > columns:
                raise ValueError(f'La vista "{panel.title}" queda fuera de la cuadrícula.')
            cells = {(row, column)
                     for row in range(area.row, area.row + area.row_span)
                     for column in range(area.column, area.column + area.column_span)}
            if occupied & cells:
                raise ValueError("Las vistas no pueden solaparse: cada celda pertenece a una sola vista.")
            occupied.update(cells)
        return self


class MesaConfiguration(VisualModel):
    schema_version: Literal[1] = 1
    active_tab_id: str = Field(min_length=1, max_length=80)
    tabs: list[MesaTabPreference] = Field(min_length=1, max_length=24)

    @model_validator(mode="after")
    def valid_tabs(self):
        ids = {tab.id for tab in self.tabs}
        if len(ids) != len(self.tabs) or self.active_tab_id not in ids:
            raise ValueError("Las pestañas deben ser únicas y la pestaña activa debe existir.")
        return self


class MesaPreferencesRequest(VisualModel):
    expected_revision: int = Field(ge=0)
    configuration: MesaConfiguration


class MesaPreferencesResponse(VisualModel):
    case_id: int
    revision: int
    configuration: MesaConfiguration


def initialize_preferences(store):
    # Additive, idempotent migration for both existing and newly created stores.
    with store._lock, store._database_transaction():
        store.connection.execute("""
            CREATE TABLE IF NOT EXISTS mesa_preferences (
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                case_id INTEGER NOT NULL REFERENCES optimization_cases(id) ON DELETE CASCADE,
                revision INTEGER NOT NULL CHECK (revision >= 0),
                configuration_json TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (user_id, case_id)
            )
        """)
        store.connection.execute(
            "INSERT INTO schema_migrations (name, applied_at) VALUES (?, ?) ON CONFLICT (name) DO NOTHING",
            ("mesa_preferences_v1", datetime.now(timezone.utc).isoformat()),
        )


def read_preferences(store, *, user_id: int, case_id: int) -> dict:
    with store._lock:
        row = store.connection.execute(
            "SELECT revision, configuration_json FROM mesa_preferences WHERE user_id = ? AND case_id = ?",
            (user_id, case_id),
        ).fetchone()
    return {
        "case_id": case_id, "revision": row["revision"] if row else 0,
        "configuration": json.loads(row["configuration_json"]) if row else {
            "schema_version": 1, "active_tab_id": "general",
            "tabs": [{"id": "general", "title": "Vista general", "layout": "2x2", "panels": []}],
        },
    }


class MesaPreferencesConflict(Exception):
    pass


def save_preferences(store, *, user_id: int, case_id: int, request: MesaPreferencesRequest) -> dict:
    with store._lock, store._database_transaction():
        store.connection.execute("""
            INSERT INTO mesa_preferences (user_id, case_id, revision, configuration_json, updated_at)
            VALUES (?, ?, 0, ?, ?)
            ON CONFLICT (user_id, case_id) DO NOTHING
        """, (user_id, case_id, request.configuration.model_dump_json(), datetime.now(timezone.utc).isoformat()))
        # Atomic compare-and-swap, including the first save. A stale request
        # rolls back the placeholder too; process-local locking is not the guard.
        changed = store.connection.execute("""
            UPDATE mesa_preferences SET revision = revision + 1, configuration_json = ?, updated_at = ?
            WHERE user_id = ? AND case_id = ? AND revision = ?
        """, (request.configuration.model_dump_json(), datetime.now(timezone.utc).isoformat(),
              user_id, case_id, request.expected_revision))
        if changed.rowcount != 1:
            raise MesaPreferencesConflict("La mesa cambió en otra sesión. Recarga la configuración guardada antes de reintentar.")
        return read_preferences(store, user_id=user_id, case_id=case_id)
