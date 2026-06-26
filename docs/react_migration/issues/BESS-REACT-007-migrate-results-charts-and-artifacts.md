# BESS-REACT-007: Migrate Results Charts And Artifacts

Status: Done
Type: AFK
Triage: ready-for-agent
Source: `docs/react_migration/prd_react_ui_migration.md`

## User stories covered

57 through 62

## What to build

Complete the React run review experience for successful executions. An analyst
can inspect summary KPIs, system and asset dispatch tables, available Plotly
charts, and registered artifact downloads through existing backend result
contracts.

The frontend should own chart lifecycle and interaction while the backend
continues to own result parsing, compatibility handling, and safe artifact
registration.

## Acceptance criteria

- [x] A succeeded run displays summary, solver, objective, and available
      economic or physical KPIs.
- [x] System and asset dispatch tables expose returned columns, units, and
      bounded rows clearly.
- [x] Available price, grid, renewable, BESS, hydro, and profit series render in
      Plotly charts.
- [x] Users can manage dense chart legends and inspect values through accessible
      interaction or accompanying summaries.
- [x] Missing legacy columns affect only the unavailable section and do not
      break the result page.
- [x] Empty, loading, parse-error, missing-artifact, and incomplete-run states
      are distinct.
- [x] Chart components update and dispose cleanly across data changes and route
      navigation.
- [x] The run page lists only safe registered artifacts.
- [x] Artifact download responses preserve display name and media type.
- [x] Unsafe, missing, or unknown artifact paths remain inaccessible.
- [x] Direct refresh of a successful run reconstructs all visible results from
      backend contracts.
- [x] Browser acceptance covers modern hydro results, legacy/missing-column
      results, chart interaction, tables, and an artifact download.
- [x] Existing result review, hydro result, artifact, and authorization tests
      remain green.

## Blocked by

- BESS-REACT-006
