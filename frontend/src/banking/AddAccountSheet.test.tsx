import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { renderWithIntl } from "@/test/intl";

import { BankingHome } from "./BankingHome";
import { bankAccount, ORG, serveJson } from "./fixtures";

/**
 * F-01-T09 — add-account side-sheet: type with plain-language help, name, institution from the
 * Canadian list (free text allowed), currency; created in one step; the server's refusal shown on
 * the name; success notice "… is ready." with Record a transaction.
 */
afterEach(() => vi.unstubAllGlobals());

it("adds an account in one step and offers to record a transaction", async () => {
  const created = bankAccount({ id: "new-1", display_name: "RBC Visa", type: "credit_card" });
  let list: unknown[] = [];
  const posted: unknown[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(
      serveJson((url, init) => {
        if (init?.method === "POST") {
          posted.push(JSON.parse(String(init.body)));
          list = [created];
          return { status: 201, body: created };
        }
        return { body: { results: list } };
      }),
    ),
  );
  const user = userEvent.setup();
  renderWithIntl(<BankingHome org={ORG} />);
  await screen.findByRole("heading", { name: "No bank account yet" });
  await user.click(screen.getAllByRole("button", { name: "Add account" })[0]!);
  const sheet = await screen.findByRole("dialog", { name: "Add a bank account" });
  expect(sheet).toHaveTextContent("Money you keep at the bank and pay from: a current asset.");
  await user.click(screen.getByRole("radio", { name: "Credit card" }));
  expect(sheet).toHaveTextContent("What you owe on a business card: a current liability.");
  await user.type(screen.getByLabelText("Name"), "RBC Visa");
  await user.type(screen.getByLabelText("Institution"), "RBC Royal Bank");
  await user.type(screen.getByLabelText("Last 4 digits (optional)"), "0042");
  const submits = screen.getAllByRole("button", { name: "Add account" });
  await user.click(submits[submits.length - 1]!);
  expect(await screen.findByText("RBC Visa is ready.")).toBeVisible();
  expect(screen.getByRole("link", { name: "Record a transaction" })).toHaveAttribute(
    "href",
    `/o/${ORG}/banking/spend?account=new-1`,
  );
  expect(posted).toEqual([
    {
      type: "credit_card",
      display_name: "RBC Visa",
      institution: "RBC Royal Bank",
      currency: "CAD",
      account_last4: "0042",
    },
  ]);
  expect(await screen.findByRole("article", { name: "RBC Visa" })).toBeVisible();
});

it("needs a name and shows the server's refusal on it", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(
      serveJson((url, init) =>
        init?.method === "POST"
          ? {
              status: 400,
              body: {
                code: "banking.account.name_taken",
                detail: "There's already an account called “Petty Cash”. Choose another name.",
              },
            }
          : { body: { results: [] } },
      ),
    ),
  );
  const user = userEvent.setup();
  renderWithIntl(<BankingHome org={ORG} />);
  await screen.findByRole("heading", { name: "No bank account yet" });
  await user.click(screen.getAllByRole("button", { name: "Add account" })[0]!);
  await screen.findByRole("dialog", { name: "Add a bank account" });
  const submit = () => {
    const all = screen.getAllByRole("button", { name: "Add account" });
    return user.click(all[all.length - 1]!);
  };
  await submit();
  expect(screen.getByText("Give the account a name.")).toBeVisible();
  await user.type(screen.getByLabelText("Name"), "Petty Cash");
  await submit();
  expect(await screen.findByText(/already an account called “Petty Cash”/)).toBeVisible();
  expect(screen.getByLabelText("Name")).toHaveAttribute("aria-invalid", "true");
});
