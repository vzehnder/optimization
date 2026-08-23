import unittest

from fastapi.testclient import TestClient

from app.auth import hash_password
from app.main import create_app
from app.persistence import AnalystStore
from app.portal_configuration import default_portal_config_document
from tests.auth_test_helpers import csrf_headers, login_json_with_csrf


class PortalBrandingPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.store = AnalystStore("sqlite:///:memory:")
        self.project = self.store.create_project(
            name="Cliente Norte", description="Interno"
        )
        self.analyst = self.store.create_user(
            email="analyst@example.local",
            display_name="Analyst",
            role="analyst",
            password_hash="test-hash",
        )

    def tearDown(self):
        self.store.close()

    def test_uploading_a_logo_persists_binary_outside_the_document_and_increments_revision(self):
        saved = self.store.save_portal_logo(
            self.project["id"],
            logo_bytes=b"\x89PNG\r\n\x1a\nproject-logo",
            logo_media_type="image/png",
            expected_revision=0,
            updated_by_user_id=self.analyst["id"],
        )

        self.assertEqual(saved["revision"], 1)
        self.assertEqual(saved["logo_bytes"], b"\x89PNG\r\n\x1a\nproject-logo")
        self.assertEqual(saved["logo_media_type"], "image/png")
        self.assertNotIn("logo_bytes", saved["document"])
        self.assertNotIn("logo_media_type", saved["document"])


