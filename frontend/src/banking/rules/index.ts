/**
 * Bank rules (F-04) — what other screens use: the statement-lines list (F-02) drops in
 * ``CreateRuleFromLineAction`` (T14) and ``RevertAutoCodedAction`` (T15) per row.
 */
export {
  CreateRuleFromLineAction,
  type CreateRuleFromLineActionProps,
} from "./CreateRuleFromLineAction";
export { prefillDraft, ruleFromLineHref, type StatementLineLike } from "./fromLine";
