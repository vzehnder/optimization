# Client Publication And Read-Only Portal PRD

## Problem Statement

Iteration 5 completed the main analyst-side modeling objective for a one-bus
hybrid optimization application. An analyst can create structured drafts,
configure PCC/grid, BESS, renewable, load, and simple reservoir hydropower
assets, load CSV/XLSX time series, generate and validate `system_case` inputs,
promote immutable scenario versions, launch manual runs, preserve auditable
artifacts, and review result tables and charts.

The product is still not ready for a client-facing workflow. All results remain
inside the analyst application. There is no authentication boundary, no client
role, no project access assignment, no controlled publication layer, no
dashboard template selected by the analyst, and no read-only portal where a
client can inspect only approved results.

Without this layer, sharing results would require manually sending files or
granting access to the internal analyst workflow. That weakens the audit trail
and exposes controls that clients must not have in the first product version,
such as editing drafts, uploading inputs, validating cases, launching runs, or
viewing internal execution logs.

Iteration 6 must turn the existing analyst result review into a controlled
publication workflow:

```text
Admin creates client user
-> Admin assigns client to project
-> Analyst selects a succeeded run
-> Analyst configures a minimal dashboard template
-> Analyst previews the client view
-> Analyst publishes the run
-> Client logs in
-> Client sees assigned projects and published results only
-> Client views dashboard and allowed downloads
```

The iteration should not add new mathematical behavior. Julia remains stable and
the web application adds a product boundary above already completed runs and
artifacts.

## Solution

Build a private authentication and publication layer around the existing FastAPI
analyst application.

The application will support three roles:

- `admin`: manages users and project access assignments.
- `analyst`: creates models, runs optimizations, defines dashboard templates,
  previews publications, and publishes selected results.
- `client`: enters a separate read-only portal and sees only explicitly assigned
  projects and active publications.

The first authentication flow is intentionally simple: local users, hashed
passwords, login/logout, server-side sessions, and a bootstrap path for the
first internal admin. There is no public self-signup, no OAuth, no Supabase Auth,
and no password recovery flow in this iteration.

Publication is represented as its own application entity above an immutable run.
A publication references a succeeded run and records the public title, analyst
notes, selected dashboard template, enabled downloadable artifacts, status, and
audit metadata. Runs remain internal execution records. Publications are the
only objects that make run results visible in the client portal.

Dashboard templates are minimal and product-focused. They reuse the existing
result readers and chart payloads from Iterations 3 through 5, but allow the
analyst to select which standard sections are visible to the client. Iteration 6
does not introduce a chart builder, drag-and-drop editor, arbitrary formulas, or
custom data transformations.

The client portal is a separate read-only SSR experience. It lists assigned
projects, active publications for those projects, a curated dashboard view, run
metadata, summary KPIs, selected charts, limited table previews, analyst notes,
and only the downloads explicitly enabled by the analyst.

Revocation is immediate. If a publication is unpublished or a client loses
project access, client routes and downloads stop returning the publication.
Analysts keep the internal audit trail and can still inspect the underlying run.

## User Stories

1. As an admin, I want to log in with a local account, so that the private app is
   not open to unauthenticated users.
2. As an analyst, I want to log in with a local account, so that internal
   modeling pages are protected.
3. As a client, I want to log in with a local account, so that I can access only
   my assigned read-only portal.
4. As any logged-in user, I want to log out, so that I can end the session from
   a shared or controlled machine.
5. As an admin, I want the app to bootstrap the first internal admin, so that a
   private deployment can be initialized without public registration.
6. As a maintainer, I want passwords stored as hashes, so that plaintext
   passwords are never persisted.
7. As a maintainer, I want sessions to identify the current user and role, so
   that routes can enforce authorization consistently.
8. As a maintainer, I want unauthenticated requests to internal pages to redirect
   to login or return unauthorized responses, so that protected routes are not
   accidentally exposed.
