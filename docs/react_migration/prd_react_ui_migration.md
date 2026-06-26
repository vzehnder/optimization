# React UI Migration PRD

## Problem Statement

The private optimization application has grown from a minimal analyst flow into
a role-gated product that supports project and scenario management, structured
one-bus model editing, CSV/XLSX time-series ingestion, Julia validation and
execution, result review, dashboard templates, publication workflows, and a
read-only client portal.

The user interface is still generated inside the FastAPI application as Python
HTML strings with embedded CSS and JavaScript. This couples presentation,
routing, form handling, authorization responses, and backend orchestration in a
single module. Repeated UI patterns are difficult to reuse, complex editor state
is difficult to reason about, browser behavior has limited automated coverage,
and each product increment makes the server-rendered layer more expensive to
change safely.

The application already exposes JSON APIs for much of the internal analyst
workflow, but API coverage and response contracts are not yet sufficient for a
complete React client. Authentication is primarily form-based, client portal
data is primarily server-rendered, several responses use inconsistent envelopes,
and the current role boundary intentionally denies clients access to almost all
API routes.

The migration must improve the presentation architecture without destabilizing
the Julia optimizer, the `system_case` contract, persisted application state,
run execution, auditable artifacts, publication permissions, or existing users.
It must also avoid a high-risk all-at-once rewrite: the current UI must remain
usable until each replacement path has proved functional parity.

## Solution

Replace the server-generated user interface with a React and TypeScript single
page application while retaining FastAPI as the application API, authentication
boundary, orchestration layer, and production static-asset host.

The React application will initially coexist with the current UI under a
dedicated application entry point. It will consume versioned, documented JSON
contracts, use the existing HTTP-only server-side session cookie, and implement
role-aware navigation for `admin`, `analyst`, and `client` users. FastAPI will
serve the compiled frontend from the same origin in production; local
development will use a frontend development server that proxies API requests to
FastAPI.

Migration will proceed through narrow end-to-end slices. Each slice will expose
or normalize the required API behavior, implement the corresponding React user
flow, and prove it against the real FastAPI application. The old server-rendered
path will remain available until the replacement slice reaches acceptance. The
final cutover will preserve or redirect established bookmarks, remove obsolete
HTML form endpoints and renderers, and leave one supported UI implementation.

The migration is a presentation and application-contract change, not a rewrite
of domain behavior. PostgreSQL/SQLite persistence, the local run queue, the
Julia CLI boundary, optimization mathematics, result readers, dashboard
filtering, publication state, and artifact formats remain authoritative.

## User Stories

1. As an application user, I want the migrated UI to preserve the workflows I
   use today, so that the technology change does not interrupt my work.
2. As an application user, I want navigation to update without full page
   reloads, so that the application feels responsive.
3. As an application user, I want consistent loading, empty, success, and error
   states, so that I understand what the application is doing.
4. As an application user, I want unexpected UI failures to be contained and
   explained, so that one broken view does not leave the whole application
   blank.
5. As an application user, I want direct links and browser history to work, so
   that I can bookmark and revisit a project, scenario, run, or publication.
6. As an application user, I want the interface to remain usable on common
   desktop and tablet widths, so that the migration does not regress layout.
7. As a keyboard user, I want controls, dialogs, forms, and navigation to be
   operable without a mouse, so that the application remains accessible.
8. As a user of assistive technology, I want labels, errors, statuses, tables,
   and charts to have meaningful accessible text, so that I can understand the
   workflow.
9. As a first-time administrator, I want to bootstrap the first admin account,
   so that a new installation can be initialized securely.
10. As a user, I want to log in with my existing account, so that migration does
    not require new credentials.
11. As a user, I want invalid credentials to produce a clear but non-revealing
    error, so that I can recover without exposing account details.
12. As a deactivated user, I want my session to stop granting access, so that
    deactivation remains immediate.
13. As a signed-in user, I want a page refresh to restore my identity and role,
    so that client-side state does not become the security authority.
14. As a user, I want to log out and lose access to protected data immediately,
    so that shared-device sessions can be ended safely.
15. As an internal user, I want to land in the analyst workspace after login,
    so that I can continue managing optimization work.
16. As a client, I want to land in the read-only client portal after login, so
    that I never enter internal analyst screens.
17. As an unauthenticated user, I want protected UI routes to return me to login
    and restore my safe destination afterward, so that authentication does not
    lose my context.
18. As a user without permission, I want a clear forbidden view, so that access
    denial is distinguishable from missing data.
19. As an analyst, I want to list and create projects, so that optimization work
    remains grouped by business context.
