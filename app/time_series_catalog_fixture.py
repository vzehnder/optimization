"""Performance fixture for the catalog projection (TS7-005, chapter 9.2).

The fixture is built by the production writers - the canonical revision
protocol and the projection it maintains - so a measurement taken on it is a
measurement of the real path, not of a hand-loaded table.

``fixture_plan(1.0)`` is the reference size chapter 9.2 documents: 100.000
catalog entries, 1.000.000 associations, 1.000.000 bindings and 100.000.000
cells. Smaller scales keep every proportion, so the same script proves the
query shapes locally and measures the budgets on a dedicated performance
database.
"""

from __future__ import annotations

import time


REFERENCE_SETS = 2_000
SIGNALS_PER_SET = 50
PERIODS_PER_REVISION = 1_000
ASSOCIATIONS_PER_ENTRY = 10
BINDINGS_PER_ENTRY = 10
OBJECTS_PER_SIGNAL = ASSOCIATIONS_PER_ENTRY
ENTRIES_PER_VARIANT = 100
# Enough hydro components that a 200 row batch fits inside one target project
# even at the smallest scale this script is normally run at.
BATCH_MEASUREMENT_OBJECTS = 8

SEMANTIC_CONTRACTS = (
    ("energy_price", "usd_per_mwh", "mean"),
    ("hydro_inflow", "m3_per_s", "mean"),
    ("load_demand", "mw", "mean"),
)


