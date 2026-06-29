from __future__ import annotations

import copy
import json
import os
import secrets
from contextlib import asynccontextmanager
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal
from urllib.parse import quote

from fastapi import FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from plotly.offline import get_plotlyjs
from pydantic import BaseModel, Field

from app.auth import (
    AuthorizationService,
    VALID_USER_ROLES,
    hash_password,
    hash_session_token,
    new_session_token,
    session_expires_at,
    verify_password,
)
from app.draft_editor import (
    DraftGenerationError,
    generate_system_case_from_draft,
    structured_draft_document_from_system_case,
)
from app.persistence import (
    AnalystStore,
    DEFAULT_PUBLICATION_ARTIFACT_TYPES,
    build_hydraulic_diagram_layout_snapshot,
    utc_now_iso,
)
from app.results import ResultReadError, apply_dashboard_template, read_run_results
from app.runner import JuliaRunExecutor, LocalRunQueue
from app.time_series_ingestion import (
    TimeSeriesIngestionError,
    attach_time_series_source,
    apply_time_series_mapping,
    get_time_series_source_rows,
    ingest_time_series_source,
    update_time_series_source_rows,
)
from app.validation import JuliaValidationService, ValidationResult


class SystemCaseValidationRequest(BaseModel):
    system_case_json: str = Field(min_length=1)


class ProjectCreateRequest(BaseModel):
    name: str = Field(min_length=1)
    description: str = ""


class ScenarioCreateRequest(BaseModel):
    name: str = Field(min_length=1)
    description: str = ""


class UserCreateRequest(BaseModel):
    email: str = Field(min_length=1)
    password: str = Field(min_length=1)
    role: str = Field(min_length=1)
    display_name: str = ""


class BootstrapAdminRequest(BaseModel):
    email: str = Field(min_length=1)
    password: str = Field(min_length=1)
    display_name: str = ""


class LoginRequest(BaseModel):
    email: str = Field(min_length=1)
    password: str = Field(min_length=1)
    next: str = ""


class CurrentUser(BaseModel):
    id: int
    email: str
    display_name: str
    role: Literal["admin", "analyst", "client"]
    is_active: bool


class CurrentUserResponse(BaseModel):
    user: CurrentUser | None
    bootstrap_required: bool = False


class AuthSessionResponse(BaseModel):
    user: CurrentUser
    redirect_path: str


class CsrfTokenResponse(BaseModel):
    csrf_token: str


class ProjectClientAccessRequest(BaseModel):
    user_id: int


class DashboardTemplateWriteRequest(BaseModel):
    name: str = Field(min_length=1)
    show_summary: bool = True
    show_price_chart: bool = True
    show_grid_chart: bool = True
    show_renewable_chart: bool = True
    show_bess_chart: bool = True
    show_hydro_chart: bool = True
    show_profit_chart: bool = True
    show_system_dispatch_table: bool = True
    show_asset_dispatch_table: bool = True
    table_preview_limit: int = Field(default=10, ge=1)


class PublicationDraftWriteRequest(BaseModel):
    dashboard_template_id: int
    public_title: str = Field(min_length=1)
    analyst_notes: str = ""
    allowed_artifact_types: list[str] | None = None


class ScenarioVersionCreateRequest(BaseModel):
    system_case_json: str = Field(min_length=1)


class ScenarioDraftWriteRequest(BaseModel):
    document: dict[str, Any] | None = None
    source_version_id: int | None = None


class HydraulicDiagramViewportRequest(BaseModel):
    x: float = 0.0
    y: float = 0.0
    zoom: float = Field(default=1.0, gt=0)


class HydraulicReservoirParametersRequest(BaseModel):
    storage_min_hm3: float
    storage_max_hm3: float
    initial_storage_hm3: float
    terminal_condition: Literal["none", "equal_initial", "min_terminal"] = "none"
    terminal_storage_min_hm3: float | None = None
    terminal_water_value_usd_per_hm3: float = 0.0


class HydraulicCurvePointRequest(BaseModel):
    x_value: float
    y_value: float


class HydraulicStorageElevationCurveRequest(BaseModel):
    curve_set_id: int | None = None
    version_label: str | None = None
    points: list[HydraulicCurvePointRequest] = Field(default_factory=list)


class HydraulicFlowPowerCurveRequest(BaseModel):
    curve_set_id: int | None = None
    version_label: str | None = None
    points: list[HydraulicCurvePointRequest] = Field(default_factory=list)


class HydraulicNaturalInflowSeriesPointRequest(BaseModel):
    timestamp: str = Field(min_length=1)
    duration_hours: float = 1.0
    value_m3s: float


class HydraulicNaturalInflowSeriesRequest(BaseModel):
    time_series_set_id: int | None = None
    version_label: str | None = None
    points: list[HydraulicNaturalInflowSeriesPointRequest] = Field(default_factory=list)


class HydraulicPlantParametersRequest(BaseModel):
    non_modeled: bool = False
    min_power_mw: float | None = None
    max_power_mw: float | None = None


class HydraulicUnitRequest(BaseModel):
    technical_key: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    is_active: bool = True
    intake_node_key: str | None = None
    discharge_node_key: str | None = None
    min_power_mw: float | None = None
    max_power_mw: float | None = None
    min_flow_m3s: float | None = None
    max_flow_m3s: float | None = None
    flow_power_curve: HydraulicFlowPowerCurveRequest | None = None


class HydraulicDiagramNodeRequest(BaseModel):
    component_type: Literal["reservoir", "junction", "plant"]
    technical_key: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    x: float | None = None
    y: float | None = None
    reservoir: HydraulicReservoirParametersRequest | None = None
    storage_elevation_curve: HydraulicStorageElevationCurveRequest | None = None
    natural_inflow_series: HydraulicNaturalInflowSeriesRequest | None = None
    plant: HydraulicPlantParametersRequest | None = None
    units: list[HydraulicUnitRequest] = Field(default_factory=list)


class HydraulicDiagramReachRequest(BaseModel):
    technical_key: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    from_node_key: str = Field(min_length=1)
    to_node_key: str = Field(min_length=1)
    reach_type: str = Field(min_length=1)
    flow_min_m3s: float | None = None
    spill_penalty_usd_per_hm3: float | None = None
    minimum_flow_series: HydraulicNaturalInflowSeriesRequest | None = None


class HydraulicDiagramSaveRequest(BaseModel):
    revision: str = Field(min_length=1)
    nodes: list[HydraulicDiagramNodeRequest]
    reaches: list[HydraulicDiagramReachRequest] = Field(default_factory=list)
    viewport: HydraulicDiagramViewportRequest = Field(default_factory=HydraulicDiagramViewportRequest)


class TimeSeriesMappingRequest(BaseModel):
    mapping: dict[str, Any]


class TimeSeriesRowsRequest(BaseModel):
    rows: list[dict[str, Any]]


class DraftPromotionError(ValueError):
    pass


