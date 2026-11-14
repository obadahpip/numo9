import { defineMessages } from "@/i18n";

/** Contacts (B-01): the live duplicate panel (B-01-T16). */
export const cm = defineMessages({
  duplicatesTitle: {
    id: "contacts.duplicates.title",
    defaultMessage: "Possible duplicates ({count})",
    description:
      "Heading of the panel listing existing contacts that look like the one being typed",
  },
  duplicatesIntro: {
    id: "contacts.duplicates.intro",
    defaultMessage: "Checked as you type. You can still save this contact.",
    description: "Text under the possible-duplicates heading: it's a warning, not a block",
  },
  duplicatesAnnounce: {
    id: "contacts.duplicates.announce",
    defaultMessage:
      "{count, plural, one {# possible duplicate found} other {# possible duplicates found}}",
    description: "Screen-reader announcement when the duplicate check finds contacts",
  },
  reasonBn: {
    id: "contacts.duplicates.reasonBn",
    defaultMessage: "Business Number matches",
    description: "Why a contact is listed: same CRA Business Number",
  },
  reasonTaxId: {
    id: "contacts.duplicates.reasonTaxId",
    defaultMessage: "Tax ID matches",
    description: "Why a contact is listed: same tax ID",
  },
  reasonEmail: {
    id: "contacts.duplicates.reasonEmail",
    defaultMessage: "Email address matches",
    description: "Why a contact is listed: a person of that contact has the same email address",
  },
  reasonName: {
    id: "contacts.duplicates.reasonName",
    defaultMessage: "Name {percent}% similar",
    description: "Why a contact is listed: its name is similar; percent is 60 to 100",
  },
  contactMeta: {
    id: "contacts.duplicates.contactMeta",
    defaultMessage: "· {number} · {province}",
    description: "After a listed contact's name: its contact number and province code (e.g. ON)",
  },
  archived: {
    id: "contacts.duplicates.archived",
    defaultMessage: "Archived",
    description: "Badge on a listed contact that is archived",
  },
  noProvince: {
    id: "contacts.duplicates.noProvince",
    defaultMessage: "No province",
    description: "Shown instead of the province when the listed contact has no Canadian address",
  },
  open: {
    id: "contacts.duplicates.open",
    defaultMessage: "Open {name}",
    description: "Link: open the existing contact (accessible name includes the contact)",
  },
  openShort: {
    id: "contacts.duplicates.openShort",
    defaultMessage: "Open",
    description: "Visible text of the link that opens the existing contact",
  },
  merge: {
    id: "contacts.duplicates.merge",
    defaultMessage: "Merge…",
    description:
      "Button: merge the contact being typed with the listed one (opens the merge dialog)",
  },
  mergeLabel: {
    id: "contacts.duplicates.mergeLabel",
    defaultMessage: "Merge with {name}",
    description: "Accessible name of the merge button",
  },
  ignore: {
    id: "contacts.duplicates.ignore",
    defaultMessage: "Ignore",
    description: "Button: hide this possible duplicate (it is not the same contact)",
  },
  ignoreLabel: {
    id: "contacts.duplicates.ignoreLabel",
    defaultMessage: "Ignore {name}",
    description: "Accessible name of the ignore button",
  },
});
