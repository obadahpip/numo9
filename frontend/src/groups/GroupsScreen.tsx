"use client";

import { Button, Dialog, ErrorState, Input, RadioGroup } from "@numo9/ui";
import { useCallback, useEffect, useId, useState, type FormEvent } from "react";

import { useFormatMessage } from "@/i18n";

import { groupsApi, moveTargets, refusal, type Group } from "./api";
import { GroupTree } from "./GroupTree";
import { m } from "./messages";

type Editing =
  | { kind: "create"; parent: Group | null }
  | { kind: "rename"; group: Group }
  | { kind: "move"; group: Group }
  | null;

/**
 * Groups and tags of a practice (V-02-T09…T11), `/p/:practice/groups`: the group tree with
 * create, rename and move (drag and drop, or "Move to…" from the keyboard). Every change goes to
 * `/api/v1/practice/groups…`; a refusal (rule or permission) is shown as the server says it.
 */
export function GroupsScreen({ practice }: { practice: string }) {
  const t = useFormatMessage();
  const [groups, setGroups] = useState<Group[]>([]);
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");
  const [editing, setEditing] = useState<Editing>(null);
  const [error, setError] = useState("");
  const [announcement, setAnnouncement] = useState("");

  const load = useCallback(async () => {
    const result = await groupsApi.list(practice);
    if (result.status === 200 && Array.isArray(result.body.groups)) {
      setGroups(result.body.groups);
      setStatus("ready");
    } else {
      setStatus("error");
    }
  }, [practice]);
  useEffect(() => {
    void load();
  }, [load]);

  const move = async (group: Group, parent: Group | null) => {
    setError("");
    const result = await groupsApi.move(group.id, parent?.id ?? null);
    if (result.status === 200) {
      setAnnouncement(t(m.moved, { name: group.name }));
      setEditing(null);
      await load();
    } else {
      setError(refusal(result) ?? t(m.failed));
    }
  };

  return (
    <div className="flex flex-col gap-4" data-groups-screen="">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-fg">{t(m.title)}</h1>
          <p className="max-w-prose text-sm text-fg-muted">{t(m.intro)}</p>
        </div>
        <Button variant="primary" onClick={() => setEditing({ kind: "create", parent: null })}>
          {t(m.newGroup)}
        </Button>
      </header>
      {error ? (
        <p role="alert" className="text-sm font-medium text-fg-danger">
          {error}
        </p>
      ) : null}
      {status === "loading" ? <p className="text-sm text-fg-muted">{t(m.loading)}</p> : null}
      {status === "error" ? (
        <ErrorState
          title={t(m.loadFailed)}
          retryLabel={t(m.retry)}
          onRetry={() => void load()}
          headingLevel={2}
        />
      ) : null}
      {status === "ready" && groups.length === 0 ? (
        <p className="text-sm text-fg-muted">{t(m.empty)}</p>
      ) : null}
      {status === "ready" && groups.length > 0 ? (
        <GroupTree
          groups={groups}
          onMove={(group, parent) => void move(group, parent)}
          onMoveTo={(group) => setEditing({ kind: "move", group })}
          onAddSub={(group) => setEditing({ kind: "create", parent: group })}
          onRename={(group) => setEditing({ kind: "rename", group })}
        />
      ) : null}
      {editing?.kind === "move" ? (
        <MoveDialog
          group={editing.group}
          groups={groups}
          onClose={() => setEditing(null)}
          onMove={(parent) => move(editing.group, parent)}
          error={error}
        />
      ) : null}
      {editing?.kind === "create" || editing?.kind === "rename" ? (
        <NameDialog
          title={
            editing.kind === "rename"
              ? t(m.renameTitle, { name: editing.group.name })
              : editing.parent
                ? t(m.createSubTitle, { name: editing.parent.name })
                : t(m.createTitle)
          }
          initial={editing.kind === "rename" ? editing.group.name : ""}
          onClose={() => setEditing(null)}
          onSave={async (name) => {
            const result =
              editing.kind === "rename"
                ? await groupsApi.rename(editing.group.id, name)
                : await groupsApi.create(practice, name, editing.parent?.id ?? null);
            if (result.status === 200 || result.status === 201) {
              setEditing(null);
              await load();
              return null;
            }
            return refusal(result) ?? t(m.failed);
          }}
        />
      ) : null}
      <p role="status" className="sr-only">
        {announcement}
      </p>
    </div>
  );
}

function MoveDialog({
  group,
  groups,
  onClose,
  onMove,
  error,
}: {
  group: Group;
  groups: Group[];
  onClose: () => void;
  onMove: (parent: Group | null) => Promise<void>;
  error: string;
}) {
  const t = useFormatMessage();
  const targets = moveTargets(groups, group);
  const first = targets[0];
  const [choice, setChoice] = useState<string>(first === undefined ? "" : (first?.id ?? "top"));
  const [busy, setBusy] = useState(false);
  return (
    <Dialog
      open
      onOpenChange={(open) => !open && onClose()}
      title={t(m.moveTitle, { name: group.name })}
      description={t(m.moveBody, { name: group.name })}
      closeLabel={t(m.close)}
      footer={
        <>
          <Button onClick={onClose}>{t(m.cancel)}</Button>
          <Button
            variant="primary"
            loading={busy}
            disabled={!targets.length}
            onClick={async () => {
              setBusy(true);
              await onMove(choice === "top" ? null : (groups.find((g) => g.id === choice) ?? null));
              setBusy(false);
            }}
          >
            {t(m.moveConfirm)}
          </Button>
        </>
      }
    >
      {targets.length ? (
        <RadioGroup
          aria-label={t(m.moveTitle, { name: group.name })}
          value={choice}
          onValueChange={setChoice}
          options={targets.map((target) => ({
            value: target?.id ?? "top",
            label: target ? (
              <span style={{ paddingInlineStart: `${(target.depth - 1) * 1}rem` }}>
                {target.name}
              </span>
            ) : (
              t(m.moveTop)
            ),
          }))}
        />
      ) : (
        <p className="text-sm text-fg-muted">{t(m.moveNone)}</p>
      )}
      {error ? (
        <p role="alert" className="mt-2 text-sm font-medium text-fg-danger">
          {error}
        </p>
      ) : null}
    </Dialog>
  );
}

function NameDialog({
  title,
  initial,
  onClose,
  onSave,
}: {
  title: string;
  initial: string;
  onClose: () => void;
  onSave: (name: string) => Promise<string | null>;
}) {
  const t = useFormatMessage();
  const id = useId();
  const formId = useId();
  const [name, setName] = useState(initial);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    const problem = await onSave(name);
    setBusy(false);
    if (problem) setError(problem);
  };
  return (
    <Dialog
      open
      onOpenChange={(open) => !open && onClose()}
      title={title}
      closeLabel={t(m.close)}
      size="sm"
      footer={
        <>
          <Button onClick={onClose}>{t(m.cancel)}</Button>
          <Button variant="primary" type="submit" form={formId} loading={busy}>
            {t(m.save)}
          </Button>
        </>
      }
    >
      <form id={formId} onSubmit={submit} className="grid gap-1" noValidate>
        <label htmlFor={id} className="text-sm font-medium text-fg">
          {t(m.nameLabel)}
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