9. As a maintainer, I want authenticated users to land in the right area for
   their role, so that internal users and clients do not share the same primary
   navigation.
10. As an admin, I want to create client users, so that clients can access the
    read-only portal without self-signup.
11. As an admin, I want to create analyst users when needed, so that internal
    access can be managed without editing the database by hand.
12. As an admin, I want to create admin users when needed, so that more than one
    internal operator can manage access.
13. As an admin, I want to see a list of users and roles, so that account state
    is visible.
14. As an admin, I want to deactivate users, so that access can be revoked
    without deleting audit history.
15. As an admin, I want active/deactivated users to be clearly distinguished, so
    that access state is not ambiguous.
16. As an admin, I want to assign a client to a project, so that the client can
    see only that project's published results.
17. As an admin, I want to remove a client from a project, so that access can be
    revoked immediately.
18. As an admin, I want a client to be assigned to multiple projects, so that one
    client account can cover a portfolio.
19. As an admin, I want a project to be assigned to multiple clients, so that
    several client users can review the same project.
20. As an analyst, I want client assignments to avoid exposing draft or run
    controls, so that project access does not become analyst access.
21. As a client, I want to see only explicitly assigned projects, so that other
    client work remains private.
22. As a client, I want project access removal to take effect immediately, so
    that revoked projects disappear from my portal.
23. As an analyst, I want to create a dashboard template for a project, so that
    repeated publications can use a consistent client-facing layout.
24. As an analyst, I want to name a dashboard template, so that I can recognize
    it during publication.
25. As an analyst, I want to choose whether price charts are visible, so that
    client dashboards can show or hide economic inputs.
26. As an analyst, I want to choose whether grid import/export charts are
    visible, so that client dashboards can show external system interaction.
27. As an analyst, I want to choose whether renewable used/curtailed charts are
    visible, so that client dashboards can show renewable behavior.
28. As an analyst, I want to choose whether BESS charge/discharge/SOC charts are
    visible, so that client dashboards can show storage behavior.
29. As an analyst, I want to choose whether hydro charts are visible, so that
    hydro projects can expose power, flow, storage, and reservoir level.
30. As an analyst, I want to choose whether period profit charts are visible, so
    that client dashboards can include economic shape when appropriate.
31. As an analyst, I want to choose whether system dispatch table previews are
    visible, so that clients can inspect period-level values without opening a
    CSV.
32. As an analyst, I want to choose whether asset dispatch table previews are
    visible, so that clients can inspect asset-level values without opening a
    CSV.
33. As an analyst, I want dashboard templates to degrade gracefully when a run
    lacks a selected chart's source columns, so that a single template can be
    reused across related runs.
34. As an analyst, I want legacy runs without hydro columns to still render
    cleanly, so that old results can be published.
35. As an analyst, I want legacy single-price runs to still render cleanly, so
    that Iteration 3/4 outputs can be published.
36. As an analyst, I want a dashboard template to be editable, so that I can
    improve the client view without changing underlying run artifacts.
37. As an analyst, I want dashboard templates to remain separate from immutable
    scenario versions, so that display decisions do not alter optimization
    inputs.
38. As an analyst, I want to create a publication from a succeeded run, so that a
    selected result can become client-visible.
39. As an analyst, I want only succeeded runs to be publishable, so that failed
    or incomplete runs stay internal.
40. As an analyst, I want to give a publication a public title, so that clients
    see a clear result name.
41. As an analyst, I want to add notes or assumptions to a publication, so that
    clients understand what they are reviewing.
42. As an analyst, I want a publication to reference the exact project,
    scenario, scenario version, and run, so that the published result is
    traceable.
43. As an analyst, I want a publication to use a selected dashboard template, so
    that the client view is curated rather than raw.
44. As an analyst, I want to select allowed downloads per publication, so that
    clients receive only approved artifacts.
