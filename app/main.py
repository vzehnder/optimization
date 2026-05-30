from __future__ import annotations

import json
from contextlib import asynccontextmanager
from html import escape

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel, Field

from app.persistence import AnalystStore
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
) -> FastAPI:
    service = validation_service or JuliaValidationService()
    analyst_store = store or AnalystStore(database_url)
    local_run_queue = run_queue or LocalRunQueue(executor=JuliaRunExecutor(store=analyst_store))

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
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return HTMLResponse(render_run_page(run))

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


def render_run_page(run: dict) -> str:
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


def format_asset_counts(asset_counts: dict) -> str:
    return ", ".join(f"{count} {kind}" for kind, count in asset_counts.items() if count)


app = create_app()
