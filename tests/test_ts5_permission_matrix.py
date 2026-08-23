"""BESS-TS5-008: permission matrix enforcement across every TS-5 surface.

Proves the accepted permission matrix (`docs/series_tiempo/iter5/
decision_record_ts5_migration_semantics.md`, Decision 6) holds for the
endpoint surfaces TS5-001 through TS5-007 added: generic catalog browse/edit,
adapter-read hydraulic series, draft extraction, hydraulic migration, case
input variants, run results/comparisons and publication preview. The gate
itself (`require_authenticated_app_boundary` in `app/main.py`) is a single
shared deep module already exercised for pre-TS-5 routes in
`tests/test_iter6_authorization_hardening.py`; this file extends the same
proof to the newer surfaces so a future route cannot silently regress.
"""

import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.auth import hash_password
from app.main import create_app
from app.persistence import AnalystStore
from tests.auth_test_helpers import (
    csrf_headers,
    login_json_with_csrf,
    post_json_with_csrf,
    put_json_with_csrf,
)
from tests.test_results_review import create_completed_run_with_result_artifacts


def _inflow_series(*values):
    return {
        "version_label": "v1",
        "points": [
            {
                "timestamp": f"2026-01-01T{index:02d}:00:00",
                "duration_hours": 1.0,
                "value_m3s": float(value),
            }
            for index, value in enumerate(values)
        ],
    }


def _reservoir_node(inflow=None):
    node = {
        "component_type": "reservoir",
        "technical_key": "reservoir_alpha",
        "display_name": "Reservoir Alpha",
        "x": 120.0,
        "y": 80.0,
        "reservoir": {
            "storage_min_hm3": 5.0,
            "storage_max_hm3": 50.0,
            "initial_storage_hm3": 20.0,
            "terminal_condition": "none",
            "terminal_water_value_usd_per_hm3": 0.0,
        },
        "storage_elevation_curve": {
            "version_label": "v1",
            "points": [
                {"x_value": 5.0, "y_value": 700.0},
                {"x_value": 50.0, "y_value": 760.0},
            ],
        },
    }
    if inflow is not None:
        node["natural_inflow_series"] = inflow
    return node


class PermissionMatrixFixture(unittest.TestCase):
    """Shared fixture: one project with a generic catalog set (via the
    hydraulic diagram's TS5-003 generic write path) plus a legacy hydraulic
    set seeded directly at storage layer, as prior TS-5 test files do since
    the public API can no longer produce legacy rows."""

    def setUp(self):
        self.store = AnalystStore("sqlite:///:memory:")
        self.addCleanup(self.store.close)
        self.admin_user = self.create_user("admin@example.local", role="admin", password="admin pass")
        self.analyst_user = self.create_user("analyst@example.local", role="analyst", password="analyst pass")
        self.client_user = self.create_user(
            "client@example.local", role="external", password="client pass"
        )

        self.admin = TestClient(create_app(store=self.store, auth_enabled=True))
        self.login(self.admin, "admin@example.local", "admin pass")

        project = post_json_with_csrf(self.admin, "/api/projects", {"name": "TS5-008 permissions"}).json()
        scenario = post_json_with_csrf(
            self.admin, f"/api/projects/{project['id']}/scenarios", {"name": "Base case"}
        ).json()
        self.project = project
        self.scenario = scenario

        diagram = post_json_with_csrf(
            self.admin, f"/api/scenarios/{scenario['id']}/hydraulic-diagram"
        ).json()["diagram"]
        save_response = put_json_with_csrf(
            self.admin,
            f"/api/scenarios/{scenario['id']}/hydraulic-diagram",
            {"revision": diagram["revision"], "nodes": [_reservoir_node(_inflow_series(5.0, 6.0))]},
        )
        saved_diagram = save_response.json()["diagram"]
        self.generic_set_id = saved_diagram["nodes"][0]["natural_inflow_series"]["time_series_set_id"]
        self.case_id = saved_diagram["optimization_case"]["id"]

        self.legacy_set_id = self._seed_legacy_hydraulic_set(saved_diagram["nodes"][0]["entity_id"])

    def _seed_legacy_hydraulic_set(self, case_node_id: int) -> int:
        base_row = self.store.connection.execute(
            "SELECT hydraulic_node_id FROM case_hydraulic_nodes WHERE id = ?",
            (case_node_id,),
        ).fetchone()
        base_entity_id = int(base_row[0])
        now = "2026-01-01T00:00:00+00:00"
        cursor = self.store.connection.execute(
            """
            INSERT INTO hydraulic_time_series_sets (
                project_id, entity_type, entity_id, signal_key, version_number,
                version_label, content_hash, status, created_at, updated_at,
                created_by, updated_by
            ) VALUES (?, 'hydraulic_node', ?, 'natural_inflow_m3s', 1, 'v1',
                      'legacy-seed-hash', 'draft', ?, ?, 'seed', 'seed')
            """,
            (self.project["id"], base_entity_id, now, now),
        )
        set_id = int(cursor.lastrowid)
        self.store.connection.execute(
            """
            INSERT INTO hydraulic_time_series_points (
                hydraulic_time_series_set_id, point_index, timestamp,
                duration_hours, value
            ) VALUES (?, 0, '2026-01-01T00:00:00', 1.0, 1.5)
            """,
            (set_id,),
        )
        self.store.connection.commit()
        return set_id

    def create_user(self, email, *, role, password):
        return self.store.create_user(
            email=email,
            display_name=email,
            role=role,
            password_hash=hash_password(password),
            created_by="test",
        )

    def login(self, client, email, password):
        response = login_json_with_csrf(client, email, password)
        self.assertEqual(response.status_code, 200)

    def client_as(self, email, password):
        client = TestClient(create_app(store=self.store, auth_enabled=True))
        self.login(client, email, password)
        return client


