"use client";

import { Button, ChevronDownIcon, Dialog, Input } from "@numo9/ui";
import { useEffect, useId, useRef, useState, type FormEvent } from "react";

import { useFormatMessage } from "@/i18n";

import type { SavedView } from "./api";
import { m } from "./messages";

export interface SavedViewsRailProps {
  views: SavedView[];
  /** The open view; null = "All organisations" (or unsaved changes from it). */
  activeId: string | null;
  modified: boolean;
  failed: boolean;
  onApplyAll: () => void;
  onApply: (view: SavedView) => void;
  /** Resolve with an error message to keep the dialog open, or null when saved. */
  onSave: (name: string) => Promise<string | null>;
  onUpdate: (view: SavedView) => void;
  onRename: (view: SavedView, name: string) => Promise<string | null>;
  onSetDefault: (view: SavedView) => void;
  onDelete: (view: SavedView) => void;
}

type Dialogs =
  | { kind: "save" }
  | { kind: "rename"; view: SavedView }
  | { kind: "delete"; view: SavedView }
  | null;

/**
 * Saved views rail (V-01-T12): the user's own views, stored on the server — they follow the user
 * after logout/login and to another device. "All organisations" clears the search and filters;
 * each view has a menu: Update with changes, Rename, Set as default, Delete (confirmed).
 */
export function SavedViewsRail(props: SavedViewsRailProps) {
  const t = useFormatMessage();
  const headingId = useId();
  const [dialog, setDialog] = useState<Dialogs>(null);
  const [menuFor, setMenuFor] = useState<string | null>(null);

  return (
    <nav
      aria-labelledby={headingId}
      data-saved-views=""
      className="flex w-full shrink-0 flex-col gap-1 md:w-56"
    >
      <h2 id={headingId} className="px-2 text-xs font-bold tracking-wide text-fg-muted uppercase">
        {t(m.viewsTitle)}
      </h2>
      <ul className="flex flex-col gap-0.5">
        <li>
          <RailButton
            active={props.activeId === null && !props.modified}
            onClick={props.onApplyAll}
          >
            {t(m.viewsAll)}
          </RailButton>
        </li>
        {props.views.map((view) => (
          <li key={view.id} className="relative flex items-center">
            <RailButton active={props.activeId === view.id} onClick={() => props.onApply(view)}>
              {view.name}
              {view.is_default ? (
                <span className="ms-1 text-xs font-normal text-fg-muted">{t(m.viewsDefault)}</span>
              ) : null}
            </RailButton>
            <ViewMenu
              view={view}
              open={menuFor === view.id}
              onOpenChange={(open) => setMenuFor(open ? view.id : null)}
              canUpdate={props.activeId === view.id && props.modified}
              onUpdate={() => props.onUpdate(view)}
              onRename={() => setDialog({ kind: "rename", view })}
              onSetDefault={() => props.onSetDefault(view)}
              onDelete={() => setDialog({ kind: "delete", view })}
            />
          </li>
        ))}
      </ul>
      {props.failed ? <p className="px-2 text-sm text-fg-danger">{t(m.viewsLoadFailed)}</p> : null}
      <Button
        variant="ghost"
        size="sm"
        className="justify-start"
        onClick={() => setDialog({ kind: "save" })}
      >
        {t(m.viewsSave)}
      </Button>

      {dialog?.kind === "save" ? (
        <NameDialog
          title={t(m.viewsSaveTitle)}
          description={t(m.viewsSaveBody)}
          submit={t(m.viewsSaveButton)}
          initial=""
          onClose={() => setDialog(null)}
          onSubmit={props.onSave}
        />
      ) : null}
      {dialog?.kind === "rename" ? (
        <NameDialog
          title={t(m.viewsRenameTitle)}
          submit={t(m.viewsRenameButton)}
          initial={dialog.view.name}
          onClose={() => setDialog(null)}
          onSubmit={(name) => props.onRename(dialog.view, name)}
        />
      ) : null}
      {dialog?.kind === "delete" ? (
        <Dialog
          open
          onOpenChange={(open) => !open && setDialog(null)}
          title={t(m.viewsDeleteTitle, { name: dialog.view.name })}
          description={t(m.viewsDeleteBody)}
          closeLabel={t(m.close)}
          size="sm"
          footer={
            <>
              <Button onClick={() => setDialog(null)}>{t(m.cancel)}</Button>
              <Button
                variant="danger"
                onClick={() => {
                  props.onDelete(dialog.view);
                  setDialog(null);
                }}
              >
                {t(m.viewsDeleteButton)}
              </Button>
            </>
          }
        />
      ) : null}
    </nav>
  );
}

function RailButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      aria-current={active ? "true" : undefined}
      onClick={onClick}
      className={
        "min-h-touch-target w-full rounded-md px-2 text-start text-sm " +
        (active
          ? "border-s-4 border-border-accent bg-surface-accent-subtle font-semibold text-fg"
          : "text-fg-muted hover:bg-surface-subtle hover:text-fg")
      }
    >
      {children}
    </button>
  );
}

