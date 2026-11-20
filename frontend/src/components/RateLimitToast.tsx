"use client";

/**
 * "You're going a little fast — retrying in 5 s" (S-06-T06): shown while the API client waits to
 * resend a rate-limited request (the `numo9:rate-limited` event of `auth/client.ts`), counting the
 * seconds down; it goes away by itself once the wait is over. Polite live region, never focus.
 */
import { useEffect, useState } from "react";

import { RATE_LIMIT_EVENT } from "@/auth/client";
import { defineMessages, useFormatMessage } from "@/i18n";

const messages = defineMessages({
  slowDown: {
    id: "common.rateLimit.retrying",
    defaultMessage: "You're going a little fast — retrying in {seconds, number} s",
    description: "Toast while a rate-limited request waits to be sent again (S-06-T06)",
  },
});

export function RateLimitToast() {
  const fm = useFormatMessage();
  const [left, setLeft] = useState(0);

  useEffect(() => {
    const onLimited = (event: Event) => {
      const seconds = Number((event as CustomEvent<{ seconds?: number }>).detail?.seconds);
      if (Number.isFinite(seconds) && seconds > 0) setLeft(Math.ceil(seconds));
    };
    window.addEventListener(RATE_LIMIT_EVENT, onLimited);
    return () => window.removeEventListener(RATE_LIMIT_EVENT, onLimited);
  }, []);

  useEffect(() => {
    if (left <= 0) return;
    const timer = setTimeout(() => setLeft((n) => n - 1), 1000);
    return () => clearTimeout(timer);
  }, [left]);

  return (
    <div
      // A polite live region from the start (so the first message is announced); the status
      // role only while it speaks — an empty status on every page would shadow the screens' own.
      role={left > 0 ? "status" : undefined}
      aria-live="polite"
      className="pointer-events-none fixed inset-x-0 bottom-4 z-50 flex justify-center px-4"
      data-rate-limit-toast=""
    >
      {left > 0 ? (
        <p className="pointer-events-auto rounded-md bg-surface-inverse px-4 py-2 text-sm text-fg-inverse shadow-lg">
          {fm(messages.slowDown, { seconds: left })}
        </p>
      ) : null}
    </div>
  );
}
