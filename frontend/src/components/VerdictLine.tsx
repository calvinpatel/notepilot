import type { Verdict } from "../findings";

function count(n: number, one: string, many: string): string {
  return `${String(n)} ${n === 1 ? one : many}`;
}

/** The verdict as the report states it, with what ran beside it (L102, L361). */
export function VerdictLine({ verdict }: { readonly verdict: Verdict }) {
  const parts = [
    verdict.allCriticalPassed ? "All critical checks passed." : "Not all critical checks passed.",
    `${String(verdict.ran)} ran`,
  ];
  if (verdict.warnings > 0) {
    parts.push(count(verdict.warnings, "warning", "warnings"));
  }
  if (verdict.didntRun > 0) {
    parts.push(`${String(verdict.didntRun)} didn't run`);
  }
  return <p className="verdict">{parts.join(" · ")}</p>;
}
