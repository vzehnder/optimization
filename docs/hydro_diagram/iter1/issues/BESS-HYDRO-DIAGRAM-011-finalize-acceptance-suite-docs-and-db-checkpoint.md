# BESS-HYDRO-DIAGRAM-011: Finalize Acceptance Suite Docs And DB Checkpoint

Status: Done
Type: AFK
Triage: ready-for-agent
Source: `docs/hydro_diagram/iter1/prd_hydro_diagram_editor.md`

## User stories covered

All user stories as final acceptance scope.

## What to build

Close the iteration with acceptance coverage, manual test instructions and an
updated DB checkpoint. The final proof should demonstrate a full analyst path:
create a hydraulic diagram, add reservoir, reaches, plant and unit, define
curves and inflow, validate, promote, run, inspect results and confirm legacy
v1/v2 behavior remains intact.

The documentation should capture the remaining gaps for future iterations:
topology import, routing, head-dependent generation, pumped storage and
collaborative editing.

## Acceptance criteria

- [x] Focused acceptance tests prove the minimal v3 hydraulic diagram workflow
      from creation through run results.
- [x] Browser coverage proves the React diagram is usable for the primary path.
- [x] Julia tests prove v3 solve behavior and v1/v2 regression.
- [x] Python backend tests prove API, validation, promotion and result behavior.
- [x] Manual test instructions are added under `docs/hydro_diagram/iter1/`.
- [x] `docs/db/hydro_diagram_db_checkpoint.md` reflects the actual final BBDD
      state of the iteration.
- [x] The local issue tracker progress log is updated with final verification
      commands and outcomes.
- [x] Known out-of-scope items are documented as future work.

## Resolution

Closed the Hydro Diagram Iteration 1 acceptance slice with a focused Python
acceptance guard, manual checklist, final issue-tracker verification section
and DB checkpoint closeout.

The accepted path proves the analyst workflow end to end:

1. Create a hydraulic diagram case.
2. Add reservoir, junctions, directed reach, plant and unit.
3. Define storage-elevation, flow-power and natural-inflow data.
4. Validate topology and generate a `bess_system_dispatch.v3` payload.
5. Promote the validated diagram to an immutable scenario version.
6. Run the version, inspect results and verify artifacts.

Future work remains explicitly out of scope for this iteration: topology import,
advanced routing, head-dependent generation, pumped storage, reversible units
and collaborative editing.

## Verification

- `.\\.venv\\Scripts\\python.exe -m unittest tests.test_hydro_diagram_acceptance -v`
  (2 ok).
- `.\\.venv\\Scripts\\python.exe -m unittest tests.test_hydraulic_diagram -v`
  (45 ok).
- `.\\.venv\\Scripts\\python.exe -m unittest discover tests -v`
  (157 ok, 1 skipped).
- `julia --project=. -e "import Pkg; Pkg.test()"`
  (532 ok; first 5 minute attempt timed out during compilation/setup, retry
  completed).
- `npm.cmd test` (26 ok).
- `npm.cmd run check` reached Prettier and failed only on pre-existing frontend
  formatting/CRLF warnings; `npx.cmd tsc -b --pretty false` and
  `npx.cmd eslint .` both passed.
- `npm.cmd run api:generate` and `npm.cmd run api:check` passed with no tracked
  OpenAPI diff.
- `npm.cmd run test:browser -- -g "hydraulic diagram persists"` passed (1
  Playwright browser test).
- Chrome/@chrome read-only smoke loaded the local React app at `/react` and
  verified the visible bootstrap DOM; the interactive primary path is covered
  by the Playwright browser test above.

## Blocked by

BESS-HYDRO-DIAGRAM-001 through BESS-HYDRO-DIAGRAM-010
