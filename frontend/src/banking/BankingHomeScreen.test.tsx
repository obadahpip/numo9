import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { renderWithIntl } from "@/test/intl";

import { expectNoAxeViolations } from "../../../packages/ui/src/test/axe";
import { BankingHomeScreen } from "./BankingHomeScreen";
import { ACCOUNTS, bankAccount, ORG, serveJson } from "./fixtures";

/**
 * F-01-T08 — banking home: card balance = API ledger balance; liability reads "owed"; optional
 * statement balance; "Not reconciled — optional" chip; empty state with 0 accounts; skeleton
 * while loading; error with retry; archived section with restore.
 */
afterEach(() => vi.unstubAllGlobals());

function serve(...answers: { status?: number; body: unknown }[]) {
  const seen: string[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(
      serveJson((url) => {
        seen.push(url);
        return answers.length > 1 ? answers.shift()! : answers[0]!;
      }),
    ),
  );
  return seen;
}

it("shows one card per account with the ledger balance from the API", async () => {
  const urls = serve({ body: { results: ACCOUNTS } });
  const { container } = renderWithIntl(<BankingHomeScreen org={ORG} />);
  const td = await screen.findByRole("article", { name: "TD Business Chequing" });
  expect(within(td).getByText("$12,450.30")).toBeVisible();
  expect(within(td).getByText("Statement balance $12,500.00 on 30 Jun 2026")).toBeVisible();
  expect(within(td).getByText("Not reconciled — optional")).toBeVisible();
  expect(within(td).getByText(/TD Canada Trust · CAD · •••• 4821/)).toBeVisible();
  expect(within(td).getByRole("link", { name: "TD Business Chequing" })).toHaveAttribute(
    "href",
    `/o/${ORG}/banking/${ACCOUNTS[0]!.id}`,
  );
  const visa = screen.getByRole("article", { name: "Visa Business" });
  expect(within(visa).getByText("$1,200.00 owed")).toBeVisible();
  const petty = screen.getByRole("article", { name: "Petty Cash" });
  expect(within(petty).getByText("-$417.22")).toHaveClass("text-fg-danger");
  expect(within(petty).getByText("No transactions yet")).toBeVisible();
  expect(urls[0]).toBe(`/api/v1/o/${ORG}/bank-accounts?status=all`);
  await expectNoAxeViolations(container);
});

it("shows the empty state with 0 accounts and opens the add-account sheet", async () => {
  serve({ body: { results: [] } });
  const add = vi.fn();
  renderWithIntl(<BankingHomeScreen org={ORG} onAddAccount={add} />);
  expect(await screen.findByRole("heading", { name: "No bank account yet" })).toBeVisible();
  expect(screen.getByText(/No bank feed is needed/)).toBeVisible();
  const buttons = screen.getAllByRole("button", { name: "Add account" });
  await userEvent.click(buttons[buttons.length - 1]!);
  expect(add).toHaveBeenCalledOnce();
});

it("shows skeleton cards while loading", () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(() => new Promise(() => undefined)),
  );
  const { container } = renderWithIntl(<BankingHomeScreen org={ORG} />);
  expect(container.querySelectorAll("[data-skeleton-card]")).toHaveLength(3);
  expect(screen.getByText("Loading bank accounts…")).toBeInTheDocument();
});

it("shows an error with Try again that reloads", async () => {
  serve({ status: 500, body: {} }, { body: { results: [bankAccount()] } });
  renderWithIntl(<BankingHomeScreen org={ORG} />);
  expect(await screen.findByText("Bank accounts couldn't be loaded")).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Try again" }));
  expect(await screen.findByRole("article", { name: "TD Business Chequing" })).toBeVisible();
});

it("keeps archived accounts in their own section with Restore", async () => {
  const old = bankAccount({
    id: "a-old",
    display_name: "Old Savings",
    archived_at: "2026-05-01T00:00:00Z",
  });
  const urls = serve(
    { body: { results: [bankAccount(), old] } },
    { body: old },
    {
      body: { results: [bankAccount(), { ...old, archived_at: null }] },
    },
  );
  renderWithIntl(<BankingHomeScreen org={ORG} />);
  expect(await screen.findByRole("heading", { name: "Archived (1)" })).toBeVisible();
  expect(screen.queryByRole("article", { name: "Old Savings" })).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Show archived accounts" }));
  expect(screen.getByRole("article", { name: "Old Savings" })).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Restore" }));
  expect(await screen.findByText("Old Savings is back in your accounts.")).toBeInTheDocument();
  expect(urls).toContain(`/api/v1/o/${ORG}/bank-accounts/a-old/restore`);
});
