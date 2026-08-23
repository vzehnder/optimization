# BESS-CONFIG-009: Run A Configured Console With Parameter Overrides

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: `docs/capa_configuracion/architecture_configuration_layer_final.md`

## What to build

Complete the first operator execution path without series editing. An operator
opens a configured console, changes one exposed scalar parameter within its
declared range, runs the console through the existing materialization and Julia
pipeline, and sees safe status, history and configured results. The override
belongs only to the console and the immutable run captures the effective value
and real actor.

## Acceptance criteria

- [ ] The console payload exposes only configured parameter ids, labels, units, ranges, defaults and effective values.
- [ ] An operator can replace parameter overrides by external configuration id; arbitrary asset ids and fields are rejected at the boundary.
- [ ] Values outside configured ranges or pointing to unavailable scalar fields block before a version or run is created.
- [ ] Saving an override never edits the analyst draft or changes the base parameters provenance hash.
- [ ] Materialization applies overrides after base provenance and freezes the effective values in a new immutable scenario version.
- [ ] The run records the real authenticated actor, operator-console origin, console configuration revision and exact materialized lineage.
- [ ] Execution reuses the common queue, Julia runner, result indexer and immutable run history.
- [ ] The operator UI covers parameter editing, run gating, enqueue, polling, reduced history and configured result rendering.
- [ ] Pre-engine failures are translated to actionable causes; Julia failures expose a generic message and reference but no stdout, stderr, exit code, paths or raw error message.
- [ ] The console result payload uses the shared results grammar and passes the same negative boundary test as the portal.
- [ ] Revoking `operate` blocks subsequent reads and mutations without cancelling an already-started run.

## Blocked by

- [BESS-CONFIG-004: Cut Over All Portal Results To Safe Shared Payloads](BESS-CONFIG-004-cut-over-all-portal-results-to-safe-shared-payloads.md)
- [BESS-CONFIG-006: Create And Activate An Operator Console End To End](BESS-CONFIG-006-create-and-activate-an-operator-console-end-to-end.md)
