"use client";

import {
  forwardRef,
  useCallback,
  useId,
  useImperativeHandle,
  useRef,
  type ClipboardEvent,
  type KeyboardEvent,
} from "react";

import { cn } from "./cn";

export interface CodeInputProps {
  /** The code typed so far (digits only), e.g. "1234". */
  value: string;
  onChange: (value: string) => void;
  /** Called once all boxes are filled (typed or pasted), with the full code. */
  onComplete?: (value: string) => void;
  /** Number of boxes; 6 for TOTP. */
  length?: number;
  /** Accessible name of the group, e.g. "Authentication code". */
  label: string;
  /** Accessible name of each box, e.g. (1, 6) → "Digit 1 of 6". */
  digitLabel: (position: number, length: number) => string;
  invalid?: boolean;
  disabled?: boolean;
  /** ids of the hint / error, for `aria-describedby` on the group. */
  "aria-describedby"?: string;
  /** id of the first box (a label's `for`, an error summary's link target). */
  id?: string;
  autoFocus?: boolean;
  className?: string;
}

export interface CodeInputHandle {
  /** Focus box `index`, or by default the first empty box (the last when all are filled). */
  focus: (index?: number) => void;
}

/**
 * The code in `text`: pasted "123 456", "123-456" → "123456". When the text holds more (an email
 * line such as "Your Numo9 code: 482 913"), the last group of exactly `length` digits — single
 * spaces or dashes allowed between them — wins; otherwise the first `length` digits.
 */
export function codeDigits(text: string, length: number): string {
  if (length > 1) {
    const group = new RegExp(`(?<![\\d])\\d(?:[ -]?\\d){${length - 1}}(?![\\d])`, "g");
    const groups = text.match(group);
    const last = groups?.[groups.length - 1];
    if (last) return last.replace(/\D/g, "");
  }
  return text.replace(/\D/g, "").slice(0, length);
}

/**
 * One-time code input (A-02-T11): `length` single-digit boxes, used for TOTP challenges and
 * enrolment.
 *
 * - **Paste-aware**: pasting the whole code into any box fills every box (spaces, dashes and
 *   surrounding text are ignored); the browser's SMS/OTP autofill (`autocomplete="one-time-code"`)
 *   lands in the first box and is spread the same way.
 * - **Auto-advance**: typing a digit moves to the next box; Backspace on an empty box clears the
 *   previous one; ←/→, Home/End move between boxes; non-digits are refused.
 * - `onComplete` fires when the last box is filled, so a screen can submit without a click.
 * - Accessible: a labelled group; each box is named ("Digit 2 of 6"); numeric keyboard on
 *   phones; 44 px boxes.
 */
export const CodeInput = forwardRef<CodeInputHandle, CodeInputProps>(function CodeInput(
  {
    value,
    onChange,
    onComplete,
    length = 6,
    label,
    digitLabel,
    invalid = false,
    disabled = false,
    id,
    autoFocus = false,
    className,
    "aria-describedby": describedBy,
  },
  ref,
) {
  const autoId = useId();
  const baseId = id ?? autoId;
  const boxes = useRef<(HTMLInputElement | null)[]>([]);
  const digits = codeDigits(value, length);

  const focusBox = useCallback(
    (index: number) => {
      const box = boxes.current[Math.max(0, Math.min(length - 1, index))];
      box?.focus();
      box?.select();
    },
    [length],
  );

  useImperativeHandle(
    ref,
    () => ({ focus: (index) => focusBox(index ?? Math.min(digits.length, length - 1)) }),
    [focusBox, digits.length, length],
  );

  const commit = (next: string, focusIndex: number) => {
    const clean = codeDigits(next, length);
    onChange(clean);
    focusBox(focusIndex);
    if (clean.length === length && clean !== digits) onComplete?.(clean);
  };

  /** Replace the digit at `index` with the typed text (one digit, or several from autofill). */
  const typeAt = (index: number, text: string) => {
    const typed = text.replace(/\D/g, "");
    if (!typed) return;
    const before = digits.slice(0, index);
    const after = digits.slice(index + typed.length);
    const next = (before + typed + after).slice(0, length);
    commit(next, Math.min(before.length + typed.length, length - 1));
  };

  const onKeyDown = (index: number, event: KeyboardEvent<HTMLInputElement>) => {
    switch (event.key) {
      case "Backspace": {
        event.preventDefault();
        if (digits[index] !== undefined) {
          commit(digits.slice(0, index) + digits.slice(index + 1), index);
        } else if (index > 0) {
          commit(digits.slice(0, index - 1) + digits.slice(index), index - 1);
        }
        break;
      }
      case "Delete":
        event.preventDefault();
        commit(digits.slice(0, index) + digits.slice(index + 1), index);
        break;
      case "ArrowLeft":
        event.preventDefault();
        focusBox(index - 1);
        break;
      case "ArrowRight":
        event.preventDefault();
        focusBox(Math.min(index + 1, digits.length));
        break;
      case "Home":
        event.preventDefault();
        focusBox(0);
        break;
      case "End":
        event.preventDefault();
        focusBox(Math.min(digits.length, length - 1));
        break;
      default:
        break;
    }
  };

  const onPaste = (event: ClipboardEvent<HTMLInputElement>) => {
    event.preventDefault();
    const pasted = codeDigits(event.clipboardData.getData("text"), length);
    if (!pasted) return;
    // A whole code replaces everything; a fragment is typed at the box.
    if (pasted.length === length) commit(pasted, length - 1);
    else typeAt(Number((event.target as HTMLInputElement).dataset.index ?? 0), pasted);
  };

  return (
    <div
      role="group"
      aria-label={label}
      aria-describedby={describedBy}
      className={cn("flex gap-2", className)}
    >
      {Array.from({ length }, (_, index) => (
        <input
          key={index}
          ref={(node) => {
            boxes.current[index] = node;
          }}
          id={index === 0 ? baseId : `${baseId}-${index}`}
          data-index={index}
          aria-label={digitLabel(index + 1, length)}
          aria-invalid={invalid || undefined}
          // A digit, never a password: the code is short-lived and shown as typed.
          type="text"
          inputMode="numeric"
          pattern="[0-9]*"
          autoComplete={index === 0 ? "one-time-code" : "off"}
          // Room for a whole autofilled or typed-over code; extra digits spill into the next boxes.
          maxLength={length}
          disabled={disabled}
          autoFocus={autoFocus && index === 0}
          value={digits[index] ?? ""}
          onChange={(event) => {
            const raw = event.target.value;
            const old = digits[index] ?? "";
            if (!raw) {
              commit(digits.slice(0, index) + digits.slice(index + 1), index);
              return;
            }
            // The box still holds its old digit when the caret wasn't selecting it.
            let typed = raw;
            if (old && raw.length > 1 && raw.startsWith(old)) typed = raw.slice(old.length);
            else if (old && raw.length > 1 && raw.endsWith(old)) typed = raw.slice(0, -old.length);
            typeAt(index, typed);
          }}
          onKeyDown={(event) => onKeyDown(index, event)}
          onPaste={onPaste}
          onFocus={(event) => event.target.select()}
          className={cn(
            "size-touch-target min-w-0 rounded-md border bg-surface text-center text-lg font-semibold tabular-nums text-fg",
            "disabled:cursor-not-allowed disabled:bg-surface-muted",
            invalid ? "border-border-danger" : "border-border-strong",
          )}
        />
      ))}
    </div>
  );
});
