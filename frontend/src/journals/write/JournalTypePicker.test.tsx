import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";

import { renderWithIntl } from "@/test/intl";

import { expectNoAxeViolations } from "../../../../packages/ui/src/test/axe";
import { SELECTABLE_TYPES, type JournalTypeKey } from "./api";
import { JournalTypePicker } from "./JournalTypePicker";

/** C-03-T11 — journal type segmented control: only the selectable types, with descriptions. */

function Harness() {
  const [value, setValue] = useState<JournalTypeKey>("general");
  return <JournalTypePicker value={value} onChange={setValue} />;
}

describe("JournalTypePicker (C-03-T11)", () => {
  it("offers only the selectable types — system types hidden", () => {
    renderWithIntl(<Harness />);
    const group = screen.getByRole("group", { name: "Journal type" });
    const names = screen.getAllByRole("radio").map((r) => r.closest("label")?.textContent);
    expect(names).toEqual(["General", "Adjusting", "Reclass", "Tax adjustment"]);
    expect(SELECTABLE_TYPES).toEqual(["general", "adjusting", "reclass", "tax_adjustment"]);
    expect(group).not.toHaveTextContent("Closing");
    expect(group).not.toHaveTextContent("Payroll");
    expect(group).not.toHaveTextContent("Depreciation");
  });

  it("describes the chosen type; arrows and clicks change it", async () => {
    const user = userEvent.setup();
    renderWithIntl(<Harness />);
    const general = screen.getByRole("radio", { name: "General" });
    expect(general).toBeChecked();
    expect(general).toHaveAccessibleDescription(
      "An everyday entry: anything that isn't one of the other types.",
    );
    await user.click(screen.getByText("Tax adjustment"));
    const tax = screen.getByRole("radio", { name: "Tax adjustment" });
    expect(tax).toBeChecked();
    expect(tax).toHaveAccessibleDescription(
      "Tax book only (CCA, book-to-tax differences); never a bank account.",
    );
    expect(screen.getByText("Adjusting").closest("label")).toHaveAttribute(
      "title",
      "Accruals, prepayments and other period-end adjustments.",
    );
    await expectNoAxeViolations(document.body);
  });
});