class ClientBlockedFromTs5SurfacesTests(PermissionMatrixFixture):
    """Acceptance: 'Client users cannot read input series, sources or
    unpublished result series through any endpoint, including adapter and
    extraction surfaces.'"""

    def test_client_is_denied_on_every_ts5_input_and_result_surface(self):
        client = self.client_as("client@example.local", "client pass")

        routes = [
            ("get", f"/api/projects/{self.project['id']}/time-series-sets"),
            ("get", f"/api/projects/{self.project['id']}/time-series-sets/{self.generic_set_id}"),
            ("get", f"/api/projects/{self.project['id']}/time-series-sets/{self.generic_set_id}/revisions"),
            ("get", f"/api/projects/{self.project['id']}/time-series-sets/hydraulic"),
            ("get", f"/api/projects/{self.project['id']}/time-series-sets/hydraulic/{self.legacy_set_id}"),
            ("post", f"/api/projects/{self.project['id']}/time-series-sets/hydraulic/{self.legacy_set_id}/migrate"),
            ("post", f"/api/projects/{self.project['id']}/time-series-sets/hydraulic/migrate-all"),
            ("post", f"/api/scenarios/{self.scenario['id']}/draft/time-series-sources/some-source/extract"),
            ("get", f"/api/scenarios/{self.scenario['id']}/case/default-variant"),
            ("get", f"/api/scenarios/{self.scenario['id']}/case/variants"),
            ("post", f"/api/scenarios/{self.scenario['id']}/case/variants"),
            ("get", f"/api/scenarios/{self.scenario['id']}/hydraulic-diagram"),
            ("get", "/api/run-comparisons?baseline_run_id=1&candidate_run_id=2"),
        ]
        for method, path in routes:
            with self.subTest(path=path):
                headers = csrf_headers(client) if method == "post" else {}
                response = getattr(client, method)(path, headers=headers)
                self.assertEqual(response.status_code, 403)

    def test_client_is_denied_from_internal_publication_preview(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_root = Path(temp_dir) / "artifacts"
            run = create_completed_run_with_result_artifacts(self.store, artifact_root)
            project_id = self.store.get_run_lineage(run["id"])["project_id"]
            template = self.store.create_dashboard_template(
                project_id=project_id, name="Preview Template", created_by="analyst@example.local"
            )
            publication = self.store.create_publication_draft(
                run_id=run["id"],
                dashboard_template_id=template["id"],
                public_title="Internal preview",
                allowed_artifact_types=["summary_json"],
                created_by="analyst@example.local",
            )
            self.store.publish_publication(publication["id"], published_by="analyst@example.local")

            client = TestClient(create_app(store=self.store, artifact_root=artifact_root, auth_enabled=True))
            self.login(client, "client@example.local", "client pass")

            response = client.get(f"/api/publications/{publication['id']}/preview")
            self.assertEqual(response.status_code, 403)


class AnalystAdminParityTests(PermissionMatrixFixture):
    """Acceptance: 'Analyst and admin visibility matches the accepted
    permission matrix across catalog, variants, results and
    publications.'"""

    def test_analyst_and_admin_both_read_generic_catalog_and_hydraulic_adapter(self):
        analyst = self.client_as("analyst@example.local", "analyst pass")

        for actor in (analyst, self.admin):
            with self.subTest(actor=actor):
                catalog = actor.get(f"/api/projects/{self.project['id']}/time-series-sets")
                self.assertEqual(catalog.status_code, 200)
                self.assertEqual(len(catalog.json()["time_series_sets"]), 1)

                hydraulic = actor.get(f"/api/projects/{self.project['id']}/time-series-sets/hydraulic")
                self.assertEqual(hydraulic.status_code, 200)
                self.assertEqual(len(hydraulic.json()["hydraulic_time_series_sets"]), 1)

    def test_analyst_and_admin_both_read_and_write_case_input_variants(self):
        analyst = self.client_as("analyst@example.local", "analyst pass")

        for actor in (analyst, self.admin):
            with self.subTest(actor=actor):
                default_variant = actor.get(f"/api/scenarios/{self.scenario['id']}/case/default-variant")
                self.assertEqual(default_variant.status_code, 200)

                created = post_json_with_csrf(
                    actor,
                    f"/api/scenarios/{self.scenario['id']}/case/variants",
                    {"display_name": f"Variant by {actor}"},
                )
                self.assertEqual(created.status_code, 201)

    def test_analyst_and_admin_both_run_the_hydraulic_migration_flow(self):
        for role, email, password in (
            ("analyst", "analyst@example.local", "analyst pass"),
            ("admin", "admin@example.local", "admin pass"),
        ):
            with self.subTest(role=role):
                store = AnalystStore("sqlite:///:memory:")
                self.addCleanup(store.close)
                store.create_user(
                    email=email,
                    display_name=email,
                    role=role,
                    password_hash=hash_password(password),
                    created_by="test",
                )
                admin_bootstrap = store.create_user(
                    email="bootstrap-admin@example.local",
                    display_name="bootstrap-admin",
                    role="admin",
                    password_hash=hash_password("bootstrap pass"),
                    created_by="test",
                )
                admin_client = TestClient(create_app(store=store, auth_enabled=True))
                self.login(admin_client, "bootstrap-admin@example.local", "bootstrap pass")
                project = post_json_with_csrf(
                    admin_client, "/api/projects", {"name": "Migration parity"}
                ).json()
                scenario = post_json_with_csrf(
                    admin_client, f"/api/projects/{project['id']}/scenarios", {"name": "Base case"}
                ).json()
                diagram = post_json_with_csrf(
                    admin_client, f"/api/scenarios/{scenario['id']}/hydraulic-diagram"
                ).json()["diagram"]
                save_response = put_json_with_csrf(
                    admin_client,
                    f"/api/scenarios/{scenario['id']}/hydraulic-diagram",
                    {"revision": diagram["revision"], "nodes": [_reservoir_node()]},
                )
                node_entity_id = save_response.json()["diagram"]["nodes"][0]["entity_id"]
                legacy_set_id = self._seed_legacy_hydraulic_set_in(store, project["id"], node_entity_id)

                actor_client = TestClient(create_app(store=store, auth_enabled=True))
                self.login(actor_client, email, password)

                response = actor_client.post(
                    f"/api/projects/{project['id']}/time-series-sets/hydraulic/{legacy_set_id}/migrate",
                    headers=csrf_headers(actor_client),
                )
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(response.json()["already_migrated"], False)

    def _seed_legacy_hydraulic_set_in(self, store, project_id, case_node_id) -> int:
        base_row = store.connection.execute(
            "SELECT hydraulic_node_id FROM case_hydraulic_nodes WHERE id = ?",
            (case_node_id,),
        ).fetchone()
        base_entity_id = int(base_row[0])
        now = "2026-01-01T00:00:00+00:00"
        cursor = store.connection.execute(
            """
            INSERT INTO hydraulic_time_series_sets (
                project_id, entity_type, entity_id, signal_key, version_number,
                version_label, content_hash, status, created_at, updated_at,
                created_by, updated_by
            ) VALUES (?, 'hydraulic_node', ?, 'natural_inflow_m3s', 1, 'v1',
                      'legacy-seed-hash', 'draft', ?, ?, 'seed', 'seed')
            """,
            (project_id, base_entity_id, now, now),
        )
        set_id = int(cursor.lastrowid)
        store.connection.execute(
            """
            INSERT INTO hydraulic_time_series_points (
                hydraulic_time_series_set_id, point_index, timestamp,
                duration_hours, value
            ) VALUES (?, 0, '2026-01-01T00:00:00', 1.0, 1.5)
            """,
            (set_id,),
        )
        store.connection.commit()
        return set_id

    def test_analyst_and_admin_both_read_run_results_and_publications_preview(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_root = Path(temp_dir) / "artifacts"
            run = create_completed_run_with_result_artifacts(self.store, artifact_root)
            project_id = self.store.get_run_lineage(run["id"])["project_id"]
            template = self.store.create_dashboard_template(
                project_id=project_id, name="Parity Template", created_by="analyst@example.local"
            )
            publication = self.store.create_publication_draft(
                run_id=run["id"],
                dashboard_template_id=template["id"],
                public_title="Parity preview",
                allowed_artifact_types=["summary_json"],
                created_by="analyst@example.local",
            )

            admin = TestClient(create_app(store=self.store, artifact_root=artifact_root, auth_enabled=True))
            self.login(admin, "admin@example.local", "admin pass")
            analyst = TestClient(create_app(store=self.store, artifact_root=artifact_root, auth_enabled=True))
            self.login(analyst, "analyst@example.local", "analyst pass")

            for actor in (analyst, admin):
                with self.subTest(actor=actor):
                    results = actor.get(f"/api/runs/{run['id']}/results")
                    self.assertEqual(results.status_code, 200)

                    preview = actor.get(f"/api/publications/{publication['id']}/preview")
                    self.assertEqual(preview.status_code, 200)


class ClientOnlySeesPublishedOutputsTests(PermissionMatrixFixture):
    """Acceptance: client visibility is limited to published outputs on
    projects it has access to, never the underlying input series or
    unpublished result series -- even when a publication for the same run
    exists side by side."""

    def test_client_sees_publication_but_not_its_underlying_catalog_or_results(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_root = Path(temp_dir) / "artifacts"
            run = create_completed_run_with_result_artifacts(self.store, artifact_root)
            project_id = self.store.get_run_lineage(run["id"])["project_id"]
            self.store.set_external_project_access(
                project_id=project_id,
                user_id=self.client_user["id"],
                portal_view=True,
                operate=False,
                updated_by="admin@example.local",
            )
            template = self.store.create_dashboard_template(
                project_id=project_id, name="Client Template", created_by="analyst@example.local"
            )
            publication = self.store.create_publication_draft(
                run_id=run["id"],
                dashboard_template_id=template["id"],
                public_title="Client-visible dashboard",
                allowed_artifact_types=["summary_json"],
                created_by="analyst@example.local",
            )
            self.store.publish_publication(publication["id"], published_by="analyst@example.local")

            client = TestClient(create_app(store=self.store, artifact_root=artifact_root, auth_enabled=True))
            self.login(client, "client@example.local", "client pass")

            allowed = client.get(f"/api/client/projects/{project_id}/publications/{publication['id']}")
            self.assertEqual(allowed.status_code, 200)

            self.assertEqual(client.get(f"/api/runs/{run['id']}/results").status_code, 403)
            self.assertEqual(client.get(f"/api/projects/{project_id}/time-series-sets").status_code, 403)
            self.assertEqual(
                client.get(f"/api/projects/{project_id}/time-series-sets/hydraulic").status_code, 403
            )


if __name__ == "__main__":
    unittest.main()
