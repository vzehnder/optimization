# BESS-CONFIG-008: Land Users In Separate Analyst, Console And Portal Roots

Status: In Review
Type: AFK
Triage: ready-for-agent
Source: `docs/capa_configuracion/architecture_configuration_layer_final.md`

## What to build

Give analyst, console and portal users three sibling application roots with
distinct navigation and headers. Login and current-user refresh return one
backend-calculated landing path, so the browser no longer independently
interprets roles. Operators land directly on their sole visible console or on
the cross-project console list, while portal-only users land in the client
report root.

## Acceptance criteria

- [x] Login and current-user responses return the same backend-calculated `landing_path` for the same user and safe next target.
- [x] Landing precedence is safe next, internal workspace, `operate` with one visible console, `operate` with zero or multiple consoles, then portal.
- [x] `operate` takes precedence over `portal_view` without removing the user's ability to navigate to an authorized portal.
- [x] Analyst, console and portal routes render distinct root layouts and do not share the analyst header.
- [x] The console list is cross-project, stays at its own route and never redirects merely because one row exists.
- [x] Configuring and operating the same console use separate internal and external routes.
- [x] React's scattered client-role checks are replaced by three root guards plus the existing admin-only check.
- [x] An external user cannot enter analyst routes, foreign console routes or internal run routes even when an id is known.
- [x] An internal analyst without admin permission receives 403 from user administration.
- [x] Route, login, refresh, direct-navigation and back/forward tests prove there is no second landing calculation in the frontend.

## Blocked by

- [BESS-CONFIG-002: Cut Over The Portal To External Capabilities And Retire Legacy Client Access](BESS-CONFIG-002-cut-over-the-portal-to-external-capabilities-and-retire-legacy-client-access.md)
- [BESS-CONFIG-006: Create And Activate An Operator Console End To End](BESS-CONFIG-006-create-and-activate-an-operator-console-end-to-end.md)
