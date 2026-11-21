import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { resetCsrfToken } from "@/auth/client";
import { renderWithIntl } from "@/test/intl";

import { expectNoAxeViolations } from "../../../../packages/ui/src/test/axe";
import type { DemoOverview } from "./api";
import { DemoManagerPanel, FoundingCounterPanel } from "./ConsolePanels";

/** U-06-T13 — founding counter & demo manager panels: the counter shows x/1,000. */
const demos = (): DemoOverview => ({
  seed_version: 1,
  idle_days: 30,
  open: 2,
  purge_soon: 1,
  templates: [{ seed_version: 1, built_at: "2026-11-01T10:00:00Z" }],
  demos: [
    {
      id: "d-1",
      name: "Maple & Pine Supply Co.",
      seed_version: 1,
      created_at: "2026-11-01T10:00:00Z",
      last_active_at: "2026-11-18T15:00:00Z",
      purge_on: "2026-12-19",
      members: 1,
    },
    {
      id: "d-2",
      name: "Idle demo",
      seed_version: 1,
      created_at: "2026-10-20T10:00:00Z",
      last_active_at: null,
      purge_on: "2026-11-20",
      members: 0,
    },
  ],
});

let purgeStatus = 204;
const posts: string[] = [];

function serve(founding: Record<string, unknown> = { cap: 1000, allocated: 427, remaining: 573 }) {
  posts.length = 0;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const json = (payload: unknown, status = 200) =>
        new Response(status === 204 ? null : JSON.stringify(payload), {
          status,
          headers: { "Content-Type": "application/json" },
        });
      if (url.includes("auth/csrf")) return json({ csrfToken: "t" });
      if (init?.method === "POST") {
        posts.push(url);
        return json({ detail: "no" }, purgeStatus);
      }
      if (url.includes("/platform/founding")) return json({ ...founding, slots: [] });
      return json(demos());
    }),
  );
}

beforeEach(() => {
  resetCsrfToken();
  purgeStatus = 204;
});

it("shows the founding counter as x/1,000 with a link", async () => {
  serve();
  const { container } = renderWithIntl(<FoundingCounterPanel />);
  const label = await screen.findByText("427 of 1,000 founding places given");
  expect(label.closest("[data-founding-counter]")).toHaveTextContent(/^427\/1,000/);
  expect(screen.getByText("573 left")).toBeVisible();
  expect(screen.getByRole("link", { name: "See founding places" })).toHaveAttribute(
    "href",
    "/console/founding",
  );
  await expectNoAxeViolations(container);
});

it("says when the offer is complete", async () => {
  serve({ cap: 1000, allocated: 1000, remaining: 0 });
  renderWithIntl(<FoundingCounterPanel />);
  expect(await screen.findByText("Offer complete")).toBeVisible();
});

it("lists the open demos and purges one after confirmation", async () => {
  serve();
  const user = userEvent.setup();
  const { container } = renderWithIntl(<DemoManagerPanel />);
  expect(
    await screen.findByText("2 demos open · 1 purged within 7 days · seed version 1"),
  ).toBeVisible();
  const rows = within(screen.getByRole("table")).getAllByRole("row").slice(1);
  expect(rows).toHaveLength(2);
  expect(within(rows[1]!).getByText("Never used")).toBeVisible();
  await expectNoAxeViolations(container);
  await user.click(screen.getByRole("button", { name: "Purge now: Idle demo" }));
  const dialog = await screen.findByRole("dialog", { name: "Purge Idle demo now?" });
  await user.click(within(dialog).getByRole("button", { name: "Purge now" }));
  expect(await screen.findByText("Idle demo purged.")).toBeInTheDocument();
  expect(posts).toEqual([expect.stringContaining("/api/v1/platform/demos/d-2/purge")]);
  expect(within(screen.getByRole("table")).getAllByRole("row")).toHaveLength(2);
});

it("explains a refused purge", async () => {
  serve();
  purgeStatus = 403;
  const user = userEvent.setup();
  renderWithIntl(<DemoManagerPanel />);
  await user.click(await screen.findByRole("button", { name: "Purge now: Idle demo" }));
  const dialog = await screen.findByRole("dialog");
  await user.click(within(dialog).getByRole("button", { name: "Purge now" }));
  expect(await within(dialog).findByRole("alert")).toHaveTextContent(
    "The demo wasn't purged. Only platform owners can purge a demo.",
  );
});
