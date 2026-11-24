import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { serveJson } from "@/banking/fixtures";
import { renderWithIntl } from "@/test/intl";

import { CreateMenu } from "./CreateMenu";

/**
 * F-01-T13 — the top bar's "+" menu: Spend money, Receive money and Add bank account with their
 * shortcuts, for someone with the banking permissions; keyboard: ↓ opens, arrows move, Esc closes
 * and returns focus.
 */
afterEach(() => vi.unstubAllGlobals());

function serve(permissions: string[]) {
  vi.stubGlobal(
    "fetch",
    vi.fn(
      serveJson((url) =>
        url.endsWith("/my-permissions") ? { body: { permissions } } : { status: 404, body: {} },
      ),
    ),
  );
}

it("lists the banking actions with their shortcuts and links", async () => {
  serve(["accounting.banking.transact", "accounting.banking.manage"]);
  renderWithIntl(<CreateMenu org="acme" />);
  await userEvent.click(screen.getByRole("button", { name: "Create" }));
  const spend = await screen.findByRole("menuitem", { name: /Spend money/ });
  expect(spend).toHaveAttribute("href", "/o/acme/banking/spend");
  expect(spend).toHaveTextContent("N S");
  expect(screen.getByRole("menuitem", { name: /Receive money/ })).toHaveAttribute(
    "href",
    "/o/acme/banking/receive",
  );
  const add = screen.getByRole("menuitem", { name: /Add bank account/ });
  expect(add).toHaveAttribute("href", "/o/acme/banking?add=1");
  expect(add).toHaveTextContent("N A");
  // Not permitted: not offered.
  expect(screen.queryByRole("menuitem", { name: /manual journal/ })).toBeNull();
});

it("is a keyboard menu: ↓ opens on the first item, arrows wrap, Esc closes", async () => {
  serve(["accounting.banking.transact"]);
  renderWithIntl(<CreateMenu org="acme" />);
  const button = screen.getByRole("button", { name: "Create" });
  button.focus();
  await userEvent.keyboard("{ArrowDown}");
  expect(button).toHaveAttribute("aria-expanded", "true");
  const spend = await screen.findByRole("menuitem", { name: /Spend money/ });
  await waitFor(() => expect(spend).toHaveFocus());
  await userEvent.keyboard("{ArrowDown}");
  expect(screen.getByRole("menuitem", { name: /Receive money/ })).toHaveFocus();
  await userEvent.keyboard("{ArrowDown}");
  expect(spend).toHaveFocus();
  await userEvent.keyboard("{Escape}");
  expect(screen.queryByRole("menu")).toBeNull();
  expect(button).toHaveFocus();
});
