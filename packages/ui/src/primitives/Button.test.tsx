import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { expectNoAxeViolations } from "../test/axe";
import { Badge } from "./Badge";
import { Button } from "./Button";
import { IconButton } from "./IconButton";
import { StatusBadge, STATUS_TONES } from "./StatusBadge";

const PlusIcon = () => <svg aria-hidden="true" />;

describe("Button (A-10-T06)", () => {
  it("is a type=button by default and fires onClick", async () => {
    const onClick = vi.fn();
    render(<Button onClick={onClick}>Save settings</Button>);
    const button = screen.getByRole("button", { name: "Save settings" });
    expect(button).toHaveAttribute("type", "button");
    await userEvent.click(button);
    expect(onClick).toHaveBeenCalledOnce();
  });

  it("loading: busy, keeps its name, ignores clicks", async () => {
    const onClick = vi.fn();
    render(
      <Button variant="primary" loading onClick={onClick}>
        Save settings
      </Button>,
    );
    const button = screen.getByRole("button", { name: "Save settings" });
    expect(button).toHaveAttribute("aria-busy", "true");
    await userEvent.click(button);
    expect(onClick).not.toHaveBeenCalled();
  });

  it("asChild renders a link with button styling", () => {
    render(
      <Button asChild variant="primary">
        <a href="/o/maple/contacts">Open contacts</a>
      </Button>,
    );
    const link = screen.getByRole("link", { name: "Open contacts" });
    expect(link.className).toContain("bg-surface-accent");
  });

  it("IconButton is named by its label", async () => {
    render(<IconButton label="Add line" icon={<PlusIcon />} />);
    expect(screen.getByRole("button", { name: "Add line" })).toBeInTheDocument();
  });

  it("has no axe violations (all variants)", async () => {
    render(
      <div>
        {(["primary", "secondary", "ghost", "danger", "link"] as const).map((variant) => (
          <Button key={variant} variant={variant}>
            Save
          </Button>
        ))}
        <Button disabled>Disabled</Button>
        <IconButton label="Delete line" icon={<PlusIcon />} />
      </div>,
    );
    await expectNoAxeViolations();
  });
});

describe("Badge and StatusBadge (A-10-T06)", () => {
  it("StatusBadge takes its tone from the one status map and always shows text", () => {
    render(<StatusBadge status="overdue" label="Overdue" />);
    const badge = screen.getByText("Overdue").parentElement!;
    expect(badge).toHaveAttribute("data-status", "overdue");
    expect(badge.className).toContain("text-fg-danger");
    expect(STATUS_TONES.paid).toBe("success");
  });

  it("has no axe violations", async () => {
    render(
      <p>
        <Badge>GIFI 1000</Badge> <Badge tone="accent">Trial</Badge>{" "}
        <StatusBadge status="awaiting_approval" label="Awaiting approval" />
      </p>,
    );
    await expectNoAxeViolations();
  });
});
