import { useState } from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it } from "vitest";
import { HydraulicTravelTime } from "./HydraulicTravelTime";
import type { HydraulicTravelTimeParameters } from "./api/client";

it("lets the analyst specify pre-horizon flow and explains the initial water inventory", async () => {
  function Editor() {
    const [value, setValue] = useState<HydraulicTravelTimeParameters>({
      travel_time_hours: 0.75,
    });
    return (
      <HydraulicTravelTime
        value={value}
        onChange={(patch) => setValue({ ...value, ...patch })}
      />
    );
  }
  render(<Editor />);
  const user = userEvent.setup();
  await user.click(screen.getByText("Condición inicial"));
  await user.clear(
    screen.getByRole("spinbutton", { name: "Caudal previo al inicio (m³/s)" }),
  );
  await user.type(
    screen.getByRole("spinbutton", { name: "Caudal previo al inicio (m³/s)" }),
    "4",
  );
  expect(
    screen.getByText(/Agua inicial en tránsito: 0.0108 hm³/),
  ).toBeVisible();
});
