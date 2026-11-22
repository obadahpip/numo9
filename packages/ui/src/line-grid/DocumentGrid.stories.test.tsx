import { render, screen } from "@testing-library/react";

import { problemCells } from "./DocumentLines";
import { sampleDocumentLines } from "./fixtures";
import * as stories from "./LineGrid.stories";

/**
 * D-01-T18: every state of the document grid has a story (the spec parity table in
 * docs/design/line-grid.md lists them); each renders.
 */
const STATES = [
  "DocumentLinesStory",
  "DocumentLinesEmpty",
  "DocumentLinesReadOnly",
  "DocumentLinesProblems",
  "DocumentLinesPurchase",
  "DocumentTotalsStory",
  "DocumentTotalsInclusive",
] as const;

describe("document grid stories (D-01-T18)", () => {
  it.each(STATES)("%s exists and renders", (name) => {
    const story = stories[name] as { render: () => React.ReactElement };
    expect(typeof story.render).toBe("function");
    const { unmount } = render(story.render());
    expect(screen.getAllByRole(name.startsWith("DocumentTotals") ? "region" : "grid").length).toBe(
      1,
    );
    unmount();
  });

  it("read-only shows no line controls", () => {
    render(stories.DocumentLinesReadOnly.render!({} as never, {} as never));
    expect(screen.queryByRole("button", { name: /Delete line/ })).toBeNull();
    expect(screen.queryByRole("button", { name: "Add a line" })).toBeNull();
  });

  it("server problems flag their cells", () => {
    render(stories.DocumentLinesProblems.render!({} as never, {} as never));
    const row = document.querySelector('tr[data-line="2"]')!;
    expect(row.querySelectorAll("td[data-invalid]")).toHaveLength(2);
  });
});

describe("problemCells", () => {
  it("maps the server's {line, field} to grid cells", () => {
    expect(
      problemCells(sampleDocumentLines, [
        { line: 1, field: "tax_code" },
        { line: 2, field: "account" },
        { line: 9, field: "account" },
      ]),
    ).toEqual({ d1: ["taxCode"], d2: ["account"] });
  });
});
