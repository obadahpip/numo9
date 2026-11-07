import type { Metadata } from "next";
import type { ReactNode } from "react";

import { defineMessages, formatMessage } from "@/i18n";

import "./globals.css";

const messages = defineMessages({
  title: { id: "common.brand", defaultMessage: "Numo9", description: "Product name" },
  description: {
    id: "common.tagline",
    defaultMessage: "Numbers build a brighter tomorrow",
    description: "Product tagline (page meta description)",
  },
});

export const metadata: Metadata = {
  title: formatMessage(messages.title),
  description: formatMessage(messages.description),
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="en-CA">
      <body className="min-h-screen antialiased">{children}</body>
    </html>
  );
}
