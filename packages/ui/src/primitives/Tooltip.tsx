"use client";

import * as RadixTooltip from "@radix-ui/react-tooltip";
import type { ReactElement, ReactNode } from "react";

export interface TooltipProps {
  content: ReactNode;
  /** The trigger: one focusable element (a button or link). */
  children: ReactElement;
  side?: "top" | "right" | "bottom" | "left";
  delayDuration?: number;
}

/**
 * Tooltip (A-10-T06, Radix): supplementary text on hover and keyboard focus, dismissed with Esc.
 * Never the only place information lives — touch users don't hover. Works without a provider;
 * wrap the app in `TooltipProvider` to share the delay between tooltips.
 */
export function Tooltip({ content, children, side = "top", delayDuration = 400 }: TooltipProps) {
  return (
    <RadixTooltip.Provider delayDuration={delayDuration}>
      <RadixTooltip.Root>
        <RadixTooltip.Trigger asChild>{children}</RadixTooltip.Trigger>
        <RadixTooltip.Portal>
          <RadixTooltip.Content
            side={side}
            sideOffset={6}
            className="z-50 max-w-xs rounded-md bg-surface-inverse px-2 py-1 text-xs text-fg-inverse shadow-elevation-2"
          >
            {content}
            <RadixTooltip.Arrow className="fill-surface-inverse" />
          </RadixTooltip.Content>
        </RadixTooltip.Portal>
      </RadixTooltip.Root>
    </RadixTooltip.Provider>
  );
}

export const TooltipProvider = RadixTooltip.Provider;
