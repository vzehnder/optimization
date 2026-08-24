import { useQuery } from "@tanstack/react-query";

import { getSignalCatalog, type SignalCatalogEntry } from "./api/client";

export type { SignalCatalogEntry };

export const signalCatalogQueryKey = ["signal-catalog"] as const;

/** The canonical registry, read once per session from the authenticated API.
 *
 * The frontend keeps no signal-to-unit table of its own: signal keys, units,
 * entity types and nonnegative rules all arrive here.
 */
export function useSignalCatalog() {
  return useQuery({
    queryKey: signalCatalogQueryKey,
    queryFn: ({ signal }) => getSignalCatalog(signal),
    staleTime: Infinity,
    retry: false,
  });
}

export function signalCatalogEntry(
  catalog: SignalCatalogEntry[],
  signalKey: string,
): SignalCatalogEntry | null {
  return catalog.find((entry) => entry.signal_key === signalKey) || null;
}

export function signalCatalogOptions(
  catalog: SignalCatalogEntry[],
): { value: string; label: string }[] {
  return catalog.map((entry) => ({
    value: entry.signal_key,
    label: `${entry.signal_key} (${entry.unit})`,
  }));
}

export function signalCatalogUnit(
  catalog: SignalCatalogEntry[],
  signalKey: string,
): string {
  return signalCatalogEntry(catalog, signalKey)?.unit || "";
}

/** Signals scoped to a one-bus component are mapped per asset, not per column. */
export function isPerEntitySignal(entry: SignalCatalogEntry): boolean {
  return Boolean(entry.entity_type?.startsWith("component:"));
}