45. As an analyst, I want `summary.json`, `dispatch.csv`, and
    `asset_dispatch.csv` to be the default client-download candidates, so that
    useful business artifacts are easy to expose.
46. As an analyst, I want internal artifacts such as input snapshots, model
    metadata, stdout logs, stderr logs, and resolved system cases disabled by
    default, so that technical details are not exposed accidentally.
47. As an analyst, I want to explicitly enable internal artifacts when needed,
    so that audit-heavy client engagements can receive more detail.
48. As an analyst, I want to preview a publication as a client before publishing,
    so that I can confirm exactly what will be visible.
49. As an analyst, I want the preview to respect selected dashboard sections and
    download permissions, so that preview and live client view do not diverge.
50. As an analyst, I want creating a publication to start as unpublished, so that
    draft publication setup is not immediately visible.
51. As an analyst, I want to publish an unpublished publication, so that it
    becomes visible to assigned clients.
52. As an analyst, I want to unpublish a publication, so that access can be
    revoked immediately without deleting history.
53. As an analyst, I want to edit a publication's title, notes, template, and
    allowed downloads, so that the client view can be adjusted after creation.
54. As an analyst, I want publication audit fields such as `created_at`,
    `updated_at`, `published_at`, `unpublished_at`, `created_by`,
    `updated_by`, and `published_by`, so that result exposure is traceable.
55. As an analyst, I want unpublished publications to remain visible internally,
    so that I can review and republish them later.
56. As an analyst, I want the publication entity to be separate from the run, so
    that internal run history is not altered by client exposure.
57. As a client, I want a read-only project list, so that I can find assigned
    projects.
58. As a client, I want a read-only project detail page, so that I can see active
    publications for a project.
59. As a client, I want to open a publication, so that I can review the results
    selected by the analyst.
60. As a client, I want to see the public title and analyst notes, so that I
    understand the context of the result.
61. As a client, I want to see publication date, scenario version, run date, and
    run status, so that I understand the provenance of the result.
62. As a client, I want to see summary KPIs from the published run, so that I can
    review high-level outcomes quickly.
63. As a client, I want to see selected charts, so that I can inspect the shape
    of dispatch and economics.
64. As a client, I want table previews to be limited and readable, so that the
    portal remains focused rather than becoming an internal analysis tool.
65. As a client, I want to download only enabled artifacts, so that I receive
    approved supporting files.
66. As a client, I want disabled artifacts to be inaccessible even if I guess the
    URL, so that publication permissions are enforced on the backend.
67. As a client, I want unpublished publications to disappear immediately, so
    that I do not keep access after revocation.
68. As a client, I want unassigned projects to be inaccessible even if I guess
    the URL, so that other work remains private.
69. As a client, I do not want to see draft, validation, upload, promotion, run
    launch, or internal artifact controls, so that the portal is clearly
    read-only.
70. As an analyst, I want client portal pages to reuse existing result readers,
    so that published dashboards stay consistent with internal results.
71. As a backend developer, I want authorization checks centralized, so that new
    routes do not accidentally bypass role or project-access rules.
72. As a backend developer, I want publication result rendering to filter
    charts, tables, and downloads by publication settings, so that UI choices
    are enforced by server behavior.
73. As a backend developer, I want publication download routes to validate both
    project assignment and artifact allowlist membership, so that downloads are
    safe.
74. As a backend developer, I want API and SSR pages to use the same publication
    and authorization services, so that tests cover the behavior users see.
75. As a maintainer, I want Iteration 3, 4, and 5 analyst flows to continue
    working for internal users, so that auth and publication do not regress the
    existing app.
76. As a maintainer, I want paste/upload JSON, structured drafts, manual runs,
    artifact registration, and result pages to remain internal analyst features,
    so that client access does not leak into modeling.
77. As a maintainer, I want the final acceptance suite to prove the complete
    publication path, so that Iteration 6 closes with a client-visible product
    workflow.

## Implementation Decisions

