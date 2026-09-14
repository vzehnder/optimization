// Chapter 8.1: every mutation entry point hands off to the one protected
// journey. The routes live here so the read surfaces can link into it without
// owning any part of the mutation itself.

/** Only application destinations and public navigation state may travel in a return link. */
export function safeReturnPath(
  value: string | null | undefined,
  depth = 0,
): string | null {
  if (
    !value ||
    depth > 2 ||
    !value.startsWith("/") ||
    value.startsWith("//") ||
    value.includes("\\") ||
    Array.from(value).some((character) => character.charCodeAt(0) <= 32)
  )
    return null;
  const url = new URL(value, "http://workspace.local");
  const path = url.pathname;
  if (
    url.origin !== "http://workspace.local" ||
    !/^(\/time-series\/catalog|\/scenarios\/[1-9]\d*|\/projects\/[1-9]\d*(\/linkable-objects\/[1-9]\d*\/time-series|\/time-series-sets\/[1-9]\d*)?)$/.test(
      path,
    )
  )
    return null;
  const clean = new URLSearchParams();
  for (const [key, entry] of url.searchParams) {
    if (
      ["variant", "scenario_id", "variant_id", "inspector"].includes(key) &&
      /^[1-9]\d*$/.test(entry) &&
      Number.isSafeInteger(Number(entry))
    )
      clean.set(key, entry);
    if (
      key === "section" &&
      [
        "overview",
        "data",
        "runs",
        "advanced",
        "scenarios",
        "reports",
        "consoles",
        "access",
      ].includes(entry)
    )
      clean.set(key, entry);
    if (key === "q" && entry.length <= 200) clean.set(key, entry);
    if (
      [
        "semantic_type_key",
        "data_class_key",
        "unit_key",
        "binding_role_key",
        "signal_key",
        "kind",
      ].includes(key) &&
      /^[a-z][a-z0-9_]{0,99}$/.test(entry)
    )
      clean.set(key, entry);
    if (key === "visibility_scope" && ["project", "global"].includes(entry))
      clean.set(key, entry);
    if (key === "signal_status" && ["active", "archived"].includes(entry))
      clean.set(key, entry);
    if (
      key === "order" &&
      [
        "-updated_at,display_name",
        "display_name",
        "owner_project_name",
        "-coverage_end",
        "-association_count",
      ].includes(entry)
    )
      clean.set(key, entry);
    if (
      key === "cursor" &&
      entry.length > 0 &&
      entry.length <= 4096 &&
      clean.getAll(key).length < 50
    )
      clean.append(key, entry);
    if (key === "return_to") {
      const nested = safeReturnPath(entry, depth + 1);
      if (nested) clean.set(key, nested);
    }
  }
  return path + (clean.size ? `?${clean}` : "");
}

export function objectJourneyPath({
  projectId,
  linkableObjectId,
  intent,
  associationId,
  scenarioId,
  variantId,
  returnTo,
}: {
  projectId: number;
  linkableObjectId: number;
  intent: string;
  associationId?: number;
  scenarioId?: number;
  variantId?: number;
  returnTo?: string;
}): string {
  const params = new URLSearchParams({
    entry: "object",
    project_id: String(projectId),
    object_id: String(linkableObjectId),
    intent,
  });
  if (associationId !== undefined) {
    params.set("association_id", String(associationId));
  }
  if (scenarioId !== undefined) params.set("scenario_id", String(scenarioId));
  if (variantId !== undefined) params.set("variant_id", String(variantId));
  const returnPath = safeReturnPath(returnTo);
  if (returnPath) params.set("return_to", returnPath);
  return `/time-series/journey?${params.toString()}`;
}

export function catalogJourneyPath({
  signalId,
  projectId,
  returnTo,
}: {
  signalId: number;
  projectId: number;
  returnTo?: string;
}): string {
  const params = new URLSearchParams({
    entry: "catalog",
    signal_id: String(signalId),
    project_id: String(projectId),
  });
  const returnPath = safeReturnPath(returnTo);
  if (returnPath) params.set("return_to", returnPath);
  return `/time-series/journey?${params.toString()}`;
}
