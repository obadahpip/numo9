import type { Meta, StoryObj } from "@storybook/react";

import { FoundingBadge, formatFoundingNumber } from "./FoundingBadge";

/**
 * Founding badge (U-08-T09): one of the first 1,000 organisations to pay — every product included
 * whatever the package. Shown on the organisation profile and, later, the client portal. The app
 * passes the translated label; the number is always four digits.
 */
const meta: Meta<typeof FoundingBadge> = {
  title: "Entitlements/FoundingBadge",
  component: FoundingBadge,
};
export default meta;
type Story = StoryObj<typeof FoundingBadge>;

export const SlotNumber: Story = {
  args: {
    slot: 427,
    label: `Founding organisation #${formatFoundingNumber(427)}`,
    description: "One of the first 1,000 organisations: every product is included.",
  },
};

export const FirstAndLast: Story = {
  render: () => (
    <div className="flex flex-col items-start gap-3">
      <FoundingBadge slot={1} label={`Founding organisation #${formatFoundingNumber(1)}`} />
      <FoundingBadge
        slot={1000}
        label={`Organisation fondatrice nº ${formatFoundingNumber(1000)}`}
      />
    </div>
  ),
};
