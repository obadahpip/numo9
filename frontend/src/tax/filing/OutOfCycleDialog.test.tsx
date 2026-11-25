import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { serveJson } from "@/banking/fixtures";
import { renderWithIntl } from "@/test/intl";

import type { FilingDiff } from "./api";
import { BASE, CUSTOM_DIFF, ORG, REG } from "./fixtures";
import { OutOfCycleDialog } from "./OutOfCycleDialog";

/**
 * G-03a-T20 — out-of-cycle period: the overlap preview and the realignment in words before
 * saving; an overlap with a filed period is refused with the period named.
 */
afterEach(() => vi.unstubAllGlobals());

function serve(preview: { status?: number; body: unknown }) {
  const calls: { url: string; body: Record<string, unknown> }[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(
      serveJson((url, init) => {
        calls.push({ url, body: JSON.parse(String(init?.body ?? "{}")) });
        return url.endsWith("/preview") ? preview : { status: 201, body: CUSTOM_DIFF };
      }),
    ),
  );
  return calls;
}

function open(onSaved: (r: FilingDiff) => void = () => {}) {
  renderWithIntl(
    <OutOfCycleDialog
      org={ORG}
      registration={REG}
      open
      onOpenChange={() => {}}
      onSaved={onSaved}
    />,
  );
  return screen.getByRole("dialog", { name: "Add an out-of-cycle period" });
}

it("previews the overlap and the realignment, then adds the previewed period", async () => {
  const calls = serve({ body: CUSTOM_DIFF });
  const saved: FilingDiff[] = [];
  const dialog = open((r) => saved.push(r));
  const user = userEvent.setup();
  await user.type(within(dialog).getByLabelText("Starts"), "2026-10-01");
  await user.type(within(dialog).getByLabelText("Ends"), "2026-11-15");
  await user.type(within(dialog).getByLabelText(/Why/), "Year-end change");
  await user.click(within(dialog).getByRole("button", { name: "Preview" }));
  expect(await within(dialog).findByText("No filed period overlaps these dates.")).toBeVisible();
  expect(dialog.querySelector("[data-realign]")).toHaveTextContent(
    "Regular periods then restart on 16 Nov 2026, the day after it ends.",
  );
  expect([...dialog.querySelectorAll("[data-diff]")].map((li) => li.textContent)).toEqual([
    "Removed: 1 Oct 2026 – 31 Dec 2026",
    "Added: 1 Oct 2026 – 15 Nov 2026 · Out of cycle",
    "Added: 16 Nov 2026 – 31 Dec 2026 · Stub",
  ]);
  await user.click(within(dialog).getByRole("button", { name: "Add period" }));
  expect(calls.map((c) => c.url)).toEqual([`${BASE}/preview`, `${BASE}/custom-periods`]);
  expect(calls[1]!.body).toEqual({
    start: "2026-10-01",
    end: "2026-11-15",
    note: "Year-end change",
  });
  expect(saved).toEqual([CUSTOM_DIFF]);
});

it("refuses an overlap with a filed period, naming it, and editing clears the preview", async () => {
  const calls = serve({
    status: 422,
    body: {
      code: "tax.filing.custom_overlaps_filed",
      detail: "The period overlaps the filed period 2026-01-01 – 2026-03-31.",
    },
  });
  const dialog = open();
  const user = userEvent.setup();
  await user.click(within(dialog).getByRole("button", { name: "Preview" }));
  expect(within(dialog).getByRole("alert")).toHaveTextContent("must end on or after");
  expect(calls).toHaveLength(0);
  await user.type(within(dialog).getByLabelText("Starts"), "2026-03-01");
  await user.type(within(dialog).getByLabelText("Ends"), "2026-04-15");
  await user.click(within(dialog).getByRole("button", { name: "Preview" }));
  expect(await within(dialog).findByRole("alert")).toHaveTextContent(
    "overlaps the filed period 2026-01-01 – 2026-03-31",
  );
  expect(within(dialog).queryByRole("button", { name: "Add period" })).toBeNull();
});
