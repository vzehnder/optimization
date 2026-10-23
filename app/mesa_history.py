"""Read-only run history in the same context as mesa results."""

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from pydantic import BaseModel

from app.optimization_mesa import MesaRun, _frozen_timezone


class MesaHistoryRun(MesaRun):
    status: str
    created_at: str
    range_start: str | None = None
    range_end: str | None = None
    variant_id: int | None = None
    source_scenario_version_id: int | None = None


class MesaHistoryResponse(BaseModel):
    case_id: int
    runs: list[MesaHistoryRun]


def read_history(store, *, scenario_id, case_id, variant_id):
    case = store.get_or_create_case_for_scenario(scenario_id)
    if case["id"] != case_id:
        raise KeyError("El caso no pertenece al escenario.")
    variant = store.get_case_input_variant_for_case(case_id, variant_id)
    items = []
    for run in store.list_scenario_runs(scenario_id):
        version = store.get_scenario_version(run["scenario_version_id"])
        document, metadata = version["system_case_json"], version["generation_metadata"]
        contract = document.get("schema_version")
        if contract not in {"bess_system_dispatch.v1", "bess_system_dispatch.v2", "bess_system_dispatch.v3"}:
            continue
        origin = metadata.get("input_variant")
        hydraulic = metadata.get("mesa_hydraulic_execution") if contract == "bess_system_dispatch.v3" else None
        matches = (hydraulic.get("case_id") == case_id if hydraulic else
                   origin.get("id") == variant_id if origin else variant["is_default"])
        if not matches:
            continue
        zone = _frozen_timezone(store, metadata)
        start = end = None
        periods = document.get("time_series", [])
        if periods:
            first = datetime.fromisoformat(periods[0]["timestamp"])
            last = datetime.fromisoformat(periods[-1]["timestamp"])
            if zone and first.tzinfo is None:
                first, last = first.replace(tzinfo=ZoneInfo(zone)), last.replace(tzinfo=ZoneInfo(zone))
            duration = timedelta(hours=float(periods[-1]["duration_hours"]))
            finish = ((last.astimezone(timezone.utc) + duration).astimezone(last.tzinfo)
                      if last.tzinfo else last + duration)
            start, end = first.isoformat(), finish.isoformat()
        items.append(dict(id=run["id"], scenario_version_id=version["id"], model_contract=contract,
            timezone=zone, status=run["status"], created_at=run["created_at"], range_start=start, range_end=end,
            variant_id=None if hydraulic else (origin["id"] if origin else variant_id),
            source_scenario_version_id=hydraulic.get("source_scenario_version_id") if hydraulic else None))
    return dict(case_id=case_id, runs=items)
