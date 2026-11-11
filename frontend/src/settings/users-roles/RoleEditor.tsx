"use client";

import {
  Badge,
  Button,
  Checkbox,
  Dialog,
  ExplainPanel,
  Input,
  LoadingRegion,
  Select,
  SkeletonText,
  type BadgeTone,
} from "@numo9/ui";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useId, useMemo, useState } from "react";

import { apiRequest } from "@/auth/client";
import { useFormatMessage } from "@/i18n";

import {
  errorText,
  isOk,
  orgApi,
  usersRolesApi,
  type ApiError,
  type Catalogue,
  type CataloguePermission,
  type Role,
} from "./api";
import { m, rm } from "./messages";
import { roleUrl, rolesTabUrl } from "./RolesPanel";

const RISK_TONE: Record<CataloguePermission["risk"], BadgeTone> = {
  low: "neutral",
  medium: "info",
  high: "warning",
  critical: "danger",
};

interface Loaded {
  catalogue: Catalogue;
  roles: Role[];
  mine: Set<string>;
  role: Role | null; // null: a new role
}

type State =
  | { kind: "loading" }
  | { kind: "ready"; data: Loaded }
  | { kind: "denied"; message: string }
  | { kind: "notFound" };

/** Organisation permissions only: what a custom organisation role can grant. */
function grantable(catalogue: Catalogue): CataloguePermission[] {
  return catalogue.permissions.filter((p) => p.scope === "organisation");
}

function matches(permission: CataloguePermission, moduleLabel: string, query: string): boolean {
  if (!query) return true;
  const text = `${permission.label} ${permission.key} ${moduleLabel} ${permission.risk_label}`;
  return text.toLocaleLowerCase().includes(query.toLocaleLowerCase());
}

/**
 * Role editor (A-03-T12): name, description, "Copy from role", and the permission matrix grouped
 * by module with search, risk badges and a select-all per module. Only organisation permissions
 * are listed (what a custom organisation role grants); permissions the editor doesn't hold are
 * disabled (the API refuses them too — no escalation). System roles open read-only with "Copy
 * into a custom role".
 */
