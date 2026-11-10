import type { Meta, StoryObj } from "@storybook/react";

import { AppShell } from "./AppShell";
import { sampleShell } from "./fixtures";

/**
 * Application shell (A-10-T05). Slots shown here with stand-ins: org switcher (A-01-T14), search
 * (A-09), job tray (A-08). Use the viewport toolbar to check 360 / 768 / 1024 / 1440 px.
 */
const OrgSwitcherStandIn = () => (
  <button
    type="button"
    className="flex h-9 min-w-0 items-center gap-2 rounded-md border border-border-inverse bg-surface-inverse-hover px-3 text-sm font-semibold text-fg-inverse"
  >
    <span className="truncate">Maple Leaf Supply Ltd.</span>
    <span aria-hidden="true">▾</span>
  </button>
);

const SearchStandIn = () => (
  <button
    type="button"
    className="flex h-9 w-60 items-center rounded-md border border-border-inverse bg-surface-inverse-hover px-3 text-sm text-fg-inverse-muted"
  >
    Search or jump to… Ctrl+K
  </button>
);

const JobTrayStandIn = () => (
  <button
    type="button"
    aria-label="Background jobs, 1 running"
    className="inline-flex size-touch-target items-center justify-center rounded-md text-fg-inverse hover:bg-surface-inverse-hover"
  >
    <span aria-hidden="true">⧗</span>
  </button>
);

const TrialChip = () => (
  <span className="rounded-full border border-yellow-600 bg-surface-accent-subtle px-3 py-0.5 text-xs font-semibold text-fg-accent-strong">
    Trial — 23 days left
  </span>
);

const meta: Meta<typeof AppShell> = {
  title: "Layout/AppShell",
  component: AppShell,
  parameters: { layout: "fullscreen" },
  args: {
    ...sampleShell,
    orgSwitcher: <OrgSwitcherStandIn />,
    search: <SearchStandIn />,
    jobTray: <JobTrayStandIn />,
    status: <TrialChip />,
    children: (
      <>
        <h1 className="text-2xl font-bold">Home</h1>
        <p className="mt-2 text-fg-muted">Page content goes here.</p>
      </>
    ),
  },
};
export default meta;

type Story = StoryObj<typeof AppShell>;

export const Organisation: Story = {};

export const OrganisationWithoutPractice: Story = {
  args: { practiceNav: undefined, status: undefined },
};

export const EmptySlots: Story = {
  args: {
    orgSwitcher: undefined,
    search: undefined,
    jobTray: undefined,
    status: undefined,
    practiceNav: undefined,
    notifications: { label: "Notifications" },
    user: { label: "Account menu", items: [] },
  },
};

export const Phone: Story = {
  parameters: { viewport: { defaultViewport: "sm" } },
};

export const Tablet: Story = {
  parameters: { viewport: { defaultViewport: "md" } },
};
