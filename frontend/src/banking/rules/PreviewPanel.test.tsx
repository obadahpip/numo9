import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { renderWithIntl } from "@/test/intl";

import { expectNoAxeViolations } from "../../../../packages/ui/src/test/axe";
import { serveJson } from "../fixtures";
import type { PreviewResult, RuleInput } from "./api";
import { PreviewPanel } from "./PreviewPanel";

/**
 * F-04-T13 — preview panel: the affected historical lines and the shadowing rules (the
 * shadowed-by rule name). The e2e check runs in e2e/bank-rules-builder.spec.ts.
 */
const RULE: RuleInput = {
  type: "spend",
  name: "Fuel",
  match_mode: "all",
  conditions: [{ field: "description", operator: "contains", value: "PETRO", value_to: "" }],
  allocations: [],
};

const line = (id: string, description: string, amount: string) => ({
  id,
  date: "2026-06-10",
  amount,
  payee: "",
  description,
  reference: "",
  bank_account: { id: "b1", name: "TD Chequing" },
});

const RESULT: PreviewResult = {
  since: "2026-03-12",
  days: 90,
  applies: 1,
  shadowed: 1,
  truncated: false,
  rows: [
    {
      line: line("l1", "PETRO-CANADA 12", "-45.00"),
      outcome: "applies",
      shadowed_by: null,
      also_matches: [{ id: "r9", name: "Any card spend" }],
    },
    {
      line: line("l2", "PETRO big fill", "-150.00"),
      outcome: "shadowed",
      shadowed_by: { id: "r1", name: "Big fuel" },
      also_matches: [],
    },
  ],
};

afterEach(() => vi.unstubAllGlobals());

it("lists the affected lines and names the shadowing rule", async () => {
  const bodies: unknown[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(
      serveJson((_url, init) => {
        bodies.push(JSON.parse(String(init?.body ?? "{}")));
        return { body: RESULT };
      }),
    ),
  );
  const { container } = renderWithIntl(<PreviewPanel org="refined" rule={RULE} ready delay={0} />);
  expect(await screen.findByText("Shadowed by Big fuel")).toBeVisible();
  expect(screen.getByText("Coded by this rule")).toBeVisible();
  expect(screen.getByText("Also matches Any card spend (lower priority)")).toBeVisible();
  expect(
    screen.getByText("1 line would be coded by this rule; 1 is taken by a higher rule."),
  ).toBeVisible();
  expect(screen.getByText("-$150.00")).toBeVisible();
  expect(bodies[0]).toMatchObject({ days: 90, id: null, rule: { allocations: [] } });
  await expectNoAxeViolations(container);
});

it("waits for complete conditions and shows a refusal", async () => {
  const user = userEvent.setup();
  vi.stubGlobal(
    "fetch",
    vi.fn(
      serveJson(() => ({
        status: 400,
        body: { code: "banking.rule.regex_slow", detail: "This pattern takes too long." },
      })),
    ),
  );
  const { rerender } = renderWithIntl(
    <PreviewPanel org="refined" rule={RULE} ready={false} delay={0} />,
  );
  expect(screen.getByRole("button", { name: "Run the test" })).toBeDisabled();
  expect(
    screen.getByText("Complete the conditions to see which lines the rule matches."),
  ).toBeVisible();
  rerender(<PreviewPanel org="refined" rule={RULE} ready delay={60_000} />);
  await user.click(screen.getByRole("button", { name: "Run the test" }));
  expect(await screen.findByText("This pattern takes too long.")).toBeVisible();
});
