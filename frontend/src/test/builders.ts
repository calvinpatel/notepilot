import type { components } from "../api";

type Body = components["schemas"]["SummarizeResponse"];
type Claim = components["schemas"]["ClinicalClaim"];
type Report = components["schemas"]["EvalReport"];
type Result = components["schemas"]["EvalResult"];

/** A claim, grounded unless the test says otherwise. */
export function claim(fields: Partial<Claim> & Pick<Claim, "id">): Claim {
  return {
    text: `claim ${fields.id}`,
    section: "S",
    source_quote: `quote ${fields.id}`,
    source_span: [0, 1],
    grounding_score: 100,
    flags: [],
    ...fields,
  };
}

/** A check's result, passed unless the test says otherwise. */
export function result(fields: Partial<Result> & Pick<Result, "check">): Result {
  return {
    severity: "warning",
    passed: true,
    errored: false,
    detail: "",
    claim_ids: [],
    ...fields,
  };
}

/** A report over the given results; checks_run defaults to their checks. */
export function report(fields: Partial<Report> & Pick<Report, "results">): Report {
  return {
    checks_run: fields.results.map((r) => r.check),
    checks_version: "d148b9ff9024",
    judge_usage: { input_tokens: 0, output_tokens: 0 },
    checks_config: { fuzzy_score_cutoff: 90, min_quote_content_tokens: 2 },
    judge_version: null,
    all_critical_passed: true,
    ...fields,
  };
}

/** A /summarize body for the given claims and report. */
export function summarizeBody(fields: Partial<Body> & Pick<Body, "note" | "report">): Body {
  return {
    note_id: "6f1c2a9e-0000-4000-8000-000000000001",
    metadata: {
      model: "claude-test",
      prompt_version: "306bbaa5126a",
      usage: { input_tokens: 1899, output_tokens: 797 },
      validation_attempts: 1,
    },
    ...fields,
  };
}

/** A fetch response carrying body as JSON, or as text when it is a string. */
export function jsonResponse(
  status: number,
  body: unknown,
  headers: Readonly<Record<string, string>> = {},
): Response {
  const text = typeof body === "string" ? body : JSON.stringify(body);
  const type = typeof body === "string" ? "text/html" : "application/json";
  return new Response(text, { status, headers: { "Content-Type": type, ...headers } });
}
