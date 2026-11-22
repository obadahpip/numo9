import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";

import { expectNoAxeViolations } from "../test/axe";
import { DocumentTotals, type DocumentDiscountType } from "./DocumentTotals";
import { sampleTotals, totalsLabels } from "./fixtures";

function Panel() {
  const [discount, setDiscount] = useState<[DocumentDiscountType, string]>(["none", ""]);
  return (
    <>
      <DocumentTotals
        value={sampleTotals}
        discountType={discount[0]}
        discountValue={discount[1]}
        onDiscountChange={(type, value) => setDiscount([type, value])}
        labels={totalsLabels}
        locale="en-CA"
      />
      <output data-testid="discount">{discount.join("|")}</output>
    </>
  );
}

describe("DocumentTotals (D-01-T14)", () => {
  it("shows subtotal, tax per component and total, and announces the total", () => {
    render(<Panel />);
    const panel = screen.getByRole("region", { name: "Totals" });
    expect(panel).toHaveTextContent("Subtotal$5,080.80");
    expect(panel).toHaveTextContent("HST (ON) 13 %$660.50");
    expect(panel).toHaveTextContent("Total$5,741.30");
    expect(within(panel).getByRole("status")).toHaveTextContent("Total $5,741.30");
  });

  it("edits the document discount as an amount or a percent", async () => {
    const user = userEvent.setup();
    render(<Panel />);
    expect(screen.queryByRole("textbox", { name: "Discount value" })).toBeNull();
    await user.selectOptions(screen.getByRole("combobox", { name: "Discount type" }), "percent");
    await user.type(screen.getByRole("textbox", { name: "Discount value" }), "10");
    expect(screen.getByTestId("discount")).toHaveTextContent("percent|10");
  });

  it("inclusive documents say the tax is included", () => {
    render(
      <DocumentTotals
        value={{ ...sampleTotals, total: "113.00", taxIncluded: true }}
        discountType="none"
        discountValue=""
        labels={totalsLabels}
        locale="en-CA"
        pending
      />,
    );
    expect(screen.getByText("Includes HST (ON) 13 % $660.50")).toBeInTheDocument();
    expect(screen.getByText("Updating…")).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Totals" })).toHaveAttribute("aria-busy", "true");
  });

  it("is axe-clean", async () => {
    const { container } = render(<Panel />);
    await expectNoAxeViolations(container);
  });
});
