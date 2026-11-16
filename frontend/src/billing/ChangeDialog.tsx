"use client";

import { Button, Dialog } from "@numo9/ui";
import { useState } from "react";

import { defineMessages, useFormatMessage } from "@/i18n";

import { changePackage, type BillingSubscription, type Interval } from "./api";

const m = defineMessages({
  title: {
    id: "billing.change.title",
    defaultMessage: "Change to {package}?",
    description: "Dialog title",
  },
  body: {
    id: "billing.change.body",
    defaultMessage:
      "Your package changes to {package}, billed {interval, select, year {annually} other {monthly}}.",
    description: "Dialog body",
  },
  confirm: {
    id: "billing.change.confirm",
    defaultMessage: "Confirm change",
    description: "Button",
  },
  cancel: { id: "billing.change.cancel", defaultMessage: "Cancel", description: "Button" },
  close: { id: "billing.change.close", defaultMessage: "Close", description: "Dialog close" },
  done: {
    id: "billing.change.done",
    defaultMessage: "Your package is now {package}.",
    description: "Status after the change",
  },
  failed: {
    id: "billing.change.failed",
    defaultMessage: "The package didn't change. Try again in a moment.",
    description: "Error",
  },
});

/** Change the package of a paying organisation (U-04-T12; the proration comparison is T13). */
export function ChangeDialog({
  org,
  target,
  interval,
  onClose,
  onDone,
}: Readonly<{
  org: string;
  target: { code: string; name: string };
  interval: Interval;
  current: BillingSubscription | null;
  onClose: () => void;
  onDone: (message: string) => void;
}>) {
  const fm = useFormatMessage();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const confirm = async () => {
    setBusy(true);
    const answer = await changePackage(org, { package: target.code, interval });
    setBusy(false);
    if (answer.status === 200) onDone(fm(m.done, { package: target.name }));
    else setError(fm(m.failed));
  };

  return (
    <Dialog
      open
      onOpenChange={(open) => (open ? null : onClose())}
      title={fm(m.title, { package: target.name })}
      closeLabel={fm(m.close)}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            {fm(m.cancel)}
          </Button>
          <Button variant="primary" disabled={busy} onClick={() => void confirm()}>
            {fm(m.confirm)}
          </Button>
        </>
      }
    >
      <p>{fm(m.body, { package: target.name, interval })}</p>
      {error ? (
        <p role="alert" className="text-fg-danger">
          {error}
        </p>
      ) : null}
    </Dialog>
  );
}
