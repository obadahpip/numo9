import { act, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { useState } from "react";
import { vi } from "vitest";

import { renderWithIntl } from "@/test/intl";

import { expectNoAxeViolations } from "../../../packages/ui/src/test/axe";
import { duplicatesUrl, isCheckable, type DuplicateMatch } from "./api";
import { DuplicatePanel, LiveDuplicatePanel } from "./DuplicatePanel";
import { DUPLICATE_DEBOUNCE_MS } from "./useDuplicateCheck";

/**
 * B-01-T16 — live duplicate panel while typing (debounced). Acceptance: the panel shows within
 * 300 ms after typing stops. Also: one request per pause with the latest text, late answers for
 * older text dropped, nothing asked for a too-short query, reasons/province/archived shown,
 * Open · Merge… · Ignore, the count announced once, no axe violations.
 */

const MAPLE: DuplicateMatch = {
  contact: {
    id: "7f6c2b1e-0000-4000-8000-000000000002",
    number: "C-0002",
    display_name: "Maple Supply Ltd.",
    province: "ON",
    roles: ["customer"],
    archived: false,
  },
  reasons: ["bn", "name"],
  similarity: 0.7857,
};

const ERABLE: DuplicateMatch = {
  contact: {
    id: "7f6c2b1e-0000-4000-8000-000000000019",
    number: "C-0019",
    display_name: "Maple Supplies (Québec) inc.",
    province: "",
    roles: ["supplier"],
    archived: true,
  },
  reasons: ["name"],
  similarity: 0.61,
};

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

/** A fetch mock answering every duplicate check with `results` (or per-URL with a function). */
function mockFetch(results: DuplicateMatch[] | ((url: string) => DuplicateMatch[])) {
  return vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);
    return jsonResponse({ results: typeof results === "function" ? results(url) : results });
  });
}

/** The contact form's name field with the live panel, as B-01-T15 will mount it. */
function Harness({ fetcher, delay }: { fetcher: typeof fetch; delay?: number }) {
  const [name, setName] = useState("");
  return (
    <>
      <label htmlFor="name">Display name</label>
      <input id="name" value={name} onChange={(event) => setName(event.target.value)} />
      <LiveDuplicatePanel org="acme" query={{ name }} fetcher={fetcher} delay={delay} />
    </>
  );
}

function type(text: string) {
  fireEvent.change(screen.getByLabelText("Display name"), { target: { value: text } });
}

afterEach(() => {
  vi.useRealTimers();
});

describe("duplicate check client", () => {
  it("builds the duplicates URL from what is typed", () => {
    expect(duplicatesUrl("acme", { name: " Maple Suply ", bn: "123456782", exclude: "x-1" })).toBe(
      "/api/v1/o/acme/contacts/duplicates?q=Maple+Suply&bn=123456782&exclude=x-1",
    );
    expect(duplicatesUrl("acme", { email: "ap@maplesupply.ca", taxId: "US 12" })).toBe(
      "/api/v1/o/acme/contacts/duplicates?email=ap%40maplesupply.ca&tax_id=US+12",
    );
  });

  it("asks only when the query is worth it", () => {
    expect(isCheckable({ name: "Ma" })).toBe(false);
    expect(isCheckable({ name: "Map" })).toBe(true);
    expect(isCheckable({ email: "ap@" })).toBe(false);
    expect(isCheckable({ email: "ap@maplesupply.ca" })).toBe(true);
    expect(isCheckable({ bn: "123 456 78" })).toBe(false);
    expect(isCheckable({ bn: "123 456 782" })).toBe(true);
    expect(isCheckable({ taxId: "US1" })).toBe(true);
  });
});