class PortalBrandingApiTests(unittest.TestCase):
    def setUp(self):
        self.store = AnalystStore("sqlite:///:memory:")
        self.client = TestClient(create_app(store=self.store, auth_enabled=True))
        self.store.create_user(
            email="analyst@example.local",
            display_name="Analyst",
            role="analyst",
            password_hash=hash_password("analyst pass"),
        )
        self.assertEqual(
            login_json_with_csrf(
                self.client, "analyst@example.local", "analyst pass"
            ).status_code,
            200,
        )
        self.project = self.store.create_project(
            name="Cliente Norte", description="Interno"
        )

    def tearDown(self):
        self.store.close()

    def test_an_analyst_can_upload_one_png_logo(self):
        response = self.client.put(
            f"/api/projects/{self.project['id']}/portal-configuration/logo",
            data={"expected_revision": "0"},
            files={"logo": ("logo.png", b"\x89PNG\r\n\x1a\nproject-logo", "image/png")},
            headers=csrf_headers(self.client),
        )

        self.assertEqual(response.status_code, 200)
        configuration = response.json()["portal_configuration"]
        self.assertEqual(
            {"revision": configuration["revision"], "has_logo": configuration["has_logo"]},
            {"revision": 1, "has_logo": True},
        )
        self.assertNotIn("logo_bytes", response.text)

    def test_an_svg_is_rejected_without_changing_the_prior_logo(self):
        prior = self.store.save_portal_logo(
            self.project["id"],
            logo_bytes=b"\xff\xd8\xffprior-jpeg",
            logo_media_type="image/jpeg",
            expected_revision=0,
            updated_by_user_id=None,
        )

        response = self.client.put(
            f"/api/projects/{self.project['id']}/portal-configuration/logo",
            data={"expected_revision": str(prior["revision"])},
            files={
                "logo": (
                    "unsafe.svg",
                    b"<svg xmlns='http://www.w3.org/2000/svg'></svg>",
                    "image/svg+xml",
                )
            },
            headers=csrf_headers(self.client),
        )

        self.assertEqual(response.status_code, 415)
        stored = self.store.get_portal_configuration(self.project["id"])
        self.assertEqual(stored["revision"], prior["revision"])
        self.assertEqual(stored["logo_bytes"], b"\xff\xd8\xffprior-jpeg")

    def test_a_logo_over_256_kib_is_rejected_without_changing_the_prior_logo(self):
        prior = self.store.save_portal_logo(
            self.project["id"],
            logo_bytes=b"\x89PNG\r\n\x1a\nprior",
            logo_media_type="image/png",
            expected_revision=0,
            updated_by_user_id=None,
        )

        response = self.client.put(
            f"/api/projects/{self.project['id']}/portal-configuration/logo",
            data={"expected_revision": str(prior["revision"])},
            files={
                "logo": (
                    "too-large.png",
                    b"\x89PNG\r\n\x1a\n" + b"x" * (256 * 1024),
                    "image/png",
                )
            },
            headers=csrf_headers(self.client),
        )

        self.assertEqual(response.status_code, 413)
        stored = self.store.get_portal_configuration(self.project["id"])
        self.assertEqual(stored["revision"], prior["revision"])
        self.assertEqual(stored["logo_bytes"], b"\x89PNG\r\n\x1a\nprior")

    def test_declaring_png_does_not_make_an_svg_payload_safe(self):
        response = self.client.put(
            f"/api/projects/{self.project['id']}/portal-configuration/logo",
            data={"expected_revision": "0"},
            files={
                "logo": (
                    "disguised.png",
                    b"<svg xmlns='http://www.w3.org/2000/svg'></svg>",
                    "image/png",
                )
            },
            headers=csrf_headers(self.client),
        )

        self.assertEqual(response.status_code, 415)
        self.assertIsNone(self.store.get_portal_configuration(self.project["id"]))

    def test_an_analyst_can_remove_the_logo_without_changing_the_document(self):
        prior = self.store.save_portal_logo(
            self.project["id"],
            logo_bytes=b"\xff\xd8\xffprior-jpeg",
            logo_media_type="image/jpeg",
            expected_revision=0,
            updated_by_user_id=None,
        )
        prior_document = prior["document"]

        response = self.client.request(
            "DELETE",
            f"/api/projects/{self.project['id']}/portal-configuration/logo",
            json={"expected_revision": prior["revision"]},
            headers=csrf_headers(self.client),
        )

        self.assertEqual(response.status_code, 200)
        configuration = response.json()["portal_configuration"]
        self.assertEqual(configuration["revision"], prior["revision"] + 1)
        self.assertFalse(configuration["has_logo"])
        stored = self.store.get_portal_configuration(self.project["id"])
        self.assertIsNone(stored["logo_bytes"])
        self.assertEqual(stored["document"], prior_document)

    def test_an_authorized_external_user_fetches_the_active_logo_with_private_revalidation(self):
        active = self.store.save_portal_configuration(
            self.project["id"],
            document=default_portal_config_document(),
            status="active",
            expected_revision=0,
            updated_by_user_id=None,
        )
        branded = self.store.save_portal_logo(
            self.project["id"],
            logo_bytes=b"\xff\xd8\xffproject-jpeg",
            logo_media_type="image/jpeg",
            expected_revision=active["revision"],
            updated_by_user_id=None,
        )
        external_user = self.store.create_user(
            email="external@example.local",
            display_name="External",
            role="external",
            password_hash=hash_password("external pass"),
        )
        self.store.set_external_project_access(
            project_id=self.project["id"],
            user_id=external_user["id"],
            portal_view=True,
            operate=False,
            updated_by="analyst@example.local",
        )
        external = TestClient(create_app(store=self.store, auth_enabled=True))
        self.assertEqual(
            login_json_with_csrf(
                external, "external@example.local", "external pass"
            ).status_code,
            200,
        )

        response = external.get(
            f"/api/client/projects/{self.project['id']}/branding/logo"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"\xff\xd8\xffproject-jpeg")
        self.assertEqual(response.headers["content-type"], "image/jpeg")
        self.assertEqual(
            response.headers["etag"], f'"portal-logo-r{branded["revision"]}"'
        )
        self.assertEqual(
            response.headers["cache-control"], "private, must-revalidate"
        )
        self.assertEqual(response.headers["x-content-type-options"], "nosniff")

    def test_a_matching_logo_etag_revalidates_without_resending_the_binary(self):
        active = self.store.save_portal_configuration(
            self.project["id"],
            document=default_portal_config_document(),
            status="active",
            expected_revision=0,
            updated_by_user_id=None,
        )
        branded = self.store.save_portal_logo(
            self.project["id"],
            logo_bytes=b"\x89PNG\r\n\x1a\nproject-logo",
            logo_media_type="image/png",
            expected_revision=active["revision"],
            updated_by_user_id=None,
        )
        external_user = self.store.create_user(
            email="viewer@example.local",
            display_name="Viewer",
            role="external",
            password_hash=hash_password("viewer pass"),
        )
        self.store.set_external_project_access(
            project_id=self.project["id"],
            user_id=external_user["id"],
            portal_view=True,
            operate=False,
            updated_by="analyst@example.local",
        )
        external = TestClient(create_app(store=self.store, auth_enabled=True))
        self.assertEqual(
            login_json_with_csrf(
                external, "viewer@example.local", "viewer pass"
            ).status_code,
            200,
        )
        etag = f'"portal-logo-r{branded["revision"]}"'

        response = external.get(
            f"/api/client/projects/{self.project['id']}/branding/logo",
            headers={"If-None-Match": etag},
        )

        self.assertEqual(response.status_code, 304)
        self.assertEqual(response.content, b"")
        self.assertEqual(response.headers["etag"], etag)
        self.assertEqual(
            response.headers["cache-control"], "private, must-revalidate"
        )

    def test_an_analyst_can_fetch_the_logo_used_by_the_faithful_preview(self):
        active = self.store.save_portal_configuration(
            self.project["id"],
            document=default_portal_config_document(),
            status="active",
            expected_revision=0,
            updated_by_user_id=None,
        )
        self.store.save_portal_logo(
            self.project["id"],
            logo_bytes=b"\x89PNG\r\n\x1a\npreview-logo",
            logo_media_type="image/png",
            expected_revision=active["revision"],
            updated_by_user_id=None,
        )

        response = self.client.get(
            f"/api/projects/{self.project['id']}/portal-configuration/logo"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"\x89PNG\r\n\x1a\npreview-logo")
        self.assertEqual(response.headers["cache-control"], "private, must-revalidate")

    def test_an_external_user_without_portal_view_cannot_discover_a_logo(self):
        active = self.store.save_portal_configuration(
            self.project["id"],
            document=default_portal_config_document(),
            status="active",
            expected_revision=0,
            updated_by_user_id=None,
        )
        self.store.save_portal_logo(
            self.project["id"],
            logo_bytes=b"\x89PNG\r\n\x1a\nprivate-logo",
            logo_media_type="image/png",
            expected_revision=active["revision"],
            updated_by_user_id=None,
        )
        operator = self.store.create_user(
            email="operator@example.local",
            display_name="Operator",
            role="external",
            password_hash=hash_password("operator pass"),
        )
        self.store.set_external_project_access(
            project_id=self.project["id"],
            user_id=operator["id"],
            portal_view=False,
            operate=True,
            updated_by="analyst@example.local",
        )
        external = TestClient(create_app(store=self.store, auth_enabled=True))
        self.assertEqual(
            login_json_with_csrf(
                external, "operator@example.local", "operator pass"
            ).status_code,
            200,
        )

        response = external.get(
            f"/api/client/projects/{self.project['id']}/branding/logo"
        )

        self.assertEqual(response.status_code, 404)

    def test_a_stale_logo_upload_is_rejected_without_replacing_the_current_logo(self):
        prior = self.store.save_portal_logo(
            self.project["id"],
            logo_bytes=b"\x89PNG\r\n\x1a\nprior",
            logo_media_type="image/png",
            expected_revision=0,
            updated_by_user_id=None,
        )

        response = self.client.put(
            f"/api/projects/{self.project['id']}/portal-configuration/logo",
            data={"expected_revision": "0"},
            files={
                "logo": (
                    "lost-update.jpg",
                    b"\xff\xd8\xffreplacement",
                    "image/jpeg",
                )
            },
            headers=csrf_headers(self.client),
        )

        self.assertEqual(response.status_code, 409)
        stored = self.store.get_portal_configuration(self.project["id"])
        self.assertEqual(stored["revision"], prior["revision"])
        self.assertEqual(stored["logo_bytes"], b"\x89PNG\r\n\x1a\nprior")


if __name__ == "__main__":
    unittest.main()
