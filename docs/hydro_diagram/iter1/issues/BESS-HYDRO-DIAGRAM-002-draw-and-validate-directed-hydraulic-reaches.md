# BESS-HYDRO-DIAGRAM-002: Draw And Validate Directed Hydraulic Reaches

Status: Todo
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

- [ ] The UI supports creating a directed reach by drag-and-drop between
      compatible visible nodes.
- [ ] The UI supports editing reach origin, destination and type through a form
      fallback.
- [ ] Supported reach types include `river`, `canal`, `tunnel`, `gate`,
      `spillway`, `bypass`, `tailrace` and `other`.
- [ ] Saved reaches reload with direction and type intact.
- [ ] Backend validation rejects active reaches whose origin or destination is
      inactive or outside the case.
- [ ] Validation results identify affected entity type and entity id so the UI
      can select the component.
- [ ] The UI displays validation warnings and errors without erasing local
      edits.
- [ ] Backend tests cover valid directed reaches, missing endpoints, inactive
      endpoints and type validation.
- [ ] React tests cover drag creation and form fallback editing.
- [ ] The DB checkpoint is updated if reach tables, constraints or indices are
      changed.

## Blocked by

BESS-HYDRO-DIAGRAM-001

