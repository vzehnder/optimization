import { ApiError } from "./api/client";

export function ruleErrorMessage(error: unknown): string {
  if (
    error instanceof ApiError &&
    error.details &&
    typeof error.details === "object"
  ) {
    const detail = error.details as {
      message?: unknown;
      alias?: unknown;
      period?: unknown;
    };
    if (typeof detail.message === "string") {
      const location = [
        typeof detail.alias === "string" ? detail.alias : "",
        typeof detail.period === "number" ? `período ${detail.period + 1}` : "",
      ]
        .filter(Boolean)
        .join(" · ");
      return `${location ? location + ": " : ""}${detail.message}`;
    }
  }
  return error instanceof Error
    ? error.message
    : "No se pudo completar la acción";
}
