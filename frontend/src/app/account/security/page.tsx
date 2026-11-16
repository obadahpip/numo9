import { AppShell } from "@/components/AppShell";
import { SecurityScreen } from "@/security-settings/SecurityScreen";

/** Account → Security (A-02-T13), `/account/security`: 2FA, recovery codes, sessions. */
export default function SecurityPage() {
  return (
    <AppShell>
      <SecurityScreen />
    </AppShell>
  );
}
