import type { Meta, StoryObj } from "@storybook/react";

import { Button } from "../primitives/Button";
import {
  agingBuckets,
  agingLabels,
  cardLabels,
  emptyTiles,
  salesTiles,
  tileLabel,
} from "./fixtures";
import { AgingBar, OverviewCard, OverviewPage, OverviewTiles } from "./OverviewPage";

/**
 * Overview page (D-09-T06): one pattern for the sales and purchases overviews (gap-22) — status
 * tiles linking to the filtered list, independent cards with their own loading and error state,
 * and the aging bar.
 */
const meta: Meta<typeof OverviewPage> = { title: "Layout/Overview page", component: OverviewPage };
export default meta;
type Story = StoryObj<typeof OverviewPage>;

const topOwing = (
  <ul className="flex flex-col gap-2 text-sm">
    {[
      ["Lakeshore Hardware Ltd.", "$6,200.00"],
      ["Maple Leaf Cafés Inc.", "$3,410.50"],
      ["Northern Lights Studio", "$1,180.00"],
    ].map(([name, amount]) => (
      <li key={name} className="flex justify-between">
        <span>{name}</span>
        <span className="tabular-nums">{amount}</span>
      </li>
    ))}
  </ul>
);

export const Sales: Story = {
  render: () => (
    <OverviewPage
      kind="sales"
      title="Sales overview"
      intro="What you've invoiced and what's owed to you."
      actions={<Button variant="primary">New invoice</Button>}
      tiles={<OverviewTiles tiles={salesTiles} locale="en-CA" tileLabel={tileLabel} />}
    >
      <OverviewCard cardKey="aging" title="Money coming in" status="ready" labels={cardLabels} wide>
        <AgingBar buckets={agingBuckets} locale="en-CA" labels={agingLabels} />
      </OverviewCard>
      <OverviewCard
        cardKey="top"
        title="Customers owing the most"
        status="ready"
        labels={cardLabels}
      >
        {topOwing}
      </OverviewCard>
      <OverviewCard cardKey="quotes" title="Quotes" status="loading" labels={cardLabels} />
    </OverviewPage>
  ),
};

export const CardError: Story = {
  render: () => (
    <OverviewPage
      kind="purchases"
      title="Purchases overview"
      tiles={<OverviewTiles tiles={salesTiles} locale="en-CA" tileLabel={tileLabel} />}
    >
      <OverviewCard
        cardKey="aging"
        title="Money going out"
        status="error"
        labels={cardLabels}
        error={{
          title: "Money going out couldn't be loaded",
          body: "Your connection may have dropped. Try again in a moment.",
          reference: "web-7f3c2a10b44e91d0",
        }}
        onRetry={() => undefined}
      />
      <OverviewCard
        cardKey="top"
        title="Suppliers you owe the most"
        status="ready"
        labels={cardLabels}
      >
        {topOwing}
      </OverviewCard>
    </OverviewPage>
  ),
};

export const EmptyOrganisation: Story = {
  render: () => (
    <OverviewPage
      kind="sales"
      title="Sales overview"
      tiles={<OverviewTiles tiles={emptyTiles} locale="en-CA" tileLabel={tileLabel} />}
    >
      <OverviewCard cardKey="aging" title="Money coming in" status="ready" labels={cardLabels} wide>
        <AgingBar
          buckets={agingBuckets.map((b) => ({ ...b, amount: "0.00" }))}
          locale="en-CA"
          labels={agingLabels}
        />
      </OverviewCard>
    </OverviewPage>
  ),
};

export const Loading: Story = {
  render: () => (
    <OverviewPage
      kind="sales"
      title="Sales overview"
      tiles={<OverviewTiles tiles={[]} loading locale="en-CA" tileLabel={tileLabel} />}
    >
      <OverviewCard cardKey="aging" title="Money coming in" status="loading" labels={cardLabels} />
    </OverviewPage>
  ),
};
