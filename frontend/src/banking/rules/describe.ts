/** Rules in words (F-04-T10/T11): "Description contains “PETRO” and Amount is between 20 and 200". */
import type { FormatMessage } from "@/i18n";

import type { MatchMode, RuleCondition } from "./api";
import { fieldLabels, m, operatorLabels, sentence } from "./messages";

export function describeCondition(fm: FormatMessage, condition: RuleCondition): string {
  const field = fm(fieldLabels[condition.field]);
  const operator = fm(operatorLabels[condition.operator]);
  if (condition.operator === "is_blank") return fm(sentence.conditionBlank, { field, operator });
  if (condition.operator === "between") {
    return fm(sentence.conditionRange, {
      field,
      operator,
      low: condition.value,
      high: condition.value_to,
    });
  }
  return fm(sentence.condition, { field, operator, value: condition.value });
}

export function describeConditions(
  fm: FormatMessage,
  conditions: RuleCondition[],
  mode: MatchMode,
): string {
  const joiner = ` ${fm(mode === "any" ? m.or : m.and)} `;
  return conditions.map((c) => describeCondition(fm, c)).join(joiner);
}
