"use client";

import * as Popover from "@radix-ui/react-popover";
import {
  forwardRef,
  useEffect,
  useImperativeHandle,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent as ReactKeyboardEvent,
} from "react";

import {
  addDays,
  addMonths,
  dayOfWeek,
  daysInMonth,
  endOfMonth,
  isoDate,
  parseIso,
  startOfMonth,
  type IsoDate,
} from "../format/dates";
import { formatDate } from "../format/format";
import { intlLocale, type AppLocale } from "../format/locale";
import { parseDate } from "../format/parse";
import { cn } from "../primitives/cn";
import { INPUT_BASE } from "../primitives/Input";
import { ChevronIcon } from "../shell/icons";

export interface DateShortcut {
  id: string;
  label: string;
  /** Date from the base date (e.g. the invoice date for a due date). */
  resolve: (base: IsoDate) => IsoDate;
}

export interface DatePickerLabels {
  openCalendar: string;
  previousMonth: string;
  nextMonth: string;
  /** Shown under the input when typed text isn't a date. */
  unreadable: string;
  shortcuts: {
    today: string;
    plus7: string;
    plus14: string;
    plus30: string;
    endOfMonth: string;
    endOfNextMonth: string;
  };
}

export interface DatePickerProps {
  value: IsoDate | null;
  onChange: (value: IsoDate | null) => void;
  locale: AppLocale;
  /** Today in the organisation's time zone. */
  today: IsoDate;
  labels: DatePickerLabels;
  /** Base of the shortcuts (+7, end of month…); default today. */
  base?: IsoDate | null;
  /** Replace the default shortcuts. */
  shortcuts?: DateShortcut[];
  min?: IsoDate;
  max?: IsoDate;
  invalid?: boolean;
  disabled?: boolean;
  required?: boolean;
  id?: string;
  name?: string;
  placeholder?: string;
  "aria-label"?: string;
  "aria-labelledby"?: string;
  "aria-describedby"?: string;
  className?: string;
}

export function defaultDateShortcuts(labels: DatePickerLabels["shortcuts"]): DateShortcut[] {
  return [
    { id: "today", label: labels.today, resolve: (base) => base },
    { id: "plus7", label: labels.plus7, resolve: (base) => addDays(base, 7) },
    { id: "plus14", label: labels.plus14, resolve: (base) => addDays(base, 14) },
    { id: "plus30", label: labels.plus30, resolve: (base) => addDays(base, 30) },
    { id: "endOfMonth", label: labels.endOfMonth, resolve: (base) => endOfMonth(base) },
    {
      id: "endOfNextMonth",
      label: labels.endOfNextMonth,
      resolve: (base) => endOfMonth(addMonths(startOfMonth(base), 1)),
    },
  ];
}

/**
 * Date picker (A-10-T09). Type a date in any forgiving form (`26/10`, `oct 26`, `+30`, `today`) or
 * use the calendar (Alt+↓ or the calendar button). Calendar keys: arrows ±1 day / ±1 week,
 * PageUp/PageDown ±1 month (with Shift ±1 year), Home/End start/end of week, Enter chooses, Esc
 * closes. Shortcuts (+7, +14, end of month…) count from `base`. The value is an ISO date.
 */
