import type { components } from "./api";

type Claim = components["schemas"]["ClinicalClaim"];
type Report = components["schemas"]["EvalReport"];
type Result = components["schemas"]["EvalResult"];
type Severity = components["schemas"]["Severity"];

/** Where each result goes, by its own flags (§9.7, §9.10, L176, L361). */
export interface Placement {
  /** By claim id: the fired results naming that claim, critical first. */
  readonly byClaim: ReadonlyMap<number, readonly Result[]>;
  /** Fired results naming no claim in the note, critical first. */
  readonly noteLevel: readonly Result[];
  /** Results that errored: they didn't run on this note (invariant 12). */
  readonly errored: readonly Result[];
  /** Results that passed, by name. */
  readonly passed: readonly Result[];
}

const SEVERITY_ORDER: Readonly<Record<Severity, number>> = { critical: 0, warning: 1, info: 2 };

function bySeverity(results: readonly Result[]): Result[] {
  return [...results].sort((a, b) => SEVERITY_ORDER[a.severity] - SEVERITY_ORDER[b.severity]);
}

/**
 * Join the report to the note by claim id. A fired result whose ids name no claim in the
 * note joins the note-level ones.
 */
export function place(claims: readonly Claim[], report: Report): Placement {
  const ids = new Set(claims.map((claim) => claim.id));
  const byClaim = new Map<number, Result[]>();
  const noteLevel: Result[] = [];
  const errored: Result[] = [];
  const passed: Result[] = [];
  for (const result of report.results) {
    if (result.errored) {
      errored.push(result);
    } else if (result.passed) {
      passed.push(result);
    } else {
      const named = result.claim_ids.filter((id) => ids.has(id));
      if (named.length === 0) {
        noteLevel.push(result);
      }
      for (const id of new Set(named)) {
        const onClaim = byClaim.get(id) ?? [];
        onClaim.push(result);
        byClaim.set(id, onClaim);
      }
    }
  }
  const sorted = new Map([...byClaim].map(([id, results]) => [id, bySeverity(results)]));
  return { byClaim: sorted, noteLevel: bySeverity(noteLevel), errored, passed };
}

/**
 * No claims, and results that all passed: nothing clinical was found, by checks that ran
 * (§9.10, L363). An errored check could have been the one to fire, and a report with no
 * results checked nothing, so either keeps the note out of this state (invariant 12).
 */
export function isEmpty(claims: readonly Claim[], report: Report): boolean {
  const checked = report.results.length > 0;
  return claims.length === 0 && checked && report.results.every((result) => result.passed);
}

/** The verdict line's parts (L102, L176, L361). */
export interface Verdict {
  /** The report's own verdict, never recomputed (L102). */
  readonly allCriticalPassed: boolean;
  /** The checks selected, less the ones that errored. */
  readonly ran: number;
  /** Fired results at warning severity. */
  readonly warnings: number;
  /** The checks that errored. */
  readonly didntRun: number;
}

export function verdict(report: Report): Verdict {
  const didntRun = report.results.filter((result) => result.errored).length;
  const warnings = report.results.filter(
    (result) => !result.passed && !result.errored && result.severity === "warning",
  ).length;
  return {
    allCriticalPassed: report.all_critical_passed,
    ran: report.checks_run.length - didntRun,
    warnings,
    didntRun,
  };
}
