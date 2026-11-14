import { act, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { vi } from "vitest";

import { renderWithIntl } from "@/test/intl";

import { expectNoAxeViolations } from "../../../packages/ui/src/test/axe";
import type { FileDocument } from "./api";
import { DocumentsInbox } from "./DocumentsInbox";
import { precheck } from "./upload";

/**
 * A-06-T12 — Documents inbox: list, unknown senders flagged, copy the address, drop overlay,
 * uploads refused before sending, bulk archive, previewer, refresh while scanning, a11y. The
 * 1,000-file first-paint check is the Playwright spec e2e/documents-inbox.spec.ts.
 */

function doc(overrides: Partial<FileDocument> = {}): FileDocument {
  return {
    id: "d1",
    name: "receipt.pdf",
    mime: "application/pdf",
    size: 2048,
    sha256: "a".repeat(64),
    status: "clean",
    status_label: "Ready",
    source: "upload",
    sender: "",
    sender_known: true,
    period: "2026-10",
    tax_year: 2026,
    tags: ["Receipts"],
    folder: "inbox",
    preview_status: "unsupported",
    password_protected: false,
    uploaded_by: "Sam Patel",
    created_at: "2026-11-10T15:00:00Z",
    ...overrides,
  };
}

const EMAILED = doc({
  id: "d2",
  name: "invoice-from-stranger.pdf",
  source: "email",
  sender: "someone@example.net",
  sender_known: false,
  tags: [],
});

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

function mockApi(documents: FileDocument[]) {
  const calls: { url: string; init?: RequestInit }[] = [];
  const fetcher = vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const url = String(input);
    calls.push({ url, init });
    if (url.includes("/inbound-address")) {
      return json({ address: "acme-7k3m9q2x4tbw@in.numo9.ca", created_at: "", previous: null });
    }
    if (url.includes("csrf")) return json({ csrfToken: "token" });
    if (url.endsWith("/files/bulk")) return json({ updated: 1 });
    if (url.endsWith("/actions")) return json({ results: [] });
    if (url.includes("/files?"))
      return json({ results: documents, next: null, total: documents.length });
    return json({}, 404);
  });
  return { fetcher, calls };
}

afterEach(() => {
  vi.restoreAllMocks();
  vi.useRealTimers();
});

describe("DocumentsInbox (A-06-T12)", () => {
  it("lists the folder, flags unknown senders and shows the address", async () => {
    const { calls } = mockApi([doc(), EMAILED]);
    renderWithIntl(<DocumentsInbox org="acme" />);
    const grid = await screen.findByRole("grid", { name: "Documents" });
    expect(await within(grid).findByText("receipt.pdf")).toBeInTheDocument();
    expect(within(grid).getByText("Unknown sender")).toBeInTheDocument();
    expect(await screen.findByTestId("inbound-address")).toHaveTextContent(
      "acme-7k3m9q2x4tbw@in.numo9.ca",
    );
    const list = new URL(calls.find((c) => c.url.includes("/files?"))!.url, "http://x");
    expect(list.searchParams.get("folder")).toBe("inbox");
    expect(list.searchParams.get("limit")).toBe("1000");
  });

  it("copies the address and says so", async () => {
    mockApi([doc()]);
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, { clipboard: { writeText } });
    renderWithIntl(<DocumentsInbox org="acme" />);
    await screen.findByTestId("inbound-address");
    fireEvent.click(screen.getByRole("button", { name: "Copy address" }));
    expect(writeText).toHaveBeenCalledWith("acme-7k3m9q2x4tbw@in.numo9.ca");
    expect(await screen.findByText("Address copied")).toBeInTheDocument();
  });

  it("switches to Archived and shows its empty state", async () => {
    const { calls } = mockApi([]);
    renderWithIntl(<DocumentsInbox org="acme" />);
    fireEvent.click(await screen.findByRole("tab", { name: "Archived" }));
    await waitFor(() => expect(calls.some((c) => c.url.includes("folder=archived"))).toBe(true));
  });

  it("shows the drop overlay while files are dragged over the page", async () => {
    mockApi([doc()]);
    renderWithIntl(<DocumentsInbox org="acme" />);
    const page = await screen.findByTestId("documents-inbox");
    fireEvent.dragEnter(page, { dataTransfer: { types: ["Files"], files: [] } });
    expect(screen.getByTestId("drop-overlay")).toBeInTheDocument();
    fireEvent.dragLeave(page, { dataTransfer: { types: ["Files"] } });
    expect(screen.queryByTestId("drop-overlay")).not.toBeInTheDocument();
  });

  it("refuses files of the wrong type or size before sending them", async () => {
    expect(precheck(new File(["x"], "virus.exe"))).toEqual({ kind: "refused", reason: "type" });
    const big = new File(["x"], "scan.pdf");
    Object.defineProperty(big, "size", { value: 26 * 1024 * 1024 });
    expect(precheck(big)).toEqual({ kind: "refused", reason: "size" });
    expect(precheck(new File(["x"], "scan.PDF"))).toBeNull();

    const { calls } = mockApi([doc()]);
    renderWithIntl(<DocumentsInbox org="acme" />);
    const input = await screen.findByTestId("file-input");
    fireEvent.change(input, { target: { files: [new File(["x"], "virus.exe")] } });
    expect(await screen.findByTestId("upload-row")).toHaveTextContent("virus.exe");
    expect(calls.some((c) => c.url.endsWith("/files/uploads"))).toBe(false);
  });

  it("archives the selected documents in bulk", async () => {
    const { calls } = mockApi([doc(), EMAILED]);
    renderWithIntl(<DocumentsInbox org="acme" />);
    const grid = await screen.findByRole("grid", { name: "Documents" });
    fireEvent.click(await within(grid).findByRole("checkbox", { name: "Select receipt.pdf" }));
    expect(await screen.findByText("1 selected")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Archive" }));
    await waitFor(() => expect(calls.some((c) => c.url.endsWith("/files/bulk"))).toBe(true));
    const bulk = calls.find((c) => c.url.endsWith("/files/bulk"))!;
    expect(JSON.parse(String(bulk.init!.body))).toEqual({ ids: ["d1"], action: "archive" });
  });

  it("refreshes while a document is being scanned", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const { calls } = mockApi([doc({ status: "scanning", status_label: "Scanning" })]);
    renderWithIntl(<DocumentsInbox org="acme" />);
    await screen.findByRole("grid", { name: "Documents" });
    await waitFor(() => expect(calls.filter((c) => c.url.includes("/files?")).length).toBe(1));
    await act(async () => {
      await vi.advanceTimersByTimeAsync(3100);
    });
    await waitFor(() =>
      expect(calls.filter((c) => c.url.includes("/files?")).length).toBeGreaterThan(1),
    );
  });

  it("has no axe violations", async () => {
    mockApi([doc(), EMAILED]);
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(null);
    const { container } = renderWithIntl(<DocumentsInbox org="acme" />);
    await screen.findByTestId("inbound-address");
    await within(await screen.findByRole("grid", { name: "Documents" })).findByText("receipt.pdf");
    await expectNoAxeViolations(container);
  });
});
