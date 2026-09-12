// Keep the caller's query parameters; section destinations are fixed by the UI.
export function workspaceSectionSearch(
  search: string,
  section: string,
): string {
  const params = new URLSearchParams(search);
  params.set("section", section);
  return `?${params.toString()}`;
}
