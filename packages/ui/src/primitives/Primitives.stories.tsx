import type { Meta, StoryObj } from "@storybook/react";
import { useState } from "react";

import { Badge } from "./Badge";
import { Button } from "./Button";
import { Checkbox } from "./Checkbox";
import { Combobox } from "./Combobox";
import { Dialog, DialogClose, Drawer } from "./Dialog";
import { IconButton } from "./IconButton";
import { Input } from "./Input";
import { RadioGroup } from "./Radio";
import { Select } from "./Select";
import { STATUS_TONES, StatusBadge, type StatusKey } from "./StatusBadge";
import { Switch } from "./Switch";
import { Tabs } from "./Tabs";
import { ToastProvider, useToast } from "./Toast";
import { Tooltip } from "./Tooltip";

/**
 * Primitives (A-10-T06): Radix-based controls in the Numo9 tokens. Every control is keyboard
 * operable, has a visible focus ring and a 44 px target; the a11y panel runs axe on each story.
 * Sample text is Canadian English; apps pass i18n messages.
 */
const meta: Meta = { title: "Primitives/Overview" };
export default meta;
type Story = StoryObj;

const Plus = () => (
  <svg
    width="20"
    height="20"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    aria-hidden="true"
  >
    <path d="M12 5v14M5 12h14" />
  </svg>
);

export const Buttons: Story = {
  render: () => (
    <div className="flex flex-wrap items-center gap-3">
      <Button variant="primary">Save settings</Button>
      <Button>Preview statement</Button>
      <Button variant="ghost">Cancel</Button>
      <Button variant="danger">Delete draft</Button>
      <Button variant="link">See plans</Button>
      <Button variant="primary" loading>
        Posting journal
      </Button>
      <Button disabled>Approve bill</Button>
      <Button size="sm">Add tag</Button>
      <IconButton label="Add line" icon={<Plus />} variant="secondary" />
    </div>
  ),
};

export const TextInputs: Story = {
  render: () => (
    <div className="grid max-w-md gap-4">
      <label className="grid gap-1 text-sm font-medium">
        Legal name
        <Input defaultValue="Maple Leaf Supply Ltd." />
      </label>
      <label className="grid gap-1 text-sm font-medium">
        Amount
        <Input numeric prefix="$" suffix="CAD" defaultValue="1,234.56" />
      </label>
      <label className="grid gap-1 text-sm font-medium">
        Postal code (invalid)
        <Input invalid defaultValue="M5V2T" />
      </label>
      <label className="grid gap-1 text-sm font-medium">
        Business number (read-only)
        <Input readOnly defaultValue="123456789RT0001" />
      </label>
    </div>
  ),
};

function SelectDemo() {
  const [province, setProvince] = useState("ON");
  return (
    <div className="grid max-w-md gap-1 text-sm font-medium">
      <span id="province-label">Province</span>
      <Select
        aria-labelledby="province-label"
        value={province}
        onValueChange={setProvince}
        options={[
          { value: "AB", label: "Alberta" },
          { value: "BC", label: "British Columbia" },
          { value: "ON", label: "Ontario" },
          { value: "QC", label: "Quebec" },
        ]}
      />
    </div>
  );
}
export const SelectStory: Story = { name: "Select", render: () => <SelectDemo /> };

function ComboboxDemo() {
  const [value, setValue] = useState<string | null>(null);
  return (
    <div className="grid max-w-md gap-1 text-sm font-medium">
      <label htmlFor="account-demo">Account</label>
      <Combobox
        id="account-demo"
        value={value}
        onChange={setValue}
        placeholder="Type a code or name"
        emptyMessage="No accounts match. Try the account code."
        options={[
          { value: "1000", label: "1000 · Chequing", group: "Assets", keywords: "bank" },
          { value: "1200", label: "1200 · Accounts receivable", group: "Assets" },
          { value: "2100", label: "2100 · GST/HST payable", group: "Liabilities" },
          { value: "4000", label: "4000 · Sales", group: "Revenue" },
          { value: "5400", label: "5400 · Vacation pay expense", group: "Expenses" },
        ]}
      />
    </div>
  );
}
export const ComboboxStory: Story = { name: "Combobox", render: () => <ComboboxDemo /> };

export const Choices: Story = {
  render: () => (
    <div className="grid max-w-md gap-2">
      <Checkbox label="Include archived contacts" description="Archived contacts stay searchable" />
      <Checkbox aria-label="Select all rows" checked="indeterminate" />
      <RadioGroup
        aria-label="Time format"
        defaultValue="12h"
        options={[
          { value: "12h", label: "12-hour (1:30 p.m.)" },
          { value: "24h", label: "24-hour (13:30)" },
        ]}
      />
      <Switch label="Compact density" description="Shows more rows on each screen" />
    </div>
  ),
};

export const Overlays: Story = {
  render: () => (
    <div className="flex flex-wrap gap-3">
      <Dialog
        trigger={<Button variant="danger">Archive organisation</Button>}
        title="Archive Maple Leaf Supply Ltd.?"
        description="It leaves your directory. You can restore it from Archived."
        closeLabel="Close"
        footer={
          <>
            <DialogClose asChild>
              <Button>Keep organisation</Button>
            </DialogClose>
            <Button variant="danger">Archive organisation</Button>
          </>
        }
      />
      <Drawer trigger={<Button>Open history</Button>} title="History" closeLabel="Close">
        <p>15 Oct 2026, 4:33 p.m. — Dana Lee changed the legal name.</p>
      </Drawer>
      <Tooltip content="Saves without leaving the page (Ctrl+S)">
        <Button variant="primary">Save</Button>
      </Tooltip>
    </div>
  ),
};

function ToastDemo() {
  const { toast } = useToast();
  return (
    <div className="flex gap-3">
      <Button
        onClick={() =>
          toast({
            title: "3 organisations added to Toronto office → Retail",
            tone: "success",
            undo: {
              label: "Undo",
              altText: "Undo from Bulk edit history",
              onUndo: () => undefined,
            },
          })
        }
      >
        Group organisations
      </Button>
      <Button
        onClick={() =>
          toast({
            title: "Statement wasn't sent",
            description: "The email address bounced. Correct it on the contact, then send again.",
            tone: "danger",
          })
        }
      >
        Show an error
      </Button>
    </div>
  );
}
export const Toasts: Story = {
  render: () => (
    <ToastProvider labels={{ region: "Notifications ({hotkey})", close: "Dismiss" }}>
      <ToastDemo />
    </ToastProvider>
  ),
};

export const TabsStory: Story = {
  name: "Tabs",
  render: () => (
    <Tabs
      label="Contact roles"
      items={[
        { value: "all", label: "All contacts", count: 128, content: <p>All contacts list</p> },
        { value: "customers", label: "Customers", count: 84, content: <p>Customers list</p> },
        { value: "suppliers", label: "Suppliers", count: 44, content: <p>Suppliers list</p> },
      ]}
    />
  ),
};

export const Badges: Story = {
  render: () => (
    <div className="grid gap-3">
      <div className="flex flex-wrap gap-2">
        <Badge>Bank</Badge>
        <Badge tone="accent">Founding #214</Badge>
        <Badge tone="info">Demo — sample data</Badge>
        <Badge tone="inverse">GIFI 1000</Badge>
      </div>
      <div className="flex flex-wrap gap-2">
        {(Object.keys(STATUS_TONES) as StatusKey[]).map((status) => (
          <StatusBadge key={status} status={status} label={status.replace(/_/g, " ")} />
        ))}
      </div>
    </div>
  ),
};
