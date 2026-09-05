// Chapter 8.1: every mutation entry point hands off to the one protected
// journey. The routes live here so the read surfaces can link into it without
// owning any part of the mutation itself.

export function objectJourneyPath({
  projectId,
  linkableObjectId,
  intent,
  associationId,
}: {
  projectId: number;
  linkableObjectId: number;
  intent: string;
  associationId?: number;
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
  return `/time-series/journey?${params.toString()}`;
}

export function catalogJourneyPath({
  signalId,
  projectId,
}: {
  signalId: number;
  projectId: number;
}): string {
  const params = new URLSearchParams({
    entry: "catalog",
    signal_id: String(signalId),
    project_id: String(projectId),
  });
  return `/time-series/journey?${params.toString()}`;
}
