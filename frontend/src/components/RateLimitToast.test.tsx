import { act, screen } from "@testing-library/react";
import { vi } from "vitest";

import { RATE_LIMIT_EVENT } from "@/auth/client";
import { renderWithIntl } from "@/test/intl";

import { expectNoAxeViolations } from "../../../packages/ui/src/test/axe";
import { RateLimitToast } from "./RateLimitToast";

/** S-06-T06 — friendly toast while a rate-limited request waits to be sent again. */
afterEach(() => vi.useRealTimers());

it("shows the countdown on a rate-limit wait and goes away by itself", async () => {
  vi.useFakeTimers();
  const { container } = renderWithIntl(<RateLimitToast />);
  const region = container.querySelector<HTMLElement>("[data-rate-limit-toast]")!;
  expect(region).toHaveAttribute("aria-live", "polite");
  expect(region).toBeEmptyDOMElement();
  expect(screen.queryByRole("status")).not.toBeInTheDocument();
  act(() => {
    window.dispatchEvent(new CustomEvent(RATE_LIMIT_EVENT, { detail: { seconds: 5 } }));
  });
  expect(region).toHaveTextContent("You're going a little fast — retrying in 5 s");
  expect(screen.getByRole("status")).toBe(region);
  const tick = (seconds: number) => {
    for (let n = 0; n < seconds; n += 1)
      act(() => {
        vi.advanceTimersByTime(1000);
      });
  };
  tick(2);
  expect(region).toHaveTextContent("retrying in 3 s");
  tick(3);
  expect(region).toBeEmptyDOMElement();
  vi.useRealTimers();
  await expectNoAxeViolations(container);
});
