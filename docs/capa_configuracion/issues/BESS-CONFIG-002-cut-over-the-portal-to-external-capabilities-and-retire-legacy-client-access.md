# BESS-CONFIG-002: Cut Over The Portal To External Capabilities And Retire Legacy Client Access

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: `docs/capa_configuracion/architecture_configuration_layer_final.md`

## What to build

Complete the access-model migration so `external` is the only external-facing
role and every portal request is authorized by `portal_view` on the relevant
project. A migrated client sees the same published material as before, an
operator without `portal_view` cannot enter the portal, and revocation affects
the next request. Retire the legacy client administration and authorization
contract once every caller uses the capability model.

This is the contract half of the access refactor. The finished application no
longer branches on the legacy client role or exposes the old client-access
administration vocabulary.

## Acceptance criteria

- [ ] Every persisted legacy client is migrated to `external` with `portal_view` enabled only for the projects previously assigned.
- [ ] Portal lists, publication details, previews intended for external users, logos and downloads check `portal_view` on every request.
- [ ] `operate` alone grants no portal, project, scenario, run, catalog, publication or download access.
- [ ] Revoking `portal_view` prevents the same authenticated session from using the portal on its next request.
- [ ] An external user receives 404 for an unassigned project or publication, while an internal non-admin receives 403 for admin-only operations.
- [ ] The new external-access administration contract replaces the legacy client-access contract in backend and frontend together.
- [ ] No runtime authorization or React routing branch depends on the legacy client role after the cutover.
- [ ] Existing publications and artifact allowlists remain unchanged by the identity migration.
- [ ] Regression tests prove that migration preserves access exactly and never widens it.

## Blocked by

- [BESS-CONFIG-001: Expand External Project Capabilities Beside Legacy Client Access](BESS-CONFIG-001-expand-external-project-capabilities-beside-legacy-client-access.md)
