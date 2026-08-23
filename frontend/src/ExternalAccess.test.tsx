import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { App } from "./App";

describe("external identity compatibility", () => {
  it("keeps a migrated external viewer in the existing client portal", async () => {
    window.history.replaceState({}, "", "/react/client");
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const path = String(input);
        if (path === "/api/auth/me") {
          return Response.json({
            user: {
              id: 7,
              email: "viewer@example.local",
              display_name: "External Viewer",
              role: "external",
              is_active: true,
            },
            bootstrap_required: false,
          });
        }
        if (path === "/api/client/projects") {
          return Response.json({ projects: [] });
        }
        return Response.json(
          { detail: `unhandled GET ${path}` },
          { status: 500 },
        );
      }),
    );

    render(<App />);

    expect(
      await screen.findByRole("heading", { name: "Portal cliente" }),
    ).toBeVisible();
    expect(screen.getByRole("link", { name: "Cliente" })).toBeVisible();
    expect(
      screen.queryByRole("link", { name: "Analista" }),
    ).not.toBeInTheDocument();
  });
});
