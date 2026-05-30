# BESS-ITER4-001: Run A Separate Import Export Price Case End To End

Status: Done
Type: AFK
Triage: ready-for-agent
Source: `docs/iter4/prd_structured_editor_flow.md`

## User stories covered

31, 51 through 54, 61 through 63

## What to build

Add backward-compatible support for separate import and export prices across the
Julia one-bus system-dispatch flow and the web result-reading flow.

A valid case may continue to provide `price_usd_per_mwh`, or it may provide both
`import_price_usd_per_mwh` and `export_price_usd_per_mwh` per period. Separate
prices must drive the objective and outputs when present, while legacy
single-price cases continue to solve and render as before.

## Acceptance criteria

- [x] Existing `price_usd_per_mwh` system cases validate, solve, and produce
      compatible outputs.
- [x] A system case with `import_price_usd_per_mwh` and
      `export_price_usd_per_mwh` validates and solves end to end through the
      stable Julia CLI.
- [x] Validation rejects periods where only one of the two separate price fields
      is provided.
- [x] The objective uses import price for grid imports and export price for grid
      exports.
- [x] Dispatch outputs include separate import and export price columns when
      present.
- [x] Dispatch outputs expose import cost, export revenue, net market value,
      degradation cost, curtailment penalty, and period profit.
- [x] Summary or metadata records whether the case used legacy single-price or
      separate-price economics.
- [x] The Python result reader handles both legacy and separate-price outputs.
- [x] Basic charts prefer separate price series when available and fall back to
      legacy single price otherwise.
- [x] Julia regression tests and Python result tests cover both price modes.

## Implementation notes

- Extended `bess_system_dispatch.v1` period parsing so a period can use either
  legacy `price_usd_per_mwh` or paired `import_price_usd_per_mwh` and
  `export_price_usd_per_mwh`.
- Kept legacy single-price cases backward-compatible by deriving import/export
  prices from the legacy field and preserving the existing legacy output column
  shape.
- Added separate-price objective accounting using import cost for grid imports
  and export revenue for grid exports.
- Added separate-price output columns when present:
  `import_price_usd_per_mwh`, `export_price_usd_per_mwh`, `import_cost_usd`,
  `export_revenue_usd`, and `net_market_value_usd`.
- Added `price_mode` to system summaries and model metadata.
- Updated the Python result chart payloads so the price chart prefers separate
  import/export price series and falls back to `price_usd_per_mwh`.

## Verification

Passed:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
julia --project=. -e "import Pkg; Pkg.test()"
```

Results:

- Python web/API/template/results tests: 41 passed.
- Julia package tests: 372 passed.
- A rendered run-results HTML smoke artifact confirmed the separate-price chart
  and table columns for `import_price_usd_per_mwh`,
  `export_price_usd_per_mwh`, `import_cost_usd`, `export_revenue_usd`,
  `net_market_value_usd`, and `period_profit_usd`.

Browser note: attempted the requested Browser workflow twice, but the
`node_repl` browser-control runtime failed to start with
`windows sandbox failed: spawn setup refresh`. Attempted the requested Chrome
DevTools MCP workflow, but it failed before listing pages because the
Chrome DevTools MCP profile was already in use.

## Blocked by

BESS-ITER4-000
