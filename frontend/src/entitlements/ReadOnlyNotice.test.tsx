import { QueryClient } from "@tanstack/react-query";
import { screen } from "@testing-library/react";
import { vi } from "vitest";

import { entitlementsBody, entitlementsFetch } from "@/test/entitlements";
import { renderWithIntl } from "@/test/intl";

import { ReadOnlyNotice } from "./ReadOnlyNotice";
import { EntitlementsProvider } from "./store";

/** U-03-T12 — the read-only notice names the reason and the date, with the owner's action. */
function renderNotice(body = entitlementsBody()) {
  vi.stubGlobal("fetch", entitlementsFetch(body));
  return renderWithIntl(
    <EntitlementsProvider
      org="acme"
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <ReadOnlyNotice />
      <p>loaded</p>
    </EntitlementsProvider>,
  );
}

const READ_ONLY = { mode: "read_only" as const, since: "2026-11-20T05:00:00+00:00" };

afterEach(() => vi.unstubAllGlobals());

describe("ReadOnlyNotice (U-03-T12)", () => {
  it.each([
    ["payment_failed", "the payment failed and the grace period ended."],
    ["trial_ended", "the free trial ended."],
    ["cancelled", "the subscription was cancelled."],
    ["platform", "Numo9 set it read-only."],
  ])("names the reason %s and the date", async (reason, text) => {
    renderNotice(entitlementsBody({ ...READ_ONLY, reason }));
    const notice = await screen.findByRole("region", { name: "Organisation status" });
    expect(notice).toHaveTextContent(
      `This organisation has been read-only since 20 Nov 2026: ${text}`,
    );
    expect(notice).toHaveTextContent("You can still see and export everything.");
    expect(notice).toHaveAttribute("data-read-only-reason", reason);
  });

  it("gives the owner the reactivate link and everyone else the ask-the-owner text", async () => {
    const { unmount } = renderNotice(entitlementsBody({ ...READ_ONLY, reason: "payment_failed" }));
    expect(
      await screen.findByRole("link", { name: "Reactivate the subscription" }),
    ).toHaveAttribute("href", "/o/acme/settings/subscription");
    unmount();
    renderNotice(
      entitlementsBody({
        ...READ_ONLY,
        reason: "payment_failed",
        viewer: { can_change_package: false },
      }),
    );
    const notice = await screen.findByRole("region", { name: "Organisation status" });
    expect(notice).toHaveTextContent("Ask the organisation's owner to reactivate it.");
    expect(screen.queryByRole("link", { name: "Reactivate the subscription" })).toBeNull();
  });

  it("shows the date in the organisation's time zone", async () => {
    renderNotice(
      entitlementsBody({
        ...READ_ONLY,
        reason: "cancelled",
        since: "2026-11-20T03:00:00+00:00", // still 19 Nov in Toronto, 20 Nov in Helsinki
        time_zone: "America/Toronto",
      }),
    );
    expect(await screen.findByRole("region", { name: "Organisation status" })).toHaveTextContent(
      "since 19 Nov 2026",
    );
  });

  it("shows nothing unless the organisation is read-only", async () => {
    renderNotice(entitlementsBody());
    expect(await screen.findByText("loaded")).toBeInTheDocument();
    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(screen.queryByRole("region", { name: "Organisation status" })).toBeNull();
  });
});
