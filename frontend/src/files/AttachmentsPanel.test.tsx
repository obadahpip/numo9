import { fireEvent, screen, waitFor } from "@testing-library/react";
import { vi } from "vitest";

import { renderWithIntl } from "@/test/intl";

import { expectNoAxeViolations } from "../../../packages/ui/src/test/axe";
import type { Attachment, FileDocument } from "./api";
import { AttachmentsPanel } from "./AttachmentsPanel";

/**
 * A-06-T13 — attachments panel for detail pages: the record's documents, download, remove,
 * attach (upload → link), read-only mode, failure state, a11y.
 */
const CONTACT = "c0000000-0000-4000-8000-000000000001";

function document(overrides: Partial<FileDocument> = {}): FileDocument {
  return {
    id: "d1",
    name: "contract.pdf",
    mime: "application/pdf",
    size: 4096,
    sha256: "a".repeat(64),
    status: "clean",
    status_label: "Ready",
    source: "upload",
    sender: "",
    sender_known: true,
    period: "",
    tax_year: null,
    tags: [],
    folder: "inbox",
    preview_status: "ready",
    password_protected: false,
    uploaded_by: "Sam Patel",
    created_at: "2026-11-10T15:00:00Z",
    ...overrides,
  };
}

const LINK: Attachment = {
  id: "a1",
  record_type: "contacts.Contact",
  record_id: CONTACT,
  document: document(),
  attached_at: "2026-11-10T15:00:00Z",
  attached_by: "Sam Patel",
};

const json = (body: unknown, status = 200) =>
  new Response(status === 204 ? null : JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });

function mockApi(results: Attachment[], { failList = false } = {}) {
  const calls: { url: string; init?: RequestInit }[] = [];
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const url = String(input);
    calls.push({ url, init });
    if (url.includes("csrf")) return json({ csrfToken: "token" });
    if (url.includes("/attachments?")) return failList ? json({}, 500) : json({ results });
    if (url.endsWith("/attachments/a1")) return json(null, 204);
    if (url.endsWith("/files/uploads")) {
      return json(
        {
          document: document({ id: "d9", name: "receipt.pdf", status: "uploading" }),
          upload: { url: "https://bucket.test/", fields: { key: "k" } },
          max_size: 25 * 1024 * 1024,
        },
        201,
      );
    }
    if (url.endsWith("/files/d9/finalize")) {
      return json({
        ...document({ id: "d9", name: "receipt.pdf", status: "scanning" }),
        duplicate: false,
      });
    }
    if (url.endsWith("/files/attachments")) return json({ ...LINK, id: "a9" }, 201);
    return json({}, 404);
  });
  return calls;
}

class FakeXhr {
  status = 204;
  upload: { onprogress?: (e: ProgressEvent) => void } = {};
  onload?: () => void;
  onerror?: () => void;
  open() {}
  send() {
    setTimeout(() => this.onload?.(), 0);
  }
}

afterEach(() => vi.restoreAllMocks());

describe("AttachmentsPanel (A-06-T13)", () => {
  it("lists the record's documents", async () => {
    const calls = mockApi([LINK]);
    renderWithIntl(
      <AttachmentsPanel org="acme" recordType="contacts.Contact" recordId={CONTACT} />,
    );
    expect(await screen.findByText("contract.pdf")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /Attachments/ })).toHaveTextContent("(1)");
    expect(screen.getByRole("button", { name: "Download contract.pdf" })).toBeInTheDocument();
    const url = new URL(calls[0]!.url, "http://x");
    expect(url.pathname).toBe("/api/v1/o/acme/files/attachments");
    expect(url.searchParams.get("record_type")).toBe("contacts.Contact");
    expect(url.searchParams.get("record_id")).toBe(CONTACT);
  });

  it("removes an attachment", async () => {
    const calls = mockApi([LINK]);
    renderWithIntl(
      <AttachmentsPanel org="acme" recordType="contacts.Contact" recordId={CONTACT} />,
    );
    fireEvent.click(await screen.findByRole("button", { name: "Remove contract.pdf" }));
    await waitFor(() => expect(screen.queryByText("contract.pdf")).not.toBeInTheDocument());
    const remove = calls.find((c) => c.url.endsWith("/attachments/a1"))!;
    expect(remove.init!.method).toBe("DELETE");
    expect(screen.getByText("contract.pdf removed from this record")).toBeInTheDocument();
  });

  it("uploads a file and links it to the record", async () => {
    vi.stubGlobal("XMLHttpRequest", FakeXhr);
    const calls = mockApi([]);
    renderWithIntl(
      <AttachmentsPanel org="acme" recordType="contacts.Contact" recordId={CONTACT} />,
    );
    expect(await screen.findByText(/No files attached yet/)).toBeInTheDocument();
    fireEvent.change(screen.getByTestId("attach-input"), {
      target: { files: [new File(["%PDF-1.4"], "receipt.pdf", { type: "application/pdf" })] },
    });
    await waitFor(() => expect(calls.some((c) => c.url.endsWith("/files/attachments"))).toBe(true));
    const link = calls.find((c) => c.url.endsWith("/files/attachments"))!;
    expect(JSON.parse(String(link.init!.body))).toEqual({
      document: "d9",
      record_type: "contacts.Contact",
      record_id: CONTACT,
    });
    expect(await screen.findByText("receipt.pdf attached")).toBeInTheDocument();
    vi.unstubAllGlobals();
  });

  it("is read-only without edit rights, and says when it can't load", async () => {
    mockApi([LINK]);
    const { unmount } = renderWithIntl(
      <AttachmentsPanel
        org="acme"
        recordType="contacts.Contact"
        recordId={CONTACT}
        canEdit={false}
      />,
    );
    expect(await screen.findByText("contract.pdf")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Attach files" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Remove/ })).not.toBeInTheDocument();
    unmount();
    vi.restoreAllMocks();
    mockApi([], { failList: true });
    renderWithIntl(
      <AttachmentsPanel org="acme" recordType="contacts.Contact" recordId={CONTACT} />,
    );
    expect(await screen.findByText("The attachments couldn't be loaded.")).toBeInTheDocument();
  });

  it("has no axe violations", async () => {
    mockApi([
      LINK,
      { ...LINK, id: "a2", document: document({ id: "d2", name: "scan.pdf", status: "scanning" }) },
    ]);
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(null);
    const { container } = renderWithIntl(
      <AttachmentsPanel org="acme" recordType="contacts.Contact" recordId={CONTACT} />,
    );
    await screen.findByText("scan.pdf");
    await expectNoAxeViolations(container);
  });
});
