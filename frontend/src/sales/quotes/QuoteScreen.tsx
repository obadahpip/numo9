"use client";

/** The quote page (D-02-T12): the editor with its action bar. */
import { useRouter } from "next/navigation";

import { QuoteActionBar } from "./QuoteActionBar";
import { QuoteEditor } from "./QuoteEditor";

export function QuoteScreen({ org, id }: { org: string; id?: string }) {
  const router = useRouter();
  const navigate = (href: string) => router.replace(href);
  return (
    <QuoteEditor
      org={org}
      id={id}
      navigate={navigate}
      actions={(context) => <QuoteActionBar org={org} context={context} navigate={navigate} />}
    />
  );
}
