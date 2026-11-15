import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { vi } from "vitest";

import { expectNoAxeViolations } from "../test/axe";
import { ColumnChooser, orderColumns } from "./ColumnChooser";
import { DataGrid, type DataGridProps } from "./DataGrid";
import { gridLabels, orgColumns, sampleOrgs, type SampleOrg } from "./fixtures";
import { HighlightedText, highlightRanges } from "./HighlightedText";
import { EMPTY_VIEW, type GridViewState } from "./types";

/** V-01: server-side (manual) mode, Ctrl/⌘+Enter, ↓ from search, column reorder, highlighting. */

const ORGS = sampleOrgs(12);
const LABELS = {
  ...gridLabels,
  reorderHint: "Drag to reorder, or Alt+↑/↓",
  columnMoved: (column: string, position: number, total: number) =>
    `${column} moved to position ${position} of ${total}`,
};

function Controlled(
  props: Partial<DataGridProps<SampleOrg>> & { onView?: (v: GridViewState) => void },
) {
  const [view, setView] = useState<GridViewState>(EMPTY_VIEW);
  return (
    <DataGrid
      data={ORGS}
      columns={orgColumns}
      getRowId={(o) => o.id}
      getRowLabel={(o) => o.name}
      labels={LABELS}
      height={400}
      view={view}
      onViewChange={(next) => {
        setView(next);
        props.onView?.(next);
      }}
      {...props}
    />
  );
}

const bodyRows = () =>
  within(screen.getByRole("grid"))
    .getAllByRole("row")
    .filter((r) => r.hasAttribute("data-row-index"));
const firstCells = () => bodyRows().map((r) => within(r).getAllByRole("gridcell")[0]!.textContent);

describe("DataGrid server-side mode (V-01)", () => {
  it("renders the server's rows as given: no client search or sort", async () => {
    const user = userEvent.setup();
    const onView = vi.fn();
    render(<Controlled manual totalCount={143} unfilteredCount={2000} onView={onView} />);
    const before = firstCells();
    await user.type(screen.getByRole("searchbox"), "zzz-no-match");
    expect(firstCells()).toEqual(before); // the server answers the search, not the grid
    expect(onView).toHaveBeenLastCalledWith(expect.objectContaining({ search: "zzz-no-match" }));
    expect(screen.getByRole("status")).toHaveTextContent("143 of 2,000 organisations");
    expect(screen.getByRole("grid")).toHaveAttribute("aria-rowcount", "144");
    const header = screen.getByRole("columnheader", { name: /Organisation/ });
    await user.click(within(header).getByRole("button"));
    expect(onView).toHaveBeenLastCalledWith(
      expect.objectContaining({ sorting: [{ id: "name", desc: false }] }),
    );
    expect(firstCells()).toEqual(before);
  });

  it("an empty answer with a search on is 'no results', without one it is 'empty'", async () => {
    const user = userEvent.setup();
    render(
      <Controlled
        manual
        data={[]}
        emptyState={<p>first run</p>}
        noResultsState={<p>nothing matches</p>}
      />,
    );
    expect(screen.getByText("first run")).toBeInTheDocument();
    await user.type(screen.getByRole("searchbox"), "maple");
    expect(screen.getByText("nothing matches")).toBeInTheDocument();
  });

  it("isFiltered counts a filters panel outside the grid", () => {
    render(
      <Controlled
        manual
        isFiltered
        data={[]}
        emptyState={<p>first run</p>}
        noResultsState={<p>none</p>}
      />,
    );
    expect(screen.getByText("none")).toBeInTheDocument();
  });

  it("↓ from the search box enters the rows; Enter opens; Ctrl/⌘+Enter opens in a new tab", async () => {
    const user = userEvent.setup();
    const open = vi.fn();
    const newTab = vi.fn();
    render(<Controlled onRowOpen={open} onRowOpenNewTab={newTab} searchPlaceholder="Search…" />);
    const search = screen.getByPlaceholderText("Search…");
    await user.click(search);
    await user.keyboard("{ArrowDown}");
    expect(bodyRows()[0]).toHaveFocus();
    await user.keyboard("{ArrowDown}{Control>}{Enter}{/Control}");
    expect(newTab).toHaveBeenCalledWith(ORGS[1]);
    expect(open).not.toHaveBeenCalled();
    await user.keyboard("{Meta>}{Enter}{/Meta}");
    expect(newTab).toHaveBeenCalledTimes(2);
    await user.keyboard("{Enter}");
    expect(open).toHaveBeenCalledWith(ORGS[1]);
  });

  it("columns follow the view's column order", () => {
    render(
      <DataGrid
        data={ORGS}
        columns={orgColumns}
        getRowId={(o) => o.id}
        getRowLabel={(o) => o.name}
        labels={LABELS}
        view={{ ...EMPTY_VIEW, columnOrder: ["province", "name"] }}
      />,
    );
    const headers = screen.getAllByRole("columnheader").map((h) => h.textContent ?? "");
    expect(headers[0]).toMatch(/Province/);
    expect(headers[1]).toMatch(/Organisation/);
  });
});

