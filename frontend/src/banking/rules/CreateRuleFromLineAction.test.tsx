import { screen } from "@testing-library/react";

import { renderWithIntl } from "@/test/intl";

import { CreateRuleFromLineAction } from "./CreateRuleFromLineAction";
import { hasPrefill, keywordOf, prefillDraft, ruleFromLineHref } from "./fromLine";

/**
 * F-04-T14 — "Create rule from line": the action links to the builder with the line's payee /
 * description; the builder's pre-fill turns them into the first condition. (End to end:
 * e2e/bank-rules-builder.spec.ts opens the builder through the action's link.)
 */
const LINE = {
  id: "line-1",
  amount: "-45.10",
  payee: "",
  description: "PETRO-CANADA #1234 TORONTO 000987",
  bank_account: { id: "bank-1" },
};

it("links to the builder pre-filled from the line", () => {
  renderWithIntl(<CreateRuleFromLineAction org="refined" line={LINE} />);
  const link = screen.getByRole("link", {
    name: "Create a rule from PETRO-CANADA #1234 TORONTO 000987",
  });
  expect(link).toHaveTextContent("Create rule from this line");
  const href = new URL(link.getAttribute("href")!, "http://x");
  expect(href.pathname).toBe("/o/refined/banking/rules/new");
  expect(Object.fromEntries(href.searchParams)).toEqual({
    from_line: "line-1",
    type: "spend",
    description: "PETRO-CANADA #1234 TORONTO 000987",
    bank_account: "bank-1",
  });
});

it("pre-fill: description keyword without reference numbers, scoped to the account", () => {
  const query = Object.fromEntries(new URL(ruleFromLineHref("o", LINE), "http://x").searchParams);
  expect(hasPrefill(query)).toBe(true);
  const draft = prefillDraft(query);
  expect(draft).toMatchObject({
    type: "spend",
    name: "PETRO-CANADA TORONTO",
    conditions: [
      { field: "description", operator: "contains", value: "PETRO-CANADA TORONTO", value_to: "" },
    ],
    scope_accounts: ["bank-1"],
  });
});

it("pre-fill: payee first; money in is a receive rule", () => {
  const href = ruleFromLineHref("o", { amount: 250, payee: "Shopify Payments", description: "X" });
  const draft = prefillDraft(Object.fromEntries(new URL(href, "http://x").searchParams));
  expect(draft.type).toBe("receive");
  expect(draft.conditions).toEqual([
    { field: "payee", operator: "contains", value: "Shopify Payments", value_to: "" },
  ]);
  expect(keywordOf("Interac e-Transfer REF 99881 Jane")).toBe("Interac e-Transfer Jane");
  expect(hasPrefill({ type: "spend" })).toBe(false);
});
