import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { renderWithIntl } from "@/test/intl";

import type { ReportLayout } from "./api";
import { BODY, CATALOGUE, ORG, serveJson } from "./fixtures";
import { editorRows, layoutConfig, move } from "./LayoutEditor";
import { ReportScreen } from "./ReportScreen";

/**
 * K-01-T15 — layout editor: reorder (arrows), rename, hide, text blocks, footnotes; Save as
 * draft, Publish (saves then publishes; the run shows the published snapshot), Save as custom;
 * a published layout says it can't be changed.
 */
afterEach(() => vi.unstubAllGlobals());

const layout = (over: Partial<ReportLayout>): ReportLayout => ({
  id: "5d1c0c9e-2b3a-4c5d-8e9f-0a1b2c3d4e5f",
  report: "account_activity",
  name: "Board pack",
  status: "draft",
  version: 1,
  params: {},
  config: {},
  notes: "",
  practice: null,
  published_at: null,
  updated_at: null,
  ...over,
});

function serve() {
  const calls: { url: string; method: string; body: unknown }[] = [];
  let published = false;
  vi.stubGlobal(
    "fetch",
    vi.fn(
      serveJson((url, init) => {
        const method = init?.method ?? "GET";
        calls.push({ url, method, body: init?.body ? JSON.parse(String(init.body)) : null });
        if (url.endsWith("/reports")) return { body: CATALOGUE };
        if (url.endsWith("/layouts") && method === "POST") return { status: 201, body: layout({}) };
        if (url.endsWith("/publish")) {
          published = true;
          return { body: layout({ status: "published", published_at: "2026-08-01T12:00:00Z" }) };
        }
        if (url.endsWith("/notes")) return { body: { row: "account:5400", column: "", text: "x" } };
        return {
          body: published ? { ...BODY, layout: layout({ status: "published" }) } : BODY,
        };
      }),
    ),
  );
  return calls;
}

it("reorders, renames, hides and adds text, then publishes", async () => {
  const calls = serve();
  renderWithIntl(<ReportScreen org={ORG} slug="account-activity" />);
  await screen.findByRole("table");
  await userEvent.click(screen.getByRole("button", { name: "Edit layout" }));
  const panel = screen.getByRole("complementary", { name: "Edit layout" });
  await userEvent.click(within(panel).getByRole("button", { name: "Move 5400 · Rent up" }));
  await userEvent.type(
    within(panel).getByRole("textbox", { name: "Label for 5400 · Rent" }),
    "Office rent",
  );
  await userEvent.click(within(panel).getByRole("checkbox", { name: "Hide 1000 · Chequing" }));
  await userEvent.click(within(panel).getByRole("button", { name: "Add text after Office rent" }));
  await userEvent.type(
    within(panel).getByRole("textbox", { name: "Text after Office rent" }),
    "Rent rose in June.",
  );
  await userEvent.type(within(panel).getByRole("textbox", { name: "Footnotes" }), "Unaudited.");
  await userEvent.clear(within(panel).getByRole("textbox", { name: "Layout name" }));
  await userEvent.type(within(panel).getByRole("textbox", { name: "Layout name" }), "Board pack");
  await userEvent.click(within(panel).getByRole("button", { name: "Publish" }));
  const save = calls.find((c) => c.method === "POST" && c.url.endsWith("/layouts"))!;
  expect(save.body).toEqual({
    name: "Board pack",
    status: "draft",
    params: { date_from: "2026-05-01", date_to: "2026-07-31", book: "accounting" },
    config: {
      rows: [
        { key: "account:1000", hidden: true },
        { key: "account:5400", label: "Office rent" },
        { key: "account:4000" },
      ],
      text_blocks: [{ after: "account:5400", text: "Rent rose in June." }],
    },
    notes: "Unaudited.",
  });
  expect(calls.some((c) => c.url.endsWith(`/layouts/${layout({}).id}/publish`))).toBe(true);
  expect(await within(panel).findByText("Published version 1.")).toBeVisible();
  expect(await screen.findByText(/Layout: Board pack \(version 1\)/)).toBeVisible();
  expect(screen.getByText(/later postings don't change it/)).toBeVisible();
  expect(calls.at(-1)!.url).toContain(`layout=${layout({}).id}`);
});

it("says a published layout can't be changed", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(
      serveJson((url) =>
        url.endsWith("/reports")
          ? { body: CATALOGUE }
          : { body: { ...BODY, layout: layout({ status: "published", version: 3 }) } },
      ),
    ),
  );
  renderWithIntl(<ReportScreen org={ORG} slug="account-activity" />);
  await screen.findByRole("table");
  await userEvent.click(screen.getByRole("button", { name: "Edit layout" }));
  expect(
    screen.getByText("Version 3 is published and can't be changed. Saving starts version 4."),
  ).toBeVisible();
});

it("builds the layout config and moves items", () => {
  const rows = editorRows(BODY);
  expect(rows.map((r) => r.key)).toEqual(["account:1000", "account:4000", "account:5400"]);
  expect(move(rows, 2, 0).map((r) => r.key)).toEqual([
    "account:5400",
    "account:1000",
    "account:4000",
  ]);
  expect(move(rows, 0, 5)).toBe(rows);
  expect(
    layoutConfig([{ ...rows[0]!, label: rows[0]!.original }], [{ after: "", text: "  " }]),
  ).toEqual({
    rows: [{ key: "account:1000" }],
    text_blocks: [],
  });
});
