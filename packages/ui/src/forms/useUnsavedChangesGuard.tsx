"use client";

import { useCallback, useEffect, useState } from "react";

import { Button } from "../primitives/Button";
import { Dialog } from "../primitives/Dialog";

export interface UnsavedChangesGuard {
  /** URL the user tried to open while changes were unsaved; null when nothing is pending. */
  pending: string | null;
  leave: () => void;
  stay: () => void;
}

/**
 * Unsaved-changes guard (A-10-T07). While `active`:
 * - reload / close tab / typed URL → the browser's own "Leave site?" prompt (`beforeunload`);
 * - clicking an in-app link → `pending` is set so the app shows `UnsavedChangesDialog`.
 * "Leave" then navigates (`navigate`, default a full page load).
 */
export function useUnsavedChangesGuard(
  active: boolean,
  navigate: (href: string) => void = (href) => window.location.assign(href),
): UnsavedChangesGuard {
  const [pending, setPending] = useState<string | null>(null);

  useEffect(() => {
    if (!active) return;
    const onBeforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      // Required by some browsers to show the prompt; the text itself is not shown.
      event.returnValue = "";
    };
    const onClick = (event: MouseEvent) => {
      if (event.defaultPrevented || event.button !== 0) return;
      if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return; // new tab
      const link = (event.target as Element | null)?.closest?.("a[href]");
      if (!(link instanceof HTMLAnchorElement)) return;
      if (link.target && link.target !== "_self") return;
      if (link.hasAttribute("download")) return;
      const url = new URL(link.href, window.location.href);
      if (url.origin !== window.location.origin) return;
      if (url.pathname === window.location.pathname && url.hash) return; // in-page anchor
      event.preventDefault();
      event.stopPropagation();
      setPending(url.pathname + url.search + url.hash);
    };
    window.addEventListener("beforeunload", onBeforeUnload);
    document.addEventListener("click", onClick, true);
    return () => {
      window.removeEventListener("beforeunload", onBeforeUnload);
      document.removeEventListener("click", onClick, true);
    };
  }, [active]);

  const leave = useCallback(() => {
    const href = pending;
    setPending(null);
    if (href) navigate(href);
  }, [pending, navigate]);
  const stay = useCallback(() => setPending(null), []);

  return { pending, leave, stay };
}

export function UnsavedChangesDialog({
  guard,
  labels,
}: {
  guard: UnsavedChangesGuard;
  labels: { leaveTitle: string; leaveBody: string; stay: string; leave: string; close: string };
}) {
  return (
    <Dialog
      open={guard.pending !== null}
      onOpenChange={(open) => {
        if (!open) guard.stay();
      }}
      title={labels.leaveTitle}
      description={labels.leaveBody}
      closeLabel={labels.close}
      size="sm"
      footer={
        <>
          <Button variant="danger" onClick={guard.leave}>
            {labels.leave}
          </Button>
          <Button variant="primary" onClick={guard.stay}>
            {labels.stay}
          </Button>
        </>
      }
    />
  );
}
