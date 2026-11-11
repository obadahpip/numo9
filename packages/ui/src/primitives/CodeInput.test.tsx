import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { vi } from "vitest";

import { expectNoAxeViolations } from "../test/axe";
import { CodeInput, codeDigits } from "./CodeInput";

function Harness({
  onComplete = vi.fn(),
  initial = "",
}: {
  onComplete?: (v: string) => void;
  initial?: string;
}) {
  const [value, setValue] = useState(initial);
  return (
    <>
      <CodeInput
        value={value}
        onChange={setValue}
        onComplete={onComplete}
        label="Authentication code"
        digitLabel={(n, total) => `Digit ${n} of ${total}`}
      />
      <output data-testid="value">{value}</output>
    </>
  );
}

const box = (n: number) => screen.getByRole("textbox", { name: `Digit ${n} of 6` });
const value = () => screen.getByTestId("value").textContent;

describe("codeDigits", () => {
  it.each([
    ["123456", "123456"],
    ["123 456", "123456"],
    ["123-456", "123456"],
    ["Your code: 987654.", "987654"],
    ["Your Numo9 code: 482 913", "482913"],
    ["Numo9 482-913 (expires in 30 s)", "482913"],
    ["12345678", "123456"],
    ["abc", ""],
  ])("%j → %j", (text, digits) => {
    expect(codeDigits(text, 6)).toBe(digits);
  });
});

describe("CodeInput (A-02-T11)", () => {
  it("is a labelled group of six named, numeric boxes; the first takes OTP autofill", async () => {
    render(<Harness />);
    expect(screen.getByRole("group", { name: "Authentication code" })).toBeInTheDocument();
    expect(screen.getAllByRole("textbox")).toHaveLength(6);
    expect(box(1)).toHaveAttribute("autocomplete", "one-time-code");
    expect(box(1)).toHaveAttribute("inputmode", "numeric");
    expect(box(2)).toHaveAttribute("autocomplete", "off");
    await expectNoAxeViolations();
  });

  it("auto-advances while typing and completes once", async () => {
    const user = userEvent.setup();
    const onComplete = vi.fn();
    render(<Harness onComplete={onComplete} />);
    await user.click(box(1));
    await user.keyboard("12345");
    expect(value()).toBe("12345");
    expect(box(6)).toHaveFocus();
    expect(onComplete).not.toHaveBeenCalled();
    await user.keyboard("6");
    expect(value()).toBe("123456");
    expect(onComplete).toHaveBeenCalledTimes(1);
    expect(onComplete).toHaveBeenCalledWith("123456");
  });

  it("refuses non-digits", async () => {
    const user = userEvent.setup();
    render(<Harness />);
    await user.click(box(1));
    await user.keyboard("a1b");
    expect(value()).toBe("1");
    expect(box(2)).toHaveFocus();
  });

  it("pasting a whole code into any box fills every box", async () => {
    const onComplete = vi.fn();
    render(<Harness onComplete={onComplete} />);
    fireEvent.paste(box(3), { clipboardData: { getData: () => " 482 913 " } });
    expect(value()).toBe("482913");
    expect(box(6)).toHaveFocus();
    expect(onComplete).toHaveBeenCalledWith("482913");
  });

  it("autofill of the whole code into the first box spreads it", () => {
    const onComplete = vi.fn();
    render(<Harness onComplete={onComplete} />);
    fireEvent.change(box(1), { target: { value: "135790" } });
    expect(value()).toBe("135790");
    expect(onComplete).toHaveBeenCalledWith("135790");
  });

  it("Backspace on an empty box clears the previous one; arrows move", async () => {
    const user = userEvent.setup();
    render(<Harness initial="123" />);
    await user.click(box(4));
    await user.keyboard("{Backspace}");
    expect(value()).toBe("12");
    expect(box(3)).toHaveFocus();
    await user.keyboard("{ArrowLeft}");
    expect(box(2)).toHaveFocus();
    await user.keyboard("{Backspace}");
    expect(value()).toBe("1");
    await user.keyboard("{Home}");
    expect(box(1)).toHaveFocus();
    await user.keyboard("{End}");
    expect(box(2)).toHaveFocus();
  });

  it("a digit typed after a gap lands in the next free box (no holes)", async () => {
    const user = userEvent.setup();
    render(<Harness initial="12" />);
    await user.click(box(5));
    await user.keyboard("7");
    expect(value()).toBe("127");
    expect(box(4)).toHaveFocus();
  });

  it("typing over a filled box replaces its digit", async () => {
    const user = userEvent.setup();
    render(<Harness initial="111111" />);
    await user.click(box(3));
    await user.keyboard("9");
    expect(value()).toBe("119111");
    expect(box(4)).toHaveFocus();
  });
});
