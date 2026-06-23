import { describe, expect, it, vi } from "vitest";

import { requestDownload, requestJson } from "./client";

describe("API client", () => {
  it("exposes structured JSON errors through one stable error type", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(
            JSON.stringify({
              error: {
                category: "validation_error",
                message: "Project name is required.",
                details: { field: "name" },
              },
            }),
            { status: 422, headers: { "Content-Type": "application/json" } },
          ),
      ),
    );

    const request = requestJson("/api/projects");

    await expect(request).rejects.toMatchObject({
      status: 422,
      category: "validation_error",
      message: "Project name is required.",
      details: { field: "name" },
    });
  });

  it("returns non-JSON downloads with response metadata", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response("timestamp,power\n1,42", {
            headers: {
              "Content-Type": "text/csv",
              "Content-Disposition": 'attachment; filename="dispatch.csv"',
            },
          }),
      ),
    );

    const download = await requestDownload("/api/run-artifacts/3/download");

    expect(download.filename).toBe("dispatch.csv");
    expect(download.contentType).toBe("text/csv");
    expect(await download.blob.text()).toBe("timestamp,power\n1,42");
  });

  it("forwards request cancellation without converting the abort error", async () => {
    const controller = new AbortController();
    vi.stubGlobal(
      "fetch",
      vi.fn(
        (_path: string, init?: RequestInit) =>
          new Promise<Response>((_resolve, reject) => {
            init?.signal?.addEventListener("abort", () =>
              reject(new DOMException("Request aborted", "AbortError")),
            );
          }),
      ),
    );

    const request = requestJson("/api/projects", { signal: controller.signal });
    controller.abort();

    await expect(request).rejects.toMatchObject({ name: "AbortError" });
  });
});
