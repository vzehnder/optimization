# TS7-019: Build The Layered Read Catalog For Verification Accounts

Status: In Review
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter7/spec_ts7_catalogo_global_y_series_especificas.md` (8.1, 8.2, 11.1)

## What to build

Build the layered catalog as the read surface for discovering and comparing
generic entries: a table with server-side filters and cursor pagination, and an
inspector showing contract, provenance, current revision with hash, coverage,
resolution and consumers, plus the bounded preview.

Reading is direct. This surface never mutates anything; exploring the catalog,
inspecting provenance, reviewing consumers and reading history are direct
actions with no protected journey around them.

The surface opens **only for the verification accounts** until the cutover. A
catalog anyone can read but nobody can mutate teaches a model that does not yet
exist and produces false reports, so `ts_next_canonical_read` stays closed to
regular users until TS7-022 flips it. Enabling this UI is explicitly not a
cutover.

Do not copy any of the three prototype variants literally; build the surface the
accepted experience describes.

## Acceptance criteria

- [x] The table shows one row per signal with owner, scope, type, class, unit, coverage and resolution (AC-CAT-01 frontend half).
- [x] Filters and pagination are server-side; the client never loads all points and never pages in memory.
- [x] The inspector shows contract, provenance, current revision with hash, coverage, resolution and consumers without downloading points (AC-DET-01 frontend half).
- [x] A bounded preview renders and an over-limit preview surfaces `TS_PREVIEW_TOO_LARGE` as a readable state, not a silent truncation.
- [x] The surface offers no mutation affordance of any kind.
- [x] Only verification accounts reach the surface; a regular internal user gets the pre-cutover behaviour and an `external` user gets a 404.
- [x] `tsc`, `eslint`, `vitest` and the production build pass.
- [x] A Chrome pass with the real `.env` credentials walks search, filter, inspect and preview with no console warnings or errors.

## Blocked by

- [TS7-006: Read The Global Catalog Signal First](TS7-006-read-the-global-catalog-signal-first.md)
