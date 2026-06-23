# BESS-REACT-000: Establish React Application Foundation

Status: Done
Type: AFK
Triage: ready-for-agent
Source: `docs/react_migration/prd_react_ui_migration.md`

## User stories covered

1 through 8, 74 through 79

## What to build

Create the production-capable React and TypeScript application boundary while
leaving the existing UI available. A user should be able to open a dedicated
React entry point, load the current application identity, navigate within the
shell, and refresh a client-side route successfully through FastAPI.

The slice should establish typed API consumption, shared request/error handling,
query and routing infrastructure, development proxying, production static-asset
serving, and the browser acceptance harness used by later slices.

## Acceptance criteria

- [x] A React and TypeScript application builds reproducibly from a committed
      lockfile.
- [x] FastAPI serves the compiled application under a dedicated coexistence
      entry point without changing existing UI routes.
- [x] Direct navigation and refresh on a React-owned route return the
      application entry document.
- [x] SPA fallback does not intercept API, generated asset, health, or artifact
      download routes.
- [x] The development server proxies same-origin-style API requests to FastAPI.
- [x] The shell loads current-user state from the backend and renders a stable
      loading, authenticated, unauthenticated, or error state.
- [x] A shared API client handles JSON success, structured errors, request
      cancellation, and non-JSON download responses appropriately.
- [x] Frontend API types are generated from FastAPI OpenAPI schemas.
- [x] An automated check fails when committed generated types drift from the
      backend contract.
- [x] Fingerprinted assets are cacheable and the application entry document is
      revalidated to avoid stale deployments.
- [x] One browser smoke test proves that the React shell is served by FastAPI,
      can call the API, navigate, and survive a direct refresh.
- [x] Existing Python acceptance tests remain green.

## Blocked by

None - can start immediately
