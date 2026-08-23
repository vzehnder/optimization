# BESS-CONFIG-006: Create And Activate An Operator Console End To End

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: `docs/capa_configuracion/architecture_configuration_layer_final.md`

## What to build

Deliver the first operator-console tracer bullet. An analyst creates a console
from an existing case and variant, edits its fixed configuration in the
scenario workspace, activates it, and opens the same console through the
external shell for testing. An authorized external operator can list and open
the active console, while draft, foreign and inaccessible consoles remain
undiscoverable.

The console owns a stable identity and an exclusive cloned variant.
Configuration edits change the existing console in place and never expose the
internal variant to the operator.

## Acceptance criteria

- [ ] An analyst can create a draft console for a case by choosing a source variant and providing a structurally valid operator-console configuration.
- [ ] Creation clones a variant exclusively owned by the console and records creator, preparer, timestamps, status and revision.
- [ ] The scenario workspace lists its consoles and lets an internal user read, edit, activate, deactivate and test them.
- [ ] Configuration saves use expected revision control, increment revision and preserve the console identity and owned variant.
- [ ] Unknown schema versions, malformed documents, duplicate ids and invalid enum values are rejected without partial persistence.
- [ ] Structural validation does not pretend to resolve current pointers, signals, sources or ranges; semantic problems appear as a fail-closed console state.
- [ ] An external user with `operate` can list consoles across assigned projects and open an active console shell with public identity and prepared-by information.
- [ ] A draft console, a console outside the user's capabilities and a guessed console id return 404 to an external user.
- [ ] Admin and analyst test using their real identity with a visible return-to-workspace affordance, never impersonation.
- [ ] No consoles are created automatically during migration.

## Blocked by

- [BESS-CONFIG-002: Cut Over The Portal To External Capabilities And Retire Legacy Client Access](BESS-CONFIG-002-cut-over-the-portal-to-external-capabilities-and-retire-legacy-client-access.md)
