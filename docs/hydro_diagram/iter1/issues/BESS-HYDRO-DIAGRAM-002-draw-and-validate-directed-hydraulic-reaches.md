# BESS-HYDRO-DIAGRAM-002: Draw And Validate Directed Hydraulic Reaches

Status: Done
Type: AFK
Triage: ready-for-agent
Source: `docs/hydro_diagram/iter1/prd_hydro_diagram_editor.md`

## User stories covered

8 through 12, 16, 42 through 45, 57 through 60

## What to build

Add directed hydraulic reaches to the diagram as a complete edit-save-validate
path. An analyst can connect active nodes with a directed reach using
drag-and-drop, edit the same connection from a form fallback, choose a reach
type, save, reload and run topology validation that points errors back to the
affected diagram component.

The validator should prove that active reaches connect active nodes in the same
case and that unsupported graph structures are identified without preventing
the analyst from drawing them.

## Acceptance criteria

- [x] The UI supports creating a directed reach by drag-and-drop between
      compatible visible nodes.
- [x] The UI supports editing reach origin, destination and type through a form
      fallback.
- [x] Supported reach types include `river`, `canal`, `tunnel`, `gate`,
      `spillway`, `bypass`, `tailrace` and `other`.
- [x] Saved reaches reload with direction and type intact.
- [x] Backend validation rejects active reaches whose origin or destination is
      inactive or outside the case.
- [x] Validation results identify affected entity type and entity id so the UI
      can select the component.
- [x] The UI displays validation warnings and errors without erasing local
      edits.
- [x] Backend tests cover valid directed reaches, missing endpoints, inactive
      endpoints and type validation.
- [x] React tests cover drag creation and form fallback editing.
- [x] The DB checkpoint is updated if reach tables, constraints or indices are
      changed.

## Implementation notes

Implemented on 2026-06-26.

- Added `hydraulic_reaches` and `case_hydraulic_reaches`, plus reach layout
  items under `case_hydraulic_diagram_items`.
- Extended the hydraulic diagram API payload and response with directed
  reaches and added `/api/scenarios/{scenario_id}/hydraulic-diagram/validate`.
- Added backend topology validation for allowed reach types and active endpoint
  membership, with affected `entity_type`, `entity_id` and `technical_key`.
- Added React drag/drop reach creation, fallback origin/destination/type form
  editing, validation display, and persisted reload coverage.
- Hardened Playwright smoke startup so stale servers on port 8123 are rejected.

## Verification

- `.\\.venv\\Scripts\\python.exe -m unittest tests.test_hydraulic_diagram`
- `.\\.venv\\Scripts\\python.exe -m unittest discover tests`
- `npm.cmd test`
- `npm.cmd run api:check`
- `npm.cmd run test:browser`
- `npx.cmd tsc -b --pretty false`
- `npx.cmd eslint src\\Workspace.tsx src\\App.test.tsx src\\api\\client.ts e2e\\react-foundation.spec.ts e2e\\global-setup.ts`
- `npx.cmd prettier --check src\\Workspace.tsx src\\App.test.tsx src\\api\\client.ts src\\api\\schema.ts src\\styles.css e2e\\react-foundation.spec.ts e2e\\global-setup.ts openapi.json`

## Blocked by

BESS-HYDRO-DIAGRAM-001
