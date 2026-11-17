import { screen, within } from "@testing-library/react";
import { vi } from "vitest";

import { renderWithIntl } from "@/test/intl";

import { expectNoAxeViolations } from "../../../../packages/ui/src/test/axe";
import { ConsoleFrame } from "./ConsoleFrame";

/**
 * U-06-T02 — platform shell layout + route guard. Acceptance: a non-platform user gets the 404
 * page (no leak: nothing of the console renders); a platform user without 2FA is sent to set it
 * up; staff see the console navigation with only the areas their permissions open.
 */

function answer(status: number, body: unknown) {
  vi.stubGlobal(
    "fetch",
    vi.fn(
      async () =>
        new Response(JSON.stringify(body), {
          status,
          headers: { "Content-Type": "application/json" },
        }),
    ),
  );
}

afterEach(() => vi.unstubAllGlobals());

const page = (
  <ConsoleFrame current="/console/organisations">
    <h1>Organisations</h1>
  </ConsoleFrame>
);

it("shows the 404 page to anyone who isn't platform staff", async () => {
  answer(404, { detail: "Not found.", code: "not_found" });
  const { container } = renderWithIntl(page);
  expect(await screen.findByRole("heading", { name: "We can't find that page" })).toBeVisible();
  expect(screen.queryByRole("navigation", { name: "Platform console" })).toBeNull();
  expect(screen.queryByText("Organisations")).toBeNull();
  await expectNoAxeViolations(container);
});

it("sends a platform user without 2FA to set it up", async () => {
  answer(403, { detail: "…", code: "auth.two_factor_required" });
  renderWithIntl(page);
  expect(
    await screen.findByRole("heading", { name: "Turn on two-factor authentication" }),
  ).toBeVisible();
  expect(screen.getByRole("link", { name: "Set it up" })).toHaveAttribute(
    "href",
    "/account/security",
  );
  expect(screen.queryByText("Organisations")).toBeNull();
});

it("shows the console navigation by permission, current area marked", async () => {
  answer(200, {
    id: "u1",
    name: "Priya",
    email: "priya@numo9.ca",
    permissions: ["platform.console.view", "platform.jobs.view"],
  });
  const { container } = renderWithIntl(page);
  const nav = await screen.findByRole("navigation", { name: "Platform console" });
  const links = within(nav)
    .getAllByRole("link")
    .map((link) => link.textContent);
  expect(links).toEqual(["Metrics", "Practices", "Organisations", "Jobs"]);
  expect(within(nav).getByRole("link", { name: "Organisations" })).toHaveAttribute(
    "aria-current",
    "page",
  );
  expect(screen.getByRole("heading", { name: "Organisations" })).toBeVisible();
  await expectNoAxeViolations(container);
});
