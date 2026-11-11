"use client";

import {
  Badge,
  Button,
  CurrencyInput,
  ErrorState,
  formatMoney,
  LoadingRegion,
  Select,
  SkeletonTable,
  useToast,
  type SelectGroup,
} from "@numo9/ui";
import { useLocale } from "next-intl";
import { useCallback, useEffect, useId, useState } from "react";

import { apiRequest } from "@/auth/client";
import { useFormatMessage } from "@/i18n";
import type { AppLocale } from "@/i18n/locales";

import {
  DOC_TYPES,
  errorText,
  isOk,
  orgApi,
  usersRolesApi,
  type ApiError,
  type ApprovalLimit,
  type DocType,
  type Member,
  type Role,
} from "./api";
import { lm, m } from "./messages";

interface CheckResult {
  allowed: boolean;
  limit: string | null;
  code: string | null;
  detail: string | null;
  approvers: { id: string; name: string; limit: string }[];
}

const whoName = (row: ApprovalLimit) => row.user?.name ?? row.role?.name ?? "";

/**
 * Approval limits (A-03-T13): per document type, the limit of each person or role, in CAD, with
 * add / change / remove (needs `roles.limit.manage`), and "Verify an amount" — the same
 * `assert_can_approve` the documents use (A-03-T07), so a saved limit is seen enforced.
 */
