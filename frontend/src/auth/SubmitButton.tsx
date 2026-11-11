"use client";

import { Button } from "@numo9/ui";
import { useFormContext } from "react-hook-form";

/** Primary submit button of an auth form: busy (spinner, `aria-busy`) while the request runs. */
export function SubmitButton({ label, busyLabel }: { label: string; busyLabel: string }) {
  const { formState } = useFormContext();
  return (
    <Button type="submit" variant="primary" loading={formState.isSubmitting} className="w-full">
      {formState.isSubmitting ? busyLabel : label}
    </Button>
  );
}