- Iteration 6 is a web application and product-boundary iteration. It should not
  change the Julia optimization formulation.
- The supported roles are `admin`, `analyst`, and `client`.
- `admin` and `analyst` are internal roles. `client` is a read-only external
  role.
- `admin` can manage users and project access assignments.
- `analyst` can use the existing analyst workflow and manage dashboard templates
  and publications.
- The first implementation may allow `admin` to do analyst work as well, but the
  role contract should distinguish `admin` from `analyst`.
- The app uses local users, hashed passwords, login/logout, and server-side
  sessions.
- There is no public registration or client self-signup.
- The first internal admin is created through a bootstrap path using controlled
  configuration or a development helper.
- User records should preserve role, active/deactivated state, display name or
  email-like identifier, password hash, and audit timestamps.
- Deactivated users cannot log in, but their audit history remains preserved.
- Client project access is an explicit many-to-many assignment between client
  users and projects.
- A client sees only assigned projects.
- Removing a project assignment immediately removes portal access to that
  project and its publications.
- Internal analyst routes must require an internal role.
- Client portal routes must require the client role and project assignment.
- Authorization checks should live behind a small reusable service or dependency
  boundary rather than being scattered as ad hoc route logic.
- Dashboard templates belong to a project.
- Dashboard templates are display configuration, not optimization input.
- Dashboard templates define a name and booleans or a simple configuration for
  standard visible sections: summary, price chart, grid chart, renewable chart,
  BESS chart, hydro chart, profit chart, system dispatch table preview, asset
  dispatch table preview, and allowed table preview limits.
- Dashboard templates reuse existing result readers and chart data from earlier
  iterations.
- Dashboard templates should tolerate missing columns and hide unavailable
  sections instead of failing a client page.
- Iteration 6 does not include drag-and-drop layout, arbitrary chart creation,
  formulas, filters, or dashboard publishing independent of a run publication.
- A publication is a separate entity that references a succeeded run.
- A run itself is not marked public. Only active publications expose client
  views.
- A publication must reference its project, scenario, scenario version, run,
  selected dashboard template, public title, analyst notes, allowed downloadable
  artifacts, status, and audit metadata.
- Publication statuses are `draft`, `published`, and `unpublished`.
- Only succeeded runs can be published.
- Publications can be edited, published, unpublished, and republished.
- Iteration 6 does not maintain a complete immutable history of every
  publication display edit. Audit timestamps and user references are sufficient.
- Publication preview is available to internal users before publishing.
- Preview should render through the same publication result renderer used by the
  live client portal.
- A publication can enable downloads from registered run artifacts.
- Default client-download candidates are `summary_json`, `dispatch_csv`, and
  `asset_dispatch_csv`.
- Technical artifacts such as input snapshots, stdout logs, stderr logs, model
  metadata, and resolved system cases are disabled by default.
- Download routes must enforce both publication status and allowed artifact
  membership.
- The client portal uses protected internal URLs under a client area, not public
  signed links.
- The client portal has separate navigation and layout from the analyst app.
- Client portal pages are read-only and must not render analyst controls.
- Client tables should be limited previews by default. Full CSV review remains
  available through enabled downloads.
- Revocation is immediate: unpublishing a publication or removing project access
  stops page and download access.
- Scheduled runs remain out of scope and are a strong candidate for a later
  iteration.
- Deployment hardening and Docker are out of scope except for small
  configuration adjustments needed by the local auth/publication flow.
- Existing `DATABASE_URL`, `ARTIFACT_ROOT`, and `INPUT_SOURCE_ROOT` behavior
  should continue working.
- The main deep modules for Iteration 6 are authentication/session management,
  user management, project access assignments, authorization guards, dashboard
  template management, publication management, publication result rendering, and
  client portal rendering.

## Testing Decisions

- Tests should verify external behavior and contracts rather than implementation
  details.
- Authentication tests should cover login success, login failure, logout,
  deactivated-user rejection, role-aware redirects, and unauthenticated access
  behavior.
