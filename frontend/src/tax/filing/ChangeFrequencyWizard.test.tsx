import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { serveJson } from "@/banking/fixtures";
import { renderWithIntl } from "@/test/intl";

import type { FilingDiff } from "./api";
import { ChangeFrequencyWizard } from "./ChangeFrequencyWizard";
import { BASE, ORG, REG, SWITCH_DIFF } from "./fixtures";

/**
 * G-03a-T19 — the wizard previews before saving and confirms exactly the previewed change; a
 * refusal sends the person back to the step it is about, in words.
 */
afterEach(() => vi.unstubAllGlobals());

interface Call {
  url: string;
  body: Record<string, unknown>;
}

function serve(preview: { status?: number; body: unknown }) {
  const calls: Call[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(
      serveJson((url, init) => {
        calls.push({ url, body: JSON.parse(String(init?.body ?? "{}")) });
        if (url.endsWith("/preview")) return preview;
        return { status: 201, body: SWITCH_DIFF };
      }),
    ),
  );
  return calls;
}

function open(onSaved: (r: FilingDiff) => void = () => {}) {
  renderWithIntl(
    <ChangeFrequencyWizard
      org={ORG}
      registration={REG}
      open
      onOpenChange={() => {}}
      current="quarterly"
      onSaved={onSaved}
    />,
  );
  return screen.getByRole("dialog", { name: "Change filing frequency" });
}

async function toPreview(dialog: HTMLElement, ref = "2026-GST-48812") {
  const user = userEvent.setup();
  expect(within(dialog).getByRole("radio", { name: "Monthly" })).toBeChecked(); // not the current
  await user.click(within(dialog).getByRole("button", { name: "Next" }));
  expect(within(dialog).getByRole("button", { name: "Next" })).toBeDisabled();
  await user.type(within(dialog).getByLabelText(/Takes effect on/), "2026-10-01");
  await user.click(within(dialog).getByRole("button", { name: "Next" }));
  if (ref) await user.type(within(dialog).getByLabelText(/approval reference/), ref);
  await user.click(within(dialog).getByRole("button", { name: "Preview" }));
  return user;
}

it("previews the diff, then confirm saves exactly the previewed change", async () => {
  const calls = serve({ body: SWITCH_DIFF });
  const saved: FilingDiff[] = [];
  const dialog = open((result) => saved.push(result));
  const user = await toPreview(dialog);
  const diff = await within(dialog).findByRole("list", {
    name: "Periods removed, added and shortened",
  });
  expect([...diff.querySelectorAll("[data-diff]")].map((li) => li.textContent)).toEqual([
    "Removed: 1 Oct 2026 – 31 Dec 2026",
    "Added: 1 Oct 2026 – 31 Oct 2026 · Regular",
    "Added: 1 Nov 2026 – 30 Nov 2026 · Regular",
    "Added: 1 Dec 2026 – 31 Dec 2026 · Regular",
  ]);
  expect(within(dialog).getByText(/1 period removed, 3 added, none shortened/)).toBeVisible();
  expect(within(dialog).getByRole("status")).toHaveTextContent("isn't the start of your financial");
  expect(calls).toHaveLength(1);
  expect(calls[0]!.url).toBe(`${BASE}/preview`);
  await user.click(within(dialog).getByRole("button", { name: "Confirm change" }));
  expect(calls[1]!.url).toBe(`${BASE}/cycles`);
  const { action, ...previewed } = calls[0]!.body;
  expect(action).toBe("switch");
  expect(calls[1]!.body).toEqual(previewed); // the same change, nothing else
  expect(previewed).toMatchObject({
    frequency: "monthly",
    effective_from: "2026-10-01",
    approval_ref: "2026-GST-48812",
  });
  expect(saved).toEqual([SWITCH_DIFF]);
});

it("a mid-year switch without the reference goes back to the approval step", async () => {
  const calls = serve({
    status: 422,
    body: {
      code: "tax.filing.approval_required",
      detail:
        "A change during the financial year needs the CRA or Revenu Québec approval reference.",
    },
  });
  const dialog = open();
  await toPreview(dialog, "");
  expect(await within(dialog).findByRole("alert")).toHaveTextContent("needs the CRA");
  expect(within(dialog).getByLabelText(/approval reference/)).toBeVisible();
  expect(within(dialog).queryByRole("button", { name: "Confirm change" })).toBeNull();
  expect(calls).toHaveLength(1); // nothing saved
});

it("a date inside a filed period goes back to the date step", async () => {
  serve({
    status: 422,
    body: { code: "tax.filing.inside_filed", detail: "2026-10-01 is inside the filed period." },
  });
  const dialog = open();
  await toPreview(dialog);
  expect(await within(dialog).findByRole("alert")).toHaveTextContent("inside the filed period");
  expect(within(dialog).getByLabelText(/Takes effect on/)).toHaveValue("2026-10-01");
});
