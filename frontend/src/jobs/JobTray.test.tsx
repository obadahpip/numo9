import { act, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { renderWithIntl } from "@/test/intl";

import type { Job } from "./api";
import { notifyJobsChanged } from "./api";
import { JobTray } from "./JobTray";
import { POLL_ACTIVE_MS } from "./useJobs";

const ORG = "7f3c2a10-1b2c-4d5e-8f90-a1b2c3d4e5f6";

function job(overrides: Partial<Job> = {}): Job {
  return {
    id: "a1b2c3d4-0000-4000-8000-000000000001",
    type: "numo9.contacts.bulk_archive",
    label: "Archive contacts",
    status: "running",
    status_label: "Running",
    progress: { done: 2, total: 5, percent: 40, message: "Contact 2 of 5" },
    result_url: "",
    error: null,
    can_retry: false,
    attempts: 1,
    created_at: "2026-11-12T14:00:00Z",
    started_at: "2026-11-12T14:00:01Z",
    finished_at: null,
    next_retry_at: null,
    ...overrides,
  };
}

const json = (body: unknown, status = 200) =>
  Promise.resolve(
    new Response(JSON.stringify(body), {
      status,
      headers: { "Content-Type": "application/json" },
    }),
  );

let lists: Job[][];
let posts: string[];

beforeEach(() => {
  lists = [];
  posts = [];
  vi.stubGlobal("EventSource", undefined); // jsdom has none: the tray polls
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string, init?: RequestInit) => {
      if (url === "/api/v1/auth/csrf") return json({ csrfToken: "t" });
      if (init?.method === "POST") {
        posts.push(url);
        return json(job({ status: "queued", status_label: "Waiting to start" }), 202);
      }
      return json(lists.length > 1 ? lists.shift() : lists[0]);
    }),
  );
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

async function openTray(name: RegExp | string = /Background jobs/) {
  const button = await screen.findByRole("button", { name });
  await userEvent.click(button);
  return screen.findByRole("dialog", { name: "Background jobs" });
}

