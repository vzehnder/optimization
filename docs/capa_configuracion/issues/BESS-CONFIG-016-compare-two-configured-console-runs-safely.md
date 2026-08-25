# BESS-CONFIG-016: Compare Two Configured Console Runs Safely

Status: In Review
Type: AFK
Triage: ready-for-agent
Source: `docs/capa_configuracion/architecture_configuration_layer_final.md`

## What to build

Let an operator select two runs from the same console history and compare their
configured KPIs, charts and tables. The comparison uses the same safe results
builder as individual run detail, preserves public labels from the active
console configuration, and never exposes immutable-version metadata, paths,
logs, hashes or internal identifiers.

## Acceptance criteria

- [x] The console history lets the operator select two accessible runs and open a comparison without leaving the console root.
- [x] Both comparison sides are built through the configured results allowlist used by console run detail.
- [x] Only runs belonging to the requested console and visible to the current user can be compared.
- [x] A guessed, foreign, draft-console or revoked-access run returns 404 to an external user.
- [x] Configured KPI, chart, series, table and column ordering and labels are preserved on both sides.
- [x] Missing configured data is represented safely and does not reveal artifact names or technical errors.
- [x] Run ids used as public history references do not grant access to the internal run-detail route.
- [x] Negative payload tests prove that scenario versions, bindings, revisions, hashes, system cases, paths, logs, exit codes and raw errors never appear.
- [x] React and API tests compare runs with different parameter and series values and prove the visible differences are correct.

## Blocked by

- [BESS-CONFIG-009: Run A Configured Console With Parameter Overrides](BESS-CONFIG-009-run-a-configured-console-with-parameter-overrides.md)
- [BESS-CONFIG-010: Edit One Exposed Series Without Changing Canonical Data](BESS-CONFIG-010-edit-one-exposed-series-without-changing-canonical-data.md)
