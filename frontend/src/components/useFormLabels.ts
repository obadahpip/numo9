"use client";

import type { FormLabels } from "@numo9/ui";
import { useMemo } from "react";

import { defineMessages, useFormatMessage } from "@/i18n";

const messages = defineMessages({
  errorSummaryTitle: {
    id: "form.errorSummaryTitle",
    defaultMessage:
      "{count, plural, one {There is # problem with this form} other {There are # problems with this form}}",
    description: "Heading of the error summary at the top of a form after a failed submit",
  },
  save: { id: "form.save", defaultMessage: "Save", description: "Sticky save bar: save button" },
  saving: { id: "form.saving", defaultMessage: "Saving…", description: "Save button while busy" },
  discard: {
    id: "form.discard",
    defaultMessage: "Discard changes",
    description: "Sticky save bar: undo all unsaved edits",
  },
  unsavedChanges: {
    id: "form.unsavedChanges",
    defaultMessage: "You have unsaved changes.",
    description: "Sticky save bar text",
  },
  leaveTitle: {
    id: "form.leaveTitle",
    defaultMessage: "Leave without saving?",
    description: "Unsaved-changes dialog heading",
  },
  leaveBody: {
    id: "form.leaveBody",
    defaultMessage: "Your changes on this page will be lost.",
    description: "Unsaved-changes dialog body",
  },
  stay: { id: "form.stay", defaultMessage: "Stay on this page", description: "Dialog button" },
  leave: {
    id: "form.leave",
    defaultMessage: "Leave without saving",
    description: "Dialog button: leave and lose the changes",
  },
  close: { id: "form.close", defaultMessage: "Close", description: "Dialog close button" },
});

/** The form kit's labels (A-10-T07) from the app's i18n catalogue. */
export function useFormLabels(): FormLabels {
  const fm = useFormatMessage();
  return useMemo(
    () => ({
      errorSummaryTitle: (count: number) => fm(messages.errorSummaryTitle, { count }),
      save: fm(messages.save),
      saving: fm(messages.saving),
      discard: fm(messages.discard),
      unsavedChanges: fm(messages.unsavedChanges),
      leaveTitle: fm(messages.leaveTitle),
      leaveBody: fm(messages.leaveBody),
      stay: fm(messages.stay),
      leave: fm(messages.leave),
      close: fm(messages.close),
    }),
    [fm],
  );
}
