"use client";

import { Button } from "@numo9/ui";
import { useRef, useState, type DragEvent, type KeyboardEvent } from "react";

import { useFormatMessage } from "@/i18n";

import type { Group } from "./api";
import { m } from "./messages";

export interface GroupTreeProps {
  groups: Group[];
  /** Drop or "Move to…" result: move `group` under `parent` (null = top level). */
  onMove: (group: Group, parent: Group | null) => void;
  onMoveTo: (group: Group) => void;
  onAddSub: (group: Group) => void;
  onRename: (group: Group) => void;
  onDelete: (group: Group) => void;
}

const DRAG_TYPE = "application/x-numo9-group";

/**
 * Group tree (V-02-T09): the practice's groups in tree order as an ARIA tree (`aria-level`,
 * roving focus with ↑/↓, Home/End). Each group shows its organisations (sub-groups included) and
 * staff, and has Add sub-group, Rename, Move to… (the keyboard alternative to dragging) and Delete
 * (which opens the impact dialog, V-02-T11). Drag a group onto another group to move it under it, or onto the "Top level" zone.
 */
export function GroupTree({
  groups,
  onMove,
  onMoveTo,
  onAddSub,
  onRename,
  onDelete,
}: GroupTreeProps) {
  const t = useFormatMessage();
  const [focused, setFocused] = useState(0);
  const [dragging, setDragging] = useState<string | null>(null);
  const [over, setOver] = useState<string | null>(null);
  const items = useRef<(HTMLLIElement | null)[]>([]);
  const byId = new Map(groups.map((g) => [g.id, g]));

  const focus = (index: number) => {
    const next = Math.max(0, Math.min(groups.length - 1, index));
    setFocused(next);
    items.current[next]?.focus();
  };
  const onKeyDown = (event: KeyboardEvent<HTMLLIElement>, index: number) => {
    if (event.target !== event.currentTarget) return; // keys inside the row's buttons
    const keys: Record<string, number> = {
      ArrowDown: index + 1,
      ArrowUp: index - 1,
      Home: 0,
      End: groups.length - 1,
    };
    if (event.key in keys) {
      event.preventDefault();
      focus(keys[event.key]!);
    }
  };
  const drop = (event: DragEvent, parent: Group | null) => {
    event.preventDefault();
    const id = event.dataTransfer.getData(DRAG_TYPE) || dragging;
    setDragging(null);
    setOver(null);
    const moving = id ? byId.get(id) : undefined;
    if (moving && moving.id !== parent?.id) onMove(moving, parent);
  };

  return (
    <div className="flex flex-col gap-2">
      <ul
        role="tree"
        aria-label={t(m.treeLabel)}
        className="flex flex-col gap-1"
        data-group-tree=""
      >
        {groups.map((group, index) => (
          <li
            key={group.id}
            ref={(node) => {
              items.current[index] = node;
            }}
            role="treeitem"
            aria-level={group.depth}
            aria-selected={focused === index}
            aria-expanded={group.has_children ? true : undefined}
            tabIndex={focused === index ? 0 : -1}
            onFocus={(event) => event.target === event.currentTarget && setFocused(index)}
            onKeyDown={(event) => onKeyDown(event, index)}
            draggable
            onDragStart={(event) => {
              event.dataTransfer.setData(DRAG_TYPE, group.id);
              event.dataTransfer.effectAllowed = "move";
              setDragging(group.id);
            }}
            onDragEnd={() => {
              setDragging(null);
              setOver(null);
            }}
            onDragOver={(event) => {
              if (dragging && dragging !== group.id) {
                event.preventDefault();
                setOver(group.id);
              }
            }}
            onDragLeave={() => setOver((current) => (current === group.id ? null : current))}
            onDrop={(event) => drop(event, group)}
            data-group={group.id}
            style={{ marginInlineStart: `${(group.depth - 1) * 1.5}rem` }}
            className={`flex flex-wrap items-center justify-between gap-2 rounded-md border px-3 py-2 focus-visible:outline-2 focus-visible:outline-offset-2 ${
              over === group.id
                ? "border-border-strong bg-surface-accent-subtle"
                : "border-border bg-surface"
            }`}
          >
            <div className="min-w-0">
              <p className="font-semibold text-fg">{group.name}</p>
              <p className="text-xs text-fg-muted">
                {t(m.counts, {
                  organisations: group.subtree_organisation_count,
                  staff: group.staff_count,
                })}
              </p>
            </div>
            <div className="flex flex-wrap gap-1">
              <Button
                size="sm"
                variant="ghost"
                aria-label={t(m.addSubGroup, { name: group.name })}
                onClick={() => onAddSub(group)}
                disabled={group.depth >= 5}
              >
                {t(m.addSubGroupShort)}
              </Button>
              <Button
                size="sm"
                variant="ghost"
                aria-label={t(m.renameFor, { name: group.name })}
                onClick={() => onRename(group)}
              >
                {t(m.rename)}
              </Button>
              <Button
                size="sm"
                variant="ghost"
                aria-label={t(m.moveToFor, { name: group.name })}
                onClick={() => onMoveTo(group)}
              >
                {t(m.moveTo)}
              </Button>
              <Button
                size="sm"
                variant="ghost"
                aria-label={t(m.deleteFor, { name: group.name })}
                onClick={() => onDelete(group)}
              >
                {t(m.delete)}
              </Button>
            </div>
          </li>
        ))}
      </ul>
      {dragging ? (
        <div
          data-drop-top=""
          onDragOver={(event) => {
            event.preventDefault();
            setOver("top");
          }}
          onDrop={(event) => drop(event, null)}
          className={`rounded-md border border-dashed px-3 py-3 text-center text-sm ${
            over === "top" ? "border-border-strong bg-surface-accent-subtle" : "border-border"
          }`}
        >
          {t(m.dropTop)}
        </div>
      ) : null}
      <p className="text-xs text-fg-muted">{t(m.dragHint)}</p>
    </div>
  );
}
