import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { renderWithIntl } from "@/test/intl";

import { CashPolicySettings } from "./CashPolicySettings";
import { ORG, serveJson } from "./fixtures";

/**
 * F-07-T08 — Banking settings: the negative-balance policy per account type with its explanation;
 * changing Chequing to Block sends the new rule and says the next posting follows it.
 */
const row = (account_type: string, label: string, standard: string, adviser: string) => ({
  account_type,
  label,
  standard,
  adviser,
  default: { standard, adviser },
  explanation: `${label} explanation`,
});

let saved: unknown[] = [];

function serve() {
  saved = [];
  const policies = [
    row("chequing", "Chequing", "warn", "warn"),
    row("savings", "Savings", "warn", "warn"),
    row("cash", "Cash / petty cash", "block", "warn"),
    row("clearing", "Clearing", "warn", "warn"),
  ];
  vi.stubGlobal(
    "fetch",
    vi.fn(
      serveJson((url, init) => {
        if (url.endsWith("/bank-settings/cash-policies") && init?.method === "PUT") {
          const body = JSON.parse(String(init.body)) as { policies: typeof policies };
          saved.push(body);
          return {
            body: {
              policies: body.policies.map((p) => ({
                ...policies.find((x) => x.account_type === p.account_type),
                ...p,
              })),
              actions: [],
            },
          };
        }
        if (url.endsWith("/bank-settings/cash-policies"))
          return { body: { policies, actions: [] } };
        return { status: 404, body: {} };
      }),
    ),
  );
}

afterEach(() => vi.unstubAllGlobals());

it("lists each type with its explanation and default, and saves a change", async () => {
  serve();
  renderWithIntl(<CashPolicySettings org={ORG} />);
  expect(await screen.findByRole("heading", { name: "Banking settings" })).toBeVisible();
  const cash = await screen.findByRole("row", { name: /Cash \/ petty cash/ });
  expect(cash).toHaveTextContent("Cash / petty cash explanation");
  expect(cash).toHaveTextContent("Default: Block / Warn — ask for a reason");
  expect(within(cash).getByLabelText("Cash / petty cash: everyone else")).toHaveValue("block");

  await userEvent.selectOptions(screen.getByLabelText("Chequing: everyone else"), "block");
  await userEvent.click(screen.getByRole("button", { name: "Save changes" }));
  await waitFor(() => expect(saved).toHaveLength(1));
  expect(saved[0]).toMatchObject({
    policies: expect.arrayContaining([
      { account_type: "chequing", standard: "block", adviser: "warn" },
    ]) as unknown,
  });
  expect(await screen.findByText("Saved. The next posting follows the new rule.")).toBeVisible();
});