20. As an analyst, I want to open a project and review its description,
    scenarios, dashboard templates, and relevant access context, so that I can
    manage it from one workspace.
21. As an analyst, I want to create scenarios under a project, so that model
    alternatives remain organized.
22. As an analyst, I want to open a scenario and review versions and runs, so
    that I can understand its history.
23. As an analyst, I want empty project and scenario states to explain the next
    action, so that a new workspace is easy to start.
24. As an analyst, I want failed project or scenario operations to preserve my
    input, so that transient errors do not force me to retype data.
25. As an analyst, I want to create or reopen one active structured draft for a
    scenario, so that I can edit a model before creating an immutable version.
26. As an analyst, I want to edit case identity, schema, time-series metadata,
    graph settings, grid settings, and solver settings, so that the generated
    case remains complete.
27. As an analyst, I want to add supported assets, so that I can model BESS,
    load, renewable, and hydro resources at the one-bus system.
28. As an analyst, I want to edit type-specific asset parameters, so that each
    asset preserves its physical and economic behavior.
29. As an analyst, I want to remove an asset intentionally, so that obsolete
    resources do not remain in the draft.
30. As an analyst, I want field-level validation close to the relevant control,
    so that I can correct obvious errors before server validation.
31. As an analyst, I want server validation to remain authoritative, so that a
    browser cannot bypass domain rules.
32. As an analyst, I want unsaved changes to be visible, so that I know whether
    the persisted draft reflects the form.
33. As an analyst, I want navigation away from unsaved changes to require an
    intentional decision, so that edits are not lost accidentally.
34. As an analyst, I want save operations serialized and reconciled with the
    persisted draft, so that slow responses do not overwrite newer local state.
35. As an analyst, I want to upload CSV and XLSX time-series sources, so that I
    can use existing operational data.
36. As an analyst, I want to select an XLSX worksheet when required, so that the
    intended data is ingested.
37. As an analyst, I want to see detected columns and preview rows, so that I can
    verify the uploaded source.
38. As an analyst, I want to review suggested mappings, so that common source
    formats require less manual configuration.
39. As an analyst, I want to correct mappings to timestamps, durations, prices,
    loads, renewable availability, and hydro inflows, so that source columns
    drive the intended assets.
40. As an analyst, I want to edit source rows in a bounded table editor, so that
    small data corrections do not require a separate spreadsheet round trip.
41. As an analyst, I want ingestion and mapping errors associated with their
    source, rows, or columns, so that data quality problems are actionable.
42. As an analyst, I want large tables to remain responsive, so that the browser
    does not become unusable on realistic time series.
43. As an analyst, I want to preview the generated `system_case`, so that I can
    inspect the exact optimizer input before promotion.
44. As an analyst, I want draft generation errors grouped by configuration,
    assets, or source data, so that I can return to the right editor section.
45. As an analyst, I want to validate the generated case through the existing
    Julia validation boundary, so that frontend acceptance matches optimizer
    acceptance.
46. As an analyst, I want validation status and details to remain visible after
    a refresh, so that the draft records its latest validation snapshot.
47. As an analyst, I want promotion blocked after draft changes invalidate the
    validated snapshot, so that an unvalidated case cannot become a version.
48. As an analyst, I want to promote a valid generated case into an immutable
    scenario version, so that it can be executed and audited.
49. As an analyst, I want to create a scenario version by pasting or uploading a
    complete JSON case, so that the expert workflow remains available.
50. As an analyst, I want malformed or invalid JSON to return actionable errors
    without creating a version, so that history contains only valid snapshots.
51. As an analyst, I want to inspect version metadata and the stored input, so
    that I can identify the exact model represented by a version.
52. As an analyst, I want to delete only versions that are eligible for
    deletion, so that run lineage cannot be broken.
53. As an analyst, I want to launch a manual run from a valid scenario version,
    so that the existing Julia execution workflow remains available.
54. As an analyst, I want the run page to show queued, running, succeeded, or
    failed state without manual refresh, so that I can monitor execution.
55. As an analyst, I want polling to stop when a run reaches a terminal state,
    so that the browser and server avoid unnecessary work.
56. As an analyst, I want failed runs to show timestamps, logs, and structured
    errors, so that execution failures can be diagnosed.
57. As an analyst, I want succeeded runs to show summary KPIs, so that I can
    assess the optimization quickly.
58. As an analyst, I want to review system and asset dispatch tables, so that I
    can inspect period-level behavior.
