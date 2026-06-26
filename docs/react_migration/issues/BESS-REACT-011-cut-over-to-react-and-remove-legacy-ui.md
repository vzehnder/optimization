# BESS-REACT-011: Cut Over To React And Remove Legacy UI

Status: Done
Type: AFK
Triage: ready-for-agent
Source: `docs/react_migration/prd_react_ui_migration.md`

## User stories covered

1 through 80

## What to build

Make React the only supported application UI after every migrated flow has
reached parity. Preserve established bookmarks through route mapping or safe
redirects, remove obsolete server-rendered forms and presentation helpers, and
close the iteration with production-build, security, accessibility, and full
regression proof.

FastAPI remains the API, download, authentication, orchestration, and static
hosting service. This slice removes duplicate presentation behavior; it does not
rewrite domain services or optimizer contracts.

## Acceptance criteria

- [x] All accepted analyst, admin, and client flows enter the React application
      without depending on server-rendered HTML behavior.
- [x] Established login, project, scenario, draft, run, admin, publication,
      client, and validation bookmarks resolve or redirect safely to their React
      equivalents.
- [x] API, generated asset, health, and artifact download URLs retain their
      intended behavior and are never captured by SPA fallback.
- [x] Obsolete server-rendered form endpoints, HTML rendering helpers, embedded
      CSS, and embedded browser scripts are removed.
- [x] Domain services, persistence, Julia execution, result readers,
      authorization, and artifact safety are not duplicated into the frontend.
- [x] The production build starts as one FastAPI-hosted application and passes
      a clean-browser smoke test.
- [x] Cache headers support safe frontend deployment and rollback behavior.
- [x] Automated accessibility checks and keyboard smoke tests pass on
      representative auth, editor, results, admin, and client pages.
- [x] Security acceptance proves authentication, role separation, cross-site
      request forgery defense, project scoping, publication state, revocation,
      artifact allowlists, and safe paths.
- [x] The full React browser acceptance suite passes against an isolated real
      FastAPI application.
- [x] The full Python acceptance suite passes after legacy UI tests are removed
      or rewritten as API/domain tests.
- [x] Julia tests pass if and only if a Julia-facing contract or artifact format
      changed; no such change is expected.
- [x] Operator and developer documentation explains frontend setup, local
      development, type generation, tests, production build, and deployment.
- [x] The final application has one documented UI implementation and no hidden
      legacy fallback.

## Blocked by

- BESS-REACT-000 through BESS-REACT-010

