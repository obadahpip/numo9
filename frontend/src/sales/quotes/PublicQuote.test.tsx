import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { renderWithIntl } from "@/test/intl";

import { TOKEN, publicQuote, serveJson } from "./fixtures";
import { PublicQuote, groupsOf, initialSelection } from "./PublicQuote";

/**
 * D-02-T13 — the public quote page: option toggles ask the server for the totals (live, nothing
 * saved); accepting takes the typed name (the signature is optional) and the options chosen; an
 * expired quote shows the reason and "ask for a new quote", and Accept is disabled; a revoked
 * link says so.
 */
afterEach(() => vi.unstubAllGlobals());

function serve(body: unknown, status = 200) {
  const calls: { url: string; method: string; body: unknown }[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(
      serveJson((url, init) => {
        const method = init?.method ?? "GET";
        const sent = init?.body ? JSON.parse(String(init.body)) : null;
        calls.push({ url, method, body: sent });
        if (url.endsWith("/preview"))
          return {
            body: {
              lines: {},
              subtotal: "1700.00",
              discount_total: "0.00",
              tax_total: "221.00",
              total: "1921.00",
              deposit: "384.20",
            },
          };
        if (url.endsWith("/accept"))
          return {
            body: publicQuote({
              status: "accepted",
              can_accept: false,
              reason: "accepted",
              accepted_by: "Jo Lee",
              total: "1921.00",
            }),
          };
        return { status, body };
      }),
    ),
  );
  return calls;
}

it("ticks an option, recalculates live and accepts with the typed name", async () => {
  const calls = serve(publicQuote());
  const user = userEvent.setup({ delay: null });
  renderWithIntl(<PublicQuote token={TOKEN} />);
  expect(
    await screen.findByRole("heading", { name: "Quote QU-0001: Kitchen renovation" }),
  ).toBeVisible();
  expect(screen.getByRole("radio", { name: /Oak doors/ })).toBeChecked();
  await user.click(screen.getByRole("checkbox", { name: /Install/ }));
  await waitFor(() => expect(screen.getByText("$1,921.00", { selector: "dd" })).toBeVisible());
  expect(screen.getByText("$384.20")).toBeVisible();
  const preview = calls.find((c) => c.url.endsWith("/preview"))!;
  expect(preview.body).toEqual({ selections: { p2: true, p3: true, p4: false } });

  await user.click(screen.getByRole("button", { name: "Accept for $1,921.00" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Type your name");
  await user.type(screen.getByRole("textbox", { name: /Your full name/ }), "Jo Lee");
  await user.click(screen.getByRole("button", { name: "Accept for $1,921.00" }));
  expect(await screen.findByText("Accepted by Jo Lee. Thank you!")).toBeVisible();
  const accepted = calls.find((c) => c.url.endsWith("/accept"))!;
  expect(accepted.body).toEqual({
    typed_name: "Jo Lee",
    signature: "",
    selections: { p2: true, p3: true, p4: false },
  });
  expect(screen.getByRole("button", { name: /Accept for/ })).toBeDisabled();
}, 30_000);

it("an expired quote shows why and can't be accepted", async () => {
  serve(publicQuote({ status: "expired", can_accept: false, reason: "expired" }));
  renderWithIntl(<PublicQuote token={TOKEN} />);
  expect(
    await screen.findByText(
      "This quote expired at the end of 2026-07-15: it can't be accepted any more.",
    ),
  ).toBeVisible();
  expect(screen.getByText("Ask Refined Interiors Inc. for a new quote.")).toBeVisible();
  expect(screen.getByRole("button", { name: /Accept for/ })).toBeDisabled();
  expect(screen.getByRole("checkbox", { name: /Install/ })).toBeDisabled();
  expect(screen.queryByRole("button", { name: "Decline the quote" })).toBeNull();
});

it("a withdrawn link says so; helpers group and preselect", async () => {
  serve({ code: "sales.quote.link_revoked" }, 410);
  renderWithIntl(<PublicQuote token={TOKEN} />);
  expect(
    await screen.findByRole("heading", { name: "This quote link was withdrawn." }),
  ).toBeVisible();
  const lines = publicQuote().lines;
  expect(groupsOf(lines).map(([group, members]) => [group, members.length])).toEqual([["Wood", 2]]);
  expect(initialSelection(lines)).toEqual({ p2: false, p3: true, p4: false });
});
