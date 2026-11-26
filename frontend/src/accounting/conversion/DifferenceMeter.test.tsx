import { act, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { vi } from "vitest";

import { serveJson } from "@/banking/fixtures";
import { renderWithIntl } from "@/test/intl";

import type { Difference } from "./api";
import { DifferenceMeter } from "./DifferenceMeter";
import { difference, overview, session } from "./fixtures";
import { blockers, meterTotals, type MeterRow } from "./meter";

/**
 * C-05-T11 — the sticky difference meter: figures follow every keystroke (< 50 ms for a large
 * trial balance), Finalise is disabled while the difference isn't 0.00 and its tooltip names the
 * difference; the server's reasons (AR/AP control vs documents) keep it disabled too; when
 * nothing blocks, Finalise confirms and posts.
 */
const row = (account: string, debit = "", credit = ""): MeterRow => ({ account, debit, credit });

describe("meterTotals", () => {
  it("adds exactly and ignores rows without an account", () => {
    const totals = meterTotals(
      [row("a", "120,000.10"), row("b", "450.00"), row("c", "", "120437.50"), row("", "99")],
      "en-CA",
    );
    expect(totals).toMatchObject({
      debits: "120450.10",
      credits: "120437.50",
      difference: "12.60",
      balanced: false,
      lines: 3,
    });
    expect(
      meterTotals([row("a", "0.1"), row("b", "0.2"), row("c", "", "0.3")], "en-CA").balanced,
    ).toBe(true);
    expect(meterTotals([row("a", "abc")], "en-CA").unreadable).toBe(1);
  });

  it("updates in under 50 ms for 2 000 lines", () => {
    const rows = Array.from({ length: 2000 }, (_, i) => row(`a${i}`, `${i}.25`, ""));
    const started = performance.now();
    meterTotals(rows, "en-CA");
    expect(performance.now() - started).toBeLessThan(50);
  });

  it("merges the server's reasons without repeating the live ones", () => {
    const server = difference({
      reasons: [
        { code: "conversion.unbalanced", message: "old" },
        { code: "conversion.control_mismatch", message: "1100 · Accounts receivable is 1,400.00" },
      ],
    });
    const found = blockers(meterTotals([row("a", "1", "")], "en-CA"), server, false);
    expect(found.map((b) => b.kind)).toEqual(["unbalanced", "server"]);
  });
});

function Harness({ server }: { server: Difference }) {
  const [debit, setDebit] = useState("120450.00");
  return (
    <>
      <label>
        Debit
        <input value={debit} onChange={(e) => setDebit(e.target.value)} />
      </label>
      <DifferenceMeter
        org="acme"
        rows={[row("cash", debit), row("re", "", "120437.50")]}
        server={server}
        conversionDate="2026-01-01"
        finalised={false}
        lockBalances
        onFinalised={() => undefined}
      />
    </>
  );
}

let posted: unknown[] = [];
beforeEach(() => {
  posted = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(
      serveJson((url, init) => {
        posted.push({ url, body: init?.body ? JSON.parse(String(init.body)) : null });
        return { body: overview({ session: session({ status: "finalised" }) }) };
      }),
    ),
  );
});
afterEach(() => vi.unstubAllGlobals());

it("disabled with the difference named; enabled once balanced; confirms and posts", async () => {
  const user = userEvent.setup();
  renderWithIntl(<Harness server={difference({ reasons: [] })} />);
  const meter = screen.getByRole("region", { name: "Conversion difference" });
  expect(meter).toHaveTextContent(
    "Debits 120,450.00 · Credits 120,437.50 · Difference 12.50— Finalise unavailable",
  );
  const finalise = screen.getByRole("button", { name: "Finalise" });
  expect(finalise).toBeDisabled();
  const reason = document.querySelector("[data-finalise-reason]");
  expect(reason?.getAttribute("data-finalise-reason")).toBe(
    "The balances are out by 12.50: debits must equal credits.",
  );
  await act(async () => {
    (reason as HTMLElement).focus();
  });
  expect((await screen.findAllByText(/out by 12.50/)).length).toBeGreaterThan(1); // tooltip too

  const input = screen.getByLabelText("Debit");
  await user.clear(input);
  await user.type(input, "120437.50");
  expect(meter).toHaveTextContent("Difference 0.00— Balanced, ready to finalise");
  expect(screen.getByRole("button", { name: "Finalise" })).toBeEnabled();
  await user.click(screen.getByRole("button", { name: "Finalise" }));
  const dialog = await screen.findByRole("dialog", { name: "Finalise the conversion?" });
  expect(dialog).toHaveTextContent("close to 31 Dec 2025 for everyone except advisers");
  await user.click(screen.getAllByRole("button", { name: "Finalise" }).at(-1)!);
  await waitFor(() =>
    expect(posted).toContainEqual({
      url: "/api/v1/o/acme/conversion/finalise",
      body: { lock_balances: true },
    }),
  );
});

it("a control mismatch from the server keeps Finalise disabled, named", () => {
  renderWithIntl(
    <DifferenceMeter
      org="acme"
      rows={[row("cash", "100"), row("re", "", "100")]}
      server={difference({
        reasons: [
          {
            code: "conversion.control_mismatch",
            message:
              "1100 · Accounts receivable is 1,400.00 but its open documents add up to 1,500.00",
          },
        ],
      })}
      conversionDate="2026-01-01"
      finalised={false}
      lockBalances={false}
      onFinalised={() => undefined}
    />,
  );
  expect(screen.getByRole("button", { name: "Finalise" })).toBeDisabled();
  expect(screen.getByRole("list", { name: "Why Finalise is unavailable" })).toHaveTextContent(
    "open documents add up to 1,500.00",
  );
});
