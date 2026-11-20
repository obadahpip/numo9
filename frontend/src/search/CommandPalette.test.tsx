import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { vi } from "vitest";

import { renderWithIntl } from "@/test/intl";

import { expectNoAxeViolations } from "../../../packages/ui/src/test/axe";
import { CommandPalette, isPaletteShortcut, matches } from "./CommandPalette";
import { readRecents } from "./recents";

/** A-09-T07 — command palette: groups, recents, gated items explained, keyboard only. */

const ORG = "11111111-0000-4000-8000-000000000000";

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

const RESULTS = {
  query: "cedar",
  records: [
    {
      type: "contacts.contact",
      id: "c-1",
      title: "Cedar Roofing Co.",
      subtitle: "Customer",
      code: "",
      amount: null,
      date: null,
      url: `/o/${ORG}/contacts/c-1`,
      match: "text",
      locked: false,
      reason: null,
    },
    {
      type: "files.document",
      id: "d-1",
      title: "Cedar invoice.pdf",
      subtitle: "",
      code: "",
      amount: null,
      date: null,
      url: `/o/${ORG}/documents/d-1`,
      match: "text",
      locked: true,
      reason: "Part of Documents, which isn't in this organisation's package.",
    },
  ],
  settings: [
    {
      key: "lock_dates",
      title: "Lock dates",
      url: `/o/${ORG}/settings/lock-dates`,
      locked: false,
      reason: null,
    },
  ],
  reports: [],
  navigation: [],
};

function mockApi({ fail = false, permissions = ["contacts.contacts.manage"] } = {}) {
  const urls: URL[] = [];
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = new URL(String(input), "http://numo9.test");
    urls.push(url);
    if (url.pathname.endsWith("/my-permissions")) return json({ permissions });
    if (fail) return json({}, 500);
    return json(RESULTS);
  });
  return urls;
}

function Harness({ navigate }: { navigate: (href: string) => void }) {
  const [open, setOpen] = useState(false);
  return (
    <CommandPalette
      org={ORG}
      open={open}
      onOpenChange={setOpen}
      navigate={navigate}
      trigger={<button type="button">Search or jump to…</button>}
    />
  );
}

beforeAll(() => {
  globalThis.ResizeObserver ??= class {
    observe() {}
    unobserve() {}
    disconnect() {}
  } as unknown as typeof ResizeObserver;
  Element.prototype.scrollIntoView ??= () => undefined;
});

beforeEach(() => window.localStorage.clear());
afterEach(() => vi.restoreAllMocks());

describe("CommandPalette (A-09-T07)", () => {
  it("recognises Ctrl+K and ⌘+K only; matches words by their start, accents ignored", () => {
    expect(isPaletteShortcut({ key: "k", ctrlKey: true, metaKey: false })).toBe(true);
    expect(isPaletteShortcut({ key: "K", ctrlKey: false, metaKey: true })).toBe(true);
    expect(isPaletteShortcut({ key: "k", ctrlKey: false, metaKey: false })).toBe(false);
    expect(matches("Nouveau contact", "cont")).toBe(true);
    expect(matches("Créer une facture", "creer fac")).toBe(true);
    expect(matches("New contact", "ntact")).toBe(false);
  });

  it("keyboard only: groups, gated item explained, ↓ + Enter opens, recents remembered", async () => {
    const urls = mockApi();
    const navigate = vi.fn();
    const user = userEvent.setup();
    renderWithIntl(<Harness navigate={navigate} />);
    await user.tab();
    await user.keyboard("{Enter}");
    const dialog = await screen.findByRole("dialog", { name: "Search" });
    const box = within(dialog).getByRole("combobox", {
      name: "Search contacts, accounts, journals, settings and reports",
    });
    expect(box).toHaveFocus();
    // Nothing typed: the quick-create actions the user may do (contact; no invite permission).
    expect(await within(dialog).findByRole("group", { name: "Create" })).toBeInTheDocument();
    expect(within(dialog).getByText("New contact")).toBeInTheDocument();
    expect(within(dialog).queryByText("Invite a user")).not.toBeInTheDocument();

    await user.type(box, "cedar");
    expect(await within(dialog).findByText("Cedar Roofing Co.")).toBeInTheDocument();
    expect(urls.at(-1)!.searchParams.get("q")).toBe("cedar");
    expect(urls.at(-1)!.pathname).toBe(`/api/v1/o/${ORG}/search`);
    expect(within(dialog).getByRole("group", { name: "Records" })).toBeInTheDocument();
    expect(within(dialog).getByRole("group", { name: "Settings" })).toBeInTheDocument();
    expect(within(dialog).queryByRole("group", { name: "Reports" })).not.toBeInTheDocument();
    expect(within(dialog).queryByRole("group", { name: "Create" })).not.toBeInTheDocument();
    const locked = within(dialog).getByRole("option", { name: /Cedar invoice\.pdf/ });
    expect(locked).toHaveTextContent(
      "Locked:Part of Documents, which isn't in this organisation's package.",
    );
    await expectNoAxeViolations(document.body);

    const options = within(dialog).getAllByRole("option");
    expect(options[0]).toHaveAttribute("aria-selected", "true");
    await user.keyboard("{ArrowDown}{ArrowDown}{Enter}");
    expect(navigate).toHaveBeenCalledWith(`/o/${ORG}/settings/lock-dates`);
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(screen.getByRole("button", { name: "Search or jump to…" })).toHaveFocus();
    expect(readRecents(ORG)).toEqual([
      { id: "settings:lock_dates", title: "Lock dates", url: `/o/${ORG}/settings/lock-dates` },
    ]);

    await user.keyboard("{Enter}");
    const again = await screen.findByRole("dialog", { name: "Search" });
    expect(await within(again).findByRole("group", { name: "Recent" })).toHaveTextContent(
      "Lock dates",
    );
    await user.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });

  it("a failed search says so and retries", async () => {
    const urls = mockApi({ fail: true });
    const user = userEvent.setup();
    renderWithIntl(<Harness navigate={vi.fn()} />);
    await user.click(screen.getByRole("button", { name: "Search or jump to…" }));
    await user.type(await screen.findByRole("combobox"), "cedar");
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Search isn't available right now");
    const before = urls.length;
    await user.click(within(alert).getByRole("button", { name: "Try again" }));
    await waitFor(() => expect(urls.length).toBeGreaterThan(before));
  });
});
