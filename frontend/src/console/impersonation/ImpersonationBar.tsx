"use client";

/**
 * The red impersonation bar (U-06-T11), on every page of the app shell: while the browser is in a
 * support session it names the user and organisation, counts down to the time limit and offers
 * "End session" (back to the organisation in the console). When the time is up it asks the API
 * (which ends the session) and says the session ended. Outside a session it renders nothing.
 */
import { Button } from "@numo9/ui";
import Link from "next/link";
import { useEffect, useState } from "react";

import { useFormatMessage } from "@/i18n";

import {
  consoleOrganisationUrl,
  currentImpersonation,
  endImpersonation,
  type ImpersonationSession,
} from "./api";
import { m } from "./messages";

/** `mm:ss`, or `h:mm:ss` over an hour. */
export function countdown(ms: number): string {
  const total = Math.max(0, Math.ceil(ms / 1000));
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const seconds = total % 60;
  const pad = (n: number) => String(n).padStart(2, "0");
  return hours ? `${hours}:${pad(minutes)}:${pad(seconds)}` : `${pad(minutes)}:${pad(seconds)}`;
}

export interface ImpersonationBarProps {
  /** Navigation after "End session" (tests inject it). */
  navigate?: (url: string) => void;
}

export function ImpersonationBar({ navigate }: ImpersonationBarProps) {
  const fm = useFormatMessage();
  const [session, setSession] = useState<ImpersonationSession | null>(null);
  const [ended, setEnded] = useState<ImpersonationSession | null>(null);
  const [now, setNow] = useState(() => Date.now());
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    void currentImpersonation().then((result) => {
      if (cancelled || result.status !== 200 || !result.body) return;
      setSession(result.body.session ?? null);
      setEnded(result.body.ended ?? null);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const expires = session ? Date.parse(session.expires_at) : 0;
  useEffect(() => {
    if (!session) return;
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [session]);

  useEffect(() => {
    if (!session || now < expires) return;
    // Time is up: the API ends the session on this request and says so.
    void currentImpersonation().then((result) => {
      setEnded(result.body?.ended ?? session);
      setSession(null);
    });
  }, [now, expires, session]);

  const go = navigate ?? ((url: string) => window.location.assign(url));

  if (session) {
    const end = async () => {
      setBusy(true);
      await endImpersonation();
      go(consoleOrganisationUrl(session.organisation.id));
    };
    return (
      <div
        role="region"
        aria-label={fm(m.barLabel)}
        data-impersonation-bar=""
        className="flex flex-wrap items-center gap-3 bg-[#B42318] px-4 py-2 text-sm font-semibold text-white"
      >
        <span>
          {fm(m.bar, { name: session.user.name, organisation: session.organisation.name })}
        </span>
        <span role="timer" aria-live="off" className="tabular-nums" data-countdown="">
          {fm(m.remaining, { time: countdown(expires - now) })}
        </span>
        <Button
          size="sm"
          variant="secondary"
          className="ms-auto"
          loading={busy}
          onClick={() => void end()}
        >
          {fm(m.end)}
        </Button>
      </div>
    );
  }
  if (ended) {
    return (
      <div
        role="status"
        data-impersonation-ended=""
        className="flex flex-wrap items-center gap-3 bg-[#B42318] px-4 py-2 text-sm font-semibold text-white"
      >
        <span>{fm(m.endedTitle, { name: ended.user.name })}</span>
        <Link href={consoleOrganisationUrl(ended.organisation.id)} className="ms-auto underline">
          {fm(m.backToConsole)}
        </Link>
      </div>
    );
  }
  return null;
}
