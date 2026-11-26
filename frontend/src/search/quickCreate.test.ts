import { describe, expect, it } from "vitest";

import { offeredQuickCreates, QUICK_CREATE, quickCreateFor, shortcutOf } from "./quickCreate";

describe("quick-create registry (A-09-T06)", () => {
  it("documents the eleven shortcuts N I, N B, N C, N Q, N P, N J, N S, N R, N A, N T, N U", () => {
    expect(QUICK_CREATE.map(shortcutOf)).toEqual([
      "N I",
      "N B",
      "N C",
      "N Q",
      "N P",
      "N J",
      "N S",
      "N R",
      "N A",
      "N T",
      "N U",
    ]);
    expect(new Set(QUICK_CREATE.map((e) => e.key)).size).toBe(11);
    for (const entry of QUICK_CREATE) {
      expect(entry.permission).toMatch(/^[a-z_]+\.[a-z_]+\.[a-z_]+$/);
      expect(entry.feature).toBeTruthy();
    }
  });

  it("finds the entry of a key, any case", () => {
    expect(quickCreateFor("c")?.id).toBe("contact");
    expect(quickCreateFor("Z")).toBeUndefined();
  });

  it("offers what is available and permitted, locked when the package lacks it", () => {
    const all = offeredQuickCreates(null, () => null).map((o) => o.entry.id);
    expect(all).toEqual([
      "invoice",
      "bill",
      "contact",
      "quote",
      "purchase-order",
      "journal",
      "spend",
      "receive",
      "bank-account",
      "user",
    ]);
    const none = offeredQuickCreates(new Set(["contacts.contacts.view"]), () => null);
    expect(none).toEqual([]);
    const locked = offeredQuickCreates(new Set(["contacts.contacts.manage"]), (f) =>
      f.startsWith("accounting.") ? "Part of Accounting" : null,
    );
    expect(locked).toEqual([{ entry: QUICK_CREATE[2], reason: "Part of Accounting" }]);
  });

  it("invoices (D-03a-T17): New invoice N I for people who write invoices", () => {
    expect(quickCreateFor("i")?.path).toBe("sales/invoices/new");
    const seller = offeredQuickCreates(new Set(["sales.invoices.write"]), () => null);
    expect(seller.map((o) => o.entry.id)).toEqual(["invoice"]);
  });

  it("purchase orders (E-01-T11): New purchase order N P for people who write POs", () => {
    expect(quickCreateFor("p")?.path).toBe("purchases/orders/new");
    const buyer = offeredQuickCreates(new Set(["purchases.orders.write"]), () => null);
    expect(buyer.map((o) => o.entry.id)).toEqual(["purchase-order"]);
  });

  it("bills (E-02-T16): New bill N B for people who enter bills", () => {
    expect(quickCreateFor("b")?.path).toBe("purchases/bills/new");
    const clerk = offeredQuickCreates(new Set(["purchases.bills.write"]), () => null);
    expect(clerk.map((o) => o.entry.id)).toEqual(["bill"]);
  });

  it("banking (F-01-T13): Spend money N S, Receive money N R, Add bank account N A", () => {
    expect(quickCreateFor("s")?.path).toBe("banking/spend");
    expect(quickCreateFor("r")?.path).toBe("banking/receive");
    expect(quickCreateFor("a")?.path).toBe("banking?add=1");
    const banker = offeredQuickCreates(new Set(["accounting.banking.transact"]), () => null);
    expect(banker.map((o) => o.entry.id)).toEqual(["spend", "receive"]);
    const manager = offeredQuickCreates(new Set(["accounting.banking.manage"]), () => null);
    expect(manager.map((o) => o.entry.id)).toEqual(["bank-account"]);
  });
});
