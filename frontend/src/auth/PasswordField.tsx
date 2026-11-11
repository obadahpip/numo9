"use client";

import { Button, Field, Input } from "@numo9/ui";
import { useState } from "react";

import { defineMessages, useFormatMessage } from "@/i18n";

import { passwordStrength, strengthScore, type Strength } from "./passwordStrength";

const messages = defineMessages({
  show: {
    id: "auth.password.show",
    defaultMessage: "Show password",
    description: "Toggle button: reveal the typed password",
  },
  hide: {
    id: "auth.password.hide",
    defaultMessage: "Hide password",
    description: "Toggle button: mask the typed password again",
  },
  hint: {
    id: "auth.password.hint",
    defaultMessage:
      "At least 12 characters. A few unrelated words make a strong, memorable password.",
    description: "Hint under a new-password field",
  },
  strength: {
    id: "auth.password.strength",
    defaultMessage:
      "Password strength: {strength, select, tooShort {too short} fair {fair} good {good} strong {strong} other {}}",
    description: "Password strength meter text; read by screen readers as it changes",
  },
});

const SEGMENT_TONE: Record<Strength, string> = {
  empty: "bg-surface-muted",
  tooShort: "bg-fg-danger",
  fair: "bg-fg-warning",
  good: "bg-fg-success",
  strong: "bg-fg-success",
};

/**
 * Password field of the sign-up and reset forms: show/hide toggle and, for a new password, a
 * strength meter (`meter`) whose text is announced politely as the user types.
 */
export function PasswordField({
  name,
  label,
  autoComplete,
  meter = false,
}: {
  name: string;
  label: string;
  autoComplete: "new-password" | "current-password";
  meter?: boolean;
}) {
  const fm = useFormatMessage();
  const [visible, setVisible] = useState(false);
  return (
    <Field name={name} label={label} required hint={meter ? fm(messages.hint) : undefined}>
      {({ id, invalid, describedBy, field }) => {
        const value = (field.value as string | undefined) ?? "";
        const strength = passwordStrength(value);
        const score = strengthScore(strength);
        return (
          <>
            <div className="flex gap-2">
              <Input
                id={id}
                name={field.name}
                ref={field.ref}
                type={visible ? "text" : "password"}
                autoComplete={autoComplete}
                value={value}
                onChange={field.onChange}
                onBlur={field.onBlur}
                invalid={invalid}
                aria-describedby={[describedBy, meter ? `${id}-strength` : undefined]
                  .filter(Boolean)
                  .join(" ")}
                aria-required
                spellCheck={false}
              />
              <Button
                variant="secondary"
                aria-pressed={visible}
                aria-controls={id}
                onClick={() => setVisible((v) => !v)}
              >
                {visible ? fm(messages.hide) : fm(messages.show)}
              </Button>
            </div>
            {meter ? (
              <div>
                <div aria-hidden="true" className="mt-1 grid grid-cols-4 gap-1">
                  {[1, 2, 3, 4].map((segment) => (
                    <span
                      key={segment}
                      className={`h-1.5 rounded-full ${segment <= score ? SEGMENT_TONE[strength] : "bg-surface-muted"}`}
                    />
                  ))}
                </div>
                <p id={`${id}-strength`} aria-live="polite" className="mt-1 text-xs text-fg-muted">
                  {strength === "empty" ? null : fm(messages.strength, { strength })}
                </p>
              </div>
            ) : null}
          </>
        );
      }}
    </Field>
  );
}
