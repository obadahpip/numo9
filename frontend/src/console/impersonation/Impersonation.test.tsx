import { act, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { resetCsrfToken } from "@/auth/client";
import { renderWithIntl } from "@/test/intl";

import { expectNoAxeViolations } from "../../../../packages/ui/src/test/axe";
import type { ImpersonationSession } from "./api";
import { countdown, ImpersonationBar } from "./ImpersonationBar";
import { StartImpersonationDialog } from "./StartImpersonationDialog";

/**
 * U-06-T11 — impersonation UI: the start modal (reason, time limit), the red bar with its
 * countdown and "End session". Acceptance: the bar is visible on every page (it lives in the app
 * shell: see AppShell's test) while a session is open, and the countdown reaches the end.
 */

const SESSION: ImpersonationSession = {
  id: "s-1",
  actor: { id: "a", name: "Sam Support", email: "sam@numo9.ca" },
  user: { id: "u", name: "Dana Lee", email: "dana@maple.ca" },
  organisation: { id: "org-1", name: "Maple Leaf Supply" },
  reason: "Ticket #42",
  started_at: "2026-11-18T15:00:00Z",
  expires_at: "2026-11-18T15:30:00Z",
  ended_at: null,
  end_reason: "",
};

type Handler = (url: string, init?: RequestInit) => { status?: number; body: unknown };
const calls: { url: string; init?: RequestInit }[] = [];

function serve(handler: Handler) {
  calls.length = 0;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      calls.push({ url, init });
      if (url.includes("auth/csrf"))
        return new Response(JSON.stringify({ csrfToken: "t" }), {
          headers: { "Content-Type": "application/json", "Set-Cookie": "csrftoken=t" },
        });
      const { status = 200, body } = handler(url, init);
      return new Response(JSON.stringify(body), {
        status,
        headers: { "Content-Type": "application/json" },
      });
    }),
  );
}

beforeEach(() => resetCsrfToken());

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

it("formats the countdown", () => {
  expect(countdown(29 * 60_000 + 59_000)).toBe("29:59");
  expect(countdown(2 * 3_600_000)).toBe("2:00:00");
  expect(countdown(-5)).toBe("00:00");
});

it("shows the red bar with a countdown and ends the session", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true, now: new Date("2026-11-18T15:05:00Z") });
  serve((url) =>
    url.endsWith("/end")
      ? { body: { session: null, ended: { ...SESSION, end_reason: "ended" } } }
      : { body: { session: SESSION, ended: null } },
  );
  const navigate = vi.fn();
  const { container } = renderWithIntl(<ImpersonationBar navigate={navigate} />);
  const bar = await screen.findByRole("region", { name: "Support session" });
  expect(bar).toHaveTextContent("You're signed in as Dana Lee in Maple Leaf Supply");
  expect(within(bar).getByRole("timer")).toHaveTextContent("25:00 left");
  await act(() => vi.advanceTimersByTimeAsync(61_000));
  expect(within(bar).getByRole("timer")).toHaveTextContent("23:59 left");
  await expectNoAxeViolations(container);
  await userEvent.click(within(bar).getByRole("button", { name: "End session" }));
  expect(calls.some((c) => c.url.endsWith("/impersonation/end") && c.init?.method === "POST")).toBe(
    true,
  );
  expect(navigate).toHaveBeenCalledWith("/console/organisations/org-1");
});

it("says the session ended when the time limit is reached", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true, now: new Date("2026-11-18T15:29:58Z") });
  let first = true;
  serve(() => {
    const body = first
      ? { session: SESSION, ended: null }
      : { session: null, ended: { ...SESSION, end_reason: "expired" } };
    first = false;
    return { body };
  });
  renderWithIntl(<ImpersonationBar />);
  await screen.findByRole("region", { name: "Support session" });
  await act(() => vi.advanceTimersByTimeAsync(3_000));
  expect(await screen.findByText("Your session as Dana Lee has ended")).toBeVisible();
  expect(screen.getByRole("link", { name: "Back to the console" })).toHaveAttribute(
    "href",
    "/console/organisations/org-1",
  );
});

it("renders nothing outside a session", async () => {
  serve(() => ({ body: { session: null, ended: null } }));
  const { container } = renderWithIntl(<ImpersonationBar />);
  await act(async () => {});
  expect(container).toBeEmptyDOMElement();
});

it("starts a session with a reason and a time limit", async () => {
  serve((url, init) =>
    init?.method === "POST"
      ? { status: 201, body: SESSION }
      : { body: { session: null, ended: null } },
  );
  const navigate = vi.fn();
  renderWithIntl(
    <StartImpersonationDialog
      organisation={{ id: "org-1", name: "Maple Leaf Supply" }}
      user={{ id: "u", name: "Dana Lee" }}
      open
      onClose={() => {}}
      navigate={navigate}
    />,
  );
  const dialog = await screen.findByRole("dialog", { name: "Sign in as Dana Lee" });
  expect(within(dialog).getByLabelText("Time limit")).toHaveValue("30");
  await userEvent.type(within(dialog).getByLabelText("Reason"), "Ticket #42");
  await userEvent.selectOptions(within(dialog).getByLabelText("Time limit"), "60");
  await userEvent.click(within(dialog).getByRole("button", { name: "Start session" }));
  const post = calls.find((c) => c.init?.method === "POST" && c.url.endsWith("/impersonation"));
  expect(JSON.parse(String(post?.init?.body))).toEqual({
    organisation: "org-1",
    user: "u",
    reason: "Ticket #42",
    minutes: 60,
  });
  expect(navigate).toHaveBeenCalledWith("/o/org-1/home");
});

it("shows the API's refusal in the dialog", async () => {
  serve(() => ({
    status: 400,
    body: { code: "impersonation.reason_required", detail: "Say why you need to sign in." },
  }));
  renderWithIntl(
    <StartImpersonationDialog
      organisation={{ id: "org-1", name: "Maple" }}
      user={{ id: "u", name: "Dana Lee" }}
      open
      onClose={() => {}}
    />,
  );
  await userEvent.click(await screen.findByRole("button", { name: "Start session" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Say why you need to sign in.");
});
