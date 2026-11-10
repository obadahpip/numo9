import { defineMessages, formatMessage } from "./index";

const messages = defineMessages({
  known: { id: "common.brand", defaultMessage: "Numo9", description: "test" },
  args: {
    id: "test.unknown.args",
    defaultMessage: "Showing {shown} of {total} for {name}",
    description: "test",
  },
});

describe("formatMessage", () => {
  it("reads the en-CA catalogue and falls back to the default message", () => {
    expect(formatMessage(messages.known)).toBe("Numo9");
    expect(formatMessage(messages.args)).toBe("Showing {shown} of {total} for {name}");
  });

  it("fills simple arguments; numbers in en-CA; unknown arguments stay visible", () => {
    expect(formatMessage(messages.args, { shown: 20, total: 2000 })).toBe(
      "Showing 20 of 2,000 for {name}",
    );
  });
});
