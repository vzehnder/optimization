# BESS-HYDRO-DIAGRAM-007: Bind Natural Inflow Series To Hydraulic Nodes

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: `docs/hydro_diagram/iter1/prd_hydro_diagram_editor.md`

## User stories covered

34 through 37, 48 through 54, 56, 57, 60 through 62

## What to build

Add the complete time-series path for `natural_inflow_m3s` on hydraulic nodes.
An analyst can bind an imported or existing versioned time-series signal to any
active hydraulic node, validate required inflows, generate a v3 payload with the
bound hydrology and run the minimal network using that series.

This slice should reuse the existing time-series ingestion/versioning patterns
where possible and avoid topology import.

## Acceptance criteria

- [ ] The UI can show and edit `natural_inflow_m3s` bindings for active
      hydraulic nodes.
- [ ] Bindings target `case_hydraulic_node` entities, not only reservoirs.
- [ ] Existing CSV/XLSX ingestion can map a column to a hydraulic node inflow
      signal or an equivalent API path exists.
- [ ] Validation rejects missing required inflow bindings.
- [ ] Validation rejects negative and nonnumeric inflow values.
- [ ] The v3 payload includes the resolved inflow series for the active node.
- [ ] A diagram-promoted v3 run uses the bound series in the water balance.
- [ ] Tests cover successful binding, missing binding, negative values and
      horizon mismatch.
- [ ] The DB checkpoint records any implemented series binding changes.

## Blocked by

BESS-HYDRO-DIAGRAM-006

