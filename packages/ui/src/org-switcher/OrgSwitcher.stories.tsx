import type { Meta, StoryObj } from "@storybook/react";

import { OrgSwitcher } from "./OrgSwitcher";
import { manyOrganisations, sampleOrganisations, switcherLabels } from "./fixtures";

/**
 * Organisation switcher (A-01-T14): active organisation + practice badge in the top bar; the panel
 * lists the 5 recent organisations, searches every accessible organisation and links to the
 * practice directory. Shown on the black top bar it lives in.
 */
const meta: Meta<typeof OrgSwitcher> = {
  title: "Layout/OrgSwitcher",
  component: OrgSwitcher,
  decorators: [
    (Story) => (
      <div className="flex h-top-nav max-w-96 items-center bg-surface-inverse px-2">
        <Story />
      </div>
    ),
  ],
  parameters: { layout: "padded" },
  args: {
    labels: switcherLabels,
    active: sampleOrganisations[0]!,
    organisations: sampleOrganisations,
    recentIds: ["org-maple", "org-north", "org-erable", "org-bay", "org-rocky"],
    hrefFor: (org) => `/o/${org.id}/contacts`,
    onNavigate: () => undefined,
    directoryHref: "/p/profitex/directory",
  },
};

export default meta;
type Story = StoryObj<typeof OrgSwitcher>;

export const Accountant: Story = {};

export const DirectMember: Story = {
  args: {
    active: { id: "org-prairie", name: "Prairie Wheat Co-op" },
    organisations: [{ id: "org-prairie", name: "Prairie Wheat Co-op" }],
    recentIds: ["org-prairie"],
    directoryHref: undefined,
  },
};

export const TwoThousandOrganisations: Story = {
  args: (() => {
    const orgs = manyOrganisations(2000);
    return { organisations: orgs, active: orgs[0]!, recentIds: orgs.slice(0, 5).map((o) => o.id) };
  })(),
};

export const Loading: Story = { args: { status: "loading", organisations: [] } };

export const LoadError: Story = {
  args: { status: "error", organisations: [], onRetry: () => undefined },
};
