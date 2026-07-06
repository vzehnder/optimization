# BESS-TS3-006: Mark Variants Stale On Series, Topology Or Parameter Changes

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter3/prd.md`
Fecha de inicio planificada: 2026-07-22
Fecha de termino planificada: 2026-07-23

## User stories covered

13, 14

## What to build

Keep validated variants honest. When a bound time-series set gains a new
revision (manual edit or file replacement) after a variant was validated, the
variant becomes stale because the recorded hash/revision no longer matches the
current one. Likewise, when the case topology or parameters change, variants
become stale because the required-signal set may have changed.

The stale state is visible wherever the variant appears (dropdown and variant
detail) with the reason (series changed versus topology/parameters changed).
Revalidating refreshes the recorded revisions and hashes and clears the stale
marker; a stale variant cannot launch a run until revalidated (per the
BESS-TS3-000 decision record).

## Acceptance criteria

- [ ] A new revision on a bound set marks every validated variant that binds it as stale.
- [ ] A topology or parameter change on the case marks its variants as stale.
- [ ] The stale state and its reason are visible in the variant dropdown and variant detail.
- [ ] Revalidation refreshes the recorded set revisions and hashes and clears the stale marker.
- [ ] Launching a run from a stale variant is blocked until revalidation, consistent with the accepted decision record.
- [ ] Backend tests prove stale detection for a hash change, a topology change and a parameter change, plus the revalidation path.

## Blocked by

BESS-TS3-003
