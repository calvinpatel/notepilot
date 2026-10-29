import { expect, test } from "vitest";

import { codePoints, segments } from "./slicing";

test("a span cuts the text into before, marked, and after", () => {
  expect(segments(codePoints("cough for 3 days"), [0, 5])).toEqual({
    before: "",
    marked: "cough",
    after: " for 3 days",
  });
});

test("a span counts code points, as Python does, past a character outside the BMP", () => {
  const text = "😷 cough"; // the mask is one code point and two UTF-16 units
  expect(segments(codePoints(text), [2, 7])?.marked).toBe("cough");
  expect(text.slice(2, 7)).not.toBe("cough"); // L177: the unit-counting slice drifts
});

test("an empty span marks nothing and keeps the text whole", () => {
  expect(segments(codePoints("abc"), [1, 1])).toEqual({ before: "a", marked: "", after: "bc" });
});

test.each([
  ["reversed", [2, 1]],
  ["negative start", [-1, 1]],
  ["past the end", [0, 4]],
  ["fractional", [0.5, 2]],
] as const)("a span that doesn't fit the text marks nothing: %s", (_name, span) => {
  expect(segments(codePoints("abc"), span)).toBeNull();
});