59. As an analyst, I want to review price, grid, renewable, BESS, hydro, and
    profit charts when their data is available, so that I can understand the
    dispatch visually.
60. As an analyst, I want missing legacy columns to degrade individual result
    sections gracefully, so that old successful runs remain reviewable.
61. As an analyst, I want chart legends and visible series to remain manageable,
    so that dense multi-asset results can be explored.
62. As an analyst, I want to list and download safe registered run artifacts, so
    that the audit trail remains accessible.
63. As an analyst, I want to create and update project-scoped dashboard
    templates, so that client result sections can be curated consistently.
64. As an analyst, I want to create a publication draft from a succeeded run, so
    that audited results can be prepared for clients.
65. As an analyst, I want to edit publication title, notes, template, and
    artifact allowlist, so that client presentation is intentional.
66. As an analyst, I want to preview a publication through the same data
    contract used by clients, so that I see what the client will receive.
67. As an analyst, I want to publish and unpublish a publication, so that client
    visibility remains under explicit control.
68. As an admin, I want to list, create, and deactivate users, so that local
    account management retains functional parity.
69. As an admin, I want to assign and remove client access to projects, so that
    clients see only authorized work.
70. As a client, I want to list my assigned projects and their published
    publications, so that I can find results shared with me.
71. As a client, I want to open a publication and review its title, notes,
    provenance, selected KPIs, charts, and bounded tables, so that I can consume
    results without analyst controls.
72. As a client, I want to download only allowlisted artifacts from active
    publications in assigned projects, so that sharing rules remain enforced.
73. As a client, I want unpublication, assignment removal, deactivation, and
    session expiry to revoke access immediately, so that stale UI state cannot
    bypass backend authorization.
74. As a developer, I want frontend types derived from the API contract, so that
    incompatible response changes are detected early.
75. As a developer, I want each migrated flow verified through the served
    application, so that tests cover routing, API integration, cookies, and UI
    behavior together.
76. As a developer, I want focused component tests only where interaction logic
    is complex, so that tests remain behavior-oriented and maintainable.
77. As a developer, I want existing backend acceptance tests to remain green
    during migration, so that domain behavior is not accidentally rewritten.
78. As an operator, I want one production service to serve the API and compiled
    UI, so that deployment remains simple and same-origin.
79. As an operator, I want cacheable fingerprinted frontend assets and a
    non-cacheable application entry document, so that deployments update safely.
80. As an existing user, I want established page URLs to continue working or
    redirect to their React equivalents, so that bookmarks do not break at
    cutover.

## Implementation Decisions

- The target frontend is a React and TypeScript single page application built
  with Vite.
- FastAPI remains the only application backend. It serves JSON APIs, download
  responses, authentication cookies, and the compiled frontend in production.
- Production uses one origin for UI and API. Local frontend development uses a
  proxy rather than introducing a production CORS dependency.
- The React application coexists with the server-rendered UI under a dedicated
  entry point until migration acceptance is complete. Existing pages remain the
  fallback during this period.
- React Router owns client-side application routes. Direct navigation to a
  frontend route returns the application entry document without intercepting
  API, asset, health, or artifact-download routes.
- A query/cache layer owns server state, request cancellation, invalidation,
  retry policy, and run polling. Form state and ephemeral UI state remain local
  rather than being copied into a global store by default.
- Frontend request and response types are generated from FastAPI OpenAPI schemas.
  Public API endpoints define explicit request and response models instead of
  relying on untyped dictionaries for migrated contracts.
- API responses use consistent resource envelopes, list envelopes, validation
  errors, authorization errors, and not-found errors. Error payloads carry a
  stable machine-readable category plus a user-safe message.
- Existing internal APIs are reused where their behavior is complete. New JSON
  contracts are added for bootstrap, login, logout, client project discovery,
  client publication discovery, client publication results, and allowlisted
  client downloads.
- Server-side session cookies remain HTTP-only and authoritative. The UI derives
  identity and role from the current-user API after startup and refresh.
- State-changing same-origin requests receive explicit cross-site request
  forgery protection. Production session cookies use secure transport settings.
- Authorization remains enforced in FastAPI for every resource operation. Route
  guards and hidden React controls improve navigation but are never treated as
  access control.
- Client APIs are explicitly read-only and project/publication scoped. They do
  not reuse unrestricted internal endpoints merely because the UI hides write
  controls.
- The backend remains authoritative for domain validation. Client validation is
  used for immediate feedback and mirrors only stable constraints.
- Draft saves are serialized. A successful save is reconciled with the server
  representation before the UI marks the draft clean. Multi-user collaborative
  editing and merge conflict resolution are not introduced by this migration.
