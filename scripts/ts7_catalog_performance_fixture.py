"""Build the TS7-005 catalog fixture, measure its budgets and save its plans.

The reference fixture of chapter 9.2 is large by design (100.000 entries and
100.000.000 cells), so this script never touches a shared database unless it is
told to: it runs inside a transaction that is rolled back, and only ``--keep``
commits. Point ``--database-url`` at a dedicated performance database before
running ``--scale 1``.

    python scripts/ts7_catalog_performance_fixture.py --scale 0.001
    python scripts/ts7_catalog_performance_fixture.py --scale 1 --keep \
        --database-url postgresql://user:pass@host:5432/ts7_performance
"""

from __future__ import annotations

import argparse
import contextlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from app.database import database_url_from_env
from app.persistence import AnalystStore, utc_now_iso
from app.time_series_catalog_fixture import (
    build_fixture,
    capture_reference_plans,
    fixture_plan,
    measure_budgets,
)


EVIDENCE_DIRECTORY = REPO_ROOT / "docs" / "series_tiempo" / "iter7" / "performance"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--scale",
        type=float,
        default=0.001,
        help="1 is the reference fixture of chapter 9.2; smaller keeps proportions",
    )
    parser.add_argument("--database-url", default=None)
    parser.add_argument(
        "--periods",
        type=int,
        default=None,
        help=(
            "shorten every revision without shrinking the projection, so a "
            "machine that cannot hold the reference cells still measures the "
            "reference page and list plans"
        ),
    )
    parser.add_argument(
        "--repetitions", type=int, default=20, help="samples per budgeted query"
    )
    parser.add_argument(
        "--keep",
        action="store_true",
        help="commit the fixture instead of rolling it back",
    )
    parser.add_argument(
        "--evidence",
        default=None,
        help="where to write the plan and budget report (default: docs evidence)",
    )
    parser.add_argument(
        "--plan-only",
        action="store_true",
        help="print the sizes of the fixture without building it",
    )
    arguments = parser.parse_args()

    plan = fixture_plan(arguments.scale, periods=arguments.periods)
    if arguments.plan_only:
        print(json.dumps(plan, indent=2))
        return 0

    database_url = arguments.database_url or database_url_from_env()
    store = AnalystStore(database_url)
    try:
        with _isolation(store, keep=arguments.keep):
            fixture = build_fixture(
                store,
                scale=arguments.scale,
                periods=arguments.periods,
                report=lambda message: print(message),
            )
            budgets = measure_budgets(
                store, fixture=fixture, repetitions=arguments.repetitions
            )
            plans = capture_reference_plans(store, fixture=fixture)
            report = {
                "captured_at": utc_now_iso(),
                "engine": store.database_backend,
                "committed": bool(arguments.keep),
                "plan": fixture["plan"],
                "built": {
                    "signal_count": fixture["signal_count"],
                    "association_count": fixture["association_count"],
                    "binding_count": fixture["binding_count"],
                    "build_seconds": round(fixture["build_seconds"], 3),
                },
                "budgets": budgets,
                "reference_plans": plans,
                "reads_periods_or_values": _touches_content(plans),
            }
    finally:
        store.close()

    destination = Path(arguments.evidence) if arguments.evidence else (
        EVIDENCE_DIRECTORY
        / f"ts7-005-{store.database_backend}-scale-{arguments.scale}.json"
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report["budgets"], indent=2))
    print(f"evidence written to {destination}")
    return 0 if not report["reads_periods_or_values"] else 1


def _isolation(store, *, keep: bool):
    """Roll the whole fixture back unless the caller asked to keep it."""

    if keep:
        return contextlib.nullcontext()
    if store.database_backend == "postgresql":
        return store.connection._connection.transaction(  # noqa: SLF001
            force_rollback=True
        )
    raise SystemExit(
        "SQLite cannot roll a fixture back across statements here; "
        "use --keep with a throwaway sqlite:/// file"
    )


def _touches_content(plans: dict) -> bool:
    """No critical query may walk periods or values (AC-CAT-04)."""

    haystack = " ".join(
        line for plan in plans.values() for line in plan["plan"]
    ).lower()
    return "time_series_periods" in haystack or "time_series_values" in haystack


if __name__ == "__main__":
    raise SystemExit(main())
