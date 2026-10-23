"""CSV projection of the public, immutable mesa comparison."""

import csv
import io
from typing import Literal

from pydantic import BaseModel, Field

from app.mesa_comparison import read_comparison
from app.optimization_mesa import _instant


class MesaExportPanel(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    entity_id: str = Field(min_length=1, max_length=200)
    entity_type: str = Field(min_length=1, max_length=100)
    series_keys: list[str] = Field(min_length=1, max_length=30)


class MesaExportRequest(BaseModel):
    case_id: int = Field(gt=0)
    variant_id: int = Field(gt=0)
    run_id: int = Field(gt=0)
    reference_run_id: int | None = Field(default=None, gt=0)
    panels: list[MesaExportPanel] = Field(min_length=1, max_length=6)
    range_start: str | None = None
    range_end: str | None = None
    mode: Literal["before", "compare", "after"] = "compare"


ORIGIN_FIELDS = {"run_id": "run_id", "snapshot_id": "scenario_version_id", "source": "source",
                 "revision_id": "revision_id", "revision_number": "revision_number", "content_hash": "content_hash",
                 "status": "status", "message": "message", "timezone": "timezone"}
FIELDS = ["view", "entity_id", "entity_type", "signal_key", "series", "unit", "role", "status", "message",
          "start", "end", "timezone", "before", "after", "delta"] + [
              f"{side}_{key}" for side in ("before", "after") for key in ORIGIN_FIELDS]


def _spreadsheet_text(value):
    if isinstance(value, str) and (value.lstrip().startswith(("=", "+", "-", "@"))
                                  or value.startswith(("\t", "\r", "\n"))):
        return "'" + value
    return value


def export_comparison(store, *, scenario_id, payload, artifact_root):
    comparison = read_comparison(store, scenario_id=scenario_id, case_id=payload.case_id,
        variant_id=payload.variant_id, run_id=payload.run_id, reference_run_id=payload.reference_run_id,
        range_start=payload.range_start, range_end=payload.range_end, artifact_root=artifact_root)
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=FIELDS)
    writer.writeheader()
    manual_components = None
    for panel in payload.panels:
        if panel.entity_type == "manual_series":
            if manual_components is None:
                from app.optimization_mesa import read_mesa
                manual_components = read_mesa(store, scenario_id=scenario_id, case_id=payload.case_id,
                                              variant_id=payload.variant_id)["components"]
            component = next((c for c in manual_components if c["entity_type"] == "manual_series"
                              and c["entity_id"] == panel.entity_id), None)
            if not component or panel.series_keys != [component["series"]["signal_key"]]:
                raise ValueError("La serie de apoyo no está disponible en este caso.")
            writer.writerow({key: _spreadsheet_text(value) for key, value in dict(view=panel.title,
                entity_id=panel.entity_id, entity_type="manual_series", signal_key=component["series"]["signal_key"],
                series=component["name"], unit=component["series"]["unit"], role="support", status="not_compared",
                message="Esta vista de apoyo no tiene resultados ni diferencias. Consulta la entrada del objeto ejecutado para ver la revisión utilizada.").items()})
            continue
        for key in panel.series_keys:
            series = next((s for s in comparison["series"] if s["entity_id"] == panel.entity_id
                and s["entity_type"] == panel.entity_type and s["signal_key"] == key), None)
            if series is None:
                raise ValueError("La serie seleccionada no pertenece al snapshot ejecutado.")
            row = {"view": panel.title, **{key: series[key] for key in
                ("entity_id", "entity_type", "signal_key", "unit", "role", "status", "message")},
                "series": series["name"], "timezone": series["after"].get("timezone")}
            sides = {}
            intervals = {}
            for side in ("before", "after", "delta"):
                visible = (payload.mode == "compare" or side == payload.mode)
                source = series.get(side) if visible else None
                points = source if side == "delta" else (source or {}).get("points")
                sides[side] = {}
                for point in points or []:
                    zone = (series["after"] if side == "delta" else source).get("timezone")
                    start, end = _instant(point["start"], zone), _instant(point["end"], zone)
                    # A local wall clock without a zone cannot be paired with another run.
                    scope = "instant" if start.tzinfo else ("snapshot" if series["status"] == "unchanged_input" else side)
                    instant = (start.isoformat(), end.isoformat(), scope)
                    sides[side][instant] = point["value"]
                    intervals[instant] = (point, zone)
                if side != "delta":
                    row.update({f"{side}_{column}": (source or {}).get(field) for column, field in ORIGIN_FIELDS.items()})
            for instant in sorted(intervals):
                point, zone = intervals[instant]
                writer.writerow({key: _spreadsheet_text(value) for key, value in {
                    **row, "start": point["start"], "end": point["end"], "timezone": zone,
                    **{side: points.get(instant) for side, points in sides.items()}}.items()})
            if not intervals:
                writer.writerow({key: _spreadsheet_text(value) for key, value in row.items()})
    return "\ufeff" + output.getvalue()
