"use client";

import { useEffect } from "react";

import { Button } from "../primitives/Button";

export interface StickySaveBarProps {
  visible: boolean;
  saving?: boolean;
  onSave: () => void;
  onDiscard: () => void;
  labels: { save: string; saving: string; discard: string; unsavedChanges: string };
}

/**
 * Sticky save bar (A-10-T07): stays at the bottom of the viewport while there are unsaved
 * changes, so Save is never below the fold (gap-12 spirit). Ctrl/⌘+S saves.
 */
export function StickySaveBar({
  visible,
  saving = false,
  onSave,
  onDiscard,
  labels,
}: StickySaveBarProps) {
  useEffect(() => {
    if (!visible) return;
    const onKey = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "s") {
        event.preventDefault();
        if (!saving) onSave();
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [visible, saving, onSave]);

  if (!visible) return null;
  return (
    <div
      data-save-bar=""
      className="sticky bottom-0 z-20 -mx-4 mt-6 flex flex-wrap items-center gap-3 border-t border-border bg-surface px-4 py-3 shadow-elevation-2 md:-mx-6 md:px-6"
    >
      <p role="status" className="me-auto text-sm text-fg-muted">
        {labels.unsavedChanges}
      </p>
      <Button onClick={onDiscard} disabled={saving}>
        {labels.discard}
      </Button>
      <Button variant="primary" type="submit" loading={saving}>
        {saving ? labels.saving : labels.save}
      </Button>
    </div>
  );
}
