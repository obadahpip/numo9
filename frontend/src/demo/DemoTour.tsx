"use client";

/**
 * Guided demo tour (U-07-T13): six short steps, our own component in the design system's Dialog
 * (focus trapped, Esc closes). It opens by itself the first time a demo is opened in this browser;
 * Skip, Esc, × and Finish all dismiss it and the dismissal is remembered (localStorage — a
 * per-viewer convenience; when storage is unavailable the tour simply opens again next time).
 * "Take the tour" on the demo bar opens it again at step 1.
 */
import { Button, Dialog } from "@numo9/ui";
import { useEffect, useState } from "react";

import { useEntitlements } from "@/entitlements/store";
import { useFormatMessage } from "@/i18n";

import { DEMO_TOUR_EVENT } from "./DemoBar";
import { tm } from "./tourMessages";

export const TOUR_KEY = "numo9.demoTour.dismissed";

const STEPS = [
  [tm.s1Title, tm.s1Text],
  [tm.s2Title, tm.s2Text],
  [tm.s3Title, tm.s3Text],
  [tm.s4Title, tm.s4Text],
  [tm.s5Title, tm.s5Text],
  [tm.s6Title, tm.s6Text],
] as const;

function dismissed(): boolean {
  try {
    return window.localStorage.getItem(TOUR_KEY) === "1";
  } catch {
    return false;
  }
}

function remember(): void {
  try {
    window.localStorage.setItem(TOUR_KEY, "1");
  } catch {
    // Storage unavailable (private mode, blocked): the tour just opens again next time.
  }
}

export function DemoTour() {
  const entitlements = useEntitlements();
  const demo = entitlements.data?.reason === "demo";
  const fm = useFormatMessage();
  const [open, setOpen] = useState(false);
  const [step, setStep] = useState(0);

  useEffect(() => {
    if (demo && !dismissed()) setOpen(true);
    const reopen = () => {
      setStep(0);
      setOpen(true);
    };
    window.addEventListener(DEMO_TOUR_EVENT, reopen);
    return () => window.removeEventListener(DEMO_TOUR_EVENT, reopen);
  }, [demo]);

  if (!demo) return null;
  const close = () => {
    remember();
    setOpen(false);
  };
  const [title, text] = STEPS[step] ?? STEPS[0];
  const last = step === STEPS.length - 1;

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => (next ? setOpen(true) : close())}
      title={fm(tm.title, { title: fm(title), step: step + 1, total: STEPS.length })}
      closeLabel={fm(tm.close)}
      size="sm"
      footer={
        <>
          <Button onClick={close}>{fm(tm.skip)}</Button>
          {step > 0 ? <Button onClick={() => setStep(step - 1)}>{fm(tm.back)}</Button> : null}
          <Button variant="primary" onClick={() => (last ? close() : setStep(step + 1))}>
            {fm(last ? tm.done : tm.next)}
          </Button>
        </>
      }
    >
      <p className="text-sm" data-tour-step={step + 1}>
        {fm(text)}
      </p>
    </Dialog>
  );
}
