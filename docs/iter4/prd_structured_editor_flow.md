# Structured Editor And Time-Series Ingestion PRD

## Problem Statement

Iteration 3 proved the private analyst web workflow around the Julia one-bus
hybrid optimizer. An analyst can create projects and scenarios, save immutable
scenario versions from a complete `system_case.json`, validate through Julia,
launch manual runs, inspect artifacts, review result tables, and see basic
charts.

That flow is usable for an engineer, but it still requires the analyst to author
or upload a complete JSON optimization contract. The product cannot become a
practical modeling application while the primary input path is hand-written
JSON.

The next gap is the structured creation of optimization cases from the web app:
forms for the one-bus model, asset parameters, solver settings, uploaded
time-series files, column mapping, generated-case preview, Julia validation, and
promotion into the existing immutable scenario-version flow.

The second gap is economic fidelity for customer-ready cases. Iteration 2 and
Iteration 3 use one grid price per period for both imports and exports. The
final product objective requires separate import and export prices before the
application can be considered client-ready, because many real behind-the-meter,
netmetering, regulated, or PPA-like cases buy and sell energy at different
prices.

Iteration 4 must therefore make the analyst input workflow real without
destabilizing the optimizer, the audit trail, or the existing paste/upload JSON
flow.

## Solution

Build a structured server-rendered editor around the existing one-bus
`system_case` contract.

An analyst can create or edit one active draft under a scenario, define the PCC
and connected assets through forms, upload CSV or Excel time-series data, map
columns to required model fields, preview the generated `system_case`, validate
it through Julia, and promote it to an immutable `ScenarioVersion`.

The existing Iteration 3 path remains intact:

```text
Paste or upload system_case_json
-> Julia validation
-> immutable ScenarioVersion
-> manual Run
-> auditable artifacts and results
```

Iteration 4 adds a parallel structured path:

```text
Scenario
-> ScenarioDraft
-> structured asset and solver forms
-> CSV/XLSX upload
-> preview and column mapping
-> generated system_case preview
-> Julia validation
-> immutable ScenarioVersion
-> manual Run
-> auditable artifacts and results
```

The draft is mutable and may be incomplete. The scenario version remains
immutable and executable. Runs continue to point only to immutable scenario
versions, never to drafts.

The Julia optimizer remains the mathematical authority. Python performs editor
and file-ingestion validation before generating the candidate `system_case`;
Julia validates the final contract before promotion and execution.

The Julia system-dispatch contract is extended in a backward-compatible way to
support separate per-period import and export prices. Existing cases using
`price_usd_per_mwh` continue to validate and solve. New cases may provide
`import_price_usd_per_mwh` and `export_price_usd_per_mwh`, which take precedence
for objective, outputs, result tables, and charts.

## User Stories

1. As an analyst, I want to create an editable draft under a scenario, so that I
   can build a model before it is valid enough to become a version.
2. As an analyst, I want a scenario to have one active draft, so that the
   private workflow stays simple and avoids parallel editing conflicts.
3. As an analyst, I want to save draft progress, so that I can return to an
   incomplete model later.
4. As an analyst, I want to create a draft from an existing scenario version, so
   that I can iterate from a validated model instead of starting over.
5. As an analyst, I want draft edits not to modify existing scenario versions,
   so that prior run inputs remain auditable.
6. As an analyst, I want to define case name and basic metadata in the editor,
   so that generated cases are recognizable in version and run listings.
7. As an analyst, I want the editor to create exactly one PCC or bus, so that
   the generated model remains a one-bus case.
8. As an analyst, I want to configure a grid connection, so that imports,
   exports, limits, and anti-simultaneity are represented without editing JSON.
9. As an analyst, I want to enter import and export power limits, so that
   constrained interconnection cases can be represented.
10. As an analyst, I want to enable or disable grid import/export
    anti-simultaneity, so that the generated case matches the model assumption I
    intend to test.
11. As an analyst, I want to define one or more battery assets, so that hybrid
    storage cases can be built from the web app.
12. As an analyst, I want to enter battery charge power, discharge power, energy
    bounds, initial energy, efficiencies, degradation cost, terminal condition,
    and anti-simultaneity settings, so that the editor covers the existing BESS
    formulation.
13. As an analyst, I want to define one or more renewable assets, so that solar
    or wind-like availability profiles can be optimized.
14. As an analyst, I want to label renewable assets as solar or wind for display,
    so that model listings are understandable while Julia still receives
    supported renewable nodes.