def create_app(
    validation_service: JuliaValidationService | None = None,
    *,
    database_url: str | None = None,
    store: AnalystStore | None = None,
    run_queue=None,
    artifact_root: Path | str | None = None,
    input_source_root: Path | str | None = None,
    frontend_dist: Path | str | None = None,
    auth_enabled: bool | None = None,
    session_cookie_name: str = "bess_session",
    csrf_cookie_name: str = "bess_csrf",
    session_hours: int = 12,
    session_cookie_secure: bool | None = None,
) -> FastAPI:
    service = validation_service or JuliaValidationService()
    analyst_store = store or AnalystStore(database_url)
    auth_required = auth_enabled_from_env(False) if auth_enabled is None else bool(auth_enabled)
    configured_artifact_root = Path(
        artifact_root
        or os.environ.get("ARTIFACT_ROOT")
        or Path(__file__).resolve().parents[1] / ".tmp" / "artifacts"
    )
    configured_input_source_root = Path(
        input_source_root
        or os.environ.get("INPUT_SOURCE_ROOT")
        or Path(__file__).resolve().parents[1] / ".tmp" / "input_sources"
    )
    configured_frontend_dist = Path(
        frontend_dist
        or os.environ.get("FRONTEND_DIST")
        or Path(__file__).resolve().parents[1] / "frontend" / "dist"
    )
    local_run_queue = run_queue or LocalRunQueue(
        executor=JuliaRunExecutor(store=analyst_store, artifact_root=configured_artifact_root)
    )
    cookie_secure = (
        cookie_secure_from_env(False)
        if session_cookie_secure is None
        else bool(session_cookie_secure)
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        try:
            yield
        finally:
            if local_run_queue is not None:
                local_run_queue.stop()
            analyst_store.close()

    app = FastAPI(title="BESS Analyst App", lifespan=lifespan)
    app.state.analyst_store = analyst_store
    app.state.auth_enabled = auth_required
    authorization = AuthorizationService(analyst_store)

    def current_user_from_request(request: Request) -> dict[str, Any] | None:
        token = request.cookies.get(session_cookie_name)
        if not token:
            return None
        return authorization.user_for_session_token_hash(hash_session_token(token))

    def public_current_user(user: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": user["id"],
            "email": user["email"],
            "display_name": user["display_name"],
            "role": user["role"],
            "is_active": user["is_active"],
        }

    def react_bookmark_path(request: Request) -> str:
        if request.url.path in {"/login", "/bootstrap"}:
            next_path = safe_internal_next_path(request.query_params.get("next", ""))
            return legacy_path_to_react_path(next_path)
        return legacy_path_to_react_path(request.url.path)

    def react_bookmark_redirect(request: Request, status_code: int = 303) -> RedirectResponse:
        target = react_bookmark_path(request)
        if request.url.query and request.url.path not in {"/login", "/bootstrap"}:
            target = f"{target}?{request.url.query}"
        return RedirectResponse(target, status_code=status_code)

    def auth_redirect(request: Request) -> RedirectResponse:
        return react_bookmark_redirect(request)

    def auth_required_response(request: Request) -> Response:
        if request.url.path.startswith("/api/"):
            return JSONResponse({"detail": "authentication required"}, status_code=401)
        return auth_redirect(request)

    def forbidden_response(request: Request) -> Response:
        if request.url.path.startswith("/api/"):
            return JSONResponse({"detail": "forbidden"}, status_code=403)
        return react_bookmark_redirect(request)

    def require_admin_user(request: Request) -> None:
        if not auth_required:
            return
        try:
            authorization.require_admin(request.state.current_user)
        except PermissionError as error:
            raise HTTPException(status_code=403, detail="forbidden")

    def require_client_project_access(request: Request, project_id: int) -> None:
        if not auth_required:
            return
        try:
            authorization.require_client_project_access(request.state.current_user, project_id)
        except PermissionError as error:
            raise HTTPException(status_code=403, detail="forbidden") from error
        except KeyError as error:
            raise HTTPException(status_code=404, detail="project not found") from error

    def require_client_publication_access(
        request: Request,
        project_id: int,
        publication_id: int,
    ) -> dict[str, Any] | None:
        if not auth_required:
            return None
        try:
            return authorization.require_published_client_publication(
                request.state.current_user,
                project_id=project_id,
                publication_id=publication_id,
            )
        except PermissionError as error:
            raise HTTPException(status_code=403, detail="forbidden") from error
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    def set_session_cookie(response: Response, token: str) -> None:
        response.set_cookie(
            session_cookie_name,
            token,
            max_age=session_hours * 60 * 60,
            httponly=True,
            samesite="lax",
            secure=cookie_secure,
        )

    def set_csrf_cookie(response: Response, token: str) -> None:
        response.set_cookie(
            csrf_cookie_name,
            token,
            max_age=session_hours * 60 * 60,
            httponly=False,
            samesite="lax",
            secure=cookie_secure,
        )

    def authenticated_landing_path(user: dict[str, Any], next_path: str = "") -> str:
        safe_next = safe_internal_next_path(next_path)
        if user["role"] == "client":
            return safe_next if safe_next.startswith("/client") else "/client"
        if safe_next and not safe_next.startswith("/client"):
            return safe_next
        return "/projects"

    def react_authenticated_landing_path(user: dict[str, Any], next_path: str = "") -> str:
        safe_next = safe_react_next_path(next_path)
        if user["role"] == "client":
            return safe_next if safe_next.startswith("/react/client") else "/react/client"
        if safe_next and not safe_next.startswith("/react/client"):
            return safe_next
        return "/react/projects"

    def require_csrf_token(request: Request) -> None:
        expected = request.cookies.get(csrf_cookie_name)
        provided = request.headers.get("x-csrf-token")
        if not expected or not provided or not secrets.compare_digest(expected, provided):
            raise HTTPException(status_code=403, detail="csrf token required")

    def auth_session_response(
        user: dict[str, Any],
        token: str,
        *,
        redirect_path: str,
        status_code: int = 200,
    ) -> JSONResponse:
        response = JSONResponse(
            {
                "user": public_current_user(user),
                "redirect_path": redirect_path,
            },
            status_code=status_code,
        )
        set_session_cookie(response, token)
        return response

    @app.middleware("http")
    async def require_authenticated_app_boundary(request: Request, call_next):
        request.state.current_user = None
        if not auth_required:
            return await call_next(request)

        path = request.url.path
        if path.startswith("/api/auth/"):
            request.state.current_user = current_user_from_request(request)
            if request.method not in {"GET", "HEAD", "OPTIONS"} and path != "/api/auth/csrf":
                try:
                    require_csrf_token(request)
                except HTTPException as error:
                    return JSONResponse({"detail": error.detail}, status_code=error.status_code)
            return await call_next(request)

        if path == "/react" or path.startswith("/react/"):
            request.state.current_user = current_user_from_request(request)
            return await call_next(request)

        if path in {"/favicon.ico", "/login", "/bootstrap", "/logout", "/assets/plotly.min.js"}:
            return await call_next(request)

        user = current_user_from_request(request)
        request.state.current_user = user
        if user is None:
            return auth_required_response(request)

        if path.startswith("/api/") and request.method not in {"GET", "HEAD", "OPTIONS"}:
            try:
                require_csrf_token(request)
            except HTTPException as error:
                return JSONResponse({"detail": error.detail}, status_code=error.status_code)

        if path == "/" or path == "/api/auth/me":
            return await call_next(request)
        if path.startswith("/api/client"):
            try:
                authorization.require_client(user)
            except PermissionError:
                return forbidden_response(request)
            return await call_next(request)
        if path.startswith("/client"):
            try:
                authorization.require_client(user)
            except PermissionError:
                return forbidden_response(request)
            return await call_next(request)
        try:
            authorization.require_internal(user)
        except PermissionError:
            return forbidden_response(request)
        return await call_next(request)

    @app.get("/assets/plotly.min.js", include_in_schema=False)
    async def plotly_javascript_bundle():
        return Response(
            content=cached_plotly_javascript(),
            media_type="application/javascript",
            headers={"Cache-Control": "public, max-age=86400"},
        )

    def save_validated_scenario_version(
        scenario_id: int,
        candidate_text: str,
        generation_metadata: dict[str, Any] | None = None,
    ) -> tuple[dict | None, ValidationResult | None]:
        result = service.validate_text(candidate_text)
        if not result.ok:
            return None, result

        try:
            document = json.loads(candidate_text)
        except json.JSONDecodeError as error:
            return None, ValidationResult(
                ok=False,
                phase="json",
                message=f"Malformed JSON: {error.msg} at line {error.lineno}, column {error.colno}",
                payload={"status": "error", "message": error.msg, "line": error.lineno, "column": error.colno},
            )

        version = analyst_store.create_scenario_version(
            scenario_id=scenario_id,
            system_case_json=document,
            validation_payload=result.payload,
            generation_metadata=generation_metadata,
        )
        return version, None

    def create_and_enqueue_run(scenario_version_id: int) -> dict:
        run = analyst_store.create_run(scenario_version_id=scenario_version_id)
        local_run_queue.enqueue(run["id"])
        return run

    def publication_download_artifacts(
        publication: dict[str, Any],
        artifacts: list[dict[str, Any]],
        url_builder,
    ) -> list[dict[str, Any]]:
        allowed_types = set(publication.get("allowed_artifact_types") or [])
        downloads: list[dict[str, Any]] = []
        for artifact in artifacts:
            artifact_type = artifact["artifact_type"]
            if artifact_type not in allowed_types:
                continue
            if not artifact_path_is_safe(artifact["path"], configured_artifact_root):
                continue
            if not Path(artifact["path"]).is_file():
                continue
            body = publication_download_response_body(artifact)
            body["download_url"] = url_builder(artifact)
            downloads.append(body)
        return downloads

    def get_client_publication_download(project_id: int, publication_id: int, artifact_type: str) -> dict[str, Any]:
        publication = analyst_store.get_publication(publication_id)
        if publication["project_id"] != project_id or publication["status"] != "published":
            raise KeyError(f"publication {publication_id} not found")
        if artifact_type not in set(publication.get("allowed_artifact_types") or []):
            raise KeyError(f"artifact {artifact_type} not found for publication {publication_id}")
        for artifact in analyst_store.list_run_artifacts(publication["run_id"]):
            if artifact["artifact_type"] != artifact_type:
                continue
            if not artifact_path_is_safe(artifact["path"], configured_artifact_root):
                raise KeyError(f"artifact {artifact_type} not found for publication {publication_id}")
            artifact_path = Path(artifact["path"])
            if not artifact_path.is_file():
                raise KeyError(f"artifact {artifact_type} file not found")
            return artifact
        raise KeyError(f"artifact {artifact_type} not found for publication {publication_id}")

    def client_publication_payload(project_id: int, publication_id: int, request: Request) -> dict[str, Any]:
        try:
            project = analyst_store.get_project(project_id)
            publication = require_client_publication_access(request, project_id, publication_id)
            if publication is None:
                publication = analyst_store.get_publication(publication_id)
                if publication["project_id"] != project_id or publication["status"] != "published":
                    raise KeyError(f"publication {publication_id} not found")
            scenario = analyst_store.get_scenario(publication["scenario_id"])
            version = analyst_store.get_scenario_version(
                publication["scenario_version_id"],
                include_document=False,
            )
            run = analyst_store.get_run(publication["run_id"])
            template = analyst_store.get_dashboard_template(publication["dashboard_template_id"])
            artifacts = analyst_store.list_run_artifacts(run["id"])
            downloads = publication_download_artifacts(
                publication,
                artifacts,
                lambda artifact: (
                    f"/api/client/projects/{project_id}/publications/{publication_id}/artifacts/"
                    f"{quote(artifact['artifact_type'], safe='')}/download"
                ),
            )
            results = apply_dashboard_template(
                read_run_results(run, artifacts, configured_artifact_root),
                template,
            )
            results_error = ""
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ResultReadError as error:
            results = None
            results_error = error.message
        return {
            "project": project,
            "scenario": scenario,
            "scenario_version": version,
            "run": run,
            "publication": publication,
            "template": template,
            "results": results,
            "results_error": results_error,
            "downloads": downloads,
        }

    def get_or_create_scenario_draft(scenario_id: int) -> dict:
        try:
            return analyst_store.get_scenario_draft(scenario_id)
        except KeyError:
            draft_document = create_initial_draft_document(analyst_store, scenario_id, None)
            return analyst_store.create_or_replace_scenario_draft(
                scenario_id=scenario_id,
                document=draft_document,
            )

    @app.get("/")
    async def root(request: Request):
        return RedirectResponse("/react", status_code=303)

    @app.get("/favicon.ico")
    async def favicon():
        return Response(status_code=204)

    def react_entry_response() -> FileResponse:
        entry_path = configured_frontend_dist / "index.html"
        if not entry_path.is_file():
            raise HTTPException(status_code=503, detail="React application has not been built")
        return FileResponse(
            entry_path,
            media_type="text/html",
            headers={"Cache-Control": "no-cache"},
        )

    @app.get("/react", include_in_schema=False)
    async def react_entry():
        return react_entry_response()

    @app.get("/react/assets/{asset_path:path}", include_in_schema=False)
    async def react_asset(asset_path: str):
        assets_root = (configured_frontend_dist / "assets").resolve(strict=False)
        candidate = (assets_root / asset_path).resolve(strict=False)
        if not candidate.is_relative_to(assets_root) or not candidate.is_file():
            raise HTTPException(status_code=404, detail="React asset not found")
        return FileResponse(
            candidate,
            headers={"Cache-Control": "public, max-age=31536000, immutable"},
        )

    @app.get("/react/{spa_path:path}", include_in_schema=False)
    async def react_spa_fallback(spa_path: str):
        return react_entry_response()

    @app.get("/login", include_in_schema=False)
    @app.get("/bootstrap", include_in_schema=False)
    @app.get("/logout", include_in_schema=False)
    @app.get("/projects", include_in_schema=False)
    @app.get("/admin/users", include_in_schema=False)
    @app.get("/system-cases/validate", include_in_schema=False)
    async def legacy_static_bookmark(request: Request):
        return react_bookmark_redirect(request)

    @app.get("/projects/{project_id}", include_in_schema=False)
    @app.get("/scenarios/{scenario_id}", include_in_schema=False)
    @app.get("/scenarios/{scenario_id}/draft", include_in_schema=False)
    @app.get("/scenario-versions/{scenario_version_id}", include_in_schema=False)
    @app.get("/runs/{run_id}", include_in_schema=False)
    @app.get("/publications/{publication_id}/preview", include_in_schema=False)
    @app.get("/client", include_in_schema=False)
    @app.get("/client/projects/{project_id}", include_in_schema=False)
    @app.get("/client/projects/{project_id}/publications/{publication_id}", include_in_schema=False)
    async def legacy_dynamic_bookmark(
        request: Request,
        project_id: int | None = None,
        scenario_id: int | None = None,
        scenario_version_id: int | None = None,
        run_id: int | None = None,
        publication_id: int | None = None,
    ):
        return react_bookmark_redirect(request)

    @app.get("/api/auth/csrf", response_model=CsrfTokenResponse)
    async def csrf_token(request: Request):
        token = request.cookies.get(csrf_cookie_name) or secrets.token_urlsafe(32)
        response = JSONResponse({"csrf_token": token})
        set_csrf_cookie(response, token)
        return response

    @app.post("/api/auth/bootstrap", response_model=AuthSessionResponse, status_code=201)
    async def api_bootstrap_first_admin(payload: BootstrapAdminRequest):
        if not auth_required:
            raise HTTPException(status_code=403, detail="authentication is disabled")
        if analyst_store.count_users() > 0:
            raise HTTPException(status_code=403, detail="bootstrap is closed")

        email = payload.email.strip().lower()
        password = payload.password
        display_name = payload.display_name.strip()
        if not email or not password:
            raise HTTPException(status_code=400, detail="email and password are required")

        user = analyst_store.create_user(
            email=email,
            display_name=display_name,
            role="admin",
            password_hash=hash_password(password),
            created_by="bootstrap",
        )
        token = new_session_token()
        analyst_store.create_auth_session(
            user_id=user["id"],
            token_hash=hash_session_token(token),
            expires_at=session_expires_at(hours=session_hours),
        )
        return auth_session_response(
            user,
            token,
            redirect_path=react_authenticated_landing_path(user),
            status_code=201,
        )

    @app.post("/api/auth/login", response_model=AuthSessionResponse)
    async def api_login(payload: LoginRequest):
        if not auth_required:
            raise HTTPException(status_code=403, detail="authentication is disabled")

        email = payload.email.strip().lower()
        user = None
        try:
            user = analyst_store.get_user_by_email(email)
        except KeyError:
            pass

        if user is None or not user["is_active"] or not verify_password(payload.password, user["password_hash"]):
            raise HTTPException(status_code=401, detail="Invalid email or password.")

        token = new_session_token()
        analyst_store.create_auth_session(
            user_id=user["id"],
            token_hash=hash_session_token(token),
            expires_at=session_expires_at(hours=session_hours),
        )
        return auth_session_response(
            user,
            token,
            redirect_path=react_authenticated_landing_path(user, payload.next),
        )

    @app.post("/api/auth/logout", status_code=204)
    async def api_logout(request: Request):
        token = request.cookies.get(session_cookie_name)
        if token:
            analyst_store.revoke_auth_session(hash_session_token(token))
        response = Response(status_code=204)
        response.delete_cookie(session_cookie_name)
        return response

    @app.get("/api/client/projects")
    async def api_client_projects(request: Request):
        user = request.state.current_user
        projects = (
            analyst_store.list_client_projects(user["id"])
            if user is not None
            else analyst_store.list_projects()
        )
        return {"projects": projects}

    @app.get("/api/client/projects/{project_id}/publications")
    async def api_client_project_publications(project_id: int, request: Request):
        require_client_project_access(request, project_id)
        try:
            project = analyst_store.get_project(project_id)
            publications = analyst_store.list_published_project_publications(project_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return {"project": project, "publications": publications}

    @app.get("/api/client/projects/{project_id}/publications/{publication_id}")
    async def api_client_publication_detail(project_id: int, publication_id: int, request: Request):
        return client_publication_payload(project_id, publication_id, request)

    @app.get("/api/client/projects/{project_id}/publications/{publication_id}/artifacts/{artifact_type}/download")
    async def api_download_client_publication_artifact(
        project_id: int,
        publication_id: int,
        artifact_type: str,
        request: Request,
    ):
        require_client_publication_access(request, project_id, publication_id)
        try:
            artifact = get_client_publication_download(project_id, publication_id, artifact_type)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return FileResponse(
            Path(artifact["path"]),
            media_type=artifact["media_type"],
            filename=artifact["display_name"],
        )

    @app.get(
        "/client/projects/{project_id}/publications/{publication_id}/artifacts/{artifact_type}/download",
        include_in_schema=False,
    )
    async def download_client_publication_artifact(
        project_id: int,
        publication_id: int,
        artifact_type: str,
        request: Request,
    ):
        require_client_publication_access(request, project_id, publication_id)
        try:
            artifact = get_client_publication_download(project_id, publication_id, artifact_type)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return FileResponse(
            Path(artifact["path"]),
            media_type=artifact["media_type"],
            filename=artifact["display_name"],
        )

    @app.get("/api/auth/me", response_model=CurrentUserResponse)
    async def current_auth_user(request: Request):
        user = request.state.current_user
        if user is None:
            return {
                "user": None,
                "bootstrap_required": auth_required and analyst_store.count_users() == 0,
            }
        return {
            "user": public_current_user(user),
            "bootstrap_required": False,
        }

    @app.get("/api/admin/users")
    async def admin_list_users(request: Request):
        require_admin_user(request)
        return {"users": [public_user_dict(user) for user in analyst_store.list_users()]}

    @app.post("/api/admin/users", status_code=201)
    async def admin_create_user(request: Request, payload: UserCreateRequest):
        require_admin_user(request)
        email = payload.email.strip().lower()
        password = payload.password
        role = payload.role.strip()
        display_name = payload.display_name.strip()
        if not email or not password:
            raise HTTPException(status_code=400, detail="email and password are required")
        if not is_valid_email(email):
            raise HTTPException(status_code=400, detail="valid email is required")
        if role not in VALID_USER_ROLES:
            raise HTTPException(status_code=400, detail="unsupported user role")
        try:
            analyst_store.get_user_by_email(email)
        except KeyError:
            pass
        else:
            raise HTTPException(status_code=400, detail="email already exists")
        try:
            user = analyst_store.create_user(
                email=email,
                display_name=display_name,
                role=role,
                password_hash=hash_password(password),
                created_by=(request.state.current_user or {}).get("email", "admin"),
            )
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        return {"user": public_user_dict(user)}

    @app.post("/api/admin/users/{user_id}/deactivate")
    async def admin_deactivate_user(user_id: int, request: Request):
        require_admin_user(request)
        try:
            user = analyst_store.set_user_active(
                user_id,
                False,
                updated_by=(request.state.current_user or {}).get("email", "admin"),
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return {"user": public_user_dict(user)}

    @app.get("/api/admin/projects/{project_id}/client-access")
    async def admin_list_project_client_access(project_id: int, request: Request):
        require_admin_user(request)
        try:
            assignments = analyst_store.list_project_client_access(project_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return {"client_access": assignments}

    @app.post("/api/admin/projects/{project_id}/client-access", status_code=201)
    async def admin_assign_project_client(
        project_id: int,
        request: Request,
        payload: ProjectClientAccessRequest,
    ):
        require_admin_user(request)
        try:
            assignment = analyst_store.assign_client_to_project(
                project_id=project_id,
                user_id=payload.user_id,
                assigned_by=(request.state.current_user or {}).get("email", "admin"),
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        return {"client_access": assignment}

    @app.delete("/api/admin/projects/{project_id}/client-access/{user_id}")
    async def admin_remove_project_client_access(project_id: int, user_id: int, request: Request):
        require_admin_user(request)
        try:
            analyst_store.remove_client_project_access(project_id=project_id, user_id=user_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return {"removed": True}

    @app.get("/api/projects/{project_id}/dashboard-templates")
    async def list_dashboard_templates(project_id: int):
        try:
            templates = analyst_store.list_dashboard_templates(project_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return {"dashboard_templates": templates}

    @app.post("/api/projects/{project_id}/dashboard-templates", status_code=201)
    async def create_dashboard_template(
        project_id: int,
        request: Request,
        payload: DashboardTemplateWriteRequest,
    ):
        try:
            template = analyst_store.create_dashboard_template(
                project_id=project_id,
                name=payload.name,
                show_summary=payload.show_summary,
                show_price_chart=payload.show_price_chart,
                show_grid_chart=payload.show_grid_chart,
                show_renewable_chart=payload.show_renewable_chart,
                show_bess_chart=payload.show_bess_chart,
                show_hydro_chart=payload.show_hydro_chart,
                show_profit_chart=payload.show_profit_chart,
                show_system_dispatch_table=payload.show_system_dispatch_table,
                show_asset_dispatch_table=payload.show_asset_dispatch_table,
                table_preview_limit=payload.table_preview_limit,
                created_by=current_user_email(request),
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        return {"dashboard_template": template}

    @app.get("/api/dashboard-templates/{template_id}")
    async def get_dashboard_template(template_id: int):
        try:
            template = analyst_store.get_dashboard_template(template_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return {"dashboard_template": template}

    @app.put("/api/dashboard-templates/{template_id}")
    async def update_dashboard_template(
        template_id: int,
        request: Request,
        payload: DashboardTemplateWriteRequest,
    ):
        try:
            template = analyst_store.update_dashboard_template(
                template_id,
                name=payload.name,
                show_summary=payload.show_summary,
                show_price_chart=payload.show_price_chart,
                show_grid_chart=payload.show_grid_chart,
                show_renewable_chart=payload.show_renewable_chart,
                show_bess_chart=payload.show_bess_chart,
                show_hydro_chart=payload.show_hydro_chart,
                show_profit_chart=payload.show_profit_chart,
                show_system_dispatch_table=payload.show_system_dispatch_table,
                show_asset_dispatch_table=payload.show_asset_dispatch_table,
                table_preview_limit=payload.table_preview_limit,
                updated_by=current_user_email(request),
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        return {"dashboard_template": template}

    @app.get("/api/dashboard-templates/{template_id}/runs/{run_id}/results")
    async def get_dashboard_template_run_results(template_id: int, run_id: int):
        try:
            template = analyst_store.get_dashboard_template(template_id)
            if analyst_store.get_run_project_id(run_id) != template["project_id"]:
                raise KeyError(f"run {run_id} not found for dashboard template {template_id}")
            run = analyst_store.get_run(run_id)
            artifacts = analyst_store.list_run_artifacts(run_id)
            results = read_run_results(run, artifacts, configured_artifact_root)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ResultReadError as error:
            return JSONResponse(
                {"status": "error", "message": error.message},
                status_code=error.status_code,
            )
        return {
            "dashboard": {
                "template": template,
                "results": apply_dashboard_template(results, template),
            }
        }

    @app.post("/api/system-cases/validate")
    async def validate_system_case(payload: SystemCaseValidationRequest):
        result = service.validate_text(payload.system_case_json)
        body = validation_response_body(result)
        if result.ok:
            return body

        return JSONResponse(body, status_code=400)

    @app.post("/api/projects", status_code=201)
    async def create_project(payload: ProjectCreateRequest):
        project = analyst_store.create_project(
            name=payload.name.strip(),
            description=payload.description.strip(),
        )
        return project

    @app.get("/api/projects")
    async def list_projects():
        return {"projects": analyst_store.list_projects()}

    @app.get("/api/projects/{project_id}")
    async def get_project(project_id: int):
        try:
            project = analyst_store.get_project(project_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return {"project": project}

    @app.post("/api/projects/{project_id}/scenarios", status_code=201)
    async def create_scenario(project_id: int, payload: ScenarioCreateRequest):
        try:
            scenario = analyst_store.create_scenario(
                project_id=project_id,
                name=payload.name.strip(),
                description=payload.description.strip(),
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return scenario

    @app.get("/api/projects/{project_id}/scenarios")
    async def list_scenarios(project_id: int):
        try:
            scenarios = analyst_store.list_scenarios(project_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return {"scenarios": scenarios}

    @app.get("/api/scenarios/{scenario_id}")
    async def get_scenario(scenario_id: int):
        try:
            scenario = analyst_store.get_scenario(scenario_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return {"scenario": scenario}

    @app.post("/api/scenarios/{scenario_id}/hydraulic-diagram", status_code=201)
    async def create_hydraulic_diagram(scenario_id: int):
        try:
            diagram = analyst_store.get_or_create_hydraulic_diagram(scenario_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return {"diagram": diagram}

    @app.get("/api/scenarios/{scenario_id}/hydraulic-diagram")
    async def get_hydraulic_diagram(scenario_id: int):
        try:
            diagram = analyst_store.get_hydraulic_diagram(scenario_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return {"diagram": diagram}

    @app.put("/api/scenarios/{scenario_id}/hydraulic-diagram")
    async def save_hydraulic_diagram(scenario_id: int, payload: HydraulicDiagramSaveRequest):
        try:
            diagram = analyst_store.save_hydraulic_diagram(
                scenario_id=scenario_id,
                revision=payload.revision,
                nodes=[node.model_dump() for node in payload.nodes],
                reaches=[reach.model_dump() for reach in payload.reaches],
                viewport=payload.viewport.model_dump(),
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            status_code = 409 if str(error) == "stale hydraulic diagram revision" else 400
            raise HTTPException(status_code=status_code, detail=str(error)) from error
        return {"diagram": diagram}

    @app.post("/api/scenarios/{scenario_id}/hydraulic-diagram/validate")
    async def validate_hydraulic_diagram(scenario_id: int):
        try:
            validation = analyst_store.validate_hydraulic_diagram(scenario_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return {"validation": validation}

    @app.post("/api/scenarios/{scenario_id}/hydraulic-diagram/v3-preview")
    async def validate_hydraulic_v3_preview(scenario_id: int):
        try:
            topology_validation = analyst_store.validate_hydraulic_diagram(scenario_id)
            if not topology_validation["ok"]:
                validation = {
                    **topology_validation,
                    "kind": "hydraulic_topology",
                    "stale": False,
                    "status": "error",
                    "system_case": None,
                }
                return {"validation": validation}
            system_case = analyst_store.generate_hydraulic_v3_preview(scenario_id)
            result = service.validate_text(json.dumps(system_case, sort_keys=True))
            if not result.ok:
                validation = {
                    "kind": "hydraulic_v3_preview",
                    "ok": False,
                    "stale": False,
                    "status": "error",
                    "summary": "Hydraulic v3 payload failed Julia validation",
                    "errors": [
                        {
                            "severity": "error",
                            "code": "julia_v3_validation_failed",
                            "message": result.message,
                            "entity_type": "hydraulic_v3_payload",
                            "entity_id": 0,
                            "technical_key": "bess_system_dispatch.v3",
                        }
                    ],
                    "warnings": [],
                    "system_case": system_case,
                    "julia_validation": result.payload,
                }
                return {"validation": validation}
            validation = analyst_store.persist_hydraulic_v3_validation(
                scenario_id=scenario_id,
                system_case=system_case,
                julia_payload=result.payload,
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        return {"validation": validation}

    @app.post("/api/scenarios/{scenario_id}/hydraulic-diagram/promote", status_code=201)
    async def promote_hydraulic_diagram(scenario_id: int):
        try:
            diagram = analyst_store.get_hydraulic_diagram(scenario_id)
            validation = diagram["validation"]
            if (
                validation.get("kind") != "hydraulic_v3_preview"
                or not validation.get("ok")
                or validation.get("stale")
            ):
                raise DraftPromotionError("hydraulic v3 validation must succeed before promotion")
            system_case = validation.get("system_case")
            if not isinstance(system_case, dict):
                raise DraftPromotionError("hydraulic v3 validation snapshot is missing system_case")
            current_system_case = analyst_store.generate_hydraulic_v3_preview(scenario_id)
            if json.dumps(current_system_case, sort_keys=True) != json.dumps(system_case, sort_keys=True):
                raise DraftPromotionError("hydraulic v3 validation is stale after diagram edits")
            scenario_version, error = save_validated_scenario_version(
                scenario_id,
                json.dumps(system_case, sort_keys=True),
                {
                    "kind": "hydraulic_diagram_v3",
                    "source_case_id": diagram["optimization_case"]["id"],
                    "validation_hash": validation.get("validation_hash"),
                    "generated_at": utc_now_iso(),
                },
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except DraftPromotionError as error:
            return JSONResponse(error_response_body("promotion", str(error), phase="python_validation"), status_code=400)
        if error is not None:
            return JSONResponse(validation_response_body(error), status_code=400)
        analyst_store.persist_scenario_version_hydraulic_diagram_snapshot(
            scenario_version_id=scenario_version["id"],
            layout_snapshot=build_hydraulic_diagram_layout_snapshot(diagram),
            source_case_id=diagram["optimization_case"]["id"],
            layout_key=diagram["layout"]["layout_key"],
        )
        return scenario_version

    @app.post("/api/scenarios/{scenario_id}/draft", status_code=201)
    async def create_scenario_draft(scenario_id: int, payload: ScenarioDraftWriteRequest):
        try:
            draft_document = payload.document
            if draft_document is None:
                draft_document = create_initial_draft_document(
                    analyst_store,
                    scenario_id,
                    payload.source_version_id,
                )
            draft = analyst_store.create_or_replace_scenario_draft(
                scenario_id=scenario_id,
                document=draft_document,
                source_version_id=payload.source_version_id,
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return draft

    @app.get("/api/scenarios/{scenario_id}/draft")
    async def get_scenario_draft(scenario_id: int):
        try:
            draft = analyst_store.get_scenario_draft(scenario_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return {"draft": draft}

    @app.get("/api/scenarios/{scenario_id}/draft/generated-system-case")
    async def get_generated_system_case_preview(scenario_id: int):
        try:
            draft = analyst_store.get_scenario_draft(scenario_id)
            system_case = generate_system_case_from_draft(draft["document"])
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except DraftGenerationError as error:
            return JSONResponse(
                error_response_body(
                    draft_error_category(draft["document"], error),
                    str(error),
                    phase="python_validation",
                ),
                status_code=400,
            )
        return {"system_case": system_case}

    @app.post("/api/scenarios/{scenario_id}/draft/generated-system-case/validate")
    async def validate_generated_system_case(scenario_id: int):
        try:
            draft = analyst_store.get_scenario_draft(scenario_id)
            system_case = generate_system_case_from_draft(draft["document"])
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except DraftGenerationError as error:
            return JSONResponse(
                error_response_body(
                    draft_error_category(draft["document"], error),
                    str(error),
                    phase="python_validation",
                ),
                status_code=400,
            )

        result = service.validate_text(json.dumps(system_case, sort_keys=True))
        updated_document = draft_document_with_generated_validation(
            draft["document"],
            system_case,
            result,
        )
        analyst_store.update_scenario_draft(
            scenario_id=scenario_id,
            document=updated_document,
        )
        body = validation_response_body(result)
        body["system_case"] = system_case
        body["generated_system_case"] = generated_system_case_snapshot(system_case, result)
        if result.ok:
            return body
        return JSONResponse(body, status_code=400)

    @app.post("/api/scenarios/{scenario_id}/draft/generated-system-case/promote", status_code=201)
    async def promote_generated_system_case(scenario_id: int):
        try:
            draft = analyst_store.get_scenario_draft(scenario_id)
            system_case = validated_generated_system_case_from_draft(draft["document"])
            scenario_version, error = save_validated_scenario_version(
                scenario_id,
                json.dumps(system_case, sort_keys=True),
                generation_metadata_from_draft(draft["document"]),
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except (DraftGenerationError, DraftPromotionError) as error:
            category = (
                draft_error_category(draft["document"], error)
                if isinstance(error, DraftGenerationError)
                else "promotion"
            )
            return JSONResponse(error_response_body(category, str(error), phase="python_validation"), status_code=400)
        if error is not None:
            updated_document = draft_document_with_generated_validation(
                draft["document"],
                system_case,
                error,
            )
            analyst_store.update_scenario_draft(
                scenario_id=scenario_id,
                document=updated_document,
            )
            return JSONResponse(validation_response_body(error), status_code=400)
        return scenario_version

    @app.post("/api/scenarios/{scenario_id}/draft/time-series-sources/upload", status_code=201)
    async def upload_draft_time_series_source(
        scenario_id: int,
        source_file: UploadFile = File(...),
        sheet_name: str | None = Form(None),
    ):
        try:
            draft = get_or_create_scenario_draft(scenario_id)
            content = await source_file.read()
            source = ingest_time_series_source(
                draft_document=draft["document"],
                original_filename=source_file.filename or "source.csv",
                content_type=source_file.content_type,
                content=content,
                input_source_root=configured_input_source_root,
                sheet_name=sheet_name,
            )
            updated_document = attach_time_series_source(draft["document"], source)
            analyst_store.update_scenario_draft(
                scenario_id=scenario_id,
                document=updated_document,
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except TimeSeriesIngestionError as error:
            return JSONResponse(error_response_body("source_file", str(error)), status_code=400)
        finally:
            await source_file.close()
        return {"source": source}

    @app.get("/api/scenarios/{scenario_id}/draft/time-series-sources/{source_id}/rows")
    async def get_draft_time_series_rows(scenario_id: int, source_id: str):
        try:
            draft = analyst_store.get_scenario_draft(scenario_id)
            columns, rows = get_time_series_source_rows(
                document=draft["document"],
                source_id=source_id,
                input_source_root=configured_input_source_root,
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except TimeSeriesIngestionError as error:
            return JSONResponse(error_response_body("source_file", str(error)), status_code=400)
        return {"columns": columns, "rows": rows}

    @app.put("/api/scenarios/{scenario_id}/draft/time-series-sources/{source_id}/rows")
    async def save_draft_time_series_rows(
        scenario_id: int,
        source_id: str,
        payload: TimeSeriesRowsRequest,
    ):
        try:
            draft = analyst_store.get_scenario_draft(scenario_id)
            updated_document, source = update_time_series_source_rows(
                document=draft["document"],
                source_id=source_id,
                rows=payload.rows,
                input_source_root=configured_input_source_root,
            )
            analyst_store.update_scenario_draft(
                scenario_id=scenario_id,
                document=updated_document,
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except TimeSeriesIngestionError as error:
            return JSONResponse(error_response_body("source_file", str(error)), status_code=400)
        return {"source": source}

    @app.put("/api/scenarios/{scenario_id}/draft/time-series-sources/{source_id}/mapping")
    async def save_draft_time_series_mapping(
        scenario_id: int,
        source_id: str,
        payload: TimeSeriesMappingRequest,
    ):
        try:
            draft = analyst_store.get_scenario_draft(scenario_id)
            updated_document, source = apply_time_series_mapping(
                document=draft["document"],
                source_id=source_id,
                mapping=payload.mapping,
                input_source_root=configured_input_source_root,
            )
            analyst_store.update_scenario_draft(
                scenario_id=scenario_id,
                document=updated_document,
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except TimeSeriesIngestionError as error:
            return JSONResponse(error_response_body("source_file", str(error)), status_code=400)
        return {"source": source}

    @app.put("/api/scenarios/{scenario_id}/draft")
    async def update_scenario_draft(scenario_id: int, payload: ScenarioDraftWriteRequest):
        if payload.document is None:
            raise HTTPException(status_code=400, detail="draft document is required")
        try:
            draft = analyst_store.update_scenario_draft(
                scenario_id=scenario_id,
                document=payload.document,
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return draft

    @app.post("/api/scenarios/{scenario_id}/versions", status_code=201)
    async def create_scenario_version(scenario_id: int, payload: ScenarioVersionCreateRequest):
        try:
            scenario_version, error = save_validated_scenario_version(scenario_id, payload.system_case_json)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        if error is not None:
            return JSONResponse(validation_response_body(error), status_code=400)
        return scenario_version

    @app.post("/api/scenarios/{scenario_id}/versions/upload", status_code=201)
    async def upload_scenario_version(scenario_id: int, system_case_file: UploadFile = File(...)):
        try:
            candidate_text = (await system_case_file.read()).decode("utf-8")
        except UnicodeDecodeError:
            error = ValidationResult(
                ok=False,
                phase="json",
                message="Uploaded file must be UTF-8 encoded JSON",
                payload={"status": "error"},
            )
            return JSONResponse(validation_response_body(error), status_code=400)
        finally:
            await system_case_file.close()
        try:
            scenario_version, error = save_validated_scenario_version(scenario_id, candidate_text)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        if error is not None:
            return JSONResponse(validation_response_body(error), status_code=400)
        return scenario_version

    @app.get("/api/scenarios/{scenario_id}/versions")
    async def list_scenario_versions(scenario_id: int):
        try:
            versions = analyst_store.list_scenario_versions(scenario_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return {"versions": versions}

    @app.get("/api/scenarios/{scenario_id}/runs")
    async def list_scenario_runs(scenario_id: int):
        try:
            runs = analyst_store.list_scenario_runs(scenario_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return {"runs": runs}

    @app.get("/api/scenario-versions/{scenario_version_id}")
    async def get_scenario_version(scenario_version_id: int):
        try:
            scenario_version = analyst_store.get_scenario_version(scenario_version_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return {"scenario_version": scenario_version}

    @app.get("/api/scenario-versions/{scenario_version_id}/hydraulic-diagram-snapshot")
    async def get_scenario_version_hydraulic_diagram_snapshot(scenario_version_id: int):
        try:
            snapshot = analyst_store.get_scenario_version_hydraulic_diagram_snapshot(
                scenario_version_id
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return {"snapshot": snapshot}

    @app.delete("/api/scenario-versions/{scenario_version_id}")
    async def delete_scenario_version(scenario_version_id: int):
        try:
            deleted_version = analyst_store.delete_scenario_version(scenario_version_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return {"deleted_version": deleted_version}

    @app.post("/api/scenario-versions/{scenario_version_id}/runs", status_code=201)
    async def create_manual_run(scenario_version_id: int):
        try:
            run = create_and_enqueue_run(scenario_version_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return run

    @app.get("/api/runs/{run_id}")
    async def get_run(run_id: int):
        try:
            run = analyst_store.get_run(run_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return {"run": run}

    @app.get("/api/runs/{run_id}/results")
    async def get_run_results(run_id: int):
        try:
            run = analyst_store.get_run(run_id)
            artifacts = analyst_store.list_run_artifacts(run_id)
            results = read_run_results(run, artifacts, configured_artifact_root)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ResultReadError as error:
            return JSONResponse(
                {"status": "error", "message": error.message},
                status_code=error.status_code,
            )
        return {"results": results}

    @app.get("/api/runs/{run_id}/publications")
    async def list_run_publications(run_id: int):
        try:
            publications = analyst_store.list_run_publications(run_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return {"publications": publications}

    @app.get("/api/publications/{publication_id}/preview")
    async def get_publication_preview(publication_id: int):
        try:
            publication = analyst_store.get_publication(publication_id)
            project = analyst_store.get_project(publication["project_id"])
            scenario = analyst_store.get_scenario(publication["scenario_id"])
            version = analyst_store.get_scenario_version(
                publication["scenario_version_id"],
                include_document=False,
            )
            run = analyst_store.get_run(publication["run_id"])
            template = analyst_store.get_dashboard_template(
                publication["dashboard_template_id"]
            )
            artifacts = analyst_store.list_run_artifacts(run["id"])
            downloads = publication_download_artifacts(
                publication,
                artifacts,
                lambda artifact: f"/api/run-artifacts/{artifact['id']}/download",
            )
            results = apply_dashboard_template(
                read_run_results(run, artifacts, configured_artifact_root),
                template,
            )
            results_error = ""
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ResultReadError as error:
            results = None
            results_error = error.message
        return {
            "project": project,
            "scenario": scenario,
            "scenario_version": version,
            "run": run,
            "publication": publication,
            "template": template,
            "results": results,
            "results_error": results_error,
            "downloads": downloads,
        }

    @app.post("/api/runs/{run_id}/publications", status_code=201)
    async def create_run_publication_draft(
        run_id: int,
        request: Request,
        payload: PublicationDraftWriteRequest,
    ):
        try:
            publication = analyst_store.create_publication_draft(
                run_id=run_id,
                dashboard_template_id=payload.dashboard_template_id,
                public_title=payload.public_title,
                analyst_notes=payload.analyst_notes,
                allowed_artifact_types=payload.allowed_artifact_types,
                created_by=current_user_email(request),
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        return {"publication": publication}

    @app.put("/api/publications/{publication_id}")
    async def update_publication_draft(
        publication_id: int,
        request: Request,
        payload: PublicationDraftWriteRequest,
    ):
        try:
            publication = analyst_store.update_publication_draft(
                publication_id,
                dashboard_template_id=payload.dashboard_template_id,
                public_title=payload.public_title,
                analyst_notes=payload.analyst_notes,
                allowed_artifact_types=payload.allowed_artifact_types,
                updated_by=current_user_email(request),
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        return {"publication": publication}

    @app.post("/api/publications/{publication_id}/publish")
    async def publish_publication(publication_id: int, request: Request):
        try:
            publication = analyst_store.publish_publication(
                publication_id,
                published_by=current_user_email(request),
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        return {"publication": publication}

    @app.post("/api/publications/{publication_id}/unpublish")
    async def unpublish_publication(publication_id: int, request: Request):
        try:
            publication = analyst_store.unpublish_publication(
                publication_id,
                unpublished_by=current_user_email(request),
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        return {"publication": publication}

    @app.get("/api/runs/{run_id}/artifacts")
    async def list_run_artifacts(run_id: int):
        try:
            artifacts = analyst_store.list_run_artifacts(run_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return {
            "artifacts": [
                artifact_response_body(artifact)
                for artifact in artifacts
                if artifact_path_is_safe(artifact["path"], configured_artifact_root)
            ]
        }

    @app.get("/api/run-artifacts/{artifact_id}/download")
    async def download_run_artifact(artifact_id: int):
        try:
            artifact = analyst_store.get_run_artifact(artifact_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        if not artifact_path_is_safe(artifact["path"], configured_artifact_root):
            raise HTTPException(status_code=404, detail="artifact not found")

        artifact_path = Path(artifact["path"])
        if not artifact_path.is_file():
            raise HTTPException(status_code=404, detail="artifact file not found")

        return FileResponse(
            artifact_path,
            media_type=artifact["media_type"],
            filename=artifact["display_name"],
        )

    return app


def validation_response_body(result: ValidationResult) -> dict:
    if result.ok:
        return {
            "status": "ok",
            "phase": result.phase,
            "message": result.message,
            "validation": result.payload,
        }

    return {
        "status": "error",
        "phase": result.phase,
        "error_category": validation_error_category(result),
        "message": result.message,
        "validation": result.payload,
    }


def validation_error_category(result: ValidationResult) -> str:
    if result.phase == "julia":
        return "julia_validation"
    return result.phase or "validation"


def error_response_body(error_category: str, detail: str, *, phase: str | None = None) -> dict:
    return {
        "status": "error",
        "phase": phase or error_category,
        "error_category": error_category,
        "detail": detail,
    }


def draft_error_category(document: dict[str, Any], error: Exception) -> str:
    source_category = active_source_validation_category(document)
    if source_category:
        return source_category
    message = str(error)
    if message.startswith("Python time-series validation failed"):
        return "python_validation"
    return "python_validation"


def active_source_validation_category(document: dict[str, Any]) -> str:
    active_source = active_time_series_source(document)
    validation = active_source.get("validation") if isinstance(active_source, dict) else None
    if not isinstance(validation, dict):
        return ""
    category = validation.get("error_category")
    return str(category) if category else ""


def generation_metadata_from_draft(document: dict[str, Any]) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "kind": "structured_draft",
        "generated_at": utc_now_iso(),
    }
    source = active_time_series_source(document)
    if not isinstance(source, dict):
        return metadata

    source_metadata: dict[str, Any] = {
        "source_id": str(source.get("id") or ""),
        "kind": str(source.get("kind") or ""),
        "original_filename": str(source.get("original_filename") or ""),
        "media_type": str(source.get("media_type") or ""),
    }
    stored_path = source.get("stored_path")
    if stored_path:
        source_metadata["stored_filename"] = Path(str(stored_path)).name
    if source.get("selected_sheet"):
        source_metadata["selected_sheet"] = str(source.get("selected_sheet"))

    mapping = source.get("mapping") if isinstance(source.get("mapping"), dict) else {}
    metadata["source"] = source_metadata
    metadata["mapping"] = copy.deepcopy(mapping)
    return metadata


def active_time_series_source(document: dict[str, Any]) -> dict[str, Any] | None:
    time_series = document.get("time_series")
    if not isinstance(time_series, dict):
        return None
    sources = time_series.get("sources")
    if not isinstance(sources, list):
        return None
    active_source_id = time_series.get("active_source_id")
    active_source = None
    for source in sources:
        if isinstance(source, dict) and source.get("id") == active_source_id:
            active_source = source
            break
    if active_source is None:
        for source in sources:
            if isinstance(source, dict):
                active_source = source
                break
    return active_source


def draft_document_with_generated_validation(
    document: dict[str, Any],
    system_case: dict[str, Any],
    result: ValidationResult,
) -> dict[str, Any]:
    updated = copy.deepcopy(document)
    updated["generated_system_case"] = generated_system_case_snapshot(system_case, result)
    return updated


def generated_system_case_snapshot(system_case: dict[str, Any], result: ValidationResult) -> dict[str, Any]:
    validation = {
        "ok": result.ok,
        "phase": result.phase,
        "message": result.message,
        "payload": copy.deepcopy(result.payload),
    }
    if not result.ok:
        validation["error_category"] = validation_error_category(result)
    return {
        "system_case": copy.deepcopy(system_case),
        "validation": validation,
    }


def validated_generated_system_case_from_draft(document: dict[str, Any]) -> dict[str, Any]:
    system_case = generate_system_case_from_draft(document)
    if draft_has_current_successful_generated_validation(document, system_case):
        return system_case

    snapshot = document.get("generated_system_case")
    if not isinstance(snapshot, dict):
        raise DraftPromotionError("generated system case must be validated before promotion")

    validation = snapshot.get("validation")
    if not isinstance(validation, dict) or not validation.get("ok"):
        raise DraftPromotionError("generated system case validation must succeed before promotion")

    raise DraftPromotionError("generated system case validation is stale; validate again before promotion")


def draft_has_current_successful_generated_validation(
    document: dict[str, Any],
    system_case: dict[str, Any],
) -> bool:
    snapshot = document.get("generated_system_case")
    if not isinstance(snapshot, dict):
        return False
    validation = snapshot.get("validation")
    if not isinstance(validation, dict) or not validation.get("ok"):
        return False
    return snapshot.get("system_case") == system_case


def artifact_response_body(artifact: dict) -> dict:
    return {
        "id": artifact["id"],
        "run_id": artifact["run_id"],
        "artifact_type": artifact["artifact_type"],
        "path": artifact["path"],
        "display_name": artifact["display_name"],
        "media_type": artifact["media_type"],
        "byte_size": artifact["byte_size"],
        "created_at": artifact["created_at"],
        "download_url": f"/api/run-artifacts/{artifact['id']}/download",
    }


def publication_download_response_body(artifact: dict) -> dict:
    return {
        "artifact_type": artifact["artifact_type"],
        "display_name": artifact["display_name"],
        "media_type": artifact["media_type"],
        "byte_size": artifact["byte_size"],
    }


def artifact_path_is_safe(path: str, artifact_root: Path) -> bool:
    root = artifact_root.resolve(strict=False)
    resolved_path = Path(path).resolve(strict=False)
    try:
        resolved_path.relative_to(root)
    except ValueError:
        return False
    return True


def create_initial_draft_document(
    analyst_store: AnalystStore,
    scenario_id: int,
    source_version_id: int | None,
) -> dict[str, Any]:
    if source_version_id is None:
        scenario = analyst_store.get_scenario(scenario_id)
        return empty_scenario_draft_document(scenario["name"])

    source_version = analyst_store.get_scenario_version(source_version_id)
    if source_version["scenario_id"] != scenario_id:
        raise KeyError(f"scenario version {source_version_id} not found for scenario {scenario_id}")
    return scenario_draft_document_from_version(source_version)


def empty_scenario_draft_document(case_name: str) -> dict[str, Any]:
    return {
        "schema_version": "bess_editor_draft.v1",
        "case": {"name": case_name},
        "source": None,
        "pcc": {"id": "bus_1", "type": "bus"},
        "grid": {
            "id": "grid_1",
            "import_power_max_mw": None,
            "export_power_max_mw": None,
            "prevent_simultaneous_grid_import_export": True,
        },
        "assets": [],
        "time_series": {"sources": []},
        "solver": {"name": "HiGHS", "options": {}},
    }


def scenario_draft_document_from_version(source_version: dict[str, Any]) -> dict[str, Any]:
    system_case = source_version["system_case_json"]
    return structured_draft_document_from_system_case(
        system_case,
        source={
            "kind": "scenario_version",
            "scenario_version_id": source_version["id"],
            "version_number": source_version["version_number"],
        },
    )


def legacy_path_to_react_path(path: str) -> str:
    safe_path = safe_internal_next_path(path)
    if not safe_path or safe_path == "/":
        return "/react"
    if safe_path == "/system-cases/validate":
        return "/react/system"
    if safe_path in {"/login", "/bootstrap", "/logout"}:
        return "/react"
    if safe_path == "/react" or safe_path.startswith("/react/"):
        return safe_path
    return f"/react{safe_path}"


def current_user_email(request: Request) -> str:
    user = getattr(request.state, "current_user", None)
    if isinstance(user, dict) and user.get("email"):
        return str(user["email"])
    return "internal_analyst"


def auth_enabled_from_env(default: bool) -> bool:
    raw_value = os.environ.get("BESS_AUTH_ENABLED")
    if raw_value is None:
        return default
    return raw_value.strip().lower() not in {"0", "false", "no", "off"}


def cookie_secure_from_env(default: bool) -> bool:
    raw_value = os.environ.get("BESS_SESSION_COOKIE_SECURE")
    if raw_value is None:
        return default
    return raw_value.strip().lower() not in {"0", "false", "no", "off"}


def safe_internal_next_path(next_path: str) -> str:
    if not next_path:
        return ""
    if not next_path.startswith("/") or next_path.startswith("//"):
        return ""
    return next_path


def safe_react_next_path(next_path: str) -> str:
    safe_next = safe_internal_next_path(next_path)
    if not safe_next:
        return ""
    if safe_next in {"/react/login", "/react/bootstrap", "/react/logout"}:
        return ""
    if safe_next == "/react" or safe_next.startswith("/react/"):
        return safe_next
    return ""


def public_user_dict(user: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": user["id"],
        "email": user["email"],
        "display_name": user["display_name"],
        "role": user["role"],
        "is_active": user["is_active"],
        "created_at": user["created_at"],
        "updated_at": user["updated_at"],
    }


def is_valid_email(value: str) -> bool:
    return "@" in value and "." in value.rsplit("@", 1)[-1]


@lru_cache(maxsize=1)
def cached_plotly_javascript() -> str:
    return get_plotlyjs()


app = create_app(auth_enabled=auth_enabled_from_env(True))

