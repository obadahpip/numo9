import { defineMessages } from "@/i18n";

/** Documents inbox, attachments panel and "create from file" (A-06). */
export const fm = defineMessages({
  createTitle: {
    id: "files.create.title",
    defaultMessage: "Create from this file",
    description:
      "Heading of the list of records a document can become (bill, expense claim, asset)",
  },
  createLoading: {
    id: "files.create.loading",
    defaultMessage: "Loading what this file can become…",
    description: "While the create-from-file actions load",
  },
  createFailed: {
    id: "files.create.failed",
    defaultMessage: "The actions couldn't be loaded. Try again.",
    description: "When the create-from-file actions fail to load",
  },
  createNone: {
    id: "files.create.none",
    defaultMessage: "Nothing can be created from files yet.",
    description: "When no module registers a create-from-file action",
  },
  title: {
    id: "files.inbox.title",
    defaultMessage: "Documents",
    description: "Heading of the documents inbox",
  },
  intro: {
    id: "files.inbox.intro",
    defaultMessage:
      "Receipts, bills and statements waiting to be dealt with. Every file is checked for viruses before it opens.",
    description: "Text under the documents heading",
  },
  upload: {
    id: "files.inbox.upload",
    defaultMessage: "Upload files",
    description: "Button (shortcut U)",
  },
  tabInbox: { id: "files.inbox.tabInbox", defaultMessage: "Inbox", description: "Folder tab" },
  tabArchived: {
    id: "files.inbox.tabArchived",
    defaultMessage: "Archived",
    description: "Folder tab",
  },
  folders: {
    id: "files.inbox.folders",
    defaultMessage: "Folders",
    description: "Accessible name of the folder tabs",
  },
  dropHere: {
    id: "files.inbox.dropHere",
    defaultMessage: "Drop files to upload them",
    description: "Overlay shown while files are dragged over the inbox",
  },
  dropHint: {
    id: "files.inbox.dropHint",
    defaultMessage: "PDF, images (incl. HEIC), CSV, XLSX, DOCX and bank files, up to 25 MB each.",
    description: "Accepted files, under the drop overlay and the upload button",
  },
  emptyTitle: {
    id: "files.inbox.emptyTitle",
    defaultMessage: "No documents yet",
    description: "Empty inbox heading",
  },
  emptyBody: {
    id: "files.inbox.emptyBody",
    defaultMessage:
      "Add documents in three ways: drag files anywhere on this page, choose Upload files, or email them to the inbox address.",
    description: "Empty inbox: the three ways to add documents",
  },
  emptyArchived: {
    id: "files.inbox.emptyArchived",
    defaultMessage: "Archived documents appear here. Archive a document once it's dealt with.",
    description: "Empty archive",
  },
  noResults: {
    id: "files.inbox.noResults",
    defaultMessage: "No documents match these filters.",
    description: "Grid",
  },
  loadFailed: {
    id: "files.inbox.loadFailed",
    defaultMessage: "The documents couldn't be loaded.",
    description: "Error state of the inbox",
  },
  retry: { id: "files.inbox.retry", defaultMessage: "Try again", description: "Button" },
  addressTitle: {
    id: "files.address.title",
    defaultMessage: "Email documents to",
    description: "Inbox address card heading",
  },
  addressCopy: { id: "files.address.copy", defaultMessage: "Copy address", description: "Button" },
  addressCopied: {
    id: "files.address.copied",
    defaultMessage: "Address copied",
    description: "Confirmation after copying",
  },
  addressHelp: {
    id: "files.address.help",
    defaultMessage:
      "Each attachment becomes a document. Mail from unknown senders is kept and flagged.",
    description: "Under the inbox address",
  },
  colName: { id: "files.col.name", defaultMessage: "File", description: "Column" },
  colFrom: {
    id: "files.col.from",
    defaultMessage: "From",
    description: "Column: uploader or email sender",
  },
  colSource: {
    id: "files.col.source",
    defaultMessage: "Source",
    description: "Column: upload or email",
  },
  colPeriod: { id: "files.col.period", defaultMessage: "Period", description: "Column" },
  colTaxYear: { id: "files.col.taxYear", defaultMessage: "Tax year", description: "Column" },
  colTags: { id: "files.col.tags", defaultMessage: "Tags", description: "Column" },
  colStatus: { id: "files.col.status", defaultMessage: "Status", description: "Column" },
  colAdded: { id: "files.col.added", defaultMessage: "Added", description: "Column: date added" },
  unknownSender: {
    id: "files.inbox.unknownSender",
    defaultMessage: "Unknown sender",
    description: "Badge on an emailed document from an address the organisation doesn't know",
  },
  statusUploading: {
    id: "files.status.uploading",
    defaultMessage: "Uploading",
    description: "Status",
  },
  statusScanning: {
    id: "files.status.scanning",
    defaultMessage: "Checking for viruses",
    description: "Status",
  },
  statusClean: { id: "files.status.clean", defaultMessage: "Ready", description: "Status" },
  statusInfected: {
    id: "files.status.infected",
    defaultMessage: "Quarantined",
    description: "Status",
  },
  sourceEmail: { id: "files.source.email", defaultMessage: "Email", description: "Filter option" },
  sourceUpload: {
    id: "files.source.upload",
    defaultMessage: "Upload",
    description: "Filter option",
  },
  tagFilter: {
    id: "files.inbox.tagFilter",
    defaultMessage: "Tag",
    description: "Tag filter label",
  },
  anyTag: { id: "files.inbox.anyTag", defaultMessage: "Any tag", description: "Tag filter option" },
  bulkArchive: { id: "files.bulk.archive", defaultMessage: "Archive", description: "Bulk action" },
  bulkUnarchive: {
    id: "files.bulk.unarchive",
    defaultMessage: "Move to inbox",
    description: "Bulk action",
  },
  bulkTag: {
    id: "files.bulk.tag",
    defaultMessage: "Tag…",
    description: "Bulk action: opens the tag dialog",
  },
  bulkTagTitle: {
    id: "files.bulk.tagTitle",
    defaultMessage: "{count, plural, one {Tag # document} other {Tag # documents}}",
    description: "Bulk tag dialog title",
  },
  bulkDone: {
    id: "files.bulk.done",
    defaultMessage: "{count, plural, one {# document updated} other {# documents updated}}",
    description: "Announcement after a bulk change",
  },
  apply: { id: "files.bulk.apply", defaultMessage: "Apply", description: "Button" },
  cancel: { id: "files.bulk.cancel", defaultMessage: "Cancel", description: "Button" },
  fieldTags: {
    id: "files.field.tags",
    defaultMessage: "Add tags (comma-separated)",
    description: "Field",
  },
  fieldPeriod: {
    id: "files.field.period",
    defaultMessage: "Period (YYYY-MM)",
    description: "Field",
  },
  fieldTaxYear: { id: "files.field.taxYear", defaultMessage: "Tax year", description: "Field" },
  save: {
    id: "files.preview.save",
    defaultMessage: "Save",
    description: "Button: save the document's tags",
  },
  saved: { id: "files.preview.saved", defaultMessage: "Saved", description: "Confirmation" },
  saveFailed: {
    id: "files.preview.saveFailed",
    defaultMessage: "Not saved: check the period and tax year.",
    description: "Error",
  },
  previewTitle: {
    id: "files.preview.title",
    defaultMessage: "Preview",
    description: "Accessible name of the previewer panel",
  },
  previewAlt: {
    id: "files.preview.alt",
    defaultMessage: "First page of {name}",
    description: "Preview image alt text",
  },
  previewPending: {
    id: "files.preview.pending",
    defaultMessage: "The preview is being made…",
    description: "Previewer",
  },
  previewNone: {
    id: "files.preview.none",
    defaultMessage: "No preview for this type of file. Download it to open it.",
    description: "Previewer",
  },
  previewPassword: {
    id: "files.preview.password",
    defaultMessage: "This PDF is password-protected: download it to open it.",
    description: "Previewer",
  },
  previewScanning: {
    id: "files.preview.scanning",
    defaultMessage: "This file is being checked for viruses. It opens once it's ready.",
    description: "Previewer",
  },
  previewInfected: {
    id: "files.preview.infected",
    defaultMessage:
      "A virus was found in this file ({signature}). It was quarantined and can't be opened.",
    description: "Previewer: quarantined file",
  },
  download: { id: "files.preview.download", defaultMessage: "Download", description: "Button" },
  close: { id: "files.preview.close", defaultMessage: "Close preview", description: "Button" },
  detailFrom: { id: "files.preview.from", defaultMessage: "From", description: "Detail label" },
  detailSize: { id: "files.preview.size", defaultMessage: "Size", description: "Detail label" },
  detailAdded: { id: "files.preview.added", defaultMessage: "Added", description: "Detail label" },
  uploadsTitle: {
    id: "files.uploads.title",
    defaultMessage: "Uploads",
    description: "Heading of the upload progress list",
  },
  uploadProgress: {
    id: "files.uploads.progress",
    defaultMessage: "Uploading {percent}%",
    description: "Upload state",
  },
  uploadChecking: {
    id: "files.uploads.checking",
    defaultMessage: "Checking the file…",
    description: "Upload state after transfer",
  },
  uploadDone: {
    id: "files.uploads.done",
    defaultMessage: "Added — checking for viruses",
    description: "Upload state",
  },
  uploadDuplicate: {
    id: "files.uploads.duplicate",
    defaultMessage: "Already in your documents",
    description: "Upload state: same file exists",
  },
  uploadFailed: {
    id: "files.uploads.failed",
    defaultMessage: "Not uploaded",
    description: "Upload state",
  },
  uploadTooLarge: {
    id: "files.uploads.tooLarge",
    defaultMessage: "{name} is {size}; files are limited to 25 MB.",
    description: "Refused before upload",
  },
  uploadType: {
    id: "files.uploads.type",
    defaultMessage: "{name} can't be added: this type of file isn't accepted.",
    description: "Refused before upload",
  },
  gridName: {
    id: "files.grid.name",
    defaultMessage: "Documents",
    description: "Accessible name of the grid",
  },
  gridSearch: {
    id: "files.grid.search",
    defaultMessage: "Search file names, senders and tags",
    description: "Grid",
  },
  gridColumns: { id: "files.grid.columns", defaultMessage: "Columns", description: "Grid" },
  gridDensity: { id: "files.grid.density", defaultMessage: "Row height", description: "Grid" },
  gridComfortable: {
    id: "files.grid.comfortable",
    defaultMessage: "Comfortable",
    description: "Grid",
  },
  gridCompact: { id: "files.grid.compact", defaultMessage: "Compact", description: "Grid" },
  gridAll: { id: "files.grid.all", defaultMessage: "All", description: "Grid filter option" },
  gridChip: {
    id: "files.grid.chip",
    defaultMessage: "{column}: {value}",
    description: "Grid filter chip",
  },
  gridClear: { id: "files.grid.clear", defaultMessage: "Clear", description: "Grid" },
  gridSelectAll: { id: "files.grid.selectAll", defaultMessage: "Select all", description: "Grid" },
  gridSelectRow: {
    id: "files.grid.selectRow",
    defaultMessage: "Select {row}",
    description: "Grid row checkbox",
  },
  gridSelected: {
    id: "files.grid.selected",
    defaultMessage: "{count} selected",
    description: "Grid bulk bar",
  },
  gridClearSelection: {
    id: "files.grid.clearSelection",
    defaultMessage: "Clear selection",
    description: "Grid",
  },
  gridResults: {
    id: "files.grid.results",
    defaultMessage: "{shown} of {total} documents",
    description: "Grid result count",
  },
  loading: { id: "files.grid.loading", defaultMessage: "Loading documents…", description: "Grid" },
  attachTitle: {
    id: "files.attach.title",
    defaultMessage: "Attachments",
    description: "Attachments panel heading on a record",
  },
  attachCount: {
    id: "files.attach.count",
    defaultMessage: "({count, number})",
    description: "Number of attachments after the heading",
  },
  attachAdd: { id: "files.attach.add", defaultMessage: "Attach files", description: "Button" },
  attachEmpty: {
    id: "files.attach.empty",
    defaultMessage:
      "No files attached yet. Attach receipts, contracts or statements, or drop them here.",
    description: "Attachments panel, nothing attached, can edit",
  },
  attachEmptyReadOnly: {
    id: "files.attach.emptyReadOnly",
    defaultMessage: "No files attached.",
    description: "Attachments panel, nothing attached, read-only",
  },
  attachLoadFailed: {
    id: "files.attach.loadFailed",
    defaultMessage: "The attachments couldn't be loaded.",
    description: "Attachments panel error",
  },
  attachFailed: {
    id: "files.attach.failed",
    defaultMessage: "The file couldn't be attached. Try again.",
    description: "Attach or remove failed",
  },
  attachDone: {
    id: "files.attach.done",
    defaultMessage: "{name} attached",
    description: "Announcement",
  },
  attachRemoved: {
    id: "files.attach.removed",
    defaultMessage: "{name} removed from this record",
    description: "Announcement",
  },
  attachRemove: {
    id: "files.attach.remove",
    defaultMessage: "Remove {name}",
    description: "Accessible name of the remove button",
  },
  attachRemoveShort: {
    id: "files.attach.removeShort",
    defaultMessage: "Remove",
    description: "Button",
  },
  attachDownload: {
    id: "files.attach.download",
    defaultMessage: "Download {name}",
    description: "Accessible name of the download button",
  },
});
