"use client";

import * as RadixDialog from "@radix-ui/react-dialog";
import type { ReactNode } from "react";

import { CloseIcon } from "../shell/icons";
import { cn } from "./cn";

export interface DialogProps {
  open?: boolean;
  defaultOpen?: boolean;
  onOpenChange?: (open: boolean) => void;
  /** Element that opens the dialog (rendered as the Radix trigger, `asChild`). */
  trigger?: ReactNode;
  /** Required: names the dialog for screen readers. */
  title: ReactNode;
  description?: ReactNode;
  /** Accessible name of the × button, e.g. "Close". */
  closeLabel: string;
  /** Action buttons, primary last (end side). */
  footer?: ReactNode;
  children?: ReactNode;
  size?: "sm" | "md" | "lg";
  /** Prevent closing by Esc / outside click (e.g. a typed confirmation in progress). */
  dismissible?: boolean;
}

const SIZES = { sm: "max-w-sm", md: "max-w-lg", lg: "max-w-3xl" } as const;

const OVERLAY = "fixed inset-0 z-50 bg-surface-inverse/50";

/**
 * Modal dialog (A-10-T06, Radix): focus is trapped inside and returns to the trigger on close;
 * Esc and the × close it. Use for decisions that block the task; prefer an Undo toast for
 * reversible actions (Phase 0 UX principle 8).
 */
export function Dialog({
  open,
  defaultOpen,
  onOpenChange,
  trigger,
  title,
  description,
  closeLabel,
  footer,
  children,
  size = "md",
  dismissible = true,
}: DialogProps) {
  const block = (event: Event) => {
    if (!dismissible) event.preventDefault();
  };
  return (
    <RadixDialog.Root open={open} defaultOpen={defaultOpen} onOpenChange={onOpenChange}>
      {trigger ? <RadixDialog.Trigger asChild>{trigger}</RadixDialog.Trigger> : null}
      <RadixDialog.Portal>
        <RadixDialog.Overlay className={OVERLAY} />
        <RadixDialog.Content
          onEscapeKeyDown={block}
          onPointerDownOutside={block}
          className={cn(
            "fixed start-1/2 top-1/2 z-50 flex max-h-[90vh] w-[calc(100vw-2rem)] -translate-x-1/2 -translate-y-1/2 flex-col rounded-lg bg-surface text-fg shadow-elevation-4 rtl:translate-x-1/2",
            SIZES[size],
          )}
          {...(description ? {} : { "aria-describedby": undefined })}
        >
          <Header title={title} description={description} closeLabel={closeLabel} />
          {children ? <div className="overflow-y-auto px-6 pb-4 text-sm">{children}</div> : null}
          {footer ? (
            <div className="flex flex-wrap justify-end gap-2 border-t border-border px-6 py-4">
              {footer}
            </div>
          ) : null}
        </RadixDialog.Content>
      </RadixDialog.Portal>
    </RadixDialog.Root>
  );
}

function Header({
  title,
  description,
  closeLabel,
}: {
  title: ReactNode;
  description?: ReactNode;
  closeLabel: string;
}) {
  return (
    <div className="flex items-start gap-4 px-6 pt-5 pb-3">
      <div className="min-w-0 flex-1">
        <RadixDialog.Title className="text-lg font-semibold">{title}</RadixDialog.Title>
        {description ? (
          <RadixDialog.Description className="mt-1 text-sm text-fg-muted">
            {description}
          </RadixDialog.Description>
        ) : null}
      </div>
      <RadixDialog.Close
        aria-label={closeLabel}
        className="-me-3 -mt-2 inline-flex size-touch-target shrink-0 items-center justify-center rounded-md text-fg-muted hover:bg-surface-muted"
      >
        <CloseIcon />
      </RadixDialog.Close>
    </div>
  );
}

export interface DrawerProps extends Omit<DialogProps, "size" | "dismissible"> {
  /** Width on larger screens; full width below 768 px. */
  size?: "sm" | "md" | "lg";
  side?: "end" | "start";
}

const DRAWER_SIZES = { sm: "md:w-80", md: "md:w-[28rem]", lg: "md:w-[40rem]" } as const;

/**
 * Drawer (A-10-T06): a modal side panel (history, notification centre, record preview) that
 * slides from the end edge (right in English and French, left in RTL). Same focus rules as
 * `Dialog`.
 */
export function Drawer({
  open,
  defaultOpen,
  onOpenChange,
  trigger,
  title,
  description,
  closeLabel,
  footer,
  children,
  size = "md",
  side = "end",
}: DrawerProps) {
  return (
    <RadixDialog.Root open={open} defaultOpen={defaultOpen} onOpenChange={onOpenChange}>
      {trigger ? <RadixDialog.Trigger asChild>{trigger}</RadixDialog.Trigger> : null}
      <RadixDialog.Portal>
        <RadixDialog.Overlay className={OVERLAY} />
        <RadixDialog.Content
          data-drawer-side={side}
          className={cn(
            "fixed inset-y-0 z-50 flex w-full flex-col bg-surface text-fg shadow-elevation-4",
            side === "end" ? "end-0" : "start-0",
            DRAWER_SIZES[size],
          )}
          {...(description ? {} : { "aria-describedby": undefined })}
        >
          <Header title={title} description={description} closeLabel={closeLabel} />
          <div className="flex-1 overflow-y-auto px-6 pb-4 text-sm">{children}</div>
          {footer ? (
            <div className="flex flex-wrap justify-end gap-2 border-t border-border px-6 py-4">
              {footer}
            </div>
          ) : null}
        </RadixDialog.Content>
      </RadixDialog.Portal>
    </RadixDialog.Root>
  );
}

/** Closes the surrounding Dialog/Drawer, e.g. `<DialogClose asChild><Button>Cancel</Button></DialogClose>`. */
export const DialogClose = RadixDialog.Close;
