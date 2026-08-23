# BESS-CONFIG-001: Expand External Project Capabilities Beside Legacy Client Access

Status: In Review
Type: AFK
Triage: ready-for-agent
Source: `docs/capa_configuracion/architecture_configuration_layer_final.md`

## What to build

Introduce the additive access model needed by the two external surfaces while
keeping the existing client portal fully usable. Administrators can manage
independent portal viewing and console operation capabilities per external user
and project. Existing client assignments are represented without granting any
new access, and both supported database engines can migrate forward without
rewriting publication history.

This is the expand half of an expand-contract change. The legacy client role
and access contract remain temporarily available so the repository stays green
while the new external capability model is proven end to end.

## Acceptance criteria

- [x] The global identity model accepts external users alongside the legacy client role during the transition.
- [x] Project access stores independent `portal_view` and `operate` capabilities, both queryable per user and project.
- [x] Existing client assignments migrate to `portal_view` enabled and `operate` disabled, without expanding access to another project or surface.
- [x] An administrator can list, grant, change and revoke both capabilities from the internal administration UI.
- [x] An analyst cannot administer external capabilities.
- [x] Capability mutations record the acting administrator and take effect for subsequent authorization checks.
- [x] The existing client portal and publication downloads remain behaviorally unchanged throughout this expand step.
- [x] Migration and persistence tests cover both supported database engines and repeated startup is idempotent.

## Blocked by

None - can start immediately.
