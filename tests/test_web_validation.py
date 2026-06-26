import json
import subprocess
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from app.validation import JuliaValidationService, ValidationResult


REPO_ROOT = Path(__file__).resolve().parents[1]


class FailingRunner:
    def __init__(self):
        self.calls = []

    def __call__(self, command, **kwargs):
        self.calls.append((command, kwargs))
        raise AssertionError("Julia should not be invoked")


class WebValidationTests(unittest.TestCase):
    def test_malformed_json_fails_before_julia_is_invoked(self):
        runner = FailingRunner()
        service = JuliaValidationService(repo_root=REPO_ROOT, runner=runner)

        result = service.validate_text('{"schema_version": ')

        self.assertFalse(result.ok)
        self.assertEqual(result.phase, "json")
        self.assertIn("Malformed JSON", result.message)
        self.assertEqual(runner.calls, [])

    def test_valid_sample_validates_through_julia_cli(self):
        service = JuliaValidationService(repo_root=REPO_ROOT)
        sample_text = (REPO_ROOT / "data" / "cases" / "hybrid_system" / "system_case.json").read_text()

        result = service.validate_text(sample_text)

        self.assertTrue(result.ok)
        self.assertEqual(result.phase, "julia")
        self.assertEqual(result.payload["status"], "ok")
        self.assertEqual(result.payload["case_name"], "hybrid_system")
        self.assertEqual(result.payload["period_count"], 4)

    def test_invalid_case_surfaces_julia_validation_error(self):
        service = JuliaValidationService(repo_root=REPO_ROOT)
        document = json.loads((REPO_ROOT / "data" / "cases" / "hybrid_system" / "system_case.json").read_text())
        del document["schema_version"]

        result = service.validate_text(json.dumps(document))

        self.assertFalse(result.ok)
        self.assertEqual(result.phase, "julia")
        self.assertIn("schema_version is required", result.message)
        self.assertEqual(result.payload["status"], "error")

    def test_api_endpoint_returns_validation_success(self):
        class StubService:
            def validate_text(self, candidate_text):
                self.candidate_text = candidate_text
                return ValidationResult(
                    ok=True,
                    phase="julia",
                    message="Validation succeeded",
                    payload={"status": "ok", "case_name": "stub_case"},
                )

        service = StubService()
        client = TestClient(create_app(validation_service=service))

        response = client.post("/api/system-cases/validate", json={"system_case_json": "{}"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")
        self.assertEqual(response.json()["validation"]["case_name"], "stub_case")
        self.assertEqual(service.candidate_text, "{}")

    def test_api_endpoint_returns_validation_failure(self):
        class StubService:
            def validate_text(self, candidate_text):
                return ValidationResult(
                    ok=False,
                    phase="julia",
                    message="schema_version is required",
                    payload={"status": "error", "message": "schema_version is required"},
                )

        client = TestClient(create_app(validation_service=StubService()))

        response = client.post("/api/system-cases/validate", json={"system_case_json": "{}"})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["status"], "error")
        self.assertEqual(response.json()["phase"], "julia")
        self.assertIn("schema_version is required", response.json()["message"])

    def legacy_removed_validation_page_renders_form_and_result(self):
        class StubService:
            def validate_text(self, candidate_text):
                return ValidationResult(
                    ok=False,
                    phase="json",
                    message="Malformed JSON: expected value",
                    payload={"status": "error"},
                )

        client = TestClient(create_app(validation_service=StubService()))

        get_response = client.get("/system-cases/validate")
        self.assertEqual(get_response.status_code, 200)
        self.assertIn("<textarea", get_response.text)

        post_response = client.post(
            "/system-cases/validate",
            data={"system_case_json": '{"schema_version": '},
        )
        self.assertEqual(post_response.status_code, 200)
        self.assertIn("Malformed JSON", post_response.text)

    def legacy_removed_validation_page_renders_julia_error(self):
        class StubService:
            def validate_text(self, candidate_text):
                return ValidationResult(
                    ok=False,
                    phase="julia",
                    message="schema_version is required",
                    payload={"status": "error"},
                )

        client = TestClient(create_app(validation_service=StubService()))

        response = client.post("/system-cases/validate", data={"system_case_json": "{}"})

        self.assertEqual(response.status_code, 200)
        self.assertIn("Invalid", response.text)
        self.assertIn("schema_version is required", response.text)


if __name__ == "__main__":
    unittest.main()
