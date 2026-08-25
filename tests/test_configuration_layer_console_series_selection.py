"""Named console-series source selection through the persistence seam."""

import unittest
from dataclasses import replace
from datetime import datetime, timedelta

from app.console_series import ConsoleSeriesError
from app.persistence import AnalystStore
from app.time_series_catalog import (
    CatalogImportRequest,
    CatalogSignalMappingRequest,
    compute_catalog_content_hash,
    prepare_time_series_catalog_import,
)


def import_demand_set(
    store: AnalystStore,
    scenario_id: int,
    *,
    name: str,
    first_value: float,
    period_count: int = 4,
    entity_key: str | None = None,
) -> dict:
    start = datetime(2026, 1, 1)
    prepared = prepare_time_series_catalog_import(
        rows=[
            {
                "period_start": (start + timedelta(hours=offset)).isoformat(),
                "hours": "1.0",
                "demand": str(first_value + offset),
            }
            for offset in range(period_count)
        ],
        request=CatalogImportRequest(
            set_name=name,
            version_label="v1",
            data_kind="real",
            timezone="America/Santiago",
            timestamp_column="period_start",
            duration_hours_column="hours",
            signal_mappings=[
                CatalogSignalMappingRequest(
                    source_column="demand", signal_key="load_demand_mw"
                )
            ],
        ),
    )
    if entity_key is not None:
        signals = [replace(signal, entity_key=entity_key) for signal in prepared.signals]
        values = [replace(value, entity_key=entity_key) for value in prepared.values]
        prepared = replace(
            prepared,
            signals=signals,
            values=values,
            content_hash=compute_catalog_content_hash(
                set_name=prepared.set_name,
                version_label=prepared.version_label,
                data_kind=prepared.data_kind,
                timezone=prepared.timezone,
                signals=[signal.__dict__ for signal in signals],
                periods=[period.__dict__ for period in prepared.periods],
                values=[value.__dict__ for value in values],
            ),
        )
    return store.import_time_series_catalog_set(
        scenario_id=scenario_id,
        source={
            "id": f"{name}-source",
            "original_filename": f"{name}.csv",
            "media_type": "text/csv",
            "checksum": f"sha256:{name}",
        },
        prepared_import=prepared,
    )


class ConsoleSeriesSelectionPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.store = AnalystStore("sqlite:///:memory:")
        self.project = self.store.create_project(name="Planta Norte")
        self.scenario = self.store.create_scenario(
            project_id=self.project["id"], name="Operacion diaria"
        )
        self.case = self.store.get_or_create_case_for_scenario(self.scenario["id"])
        self.source_variant = self.store.get_or_create_default_input_variant(
            self.case["id"]
        )
        self.analyst = self.store.create_user(
            email="analyst@example.local",
            display_name="Ana Analista",
            role="analyst",
            password_hash="test-hash",
        )
        self.operator = self.store.create_user(
            email="operator@example.local",
            display_name="Olga Operadora",
            role="external",
            password_hash="test-hash",
        )
        self.base_set = import_demand_set(
            self.store,
            self.scenario["id"],
            name="Demanda base",
            first_value=10,
        )
        self.forecast_set = import_demand_set(
            self.store,
            self.scenario["id"],
            name="Pronostico actualizado",
            first_value=20,
        )
        self.store.upsert_case_time_series_binding(
            case_input_variant_id=self.source_variant["id"],
            signal_key="load_demand_mw",
            time_series_set_id=self.base_set["id"],
        )
        self.console = self.store.create_operator_console(
            case_id=self.case["id"],
            source_variant_id=self.source_variant["id"],
            document={
                "schema_version": "operator_console_config.v1",
                "public_identity": {"name": "Plan diario", "description": ""},
                "parameters": [],
                "groups": [
                    {
                        "id": "potencia",
                        "label": "Potencia",
                        "granularities": ["full_horizon"],
                        "columns": [
                            {
                                "id": "demanda",
                                "signal": {
                                    "entity_type": "component:load",
                                    "entity_id": "load_1",
                                    "signal_key": "load_demand_mw",
                                },
                                "label": "Demanda",
                                "editable": True,
                                "source_options": [
                                    {
                                        "id": "base",
                                        "label": "Demanda base",
                                        "time_series_set_id": self.base_set["id"],
                                    },
                                    {
                                        "id": "pronostico",
                                        "label": "Pronostico actualizado",
                                        "time_series_set_id": self.forecast_set["id"],
                                    },
                                ],
                                "default_source_option_id": "base",
                            }
                        ],
                    }
                ],
                "results": {"kpis": [], "charts": [], "tables": []},
            },
            created_by_user_id=self.analyst["id"],
        )

    def tearDown(self):
        self.store.close()

    def test_series_options_expose_only_public_ids_labels_and_initial_selection(self):
        options = self.store.resolve_operator_console_series_options(
            self.console["id"]
        )

        self.assertEqual(
            options,
            {
                "selections": [
                    {
                        "group_id": "potencia",
                        "column_id": "demanda",
                        "selected_source_option_id": "base",
                        "options": [
                            {"id": "base", "label": "Demanda base"},
                            {
                                "id": "pronostico",
                                "label": "Pronostico actualizado",
                            },
                        ],
                    }
                ]
            },
        )

    def test_selecting_a_named_source_forks_it_and_rebinds_only_the_console(self):
        canonical_before = self.store.get_time_series_set(
            self.project["id"], self.forecast_set["id"]
        )
        other_console = self.store.create_operator_console(
            case_id=self.case["id"],
            source_variant_id=self.source_variant["id"],
            document=self.console["document"],
            created_by_user_id=self.analyst["id"],
        )

        self.store.replace_operator_console_series_selections(
            self.console["id"],
            selections=[
                {
                    "group_id": "potencia",
                    "column_id": "demanda",
                    "source_option_id": "pronostico",
                }
            ],
            actor_user_id=self.operator["id"],
        )

        copy = self.store.list_operator_console_series_copies(self.console["id"])[0]
        self.assertEqual(copy["origin_set_id"], self.forecast_set["id"])
        self.assertEqual(
            copy["origin_revision_number"], self.forecast_set["revision_number"]
        )
        self.assertEqual(
            self.store.get_time_series_set(
                self.project["id"], self.forecast_set["id"]
            ),
            canonical_before,
        )
        self.assertEqual(
            [
                binding["time_series_set_id"]
                for binding in self.store.list_case_time_series_bindings(
                    self.console["owned_variant_id"]
                )
            ],
            [copy["time_series_set_id"]],
        )
        self.assertEqual(
            [
                binding["time_series_set_id"]
                for binding in self.store.list_case_time_series_bindings(
                    self.source_variant["id"]
                )
            ],
            [self.base_set["id"]],
        )
        self.assertEqual(
            [
                binding["time_series_set_id"]
                for binding in self.store.list_case_time_series_bindings(
                    other_console["owned_variant_id"]
                )
            ],
            [self.base_set["id"]],
        )

    def test_columns_selecting_the_same_source_share_one_operational_copy(self):
        document = self.console["document"]
        group = document["groups"][0]
        original_column = group["columns"][0]
        self.console = self.store.save_operator_console(
            self.console["id"],
            document={
                **document,
                "groups": [
                    {
                        **group,
                        "columns": [
                            original_column,
                            {
                                **original_column,
                                "id": "demanda_referencia",
                                "label": "Demanda de referencia",
                            },
                        ],
                    }
                ],
            },
            status="active",
            expected_revision=self.console["revision"],
            updated_by_user_id=self.analyst["id"],
        )

        self.store.replace_operator_console_series_selections(
            self.console["id"],
            selections=[
                {
                    "group_id": "potencia",
                    "column_id": column_id,
                    "source_option_id": "pronostico",
                }
                for column_id in ("demanda", "demanda_referencia")
            ],
            actor_user_id=self.operator["id"],
        )

        copies = self.store.list_operator_console_series_copies(
            self.console["id"], include_archived=True
        )
        self.assertEqual(len(copies), 1)
        self.assertEqual(copies[0]["origin_set_id"], self.forecast_set["id"])
        self.assertIsNone(copies[0]["archived_at"])
        self.assertEqual(
            {
                entry["selected_source_option_id"]
                for entry in self.store.resolve_operator_console_series_options(
                    self.console["id"]
                )["selections"]
            },
            {"pronostico"},
        )

    def test_switching_again_archives_the_replaced_copy_without_rewriting_it(self):
        self.store.replace_operator_console_series_selections(
            self.console["id"],
            selections=[
                {
                    "group_id": "potencia",
                    "column_id": "demanda",
                    "source_option_id": "pronostico",
                }
            ],
            actor_user_id=self.operator["id"],
        )
        forecast_copy = self.store.list_operator_console_series_copies(
            self.console["id"]
        )[0]
        forecast_values_before = self.store.get_time_series_set(
            self.project["id"], forecast_copy["time_series_set_id"]
        )

        self.store.replace_operator_console_series_selections(
            self.console["id"],
            selections=[
                {
                    "group_id": "potencia",
                    "column_id": "demanda",
                    "source_option_id": "base",
                }
            ],
            actor_user_id=self.operator["id"],
        )

        copies = self.store.list_operator_console_series_copies(
            self.console["id"], include_archived=True
        )
        archived = next(copy for copy in copies if copy["id"] == forecast_copy["id"])
        active = next(copy for copy in copies if copy["archived_at"] is None)
        self.assertIsNotNone(archived["archived_at"])
        self.assertEqual(active["origin_set_id"], self.base_set["id"])
        self.assertEqual(
            self.store.get_time_series_set(
                self.project["id"], forecast_copy["time_series_set_id"]
            ),
            forecast_values_before,
        )

    def test_an_incompatible_source_is_rejected_without_changing_the_selection(self):
        short_set = import_demand_set(
            self.store,
            self.scenario["id"],
            name="Pronostico corto",
            first_value=30,
            period_count=2,
        )
        document = self.console["document"]
        group = document["groups"][0]
        column = group["columns"][0]
        self.console = self.store.save_operator_console(
            self.console["id"],
            document={
                **document,
                "groups": [
                    {
                        **group,
                        "columns": [
                            {
                                **column,
                                "source_options": [
                                    *column["source_options"],
                                    {
                                        "id": "corto",
                                        "label": "Pronostico corto",
                                        "time_series_set_id": short_set["id"],
                                    },
                                ],
                            }
                        ],
                    }
                ],
            },
            status="active",
            expected_revision=self.console["revision"],
            updated_by_user_id=self.analyst["id"],
        )

        with self.assertRaises(ConsoleSeriesError):
            self.store.replace_operator_console_series_selections(
                self.console["id"],
                selections=[
                    {
                        "group_id": "potencia",
                        "column_id": "demanda",
                        "source_option_id": "corto",
                    }
                ],
                actor_user_id=self.operator["id"],
            )

        self.assertEqual(
            self.store.list_operator_console_series_copies(self.console["id"]), []
        )
        self.assertEqual(
            self.store.resolve_operator_console_series_options(self.console["id"])[
                "selections"
            ][0]["selected_source_option_id"],
            "base",
        )

    def test_a_source_scoped_to_another_entity_is_rejected(self):
        other_load_set = import_demand_set(
            self.store,
            self.scenario["id"],
            name="Demanda otra carga",
            first_value=30,
            entity_key="load_2",
        )
        document = self.console["document"]
        group = document["groups"][0]
        column = group["columns"][0]
        self.console = self.store.save_operator_console(
            self.console["id"],
            document={
                **document,
                "groups": [
                    {
                        **group,
                        "columns": [
                            {
                                **column,
                                "source_options": [
                                    *column["source_options"],
                                    {
                                        "id": "otra_carga",
                                        "label": "Demanda otra carga",
                                        "time_series_set_id": other_load_set["id"],
                                    },
                                ],
                            }
                        ],
                    }
                ],
            },
            status="active",
            expected_revision=self.console["revision"],
            updated_by_user_id=self.analyst["id"],
        )

        with self.assertRaises(ConsoleSeriesError):
            self.store.replace_operator_console_series_selections(
                self.console["id"],
                selections=[
                    {
                        "group_id": "potencia",
                        "column_id": "demanda",
                        "source_option_id": "otra_carga",
                    }
                ],
                actor_user_id=self.operator["id"],
            )

        self.assertEqual(
            self.store.list_operator_console_series_copies(self.console["id"]), []
        )

    def test_a_stale_option_rolls_back_every_selection_in_the_request(self):
        other_project = self.store.create_project(name="Otra planta")
        other_scenario = self.store.create_scenario(
            project_id=other_project["id"], name="Otro escenario"
        )
        foreign_set = import_demand_set(
            self.store,
            other_scenario["id"],
            name="Fuente ajena",
            first_value=40,
        )
        document = self.console["document"]
        group = document["groups"][0]
        column = group["columns"][0]
        self.console = self.store.save_operator_console(
            self.console["id"],
            document={
                **document,
                "groups": [
                    {
                        **group,
                        "columns": [
                            column,
                            {
                                **column,
                                "id": "demanda_referencia",
                                "label": "Demanda de referencia",
                                "source_options": [
                                    {
                                        "id": "ajena",
                                        "label": "Fuente ajena",
                                        "time_series_set_id": foreign_set["id"],
                                    }
                                ],
                                "default_source_option_id": "ajena",
                            },
                        ],
                    }
                ],
            },
            status="active",
            expected_revision=self.console["revision"],
            updated_by_user_id=self.analyst["id"],
        )

        with self.assertRaises(ConsoleSeriesError) as raised:
            self.store.replace_operator_console_series_selections(
                self.console["id"],
                selections=[
                    {
                        "group_id": "potencia",
                        "column_id": "demanda",
                        "source_option_id": "pronostico",
                    },
                    {
                        "group_id": "potencia",
                        "column_id": "demanda_referencia",
                        "source_option_id": "ajena",
                    },
                ],
                actor_user_id=self.operator["id"],
            )

        self.assertEqual(raised.exception.status_code, 409)
        self.assertEqual(
            self.store.list_operator_console_series_copies(self.console["id"]), []
        )
        self.assertEqual(
            {
                binding["time_series_set_id"]
                for binding in self.store.list_case_time_series_bindings(
                    self.console["owned_variant_id"]
                )
            },
            {self.base_set["id"]},
        )


if __name__ == "__main__":
    unittest.main()