function ViewMenu({
  view,
  open,
  onOpenChange,
  canUpdate,
  onUpdate,
  onRename,
  onSetDefault,
  onDelete,
}: {
  view: SavedView;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  canUpdate: boolean;
  onUpdate: () => void;
  onRename: () => void;
  onSetDefault: () => void;
  onDelete: () => void;
}) {
  const t = useFormatMessage();
  const menuId = useId();
  const button = useRef<HTMLButtonElement>(null);
  const list = useRef<HTMLUListElement>(null);
  useEffect(() => {
    if (open) list.current?.querySelector<HTMLButtonElement>("button")?.focus();
  }, [open]);
  const choose = (action: () => void) => () => {
    onOpenChange(false);
    action();
    button.current?.focus();
  };
  const items: { label: string; action: () => void; danger?: boolean }[] = [
    ...(canUpdate ? [{ label: t(m.viewsUpdate), action: onUpdate }] : []),
    { label: t(m.viewsRename), action: onRename },
    ...(view.is_default ? [] : [{ label: t(m.viewsSetDefault), action: onSetDefault }]),
    { label: t(m.viewsDelete), action: onDelete, danger: true },
  ];
  return (
    <>
      <button
        ref={button}
        type="button"
        aria-haspopup="true"
        aria-expanded={open}
        aria-controls={open ? menuId : undefined}
        aria-label={t(m.viewsMenu, { name: view.name })}
        onClick={() => onOpenChange(!open)}
        className="min-h-touch-target rounded-md px-2 text-fg-muted hover:bg-surface-subtle hover:text-fg"
      >
        <span aria-hidden="true" className="inline-flex size-4">
          <ChevronDownIcon />
        </span>
      </button>
      {open ? (
        <ul
          ref={list}
          id={menuId}
          className="absolute end-0 top-full z-20 w-48 rounded-lg border border-border bg-surface p-1 shadow-elevation-3"
          onKeyDown={(event) => {
            const buttons = Array.from(list.current?.querySelectorAll("button") ?? []);
            const index = buttons.indexOf(document.activeElement as HTMLButtonElement);
            if (event.key === "Escape") {
              event.preventDefault();
              onOpenChange(false);
              button.current?.focus();
            } else if (event.key === "ArrowDown" || event.key === "ArrowUp") {
              event.preventDefault();
              const step = event.key === "ArrowDown" ? 1 : -1;
              buttons[(index + step + buttons.length) % buttons.length]?.focus();
            }
          }}
        >
          {items.map((item) => (
            <li key={item.label}>
              <button
                type="button"
                onClick={choose(item.action)}
                className={
                  "min-h-touch-target w-full rounded-md px-2 text-start text-sm hover:bg-surface-subtle " +
                  (item.danger ? "text-fg-danger" : "text-fg")
                }
              >
                {item.label}
              </button>
            </li>
          ))}
        </ul>
      ) : null}
    </>
  );
}

function NameDialog({
  title,
  description,
  submit,
  initial,
  onClose,
  onSubmit,
}: {
  title: string;
  description?: string;
  submit: string;
  initial: string;
  onClose: () => void;
  onSubmit: (name: string) => Promise<string | null>;
}) {
  const t = useFormatMessage();
  const id = useId();
  const formId = useId();
  const [name, setName] = useState(initial);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const send = async (event: FormEvent) => {
    event.preventDefault();
    if (!name.trim()) {
      setError(t(m.viewsNameRequired));
      return;
    }
    setBusy(true);
    const problem = await onSubmit(name.trim());
    setBusy(false);
    if (problem) setError(problem);
    else onClose();
  };
  return (
    <Dialog
      open
      onOpenChange={(open) => !open && onClose()}
      title={title}
      description={description}
      closeLabel={t(m.close)}
      size="sm"
      footer={
        <>
          <Button onClick={onClose}>{t(m.cancel)}</Button>
          <Button variant="primary" type="submit" form={formId} loading={busy}>
            {submit}
          </Button>
        </>
      }
    >
      <form id={formId} onSubmit={send} className="grid gap-1" noValidate>
        <label htmlFor={id} className="text-sm font-medium text-fg">
          {t(m.viewsNameLabel)}
        </label>
        <Input
          id={id}
          value={name}
          maxLength={80}
          autoFocus
          invalid={Boolean(error)}
          aria-describedby={error ? `${id}-error` : undefined}
          onChange={(event) => {
            setName(event.target.value);
            setError("");
          }}
        />
        {error ? (
          <p id={`${id}-error`} className="text-sm font-medium text-fg-danger">
            {error}
          </p>
        ) : null}
      </form>
    </Dialog>
  );
}
