import { screen, within } from "@testing-library/react";

import { renderWithIntl } from "@/test/intl";

import { expectNoAxeViolations } from "../../../../packages/ui/src/test/axe";
import { CatalogueNav } from "./CatalogueNav";

/**
 * U-06-T07 — package editor integration: the U-02 screens are reached from the console's
 * "Packages and prices" area, with a sub-navigation between packages, products and promo codes.
 */
it("links the reused catalogue screens and marks the current one", async () => {
  const { container } = renderWithIntl(<CatalogueNav current="/console/products" />);
  const nav = screen.getByRole("navigation", { name: "Catalogue" });
  const links = within(nav).getAllByRole("link");
  expect(links.map((link) => link.getAttribute("href"))).toEqual([
    "/console/packages",
    "/console/products",
    "/console/promo-codes",
  ]);
  expect(within(nav).getByRole("link", { name: "Products" })).toHaveAttribute(
    "aria-current",
    "page",
  );
  expect(within(nav).getByRole("link", { name: "Packages" })).not.toHaveAttribute("aria-current");
  await expectNoAxeViolations(container);
});
