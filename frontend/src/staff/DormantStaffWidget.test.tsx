import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { resetCsrfToken } from "@/auth/client";
import { renderWithIntl } from "@/test/intl";

import { expectNoAxeViolations } from "../../../packages/ui/src/test/axe";
import { DormantStaffWidget } from "./DormantStaffWidget";

/** V-05-T06 — the dormant-staff dashboard widget with one-click suspend. */

function serve(status: number, body: unknown) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      const json = (data: unknown, code = 200) =>
        new Response(JSON.stringify(data), {
          status: code,
          headers: { "Content-Type": "application/json" },
        });
      if (url.includes("csrf")) return json({ csrfToken: "t" });
      if (url.includes("/suspend")) return json({ status: "suspended" });
      return json(body, status);
    }),
  );
}

beforeEach(() => resetCsrfToken());
afterEach(() => vi.unstubAllGlobals());

it("lists dormant staff and suspends in one click", async () => {
  serve(200, {
    dormant_days: 60,
    staff: [
      {
        id: "u1",
        name: "Lina Roy",
        email: "lina@cpa.ca",
        role: "reviewer",
        last_login: null,
        days: 62,
      },
    ],
  });
  const { container } = renderWithIntl(<DormantStaffWidget practice="p" />);
  expect(await screen.findByRole("heading", { name: "Dormant staff" })).toBeVisible();
  expect(screen.getByText("Lina Roy — 62 days without signing in")).toBeVisible();
  await expectNoAxeViolations(container);
  await userEvent.click(screen.getByRole("button", { name: "Suspend access for Lina Roy" }));
  expect(await screen.findByText("Lina Roy's access is suspended.")).toBeVisible();
  expect(screen.queryByRole("heading", { name: "Dormant staff" })).toBeNull();
});

it("renders nothing for someone who doesn't manage staff", async () => {
  serve(403, { code: "permission.denied", detail: "No." });
  const { container } = renderWithIntl(<DormantStaffWidget practice="p" />);
  await new Promise((resolve) => setTimeout(resolve, 20));
  expect(container).toBeEmptyDOMElement();
});
