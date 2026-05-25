#!/usr/bin/env python3
"""Generate a Plotly dispatch report from a BESS run output folder."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


REQUIRED_COLUMNS = (
    "timestamp",
    "price_usd_per_mwh",
    "p_charge_mw",
    "p_discharge_mw",
    "energy_mwh",
    "period_profit_usd",
    "degradation_cost_usd",
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate plots/dispatch_report.html from a BESS dispatch run folder."
    )
    parser.add_argument("run_output_dir", help="Folder containing dispatch.csv")
    args = parser.parse_args()

    report_path = generate_report(Path(args.run_output_dir))
    print(report_path)
    return 0


def generate_report(run_output_dir: Path) -> Path:
    dispatch_path = run_output_dir / "dispatch.csv"
    rows = read_dispatch_rows(dispatch_path)

    plots_dir = run_output_dir / "plots"
    plots_dir.mkdir(parents=True, exist_ok=True)

    report_path = plots_dir / "dispatch_report.html"
    report_path.write_text(build_html(rows), encoding="utf-8")
    return report_path


def read_dispatch_rows(dispatch_path: Path) -> list[dict[str, str]]:
    if not dispatch_path.is_file():
        raise FileNotFoundError(f"dispatch.csv not found: {dispatch_path}")

    with dispatch_path.open(newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        missing_columns = [
            column for column in REQUIRED_COLUMNS if column not in (reader.fieldnames or [])
        ]
        if missing_columns:
            missing = ", ".join(missing_columns)
            raise ValueError(f"dispatch.csv is missing required columns: {missing}")

        rows = list(reader)

    if not rows:
        raise ValueError("dispatch.csv must contain at least one dispatch row")

    return rows


def build_html(rows: list[dict[str, str]]) -> str:
    timestamps = [row["timestamp"] for row in rows]
    data = {
        column: numeric_column(rows, column)
        for column in REQUIRED_COLUMNS
        if column != "timestamp"
    }

    payload = json.dumps(
        {
            "timestamp": timestamps,
            **data,
        }
    )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>BESS Dispatch Report</title>
  <script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
  <style>
    :root {{
      color-scheme: light;
      font-family: Arial, Helvetica, sans-serif;
      background: #f7f9fb;
      color: #172033;
    }}

    body {{
      margin: 0;
    }}

    main {{
      max-width: 1180px;
      margin: 0 auto;
      padding: 28px 20px 40px;
    }}

    h1 {{
      margin: 0 0 18px;
      font-size: 28px;
      font-weight: 700;
    }}

    .plot {{
      width: 100%;
      height: 360px;
      margin: 0 0 18px;
      background: #ffffff;
      border: 1px solid #d9e1ea;
    }}
  </style>
</head>
<body>
  <main>
    <h1>BESS Dispatch Report</h1>
    <div id="price-dispatch" class="plot" aria-label="Price and dispatch plot"></div>
    <div id="energy-state" class="plot" aria-label="Stored energy plot"></div>
    <div id="period-economics" class="plot" aria-label="Period economics plot"></div>
  </main>

  <script>
    const dispatch = {payload};
    const commonLayout = {{
      margin: {{l: 64, r: 28, t: 46, b: 58}},
      paper_bgcolor: "#ffffff",
      plot_bgcolor: "#ffffff",
      hovermode: "x unified",
      legend: {{orientation: "h", y: -0.25}},
      xaxis: {{title: "timestamp"}}
    }};

    Plotly.newPlot("price-dispatch", [
      {{
        x: dispatch.timestamp,
        y: dispatch.price_usd_per_mwh,
        name: "price_usd_per_mwh",
        type: "scatter",
        mode: "lines+markers",
        yaxis: "y2",
        line: {{color: "#4257b2", width: 2}}
      }},
      {{
        x: dispatch.timestamp,
        y: dispatch.p_charge_mw,
        name: "p_charge_mw",
        type: "bar",
        marker: {{color: "#1f9d77"}}
      }},
      {{
        x: dispatch.timestamp,
        y: dispatch.p_discharge_mw,
        name: "p_discharge_mw",
        type: "bar",
        marker: {{color: "#c85050"}}
      }}
    ], {{
      ...commonLayout,
      title: "Price and dispatch",
      barmode: "group",
      yaxis: {{title: "MW"}},
      yaxis2: {{
        title: "USD/MWh",
        overlaying: "y",
        side: "right",
        showgrid: false
      }}
    }}, {{responsive: true}});

    Plotly.newPlot("energy-state", [
      {{
        x: dispatch.timestamp,
        y: dispatch.energy_mwh,
        name: "energy_mwh",
        type: "scatter",
        mode: "lines+markers",
        fill: "tozeroy",
        line: {{color: "#2f6f91", width: 2}}
      }}
    ], {{
      ...commonLayout,
      title: "Stored energy",
      yaxis: {{title: "MWh"}}
    }}, {{responsive: true}});

    Plotly.newPlot("period-economics", [
      {{
        x: dispatch.timestamp,
        y: dispatch.period_profit_usd,
        name: "period_profit_usd",
        type: "bar",
        marker: {{color: "#326f3f"}}
      }},
      {{
        x: dispatch.timestamp,
        y: dispatch.degradation_cost_usd,
        name: "degradation_cost_usd",
        type: "bar",
        marker: {{color: "#94623a"}}
      }}
    ], {{
      ...commonLayout,
      title: "Period economics",
      barmode: "group",
      yaxis: {{title: "USD"}}
    }}, {{responsive: true}});
  </script>
</body>
</html>
"""


def numeric_column(rows: list[dict[str, str]], column: str) -> list[float]:
    values = []
    for row_index, row in enumerate(rows, start=1):
        value = row[column]
        try:
            values.append(float(value))
        except ValueError as error:
            raise ValueError(
                f"dispatch.csv column {column} has a non-numeric value at row {row_index}: {value!r}"
            ) from error

    return values


if __name__ == "__main__":
    raise SystemExit(main())
