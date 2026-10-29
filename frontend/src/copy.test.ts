import { expect, test } from "vitest";

import { failureCopy } from "./copy";

type Failure = Parameters<typeof failureCopy>[0];

function error(status: number, code: string | null, retryAfter: number | null = null): Failure {
  return { kind: "error", status, code, requestId: code === null ? null : "r1", retryAfter };
}

test.each([
  [422, "input_invalid", "That paste can't be summarized: it's empty, too short, or too long."],
  [429, "rate_limited", "Too many requests from this address. Try again shortly."],
  [503, "budget_exhausted", "The demo has used today's budget. It resets at midnight UTC."],
  [503, "upstream_busy", "The model is busy. Try again shortly."],
  [504, "upstream_timeout", "The model took too long to answer. Try again."],
  [502, "output_truncated", "The model's answer was cut off. A shorter note may fit."],
  [502, "model_output_invalid", "The model's answer couldn't be read as a note. Try again."],
  [502, "upstream_error", "The model service failed. Try again."],
  [500, "internal_error", "Something went wrong on our side."],
  [404, "not_found", "The request failed (HTTP 404 · not_found)."],
  [405, "method_not_allowed", "The request failed (HTTP 405 · method_not_allowed)."],
  [400, "http_error", "The request failed (HTTP 400 · http_error)."],
])("%s %s has its own line and the request's reference", (status, code, line) => {
  expect(failureCopy(error(status, code))).toBe(`${line} Reference: r1`);
});

test.each([
  [30, "in 30 seconds"],
  [1, "in 1 second"],
  [0, "in 1 second"],
])("a 429 says the wait Retry-After gave: %s", (wait, said) => {
  expect(failureCopy(error(429, "rate_limited", wait))).toContain(`Try again ${said}.`);
});

test("a busy 503 says the wait when Retry-After gave one", () => {
  expect(failureCopy(error(503, "upstream_busy", 20))).toContain("Try again in 20 seconds.");
});

test.each([
  [25920, ", in 7h 12m"],
  [3600, ", in 1h 0m"],
  [61, ", in 2m"],
  [59, ", in 1m"],
])("the budget's 503 says how long to midnight UTC: %s seconds", (wait, said) => {
  expect(failureCopy(error(503, "budget_exhausted", wait))).toContain(`midnight UTC${said}.`);
});

test("a code the page doesn't know says its status, code, and request id", () => {
  const said = "The request failed: HTTP 418 · teapot · request r1";
  expect(failureCopy(error(418, "teapot"))).toBe(said);
});

test("a body that isn't ours says its status alone", () => {
  expect(failureCopy(error(502, null))).toBe("The request failed: HTTP 502");
});

test("no response says so, and what to try", () => {
  expect(failureCopy({ kind: "no-response" })).toBe(
    "No response from the server. Check your connection and try again.",
  );
});
