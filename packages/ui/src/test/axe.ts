import axe from "axe-core";

/**
 * Accessibility check for component tests (A-10-T06): runs axe-core (WCAG 2.0/2.1 A + AA rules)
 * on `container` and fails with a readable list of violations. Colour contrast is checked by the
 * token contrast script (A-10-T04) — jsdom cannot compute styles — and visually in Storybook.
 */
export async function expectNoAxeViolations(container: Element = document.body): Promise<void> {
  const result = await axe.run(container, {
    runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "best-practice"] },
    rules: {
      "color-contrast": { enabled: false },
      // Components are tested in isolation, outside a page with landmarks and a main heading.
      region: { enabled: false },
      "page-has-heading-one": { enabled: false },
      "landmark-one-main": { enabled: false },
    },
  });
  const problems = result.violations.map(
    (violation) =>
      `${violation.id} (${violation.impact}): ${violation.help}\n` +
      violation.nodes.map((node) => `    ${node.target.join(" ")}`).join("\n"),
  );
  expect(problems, problems.join("\n")).toEqual([]);
}