export const DatePicker = forwardRef<HTMLInputElement, DatePickerProps>(function DatePicker(
  {
    value,
    onChange,
    locale,
    today,
    labels,
    base,
    shortcuts,
    min,
    max,
    invalid = false,
    disabled = false,
    required,
    id,
    name,
    placeholder,
    className,
    ...aria
  },
  ref,
) {
  const input = useRef<HTMLInputElement>(null);
  useImperativeHandle(ref, () => input.current as HTMLInputElement);
  const display = value ? formatDate(value, { locale }) : "";
  const [text, setText] = useState(display);
  const [unreadable, setUnreadable] = useState(false);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    setText(display);
    setUnreadable(false);
  }, [display]);

  const inRange = (date: IsoDate) => (!min || date >= min) && (!max || date <= max);

  const commitText = () => {
    const trimmed = text.trim();
    if (!trimmed) {
      setUnreadable(false);
      if (value !== null) onChange(null);
      return;
    }
    const parsed = parseDate(trimmed, { locale, today });
    if (parsed && inRange(parsed)) {
      setUnreadable(false);
      if (parsed === value) setText(display);
      else onChange(parsed);
    } else {
      setUnreadable(true);
    }
  };

  const choose = (date: IsoDate) => {
    setOpen(false);
    setUnreadable(false);
    onChange(date);
    input.current?.focus();
  };

  const messageId = `${id ?? name ?? "date"}-unreadable`;
  const describedBy =
    [aria["aria-describedby"], unreadable ? messageId : null].filter(Boolean).join(" ") ||
    undefined;

  return (
    <div className={cn("grid gap-1", className)}>
      <Popover.Root open={open && !disabled} onOpenChange={setOpen}>
        <Popover.Anchor asChild>
          <div className="relative">
            <input
              ref={input}
              id={id}
              name={name}
              type="text"
              inputMode="text"
              autoComplete="off"
              disabled={disabled}
              required={required}
              placeholder={placeholder}
              value={text}
              aria-invalid={invalid || unreadable || undefined}
              aria-label={aria["aria-label"]}
              aria-labelledby={aria["aria-labelledby"]}
              aria-describedby={describedBy}
              onChange={(event) => setText(event.target.value)}
              onBlur={commitText}
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  event.preventDefault();
                  commitText();
                } else if (event.key === "ArrowDown" && event.altKey) {
                  event.preventDefault();
                  setOpen(true);
                }
              }}
              className={cn(
                INPUT_BASE,
                "pe-12",
                invalid || unreadable ? "border-border-danger" : "border-border-strong",
              )}
            />
            <Popover.Trigger
              disabled={disabled}
              aria-label={labels.openCalendar}
              className="absolute inset-y-0 end-0 inline-flex w-11 items-center justify-center rounded-e-md text-fg-muted hover:text-fg"
            >
              <CalendarIcon />
            </Popover.Trigger>
          </div>
        </Popover.Anchor>
        <Popover.Portal>
          <Popover.Content
            align="end"
            sideOffset={4}
            aria-label={labels.openCalendar}
            onCloseAutoFocus={(event) => {
              event.preventDefault();
              input.current?.focus();
            }}
            className="z-50 flex flex-col gap-3 rounded-lg border border-border bg-surface p-3 text-fg shadow-elevation-3 sm:flex-row"
          >
            <Calendar
              locale={locale}
              today={today}
              selected={value}
              min={min}
              max={max}
              labels={labels}
              onChoose={choose}
            />
            <ul className="flex flex-wrap gap-1 sm:w-40 sm:flex-col sm:border-s sm:border-border sm:ps-3">
              {(shortcuts ?? defaultDateShortcuts(labels.shortcuts)).map((shortcut) => {
                const date = shortcut.resolve(base ?? today);
                return (
                  <li key={shortcut.id}>
                    <button
                      type="button"
                      disabled={!inRange(date)}
                      onClick={() => choose(date)}
                      className="flex min-h-touch-target w-full flex-col items-start justify-center rounded-md px-2 text-start text-sm hover:bg-surface-muted disabled:opacity-50"
                    >
                      <span className="font-medium">{shortcut.label}</span>
                      <span className="text-xs text-fg-muted">{formatDate(date, { locale })}</span>
                    </button>
                  </li>
                );
              })}
            </ul>
          </Popover.Content>
        </Popover.Portal>
      </Popover.Root>
      {unreadable ? (
        <p id={messageId} className="text-sm font-medium text-fg-danger">
          {labels.unreadable}
        </p>
      ) : null}
    </div>
  );
});

interface CalendarProps {
  locale: AppLocale;
  today: IsoDate;
  selected: IsoDate | null;
  min?: IsoDate;
  max?: IsoDate;
  labels: Pick<DatePickerLabels, "previousMonth" | "nextMonth">;
  onChoose: (date: IsoDate) => void;
}

