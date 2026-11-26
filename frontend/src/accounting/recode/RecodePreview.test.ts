import { EMPTY_CHANGES, toChanges } from "./RecodePreview";

/** C-07-T12 — the new coding form as the API's `changes` (empty fields keep their value). */
test("only the fields chosen are sent", () => {
  expect(toChanges(EMPTY_CHANGES)).toBeNull();
  expect(toChanges({ ...EMPTY_CHANGES, account: "acc-rent" })).toEqual({ account: "acc-rent" });
  expect(
    toChanges({ ...EMPTY_CHANGES, taxCode: " sales.ON.zero ", category: "region", option: "" }),
  ).toEqual({ tax_code: "sales.ON.zero" });
  expect(
    toChanges({
      ...EMPTY_CHANGES,
      taxCode: "ignored",
      clearTax: true,
      category: "region",
      option: "east",
      contact: "c-1",
      clearContact: true,
    }),
  ).toEqual({ tax_code: "", tracking: { region: "east" }, contact: null });
});