15. As an analyst, I want to define one or more local load assets, so that
    behind-the-meter or demand-serving cases can be built.
16. As an analyst, I want all assets generated by the editor to connect to the
    PCC automatically, so that I do not need to edit graph edges manually.
17. As an analyst, I want to delete or disable draft assets before promotion, so
    that model alternatives can be adjusted without starting over.
18. As an analyst, I want the editor to prevent duplicate asset IDs, so that
    generated outputs remain traceable to model inputs.
19. As an analyst, I want solver name to default to HiGHS, so that common cases
    require no solver setup.
20. As an analyst, I want to provide solver options as an advanced JSON object,
    so that specialized runs are possible without building a large solver UI.
21. As an analyst, I want malformed solver options to fail before validation, so
    that a simple typo does not become a Julia process failure.
22. As an analyst, I want to upload a CSV time-series file, so that period data
    can come from spreadsheets or external workflows.
23. As an analyst, I want to upload a basic XLSX time-series file, so that Excel
    users can use the structured editor without manual CSV conversion.
24. As an analyst, I want the app to preview uploaded time-series rows, so that I
    can confirm the file is the one I intended to use.
25. As an analyst, I want XLSX ingestion to use a selected sheet or the first
    sheet by default, so that simple workbooks are supported.
26. As an analyst, I want the app to detect common columns automatically, so
    that mapping is fast for well-named files.
27. As an analyst, I want to manually correct column mappings, so that files with
    project-specific names can still be used.
28. As an analyst, I want to map a timestamp column, so that each optimization
    period has a stable start time.
29. As an analyst, I want to map a duration column, so that variable-duration
    periods remain supported.
30. As an analyst, I want to map a legacy single price column when buy and sell
    prices are equal, so that existing datasets remain easy to use.
31. As an analyst, I want to map separate import and export price columns, so
    that buy and sell economics are modeled correctly.
32. As an analyst, I want to map renewable availability columns by asset ID, so
    that each renewable asset receives the correct profile.
33. As an analyst, I want to map load demand columns by asset ID, so that each
    load asset receives the correct demand profile.
34. As an analyst, I want the app to validate missing mapped values, so that
    incomplete time series fail before promotion.
35. As an analyst, I want the app to validate numeric columns, so that text or
    invalid numbers are caught early.
36. As an analyst, I want the app to validate timestamp ordering and uniqueness,
    so that generated cases match Julia time-series requirements.
37. As an analyst, I want the app to reject nonpositive durations, so that period
    energy accounting is valid.
38. As an analyst, I want the app to reject negative renewable availability and
    load demand, so that invalid physical inputs are caught early.
39. As an analyst, I want the app to reject missing required mappings, so that
    generated JSON is complete before Julia validation.
40. As an analyst, I want the uploaded source file to be retained, so that the
    origin of generated time series is auditable.
41. As an analyst, I want the column mapping to be retained, so that I can
    understand how source columns became `system_case` fields.
42. As an analyst, I want the generated `system_case` preview to be read-only, so
    that the structured editor remains the source for structured drafts.
43. As an analyst, I want the advanced paste/upload JSON path to remain
    available, so that I can still submit hand-authored or externally generated
    cases.
44. As an analyst, I want to explicitly generate and validate a draft before
    creating a version, so that I can review the exact candidate case.
45. As an analyst, I want Julia validation errors to appear on the draft page, so
    that contract-level problems can be corrected before promotion.
46. As an analyst, I want Python file-ingestion errors to appear on the draft
    page, so that mapping and data problems are clear before Julia is called.
47. As an analyst, I want a successful validation to allow promotion to a new
    immutable scenario version, so that the draft becomes executable only after
    it is valid.
48. As an analyst, I want the promoted version to store the exact generated
    `system_case_json`, so that runs remain reproducible.
49. As an analyst, I want promoted versions to retain metadata about the source
    file and mapping, so that input provenance is not lost.
50. As an analyst, I want to launch a manual run from a version created by the
    editor, so that the new input path connects to the existing execution flow.
51. As an analyst, I want result tables to show separate import and export
    prices when present, so that I can inspect buy and sell economics.
52. As an analyst, I want result tables to show import cost and export revenue,
    so that period profit is auditable.
53. As an analyst, I want charts to show separate price series when present, so
    that economic behavior is visually inspectable.
54. As an analyst, I want legacy single-price cases to keep working in results,
    so that old scenario versions and sample cases do not break.
