import type { Metadata } from "next";
import { NextIntlClientProvider } from "next-intl";
import { getLocale, getMessages } from "next-intl/server";
import type { ReactNode } from "react";

import { defineMessages } from "@/i18n";
import { getFormatMessage } from "@/i18n/server";

import "./globals.css";

const messages = defineMessages({
  title: { id: "common.brand", defaultMessage: "Numo9", description: "Product name" },
  description: {
    id: "common.tagline",
    defaultMessage: "Numbers build a brighter tomorrow",
    description: "Product tagline (page meta description)",
  },
});

export async function generateMetadata(): Promise<Metadata> {
  const fm = await getFormatMessage();
  return { title: fm(messages.title), description: fm(messages.description) };
}

/** Root layout: the request's locale (A-10-T13) on `<html lang>` and in the i18n provider. */
export default async function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  const [locale, catalogue] = await Promise.all([getLocale(), getMessages()]);
  return (
    <html lang={locale}>
      <body className="min-h-screen antialiased">
        <NextIntlClientProvider locale={locale} messages={catalogue} timeZone="America/Toronto">
          {children}
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
