import { renderHook } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it } from "vitest";

import frCA from "../../messages/fr-CA.json";
import { pseudoCatalog } from "@/i18n/pseudo";
import { IntlWrapper, testMessages } from "@/test/intl";

import { useDocumentLinesLabels, useDocumentTotalsLabels, useDueDateLabels } from "./labels";

function wrap(locale: string, messages: Record<string, unknown>) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return (
      <IntlWrapper locale={locale} messages={messages}>
        {children}
      </IntlWrapper>
    );
  };
}

const DATE = {
  openCalendar: "",
  previousMonth: "",
  nextMonth: "",
  unreadable: "",
  shortcuts: { today: "", plus7: "", plus14: "", plus30: "", endOfMonth: "", endOfNextMonth: "" },
};

describe("document grid labels (D-01-T19)", () => {
  it("en-CA", () => {
    const { result } = renderHook(
      () => ({
        lines: useDocumentLinesLabels(),
        bill: useDocumentLinesLabels("purchase"),
        totals: useDocumentTotalsLabels(),
        due: useDueDateLabels(DATE),
      }),
      { wrapper: wrap("en-CA", testMessages) },
    );
    expect(result.current.lines.cell("Qty", 3)).toBe("Qty, line 3");
    expect(result.current.bill.unitPrice).toBe("Unit cost");
    expect(result.current.totals.includes("HST", "$13.00")).toBe("Includes HST $13.00");
    expect(result.current.due.dueIn(0)).toBe("Due on the document date");
    expect(result.current.due.dueIn(1)).toBe("Due in 1 day");
    expect(result.current.due.dueIn(30)).toBe("Due in 30 days");
  });

  it("fr-CA", () => {
    const { result } = renderHook(
      () => ({ lines: useDocumentLinesLabels(), due: useDueDateLabels(DATE) }),
      { wrapper: wrap("fr-CA", frCA) },
    );
    expect(result.current.lines.taxAmount).toBe("Montant de taxe");
    expect(result.current.lines.removeLine(2)).toBe("Supprimer la ligne 2");
    expect(result.current.lines.taxTypes.zero_rated).toBe("Détaxé");
    expect(result.current.due.dueIn(30)).toBe("Échéance dans 30 jours");
  });

  it("pseudo-locale keeps the arguments", () => {
    const { result } = renderHook(() => useDocumentLinesLabels(), {
      wrapper: wrap("en-CA", pseudoCatalog(testMessages)),
    });
    expect(result.current.cell("Qty", 3)).toMatch(/^\[Qty, ļîñé 3 ~+\]$/);
  });
});
