# BESS-ITER5-005: Map Hydro Inflows From CSV And XLSX

Status: Done
Type: AFK
Triage: ready-for-agent
Source: `docs/iter5/prd_hydro_simple_dispatch.md`

## User stories covered

40 through 42, 64

## What to build

Extend the time-series ingestion and mapping flow so CSV and XLSX sources can
provide `hydro_inflow_m3s` values by hydro asset ID.

The source preview, mapping suggestions, manual mapping save, Python validation,
generated periods, and provenance metadata should include hydro inflow while
preserving the existing price, renewable, and load mapping behavior.

## Acceptance criteria

- [x] CSV ingestion suggests hydro inflow mappings for well-named columns.
- [x] XLSX ingestion suggests hydro inflow mappings for well-named columns.
- [x] Manual mapping can assign `hydro_inflow_m3s.<hydro_id>` columns.
- [x] Mapping validation requires hydro inflow for every hydro asset.
- [x] Mapping validation rejects negative hydro inflow values.
- [x] Mapping validation rejects nonnumeric or missing hydro inflow values.
- [x] Validated rows include `hydro_inflow_m3s` keyed by hydro asset ID.
- [x] Generated `v2` periods include hydro inflow maps.
- [x] Source-file provenance and accepted mapping metadata include hydro
      mappings.
- [x] Existing price, renewable availability, and load demand mapping
      behavior remains unchanged.

## Implementation notes

Completed on 2026-06-05.

- Added hydro inflow mapping suggestions and validation to the shared CSV/XLSX
  time-series ingestion path.
- Added manual SSR mapping support for `hydro_inflow_m3s.<hydro_id>`.
- Generated `bess_system_dispatch.v2` preview periods now include
  `hydro_inflow_m3s` maps when hydro rows are present.
- Preserved existing price, renewable availability, load demand, source
  provenance, and safe mapping metadata behavior.

## Verification

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_csv_time_series_ingestion -v
.\.venv\Scripts\python.exe -m unittest tests.test_draft_generated_system_case -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Result: 77 Python web/API/template/regression tests passed.

Chrome DevTools MCP verification opened a local draft page, confirmed the
`hydro_inflow_m3s.hydro_1` mapping field, `Valid mapped rows: 1`, and a
generated `bess_system_dispatch.v2` preview containing `hydro_inflow_m3s`.
The console had no messages and the draft page loaded with HTTP 200.

## Blocked by

BESS-ITER5-004