55. As a backend developer, I want a draft persistence API, so that SSR pages and
    future clients use the same draft behavior.
56. As a backend developer, I want a time-series ingestion module with a small
    interface, so that CSV/XLSX parsing, preview, mapping, and validation can be
    tested independently.
57. As a backend developer, I want a system-case generation module with a small
    interface, so that editor state can be converted into a Julia contract
    without spreading JSON construction across route handlers.
58. As a backend developer, I want source files stored under a controlled input
    artifact root, so that file paths are predictable and safe to expose.
59. As a backend developer, I want editor-generated versions to use the same
    validation and version persistence path as paste/upload JSON, so that the
    app has one scenario-version contract.
60. As a backend developer, I want errors to distinguish file parsing, mapping,
    Python validation, Julia validation, and execution failures, so that support
    and debugging are practical.
61. As a Julia maintainer, I want single-price cases to remain valid, so that
    Iteration 2 and Iteration 3 regressions stay green.
62. As a Julia maintainer, I want separate import/export price cases covered in
    model tests, so that the objective cannot silently regress.
63. As a Julia maintainer, I want outputs to expose import cost, export revenue,
    and net value, so that the economic accounting is testable.
64. As a maintainer, I want the final Iteration 4 acceptance suite to prove the
    structured editor flow end to end, so that the iteration closes with a real
    analyst workflow instead of isolated components.

## Implementation Decisions

- Iteration 4 adds a structured editor path. It does not replace the
  paste/upload JSON path from Iteration 3.
- A `ScenarioDraft` is mutable and belongs to a scenario.
- Iteration 4 supports one active draft per scenario.
- Runs continue to reference only immutable `ScenarioVersion` records.
- A draft can be created from scratch or initialized from an existing scenario
  version.
- A draft stores an application-owned structured JSON document rather than fully
  normalized relational tables for every asset, parameter, and time-series row.
- The structured draft document is not the execution contract. The generated
  `system_case_json` is the execution contract after validation and promotion.
- The draft may be incomplete or invalid while being edited.
- Promotion from draft to scenario version requires a generated `system_case`
  candidate and successful Julia validation.
- Promoted scenario versions remain immutable.
- The editor supports the asset types already handled by the one-bus optimizer:
  bus/PCC, grid, battery, renewable, and load.
- The editor may display renewable category metadata such as solar or wind, but
  generated cases continue to use supported renewable nodes.
- Hydropower is intentionally excluded from Iteration 4.
- The editor supports multiple batteries, renewables, loads, and grid
  connections where the existing one-bus contract supports them.
- The editor automatically generates logical edges from every asset to the PCC.
  Manual edge editing is out of scope.
- The editor requires time-series data to come from an uploaded CSV or basic
  XLSX file. Manual row-by-row time-series editing is out of scope.
- The time-series ingestion module supports CSV as the fully covered path.
- The time-series ingestion module supports basic XLSX ingestion with a selected
  sheet or first-sheet default.
- The ingestion module does not support formulas, named ranges, complex
  multi-table sheets, unit conversion, currency conversion, or advanced ETL.
- The ingestion module produces preview rows, column metadata, detected mapping
  suggestions, validation errors, and a normalized mapped time-series payload.
- Column mapping is mixed: simple auto-detection plus analyst confirmation or
  correction.
- The app stores the original uploaded source file in a controlled input-source
  area.
- The app stores the accepted column mapping for auditability.
- Input source files are separate from run artifacts. Run artifacts remain tied
  to an executed run.
- Python validates editor and ingestion concerns before generating the candidate
  `system_case`.
- Julia remains the final authority for the `system_case` contract and model
  validation.
- The generated `system_case` preview is read-only in the structured editor.
- Advanced users can still use the existing paste/upload JSON path when they
  need direct JSON control.
- The solver editor remains minimal: solver name defaults to HiGHS and solver
  options are an advanced JSON object.
- Iteration 4 keeps authentication and roles out of scope and continues using
  the implicit internal analyst identity.
- Iteration 4 keeps scheduled runs out of scope.
- Iteration 4 keeps configurable dashboard templates and publication out of
  scope.
- The Julia system-dispatch contract remains `bess_system_dispatch.v1` because
  separate prices can be introduced backward-compatibly.
- A period may continue to use `price_usd_per_mwh`.
- A period may use `import_price_usd_per_mwh` and
  `export_price_usd_per_mwh`.
- If separate import/export prices are present, they take precedence in the
  objective and output economics.
