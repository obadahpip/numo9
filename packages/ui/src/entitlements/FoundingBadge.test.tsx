import { render, screen } from "@testing-library/react";

import { expectNoAxeViolations } from "../test/axe";
import { FoundingBadge, formatFoundingNumber } from "./FoundingBadge";

describe("FoundingBadge (U-08-T09)", () => {
  it("pads the slot number to four digits", () => {
    expect(formatFoundingNumber(427)).toBe("0427");
    expect(formatFoundingNumber(1)).toBe("0001");
    expect(formatFoundingNumber(1000)).toBe("1000");
  });

  it("shows the slot number in its text", async () => {
    const { container } = render(
      <FoundingBadge
        slot={427}
        label={`Founding organisation #${formatFoundingNumber(427)}`}
        description="One of the first 1,000 organisations"
      />,
    );
    const badge = screen.getByText("Founding organisation #0427");
    expect(badge.closest("[data-founding-slot]")?.getAttribute("data-founding-slot")).toBe("427");
    expect(badge.closest("[title]")?.getAttribute("title")).toBe(
      "One of the first 1,000 organisations",
    );
    await expectNoAxeViolations(container);
  });
});