describe("JobTray (A-08-T07)", () => {
  it("stays hidden while the person has no jobs", async () => {
    lists = [[]];
    renderWithIntl(<JobTray org={ORG} />);
    await waitFor(() =>
      expect(fetch).toHaveBeenCalledWith(`/api/v1/o/${ORG}/jobs`, expect.anything()),
    );
    expect(screen.queryByRole("button", { name: /Background jobs/ })).not.toBeInTheDocument();
  });

  it("shows a running bulk job's progress", async () => {
    lists = [[job()]];
    renderWithIntl(<JobTray org={ORG} />);
    const tray = await openTray("Background jobs: 1 running");
    const item = within(tray).getByText("Archive contacts").closest("li")!;
    const bar = within(item as HTMLElement).getByRole("progressbar", { name: "Archive contacts" });
    expect(bar).toHaveAttribute("aria-valuenow", "40");
    expect(bar).toHaveAttribute("aria-valuetext", "40% done");
    expect(within(item as HTMLElement).getByText("Contact 2 of 5")).toBeInTheDocument();
    expect(within(item as HTMLElement).getByText("Running")).toBeInTheDocument();
  });

  it("follows progress by polling until the job is done, then links the result", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    lists = [
      [job()], // first load
      [job({ progress: { done: 4, total: 5, percent: 80, message: "Contact 4 of 5" } })],
      [
        job({
          status: "succeeded",
          status_label: "Done",
          progress: { done: 5, total: 5, percent: 100, message: "" },
          result_url: `/o/${ORG}/contacts?archived=1`,
          finished_at: "2026-11-12T14:01:00Z",
        }),
      ],
    ];
    renderWithIntl(<JobTray org={ORG} />);
    const tray = await openTray();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(POLL_ACTIVE_MS + 10);
    });
    await waitFor(() =>
      expect(within(tray).getByRole("progressbar")).toHaveAttribute("aria-valuenow", "80"),
    );
    await act(async () => {
      await vi.advanceTimersByTimeAsync(POLL_ACTIVE_MS + 10);
    });
    const link = await within(tray).findByRole("link", { name: "Open the result" });
    expect(link).toHaveAttribute("href", `/o/${ORG}/contacts?archived=1`);
    expect(within(tray).queryByRole("progressbar")).not.toBeInTheDocument();
    expect(within(tray).getByText(/^Finished /)).toBeInTheDocument();
  });

  it("shows a failed job's error and starts it again", async () => {
    lists = [
      [
        job({
          status: "dead",
          status_label: "Failed after several tries",
          error: {
            code: "job.failed",
            message: "Something went wrong while this job was running.",
          },
          can_retry: true,
        }),
      ],
    ];
    renderWithIntl(<JobTray org={ORG} />);
    const tray = await openTray("Background jobs");
    expect(
      within(tray).getByText("Something went wrong while this job was running."),
    ).toBeVisible();
    expect(within(tray).getByText("Reference: a1b2c3d4")).toBeVisible();
    await userEvent.click(within(tray).getByRole("button", { name: "Try again" }));
    await within(tray).findByText("Waiting to start");
    expect(posts).toEqual([`/api/v1/o/${ORG}/jobs/a1b2c3d4-0000-4000-8000-000000000001/retry`]);
    expect(within(tray).queryByRole("button", { name: "Try again" })).not.toBeInTheDocument();
  });

  it("says so when Try again itself fails", async () => {
    lists = [
      [
        job({
          status: "failed",
          status_label: "Failed",
          can_retry: true,
          error: { code: "job.failed", message: "Failed." },
        }),
      ],
    ];
    vi.mocked(fetch).mockImplementation((url: string | URL | Request, init?: RequestInit) => {
      if (url === "/api/v1/auth/csrf") return json({ csrfToken: "t" });
      if (init?.method === "POST") return json({ code: "job.not_retryable", detail: "x" }, 409);
      return json(lists[0]);
    });
    renderWithIntl(<JobTray org={ORG} />);
    const tray = await openTray();
    await userEvent.click(within(tray).getByRole("button", { name: "Try again" }));
    expect(await within(tray).findByRole("alert")).toHaveTextContent("couldn't be started again");
  });

  it("appears as soon as a screen starts a job", async () => {
    lists = [[]];
    renderWithIntl(<JobTray org={ORG} />);
    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(1));
    lists = [[job({ status: "queued", status_label: "Waiting to start" })]];
    act(() => notifyJobsChanged());
    const tray = await openTray("Background jobs: 1 running");
    expect(within(tray).getByText("Waiting for a free server…")).toBeVisible();
  });

  it("follows the event stream when the browser has EventSource", async () => {
    const sources: FakeEventSource[] = [];
    class FakeEventSource {
      static CLOSED = 2;
      readyState = 1;
      listeners: Record<string, ((event: MessageEvent<string>) => void)[]> = {};
      onerror: (() => void) | null = null;
      closed = false;
      constructor(public url: string) {
        sources.push(this);
      }
      addEventListener(type: string, listener: (event: MessageEvent<string>) => void) {
        (this.listeners[type] ??= []).push(listener);
      }
      emit(type: string, data: unknown) {
        for (const listener of this.listeners[type] ?? [])
          listener(new MessageEvent(type, { data: JSON.stringify(data) }));
      }
      close() {
        this.closed = true;
      }
    }
    vi.stubGlobal("EventSource", FakeEventSource);
    lists = [[job()]];
    renderWithIntl(<JobTray org={ORG} />);
    const tray = await openTray();
    await waitFor(() => expect(sources).toHaveLength(1));
    expect(sources[0]!.url).toBe(`/api/v1/o/${ORG}/jobs/events`);
    act(() =>
      sources[0]!.emit("jobs", [
        job({ progress: { done: 3, total: 5, percent: 60, message: "Contact 3 of 5" } }),
      ]),
    );
    expect(within(tray).getByRole("progressbar")).toHaveAttribute("aria-valuenow", "60");
    act(() => {
      sources[0]!.emit("jobs", [job({ status: "succeeded", status_label: "Done" })]);
      sources[0]!.emit("idle", { active: 0 });
    });
    expect(within(tray).getByText("Done")).toBeVisible();
    expect(sources[0]!.closed).toBe(true);
  });
});
