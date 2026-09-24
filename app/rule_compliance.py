"""Rebuild internal rule compliance from immutable inputs and solver artifacts."""
import math
import re
from datetime import datetime, timezone
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from app.results import ResultReadError, read_csv_artifact, read_json_artifact
from app.rule_diagnostics import failure_diagnostic
from app.rule_ir import RuleBoundsError, validate_model_bounds


class ComplianceRow(BaseModel):
    row_index: int
    name: str
    rule_id: str
    definition_id: str
    instance_revision: int
    revision_id: str
    application_id: str
    rule_name: str
    rule_url: str
    components: list[dict]
    period: int
    affected_periods: list[int]
    window: dict | None
    timestamp: str
    line: int
    unit: str
    relation: str
    constant: float
    terms: list[dict]
    lhs: float | None
    rhs: float
    margin: float | None
    residual: float | None
    absolute_tolerance: float
    relative_tolerance: float
    tolerance: float | None
    status: str


class ComplianceReport(BaseModel):
    version: str = "rule_compliance.v1"
    run_id: int
    solution_state: str
    termination_status: str | None
    counts: dict[str, int]
    rows: list[ComplianceRow]
    diagnostics: list["ComplianceDiagnostic"]
    page: "CompliancePage"
    samples: list["ComplianceSample"]
    rules: list["ComplianceRule"]
    period_count: int


class ComplianceConflict(BaseModel):
    name: str
    period: int
    application_id: str
    rule_url: str


class ComplianceDiagnostic(BaseModel):
    category: str
    message: str
    action: str
    code: str | None = None
    period: int | None = None
    line: int | None = None
    application_id: str | None = None
    rule_url: str | None = None
    conflicts: list[ComplianceConflict] = []


class CompliancePage(BaseModel):
    offset: int
    limit: int
    total: int
    next_offset: int | None


class ComplianceSample(BaseModel):
    row_index: int
    name: str
    period: int
    unit: str
    margin: float | None
    residual: float | None
    status: str


class ComplianceRule(BaseModel):
    rule_id: str
    name: str
    application_id: str
    revision_id: str
    url: str


def instant(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)


def rule_url(project_id, scenario_id, application):
    return (f"/react/projects/{project_id}/linkable-objects/{application['object_id']}/rules?"
            + urlencode({"scenario_id": scenario_id, "rule": application["rule_id"]}))


def term_value(term, objects, grid, values):
    columns = {"caudal": "hydro_turbine_flow_m3s", "potencia": "hydro_power_mw",
               "almacenamiento": "hydro_storage_hm3", "vertimiento": "hydro_spill_flow_m3s"}
    obj = objects[term["object_id"]]
    kind, key = ("hydraulic_unit", "unit_key") if "unit_key" in obj else ("hydraulic_reservoir", "node_key")
    row = values[(kind, obj[key], instant(grid[term["period"]]["timestamp"]))]
    return float(row[columns[term["variable"]]]) * term["coefficient"]


