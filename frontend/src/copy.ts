import type { components } from "./api";
import type { Outcome } from "./client";

export type ErrorCode = components["schemas"]["ErrorBody"]["error"];
type Failure = Exclude<Outcome, { kind: "result" }>;
type Wait = number | null;

function inSeconds(seconds: Wait): string {
  if (seconds === null) {
    return "shortly";
  }
  const wait = Math.max(1, seconds);
  return wait === 1 ? "in 1 second" : `in ${String(wait)} seconds`;
}

function untilMidnight(seconds: Wait): string {
  if (seconds === null) {
    return "";
  }
  const minutes = Math.max(1, Math.ceil(seconds / 60));
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  return hours === 0 ? `, in ${String(rest)}m` : `, in ${String(hours)}h ${String(rest)}m`;
}

/**
 * What each code says (§9.4, §9.10, L363). Keyed by ErrorBody's code type, so a code the API
 * gains with no line here fails tsc (L358).
 */
const COPY: Readonly<Record<ErrorCode, (status: number, wait: Wait) => string>> = {
  input_invalid: () => "That paste can't be summarized: it's empty, too short, or too long.",
  rate_limited: (_status, wait) =>
    `Too many requests from this address. Try again ${inSeconds(wait)}.`,
  budget_exhausted: (_status, wait) =>
    `The demo has used today's budget. It resets at midnight UTC${untilMidnight(wait)}.`,
  upstream_busy: (_status, wait) => `The model is busy. Try again ${inSeconds(wait)}.`,
  upstream_timeout: () => "The model took too long to answer. Try again.",
  output_truncated: () => "The model's answer was cut off. A shorter note may fit.",
  model_output_invalid: () => "The model's answer couldn't be read as a note. Try again.",
  upstream_error: () => "The model service failed. Try again.",
  internal_error: () => "Something went wrong on our side.",
  not_found: (status) => `The request failed (HTTP ${String(status)} · not_found).`,
  method_not_allowed: (status) =>
    `The request failed (HTTP ${String(status)} · method_not_allowed).`,
  http_error: (status) => `The request failed (HTTP ${String(status)} · http_error).`,
};

function isErrorCode(code: string): code is ErrorCode {
  return Object.hasOwn(COPY, code);
}

/** Anything but a result, said in place of one (§9.10, L92, L100, L363). */
export function failureCopy(failure: Failure): string {
  if (failure.kind === "no-response") {
    return "No response from the server. Check your connection and try again.";
  }
  const { status, code, requestId, retryAfter } = failure;
  if (code !== null && requestId !== null && isErrorCode(code)) {
    return `${COPY[code](status, retryAfter)} Reference: ${requestId}`;
  }
  const parts = [`HTTP ${String(status)}`];
  if (code !== null && requestId !== null) {
    parts.push(code, `request ${requestId}`);
  }
  return `The request failed: ${parts.join(" · ")}`;
}
