"use client";

import { OrgSwitcher as Switcher, type ShellLinkComponent, type SwitcherOrg } from "@numo9/ui";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

import { defineMessages, formatMessage } from "@/i18n";
import {
  actingPractice,
  directoryPractice,
  loadMyOrganisations,
  type MyOrganisation,
} from "@/org/myOrganisations";
import { rememberOrg, writeCurrentOrgCookie } from "@/org/recentOrgs";
import { equivalentOrgUrl, practiceDirectoryUrl } from "@/routing/routes";

const messages = defineMessages({
  button: {
    id: "orgSwitcher.button",
    defaultMessage: "Switch organisation",
    description: "Screen-reader prefix of the org switcher button; the organisation name follows",
  },
  panel: {
    id: "orgSwitcher.panel",
    defaultMessage: "Organisations",
    description: "Accessible name of the org switcher panel",
  },
  search: {
    id: "orgSwitcher.search",
    defaultMessage: "Search organisations",
    description: "Label of the search box in the org switcher",
  },
  recent: {
    id: "orgSwitcher.recent",
    defaultMessage: "Recent",
    description: "Heading of the list of the 5 organisations opened most recently",
  },
  results: {
    id: "orgSwitcher.results",
    defaultMessage: "Results",
    description: "Heading of the search results in the org switcher",
  },
  noResults: {
    id: "orgSwitcher.noResults",
    defaultMessage: "No organisations match. Try another spelling, or open the directory.",
    description: "Org switcher search found nothing",
  },
  loading: {
    id: "orgSwitcher.loading",
    defaultMessage: "Loading organisations…",
    description: "Org switcher while the organisation list loads",
  },
  error: {
    id: "orgSwitcher.error",
    defaultMessage:
      "Your organisations couldn't be loaded. Make sure you're online, then try again.",
    description: "Org switcher when the organisation list request failed",
  },
  retry: {
    id: "orgSwitcher.retry",
    defaultMessage: "Try again",
    description: "Button: reload the organisation list",
  },
  openDirectory: {
    id: "orgSwitcher.openDirectory",
    defaultMessage: "Open directory",
    description: "Link at the bottom of the org switcher to the practice directory",
  },
  current: {
    id: "orgSwitcher.current",
    defaultMessage: "Current",
    description: "Marks the organisation that is open now in the org switcher list",
  },
  moreResults: {
    id: "orgSwitcher.moreResults",
    defaultMessage: "Showing {shown} of {total}. Refine your search or open the directory.",
    description: "Org switcher: results are capped; shown and total are numbers",
  },
  practiceBadge: {
    id: "orgSwitcher.practiceBadge",
    defaultMessage: "via {practice}",
    description:
      "Practice badge next to the organisation name: the accountant's practice giving access, e.g. 'via Profitex'",
  },
});

type Status = "loading" | "ready" | "error";

function toSwitcherOrg(org: MyOrganisation): SwitcherOrg {
  const practice = actingPractice(org);
  return {
    id: org.id,
    name: org.name,
    badge: practice
      ? formatMessage(messages.practiceBadge, { practice: practice.practice_name })
      : undefined,
  };
}

interface OrgSwitcherProps {
  /** Active organisation (the `/o/:org` URL segment: the organisation's public id). */
  org: string;
  /** Current module path, kept when switching (`contacts` → `/o/<other>/contacts`). */
  modulePath?: string;
  linkComponent?: ShellLinkComponent;
}

/**
 * The org switcher wired to the API (A-01-T14): loads the user's organisations, records the open
 * organisation as recent (and in the current-organisation cookie) and switches to the equivalent
 * page of the chosen organisation.
 */
export function OrgSwitcher({ org, modulePath, linkComponent }: Readonly<OrgSwitcherProps>) {
  const router = useRouter();
  const [organisations, setOrganisations] = useState<MyOrganisation[]>([]);
  const [status, setStatus] = useState<Status>("loading");
  const [recentIds, setRecentIds] = useState<string[]>([]);

  const load = useCallback(() => {
    let cancelled = false;
    setStatus("loading");
    loadMyOrganisations().then(
      (list) => {
        if (cancelled) return;
        setOrganisations(list);
        setStatus("ready");
      },
      () => {
        if (!cancelled) setStatus("error");
      },
    );
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => load(), [load]);

  useEffect(() => {
    setRecentIds(rememberOrg(org));
    writeCurrentOrgCookie(org);
  }, [org]);

  const switcherOrgs = useMemo(() => organisations.map(toSwitcherOrg), [organisations]);
  const activeOrg = organisations.find((entry) => entry.id === org);
  const active: SwitcherOrg = activeOrg ? toSwitcherOrg(activeOrg) : { id: org, name: org };
  const practice =
    (activeOrg && actingPractice(activeOrg)?.practice_id) ?? directoryPractice(organisations);

  return (
    <Switcher
      labels={{
        button: formatMessage(messages.button),
        panel: formatMessage(messages.panel),
        search: formatMessage(messages.search),
        recent: formatMessage(messages.recent),
        results: formatMessage(messages.results),
        noResults: formatMessage(messages.noResults),
        loading: formatMessage(messages.loading),
        error: formatMessage(messages.error),
        retry: formatMessage(messages.retry),
        openDirectory: formatMessage(messages.openDirectory),
        current: formatMessage(messages.current),
        moreResults: (shown, total) => formatMessage(messages.moreResults, { shown, total }),
      }}
      active={active}
      organisations={switcherOrgs}
      status={status}
      recentIds={recentIds}
      hrefFor={(target) => equivalentOrgUrl(target.id, modulePath)}
      onNavigate={(href) => router.push(href)}
      onRetry={load}
      directoryHref={practice ? practiceDirectoryUrl(practice) : undefined}
      linkComponent={linkComponent}
    />
  );
}