def rebuild_compliance(store, run, artifact_root):
    version = store.get_scenario_version(run["scenario_version_id"])
    document = version["system_case_json"]
    block = document.get("component_rules", {})
    project_id = store.get_scenario(version["scenario_id"])["project_id"]
    artifacts = {a["artifact_type"]: a for a in store.list_run_artifacts(run["id"])}
    diagnostics = []
    summary, dispatch = {}, {"rows": []}
    has_primal = run["status"] == "succeeded"
    if has_primal:
        try:
            summary = read_json_artifact(artifacts, "summary_json", artifact_root, display_name="summary.json")
            has_primal = summary.get("primal_status", "FEASIBLE_POINT") in {"FEASIBLE_POINT", "NEARLY_FEASIBLE_POINT"}
            if has_primal:
                dispatch = read_csv_artifact(artifacts, "asset_dispatch_csv", artifact_root, display_name="asset_dispatch.csv")
        except (ResultReadError, OSError, UnicodeError) as error:
            diagnostics.append({"category": "result_data", "message": str(error),
                                "action": "Restaurar los artefactos de esta corrida y reconstruir el informe."})
            has_primal = False
    termination = summary.get("termination_status") or (run.get("error_payload") or {}).get("termination_status")
    if not termination:
        match = re.search(r"termination_status=([A-Z_]+)", (run.get("error_payload") or {}).get("message", ""))
        termination = match.group(1) if match else None
    if termination == "INFEASIBLE":
        has_primal = False
        diagnostics.append({"category": "infeasible", "message": "El solver informa infactibilidad. No se identificó una causa única ni se dispone de IIS.",
                            "action": "Revisar conjuntamente reglas, balances y límites físicos de esta corrida."})
    if termination == "TIME_LIMIT":
        diagnostics.append({"category": "timeout", "message": "El solver alcanzó su límite de tiempo.",
                            "action": "Revisar el límite del solver y la solución disponible antes de reintentar."})
    state = ("no_primal" if not has_primal else "primal_available" if summary.get("primal_status") == "NEARLY_FEASIBLE_POINT" else "optimal" if termination == "OPTIMAL" else
             "feasible" if summary.get("primal_status") == "FEASIBLE_POINT" else "primal_available")
    values = {}
    for result_row in dispatch["rows"]:
        try:
            key = (result_row["asset_type"], result_row["asset_id"], instant(result_row["timestamp"]))
        except (KeyError, ValueError, TypeError, AttributeError):
            continue
        values[key] = None if key in values else result_row
    objects = {o["id"]: o for o in block.get("objects", [])}
    applications = {a["id"]: a for a in block.get("applications", [])}
    if block.get("rows"):
        try:
            validate_model_bounds(block["rows"], [dict(o, kind=o.get("kind", "hydraulic_unit")) for o in objects.values()], document)
        except RuleBoundsError as error:
            conflicts = []
            for origin in error.conflicting_rows:
                application = applications[origin["application_id"]]
                conflicts.append({"name": origin["name"], "period": origin["period"], "application_id": application["id"],
                                  "rule_url": rule_url(project_id, version["scenario_id"], application)})
            diagnostics.append({"code": "RULE_BOUNDS_CONFLICT", "category": "bounds_conflict", "message": str(error),
                                "action": "Revisar las cotas señaladas junto con los límites físicos congelados.", "conflicts": conflicts})
    if run["status"] in {"failed", "cancelled"} and termination not in {"INFEASIBLE", "TIME_LIMIT"}:
        diagnostic = failure_diagnostic(run.get("error_payload") or {}, status=run["status"])
        application = applications.get(diagnostic.get("application_id"))
        if application:
            diagnostic["rule_url"] = rule_url(project_id, version["scenario_id"], application)
        diagnostics.append(diagnostic)
    rows = []
    for index, row in enumerate(block.get("rows", [])):
        application = applications[row["application_id"]]
        lhs = None
        if has_primal:
            try:
                lhs = math.fsum(term_value(t, objects, block["grid"], values) for t in row["terms"])
                if not math.isfinite(lhs):
                    lhs = None
            except (KeyError, ValueError, TypeError, OverflowError):
                lhs = None
        rhs = -row["constant"]
        tolerance, residual, margin, status = None, None, None, "unavailable"
        if lhs is not None:
            tolerance = 1e-7 + 1e-7 * max(abs(lhs), abs(rhs))
            residual = lhs - rhs if row["relation"] == "==" else None
            margin = None if residual is not None else rhs - lhs if row["relation"] == "<=" else lhs - rhs
            satisfied = abs(residual) <= tolerance if residual is not None else margin >= -tolerance
            status = "satisfied" if satisfied else "violated"
        rows.append({"row_index": index, "name": row["name"], "rule_id": application["rule_id"],
                     "definition_id": (application.get("template") or {}).get("rule_id", application["rule_id"]),
                     "instance_revision": application["revision"], "constant": row["constant"], "terms": row["terms"],
                     "revision_id": row["revision_id"], "application_id": application["id"],
                     "rule_name": application["name"], "rule_url": rule_url(project_id, version["scenario_id"], application),
                     "components": [objects[oid] for oid in sorted({t["object_id"] for t in row["terms"]})],
                     "period": row["period"], "timestamp": block["grid"][row["period"]]["timestamp"],
                     "affected_periods": sorted({row["period"], *[t["period"] for t in row["terms"]], *row.get("window", {}).get("periods", [])}),
                     "window": row.get("window"),
                     "line": row["line"], "unit": row["unit"], "relation": row["relation"], "lhs": lhs, "rhs": rhs,
                     "margin": margin, "residual": residual, "absolute_tolerance": 1e-7, "relative_tolerance": 1e-7,
                     "tolerance": tolerance, "status": status})
    if has_primal and any(r["status"] == "unavailable" for r in rows):
        diagnostics.append({"category": "result_data", "message": "Faltan valores finitos para algunas filas; permanecen sin evaluar.",
                            "action": "Revisar los artefactos originales y reconstruir el informe completo."})
    return {"run_id": run["id"], "solution_state": state, "termination_status": termination,
            "period_count": len(block.get("grid", [])),
            "rules": [{"rule_id": a["rule_id"], "name": a["name"], "application_id": a["id"],
                       "revision_id": a["publication_id"], "url": rule_url(project_id, version["scenario_id"], a)} for a in applications.values()],
            "counts": {"total": len(rows), "evaluated": sum(r["status"] != "unavailable" for r in rows),
                       **{key: sum(r["status"] == key for r in rows) for key in ("satisfied", "violated", "unavailable")}},
            "rows": rows, "diagnostics": diagnostics}


def compliance_router(store, artifact_root):
    router = APIRouter(tags=["component-rules"])

    @router.get("/api/runs/{run_id}/rule-compliance", response_model=ComplianceReport)
    def get_compliance(run_id: int, request: Request, rule_id: str | None = None,
                       period: int | None = Query(None, ge=0), offset: int = Query(0, ge=0), limit: int = Query(25, ge=1, le=100)):
        user = getattr(request.state, "current_user", None)
        if not user:
            raise HTTPException(401, "Autenticación requerida")
        if user["role"] not in {"analyst", "admin"}:
            raise HTTPException(403, "Acceso interno requerido")
        try:
            report = rebuild_compliance(store, store.get_run(run_id), artifact_root)
            selected = [r for r in report["rows"] if (rule_id is None or r["rule_id"] == rule_id)
                        and (period is None or period in r["affected_periods"])]
            count = len(selected)
            sample_indices = range(count) if count <= 100 else [i * (count - 1) // 99 for i in range(100)]
            report["samples"] = [{k: selected[i][k] for k in ("row_index", "name", "period", "unit", "margin", "residual", "status")} for i in sample_indices]
            report["page"] = {"offset": offset, "limit": limit, "total": count, "next_offset": offset + limit if offset + limit < count else None}
            report["rows"] = selected[offset:offset + limit]
            return report
        except KeyError as error:
            raise HTTPException(404, "Corrida o snapshot no encontrado") from error
        except ResultReadError as error:
            raise HTTPException(error.status_code, error.message) from error

    return router
