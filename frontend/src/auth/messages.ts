/** Messages shared by the authentication screens (A-02-T10…T12). */
import { defineMessages, type FormatMessage } from "@/i18n";

export const authMessages = defineMessages({
  email: { id: "auth.common.email", defaultMessage: "Email", description: "Field label" },
  password: { id: "auth.common.password", defaultMessage: "Password", description: "Field label" },
  signIn: {
    id: "auth.common.signIn",
    defaultMessage: "Sign in",
    description: "Link/button to /login",
  },
  signUp: {
    id: "auth.common.signUp",
    defaultMessage: "Create an account",
    description: "Link to /signup",
  },
  working: {
    id: "auth.common.working",
    defaultMessage: "Please wait…",
    description: "Busy button",
  },
  retry: { id: "auth.common.retry", defaultMessage: "Try again", description: "Retry button" },
  emailInvalid: {
    id: "auth.common.emailInvalid",
    defaultMessage: "Enter an email address like 'dana@mapleleaf.ca'.",
    description: "Validation: malformed email",
  },
  passwordRequired: {
    id: "auth.common.passwordRequired",
    defaultMessage: "Enter your password.",
    description: "Validation: password missing on sign-in",
  },
  passwordTooShort: {
    id: "auth.common.passwordTooShort",
    defaultMessage: "Use at least 12 characters. A few unrelated words work well.",
    description: "Validation: new password shorter than 12 characters",
  },
  offline: {
    id: "auth.common.offline",
    defaultMessage: "Numo9 couldn't be reached. Make sure you're online, then try again.",
    description: "Network failure on an auth request",
  },
  serverError: {
    id: "auth.common.serverError",
    defaultMessage:
      "Something went wrong on our side and nothing was changed. Try again in a moment.",
    description: "5xx answer on an auth request",
  },
  rateLimited: {
    id: "auth.common.rateLimited",
    defaultMessage:
      "Too many attempts. For your security, wait {minutes, plural, one {# minute} other {# minutes}} before trying again.",
    description: "429 answer; minutes rounded up from Retry-After",
  },
  unexpected: {
    id: "auth.common.unexpected",
    defaultMessage:
      "That didn't work (error {status}). Try again; if it keeps happening, contact support.",
    description: "Any other unexpected HTTP status",
  },
});

/** The message for a failed request that has no field errors (network, 429, 5xx, other). */
export function requestFailureMessage(
  fm: FormatMessage,
  status: number,
  retryAfter?: number,
): string {
  if (status === 0) return fm(authMessages.offline);
  if (status === 429) {
    const minutes = Math.max(1, Math.ceil((retryAfter ?? 60) / 60));
    return fm(authMessages.rateLimited, { minutes });
  }
  if (status >= 500) return fm(authMessages.serverError);
  return fm(authMessages.unexpected, { status });
}
