"use client";

import { Button } from "@numo9/ui";
import { useId, useMemo, useState, type KeyboardEvent } from "react";

import { useFormatMessage } from "@/i18n";

import { TAG_COLOURS, type Tag, type TagColour } from "./api";
import { m } from "./messages";

/** Swatch of each named colour (decoration only: the tag's name and colour name are the text). */
export const SWATCH: Record<TagColour, string> = {
  red: "#c62828",
  orange: "#d84315",
  amber: "#b26a00",
  olive: "#6b7a1a",
  green: "#2e7d32",
  teal: "#00796b",
  cyan: "#00838f",
  blue: "#1565c0",
  indigo: "#3949ab",
  violet: "#6a1b9a",
  magenta: "#ad1457",
  slate: "#546e7a",
};

const fold = (text: string) =>
  text.normalize("NFKD").replace(/\p{M}/gu, "").toLowerCase().replace(/\s+/g, " ").trim();

export function TagChip({ tag }: { tag: Pick<Tag, "name" | "colour" | "colour_label"> }) {
  const t = useFormatMessage();
  return (
    <span
      data-tag-chip={tag.colour}
      className="inline-flex items-center gap-1 rounded-full border border-border bg-surface px-2 text-xs font-semibold text-fg"
    >
      <span
        aria-hidden="true"
        className="size-2.5 rounded-full"
        style={{ background: SWATCH[tag.colour] }}
      />
      {tag.name}
      <span className="sr-only">{t(m.tagColourName, { colour: tag.colour_label })}</span>
    </span>
  );
}

export interface TagPickerProps {
  tags: Tag[];
  /** Ids already chosen (left out of the suggestions). */
  selected?: string[];
  onSelect: (tag: Tag) => void;
  /** Type-to-create: make the tag, return it (or an error message). */
  onCreate: (name: string, colour: TagColour) => Promise<Tag | string>;
  colourLabels: Record<TagColour, string>;
}

/**
 * Tag picker (V-02-T10): a combobox — type to filter the practice's tags (accents and case
 * ignored), ↑/↓ and Enter to choose; when no tag has that name, the last option creates it
 * inline with the chosen colour (12 named colours; a tag always shows its name, never colour
 * alone).
 */
export function TagPicker({
  tags,
  selected = [],
  onSelect,
  onCreate,
  colourLabels,
}: TagPickerProps) {
  const t = useFormatMessage();
  const inputId = useId();
  const listId = useId();
  const [text, setText] = useState("");
  const [active, setActive] = useState(0);
  const [colour, setColour] = useState<TagColour>(TAG_COLOURS[tags.length % TAG_COLOURS.length]!);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const typed = fold(text);
  const matches = useMemo(
    () => tags.filter((tag) => !selected.includes(tag.id) && fold(tag.name).includes(typed)),
    [tags, selected, typed],
  );
  const exact = tags.some((tag) => fold(tag.name) === typed);
  const canCreate = typed !== "" && !exact;
  const options = matches.length + (canCreate ? 1 : 0);
  const open = text.trim() !== "" && options > 0;

  const choose = async (index: number) => {
    setError("");
    if (index < matches.length) {
      onSelect(matches[index]!);
      setText("");
      return;
    }
    setBusy(true);
    const made = await onCreate(text.trim(), colour);
    setBusy(false);
    if (typeof made === "string") {
      setError(made);
      return;
    }
    onSelect(made);
    setText("");
  };
  const onKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (!open) return;
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActive((index) => Math.min(options - 1, index + 1));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActive((index) => Math.max(0, index - 1));
    } else if (event.key === "Enter") {
      event.preventDefault();
      void choose(Math.min(active, options - 1));
    } else if (event.key === "Escape") {
      setText("");
    }
  };
  const optionId = (index: number) => `${listId}-${index}`;

  return (
    <div className="flex flex-col gap-2" data-tag-picker="">
      <label htmlFor={inputId} className="text-sm font-medium text-fg">
        {t(m.tagPickerLabel)}
      </label>
      <input
        id={inputId}
        role="combobox"
        aria-expanded={open}
        aria-controls={listId}
        aria-autocomplete="list"
        aria-activedescendant={open ? optionId(Math.min(active, options - 1)) : undefined}
        value={text}
        maxLength={40}
        disabled={busy}
        onChange={(event) => {
          setText(event.target.value);
          setActive(0);
          setError("");
        }}
        onKeyDown={onKeyDown}
        className="min-h-touch-target rounded-md border border-border-strong bg-surface px-3 text-sm text-fg"
      />
      {open ? (
        <ul
          id={listId}
          role="listbox"
          aria-label={t(m.tagPickerLabel)}
          className="rounded-md border border-border bg-surface p-1"
        >
          {matches.map((tag, index) => (
            <li
              key={tag.id}
              id={optionId(index)}
              role="option"
              aria-selected={active === index}
              onMouseDown={(event) => event.preventDefault()}
              onClick={() => void choose(index)}
              className={`cursor-pointer rounded px-2 py-1 ${active === index ? "bg-surface-accent-subtle" : ""}`}
            >
              <TagChip tag={tag} />
            </li>
          ))}
          {canCreate ? (
            <li
              id={optionId(matches.length)}
              role="option"
              aria-selected={active === matches.length}
              data-create-option=""
              onMouseDown={(event) => event.preventDefault()}
              onClick={() => void choose(matches.length)}
              className={`cursor-pointer rounded px-2 py-1 text-sm font-semibold text-fg ${
                active === matches.length ? "bg-surface-accent-subtle" : ""
              }`}
            >
              {t(m.tagCreate, { name: text.trim(), colour: colourLabels[colour] })}
            </li>
          ) : null}
        </ul>
      ) : null}
      {canCreate ? (
        <fieldset className="flex flex-wrap gap-1">
          <legend className="mb-1 text-xs font-medium text-fg-muted">{t(m.tagColour)}</legend>
          {TAG_COLOURS.map((value) => (
            <Button
              key={value}
              size="sm"
              variant={value === colour ? "primary" : "ghost"}
              aria-pressed={value === colour}
              onClick={() => setColour(value)}
            >
              <span
                aria-hidden="true"
                className="me-1 inline-block size-3 rounded-full"
                style={{ background: SWATCH[value] }}
              />
              {colourLabels[value]}
            </Button>
          ))}
        </fieldset>
      ) : null}
      {error ? (
        <p role="alert" className="text-sm font-medium text-fg-danger">
          {error}
        </p>
      ) : null}
    </div>
  );
}
