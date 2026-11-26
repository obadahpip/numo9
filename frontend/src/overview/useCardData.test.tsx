import { OverviewCard } from "@numo9/ui";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { apiRequest } from "@/auth/client";
import { useFormatMessage } from "@/i18n";
import { renderWithIntl, testFormatMessage } from "@/test/intl";

import { cardError, cardState, useCardData } from "./useCardData";

/**
 * D-09-T10 (gap-05) — an overview card's error: a simulated 500 shows what failed, Try again and
 * the support reference (the request's X-Request-ID); Try again recovers; nothing is silent.
 */
interface Owing {
  total: string;
}

function Card({ fetcher }: { fetcher: typeof fetch }) {
  const fm = useFormatMessage();
  const card = useCardData<Owing>(
    (headers) => apiRequest<Owing>("/api/v1/o/x/overview", { headers, fetcher }),
    "x",
  );
  return (
    <OverviewCard cardKey="owing" {...cardState(fm, "Money coming in", card)}>
      <p>Owed: {card.data?.total}</p>
    </OverviewCard>
  );
}

const answer = (status: number, body: unknown, requestId?: string) =>
  new Response(JSON.stringify(body), {
    status,
    headers: {
      "Content-Type": "application/json",
      ...(requestId ? { "X-Request-ID": requestId } : {}),
    },
  });

describe("overview card errors (D-09-T10, gap-05)", () => {
  it("a 500 shows what failed, Try again and the reference; Try again recovers", async () => {
    const fetcher = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(answer(500, { detail: "boom" }, "req-5f1c9e2a"))
      .mockResolvedValueOnce(answer(200, { total: "1250.00" }));
    renderWithIntl(<Card fetcher={fetcher} />);

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Money coming in couldn't be loaded");
    expect(alert).toHaveTextContent("Something went wrong on our side");
    expect(alert).toHaveTextContent("Reference: req-5f1c9e2a");
    expect(alert).not.toHaveTextContent(/unable to load/i);

    await userEvent.click(within(alert).getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("Owed: 1250.00")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(fetcher).toHaveBeenCalledTimes(2);
  });

  it("sends a fresh X-Request-ID with every attempt", async () => {
    const fetcher = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(answer(503, {}))
      .mockResolvedValueOnce(answer(200, { total: "0.00" }));
    renderWithIntl(<Card fetcher={fetcher} />);
    const alert = await screen.findByRole("alert");
    const sent = (call: number) =>
      (fetcher.mock.calls[call]?.[1]?.headers as Record<string, string>)["X-Request-ID"];
    // Without an echo from the server, the reference is the one the client sent.
    expect(alert).toHaveTextContent(`Reference: ${sent(0)}`);
    expect(sent(0)).toMatch(/^web-[0-9a-z]{16}$/);
    await userEvent.click(within(alert).getByRole("button", { name: "Try again" }));
    await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(2));
    expect(sent(1)).not.toBe(sent(0));
  });

  it("offline: says the connection may have dropped and still shows a reference", async () => {
    const fetcher = vi.fn<typeof fetch>().mockRejectedValue(new TypeError("Failed to fetch"));
    renderWithIntl(<Card fetcher={fetcher} />);
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Numo9 couldn't be reached");
    expect(alert).toHaveTextContent(/Reference: web-/);
  });

  it("explains a refusal by status", () => {
    const fm = testFormatMessage();
    expect(cardError(fm, "Bills to pay", { status: 403 }).body).toMatch(/role doesn't include/);
    expect(cardError(fm, "Bills to pay", { status: 400, reference: "r1" })).toMatchObject({
      title: "Bills to pay couldn't be loaded",
      reference: "r1",
    });
  });
});
