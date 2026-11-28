/**
 * Bank rules (F-04) fixtures for the e2e specs: rules in the API's shape and a stateful mock of
 * `/api/v1/o/acme/bank-rules…` (list per type, reorder, toggle) that keeps its state across page
 * reloads within one test — so "order persists after reload" checks what the server returns.
 * The rules themselves are tested on the real API in backend/tests/test_bank_rule_api.py.
 */
import type { Page, Route } from "@playwright/test";

import { jsonBody, mockCsrf } from "./auth-helpers";

export const ORG = "acme";

export function bankRule(over: Record<string, unknown> = {}) {
  return {
    id: "r1",
    type: "spend",
    name: "Petro-Canada fuel",
    match_mode: "all",
    priority: 1,
    active: true,
    auto_apply: false,
    contact_strategy: "none",
    contact: null,
    reference_template: "",
    transfer_account: null,
    scope_accounts: [],
    conditions: [{ field: "description", operator: "contains", value: "PETRO", value_to: "" }],
    allocations: [
      {
        account: { id: "acc-fuel", code: "5100", name: "Fuel" },
        tax_code: "purchase.ON.standard",
        description: "",
        fixed_amount: null,
        percent: "100",
      },
    ],
    applied_count: 0,
    last_applied_at: null,
    warnings: [],
    ...over,
  };
}

export type Rule = ReturnType<typeof bankRule>;

export async function mockRules(page: Page, initial: Rule[]) {
  await mockCsrf(page);
  const state = { rules: initial.map((r) => ({ ...r })), reorders: 0 };
  const ofType = (type: string) =>
    state.rules.filter((r) => r.type === type).sort((a, b) => a.priority - b.priority);
  await page.route(/\/api\/v1\/o\/acme\/bank-rules(\?.*)?$/, async (route: Route) => {
    const type = new URL(route.request().url()).searchParams.get("type") ?? "spend";
    await route.fulfill({ json: { results: ofType(type) } });
  });
  await page.route("**/api/v1/o/acme/bank-rules/reorder", async (route) => {
    const body = jsonBody(route) as { type: string; order: string[] };
    state.reorders += 1;
    body.order.forEach((id, index) => {
      const found = state.rules.find((r) => r.id === id);
      if (found) found.priority = index + 1;
    });
    await route.fulfill({ json: { results: ofType(body.type) } });
  });
  await page.route(/\/api\/v1\/o\/acme\/bank-rules\/r[0-9]+$/, async (route) => {
    const id = route.request().url().split("/").pop()!;
    const found = state.rules.find((r) => r.id === id);
    if (!found) return route.fulfill({ status: 404, json: {} });
    if (route.request().method() === "PATCH") Object.assign(found, jsonBody(route));
    await route.fulfill({ json: found });
  });
  return state;
}
