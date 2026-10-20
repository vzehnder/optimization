import { act, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { RunProgress, ScenarioRun } from "./api/client";
import { RunProgressPanel } from "./RunProgress";

const progress: RunProgress = {
  stage: "building",
  elapsed_seconds: 65,
  gap_percent: null,
  best_objective: null,
  best_bound: null,
  solver_seconds: null,
  events: [
    {
      timestamp: "2026-10-16T12:00:00Z",
      stage: "building",
      message: "Construyendo modelo hidráulico.",
    },
  ],
  solver_log: "",
  log_truncated: false,
};
const run: ScenarioRun = {
  id: 53,
  scenario_version_id: 1,
  created_at: "2026-10-16T12:00:00Z",
  status: "running",
  progress,
};

afterEach(() => vi.useRealTimers());

describe("simulation progress", () => {
  it("shows Julia preparation immediately and advances elapsed time between polls", () => {
    vi.useFakeTimers();
    render(<RunProgressPanel run={run} updatedAt={Date.now()} />);
    expect(screen.getByText("Construyendo el modelo en Julia")).toBeVisible();
    expect(screen.getByText("00:01:05")).toBeVisible();
    expect(screen.getByText("Sin dato del solver")).toBeVisible();
    act(() => vi.advanceTimersByTime(3000));
    expect(screen.getByText("00:01:08")).toBeVisible();
  });

  it("updates the real gap and log and freezes elapsed time on completion", () => {
    vi.useFakeTimers();
    const { rerender } = render(
      <RunProgressPanel run={run} updatedAt={Date.now()} />,
    );
    const optimizing = {
      ...run,
      progress: {
        ...progress,
        stage: "optimizing",
        gap_percent: 9.09,
        solver_log: "BestBound BestSol Gap\n1200 1100 9.09%\n",
      },
    };
    rerender(<RunProgressPanel run={optimizing} updatedAt={Date.now()} />);
    expect(screen.getByText("Optimizando con HiGHS")).toBeVisible();
    expect(screen.getByText("9,09 %")).toBeVisible();
    expect(screen.getByLabelText("Log de HiGHS")).toHaveTextContent(
      "1200 1100 9.09%",
    );
    rerender(
      <RunProgressPanel
        run={{
          ...optimizing,
          status: "succeeded",
          progress: {
            ...optimizing.progress,
            elapsed_seconds: 80,
            gap_percent: 0,
          },
        }}
        updatedAt={Date.now()}
      />,
    );
    expect(screen.getByText("0 %")).toBeVisible();
    act(() => vi.advanceTimersByTime(5000));
    expect(screen.getByText("00:01:20")).toBeVisible();
    expect(screen.getByText("Simulación finalizada")).toBeVisible();
  });

  it("distinguishes queueing and old runs without fabricating progress", () => {
    const { rerender } = render(
      <RunProgressPanel
        run={{ ...run, status: "queued", progress: undefined }}
        updatedAt={Date.now()}
      />,
    );
    expect(screen.getByText("Esperando turno para iniciar")).toBeVisible();
    expect(screen.getByText("—")).toBeVisible();
    rerender(
      <RunProgressPanel
        run={{ ...run, status: "succeeded", progress: undefined }}
        updatedAt={Date.now()}
      />,
    );
    expect(
      screen.queryByRole("region", { name: "Avance de la simulación" }),
    ).not.toBeInTheDocument();
  });
});
