import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { DataGrid } from "../data-grid/DataGrid";
import { gridLabels, orgColumns } from "../data-grid/fixtures";
import { Button } from "../primitives/Button";
import { expectNoAxeViolations } from "../test/axe";
import { EmptyState } from "./EmptyState";
import { ErrorState } from "./ErrorState";
import { ExplainPanel } from "./ExplainPanel";
import { LoadingRegion, Skeleton, SkeletonTable, SkeletonText } from "./Skeleton";

describe("EmptyState (A-10-T12)", () => {
  it("shows illustration, title, body and at most 3 actions", () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => undefined);
    render(
      <EmptyState
        illustration="contacts"
        title="No contacts yet"
        body="Customers and suppliers you add appear here."
        actions={[
          <Button key="1" variant="primary">
            New contact
          </Button>,
          <Button key="2">Import contacts</Button>,
          <Button key="3">Learn about contacts</Button>,
          <Button key="4">Fourth</Button>,
        ]}
      />,
    );
    expect(screen.getByRole("heading", { level: 2, name: "No contacts yet" })).toBeInTheDocument();
    expect(screen.getAllByRole("button")).toHaveLength(3);
    expect(warn).toHaveBeenCalled();
    expect(document.querySelector("[data-illustration=contacts]")).toHaveAttribute(
      "aria-hidden",
      "true",
    );
  });

  it("has no axe violations", async () => {
    render(
      <EmptyState
        illustration="documents"
        title="No documents"
        actions={[<Button key="u">Upload files</Button>]}
      />,
    );
    await expectNoAxeViolations();
  });
});

describe("Skeletons (A-10-T12)", () => {
  it("are decorative; the loading region announces one message", async () => {
    render(
      <LoadingRegion label="Loading contacts…">
        <Skeleton shape="circle" width={40} />
        <SkeletonText lines={2} />
        <SkeletonTable rows={2} columns={3} />
      </LoadingRegion>,
    );
    expect(screen.getByRole("status")).toHaveTextContent("Loading contacts…");
    expect(document.querySelectorAll("[data-skeleton]").length).toBe(1 + 2 + 6);
    expect(screen.getByRole("status").parentElement).toHaveAttribute("aria-busy", "true");
    await expectNoAxeViolations();
  });
});

describe("ErrorState (A-10-T12)", () => {
  it("offers Try again and Report a problem with a reference", async () => {
    const user = userEvent.setup();
    const onRetry = vi.fn();
    const onReport = vi.fn();
    render(
      <ErrorState
        title="Organisations couldn't be loaded"
        body="The connection to Numo9 dropped. Your data is safe — try again."
        retryLabel="Try again"
        onRetry={onRetry}
        reportLabel="Report a problem"
        onReport={onReport}
        reference="7f3c2a10"
        referenceLabel={(ref) => `Reference: ${ref}`}
      />,
    );
    expect(screen.getByRole("alert")).toHaveTextContent("Organisations couldn't be loaded");
    await user.click(screen.getByRole("button", { name: "Try again" }));
    await user.click(screen.getByRole("button", { name: "Report a problem" }));
    expect(onRetry).toHaveBeenCalledOnce();
    expect(onReport).toHaveBeenCalledOnce();
    expect(screen.getByText("Reference: 7f3c2a10")).toBeInTheDocument();
    await expectNoAxeViolations();
  });
});

describe("ExplainPanel (A-10-T12)", () => {
  it.each(["gated", "readOnly", "permission", "lock", "notFound"] as const)(
    "%s: what, why, who can fix, actions",
    async (kind) => {
      render(
        <ExplainPanel
          kind={kind}
          title="Payroll isn't in your package (Starter)"
          body="It's included in Growth and Complete. Your existing data stays available to view."
          fixer="Ask the organisation owner, Dana Lee, to upgrade."
          actions={[
            <Button key="c" variant="primary">
              Compare packages
            </Button>,
            <Button key="a">Ask the owner to upgrade</Button>,
          ]}
          headingLevel={1}
        />,
      );
      const panel = screen.getByRole("region", { name: "Payroll isn't in your package (Starter)" });
      expect(panel).toHaveAttribute("data-explain", kind);
      expect(panel).toHaveTextContent("Ask the organisation owner, Dana Lee, to upgrade.");
      expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument();
      await expectNoAxeViolations();
    },
  );
});

describe("DataGrid uses the state components (A-10-T12)", () => {
  it("loading rows are Skeletons; empty and error slots take EmptyState / ErrorState", () => {
    const { rerender } = render(
      <DataGrid
        data={[]}
        columns={orgColumns}
        getRowId={(o) => o.id}
        getRowLabel={(o) => o.name}
        labels={gridLabels}
        status="loading"
      />,
    );
    expect(document.querySelectorAll("[data-skeleton]").length).toBeGreaterThan(0);
    rerender(
      <DataGrid
        data={[]}
        columns={orgColumns}
        getRowId={(o) => o.id}
        getRowLabel={(o) => o.name}
        labels={gridLabels}
        emptyState={<EmptyState illustration="organisations" title="No organisations yet" />}
      />,
    );
    expect(screen.getByRole("heading", { name: "No organisations yet" })).toBeInTheDocument();
    rerender(
      <DataGrid
        data={[]}
        columns={orgColumns}
        getRowId={(o) => o.id}
        getRowLabel={(o) => o.name}
        labels={gridLabels}
        status="error"
        errorState={
          <ErrorState
            title="Organisations couldn't be loaded"
            retryLabel="Try again"
            onRetry={() => undefined}
          />
        }
      />,
    );
    expect(screen.getByRole("alert")).toHaveTextContent("Organisations couldn't be loaded");
  });
});