def fixture_plan(scale: float = 1.0, *, periods: int | None = None) -> dict[str, object]:
    """Sizes of the fixture at one scale, keeping the documented proportions.

    ``periods`` shortens the coverage of every revision without touching the
    number of entries, associations or bindings. It is how a machine that
    cannot hold 100.000.000 cells still measures the page and list plans over a
    projection of the documented size - the plans are the evidence that no list
    reads a cell in the first place.
    """

    if scale <= 0:
        raise ValueError("scale must be positive")
    coverage = PERIODS_PER_REVISION if periods is None else int(periods)
    if coverage < 1:
        raise ValueError("a revision covers at least one period")
    sets = max(1, round(REFERENCE_SETS * scale))
    entries = sets * SIGNALS_PER_SET
    variants = max(1, entries // ENTRIES_PER_VARIANT)
    objects = OBJECTS_PER_SIGNAL
    active_bindings = variants * objects
    binding_history_depth = max(1, (entries * BINDINGS_PER_ENTRY) // active_bindings)
    return {
        "scale": scale,
        "sets": sets,
        "signals_per_set": SIGNALS_PER_SET,
        "entries": entries,
        "periods": coverage,
        "cells": entries * coverage,
        "objects": objects,
        "associations": entries * ASSOCIATIONS_PER_ENTRY,
        "variants": variants,
        "active_bindings": active_bindings,
        "binding_history_depth": binding_history_depth,
        "bindings": active_bindings * binding_history_depth,
    }


def _signal_contract(index: int) -> dict[str, object]:
    semantic_key, unit_key, aggregation = SEMANTIC_CONTRACTS[
        index % len(SEMANTIC_CONTRACTS)
    ]
    return {
        "series_key": f"signal_{index:05d}",
        "display_name": f"Senal de referencia {index:05d}",
        "semantic_type_key": semantic_key,
        "unit_key": unit_key,
        "signal_role": "input",
        "aggregation": aggregation,
    }


def _ordered_periods(count: int) -> list[dict[str, object]]:
    """Strictly ordered, non overlapping coverage of a fixed resolution.

    The stamps are a synthetic monotonic sequence rather than a calendar: the
    projection only needs ordered, comparable text, and this keeps a million
    period rows cheap to generate.
    """

    return [
        {
            "timestamp_start": f"2026-01-01T00:00:{index:07d}",
            "timestamp_end": f"2026-01-01T00:00:{index + 1:07d}",
            "duration_hours": 1.0,
        }
        for index in range(count)
    ]


def build_fixture(
    store,
    *,
    scale: float = 1.0,
    periods: int | None = None,
    actor: str = "performance_fixture",
    report=None,
) -> dict[str, object]:
    """Build the fixture through the production writers and time each stage."""

    plan = fixture_plan(scale, periods=periods)
    announce = report or (lambda message: None)
    started = time.perf_counter()

    project = store.create_project(name=f"TS7-005 fixture {int(started)}")
    signals = [_signal_contract(index) for index in range(plan["signals_per_set"])]
    periods = _ordered_periods(plan["periods"])
    values = {
        signal["series_key"]: [
            float(index % 97) + 0.5 for index in range(plan["periods"])
        ]
        for signal in signals
    }

    publication_seconds: list[float] = []
    signal_ids: list[int] = []
    for set_index in range(plan["sets"]):
        publish_started = time.perf_counter()
        receipt = store.publish_canonical_set_revision(
            project_id=project["id"],
            name=f"Referencia {set_index:05d}",
            data_class_key="real",
            timezone="UTC",
            signals=signals,
            periods=periods,
            values=values,
            actor=actor,
        )
        publication_seconds.append(time.perf_counter() - publish_started)
        signal_ids.extend(int(value) for value in receipt["signal_ids"].values())
        if (set_index + 1) % 25 == 0:
            announce(f"published {set_index + 1}/{plan['sets']} sets")

    # Consumers live in their own projects, which is the mixed-project shape
    # chapter 9.2 asks the fixture to have: a shared set is associated with
    # objects that do not belong to the project that owns it.
    objects = [
        store.ensure_global_signal_slot(project_id=project["id"], actor=actor)["id"]
    ]
    for index in range(1, plan["objects"]):
        consumer = store.create_project(
            name=f"TS7-005 consumidor {int(started)}-{index:03d}"
        )
        objects.append(
            store.ensure_global_signal_slot(
                project_id=consumer["id"], actor=actor
            )["id"]
        )

    associations = _seed_associations(store, signal_ids, objects, actor=actor)
    announce(f"seeded {associations} associations")

    # AC-PER-05 and AC-PER-06 measure one 200 row batch, and a batch belongs to
    # exactly one target project. `_seed_associations` claims every pair it can
    # see, so the batch needs its own objects inside the fixture project: hydro
    # components, which the positive matrix pairs with the `hydro_inflow`
    # signals the fixture already publishes.
    batch_objects = [
        int(
            store.ensure_project_component(
                project_id=project["id"],
                component_key=f"batch_hydro_{index:03d}",
                component_type="hydro",
                display_name=f"Central de lote {index:03d}",
            )["id"]
        )
        for index in range(BATCH_MEASUREMENT_OBJECTS)
    ]

    variants = _seed_variants(store, project["id"], plan["variants"], actor=actor)
    bindings = _seed_bindings(
        store,
        variants=variants,
        objects=objects,
        signal_ids=signal_ids,
        depth=plan["binding_history_depth"],
        actor=actor,
    )
    announce(f"seeded {bindings} bindings")

    return {
        "plan": plan,
        "project_id": project["id"],
        "objects": objects,
        "batch_objects": batch_objects,
        "signal_ids": signal_ids,
        "variants": variants,
        # The preview budgets need one exact revision and a range that is
        # inside the synthetic coverage, so the fixture hands both back rather
        # than making the caller reconstruct them.
        "preview_revision_id": int(receipt["revision_id"]),
        "preview_signal_id": int(receipt["signal_ids"][signals[0]["series_key"]]),
        "coverage_from": periods[0]["timestamp_start"],
        "coverage_to": periods[-1]["timestamp_end"],
        "signal_count": len(signal_ids),
        "association_count": associations,
        "binding_count": bindings,
        "publication_seconds": publication_seconds,
        "build_seconds": time.perf_counter() - started,
    }


def _seed_associations(store, signal_ids, objects, *, actor: str) -> int:
    table = store.link_layer_table_names()["time_series_catalog_associations"]
    canonical_sets = store.canonical_table_names()["time_series_signals"]
    set_of = {
        int(row["id"]): int(row["time_series_set_id"])
        for row in store.connection.execute(
            f"SELECT id, time_series_set_id FROM {canonical_sets}"
        ).fetchall()
    }
    rows = [
        (
            signal_id,
            set_of[signal_id],
            object_id,
            1,
            1,
            "2026-01-01T00:00:00",
            actor,
        )
        for signal_id in signal_ids
        for object_id in objects
    ]
    store.connection.executemany(
        f"""
        INSERT INTO {table} (
            signal_id, time_series_set_id, linkable_object_id, binding_role_id,
            compatibility_rule_id, created_at, created_by
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    return len(rows)


def _seed_variants(store, project_id: int, count: int, *, actor: str) -> list[int]:
    variants = []
    for index in range(count):
        scenario = store.create_scenario(
            project_id=project_id, name=f"Variante {index:05d}"
        )
        case = store.get_or_create_case_for_scenario(scenario["id"])
        variants.append(int(store.get_or_create_default_input_variant(case["id"])["id"]))
    return variants


def _seed_bindings(
    store, *, variants, objects, signal_ids, depth: int, actor: str
) -> int:
    table = store.link_layer_table_names()["case_time_series_bindings"]
    canonical = store.canonical_table_names()
    pinned = {
        int(row["id"]): (
            int(row["time_series_set_id"]),
            int(row["set_revision_id"]),
            row["content_hash"],
        )
        for row in store.connection.execute(
            f"""
            SELECT signal.id AS id, signal.time_series_set_id AS time_series_set_id,
                   revision.id AS set_revision_id, revision.content_hash AS content_hash
            FROM {canonical['time_series_signals']} AS signal
            JOIN {canonical['time_series_sets']} AS the_set
              ON the_set.id = signal.time_series_set_id
            JOIN {canonical['time_series_set_revisions']} AS revision
              ON revision.id = the_set.current_revision_id
            """
        ).fetchall()
    }
    rows = []
    for position, variant_id in enumerate(variants):
        for object_index, object_id in enumerate(objects):
            signal_id = signal_ids[(position + object_index) % len(signal_ids)]
            set_id, revision_id, content_hash = pinned[signal_id]
            for generation in range(depth):
                # Only the last generation stays active; the rest is the
                # append-only history a real variant accumulates.
                active = generation == depth - 1
                rows.append(
                    (
                        variant_id,
                        object_id,
                        1,
                        signal_id,
                        set_id,
                        revision_id,
                        content_hash,
                        "catalog",
                        1,
                        "active" if active else "superseded",
                        "fixture",
                        None if active else "2026-01-02T00:00:00",
                        None if active else actor,
                        "2026-01-01T00:00:00",
                        "2026-01-01T00:00:00",
                        actor,
                        actor,
                    )
                )
    store.connection.executemany(
        f"""
        INSERT INTO {table} (
            case_input_variant_id, linkable_object_id, binding_role_id,
            signal_id, time_series_set_id, set_revision_id, bound_content_hash,
            source_kind, compatibility_rule_id, status, change_reason_code,
            superseded_at, superseded_by, created_at, updated_at,
            created_by, updated_by
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    return len(rows)


def percentile(samples: list[float], fraction: float) -> float:
    """Nearest-rank percentile, so a small sample still reports honestly."""

    if not samples:
        raise ValueError("no samples")
    ordered = sorted(samples)
    rank = max(1, min(len(ordered), int(round(fraction * len(ordered) + 0.5))))
    return ordered[rank - 1]


def _preview_samples(
    store, *, fixture: dict, max_points: int, repetitions: int
) -> list[float]:
    """Time one bounded preview of an exact revision, chapter 9.2 style."""

    def read():
        return store.read_catalog_input_preview(
            fixture["preview_signal_id"],
            revision_id=fixture["preview_revision_id"],
            range_from=fixture["coverage_from"],
            range_to=fixture["coverage_to"],
            sampling="uniform",
            max_points=max_points,
        )

    # One discarded call, so the budget reports the steady state of the query
    # and not the cold cache the fixture build leaves behind.
    read()
    samples = []
    for _ in range(repetitions):
        started = time.perf_counter()
        read()
        samples.append((time.perf_counter() - started) * 1000.0)
    return samples


def _free_association_operations(store, *, fixture: dict, size: int) -> list[dict]:
    """Batch rows the fixture has not already claimed.

    ``_seed_associations`` fills every ``(signal, object)`` pair of the shared
    consumers, and those consumers deliberately live in other projects, so a
    fresh batch uses the dedicated hydro components of the fixture project and
    the ``hydro_inflow`` signals the positive matrix of chapter 3.2 pairs with
    them.
    """

    entries = store.catalog_projection_table_names()["time_series_catalog_entries"]
    inflows = [
        int(row["signal_id"])
        for row in store.connection.execute(
            f"""
            SELECT signal_id FROM {entries}
            WHERE semantic_type_key = 'hydro_inflow'
            ORDER BY signal_id
            """
        ).fetchall()
    ]
    operations = []
    for signal_id in inflows:
        for object_id in fixture["batch_objects"]:
            operations.append(
                {
                    "client_operation_id": f"perf-{signal_id}-{object_id}",
                    "action": "add",
                    "signal_id": signal_id,
                    "linkable_object_id": object_id,
                    "binding_role_key": "hydro_inflow",
                    "expected_absent": True,
                    "reason_code": "catalog_association_requested",
                }
            )
            if len(operations) == size:
                return operations
    return operations


def measure_budgets(
    store, *, fixture: dict, repetitions: int = 20
) -> dict[str, object]:
    """p95 of every budgeted query of chapter 9.2 this ticket is measured by."""

    page_samples = []
    for _ in range(repetitions):
        started = time.perf_counter()
        store.read_catalog_page(limit=50)
        page_samples.append((time.perf_counter() - started) * 1000.0)

    context_samples = []
    for index in range(repetitions):
        object_id = fixture["objects"][index % len(fixture["objects"])]
        started = time.perf_counter()
        store.read_object_context_page(linkable_object_id=object_id, limit=50)
        context_samples.append((time.perf_counter() - started) * 1000.0)

    publication_samples = [
        seconds * 1000.0 for seconds in fixture["publication_seconds"]
    ]

    small_preview = _preview_samples(
        store, fixture=fixture, max_points=500, repetitions=repetitions
    )
    large_preview = _preview_samples(
        store, fixture=fixture, max_points=2000, repetitions=repetitions
    )

    # AC-PER-05 and AC-PER-06 are the two halves of one batch: the read-only
    # prevalidation, then the commit that has to reauthorize and write it in a
    # single transaction. They are measured on the same 200 rows, in order,
    # because that is how the surface is used.
    batch_size = 200
    operations = _free_association_operations(
        store, fixture=fixture, size=batch_size
    )
    prevalidation_samples: list[float] = []
    commit_samples: list[float] = []
    if operations:
        document = {
            "target_project_id": fixture["project_id"],
            "operations": operations,
        }
        for _ in range(max(1, repetitions // 4)):
            started = time.perf_counter()
            prevalidation = store.prevalidate_catalog_association_batch(
                document, actor_class="internal:performance"
            )
            prevalidation_samples.append((time.perf_counter() - started) * 1000.0)
        started = time.perf_counter()
        store.commit_catalog_association_batch(
            document,
            actor_user={"id": None, "email": "performance_fixture", "role": "admin"},
            actor_class="internal:performance",
            request_id="req-performance-fixture",
            prevalidation_token=prevalidation["prevalidation_token"],
            if_match=prevalidation["commit_etag"],
            idempotency_key="performance-fixture-batch",
            confirmed=True,
        )
        commit_samples.append((time.perf_counter() - started) * 1000.0)

    def budget(identifier, description, budget_ms, samples):
        if not samples:
            return {
                "description": description,
                "budget_ms": budget_ms,
                "p95_ms": None,
                "samples": 0,
                "note": "the fixture had no free rows at this scale",
            }
        return {
            "description": description,
            "budget_ms": budget_ms,
            "p95_ms": round(percentile(samples, 0.95), 3),
            # The spread is reported next to the percentile, so a run that only
            # missed a budget on one outlier is legible as such in the evidence.
            "median_ms": round(percentile(samples, 0.5), 3),
            "min_ms": round(min(samples), 3),
            "max_ms": round(max(samples), 3),
            "samples": len(samples),
        }

    measured = {
        "AC-PER-01": budget(
            "AC-PER-01", "50 row catalog page without facets", 300, page_samples
        ),
        "AC-PER-02": budget(
            "AC-PER-02", "contextual object list", 300, context_samples
        ),
        "AC-PER-07": budget(
            "AC-PER-07",
            (
                "synchronous publication of "
                f"{fixture['plan']['signals_per_set'] * fixture['plan']['periods']}"
                " cells"
            ),
            5000,
            publication_samples,
        ),
    }
    measured["AC-PER-03"] = budget(
        "AC-PER-03", "preview of 500 points", 500, small_preview
    )
    measured["AC-PER-04"] = budget(
        "AC-PER-04", "maximum preview of 2.000 points", 1000, large_preview
    )
    measured["AC-PER-05"] = budget(
        "AC-PER-05",
        f"prevalidation of {len(operations)} associations",
        2000,
        prevalidation_samples,
    )
    measured["AC-PER-06"] = budget(
        "AC-PER-06",
        f"commit of {len(operations)} associations without lock wait",
        2000,
        commit_samples,
    )
    return {key: measured[key] for key in sorted(measured)}


def capture_reference_plans(store, *, fixture: dict) -> dict[str, object]:
    """Reference plan of every critical query, for the saved evidence file."""

    plans = {
        "catalog_page": store.explain_catalog_page(limit=50, analyze=True),
        "object_context_page": store.explain_object_context_page(
            linkable_object_id=fixture["objects"][0], limit=50, analyze=True
        ),
    }
    page = store.read_catalog_page(limit=50)
    if page["items"]:
        last = page["items"][-1]
        plans["catalog_page_keyset"] = store.explain_catalog_page(
            limit=50,
            cursor_key=[last["updated_at"], last["display_name_sort"], last["signal_id"]],
            analyze=True,
        )
    # The preview is the one budgeted query that is allowed to read values, so
    # its plan is saved to show that it reads them through the revision key and
    # never scans the table (chapter 9.4).
    plans["revision_preview"] = store.explain_revision_preview(
        signal_id=fixture["preview_signal_id"],
        revision_id=fixture["preview_revision_id"],
        range_from=fixture["coverage_from"],
        range_to=fixture["coverage_to"],
        analyze=True,
    )
    return plans
