"use client";

import { Badge, Button, Dialog, ErrorState, Input, LoadingRegion, SkeletonText } from "@numo9/ui";
import { useCallback, useEffect, useId, useState } from "react";

import { defineMessages, useFormatMessage } from "@/i18n";

import {
  addDomain,
  checkDomain,
  listDomains,
  removeDomain,
  type DnsRecord,
  type SendingDomain,
} from "./api";

/** While a domain is not verified, the page checks its records again this often. */
export const LIVE_CHECK_MS = 20_000;

const m = defineMessages({
  title: { id: "emailDomain.title", defaultMessage: "Email domain", description: "Page heading" },
  intro: {
    id: "emailDomain.intro",
    defaultMessage:
      "Send invoices, statements and reminders from your own address, e.g. billing@yourcompany.ca. Until your domain is verified, emails go from Numo9 with replies to your organisation's email address.",
    description: "Text under the heading",
  },
  domain: { id: "emailDomain.domain", defaultMessage: "Your domain", description: "Field" },
  domainHint: {
    id: "emailDomain.domainHint",
    defaultMessage: "The part after @ in your email address, e.g. refined.ca",
    description: "Field hint",
  },
  localPart: {
    id: "emailDomain.localPart",
    defaultMessage: "Send as",
    description: "Field: the part before @ of the sender address",
  },
  add: { id: "emailDomain.add", defaultMessage: "Set up domain", description: "Button" },
  sender: {
    id: "emailDomain.sender",
    defaultMessage: "Emails will come from {address}",
    description: "Sender address of a domain",
  },
  recordsIntro: {
    id: "emailDomain.recordsIntro",
    defaultMessage:
      "Add these {count} records at your DNS host — where you bought the domain or manage its DNS (e.g. GoDaddy, Cloudflare, Namecheap). Numo9 checks them every few minutes; changes can take up to an hour to show.",
    description: "Text above the DNS record cards",
  },
  typeIs: {
    id: "emailDomain.typeIs",
    defaultMessage: "Type: {type}",
    description: "DNS record type (TXT, CNAME)",
  },
  host: { id: "emailDomain.host", defaultMessage: "Host / name", description: "DNS record field" },
  value: { id: "emailDomain.value", defaultMessage: "Value", description: "DNS record field" },
  copy: { id: "emailDomain.copy", defaultMessage: "Copy", description: "Copy button" },
  copyWhat: {
    id: "emailDomain.copyWhat",
    defaultMessage: "Copy the {field} of the {record} record",
    description: "Accessible name of a copy button",
  },
  copied: { id: "emailDomain.copied", defaultMessage: "Copied", description: "After copying" },
  ok: { id: "emailDomain.ok", defaultMessage: "✓ Found and correct", description: "Record status" },
  missing: {
    id: "emailDomain.missing",
    defaultMessage: "✗ Not found yet. Add this record at your DNS host.",
    description: "Record status with the fix",
  },
  wrong: {
    id: "emailDomain.wrong",
    defaultMessage:
      "✗ A record is there but isn't right. Replace its value with the one above. Found: {found}",
    description: "Record status with the fix",
  },
  unchecked: {
    id: "emailDomain.unchecked",
    defaultMessage: "Not checked yet",
    description: "Record status",
  },
  check: { id: "emailDomain.check", defaultMessage: "Verify now", description: "Button" },
  checking: {
    id: "emailDomain.checking",
    defaultMessage: "Checking your DNS…",
    description: "While a check runs",
  },
  lastChecked: {
    id: "emailDomain.lastChecked",
    defaultMessage: "Checked automatically every 20 seconds while this page is open.",
    description: "Live checker note",
  },
  verifiedNote: {
    id: "emailDomain.verifiedNote",
    defaultMessage: "Verified: your emails now go from {address}.",
    description: "Announced when the domain becomes verified",
  },
  remove: { id: "emailDomain.remove", defaultMessage: "Remove domain", description: "Button" },
  removeTitle: {
    id: "emailDomain.removeTitle",
    defaultMessage: "Remove {domain}?",
    description: "Confirmation title",
  },
  removeBody: {
    id: "emailDomain.removeBody",
    defaultMessage:
      "Emails will go from Numo9 again, with replies to your organisation's email address. You can set the domain up again later.",
    description: "Confirmation body",
  },
  cancel: { id: "emailDomain.cancel", defaultMessage: "Cancel", description: "Button" },
  close: { id: "emailDomain.close", defaultMessage: "Close", description: "Close button" },
  loading: {
    id: "emailDomain.loading",
    defaultMessage: "Loading the email domain…",
    description: "Loading state",
  },
  loadFailed: {
    id: "emailDomain.loadFailed",
    defaultMessage: "The email domain couldn't be loaded",
    description: "Error title",
  },
  loadFailedBody: {
    id: "emailDomain.loadFailedBody",
    defaultMessage: "Verify your connection, then try again.",
    description: "Error body",
  },
  retry: { id: "emailDomain.retry", defaultMessage: "Try again", description: "Retry" },
  addFailed: {
    id: "emailDomain.addFailed",
    defaultMessage: "The domain couldn't be set up. Try again.",
    description: "Generic add error",
  },
});

