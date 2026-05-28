# BESS-ITER2-007: Add Hybrid System Sample Case And Run Docs

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: `docs/iter2/prd_bess_system_dispatch.md`

## What to build

Add a sample hybrid system case and update run documentation for iteration 2.

The sample should demonstrate renewable generation, one battery, one grid connection, and enough price variation to show meaningful dispatch. A small load variant may be included to prove local demand behavior.

## Acceptance criteria

- [ ] A sample `system_case.json` exists for a renewable plus BESS plus grid system.
- [ ] The sample uses a single bus/PCC node and graph edges from assets to the bus.
- [ ] The sample includes common time-series records with timestamps, duration, price, and renewable availability.
- [ ] The sample includes battery parameters consistent with iteration 1 units.
- [ ] The sample includes grid import/export configuration.
- [ ] The sample produces renewable use, battery charge/discharge, grid import/export, and curtailment where applicable.
- [ ] Documentation shows how to run the system case through the Julia API.
- [ ] Documentation shows how to run the system case through the CLI.
- [ ] Documentation explains which outputs are produced.

## Verification

Run the documented commands and confirm the sample produces the expected output files.

## Blocked by

BESS-ITER2-006
