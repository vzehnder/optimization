# BESS-HYDRO-DIAGRAM-005: Generate And Validate A v3 Network Payload

Status: Done
Type: AFK
Triage: ready-for-agent
Source: `docs/hydro_diagram/iter1/prd_hydro_diagram_editor.md`

## User stories covered

16 through 18, 34 through 37, 42 through 48, 54, 59, 60, 65 through 67

## What to build

Generate the first read-only `bess_system_dispatch.v3` preview from the active
normalized hydraulic case. The payload should represent a minimal supported
network with active nodes, reaches, reservoir parameters, plant/unit mappings,
required curves and placeholder or bound time-series requirements.

The same path should call Julia-side `v3` validation without solving, show
errors in the React editor, persist the validation payload on success and mark
the case stale when topology, parameters, curves or series change.

## Acceptance criteria

- [x] The backend can generate a deterministic `bess_system_dispatch.v3`
      preview from the normalized case.
- [x] The preview includes active hydraulic nodes, reaches, plants, units,
      curves and required signal references.
- [x] The React editor displays the generated payload read-only.
- [x] Julia validation accepts a valid minimal `v3` payload.
- [x] Julia validation rejects unsupported schema versions and malformed v3
      network payloads with explicit errors.
- [x] Successful validation persists a validation snapshot for the normalized
      case.
- [x] Editing topology, parameters, curves or series after validation marks the
      validation stale and blocks promotion.
- [x] Existing `v1` and `v2` validation tests remain green.
- [x] Backend and Julia tests cover valid and invalid v3 preview/validation.
- [x] The DB checkpoint is updated if validation payload fields or dependencies
      are added.

## Implementation notes

- Added `/api/scenarios/{scenario_id}/hydraulic-diagram/v3-preview`.
- Generated `bess_system_dispatch.v3` from normalized active hydraulic nodes,
  reaches, plants, units, storage-elevation curves, flow-power curves and
  placeholder `natural_inflow_m3s` requirements.
- Stored successful v3 validation snapshots in
  `optimization_cases.validation_payload_json` with `validation_hash`,
  `system_case`, `julia_validation` and `stale` status.
- Marked prior v3 validation stale when saved diagram edits change the
  generated payload hash.
- Added Julia validation-only support for `bess_system_dispatch.v3` without
  routing it through the v1/v2 solver path.
- Added React read-only preview rendering through `Generar preview v3`.

## Verification

- `.\\.venv\\Scripts\\python.exe -m unittest tests.test_hydraulic_diagram`
- `.\\.venv\\Scripts\\python.exe -m unittest discover tests`
- `npm.cmd test`
- `npm.cmd run build`
- `npm.cmd run api:check`
- `julia --project=. test\\runtests.jl`
- Chrome smoke against `http://127.0.0.1:8124/react/scenarios/1/hydraulic-diagram`
  confirmed `Generar preview v3` renders a read-only payload containing
  `bess_system_dispatch.v3`.

Known verification note: `npm.cmd run check` passed TypeScript and ESLint, then
failed at repository-wide `prettier --check` because existing checkout
formatting/CRLF warnings still affect many frontend files.

## Blocked by

BESS-HYDRO-DIAGRAM-004