- Time-series tables use bounded rendering or virtualization where necessary.
  Uploads continue using multipart requests and existing safe source storage.
- Plotly remains the chart engine and existing result payload semantics are
  preserved. React components own chart lifecycle, empty states, cleanup, and
  accessible summaries.
- Existing result readers and dashboard-template filtering remain backend
  responsibilities. The frontend does not parse raw artifact files to recreate
  domain result contracts.
- Existing database entities and optimization artifact formats remain unchanged
  unless an API contract requires additive audit metadata. No optimization
  result is rewritten during migration.
- The final cutover redirects or maps established user-facing URLs to React
  routes, removes obsolete server-rendered forms and rendering helpers, and
  keeps API and download URLs stable.
- Frontend assets are fingerprinted and cacheable. The application entry
  document is served with revalidation/no-cache semantics to avoid stale bundles.
- Dependencies are pinned through the frontend lockfile and vulnerability
  review becomes part of normal maintenance.

## Testing Decisions

- The primary acceptance seam is the highest practical seam: a browser drives
  the compiled or development React application while it communicates with a
  real FastAPI test instance and isolated database. This one seam proves routing,
  session cookies, API contracts, uploads, polling, downloads, and visible role
  behavior.
- Each vertical slice adds one focused end-to-end happy path and the material
  authorization or failure paths for that feature. Tests assert external
  behavior, not component structure, hook calls, CSS class names, or internal
  state-management choices.
- Existing FastAPI/API acceptance tests remain the regression authority for
  persistence, validation, execution orchestration, result reading,
  publication, and authorization behavior during coexistence.
- API contract tests cover new authentication and client endpoints, explicit
  response schemas, safe error bodies, role denial, project scoping, publication
  state, artifact allowlists, and immediate revocation.
- Focused component tests are reserved for complex local interactions such as
  unsaved draft state, type-specific asset forms, time-series mapping/table
  editing, run polling termination, and Plotly lifecycle behavior.
- Accessibility checks cover labels, keyboard operation, focus movement after
  navigation and errors, semantic status updates, and automated high-signal
  violations on representative pages.
- Contract generation is checked in continuous integration so that committed
  frontend types cannot drift from the FastAPI OpenAPI document.
- Production-build smoke coverage verifies static asset serving, direct route
  fallback, cache headers, API exclusions, and a clean load without development
  tooling.
- Security-focused acceptance coverage proves unauthenticated denial, internal
  versus client role boundaries, cross-site request forgery rejection,
  unpublish revocation, assignment removal, user deactivation, safe artifact
  paths, and allowlist enforcement.
- Existing prior art includes the iteration acceptance suites for the analyst
  workflow, structured draft editor, time-series ingestion, hydro support,
  authentication, project access, dashboard templates, publications, client
  portal, and authorization hardening.
- The Julia regression suite is required only if a migration slice changes the
  Julia-facing validation/execution contract or artifact formats. The migration
  is expected to avoid those changes.

## Out of Scope

- Changes to the one-bus mathematical model, solver behavior, Julia package, or
  optimization objective.
- New asset types, network modeling, scheduling, forecasting, SCADA, or external
  data connectors.
- Replacing FastAPI, PostgreSQL/SQLite persistence, the run queue, local session
  model, Plotly, or the Julia CLI boundary.
- Native mobile applications, offline operation, or installable progressive web
  application behavior.
- Server-side rendering, search-engine optimization, or public anonymous pages.
- Splitting the frontend and backend into independently operated production
  services.
- A new design system, broad visual rebrand, or unrelated workflow redesign.
- Collaborative real-time draft editing, conflict merging, comments, or presence.
- Client model editing, client run execution, or expanded client permissions.
- Reinterpreting old result artifacts in the browser or changing publication
  audit semantics.
- Deleting the legacy UI before all replacement acceptance paths and bookmark
  behavior are proven.

## Further Notes

The migration should be judged by functional parity, clearer application
contracts, and reduced coupling—not by the number of React components created.
The desired final boundary is:

```text
React UI
-> FastAPI JSON/download contracts
-> persistence, validation, run orchestration, and result services
-> Julia CLI and auditable artifacts
```

The preferred implementation order is foundation and authentication, simple
analyst navigation, complex draft and time-series editing, validation and run
execution, result review and publication, client access, and final cutover.

If schedule pressure appears, coexistence should last longer rather than
weakening authorization, validation, artifact safety, or acceptance coverage.
Visual refinements can follow functional parity; security and audit behavior
cannot.
