"use client";

/**
 * Demo bar (U-07-T12): on every page of a demo organisation, in the shell's banner slot — a
 * "Demo" watermark tag over subtle diagonal stripes, what the demo is, and its three actions:
 * Reset demo (confirm, then a progress bar until the sample data is back), Start my free trial
 * (name the new organisation; anonymous visitors are sent to sign up) and the Demo outbox (the
 * emails it would have sent). Nothing shows outside a demo.
 */
import { Button, Dialog, Drawer, formatDateTime, Input, type AppLocale } from "@numo9/ui";
import { useLocale } from "next-intl";
import { useState } from "react";

import { firstError } from "@/contacts/api";
import { useEntitlements } from "@/entitlements/store";
import { useFormatMessage } from "@/i18n";
import { orgModuleUrl } from "@/routing/routes";

import { demoApi, type DemoOutboxItem } from "./api";
import { dm } from "./messages";

export const DEMO_TOUR_EVENT = "numo9:demo-tour";

export function DemoBar({ org }: { org: string }) {
  const entitlements = useEntitlements();
  if (entitlements.data?.reason !== "demo") return null;
  return <DemoBarContent org={org} />;
}

function DemoBarContent({ org }: { org: string }) {
  const fm = useFormatMessage();
  const locale = useLocale() as AppLocale;
  const [dialog, setDialog] = useState<"reset" | "trial" | "outbox" | null>(null);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const [signUp, setSignUp] = useState(false);
  const [name, setName] = useState("");
  const [outbox, setOutbox] = useState<DemoOutboxItem[] | null>(null);

  const reset = async () => {
    setBusy(true);
    setError("");
    const result = await demoApi.reset(org);
    setBusy(false);
    setDialog(null);
    if (result.status === 200) {
      setStatus(fm(dm.resetDone));
      window.location.reload();
    } else {
      setError(fm(dm.failed, { reason: firstError(result.body) ?? "" }));
    }
  };

  const convert = async () => {
    setBusy(true);
    setError("");
    setSignUp(false);
    const result = await demoApi.convert(org, name);
    setBusy(false);
    if (result.status === 201) {
      window.location.assign(orgModuleUrl(result.body.id, "home"));
      return;
    }
    const code = (result.body as { code?: string } | null)?.code;
    if (code === "demo.sign_up_first") setSignUp(true);
    else setError(fm(dm.failed, { reason: firstError(result.body) ?? "" }));
  };

  const openOutbox = async () => {
    setDialog("outbox");
    const result = await demoApi.outbox(org);
    setOutbox(result.status === 200 ? result.body.results : []);
  };

  return (
    <section
      aria-label={fm(dm.region)}
      data-demo-bar=""
      className="demo-bar flex flex-wrap items-center gap-3 border-b border-border px-4 py-2 text-sm"
      style={{
        backgroundImage:
          "repeating-linear-gradient(135deg, rgba(255, 209, 0, 0.18) 0 12px, transparent 12px 24px)",
      }}
    >
      <span
        className="inline-block -rotate-6 rounded-sm border-2 border-fg px-2 text-xs font-bold tracking-widest uppercase"
        data-demo-watermark=""
      >
        {fm(dm.tag)}
      </span>
      <p className="min-w-0 flex-1">{fm(dm.text)}</p>
      <Button size="sm" onClick={() => setDialog("reset")}>
        {fm(dm.reset)}
      </Button>
      <Button size="sm" onClick={() => void openOutbox()}>
        {fm(dm.outbox)}
      </Button>
      <Button size="sm" onClick={() => window.dispatchEvent(new Event(DEMO_TOUR_EVENT))}>
        {fm(dm.tour)}
      </Button>
      <Button size="sm" variant="primary" onClick={() => setDialog("trial")}>
        {fm(dm.trial)}
      </Button>
      <p role="status" className="sr-only">
        {status}
      </p>
      {error ? (
        <p role="alert" className="w-full text-fg-danger">
          {error}
        </p>
      ) : null}

      <Dialog
        open={dialog === "reset"}
        onOpenChange={(open) => (open || busy ? undefined : setDialog(null))}
        title={fm(dm.resetTitle)}
        description={fm(dm.resetText)}
        closeLabel={fm(dm.close)}
        dismissible={!busy}
        size="sm"
        footer={
          busy ? null : (
            <>
              <Button onClick={() => setDialog(null)}>{fm(dm.cancel)}</Button>
              <Button variant="primary" onClick={() => void reset()}>
                {fm(dm.resetConfirm)}
              </Button>
            </>
          )
        }
      >
        {busy ? (
          <div className="flex flex-col gap-2" data-demo-reset-progress="">
            <span id="demo-reset-progress">{fm(dm.resetting)}</span>
            <div
              role="progressbar"
              aria-labelledby="demo-reset-progress"
              className="h-2 w-full overflow-hidden rounded-full bg-surface-sunken"
            >
              <div className="h-full w-1/2 animate-pulse rounded-full bg-surface-accent" />
            </div>
          </div>
        ) : null}
      </Dialog>

      <Dialog
        open={dialog === "trial"}
        onOpenChange={(open) => (open ? undefined : setDialog(null))}
        title={fm(dm.trialTitle)}
        description={fm(dm.trialText)}
        closeLabel={fm(dm.close)}
        size="sm"
        footer={
          <>
            <Button onClick={() => setDialog(null)}>{fm(dm.cancel)}</Button>
            <Button
              variant="primary"
              disabled={busy || !name.trim()}
              onClick={() => void convert()}
            >
              {fm(dm.trialConfirm)}
            </Button>
          </>
        }
      >
        <label className="flex flex-col gap-1 text-sm">
          {fm(dm.trialName)}
          <Input value={name} onChange={(event) => setName(event.target.value)} />
        </label>
        {signUp ? (
          <p className="mt-2 text-sm">
            <a href="/signup" className="font-semibold underline">
              {fm(dm.signUpFirst)}
            </a>
          </p>
        ) : null}
      </Dialog>

      <Drawer
        open={dialog === "outbox"}
        onOpenChange={(open) => (open ? undefined : setDialog(null))}
        title={fm(dm.outboxTitle)}
        description={fm(dm.outboxText)}
        closeLabel={fm(dm.close)}
        size="md"
      >
        {outbox && outbox.length === 0 ? (
          <p className="text-sm text-fg-muted">{fm(dm.outboxEmpty)}</p>
        ) : (
          <ul className="flex flex-col divide-y divide-border">
            {(outbox ?? []).map((item) => (
              <li key={item.id} className="flex flex-col gap-1 py-3 text-sm">
                <span className="font-semibold">{item.subject}</span>
                <span className="text-fg-muted">
                  {fm(dm.outboxLine, {
                    to: item.to_email,
                    when: formatDateTime(item.created_at, { locale }),
                  })}
                </span>
                <span className="whitespace-pre-line">{item.text_body}</span>
              </li>
            ))}
          </ul>
        )}
      </Drawer>
    </section>
  );
}
