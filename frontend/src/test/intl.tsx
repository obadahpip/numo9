/**
 * i18n for component tests (A-10-T13): the real en-CA catalogue through next-intl, so tests see
 * the same text users do.
 */
import { render, type RenderOptions } from "@testing-library/react";
import { createTranslator, NextIntlClientProvider } from "next-intl";
import type { ReactElement, ReactNode } from "react";

import enCA from "../../messages/en-CA.json";
import type { FormatMessage } from "../i18n";

export const testMessages = enCA;

export function IntlWrapper({
  children,
  locale = "en-CA",
  messages = enCA,
}: {
  children?: ReactNode;
  locale?: string;
  messages?: Record<string, unknown>;
}) {
  return (
    <NextIntlClientProvider locale={locale} messages={messages} timeZone="America/Toronto">
      {children}
    </NextIntlClientProvider>
  );
}

export function renderWithIntl(ui: ReactElement, options?: Omit<RenderOptions, "wrapper">) {
  return render(ui, { wrapper: IntlWrapper, ...options });
}

/** A FormatMessage over the en-CA catalogue (for pure functions and mocked server helpers). */
export function testFormatMessage(): FormatMessage {
  const t = createTranslator({ locale: "en-CA", messages: enCA });
  return (descriptor, values) => t(descriptor.id as never, values as never);
}
