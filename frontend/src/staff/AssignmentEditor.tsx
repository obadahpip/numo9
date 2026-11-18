"use client";

/**
 * Assignment editor (V-05-T04): the organisations a staff member works on directly and the
 * groups they are assigned to (with the group role). Search adds an organisation, a group and a
 * role assign a group; every change is saved at once and takes effect on their next request.
 */
import { Button, ErrorState, Input } from "@numo9/ui";
import { useEffect, useId, useState } from "react";

import { directoryApi } from "@/directory/api";
import { groupsApi, type Group } from "@/groups/api";
import { useFormatMessage, type MessageDescriptor } from "@/i18n";

import { assignmentsApi, type Assignments } from "./api";
import { m } from "./messages";

const ROLES: [string, MessageDescriptor][] = [
  ["accountant", m.roleAccountant],
  ["reviewer", m.roleReviewer],
  ["payroll_specialist", m.rolePayroll],
  ["read_only", m.roleReadOnly],
];

export interface AssignmentEditorProps {
  practice: string;
  user: { id: string; name: string };
}

export function AssignmentEditor({ practice, user }: AssignmentEditorProps) {
  const fm = useFormatMessage();
  const ids = { search: useId(), group: useId(), role: useId() };
  const [data, setData] = useState<Assignments | null>(null);
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [groups, setGroups] = useState<Group[]>([]);
  const [q, setQ] = useState("");
  const [found, setFound] = useState<{ id: string; name: string }[]>([]);
  const [group, setGroup] = useState("");
  const [role, setRole] = useState("accountant");
  const [status, setStatus] = useState("");

  useEffect(() => {
    let cancelled = false;
    void assignmentsApi.get(practice, user.id).then((result) => {
      if (cancelled) return;
      if (result.status === 200) setData(result.body);
      else setFailed(true);
    });
    void groupsApi
      .list(practice)
      .then((r) => !cancelled && r.status === 200 && setGroups(r.body.groups));
    return () => {
      cancelled = true;
    };
  }, [practice, user.id, attempt]);

  useEffect(() => {
    if (q.trim().length < 2) {
      setFound([]);
      return;
    }
    const controller = new AbortController();
    const timer = setTimeout(() => {
      void directoryApi
        .list({ practice, q, pageSize: 10, facets: false, signal: controller.signal })
        .then((result) => {
          if (result.status === 200)
            setFound(result.body.results.map((row) => ({ id: row.id, name: row.name })));
        });
    }, 250);
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [practice, q]);

  const save = async (request: Promise<{ status: number; body: unknown }>) => {
    const result = await request;
    if (result.status === 200) {
      setData(result.body as Assignments);
      setStatus(fm(m.saved));
    } else setStatus(fm(m.failed));
  };

  if (failed) {
    return (
      <ErrorState
        title={fm(m.loadFailed)}
        retryLabel={fm(m.retry)}
        onRetry={() => {
          setFailed(false);
          setAttempt((n) => n + 1);
        }}
        headingLevel={2}
      />
    );
  }
  if (!data) return null;
  const assigned = new Set(data.organisations.map((org) => org.id));
  const roleLabel = (key: string) =>
    fm(ROLES.find(([value]) => value === key)?.[1] ?? m.roleAccountant);

  return (
    <div className="flex flex-col gap-4" data-assignment-editor="">
      <h2 className="text-lg font-semibold text-fg">
        {fm(m.assignmentsTitle, { name: user.name })}
      </h2>
      <p className="text-sm text-fg-muted">{fm(m.immediate)}</p>
      <p role="status" className="sr-only">
        {status}
      </p>
      <div className="grid gap-6 md:grid-cols-2">
        <section className="flex flex-col gap-2" aria-labelledby={`${ids.search}-h`}>
          <h3 id={`${ids.search}-h`} className="text-sm font-semibold">
            {fm(m.organisations)}
          </h3>
          {data.organisations.length ? (
            <ul className="flex flex-col divide-y divide-border rounded-md border border-border">
              {data.organisations.map((org) => (
                <li key={org.id} className="flex items-center justify-between px-3 py-1 text-sm">
                  {org.name}
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() =>
                      void save(assignmentsApi.unassignOrganisation(practice, user.id, org.id))
                    }
                  >
                    {fm(m.remove, { name: org.name })}
                  </Button>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-fg-muted">{fm(m.none)}</p>
          )}
          <label htmlFor={ids.search} className="text-xs font-semibold text-fg-muted">
            {fm(m.searchOrganisations)}
          </label>
          <Input id={ids.search} type="search" value={q} onChange={(e) => setQ(e.target.value)} />
          {found.filter((org) => !assigned.has(org.id)).length ? (
            <ul className="flex flex-col rounded-md border border-border">
              {found
                .filter((org) => !assigned.has(org.id))
                .map((org) => (
                  <li key={org.id}>
                    <button
                      type="button"
                      className="w-full px-2 py-1 text-start text-sm hover:bg-surface-muted"
                      aria-label={fm(m.add, { name: org.name })}
                      onClick={() => {
                        setQ("");
                        void save(assignmentsApi.assignOrganisation(practice, user.id, org.id));
                      }}
                    >
                      {org.name}
                    </button>
                  </li>
                ))}
            </ul>
          ) : null}
        </section>
        <section className="flex flex-col gap-2" aria-labelledby={`${ids.group}-h`}>
          <h3 id={`${ids.group}-h`} className="text-sm font-semibold">
            {fm(m.groups)}
          </h3>
          {data.groups.length ? (
            <ul className="flex flex-col divide-y divide-border rounded-md border border-border">
              {data.groups.map((item) => (
                <li key={item.id} className="flex items-center justify-between px-3 py-1 text-sm">
                  <span>{fm(m.groupLine, { name: item.name, role: roleLabel(item.role) })}</span>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() =>
                      void save(assignmentsApi.unassignGroup(practice, user.id, item.id))
                    }
                  >
                    {fm(m.remove, { name: item.name })}
                  </Button>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-fg-muted">{fm(m.none)}</p>
          )}
          <div className="flex flex-wrap items-end gap-2">
            <div className="grid gap-1">
              <label htmlFor={ids.group} className="text-xs font-semibold text-fg-muted">
                {fm(m.group)}
              </label>
              <select
                id={ids.group}
                className="min-h-touch-target rounded-md border border-border-strong bg-surface px-2 text-sm"
                value={group}
                onChange={(e) => setGroup(e.target.value)}
              >
                <option value="">{fm(m.choose)}</option>
                {groups.map((item) => (
                  <option key={item.id} value={item.id}>
                    {"— ".repeat(Math.max(0, item.depth - 1)) + item.name}
                  </option>
                ))}
              </select>
            </div>
            <div className="grid gap-1">
              <label htmlFor={ids.role} className="text-xs font-semibold text-fg-muted">
                {fm(m.role)}
              </label>
              <select
                id={ids.role}
                className="min-h-touch-target rounded-md border border-border-strong bg-surface px-2 text-sm"
                value={role}
                onChange={(e) => setRole(e.target.value)}
              >
                {ROLES.map(([value, label]) => (
                  <option key={value} value={value}>
                    {fm(label)}
                  </option>
                ))}
              </select>
            </div>
            <Button
              disabled={!group}
              onClick={() => void save(assignmentsApi.assignGroup(practice, user.id, group, role))}
            >
              {fm(m.addGroup)}
            </Button>
          </div>
        </section>
      </div>
    </div>
  );
}