- If separate prices are not present, the existing `price_usd_per_mwh` is used
  for both import and export.
- Validation rejects ambiguous or incomplete price data, such as only one of the
  two separate price columns being present for a period.
- Julia outputs include separate import and export prices when available.
- Julia outputs expose import cost, export revenue, and net market value in
  addition to period profit.
- Legacy outputs remain compatible enough for existing result readers and
  regression tests.
- Result tables and charts prefer separate price series when available and fall
  back to the legacy single price when not.
- The main deep modules for Iteration 4 are the Julia economic-price extension,
  draft persistence, time-series ingestion and mapping, system-case generation,
  draft validation/promotion, and result economics rendering.
- The SSR UI and JSON API should use the same backend behavior for drafts,
  uploads, mapping, generated-case preview, validation, and promotion.

## Testing Decisions

- Tests should verify externally visible behavior and contracts, not internal
  implementation details.
- Existing Julia regression coverage remains a required guard for every slice
  that changes optimizer code.
- Existing Python web acceptance and persistence coverage remains a required
  guard for every slice that changes the web app.
- Julia tests should cover legacy single-price cases, separate import/export
  price cases, validation errors for incomplete price data, objective behavior,
  and output columns for economic accounting.
- Result writer tests should verify import cost, export revenue, net market
  value, degradation cost, curtailment penalty, and period profit.
- Result reader tests should verify both legacy single-price runs and
  separate-price runs.
- Draft persistence tests should prove one active draft per scenario, draft
  update behavior, draft initialization from a scenario version, and immutable
  scenario-version preservation.
- System-case generation tests should prove that editor state creates a valid
  one-bus graph with generated edges, stable asset IDs, solver config, price
  fields, renewable series, load series, battery settings, and grid settings.
- Time-series ingestion tests should cover CSV parsing, XLSX parsing, preview
  rows, auto-detected mappings, manual mapping overrides, missing required
  mappings, invalid timestamps, duplicate timestamps, nonpositive durations,
  nonnumeric values, negative renewable availability, and negative load demand.
- Source-file audit tests should prove uploaded files are stored under the
  configured input-source root and that unsafe paths are not exposed.
- API tests should cover draft read/update, file upload, preview, mapping,
  generated-case preview, Julia validation, promotion to scenario version, and
  launch of a run from an editor-created version.
- Template smoke tests should cover the scenario draft page, asset forms, source
  upload/mapping page, generated-case preview, validation errors, promotion
  success, and result display with separate prices.
- Acceptance tests should prove the full Iteration 4 flow: create project,
  create scenario, create draft, configure assets, upload CSV or XLSX, map
  columns, generate `system_case`, validate through Julia, promote to immutable
  scenario version, launch a manual run, register artifacts, and review results.
- Regression tests should prove the Iteration 3 paste/upload JSON path still
  creates valid versions and runs.

## Out of Scope

- Customer read-only portal.
- Published dashboards.
- Configurable dashboard templates.
- Daily, weekly, monthly, or cron-like scheduled runs.
- Authentication, authorization, roles, or multi-user administration.
- Full SPA frontend.
- Canvas-based model editing.
- Manual graph edge editing.
- Normalized relational tables for every asset parameter and every time-series
  row.
- Manual row-by-row time-series editing in the browser.
- Hydropower modeling.
- Demand charges, tariff billing engines, PPA contract logic, or other
  mathematical changes beyond separate import/export prices.
- Unit conversion, currency conversion, exchange-rate handling, or other ETL
  transformations.
- Complex Excel workbooks, formulas, named ranges, or multi-table sheet
  detection.
- Multiple physical buses, network flows, line limits, or electrical losses.
- Advanced browser end-to-end automation beyond lightweight smoke coverage.
- Replacing, hiding, or weakening the auditable Julia output files.

## Further Notes

Iteration 4 should be treated as the conversion point from an engineer-operated
JSON wrapper to a usable private analyst modeling app.

The most important product proof is that an analyst can create a real one-bus
hybrid case without writing JSON, while the system still ends at the same
immutable scenario version and auditable run artifacts introduced in Iteration
3.

The most important technical guardrail is compatibility. Existing Iteration 2
and Iteration 3 cases must keep validating, solving, producing outputs, and
rendering results.

Hydropower remains important to the final objective, but it should follow this
iteration. The structured editor and ingestion foundation should make adding a
simple hydropower asset in a later iteration substantially cleaner.
