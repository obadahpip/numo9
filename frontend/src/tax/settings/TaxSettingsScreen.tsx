"use client";

/**
 * Tax registrations and settings — the one page (G-06-T08, wireframes 52 and 53): an anchor nav
 * and one card per group, each read first and edited in place: business number and
 * registrations (with each registration's filing summary and its timeline link), tax basis
 * (a change needs a reason and warns during the year), default codes per side and account type
 * with the rounding mode, the quick-method election, and the restricted-ITC accounts. The
 * History button opens the one history of every tax object. No other page edits these.
 */
import {
  Button,
  EmptyState,
  ErrorState,
  Input,
  RadioGroup,
  Select,
  SkeletonText,
  Switch,
} from "@numo9/ui";
import { useCallback, useEffect, useId, useState, type ReactNode } from "react";

import { accountsApi, type Account } from "@/accounts/api";
import { useFormatMessage, type MessageDescriptor } from "@/i18n";
import { RegistrationsScreen } from "@/settings/general/RegistrationsScreen";

import { taxApi, type TaxCode } from "../api";
import {
  DEFAULT_TYPES,
  firstError,
  taxSettingsApi,
  type BasisCheck,
  type SettingsChange,
  type Side,
  type TaxBasis,
  type TaxSettings,
} from "./api";
import { ANCHORS, type Anchor } from "./links";
import { sm } from "./messages";
import { TaxHistory } from "./TaxHistory";

const NAV: Record<Anchor, MessageDescriptor> = {
  registrations: sm.navRegistrations,
  "tax-basis": sm.navBasis,
  "default-codes": sm.navDefaults,
  "quick-method": sm.navQuick,
  "restricted-itc": sm.navItc,
};
const NONE = "__none__";
const SIDES: Side[] = ["sales", "purchase"];

interface CardProps {
  anchor: Anchor;
  title: string;
  help: string;
  editing: boolean;
  onEdit?: () => void;
  editLabel: string;
  children: ReactNode;
}

function Card({ anchor, title, help, editing, onEdit, editLabel, children }: Readonly<CardProps>) {
  const fm = useFormatMessage();
  return (
    <section
      id={anchor}
      aria-labelledby={`${anchor}-title`}
      data-card={anchor}
      data-editing={editing ? "" : undefined}
      className="scroll-mt-20 rounded-lg border border-border p-4"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="max-w-3xl">
          <h2 id={`${anchor}-title`} className="text-lg font-semibold text-fg">
            {title}
          </h2>
          <p className="text-sm text-fg-muted">{help}</p>
        </div>
        {onEdit && !editing ? (
          <Button size="sm" variant="secondary" onClick={onEdit} aria-label={editLabel}>
            {fm(sm.edit)}
          </Button>
        ) : null}
      </div>
      <div className="mt-3 flex flex-col gap-3 text-sm text-fg">{children}</div>
    </section>
  );
}

export interface TaxSettingsScreenProps {
  org: string;
  /** Whether the person may change tax settings (tax.manage). */
  canManage?: boolean;
}

