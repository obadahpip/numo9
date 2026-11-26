import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { serveJson } from "@/banking/fixtures";
import { renderWithIntl } from "@/test/intl";

import type { Overview, StepKey } from "./api";
import { ConversionWizard } from "./ConversionWizard";
import { ACCOUNTS, overview, session } from "./fixtures";

/**
 * C-05-T10 — the wizard resumes at the step saved on the server; "Save and continue" saves the
 * step's balances, marks it done and moves on (PATCH step + completed_steps); before a
 * conversion exists only the date step is offered.
 */
let state: Overview;
let calls: { method: string; url: string; body: unknown }[] = [];

beforeEach(() => {
  calls = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(
      serveJson((url, init) => {
        const method = init?.method ?? "GET";
        const body = init?.body ? JSON.parse(String(init.body)) : null;
        calls.push({ method, url, body });
        if (url.includes("/accounts?")) return { body: { results: ACCOUNTS, count: 2 } };
        if (url.endsWith("/conversion/lines") && method === "GET") return { body: { lines: [] } };
        if (url.endsWith("/conversion/lines")) return { body: { lines: [], difference: {} } };
        if (url.includes("/conversion/documents")) return { body: { documents: [] } };
        if (url.endsWith("/conversion/") && method === "PATCH") {
          const changes = body as { step?: StepKey; completed_steps?: StepKey[] };
          state = {
            ...state,
            session: {
              ...state.session!,
              step: changes.step ?? state.session!.step,
              completed_steps: changes.completed_steps ?? state.session!.completed_steps,
            },
          };
          return { body: state };
        }
        if (url.endsWith("/conversion/") && method === "POST") {
          state = overview({ session: session({ step: "date", completed_steps: [] }) });
          return { status: 201, body: state };
        }
        return { body: state };
      }),
    ),
  );
});
afterEach(() => vi.unstubAllGlobals());

const current = () =>
  document.querySelector('[aria-current="step"]')?.getAttribute("data-step-key");

it("resumes at the saved step and saves progress on Save and continue", async () => {
  const user = userEvent.setup();
  state = overview({ session: session({ step: "bank", completed_steps: ["date"] }) });
  renderWithIntl(<ConversionWizard org="acme" />);
  await waitFor(() => expect(current()).toBe("bank"));
  expect(screen.getByRole("button", { name: "1. Conversion date (done)" })).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Save and continue" }));
  await waitFor(() => expect(current()).toBe("invoices"));
  const put = calls.find((c) => c.method === "PUT" && c.url.endsWith("/conversion/lines"));
  expect(put?.body).toEqual({ lines: [] });
  const patch = calls.filter((c) => c.method === "PATCH").at(-1);
  expect(patch?.body).toEqual({ step: "invoices", completed_steps: ["date", "bank"] });
  expect(screen.getByRole("button", { name: "2. Bank and cash (done)" })).toBeInTheDocument();
});

it("jumps to any step from the stepper", async () => {
  const user = userEvent.setup();
  state = overview({ session: session({ step: "bills", completed_steps: ["date", "bank"] }) });
  renderWithIntl(<ConversionWizard org="acme" />);
  await waitFor(() => expect(current()).toBe("bills"));
  await user.click(screen.getByRole("button", { name: "6. Review and finalise" }));
  await waitFor(() => expect(current()).toBe("review"));
  expect(screen.getByText(/No equity balance was entered/)).toBeInTheDocument();
});

it("before a conversion exists: the date step starts one", async () => {
  const user = userEvent.setup();
  state = overview({ session: null, difference: null });
  renderWithIntl(<ConversionWizard org="acme" />);
  const date = await screen.findByLabelText("Conversion date", { selector: "input" });
  expect(screen.getByRole("button", { name: "2. Bank and cash" })).toBeDisabled();
  await user.type(date, "2026-01-01");
  await user.click(screen.getByRole("button", { name: "Start the conversion" }));
  await waitFor(() => expect(current()).toBe("bank"));
  expect(calls.find((c) => c.method === "POST")?.body).toEqual({ conversion_date: "2026-01-01" });
});
