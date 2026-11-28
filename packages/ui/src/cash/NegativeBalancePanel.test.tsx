import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { vi } from "vitest";

import { expectNoAxeViolations } from "../test/axe";
import { NegativeBalancePanel, reasonIsEnough } from "./NegativeBalancePanel";

const SHORTFALL = [{ id: "petty", message: "Petty Cash would be −994.17 on 15 Jun 2026" }];

function Warned({ onPost }: { onPost?: (reason: string) => void }) {
  const [reason, setReason] = useState("");
  return (
    <>
      <NegativeBalancePanel
        state="warn"
        title="This would take a bank or cash account below zero"
        shortfalls={SHORTFALL}
        reason={reason}
        onReasonChange={setReason}
        reasonLabel="Reason for posting anyway"
        reasonHint="At least 10 characters, kept with the journal."
        remediesLabel="Ways to fix it"
        remedies={[
          { id: "transfer", label: "Fund petty cash from Chequing", onSelect: vi.fn() },
          { id: "loan", label: "Record as owner paid", onSelect: vi.fn() },
          { id: "third", label: "Never shown", onSelect: vi.fn() },
        ]}
      />
      <button type="button" disabled={!reasonIsEnough(reason)} onClick={() => onPost?.(reason)}>
        Post
      </button>
    </>
  );
}

describe("NegativeBalancePanel (F-07-T07)", () => {
  it("warn: the shortfall, two remedy buttons and the reason field", async () => {
    const onPost = vi.fn();
    render(<Warned onPost={onPost} />);
    const panel = screen.getByRole("status", {
      name: "This would take a bank or cash account below zero",
    });
    expect(panel).toHaveAttribute("data-negative-balance", "warn");
    expect(panel).toHaveTextContent("Petty Cash would be −994.17 on 15 Jun 2026");
    const remedies = screen.getByRole("group", { name: "Ways to fix it" });
    expect(remedies.querySelectorAll("button")).toHaveLength(2);
    const post = screen.getByRole("button", { name: "Post" });
    expect(post).toBeDisabled();
    await userEvent.type(screen.getByLabelText("Reason for posting anyway"), "short");
    expect(post).toBeDisabled();
    await userEvent.type(screen.getByLabelText("Reason for posting anyway"), " but now enough");
    expect(post).toBeEnabled();
    await userEvent.click(post);
    expect(onPost).toHaveBeenCalledWith("short but now enough");
  });

  it("block: names who can override, no reason field, remedies call back", async () => {
    const fund = vi.fn();
    render(
      <NegativeBalancePanel
        state="block"
        title="This would take a bank or cash account below zero"
        shortfalls={SHORTFALL}
        body="Record the money coming in first."
        overrider="An adviser can post it, or change the policy in Banking settings."
        remedies={[{ id: "transfer", label: "Fund petty cash from Chequing", onSelect: fund }]}
        reasonLabel="Reason"
        onReasonChange={vi.fn()}
      />,
    );
    const panel = screen.getByRole("alert");
    expect(panel).toHaveAttribute("data-negative-balance", "block");
    expect(panel).toHaveTextContent("An adviser can post it");
    expect(screen.queryByLabelText("Reason")).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Fund petty cash from Chequing" }));
    expect(fund).toHaveBeenCalledOnce();
  });

  it("has no axe violations", async () => {
    const { container } = render(<Warned />);
    await expectNoAxeViolations(container);
  });

  it("reasonIsEnough trims and counts", () => {
    expect(reasonIsEnough("   123456789  ")).toBe(false);
    expect(reasonIsEnough("1234567890")).toBe(true);
    expect(reasonIsEnough("abc", 3)).toBe(true);
  });
});
