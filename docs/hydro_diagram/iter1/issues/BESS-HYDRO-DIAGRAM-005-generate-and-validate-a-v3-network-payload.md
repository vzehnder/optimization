# BESS-HYDRO-DIAGRAM-005: Generate And Validate A v3 Network Payload

Status: Todo
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

- [ ] The backend can generate a deterministic `bess_system_dispatch.v3`
      preview from the normalized case.
- [ ] The preview includes active hydraulic nodes, reaches, plants, units,
      curves and required signal references.
- [ ] The React editor displays the generated payload read-only.
- [ ] Julia validation accepts a valid minimal `v3` payload.
- [ ] Julia validation rejects unsupported schema versions and malformed v3
      network payloads with explicit errors.
- [ ] Successful validation persists a validation snapshot for the normalized
      case.
- [ ] Editing topology, parameters, curves or series after validation marks the
      validation stale and blocks promotion.
- [ ] Existing `v1` and `v2` validation tests remain green.
- [ ] Backend and Julia tests cover valid and invalid v3 preview/validation.
- [ ] The DB checkpoint is updated if validation payload fields or dependencies
      are added.

## Blocked by

BESS-HYDRO-DIAGRAM-004

