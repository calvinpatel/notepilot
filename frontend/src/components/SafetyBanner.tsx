import { useId } from "react";

import type { components } from "../api";
import { Finding } from "./Finding";

type Result = components["schemas"]["EvalResult"];

interface Props {
  readonly noteLevel: readonly Result[];
  readonly errored: readonly Result[];
}

/** The top-of-note banner (§9.7): note-level findings, and the checks that didn't run. */
export function SafetyBanner({ noteLevel, errored }: Props) {
  const heading = useId();
  if (noteLevel.length === 0 && errored.length === 0) {
    return null;
  }
  return (
    <section className="banner" aria-labelledby={heading}>
      <h2 id={heading}>Note-level findings</h2>
      {noteLevel.length > 0 && (
        <ul>
          {noteLevel.map((result, index) => (
            <Finding key={`${result.check}-${String(index)}`} result={result} />
          ))}
        </ul>
      )}
      {errored.length > 0 && (
        <p>Didn't run on this note: {errored.map((result) => result.check).join(", ")}</p>
      )}
    </section>
  );
}
