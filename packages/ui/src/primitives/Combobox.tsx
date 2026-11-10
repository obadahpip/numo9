"use client";

import * as Popover from "@radix-ui/react-popover";
import {
  forwardRef,
  useEffect,
  useId,
  useImperativeHandle,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent as ReactKeyboardEvent,
  type ReactNode,
} from "react";

import { queryWords, normaliseForSearch } from "../org-switcher/search";
import { ChevronDownIcon } from "../shell/icons";
import { cn } from "./cn";
import { INPUT_BASE } from "./Input";

export interface ComboboxOption {
  value: string;
  label: string;
  /** Second line, e.g. an account type or a contact's email. */
  description?: string;
  /** Group heading the option is listed under (options of a group must be adjacent). */
  group?: string;
  /** Extra search text, e.g. an account code. */
  keywords?: string;
  disabled?: boolean;
}

export interface ComboboxProps {
  options: readonly ComboboxOption[];
  value: string | null;
  onChange: (value: string | null, option: ComboboxOption | null) => void;
  /** Shown when nothing matches the typed text. */
  emptyMessage: string;
  /** Called on every keystroke — use for server-side search (then pass `filter={() => true}`). */
  onQueryChange?: (query: string) => void;
  /** Custom match; default: every typed word appears in label, description or keywords. */
  filter?: (option: ComboboxOption, query: string) => boolean;
  loading?: boolean;
  loadingMessage?: string;
  /** Extra content under the list, e.g. a "Create contact" button. */
  footer?: ReactNode;
  placeholder?: string;
  invalid?: boolean;
  disabled?: boolean;
  required?: boolean;
  id?: string;
  name?: string;
  "aria-label"?: string;
  "aria-labelledby"?: string;
  "aria-describedby"?: string;
  className?: string;
  /** Most options rendered at once (keeps long lists fast). */
  maxOptions?: number;
  /**
   * Runs before the combobox's own keys (e.g. a grid's ↑/↓ row navigation while the list is
   * closed); call `preventDefault()` to take the key.
   */
  onKeyDownCapture?: (event: ReactKeyboardEvent<HTMLInputElement>) => void;
}

export function defaultComboboxFilter(option: ComboboxOption, query: string): boolean {
  const haystack = normaliseForSearch(
    `${option.label} ${option.description ?? ""} ${option.keywords ?? ""}`,
  );
  return queryWords(query).every((word) => haystack.includes(word));
}

/**
 * Combobox (A-10-T06): a searchable single choice (ARIA 1.2 combobox + listbox). Type to filter,
 * ↑/↓ to move, Enter to choose, Esc to close and restore the chosen value. Base of the pickers
 * (A-10-T09: account, contact, province).
 */
