# TS7-001: Seed The Persistent Classification Catalogs And Compatibility Matrix

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter7/spec_ts7_catalogo_global_y_series_especificas.md` (2.2, 3, 10.4)

## What to build

Move classification out of the Python registry and into the database. Land
`measurement_dimensions`, `measurement_units`, `time_series_data_classes`,
`time_series_semantic_types`, `time_series_binding_roles` and
`time_series_role_compatibilities` on both supported engines, seeded as a
versioned contract.

The seed is an `INSERT ... ON CONFLICT` that accepts only equality of the
immutable contract: if `TIME_SERIES_SIGNAL_CATALOG` diverges from what is
seeded, the deployment blocks instead of drifting silently. The registry stays
in place as a seed and adapter; it stops being the source of truth.

Deliver the single compatibility evaluator on top of that matrix. The rule is
positive: a `semantic_type + binding_role + linkable_object_type` triple is
allowed only if the matrix says so, with exact unit match, and the same
evaluator answers for UI and backend so a rejection cannot be argued around.
Every refusal carries a stable code. `admin` can create a custom semantic type
only with a complete contract; nothing maps an unknown key to a canonical type
automatically, and there is no wildcard category.

The role is decoupled from the semantic type: `time_series_binding_roles` has no
`semantic_type_id` column, because that relationship lives in the matrix (P-01).

## Acceptance criteria

- [ ] The six catalog tables exist on PostgreSQL and SQLite with identical semantics, unique keys and immutability guarantees.
- [ ] Seeding is repeatable: running it twice changes no rows and reports convergence.
- [ ] A divergence between `TIME_SERIES_SIGNAL_CATALOG` and the seeded contract blocks the deployment with a named failure, never a partial seed (AC-CAT-05).
- [ ] One evaluator answers compatibility for both UI and backend, in the documented validation order, and no route can bypass it.
- [ ] Every refusal returns a stable code from chapter 3.6; codes are asserted by test, not by string matching on prose.
- [ ] Unit compatibility is exact match within the dimension, never implicit conversion.
- [ ] `admin` can create a custom semantic type with a complete contract; an incomplete contract is rejected (AC-CAT-06 backend half).
- [ ] An unknown `signal_key`, class or unit never becomes a canonical type on its own (AC-MIG-07 domain half).
- [ ] `time_series_binding_roles` carries no `semantic_type_id`; role-to-type compatibility is expressed only in the matrix (P-01).

## Blocked by

- None - can start immediately.
