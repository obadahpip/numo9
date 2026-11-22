import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { renderWithIntl } from "@/test/intl";

import { DISMISS_DAYS, dismiss, isDismissed } from "./dismissal";
import { bankAccount, ORG, serveJson } from "./fixtures";
import { NoBankPrompt } from "./NoBankPrompt";

/**
 * F-01-T12 — no-bank prompt: shown while the organisation has no bank account, links to the
 * add-account sheet, hidden for 7 days per person when dismissed, back afterwards; never shown
 * when an account exists; never blocks (it is only a banner).
 */
afterEach(() => {
  vi.unstubAllGlobals();
  window.localStorage.clear();
});

function serve(results: unknown[]) {
  vi.stubGlobal("fetch", vi.fn(serveJson(() => ({ body: { results } }))));
}

it("shows the prompt with no account and links to the add-account sheet", async () => {
  serve([]);
  renderWithIntl(<NoBankPrompt org={ORG} />);
  expect(await screen.findByRole("heading", { name: "Add your first bank account" })).toBeVisible();
  expect(screen.getByRole("link", { name: "Add account" })).toHaveAttribute(
    "href",
    `/o/${ORG}/banking?add=1`,
  );
});

it("stays hidden when the organisation has an account", async () => {
  serve([bankAccount()]);
  const { container } = renderWithIntl(<NoBankPrompt org={ORG} />);
  await new Promise((resolve) => setTimeout(resolve, 20));
  expect(container.querySelector("[data-no-bank-prompt]")).toBeNull();
});

it("hides for 7 days when dismissed, then comes back", async () => {
  serve([]);
  const { unmount } = renderWithIntl(<NoBankPrompt org={ORG} />);
  await userEvent.click(await screen.findByRole("button", { name: "Hide for 7 days" }));
  expect(screen.queryByRole("heading", { name: "Add your first bank account" })).toBeNull();
  unmount();
  expect(isDismissed(ORG)).toBe(true);
  const day = 24 * 60 * 60 * 1000;
  expect(isDismissed(ORG, Date.now() + (DISMISS_DAYS - 1) * day)).toBe(true);
  expect(isDismissed(ORG, Date.now() + DISMISS_DAYS * day + 1)).toBe(false);
  dismiss(ORG, Date.now() - DISMISS_DAYS * day - 1);
  renderWithIntl(<NoBankPrompt org={ORG} />);
  expect(await screen.findByRole("heading", { name: "Add your first bank account" })).toBeVisible();
  expect(isDismissed("other-org")).toBe(false);
});