export const Combobox = forwardRef<HTMLInputElement, ComboboxProps>(function Combobox(
  {
    options,
    value,
    onChange,
    emptyMessage,
    onQueryChange,
    filter = defaultComboboxFilter,
    loading = false,
    loadingMessage,
    footer,
    placeholder,
    invalid = false,
    disabled = false,
    required,
    id,
    name,
    className,
    maxOptions = 100,
    onKeyDownCapture,
    ...aria
  },
  ref,
) {
  const baseId = useId();
  const inputId = id ?? `${baseId}-input`;
  const listId = `${baseId}-list`;
  const input = useRef<HTMLInputElement>(null);
  useImperativeHandle(ref, () => input.current as HTMLInputElement);

  const selected = options.find((option) => option.value === value) ?? null;
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState<string | null>(null); // null = not typing: show selection
  const [highlight, setHighlight] = useState(0);

  const visible = useMemo(() => {
    const typed = query ?? "";
    const list = typed.trim() ? options.filter((option) => filter(option, typed)) : [...options];
    return list.slice(0, maxOptions);
  }, [options, query, filter, maxOptions]);

  useEffect(() => {
    if (!open) return;
    const index = visible.findIndex((option) => option.value === value);
    setHighlight(query === null && index >= 0 ? index : firstEnabled(visible));
    // Recompute only when the list changes or opens.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, visible]);

  useEffect(() => {
    if (open)
      document.getElementById(`${baseId}-opt-${highlight}`)?.scrollIntoView?.({ block: "nearest" });
  }, [open, highlight, baseId]);

  const close = () => {
    setOpen(false);
    setQuery(null);
  };

  const choose = (option: ComboboxOption) => {
    if (option.disabled) return;
    onChange(option.value, option);
    close();
  };

  const move = (step: number) => {
    if (!visible.length) return;
    let next = highlight;
    for (let i = 0; i < visible.length; i += 1) {
      next = (next + step + visible.length) % visible.length;
      if (!visible[next]?.disabled) break;
    }
    setHighlight(next);
  };

  const onKeyDown = (event: ReactKeyboardEvent<HTMLInputElement>) => {
    if (event.defaultPrevented) return; // taken by onKeyDownCapture
    if (event.key === "ArrowDown" && event.altKey && !open) {
      event.preventDefault();
      setOpen(true);
      return;
    }
    switch (event.key) {
      case "ArrowDown":
        event.preventDefault();
        if (!open) setOpen(true);
        else move(1);
        break;
      case "ArrowUp":
        event.preventDefault();
        if (!open) setOpen(true);
        else move(-1);
        break;
      case "Enter": {
        if (!open) return;
        event.preventDefault();
        const option = visible[highlight];
        if (option) choose(option);
        break;
      }
      case "Escape":
        if (open) {
          event.preventDefault();
          event.stopPropagation();
          close();
        } else if (!required && value !== null) {
          event.preventDefault();
          onChange(null, null);
        }
        break;
      case "Tab":
        close();
        break;
    }
  };

  let lastGroup: string | undefined;
  return (
    <Popover.Root
      open={open && !disabled}
      onOpenChange={(next) => (next ? setOpen(true) : close())}
    >
      <Popover.Anchor asChild>
        <span className={cn("relative block", className)}>
          <input
            ref={input}
            id={inputId}
            name={name}
            type="text"
            role="combobox"
            autoComplete="off"
            spellCheck={false}
            aria-autocomplete="list"
            aria-expanded={open}
            aria-controls={listId}
            aria-activedescendant={
              open && visible.length ? `${baseId}-opt-${highlight}` : undefined
            }
            aria-invalid={invalid || undefined}
            aria-required={required || undefined}
            disabled={disabled}
            placeholder={placeholder}
            value={query ?? selected?.label ?? ""}
            onChange={(event) => {
              setQuery(event.target.value);
              setOpen(true);
              onQueryChange?.(event.target.value);
            }}
            onClick={() => setOpen(true)}
            onKeyDownCapture={onKeyDownCapture}
            onKeyDown={onKeyDown}
            onBlur={() => close()}
            className={cn(
              INPUT_BASE,
              "pe-9",
              invalid ? "border-border-danger" : "border-border-strong",
            )}
            {...aria}
          />
          <span
            aria-hidden="true"
            className="pointer-events-none absolute inset-y-0 end-3 flex items-center text-fg-muted"
          >
            <ChevronDownIcon />
          </span>
        </span>
      </Popover.Anchor>
      <Popover.Portal>
        <Popover.Content
          align="start"
          sideOffset={4}
          // A listbox popup, not a dialog: the input keeps focus (ARIA combobox pattern).
          role="presentation"
          onOpenAutoFocus={(event) => event.preventDefault()}
          onCloseAutoFocus={(event) => event.preventDefault()}
          onInteractOutside={(event) => {
            if (input.current?.contains(event.target as Node)) event.preventDefault();
          }}
          // Keep focus in the input while the pointer is on the list.
          onMouseDown={(event) => event.preventDefault()}
          className="z-50 max-h-80 w-[var(--radix-popover-trigger-width)] min-w-56 overflow-y-auto rounded-md border border-border bg-surface py-1 text-fg shadow-elevation-3"
        >
          <div
            id={listId}
            role="listbox"
            aria-labelledby={aria["aria-labelledby"]}
            aria-label={aria["aria-labelledby"] ? undefined : aria["aria-label"]}
          >
            {visible.map((option, index) => {
              const heading = option.group && option.group !== lastGroup ? option.group : null;
              lastGroup = option.group;
              return (
                <div key={option.value} role="presentation">
                  {heading ? (
                    <div
                      role="presentation"
                      className="px-3 pt-2 pb-1 text-xs font-bold tracking-wide text-fg-muted uppercase"
                    >
                      {heading}
                    </div>
                  ) : null}
                  <div
                    id={`${baseId}-opt-${index}`}
                    role="option"
                    aria-selected={option.value === value}
                    aria-disabled={option.disabled || undefined}
                    data-highlighted={index === highlight || undefined}
                    onMouseEnter={() => setHighlight(index)}
                    onClick={() => choose(option)}
                    className={cn(
                      "flex min-h-touch-target cursor-pointer flex-col justify-center px-3 text-sm",
                      index === highlight && "bg-surface-muted",
                      option.value === value && "font-semibold",
                      option.disabled && "cursor-not-allowed text-fg-disabled",
                    )}
                  >
                    <span>{option.label}</span>
                    {option.description ? (
                      <span className="text-xs font-normal text-fg-muted">
                        {option.description}
                      </span>
                    ) : null}
                  </div>
                </div>
              );
            })}
          </div>
          {loading ? (
            <p role="status" className="px-3 py-2 text-sm text-fg-muted">
              {loadingMessage}
            </p>
          ) : visible.length === 0 ? (
            <p role="status" className="px-3 py-2 text-sm text-fg-muted">
              {emptyMessage}
            </p>
          ) : null}
          {footer ? <div className="border-t border-border p-1">{footer}</div> : null}
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
});

function firstEnabled(options: readonly ComboboxOption[]): number {
  const index = options.findIndex((option) => !option.disabled);
  return index < 0 ? 0 : index;
}
