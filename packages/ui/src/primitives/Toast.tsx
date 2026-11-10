"use client";

import * as RadixToast from "@radix-ui/react-toast";
import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

import { CloseIcon } from "../shell/icons";
import { cn } from "./cn";

export type ToastTone = "neutral" | "success" | "danger";

export interface ToastOptions {
  /** What happened, naming the record: "Maple Leaf Supply Ltd. archived". */
  title: string;
  description?: string;
  tone?: ToastTone;
  /**
   * Undo (Phase 0 UX principle 8): reversible actions show Undo instead of a confirmation.
   * `altText` tells screen-reader users how to undo another way (e.g. "Undo from History").
   */
  undo?: { label: string; altText: string; onUndo: () => void };
  /** Milliseconds before the toast closes; default 10 s (undo window), errors stay 15 s. */
  duration?: number;
}

interface ActiveToast extends ToastOptions {
  id: number;
  open: boolean;
}

interface ToastApi {
  /** Show a toast; returns its id. */
  toast: (options: ToastOptions) => number;
  dismiss: (id: number) => void;
}

const ToastContext = createContext<ToastApi | null>(null);

export interface ToastProviderProps {
  children: ReactNode;
  labels: {
    /** Name of the toast region; `{hotkey}` is replaced by the shortcut (F8). */
    region: string;
    /** Accessible name of each toast's × button. */
    close: string;
  };
}

export const UNDO_DURATION_MS = 10_000;

const TONES: Record<ToastTone, string> = {
  neutral: "border-border",
  success: "border-s-4 border-s-green-700 border-border",
  danger: "border-s-4 border-s-red-700 border-border",
};

/**
 * Toasts (A-10-T06, Radix): brief status messages announced in a live region (polite; errors
 * assertive), with an optional Undo action. Pausing on hover/focus, F8 jumps to the region, swipe
 * to dismiss on touch. Wrap the app once; call `useToast().toast({...})`.
 */
export function ToastProvider({ children, labels }: ToastProviderProps) {
  const [toasts, setToasts] = useState<ActiveToast[]>([]);
  const nextId = useRef(1);

  const dismiss = useCallback((id: number) => {
    setToasts((list) => list.map((t) => (t.id === id ? { ...t, open: false } : t)));
    // Remove after the close animation.
    setTimeout(() => setToasts((list) => list.filter((t) => t.id !== id)), 300);
  }, []);

  const toast = useCallback((options: ToastOptions) => {
    const id = nextId.current++;
    setToasts((list) => [...list, { ...options, id, open: true }]);
    return id;
  }, []);

  const api = useMemo(() => ({ toast, dismiss }), [toast, dismiss]);

  return (
    <ToastContext.Provider value={api}>
      <RadixToast.Provider swipeDirection="right" label={labels.region}>
        {children}
        {toasts.map((t) => (
          <RadixToast.Root
            key={t.id}
            open={t.open}
            onOpenChange={(open) => {
              if (!open) dismiss(t.id);
            }}
            type={t.tone === "danger" ? "foreground" : "background"}
            duration={t.duration ?? (t.tone === "danger" ? 15_000 : UNDO_DURATION_MS)}
            data-tone={t.tone ?? "neutral"}
            className={cn(
              "flex w-full items-start gap-3 rounded-lg border bg-surface p-4 text-fg shadow-elevation-3",
              TONES[t.tone ?? "neutral"],
            )}
          >
            <div className="min-w-0 flex-1">
              <RadixToast.Title className="text-sm font-semibold">{t.title}</RadixToast.Title>
              {t.description ? (
                <RadixToast.Description className="mt-0.5 text-sm text-fg-muted">
                  {t.description}
                </RadixToast.Description>
              ) : null}
            </div>
            {t.undo ? (
              <RadixToast.Action
                altText={t.undo.altText}
                onClick={() => t.undo?.onUndo()}
                className="min-h-touch-target shrink-0 rounded-md px-3 text-sm font-bold text-fg-link underline hover:bg-surface-muted"
              >
                {t.undo.label}
              </RadixToast.Action>
            ) : null}
            <RadixToast.Close
              aria-label={labels.close}
              className="-me-2 -mt-2 inline-flex size-touch-target shrink-0 items-center justify-center rounded-md text-fg-muted hover:bg-surface-muted"
            >
              <CloseIcon />
            </RadixToast.Close>
          </RadixToast.Root>
        ))}
        <RadixToast.Viewport className="fixed end-0 bottom-0 z-[60] flex w-full max-w-sm flex-col gap-2 p-4 outline-none" />
      </RadixToast.Provider>
    </ToastContext.Provider>
  );
}

/** Toast API of the nearest `ToastProvider`. */
export function useToast(): ToastApi {
  const api = useContext(ToastContext);
  if (!api) throw new Error("useToast() must be used inside <ToastProvider>.");
  return api;
}
