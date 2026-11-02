import { useEffect, useId, useRef } from "react";

import { clauseSegments } from "../slicing";

interface Props {
  /** The sent text's code points (L177). */
  readonly points: readonly string[];
  /** The active claim's span, or null when no claim is active or it has none. */
  readonly span: readonly [number, number] | null;
  /** The active claim's clause from the response's clause_spans, or null with none (L380). */
  readonly clause: readonly [number, number] | null;
  /** Yellow for a paraphrased claim (§9.7). */
  readonly paraphrased: boolean;
}

/**
 * The text as sent, with the active claim's span marked and the rest of its clause tinted
 * lighter: one highlight at a time (§9.10, L380). A clause that doesn't hold the span tints
 * the span alone.
 */
export function SourcePane({ points, span, clause, paraphrased }: Props) {
  const heading = useId();
  const mark = useRef<HTMLElement>(null);
  const kind = paraphrased ? "paraphrased" : "grounded";
  const cut =
    span === null
      ? null
      : (clauseSegments(points, clause ?? span, span) ?? clauseSegments(points, span, span));
  useEffect(() => {
    // jsdom has no scrollIntoView, hence the optional call
    mark.current?.scrollIntoView?.({ block: "nearest" });
  }, [span]);
  return (
    <section className="source" aria-labelledby={heading}>
      <h2 id={heading}>Source (as sent)</h2>
      <pre>
        {cut === null ? (
          points.join("")
        ) : (
          <>
            {cut.before}
            <span className={`clause ${kind}`}>
              {cut.lead}
              <mark ref={mark} className={kind}>
                {cut.marked}
              </mark>
              {cut.trail}
            </span>
            {cut.after}
          </>
        )}
      </pre>
    </section>
  );
}
