# BESS-CONFIG-014: Fail Closed And Request Engineer Review After External Changes

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: `docs/capa_configuracion/architecture_configuration_layer_final.md`

## What to build

Enforce the boundary between safe operator edits and engineering changes. A
save through the console attests only the operational copies it changed, so it
remains runnable without a separate revalidation. A later analyst topology or
parameter change, or a configured pointer that no longer exists, blocks the
console before version or run creation. The operator receives a translated
reason and can request review from the preparer.

## Acceptance criteria

- [ ] Console save, undo and restore refresh only the time-series dependencies for the operational copies changed in that transaction.
- [ ] Topology and base-parameter dependency hashes are never refreshed by an operator mutation.
- [ ] An accepted operator save can run immediately when no unrelated dependency changed.
- [ ] A later analyst topology or parameter change produces `dependencia_movida` and prevents scenario-version and run creation.
- [ ] A configured scalar pointer or exposed source that no longer resolves produces `campo_no_disponible` and prevents execution.
- [ ] The external run gate contains only the accepted public reasons, an actionable Spanish message and the console preparer's public name.
- [ ] Raw staleness reasons remain available internally and never cross the console payload.
- [ ] Requesting review on a genuinely blocked console sets `waiting_since`; it creates no inbox item, email, push, expiry or automatic escalation.
- [ ] Saving an analyst case change returns the active consoles it affected as a synchronous non-blocking warning.
- [ ] Operational copies remain flat and do not inherit active validation dependencies from their origin recipe.
- [ ] Tests prove that saving another series cannot falsely clear an unrelated dependency or broken field.

## Blocked by

- [BESS-CONFIG-009: Run A Configured Console With Parameter Overrides](BESS-CONFIG-009-run-a-configured-console-with-parameter-overrides.md)
- [BESS-CONFIG-010: Edit One Exposed Series Without Changing Canonical Data](BESS-CONFIG-010-edit-one-exposed-series-without-changing-canonical-data.md)
