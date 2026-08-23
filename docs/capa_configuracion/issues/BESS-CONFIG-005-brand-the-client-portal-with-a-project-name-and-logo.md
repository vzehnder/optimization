# BESS-CONFIG-005: Brand The Client Portal With A Project Name And Logo

Status: In Review
Type: AFK
Triage: ready-for-agent
Source: `docs/capa_configuracion/architecture_configuration_layer_final.md`

## What to build

Let an analyst brand a project portal with exactly a public display name and
one logo. The live portal and faithful preview show the current brand, use it
for the document title, and apply explicit fallbacks that never display the
analyst-product mark. The binary remains protected by portal authorization and
is delivered with private revalidation semantics.

## Acceptance criteria

- [x] An analyst can set or clear `display_name` in the portal configuration and upload, replace or remove a single logo.
- [x] Only PNG and JPEG payloads of at most 256 KB are accepted; SVG, other media types and oversized payloads are rejected without changing the prior logo.
- [x] Logo bytes and media type are stored outside the configuration document, and each logo mutation increments the configuration revision.
- [x] The protected logo response carries an ETag derived from the current revision and `private, must-revalidate` caching.
- [x] An external user needs `portal_view` for the project to fetch the logo; guessing another project returns 404.
- [x] The portal payload contains only resolved `display_name` and `logo_url`, never raw binary or project internals.
- [x] Missing `display_name` falls back to the project name; missing logo shows no logo.
- [x] The portal never falls back to the product mark or analyst header, and project description is deliberately absent.
- [x] The document title follows the resolved project display name in portal routes.
- [x] A historical publication reopened later uses current branding while preserving its immutable run results.

## Blocked by

- [BESS-CONFIG-003: Configure One Portal Result End To End](BESS-CONFIG-003-configure-one-portal-result-end-to-end.md)
