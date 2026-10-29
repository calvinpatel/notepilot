import type { components } from "../api";

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
