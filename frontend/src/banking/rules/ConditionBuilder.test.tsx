import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";

import { renderWithIntl } from "@/test/intl";

import { expectNoAxeViolations } from "../../../../packages/ui/src/test/axe";
import type { MatchMode, RuleCondition } from "./api";
import { ConditionBuilder, conditionComplete, emptyCondition } from "./ConditionBuilder";
import { foldAccents, highlightMatches } from "./regex";

/**
 * F-04-T11 — sentence-style rule builder with operator-aware inputs. Acceptance: the regex tester
 * highlights the matches in a sample text (case and accents ignored); "amount is between" shows
 * two fields; "is blank" none; the operators follow the field.
 */
function Harness({ initial }: { initial: RuleCondition[] }) {
  const [conditions, setConditions] = useState(initial);
  const [mode, setMode] = useState<MatchMode>("all");
  return (
    <>
      <ConditionBuilder
        conditions={conditions}
        matchMode={mode}
        onChange={setConditions}
        onMatchModeChange={setMode}
      />
      <output data-testid="state">{JSON.stringify({ conditions, mode })}</output>
    </>
  );
}

const state = () => JSON.parse(screen.getByTestId("state").textContent ?? "{}");

it("regex tester highlights the matches in the sample text", async () => {
  const user = userEvent.setup();
  const { container } = renderWithIntl(
    <Harness initial={[{ ...emptyCondition(), operator: "regex" }]} />,
  );
  await user.type(screen.getByLabelText("Condition 1: pattern"), "petro\\S*");
  await user.type(
    screen.getByLabelText("Test condition 1 on a sample text"),
    "PÉTRO-CANADA #12 and petro again",
  );
  const highlighted = container.querySelector("[data-highlighted]")!;
  const marks = within(highlighted as HTMLElement)
    .getAllByText((_t, el) => el?.tagName === "MARK")
    .map((el) => el.textContent);
  expect(marks).toEqual(["PÉTRO-CANADA", "petro"]);
  expect(screen.getByText("2 matches")).toBeVisible();
  expect(state().conditions[0]).toMatchObject({ operator: "regex", value: "petro\\S*" });
  await expectNoAxeViolations(container);
});

it("an invalid pattern is flagged and the condition is incomplete", async () => {
  const user = userEvent.setup();
  renderWithIntl(<Harness initial={[{ ...emptyCondition(), operator: "regex" }]} />);
  await user.type(screen.getByLabelText("Condition 1: pattern"), "(unclosed");
  await user.type(screen.getByLabelText("Test condition 1 on a sample text"), "x");
  expect(screen.getByRole("alert")).toHaveTextContent("This pattern isn't valid.");
  expect(conditionComplete(state().conditions[0])).toBe(false);
});

it("amount between shows two fields; is blank shows none; operators follow the field", async () => {
  const user = userEvent.setup();
  renderWithIntl(<Harness initial={[emptyCondition()]} />);
  const operator = () => screen.getByLabelText("Condition 1: comparison") as HTMLSelectElement;
  expect(Array.from(operator().options).map((o) => o.value)).toContain("regex");

  await user.selectOptions(screen.getByLabelText("Condition 1: field"), "amount");
  expect(Array.from(operator().options).map((o) => o.value)).toEqual([
    "between",
    "equals",
    "gt",
    "lt",
  ]);
  await user.selectOptions(operator(), "between");
  await user.type(screen.getByLabelText("Condition 1: lowest amount"), "20");
  await user.type(screen.getByLabelText("Condition 1: highest amount"), "200");
  expect(state().conditions[0]).toMatchObject({
    field: "amount",
    operator: "between",
    value: "20",
    value_to: "200",
  });
  expect(conditionComplete(state().conditions[0])).toBe(true);

  await user.selectOptions(operator(), "gt");
  expect(screen.queryByLabelText("Condition 1: highest amount")).toBeNull();
  expect(screen.getByLabelText("Condition 1: value")).toBeVisible();

  await user.selectOptions(screen.getByLabelText("Condition 1: field"), "reference");
  await user.selectOptions(operator(), "is_blank");
  expect(screen.queryByLabelText("Condition 1: value")).toBeNull();
  expect(conditionComplete(state().conditions[0])).toBe(true);
});

it("adds, joins and removes conditions; any/all", async () => {
  const user = userEvent.setup();
  renderWithIntl(<Harness initial={[{ ...emptyCondition(), value: "PETRO" }]} />);
  await user.click(screen.getByRole("button", { name: "Add a condition" }));
  expect(screen.getByLabelText("Condition 2: field")).toBeVisible();
  expect(screen.getByText("and")).toBeVisible();
  await user.selectOptions(screen.getByLabelText("Match all or any condition"), "any");
  expect(screen.getByText("or")).toBeVisible();
  await user.click(screen.getByRole("button", { name: "Remove condition 2" }));
  expect(state()).toMatchObject({ mode: "any", conditions: [{ value: "PETRO" }] });
});

it("highlight helpers fold accents and keep offsets", () => {
  expect(foldAccents("Café Montréal")).toBe("Cafe Montreal");
  const result = highlightMatches("montreal", "Café Montréal");
  expect(result.parts).toEqual([
    { text: "Café ", match: false },
    { text: "Montréal", match: true },
  ]);
  expect(highlightMatches("", "x").count).toBe(0);
});