export function LimitsPanel({
  org,
  roles,
  canManage,
}: {
  org: string;
  roles: Role[];
  canManage: boolean;
}) {
  const fm = useFormatMessage();
  const locale = useLocale() as AppLocale;
  const toast = useToast();
  const [rows, setRows] = useState<ApprovalLimit[] | null>(null);
  const [people, setPeople] = useState<Member[]>([]);
  const [failed, setFailed] = useState(false);

  const load = useCallback(async () => {
    setFailed(false);
    const [limits, members] = await Promise.all([
      usersRolesApi.limits(org),
      usersRolesApi.members(org),
    ]);
    if (!isOk<ApprovalLimit[]>(limits)) {
      setFailed(true);
      return;
    }
    setRows(limits.body);
    setPeople(isOk<Member[]>(members) ? members.body : []);
  }, [org]);

  useEffect(() => {
    void load();
  }, [load]);

  if (failed) {
    return (
      <ErrorState
        title={fm(m.loadFailed)}
        retryLabel={fm(m.retry)}
        onRetry={() => void load()}
        headingLevel={3}
      />
    );
  }
  if (rows === null) {
    return (
      <LoadingRegion label={fm(m.loading)}>
        <SkeletonTable rows={4} columns={3} />
      </LoadingRegion>
    );
  }

  const money = (amount: string) => formatMoney(amount, { locale });

  return (
    <div className="flex flex-col gap-8">
      <div>
        <h2 className="text-lg font-semibold">{fm(lm.heading)}</h2>
        <p className="mt-1 max-w-3xl text-sm text-fg-muted">{fm(lm.intro)}</p>
      </div>
      {canManage ? (
        <AddLimit
          org={org}
          roles={roles}
          people={people}
          onSaved={async (row) => {
            toast.toast({
              title: fm(lm.saved, {
                who: whoName(row),
                type: fm(lm.docType, { type: row.doc_type }).toLocaleLowerCase(locale),
                amount: money(row.max_amount),
              }),
              tone: "success",
            });
            await load();
          }}
        />
      ) : null}
      {DOC_TYPES.map((type) => {
        const ofType = rows.filter((r) => r.doc_type === type);
        const label = fm(lm.docType, { type });
        return (
          <section key={type} aria-labelledby={`limits-${type}`} className="flex flex-col gap-2">
            <h3 id={`limits-${type}`} className="text-base font-semibold">
              {label}
            </h3>
            {ofType.length === 0 ? (
              <p className="text-sm text-fg-muted">
                {fm(lm.none, { type: label.toLocaleLowerCase(locale) })}
              </p>
            ) : (
              <div className="relative overflow-x-auto rounded-lg border border-border">
                <table className="w-full border-collapse text-sm [overflow-wrap:anywhere]">
                  <caption className="sr-only">{fm(lm.table, { type: label })}</caption>
                  <thead className="bg-surface-muted text-xs font-semibold text-fg-muted">
                    <tr>
                      <th scope="col" className="px-3 py-2 text-start">
                        {fm(lm.colWho)}
                      </th>
                      <th scope="col" className="px-3 py-2 text-end">
                        {fm(lm.colAmount)}
                      </th>
                      {canManage ? (
                        <th scope="col" className="px-3 py-2 text-end">
                          <span className="sr-only">{fm(m.colActions)}</span>
                        </th>
                      ) : null}
                    </tr>
                  </thead>
                  <tbody>
                    {ofType.map((row) => (
                      <LimitRow
                        key={row.id}
                        org={org}
                        row={row}
                        canManage={canManage}
                        onChanged={async (message) => {
                          toast.toast({ title: message });
                          await load();
                        }}
                      />
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        );
      })}
      <CheckAmount org={org} people={people} />
    </div>
  );
}

function LimitRow({
  org,
  row,
  canManage,
  onChanged,
}: {
  org: string;
  row: ApprovalLimit;
  canManage: boolean;
  onChanged: (message: string) => Promise<void>;
}) {
  const fm = useFormatMessage();
  const locale = useLocale() as AppLocale;
  const [editing, setEditing] = useState(false);
  const [amount, setAmount] = useState<string | null>(row.max_amount);
  const [error, setError] = useState<string | null>(null);
  const who = whoName(row);

  const save = async () => {
    if (amount === null) {
      setError(fm(lm.amountInvalid));
      return;
    }
    const result = await usersRolesApi.updateLimit(org, row.id, amount);
    if (isOk<ApprovalLimit>(result)) {
      setEditing(false);
      await onChanged(
        fm(lm.saved, {
          who,
          type: fm(lm.docType, { type: row.doc_type }).toLocaleLowerCase(locale),
          amount: formatMoney(result.body.max_amount, { locale }),
        }),
      );
    } else setError(errorText(result.body) ?? fm(m.failed));
  };

  const remove = async () => {
    const result = await usersRolesApi.deleteLimit(org, row.id);
    if (result.status === 204) await onChanged(fm(lm.removed, { who }));
    else setError(errorText(result.body) ?? fm(m.failed));
  };

  return (
    <tr className="border-t border-border">
      <th scope="row" className="px-3 py-2 text-start font-normal">
        {row.user ? (
          row.user.name
        ) : (
          <Badge tone="info">{fm(lm.roleBadge, { role: row.role?.name ?? "" })}</Badge>
        )}
        {error ? (
          <p role="alert" className="mt-1 text-sm text-fg-danger">
            {error}
          </p>
        ) : null}
      </th>
      <td className="px-3 py-2 text-end tabular-nums">
        {editing ? (
          <CurrencyInput
            aria-label={fm(lm.edit, { who })}
            value={amount}
            onChange={setAmount}
            locale={locale}
            unreadableMessage={fm(lm.amountInvalid)}
            className="ms-auto max-w-40"
          />
        ) : (
          formatMoney(row.max_amount, { locale })
        )}
      </td>
      {canManage ? (
        <td className="px-3 py-2 text-end whitespace-nowrap">
          {editing ? (
            <Button size="sm" onClick={() => void save()}>
              {fm(lm.save)}
            </Button>
          ) : (
            <span className="inline-flex gap-2">
              <Button
                size="sm"
                variant="secondary"
                aria-label={fm(lm.edit, { who })}
                onClick={() => setEditing(true)}
              >
                {fm(lm.editShort)}
              </Button>
              <Button
                size="sm"
                variant="ghost"
                aria-label={fm(lm.remove, { who })}
                onClick={() => void remove()}
              >
                {fm(lm.removeShort)}
              </Button>
            </span>
          )}
        </td>
      ) : null}
    </tr>
  );
}

function AddLimit({
  org,
  roles,
  people,
  onSaved,
}: {
  org: string;
  roles: Role[];
  people: Member[];
  onSaved: (row: ApprovalLimit) => Promise<void>;
}) {
  const fm = useFormatMessage();
  const locale = useLocale() as AppLocale;
  const ids = { type: useId(), who: useId(), amount: useId(), error: useId() };
  const [type, setType] = useState<DocType>("bill");
  const [who, setWho] = useState("");
  const [amount, setAmount] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const groups: SelectGroup[] = [
    {
      label: fm(lm.people),
      options: people.map((p) => ({ value: `user:${p.id}`, label: p.name })),
    },
    {
      label: fm(lm.roles),
      options: roles
        .filter((r) => r.scope === "organisation" || r.is_system)
        .map((r) => ({ value: `role:${r.id}`, label: r.name })),
    },
  ].filter((g) => g.options.length > 0);

  const submit = async () => {
    if (!who) return setError(fm(lm.whoRequired));
    if (amount === null) return setError(fm(lm.amountInvalid));
    const [kind, id] = who.split(":");
    setBusy(true);
    const result = await usersRolesApi.createLimit(org, {
      doc_type: type,
      max_amount: amount,
      ...(kind === "user" ? { user: id } : { role: id }),
    });
    setBusy(false);
    if (isOk<ApprovalLimit>(result)) {
      setWho("");
      setAmount(null);
      setError(null);
      await onSaved(result.body);
    } else setError(errorText(result.body) ?? fm(m.failed));
  };

  return (
    <section aria-labelledby={ids.type + "-h"} className="rounded-lg border border-border p-4">
      <h3 id={ids.type + "-h"} className="text-base font-semibold">
        {fm(lm.add)}
      </h3>
      <form
        noValidate
        className="mt-3 grid gap-4 md:grid-cols-[1fr_1fr_12rem_auto] md:items-end"
        onSubmit={(event) => {
          event.preventDefault();
          void submit();
        }}
      >
        <div className="flex flex-col gap-1.5">
          <span id={ids.type} className="text-sm font-semibold">
            {fm(lm.type)}
          </span>
          <Select
            aria-labelledby={ids.type}
            value={type}
            onValueChange={(value) => setType(value as DocType)}
            options={DOC_TYPES.map((t) => ({ value: t, label: fm(lm.docType, { type: t }) }))}
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <span id={ids.who} className="text-sm font-semibold">
            {fm(lm.who)}
          </span>
          <Select
            aria-labelledby={ids.who}
            value={who}
            placeholder={fm(lm.whoPlaceholder)}
            onValueChange={(value) => {
              setWho(value);
              setError(null);
            }}
            options={groups}
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <label htmlFor={ids.amount} className="text-sm font-semibold">
            {fm(lm.amount)}
          </label>
          <CurrencyInput
            id={ids.amount}
            value={amount}
            onChange={(value) => {
              setAmount(value);
              setError(null);
            }}
            locale={locale}
            unreadableMessage={fm(lm.amountInvalid)}
          />
        </div>
        <Button type="submit" loading={busy}>
          {fm(lm.save)}
        </Button>
      </form>
      {error ? (
        <p id={ids.error} role="alert" className="mt-3 text-sm text-fg-danger">
          {error}
        </p>
      ) : null}
    </section>
  );
}

function CheckAmount({ org, people }: { org: string; people: Member[] }) {
  const fm = useFormatMessage();
  const locale = useLocale() as AppLocale;
  const ids = { type: useId(), person: useId(), amount: useId() };
  const [type, setType] = useState<DocType>("bill");
  const [person, setPerson] = useState("");
  const [amount, setAmount] = useState<string | null>(null);
  const [result, setResult] = useState<{ tone: "ok" | "no"; text: string } | null>(null);

  const check = async () => {
    if (!person || amount === null) {
      setResult({ tone: "no", text: fm(!person ? lm.whoRequired : lm.amountInvalid) });
      return;
    }
    const query = new URLSearchParams({ doc_type: type, amount, user: person });
    const answer = await apiRequest<CheckResult | ApiError>(
      `${orgApi(org, "approval-limits/check")}?${query.toString()}`,
    );
    if (!isOk<CheckResult>(answer)) {
      setResult({ tone: "no", text: errorText(answer.body) ?? fm(m.failed) });
      return;
    }
    const name = people.find((p) => p.id === person)?.name ?? "";
    setResult(
      answer.body.allowed
        ? {
            tone: "ok",
            text: fm(lm.allowed, {
              name,
              limit: formatMoney(answer.body.limit ?? "0", { locale }),
            }),
          }
        : { tone: "no", text: answer.body.detail ?? fm(m.failed) },
    );
  };

  return (
    <section aria-labelledby={ids.type + "-h"} className="rounded-lg border border-border p-4">
      <h3 id={ids.type + "-h"} className="text-base font-semibold">
        {fm(lm.checkHeading)}
      </h3>
      <p className="mt-1 text-sm text-fg-muted">{fm(lm.checkHelp)}</p>
      <form
        noValidate
        className="mt-3 grid gap-4 md:grid-cols-[1fr_1fr_12rem_auto] md:items-end"
        onSubmit={(event) => {
          event.preventDefault();
          void check();
        }}
      >
        <div className="flex flex-col gap-1.5">
          <span id={ids.type} className="text-sm font-semibold">
            {fm(lm.type)}
          </span>
          <Select
            aria-labelledby={ids.type}
            value={type}
            onValueChange={(value) => setType(value as DocType)}
            options={DOC_TYPES.map((t) => ({ value: t, label: fm(lm.docType, { type: t }) }))}
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <span id={ids.person} className="text-sm font-semibold">
            {fm(lm.person)}
          </span>
          <Select
            aria-labelledby={ids.person}
            value={person}
            placeholder={fm(lm.personPlaceholder)}
            onValueChange={setPerson}
            options={people.map((p) => ({ value: p.id, label: p.name }))}
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <label htmlFor={ids.amount} className="text-sm font-semibold">
            {fm(lm.amount)}
          </label>
          <CurrencyInput
            id={ids.amount}
            value={amount}
            onChange={setAmount}
            locale={locale}
            unreadableMessage={fm(lm.amountInvalid)}
          />
        </div>
        <Button type="submit" variant="secondary">
          {fm(lm.checkButton)}
        </Button>
      </form>
      {result ? (
        <p
          role="status"
          className={`mt-3 rounded-md border-2 px-4 py-3 text-sm ${
            result.tone === "ok"
              ? "border-border bg-surface-success-subtle"
              : "border-border-danger bg-surface-danger-subtle"
          }`}
        >
          {result.text}
        </p>
      ) : null}
    </section>
  );
}
