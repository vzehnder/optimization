from __future__ import annotations

import json
import os
from contextlib import asynccontextmanager
from html import escape
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel, Field

from app.persistence import AnalystStore
from app.results import ResultReadError, read_run_results
from app.runner import JuliaRunExecutor, LocalRunQueue
from app.validation import JuliaValidationService, ValidationResult


class SystemCaseValidationRequest(BaseModel):
    system_case_json: str = Field(min_length=1)


class ProjectCreateRequest(BaseModel):
    name: str = Field(min_length=1)
    description: str = ""


class ScenarioCreateRequest(BaseModel):
    name: str = Field(min_length=1)
    description: str = ""


class ScenarioVersionCreateRequest(BaseModel):
    system_case_json: str = Field(min_length=1)


def create_app(
    validation_service: JuliaValidationService | None = None,
    *,
    database_url: str | None = None,
    store: AnalystStore | None = None,
    run_queue=None,
    artifact_root: Path | str | None = None,
) -> FastAPI:
    service = validation_service or JuliaValidationService()
    analyst_store = store or AnalystStore(database_url)
    configured_artifact_root = Path(
        artifact_root
        or os.environ.get("ARTIFACT_ROOT")
        or Path(__file__).resolve().parents[1] / ".tmp" / "artifacts"
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

    def save_validated_scenario_version(
        scenario_id: int,
        candidate_text: str,
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
        )
        return version, None

    def create_and_enqueue_run(scenario_version_id: int) -> dict:
        run = analyst_store.create_run(scenario_version_id=scenario_version_id)
        local_run_queue.enqueue(run["id"])
        return run

    @app.get("/")
    async def root():
        return RedirectResponse("/projects")

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
    async def project_page(project_id: int):
        try:
            project = analyst_store.get_project(project_id)
            scenarios = analyst_store.list_scenarios(project_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return HTMLResponse(render_project_page(project, scenarios))

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
            "message": result.message,
            "validation": result.payload,
        }

    return {
        "status": "error",
        "phase": result.phase,
        "message": result.message,
        "validation": result.payload,
    }


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


def render_project_page(project: dict, scenarios: list[dict]) -> str:
    scenario_items = "".join(
        f'<li><a href="/scenarios/{scenario["id"]}">{escape(scenario["name"])}</a>'
        f'<span>{escape(scenario["description"])}</span></li>'
        for scenario in scenarios
    )
    if not scenario_items:
        scenario_items = '<li class="empty">No scenarios yet</li>'

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
    textarea {{
      min-height: 116px;
      resize: vertical;
    }}
    #system_case_json {{
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
    return f'<div class="details"><dl>{rows}</dl></div>'


def render_chart_grid(charts: dict) -> str:
    chart_keys = [
        "price",
        "grid_import_export",
        "renewable_used_curtailed",
        "bess_charge_discharge_soc",
        "period_profit",
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


app = create_app()
