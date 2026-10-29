import type { components } from "../api";

type Result = components["schemas"]["EvalResult"];

/** One fired result: its severity, check, and detail when it has one, as text (§9.7). */
export function Finding({ result }: { readonly result: Result }) {
  return (
    <li className={`finding ${result.severity}`}>
      <strong>{result.severity.toUpperCase()}</strong> {result.check}
      {result.detail !== "" && `: ${result.detail}`}
    </li>
  );
}
