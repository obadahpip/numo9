import { fireEvent, screen } from "@testing-library/react";
import { vi } from "vitest";

import { renderWithIntl } from "@/test/intl";

import { expectNoAxeViolations } from "../../../packages/ui/src/test/axe";
import type { FileAction } from "./api";
import { CreateFromFile } from "./CreateFromFile";

/**
 * A-06-T11 — "create from file" actions. Acceptance: the action list renders with explanations —
 * every registered action is shown; unavailable ones are greyed with their reason linked to the
 * button; available ones open their URL or the handler; loading and failure states.
 */

const PLANNED: FileAction[] = [
  {
    key: "bill",
    label: "Create a bill",
    module: "purchases",
    available: false,
    reason: "Bills arrive with Purchases in Phase 1.",
    url: "",
  },
  {
    key: "expense",
    label: "Create an expense claim",
    module: "purchases",
    available: false,
    reason: "Expense claims arrive with Purchases in Phase 1.",
    url: "",
  },
  {
    key: "asset",
    label: "Create a fixed asset",
    module: "accounting",
    available: false,
    reason: "The fixed asset register arrives in Phase 2.",
    url: "",
  },
];

const RECEIPT: FileAction = {
  key: "receipt",
  label: "Record a receipt",
  module: "banking",
  available: true,
  reason: "",
  url: "/o/acme/banking/receipts/new?document=d1",
};

describe("CreateFromFile (A-06-T11)", () => {
  it("renders every action, unavailable ones with their explanation", () => {
    renderWithIntl(<CreateFromFile org="acme" documentId="d1" actions={PLANNED} />);
    expect(screen.getByRole("heading", { name: "Create from this file" })).toBeInTheDocument();
    for (const action of PLANNED) {
      const button = screen.getByRole("button", { name: action.label });
      expect(button).toHaveAttribute("aria-disabled", "true");
      expect(button).toHaveAccessibleDescription(action.reason);
      expect(screen.getByText(action.reason)).toBeVisible();
    }
  });

  it("opens an available action and ignores clicks on greyed ones", () => {
    const onOpen = vi.fn();
    renderWithIntl(
      <CreateFromFile org="acme" documentId="d1" actions={[...PLANNED, RECEIPT]} onOpen={onOpen} />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Create a bill" }));
    expect(onOpen).not.toHaveBeenCalled();
    const receipt = screen.getByRole("button", { name: "Record a receipt" });
    expect(receipt).not.toHaveAttribute("aria-disabled");
    fireEvent.click(receipt);
    expect(onOpen).toHaveBeenCalledWith(RECEIPT);
  });

  it("loads the actions from the API, and says when it can't", async () => {
    const fetcher = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ results: PLANNED }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      )
      .mockResolvedValueOnce(new Response("{}", { status: 500 }));
    const { unmount } = renderWithIntl(<CreateFromFile org="acme" documentId="d1" />);
    expect(screen.getByText("Loading what this file can become…")).toBeInTheDocument();
    expect(await screen.findByText("Bills arrive with Purchases in Phase 1.")).toBeVisible();
    expect(String(fetcher.mock.calls[0]![0])).toBe("/api/v1/o/acme/files/d1/actions");
    unmount();
    renderWithIntl(<CreateFromFile org="acme" documentId="d2" />);
    expect(await screen.findByText("The actions couldn't be loaded. Try again.")).toBeVisible();
    fetcher.mockRestore();
  });

  it("has no axe violations", async () => {
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(null);
    const { container } = renderWithIntl(
      <CreateFromFile org="acme" documentId="d1" actions={[...PLANNED, RECEIPT]} />,
    );
    await expectNoAxeViolations(container);
  });
});
