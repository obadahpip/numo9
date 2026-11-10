import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { expectNoAxeViolations } from "../test/axe";
import { Button } from "./Button";
import { Dialog, DialogClose, Drawer } from "./Dialog";
import { ToastProvider, useToast } from "./Toast";
import { Tooltip } from "./Tooltip";

describe("Dialog (A-10-T06)", () => {
  function Archive() {
    return (
      <Dialog
        trigger={<Button>Archive organisation</Button>}
        title="Archive Maple Leaf Supply Ltd.?"
        description="Archived organisations leave your directory. You can restore them later."
        closeLabel="Close"
        footer={
          <>
            <DialogClose asChild>
              <Button>Keep organisation</Button>
            </DialogClose>
            <Button variant="danger">Archive organisation</Button>
          </>
        }
      />
    );
  }

  it("opens, traps focus inside, Escape closes and returns focus to the trigger", async () => {
    const user = userEvent.setup();
    render(<Archive />);
    const trigger = screen.getByRole("button", { name: "Archive organisation" });
    await user.click(trigger);
    const dialog = screen.getByRole("dialog", { name: "Archive Maple Leaf Supply Ltd.?" });
    expect(dialog).toHaveAccessibleDescription(/Archived organisations leave/);
    expect(dialog.contains(document.activeElement)).toBe(true);
    await user.tab();
    await user.tab();
    await user.tab();
    expect(dialog.contains(document.activeElement)).toBe(true);
    await user.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(trigger).toHaveFocus();
  });

  it("has no axe violations when open", async () => {
    const user = userEvent.setup();
    render(<Archive />);
    await user.click(screen.getByRole("button", { name: "Archive organisation" }));
    await expectNoAxeViolations();
  });

  it("dismissible=false ignores Escape", async () => {
    const user = userEvent.setup();
    render(<Dialog defaultOpen title="Delete practice" closeLabel="Close" dismissible={false} />);
    await user.keyboard("{Escape}");
    expect(screen.getByRole("dialog", { name: "Delete practice" })).toBeInTheDocument();
  });
});

describe("Drawer (A-10-T06)", () => {
  it("is a named modal side panel from the end edge", async () => {
    const user = userEvent.setup();
    render(
      <Drawer trigger={<Button>History</Button>} title="History" closeLabel="Close">
        <p>Changed by Dana Lee</p>
      </Drawer>,
    );
    await user.click(screen.getByRole("button", { name: "History" }));
    const drawer = screen.getByRole("dialog", { name: "History" });
    expect(drawer).toHaveAttribute("data-drawer-side", "end");
    await expectNoAxeViolations();
    await user.click(screen.getByRole("button", { name: "Close" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  });
});

describe("Tooltip (A-10-T06)", () => {
  it("shows on keyboard focus and is announced as the trigger's description", async () => {
    const user = userEvent.setup();
    render(
      <Tooltip content="Ctrl+S">
        <Button>Save</Button>
      </Tooltip>,
    );
    await user.tab();
    const tip = await screen.findByRole("tooltip");
    expect(tip).toHaveTextContent("Ctrl+S");
    expect(screen.getByRole("button", { name: "Save" })).toHaveAccessibleDescription("Ctrl+S");
    await user.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("tooltip")).toBeNull());
  });
});

describe("Toast with Undo (A-10-T06)", () => {
  function ArchiveButton({ onUndo }: { onUndo: () => void }) {
    const { toast } = useToast();
    return (
      <Button
        onClick={() =>
          toast({
            title: "Maple Leaf Supply Ltd. archived",
            tone: "success",
            undo: { label: "Undo", altText: "Undo from the organisation's History", onUndo },
          })
        }
      >
        Archive
      </Button>
    );
  }

  const labels = { region: "Notifications ({hotkey})", close: "Dismiss" };

  it("announces the toast and runs Undo", async () => {
    const user = userEvent.setup();
    const onUndo = vi.fn();
    render(
      <ToastProvider labels={labels}>
        <ArchiveButton onUndo={onUndo} />
      </ToastProvider>,
    );
    await user.click(screen.getByRole("button", { name: "Archive" }));
    const status = await screen.findByText("Maple Leaf Supply Ltd. archived");
    expect(status).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Undo" }));
    expect(onUndo).toHaveBeenCalledOnce();
    await waitFor(() => expect(screen.queryByText("Maple Leaf Supply Ltd. archived")).toBeNull());
  });

  it("closes by itself after the 10 s undo window", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    render(
      <ToastProvider labels={labels}>
        <ArchiveButton onUndo={vi.fn()} />
      </ToastProvider>,
    );
    await user.click(screen.getByRole("button", { name: "Archive" }));
    expect(screen.getByText("Maple Leaf Supply Ltd. archived")).toBeInTheDocument();
    vi.advanceTimersByTime(9_000);
    expect(screen.getByText("Maple Leaf Supply Ltd. archived")).toBeInTheDocument();
    vi.advanceTimersByTime(1_500);
    await waitFor(() => expect(screen.queryByText("Maple Leaf Supply Ltd. archived")).toBeNull());
    vi.useRealTimers();
  });

  it("has no axe violations with a toast open", async () => {
    const user = userEvent.setup();
    render(
      <ToastProvider labels={labels}>
        <ArchiveButton onUndo={vi.fn()} />
      </ToastProvider>,
    );
    await user.click(screen.getByRole("button", { name: "Archive" }));
    await screen.findByText("Maple Leaf Supply Ltd. archived");
    await expectNoAxeViolations();
  });

  it("useToast outside the provider explains the fix", () => {
    const Bad = () => {
      useToast();
      return null;
    };
    vi.spyOn(console, "error").mockImplementation(() => undefined);
    expect(() => render(<Bad />)).toThrow(/inside <ToastProvider>/);
  });
});
