import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app


class ReactFoundationTests(unittest.TestCase):
    def test_fastapi_serves_react_entry_and_client_route_without_replacing_legacy_ui(self):
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
                entry = client.get("/react")
                deep_link = client.get("/react/workspace")
                legacy = client.get("/projects")

            self.assertEqual(entry.status_code, 200)
            self.assertIn("React application", entry.text)
            self.assertEqual(deep_link.status_code, 200)
            self.assertIn("React application", deep_link.text)
            self.assertIn("Projects", legacy.text)

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


if __name__ == "__main__":
    unittest.main()
