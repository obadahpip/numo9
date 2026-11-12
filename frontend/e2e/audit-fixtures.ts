/** Audit event fixtures in the API's shape (backend/numo9/audit/presenter.py), A-04-T09/T10. */
export const SAM = "5a1b2c3d-0000-4000-8000-000000000001";

export function auditEvent(overrides: Record<string, unknown> = {}) {
  return {
    id: "e0000000-0000-4000-8000-000000000001",
    at: "2026-10-26T20:33:00Z",
    action: "contacts.contact.updated",
    action_label: "Edited",
    verb: "updated",
    actor: {
      kind: "user",
      label: "Sam Patel (sam@refined.ca)",
      user: { id: SAM, name: "Sam Patel", email: "sam@refined.ca" },
      impersonator: null,
    },
    record: {
      type: "contacts.Contact",
      type_label: "Contact",
      id: "c0000000-0000-4000-8000-000000000001",
      label: "Maple Leaf Supply Ltd.",
    },
    changes: [
      {
        field: "credit_limit",
        label: "Credit limit",
        old: "5000.00",
        new: "7500.00",
        masked: false,
      },
      {
        field: "bank_account",
        label: "Bank account",
        old: { masked: true },
        new: { masked: true },
        masked: true,
      },
    ],
    meta: {},
    ip: "203.0.113.9",
    device: "Mozilla/5.0",
    request_id: "4f1c0e2b9a7d4c3e8b6a5d4c3b2a1f0e",
    batch_id: null,
    is_batch_summary: false,
    ...overrides,
  };
}
