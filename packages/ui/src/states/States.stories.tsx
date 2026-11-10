import type { Meta, StoryObj } from "@storybook/react";

import { Button } from "../primitives/Button";
import { EmptyState } from "./EmptyState";
import { ErrorState } from "./ErrorState";
import { ExplainPanel } from "./ExplainPanel";
import { LoadingRegion, Skeleton, SkeletonTable, SkeletonText } from "./Skeleton";

/**
 * State components (A-10-T12): every list and screen uses these for nothing-yet, loading, failure
 * and "not available" — never a blank area, a bare spinner or a silent redirect.
 */
const meta: Meta = { title: "States/Overview" };
export default meta;
type Story = StoryObj;

export const Empty: Story = {
  render: () => (
    <EmptyState
      illustration="contacts"
      title="No contacts yet"
      body="Customers and suppliers you add or import appear here."
      actions={[
        <Button key="new" variant="primary">
          New contact
        </Button>,
        <Button key="import">Import contacts</Button>,
      ]}
    />
  ),
};

export const NoResults: Story = {
  render: () => (
    <EmptyState
      illustration="search"
      title="No organisations match “retail QC”"
      body="Check the spelling, or clear the filters to see every organisation."
      actions={[<Button key="clear">Clear filters</Button>]}
    />
  ),
};

export const Loading: Story = {
  render: () => (
    <LoadingRegion label="Loading organisation…" className="grid max-w-xl gap-4">
      <div className="flex items-center gap-3">
        <Skeleton shape="circle" width={40} />
        <Skeleton width="40%" height="1rem" />
      </div>
      <SkeletonText lines={3} />
      <SkeletonTable rows={4} columns={4} />
    </LoadingRegion>
  ),
};

export const LoadError: Story = {
  render: () => (
    <ErrorState
      title="Organisations couldn't be loaded"
      body="The connection to Numo9 dropped. Nothing was lost — try again."
      retryLabel="Try again"
      onRetry={() => undefined}
      reportLabel="Report a problem"
      onReport={() => undefined}
      reference="7f3c2a10"
      referenceLabel={(ref) => `Reference: ${ref}`}
    />
  ),
};

export const Gated: Story = {
  render: () => (
    <ExplainPanel
      kind="gated"
      title="Payroll isn't in your package (Starter)"
      body="It's included in Growth and Complete. Your existing data stays available to view."
      fixer="Only the organisation owner can change the package."
      actions={[
        <Button key="compare" variant="primary">
          Compare packages
        </Button>,
        <Button key="ask">Ask the owner to upgrade</Button>,
      ]}
    />
  ),
};

export const Permission: Story = {
  render: () => (
    <ExplainPanel
      kind="permission"
      title="You can't approve bills over $5,000.00"
      body="Your approval limit for bills is $5,000.00. This bill is $5,001.00."
      fixer="Dana Lee (limit $25,000.00) can approve it."
      actions={[
        <Button key="send" variant="primary">
          Send to Dana Lee for approval
        </Button>,
      ]}
    />
  ),
};

export const Lock: Story = {
  render: () => (
    <ExplainPanel
      kind="lock"
      title="This period is locked"
      body="This entry is dated 15 Jun 2026, before the General Ledger lock date (30 Jun 2026)."
      fixer="Change the date, or ask an accountant to move the lock in Settings → Lock dates."
      actions={[<Button key="lock">Open lock dates</Button>]}
    />
  ),
};

export const NotFound: Story = {
  render: () => (
    <ExplainPanel
      kind="notFound"
      title="You don't have access to this organisation"
      body="It may have been unassigned from you."
      fixer="Ask your practice admin, or open your directory."
      actions={[
        <Button key="dir" variant="primary">
          Open directory
        </Button>,
      ]}
    />
  ),
};
