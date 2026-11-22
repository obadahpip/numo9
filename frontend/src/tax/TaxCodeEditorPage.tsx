"use client";

/** Loads a tax code version and opens the editor (G-01-T13). */
import { ErrorState, SkeletonText } from "@numo9/ui";
import { useEffect, useState } from "react";

import { useFormatMessage } from "@/i18n";

import { taxApi, type TaxCode } from "./api";
import { m } from "./messages";
import { TaxCodeEditor } from "./TaxCodeEditor";

export function TaxCodeEditorPage({ org, id }: { org: string; id: string }) {
  const fm = useFormatMessage();
  const [code, setCode] = useState<TaxCode | null>(null);
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let cancelled = false;
    void taxApi.code(org, id).then((result) => {
      if (cancelled) return;
      if (result.status === 200) setCode(result.body);
      else setFailed(true);
    });
    return () => {
      cancelled = true;
    };
  }, [org, id, attempt]);
  if (failed) {
    return (
      <ErrorState
        title={fm(m.loadFailed)}
        body={fm(m.loadFailedBody)}
        retryLabel={fm(m.retry)}
        onRetry={() => {
          setFailed(false);
          setAttempt((n) => n + 1);
        }}
        headingLevel={2}
      />
    );
  }
  if (!code) return <SkeletonText lines={6} />;
  return <TaxCodeEditor org={org} code={code} onSaved={setCode} />;
}