describe("LiveDuplicatePanel (B-01-T16)", () => {
  it("shows the panel within 300 ms after typing stops", async () => {
    const fetcher = mockFetch([MAPLE]);
    renderWithIntl(<Harness fetcher={fetcher as unknown as typeof fetch} />);
    type("Maple Suply");
    const typedAt = performance.now();
    await screen.findByTestId("duplicate-panel", {}, { timeout: 1000, interval: 5 });
    const elapsed = performance.now() - typedAt;
    expect(elapsed).toBeLessThan(300);
    expect(elapsed).toBeGreaterThanOrEqual(DUPLICATE_DEBOUNCE_MS - 5); // debounced, not instant
    expect(screen.getByRole("heading", { name: "Possible duplicates (1)" })).toBeInTheDocument();
  });

  it("sends one request per pause, with the latest text", async () => {
    vi.useFakeTimers();
    const fetcher = mockFetch([MAPLE]);
    renderWithIntl(<Harness fetcher={fetcher as unknown as typeof fetch} />);
    for (const text of ["Map", "Mapl", "Maple", "Maple S", "Maple Suply"]) {
      type(text);
      await act(async () => {
        vi.advanceTimersByTime(100); // typing faster than the debounce
      });
    }
    expect(fetcher).not.toHaveBeenCalled();
    await act(async () => {
      vi.advanceTimersByTime(DUPLICATE_DEBOUNCE_MS);
    });
    expect(fetcher).toHaveBeenCalledTimes(1);
    expect(String(fetcher.mock.calls[0]![0])).toContain("q=Maple+Suply");
  });

  it("asks nothing for fewer than 3 characters and clears the panel", async () => {
    const fetcher = mockFetch([MAPLE]);
    renderWithIntl(<Harness fetcher={fetcher as unknown as typeof fetch} delay={10} />);
    type("Maple");
    await screen.findByTestId("duplicate-panel");
    type("Ma");
    await waitFor(() => expect(screen.queryByTestId("duplicate-panel")).not.toBeInTheDocument());
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it("drops a late answer for older text", async () => {
    let releaseOld: (() => void) | undefined;
    const fetcher = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("q=Maple+S")) {
        await new Promise<void>((resolve) => (releaseOld = resolve));
        return jsonResponse({ results: [ERABLE] });
      }
      return jsonResponse({ results: [MAPLE] });
    });
    renderWithIntl(<Harness fetcher={fetcher as unknown as typeof fetch} delay={10} />);
    type("Maple S");
    await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(1));
    type("Maple Suply");
    await screen.findByText("Maple Supply Ltd.");
    await act(async () => releaseOld?.());
    expect(screen.queryByText("Maple Supplies (Québec) inc.")).not.toBeInTheDocument();
    expect(screen.getByText("Maple Supply Ltd.")).toBeInTheDocument();
  });

  it("shows nothing when the check fails (the form stays usable)", async () => {
    const fetcher = vi.fn(async () => new Response("{}", { status: 500 }));
    renderWithIntl(<Harness fetcher={fetcher as unknown as typeof fetch} delay={10} />);
    type("Maple Suply");
    await waitFor(() => expect(fetcher).toHaveBeenCalled());
    expect(screen.queryByTestId("duplicate-panel")).not.toBeInTheDocument();
  });
});

describe("DuplicatePanel", () => {
  it("says why each contact matched, with its number and province", () => {
    renderWithIntl(<DuplicatePanel org="acme" matches={[MAPLE, ERABLE]} />);
    const items = within(screen.getByTestId("duplicate-panel")).getAllByRole("listitem");
    expect(items[0]).toHaveTextContent("Maple Supply Ltd.· C-0002 · ON"); // a CSS gap before ·
    expect(items[0]).toHaveTextContent("Business Number matches · Name 79% similar");
    expect(items[1]).toHaveTextContent("C-0019 · No province");
    expect(items[1]).toHaveTextContent("Archived");
    expect(screen.getByRole("link", { name: "Open Maple Supply Ltd." })).toHaveAttribute(
      "href",
      "/o/acme/contacts/7f6c2b1e-0000-4000-8000-000000000002",
    );
    expect(screen.getByText("Checked as you type. You can still save this contact.")).toBeVisible();
  });

  it("ignores a contact and merges with another", () => {
    const onMerge = vi.fn();
    renderWithIntl(<DuplicatePanel org="acme" matches={[MAPLE, ERABLE]} onMerge={onMerge} />);
    fireEvent.click(screen.getByRole("button", { name: "Merge with Maple Supply Ltd." }));
    expect(onMerge).toHaveBeenCalledWith(MAPLE);
    fireEvent.click(screen.getByRole("button", { name: "Ignore Maple Supplies (Québec) inc." }));
    expect(screen.getByRole("heading", { name: "Possible duplicates (1)" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Ignore Maple Supply Ltd." }));
    expect(screen.queryByTestId("duplicate-panel")).not.toBeInTheDocument();
  });

  it("hides Merge until the merge dialog exists", () => {
    renderWithIntl(<DuplicatePanel org="acme" matches={[MAPLE]} />);
    expect(screen.queryByRole("button", { name: /Merge/ })).not.toBeInTheDocument();
  });

  it("announces the count once in a polite status", () => {
    const { rerender } = renderWithIntl(<DuplicatePanel org="acme" matches={[MAPLE, ERABLE]} />);
    const status = screen.getByRole("status");
    expect(status).toHaveAttribute("aria-live", "polite");
    expect(status).toHaveTextContent("2 possible duplicates found");
    rerender(<DuplicatePanel org="acme" matches={[]} />);
    expect(status).toHaveTextContent("");
  });

  it("has no axe violations", async () => {
    // axe-core probes canvas for icon ligatures; jsdom has no canvas.
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(null);
    const { container } = renderWithIntl(
      <DuplicatePanel org="acme" matches={[MAPLE, ERABLE]} onMerge={() => undefined} />,
    );
    await expectNoAxeViolations(container);
  });
});
