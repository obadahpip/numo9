import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { serveJson } from "@/banking/fixtures";
import { renderWithIntl } from "@/test/intl";

import { RETURN_ID, taxReturn } from "./fixtures";
import { ReturnActions } from "./ReturnActions";

/** G-03-T12 — mark as filed needs the confirmation number; a filed return shows the lock. */
const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));
afterEach(() => vi.unstubAllGlobals());

it("marks a reviewed return as filed with its confirmation number", async () => {
  const bodies: unknown[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(
      serveJson((_url, init) => {
        bodies.push(JSON.parse(String(init?.body ?? "{}")));
        return {
          body: taxReturn({ status: "filed", filed_on: "2026-07-20", confirmation_no: "GH-1" }),
        };
      }),
    ),
  );
  const onChange = vi.fn();
  renderWithIntl(
    <ReturnActions org="acme" data={taxReturn({ status: "reviewed" })} onChange={onChange} />,
  );
  await userEvent.click(screen.getByRole("button", { name: "Mark as filed" }));
  const dialog = await screen.findByRole("dialog", { name: "Mark the return as filed" });
  await userEvent.click(within(dialog).getByRole("button", { name: "Mark as filed" }));
  expect(within(dialog).getByRole("alert")).toHaveTextContent("Required");
  await userEvent.type(
    within(dialog).getByRole("textbox", { name: "Confirmation number" }),
    "GH-1",
  );
  await userEvent.click(within(dialog).getByRole("button", { name: "Mark as filed" }));
  await waitFor(() => expect(onChange).toHaveBeenCalled());
  expect(bodies.at(-1)).toMatchObject({ confirmation_no: "GH-1" });
});

it("a filed return shows the lock and offers Amend", () => {
  renderWithIntl(
    <ReturnActions
      org="acme"
      data={taxReturn({
        id: RETURN_ID,
        status: "filed",
        filed_on: "2026-07-20",
        confirmation_no: "GH-1",
      })}
      onChange={() => undefined}
    />,
  );
  expect(screen.getByRole("img", { name: "Locked: filed" })).toBeVisible();
  expect(screen.getByText("Filed on 20 Jul 2026 · confirmation GH-1")).toBeVisible();
  expect(screen.getByRole("button", { name: "Amend" })).toBeEnabled();
});
