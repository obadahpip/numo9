import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { renderWithIntl } from "@/test/intl";

import { expectNoAxeViolations } from "../../../packages/ui/src/test/axe";
import { resetCsrfToken } from "./client";
import { offeredProviders, SocialSignIn } from "./SocialSignIn";

/** A-02-T16 — social sign-in behind a feature flag: flag off → buttons hidden. */
const config = (providers: string[]) => ({
  status: 200,
  data: {
    account: { login_methods: ["email"] },
    ...(providers.length
      ? {
          socialaccount: {
            providers: providers.map((id) => ({ id, name: id, flows: ["provider_redirect"] })),
          },
        }
      : {}),
  },
});

function serve(providers: string[]) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      const body = url.includes("auth/csrf") ? { csrfToken: "tok" } : config(providers);
      return new Response(JSON.stringify(body), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }),
  );
}

beforeEach(() => resetCsrfToken());

it("reads the offered providers, ignoring unknown ones", () => {
  expect(offeredProviders(config(["microsoft", "github", "google"]))).toEqual([
    "google",
    "microsoft",
  ]);
  expect(offeredProviders(config([]))).toEqual([]);
  expect(offeredProviders(undefined)).toEqual([]);
});

it("flag off: no button and no divider", async () => {
  serve([]);
  const { container } = renderWithIntl(<SocialSignIn next="/" />);
  await new Promise((resolve) => setTimeout(resolve, 20));
  expect(screen.queryByRole("button")).toBeNull();
  expect(container.querySelector("[data-social-signin]")).toBeNull();
});

it("flag on: Google and Microsoft buttons post the provider redirect form", async () => {
  serve(["google", "microsoft"]);
  const submit = vi.spyOn(HTMLFormElement.prototype, "submit").mockImplementation(() => {});
  const user = userEvent.setup();
  const { container } = renderWithIntl(<SocialSignIn next="/o/acme" />);
  const google = await screen.findByRole("button", { name: "Continue with Google" });
  expect(screen.getByRole("button", { name: "Continue with Microsoft" })).toBeVisible();
  expect(screen.getByText("or use your email")).toBeVisible();
  await expectNoAxeViolations(container);
  await user.click(google);
  await vi.waitFor(() => expect(submit).toHaveBeenCalledTimes(1));
  const form = document.querySelector<HTMLFormElement>(
    'form[action="/_allauth/browser/v1/auth/provider/redirect"]',
  );
  expect(form?.method.toUpperCase()).toBe("POST");
  const fields = Object.fromEntries(new FormData(form!).entries());
  expect(fields).toEqual({
    provider: "google",
    process: "login",
    callback_url: "/o/acme",
    csrfmiddlewaretoken: "tok",
  });
  submit.mockRestore();
});
