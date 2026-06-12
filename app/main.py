from __future__ import annotations

import copy
import json
import os
from contextlib import asynccontextmanager
from html import escape
from pathlib import Path
from typing import Any
from urllib.parse import quote

from fastapi import FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel, Field

from app.auth import (
    INTERNAL_USER_ROLES,
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
    structured_draft_document_from_form,
)
from app.persistence import AnalystStore, utc_now_iso
from app.results import ResultReadError, read_run_results
from app.runner import JuliaRunExecutor, LocalRunQueue
from app.time_series_ingestion import (
    TimeSeriesIngestionError,
    attach_time_series_source,
    apply_time_series_mapping,
    ingest_time_series_source,
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


class ProjectClientAccessRequest(BaseModel):
    user_id: int


class ScenarioVersionCreateRequest(BaseModel):
    system_case_json: str = Field(min_length=1)


class ScenarioDraftWriteRequest(BaseModel):
    document: dict[str, Any] | None = None
    source_version_id: int | None = None


class TimeSeriesMappingRequest(BaseModel):
    mapping: dict[str, Any]


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
    auth_enabled: bool | None = None,
    session_cookie_name: str = "bess_session",
    session_hours: int = 12,
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
    local_run_queue = run_queue or LocalRunQueue(
        executor=JuliaRunExecutor(store=analyst_store, artifact_root=configured_artifact_root)
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

    def current_user_from_request(request: Request) -> dict[str, Any] | None:
        token = request.cookies.get(session_cookie_name)
        if not token:
            return None
        return analyst_store.get_user_for_session(hash_session_token(token))

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
        user = request.state.current_user
        if user is None or user["role"] != "admin":
            raise HTTPException(status_code=403, detail="forbidden")

    def set_session_cookie(response: Response, token: str) -> None:
        response.set_cookie(
            session_cookie_name,
            token,
            max_age=session_hours * 60 * 60,
            httponly=True,
            samesite="lax",
        )

    def authenticated_landing_path(user: dict[str, Any], next_path: str = "") -> str:
        safe_next = safe_internal_next_path(next_path)
        if user["role"] == "client":
            return safe_next if safe_next.startswith("/client") else "/client"
        if safe_next and not safe_next.startswith("/client"):
            return safe_next
        return "/projects"

    @app.middleware("http")
    async def require_authenticated_app_boundary(request: Request, call_next):
        request.state.current_user = None
        if not auth_required:
            return await call_next(request)

        path = request.url.path
        if path in {"/favicon.ico", "/login", "/bootstrap", "/logout"}:
            return await call_next(request)

        user = current_user_from_request(request)
        request.state.current_user = user
        if user is None:
            if analyst_store.count_users() == 0 and not path.startswith("/api/"):
                return RedirectResponse("/bootstrap", status_code=303)
            return auth_required_response(request)

        if path == "/":
            return await call_next(request)
        if path.startswith("/client"):
            if user["role"] != "client":
                return forbidden_response(request)
            return await call_next(request)
        if user["role"] not in INTERNAL_USER_ROLES:
            return forbidden_response(request)
        return await call_next(request)

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
        user = request.state.current_user
        if not analyst_store.client_has_project_access(user_id=user["id"], project_id=project_id):
            raise HTTPException(status_code=404, detail="project not found")
        try:
            project = analyst_store.get_project(project_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return HTMLResponse(render_client_project_page(project))

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

    @app.get("/api/auth/me")
    async def current_auth_user(request: Request):
        user = request.state.current_user
        if user is None:
            return {"user": None}
        return {
            "user": {
                "id": user["id"],
                "email": user["email"],
                "display_name": user["display_name"],
                "role": user["role"],
                "is_active": user["is_active"],
            }
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
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        client_users = [user for user in analyst_store.list_users() if user["role"] == "client"]
        can_manage_access = bool(auth_required and request.state.current_user and request.state.current_user["role"] == "admin")
        return HTMLResponse(render_project_page(project, scenarios, client_access, client_users, can_manage_access))

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
            draft_document = structured_draft_document_from_form(form)
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
            candidate_text = ""
            if from_version_id is not None:
                base_version = analyst_store.get_scenario_version(from_version_id)
                if base_version["scenario_id"] != scenario_id:
                    raise KeyError(f"scenario version {from_version_id} not found for scenario {scenario_id}")
                candidate_text = json.dumps(base_version["system_case_json"], indent=2, sort_keys=True)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return HTMLResponse(render_scenario_page(scenario, versions, candidate_text))

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
                error = ValidationResult(
                    ok=False,
                    phase="json",
                    message="Uploaded file must be UTF-8 encoded JSON",
                    payload={"status": "error"},
                )
                return HTMLResponse(render_scenario_page(scenario, versions, candidate_text, error))
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
            return HTMLResponse(render_scenario_page(scenario, versions, candidate_text, error))
        return RedirectResponse(f"/scenarios/{scenario_id}#version-{version['id']}", status_code=303)

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
            stored_artifacts = analyst_store.list_run_artifacts(run_id)
            artifacts = [
                artifact_response_body(artifact)
                for artifact in stored_artifacts
                if artifact_path_is_safe(artifact["path"], configured_artifact_root)
            ]
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

        results = None
        results_error = ""
        if run["status"] == "succeeded":
            try:
                results = read_run_results(run, stored_artifacts, configured_artifact_root)
            except ResultReadError as error:
                results_error = error.message
        return HTMLResponse(render_run_page(run, artifacts, results, results_error))

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

    @app.get("/api/scenario-versions/{scenario_version_id}")
    async def get_scenario_version(scenario_version_id: int):
        try:
            scenario_version = analyst_store.get_scenario_version(scenario_version_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return {"scenario_version": scenario_version}

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
        {access_section}
        """,
    )


def render_scenario_page(
    scenario: dict,
    versions: list[dict],
    candidate_text: str = "",
    error: ValidationResult | None = None,
) -> str:
    version_items = "".join(
        f'<li id="version-{version["id"]}">'
        f'<strong>Version {version["version_number"]}</strong>'
        f'<span>{escape(version["case_name"])} | {escape(version["schema_version"])} | '
        f'{version["period_count"]} periods | {format_asset_counts(version["asset_counts"])}</span>'
        f'<a href="/scenarios/{scenario["id"]}?from_version_id={version["id"]}">Use as base</a>'
        f'<a href="/scenarios/{scenario["id"]}/draft?source_version_id={version["id"]}">Use as draft base</a>'
        f'<form class="inline-form" method="post" action="/scenario-versions/{version["id"]}/runs">'
        f'<button type="submit">Launch Run</button>'
        f"</form>"
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
        {structured_form}
        {time_series_section}
        {preview_markup}
        {generated_validation_markup}
        <form method="post" action="/scenarios/{scenario["id"]}/draft">
          <h2>Draft Document</h2>
          <label for="structured_draft_json">structured_draft_json</label>
          <textarea id="structured_draft_json" name="structured_draft_json" spellcheck="false">{escape(draft_text)}</textarea>
          {hidden_source}
          <button type="submit">Save Draft</button>
        </form>
        """,
    )


def render_structured_draft_form(scenario: dict, document: dict) -> str:
    case = document.get("case") if isinstance(document.get("case"), dict) else {}
    pcc = document.get("pcc") if isinstance(document.get("pcc"), dict) else {}
    grid = document.get("grid") if isinstance(document.get("grid"), dict) else {}
    solver = document.get("solver") if isinstance(document.get("solver"), dict) else {}
    assets = document.get("assets") if isinstance(document.get("assets"), list) else []
    battery = first_asset_of_type(assets, "battery")
    renewable = first_asset_of_type(assets, "renewable")
    load = first_asset_of_type(assets, "load")
    hydro = first_asset_of_type(assets, "hydro")
    solver_options = solver.get("options") if isinstance(solver.get("options"), dict) else {}
    hydro_generation_curve = hydro.get("generation_curve") if isinstance(hydro.get("generation_curve"), list) else []
    hydro_reservoir_curve = (
        hydro.get("reservoir_curve")
        if isinstance(hydro.get("reservoir_curve"), list)
        else [
            {"storage_hm3": 1.0, "elevation_masl": 700.0},
            {"storage_hm3": 3.0, "elevation_masl": 710.0},
            {"storage_hm3": 5.0, "elevation_masl": 720.0},
        ]
    )

    return f"""
        <form method="post" action="/scenarios/{scenario["id"]}/draft/structure" class="structured-form">
          <h2>Case Metadata</h2>
          <label for="case_name">case_name</label>
          <input id="case_name" name="case_name" value="{html_value(case.get("name") or scenario["name"])}">
          <label for="case_description">case_description</label>
          <textarea id="case_description" name="case_description">{escape(str(case.get("description") or ""))}</textarea>

          <h2>PCC And Grid</h2>
          <div class="form-grid">
            <label for="pcc_id">pcc_id</label>
            <input id="pcc_id" name="pcc_id" value="{html_value(pcc.get("id") or "bus_1")}">
            <label for="grid_id">grid_id</label>
            <input id="grid_id" name="grid_id" value="{html_value(grid.get("id") or "grid_1")}">
            <label for="grid_import_power_max_mw">grid_import_power_max_mw</label>
            <input id="grid_import_power_max_mw" name="grid_import_power_max_mw" value="{html_value(grid.get("import_power_max_mw"))}">
            <label for="grid_export_power_max_mw">grid_export_power_max_mw</label>
            <input id="grid_export_power_max_mw" name="grid_export_power_max_mw" value="{html_value(grid.get("export_power_max_mw"))}">
          </div>
          <label class="checkbox-row">
            <input type="checkbox" name="grid_prevent_simultaneous_grid_import_export" {checked_attr(grid.get("prevent_simultaneous_grid_import_export", True))}>
            prevent_simultaneous_grid_import_export
          </label>

          <h2>Battery Asset</h2>
          <div class="form-grid">
            <label for="battery_id">battery_id</label>
            <input id="battery_id" name="battery_id" value="{html_value(battery.get("id") or "battery_1")}">
            <label for="battery_charge_power_max_mw">charge_power_max_mw</label>
            <input id="battery_charge_power_max_mw" name="battery_charge_power_max_mw" value="{html_value(battery.get("charge_power_max_mw") or 4.0)}">
            <label for="battery_discharge_power_max_mw">discharge_power_max_mw</label>
            <input id="battery_discharge_power_max_mw" name="battery_discharge_power_max_mw" value="{html_value(battery.get("discharge_power_max_mw") or 4.0)}">
            <label for="battery_energy_min_mwh">energy_min_mwh</label>
            <input id="battery_energy_min_mwh" name="battery_energy_min_mwh" value="{html_value(battery.get("energy_min_mwh") if "energy_min_mwh" in battery else 0.0)}">
            <label for="battery_energy_max_mwh">energy_max_mwh</label>
            <input id="battery_energy_max_mwh" name="battery_energy_max_mwh" value="{html_value(battery.get("energy_max_mwh") or 8.0)}">
            <label for="battery_initial_energy_mwh">initial_energy_mwh</label>
            <input id="battery_initial_energy_mwh" name="battery_initial_energy_mwh" value="{html_value(battery.get("initial_energy_mwh") or 4.0)}">
            <label for="battery_charge_efficiency">charge_efficiency</label>
            <input id="battery_charge_efficiency" name="battery_charge_efficiency" value="{html_value(battery.get("charge_efficiency") or 0.95)}">
            <label for="battery_discharge_efficiency">discharge_efficiency</label>
            <input id="battery_discharge_efficiency" name="battery_discharge_efficiency" value="{html_value(battery.get("discharge_efficiency") or 0.95)}">
            <label for="battery_degradation_cost_per_mwh_delta_soc">degradation_cost_per_mwh_delta_soc</label>
            <input id="battery_degradation_cost_per_mwh_delta_soc" name="battery_degradation_cost_per_mwh_delta_soc" value="{html_value(battery.get("degradation_cost_per_mwh_delta_soc") if "degradation_cost_per_mwh_delta_soc" in battery else 0.0)}">
            <label for="battery_terminal_condition">terminal_condition</label>
            <input id="battery_terminal_condition" name="battery_terminal_condition" value="{html_value(battery.get("terminal_condition") or "equal_initial")}">
            <label for="battery_terminal_energy_min_mwh">terminal_energy_min_mwh</label>
            <input id="battery_terminal_energy_min_mwh" name="battery_terminal_energy_min_mwh" value="{html_value(battery.get("terminal_energy_min_mwh"))}">
          </div>
          <label class="checkbox-row">
            <input type="checkbox" name="battery_prevent_simultaneous_charge_discharge" {checked_attr(battery.get("prevent_simultaneous_charge_discharge", True))}>
            prevent_simultaneous_charge_discharge
          </label>
          <label class="checkbox-row">
            <input type="checkbox" name="battery_degradation_linear_delta_soc" {checked_attr(battery.get("degradation_linear_delta_soc", True))}>
            degradation_linear_delta_soc
          </label>

          <h2>Renewable And Load Assets</h2>
          <div class="form-grid">
            <label for="renewable_id">renewable_id</label>
            <input id="renewable_id" name="renewable_id" value="{html_value(renewable.get("id") or "solar_1")}">
            <label for="renewable_category">renewable_category</label>
            <input id="renewable_category" name="renewable_category" value="{html_value(renewable.get("category") or renewable.get("display_category") or "solar")}">
            <label for="renewable_curtailment_penalty_usd_per_mwh">curtailment_penalty_usd_per_mwh</label>
            <input id="renewable_curtailment_penalty_usd_per_mwh" name="renewable_curtailment_penalty_usd_per_mwh" value="{html_value(renewable.get("curtailment_penalty_usd_per_mwh") if "curtailment_penalty_usd_per_mwh" in renewable else 0.0)}">
            <label for="load_id">load_id</label>
            <input id="load_id" name="load_id" value="{html_value(load.get("id") or "load_1")}">
          </div>

          <h2>Hydro Asset</h2>
          <div class="form-grid">
            <label for="hydro_id">hydro_id</label>
            <input id="hydro_id" name="hydro_id" value="{html_value(hydro.get("id") or "")}">
            <label for="hydro_storage_min_hm3">storage_min_hm3</label>
            <input id="hydro_storage_min_hm3" name="hydro_storage_min_hm3" value="{html_value(hydro.get("storage_min_hm3") if "storage_min_hm3" in hydro else 1.0)}">
            <label for="hydro_storage_max_hm3">storage_max_hm3</label>
            <input id="hydro_storage_max_hm3" name="hydro_storage_max_hm3" value="{html_value(hydro.get("storage_max_hm3") if "storage_max_hm3" in hydro else 5.0)}">
            <label for="hydro_initial_storage_hm3">initial_storage_hm3</label>
            <input id="hydro_initial_storage_hm3" name="hydro_initial_storage_hm3" value="{html_value(hydro.get("initial_storage_hm3") if "initial_storage_hm3" in hydro else 2.5)}">
            <label for="hydro_generation_mode">generation_mode</label>
            <input id="hydro_generation_mode" name="hydro_generation_mode" value="{html_value(hydro.get("generation_mode") or "linear")}">
            <label for="hydro_power_per_flow_mw_per_m3s">power_per_flow_mw_per_m3s</label>
            <input id="hydro_power_per_flow_mw_per_m3s" name="hydro_power_per_flow_mw_per_m3s" value="{html_value(hydro.get("power_per_flow_mw_per_m3s") if "power_per_flow_mw_per_m3s" in hydro else 0.08)}">
            <label for="hydro_turbine_flow_min_m3s">turbine_flow_min_m3s</label>
            <input id="hydro_turbine_flow_min_m3s" name="hydro_turbine_flow_min_m3s" value="{html_value(hydro.get("turbine_flow_min_m3s"))}">
            <label for="hydro_turbine_flow_max_m3s">turbine_flow_max_m3s</label>
            <input id="hydro_turbine_flow_max_m3s" name="hydro_turbine_flow_max_m3s" value="{html_value(hydro.get("turbine_flow_max_m3s") if "turbine_flow_max_m3s" in hydro else 40.0)}">
            <label for="hydro_power_max_mw">power_max_mw</label>
            <input id="hydro_power_max_mw" name="hydro_power_max_mw" value="{html_value(hydro.get("power_max_mw") if "power_max_mw" in hydro else 3.0)}">
            <label for="hydro_minimum_release_m3s">minimum_release_m3s</label>
            <input id="hydro_minimum_release_m3s" name="hydro_minimum_release_m3s" value="{html_value(hydro.get("minimum_release_m3s") if "minimum_release_m3s" in hydro else 0.0)}">
            <label for="hydro_spill_penalty_usd_per_hm3">spill_penalty_usd_per_hm3</label>
            <input id="hydro_spill_penalty_usd_per_hm3" name="hydro_spill_penalty_usd_per_hm3" value="{html_value(hydro.get("spill_penalty_usd_per_hm3") if "spill_penalty_usd_per_hm3" in hydro else 100.0)}">
            <label for="hydro_terminal_condition">terminal_condition</label>
            <input id="hydro_terminal_condition" name="hydro_terminal_condition" value="{html_value(hydro.get("terminal_condition") or "none")}">
            <label for="hydro_terminal_storage_min_hm3">terminal_storage_min_hm3</label>
            <input id="hydro_terminal_storage_min_hm3" name="hydro_terminal_storage_min_hm3" value="{html_value(hydro.get("terminal_storage_min_hm3"))}">
            <label for="hydro_terminal_water_value_usd_per_hm3">terminal_water_value_usd_per_hm3</label>
            <input id="hydro_terminal_water_value_usd_per_hm3" name="hydro_terminal_water_value_usd_per_hm3" value="{html_value(hydro.get("terminal_water_value_usd_per_hm3") if "terminal_water_value_usd_per_hm3" in hydro else 0.0)}">
          </div>
          <label for="hydro_generation_curve_json">generation_curve_json</label>
          <textarea id="hydro_generation_curve_json" name="hydro_generation_curve_json" spellcheck="false">{escape(json.dumps(hydro_generation_curve, sort_keys=True))}</textarea>
          <label for="hydro_reservoir_curve_json">reservoir_curve_json</label>
          <textarea id="hydro_reservoir_curve_json" name="hydro_reservoir_curve_json" spellcheck="false">{escape(json.dumps(hydro_reservoir_curve, sort_keys=True))}</textarea>

          <h2>Solver</h2>
          <label for="solver_name">solver_name</label>
          <input id="solver_name" name="solver_name" value="{html_value(solver.get("name") or "HiGHS")}">
          <label for="solver_options_json">solver_options_json</label>
          <textarea id="solver_options_json" name="solver_options_json" spellcheck="false">{escape(json.dumps(solver_options, sort_keys=True))}</textarea>
          <button type="submit">Save Structured Draft</button>
        </form>
    """


def render_time_series_source_section(scenario: dict, document: dict) -> str:
    source = active_time_series_source(document)
    source_markup = ""
    if source is not None:
        source_markup = render_time_series_source_detail(scenario, document, source)
    return f"""
        <section class="time-series-source">
          <form method="post" action="/scenarios/{scenario["id"]}/draft/time-series-sources/upload" enctype="multipart/form-data">
            <h2>CSV Time-Series Source</h2>
            <label for="source_file">source_file</label>
            <input id="source_file" name="source_file" type="file" accept="text/csv,.csv,.xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet">
            <label for="sheet_name">xlsx_sheet_name</label>
            <input id="sheet_name" name="sheet_name" placeholder="First sheet by default">
            <button type="submit">Upload Source</button>
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
    return f"""
          <div class="source-detail">
            <h2>{source_title}</h2>
            <p>{escape(str(source.get("original_filename") or "source.csv"))}</p>
            {selected_sheet_markup}
            <p>Columns: {escape(", ".join(str(column) for column in columns))}</p>
            {render_preview_rows(source)}
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
        '<section class="preview-block">'
        "<h2>Generated System Case Preview</h2>"
        f'<textarea id="generated_system_case_preview" readonly spellcheck="false">{escape(preview_text)}</textarea>'
        "</section>"
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
        "<h2>Generated System Case Validation</h2>"
        '<button type="submit">Validate Generated System Case</button>'
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


def auth_enabled_from_env(default: bool) -> bool:
    raw_value = os.environ.get("BESS_AUTH_ENABLED")
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


def render_client_project_page(project: dict[str, Any]) -> str:
    return render_auth_shell(
        project["name"],
        f"""
        <nav><a href="/client">Client Portal</a></nav>
        <h1>{escape(project["name"])}</h1>
        <p>{escape(project["description"])}</p>
        <section>
          <h2>Publications</h2>
          <p>No published results yet.</p>
        </section>
        <form method="post" action="/logout">
          <button type="submit">Log Out</button>
        </form>
        """,
    )


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
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
      gap: 16px;
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
    .chart-svg {{
      display: block;
      width: 100%;
      aspect-ratio: 16 / 7;
      min-height: 180px;
    }}
    .chart-legend {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px 12px;
      margin: 8px 0 0;
      padding: 0;
      list-style: none;
      color: var(--muted);
      font-size: 12px;
    }}
    .legend-swatch {{
      display: inline-block;
      width: 10px;
      height: 10px;
      border-radius: 2px;
      margin-right: 5px;
      vertical-align: -1px;
    }}
    .table-scroll {{
      border: 1px solid var(--line);
      border-radius: 6px;
      overflow-x: auto;
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
) -> str:
    artifact_items = render_artifact_items(artifacts or [])
    results_markup = render_results_section(results, results_error)
    return render_app_page(
        f"Run {run['id']}",
        f"""
        <nav><a href="/api/scenario-versions/{run["scenario_version_id"]}">Scenario Version</a></nav>
        <section class="toolbar">
          <h1>Run {run["id"]}</h1>
          <p>Status: <strong id="run-status">{escape(run["status"])}</strong></p>
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
        {results_markup}
        <script>
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
            }}
          }}
          window.setTimeout(pollRun, 1000);
        </script>
        """,
    )


def render_results_section(results: dict | None, results_error: str = "") -> str:
    if results_error:
        return (
            '<section class="notice error results-section">'
            "<h2>Results Error</h2>"
            f"<p>{escape(results_error)}</p>"
            "</section>"
        )
    if results is None:
        return ""

    return f"""
        <section class="results-section">
          <h2>Run Summary</h2>
          {render_summary_details(results["summary"])}
          <h2>Basic Charts</h2>
          {render_chart_grid(results["charts"])}
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


def render_chart_grid(charts: dict) -> str:
    chart_keys = [
        "price",
        "grid_import_export",
        "renewable_used_curtailed",
        "bess_charge_discharge_soc",
        "period_profit",
        "hydro_power",
        "hydro_flows",
        "hydro_storage",
        "hydro_reservoir_elevation",
    ]
    panels = "".join(render_chart_panel(charts[key]) for key in chart_keys if key in charts)
    return f'<div class="chart-grid">{panels}</div>'


def render_chart_panel(chart: dict) -> str:
    chart_id = escape(chart["id"])
    title = escape(chart["title"])
    if not chart["available"]:
        message = escape(chart.get("message") or "Chart data is not available for this run.")
        return (
            f'<section class="chart-panel" data-chart-id="{chart_id}">'
            f"<h3>{title}</h3>"
            f"<p>{message}</p>"
            "</section>"
        )

    return (
        f'<section class="chart-panel" data-chart-id="{chart_id}">'
        f"<h3>{title}</h3>"
        f"{render_chart_svg(chart)}"
        f"{render_chart_legend(chart)}"
        "</section>"
    )


def render_chart_svg(chart: dict) -> str:
    width = 640
    height = 280
    left = 52
    right = 18
    top = 22
    bottom = 42
    plot_width = width - left - right
    plot_height = height - top - bottom
    labels = chart["labels"]
    values = [
        value
        for series in chart["series"]
        for value in series["values"]
        if isinstance(value, (int, float))
    ]
    if not values:
        return '<p>No numeric chart data is available for this run.</p>'

    y_min = min(values)
    y_max = max(values)
    if y_min == y_max:
        padding = max(abs(y_min) * 0.1, 1.0)
        y_min -= padding
        y_max += padding

    def x_position(index: int) -> float:
        if len(labels) <= 1:
            return left + plot_width / 2
        return left + (plot_width * index / (len(labels) - 1))

    def y_position(value: float) -> float:
        return top + ((y_max - value) / (y_max - y_min)) * plot_height

    colors = ["#2563eb", "#dc2626", "#0f766e", "#ca8a04"]
    series_markup = []
    for series_index, series in enumerate(chart["series"]):
        color = colors[series_index % len(colors)]
        points = [
            (x_position(index), y_position(value), value)
            for index, value in enumerate(series["values"])
            if isinstance(value, (int, float))
        ]
        if len(points) > 1:
            point_text = " ".join(f"{x:.2f},{y:.2f}" for x, y, _ in points)
            series_markup.append(
                f'<polyline points="{point_text}" fill="none" stroke="{color}" '
                'stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"></polyline>'
            )
        for x, y, value in points:
            series_markup.append(
                f'<circle cx="{x:.2f}" cy="{y:.2f}" r="4" fill="{color}" '
                f'data-series="{escape(series["key"])}" data-value="{format_chart_number(value)}">'
                f"<title>{escape(series['label'])}: {format_chart_number(value)}</title>"
                "</circle>"
            )

    first_label = escape(labels[0]) if labels else ""
    last_label = escape(labels[-1]) if labels else ""
    axis_markup = f"""
      <line x1="{left}" y1="{height - bottom}" x2="{width - right}" y2="{height - bottom}" stroke="#9aa4b2"></line>
      <line x1="{left}" y1="{top}" x2="{left}" y2="{height - bottom}" stroke="#9aa4b2"></line>
      <text x="{left}" y="{height - 14}" fill="#606a78" font-size="11">{first_label}</text>
      <text x="{width - right}" y="{height - 14}" fill="#606a78" font-size="11" text-anchor="end">{last_label}</text>
      <text x="{left - 8}" y="{top + 4}" fill="#606a78" font-size="11" text-anchor="end">{format_chart_number(y_max)}</text>
      <text x="{left - 8}" y="{height - bottom + 4}" fill="#606a78" font-size="11" text-anchor="end">{format_chart_number(y_min)}</text>
    """
    return (
        f'<svg class="chart-svg" viewBox="0 0 {width} {height}" role="img" '
        f'aria-label="{escape(chart["title"])}">'
        f"{axis_markup}"
        f"{''.join(series_markup)}"
        "</svg>"
    )


def render_chart_legend(chart: dict) -> str:
    colors = ["#2563eb", "#dc2626", "#0f766e", "#ca8a04"]
    items = "".join(
        '<li>'
        f'<span class="legend-swatch" style="background:{colors[index % len(colors)]}"></span>'
        f'{escape(series["label"])}'
        "</li>"
        for index, series in enumerate(chart["series"])
    )
    return f'<ul class="chart-legend">{items}</ul>'


def format_chart_number(value: float) -> str:
    return f"{value:g}"


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
