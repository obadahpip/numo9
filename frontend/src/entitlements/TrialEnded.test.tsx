import { QueryClient } from "@tanstack/react-query";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { Gated } from "@/catalogue/Gated";
import { entitlementsBody } from "@/test/entitlements";
import { renderWithIntl } from "@/test/intl";

import { expectNoAxeViolations } from "../../../packages/ui/src/test/axe";
import { ReadOnlyNotice } from "./ReadOnlyNotice";
import { EntitlementsProvider } from "./store";

/**
 * U-05-T11 — trial-ended read-only experience (banner, export button, subscribe CTA). Acceptance:
 * every list stays readable (read keys allowed) while every change shows the locked panel that says
 * why — the trial ended — with "Choose a package" for the owner; the banner keeps the data
 * promise, offers the export and the subscribe call to action; not a wall.
 */

const ENDED = entitlementsBody({
  mode: "read_only",
  reason: "trial_ended",
  status: "read_only",
  since: "2026-11-14T04:59:59+00:00",
  time_zone: "America/Toronto",
  features: ["accounting.contacts.read", "accounting.journals.read"],
});

function render(body = ENDED) {
  const posts: string[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const json = (data: unknown, status = 200) =>
        new Response(JSON.stringify(data), {
          status,
          headers: { "Content-Type": "application/json" },
        });
      if (url.endsWith("/csrf")) return json({ csrfToken: "t" });
      if (url.endsWith("/billing/export") && init?.method === "POST") {
        posts.push(url);
        return json({ job: "j1", status: "queued" }, 202);
      }
      return json(body);
    }),
  );
  const view = renderWithIntl(
    <EntitlementsProvider
      org="acme"
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <ReadOnlyNotice />
      <Gated feature="accounting.contacts.read">
        <p>Contact list</p>
      </Gated>
      <Gated feature="accounting.contacts.write">
        <p>New contact form</p>
      </Gated>
    </EntitlementsProvider>,
  );
  return { ...view, posts };
}

afterEach(() => vi.unstubAllGlobals());

it("lists stay readable; changes show the trial-ended locked panel", async () => {
  const { container } = render();
  expect(await screen.findByText("Contact list")).toBeVisible();
  expect(screen.queryByText("New contact form")).toBeNull();
  expect(screen.getByRole("heading", { name: "This organisation is read-only" })).toBeVisible();
  expect(
    screen.getByText(/The free trial ended\. You can still see and export everything/),
  ).toBeVisible();
  expect(screen.getAllByRole("link", { name: "Choose a package" })[0]).toHaveAttribute(
    "href",
    "/o/acme/settings/subscription",
  );
  await expectNoAxeViolations(container);
});

it("the banner keeps the data promise and starts the export", async () => {
  const user = userEvent.setup();
  const { posts } = render();
  const banner = await screen.findByRole("region", { name: "Organisation status" });
  expect(banner).toHaveTextContent("read-only since 13 Nov 2026: the free trial ended.");
  expect(banner).toHaveTextContent("Everything you entered during the trial is kept.");
  await user.click(screen.getByRole("button", { name: "Export your data" }));
  await waitFor(() => expect(posts).toEqual(["/api/v1/o/acme/billing/export"]));
  expect(await screen.findByRole("status")).toHaveTextContent("The export has started.");
});

it("everyone but the owner is told to ask the owner, no export button", async () => {
  render(entitlementsBody({ ...ENDED, viewer: { can_change_package: false } }));
  const banner = await screen.findByRole("region", { name: "Organisation status" });
  expect(banner).toHaveTextContent("Ask the organisation's owner to choose a package.");
  expect(screen.queryByRole("button", { name: "Export your data" })).toBeNull();
});
