/** Message API for async server components and metadata (A-10-T13). */
import { getTranslations } from "next-intl/server";

import type { FormatMessage } from "./index";

export async function getFormatMessage(): Promise<FormatMessage> {
  const t = await getTranslations();
  return (descriptor, values) => t(descriptor.id as never, values as never);
}
