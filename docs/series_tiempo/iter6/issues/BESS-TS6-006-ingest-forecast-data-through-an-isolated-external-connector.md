# BESS-TS6-006: Ingest Forecast Data Through An Isolated External Connector

Status: Done
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter6/prd.md`
Fecha de inicio planificada: 2026-07-30
Fecha de termino planificada: 2026-08-03
Fecha de inicio real: 2026-07-11
Fecha de termino real: 2026-07-11

## User stories covered

9, 17

## What to build

Bring external forecast data into the catalog through the same workflow files
use: a connector fetches data from an external API (the concrete first target
comes from the BESS-TS6-000 decision record) and lands it as a time-series
source with connector-origin metadata, producing a validated set in the
project catalog with `forecast` data kind — same semantics as a CSV/XLSX
import, different origin.

The connector does not change the data model: an external API enters as a
source and produces a set, exactly like a file. Connector-specific logic
(endpoint, authentication, payload parsing) lives in an isolated module
behind a narrow interface, so external APIs are replaceable without touching
core series logic. Tests use mocked external data and assert that ingestion
lands through the common source/set creation path.

Re-ingesting from the same connector follows the revision semantics the
catalog already has: unchanged data converges without duplicates, changed
data creates a new revision with hash, date and origin metadata recording the
fetch. Ingested forecast sets are browsable, validatable and bindable in
variants like any other set.

## Acceptance criteria

- [x] A connector ingests external forecast data into the project catalog as a source plus a validated set with `forecast` data kind, without any new data-model concept.
- [x] The source records connector-origin metadata (connector identity, fetch time, target) sufficient to audit where the data came from.
- [x] Connector-specific logic is isolated behind a narrow interface, with core series logic unaware of the external API's shape.
- [x] Re-ingesting unchanged data converges without duplicates; changed data creates a new revision with hash and origin metadata.
- [x] Ingested sets are browsable, pass the existing TS-2 validation gates and are bindable in a case input variant.
- [x] Connector tests run against mocked external data, without network access, and assert common source/set creation.

## Blocked by

BESS-TS6-000
