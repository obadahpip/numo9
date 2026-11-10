"use client";

import { useCallback, useEffect, useState } from "react";

import { EMPTY_VIEW, type GridViewState } from "./types";

export interface SavedView {
  id: string;
  name: string;
  state: GridViewState;
}

/** Where saved views live: the browser now, the server in V-01 (views follow the user). */
export interface SavedViewsStore {
  load: () => Promise<SavedView[]> | SavedView[];
  save: (views: SavedView[]) => Promise<void> | void;
}

/** localStorage store keyed per grid (unavailable storage → views live for the page only). */
export function localSavedViewsStore(key: string): SavedViewsStore {
  return {
    load: () => {
      try {
        const raw = window.localStorage.getItem(key);
        const parsed: unknown = raw ? JSON.parse(raw) : [];
        return Array.isArray(parsed) ? (parsed as SavedView[]) : [];
      } catch {
        return [];
      }
    },
    save: (views) => {
      try {
        window.localStorage.setItem(key, JSON.stringify(views));
      } catch {
        // Storage blocked or full: keep the views in memory.
      }
    },
  };
}

export interface UseSavedViews {
  views: SavedView[];
  activeId: string | null;
  /** The grid's current view state (pass to `DataGrid view`). */
  view: GridViewState;
  setView: (view: GridViewState) => void;
  apply: (id: string) => void;
  /** Save the current state as a new view; returns it. */
  saveAs: (name: string) => SavedView;
  /** Overwrite the active view with the current state. */
  update: () => void;
  remove: (id: string) => void;
  /** True when the current state differs from the active view (show "Save view"). */
  modified: boolean;
}

let counter = 0;
const newId = () => `view-${Date.now().toString(36)}-${(counter++).toString(36)}`;

/**
 * Saved views (A-10-T10): named grid states (sort, search, filters, columns, density) the user
 * can return to — "Ontario retail" in the directory (F3). Pairs with `DataGrid`'s `view` /
 * `onViewChange`.
 */
export function useSavedViews(
  store: SavedViewsStore,
  initial: GridViewState = EMPTY_VIEW,
): UseSavedViews {
  const [views, setViews] = useState<SavedView[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [view, setView] = useState<GridViewState>(initial);

  useEffect(() => {
    let cancelled = false;
    void Promise.resolve(store.load()).then((loaded) => {
      if (!cancelled) setViews(loaded);
    });
    return () => {
      cancelled = true;
    };
    // The store is created once per grid.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const persist = useCallback(
    (next: SavedView[]) => {
      setViews(next);
      void store.save(next);
    },
    [store],
  );

  const apply = useCallback(
    (id: string) => {
      const found = views.find((v) => v.id === id);
      if (!found) return;
      setActiveId(id);
      setView(found.state);
    },
    [views],
  );

  const saveAs = useCallback(
    (name: string) => {
      const saved: SavedView = { id: newId(), name: name.trim(), state: view };
      persist([...views, saved]);
      setActiveId(saved.id);
      return saved;
    },
    [persist, view, views],
  );

  const update = useCallback(() => {
    if (!activeId) return;
    persist(views.map((v) => (v.id === activeId ? { ...v, state: view } : v)));
  }, [activeId, persist, view, views]);

  const remove = useCallback(
    (id: string) => {
      persist(views.filter((v) => v.id !== id));
      if (activeId === id) setActiveId(null);
    },
    [activeId, persist, views],
  );

  const active = views.find((v) => v.id === activeId);
  const modified = active ? JSON.stringify(active.state) !== JSON.stringify(view) : false;

  return { views, activeId, view, setView, apply, saveAs, update, remove, modified };
}