const TONES = {
  verified: "success",
  partial: "warning",
  failed: "danger",
  pending: "neutral",
} as const;

/**
 * Settings → Email domain (A-07-T10): set up the organisation's own sending domain, then one
 * copyable card per DNS record with its live status ✓/✗ and a plain-language fix. While the
 * domain is not verified the page checks again every 20 s (and on "Verify now"); the status flips
 * to Verified as soon as every record is right, and that is announced.
 */
export function EmailDomainScreen({ org }: Readonly<{ org: string }>) {
  const fm = useFormatMessage();
  const [domains, setDomains] = useState<SendingDomain[] | null>(null);
  const [failed, setFailed] = useState(false);

  const load = useCallback(async () => {
    setFailed(false);
    const answer = await listDomains(org);
    if (answer.status === 200 && Array.isArray(answer.body.results))
      setDomains(answer.body.results);
    else setFailed(true);
  }, [org]);

  useEffect(() => {
    void load();
  }, [load]);

  const replace = (next: SendingDomain) =>
    setDomains((current) => current?.map((d) => (d.id === next.id ? next : d)) ?? [next]);

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-col gap-2">
        <h1 className="text-2xl font-semibold">{fm(m.title)}</h1>
        <p className="max-w-3xl text-fg-muted">{fm(m.intro)}</p>
      </header>
      {failed ? (
        <ErrorState
          title={fm(m.loadFailed)}
          body={fm(m.loadFailedBody)}
          retryLabel={fm(m.retry)}
          onRetry={() => void load()}
        />
      ) : domains === null ? (
        <LoadingRegion label={fm(m.loading)}>
          <SkeletonText lines={6} />
        </LoadingRegion>
      ) : domains.length === 0 ? (
        <AddDomainForm org={org} onAdded={(d) => setDomains([d])} />
      ) : (
        domains.map((d) => (
          <DomainPanel
            key={d.id}
            org={org}
            domain={d}
            onChange={replace}
            onRemoved={() => setDomains((current) => current?.filter((x) => x.id !== d.id) ?? [])}
          />
        ))
      )}
    </div>
  );
}

function AddDomainForm({
  org,
  onAdded,
}: Readonly<{ org: string; onAdded: (domain: SendingDomain) => void }>) {
  const fm = useFormatMessage();
  const domainId = useId();
  const localId = useId();
  const [domain, setDomain] = useState("");
  const [local, setLocal] = useState("billing");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    setBusy(true);
    setError("");
    const answer = await addDomain(org, domain, local);
    setBusy(false);
    if (answer.status === 201 && "records" in answer.body) onAdded(answer.body as SendingDomain);
    else if ("detail" in answer.body && typeof answer.body.detail === "string")
      setError(answer.body.detail);
    else setError(fm(m.addFailed));
  };

  return (
    <form
      className="flex max-w-xl flex-col gap-4"
      onSubmit={(event) => {
        event.preventDefault();
        void submit();
      }}
    >
      <div className="flex flex-col gap-1">
        <label htmlFor={domainId} className="font-medium">
          {fm(m.domain)}
        </label>
        <Input
          id={domainId}
          value={domain}
          onChange={(e) => setDomain(e.target.value)}
          aria-describedby={`${domainId}-hint ${domainId}-error`}
          aria-invalid={error ? true : undefined}
          required
        />
        <span id={`${domainId}-hint`} className="text-sm text-fg-muted">
          {fm(m.domainHint)}
        </span>
        <span id={`${domainId}-error`} role="alert" className="text-sm text-fg-danger">
          {error}
        </span>
      </div>
      <div className="flex flex-col gap-1">
        <label htmlFor={localId} className="font-medium">
          {fm(m.localPart)}
        </label>
        <Input id={localId} value={local} onChange={(e) => setLocal(e.target.value)} />
      </div>
      <Button type="submit" variant="primary" loading={busy} className="self-start">
        {fm(m.add)}
      </Button>
    </form>
  );
}

