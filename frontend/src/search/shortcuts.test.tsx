import { screen, within } from "@testing-library/react";

import { renderWithIntl } from "@/test/intl";

import { expectNoAxeViolations } from "../../../packages/ui/src/test/axe";
import { ShortcutHint } from "./ShortcutHint";
import { SEQUENCE_MS, isTypingTarget, shortcutFor } from "./shortcuts";
import { ShortcutSheet } from "./ShortcutSheet";

/** A-09-T08 — shortcut sheet (`?`), N-sequences and inline hints. */

const key = (
  k: string,
  mods: Partial<{ ctrlKey: boolean; metaKey: boolean; altKey: boolean }> = {},
) => ({
  key: k,
  ctrlKey: false,
  metaKey: false,
  altKey: false,
  ...mods,
});

describe("keyboard shortcuts (A-09-T08)", () => {
  it("? opens the sheet; N then a letter opens an available quick-create, in time only", () => {
    expect(shortcutFor(key("?"), null, 0)).toEqual({ kind: "sheet" });
    expect(shortcutFor(key("n"), null, 0)).toEqual({ kind: "pending" });
    const create = shortcutFor(key("c"), 1000, 1000 + SEQUENCE_MS);
    expect(create.kind === "create" && create.entry.id).toBe("contact");
    expect(shortcutFor(key("c"), 1000, 1001 + SEQUENCE_MS)).toEqual({ kind: "none" });
    // N B: documented, its screen comes later — nothing happens yet.
    expect(shortcutFor(key("b"), 0, 10)).toEqual({ kind: "none" });
    const invoice = shortcutFor(key("i"), 0, 10); // N I: New invoice (D-03a-T17)
    expect(invoice.kind === "create" && invoice.entry.id).toBe("invoice");
    expect(shortcutFor(key("n", { ctrlKey: true }), null, 0)).toEqual({ kind: "none" });
    expect(shortcutFor(key("c"), null, 0)).toEqual({ kind: "none" });
  });

  it("never fires while typing", () => {
    expect(isTypingTarget(document.createElement("input"))).toBe(true);
    expect(isTypingTarget(document.createElement("textarea"))).toBe(true);
    expect(isTypingTarget(document.createElement("button"))).toBe(false);
    expect(isTypingTarget(null)).toBe(false);
  });

  it("Shortcut sheet lists all", async () => {
    renderWithIntl(<ShortcutSheet open onOpenChange={() => undefined} />);
    const dialog = screen.getByRole("dialog", { name: "Keyboard shortcuts" });
    const create = within(dialog).getByRole("table", { name: "Create (press N, then the letter)" });
    const rows = within(create).getAllByRole("row").slice(1);
    expect(rows.map((row) => row.querySelector("kbd")?.textContent)).toEqual([
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
    expect(rows[2]).toHaveTextContent("New contact");
    expect(rows[2]).not.toHaveTextContent("Coming soon");
    expect(rows[0]).toHaveTextContent("New invoice");
    expect(rows[0]).not.toHaveTextContent("Coming soon");
    expect(rows[1]).toHaveTextContent("New billComing soon");
    const general = within(dialog).getByRole("table", { name: "Everywhere" });
    expect(general).toHaveTextContent("Ctrl+K");
    expect(general).toHaveTextContent("?");
    await expectNoAxeViolations(document.body);
  });

  it("inline hint shows the keys, hidden from assistive technology", () => {
    renderWithIntl(
      <button type="button">
        New contact
        <ShortcutHint id="contact" />
      </button>,
    );
    const button = screen.getByRole("button", { name: "New contact" });
    expect(button.querySelector("kbd")).toHaveTextContent("N C");
    expect(button.querySelector("kbd")).toHaveAttribute("aria-hidden", "true");
  });
});
