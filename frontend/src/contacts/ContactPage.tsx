"use client";

/** A contact's page: Details (B-01-T15 form), Activity (B-02-T10), Statements (B-02-T11) and, for
 * suppliers, Supplier statements reconciliation (B-02-T12). */
import { Tabs } from "@numo9/ui";
import { useState } from "react";

import { useFormatMessage } from "@/i18n";

import { ActivityTab } from "./ActivityTab";
import { ContactForm } from "./ContactForm";
import { ReconciliationTab } from "./ReconciliationTab";
import { StatementsTab } from "./StatementsTab";
import { tm } from "./tabMessages";

export function ContactPage({ org, id }: { org: string; id: string }) {
  const fm = useFormatMessage();
  const [tab, setTab] = useState("details");
  return (
    <Tabs
      label={fm(tm.tabs)}
      value={tab}
      onValueChange={setTab}
      items={[
        {
          value: "details",
          label: fm(tm.details),
          content: tab === "details" ? <ContactForm org={org} id={id} /> : null,
        },
        {
          value: "activity",
          label: fm(tm.activity),
          content: tab === "activity" ? <ActivityTab org={org} id={id} /> : null,
        },
        {
          value: "statements",
          label: fm(tm.statements),
          content: tab === "statements" ? <StatementsTab org={org} id={id} /> : null,
        },
        {
          value: "reconciliation",
          label: fm(tm.reconciliation),
          content: tab === "reconciliation" ? <ReconciliationTab org={org} id={id} /> : null,
        },
      ]}
    />
  );
}
