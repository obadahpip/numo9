import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { renderWithIntl } from "@/test/intl";

import { expectNoAxeViolations } from "../../../packages/ui/src/test/axe";
import type { Tag } from "./api";
import { TagsSection } from "./TagsSection";

/**
 * V-02-T10 — tag picker (type-to-create, colour + label). Acceptance: a new tag is created inline
 * — typing a name no tag has offers "Create tag “…” (colour)"; Enter creates it with the chosen
 * named colour (`POST /api/v1/practice/tags`) and it joins the list, shown with its name and its
 * colour's name. Existing tags are matched without accents or case; refusals are shown.
 */

const PRACTICE = "6ca1b880-64f7-4053-80e3-0c3618895553";
const QUEBEC: Tag = {
  id: "t1",
  name: "Québec clients",
  colour: "blue",
  colour_label: "Blue",
  organisation_count: 3,
};

function mockApi() {
  const posts: unknown[] = [];
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const url = new URL(String(input), "http://numo9.test");
    const json = (body: unknown, status = 200) =>
      new Response(JSON.stringify(body), {
        status,
        headers: { "Content-Type": "application/json" },
      });
    if (url.pathname.endsWith("/csrf")) return json({ csrfToken: "t" });
    if (url.pathname === "/api/v1/practice/tags" && init?.method === "POST") {
      const body = JSON.parse(String(init.body)) as { name: string; colour: string };
      posts.push(body);
      if (body.name === "Taken")
        return json({ detail: "There's already a tag called Taken.", code: "x" }, 400);
      return json(
        {
          id: "t2",
          name: body.name,
          colour: body.colour,
          colour_label: "Red",
          organisation_count: 0,
        },
        201,
      );
    }
    if (url.pathname === "/api/v1/practice/tags")
      return json({ practice: PRACTICE, tags: [QUEBEC] });
    return json({}, 404);
  });
  return posts;
}

afterEach(() => vi.restoreAllMocks());

it("creates a new tag inline with a named colour", async () => {
  const posts = mockApi();
  const user = userEvent.setup();
  const { container } = renderWithIntl(<TagsSection practice={PRACTICE} />);
  await screen.findByText("Québec clients");
  const box = screen.getByRole("combobox", { name: "Find or create a tag" });
  await user.type(box, "quebec");
  const found = within(screen.getByRole("listbox")).getAllByRole("option");
  expect(found[0]).toHaveTextContent("Québec clients"); // accents and case ignored
  await user.clear(box);
  await user.type(box, "Year-end soon");
  const create = screen.getByRole("option", { name: /Create tag “Year-end soon”/ });
  expect(create).toHaveAttribute("aria-selected", "true");
  await user.click(screen.getByRole("button", { name: "Red" }));
  expect(screen.getByRole("button", { name: "Red" })).toHaveAttribute("aria-pressed", "true");
  box.focus();
  await user.keyboard("{Enter}");
  await waitFor(() =>
    expect(posts).toEqual([{ practice: PRACTICE, name: "Year-end soon", colour: "red" }]),
  );
  const list = container.querySelector("[data-tag-list]") as HTMLElement;
  expect(within(list).getByText("Year-end soon")).toBeInTheDocument();
  expect(within(list).getByText("(Red)")).toBeInTheDocument(); // colour named, never alone
  await expectNoAxeViolations(container);
});

it("shows a refusal", async () => {
  mockApi();
  const user = userEvent.setup();
  renderWithIntl(<TagsSection practice={PRACTICE} />);
  await screen.findByText("Québec clients");
  await user.type(screen.getByRole("combobox"), "Taken{Enter}");
  expect(await screen.findByRole("alert")).toHaveTextContent("There's already a tag called Taken.");
});