/** Month grid (ARIA grid): weeks start on Sunday, as Canadian calendars do. */
export function Calendar({ locale, today, selected, min, max, labels, onChoose }: CalendarProps) {
  const [focused, setFocused] = useState<IsoDate>(selected ?? today);
  const grid = useRef<HTMLTableElement>(null);
  const { year, month } = parseIso(focused)!;
  const lang = intlLocale(locale);

  const heading = useMemo(
    () =>
      new Intl.DateTimeFormat(lang, { month: "long", year: "numeric", timeZone: "UTC" }).format(
        new Date(Date.UTC(year, month - 1, 1)),
      ),
    [lang, year, month],
  );
  const weekdays = useMemo(() => {
    const short = new Intl.DateTimeFormat(lang, { weekday: "short", timeZone: "UTC" });
    const long = new Intl.DateTimeFormat(lang, { weekday: "long", timeZone: "UTC" });
    // 2026-10-04 is a Sunday.
    return Array.from({ length: 7 }, (_, i) => {
      const date = new Date(Date.UTC(2026, 9, 4 + i));
      return { short: short.format(date), long: long.format(date) };
    });
  }, [lang]);

  const first = isoDate(year, month, 1)!;
  const lead = dayOfWeek(first);
  const total = daysInMonth(year, month);
  const cells: (IsoDate | null)[] = [
    ...Array.from({ length: lead }, () => null),
    ...Array.from({ length: total }, (_, i) => isoDate(year, month, i + 1)),
  ];
  while (cells.length % 7) cells.push(null);
  const weeks = Array.from({ length: cells.length / 7 }, (_, i) => cells.slice(i * 7, i * 7 + 7));

  const focusDay = (date: IsoDate) => {
    setFocused(date);
    requestAnimationFrame(() =>
      grid.current?.querySelector<HTMLButtonElement>(`[data-date="${date}"]`)?.focus(),
    );
  };

  useEffect(() => {
    grid.current?.querySelector<HTMLButtonElement>(`[data-date="${focused}"]`)?.focus();
    // Focus the selected (or today's) day once, when the calendar opens.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const disabled = (date: IsoDate) =>
    (min !== undefined && date < min) || (max !== undefined && date > max);

  const onKey = (event: ReactKeyboardEvent<HTMLTableElement>) => {
    const moves: Record<string, () => IsoDate> = {
      ArrowLeft: () => addDays(focused, -1),
      ArrowRight: () => addDays(focused, 1),
      ArrowUp: () => addDays(focused, -7),
      ArrowDown: () => addDays(focused, 7),
      PageUp: () => addMonths(focused, event.shiftKey ? -12 : -1),
      PageDown: () => addMonths(focused, event.shiftKey ? 12 : 1),
      Home: () => addDays(focused, -dayOfWeek(focused)),
      End: () => addDays(focused, 6 - dayOfWeek(focused)),
    };
    const move = moves[event.key];
    if (move) {
      event.preventDefault();
      focusDay(move());
    }
  };

  return (
    <div className="w-72">
      <div className="mb-2 flex items-center justify-between">
        <button
          type="button"
          aria-label={labels.previousMonth}
          onClick={() => setFocused(addMonths(focused, -1))}
          className="inline-flex size-touch-target items-center justify-center rounded-md hover:bg-surface-muted"
        >
          <span className="rotate-180 rtl:rotate-0">
            <ChevronIcon />
          </span>
        </button>
        <h2 aria-live="polite" className="text-sm font-semibold capitalize">
          {heading}
        </h2>
        <button
          type="button"
          aria-label={labels.nextMonth}
          onClick={() => setFocused(addMonths(focused, 1))}
          className="inline-flex size-touch-target items-center justify-center rounded-md hover:bg-surface-muted"
        >
          <span className="rtl:rotate-180">
            <ChevronIcon />
          </span>
        </button>
      </div>
      <table
        ref={grid}
        role="grid"
        aria-label={heading}
        onKeyDown={onKey}
        className="w-full border-collapse text-center text-sm"
      >
        <thead>
          <tr>
            {weekdays.map((day) => (
              <th key={day.long} scope="col" className="pb-1 text-xs font-medium text-fg-muted">
                <abbr title={day.long} className="no-underline">
                  {day.short}
                </abbr>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {weeks.map((week, w) => (
            <tr key={w}>
              {week.map((date, d) =>
                date ? (
                  <td key={date} role="gridcell" aria-selected={date === selected}>
                    <button
                      type="button"
                      data-date={date}
                      tabIndex={date === focused ? 0 : -1}
                      disabled={disabled(date)}
                      aria-current={date === today ? "date" : undefined}
                      aria-label={formatDate(date, { locale })}
                      onClick={() => onChoose(date)}
                      onFocus={() => setFocused(date)}
                      className={cn(
                        "inline-flex size-10 items-center justify-center rounded-md tabular-nums hover:bg-surface-muted disabled:text-fg-disabled",
                        date === selected &&
                          "bg-surface-inverse font-semibold text-fg-inverse hover:bg-surface-inverse-hover",
                        date === today && date !== selected && "font-bold underline",
                      )}
                    >
                      {Number(date.slice(8))}
                    </button>
                  </td>
                ) : (
                  <td key={`empty-${w}-${d}`} role="gridcell" />
                ),
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function CalendarIcon() {
  return (
    <svg
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      aria-hidden="true"
      focusable="false"
    >
      <rect x="3" y="5" width="18" height="16" rx="2" />
      <path d="M3 10h18M8 3v4M16 3v4" />
    </svg>
  );
}
