import { fireEvent, screen, within } from "@testing-library/react";
import { vi } from "vitest";

import {
  buildDestinations,
  NotFoundSearch,
  queryFromPath,
  searchDestinations,
} from "./NotFoundSearch";
import { renderWithIntl, testFormatMessage } from "@/test/intl";

const pathname = vi.hoisted(() => ({ value: "/" }));
vi.mock("next/navigation", () => ({ usePathname: () => pathname.value }));

describe("queryFromPath", () => {
  it.each([
    ["/o/acme/chart-acounts", "chart acounts"],
    ["/Journal/Serch.aspx", "serch"],
    ["/", ""],
    ["/o/acme", "acme"],
  ])("%s → %s", (path, query) => {
    expect(queryFromPath(path)).toBe(query);
  });
});

describe("searchDestinations", () => {
  const destinations = buildDestinations(testFormatMessage());
  const labels = (query: string) => searchDestinations(query, destinations).map((d) => d.label);

  it("lists every page for an empty query", () => {
    expect(labels("")).toContain("Home");
    expect(labels("").length).toBeGreaterThanOrEqual(14);
  });

  it("matches labels, aliases and typos", () => {
    expect(labels("chart")).toEqual(["Chart of accounts"]);
    expect(labels("acounts")).toContain("Chart of accounts");
    expect(labels("dashbord")).toEqual(["Home"]);
    expect(labels("lock")).toEqual(["Settings: Lock dates"]);
    expect(labels("billing")).toEqual(["Settings: Subscription"]);
  });

  it("returns nothing for unrelated words", () => {
    expect(labels("qqqq")).toEqual([]);
  });
});

describe("NotFoundSearch", () => {
  it("pre-fills the search from the broken URL and links to the page", () => {
    pathname.value = "/o/acme/jornals";
    renderWithIntl(<NotFoundSearch />);

    expect(screen.getByRole("searchbox", { name: "Search pages" })).toHaveValue("jornals");
    const list = screen.getByRole("list", { name: "Matching pages" });
    expect(within(list).getByRole("link", { name: "Journals" })).toHaveAttribute(
      "href",
      "/accounting/journals",
    );
  });

  it("filters as the user types and explains when nothing matches", () => {
    pathname.value = "/nowhere";
    renderWithIntl(<NotFoundSearch />);
    const box = screen.getByRole("searchbox", { name: "Search pages" });

    fireEvent.change(box, { target: { value: "contacts" } });
    expect(screen.getByRole("link", { name: "Contacts" })).toHaveAttribute("href", "/contacts");

    fireEvent.change(box, { target: { value: "qqqq" } });
    expect(screen.queryByRole("list")).not.toBeInTheDocument();
    expect(screen.getByText("No matching pages. Try another word.")).toBeInTheDocument();
  });
});
