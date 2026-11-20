import { defineMessages } from "@/i18n";

export const im = defineMessages({
  invite: {
    id: "staff.invite.open",
    defaultMessage: "Invite staff",
    description: "Button above the staff list (V-05-T03)",
  },
  title: {
    id: "staff.invite.title",
    defaultMessage: "Invite a staff member",
    description: "Dialog title",
  },
  body: {
    id: "staff.invite.body",
    defaultMessage:
      "We email them a link to join your practice. It works once and for 14 days; until then they show as Pending.",
    description: "Dialog text",
  },
  email: { id: "staff.invite.email", defaultMessage: "Email", description: "Field" },
  role: { id: "staff.invite.role", defaultMessage: "Practice role", description: "Field" },
  roleAdmin: {
    id: "staff.invite.roleAdmin",
    defaultMessage: "Practice admin",
    description: "Practice role option",
  },
  roleHint: {
    id: "staff.invite.roleHint",
    defaultMessage: "You can change it later on their page.",
    description: "Field hint",
  },
  send: { id: "staff.invite.send", defaultMessage: "Send invitation", description: "Button" },
  cancel: { id: "staff.invite.cancel", defaultMessage: "Cancel", description: "Button" },
  close: { id: "staff.invite.close", defaultMessage: "Close", description: "Dialog close" },
  emailInvalid: {
    id: "staff.invite.emailInvalid",
    defaultMessage: "Enter an email address, e.g. sam@yourpractice.ca.",
    description: "Validation",
  },
  sent: {
    id: "staff.invite.sent",
    defaultMessage: "Invitation sent to {email}.",
    description: "Status after sending",
  },
  failed: {
    id: "staff.invite.failed",
    defaultMessage: "The invitation wasn't sent. Try again.",
    description: "Error",
  },
  resend: { id: "staff.invite.resend", defaultMessage: "Resend", description: "Button" },
  resendLabel: {
    id: "staff.invite.resendLabel",
    defaultMessage: "Resend the invitation to {email}",
    description: "Accessible name",
  },
  resent: {
    id: "staff.invite.resent",
    defaultMessage: "Sent again to {email}: a new link for 14 days.",
    description: "Status after resending",
  },
  revoke: { id: "staff.invite.revoke", defaultMessage: "Withdraw", description: "Button" },
  revokeLabel: {
    id: "staff.invite.revokeLabel",
    defaultMessage: "Withdraw the invitation to {email}",
    description: "Accessible name",
  },
  revoked: {
    id: "staff.invite.revoked",
    defaultMessage: "Invitation to {email} withdrawn.",
    description: "Status after withdrawing",
  },
});
