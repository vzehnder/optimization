from __future__ import annotations

import copy
import json
import os
import secrets
from contextlib import asynccontextmanager
from functools import lru_cache
from html import escape
from pathlib import Path
from typing import Any, Literal
from urllib.parse import quote

from fastapi import FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
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
    SUPPORTED_ASSET_TYPES,
    add_asset_to_draft,
    generate_system_case_from_draft,
    remove_asset_from_draft,
    structured_draft_document_from_system_case,
    structured_draft_document_from_form,
)
from app.persistence import AnalystStore, DEFAULT_PUBLICATION_ARTIFACT_TYPES, utc_now_iso
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

    def auth_redirect(request: Request) -> RedirectResponse:
        target = request.url.path
        if request.url.query:
            target = f"{target}?{request.url.query}"
        return RedirectResponse(f"/login?next={quote(target, safe='/')}", status_code=303)

    def auth_required_response(request: Request) -> Response:
        if request.url.path.startswith("/api/"):
            return JSONResponse({"detail": "authentication required"}, status_code=401)
        return auth_redirect(request)

    def forbidden_response(request: Request) -> Response:
        if request.url.path.startswith("/api/"):
            return JSONResponse({"detail": "forbidden"}, status_code=403)
        return HTMLResponse(render_forbidden_page(), status_code=403)

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
            if analyst_store.count_users() == 0 and not path.startswith("/api/"):
                return RedirectResponse("/bootstrap", status_code=303)
            return auth_required_response(request)

        if path.startswith("/api/") and request.method not in {"GET", "HEAD", "OPTIONS"}:
            try:
                require_csrf_token(request)
            except HTTPException as error:
                return JSONResponse({"detail": error.detail}, status_code=error.status_code)

        if path == "/" or path == "/api/auth/me":
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
            body = artifact_response_body(artifact)
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
        if auth_required:
            user = request.state.current_user
            if user is not None and user["role"] == "client":
                return RedirectResponse("/client")
        return RedirectResponse("/projects")

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

    @app.get("/bootstrap", response_class=HTMLResponse)
    async def bootstrap_page():
        if auth_required and analyst_store.count_users() > 0:
            return RedirectResponse("/login", status_code=303)
        return HTMLResponse(render_bootstrap_page())

    @app.post("/bootstrap")
    async def bootstrap_first_admin(request: Request):
        if not auth_required:
            return RedirectResponse("/projects", status_code=303)
        if analyst_store.count_users() > 0:
            return HTMLResponse(render_forbidden_page("Bootstrap is closed after the first user exists."), status_code=403)

        form = await request.form()
        email = str(form.get("email", "")).strip().lower()
        password = str(form.get("password", ""))
        display_name = str(form.get("display_name", "")).strip()
        if not email or not password:
            return HTMLResponse(render_bootstrap_page("Email and password are required."), status_code=400)

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
        response = RedirectResponse("/projects", status_code=303)
        set_session_cookie(response, token)
        return response

    @app.get("/login", response_class=HTMLResponse)
    async def login_page(request: Request, next: str = ""):
        if auth_required:
            user = current_user_from_request(request)
            if user is not None:
                return RedirectResponse(authenticated_landing_path(user, next), status_code=303)
        return HTMLResponse(render_login_page(next_path=next))

    @app.post("/login")
    async def login(request: Request):
        if not auth_required:
            return RedirectResponse("/projects", status_code=303)

        form = await request.form()
        email = str(form.get("email", "")).strip().lower()
        password = str(form.get("password", ""))
        next_path = str(form.get("next", ""))
        user = None
        try:
            user = analyst_store.get_user_by_email(email)
        except KeyError:
            pass

        if user is None or not user["is_active"] or not verify_password(password, user["password_hash"]):
            return HTMLResponse(
                render_login_page("Invalid email or password.", next_path=next_path, email=email),
                status_code=401,
            )

        token = new_session_token()
        analyst_store.create_auth_session(
            user_id=user["id"],
            token_hash=hash_session_token(token),
            expires_at=session_expires_at(hours=session_hours),
        )
        response = RedirectResponse(authenticated_landing_path(user, next_path), status_code=303)
        set_session_cookie(response, token)
        return response

    @app.post("/logout")
    async def logout(request: Request):
        token = request.cookies.get(session_cookie_name)
        if token:
            analyst_store.revoke_auth_session(hash_session_token(token))
        response = RedirectResponse("/login", status_code=303)
        response.delete_cookie(session_cookie_name)
        return response

    @app.get("/client", response_class=HTMLResponse)
    async def client_home(request: Request):
        user = request.state.current_user
        projects = analyst_store.list_client_projects(user["id"])
        return HTMLResponse(render_client_home_page(user, projects))

    @app.get("/client/projects/{project_id}", response_class=HTMLResponse)
    async def client_project_detail(project_id: int, request: Request):
        require_client_project_access(request, project_id)
        try:
            project = analyst_store.get_project(project_id)
            publications = analyst_store.list_published_project_publications(project_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return HTMLResponse(render_client_project_page(project, publications))

    @app.get("/client/projects/{project_id}/publications/{publication_id}", response_class=HTMLResponse)
    async def client_publication_detail(project_id: int, publication_id: int, request: Request):
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
                    f"/client/projects/{project_id}/publications/{publication_id}/artifacts/"
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
        return HTMLResponse(
            render_client_publication_page(
                project,
                scenario,
                version,
                run,
                publication,
                results,
                results_error,
                downloads,
            )
        )

    @app.get("/client/projects/{project_id}/publications/{publication_id}/artifacts/{artifact_type}/download")
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

    @app.get("/admin/users", response_class=HTMLResponse)
    async def admin_users_page(request: Request):
        require_admin_user(request)
        return HTMLResponse(render_admin_users_page(analyst_store.list_users()))

    @app.post("/admin/users")
    async def admin_create_user_from_page(request: Request):
        require_admin_user(request)
        form = await request.form()
        email = str(form.get("email", "")).strip().lower()
        password = str(form.get("password", ""))
        role = str(form.get("role", "")).strip()
        if not email or not password:
            return HTMLResponse(
                render_admin_users_page(analyst_store.list_users(), "Email and password are required."),
                status_code=400,
            )
        if role not in VALID_USER_ROLES:
            return HTMLResponse(
                render_admin_users_page(analyst_store.list_users(), "Unsupported user role."),
                status_code=400,
            )
        try:
            analyst_store.create_user(
                email=email,
                display_name=str(form.get("display_name", "")).strip(),
                role=role,
                password_hash=hash_password(password),
                created_by=(request.state.current_user or {}).get("email", "admin"),
            )
        except ValueError as error:
            return HTMLResponse(render_admin_users_page(analyst_store.list_users(), str(error)), status_code=400)
        return RedirectResponse("/admin/users", status_code=303)

    @app.post("/admin/users/{user_id}/deactivate")
    async def admin_deactivate_user_from_page(user_id: int, request: Request):
        require_admin_user(request)
        try:
            analyst_store.set_user_active(
                user_id,
                False,
                updated_by=(request.state.current_user or {}).get("email", "admin"),
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return RedirectResponse("/admin/users", status_code=303)

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
        if role not in VALID_USER_ROLES:
            raise HTTPException(status_code=400, detail="unsupported user role")
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

    @app.get("/projects", response_class=HTMLResponse)
    async def projects_page():
        return HTMLResponse(render_projects_page(analyst_store.list_projects()))

    @app.post("/projects")
    async def create_project_from_page(request: Request):
        form = await request.form()
        project = analyst_store.create_project(
            name=str(form.get("name", "")).strip(),
            description=str(form.get("description", "")).strip(),
        )
        return RedirectResponse(f"/projects/{project['id']}", status_code=303)

    @app.get("/projects/{project_id}", response_class=HTMLResponse)
    async def project_page(project_id: int, request: Request):
        try:
            project = analyst_store.get_project(project_id)
            scenarios = analyst_store.list_scenarios(project_id)
            client_access = analyst_store.list_project_client_access(project_id)
            dashboard_templates = analyst_store.list_dashboard_templates(project_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        client_users = [user for user in analyst_store.list_users() if user["role"] == "client"]
        can_manage_access = bool(auth_required and request.state.current_user and request.state.current_user["role"] == "admin")
        return HTMLResponse(
            render_project_page(
                project,
                scenarios,
                dashboard_templates,
                client_access,
                client_users,
                can_manage_access,
            )
        )

    @app.post("/projects/{project_id}/dashboard-templates")
    async def create_dashboard_template_from_page(project_id: int, request: Request):
        form = await request.form()
        try:
            analyst_store.create_dashboard_template(
                project_id=project_id,
                name=str(form.get("name", "")).strip(),
                show_summary=form_checkbox(form, "show_summary"),
                show_price_chart=form_checkbox(form, "show_price_chart"),
                show_grid_chart=form_checkbox(form, "show_grid_chart"),
                show_renewable_chart=form_checkbox(form, "show_renewable_chart"),
                show_bess_chart=form_checkbox(form, "show_bess_chart"),
                show_hydro_chart=form_checkbox(form, "show_hydro_chart"),
                show_profit_chart=form_checkbox(form, "show_profit_chart"),
                show_system_dispatch_table=form_checkbox(form, "show_system_dispatch_table"),
                show_asset_dispatch_table=form_checkbox(form, "show_asset_dispatch_table"),
                table_preview_limit=int(str(form.get("table_preview_limit", "10"))),
                created_by=current_user_email(request),
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except (TypeError, ValueError) as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        return RedirectResponse(f"/projects/{project_id}", status_code=303)

    @app.post("/dashboard-templates/{template_id}")
    async def update_dashboard_template_from_page(template_id: int, request: Request):
        form = await request.form()
        try:
            existing = analyst_store.get_dashboard_template(template_id)
            analyst_store.update_dashboard_template(
                template_id,
                name=str(form.get("name", "")).strip(),
                show_summary=form_checkbox(form, "show_summary"),
                show_price_chart=form_checkbox(form, "show_price_chart"),
                show_grid_chart=form_checkbox(form, "show_grid_chart"),
                show_renewable_chart=form_checkbox(form, "show_renewable_chart"),
                show_bess_chart=form_checkbox(form, "show_bess_chart"),
                show_hydro_chart=form_checkbox(form, "show_hydro_chart"),
                show_profit_chart=form_checkbox(form, "show_profit_chart"),
                show_system_dispatch_table=form_checkbox(form, "show_system_dispatch_table"),
                show_asset_dispatch_table=form_checkbox(form, "show_asset_dispatch_table"),
                table_preview_limit=int(str(form.get("table_preview_limit", "10"))),
                updated_by=current_user_email(request),
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except (TypeError, ValueError) as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        return RedirectResponse(f"/projects/{existing['project_id']}", status_code=303)

    @app.post("/runs/{run_id}/publications")
    async def create_publication_draft_from_page(run_id: int, request: Request):
        form = await request.form()
        try:
            analyst_store.create_publication_draft(
                run_id=run_id,
                dashboard_template_id=int(str(form.get("dashboard_template_id", "0"))),
                public_title=str(form.get("public_title", "")).strip(),
                analyst_notes=str(form.get("analyst_notes", "")).strip(),
                allowed_artifact_types=form.getlist("allowed_artifact_types"),
                created_by=current_user_email(request),
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except (TypeError, ValueError) as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        return RedirectResponse(f"/runs/{run_id}", status_code=303)

    @app.post("/publications/{publication_id}")
    async def update_publication_draft_from_page(publication_id: int, request: Request):
        form = await request.form()
        try:
            publication = analyst_store.update_publication_draft(
                publication_id,
                dashboard_template_id=int(str(form.get("dashboard_template_id", "0"))),
                public_title=str(form.get("public_title", "")).strip(),
                analyst_notes=str(form.get("analyst_notes", "")).strip(),
                allowed_artifact_types=form.getlist("allowed_artifact_types"),
                updated_by=current_user_email(request),
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except (TypeError, ValueError) as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        return RedirectResponse(f"/runs/{publication['run_id']}", status_code=303)

    @app.get("/publications/{publication_id}/preview", response_class=HTMLResponse)
    async def preview_publication_as_client(publication_id: int):
        try:
            publication = analyst_store.get_publication(publication_id)
            project = analyst_store.get_project(publication["project_id"])
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
        return HTMLResponse(
            render_client_publication_page(
                project,
                scenario,
                version,
                run,
                publication,
                results,
                results_error,
                downloads,
            )
        )

    @app.post("/publications/{publication_id}/publish")
    async def publish_publication_from_page(publication_id: int, request: Request):
        try:
            publication = analyst_store.publish_publication(
                publication_id,
                published_by=current_user_email(request),
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        return RedirectResponse(f"/runs/{publication['run_id']}", status_code=303)

    @app.post("/publications/{publication_id}/unpublish")
    async def unpublish_publication_from_page(publication_id: int, request: Request):
        try:
            publication = analyst_store.unpublish_publication(
                publication_id,
                unpublished_by=current_user_email(request),
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        return RedirectResponse(f"/runs/{publication['run_id']}", status_code=303)

    @app.post("/projects/{project_id}/client-access")
    async def assign_client_access_from_page(project_id: int, request: Request):
        require_admin_user(request)
        form = await request.form()
        try:
            analyst_store.assign_client_to_project(
                project_id=project_id,
                user_id=int(str(form.get("user_id", "0"))),
                assigned_by=(request.state.current_user or {}).get("email", "admin"),
            )
        except (KeyError, ValueError) as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        return RedirectResponse(f"/projects/{project_id}", status_code=303)

    @app.post("/projects/{project_id}/client-access/{user_id}/remove")
    async def remove_client_access_from_page(project_id: int, user_id: int, request: Request):
        require_admin_user(request)
        try:
            analyst_store.remove_client_project_access(project_id=project_id, user_id=user_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return RedirectResponse(f"/projects/{project_id}", status_code=303)

    @app.post("/projects/{project_id}/scenarios")
    async def create_scenario_from_page(project_id: int, request: Request):
        form = await request.form()
        try:
            scenario = analyst_store.create_scenario(
                project_id=project_id,
                name=str(form.get("name", "")).strip(),
                description=str(form.get("description", "")).strip(),
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return RedirectResponse(f"/scenarios/{scenario['id']}", status_code=303)

    @app.get("/scenarios/{scenario_id}/draft", response_class=HTMLResponse)
    async def scenario_draft_page(scenario_id: int, source_version_id: int | None = None):
        try:
            scenario = analyst_store.get_scenario(scenario_id)
            draft = None
            if source_version_id is None:
                try:
                    draft = analyst_store.get_scenario_draft(scenario_id)
                    draft_document = draft["document"]
                except KeyError:
                    draft_document = create_initial_draft_document(analyst_store, scenario_id, None)
            else:
                draft_document = create_initial_draft_document(analyst_store, scenario_id, source_version_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return HTMLResponse(
            render_scenario_draft_page(
                scenario,
                draft,
                draft_document,
                source_version_id=source_version_id,
            )
        )

    @app.post("/scenarios/{scenario_id}/draft")
    async def save_scenario_draft_from_page(scenario_id: int, request: Request):
        form = await request.form()
        candidate_text = str(form.get("structured_draft_json", ""))
        source_version_text = str(form.get("source_version_id", "")).strip()
        source_version_id = int(source_version_text) if source_version_text else None
        try:
            draft_document = json.loads(candidate_text)
            if not isinstance(draft_document, dict):
                raise ValueError("Draft JSON must be an object")
            analyst_store.create_or_replace_scenario_draft(
                scenario_id=scenario_id,
                document=draft_document,
                source_version_id=source_version_id,
            )
        except (json.JSONDecodeError, ValueError) as error:
            try:
                scenario = analyst_store.get_scenario(scenario_id)
            except KeyError as not_found:
                raise HTTPException(status_code=404, detail=str(not_found)) from not_found
            message = str(error)
            if isinstance(error, json.JSONDecodeError):
                message = f"Malformed JSON: {error.msg} at line {error.lineno}, column {error.colno}"
            return HTMLResponse(
                render_scenario_draft_page(
                    scenario,
                    None,
                    candidate_text,
                    source_version_id=source_version_id,
                    error_message=message,
                )
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return RedirectResponse(f"/scenarios/{scenario_id}/draft", status_code=303)

    @app.post("/scenarios/{scenario_id}/draft/structure")
    async def save_structured_scenario_draft_from_page(scenario_id: int, request: Request):
        form = await request.form()
        try:
            current_draft = get_or_create_scenario_draft(scenario_id)
            draft_document = structured_draft_document_from_form(
                form,
                existing_document=current_draft["document"],
            )
            analyst_store.create_or_replace_scenario_draft(
                scenario_id=scenario_id,
                document=draft_document,
            )
        except DraftGenerationError as error:
            try:
                scenario = analyst_store.get_scenario(scenario_id)
            except KeyError as not_found:
                raise HTTPException(status_code=404, detail=str(not_found)) from not_found
            return HTMLResponse(
                render_scenario_draft_page(
                    scenario,
                    None,
                    empty_scenario_draft_document(scenario["name"]),
                    error_message=str(error),
                )
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return RedirectResponse(f"/scenarios/{scenario_id}/draft", status_code=303)

    @app.post("/scenarios/{scenario_id}/draft/assets")
    async def add_scenario_draft_asset_from_page(scenario_id: int, request: Request):
        form = await request.form()
        try:
            draft = get_or_create_scenario_draft(scenario_id)
            updated_document = add_asset_to_draft(
                draft["document"],
                str(form.get("asset_type") or ""),
            )
            analyst_store.update_scenario_draft(
                scenario_id=scenario_id,
                document=updated_document,
            )
        except DraftGenerationError as error:
            try:
                scenario = analyst_store.get_scenario(scenario_id)
                draft = get_or_create_scenario_draft(scenario_id)
            except KeyError as not_found:
                raise HTTPException(status_code=404, detail=str(not_found)) from not_found
            return HTMLResponse(
                render_scenario_draft_page(
                    scenario,
                    draft,
                    draft["document"],
                    error_message=str(error),
                ),
                status_code=400,
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return RedirectResponse(f"/scenarios/{scenario_id}/draft", status_code=303)

    @app.post("/scenarios/{scenario_id}/draft/assets/{asset_id}/remove")
    async def remove_scenario_draft_asset_from_page(scenario_id: int, asset_id: str):
        try:
            draft = get_or_create_scenario_draft(scenario_id)
            updated_document = remove_asset_from_draft(draft["document"], asset_id)
            analyst_store.update_scenario_draft(
                scenario_id=scenario_id,
                document=updated_document,
            )
        except DraftGenerationError as error:
            try:
                scenario = analyst_store.get_scenario(scenario_id)
                draft = get_or_create_scenario_draft(scenario_id)
            except KeyError as not_found:
                raise HTTPException(status_code=404, detail=str(not_found)) from not_found
            return HTMLResponse(
                render_scenario_draft_page(
                    scenario,
                    draft,
                    draft["document"],
                    error_message=str(error),
                ),
                status_code=404,
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return RedirectResponse(f"/scenarios/{scenario_id}/draft", status_code=303)

    @app.post("/scenarios/{scenario_id}/draft/time-series-sources/upload")
    async def upload_draft_time_series_source_from_page(
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
            try:
                scenario = analyst_store.get_scenario(scenario_id)
                draft = analyst_store.get_scenario_draft(scenario_id)
            except KeyError as not_found:
                raise HTTPException(status_code=404, detail=str(not_found)) from not_found
            return HTMLResponse(
                render_scenario_draft_page(
                    scenario,
                    draft,
                    draft["document"],
                    error_message=f"Source-file error: {error}",
                )
            )
        finally:
            await source_file.close()
        return RedirectResponse(f"/scenarios/{scenario_id}/draft", status_code=303)

    @app.post("/scenarios/{scenario_id}/draft/time-series-sources/{source_id}/mapping")
    async def save_draft_time_series_mapping_from_page(scenario_id: int, source_id: str, request: Request):
        form = await request.form()
        try:
            draft = analyst_store.get_scenario_draft(scenario_id)
            mapping = time_series_mapping_from_form(form)
            updated_document, _source = apply_time_series_mapping(
                document=draft["document"],
                source_id=source_id,
                mapping=mapping,
                input_source_root=configured_input_source_root,
            )
            analyst_store.update_scenario_draft(
                scenario_id=scenario_id,
                document=updated_document,
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except TimeSeriesIngestionError as error:
            try:
                scenario = analyst_store.get_scenario(scenario_id)
                draft = analyst_store.get_scenario_draft(scenario_id)
            except KeyError as not_found:
                raise HTTPException(status_code=404, detail=str(not_found)) from not_found
            return HTMLResponse(
                render_scenario_draft_page(
                    scenario,
                    draft,
                    draft["document"],
                    error_message=f"Source-file error: {error}",
                )
            )
        return RedirectResponse(f"/scenarios/{scenario_id}/draft", status_code=303)

    @app.post("/scenarios/{scenario_id}/draft/generated-system-case/validate")
    async def validate_generated_system_case_from_page(scenario_id: int):
        try:
            scenario = analyst_store.get_scenario(scenario_id)
            draft = analyst_store.get_scenario_draft(scenario_id)
            system_case = generate_system_case_from_draft(draft["document"])
            result = service.validate_text(json.dumps(system_case, sort_keys=True))
            updated_document = draft_document_with_generated_validation(
                draft["document"],
                system_case,
                result,
            )
            draft = analyst_store.update_scenario_draft(
                scenario_id=scenario_id,
                document=updated_document,
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except DraftGenerationError as error:
            try:
                scenario = analyst_store.get_scenario(scenario_id)
                draft = analyst_store.get_scenario_draft(scenario_id)
            except KeyError as not_found:
                raise HTTPException(status_code=404, detail=str(not_found)) from not_found
            return HTMLResponse(
                render_scenario_draft_page(
                    scenario,
                    draft,
                    draft["document"],
                    error_message=str(error),
                )
            )
        return HTMLResponse(
            render_scenario_draft_page(
                scenario,
                draft,
                draft["document"],
                generated_validation_result=result,
            )
        )

    @app.post("/scenarios/{scenario_id}/draft/generated-system-case/promote")
    async def promote_generated_system_case_from_page(scenario_id: int):
        try:
            scenario = analyst_store.get_scenario(scenario_id)
            draft = analyst_store.get_scenario_draft(scenario_id)
            system_case = validated_generated_system_case_from_draft(draft["document"])
            version, error = save_validated_scenario_version(
                scenario_id,
                json.dumps(system_case, sort_keys=True),
                generation_metadata_from_draft(draft["document"]),
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except (DraftGenerationError, DraftPromotionError) as error:
            return HTMLResponse(
                render_scenario_draft_page(
                    scenario,
                    draft,
                    draft["document"],
                    error_message=str(error),
                )
            )
        if error is not None:
            updated_document = draft_document_with_generated_validation(
                draft["document"],
                system_case,
                error,
            )
            draft = analyst_store.update_scenario_draft(
                scenario_id=scenario_id,
                document=updated_document,
            )
            return HTMLResponse(
                render_scenario_draft_page(
                    scenario,
                    draft,
                    draft["document"],
                    generated_validation_result=error,
                )
            )
        return RedirectResponse(f"/scenarios/{scenario_id}#version-{version['id']}", status_code=303)

    @app.get("/scenarios/{scenario_id}", response_class=HTMLResponse)
    async def scenario_page(scenario_id: int, from_version_id: int | None = None):
        try:
            scenario = analyst_store.get_scenario(scenario_id)
            versions = analyst_store.list_scenario_versions(scenario_id)
            runs = analyst_store.list_scenario_runs(scenario_id)
            candidate_text = ""
            if from_version_id is not None:
                base_version = analyst_store.get_scenario_version(from_version_id)
                if base_version["scenario_id"] != scenario_id:
                    raise KeyError(f"scenario version {from_version_id} not found for scenario {scenario_id}")
                candidate_text = json.dumps(base_version["system_case_json"], indent=2, sort_keys=True)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return HTMLResponse(render_scenario_page(scenario, versions, candidate_text, runs=runs))

    @app.post("/scenarios/{scenario_id}/versions", response_class=HTMLResponse)
    async def create_scenario_version_from_page(scenario_id: int, request: Request):
        form = await request.form()
        upload = form.get("system_case_file")
        candidate_text = str(form.get("system_case_json", ""))
        if hasattr(upload, "filename") and upload.filename:
            try:
                candidate_text = (await upload.read()).decode("utf-8")
            except UnicodeDecodeError:
                scenario = analyst_store.get_scenario(scenario_id)
                versions = analyst_store.list_scenario_versions(scenario_id)
                runs = analyst_store.list_scenario_runs(scenario_id)
                error = ValidationResult(
                    ok=False,
                    phase="json",
                    message="Uploaded file must be UTF-8 encoded JSON",
                    payload={"status": "error"},
                )
                return HTMLResponse(render_scenario_page(scenario, versions, candidate_text, error, runs=runs))
            finally:
                close_upload = getattr(upload, "close", None)
                if close_upload is not None:
                    await close_upload()
        try:
            version, error = save_validated_scenario_version(scenario_id, candidate_text)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        if error is not None:
            scenario = analyst_store.get_scenario(scenario_id)
            versions = analyst_store.list_scenario_versions(scenario_id)
            runs = analyst_store.list_scenario_runs(scenario_id)
            return HTMLResponse(render_scenario_page(scenario, versions, candidate_text, error, runs=runs))
        return RedirectResponse(f"/scenarios/{scenario_id}#version-{version['id']}", status_code=303)

    @app.post("/scenario-versions/{scenario_version_id}/delete")
    async def delete_scenario_version_from_page(scenario_version_id: int):
        try:
            deleted_version = analyst_store.delete_scenario_version(scenario_version_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return RedirectResponse(f"/scenarios/{deleted_version['scenario_id']}", status_code=303)

    @app.post("/scenario-versions/{scenario_version_id}/runs")
    async def create_manual_run_from_page(scenario_version_id: int):
        try:
            run = create_and_enqueue_run(scenario_version_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return RedirectResponse(f"/runs/{run['id']}", status_code=303)

    @app.get("/runs/{run_id}", response_class=HTMLResponse)
    async def run_page(run_id: int):
        try:
            run = analyst_store.get_run(run_id)
            lineage = analyst_store.get_run_lineage(run_id)
            stored_artifacts = analyst_store.list_run_artifacts(run_id)
            artifacts = [
                artifact_response_body(artifact)
                for artifact in stored_artifacts
                if artifact_path_is_safe(artifact["path"], configured_artifact_root)
            ]
            publications = analyst_store.list_run_publications(run_id)
            dashboard_templates = []
            if run["status"] == "succeeded":
                dashboard_templates = analyst_store.list_dashboard_templates(lineage["project_id"])
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

        results = None
        results_error = ""
        if run["status"] == "succeeded":
            try:
                results = read_run_results(run, stored_artifacts, configured_artifact_root)
            except ResultReadError as error:
                results_error = error.message
        return HTMLResponse(
            render_run_page(
                run,
                artifacts,
                results,
                results_error,
                publications=publications,
                dashboard_templates=dashboard_templates,
                publication_artifacts=stored_artifacts,
                scenario_id=lineage["scenario_id"],
            )
        )

    @app.get("/system-cases/validate", response_class=HTMLResponse)
    async def validation_page():
        return HTMLResponse(render_validation_page())

    @app.post("/system-cases/validate", response_class=HTMLResponse)
    async def validate_from_page(request: Request):
        form = await request.form()
        candidate_text = str(form.get("system_case_json", ""))
        result = service.validate_text(candidate_text)
        return HTMLResponse(render_validation_page(candidate_text, result))

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


def artifact_path_is_safe(path: str, artifact_root: Path) -> bool:
    root = artifact_root.resolve(strict=False)
    resolved_path = Path(path).resolve(strict=False)
    try:
        resolved_path.relative_to(root)
    except ValueError:
        return False
    return True


def time_series_mapping_from_form(form) -> dict[str, Any]:
    mapping: dict[str, Any] = {
        "timestamp": str(form.get("mapping_timestamp", "")).strip() or None,
        "duration_hours": str(form.get("mapping_duration_hours", "")).strip() or None,
        "price_usd_per_mwh": str(form.get("mapping_price_usd_per_mwh", "")).strip() or None,
        "import_price_usd_per_mwh": str(form.get("mapping_import_price_usd_per_mwh", "")).strip() or None,
        "export_price_usd_per_mwh": str(form.get("mapping_export_price_usd_per_mwh", "")).strip() or None,
        "renewable_available_power_mw": {},
        "load_demand_mw": {},
        "hydro_inflow_m3s": {},
    }
    for key, value in form.items():
        text_value = str(value).strip()
        if key.startswith("mapping_renewable_available_power_mw__"):
            asset_id = key.removeprefix("mapping_renewable_available_power_mw__")
            mapping["renewable_available_power_mw"][asset_id] = text_value or None
        if key.startswith("mapping_load_demand_mw__"):
            asset_id = key.removeprefix("mapping_load_demand_mw__")
            mapping["load_demand_mw"][asset_id] = text_value or None
        if key.startswith("mapping_hydro_inflow_m3s__"):
            asset_id = key.removeprefix("mapping_hydro_inflow_m3s__")
            mapping["hydro_inflow_m3s"][asset_id] = text_value or None
    return mapping


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


def render_validation_page(candidate_text: str = "", result: ValidationResult | None = None) -> str:
    result_markup = ""
    if result is not None:
        status_class = "success" if result.ok else "error"
        status_text = "Valid" if result.ok else "Invalid"
        detail = result.message
        if result.ok and result.payload:
            detail = (
                f"{result.payload.get('case_name', 'system_case')} "
                f"({result.payload.get('period_count', 0)} periods)"
            )
        result_markup = (
            f'<section class="result {status_class}">'
            f"<h2>{status_text}</h2>"
            f"<p>{escape(detail)}</p>"
            "</section>"
        )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>System Case Validation</title>
  <style>
    :root {{
      color-scheme: light;
      font-family: Arial, sans-serif;
      --ink: #17202a;
      --muted: #5b6472;
      --line: #d9dee7;
      --surface: #f7f8fa;
      --accent: #0f766e;
      --error: #b42318;
    }}
    body {{
      margin: 0;
      color: var(--ink);
      background: white;
    }}
    main {{
      width: min(1040px, calc(100vw - 32px));
      margin: 0 auto;
      padding: 32px 0;
    }}
    header {{
      display: flex;
      align-items: baseline;
      justify-content: space-between;
      gap: 16px;
      border-bottom: 1px solid var(--line);
      padding-bottom: 18px;
      margin-bottom: 24px;
    }}
    h1 {{
      font-size: 24px;
      line-height: 1.2;
      margin: 0;
    }}
    form {{
      display: grid;
      gap: 14px;
    }}
    label {{
      color: var(--muted);
      font-size: 14px;
      font-weight: 700;
    }}
    textarea {{
      box-sizing: border-box;
      width: 100%;
      min-height: 440px;
      resize: vertical;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 14px;
      font: 13px/1.45 Consolas, "Liberation Mono", monospace;
      background: var(--surface);
      color: var(--ink);
    }}
    button {{
      justify-self: start;
      border: 0;
      border-radius: 6px;
      padding: 10px 16px;
      background: var(--accent);
      color: white;
      font-weight: 700;
      cursor: pointer;
    }}
    .result {{
      border-left: 4px solid var(--accent);
      background: #effcf8;
      padding: 12px 14px;
      margin-bottom: 18px;
    }}
    .result.error {{
      border-left-color: var(--error);
      background: #fff4f2;
    }}
    .result h2 {{
      font-size: 16px;
      margin: 0 0 4px;
    }}
    .result p {{
      margin: 0;
      color: var(--muted);
    }}
  </style>
</head>
<body>
  <main>
    <header>
      <h1>System Case Validation</h1>
    </header>
    {result_markup}
    <form method="post" action="/system-cases/validate">
      <label for="system_case_json">system_case_json</label>
      <textarea id="system_case_json" name="system_case_json" spellcheck="false">{escape(candidate_text)}</textarea>
      <button type="submit">Validate</button>
    </form>
  </main>
</body>
</html>"""


def render_projects_page(projects: list[dict]) -> str:
    project_items = "".join(
        f'<li><a href="/projects/{project["id"]}">{escape(project["name"])}</a>'
        f'<span>{escape(project["description"])}</span></li>'
        for project in projects
    )
    if not project_items:
        project_items = '<li class="empty">No projects yet</li>'

    return render_app_page(
        "Projects",
        f"""
        <section class="toolbar">
          <h1>Projects</h1>
        </section>
        <section class="split">
          <div>
            <h2>Project List</h2>
            <ul class="entity-list">{project_items}</ul>
          </div>
          <form method="post" action="/projects">
            <h2>New Project</h2>
            <label for="name">Name</label>
            <input id="name" name="name" required>
            <label for="description">Description</label>
            <textarea id="description" name="description"></textarea>
            <button type="submit">Create Project</button>
          </form>
        </section>
        """,
    )


def render_project_page(
    project: dict,
    scenarios: list[dict],
    dashboard_templates: list[dict[str, Any]] | None = None,
    client_access: list[dict[str, Any]] | None = None,
    client_users: list[dict[str, Any]] | None = None,
    can_manage_access: bool = False,
) -> str:
    scenario_items = "".join(
        f'<li><a href="/scenarios/{scenario["id"]}">{escape(scenario["name"])}</a>'
        f'<span>{escape(scenario["description"])}</span></li>'
        for scenario in scenarios
    )
    if not scenario_items:
        scenario_items = '<li class="empty">No scenarios yet</li>'
    dashboard_templates = dashboard_templates or []
    template_items = "".join(render_dashboard_template_item(template) for template in dashboard_templates)
    if not template_items:
        template_items = '<li class="empty">No dashboard templates yet</li>'
    access_section = ""
    if can_manage_access:
        client_access = client_access or []
        client_users = client_users or []
        access_items = "".join(
            f'<li><span>{escape(assignment["email"])}</span>'
            f'<form method="post" action="/projects/{project["id"]}/client-access/{assignment["user_id"]}/remove">'
            '<button type="submit">Remove</button></form></li>'
            for assignment in client_access
        )
        if not access_items:
            access_items = '<li class="empty">No client access assigned</li>'
        client_options = "".join(
            f'<option value="{user["id"]}">{escape(user["email"])}</option>'
            for user in client_users
        )
        if not client_options:
            client_options = '<option value="">No client users available</option>'
        access_section = f"""
        <section class="split">
          <div>
            <h2>Client Access</h2>
            <ul class="entity-list">{access_items}</ul>
          </div>
          <form method="post" action="/projects/{project["id"]}/client-access">
            <h2>Assign Client</h2>
            <label for="user_id">Client</label>
            <select id="user_id" name="user_id" required>{client_options}</select>
            <button type="submit">Assign Client</button>
          </form>
        </section>
        """

    return render_app_page(
        project["name"],
        f"""
        <nav><a href="/projects">Projects</a></nav>
        <section class="toolbar">
          <h1>{escape(project["name"])}</h1>
          <p>{escape(project["description"])}</p>
        </section>
        <section class="split">
          <div>
            <h2>Scenarios</h2>
            <ul class="entity-list">{scenario_items}</ul>
          </div>
          <form method="post" action="/projects/{project["id"]}/scenarios">
            <h2>New Scenario</h2>
            <label for="name">Name</label>
            <input id="name" name="name" required>
            <label for="description">Description</label>
            <textarea id="description" name="description"></textarea>
            <button type="submit">Create Scenario</button>
          </form>
        </section>
        <section class="split">
          <div>
            <h2>Dashboard Templates</h2>
            <ul class="entity-list">{template_items}</ul>
          </div>
          {render_dashboard_template_form(f'/projects/{project["id"]}/dashboard-templates')}
        </section>
        {access_section}
        """,
    )


def render_dashboard_template_item(template: dict[str, Any]) -> str:
    enabled = [
        label
        for field, label in [
            ("show_summary", "summary"),
            ("show_price_chart", "price"),
            ("show_grid_chart", "grid"),
            ("show_renewable_chart", "renewable"),
            ("show_bess_chart", "BESS"),
            ("show_hydro_chart", "hydro"),
            ("show_profit_chart", "profit"),
            ("show_system_dispatch_table", "system table"),
            ("show_asset_dispatch_table", "asset table"),
        ]
        if template.get(field)
    ]
    enabled_text = ", ".join(enabled) if enabled else "no sections enabled"
    form_action = f"/dashboard-templates/{template['id']}"
    return (
        "<li>"
        f"<strong>{escape(template['name'])}</strong>"
        f"<span>{escape(enabled_text)} | table preview {template['table_preview_limit']} rows</span>"
        f"{render_dashboard_template_form(form_action, template)}"
        "</li>"
    )


def render_dashboard_template_form(action: str, template: dict[str, Any] | None = None) -> str:
    template = template or {
        "name": "",
        "show_summary": True,
        "show_price_chart": True,
        "show_grid_chart": True,
        "show_renewable_chart": True,
        "show_bess_chart": True,
        "show_hydro_chart": True,
        "show_profit_chart": True,
        "show_system_dispatch_table": True,
        "show_asset_dispatch_table": True,
        "table_preview_limit": 10,
    }
    title = "Edit Template" if template.get("id") else "New Dashboard Template"
    button = "Update Template" if template.get("id") else "Create Template"
    checkbox_rows = "".join(
        render_checkbox_row(field, label, template.get(field, False))
        for field, label in [
            ("show_summary", "Summary"),
            ("show_price_chart", "Price chart"),
            ("show_grid_chart", "Grid chart"),
            ("show_renewable_chart", "Renewable chart"),
            ("show_bess_chart", "BESS chart"),
            ("show_hydro_chart", "Hydro charts"),
            ("show_profit_chart", "Period profit chart"),
            ("show_system_dispatch_table", "System dispatch preview"),
            ("show_asset_dispatch_table", "Asset dispatch preview"),
        ]
    )
    return f"""
          <form method="post" action="{escape(action, quote=True)}">
            <h2>{title}</h2>
            <label for="template_name_{template.get('id', 'new')}">Name</label>
            <input id="template_name_{template.get('id', 'new')}" name="name" value="{html_value(template.get('name', ''))}" required>
            {checkbox_rows}
            <label for="table_preview_limit_{template.get('id', 'new')}">Table Preview Rows</label>
            <input id="table_preview_limit_{template.get('id', 'new')}" name="table_preview_limit" type="number" min="1" value="{html_value(template.get('table_preview_limit', 10))}" required>
            <button type="submit">{button}</button>
          </form>
    """


def render_checkbox_row(field: str, label: str, value: Any) -> str:
    return (
        '<label class="checkbox-row">'
        f'<input type="checkbox" name="{escape(field, quote=True)}" {checked_attr(value)}>'
        f"{escape(label)}"
        "</label>"
    )


def render_scenario_page(
    scenario: dict,
    versions: list[dict],
    candidate_text: str = "",
    error: ValidationResult | None = None,
    *,
    runs: list[dict] | None = None,
) -> str:
    runs_by_version: dict[int, list[dict]] = {}
    for run in runs or []:
        runs_by_version.setdefault(int(run["scenario_version_id"]), []).append(run)

    version_items = "".join(
        f'<li id="version-{version["id"]}">'
        f'<strong>Version {version["version_number"]}</strong>'
        f'<span>{escape(version["case_name"])} | {escape(version["schema_version"])} | '
        f'{version["period_count"]} periods | {format_asset_counts(version["asset_counts"])}</span>'
        f'{render_scenario_version_runs(runs_by_version.get(int(version["id"]), []))}'
        f'<a href="/scenarios/{scenario["id"]}?from_version_id={version["id"]}">Use as base</a>'
        f'<a href="/scenarios/{scenario["id"]}/draft?source_version_id={version["id"]}">Use as draft base</a>'
        f'<form class="inline-form" method="post" action="/scenario-versions/{version["id"]}/runs">'
        f'<button type="submit">Launch Run</button>'
        f"</form>"
        f'<form class="inline-form" method="post" action="/scenario-versions/{version["id"]}/delete" '
        'onsubmit="return confirm(\'Delete this eligible version? Versions referenced by runs or publications are protected.\')">'
        f'<button type="submit" class="button-danger" aria-label="Delete version {version["version_number"]}">'
        "Delete Version</button>"
        "</form>"
        "</li>"
        for version in versions
    )
    if not version_items:
        version_items = '<li class="empty">No saved versions yet</li>'

    error_markup = ""
    if error is not None:
        error_markup = (
            '<section class="notice error">'
            "<h2>Validation Error</h2>"
            f"<p>{escape(error.message)}</p>"
            "</section>"
        )

    return render_app_page(
        scenario["name"],
        f"""
        <nav><a href="/projects/{scenario["project_id"]}">Project</a></nav>
        <section class="toolbar">
          <h1>{escape(scenario["name"])}</h1>
          <p>{escape(scenario["description"])}</p>
        </section>
        {error_markup}
        <section class="notice">
          <h2>Structured Draft</h2>
          <p>One active editable draft can be saved before promotion to an immutable version.</p>
          <a href="/scenarios/{scenario["id"]}/draft">Open Draft</a>
        </section>
        <section class="split wide">
          <div>
            <h2>Versions</h2>
            <ul class="entity-list">{version_items}</ul>
          </div>
          <form method="post" action="/scenarios/{scenario["id"]}/versions" enctype="multipart/form-data">
            <h2>New Version</h2>
            <label for="system_case_json">system_case_json</label>
            <textarea id="system_case_json" name="system_case_json" spellcheck="false">{escape(candidate_text)}</textarea>
            <label for="system_case_file">Upload JSON</label>
            <input id="system_case_file" name="system_case_file" type="file" accept="application/json,.json">
            <button type="submit">Validate And Save</button>
          </form>
        </section>
        """,
    )


def render_scenario_version_runs(runs: list[dict]) -> str:
    if not runs:
        return (
            '<div class="version-runs">'
            "<h3>Previous Runs</h3>"
            '<p class="empty">No runs saved for this version.</p>'
            "</div>"
        )

    items = []
    for run in runs:
        succeeded = run.get("status") == "succeeded"
        action_label = "Load Results" if succeeded else "Open Run"
        action_href = f'/runs/{run["id"]}#results' if succeeded else f'/runs/{run["id"]}'
        finished = f' | finished {escape(str(run["finished_at"]))}' if run.get("finished_at") else ""
        items.append(
            "<li>"
            "<div>"
            f'<strong>Run {run["id"]}</strong>'
            f'<span>Status: {escape(str(run["status"]))} | created {escape(str(run["created_at"]))}{finished}</span>'
            "</div>"
            f'<a class="button-link" href="{action_href}">{action_label}</a>'
            "</li>"
        )
    return (
        '<div class="version-runs">'
        "<h3>Previous Runs</h3>"
        f'<ul class="version-run-list">{"".join(items)}</ul>'
        "</div>"
    )


def render_scenario_draft_page(
    scenario: dict,
    draft: dict | None,
    draft_document: dict | str,
    *,
    source_version_id: int | None = None,
    error_message: str = "",
    generated_validation_result: ValidationResult | None = None,
) -> str:
    if isinstance(draft_document, str):
        draft_text = draft_document
    else:
        draft_text = json.dumps(draft_document, indent=2, sort_keys=True)

    status_text = "No active draft saved yet"
    if draft is not None:
        status_text = f"Active draft {draft['id']} last saved at {draft['updated_at']}"

    source_version_value = source_version_id
    if source_version_value is None and draft is not None:
        source_version_value = draft["source_version_id"]
    hidden_source = ""
    if source_version_value is not None:
        hidden_source = f'<input type="hidden" name="source_version_id" value="{source_version_value}">'

    error_markup = ""
    if error_message:
        error_markup = (
            '<section class="notice error">'
            "<h2>Draft Error</h2>"
            f"<p>{escape(error_message)}</p>"
            "</section>"
        )
    document_for_sections = draft_document if isinstance(draft_document, dict) else {}
    asset_builder = render_asset_builder(scenario, document_for_sections)
    structured_form = render_structured_draft_form(scenario, document_for_sections)
    time_series_section = render_time_series_source_section(scenario, document_for_sections)
    preview_markup = render_generated_preview(draft_document if isinstance(draft_document, dict) else None)
    generated_validation_markup = render_generated_validation_section(
        scenario,
        draft_document if isinstance(draft_document, dict) else None,
        generated_validation_result,
    )

    return render_app_page(
        "Structured Draft",
        f"""
        <nav><a href="/scenarios/{scenario["id"]}">Scenario</a></nav>
        <section class="toolbar">
          <h1>Structured Draft</h1>
          <p>{escape(scenario["name"])} | {escape(status_text)}</p>
        </section>
        {error_markup}
        {asset_builder}
        {structured_form}
        {time_series_section}
        {preview_markup}
        {generated_validation_markup}
        <details class="advanced-section">
          <summary>Advanced: edit raw draft JSON</summary>
          <form method="post" action="/scenarios/{scenario["id"]}/draft">
            <label for="structured_draft_json">structured_draft_json</label>
            <textarea id="structured_draft_json" name="structured_draft_json" spellcheck="false">{escape(draft_text)}</textarea>
            {hidden_source}
            <button type="submit">Save Raw Draft</button>
          </form>
        </details>
        """,
    )


def render_asset_builder(scenario: dict, document: dict) -> str:
    assets = document.get("assets") if isinstance(document.get("assets"), list) else []
    valid_assets = [
        asset
        for asset in assets
        if isinstance(asset, dict) and asset.get("type") in SUPPORTED_ASSET_TYPES
    ]
    present_types = {str(asset.get("type")) for asset in valid_assets}
    labels = {
        "battery": "BESS",
        "load": "Demand",
        "renewable": "Renewable",
        "hydro": "Hydro",
    }
    cards = []
    for asset in valid_assets:
        asset_id = str(asset.get("id") or "")
        asset_type = str(asset.get("type") or "")
        cards.append(
            '<article class="asset-card">'
            "<div>"
            f"<strong>{escape(labels.get(asset_type, asset_type.title()))}</strong>"
            f"<span>{escape(asset_id)}</span>"
            "</div>"
            f'<form method="post" action="/scenarios/{scenario["id"]}/draft/assets/'
            f'{quote(asset_id, safe="")}/remove" class="inline-form">'
            '<button type="submit" class="button-secondary">Remove</button>'
            "</form>"
            "</article>"
        )
    cards_markup = "".join(cards) or '<p class="empty">No optional assets added yet.</p>'
    options = "".join(
        f'<option value="{asset_type}">{escape(labels[asset_type])}</option>'
        for asset_type in SUPPORTED_ASSET_TYPES
        if asset_type not in present_types
    )
    if options:
        add_form = f"""
          <form method="post" action="/scenarios/{scenario["id"]}/draft/assets" class="asset-add-form">
            <label for="asset_type">Asset type</label>
            <select id="asset_type" name="asset_type">{options}</select>
            <button type="submit">Add Asset</button>
          </form>
        """
    else:
        add_form = '<p class="empty">All supported asset types are already present.</p>'
    return f"""
      <section class="asset-builder">
        <div>
          <h2>1. Choose Assets</h2>
          <p>Add only what this scenario needs. PCC and grid are created automatically.</p>
        </div>
        <div class="asset-list">{cards_markup}</div>
        {add_form}
      </section>
    """


def render_structured_draft_form(scenario: dict, document: dict) -> str:
    case = document.get("case") if isinstance(document.get("case"), dict) else {}
    pcc = document.get("pcc") if isinstance(document.get("pcc"), dict) else {}
    grid = document.get("grid") if isinstance(document.get("grid"), dict) else {}
    solver = document.get("solver") if isinstance(document.get("solver"), dict) else {}
    assets = document.get("assets") if isinstance(document.get("assets"), list) else []
    solver_options = solver.get("options") if isinstance(solver.get("options"), dict) else {}
    asset_sections = "".join(
        render_asset_settings(asset)
        for asset in assets
        if isinstance(asset, dict) and asset.get("type") in SUPPORTED_ASSET_TYPES
    )
    if not asset_sections:
        asset_sections = '<p class="empty asset-empty">Add an asset above to configure it.</p>'

    return f"""
        <form method="post" action="/scenarios/{scenario["id"]}/draft/structure" class="structured-form">
          <h2>2. Configure Scenario</h2>
          <label for="case_name">Scenario name</label>
          <input id="case_name" name="case_name" value="{html_value(case.get("name") or scenario["name"])}">
          <label for="case_description">Description</label>
          <textarea id="case_description" name="case_description">{escape(str(case.get("description") or ""))}</textarea>

          {asset_sections}

          <details class="advanced-section">
            <summary>Connection and solver settings</summary>
            <div class="form-grid details-fields">
              <label for="pcc_id">PCC ID</label>
              <input id="pcc_id" name="pcc_id" value="{html_value(pcc.get("id") or "bus_1")}">
              <label for="grid_id">Grid ID</label>
              <input id="grid_id" name="grid_id" value="{html_value(grid.get("id") or "grid_1")}">
              <label for="grid_import_power_max_mw">Maximum import (MW)</label>
              <input id="grid_import_power_max_mw" name="grid_import_power_max_mw" type="number" step="any" value="{html_value(grid.get("import_power_max_mw"))}">
              <label for="grid_export_power_max_mw">Maximum export (MW)</label>
              <input id="grid_export_power_max_mw" name="grid_export_power_max_mw" type="number" step="any" value="{html_value(grid.get("export_power_max_mw"))}">
              <label for="solver_name">Solver</label>
              <input id="solver_name" name="solver_name" value="{html_value(solver.get("name") or "HiGHS")}">
            </div>
            <label class="checkbox-row">
              <input type="checkbox" name="grid_prevent_simultaneous_grid_import_export" {checked_attr(grid.get("prevent_simultaneous_grid_import_export", True))}>
              Prevent simultaneous import and export
            </label>
            <label for="solver_options_json">Solver options (JSON)</label>
            <textarea id="solver_options_json" name="solver_options_json" spellcheck="false">{escape(json.dumps(solver_options, sort_keys=True))}</textarea>
          </details>
          <button type="submit">Save Scenario Changes</button>
        </form>
    """


def render_asset_settings(asset: dict[str, Any]) -> str:
    asset_type = str(asset.get("type") or "")
    if asset_type == "battery":
        return render_battery_settings(asset)
    if asset_type == "load":
        return render_load_settings(asset)
    if asset_type == "renewable":
        return render_renewable_settings(asset)
    if asset_type == "hydro":
        return render_hydro_settings(asset)
    return ""


def render_battery_settings(battery: dict[str, Any]) -> str:
    terminal_condition = str(battery.get("terminal_condition") or "equal_initial")
    return f"""
      <fieldset class="asset-settings">
        <legend>BESS settings</legend>
        <div class="form-grid">
          <label for="battery_id">Asset ID</label>
          <input id="battery_id" name="battery_id" value="{html_value(battery.get("id"))}" required>
          <label for="battery_charge_power_max_mw">Maximum charge (MW)</label>
          <input id="battery_charge_power_max_mw" name="battery_charge_power_max_mw" type="number" step="any" value="{html_value(draft_value(battery, "charge_power_max_mw", 4.0))}" required>
          <label for="battery_discharge_power_max_mw">Maximum discharge (MW)</label>
          <input id="battery_discharge_power_max_mw" name="battery_discharge_power_max_mw" type="number" step="any" value="{html_value(draft_value(battery, "discharge_power_max_mw", 4.0))}" required>
          <label for="battery_energy_min_mwh">Minimum energy (MWh)</label>
          <input id="battery_energy_min_mwh" name="battery_energy_min_mwh" type="number" step="any" value="{html_value(draft_value(battery, "energy_min_mwh", 0.0))}" required>
          <label for="battery_energy_max_mwh">Maximum energy (MWh)</label>
          <input id="battery_energy_max_mwh" name="battery_energy_max_mwh" type="number" step="any" value="{html_value(draft_value(battery, "energy_max_mwh", 8.0))}" required>
          <label for="battery_initial_energy_mwh">Initial energy (MWh)</label>
          <input id="battery_initial_energy_mwh" name="battery_initial_energy_mwh" type="number" step="any" value="{html_value(draft_value(battery, "initial_energy_mwh", 4.0))}" required>
          <label for="battery_charge_efficiency">Charge efficiency</label>
          <input id="battery_charge_efficiency" name="battery_charge_efficiency" type="number" step="any" value="{html_value(draft_value(battery, "charge_efficiency", 0.95))}" required>
          <label for="battery_discharge_efficiency">Discharge efficiency</label>
          <input id="battery_discharge_efficiency" name="battery_discharge_efficiency" type="number" step="any" value="{html_value(draft_value(battery, "discharge_efficiency", 0.95))}" required>
          <label for="battery_degradation_cost_per_mwh_delta_soc">Degradation cost (USD/MWh)</label>
          <input id="battery_degradation_cost_per_mwh_delta_soc" name="battery_degradation_cost_per_mwh_delta_soc" type="number" step="any" value="{html_value(draft_value(battery, "degradation_cost_per_mwh_delta_soc", 0.0))}" required>
          <label for="battery_terminal_condition">Terminal condition</label>
          <select id="battery_terminal_condition" name="battery_terminal_condition">
            <option value="none" {selected_attr(terminal_condition == "none")}>None</option>
            <option value="equal_initial" {selected_attr(terminal_condition == "equal_initial")}>Equal initial</option>
            <option value="min_terminal" {selected_attr(terminal_condition == "min_terminal")}>Minimum terminal</option>
          </select>
          <label for="battery_terminal_energy_min_mwh">Minimum terminal energy (MWh)</label>
          <input id="battery_terminal_energy_min_mwh" name="battery_terminal_energy_min_mwh" type="number" step="any" value="{html_value(battery.get("terminal_energy_min_mwh"))}">
        </div>
        <label class="checkbox-row">
          <input type="checkbox" name="battery_prevent_simultaneous_charge_discharge" {checked_attr(battery.get("prevent_simultaneous_charge_discharge", True))}>
          Prevent simultaneous charge and discharge
        </label>
        <label class="checkbox-row">
          <input type="checkbox" name="battery_degradation_linear_delta_soc" {checked_attr(battery.get("degradation_linear_delta_soc", True))}>
          Apply linear degradation
        </label>
      </fieldset>
    """


def render_load_settings(load: dict[str, Any]) -> str:
    return f"""
      <fieldset class="asset-settings">
        <legend>Demand settings</legend>
        <label for="load_id">Asset ID</label>
        <input id="load_id" name="load_id" value="{html_value(load.get("id"))}" required>
        <p>Demand values are supplied period by period in the time-series file.</p>
      </fieldset>
    """


def render_renewable_settings(renewable: dict[str, Any]) -> str:
    category = str(renewable.get("category") or renewable.get("display_category") or "solar")
    return f"""
      <fieldset class="asset-settings">
        <legend>Renewable settings</legend>
        <div class="form-grid">
          <label for="renewable_id">Asset ID</label>
          <input id="renewable_id" name="renewable_id" value="{html_value(renewable.get("id"))}" required>
          <label for="renewable_category">Technology</label>
          <select id="renewable_category" name="renewable_category">
            <option value="solar" {selected_attr(category == "solar")}>Solar</option>
            <option value="wind" {selected_attr(category == "wind")}>Wind</option>
          </select>
          <label for="renewable_curtailment_penalty_usd_per_mwh">Curtailment penalty (USD/MWh)</label>
          <input id="renewable_curtailment_penalty_usd_per_mwh" name="renewable_curtailment_penalty_usd_per_mwh" type="number" step="any" value="{html_value(draft_value(renewable, "curtailment_penalty_usd_per_mwh", 0.0))}">
        </div>
        <p>Availability values are supplied period by period in the time-series file.</p>
      </fieldset>
    """


def render_hydro_settings(hydro: dict[str, Any]) -> str:
    generation_curve = hydro.get("generation_curve") if isinstance(hydro.get("generation_curve"), list) else []
    reservoir_curve = (
        hydro.get("reservoir_curve")
        if isinstance(hydro.get("reservoir_curve"), list)
        else [
            {"storage_hm3": 1.0, "elevation_masl": 700.0},
            {"storage_hm3": 3.0, "elevation_masl": 710.0},
            {"storage_hm3": 5.0, "elevation_masl": 720.0},
        ]
    )
    generation_mode = str(hydro.get("generation_mode") or "linear")
    terminal_condition = str(hydro.get("terminal_condition") or "none")
    return f"""
      <fieldset class="asset-settings">
        <legend>Hydro settings</legend>
        <div class="form-grid">
          <label for="hydro_id">Asset ID</label>
          <input id="hydro_id" name="hydro_id" value="{html_value(hydro.get("id"))}" required>
          <label for="hydro_storage_min_hm3">Minimum storage (hm3)</label>
          <input id="hydro_storage_min_hm3" name="hydro_storage_min_hm3" type="number" step="any" value="{html_value(draft_value(hydro, "storage_min_hm3", 1.0))}" required>
          <label for="hydro_storage_max_hm3">Maximum storage (hm3)</label>
          <input id="hydro_storage_max_hm3" name="hydro_storage_max_hm3" type="number" step="any" value="{html_value(draft_value(hydro, "storage_max_hm3", 5.0))}" required>
          <label for="hydro_initial_storage_hm3">Initial storage (hm3)</label>
          <input id="hydro_initial_storage_hm3" name="hydro_initial_storage_hm3" type="number" step="any" value="{html_value(draft_value(hydro, "initial_storage_hm3", 2.5))}" required>
          <label for="hydro_generation_mode">Generation mode</label>
          <select id="hydro_generation_mode" name="hydro_generation_mode">
            <option value="linear" {selected_attr(generation_mode == "linear")}>Linear</option>
            <option value="piecewise_linear" {selected_attr(generation_mode == "piecewise_linear")}>Piecewise linear</option>
          </select>
          <label for="hydro_power_per_flow_mw_per_m3s">Power per flow (MW per m3/s)</label>
          <input id="hydro_power_per_flow_mw_per_m3s" name="hydro_power_per_flow_mw_per_m3s" type="number" step="any" value="{html_value(draft_value(hydro, "power_per_flow_mw_per_m3s", 0.08))}">
          <label for="hydro_turbine_flow_min_m3s">Minimum turbine flow (m3/s)</label>
          <input id="hydro_turbine_flow_min_m3s" name="hydro_turbine_flow_min_m3s" type="number" step="any" value="{html_value(hydro.get("turbine_flow_min_m3s"))}">
          <label for="hydro_turbine_flow_max_m3s">Maximum turbine flow (m3/s)</label>
          <input id="hydro_turbine_flow_max_m3s" name="hydro_turbine_flow_max_m3s" type="number" step="any" value="{html_value(draft_value(hydro, "turbine_flow_max_m3s", 40.0))}">
          <label for="hydro_power_max_mw">Maximum power (MW)</label>
          <input id="hydro_power_max_mw" name="hydro_power_max_mw" type="number" step="any" value="{html_value(draft_value(hydro, "power_max_mw", 3.0))}">
          <label for="hydro_minimum_release_m3s">Minimum release (m3/s)</label>
          <input id="hydro_minimum_release_m3s" name="hydro_minimum_release_m3s" type="number" step="any" value="{html_value(draft_value(hydro, "minimum_release_m3s", 0.0))}">
          <label for="hydro_spill_penalty_usd_per_hm3">Spill penalty (USD/hm3)</label>
          <input id="hydro_spill_penalty_usd_per_hm3" name="hydro_spill_penalty_usd_per_hm3" type="number" step="any" value="{html_value(draft_value(hydro, "spill_penalty_usd_per_hm3", 100.0))}">
          <label for="hydro_terminal_condition">Terminal condition</label>
          <select id="hydro_terminal_condition" name="hydro_terminal_condition">
            <option value="none" {selected_attr(terminal_condition == "none")}>None</option>
            <option value="equal_initial" {selected_attr(terminal_condition == "equal_initial")}>Equal initial</option>
            <option value="min_terminal" {selected_attr(terminal_condition == "min_terminal")}>Minimum terminal</option>
          </select>
          <label for="hydro_terminal_storage_min_hm3">Minimum terminal storage (hm3)</label>
          <input id="hydro_terminal_storage_min_hm3" name="hydro_terminal_storage_min_hm3" type="number" step="any" value="{html_value(hydro.get("terminal_storage_min_hm3"))}">
          <label for="hydro_terminal_water_value_usd_per_hm3">Terminal water value (USD/hm3)</label>
          <input id="hydro_terminal_water_value_usd_per_hm3" name="hydro_terminal_water_value_usd_per_hm3" type="number" step="any" value="{html_value(draft_value(hydro, "terminal_water_value_usd_per_hm3", 0.0))}">
        </div>
        <label for="hydro_generation_curve_json">Generation curve (JSON)</label>
        <textarea id="hydro_generation_curve_json" name="hydro_generation_curve_json" spellcheck="false">{escape(json.dumps(generation_curve, sort_keys=True))}</textarea>
        <label for="hydro_reservoir_curve_json">Reservoir curve (JSON)</label>
        <textarea id="hydro_reservoir_curve_json" name="hydro_reservoir_curve_json" spellcheck="false">{escape(json.dumps(reservoir_curve, sort_keys=True))}</textarea>
      </fieldset>
    """


def draft_value(document: dict[str, Any], key: str, default: Any) -> Any:
    value = document.get(key)
    return default if value is None else value


def render_time_series_source_section(scenario: dict, document: dict) -> str:
    source = active_time_series_source(document)
    source_markup = ""
    if source is not None:
        source_markup = render_time_series_source_detail(scenario, document, source)
    return f"""
        <section class="time-series-source">
          <form method="post" action="/scenarios/{scenario["id"]}/draft/time-series-sources/upload" enctype="multipart/form-data">
            <h2>3. Upload Time Series</h2>
            <p>Use a CSV or XLSX file for prices, demand and asset availability by period.</p>
            <label for="source_file">Time-series file</label>
            <input id="source_file" name="source_file" type="file" accept="text/csv,.csv,.xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet">
            <label for="sheet_name">XLSX sheet (optional)</label>
            <input id="sheet_name" name="sheet_name" placeholder="First sheet by default">
            <button type="submit">Upload Time Series</button>
          </form>
          {source_markup}
        </section>
    """


def render_time_series_source_detail(scenario: dict, document: dict, source: dict) -> str:
    columns = source.get("columns") if isinstance(source.get("columns"), list) else []
    source_id = html_value(source.get("id") or "")
    source_title = "XLSX Time-Series Source" if source.get("kind") == "xlsx" else "CSV Time-Series Source"
    selected_sheet_markup = ""
    if source.get("kind") == "xlsx" and source.get("selected_sheet"):
        selected_sheet_markup = f'<p>Sheet: {escape(str(source.get("selected_sheet")))}</p>'
    mapping = source.get("mapping") if isinstance(source.get("mapping"), dict) else {}
    suggestions = source.get("mapping_suggestions") if isinstance(source.get("mapping_suggestions"), dict) else {}
    validation_markup = render_time_series_validation(source)
    renewable_inputs = render_asset_mapping_inputs(document, source, "renewable", "renewable_available_power_mw")
    load_inputs = render_asset_mapping_inputs(document, source, "load", "load_demand_mw")
    hydro_inputs = render_asset_mapping_inputs(document, source, "hydro", "hydro_inflow_m3s")
    editor_markup = render_time_series_editor(scenario, source)
    return f"""
          <div class="source-detail">
            <h2>{source_title}</h2>
            <p>{escape(str(source.get("original_filename") or "source.csv"))}</p>
            {selected_sheet_markup}
            <p>Columns: {escape(", ".join(str(column) for column in columns))}</p>
            {render_preview_rows(source)}
            {editor_markup}
            <form method="post" action="/scenarios/{scenario["id"]}/draft/time-series-sources/{source_id}/mapping">
              <h2>Column Mapping</h2>
              <div class="form-grid">
                <label for="mapping_timestamp">timestamp</label>
                <input id="mapping_timestamp" name="mapping_timestamp" value="{html_value(mapping_input_value(mapping, suggestions, "timestamp"))}">
                <label for="mapping_duration_hours">duration_hours</label>
                <input id="mapping_duration_hours" name="mapping_duration_hours" value="{html_value(mapping_input_value(mapping, suggestions, "duration_hours"))}">
                <label for="mapping_price_usd_per_mwh">price_usd_per_mwh</label>
                <input id="mapping_price_usd_per_mwh" name="mapping_price_usd_per_mwh" value="{html_value(mapping_input_value(mapping, suggestions, "price_usd_per_mwh"))}">
                <label for="mapping_import_price_usd_per_mwh">import_price_usd_per_mwh</label>
                <input id="mapping_import_price_usd_per_mwh" name="mapping_import_price_usd_per_mwh" value="{html_value(mapping_input_value(mapping, suggestions, "import_price_usd_per_mwh"))}">
                <label for="mapping_export_price_usd_per_mwh">export_price_usd_per_mwh</label>
                <input id="mapping_export_price_usd_per_mwh" name="mapping_export_price_usd_per_mwh" value="{html_value(mapping_input_value(mapping, suggestions, "export_price_usd_per_mwh"))}">
                {renewable_inputs}
                {load_inputs}
                {hydro_inputs}
              </div>
              <button type="submit">Save Mapping</button>
            </form>
            {validation_markup}
          </div>
    """


def render_time_series_editor(scenario: dict, source: dict) -> str:
    source_id = quote(str(source.get("id") or ""), safe="")
    endpoint = f'/api/scenarios/{scenario["id"]}/draft/time-series-sources/{source_id}/rows'
    editor = f"""
        <div class="time-series-editor-shell" data-rows-endpoint="{escape(endpoint, quote=True)}">
          <button type="button" class="edit-time-series-button">Edit Table</button>
          <div class="time-series-editor" hidden>
            <div class="time-series-editor-header">
              <div>
                <h2>Edit Time-Series Values</h2>
                <p>Edit individual cells, or paste a column/range copied from Excel into the first destination cell.</p>
              </div>
              <button type="button" class="button-secondary close-time-series-editor">Close</button>
            </div>
            <div class="table-scroll editable-table-scroll">
              <table class="editable-time-series-table">
                <thead><tr></tr></thead>
                <tbody></tbody>
              </table>
            </div>
            <div class="time-series-editor-actions">
              <button type="button" class="save-time-series-rows">Save Changes</button>
              <span class="time-series-editor-status" role="status"></span>
            </div>
          </div>
        </div>
    """
    script = r"""
        <script>
          (() => {
            const shell = document.currentScript.previousElementSibling;
            const editor = shell.querySelector('.time-series-editor');
            const editButton = shell.querySelector('.edit-time-series-button');
            const closeButton = shell.querySelector('.close-time-series-editor');
            const saveButton = shell.querySelector('.save-time-series-rows');
            const status = shell.querySelector('.time-series-editor-status');
            const table = shell.querySelector('.editable-time-series-table');
            const headerRow = table.querySelector('thead tr');
            const tableBody = table.querySelector('tbody');
            const endpoint = shell.dataset.rowsEndpoint;
            let columns = [];
            let loaded = false;

            const responseError = async (response) => {
              let body = {};
              try { body = await response.json(); } catch (_error) { /* no JSON body */ }
              return body.detail || body.message || `Request failed (${response.status})`;
            };

            const renderRows = (payload) => {
              columns = payload.columns;
              headerRow.replaceChildren(...columns.map((column) => {
                const th = document.createElement('th');
                th.textContent = column;
                return th;
              }));
              tableBody.replaceChildren(...payload.rows.map((row, rowIndex) => {
                const tr = document.createElement('tr');
                columns.forEach((column, columnIndex) => {
                  const td = document.createElement('td');
                  td.contentEditable = 'true';
                  td.spellcheck = false;
                  td.dataset.row = String(rowIndex);
                  td.dataset.column = String(columnIndex);
                  td.textContent = row[column] ?? '';
                  tr.appendChild(td);
                });
                return tr;
              }));
            };

            const loadRows = async () => {
              status.textContent = 'Loading table...';
              const response = await fetch(endpoint, { headers: { Accept: 'application/json' } });
              if (!response.ok) throw new Error(await responseError(response));
              renderRows(await response.json());
              loaded = true;
              status.textContent = '';
            };

            editButton.addEventListener('click', async () => {
              editor.hidden = false;
              editButton.hidden = true;
              if (loaded) return;
              try { await loadRows(); } catch (error) { status.textContent = error.message; }
            });

            closeButton.addEventListener('click', () => {
              editor.hidden = true;
              editButton.hidden = false;
            });

            tableBody.addEventListener('paste', (event) => {
              const startCell = event.target.closest('td[contenteditable="true"]');
              if (!startCell) return;
              const clipboardText = event.clipboardData.getData('text/plain');
              if (!clipboardText) return;
              event.preventDefault();
              const lines = clipboardText.replace(/\r/g, '').split('\n');
              if (lines.at(-1) === '') lines.pop();
              const pastedCells = lines.map((line) => line.split('\t'));
              const startRow = Number(startCell.dataset.row);
              const startColumn = Number(startCell.dataset.column);
              pastedCells.forEach((values, rowOffset) => {
                values.forEach((value, columnOffset) => {
                  const target = tableBody.querySelector(
                    `td[data-row="${startRow + rowOffset}"][data-column="${startColumn + columnOffset}"]`
                  );
                  if (target) target.textContent = value;
                });
              });
            });

            tableBody.addEventListener('keydown', (event) => {
              const cell = event.target.closest('td[contenteditable="true"]');
              if (!cell || event.key !== 'Enter') return;
              event.preventDefault();
              const nextCell = tableBody.querySelector(
                `td[data-row="${Number(cell.dataset.row) + 1}"][data-column="${cell.dataset.column}"]`
              );
              if (nextCell) nextCell.focus();
            });

            saveButton.addEventListener('click', async () => {
              const rows = Array.from(tableBody.rows).map((row) => {
                const values = {};
                columns.forEach((column, index) => {
                  values[column] = row.cells[index].textContent.replace(/\u00a0/g, ' ');
                });
                return values;
              });
              saveButton.disabled = true;
              status.textContent = 'Saving changes...';
              try {
                const response = await fetch(endpoint, {
                  method: 'PUT',
                  headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
                  body: JSON.stringify({ rows }),
                });
                if (!response.ok) throw new Error(await responseError(response));
                status.textContent = 'Changes saved.';
                window.location.reload();
              } catch (error) {
                status.textContent = error.message;
                saveButton.disabled = false;
              }
            });
          })();
        </script>
    """
    return editor + script


def active_time_series_source(document: dict) -> dict | None:
    time_series = document.get("time_series") if isinstance(document.get("time_series"), dict) else {}
    sources = time_series.get("sources") if isinstance(time_series.get("sources"), list) else []
    active_source_id = time_series.get("active_source_id")
    for source in sources:
        if isinstance(source, dict) and source.get("id") == active_source_id:
            return source
    for source in sources:
        if isinstance(source, dict):
            return source
    return None


def mapping_input_value(mapping: dict, suggestions: dict, key: str) -> Any:
    if key in mapping:
        return mapping.get(key) or ""
    return suggestions.get(key) or ""


def render_preview_rows(source: dict) -> str:
    rows = source.get("preview_rows") if isinstance(source.get("preview_rows"), list) else []
    columns = source.get("columns") if isinstance(source.get("columns"), list) else []
    if not rows or not columns:
        return ""
    table = {
        "columns": columns,
        "rows": rows,
    }
    return render_result_table(table)


def render_asset_mapping_inputs(document: dict, source: dict, asset_type: str, mapping_key: str) -> str:
    assets = document.get("assets") if isinstance(document.get("assets"), list) else []
    mapping = source.get("mapping") if isinstance(source.get("mapping"), dict) else {}
    suggestions = source.get("mapping_suggestions") if isinstance(source.get("mapping_suggestions"), dict) else {}
    mapped_assets = mapping.get(mapping_key) if isinstance(mapping.get(mapping_key), dict) else {}
    suggested_assets = suggestions.get(mapping_key) if isinstance(suggestions.get(mapping_key), dict) else {}
    pieces: list[str] = []
    for asset in assets:
        if not isinstance(asset, dict) or asset.get("type") != asset_type:
            continue
        asset_id = str(asset.get("id") or "")
        input_name = f"mapping_{mapping_key}__{asset_id}"
        value = mapping_input_value(mapped_assets, suggested_assets, asset_id)
        pieces.append(
            f'<label for="{html_value(input_name)}">{escape(mapping_key)}.{escape(asset_id)}</label>'
            f'<input id="{html_value(input_name)}" name="{html_value(input_name)}" value="{html_value(value)}">'
        )
    return "".join(pieces)


def render_time_series_validation(source: dict) -> str:
    validation = source.get("validation") if isinstance(source.get("validation"), dict) else None
    if validation is None:
        return ""
    if validation.get("ok"):
        row_count = len(source.get("validated_rows") if isinstance(source.get("validated_rows"), list) else [])
        return (
            '<section class="notice">'
            "<h2>Time-Series Validation</h2>"
            f"<p>Valid mapped rows: {row_count}</p>"
            "</section>"
        )
    errors = validation.get("errors") if isinstance(validation.get("errors"), list) else []
    items = "".join(f"<li>{escape(str(error))}</li>" for error in errors)
    category = human_error_category(str(validation.get("error_category") or "python_validation"))
    return (
        '<section class="notice error">'
        f"<h2>Time-Series Validation: {escape(category)}</h2>"
        f"<ul>{items}</ul>"
        "</section>"
    )


def human_error_category(error_category: str) -> str:
    labels = {
        "source_file": "Source-file Error",
        "mapping": "Mapping Error",
        "python_validation": "Python Validation Error",
        "julia_validation": "Julia Validation Error",
    }
    return labels.get(error_category, "Validation Error")


def render_generated_preview(document: dict | None) -> str:
    if document is None:
        return ""
    try:
        preview_text = json.dumps(generate_system_case_from_draft(document), indent=2, sort_keys=True)
    except DraftGenerationError:
        return ""
    return (
        '<details class="preview-block advanced-section">'
        "<summary>Generated system case preview</summary>"
        f'<textarea id="generated_system_case_preview" readonly spellcheck="false">{escape(preview_text)}</textarea>'
        "</details>"
    )


def render_generated_validation_section(
    scenario: dict,
    document: dict | None,
    result: ValidationResult | None = None,
) -> str:
    if document is None:
        return ""
    try:
        current_system_case = generate_system_case_from_draft(document)
    except DraftGenerationError:
        return ""

    result_markup = ""
    if result is not None:
        status = "Valid" if result.ok else "Invalid"
        css_class = "notice" if result.ok else "notice error"
        result_markup = (
            f'<section class="{css_class}">'
            "<h2>Generated System Case Validation</h2>"
            f"<p>{status}: {escape(result.message)}</p>"
            "</section>"
        )
    promote_markup = ""
    if draft_has_current_successful_generated_validation(document, current_system_case):
        promote_markup = (
            f'<form method="post" action="/scenarios/{scenario["id"]}/draft/generated-system-case/promote" '
            'class="inline-form">'
            '<button type="submit">Promote To Scenario Version</button>'
            "</form>"
        )
    return (
        f'<form method="post" action="/scenarios/{scenario["id"]}/draft/generated-system-case/validate" '
        'class="inline-form">'
        "<h2>4. Validate Scenario</h2>"
        '<button type="submit">Validate Scenario</button>'
        "</form>"
        f"{result_markup}"
        f"{promote_markup}"
    )


def first_asset_of_type(assets: list, asset_type: str) -> dict[str, Any]:
    for asset in assets:
        if isinstance(asset, dict) and asset.get("type") == asset_type:
            return asset
    return {}


def html_value(value: Any) -> str:
    if value is None:
        return ""
    return escape(str(value), quote=True)


def checked_attr(value: Any) -> str:
    return "checked" if bool(value) else ""


def selected_attr(value: Any) -> str:
    return "selected" if bool(value) else ""


def form_checkbox(form: Any, name: str) -> bool:
    return name in form


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
    if next_path in {"/login", "/bootstrap", "/logout"}:
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


def render_auth_shell(title: str, content: str) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)} - BESS</title>
  <style>
    :root {{
      color-scheme: light;
      font-family: Arial, sans-serif;
      --ink: #18212f;
      --muted: #606a78;
      --line: #d7dde6;
      --surface: #f6f8fb;
      --accent: #0f766e;
      --error: #b42318;
    }}
    body {{
      margin: 0;
      color: var(--ink);
      background: white;
    }}
    main {{
      width: min(440px, calc(100vw - 32px));
      margin: 12vh auto 0;
    }}
    h1 {{
      font-size: 28px;
      line-height: 1.2;
      margin: 0 0 8px;
    }}
    p {{
      color: var(--muted);
      margin: 0 0 18px;
    }}
    form {{
      display: grid;
      gap: 10px;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 16px;
      background: var(--surface);
    }}
    label {{
      color: var(--muted);
      font-size: 13px;
      font-weight: 700;
    }}
    input {{
      box-sizing: border-box;
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 10px;
      color: var(--ink);
      background: white;
    }}
    button {{
      justify-self: start;
      border: 0;
      border-radius: 6px;
      padding: 10px 14px;
      background: var(--accent);
      color: white;
      font-weight: 700;
      cursor: pointer;
    }}
    .notice {{
      border-left: 4px solid var(--error);
      background: #fff4f2;
      margin-bottom: 14px;
      padding: 12px 14px;
    }}
  </style>
</head>
<body>
  <main>{content}</main>
</body>
</html>"""


def render_login_page(error_message: str = "", *, next_path: str = "", email: str = "") -> str:
    error_markup = f'<section class="notice">{escape(error_message)}</section>' if error_message else ""
    safe_next = html_value(safe_internal_next_path(next_path))
    return render_auth_shell(
        "Login",
        f"""
        <h1>Sign In</h1>
        <p>Use a local account to enter the application.</p>
        {error_markup}
        <form method="post" action="/login">
          <input type="hidden" name="next" value="{safe_next}">
          <label for="email">Email</label>
          <input id="email" name="email" type="email" autocomplete="username" value="{html_value(email)}" required>
          <label for="password">Password</label>
          <input id="password" name="password" type="password" autocomplete="current-password" required>
          <button type="submit">Sign In</button>
        </form>
        """,
    )


def render_bootstrap_page(error_message: str = "") -> str:
    error_markup = f'<section class="notice">{escape(error_message)}</section>' if error_message else ""
    return render_auth_shell(
        "Bootstrap Admin",
        f"""
        <h1>Bootstrap Admin</h1>
        <p>Create the first internal admin. This path closes after the first user exists.</p>
        {error_markup}
        <form method="post" action="/bootstrap">
          <label for="email">Email</label>
          <input id="email" name="email" type="email" autocomplete="username" required>
          <label for="display_name">Display Name</label>
          <input id="display_name" name="display_name" type="text" autocomplete="name">
          <label for="password">Password</label>
          <input id="password" name="password" type="password" autocomplete="new-password" required>
          <button type="submit">Create Admin</button>
        </form>
        """,
    )


def render_forbidden_page(message: str = "You do not have access to this page.") -> str:
    return render_auth_shell(
        "Forbidden",
        f"""
        <h1>Forbidden</h1>
        <p>{escape(message)}</p>
        """,
    )


def render_client_home_page(user: dict[str, Any] | None, projects: list[dict[str, Any]]) -> str:
    email = user["email"] if user else ""
    project_items = "".join(
        f'<li><a href="/client/projects/{project["id"]}">{escape(project["name"])}</a>'
        f'<span>{escape(project["description"])}</span></li>'
        for project in projects
    )
    if not project_items:
        project_items = '<li class="empty">No assigned projects yet</li>'
    return render_auth_shell(
        "Client Portal",
        f"""
        <h1>Client Portal</h1>
        <p>Signed in as {escape(email)}.</p>
        <section>
          <h2>Projects</h2>
          <ul class="entity-list">{project_items}</ul>
        </section>
        <form method="post" action="/logout">
          <button type="submit">Log Out</button>
        </form>
        """,
    )


def render_client_project_page(project: dict[str, Any], publications: list[dict[str, Any]]) -> str:
    publication_items = "".join(
        f'<li><a href="/client/projects/{project["id"]}/publications/{publication["id"]}">'
        f'{escape(publication["public_title"])}</a>'
        f'<span>{escape(publication.get("published_at") or "")}</span></li>'
        for publication in publications
    )
    if not publication_items:
        publication_items = '<li class="empty">No published results yet.</li>'
    return render_auth_shell(
        project["name"],
        f"""
        <nav><a href="/client">Client Portal</a></nav>
        <h1>{escape(project["name"])}</h1>
        <p>{escape(project["description"])}</p>
        <section>
          <h2>Publications</h2>
          <ul class="entity-list">{publication_items}</ul>
        </section>
        <form method="post" action="/logout">
          <button type="submit">Log Out</button>
        </form>
        """,
    )


def render_client_publication_page(
    project: dict[str, Any],
    scenario: dict[str, Any],
    version: dict[str, Any],
    run: dict[str, Any],
    publication: dict[str, Any],
    results: dict | None,
    results_error: str = "",
    downloads: list[dict[str, Any]] | None = None,
) -> str:
    metadata = {
        "Published At": publication.get("published_at") or "",
        "Scenario": scenario["name"],
        "Scenario Version": version["version_number"],
        "Run Date": run.get("finished_at") or run.get("created_at") or "",
        "Run Status": run["status"],
    }
    return render_auth_shell(
        publication["public_title"],
        f"""
        <nav><a href="/client">Client Portal</a> / <a href="/client/projects/{project['id']}">{escape(project['name'])}</a></nav>
        <h1>{escape(publication["public_title"])}</h1>
        <p>{escape(publication["analyst_notes"])}</p>
        {render_key_value_table(metadata)}
        {render_client_dashboard_results(results, results_error)}
        {render_client_downloads(downloads or [])}
        <form method="post" action="/logout">
          <button type="submit">Log Out</button>
        </form>
        """,
    )


def render_client_downloads(downloads: list[dict[str, Any]]) -> str:
    if not downloads:
        items = '<li class="empty">No downloads enabled for this publication.</li>'
    else:
        items = "".join(
            f'<li><a href="{escape(download["download_url"])}">{escape(download["display_name"])}</a>'
            f'<span>{escape(download["artifact_type"])} | {escape(download["media_type"])} | '
            f'{download["byte_size"]} bytes</span></li>'
            for download in downloads
        )
    return f"""
        <section>
          <h2>Downloads</h2>
          <ul class="entity-list">{items}</ul>
        </section>
    """


def render_admin_users_page(users: list[dict[str, Any]], error_message: str = "") -> str:
    error_markup = f'<p class="error">{escape(error_message)}</p>' if error_message else ""
    user_items = "".join(
        f'<li><span>{escape(user["email"])} - {escape(user["role"])} - '
        f'{"active" if user["is_active"] else "deactivated"}</span>'
        + (
            f'<form method="post" action="/admin/users/{user["id"]}/deactivate">'
            '<button type="submit">Deactivate</button></form>'
            if user["is_active"]
            else ""
        )
        + "</li>"
        for user in users
    )
    if not user_items:
        user_items = '<li class="empty">No users yet</li>'
    return render_app_page(
        "Users",
        f"""
        <nav><a href="/projects">Projects</a></nav>
        <section class="toolbar">
          <h1>Users</h1>
        </section>
        {error_markup}
        <section class="split">
          <div>
            <h2>User List</h2>
            <ul class="entity-list">{user_items}</ul>
          </div>
          <form method="post" action="/admin/users">
            <h2>New User</h2>
            <label for="email">Email</label>
            <input id="email" name="email" type="email" required>
            <label for="display_name">Display Name</label>
            <input id="display_name" name="display_name">
            <label for="role">Role</label>
            <select id="role" name="role" required>
              <option value="client">client</option>
              <option value="analyst">analyst</option>
              <option value="admin">admin</option>
            </select>
            <label for="password">Password</label>
            <input id="password" name="password" type="password" required>
            <button type="submit">Create User</button>
          </form>
        </section>
        """,
    )


def public_user_dict(user: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": user["id"],
        "email": user["email"],
        "display_name": user["display_name"],
        "role": user["role"],
        "is_active": user["is_active"],
        "created_at": user["created_at"],
        "updated_at": user["updated_at"],
        "created_by": user["created_by"],
        "deactivated_at": user["deactivated_at"],
    }


def render_app_page(title: str, content: str) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)} - BESS Analyst App</title>
  <style>
    :root {{
      color-scheme: light;
      font-family: Arial, sans-serif;
      --ink: #18212f;
      --muted: #606a78;
      --line: #d7dde6;
      --surface: #f6f8fb;
      --accent: #0f766e;
      --error: #b42318;
    }}
    body {{
      margin: 0;
      color: var(--ink);
      background: white;
    }}
    main {{
      width: min(1180px, calc(100vw - 32px));
      margin: 0 auto;
      padding: 28px 0 40px;
    }}
    nav {{
      margin-bottom: 18px;
    }}
    a {{
      color: var(--accent);
      font-weight: 700;
      text-decoration: none;
    }}
    h1 {{
      font-size: 28px;
      line-height: 1.2;
      margin: 0;
    }}
    h2 {{
      font-size: 16px;
      margin: 0 0 12px;
    }}
    p {{
      color: var(--muted);
      margin: 6px 0 0;
    }}
    .toolbar {{
      border-bottom: 1px solid var(--line);
      margin-bottom: 24px;
      padding-bottom: 18px;
    }}
    .run-actions {{
      display: flex;
      gap: 8px;
      margin-top: 14px;
    }}
    .split {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) minmax(280px, 360px);
      gap: 28px;
      align-items: start;
    }}
    .split.wide {{
      grid-template-columns: minmax(280px, 380px) minmax(0, 1fr);
    }}
    .entity-list {{
      list-style: none;
      margin: 0;
      padding: 0;
      border-top: 1px solid var(--line);
    }}
    .entity-list li {{
      display: grid;
      gap: 4px;
      border-bottom: 1px solid var(--line);
      padding: 12px 0;
    }}
    .entity-list span,
    .empty {{
      color: var(--muted);
      font-size: 14px;
    }}
    .version-runs {{
      border-left: 3px solid var(--line);
      margin: 8px 0;
      padding: 8px 0 8px 12px;
    }}
    .version-runs h3 {{
      font-size: 13px;
      margin: 0 0 8px;
    }}
    .version-run-list {{
      display: grid;
      gap: 8px;
      list-style: none;
      margin: 0;
      padding: 0;
    }}
    .version-run-list li {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      border: 0;
      padding: 0;
    }}
    .version-run-list li div {{
      display: grid;
      gap: 2px;
      min-width: 0;
    }}
    .version-run-list .button-link {{
      flex: 0 0 auto;
      padding: 7px 10px;
    }}
    form {{
      display: grid;
      gap: 10px;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 16px;
      background: var(--surface);
    }}
    .structured-form {{
      margin-bottom: 18px;
    }}
    .asset-builder {{
      display: grid;
      gap: 14px;
      border: 1px solid var(--line);
      border-radius: 8px;
      margin-bottom: 18px;
      padding: 18px;
    }}
    .asset-list {{
      display: grid;
      gap: 8px;
    }}
    .asset-card {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 10px 12px;
      background: var(--surface);
    }}
    .asset-card div {{
      display: grid;
      gap: 3px;
    }}
    .asset-card span {{
      color: var(--muted);
      font-size: 13px;
    }}
    .asset-add-form {{
      display: grid;
      grid-template-columns: minmax(180px, 1fr) auto;
      align-items: end;
      gap: 8px 12px;
      border: 0;
      padding: 0;
      background: transparent;
    }}
    .asset-add-form label {{
      grid-column: 1 / -1;
    }}
    .asset-settings {{
      display: grid;
      gap: 12px;
      border: 1px solid var(--line);
      border-radius: 6px;
      margin: 8px 0;
      padding: 16px;
      background: white;
    }}
    .asset-settings legend {{
      padding: 0 8px;
      color: var(--ink);
      font-weight: 700;
    }}
    .asset-empty {{
      border: 1px dashed var(--line);
      border-radius: 6px;
      padding: 16px;
    }}
    .form-grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(180px, 1fr));
      gap: 10px 14px;
      align-items: end;
    }}
    .inline-form {{
      display: block;
      border: 0;
      padding: 0;
      background: transparent;
    }}
    label {{
      color: var(--muted);
      font-size: 13px;
      font-weight: 700;
    }}
    input,
    select,
    textarea {{
      box-sizing: border-box;
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 10px;
      color: var(--ink);
      background: white;
    }}
    input[type="checkbox"] {{
      width: auto;
    }}
    .checkbox-row {{
      display: flex;
      align-items: center;
      gap: 8px;
    }}
    textarea {{
      min-height: 116px;
      resize: vertical;
    }}
    #system_case_json,
    #structured_draft_json {{
      min-height: 420px;
      font: 13px/1.45 Consolas, "Liberation Mono", monospace;
    }}
    button {{
      justify-self: start;
      border: 0;
      border-radius: 6px;
      padding: 10px 14px;
      background: var(--accent);
      color: white;
      font-weight: 700;
      cursor: pointer;
    }}
    .button-secondary {{
      border: 1px solid var(--line);
      padding: 7px 10px;
      background: white;
      color: var(--ink);
    }}
    .button-danger {{
      border: 1px solid #f1b7b2;
      padding: 7px 10px;
      background: #fff4f2;
      color: var(--error);
    }}
    .button-link {{
      display: inline-block;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 9px 12px;
      background: white;
      color: var(--ink);
    }}
    .advanced-section {{
      border: 1px solid var(--line);
      border-radius: 6px;
      margin: 12px 0;
      padding: 12px;
      background: white;
    }}
    .advanced-section summary {{
      cursor: pointer;
      color: var(--ink);
      font-weight: 700;
    }}
    .advanced-section[open] summary {{
      margin-bottom: 14px;
    }}
    .details-fields {{
      margin-bottom: 12px;
    }}
    .notice {{
      border-left: 4px solid var(--accent);
      background: #effcf8;
      margin-bottom: 18px;
      padding: 12px 14px;
    }}
    .preview-block {{
      margin-bottom: 18px;
    }}
    .preview-block textarea {{
      min-height: 260px;
      font: 13px/1.45 Consolas, "Liberation Mono", monospace;
    }}
    .time-series-editor-shell {{
      margin: 12px 0 20px;
    }}
    .time-series-editor {{
      border: 1px solid var(--line);
      border-radius: 8px;
      margin-top: 10px;
      padding: 14px;
      background: var(--surface);
    }}
    .time-series-editor-header,
    .time-series-editor-actions {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
    }}
    .time-series-editor-header {{
      align-items: flex-start;
      margin-bottom: 12px;
    }}
    .time-series-editor-header p {{
      margin-top: 3px;
    }}
    .editable-table-scroll {{
      max-height: 360px;
      margin-bottom: 12px;
      background: white;
    }}
    .editable-time-series-table td[contenteditable="true"] {{
      min-width: 110px;
      cursor: text;
      background: white;
    }}
    .editable-time-series-table td[contenteditable="true"]:focus {{
      outline: 2px solid var(--accent);
      outline-offset: -2px;
      background: #effcf8;
    }}
    .time-series-editor-status {{
      color: var(--muted);
      font-size: 13px;
    }}
    .notice.error {{
      border-left-color: var(--error);
      background: #fff4f2;
    }}
    .details dl {{
      display: grid;
      grid-template-columns: minmax(92px, 140px) minmax(0, 1fr);
      gap: 10px 16px;
      margin: 0;
      max-width: 760px;
    }}
    .details dt {{
      color: var(--muted);
      font-weight: 700;
    }}
    .details dd {{
      margin: 0;
      overflow-wrap: anywhere;
    }}
    .results-section {{
      margin-top: 26px;
    }}
    .chart-grid {{
      margin-bottom: 24px;
    }}
    .chart-panel {{
      min-width: 0;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 12px;
      background: white;
    }}
    .chart-panel h3 {{
      font-size: 14px;
      line-height: 1.3;
      margin: 0 0 10px;
    }}
    .chart-panel p {{
      font-size: 13px;
    }}
    .plot-builder-toolbar,
    .configurable-plot-header {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 12px;
    }}
    .plot-builder-toolbar p {{
      margin: 0;
    }}
    .plot-favorites {{
      display: grid;
      grid-template-columns: minmax(180px, 1fr) auto minmax(180px, 1fr) auto auto;
      gap: 8px;
      align-items: end;
      border: 1px solid var(--line);
      border-radius: 8px;
      margin-bottom: 16px;
      padding: 12px;
      background: var(--surface);
    }}
    .plot-favorites label {{
      display: grid;
      gap: 5px;
    }}
    .favorite-feedback {{
      grid-column: 1 / -1;
      min-height: 18px;
      color: var(--muted);
      font-size: 12px;
    }}
    .configurable-plot {{
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 14px;
      margin-bottom: 18px;
      background: white;
    }}
    .plot-title-input {{
      max-width: 420px;
      font-size: 16px;
      font-weight: 700;
    }}
    .plot-controls {{
      display: grid;
      grid-template-columns: repeat(2, minmax(240px, 1fr));
      gap: 12px;
      margin-bottom: 10px;
    }}
    .series-picker {{
      position: relative;
    }}
    .series-picker summary {{
      cursor: pointer;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 10px 12px;
      color: var(--ink);
      font-weight: 700;
      background: var(--surface);
    }}
    .series-picker-panel {{
      position: absolute;
      z-index: 20;
      width: min(520px, calc(100vw - 64px));
      max-height: 360px;
      overflow: auto;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 10px;
      background: white;
      box-shadow: 0 12px 28px rgba(24, 33, 47, 0.16);
    }}
    .series-filter {{
      position: sticky;
      top: 0;
      z-index: 1;
      margin-bottom: 8px;
      background: white;
    }}
    .series-group-block {{
      border-top: 1px solid var(--line);
      margin-top: 8px;
      padding-top: 8px;
    }}
    .series-group-header {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
      margin-bottom: 4px;
    }}
    .series-group-label {{
      color: var(--muted);
      font-size: 11px;
      font-weight: 800;
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }}
    .series-group-actions {{
      display: flex;
      gap: 5px;
    }}
    .series-group-action {{
      border: 1px solid var(--line);
      padding: 4px 7px;
      background: white;
      color: var(--accent);
      font-size: 11px;
    }}
    .series-option {{
      display: flex;
      align-items: flex-start;
      gap: 8px;
      padding: 5px 2px;
      color: var(--ink);
      font-size: 12px;
      font-weight: 400;
    }}
    .series-option input {{
      width: auto;
      margin-top: 2px;
    }}
    .plotly-chart {{
      width: 100%;
      min-height: 500px;
    }}
    .table-scroll {{
      border: 1px solid var(--line);
      border-radius: 6px;
      max-height: 420px;
      overflow: auto;
      margin-bottom: 24px;
    }}
    table {{
      width: 100%;
      min-width: 760px;
      border-collapse: collapse;
      font-size: 13px;
    }}
    th,
    td {{
      border-bottom: 1px solid var(--line);
      padding: 8px 10px;
      text-align: left;
      white-space: nowrap;
    }}
    thead th {{
      position: sticky;
      top: 0;
      z-index: 2;
      background: var(--surface);
      color: var(--muted);
      font-weight: 700;
    }}
    tbody tr:last-child td {{
      border-bottom: 0;
    }}
    @media (max-width: 760px) {{
      .split,
      .split.wide {{
        grid-template-columns: 1fr;
      }}
      .form-grid {{
        grid-template-columns: 1fr;
      }}
      .asset-add-form {{
        grid-template-columns: 1fr;
      }}
      .plot-controls {{
        grid-template-columns: 1fr;
      }}
      .plot-favorites {{
        grid-template-columns: 1fr;
      }}
      .favorite-feedback {{
        grid-column: 1;
      }}
      .details dl {{
        grid-template-columns: 1fr;
      }}
    }}
  </style>
</head>
<body>
  <main>
    {content}
  </main>
</body>
</html>"""


def render_run_page(
    run: dict,
    artifacts: list[dict] | None = None,
    results: dict | None = None,
    results_error: str = "",
    publications: list[dict] | None = None,
    dashboard_templates: list[dict[str, Any]] | None = None,
    publication_artifacts: list[dict] | None = None,
    scenario_id: int | None = None,
) -> str:
    artifact_items = render_artifact_items(artifacts or [])
    publication_markup = render_publications_section(
        run,
        publications or [],
        dashboard_templates or [],
        publication_artifacts or [],
    )
    results_markup = render_results_section(results, results_error)
    parameters_link = (
        f'<a class="button-link" href="/scenarios/{scenario_id}/draft">Back to parameters</a>'
        if scenario_id is not None
        else ""
    )
    return render_app_page(
        f"Run {run['id']}",
        f"""
        <nav><a href="/api/scenario-versions/{run["scenario_version_id"]}">Scenario Version</a></nav>
        <section class="toolbar">
          <h1>Run {run["id"]}</h1>
          <p>Status: <strong id="run-status">{escape(run["status"])}</strong></p>
          <div class="run-actions">{parameters_link}</div>
        </section>
        <section class="details">
          <dl>
            <dt>Created</dt><dd id="run-created-at">{escape(str(run["created_at"]))}</dd>
            <dt>Started</dt><dd id="run-started-at">{escape(str(run["started_at"] or ""))}</dd>
            <dt>Finished</dt><dd id="run-finished-at">{escape(str(run["finished_at"] or ""))}</dd>
            <dt>Exit Code</dt><dd id="run-exit-code">{escape(str(run["exit_code"] if run["exit_code"] is not None else ""))}</dd>
            <dt>Error</dt><dd id="run-error-message">{escape(str(run["error_message"] or ""))}</dd>
          </dl>
        </section>
        <section>
          <h2>Artifacts</h2>
          <ul class="entity-list" id="artifact-list">{artifact_items}</ul>
        </section>
        {publication_markup}
        {results_markup}
        <script>
          const initialRunStatus = {json.dumps(run["status"])};

          async function pollRun() {{
            const response = await fetch("/api/runs/{run["id"]}");
            if (!response.ok) return;
            const payload = await response.json();
            const run = payload.run;
            document.getElementById("run-status").textContent = run.status;
            document.getElementById("run-started-at").textContent = run.started_at || "";
            document.getElementById("run-finished-at").textContent = run.finished_at || "";
            document.getElementById("run-exit-code").textContent = run.exit_code ?? "";
            document.getElementById("run-error-message").textContent = run.error_message || "";
            if (run.status === "queued" || run.status === "running") {{
              window.setTimeout(pollRun, 1000);
            }} else if (initialRunStatus === "queued" || initialRunStatus === "running") {{
              window.location.reload();
            }}
          }}
          if (initialRunStatus === "queued" || initialRunStatus === "running") {{
            window.setTimeout(pollRun, 1000);
          }}
        </script>
        """,
    )


def render_publications_section(
    run: dict,
    publications: list[dict],
    dashboard_templates: list[dict[str, Any]],
    artifacts: list[dict],
) -> str:
    if run["status"] != "succeeded" and not publications:
        return ""

    publication_items = "".join(
        render_publication_item(publication, dashboard_templates, artifacts)
        for publication in publications
    )
    if not publication_items:
        publication_items = '<li class="empty">No publication drafts yet</li>'

    create_form = ""
    if run["status"] == "succeeded":
        create_form = render_publication_form(
            f"/runs/{run['id']}/publications",
            dashboard_templates,
            artifacts,
        )

    return f"""
        <section class="split results-section">
          <div>
            <h2>Publication Drafts</h2>
            <ul class="entity-list">{publication_items}</ul>
          </div>
          {create_form}
        </section>
    """


def render_publication_item(
    publication: dict,
    dashboard_templates: list[dict[str, Any]],
    artifacts: list[dict],
) -> str:
    allowed_text = ", ".join(publication["allowed_artifact_types"]) or "no downloads"
    preview_link = f'<a href="/publications/{publication["id"]}/preview">Preview as Client</a>'
    state_form = ""
    if publication["status"] in {"draft", "unpublished"}:
        state_form = (
            f'<form class="inline-form" method="post" action="/publications/{publication["id"]}/publish">'
            '<button type="submit">Publish Publication</button></form>'
        )
    elif publication["status"] == "published":
        state_form = (
            f'<form class="inline-form" method="post" action="/publications/{publication["id"]}/unpublish">'
            '<button type="submit">Unpublish Publication</button></form>'
        )
    edit_form = ""
    if publication["status"] == "draft":
        edit_form = render_publication_form(
            f"/publications/{publication['id']}",
            dashboard_templates,
            artifacts,
            publication,
        )
    return (
        "<li>"
        f"<strong>{escape(publication['public_title'])}</strong>"
        f"<span>{escape(publication['status'])} | {escape(allowed_text)}</span>"
        f"<span>{escape(publication['analyst_notes'])}</span>"
        f"{preview_link}"
        f"{state_form}"
        f"{edit_form}"
        "</li>"
    )


def render_publication_form(
    action: str,
    dashboard_templates: list[dict[str, Any]],
    artifacts: list[dict],
    publication: dict | None = None,
) -> str:
    publication = publication or {}
    title = "Edit Publication Draft" if publication.get("id") else "New Publication Draft"
    button = "Update Publication" if publication.get("id") else "Create Publication"
    selected_template_id = publication.get("dashboard_template_id")
    template_options = "".join(
        f'<option value="{template["id"]}" {selected_attr(template["id"] == selected_template_id)}>'
        f'{escape(template["name"])}</option>'
        for template in dashboard_templates
    )
    if not template_options:
        template_options = '<option value="">No dashboard templates available</option>'

    selected_artifacts = set(
        publication.get("allowed_artifact_types")
        if publication.get("allowed_artifact_types") is not None
        else DEFAULT_PUBLICATION_ARTIFACT_TYPES
    )
    artifact_rows = "".join(
        render_artifact_allowlist_row(artifact["artifact_type"], artifact["display_name"], selected_artifacts)
        for artifact in artifacts
    )
    if not artifact_rows:
        artifact_rows = '<p>No run artifacts registered yet.</p>'

    return f"""
          <form method="post" action="{escape(action, quote=True)}">
            <h2>{title}</h2>
            <label for="publication_template_{publication.get('id', 'new')}">Dashboard Template</label>
            <select id="publication_template_{publication.get('id', 'new')}" name="dashboard_template_id" required>
              {template_options}
            </select>
            <label for="publication_title_{publication.get('id', 'new')}">Public Title</label>
            <input id="publication_title_{publication.get('id', 'new')}" name="public_title" value="{html_value(publication.get('public_title', ''))}" required>
            <label for="publication_notes_{publication.get('id', 'new')}">Analyst Notes</label>
            <textarea id="publication_notes_{publication.get('id', 'new')}" name="analyst_notes">{escape(str(publication.get('analyst_notes') or ''))}</textarea>
            <h2>Allowed Downloads</h2>
            {artifact_rows}
            <button type="submit">{button}</button>
          </form>
    """


def render_artifact_allowlist_row(
    artifact_type: str,
    display_name: str,
    selected_artifacts: set[str],
) -> str:
    return (
        '<label class="checkbox-row">'
        f'<input type="checkbox" name="allowed_artifact_types" value="{html_value(artifact_type)}" '
        f'{checked_attr(artifact_type in selected_artifacts)}>'
        f"{escape(artifact_type)} ({escape(display_name)})"
        "</label>"
    )


def render_client_dashboard_results(results: dict | None, results_error: str = "") -> str:
    if results_error:
        return (
            '<section class="notice error results-section">'
            "<h2>Results Error</h2>"
            f"<p>{escape(results_error)}</p>"
            "</section>"
        )
    if results is None:
        return ""

    sections: list[str] = []
    if results.get("summary") is not None:
        sections.append(
            "<h2>Run Summary</h2>"
            f"{render_summary_details(results['summary'])}"
        )
    if results.get("charts"):
        sections.append(
            "<h2>Interactive Plots</h2>"
            f"{render_chart_grid(results['charts'], results.get('plot_series', []))}"
        )
    if results.get("dispatch_table") is not None:
        sections.append(
            "<h2>System Dispatch</h2>"
            f"{render_result_table(results['dispatch_table'])}"
        )
    if results.get("asset_dispatch_table") is not None:
        sections.append(
            "<h2>Asset Dispatch</h2>"
            f"{render_result_table(results['asset_dispatch_table'])}"
        )
    if not sections:
        sections.append("<p>No dashboard sections are enabled for this publication.</p>")
    return f'<section class="results-section">{"".join(sections)}</section>'


def render_results_section(results: dict | None, results_error: str = "") -> str:
    if results_error:
        return (
            '<section id="results" class="notice error results-section">'
            "<h2>Results Error</h2>"
            f"<p>{escape(results_error)}</p>"
            "</section>"
        )
    if results is None:
        return ""

    return f"""
        <section id="results" class="results-section">
          <h2>Run Summary</h2>
          {render_summary_details(results["summary"])}
          <h2>Interactive Plots</h2>
          {render_chart_grid(results["charts"], results.get("plot_series", []))}
          <h2>System Dispatch</h2>
          {render_result_table(results["dispatch_table"])}
          <h2>Asset Dispatch</h2>
          {render_result_table(results["asset_dispatch_table"])}
        </section>
    """


def render_summary_details(summary: dict) -> str:
    fields = [
        ("case_name", "Case Name"),
        ("run_timestamp", "Run Timestamp"),
        ("solver_name", "Solver"),
        ("solver_status", "Solver Status"),
        ("termination_status", "Termination Status"),
        ("objective_value_usd", "Objective Value"),
        ("model_version", "Model Version"),
    ]
    rows = "".join(
        f"<dt>{escape(label)}</dt><dd>{escape(str(summary.get(key, '')))}</dd>"
        for key, label in fields
        if key in summary
    )
    return f'<div class="details"><dl>{rows}</dl></div>{render_hydro_summary(summary)}'


def render_hydro_summary(summary: dict) -> str:
    hydro_totals = summary.get("hydro_totals")
    hydro_kpis_by_asset = summary.get("hydro_kpis_by_asset")
    if not isinstance(hydro_totals, dict) and not isinstance(hydro_kpis_by_asset, dict):
        return ""

    totals_markup = ""
    if isinstance(hydro_totals, dict):
        totals_markup = (
            "<h4>Hydro Totals</h4>"
            f"{render_key_value_table(hydro_totals)}"
        )

    asset_markup = ""
    if isinstance(hydro_kpis_by_asset, dict):
        rows = []
        for asset_id, kpis in hydro_kpis_by_asset.items():
            if not isinstance(kpis, dict):
                continue
            for key, value in kpis.items():
                rows.append(
                    "<tr>"
                    f"<td>{escape(str(asset_id))}</td>"
                    f"<td>{escape(str(key))}</td>"
                    f"<td>{escape(str(value))}</td>"
                    "</tr>"
                )
        if rows:
            asset_markup = (
                "<h4>Hydro KPIs By Asset</h4>"
                '<div class="table-scroll"><table>'
                "<thead><tr><th>asset_id</th><th>kpi</th><th>value</th></tr></thead>"
                f"<tbody>{''.join(rows)}</tbody>"
                "</table></div>"
            )

    return f'<section class="hydro-summary"><h3>Hydro Summary</h3>{totals_markup}{asset_markup}</section>'


def render_key_value_table(values: dict[str, Any]) -> str:
    rows = "".join(
        "<tr>"
        f"<td>{escape(str(key))}</td>"
        f"<td>{escape(str(value))}</td>"
        "</tr>"
        for key, value in values.items()
    )
    return (
        '<div class="table-scroll"><table>'
        "<thead><tr><th>kpi</th><th>value</th></tr></thead>"
        f"<tbody>{rows}</tbody>"
        "</table></div>"
    )


def render_chart_grid(charts: dict, plot_series: list[dict[str, Any]]) -> str:
    if not charts:
        return ""
    if not plot_series:
        return '<p>No numeric series are available for plotting.</p>'
    payload = json_for_inline_script(plot_series)
    script = """
      <script>
        (() => {
          const root = document.getElementById("plot-builder");
          const catalog = __PLOT_SERIES__;
          const seriesById = new Map(catalog.map((series) => [series.id, series]));
          const plotsContainer = root.querySelector("[data-plots]");
          const addButton = root.querySelector("[data-add-plot]");
          const favoriteNameInput = root.querySelector("[data-favorite-name]");
          const favoriteSelect = root.querySelector("[data-favorite-select]");
          const favoriteFeedback = root.querySelector("[data-favorite-feedback]");
          const favoriteStorageKey = "energy_dispatch.plotFavorites.v1";
          const plots = [];
          let nextPlotId = 1;

          function element(tag, className, text) {
            const node = document.createElement(tag);
            if (className) node.className = className;
            if (text !== undefined) node.textContent = text;
            return node;
          }

          function setFavoriteFeedback(message) {
            favoriteFeedback.textContent = message;
          }

          function readFavorites() {
            try {
              const parsed = JSON.parse(window.localStorage.getItem(favoriteStorageKey) || "[]");
              return Array.isArray(parsed) ? parsed.filter((favorite) => favorite && favorite.name) : [];
            } catch (error) {
              setFavoriteFeedback("Favorites could not be read from this browser.");
              return [];
            }
          }

          function writeFavorites(favorites) {
            try {
              window.localStorage.setItem(favoriteStorageKey, JSON.stringify(favorites));
              return true;
            } catch (error) {
              setFavoriteFeedback("Favorites could not be saved in this browser.");
              return false;
            }
          }

          function refreshFavoriteOptions(selectedName = "") {
            favoriteSelect.replaceChildren(new Option("Choose a favorite", ""));
            for (const favorite of readFavorites().sort((left, right) => left.name.localeCompare(right.name))) {
              favoriteSelect.appendChild(new Option(favorite.name, favorite.name));
            }
            favoriteSelect.value = selectedName;
          }

          function saveFavorite() {
            const name = favoriteNameInput.value.trim();
            if (!name) {
              setFavoriteFeedback("Enter a name before saving a favorite.");
              favoriteNameInput.focus();
              return;
            }
            if (!plots.length) {
              setFavoriteFeedback("Add at least one plot before saving a favorite.");
              return;
            }
            const favorite = {
              name,
              plots: plots.map((state) => ({
                title: state.titleInput.value,
                primary: [...state.primary],
                secondary: [...state.secondary],
              })),
              updatedAt: new Date().toISOString(),
            };
            const favorites = readFavorites().filter((item) => item.name !== name);
            favorites.push(favorite);
            if (!writeFavorites(favorites)) return;
            refreshFavoriteOptions(name);
            setFavoriteFeedback(`Favorite “${name}” saved in this browser.`);
          }

          function clearPlots() {
            for (const state of [...plots]) {
              Plotly.purge(state.chart);
              state.card.remove();
            }
            plots.length = 0;
          }

          function loadFavorite() {
            const name = favoriteSelect.value;
            const favorite = readFavorites().find((item) => item.name === name);
            if (!favorite) {
              setFavoriteFeedback("Choose a favorite to load.");
              return;
            }
            clearPlots();
            for (const plot of favorite.plots || []) {
              addPlot(plot.primary || [], plot.secondary || [], plot.title || "");
            }
            if (!plots.length) addPlot();
            favoriteNameInput.value = favorite.name;
            setFavoriteFeedback(`Favorite “${favorite.name}” loaded.`);
          }

          function deleteFavorite() {
            const name = favoriteSelect.value;
            if (!name) {
              setFavoriteFeedback("Choose a favorite to delete.");
              return;
            }
            if (!window.confirm(`Delete favorite “${name}”?`)) return;
            const favorites = readFavorites().filter((item) => item.name !== name);
            if (!writeFavorites(favorites)) return;
            refreshFavoriteOptions();
            if (favoriteNameInput.value.trim() === name) favoriteNameInput.value = "";
            setFavoriteFeedback(`Favorite “${name}” deleted.`);
          }

          function axisTitle(seriesIds) {
            const units = [...new Set(seriesIds.map((id) => seriesById.get(id)?.unit).filter(Boolean))];
            return units.length === 1 ? units[0] : "Value (mixed units)";
          }

          function updateGroupSelection(state, axis, groupSeries, selected) {
            const otherAxis = axis === "primary" ? "secondary" : "primary";
            for (const series of groupSeries) {
              if (selected) {
                state[axis].add(series.id);
                state[otherAxis].delete(series.id);
              } else {
                state[axis].delete(series.id);
              }
            }
            syncControls(state);
            updatePlot(state);
          }

          function createSeriesPicker(state, axis, label) {
            const details = element("details", "series-picker");
            const summary = element("summary", "", label);
            const panel = element("div", "series-picker-panel");
            const filter = element("input", "series-filter");
            filter.type = "search";
            filter.placeholder = "Filter series...";
            panel.appendChild(filter);
            state.summaries[axis] = summary;
            state.inputs[axis] = new Map();

            const groups = new Map();
            for (const series of catalog) {
              if (!groups.has(series.source_label)) groups.set(series.source_label, []);
              groups.get(series.source_label).push(series);
            }
            for (const [groupLabel, groupSeries] of groups) {
              const groupBlock = element("div", "series-group-block");
              const groupHeader = element("div", "series-group-header");
              const groupActions = element("div", "series-group-actions");
              const selectAll = element("button", "series-group-action", "Select all");
              const unselectAll = element("button", "series-group-action", "Unselect all");
              selectAll.type = "button";
              unselectAll.type = "button";
              selectAll.addEventListener("click", () => updateGroupSelection(state, axis, groupSeries, true));
              unselectAll.addEventListener("click", () => updateGroupSelection(state, axis, groupSeries, false));
              groupActions.append(selectAll, unselectAll);
              groupHeader.append(element("div", "series-group-label", groupLabel), groupActions);
              groupBlock.appendChild(groupHeader);

              for (const series of groupSeries) {
                const option = element("label", "series-option");
                option.dataset.search = `${series.label} ${series.column} ${series.source_label}`.toLowerCase();
                const checkbox = element("input");
                checkbox.type = "checkbox";
                checkbox.dataset.seriesId = series.id;
                checkbox.dataset.axis = axis;
                checkbox.addEventListener("change", () => {
                  const otherAxis = axis === "primary" ? "secondary" : "primary";
                  if (checkbox.checked) {
                    state[axis].add(series.id);
                    state[otherAxis].delete(series.id);
                  } else {
                    state[axis].delete(series.id);
                  }
                  syncControls(state);
                  updatePlot(state);
                });
                state.inputs[axis].set(series.id, checkbox);
                option.append(checkbox, document.createTextNode(series.label));
                groupBlock.appendChild(option);
              }
              panel.appendChild(groupBlock);
            }

            filter.addEventListener("input", () => {
              const query = filter.value.trim().toLowerCase();
              for (const groupBlock of panel.querySelectorAll(".series-group-block")) {
                const options = [...groupBlock.querySelectorAll(".series-option")];
                for (const option of options) {
                  option.hidden = Boolean(query) && !option.dataset.search.includes(query);
                }
                groupBlock.hidden = options.every((option) => option.hidden);
              }
            });
            details.append(summary, panel);
            return details;
          }

          function syncControls(state) {
            for (const axis of ["primary", "secondary"]) {
              for (const [seriesId, checkbox] of state.inputs[axis]) {
                checkbox.checked = state[axis].has(seriesId);
              }
              const label = axis === "primary" ? "Primary Y axis" : "Secondary Y axis";
              state.summaries[axis].textContent = `${label} (${state[axis].size})`;
            }
          }

          function updatePlot(state) {
            const primaryIds = [...state.primary];
            const secondaryIds = [...state.secondary];
            const traces = [...primaryIds, ...secondaryIds].map((seriesId) => {
              const series = seriesById.get(seriesId);
              const secondary = state.secondary.has(seriesId);
              return {
                x: series.labels,
                y: series.values,
                name: series.label,
                mode: "lines",
                type: "scatter",
                yaxis: secondary ? "y2" : "y",
                connectgaps: false,
                customdata: series.values.map(() => series.unit || ""),
                hovertemplate: "%{x}<br>%{fullData.name}: %{y} %{customdata}<extra></extra>",
              };
            });
            const layout = {
              title: {text: state.titleInput.value || `Plot ${state.id}`, x: 0.02},
              autosize: true,
              height: 500,
              hovermode: "closest",
              margin: {l: 70, r: secondaryIds.length ? 80 : 30, t: 55, b: 135},
              xaxis: {title: "Timestamp", type: "date", rangeslider: {visible: true}},
              yaxis: {title: axisTitle(primaryIds), zeroline: true},
              yaxis2: {
                title: axisTitle(secondaryIds),
                overlaying: "y",
                side: "right",
                showgrid: false,
                visible: secondaryIds.length > 0,
              },
              legend: {
                orientation: "h",
                yanchor: "top",
                y: -0.3,
                itemclick: "toggle",
                itemdoubleclick: "toggleothers",
              },
              annotations: traces.length ? [] : [{
                text: "Choose series from the Primary or Secondary Y axis dropdowns",
                showarrow: false,
                xref: "paper",
                yref: "paper",
                x: 0.5,
                y: 0.5,
              }],
              paper_bgcolor: "#ffffff",
              plot_bgcolor: "#ffffff",
              uirevision: `plot-${state.id}`,
            };
            Plotly.react(state.chart, traces, layout, {
              responsive: true,
              displaylogo: false,
              scrollZoom: true,
            });
          }

          function addPlot(initialPrimary = [], initialSecondary = [], initialTitle = "") {
            const primary = initialPrimary.filter((seriesId) => seriesById.has(seriesId));
            const primarySet = new Set(primary);
            const secondary = initialSecondary.filter(
              (seriesId) => seriesById.has(seriesId) && !primarySet.has(seriesId),
            );
            const state = {
              id: nextPlotId++,
              primary: primarySet,
              secondary: new Set(secondary),
              summaries: {},
              inputs: {},
            };
            const card = element("section", "configurable-plot");
            state.card = card;
            card.dataset.plotId = String(state.id);
            const header = element("div", "configurable-plot-header");
            state.titleInput = element("input", "plot-title-input");
            state.titleInput.value = initialTitle || `Plot ${state.id}`;
            state.titleInput.setAttribute("aria-label", `Plot ${state.id} title`);
            const removeButton = element("button", "", "Remove plot");
            removeButton.type = "button";
            removeButton.addEventListener("click", () => {
              Plotly.purge(state.chart);
              card.remove();
              const index = plots.indexOf(state);
              if (index >= 0) plots.splice(index, 1);
            });
            header.append(state.titleInput, removeButton);
            const controls = element("div", "plot-controls");
            controls.append(
              createSeriesPicker(state, "primary", "Primary Y axis"),
              createSeriesPicker(state, "secondary", "Secondary Y axis"),
            );
            state.chart = element("div", "plotly-chart");
            state.chart.id = `plotly-configurable-${state.id}`;
            state.titleInput.addEventListener("input", () => updatePlot(state));
            card.append(header, controls, state.chart);
            plotsContainer.appendChild(card);
            plots.push(state);
            syncControls(state);
            updatePlot(state);
          }

          addButton.addEventListener("click", () => addPlot());
          root.querySelector("[data-save-favorite]").addEventListener("click", saveFavorite);
          root.querySelector("[data-load-favorite]").addEventListener("click", loadFavorite);
          root.querySelector("[data-delete-favorite]").addEventListener("click", deleteFavorite);
          refreshFavoriteOptions();
          addPlot(catalog.filter((series) => series.source === "system").map((series) => series.id));
        })();
      </script>
    """.replace("__PLOT_SERIES__", payload)
    return (
        '<div id="plot-builder" class="plot-builder" data-series-source="system-and-assets">'
        '<div class="plot-builder-toolbar">'
        '<p>Add plots and assign each series to one Y axis. Current changes reset on reload unless saved as a favorite.</p>'
        '<button type="button" data-add-plot>Add plot</button>'
        "</div>"
        '<section class="plot-favorites">'
        '<label>Favorite name<input type="text" data-favorite-name placeholder="e.g. Battery operation"></label>'
        '<button type="button" data-save-favorite>Save favorite</button>'
        '<label>Saved favorites<select data-favorite-select><option value="">Choose a favorite</option></select></label>'
        '<button type="button" data-load-favorite>Load</button>'
        '<button type="button" data-delete-favorite>Delete</button>'
        '<span class="favorite-feedback" data-favorite-feedback role="status">Favorites are saved in this browser.</span>'
        "</section>"
        '<div data-plots></div>'
        "</div>"
        '<script src="/assets/plotly.min.js"></script>'
        f"{script}"
    )


def json_for_inline_script(value: Any) -> str:
    return (
        json.dumps(value, ensure_ascii=True, separators=(",", ":"))
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
    )


@lru_cache(maxsize=1)
def cached_plotly_javascript() -> str:
    return get_plotlyjs()


def render_result_table(table: dict) -> str:
    columns = table["columns"]
    header = "".join(f"<th>{escape(column)}</th>" for column in columns)
    body = "".join(
        "<tr>"
        + "".join(f"<td>{escape(str(row.get(column) or ''))}</td>" for column in columns)
        + "</tr>"
        for row in table["rows"]
    )
    if not body:
        body = f'<tr><td colspan="{len(columns)}">No rows</td></tr>'
    return f'<div class="table-scroll"><table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table></div>'


def render_artifact_items(artifacts: list[dict]) -> str:
    if not artifacts:
        return '<li class="empty">No artifacts registered yet</li>'

    return "".join(
        f'<li><a href="{escape(artifact["download_url"])}">{escape(artifact["display_name"])}</a>'
        f'<span>{escape(artifact["artifact_type"])} | {escape(artifact["media_type"])} | '
        f'{artifact["byte_size"]} bytes</span></li>'
        for artifact in artifacts
    )


def format_asset_counts(asset_counts: dict) -> str:
    return ", ".join(f"{count} {kind}" for kind, count in asset_counts.items() if count)


app = create_app(auth_enabled=auth_enabled_from_env(True))
