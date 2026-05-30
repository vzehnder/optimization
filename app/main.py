from __future__ import annotations

from html import escape

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel, Field

from app.validation import JuliaValidationService, ValidationResult


class SystemCaseValidationRequest(BaseModel):
    system_case_json: str = Field(min_length=1)


def create_app(validation_service: JuliaValidationService | None = None) -> FastAPI:
    service = validation_service or JuliaValidationService()
    app = FastAPI(title="BESS Analyst App")

    @app.get("/")
    async def root():
        return RedirectResponse("/system-cases/validate")

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


app = create_app()
