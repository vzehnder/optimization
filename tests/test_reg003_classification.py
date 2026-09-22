"""Opening a pre-REG003 database must preserve custom classification IDs."""
import sqlite3
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient
from app.main import create_app
from app.persistence import AnalystStore


class AdditiveRuleClassificationTests(unittest.TestCase):
    def test_existing_custom_type_at_id_nine_survives_installation(self):
        with tempfile.TemporaryDirectory(prefix="reg003-upgrade-") as temporary:
            path = Path(temporary) / "previous.sqlite3"
            # The persisted TS-7 table, before availability_factor was introduced.
            with sqlite3.connect(path) as connection:
                connection.executescript('''
                    CREATE TABLE time_series_semantic_types (
                        id INTEGER PRIMARY KEY AUTOINCREMENT, semantic_key TEXT NOT NULL UNIQUE,
                        display_name TEXT NOT NULL, description TEXT NOT NULL DEFAULT '',
                        dimension_id INTEGER NOT NULL, canonical_unit_id INTEGER NOT NULL,
                        value_kind TEXT NOT NULL DEFAULT 'numeric', default_aggregation TEXT NOT NULL,
                        validation_rules_json TEXT NOT NULL DEFAULT '{}', is_system INTEGER NOT NULL DEFAULT 0,
                        status TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                        created_by TEXT NOT NULL, updated_by TEXT NOT NULL
                    );
                    INSERT INTO time_series_semantic_types VALUES
                        (9, 'custom_fraction', 'Fracción propia', 'Tipo existente', 4, 4, 'numeric', 'mean',
                         '{}', 0, 'active', '2026-01-01', '2026-01-01', 'analyst', 'analyst');
                ''')
            connection.close()
            for _ in range(2):
                store = AnalystStore(f"sqlite:///{path}")
                with TestClient(create_app(store=store, auth_enabled=False)) as client:
                    response = client.get("/api/time-series/catalog/descriptors?kind=semantic_type")
                    self.assertEqual(response.status_code, 200, response.text)
                    self.assertIn("custom_fraction", response.text)
                    self.assertIn("availability_factor", response.text)
                store.close()