function DomainPanel({
  org,
  domain,
  onChange,
  onRemoved,
}: Readonly<{
  org: string;
  domain: SendingDomain;
  onChange: (domain: SendingDomain) => void;
  onRemoved: () => void;
}>) {
  const fm = useFormatMessage();
  const [checking, setChecking] = useState(false);
  const [announce, setAnnounce] = useState("");
  const [confirm, setConfirm] = useState(false);
  const verified = domain.status === "verified";

  const check = useCallback(async () => {
    setChecking(true);
    const answer = await checkDomain(org, domain.id);
    setChecking(false);
    if (answer.status === 200 && "records" in answer.body) {
      if (answer.body.status === "verified" && domain.status !== "verified") {
        setAnnounce(fm(m.verifiedNote, { address: answer.body.from_address }));
      }
      onChange(answer.body);
    }
  }, [org, domain.id, domain.status, onChange, fm]);

  useEffect(() => {
    if (verified) return undefined;
    const timer = setInterval(() => void check(), LIVE_CHECK_MS);
    return () => clearInterval(timer);
  }, [verified, check]);

  const remove = async () => {
    const answer = await removeDomain(org, domain.id);
    if (answer.status === 204) onRemoved();
  };

  return (
    <section
      aria-labelledby={`domain-${domain.id}`}
      className="flex flex-col gap-4"
      data-domain={domain.domain}
    >
      <div className="flex flex-wrap items-center gap-3">
        <h2 id={`domain-${domain.id}`} className="text-xl font-semibold">
          {domain.domain}
        </h2>
        <Badge tone={TONES[domain.status]} dot data-domain-status={domain.status}>
          {domain.status_label}
        </Badge>
      </div>
      <p>{fm(m.sender, { address: domain.from_address })}</p>
      <p
        role="status"
        aria-live="polite"
        className="font-medium text-fg-success"
        data-verified-live
      >
        {announce}
      </p>
      {verified ? null : (
        <p className="max-w-3xl text-fg-muted">
          {fm(m.recordsIntro, { count: domain.records.length })}
        </p>
      )}
      <ul className="grid gap-4 lg:grid-cols-2">
        {domain.records.map((record) => (
          <RecordCard key={record.kind} record={record} />
        ))}
      </ul>
      <div className="flex flex-wrap items-center gap-3">
        <Button onClick={() => void check()} loading={checking}>
          {checking ? fm(m.checking) : fm(m.check)}
        </Button>
        {verified ? null : <span className="text-sm text-fg-muted">{fm(m.lastChecked)}</span>}
        <Dialog
          open={confirm}
          onOpenChange={setConfirm}
          title={fm(m.removeTitle, { domain: domain.domain })}
          description={fm(m.removeBody)}
          closeLabel={fm(m.close)}
          trigger={<Button variant="ghost">{fm(m.remove)}</Button>}
          footer={
            <>
              <Button onClick={() => setConfirm(false)}>{fm(m.cancel)}</Button>
              <Button variant="danger" onClick={() => void remove()}>
                {fm(m.remove)}
              </Button>
            </>
          }
        />
      </div>
    </section>
  );
}

function RecordCard({ record }: Readonly<{ record: DnsRecord }>) {
  const fm = useFormatMessage();
  const status =
    record.status === "ok"
      ? fm(m.ok)
      : record.status === "missing"
        ? fm(m.missing)
        : record.status === "wrong"
          ? fm(m.wrong, { found: record.found })
          : fm(m.unchecked);
  return (
    <li
      className="flex flex-col gap-3 rounded-lg border border-border bg-surface p-4"
      data-record={record.kind}
      data-record-status={record.status}
    >
      <div className="flex items-center justify-between gap-2">
        <h3 className="font-semibold">{record.kind_label}</h3>
        <span className="text-sm text-fg-muted">{fm(m.typeIs, { type: record.record_type })}</span>
      </div>
      <CopyRow label={fm(m.host)} record={record.kind_label} value={record.host} />
      <CopyRow label={fm(m.value)} record={record.kind_label} value={record.value} />
      <p
        className={
          record.status === "ok"
            ? "text-fg-success"
            : record.status === "unchecked"
              ? "text-fg-muted"
              : "text-fg-danger"
        }
      >
        {status}
      </p>
    </li>
  );
}

function CopyRow({
  label,
  record,
  value,
}: Readonly<{ label: string; record: string; value: string }>) {
  const fm = useFormatMessage();
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopied(false);
    }
  };
  return (
    <div className="flex flex-col gap-1">
      <span className="text-xs font-semibold tracking-wide text-fg-muted uppercase">{label}</span>
      <div className="flex items-start gap-2">
        <code className="min-w-0 flex-1 rounded bg-surface-muted px-2 py-1 text-sm break-all">
          {value}
        </code>
        <Button
          size="sm"
          onClick={() => void copy()}
          aria-label={fm(m.copyWhat, { field: label.toLowerCase(), record })}
        >
          {copied ? fm(m.copied) : fm(m.copy)}
        </Button>
      </div>
    </div>
  );
}
