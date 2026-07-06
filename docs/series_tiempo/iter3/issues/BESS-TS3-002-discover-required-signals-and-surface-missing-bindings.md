# BESS-TS3-002: Discover Required Signals And Surface Missing Bindings

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter3/prd.md`
Fecha de inicio planificada: 2026-07-10
Fecha de termino planificada: 2026-07-13

## User stories covered

9, 19

## What to build

Make variant completeness explicit. The backend derives the list of required
signals for a case from its topology and parameters (which assets exist, which
constraints are active), and each variant reports, per required signal,
whether it is bound and to what. Incomplete variants cannot be validated or
run; the error names each missing required signal.

Required-signal discovery and binding-completeness evaluation live in a deep
module testable without UI. The React variant view lists every required
signal with its bound/missing state so an analyst immediately sees what is
left to bind.

## Acceptance criteria

- [ ] Required signals are derived from the case topology and parameters via a deep module testable without UI.
- [ ] Each variant reports a bound or missing state per required signal, including the bound set/signal when present.
- [ ] Validating or running an incomplete variant fails with one clear error per missing required signal.
- [ ] The React variant view lists required signals with their binding status.
- [ ] Backend tests prove missing-binding errors per required signal and completeness for a fully bound variant.

## Blocked by

BESS-TS3-001