export function RoleEditor({
  org,
  roleId,
  copyFrom,
}: {
  org: string;
  /** "new" or the role's id. */
  roleId: string;
  copyFrom?: string;
}) {
  const fm = useFormatMessage();
  const router = useRouter();
  const ids = {
    name: useId(),
    description: useId(),
    copy: useId(),
    search: useId(),
    hint: useId(),
  };
  const [state, setState] = useState<State>({ kind: "loading" });
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [nameError, setNameError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [copySource, setCopySource] = useState<string>("");
  const [confirmDelete, setConfirmDelete] = useState(false);

  const load = useCallback(async () => {
    const [catalogue, roles, mine] = await Promise.all([
      usersRolesApi.catalogue(),
      usersRolesApi.roles(org),
      apiRequest<{ permissions: string[] } | ApiError>(orgApi(org, "my-permissions")),
    ]);
    if (roles.status === 404 || mine.status === 404) return setState({ kind: "notFound" });
    if (!isOk<Role[]>(roles)) {
      return setState({ kind: "denied", message: errorText(roles.body) ?? fm(m.failed) });
    }
    if (!isOk<Catalogue>(catalogue) || !isOk<{ permissions: string[] }>(mine)) {
      return setState({ kind: "denied", message: fm(m.failed) });
    }
    let role: Role | null = null;
    if (roleId !== "new") {
      role = roles.body.find((r) => r.id === roleId) ?? null;
      if (role === null) return setState({ kind: "notFound" });
      setName(role.name);
      setDescription(role.description);
      setSelected(new Set(role.permissions));
    } else if (copyFrom) {
      const source = roles.body.find((r) => r.id === copyFrom);
      if (source) {
        setCopySource(source.id);
        setSelected(new Set(source.permissions));
      }
    }
    setState({
      kind: "ready",
      data: {
        catalogue: catalogue.body,
        roles: roles.body,
        mine: new Set(mine.body.permissions),
        role,
      },
    });
  }, [org, roleId, copyFrom, fm]);

  useEffect(() => {
    void load();
  }, [load]);

  const data = state.kind === "ready" ? state.data : null;
  const permissions = useMemo(() => (data ? grantable(data.catalogue) : []), [data]);
  const moduleLabels = useMemo(
    () => new Map((data?.catalogue.modules ?? []).map((mod) => [mod.key, mod.label])),
    [data],
  );

  if (state.kind === "loading") {
    return (
      <LoadingRegion label={fm(m.loading)}>
        <SkeletonText lines={8} />
      </LoadingRegion>
    );
  }
  if (state.kind === "notFound") {
    return <ExplainPanel kind="notFound" title={fm(m.notFoundTitle)} body={fm(m.notFoundBody)} />;
  }
  if (state.kind === "denied") {
    return <ExplainPanel kind="permission" title={fm(m.deniedTitle)} body={state.message} />;
  }

  const { role, roles, mine } = state.data;
  const readOnly = role !== null && !role.editable;
  const canManage = mine.has("roles.role.manage");
  const editable = !readOnly && canManage;
  const grantableKeys = new Set(permissions.map((p) => p.key));
  // What the editor may tick: permissions they hold (and, when editing, what the role has).
  const allowed = (key: string) => mine.has(key) || (role?.permissions.includes(key) ?? false);
  const selectedCount = [...selected].filter((k) => grantableKeys.has(k)).length;

  const toggle = (key: string, on: boolean) =>
    setSelected((prev) => {
      const next = new Set(prev);
      if (on) next.add(key);
      else next.delete(key);
      return next;
    });

  const copy = (sourceId: string) => {
    const source = roles.find((r) => r.id === sourceId);
    if (!source) return;
    setCopySource(sourceId);
    setSelected(new Set(source.permissions.filter((k) => grantableKeys.has(k))));
    setStatus(fm(rm.copied, { role: source.name }));
  };

  const save = async () => {
    setError(null);
    if (!name.trim()) {
      setNameError(fm(rm.nameRequired));
      return;
    }
    setBusy(true);
    const keys = [...selected].filter((k) => grantableKeys.has(k)).sort();
    const result =
      role === null
        ? await usersRolesApi.createRole(org, {
            name: name.trim(),
            description: description.trim(),
            permissions: keys,
          })
        : await usersRolesApi.updateRole(org, role.id, {
            name: name.trim(),
            description: description.trim(),
            permissions: keys,
          });
    setBusy(false);
    if (isOk<Role>(result)) {
      router.push(`${rolesTabUrl(org)}&saved=${encodeURIComponent(result.body.name)}`);
    } else {
      setError(errorText(result.body) ?? fm(m.failed));
    }
  };

  const remove = async () => {
    if (role === null) return;
    setBusy(true);
    const result = await usersRolesApi.deleteRole(org, role.id);
    setBusy(false);
    setConfirmDelete(false);
    if (result.status === 204) {
      router.push(`${rolesTabUrl(org)}&deleted=${encodeURIComponent(role.name)}`);
    } else {
      setError(errorText(result.body) ?? fm(m.failed));
    }
  };

  const title =
    role === null
      ? fm(rm.editorNew)
      : readOnly
        ? fm(rm.editorView, { role: role.name })
        : fm(rm.editorEdit, { role: role.name });
  const visible = permissions.filter((p) =>
    matches(p, moduleLabels.get(p.module) ?? p.module, query),
  );
  const modules = state.data.catalogue.modules
    .map((mod) => ({ ...mod, items: visible.filter((p) => p.module === mod.key) }))
    .filter((mod) => mod.items.length > 0);

  return (
    <div className="flex flex-col gap-6">
      <div>
        <Link
          href={rolesTabUrl(org)}
          className="text-sm font-semibold underline underline-offset-2"
        >
          {fm(rm.back)}
        </Link>
        <h1 className="mt-2 text-2xl font-semibold">{title}</h1>
      </div>
      {readOnly ? (
        <div className="flex flex-col items-start gap-3 rounded-md border-2 border-border bg-surface-info-subtle px-4 py-3 text-sm">
          <p>{fm(rm.systemReadOnly)}</p>
          {canManage ? (
            <Button asChild variant="secondary" size="sm">
              <Link href={`${roleUrl(org, "new")}?copy=${role.id}`}>{fm(rm.copyIntoCustom)}</Link>
            </Button>
          ) : null}
        </div>
      ) : null}
      {status ? (
        <p role="status" className="text-sm text-fg-muted">
          {status}
        </p>
      ) : null}
      {error ? (
        <p
          role="alert"
          className="rounded-md border-2 border-border-danger bg-surface-danger-subtle px-4 py-3 text-sm"
        >
          {error}
        </p>
      ) : null}
      {editable ? (
        <div className="grid gap-4 md:grid-cols-2">
          <div className="flex flex-col gap-1.5">
            <label htmlFor={ids.name} className="text-sm font-semibold">
              {fm(rm.name)}
            </label>
            <Input
              id={ids.name}
              value={name}
              maxLength={100}
              invalid={nameError !== null}
              aria-describedby={nameError ? `${ids.name}-error` : undefined}
              onChange={(event) => {
                setName(event.target.value);
                setNameError(null);
              }}
            />
            {nameError ? (
              <p id={`${ids.name}-error`} className="text-sm text-fg-danger">
                {nameError}
              </p>
            ) : null}
          </div>
          {role === null ? (
            <div className="flex flex-col gap-1.5">
              <span id={ids.copy} className="text-sm font-semibold">
                {fm(rm.copyFrom)}
              </span>
              <Select
                aria-labelledby={ids.copy}
                placeholder={fm(rm.copyFromPlaceholder)}
                value={copySource}
                onValueChange={copy}
                options={roles
                  .filter((r) => r.scope === "organisation")
                  .map((r) => ({ value: r.id, label: r.name }))}
              />
            </div>
          ) : null}
          <div className="flex flex-col gap-1.5 md:col-span-2">
            <label htmlFor={ids.description} className="text-sm font-semibold">
              {fm(rm.description)}
            </label>
            <Input
              id={ids.description}
              value={description}
              onChange={(event) => setDescription(event.target.value)}
            />
          </div>
        </div>
      ) : null}

      <section aria-labelledby={`${ids.search}-heading`} className="flex flex-col gap-3">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <h2 id={`${ids.search}-heading`} className="text-lg font-semibold">
            {fm(rm.matrix)}
          </h2>
          <p className="text-sm text-fg-muted" aria-live="polite">
            {fm(rm.selected, { selected: selectedCount, total: permissions.length })}
          </p>
        </div>
        <div className="flex flex-col gap-1.5">
          <label htmlFor={ids.search} className="text-sm font-semibold">
            {fm(rm.search)}
          </label>
          <Input
            id={ids.search}
            type="search"
            value={query}
            aria-describedby={ids.hint}
            onChange={(event) => setQuery(event.target.value)}
          />
          <p id={ids.hint} className="text-xs text-fg-muted">
            {fm(rm.searchHint)}
          </p>
        </div>
        {modules.length === 0 ? (
          <p role="status" className="text-sm text-fg-muted">
            {fm(rm.noMatch, { query })}
          </p>
        ) : null}
        {modules.map((mod) => {
          const keys = mod.items.map((p) => p.key);
          const open = keys.filter((k) => editable && allowed(k));
          const on = keys.filter((k) => selected.has(k)).length;
          const all: boolean | "indeterminate" =
            on === 0 ? false : on === keys.length ? true : "indeterminate";
          return (
            <fieldset key={mod.key} className="rounded-lg border border-border px-4 pb-2">
              <legend className="px-1 text-base font-semibold">{mod.label}</legend>
              {editable ? (
                <Checkbox
                  label={fm(rm.allInModule, { module: mod.label })}
                  checked={all}
                  disabled={open.length === 0}
                  onCheckedChange={(value) =>
                    setSelected((prev) => {
                      const next = new Set(prev);
                      for (const key of open) {
                        if (value === true) next.add(key);
                        else next.delete(key);
                      }
                      return next;
                    })
                  }
                />
              ) : null}
              <ul className="divide-y divide-border">
                {mod.items.map((permission) => (
                  <li
                    key={permission.key}
                    className="flex flex-wrap items-center justify-between gap-2"
                  >
                    <Checkbox
                      label={permission.label}
                      description={
                        editable && !allowed(permission.key) ? fm(rm.notYours) : permission.key
                      }
                      checked={selected.has(permission.key)}
                      disabled={!editable || !allowed(permission.key)}
                      onCheckedChange={(value) => toggle(permission.key, value === true)}
                    />
                    <span className="flex flex-wrap gap-1.5">
                      {permission.owner_only ? (
                        <Badge tone="inverse">{fm(rm.ownerOnly)}</Badge>
                      ) : null}
                      <Badge tone={RISK_TONE[permission.risk]} dot>
                        {permission.risk_label}
                      </Badge>
                    </span>
                  </li>
                ))}
              </ul>
            </fieldset>
          );
        })}
      </section>

      {editable ? (
        <div className="sticky bottom-0 flex flex-wrap justify-between gap-3 border-t border-border bg-surface py-3">
          <div>
            {role !== null ? (
              role.holders > 0 ? (
                <p className="max-w-md text-sm text-fg-muted">
                  {fm(rm.inUse, { count: role.holders })}
                </p>
              ) : (
                <Button variant="danger" onClick={() => setConfirmDelete(true)}>
                  {fm(rm.delete)}
                </Button>
              )
            ) : null}
          </div>
          <Button loading={busy} onClick={() => void save()}>
            {fm(rm.save)}
          </Button>
        </div>
      ) : null}
      {confirmDelete && role ? (
        <Dialog
          open
          onOpenChange={(open) => setConfirmDelete(open)}
          title={fm(rm.deleteConfirm, { role: role.name })}
          description={fm(rm.deleteBody)}
          closeLabel={fm(m.close)}
          footer={
            <>
              <Button variant="secondary" onClick={() => setConfirmDelete(false)}>
                {fm(m.cancel)}
              </Button>
              <Button variant="danger" loading={busy} onClick={() => void remove()}>
                {fm(rm.delete)}
              </Button>
            </>
          }
        />
      ) : null}
    </div>
  );
}
