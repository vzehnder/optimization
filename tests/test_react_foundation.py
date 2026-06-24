import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app


class ReactFoundationTests(unittest.TestCase):
    def test_fastapi_serves_react_entry_and_redirects_legacy_bookmarks(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            frontend_dist = Path(temp_dir)
            (frontend_dist / "assets").mkdir()
            (frontend_dist / "index.html").write_text(
                '<!doctype html><div id="root">React application</div>',
                encoding="utf-8",
            )
            (frontend_dist / "assets" / "app-abc123.js").write_text(
                "console.log('react')",
                encoding="utf-8",
            )

            with TestClient(create_app(frontend_dist=frontend_dist)) as client:
                root = client.get("/", follow_redirects=False)
                entry = client.get("/react")
                deep_link = client.get("/react/workspace")
                legacy_project_list = client.get("/projects", follow_redirects=False)
                legacy_project = client.get("/projects/17?tab=access", follow_redirects=False)
                legacy_scenario = client.get("/scenarios/23/draft", follow_redirects=False)
                legacy_run = client.get("/runs/42#results", follow_redirects=False)
                legacy_login = client.get("/login?next=/projects/17", follow_redirects=False)

            self.assertEqual(root.status_code, 303)
            self.assertEqual(root.headers["location"], "/react")
            self.assertEqual(entry.status_code, 200)
            self.assertIn("React application", entry.text)
            self.assertEqual(deep_link.status_code, 200)
            self.assertIn("React application", deep_link.text)
            self.assertEqual(legacy_project_list.status_code, 303)
            self.assertEqual(legacy_project_list.headers["location"], "/react/projects")
            self.assertEqual(legacy_project.status_code, 303)
            self.assertEqual(legacy_project.headers["location"], "/react/projects/17?tab=access")
            self.assertEqual(legacy_scenario.status_code, 303)
            self.assertEqual(legacy_scenario.headers["location"], "/react/scenarios/23/draft")
            self.assertEqual(legacy_run.status_code, 303)
            self.assertEqual(legacy_run.headers["location"], "/react/runs/42")
            self.assertEqual(legacy_login.status_code, 303)
            self.assertEqual(legacy_login.headers["location"], "/react/projects/17")

    def test_react_assets_and_entry_use_safe_production_cache_rules(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            frontend_dist = Path(temp_dir)
            assets = frontend_dist / "assets"
            assets.mkdir()
            (frontend_dist / "index.html").write_text(
                '<script src="/react/assets/app-abc123.js"></script>',
                encoding="utf-8",
            )
            (assets / "app-abc123.js").write_text("built asset", encoding="utf-8")

            with TestClient(create_app(frontend_dist=frontend_dist)) as client:
                entry = client.get("/react/settings")
                asset = client.get("/react/assets/app-abc123.js")
                missing_asset = client.get("/react/assets/missing.js")
                missing_api = client.get("/api/not-real")
                health = client.get("/health")
                missing_artifact = client.get("/api/run-artifacts/999/download")

            self.assertEqual(entry.headers["cache-control"], "no-cache")
            self.assertEqual(asset.status_code, 200)
            self.assertEqual(asset.text, "built asset")
            self.assertEqual(
                asset.headers["cache-control"],
                "public, max-age=31536000, immutable",
            )
            self.assertEqual(missing_asset.status_code, 404)
            self.assertNotIn("<script", missing_asset.text)
            self.assertEqual(missing_api.status_code, 404)
            self.assertEqual(missing_api.headers["content-type"], "application/json")
            self.assertEqual(health.status_code, 404)
            self.assertEqual(health.headers["content-type"], "application/json")
            self.assertEqual(missing_artifact.status_code, 404)
            self.assertNotIn("<script", missing_artifact.text)

    def test_current_user_contract_is_explicit_in_openapi(self):
        with TestClient(create_app()) as client:
            schema = client.get("/openapi.json").json()

        response_schema = schema["paths"]["/api/auth/me"]["get"]["responses"]["200"][
            "content"
        ]["application/json"]["schema"]
        self.assertEqual(
            response_schema,
            {"$ref": "#/components/schemas/CurrentUserResponse"},
        )
        user_schema = schema["components"]["schemas"]["CurrentUser"]
        self.assertEqual(user_schema["properties"]["role"]["enum"], ["admin", "analyst", "client"])

    def test_legacy_html_routes_are_absent_from_openapi(self):
        with TestClient(create_app()) as client:
            schema = client.get("/openapi.json").json()

        paths = set(schema["paths"])
        self.assertFalse(
            {
                "/projects",
                "/projects/{project_id}",
                "/scenarios/{scenario_id}",
                "/scenarios/{scenario_id}/draft",
                "/runs/{run_id}",
                "/login",
                "/bootstrap",
                "/client",
                "/admin/users",
                "/system-cases/validate",
            }
            & paths
        )
        self.assertNotIn('"text/html"', client_serialized_schema(schema))


def client_serialized_schema(schema):
    import json

    return json.dumps(schema, sort_keys=True)


if __name__ == "__main__":
    unittest.main()
