# BESS-CONFIG-004: Cut Over All Portal Results To Safe Shared Payloads

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: `docs/capa_configuracion/architecture_configuration_layer_final.md`

## What to build

Complete the configured portal by supporting the full fixed report order:
publication context, KPIs, charts, tables and approved downloads. Migrate each
project from its most recent usable dashboard template, switch both preview and
live portal to one allowlisted payload builder, and stop reading dashboard
templates for presentation. An analyst can configure the content and
vocabulary inside the fixed shell, and a client sees only those declared
results.

The shared results block established here is also the contract later consumed
by operator-console results.

## Acceptance criteria

- [ ] Portal configurations support ordered KPI, chart, table and download sections using only fixed backend catalogs.
- [ ] Existing dashboard-template flags and table limits migrate to explicit portal configuration entries without enabling content that was previously hidden.
- [ ] A project with publications but no usable template receives a safe explicit configuration with no result panels enabled by fallback.
- [ ] Dashboard templates remain as legacy data but are no longer read to construct preview or live presentation.
- [ ] Preview and live portal use the same result builder and differ only where context-specific URLs require it.
- [ ] Only configured KPIs, chart series, tables and columns appear; unknown keys, `all_series` and `plot_series` never pass through.
- [ ] Downloads remain the intersection of portal configuration and the publication artifact allowlist.
- [ ] The portal renders the fixed macro order with configured labels, empty states and unavailable-result language that exposes no artifact details.
- [ ] Negative boundary tests inject sensitive database fields, unknown summary keys and server artifact paths and prove none appear in portal, preview or serialized results.
- [ ] Existing publication identity, comments, dates, status, run selection and downloadable artifacts remain intact.

## Blocked by

- [BESS-CONFIG-003: Configure One Portal Result End To End](BESS-CONFIG-003-configure-one-portal-result-end-to-end.md)
