# BESS-ITER5-005: Map Hydro Inflows From CSV And XLSX

Status: Todo
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

- [ ] CSV ingestion suggests hydro inflow mappings for well-named columns.
- [ ] XLSX ingestion suggests hydro inflow mappings for well-named columns.
- [ ] Manual mapping can assign `hydro_inflow_m3s.<hydro_id>` columns.
- [ ] Mapping validation requires hydro inflow for every hydro asset.
- [ ] Mapping validation rejects negative hydro inflow values.
- [ ] Mapping validation rejects nonnumeric or missing hydro inflow values.
- [ ] Validated rows include `hydro_inflow_m3s` keyed by hydro asset ID.
- [ ] Generated `v2` periods include hydro inflow maps.
- [ ] Source-file provenance and accepted mapping metadata include hydro
      mappings.
- [ ] Existing price, renewable availability, and load demand mapping
      behavior remains unchanged.

## Blocked by

BESS-ITER5-004