- Password tests should prove passwords are hashed and plaintext is not
  persisted.
- Bootstrap tests should prove the first admin can be created in a controlled
  local/test setup without public self-signup.
- User-management tests should prove admin-created users, roles, deactivation,
  and user listings.
- Project-access tests should prove many-to-many client/project assignments,
  removal, and client-visible project filtering.
- Authorization tests should prove clients cannot access analyst routes,
  internal APIs, draft editing, source uploads, validation, promotion, manual run
  launch, or unallowed artifact downloads.
- Dashboard-template tests should prove template creation, updates, selected
  section behavior, missing-column fallback behavior, and project scoping.
- Publication tests should prove only succeeded runs can be published,
  publication draft/published/unpublished state transitions, title/notes edits,
  allowed artifact selection, preview rendering, and revocation behavior.
- Client portal tests should prove assigned project listing, published
  publication listing, publication detail rendering, summary KPI rendering,
  selected chart rendering, limited table preview rendering, and allowed
  downloads.
- Negative client portal tests should prove unassigned projects, unpublished
  publications, failed-run publications, and disabled artifacts are inaccessible.
- Regression tests should prove existing analyst flows still work for internal
  users: paste/upload JSON, structured drafts, source mapping, generated
  validation, promotion, manual runs, artifacts, result pages, and hydro result
  rendering.
- Existing Python web tests from Iterations 3 through 5 are the main regression
  guard for web behavior.
- The Julia regression suite is required only if Iteration 6 changes optimizer
  contracts, result artifact formats, or Julia-facing behavior. The intended
  scope should avoid those changes.
- Manual tests should verify analyst and client navigation, permission
  boundaries, publication preview, client dashboard readability, artifact
  download behavior, immediate revocation, and responsive layout.

## Out of Scope

- Daily, weekly, monthly, or cron-like scheduled runs.
- External queue infrastructure, Celery, Redis, or multi-worker execution.
- New optimization formulation behavior.
- New Julia `system_case` schema versions.
- New asset physics or tariff models.
- Customer editing of models, drafts, time series, dashboard templates, or runs.
- Public links, signed links, expiring tokens, or unauthenticated sharing.
- Public self-signup.
- OAuth, SSO, Supabase Auth, RLS, or identity-provider integration.
- Password recovery, email invitations, or email notifications.
- Granular per-artifact permissions beyond the publication allowlist.
- Full dashboard builder, drag-and-drop layout, custom chart formulas, custom SQL
  queries, or user-defined transformations.
- Collaborative comments or review workflows.
- Full immutable publication revision history.
- Dockerization and production deployment hardening.
- HTTPS, secret rotation, backups, monitoring, and operations runbooks.
- Multi-tenant isolation beyond role and project assignment checks.
- Advanced browser E2E automation beyond lightweight smoke/manual coverage.

## Further Notes

Iteration 6 should be treated as the product transition from an internal analyst
tool to a controlled client-facing application. The most important acceptance
proof is not a new model capability; it is permissioned publication of already
audited optimization results.

The publication layer should preserve the prior architecture principle: runs and
artifacts remain reproducible and auditable, while the web application adds
curation, access control, and client-safe presentation above them.

The central acceptance flow is:

```text
Admin creates client
-> Admin assigns client to project
-> Analyst creates dashboard template
-> Analyst creates publication from succeeded run
-> Analyst previews client view
-> Analyst publishes
-> Client logs in
-> Client sees assigned project
-> Client opens publication
-> Client sees selected summary, charts, table previews, and notes
-> Client downloads only allowlisted artifacts
-> Client cannot access analyst routes or unallowed artifacts
-> Analyst unpublishes or removes access
-> Client access is revoked immediately
```

If the implementation pressure becomes high, the first thing to simplify should
be dashboard customization, not authorization. A fixed but publication-backed
dashboard is less risky than a weak permission boundary.
