# BESS-MVP-008: Generate Plotly Dispatch Report From Run Output

Status: Todo
Type: AFK
Source: `docs/prd_bess_dispatch.md`

## What to build

Create the first Python reporting path that reads a completed run output folder and writes an interactive Plotly HTML report. The report should let a user inspect price, dispatch, stored energy, and period economics without rerunning the optimization.

The script should depend on the persisted output contract, not on Julia internals.

## Acceptance criteria

- [ ] The script accepts a run output folder as input.
- [ ] The script reads `dispatch.csv` from that folder.
- [ ] The generated HTML includes price and dispatch traces.
- [ ] The generated HTML includes stored energy over time.
- [ ] The generated HTML includes period profit and degradation cost.
- [ ] The report is written under a `plots` folder inside the run output folder.
- [ ] A smoke check verifies that the HTML report is created for the sample run.

## Blocked by

- BESS-MVP-007
