"use client";

/**
 * The builder page's client part (F-04-T11): loads the saved rule for `/banking/rules/<id>`, or
 * starts a new one for `/banking/rules/new?type=…`.
 */
import { ErrorState, Skeleton } from "@numo9/ui";
import { useEffect, useState } from "react";

import { useFormatMessage } from "@/i18n";

import { rulesApi, type BankRule, type RuleType } from "./api";
import { builder } from "./builderMessages";
import { newDraft, type RuleDraft } from "./draft";
import { m } from "./messages";
import { RuleBuilder } from "./RuleBuilder";

export interface RuleEditorProps {
  org: string;
  id?: string;
  type?: RuleType;
  initial?: RuleDraft;
}

export function RuleEditor({ org, id, type = "spend", initial }: RuleEditorProps) {
  const fm = useFormatMessage();
  const [rule, setRule] = useState<BankRule | null>(null);
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    if (!id) return;
    let cancelled = false;
    setFailed(false);
    void rulesApi
      .get(org, id)
      .then((result) => {
        if (cancelled) return;
        if (result.status === 200) setRule(result.body);
        else setFailed(true);
      })
      .catch(() => !cancelled && setFailed(true));
    return () => {
      cancelled = true;
    };
  }, [org, id, attempt]);

  if (!id) return <RuleBuilder org={org} initial={initial ?? newDraft(type)} />;
  if (failed) {
    return (
      <ErrorState
        title={fm(builder.loadFailed)}
        retryLabel={fm(m.retry)}
        onRetry={() => setAttempt((n) => n + 1)}
        headingLevel={2}
      />
    );
  }
  if (!rule) return <Skeleton className="h-64" />;
  return <RuleBuilder org={org} rule={rule} />;
}
