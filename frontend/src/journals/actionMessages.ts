import { defineMessages } from "@/i18n";

/** The journal actions bar (C-04-T10). */
export const am = defineMessages({
  toolbar: {
    id: "journals.actions.toolbar",
    defaultMessage: "Journal actions",
    description: "Accessible name of the journal's actions bar",
  },
  saveDraft: {
    id: "journals.actions.saveDraft",
    defaultMessage: "Save as draft",
    description: "Action",
  },
  submit: {
    id: "journals.actions.submit",
    defaultMessage: "Submit for approval",
    description: "Action: send the draft to an approver",
  },
  post: { id: "journals.actions.post", defaultMessage: "Post journal", description: "Action" },
  approve: {
    id: "journals.actions.approve",
    defaultMessage: "Approve and post",
    description: "Action of an approver",
  },
  reject: {
    id: "journals.actions.reject",
    defaultMessage: "Send back",
    description: "Action of an approver: back to draft with a reason",
  },
  withdraw: {
    id: "journals.actions.withdraw",
    defaultMessage: "Withdraw",
    description: "Action of the author: take the journal back from approval",
  },
  copy: {
    id: "journals.actions.copy",
    defaultMessage: "Copy journal",
    description: "Action: a new journal with the same lines",
  },
  reverse: {
    id: "journals.actions.reverse",
    defaultMessage: "Reverse journal",
    description: "Action: post the mirror entry",
  },
  working: { id: "journals.actions.working", defaultMessage: "Working…", description: "Busy" },
  failed: {
    id: "journals.actions.failed",
    defaultMessage: "That didn't work. Try again.",
    description: "Unexpected error of an action",
  },
  youCreated: {
    id: "journals.actions.youCreated",
    defaultMessage: "You created this: someone else must approve it.",
    description: "Under the actions of the author's journal awaiting approval",
  },
  rejectTitle: {
    id: "journals.actions.rejectTitle",
    defaultMessage: "Send the journal back?",
    description: "Title of the send-back dialog",
  },
  reason: {
    id: "journals.actions.reason",
    defaultMessage: "Reason (at least {min} characters)",
    description: "Field of the send-back dialog",
  },
  reverseTitle: {
    id: "journals.actions.reverseTitle",
    defaultMessage: "Reverse this journal?",
    description: "Title of the reverse dialog",
  },
  reverseBody: {
    id: "journals.actions.reverseBody",
    defaultMessage:
      "A new journal with debits and credits swapped is posted on the date you choose.",
    description: "Text of the reverse dialog",
  },
  reverseDate: {
    id: "journals.actions.reverseDate",
    defaultMessage: "Reversal date",
    description: "Field of the reverse dialog",
  },
  cancel: { id: "journals.actions.cancel", defaultMessage: "Cancel", description: "Button" },
  close: { id: "journals.actions.close", defaultMessage: "Close", description: "Dialog close" },
});
