import { act, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderHook } from "@testing-library/react";
import { vi } from "vitest";

import { expectNoAxeViolations } from "../test/axe";
import { DataGrid, type DataGridProps } from "./DataGrid";
import { gridLabels, orgColumns, sampleOrgs, type SampleOrg } from "./fixtures";
import { localSavedViewsStore, useSavedViews } from "./useSavedViews";

const ORGS = sampleOrgs(30);

function setup(props: Partial<DataGridProps<SampleOrg>> = {}) {
  const user = userEvent.setup();
  render(
    <DataGrid
      data={ORGS}
      columns={orgColumns}
      getRowId={(o) => o.id}
      getRowLabel={(o) => o.name}
      labels={gridLabels}
      height={400}
      {...props}
    />,
  );
  const grid = screen.getByRole("grid", { name: "Organisations" });
  const bodyRows = () =>
    within(grid)
      .getAllByRole("row")
      .filter((r) => r.hasAttribute("data-row-index"));
  return { user, grid, bodyRows };
}

const names = (rows: HTMLElement[]) =>
  rows.map((row) => within(row).getAllByRole("gridcell").at(0)?.textContent ?? "");

describe("DataGrid (A-10-T10)", () => {
  it("renders only the visible rows (virtualised) with row counts for assistive tech", () => {
    const big = sampleOrgs(10_000);
    const { grid, bodyRows } = setup({ data: big });
    expect(grid).toHaveAttribute("aria-rowcount", "10001");
    expect(bodyRows().length).toBeLessThan(60);
    expect(bodyRows()[0]).toHaveAttribute("aria-rowindex", "2");
  });

  it("sorts by a column header (ascending, then descending) and sets aria-sort", async () => {
    const { user, grid, bodyRows } = setup();
    const header = within(grid).getByRole("columnheader", { name: /Receivables/ });
    expect(header).toHaveAttribute("aria-sort", "none");
    await user.click(within(header).getByRole("button"));
    expect(header).toHaveAttribute("aria-sort", "ascending");
    const amounts = () =>
      bodyRows().map((r) =>
        Number(
          (within(r).getAllByRole("gridcell").at(-1)?.textContent ?? "").replace(/[^0-9.-]/g, ""),
        ),
      );
    const asc = amounts();
    expect([...asc].sort((a, b) => a - b)).toEqual(asc);
    await user.click(within(header).getByRole("button"));
    expect(header).toHaveAttribute("aria-sort", "descending");
    const desc = amounts();
    expect([...desc].sort((a, b) => b - a)).toEqual(desc);
  });

  it("searches every word accent-insensitively and announces the count", async () => {
    const { user, bodyRows } = setup();
    await user.type(
      screen.getByRole("searchbox", { name: "Search organisations" }),
      "emilie harbour",
    );
    const rows = bodyRows();
    expect(rows.length).toBeGreaterThan(0);
    expect(names(rows).every((n) => n.startsWith("Harbour"))).toBe(true);
    expect(screen.getByRole("status")).toHaveTextContent(`${rows.length} of 30 organisations`);
  });

  it("filter chips narrow by column value; Clear filters resets", async () => {
    const { user, bodyRows } = setup({ selectable: false });
    await user.click(screen.getByRole("combobox", { name: "Province" }));
    await user.click(await screen.findByRole("option", { name: "Province: QC" }));
    expect(bodyRows()).toHaveLength(5);
    await user.click(screen.getByRole("button", { name: "Clear filters" }));
    expect(screen.getByRole("grid")).toHaveAttribute("aria-rowcount", "31");
  });

  it("column chooser hides and shows columns (the key column can't be hidden)", async () => {
    const { user, grid } = setup();
    await user.click(screen.getByRole("button", { name: "Columns" }));
    expect(screen.getByRole("checkbox", { name: "Organisation" })).toBeDisabled();
    await user.click(screen.getByRole("checkbox", { name: "Owner" }));
    expect(within(grid).queryByRole("columnheader", { name: /Owner/ })).toBeNull();
    await user.click(screen.getByRole("checkbox", { name: "Owner" }));
    expect(within(grid).getByRole("columnheader", { name: /Owner/ })).toBeInTheDocument();
  });

  it("density toggle switches row height", async () => {
    const { user, bodyRows } = setup();
    expect(bodyRows()[0]).toHaveStyle({ height: "44px" });
    await user.click(screen.getByRole("button", { name: "Compact" }));
    expect(screen.getByRole("button", { name: "Compact" })).toHaveAttribute("aria-pressed", "true");
    expect(bodyRows()[0]).toHaveStyle({ height: "32px" });
  });

  it("row selection: checkbox, Space, Shift+click range, select all; bulk bar shows actions", async () => {
    const bulk = vi.fn((rows: SampleOrg[]) => (
      <button type="button">Add {rows.length} to group</button>
    ));
    const { user, bodyRows } = setup({ selectable: true, bulkActions: bulk });
    const rows = bodyRows();
    await user.click(within(rows[0]!).getByRole("checkbox"));
    expect(screen.getByText("1 selected")).toBeInTheDocument();
    await user.keyboard("{Shift>}");
    await user.click(within(rows[3]!).getByRole("checkbox"));
    await user.keyboard("{/Shift}");
    expect(screen.getByText("4 selected")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Add 4 to group" })).toBeInTheDocument();
    expect(rows[2]).toHaveAttribute("aria-selected", "true");

    const all = screen.getByRole("checkbox", { name: "Select all organisations" });
    expect(all).toHaveAttribute("aria-checked", "mixed");
    await user.click(all);
    expect(screen.getByText("30 selected")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Clear selection" }));
    expect(screen.queryByText(/selected$/)).toBeNull();
  });

  it("keyboard: Tab into rows, arrows move, Space selects, Shift+↓ extends, Enter opens", async () => {
    const onRowOpen = vi.fn();
    const { user, bodyRows } = setup({ selectable: true, onRowOpen });
    const first = bodyRows()[0]!;
    first.focus();
    await user.keyboard("{ArrowDown}");
    await vi.waitFor(() => expect(bodyRows()[1]).toHaveFocus());
    await user.keyboard(" ");
    expect(bodyRows()[1]).toHaveAttribute("aria-selected", "true");
    await user.keyboard("{Shift>}{ArrowDown}{ArrowDown}{/Shift}");
    expect(screen.getByText("3 selected")).toBeInTheDocument();
    await user.keyboard("{Enter}");
    expect(onRowOpen).toHaveBeenCalledWith(ORGS[3]);
    // End / PageDown on rows that are not rendered yet: checked in a real browser (e2e/data-grid.spec.ts).
  });

  it("states: loading skeleton, empty, no results, error", async () => {
    const { rerender } = render(
      <DataGrid
        data={[]}
        columns={orgColumns}
        getRowId={(o) => o.id}
        getRowLabel={(o) => o.name}
        labels={gridLabels}
        status="loading"
      />,
    );
    expect(screen.getByRole("grid")).toHaveAttribute("aria-busy", "true");
    expect(screen.getByRole("status")).toHaveTextContent("Loading organisations…");

    rerender(
      <DataGrid
        data={[]}
        columns={orgColumns}
        getRowId={(o) => o.id}
        getRowLabel={(o) => o.name}
        labels={gridLabels}
        emptyState={<p>No organisations yet</p>}
      />,
    );
    expect(screen.getByText("No organisations yet")).toBeInTheDocument();

    rerender(
      <DataGrid
        data={ORGS}
        columns={orgColumns}
        getRowId={(o) => o.id}
        getRowLabel={(o) => o.name}
        labels={gridLabels}
        view={{
          sorting: [],
          search: "zzzz",
          filters: {},
          hiddenColumns: [],
          density: "comfortable",
        }}
        noResultsState={<p>No organisations match</p>}
      />,
    );
    expect(screen.getByText("No organisations match")).toBeInTheDocument();

    rerender(
      <DataGrid
        data={ORGS}
        columns={orgColumns}
        getRowId={(o) => o.id}
        getRowLabel={(o) => o.name}
        labels={gridLabels}
        status="error"
        errorState={<p>Couldn't load</p>}
      />,
    );
    expect(screen.getByText("Couldn't load")).toBeInTheDocument();
  });

  it("controlled view reports every change (saved views)", async () => {
    const onViewChange = vi.fn();
    const { user } = setup({ onViewChange });
    await user.click(screen.getByRole("button", { name: "Compact" }));
    expect(onViewChange).toHaveBeenLastCalledWith(expect.objectContaining({ density: "compact" }));
  });

  it("has no axe violations (selectable, with a selection)", async () => {
    const { user, bodyRows } = setup({
      selectable: true,
      bulkActions: () => <button type="button">Archive</button>,
    });
    await user.click(within(bodyRows()[0]!).getByRole("checkbox"));
    await expectNoAxeViolations();
  });
});

describe("useSavedViews (A-10-T10)", () => {
  beforeEach(() => localStorage.clear());

  it("saves, applies, updates and removes named views (persisted)", async () => {
    const store = localSavedViewsStore("numo9.grid.directory");
    const { result } = renderHook(() => useSavedViews(store));
    act(() =>
      result.current.setView({
        ...result.current.view,
        search: "retail",
        filters: { province: "ON" },
      }),
    );
    let saved!: { id: string };
    act(() => {
      saved = result.current.saveAs(" Ontario retail ");
    });
    expect(result.current.views.map((v) => v.name)).toEqual(["Ontario retail"]);
    expect(JSON.parse(localStorage.getItem("numo9.grid.directory")!)[0].state.filters).toEqual({
      province: "ON",
    });

    act(() => result.current.setView({ ...result.current.view, search: "" }));
    expect(result.current.modified).toBe(true);
    act(() => result.current.apply(saved.id));
    expect(result.current.view.search).toBe("retail");
    expect(result.current.modified).toBe(false);

    act(() => result.current.setView({ ...result.current.view, density: "compact" }));
    act(() => result.current.update());
    expect(result.current.views[0]!.state.density).toBe("compact");

    const reloaded = renderHook(() => useSavedViews(localSavedViewsStore("numo9.grid.directory")));
    await vi.waitFor(() => expect(reloaded.result.current.views).toHaveLength(1));

    act(() => result.current.remove(saved.id));
    expect(result.current.views).toEqual([]);
    expect(result.current.activeId).toBeNull();
  });
});
