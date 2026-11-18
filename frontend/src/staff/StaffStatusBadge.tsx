import { Badge } from "@numo9/ui";

import { useFormatMessage } from "@/i18n";

import { STAFF_STATUS_TONES, staffStatusLabel, type StaffStatus } from "./status";

/** Status of a practice member (V-05-T09): tone from STAFF_STATUS_TONES, text always shown. */
export function StaffStatusBadge({ status }: { status: StaffStatus }) {
  const fm = useFormatMessage();
  return (
    <Badge tone={STAFF_STATUS_TONES[status]} dot data-status={status}>
      {staffStatusLabel(status, fm)}
    </Badge>
  );
}
