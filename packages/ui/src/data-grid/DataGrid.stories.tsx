import type { Meta, StoryObj } from "@storybook/react";
import { useMemo, useState } from "react";

import { Button } from "../primitives/Button";
import { DataGrid } from "./DataGrid";
import { gridLabels, orgColumns, sampleOrgs } from "./fixtures";
import { localSavedViewsStore, useSavedViews } from "./useSavedViews";

/**
 * DataGrid (A-10-T10): the directory grid. Search ("harbour ON"), filter chips, sort by any
 * heading, hide columns, compact density, select rows (Shift+click for a range) to see the bulk
 * bar, save the view. Keyboard: Tab into the rows, ↑/↓, Space, Shift+↓, Enter.
 */
const meta: Meta = { title: "Data/DataGrid", parameters: { layout: "padded" } };
export default meta;
type Story = StoryObj;

function Directory({ count }: { count: number }) {
  const data = useMemo(() => sampleOrgs(count), [count]);
  const store = useMemo(() => localSavedViewsStore("storybook.grid.directory"), []);
  const views = useSavedViews(store);
  const [opened, setOpened] = useState<string | null>(null);
  return (
    <div className="grid gap-2">
      <DataGrid
        data={data}
        columns={orgColumns}
        getRowId={(o) => o.id}
        getRowLabel={(o) => o.name}
        labels={gridLabels}
        view={views.view}
        onViewChange={views.setView}
        selectable
        onRowOpen={(o) => setOpened(o.name)}
        bulkActions={(rows) => (
          <>
            <Button size="sm">Add {rows.length} to group</Button>
            <Button size="sm">Tag</Button>
          </>
        )}
        toolbar={
          <Button onClick={() => views.saveAs(`View ${views.views.length + 1}`)}>Save view</Button>
        }
        emptyState={<p className="p-8 text-center">No organisations yet.</p>}
        noResultsState={
          <p className="p-8 text-center">No organisations match. Clear the filters.</p>
        }
      />
      <p className="text-sm text-fg-muted" data-testid="opened">
        {opened ? `Opened ${opened}` : "Enter or click a row to open it."}
      </p>
    </div>
  );
}

export const DirectoryGrid: Story = {
  name: "Directory (200 rows)",
  render: () => <Directory count={200} />,
};

/** Performance check (Playwright, A-10-T10 acceptance): 10,000 rows scroll at 60 fps. */
export const TenThousandRows: Story = {
  render: () => <Directory count={10_000} />,
  // The a11y panel's axe run would compete with the measurement; axe covers the 200-row story.
  parameters: { a11y: { disable: true } },
};

export const Loading: Story = {
  render: () => (
    <DataGrid
      data={[]}
      columns={orgColumns}
      getRowId={(o) => o.id}
      getRowLabel={(o) => o.name}
      labels={gridLabels}
      status="loading"
      height={320}
    />
  ),
};

export const Empty: Story = {
  render: () => (
    <DataGrid
      data={[]}
      columns={orgColumns}
      getRowId={(o) => o.id}
      getRowLabel={(o) => o.name}
      labels={gridLabels}
      height={320}
      emptyState={
        <p className="p-8 text-center">No organisations yet. Create your first organisation.</p>
      }
    />
  ),
};

export const LoadError: Story = {
  render: () => (
    <DataGrid
      data={[]}
      columns={orgColumns}
      getRowId={(o) => o.id}
      getRowLabel={(o) => o.name}
      labels={gridLabels}
      height={320}
      status="error"
      errorState={<p className="p-8 text-center">Organisations couldn't be loaded. Try again.</p>}
    />
  ),
};
