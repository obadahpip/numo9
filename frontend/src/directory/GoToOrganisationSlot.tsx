"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { useFormatMessage } from "@/i18n";
import { actingPractice, directoryPractice, loadMyOrganisations } from "@/org/myOrganisations";

import { GoToOrganisation } from "./GoToOrganisation";
import { m } from "./messages";

/**
 * Top bar search slot (V-01-T13): the "Go to organisation… Ctrl+K" button and its dialog, on
 * every page. The practice searched is the page's practice (`/p/:practice/…`), else the practice
 * the user acts through in the open organisation, else their first practice; a user with no
 * practice (an owner managing their own books) gets neither.
 */
export function GoToOrganisationSlot({ practice, org }: { practice?: string; org?: string }) {
  const t = useFormatMessage();
  const router = useRouter();
  const [found, setFound] = useState<string | undefined>(practice);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (practice) {
      setFound(practice);
      return;
    }
    let cancelled = false;
    loadMyOrganisations()
      .then((orgs) => {
        if (cancelled) return;
        const active = org ? orgs.find((item) => item.id === org) : undefined;
        setFound((active && actingPractice(active)?.practice_id) || directoryPractice(orgs));
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [practice, org]);

  if (!found) return null;
  return (
    <>
      <button
        type="button"
        aria-keyshortcuts="Control+K Meta+K"
        onClick={() => setOpen(true)}
        className="flex min-h-10 w-60 items-center rounded-md border border-border-inverse bg-surface-inverse-hover px-3 text-start text-sm text-fg-inverse-muted"
      >
        {t(m.gotoButton)}
        <kbd className="ms-auto font-sans text-xs">{t(m.gotoKeys)}</kbd>
      </button>
      <GoToOrganisation
        practice={found}
        open={open}
        onOpenChange={setOpen}
        navigate={(href) => router.push(href)}
      />
    </>
  );
}
