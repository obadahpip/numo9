import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { renderWithIntl } from "@/test/intl";

import { expectNoAxeViolations } from "../../../../packages/ui/src/test/axe";
import { serveJson } from "../fixtures";
import { RevertAutoCodedAction } from "./RevertAutoCodedAction";

/**
 * F-04-T15 (UI) — revert an auto-coded line: asks once, calls the revert endpoint, reports the
 * line Uncoded again; refusals (a locked period) are shown. The ledger side (journal reversed,
 * GL nets to 0) is tested on the real API in backend/tests/test_bank_rule_revert.py.
 */
afterEach(() => vi.unstubAllGlobals());

const LINE = { id: "line-1", auto_coded: true, applied_rule: { id: "r1", name: "Fuel" } };

it("reverts after confirmation", async () => {
  const user = userEvent.setup();
  const urls: string[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(
      serveJson((url) => {
        urls.push(url);
        return {
          body: { line: "line-1", status: "uncoded", auto_coded: false, applied_rule: null },
        };
      }),
    ),
  );
  const onReverted = vi.fn();
  const { container } = renderWithIntl(
    <RevertAutoCodedAction org="refined" line={LINE} onReverted={onReverted} />,
  );
  await user.click(screen.getByRole("button", { name: "Revert auto-coding" }));
  expect(
    screen.getByText(
      "Revert the coding by Fuel? The journal is reversed and the line goes back to Uncoded.",
    ),
  ).toBeVisible();
  await expectNoAxeViolations(container);
  await user.click(screen.getByRole("button", { name: "Revert" }));
  expect(await screen.findByRole("status")).toHaveTextContent(
    "Reverted: the line is uncoded again.",
  );
  expect(urls.at(-1)).toBe("/api/v1/o/refined/bank-rules/lines/line-1/revert");
  expect(onReverted).toHaveBeenCalledWith(expect.objectContaining({ status: "uncoded" }));
  expect(screen.queryByRole("button", { name: "Revert auto-coding" })).toBeNull();
});

it("shows a refusal and hides itself on lines not auto-coded", async () => {
  const user = userEvent.setup();
  vi.stubGlobal(
    "fetch",
    vi.fn(
      serveJson(() => ({
        status: 409,
        body: { code: "lock.violation", detail: "The Bank lock date is 2026-06-30." },
      })),
    ),
  );
  const { unmount } = renderWithIntl(<RevertAutoCodedAction org="refined" line={LINE} />);
  await user.click(screen.getByRole("button", { name: "Revert auto-coding" }));
  await user.click(screen.getByRole("button", { name: "Revert" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("The Bank lock date is 2026-06-30.");
  unmount();
  const { container } = renderWithIntl(
    <RevertAutoCodedAction org="refined" line={{ id: "l2", auto_coded: false }} />,
  );
  expect(container).toBeEmptyDOMElement();
});
