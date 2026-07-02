import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type {
  HydraulicDiagramNodeWrite,
  HydraulicNaturalInflowSeriesPoint,
} from "../api/client";
import { HydraulicInflowPanel } from "../Workspace";

function makeNode(
  points: HydraulicNaturalInflowSeriesPoint[] = [],
): HydraulicDiagramNodeWrite {
  return {
    technical_key: "reservoir_1",
    display_name: "emb_Laja",
    component_type: "reservoir",
    natural_inflow_series: points.length
      ? { time_series_set_id: null, version_label: null, points }
      : null,
  } as unknown as HydraulicDiagramNodeWrite;
}

describe("HydraulicInflowPanel import", () => {
  it("imports afluentes from a csv file, replacing points", async () => {
    const updateInflowSeries = vi.fn();
    render(
      <HydraulicInflowPanel
        node={makeNode([
          { timestamp: "1999-01-01T00:00:00", duration_hours: 1, value_m3s: 1 },
        ])}
        availableSeries={[]}
        updateInflowSeries={updateInflowSeries}
      />,
    );

    const file = new File(
      [
        "timestamp,duration_hours,value_m3s\n" +
          "2026-01-01T00:00:00,1,12.5\n" +
          "2026-01-01T01:00:00,1,13\n",
      ],
      "afluentes.csv",
      { type: "text/csv" },
    );

    await userEvent.upload(screen.getByTestId("inflow-import-reservoir_1"), file);

    await waitFor(() => expect(updateInflowSeries).toHaveBeenCalled());
    expect(updateInflowSeries).toHaveBeenCalledWith("reservoir_1", {
      time_series_set_id: null,
      version_label: null,
      points: [
        { timestamp: "2026-01-01T00:00:00", duration_hours: 1, value_m3s: 12.5 },
        { timestamp: "2026-01-01T01:00:00", duration_hours: 1, value_m3s: 13 },
      ],
    });
  });

  it("shows imported points read-only with no manual add or edit", () => {
    render(
      <HydraulicInflowPanel
        node={makeNode([
          { timestamp: "2026-01-01T00:00:00", duration_hours: 1, value_m3s: 12.5 },
        ])}
        availableSeries={[]}
        updateInflowSeries={vi.fn()}
      />,
    );

    // The imported value is visible to the user.
    expect(screen.getByText(/12\.5/)).toBeVisible();
    // No manual add button, no per-point remove button, no editable inputs.
    expect(screen.queryByText(/Agregar punto de afluente/)).toBeNull();
    expect(screen.queryByText(/Quitar punto/)).toBeNull();
    expect(screen.queryByLabelText(/Caudal m3\/s 1/)).toBeNull();
  });

  it("surfaces a helpful error when the file is malformed", async () => {
    render(
      <HydraulicInflowPanel
        node={makeNode()}
        availableSeries={[]}
        updateInflowSeries={vi.fn()}
      />,
    );

    const bad = new File(["timestamp,value_m3s\n2026-01-01T00:00:00,1\n"], "x.csv", {
      type: "text/csv",
    });
    await userEvent.upload(screen.getByTestId("inflow-import-reservoir_1"), bad);

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/duration_hours/);
  });
});
