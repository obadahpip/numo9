/**
 * Feature keys in the web app (U-01, docs/architecture/feature-keys.md): `<product>.<area>.<action>`
 * with action read, write or approve, or `CORE` for what every organisation has (Home, Settings,
 * users and roles, audit log) — never gated. Routes declare one in the route registry (eslint
 * `numo9/route-feature`, U-01-T08); screens and controls pass it to `useFeature` / `<Gated>`.
 */
export const CORE = "@core";

export type FeatureDeclaration =
  typeof CORE | `${string}.${string}.${"read" | "write" | "approve"}`;

const KEY = /^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)?\.[a-z][a-z0-9_]*\.(?:read|write|approve)$/;

export function isFeatureKey(value: string): boolean {
  return KEY.test(value);
}
