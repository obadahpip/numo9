"use client";

import { useEffect, useRef } from "react";

export interface ErrorSummaryItem {
  /** Field name, e.g. "address.postalCode". */
  name: string;
  /** id of the field's control (link target). */
  id: string;
  /** Field label, shown before the message when known. */
  label?: string;
  message: string;
}

/**
 * Error summary (A-10-T07) at the top of a form after a failed submit: how many problems, each a
 * link that moves focus to its field. Announced by screen readers (`role="alert"`).
 */
export function ErrorSummary({ title, items }: { title: string; items: ErrorSummaryItem[] }) {
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    heading.current?.scrollIntoView?.({ block: "nearest" });
  }, []);
  return (
    <div
      role="alert"
      data-error-summary=""
      className="mb-6 rounded-lg border-2 border-border-danger bg-surface-danger-subtle p-4"
    >
      <h2 ref={heading} className="text-base font-semibold text-fg-danger">
        {title}
      </h2>
      <ul className="mt-2 list-disc ps-5 text-sm">
        {items.map((item) => (
          <li key={item.name}>
            <a
              href={`#${item.id}`}
              className="font-medium text-fg-danger underline"
              onClick={(event) => {
                const target = document.getElementById(item.id);
                if (target) {
                  event.preventDefault();
                  target.focus();
                  target.scrollIntoView?.({ block: "center" });
                }
              }}
            >
              {item.label ? `${item.label}: ${item.message}` : item.message}
            </a>
          </li>
        ))}
      </ul>
    </div>
  );
}
