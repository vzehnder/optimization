# BESS-CONFIG-007: Drive Console Signal Choices From The Canonical Catalog

Status: In Review
Type: AFK
Triage: ready-for-agent
Source: `docs/capa_configuracion/architecture_configuration_layer_final.md`

## What to build

Make canonical signal metadata the single source of truth for configuring
operator tables. The internal console editor obtains signal keys, units,
entity types and nonnegative rules from an authenticated catalog and uses them
to validate and present column choices. The one-bus required-signal
representation can express more than one signal per entity type without
changing hydraulic behavior.

## Acceptance criteria

- [x] Internal authenticated users can read the canonical signal catalog with signal key, unit, entity type and nonnegative metadata.
- [x] The signal-catalog endpoint passes through the common authenticated application boundary and is unavailable to external surfaces.
- [x] The console configuration editor derives signal options, units and nonnegative presentation from the catalog response.
- [x] The frontend no longer contains a separately maintained canonical signal-to-unit mapping.
- [x] One-bus required-signal discovery accepts an ordered list of signals per entity type and still emits the established `entity_type`, `entity_id` and `signal_key` shape.
- [x] Hydraulic required-signal behavior remains separate and unchanged.
- [x] Adding a declarative vector signal to the catalog and one-bus requirement list makes it selectable without editing the operator table, parser, payload builder or frontend unit mapping.
- [x] External console payloads continue to expose only configuration column ids and labels, never signal keys or entity pointers.
- [x] API, configuration UI, required-signal and regression tests prove the new source of truth.

## Blocked by

- [BESS-CONFIG-006: Create And Activate An Operator Console End To End](BESS-CONFIG-006-create-and-activate-an-operator-console-end-to-end.md)
