import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";

import { expectNoAxeViolations } from "../test/axe";
import { DueDateField } from "./DueDateField";
import { daysBetween, dueDate } from "./dueDates";
import { dueDateLabels, sampleTerms } from "./fixtures";

function Form({ initial = null }: { initial?: string | null }) {
  const [due, setDue] = useState<string | null>(initial);
  const [term, setTerm] = useState<string | null>(null);
  const [tried, setTried] = useState(false);
  const [saved, setSaved] = useState(false);
  return (
    <form
      noValidate
      onSubmit={(event) => {
        event.preventDefault();
        setTried(true);
        setSaved(Boolean(due));
      }}
    >
      <DueDateField
        value={due}
        onChange={(value, chosen) => {
          setDue(value);
          setTerm(chosen?.id ?? null);
        }}
        termId={term}
        documentDate="2026-07-15"
        terms={sampleTerms}
        today="2026-07-15"
        locale="en-CA"
        labels={dueDateLabels}
        showRequired={tried}
      />
      <button type="submit">Save</button>
      <output data-testid="saved">{saved ? `saved ${due}` : "not saved"}</output>
    </form>
  );
}

describe("dueDate mirror (D-01-T17)", () => {
  it.each([
    ["2026-07-15", "days_after_document", 30, "2026-08-14"],
    ["2026-01-31", "days_after_document", 30, "2026-03-02"],
    ["2026-02-03", "days_after_month_end", 0, "2026-02-28"],
    ["2028-02-03", "days_after_month_end", 0, "2028-02-29"],
    ["2026-12-01", "days_after_month_end", 1, "2027-01-01"],
    ["2026-01-15", "day_of_following_month", 31, "2026-02-28"],
    ["2026-12-15", "day_of_following_month", 5, "2027-01-05"],
    ["2026-07-25", "day_of_current_month", 20, "2026-08-20"],
    ["2026-04-10", "day_of_current_month", 31, "2026-04-30"],
  ] as const)("%s %s %i → %s (same as the server)", (date, type, days, due) => {
    expect(dueDate(date, type, days)).toBe(due);
  });

  it("counts days across months and years", () => {
    expect(daysBetween("2026-01-31", "2026-03-02")).toBe(30);
    expect(daysBetween("2026-12-15", "2027-01-14")).toBe(30);
    expect(daysBetween("2026-07-15", "2026-07-12")).toBe(-3);
  });
});

describe("DueDateField (D-01-T17)", () => {
  it("can't be saved without a due date", async () => {
    const user = userEvent.setup();
    render(<Form />);
    await user.click(screen.getByRole("button", { name: "Save" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Enter a due date.");
    expect(screen.getByTestId("saved")).toHaveTextContent("not saved");
  });

  it("term chips set the date and say when it's due", async () => {
    const user = userEvent.setup();
    render(<Form />);
    await user.click(screen.getByRole("button", { name: "Net 30" }));
    expect(screen.getByRole("textbox", { name: "Due date" })).toHaveValue("14 Aug 2026");
    expect(screen.getByRole("button", { name: "Net 30" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByText("Due in 30 days")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "EOM" }));
    expect(screen.getByText("Due in 16 days")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Due on receipt" }));
    expect(screen.getByText("Due on the invoice date")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Save" }));
    expect(screen.getByTestId("saved")).toHaveTextContent("saved 2026-07-15");
  });

  it("flags a due date before the document date", () => {
    render(<Form initial="2026-07-01" />);
    expect(screen.getByRole("alert")).toHaveTextContent("before the invoice date");
  });

  it("is axe-clean", async () => {
    const { container } = render(<Form initial="2026-08-14" />);
    await expectNoAxeViolations(container);
  });
});
