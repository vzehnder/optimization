"""One promoted plant/reservoir and independent CMg for real mesa execution."""

from app.time_series_catalog import CatalogImportRequest, CatalogSignalMappingRequest, prepare_time_series_catalog_import
from tests.mesa_hydraulic_fixture import seed_hydraulic_mesa


def seed_executable_hydraulic_mesa(store, *, name="Ejecución hidráulica"):
    fixture = seed_hydraulic_mesa(store, name=name, single_plant=True)
    scenario_id = fixture["scenario"]["id"]
    document = store.generate_hydraulic_v3_preview(scenario_id)
    fixture["version"] = store.create_scenario_version(scenario_id=scenario_id, system_case_json=document,
        validation_payload={"status": "ok"}, generation_metadata={"kind": "hydraulic_diagram_v3"})
    store.persist_scenario_version_hydraulic_diagram_snapshot(scenario_version_id=fixture["version"]["id"],
        layout_snapshot={"schema_version": "hydraulic_diagram_layout.v1", "nodes": [], "reaches": []},
        source_case_id=fixture["case"]["id"])
    fixture["prices"] = store.import_time_series_catalog_set(scenario_id=scenario_id,
        source={"id": "cmg", "original_filename": "cmg.csv", "media_type": "text/csv", "checksum": "cmg-v1"},
        prepared_import=prepare_time_series_catalog_import(
            rows=[{"timestamp": f"2026-10-20T0{i}:00:00+00:00", "duration_hours": "1", "price": str(p)}
                  for i, p in enumerate([10, 90])],
            request=CatalogImportRequest(set_name="CMg hidráulico", version_label="v1", data_kind="synthetic", timezone="UTC",
                timestamp_column="timestamp", duration_hours_column="duration_hours",
                signal_mappings=[CatalogSignalMappingRequest(source_column="price", signal_key="price_usd_per_mwh")]),
        ))
    return fixture