describe("ColumnChooser reorder (V-01-T12)", () => {
  const COLUMNS = [
    { id: "name", header: "Organisation", hideable: false },
    { id: "bn", header: "BN", hideable: true },
    { id: "province", header: "Province", hideable: true },
  ];

  function Chooser() {
    const [order, setOrder] = useState(["name", "bn", "province"]);
    const [hidden, setHidden] = useState<string[]>([]);
    return (
      <>
        <ColumnChooser
          label="Columns"
          columns={COLUMNS}
          hidden={hidden}
          onChange={setHidden}
          order={order}
          onOrderChange={setOrder}
          reorderHint={LABELS.reorderHint}
          movedLabel={LABELS.columnMoved}
        />
        <output data-testid="order">{order.join(",")}</output>
      </>
    );
  }

  it("Alt+↑/↓ moves the focused column and announces it", async () => {
    const user = userEvent.setup();
    render(<Chooser />);
    await user.click(screen.getByRole("button", { name: "Columns" }));
    screen.getByRole("checkbox", { name: "Province" }).focus();
    await user.keyboard("{Alt>}{ArrowUp}{/Alt}");
    expect(screen.getByTestId("order")).toHaveTextContent("name,province,bn");
    expect(screen.getByText("Province moved to position 2 of 3")).toBeInTheDocument();
    expect(screen.getByText("Drag to reorder, or Alt+↑/↓")).toBeInTheDocument();
    await user.keyboard("{Alt>}{ArrowDown}{/Alt}");
    expect(screen.getByTestId("order")).toHaveTextContent("name,bn,province");
    await expectNoAxeViolations(document.body);
  });

  it("orderColumns keeps unknown ids out and appends new columns", () => {
    expect(orderColumns(COLUMNS, ["province", "gone"]).map((c) => c.id)).toEqual([
      "province",
      "name",
      "bn",
    ]);
    expect(orderColumns(COLUMNS, undefined)).toBe(COLUMNS);
  });
});

describe("HighlightedText (V-01-T10)", () => {
  it.each([
    ["Érable Bakery Inc.", "erab", [[0, 4]]],
    [
      "Maple Leaf Supply Ltd.",
      "map sup",
      [
        [0, 3],
        [11, 14],
      ],
    ],
    ["Maple Leaf Supply Ltd.", "ple", []], // word starts only, like the server
    ["123 456 782", "123 456", [[0, 7]]],
    ["123456782", "123 456", [[0, 6]]],
    ["123 456 782", "4567", [[4, 9]]],
  ])("%s / %s", (text, query, expected) => {
    expect(highlightRanges(text, query)).toEqual(expected);
  });

  it("wraps matches in <mark>", () => {
    const { container } = render(<HighlightedText text="Érable Bakery" query="bak" />);
    expect(container.querySelector("mark")?.textContent).toBe("Bak");
    expect(container.textContent).toBe("Érable Bakery");
  });
});
