"use client";

/**
 * Entitlement store (U-03-T10): the organisation's entitlements from the bootstrap API, kept by
 * React Query and given to every `useFeature` / `<Gated>` below through `FeatureProvider`.
 *
 *   <EntitlementsProvider org={org}>…</EntitlementsProvider>      // AppShell does this
 *   const { data } = useEntitlements();                            // mode, reason, since…
 *
 * Decisions (`decide`): `loading` until the first answer; `allowed` when the key is in
 * `features`; otherwise `gated` with the product, its name and the packages that include it (the
 * locked panel names them, gap-41). If the bootstrap call fails, decisions are `allowed`: the API
 * still refuses with 402 and forms show the same locked panel (U-03 UI rule), so a network hiccup
 * never locks people out of screens they paid for. `CORE` is never gated.
 *
 * The query key is `["entitlements", org]`. A screen that gets a 402 calls
 * `useRefreshEntitlements()`, so the app follows a change made elsewhere (a downgrade, the grace
 * period ending) without a reload.
 */
import { QueryClient, QueryClientProvider, useQuery, useQueryClient } from "@tanstack/react-query";
import { createContext, useCallback, useContext, useMemo, type ReactNode } from "react";

import { FeatureProvider, type FeatureDecision } from "@numo9/ui";

import { CORE } from "@/catalogue/features";

import { getEntitlements, isEntitlements, type Entitlements } from "./api";

export const ENTITLEMENTS_KEY = "entitlements";
/** Fresh for a minute; a 402, a focus or a reconnect refreshes it sooner. */
const STALE_MS = 60_000;

/** The bootstrap call answered something else than the entitlements (status 0 = no network). */
export class EntitlementsUnavailable extends Error {
  constructor(readonly status: number) {
    super(`entitlements answered ${status}`);
  }
}

/** Retry once when the network failed; an HTTP answer (404, 500…) is final at once. */
function retryOnce(failures: number, error: unknown): boolean {
  return failures < 1 && error instanceof EntitlementsUnavailable && error.status === 0;
}

let sharedClient: QueryClient | undefined;

/** The app's QueryClient (one per page); tests pass their own to `EntitlementsProvider`. */
export function appQueryClient(): QueryClient {
  sharedClient ??= new QueryClient({
    defaultOptions: { queries: { staleTime: STALE_MS, refetchOnWindowFocus: true } },
  });
  return sharedClient;
}

export interface EntitlementsState {
  org?: string;
  /** The answer once loaded; undefined while loading or after a failed call. */
  data?: Entitlements;
  status: "loading" | "ready" | "error";
}

const StateContext = createContext<EntitlementsState>({ status: "error" });

/** The current organisation's entitlements (mode, reason, since, products…). */
export function useEntitlements(): EntitlementsState {
  return useContext(StateContext);
}

/** The decision for `feature` under `state` (see the module docstring). */
export function decide(state: EntitlementsState, feature: string): FeatureDecision {
  if (feature === CORE || state.status === "error") return { feature, state: "allowed" };
  if (state.status === "loading" || !state.data) return { feature, state: "loading" };
  const data = state.data;
  if (data.features.includes(feature)) return { feature, state: "allowed" };
  const product = productOf(feature);
  return {
    feature,
    state: "gated",
    product,
    productName: data.product_names[product] ?? product,
    packages: (data.packages_by_product[product] ?? []).map((p) => p.name),
  };
}

/** Product code of a feature key: `payroll.pay_runs.write` → `payroll`, `app.bank.x.read` → `app.bank`. */
export function productOf(feature: string): string {
  const parts = feature.split(".");
  return parts.slice(0, -2).join(".");
}

async function fetchEntitlements(org: string): Promise<Entitlements> {
  const result = await getEntitlements(org);
  if (result.status !== 200 || !isEntitlements(result.body)) {
    throw new EntitlementsUnavailable(result.status);
  }
  return result.body;
}

function Store({ org, children }: { org: string; children: ReactNode }) {
  const query = useQuery({
    queryKey: [ENTITLEMENTS_KEY, org],
    queryFn: () => fetchEntitlements(org),
    retry: retryOnce,
  });
  const state = useMemo<EntitlementsState>(
    () => ({
      org,
      data: query.data,
      status: query.data ? "ready" : query.isError ? "error" : "loading",
    }),
    [org, query.data, query.isError],
  );
  const source = useCallback((feature: string) => decide(state, feature), [state]);
  return (
    <StateContext.Provider value={state}>
      <FeatureProvider source={source}>{children}</FeatureProvider>
    </StateContext.Provider>
  );
}

export function EntitlementsProvider({
  org,
  client,
  children,
}: {
  org: string;
  /** Defaults to the app's QueryClient. */
  client?: QueryClient;
  children: ReactNode;
}) {
  return (
    <QueryClientProvider client={client ?? appQueryClient()}>
      <Store org={org}>{children}</Store>
    </QueryClientProvider>
  );
}

/** Refetch the organisation's entitlements (after a 402: the package or the status changed). */
export function useRefreshEntitlements(): () => void {
  const client = useQueryClient();
  const { org } = useEntitlements();
  return useCallback(() => {
    if (org) void client.invalidateQueries({ queryKey: [ENTITLEMENTS_KEY, org] });
  }, [client, org]);
}