export function TaxSettingsScreen({ org, canManage = false }: Readonly<TaxSettingsScreenProps>) {
  const fm = useFormatMessage();
  const ids = useId();
  const [settings, setSettings] = useState<TaxSettings | null>(null);
  const [failed, setFailed] = useState(false);
  const [editing, setEditing] = useState<Anchor | null>(null);
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  // drafts
  const [basis, setBasis] = useState<TaxBasis>("accrual");
  const [reason, setReason] = useState("");
  const [check, setCheck] = useState<BasisCheck | null>(null);
  const [codes, setCodes] = useState<TaxSettings["default_codes"]>({});
  const [rounding, setRounding] = useState<TaxSettings["rounding_mode"]>("line");
  const [afterStop, setAfterStop] = useState(true);
  const [quick, setQuick] = useState(false);
  const [quickFrom, setQuickFrom] = useState("");
  const [options, setOptions] = useState<Record<Side, TaxCode[]>>({ sales: [], purchase: [] });
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [pick, setPick] = useState("");
  const [pct, setPct] = useState<Record<string, string>>({});

  const load = useCallback(async () => {
    setFailed(false);
    const answer = await taxSettingsApi.get(org);
    if (answer.status === 200 && answer.body) setSettings(answer.body);
    else setFailed(true);
  }, [org]);
  useEffect(() => {
    void load();
  }, [load]);

  // A deep link lands on its card once the page has its content (G-06-T09).
  const ready = settings !== null;
  useEffect(() => {
    if (!ready) return;
    const anchor = window.location.hash.slice(1);
    if ((ANCHORS as readonly string[]).includes(anchor)) {
      document.getElementById(anchor)?.scrollIntoView();
    }
  }, [ready]);

  function begin(anchor: Anchor) {
    if (!settings) return;
    setError("");
    setStatus("");
    setEditing(anchor);
    if (anchor === "tax-basis") {
      setBasis(settings.basis);
      setReason("");
      setCheck(null);
    } else if (anchor === "default-codes") {
      setCodes(settings.default_codes);
      setRounding(settings.rounding_mode);
      setAfterStop(settings.out_of_scope_after_stop);
      for (const side of SIDES) {
        void taxApi.codes(org, { side }).then((answer) => {
          if (answer.status === 200 && Array.isArray(answer.body?.results)) {
            setOptions((current) => ({ ...current, [side]: answer.body.results }));
          }
        });
      }
    } else if (anchor === "quick-method") {
      setQuick(settings.quick_method);
      setQuickFrom(settings.quick_method_from ?? "");
    } else if (anchor === "restricted-itc") {
      setPct(Object.fromEntries(settings.restricted_itc_accounts.map((a) => [a.id, a.pct])));
      setPick("");
      void accountsApi.list(org, "active").then((answer) => {
        if (answer.status === 200 && Array.isArray(answer.body?.results)) {
          setAccounts(answer.body.results.filter((a) => a.type === "expense"));
        }
      });
    }
  }

  async function save(card: string, change: SettingsChange) {
    setBusy(true);
    setError("");
    const answer = await taxSettingsApi.save(org, change);
    setBusy(false);
    if (answer.status === 200) {
      const body = answer.body as TaxSettings;
      setSettings(body);
      setEditing(null);
      setStatus(body.basis_warning || fm(sm.saved, { card }));
    } else setError(firstError(answer.body) ?? fm(sm.failed));
  }

  async function chooseBasis(value: TaxBasis) {
    setBasis(value);
    setCheck(null);
    if (settings && value !== settings.basis) {
      const answer = await taxSettingsApi.basisCheck(org, value);
      if (answer.status === 200) setCheck(answer.body);
    }
  }

  async function restrict(account: string, value: string | null) {
    setBusy(true);
    setError("");
    const answer = await taxSettingsApi.restrictItc(org, account, value);
    setBusy(false);
    if (answer.status === 200 && settings && "restricted_itc_accounts" in answer.body) {
      const list = answer.body.restricted_itc_accounts as TaxSettings["restricted_itc_accounts"];
      setSettings({ ...settings, restricted_itc_accounts: list });
      setPct(Object.fromEntries(list.map((a) => [a.id, a.pct])));
      setPick("");
      setStatus(fm(sm.saved, { card: fm(sm.itcTitle) }));
    } else setError(firstError(answer.body) ?? fm(sm.failed));
  }

  // The heading is always there: while loading and when the settings can't be read too.
  const header = (
    <header className="flex flex-wrap items-start justify-between gap-3">
      <div className="max-w-3xl">
        <h1 className="text-2xl font-semibold">{fm(sm.title)}</h1>
        <p className="text-fg-muted">{fm(sm.intro)}</p>
      </div>
      <TaxHistory org={org} />
    </header>
  );
  if (failed || !settings) {
    return (
      <div className="flex flex-col gap-6" data-tax-settings="">
        {header}
        {failed ? (
          <ErrorState
            title={fm(sm.loadFailed)}
            retryLabel={fm(sm.retry)}
            onRetry={() => void load()}
          />
        ) : (
          <SkeletonText lines={6} />
        )}
      </div>
    );
  }

  const actions = (onSave: () => void, disabled = false) => (
    <div className="flex gap-2">
      <Button size="sm" variant="primary" loading={busy} disabled={disabled} onClick={onSave}>
        {fm(sm.save)}
      </Button>
      <Button size="sm" variant="ghost" onClick={() => setEditing(null)}>
        {fm(sm.cancel)}
      </Button>
    </div>
  );
  const problem = (anchor: Anchor) =>
    editing === anchor && error ? (
      <p role="alert" className="text-fg-danger">
        {error}
      </p>
    ) : null;
  const can = (anchor: Anchor) => (canManage ? () => begin(anchor) : undefined);
  const codeName = (side: Side, type: string) => settings.default_codes[side]?.[type] ?? "";
  const restricted = new Set(settings.restricted_itc_accounts.map((a) => a.id));

  return (
    <div className="flex flex-col gap-6" data-tax-settings="">
      {header}
      <nav aria-label={fm(sm.nav)}>
        <ul className="flex flex-wrap gap-x-4 gap-y-1 text-sm">
          {ANCHORS.map((anchor) => (
            <li key={anchor}>
              <a href={`#${anchor}`} className="text-fg underline">
                {fm(NAV[anchor])}
              </a>
            </li>
          ))}
        </ul>
      </nav>
      <p role="status" aria-live="polite" className="text-sm text-fg-success" data-tax-status="">
        {status}
      </p>
      {settings.registered ? null : (
        <EmptyState title={fm(sm.notRegistered)} body={fm(sm.notRegisteredBody)} compact />
      )}
      <section id="registrations" data-card="registrations" className="scroll-mt-20">
        <RegistrationsScreen org={org} embedded onChanged={() => void load()} />
      </section>

      <Card
        anchor="tax-basis"
        title={fm(sm.basisTitle)}
        help={fm(sm.basisHelp)}
        editing={editing === "tax-basis"}
        onEdit={can("tax-basis")}
        editLabel={fm(sm.editCard, { card: fm(sm.basisTitle) })}
      >
        {editing === "tax-basis" ? (
          <>
            <RadioGroup
              aria-label={fm(sm.basisLabel)}
              value={basis}
              onValueChange={(value) => void chooseBasis(value as TaxBasis)}
              options={[
                { value: "accrual", label: fm(sm.basisAccrualHelp) },
                { value: "cash", label: fm(sm.basisCashHelp) },
              ]}
            />
            {check?.warning ? (
              <p role="status" data-basis-warning="" className="text-fg-warning">
                {check.warning}
              </p>
            ) : null}
            {basis !== settings.basis ? (
              <label htmlFor={`${ids}-reason`} className="flex flex-col gap-1 font-medium">
                {fm(sm.basisReason)}
                <Input
                  id={`${ids}-reason`}
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                />
              </label>
            ) : null}
            {problem("tax-basis")}
            {actions(() => void save(fm(sm.basisTitle), { basis, basis_reason: reason }))}
          </>
        ) : (
          <p data-value="basis">{fm(sm.basisValue, { basis: settings.basis })}</p>
        )}
      </Card>

      <Card
        anchor="default-codes"
        title={fm(sm.defaultsTitle)}
        help={fm(sm.defaultsHelp)}
        editing={editing === "default-codes"}
        onEdit={can("default-codes")}
        editLabel={fm(sm.editCard, { card: fm(sm.defaultsTitle) })}
      >
        <dl className="grid gap-x-6 gap-y-2 md:grid-cols-[minmax(0,18rem)_minmax(0,1fr)]">
          {SIDES.flatMap((side) =>
            DEFAULT_TYPES[side].map((type) => {
              const label = fm(sm.defaultFor, { side, type });
              const fieldId = `${ids}-${side}-${type}`;
              return (
                <div key={fieldId} className="contents" data-default={`${side}.${type}`}>
                  <dt>
                    {editing === "default-codes" ? <label htmlFor={fieldId}>{label}</label> : label}
                  </dt>
                  <dd>
                    {editing === "default-codes" ? (
                      <Select
                        id={fieldId}
                        value={codes[side]?.[type] || NONE}
                        onValueChange={(value) =>
                          setCodes((current) => {
                            const next = { ...(current[side] ?? {}) };
                            if (value === NONE) delete next[type];
                            else next[type] = value;
                            return { ...current, [side]: next };
                          })
                        }
                        options={[
                          { value: NONE, label: fm(sm.noDefault) },
                          ...options[side].map((code) => ({ value: code.code, label: code.name })),
                        ]}
                      />
                    ) : (
                      codeName(side, type) || fm(sm.noDefault)
                    )}
                  </dd>
                </div>
              );
            }),
          )}
          <div className="contents" data-default="rounding">
            <dt>
              {editing === "default-codes" ? (
                <label htmlFor={`${ids}-rounding`}>{fm(sm.rounding)}</label>
              ) : (
                fm(sm.rounding)
              )}
            </dt>
            <dd>
              {editing === "default-codes" ? (
                <Select
                  id={`${ids}-rounding`}
                  value={rounding}
                  onValueChange={(value) => setRounding(value as TaxSettings["rounding_mode"])}
                  options={(["line", "document"] as const).map((mode) => ({
                    value: mode,
                    label: fm(sm.roundingValue, { mode }),
                  }))}
                />
              ) : (
                fm(sm.roundingValue, { mode: settings.rounding_mode })
              )}
            </dd>
          </div>
          <div className="contents" data-default="after-stop">
            <dt>{fm(sm.afterStop)}</dt>
            <dd>
              {editing === "default-codes" ? (
                <Switch
                  checked={afterStop}
                  onCheckedChange={setAfterStop}
                  aria-label={fm(sm.afterStop)}
                />
              ) : (
                fm(sm.afterStopValue, { on: String(settings.out_of_scope_after_stop) })
              )}
            </dd>
          </div>
        </dl>
        {problem("default-codes")}
        {editing === "default-codes"
          ? actions(
              () =>
                void save(fm(sm.defaultsTitle), {
                  default_codes: codes,
                  rounding_mode: rounding,
                  out_of_scope_after_stop: afterStop,
                }),
            )
          : null}
      </Card>

      <Card
        anchor="quick-method"
        title={fm(sm.quickTitle)}
        help={fm(sm.quickHelp)}
        editing={editing === "quick-method"}
        onEdit={can("quick-method")}
        editLabel={fm(sm.editCard, { card: fm(sm.quickTitle) })}
      >
        {editing === "quick-method" ? (
          <>
            <label className="flex items-center gap-2 font-medium">
              <Switch checked={quick} onCheckedChange={setQuick} aria-label={fm(sm.quickSwitch)} />
              {fm(sm.quickSwitch)}
            </label>
            {quick ? (
              <label htmlFor={`${ids}-quick`} className="flex max-w-xs flex-col gap-1 font-medium">
                {fm(sm.quickFrom)}
                <Input
                  id={`${ids}-quick`}
                  type="date"
                  value={quickFrom}
                  onChange={(e) => setQuickFrom(e.target.value)}
                />
              </label>
            ) : null}
            {problem("quick-method")}
            {actions(
              () =>
                void save(fm(sm.quickTitle), {
                  quick_method: quick,
                  quick_method_from: quick ? quickFrom || null : null,
                }),
            )}
          </>
        ) : (
          <p data-value="quick">
            {settings.quick_method && settings.quick_method_from
              ? fm(sm.quickOn, { date: settings.quick_method_from })
              : fm(sm.quickOff)}
          </p>
        )}
      </Card>

      <Card
        anchor="restricted-itc"
        title={fm(sm.itcTitle)}
        help={fm(sm.itcHelp)}
        editing={editing === "restricted-itc"}
        onEdit={can("restricted-itc")}
        editLabel={fm(sm.editCard, { card: fm(sm.itcTitle) })}
      >
        {settings.restricted_itc_accounts.length === 0 ? (
          <p className="text-fg-muted">{fm(sm.itcNone)}</p>
        ) : (
          <table aria-label={fm(sm.itcTable)} className="w-full max-w-xl text-left">
            <thead className="text-xs text-fg-muted">
              <tr>
                <th scope="col" className="py-1 pr-3 font-medium">
                  {fm(sm.itcAccount)}
                </th>
                <th scope="col" className="py-1 pr-3 font-medium">
                  {fm(sm.itcPct)}
                </th>
                {editing === "restricted-itc" ? <td /> : null}
              </tr>
            </thead>
            <tbody>
              {settings.restricted_itc_accounts.map((account) => {
                const name = `${account.code} ${account.name}`;
                return (
                  <tr key={account.id} data-itc={account.code} className="border-t border-border">
                    <td className="py-1.5 pr-3">{name}</td>
                    <td className="py-1.5 pr-3">
                      {editing === "restricted-itc" ? (
                        <Input
                          className="w-24"
                          inputMode="decimal"
                          aria-label={fm(sm.itcPctOf, { account: name })}
                          value={pct[account.id] ?? account.pct}
                          onChange={(e) =>
                            setPct((current) => ({ ...current, [account.id]: e.target.value }))
                          }
                          onBlur={() => {
                            const value = pct[account.id];
                            if (value && value !== account.pct) void restrict(account.id, value);
                          }}
                        />
                      ) : (
                        account.pct
                      )}
                    </td>
                    {editing === "restricted-itc" ? (
                      <td className="py-1.5">
                        <Button
                          size="sm"
                          variant="ghost"
                          aria-label={fm(sm.itcLift, { account: name })}
                          onClick={() => void restrict(account.id, null)}
                        >
                          {fm(sm.itcLiftShort)}
                        </Button>
                      </td>
                    ) : null}
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
        {editing === "restricted-itc" ? (
          <>
            <div className="flex flex-wrap items-end gap-2">
              <label htmlFor={`${ids}-itc`} className="flex min-w-64 flex-col gap-1 font-medium">
                {fm(sm.itcAdd)}
                <Select
                  id={`${ids}-itc`}
                  value={pick}
                  onValueChange={setPick}
                  options={accounts
                    .filter((a) => !restricted.has(a.id))
                    .map((a) => ({ value: a.id, label: `${a.code} ${a.name}` }))}
                />
              </label>
              <Button
                size="sm"
                variant="secondary"
                disabled={!pick || busy}
                onClick={() => void restrict(pick, "50")}
              >
                {fm(sm.itcAddButton)}
              </Button>
            </div>
            {problem("restricted-itc")}
            <div>
              <Button size="sm" variant="ghost" onClick={() => setEditing(null)}>
                {fm(sm.cancel)}
              </Button>
            </div>
          </>
        ) : null}
      </Card>
    </div>
  );
}
